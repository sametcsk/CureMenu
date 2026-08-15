from src.curebot_intent import CureBotConversationContext, CureBotIntentPlan, ResolvedTurn
from src.models import AileUyesi, Cinsiyet, KullaniciProfili
from src.profile_context import resolve_profile_snapshot_from_profile
from src.quality.evidence import (
    SafetyFinding,
    carry_findings_without_new_evidence,
    coerce_finding,
    merge_finding_evidence,
    render_finding,
)
from src.quality.rule_engine import RuleEngine
from src.routers.chat import (
    CureBotResponseContext,
    _artifact_followup_decision,
    _explicit_input_safety_answer,
)


def _snapshot(*, allergy: str = "ingredient-x", target_id: str = "target-1"):
    profile = KullaniciProfili(ana_kullanici=AileUyesi(
        id=target_id,
        ad="Test Profile",
        yas=35,
        cinsiyet=Cinsiyet.KADIN,
        alerjiler=[allergy],
    ))
    return resolve_profile_snapshot_from_profile("account", profile, "kendim")


def _turn(*, object_label="ingredient-x", object_source="current_message", artifact="none"):
    return ResolvedTurn(
        turn_id="turn-1",
        conversation_id="conversation-1",
        target_profile_id="kendim",
        target_scope="self",
        target_resolution_source="message_self",
        intent="allergy_conflict" if artifact == "none" else "meal_followup",
        subject="food_suitability" if artifact == "none" else "artifact",
        object_label=object_label,
        object_type="food",
        object_resolution_source=object_source,
        artifact_reference=artifact,
    )


def test_profile_restriction_alone_is_not_confirmed_food_evidence():
    result = RuleEngine().check_rules(
        {"alerjiler": ["yer fıstığı"], "hastaliklar": []},
        "",
        [],
    )
    finding = next(item for item in result["evidence_findings"] if item["restriction_type"] == "allergy")
    assert finding["evidence_level"] == "UNKNOWN"
    assert result["confirmed_conflicts"] == []
    assert "eşleşme bulundu" not in render_finding(finding).casefold()


def test_structured_non_match_is_clear_but_not_declared_absolutely_safe():
    result = RuleEngine().check_rules(
        {"alerjiler": ["yer fıstığı"], "hastaliklar": []},
        "",
        ["domates"],
        structured_ingredients=True,
    )
    finding = next(item for item in result["evidence_findings"] if item["restriction_type"] == "allergy")
    rendered = render_finding(finding)
    assert finding["evidence_level"] == "CLEAR"
    assert "eşleşme görülmedi" in rendered
    assert "kesin güvenli" not in rendered.casefold()


def test_explicit_match_is_confirmed_with_matched_entity():
    result = RuleEngine().check_rules(
        {"alerjiler": ["yer fıstığı"], "hastaliklar": []},
        "yer fıstığı içeren ürün",
        ["yer fıstığı"],
    )
    finding = next(item for item in result["evidence_findings"] if item["evidence_level"] == "CONFIRMED")
    assert finding["matched_ingredient"]
    assert "eşleşme bulundu" in render_finding(finding)


def test_different_food_does_not_confirm_registered_restriction():
    result = RuleEngine().check_rules(
        {"alerjiler": ["yer fıstığı"], "hastaliklar": []},
        "elma",
        ["elma"],
        structured_ingredients=True,
    )
    assert not any(item["evidence_level"] == "CONFIRMED" for item in result["evidence_findings"])


def test_legacy_finding_without_level_is_unknown_not_confirmed():
    finding = coerce_finding({
        "restriction_type": "allergy",
        "restriction_identifier": "ingredient-x",
        "explanation": "legacy text",
    })
    assert finding.evidence_level == "UNKNOWN"
    assert "eşleşme bulundu" not in render_finding(finding).casefold()


