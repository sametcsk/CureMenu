import requests

from src.medical_knowledge.bioportal_client import BioPortalClient
from src.medical_knowledge.normalizer import MedicationNormalizer, extract_medication_mentions
from src.medical_knowledge.safety_checker import check_medication_food_safety, medication_safety_events
from src.agent_state import create_initial_state
from src.nodes import denetleyici_node


def test_bioportal_key_yokken_local_fallback_calisir(monkeypatch):
    monkeypatch.delenv("BIOPORTAL_API_KEY", raising=False)

    normalized = MedicationNormalizer().normalize("Coumadin")

    assert normalized.normalized_name == "warfarin"
    assert normalized.source_type == "local_fallback"


def test_coumadin_warfarin_normalize_olur(monkeypatch):
    monkeypatch.delenv("BIOPORTAL_API_KEY", raising=False)

    result = check_medication_food_safety(["Coumadin"], "Ispanak salatası")

    assert result["normalized_medications"][0]["normalized_name"] == "warfarin"
    assert result["matched_rules"]
    assert result["severity"] == "caution"


def test_warfarin_ispanak_risk_yakalar(monkeypatch):
    monkeypatch.delenv("BIOPORTAL_API_KEY", raising=False)

    result = check_medication_food_safety(["warfarin"], "Ispanak ve lahana salatası")

    assert result["severity"] == "caution"
    assert result["matched_rules"][0]["medication"] == "warfarin"


def test_lipitor_greyfurt_risk_yakalar(monkeypatch):
    monkeypatch.delenv("BIOPORTAL_API_KEY", raising=False)

    result = check_medication_food_safety(["Lipitor"], "Greyfurtlu salata")

    assert result["severity"] == "caution"
    assert result["matched_rules"][0]["medication"] == "atorvastatin"


def test_glucophage_alkol_caution_verir(monkeypatch):
    monkeypatch.delenv("BIOPORTAL_API_KEY", raising=False)

    result = check_medication_food_safety(["Glucophage"], "Alkol içeren sos")

    assert result["severity"] == "caution"
    assert result["needs_professional_review"] is True
    assert result["matched_rules"][0]["medication"] == "metformin"


def test_maoi_tiraminli_gida_avoid_verir(monkeypatch):
    monkeypatch.delenv("BIOPORTAL_API_KEY", raising=False)

    result = check_medication_food_safety(["MAOI"], "Eski peynir ve soya sosu")

    assert result["severity"] == "avoid"
    assert result["matched_rules"][0]["medication"] == "linezolid"


def test_cipro_sut_risk_yakalar(monkeypatch):
    monkeypatch.delenv("BIOPORTAL_API_KEY", raising=False)

    result = check_medication_food_safety(["Cipro"], "Sütlü yoğurt çorbası")

    assert result["severity"] == "caution"
    assert result["matched_rules"][0]["medication"] == "ciprofloxacin"


def test_levothyroxine_sut_kalsiyum_risk_yakalar(monkeypatch):
    monkeypatch.delenv("BIOPORTAL_API_KEY", raising=False)

    result = check_medication_food_safety(["Euthyrox"], "Süt ve kalsiyum destekli kahvaltı")

    assert result["severity"] == "caution"
    assert result["matched_rules"][0]["medication"] == "levothyroxine"


def test_ciproheptadine_cipro_false_positive_olmaz(monkeypatch):
    monkeypatch.delenv("BIOPORTAL_API_KEY", raising=False)

    normalized = MedicationNormalizer().normalize("ciproheptadine")

    assert normalized.normalized_name is None


def test_bilinmeyen_ilac_unknown_professional_review(monkeypatch):
    monkeypatch.delenv("BIOPORTAL_API_KEY", raising=False)

    result = check_medication_food_safety(["BilinmeyenIlac"], "Mercimek çorbası")

    assert result["severity"] == "unknown"
    assert result["needs_professional_review"] is True
    assert result["matched_rules"] == []
    assert result["normalized_medications"][0]["normalized_name"] is None


def test_medication_safety_event_metadata_normalized_ve_unknown_detay_tasir(monkeypatch):
    monkeypatch.delenv("BIOPORTAL_API_KEY", raising=False)

    result = check_medication_food_safety(["Lipitor", "BilinmeyenIlac"], "Mercimek çorbası")
    events = medication_safety_events(result)
    normalized_event = next(event for event in events if event["event_type"] == "MedicalTermNormalized")

    assert "atorvastatin" in normalized_event["metadata"]["normalized_names"]
    assert normalized_event["metadata"]["unknown_count"] == 1
    assert len(normalized_event["metadata"]["unknown_hashes"][0]) == 12


