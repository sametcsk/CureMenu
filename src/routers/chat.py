import json
import re
import asyncio
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
from src.memory import hafizadakini_getir
from src.governance.events import apply_event, make_event
from src.graph import app as langgraph_app
from src.nodes import _quality_profile_from_snapshot
from src.quality.policy_engine import PolicyEngine
from src.quality.rule_engine import RuleEngine
from src.logger import get_logger, log_failure
from src.config import settings
from src.profile_context import ResolvedProfileSnapshot, history_matches_snapshot, resolve_profile_snapshot
from src.chat_intents import intent_fast_answer, merge_medications, normalized_message
from src.chat_response import final_response_text, safety_outcome
from src.curebot_intent import (
    CureBotConversationContext,
    CureBotIntentPlan,
    fallback_intent_plan,
    extract_suggestion_topics,
    generate_curebot_natural_answer,
    plan_curebot_semantically,
    plan_requires_safety_gate,
)
from src.presentation import (
    friendly_source_title,
    format_rule_risks_for_user,
)
from src.rate_limit import authenticated_user_or_ip, limiter

logger = get_logger(__name__)
router = APIRouter()


def _infer_chat_target(requested_target: str) -> tuple[str, str]:
    """Resolve conversational target strictly from the explicit API contract."""
    if not requested_target:
        logger.warning("Chat target is missing from request, defaulting to 'kendim'.")
        return "kendim", "Varsayılan (hedef belirtilmemiş)"
    return requested_target, "Seçili hedef kişi"


def _chat_history_metadata(
    snapshot: ResolvedProfileSnapshot,
    plan: CureBotIntentPlan | None = None,
    answer_type: str = "",
    answer_text: str = "",
) -> str:
    metadata = dict(snapshot.history_metadata())
    if plan is not None:
        metadata.update({
            "last_intent": plan.intent,
            "last_meal_context": plan.meal_context,
            "last_answer_type": answer_type or plan.answer_style,
            "last_target_scope": snapshot.target_scope,
            "privacy_mode": "minimal",
        })
    topics = extract_suggestion_topics(answer_text)
    if topics:
        metadata["recent_suggestion_topics"] = list(topics)
    return json.dumps(metadata, ensure_ascii=False)


def _local_conversation_context(logs: list[dict], snapshot: ResolvedProfileSnapshot) -> CureBotConversationContext:
    curebot_logs = [item for item in logs if item.get("sayfa") == "CureBot"]
    previous = curebot_logs[0] if curebot_logs else None
    if previous is None:
        return CureBotConversationContext(last_target_scope=snapshot.target_scope)
    recent_topics: list[str] = []
    seen_topics: set[str] = set()
    for item in curebot_logs[:5]:
        try:
            item_metadata = json.loads(item.get("metadata") or "{}")
        except (TypeError, json.JSONDecodeError):
            item_metadata = {}
        stored_topics = item_metadata.get("recent_suggestion_topics") or ()
        topics = stored_topics if isinstance(stored_topics, list) else ()
        if not topics:
            topics = extract_suggestion_topics(str(item.get("cevap") or ""))
        for topic in topics:
            clean_topic = str(topic or "").strip()
            topic_key = clean_topic.casefold()
            if clean_topic and topic_key not in seen_topics:
                seen_topics.add(topic_key)
                recent_topics.append(clean_topic)
            if len(recent_topics) >= 8:
                break
        if len(recent_topics) >= 8:
            break
    try:
        metadata = json.loads(previous.get("metadata") or "{}")
    except (TypeError, json.JSONDecodeError):
        metadata = {}
    if metadata.get("last_intent"):
        try:
            return CureBotConversationContext(
                last_intent=str(metadata.get("last_intent") or ""),
                last_meal_context=str(metadata.get("last_meal_context") or "unknown"),
                last_answer_type=str(metadata.get("last_answer_type") or ""),
                last_target_scope=str(metadata.get("last_target_scope") or snapshot.target_scope),
                has_previous_turn=True,
                recent_suggestion_topics=tuple(recent_topics),
            )
        except ValueError:
            logger.warning("Invalid local CureBot context labels; rebuilding from the previous local intent.")
    # Legacy records are classified locally once. Their raw text is never
    # included in the provider prompt.
    previous_plan = fallback_intent_plan(
        str(previous.get("istek") or ""),
        snapshot.target_scope,
    )
    return CureBotConversationContext(
        last_intent=previous_plan.intent,
        last_meal_context=previous_plan.meal_context,
        last_answer_type=previous_plan.answer_style,
        last_target_scope=snapshot.target_scope,
        has_previous_turn=True,
        recent_suggestion_topics=tuple(recent_topics),
    )

