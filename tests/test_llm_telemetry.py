"""AI usage telemetry: records anonymized operational metadata only, never breaks
the product request, and never stores sensitive/health/prompt content."""
import json

import pytest

from src import pricing
from src.database import _ensure_db, get_connection, llm_usage_kaydet, llm_usage_ozet
from src.llm_telemetry import (
    anonymize_account,
    extract_usage,
    record_llm_usage,
    set_llm_context,
)


class _FakeMsg:
    def __init__(self, usage):
        self.usage_metadata = usage
        self.content = "ok"


def _rows(test_db_path):
    with get_connection(None) as conn:
        cols = [c[0] for c in conn.execute("SELECT * FROM llm_usage LIMIT 0").description]
        return [dict(zip(cols, r)) for r in conn.execute("SELECT * FROM llm_usage").fetchall()]


def test_record_writes_anonymized_row(test_db_path):
    _ensure_db()
    set_llm_context(feature="curebot", conversation_id="c1", account_id="5551234567", graph_used=True)
    record_llm_usage(model="gemini-2.5-flash", input_tokens=1000, output_tokens=200, total_tokens=1200,
                     cached_tokens=100, image_count=0, latency_ms=900, success=True, retry_count=1)
    rows = _rows(test_db_path)
    assert len(rows) == 1
    row = rows[0]
    assert row["feature"] == "curebot" and row["graph_used"] == 1
    assert row["input_tokens"] == 1000 and row["output_tokens"] == 200 and row["retry_count"] == 1
    assert row["anon_user_id"] == anonymize_account("5551234567")


def test_no_phone_or_content_in_telemetry(test_db_path):
    _ensure_db()
    set_llm_context(feature="curebot", conversation_id="c1", account_id="5551234567")
    record_llm_usage(model="gemini-2.5-flash", input_tokens=10, output_tokens=5)
    blob = json.dumps(_rows(test_db_path), ensure_ascii=False)
    assert "5551234567" not in blob
    # only structured/count fields exist — no free-text prompt/answer columns
    assert set(_rows(test_db_path)[0].keys()).isdisjoint({"istek", "cevap", "prompt", "answer"})


def test_extract_usage_parses_langchain_shape():
    msg = _FakeMsg({"input_tokens": 800, "output_tokens": 300, "total_tokens": 1100,
                    "input_token_details": {"cache_read": 50}})
    usage = extract_usage(msg)
    assert usage == {"input_tokens": 800, "output_tokens": 300, "total_tokens": 1100, "cached_tokens": 50}


def test_extract_usage_defensive_on_missing():
    assert extract_usage(object()) == {"input_tokens": 0, "output_tokens": 0, "total_tokens": 0, "cached_tokens": 0}


def test_pricing_unknown_returns_none_not_fabricated():
    cost, currency = pricing.estimate_cost("gemini-2.5-flash", input_tokens=1000, output_tokens=500)
    assert cost is None  # no verified price configured -> never invented
    assert currency  # currency label still returned


def test_pricing_priced_model_computes(monkeypatch):
    monkeypatch.setitem(
        pricing._TABLE, "priced-model",
        pricing.ModelPrice(input_price=1.0, output_price=2.0, currency="USD"),
    )
    cost, currency = pricing.estimate_cost("priced-model", input_tokens=1_000_000, output_tokens=500_000)
    assert cost == pytest.approx(1.0 + 1.0)  # 1M in * $1 + 0.5M out * $2
    assert currency == "USD"


def test_telemetry_failure_never_raises(test_db_path, monkeypatch):
    def boom(*a, **k):
        raise RuntimeError("db down")
    monkeypatch.setattr("src.database.llm_usage_kaydet", boom)
    # Must swallow the error — the product request must never fail on telemetry.
    record_llm_usage(model="gemini-2.5-flash", input_tokens=1, output_tokens=1)


def test_ozet_aggregates_by_feature(test_db_path):
    _ensure_db()
    set_llm_context(feature="curebot", account_id="u1")
    record_llm_usage(model="m", input_tokens=100, output_tokens=50)
    record_llm_usage(model="m", input_tokens=100, output_tokens=50)
    set_llm_context(feature="menu_analysis", account_id="u2")
    record_llm_usage(model="m", input_tokens=200, output_tokens=80, image_count=1)
    ozet = llm_usage_ozet()
    by = {r["feature"]: r for r in ozet["by_feature"]}
    assert by["curebot"]["calls"] == 2 and by["curebot"]["input_tokens"] == 200
    assert by["menu_analysis"]["images"] == 1
    assert ozet["total_users"] == 2


def test_wrapper_records_usage_and_retry(test_db_path, monkeypatch):
    import src.llm as llm

    calls = {"n": 0}

    class _Model:
        def __init__(self, fail):
            self.fail = fail
        def invoke(self, payload):
            calls["n"] += 1
            if self.fail:
                raise RuntimeError("404 model not_found")
            return _FakeMsg({"input_tokens": 500, "output_tokens": 120, "total_tokens": 620})

    def fake_build(model_name, temperature=0.7):
        # First configured model fails with not_found -> fallback path.
        return _Model(fail=calls["n"] == 0)

    monkeypatch.setattr(llm, "build_llm", fake_build)
    set_llm_context(feature="curebot", account_id="u9")
    resp = llm.invoke_with_model_fallback("merhaba")
    assert resp.usage_metadata["input_tokens"] == 500
    rows = _rows(test_db_path)
    assert len(rows) == 1 and rows[0]["success"] == 1 and rows[0]["retry_count"] == 1
