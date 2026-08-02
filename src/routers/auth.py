from fastapi import APIRouter, Request, Response, BackgroundTasks, Depends, HTTPException
import sqlite3

from src.models import LoginRequest, RegisterRequest, KullaniciProfili
from src.database import get_db, profil_getir_db, profil_kaydet_db, etkilesim_logla, sifre_hash_getir, sifre_hash_kaydet
from src.auth import create_tokens, verify_token, revoke_token_jti
import hashlib
import hmac
import os
from src.rate_limit import limiter

router = APIRouter()

from src.config import settings

PASSWORD_HASH_SCHEME = "pbkdf2_sha256"
DEFAULT_PASSWORD_HASH_ITERATIONS = 600_000
PASSWORD_HASH_ITERATIONS = DEFAULT_PASSWORD_HASH_ITERATIONS
LEGACY_PASSWORD_HASH_ITERATIONS = 100_000

def hash_password(password: str) -> str:
    salt = os.urandom(16).hex()
    key = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt.encode("utf-8"),
        PASSWORD_HASH_ITERATIONS,
    ).hex()
    return f"{PASSWORD_HASH_SCHEME}${PASSWORD_HASH_ITERATIONS}${salt}${key}"

def verify_password(password: str, hashed: str) -> bool:
    if not hashed or "$" not in hashed:
        return False
    try:
        parts = hashed.split("$")
        if len(parts) == 4 and parts[0] == PASSWORD_HASH_SCHEME:
            iterations = int(parts[1])
            salt, key = parts[2], parts[3]
        elif len(parts) == 2:
            iterations = LEGACY_PASSWORD_HASH_ITERATIONS
            salt, key = parts
        else:
            return False
        if iterations < LEGACY_PASSWORD_HASH_ITERATIONS or iterations > 2_000_000:
            return False
    except (TypeError, ValueError):
        return False
    new_key = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt.encode("utf-8"),
        iterations,
    ).hex()
    return hmac.compare_digest(key, new_key)


def password_needs_rehash(hashed: str | None) -> bool:
    if not hashed:
        return True
    parts = hashed.split("$")
    if len(parts) != 4 or parts[0] != PASSWORD_HASH_SCHEME:
        return True
    try:
        return int(parts[1]) < PASSWORD_HASH_ITERATIONS
    except ValueError:
        return True


DUMMY_PASSWORD_HASH = hash_password("curemenu-dummy-password")

def _secure_cookie_enabled(request: Request) -> bool:
    if settings.CUREMENU_COOKIE_SECURE is not None:
        return bool(settings.CUREMENU_COOKIE_SECURE)
    forwarded_proto = request.headers.get("x-forwarded-proto", "")
    if forwarded_proto:
        return forwarded_proto.lower() == "https"
    return request.url.scheme == "https"

def _set_auth_cookies(request: Request, response: Response, access_token: str, refresh_token: str):
    is_secure = _secure_cookie_enabled(request)
    
    response.set_cookie(
        key="access_token",
        value=access_token,
        httponly=True,
        secure=is_secure,
        samesite="lax",
        max_age=15 * 60
    )
    response.set_cookie(
        key="refresh_token",
        value=refresh_token,
        httponly=True,
        secure=is_secure,
        samesite="lax",
        path="/api",
        max_age=7 * 24 * 60 * 60
    )

@router.post("/api/register")
@limiter.limit("8/minute")
async def register(request: Request, response: Response, req: RegisterRequest, bg_tasks: BackgroundTasks, db: sqlite3.Connection = Depends(get_db)):
    """Yeni kullanıcı kaydı oluştur."""
    profil = profil_getir_db(req.telefon, conn=db)
    if profil is not None:
        raise HTTPException(status_code=409, detail="Bu telefon numarası zaten kayıtlı.")
        
    profil = KullaniciProfili()
    profil_kaydet_db(req.telefon, req.kullanici_adi, profil, conn=db)
    sifre_hash_kaydet(req.telefon, hash_password(req.sifre), conn=db)
    
    access_token, refresh_token = create_tokens(user_id=req.telefon)
    _set_auth_cookies(request, response, access_token, refresh_token)
    
    bg_tasks.add_task(etkilesim_logla, req.telefon, req.kullanici_adi, "Kayıt", "Register", "Başarılı", None)
    
    return {
        "success": True,
        "is_new_user": True,
        "kullanici_adi": req.kullanici_adi,
        "has_profile": False
    }

@router.post("/api/login")
@limiter.limit("10/minute")
async def login(request: Request, response: Response, req: LoginRequest, bg_tasks: BackgroundTasks, db: sqlite3.Connection = Depends(get_db)):
    """Giriş yap."""
    profil = profil_getir_db(req.telefon, conn=db)
    stored_hash = sifre_hash_getir(req.telefon, conn=db)
    password_valid = verify_password(req.sifre, stored_hash or DUMMY_PASSWORD_HASH)
    if profil is None or not password_valid:
        raise HTTPException(status_code=401, detail="Telefon veya şifre hatalı.")
    if password_needs_rehash(stored_hash):
        sifre_hash_kaydet(req.telefon, hash_password(req.sifre), conn=db)
    
    access_token, refresh_token = create_tokens(user_id=req.telefon)
    _set_auth_cookies(request, response, access_token, refresh_token)
    
    # Kullanıcı adını interaction logs tablosundan veya başka yerden çekebiliriz, 
    # Ancak profil.ana_kullanici varsa ondan alalım:
    kullanici_adi = profil.ana_kullanici.ad if profil.ana_kullanici else ""
    
    bg_tasks.add_task(etkilesim_logla, req.telefon, kullanici_adi, "Giriş", "Login", "Başarılı", None)
    
    return {
        "success": True,
        "is_new_user": False,
        "kullanici_adi": kullanici_adi,
        "has_profile": profil.ana_kullanici is not None
    }

@router.post("/api/logout")
async def logout(request: Request, response: Response, db: sqlite3.Connection = Depends(get_db)):
    token = request.cookies.get("refresh_token")
    if token:
        try:
            payload = verify_token(token, expected_type="refresh", conn=db)
            revoke_token_jti(payload.get("jti"), payload.get("exp"), conn=db)
        except HTTPException:
            pass
    response.delete_cookie("access_token")
    response.delete_cookie("refresh_token", path="/api")
    # Remove refresh cookies issued by older CureMenu versions as well.
    response.delete_cookie("refresh_token", path="/api/refresh")
    return {"success": True}

@router.post("/api/refresh")
@limiter.limit("20/minute")
async def refresh_token(request: Request, response: Response, db: sqlite3.Connection = Depends(get_db)):
    token = request.cookies.get("refresh_token")
    if not token:
        raise HTTPException(status_code=401, detail="Refresh token eksik")
    
    payload = verify_token(token, expected_type="refresh", conn=db)
    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(status_code=401, detail="Geçersiz refresh token")
        
    if not revoke_token_jti(payload.get("jti"), payload.get("exp"), conn=db):
        raise HTTPException(status_code=401, detail="Geçersiz refresh token")
    access_token, new_refresh_token = create_tokens(user_id=user_id)
    _set_auth_cookies(request, response, access_token, new_refresh_token)
    return {"success": True}
