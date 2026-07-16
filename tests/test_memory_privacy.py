import json
import pytest

from src.models import AileUyesi, Cinsiyet
from src.memory import build_memory_namespace, geri_bildirim_ekle, hafizadakini_getir


class FakeDocument:
    def __init__(self, page_content):
        self.page_content = page_content


class FakeVectorDB:
    def __init__(self):
        self.rows = []

    def add_texts(self, texts, metadatas):
        self.rows.extend(zip(texts, metadatas))

    def similarity_search(self, query, k, filter):
        del query
        matches = [
            FakeDocument(text)
            for text, metadata in self.rows
            if metadata.get("kullanici_id") == filter.get("kullanici_id")
        ]
        return matches[:k]


def test_memory_namespace_accounts_and_members_are_isolated(monkeypatch):
    fake_db = FakeVectorDB()
    monkeypatch.setattr("src.memory._get_vector_db", lambda: fake_db)

    same_name_first = AileUyesi(ad="Ali", yas=30, cinsiyet=Cinsiyet.ERKEK)
    same_name_second = AileUyesi(ad="Ali", yas=30, cinsiyet=Cinsiyet.ERKEK)
    first_account = build_memory_namespace("05551112233", f"member:{same_name_first.id}")
    second_account = build_memory_namespace("05559998877", f"member:{same_name_second.id}")
    first_member = build_memory_namespace("05551112233", "member:member-a")
    second_member = build_memory_namespace("05551112233", "member:member-b")
    family_scope = build_memory_namespace("05551112233", "family")

    assert first_account != second_account
    assert first_member != second_member
    assert family_scope not in {first_account, first_member, second_member}
    assert "05551112233" not in first_account
    assert same_name_first.id not in first_account

    geri_bildirim_ekle(first_account, "yalnizca birinci hesabin gizli kaydi")
    geri_bildirim_ekle(first_member, "yalnizca ilk aile uyesinin gizli kaydi")

    assert hafizadakini_getir(first_account, "gizli") == ["yalnizca birinci hesabin gizli kaydi"]
    assert hafizadakini_getir(second_account, "gizli") == []
    assert hafizadakini_getir(first_member, "gizli") == ["yalnizca ilk aile uyesinin gizli kaydi"]
    assert hafizadakini_getir(second_member, "gizli") == []


def test_legacy_memory_namespaces_are_not_read_or_written(monkeypatch):
    fake_db = FakeVectorDB()
    monkeypatch.setattr("src.memory._get_vector_db", lambda: fake_db)

    assert hafizadakini_getir("user_family", "gizli") == []
    assert hafizadakini_getir("user_ali", "gizli") == []
    with pytest.raises(ValueError):
        geri_bildirim_ekle("user_family", "legacy kayit")
    assert fake_db.rows == []


def test_chroma_persistence_redacts_text_and_nested_metadata(monkeypatch):
    fake_db = FakeVectorDB()
    monkeypatch.setattr("src.memory._get_vector_db", lambda: fake_db)
    namespace = build_memory_namespace("05551112233", "member:member-a")

    raw_values = (
        "12345678901",
        "0555 123 45 67",
        "hasta@example.com",
        "TR330006100519786457841326",
        "raw-secret-value",
    )
    geri_bildirim_ekle(
        namespace,
        "12345678901_0555 123 45 67_hasta@example.com.pdf ozeti "
        "TR330006100519786457841326",
        metadata={
            "contact": {"email": "hasta@example.com"},
            "api_key": "raw-secret-value",
            "token": "raw-token-value",
        },
    )

    stored_text, stored_metadata = fake_db.rows[0]
    serialized = stored_text + json.dumps(stored_metadata, ensure_ascii=False)
    for raw in raw_values:
        assert raw not in serialized
    assert "raw-token-value" not in serialized
    assert "[REDACTED_ID]" in stored_text
    assert "[REDACTED_PHONE]" in stored_text
    assert "[REDACTED_EMAIL]" in stored_text
    assert "[REDACTED_IBAN]" in stored_text
    assert "[REDACTED_SECRET]" in stored_metadata["context_json"]
