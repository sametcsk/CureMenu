"""Event-sourcing primitives for clinical decision traces."""

from datetime import datetime, timezone
from uuid import uuid4
from typing import Any


SCHEMA_VERSION = "governance_event.v1"

DEFAULT_EVENT_SCHEMA: dict[str, dict[str, Any]] = {
    "MedicalTermNormalized": {
        "category": "medication_safety",
        "severity": "low",
        "decision_effect": "review_required",
    },
    "MedicationRuleMatched": {
        "category": "medication_safety",
        "severity": "medium",
        "decision_effect": "caution",
    },
    "MedicationSafetyChecked": {
        "category": "medication_safety",
        "severity": "medium",
        "decision_effect": "review_required",
    },
    "GroceryListGenerated": {
        "category": "grocery",
        "severity": "info",
        "decision_effect": "none",
    },
    "HealthComplianceChecked": {
        "category": "grocery",
        "severity": "medium",
        "decision_effect": "caution",
    },
    "PriceEstimationAttempted": {
        "category": "grocery",
        "severity": "info",
        "decision_effect": "none",
    },
    "GroceryBasketSuggested": {
        "category": "grocery",
        "severity": "low",
        "decision_effect": "allow",
    },
    "PolicyChecked": {
        "category": "policy",
        "severity": "medium",
        "decision_effect": "review_required",
    },
    "RuleChecked": {
        "category": "rule",
        "severity": "medium",
        "decision_effect": "caution",
    },
    "RiskClassified": {
        "category": "rule",
        "severity": "medium",
        "decision_effect": "review_required",
    },
    "FinalAnswerGenerated": {
        "category": "generation",
        "severity": "info",
        "decision_effect": "allow",
    },
    "RetrieverExecuted": {
        "category": "retrieval",
        "severity": "info",
        "decision_effect": "none",
    },
}

VALID_SEVERITIES = {"info", "low", "medium", "high", "critical"}
VALID_DECISION_EFFECTS = {"none", "allow", "caution", "block", "review_required"}
BLOCKING_STATUSES = {"blocked", "rejected"}
REVIEW_STATUSES = {"review", "fallback"}


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def new_decision_id() -> str:
    return f"dec_{uuid4().hex}"


def _severity_from_status(status: str, default: str) -> str:
    if status in BLOCKING_STATUSES:
        return "high"
    if status in REVIEW_STATUSES:
        return "medium"
    return default


def _decision_effect_from_status(status: str, default: str) -> str:
    if status in BLOCKING_STATUSES:
        return "block"
    if status in REVIEW_STATUSES:
        return "review_required"
    return default


def normalize_event_metadata(
    event_type: str,
    component: str,
    status: str = "ok",
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Add governance schema fields while preserving existing event metadata."""
    original = dict(metadata or {})
    defaults = DEFAULT_EVENT_SCHEMA.get(
        event_type,
        {"category": "system", "severity": "info", "decision_effect": "none"},
    )
    original_severity = original.get("severity")
    severity = original_severity or _severity_from_status(status, defaults["severity"])
    decision_effect = original.get("decision_effect") or _decision_effect_from_status(status, defaults["decision_effect"])
    if severity not in VALID_SEVERITIES:
        severity = _severity_from_status(status, defaults["severity"])
    if decision_effect not in VALID_DECISION_EFFECTS:
        decision_effect = defaults["decision_effect"]

    blocking = bool(original.get("blocking", status in BLOCKING_STATUSES or decision_effect == "block"))
    review_required = bool(
        original.get(
            "review_required",
            status in REVIEW_STATUSES or decision_effect in {"caution", "review_required", "block"},
        )
    )
    category = original.get("category", defaults["category"])
    return {
        **original,
        "event_name": original.get("event_name", event_type),
        "category": category,
        "severity": severity,
        "decision_effect": decision_effect,
        "blocking": blocking,
        "review_required": review_required,
        "source_component": original.get("source_component", component),
        "schema_version": original.get("schema_version", SCHEMA_VERSION),
    }


def make_event(
    event_type: str,
    component: str,
    *,
    status: str = "ok",
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    normalized_metadata = normalize_event_metadata(event_type, component, status, metadata)
    return {
        "event_type": event_type,
        "component": component,
        "status": status,
        "metadata": normalized_metadata,
        "created_at": utc_now_iso(),
    }


def create_governance_event(
    event_name: str,
    source_component: str,
    *,
    status: str = "ok",
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return make_event(event_name, source_component, status=status, metadata=metadata)


def event_update(
    state: dict[str, Any],
    event_type: str,
    component: str,
    *,
    status: str = "ok",
    metadata: dict[str, Any] | None = None,
) -> dict[str, list[dict[str, Any]]]:
    events = list(state.get("governance_events") or [])
    events.append(
        make_event(
            event_type=event_type,
            component=component,
            status=status,
            metadata=metadata,
        )
    )
    return {"governance_events": events}


def apply_event(
    state: dict[str, Any],
    event_type: str,
    component: str,
    *,
    status: str = "ok",
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    updated = dict(state)
    updated.update(event_update(updated, event_type, component, status=status, metadata=metadata))
    return updated
