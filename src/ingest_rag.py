"""Build a versioned, reproducible clinical RAG collection from local documents."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

if "--offline" in sys.argv:
    os.environ.setdefault("HF_HUB_OFFLINE", "1")
    os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")

import fitz
from langchain_chroma import Chroma
from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter

from src.config import settings
from src.logger import get_logger
from src.memory import _get_embeddings


logger = get_logger(__name__)
DEFAULT_COLLECTION = "klinik_kutuphane_v2"
DEFAULT_SOURCE_POLICY_PATH = Path(__file__).resolve().parents[1] / "data" / "rag_source_policy.json"
DEFAULT_EVIDENCE_REGISTRY_PATH = Path(__file__).resolve().parents[1] / "data" / "clinical_evidence_registry.json"


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _document_id(document: Document, chunk_index: int) -> str:
    metadata = document.metadata
    identity = ":".join(
        [
            str(metadata.get("file_sha256") or ""),
            str(metadata.get("page") or ""),
            str(chunk_index),
            hashlib.sha256(document.page_content.encode("utf-8")).hexdigest(),
        ]
    )
    return hashlib.sha256(identity.encode("utf-8")).hexdigest()


def load_source_policy(path: Path = DEFAULT_SOURCE_POLICY_PATH) -> dict[str, str]:
    if not path.exists():
        return {}
    payload = json.loads(path.read_text(encoding="utf-8"))
    return {
        str(filename).casefold(): str(reason)
        for filename, reason in (payload.get("excluded_sources") or {}).items()
    }


def load_source_scope(path: Path) -> tuple[str, dict[str, dict]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    return (
        str(payload.get("version", "official_clinical_scope:unknown")),
        {
            str(filename).casefold(): dict(metadata)
            for filename, metadata in (payload.get("sources") or {}).items()
        },
    )


def load_evidence_registry(path: Path = DEFAULT_EVIDENCE_REGISTRY_PATH) -> tuple[str, str, dict[str, dict]]:
    """Load the canonical evidence registry as an ingest page allowlist."""
    payload = json.loads(path.read_text(encoding="utf-8"))
    sources: dict[str, dict] = {}
    for source_id, source in (payload.get("sources") or {}).items():
        filename = str(source.get("filename") or "").strip()
        if not filename:
            continue
        sources[filename.casefold()] = {
            "source_id": source_id,
            "included_pages": list(source.get("included_pages") or []),
            "authority": source.get("authority"),
            "authority_tier": source.get("authority_tier", 1),
            "source_role": source.get("source_role"),
            "source_url": source.get("url"),
            "expected_sha256": source.get("sha256"),
        }
    return (
        str(payload.get("schema_version", "clinical_evidence_registry:unknown")),
        str(payload.get("collection", "")),
        sources,
    )


def _page_metadata(path: Path, file_hash: str, page_number: int, scope: dict | None, scope_version: str | None) -> dict:
    metadata = {
        "source": path.name,
        "source_id": file_hash,
        "file_sha256": file_hash,
        "page": page_number,
        "page_label": str(page_number),
        "authority_tier": 3,
    }
    if scope:
        metadata.update({
            "authority": str(scope.get("authority") or ""),
            "authority_tier": int(scope.get("authority_tier", 1)),
            "source_role": str(scope.get("source_role") or ""),
            "source_url": str(scope.get("source_url") or ""),
            "scope_version": str(scope_version or ""),
            "registry_source_id": str(scope.get("source_id") or ""),
        })
    return metadata


def load_source_pages(
    folder: Path,
    excluded_sources: dict[str, str] | None = None,
    *,
    source_scope: dict[str, dict] | None = None,
    scope_version: str | None = None,
) -> tuple[list[Document], list[dict]]:
    documents: list[Document] = []
    manifest: list[dict] = []
    excluded_sources = excluded_sources or {}
    for path in sorted(folder.iterdir(), key=lambda item: item.name.casefold()):
        if path.suffix.casefold() not in {".pdf", ".txt"}:
            continue
        file_hash = _file_sha256(path)
        record = {
            "filename": path.name,
            "sha256": file_hash,
            "type": path.suffix.casefold().lstrip("."),
            "pages": 0,
            "indexed_pages": 0,
            "skipped_pages": 0,
            "text_chars": 0,
            "warnings": [],
        }
        scope = source_scope.get(path.name.casefold()) if source_scope is not None else None
        if source_scope is not None and scope is None:
            record["excluded"] = True
            record["warnings"].append("Source is not present in the explicit scope allowlist.")
            manifest.append(record)
            continue
        allowed_pages = {int(page) for page in (scope or {}).get("included_pages", [])}
        if scope:
            expected_hash = str(scope.get("expected_sha256") or "").lower()
            if expected_hash and file_hash.lower() != expected_hash:
                record["excluded"] = True
                record["warnings"].append("Source hash does not match the evidence registry.")
                manifest.append(record)
                continue
            record["included_pages"] = sorted(allowed_pages)
            record["authority"] = scope.get("authority")
            record["authority_tier"] = scope.get("authority_tier")
            record["source_role"] = scope.get("source_role")
            record["scope_version"] = scope_version
            record["out_of_scope_pages"] = 0
        exclusion_reason = excluded_sources.get(path.name.casefold())
        if exclusion_reason:
            record["excluded"] = True
            record["warnings"].append(exclusion_reason)
            manifest.append(record)
            continue
        try:
            if path.suffix.casefold() == ".txt":
                text = path.read_text(encoding="utf-8").strip()
                record["pages"] = 1
                record["text_chars"] = len(text)
                if len(text) >= 40:
                    documents.append(Document(
                        page_content=text,
                        metadata=_page_metadata(path, file_hash, 1, scope, scope_version),
                    ))
                    record["indexed_pages"] = 1
                else:
                    record["skipped_pages"] = 1
                    record["warnings"].append("No meaningful extractable text.")
            else:
                pdf = fitz.open(path)
                record["pages"] = pdf.page_count
                for page_index, page in enumerate(pdf):
                    page_number = page_index + 1
                    if allowed_pages and page_number not in allowed_pages:
                        record["out_of_scope_pages"] += 1
                        continue
                    text = (page.get_text("text") or "").strip()
                    record["text_chars"] += len(text)
                    if len(text) < 40:
                        record["skipped_pages"] += 1
                        continue
                    documents.append(Document(
                        page_content=text,
                        metadata=_page_metadata(path, file_hash, page_number, scope, scope_version),
                    ))
                    record["indexed_pages"] += 1
                pdf.close()
                if record["indexed_pages"] == 0:
                    record["warnings"].append("OCR required; document was not indexed.")
                elif record["skipped_pages"]:
                    record["warnings"].append("Some pages require OCR and were skipped.")
        except Exception as exc:
            record["warnings"].append(f"Read failed: {type(exc).__name__}")
            logger.warning("RAG source could not be read: %s (%s)", path.name, type(exc).__name__)
        manifest.append(record)
    return documents, manifest


def split_documents(documents: list[Document]) -> tuple[list[Document], list[str]]:
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=1200,
        chunk_overlap=180,
        separators=["\n\n", "\n", ". ", " ", ""],
    )
    chunks: list[Document] = []
    ids: list[str] = []
    seen_content: set[str] = set()
    for document in documents:
        for chunk_index, chunk in enumerate(splitter.split_documents([document])):
            normalized_content = " ".join(chunk.page_content.split())
            content_hash = hashlib.sha256(normalized_content.encode("utf-8")).hexdigest()
            if content_hash in seen_content:
                continue
            seen_content.add(content_hash)
            chunk.metadata["chunk_sha256"] = content_hash
            chunk.metadata["indexed_at"] = datetime.now(timezone.utc).isoformat()
            chunks.append(chunk)
            ids.append(_document_id(chunk, chunk_index))
    return chunks, ids


def build_collection(
    folder: Path,
    *,
    collection_name: str,
    rebuild: bool,
    manifest_path: Path,
    dry_run: bool = False,
    scope_path: Path | None = None,
    registry_path: Path | None = None,
) -> dict:
    if not folder.is_dir():
        raise ValueError(f"RAG folder not found: {folder}")
    scope_version = None
    source_scope = None
    registry_collection = None
    if registry_path is not None:
        scope_version, registry_collection, source_scope = load_evidence_registry(registry_path)
        if registry_collection and collection_name != registry_collection:
            logger.warning(
                "Collection %s differs from registry collection %s",
                collection_name,
                registry_collection,
            )
    elif scope_path is not None:
        scope_version, source_scope = load_source_scope(scope_path)
    pages, manifest = load_source_pages(
        folder,
        load_source_policy(),
        source_scope=source_scope,
        scope_version=scope_version,
    )
    if registry_path is not None and source_scope is not None:
        accepted = {
            str(source["filename"]).casefold()
            for source in manifest
            if not source.get("excluded") and source.get("indexed_pages", 0) > 0
        }
        missing_or_invalid = sorted(set(source_scope) - accepted)
        if missing_or_invalid:
            raise ValueError(
                "Evidence registry validation failed for: " + ", ".join(missing_or_invalid)
            )
    chunks, ids = split_documents(pages)
    chunk_counts = Counter(str(chunk.metadata.get("source") or "") for chunk in chunks)
    for source in manifest:
        source["chunks"] = chunk_counts.get(source["filename"], 0)
        if source["indexed_pages"] and source["chunks"] == 0:
            source["warnings"].append("All extracted content duplicated another indexed source.")
    summary = {
        "collection": collection_name,
        "source_count": len(manifest),
        "page_count": len(pages),
        "chunk_count": len(chunks),
        "dry_run": dry_run,
        "scope_version": scope_version,
        "registry_collection": registry_collection,
        "sources": manifest,
    }
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    if dry_run:
        return summary

    database = Chroma(
        collection_name=collection_name,
        embedding_function=_get_embeddings(),
        persist_directory=settings.CHROMA_PERSIST_DIR,
    )
    if rebuild:
        try:
            database.delete_collection()
        except ValueError:
            pass
        database = Chroma(
            collection_name=collection_name,
            embedding_function=_get_embeddings(),
            persist_directory=settings.CHROMA_PERSIST_DIR,
        )

    batch_size = 64
    for start in range(0, len(chunks), batch_size):
        database.add_documents(
            documents=chunks[start:start + batch_size],
            ids=ids[start:start + batch_size],
        )
        logger.info("Indexed %d/%d clinical chunks", min(start + batch_size, len(chunks)), len(chunks))
    summary["persisted_count"] = database._collection.count()
    return summary


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("folder", nargs="?", type=Path, default=os.getenv("RAG_FOLDER"))
    parser.add_argument("--collection", default=os.getenv("CLINICAL_RAG_COLLECTION", DEFAULT_COLLECTION))
    parser.add_argument("--manifest", type=Path, default=Path("outputs/rag_audit/ingest_manifest.json"))
    parser.add_argument("--rebuild", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--offline", action="store_true")
    parser.add_argument("--scope", type=Path)
    parser.add_argument("--registry", type=Path)
    args = parser.parse_args()
    if args.folder is None:
        parser.error("folder is required unless RAG_FOLDER is set")
    if args.offline:
        os.environ["HF_HUB_OFFLINE"] = "1"
        os.environ["TRANSFORMERS_OFFLINE"] = "1"
    summary = build_collection(
        args.folder,
        collection_name=args.collection,
        rebuild=args.rebuild,
        manifest_path=args.manifest,
        dry_run=args.dry_run,
        scope_path=args.scope,
        registry_path=args.registry,
    )
    print(json.dumps({key: value for key, value in summary.items() if key != "sources"}, ensure_ascii=False))


if __name__ == "__main__":
    main()
