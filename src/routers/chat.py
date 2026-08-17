import json
import re
import asyncio
from fastapi import APIRouter, Request, Depends, BackgroundTasks, HTTPException
from fastapi.responses import StreamingResponse
from fastapi.concurrency import run_in_threadpool
import sqlite3
from dataclasses import dataclass

from src.models import ChatRequest
from src.database import (
    get_db,
    etkilesim_logla,
    klinik_karar_getir,
    klinik_karar_kaydet,
    klinik_kararlari_getir,
    loglari_getir_db,
    son_sayfa_kayitlari,
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
from src.quality.evidence import (
    SafetyFinding,
    carry_findings_without_new_evidence,
    coerce_finding,
    render_finding,
)
from src.logger import get_logger, log_failure
from src.config import settings
from src.profile_context import ResolvedProfileSnapshot, history_matches_snapshot, resolve_profile_snapshot, resolve_target_snapshot
from src.target_resolution import TargetResolution, clarification_prompt
from src.chat_intents import intent_fast_answer, merge_medications, normalized_message
from src.chat_response import final_response_text, safety_outcome
from src.curebot_intent import (
    CureBotConversationContext,
    CureBotIntentPlan,
    ResolvedTurn,
    fallback_intent_plan,
    extract_suggestion_topics,
    generate_curebot_natural_answer,
    natural_fallback_answer,
    plan_curebot_semantically,
    plan_requires_safety_gate,
    resolve_semantic_turn,
    semantic_continuity_labels,
    soften_unsourced_clinical_limits,
)
from src.presentation import (
    friendly_source_title,
)
from src.rate_limit import authenticated_user_or_ip, limiter

logger = get_logger(__name__)
router = APIRouter()
CHAT_HISTORY_RESPONSE_LIMIT = 3000


@dataclass(frozen=True)
class CureBotResponseContext:
    """Canonical, already-resolved input consumed by response composers."""

    turn: ResolvedTurn
    snapshot: ResolvedProfileSnapshot | None
    plan: CureBotIntentPlan | None
    conversation: CureBotConversationContext
    user_message: str
    findings: tuple[SafetyFinding, ...] = ()

    @property
    def object_dependent(self) -> bool:
        return self.turn.intent in {
            "allergy_conflict", "food_suitability", "medication_food_question",
            "meal_followup", "menu_followup", "weekly_plan_followup",
        }

    @property
    def response_input(self) -> str:
        if self.object_dependent and self.turn.object_label.strip():
            return self.turn.object_label.strip()
        return self.user_message


@dataclass(frozen=True)
class ResponseDecision:
    answer: str
    findings: tuple[SafetyFinding, ...] = ()


@dataclass(frozen=True)
class ArtifactRecallResult:
    answer: str
    artifact_reference: str
    findings: tuple[SafetyFinding, ...] = ()


def _history_response_text(value: str) -> str:
    return str(value or "")[:CHAT_HISTORY_RESPONSE_LIMIT]


def _infer_chat_target(requested_target: str) -> tuple[str, str]:
    """Resolve conversational target strictly from the explicit API contract."""
    if not requested_target:
        logger.warning("Chat target is missing from request, defaulting to 'kendim'.")
        return "kendim", "Varsayılan (hedef belirtilmemiş)"
    return requested_target, "Seçili hedef kişi"


def _log_metadata(item: dict) -> dict:
    try:
        value = item.get("metadata") or "{}"
        return json.loads(value) if isinstance(value, str) else dict(value)
    except (TypeError, ValueError, json.JSONDecodeError):
        return {}


def _conversation_curebot_logs(logs: list[dict], conversation_id: str | None) -> list[dict]:
    """Return CureBot turns belonging to one household conversation.

    Legacy API clients do not send a conversation id; for those clients the
    historical account-wide behavior is retained. Once a conversation id is
    supplied, turns from another browser conversation can never influence target
    continuity or local intent labels.
    """
    curebot_logs = [item for item in logs if item.get("sayfa") == "CureBot"]
    if not conversation_id:
        return curebot_logs
    return [
        item for item in curebot_logs
        if str(_log_metadata(item).get("conversation_id") or "") == conversation_id
    ]


def _previous_curebot_target(logs: list[dict]) -> str | None:
    """Most recent CureBot turn's resolved target, for follow-up continuity.

    Read from the persisted interaction log (backend conversation state), not a
    frontend variable. Clarification/legacy turns carry no target and are skipped.
    """
    for item in logs:  # loglari_getir_db returns newest-first
        if item.get("sayfa") != "CureBot":
            continue
        metadata = _log_metadata(item)
        scope = str(metadata.get("target_scope") or "").strip()
        target_id = str(metadata.get("target_id") or "").strip()
        if not scope or not target_id:
            continue
        if scope == "self":
            return "kendim"
        if scope == "family":
            return "aile"
        return target_id
    return None


def _chat_history_metadata(
    snapshot: ResolvedProfileSnapshot | None,
    plan: CureBotIntentPlan | None = None,
    answer_type: str = "",
    answer_text: str = "",
    conversation_id: str | None = None,
    target_resolution: TargetResolution | None = None,
    user_message: str = "",
    previous_context: CureBotConversationContext | dict | None = None,
    artifact_reference: str = "",
    resolved_turn: ResolvedTurn | None = None,
    response_path: str = "unknown",
    findings: tuple[SafetyFinding, ...] = (),
) -> str:
    metadata = dict(snapshot.history_metadata())
    if conversation_id:
        metadata["conversation_id"] = conversation_id
    if target_resolution is not None:
        metadata.update({
            "target_resolution_source": target_resolution.source,
            "target_explicit": target_resolution.source.startswith("message_"),
            "target_inherited": target_resolution.source in {"continuity", "pronoun"},
        })
    if resolved_turn is not None:
        metadata.update(resolved_turn.metadata(response_path=response_path))
        if plan is not None:
            metadata["last_meal_context"] = plan.meal_context
            metadata["last_answer_type"] = answer_type or plan.answer_style
    elif plan is not None:
        continuity = semantic_continuity_labels(plan, user_message, previous_context)
        metadata.update({
            "last_intent": plan.intent,
            "last_meal_context": plan.meal_context,
            **continuity,
            "last_answer_type": answer_type or plan.answer_style,
            "last_target_scope": snapshot.target_scope,
            "privacy_mode": "minimal",
        })
    elif artifact_reference in {"weekly_plan", "menu_analysis", "lab_analysis", "fridge_analysis"}:
        metadata.update({
            "last_intent": "menu_followup" if artifact_reference == "menu_analysis" else "unknown_nutrition_related",
            "last_meal_context": "unknown",
            "last_subject": "artifact",
            "last_object": "",
            "last_object_type": "unknown",
            "last_artifact_reference": artifact_reference,
            "last_answer_type": answer_type or "explanatory",
            "last_target_scope": snapshot.target_scope,
            "privacy_mode": "minimal",
        })
    topics = extract_suggestion_topics(answer_text)
    if topics:
        metadata["recent_suggestion_topics"] = list(topics)
    if findings:
        metadata["structured_findings"] = [finding.persisted() for finding in findings]
    metadata.update({
        "resolved_object_present": bool(resolved_turn and resolved_turn.object_label),
        "responder_received_object": bool(resolved_turn and resolved_turn.object_label),
        "finding_count": len(findings),
        "evidence_levels": sorted({finding.evidence_level for finding in findings}),
        "evidence_upgraded": any(
            bool(finding.provenance.get("evidence_upgrade_reason"))
            for finding in findings
        ),
        "upgrade_source_present": all(
            bool(finding.evidence_source)
            for finding in findings
            if finding.provenance.get("evidence_upgrade_reason")
        ),
        "artifact_reference_present": bool(
            resolved_turn and resolved_turn.artifact_reference != "none"
        ),
    })
    return json.dumps(metadata, ensure_ascii=False)


def _schedule_turn_commit(
    bg_tasks: BackgroundTasks,
    *,
    telefon: str,
    snapshot: ResolvedProfileSnapshot,
    user_message: str,
    answer_text: str,
    turn: ResolvedTurn,
    response_path: str,
    plan: CureBotIntentPlan | None = None,
    findings: tuple[SafetyFinding, ...] = (),
) -> str:
    """The single semantic-state commit point for every resolved response path."""
    if snapshot is None:
        unresolved_metadata = turn.metadata(response_path=response_path)
        unresolved_metadata["last_answer_type"] = "clarification"
        metadata = json.dumps(unresolved_metadata, ensure_ascii=False)
    else:
        metadata = _chat_history_metadata(
            snapshot,
            plan,
            answer_text=answer_text,
            conversation_id=turn.conversation_id,
            user_message=user_message,
            resolved_turn=turn,
            response_path=response_path,
            findings=findings,
        )
    bg_tasks.add_task(
        etkilesim_logla,
        telefon,
        snapshot.target_name if snapshot is not None else "",
        "CureBot",
        user_message,
        _history_response_text(answer_text),
        metadata,
    )
    logger.info(
        "event=curebot_turn_committed conversation_id=%s response_path=%s target_source=%s "
        "object_changed=%s state_committed=true",
        turn.conversation_id or "legacy",
        response_path,
        turn.target_resolution_source,
        turn.object_changed,
    )
    return metadata


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
                last_subject=str(metadata.get("last_subject") or "unknown"),
                last_object=str(metadata.get("last_object") or ""),
                last_object_type=str(metadata.get("last_object_type") or "unknown"),
                last_artifact_reference=str(metadata.get("last_artifact_reference") or "none"),
                last_answer_type=str(metadata.get("last_answer_type") or ""),
                last_target_scope=str(metadata.get("last_target_scope") or snapshot.target_scope),
                has_previous_turn=True,
                recent_suggestion_topics=tuple(recent_topics),
                structured_findings=tuple(
                    item for item in (metadata.get("structured_findings") or [])
                    if isinstance(item, dict)
                ),
            )
        except ValueError:
            logger.warning("Invalid local CureBot context labels; rebuilding from the previous local intent.")
    # Legacy records are classified locally once. Their raw text is never
    # included in the provider prompt.
    previous_plan = fallback_intent_plan(
        str(previous.get("istek") or ""),
        snapshot.target_scope,
    )
    continuity = semantic_continuity_labels(previous_plan, str(previous.get("istek") or ""))
    return CureBotConversationContext(
        last_intent=previous_plan.intent,
        last_meal_context=previous_plan.meal_context,
        **continuity,
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


def _chat_stream_response(
    stream,
    snapshot: ResolvedProfileSnapshot | None = None,
    resolution: TargetResolution | None = None,
) -> StreamingResponse:
    headers: dict[str, str] = {}
    if snapshot is not None:
        # Header values must be latin-1 safe; the target key/scope are ASCII. The
        # human label (which may contain Turkish characters and member names) is
        # built on the client from currentProfile, never sent in a header.
        headers["X-CureMenu-Resolved-Target"] = str(snapshot.target_key)
        headers["X-CureMenu-Target-Scope"] = str(snapshot.target_scope)
    if resolution is not None:
        headers["X-CureMenu-Resolution-Source"] = str(resolution.source)
    return StreamingResponse(stream, media_type="text/event-stream", headers=headers)

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

_CONFLICT_NEGATION_TOKENS = {
    "yok", "yokmus", "degil", "degilim", "kalmadi", "gecti", "gecmis",
    "olmadigini", "olmadigi", "olmadi", "olmuyor",
}
_CONFLICT_NEGATION_PREFIXES = ("birak", "olmad", "yanlis", "kaldir", "cikar", "eklemis")


def _conflict_notice(subject: str) -> str:
    return (
        f"Profilinde {subject} kayıtlı görünüyor. Güvenlik açısından, bu bilgi "
        "profil sayfandan güncellenene kadar önerilerde dikkate almaya devam edeceğim. "
        "Artık geçerli değilse ya da yanlış eklendiyse lütfen profilinden güncelle; "
        "ona göre değerlendireyim."
    )


def _profile_conflict_answer(snapshot: ResolvedProfileSnapshot | None, message: str) -> str | None:
    """When the message denies / disowns a *registered* allergy or disease, do not
    silently drop it. The structured profile stays source-of-truth; direct the user
    to update it from the profile page instead of overriding critical health data
    in chat. Covers "... yok", "artık ... olmadığını söyledi", "yanlışlıkla
    eklemişim", and short terms like "süt".
    """
    if snapshot is None:
        return None
    text = _normalized_message(message)
    tokens = text.split()
    has_negation = any(token in _CONFLICT_NEGATION_TOKENS for token in tokens) or any(
        token.startswith(prefix) for token in tokens for prefix in _CONFLICT_NEGATION_PREFIXES
    )
    if not has_negation:
        return None
    for term in (*snapshot.allergies, *snapshot.diseases):
        term_norm = _normalized_message(term)
        for word in term_norm.split():
            if len(word) < 3:
                continue
            if word in tokens or (len(word) >= 5 and word[:5] in text):
                return _conflict_notice(f"“{term}”")
    # Generic denial ("alerjim yok", "artık hastalığım olmadığını söyledi") while
    # some allergy/disease is on file, without naming the specific one.
    if snapshot.allergies and any(token.startswith("alerj") for token in tokens):
        return _conflict_notice("kayıtlı bir alerji")
    if snapshot.diseases and any(token.startswith("hastal") for token in tokens):
        return _conflict_notice("kayıtlı bir sağlık durumu")
    return None


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


def _intent_fast_answer(context: CureBotResponseContext) -> str | None:
    if context.snapshot is None:
        return None
    return intent_fast_answer(context.snapshot, context.response_input)


def _merge_medications(profile_medications: list[str], message: str) -> tuple[list[str], list[str]]:
    return merge_medications(profile_medications, message)


def _is_previous_answer_source_question(message: str) -> bool:
    text = _normalized_message(message)
    refers_to_previous = any(
        phrase in text
        for phrase in ("bu cevap", "bu cevab", "bu yanit", "onceki cevap", "onceki cevab", "onceki yanit")
    )
    has_source_cue = any(word in text for word in ("kaynak", "kayna", "kanit", "dayanak", "dayanag", "referans"))
    direct_source_request = any(
        phrase in text
        for phrase in (
            "kaynak goster", "kaynak belirt", "kaynak nedir", "kaynaklar neler",
            "kanit nerede", "kaniti nedir", "dayanagi nedir", "referans goster",
        )
    )
    return has_source_cue and (refers_to_previous or direct_source_request)


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


def _explicit_input_safety_answer(context: CureBotResponseContext) -> ResponseDecision | None:
    if context.snapshot is None:
        return None
    # Hard conflict is reserved for a concrete food the user actually supplies to
    # evaluate this turn: either an explicit suitability question ("... uygun
    # mu?") or a concrete food named in the current message. A generic
    # recommendation ("ne önerirsin?") — even one that only inherits a prior food
    # object through follow-up continuity — must not produce a hard conflict;
    # downstream the profile restrictions become a candidate-generation filter
    # (the natural path avoids them and the output safety gate still runs).
    plan = context.plan
    explicit_suitability = bool(
        plan and (plan.needs_safety_gate or plan.risk_subject == "explicit_food_request")
    )
    supplied_food_this_turn = (
        context.turn.object_resolution_source == "current_message"
        and context.turn.object_type == "food"
        and bool(context.turn.object_label.strip())
    )
    if not (explicit_suitability or supplied_food_this_turn):
        return None
    message = context.response_input
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
        context.snapshot.quality_profile(),
        request_text,
        [request_text],
    )
    findings = tuple(
        coerce_finding(item, target_profile_id=context.snapshot.target_key).model_copy(update={
            "inherited_from_previous_turn": context.turn.object_resolution_source == "previous_turn",
            "new_evidence_this_turn": bool(
                context.turn.object_resolution_source == "current_message"
                and item.get("matched_ingredient")
            ),
            "originating_turn_id": context.turn.turn_id,
            "provenance": {
                "object_resolution_source": (
                    context.turn.object_resolution_source
                ),
                "target_resolution_source": context.turn.target_resolution_source,
            },
        })
        for item in (result.get("evidence_findings") or [])
    )
    confirmed = tuple(item for item in findings if item.evidence_level == "CONFIRMED")
    if not confirmed:
        return None
    risk_lines = "\n".join(f"- {render_finding(finding)}" for finding in confirmed)
    answer = (
        "Bu seçeneği mevcut haliyle önermiyorum. Profilinizle şu açık çakışmalar bulundu:\n"
        f"{risk_lines}\n\n"
        "Bu malzemeleri kullanmadan hazırlanmış bir alternatif seçin. İsterseniz aynı öğünün kayıtlı "
        "alerjenleri içermeyen bir alternatifini önerebilirim."
    )
    return ResponseDecision(answer=answer, findings=findings)

