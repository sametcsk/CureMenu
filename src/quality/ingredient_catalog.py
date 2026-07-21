import re
import unicodedata
from dataclasses import dataclass
from typing import Any

from src.rules.registry import load_ingredient_catalog


def normalize_catalog_text(value: str) -> str:
    folded = unicodedata.normalize("NFKD", str(value or "").casefold())
    without_marks = "".join(char for char in folded if not unicodedata.combining(char))
    return without_marks.translate(str.maketrans({"ı": "i"})).strip()


@dataclass(frozen=True)
class IngredientMatch:
    raw_value: str
    matched_alias: str
    ingredient: dict[str, Any]

    @property
    def canonical_name(self) -> str:
        return str(self.ingredient["canonical_name"])


class IngredientCatalog:
    """Resolve explicit ingredient wording to a small, versioned catalog."""

    def __init__(self) -> None:
        registry = load_ingredient_catalog()
        self.version = str(registry["version"])
        self.ingredients = list(registry["ingredients"])
        aliases: list[tuple[str, str, dict[str, Any]]] = []
        for ingredient in self.ingredients:
            for alias in [ingredient["canonical_name"], *ingredient["aliases"]]:
                normalized_alias = normalize_catalog_text(alias)
                if normalized_alias:
                    aliases.append((normalized_alias, str(alias), ingredient))
        self._aliases = sorted(aliases, key=lambda item: len(item[0]), reverse=True)

    def resolve_all(self, value: str) -> list[IngredientMatch]:
        normalized = normalize_catalog_text(value)
        if not normalized:
            return []

        candidates: list[tuple[int, int, str, dict[str, Any]]] = []
        for normalized_alias, display_alias, ingredient in self._aliases:
            pattern = re.compile(
                rf"(?<![a-z0-9]){re.escape(normalized_alias)}(?:i|u|li|lu|lik|luk)?(?![a-z0-9])"
            )
            for match in pattern.finditer(normalized):
                candidates.append((match.start(), match.end(), display_alias, ingredient))

        selected: list[tuple[int, int, str, dict[str, Any]]] = []
        for candidate in sorted(candidates, key=lambda item: (item[0], -(item[1] - item[0]))):
            start, end, _, _ = candidate
            if any(start < selected_end and end > selected_start for selected_start, selected_end, _, _ in selected):
                continue
            selected.append(candidate)

        return [
            IngredientMatch(raw_value=value, matched_alias=alias, ingredient=ingredient)
            for _, _, alias, ingredient in selected
        ]

    def resolve(self, value: str) -> IngredientMatch | None:
        matches = self.resolve_all(value)
        return matches[0] if matches else None
