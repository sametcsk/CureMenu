import json
import asyncio
import unicodedata
from fastapi import APIRouter, Request, Depends, BackgroundTasks, HTTPException
from fastapi.responses import StreamingResponse
from fastapi.concurrency import run_in_threadpool
import sqlite3

from src.models import ChatRequest
from src.database import (
    get_db,
    etkilesim_logla,
    klinik_karar_getir,
    klinik_karar_kaydet,
    klinik_kararlari_getir,
    loglari_getir_db,
)
from src.auth import get_current_user
from src.messages import PROFIL_GEREKLI
from src.governance.decision import build_decision_record, calculate_confidence
from src.agent_state import create_initial_state
from src.memory import build_memory_namespace, hafizadakini_getir
from src.governance.events import apply_event, make_event
from src.graph import app as langgraph_app
from src.nodes import _quality_profile_from_summary
from src.quality.policy_engine import PolicyEngine
from src.quality.rule_engine import RuleEngine
from src.logger import get_logger, log_failure
from src.config import settings
from src.profil_utils import hedef_ilaclari, profil_ozeti_olustur, aile_profil_ozeti_olustur
from src.database import profil_getir_db
from src.messages import PROFIL_BULUNAMADI
from src.medical_knowledge.normalizer import extract_medication_mentions, normalize_text
from src.rate_limit import authenticated_user_or_ip, limiter

logger = get_logger(__name__)
router = APIRouter()

# NEMO GUARDRAILS
rails = None
if settings.ENABLE_NEMO_GUARDRAILS:
    try:
        from nemoguardrails import LLMRails, RailsConfig
        rails_config = RailsConfig.from_path("config")
        rails = LLMRails(rails_config)
    except Exception as e:
        log_failure(logger, "guardrails_initialize", e, component="chat")


def _get_profil_ve_hedef(telefon: str, kimin_icin: str, db: sqlite3.Connection):
    profil = profil_getir_db(telefon, conn=db)
    if profil is None:
        raise HTTPException(status_code=404, detail=PROFIL_BULUNAMADI)

    if kimin_icin == "aile":
        return profil, None

    hedef = profil.ana_kullanici
    if kimin_icin != "kendim":
        hedef = next((uye for uye in profil.aile_uyeleri if uye.ad.lower() == kimin_icin.lower()), None)

    if hedef is None:
        raise HTTPException(status_code=400, detail=PROFIL_GEREKLI)

    return profil, hedef


def _profil_baglamini_hazirla(telefon: str, kimin_icin: str, db: sqlite3.Connection):
    profil, hedef = _get_profil_ve_hedef(telefon, kimin_icin, db=db)
    if kimin_icin == "aile":
        return profil, aile_profil_ozeti_olustur(profil), build_memory_namespace(telefon, "family")

    if hedef is None:
        raise HTTPException(status_code=400, detail=PROFIL_GEREKLI)
    return profil, profil_ozeti_olustur(hedef), build_memory_namespace(telefon, f"member:{hedef.id}")


def _sse(event: str, payload: dict | None = None) -> str:
    return f"event: {event}\ndata: {json.dumps(payload or {}, ensure_ascii=False)}\n\n"

def _normalized_message(message: str) -> str:
    text = (message or "").strip().lower()
    text = unicodedata.normalize("NFKD", text)
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    return text.replace("ı", "i")

def _prompt_injection_warning(message: str) -> str | None:
    text = _normalized_message(message)
    risky_patterns = (
        "ignore previous instructions", "önceki talimat", "onceki talimat",
        "system prompt", "developer message", "gizli prompt",
        "promptu göster", "promptu goster", "kuralları unut",
        "kurallari unut", "jailbreak",
    )
    if any(pattern in text for pattern in risky_patterns):
        return (
            "Bu istekte sistem kurallarını devre dışı bırakmaya yönelik bir ifade görüyorum. "
            "Gizli talimatları veya iç yapılandırmayı paylaşamam. Beslenme, menü, tahlil ya da "
            "profiline uygun güvenli yemek seçimi konusunda yardımcı olabilirim."
        )
    return None

