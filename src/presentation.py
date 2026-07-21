"""User-facing wording for internal safety outcomes."""

from __future__ import annotations

import re
import unicodedata


GENERAL_REVIEW_GUIDANCE = (
    "Sağlık profiliniz nedeniyle bu öneri dikkat gerektirir. Böbrek hastalığı, "
    "kullandığınız ilaçlar ve güncel tahliller kişisel porsiyon ve zamanlama "
    "kararını etkileyebilir. Bu nedenle bu öneriyi uygulamadan önce doktorunuza, "
    "eczacınıza veya diyetisyeninize danışmanız uygun olur."
)

LEVOTHYROXINE_GUIDANCE = (
    "Levotiroksin kullanıyorsanız bazı besin ve takviyeler ilacın emilimini "
    "etkileyebilir. Zamanlama için doktorunuzun veya eczacınızın önerisini izleyin."
)

WARFARIN_GUIDANCE = (
    "Warfarin kullanıyorsanız K vitamini içeren besinleri tamamen kesmek yerine "
    "tüketim miktarını düzenli ve tutarlı tutmanız gerekebilir. Kişisel öneri için "
    "doktorunuza veya eczacınıza danışın."
)

YOUTH_GUIDANCE = (
    "18 yaş altındaki kullanıcılar için öğün ve porsiyon önerileri büyüme ve gelişim "
    "gereksinimleriyle birlikte değerlendirilmelidir. Ebeveyn ve çocuk sağlığı alanında "
    "çalışan bir doktor veya diyetisyen görüşü alınması uygun olur."
)


def _normalize(value: str) -> str:
    folded = unicodedata.normalize("NFKD", str(value or "").casefold().replace("ı", "i"))
    return "".join(char for char in folded if not unicodedata.combining(char))


def format_rule_risks_for_user(risks: list[str]) -> list[str]:
    """Keep rule outcomes intact while removing internal rule-engine labels."""
    formatted: list[str] = []
    for risk in risks:
        allergy_match = re.match(r"Alerji riski \(Kesin İhlal\):\s*(.+)", str(risk), re.IGNORECASE)
        if allergy_match:
            formatted.append(f"Kayıtlı alerjenle eşleşme bulundu: {allergy_match.group(1).strip()}.")
            continue
        formatted.append(str(risk).strip())
    return [item for item in formatted if item]


def friendly_source_title(title: str) -> str:
    """Return a readable title without exposing file or chunk identifiers."""
    raw = str(title or "").strip()
    normalized = _normalize(raw)
    if "kdigo" in normalized:
        return "KDIGO böbrek rehberi"
    if "levothyroxine" in normalized or "levotiroksin" in normalized:
        return "Levothyroxine ilaç etiketi"
    if "metformin" in normalized:
        return "Metformin ilaç etiketi"
    cleaned = re.sub(r"\s+", " ", re.sub(r"[_-]+", " ", re.sub(r"\.pdf$", "", raw, flags=re.IGNORECASE))).strip()
    return cleaned or "Sağlık kaynağı"


def user_facing_safety_guidance(raw_warning: str, *, blocked: bool = False) -> str:
    """Translate internal review detail into calm decision-support language."""
    normalized = _normalize(raw_warning)
    messages: list[str] = []

    if "warfarin" in normalized or "coumadin" in normalized or "inr" in normalized:
        messages.append(WARFARIN_GUIDANCE)
    if "levothyroxine" in normalized or "levotiroksin" in normalized:
        messages.append(LEVOTHYROXINE_GUIDANCE)
    if "18 yas alti" in normalized or "cocuk" in normalized or "ergen" in normalized:
        messages.append(YOUTH_GUIDANCE)

    needs_general_guidance = blocked or any(
        term in normalized
        for term in (
            "bobrek",
            "uzman incelemesi",
            "kaynak kaydi",
            "registry",
            "dogrulanamadi",
            "saglik profesyoneli",
        )
    )
    if needs_general_guidance or not messages:
        messages.append(GENERAL_REVIEW_GUIDANCE)

    return "\n\n".join(dict.fromkeys(messages))


def soften_generated_guidance(raw_text: str) -> str:
    """Remove authoritative clinical wording from model-generated user copy."""
    paragraphs = [part.strip() for part in re.split(r"\n\s*\n", str(raw_text or "")) if part.strip()]
    softened: list[str] = []

    for paragraph in paragraphs:
        normalized = _normalize(paragraph)
        medication_guidance: list[str] = []
        if "levothyroxine" in normalized or "levotiroksin" in normalized:
            if any(term in normalized for term in ("60 dakika", "ac karnina", "emin olun", "unutmay")):
                medication_guidance.append(LEVOTHYROXINE_GUIDANCE)
        if "warfarin" in normalized or "inr" in normalized:
            if any(term in normalized for term in ("kritik", "koruyunuz", "emin olun", "unutmay")):
                medication_guidance.append(WARFARIN_GUIDANCE)
        if medication_guidance:
            softened.extend(medication_guidance)
            continue

        paragraph = re.sub(r"(?i)\*\*Önemli (?:Not|Uyarı):\*\*", "**Dikkat:**", paragraph)
        paragraph = re.sub(r"(?i)\bharika ve güvenli\b", "profilinize göre değerlendirilebilecek", paragraph)
        paragraph = re.sub(
            r"(?i)\bböbrek dostu(?:dur)?\b",
            "böbrek durumunuz açısından porsiyonu değerlendirilmesi gereken",
            paragraph,
        )
        paragraph = re.sub(r"(?i)\ben güvenli\b", "değerlendirilebilecek", paragraph)
        paragraph = re.sub(r"(?i)\bgüvenli\b", "profil kısıtlarıyla karşılaştırılmış", paragraph)
        paragraph = re.sub(
            r"(?i)\bwarfarin etkileşimi yaratmayacak şekilde\b",
            "Warfarin kullanımı açısından uzmanla değerlendirilmek üzere",
            paragraph,
        )
        paragraph = re.sub(r"(?i)\bhayati önem taşır\b", "dikkat gerektirir", paragraph)
        paragraph = re.sub(r"(?i)\bkritiktir\b", "uzmanla değerlendirilmelidir", paragraph)
        paragraph = re.sub(r"(?i)\bkesinlikle\b", "", paragraph)
        softened.append(re.sub(r" {2,}", " ", paragraph).strip())

    return "\n\n".join(dict.fromkeys(item for item in softened if item))
