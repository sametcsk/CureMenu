import zipfile

from scripts.check_package_safety import scan_source_tree, scan_zip


def test_package_scanner_rejects_env_and_secret_patterns(tmp_path):
    archive = tmp_path / "unsafe.zip"
    with zipfile.ZipFile(archive, "w") as output:
        output.writestr("project/.env", "API_KEY=must-not-ship")
        output.writestr("project/readme.txt", "Authorization: Bearer " + "a" * 32)

    issues = scan_zip(archive)

    assert any("environment file" in issue for issue in issues)
    assert any("secret pattern" in issue for issue in issues)


def test_package_scanner_accepts_safe_source_archive(tmp_path):
    archive = tmp_path / "safe.zip"
    with zipfile.ZipFile(archive, "w") as output:
        output.writestr("project/src/example.py", "print('safe package')\n")
        output.writestr("project/README.md", "Environment values are configured outside the archive.\n")

    assert scan_zip(archive) == []


def test_source_scanner_detects_high_confidence_key_without_exposing_value(tmp_path):
    source = tmp_path / "unsafe.py"
    source.write_text("GOOGLE_API_KEY = '" + "AIza" + "A" * 32 + "'\n", encoding="utf-8")

    issues = scan_source_tree(tmp_path)

    assert issues == ["unsafe.py: high-confidence secret pattern"]
