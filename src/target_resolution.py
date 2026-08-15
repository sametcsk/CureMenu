"""Deterministic, fail-closed target-person resolution for CureBot turns.

Resolves *which* profile a chat message is about, using only the account's own
family metadata (names, `yakinlik` relationship, Turkish possessive
normalization). Design principles (see product spec):

- STRUCTURED BEFORE LLM: identity is resolved here, not by the language model.
- FAIL CLOSED: when a message clearly refers to someone other than the account
  owner but the target cannot be resolved with confidence, this NEVER silently
  falls back to the owner. It returns ``needs_clarification=True`` with candidates.
- CONTEXT CONTINUITY: when the message names nobody, the previously resolved
  target (carried in conversation state) is kept, so a follow-up like
  "peki ayran?" stays on the same person. Only an explicit self / other-person /
  family reference switches the subject.
- The client-provided dropdown hint is used only when there is neither a message
  reference nor a previous target.
"""
from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass

from src.models import KullaniciProfili


def _norm(value: str) -> str:
    text = unicodedata.normalize("NFKD", str(value or "").casefold())
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    return text.replace("ı", "i")


def _tokens(text_norm: str) -> list[str]:
    return re.findall(r"[a-z0-9]+", text_norm)


# Stored `yakinlik` value -> relationship category. Ordered by specificity so a
# value like "kız kardeş" is classified as sibling, not daughter.
RELATION_CATEGORY_ALIASES: dict[str, tuple[str, ...]] = {
    "spouse": ("es", "spouse", "hanim", "koca", "kari", "hayat arkadasi"),
    "mother": ("anne", "mother", "valide"),
    "father": ("baba", "father", "peder"),
    "sibling": ("kardes", "sibling", "abi", "abla"),
    "son": ("ogul", "erkek cocuk", "son"),
    "daughter": ("kiz cocuk", "kiz", "daughter"),
}

# Token prefixes (stems) in the speaker's possessive forms, including the common
# "-n" typo for "-m" ("oğlun" for "oğlum"). Matched with str.startswith so Turkish
# suffixes ("oğlumunki", "oğluma", "oğlunun") still resolve.
MESSAGE_RELATION_STEMS: dict[str, tuple[str, ...]] = {
    "son": ("oglum", "oglun", "oglan"),
    "daughter": ("kizim", "kizin"),
    "spouse": ("esim", "esin", "hanimim", "kocam", "karim"),
    "mother": ("annem", "annen"),
    "father": ("babam", "baban"),
    "sibling": ("kardesim", "kardesin", "abim", "ablam"),
}

OTHER_PRONOUN_STEMS = ("onun", "ona", "onu", "ondan", "onunki")

SELF_EXACT = {"ben", "bana", "beni", "kendim", "kendime", "kendi", "benimki"}
SELF_PREFIXES = ("benim", "kendim")
# Common Turkish first-person verb forms used in short nutrition questions.
# These are message-local linguistic signals; they do not mutate or persist the
# selected target. Relationship/name references still win earlier in the
# resolver, and third-person pronouns are handled before this implicit signal.
IMPLICIT_SELF_FORMS = {
    "aciktim", "yemeliyim", "yiyeyim", "yiyim", "yesem",
    "yiyebilirim", "icebilirim", "istiyorum", "istemiyorum",
    "seviyorum", "sevmiyorum", "kullaniyorum", "kullandigim",
    "yedim", "ictim", "hazirladim", "yukledim",
}
IMPLICIT_SELF_POSSESSIVE_STEMS = (
    "planim", "tahlilim", "tahlillerim", "profilim", "alerjim",
    "hastaligim", "ilacim", "ilaclarim", "ogunum", "menum", "buzdolabim",
)
FAMILY_TERMS = ("tum aile", "butun aile", "hepimiz", "ailecek", "hep birlikte", "tum ailem", "butun ailem")


