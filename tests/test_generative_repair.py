"""Solution-first coverage: every generative food feature resolves the SAME
central food constraints, GENERATES with them, and REPAIRS an unsafe draft into
a safe one instead of leaving the user with a bare "you can't eat this".

Contract under test (identical across features):
    central food constraints -> generate -> deterministic safety -> bounded
    repair (<=2) -> safety -> safe result (or fail-closed 422 if never safe).

Example names / foods are fixtures only. The deterministic safety gate is never
weakened; an unsafe draft is never surfaced.
"""
import itertools
import json as _json
from types import SimpleNamespace

from unittest.mock import patch

from test_api import login_with_profile


def _msg(text: str):
    """Wrap raw model text like the provider response objects parse_llm_response expects."""
    return SimpleNamespace(content=text)


# --------------------------------------------------------------------------
# Central resolver: raw disease names are NEVER forbidden foods; every feature
# shares one deterministic source of hard-avoid FOOD terms.
# --------------------------------------------------------------------------
def test_raw_disease_names_never_become_forbidden_ingredients():
    from src.quality.food_constraints import resolve_food_constraints

    resolved = resolve_food_constraints(
        {"alerjiler": [], "hastaliklar": ["diyabet", "hipertansiyon", "gut"], "ilaclar": []}
    )
    joined = " ".join(resolved.hard_avoid_ingredients).casefold()
    assert "diyabet" not in joined
    assert "hipertansiyon" not in joined
    # The condition is kept as a personalization label / context, not a food.
    assert resolved.hard_avoid_ingredients == () or all(
        term.casefold() not in {"diyabet", "hipertansiyon", "gut"}
        for term in resolved.hard_avoid_ingredients
    )


def test_all_features_share_one_central_hard_avoid_source():
    """Endpoint features and the graph nodes resolve the exact same food terms
    from one snapshot — no feature-local health->food mapping."""
    from src.quality.food_constraints import resolve_food_constraints
    from src.quality.rule_engine import profile_hard_avoid_ingredients
    from src.nodes import _central_hard_avoid_terms

    profile = {"alerjiler": ["inek sütü proteini"], "hastaliklar": [], "ilaclar": []}
    central = list(resolve_food_constraints(profile).hard_avoid_ingredients)

    # rule_engine helper (used by deterministic layer) delegates to the center.
    assert profile_hard_avoid_ingredients(profile) == central

    # graph nodes resolve from the serialized snapshot payload -> same terms.
    snapshot_payload = {
        "allergies": ["inek sütü proteini"], "diseases": [], "medications": [], "goals": [],
    }
    assert _central_hard_avoid_terms(snapshot_payload) == central
    assert central  # milk allergy really does yield dairy food terms


def test_generic_repair_helper_generates_then_repairs_to_safe():
    from src.quality.food_constraints import (
        ResolvedFoodConstraints,
        generate_with_safety_repair,
    )

    constraints = ResolvedFoodConstraints(hard_avoid_ingredients=("süt", "peynir"))
    drafts = iter([
        {"text": "peynirli tost"},   # unsafe
        {"text": "peynirli tost"},   # still unsafe (repair 1)
        {"text": "zeytinli salata"}, # safe (repair 2)
    ])

    def generate(feedback):
        return next(drafts)

    def check(output):
        blocked = "peynir" in output["text"]
        return {"blocked": blocked, "reasons": ["peynir"] if blocked else []}

    output, safety, attempts = generate_with_safety_repair(
        generate=generate, check=check, constraints=constraints, max_repairs=2
    )
    assert safety["blocked"] is False
    assert output["text"] == "zeytinli salata"
    assert attempts == 2


def test_generic_repair_helper_fails_closed_when_never_safe():
    from src.quality.food_constraints import (
        ResolvedFoodConstraints,
        generate_with_safety_repair,
    )

    constraints = ResolvedFoodConstraints(hard_avoid_ingredients=("süt",))

    def generate(feedback):
        return {"text": "sütlü tabak"}

    def check(output):
        return {"blocked": True, "reasons": ["süt"]}

    output, safety, attempts = generate_with_safety_repair(
        generate=generate, check=check, constraints=constraints, max_repairs=2
    )
    assert safety["blocked"] is True   # gate unchanged -> caller fails closed
    assert attempts == 2               # bounded


# --------------------------------------------------------------------------
# plan-action: recipe / snack / alternative — GENERATE + bounded REPAIR.
# --------------------------------------------------------------------------
_RECIPE_UNSAFE = _json.dumps(
    {"name": "Peynirli tost", "ingredients": ["peynir", "ekmek"], "preparation": "Hazırla."}
)
_RECIPE_SAFE = _json.dumps(
    {"name": "Zeytinli salata", "ingredients": ["zeytin", "domates"], "preparation": "Karıştır."}
)


