"""Regression tests for fail-closed target-person resolution (BUG 1/2/4/5).

These assert profile identity at the resolution layer, before any LLM call:
- a relationship/typo reference resolves to the correct family member,
- an ambiguous reference asks for clarification instead of guessing,
- the account owner is NEVER silently used when the message names someone else.
"""
from src.models import AileUyesi, Cinsiyet, KullaniciProfili
from src.target_resolution import (
    TargetResolution,
    clarification_prompt,
    relation_category,
    resolve_target_from_message,
)


def _mert(**kw):
    return AileUyesi(id="mert-1", ad="Mert", yas=12, cinsiyet=Cinsiyet.ERKEK, yakinlik=kw.pop("yakinlik", "oğul"), **kw)


def _elif(**kw):
    return AileUyesi(id="elif-1", ad="Elif", yas=9, cinsiyet=Cinsiyet.KADIN, yakinlik=kw.pop("yakinlik", "kız"), **kw)


def _profile(members):
    return KullaniciProfili(
        ana_kullanici=AileUyesi(id="ayse-main", ad="Ayşe", yas=45, cinsiyet=Cinsiyet.KADIN),
        aile_uyeleri=list(members),
    )


def test_relation_category_mapping():
    assert relation_category("oğul") == "son"
    assert relation_category("kız") == "daughter"
    assert relation_category("kız kardeş") == "sibling"
    assert relation_category("eş") == "spouse"
    assert relation_category("anne") == "mother"
    assert relation_category(None) is None


def test_no_reference_honours_client_hint():
    res = resolve_target_from_message(_profile([_mert()]), "bu akşam ıspanaklı börek uygun mu", "kendim")
    assert res.target == "kendim"
    assert res.source == "client_hint"
    assert res.needs_clarification is False


def test_explicit_self_reference():
    res = resolve_target_from_message(_profile([_mert()]), "benim için bu akşam ne önerirsin", "kendim")
    assert res.target == "kendim"
    assert res.source == "message_self"


def test_direct_name_match_resolves_member():
    res = resolve_target_from_message(_profile([_mert()]), "Mert bugün okulda ne yesin", "kendim")
    assert res.target == "mert-1"
    assert res.source == "message_name"


def test_relationship_resolves_via_yakinlik():
    res = resolve_target_from_message(_profile([_mert(), _elif()]), "oğlum için okul çıkışı tost uygun mu", "kendim")
    assert res.target == "mert-1"
    assert res.source == "message_relationship"
    assert res.referenced_someone_else is True


def test_typo_oglun_still_resolves_to_son_not_owner():
    # BUG 2: "oğlun" (typo for "oğlum") must not silently fall back to Ayşe.
    res = resolve_target_from_message(_profile([_mert(), _elif()]), "oğlun için geçen menü analizindeki ana risk neydi", "kendim")
    assert res.target == "mert-1"
    assert res.target != "kendim"


def test_ambiguous_two_matching_relations_ask_clarification():
    two_sons = [_mert(), AileUyesi(id="ali-2", ad="Ali", yas=15, cinsiyet=Cinsiyet.ERKEK, yakinlik="oğul")]
    res = resolve_target_from_message(_profile(two_sons), "oğlum için kahvaltı öner", "kendim")
    assert res.needs_clarification is True
    assert res.target is None
    assert {c[0] for c in res.candidates} == {"mert-1", "ali-2"}
    assert "Mert" in clarification_prompt(res)


def test_relationship_single_member_without_yakinlik_asks_instead_of_inventing_relation():
    res = resolve_target_from_message(_profile([_mert(yakinlik=None)]), "oğlum için tost uygun mu", "kendim")
    assert res.target is None
    assert res.needs_clarification is True
    assert res.reason == "relationship_without_metadata"


def test_relationship_multiple_members_without_yakinlik_clarifies_not_owner():
    members = [_mert(yakinlik=None), _elif(yakinlik=None)]
    res = resolve_target_from_message(_profile(members), "oğlum için tost uygun mu", "kendim")
    assert res.needs_clarification is True
    assert res.target is None
    assert res.target != "kendim"


def test_family_wide_reference():
    res = resolve_target_from_message(_profile([_mert()]), "tüm aile için akşam ne pişireyim", "kendim")
    assert res.target == "aile"
    assert res.source == "message_family"


def test_client_hint_member_when_no_message_reference():
    res = resolve_target_from_message(_profile([_mert()]), "bu akşam ne yesek", "mert-1")
    assert res.target == "mert-1"
    assert res.source == "client_hint"


def test_relationship_reference_never_returns_owner_silently():
    # Even with no family members, a clear relationship reference must not become Ayşe.
    res = resolve_target_from_message(_profile([]), "oğlum için ne alayım", "kendim")
    assert res.needs_clarification is True
    assert res.target != "kendim"


def test_oglumunki_suffixed_token_resolves_to_son():
    res = resolve_target_from_message(_profile([_mert(), _elif()]), "oğlumunki?", "kendim")
    assert res.target == "mert-1"
    assert res.source == "message_relationship"


# --- Follow-up continuity (Req 1): a no-reference follow-up keeps the prior target ---

def test_followup_without_reference_keeps_previous_target():
    prof = _profile([_mert(), _elif()])
    res = resolve_target_from_message(prof, "peki ayran?", client_hint="kendim", previous_target="mert-1")
    assert res.target == "mert-1"
    assert res.source == "continuity"


