from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
FRONTEND = ROOT / "frontend"
DOMPURIFY_URL = "https://cdn.jsdelivr.net/npm/dompurify@3.4.12/dist/purify.min.js"


def test_all_dompurify_pages_use_the_same_patched_version():
    pages = ["dashboard.html", "guven.html", "index.html", "kayit.html"]
    for page in pages:
        source = (FRONTEND / page).read_text(encoding="utf-8")
        assert DOMPURIFY_URL in source
        assert "dompurify/3.0.6" not in source


def test_dynamic_error_messages_are_not_interpolated_into_html_sinks():
    modules = [
        "governance-dashboard.js",
        "lab-upload.js",
        "menu-scanner.js",
        "smart-grocery.js",
    ]
    for module in modules:
        source = (FRONTEND / "modules" / module).read_text(encoding="utf-8")
        dynamic_html_lines = [
            line
            for line in source.splitlines()
            if "innerHTML" in line or "insertAdjacentHTML" in line
        ]
        assert all("apiHataMesaji(" not in line for line in dynamic_html_lines)
        assert all("baglantiHatasi(" not in line for line in dynamic_html_lines)


def test_registration_summary_does_not_use_an_html_sink():
    source = (FRONTEND / "kayit.html").read_text(encoding="utf-8")
    render_summary = source.split("function renderSummary()", 1)[1].split(
        "nextBtn.addEventListener", 1
    )[0]
    assert "innerHTML" not in render_summary
    assert "textContent" in render_summary
    assert "replaceChildren" in render_summary
