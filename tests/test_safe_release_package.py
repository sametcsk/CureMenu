import zipfile

import pytest

from scripts.check_package_safety import scan_zip
from scripts.create_safe_release_package import create_safe_release_package


def test_safe_release_package_excludes_private_artifacts(tmp_path):
    root = tmp_path / "project"
    root.mkdir()
    (root / "app.py").write_text("print('safe')", encoding="utf-8")
    (root / ".env").write_text("GOOGLE_API_KEY=local-only", encoding="utf-8")
    (root / "healmenu.db").write_bytes(b"sqlite")
    (root / "old.zip").write_bytes(b"archive")
    (root / "security_quarantine").mkdir()
    (root / "security_quarantine" / "unsafe.zip").write_bytes(b"archive")
    (root / "logs").mkdir()
    (root / "logs" / "app.log").write_text("private", encoding="utf-8")
    (root / "__pycache__").mkdir()
    (root / "__pycache__" / "app.pyc").write_bytes(b"cache")

    output_dir = tmp_path / "release"
    package = create_safe_release_package(
        root,
        output_dir=output_dir,
        timestamp="20260715_120000",
    )

    with zipfile.ZipFile(package) as archive:
        assert archive.namelist() == ["app.py"]
    assert scan_zip(package) == []


def test_safe_release_package_removes_output_when_secret_scanner_fails(tmp_path):
    root = tmp_path / "project"
    root.mkdir()
    fake_key = "AI" + "za" + ("A" * 32)
    (root / "unsafe.py").write_text(f"KEY = '{fake_key}'", encoding="utf-8")
    output_dir = tmp_path / "release"

    with pytest.raises(RuntimeError, match="Unsafe release package rejected"):
        create_safe_release_package(
            root,
            output_dir=output_dir,
            timestamp="20260715_120001",
        )

    assert not list(output_dir.glob("*.zip"))
    assert not list(output_dir.glob("*.tmp"))