def _guardrail_block_state(initial_state: dict, content: str) -> dict:
    confidence = calculate_confidence(safe=False, evidence_found=False, citations=[], deterministic_block=True)
    blocked_state = apply_event(initial_state, "InputGuardrailBlocked", "nemo_guardrails", status="blocked", metadata={"reason": "pre_graph_guardrail", "response_preview": content[:160]})
    blocked_state.update({
        "hedef_islem": "INPUT_GUARDRAIL_BLOCKED", "guvenli_mi": False, "uyari_mesaji": content, "tarif_metni": None,
        "uzman_onerisi": None, "risk_score": confidence["medical_risk"], "confidence": confidence, "citations": []
    })
    return blocked_state

def _is_small_talk(message: str) -> bool:
    text = _normalized_message(message)
    small_talk = {"merhaba", "selam", "selamlar", "slm", "mrb", "naber", "nasilsin", "nasilsiniz", "iyi misin", "gunaydin", "iyi aksamlar"}
    return text in small_talk or len(text) <= 12 and any(word in text for word in small_talk)

def _is_lab_question(message: str) -> bool:
    text = _normalized_message(message)
    keywords = ("tahlil", "kan", "rapor", "kolesterol", "glukoz", "şeker", "seker", "hb", "hba1c")
    return any(keyword in text for keyword in keywords)

def _simple_chat_message(user_message: str, profil_ozeti: str, klinik_hafiza: list[str]) -> str | None:
    if _is_small_talk(user_message):
        return "Merhaba, buradayım. İstersen bugün ne yesem, dışarıda ne seçsem ya da profilime göre nelere dikkat etmeliyim diye birlikte hızlıca bakabiliriz."
    if _is_lab_question(user_message):
        if klinik_hafiza:
            return "Tahlil notlarını görüyorum. Burada teşhis koyamam ya da tedavi düzenleyemem; ama beslenme açısından daha dikkatli ilerlemene yardım edebilirim.\n\n- Değerlerinde doktorunun özellikle takip dediği bir alan varsa onu yaz, öğün seçimini ona göre daraltalım.\n- Bugün için güvenli yaklaşım: aşırı tuzlu, çok şekerli ve işlenmiş seçeneklerden uzak dur; protein, sebze ve tam tahıl dengesini koru.\n- Yeni belirti, çok yüksek/düşük değer veya ilaç değişikliği varsa doktorunla görüşmeni öneririm."
        return "Henüz kayıtlı bir tahlil dosyası göremiyorum. Tahlillerim alanından PDF yüklediğinde sonraki beslenme önerilerinde bunu dikkate alabilirim. Acil ya da yeni belirti varsa beklemeden doktoruna danışmalısın."
    return None

def _simple_chat_state(initial_state: dict, answer: str) -> dict:
    quality_profile = _quality_profile_from_summary(initial_state.get("profil_ozeti", ""))
    policy_result = PolicyEngine().check_policy(quality_profile, "SOHBET")
    rule_result = RuleEngine().check_rules(quality_profile, answer, [answer])
    found_risks = rule_result.get("found_risks", [])
    is_safe = not found_risks
    confidence = calculate_confidence(
        safe=is_safe,
        evidence_found=False,
        citations=[],
        deterministic_block=bool(found_risks),
    )
    policy_warnings = list(policy_result.get("applied_policies") or [])
    if policy_result.get("requires_review"):
        confidence["medical_risk"] = max(float(confidence.get("medical_risk", 0.0)), 0.5)
    state = apply_event(
        initial_state,
        "FastAnswerGenerated",
        "conversation_capability",
        metadata={"reason": "simple_chat_or_lab_guidance", "output_chars": len(answer)},
    )
    state = dict(state)
    state["governance_events"] = list(state.get("governance_events") or []) + [
        make_event(
            "PolicyChecked",
            "policy_engine",
            status="review" if policy_result.get("requires_review") else "ok",
            metadata={
                "fast_path": True,
                "requires_review": bool(policy_result.get("requires_review")),
                "policies_count": len(policy_result.get("applied_policies", [])),
            },
        ),
        make_event(
            "RuleChecked",
            "rule_engine",
            status="blocked" if found_risks else "ok",
            metadata={
                "fast_path": True,
                "risk_count": len(found_risks),
                "medical_risk_score": rule_result.get("medical_risk_score", 0.0),
            },
        ),
        make_event(
            "RiskClassified",
            "fast_path_safety",
            status="blocked" if found_risks else "ok",
            metadata={"fast_path": True, "risk_score": confidence["medical_risk"]},
        ),
    ]
    state.update({
        "hedef_islem": "SOHBET", "guvenli_mi": is_safe,
        "uyari_mesaji": " ".join([*found_risks, *policy_warnings]), "tarif_metni": answer,
        "uzman_onerisi": None, "risk_score": confidence["medical_risk"], "confidence": confidence, "citations": []
    })
    return state


