"""Compare local PDFs with source metadata persisted in a Chroma collection."""

from __future__ import annotations

import argparse
import json
import os
import sys
from collections import Counter
from pathlib import Path

import chromadb

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.config import settings


def _source_name(metadata: dict | None) -> str:
    source = str((metadata or {}).get("source") or "unknown")
    return os.path.basename(source.replace("\\", "/"))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("folder", type=Path)
    parser.add_argument("--collection", default="klinik_kutuphane")
    parser.add_argument("--output", type=Path, default=Path("outputs/rag_audit/chroma_source_audit.json"))
    args = parser.parse_args()

    client = chromadb.PersistentClient(path=settings.CHROMA_PERSIST_DIR)
    collection = client.get_collection(args.collection)
    payload = collection.get(include=["metadatas", "documents"])
    metadatas = payload.get("metadatas") or []
    documents = payload.get("documents") or []
    source_counts = Counter(_source_name(metadata) for metadata in metadatas)
    exact_chunk_counts = Counter((document or "").strip() for document in documents if (document or "").strip())
    local_names = {path.name for path in args.folder.glob("*.pdf")}
    persisted_names = set(source_counts)

    report = {
        "collection": args.collection,
        "chunk_count": collection.count(),
        "unique_source_count": len(source_counts),
        "local_pdf_count": len(local_names),
        "source_chunk_counts": dict(source_counts.most_common()),
        "persisted_only_sources": sorted(persisted_names - local_names, key=str.casefold),
        "local_only_sources": sorted(local_names - persisted_names, key=str.casefold),
        "duplicate_exact_chunk_instances": sum(count - 1 for count in exact_chunk_counts.values() if count > 1),
        "duplicate_exact_chunk_groups": sum(count > 1 for count in exact_chunk_counts.values()),
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
