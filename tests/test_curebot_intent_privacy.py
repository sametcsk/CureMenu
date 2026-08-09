import json
from types import SimpleNamespace

from src.curebot_intent import (
    CureBotConversationContext,
    CureBotIntentPlan,
    _concise_markdown,
    classify_intent_plan,
    generate_curebot_natural_answer,
    plan_curebot_semantically,
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


def test_natural_answer_postprocessor_formats_plain_meal_options_as_bold_bullets():
    plan = CureBotIntentPlan(intent="meal_recommendation", meal_context="dinner")
    snapshot = SimpleNamespace(allergies=())
    answer = (
        "Bu akşam hafif ve pratik bir tabak seçebilirsin.\n\n"
        "Fırında tavuk ve sebze: Derisiz tavuk ve mevsim sebzeleriyle hazırlanır.\n"
        "Izgara balık ve sade salata: Sosu ayrı istemek daha kontrollü bir seçim sağlar.\n"
        "Zeytinyağlı taze fasulye: Porsiyon kontrollü bir ev yemeği alternatifidir."
    )

    cleaned = _concise_markdown(answer, plan, snapshot)

    assert "- **Fırında tavuk ve sebze:**" in cleaned
    assert "- **Izgara balık ve sade salata:**" in cleaned
    assert "- **Zeytinyağlı taze fasulye:**" in cleaned


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


def test_semantic_triage_uses_minimal_context_and_validated_json(monkeypatch):
    captured = {}

    def fake_invoke(prompt, **_kwargs):
        captured["prompt"] = prompt
        return """```json
        {
          "intent": "meal_followup",
          "meal_context": "dinner",
          "is_profile_declaration": false,
          "is_followup": true,
          "needs_safety_gate": false,
          "answer_style": "practical",
          "confidence": 0.94
        }
        ```"""

    monkeypatch.setattr("src.curebot_intent.invoke_with_model_fallback", fake_invoke)
    context = CureBotConversationContext(
        last_intent="meal_recommendation",
        last_meal_context="dinner",
        last_answer_type="practical",
        last_target_scope="member",
        has_previous_turn=True,
    )
    plan = plan_curebot_semantically(
        "Mert için peki ekmek ne olsun? Telefon 0532 111 22 33",
        context,
        "member",
        ["Mert", "Ayşe"],
        {"allergy_present": True, "medication_present": False, "disease_present": True},
    )

    prompt = captured["prompt"]
    assert plan.intent == "meal_followup"
    assert plan.target == "member"
    assert plan.privacy_mode == "minimal"
    assert "Mert" not in prompt
    assert "Ayşe" not in prompt
    assert "0532 111 22 33" not in prompt
    assert "Gizli raw mesaj" not in prompt
    assert '"allergy_present": true' in prompt
    assert '"last_meal_context": "dinner"' in prompt


def test_semantic_triage_cannot_disable_local_safety_gate(monkeypatch):
    monkeypatch.setattr(
        "src.curebot_intent.invoke_with_model_fallback",
        lambda *_args, **_kwargs: json.dumps({
            "intent": "unknown_nutrition_related",
            "meal_context": "unknown",
            "is_profile_declaration": False,
            "is_followup": False,
            "needs_safety_gate": False,
            "answer_style": "practical",
            "confidence": 0.7,
        }),
    )

    plan = plan_curebot_semantically("Fındıklı baklava yiyebilir miyim?", target="self")

    assert plan.needs_safety_gate is True
    assert plan.risk_subject == "explicit_food_request"


def test_semantic_triage_provider_failure_uses_local_fallback(monkeypatch):
    monkeypatch.setattr(
        "src.curebot_intent.invoke_with_model_fallback",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(TimeoutError("provider timeout")),
    )

    plan = plan_curebot_semantically(
        "Biraz bunaldım, hiçbir şey yiyemez gibiyim.",
        target="self",
    )

    assert plan.intent == "emotional_support"
    assert plan.reason == "local privacy fallback"
