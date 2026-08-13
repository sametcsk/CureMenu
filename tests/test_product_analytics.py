import sqlite3
from datetime import datetime, timezone

import pytest

from src.analytics import pseudonymous_account_id
from src.config import settings
from src.database import analytics_event_kaydet_db, analytics_retention_summary_db


@pytest.fixture()
def analytics_on(monkeypatch):
    monkeypatch.setattr(settings, "CUREMENU_ANALYTICS_ENABLED", True)
    monkeypatch.setattr(settings, "CUREMENU_ANALYTICS_HASH_KEY", "test-analytics-secret")
    monkeypatch.setattr(settings, "CUREMENU_ANALYTICS_ADMIN_TOKEN", "test-admin-token")


def event(name="screen_viewed", **extra):
    payload = {"event_name": name, "session_id": "11111111-1111-4111-8111-111111111111", "anonymous_user_id": "22222222-2222-4222-8222-222222222222", "screen": "home", "app_version": "web-v1"}
    payload.update(extra)
    return payload


def test_event_is_whitelisted_hmac_pseudonymous_and_minimised(client, test_db_path, analytics_on):
    client.post("/api/register", json={"telefon": "5559001001", "kullanici_adi": "Test", "sifre": "123456"})
    response = client.post("/api/analytics/event", json=event(metadata={"source": "home", "prompt": "secret health text"}))
    assert response.status_code == 202 and response.json()["recorded"] is True
    with sqlite3.connect(test_db_path) as db:
        row = db.execute("SELECT anonymous_user_id, metadata_json FROM analytics_events").fetchone()
    assert row[0] == pseudonymous_account_id("5559001001")
    assert "5559001001" not in row[0] and row[1] == '{"source": "home"}'


def test_unknown_event_and_unapproved_metadata_are_rejected_or_dropped(client, analytics_on):
    assert client.post("/api/analytics/event", json=event("message_body")).status_code == 422
    response = client.post("/api/analytics/event", json=event(metadata={"message": "do not persist"}))
    assert response.status_code == 202


def test_disabled_analytics_is_noop(client, test_db_path, monkeypatch):
    monkeypatch.setattr(settings, "CUREMENU_ANALYTICS_ENABLED", False)
    assert client.post("/api/analytics/event", json=event()).json()["recorded"] is False
    from src.database import _ensure_db
    _ensure_db()
    with sqlite3.connect(test_db_path) as db:
        assert db.execute("SELECT COUNT(*) FROM analytics_events").fetchone()[0] == 0


def test_admin_metrics_require_token_and_aggregate_events(client, test_db_path, analytics_on):
    with sqlite3.connect(test_db_path) as db:
        record = event("weekly_plan_generated", feature="weekly_plan")
        record.update({"event_time": datetime.now(timezone.utc).isoformat(), "anonymous_user_id": "anon-a"})
        analytics_event_kaydet_db(record, conn=db)
    assert client.get("/api/admin/analytics/summary").status_code == 403
    response = client.get("/api/admin/analytics/summary", headers={"Authorization": "Bearer test-admin-token"})
    assert response.status_code == 200 and response.json()["users"]["total"] == 1
    assert client.get("/api/admin/analytics/funnel", headers={"Authorization": "Bearer test-admin-token"}).json()["funnel"]["first_value"]["users"] == 1


@pytest.mark.parametrize("event_name", ["lab_analysis_completed", "grocery_list_created"])
def test_first_value_includes_successful_lab_and_grocery_events(client, test_db_path, analytics_on, event_name):
    with sqlite3.connect(test_db_path) as db:
        record = event(event_name, feature="lab" if event_name.startswith("lab") else "grocery")
        record.update({"event_time": datetime.now(timezone.utc).isoformat(), "anonymous_user_id": "anon-value"})
        analytics_event_kaydet_db(record, conn=db)
    response = client.get("/api/admin/analytics/funnel", headers={"Authorization": "Bearer test-admin-token"})
    assert response.json()["funnel"]["first_value"]["users"] == 1


def test_analytics_retention_is_separate_and_bounded(client, test_db_path, analytics_on):
    with sqlite3.connect(test_db_path) as db:
        old = event(); old.update({"event_time": "2020-01-01T00:00:00+00:00", "anonymous_user_id": "anon-old"})
        analytics_event_kaydet_db(old, conn=db)
        assert analytics_retention_summary_db("2021-01-01T00:00:00+00:00", conn=db) == 1
        assert analytics_retention_summary_db("2021-01-01T00:00:00+00:00", apply=True, conn=db) == 1


def test_account_deletion_removes_pseudonymous_analytics(client, test_db_path, analytics_on, monkeypatch):
    client.post("/api/register", json={"telefon": "5559001002", "kullanici_adi": "Silme", "sifre": "123456"})
    assert client.post("/api/analytics/event", json=event()).json()["recorded"] is True
    monkeypatch.setattr("src.routers.privacy.delete_account_memory", lambda *_args: 0)
    deleted = client.request("DELETE", "/api/account", json={"sifre": "123456", "confirmation": "DELETE"})
    assert deleted.status_code == 200 and deleted.json()["deleted"]["analytics_events"] == 1
    with sqlite3.connect(test_db_path) as db:
        assert db.execute("SELECT COUNT(*) FROM analytics_events").fetchone()[0] == 0
