"""Generic recommendation vs concrete food-suitability intent.

A generic recommendation ("ne önerirsin?") — even one that inherits a prior food
object through follow-up continuity — must NOT trigger a hard conflict response.
Profile restrictions become a candidate-generation filter instead. A concrete
food-suitability question ("... uygun mu?") still hard-conflicts on a real match.

No person / food / time is hard-coded in production logic; the fixtures below use
example values only.
"""
from src.curebot_intent import (
    CureBotConversationContext,
    CureBotIntentPlan,
    ResolvedTurn,
    fallback_intent_plan,
)
from src.models import AileUyesi, Cinsiyet, KullaniciProfili
from src.profile_context import resolve_profile_snapshot_from_profile
from src.routers.chat import CureBotResponseContext, _explicit_input_safety_answer


def _member_snapshot(allergies):
    member = AileUyesi(id="m1", ad="Deniz", yas=12, cinsiyet=Cinsiyet.ERKEK, yakinlik="ogul", alerjiler=allergies)
    profile = KullaniciProfili(
        ana_kullanici=AileUyesi(id="own", ad="Veli", yas=40, cinsiyet=Cinsiyet.KADIN),
        aile_uyeleri=[member],
    )
    return resolve_profile_snapshot_from_profile("acct", profile, "m1")


def _context(snapshot, plan, *, object_label, object_source, user_message, intent):
    turn = ResolvedTurn(
        target_profile_id=snapshot.target_key,
        target_scope=snapshot.target_scope,
        target_resolution_source="message_relationship",
        intent=intent,
        subject="food_suitability",
        object_label=object_label,
        object_type="food",
        object_resolution_source=object_source,
    )
    return CureBotResponseContext(
        turn=turn, snapshot=snapshot, plan=plan,
        conversation=CureBotConversationContext(), user_message=user_message,
    )


def test_generic_recommendation_followup_does_not_hard_conflict_on_inherited_object():
    snapshot = _member_snapshot(["yer fıstığı"])
    # Follow-up recommendation: no explicit suitability question this turn.
    plan = CureBotIntentPlan(intent="meal_followup", needs_safety_gate=False, risk_subject="")
    context = _context(
        snapshot, plan,
        object_label="yer fıstığı ezmesi",  # inherited from a previous suitability turn
        object_source="previous_turn",
        user_message="peki ne önerirsin?",
        intent="meal_followup",
    )
    assert _explicit_input_safety_answer(context) is None  # filter, not hard block


def test_generic_recommendation_first_turn_no_hard_conflict():
    snapshot = _member_snapshot(["yer fıstığı"])
    plan = CureBotIntentPlan(intent="meal_recommendation", needs_safety_gate=False, risk_subject="")
    context = _context(
        snapshot, plan,
        object_label="", object_source="none",
        user_message="oğluma ne önerirsin?",
        intent="meal_recommendation",
    )
    assert _explicit_input_safety_answer(context) is None


def test_concrete_food_suitability_still_hard_conflicts_on_explicit_match():
    snapshot = _member_snapshot(["yer fıstığı"])
    plan = CureBotIntentPlan(intent="meal_recommendation", needs_safety_gate=True, risk_subject="explicit_food_request")
    context = _context(
        snapshot, plan,
        object_label="", object_source="current_message",
        user_message="oğluma yer fıstığı ezmesi uygun mu?",
        intent="meal_recommendation",
    )
    decision = _explicit_input_safety_answer(context)
    assert decision is not None
    assert "önermiyorum" in decision.answer.lower()
    assert any(finding.evidence_level == "CONFIRMED" for finding in decision.findings)


def test_followup_recommendation_preserves_meal_context():
    previous = CureBotConversationContext(last_meal_context="dinner", has_previous_turn=True)
    plan = fallback_intent_plan("peki ne önerirsin?", "kendim", previous)
    assert plan.intent == "meal_followup"
    assert plan.meal_context == "dinner"  # meal/time context safely inherited
    assert plan.needs_safety_gate is False  # a recommendation follow-up is not a suitability gate
