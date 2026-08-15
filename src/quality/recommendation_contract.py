from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Any, Mapping
import unicodedata

from pydantic import BaseModel

from src.quality.ingredient_catalog import IngredientCatalog


@dataclass(frozen=True)
class CanonicalIngredient:
    raw_text: str
    quantity: str
    unit: str
    preparation_descriptors: tuple[str, ...]
    safety_descriptors: tuple[str, ...]
    canonical_name: str
    catalog_resolved: bool
    identity_key: str

    def metadata(self) -> dict[str, Any]:
        return {
            "raw_text": self.raw_text,
            "quantity": self.quantity,
            "unit": self.unit,
            "preparation_descriptors": list(self.preparation_descriptors),
            "safety_descriptors": list(self.safety_descriptors),
            "canonical_name": self.canonical_name,
            "catalog_resolved": self.catalog_resolved,
            "identity_key": self.identity_key,
        }


@dataclass(frozen=True)
class RecommendationSafetyInput:
    display_text: str
    ingredients: tuple[str, ...]
    has_structured_ingredients: bool
    raw_ingredients: tuple[str, ...] = ()
    ingredient_records: tuple[CanonicalIngredient, ...] = ()


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


_WEEKLY_QUANTITY_PREFIX = re.compile(
    r"^\s*(?:yaklaşık\s+)?(?P<quantity>\d+(?:[.,]\d+)?|\d+\s*/\s*\d+|[¼½¾]|bir|yarım|çeyrek)\s*",
    re.IGNORECASE,
)
_WEEKLY_UNIT_PREFIX = re.compile(
    r"^(?P<unit>(?:su|çay)\s+bardağı|(?:yemek|çay|tatlı)\s+kaşığı|"
    r"adet|tane|dilim|kase|paket|avuç|tutam|gram|gr|g|kilogram|kg|"
    r"mililitre|ml|litre|lt|l)\b\s*(?:kadar\s*)?",
    re.IGNORECASE,
)
_WEEKLY_DESCRIPTOR_PREFIX = re.compile(
    r"^(?:orta\s+boy|küçük\s+boy|büyük\s+boy|ince\s+doğranmış|küp\s+doğranmış|"
    r"doğranmış|rendelenmiş|haşlanmış|pişmiş|yıkanmış|ayıklanmış|soyulmuş|"
    r"ezilmiş|dövülmüş|derisiz)\s+",
    re.IGNORECASE,
)
_WEEKLY_DESCRIPTOR_SUFFIX = re.compile(
    r"\s*(?:,\s*|\s+\()(?:ince\s+doğranmış|küp\s+doğranmış|doğranmış|rendelenmiş|"
    r"haşlanmış|pişmiş|yıkanmış|ayıklanmış|soyulmuş|ezilmiş|dövülmüş|"
    r"orta\s+boy|küçük\s+boy|büyük\s+boy)\)?\s*$",
    re.IGNORECASE,
)
_SAFETY_DESCRIPTOR = re.compile(
    r"(?<!\w)([A-Za-zÇĞİÖŞÜçğıöşü]+(?:sız|siz|suz|süz))(?!\w)",
    re.IGNORECASE,
)


def _ingredient_key(value: str) -> str:
    folded = unicodedata.normalize("NFKD", value.casefold().replace("ı", "i"))
    return "".join(char for char in folded if not unicodedata.combining(char))


def parse_canonical_ingredient(value: str, catalog: IngredientCatalog | None = None) -> CanonicalIngredient | None:
    raw_text = re.sub(r"\s+", " ", _clean_text(value)).strip(" -;,.")
    if not raw_text:
        return None
    text = raw_text
    quantity_match = _WEEKLY_QUANTITY_PREFIX.match(text)
    quantity = quantity_match.group("quantity") if quantity_match else ""
    if quantity_match:
        text = text[quantity_match.end():].strip()
    unit_match = _WEEKLY_UNIT_PREFIX.match(text)
    unit = unit_match.group("unit") if unit_match else ""
    if unit_match:
        text = text[unit_match.end():].strip()
    preparation_descriptors: list[str] = []
    while True:
        descriptor_match = _WEEKLY_DESCRIPTOR_PREFIX.match(text)
        if descriptor_match is None:
            break
        descriptor = descriptor_match.group(0).strip()
        if descriptor:
            preparation_descriptors.append(descriptor)
        text = text[descriptor_match.end():].strip()
    suffix_match = _WEEKLY_DESCRIPTOR_SUFFIX.search(text)
    if suffix_match:
        descriptor = suffix_match.group(0).strip(" ,()")
        if descriptor:
            preparation_descriptors.append(descriptor)
        text = text[:suffix_match.start()].strip()
    text = text.strip(" -;,.")
    if not text:
        return None

    safety_descriptors = tuple(dict.fromkeys(
        match.group(1).casefold() for match in _SAFETY_DESCRIPTOR.finditer(text)
    ))
    catalog = catalog or IngredientCatalog()
    catalog_match = catalog.resolve(text)
    canonical_name = catalog_match.canonical_name if catalog_match else text
    identity_key = _ingredient_key(canonical_name)
    if safety_descriptors:
        identity_key += "|" + "|".join(sorted(_ingredient_key(item) for item in safety_descriptors))
    return CanonicalIngredient(
        raw_text=raw_text,
        quantity=quantity,
        unit=unit,
        preparation_descriptors=tuple(preparation_descriptors),
        safety_descriptors=safety_descriptors,
        canonical_name=canonical_name,
        catalog_resolved=catalog_match is not None,
        identity_key=identity_key,
    )


def canonicalize_ingredient_records(values: list[str]) -> list[CanonicalIngredient]:
    result: list[CanonicalIngredient] = []
    seen: set[str] = set()
    catalog = IngredientCatalog()
    for value in values:
        record = parse_canonical_ingredient(value, catalog)
        if record is None or record.identity_key in seen:
            continue
        seen.add(record.identity_key)
        result.append(record)
    return result


def _structured_result(display_text: str, raw_ingredients: list[str], complete: bool) -> RecommendationSafetyInput:
    records = canonicalize_ingredient_records(raw_ingredients)
    return RecommendationSafetyInput(
        display_text,
        tuple(record.canonical_name for record in records),
        complete,
        tuple(raw_ingredients),
        tuple(records),
    )


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
        return _structured_result(
            "\n".join(part for part in display_parts if part),
            ingredients,
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
        return _structured_result("\n".join(names), ingredients, complete)

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
        return _structured_result("\n".join(names), ingredients, complete)

    if isinstance(payload.get("ingredients"), list):
        name, ingredients, complete = _meal_parts(payload)
        return _structured_result(name, ingredients, complete)

    if "snack_onerileri" in payload:
        return RecommendationSafetyInput(_clean_text(payload.get("snack_onerileri")), (), False)

    return RecommendationSafetyInput(_clean_text(output), (), False)
