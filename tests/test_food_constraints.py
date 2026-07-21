import pytest

from src.medical_knowledge.safety_checker import check_medication_food_safety
from src.grocery.health import assess_item_health
from src.quality.ingredient_catalog import IngredientCatalog
from src.quality.rule_engine import RuleEngine
from src.rules.registry import load_food_constraint_registry, load_ingredient_catalog


def _check(
    *,
    allergies=None,
    diseases=None,
    meal="",
    ingredients=None,
    structured_ingredients=False,
):
    return RuleEngine().check_rules(
        {
            "alerjiler": allergies or [],
            "hastaliklar": diseases or [],
        },
        meal,
        ingredients if ingredients is not None else [meal],
        structured_ingredients=structured_ingredients,
    )


def test_food_constraint_registry_is_versioned_and_data_driven():
    registry = load_food_constraint_registry()

    assert registry["version"] == "food_constraints:v1"
    assert {"cow_milk", "egg", "peanut", "gluten", "offal"}.issubset(
        registry["ingredient_groups"]
    )
    assert all(rule["outcome"] in {"block", "caution"} for rule in registry["profile_rules"])


def test_ingredient_catalog_is_small_versioned_and_schema_complete():
    catalog = load_ingredient_catalog()
    required_fields = {
        "canonical_name",
        "aliases",
        "tags",
        "allergens",
        "gluten_status",
        "milk_product",
        "purine_level",
        "vitamin_k_level",
        "ckd_caution_tags",
    }

    assert catalog["version"] == "ingredient_catalog:v1"
    assert 50 <= len(catalog["ingredients"]) <= 100
    assert all(required_fields.issubset(ingredient) for ingredient in catalog["ingredients"])


def test_catalog_distinguishes_plant_milk_from_dairy():
    catalog = IngredientCatalog()

    almond_milk = catalog.resolve("badem sütü")
    yogurt = catalog.resolve("yoğurt")

    assert almond_milk is not None
    assert almond_milk.canonical_name == "badem sütü"
    assert almond_milk.ingredient["milk_product"] is False
    assert yogurt is not None
    assert yogurt.ingredient["milk_product"] is True


def test_catalog_distinguishes_gluten_free_and_regular_bread():
    catalog = IngredientCatalog()

    gluten_free = catalog.resolve("glutensiz ekmek")
    regular = catalog.resolve("normal ekmek")

    assert gluten_free is not None
    assert gluten_free.ingredient["gluten_status"] == "free"
    assert regular is not None
    assert regular.ingredient["gluten_status"] == "contains"


@pytest.mark.parametrize("ingredient", ["süt", "yoğurt", "peynir"])
def test_cow_milk_allergy_blocks_real_dairy(ingredient):
    result = _check(allergies=["İnek sütü proteini"], meal=ingredient)

    assert result["found_risks"]
    assert "allergy-cow-milk:v1" in result["matched_rules"]


@pytest.mark.parametrize("allergy", ["İnek sütü proteini", "süt"])
def test_cow_milk_allergy_allows_almond_milk(allergy):
    result = _check(allergies=[allergy], meal="Badem sütü ile chia pudingi")

    assert result["found_risks"] == []


def test_egg_allergy_blocks_egg():
    result = _check(allergies=["yumurta"], ingredients=["yumurta", "domates"])

    assert result["found_risks"]


def test_egg_allergy_allows_egg_free_recipe():
    result = _check(allergies=["yumurta"], meal="Yumurtasız sebzeli mücver")

    assert result["found_risks"] == []


def test_celiac_blocks_regular_bread():
    result = _check(diseases=["çölyak"], ingredients=["normal ekmek"])

    assert result["found_risks"]
    assert "disease-celiac-gluten:v1" in result["matched_rules"]


def test_celiac_allows_gluten_free_bread():
    result = _check(diseases=["çölyak"], ingredients=["glutensiz ekmek"])

    assert result["found_risks"] == []


def test_peanut_allergy_blocks_peanut():
    result = _check(allergies=["yer fıstığı"], ingredients=["yer fıstığı ezmesi"])

    assert result["found_risks"]


def test_kidney_disease_does_not_create_offal_warning():
    result = _check(
        diseases=["evre 3 kronik böbrek hastalığı"],
        meal="Sebzeli karabuğday kasesi",
    )

    assert result["found_risks"] == []
    assert result["found_warnings"]
    assert all("sakatat" not in warning.casefold() for warning in result["found_warnings"])


def test_gout_offal_is_caution_not_absolute_block():
    result = _check(diseases=["gut"], ingredients=["kuzu böbrek"])

    assert result["found_risks"] == []
    assert result["found_warnings"]


def test_unknown_structured_product_is_marked_uncertain_not_safe():
    result = _check(
        meal="Protein bar",
        ingredients=["protein bar"],
        structured_ingredients=True,
    )

    assert result["found_risks"] == []
    assert result["unknown_ingredients"] == ["protein bar"]
    assert any(
        "katalogda doğrulanamayan" in warning
        for warning in result["found_warnings"]
    )


def test_warfarin_vitamin_k_guidance_emphasizes_consistency_not_ban():
    result = check_medication_food_safety(["Warfarin"], "Ispanak yemeği")
    explanation = " ".join(rule["explanation"] for rule in result["matched_rules"])

    assert result["severity"] == "caution"
    assert "tamamen kesmek yerine" in explanation
    assert "düzenli ve tutarlı" in explanation


def test_levothyroxine_food_timing_is_caution_not_block():
    result = check_medication_food_safety(["Levotiroksin"], "Yoğurt ve yulaf")

    assert result["severity"] == "caution"
    assert result["matched_rules"]


def test_allergy_block_takes_priority_over_medication_caution():
    result = assess_item_health(
        "Yoğurt",
        allergies=["İnek sütü proteini"],
        diseases=[],
        medications=["Levotiroksin"],
    )

    assert result.status == "avoid"
    assert "Alerji" in result.reason
