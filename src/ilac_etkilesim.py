"""
CureMenu - hybrid medication-food safety layer.

The primary deterministic rule source is
src/medical_knowledge/data/high_risk_medications.json. Broader clinical context
can still come from RAG, but critical safety is not delegated to retrieval alone.
"""

from dataclasses import dataclass, field

from src.logger import get_logger
from src.memory import klinik_bilgi_getir
from src.medical_knowledge.medication_rules import load_high_risk_medication_rules, rules_for_medication
from src.medical_knowledge.normalizer import MedicationNormalizer
from src.medical_knowledge.safety_checker import check_medication_food_safety

logger = get_logger(__name__)

YAYGIN_ILACLAR = [
    "metformin",
    "insulin",
    "warfarin",
    "atorvastatin",
    "levothyroxine",
    "ciprofloxacin",
    "linezolid",
    "lisinopril",
    "omeprazol",
    "aspirin",
]


@dataclass(frozen=True)
class IlacEtkilesimKurali:
    ad: str
    aliases: list[str] = field(default_factory=list)
    riskli_terimler: list[str] = field(default_factory=list)
    uyari: str = ""


def _load_deterministic_rules() -> list[IlacEtkilesimKurali]:
    registry = load_high_risk_medication_rules()
    return [
        IlacEtkilesimKurali(
            ad=rule.medication,
            aliases=rule.aliases,
            riskli_terimler=rule.risk_terms,
            uyari=rule.explanation,
        )
        for rule in registry["rules"]
    ]


ILAC_ETKILESIM_KURALLARI = _load_deterministic_rules()

_TURKISH_ASCII = str.maketrans(
    {
        "ç": "c",
        "Ç": "c",
        "ğ": "g",
        "Ğ": "g",
        "ı": "i",
        "I": "i",
        "İ": "i",
        "ö": "o",
        "Ö": "o",
        "ş": "s",
        "Ş": "s",
        "ü": "u",
        "Ü": "u",
    }
)


def _normalize(text: str) -> str:
    return (text or "").translate(_TURKISH_ASCII).casefold()


def eslesen_kurallar(ilaclar: list[str]) -> list[IlacEtkilesimKurali]:
    """Return deterministic safety rules matching user-entered medications."""
    normalized_ilaclar = MedicationNormalizer().normalize_many(ilaclar or [])
    eslesenler: list[IlacEtkilesimKurali] = []
    seen: set[str] = set()

    for normalized in normalized_ilaclar:
        for rule in rules_for_medication(normalized.normalized_name):
            if rule.medication in seen:
                continue
            seen.add(rule.medication)
            eslesenler.append(
                IlacEtkilesimKurali(
                    ad=rule.medication,
                    aliases=rule.aliases,
                    riskli_terimler=rule.risk_terms,
                    uyari=rule.explanation,
                )
            )

    return eslesenler


def yemekte_riskli_ilac_etkilesimi(yemek_adi: str, ilaclar: list[str]) -> list[str]:
    """Detect known medication-food risks in a proposed meal name."""
    result = check_medication_food_safety(ilaclar or [], yemek_adi or "")
    return [
        f"{rule['medication']}: {rule['explanation']}"
        for rule in result.get("matched_rules", [])
    ]


def ilac_etkilesim_ozeti(ilaclar: list[str]) -> str:
    """Build a prompt-ready hybrid medication-food interaction summary."""
    if not ilaclar:
        return "Kullandigi ilac: bildirilmedi."

    ilac_listesi = ", ".join(ilaclar)
    deterministic_rules = eslesen_kurallar(ilaclar)

    if deterministic_rules:
        kurallar = "\n".join(
            f"- {kural.ad}: {kural.uyari}" for kural in deterministic_rules
        )
        return (
            "ZORUNLU DETERMINISTIK ILAC-BESIN GUVENLIK KURALLARI:\n"
            f"{kurallar}\n"
            "Bu kurallar kritik guvenlik bariyeridir; RAG sonucu bos olsa bile uygulanmalidir."
        )

    sorgu = f"besin ilac etkilesimi: {ilac_listesi}"
    klinik_kanit = klinik_bilgi_getir(sorgu, k_adet=2)

    if not klinik_kanit:
        return (
            f"Kullandigi ilaclar: {ilac_listesi}. "
            "Registry kapsamindaki resmi kaynaklarda bu ilaclar icin yeterli bir etkilesim eslesmesi bulunamadi. "
            "Kesin bir etkilesim sonucu cikarma; belirsizligi doktor veya eczaciyla degerlendirmesini oner."
        )

    logger.info(
        "event=medication_rag_lookup status=completed medication_count=%d",
        len(ilaclar),
    )
    return (
        "KULLANILAN ILACLAR ICIN RESMI KAPSAMLI KAYNAK ALINTILARI "
        "(DESTEKLEYICI BILGI; UZMAN ONAYI DEGILDIR):\n"
        f"{klinik_kanit}"
    )
