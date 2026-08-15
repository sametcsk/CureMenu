"""Idempotent backfill for the AileUyesi.yakinlik field.

No SQL schema migration is required: a profile is stored as a JSON blob in
`profiles.profil_data`, and `yakinlik` is a new *optional* JSON field. Old records
that lack it parse fine and default to None (verified backward-compatible), so the
running app is never broken by their absence.

This script only *sets* `yakinlik` for a specific family member when it is
currently empty. It never overwrites an existing value, never touches other
fields, and never deletes or resets the database.

Usage:
  # report how many family members still have no yakinlik (safe = None):
  python -m scripts.backfill_family_yakinlik --check

  # set one member's relationship (idempotent):
  python -m scripts.backfill_family_yakinlik --telefon 05XXXXXXXXX --member <member_id> --yakinlik oğul
"""
from __future__ import annotations

import argparse
import json
import sqlite3

from src.config import settings
from src.models import KullaniciProfili


def _connect() -> sqlite3.Connection:
    return sqlite3.connect(settings.CUREMENU_DB_PATH)


def check() -> None:
    conn = _connect()
    total = missing = 0
    try:
        for _telefon, profil_data in conn.execute("SELECT telefon, profil_data FROM profiles"):
            try:
                data = json.loads(profil_data or "{}")
            except json.JSONDecodeError:
                continue
            for member in data.get("aile_uyeleri") or []:
                total += 1
                if not member.get("yakinlik"):
                    missing += 1
    finally:
        conn.close()
    print(f"family_members={total} without_yakinlik={missing} "
          "(None is backward-compatible and does not break the app)")


def backfill(telefon: str, member_id: str, yakinlik: str) -> None:
    conn = _connect()
    try:
        row = conn.execute("SELECT profil_data FROM profiles WHERE telefon = ?", (telefon,)).fetchone()
        if not row:
            print("account not found")
            return
        profile = KullaniciProfili.model_validate_json(row[0])
        changed = False
        for member in profile.aile_uyeleri:
            if member.id == member_id and not member.yakinlik:
                member.yakinlik = yakinlik
                changed = True
        if changed:
            conn.execute(
                "UPDATE profiles SET profil_data = ?, son_guncelleme = datetime('now') WHERE telefon = ?",
                (profile.model_dump_json(), telefon),
            )
            conn.commit()
            print(f"set yakinlik={yakinlik!r} for member={member_id}")
        else:
            print("no change (already set, or member not found) — idempotent no-op")
    finally:
        conn.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--telefon")
    parser.add_argument("--member")
    parser.add_argument("--yakinlik")
    args = parser.parse_args()
    if args.check or not (args.telefon and args.member and args.yakinlik):
        check()
    else:
        backfill(args.telefon, args.member, args.yakinlik)
