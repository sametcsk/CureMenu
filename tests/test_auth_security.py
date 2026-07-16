import sqlite3

import pytest
from fastapi.testclient import TestClient

from src.config import settings
from src.database import refresh_token_jti_is_revoked_db


def _register(client, telefon="5557000001", password="123456"):
    return client.post(
        "/api/register",
        json={"telefon": telefon, "kullanici_adi": "Guvenlik Test", "sifre": password},
    )


def test_login_enumeration_same_status_and_response(client):
    _register(client)

    unknown = client.post("/api/login", json={"telefon": "5557000099", "sifre": "wrong-password"})
    wrong_password = client.post("/api/login", json={"telefon": "5557000001", "sifre": "wrong-password"})

    assert unknown.status_code == wrong_password.status_code == 401
    assert unknown.json() == wrong_password.json() == {"detail": "Telefon veya şifre hatalı."}


def test_successful_login_cookie_security_contract(client):
    _register(client, telefon="5557000002")

    response = client.post("/api/login", json={"telefon": "5557000002", "sifre": "123456"})

    assert response.status_code == 200
    cookie_header = response.headers.get("set-cookie", "")
    assert "HttpOnly" in cookie_header
    assert "SameSite=lax" in cookie_header
    assert "Secure" in cookie_header


def test_login_rate_limit_returns_429(client):
    payload = {"telefon": "5557000098", "sifre": "wrong-password"}

    responses = [client.post("/api/login", json=payload) for _ in range(11)]

    assert all(response.status_code == 401 for response in responses[:10])
    assert responses[10].status_code == 429


def test_logout_revokes_refresh_token(client):
    _register(client, telefon="5557000003")
    login = client.post("/api/login", json={"telefon": "5557000003", "sifre": "123456"})
    refresh_token = login.cookies.get("refresh_token")
    assert refresh_token

    logout = client.post("/api/logout")
    assert logout.status_code == 200

    from api import app

    replay_client = TestClient(app, base_url="https://testserver")
    replay_client.cookies.set("refresh_token", refresh_token, domain="testserver.local", path="/api/refresh")
    assert replay_client.post("/api/refresh").status_code == 401


def test_refresh_revocation_persists_in_database(client, test_db_path):
    _register(client, telefon="5557000004")
    login = client.post("/api/login", json={"telefon": "5557000004", "sifre": "123456"})
    old_refresh = login.cookies.get("refresh_token")
    assert old_refresh

    assert client.post("/api/refresh").status_code == 200

    import jwt

    payload = jwt.decode(
        old_refresh,
        settings.jwt_secret_key,
        algorithms=[settings.ALGORITHM],
        audience="curemenu_api",
        issuer="curemenu",
    )
    with sqlite3.connect(test_db_path) as connection:
        assert refresh_token_jti_is_revoked_db(payload["jti"], conn=connection) is True


def test_production_requires_secure_cookie(monkeypatch):
    monkeypatch.setattr(settings, "APP_ENV", "production")
    monkeypatch.setattr(settings, "GOOGLE_API_KEY", "configured-for-test")
    monkeypatch.setattr(settings, "JWT_SECRET_KEY", "configured-for-test")
    monkeypatch.setattr(settings, "CORS_ORIGINS", "https://example.test")
    monkeypatch.setattr(settings, "CUREMENU_COOKIE_SECURE", False)

    with pytest.raises(ValueError, match="CUREMENU_COOKIE_SECURE"):
        settings.validate_startup_security()


def test_development_allows_automatic_cookie_mode(monkeypatch):
    monkeypatch.setattr(settings, "APP_ENV", "development")
    monkeypatch.setattr(settings, "GOOGLE_API_KEY", "configured-for-test")
    monkeypatch.setattr(settings, "CUREMENU_COOKIE_SECURE", None)

    settings.validate_startup_security()
