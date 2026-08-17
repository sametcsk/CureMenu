"""Canonical profile target resolution for all personalized runtime flows."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import sqlite3
import unicodedata
from typing import Any

from fastapi import HTTPException

from src.database import profil_getir_db
from src.memory import build_memory_namespace
from src.messages import PROFIL_BULUNAMADI, PROFIL_GEREKLI
from src.models import AileUyesi, KullaniciProfili
from src.privacy.redaction import redact_text
from src.profil_utils import aile_profil_ozeti_olustur, profil_ozeti_olustur
from src.target_resolution import TargetResolution, parse_multi_key, resolve_target_from_message


def _dedupe(values: list[str]) -> tuple[str, ...]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        cleaned = str(value or "").strip()
        key = cleaned.casefold()
        if cleaned and key not in seen:
            seen.add(key)
            result.append(cleaned)
    return tuple(result)


def _fold_profile_key(value: str) -> str:
    text = unicodedata.normalize("NFKD", str(value or "").strip().casefold())
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    return text.replace("ı", "i")


def _profile_fingerprint(members: list[AileUyesi]) -> str:
    payload = [
        {
            "id": member.id,
            "diseases": sorted(_dedupe(member.hastaliklar or []), key=str.casefold),
            "allergies": sorted(_dedupe(member.alerjiler or []), key=str.casefold),
            "medications": sorted(_dedupe(member.ilaclar or []), key=str.casefold),
            "goal": str(member.hedef or ""),
            "medical_history": str(member.tibbi_gecmis or ""),
            "notes": str(member.notlar or ""),
        }
        for member in members
    ]
    canonical = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def profile_fingerprint_map(profile: KullaniciProfili) -> dict[str, Any]:
    """Return backend-owned fingerprints for every selectable profile target."""
    result: dict[str, Any] = {"members": {}}
    if profile.ana_kullanici is not None:
        result["self"] = _profile_fingerprint([profile.ana_kullanici])
    if profile.aile_uyeleri:
        result["members"] = {
            member.id: _profile_fingerprint([member])
            for member in profile.aile_uyeleri
        }
    all_members = profile.tum_uyeler()
    if all_members:
        result["family"] = _profile_fingerprint(all_members)
    return result


@dataclass(frozen=True)
class ResolvedProfileSnapshot:
    account_id: str
    target_id: str
    target_name: str
    target_scope: str
    target_key: str
    source: str
    profile_fingerprint: str
    diseases: tuple[str, ...]
    allergies: tuple[str, ...]
    medications: tuple[str, ...]
    goals: tuple[str, ...]
    ages: tuple[int, ...]
    genders: tuple[str, ...]
    medical_history: tuple[str, ...]
    notes: tuple[str, ...]
    family_member_id: str | None
    profile_summary: str
    relationship: str = ""

    @property
    def memory_namespace(self) -> str:
        subject = f"{self.target_scope}:{self.target_id}:profile:{self.profile_fingerprint}"
        return build_memory_namespace(self.account_id, subject)

    def quality_profile(self) -> dict[str, Any]:
        return {
            "hastaliklar": list(self.diseases),
            "alerjiler": list(self.allergies),
            "ilaclar": list(self.medications),
            "yas": min(self.ages) if self.ages else 30,
            "cinsiyet": self.genders[0] if len(self.genders) == 1 else "",
            "hedef": ", ".join(self.goals),
            "notlar": list(self.notes),
        }

    def history_metadata(self) -> dict[str, str]:
        return {
            "target_key": self.target_key,
            "target_id": self.target_id,
            "target_name": self.target_name,
            "target_scope": self.target_scope,
            "profile_fingerprint": self.profile_fingerprint,
        }

    def state_payload(self) -> dict[str, Any]:
        return {
            **self.history_metadata(),
            "source": self.source,
            "diseases": list(self.diseases),
            "allergies": list(self.allergies),
            "medications": list(self.medications),
            "goals": list(self.goals),
            "ages": list(self.ages),
            "genders": list(self.genders),
            "medical_history": list(self.medical_history),
            "notes": list(self.notes),
            "family_member_id": self.family_member_id,
        }


def _resolve_members(profile: KullaniciProfili, requested_target: str) -> tuple[list[AileUyesi], str, str, str, str, str | None]:
    target = str(requested_target or "kendim").strip()
    if target == "aile":
        members = profile.tum_uyeler()
        if not members:
            raise HTTPException(status_code=400, detail=PROFIL_GEREKLI)
        return members, "family", "Tüm Aile", "family", "aile", None

    main = profile.ana_kullanici

    if target.startswith("multi:"):
        # An explicit set of two or more members. Canonical (sorted) order makes
        # the member list, target key, and fingerprint independent of the order
        # the people were mentioned in the message.
        canonical = sorted(dict.fromkeys(parse_multi_key(target)))
        selected: list[AileUyesi] = []
        labels: list[str] = []
        for cid in canonical:
            if cid == "kendim":
                if main is None:
                    raise HTTPException(status_code=400, detail=PROFIL_GEREKLI)
                selected.append(main)
                labels.append("Sen")
            else:
                member = next((item for item in profile.aile_uyeleri if item.id == cid), None)
                if member is None:
                    raise HTTPException(status_code=400, detail=PROFIL_GEREKLI)
                selected.append(member)
                labels.append(member.ad)
        if len(selected) < 2:
            raise HTTPException(status_code=400, detail=PROFIL_GEREKLI)
        return selected, target, " + ".join(labels), "multi", target, None
    if target == "kendim" or (main is not None and target == main.id):
        if main is None:
            raise HTTPException(status_code=400, detail=PROFIL_GEREKLI)
        return [main], main.id, main.ad, "self", "kendim", main.id

    folded = _fold_profile_key(target)
    member = next(
        (
            item
            for item in profile.aile_uyeleri
            if item.id == target or _fold_profile_key(item.ad) == folded
        ),
        None,
    )
    if member is None:
        raise HTTPException(status_code=400, detail=PROFIL_GEREKLI)
    return [member], member.id, member.ad, "member", member.id, member.id


def resolve_profile_snapshot_from_profile(
    account_id: str,
    profile: KullaniciProfili,
    requested_target: str,
) -> ResolvedProfileSnapshot:
    members, target_id, target_name, target_scope, target_key, family_member_id = _resolve_members(
        profile,
        requested_target,
    )
    diseases = _dedupe([value for member in members for value in (member.hastaliklar or [])])
    allergies = _dedupe([value for member in members for value in (member.alerjiler or [])])
    medications = _dedupe([value for member in members for value in (member.ilaclar or [])])
    goals = _dedupe([member.hedef for member in members if member.hedef])
    medical_history = _dedupe([member.tibbi_gecmis for member in members if member.tibbi_gecmis])
    notes = _dedupe([
        redact_text(member.notlar, max_length=1000)
        for member in members
        if member.notlar
    ])
    if target_scope == "family":
        summary = aile_profil_ozeti_olustur(profile)
    elif target_scope == "multi":
        # Per-person breakdown (each member's own constraints) plus a combined
        # safety directive. The union above (diseases/allergies/...) still drives
        # the deterministic RuleEngine; this text lets the model word per-person
        # adaptations without losing anyone's restriction.
        lines = ["SEÇİLİ KİŞİLER ORTAK İSTEĞİ:"]
        lines.extend(f"- {profil_ozeti_olustur(member)}" for member in members)
        lines.append(
            "Öneri, seçili kişilerin TÜM alerji/hastalık/ilaç kısıtlarına AYNI ANDA uymalı. "
            "Ortak güvenli bir taban seçenek öner; gerekiyorsa kişi bazlı küçük uyarlama belirt. "
            "Hepsine aynı anda güvenli tek bir seçenek yoksa bunu söyle ve ayrı uyarlamalar öner."
        )
        summary = "\n".join(lines)
    else:
        summary = profil_ozeti_olustur(members[0])
    return ResolvedProfileSnapshot(
        account_id=account_id,
        target_id=target_id,
        target_name=target_name,
        target_scope=target_scope,
        target_key=target_key,
        source="profile_db",
        profile_fingerprint=_profile_fingerprint(members),
        diseases=diseases,
        allergies=allergies,
        medications=medications,
        goals=goals,
        ages=tuple(member.yas for member in members),
        genders=tuple(member.cinsiyet.value for member in members),
        medical_history=medical_history,
        notes=notes,
        family_member_id=family_member_id,
        profile_summary=summary,
        relationship=(members[0].yakinlik or "") if target_scope == "member" and members else "",
    )


def resolve_profile_snapshot(
    account_id: str,
    requested_target: str,
    *,
    db: sqlite3.Connection,
) -> ResolvedProfileSnapshot:
    profile = profil_getir_db(account_id, conn=db)
    if profile is None:
        raise HTTPException(status_code=404, detail=PROFIL_BULUNAMADI)
    return resolve_profile_snapshot_from_profile(account_id, profile, requested_target)


def resolve_target_snapshot(
    account_id: str,
    message: str,
    client_hint: str,
    *,
    previous_target: str | None = None,
    db: sqlite3.Connection,
) -> tuple[ResolvedProfileSnapshot | None, TargetResolution]:
    """Resolve the chat target from the message (fail-closed) and build its snapshot.

    Canonical entry point for CureBot: the message decides the person when it names
    one; the client hint is used only when the message names nobody. When the
    reference is ambiguous the snapshot is None and ``resolution.needs_clarification``
    is True, and the caller must ask for clarification instead of falling back to
    any profile. Kept here (not in a router) so personalized flows never read the
    raw profile directly.
    """
    profile = profil_getir_db(account_id, conn=db)
    if profile is None:
        raise HTTPException(status_code=404, detail=PROFIL_BULUNAMADI)
    resolution = resolve_target_from_message(profile, message, client_hint, previous_target)
    if resolution.needs_clarification:
        return None, resolution
    snapshot = resolve_profile_snapshot_from_profile(account_id, profile, resolution.target)
    return snapshot, resolution


def history_matches_snapshot(record: dict[str, Any], snapshot: ResolvedProfileSnapshot) -> bool:
    raw = record.get("metadata")
    if not raw:
        return False
    try:
        metadata = json.loads(raw) if isinstance(raw, str) else dict(raw)
    except (TypeError, ValueError, json.JSONDecodeError):
        return False
    return (
        metadata.get("target_id") == snapshot.target_id
        and metadata.get("target_scope") == snapshot.target_scope
        and metadata.get("profile_fingerprint") == snapshot.profile_fingerprint
    )
