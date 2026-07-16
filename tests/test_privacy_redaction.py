import json
import sqlite3

from src.database import etkilesim_logla, klinik_karar_getir, klinik_karar_kaydet
from src.privacy.redaction import redact_data, redact_text


def test_redaction_utility_identifier_maskeler():
    text = (
        "Mail ali@example.com, telefon 0555 123 45 67, "
        "TC 12345678901, IBAN TR330006100519786457841326"
    )

    redacted = redact_text(text)

    assert "ali@example.com" not in redacted
    assert "0555 123 45 67" not in redacted
    assert "12345678901" not in redacted
    assert "TR330006100519786457841326" not in redacted
    assert "[REDACTED_EMAIL]" in redacted
    assert "[REDACTED_PHONE]" in redacted
    assert "[REDACTED_ID]" in redacted
    assert "[REDACTED_IBAN]" in redacted


def test_redaction_utility_uzun_metin_truncate_eder():
    redacted = redact_text("a" * 50, max_length=12)

    assert redacted == "a" * 12 + "...[TRUNCATED]"


def test_redaction_utility_url_ve_bearer_secret_maskeler():
    text = (
        "https://menu.example/path?table=4&access_token=raw-url-token "
        "Authorization: Bearer raw-header-token"
    )

    redacted = redact_text(text)

    assert "raw-url-token" not in redacted
    assert "raw-header-token" not in redacted
    assert redacted.count("[REDACTED_SECRET]") == 2


def test_nested_metadata_redaction_secret_ve_identifier_maskeler():
    metadata = {
        "contact": {"email": "hasta@example.com", "phones": ["+90 555 111 22 33"]},
        "Authorization": "Bearer secret-token",
        "notes": ["TC 12345678901"],
    }

    redacted = redact_data(metadata)

    assert redacted["contact"]["email"] == "[REDACTED_EMAIL]"
    assert redacted["contact"]["phones"][0] == "[REDACTED_PHONE]"
    assert redacted["Authorization"] == "[REDACTED_SECRET]"
    assert redacted["notes"][0] == "TC [REDACTED_ID]"


def test_interaction_log_persistence_identifier_redacted(test_db_path):
    metadata = json.dumps(
        {
            "nested": {"email": "log@example.com"},
            "api_key": "should-not-persist",
        },
        ensure_ascii=False,
    )

    etkilesim_logla(
        "5557778899",
        "Hasta 0555 111 22 33",
        "CureBot",
        "Bana log@example.com üzerinden ulaş, TC 12345678901",
        "IBAN TR330006100519786457841326 kaydı var",
        metadata,
    )

    row = sqlite3.connect(test_db_path).execute(
        "SELECT kullanici_adi, istek, cevap, metadata FROM interaction_logs WHERE telefon = ?",
        ("5557778899",),
    ).fetchone()

    persisted = " ".join(value or "" for value in row)
    assert "0555 111 22 33" not in persisted
    assert "log@example.com" not in persisted
    assert "12345678901" not in persisted
    assert "TR330006100519786457841326" not in persisted
    assert "should-not-persist" not in persisted
    assert "[REDACTED_PHONE]" in persisted
    assert "[REDACTED_EMAIL]" in persisted
    assert "[REDACTED_ID]" in persisted
    assert "[REDACTED_IBAN]" in persisted
    assert "[REDACTED_SECRET]" in persisted


def test_clinical_decision_event_metadata_identifier_redacted(test_db_path):
    record = {
        "decision_id": "dec_privacy_1",
        "telefon": "5551230000",
        "kimin_icin": "kendim",
        "request": "TC 12345678901 ve e-posta hasta@example.com",
        "final_answer": "Telefon 0555 123 45 67 ile takip edilmesin.",
        "final_action": "SOHBET",
        "risk_score": 0.2,
        "confidence_score": 0.7,
        "confidence": {"debug": "mail hasta@example.com"},
        "component_versions": {"model": "test"},
        "citations": [{"url": "mailto:hasta@example.com"}],
        "events": [
            {
                "event_type": "PrivacyProbe",
                "component": "test",
                "status": "ok",
                "metadata": {
                    "contact": "0555 999 88 77",
                    "nested": {"iban": "TR330006100519786457841326"},
                    "authorization": "Bearer raw-token",
                },
                "created_at": "2026-07-06T00:00:00Z",
            }
        ],
        "created_at": "2026-07-06T00:00:00Z",
        "completed_at": "2026-07-06T00:00:01Z",
    }

    klinik_karar_kaydet(record)
    loaded = klinik_karar_getir("dec_privacy_1")

    serialized = json.dumps(loaded, ensure_ascii=False)
    assert "12345678901" not in serialized
    assert "hasta@example.com" not in serialized
    assert "0555 123 45 67" not in serialized
    assert "0555 999 88 77" not in serialized
    assert "TR330006100519786457841326" not in serialized
    assert "raw-token" not in serialized
    assert "[REDACTED_ID]" in serialized
    assert "[REDACTED_EMAIL]" in serialized
    assert "[REDACTED_PHONE]" in serialized
    assert "[REDACTED_IBAN]" in serialized
    assert "[REDACTED_SECRET]" in serialized
