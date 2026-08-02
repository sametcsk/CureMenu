"""Initialize persistent staging state before starting the web process."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import chromadb

from scripts.sync_clinical_evidence import sync_evidence
from src.config import settings


PERSIST_ROOT = Path(settings.CUREMENU_DB_PATH).resolve().parent
EVIDENCE_SOURCE_DIR = PERSIST_ROOT / "official_evidence"
EVIDENCE_REPORT = PERSIST_ROOT / "clinical_evidence_sync.json"


def _upgrade_database() -> None:
    subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        check=True,
    )


def _official_evidence_is_ready() -> bool:
    try:
        client = chromadb.PersistentClient(path=settings.CHROMA_PERSIST_DIR)
        collection = client.get_collection(settings.CLINICAL_OFFICIAL_RAG_COLLECTION)
        return int(collection.count()) > 0
    except (ValueError, OSError):
        return False


def _bootstrap_official_evidence() -> None:
    if _official_evidence_is_ready():
        return

    report = sync_evidence(
        source_dir=EVIDENCE_SOURCE_DIR,
        report_path=EVIDENCE_REPORT,
        download=True,
        rebuild=True,
    )
    if report.get("status") != "passed":
        raise RuntimeError("Official evidence bootstrap failed closed.")


def main() -> int:
    PERSIST_ROOT.mkdir(parents=True, exist_ok=True)
    _upgrade_database()
    _bootstrap_official_evidence()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
