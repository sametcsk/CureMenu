"""Constraint-aware weekly-plan generation + bounded repair loop.

The plan generator must treat the profile's recorded restrictions (union for
multi/family) as hard constraints; an unsafe draft is repaired at most twice with
the concrete deterministic rejection reasons, and a plan that never passes safety
is blocked (422) — the unsafe draft is NEVER shown and the safety gate is NEVER
weakened. Example names/foods are fixtures only.
"""
from unittest.mock import patch

from test_api import login_with_profile


def _plan(summary, breakfast_ings):
    return {
        "days": [{
            "day": "Pazartesi", "breakfast": "Kahvaltı", "lunch": "Sebze çorbası",
            "dinner": "Izgara tavuk", "snacks": [], "notes": [],
            "meal_details": {
                "breakfast": {"name": "Kahvaltı", "ingredients": breakfast_ings},
                "lunch": {"name": "Sebze çorbası", "ingredients": ["havuç", "kabak"]},
                "dinner": {"name": "Izgara tavuk", "ingredients": ["tavuk", "brokoli"]},
            },
        }],
        "summary": summary, "warnings": [], "confidence": {},
    }


UNSAFE = _plan("Sütlü taslak", ["yoğurt", "elma"])           # milk -> blocked
SAFE = _plan("Güvenli taslak", ["badem sütü", "chia", "elma"])  # no milk


@patch("src.routers.tools.hafizadakini_getir", return_value=[])
@patch("src.routers.tools.haftalik_plan_olustur")
def test_bounded_repair_two_attempts_then_safe(mock_plan, mock_hafiza, client):
    login_with_profile(client, "5556000001", "Repair Two", alerjiler=["inek sütü proteini"])
    mock_plan.side_effect = [UNSAFE, UNSAFE, SAFE]  # 2 repairs, then safe
    res = client.post("/api/weekly-plan", json={"kimin_icin": "kendim"})
    assert res.status_code == 200
    assert res.json()["plan"]["summary"] == "Güvenli taslak"
    assert mock_plan.call_count == 3


@patch("src.routers.tools.hafizadakini_getir", return_value=[])
@patch("src.routers.tools.haftalik_plan_olustur")
def test_all_repairs_unsafe_blocks_and_never_shows_draft(mock_plan, mock_hafiza, client):
    login_with_profile(client, "5556000002", "Repair Block", alerjiler=["inek sütü proteini"])
    mock_plan.side_effect = [UNSAFE, UNSAFE, UNSAFE]  # initial + 2 repairs, all unsafe
    res = client.post("/api/weekly-plan", json={"kimin_icin": "kendim"})
    assert res.status_code == 422
    assert res.json()["error"]["code"] == "PLAN_SAFETY_BLOCKED"
    assert "Sütlü taslak" not in res.text  # unsafe draft never leaks
    assert mock_plan.call_count == 3


def _add_member(client, ad, yakinlik, alerjiler=None):
    client.post("/api/family/add", json={
        "ad": ad, "yas": 9, "cinsiyet": "erkek", "yakinlik": yakinlik,
        "alerjiler": alerjiler or [], "hastaliklar": [], "ilaclar": [],
    })


def test_hard_avoid_terms_are_foods_not_disease_names():
    from src.quality.rule_engine import profile_hard_avoid_ingredients
    terms = profile_hard_avoid_ingredients({"alerjiler": [], "hastaliklar": ["diyabet", "hipertansiyon"]})
    # Raw disease names must NEVER be treated as forbidden ingredients.
    assert "diyabet" not in terms and "hipertansiyon" not in terms


def test_lactose_intolerance_yields_dairy_food_terms():
    from src.quality.rule_engine import profile_hard_avoid_ingredients
    # The deterministic registry classifies lactose intolerance under the allergy
    # check field; the helper faithfully mirrors that (no new mapping invented).
    terms = " ".join(profile_hard_avoid_ingredients({"alerjiler": ["laktoz intoleransı"], "hastaliklar": []}))
    assert "peynir" in terms and "süt" in terms  # cheese/milk come from the deterministic catalog


@patch("src.routers.tools.hafizadakini_getir", return_value=[])
@patch("src.routers.tools.haftalik_plan_olustur")
def test_lactose_family_plan_repairs_cheese_then_safe(mock_plan, mock_hafiza, client):
    # Real user scenario: a family member is lactose-intolerant; a draft with cheese
    # is blocked, then a bounded repair returns a safe plan (200). Safety unchanged.
    # Lactose intolerance is recorded in the allergy-check field (registry classifies
    # it there); the deterministic layer then blocks cheese/dairy.
    login_with_profile(client, "5556000005", "Lactose Owner", alerjiler=["laktoz intoleransı"])
    cheese = _plan("Peynirli taslak", ["peynir", "domates"])
    safe = _plan("Sütsüz taslak", ["zeytin", "domates", "salatalık"])
    mock_plan.side_effect = [cheese, safe]
    res = client.post("/api/weekly-plan", json={"kimin_icin": "kendim"})
    assert res.status_code == 200
    assert res.json()["plan"]["summary"] == "Sütsüz taslak"


@patch("src.routers.tools.hafizadakini_getir", return_value=[])
@patch("src.routers.tools.haftalik_plan_olustur")
def test_family_plan_enforces_union_restriction_of_selected_members(mock_plan, mock_hafiza, client):
    # Owner has no allergy; the child does. A single common family plan that uses
    # milk must be blocked because the union includes the child's milk allergy.
    login_with_profile(client, "5556000003", "Family Union")
    _add_member(client, "Cocuk", "ogul", alerjiler=["inek sütü proteini"])
    mock_plan.side_effect = [UNSAFE, UNSAFE, UNSAFE]
    res = client.post("/api/weekly-plan", json={"kimin_icin": "aile"})
    assert res.status_code == 422  # child's restriction (via union) enforced for the family plan
    assert mock_plan.call_count == 3
