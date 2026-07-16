from src.models import AileUyesi, Cinsiyet, KullaniciProfili
from src.nodes import _quality_profile_from_summary
from src.profil_utils import profil_ozeti_olustur
from src.quality.policy_engine import PolicyEngine
from src.quality.scope_policy import profile_scope_review_reasons
from src.routers.tools import _check_tool_output_safety


def _profile(member: AileUyesi) -> KullaniciProfili:
    return KullaniciProfili(ana_kullanici=member)


def test_profile_summary_carries_real_age_into_policy_profile():
    member = AileUyesi(ad="Ada", yas=15, cinsiyet=Cinsiyet.KADIN)

    summary = profil_ozeti_olustur(member)
    quality_profile = _quality_profile_from_summary(summary)
    policy = PolicyEngine().check_policy(quality_profile, "meal_recommendation")

    assert quality_profile["yas"] == 15
    assert policy["requires_review"] is True
    assert "18 yaş altı" in policy["applied_policies"][0]


def test_pregnancy_and_kidney_profiles_require_review_without_hard_block():
    pregnancy = AileUyesi(
        ad="Ece",
        yas=30,
        cinsiyet=Cinsiyet.KADIN,
        hedef="Hamilelik / Emzirme Beslenmesi",
    )
    kidney = AileUyesi(
        ad="Can",
        yas=48,
        cinsiyet=Cinsiyet.ERKEK,
        hastaliklar=["Kronik böbrek hastalığı"],
    )

    assert any("Gebelik" in item for item in profile_scope_review_reasons(_profile(pregnancy), "kendim"))
    assert any("Böbrek" in item for item in profile_scope_review_reasons(_profile(kidney), "kendim"))


def test_weekly_tool_safety_surfaces_scope_warning():
    member = AileUyesi(ad="Ada", yas=15, cinsiyet=Cinsiyet.KADIN)

    result = _check_tool_output_safety(
        _profile(member),
        "kendim",
        {"days": [{"breakfast": "Yulaf", "lunch": "Mercimek", "dinner": "Sebze"}]},
    )

    assert result["blocked"] is False
    assert result["review_required"] is True
    assert "18 yaş altı" in result["warning"]
    rule_event = next(event for event in result["events"] if event["event_type"] == "RuleChecked")
    assert rule_event["metadata"]["scope_review_count"] == 1
