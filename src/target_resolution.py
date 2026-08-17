"""Deterministic, fail-closed target-person resolution for CureBot turns.

Resolves *which* profile(s) a chat message is about, using only the account's own
family metadata (names, `yakinlik` relationship, Turkish possessive
normalization). Design principles (see product spec / audit):

- STRUCTURED BEFORE LLM: identity is resolved here, not by the language model.
- FIVE SCOPES: a turn resolves to one of SELF, SINGLE (one member), MULTI (an
  explicit set of 2+ members), FAMILY (everyone), or UNRESOLVED (clarification).
- FAIL CLOSED: when a message clearly refers to people we cannot resolve with
  confidence, this NEVER silently falls back to the owner or the active profile.
  It returns ``needs_clarification=True`` with candidates.
- MULTI is additive and conservative: it only fires when the message explicitly
  names/relates 2+ distinct persons joined by a conjunction/comitative
  ("ben ve annem", "eşimle bana", "annemle babam"). A bare plural pronoun
  ("bize", "ikimize") with no explicit set is AMBIGUOUS -> clarification, unless
  the conversation already carries an explicit group target.
- CONTEXT CONTINUITY: when the message names nobody, the previously resolved
  target (single OR multi OR family, carried in conversation state) is kept.
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
# suffixes ("oğlumunki", "oğluma", "oğlunun", comitative "annemle") still resolve.
MESSAGE_RELATION_STEMS: dict[str, tuple[str, ...]] = {
    "son": ("oglum", "oglun", "oglan"),
    "daughter": ("kizim", "kizin"),
    "spouse": ("esim", "esin", "hanimim", "kocam", "karim"),
    "mother": ("annem", "annen"),
    "father": ("babam", "baban"),
    "sibling": ("kardesim", "kardesin", "abim", "ablam"),
}

# Gender-neutral child references ("çocuğum", "çocuğuma"...). A child is a member
# whose relationship category is son or daughter. Plural forms select all
# children; the singular selects the only child or asks which one.
CHILD_PLURAL_STEMS = ("cocuklar",)
CHILD_SINGULAR_STEMS = ("cocugum", "cocuguma", "cocugun", "cocuguna", "cocugu", "cocuguyla", "cocugumla")
CHILD_BARE = {"cocuk"}
CHILD_CATEGORIES = {"son", "daughter"}

OTHER_PRONOUN_STEMS = ("onun", "ona", "onu", "ondan", "onunki")

SELF_EXACT = {"ben", "bana", "beni", "kendim", "kendime", "kendi", "benimki"}
SELF_PREFIXES = ("benim", "kendim")
# Common Turkish first-person verb forms used in short nutrition questions.
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

# First-person-plural pronouns that imply a GROUP but do not say which people.
# These must never silently resolve to a single active profile. NOTE: bare
# "beraber"/"birlikte" are intentionally excluded — in Turkish they usually mean
# "together with [a food]" ("kahvaltıyla birlikte") and cause false positives;
# a real group is expressed with "biz/ikimiz" or by naming the people (-> MULTI).
AMBIGUOUS_GROUP_EXACT = {
    "biz", "bize", "bizi", "bizde", "bizce", "bizler",
    "ikimiz", "ikimize", "ikimizi", "ikimizde",
}
AMBIGUOUS_GROUP_PREFIXES = ("bizim", "ikimiz", "bizimle")

# Conjunction / comitative markers that link two person references into a set.
CONJUNCTION_TOKENS = {"ve", "ile", "hem", "ayrica"}

SELF_CANONICAL = "kendim"
MULTI_PREFIX = "multi:"


@dataclass(frozen=True)
class TargetResolution:
    target: str | None          # "kendim" | "aile" | member_id | "multi:a+b" when resolved; None when clarification
    target_label: str
    source: str
    needs_clarification: bool = False
    candidates: tuple[tuple[str, str], ...] = ()  # (member_id, ad)
    referenced_someone_else: bool = False
    reason: str = ""
    scope: str = ""             # self | single | multi | family | unresolved
    member_ids: tuple[str, ...] = ()  # canonical ids ("kendim" for the owner)


def multi_key(ids: list[str]) -> str:
    return MULTI_PREFIX + "+".join(sorted(set(ids)))


def parse_multi_key(key: str) -> list[str]:
    if not str(key or "").startswith(MULTI_PREFIX):
        return []
    return [part for part in key[len(MULTI_PREFIX):].split("+") if part]


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


def _mentions_child_plural(tokens: list[str]) -> bool:
    return any(token.startswith(stem) for token in tokens for stem in CHILD_PLURAL_STEMS)


def _mentions_child_singular(tokens: list[str]) -> bool:
    if _mentions_child_plural(tokens):
        return False
    return any(
        token in CHILD_BARE or any(token.startswith(stem) for stem in CHILD_SINGULAR_STEMS)
        for token in tokens
    )


def _mentions_ambiguous_group(tokens: list[str]) -> bool:
    return any(
        token in AMBIGUOUS_GROUP_EXACT or any(token.startswith(prefix) for prefix in AMBIGUOUS_GROUP_PREFIXES)
        for token in tokens
    )


def _children(members: list) -> list:
    return [member for member in members if relation_category(member.yakinlik) in CHILD_CATEGORIES]


def _name_match(name: str, tokens: list[str], text_norm: str) -> bool:
    name_norm = _norm(name).strip()
    if len(name_norm) < 2:
        return False
    if " " in name_norm:  # multi-word name
        return _word_present(name_norm, text_norm)
    return any(token == name_norm or (len(name_norm) >= 3 and token.startswith(name_norm)) for token in tokens)


def _name_matches(members: list, tokens: list[str], text_norm: str) -> list:
    return [member for member in members if _name_match(member.ad, tokens, text_norm)]


def _self_label(profile: KullaniciProfili) -> str:
    return profile.ana_kullanici.ad if profile.ana_kullanici else "Kendim"


def _label_for_id(profile: KullaniciProfili, canonical_id: str) -> str:
    if canonical_id == SELF_CANONICAL:
        return "Sen"
    member = next((item for item in (profile.aile_uyeleri or []) if item.id == canonical_id), None)
    return member.ad if member else canonical_id


# ---- Scoped constructors -----------------------------------------------------

def _self(profile: KullaniciProfili, source: str) -> TargetResolution:
    return TargetResolution(SELF_CANONICAL, _self_label(profile), source, scope="self", member_ids=(SELF_CANONICAL,))


def _single(member, source: str, referenced_other: bool = True) -> TargetResolution:
    return TargetResolution(
        member.id, member.ad, source, referenced_someone_else=referenced_other,
        scope="single", member_ids=(member.id,),
    )


def _family(source: str = "message_family") -> TargetResolution:
    return TargetResolution("aile", "Tüm aile", source, referenced_someone_else=True, scope="family")


def _multi(profile: KullaniciProfili, ids: list[str], source: str) -> TargetResolution:
    canonical = sorted(set(ids))
    label = " + ".join(_label_for_id(profile, cid) for cid in canonical)
    return TargetResolution(
        multi_key(canonical), label, source, referenced_someone_else=True,
        scope="multi", member_ids=tuple(canonical),
    )


def _clarify(source: str, candidates, reason: str) -> TargetResolution:
    return TargetResolution(
        None, "", source, needs_clarification=True,
        candidates=tuple(candidates), referenced_someone_else=True, reason=reason, scope="unresolved",
    )


def _hint_resolution(profile: KullaniciProfili, hint: str, source: str) -> TargetResolution:
    members = list(profile.aile_uyeleri or [])
    main = profile.ana_kullanici
    hint = (str(hint or "").strip() or "kendim")
    if hint == "aile" and members:
        return _family(source)
    if hint.startswith(MULTI_PREFIX):
        ids = parse_multi_key(hint)
        valid: list[str] = []
        for cid in ids:
            if cid == SELF_CANONICAL and main is not None:
                valid.append(SELF_CANONICAL)
            elif any(member.id == cid for member in members):
                valid.append(cid)
        if valid and len(valid) == len(ids) and len(valid) >= 2:
            return _multi(profile, valid, source)
        return _clarify(
            "stale_previous_target",
            tuple((member.id, member.ad) for member in members),
            "stale_previous_target",
        )
    if hint == "kendim" or (main is not None and hint == main.id):
        if main is None:
            return _clarify("unknown_hint", (), "unknown_hint")
        return TargetResolution(SELF_CANONICAL, _self_label(profile), source, scope="self", member_ids=(SELF_CANONICAL,))
    for member in members:
        if member.id == hint:
            return _single(member, source)
    return _clarify(
        "unknown_hint",
        tuple((member.id, member.ad) for member in members),
        "unknown_hint",
    )


# ---- Targeting vs. reference: dative / feedback / expansion ------------------
# A member appearing as the *recipient* of a request ("anneme öner", dative
# "-a/-e"; or "X için") is a TARGET REQUEST. The same member appearing as the
# *subject* of a statement ("annem bunu sevmez") is a REFERENCE/feedback and must
# not, on its own, change an existing family/multi conversation target.

DATIVE_RELATION_STEMS: dict[str, tuple[str, ...]] = {
    "son": ("ogluma", "ogluna"),
    "daughter": ("kizima", "kizina"),
    "spouse": ("esime", "esine", "hanimima", "kocama", "karima"),
    "mother": ("anneme", "annene"),
    "father": ("babama", "babana"),
    "sibling": ("kardesime", "kardesine", "abime", "ablama"),
}
DATIVE_CHILD_STEMS = ("cocuguma", "cocuguna")
DATIVE_CHILD_PLURAL_STEMS = ("cocuklarima", "cocuklarina")
SELF_DATIVE = {"bana", "kendime"}

# Preference / ability statements that mark a sentence as feedback, not a target
# request ("sevmez", "sevmiyor", "yiyemez", "istemiyor", "kullanmıyor", ...).
FEEDBACK_VERB_PREFIXES = (
    "sevm", "begenm", "yemiy", "yemez", "yiyem", "icmiy", "icmez", "icem",
    "istemi", "istem", "kullanmi", "kullanmaz", "yasak", "dokunuy",
)
CHILD_MAX_AGE = 18


def _has_conjunction(tokens: list[str]) -> bool:
    if any(token in CONJUNCTION_TOKENS for token in tokens):
        return True
    if (tokens.count("de") + tokens.count("da")) >= 2:  # "ben de annem de"
        return True
    for token in tokens:  # comitative "-le"/"-la" on a person token ("eşimle").
        if (token.endswith("le") or token.endswith("la")) and _is_person_token(token):
            return True
    return False


def _is_person_token(token: str) -> bool:
    if token in SELF_EXACT or any(token.startswith(prefix) for prefix in SELF_PREFIXES):
        return True
    for stems in MESSAGE_RELATION_STEMS.values():
        if any(token.startswith(stem) for stem in stems):
            return True
    if token in CHILD_BARE or any(token.startswith(stem) for stem in (*CHILD_SINGULAR_STEMS, *CHILD_PLURAL_STEMS)):
        return True
    return False


def _child_candidates(members: list) -> list:
    """Members who are the account's children: sons/daughters, plus a member with
    an unspecified relationship but a child's age (so a member stored as "diğer"
    is still reachable by "çocuğum" instead of silently failing)."""
    kids = []
    for member in members:
        category = relation_category(member.yakinlik)
        if category in CHILD_CATEGORIES:
            kids.append(member)
        elif category is None and (member.yas or 99) < CHILD_MAX_AGE:
            kids.append(member)
    return kids


def _dative_categories(tokens: list[str]) -> set[str]:
    detected: set[str] = set()
    for category, stems in DATIVE_RELATION_STEMS.items():
        if any(token.startswith(stem) for token in tokens for stem in stems):
            detected.add(category)
    return detected


def _dative_child_singular(tokens: list[str]) -> bool:
    return any(token.startswith(stem) for token in tokens for stem in DATIVE_CHILD_STEMS)


def _dative_child_plural(tokens: list[str]) -> bool:
    return any(token.startswith(stem) for token in tokens for stem in DATIVE_CHILD_PLURAL_STEMS)


def _dative_present(tokens: list[str]) -> bool:
    return bool(_dative_categories(tokens)) or _dative_child_singular(tokens) or _dative_child_plural(tokens) or any(
        token in SELF_DATIVE for token in tokens
    )


def _explicit_target_request(tokens: list[str]) -> bool:
    if "icin" in tokens or "gore" in tokens:
        return True
    if any(token in {"sadece", "yalniz", "yalnizca"} for token in tokens):
        return True
    return _dative_present(tokens)


def _has_feedback_verb(tokens: list[str]) -> bool:
    return any(token.startswith(prefix) for token in tokens for prefix in FEEDBACK_VERB_PREFIXES)


def _is_expansion(tokens: list[str]) -> bool:
    also = ("da" in tokens) or ("de" in tokens)
    eats = any(token.startswith("yiy") for token in tokens) or any(
        token in {"yesin", "yesek", "yiyecek"} for token in tokens
    )
    return also and eats


def _scope_of(target: str | None) -> str:
    target = str(target or "")
    if not target:
        return "none"
    if target == "aile":
        return "family"
    if target.startswith(MULTI_PREFIX):
        return "multi"
    if target == "kendim":
        return "self"
    return "single"


def _current_member_ids(profile: KullaniciProfili, target: str | None) -> list[str]:
    target = str(target or "")
    if target == "kendim":
        return [SELF_CANONICAL]
    if target.startswith(MULTI_PREFIX):
        return parse_multi_key(target)
    if any(member.id == target for member in (profile.aile_uyeleri or [])):
        return [target]
    return []


def _collect_person_ids(
    profile: KullaniciProfili,
    tokens: list[str],
    text: str,
    detected: set[str],
    child_singular: bool,
    child_plural: bool,
) -> tuple[list[str], bool, list[tuple[str, str]]]:
    """Resolve every explicit person reference to canonical ids. Returns
    (ids, ambiguous, candidates)."""
    members = list(profile.aile_uyeleri or [])
    ids: list[str] = []
    candidates: list[tuple[str, str]] = []
    ambiguous = False

    def add(cid: str) -> None:
        if cid not in ids:
            ids.append(cid)

    if _has_self_reference(tokens):
        add(SELF_CANONICAL)
    for category in detected:
        matches = [member for member in members if relation_category(member.yakinlik) == category]
        if len(matches) == 1:
            add(matches[0].id)
        elif len(matches) > 1:
            ambiguous = True
            candidates.extend((member.id, member.ad) for member in matches)
        else:
            ambiguous = True
    if child_plural:
        kids = _child_candidates(members)
        if kids:
            for kid in kids:
                add(kid.id)
        else:
            ambiguous = True
    elif child_singular:
        kids = _child_candidates(members)
        if len(kids) == 1:
            add(kids[0].id)
        elif len(kids) > 1:
            ambiguous = True
            candidates.extend((kid.id, kid.ad) for kid in kids)
        else:
            ambiguous = True
    for member in members:
        if _name_match(member.ad, tokens, text):
            add(member.id)
    return ids, ambiguous, candidates


def _resolve_multi(
    profile: KullaniciProfili,
    tokens: list[str],
    text: str,
    detected: set[str],
    child_singular: bool,
    child_plural: bool,
) -> TargetResolution | None:
    """MULTI/clarification when the message names 2+ persons joined by a
    conjunction; otherwise None (single logic)."""
    if not _has_conjunction(tokens):
        return None
    ids, ambiguous, candidates = _collect_person_ids(profile, tokens, text, detected, child_singular, child_plural)
    if len(ids) >= 2 and not ambiguous:
        return _multi(profile, ids, "message_multi")
    if ambiguous and (len(ids) >= 1 or candidates):
        return _clarify("message_multi", candidates, "multi_ambiguous_member")
    return None


def _expand_current_target(
    profile: KullaniciProfili,
    current_target: str,
    tokens: list[str],
    text: str,
    detected: set[str],
    child_singular: bool,
    child_plural: bool,
) -> TargetResolution | None:
    """"X da yiyecek" while a single/self target is active -> add X to the set."""
    ids, ambiguous, candidates = _collect_person_ids(profile, tokens, text, detected, child_singular, child_plural)
    if ambiguous:
        return _clarify("expansion", candidates, "multiple_children" if candidates else "ambiguous_group")
    combined = list(dict.fromkeys([*_current_member_ids(profile, current_target), *ids]))
    if len(combined) >= 2:
        return _multi(profile, combined, "expansion")
    return None


def resolve_target_from_message(
    profile: KullaniciProfili,
    message: str,
    client_hint: str = "kendim",
    previous_target: str | None = None,
) -> TargetResolution:
    """Resolve the target profile(s) for one chat turn. Fail-closed on ambiguity."""
    members = list(profile.aile_uyeleri or [])
    main = profile.ana_kullanici
    text = _norm(message)
    tokens = _tokens(text)

    # 1) Explicit family-wide reference.
    if members and any(term in text for term in FAMILY_TERMS):
        return _family()

    detected_all = _detected_relation_categories(tokens)
    child_singular_all = _mentions_child_singular(tokens)
    child_plural_all = _mentions_child_plural(tokens)
    name_hits = _name_matches(members, tokens, text)
    owner_named = bool(main is not None and _name_match(main.ad, tokens, text))
    member_ref_present = bool(detected_all) or child_singular_all or child_plural_all or bool(name_hits) or owner_named

    current_target = previous_target or client_hint
    current_scope = _scope_of(current_target)
    explicit_request = _explicit_target_request(tokens)

    # 1.5) MEMBER REFERENCE INSIDE THE CURRENT TARGET (not a switch). A feedback /
    #      preference statement about a member ("çocuk bunu sevmez", "eşim tuzlu
    #      sevmiyor") while a family/multi conversation is active keeps that target
    #      instead of narrowing to the mentioned member. Only an explicit request
    #      ("sadece çocuğuma", "... için") switches.
    if (
        current_scope in {"family", "multi"}
        and member_ref_present
        and _has_feedback_verb(tokens)
        and not explicit_request
    ):
        kept = _hint_resolution(profile, current_target, "continuity")
        if not kept.needs_clarification:
            return kept

    # When a sentence mixes feedback about one member with an explicit dative
    # request for another ("annem sevmedi, sadece babama öner"), target only the
    # dative-marked person and ignore the nominative feedback subject. Without a
    # feedback verb, every reference (incl. comitative "eşimle") is a real target.
    if _dative_present(tokens) and _has_feedback_verb(tokens):
        detected = _dative_categories(tokens)
        child_singular = _dative_child_singular(tokens)
        child_plural = _dative_child_plural(tokens)
    else:
        detected = detected_all
        child_singular = child_singular_all
        child_plural = child_plural_all

    # 2) Explicit MULTI set (2+ persons joined by a conjunction).
    multi = _resolve_multi(profile, tokens, text, detected, child_singular, child_plural)
    if multi is not None:
        return multi

    # 2.5) Expansion of the active single/self target ("çocuk da yiyecek").
    if current_scope in {"self", "single"} and member_ref_present and _is_expansion(tokens) and not explicit_request:
        expanded = _expand_current_target(
            profile, current_target, tokens, text, detected_all, child_singular_all, child_plural_all
        )
        if expanded is not None:
            return expanded

    # 3) Explicit name match. All matches are collected: duplicates ask instead
    #    of silently picking the first. A name whose stored relationship disagrees
    #    with a relationship also present in the message asks (NAME != RELATIONSHIP).
    name_matches = _name_matches(members, tokens, text)
    if name_matches:
        if len(name_matches) > 1:
            return _clarify("message_name", ((m.id, m.ad) for m in name_matches), "duplicate_name")
        member = name_matches[0]
        if detected and relation_category(member.yakinlik) not in detected:
            return _clarify("name_relationship_conflict", ((member.id, member.ad),), "name_relationship_conflict")
        return _single(member, "message_name")
    if main is not None and _name_match(main.ad, tokens, text):
        if detected:
            return _clarify("name_relationship_conflict", (), "name_relationship_conflict_self")
        return TargetResolution("kendim", main.ad, "message_name", scope="self", member_ids=(SELF_CANONICAL,))

    # 4) Gender-neutral child reference ("çocuğum", "çocuklar").
    if child_singular or child_plural:
        kids = _child_candidates(members)
        if not kids:
            return _clarify(
                "message_relationship",
                ((m.id, m.ad) for m in members),
                "child_without_metadata" if members else "child_without_family",
            )
        if child_plural:
            if len(kids) == 1:
                return _single(kids[0], "message_relationship")
            return _multi(profile, [kid.id for kid in kids], "message_relationship")
        if len(kids) == 1:
            return _single(kids[0], "message_relationship")
        return _clarify("message_relationship", ((k.id, k.ad) for k in kids), "multiple_children")

    # 5) Relationship reference (before generic self so "oğluma ... bana"
    #    resolves to the son, not the owner).
    if detected:
        matches = [m for m in members if relation_category(m.yakinlik) in detected]
        if len(matches) == 1:
            return _single(matches[0], "message_relationship")
        if len(matches) > 1:
            return _clarify("message_relationship", ((m.id, m.ad) for m in matches), "multiple_relationship_matches")
        return _clarify(
            "message_relationship",
            ((m.id, m.ad) for m in members),
            "relationship_without_metadata" if members else "relationship_without_family",
        )

    # 6) Explicit self reference switches back to the owner.
    if _has_self_reference(tokens):
        return _self(profile, "message_self")

    # 7) A third-person pronoun inherits only a valid, previously resolved
    #    non-owner target. Without such an antecedent we ask.
    if _has_other_pronoun(tokens):
        if previous_target and previous_target not in {"kendim", "aile"}:
            pronoun = _hint_resolution(profile, previous_target, "pronoun")
            if not pronoun.needs_clarification:
                return pronoun
        return _clarify("pronoun_ambiguous", ((m.id, m.ad) for m in members), "pronoun_without_antecedent")

    # 8) Turkish often omits the subject pronoun; a first-person verb ("acıktım")
    #    is an explicit switch to the speaker.
    if _has_implicit_self_reference(tokens):
        return _self(profile, "message_self_implicit")

    # 9) Bare plural group ("bize", "ikimize") with no explicit set: honor an
    #    explicit group already in context — a prior group target OR an explicit
    #    group selection in the client hint ("aile"/multi). A single active profile
    #    is NOT a group, so ASK rather than silently using it. Never a silent single.
    if _mentions_ambiguous_group(tokens):
        for candidate, candidate_source in ((previous_target, "continuity"), (client_hint, "client_hint")):
            if candidate and (candidate == "aile" or candidate.startswith(MULTI_PREFIX)):
                resolved = _hint_resolution(profile, candidate, candidate_source)
                if not resolved.needs_clarification:
                    return resolved
        return _clarify("ambiguous_group", ((m.id, m.ad) for m in members), "ambiguous_group")

    # 10) No person reference: keep the previous target (continuity), never a
    #     silent owner fallback. Fall to the client hint only with no prior target.
    if previous_target:
        continuity = _hint_resolution(profile, previous_target, "continuity")
        if not continuity.needs_clarification:
            return continuity
        return _clarify("stale_previous_target", ((m.id, m.ad) for m in members), "stale_previous_target")
    return _hint_resolution(profile, client_hint, "client_hint")


def clarification_prompt(resolution: TargetResolution) -> str:
    """User-facing, Turkish clarification when the target is ambiguous."""
    if resolution.reason in {"ambiguous_group", "multi_ambiguous_member"}:
        names = [name for _id, name in resolution.candidates if str(name or "").strip()]
        if resolution.reason == "ambiguous_group":
            return (
                "Bunu kimler için değerlendireyim? Yalnız senin için mi, seçtiğin birkaç kişi için mi, "
                "yoksa tüm aile için mi? Doğru kişileri seçmem sağlık bilgilerini karıştırmamam için önemli."
            )
        if names:
            listed = ", ".join(names)
            return f"Birden fazla profil eşleşiyor ({listed}). Hangi kişileri kastediyorsun?"
        return "Kimleri kastettiğini tam çıkaramadım. İlgili profilleri tek tek söyler misin?"
    if resolution.reason == "duplicate_name":
        names = [name for _id, name in resolution.candidates if str(name or "").strip()]
        listed = ", ".join(names) if names else "aynı isimli profiller"
        return (
            f"Aynı isimde birden fazla profil var ({listed}). Hangi profili kastediyorsun? "
            "Doğru kişiyi seçmem sağlık bilgilerini karıştırmamam için önemli."
        )
    if resolution.reason == "multiple_children":
        names = [name for _id, name in resolution.candidates if str(name or "").strip()]
        listed = (", ".join(names[:-1]) + " mi, " + names[-1] + " mi") if len(names) > 1 else ((names[0] + " için mi") if names else "")
        return f"Hangi çocuğun için değerlendireyim? {listed}?".strip()
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
