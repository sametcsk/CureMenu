from src.presentation import format_rule_risks_for_user, soften_generated_guidance, user_facing_safety_guidance
from src.chat_intents import normalized_message

_GENERIC_REVIEW_GUIDANCE = (
    "Sa\u011fl\u0131k profiliniz nedeniyle bu \u00f6neri dikkat gerektirebilir. "
    "Ki\u015fisel porsiyon ve zamanlama i\u00e7in doktorunuza, eczac\u0131n\u0131za veya diyetisyeninize dan\u0131\u015fman\u0131z uygun olur."
)


def _warning_free_intent(message: str) -> bool:
    text = normalized_message(message)
    return text in {"ok", "tamam", "tesekkurler", "tesekkur ederim", "rica ederim", "sag ol", "sagol", "devam"} or any(
        phrase in text for phrase in ("curemenu nedir", "nasil kullanilir", "hangi ekrandayim", "nasil calisir")
    )


def safety_outcome(result: dict) -> tuple[bool, bool]:
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


def _has_specific_review_signal(result: dict) -> bool:
    for event in result.get("governance_events") or []:
        event_type = event.get("event_type")
        status = event.get("status")
        metadata = event.get("metadata") or {}
        if event_type == "RuleTriggered" and status in {"review", "blocked"}:
            return True
        if event_type in {"MedicationSafetyChecked", "MedicationReviewRequired"} and status in {"review", "blocked"}:
            return True
        if event_type == "RuleChecked" and (
            int(metadata.get("warning_count") or 0) > 0
            or int(metadata.get("risk_count") or 0) > 0
        ):
            return True
    warning = normalized_message(str(result.get("uyari_mesaji") or ""))
    if "ilac-besin etkilesimi" in warning and any(
        signal in warning for signal in ("dogrulanamadi", "risk", "sakincali", "etkilesim")
    ):
        return True
    return False


def _food_specific_block_answer(result: dict) -> str:
    """Render deterministic blocked food findings without exposing rule labels."""
    risks: list[str] = []
    for event in result.get("governance_events") or []:
        if event.get("event_type") != "RuleTriggered" or event.get("status") != "blocked":
            continue
        metadata = event.get("metadata") or {}
        event_risks = metadata.get("risks") or []
        if isinstance(event_risks, (list, tuple)):
            risks.extend(str(item).strip() for item in event_risks if str(item).strip())
    formatted = format_rule_risks_for_user(list(dict.fromkeys(risks)))
    if not formatted:
        return ""
    bullets = "\n".join(f"- {item}" for item in formatted)
    return (
        "Bu seçeneği mevcut haliyle önermiyorum. Profilinizle şu açık çakışmalar bulundu:\n"
        f"{bullets}\n\n"
        "Riskli malzeme çıkarılmış bir alternatif seçmek daha doğru olur."
    )


def final_response_text(result: dict, streamed_text: str = "") -> str:
    warning = str(result.get("uyari_mesaji") or "").strip()
    profile = result.get("resolved_profile_snapshot")
    base_answer = soften_generated_guidance(str(
        result.get("tarif_metni")
        or result.get("uzman_onerisi")
        or result.get("adime_raporu")
        or streamed_text
        or ""
    ).strip())
    if _warning_free_intent(str(result.get("istek") or result.get("mesaj") or "")):
        return base_answer or "Rica ederim. Ba\u015fka bir konuda yard\u0131mc\u0131 olmam\u0131 ister misin?"
    blocked, review_required = safety_outcome(result)
    if blocked:
        food_specific_answer = _food_specific_block_answer(result)
        if food_specific_answer:
            return food_specific_answer
        return user_facing_safety_guidance(warning, blocked=True, profile=profile)
    if review_required:
        if base_answer and (not warning or not _has_specific_review_signal(result)):
            return base_answer
        if base_answer and normalized_message(warning) == normalized_message(_GENERIC_REVIEW_GUIDANCE):
            return base_answer
        guidance = user_facing_safety_guidance(warning, profile=profile)
        if base_answer and base_answer != warning:
            if normalized_message(guidance) in normalized_message(base_answer):
                return base_answer
            return f"{base_answer}\n\nKısa not: {guidance}"
        return guidance
    return base_answer or warning
