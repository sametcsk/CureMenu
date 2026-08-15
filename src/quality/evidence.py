"""Typed evidence contract shared by safety decisions and user-facing wording.

The renderer deliberately does not inspect profile restrictions or free-form
answer text.  It can only express the evidence level already assigned by the
deterministic evidence layer.
"""
from __future__ import annotations

import hashlib
import json
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


EvidenceLevel = Literal["CONFIRMED", "INFERRED-LIKELY", "UNKNOWN", "CLEAR"]


class SafetyFinding(BaseModel):
    model_config = ConfigDict(frozen=True)

    finding_id: str = ""
    restriction_type: str
    restriction_identifier: str
    evidence_level: EvidenceLevel = "UNKNOWN"
    evidence_source: str = "legacy_or_unspecified"
    matched_ingredient: str = ""
    matched_catalog_entry: str = ""
    input_span: str = ""
    explanation: str = ""
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    target_profile_id: str = ""
    provenance: dict[str, Any] = Field(default_factory=dict)
    inherited_from_previous_turn: bool = False
    new_evidence_this_turn: bool = False
    originating_turn_id: str = ""
    artifact_reference: str = "none"

    @property
    def identity(self) -> tuple[str, str, str, str]:
        return (
            self.target_profile_id,
            self.restriction_type,
            self.restriction_identifier.casefold(),
            self.matched_ingredient.casefold(),
        )

    def persisted(self) -> dict[str, Any]:
        payload = self.model_dump()
        if not payload["finding_id"]:
            stable = json.dumps(self.identity, ensure_ascii=False, separators=(",", ":"))
            payload["finding_id"] = hashlib.sha256(stable.encode("utf-8")).hexdigest()[:20]
        return payload


def coerce_finding(
    value: SafetyFinding | dict[str, Any],
    *,
    target_profile_id: str = "",
    artifact_reference: str = "none",
) -> SafetyFinding:
    if isinstance(value, SafetyFinding):
        finding = value
    else:
        raw = dict(value or {})
        # Backward compatibility is fail-closed: old rows without an explicit
        # evidence level are not promoted to confirmed findings.
        raw["evidence_level"] = str(raw.get("evidence_level") or "UNKNOWN").upper()
        if raw["evidence_level"] == "INFERRED":
            raw["evidence_level"] = "INFERRED-LIKELY"
        if raw["evidence_level"] not in {"CONFIRMED", "INFERRED-LIKELY", "UNKNOWN", "CLEAR"}:
            raw["evidence_level"] = "UNKNOWN"
        raw.setdefault("restriction_identifier", str(raw.get("restriction_id") or ""))
        raw.setdefault("matched_ingredient", str(raw.get("matched_entity") or ""))
        raw.setdefault("matched_catalog_entry", str(raw.get("catalog_reference") or ""))
        raw.setdefault("input_span", str(raw.get("input_reference") or ""))
        raw.setdefault("evidence_source", "legacy_or_unspecified")
        raw.setdefault("restriction_type", "unknown")
        raw.setdefault("target_profile_id", target_profile_id)
        raw.setdefault("artifact_reference", artifact_reference)
        finding = SafetyFinding.model_validate(raw)

    updates: dict[str, Any] = {}
    if target_profile_id and not finding.target_profile_id:
        updates["target_profile_id"] = target_profile_id
    if artifact_reference != "none" and finding.artifact_reference == "none":
        updates["artifact_reference"] = artifact_reference
    # A confirmed comparison requires an actual matched entity and a traceable
    # source. A bare profile restriction is comparison input, not food evidence.
    if finding.evidence_level == "CONFIRMED" and (
        not finding.matched_ingredient.strip()
        or finding.evidence_source in {"", "legacy_or_unspecified", "profile_review_policy"}
    ):
        updates.update({
            "evidence_level": "UNKNOWN",
            "confidence": min(finding.confidence, 0.25),
            "new_evidence_this_turn": False,
        })
    return finding.model_copy(update=updates) if updates else finding


def render_finding(value: SafetyFinding | dict[str, Any]) -> str:
    finding = coerce_finding(value)
    restriction = finding.restriction_identifier.strip() or "kayıtlı kısıt"
    matched = finding.matched_ingredient.strip()

    if finding.evidence_level == "CONFIRMED":
        base = f"{matched} içeriği ile kayıtlı {restriction} kısıtı arasında eşleşme bulundu."
        explanation = finding.explanation.strip()
        return f"{base} {explanation}" if explanation and explanation not in base else base
    if finding.evidence_level == "INFERRED-LIKELY":
        subject = matched or "Bu ürün kategorisi"
        return (
            f"{subject} için {restriction} açısından risk olabilir; "
            "kesin içerik etiket veya üretici bilgisiyle doğrulanmalıdır."
        )
    if finding.evidence_level == "CLEAR":
        return f"Mevcut yapılandırılmış içerik bilgisinde {restriction} ile eşleşme görülmedi."
    return (
        f"{restriction} açısından içerik bilgisi kesin karar vermek için yeterli değil; "
        "etiket veya üretici bilgisi kontrol edilmelidir."
    )


def carry_findings_without_new_evidence(
    findings: list[SafetyFinding | dict[str, Any]] | tuple[SafetyFinding | dict[str, Any], ...],
) -> tuple[SafetyFinding, ...]:
    return tuple(
        coerce_finding(item).model_copy(update={
            "inherited_from_previous_turn": True,
            "new_evidence_this_turn": False,
        })
        for item in findings
    )


def merge_finding_evidence(
    previous: SafetyFinding | dict[str, Any],
    current: SafetyFinding | dict[str, Any],
) -> SafetyFinding:
    """Apply the no-new-evidence monotonicity contract to one finding."""
    old = coerce_finding(previous)
    new = coerce_finding(current)
    rank = {"CLEAR": 0, "UNKNOWN": 1, "INFERRED-LIKELY": 2, "CONFIRMED": 3}
    is_upgrade = rank[new.evidence_level] > rank[old.evidence_level]
    has_upgrade_provenance = bool(
        new.new_evidence_this_turn
        and new.evidence_source not in {"", "legacy_or_unspecified", "profile_review_policy"}
        and (new.matched_ingredient or new.input_span or new.matched_catalog_entry)
    )
    if is_upgrade and not has_upgrade_provenance:
        return old.model_copy(update={
            "inherited_from_previous_turn": True,
            "new_evidence_this_turn": False,
        })
    if is_upgrade:
        provenance = dict(new.provenance)
        provenance.setdefault("evidence_upgrade_reason", "new_traceable_evidence")
        return new.model_copy(update={"provenance": provenance})
    return new