def _merge_medications(profile_medications: list[str], message: str) -> tuple[list[str], list[str]]:
    message_medications = extract_medication_mentions(message)
    merged: list[str] = []
    seen: set[str] = set()
    for medication in [*(profile_medications or []), *message_medications]:
        key = normalize_text(str(medication))
        if key and key not in seen:
            seen.add(key)
            merged.append(str(medication).strip())
    return merged, message_medications


def _is_previous_answer_source_question(message: str) -> bool:
    text = _normalized_message(message)
    refers_to_previous = any(
        phrase in text
        for phrase in ("bu cevap", "bu cevab", "bu yanit", "onceki cevap", "onceki cevab", "onceki yanit")
    )
    return refers_to_previous and any(word in text for word in ("kaynak", "kayna", "dayanak", "referans"))


def _previous_answer_source_state(
    initial_state: dict,
    *,
    telefon: str,
    db: sqlite3.Connection,
) -> tuple[dict, str] | None:
    if not _is_previous_answer_source_question(initial_state.get("istek", "")):
        return None

    decisions = klinik_kararlari_getir(telefon, limit=1, conn=db)
    previous = klinik_karar_getir(decisions[0]["decision_id"], conn=db) if decisions else None
    recorded_citations = list((previous or {}).get("citations") or [])
    verified_citations = [
        citation
        for citation in recorded_citations
        if str(citation.get("source_id") or "").strip()
        and str(citation.get("evidence_span") or "").strip()
    ]

    if verified_citations:
        source_lines = [
            f"- {citation.get('title') or citation.get('source_id')}"
            for citation in verified_citations
        ]
        answer = (
            "Önceki yanıtın karar kaydında doğrulanabilir kaynaklar bulunuyor:\n"
            + "\n".join(source_lines)
            + f"\n\nKarar kaydı: {previous.get('decision_id')}"
        )
    else:
        answer = (
            "Önceki yanıt için doğrulanabilir bir kaynak kaydı bulunmuyor. "
            "Bu nedenle belirli bir kurum, rehber veya makale adı vermeyeceğim. "
            "Sağlıkla ilgili belirsiz bir noktada doktorunuza, eczacınıza veya diyetisyeninize danışın."
        )

    state = _simple_chat_state(initial_state, answer)
    state["hedef_islem"] = "SOURCE_DISCLOSURE"
    state["citations"] = verified_citations
    state = apply_event(
        state,
        "SourceDisclosureGenerated",
        "api.chat",
        metadata={
            "previous_decision_found": previous is not None,
            "verified_citation_count": len(verified_citations),
        },
    )
    return state, answer


def _safety_outcome(result: dict) -> tuple[bool, bool]:
    risk_score = float(result.get("risk_score") or 0.0)
    blocked = result.get("guvenli_mi") is False
    review_required = risk_score >= 0.5
    relevant_events = {
        "MedicationSafetyChecked",
        "MedicationReviewRequired",
        "RuleTriggered",
        "RuleChecked",
        "RiskClassified",
    }
    for event in result.get("governance_events") or []:
        if event.get("event_type") not in relevant_events:
            continue
        metadata = event.get("metadata") or {}
        blocked = blocked or bool(metadata.get("blocking")) or event.get("status") == "blocked"
        review_required = review_required or event.get("status") in {"review", "fallback"}
        review_required = review_required or bool(metadata.get("needs_professional_review"))
        review_required = review_required or bool(metadata.get("requires_review"))
    return blocked, review_required


