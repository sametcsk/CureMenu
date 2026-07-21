"""Load and validate versioned clinical rule registries."""

import json
from functools import lru_cache
from pathlib import Path
from typing import Any


RULE_DIR = Path(__file__).resolve().parent
MEDICATION_FOOD_RULE_PATH = RULE_DIR / "medication_food.yaml"
FOOD_CONSTRAINT_RULE_PATH = RULE_DIR / "food_constraints.json"
INGREDIENT_CATALOG_PATH = RULE_DIR / "ingredient_catalog.json"


class RuleRegistryError(RuntimeError):
    """Raised when a rule registry cannot be loaded or validated."""


def _strip_inline_comment(line: str) -> str:
    in_quote: str | None = None
    for index, char in enumerate(line):
        if char in ("'", '"'):
            in_quote = None if in_quote == char else char
        elif char == "#" and in_quote is None:
            return line[:index]
    return line


def _parse_scalar(value: str) -> Any:
    value = value.strip()
    if value in ("", "null", "None"):
        return ""
    if value in ("true", "false"):
        return value == "true"
    if (
        len(value) >= 2
        and value[0] == value[-1]
        and value.startswith(("'", '"'))
    ):
        return value[1:-1]
    return value


def _parse_simple_yaml(text: str) -> dict[str, Any]:
    """Parse the limited YAML subset used by our checked-in rule registry.

    PyYAML is preferred in production. This fallback keeps tests and local
    development deterministic in minimal environments where PyYAML is absent.
    """
    data: dict[str, Any] = {}
    current_rule: dict[str, Any] | None = None
    active_top_key: str | None = None
    active_list_key: str | None = None

    for raw_line in text.splitlines():
        line = _strip_inline_comment(raw_line).rstrip()
        if not line.strip():
            continue

        stripped = line.strip()
        indent = len(line) - len(line.lstrip(" "))

        if indent == 0:
            current_rule = None
            active_list_key = None
            if stripped.endswith(":"):
                active_top_key = stripped[:-1].strip()
                data.setdefault(active_top_key, [])
                continue
            key, _, value = stripped.partition(":")
            data[key.strip()] = _parse_scalar(value)
            active_top_key = key.strip()
            continue

        if active_top_key == "rules" and stripped.startswith("- "):
            item = stripped[2:].strip()
            key, _, value = item.partition(":")
            current_rule = {key.strip(): _parse_scalar(value)}
            data.setdefault("rules", []).append(current_rule)
            active_list_key = None
            continue

        if current_rule is None:
            continue

        if stripped.startswith("- ") and active_list_key:
            current_rule.setdefault(active_list_key, []).append(
                _parse_scalar(stripped[2:].strip())
            )
            continue

        key, _, value = stripped.partition(":")
        key = key.strip()
        if value.strip() == "":
            current_rule[key] = []
            active_list_key = key
        else:
            current_rule[key] = _parse_scalar(value)
            active_list_key = None

    return data


def _load_yaml(path: Path) -> dict[str, Any]:
    text = path.read_text(encoding="utf-8")
    try:
        import yaml  # type: ignore
    except ModuleNotFoundError:
        data = _parse_simple_yaml(text)
    else:
        data = yaml.safe_load(text) or {}

    if not isinstance(data, dict):
        raise RuleRegistryError(f"Rule registry must be a mapping: {path}")
    return data


def _as_str_list(value: Any, *, field_name: str) -> list[str]:
    if value is None:
        return []
    if not isinstance(value, list):
        raise RuleRegistryError(f"{field_name} must be a list")
    result = []
    for item in value:
        if item is None:
            continue
        result.append(str(item).strip())
    return [item for item in result if item]


