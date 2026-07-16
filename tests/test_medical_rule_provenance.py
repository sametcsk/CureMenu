from src.governance.version_registry import get_component_versions
from src.medical_knowledge.medication_rules import load_high_risk_medication_rules
from src.medical_knowledge.provenance import (
    OFFICIAL_SOURCE_DIR,
    get_rule_provenance,
    load_evidence_registry,
    rule_provenance_version,
    validate_rule_provenance,
)
from src.medical_knowledge.safety_checker import check_medication_food_safety


def test_every_deterministic_medication_rule_has_verified_provenance():
    assert validate_rule_provenance(verify_files=False) == []
    for rule in load_high_risk_medication_rules()["rules"]:
        evidence = get_rule_provenance(rule.rule_id)
        assert evidence is not None
        assert evidence["verification_status"] == "source_verified"
        assert evidence["clinical_review_status"] == "pending"
        assert evidence["pages"]


def test_local_official_pdfs_are_verified_when_available():
    sources = load_evidence_registry().get("sources") or {}
    expected_files = [OFFICIAL_SOURCE_DIR / str(source["filename"]) for source in sources.values()]
    if not expected_files or not all(path.is_file() for path in expected_files):
        return

    assert validate_rule_provenance(verify_files=True) == []


def test_warfarin_match_carries_exact_fda_page(monkeypatch):
    monkeypatch.delenv("BIOPORTAL_API_KEY", raising=False)

    result = check_medication_food_safety(["Coumadin"], "Ispanak salatasi")
    matched = result["matched_rules"][0]

    assert matched["rule_id"] == "warfarin-vitamin-k-consistency:v2"
    assert matched["evidence"]["authority"] == "FDA"
    assert matched["evidence"]["pages"] == [16]
    assert matched["provenance_version"] == rule_provenance_version()


def test_component_versions_expose_rule_and_official_rag_versions():
    versions = get_component_versions()

    assert versions["high_risk_medications"] == "high_risk_medications:v2"
    assert versions["medication_rule_provenance"] == "medication_rule_provenance:v1"
    assert versions["official_clinical_scope"] == "official_clinical_scope:v1"
    assert versions["clinical_evidence_registry"] == "clinical_evidence_registry:v1"