def test_bioportal_client_mock_response_normalize_edilir(monkeypatch):
    class FakeResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return {
                "collection": [
                    {
                        "@id": "http://example.test/warfarin",
                        "prefLabel": "Warfarin",
                        "synonym": ["Anticoagulant"],
                        "cui": "C0043031",
                        "semanticType": ["T121"],
                    }
                ]
            }

    def fake_get(*args, **kwargs):
        return FakeResponse()

    monkeypatch.setenv("BIOPORTAL_API_KEY", "test-key")
    monkeypatch.setattr("requests.get", fake_get)

    normalizer = MedicationNormalizer(bioportal_client=BioPortalClient())
    normalized = normalizer.normalize("external-anticoagulant-term")

    assert normalized.normalized_name == "warfarin"
    assert normalized.source_type == "bioportal"
    assert normalized.ontology_id == "http://example.test/warfarin"


def test_bioportal_timeout_fallbacke_doner(monkeypatch):
    def failing_get(*args, **kwargs):
        raise requests.Timeout("timeout")

    monkeypatch.setenv("BIOPORTAL_API_KEY", "test-key")
    monkeypatch.setattr("requests.get", failing_get)

    normalizer = MedicationNormalizer(bioportal_client=BioPortalClient())
    normalized = normalizer.normalize("not-known-by-local-map")

    assert normalized.normalized_name is None
    assert normalized.source_type == "local_fallback"


def test_bioportal_failure_cachelenmez(monkeypatch):
    class FakeResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return {"collection": [{"prefLabel": "Warfarin"}]}

    calls = {"count": 0}

    def flaky_get(*args, **kwargs):
        calls["count"] += 1
        if calls["count"] == 1:
            raise requests.Timeout("timeout")
        return FakeResponse()

    monkeypatch.setenv("BIOPORTAL_API_KEY", "test-key")
    monkeypatch.setattr("requests.get", flaky_get)
    client = BioPortalClient()

    assert client.search("external-anticoagulant-term") == []
    assert client.search("external-anticoagulant-term")[0]["prefLabel"] == "Warfarin"


def test_medication_safety_governance_eventleri_uretilir(monkeypatch):
    monkeypatch.delenv("BIOPORTAL_API_KEY", raising=False)
    state = create_initial_state(
        profil_ozeti="Ali, Hastalıklar (ICD-11 Standart): Yok, Alerjiler: Yok, Kullandığı İlaçlar: Lipitor",
        istek="Akşam ne yesem?",
        hafiza=[],
        ilaclar=["Lipitor"],
    )
    state.update({"uzman_onerisi": "Greyfurtlu salata", "hedef_islem": "SECENEK_SUN_BITTI"})

    result = denetleyici_node(state)
    event_types = {event["event_type"] for event in result["governance_events"]}

    assert result["guvenli_mi"] is True
    assert result["risk_score"] >= 0.5
    assert "greyfurt" in result["uzman_onerisi"].casefold()
    assert {"MedicalTermNormalized", "MedicationRuleMatched", "MedicationSafetyChecked"}.issubset(event_types)
    assert any(event["event_type"] == "RuleTriggered" and event["component"] == "medication_safety" for event in result["governance_events"])


def test_unknown_ilac_final_cevapta_profesyonel_uyari_uretir(monkeypatch):
    from src.routers.chat import _final_cevap_metni

    monkeypatch.delenv("BIOPORTAL_API_KEY", raising=False)
    state = create_initial_state(
        profil_ozeti="Ali, Hastalıklar (ICD-11 Standart): Yok, Alerjiler: Yok, Kullandığı İlaçlar: BilinmeyenIlac",
        istek="Akşam ne yesem?",
        hafiza=[],
        ilaclar=["BilinmeyenIlac"],
    )
    state.update({"uzman_onerisi": "Mercimek çorbası", "hedef_islem": "SECENEK_SUN_BITTI"})

    result = denetleyici_node(state)

    assert result["guvenli_mi"] is True
    assert result["risk_score"] >= 0.5
    assert result["uzman_onerisi"] == "Mercimek çorbası"
    assert "İlaç-besin etkileşimi doğrulanamadı" in result["uyari_mesaji"]
    assert "doktorunuza" in _final_cevap_metni(result)
    assert any(event["event_type"] == "MedicationReviewRequired" for event in result["governance_events"])


