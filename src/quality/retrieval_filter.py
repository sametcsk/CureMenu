"""Conservative lexical checks for semantically retrieved clinical evidence."""

from __future__ import annotations

import os
import re
import unicodedata
from dataclasses import dataclass
from typing import Iterable

from src.medical_knowledge.provenance import load_evidence_registry


STOPWORDS = {
    "acaba", "ama", "and", "besin", "bir", "bunu", "icin", "ile", "ilac",
    "kadar", "kullanilan", "kullanimi", "meal", "nedir", "onerilen", "profil",
    "saglik", "the", "uygun", "ve", "veya", "yemek", "yok",
}

SYNONYM_GROUPS = (
    {"colyak", "celiac"},
    {"diyabet", "diabetes"},
    {"sut", "milk", "dairy"},
    {"kalsiyum", "calcium"},
    {"ispanak", "spinach"},
    {"vitamin", "vitamini"},
    {"bobrek", "bobrekler", "kidney", "renal"},
    {"hipertansiyon", "hypertension"},
    {"alerji", "alerjisi", "allergy"},
    {"gida", "food"},
    {"kacinma", "kacinmak", "avoid", "avoidance"},
    {"tetikleyici", "tetikleyiciden", "trigger"},
    {"sodyum", "sodium"},
    {"potasyum", "potassium"},
    {"hastalik", "hastaligi", "disease"},
)

CLINICAL_ANCHORS = {
    "warfarin", "atorvastatin", "metformin", "levothyroxine", "ciprofloxacin", "linezolid",
    "coumadin", "jantoven", "lipitor", "glucophage", "euthyrox", "cipro", "maoi",
    "colyak", "celiac", "diyabet", "diabetes", "hipertansiyon", "hypertension",
    "bobrek", "kidney", "renal", "gut", "gout", "alerji", "allergy", "laktoz", "lactose",
    "ibs", "hashimoto",
}


def normalize_text(value: str) -> str:
    folded = unicodedata.normalize("NFKD", (value or "").casefold())
    without_marks = "".join(char for char in folded if not unicodedata.combining(char))
    return re.sub(r"[^a-z0-9]+", " ", without_marks).strip()


def informative_tokens(value: str) -> set[str]:
    return {
        token
        for token in normalize_text(value).split()
        if len(token) >= 3 and token not in STOPWORDS and not token.isdigit()
    }


def expand_query_tokens(tokens: set[str]) -> set[str]:
    expanded = set(tokens)
    for group in SYNONYM_GROUPS:
        if tokens & group:
            expanded.update(group)
    return expanded


@dataclass(frozen=True)
class FilteredRetrieval:
    document: object
    distance: float
    lexical_score: float
    matched_terms: tuple[str, ...]


OFFICIAL_SOURCE_ROLES = {"regulatory_label", "clinical_guideline"}


def is_official_scoped_evidence(document: object) -> bool:
    """Return whether a result belongs to the hash-pinned official registry scope."""
    metadata = getattr(document, "metadata", {}) or {}
    try:
        authority_tier = int(metadata.get("authority_tier", 3))
    except (TypeError, ValueError):
        return False
    registry_source_id = str(metadata.get("registry_source_id") or "").strip()
    try:
        registry = load_evidence_registry()
    except (OSError, ValueError):
        return False
    source = (registry.get("sources") or {}).get(registry_source_id) or {}
    expected_hash = str(source.get("sha256") or "").casefold()
    return bool(
        authority_tier == 1
        and source
        and str(metadata.get("scope_version") or "") == str(registry.get("schema_version") or "")
        and str(metadata.get("file_sha256") or "").casefold() == expected_hash
        and str(metadata.get("source_role") or "") in OFFICIAL_SOURCE_ROLES
        and str(metadata.get("source_role") or "") == str(source.get("source_role") or "")
        and authority_tier == int(source.get("authority_tier", 3))
    )


def filter_retrieval_results(
    query: str,
    results: Iterable[tuple[object, float]],
    *,
    limit: int,
    max_per_source: int = 1,
    evidence_context: str = "background",
) -> list[FilteredRetrieval]:
    """Keep only results sharing meaningful terms and diversify by source."""
    query_tokens = expand_query_tokens(informative_tokens(query))
    if not query_tokens:
        return []

    candidates: list[FilteredRetrieval] = []
    seen_content: set[str] = set()
    for document, distance in results:
        if evidence_context == "health_claim" and not is_official_scoped_evidence(document):
            continue
        content = str(getattr(document, "page_content", "") or "").strip()
        if len(content) < 80:
            continue
        content_key = normalize_text(content)
        if content_key in seen_content:
            continue
        seen_content.add(content_key)
        overlap = query_tokens & informative_tokens(content)
        if not overlap:
            continue
        query_anchors = query_tokens & CLINICAL_ANCHORS
        if query_anchors and not (overlap & query_anchors):
            continue
        if not query_anchors and len(query_tokens) >= 3 and len(overlap) < 2:
            continue
        candidates.append(
            FilteredRetrieval(
                document=document,
                distance=float(distance),
                lexical_score=len(overlap) / max(len(query_tokens), 1),
                matched_terms=tuple(sorted(overlap)),
            )
        )

    def sort_key(item: FilteredRetrieval) -> tuple[float, int, float]:
        metadata = getattr(item.document, "metadata", {}) or {}
        try:
            authority_tier = int(metadata.get("authority_tier", 3))
        except (TypeError, ValueError):
            authority_tier = 3
        authority_bonus = 0.20 if authority_tier == 1 else 0.0
        return (-(item.lexical_score + authority_bonus), authority_tier, item.distance)

    candidates.sort(key=sort_key)
    selected: list[FilteredRetrieval] = []
    source_counts: dict[str, int] = {}
    for candidate in candidates:
        metadata = getattr(candidate.document, "metadata", {}) or {}
        source = os.path.basename(str(metadata.get("source") or "unknown"))
        if source_counts.get(source, 0) >= max_per_source:
            continue
        source_counts[source] = source_counts.get(source, 0) + 1
        selected.append(candidate)
        if len(selected) >= limit:
            break
    return selected
