from __future__ import annotations

from collections import deque
import itertools
import json
import os
import socket
import subprocess
import sys
import tempfile
import threading
import time
import urllib.request
from pathlib import Path
from urllib.parse import urlparse

import pytest

try:
    from playwright import sync_api as playwright_sync
except ImportError:
    message = "Playwright E2E dependencies are not installed. See docs/PLAYWRIGHT_E2E.md."
    if os.getenv("CUREMENU_E2E_REQUIRE_BROWSER", "").lower() in {"1", "true", "yes"}:
        raise pytest.UsageError(message)
    pytest.skip(message, allow_module_level=True)


REPO_ROOT = Path(__file__).resolve().parents[2]
DOMPURIFY_SOURCE = (REPO_ROOT / "tests" / "fixtures" / "dompurify-3.4.12.min.js").read_text(encoding="utf-8")
MARKED_SOURCE = (REPO_ROOT / "tests" / "fixtures" / "marked-12.0.2.min.js").read_text(encoding="utf-8")
_PHONE_SEQUENCE = itertools.count(1001)


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def _drain_server_output(stream, output_lines: deque[str]) -> None:
    try:
        for line in iter(stream.readline, ""):
            output_lines.append(line)
    except (OSError, ValueError):
        return


def _wait_for_server(
    url: str,
    process: subprocess.Popen[str],
    output_lines: deque[str],
    timeout: float = 150.0,
) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if process.poll() is not None:
            output = "".join(output_lines)
            pytest.fail(f"E2E server exited during startup.\n{output}")
        try:
            with urllib.request.urlopen(url, timeout=1.0) as response:
                if response.status == 200:
                    return
        except Exception:
            time.sleep(0.2)
    process.terminate()
    try:
        process.wait(timeout=10)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait(timeout=5)
    output = "".join(output_lines)
    pytest.fail(f"E2E server did not become ready in {timeout:.0f}s.\n{output}")


@pytest.fixture(scope="session")
def e2e_base_url() -> str:
    configured_base_url = os.getenv("CUREMENU_E2E_BASE_URL", "").strip().rstrip("/")
    if configured_base_url:
        yield configured_base_url
        return

    default_temp_root = Path("C:/tmp") if os.name == "nt" else Path(tempfile.gettempdir())
    temp_root = Path(os.getenv("CUREMENU_E2E_TMP", str(default_temp_root))).resolve()
    temp_root.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory(prefix="curemenu-e2e-", dir=temp_root) as temp_dir:
        runtime_dir = Path(temp_dir)
        port = _free_port()
        base_url = f"http://127.0.0.1:{port}"
        env = os.environ.copy()
        env.update(
            {
                "APP_ENV": "test",
                "GOOGLE_API_KEY": "e2e-placeholder-key",
                "JWT_SECRET_KEY": "e2e-only-jwt-secret-not-for-production",
                "CUREMENU_DB_PATH": str(runtime_dir / "e2e.db"),
                "CHROMA_PERSIST_DIR": str(runtime_dir / "chroma"),
                "CORS_ORIGINS": base_url,
                "ALLOWED_HOSTS": "127.0.0.1,localhost,testserver",
                "CUREMENU_COOKIE_SECURE": "false",
                "LANGCHAIN_TRACING_V2": "false",
                "EMBEDDINGS_LOCAL_ONLY": "true",
            }
        )

        creation_flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        process = subprocess.Popen(
            [
                sys.executable,
                "-m",
                "uvicorn",
                "api:app",
                "--host",
                "127.0.0.1",
                "--port",
                str(port),
                "--log-level",
                "warning",
            ],
            cwd=REPO_ROOT,
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            creationflags=creation_flags,
        )
        output_lines: deque[str] = deque(maxlen=2000)
        assert process.stdout is not None
        output_thread = threading.Thread(
            target=_drain_server_output,
            args=(process.stdout, output_lines),
            daemon=True,
        )
        output_thread.start()
        _wait_for_server(f"{base_url}/live", process, output_lines)
        yield base_url

        if process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=5)
        output_thread.join(timeout=2)
        process.stdout.close()


@pytest.fixture(scope="session")
def browser():
    with playwright_sync.sync_playwright() as playwright:
        channel = os.getenv("PLAYWRIGHT_BROWSER_CHANNEL", "msedge")
        try:
            instance = playwright.chromium.launch(channel=channel, headless=True)
        except playwright_sync.Error as channel_error:
            try:
                instance = playwright.chromium.launch(headless=True)
            except playwright_sync.Error:
                message = (
                    "No Playwright browser is available. Install Chromium or set "
                    "PLAYWRIGHT_BROWSER_CHANNEL. Original error: " + str(channel_error)
                )
                if os.getenv("CUREMENU_E2E_REQUIRE_BROWSER", "").lower() in {"1", "true", "yes"}:
                    pytest.fail(message, pytrace=False)
                pytest.skip(message)
        yield instance
        instance.close()


