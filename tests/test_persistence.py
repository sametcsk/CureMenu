"""Backend-as-source-of-truth persistence: shopping list, media, weekly multi-target.

Verifies F5/route-change survival (reload via GET), account isolation, target
isolation, media type separation/replace, and that multi/family weekly-plan targets
union only the selected members. No real names are hard-coded in logic.
"""
import base64
from unittest.mock import patch

import pytest

from test_api import login_with_profile

MENU_IMG = "data:image/jpeg;base64," + base64.b64encode(b"\xff\xd8\xff\xe0menu-bytes").decode()
FRIDGE_IMG = "data:image/jpeg;base64," + base64.b64encode(b"\xff\xd8\xff\xe0fridge-bytes").decode()

def _basket(summary="Sepet hazır"):
    return {
        "items": [], "excluded_items": [], "risk_items": [], "categories": {},
        "estimated_min_total": 0.0, "estimated_max_total": 0.0,
        "health_safe_total_items": 0, "caution_items": 0, "avoid_items": 0, "unknown_items": 0,
        "recommendation_summary": summary, "market_search_links": [],
        "disclaimer": "Bilgilendirme amaçlıdır.", "price_catalog_version": "test",
    }


_BASKET = _basket()
_STATE = {"hedef_islem": "GROCERY", "guvenli_mi": True}
_DECISION = {"decision_id": "d1", "risk_score": 0.0, "confidence_score": 0.0}


def _add_member(client, ad="Cocuk", yakinlik="ogul", alerjiler=None):
    client.post("/api/family/add", json={
        "ad": ad, "yas": 9, "cinsiyet": "erkek", "yakinlik": yakinlik,
        "alerjiler": alerjiler or [], "hastaliklar": [], "ilaclar": [],
    })
    me = client.get("/api/profile/me").json()
    members = me.get("aile_uyeleri") or me.get("profil", {}).get("aile_uyeleri") or []
    return members[-1]["id"] if members else None


# ---- Shopping list -----------------------------------------------------------
def test_shopping_list_empty_before_save(client):
    login_with_profile(client, "5557000001", "Grocery Empty")
    res = client.get("/api/smart-grocery/saved?kimin_icin=kendim")
    assert res.status_code == 200 and res.json()["saved"] is None


@patch("src.routers.grocery.build_decision_record", return_value=_DECISION)
@patch("src.routers.grocery.build_smart_grocery", return_value=(_BASKET, _STATE))
def test_shopping_list_persists_and_reloads(mock_g, mock_d, client):
    login_with_profile(client, "5557000002", "Grocery Save")
    post = client.post("/api/smart-grocery", json={"weekly_plan": "Pazartesi: mercimek", "kimin_icin": "kendim"})
    assert post.status_code == 200
    # Simulates F5 / route change: reload purely from backend.
    saved = client.get("/api/smart-grocery/saved?kimin_icin=kendim").json()["saved"]
    assert saved and saved["recommendation_summary"] == "Sepet hazır"


@patch("src.routers.grocery.build_decision_record", return_value=_DECISION)
@patch("src.routers.grocery.build_smart_grocery", return_value=(_BASKET, _STATE))
def test_shopping_list_account_isolation(mock_g, mock_d, client):
    login_with_profile(client, "5557000003", "Grocery A")
    client.post("/api/smart-grocery", json={"weekly_plan": "x", "kimin_icin": "kendim"})
    login_with_profile(client, "5557000004", "Grocery B")  # switch account
    assert client.get("/api/smart-grocery/saved?kimin_icin=kendim").json()["saved"] is None


@patch("src.routers.grocery.build_decision_record", return_value=_DECISION)
@patch("src.routers.grocery.build_smart_grocery", return_value=(_BASKET, _STATE))
def test_shopping_list_target_isolation(mock_g, mock_d, client):
    login_with_profile(client, "5557000005", "Grocery Target")
    member_id = _add_member(client)
    client.post("/api/smart-grocery", json={"weekly_plan": "self-plan", "kimin_icin": "kendim"})
    # Member target has no saved list of its own.
    assert client.get(f"/api/smart-grocery/saved?kimin_icin={member_id}").json()["saved"] is None
    assert client.get("/api/smart-grocery/saved?kimin_icin=kendim").json()["saved"] is not None


@patch("src.routers.grocery.build_decision_record", return_value=_DECISION)
@patch("src.routers.grocery.build_smart_grocery")
def test_shopping_list_update_replaces(mock_g, mock_d, client):
    login_with_profile(client, "5557000006", "Grocery Update")
    mock_g.return_value = (_basket("ilk"), _STATE)
    client.post("/api/smart-grocery", json={"weekly_plan": "a", "kimin_icin": "kendim"})
    mock_g.return_value = (_basket("ikinci"), _STATE)
    client.post("/api/smart-grocery", json={"weekly_plan": "b", "kimin_icin": "kendim"})
    saved = client.get("/api/smart-grocery/saved?kimin_icin=kendim").json()["saved"]
    assert saved["recommendation_summary"] == "ikinci"


# ---- Media -------------------------------------------------------------------
def test_media_save_load_roundtrip(client):
    login_with_profile(client, "5557000010", "Media Save")
    assert client.post("/api/media", json={"media_type": "menu", "kimin_icin": "kendim", "image_base64": MENU_IMG}).status_code == 200
    media = client.get("/api/media?media_type=menu&kimin_icin=kendim").json()["media"]
    assert media and media["media_type"] == "menu" and media["image_base64"].startswith("data:image/")


