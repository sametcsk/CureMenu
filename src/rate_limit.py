"""Shared rate limiter and privacy-preserving request identity helpers."""

from __future__ import annotations

import hashlib

import jwt
from fastapi import Request
from slowapi import Limiter
from slowapi.util import get_remote_address

from src.config import settings


def authenticated_user_or_ip(request: Request) -> str:
    """Use a verified, hashed account id when available; otherwise use client IP."""
    token = request.cookies.get("access_token")
    if not token:
        authorization = request.headers.get("Authorization", "")
        if authorization.startswith("Bearer "):
            token = authorization.removeprefix("Bearer ").strip()
    if token:
        try:
            payload = jwt.decode(
                token,
                settings.jwt_secret_key,
                algorithms=[settings.ALGORITHM],
                audience="curemenu_api",
                issuer="curemenu",
            )
            account_id = str(payload.get("sub") or "").strip()
            if account_id:
                digest = hashlib.sha256(account_id.encode("utf-8")).hexdigest()
                return f"user:{digest}"
        except jwt.InvalidTokenError:
            pass
    return f"ip:{get_remote_address(request)}"


limiter = Limiter(key_func=get_remote_address)
