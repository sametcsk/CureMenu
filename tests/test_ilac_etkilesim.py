from src.ilac_etkilesim import (
    eslesen_kurallar,
    ilac_etkilesim_ozeti,
    yemekte_riskli_ilac_etkilesimi,
)
from src.profil_utils import hedef_ilaclari, profil_ozeti_olustur
from src.models import AileUyesi, Cinsiyet, KullaniciProfili
from src.rules.registry import load_medication_food_registry


def test_ilac_kurallari_registryden_yuklenir():
    registry = load_medication_food_registry()
    assert registry["version"] == "medication_food_rules:v1"
    assert any(rule["medication"] == "warfarin" for rule in registry["rules"])


def test_metformin_alkol_etkilesimi():
    riskler = yemekte_riskli_ilac_etkilesimi("Bira tavası", ["metformin"])
    assert len(riskler) >= 1
    assert "metformin" in riskler[0].lower()


def test_statin_greyfurt_etkilesimi():
    riskler = yemekte_riskli_ilac_etkilesimi("Greyfurtlu salata", ["atorvastatin"])
    assert len(riskler) >= 1
    assert "greyfurt" in riskler[0].lower() or "statin" in riskler[0].lower()


def test_guvenli_yemek_risk_yok():
    riskler = yemekte_riskli_ilac_etkilesimi("Mercimek çorbası", ["metformin"])
    assert riskler == []


def test_eslesen_kurallar_alias():
    kurallar = eslesen_kurallar(["Glifor"])
    assert any(k.ad == "metformin" for k in kurallar)


def test_profil_ozetinde_ilac_kurallari():
    uye = AileUyesi(
        id="1",
        ad="Ali",
        yas=45,
        cinsiyet=Cinsiyet.ERKEK,
        ilaclar=["warfarin"],
    )
    ozet = profil_ozeti_olustur(uye)
    assert "warfarin" in ozet.lower()
    assert "ZORUNLU" in ilac_etkilesim_ozeti(["warfarin"])


def test_hedef_ilaclari_aile_modu():
    profil = KullaniciProfili(
        ana_kullanici=AileUyesi(
            id="1", ad="Ali", yas=40, cinsiyet=Cinsiyet.ERKEK, ilaclar=["metformin"]
        ),
        aile_uyeleri=[
            AileUyesi(
                id="2", ad="Ayşe", yas=38, cinsiyet=Cinsiyet.KADIN, ilaclar=["aspirin"]
            )
        ],
    )
    ilaclar = hedef_ilaclari(profil, "aile")
    assert "metformin" in ilaclar
    assert "aspirin" in ilaclar
