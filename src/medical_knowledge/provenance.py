"""Versioned, machine-verifiable provenance for deterministic medication rules."""

from __future__ import annotations

import hashlib
import json
from functools import lru_cache
from pathlib import Path
from typing import Any

import fitz


PROJECT_ROOT = Path(__file__).resolve().parents[2]
PROVENANCE_PATH = PROJECT_ROOT / "data" / "clinical_evidence_registry.json"
OFFICIAL_SOURCE_DIR = PROJECT_ROOT / "data" / "rag_candidates" / "official"
RULE_PATH = Path(__file__).resolve().parent / "data" / "high_risk_medications.json"


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest().upper()


@lru_cache(maxsize=1)
def load_rule_provenance() -> dict[str, Any]:
    registry = json.loads(PROVENANCE_PATH.read_text(encoding="utf-8"))
    sources = registry.get("sources") or {}
    rules: dict[str, dict[str, Any]] = {}
    for rule_id, rule in (registry.get("rules") or {}).items():
        source_id = str(rule.get("source_id") or "")
        source = sources.get(source_id) or {}
        rules[rule_id] = {
            **rule,
            "authority": source.get("authority"),
            "source_file": source.get("filename"),
            "source_url": source.get("url"),
            "sha256": source.get("sha256"),
        }
    versions = registry.get("compatibility_versions") or {}
    return {
        "version": versions.get("medication_rule_provenance", registry.get("schema_version")),
        "schema_version": registry.get("schema_version"),
        "last_source_check": registry.get("last_source_check"),
        "clinical_review_required": registry.get("clinical_review_required"),
        "sources": sources,
        "rules": rules,
    }


@lru_cache(maxsize=1)
def load_evidence_registry() -> dict[str, Any]:
    return json.loads(PROVENANCE_PATH.read_text(encoding="utf-8"))


def rule_provenance_version() -> str:
    return str(load_rule_provenance().get("version", "medication_rule_provenance:unknown"))


def get_rule_provenance(rule_id: str) -> dict[str, Any] | None:
    item = (load_rule_provenance().get("rules") or {}).get(rule_id)
    return dict(item) if isinstance(item, dict) else None


def validate_rule_provenance(*, verify_files: bool = False) -> list[str]:
    """Return validation issues; an empty list means the registry is internally valid."""
    registry = load_evidence_registry()
    payload = load_rule_provenance()
    issues: list[str] = []
    if registry.get("schema_version") != "clinical_evidence_registry:v1":
        issues.append("registry: unsupported schema_version")
    if not payload.get("last_source_check"):
        issues.append("registry: last_source_check missing")
    if payload.get("clinical_review_required") is not True:
        issues.append("registry: clinical_review_required must be true")
    source_required = {
        "filename", "url", "sha256", "authority", "authority_tier",
        "source_role", "included_pages",
    }
    source_pages: dict[str, set[int]] = {}
    for source_id, source in (registry.get("sources") or {}).items():
        missing = sorted(source_required - set(source))
        if missing:
            issues.append(f"{source_id}: missing {', '.join(missing)}")
            continue
        included_pages = source.get("included_pages") or []
        if not included_pages or not all(isinstance(page, int) and page > 0 for page in included_pages):
            issues.append(f"{source_id}: invalid included_pages")
            continue
        source_pages[source_id] = set(included_pages)
        if not verify_files:
            continue
        path = OFFICIAL_SOURCE_DIR / str(source["filename"])
        if not path.is_file():
            issues.append(f"{source_id}: source file missing")
            continue
        with path.open("rb") as handle:
            pdf_magic = handle.read(5)
        if pdf_magic != b"%PDF-":
            issues.append(f"{source_id}: source is not a PDF")
            continue
        if _sha256(path) != str(source["sha256"]).upper():
            issues.append(f"{source_id}: source hash mismatch")
            continue
        try:
            with fitz.open(path) as pdf:
                for page_number in included_pages:
                    if page_number > pdf.page_count:
                        issues.append(f"{source_id}: page {page_number} out of range")
                    elif len((pdf[page_number - 1].get_text("text") or "").strip()) < 40:
                        issues.append(f"{source_id}: page {page_number} has no meaningful text")
        except Exception as exc:
            issues.append(f"{source_id}: PDF read failed ({type(exc).__name__})")

    required = {
        "source_id", "authority", "source_file", "source_url", "sha256", "pages",
        "evidence_summary", "evidence_class", "verification_status",
        "clinical_review_status",
    }
    for rule_id, item in (payload.get("rules") or {}).items():
        missing = sorted(required - set(item))
        if missing:
            issues.append(f"{rule_id}: missing {', '.join(missing)}")
            continue
        if not item.get("pages") or not all(isinstance(page, int) and page > 0 for page in item["pages"]):
            issues.append(f"{rule_id}: invalid pages")
        source_id = str(item.get("source_id") or "")
        if source_id not in (registry.get("sources") or {}):
            issues.append(f"{rule_id}: unknown source_id")
        elif not set(item.get("pages") or []).issubset(source_pages.get(source_id, set())):
            issues.append(f"{rule_id}: rule pages are outside source included_pages")

    active_payload = json.loads(RULE_PATH.read_text(encoding="utf-8"))
    active_ids = {str(rule.get("rule_id") or "") for rule in active_payload.get("rules", [])}
    registry_ids = set((registry.get("rules") or {}).keys())
    for missing_rule in sorted(active_ids - registry_ids):
        issues.append(f"{missing_rule}: active rule has no provenance")
    for stale_rule in sorted(registry_ids - active_ids):
        issues.append(f"{stale_rule}: provenance has no active rule")
    return issues
