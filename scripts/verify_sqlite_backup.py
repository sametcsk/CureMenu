"""Verify a SQLite backup without printing row contents."""

from __future__ import annotations

import argparse
import hashlib
import json
import sqlite3
from pathlib import Path


def _quote_identifier(name: str) -> str:
    return '"' + name.replace('"', '""') + '"'


def inspect_sqlite(path: Path) -> dict:
    resolved = path.resolve(strict=True)
    with resolved.open("rb") as database_file:
        digest = hashlib.file_digest(database_file, "sha256").hexdigest()
    connection = sqlite3.connect(f"file:{resolved.as_posix()}?mode=ro", uri=True)
    try:
        integrity = connection.execute("PRAGMA integrity_check").fetchone()[0]
        tables = [
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_master "
                "WHERE type = 'table' AND name NOT LIKE 'sqlite_%' ORDER BY name"
            )
        ]
        counts = {
            table: connection.execute(
                f"SELECT COUNT(*) FROM {_quote_identifier(table)}"
            ).fetchone()[0]
            for table in tables
        }
        revision = None
        if "alembic_version" in tables:
            row = connection.execute("SELECT version_num FROM alembic_version LIMIT 1").fetchone()
            revision = row[0] if row else None
    finally:
        connection.close()
    return {
        "path": str(resolved),
        "sha256": digest,
        "size_bytes": resolved.stat().st_size,
        "integrity": integrity,
        "revision": revision,
        "tables": tables,
        "record_counts": counts,
    }


def compare_snapshots(source: dict, backup: dict) -> list[str]:
    issues: list[str] = []
    if source["integrity"] != "ok":
        issues.append("source_integrity_failed")
    if backup["integrity"] != "ok":
        issues.append("backup_integrity_failed")
    if source["tables"] != backup["tables"]:
        issues.append("table_set_mismatch")
    if source["record_counts"] != backup["record_counts"]:
        issues.append("record_count_mismatch")
    if source["revision"] != backup["revision"]:
        issues.append("revision_mismatch")
    return issues


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify a CureMenu SQLite backup")
    parser.add_argument("--backup", required=True, type=Path)
    parser.add_argument("--source", type=Path)
    args = parser.parse_args()

    backup = inspect_sqlite(args.backup)
    issues = [] if backup["integrity"] == "ok" else ["backup_integrity_failed"]
    payload = {"backup": backup, "issues": issues}
    if args.source:
        source = inspect_sqlite(args.source)
        issues = compare_snapshots(source, backup)
        payload = {"source": source, "backup": backup, "issues": issues}
    print(json.dumps(payload, ensure_ascii=True, sort_keys=True))
    return 1 if issues else 0


if __name__ == "__main__":
    raise SystemExit(main())
