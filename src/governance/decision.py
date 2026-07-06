"""Build auditable clinical decision records from graph state."""

import re
from typing import Any

from src.governance.events import utc_now_iso
from src.quality.confidence import ConfidenceCalculator

_calculator: ConfidenceCalculator | None = None


def _get_calculator() -> ConfidenceCalculator:
    global _calculator
    if _calculator is None:
        _calculator = ConfidenceCalculator()
    return _calculator


def extract_citations_from_rag(clinical_evidence: str) -> list[dict[str, Any]]:
    """Extract source labels from the current RAG context format."""
    if not clinical_evidence:
        return []

    citations = []
    seen = set()
    for match in re.finditer(r"\[([^\]]+)\]:", clinical_evidence):
        source_id = match.group(1).strip()
        if source_id and source_id not in seen:
            seen.add(source_id)
            citations.append(
                {
                    "source_id": source_id,
                    "chunk_id": "unknown",
                    "title": source_id,
                    "evidence_span": "",
                }
            )
    return citations


def calculate_confidence(
    *,
    safe: bool,
    evidence_found: bool,
    citations: list[dict[str, Any]] | None = None,
    deterministic_block: bool = False,
) -> dict[str, Any]:
    medical_risk = 0.95 if deterministic_block else (0.15 if safe else 0.85)
    evidence_strength = 0.75 if evidence_found else 0.35
    citation_quality = 0.8 if citations else 0.2
    model_confidence = 0.85 if safe else 0.75

    scores = _get_calculator().calculate_final_score(
        model_confidence=model_confidence,
        evidence_strength=evidence_strength,
        medical_risk=medical_risk,
        citation_quality=citation_quality,
    )
    scores["action"] = _get_calculator().determine_action(scores["final_score"])
    return scores


def build_decision_record(
    state: dict[str, Any],
    *,
    telefon: str,
    kimin_icin: str,
    final_answer: str,
) -> dict[str, Any]:
    confidence = state.get("confidence") or calculate_confidence(
        safe=bool(state.get("guvenli_mi", True)),
        evidence_found=bool(state.get("citations")),
        citations=state.get("citations") or [],
    )
    risk_score = state.get("risk_score")
    if risk_score is None:
        risk_score = confidence.get("medical_risk", 0.5)

    return {
        "decision_id": state.get("decision_id"),
        "telefon": telefon,
        "kimin_icin": kimin_icin,
        "request": state.get("istek", ""),
        "final_answer": final_answer,
        "final_action": state.get("hedef_islem", "UNKNOWN"),
        "risk_score": float(risk_score),
        "confidence_score": float(confidence.get("final_score", 0.0)),
        "confidence": confidence,
        "citations": state.get("citations") or [],
        "component_versions": state.get("component_versions") or {},
        "events": state.get("governance_events") or [],
        "created_at": state.get("created_at") or utc_now_iso(),
        "completed_at": utc_now_iso(),
    }
