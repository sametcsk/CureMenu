from types import SimpleNamespace

from src.curebot_intent import (
    CureBotConversationContext,
    CureBotIntentPlan,
    _concise_markdown,
    classify_intent_plan,
    generate_curebot_natural_answer,
)


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


def test_short_followup_uses_only_local_context_labels():
    context = CureBotConversationContext(
        last_intent="meal_recommendation",
        last_meal_context="dinner",
        last_answer_type="practical",
        last_target_scope="family",
        has_previous_turn=True,
    )

    plan = classify_intent_plan("Peki ekmek olarak ne koyalım sofraya?", context.model_dump(), "family")

    assert plan.intent == "meal_followup"
    assert plan.meal_context == "dinner"
    assert plan.target == "family"
    assert plan.is_followup is True


def test_domain_intents_cover_medication_food_and_nutrition_overwhelm():
    medication = classify_intent_plan("Metformin ile birlikte greyfurt suyu içsem sakıncalı mı?", target="self")
    overwhelmed = classify_intent_plan("Biraz bunaldım, hiçbir şey yiyemez gibiyim; ne yapmalıyım?", target="self")

    assert medication.intent == "medication_food_question"
    assert medication.needs_safety_gate is True
    assert overwhelmed.intent == "emotional_support"
    assert overwhelmed.needs_safety_gate is False


def test_natural_answer_prompt_redacts_identity_phone_and_raw_history(monkeypatch):
    captured = {}

    def fake_invoke(prompt, **_kwargs):
        captured["prompt"] = prompt
        return "Kısa bir başlangıç yapalım.\n\n- **Dengeli tabak:** Sebze ve uygun bir protein seçebilirsin."

    monkeypatch.setattr("src.curebot_intent.invoke_with_model_fallback", fake_invoke)
    snapshot = SimpleNamespace(
        target_scope="member",
        target_name="Mert",
        allergies=("kabuklu deniz ürünleri",),
        diseases=("çölyak",),
        medications=(),
    )
    plan = CureBotIntentPlan(intent="meal_recommendation", target="member", meal_context="dinner")
    context = CureBotConversationContext(
        last_intent="meal_recommendation",
        last_meal_context="dinner",
        last_answer_type="practical",
        last_target_scope="member",
        has_previous_turn=True,
    )

    generate_curebot_natural_answer(
        plan,
        snapshot,
        "Mert için akşam yemeği öner, telefonum 0532 111 22 33",
        conversation_context=context,
    )

    prompt = captured["prompt"]
    assert "Mert" not in prompt
    assert "0532 111 22 33" not in prompt
    assert "Gizli raw mesaj" not in prompt
    assert '"last_intent": "meal_recommendation"' in prompt
    assert '"privacy_mode":"minimal"' in prompt