def _is_weekly_plan_recall(text: str) -> bool:
    return any(cue in text for cue in (
        "planim", "planinda", "planimda", "hazirladigin plan",
        "bu haftaki plan", "haftalik planim", "haftalik planinda", "haftaki planim",
    ))


def _is_menu_recall(text: str) -> bool:
    if "menu" not in text:
        return False
    return any(cue in text for cue in ("gecen", "onceki", "gecmis", "daha once", "ana risk", "hangi risk", "neydi"))


def _is_generic_clinical_notice(value: str) -> bool:
    text = _normalized_message(value)
    return any(cue in text for cue in (
        "doktor", "diyetisyen", "eczaci", "saglik profesyoneli",
        "uzmaniniza", "uzmana danis", "yerine gecmez", "genel bilgilendirme",
    ))


def _is_weekly_plan_ingredient_recall(text: str) -> bool:
    return _is_weekly_plan_recall(text) and any(
        cue in text for cue in ("malzeme", "icerik", "neler vardi", "ne vardi")
    )


def _weekly_plan_recall_answer(
    log: dict,
    snapshot: ResolvedProfileSnapshot,
    *,
    wants_ingredients: bool = False,
) -> str:
    label = snapshot.target_name or "Bu profil"
    metadata = _log_metadata(log)
    if wants_ingredients:
        normalized_ingredients = [
            str(item).strip()
            for item in (metadata.get("normalized_ingredients") or [])
            if str(item).strip()
        ]
        if normalized_ingredients:
            bullets = "\n".join(f"- {item}" for item in normalized_ingredients[:30])
            return f"{label} için kayıtlı haftalık plandaki standartlaştırılmış malzemeler:\n{bullets}"
        return (
            f"{label} için kayıtlı plan eski formatta olduğu için doğrulanmış standart malzeme listesine "
            "erişemiyorum. Ham plan metnini güvenlik bulgusu gibi yeniden yorumlamıyorum."
        )
    try:
        plan = json.loads(log.get("cevap") or "{}")
    except (TypeError, json.JSONDecodeError):
        plan = {}
    warnings = [
        str(w).strip()
        for w in (plan.get("warnings") or [])
        if str(w).strip() and not _is_generic_clinical_notice(str(w))
    ] if isinstance(plan, dict) else []
    considerations = [
        str(item).strip()
        for item in (metadata.get("health_considerations") or [])
        if str(item).strip()
    ]
    compat = (plan.get("compatibility") or {}) if isinstance(plan, dict) else {}
    if not compat and isinstance(metadata.get("compatibility"), dict):
        compat = metadata["compatibility"]
    compat_msg = str(compat.get("message") or "").strip()
    if considerations:
        bullets = "\n".join(f"- {item}" for item in considerations[:8])
        return (
            f"{label} için bu haftaki plan oluşturulurken kayda geçen sağlık ve güvenlik bağlamı:\n"
            f"{bullets}"
        )
    if warnings:
        bullets = "\n".join(f"- {item}" for item in warnings[:6])
        return f"{label} için bu haftaki planında özellikle şu noktalara dikkat edildi:\n{bullets}"
    if compat_msg and not _is_generic_clinical_notice(compat_msg):
        return f"{label} için bu haftaki planında öne çıkan not: {compat_msg}"
    return (
        f"{label} için kayıtlı bir haftalık plan var ama içinde ayrı bir uyarı notu bulamadım. "
        "Planı Haftalık Plan ekranından açıp ayrıntılarını görebilirsin."
    )


