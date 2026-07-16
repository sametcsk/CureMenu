"""Verify, download and optionally rebuild the scoped clinical evidence collection."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

import fitz
import requests


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

DEFAULT_REGISTRY = PROJECT_ROOT / "data" / "clinical_evidence_registry.json"
DEFAULT_SOURCE_DIR = PROJECT_ROOT / "data" / "rag_candidates" / "official"
DEFAULT_RULE_PATH = PROJECT_ROOT / "src" / "medical_knowledge" / "data" / "high_risk_medications.json"
DEFAULT_REPORT = PROJECT_ROOT / "outputs" / "rag_audit" / "clinical_evidence_sync.json"
MAX_PDF_BYTES = 50 * 1024 * 1024


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest().upper()


def load_registry(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def validate_registry_structure(registry: dict[str, Any], rule_path: Path = DEFAULT_RULE_PATH) -> list[str]:
    issues: list[str] = []
    if registry.get("schema_version") != "clinical_evidence_registry:v1":
        issues.append("registry: unsupported schema_version")
    if registry.get("clinical_review_required") is not True:
        issues.append("registry: clinical_review_required must be true")
    if not registry.get("collection"):
        issues.append("registry: collection missing")

    sources = registry.get("sources") or {}
    filenames: set[str] = set()
    required_source_fields = {
        "filename", "url", "sha256", "authority", "authority_tier",
        "source_role", "included_pages",
    }
    for source_id, source in sources.items():
        missing = sorted(required_source_fields - set(source))
        if missing:
            issues.append(f"{source_id}: missing {', '.join(missing)}")
            continue
        filename = str(source["filename"]).casefold()
        if filename in filenames:
            issues.append(f"{source_id}: duplicate filename")
        filenames.add(filename)
        pages = source.get("included_pages") or []
        if not pages or not all(isinstance(page, int) and page > 0 for page in pages):
            issues.append(f"{source_id}: invalid included_pages")

    registry_rule_ids = set((registry.get("rules") or {}).keys())
    for rule_id, rule in (registry.get("rules") or {}).items():
        source_id = str(rule.get("source_id") or "")
        source = sources.get(source_id)
        if not source:
            issues.append(f"{rule_id}: unknown source_id")
            continue
        pages = rule.get("pages") or []
        if not pages or not set(pages).issubset(set(source.get("included_pages") or [])):
            issues.append(f"{rule_id}: rule pages are outside source included_pages")
        for field in ("sections", "evidence_summary", "evidence_class", "verification_status", "clinical_review_status"):
            if not rule.get(field):
                issues.append(f"{rule_id}: {field} missing")

    if rule_path.is_file():
        active = json.loads(rule_path.read_text(encoding="utf-8"))
        active_ids = {str(rule.get("rule_id") or "") for rule in active.get("rules", [])}
        for rule_id in sorted(active_ids - registry_rule_ids):
            issues.append(f"{rule_id}: active rule has no registry evidence")
        for rule_id in sorted(registry_rule_ids - active_ids):
            issues.append(f"{rule_id}: registry evidence has no active rule")
    return issues


def inspect_pdf(path: Path, source: dict[str, Any]) -> dict[str, Any]:
    result: dict[str, Any] = {
        "filename": source.get("filename"),
        "status": "invalid",
        "issues": [],
    }
    if not path.is_file():
        result["issues"].append("file_missing")
        return result
    if path.stat().st_size > MAX_PDF_BYTES:
        result["issues"].append("file_too_large")
        return result
    with path.open("rb") as handle:
        if handle.read(5) != b"%PDF-":
            result["issues"].append("not_pdf")
            return result

    actual_hash = file_sha256(path)
    result["actual_sha256"] = actual_hash
    if actual_hash != str(source.get("sha256") or "").upper():
        result["issues"].append("hash_changed")
        return result
    try:
        with fitz.open(path) as pdf:
            result["page_count"] = pdf.page_count
            for page_number in source.get("included_pages") or []:
                if page_number > pdf.page_count:
                    result["issues"].append(f"page_out_of_range:{page_number}")
                    continue
                text = (pdf[page_number - 1].get_text("text") or "").strip()
                if len(text) < 40:
                    result["issues"].append(f"page_without_text:{page_number}")
    except Exception as exc:
        result["issues"].append(f"pdf_read_failed:{type(exc).__name__}")
    if not result["issues"]:
        result["status"] = "verified"
    return result


def download_and_verify(
    source: dict[str, Any],
    target: Path,
    *,
    get: Callable[..., Any] | None = None,
) -> dict[str, Any]:
    """Download to a temporary file and promote only an exact verified match."""
    getter = get or requests.get
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_name(f".{target.name}.download")
    temporary.unlink(missing_ok=True)
    result: dict[str, Any] = {"status": "download_failed", "issues": []}
    response = None
    try:
        response = getter(
            str(source["url"]),
            stream=True,
            timeout=(5, 30),
            headers={"User-Agent": "CureMenu-Evidence-Sync/1.0"},
        )
        response.raise_for_status()
        size = 0
        with temporary.open("wb") as handle:
            for chunk in response.iter_content(chunk_size=64 * 1024):
                if not chunk:
                    continue
                size += len(chunk)
                if size > MAX_PDF_BYTES:
                    raise ValueError("download_too_large")
                handle.write(chunk)
        inspection = inspect_pdf(temporary, source)
        result.update(inspection)
        if inspection["status"] != "verified":
            return result
        existed = target.exists()
        os.replace(temporary, target)
        result["status"] = "remote_verified" if existed else "downloaded"
        return result
    except (requests.RequestException, OSError, ValueError) as exc:
        result["issues"].append(type(exc).__name__)
        return result
    finally:
        temporary.unlink(missing_ok=True)
        if response is not None and hasattr(response, "close"):
            response.close()


def discover_candidate_pages(path: Path, source: dict[str, Any], limit: int = 5) -> list[dict[str, Any]]:
    terms = [str(term).casefold() for term in source.get("discovery_terms") or [] if str(term).strip()]
    if not terms or not path.is_file():
        return []
    included = set(source.get("included_pages") or [])
    candidates: list[dict[str, Any]] = []
    with fitz.open(path) as pdf:
        for index, page in enumerate(pdf):
            text = (page.get_text("text") or "").casefold()
            score = sum(text.count(term) for term in terms)
            if score:
                candidates.append({"page": index + 1, "score": score, "included": index + 1 in included})
    return sorted(candidates, key=lambda item: (-item["score"], item["page"]))[:limit]


def sync_evidence(
    *,
    registry_path: Path = DEFAULT_REGISTRY,
    source_dir: Path = DEFAULT_SOURCE_DIR,
    report_path: Path = DEFAULT_REPORT,
    rule_path: Path = DEFAULT_RULE_PATH,
    download: bool = False,
    rebuild: bool = False,
    discover_pages: bool = False,
) -> dict[str, Any]:
    registry = load_registry(registry_path)
    issues = validate_registry_structure(registry, rule_path)
    source_reports: dict[str, dict[str, Any]] = {}
    for source_id, source in (registry.get("sources") or {}).items():
        path = source_dir / str(source.get("filename") or "")
        download_report = download_and_verify(source, path) if download else None
        local_report = inspect_pdf(path, source)
        if download_report is not None:
            local_report["download"] = download_report["status"]
            if download_report.get("issues"):
                local_report["download_issues"] = download_report["issues"]
                issues.append(f"{source_id}: remote verification failed")
        if local_report["status"] != "verified":
            issues.extend(f"{source_id}: {item}" for item in local_report["issues"])
        if discover_pages and local_report["status"] == "verified":
            local_report["candidate_pages"] = discover_candidate_pages(path, source)
        source_reports[source_id] = local_report

    ingest_summary = None
    if rebuild and not issues:
        from src.ingest_rag import build_collection

        ingest_summary = build_collection(
            source_dir,
            collection_name=str(registry["collection"]),
            rebuild=True,
            manifest_path=report_path,
            registry_path=registry_path,
        )

    report = {
        "status": "passed" if not issues else "failed",
        "checked_at": datetime.now(timezone.utc).isoformat(),
        "schema_version": registry.get("schema_version"),
        "collection": registry.get("collection"),
        "clinical_review_required": registry.get("clinical_review_required"),
        "clinical_validation": "not_established",
        "source_count": len(source_reports),
        "rule_count": len(registry.get("rules") or {}),
        "issues": issues,
        "sources": source_reports,
        "ingest": ingest_summary,
    }
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--registry", type=Path, default=DEFAULT_REGISTRY)
    parser.add_argument("--source-dir", type=Path, default=DEFAULT_SOURCE_DIR)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    parser.add_argument("--rule-path", type=Path, default=DEFAULT_RULE_PATH)
    parser.add_argument("--download", action="store_true", help="Verify remote PDFs without accepting changed hashes")
    parser.add_argument("--check-only", action="store_true", help="Verify local evidence without rebuilding Chroma")
    parser.add_argument("--rebuild", action="store_true", help="Rebuild the scoped Chroma collection after verification")
    parser.add_argument("--discover-pages", action="store_true", help="Report likely evidence pages for human review")
    args = parser.parse_args()
    if args.check_only and args.rebuild:
        parser.error("--check-only and --rebuild cannot be used together")
    report = sync_evidence(
        registry_path=args.registry,
        source_dir=args.source_dir,
        report_path=args.report,
        rule_path=args.rule_path,
        download=args.download,
        rebuild=args.rebuild,
        discover_pages=args.discover_pages,
    )
    print(json.dumps({key: value for key, value in report.items() if key not in {"sources", "ingest"}}, ensure_ascii=False))
    return 0 if report["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