def test_resmi_kanit_yokken_final_karar_uzman_uyarisi_ve_orta_risk_tasir(monkeypatch):
    from types import SimpleNamespace
    from src.memory import ClinicalEvidence

    monkeypatch.setattr("src.nodes.klinik_bilgi_getir", lambda *args, **kwargs: ClinicalEvidence(""))
    monkeypatch.setattr(
        "src.nodes.invoke_with_model_fallback",
        lambda *args, **kwargs: SimpleNamespace(content="SAFE: YES\nREASON: Bilinen kural ihlali bulunmadi."),
    )
    state = create_initial_state(
        profil_ozeti="Ali, Hastaliklar: Yok, Alerjiler: Yok",
        istek="Aksam ne yesem?",
        hafiza=[],
        ilaclar=[],
    )
    state.update({"uzman_onerisi": "Mercimek corbasi", "hedef_islem": "SECENEK_SUN_BITTI"})

    result = denetleyici_node(state)

    assert result["guvenli_mi"] is True
    assert result["risk_score"] >= 0.5
    assert "yeterli eşleşme bulunamadı" in result["uyari_mesaji"]
    retrieval = next(event for event in result["governance_events"] if event["event_type"] == "RetrieverExecuted")
    assert retrieval["metadata"]["evidence_policy"] == "official_scoped_only"
    assert retrieval["metadata"]["clinical_review_status"] == "not_established"
    assert retrieval["metadata"]["review_required"] is True


def test_mesajdaki_ilac_adi_deterministik_olarak_cikarilir():
    assert extract_medication_mentions("Xyzalor kullanıyorum; yoğurt yiyebilir miyim?") == ["Xyzalor"]
    assert extract_medication_mentions("Euthyrox adlı ilacı kullanıyorum") == ["Euthyrox"]
    assert extract_medication_mentions("Bunu ben kullanıyorum") == []
    assert extract_medication_mentions("Bu yöntemi düzenli kullanıyorum") == []


def test_eslesen_kural_bilinmeyen_ilaci_gizlemez(monkeypatch):
    monkeypatch.delenv("BIOPORTAL_API_KEY", raising=False)

    result = check_medication_food_safety(["Coumadin", "Xyzalor"], "Ispanak yemeği")

    assert result["matched_rules"]
    assert result["needs_professional_review"] is True
    assert "Bilinmeyen ilaç kaydı" in result["explanation"]


def test_gut_kurali_buyuk_kucuk_harften_bagimsiz_ve_spesifiktir():
    from src.quality.rule_engine import RuleEngine

    profile = {"alerjiler": [], "hastaliklar": ["FA25 Gout (gut)"]}

    offal_result = RuleEngine().check_rules(profile, "Sakatat yemeği", ["Sakatat"])
    assert offal_result["found_risks"] == []
    assert offal_result["found_warnings"]
    assert RuleEngine().check_rules(profile, "Az porsiyon kırmızı et", ["Kırmızı et"])["found_risks"] == []
    assert RuleEngine().check_rules(profile, "Sebzeli diyet yemeği", ["Sebzeli diyet yemeği"])["found_risks"] == []


def test_sayisal_secim_resolve_edilip_safety_checkten_gecer(monkeypatch):
    monkeypatch.delenv("BIOPORTAL_API_KEY", raising=False)
    state = create_initial_state(
        profil_ozeti="Ali, Hastalıklar (ICD-11 Standart): Yok, Alerjiler: Yok, Kullandığı İlaçlar: Lipitor",
        istek="1",
        hafiza=[],
        sohbet_gecmisi=[
            {"role": "assistant", "content": "1. Greyfurtlu salata\n2. Mercimek çorbası"},
        ],
        ilaclar=["Lipitor"],
    )
    state.update({"uzman_onerisi": "1", "hedef_islem": "TARIF_GETIR"})

    result = denetleyici_node(state)
    event_types = {event["event_type"] for event in result["governance_events"]}

    assert result["guvenli_mi"] is True
    assert result["risk_score"] >= 0.5
    assert "atorvastatin" in result["uyari_mesaji"]
    assert "MealSelectionResolved" in event_types
    assert "MedicationSafetyChecked" in event_types