def _artifact_evidence_findings(
    metadata: dict,
    snapshot: ResolvedProfileSnapshot,
    artifact_reference: str,
) -> tuple[SafetyFinding, ...]:
    findings: list[SafetyFinding] = []
    for item in (metadata.get("evidence_findings") or []):
        if not isinstance(item, dict):
            continue
        finding = coerce_finding(
            item,
            target_profile_id=snapshot.target_key,
            artifact_reference=artifact_reference,
        )
        if finding.target_profile_id != snapshot.target_key:
            logger.warning(
                "event=artifact_finding_scope_rejected artifact=%s target_mismatch=true",
                artifact_reference,
            )
            continue
        findings.append(finding)
    return tuple(findings)


def _menu_recall_answer(log: dict, snapshot: ResolvedProfileSnapshot) -> ResponseDecision:
    label = snapshot.target_name or "Bu profil"
    metadata = _log_metadata(log)
    findings = _artifact_evidence_findings(metadata, snapshot, "menu_analysis")
    relevant = tuple(item for item in findings if item.evidence_level != "CLEAR")
    if relevant:
        bullets = "\n".join(f"- {render_finding(item)}" for item in relevant[:6])
        return ResponseDecision(
            answer=f"{label} için geçen menü analizindeki yapılandırılmış bulgular:\n{bullets}",
            findings=findings,
        )
    if metadata.get("detected_risks") or metadata.get("analysis_findings"):
        return ResponseDecision(
            answer=(
                f"{label} için bu eski menü kaydında risk notları var, ancak kanıt düzeyi yapılandırılmış "
                "olarak saklanmamış. Bu nedenle notları kesin eşleşme gibi aktarmıyorum; menüyü yeniden "
                "açarak içeriği doğrulayabilirsin."
            ),
        )
    return ResponseDecision(answer=(
        f"{label} için bu menü analizi kaydında spesifik bir risk bulgusu yapılandırılmış olarak saklanmamış. "
        "Genel güvenlik notlarını geçmiş analiz bulgusu gibi aktarmıyorum; menüyü Menü Analizi ekranından tekrar açabilirsin."
    ))


