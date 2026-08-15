from src.models import StructuredMealRecommendation, WeeklyPlan, WeeklyPlanDay
from src.quality.recommendation_contract import extract_recommendation_safety_input


def test_single_structured_meal_uses_explicit_ingredients():
    meal = StructuredMealRecommendation(
        name="Badem sütlü yulaf",
        ingredients=["badem sütü", "glutensiz yulaf"],
    )

    result = extract_recommendation_safety_input(meal)

    assert result.display_text == "Badem sütlü yulaf"
    assert result.ingredients == ("badem sütü", "glutensiz yulaf")
    assert result.has_structured_ingredients is True


def test_plain_text_keeps_conservative_fallback():
    result = extract_recommendation_safety_input("Yoğurtlu bir tarif")

    assert result.display_text == "Yoğurtlu bir tarif"
    assert result.ingredients == ()
    assert result.has_structured_ingredients is False


def test_alternative_requires_ingredients_for_every_replacement():
    result = extract_recommendation_safety_input(
        {
            "degisen_ogunler": [
                {"eski": "Yemek A", "yeni": "Yemek B", "ingredients": ["nohut"]},
                {"eski": "Yemek C", "yeni": "Yemek D"},
            ]
        }
    )

    assert result.has_structured_ingredients is False
    assert result.ingredients == ("nohut",)


def test_weekly_plan_is_structured_when_every_displayed_meal_has_details():
    plan = WeeklyPlan(
        days=[
            WeeklyPlanDay(
                day="Pazartesi",
                breakfast="Yulaf kasesi",
                lunch="Nohut salatası",
                dinner="Sebzeli tavuk",
                snacks=["Meyve kasesi"],
                meal_details={
                    "breakfast": {"name": "Yulaf kasesi", "ingredients": ["glutensiz yulaf"]},
                    "lunch": {"name": "Nohut salatası", "ingredients": ["nohut", "marul"]},
                    "dinner": {"name": "Sebzeli tavuk", "ingredients": ["tavuk", "brokoli"]},
                },
                snack_details=[{"name": "Meyve kasesi", "ingredients": ["elma"]}],
            )
        ],
        summary="Özet",
    )

    result = extract_recommendation_safety_input(plan)

    assert result.has_structured_ingredients is True
    assert "glutensiz yulaf" in result.ingredients
    assert "elma" in result.ingredients


def test_weekly_plan_missing_one_detail_falls_back_to_text_validation():
    plan = WeeklyPlan(
        days=[
            WeeklyPlanDay(
                day="Pazartesi",
                breakfast="Yulaf kasesi",
                lunch="Nohut salatası",
                dinner="Yoğurtlu makarna",
                meal_details={
                    "breakfast": {"name": "Yulaf kasesi", "ingredients": ["glutensiz yulaf"]},
                    "lunch": {"name": "Nohut salatası", "ingredients": ["nohut", "marul"]},
                },
            )
        ],
        summary="Özet",
    )

    result = extract_recommendation_safety_input(plan)

    assert result.has_structured_ingredients is False
    assert "Yoğurtlu makarna" in result.display_text


def test_weekly_plan_ingredients_strip_quantity_unit_descriptors_and_dedupe():
    plan = WeeklyPlan(
        days=[
            WeeklyPlanDay(
                day="Pazartesi",
                breakfast="Yulaf kasesi",
                lunch="Tavuklu salata",
                dinner="Fıstıklı sebze tabağı",
                meal_details={
                    "breakfast": {
                        "name": "Yulaf kasesi",
                        "ingredients": ["1 su bardağı glutensiz yulaf", "glutensiz yulaf"],
                    },
                    "lunch": {
                        "name": "Tavuklu salata",
                        "ingredients": ["200 g derisiz tavuk göğsü, küp doğranmış", "tavuk göğsü"],
                    },
                    "dinner": {
                        "name": "Fıstıklı sebze tabağı",
                        "ingredients": ["2 yemek kaşığı yer fıstığı", "yer fıstığı", "1 adet orta boy havuç, rendelenmiş"],
                    },
                },
            )
        ],
        summary="Özet",
    )

    result = extract_recommendation_safety_input(plan)

    assert result.ingredients == (
        "glutensiz yulaf",
        "tavuk",
        "yer fıstığı",
        "havuç",
    )
    assert result.has_structured_ingredients is True
    assert result.raw_ingredients[0] == "1 su bardağı glutensiz yulaf"
    assert result.ingredient_records[0].quantity == "1"
    assert result.ingredient_records[0].unit == "su bardağı"
    assert result.ingredient_records[0].safety_descriptors == ("glutensiz",)
    assert result.ingredient_records[1].preparation_descriptors == ("derisiz", "küp doğranmış")
