"""Create a shareable CureMenu source ZIP and reject unsafe output."""

from __future__ import annotations

import argparse
import os
import sys
import zipfile
from datetime import datetime
from pathlib import Path

try:
    from scripts.check_package_safety import scan_zip
except ModuleNotFoundError:  # Direct execution from the scripts directory.
    from check_package_safety import scan_zip


EXCLUDED_DIRS = {
    ".cache",
    ".git",
    ".idea",
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
    "scratch",
    "security_quarantine",
    "temp_extract",
    "test-results",
    "tmphealmenu-pytest",
    "venv",
}
EXCLUDED_SUFFIXES = {
    ".bak",
    ".db",
    ".download",
    ".log",
    ".pyc",
    ".pyo",
    ".sqlite",
    ".sqlite3",
    ".tmp",
    ".zip",
}
EXCLUDED_NAMES = {
    ".coverage",
    "credentials.json",
    "service-account.json",
    "service_account.json",
}


def _should_exclude(relative: Path) -> bool:
    lowered_parts = {part.lower() for part in relative.parts}
    basename = relative.name.lower()
    if lowered_parts & EXCLUDED_DIRS:
        return True
    if basename == ".env" or basename.startswith(".env."):
        return True
    if basename in EXCLUDED_NAMES:
        return True
    return relative.suffix.lower() in EXCLUDED_SUFFIXES


def _safe_source_files(root: Path):
    for path in sorted(root.rglob("*")):
        if path.is_symlink() or not path.is_file():
            continue
        relative = path.relative_to(root)
        if not _should_exclude(relative):
            yield path, relative


def create_safe_release_package(
    root: Path,
    *,
    output_dir: Path | None = None,
    timestamp: str | None = None,
) -> Path:
    root = root.resolve()
    if not root.is_dir():
        raise ValueError(f"Project root does not exist: {root}")

    output_dir = (output_dir or root).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    stamp = timestamp or datetime.now().strftime("%Y%m%d_%H%M%S")
    output_path = output_dir / f"healmenu_safe_release_{stamp}.zip"
    temporary_path = output_dir / f".{output_path.name}.tmp"

    if output_path.exists():
        raise FileExistsError(f"Release package already exists: {output_path}")
    if temporary_path.exists():
        temporary_path.unlink()

    try:
        with zipfile.ZipFile(
            temporary_path,
            mode="w",
            compression=zipfile.ZIP_DEFLATED,
            compresslevel=9,
        ) as archive:
            for source, relative in _safe_source_files(root):
                resolved = source.resolve()
                if not resolved.is_relative_to(root):
                    continue
                archive.write(resolved, relative.as_posix())

        issues = scan_zip(temporary_path)
        if issues:
            raise RuntimeError(
                "Unsafe release package rejected: " + "; ".join(issues)
            )
        os.replace(temporary_path, output_path)
    except Exception:
        temporary_path.unlink(missing_ok=True)
        output_path.unlink(missing_ok=True)
        raise

    return output_path


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--root",
        type=Path,
        default=Path(__file__).resolve().parents[1],
        help="Project root to package (defaults to the repository root).",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        help="Directory for the generated ZIP (defaults to the project root).",
    )
    args = parser.parse_args()

    try:
        package = create_safe_release_package(args.root, output_dir=args.output_dir)
    except Exception as exc:
        print(f"PACKAGE_REJECTED: {exc}", file=sys.stderr)
        return 1

    print(f"PACKAGE_CREATED: {package}")
    print(f"SAFE: {package}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
