"""Internal Beta Operations & Quality dashboard API (READ-ONLY, admin-only).

This is NOT an end-user feature. It gives the founder/admin a privacy-preserving
window into product usage and CureMenu output quality during closed beta.

Guarantees enforced here:
  * Admin bearer token required (shared `require_admin`); fails closed to 403.
  * Read-only: every query is a SELECT. No insert/update/delete.
  * No raw identity leaves the server: phone and real names are never
    serialized. Users are shown as a deterministic keyed-HMAC pseudonym.
  * Interaction metadata passes through a strict SAFE ALLOWLIST; identity and
    raw health fields (target_name/key/id, raw objects) are dropped.
  * This module never widens data collection; it only reads what the product
    already persisted (already redacted at write time by `etkilesim_logla`).
"""
from __future__ import annotations

import hashlib
import hmac
import json
import sqlite3
from collections import Counter
from typing import Any

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse

from src.admin_auth import require_admin
from src.config import settings
from src.database import (
    beta_curebot_metadata,
    beta_distinct_telefonlar,
    beta_interactions_ara,
    beta_konusma_kayitlari,
    beta_modul_ozet,
    beta_zaman_serisi,
    get_db,
)
from src.logger import get_logger
from src.routers.chat import CHAT_HISTORY_RESPONSE_LIMIT

router = APIRouter()
logger = get_logger(__name__)

MAX_PAGE_SIZE = 100
DEFAULT_PAGE_SIZE = 50
QUALITY_SAMPLE_SIZE = 5000
MAX_CONVERSATION_TURNS = 500

# Response paths that mean the turn did NOT complete normally through the model
# (surfaced as an honest error/anomaly status, derived from existing metadata —
# no new logging). Deliberate safety behaviours (deterministic_safety,
# off_topic, input_guardrail) are intended outcomes, not errors.
ERROR_STATUS_PATHS = frozenset({"error_fallback", "runtime_guardrail"})

# Metadata keys that are safe to surface for quality review. Deliberately
# excludes identity/raw fields: target_name, target_key, target_id,
# target_profile_id, family_member_id, last_object, structured_findings,
# recent_suggestion_topics, and anything not listed below.
SAFE_METADATA_KEYS = frozenset({
    "conversation_id",
    "target_scope",
    "last_target_scope",
    "target_resolution_source",
    "intent_resolution_source",
    "object_resolution_source",
    "response_path",
    "last_intent",
    "last_meal_context",
    "last_subject",
    "last_object_type",
    "last_artifact_reference",
    "artifact_reference_present",
    "last_answer_type",
    "privacy_mode",
    "evidence_levels",
    "finding_count",
    "evidence_upgraded",
    "upgrade_source_present",
    "object_changed",
    "ambiguity_status",
    "target_explicit",
    "target_inherited",
    "resolved_object_present",
    "responder_received_object",
    "profile_fingerprint",
    "semantic_state_version",
})


def _pseudonym_secret() -> bytes:
    """Stable server secret for pseudonymization.

    Prefers the analytics hash key; falls back to the JWT secret (always present)
    so the dashboard works even when product analytics is disabled.
    """
    key = settings.CUREMENU_ANALYTICS_HASH_KEY or settings.jwt_secret_key
    return str(key or "").encode("utf-8")


def pseudonymous_user_label(account_id: str) -> str:
    """Deterministic, non-reversible per-account label, e.g. ``U-A1B2C3``."""
    digest = hmac.new(_pseudonym_secret(), str(account_id or "").encode("utf-8"), hashlib.sha256).hexdigest()
    return "U-" + digest[:6].upper()


def _safe_metadata(raw: Any) -> dict[str, Any]:
    """Return only allowlisted metadata keys; never crash on bad/legacy blobs."""
    if not raw:
        return {}
    if isinstance(raw, dict):
        parsed: Any = raw
    else:
        try:
            parsed = json.loads(raw)
        except (TypeError, ValueError):
            return {}
    if not isinstance(parsed, dict):
        return {}
    return {key: parsed[key] for key in SAFE_METADATA_KEYS if key in parsed}


