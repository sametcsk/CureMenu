"""Generic media reference layer for uploaded previews (fridge / menu).

Root-cause fix: previews were held only in component state (lost on route change)
and base64-embedded in interaction_logs TEXT. Here the last/active preview per
(account, resolved target, media_type) lives in a dedicated media store (BLOB),
reloadable via GET, isolated by account+target, and separated by type. The
frontend keeps only a display cache; it never persists large base64 itself.
"""
from __future__ import annotations

import base64
import binascii
import sqlite3

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

from src.auth import get_current_user
from src.database import get_db, media_getir, media_kaydet
from src.logger import get_logger, log_failure
from src.profile_context import resolve_profile_snapshot
from src.rate_limit import authenticated_user_or_ip, limiter

router = APIRouter()
logger = get_logger(__name__)

MEDIA_TYPES = {"fridge", "menu"}
MAX_MEDIA_BYTES = 700_000  # a preview, not the full-resolution upload


class MediaSaveRequest(BaseModel):
    media_type: str = Field(..., max_length=16)
    kimin_icin: str = Field(default="kendim", min_length=1, max_length=128)
    image_base64: str = Field(..., max_length=2_000_000)


def _decode(image_base64: str) -> tuple[bytes, str]:
    raw = (image_base64 or "").strip()
    content_type = "image/jpeg"
    if raw.startswith("data:"):
        header, _, payload = raw.partition(",")
        raw = payload
        if ";" in header and ":" in header:
            content_type = header.split(":", 1)[1].split(";", 1)[0] or content_type
    try:
        data = base64.b64decode(raw, validate=True)
    except (binascii.Error, ValueError) as exc:
        raise HTTPException(status_code=422, detail="Geçersiz görsel verisi.") from exc
    if not data:
        raise HTTPException(status_code=422, detail="Boş görsel verisi.")
    if len(data) > MAX_MEDIA_BYTES:
        raise HTTPException(status_code=413, detail="Görsel önizleme çok büyük.")
    return data, content_type


@router.post("/api/media")
@limiter.limit("30/minute", key_func=authenticated_user_or_ip)
async def save_media(
    request: Request,
    req: MediaSaveRequest,
    telefon: str = Depends(get_current_user),
    db: sqlite3.Connection = Depends(get_db),
):
    if req.media_type not in MEDIA_TYPES:
        raise HTTPException(status_code=400, detail="Geçersiz medya türü.")
    data, content_type = _decode(req.image_base64)
    snapshot = resolve_profile_snapshot(telefon, req.kimin_icin, db=db)
    try:
        media_kaydet(telefon, snapshot.target_key, req.media_type, data, content_type=content_type, conn=db)
    except Exception as exc:
        log_failure(logger, "media_persist", exc, component="media")
        raise HTTPException(status_code=503, detail="Görsel şu anda kaydedilemedi.") from exc
    return {"success": True, "media_type": req.media_type, "byte_size": len(data)}


@router.get("/api/media")
async def load_media(
    media_type: str,
    kimin_icin: str = "kendim",
    media_uid: str = "",
    telefon: str = Depends(get_current_user),
    db: sqlite3.Connection = Depends(get_db),
):
    if media_type not in MEDIA_TYPES:
        raise HTTPException(status_code=400, detail="Geçersiz medya türü.")
    if media_uid:
        # Per-record lookup (history detail). Owner-scoped by telefon -> a user can
        # only load their own media; no cross-account access.
        asset = media_getir(telefon, media_uid, media_type, conn=db)
    else:
        snapshot = resolve_profile_snapshot(telefon, kimin_icin, db=db)
        asset = media_getir(telefon, snapshot.target_key, media_type, conn=db)
    if not asset:
        return {"success": True, "media": None}
    encoded = base64.b64encode(asset["data"]).decode("ascii")
    content_type = asset["content_type"] or "image/jpeg"
    return {
        "success": True,
        "media": {
            "media_type": media_type,
            "content_type": content_type,
            "image_base64": f"data:{content_type};base64,{encoded}",
            "byte_size": asset["byte_size"],
            "created_at": asset["created_at"],
        },
    }
