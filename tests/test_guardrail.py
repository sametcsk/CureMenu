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


def test_registered_milk_protein_allergy_matches_milk_wording():
    result = RuleEngine().check_rules(
        {"alerjiler": ["İnek sütü proteini"], "hastaliklar": []},
        "Sütlü muzlu içecek",
        ["Sütlü muzlu içecek"],
    )

    assert result["found_risks"] == ["Alerji riski (Kesin İhlal): İnek sütü proteini"]


def test_food_warning_is_not_mistaken_for_food_recommendation():
    result = RuleEngine().check_rules(
        {"alerjiler": [], "hastaliklar": ["gut"]},
        "Gut hastalığında yüksek pürinli sakatat riski vardır; sakatat önerilmez.",
        ["Gut hastalığında yüksek pürinli sakatat riski vardır; sakatat önerilmez."],
    )

    assert result["found_risks"] == []


def test_kidney_disease_context_is_not_mistaken_for_organ_meat():
    result = RuleEngine().check_rules(
        {"alerjiler": [], "hastaliklar": ["gut", "evre 3 kronik böbrek hastalığı"]},
        "Böbrek hastalığında öneri güncel tahlillerle değerlendirilmelidir.",
        ["Böbrek hastalığında öneri güncel tahlillerle değerlendirilmelidir."],
    )

    assert result["found_risks"] == []


def test_kidney_meat_is_still_detected_for_gout():
    result = RuleEngine().check_rules(
        {"alerjiler": [], "hastaliklar": ["gut"]},
        "Izgara kuzu böbrek",
        ["kuzu böbrek"],
    )

    assert result["found_risks"] == []
    assert result["found_warnings"] == [
        "Gut kaydı nedeniyle sakatat ve yüksek pürin yükü dikkat gerektirir."
    ]


def test_plant_milk_is_not_mistaken_for_cow_milk_protein():
    result = RuleEngine().check_rules(
        {"alerjiler": ["İnek sütü proteini"], "hastaliklar": []},
        "Badem sütlü chia pudingi",
        ["Badem sütlü chia pudingi"],
    )

    assert result["found_risks"] == []


def test_egg_free_wording_is_not_mistaken_for_egg_ingredient():
    result = RuleEngine().check_rules(
        {"alerjiler": ["yumurta"], "hastaliklar": []},
        "Yumurtasız sebzeli mücver",
        ["Yumurtasız sebzeli mücver"],
    )

    assert result["found_risks"] == []


def test_coordinated_allergen_absence_applies_to_the_whole_list():
    result = RuleEngine().check_rules(
        {
            "alerjiler": ["İnek sütü proteini", "yumurta", "yer fıstığı"],
            "hastaliklar": [],
        },
        "Süt, yumurta ve yer fıstığı içermeyen karabuğday kasesi",
        ["Süt, yumurta ve yer fıstığı kullanılmadan hazırlanır."],
    )

    assert result["found_risks"] == []


def test_positive_ingredient_claim_is_not_hidden_by_later_absence_claim():
    result = RuleEngine().check_rules(
        {
            "alerjiler": ["İnek sütü proteini", "yumurta", "yer fıstığı"],
            "hastaliklar": [],
        },
        "Süt ve yumurta içerir, yer fıstığı içermez.",
        ["Süt ve yumurta içerir, yer fıstığı içermez."],
    )

    assert result["found_risks"] == [
        "Alerji riski (Kesin İhlal): İnek sütü proteini",
        "Alerji riski (Kesin İhlal): yumurta",
    ]


def test_almond_milk_and_gluten_free_oats_are_not_false_allergen_matches():
    result = RuleEngine().check_rules(
        {
            "alerjiler": ["İnek sütü proteini", "yumurta", "yer fıstığı"],
            "hastaliklar": ["çölyak"],
        },
        "Badem sütü, glutensiz yulaf, muz ve bitkisel proteinli smoothie",
        ["Badem sütü ve glutensiz yulaf kullanılır."],
    )

    assert result["found_risks"] == []
