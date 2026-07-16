from unittest.mock import patch

from src.graph import kural_kontrolü, MAX_DENEME
from src.grocery.health import assess_item_health
from src.quality.rule_engine import RuleEngine


def test_guardrail_guvenli_yemek_onaylanir():
    sonuc = kural_kontrolü({"guvenli_mi": True, "deneme_sayisi": 1})
    assert sonuc == "onaylandi"


def test_guardrail_guvenli_degil_tekrar_dener():
    sonuc = kural_kontrolü({"guvenli_mi": False, "deneme_sayisi": 1})
    assert sonuc == "reddedildi"


def test_guardrail_limit_asildiginda_dongu_kirilir():
    sonuc = kural_kontrolü({"guvenli_mi": False, "deneme_sayisi": MAX_DENEME})
    assert sonuc == "limit_asildi"


def test_food_word_boundaries_prevent_bal_balik_false_positive():
    assessment = assess_item_health(
        "Ton balığı",
        allergies=[],
        diseases=["diyabet"],
        medications=[],
    )

    assert assessment.status == "safe"


def test_gout_red_meat_is_not_treated_as_absolute_allergy_block():
    result = RuleEngine().check_rules(
        {"alerjiler": [], "hastaliklar": ["gut"]},
        "Az porsiyon kırmızı et",
        ["kırmızı et"],
    )

    assert result["found_risks"] == []
