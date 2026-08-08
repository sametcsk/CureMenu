"""Structured, bounded intent planning for CureBot conversation routing."""
import json
from datetime import datetime
import re
from typing import Literal

from pydantic import BaseModel, Field

from src.llm import invoke_with_model_fallback, parse_llm_response



class CureBotIntentPlan(BaseModel):
    intent: Literal[
        "smalltalk", "meal_recommendation", "dessert_craving", "coffee_habit",
        "explanation_followup", "medication_food_question", "allergy_conflict",
        "product_question", "lab_followup", "menu_followup", "out_of_scope",
        "unknown_nutrition_related",
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


def fallback_intent_plan(message: str, target: str = "kendim") -> CureBotIntentPlan:
    text = str(message or "").casefold()
    resolved_target = "family" if target == "aile" else ("self" if target == "kendim" else "member")
    risk = ""
    if any(x in text for x in ("fındıklı baklava", "fındıklı tatlı", "yiyebilir miyim")):
        risk = message
    context = "unknown"
    intent = "unknown_nutrition_related"
    if any(x in text for x in ("kahvalt", "sabah")):
        context, intent = "breakfast", "meal_recommendation"
    elif any(x in text for x in ("akşam", "aksam", "öğün", "ogun")):
        context, intent = "dinner", "meal_recommendation"
    elif any(x in text for x in ("tatlı", "tatli")):
        context, intent = "dessert", "dessert_craving"
    elif "kahve" in text:
        context, intent = "coffee_pairing", "coffee_habit"
    elif any(x in text for x in ("hangi kriter", "neye göre", "neye gore", "önceki öner")):
        intent = "explanation_followup"
    if text.strip() in {"öner", "oner", "alternatif", "başka", "baska", "daha farklı", "daha farkli", "detay", "tarif"}:
        context, intent = "dessert", "dessert_craving"
    return CureBotIntentPlan(target=resolved_target, intent=intent, meal_context=context, risk_subject=risk, needs_safety_gate=bool(risk), reason="local privacy fallback")


def classify_intent_plan(message: str, conversation: list[dict] | None = None, target: str = "self", profile_names: list[str] | None = None, health_flags: dict | None = None) -> CureBotIntentPlan:
    # Deliberately local until an explicit provider/data-use approval exists.
    # The structured contract is ready for a future classifier without exporting user data.
    return fallback_intent_plan(message, target)


def plan_requires_safety_gate(plan: CureBotIntentPlan) -> bool:
    return bool(plan.needs_safety_gate or plan.intent in {"medication_food_question", "allergy_conflict", "lab_followup"})


def _natural_fallback(plan: CureBotIntentPlan) -> str:
    return {
        "breakfast": "Bugün pratik ve dengeli bir kahvaltı seçelim: yumurta veya yulafı, yanında sebze ve küçük bir meyve porsiyonuyla tamamlayabilirsin.",
        "dinner": "Akşam için ızgara bir protein, bol sebze ve ölçülü bir tahıl/ekmek eşliği iyi bir başlangıç olur. Evdeki malzemeleri söylersen bunu netleştirebilirim.",
        "dessert_craving": "Tatlı isteğini küçük bir porsiyon fırınlanmış elma, meyve-chia karışımı veya kuruyemişsiz uygun bir yoğurt alternatifiyle karşılayabilirsin.",
        "coffee_habit": "Kahveyi tamamen bırakman gerekmeyebilir; miktarı ve saatini gözlemle, yanında küçük ve dengeli bir atıştırmalık tercih et.",
        "explanation_followup": "Öneriyi profilindeki kısıtlar, öğünün dengesi ve isteğinin pratikliği birlikte düşünülerek hazırladım. İstersen hangi kısmı değiştirmek istediğini söyle.",
    }.get(plan.meal_context, "İsteğini profil bağlamında değerlendiriyorum. Birkaç güvenli ve pratik seçenek önerebilirim; istersen neyi özellikle sevdiğini de söyle.")


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
    if "**" not in text and not re.search(r"(?m)^\s*[-•]", text):
        sentences = [part.strip() for part in re.split(r"(?<=[.!?])\s+", text) if part.strip()]
        if len(sentences) > 1:
            text = sentences[0] + "\n\n" + "\n".join(f"- {sentence}" for sentence in sentences[1:3])
    return text.strip() or _natural_fallback(plan)


def generate_curebot_natural_answer(intent_plan: CureBotIntentPlan, snapshot, user_message: str, safety_context: str = "") -> str:
    flags = {
        "target_scope": snapshot.target_scope,
        "allergy_present": bool(snapshot.allergies),
        "disease_present": bool(snapshot.diseases),
        "medication_present": bool(snapshot.medications),
        "allergy_categories": list(snapshot.allergies)[:8],
        "disease_categories": list(snapshot.diseases)[:8],
        "medication_categories": list(snapshot.medications)[:8],
    }
    prompt = f"""You are CureBot, a warm Turkish nutrition decision-support assistant.
Return only the final Turkish answer to the user.
USER MESSAGE: {str(user_message)[:900]}
INTENT PLAN: {intent_plan.model_dump_json(exclude={"reason"})}
MINIMAL PROFILE FACTS: {json.dumps(flags, ensure_ascii=False)}
SAFETY CONTEXT: {safety_context[:500]}
RESPONSE VARIATION SEED: {datetime.now().minute}

Rules: sound natural and varied. Default to 60-110 words; only use 120-180 words if the user asks for detail, a recipe, or an explanation. Never write one long paragraph.
Use this Markdown structure: one short opening sentence, then 2-3 separate bullet options.
Each option must start with a short bold heading (**Başlık**) followed by 1-2 concise explanatory sentences.
End with one brief "Kısa not:" only when genuinely needed. Do not add a long disclaimer.
Do not use the user's name or any family member name. Do not mention internal plans, rules, scores or classifiers.
Avoid exaggerated words such as "harika", "en sağlıklısı" or "çok önemli". Do not repeat stock openings such as "İsteğinize uygun seçenekler".
If allergy flags are present, do not make nuts or nut milks the default first option; prefer nut-free fruit, baked apple/pear, chia or suitable yogurt alternatives. If a nut-derived option is mentioned, advise checking labels and cross-contamination.
Never begin with generic health disclaimers. Do not use the phrase 'kayıtlı alerjenleri dışarıda bırakan'.
Use a short safety note only at the end when clearly necessary. Do not invent unknown ingredients or medical facts.
"""
    try:
        response = invoke_with_model_fallback(prompt, temperature=0.65)
        answer = parse_llm_response(response).strip()
        return _concise_markdown(answer or _natural_fallback(intent_plan), intent_plan, snapshot)
    except Exception:
        return _natural_fallback(intent_plan)
