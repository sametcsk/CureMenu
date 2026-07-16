from langchain_core.documents import Document

from src import memory
from src.quality.retrieval_filter import filter_retrieval_results


def _official_metadata(source: str = "fda_warfarin_coumadin_2017.pdf") -> dict:
    return {
        "source": source,
        "authority": "FDA",
        "authority_tier": 1,
        "source_role": "regulatory_label",
        "scope_version": "clinical_evidence_registry:v1",
        "registry_source_id": "warfarin_fda",
        "file_sha256": "926D0AA997920DAE2F686A7CBD0E3EF8051474BC67F7162741DCFC394E48F67C",
    }


def test_retrieval_filter_rejects_semantically_near_but_lexically_irrelevant_result():
    results = [
        (Document(page_content="Diyabetin kronik komplikasyonlari ve tibbi beslenme bolumu."), 3.2),
    ]

    selected = filter_retrieval_results("mor gezegen kuantum corbasi", results, limit=3)

    assert selected == []


def test_retrieval_filter_requires_clinical_anchor_not_only_generic_vitamin_term():
    results = [
        (Document(page_content="D vitamini ve kalsiyum gereksinimleri hakkinda genel bilgiler." * 5), 5.0),
    ]

    selected = filter_retrieval_results("warfarin ispanak K vitamini", results, limit=3)

    assert selected == []


def test_retrieval_filter_deduplicates_and_diversifies_sources():
    results = [
        (Document(page_content="Warfarin ve vitamin K dengesi korunmalidir." * 5, metadata={"source": "a.pdf"}), 8.0),
        (Document(page_content="Warfarin ve vitamin K dengesi korunmalidir." * 5, metadata={"source": "a.pdf"}), 8.1),
        (Document(page_content="Warfarin kullanirken ispanak tuketimi tutarli olmalidir." * 4, metadata={"source": "a.pdf"}), 8.2),
        (Document(page_content="Warfarin tedavisinde K vitamini alimi ani degismemelidir." * 4, metadata={"source": "b.pdf"}), 8.3),
    ]

    selected = filter_retrieval_results("warfarin ispanak K vitamini", results, limit=3)

    assert len(selected) == 2
    assert {item.document.metadata["source"] for item in selected} == {"a.pdf", "b.pdf"}


def test_retrieval_filter_prefers_official_source_when_relevance_is_equal():
    content = "Warfarin tedavisinde vitamin K alimi tutarli tutulmalidir. " * 5
    results = [
        (Document(page_content=content + "Academic review.", metadata={"source": "review.pdf", "authority_tier": 3}), 7.0),
        (Document(page_content=content + "Regulatory label.", metadata={"source": "label.pdf", "authority_tier": 1}), 8.0),
    ]

    selected = filter_retrieval_results("warfarin vitamin K", results, limit=2)

    assert selected[0].document.metadata["source"] == "label.pdf"


def test_retrieval_filter_gives_limited_authority_bonus_to_relevant_official_source():
    results = [
        (
            Document(
                page_content="Warfarin ispanak vitamin K dengesi hakkinda akademik derleme. " * 5,
                metadata={"source": "review.pdf", "authority_tier": 3},
            ),
            7.0,
        ),
        (
            Document(
                page_content="Warfarin vitamin K alimi tutarli tutulmalidir. " * 5,
                metadata={"source": "label.pdf", "authority_tier": 1},
            ),
            8.0,
        ),
    ]

    selected = filter_retrieval_results("warfarin ispanak vitamin K", results, limit=2)

    assert selected[0].document.metadata["source"] == "label.pdf"


def test_health_claim_context_rejects_general_source_without_registry_scope():
    results = [
        (
            Document(
                page_content="Warfarin vitamin K alimi hakkinda genel internet yazisi. " * 5,
                metadata={"source": "general.pdf", "authority_tier": 3},
            ),
            0.1,
        )
    ]

    selected = filter_retrieval_results(
        "warfarin vitamin K",
        results,
        limit=2,
        evidence_context="health_claim",
    )

    assert selected == []


def test_health_claim_context_rejects_forged_registry_metadata():
    metadata = _official_metadata()
    metadata["file_sha256"] = "0" * 64
    results = [
        (
            Document(
                page_content="Warfarin vitamin K alimi tutarli tutulmalidir. " * 5,
                metadata=metadata,
            ),
            0.1,
        )
    ]

    selected = filter_retrieval_results(
        "warfarin vitamin K",
        results,
        limit=2,
        evidence_context="health_claim",
    )

    assert selected == []


def test_health_claim_context_uses_official_scope_when_general_source_conflicts():
    general = Document(
        page_content="Warfarin vitamin K icin genel ve celiskili bir yorum. " * 5,
        metadata={"source": "general.pdf", "authority_tier": 3},
    )
    official = Document(
        page_content="Warfarin tedavisinde vitamin K alimi tutarli tutulmalidir. " * 5,
        metadata=_official_metadata(),
    )

    selected = filter_retrieval_results(
        "warfarin vitamin K",
        [(general, 0.1), (official, 1.0)],
        limit=2,
        evidence_context="health_claim",
    )

    assert [item.document.metadata["source"] for item in selected] == ["fda_warfarin_coumadin_2017.pdf"]


def test_klinik_bilgi_getir_includes_page_and_relevance_metadata(monkeypatch):
    class FakeClinicalDb:
        class Collection:
            @staticmethod
            def count():
                return 0

        _collection = Collection()

        def similarity_search_with_score(self, query, k):
            assert k >= 12
            return [
                (
                    Document(
                        page_content="Warfarin kullanirken vitamin K alimi dengeli ve tutarli tutulmalidir." * 3,
                        metadata={
                            **_official_metadata(r"C:\library\fda_warfarin_coumadin_2017.pdf"),
                            "page": 7,
                        },
                    ),
                    8.4,
                )
            ]

    monkeypatch.setattr(memory, "_klinik_db", FakeClinicalDb())
    monkeypatch.setattr(memory, "_official_klinik_db", FakeClinicalDb())

    evidence = memory.klinik_bilgi_getir("warfarin vitamin K", k_adet=3)

    assert "fda_warfarin_coumadin_2017.pdf, sayfa 7" in evidence
    assert evidence.citations[0]["page"] == 7
    assert evidence.citations[0]["lexical_score"] > 0
    assert "warfarin" in evidence.citations[0]["matched_terms"]
    assert evidence.citations[0]["clinical_review_status"] == "pending"
    assert evidence.citations[0]["review_required"] is True


def test_klinik_bilgi_getir_returns_review_required_when_official_evidence_is_absent(monkeypatch):
    class FakeClinicalDb:
        class Collection:
            @staticmethod
            def count():
                return 0

        _collection = Collection()

        @staticmethod
        def similarity_search_with_score(query, k):
            return [
                (
                    Document(
                        page_content="Warfarin vitamin K hakkinda genel kaynak metni. " * 5,
                        metadata={"source": "general.pdf", "authority_tier": 3},
                    ),
                    0.1,
                )
            ]

    monkeypatch.setattr(memory, "_klinik_db", FakeClinicalDb())
    monkeypatch.setattr(memory, "_official_klinik_db", FakeClinicalDb())

    evidence = memory.klinik_bilgi_getir("warfarin vitamin K", k_adet=2)

    assert evidence == ""
    assert evidence.review_required is True
    assert evidence.clinical_review_status == "not_established"
