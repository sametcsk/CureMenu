from src.database import profil_getir_db, retention_summary_db


def _register(client, telefon: str, password: str = "123456"):
    response = client.post(
        "/api/register",
        json={"telefon": telefon, "kullanici_adi": "Gizlilik Test", "sifre": password},
    )
    assert response.status_code == 200
    return response


def test_account_export_is_scoped_and_excludes_password_material(client):
    _register(client, "5558111001")

    response = client.get("/api/account/export")

    assert response.status_code == 200
    payload = response.json()
    assert payload["profile"]["telefon"] == "5558111001"
    assert payload["schema_version"] == "1"
    assert "sifre_hash" not in response.text
    assert "123456" not in response.text


def test_account_delete_requires_password_and_preserves_account_on_memory_failure(client, monkeypatch):
    _register(client, "5558111002")

    wrong_password = client.request(
        "DELETE",
        "/api/account",
        json={"sifre": "wrong-password", "confirmation": "DELETE"},
    )
    assert wrong_password.status_code == 401

    def fail_memory_delete(*_args, **_kwargs):
        raise RuntimeError("synthetic chroma failure")

    monkeypatch.setattr("src.routers.privacy.delete_account_memory", fail_memory_delete)
    failed_delete = client.request(
        "DELETE",
        "/api/account",
        json={"sifre": "123456", "confirmation": "DELETE"},
    )

    assert failed_delete.status_code == 503
    assert client.post(
        "/api/login", json={"telefon": "5558111002", "sifre": "123456"}
    ).status_code == 200


def test_account_delete_removes_relational_data_and_clears_session(client, monkeypatch, test_db_path):
    _register(client, "5558111003")
    captured = {}

    def fake_memory_delete(account_id, namespaces):
        captured["account_id"] = account_id
        captured["namespaces"] = namespaces
        return 2

    monkeypatch.setattr("src.routers.privacy.delete_account_memory", fake_memory_delete)
    response = client.request(
        "DELETE",
        "/api/account",
        json={"sifre": "123456", "confirmation": "DELETE"},
    )

    assert response.status_code == 200
    assert response.json()["deleted"]["profiles"] == 1
    assert captured["account_id"] == "5558111003"
    assert client.get("/api/account/export").status_code == 401
    assert client.post(
        "/api/login", json={"telefon": "5558111003", "sifre": "123456"}
    ).status_code == 401

    import sqlite3

    with sqlite3.connect(test_db_path) as connection:
        assert profil_getir_db("5558111003", conn=connection) is None


def test_retention_cleanup_removes_expired_logs_but_preserves_profile(client, test_db_path):
    _register(client, "5558111004")

    import sqlite3

    with sqlite3.connect(test_db_path) as connection:
        connection.execute(
            """
            INSERT INTO interaction_logs (telefon, kullanici_adi, sayfa, istek, cevap, tarih)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            ("5558111004", "Test", "Eski", "istek", "cevap", "2020-01-01T00:00:00+00:00"),
        )
        connection.commit()
        dry_run = retention_summary_db("2021-01-01T00:00:00+00:00", conn=connection)
        assert dry_run["interactions"] == 1
        assert profil_getir_db("5558111004", conn=connection) is not None

        applied = retention_summary_db(
            "2021-01-01T00:00:00+00:00", apply=True, conn=connection
        )
        assert applied["interactions"] == 1
        assert connection.execute(
            "SELECT COUNT(*) FROM interaction_logs WHERE sayfa = 'Eski'"
        ).fetchone()[0] == 0
        assert profil_getir_db("5558111004", conn=connection) is not None
