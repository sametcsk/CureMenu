"""Operational clinical KPI calculations for audit/dashboard views."""

from collections import Counter
from typing import Any


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _rate(numerator: int, denominator: int) -> float:
    if denominator <= 0:
        return 0.0
    return round((numerator / denominator) * 100, 2)


def event_is_blocking(event: dict[str, Any]) -> bool:
    metadata = event.get("metadata") or {}
    if metadata.get("blocking") is True:
        return True
    return event.get("status") == "blocked" or event.get("event_type") == "RuleTriggered"


def event_requires_review(event: dict[str, Any]) -> bool:
    metadata = event.get("metadata") or {}
    if metadata.get("review_required") is True:
        return True
    return event.get("status") in {"review", "fallback"}


def calculate_clinical_kpis(
    decisions: list[dict[str, Any]],
    events: list[dict[str, Any]],
) -> dict[str, Any]:
    """Calculate operational safety/observability KPIs from persisted audit data."""
    total = len(decisions)
    confidence_scores = [_safe_float(d.get("confidence_score")) for d in decisions]
    risk_scores = [_safe_float(d.get("risk_score")) for d in decisions]

    low_confidence = [score for score in confidence_scores if score < 0.70]
    high_risk = [score for score in risk_scores if score >= 0.70]

    confidence_actions = Counter(
        (d.get("confidence_data") or {}).get("action", "UNKNOWN")
        for d in decisions
    )
    decisions_with_citations = sum(1 for d in decisions if d.get("citations"))

    event_types = Counter(e.get("event_type", "UNKNOWN") for e in events)
    components = Counter(e.get("component", "UNKNOWN") for e in events)
    blocked_events = [e for e in events if event_is_blocking(e)]
    review_events = [e for e in events if event_requires_review(e)]
    retrieval_events = [e for e in events if e.get("event_type") == "RetrieverExecuted"]
    evidence_found_events = [
        e for e in retrieval_events
        if (e.get("metadata") or {}).get("evidence_found") is True
    ]

    avg_confidence = round(sum(confidence_scores) / total, 4) if total else 0.0
    avg_risk = round(sum(risk_scores) / total, 4) if total else 0.0

    return {
        "total_decisions": total,
        "average_confidence": avg_confidence,
        "average_risk": avg_risk,
        "low_confidence_count": len(low_confidence),
        "low_confidence_rate": _rate(len(low_confidence), total),
        "high_risk_count": len(high_risk),
        "high_risk_rate": _rate(len(high_risk), total),
        "evidence_coverage_rate": _rate(decisions_with_citations, total),
        "retrieval_evidence_rate": _rate(len(evidence_found_events), len(retrieval_events)),
        "blocked_decision_events": len(blocked_events),
        "blocked_event_rate": _rate(len(blocked_events), len(events)),
        "review_required_event_count": len(review_events),
        "review_required_count": confidence_actions.get("REVIEW_REQUIRED", 0),
        "reject_count": confidence_actions.get("REJECT", 0),
        "approve_count": confidence_actions.get("APPROVE", 0),
        "action_distribution": dict(confidence_actions),
        "top_event_types": event_types.most_common(8),
        "top_components": components.most_common(8),
    }
