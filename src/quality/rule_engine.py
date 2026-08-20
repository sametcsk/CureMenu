import re
import unicodedata
from typing import Any, Dict, List

from src.quality.ingredient_catalog import IngredientCatalog, IngredientMatch
from src.quality.evidence import SafetyFinding
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


def _group_evidence(texts: list[str], group: dict[str, list[str]]) -> list[tuple[str, str]]:
    safe_prefixes = tuple(group.get("allowed_prefixes") or [])
    evidence: list[tuple[str, str]] = []
    for text in texts:
        for alias in group.get("aliases") or []:
            if contains_positive_food_mention(text, alias, safe_prefixes=safe_prefixes):
                evidence.append((str(text).strip(), str(alias).strip()))
    return evidence


def _finding(
    *,
    restriction_type: str,
    restriction_identifier: str,
    evidence_level: str,
    evidence_source: str,
    explanation: str,
    matched_ingredient: str = "",
    matched_catalog_entry: str = "",
    input_span: str = "",
    confidence: float = 0.0,
) -> dict[str, Any]:
    return SafetyFinding(
        restriction_type=restriction_type,
        restriction_identifier=restriction_identifier,
        evidence_level=evidence_level,
        evidence_source=evidence_source,
        matched_ingredient=matched_ingredient,
        matched_catalog_entry=matched_catalog_entry,
        input_span=input_span,
        explanation=explanation,
        confidence=confidence,
        new_evidence_this_turn=bool(
            matched_ingredient
            and evidence_source not in {"", "legacy_or_unspecified", "profile_review_policy"}
        ),
    ).persisted()


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
        evidence_findings: list[dict[str, Any]] = []
        risk_score = 0.0
        texts = [meal or "", *(ingredients or [])]

        registry = load_food_constraint_registry()
        catalog = IngredientCatalog()
        catalog_matches = _positive_catalog_matches(catalog, texts)
        groups = registry["ingredient_groups"]
        configured_allergies: set[str] = set()

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

        for rule in registry["profile_rules"]:
            matching_profiles = [
                str(value)
                for value in profile.get(rule["profile_field"], [])
                if _contains_profile_alias(str(value), rule["profile_aliases"])
            ]
            if not matching_profiles:
                continue
            if rule["profile_field"] == "alerjiler":
                configured_allergies.update(_normalize(item) for item in matching_profiles)
            ingredient_group = rule.get("ingredient_group")
            catalog_conditions = rule.get("catalog_conditions") or []
            catalog_rule_matches = [
                match for match in catalog_matches
                if _catalog_condition_matches(match.ingredient, catalog_conditions)
            ] if catalog_conditions else []
            group_matches = _group_evidence(texts, groups[ingredient_group]) if ingredient_group else []
            triggered = bool(rule.get("always_review") or catalog_rule_matches or group_matches)
            if not triggered:
                evidence_level = "CLEAR" if structured_ingredients and not unknown_ingredients else "UNKNOWN"
                evidence_findings.extend(
                    _finding(
                        restriction_type="allergy" if rule["profile_field"] == "alerjiler" else "disease",
                        restriction_identifier=profile_value,
                        evidence_level=evidence_level,
                        evidence_source="structured_ingredients" if evidence_level == "CLEAR" else "missing_or_unverified_ingredients",
                        explanation=(
                            "Yapılandırılmış içerikte bu kısıtla eşleşme bulunmadı."
                            if evidence_level == "CLEAR"
                            else "İçerik verisi bu kısıt için kesin eşleşme kararı vermeye yeterli değil."
                        ),
                        confidence=0.9 if evidence_level == "CLEAR" else 0.25,
                    )
                    for profile_value in matching_profiles
                )
                continue

            message = rule["message"].format(profile=matching_profiles[0])
            matched_rules.append(rule["rule_id"])
            if catalog_rule_matches:
                matched_ingredient = catalog_rule_matches[0].canonical_name
                matched_catalog_entry = catalog_rule_matches[0].canonical_name
                input_span = catalog_rule_matches[0].matched_alias
                evidence_level = "CONFIRMED"
                evidence_source = "ingredient_catalog"
                confidence = 1.0
            elif group_matches:
                matched_ingredient = group_matches[0][1]
                matched_catalog_entry = ""
                input_span = group_matches[0][1]
                evidence_level = "CONFIRMED"
                evidence_source = "explicit_input"
                confidence = 0.95
            else:
                matched_ingredient = matched_catalog_entry = input_span = ""
                evidence_level = "UNKNOWN"
                evidence_source = "profile_review_policy"
                confidence = 0.25
            evidence_findings.extend(
                _finding(
                    restriction_type="allergy" if rule["profile_field"] == "alerjiler" else "disease",
                    restriction_identifier=profile_value,
                    evidence_level=evidence_level,
                    evidence_source=evidence_source,
                    matched_ingredient=matched_ingredient,
                    matched_catalog_entry=matched_catalog_entry,
                    input_span=input_span,
                    explanation=message,
                    confidence=confidence,
                )
                for profile_value in matching_profiles
            )
            if rule["outcome"] == "block":
                found_risks.append(message)
                risk_score = 1.0
            else:
                found_warnings.append(message)
                risk_score = max(risk_score, 0.4)

        for allergy in profile.get("alerjiler", []):
            allergy_text = str(allergy).strip()
            allergy_key = _normalize(allergy_text)
            if not allergy_text or allergy_key in configured_allergies:
                continue
            matches = [text for text in texts if contains_positive_food_mention(text, allergy_text)]
            if matches:
                found_risks.append(f"Alerji riski (Kesin İhlal): {allergy_text}")
                risk_score = 1.0
                evidence_findings.append(_finding(
                    restriction_type="allergy",
                    restriction_identifier=allergy_text,
                    evidence_level="CONFIRMED",
                    evidence_source="explicit_input",
                    matched_ingredient=allergy_text,
                    input_span=allergy_text,
                    explanation=f"Alerji riski (Kesin İhlal): {allergy_text}",
                    confidence=0.95,
                ))
            else:
                evidence_level = "CLEAR" if structured_ingredients and not unknown_ingredients else "UNKNOWN"
                evidence_findings.append(_finding(
                    restriction_type="allergy",
                    restriction_identifier=allergy_text,
                    evidence_level=evidence_level,
                    evidence_source="structured_ingredients" if evidence_level == "CLEAR" else "missing_or_unverified_ingredients",
                    explanation=(
                        "Yapılandırılmış içerikte bu alerjenle eşleşme bulunmadı."
                        if evidence_level == "CLEAR"
                        else "Alerjen profilde kayıtlı, ancak incelenen içerikte bulunduğuna dair kanıt yok. Etiket doğrulaması gerekebilir."
                    ),
                    confidence=0.9 if evidence_level == "CLEAR" else 0.2,
                ))

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
            "evidence_findings": evidence_findings,
            "confirmed_conflicts": [
                finding for finding in evidence_findings
                if finding["evidence_level"] == "CONFIRMED"
                and finding["explanation"] in found_risks
            ],
        }