@dataclass(frozen=True)
class TargetResolution:
    target: str | None          # "kendim" | "aile" | member_id when resolved; None when clarification needed
    target_label: str
    source: str                 # message_family | message_name | message_relationship | message_self | single_member | continuity | client_hint | default_self
    needs_clarification: bool = False
    candidates: tuple[tuple[str, str], ...] = ()  # (member_id, ad)
    referenced_someone_else: bool = False
    reason: str = ""


def _word_present(needle: str, haystack_norm: str) -> bool:
    needle = needle.strip()
    if not needle:
        return False
    return re.search(rf"(?<![a-z0-9]){re.escape(needle)}(?![a-z0-9])", haystack_norm) is not None


def relation_category(yakinlik: str | None) -> str | None:
    """Map a stored `yakinlik` value to a canonical relationship category."""
    if not yakinlik:
        return None
    value = _norm(yakinlik)
    # Word-boundary matching only: a loose substring test would misclassify
    # "kız kardeş" (sibling) as spouse because "es" is a substring of "kardes".
    for category, aliases in RELATION_CATEGORY_ALIASES.items():
        if any(_word_present(alias, value) for alias in aliases):
            return category
    return None


def _detected_relation_categories(tokens: list[str]) -> set[str]:
    detected: set[str] = set()
    for category, stems in MESSAGE_RELATION_STEMS.items():
        if any(token.startswith(stem) for token in tokens for stem in stems):
            detected.add(category)
    return detected


def _has_self_reference(tokens: list[str]) -> bool:
    for token in tokens:
        if token in SELF_EXACT:
            return True
        if any(token.startswith(prefix) for prefix in SELF_PREFIXES):
            return True
    return False


def _has_other_pronoun(tokens: list[str]) -> bool:
    return any(token.startswith(stem) for token in tokens for stem in OTHER_PRONOUN_STEMS)


def _has_implicit_self_reference(tokens: list[str]) -> bool:
    return any(
        token in IMPLICIT_SELF_FORMS
        or any(token.startswith(stem) for stem in IMPLICIT_SELF_POSSESSIVE_STEMS)
        for token in tokens
    )


def _name_match(name: str, tokens: list[str], text_norm: str) -> bool:
    name_norm = _norm(name).strip()
    if len(name_norm) < 2:
        return False
    if " " in name_norm:  # multi-word name
        return _word_present(name_norm, text_norm)
    return any(token == name_norm or (len(name_norm) >= 3 and token.startswith(name_norm)) for token in tokens)


def _self_label(profile: KullaniciProfili) -> str:
    return profile.ana_kullanici.ad if profile.ana_kullanici else "Kendim"


def _hint_resolution(profile: KullaniciProfili, hint: str, source: str) -> TargetResolution:
    members = list(profile.aile_uyeleri or [])
    main = profile.ana_kullanici
    hint = (str(hint or "").strip() or "kendim")
    if hint == "aile" and members:
        return TargetResolution("aile", "Tüm aile", source)
    if hint == "kendim" or (main is not None and hint == main.id):
        return TargetResolution("kendim", _self_label(profile), source)
    for member in members:
        if member.id == hint:
            return TargetResolution(member.id, member.ad, source)
    return TargetResolution(
        None,
        "",
        "unknown_hint",
        needs_clarification=True,
        candidates=tuple((member.id, member.ad) for member in members),
        referenced_someone_else=True,
        reason="unknown_hint",
    )


