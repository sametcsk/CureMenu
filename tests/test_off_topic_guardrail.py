import pytest
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient
from api import app

client = TestClient(app)

from src.auth import get_current_user

@pytest.fixture
def mock_auth():
    app.dependency_overrides[get_current_user] = lambda: "05000000000"
    yield
    app.dependency_overrides = {}

@pytest.fixture
def mock_profile():
    with patch("src.routers.chat.resolve_profile_snapshot") as mock:
        snapshot = MagicMock()
        snapshot.target_key = "kendim"
        snapshot.target_name = "Test User"
        snapshot.target_scope = "self"
        snapshot.allergies = []
        snapshot.diseases = []
        snapshot.medications = []
        snapshot.memory_namespace = "test_memory_namespace"
        snapshot.state_payload.return_value = {"isim": "Test User"}
        snapshot.history_metadata.return_value = {}
        mock.return_value = snapshot
        yield mock

@pytest.mark.parametrize("off_topic_msg", [
    "Bugün hava nasıl?",
    "Bana komik bir fıkra anlat",
    "React JS ile bir butonu nasıl ortalarım?",
    "Türkiye'nin başkenti neresidir?",
])
def test_off_topic_guardrail(mock_auth, mock_profile, off_topic_msg):
    response = client.post(
        "/api/chat",
        json={"mesaj": off_topic_msg, "kimin_icin": "kendim", "gecmis": []},
        cookies={"token": "fake_token"}
    )
    
    assert response.status_code == 200
    assert "Ben beslenme ve sağlık odaklı bir asistanım." in response.text
