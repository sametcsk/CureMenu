"""Central, deterministic food-constraint resolution.

The single place that turns raw profile health data into structured food
constraints for every generative/analysis feature. It enforces the core
invariants:

- A raw disease/condition name (e.g. "Diyabet", "Hipertansiyon", "Laktoz
  intoleransı") is NEVER, by itself, a forbidden ingredient. It is a health label
  / personalization context.
- A raw allergy/intolerance string becomes a hard-avoid ingredient ONLY when the
  deterministic registry (a matched block rule's ingredient group) or the
  ingredient catalog actually resolves it to a food/allergen.
- A value that resolves to nothing is NOT invented into a forbidden food; it is
  carried as an unresolved profile item.
- Every resolved constraint keeps provenance (rule id / ingredient group /
  source), so "why was X avoided?" stays traceable — without logging raw health
  text to telemetry.

No new clinical mapping is invented here: block/caution terms come only from the
existing food-constraint registry and ingredient catalog.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from src.quality.ingredient_catalog import IngredientCatalog
from src.quality.rule_engine import _contains_profile_alias
from src.rules.registry import load_food_constraint_registry


@dataclass(frozen=True)
class ResolvedFoodConstraints:
    profile_health_labels: tuple[str, ...] = ()      # raw condition names (NOT foods)
    hard_avoid_ingredients: tuple[str, ...] = ()      # registry/catalog-verified foods to avoid
    caution_ingredients: tuple[str, ...] = ()         # verified foods needing caution
    dietary_preferences: tuple[str, ...] = ()
    medication_food_constraints: tuple[str, ...] = ()
    health_considerations: tuple[str, ...] = ()       # condition labels that matched a rule (context)
    unresolved_profile_items: tuple[str, ...] = ()    # free-text that resolved to no food
    evidence: tuple[dict[str, Any], ...] = ()

    def as_repair_feedback(self, safety: dict | None = None) -> dict[str, Any]:
        """Structured repair instruction for a generator — food terms only, no
        clinical inference asked of the model."""
        safety = safety or {}
        return {
            "hard_avoid_ingredients": list(self.hard_avoid_ingredients),
            "caution_ingredients": list(self.caution_ingredients),
            "blocked_ingredients": list(safety.get("reasons") or []),
            "safety_findings": list(safety.get("findings") or []),
        }


def _clean(values: list) -> list[str]:
    return [str(v).strip() for v in (values or []) if str(v or "").strip()]


def resolve_food_constraints(profile: dict[str, Any]) -> ResolvedFoodConstraints:
    """PROFILE DATA -> STRUCTURED FOOD CONSTRAINTS (deterministic)."""
    diseases = _clean(profile.get("hastaliklar"))
    allergies = _clean(profile.get("alerjiler"))
    medications = _clean(profile.get("ilaclar"))
    preferences = _clean(profile.get("dietary_preferences") or profile.get("tercihler"))

    registry = load_food_constraint_registry()
    groups = registry["ingredient_groups"]
    catalog = IngredientCatalog()

    hard_avoid: list[str] = []
    caution: list[str] = []
    considerations: list[str] = []
    evidence: list[dict[str, Any]] = []
    matched_values: set[str] = set()

    for rule in registry["profile_rules"]:
        field_name = rule.get("profile_field")
        source_values = allergies if field_name == "alerjiler" else diseases
        matched = [value for value in source_values if _contains_profile_alias(value, rule["profile_aliases"])]
        if not matched:
            continue
        matched_values.update(matched)
        group = groups.get(rule.get("ingredient_group")) if rule.get("ingredient_group") else None
        terms = _clean(group.get("aliases")) if group else []
        outcome = rule.get("outcome")
        target = hard_avoid if outcome == "block" else caution
        target.extend(terms)
        if field_name == "hastaliklar":
            considerations.extend(matched)  # condition -> context, never a food itself
        evidence.append({
            "rule_id": rule.get("rule_id"),
            "ingredient_group": rule.get("ingredient_group"),
            "level": "BLOCK" if outcome == "block" else "CAUTION",
            "source_type": "deterministic_registry",
            "terms": terms,
        })

    unresolved: list[str] = []
    for value in allergies:
        if value in matched_values:
            continue  # already resolved via a registry rule -> its group terms are used
        if catalog.resolve_all(value):
            hard_avoid.append(value)  # a real, catalog-verified ingredient/allergen
            evidence.append({"term": value, "level": "BLOCK", "source_type": "ingredient_catalog"})
        else:
            unresolved.append(value)  # free-text -> never invented into a forbidden food

    def _dedupe(values: list[str]) -> tuple[str, ...]:
        seen: set[str] = set()
        result: list[str] = []
        for value in values:
            key = value.casefold()
            if key not in seen:
                seen.add(key)
                result.append(value)
        return tuple(result)

    # Defensive: a health label must never leak into the ingredient list.
    label_keys = {d.casefold() for d in diseases}
    hard_avoid = [t for t in hard_avoid if t.casefold() not in label_keys]
    caution = [t for t in caution if t.casefold() not in label_keys]

    return ResolvedFoodConstraints(
        profile_health_labels=_dedupe(diseases),
        hard_avoid_ingredients=_dedupe(hard_avoid),
        caution_ingredients=_dedupe(caution),
        dietary_preferences=_dedupe(preferences),
        medication_food_constraints=_dedupe(medications),
        health_considerations=_dedupe(considerations),
        unresolved_profile_items=_dedupe(unresolved),
        evidence=tuple(evidence),
    )


def resolve_food_constraints_from_snapshot(snapshot) -> ResolvedFoodConstraints:
    """Convenience for the ResolvedProfileSnapshot used across features."""
    return resolve_food_constraints({
        "alerjiler": list(getattr(snapshot, "allergies", []) or []),
        "hastaliklar": list(getattr(snapshot, "diseases", []) or []),
        "ilaclar": list(getattr(snapshot, "medications", []) or []),
        "dietary_preferences": list(getattr(snapshot, "goals", []) or []),
    })


def generate_with_safety_repair(*, generate, check, constraints: ResolvedFoodConstraints, max_repairs: int = 2):
    """Shared GENERATE -> SAFETY -> bounded REPAIR loop.

    `generate(feedback)` produces an output (feedback is None on the first attempt,
    else a structured food-only repair dict). `check(output)` returns the
    deterministic safety dict ({"blocked": bool, "reasons": [...], ...}). Returns
    (output, safety, repair_attempts). The safety gate itself is untouched; a draft
    that never passes stays blocked for the caller to fail closed.
    """
    output = generate(None)
    safety = check(output)
    attempts = 0
    while safety.get("blocked") and attempts < max_repairs:
        attempts += 1
        output = generate(constraints.as_repair_feedback(safety))
        safety = check(output)
    return output, safety, attempts
