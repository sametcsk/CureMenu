"""Structured, bounded intent planning for CureBot conversation routing."""
import json
from datetime import datetime
import re
import unicodedata
from typing import Any, Literal

from pydantic import BaseModel, Field

from src.llm import invoke_with_model_fallback, parse_llm_response
from src.medical_knowledge.normalizer import canonical_medication_name, extract_medication_mentions



class CureBotIntentPlan(BaseModel):
    intent: Literal[
        "smalltalk", "meal_recommendation", "dessert_craving", "coffee_habit",
        "meal_followup", "explanation_followup", "emotional_support",
        "medication_food_question", "allergy_conflict",
        "product_question", "lab_followup", "menu_followup", "out_of_scope",
        "unknown_nutrition_related", "off_topic"
    ] = "unknown_nutrition_related"
    target: Literal["self", "family", "member"] = "self"
    target_hint: str = ""
    meal_context: Literal["breakfast", "lunch", "dinner", "snack", "dessert", "coffee_pairing", "unknown"] = "unknown"
    risk_subject: str = ""
    is_profile_declaration: bool = False
    is_followup: bool = False
    needs_safety_gate: bool = False
    answer_style: Literal["short", "practical", "explanatory", "product_explainer"] = "practical"
    confidence: float = Field(default=0.35, ge=0, le=1)
    reason: str = "fallback"
    privacy_mode: Literal["minimal"] = "minimal"


class CureBotConversationContext(BaseModel):
    last_intent: str = ""
    last_meal_context: Literal["breakfast", "lunch", "dinner", "snack", "dessert", "coffee_pairing", "unknown"] = "unknown"
    last_answer_type: str = ""
    last_target_scope: Literal["self", "member", "family", "unknown"] = "unknown"
    has_previous_turn: bool = False
    privacy_mode: Literal["minimal"] = "minimal"


def _normalized(value: str) -> str:
    folded = unicodedata.normalize("NFKD", str(value or "").casefold().replace("ı", "i"))
    return "".join(char for char in folded if not unicodedata.combining(char))


def _coerce_conversation_context(value: Any) -> CureBotConversationContext:
    if isinstance(value, CureBotConversationContext):
        return value
    if isinstance(value, dict):
        allowed = {
            key: value.get(key)
            for key in ("last_intent", "last_meal_context", "last_answer_type", "last_target_scope", "has_previous_turn")
            if key in value
        }
        try:
            return CureBotConversationContext(**allowed)
        except Exception:
            return CureBotConversationContext()
    if isinstance(value, list):
        # Raw conversation messages are deliberately ignored. Only explicit
        # local labels are accepted as cross-turn context.
        for item in reversed(value):
            if isinstance(item, dict) and any(str(key).startswith("last_") for key in item):
                return _coerce_conversation_context(item)
    return CureBotConversationContext()


def _resolved_target_scope(target: str) -> Literal["self", "member", "family"]:
    normalized = _normalized(target)
    if normalized in {"aile", "family"}:
        return "family"
    if normalized in {"kendim", "self"}:
        return "self"
    return "member"


