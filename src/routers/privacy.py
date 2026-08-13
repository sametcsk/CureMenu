import sqlite3

from fastapi import APIRouter, Depends, HTTPException, Request, Response

from src.auth import get_current_user
from src.database import (
    account_export_db,
    account_memory_metadata_db,
    delete_account_relational_db,
    get_db,
    profil_getir_db,
    sifre_hash_getir,
    analytics_delete_account_db,
)
from src.analytics import analytics_enabled, pseudonymous_account_id
from src.logger import get_logger, log_failure
from src.memory import build_memory_namespace, delete_account_memory
from src.models import AccountDeletionRequest
from src.profile_context import resolve_profile_snapshot_from_profile
from src.rate_limit import authenticated_user_or_ip, limiter
from src.routers.auth import verify_password


router = APIRouter()
logger = get_logger(__name__)


def _historical_memory_namespaces(account_id: str, metadata_rows: list[dict]) -> set[str]:
    namespaces: set[str] = set()
    for metadata in metadata_rows:
        target_scope = str(metadata.get("target_scope") or "").strip()
        target_id = str(metadata.get("target_id") or "").strip()
        fingerprint = str(metadata.get("profile_fingerprint") or "").strip()
        if target_scope and target_id and fingerprint:
            subject = f"{target_scope}:{target_id}:profile:{fingerprint}"
            namespaces.add(build_memory_namespace(account_id, subject))
    return namespaces


def _current_memory_namespaces(account_id: str, profile) -> set[str]:
    if profile is None:
        return set()
    requested_targets = {"kendim", "tum_aile"}
    requested_targets.update(member.id for member in profile.aile_uyeleri)
    namespaces: set[str] = set()
    for target in requested_targets:
        try:
            snapshot = resolve_profile_snapshot_from_profile(account_id, profile, target)
        except HTTPException:
            continue
        namespaces.add(snapshot.memory_namespace)
    return namespaces


def _clear_auth_cookies(response: Response) -> None:
    response.delete_cookie("access_token")
    response.delete_cookie("refresh_token", path="/api")
    response.delete_cookie("refresh_token", path="/api/refresh")


@router.get("/api/account/export")
@limiter.limit("3/hour", key_func=authenticated_user_or_ip)
async def export_account_data(
    request: Request,
    telefon: str = Depends(get_current_user),
    db: sqlite3.Connection = Depends(get_db),
):
    export = account_export_db(telefon, conn=db)
    if export is None:
        raise HTTPException(status_code=404, detail="Hesap bulunamadı.")
    return export


@router.delete("/api/account")
@limiter.limit("3/hour", key_func=authenticated_user_or_ip)
async def delete_account(
    request: Request,
    response: Response,
    req: AccountDeletionRequest,
    telefon: str = Depends(get_current_user),
    db: sqlite3.Connection = Depends(get_db),
):
    password_hash = sifre_hash_getir(telefon, conn=db)
    if not verify_password(req.sifre, password_hash or ""):
        raise HTTPException(status_code=401, detail="Şifre doğrulanamadı.")

    profile = profil_getir_db(telefon, conn=db)
    namespaces = _current_memory_namespaces(telefon, profile)
    namespaces.update(
        _historical_memory_namespaces(telefon, account_memory_metadata_db(telefon, conn=db))
    )

    try:
        deleted_memory_records = delete_account_memory(telefon, namespaces)
    except Exception as exc:
        log_failure(logger, "account_memory_delete", exc, component="privacy")
        raise HTTPException(
            status_code=503,
            detail="Kullanıcı hafızası temizlenemediği için hesap silme işlemi başlatılmadı.",
        ) from exc

    deleted_relational = delete_account_relational_db(telefon, conn=db)
    deleted_analytics = 0
    if analytics_enabled():
        deleted_analytics = analytics_delete_account_db(pseudonymous_account_id(telefon), conn=db)
    _clear_auth_cookies(response)
    return {
        "success": True,
        "deleted": {
            "user_memory_records": deleted_memory_records,
            "analytics_events": deleted_analytics,
            **deleted_relational,
        },
    }
