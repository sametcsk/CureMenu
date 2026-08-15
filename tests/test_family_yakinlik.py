"""Family-member yakinlik: add, edit, persistence and backward compatibility.

Data-driven only — no person name is special-cased anywhere.
"""


def _register(client, phone):
    client.post("/api/register", json={"telefon": phone, "kullanici_adi": "Test Kullanici", "sifre": "123456"})
    client.post("/api/login", json={"telefon": phone, "sifre": "123456"})
    assert client.post("/api/profile/save", json={
        "kullanici_adi": "Test Kullanici", "ad": "Ana Profil", "yas": 40, "cinsiyet": "kadın",
        "hastaliklar": [], "alerjiler": [], "ilaclar": [],
    }).status_code == 200


def _member(client):
    me = client.get("/api/profile/me").json()
    return me["profil"]["aile_uyeleri"][0]


def test_add_member_persists_yakinlik(client):
    _register(client, "5557770001")
    assert client.post("/api/family/add", json={
        "ad": "Cocuk", "yas": 10, "cinsiyet": "erkek", "yakinlik": "ogul",
    }).status_code == 200
    assert _member(client)["yakinlik"] == "ogul"


def test_family_api_normalizes_relationship_label(client):
    _register(client, "5557770006")
    assert client.post("/api/family/add", json={
        "ad": "Cocuk", "yas": 10, "cinsiyet": "erkek", "yakinlik": "annem",
    }).status_code == 200
    assert _member(client)["yakinlik"] == "anne"


def test_legacy_member_without_yakinlik_is_valid(client):
    _register(client, "5557770002")
    assert client.post("/api/family/add", json={
        "ad": "Cocuk", "yas": 10, "cinsiyet": "erkek",
    }).status_code == 200
    # Missing yakinlik stays None and must not break profile read.
    assert _member(client).get("yakinlik") in (None, "")


def test_update_member_sets_and_persists_yakinlik_preserving_id(client):
    _register(client, "5557770003")
    member_id = client.post("/api/family/add", json={
        "ad": "Cocuk", "yas": 12, "cinsiyet": "erkek",
    }).json()["uye_id"]
    assert _member(client).get("yakinlik") in (None, "")

    update = client.put(f"/api/family/{member_id}", json={
        "ad": "Cocuk", "yas": 12, "cinsiyet": "erkek", "yakinlik": "ogul",
    })
    assert update.status_code == 200

    reloaded = _member(client)
    assert reloaded["id"] == member_id          # id preserved across update
    assert reloaded["yakinlik"] == "ogul"       # persisted after reload


def test_update_member_changes_relationship_value(client):
    _register(client, "5557770004")
    member_id = client.post("/api/family/add", json={
        "ad": "Deniz", "yas": 14, "cinsiyet": "erkek", "yakinlik": "ogul",
    }).json()["uye_id"]
    assert client.put(f"/api/family/{member_id}", json={
        "ad": "Deniz", "yas": 14, "cinsiyet": "erkek", "yakinlik": "kardes",
    }).status_code == 200
    assert _member(client)["yakinlik"] == "kardes"


def test_update_unknown_member_is_404(client):
    _register(client, "5557770005")
    resp = client.put("/api/family/does-not-exist", json={
        "ad": "Yok", "yas": 30, "cinsiyet": "kadın", "yakinlik": "kiz",
    })
    assert resp.status_code == 404
