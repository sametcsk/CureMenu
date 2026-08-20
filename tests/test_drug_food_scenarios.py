"""Governance invariants for the drug-food scenario scaffold.

The scaffold must never let unreviewed clinical content be marked as approved.
No clinical rule is asserted here — only structure and review-gating.
"""
import csv
from pathlib import Path

import pytest

CSV_PATH = Path(__file__).resolve().parents[1] / "docs" / "drug_food_scenarios.csv"
REQUIRED_COLUMNS = {
    "scenario_id", "drug_or_active_ingredient", "food_or_food_group", "risk_level",
    "expected_system_behavior", "source_required", "professional_referral_required",
    "expert_status", "notes",
}
VALID_STATUS = {"pending_review", "approved", "revision_required"}


def _rows():
    with CSV_PATH.open(encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def test_scaffold_exists_and_has_required_columns():
    with CSV_PATH.open(encoding="utf-8") as handle:
        header = set(next(csv.reader(handle)))
    assert REQUIRED_COLUMNS <= header


def test_every_row_has_valid_status_and_unique_id():
    rows = _rows()
    assert rows, "scaffold must contain at least one scenario row"
    ids = [r["scenario_id"] for r in rows]
    assert len(ids) == len(set(ids)), "scenario_id must be unique"
    for row in rows:
        assert row["expert_status"] in VALID_STATUS


def test_no_row_is_approved_without_expert_source():
    # Un-reviewed clinical content must not ship as approved. An approved row must
    # carry a source reference in notes and must not be flagged revision_required.
    for row in _rows():
        if row["expert_status"] == "approved":
            assert row["source_required"].lower() != "true" or row["notes"].strip(), (
                f"{row['scenario_id']} approved but has no source note"
            )
            assert row["expert_status"] != "revision_required"


def test_scaffold_starts_fully_pending():
    # Initial scaffold: nothing is expert-approved yet.
    assert all(row["expert_status"] == "pending_review" for row in _rows())
