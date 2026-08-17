"""Target CHANGE vs. member REFERENCE/feedback, and multi/family safety.

A statement about a member ("çocuk bunu sevmez", "eşim tuzlu sevmiyor") inside an
active family/multi conversation must NOT narrow the target to that member — it is
feedback. Only an explicit request ("sadece çocuğuma", "... için", dative) switches.
All deterministic, LLM-free. Example names are fixtures only.
"""
import pytest

from src.models import AileUyesi, Cinsiyet, KullaniciProfili
from src.profile_context import resolve_profile_snapshot_from_profile as SNAP
from src.routers.chat import _profile_conflict_answer
from src.target_resolution import multi_key, resolve_target_from_message


def R(profile, message, hint="kendim", previous=None):
    return resolve_target_from_message(profile, message, hint, previous)


def _m(mid, ad, yakinlik, cins=Cinsiyet.KADIN, yas=30, alj=None, has=None):
    return AileUyesi(id=mid, ad=ad, yas=yas, cinsiyet=cins, yakinlik=yakinlik, alerjiler=alj or [], hastaliklar=has or [])


def _owner(has=None, alj=None):
    return AileUyesi(id="own", ad="Ayşe", yas=45, cinsiyet=Cinsiyet.KADIN, hastaliklar=has or [], alerjiler=alj or [])


def _household():
    return KullaniciProfili(
        ana_kullanici=_owner(has=["diyabet"]),
        aile_uyeleri=[
            _m("cocuk", "Mert", "ogul", Cinsiyet.ERKEK, 9, alj=["süt", "yer fıstığı"]),
            _m("es", "Deniz", "es", Cinsiyet.ERKEK, 47, has=["hipertansiyon"]),
        ],
    )


def _parents():
    return KullaniciProfili(
        ana_kullanici=_owner(),
        aile_uyeleri=[
            _m("anne", "Fatma", "anne", has=["diyabet"]),
            _m("baba", "Kemal", "baba", Cinsiyet.ERKEK, has=["hipertansiyon"]),
        ],
    )


# ---- A/B: feedback inside a FAMILY conversation keeps FAMILY -----------------
def test_A_child_feedback_keeps_family():
    prof = _household()
    r = R(prof, "çocuk bunu sevmez", previous="aile")
    assert r.scope == "family"
    assert r.needs_clarification is False
    # and the next "başka?" stays family too
    assert R(prof, "başka?", previous="aile").scope == "family"


@pytest.mark.parametrize("message", [
    "eşim tuzlu sevmiyor",
    "annem bunu yemiyor",
    "çocuk bunu beğenmedi",
    "eşim tuz kullanmıyor",
])
def test_B_member_feedback_keeps_family(message):
    r = R(_household(), message, previous="aile")
    assert r.scope == "family"
    assert r.needs_clarification is False


# ---- C: "çocuk da yiyecek" expands self -> multi -----------------------------
def test_C_expansion_self_plus_single_child():
    prof = KullaniciProfili(ana_kullanici=_owner(has=["diyabet"]),
                            aile_uyeleri=[_m("cocuk", "Mert", "ogul", Cinsiyet.ERKEK, 9, alj=["süt"])])
    r = R(prof, "çocuk da yiyecek", previous="kendim")
    assert r.scope == "multi"
    assert set(r.member_ids) == {"kendim", "cocuk"}


def test_C_expansion_multiple_children_clarifies():
    prof = KullaniciProfili(ana_kullanici=_owner(),
                            aile_uyeleri=[_m("c1", "Mert", "ogul", Cinsiyet.ERKEK, 9),
                                          _m("c2", "Elif", "kiz", Cinsiyet.KADIN, 7)])
    r = R(prof, "çocuk da yiyecek", previous="kendim")
    assert r.needs_clarification is True


# ---- D: feedback does NOT add a member to a MULTI set ------------------------
def test_D_feedback_does_not_expand_multi_set():
    prof = _household()
    prev = multi_key(["kendim", "es"])
    r = R(prof, "çocuk bunu sevmez", previous=prev)
    assert r.scope == "multi"
    assert set(r.member_ids) == {"kendim", "es"}  # child NOT added


# ---- E: explicit switch out of family to a single member --------------------
def test_E_explicit_switch_family_to_child():
    r = R(_household(), "şimdi sadece çocuğuma göre yap", previous="aile")
    assert r.scope == "single"
    assert r.target == "cocuk"


# ---- F/G: multi kept on feedback; explicit dative switches ------------------
def test_F_feedback_keeps_multi_parents():
    prof = _parents()
    prev = multi_key(["anne", "baba"])
    r = R(prof, "annem bunu sevmedi", previous=prev)
    assert r.scope == "multi"
    assert set(r.member_ids) == {"anne", "baba"}


