import pytest


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
