from dataclasses import dataclass
import re
import unicodedata

from src.medical_knowledge.bioportal_client import BioPortalClient
from src.medical_knowledge.normalizer import MedicationNormalizer
from src.medical_knowledge.safety_checker import check_medication_food_safety
from src.quality.rule_engine import RuleEngine, contains_positive_food_mention


@dataclass(frozen=True)
class HealthAssessment:
    status: str
    reason: str


TR_MAP = str.maketrans(
    {
        "ç": "c",
        "ğ": "g",
        "ı": "i",
        "ö": "o",
        "ş": "s",
        "ü": "u",
        "Ç": "c",
        "Ğ": "g",
        "İ": "i",
        "I": "i",
        "Ö": "o",
        "Ş": "s",
        "Ü": "u",
    }
)

FOOD_GROUPS = {
    "dairy": ("sut", "yogurt", "peynir", "ayran", "kefir", "tereyagi", "kaymak"),
    "gluten": ("bugday", "ekmek", "makarna", "bulgur", "un", "irmik", "sehriye"),
    "sugar": ("seker", "tatli", "recel", "bal", "surup", "cikolata", "pasta"),
    "high_glycemic": ("pirinc", "makarna", "ekmek", "bulgur", "patates", "muz"),
    "sodium": ("tuz", "tuzlu", "salam", "sucuk", "konserve", "tursu", "zeytin", "cips"),
    "purine": ("sakatat", "kirmizi et", "ton baligi", "hamsi", "sardalya", "midye"),
    "processed": ("hazir", "paketli", "islenmis", "sos"),
}

def _normalize(value: str) -> str:
    folded = unicodedata.normalize("NFKD", str(value or "").casefold())
    without_marks = "".join(char for char in folded if not unicodedata.combining(char))
    return without_marks.translate(str.maketrans({"ı": "i"})).strip()


def _contains_any(text: str, keywords: tuple[str, ...]) -> bool:
    return any(contains_positive_food_mention(text, keyword) for keyword in keywords)


def _item_matches_group(item: str, group: str) -> bool:
    safe_prefixes: tuple[str, ...] = ()
    if group == "dairy":
        safe_prefixes = ("bitkisel", "badem", "soya", "yulaf", "pirinc", "hindistan cevizi")
    elif group == "gluten":
        safe_prefixes = ("glutensiz",)
    return any(
        contains_positive_food_mention(item, keyword, safe_prefixes=safe_prefixes)
        for keyword in FOOD_GROUPS.get(group, ())
    )


def assess_item_health(
    item_name: str,
    *,
    allergies: list[str],
    diseases: list[str],
    medications: list[str] | None = None,
) -> HealthAssessment:
    item = _normalize(item_name)
    allergy_terms = [_normalize(allergy) for allergy in allergies if _normalize(allergy)]
    disease_terms = [_normalize(disease) for disease in diseases if _normalize(disease)]
    disease_text = " ".join(disease_terms)
    has_profile_data = bool(allergy_terms or disease_terms or medications)
    medication_assessment: HealthAssessment | None = None

    if medications:
        medication_safety = check_medication_food_safety(
            medications,
            item_name,
            normalizer=MedicationNormalizer(BioPortalClient(api_key="")),
        )
        matched_rules = medication_safety.get("matched_rules") or []
        if matched_rules:
            explanation = " ".join(rule.get("explanation", "") for rule in matched_rules)
            severity = medication_safety.get("severity", "caution")
            medication_assessment = HealthAssessment(
                "avoid" if severity == "avoid" else "caution",
                f"İlaç-besin riski ({severity}): {explanation}",
            )
        elif medication_safety.get("severity") == "unknown":
            medication_assessment = HealthAssessment(
                "unknown",
                "Kayıtlı ilaç için bu ürünün etkileşimi doğrulanamadı; sağlık profesyoneline danışılmalı.",
            )

    constraint_result = RuleEngine().check_rules(
        {"alerjiler": allergies, "hastaliklar": diseases},
        item_name,
        [item_name],
    )
    if constraint_result["found_risks"]:
        return HealthAssessment("avoid", constraint_result["found_risks"][0])
    if medication_assessment and medication_assessment.status == "avoid":
        return medication_assessment
    if constraint_result["found_warnings"]:
        return HealthAssessment("caution", constraint_result["found_warnings"][0])
    if medication_assessment:
        return medication_assessment

    if _contains_any(disease_text, ("laktoz", "lactose")) and _item_matches_group(item, "dairy"):
        return HealthAssessment("caution", "Laktoz hassasiyeti için alternatif gerekebilir.")

    if _contains_any(disease_text, ("diyabet", "seker", "diabetes")):
        if _item_matches_group(item, "sugar"):
            return HealthAssessment("caution", "Diyabet kaydı nedeniyle şeker miktarı ve porsiyon doğrulanmalı.")
        if _item_matches_group(item, "high_glycemic"):
            return HealthAssessment("caution", "Karbonhidrat porsiyonu diyabet kaydı nedeniyle dikkat gerektirir.")

    if _contains_any(disease_text, ("hipertansiyon", "tansiyon", "hypertension")):
        if _item_matches_group(item, "sodium"):
            return HealthAssessment("caution", "Hipertansiyon kaydı nedeniyle sodyum miktarı doğrulanmalı.")
        if _item_matches_group(item, "processed"):
            return HealthAssessment("caution", "İşlenmiş ürünlerde sodyum içeriği değişebileceği için dikkat gerekir.")

    if not has_profile_data:
        return HealthAssessment("unknown", "Sağlık profili sınırlı; güvenli olduğu varsayılmadı.")

    return HealthAssessment("safe", "Profil kayıtlarıyla belirgin bir çakışma bulunmadı.")
