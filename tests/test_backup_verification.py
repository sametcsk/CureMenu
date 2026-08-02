import sqlite3

from scripts.verify_sqlite_backup import compare_snapshots, inspect_sqlite


def _create_database(path):
    connection = sqlite3.connect(path)
    connection.executescript(
        """
        CREATE TABLE alembic_version (version_num TEXT NOT NULL);
        INSERT INTO alembic_version VALUES ('20260715_0002');
        CREATE TABLE sample_records (id INTEGER PRIMARY KEY, value TEXT);
        INSERT INTO sample_records (value) VALUES ('synthetic');
        """
    )
    connection.commit()
    return connection


def test_sqlite_backup_verification_compares_only_structural_metadata(tmp_path):
    source_path = tmp_path / "source.db"
    backup_path = tmp_path / "backup.db"
    source = _create_database(source_path)
    backup = sqlite3.connect(backup_path)
    source.backup(backup)
    backup.close()
    source.close()

    source_snapshot = inspect_sqlite(source_path)
    backup_snapshot = inspect_sqlite(backup_path)

    assert source_snapshot["integrity"] == "ok"
    assert backup_snapshot["integrity"] == "ok"
    assert source_snapshot["revision"] == "20260715_0002"
    assert compare_snapshots(source_snapshot, backup_snapshot) == []
    assert "synthetic" not in str(backup_snapshot)


def test_sqlite_backup_verification_detects_record_count_mismatch(tmp_path):
    source_path = tmp_path / "source.db"
    backup_path = tmp_path / "backup.db"
    source = _create_database(source_path)
    backup = sqlite3.connect(backup_path)
    source.backup(backup)
    backup.execute("DELETE FROM sample_records")
    backup.commit()
    backup.close()
    source.close()

    issues = compare_snapshots(inspect_sqlite(source_path), inspect_sqlite(backup_path))

    assert "record_count_mismatch" in issues