def _external_asset_handler(base_url: str):
    base_origin = urlparse(base_url).netloc

    def handle(route) -> None:
        url = route.request.url
        parsed = urlparse(url)
        if parsed.netloc == base_origin:
            route.continue_()
            return

        if "cdn.tailwindcss.com" in parsed.netloc:
            route.fulfill(
                status=200,
                content_type="application/javascript",
                body=(
                    "window.tailwind={config:{}};"
                    "document.head.insertAdjacentHTML('beforeend',"
                    "'<style>.hidden{display:none!important}.flex{display:flex!important}"
                    ".fixed{position:fixed!important}.inset-0{inset:0!important}.bottom-0{bottom:0!important}"
                    ".inset-x-0{left:0!important;right:0!important}"
                    ".w-\\\\[280px\\\\]{width:280px!important}"
                    "@media(min-width:768px){.md\\\\:flex{display:flex!important}"
                    ".md\\\\:ml-\\\\[280px\\\\]{margin-left:280px!important}}</style>');"
                ),
            )
        elif "marked" in url:
            route.fulfill(
                status=200,
                content_type="application/javascript",
                body=MARKED_SOURCE,
            )
        elif "dompurify" in url:
            route.fulfill(
                status=200,
                content_type="application/javascript",
                body=DOMPURIFY_SOURCE,
            )
        elif "chart" in url:
            route.fulfill(
                status=200,
                content_type="application/javascript",
                body="window.Chart=function(){this.destroy=function(){}};",
            )
        elif "html5-qrcode" in url:
            # QR fallback is part of the E2E contract when the optional CDN is unavailable.
            route.fulfill(status=200, content_type="application/javascript", body="")
        elif parsed.path.endswith(".css"):
            route.fulfill(status=200, content_type="text/css", body="")
        else:
            route.abort()

    return handle


@pytest.fixture()
def browser_page(e2e_base_url: str, browser):
    context = browser.new_context(
        locale="tr-TR",
        viewport={"width": 1440, "height": 1000},
        geolocation={"latitude": 41.0082, "longitude": 28.9784},
        permissions=["geolocation"],
    )
    context.route("**/*", _external_asset_handler(e2e_base_url))
    page = context.new_page()
    runtime_errors: list[str] = []
    page.on("pageerror", lambda error: runtime_errors.append(str(error)))
    yield page, context, runtime_errors
    context.close()


def next_phone() -> str:
    return f"0500000{next(_PHONE_SEQUENCE):04d}"


def seed_authenticated_user(page, context, base_url: str) -> dict[str, str]:
    phone = next_phone()
    password = "E2ePass123"
    name = "Test Kullanici"
    register = context.request.post(
        f"{base_url}/api/register",
        data={"telefon": phone, "kullanici_adi": name, "sifre": password},
    )
    if register.status == 429:
        time.sleep(65)
        register = context.request.post(
            f"{base_url}/api/register",
            data={"telefon": phone, "kullanici_adi": name, "sifre": password},
        )
    assert register.ok, register.text()
    profile = context.request.post(
        f"{base_url}/api/profile/save",
        data={
            "kullanici_adi": name,
            "ad": name,
            "yas": 35,
            "cinsiyet": "erkek",
            "boy": 178,
            "kilo": 78,
            "hedef": "Saglikli Yasam",
            "hastaliklar": ["hipertansiyon"],
            "alerjiler": ["fistik"],
            "ilaclar": ["warfarin"],
            "genetik_hastaliklar": [],
            "tibbi_gecmis": None,
        },
    )
    assert profile.ok, profile.text()
    values = {
        "cm_telefon": phone,
        "cm_kullanici_adi": name,
        "cm_has_profile": "true",
        "cm_onboarding_done": "true",
        "cm_disclaimer_ok": "true",
    }
    page.add_init_script(
        "const values = " + json.dumps(values) + ";"
        "for (const [key, value] of Object.entries(values)) localStorage.setItem(key, value);"
    )
    return {"phone": phone, "password": password, "name": name}


@pytest.fixture()
def authenticated_page(browser_page, e2e_base_url: str):
    page, context, runtime_errors = browser_page
    user = seed_authenticated_user(page, context, e2e_base_url)
    page.goto(f"{e2e_base_url}/dashboard", wait_until="domcontentloaded")
    page.wait_for_function("window.AuthManager && window.WeeklyPlanManager && window.SmartGrocery")
    return page, context, runtime_errors, user