def resolve_target_from_message(
    profile: KullaniciProfili,
    message: str,
    client_hint: str = "kendim",
    previous_target: str | None = None,
) -> TargetResolution:
    """Resolve the target profile for one chat turn. Fail-closed on ambiguity."""
    members = list(profile.aile_uyeleri or [])
    main = profile.ana_kullanici
    text = _norm(message)
    tokens = _tokens(text)

    # 1) Explicit family-wide reference.
    if members and any(term in text for term in FAMILY_TERMS):
        return TargetResolution("aile", "Tüm aile", "message_family")

    detected = _detected_relation_categories(tokens)

    # 2) Explicit name match (family member first, then the account owner). If the
    #    message ALSO carries a relationship that disagrees with the named person's
    #    stored yakinlik, do not guess — ask for clarification (NAME != RELATIONSHIP).
    for member in members:
        if _name_match(member.ad, tokens, text):
            if detected and relation_category(member.yakinlik) not in detected:
                return TargetResolution(
                    None, "", "name_relationship_conflict", needs_clarification=True,
                    candidates=((member.id, member.ad),), referenced_someone_else=True,
                    reason="name_relationship_conflict",
                )
            return TargetResolution(member.id, member.ad, "message_name")
    if main is not None and _name_match(main.ad, tokens, text):
        if detected:
            return TargetResolution(
                None, "", "name_relationship_conflict", needs_clarification=True,
                candidates=(), referenced_someone_else=True, reason="name_relationship_conflict_self",
            )
        return TargetResolution("kendim", main.ad, "message_name")

    # 3) Relationship reference (before generic self so "oğluma ... bana"
    #    resolves to the son, not the owner).
    if detected:
        matches = [m for m in members if relation_category(m.yakinlik) in detected]
        if len(matches) == 1:
            return TargetResolution(matches[0].id, matches[0].ad, "message_relationship", referenced_someone_else=True)
        if len(matches) > 1:
            return TargetResolution(
                None, "", "message_relationship", needs_clarification=True,
                candidates=tuple((m.id, m.ad) for m in matches),
                referenced_someone_else=True, reason="multiple_relationship_matches",
            )
        return TargetResolution(
            None, "", "message_relationship", needs_clarification=True,
            candidates=tuple((m.id, m.ad) for m in members),
            referenced_someone_else=True,
            reason="relationship_without_metadata" if members else "relationship_without_family",
        )

    # 4) Explicit self reference switches back to the owner.
    if _has_self_reference(tokens):
        return TargetResolution("kendim", _self_label(profile), "message_self")

    # 5) A third-person pronoun inherits only a valid, previously resolved
    #    non-owner target. Without such an antecedent we must ask instead of
    #    guessing which family member the user meant.
    if _has_other_pronoun(tokens):
        if previous_target and previous_target not in {"kendim", "aile"}:
            pronoun = _hint_resolution(profile, previous_target, "pronoun")
            if not pronoun.needs_clarification:
                return pronoun
        return TargetResolution(
            None,
            "",
            "pronoun_ambiguous",
            needs_clarification=True,
            candidates=tuple((member.id, member.ad) for member in members),
            referenced_someone_else=True,
            reason="pronoun_without_antecedent",
        )

    # 6) Turkish often omits the subject pronoun. A first-person verb such as
    #    "acıktım" or "ne yemeliyim" is therefore an explicit semantic switch
    #    to the speaker even when the previous turn concerned a family member.
    if _has_implicit_self_reference(tokens):
        return TargetResolution("kendim", _self_label(profile), "message_self_implicit")

    # 7) No person reference: keep the previous target (continuity), never a
    #    silent owner fallback. Only fall to the client hint when there is no
    #    conversation target yet.
    if previous_target:
        continuity = _hint_resolution(profile, previous_target, "continuity")
        if not continuity.needs_clarification:  # previous target still valid
            return continuity
        return TargetResolution(
            None,
            "",
            "stale_previous_target",
            needs_clarification=True,
            candidates=tuple((member.id, member.ad) for member in members),
            referenced_someone_else=True,
            reason="stale_previous_target",
        )
    return _hint_resolution(profile, client_hint, "client_hint")


def clarification_prompt(resolution: TargetResolution) -> str:
    """User-facing, Turkish clarification when the target is ambiguous."""
    names = [name for _id, name in resolution.candidates if str(name or "").strip()]
    if names:
        listed = (", ".join(names[:-1]) + " mi, " + names[-1] + " mi") if len(names) > 1 else (names[0] + " için mi")
        return (
            f"Bunu kimin için soruyorsun? {listed}? "
            "Doğru kişiyi seçmem, sağlık bilgilerini karıştırmamam için önemli."
        )
    return (
        "Bunu kimin için soruyorsun: kendin için mi, yoksa bir aile üyesi için mi? "
        "Aile üyesi ise profil bilgilerini eklersen ona göre değerlendirebilirim."
    )