def test_followup_new_food_keeps_previous_target():
    prof = _profile([_mert(), _elif()])
    for msg in ("ya pizza?", "peki akşam?", "başka ne olur"):
        res = resolve_target_from_message(prof, msg, client_hint="kendim", previous_target="mert-1")
        assert res.target == "mert-1", msg


def test_explicit_self_switches_away_from_previous_target():
    prof = _profile([_mert(), _elif()])
    res = resolve_target_from_message(prof, "benim için peki?", client_hint="kendim", previous_target="mert-1")
    assert res.target == "kendim"
    assert res.source == "message_self"


def test_implicit_turkish_first_person_switches_away_from_previous_target():
    prof = _profile([_mert()])

    for message in (
        "çok acıktım ne yemeliyim",
        "ne yesem",
        "bir şey yemek istiyorum",
        "Warfarin kullandığım için ıspanağı bırakmalı mıyım",
        "bu haftaki planımda neye dikkat ettin",
    ):
        res = resolve_target_from_message(
            prof,
            message,
            client_hint="kendim",
            previous_target="mert-1",
        )
        assert res.target == "kendim"
        assert res.source == "message_self_implicit"


def test_relationship_and_pronoun_win_over_implicit_first_person():
    prof = _profile([_mert()])

    relationship = resolve_target_from_message(
        prof,
        "oğlum için bir şey hazırlamak istiyorum",
        client_hint="kendim",
        previous_target="kendim",
    )
    pronoun = resolve_target_from_message(
        prof,
        "onun için daha güvenli ne seçebilirim",
        client_hint="kendim",
        previous_target="mert-1",
    )

    assert relationship.target == "mert-1"
    assert relationship.source == "message_relationship"
    assert pronoun.target == "mert-1"
    assert pronoun.source == "pronoun"


def test_relationship_switches_back_after_self():
    prof = _profile([_mert(), _elif()])
    res = resolve_target_from_message(prof, "oğlumunki?", client_hint="kendim", previous_target="kendim")
    assert res.target == "mert-1"


def test_no_previous_and_no_reference_uses_hint():
    prof = _profile([_mert()])
    res = resolve_target_from_message(prof, "bugün ne yesek", client_hint="kendim", previous_target=None)
    assert res.target == "kendim"
    assert res.source == "client_hint"


def test_stale_previous_target_asks_instead_of_falling_back_to_owner():
    prof = _profile([_mert()])
    res = resolve_target_from_message(prof, "peki ayran?", client_hint="kendim", previous_target="deleted-id")
    assert res.target is None
    assert res.needs_clarification is True
    assert res.source == "stale_previous_target"


def test_pronoun_keeps_valid_non_owner_antecedent():
    prof = _profile([_mert(), _elif()])
    res = resolve_target_from_message(
        prof,
        "peki onun için daha güvenli ne seçebiliriz?",
        client_hint="kendim",
        previous_target="mert-1",
    )
    assert res.target == "mert-1"
    assert res.source == "pronoun"


def test_pronoun_without_non_owner_antecedent_is_ambiguous():
    prof = _profile([_mert(), _elif()])
    res = resolve_target_from_message(prof, "onun için ne olur?", client_hint="kendim")
    assert res.target is None
    assert res.needs_clarification is True
    assert res.source == "pronoun_ambiguous"


def test_unknown_client_target_never_silently_becomes_owner():
    res = resolve_target_from_message(_profile([_mert()]), "peki pizza?", client_hint="deleted-id")
    assert res.target is None
    assert res.needs_clarification is True
    assert res.source == "unknown_hint"


# --- Data-driven relationship resolution: changing yakinlik changes the outcome ---

def test_changing_yakinlik_changes_relationship_resolution():
    prof = _profile([_mert(yakinlik="ogul"), _elif(yakinlik="kiz")])
    assert resolve_target_from_message(prof, "oğlum için ne olur", "kendim").target == "mert-1"

    # Same names, but Mert is now a sibling: "oğlum" (son) matches nobody -> clarify,
    # while "kardeşim" now resolves Mert. No name is hard-coded anywhere.
    prof2 = _profile([_mert(yakinlik="kardes"), _elif(yakinlik="kiz")])
    assert resolve_target_from_message(prof2, "oğlum için ne olur", "kendim").needs_clarification is True
    assert resolve_target_from_message(prof2, "kardeşim için ne olur", "kendim").target == "mert-1"


def test_name_relationship_conflict_asks_clarification():
    prof = _profile([_mert(yakinlik="ogul"), _elif(yakinlik="kiz")])
    res = resolve_target_from_message(prof, "kızım Mert için ne olur", "kendim")
    assert res.needs_clarification is True         # name=Mert(son) vs relationship=kız -> conflict
    assert ("mert-1", "Mert") in res.candidates


def test_name_with_matching_relationship_has_no_conflict():
    prof = _profile([_mert(yakinlik="ogul")])
    res = resolve_target_from_message(prof, "oğlum Mert için ne olur", "kendim")
    assert res.target == "mert-1"                  # name + agreeing relationship

    # Normalized ("ogul") and Turkish ("oğul") yakinlik values both resolve.
    prof_tr = _profile([_mert(yakinlik="oğul")])
    assert resolve_target_from_message(prof_tr, "oğlum için", "kendim").target == "mert-1"
