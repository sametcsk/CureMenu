from datetime import datetime
from types import SimpleNamespace
from unittest.mock import patch

from src.economist_agent import alisveris_ve_butce_hesapla


@patch(
    "src.economist_agent.invoke_with_model_fallback",
    side_effect=[
        SimpleNamespace(content="Yulaf, elma"),
        SimpleNamespace(content="2024 Türkiye fiyatlarıyla tahmini toplam 100 TL"),
    ],
)
def test_budget_report_replaces_stale_year_and_discloses_estimate(mock_invoke):
    report = alisveris_ve_butce_hesapla("Pazartesi kahvaltı: yulaf ve elma")

    assert mock_invoke.call_count == 2
    assert "2024" not in report
    assert str(datetime.now().year) in report
    assert "canlı fiyat değildir" in report.casefold()
