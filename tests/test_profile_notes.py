from pathlib import Path

from src.models import AileUyesi, Cinsiyet, KullaniciProfili
from src.profile_context import resolve_profile_snapshot_from_profile


ROOT = Path(__file__).resolve().parents[1]


def _register_and_login(client, phone: str) -> None:
    response = client.post(
        "/api/register",
        json={"telefon": phone, "kullanici_adi": "Not Testi", "sifre": "123456"},
    )
    assert response.status_code in (200, 409)
    assert client.post(
        "/api/login",
        json={"telefon": phone, "sifre": "123456"},
    ).status_code == 200


def test_profile_and_family_notes_are_persisted(client):
    _register_and_login(client, "5551112391")

    profile_response = client.post(
        "/api/profile/save",
        json={
            "kullanici_adi": "Not Testi",
            "ad": "Ana Profil",
            "yas": 35,
            "cinsiyet": "kadın",
            "notlar": "Mantar sevmiyorum ve öğlenleri ofisteyim.",
        },
    )
    assert profile_response.status_code == 200

    family_response = client.post(
        "/api/family/add",
        json={
            "ad": "Aile Üyesi",
            "yas": 12,
            "cinsiyet": "erkek",
            "notlar": "Okul günlerinde hızlı hazırlanabilen öğünleri tercih eder.",
        },
    )
    assert family_response.status_code == 200

    profile = client.get("/api/profile/me").json()["profil"]
    assert profile["ana_kullanici"]["notlar"] == "Mantar sevmiyorum ve öğlenleri ofisteyim."
    assert profile["aile_uyeleri"][0]["notlar"] == "Okul günlerinde hızlı hazırlanabilen öğünleri tercih eder."


def test_profile_note_is_part_of_target_snapshot_and_cache_fingerprint():
    base_member = AileUyesi(
        id="self-note",
        ad="Ana Profil",
        yas=35,
        cinsiyet=Cinsiyet.KADIN,
        notlar="Mantar sevmiyorum.",
    )
    changed_member = base_member.model_copy(update={"notlar": "Kereviz sevmiyorum."})

    first = resolve_profile_snapshot_from_profile(
        "account",
        KullaniciProfili(ana_kullanici=base_member),
        "kendim",
    )
    second = resolve_profile_snapshot_from_profile(
        "account",
        KullaniciProfili(ana_kullanici=changed_member),
        "kendim",
    )

    assert first.notes == ("Mantar sevmiyorum.",)
    assert first.quality_profile()["notlar"] == ["Mantar sevmiyorum."]
    assert "Mantar sevmiyorum." in first.profile_summary
    assert first.profile_fingerprint != second.profile_fingerprint


def test_profile_note_length_is_bounded(client):
    _register_and_login(client, "5551112392")

    response = client.post(
        "/api/profile/save",
        json={
            "kullanici_adi": "Not Testi",
            "ad": "Ana Profil",
            "yas": 35,
            "cinsiyet": "kadın",
            "notlar": "x" * 1001,
        },
    )

    assert response.status_code == 422


def test_registration_and_family_forms_submit_optional_notes():
    registration = (ROOT / "frontend" / "kayit.html").read_text(encoding="utf-8")
    dashboard = (ROOT / "frontend" / "dashboard.html").read_text(encoding="utf-8")
    profile_manager = (ROOT / "frontend" / "modules" / "profile-family-manager.js").read_text(encoding="utf-8")

    assert 'id="additionalNotes"' in registration
    assert "notlar: document.getElementById('additionalNotes')" in registration
    assert 'id="m_notlar"' in dashboard
    assert "notlar: document.getElementById('m_notlar')" in profile_manager
