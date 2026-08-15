import os

import pytest


# Configuration is imported during test collection in several modules. Keep
# tests independent from a developer's real provider credentials.
os.environ.setdefault("GOOGLE_API_KEY", "test-only-not-a-real-key")


def pytest_configure():
    """Keep password-flow tests fast without weakening runtime defaults."""
    import src.routers.auth as auth

    auth.PASSWORD_HASH_ITERATIONS = auth.LEGACY_PASSWORD_HASH_ITERATIONS


@pytest.fixture(autouse=True)
def disable_external_curebot_generation(monkeypatch):
    """Keep API tests deterministic without requiring a model provider."""
    from src.curebot_intent import classify_intent_plan

    monkeypatch.setattr(
        "src.profil_utils.icd_11_cevir",
        lambda diseases: ", ".join(str(item) for item in diseases) if diseases else "Bilinen hastalık yok",
    )
    monkeypatch.setattr("src.routers.chat.generate_curebot_natural_answer", lambda *_args, **_kwargs: "")
    monkeypatch.setattr(
        "src.routers.chat.plan_curebot_semantically",
        lambda message, conversation=None, target="self", profile_names=None, health_flags=None: classify_intent_plan(
            message,
            conversation,
            target,
            [],
            health_flags,
        ),
    )


@pytest.fixture()
def test_db_path(tmp_path, monkeypatch):
    db_file = tmp_path / "test_healmenu.db"
    monkeypatch.setenv("CUREMENU_DB_PATH", str(db_file))
    monkeypatch.setenv("LANGCHAIN_TRACING_V2", "false")
    monkeypatch.delenv("LANGCHAIN_API_KEY", raising=False)

    import src.database as db
    from src.config import settings

    settings.CUREMENU_DB_PATH = str(db_file)
    db._db_initialized = False
    return str(db_file)


@pytest.fixture()
def client(test_db_path):
    from fastapi.testclient import TestClient
    from api import app
    from src.rate_limit import limiter

    limiter.reset()
    with TestClient(app, base_url="https://testserver") as test_client:
        yield test_client
    limiter.reset()