@patch("src.routers.tools.invoke_with_model_fallback")
def test_plan_action_recipe_repairs_unsafe_then_safe(mock_llm, client):
    login_with_profile(client, "5557000001", "Recipe Repair", alerjiler=["inek sütü proteini"])
    mock_llm.side_effect = [_msg(_RECIPE_UNSAFE), _msg(_RECIPE_SAFE)]  # cheese -> repair -> safe
    res = client.post("/api/plan-action", json={"action_type": "recipe", "meal_text": "Tost", "kimin_icin": "kendim"})
    assert res.status_code == 200 and res.json()["success"] is True
    assert "Peynirli tost" not in res.text          # unsafe draft never leaks
    assert mock_llm.call_count == 2


@patch("src.routers.tools.invoke_with_model_fallback")
def test_plan_action_recipe_all_repairs_unsafe_blocks(mock_llm, client):
    login_with_profile(client, "5557000002", "Recipe Block", alerjiler=["inek sütü proteini"])
    mock_llm.return_value = _msg(_RECIPE_UNSAFE)  # always cheese
    res = client.post("/api/plan-action", json={"action_type": "recipe", "meal_text": "Tost", "kimin_icin": "kendim"})
    assert res.status_code == 422              # never-safe -> fail-closed
    assert mock_llm.call_count == 3            # initial + 2 bounded repairs


@patch("src.routers.tools.invoke_with_model_fallback")
def test_plan_action_snack_repairs_unsafe_then_safe(mock_llm, client):
    login_with_profile(client, "5557000003", "Snack Repair", alerjiler=["inek sütü proteini"])
    unsafe = _json.dumps({"snacks": [{"name": "Peynir tabağı", "ingredients": ["peynir"], "preparation": "Dizin.", "why_it_fits": "Pratik."}]})
    safe = _json.dumps({"snacks": [{"name": "Meyve kasesi", "ingredients": ["elma", "armut"], "preparation": "Doğra.", "why_it_fits": "Hafif."}]})
    mock_llm.side_effect = [_msg(unsafe), _msg(safe)]
    res = client.post("/api/plan-action", json={"action_type": "snack", "meal_text": "Atıştırmalık", "plan_text": "Bugün: hafif", "kimin_icin": "kendim"})
    assert res.status_code == 200 and res.json()["success"] is True
    assert "Peynir tabağı" not in res.text
    assert mock_llm.call_count == 2


@patch("src.routers.tools.invoke_with_model_fallback")
def test_plan_action_alternative_repairs_unsafe_then_safe(mock_llm, client):
    login_with_profile(client, "5557000004", "Alt Repair", alerjiler=["inek sütü proteini"])
    unsafe = _json.dumps({"degisen_ogunler": [{"eski": "Mercimek Çorbası", "yeni": "Peynirli börek", "ingredients": ["peynir", "yufka"]}]})
    safe = _json.dumps({"degisen_ogunler": [{"eski": "Mercimek Çorbası", "yeni": "Zeytinli salata", "ingredients": ["zeytin", "domates"]}]})
    mock_llm.side_effect = [_msg(unsafe), _msg(safe)]
    res = client.post("/api/plan-action", json={"action_type": "alternative", "meal_text": "Mercimek Çorbası", "plan_text": "Öğle: Mercimek Çorbası", "kimin_icin": "kendim"})
    assert res.status_code == 200 and res.json()["success"] is True
    assert "Peynirli börek" not in res.text
    assert mock_llm.call_count == 2


# --------------------------------------------------------------------------
# CureBot food-generation intent: GENERATE with central constraints + REPAIR,
# then surface a SAFE meal (never a bare refusal) for a food request.
# --------------------------------------------------------------------------
def test_curebot_food_generation_repairs_unsafe_then_safe(client, monkeypatch):
    login_with_profile(client, "5557000010", "CureBot Repair", alerjiler=["inek sütü proteini"])

    answers = itertools.chain(
        ["Sana **Peynirli tost:** peynir ve ekmekle önerebilirim."],  # unsafe draft
        itertools.repeat("Bu akşam **Fırında tavuk ve sebze:** derisiz tavuk ve kabak deneyebilirsin."),  # safe repair
    )
    calls = {"n": 0}

    def fake_generate(*_args, **_kwargs):
        calls["n"] += 1
        return next(answers)

    monkeypatch.setattr("src.routers.chat.generate_curebot_natural_answer", fake_generate)

    async def should_not_run(_state):
        raise AssertionError("food generation must resolve on the repair fast-path, not the graph")

    monkeypatch.setattr("src.routers.chat.langgraph_app.astream", should_not_run)

    res = client.post("/api/chat", json={"mesaj": "Bu akşam ne yiyebilirim?", "kimin_icin": "kendim"})
    assert res.status_code == 200
    assert "Fırında tavuk" in res.text          # safe alternative surfaced
    assert "Peynirli tost" not in res.text       # unsafe draft never leaks
    assert calls["n"] >= 2                        # it actually repaired, not just refused
