import json
from pathlib import Path
from unittest.mock import patch

from src.models import AileUyesi, Cinsiyet, KullaniciProfili
from src.nodes import _quality_profile_from_snapshot
from src.profile_context import resolve_profile_snapshot_from_profile
from src.curebot_intent import CureBotConversationContext, fallback_intent_plan, resolve_semantic_turn
from src.routers.chat import CureBotResponseContext, _explicit_input_safety_answer


def _register_and_save(client, phone: str, *, diseases=None, allergies=None, medications=None):
    assert client.post(
        "/api/register",
        json={"telefon": phone, "kullanici_adi": "Snapshot Test", "sifre": "123456"},
    ).status_code in (200, 409)
    assert client.post("/api/login", json={"telefon": phone, "sifre": "123456"}).status_code == 200
    response = client.post(
        "/api/profile/save",
        json={
            "kullanici_adi": "Snapshot Test",
            "ad": "Ana Profil",
            "yas": 34,
            "cinsiyet": "erkek",
            "hastaliklar": diseases or [],
            "alerjiler": allergies or [],
            "ilaclar": medications or [],
        },
    )
    assert response.status_code == 200


def _safe_plan():
    return {
        "summary": "Dengeli plan",
        "days": [
            {
                "day": "Pazartesi",
                "breakfast": "Sebzeli karabuğday kasesi",
                "lunch": "Zeytinyağlı sebze yemeği",
                "dinner": "Izgara tavuk ve salata",
                "snacks": ["Armut"],
            }
        ],
    }


def test_resolver_normalizes_self_member_legacy_name_and_family():
    main = AileUyesi(
        id="self-1",
        ad="Ana",
        yas=34,
        cinsiyet=Cinsiyet.ERKEK,
        hastaliklar=["hipertansiyon"],
    )
    member = AileUyesi(
        id="member-1",
        ad="Ece",
        yas=29,
        cinsiyet=Cinsiyet.KADIN,
        alerjiler=["yumurta"],
    )
    profile = KullaniciProfili(ana_kullanici=main, aile_uyeleri=[member])

    self_snapshot = resolve_profile_snapshot_from_profile("account", profile, main.id)
    member_by_id = resolve_profile_snapshot_from_profile("account", profile, member.id)
    member_by_name = resolve_profile_snapshot_from_profile("account", profile, "Ece")
    family = resolve_profile_snapshot_from_profile("account", profile, "aile")

    assert (self_snapshot.target_scope, self_snapshot.target_key) == ("self", "kendim")
    assert member_by_id.state_payload() == member_by_name.state_payload()
    assert member_by_id.target_id == "member-1"
    assert family.target_scope == "family"
    assert set(family.diseases) == {"hipertansiyon"}
    assert set(family.allergies) == {"yumurta"}


def test_rule_engine_input_is_snapshot_not_profile_summary_text():
    snapshot = {
        "diseases": ["hipertansiyon"],
        "allergies": ["yumurta"],
        "medications": ["metformin"],
        "ages": [41],
        "genders": ["kadın"],
        "goals": ["Sağlıklı Yaşam"],
    }

    quality_profile = _quality_profile_from_snapshot(snapshot)

    assert quality_profile["hastaliklar"] == ["hipertansiyon"]
    assert quality_profile["alerjiler"] == ["yumurta"]
    assert quality_profile["ilaclar"] == ["metformin"]
    assert "böbrek" not in json.dumps(quality_profile, ensure_ascii=False).casefold()
    assert "warfarin" not in json.dumps(quality_profile, ensure_ascii=False).casefold()


def test_user_safety_answer_does_not_invent_profile_conditions():
    member = AileUyesi(
        id="self-allergy",
        ad="Ana",
        yas=34,
        cinsiyet=Cinsiyet.ERKEK,
        alerjiler=["yumurta"],
    )
    snapshot = resolve_profile_snapshot_from_profile(
        "account",
        KullaniciProfili(ana_kullanici=member),
        "kendim",
    )

    message = "Yumurtalı tost yiyebilir miyim?"
    conversation = CureBotConversationContext(last_target_scope="self")
    plan = fallback_intent_plan(message, "self", conversation)
    turn = resolve_semantic_turn(
        plan, message, conversation, conversation_id="test", target_profile_id="kendim",
        target_scope="self", target_resolution_source="message_self",
    )
    decision = _explicit_input_safety_answer(CureBotResponseContext(
        turn=turn, snapshot=snapshot, plan=plan, conversation=conversation,
        user_message=message,
    ))

    assert decision is not None
    answer = decision.answer
    assert "yumurta" in answer.casefold()
    assert "böbrek" not in answer.casefold()
    assert "warfarin" not in answer.casefold()
    assert "gut" not in answer.casefold()


