from pathlib import Path

import yaml

from scripts import bootstrap_staging


ROOT = Path(__file__).resolve().parents[1]


def test_render_blueprint_uses_persistent_single_instance_staging():
    blueprint = yaml.safe_load((ROOT / "render.yaml").read_text(encoding="utf-8"))
    service = blueprint["services"][0]
    env = {item["key"]: item for item in service["envVars"]}

    assert service["runtime"] == "python"
    assert service["plan"] == "standard"
    assert service["numInstances"] == 1
    assert service["autoDeployTrigger"] == "off"
    assert service["disk"]["mountPath"] == "/var/data"
    assert service["healthCheckPath"] == "/live"
    assert "bootstrap_staging.py" in service["startCommand"]
    assert env["APP_ENV"]["value"] == "staging"
    assert env["CUREMENU_DB_PATH"]["value"].startswith("/var/data/")
    assert env["CHROMA_PERSIST_DIR"]["value"].startswith("/var/data/")
    assert env["CUREMENU_COOKIE_SECURE"]["value"] == "true"
    assert env["TRUST_PROXY_HEADERS"]["value"] == "true"
    assert env["GOOGLE_API_KEY"]["sync"] is False
    assert env["JWT_SECRET_KEY"]["generateValue"] is True


def test_staging_bootstrap_skips_evidence_rebuild_when_collection_exists(monkeypatch, tmp_path):
    calls = []
    monkeypatch.setattr(bootstrap_staging, "PERSIST_ROOT", tmp_path)
    monkeypatch.setattr(bootstrap_staging, "_upgrade_database", lambda: calls.append("migration"))
    monkeypatch.setattr(bootstrap_staging, "_official_evidence_is_ready", lambda: True)
    monkeypatch.setattr(
        bootstrap_staging,
        "sync_evidence",
        lambda **kwargs: calls.append("sync"),
    )
    assert bootstrap_staging.main() == 0
    assert calls == ["migration"]


def test_staging_bootstrap_fails_closed_when_evidence_sync_fails(monkeypatch):
    monkeypatch.setattr(bootstrap_staging, "_official_evidence_is_ready", lambda: False)
    monkeypatch.setattr(bootstrap_staging, "sync_evidence", lambda **kwargs: {"status": "failed"})

    try:
        bootstrap_staging._bootstrap_official_evidence()
    except RuntimeError as exc:
        assert "failed closed" in str(exc)
    else:
        raise AssertionError("Bootstrap must reject an unverified evidence collection")
