"""manual SQLite baseline for existing CureMenu schema

Revision ID: 20260706_0001
Revises:
Create Date: 2026-07-06
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op


revision = "20260706_0001"
down_revision = None
branch_labels = None
depends_on = None


def _column_exists(table_name: str, column_name: str) -> bool:
    connection = op.get_bind()
    rows = connection.exec_driver_sql(f"PRAGMA table_info({table_name})").fetchall()
    return any(row[1] == column_name for row in rows)


def _add_column_if_missing(table_name: str, column: sa.Column) -> None:
    if not _column_exists(table_name, column.name):
        op.add_column(table_name, column)


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS profiles (
            telefon TEXT PRIMARY KEY,
            kullanici_adi TEXT,
            sifre_hash TEXT,
            profil_data TEXT,
            kayit_tarihi TEXT DEFAULT CURRENT_TIMESTAMP,
            son_guncelleme TEXT DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    _add_column_if_missing("profiles", sa.Column("sifre_hash", sa.Text()))

    op.execute(
        """
        CREATE TABLE IF NOT EXISTS interaction_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            telefon TEXT,
            kullanici_adi TEXT,
            sayfa TEXT,
            istek TEXT,
            cevap TEXT,
            metadata TEXT,
            tarih TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (telefon) REFERENCES profiles(telefon)
        )
        """
    )
    _add_column_if_missing("interaction_logs", sa.Column("metadata", sa.Text()))

    op.execute(
        """
        CREATE TABLE IF NOT EXISTS icd11_cache (
            cache_key TEXT PRIMARY KEY,
            sonuc TEXT
        )
        """
    )

    op.execute(
        """
        CREATE TABLE IF NOT EXISTS clinical_decisions (
            decision_id TEXT PRIMARY KEY,
            telefon TEXT,
            kimin_icin TEXT,
            istek TEXT,
            final_answer TEXT,
            final_action TEXT,
            risk_score REAL,
            confidence_score REAL,
            confidence_data TEXT,
            component_versions TEXT,
            citations TEXT,
            created_at TEXT,
            completed_at TEXT,
            FOREIGN KEY (telefon) REFERENCES profiles(telefon)
        )
        """
    )

    op.execute(
        """
        CREATE TABLE IF NOT EXISTS decision_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            decision_id TEXT,
            sequence_no INTEGER,
            event_type TEXT,
            component TEXT,
            status TEXT,
            metadata TEXT,
            created_at TEXT,
            FOREIGN KEY (decision_id) REFERENCES clinical_decisions(decision_id)
        )
        """
    )


def downgrade() -> None:
    # Baseline downgrade is intentionally non-destructive for existing SQLite data.
    pass
