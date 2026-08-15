"""Acceptance tests for CureBot profile identity, continuity and artifact recall.

Covers the product spec's acceptance cases end-to-end through /api/chat:
- Faz 2: profile-scoped weekly-plan / menu-analysis recall from interaction_logs,
  fail-closed when the target has no artifact, never another profile.
- Follow-up continuity: a no-reference follow-up keeps the previous target; an
  explicit self/relationship reference switches it.
- Profile isolation: the account owner's health context never leaks into a family
  member's answer.

Ayşe (owner): warfarin, metformin, diyabet, böbrek.
Mert (son, <18): çölyak, yer fıstığı.
"""
import json
import random
import string
from unittest.mock import patch

from src.database import etkilesim_logla


def _setup(client, phone, *, owner_name="Ayşe", member_name="Mert"):
    client.post("/api/register", json={"telefon": phone, "kullanici_adi": owner_name, "sifre": "123456"})
    client.post("/api/login", json={"telefon": phone, "sifre": "123456"})
    assert client.post("/api/profile/save", json={
        "kullanici_adi": owner_name, "ad": owner_name, "yas": 45, "cinsiyet": "kadın",
        "hastaliklar": ["diyabet", "böbrek hastalığı"], "alerjiler": [],
        "ilaclar": ["warfarin", "metformin"],
    }).status_code == 200
    fam = client.post("/api/family/add", json={
        "ad": member_name, "yas": 12, "cinsiyet": "erkek", "yakinlik": "oğul",
        "hastaliklar": ["çölyak"], "alerjiler": ["yer fıstığı"],
    })
    assert fam.status_code == 200
    mert_id = fam.json()["uye_id"]
    me = client.get("/api/profile/me").json()
    return phone, me["profil"]["ana_kullanici"]["id"], mert_id, me["profile_fingerprints"]


def _seed(phone, name, target_id, scope, fingerprint, sayfa, cevap, **extra_metadata):
    metadata = {"target_id": target_id, "target_scope": scope, "profile_fingerprint": fingerprint}
    metadata.update(extra_metadata)
    etkilesim_logla(phone, name, sayfa, "seed", cevap, json.dumps(metadata, ensure_ascii=False))


def _latest_curebot_target(client):
    logs = client.get("/api/history?limit=50").json()["loglar"]
    for item in logs:  # newest first
        if item.get("eylem") == "CureBot":
            try:
                return json.loads(item.get("metadata") or "{}").get("target_id")
            except (TypeError, json.JSONDecodeError):
                return None
    return None


@patch("src.routers.chat.hafizadakini_getir", return_value=[])
def test_F_menu_recall_uses_only_target_artifact(_mem, client):
    phone, _main_id, mert_id, fps = _setup(client, "5559990001")
    _seed(phone, "Mert", mert_id, "member", fps["members"][mert_id], "Menü Analizi",
          "### Profil İçin Zorunlu Güvenlik Uyarıları\n"
          "- Çölyak nedeniyle glutensiz içerik ve çapraz bulaş riski\n"
          "- Yer fıstığı alerjisi nedeniyle içerik kontrolü\n\nMenü analiz metni.",
          artifact_type="menu_analysis",
          artifact_schema_version=3,
          evidence_findings=[
              {
                  "restriction_type": "disease",
                  "restriction_identifier": "çölyak",
                  "evidence_level": "INFERRED-LIKELY",
                  "evidence_source": "menu_category_inference",
                  "matched_ingredient": "gluten içerebilen ürün",
                  "explanation": "Çapraz bulaş olasılığı işletmeden teyit edilmeli.",
                  "target_profile_id": mert_id,
                  "artifact_reference": "menu_analysis",
              }
          ],
          detected_risks=[
              "Çölyak nedeniyle glutensiz içerik ve çapraz bulaş riski",
              "Yer fıstığı alerjisi nedeniyle içerik kontrolü",
          ],
          clinical_safety_notices=["18 yaş altı için genel porsiyon notu"],
    )
    resp = client.post("/api/chat", json={"mesaj": "oğlumun geçen menü analizindeki ana risk neydi", "kimin_icin": "kendim"})
    assert resp.status_code == 200
    body = resp.text.lower()
    assert "çölyak" in body or "gluten" in body
    assert "warfarin" not in body and "diyabet" not in body  # owner context must not leak
    assert "18 yaş" not in body


