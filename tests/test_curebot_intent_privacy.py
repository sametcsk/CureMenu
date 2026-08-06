from src.curebot_intent import CureBotIntentPlan, classify_intent_plan


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
