from types import SimpleNamespace

from src.curebot_intent import CureBotIntentPlan, _concise_markdown, classify_intent_plan


def test_local_intent_plan_does_not_export_identity_or_history():
    plan = classify_intent_plan(
        "Bu öneriyi hangi kriterlere göre hazırladın?",
        [{"role": "user", "content": "Gizli raw mesaj"}, {"intent": "meal_recommendation"}],
        "member",
        ["Züleyha"],
        {"allergy_present": True, "medication_present": True, "disease_present": False},
    )

    assert isinstance(plan, CureBotIntentPlan)
    assert plan.privacy_mode == "minimal"


def test_natural_answer_postprocessor_enforces_markdown_and_nut_safety():
    plan = CureBotIntentPlan(intent="dessert_craving", meal_context="dessert")
    snapshot = SimpleNamespace(allergies=("fındık",))
    answer = "İki harika önerim var. Badem sütüyle uzun bir tarif. Ceviz de ekleyebilirsin."
    cleaned = _concise_markdown(answer, plan, snapshot)
    assert "badem sütü" not in cleaned.casefold()
    assert "ceviz" not in cleaned.casefold()
    assert "iki harika" not in cleaned.casefold()