def _final_cevap_metni(result: dict, streamed_text: str = "") -> str:
    warning = str(result.get("uyari_mesaji") or "").strip()
    base_answer = str(
        result.get("tarif_metni")
        or result.get("uzman_onerisi")
        or result.get("adime_raporu")
        or streamed_text
        or ""
    ).strip()
    blocked, review_required = _safety_outcome(result)
    if blocked:
        reason = warning or "Bu seçeneğin sağlık profiliyle güvenli uyumu doğrulanamadı."
        return (
            f"Güvenlik uyarısı: {reason}\n\n"
            "Bu seçeneği uygulamadan önce doktorunuza, eczacınıza veya diyetisyeninize danışın."
        )
    if review_required:
        reason = warning or "İlaç-besin etkileşimi veya önerinin güvenli uyumu doğrulanamadı."
        professional_warning = (
            "Bu öneriyi uygulamadan önce doktorunuza, eczacınıza veya diyetisyeninize danışın."
        )
        parts = [f"Doğrulama uyarısı: {reason}"]
        if base_answer and base_answer != warning:
            parts.append(base_answer)
        if professional_warning.casefold() not in "\n".join(parts).casefold():
            parts.append(professional_warning)
        return "\n\n".join(parts)
    return base_answer or warning

def _chat_fallback_message(profil_ozeti: str, user_message: str) -> str:
    request_hint = user_message.strip()[:140] if user_message else "beslenme sorusu"
    profile_hint = "Profilindeki hastalik, alerji ve ilac bilgilerini dikkate alarak ilerlemem gerekiyor."
    if not profil_ozeti:
        profile_hint = "Sana ozel konusabilmem icin profil bilgilerini net gormem gerekiyor."
    return f"Su an akilli oneri motoruna baglanirken bir aksama yasadim, ama seni bosta birakmayacagim.\n\n- Istegin: {request_hint}\n- Guvenlik notum: {profile_hint}\n- Bugun icin en guvenli yaklasim: hafif, az tuzlu, islenmemis ve alerji riski tasimayan bir ogun sec; emin olmadigin ilac-besin eslesmelerinde doktoruna veya diyetisyenine danis.\n\nBirazdan tekrar denediginde daha ayrintili ve kisisel bir oneri hazirlayabilirim."

def _chat_fallback_state(initial_state: dict, fallback_message: str, error: Exception) -> dict:
    confidence = calculate_confidence(safe=True, evidence_found=False, citations=[])
    fallback_state = apply_event(initial_state, "AIFallbackActivated", "api.chat", status="fallback", metadata={"error_type": type(error).__name__, "message": str(error)[:180]})
    fallback_state.update({
        "hedef_islem": "SOHBET_FALLBACK", "guvenli_mi": True, "uyari_mesaji": "", "tarif_metni": fallback_message,
        "uzman_onerisi": None, "risk_score": confidence["medical_risk"], "confidence": confidence, "citations": []
    })
    return fallback_state

