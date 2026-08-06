from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urlparse


FRONTEND_DIR = Path(__file__).resolve().parents[1] / "frontend"


class ExternalAssetParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.assets: list[str] = []

    def handle_starttag(self, tag, attrs):
        values = dict(attrs)
        url = values.get("src") if tag == "script" else values.get("href") if tag == "link" else None
        if url and url.startswith("https://"):
            self.assets.append(url)


def _external_assets(filename: str) -> list[str]:
    parser = ExternalAssetParser()
    parser.feed((FRONTEND_DIR / filename).read_text(encoding="utf-8"))
    return parser.assets


EXPECTED_EXTERNAL_ASSETS = {
    "dashboard.html": [
        "https://cdn.tailwindcss.com/3.4.17?plugins=forms,container-queries,typography",
        "https://cdn.jsdelivr.net/npm/marked@12.0.2/marked.min.js",
        "https://cdn.jsdelivr.net/npm/dompurify@3.4.12/dist/purify.min.js",
        "https://cdn.jsdelivr.net/npm/chart.js@4.4.7/dist/chart.umd.min.js",
        "https://fonts.googleapis.com/css2?family=Material+Symbols+Outlined:wght,FILL@100..700,0..1&display=swap",
        "https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&family=Outfit:wght@600;700;800&display=swap",
    ],
    "giris.html": [
        "https://cdn.tailwindcss.com/3.4.17?plugins=forms,container-queries",
        "https://fonts.googleapis.com/css2?family=Material+Symbols+Outlined:wght,FILL@100..700,0..1&display=swap",
        "https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=Outfit:wght@600;700&display=swap",
    ],
    "guven.html": [
        "https://cdn.tailwindcss.com/3.4.17?plugins=forms,container-queries",
        "https://fonts.googleapis.com/css2?family=Material+Symbols+Outlined:wght,FILL@100..700,0..1&display=swap",
        "https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=Outfit:wght@500;600;700&display=swap",
        "https://cdn.jsdelivr.net/npm/marked@12.0.2/marked.min.js",
        "https://cdn.jsdelivr.net/npm/dompurify@3.4.12/dist/purify.min.js",
    ],
    "index.html": [
        "https://cdn.tailwindcss.com/3.4.17?plugins=forms,container-queries,typography",
        "https://fonts.googleapis.com/css2?family=Material+Symbols+Outlined:wght,FILL@100..700,0..1&display=swap",
        "https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=Outfit:wght@600;700&display=swap",
        "https://cdn.jsdelivr.net/npm/marked@12.0.2/marked.min.js",
        "https://cdn.jsdelivr.net/npm/dompurify@3.4.12/dist/purify.min.js",
    ],
    "kayit.html": [
        "https://cdn.tailwindcss.com/3.4.17?plugins=forms,container-queries",
        "https://fonts.googleapis.com/css2?family=Material+Symbols+Outlined:wght,FILL@100..700,0..1&display=swap",
        "https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=Outfit:wght@600;700&display=swap",
        "https://cdn.jsdelivr.net/npm/marked@12.0.2/marked.min.js",
        "https://cdn.jsdelivr.net/npm/dompurify@3.4.12/dist/purify.min.js",
    ],
}


def test_external_frontend_assets_are_known_and_version_pinned():
    for filename, expected in EXPECTED_EXTERNAL_ASSETS.items():
        actual = _external_assets(filename)
        if filename == "dashboard.html" and "https://unpkg.com/html5-qrcode@2.3.8/html5-qrcode.min.js" in actual:
            expected = [
                *expected[:3],
                "https://unpkg.com/html5-qrcode@2.3.8/html5-qrcode.min.js",
                *expected[3:],
            ]
        assert actual == expected


def test_dashboard_uses_local_pinned_qr_scanner():
    html = (FRONTEND_DIR / "dashboard.html").read_text(encoding="utf-8")
    vendor = FRONTEND_DIR / "vendor" / "html5-qrcode-2.3.8.min.js"

    if vendor.is_file():
        assert 'src="/static/vendor/html5-qrcode-2.3.8.min.js"' in html
        assert vendor.stat().st_size > 100_000
    else:
        assert "https://unpkg.com/html5-qrcode@2.3.8/html5-qrcode.min.js" in html


def test_non_google_cdn_assets_are_version_pinned():
    for filename in EXPECTED_EXTERNAL_ASSETS:
        for asset in _external_assets(filename):
            parsed = urlparse(asset)
            if parsed.netloc == "fonts.googleapis.com":
                continue
            if parsed.netloc == "cdn.tailwindcss.com":
                assert parsed.path.startswith("/3.4.17")
            elif parsed.netloc == "cdn.jsdelivr.net":
                assert "@" in parsed.path
            elif parsed.netloc == "unpkg.com":
                assert "@" in parsed.path
            else:
                raise AssertionError(f"Unexpected external asset host in {filename}: {asset}")
