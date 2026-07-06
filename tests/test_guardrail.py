from unittest.mock import patch

from src.graph import kural_kontrolü, MAX_DENEME


def test_guardrail_guvenli_yemek_onaylanir():
    sonuc = kural_kontrolü({"guvenli_mi": True, "deneme_sayisi": 1})
    assert sonuc == "onaylandi"


def test_guardrail_guvenli_degil_tekrar_dener():
    sonuc = kural_kontrolü({"guvenli_mi": False, "deneme_sayisi": 1})
    assert sonuc == "reddedildi"


def test_guardrail_limit_asildiginda_dongu_kirilir():
    sonuc = kural_kontrolü({"guvenli_mi": False, "deneme_sayisi": MAX_DENEME})
    assert sonuc == "limit_asildi"