@lru_cache(maxsize=1)
def load_medication_food_registry() -> dict[str, Any]:
    """Return the validated medication-food rule registry."""
    data = _load_yaml(MEDICATION_FOOD_RULE_PATH)
    rules = data.get("rules")
    if not isinstance(rules, list) or not rules:
        raise RuleRegistryError("medication_food registry must contain rules")

    validated_rules: list[dict[str, Any]] = []
    for index, raw_rule in enumerate(rules, start=1):
        if not isinstance(raw_rule, dict):
            raise RuleRegistryError(f"Rule #{index} must be a mapping")

        medication = str(raw_rule.get("medication", "")).strip()
        warning = str(raw_rule.get("warning", "")).strip()
        if not medication:
            raise RuleRegistryError(f"Rule #{index} missing medication")
        if not warning:
            raise RuleRegistryError(f"Rule #{index} missing warning")

        validated_rules.append(
            {
                "medication": medication,
                "aliases": _as_str_list(
                    raw_rule.get("aliases"), field_name=f"{medication}.aliases"
                ),
                "risk_terms": _as_str_list(
                    raw_rule.get("risk_terms"), field_name=f"{medication}.risk_terms"
                ),
                "warning": warning,
                "severity": str(raw_rule.get("severity", "medium")).strip() or "medium",
            }
        )

    return {
        "version": str(data.get("version", "medication_food_rules:unknown")),
        "description": str(data.get("description", "")),
        "rules": validated_rules,
    }


def medication_food_registry_version() -> str:
    """Expose the active registry version for audit metadata."""
    return str(load_medication_food_registry().get("version", "unknown"))


