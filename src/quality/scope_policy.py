"""Conservative product-scope boundaries for personalized nutrition output."""

from __future__ import annotations

import unicodedata

from src.models import AileUyesi, KullaniciProfili


def _normalize(value: str) -> str:
    folded = unicodedata.normalize("NFKD", str(value or "").casefold())
    return "".join(char for char in folded if not unicodedata.combining(char))


def _target_members(profile: KullaniciProfili, target: str) -> list[AileUyesi]:
    if target == "aile":
        return profile.tum_uyeler()
    if target == "kendim":
        return [profile.ana_kullanici] if profile.ana_kullanici else []
    return [
        member
        for member in profile.aile_uyeleri
        if _normalize(member.ad) == _normalize(target)
    ]


def profile_scope_review_reasons(profile: KullaniciProfili, target: str) -> list[str]:
    """Identify populations that require professional review without diagnosing or blocking."""
    reasons: list[str] = []
    for member in _target_members(profile, target):
        context = _normalize(" ".join([
            str(member.hedef or ""),
            str(member.tibbi_gecmis or ""),
            " ".join(member.hastaliklar or []),
        ]))
        if member.yas < 18:
            reasons.append("18 yaş altı bireyler için kişiselleştirilmiş plan sağlık profesyoneli tarafından değerlendirilmelidir.")
        if any(term in context for term in ("hamile", "gebelik", "emzir")):
            reasons.append("Gebelik veya emzirme dönemindeki plan sağlık profesyoneli tarafından değerlendirilmelidir.")
        if any(term in context for term in ("bobrek", "renal", "diyaliz", "dialysis")):
            reasons.append("Böbrek hastalığında beslenme; evre, ilaçlar ve güncel tahlillere göre uzman tarafından değerlendirilmelidir.")
        if any(term in context for term in ("anoreksi", "bulimi", "yeme bozuklugu", "eating disorder")):
            reasons.append("Yeme bozukluğu öyküsünde otomatik plan yerine sağlık profesyoneli değerlendirmesi gerekir.")
    return list(dict.fromkeys(reasons))
