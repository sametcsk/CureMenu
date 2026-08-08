"""Railway-safe startup wrapper for CureMenu closed beta.

This module normalizes Railway-provided environment variables before importing
CureMenu settings, verifies required secrets/persistence, bootstraps the SQLite
and clinical evidence stores on the mounted volume, then execs Uvicorn.
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path


def _set_if_missing(key: str, value: str) -> None:
    current = str(os.environ.get(key, "")).strip()
    if not current:
        os.environ[key] = value


def configure_railway_environment() -> dict[str, str]:
    """Configure safe defaults while respecting explicit operator overrides."""
    _set_if_missing("APP_ENV", "staging")
    _set_if_missing("DEBUG", "false")
    _set_if_missing("CUREMENU_INSTANCE_COUNT", "1")
    _set_if_missing("CUREMENU_COOKIE_SECURE", "true")
    _set_if_missing("TRUST_PROXY_HEADERS", "true")
    _set_if_missing("LANGCHAIN_TRACING", "false")
    _set_if_missing("LANGCHAIN_TRACING_V2", "false")
    _set_if_missing("LANGSMITH_TRACING", "false")
    _set_if_missing("LANGSMITH_TRACING_V2", "false")
    _set_if_missing("LOG_LEVEL", "INFO")

    # Railway healthchecks use this Host header. The public service domain is
    # added when available; wildcard Railway domains cover first deployment and
    # domain regeneration without accepting arbitrary hosts.
    public_domain = str(os.environ.get("RAILWAY_PUBLIC_DOMAIN", "")).strip()
    if not str(os.environ.get("ALLOWED_HOSTS", "")).strip():
        hosts = ["healthcheck.railway.app"]
        if public_domain:
            hosts.append(public_domain)
        else:
            hosts.append("*.up.railway.app")
        os.environ["ALLOWED_HOSTS"] = ",".join(hosts)

    # Same-origin frontend calls do not require CORS, but production validation
    # deliberately rejects '*'. Use the Railway domain when it exists.
    cors = str(os.environ.get("CORS_ORIGINS", "")).strip()
    if not cors or cors == "*":
        os.environ["CORS_ORIGINS"] = (
            f"https://{public_domain}" if public_domain else "https://curemenu.invalid"
        )

    volume_mount = str(os.environ.get("RAILWAY_VOLUME_MOUNT_PATH", "")).strip()
    explicit_db = str(os.environ.get("CUREMENU_DB_PATH", "")).strip()
    explicit_chroma = str(os.environ.get("CHROMA_PERSIST_DIR", "")).strip()

    if volume_mount:
        volume = Path(volume_mount)
        volume.mkdir(parents=True, exist_ok=True)
        _set_if_missing("CUREMENU_DB_PATH", str(volume / "healmenu.db"))
        _set_if_missing("CHROMA_PERSIST_DIR", str(volume / "chroma_db"))

        # Persist Hugging Face / SentenceTransformer artifacts on the same
        # Railway volume so the embedding model is downloaded only once.
        hf_home = volume / "model_cache" / "huggingface"
        st_home = volume / "model_cache" / "sentence_transformers"
        hf_home.mkdir(parents=True, exist_ok=True)
        st_home.mkdir(parents=True, exist_ok=True)
        _set_if_missing("HF_HOME", str(hf_home))
        _set_if_missing("SENTENCE_TRANSFORMERS_HOME", str(st_home))
    elif not (explicit_db and explicit_chroma):
        raise RuntimeError(
            "Railway persistent volume is required. Attach a volume to the service "
            "(recommended mount path: /data) or explicitly set both "
            "CUREMENU_DB_PATH and CHROMA_PERSIST_DIR to persistent paths."
        )

    # First Railway boot must be able to fetch the embedding model into the
    # persistent cache. Operators may override this to true after the cache has
    # been populated successfully.
    _set_if_missing("EMBEDDINGS_LOCAL_ONLY", "false")

    if not str(os.environ.get("GOOGLE_API_KEY", "")).strip():
        raise RuntimeError("GOOGLE_API_KEY is required in Railway service variables.")

    # A stable secret is mandatory; never auto-generate a new one on each boot,
    # because that would invalidate sessions and change opaque memory HMAC keys.
    jwt_secret = str(os.environ.get("JWT_SECRET_KEY", "")).strip()
    if not jwt_secret:
        raise RuntimeError(
            "JWT_SECRET_KEY is required in Railway service variables. Generate and "
            "store one once (for example: python -c \"import secrets; print(secrets.token_urlsafe(48))\")."
        )
    if len(jwt_secret) < 32:
        raise RuntimeError("JWT_SECRET_KEY must be at least 32 characters long.")

    return {
        "app_env": os.environ["APP_ENV"],
        "db_path": os.environ["CUREMENU_DB_PATH"],
        "chroma_path": os.environ["CHROMA_PERSIST_DIR"],
        "allowed_hosts": os.environ["ALLOWED_HOSTS"],
        "cors_origins": os.environ["CORS_ORIGINS"],
        "embedding_local_only": os.environ["EMBEDDINGS_LOCAL_ONLY"],
    }


def main() -> int:
    configure_railway_environment()

    # Railway volumes are unavailable during build/pre-deploy, so migrations and
    # evidence initialization intentionally happen here, after the volume mount.
    subprocess.run([sys.executable, "-m", "scripts.bootstrap_staging"], check=True)

    port = str(os.environ.get("PORT", "8000")).strip() or "8000"
    argv = [
        sys.executable,
        "-m",
        "uvicorn",
        "api:app",
        "--host",
        "0.0.0.0",
        "--port",
        port,
        "--workers",
        "1",
        "--proxy-headers",
    ]
    os.execv(sys.executable, argv)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