@patch("src.routers.chat.hafizadakini_getir", return_value=[])
def test_legacy_menu_record_without_structured_findings_fails_closed(_mem, client):
    phone, _main_id, mert_id, fps = _setup(client, "5559990006")
    _seed(
        phone, "Mert", mert_id, "member", fps["members"][mert_id], "Menü Analizi",
        "### Genel Güvenlik Uyarısı\n- 18 yaş altı için porsiyonları uzmanla değerlendirin.",
    )
    resp = client.post("/api/chat", json={
        "mesaj": "oğlumun geçen menü analizindeki ana risk neydi",
        "kimin_icin": "kendim",
    })
    assert resp.status_code == 200
    assert "spesifik bir risk bulgusu" in resp.text.lower()
    assert "ana risk" not in resp.text.lower() or "18 yaş" not in resp.text.lower()


@patch("src.routers.chat.hafizadakini_getir", return_value=[])
def test_G_menu_recall_missing_is_fail_closed(_mem, client):
    phone, _main_id, _mert_id, _fps = _setup(client, "5559990002")
    resp = client.post("/api/chat", json={"mesaj": "oğlumun geçen menü analizindeki ana risk neydi", "kimin_icin": "kendim"})
    assert resp.status_code == 200
    body = resp.text.lower()
    assert "erişemiyorum" in body
    assert "warfarin" not in body  # no fallback to owner


@patch("src.routers.chat.hafizadakini_getir", return_value=[])
def test_E_weekly_plan_recall_uses_real_artifact(_mem, client):
    phone, main_id, _mert_id, fps = _setup(client, "5559990003")
    plan = {"summary": "s", "days": [], "warnings": [
        "Warfarin nedeniyle K vitamini tüketiminde tutarlılık",
        "Diyabet nedeniyle karbonhidrat dengesi",
        "Böbrek durumu nedeniyle tuz/protein yükü",
    ]}
    _seed(phone, "Ayşe", main_id, "self", fps["self"], "Haftalık Plan", json.dumps(plan, ensure_ascii=False))
    resp = client.post("/api/chat", json={"mesaj": "bu haftaki planımda nelere dikkat ettin", "kimin_icin": "kendim"})
    assert resp.status_code == 200
    body = resp.text
    assert ("K vitamini" in body) or ("karbonhidrat" in body)
    assert "çölyak" not in body.lower() and "fıstık" not in body.lower()  # member context must not leak


@patch("src.routers.chat.hafizadakini_getir", return_value=[])
def test_weekly_plan_recall_uses_structured_generation_metadata(_mem, client):
    phone, main_id, _mert_id, fps = _setup(client, "5559990007")
    _seed(
        phone, "Ayşe", main_id, "self", fps["self"], "Haftalık Plan",
        json.dumps({
            "summary": "s",
            "days": [],
            "warnings": ["Özel sağlık durumları için uzmanınıza danışın."],
        }, ensure_ascii=False),
        artifact_type="weekly_plan",
        artifact_schema_version=2,
        health_considerations=[
            "Warfarin kaydı nedeniyle K vitamini tüketiminde tutarlılık gözetildi.",
            "Diyabet kaydı planın kişiselleştirme bağlamına dahil edildi.",
        ],
    )
    resp = client.post("/api/chat", json={
        "mesaj": "bu haftaki planımda özellikle nelere dikkat ettin",
        "kimin_icin": "kendim",
    })
    assert resp.status_code == 200
    assert "K vitamini" in resp.text
    assert "uzmanınıza danışın" not in resp.text
    assert "çölyak" not in resp.text.lower()