def profile_hard_avoid_ingredients(profile: Dict[str, Any]) -> List[str]:
    """Deterministic hard-avoid FOOD/ingredient terms for a profile.

    Sourced only from the food-constraint registry: for each BLOCK rule whose
    profile aliases match the profile's allergies/diseases, the offending
    ingredient group's food aliases are collected, plus the literal allergy terms.
    Raw disease names (e.g. "diyabet") are NEVER added — they are not foods; they
    remain personalization context in the profile summary, not a forbidden list.
    No new clinical mapping is invented here.
    """
    registry = load_food_constraint_registry()
    groups = registry["ingredient_groups"]
    avoid: list[str] = []
    for rule in registry["profile_rules"]:
        if rule.get("outcome") != "block":
            continue
        field = rule.get("profile_field")
        profile_values = profile.get(field) or []
        if not any(_contains_profile_alias(str(value), rule["profile_aliases"]) for value in profile_values):
            continue
        group_name = rule.get("ingredient_group")
        group = groups.get(group_name) if group_name else None
        if group:
            avoid.extend(str(alias) for alias in (group.get("aliases") or []))
    # Literal allergy values are themselves food/allergen terms.
    avoid.extend(str(term) for term in (profile.get("alerjiler") or []))
    return list(dict.fromkeys(term.strip() for term in avoid if str(term or "").strip()))