# NEMO GUARDRAILS
rails = None
if settings.ENABLE_NEMO_GUARDRAILS:
    try:
        from nemoguardrails import LLMRails, RailsConfig
        rails_config = RailsConfig.from_path("config")
        rails = LLMRails(rails_config)
    except Exception as e:
        log_failure(logger, "guardrails_initialize", e, component="chat")


def _sse(event: str, payload: dict | None = None) -> str:
    return f"event: {event}\ndata: {json.dumps(payload or {}, ensure_ascii=False)}\n\n"

def _normalized_message(message: str) -> str:
    return normalized_message(message)

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
    small_talk = {
        "merhaba", "selam", "selamlar", "slm", "mrb", "naber", "nasilsin", "nasilsiniz",
        "iyi misin", "gunaydin", "iyi aksamlar", "ok", "tamam", "tesekkurler",
        "tesekkur ederim", "sag ol", "sagol", "devam", "anladim",
    }
    return text in small_talk or len(text) <= 12 and any(word in text for word in small_talk)


def _small_talk_answer(message: str) -> str | None:
    text = _normalized_message(message)
    if text in {"tesekkurler", "tesekkur ederim", "sag ol", "sagol"}:
        return "Rica ederim. İstersen bir sonraki öğün, menü seçimi ya da alışveriş planı için de yardımcı olabilirim."
    if text in {"ok", "tamam", "devam", "anladim"}:
        return "Tamam. İstersen bir sonraki öğün, menü seçimi ya da alışveriş planı için devam edebiliriz."
    if text in {"merhaba", "selam", "selamlar", "slm", "mrb", "naber", "nasilsin", "nasilsiniz", "iyi misin", "gunaydin", "iyi aksamlar"}:
        return "Merhaba, buradayım. İstersen bugün ne yesem, dışarıda ne seçsem ya da profilime göre nelere dikkat etmeliyim diye birlikte hızlıca bakabiliriz."
    return None
def _is_lab_question(message: str) -> bool:
    text = _normalized_message(message)
    keywords = (
        "tahlil", "kan", "rapor", "kolesterol", "glukoz", "şeker", "seker",
        "hb", "hba1c", "hemoglobin", "ferritin", "b12", "tsh", "kreatinin",
    )
    return any(re.search(rf"(?<!\w){re.escape(keyword)}(?!\w)", text) for keyword in keywords)

def _simple_chat_message(user_message: str, profil_ozeti: str, klinik_hafiza: list[str]) -> str | None:
    small_talk_answer = _small_talk_answer(user_message)
    if small_talk_answer:
        return small_talk_answer
    if _is_lab_question(user_message):
        if klinik_hafiza:
            return "Tahlil notlarını görüyorum. Burada teşhis koyamam ya da tedavi düzenleyemem; ama beslenme açısından daha dikkatli ilerlemene yardım edebilirim.\n\n- Değerlerinde doktorunun özellikle takip dediği bir alan varsa onu yaz, öğün seçimini ona göre daraltalım.\n- Bugün için güvenli yaklaşım: aşırı tuzlu, çok şekerli ve işlenmiş seçeneklerden uzak dur; protein, sebze ve tam tahıl dengesini koru.\n- Yeni belirti, çok yüksek/düşük değer veya ilaç değişikliği varsa doktorunla görüşmeni öneririm."
        return "Henüz kayıtlı bir tahlil dosyası göremiyorum. Tahlillerim alanından PDF yüklediğinde sonraki beslenme önerilerinde bunu dikkate alabilirim. Acil ya da yeni belirti varsa beklemeden doktoruna danışmalısın."
    return None

def _simple_chat_state(initial_state: dict, answer: str) -> dict:
    quality_profile = _quality_profile_from_snapshot(initial_state.get("resolved_profile_snapshot"))
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


def _intent_fast_answer(snapshot: ResolvedProfileSnapshot, message: str) -> str | None:
    return intent_fast_answer(snapshot, message)


