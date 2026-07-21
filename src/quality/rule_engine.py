import re
import unicodedata
from typing import Any, Dict, List


def _normalize(value: str) -> str:
    folded = unicodedata.normalize("NFKD", str(value or "").casefold())
    without_marks = "".join(char for char in folded if not unicodedata.combining(char))
    return without_marks.translate(str.maketrans({"ı": "i"}))


_NON_INGREDIENT_SUFFIX = re.compile(
    r"^\s*(?:urunu\s+)?(?:"
    r"icermez|icermeyen|bulunmaz|yok(?:tur)?|kullanilmadan|yerine|alerjisi?|"
    r"riski|risklidir|riskli(?:dir)?|onerilmez|onermiyorum|onermeyin|"
    r"tuketmeyin|tuketilmemeli|kacinin|uzak\s+durun|uygun\s+degil|siz|suz"
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
        rf"(?<![a-z0-9]){re.escape(needle)}(?:li|lu|lik|luk)?(?![a-z0-9])"
    )
    for match in pattern.finditer(value):
        before = value[max(0, match.start() - 40):match.start()]
        if any(before.rstrip().endswith(f"{_normalize(prefix)} ".rstrip()) for prefix in safe_prefixes):
            continue
        after = value[match.end():match.end() + 60]
        if not _NON_INGREDIENT_SUFFIX.match(after):
            if not _belongs_to_shared_absence_list(value[match.end():]):
                return True
    return False


def _allergen_terms(allergy: str) -> set[str]:
    """Expand only well-defined food-allergen synonyms used by the UI."""
    normalized = _normalize(allergy)
    terms = {str(allergy or "").strip()}
    if "sut" in normalized:
        terms.update({"süt", "inek sütü", "yoğurt", "peynir", "ayran", "whey", "kazein"})
    if "yer fistigi" in normalized:
        terms.update({"yer fıstığı", "yer fıstığı ezmesi", "peanut"})
    if "yumurta" in normalized:
        terms.add("yumurta")
    return {term for term in terms if term}


def _contains_allergen_risk(text: str, allergy: str) -> bool:
    normalized_allergy = _normalize(allergy)
    plant_based_prefixes = (
        "bitkisel",
        "badem",
        "soya",
        "yulaf",
        "pirinç",
        "hindistan cevizi",
    )
    return any(
        contains_positive_food_mention(
            text,
            term,
            safe_prefixes=plant_based_prefixes if "sut" in normalized_allergy and _normalize(term) == "sut" else (),
        )
        for term in _allergen_terms(allergy)
    )


class RuleEngine:
    """Deterministic hard-rule checks for explicit food safety conflicts."""

    def check_rules(self, profile: Dict[str, Any], meal: str, ingredients: List[str]) -> Dict[str, Any]:
        found_risks: list[str] = []
        risk_score = 0.0
        texts = [meal or "", *(ingredients or [])]

        for allergy in profile.get("alerjiler", []):
            if any(_contains_allergen_risk(text, str(allergy)) for text in texts):
                found_risks.append(f"Alerji riski (Kesin İhlal): {allergy}")
                risk_score = 1.0

        diseases = {_normalize(disease) for disease in profile.get("hastaliklar", [])}
        has_gout = any("gut" in disease or "gout" in disease for disease in diseases)
        has_high_purine_meat = any(
            contains_positive_food_mention(text, term)
            for text in texts
            for term in ("sakatat", "ciğer", "böbrek eti", "dana böbrek", "kuzu böbrek", "işkembe")
        )
        if has_gout and has_high_purine_meat:
            found_risks.append("Gut hastalığında yüksek pürinli sakatat riski.")
            risk_score = max(risk_score, 0.8)

        return {
            "found_risks": found_risks,
            "medical_risk_score": risk_score,
        }