def test_personalized_runtime_cannot_reintroduce_direct_profile_reads():
    root = Path(__file__).resolve().parents[1]
    guarded_files = [
        "src/routers/chat.py",
        "src/routers/tools.py",
        "src/routers/grocery.py",
        "src/grocery/profile.py",
        "src/quality/scope_policy.py",
        "src/nodes.py",
    ]
    forbidden = ("profil_getir_db", "hedef_profili_bul", "_quality_profile_from_summary")

    for relative_path in guarded_files:
        source = (root / relative_path).read_text(encoding="utf-8")
        for symbol in forbidden:
            assert symbol not in source, f"{relative_path} bypasses the canonical profile snapshot via {symbol}"


@patch("src.routers.chat.langgraph_app")
@patch("src.routers.chat.hafizadakini_getir", return_value=[])
def test_chat_snapshot_and_history_metadata_share_same_target(mock_memory, mock_graph, client):
    _register_and_save(client, "5557001001", diseases=["hipertansiyon"])
    family = client.post(
        "/api/family/add",
        json={
            "ad": "Ece",
            "yas": 29,
            "cinsiyet": "kadın",
            "hastaliklar": ["çölyak"],
            "alerjiler": ["yumurta"],
            "ilaclar": ["levotiroksin"],
        },
    )
    assert family.status_code == 200
    member_id = family.json()["uye_id"]
    response = client.post(
        "/api/chat",
        json={"mesaj": "Kahvaltı önerir misin?", "kimin_icin": member_id},
    )
    assert response.status_code == 200

    history = client.get("/api/history?limit=20").json()["loglar"]
    chat_log = next(item for item in history if item["eylem"] == "CureBot")
    metadata = json.loads(chat_log["metadata"])
    assert metadata["target_id"] == member_id
    assert metadata["target_scope"] == "member"
    assert metadata["profile_fingerprint"]


