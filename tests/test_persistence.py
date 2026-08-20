"""Backend-as-source-of-truth persistence: shopping list, media, weekly multi-target.

Verifies F5/route-change survival (reload via GET), account isolation, target
isolation, media type separation/replace, and that multi/family weekly-plan targets
union only the selected members. No real names are hard-coded in logic.
"""
import base64
from unittest.mock import patch

import pytest

from test_api import login_with_profile

_SAFE_PLAN = {
    "days": [{
        "day": "Pazartesi", "breakfast": "Yulaf", "lunch": "Salata", "dinner": "Izgara",
        "snacks": [], "notes": [],
        "meal_details": {
            "breakfast": {"name": "Yulaf", "ingredients": ["yulaf", "elma"]},
            "lunch": {"name": "Salata", "ingredients": ["marul", "domates"]},
            "dinner": {"name": "Izgara", "ingredients": ["tavuk", "brokoli"]},
        },
    }],
    "summary": "Haftalik plan hazir", "warnings": [], "confidence": {},
}

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


# ---- Budget/shopping report persistence (primary "Alışveriş ve Bütçeyi Hesapla") --
# The primary plan-tab action posts to /api/shopping-list; its report must survive
# F5 / logout-login for the SAME account + target + weekly plan, and must NOT be
# shown against a different plan (stale) or leak across accounts/targets.
import hashlib as _hashlib


def _budget_ref(plan_metni: str) -> str:
    return _hashlib.sha256((plan_metni or "").encode("utf-8")).hexdigest()[:16]


def test_budget_report_empty_before_save(client):
    login_with_profile(client, "5557000040", "Budget Empty")
    res = client.get("/api/shopping-list/saved?kimin_icin=kendim")
    assert res.status_code == 200 and res.json()["saved"] is None


@patch("src.routers.tools.alisveris_ve_butce_hesapla", return_value="**Bütçe:** 100-140 TL")
def test_budget_report_persists_and_reloads(mock_budget, client):
    # (A) same account + target + plan: create -> F5 -> report comes back.
    login_with_profile(client, "5557000041", "Budget Save")
    plan = "Pazartesi: mercimek çorbası"
    post = client.post("/api/shopping-list", json={"plan_metni": plan, "kimin_icin": "kendim"})
    assert post.status_code == 200 and post.json()["success"] is True
    saved = client.get(
        f"/api/shopping-list/saved?kimin_icin=kendim&plan_ref={_budget_ref(plan)}"
    ).json()
    assert saved["saved"] and saved["saved"]["rapor"] == "**Bütçe:** 100-140 TL"


@patch("src.routers.tools.alisveris_ve_butce_hesapla", return_value="**Bütçe:** eski")
def test_budget_report_stale_for_different_plan(mock_budget, client):
    # (C / #8) a different weekly plan must NOT show the old report: stale guard.
    login_with_profile(client, "5557000042", "Budget Stale")
    client.post("/api/shopping-list", json={"plan_metni": "eski plan", "kimin_icin": "kendim"})
    stale = client.get(
        f"/api/shopping-list/saved?kimin_icin=kendim&plan_ref={_budget_ref('yeni plan')}"
    ).json()
    assert stale["saved"] is None and stale.get("stale") is True
    # No plan_ref -> latest report is returned (freshness check is opt-in).
    assert client.get("/api/shopping-list/saved?kimin_icin=kendim").json()["saved"]["rapor"] == "**Bütçe:** eski"


@patch("src.routers.tools.alisveris_ve_butce_hesapla", return_value="**Bütçe:** A")
def test_budget_report_account_isolation(mock_budget, client):
    # (D) another account never sees this report.
    login_with_profile(client, "5557000043", "Budget AccA")
    client.post("/api/shopping-list", json={"plan_metni": "p", "kimin_icin": "kendim"})
    login_with_profile(client, "5557000044", "Budget AccB")  # switch account
    assert client.get("/api/shopping-list/saved?kimin_icin=kendim").json()["saved"] is None


@patch("src.routers.tools.alisveris_ve_butce_hesapla", return_value="**Bütçe:** self")
def test_budget_report_target_isolation(mock_budget, client):
    # (E) another target/profile does not show this target's report.
    login_with_profile(client, "5557000045", "Budget Target")
    member_id = _add_member(client)
    client.post("/api/shopping-list", json={"plan_metni": "self-plan", "kimin_icin": "kendim"})
    assert client.get(f"/api/shopping-list/saved?kimin_icin={member_id}").json()["saved"] is None
    assert client.get("/api/shopping-list/saved?kimin_icin=kendim").json()["saved"] is not None


# ---- Weekly plan persistence (backend source-of-truth; survives logout/login) ---
@patch("src.routers.tools.hafizadakini_getir", return_value=[])
@patch("src.routers.tools.haftalik_plan_olustur")
def test_weekly_plan_persists_and_reloads(mock_plan, mock_hafiza, client):
    login_with_profile(client, "5557000030", "WP Save")
    mock_plan.return_value = _SAFE_PLAN
    assert client.post("/api/weekly-plan", json={"kimin_icin": "kendim"}).status_code == 200
    saved = client.get("/api/weekly-plan/saved?kimin_icin=kendim").json()
    assert saved["saved"] and saved["saved"]["plan"]["summary"] == "Haftalik plan hazir"
    assert saved["profile_changed"] is False


