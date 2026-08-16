"""Security & behaviour tests for the internal Beta Ops & Quality dashboard.

Fixtures use synthetic identifiers only. The dashboard is read-only and must
never leak phone numbers, real names, or identity metadata.
"""
import json
import sqlite3

import pytest

from src.auth import create_tokens
from src.config import settings
from src.database import etkilesim_logla
from src.routers.beta_admin import pseudonymous_user_label

ADMIN = {"Authorization": "Bearer test-admin-token"}
PHONE_A = "5551234567"
PHONE_B = "5559998877"
SECRET_NAME = "Gizli Isim"


@pytest.fixture()
def admin_on(monkeypatch):
    monkeypatch.setattr(settings, "CUREMENU_ANALYTICS_ADMIN_TOKEN", "test-admin-token")


def _seed():
    etkilesim_logla(
        PHONE_A, SECRET_NAME, "CureBot", "annem icin oneri ister misin", "guvenli oneri",
        json.dumps({
            "conversation_id": "c1", "target_name": SECRET_NAME, "target_key": "m1",
            "target_scope": "member", "response_path": "deterministic_safety",
            "last_intent": "food_suitability", "evidence_levels": ["CONFIRMED"],
            "finding_count": 1, "last_answer_type": "safety_block",
            "last_artifact_reference": "none", "target_resolution_source": "message_relationship",
        }, ensure_ascii=False),
    )
    etkilesim_logla(
        PHONE_B, "Diger Kisi", "CureBot", "peki ne onerirsin", "filtre tabanli oneri",
        json.dumps({
            "conversation_id": "c2", "response_path": "natural", "last_intent": "meal_followup",
            "evidence_levels": [], "finding_count": 0, "last_answer_type": "recommendation",
            "last_artifact_reference": "weekly_plan", "target_resolution_source": "continuity",
        }, ensure_ascii=False),
    )
    etkilesim_logla(
        PHONE_A, SECRET_NAME, "Haftalık Plan", "plan istegi", "haftalik plan icerigi",
        json.dumps({"target_name": SECRET_NAME, "target_key": "m1", "target_scope": "member",
                    "profile_fingerprint": "a" * 64}, ensure_ascii=False),
    )
    # malformed metadata, empty metadata, and an unknown/legacy module value.
    etkilesim_logla(PHONE_B, "Diger Kisi", "CureBot", "bozuk kayit", "cevap", "not-a-json-blob")
    etkilesim_logla(PHONE_A, SECRET_NAME, "Buzdolabı", "malzemeler", "tarif", None)
    etkilesim_logla(PHONE_B, "Diger Kisi", "LegacyThing", "eski", "kayit", json.dumps({"foo": "bar"}))


# ---- Auth -------------------------------------------------------------------
def test_no_token_is_forbidden(client, admin_on):
    assert client.get("/api/admin/beta/interactions").status_code == 403
    assert client.get("/api/admin/beta/modules").status_code == 403
    assert client.get("/api/admin/beta/quality").status_code == 403


def test_wrong_token_is_forbidden(client, admin_on):
    res = client.get("/api/admin/beta/interactions", headers={"Authorization": "Bearer nope"})
    assert res.status_code == 403


def test_correct_token_is_ok(client, admin_on):
    assert client.get("/api/admin/beta/interactions", headers=ADMIN).status_code == 200


def test_unset_admin_token_fails_closed(client, monkeypatch):
    monkeypatch.setattr(settings, "CUREMENU_ANALYTICS_ADMIN_TOKEN", None)
    assert client.get("/api/admin/beta/interactions", headers=ADMIN).status_code == 403


def test_normal_user_jwt_cannot_access(client, admin_on):
    access, _ = create_tokens("5550000000")
    res = client.get("/api/admin/beta/interactions", headers={"Authorization": f"Bearer {access}"})
    assert res.status_code == 403


# ---- Privacy ----------------------------------------------------------------
def test_response_never_contains_phone_or_real_name(client, admin_on):
    _seed()
    res = client.get("/api/admin/beta/interactions?limit=100", headers=ADMIN)
    assert res.status_code == 200
    blob = json.dumps(res.json(), ensure_ascii=False)
    assert PHONE_A not in blob and PHONE_B not in blob
    assert SECRET_NAME not in blob
    assert "telefon" not in blob and "kullanici_adi" not in blob


def test_pseudonym_is_deterministic_and_opaque(client, admin_on):
    assert pseudonymous_user_label(PHONE_A) == pseudonymous_user_label(PHONE_A)
    assert pseudonymous_user_label(PHONE_A) != pseudonymous_user_label(PHONE_B)
    label = pseudonymous_user_label(PHONE_A)
    assert label.startswith("U-") and len(label) == 8
    assert PHONE_A not in label


