import pytest

from src.scanner import _validate_public_url


@pytest.mark.parametrize(
    "url",
    [
        "http://127.0.0.1/menu",
        "http://localhost/menu",
        "file:///etc/passwd",
    ],
)
def test_validate_public_url_private_hedefleri_reddeder(url):
    with pytest.raises(ValueError):
        _validate_public_url(url)
