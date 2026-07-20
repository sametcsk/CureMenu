from __future__ import annotations

from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[2]
FRONTEND = ROOT / "frontend"
FIXTURES = ROOT / "tests" / "fixtures"


@pytest.fixture()
def frontend_page(browser):
    context = browser.new_context(locale="tr-TR")
    context.route("https://**", lambda route: route.abort())
    page = context.new_page()
    runtime_errors: list[str] = []
    page.on("pageerror", lambda error: runtime_errors.append(str(error)))
    yield page, runtime_errors
    context.close()


def test_registration_summary_renders_user_markup_as_text(frontend_page) -> None:
    page, runtime_errors = frontend_page
    payloads = {
        "fullName": '<img src=x onerror="window.__xss=1">',
        "conditions": '<svg onload="window.__xss=2"></svg>',
        "allergies": '</strong><img src=x onerror="window.__xss=3">',
        "medications": '<script>window.__xss=4</script>',
    }

    page.goto((FRONTEND / "kayit.html").as_uri(), wait_until="domcontentloaded")
    page.evaluate("window.__xss = 0")
    page.evaluate(
        """
        payloads => {
            for (const [id, value] of Object.entries(payloads)) {
                document.getElementById(id).value = value;
            }
            renderSummary();
        }
        """,
        payloads,
    )

    summary = page.locator("#profileSummary")
    assert summary.locator("img, svg, script").count() == 0
    assert summary.locator("[onerror], [onload]").count() == 0
    rendered_text = summary.text_content() or ""
    for payload in payloads.values():
        assert payload in rendered_text
    assert page.evaluate("window.__xss") == 0
    assert not runtime_errors


def test_real_dompurify_blocks_xss_and_preserves_markdown(frontend_page) -> None:
    page, runtime_errors = frontend_page
    payload = """
**Güvenli kalın metin** ve *italik metin*
<img src=x onerror="window.__xss=1">
<svg onload="window.__xss=2"></svg>
</div><script>window.__xss=3</script>
"""

    page.set_content("<div id='root'></div>")
    page.add_script_tag(path=FIXTURES / "marked-12.0.2.min.js")
    page.add_script_tag(path=FIXTURES / "dompurify-3.4.12.min.js")
    page.add_script_tag(path=FRONTEND / "modules" / "api-client.js")
    result = page.evaluate(
        """
        payload => {
            window.__xss = 0;
            const host = document.createElement('div');
            host.id = 'xss-regression-host';
            host.innerHTML = formatMarkdownSafe(payload);
            document.body.appendChild(host);
            return {
                version: window.DOMPurify && window.DOMPurify.version,
                html: host.innerHTML,
            };
        }
        """,
        payload,
    )
    page.wait_for_timeout(100)

    host = page.locator("#xss-regression-host")
    assert result["version"] == "3.4.12"
    assert host.locator("strong").inner_text() == "Güvenli kalın metin"
    assert host.locator("em").inner_text() == "italik metin"
    assert host.locator("script, [onerror], [onload]").count() == 0
    assert page.evaluate("window.__xss") == 0
    assert not runtime_errors


def test_api_error_markup_is_rendered_as_text(frontend_page) -> None:
    page, runtime_errors = frontend_page
    payload = '<img src=x onerror="window.__xss=1"> Sunucu hatası'
    page.set_content(
        """
        <input id="menuUrlInput">
        <select id="menuTarget"><option value="kendim">Kendim</option></select>
        <div id="menuScanResult"></div>
        """
    )
    page.add_script_tag(path=FRONTEND / "modules" / "api-client.js")
    page.add_script_tag(path=FRONTEND / "modules" / "menu-scanner.js")
    page.evaluate(
        """
        payload => {
            window.__xss = 0;
            window.getUser = () => ({});
            window.safeFetchJson = async () => ({
                res: { ok: false },
                data: { detail: payload },
            });
        }
        """,
        payload,
    )
    page.fill("#menuUrlInput", "https://example.com/menu")
    page.evaluate("window.MenuScanner.scanMenu()")
    page.wait_for_function(
        "document.querySelector('#menuScanResult').textContent.includes('Sunucu hatası')"
    )

    result = page.locator("#menuScanResult")
    assert result.locator("img, svg, script, [onerror], [onload]").count() == 0
    assert payload in (result.text_content() or "")
    assert page.evaluate("window.__xss") == 0
    assert not runtime_errors