def test_safe_metadata_allowlist_drops_identity_fields(client, admin_on):
    _seed()
    res = client.get("/api/admin/beta/interactions?module=CureBot&limit=100", headers=ADMIN)
    metas = [item["metadata"] for item in res.json()["items"]]
    assert any("conversation_id" in m for m in metas)
    for meta in metas:
        assert "target_name" not in meta
        assert "target_key" not in meta
        assert "target_id" not in meta


# ---- Listing / filtering / pagination --------------------------------------
def test_lists_non_curebot_records_without_filter(client, admin_on):
    _seed()
    modules = {item["module"] for item in client.get("/api/admin/beta/interactions?limit=100", headers=ADMIN).json()["items"]}
    assert "CureBot" in modules and "Haftalık Plan" in modules and "LegacyThing" in modules


def test_module_filter_returns_only_matching(client, admin_on):
    _seed()
    items = client.get("/api/admin/beta/interactions?module=Haftalık Plan&limit=100", headers=ADMIN).json()["items"]
    assert items and all(item["module"] == "Haftalık Plan" for item in items)


def test_pagination_limit_and_offset(client, admin_on):
    _seed()
    page1 = client.get("/api/admin/beta/interactions?limit=2&offset=0", headers=ADMIN).json()
    page2 = client.get("/api/admin/beta/interactions?limit=2&offset=2", headers=ADMIN).json()
    assert page1["limit"] == 2 and len(page1["items"]) == 2
    assert page1["total"] >= 4
    ids1 = {item["id"] for item in page1["items"]}
    ids2 = {item["id"] for item in page2["items"]}
    assert ids1.isdisjoint(ids2)


def test_limit_is_capped_server_side(client, admin_on):
    _seed()
    res = client.get("/api/admin/beta/interactions?limit=9999", headers=ADMIN).json()
    assert res["limit"] == 100


def test_search_matches_redacted_input_output_only(client, admin_on):
    _seed()
    hit = client.get("/api/admin/beta/interactions?search=filtre&limit=100", headers=ADMIN).json()
    assert hit["total"] >= 1
    assert all("filtre" in (i["input"] + i["output"]).lower() for i in hit["items"])
    miss = client.get("/api/admin/beta/interactions?search=zzznotfoundzzz", headers=ADMIN).json()
    assert miss["total"] == 0 and miss["items"] == []


def test_user_pseudonym_filter(client, admin_on):
    _seed()
    label_b = pseudonymous_user_label(PHONE_B)
    res = client.get(f"/api/admin/beta/interactions?user={label_b}&limit=100", headers=ADMIN).json()
    assert res["total"] >= 1
    assert all(item["pseudonymous_user_id"] == label_b for item in res["items"])
    unknown = client.get("/api/admin/beta/interactions?user=U-000000", headers=ADMIN).json()
    assert unknown["total"] == 0


def test_date_filter_future_returns_empty(client, admin_on):
    _seed()
    res = client.get("/api/admin/beta/interactions?date_from=2999-01-01", headers=ADMIN).json()
    assert res["total"] == 0


# ---- Robustness -------------------------------------------------------------
def test_malformed_empty_and_legacy_metadata_do_not_crash(client, admin_on):
    _seed()
    res = client.get("/api/admin/beta/interactions?limit=100", headers=ADMIN)
    assert res.status_code == 200
    for item in res.json()["items"]:
        assert isinstance(item["metadata"], dict)  # degrades to {} on bad blobs


def test_read_only_does_not_mutate_rows(client, admin_on, test_db_path):
    _seed()
    with sqlite3.connect(test_db_path) as db:
        before = db.execute("SELECT COUNT(*) FROM interaction_logs").fetchone()[0]
    client.get("/api/admin/beta/interactions?limit=100", headers=ADMIN)
    client.get("/api/admin/beta/quality", headers=ADMIN)
    client.get("/api/admin/beta/modules", headers=ADMIN)
    with sqlite3.connect(test_db_path) as db:
        after = db.execute("SELECT COUNT(*) FROM interaction_logs").fetchone()[0]
    assert before == after == 6


def test_response_sets_no_store(client, admin_on):
    res = client.get("/api/admin/beta/interactions", headers=ADMIN)
    assert res.headers.get("Cache-Control") == "no-store"


# ---- Modules & Quality ------------------------------------------------------
def test_modules_endpoint_reports_real_values(client, admin_on):
    _seed()
    modules = {m["module"]: m for m in client.get("/api/admin/beta/modules", headers=ADMIN).json()["modules"]}
    assert "CureBot" in modules and modules["CureBot"]["interactions"] >= 3
    assert modules["CureBot"]["users"] >= 2


