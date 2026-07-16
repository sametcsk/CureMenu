"""Backward-compatible entry point for the versioned RAG ingestion command."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.ingest_rag import main


if __name__ == "__main__":
    main()
