from dataclasses import dataclass

from src.models import AileUyesi, KullaniciProfili
from src.profil_utils import aile_profil_ozeti_olustur


@dataclass(frozen=True)
class GroceryProfileFacts:
    summary: str
    diseases: list[str]
    allergies: list[str]
    medications: list[str]


def _dedupe(values: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        cleaned = str(value or "").strip()
        key = cleaned.lower()
        if cleaned and key not in seen:
            seen.add(key)
            result.append(cleaned)
    return result


def _collect_members(members: list[AileUyesi]) -> GroceryProfileFacts:
    diseases: list[str] = []
    allergies: list[str] = []
    medications: list[str] = []
    for member in members:
        diseases.extend(getattr(member, "hastaliklar", []) or [])
        allergies.extend(getattr(member, "alerjiler", []) or [])
        medications.extend(getattr(member, "ilaclar", []) or [])
    return GroceryProfileFacts(
        summary="",
        diseases=_dedupe(diseases),
        allergies=_dedupe(allergies),
        medications=_dedupe(medications),
    )


def _member_summary(member: AileUyesi) -> str:
    diseases = ", ".join(getattr(member, "hastaliklar", []) or []) or "Yok"
    allergies = ", ".join(getattr(member, "alerjiler", []) or []) or "Yok"
    medications = ", ".join(getattr(member, "ilaclar", []) or []) or "Yok"
    return (
        f"{member.ad}, "
        f"Hastalıklar: {diseases}, "
        f"Alerjiler: {allergies}, "
        f"Kullandığı ilaçlar: {medications}"
    )


def grocery_profile_facts(profil: KullaniciProfili, kimin_icin: str) -> GroceryProfileFacts:
    if kimin_icin == "aile":
        members = profil.tum_uyeler()
        facts = _collect_members(members)
        return GroceryProfileFacts(
            summary=aile_profil_ozeti_olustur(profil),
            diseases=facts.diseases,
            allergies=facts.allergies,
            medications=facts.medications,
        )

    target = profil.ana_kullanici
    if kimin_icin != "kendim":
        target = next((uye for uye in profil.aile_uyeleri if uye.ad.lower() == kimin_icin.lower()), None)
    if target is None:
        raise ValueError("profile_target_not_found")

    return GroceryProfileFacts(
        summary=_member_summary(target),
        diseases=_dedupe(getattr(target, "hastaliklar", []) or []),
        allergies=_dedupe(getattr(target, "alerjiler", []) or []),
        medications=_dedupe(getattr(target, "ilaclar", []) or []),
    )
