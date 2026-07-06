"""Load versioned clinical rule registries from YAML files."""

from functools import lru_cache
from pathlib import Path
from typing import Any


RULE_DIR = Path(__file__).resolve().parent
MEDICATION_FOOD_RULE_PATH = RULE_DIR / "medication_food.yaml"


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
