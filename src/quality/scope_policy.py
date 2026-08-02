"""Conservative product-scope boundaries for personalized nutrition output."""

from __future__ import annotations

import unicodedata

from src.profile_context import ResolvedProfileSnapshot


def _normalize(value: str) -> str:
    folded = unicodedata.normalize("NFKD", str(value or "").casefold())
    return "".join(char for char in folded if not unicodedata.combining(char))


def profile_scope_review_reasons(snapshot: ResolvedProfileSnapshot) -> list[str]:
    """Identify populations that require professional review without diagnosing or blocking."""
    reasons: list[str] = []
    context = _normalize(" ".join([
        *snapshot.goals,
        *snapshot.medical_history,
        *snapshot.diseases,
    ]))
    if any(age < 18 for age in snapshot.ages):
        reasons.append("18 yaş altı bireyler için kişiselleştirilmiş plan sağlık profesyoneli tarafından değerlendirilmelidir.")
    if any(term in context for term in ("hamile", "gebelik", "emzir")):
        reasons.append("Gebelik veya emzirme dönemindeki plan sağlık profesyoneli tarafından değerlendirilmelidir.")
    if any(term in context for term in ("bobrek", "renal", "diyaliz", "dialysis")):
        reasons.append("Böbrek hastalığında beslenme; evre, ilaçlar ve güncel tahlillere göre uzman tarafından değerlendirilmelidir.")
    if any(term in context for term in ("anoreksi", "bulimi", "yeme bozuklugu", "eating disorder")):
        reasons.append("Yeme bozukluğu öyküsünde otomatik plan yerine sağlık profesyoneli değerlendirmesi gerekir.")
    return list(dict.fromkeys(reasons))