def test_missing_expert_recommendation_returns_safe_review_instead_of_crashing(monkeypatch):
    monkeypatch.delenv("BIOPORTAL_API_KEY", raising=False)
    state = create_initial_state(
        profil_ozeti="Ali, Hastaliklar: Yok, Alerjiler: Yok, Ilaclar: Yok",
        istek="Aksam ne yesem?",
        hafiza=[],
        ilaclar=[],
    )
    state.update({"uzman_onerisi": None, "hedef_islem": "SECENEK_SUN_BITTI"})

    result = denetleyici_node(state)

    assert result["guvenli_mi"] is True
    assert result["uzman_onerisi"] is None
    assert result["risk_score"] >= 0.5
    assert any(
        event.get("metadata", {}).get("reason") == "short_selection_unresolved"
        for event in result["governance_events"]
    )


def test_absence_wording_does_not_trigger_medication_food_rule(monkeypatch):
    monkeypatch.delenv("BIOPORTAL_API_KEY", raising=False)

    cipro = check_medication_food_safety(["Cipro"], "Sütsüz sebze çorbası")
    metformin = check_medication_food_safety(["Glucophage"], "Alkolsüz içecek")

    assert cipro["matched_rules"] == []
    assert metformin["matched_rules"] == []


def test_guardrail_checks_original_request_and_keeps_related_warnings(monkeypatch):
    monkeypatch.delenv("BIOPORTAL_API_KEY", raising=False)
    state = create_initial_state(
        profil_ozeti=(
            "Test, Yas: 52, Cinsiyet: Erkek, Beslenme Hedefi: Kas Kazanımı, "
            "Hastalıklar (ICD-11 Standart): Gut, evre 3 kronik böbrek hastalığı, "
            "Alerjiler: İnek sütü proteini, yer fıstığı, "
            "Kullandığı İlaçlar: Warfarin, Levotiroksin"
        ),
        istek="Sütlü, yer fıstığı ezmeli ve ıspanaklı içecek tüketebilir miyim?",
        hafiza=[],
        ilaclar=["Warfarin", "Levotiroksin"],
        resolved_profile_snapshot={
            "target_id": "self-test",
            "target_scope": "self",
            "diseases": ["Gut", "evre 3 kronik böbrek hastalığı"],
            "allergies": ["İnek sütü proteini", "yer fıstığı"],
            "medications": ["Warfarin", "Levotiroksin"],
            "ages": [52],
            "genders": ["erkek"],
            "goals": ["Kas Kazanımı"],
        },
    )
    state.update({
        "uzman_onerisi": "Bu içecek uygun değildir. Gut hastalığında sakatat riski ayrıca değerlendirilir.",
        "hedef_islem": "SECENEK_SUN_BITTI",
    })

    result = denetleyici_node(state)

    assert result["guvenli_mi"] is False
    assert "İnek sütü proteini" in result["uyari_mesaji"]
    assert "yer fıstığı" in result["uyari_mesaji"]
    assert "Warfarin" in result["uyari_mesaji"]
    assert "Levothyroxine" in result["uyari_mesaji"]
    assert "Böbrek hastalığında" in result["uyari_mesaji"]
    assert "sakatat riski." not in result["uyari_mesaji"]
    assert any(
        event.get("event_type") == "MedicationSafetyChecked"
        for event in result["governance_events"]
    )


def test_secondary_health_check_accepts_explicit_safe_substitutes():
    from src.grocery.health import assess_item_health

    milk = assess_item_health(
        "Badem sütlü chia pudingi",
        allergies=["İnek sütü proteini"],
        diseases=[],
    )
    gluten = assess_item_health(
        "Glutensiz ekmek ile sebzeli sandviç",
        allergies=[],
        diseases=["çölyak"],
    )
    egg = assess_item_health(
        "Yumurtasız sebzeli mücver",
        allergies=["yumurta"],
        diseases=[],
    )
    gout_warning = assess_item_health(
        "Gut hastalığında sakatat önerilmez.",
        allergies=[],
        diseases=["gut"],
    )

    assert milk.status == "safe"
    assert gluten.status == "safe"
    assert egg.status == "safe"
    assert gout_warning.status == "safe"
