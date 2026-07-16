import base64
import socket

import cv2
import numpy as np
import pytest

from src.scanner import (
    MAX_IMAGE_BYTES,
    MAX_URL_RESPONSE_BYTES,
    _validate_base64_image,
    _validate_public_url,
    scrape_menu_from_url,
)


@pytest.mark.parametrize(
    "url",
    [
        "http://127.0.0.1/menu",
        "http://localhost/menu",
        "http://169.254.169.254/latest/meta-data",
        "http://10.0.0.8/menu",
        "http://[::1]/menu",
        "file:///etc/passwd",
    ],
)
def test_validate_public_url_private_hedefleri_reddeder(url):
    with pytest.raises(ValueError):
        _validate_public_url(url)


def test_validate_public_url_userinfo_ve_supheli_portu_reddeder():
    with pytest.raises(ValueError, match="Kullanıcı bilgisi"):
        _validate_public_url("https://user:pass@example.com/menu")
    with pytest.raises(ValueError, match="standart web portlarına"):
        _validate_public_url("https://example.com:8080/menu")


class FakeResponse:
    def __init__(self, chunks=(), *, status_code=200, headers=None, encoding="utf-8"):
        self._chunks = list(chunks)
        self.status_code = status_code
        self.headers = headers or {}
        self.encoding = encoding
        self.raw = None
        self.closed = False

    @property
    def is_redirect(self):
        return self.status_code in {301, 302, 303, 307, 308}

    @property
    def content(self):
        raise AssertionError("Streaming güvenlik sınırı response.content kullanmamalı")

    def iter_content(self, chunk_size):
        yield from self._chunks

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError("HTTP error")

    def close(self):
        self.closed = True


def _public_dns(monkeypatch):
    monkeypatch.setattr(
        socket,
        "getaddrinfo",
        lambda host, port, type=0: [
            (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", 0))
        ],
    )


def test_scrape_menu_private_ip_redirectini_reddeder(monkeypatch):
    _public_dns(monkeypatch)
    response = FakeResponse(status_code=302, headers={"Location": "http://127.0.0.1/admin"})
    monkeypatch.setattr("src.scanner.requests.get", lambda *args, **kwargs: response)

    with pytest.raises(Exception, match="iç ağ"):
        scrape_menu_from_url("https://example.test/menu")
    assert response.closed is True


def test_scrape_menu_buyuk_chunked_responseu_stream_sirasinda_keser(monkeypatch):
    _public_dns(monkeypatch)
    chunks = [b"x" * (64 * 1024)] * ((MAX_URL_RESPONSE_BYTES // (64 * 1024)) + 2)
    response = FakeResponse(chunks)
    monkeypatch.setattr("src.scanner.requests.get", lambda *args, **kwargs: response)

    with pytest.raises(Exception, match="çok büyük"):
        scrape_menu_from_url("https://example.test/menu")
    assert response.closed is True


def test_scrape_menu_guvenli_https_akisi_calisir(monkeypatch):
    _public_dns(monkeypatch)
    response = FakeResponse([b"<html><body>Mercimek corbasi ve sebze yemegi</body></html>"])
    monkeypatch.setattr("src.scanner.requests.get", lambda *args, **kwargs: response)

    result = scrape_menu_from_url("https://example.test/menu")

    assert "Mercimek corbasi" in result
    assert response.closed is True


def _encoded_image(extension: str) -> str:
    image = np.zeros((8, 8, 3), dtype=np.uint8)
    ok, encoded = cv2.imencode(extension, image)
    assert ok
    return base64.b64encode(encoded.tobytes()).decode("ascii")


@pytest.mark.parametrize("extension,mime", [(".png", "image/png"), (".jpg", "image/jpeg")])
def test_validate_base64_image_gecerli_kucuk_gorseli_kabul_eder(extension, mime):
    payload = _encoded_image(extension)

    normalized, detected_mime = _validate_base64_image(f"data:{mime};base64,{payload}")

    assert detected_mime == mime
    assert base64.b64decode(normalized)


def test_validate_base64_image_gecersiz_base64_ve_sahte_mime_reddeder():
    with pytest.raises(ValueError, match="base64"):
        _validate_base64_image("data:image/png;base64,%%%not-base64%%")

    fake_image = base64.b64encode(b"this is text, not an image").decode("ascii")
    with pytest.raises(ValueError, match="JPEG, PNG veya WebP"):
        _validate_base64_image(f"data:image/jpeg;base64,{fake_image}")


def test_validate_base64_image_decoded_byte_limitini_uygular():
    oversized = b"\xff\xd8\xff" + (b"x" * MAX_IMAGE_BYTES)
    payload = base64.b64encode(oversized).decode("ascii")

    with pytest.raises(ValueError, match="çok büyük"):
        _validate_base64_image(payload)


def test_validate_base64_image_asiri_piksel_boyutunu_decode_oncesi_reddeder():
    fake_png = (
        b"\x89PNG\r\n\x1a\n"
        + b"\x00\x00\x00\x0dIHDR"
        + (5000).to_bytes(4, "big")
        + (5000).to_bytes(4, "big")
        + b"\x08\x02\x00\x00\x00"
    )
    payload = base64.b64encode(fake_png).decode("ascii")

    with pytest.raises(ValueError, match="piksel boyutu"):
        _validate_base64_image(payload)
