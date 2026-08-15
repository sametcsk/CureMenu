from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_chat_cache_is_account_conversation_scoped_not_profile_scoped():
    source = (ROOT / "frontend/modules/chat-widget.js").read_text(encoding="utf-8")
    assert "cm_chat_v3_${accountKey}_${conversationId}" in source
    assert "conversation_id: conversationId" in source
    assert "context.targetScope" not in source[source.index("getConversationCacheKey()"):source.index("readCachedConversation()")]


def test_profile_dropdown_does_not_reload_or_replace_curebot_conversation():
    source = (ROOT / "frontend/modules/profile-family-manager.js").read_text(encoding="utf-8")
    assert "selectId === 'chatTarget'" not in source


def test_logout_removes_only_owned_v3_conversation_keys():
    source = (ROOT / "frontend/modules/auth-manager.js").read_text(encoding="utf-8")
    assert "cm_chat_v3_${normalizedAccountKey}_" in source
    assert "cm_chat_conversation_${normalizedAccountKey}" in source
