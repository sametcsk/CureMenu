import json
from types import SimpleNamespace

from src.curebot_intent import (
    CureBotConversationContext,
    CureBotIntentPlan,
    _concise_markdown,
    classify_intent_plan,
    extract_suggestion_topics,
    generate_curebot_natural_answer,
    natural_fallback_answer,
    plan_curebot_semantically,
    semantic_continuity_labels,
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


def test_suggestion_topics_extract_only_compact_meal_labels():
    answer = (
        "Bu akşam farklı seçeneklere bakalım.\n\n"
        "- **Fırında sebzeli tavuk:** Hafif bir ana öğün olabilir.\n"
        "- **Mercimekli kabak yemeği:** Bitkisel bir alternatif sunar.\n"
        "> **Kısa not:** Porsiyonu ihtiyacına göre ayarla."
    )

    assert extract_suggestion_topics(answer) == (
        "Fırında sebzeli tavuk",
        "Mercimekli kabak yemeği",
    )


def test_short_followup_uses_only_local_context_labels():
    context = CureBotConversationContext(
        last_intent="meal_recommendation",
        last_meal_context="dinner",
        last_answer_type="practical",
        last_target_scope="family",
        has_previous_turn=True,
        recent_suggestion_topics=("Fırında tavuk", "Izgara balık"),
    )

    plan = classify_intent_plan("Peki ekmek olarak ne koyalım sofraya?", context.model_dump(), "family")

    assert plan.intent == "meal_followup"
    assert plan.meal_context == "dinner"
    assert plan.target == "family"
    assert plan.is_followup is True


def test_semantic_continuity_preserves_artifact_without_raw_history():
    previous = CureBotConversationContext(
        last_intent="menu_followup",
        last_subject="artifact",
        last_object="menu_analysis",
        last_artifact_reference="menu_analysis",
        last_target_scope="member",
        has_previous_turn=True,
    )
    plan = classify_intent_plan(
        "Peki onun için daha güvenli ne seçebiliriz?",
        previous.model_dump(),
        "member",
    )
    labels = semantic_continuity_labels(plan, "Peki onun için daha güvenli ne seçebiliriz?", previous)

    assert plan.intent == "meal_followup"
    assert labels == {
        "last_subject": "artifact",
        "last_object": "",
        "last_object_type": "unknown",
        "last_artifact_reference": "menu_analysis",
    }


def test_implicit_first_person_hunger_is_a_new_meal_request_not_stale_followup():
    previous = CureBotConversationContext(
        last_intent="menu_followup",
        last_subject="artifact",
        last_object="menu_analysis",
        last_artifact_reference="menu_analysis",
        last_target_scope="member",
        has_previous_turn=True,
    )

    plan = classify_intent_plan("çok acıktım ne yemeliyim", previous.model_dump(), "self")

    assert plan.intent == "meal_recommendation"
    assert plan.is_followup is False


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
        notes=("Mantar sevmiyorum, telefon 0532 111 22 33",),
    )
    plan = CureBotIntentPlan(intent="meal_recommendation", target="member", meal_context="dinner")
    context = CureBotConversationContext(
        last_intent="meal_recommendation",
        last_meal_context="dinner",
        last_answer_type="practical",
        last_target_scope="member",
        has_previous_turn=True,
        recent_suggestion_topics=("Fırında tavuk", "Izgara balık"),
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
    assert "Mantar sevmiyorum" in prompt
    assert "[REDACTED_PHONE]" in prompt
    assert "Gizli raw mesaj" not in prompt
    assert '"last_intent": "meal_recommendation"' in prompt
    assert '"recent_suggestion_topics": ["Fırında tavuk", "Izgara balık"]' in prompt
    assert '"privacy_mode":"minimal"' in prompt


def test_natural_answer_formats_stacked_bold_meals_and_removes_generic_medication_note(monkeypatch):
    monkeypatch.setattr(
        "src.curebot_intent.invoke_with_model_fallback",
        lambda *_args, **_kwargs: SimpleNamespace(content=(
            "Akşam için üç seçenek:\n\n"
            "**Zeytinyağlı taze fasulye:**\nHafif bir sebze yemeğidir.\n"
            "**Izgara balık:**\nYanına sade salata eklenebilir.\n"
            "Kısa not: Metformin kullanırken lifli besinlere ağırlık vermek faydalıdır."
        )),
    )
    snapshot = SimpleNamespace(
        target_scope="self",
        target_name="Test",
        allergies=("fındık",),
        diseases=("insülin direnci",),
        medications=("metformin",),
        notes=(),
    )
    answer = generate_curebot_natural_answer(
        CureBotIntentPlan(intent="meal_recommendation", meal_context="dinner"),
        snapshot,
        "Bu akşam ne yiyebilirim?",
    )

    assert "- **Zeytinyağlı taze fasulye:** Hafif bir sebze yemeğidir." in answer
    assert "- **Izgara balık:** Yanına sade salata eklenebilir." in answer
    assert "Metformin kullanırken" not in answer


def test_semantic_triage_uses_minimal_context_and_validated_json(monkeypatch):
    captured = {}

    def fake_invoke(prompt, **_kwargs):
        captured["prompt"] = prompt
        return SimpleNamespace(content="""```json
        {
          "intent": "meal_followup",
          "meal_context": "dinner",
          "is_profile_declaration": false,
          "is_followup": true,
          "needs_safety_gate": false,
          "answer_style": "practical",
          "confidence": 0.94
        }
        ```""")

    monkeypatch.setattr("src.curebot_intent.invoke_with_model_fallback", fake_invoke)
    context = CureBotConversationContext(
        last_intent="meal_recommendation",
        last_meal_context="dinner",
        last_answer_type="practical",
        last_target_scope="member",
        has_previous_turn=True,
        recent_suggestion_topics=("Gizli önceki yemek",),
    )
    plan = plan_curebot_semantically(
        "Mert için bunu nasıl ilerletelim? Telefon 0532 111 22 33",
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
    assert "Gizli önceki yemek" not in prompt


def test_obvious_meal_bypasses_triage_but_contextual_followup_uses_it(monkeypatch):
    calls = []

    def semantic_followup(prompt, **_kwargs):
        calls.append(prompt)
        return SimpleNamespace(content=json.dumps({
            "intent": "meal_followup",
            "meal_context": "dinner",
            "is_profile_declaration": False,
            "is_followup": True,
            "needs_safety_gate": False,
            "answer_style": "practical",
            "confidence": 0.93,
        }))

    monkeypatch.setattr(
        "src.curebot_intent.invoke_with_model_fallback",
        semantic_followup,
    )
    dinner = plan_curebot_semantically("Bu akşam hafif ve pratik ne yiyebilirim?", target="self")
    followup = plan_curebot_semantically(
        "öner işete bana bir şeyler",
        CureBotConversationContext(
            last_intent="meal_recommendation",
            last_meal_context="dinner",
            last_answer_type="practical",
            last_target_scope="self",
            has_previous_turn=True,
        ),
        target="self",
    )

    assert dinner.intent == "meal_recommendation"
    assert dinner.meal_context == "dinner"
    assert followup.intent == "meal_followup"
    assert followup.meal_context == "dinner"
    assert len(calls) == 1


def test_disliked_ingredient_followup_preserves_previous_meal_context(monkeypatch):
    monkeypatch.setattr(
        "src.curebot_intent.invoke_with_model_fallback",
        lambda *_args, **_kwargs: SimpleNamespace(content=json.dumps({
            "intent": "meal_followup",
            "meal_context": "unknown",
            "is_profile_declaration": False,
            "is_followup": True,
            "needs_safety_gate": False,
            "answer_style": "practical",
            "confidence": 0.95,
        })),
    )
    plan = plan_curebot_semantically(
        "Çökelek sevmiyorum, daha güzel bir şey öner",
        CureBotConversationContext(
            last_intent="meal_recommendation",
            last_meal_context="breakfast",
            last_answer_type="practical",
            last_target_scope="family",
            has_previous_turn=True,
        ),
        target="family",
    )

    assert plan.intent == "meal_followup"
    assert plan.meal_context == "breakfast"


def test_unknown_new_topic_does_not_inherit_previous_meal_in_fallback():
    context = CureBotConversationContext(
        last_intent="meal_recommendation",
        last_meal_context="dinner",
        last_answer_type="practical",
        last_target_scope="self",
        has_previous_turn=True,
    )

    answer = natural_fallback_answer(
        CureBotIntentPlan(intent="unknown_nutrition_related", meal_context="unknown"),
        conversation_context=context,
    )

    assert "Fırında tavuk" not in answer
    assert "Izgara balık" not in answer
    assert "Ne tür bir öğün" in answer


def test_meal_followup_can_inherit_previous_meal_in_fallback():
    context = CureBotConversationContext(
        last_intent="meal_recommendation",
        last_meal_context="dinner",
        last_answer_type="practical",
        last_target_scope="self",
        has_previous_turn=True,
    )

    answer = natural_fallback_answer(
        CureBotIntentPlan(intent="meal_followup", is_followup=True),
        conversation_context=context,
    )

    assert any(meal in answer for meal in ("Fırında tavuk", "Izgara balık", "mercimek çorbası"))


def test_natural_answer_removes_unsupported_medical_and_macro_claims(monkeypatch):
    monkeypatch.setattr(
        "src.curebot_intent.invoke_with_model_fallback",
        lambda *_args, **_kwargs: SimpleNamespace(content=(
            "Akşam için iki seçenek:\n\n"
            "- **Somon:** Metforminin etkisini destekler ve kolesterol seviyelerini dengeler. "
            "(Tahmini enerji ve makro besin değerleri: 400 kcal, 30g protein)\n"
            "- **Enginar:** Karaciğer fonksiyonlarını destekleyen sebze ağırlıklı bir tabaktır."
        )),
    )
    snapshot = SimpleNamespace(
        target_scope="self",
        target_name="Test",
        allergies=(),
        diseases=("insülin direnci",),
        medications=("metformin",),
        notes=(),
    )

    answer = generate_curebot_natural_answer(
        CureBotIntentPlan(intent="meal_recommendation", meal_context="dinner"),
        snapshot,
        "Akşam ne yiyebilirim?",
    )

    normalized = answer.casefold()
    assert "metforminin etkisini" not in normalized
    assert "kolesterol seviyelerini deng" not in normalized
    assert "karaciğer fonksiyonlarını" not in normalized
    assert "400 kcal" not in normalized


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