def _is_truncated(output: str, module: str) -> bool:
    """Whether the stored answer is likely a truncated copy of the real answer.

    CureBot answers are capped at CHAT_HISTORY_RESPONSE_LIMIT before logging;
    redaction adds a trailing marker for anything over its own cap.
    """
    if output.endswith("...[TRUNCATED]"):
        return True
    return module == "CureBot" and len(output) >= CHAT_HISTORY_RESPONSE_LIMIT


def _serialize_interaction(row: dict[str, Any]) -> dict[str, Any]:
    """Explicit, safe projection of a raw interaction_logs row.

    Note: `telefon` and `kullanici_adi` are intentionally never included.
    """
    module = row.get("sayfa")
    output = row.get("cevap") or ""
    metadata = _safe_metadata(row.get("metadata"))
    response_path = str(metadata.get("response_path") or "")
    return {
        "id": row.get("id"),
        "timestamp": row.get("tarih"),
        "pseudonymous_user_id": pseudonymous_user_label(row.get("telefon")),
        "module": module,
        "input": row.get("istek") or "",
        "output": output,
        "output_truncated": _is_truncated(output, module),
        "response_log_limit": CHAT_HISTORY_RESPONSE_LIMIT,
        "error_status": response_path if response_path in ERROR_STATUS_PATHS else "",
        "conversation_id": str(metadata.get("conversation_id") or ""),
        "metadata": metadata,
    }


def _no_store(payload: dict[str, Any]) -> JSONResponse:
    return JSONResponse(content=payload, headers={"Cache-Control": "no-store"})


def _rate(part: int, whole: int) -> float:
    return round(part * 100 / whole, 1) if whole else 0.0


def _curebot_quality(metadata_blobs: list, total_turns: int, unique_users: int) -> dict[str, Any]:
    """Aggregate CureBot quality from deterministic metadata only.

    Never fabricates accuracy/safety scores. `sample_size` is the number of most
    recent turns actually scanned; rates are computed over that sample.
    """
    response_paths: Counter = Counter()
    evidence_levels: Counter = Counter()
    resolution_sources: Counter = Counter()
    clarifications = 0
    findings_present = 0
    artifact_recall = 0

    safe_rows = [_safe_metadata(blob) for blob in metadata_blobs]
    for meta in safe_rows:
        if meta.get("response_path"):
            response_paths[str(meta["response_path"])] += 1
        for level in meta.get("evidence_levels", []) or []:
            evidence_levels[str(level)] += 1
        if meta.get("target_resolution_source"):
            resolution_sources[str(meta["target_resolution_source"])] += 1
        if str(meta.get("last_answer_type") or "") == "clarification":
            clarifications += 1
        try:
            if int(meta.get("finding_count") or 0) > 0:
                findings_present += 1
        except (TypeError, ValueError):
            pass
        artifact = str(meta.get("last_artifact_reference") or "")
        if artifact and artifact != "none":
            artifact_recall += 1

    sample = len(safe_rows)
    return {
        "total_turns": total_turns,
        "unique_users": unique_users,
        "sample_size": sample,
        "response_path_distribution": dict(response_paths),
        "evidence_level_distribution": dict(evidence_levels),
        "target_resolution_source_distribution": dict(resolution_sources),
        "clarification_count": clarifications,
        "clarification_rate": _rate(clarifications, sample),
        "findings_present_count": findings_present,
        "findings_present_rate": _rate(findings_present, sample),
        "artifact_recall_count": artifact_recall,
        "artifact_recall_rate": _rate(artifact_recall, sample),
    }


@router.get("/api/admin/beta/modules")
async def beta_modules(request: Request, db: sqlite3.Connection = Depends(get_db)):
    """Real module (sayfa) values with counts — source for the filter dropdown."""
    require_admin(request)
    return _no_store({"success": True, "modules": beta_modul_ozet(conn=db)})