@patch("src.routers.tools.hafizadakini_getir", return_value=[])
@patch("src.routers.tools.haftalik_plan_olustur")
def test_weekly_plan_endpoint_persists_canonical_ingredients_and_curebot_recalls_them(
    mock_plan, _plan_memory, client,
):
    _phone, _main_id, _child_id, _fps = _setup(client, "5559990012")
    mock_plan.return_value = {
        "days": [{
            "day": "Pazartesi",
            "breakfast": "Yulaf kasesi",
            "lunch": "Tavuklu salata",
            "dinner": "Sebze tabağı",
            "snacks": [],
            "notes": [],
            "meal_details": {
                "breakfast": {
                    "name": "Yulaf kasesi",
                    "ingredients": ["1 su bardağı glutensiz yulaf", "glutensiz yulaf"],
                },
                "lunch": {
                    "name": "Tavuklu salata",
                    "ingredients": ["200 g derisiz tavuk göğsü, küp doğranmış", "tavuk göğsü"],
                },
                "dinner": {
                    "name": "Sebze tabağı",
                    "ingredients": ["1 adet orta boy havuç, rendelenmiş", "havuç"],
                },
            },
        }],
        "summary": "Yapılandırılmış plan",
        "warnings": [],
        "confidence": {},
    }

    response = client.post("/api/weekly-plan", json={"kimin_icin": "kendim"})
    assert response.status_code == 200

    history = client.get("/api/history?limit=30").json()["loglar"]
    plan_log = next(item for item in history if item["eylem"] == "Haftalık Plan")
    metadata = json.loads(plan_log["metadata"])
    assert metadata["artifact_schema_version"] == 3
    assert metadata["raw_ingredients"] == [
        "1 su bardağı glutensiz yulaf",
        "glutensiz yulaf",
        "200 g derisiz tavuk göğsü, küp doğranmış",
        "tavuk göğsü",
        "1 adet orta boy havuç, rendelenmiş",
        "havuç",
    ]
    assert metadata["normalized_ingredients"] == ["glutensiz yulaf", "tavuk", "havuç"]
    assert metadata["ingredient_catalog_version"]
    assert metadata["unresolved_ingredients"] == []
    records = {item["canonical_name"]: item for item in metadata["ingredient_records"]}
    assert records["glutensiz yulaf"]["safety_descriptors"] == ["glutensiz"]
    assert records["tavuk"]["quantity"] == "200"
    assert records["tavuk"]["unit"] == "g"
    assert records["tavuk"]["preparation_descriptors"] == ["derisiz", "küp doğranmış"]

    recall = client.post("/api/chat", json={
        "mesaj": "Bu haftaki planımda hangi malzemeler vardı?",
        "kimin_icin": "kendim",
        "conversation_id": "conv_weekly_ingredient_recall",
    })
    assert recall.status_code == 200
    assert recall.text.count("- tavuk") == 1
    assert "glutensiz yulaf" in recall.text
    assert "havuç" in recall.text
    assert "su bardağı" not in recall.text
    assert "uzmanınıza danışın" not in recall.text


@patch("src.routers.chat.hafizadakini_getir", return_value=[])
def test_legacy_weekly_plan_does_not_reparse_raw_text_as_canonical_ingredients(_mem, client):
    phone, main_id, _child_id, fps = _setup(client, "5559990013")
    _seed(
        phone,
        "Ayşe",
        main_id,
        "self",
        fps["self"],
        "Haftalık Plan",
        json.dumps({"summary": "Eski plan", "days": []}, ensure_ascii=False),
        artifact_type="weekly_plan",
        artifact_schema_version=2,
    )

    recall = client.post("/api/chat", json={
        "mesaj": "Bu haftaki planımda hangi malzemeler vardı?",
        "kimin_icin": "kendim",
    })

    assert recall.status_code == 200
    assert "eski formatta" in recall.text
    assert "standart malzeme listesine erişemiyorum" in recall.text


@patch("src.routers.chat.langgraph_app")
@patch("src.routers.chat.generate_curebot_natural_answer", return_value="Tamam, işte birkaç seçenek.")
@patch("src.routers.chat.plan_curebot_semantically")
@patch("src.routers.chat.hafizadakini_getir", return_value=[])
def test_followup_continuity_switches_only_on_explicit_reference(_mem, mock_plan, _nat, _graph, client):
    from src.curebot_intent import CureBotIntentPlan
    mock_plan.return_value = CureBotIntentPlan(intent="meal_recommendation", meal_context="unknown", needs_safety_gate=False)
    phone, main_id, mert_id, _fps = _setup(client, "5559990004")

    client.post("/api/chat", json={"mesaj": "Oğlum için tost uygun mu?", "kimin_icin": "kendim"})
    assert _latest_curebot_target(client) == mert_id           # relationship -> Mert

    client.post("/api/chat", json={"mesaj": "Peki ayran?", "kimin_icin": "kendim"})
    assert _latest_curebot_target(client) == mert_id           # no reference -> continuity (Mert)

    client.post("/api/chat", json={"mesaj": "Benim için peki?", "kimin_icin": "kendim"})
    assert _latest_curebot_target(client) == main_id           # explicit self -> Ayşe

    client.post("/api/chat", json={"mesaj": "Oğlumunki?", "kimin_icin": "kendim"})
    assert _latest_curebot_target(client) == mert_id           # relationship again -> Mert