def test_no_new_evidence_cannot_upgrade_inferred_finding():
    previous = SafetyFinding(
        restriction_type="allergy",
        restriction_identifier="ingredient-x",
        evidence_level="INFERRED-LIKELY",
        evidence_source="category_inference",
        matched_ingredient="product category",
        target_profile_id="kendim",
    )
    attempted_upgrade = previous.model_copy(update={
        "evidence_level": "CONFIRMED",
        "new_evidence_this_turn": False,
    })
    merged = merge_finding_evidence(previous, attempted_upgrade)
    assert merged.evidence_level == "INFERRED-LIKELY"
    assert merged.inherited_from_previous_turn is True


def test_traceable_new_evidence_can_upgrade_inferred_finding():
    previous = SafetyFinding(
        restriction_type="allergy",
        restriction_identifier="ingredient-x",
        evidence_level="INFERRED-LIKELY",
        evidence_source="category_inference",
        matched_ingredient="product category",
        target_profile_id="kendim",
    )
    current = previous.model_copy(update={
        "evidence_level": "CONFIRMED",
        "evidence_source": "explicit_ingredient_list",
        "matched_ingredient": "ingredient-x",
        "input_span": "ingredient-x",
        "new_evidence_this_turn": True,
    })
    assert merge_finding_evidence(previous, current).evidence_level == "CONFIRMED"


def test_artifact_followup_preserves_each_finding_level_without_new_evidence():
    findings = (
        SafetyFinding(
            restriction_type="allergy", restriction_identifier="restriction-a",
            evidence_level="CONFIRMED", evidence_source="ingredient_list",
            matched_ingredient="entity-a", target_profile_id="kendim",
            artifact_reference="menu_analysis",
        ),
        SafetyFinding(
            restriction_type="allergy", restriction_identifier="restriction-b",
            evidence_level="INFERRED-LIKELY", evidence_source="category_inference",
            matched_ingredient="entity-b", target_profile_id="kendim",
            artifact_reference="menu_analysis",
        ),
    )
    context = CureBotResponseContext(
        turn=_turn(object_label="", object_source="none", artifact="menu_analysis"),
        snapshot=_snapshot(),
        plan=CureBotIntentPlan(intent="meal_followup", is_followup=True),
        conversation=CureBotConversationContext(last_artifact_reference="menu_analysis"),
        user_message="Daha güvenli bir seçenek nasıl buluruz?",
        findings=findings,
    )
    decision = _artifact_followup_decision(context)
    assert decision is not None
    assert [item.evidence_level for item in decision.findings] == ["CONFIRMED", "INFERRED-LIKELY"]
    assert all(item.inherited_from_previous_turn for item in decision.findings)
    inferred_line = render_finding(decision.findings[1])
    assert "risk olabilir" in inferred_line
    assert "eşleşme bulundu" not in inferred_line


def test_object_dependent_responder_consumes_inherited_canonical_object():
    snapshot = _snapshot(allergy="yer fıstığı")
    turn = _turn(object_label="yer fıstığı", object_source="previous_turn")
    context = CureBotResponseContext(
        turn=turn,
        snapshot=snapshot,
        plan=CureBotIntentPlan(intent="allergy_conflict", needs_safety_gate=True),
        conversation=CureBotConversationContext(last_object="yer fıstığı", last_object_type="food"),
        user_message="Benim için?",
    )
    decision = _explicit_input_safety_answer(context)
    assert context.response_input == turn.object_label
    assert decision is not None
    assert any(item.matched_ingredient for item in decision.findings if item.evidence_level == "CONFIRMED")
    assert "yer fıstığı" in decision.answer.casefold()
    assert all(item.target_profile_id == snapshot.target_key for item in decision.findings)


def test_carrying_findings_never_marks_new_evidence():
    finding = SafetyFinding(
        restriction_type="allergy", restriction_identifier="restriction-a",
        evidence_level="UNKNOWN", evidence_source="missing_ingredients",
        target_profile_id="kendim",
    )
    carried = carry_findings_without_new_evidence([finding])[0]
    assert carried.evidence_level == "UNKNOWN"
    assert carried.inherited_from_previous_turn is True
    assert carried.new_evidence_this_turn is False