def fallback_intent_plan(
    message: str,
    target: str = "kendim",
    conversation_context: CureBotConversationContext | dict | list | None = None,
) -> CureBotIntentPlan:
    text = _normalized(message)
    previous_context = _coerce_conversation_context(conversation_context)
    resolved_target = _resolved_target_scope(target)
    meal_context = "unknown"
    intent = "unknown_nutrition_related"
    if any(x in text for x in ("kahvalt", "sabah")):
        meal_context, intent = "breakfast", "meal_recommendation"
    elif any(x in text for x in ("aksam", "ogun", "yemek", "sofra")):
        meal_context, intent = "dinner", "meal_recommendation"
    elif "tatli" in text:
        meal_context, intent = "dessert", "dessert_craving"
    elif "kahve" in text:
        meal_context, intent = "coffee_pairing", "coffee_habit"
    if any(x in text for x in ("hangi kriter", "neye gore", "onceki oner", "neden bunu onerdin")):
        intent = "explanation_followup"

    emotional_signals = (
        "bunaldim", "hicbir sey yiyem", "her sey yasak", "ne yiyecegimi sasirdim",
        "yemek secmekten yoruldum", "beslenme konusunda kaygili",
    )
    if any(signal in text for signal in emotional_signals):
        intent = "emotional_support"

    followup_signals = (
        "peki", "yanina ne", "sofraya ne", "ekmek olarak", "malzemeleri ne",
        "tarifini", "baska bir", "daha farkli", "alternatif", "hangisi",
    )
    short_followups = {"oner", "alternatif", "baska", "daha farkli", "detay", "tarif"}
    if text.strip() in short_followups or any(signal in text for signal in followup_signals):
        intent = "meal_followup"
        if previous_context.last_meal_context != "unknown":
            meal_context = previous_context.last_meal_context

    medication_mentions = extract_medication_mentions(message)
    if not medication_mentions:
        medication_mentions = [
            token
            for token in re.findall(r"[A-Za-zÇĞİÖŞÜçğıöşü-]{2,40}", str(message or ""))
            if canonical_medication_name(token) is not None
        ]
    medication_question = bool(medication_mentions) and any(
        signal in text
        for signal in ("birlikte", "sonra", "once", "icersem", "icsem", "yesem", "sakincali", "etkiles", "uygun mu")
    )
    if medication_question:
        intent = "medication_food_question"

    explicit_consumption_question = any(
        signal in text for signal in ("yiyebilir miyim", "icebilir miyim", "uygun mu", "sakincali mi")
    )
    risk_subject = "explicit_food_request" if explicit_consumption_question else ""
    return CureBotIntentPlan(
        target=resolved_target,
        intent=intent,
        meal_context=meal_context,
        risk_subject=risk_subject,
        needs_safety_gate=bool(explicit_consumption_question or medication_question),
        is_followup=intent in {"meal_followup", "explanation_followup"},
        reason="local privacy fallback",
    )


def classify_intent_plan(message: str, conversation: Any = None, target: str = "self", profile_names: list[str] | None = None, health_flags: dict | None = None) -> CureBotIntentPlan:
    text = _normalized(message)
    nutrition_signals = (
        "yemek", "yemel", "beslen", "diyet", "kahvalt", "ogun", "tatli",
        "kahve", "alerji", "hastalik", "ilac", "tahlil", "menu",
        "kalori", "protein", "market", "alisveris", "yogurt",
    )
    off_topic_signals = (
        "hava nasil", "fikra", "react js", "javascript", "kod yaz",
        "baskent", "futbol", "mac sonucu", "siir yaz",
    )
    if any(signal in text for signal in off_topic_signals) and not any(signal in text for signal in nutrition_signals):
        return CureBotIntentPlan(intent="off_topic", answer_style="short", confidence=0.98, reason="local off-topic classifier")
    # The classifier is intentionally local. Raw history, names and health data
    # must not be sent to a provider merely to choose a routing label.
    return fallback_intent_plan(message, target, conversation)