def test_quality_metrics_are_metadata_derived(client, admin_on):
    _seed()
    data = client.get("/api/admin/beta/quality", headers=ADMIN).json()
    assert data["total_interactions"] == 6
    cb = data["curebot"]
    assert cb["total_turns"] >= 3
    assert cb["unique_users"] >= 2
    assert "CONFIRMED" in cb["evidence_level_distribution"]
    assert "deterministic_safety" in cb["response_path_distribution"]
    assert cb["artifact_recall_count"] >= 1  # the weekly_plan reference
    # No fabricated accuracy/safety score fields.
    assert "accuracy" not in cb and "safety_score" not in cb


def _seed_conversation():
    etkilesim_logla(
        PHONE_A, SECRET_NAME, "CureBot", "merhaba ilk mesaj", "ilk cevap",
        json.dumps({"conversation_id": "conv-x", "response_path": "natural"}, ensure_ascii=False),
    )
    etkilesim_logla(
        PHONE_A, SECRET_NAME, "CureBot", "peki ikinci mesaj", "ikinci cevap",
        json.dumps({"conversation_id": "conv-x", "response_path": "deterministic_intent"}, ensure_ascii=False),
    )
    etkilesim_logla(
        PHONE_B, "Diger Kisi", "CureBot", "baska konusma", "baska cevap",
        json.dumps({"conversation_id": "conv-y", "response_path": "natural"}, ensure_ascii=False),
    )


# ---- Conversation thread -----------------------------------------------------
def test_conversation_requires_admin(client, admin_on):
    assert client.get("/api/admin/beta/conversation?conversation_id=conv-x").status_code == 403


def test_conversation_requires_id(client, admin_on):
    res = client.get("/api/admin/beta/conversation", headers=ADMIN).json()
    assert res["success"] is False and res["turns"] == []


def test_conversation_groups_by_id_chronologically(client, admin_on):
    _seed_conversation()
    data = client.get("/api/admin/beta/conversation?conversation_id=conv-x", headers=ADMIN).json()
    turns = data["turns"]
    assert len(turns) == 2  # only conv-x, not conv-y
    assert "merhaba" in turns[0]["input"] and "peki" in turns[1]["input"]  # chronological
    assert turns[0]["id"] < turns[1]["id"]
    assert data["pseudonymous_user_id"] == pseudonymous_user_label(PHONE_A)


def test_conversation_never_leaks_identity(client, admin_on):
    _seed_conversation()
    blob = json.dumps(client.get("/api/admin/beta/conversation?conversation_id=conv-x", headers=ADMIN).json(), ensure_ascii=False)
    assert PHONE_A not in blob and SECRET_NAME not in blob


# ---- Truncation notice & error status ---------------------------------------
def test_output_truncation_flag(client, admin_on):
    etkilesim_logla(PHONE_A, "N", "CureBot", "uzun cevap istegi", "x" * 3000,
                    json.dumps({"conversation_id": "conv-t"}, ensure_ascii=False))
    etkilesim_logla(PHONE_A, "N", "CureBot", "kisa", "kisa cevap",
                    json.dumps({"conversation_id": "conv-s"}, ensure_ascii=False))
    items = {i["input"]: i for i in client.get("/api/admin/beta/interactions?limit=100", headers=ADMIN).json()["items"]}
    assert items["uzun cevap istegi"]["output_truncated"] is True
    assert items["uzun cevap istegi"]["response_log_limit"] == 3000
    assert items["kisa"]["output_truncated"] is False


def test_error_status_derived_from_metadata(client, admin_on):
    etkilesim_logla(PHONE_B, "N", "CureBot", "hata ureten", "fallback cevap",
                    json.dumps({"conversation_id": "conv-e", "response_path": "error_fallback"}, ensure_ascii=False))
    etkilesim_logla(PHONE_B, "N", "CureBot", "normal", "normal cevap",
                    json.dumps({"conversation_id": "conv-n", "response_path": "natural"}, ensure_ascii=False))
    items = {i["input"]: i for i in client.get("/api/admin/beta/interactions?limit=100", headers=ADMIN).json()["items"]}
    assert items["hata ureten"]["error_status"] == "error_fallback"
    assert items["normal"]["error_status"] == ""


def test_existing_analytics_admin_still_reachable(client, admin_on, monkeypatch):
    # Shared require_admin still guards the pre-existing analytics endpoints.
    from src.database import _ensure_db
    _ensure_db()  # ensure analytics_events table exists in this fresh test DB
    monkeypatch.setattr(settings, "CUREMENU_ANALYTICS_ENABLED", True)
    monkeypatch.setattr(settings, "CUREMENU_ANALYTICS_HASH_KEY", "test-analytics-secret")
    assert client.get("/api/admin/analytics/summary").status_code == 403
    assert client.get("/api/admin/analytics/summary", headers=ADMIN).status_code == 200
