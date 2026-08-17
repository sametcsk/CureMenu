"""Structured multi-target resolution (SELF / SINGLE / MULTI / FAMILY / AMBIGUOUS).

All deterministic, LLM-free. Covers the audit follow-up: ambiguous plurals never
fall silently to a single profile, gender-neutral "çocuğum" resolves, duplicate
names ask, and explicit sets ("ben ve annem") become a MULTI scope whose snapshot
unions ONLY the referenced members. Example names are fixtures only.
"""
import pytest

from src.models import AileUyesi, Cinsiyet, KullaniciProfili
from src.profile_context import resolve_profile_snapshot_from_profile
from src.routers.chat import _profile_conflict_answer
from src.target_resolution import (
    multi_key,
    parse_multi_key,
    resolve_target_from_message,
)


def _member(mid, ad, yakinlik, cinsiyet=Cinsiyet.KADIN, yas=30, alerjiler=None, hastaliklar=None):
    return AileUyesi(
        id=mid, ad=ad, yas=yas, cinsiyet=cinsiyet, yakinlik=yakinlik,
        alerjiler=alerjiler or [], hastaliklar=hastaliklar or [],
    )


def _owner(alerjiler=None, hastaliklar=None):
    return AileUyesi(
        id="owner-1", ad="Ayşe", yas=45, cinsiyet=Cinsiyet.KADIN,
        alerjiler=alerjiler or [], hastaliklar=hastaliklar or [],
    )


def _profile(members, owner=None):
    return KullaniciProfili(ana_kullanici=owner or _owner(), aile_uyeleri=list(members))


# Standard household used across many cases.
def _household():
    return _profile(
        [
            _member("anne-1", "Fatma", "anne", hastaliklar=["diyabet"]),
            _member("baba-1", "Kemal", "baba", cinsiyet=Cinsiyet.ERKEK, hastaliklar=["hipertansiyon"]),
            _member("ogul-1", "Mert", "ogul", cinsiyet=Cinsiyet.ERKEK, yas=10, alerjiler=["yer fıstığı"]),
        ]
    )


def _r(profile, message, hint="kendim", previous=None):
    return resolve_target_from_message(profile, message, hint, previous)


# ---- SELF / SINGLE / FAMILY preserved ---------------------------------------
def test_self_direct():
    assert _r(_household(), "şimdi bana öner").scope == "self"


@pytest.mark.parametrize("message,expected_scope,expected_target", [
    ("anneme yemek öner", "single", "anne-1"),
    ("babama öner", "single", "baba-1"),
    ("oğluma öner", "single", "ogul-1"),
    ("Mert için öner", "single", "ogul-1"),
    ("bana öner", "self", "kendim"),
    ("benim için ne olur", "self", "kendim"),
])
def test_single_and_self_preserved(message, expected_scope, expected_target):
    res = _r(_household(), message)
    assert res.scope == expected_scope
    assert res.target == expected_target
    assert res.needs_clarification is False


@pytest.mark.parametrize("message", [
    "hepimize akşam yemeği öner",
    "tüm aile için ne pişireyim",
    "ailecek ne yiyebiliriz",
    "hep birlikte ne yesek",
])
def test_family_terms_stay_family(message):
    res = _r(_household(), message)
    assert res.scope == "family"
    assert res.target == "aile"
    assert res.needs_clarification is False


# ---- MULTI (explicit set) ----------------------------------------------------
@pytest.mark.parametrize("message,expected_ids", [
    ("ben ve annem yiyebilir miyiz", {"kendim", "anne-1"}),
    ("bana ve anneme uygun olsun", {"kendim", "anne-1"}),
    ("ben de annem de yiyebilir miyiz", {"kendim", "anne-1"}),
    ("annemle babam için öner", {"anne-1", "baba-1"}),
    ("annem ve babam ve ben yiyeceğiz", {"kendim", "anne-1", "baba-1"}),
])
def test_multi_detection_basic(message, expected_ids):
    res = _r(_household(), message)
    assert res.scope == "multi"
    assert set(res.member_ids) == expected_ids
    assert res.target.startswith("multi:")
    assert res.needs_clarification is False


def test_multi_with_spouse_excludes_others():
    prof = _profile([
        _member("es-1", "Deniz", "es", cinsiyet=Cinsiyet.ERKEK, hastaliklar=["hipertansiyon"]),
        _member("ogul-1", "Mert", "ogul", cinsiyet=Cinsiyet.ERKEK, alerjiler=["süt"]),
    ])
    res = _r(prof, "eşimle bana bir şey öner")
    assert res.scope == "multi"
    assert set(res.member_ids) == {"kendim", "es-1"}


