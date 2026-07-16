from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any

from src.config import settings
from src.logger import get_logger
from src.medical_knowledge.provenance import load_evidence_registry, validate_rule_provenance

logger = get_logger(__name__)


def _safe_check(name: str, fn) -> dict[str, Any]:
    try:
        return fn()
    except Exception as exc:
        logger.warning("Readiness check failed: %s (%s)", name, type(exc).__name__)
        return {"ok": False, "error": "check_failed"}


def _check_config() -> dict[str, Any]:
    settings.validate_startup_security()
    return {"ok": True, "environment": settings.APP_ENV}


def _expected_alembic_head() -> str | None:
    try:
        from alembic.config import Config
        from alembic.script import ScriptDirectory

        root = Path(__file__).resolve().parents[1]
        config_path = root / "alembic.ini"
        if not config_path.is_file():
            return None
        script = ScriptDirectory.from_config(Config(str(config_path)))
        return script.get_current_head()
    except Exception as exc:
        logger.warning("Alembic head check skipped (%s)", type(exc).__name__)
        return None


def _check_database() -> dict[str, Any]:
    db_path = settings.CUREMENU_DB_PATH
    if db_path != ":memory:" and not Path(db_path).is_file():
        return {"ok": False, "error": "database_missing"}

    with sqlite3.connect(db_path, timeout=settings.CUREMENU_DB_TIMEOUT) as connection:
        connection.execute("SELECT 1").fetchone()
        row = connection.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='alembic_version'"
        ).fetchone()
        current_revision = None
        if row:
            version_row = connection.execute("SELECT version_num FROM alembic_version LIMIT 1").fetchone()
            current_revision = version_row[0] if version_row else None

    expected_head = _expected_alembic_head()
    migration_ok = bool(current_revision and expected_head and current_revision == expected_head)
    if settings.is_production and expected_head and not migration_ok:
        return {"ok": False, "error": "migration_not_current"}

    return {
        "ok": True,
        "migration_current": migration_ok,
        "current_revision": current_revision,
        "expected_head": expected_head,
    }


def _check_registry() -> dict[str, Any]:
    issues = validate_rule_provenance(verify_files=False)
    if issues:
        return {"ok": False, "error": "registry_invalid", "issue_count": len(issues)}
    registry = load_evidence_registry()
    return {
        "ok": True,
        "schema_version": registry.get("schema_version"),
        "source_count": len(registry.get("sources") or {}),
        "rule_count": len(registry.get("rules") or {}),
    }


def _check_chroma() -> dict[str, Any]:
    import chromadb

    client = chromadb.PersistentClient(path=settings.CHROMA_PERSIST_DIR)
    collection = client.get_collection(settings.CLINICAL_OFFICIAL_RAG_COLLECTION)
    count = int(collection.count())
    if count <= 0:
        return {"ok": False, "error": "official_evidence_empty"}
    return {"ok": True, "collection": settings.CLINICAL_OFFICIAL_RAG_COLLECTION, "count": count}


def collect_readiness() -> dict[str, Any]:
    checks = {
        "config": _safe_check("config", _check_config),
        "database": _safe_check("database", _check_database),
        "clinical_evidence_registry": _safe_check("clinical_evidence_registry", _check_registry),
        "clinical_evidence_store": _safe_check("clinical_evidence_store", _check_chroma),
    }
    ready = all(bool(item.get("ok")) for item in checks.values())
    return {"ready": ready, "checks": checks}
