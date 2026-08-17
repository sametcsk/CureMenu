"""Static regression guards for the beta-admin conversation modal.

These do not need a browser: they assert the exact CSS/JS invariants whose
absence caused the production bug (the overlay could never be hidden because a
bare `.hidden` lost to `.overlay` on specificity, so "Kapat" did nothing and the
empty modal showed on load).
"""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HTML = (ROOT / "frontend" / "beta-admin.html").read_text(encoding="utf-8")
JS = (ROOT / "frontend" / "modules" / "beta-admin.js").read_text(encoding="utf-8")


def test_overlay_hidden_rule_beats_overlay_display():
    # The specific rule must exist so `.overlay.hidden` actually hides the modal.
    assert ".overlay.hidden{display:none}" in HTML


def test_html_references_bumped_script_version():
    # Cache-bust so the fixed JS is fetched instead of a stale cached copy.
    assert "beta-admin.js?v=2" in HTML


def test_modal_ids_match_between_html_and_js():
    for element_id in ("thread-overlay", "thread-close", "thread-title", "thread-status", "thread-body"):
        assert f'id="{element_id}"' in HTML, element_id
        assert element_id in JS, element_id


def test_close_button_is_wired_and_hides_overlay():
    assert "byId('thread-close').addEventListener('click', closeThread)" in JS
    assert "classList.add('hidden')" in JS  # closeThread hides the overlay


def test_escape_key_closes_modal():
    assert "'Escape'" in JS
    assert "keydown" in JS


def test_reopen_clears_previous_conversation():
    # loadConversation resets the body, and closeThread also clears it.
    assert "byId('thread-body').innerHTML = ''" in JS


def test_loading_and_empty_states_are_handled():
    assert "Yükleniyor..." in JS
    assert "Bu konuşmada kayıt bulunamadı." in JS
