"""First-party product analytics router; deliberately separate from clinical audit logs."""

from __future__ import annotations

import hmac
import sqlite3
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

from src.analytics import analytics_enabled, build_completion_rows, build_cta_rows, build_feature_rows, build_funnel, build_retention, build_screen_rows, build_summary, validate_event
from src.auth import get_current_user, verify_token
from src.config import settings
from src.database import analytics_event_kaydet_db, get_db
from src.logger import get_logger, log_failure
from src.rate_limit import authenticated_user_or_ip, limiter

router = APIRouter()
logger = get_logger(__name__)


class AnalyticsEventRequest(BaseModel):
    event_name: str = Field(max_length=64)
    session_id: str = Field(max_length=64)
    anonymous_user_id: str = Field(default="", max_length=64)
    screen: str = Field(default="", max_length=32)
    feature: str = Field(default="", max_length=32)
    active_duration_ms: int | None = None
    app_version: str = Field(default="web-v1", max_length=32)
    research_cohort: str = Field(default="", max_length=8)
    metadata: dict[str, Any] = Field(default_factory=dict)


def _optional_account(request: Request) -> str | None:
    token = request.cookies.get("access_token")
    if not token:
        header = request.headers.get("Authorization", "")
        token = header.removeprefix("Bearer ").strip() if header.startswith("Bearer ") else ""
    if not token:
        return None
    try:
        return str(verify_token(token).get("sub") or "") or None
    except HTTPException:
        return None


def _require_admin(request: Request) -> None:
    expected = settings.CUREMENU_ANALYTICS_ADMIN_TOKEN or ""
    supplied = request.headers.get("Authorization", "")
    token = supplied.removeprefix("Bearer ").strip() if supplied.startswith("Bearer ") else ""
    if not expected or not hmac.compare_digest(token, expected):
        raise HTTPException(status_code=403, detail="Yönetici erişimi gerekli.")


def _all_events(db: sqlite3.Connection) -> list[dict[str, Any]]:
    cursor = db.execute("SELECT anonymous_user_id, session_id, event_name, screen, feature, event_time, active_duration_ms, research_cohort, metadata_json FROM analytics_events ORDER BY event_time ASC")
    return [dict(zip([item[0] for item in cursor.description], row)) for row in cursor.fetchall()]


@router.post("/api/analytics/event", status_code=202)
@limiter.limit("120/minute", key_func=authenticated_user_or_ip)
async def record_event(request: Request, payload: AnalyticsEventRequest, db: sqlite3.Connection = Depends(get_db)):
    if not analytics_enabled():
        return {"success": True, "recorded": False}
    try:
        event = validate_event(payload.model_dump(), account_id=_optional_account(request))
    except ValueError as exc:
        raise HTTPException(status_code=422, detail="Geçersiz analytics olayı.") from exc
    try:
        analytics_event_kaydet_db(event, conn=db)
    except Exception as exc:
        log_failure(logger, "analytics_event_write", exc, component="analytics")
        # Best-effort telemetry must never cause the product flow to fail.
        return {"success": True, "recorded": False}
    return {"success": True, "recorded": True}


@router.get("/api/admin/analytics/summary")
async def summary(request: Request, db: sqlite3.Connection = Depends(get_db)):
    _require_admin(request); return {"success": True, **build_summary(_all_events(db))}


@router.get("/api/admin/analytics/funnel")
async def funnel(request: Request, db: sqlite3.Connection = Depends(get_db)):
    _require_admin(request); return {"success": True, "funnel": build_funnel(_all_events(db))}


@router.get("/api/admin/analytics/retention")
async def retention(request: Request, db: sqlite3.Connection = Depends(get_db)):
    _require_admin(request); return {"success": True, "retention": build_retention(_all_events(db))}


@router.get("/api/admin/analytics/features")
async def features(request: Request, db: sqlite3.Connection = Depends(get_db)):
    _require_admin(request); return {"success": True, "features": build_feature_rows(_all_events(db))}


@router.get("/api/admin/analytics/completions")
async def completions(request: Request, db: sqlite3.Connection = Depends(get_db)):
    _require_admin(request); return {"success": True, "completions": build_completion_rows(_all_events(db))}


@router.get("/api/admin/analytics/screens")
async def screens(request: Request, db: sqlite3.Connection = Depends(get_db)):
    _require_admin(request); return {"success": True, "screens": build_screen_rows(_all_events(db))}


@router.get("/api/admin/analytics/ctas")
async def ctas(request: Request, db: sqlite3.Connection = Depends(get_db)):
    _require_admin(request); return {"success": True, "ctas": build_cta_rows(_all_events(db))}


@router.get("/api/admin/analytics/cohorts")
async def cohorts(request: Request, db: sqlite3.Connection = Depends(get_db)):
    _require_admin(request)
    rows = _all_events(db); groups: dict[str, list[dict[str, Any]]] = {}
    for row in rows: groups.setdefault(row.get("research_cohort") or "unassigned", []).append(row)
    return {"success": True, "cohorts": [{"cohort": cohort, **build_summary(items)["users"], "funnel": build_funnel(items), "retention": build_retention(items), "features": build_feature_rows(items)} for cohort, items in sorted(groups.items())]}