@patch("src.routers.chat.langgraph_app")
@patch("src.routers.chat.generate_curebot_natural_answer", return_value="Tamam, profil bağlamına göre değerlendirdim.")
@patch("src.routers.chat.plan_curebot_semantically")
@patch("src.routers.chat.hafizadakini_getir", return_value=[])
def test_one_conversation_switches_targets_without_splitting_or_cross_session_leak(
    _mem, mock_plan, _nat, _graph, client,
):
    from src.curebot_intent import CureBotIntentPlan

    mock_plan.return_value = CureBotIntentPlan(
        intent="meal_recommendation",
        meal_context="dinner",
        needs_safety_gate=False,
    )
    _phone, _main_id, child_id, _fps = _setup(client, "5559990008")
    conversation_id = "conv_acceptance_household_001"

    turns = [
        ("Benim için bu akşam ıspanaklı börek ve ayran uygun mu?", "kendim"),
        ("Oğlum için bugün okul çıkışı tost ve ayran uygun mu?", child_id),
        ("Peki pizza?", child_id),
        ("Benim için peki?", "kendim"),
        ("Oğlumunki?", child_id),
        ("Peki onun için daha güvenli ne seçebiliriz?", child_id),
    ]
    for message, expected_target in turns:
        response = client.post("/api/chat", json={
            "mesaj": message,
            "kimin_icin": "kendim",
            "conversation_id": conversation_id,
        })
        assert response.status_code == 200
        assert response.headers["X-CureMenu-Resolved-Target"] == expected_target

    logs = client.get("/api/history?limit=50").json()["loglar"]
    conversation_metadata = []
    for item in logs:
        if item.get("eylem") != "CureBot":
            continue
        metadata = json.loads(item.get("metadata") or "{}")
        if metadata.get("conversation_id") == conversation_id:
            conversation_metadata.append(metadata)
    assert len(conversation_metadata) == len(turns)
    assert {item["target_resolution_source"] for item in conversation_metadata} >= {
        "message_self", "message_relationship", "continuity", "pronoun",
    }

    # A separate conversation must not inherit the child target from the first.
    restarted = client.post("/api/chat", json={
        "mesaj": "Peki pizza?",
        "kimin_icin": "kendim",
        "conversation_id": "conv_acceptance_household_002",
    })
    assert restarted.status_code == 200
    assert restarted.headers["X-CureMenu-Resolved-Target"] == "kendim"