def _privacy_safe_classifier_message(message: str, profile_names: list[str] | None = None) -> str:
    text = str(message or "")[:900]
    for name in profile_names or []:
        clean_name = str(name or "").strip()
        if clean_name:
            text = re.sub(re.escape(clean_name), "seçili kişi", text, flags=re.IGNORECASE)
    text = re.sub(r"(?<!\d)(?:\+?90\s*)?0?5\d{2}[\s.-]*\d{3}[\s.-]*\d{2}[\s.-]*\d{2}(?!\d)", "[telefon gizlendi]", text)
    text = re.sub(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", "[e-posta gizlendi]", text, flags=re.IGNORECASE)
    return text


def _parse_intent_plan_json(raw_response: Any) -> dict[str, Any]:
    text = parse_llm_response(raw_response).strip()
    fenced = re.sub(r"^```(?:json)?\s*|\s*```$", "", text, flags=re.IGNORECASE).strip()
    try:
        parsed = json.loads(fenced)
    except json.JSONDecodeError:
        match = re.search(r"\{[\s\S]*\}", fenced)
        if not match:
            raise
        parsed = json.loads(match.group(0))
    if not isinstance(parsed, dict):
        raise ValueError("Intent planner response must be a JSON object")
    return parsed


def plan_curebot_semantically(
    message: str,
    conversation: CureBotConversationContext | dict | list | None = None,
    target: str = "self",
    profile_names: list[str] | None = None,
    health_flags: dict | None = None,
) -> CureBotIntentPlan:
    """Classify one turn with minimal provider context and a local fallback."""
    previous_context = _coerce_conversation_context(conversation)
    local_plan = classify_intent_plan(message, previous_context, target, [], health_flags)
    safe_message = _privacy_safe_classifier_message(message, profile_names)
    minimal_health_flags = {
        "allergy_present": bool((health_flags or {}).get("allergy_present")),
        "medication_present": bool((health_flags or {}).get("medication_present")),
        "disease_present": bool((health_flags or {}).get("disease_present")),
    }
    planner_payload = {
        "current_user_message": safe_message,
        "active_target_scope": _resolved_target_scope(target),
        "health_constraint_flags": minimal_health_flags,
        "previous_turn_labels": previous_context.model_dump(exclude={"privacy_mode"}),
        "privacy_mode": "minimal",
    }
    allowed_intents = list(CureBotIntentPlan.model_fields["intent"].annotation.__args__)
    allowed_meal_contexts = list(CureBotIntentPlan.model_fields["meal_context"].annotation.__args__)
    prompt = f"""You are the privacy-safe semantic triage layer for CureBot, a Turkish nutrition decision-support assistant.
Classify the user's current turn. Do not answer the user.

MINIMAL INPUT:
{json.dumps(planner_payload, ensure_ascii=False)}

Return exactly one JSON object with these fields:
intent, meal_context, is_profile_declaration, is_followup, needs_safety_gate, answer_style, confidence.

Allowed intents: {json.dumps(allowed_intents, ensure_ascii=False)}
Allowed meal_context values: {json.dumps(allowed_meal_contexts, ensure_ascii=False)}
Allowed answer_style values: ["short", "practical", "explanatory", "product_explainer"]

Routing rules:
- meal_followup covers short contextual continuations such as asking what to add, replace, cook, or explain.
- emotional_support covers feeling overwhelmed specifically about food choices; it is not a medical diagnosis.
- medication_food_question covers medicine timing or medicine-food interaction questions.
- off_topic covers requests outside nutrition, health-profile use, menus, labs, groceries, and CureMenu product help.
- Mark needs_safety_gate true for explicit consumption safety, allergy conflict, medication-food, or lab-risk questions.
- Never infer or reproduce a person's name, phone, email, diagnosis, medication, or allergy that is absent from MINIMAL INPUT.
"""
    try:
        parsed = _parse_intent_plan_json(invoke_with_model_fallback(prompt, temperature=0.0))
        semantic_plan = CureBotIntentPlan.model_validate({
            **parsed,
            "target": _resolved_target_scope(target),
            "target_hint": "",
            "risk_subject": local_plan.risk_subject,
            "privacy_mode": "minimal",
            "reason": "privacy-safe semantic triage",
        })
        semantic_plan.needs_safety_gate = bool(
            semantic_plan.needs_safety_gate
            or local_plan.needs_safety_gate
            or semantic_plan.intent in {"medication_food_question", "allergy_conflict", "lab_followup"}
        )
        return semantic_plan
    except Exception:
        return local_plan


def plan_requires_safety_gate(plan: CureBotIntentPlan) -> bool:
    return bool(plan.needs_safety_gate or plan.intent in {"medication_food_question", "allergy_conflict", "lab_followup"})


def _natural_fallback(plan: CureBotIntentPlan) -> str:
    by_intent = {
        "dessert_craving": "Tatlı isteğini daha dengeli karşılayabiliriz:\n\n- **Meyveli seçenek:** Küçük bir porsiyon fırınlanmış elma veya armut deneyebilirsin.\n- **Kaşık tatlısı:** Kuruyemişsiz chia pudingi ya da sana uygun bir yoğurt alternatifi seçebilirsin.",
        "coffee_habit": "Kahveyi tamamen bırakmak gerekmeyebilir:\n\n- **Miktarı gözle:** Seni rahatsız etmeyen günlük miktarı koru.\n- **Saati ayarla:** Uyku veya mide sorunu yapıyorsa daha erken saatlere çek.",
        "meal_followup": "Önceki öğün fikrini tamamlayabiliriz:\n\n- **Dengeli eşlikçi:** Sebze, ölçülü bir tahıl veya uygun bir ekmek seçeneği ekleyebilirsin.\n- **Netleştirelim:** Hangi parçayı değiştirmek istediğini söylersen öneriyi daraltabilirim.",
        "emotional_support": "Bu kadar çok ayrıntıyı aynı anda düşünmek yorucu gelebilir.\n\n- **Tek öğüne odaklan:** Şimdilik yalnızca bir sonraki öğünü seçelim.\n- **Basit tut:** Bildiğin, içeriği net ve seni rahatsız etmeyen birkaç temel malzemeyle başlayalım.",
        "explanation_followup": "Öneriyi profil uyumu, alerji güvenliği, porsiyon dengesi ve hazırlama kolaylığını birlikte düşünerek oluşturdum.",
    }
    by_meal = {
        "breakfast": "Kahvaltıyı sade ve dengeli tutabiliriz:\n\n- **Protein desteği:** Sana uygun bir yumurta veya yoğurt seçeneği ekle.\n- **Lif desteği:** Sebze ve ölçülü bir tahılla tamamla.",
        "dinner": "Akşam için dengeli bir tabakla başlayabiliriz:\n\n- **Ana yemek:** Izgara veya fırında bir protein seç.\n- **Yanına:** Sebze ve ölçülü bir tahıl ya da ekmek ekle.",
    }
    return by_intent.get(plan.intent) or by_meal.get(plan.meal_context) or "İsteğini biraz netleştirirsen profil bağlamında pratik bir seçenek önerebilirim."


def _concise_markdown(answer: str, plan: CureBotIntentPlan, snapshot) -> str:
    text = re.sub(r"(?is)^(?:sağlık profiliniz nedeniyle.*?)(?:\n\n|$)", "", str(answer or "").strip())
    for phrase in ("İsteğinize uygun seçenekler:", "iki harika önerim var", "ilaçlarını düzenli kullanmayı unutma"):
        text = re.sub(re.escape(phrase), "", text, flags=re.IGNORECASE)
    if snapshot.allergies:
        text = re.sub(r"(?im)^.*(?:badem sütü|ceviz|fıstık|kuruyemiş).*$(?:\n|$)", "", text)
    words = text.split()
    if len(words) > 110 and plan.intent != "explanation_followup":
        text = " ".join(words[:110]).rstrip(" ,;:") + "."
    if plan.intent == "explanation_followup":
        # Explanations should describe criteria, never become a second meal recommendation.
        text = (
            "Bu öneriyi birkaç ölçütü birlikte değerlendirerek hazırladım:\n\n"
            "- **Profil uyumu:** Seçili hedefin bilinen sağlık kısıtları.\n"
            "- **Alerji güvenliği:** Kayıtlı alerjenlerden ve belirsiz içeriklerden kaçınma.\n"
            "- **Porsiyon dengesi:** Öğünün tokluk ve kan şekeri açısından ölçülü olması.\n"
            "- **Pratiklik:** Hazırlama süresi, pişirme yöntemi ve günlük koşullar."
        )
    else:
        # Models can follow the requested structure semantically while omitting
        # Markdown markers. Normalize plain "meal: explanation" option lines so
        # every target receives the same readable presentation.
        formatted_lines: list[str] = []
        option_count = 0
        for raw_line in text.splitlines():
            line = raw_line.strip()
            option_match = re.match(r"^(?![-*>#])([^:]{3,80}):\s+(.+)$", line)
            if option_match:
                heading = option_match.group(1).strip()
                explanation = option_match.group(2).strip()
                if _normalized(heading) not in {"kisa not", "not", "dikkat"}:
                    formatted_lines.append(f"- **{heading}:** {explanation}")
                    option_count += 1
                    continue
            formatted_lines.append(raw_line.rstrip())
        if option_count >= 2:
            text = "\n".join(formatted_lines)
    if "**" not in text and not re.search(r"(?m)^\s*[-•]", text):
        sentences = [part.strip() for part in re.split(r"(?<=[.!?])\s+", text) if part.strip()]
        if len(sentences) > 1:
            text = sentences[0] + "\n\n" + "\n".join(f"- {sentence}" for sentence in sentences[1:3])
    return text.strip() or _natural_fallback(plan)


def _privacy_safe_user_message(user_message: str, snapshot) -> str:
    target_name = str(getattr(snapshot, "target_name", "") or "").strip()
    names = [] if _normalized(target_name) in {"tum aile", "family"} else [target_name]
    return _privacy_safe_classifier_message(user_message, names)


def generate_curebot_natural_answer(
    intent_plan: CureBotIntentPlan,
    snapshot,
    user_message: str,
    safety_context: str = "",
    conversation_context: CureBotConversationContext | dict | None = None,
) -> str:
    previous_context = _coerce_conversation_context(conversation_context)
    flags = {
        "target_scope": snapshot.target_scope,
        "allergy_present": bool(snapshot.allergies),
        "disease_present": bool(snapshot.diseases),
        "medication_present": bool(snapshot.medications),
        "allergy_categories": list(snapshot.allergies)[:8],
        "disease_categories": list(snapshot.diseases)[:8],
        "medication_categories": list(snapshot.medications)[:8],
    }
    safe_message = _privacy_safe_user_message(user_message, snapshot)
    context_labels = previous_context.model_dump(exclude={"privacy_mode"})
    prompt = f"""You are CureBot, a warm Turkish nutrition decision-support assistant.
Return only the final Turkish answer to the user.
USER MESSAGE: {safe_message}
INTENT PLAN: {intent_plan.model_dump_json(exclude={"reason"})}
LOCAL CONVERSATION LABELS: {json.dumps(context_labels, ensure_ascii=False)}
MINIMAL PROFILE FACTS: {json.dumps(flags, ensure_ascii=False)}
SAFETY CONTEXT: {safety_context[:500]}
RESPONSE VARIATION SEED: {datetime.now().minute}

Rules: sound natural and varied. Default to 60-110 words; only use 120-180 words if the user asks for detail, a recipe, or an explanation. Never write one long paragraph.
Use this exact Markdown structure: one short opening sentence, then 2-3 separate bullet options.
Write every option as `- **Yemek adı:** 1-2 concise explanatory sentences.` Never return option names as plain `Yemek adı:` lines.
End with one brief "Kısa not:" only when genuinely needed. Do not add a long disclaimer.
Do not use the user's name or any family member name. Do not mention internal plans, rules, scores or classifiers.
Avoid exaggerated words such as "harika", "en sağlıklısı" or "çok önemli". Do not repeat stock openings such as "İsteğinize uygun seçenekler".
If allergy flags are present, do not make nuts or nut milks the default first option; prefer nut-free fruit, baked apple/pear, chia or suitable yogurt alternatives. If a nut-derived option is mentioned, advise checking labels and cross-contamination.
Never begin with generic health disclaimers. Do not use the phrase 'kayıtlı alerjenleri dışarıda bırakan'.
Use a short safety note only at the end when clearly necessary. Do not invent unknown ingredients or medical facts.
For meal_followup, answer the current follow-up using only the local labels and current message. If those labels are insufficient, ask one short clarifying question instead of inventing the previous meal.
For emotional_support, acknowledge that food decisions can feel tiring, reduce the task to one manageable next meal, and avoid diagnosis, alarmist language, or a long restriction list.
"""
    try:
        response = invoke_with_model_fallback(prompt, temperature=0.65)
        answer = parse_llm_response(response).strip()
        return _concise_markdown(answer or _natural_fallback(intent_plan), intent_plan, snapshot)
    except Exception:
        return _natural_fallback(intent_plan)
