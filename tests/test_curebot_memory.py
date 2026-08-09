import json
from pathlib import Path
from types import SimpleNamespace

from src.curebot_intent import CureBotIntentPlan
from src.routers.chat import _chat_history_metadata, _local_conversation_context


ROOT = Path(__file__).resolve().parents[1]


def _snapshot():
    return SimpleNamespace(
        target_scope="self",
        history_metadata=lambda: {
            "target_key": "kendim",
            "target_id": "self-1",
            "target_scope": "self",
            "profile_fingerprint": "fingerprint",
        },
    )


def test_chat_metadata_persists_only_structured_suggestion_topics():
    metadata = json.loads(
        _chat_history_metadata(
            _snapshot(),
            CureBotIntentPlan(intent="meal_recommendation", meal_context="dinner"),
            answer_text=(
                "Akşam için iki seçenek düşünebiliriz.\n\n"
                "- **Fırında levrek:** Sebzeyle tamamlanabilir.\n"
                "- **Nohutlu ıspanak:** Ölçülü bir tahılla sunulabilir."
            ),
        )
    )

    assert metadata["recent_suggestion_topics"] == ["Fırında levrek", "Nohutlu ıspanak"]
    assert "Sebzeyle tamamlanabilir" not in json.dumps(metadata, ensure_ascii=False)


def test_local_context_aggregates_recent_topics_without_raw_history():
    logs = [
        {
            "sayfa": "CureBot",
            "istek": "Gizli kullanıcı mesajı",
            "cevap": "- **Sebzeli hindi sote:** Kısa açıklama.",
            "metadata": json.dumps({
                "last_intent": "meal_recommendation",
                "last_meal_context": "dinner",
                "last_answer_type": "practical",
                "last_target_scope": "self",
                "recent_suggestion_topics": ["Sebzeli hindi sote"],
            }),
        },
        {
            "sayfa": "CureBot",
            "istek": "Başka gizli mesaj",
            "cevap": "- **Zeytinyağlı barbunya:** Kısa açıklama.",
            "metadata": json.dumps({"recent_suggestion_topics": ["Zeytinyağlı barbunya"]}),
        },
    ]

    context = _local_conversation_context(logs, _snapshot())

    assert context.recent_suggestion_topics == (
        "Sebzeli hindi sote",
        "Zeytinyağlı barbunya",
    )
    assert "Gizli kullanıcı mesajı" not in context.model_dump_json()


def test_cached_bot_messages_are_rendered_as_safe_markdown():
    widget = (ROOT / "frontend" / "modules" / "chat-widget.js").read_text(encoding="utf-8")

    assert 'type === "bot" && window.formatMarkdownSafe' in widget
    assert "item.innerHTML = formatMarkdownSafe(text);" in widget
