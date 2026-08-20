"""Central food-constraint resolution invariants (INVARIANT 1-6) and cross-feature
consistency. Health condition names must never become forbidden ingredients; a raw
allergy string becomes a food constraint only when the deterministic registry /
catalog resolves it; unresolved free-text is never invented into a forbidden food.
No real user/profile names are hard-coded in logic.
"""
from src.models import AileUyesi, Cinsiyet, KullaniciProfili
from src.profile_context import resolve_profile_snapshot_from_profile
from src.quality.food_constraints import (
    resolve_food_constraints,
    resolve_food_constraints_from_snapshot,
)
from src.quality.rule_engine import profile_hard_avoid_ingredients


def test_inv1_disease_name_never_in_hard_avoid():
    c = resolve_food_constraints({"hastaliklar": ["diyabet", "hipertansiyon", "böbrek hastalığı"], "alerjiler": []})
    for label in ("diyabet", "hipertansiyon", "böbrek hastalığı"):
        assert label not in c.hard_avoid_ingredients
        assert label in c.profile_health_labels  # kept as context, not a food


def test_inv2_raw_allergy_only_when_registry_resolves():
    # Lactose intolerance resolves (via registry) to dairy foods; the literal label
    # itself is not added as an ingredient.
    c = resolve_food_constraints({"hastaliklar": [], "alerjiler": ["laktoz intoleransı"]})
    assert "peynir" in c.hard_avoid_ingredients and "süt" in c.hard_avoid_ingredients
    assert "laktoz intoleransı" not in c.hard_avoid_ingredients


def test_inv3_health_labels_are_not_ingredients():
    c = resolve_food_constraints({"hastaliklar": ["diyabet"], "alerjiler": []})
    assert set(c.profile_health_labels).isdisjoint(set(c.hard_avoid_ingredients))


def test_inv4_block_terms_carry_deterministic_provenance():
    c = resolve_food_constraints({"hastaliklar": [], "alerjiler": ["yer fıstığı"]})
    assert c.hard_avoid_ingredients
    assert any(e.get("source_type") in {"deterministic_registry", "ingredient_catalog"} for e in c.evidence)


def test_inv5_unresolved_free_text_is_not_a_forbidden_food():
    c = resolve_food_constraints({"hastaliklar": [], "alerjiler": ["zzz bilinmeyen madde"]})
    assert "zzz bilinmeyen madde" in c.unresolved_profile_items
    assert "zzz bilinmeyen madde" not in c.hard_avoid_ingredients


def test_inv6_single_source_wrapper_delegates():
    profile = {"hastaliklar": ["diyabet"], "alerjiler": ["yer fıstığı", "laktoz intoleransı"]}
    assert profile_hard_avoid_ingredients(profile) == list(resolve_food_constraints(profile).hard_avoid_ingredients)


def test_cross_feature_consistency_same_snapshot_same_constraints():
    # The same snapshot yields the same hard-avoid set no matter which feature asks.
    member = AileUyesi(id="m1", ad="Uye", yas=10, cinsiyet=Cinsiyet.ERKEK, yakinlik="ogul",
                       alerjiler=["yer fıstığı"])
    owner = AileUyesi(id="own", ad="Sahip", yas=40, cinsiyet=Cinsiyet.KADIN, alerjiler=["laktoz intoleransı"])
    profile = KullaniciProfili(ana_kullanici=owner, aile_uyeleri=[member])
    snap = resolve_profile_snapshot_from_profile("acct", profile, "aile")
    a = resolve_food_constraints_from_snapshot(snap).hard_avoid_ingredients
    b = resolve_food_constraints_from_snapshot(snap).hard_avoid_ingredients
    assert a == b
    # union of both members' resolved food terms (peanut + dairy), no disease labels
    joined = " ".join(a)
    assert "yer fıstığı" in joined and "peynir" in joined
