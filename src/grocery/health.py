from dataclasses import dataclass

from src.medical_knowledge.bioportal_client import BioPortalClient
from src.medical_knowledge.normalizer import MedicationNormalizer
from src.medical_knowledge.safety_checker import check_medication_food_safety


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

ALLERGY_GROUPS = {
    "sut": "dairy",
    "laktoz": "dairy",
    "dairy": "dairy",
    "gluten": "gluten",
    "colyak": "gluten",
    "bugday": "gluten",
}


def _normalize(value: str) -> str:
    return (value or "").strip().lower().translate(TR_MAP)


def _contains_any(text: str, keywords: tuple[str, ...]) -> bool:
    return any(keyword in text for keyword in keywords)


def _item_matches_group(item: str, group: str) -> bool:
    return _contains_any(item, FOOD_GROUPS.get(group, ()))


def _allergy_group(allergy: str) -> str | None:
    for keyword, group in ALLERGY_GROUPS.items():
        if keyword in allergy:
            return group
    return None


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
            return HealthAssessment(
                "avoid",
                f"İlaç-besin riski ({severity}): {explanation}",
            )

    for allergy in allergy_terms:
        group = _allergy_group(allergy)
        if group and _item_matches_group(item, group):
            return HealthAssessment("avoid", f"Alerji kaydıyla çakışıyor: {allergy}")
        if allergy and allergy in item:
            return HealthAssessment("avoid", f"Alerji kaydıyla çakışıyor: {allergy}")

    if _contains_any(disease_text, ("colyak", "celiac", "gluten")) and _item_matches_group(item, "gluten"):
        return HealthAssessment("avoid", "Çölyak/gluten hassasiyeti için uygun olmayabilir.")

    if _contains_any(disease_text, ("laktoz", "lactose")) and _item_matches_group(item, "dairy"):
        return HealthAssessment("caution", "Laktoz hassasiyeti için alternatif gerekebilir.")

    if _contains_any(disease_text, ("diyabet", "seker", "diabetes")):
        if _item_matches_group(item, "sugar"):
            return HealthAssessment("avoid", "Diyabet kaydı nedeniyle ilave şekerden kaçınılmalı.")
        if _item_matches_group(item, "high_glycemic"):
            return HealthAssessment("caution", "Karbonhidrat porsiyonu diyabet kaydı nedeniyle dikkat gerektirir.")

    if _contains_any(disease_text, ("hipertansiyon", "tansiyon", "hypertension")):
        if _item_matches_group(item, "sodium"):
            return HealthAssessment("avoid", "Hipertansiyon kaydı nedeniyle tuz/işlenmiş ürün riski var.")
        if _item_matches_group(item, "processed"):
            return HealthAssessment("caution", "İşlenmiş ürünlerde sodyum içeriği değişebileceği için dikkat gerekir.")

    if _contains_any(disease_text, ("gut", "gout")):
        if "sakatat" in item:
            return HealthAssessment("avoid", "Gut kaydı nedeniyle yüksek pürin riski var.")
        if _item_matches_group(item, "purine"):
            return HealthAssessment("caution", "Gut kaydı nedeniyle pürin yükü dikkat gerektirir.")

    if not has_profile_data:
        return HealthAssessment("unknown", "Sağlık profili sınırlı; güvenli olduğu varsayılmadı.")

    return HealthAssessment("safe", "Profil kayıtlarıyla belirgin bir çakışma bulunmadı.")
