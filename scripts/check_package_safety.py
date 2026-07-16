"""Reject unsafe distribution archives without printing secret values."""

from __future__ import annotations

import argparse
import re
import sys
import zipfile
from pathlib import Path, PurePosixPath


FORBIDDEN_NAMES = {
    ".env",
    "credentials.json",
    "service-account.json",
    "service_account.json",
}
FORBIDDEN_PARTS = {
    ".cache",
    ".git",
    ".pytest_cache",
    ".venv",
    "__pycache__",
    "blob-report",
    "cache",
    "chroma_db",
    "htmlcov",
    "logs",
    "outputs",
    "playwright-report",
    "security_quarantine",
    "temp_extract",
    "test-results",
    "venv",
}
FORBIDDEN_SUFFIXES = {".db", ".log", ".pyc", ".pyo", ".sqlite", ".sqlite3", ".zip"}
TEXT_SUFFIXES = {
    ".env", ".ini", ".json", ".md", ".py", ".toml", ".txt", ".yaml", ".yml",
}
SECRET_PATTERNS = (
    re.compile(rb"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
    re.compile(rb"AIza[0-9A-Za-z_-]{30,}"),
    re.compile(rb"(?i)\bBearer\s+[A-Za-z0-9._~+/=-]{24,}"),
    re.compile(
        rb"(?im)^\s*(?:GOOGLE_API_KEY|BIOPORTAL_API_KEY|LANGCHAIN_API_KEY|"
        rb"TAVILY_API_KEY|JWT_SECRET_KEY)\s*=\s*(['\"])[A-Za-z0-9._~+/=-]{16,}\1"
    ),
)
SOURCE_SKIP_PARTS = FORBIDDEN_PARTS | {"__pycache__", ".pytest_cache"}


def _normalized_path(name: str) -> PurePosixPath:
    return PurePosixPath(name.replace("\\", "/"))


def unsafe_entry_reason(name: str) -> str | None:
    path = _normalized_path(name)
    lowered_parts = tuple(part.lower() for part in path.parts)
    basename = path.name.lower()
    if basename == ".env" or basename.startswith(".env."):
        return "environment file"
    if basename in FORBIDDEN_NAMES:
        return "credential file"
    if path.suffix.lower() in FORBIDDEN_SUFFIXES or basename == ".coverage":
        return "local/private artifact file"
    if any(part in FORBIDDEN_PARTS for part in lowered_parts):
        return "local/private artifact directory"
    return None


def scan_zip(path: Path) -> list[str]:
    issues: list[str] = []
    try:
        with zipfile.ZipFile(path) as archive:
            for info in archive.infolist():
                if info.is_dir():
                    continue
                reason = unsafe_entry_reason(info.filename)
                if reason:
                    issues.append(f"{info.filename}: {reason}")
                    continue
                suffix = _normalized_path(info.filename).suffix.lower()
                if suffix not in TEXT_SUFFIXES or info.file_size > 2 * 1024 * 1024:
                    continue
                content = archive.read(info)
                if any(pattern.search(content) for pattern in SECRET_PATTERNS):
                    issues.append(f"{info.filename}: high-confidence secret pattern")
    except (OSError, zipfile.BadZipFile):
        issues.append("archive could not be read")
    return issues


def scan_source_tree(root: Path) -> list[str]:
    """Scan source-like files while intentionally excluding local env/artifact paths."""
    issues: list[str] = []
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        relative = path.relative_to(root)
        lowered_parts = {part.lower() for part in relative.parts}
        if lowered_parts & SOURCE_SKIP_PARTS:
            continue
        if path.suffix.lower() == ".zip" or path.name.lower().startswith(".env"):
            continue
        if path.suffix.lower() not in TEXT_SUFFIXES or path.stat().st_size > 2 * 1024 * 1024:
            continue
        try:
            content = path.read_bytes()
        except OSError:
            issues.append(f"{relative}: could not be read")
            continue
        if any(pattern.search(content) for pattern in SECRET_PATTERNS):
            issues.append(f"{relative}: high-confidence secret pattern")
    return issues


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("archives", nargs="*", type=Path)
    parser.add_argument("--source-root", type=Path)
    args = parser.parse_args()

    if not args.archives and args.source_root is None:
        parser.error("provide at least one archive or --source-root")

    unsafe = False
    if args.source_root is not None:
        issues = scan_source_tree(args.source_root)
        if issues:
            unsafe = True
            print(f"SOURCE_UNSAFE: {args.source_root} ({len(issues)} issue(s))")
            for issue in issues:
                print(f"  - {issue}")
        else:
            print(f"SOURCE_SAFE: {args.source_root}")
    for archive in args.archives:
        issues = scan_zip(archive)
        if not issues:
            print(f"SAFE: {archive}")
            continue
        unsafe = True
        print(f"UNSAFE: {archive} ({len(issues)} issue(s))")
        for issue in issues:
            print(f"  - {issue}")
    return 1 if unsafe else 0


if __name__ == "__main__":
    sys.exit(main())