def test_media_type_separation(client):
    login_with_profile(client, "5557000011", "Media Types")
    client.post("/api/media", json={"media_type": "menu", "kimin_icin": "kendim", "image_base64": MENU_IMG})
    client.post("/api/media", json={"media_type": "fridge", "kimin_icin": "kendim", "image_base64": FRIDGE_IMG})
    menu = client.get("/api/media?media_type=menu&kimin_icin=kendim").json()["media"]
    fridge = client.get("/api/media?media_type=fridge&kimin_icin=kendim").json()["media"]
    assert menu["image_base64"] != fridge["image_base64"]


def test_media_replace_keeps_latest(client):
    login_with_profile(client, "5557000012", "Media Replace")
    client.post("/api/media", json={"media_type": "menu", "kimin_icin": "kendim", "image_base64": MENU_IMG})
    client.post("/api/media", json={"media_type": "menu", "kimin_icin": "kendim", "image_base64": FRIDGE_IMG})
    media = client.get("/api/media?media_type=menu&kimin_icin=kendim").json()["media"]
    assert base64.b64decode(media["image_base64"].split(",", 1)[1]) == b"\xff\xd8\xff\xe0fridge-bytes"


def test_media_account_isolation(client):
    login_with_profile(client, "5557000013", "Media A")
    client.post("/api/media", json={"media_type": "menu", "kimin_icin": "kendim", "image_base64": MENU_IMG})
    login_with_profile(client, "5557000014", "Media B")
    assert client.get("/api/media?media_type=menu&kimin_icin=kendim").json()["media"] is None


def test_media_validation(client):
    login_with_profile(client, "5557000015", "Media Valid")
    assert client.post("/api/media", json={"media_type": "xxx", "kimin_icin": "kendim", "image_base64": MENU_IMG}).status_code == 400
    assert client.post("/api/media", json={"media_type": "menu", "kimin_icin": "kendim", "image_base64": "not-base64!!"}).status_code == 422
    assert client.get("/api/media?media_type=menu&kimin_icin=kendim").json()["media"] is None


def test_media_size_cap_rejects_oversized_preview(client):
    from src.routers.media import MAX_MEDIA_BYTES
    login_with_profile(client, "5557000016", "Media Cap")
    big = "data:image/jpeg;base64," + base64.b64encode(b"x" * (MAX_MEDIA_BYTES + 1000)).decode()
    assert client.post("/api/media", json={"media_type": "menu", "kimin_icin": "kendim", "image_base64": big}).status_code == 413
    # nothing stored for an oversized upload
    assert client.get("/api/media?media_type=menu&kimin_icin=kendim").json()["media"] is None


# ---- Weekly plan multi-target (tools resolver, single common family plan) -----
def test_weekly_multi_target_unions_only_selected_members(client):
    from src.database import get_connection
    from src.profile_context import resolve_profile_snapshot
    from src.target_resolution import multi_key

    login_with_profile(client, "5557000020", "Plan Multi", hastaliklar=["diyabet"])
    spouse = _add_member(client, ad="Es", yakinlik="es")
    child = _add_member(client, ad="Cocuk", yakinlik="ogul", alerjiler=["süt"])
    with get_connection(None) as db:
        fam = resolve_profile_snapshot("5557000020", "aile", db=db)
        subset = resolve_profile_snapshot("5557000020", multi_key(["kendim", spouse]), db=db)
        single = resolve_profile_snapshot("5557000020", child, db=db)
    assert "diyabet" in fam.diseases and "süt" in fam.allergies          # all family unioned
    assert "süt" not in subset.allergies                                 # child NOT in the subset
    assert subset.target_scope == "multi" and subset.target_key.startswith("multi:")
    assert set(single.allergies) == {"süt"}                              # single member isolated


def test_multi_target_key_is_canonical_order_independent(client):
    from src.database import get_connection
    from src.profile_context import resolve_profile_snapshot

    login_with_profile(client, "5557000021", "Plan Canon")
    spouse = _add_member(client, ad="Es", yakinlik="es")
    child = _add_member(client, ad="Cocuk", yakinlik="ogul", alerjiler=["süt"])
    with get_connection(None) as db:
        forward = resolve_profile_snapshot("5557000021", f"multi:{spouse}+{child}", db=db)
        reverse = resolve_profile_snapshot("5557000021", f"multi:{child}+{spouse}", db=db)
    # Same semantic set -> one canonical key/bucket (no duplicate saved artifact).
    assert forward.target_key == reverse.target_key
    assert forward.profile_fingerprint == reverse.profile_fingerprint


def test_member_with_minimal_fields_resolves_without_crash(client):
    from src.database import get_connection
    from src.profile_context import resolve_profile_snapshot

    login_with_profile(client, "5557000022", "Plan Minimal")
    # Member with only the required fields (no diseases/allergies/meds).
    minimal = _add_member(client, ad="Sade", yakinlik="kardes")
    with get_connection(None) as db:
        snap = resolve_profile_snapshot("5557000022", minimal, db=db)
    assert snap.target_scope == "member" and snap.target_key == minimal
    assert snap.allergies == () and snap.diseases == ()
