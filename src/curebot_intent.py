"""Structured, bounded intent planning for CureBot conversation routing."""
import json
from typing import Literal

from pydantic import BaseModel, Field



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


def fallback_intent_plan(message: str, target: str = "self") -> CureBotIntentPlan:
    text = str(message or "").casefold()
    resolved_target = "family" if any(x in text for x in ("bize", "hepimize", "ailece", "tüm aile")) else ("member" if any(x in text for x in ("annem", "anne")) else ("self" if target == "kendim" else "member"))
    risk = ""
    if any(x in text for x in ("fındıklı baklava", "fındıklı tatlı", "yiyebilir miyim")):
        risk = message
    return CureBotIntentPlan(target=resolved_target, risk_subject=risk, needs_safety_gate=bool(risk), reason="classifier fallback")


def classify_intent_plan(message: str, conversation: list[dict] | None = None, target: str = "self", profile_names: list[str] | None = None, health_flags: dict | None = None) -> CureBotIntentPlan:
    # Deliberately local until an explicit provider/data-use approval exists.
    # The structured contract is ready for a future classifier without exporting user data.
    return fallback_intent_plan(message, target)


def plan_requires_safety_gate(plan: CureBotIntentPlan) -> bool:
    return bool(plan.needs_safety_gate or plan.intent in {"medication_food_question", "allergy_conflict", "lab_followup"})
