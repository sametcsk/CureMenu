"""Print retrieval distances and source distribution for representative queries."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

from langchain_chroma import Chroma

os.environ.setdefault("HF_HUB_OFFLINE", "1")
os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from src.memory import CHROMA_DIR, _get_embeddings
from src.quality.retrieval_filter import filter_retrieval_results


DEFAULT_QUERIES = [
    "warfarin ispanak K vitamini",
    "colyak gluten ekmek",
    "ciprofloxacin sut kalsiyum",
    "mor gezegen kuantum corbasi",
]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--collection", default="klinik_kutuphane")
    parser.add_argument("--limit", type=int, default=8)
    args = parser.parse_args()

    database = Chroma(
        collection_name=args.collection,
        embedding_function=_get_embeddings(),
        persist_directory=CHROMA_DIR,
    )
    print(json.dumps({"collection": args.collection, "count": database._collection.count()}))
    for query in DEFAULT_QUERIES:
        print(f"\nQUERY: {query}")
        raw_results = database.similarity_search_with_score(query, k=max(args.limit, 40))
        selected = filter_retrieval_results(query, raw_results, limit=args.limit)
        print(f"FILTERED_COUNT: {len(selected)}")
        for item in selected:
            document = item.document
            distance = item.distance
            print(json.dumps({
                "distance": round(float(distance), 4),
                "lexical_score": round(item.lexical_score, 4),
                "matched_terms": item.matched_terms,
                "source": document.metadata.get("source"),
                "page": document.metadata.get("page"),
                "preview": document.page_content[:120].replace("\n", " "),
            }, ensure_ascii=False))


if __name__ == "__main__":
    main()
