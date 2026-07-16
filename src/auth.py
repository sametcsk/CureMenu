from datetime import datetime, timedelta, timezone
from typing import Optional, Tuple
import sqlite3
import jwt
from fastapi import Request, HTTPException, status
import uuid

from src.config import settings
from src.logger import get_logger, log_failure
from src.database import refresh_token_jti_consume_db, refresh_token_jti_is_revoked_db

logger = get_logger(__name__)
def generate_jti() -> str:
    """Benzersiz token id'si üretir (Token Blacklist/Rotation için)"""
    return str(uuid.uuid4())


def revoke_token_jti(
    jti: str | None,
    expires_at: int | float | None,
    conn: sqlite3.Connection | None = None,
) -> bool:
    return refresh_token_jti_consume_db(jti, expires_at, conn=conn)


def is_token_revoked(jti: str | None, conn: sqlite3.Connection | None = None) -> bool:
    return refresh_token_jti_is_revoked_db(jti, conn=conn)

def create_tokens(user_id: str, role: str = "user") -> Tuple[str, str]:
    """
    Access ve Refresh tokenlarını oluşturur.
    Access Token: Kısa ömürlü (Örn: 15 dk)
    Refresh Token: Uzun ömürlü (Örn: 7 gün)
    """
    now = datetime.now(timezone.utc)
    
    # Access Token Payload
    access_payload = {
        "sub": user_id,
        "role": role,
        "iat": now,
        "exp": now + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES),
        "jti": generate_jti(),
        "iss": "curemenu",
        "aud": "curemenu_api"
    }
    access_token = jwt.encode(access_payload, settings.jwt_secret_key, algorithm=settings.ALGORITHM)
    
    # Refresh Token Payload
    refresh_payload = {
        "sub": user_id,
        "type": "refresh",
        "iat": now,
        "exp": now + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS),
        "jti": generate_jti(),
        "iss": "curemenu",
        "aud": "curemenu_api"
    }
    refresh_token = jwt.encode(refresh_payload, settings.jwt_secret_key, algorithm=settings.ALGORITHM)
    
    return access_token, refresh_token

def verify_token(
    token: str,
    expected_type: Optional[str] = None,
    conn: sqlite3.Connection | None = None,
) -> dict:
    """
    Verilen JWT token'ı doğrular ve payload'ı döner.
    """
    try:
        payload = jwt.decode(
            token, 
            settings.jwt_secret_key,
            algorithms=[settings.ALGORITHM],
            audience="curemenu_api",
            issuer="curemenu"
        )
        if expected_type and payload.get("type") != expected_type:
            raise jwt.InvalidTokenError("Geçersiz token tipi")
        if expected_type == "refresh" and is_token_revoked(payload.get("jti"), conn=conn):
            raise jwt.InvalidTokenError("Token revoked")
        return payload
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token süresi doldu",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except jwt.InvalidTokenError as e:
        log_failure(logger, "token_validation", e, component="auth")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Geçersiz kimlik bilgisi",
            headers={"WWW-Authenticate": "Bearer"},
        )

def get_current_user(request: Request) -> str:
    """
    FastAPI Dependency (Bağımlılık).
    Cookie içindeki 'access_token' değerini okur ve doğrular.
    Başarılı olursa kullanıcının ID'sini (telefon) döner.
    """
    token = request.cookies.get("access_token")
    if not token:
        # Belki header olarak gelmiştir (Gelecekte mobil uygulama için)
        auth_header = request.headers.get("Authorization")
        if auth_header and auth_header.startswith("Bearer "):
            token = auth_header.split(" ")[1]
            
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Kimlik doğrulama gereklidir (Giriş yapın)",
        )
        
    payload = verify_token(token)
    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Geçersiz kullanıcı kimliği")
        
    return user_id