@patch("src.routers.chat.hafizadakini_getir", return_value=[])
def test_deterministic_safety_turn_commits_new_object_and_target_switch_keeps_it(
    _mem, client, monkeypatch,
):
    from src.curebot_intent import fallback_intent_plan

    phone = "5559990011"
    suffix = "".join(random.Random(phone).choices(string.ascii_letters, k=8))
    _phone, main_id, child_id, _fps = _setup(
        client,
        phone,
        owner_name=f"Owner {suffix}",
        member_name=f"Member {suffix}",
    )
    conversation_id = "conv_safety_state_commit"

    def local_plan(message, conversation, target, _profile_names, _health_flags):
        return fallback_intent_plan(message, target, conversation)

    async def graph_must_not_run(_state):
        raise AssertionError("Bounded conversation paths must not reach the model graph")
        yield  # pragma: no cover

    monkeypatch.setattr("src.routers.chat.plan_curebot_semantically", local_plan)
    monkeypatch.setattr(
        "src.routers.chat.generate_curebot_natural_answer",
        lambda *_args, **_kwargs: "Profil bağlamında kısa bir değerlendirme.",
    )
    monkeypatch.setattr(
        "src.routers.chat._intent_fast_answer",
        lambda *_args, **_kwargs: "Profil bağlamında kısa bir değerlendirme.",
    )
    monkeypatch.setattr("src.routers.chat.langgraph_app.astream", graph_must_not_run)

    turns = [
        ("Benim için mercimek çorbası uygun mu?", "kendim"),
        ("Oğlum için tost uygun mu?", child_id),
        ("Peki yer fıstığı?", child_id),
        ("Benim için?", "kendim"),
        ("Oğlumunki?", child_id),
    ]
    for message, expected_target in turns:
        response = client.post("/api/chat", json={
            "mesaj": message,
            "kimin_icin": "kendim",
            "conversation_id": conversation_id,
        })
        assert response.status_code == 200
        assert response.headers["X-CureMenu-Resolved-Target"] == expected_target

    logs = client.get("/api/history?limit=50").json()["loglar"]
    states = {
        item["kullanici_girdisi"]: json.loads(item.get("metadata") or "{}")
        for item in logs
        if item.get("eylem") == "CureBot"
        and json.loads(item.get("metadata") or "{}").get("conversation_id") == conversation_id
    }

    assert len(states) == 5
    safety_state = states["Peki yer fıstığı?"]
    assert safety_state["response_path"] == "deterministic_safety"
    assert safety_state["state_committed"] is True
    assert safety_state["last_object"] == "yer fistigi"
    assert safety_state["last_object_type"] == "food"
    assert states["Benim için?"]["target_id"] == main_id
    assert states["Benim için?"]["target_profile_id"] == "kendim"
    assert states["Benim için?"]["last_object"] == "yer fistigi"
    assert states["Oğlumunki?"]["target_id"] == child_id
    assert states["Oğlumunki?"]["target_profile_id"] == child_id
    assert states["Oğlumunki?"]["last_object"] == "yer fistigi"


