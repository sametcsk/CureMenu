from typing import Any
from hashlib import sha256

from src.governance.events import make_event
from src.medical_knowledge.medication_rules import high_risk_rules_version, highest_severity, match_rules
from src.medical_knowledge.provenance import rule_provenance_version
from src.medical_knowledge.normalizer import MedicationNormalizer


def _result_source_type(normalized_medications: list[dict[str, Any]], matched_rules: list[dict[str, Any]]) -> str:
    if matched_rules:
        return "deterministic_rule"
    if any(item.get("source_type") == "bioportal" for item in normalized_medications):
        return "bioportal"
    return "local_fallback"


def check_medication_food_safety(
    medications: list[str],
    food_text: str,
    *,
    normalizer: MedicationNormalizer | None = None,
) -> dict[str, Any]:
    normalizer = normalizer or MedicationNormalizer()
    normalized = [item.to_dict() for item in normalizer.normalize_many(medications or [])]
    known_names = [
        item["normalized_name"]
        for item in normalized
        if item.get("normalized_name")
    ]
    unknown = [item for item in normalized if not item.get("normalized_name")]
    matched_rules = match_rules(known_names, food_text or "")

    if matched_rules:
        severity = highest_severity([rule["severity"] for rule in matched_rules])
    elif unknown:
        severity = "unknown"
    else:
        severity = "safe"

    needs_review = bool(unknown or matched_rules)
    explanation_parts = [rule["explanation"] for rule in matched_rules]
    if unknown:
        names = ", ".join(item["original"] for item in unknown)
        explanation_parts.append(
            f"Bilinmeyen ilaç kaydı var: {names}. Sağlık profesyoneli değerlendirmesi gerekir."
        )
    if explanation_parts:
        explanation = " ".join(explanation_parts)
    elif medications:
        explanation = "Bilinen yüksek riskli ilaç-besin kuralı tetiklenmedi."
    else:
        explanation = "Kayıtlı ilaç bulunmadığı için ilaç-besin kuralı çalışmadı."

    return {
        "normalized_medications": normalized,
        "matched_rules": matched_rules,
        "severity": severity,
        "explanation": explanation,
        "source_type": _result_source_type(normalized, matched_rules),
        "needs_professional_review": needs_review,
        "rule_version": high_risk_rules_version(),
        "rule_provenance_version": rule_provenance_version(),
    }


def medication_safety_events(result: dict[str, Any]) -> list[dict[str, Any]]:
    normalized = result.get("normalized_medications") or []
    matched = result.get("matched_rules") or []
    severity = result.get("severity", "unknown")
    unknown_items = [item for item in normalized if not item.get("normalized_name")]
    status = "blocked" if severity == "avoid" else ("review" if severity in {"caution", "unknown"} else "ok")
    return [
        make_event(
            "MedicalTermNormalized",
            "medical_knowledge.normalizer",
            status="ok" if not unknown_items else "review",
            metadata={
                "medication_count": len(normalized),
                "normalized_count": len([item for item in normalized if item.get("normalized_name")]),
                "normalized_names": sorted({item.get("normalized_name") for item in normalized if item.get("normalized_name")}),
                "unknown_count": len(unknown_items),
                "unknown_hashes": [
                    sha256(str(item.get("original", "")).casefold().encode("utf-8")).hexdigest()[:12]
                    for item in unknown_items
                ],
                "source_types": sorted({item.get("source_type", "unknown") for item in normalized}),
            },
        ),
        make_event(
            "MedicationRuleMatched",
            "medical_knowledge.medication_rules",
            status="review" if matched else "ok",
            metadata={
                "matched_count": len(matched),
                "matched_rules": matched,
                "rule_version": result.get("rule_version"),
                "rule_provenance_version": result.get("rule_provenance_version"),
            },
        ),
        make_event(
            "MedicationSafetyChecked",
            "medical_knowledge.safety_checker",
            status=status,
            metadata={
                "severity": severity,
                "needs_professional_review": bool(result.get("needs_professional_review")),
                "source_type": result.get("source_type"),
            },
        ),
    ]
