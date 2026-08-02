import json
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
CATALOG_PATH = PROJECT_ROOT / "data" / "rag_knowledge_catalog.json"
POLICY_PATH = PROJECT_ROOT / "data" / "rag_source_policy.json"


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def test_rag_knowledge_catalog_has_complete_lane_separation():
    catalog = _load(CATALOG_PATH)
    sources = catalog["sources"]

    assert catalog["schema_version"] == "rag_knowledge_catalog:v1"
    assert catalog["library_file_count"] == 43
    assert len(sources) == 43
    assert len({source["filename"] for source in sources}) == 43

    lane_counts = {
        lane: sum(source["usage_lane"] == lane for source in sources)
        for lane in catalog["usage_policy"]
    }
    assert lane_counts == {
        "clinical_background": 26,
        "product_research": 11,
        "technical_reference": 4,
        "quarantine": 2,
    }


def test_non_official_library_never_claims_clinical_eligibility():
    catalog = _load(CATALOG_PATH)

    assert all(source["clinical_claim_eligible"] is False for source in catalog["sources"])
    assert catalog["official_evidence"]["source_count"] == 8
    assert catalog["official_evidence"]["clinical_review_required"] is True


def test_source_policy_exclusions_match_non_clinical_lanes():
    catalog = _load(CATALOG_PATH)
    policy = _load(POLICY_PATH)
    excluded = set(policy["excluded_sources"])
    catalog_excluded = {
        source["filename"]
        for source in catalog["sources"]
        if source["policy_excluded_from_general_rag"]
    }

    assert catalog_excluded == excluded
    assert all(
        source["usage_lane"] != "clinical_background"
        for source in catalog["sources"]
        if source["filename"] in excluded
    )


def test_catalog_records_are_traceable_without_local_paths():
    catalog = _load(CATALOG_PATH)

    for source in catalog["sources"]:
        assert len(source["sha256"]) == 64
        assert source["product_use"]
        assert source["limitation"]
        assert not Path(source["filename"]).is_absolute()
        assert "C:\\Users" not in json.dumps(source)