def _artifact_missing_answer(wants_plan: bool, snapshot: ResolvedProfileSnapshot) -> str:
    label = snapshot.target_name or "Bu profil"
    if wants_plan:
        return (
            f"{label} için güncel bir haftalık plana şu anda erişemiyorum. "
            "Haftalık Plan ekranından yeni bir plan oluşturabilirsin."
        )
    return (
        f"{label} için önceki bir menü analizine şu anda erişemiyorum. "
        "Menü Analizi ekranından menüyü tekrar yükleyip analiz edebilirsin."
    )


def _artifact_recall_answer(
    snapshot: ResolvedProfileSnapshot,
    message: str,
    *,
    db: sqlite3.Connection,
) -> ArtifactRecallResult | None:
    """Profile-scoped, fail-closed recall of the target's own stored plan/menu.

    Never returns another profile's artifact and never guesses: if the target has
    no matching artifact it returns an explicit 'erişemiyorum' message.
    """
    text = _normalized_message(message)
    wants_plan = _is_weekly_plan_recall(text)
    wants_menu = _is_menu_recall(text) if not wants_plan else False
    if not (wants_plan or wants_menu):
        return None
    sayfa = "Haftalık Plan" if wants_plan else "Menü Analizi"
    rows = son_sayfa_kayitlari(snapshot.account_id, sayfa, limit=15, conn=db)
    matches = [row for row in rows if history_matches_snapshot(row, snapshot)]
    if not matches:
        return ArtifactRecallResult(
            answer=_artifact_missing_answer(wants_plan, snapshot),
            artifact_reference="weekly_plan" if wants_plan else "menu_analysis",
        )
    latest = matches[0]  # son_sayfa_kayitlari returns newest-first
    if wants_plan:
        metadata = _log_metadata(latest)
        findings = _artifact_evidence_findings(metadata, snapshot, "weekly_plan")
        return ArtifactRecallResult(
            answer=_weekly_plan_recall_answer(
            latest,
            snapshot,
            wants_ingredients=_is_weekly_plan_ingredient_recall(text),
            ),
            artifact_reference="weekly_plan",
            findings=findings,
        )
    decision = _menu_recall_answer(latest, snapshot)
    return ArtifactRecallResult(
        answer=decision.answer,
        artifact_reference="menu_analysis",
        findings=decision.findings,
    )