@patch("src.routers.tools.hafizadakini_getir", return_value=[])
@patch("src.routers.tools.haftalik_plan_olustur")
def test_weekly_plan_account_isolation(mock_plan, mock_hafiza, client):
    login_with_profile(client, "5557000031", "WP A")
    mock_plan.return_value = _SAFE_PLAN
    client.post("/api/weekly-plan", json={"kimin_icin": "kendim"})
    login_with_profile(client, "5557000032", "WP B")  # different account
    assert client.get("/api/weekly-plan/saved?kimin_icin=kendim").json()["saved"] is None


@patch("src.routers.tools.hafizadakini_getir", return_value=[])
@patch("src.routers.tools.haftalik_plan_olustur")
def test_weekly_plan_survives_logout_login(mock_plan, mock_hafiza, client):
    mock_plan.return_value = _SAFE_PLAN
    login_with_profile(client, "5557000033", "WP Logout")
    client.post("/api/weekly-plan", json={"kimin_icin": "kendim"})
    client.post("/api/logout")  # logout clears client caches only
    login_with_profile(client, "5557000033", "WP Logout")  # log back in
    saved = client.get("/api/weekly-plan/saved?kimin_icin=kendim").json()
    assert saved["saved"] and saved["saved"]["plan"]["summary"] == "Haftalik plan hazir"


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


def test_media_by_uid_roundtrip_and_owner_isolation(client):
    from src.database import media_kaydet
    login_with_profile(client, "5557000017", "Media Uid")
    media_kaydet("5557000017", "uid-abc", "fridge", b"\xff\xd8\xff\xe0blob", content_type="image/jpeg")
    got = client.get("/api/media?media_type=fridge&media_uid=uid-abc").json()["media"]
    assert got and base64.b64decode(got["image_base64"].split(",", 1)[1]) == b"\xff\xd8\xff\xe0blob"
    login_with_profile(client, "5557000018", "Media Uid Other")  # different account
    assert client.get("/api/media?media_type=fridge&media_uid=uid-abc").json()["media"] is None


@patch("src.routers.tools.mutfak_asistani", return_value='{"name":"Salata","ingredients":["marul","domates"],"preparation":"Karıştır."}')
@patch("src.routers.tools.extract_ingredients_from_image_base64", return_value="marul, domates")
def test_fridge_scan_stores_preview_by_uid_not_base64_in_log(mock_scan, mock_recipe, client):
    from io import BytesIO
    from PIL import Image
    login_with_profile(client, "5557000019", "Fridge Media")
    buf = BytesIO(); Image.new("RGB", (48, 32), (10, 20, 30)).save(buf, "JPEG")
    preview = "data:image/jpeg;base64," + base64.b64encode(buf.getvalue()).decode()
    resp = client.post("/api/fridge-scan", json={"kimin_icin": "kendim", "image_base64": preview, "image_preview_base64": preview})
    assert resp.status_code == 200
    import json as _json
    record = next(log for log in client.get("/api/history?page=1&limit=10").json()["loglar"] if log["eylem"] == "Buzdolabı")
    metadata = _json.loads(record["metadata"])
    # Canonical path: reference by uid, and NO truncated base64 in the log.
    assert metadata.get("media_uid") and metadata.get("media_type") == "fridge"
    assert "image_preview_base64" not in metadata
    got = client.get(f"/api/media?media_type=fridge&media_uid={metadata['media_uid']}").json()["media"]
    assert got and got["image_base64"].startswith("data:image/")


@patch("src.routers.tools.menu_danismani", return_value="🟢 Daha uygun: Salata\n🔴 Kaçın: -")
@patch("src.routers.tools.extract_text_from_image_base64", return_value="Menu: Salata, Corba, Izgara Tavuk")
def test_menu_scan_stores_preview_by_uid_not_base64(mock_extract, mock_advisor, client):
    from io import BytesIO
    from PIL import Image
    login_with_profile(client, "5557000040", "Menu Media")
    buf = BytesIO(); Image.new("RGB", (48, 32), (9, 9, 9)).save(buf, "JPEG")
    preview = "data:image/jpeg;base64," + base64.b64encode(buf.getvalue()).decode()
    resp = client.post("/api/scan-menu-image", json={"kimin_icin": "kendim", "image_base64": preview, "image_preview_base64": preview})
    assert resp.status_code == 200 and resp.json()["success"] is True and resp.json()["media_uid"]
    import json as _json
    record = next(log for log in client.get("/api/history?page=1&limit=10").json()["loglar"] if log["eylem"] == "Menü Analizi")
    metadata = _json.loads(record["metadata"])
    assert metadata.get("media_uid") and metadata.get("media_type") == "menu"
    assert "image_preview_base64" not in metadata  # no truncated base64 in the log
    got = client.get(f"/api/media?media_type=menu&media_uid={metadata['media_uid']}").json()["media"]
    assert got and got["image_base64"].startswith("data:image/")


@patch("src.routers.tools.menu_danismani", return_value="Metin menü analizi")
@patch("src.routers.tools.extract_text_from_image_base64", return_value="Menu text")
def test_menu_scan_without_preview_needs_no_media(mock_extract, mock_advisor, client):
    login_with_profile(client, "5557000041", "Menu No Media")
    resp = client.post("/api/scan-menu-image", json={"kimin_icin": "kendim", "image_base64": "data:image/jpeg;base64,abc"})
    assert resp.status_code == 200
    assert resp.json().get("media_uid") is None  # no preview -> no media asset


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
