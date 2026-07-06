from src.models import KullaniciProfili, AileUyesi, Cinsiyet
from src.database import (
    klinik_karar_getir,
    klinik_karar_kaydet,
    klinik_kararlari_getir,
    klinik_kpi_getir,
    profil_getir_db,
    profil_kaydet_db,
)


def test_profil_kayit_ve_getir(test_db_path):
    profil = KullaniciProfili()
    profil.ana_kullanici = AileUyesi(ad="AyÅŸe", yas=35, cinsiyet=Cinsiyet.KADIN, hastaliklar=["diyabet"])

    profil_kaydet_db("5551234567", "AyÅŸe K.", profil)
    yuklenen = profil_getir_db("5551234567")

    assert yuklenen is not None
    assert yuklenen.ana_kullanici.ad == "AyÅŸe"
    assert "diyabet" in yuklenen.ana_kullanici.hastaliklar


def test_bos_kullanici_adi_mevcut_adi_silmez(test_db_path):
    profil = KullaniciProfili()
    profil.ana_kullanici = AileUyesi(ad="Mehmet", yas=40, cinsiyet=Cinsiyet.ERKEK)

    profil_kaydet_db("5559998877", "Mehmet Y.", profil)
    profil_kaydet_db("5559998877", "", profil)

    import sqlite3

    row = sqlite3.connect(test_db_path).execute(
        "SELECT kullanici_adi FROM profiles WHERE telefon = ?", ("5559998877",)
    ).fetchone()

    assert row[0] == "Mehmet Y."


def test_klinik_karar_event_zinciri_kaydedilir(test_db_path):
    record = {
        "decision_id": "dec_test_1",
        "telefon": "5551230000",
        "kimin_icin": "kendim",
        "request": "Mercimek corbasi uygun mu?",
        "final_answer": "Uygun gorunuyor.",
        "final_action": "TARIF_GETIR",
        "risk_score": 0.15,
        "confidence_score": 0.82,
        "confidence": {"final_score": 0.82, "action": "APPROVE"},
        "component_versions": {"model": "test-model"},
        "citations": [{"source_id": "guideline.pdf"}],
        "events": [
            {"event_type": "ConversationStarted", "component": "api.chat", "status": "ok", "metadata": {}, "created_at": "2026-07-03T00:00:00Z"},
            {"event_type": "RiskClassified", "component": "auditor", "status": "ok", "metadata": {"risk_score": 0.15}, "created_at": "2026-07-03T00:00:01Z"},
        ],
        "created_at": "2026-07-03T00:00:00Z",
        "completed_at": "2026-07-03T00:00:02Z",
    }

    klinik_karar_kaydet(record)
    loaded = klinik_karar_getir("dec_test_1")
    listed = klinik_kararlari_getir("5551230000")

    assert loaded is not None
    assert loaded["decision_id"] == "dec_test_1"
    assert loaded["confidence_data"]["action"] == "APPROVE"
    assert loaded["component_versions"]["model"] == "test-model"
    assert loaded["citations"][0]["source_id"] == "guideline.pdf"
    assert [event["event_type"] for event in loaded["events"]] == [
        "ConversationStarted",
        "RiskClassified",
    ]
    assert listed[0]["decision_id"] == "dec_test_1"

    kpis = klinik_kpi_getir("5551230000")
    assert kpis["total_decisions"] == 1
    assert kpis["average_confidence"] == 0.82
    assert kpis["evidence_coverage_rate"] == 100.0