def _artifact_followup_decision(context: CureBotResponseContext) -> ResponseDecision | None:
    if (
        context.turn.artifact_reference == "none"
        or context.turn.intent not in {"meal_followup", "menu_followup", "weekly_plan_followup"}
        or not context.findings
    ):
        return None
    inherited = carry_findings_without_new_evidence(context.findings)
    relevant = [item for item in inherited if item.evidence_level != "CLEAR"]
    if not relevant:
        return ResponseDecision(
            answer=(
                "Önceki kaydın yapılandırılmış içeriğinde kayıtlı kısıtlarla bir eşleşme görünmüyordu. "
                "Yine de kesin güvenlik için güncel etiket veya içerik bilgisini kontrol etmek gerekir."
            ),
            findings=inherited,
        )
    bullets = "\n".join(f"- {render_finding(item)}" for item in relevant[:6])
    return ResponseDecision(
        answer=(
            "Önceki analizdeki kanıt düzeyini değiştirmeden daha güvenli seçim için şu bulguları koruyorum:\n"
            f"{bullets}\n\nKesin eşleşen içeriği dışarıda bırak; olası veya belirsiz içerikleri etiket ya da işletmeden teyit et."
        ),
        findings=inherited,
    )


@router.post("/api/chat")
@limiter.limit("12/minute", key_func=authenticated_user_or_ip)
async def chat(request: Request, req: ChatRequest, bg_tasks: BackgroundTasks, telefon: str = Depends(get_current_user), db: sqlite3.Connection = Depends(get_db)):
    # Fail-closed target resolution: the message itself decides the person when it
    # names one; the client hint is used only when the message names nobody. A clear
    # reference to someone we cannot resolve asks for clarification instead of
    # silently using the account owner's health profile. Profile is read only via
    # the canonical snapshot layer (never a direct profile read in this router).
    recent_logs = loglari_getir_db(telefon, limit=50, conn=db)
    conversation_logs = _conversation_curebot_logs(recent_logs, req.conversation_id)
    previous_target = _previous_curebot_target(conversation_logs)
    snapshot, target_resolution = resolve_target_snapshot(
        telefon, req.mesaj, req.kimin_icin, previous_target=previous_target, db=db
    )
    logger.info(
        "event=curebot_target_resolved conversation_id=%s target_id=%s source=%s needs_clarification=%s referenced_other=%s",
        req.conversation_id or "legacy",
        snapshot.target_key if snapshot is not None else "unresolved",
        target_resolution.source,
        target_resolution.needs_clarification,
        target_resolution.referenced_someone_else,
    )
    if target_resolution.needs_clarification:
        clarify_answer = clarification_prompt(target_resolution)
        clarification_turn = ResolvedTurn(
            conversation_id=str(req.conversation_id or ""),
            target_profile_id="",
            target_scope="unknown",
            target_resolution_source=target_resolution.source,
            intent="clarification",
            subject="unknown",
            ambiguity_status="clarification_required",
        )
        _schedule_turn_commit(
            bg_tasks,
            telefon=telefon,
            snapshot=None,
            user_message=req.mesaj,
            answer_text=clarify_answer,
            turn=clarification_turn,
            response_path="clarification",
        )

        async def clarify_stream():
            yield _sse("message", {"chunk": clarify_answer})
            yield _sse("done")

        return _chat_stream_response(clarify_stream(), resolution=target_resolution)

    profil_ozeti = snapshot.profile_summary
    kullanici_id = snapshot.memory_namespace
    history_metadata = _chat_history_metadata(
        snapshot,
        conversation_id=req.conversation_id,
        target_resolution=target_resolution,
    )
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
        for item in conversation_logs
        if history_matches_snapshot(item, snapshot)
    ][:10]
    conversation_context = _local_conversation_context(conversation_logs[:10], snapshot)
    local_intent_plan = fallback_intent_plan(req.mesaj, snapshot.target_scope, conversation_context)
    resolved_turn = resolve_semantic_turn(
        local_intent_plan,
        req.mesaj,
        conversation_context,
        conversation_id=req.conversation_id,
        target_profile_id=snapshot.target_key,
        target_scope=snapshot.target_scope,
        target_resolution_source=target_resolution.source,
    )
    carried_findings = tuple(
        coerce_finding(item)
        for item in conversation_context.structured_findings
        if str(item.get("target_profile_id") or "") == snapshot.target_key
    )
    response_context = CureBotResponseContext(
        turn=resolved_turn,
        snapshot=snapshot,
        plan=local_intent_plan,
        conversation=conversation_context,
        user_message=req.mesaj,
        findings=carried_findings,
    )
    history_metadata = _chat_history_metadata(
        snapshot,
        local_intent_plan,
        conversation_id=req.conversation_id,
        target_resolution=target_resolution,
        user_message=req.mesaj,
        previous_context=conversation_context,
        resolved_turn=resolved_turn,
        response_path="resolved",
    )
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
        resolved_turn=resolved_turn.model_dump(),
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
        _schedule_turn_commit(
            bg_tasks, telefon=telefon, snapshot=snapshot, user_message=req.mesaj,
            answer_text=injection_answer, turn=resolved_turn, response_path="input_guardrail",
            plan=local_intent_plan,
        )
        async def injection_stream():
            yield _sse("message", {"chunk": injection_answer})
            yield _sse("governance", {"decision_id": decision_record["decision_id"], "risk_score": decision_record["risk_score"], "confidence_score": decision_record["confidence_score"], "input_guardrail": True})
            yield _sse("done")
        return _chat_stream_response(injection_stream(), snapshot, target_resolution)

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
        _schedule_turn_commit(
            bg_tasks, telefon=telefon, snapshot=snapshot, user_message=req.mesaj,
            answer_text=source_answer, turn=resolved_turn, response_path="source_disclosure",
            plan=local_intent_plan,
        )

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

        return _chat_stream_response(source_stream(), snapshot, target_resolution)

    # Profile-scoped recall of the target's own stored weekly plan / menu analysis.
    # Real artifact from interaction_logs (fail-closed); never another profile.
    artifact_result = _artifact_recall_answer(snapshot, req.mesaj, db=db)
    if artifact_result:
        artifact_answer = artifact_result.answer
        artifact_reference = artifact_result.artifact_reference
        artifact_turn = resolve_semantic_turn(
            local_intent_plan,
            req.mesaj,
            conversation_context,
            conversation_id=req.conversation_id,
            target_profile_id=snapshot.target_key,
            target_scope=snapshot.target_scope,
            target_resolution_source=target_resolution.source,
            artifact_reference=artifact_reference,
        )
        artifact_turn = artifact_turn.model_copy(update={
            "intent": f"{artifact_reference}_followup",
            "subject": "artifact",
            "object_label": "",
            "object_type": "unknown",
            "artifact_reference": artifact_reference,
        })
        artifact_state = _simple_chat_state(initial_state, artifact_answer)
        artifact_state["hedef_islem"] = "ARTIFACT_RECALL"
        decision_record = build_decision_record(artifact_state, telefon=telefon, kimin_icin=snapshot.target_key, final_answer=artifact_answer)
        bg_tasks.add_task(klinik_karar_kaydet, decision_record)
        _schedule_turn_commit(
            bg_tasks, telefon=telefon, snapshot=snapshot, user_message=req.mesaj,
            answer_text=artifact_answer, turn=artifact_turn, response_path="artifact_recall",
            plan=local_intent_plan,
            findings=artifact_result.findings,
        )

        async def artifact_stream():
            yield _sse("message", {"chunk": artifact_answer})
            yield _sse("governance", {"decision_id": decision_record["decision_id"], "risk_score": decision_record["risk_score"], "confidence_score": decision_record["confidence_score"], "artifact_recall": True})
            yield _sse("done")

        return _chat_stream_response(artifact_stream(), snapshot, target_resolution)

    # Registered health data is source-of-truth: if the message denies a recorded
    # allergy/disease, surface a notice and keep applying it, rather than silently
    # honoring the chat message. (Audit P2-a.)
    conflict_answer = _profile_conflict_answer(snapshot, req.mesaj)
    if conflict_answer:
        conflict_state = _simple_chat_state(initial_state, conflict_answer)
        decision_record = build_decision_record(conflict_state, telefon=telefon, kimin_icin=snapshot.target_key, final_answer=conflict_answer)
        bg_tasks.add_task(klinik_karar_kaydet, decision_record)
        _schedule_turn_commit(
            bg_tasks, telefon=telefon, snapshot=snapshot, user_message=req.mesaj,
            answer_text=conflict_answer, turn=resolved_turn, response_path="profile_conflict",
            plan=local_intent_plan,
        )

        async def conflict_stream():
            yield _sse("message", {"chunk": conflict_answer})
            yield _sse("done")

        return _chat_stream_response(conflict_stream(), snapshot, target_resolution)

    # Everyday conversation must be resolved before generic input/rule safety.
    # Risky food questions return None here and continue to the explicit safety gate below.
    intent_answer = None
    if intent_answer:
        intent_state = _simple_chat_state(initial_state, intent_answer)
        decision_record = build_decision_record(intent_state, telefon=telefon, kimin_icin=snapshot.target_key, final_answer=intent_answer)
        bg_tasks.add_task(klinik_karar_kaydet, decision_record)
        _schedule_turn_commit(
            bg_tasks, telefon=telefon, snapshot=snapshot, user_message=req.mesaj,
            answer_text=intent_answer, turn=resolved_turn, response_path="precheck_fast_path",
            plan=local_intent_plan,
        )

        async def intent_stream_precheck():
            yield _sse("status", {"status": "Yanıt hazırlanıyor..."})
            yield _sse("message", {"chunk": intent_answer})
            yield _sse("governance", {"decision_id": decision_record["decision_id"], "risk_score": decision_record["risk_score"], "confidence_score": decision_record["confidence_score"], "fast_path": True})
            yield _sse("done")

        return _chat_stream_response(intent_stream_precheck(), snapshot, target_resolution)

    try:
        intent_plan = await asyncio.wait_for(
            run_in_threadpool(
                plan_curebot_semantically,
                req.mesaj,
                conversation_context.model_dump(exclude={"structured_findings"}),
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

    resolved_turn = resolve_semantic_turn(
        intent_plan,
        req.mesaj,
        conversation_context,
        conversation_id=req.conversation_id,
        target_profile_id=snapshot.target_key,
        target_scope=snapshot.target_scope,
        target_resolution_source=target_resolution.source,
    )
    response_context = CureBotResponseContext(
        turn=resolved_turn,
        snapshot=snapshot,
        plan=intent_plan,
        conversation=conversation_context,
        user_message=req.mesaj,
        findings=carried_findings,
    )
    initial_state["resolved_turn"] = resolved_turn.model_dump()

    history_metadata = _chat_history_metadata(
        snapshot,
        intent_plan,
        conversation_id=req.conversation_id,
        target_resolution=target_resolution,
        user_message=req.mesaj,
        previous_context=conversation_context,
        resolved_turn=resolved_turn,
        response_path="resolved",
    )

    if intent_plan.intent == "off_topic":
        off_topic_answer = "Ben beslenme ve sağlık odaklı bir asistanım. Lütfen CureMenu'nün temel amacı olan bu konularda sorular sorun."
        off_topic_state = _simple_chat_state(initial_state, off_topic_answer)
        decision_record = build_decision_record(off_topic_state, telefon=telefon, kimin_icin=snapshot.target_key, final_answer=off_topic_answer)
        bg_tasks.add_task(klinik_karar_kaydet, decision_record)
        _schedule_turn_commit(
            bg_tasks, telefon=telefon, snapshot=snapshot, user_message=req.mesaj,
            answer_text=off_topic_answer, turn=resolved_turn, response_path="off_topic",
            plan=intent_plan,
        )
        
        async def off_topic_stream():
            yield _sse("message", {"chunk": off_topic_answer})
            yield _sse("governance", {"decision_id": decision_record["decision_id"], "risk_score": decision_record["risk_score"], "confidence_score": decision_record["confidence_score"], "fast_path": True})
            yield _sse("done")
        return _chat_stream_response(off_topic_stream(), snapshot, target_resolution)

    input_safety_decision = _explicit_input_safety_answer(response_context)
    input_safety_answer = input_safety_decision.answer if input_safety_decision else None
    artifact_followup = _artifact_followup_decision(response_context)
    if not input_safety_answer and artifact_followup:
        artifact_state = _simple_chat_state(initial_state, artifact_followup.answer)
        decision_record = build_decision_record(
            artifact_state, telefon=telefon, kimin_icin=snapshot.target_key,
            final_answer=artifact_followup.answer,
        )
        bg_tasks.add_task(klinik_karar_kaydet, decision_record)
        _schedule_turn_commit(
            bg_tasks, telefon=telefon, snapshot=snapshot, user_message=req.mesaj,
            answer_text=artifact_followup.answer, turn=resolved_turn,
            response_path="artifact_followup", plan=intent_plan,
            findings=artifact_followup.findings,
        )

        async def artifact_followup_stream():
            yield _sse("message", {"chunk": artifact_followup.answer})
            yield _sse("done")

        return _chat_stream_response(artifact_followup_stream(), snapshot, target_resolution)

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
                        resolved_turn,
                    ),
                    timeout=6,
                )
        except Exception:
            natural_answer = natural_fallback_answer(intent_plan, snapshot, conversation_context, resolved_turn)
        if natural_answer:
            natural_state = _simple_chat_state(initial_state, natural_answer)
            if natural_state.get("guvenli_mi") is False:
                natural_answer = natural_fallback_answer(intent_plan, snapshot, conversation_context, resolved_turn)
                natural_state = _simple_chat_state(initial_state, natural_answer)
                if natural_state.get("guvenli_mi") is False:
                    natural_answer = (
                        "Bu seçenekleri profilinle güvenle eşleştiremedim. "
                        "Evde bulunan iki veya üç malzemeyi yazarsan alerjenleri dışarıda bırakıp daha net bir öğün önerebilirim."
                    )
                    natural_state = _simple_chat_state(initial_state, natural_answer)
            decision_record = build_decision_record(natural_state, telefon=telefon, kimin_icin=snapshot.target_key, final_answer=natural_answer)
            bg_tasks.add_task(klinik_karar_kaydet, decision_record)
            _schedule_turn_commit(
                bg_tasks, telefon=telefon, snapshot=snapshot, user_message=req.mesaj,
                answer_text=natural_answer, turn=resolved_turn, response_path="natural_fast_path",
                plan=intent_plan,
            )

            async def natural_stream():
                yield _sse("message", {"chunk": natural_answer})
                yield _sse("governance", {"decision_id": decision_record["decision_id"], "risk_score": decision_record["risk_score"], "confidence_score": decision_record["confidence_score"], "fast_path": True})
                yield _sse("done")

            return _chat_stream_response(natural_stream(), snapshot, target_resolution)
    if input_safety_answer:
        blocked_state = _guardrail_block_state(initial_state, input_safety_answer)
        decision_record = build_decision_record(
            blocked_state,
            telefon=telefon,
            kimin_icin=snapshot.target_key,
            final_answer=input_safety_answer,
        )
        bg_tasks.add_task(klinik_karar_kaydet, decision_record)
        _schedule_turn_commit(
            bg_tasks, telefon=telefon, snapshot=snapshot, user_message=req.mesaj,
            answer_text=input_safety_answer, turn=resolved_turn, response_path="deterministic_safety",
            plan=intent_plan,
            findings=input_safety_decision.findings,
        )

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

        return _chat_stream_response(input_safety_stream(), snapshot, target_resolution)

    intent_answer = _intent_fast_answer(response_context)
    if intent_answer:
        intent_state = _simple_chat_state(initial_state, intent_answer)
        decision_record = build_decision_record(intent_state, telefon=telefon, kimin_icin=snapshot.target_key, final_answer=intent_answer)
        bg_tasks.add_task(klinik_karar_kaydet, decision_record)
        _schedule_turn_commit(
            bg_tasks, telefon=telefon, snapshot=snapshot, user_message=req.mesaj,
            answer_text=intent_answer, turn=resolved_turn, response_path="deterministic_intent",
            plan=intent_plan,
        )

        async def intent_stream():
            yield _sse("status", {"status": "Yanıt hazırlanıyor..."})
            yield _sse("message", {"chunk": intent_answer})
            yield _sse("governance", {"decision_id": decision_record["decision_id"], "risk_score": decision_record["risk_score"], "confidence_score": decision_record["confidence_score"], "fast_path": True})
            yield _sse("done")

        return _chat_stream_response(intent_stream(), snapshot, target_resolution)

    simple_answer = _simple_chat_message(req.mesaj, profil_ozeti, gecmis_klinik)
    if simple_answer:
        simple_state = _simple_chat_state(initial_state, simple_answer)
        decision_record = build_decision_record(simple_state, telefon=telefon, kimin_icin=snapshot.target_key, final_answer=simple_answer)
        bg_tasks.add_task(klinik_karar_kaydet, decision_record)
        _schedule_turn_commit(
            bg_tasks, telefon=telefon, snapshot=snapshot, user_message=req.mesaj,
            answer_text=simple_answer, turn=resolved_turn, response_path="simple_response",
            plan=intent_plan,
        )
        async def simple_stream():
            yield _sse("status", {"status": "Yanıt hazırlanıyor..."})
            yield _sse("message", {"chunk": simple_answer})
            yield _sse("governance", {"decision_id": decision_record["decision_id"], "risk_score": decision_record["risk_score"], "confidence_score": decision_record["confidence_score"], "fast_path": True})
            yield _sse("done")
        return _chat_stream_response(simple_stream(), snapshot, target_resolution)

    if rails:
        try:
            guard_cevap = await rails.generate_async(messages=[{"role": "user", "content": req.mesaj}])
            icerik = guard_cevap.get("content", "")
            red_mesajlari = ["Siyaset hakkında yorum yapamam", "Yazılım veya kodlama konularında yardımcı olamam", "doktor değilim, tıbbi bir tanı koyamam", "Therapeutic Hallucination Guardrail"]
            if any(r in icerik for r in red_mesajlari):
                blocked_state = _guardrail_block_state(initial_state, icerik)
                decision_record = build_decision_record(blocked_state, telefon=telefon, kimin_icin=snapshot.target_key, final_answer=icerik)
                bg_tasks.add_task(klinik_karar_kaydet, decision_record)
                _schedule_turn_commit(
                    bg_tasks, telefon=telefon, snapshot=snapshot, user_message=req.mesaj,
                    answer_text=icerik[:500], turn=resolved_turn, response_path="runtime_guardrail",
                    plan=intent_plan,
                )
                async def guardrail_stream():
                    yield _sse("governance", {"decision_id": decision_record["decision_id"], "risk_score": decision_record["risk_score"], "confidence_score": decision_record["confidence_score"]})
                    msg_text = f"🛡️ **Sistem Uyarısı (NeMo Guardrails):**\n\n{icerik}"
                    yield f"event: error\ndata: {json.dumps({'message': msg_text})}\n\n"
                return _chat_stream_response(guardrail_stream(), snapshot, target_resolution)
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
                final_answer = natural_fallback_answer(intent_plan, snapshot, conversation_context, resolved_turn)
            final_answer = soften_unsourced_clinical_limits(final_answer)
            yield _sse("message", {"chunk": final_answer})
                
            decision_record = build_decision_record(final_state, telefon=telefon, kimin_icin=snapshot.target_key, final_answer=final_answer)
            bg_tasks.add_task(klinik_karar_kaydet, decision_record)
            _schedule_turn_commit(
                bg_tasks, telefon=telefon, snapshot=snapshot, user_message=req.mesaj,
                answer_text=final_answer, turn=resolved_turn, response_path="model_graph",
                plan=intent_plan,
            )
            yield _sse("governance", {"decision_id": decision_record["decision_id"], "risk_score": decision_record["risk_score"], "confidence_score": decision_record["confidence_score"]})
            yield _sse("done")
        except Exception as e:
            log_failure(logger, "chat_stream", e, component="chat")
            fallback_answer = natural_fallback_answer(intent_plan, snapshot, conversation_context, resolved_turn)
            fallback_state = _chat_fallback_state(initial_state, fallback_answer, e)
            decision_record = build_decision_record(fallback_state, telefon=telefon, kimin_icin=snapshot.target_key, final_answer=fallback_answer)
            bg_tasks.add_task(klinik_karar_kaydet, decision_record)
            _schedule_turn_commit(
                bg_tasks, telefon=telefon, snapshot=snapshot, user_message=req.mesaj,
                answer_text=fallback_answer, turn=resolved_turn, response_path="error_fallback",
                plan=intent_plan,
            )
            yield _sse("message", {"chunk": fallback_answer})
            yield _sse("governance", {"decision_id": decision_record["decision_id"], "risk_score": decision_record["risk_score"], "confidence_score": decision_record["confidence_score"], "fallback": True})
            yield _sse("done")

    return _chat_stream_response(event_generator(), snapshot, target_resolution)