def test_multi_names():
    prof = _profile([
        _member("ali-1", "Ali", "ogul", cinsiyet=Cinsiyet.ERKEK),
        _member("ayse-2", "Ayşen", "kiz"),
    ])
    res = _r(prof, "Ali ve Ayşen için öner")
    assert res.scope == "multi"
    assert set(res.member_ids) == {"ali-1", "ayse-2"}


def test_multi_self_plus_child():
    prof = _profile([_member("ogul-1", "Mert", "ogul", cinsiyet=Cinsiyet.ERKEK, alerjiler=["süt"])])
    res = _r(prof, "bana ve çocuğuma uygun olsun")
    assert res.scope == "multi"
    assert set(res.member_ids) == {"kendim", "ogul-1"}


def test_multi_order_independent_key_and_resolution():
    prof = _household()
    a = _r(prof, "annemle bana öner")
    b = _r(prof, "bana ve anneme öner")
    assert a.target == b.target  # order-independent canonical key
    assert multi_key(["anne-1", "kendim"]) == multi_key(["kendim", "anne-1"])
    assert parse_multi_key(a.target) == sorted({"kendim", "anne-1"})


# ---- AMBIGUOUS GROUP (bize / ikimize) ---------------------------------------
@pytest.mark.parametrize("message", [
    "bize yemek öner",
    "bizim için bir şey öner",
    "ikimize uygun olsun",
    "ikimiz için ne olur",
    "bize de uygun olsun",
])
def test_ambiguous_group_asks_clarification(message):
    res = _r(_household(), message)
    assert res.needs_clarification is True
    assert res.target is None
    assert res.scope == "unresolved"
    assert res.reason == "ambiguous_group"


def test_bare_together_word_is_not_treated_as_group():
    # "birlikte"/"beraber" alone (e.g. "food together with breakfast") must NOT
    # hijack the turn into a group clarification.
    res = _r(_household(), "levotiroksini kahvaltıyla birlikte alabilir miyim", hint="kendim")
    assert res.needs_clarification is False
    assert res.scope == "self"


def test_ambiguous_group_never_silently_uses_active_profile():
    # Even with a client hint pointing at a member, a bare "bize" must NOT resolve.
    res = _r(_household(), "bize yemek öner", hint="ogul-1")
    assert res.needs_clarification is True


def test_ambiguous_group_continues_prior_group_target():
    prof = _household()
    prior = multi_key(["kendim", "anne-1"])
    res = _r(prof, "ikimize de uygun olsun", previous=prior)
    assert res.scope == "multi"
    assert set(res.member_ids) == {"kendim", "anne-1"}
    assert res.source == "continuity"


def test_ambiguous_group_continues_family_target():
    res = _r(_household(), "bize de öner", previous="aile")
    assert res.scope == "family"
    assert res.source == "continuity"


# ---- CHILD (çocuğum / çocuklar) ---------------------------------------------
def test_single_child_resolves():
    prof = _profile([_member("ogul-1", "Mert", "ogul", cinsiyet=Cinsiyet.ERKEK, alerjiler=["süt"])])
    for message in ("çocuğuma yemek öner", "çocuğum için ne olur", "çocuğuma da uygun olsun"):
        res = _r(prof, message)
        assert res.scope == "single", message
        assert res.target == "ogul-1", message


def test_multiple_children_ask_clarification():
    prof = _profile([
        _member("ogul-1", "Mert", "ogul", cinsiyet=Cinsiyet.ERKEK),
        _member("kiz-1", "Elif", "kiz"),
    ])
    res = _r(prof, "çocuğuma yemek öner")
    assert res.needs_clarification is True
    assert res.reason == "multiple_children"
    assert {c[0] for c in res.candidates} == {"ogul-1", "kiz-1"}


def test_plural_children_selects_all():
    prof = _profile([
        _member("ogul-1", "Mert", "ogul", cinsiyet=Cinsiyet.ERKEK),
        _member("kiz-1", "Elif", "kiz"),
    ])
    res = _r(prof, "çocuklara yemek öner")
    assert res.scope == "multi"
    assert set(res.member_ids) == {"ogul-1", "kiz-1"}


def test_child_without_any_child_asks():
    prof = _profile([_member("anne-1", "Fatma", "anne")])
    res = _r(prof, "çocuğuma öner")
    assert res.needs_clarification is True