@router.post("/api/chat")
@limiter.limit("12/minute", key_func=authenticated_user_or_ip)
async def chat(request: Request, req: ChatRequest, bg_tasks: BackgroundTasks, telefon: str = Depends(get_current_user), db: sqlite3.Connection = Depends(get_db)):
    profil, profil_ozeti, kullanici_id = _profil_baglamini_hazirla(telefon, req.kimin_icin, db=db)
    ilaclar, message_medications = _merge_medications(
        hedef_ilaclari(profil, req.kimin_icin),
        req.mesaj,
    )
    
    if kullanici_id is None:
        raise HTTPException(status_code=400, detail=PROFIL_GEREKLI)
    
    gecmis_yemek = await run_in_threadpool(hafizadakini_getir, kullanici_id, "yemek", 3)
    gecmis_klinik = await run_in_threadpool(hafizadakini_getir, kullanici_id, "SAĞLIK RAPORU TAHLİL KAN", 2)
    
    gecmis = gecmis_yemek + gecmis_klinik
    
    son_loglar = loglari_getir_db(telefon, limit=10, conn=db)
    sohbet_gecmisi = []
    for log in reversed(son_loglar):
        sayfa = log.get("sayfa", "Sistem")
        istek = log["istek"]
        if sayfa != "CureBot":
            istek = f"[{sayfa} İşlemi Gerçekleştirildi]: {istek}"
            
        sohbet_gecmisi.append({"role": "user", "content": istek})
        sohbet_gecmisi.append({"role": "assistant", "content": log["cevap"]})
    
    initial_state = create_initial_state(
        istek=req.mesaj, profil_ozeti=profil_ozeti, hafiza=gecmis, sohbet_gecmisi=sohbet_gecmisi, ilaclar=ilaclar,
    )
    if message_medications:
        initial_state = apply_event(
            initial_state,
            "MedicationMentionExtracted",
            "medical_knowledge.normalizer",
            metadata={
                "message_medication_count": len(message_medications),
                "merged_medication_count": len(ilaclar),
            },
        )

    injection_answer = _prompt_injection_warning(req.mesaj)
    if injection_answer:
        blocked_state = _guardrail_block_state(initial_state, injection_answer)
        decision_record = build_decision_record(blocked_state, telefon=telefon, kimin_icin=req.kimin_icin, final_answer=injection_answer)
        bg_tasks.add_task(klinik_karar_kaydet, decision_record)
        bg_tasks.add_task(etkilesim_logla, telefon, "", "CureBot", req.mesaj, injection_answer[:500], None)
        async def injection_stream():
            yield _sse("message", {"chunk": injection_answer})
            yield _sse("governance", {"decision_id": decision_record["decision_id"], "risk_score": decision_record["risk_score"], "confidence_score": decision_record["confidence_score"], "input_guardrail": True})
            yield _sse("done")
        return StreamingResponse(injection_stream(), media_type="text/event-stream")

    simple_answer = _simple_chat_message(req.mesaj, profil_ozeti, gecmis_klinik)
    if simple_answer:
        simple_state = _simple_chat_state(initial_state, simple_answer)
        decision_record = build_decision_record(simple_state, telefon=telefon, kimin_icin=req.kimin_icin, final_answer=simple_answer)
        bg_tasks.add_task(klinik_karar_kaydet, decision_record)
        bg_tasks.add_task(etkilesim_logla, telefon, "", "CureBot", req.mesaj, simple_answer[:500], None)
        async def simple_stream():
            yield _sse("status", {"message": "Yanıt hazırlanıyor"})
            yield _sse("message", {"chunk": simple_answer})
            yield _sse("governance", {"decision_id": decision_record["decision_id"], "risk_score": decision_record["risk_score"], "confidence_score": decision_record["confidence_score"], "fast_path": True})
            yield _sse("done")
        return StreamingResponse(simple_stream(), media_type="text/event-stream")

    source_disclosure = _previous_answer_source_state(initial_state, telefon=telefon, db=db)
    if source_disclosure:
        source_state, source_answer = source_disclosure
        decision_record = build_decision_record(
            source_state,
            telefon=telefon,
            kimin_icin=req.kimin_icin,
            final_answer=source_answer,
        )
        bg_tasks.add_task(klinik_karar_kaydet, decision_record)
        bg_tasks.add_task(etkilesim_logla, telefon, "", "CureBot", req.mesaj, source_answer[:500], None)

        async def source_stream():
            yield _sse("message", {"chunk": source_answer})
            yield _sse(
                "governance",
                {
                    "decision_id": decision_record["decision_id"],
                    "risk_score": decision_record["risk_score"],
                    "confidence_score": decision_record["confidence_score"],
                    "source_disclosure": True,
                },
            )
            yield _sse("done")

        return StreamingResponse(source_stream(), media_type="text/event-stream")
    
    if rails:
        try:
            guard_cevap = await rails.generate_async(messages=[{"role": "user", "content": req.mesaj}])
            icerik = guard_cevap.get("content", "")
            red_mesajlari = ["Siyaset hakkında yorum yapamam", "Yazılım veya kodlama konularında yardımcı olamam", "doktor değilim, tıbbi bir tanı koyamam", "Therapeutic Hallucination Guardrail"]
            if any(r in icerik for r in red_mesajlari):
                blocked_state = _guardrail_block_state(initial_state, icerik)
                decision_record = build_decision_record(blocked_state, telefon=telefon, kimin_icin=req.kimin_icin, final_answer=icerik)
                bg_tasks.add_task(klinik_karar_kaydet, decision_record)
                bg_tasks.add_task(etkilesim_logla, telefon, "", "Guardrails Blok", req.mesaj, icerik[:500], None)
                async def guardrail_stream():
                    yield _sse("governance", {"decision_id": decision_record["decision_id"], "risk_score": decision_record["risk_score"], "confidence_score": decision_record["confidence_score"]})
                    msg_text = f"🛡️ **Sistem Uyarısı (NeMo Guardrails):**\n\n{icerik}"
                    yield f"event: error\ndata: {json.dumps({'message': msg_text})}\n\n"
                return StreamingResponse(guardrail_stream(), media_type="text/event-stream")
        except Exception as e:
            log_failure(logger, "guardrails_request", e, component="chat")

    async def event_generator():
        yield _sse("heartbeat")
        final_state = dict(initial_state)
        try:
            async with asyncio.timeout(75):
                agent_names = {"supervisor_node": "Yönetici", "triyaj_node": "Triyaj Uzmanı", "beslenme_uzmani": "Beslenme Uzmanı", "denetleyici_node": "Tıbbi Denetmen", "sef_node": "Şef"}
                async for event in langgraph_app.astream(initial_state):
                    if await request.is_disconnected():
                        logger.info("Kullanıcı bağlantıyı kopardı (İptal).")
                        break
                    
                    for node_name, state_update in event.items():
                        final_state.update(state_update)
                        if node_name in agent_names:
                            yield _sse("status", {"agent": agent_names[node_name], "status": "tamamlandı"})

            
            final_answer = _final_cevap_metni(final_state, "")
            if not final_answer:
                final_answer = _chat_fallback_message(profil_ozeti, req.mesaj)
            yield _sse("message", {"chunk": final_answer})
                
            decision_record = build_decision_record(final_state, telefon=telefon, kimin_icin=req.kimin_icin, final_answer=final_answer)
            bg_tasks.add_task(klinik_karar_kaydet, decision_record)
            bg_tasks.add_task(etkilesim_logla, telefon, "", "CureBot", req.mesaj, final_answer[:500], None)
            yield _sse("governance", {"decision_id": decision_record["decision_id"], "risk_score": decision_record["risk_score"], "confidence_score": decision_record["confidence_score"]})
            yield _sse("done")
        except Exception as e:
            log_failure(logger, "chat_stream", e, component="chat")
            fallback_answer = _chat_fallback_message(profil_ozeti, req.mesaj)
            fallback_state = _chat_fallback_state(initial_state, fallback_answer, e)
            decision_record = build_decision_record(fallback_state, telefon=telefon, kimin_icin=req.kimin_icin, final_answer=fallback_answer)
            bg_tasks.add_task(klinik_karar_kaydet, decision_record)
            bg_tasks.add_task(etkilesim_logla, telefon, "", "CureBot", req.mesaj, fallback_answer[:500], None)
            yield _sse("message", {"chunk": fallback_answer})
            yield _sse("governance", {"decision_id": decision_record["decision_id"], "risk_score": decision_record["risk_score"], "confidence_score": decision_record["confidence_score"], "fallback": True})
            yield _sse("done")

    return StreamingResponse(event_generator(), media_type="text/event-stream")
