import os

import pytest

from src.config import settings


_TRACING_ENV_KEYS = (
    "LANGCHAIN_TRACING",
    "LANGCHAIN_TRACING_V2",
    "LANGSMITH_TRACING",
    "LANGSMITH_TRACING_V2",
    "LANGCHAIN_HIDE_INPUTS",
    "LANGCHAIN_HIDE_OUTPUTS",
    "LANGCHAIN_HIDE_METADATA",
    "LANGSMITH_HIDE_INPUTS",
    "LANGSMITH_HIDE_OUTPUTS",
    "LANGSMITH_HIDE_METADATA",
)


def _set_tracing_config(monkeypatch, *, app_env="development", enabled=False):
    monkeypatch.setattr(settings, "APP_ENV", app_env)
    monkeypatch.setattr(settings, "LANGCHAIN_TRACING", enabled)
    monkeypatch.setattr(settings, "LANGCHAIN_TRACING_V2", "false")
    monkeypatch.setattr(settings, "LANGSMITH_TRACING", "false")
    monkeypatch.setattr(settings, "LANGSMITH_TRACING_V2", "false")
    for key in _TRACING_ENV_KEYS:
        monkeypatch.setenv(key, "false")


def test_security_headers_are_present(client):
    for path in ["/", "/dashboard", "/health"]:
        response = client.get(path)
        assert response.status_code == 200
        assert response.headers["x-content-type-options"] == "nosniff"
        assert response.headers["referrer-policy"] == "strict-origin-when-cross-origin"
        assert response.headers["x-frame-options"] == "DENY"
        assert "camera=(self)" in response.headers["permissions-policy"]
        assert response.headers["cache-control"] == "no-store"


def test_hsts_only_added_for_production_https(client, monkeypatch):
    response = client.get("/health")
    assert "strict-transport-security" not in response.headers

    monkeypatch.setattr(settings, "APP_ENV", "production")
    response = client.get("/health")
    assert response.headers["strict-transport-security"] == "max-age=31536000; includeSubDomains"


def test_health_and_live_are_liveness_checks(client):
    assert client.get("/health").json()["status"] == "ok"
    assert client.get("/live").json()["status"] == "ok"


def test_ready_returns_200_when_all_checks_pass(client, monkeypatch):
    import src.readiness as readiness

    monkeypatch.setattr(readiness, "_check_config", lambda: {"ok": True})
    monkeypatch.setattr(readiness, "_check_database", lambda: {"ok": True})
    monkeypatch.setattr(readiness, "_check_registry", lambda: {"ok": True})
    monkeypatch.setattr(readiness, "_check_chroma", lambda: {"ok": True})

    response = client.get("/ready")

    assert response.status_code == 200
    assert response.json()["status"] == "ready"


@pytest.mark.parametrize(
    ("failed_check", "expected_key"),
    [
        ("_check_database", "database"),
        ("_check_registry", "clinical_evidence_registry"),
    ],
)
def test_ready_returns_503_when_required_check_fails(client, monkeypatch, failed_check, expected_key):
    import src.readiness as readiness

    monkeypatch.setattr(readiness, "_check_config", lambda: {"ok": True})
    monkeypatch.setattr(readiness, "_check_database", lambda: {"ok": True})
    monkeypatch.setattr(readiness, "_check_registry", lambda: {"ok": True})
    monkeypatch.setattr(readiness, "_check_chroma", lambda: {"ok": True})
    monkeypatch.setattr(readiness, failed_check, lambda: {"ok": False, "error": "test_failure"})

    response = client.get("/ready")
    payload = response.json()

    assert response.status_code == 503
    assert payload["status"] == "not_ready"
    assert payload["checks"][expected_key]["ok"] is False


def _set_safe_production_config(monkeypatch):
    monkeypatch.setattr(settings, "APP_ENV", "production")
    monkeypatch.setattr(settings, "GOOGLE_API_KEY", "configured-for-test")
    monkeypatch.setattr(settings, "JWT_SECRET_KEY", "configured-for-test-secret")
    monkeypatch.setattr(settings, "CORS_ORIGINS", "https://app.example")
    monkeypatch.setattr(settings, "CUREMENU_COOKIE_SECURE", True)
    monkeypatch.setattr(settings, "DEBUG", False)
    monkeypatch.setattr(settings, "ALLOWED_HOSTS", "app.example")
    monkeypatch.setattr(settings, "CUREMENU_DB_PATH", "C:/data/curemenu.db")


def test_production_config_accepts_explicit_safe_values(monkeypatch):
    _set_safe_production_config(monkeypatch)

    settings.validate_startup_security()


@pytest.mark.parametrize(
    ("field", "value", "error_match"),
    [
        ("DEBUG", True, "DEBUG"),
        ("ALLOWED_HOSTS", "*", "ALLOWED_HOSTS"),
        ("ALLOWED_HOSTS", "localhost,127.0.0.1,testserver", "ALLOWED_HOSTS"),
        ("CUREMENU_DB_PATH", "healmenu.db", "CUREMENU_DB_PATH"),
        ("CORS_ORIGINS", "https://app.example,*", "CORS_ORIGINS"),
        ("JWT_SECRET_KEY", "curemenu_local_dev_secret_do_not_use_in_production", "JWT_SECRET_KEY"),
    ],
)
def test_production_config_rejects_unsafe_values(monkeypatch, field, value, error_match):
    _set_safe_production_config(monkeypatch)
    monkeypatch.setattr(settings, field, value)

    with pytest.raises(ValueError, match=error_match):
        settings.validate_startup_security()


def test_development_tracing_is_disabled_by_default(monkeypatch):
    _set_tracing_config(monkeypatch)

    assert settings.configure_langsmith_tracing() is False
    assert os.environ["LANGCHAIN_TRACING"] == "false"
    assert os.environ["LANGCHAIN_TRACING_V2"] == "false"
    assert os.environ["LANGSMITH_TRACING"] == "false"


def test_legacy_provider_flag_does_not_opt_in_development_tracing(monkeypatch):
    _set_tracing_config(monkeypatch)
    monkeypatch.setattr(settings, "LANGCHAIN_TRACING_V2", "true")

    assert settings.configure_langsmith_tracing() is False
    assert os.environ["LANGCHAIN_TRACING_V2"] == "false"
    assert os.environ["LANGSMITH_TRACING_V2"] == "false"


def test_development_tracing_requires_opt_in_and_hides_payloads(monkeypatch):
    from langsmith import utils as langsmith_utils

    _set_tracing_config(monkeypatch, enabled=True)

    assert settings.configure_langsmith_tracing() is True
    assert os.environ["LANGCHAIN_TRACING_V2"] == "true"
    assert langsmith_utils.get_env_var("HIDE_INPUTS") == "true"
    assert langsmith_utils.get_env_var("HIDE_OUTPUTS") == "true"
    assert langsmith_utils.get_env_var("HIDE_METADATA") == "true"


@pytest.mark.parametrize("app_env", ["production", "staging", "closed_beta"])
def test_real_user_environments_reject_langsmith_tracing(monkeypatch, app_env):
    _set_tracing_config(monkeypatch, app_env=app_env, enabled=True)

    with pytest.raises(ValueError, match="LangSmith tracing must be disabled"):
        settings.configure_langsmith_tracing()


def test_legacy_provider_flag_cannot_enable_closed_beta_tracing(monkeypatch):
    _set_tracing_config(monkeypatch, app_env="closed-beta")
    monkeypatch.setattr(settings, "LANGCHAIN_TRACING_V2", "true")

    with pytest.raises(ValueError, match="LangSmith tracing must be disabled"):
        settings.configure_langsmith_tracing()
