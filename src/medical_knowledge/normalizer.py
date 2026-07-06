from dataclasses import asdict, dataclass
import re
from typing import Any

from src.medical_knowledge.bioportal_client import BioPortalClient, default_bioportal_client


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

LOCAL_MEDICATION_ALIASES = {
    "warfarin": "warfarin",
    "coumadin": "warfarin",
    "jantoven": "warfarin",
    "kumadin": "warfarin",
    "metformin": "metformin",
    "glucophage": "metformin",
    "glifor": "metformin",
    "atorvastatin": "atorvastatin",
    "lipitor": "atorvastatin",
    "statin": "atorvastatin",
    "ciprofloxacin": "ciprofloxacin",
    "cipro": "ciprofloxacin",
    "siprofloksasin": "ciprofloxacin",
    "levothyroxine": "levothyroxine",
    "levotiroksin": "levothyroxine",
    "euthyrox": "levothyroxine",
    "tefor": "levothyroxine",
    "linezolid": "linezolid",
    "zyvox": "linezolid",
    "maoi": "linezolid",
    "mao inhibitor": "linezolid",
    "mao inhibitoru": "linezolid",
    "monoamin oksidaz inhibitoru": "linezolid",
    "monoamine oxidase inhibitor": "linezolid",
}


@dataclass(frozen=True)
class NormalizedMedication:
    original: str
    normalized_name: str | None
    source_type: str
    pref_label: str | None = None
    ontology_id: str | None = None
    cui: str | None = None
    semantic_types: list[str] | None = None
    synonyms: list[str] | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def normalize_text(value: str) -> str:
    return (value or "").strip().casefold().translate(TR_MAP)


def _candidate_values(result: dict[str, Any]) -> list[str]:
    values: list[str] = []
    for key in ("prefLabel", "notation", "cui"):
        value = result.get(key)
        if isinstance(value, str):
            values.append(value)
    synonyms = result.get("synonym")
    if isinstance(synonyms, list):
        values.extend(str(item) for item in synonyms)
    elif isinstance(synonyms, str):
        values.append(synonyms)
    return values


def canonical_medication_name(value: str) -> str | None:
    normalized = normalize_text(value)
    if normalized in LOCAL_MEDICATION_ALIASES:
        return LOCAL_MEDICATION_ALIASES[normalized]
    for alias, canonical in LOCAL_MEDICATION_ALIASES.items():
        if re.search(rf"(?<![a-z0-9]){re.escape(alias)}(?![a-z0-9])", normalized):
            return canonical
    return None


class MedicationNormalizer:
    def __init__(self, bioportal_client: BioPortalClient | None = None) -> None:
        self._bioportal_client = bioportal_client or default_bioportal_client()
        self._cache: dict[str, NormalizedMedication] = {}

    def normalize(self, medication: str) -> NormalizedMedication:
        original = (medication or "").strip()
        cache_key = normalize_text(original)
        if cache_key in self._cache:
            return self._cache[cache_key]

        canonical = canonical_medication_name(original)
        if canonical:
            result = NormalizedMedication(
                original=original,
                normalized_name=canonical,
                source_type="local_fallback",
                pref_label=canonical,
            )
            self._cache[cache_key] = result
            return result

        for hit in self._bioportal_client.search(original):
            for candidate in _candidate_values(hit):
                canonical = canonical_medication_name(candidate)
                if canonical:
                    result = NormalizedMedication(
                        original=original,
                        normalized_name=canonical,
                        source_type="bioportal",
                        pref_label=str(hit.get("prefLabel") or canonical),
                        ontology_id=str(hit.get("@id") or hit.get("id") or "") or None,
                        cui=str(hit.get("cui") or "") or None,
                        semantic_types=hit.get("semanticType") if isinstance(hit.get("semanticType"), list) else None,
                        synonyms=hit.get("synonym") if isinstance(hit.get("synonym"), list) else None,
                    )
                    self._cache[cache_key] = result
                    return result

        result = NormalizedMedication(
            original=original,
            normalized_name=None,
            source_type="local_fallback",
            pref_label=None,
        )
        self._cache[cache_key] = result
        return result

    def normalize_many(self, medications: list[str]) -> list[NormalizedMedication]:
        return [self.normalize(medication) for medication in medications or [] if str(medication or "").strip()]
