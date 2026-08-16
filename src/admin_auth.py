"""Shared admin authentication for internal/admin-only endpoints.

Single source of truth for the analytics/beta admin bearer-token check so the
product-analytics and beta-operations routers never duplicate the logic.
"""
from __future__ import annotations

import hmac

from fastapi import HTTPException, Request

from src.config import settings


def require_admin(request: Request) -> None:
    """Validate the analytics admin bearer token.

    Returns None when the caller supplies the configured admin token; otherwise
    raises 403. When the token is not configured at all, every admin endpoint
    fails closed (403) while the rest of the application keeps working.
    """
    expected = settings.CUREMENU_ANALYTICS_ADMIN_TOKEN or ""
    supplied = request.headers.get("Authorization", "")
    token = supplied.removeprefix("Bearer ").strip() if supplied.startswith("Bearer ") else ""
    if not expected or not hmac.compare_digest(token, expected):
        raise HTTPException(status_code=403, detail="Yönetici erişimi gerekli.")