def test_smart_grocery_uses_member_snapshot_and_matching_history_metadata(client):
    _register_and_save(
        client,
        "5557001003",
        diseases=["evre 3 kronik böbrek hastalığı", "gut"],
        allergies=["inek sütü proteini"],
        medications=["warfarin"],
    )
    family = client.post(
        "/api/family/add",
        json={
            "ad": "Ece",
            "yas": 29,
            "cinsiyet": "kadın",
            "hastaliklar": [],
            "alerjiler": [],
            "ilaclar": [],
        },
    )
    assert family.status_code == 200
    member_id = family.json()["uye_id"]

    response = client.post(
        "/api/smart-grocery",
        json={
            "kimin_icin": member_id,
            "shopping_items": [{"name": "Yoğurt", "quantity": "1 kase"}],
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["avoid_items"] == 0
    assert [item["name"] for item in body["items"]] == ["Yoğurt"]

    history = client.get("/api/history?limit=20").json()["loglar"]
    grocery_log = next(item for item in history if item["eylem"] == "Smart Grocery")
    metadata = json.loads(grocery_log["metadata"])
    assert metadata["target_id"] == member_id
    assert metadata["target_scope"] == "member"
    assert metadata["profile_fingerprint"]
    serialized = json.dumps(body, ensure_ascii=False).casefold()
    for stale_term in ("böbrek", "warfarin", "gut", "inek sütü proteini"):
        assert stale_term not in serialized


@patch("src.routers.tools.hafizadakini_getir", return_value=[])
@patch("src.routers.tools.haftalik_plan_olustur", return_value=_safe_plan())
def test_weekly_plan_uses_member_snapshot_and_matching_history_metadata(mock_plan, mock_memory, client):
    _register_and_save(
        client,
        "5557001004",
        diseases=["evre 3 kronik böbrek hastalığı", "gut"],
        medications=["warfarin"],
    )
    family = client.post(
        "/api/family/add",
        json={
            "ad": "Ece",
            "yas": 29,
            "cinsiyet": "kadın",
            "hastaliklar": [],
            "alerjiler": [],
            "ilaclar": [],
        },
    )
    assert family.status_code == 200
    member_id = family.json()["uye_id"]

    response = client.post("/api/weekly-plan", json={"kimin_icin": member_id})
    assert response.status_code == 200
    profile_summary = mock_plan.call_args.args[0].casefold()
    for stale_term in ("böbrek", "warfarin", "gut"):
        assert stale_term not in profile_summary

    history = client.get("/api/history?limit=20").json()["loglar"]
    plan_log = next(item for item in history if item["eylem"] == "Haftalık Plan")
    metadata = json.loads(plan_log["metadata"])
    assert metadata["target_id"] == member_id
    assert metadata["target_scope"] == "member"
    assert metadata["profile_fingerprint"]
    assert metadata["artifact_type"] == "weekly_plan"
    assert metadata["artifact_schema_version"] == 3
    assert isinstance(metadata["health_considerations"], list)
    persisted_plan = json.loads(plan_log["asistan_ciktisi"])
    assert persisted_plan["days"]
    assert persisted_plan["compatibility"] == response.json()["compatibility"]


@patch("src.routers.chat.langgraph_app")
@patch("src.routers.chat.hafizadakini_getir")
@patch("src.routers.tools.hafizadakini_getir")
@patch("src.routers.tools.haftalik_plan_olustur", return_value=_safe_plan())
def test_profile_switch_isolates_memory_history_and_response(
    mock_plan,
    mock_plan_memory,
    mock_chat_memory,
    mock_graph,
    client,
):
    _register_and_save(
        client,
        "5557001002",
        diseases=["evre 3 kronik böbrek hastalığı", "gut"],
        medications=["warfarin"],
    )
    namespaces = []
    heavy_memory = ["Profil A: böbrek hastalığı, warfarin ve gut kaydı"]

    def memory_side_effect(namespace, *_args):
        namespaces.append(namespace)
        return heavy_memory if namespace == namespaces[0] else []

    mock_chat_memory.side_effect = memory_side_effect
    mock_plan_memory.side_effect = memory_side_effect
    first_chat = client.post(
        "/api/chat",
        json={"mesaj": "Akşam için bir seçenek öner", "kimin_icin": "kendim"},
    )
    assert first_chat.status_code == 200
    first_plan = client.post("/api/weekly-plan", json={"kimin_icin": "kendim"})
    assert first_plan.status_code == 200
    history_after_plan = client.get("/api/history?limit=20").json()["loglar"]
    first_chat_log = next(item for item in history_after_plan if item["eylem"] == "CureBot")
    first_snapshot = json.loads(first_chat_log["metadata"])
    plan_log = next(item for item in history_after_plan if item["eylem"] == "Haftalık Plan")
    plan_metadata = json.loads(plan_log["metadata"])
    assert plan_metadata["target_id"] == first_snapshot["target_id"]
    assert plan_metadata["target_scope"] == first_snapshot["target_scope"]
    assert plan_metadata["profile_fingerprint"] == first_snapshot["profile_fingerprint"]

    save_b = client.post(
        "/api/profile/save",
        json={
            "kullanici_adi": "Snapshot Test",
            "ad": "Ana Profil",
            "yas": 34,
            "cinsiyet": "erkek",
            "hastaliklar": [],
            "alerjiler": [],
            "ilaclar": [],
        },
    )
    assert save_b.status_code == 200

    second_chat = client.post(
        "/api/chat",
        json={"mesaj": "Kahvaltı için bir seçenek öner", "kimin_icin": "kendim"},
    )
    assert second_chat.status_code == 200

    history_after_second_chat = client.get("/api/history?limit=20").json()["loglar"]
    chat_logs = [item for item in history_after_second_chat if item["eylem"] == "CureBot"]
    second_snapshot = json.loads(chat_logs[0]["metadata"])
    assert first_snapshot["profile_fingerprint"] != second_snapshot["profile_fingerprint"]
    assert namespaces[0] != namespaces[-1]
    combined_context = json.dumps(
        {
            "snapshot": second_snapshot,
        },
        ensure_ascii=False,
    ).casefold()
    response_text = second_chat.text.casefold()
    for stale_term in ("böbrek", "warfarin", "gut"):
        assert stale_term not in combined_context
        assert stale_term not in response_text
