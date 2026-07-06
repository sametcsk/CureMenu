import requests

from src.medical_knowledge.bioportal_client import BioPortalClient
from src.medical_knowledge.normalizer import MedicationNormalizer
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

    assert result["severity"] == "avoid"
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

    assert result["guvenli_mi"] is False
    assert {"MedicalTermNormalized", "MedicationRuleMatched", "MedicationSafetyChecked"}.issubset(event_types)
    assert any(event["event_type"] == "RuleTriggered" and event["component"] == "medication_safety" for event in result["governance_events"])


def test_unknown_ilac_final_cevapta_profesyonel_uyari_uretir(monkeypatch):
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
    assert "İlaç-besin etkileşimi doğrulanamadı" in result["uzman_onerisi"]
    assert any(event["event_type"] == "MedicationReviewRequired" for event in result["governance_events"])


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

    assert result["guvenli_mi"] is False
    assert "atorvastatin" in result["uyari_mesaji"]
    assert "MealSelectionResolved" in event_types
    assert "MedicationSafetyChecked" in event_types
