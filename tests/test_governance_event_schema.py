from src.governance.events import SCHEMA_VERSION, make_event
from src.governance.kpi import calculate_clinical_kpis, event_is_blocking, event_requires_review
from src.grocery.capability import build_smart_grocery
from src.grocery.profile import GroceryProfileFacts
from src.medical_knowledge.safety_checker import check_medication_food_safety, medication_safety_events


def test_event_factory_standart_metadata_alanlarini_ekler():
    event = make_event(
        "PolicyChecked",
        "policy_engine",
        status="review",
        metadata={"legacy_field": "kept"},
    )

    metadata = event["metadata"]
    assert metadata["legacy_field"] == "kept"
    assert metadata["event_name"] == "PolicyChecked"
    assert metadata["category"] == "policy"
    assert metadata["severity"] == "medium"
    assert metadata["decision_effect"] == "review_required"
    assert metadata["blocking"] is False
    assert metadata["review_required"] is True
    assert metadata["source_component"] == "policy_engine"
    assert metadata["schema_version"] == SCHEMA_VERSION


def test_medication_safety_event_schema_alanlari_tasir(monkeypatch):
    monkeypatch.delenv("BIOPORTAL_API_KEY", raising=False)

    result = check_medication_food_safety(["Lipitor"], "Greyfurtlu salata")
    events = medication_safety_events(result)
    checked = next(event for event in events if event["event_type"] == "MedicationSafetyChecked")

    metadata = checked["metadata"]
    assert metadata["category"] == "medication_safety"
    assert metadata["severity"] == "high"
    assert metadata["decision_effect"] == "block"
    assert metadata["blocking"] is True
    assert metadata["review_required"] is True
    assert metadata["source_component"] == "medical_knowledge.safety_checker"
    assert metadata["schema_version"] == SCHEMA_VERSION
    assert metadata["source_type"] == "deterministic_rule"


def test_smart_grocery_event_schema_alanlari_ve_legacy_metadata_korunur():
    profile = GroceryProfileFacts(
        summary="test profile",
        allergies=["yumurta"],
        diseases=[],
        medications=[],
    )

    _basket, state = build_smart_grocery(
        weekly_plan=None,
        shopping_items=[{"name": "Yumurta"}],
        profile_facts=profile,
    )
    events = state["governance_events"]
    health = next(event for event in events if event["event_type"] == "HealthComplianceChecked")
    price = next(event for event in events if event["event_type"] == "PriceEstimationAttempted")
    basket = next(event for event in events if event["event_type"] == "GroceryBasketSuggested")

    assert health["metadata"]["category"] == "grocery"
    assert health["metadata"]["decision_effect"] == "block"
    assert health["metadata"]["blocking"] is True
    assert health["metadata"]["risk_items"][0]["name"] == "Yumurta"
    assert price["metadata"]["category"] == "grocery"
    assert price["metadata"]["decision_effect"] == "none"
    assert price["metadata"]["live_price"] is False
    assert basket["metadata"]["category"] == "grocery"
    assert basket["metadata"]["included_item_count"] == 0
    assert basket["metadata"]["excluded_item_count"] == 1


def test_kpi_helper_eski_ve_yeni_eventleri_geriye_uyumlu_okur():
    old_blocked = {"event_type": "RuleTriggered", "status": "ok", "metadata": {}}
    new_review = {
        "event_type": "PolicyChecked",
        "status": "ok",
        "metadata": {"review_required": True, "severity": "medium"},
    }

    assert event_is_blocking(old_blocked) is True
    assert event_requires_review(new_review) is True

    kpis = calculate_clinical_kpis(
        decisions=[],
        events=[old_blocked, new_review],
    )

    assert kpis["blocked_decision_events"] == 1
    assert kpis["review_required_event_count"] == 1
