import json
import logging
from pathlib import Path

from src.agent_state import create_initial_state
from src.logger import log_failure
import src.menu_agent as menu_agent
import src.nodes as nodes


PRIVATE_MARKERS = (
    "private.person@example.test",
    "+905551112233",
    "warfarin",
    "diyabet",
    "HbA1c=9.7",
    "MODEL_RESPONSE_MARKER_42",
)


def _private_payload() -> str:
    return " | ".join(PRIVATE_MARKERS)


def _assert_private_markers_absent(log_text: str) -> None:
    normalized = log_text.casefold()
    for marker in PRIVATE_MARKERS:
        assert marker.casefold() not in normalized


def _stub_node_prompt(monkeypatch) -> None:
    monkeypatch.setattr(
        nodes.PromptManager,
        "get_agent_prompt",
        staticmethod(lambda *_args, **_kwargs: "template"),
    )
    monkeypatch.setattr(
        nodes.PromptManager,
        "hydrate_prompt",
        staticmethod(lambda *_args, **_kwargs: "hydrated-prompt"),
    )


def test_triage_success_logs_only_operational_metadata(monkeypatch, caplog):
    sensitive = _private_payload()
    state = create_initial_state(
        profil_ozeti=sensitive,
        istek=sensitive,
        hafiza=[sensitive],
        ilaclar=["warfarin"],
    )
    _stub_node_prompt(monkeypatch)
    monkeypatch.setattr(nodes, "invoke_with_model_fallback", lambda *_args, **_kwargs: object())
    monkeypatch.setattr(nodes, "parse_llm_response", lambda _response: sensitive)

    caplog.set_level(logging.INFO, logger="src.nodes")
    result = nodes.onceliklendirme_node(state)

    assert result["klinik_oncelik"] == sensitive
    _assert_private_markers_absent(caplog.text)
    assert "event=clinical_priority_resolved" in caplog.text
    assert "component=triage" in caplog.text
    assert f"output_chars={len(sensitive)}" in caplog.text


def test_supervisor_parse_failure_does_not_log_response_or_exception_text(monkeypatch, caplog):
    sensitive = _private_payload()
    state = create_initial_state(
        profil_ozeti=sensitive,
        istek=sensitive,
        hafiza=[sensitive],
        ilaclar=["warfarin"],
    )
    _stub_node_prompt(monkeypatch)
    monkeypatch.setattr(nodes, "invoke_with_model_fallback", lambda *_args, **_kwargs: object())
    monkeypatch.setattr(nodes, "parse_llm_response", lambda _response: f"not-json {sensitive}")

    caplog.set_level(logging.ERROR, logger="src.nodes")
    result = nodes.supervisor_node(state)

    assert result["next_node"] == "DIETITIAN"
    _assert_private_markers_absent(caplog.text)
    assert "event=supervisor_response_parse" in caplog.text
    assert "status=failed" in caplog.text
    assert "error_type=JSONDecodeError" in caplog.text


def test_menu_guardrail_does_not_log_model_generated_issue_content(monkeypatch, caplog):
    sensitive = _private_payload()
    responses = iter(
        [
            sensitive,
            json.dumps(
                {
                    "is_safe": False,
                    "issues": [sensitive],
                    "corrected_analysis": "Corrected menu analysis with no private markers.",
                }
            ),
        ]
    )
    monkeypatch.setattr(
        menu_agent,
        "invoke_with_model_fallback",
        lambda *_args, **_kwargs: next(responses),
    )
    monkeypatch.setattr(menu_agent, "parse_llm_response", lambda response: response)

    caplog.set_level(logging.INFO, logger="src.menu_agent")
    result = menu_agent.menu_danismani(sensitive, sensitive)

    assert result == "Corrected menu analysis with no private markers."
    _assert_private_markers_absent(caplog.text)
    assert "event=menu_safety_review" in caplog.text
    assert "issue_count=1" in caplog.text


def test_safe_failure_logger_never_serializes_exception_message(caplog):
    logger = logging.getLogger("tests.runtime_log_privacy")
    caplog.set_level(logging.ERROR, logger=logger.name)

    log_failure(
        logger,
        "provider_call",
        RuntimeError(_private_payload()),
        component="llm",
    )

    _assert_private_markers_absent(caplog.text)
    assert "event=provider_call" in caplog.text
    assert "component=llm" in caplog.text
    assert "error_type=RuntimeError" in caplog.text


def test_runtime_code_does_not_use_exception_traceback_logging():
    root = Path(__file__).resolve().parents[1]
    runtime_files = [root / "api.py", *(root / "src").rglob("*.py")]

    offenders = [str(path.relative_to(root)) for path in runtime_files if ".exception(" in path.read_text(encoding="utf-8")]

    assert offenders == []
