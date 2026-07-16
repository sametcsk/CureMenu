import hashlib
import json

import fitz

from scripts.sync_clinical_evidence import (
    download_and_verify,
    inspect_pdf,
    sync_evidence,
)


def _pdf_bytes(text: str) -> bytes:
    pdf = fitz.open()
    page = pdf.new_page()
    page.insert_text((72, 72), text)
    content = pdf.tobytes()
    pdf.close()
    return content


def _write_registry(tmp_path, pdf_content: bytes):
    source_dir = tmp_path / "sources"
    source_dir.mkdir()
    pdf_path = source_dir / "official.pdf"
    pdf_path.write_bytes(pdf_content)
    digest = hashlib.sha256(pdf_content).hexdigest().upper()
    registry = {
        "schema_version": "clinical_evidence_registry:v1",
        "collection": "test_official_evidence",
        "last_source_check": "2026-07-15",
        "clinical_review_required": True,
        "sources": {
            "official": {
                "filename": "official.pdf",
                "url": "https://example.test/official.pdf",
                "sha256": digest,
                "authority": "TEST",
                "authority_tier": 1,
                "source_role": "regulatory_label",
                "included_pages": [1],
                "discovery_terms": ["warfarin"],
            }
        },
        "rules": {
            "test-rule:v1": {
                "source_id": "official",
                "pages": [1],
                "sections": ["Test"],
                "evidence_summary": "Test evidence.",
                "evidence_class": "regulatory_label",
                "verification_status": "source_verified",
                "clinical_review_status": "pending",
            }
        },
    }
    registry_path = tmp_path / "registry.json"
    registry_path.write_text(json.dumps(registry), encoding="utf-8")
    rule_path = tmp_path / "rules.json"
    rule_path.write_text(json.dumps({"rules": [{"rule_id": "test-rule:v1"}]}), encoding="utf-8")
    return registry_path, source_dir, rule_path, registry


def test_inspect_pdf_rejects_html_disguised_as_pdf(tmp_path):
    path = tmp_path / "fake.pdf"
    path.write_text("<html>not a pdf</html>", encoding="utf-8")

    result = inspect_pdf(path, {"filename": path.name, "sha256": "0" * 64, "included_pages": [1]})

    assert result["status"] == "invalid"
    assert "not_pdf" in result["issues"]


def test_changed_remote_hash_fails_closed_without_overwriting_local_pdf(tmp_path):
    original = _pdf_bytes("Warfarin evidence text. " * 8)
    changed = _pdf_bytes("Changed upstream evidence text. " * 8)
    target = tmp_path / "official.pdf"
    target.write_bytes(original)
    source = {
        "filename": target.name,
        "url": "https://example.test/official.pdf",
        "sha256": hashlib.sha256(original).hexdigest().upper(),
        "included_pages": [1],
    }

    class FakeResponse:
        def raise_for_status(self):
            return None

        def iter_content(self, chunk_size):
            return [changed]

        def close(self):
            return None

    result = download_and_verify(source, target, get=lambda *args, **kwargs: FakeResponse())

    assert result["status"] == "invalid"
    assert "hash_changed" in result["issues"]
    assert target.read_bytes() == original


def test_sync_verifies_registry_without_claiming_clinical_validation(tmp_path):
    pdf_content = _pdf_bytes("Warfarin official source text for deterministic checking. " * 8)
    registry_path, source_dir, rule_path, _ = _write_registry(tmp_path, pdf_content)
    report_path = tmp_path / "sync-report.json"

    report = sync_evidence(
        registry_path=registry_path,
        source_dir=source_dir,
        report_path=report_path,
        rule_path=rule_path,
        discover_pages=True,
    )

    assert report["status"] == "passed"
    assert report["source_count"] == 1
    assert report["rule_count"] == 1
    assert report["clinical_review_required"] is True
    assert report["clinical_validation"] == "not_established"
    assert report["sources"]["official"]["candidate_pages"][0]["page"] == 1
    assert report_path.is_file()
