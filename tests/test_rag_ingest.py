import json

import fitz
import pytest
from langchain_core.documents import Document

from src.ingest_rag import build_collection, load_source_pages, split_documents


def test_rag_ingest_dry_run_skips_empty_pdf_and_keeps_safe_source_metadata(tmp_path):
    pdf_path = tmp_path / "clinical.pdf"
    pdf = fitz.open()
    page = pdf.new_page()
    page.insert_text((72, 72), "Warfarin ve vitamin K alimi dengeli tutulmalidir. " * 4)
    pdf.new_page()
    pdf.save(pdf_path)
    pdf.close()

    summary = build_collection(
        tmp_path,
        collection_name="test_clinical_v2",
        rebuild=False,
        manifest_path=tmp_path / "manifest.json",
        dry_run=True,
    )

    assert summary["source_count"] == 1
    assert summary["page_count"] == 1
    assert summary["chunk_count"] >= 1
    assert summary["sources"][0]["skipped_pages"] == 1
    assert str(tmp_path) not in (tmp_path / "manifest.json").read_text(encoding="utf-8")


def test_rag_chunk_ids_and_exact_content_deduplication_are_deterministic():
    first = Document(
        page_content="Celiac disease requires a strict gluten free diet. " * 8,
        metadata={"source": "a.pdf", "file_sha256": "a" * 64, "page": 1},
    )
    duplicate = Document(
        page_content=first.page_content,
        metadata={"source": "b.pdf", "file_sha256": "b" * 64, "page": 2},
    )

    chunks1, ids1 = split_documents([first, duplicate])
    chunks2, ids2 = split_documents([first, duplicate])

    assert len(chunks1) == len(chunks2) == 1
    assert ids1 == ids2


def test_load_source_pages_reports_ocr_requirement(tmp_path):
    pdf_path = tmp_path / "scan.pdf"
    pdf = fitz.open()
    pdf.new_page()
    pdf.save(pdf_path)
    pdf.close()

    documents, manifest = load_source_pages(tmp_path)

    assert documents == []
    assert manifest[0]["indexed_pages"] == 0
    assert "OCR required" in manifest[0]["warnings"][0]


def test_explicit_scope_indexes_only_allowlisted_pages_with_authority_metadata(tmp_path):
    pdf_path = tmp_path / "official.pdf"
    pdf = fitz.open()
    for page_number in range(1, 4):
        page = pdf.new_page()
        page.insert_text((72, 72), f"Official evidence page {page_number}. " * 8)
    pdf.save(pdf_path)
    pdf.close()

    documents, manifest = load_source_pages(
        tmp_path,
        source_scope={
            "official.pdf": {
                "included_pages": [2],
                "authority": "TEST_AUTHORITY",
                "authority_tier": 1,
                "source_role": "clinical_guideline",
                "source_url": "https://example.test/guideline.pdf",
            }
        },
        scope_version="scope:test-v1",
    )

    assert [document.metadata["page"] for document in documents] == [2]
    assert documents[0].metadata["authority_tier"] == 1
    assert documents[0].metadata["scope_version"] == "scope:test-v1"
    assert manifest[0]["out_of_scope_pages"] == 2


def test_registry_ingest_fails_closed_when_expected_source_is_missing(tmp_path):
    registry_path = tmp_path / "registry.json"
    registry_path.write_text(
        json.dumps({
            "schema_version": "clinical_evidence_registry:v1",
            "collection": "test_official",
            "sources": {
                "missing": {
                    "filename": "missing.pdf",
                    "url": "https://example.test/missing.pdf",
                    "sha256": "0" * 64,
                    "authority": "TEST",
                    "authority_tier": 1,
                    "source_role": "clinical_guideline",
                    "included_pages": [1],
                }
            },
        }),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="Evidence registry validation failed"):
        build_collection(
            tmp_path,
            collection_name="test_official",
            rebuild=False,
            manifest_path=tmp_path / "report.json",
            dry_run=True,
            registry_path=registry_path,
        )
