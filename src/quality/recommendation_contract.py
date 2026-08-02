from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from pydantic import BaseModel


@dataclass(frozen=True)
class RecommendationSafetyInput:
    display_text: str
    ingredients: tuple[str, ...]
    has_structured_ingredients: bool


def _mapping(value: Any) -> Mapping[str, Any] | None:
    if isinstance(value, BaseModel):
        return value.model_dump()
    if isinstance(value, Mapping):
        return value
    return None


def _clean_text(value: Any) -> str:
    return str(value or "").strip()


def _ingredient_list(value: Any) -> list[str]:
    if not isinstance(value, (list, tuple)):
        return []
    return [text for item in value if (text := _clean_text(item))]


def _meal_parts(value: Any) -> tuple[str, list[str], bool]:
    meal = _mapping(value)
    if meal is None:
        return _clean_text(value), [], False
    name = _clean_text(meal.get("name") or meal.get("recommendation"))
    ingredients = _ingredient_list(meal.get("ingredients"))
    return name, ingredients, bool(name and ingredients)


def extract_recommendation_safety_input(output: Any) -> RecommendationSafetyInput:
    payload = _mapping(output)
    if payload is None:
        return RecommendationSafetyInput(_clean_text(output), (), False)

    days = payload.get("days")
    if isinstance(days, list):
        display_parts: list[str] = []
        ingredients: list[str] = []
        expected_meals = 0
        structured_meals = 0

        for raw_day in days:
            day = _mapping(raw_day)
            if day is None:
                continue
            details = _mapping(day.get("meal_details")) or {}
            for key in ("breakfast", "lunch", "dinner"):
                display = _clean_text(day.get(key))
                if display:
                    display_parts.append(display)
                    expected_meals += 1
                detail_text, detail_ingredients, complete = _meal_parts(details.get(key))
                if detail_text:
                    display_parts.append(detail_text)
                ingredients.extend(detail_ingredients)
                if display and complete:
                    structured_meals += 1

            snack_texts = [_clean_text(item) for item in day.get("snacks", []) if _clean_text(item)]
            display_parts.extend(snack_texts)
            expected_meals += len(snack_texts)
            snack_details = day.get("snack_details")
            if isinstance(snack_details, list):
                for detail in snack_details:
                    detail_text, detail_ingredients, complete = _meal_parts(detail)
                    if detail_text:
                        display_parts.append(detail_text)
                    ingredients.extend(detail_ingredients)
                    if complete:
                        structured_meals += 1

        fully_structured = expected_meals > 0 and structured_meals == expected_meals
        return RecommendationSafetyInput(
            "\n".join(part for part in display_parts if part),
            tuple(ingredients),
            fully_structured,
        )

    replacements = payload.get("degisen_ogunler")
    if isinstance(replacements, list):
        names: list[str] = []
        ingredients: list[str] = []
        complete = bool(replacements)
        for raw_item in replacements:
            item = _mapping(raw_item)
            if item is None:
                complete = False
                continue
            name = _clean_text(item.get("yeni"))
            item_ingredients = _ingredient_list(item.get("ingredients"))
            if name:
                names.append(name)
            ingredients.extend(item_ingredients)
            complete = complete and bool(name and item_ingredients)
        return RecommendationSafetyInput("\n".join(names), tuple(ingredients), complete)

    snacks = payload.get("snacks")
    if isinstance(snacks, list):
        names: list[str] = []
        ingredients: list[str] = []
        complete = bool(snacks)
        for raw_snack in snacks:
            name, snack_ingredients, item_complete = _meal_parts(raw_snack)
            if name:
                names.append(name)
            ingredients.extend(snack_ingredients)
            complete = complete and item_complete
        return RecommendationSafetyInput("\n".join(names), tuple(ingredients), complete)

    if isinstance(payload.get("ingredients"), list):
        name, ingredients, complete = _meal_parts(payload)
        return RecommendationSafetyInput(name, tuple(ingredients), complete)

    if "snack_onerileri" in payload:
        return RecommendationSafetyInput(_clean_text(payload.get("snack_onerileri")), (), False)

    return RecommendationSafetyInput(_clean_text(output), (), False)