def test_child_does_not_break_owner_default():
    # "çocuğuma da uygun olsun" must NOT silently fall to the owner.
    prof = _profile([_member("ogul-1", "Mert", "ogul", cinsiyet=Cinsiyet.ERKEK)])
    res = _r(prof, "çocuğuma da uygun olsun", hint="kendim")
    assert res.target == "ogul-1"


# ---- DUPLICATE NAMES ---------------------------------------------------------
def test_duplicate_names_ask_clarification():
    prof = _profile([
        _member("ali-1", "Ali", "ogul", cinsiyet=Cinsiyet.ERKEK),
        _member("ali-2", "Ali", "kardes", cinsiyet=Cinsiyet.ERKEK),
    ])
    res = _r(prof, "Ali için öner")
    assert res.needs_clarification is True
    assert res.reason == "duplicate_name"
    assert {c[0] for c in res.candidates} == {"ali-1", "ali-2"}


def test_single_name_still_resolves():
    prof = _profile([_member("ali-1", "Ali", "ogul", cinsiyet=Cinsiyet.ERKEK)])
    res = _r(prof, "Ali için öner")
    assert res.scope == "single"
    assert res.target == "ali-1"


# ---- SNAPSHOT: multi unions only referenced members --------------------------
def test_multi_snapshot_unions_only_referenced_members():
    prof = _profile([
        _member("es-1", "Deniz", "es", cinsiyet=Cinsiyet.ERKEK, hastaliklar=["hipertansiyon"]),
        _member("ogul-1", "Mert", "ogul", cinsiyet=Cinsiyet.ERKEK, alerjiler=["süt", "yer fıstığı"]),
    ], owner=_owner(hastaliklar=["diyabet"]))
    res = _r(prof, "bana ve eşime öner")
    snap = resolve_profile_snapshot_from_profile("acct", prof, res.target)
    assert snap.target_scope == "multi"
    assert set(snap.diseases) == {"diyabet", "hipertansiyon"}
    # The child was NOT referenced -> its allergies must not appear.
    assert "süt" not in snap.allergies
    assert "yer fıstığı" not in snap.allergies


def test_family_snapshot_unions_everyone():
    prof = _profile([
        _member("es-1", "Deniz", "es", cinsiyet=Cinsiyet.ERKEK, hastaliklar=["hipertansiyon"]),
        _member("ogul-1", "Mert", "ogul", cinsiyet=Cinsiyet.ERKEK, alerjiler=["süt", "yer fıstığı"]),
    ], owner=_owner(hastaliklar=["diyabet"]))
    snap = resolve_profile_snapshot_from_profile("acct", prof, "aile")
    assert {"diyabet", "hipertansiyon"} <= set(snap.diseases)
    assert {"süt", "yer fıstığı"} <= set(snap.allergies)


def test_multi_snapshot_fingerprint_is_order_independent():
    prof = _household()
    a = resolve_profile_snapshot_from_profile("acct", prof, multi_key(["kendim", "anne-1"]))
    b = resolve_profile_snapshot_from_profile("acct", prof, multi_key(["anne-1", "kendim"]))
    assert a.profile_fingerprint == b.profile_fingerprint
    assert a.target_key == b.target_key


def test_multi_summary_has_per_person_breakdown():
    prof = _profile([_member("anne-1", "Fatma", "anne", hastaliklar=["diyabet"])],
                    owner=_owner(hastaliklar=["çölyak"]))
    snap = resolve_profile_snapshot_from_profile("acct", prof, multi_key(["kendim", "anne-1"]))
    assert "SEÇİLİ KİŞİLER" in snap.profile_summary
    assert "Ayşe" in snap.profile_summary and "Fatma" in snap.profile_summary


# ---- PROFILE CONFLICT (registered constraint denied in chat) -----------------
def test_profile_conflict_notice_on_denied_allergy():
    prof = _profile([], owner=_owner(alerjiler=["yer fıstığı"]))
    snap = resolve_profile_snapshot_from_profile("acct", prof, "kendim")
    notice = _profile_conflict_answer(snap, "benim artık fıstık alerjim yok")
    assert notice is not None
    assert "profil" in notice.lower()


def test_profile_conflict_ignores_unrelated_negation():
    prof = _profile([], owner=_owner(alerjiler=["yer fıstığı"]))
    snap = resolve_profile_snapshot_from_profile("acct", prof, "kendim")
    assert _profile_conflict_answer(snap, "bugün pek aç değilim ne yesem") is None


def test_profile_conflict_none_without_registered_match():
    prof = _profile([], owner=_owner())
    snap = resolve_profile_snapshot_from_profile("acct", prof, "kendim")
    assert _profile_conflict_answer(snap, "fıstık alerjim yok") is None