@router.get("/api/admin/beta/interactions")
async def beta_interactions(
    request: Request,
    module: str = "",
    date_from: str = "",
    date_to: str = "",
    search: str = "",
    user: str = "",
    limit: int = DEFAULT_PAGE_SIZE,
    offset: int = 0,
    db: sqlite3.Connection = Depends(get_db),
):
    """READ-ONLY, filtered, paginated interaction review across all modules."""
    require_admin(request)
    try:
        limit = max(1, min(int(limit), MAX_PAGE_SIZE))
    except (TypeError, ValueError):
        limit = DEFAULT_PAGE_SIZE
    try:
        offset = max(0, int(offset))
    except (TypeError, ValueError):
        offset = 0

    telefonlar = None
    if user:
        # Pseudonyms are non-reversible, so resolve the requested label by
        # recomputing it over the (small, beta-scale) set of distinct accounts.
        telefonlar = [
            telefon
            for telefon in beta_distinct_telefonlar(conn=db)
            if pseudonymous_user_label(telefon) == user
        ]
        if not telefonlar:
            return _no_store({"success": True, "items": [], "total": 0, "limit": limit, "offset": offset})

    rows, total = beta_interactions_ara(
        module=module or None,
        date_from=date_from or None,
        date_to=date_to or None,
        search=search or None,
        telefonlar=telefonlar,
        limit=limit,
        offset=offset,
        conn=db,
    )
    items = [_serialize_interaction(row) for row in rows]
    return _no_store({"success": True, "items": items, "total": total, "limit": limit, "offset": offset})


@router.get("/api/admin/beta/conversation")
async def beta_conversation(
    request: Request,
    conversation_id: str = "",
    limit: int = 200,
    db: sqlite3.Connection = Depends(get_db),
):
    """READ-ONLY CureBot thread: all turns of one conversation, chronological."""
    require_admin(request)
    conversation_id = (conversation_id or "").strip()
    if not conversation_id:
        return _no_store({"success": False, "detail": "conversation_id gerekli.", "turns": []})
    try:
        limit = max(1, min(int(limit), MAX_CONVERSATION_TURNS))
    except (TypeError, ValueError):
        limit = 200

    rows = beta_konusma_kayitlari(conversation_id, limit=limit, conn=db)
    turns: list[dict[str, Any]] = []
    pseudonym: str | None = None
    for row in rows:
        # LIKE can over-match; keep only exact conversation_id rows.
        if _safe_metadata(row.get("metadata")).get("conversation_id") != conversation_id:
            continue
        turns.append(_serialize_interaction(row))
        if pseudonym is None:
            pseudonym = pseudonymous_user_label(row.get("telefon"))
    turns = turns[:limit]
    return _no_store({
        "success": True,
        "conversation_id": conversation_id,
        "pseudonymous_user_id": pseudonym,
        "turns": turns,
    })


@router.get("/api/admin/beta/quality")
async def beta_quality(request: Request, db: sqlite3.Connection = Depends(get_db)):
    """Aggregate product-usage and CureBot quality view (deterministic only)."""
    require_admin(request)
    modules = beta_modul_ozet(conn=db)
    timeseries = beta_zaman_serisi(days=30, conn=db)
    metadata_blobs = beta_curebot_metadata(limit=QUALITY_SAMPLE_SIZE, conn=db)

    curebot_row = next((item for item in modules if item["module"] == "CureBot"), None)
    curebot = _curebot_quality(
        metadata_blobs,
        total_turns=curebot_row["interactions"] if curebot_row else 0,
        unique_users=curebot_row["users"] if curebot_row else 0,
    )
    total = sum(item["interactions"] for item in modules)
    return _no_store({
        "success": True,
        "total_interactions": total,
        "module_distribution": modules,
        "interactions_over_time": timeseries,
        "curebot": curebot,
    })