@lru_cache(maxsize=1)
def load_food_constraint_registry() -> dict[str, Any]:
    """Return validated ingredient groups and profile constraint rules."""
    try:
        data = json.loads(FOOD_CONSTRAINT_RULE_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise RuleRegistryError("food constraint registry could not be loaded") from exc

    groups = data.get("ingredient_groups")
    rules = data.get("profile_rules")
    if not isinstance(groups, dict) or not groups:
        raise RuleRegistryError("food constraint registry must contain ingredient_groups")
    if not isinstance(rules, list) or not rules:
        raise RuleRegistryError("food constraint registry must contain profile_rules")

    validated_groups: dict[str, dict[str, list[str]]] = {}
    for group_name, raw_group in groups.items():
        if not isinstance(raw_group, dict):
            raise RuleRegistryError(f"Ingredient group {group_name} must be a mapping")
        aliases = _as_str_list(raw_group.get("aliases"), field_name=f"{group_name}.aliases")
        if not aliases:
            raise RuleRegistryError(f"Ingredient group {group_name} must contain aliases")
        validated_groups[str(group_name)] = {
            "aliases": aliases,
            "allowed_prefixes": _as_str_list(
                raw_group.get("allowed_prefixes"),
                field_name=f"{group_name}.allowed_prefixes",
            ),
        }

    validated_rules: list[dict[str, Any]] = []
    allowed_catalog_fields = {
        "tags",
        "allergens",
        "gluten_status",
        "milk_product",
        "purine_level",
        "vitamin_k_level",
        "ckd_caution_tags",
    }
    for index, raw_rule in enumerate(rules, start=1):
        if not isinstance(raw_rule, dict):
            raise RuleRegistryError(f"Food constraint rule #{index} must be a mapping")
        rule_id = str(raw_rule.get("rule_id", "")).strip()
        profile_field = str(raw_rule.get("profile_field", "")).strip()
        outcome = str(raw_rule.get("outcome", "")).strip()
        message = str(raw_rule.get("message", "")).strip()
        ingredient_group = raw_rule.get("ingredient_group")
        profile_aliases = _as_str_list(
            raw_rule.get("profile_aliases"),
            field_name=f"{rule_id or index}.profile_aliases",
        )
        if not rule_id or not message or not profile_aliases:
            raise RuleRegistryError(f"Food constraint rule #{index} is incomplete")
        if profile_field not in {"alerjiler", "hastaliklar"}:
            raise RuleRegistryError(f"Food constraint rule {rule_id} has invalid profile_field")
        if outcome not in {"block", "caution"}:
            raise RuleRegistryError(f"Food constraint rule {rule_id} has invalid outcome")
        if ingredient_group is not None and ingredient_group not in validated_groups:
            raise RuleRegistryError(f"Food constraint rule {rule_id} references an unknown group")
        always_review = bool(raw_rule.get("always_review", False))
        if ingredient_group is None and not always_review:
            raise RuleRegistryError(f"Food constraint rule {rule_id} has no trigger")
        raw_conditions = raw_rule.get("catalog_conditions", [])
        if not isinstance(raw_conditions, list):
            raise RuleRegistryError(f"Food constraint rule {rule_id} has invalid catalog_conditions")
        catalog_conditions: list[dict[str, Any]] = []
        for condition in raw_conditions:
            if not isinstance(condition, dict):
                raise RuleRegistryError(f"Food constraint rule {rule_id} has invalid catalog condition")
            field = str(condition.get("field", "")).strip()
            operator = str(condition.get("operator", "")).strip()
            value = condition.get("value")
            if field not in allowed_catalog_fields or operator not in {"contains", "equals"}:
                raise RuleRegistryError(f"Food constraint rule {rule_id} has unsupported catalog condition")
            catalog_conditions.append(
                {"field": field, "operator": operator, "value": value}
            )

        validated_rules.append(
            {
                "rule_id": rule_id,
                "profile_field": profile_field,
                "profile_aliases": profile_aliases,
                "ingredient_group": ingredient_group,
                "outcome": outcome,
                "always_review": always_review,
                "catalog_conditions": catalog_conditions,
                "message": message,
            }
        )

    return {
        "version": str(data.get("version", "food_constraints:unknown")),
        "ingredient_groups": validated_groups,
        "profile_rules": validated_rules,
        "unknown_ingredient_message": str(
            data.get(
                "unknown_ingredient_message",
                "İçeriği katalogda doğrulanamayan bir malzeme bulundu: {ingredient}.",
            )
        ),
    }


@lru_cache(maxsize=1)
def load_ingredient_catalog() -> dict[str, Any]:
    """Return the validated, intentionally small ingredient catalog."""
    try:
        data = json.loads(INGREDIENT_CATALOG_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise RuleRegistryError("ingredient catalog could not be loaded") from exc

    ingredients = data.get("ingredients")
    if not isinstance(ingredients, list) or not ingredients:
        raise RuleRegistryError("ingredient catalog must contain ingredients")

    required_fields = {
        "canonical_name",
        "aliases",
        "tags",
        "allergens",
        "gluten_status",
        "milk_product",
        "purine_level",
        "vitamin_k_level",
        "ckd_caution_tags",
    }
    allowed_gluten = {"contains", "free", "unknown"}
    allowed_levels = {"low", "moderate", "high", "unknown"}
    validated: list[dict[str, Any]] = []
    canonical_names: set[str] = set()
    for index, ingredient in enumerate(ingredients, start=1):
        if not isinstance(ingredient, dict):
            raise RuleRegistryError(f"Ingredient #{index} must be a mapping")
        missing = required_fields.difference(ingredient)
        if missing:
            raise RuleRegistryError(f"Ingredient #{index} missing fields: {sorted(missing)}")
        canonical_name = str(ingredient["canonical_name"]).strip()
        if not canonical_name or canonical_name in canonical_names:
            raise RuleRegistryError(f"Ingredient #{index} has an invalid canonical_name")
        canonical_names.add(canonical_name)
        gluten_status = str(ingredient["gluten_status"]).strip()
        purine_level = str(ingredient["purine_level"]).strip()
        vitamin_k_level = str(ingredient["vitamin_k_level"]).strip()
        if gluten_status not in allowed_gluten:
            raise RuleRegistryError(f"Ingredient {canonical_name} has invalid gluten_status")
        if purine_level not in allowed_levels or vitamin_k_level not in allowed_levels:
            raise RuleRegistryError(f"Ingredient {canonical_name} has invalid level data")
        if not isinstance(ingredient["milk_product"], bool):
            raise RuleRegistryError(f"Ingredient {canonical_name} has invalid milk_product")

        validated.append(
            {
                "canonical_name": canonical_name,
                "aliases": _as_str_list(
                    ingredient["aliases"], field_name=f"{canonical_name}.aliases"
                ),
                "tags": _as_str_list(
                    ingredient["tags"], field_name=f"{canonical_name}.tags"
                ),
                "allergens": _as_str_list(
                    ingredient["allergens"], field_name=f"{canonical_name}.allergens"
                ),
                "gluten_status": gluten_status,
                "milk_product": ingredient["milk_product"],
                "purine_level": purine_level,
                "vitamin_k_level": vitamin_k_level,
                "ckd_caution_tags": _as_str_list(
                    ingredient["ckd_caution_tags"],
                    field_name=f"{canonical_name}.ckd_caution_tags",
                ),
            }
        )

    return {
        "version": str(data.get("version", "ingredient_catalog:unknown")),
        "ingredients": validated,
    }