def test_G_explicit_dative_switch_ignores_feedback_subject():
    prof = _parents()
    prev = multi_key(["anne", "baba"])
    r = R(prof, "annem bunu sevmedi, sadece babama başka bir şey öner", previous=prev)
    assert r.scope == "single"
    assert r.target == "baba"


# ---- "çocuk" generic reference is not a switch by itself --------------------
def test_child_word_alone_is_not_a_switch_in_family():
    assert R(_household(), "çocuk bunu istemiyor", previous="aile").scope == "family"


def test_child_for_is_a_switch():
    prof = KullaniciProfili(ana_kullanici=_owner(),
                            aile_uyeleri=[_m("cocuk", "Mert", "ogul", Cinsiyet.ERKEK, 9)])
    assert R(prof, "çocuk için öner", previous="kendim").target == "cocuk"


# ---- RELATION="diğer" young member reachable by "çocuğum" --------------------
def test_child_reference_reaches_diger_young_member():
    prof = KullaniciProfili(ana_kullanici=_owner(),
                            aile_uyeleri=[_m("kid", "Can", "diger", Cinsiyet.ERKEK, 8, alj=["yumurta"])])
    r = R(prof, "çocuğuma yemek öner", previous="kendim")
    assert r.scope == "single"
    assert r.target == "kid"


def test_child_reference_diger_adult_is_not_a_child():
    prof = KullaniciProfili(ana_kullanici=_owner(),
                            aile_uyeleri=[_m("rel", "Uzak", "diger", Cinsiyet.ERKEK, 40)])
    r = R(prof, "çocuğuma yemek öner", previous="kendim")
    assert r.needs_clarification is True  # no plausible child -> ask, never silently wrong


# ---- Section 6: multi/family safety invariants ------------------------------
def test_union_includes_every_referenced_member_constraint():
    prof = _household()
    snap = SNAP("acct", prof, multi_key(["kendim", "es"]))
    assert "diyabet" in snap.diseases and "hipertansiyon" in snap.diseases


def test_union_excludes_non_referenced_member_constraint():
    prof = _household()
    snap = SNAP("acct", prof, multi_key(["kendim", "es"]))
    assert "süt" not in snap.allergies and "yer fıstığı" not in snap.allergies


def test_distinct_target_sets_have_distinct_keys_so_history_isolates():
    prof = _household()
    keys = {
        SNAP("acct", prof, "aile").target_key,
        SNAP("acct", prof, multi_key(["kendim", "es"])).target_key,
        SNAP("acct", prof, "cocuk").target_key,
        SNAP("acct", prof, "kendim").target_key,
    }
    assert len(keys) == 4  # every scope/set is a separate isolation bucket


def test_scope_transitions_rebuild_snapshot_correctly():
    prof = _household()
    fam = SNAP("acct", prof, "aile")
    multi = SNAP("acct", prof, multi_key(["kendim", "es"]))
    single = SNAP("acct", prof, "cocuk")
    assert set(fam.allergies) >= {"süt", "yer fıstığı"}
    assert "süt" not in multi.allergies
    assert set(single.allergies) == {"süt", "yer fıstığı"} and single.target_scope == "self" or single.target_scope == "member"


# ---- Section 7: profile conflict (registered constraint denied) -------------
@pytest.mark.parametrize("message", [
    "benim artık fıstık alerjim yok",
    "doktor artık alerjim olmadığını söyledi",
    "yanlışlıkla alerji eklemişim",
])
def test_conflict_notice_on_denied_allergy(message):
    prof = KullaniciProfili(ana_kullanici=_owner(alj=["yer fıstığı"]))
    snap = SNAP("acct", prof, "kendim")
    assert _profile_conflict_answer(snap, message) is not None


def test_conflict_short_term_sut():
    prof = KullaniciProfili(ana_kullanici=_owner(),
                            aile_uyeleri=[_m("cocuk", "Mert", "ogul", Cinsiyet.ERKEK, 9, alj=["süt"])])
    snap = SNAP("acct", prof, "cocuk")
    assert _profile_conflict_answer(snap, "çocuğun süt alerjisi artık yok") is not None


def test_conflict_ignored_without_negation():
    prof = KullaniciProfili(ana_kullanici=_owner(alj=["yer fıstığı"]))
    snap = SNAP("acct", prof, "kendim")
    assert _profile_conflict_answer(snap, "bugün fıstıklı bir şey yiyebilir miyim") is None