@patch("src.routers.chat.hafizadakini_getir", return_value=[])
def test_real_household_conversation_preserves_semantics_artifacts_and_profile_isolation(
    _mem, client, monkeypatch,
):
    from src.curebot_intent import fallback_intent_plan

    phone, main_id, child_id, fps = _setup(client, "5559990010")
    conversation_id = "conv_real_household_regression"
    _seed(
        phone,
        "Ayşe",
        main_id,
        "self",
        fps["self"],
        "Haftalık Plan",
        json.dumps({"warnings": []}, ensure_ascii=False),
        artifact_type="weekly_plan",
        artifact_schema_version=2,
        health_considerations=[
            "Warfarin kaydı nedeniyle K vitamini tüketiminde tutarlılık gözetildi.",
            "Diyabet kaydı nedeniyle karbonhidrat dengesi gözetildi.",
        ],
    )
    _seed(
        phone,
        "Mert",
        child_id,
        "member",
        fps["members"][child_id],
        "Menü Analizi",
        "Menü analiz metni",
        artifact_type="menu_analysis",
        artifact_schema_version=3,
        evidence_findings=[
            {
                "restriction_type": "disease",
                "restriction_identifier": "çölyak",
                "evidence_level": "CONFIRMED",
                "evidence_source": "structured_ingredient_list",
                "matched_ingredient": "glutenli içerik",
                "target_profile_id": child_id,
                "artifact_reference": "menu_analysis",
            },
            {
                "restriction_type": "allergy",
                "restriction_identifier": "yer fıstığı",
                "evidence_level": "INFERRED-LIKELY",
                "evidence_source": "menu_category_inference",
                "matched_ingredient": "sos",
                "target_profile_id": child_id,
                "artifact_reference": "menu_analysis",
            },
        ],
        detected_risks=[
            "Çölyak nedeniyle gluten ve çapraz bulaş riski.",
            "Yer fıstığı alerjisi nedeniyle içerik teyidi gerekir.",
        ],
    )

    natural_calls = []

    def local_plan(message, conversation, target, _profile_names, _health_flags):
        return fallback_intent_plan(message, target, conversation)

    def natural_answer(plan, snapshot, message, _safety_context="", conversation_context=None, resolved_turn=None):
        natural_calls.append((message, plan, conversation_context, snapshot.target_scope))
        if snapshot.target_scope == "member":
            assert "warfarin" not in {item.casefold() for item in snapshot.medications}
            assert "diyabet" not in " ".join(snapshot.diseases).casefold()
            return "Seçili aile üyesi için çölyak ve yer fıstığı bağlamında daha güvenli bir alternatif seçebiliriz."
        assert "çölyak" not in " ".join(snapshot.diseases).casefold()
        assert "yer fıstığı" not in " ".join(snapshot.allergies).casefold()
        return "Kendi profiliniz için Warfarin ve diyabet bağlamında değerlendirdim."

    def fast_answer(context):
        snapshot = context.snapshot
        message = context.response_input
        if "warfarin" in message.casefold():
            return (
                "Warfarin kullanırken brokoli ve ıspanağı otomatik olarak tamamen bırakmak yerine "
                "K vitamini tüketimini düzenli ve tutarlı tutmak gerekir."
            )
        if snapshot.target_scope == "member":
            return "Seçili aile üyesinin çölyak ve yer fıstığı kayıtlarına göre değerlendirdim."
        return "Kendi profilinizdeki Warfarin ve diyabet kayıtlarına göre değerlendirdim."

    async def graph_must_not_run(_state):
        raise AssertionError("Regression conversation must use bounded local paths")
        yield  # pragma: no cover

    monkeypatch.setattr("src.routers.chat.plan_curebot_semantically", local_plan)
    monkeypatch.setattr("src.routers.chat.generate_curebot_natural_answer", natural_answer)
    monkeypatch.setattr("src.routers.chat._intent_fast_answer", fast_answer)
    monkeypatch.setattr("src.routers.chat.langgraph_app.astream", graph_must_not_run)

    turns = [
        ("Benim için bu akşam ıspanaklı börek ve ayran uygun mu?", "kendim", "self"),
        ("Oğlum için bugün okul çıkışı tost ve ayran uygun mu?", child_id, "member"),
        ("Peki pizza?", child_id, "member"),
        ("Benim için peki?", "kendim", "self"),
        ("Oğlumunki?", child_id, "member"),
        ("Warfarin kullandığım için brokoli ve ıspanağı tamamen bırakmalı mıyım?", "kendim", "self"),
        ("Bu haftaki planımda özellikle nelere dikkat ettin?", "kendim", "self"),
        ("Oğlumun geçen menü analizindeki en önemli risk neydi?", child_id, "member"),
        ("Peki onun için daha güvenli ne seçebiliriz?", child_id, "member"),
    ]
    responses = []
    for message, expected_target, expected_scope in turns:
        response = client.post("/api/chat", json={
            "mesaj": message,
            "kimin_icin": "kendim",
            "conversation_id": conversation_id,
        })
        assert response.status_code == 200
        assert response.headers["X-CureMenu-Resolved-Target"] == expected_target
        assert response.headers["X-CureMenu-Target-Scope"] == expected_scope
        responses.append(response.text.casefold())

    for index in (0, 3, 5, 6):
        assert "çölyak" not in responses[index]
        assert "yer fıstığı" not in responses[index]
    for index in (1, 2, 4, 7, 8):
        assert "warfarin" not in responses[index]
        assert "diyabet" not in responses[index]

    assert "tamamen bırakmak yerine" in responses[5]
    assert "k vitamini" in responses[6]
    assert "gluten" in responses[7] or "çölyak" in responses[7]

    assert "risk olabilir" in responses[8]
    assert "sos içeriği ile" not in responses[8]

    logs = client.get("/api/history?limit=50").json()["loglar"]
    final_metadata = next(
        json.loads(item.get("metadata") or "{}")
        for item in logs
        if item.get("eylem") == "CureBot"
        and json.loads(item.get("metadata") or "{}").get("conversation_id") == conversation_id
    )
    assert final_metadata["last_subject"] == "artifact"
    assert final_metadata["last_object"] == ""
    assert final_metadata["last_object_type"] == "unknown"
    assert final_metadata["last_artifact_reference"] == "menu_analysis"
    assert final_metadata["response_path"] == "artifact_followup"
    assert [
        item["evidence_level"] for item in final_metadata["structured_findings"]
    ] == ["CONFIRMED", "INFERRED-LIKELY"]
    assert all(
        item["inherited_from_previous_turn"] is True
        and item["new_evidence_this_turn"] is False
        for item in final_metadata["structured_findings"]
    )
