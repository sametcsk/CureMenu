import json
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any

from src.medical_knowledge.normalizer import normalize_text


RULE_PATH = Path(__file__).resolve().parent / "data" / "high_risk_medications.json"
SEVERITY_RANK = {"safe": 0, "unknown": 1, "caution": 2, "avoid": 3}


@dataclass(frozen=True)
class MedicationFoodRule:
    medication: str
    aliases: list[str]
    risk_terms: list[str]
    severity: str
    explanation: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "medication": self.medication,
            "aliases": self.aliases,
            "risk_terms": self.risk_terms,
            "severity": self.severity,
            "explanation": self.explanation,
        }


@lru_cache(maxsize=1)
def load_high_risk_medication_rules() -> dict[str, Any]:
    with RULE_PATH.open("r", encoding="utf-8") as fh:
        raw = json.load(fh)
    rules = []
    for item in raw.get("rules", []):
        rules.append(
            MedicationFoodRule(
                medication=str(item["medication"]).strip(),
                aliases=[str(alias).strip() for alias in item.get("aliases", []) if str(alias).strip()],
                risk_terms=[str(term).strip() for term in item.get("risk_terms", []) if str(term).strip()],
                severity=str(item.get("severity", "caution")).strip() or "caution",
                explanation=str(item.get("explanation", "")).strip(),
            )
        )
    return {"version": str(raw.get("version", "high_risk_medications:unknown")), "rules": rules}


def high_risk_rules_version() -> str:
    return str(load_high_risk_medication_rules()["version"])


def rules_for_medication(normalized_name: str | None) -> list[MedicationFoodRule]:
    if not normalized_name:
        return []
    target = normalize_text(normalized_name)
    matches = []
    for rule in load_high_risk_medication_rules()["rules"]:
        aliases = [rule.medication, *rule.aliases]
        if any(normalize_text(alias) == target for alias in aliases):
            matches.append(rule)
    return matches


def match_rules(normalized_medications: list[str], food_text: str) -> list[dict[str, Any]]:
    folded_food = normalize_text(food_text)
    matches: list[dict[str, Any]] = []
    for medication in normalized_medications:
        for rule in rules_for_medication(medication):
            matched_terms = [
                term
                for term in rule.risk_terms
                if normalize_text(term) and normalize_text(term) in folded_food
            ]
            if matched_terms:
                matches.append(
                    {
                        "medication": rule.medication,
                        "matched_terms": matched_terms,
                        "severity": rule.severity,
                        "explanation": rule.explanation,
                        "source_type": "deterministic_rule",
                        "rule_version": high_risk_rules_version(),
                    }
                )
    return matches


def highest_severity(severities: list[str]) -> str:
    if not severities:
        return "safe"
    return max(severities, key=lambda severity: SEVERITY_RANK.get(severity, 0))
