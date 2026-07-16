"""add persistent refresh token revocation table

Revision ID: 20260715_0002
Revises: 20260706_0001
Create Date: 2026-07-15
"""

from __future__ import annotations

from alembic import op


revision = "20260715_0002"
down_revision = "20260706_0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS revoked_refresh_tokens (
            jti_hash TEXT PRIMARY KEY,
            expires_at INTEGER NOT NULL,
            revoked_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_revoked_refresh_tokens_expires_at
        ON revoked_refresh_tokens(expires_at)
        """
    )


def downgrade() -> None:
    # Security records are intentionally retained; no destructive downgrade.
    pass