def _merge_medications(profile_medications: list[str], message: str) -> tuple[list[str], list[str]]:
    return merge_medications(profile_medications, message)


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
    snapshot: ResolvedProfileSnapshot,
) -> tuple[dict, str] | None:
    if not _is_previous_answer_source_question(initial_state.get("istek", "")):
        return None

    decisions = klinik_kararlari_getir(telefon, limit=20, conn=db)
    matching = next(
        (item for item in decisions if item.get("kimin_icin") == snapshot.target_key),
        None,
    )
    previous = klinik_karar_getir(matching["decision_id"], conn=db) if matching else None
    recorded_citations = list((previous or {}).get("citations") or [])
    verified_citations = [
        citation
        for citation in recorded_citations
        if str(citation.get("source_id") or "").strip()
        and str(citation.get("evidence_span") or "").strip()
    ]

    if verified_citations:
        source_lines = [
            f"- {friendly_source_title(citation.get('title'))}"
            for citation in verified_citations
        ]
        answer = (
            "Önceki yanıt hazırlanırken kullanılan doğrulanabilir kaynaklar:\n"
            + "\n".join(source_lines)
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
    return safety_outcome(result)


def _final_cevap_metni(result: dict, streamed_text: str = "") -> str:
    return final_response_text(result, streamed_text)

def _chat_fallback_message(profil_ozeti: str, user_message: str) -> str:
    request_hint = user_message.strip()[:140] if user_message else "beslenme sorusu"
    profile_hint = "Profilindeki hastalık, alerji ve ilaç bilgilerini dikkate alarak ilerlemem gerekiyor."
    if not profil_ozeti:
        profile_hint = "Sana özel konuşabilmem için profil bilgilerini net görmem gerekiyor."
    return f"Şu an akıllı öneri motoruna bağlanırken bir aksama yaşadım, ama seni yanıtsız bırakmayacağım.\n\n- İsteğin: {request_hint}\n- Güvenlik notum: {profile_hint}\n- Bugün için en güvenli yaklaşım: hafif, az tuzlu, işlenmemiş ve alerji riski taşımayan bir öğün seç; emin olmadığın ilaç-besin eşleşmelerinde doktoruna veya diyetisyenine danış.\n\nBirazdan tekrar denediğinde daha ayrıntılı ve kişisel bir öneri hazırlayabilirim."

def _chat_fallback_state(initial_state: dict, fallback_message: str, error: Exception) -> dict:
    confidence = calculate_confidence(safe=True, evidence_found=False, citations=[])
    fallback_state = apply_event(initial_state, "AIFallbackActivated", "api.chat", status="fallback", metadata={"error_type": type(error).__name__, "message": str(error)[:180]})
    fallback_state.update({
        "hedef_islem": "SOHBET_FALLBACK", "guvenli_mi": True, "uyari_mesaji": "", "tarif_metni": fallback_message,
        "uzman_onerisi": None, "risk_score": confidence["medical_risk"], "confidence": confidence, "citations": []
    })
    return fallback_state


def _explicit_input_safety_answer(snapshot: ResolvedProfileSnapshot, message: str) -> str | None:
    request_parts = []
    for part in re.split(r"[.!?\n]+", message or ""):
        normalized = _normalized_message(part)
        if normalized and not re.search(
            r"\b(?:alerjim|alerjisi|hassasiyetim|direncim|hastaligim|ilacim|ilac kullaniyorum)\b",
            normalized,
        ):
            request_parts.append(part)
    request_text = " ".join(request_parts).strip()
    result = RuleEngine().check_rules(
        snapshot.quality_profile(),
        request_text,
        [request_text],
    )
    risks = list(result.get("found_risks") or [])
    if not risks:
        return None
    risk_lines = "\n".join(f"- {risk}" for risk in format_rule_risks_for_user(risks))
    return (
        "Bu seçeneği mevcut haliyle önermiyorum. Profilinizle şu açık çakışmalar bulundu:\n"
        f"{risk_lines}\n\n"
        "Bu malzemeleri kullanmadan hazırlanmış bir alternatif seçin. İsterseniz aynı öğünün kayıtlı "
        "alerjenleri içermeyen bir alternatifini önerebilirim."
    )

@router.post("/api/chat")
@limiter.limit("12/minute", key_func=authenticated_user_or_ip)
async def chat(request: Request, req: ChatRequest, bg_tasks: BackgroundTasks, telefon: str = Depends(get_current_user), db: sqlite3.Connection = Depends(get_db)):
    resolved_target, context_reason = _infer_chat_target(req.kimin_icin)
    snapshot = resolve_profile_snapshot(telefon, resolved_target, db=db)
    profil_ozeti = snapshot.profile_summary
    kullanici_id = snapshot.memory_namespace
    history_metadata = _chat_history_metadata(snapshot)
    ilaclar, message_medications = _merge_medications(
        list(snapshot.medications),
        req.mesaj,
    )
    
    if kullanici_id is None:
        raise HTTPException(status_code=400, detail=PROFIL_GEREKLI)
    
    gecmis_yemek = await run_in_threadpool(hafizadakini_getir, kullanici_id, "yemek", 3)
    gecmis_klinik = await run_in_threadpool(hafizadakini_getir, kullanici_id, "SAĞLIK RAPORU TAHLİL KAN", 2)
    
    gecmis = gecmis_yemek + gecmis_klinik
    
    son_loglar = [
        item
        for item in loglari_getir_db(telefon, limit=50, conn=db)
        if history_matches_snapshot(item, snapshot)
    ][:10]
    conversation_context = _local_conversation_context(son_loglar, snapshot)
    sohbet_gecmisi = []
    for log in reversed(son_loglar):
        sayfa = log.get("sayfa", "Sistem")
        istek = log["istek"]
        if sayfa != "CureBot":
            istek = f"[{sayfa} İşlemi Gerçekleştirildi]: {istek}"
            
        sohbet_gecmisi.append({"role": "user", "content": istek})
        sohbet_gecmisi.append({"role": "assistant", "content": log["cevap"]})
    
    initial_state = create_initial_state(
        istek=req.mesaj,
        profil_ozeti=profil_ozeti,
        hafiza=gecmis,
        sohbet_gecmisi=sohbet_gecmisi,
        ilaclar=ilaclar,
        resolved_profile_snapshot=snapshot.state_payload(),
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
        decision_record = build_decision_record(blocked_state, telefon=telefon, kimin_icin=snapshot.target_key, final_answer=injection_answer)
        bg_tasks.add_task(klinik_karar_kaydet, decision_record)
        bg_tasks.add_task(etkilesim_logla, telefon, snapshot.target_name, "CureBot", req.mesaj, injection_answer[:500], history_metadata)
        async def injection_stream():
            yield _sse("message", {"chunk": injection_answer})
            yield _sse("governance", {"decision_id": decision_record["decision_id"], "risk_score": decision_record["risk_score"], "confidence_score": decision_record["confidence_score"], "input_guardrail": True})
            yield _sse("done")
        return StreamingResponse(injection_stream(), media_type="text/event-stream")

    # Everyday conversation must be resolved before generic input/rule safety.
    # Risky food questions return None here and continue to the explicit safety gate below.
    intent_answer = None
    if intent_answer:
        intent_state = _simple_chat_state(initial_state, intent_answer)
        decision_record = build_decision_record(intent_state, telefon=telefon, kimin_icin=snapshot.target_key, final_answer=intent_answer)
        bg_tasks.add_task(klinik_karar_kaydet, decision_record)
        bg_tasks.add_task(etkilesim_logla, telefon, snapshot.target_name, "CureBot", req.mesaj, intent_answer[:500], history_metadata)

        async def intent_stream_precheck():
            yield _sse("status", {"status": "Yanıt hazırlanıyor..."})
            yield _sse("message", {"chunk": intent_answer})
            yield _sse("governance", {"decision_id": decision_record["decision_id"], "risk_score": decision_record["risk_score"], "confidence_score": decision_record["confidence_score"], "fast_path": True})
            yield _sse("done")

        return StreamingResponse(intent_stream_precheck(), media_type="text/event-stream")

    try:
        intent_plan = await asyncio.wait_for(
            run_in_threadpool(
                plan_curebot_semantically,
                req.mesaj,
                conversation_context.model_dump(),
                snapshot.target_scope,
                [snapshot.target_name],
                {
                    "allergy_present": bool(snapshot.allergies),
                    "medication_present": bool(snapshot.medications),
                    "disease_present": bool(snapshot.diseases),
                },
            ),
            timeout=8,
        )
    except Exception:
        intent_plan = fallback_intent_plan(req.mesaj, req.kimin_icin, conversation_context)

    history_metadata = _chat_history_metadata(snapshot, intent_plan)
        
    if intent_plan.intent == "off_topic":
        off_topic_answer = "Ben beslenme ve sağlık odaklı bir asistanım. Lütfen CureMenu'nün temel amacı olan bu konularda sorular sorun."
        off_topic_state = _simple_chat_state(initial_state, off_topic_answer)
        decision_record = build_decision_record(off_topic_state, telefon=telefon, kimin_icin=snapshot.target_key, final_answer=off_topic_answer)
        bg_tasks.add_task(klinik_karar_kaydet, decision_record)
        bg_tasks.add_task(etkilesim_logla, telefon, snapshot.target_name, "CureBot", req.mesaj, off_topic_answer[:500], history_metadata)
        
        async def off_topic_stream():
            yield _sse("message", {"chunk": off_topic_answer})
            yield _sse("governance", {"decision_id": decision_record["decision_id"], "risk_score": decision_record["risk_score"], "confidence_score": decision_record["confidence_score"], "fast_path": True})
            yield _sse("done")
        return StreamingResponse(off_topic_stream(), media_type="text/event-stream")

    input_safety_answer = _explicit_input_safety_answer(snapshot, req.mesaj)
    if not input_safety_answer and intent_plan.intent in {
        "meal_recommendation", "meal_followup", "dessert_craving", "coffee_habit",
        "explanation_followup", "emotional_support", "product_question",
    } and not plan_requires_safety_gate(intent_plan):
        if normalized_message(req.mesaj).strip() in {"öner", "oner", "alternatif", "başka", "baska", "detay", "tarif"} and not sohbet_gecmisi:
            natural_answer = "Neye alternatif istediğini tam çıkaramadım. İstersen tatlı, kahvaltı ya da akşam yemeği olarak uyarlayabilirim."
        else:
            natural_answer = None
        try:
            if natural_answer is None:
                natural_answer = await asyncio.wait_for(
                    run_in_threadpool(
                        generate_curebot_natural_answer,
                        intent_plan,
                        snapshot,
                        req.mesaj,
                        "Önceki konuşma bağlamı yerel etiketlerle mevcut." if conversation_context.has_previous_turn else "",
                        conversation_context,
                    ),
                    timeout=12,
                )
        except Exception:
            natural_answer = "İsteğini anladım. Profiline uygun birkaç pratik seçenek düşünebiliriz; istersen neyi özellikle sevdiğini söyle."
        if natural_answer:
            natural_state = _simple_chat_state(initial_state, natural_answer)
            decision_record = build_decision_record(natural_state, telefon=telefon, kimin_icin=snapshot.target_key, final_answer=natural_answer)
            bg_tasks.add_task(klinik_karar_kaydet, decision_record)
            natural_history_metadata = _chat_history_metadata(
                snapshot,
                intent_plan,
                answer_text=natural_answer,
            )
            bg_tasks.add_task(etkilesim_logla, telefon, snapshot.target_name, "CureBot", req.mesaj, natural_answer[:500], natural_history_metadata)

            async def natural_stream():
                yield _sse("message", {"chunk": natural_answer})
                yield _sse("governance", {"decision_id": decision_record["decision_id"], "risk_score": decision_record["risk_score"], "confidence_score": decision_record["confidence_score"], "fast_path": True})
                yield _sse("done")

            return StreamingResponse(natural_stream(), media_type="text/event-stream")
    if input_safety_answer:
        blocked_state = _guardrail_block_state(initial_state, input_safety_answer)
        decision_record = build_decision_record(
            blocked_state,
            telefon=telefon,
            kimin_icin=snapshot.target_key,
            final_answer=input_safety_answer,
        )
        bg_tasks.add_task(klinik_karar_kaydet, decision_record)
        bg_tasks.add_task(etkilesim_logla, telefon, snapshot.target_name, "CureBot", req.mesaj, input_safety_answer[:500], history_metadata)

        async def input_safety_stream():
            yield _sse("message", {"chunk": input_safety_answer})
            yield _sse(
                "governance",
                {
                    "decision_id": decision_record["decision_id"],
                    "risk_score": decision_record["risk_score"],
                    "confidence_score": decision_record["confidence_score"],
                    "input_safety": True,
                },
            )
            yield _sse("done")

        return StreamingResponse(input_safety_stream(), media_type="text/event-stream")

    intent_answer = _intent_fast_answer(snapshot, req.mesaj)
    if intent_answer:
        intent_state = _simple_chat_state(initial_state, intent_answer)
        decision_record = build_decision_record(intent_state, telefon=telefon, kimin_icin=snapshot.target_key, final_answer=intent_answer)
        bg_tasks.add_task(klinik_karar_kaydet, decision_record)
        bg_tasks.add_task(etkilesim_logla, telefon, snapshot.target_name, "CureBot", req.mesaj, intent_answer[:500], history_metadata)

        async def intent_stream():
            yield _sse("status", {"status": "Yanıt hazırlanıyor..."})
            yield _sse("message", {"chunk": intent_answer})
            yield _sse("governance", {"decision_id": decision_record["decision_id"], "risk_score": decision_record["risk_score"], "confidence_score": decision_record["confidence_score"], "fast_path": True})
            yield _sse("done")

        return StreamingResponse(intent_stream(), media_type="text/event-stream")

    simple_answer = _simple_chat_message(req.mesaj, profil_ozeti, gecmis_klinik)
    if simple_answer:
        simple_state = _simple_chat_state(initial_state, simple_answer)
        decision_record = build_decision_record(simple_state, telefon=telefon, kimin_icin=snapshot.target_key, final_answer=simple_answer)
        bg_tasks.add_task(klinik_karar_kaydet, decision_record)
        bg_tasks.add_task(etkilesim_logla, telefon, snapshot.target_name, "CureBot", req.mesaj, simple_answer[:500], history_metadata)
        async def simple_stream():
            yield _sse("status", {"status": "Yanıt hazırlanıyor..."})
            yield _sse("message", {"chunk": simple_answer})
            yield _sse("governance", {"decision_id": decision_record["decision_id"], "risk_score": decision_record["risk_score"], "confidence_score": decision_record["confidence_score"], "fast_path": True})
            yield _sse("done")
        return StreamingResponse(simple_stream(), media_type="text/event-stream")

    source_disclosure = _previous_answer_source_state(initial_state, telefon=telefon, db=db, snapshot=snapshot)
    if source_disclosure:
        source_state, source_answer = source_disclosure
        decision_record = build_decision_record(
            source_state,
            telefon=telefon,
            kimin_icin=snapshot.target_key,
            final_answer=source_answer,
        )
        bg_tasks.add_task(klinik_karar_kaydet, decision_record)
        bg_tasks.add_task(etkilesim_logla, telefon, snapshot.target_name, "CureBot", req.mesaj, source_answer[:500], history_metadata)

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
                decision_record = build_decision_record(blocked_state, telefon=telefon, kimin_icin=snapshot.target_key, final_answer=icerik)
                bg_tasks.add_task(klinik_karar_kaydet, decision_record)
                bg_tasks.add_task(etkilesim_logla, telefon, snapshot.target_name, "Guardrails Blok", req.mesaj, icerik[:500], history_metadata)
                async def guardrail_stream():
                    yield _sse("governance", {"decision_id": decision_record["decision_id"], "risk_score": decision_record["risk_score"], "confidence_score": decision_record["confidence_score"]})
                    msg_text = f"🛡️ **Sistem Uyarısı (NeMo Guardrails):**\n\n{icerik}"
                    yield f"event: error\ndata: {json.dumps({'message': msg_text})}\n\n"
                return StreamingResponse(guardrail_stream(), media_type="text/event-stream")
        except Exception as e:
            log_failure(logger, "guardrails_request", e, component="chat")

    async def event_generator():
        yield _sse("status", {"status": "Profil bilgilerin kontrol ediliyor..."})
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
                
            decision_record = build_decision_record(final_state, telefon=telefon, kimin_icin=snapshot.target_key, final_answer=final_answer)
            bg_tasks.add_task(klinik_karar_kaydet, decision_record)
            final_history_metadata = _chat_history_metadata(
                snapshot,
                intent_plan,
                answer_text=final_answer,
            )
            bg_tasks.add_task(etkilesim_logla, telefon, snapshot.target_name, "CureBot", req.mesaj, final_answer[:500], final_history_metadata)
            yield _sse("governance", {"decision_id": decision_record["decision_id"], "risk_score": decision_record["risk_score"], "confidence_score": decision_record["confidence_score"]})
            yield _sse("done")
        except Exception as e:
            log_failure(logger, "chat_stream", e, component="chat")
            fallback_answer = _chat_fallback_message(profil_ozeti, req.mesaj)
            fallback_state = _chat_fallback_state(initial_state, fallback_answer, e)
            decision_record = build_decision_record(fallback_state, telefon=telefon, kimin_icin=snapshot.target_key, final_answer=fallback_answer)
            bg_tasks.add_task(klinik_karar_kaydet, decision_record)
            bg_tasks.add_task(etkilesim_logla, telefon, snapshot.target_name, "CureBot", req.mesaj, fallback_answer[:500], history_metadata)
            yield _sse("message", {"chunk": fallback_answer})
            yield _sse("governance", {"decision_id": decision_record["decision_id"], "risk_score": decision_record["risk_score"], "confidence_score": decision_record["confidence_score"], "fallback": True})
            yield _sse("done")

    return StreamingResponse(event_generator(), media_type="text/event-stream")
