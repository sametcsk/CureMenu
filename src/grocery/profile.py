from dataclasses import dataclass

from src.profile_context import ResolvedProfileSnapshot


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


def grocery_profile_facts(snapshot: ResolvedProfileSnapshot) -> GroceryProfileFacts:
    return GroceryProfileFacts(
        summary=snapshot.profile_summary,
        diseases=_dedupe(list(snapshot.diseases)),
        allergies=_dedupe(list(snapshot.allergies)),
        medications=_dedupe(list(snapshot.medications)),
    )
