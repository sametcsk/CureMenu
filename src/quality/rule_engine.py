import re
import unicodedata
from typing import Any, Dict, List

from src.quality.ingredient_catalog import IngredientCatalog, IngredientMatch
from src.rules.registry import load_food_constraint_registry


def _normalize(value: str) -> str:
    folded = unicodedata.normalize("NFKD", str(value or "").casefold())
    without_marks = "".join(char for char in folded if not unicodedata.combining(char))
    return without_marks.translate(str.maketrans({"ı": "i"}))


_NON_INGREDIENT_SUFFIX = re.compile(
    r"^\s*(?:urunu\s+)?(?:"
    r"icermez|icermeyen|bulunmaz|yok(?:tur)?|kullanilmadan|yerine|alerjisi?|"
    r"riski|risklidir|riskli(?:dir)?|onerilmez|onermiyorum|onermeyin|"
    r"tuketmeyin|tuketilmemeli|kacinin|uzak\s+durun|uygun\s+degil|sız|siz|suz|süz"
    r")"
)

_SHARED_ABSENCE_CLAIM = re.compile(
    r"\b(?:icermez|icermeyen|bulunmaz|yok(?:tur)?|kullanilmadan|eklenmeden)\b"
)
_POSITIVE_INGREDIENT_CLAIM = re.compile(
    r"\b(?:icerir|iceren|bulunur|kullanilir|eklenir)\b"
)


def _belongs_to_shared_absence_list(after_match: str) -> bool:
    """Handle lists such as 'sut, yumurta ve fistik icermeyen' safely."""
    clause = re.split(r"[.;:!?\n]", after_match, maxsplit=1)[0][:160]
    absence = _SHARED_ABSENCE_CLAIM.search(clause)
    if not absence:
        return False
    return _POSITIVE_INGREDIENT_CLAIM.search(clause[:absence.start()]) is None


def contains_positive_food_mention(
    text: str,
    term: str,
    *,
    safe_prefixes: tuple[str, ...] = (),
) -> bool:
    """Return true for ingredient use, not warnings or explicit absence."""
    value = _normalize(text)
    needle = _normalize(term).strip()
    if not needle:
        return False

    pattern = re.compile(
        rf"(?<![a-z0-9]){re.escape(needle)}(?:i|u|li|lu|lik|luk)?(?![a-z0-9])"
    )
    for match in pattern.finditer(value):
        before = value[max(0, match.start() - 40):match.start()]
        if re.search(r"(?:^|\s)\S*(?:sız|siz|suz|süz)\s*$", before):
            continue
        if any(before.rstrip().endswith(f"{_normalize(prefix)} ".rstrip()) for prefix in safe_prefixes):
            continue
        after = value[match.end():match.end() + 60]
        if not _NON_INGREDIENT_SUFFIX.match(after):
            if not _belongs_to_shared_absence_list(value[match.end():]):
                return True
    return False


def _contains_profile_alias(value: str, aliases: list[str]) -> bool:
    normalized = _normalize(value)
    return any(
        re.search(rf"(?<![a-z0-9]){re.escape(_normalize(alias))}(?![a-z0-9])", normalized)
        for alias in aliases
        if _normalize(alias)
    )


def _group_matches(texts: list[str], group: dict[str, list[str]]) -> bool:
    safe_prefixes = tuple(group.get("allowed_prefixes") or [])
    return any(
        contains_positive_food_mention(text, alias, safe_prefixes=safe_prefixes)
        for text in texts
        for alias in group.get("aliases") or []
    )


def _catalog_condition_matches(
    ingredient: dict[str, Any],
    conditions: list[dict[str, Any]],
) -> bool:
    if not conditions:
        return False

    for condition in conditions:
        actual = ingredient.get(condition["field"])
        expected = condition["value"]
        if condition["operator"] == "contains":
            if not isinstance(actual, list) or expected not in actual:
                return False
        elif actual != expected:
            return False
    return True


def _positive_catalog_matches(
    catalog: IngredientCatalog,
    texts: list[str],
) -> list[IngredientMatch]:
    matches: list[IngredientMatch] = []
    for text in texts:
        for match in catalog.resolve_all(text):
            if contains_positive_food_mention(text, match.matched_alias):
                matches.append(match)
    return matches


class RuleEngine:
    """Apply deterministic, data-driven profile constraints to food content."""

    def check_rules(
        self,
        profile: Dict[str, Any],
        meal: str,
        ingredients: List[str],
        *,
        structured_ingredients: bool = False,
    ) -> Dict[str, Any]:
        found_risks: list[str] = []
        found_warnings: list[str] = []
        matched_rules: list[str] = []
        risk_score = 0.0
        texts = [meal or "", *(ingredients or [])]

        registry = load_food_constraint_registry()
        catalog = IngredientCatalog()
        catalog_matches = _positive_catalog_matches(catalog, texts)
        groups = registry["ingredient_groups"]
        configured_allergies: set[str] = set()

        for rule in registry["profile_rules"]:
            matching_profiles = [
                str(value)
                for value in profile.get(rule["profile_field"], [])
                if _contains_profile_alias(str(value), rule["profile_aliases"])
            ]
            if not matching_profiles:
                continue
            if rule["profile_field"] == "alerjiler":
                configured_allergies.update(matching_profiles)
            ingredient_group = rule.get("ingredient_group")
            triggered = bool(rule.get("always_review"))
            catalog_conditions = rule.get("catalog_conditions") or []
            if not triggered and catalog_conditions:
                triggered = any(
                    _catalog_condition_matches(match.ingredient, catalog_conditions)
                    for match in catalog_matches
                )
            if not triggered and ingredient_group:
                triggered = _group_matches(texts, groups[ingredient_group])
            if not triggered:
                continue

            message = rule["message"].format(profile=matching_profiles[0])
            matched_rules.append(rule["rule_id"])
            if rule["outcome"] == "block":
                found_risks.append(message)
                risk_score = 1.0
            else:
                found_warnings.append(message)
                risk_score = max(risk_score, 0.4)

        for allergy in profile.get("alerjiler", []):
            allergy_text = str(allergy).strip()
            if not allergy_text or allergy_text in configured_allergies:
                continue
            if any(contains_positive_food_mention(text, allergy_text) for text in texts):
                found_risks.append(f"Alerji riski (Kesin İhlal): {allergy_text}")
                risk_score = 1.0

        unknown_ingredients: list[str] = []
        if structured_ingredients:
            for ingredient in ingredients or []:
                ingredient_text = str(ingredient).strip()
                if not ingredient_text:
                    continue
                if _positive_catalog_matches(catalog, [ingredient_text]):
                    continue
                unknown_ingredients.append(ingredient_text)
                found_warnings.append(
                    registry["unknown_ingredient_message"].format(
                        ingredient=ingredient_text
                    )
                )
                risk_score = max(risk_score, 0.2)

        return {
            "found_risks": list(dict.fromkeys(found_risks)),
            "found_warnings": list(dict.fromkeys(found_warnings)),
            "medical_risk_score": risk_score,
            "matched_rules": list(dict.fromkeys(matched_rules)),
            "registry_version": registry["version"],
            "catalog_version": catalog.version,
            "catalog_matches": list(
                dict.fromkeys(match.canonical_name for match in catalog_matches)
            ),
            "unknown_ingredients": list(dict.fromkeys(unknown_ingredients)),
        }
