from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_smart_grocery_visible_text_mojibake_yok():
    app_js = (ROOT / "frontend" / "app.js").read_text(encoding="utf-8")
    start = app_js.index("function ensureSmartGroceryModal")
    end = app_js.index("window.askRecipeForWeeklyPlan", start)
    smart_grocery_block = app_js[start:end]

    for token in ["AkÄ", "KaÃ", "SaÄ", "TÃ¼rkiye", "Â·", "FiyatlandÄ", "gÃ¶re"]:
        assert token not in smart_grocery_block


def test_nodes_legacy_numeric_passthrough_yok():
    nodes_py = (ROOT / "src" / "nodes.py").read_text(encoding="utf-8")

    assert "short_or_numeric_selection" not in nodes_py
    assert "legacy_short_selection_guard_disabled" not in nodes_py
    assert "status=\"passthrough\"" not in nodes_py
