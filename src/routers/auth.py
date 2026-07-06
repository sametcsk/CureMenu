from fastapi import APIRouter, Request, Response, BackgroundTasks, Depends, HTTPException
import sqlite3

from src.models import LoginRequest, RegisterRequest, KullaniciProfili
from src.database import get_db, profil_getir_db, profil_kaydet_db, etkilesim_logla, sifre_hash_getir, sifre_hash_kaydet
from src.auth import create_tokens, verify_token, revoke_token_jti
import hashlib
import os

router = APIRouter()

from src.config import settings

def hash_password(password: str) -> str:
    salt = os.urandom(16).hex()
    key = hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'), salt.encode('utf-8'), 100000).hex()
    return f"{salt}${key}"

def verify_password(password: str, hashed: str) -> bool:
    if not hashed or "$" not in hashed:
        return False
    salt, key = hashed.split("$")
    new_key = hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'), salt.encode('utf-8'), 100000).hex()
    return key == new_key

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
        path="/api/refresh",
        max_age=7 * 24 * 60 * 60
    )

@router.post("/api/register")
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
async def login(request: Request, response: Response, req: LoginRequest, bg_tasks: BackgroundTasks, db: sqlite3.Connection = Depends(get_db)):
    """Giriş yap."""
    profil = profil_getir_db(req.telefon, conn=db)
    if profil is None:
        raise HTTPException(status_code=404, detail="Hesap bulunamadı, lütfen kayıt olun.")
        
    hashed = sifre_hash_getir(req.telefon, conn=db)
    if not verify_password(req.sifre, hashed):
        raise HTTPException(status_code=401, detail="Şifre hatalı.")
    
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
async def logout(response: Response):
    response.delete_cookie("access_token")
    response.delete_cookie("refresh_token", path="/api/refresh")
    return {"success": True}

@router.post("/api/refresh")
async def refresh_token(request: Request, response: Response):
    token = request.cookies.get("refresh_token")
    if not token:
        raise HTTPException(status_code=401, detail="Refresh token eksik")
    
    payload = verify_token(token, expected_type="refresh")
    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(status_code=401, detail="Geçersiz refresh token")
        
    access_token, new_refresh_token = create_tokens(user_id=user_id)
    revoke_token_jti(payload.get("jti"))
    _set_auth_cookies(request, response, access_token, new_refresh_token)
    return {"success": True}
