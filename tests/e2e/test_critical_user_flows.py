from __future__ import annotations

import json

import cv2

from conftest import next_phone


def _json(route, payload: dict, status: int = 200) -> None:
    route.fulfill(
        status=status,
        content_type="application/json",
        body=json.dumps(payload, ensure_ascii=False),
    )


def _weekly_plan() -> dict:
    return {
        "summary": "Warfarin ve alerji kaydi dikkate alinan test plani.",
        "warnings": ["Belirsiz durumda saglik profesyoneline danisin."],
        "days": [
            {
                "day": "Pazartesi",
                "breakfast": "Yulaf ve elma",
                "lunch": "Mercimek corbasi",
                "dinner": "Izgara tavuk ve sebze",
            }
        ],
    }


def test_public_chatbot_blocks_personal_health_advice(browser_page, e2e_base_url: str) -> None:
    page, _context, runtime_errors = browser_page
    chat_requests: list[str] = []

    page.route("**/api/chat", lambda route: (chat_requests.append(route.request.post_data or ""), route.abort()))
    page.goto(e2e_base_url + "/", wait_until="domcontentloaded")
    page.locator("[data-cm-assistant-launcher]").click()
    page.fill(
        "[data-cm-assistant-input]",
        "Profil ve sağlık bilgilerime göre bugün güvenli bir akşam yemeği önerir misin?",
    )
    page.locator("[data-cm-assistant-form]").evaluate("form => form.requestSubmit()")

    body = page.locator("[data-cm-assistant-body]")
    body.get_by_text("Bunu kişisel sağlık profili olmadan güvenli şekilde değerlendiremem").wait_for()
    assert body.get_by_text("hastalık, alerji, ilaç ve tercih bilgilerinizi").count() >= 1
    assert body.get_by_text("Decision ID").count() == 0
    assert body.get_by_text("risk skoru").count() == 0
    assert body.get_by_text("governance").count() == 0
    assert chat_requests == []
    assert not runtime_errors


def test_public_chatbot_product_and_data_explanations(browser_page, e2e_base_url: str) -> None:
    page, _context, runtime_errors = browser_page
    chat_requests: list[str] = []

    page.route("**/api/chat", lambda route: (chat_requests.append(route.request.post_data or ""), route.abort()))
    page.goto(e2e_base_url + "/", wait_until="domcontentloaded")
    page.locator("[data-cm-assistant-launcher]").click()

    page.fill("[data-cm-assistant-input]", "CureMenu nedir?")
    page.locator("[data-cm-assistant-form]").evaluate("form => form.requestSubmit()")
    body = page.locator("[data-cm-assistant-body]")
    body.get_by_text("beslenme karar destek asistanıdır").wait_for()
    assert body.get_by_text("Doktor veya diyetisyen yerine geçmez").count() >= 1

    page.fill("[data-cm-assistant-input]", "Verilerimi neden istiyorsunuz?")
    page.locator("[data-cm-assistant-form]").evaluate("form => form.requestSubmit()")
    body.get_by_text("kişiselleştirme ve güvenlik kontrolleri için kullanır").wait_for()
    assert body.get_by_text("tanı koymak veya tedavi düzenlemek değil").count() >= 1
    assert chat_requests == []
    assert not runtime_errors


def test_public_chatbot_blocks_disease_based_advice(browser_page, e2e_base_url: str) -> None:
    page, _context, runtime_errors = browser_page
    chat_requests: list[str] = []

    page.route("**/api/chat", lambda route: (chat_requests.append(route.request.post_data or ""), route.abort()))
    page.goto(e2e_base_url + "/", wait_until="domcontentloaded")
    page.locator("[data-cm-assistant-launcher]").click()
    page.fill("[data-cm-assistant-input]", "Diyabetim var, ne yemeliyim?")
    page.locator("[data-cm-assistant-form]").evaluate("form => form.requestSubmit()")

    body = page.locator("[data-cm-assistant-body]")
    body.get_by_text("giriş yaptıktan sonra hastalık, alerji, ilaç").wait_for()
    assert body.get_by_text("menü").count() == 0
    assert chat_requests == []
    assert not runtime_errors


def test_family_target_selectors_and_chat_payload(browser_page, e2e_base_url: str) -> None:
    page, _context, runtime_errors = browser_page
    chat_requests: list[dict] = []
    profile = {
        "ana_kullanici": {
            "id": "main",
            "ad": "Test Kullanıcı",
            "hastaliklar": [],
            "alerjiler": [],
            "ilaclar": [],
            "hedef": "Sağlıklı Yaşam",
        },
        "aile_uyeleri": [
            {
                "id": "member-ece",
                "ad": "Ece",
                "hastaliklar": [],
                "alerjiler": [],
                "ilaclar": [],
                "hedef": "Sağlıklı Yaşam",
            }
        ],
    }

    def api_handler(route) -> None:
        url = route.request.url
        if "/api/profile/me" in url:
            _json(route, {"success": True, "profil": profile})
        elif "/api/public/metinler" in url:
            _json(route, {"tibbi_feragat_kisa": "Test uyarısı", "ornek_sorular": [], "yaygin_ilaclar": []})
        elif "/api/chat" in url:
            chat_requests.append(json.loads(route.request.post_data or "{}"))
            route.fulfill(
                status=200,
                content_type="text/event-stream",
                body='event: token\ndata: {"chunk":"Ece için yanıt."}\n\nevent: done\ndata: {}\n\n',
            )
        else:
            _json(route, {"success": True, "items": [], "records": []})

    page.route("**/api/**", api_handler)
    page.add_init_script(
        "localStorage.setItem('cm_telefon', '05000000000');"
        "localStorage.setItem('cm_kullanici_adi', 'Test Kullanıcı');"
        "localStorage.setItem('cm_has_profile', 'true');"
        "localStorage.setItem('cm_onboarding_done', 'true');"
        "localStorage.setItem('cm_disclaimer_ok', 'true');"
    )
    page.goto(f"{e2e_base_url}/dashboard", wait_until="domcontentloaded")
    page.wait_for_function("window.currentProfile && window.currentProfile.aile_uyeleri.length === 1")

    expected_targets = ["Kendim İçin", "Ece İçin", "Tüm Aile İçin"]
    for selector in ["#planTarget", "#chatTarget", "#menuTarget", "#fridgeTarget", "#tahlilTarget"]:
        assert page.locator(selector).locator("option").all_text_contents() == expected_targets

    for tab_name in ["dashboard", "profile", "tahlil", "plan", "tarayici", "buzdolabi", "governance", "gecmis"]:
        page.evaluate("tab => window.switchTab(tab)", tab_name)
        assert page.locator(f"#tab-{tab_name}").evaluate("node => node.classList.contains('active')")
        assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth")

    page.locator("[data-cm-assistant-launcher]").click()
    page.locator("#chatTarget").select_option("member-ece")
    page.fill("[data-cm-assistant-input]", "Bugün ne yiyebilir?")
    page.locator("[data-cm-assistant-form]").evaluate("form => form.requestSubmit()")
    page.locator("[data-cm-assistant-body]").get_by_text("Ece i").wait_for()

    assert chat_requests[-1]["kimin_icin"] == "member-ece"
    assert page.evaluate("Object.keys(localStorage).some(key => key.startsWith('cm_chat_v2_05000000000_member_member-ece_'))")
    page.locator("#chatTarget").select_option("kendim")
    assert page.locator("[data-cm-assistant-body]").get_by_text("Ece i").count() == 0
    page.locator("#chatTarget").select_option("member-ece")
    page.locator("[data-cm-assistant-body]").get_by_text("Ece i").wait_for()
    assert not runtime_errors


def test_register_wrong_password_login_and_logout(browser_page, e2e_base_url: str) -> None:
    page, _context, runtime_errors = browser_page
    phone = next_phone()
    password = "E2ePass123"

    page.goto(f"{e2e_base_url}/kayit", wait_until="domcontentloaded")
    page.fill("#fullName", "Samet Test")
    page.fill("#phoneNumber", phone)
    page.fill("#password", password)
    page.click("#nextBtn")
    page.fill("#conditions", "hipertansiyon")
    page.fill("#allergies", "fistik")
    page.fill("#medications", "warfarin")
    page.click("#nextBtn")
    page.check("#disclaimerCheck")
    page.click("#submitBtn")
    page.wait_for_url("**/dashboard", timeout=15_000)
    assert page.evaluate("localStorage.getItem('cm_has_profile')") == "true"
    page.wait_for_function("window.currentProfile && window.currentProfile.ana_kullanici")
    page.evaluate("switchTab('profile')")
    assert page.locator("#familyGrid").get_by_text("Samet Test").count() >= 1
    page.evaluate("window.ProfileManager.openProfileEditor()")
    assert page.locator("#ob_ad").input_value() == "Samet Test"
    assert "hipertansiyon" in page.locator("#ob_hastaliklar").input_value()
    page.locator("#onboardingModal").evaluate("modal => modal.classList.add('hidden')")
    page.evaluate("switchTab('tahlil')")
    assert page.evaluate("localStorage.getItem('cm_active_tab')") == "tahlil"

    page.locator('button[onclick="logout()"]').first.click()
    page.wait_for_url(e2e_base_url + "/", timeout=10_000)
    assert page.evaluate("localStorage.getItem('cm_active_tab')") is None

    page.goto(f"{e2e_base_url}/giris", wait_until="domcontentloaded")
    page.fill("#phoneNumber", phone)
    page.fill("#password", "wrong-password")
    page.click("#submitBtn")
    page.locator("#loginError").wait_for(state="visible")
    assert page.locator("#loginError").inner_text().strip()

    page.fill("#password", password)
    page.click("#submitBtn")
    page.wait_for_url("**/dashboard", timeout=10_000)
    page.wait_for_function("window.currentProfile && document.querySelector('#tab-dashboard')?.classList.contains('active')")
    assert not runtime_errors


def test_weekly_plan_actions_and_gamification(authenticated_page) -> None:
    page, _context, runtime_errors, _user = authenticated_page
    plan = _weekly_plan()
    weekly_requests: list[dict] = []
    action_requests: list[dict] = []

    def weekly_plan(route) -> None:
        weekly_requests.append(json.loads(route.request.post_data or "{}"))
        _json(route, {"ok": True, "plan": plan, "compatibility": {"status": "fit", "tone": "green", "label": "Belirgin çakışma bulunmadı", "message": "Test değerlendirmesi."}})

    page.route("**/api/weekly-plan", weekly_plan)

    def plan_action(route) -> None:
        request = json.loads(route.request.post_data or "{}")
        action_requests.append(request)
        action = request.get("action_type")
        if action == "recipe":
            _json(route, {"success": True, "result": "Test tarifi: kontrollu porsiyon."})
        elif action == "snack":
            _json(route, {"success": True, "result": {"snack_onerileri": "Bir porsiyon elma", "warning": ""}})
        else:
            _json(
                route,
                {
                    "success": True,
                    "result": {
                        "degisen_ogunler": [{"eski": request.get("meal_text"), "yeni": "Sebzeli omlet"}],
                        "aciklama": "Profil icin test alternatifi.",
                    },
                },
            )

    page.route("**/api/plan-action", plan_action)
    page.route("**/api/compliance", lambda route: _json(route, {"success": True}))

    page.evaluate("switchTab('plan')")
    page.click("#generatePlanBtn")
    page.locator("#planResult").get_by_text("Pazartesi").wait_for()
    page.locator("#planResult").get_by_text("Belirgin çakışma bulunmadı").wait_for()
    assert page.locator('[data-weekly-action="recipe"]').count() == 3

    page.locator('[data-weekly-action="recipe"]').first.evaluate("button => { button.click(); button.click(); }")
    page.locator("#actionModalContent").get_by_text("Test tarifi").wait_for()
    recipe_requests = [item for item in action_requests if item.get("action_type") == "recipe"]
    assert len(recipe_requests) == 1
    assert recipe_requests[0]["meal_text"] == "Yulaf ve elma"
    assert recipe_requests[0]["kimin_icin"] == "kendim"
    page.locator('#actionModal [data-weekly-action="close"]').last.click()
    assert "hidden" in page.locator("#actionModal").get_attribute("class")

    page.locator('[data-weekly-action="alternative"]').first.click()
    page.locator("#actionModalContent").get_by_text("Sebzeli omlet").wait_for()
    alternative_request = next(item for item in action_requests if item.get("action_type") == "alternative")
    assert alternative_request["meal_text"] == "Yulaf ve elma"
    assert alternative_request["plan_text"]
    page.locator('#actionModal [data-weekly-action="close"]').last.click()

    page.locator('[data-weekly-action="snack"]').click()
    page.locator("#actionModalContent").get_by_text("Bir porsiyon elma").wait_for()
    snack_request = next(item for item in action_requests if item.get("action_type") == "snack")
    assert snack_request["plan_text"]
    assert snack_request["kimin_icin"] == "kendim"
    page.locator('#actionModal [data-weekly-action="close"]').last.click()

    checkbox = page.locator('#planResult input[type="checkbox"]').first
    checkbox.check(force=True)
    assert page.evaluate("Object.keys(localStorage).some(key => key.startsWith('cm_check_') && key.endsWith('_meal-0-0') && localStorage.getItem(key) === 'true')")
    page.locator("#planResult .day-progress").get_by_text("Durum: 1/3").wait_for()

    page.evaluate("window.updatePlanDropdown({aile_uyeleri: [{id: 'member-ece', ad: 'Ece'}]})")
    page.locator("#planTarget").select_option("member-ece")
    page.locator("#planResult").get_by_text("Henüz bir haftalık planınız yok").wait_for()
    assert page.evaluate("Object.keys(localStorage).filter(key => key.startsWith('cm_check_') && key.endsWith('_meal-0-0')).length === 1")

    page.locator("#planTarget").select_option("kendim")
    page.locator("#planResult").get_by_text("Pazartesi").wait_for()
    assert page.locator('#planResult input[type="checkbox"]').first.is_checked()

    page.unroute("**/api/weekly-plan")
    page.route(
        "**/api/weekly-plan",
        lambda route: _json(route, {"success": False, "error": {"message": "E2E plan olusturulamadi."}}),
    )
    page.click("#generatePlanBtn")
    page.locator("#planResult").get_by_text("E2E plan olusturulamadi.").wait_for()
    assert not runtime_errors


def test_smart_grocery_open_budget_feedback_and_close(authenticated_page) -> None:
    page, _context, runtime_errors, _user = authenticated_page
    page.evaluate("switchTab('plan')")
    page.route("**/api/weekly-plan*", lambda route: _json(route, {"success": True, "plan": _weekly_plan()}))

    # Plan oluştururken Mert'i seç, sonra plan ekranında Kendim'e dön
    page.evaluate("window.updatePlanDropdown({aile_uyeleri: [{id: 'member-mert', ad: 'Mert'}]})")
    page.locator("#planTarget").select_option("member-mert")
    page.locator("#planTarget").select_option("kendim")
    
    page.evaluate("plan => window.WeeklyPlanManager.renderPlan(plan)", _weekly_plan())

    smart_grocery_response = {
        "success": True,
        "decision_id": "e2e-grocery-decision",
        "price_catalog_version": "test-catalog-v1",
        "estimated_min_total": 100,
        "estimated_max_total": 140,
        "health_safe_total_items": 1,
        "caution_items": 0,
        "avoid_items": 1,
        "categories": {
            "tahil": [
                {
                    "name": "Yulaf",
                    "estimated_quantity": "500 g",
                    "reason": "Test profili icin uygun.",
                    "health_status": "safe",
                    "estimated_min_price": 40,
                    "estimated_max_price": 55,
                }
            ]
        },
        "excluded_items": [
            {
                "name": "Ispanak",
                "estimated_quantity": "1 demet",
                "reason": "Warfarin ile K vitamini yonetimi profesyonel takip gerektirir.",
                "health_status": "avoid",
                "estimated_min_price": None,
                "estimated_max_price": None,
            }
        ],
        "risk_items": [],
        "market_search_links": [],
        "disclaimer": "Fiyat ve stok bilgisi test verisidir.",
        "recommendation_summary": "Riskli urun toplam fiyata dahil edilmedi.",
    }
    smart_grocery_requests = []
    def intercept_grocery(route):
        smart_grocery_requests.append(route.request.post_data_json)
        _json(route, smart_grocery_response)

    page.route("**/api/smart-grocery", intercept_grocery)
    page.route("**/api/shopping-list", lambda route: _json(route, {"success": True, "rapor": "Tahmini toplam: 120 TL"}))
    page.route("**/api/feedback", lambda route: _json(route, {"success": True, "message": "Geri bildirim kaydedildi."}))


    page.locator('[data-grocery-action="open"]').click()
    page.wait_for_timeout(3000)
    print("\n--- MODAL HTML ---")
    print(page.locator("#smartGroceryModal").inner_html())
    print("--- END MODAL HTML ---")
    page.locator("#smartGroceryContent").get_by_text(
        "Sepet önerileri, profiliniz ve güvenlik kontrolleri dikkate alınarak değerlendirildi."
    ).wait_for()
    assert page.locator("#smartGroceryContent").get_by_text("e2e-grocery-decision").count() == 0
    assert page.locator("#smartGroceryContent").get_by_text("Ispanak").count() == 1
    
    assert smart_grocery_requests[-1]["kimin_icin"] == "kendim"
    assert page.locator("#groceryTarget").input_value() == "kendim"
    
    page.locator("#groceryTarget").select_option("member-mert")
    page.locator("#smartGroceryContent").get_by_text(
        "Sepet önerileri, profiliniz ve güvenlik kontrolleri dikkate alınarak değerlendirildi."
    ).wait_for()
    assert smart_grocery_requests[-1]["kimin_icin"] == "member-mert"

    page.locator('#smartGroceryModal [data-grocery-action="close"]').last.click()
    assert "hidden" in page.locator("#smartGroceryModal").get_attribute("class")

    page.locator('[data-grocery-action="calculate-budget"]').click()
    page.locator("#budgetResult").get_by_text("Tahmini toplam").wait_for()

    dialog_messages: list[str] = []
    page.once("dialog", lambda dialog: (dialog_messages.append(dialog.message), dialog.accept()))
    page.evaluate("window.SmartGrocery.sendFeedback('Yulaf')")
    page.wait_for_timeout(100)
    assert dialog_messages == ["Geri bildirim kaydedildi."]
    assert not runtime_errors


def test_curebot_upload_menu_fridge_and_qr_fallback(authenticated_page) -> None:
    page, _context, runtime_errors, _user = authenticated_page
    chat_requests: list[dict] = []

    def chat_stream(route) -> None:
        request = json.loads(route.request.post_data or "{}")
        chat_requests.append(request)
        target_name = request.get("kimin_icin", "kendim")
        body = "".join(
            [
                'event: status\ndata: {"status":"Kontroller calisiyor"}\n\n',
                f'event: token\ndata: {{"chunk":"{target_name} icin test yaniti."}}\n\n',
                'event: governance\ndata: {"decision_id":"e2e-chat-decision","confidence_score":0.82,"risk_score":0.25}\n\n',
                "event: done\ndata: {}\n\n",
            ]
        )
        route.fulfill(status=200, content_type="text/event-stream", body=body)

    page.route("**/api/chat", chat_stream)
    page.route(
        "**/api/clinical-decisions/e2e-chat-decision",
        lambda route: _json(
            route,
            {
                "success": True,
                "decision": {
                    "citations": [
                        {"title": "E2E resmi kaynak", "evidence_span": "Test kanit parcasi"}
                    ]
                },
            },
        ),
    )
    page.locator("[data-cm-assistant-launcher]").click()
    page.locator('[data-cm-feature="plan"]').click()
    assert page.locator("#tab-plan").evaluate("element => element.classList.contains('active')")
    page.evaluate("window.updatePlanDropdown({aile_uyeleri: [{id: 'member-ece', ad: 'Ece'}, {id: 'member-mert', ad: 'Mert'}, {id: 'member-ayse', ad: 'Ayşe'}]})")
    expected_targets = ["Kendim İçin", "Ece İçin", "Mert İçin", "Ayşe İçin", "Tüm Aile İçin"]
    for selector in ["#planTarget", "#chatTarget", "#menuTarget", "#fridgeTarget", "#tahlilTarget"]:
        assert page.locator(selector).locator("option").all_text_contents() == expected_targets
    target = page.locator("#chatTarget")
    target.wait_for(state="visible")
    target.select_option("member-ece")
    assert page.locator("[data-cm-context-chip]").inner_text() == "Ece İçin"
    page.fill("[data-cm-assistant-input]", "Aksam ne yiyebilirim?")
    page.locator("[data-cm-assistant-form]").evaluate("form => form.requestSubmit()")
    page.locator("[data-cm-assistant-body]").get_by_text("member-ece icin test yaniti.").wait_for()
    assert chat_requests[-1]["kimin_icin"] == "member-ece"
    assert page.locator("[data-cm-assistant-body]").get_by_text("e2e-chat-decision").count() == 0
    assert page.locator("[data-cm-assistant-body]").get_by_text("Operasyonel güven").count() == 0
    citation_panel = page.locator("[data-chat-governance-citations]")
    assert citation_panel.count() == 0 or citation_panel.is_hidden()
    assert page.locator("[data-cm-assistant-body]").get_by_text("E2E resmi kaynak").count() == 0
    assert page.locator("[data-cm-assistant-body]").get_by_text("Test kanit parcasi").count() == 0

    target.select_option("kendim")
    page.fill("[data-cm-assistant-input]", "Kendim icin ne onerirsin?")
    page.locator("[data-cm-assistant-form]").evaluate("form => form.requestSubmit()")
    page.locator("[data-cm-assistant-body]").get_by_text("kendim icin test yaniti.").wait_for()
    assert chat_requests[-1]["kimin_icin"] == "kendim"
    assert page.locator("[data-cm-assistant-body]").get_by_text("member-ece icin test yaniti.").count() == 0

    target.select_option("member-mert")
    page.fill("[data-cm-assistant-input]", "Mert icin ne onerirsin?")
    page.locator("[data-cm-assistant-form]").evaluate("form => form.requestSubmit()")
    page.locator("[data-cm-assistant-body]").get_by_text("member-mert icin test yaniti.").wait_for()
    assert chat_requests[-1]["kimin_icin"] == "member-mert"

    target.select_option("member-ayse")
    page.fill("[data-cm-assistant-input]", "Ayse icin ne onerirsin?")
    page.locator("[data-cm-assistant-form]").evaluate("form => form.requestSubmit()")
    page.locator("[data-cm-assistant-body]").get_by_text("member-ayse icin test yaniti.").wait_for()
    assert chat_requests[-1]["kimin_icin"] == "member-ayse"

    target.select_option("aile")
    page.fill("[data-cm-assistant-input]", "Tum aile icin ne onerirsin?")
    page.locator("[data-cm-assistant-form]").evaluate("form => form.requestSubmit()")
    page.locator("[data-cm-assistant-body]").get_by_text("aile icin test yaniti.").wait_for()
    assert chat_requests[-1]["kimin_icin"] == "aile"
    assert page.locator("[data-cm-assistant-body]").get_by_text("kendim icin test yaniti.").count() == 0

    page.route(
        "**/api/clinical-decisions/e2e-no-citations",
        lambda route: _json(route, {"success": True, "decision": {"citations": []}}),
    )
    page.evaluate(
        """
        const root = document.createElement('div');
        root.id = 'e2e-no-citations';
        document.body.appendChild(root);
        window.ChatGovernancePanel.renderChatGovernanceSummary(
            {decision_id: 'e2e-no-citations', risk_score: 0.9},
            root
        );
        """
    )
    page.wait_for_function("document.getElementById('e2e-no-citations').hidden === true")
    assert page.locator("#e2e-no-citations").text_content() == ""

    page.unroute("**/api/chat")
    page.route(
        "**/api/chat",
        lambda route: route.fulfill(
            status=200,
            content_type="text/event-stream",
            body='event: error\ndata: {"message":"E2E guvenli chat hatasi."}\n\nevent: done\ndata: {}\n\n',
        ),
    )
    page.fill("[data-cm-assistant-input]", "Hata durumunu dene")
    page.locator("[data-cm-assistant-form]").evaluate("form => form.requestSubmit()")
    page.locator("[data-cm-assistant-body]").get_by_text("E2E guvenli chat hatasi.").wait_for()

    page.route(
        "**/api/upload-health-record",
        lambda route: _json(route, {"success": True, "message": "E2E tahlil ozeti kaydedildi."}),
    )
    page.evaluate("switchTab('tahlil')")
    page.set_input_files(
        "#healthRecordInput",
        {"name": "test-report.pdf", "mimeType": "application/pdf", "buffer": b"%PDF-1.4\n%%EOF"},
    )
    page.locator("#healthRecordResult").get_by_text("E2E tahlil ozeti").wait_for()

    page.unroute("**/api/upload-health-record")
    page.route(
        "**/api/upload-health-record",
        lambda route: _json(route, {"detail": "E2E gecersiz PDF."}, status=400),
    )
    page.set_input_files(
        "#healthRecordInput",
        {"name": "broken.pdf", "mimeType": "application/pdf", "buffer": b"broken-pdf"},
    )
    page.locator("#healthRecordResult").get_by_text("E2E gecersiz PDF.").wait_for()

    page.route("**/api/scan-menu", lambda route: _json(route, {"success": True, "analiz": "E2E menu analizi guvenli sekilde tamamlandi."}))
    page.evaluate("switchTab('tarayici')")
    page.fill("#menuUrlInput", "https://example.com/menu")
    page.evaluate("window.MenuScanner.scanMenu()")
    page.locator("#menuScanResult").get_by_text("E2E menu analizi").wait_for()

    assert page.evaluate("typeof window.Html5Qrcode === 'function'")

    qr_encoder = cv2.QRCodeEncoder_create()
    qr_image = qr_encoder.encode("https://example.com/qr-menu")
    qr_image = cv2.resize(qr_image, None, fx=10, fy=10, interpolation=cv2.INTER_NEAREST)
    qr_image = cv2.copyMakeBorder(qr_image, 80, 80, 80, 80, cv2.BORDER_CONSTANT, value=255)
    encoded, qr_png = cv2.imencode(".png", qr_image)
    assert encoded
    page.set_input_files(
        "#qrImageInput",
        {"name": "menu-qr.png", "mimeType": "image/png", "buffer": qr_png.tobytes()},
    )
    page.wait_for_function("document.getElementById('menuUrlInput').value === 'https://example.com/qr-menu'")
    page.locator("#menuScanResult").get_by_text("Menü bağlantısı okundu").wait_for()

    page.evaluate(
        """
        () => {
            window.Html5Qrcode = class {
                constructor(elementId) { this.elementId = elementId; }
                async start() {
                    this.isScanning = true;
                    document.getElementById(this.elementId).textContent = 'QR okuyucu';
                }
                async stop() { this.isScanning = false; }
                async clear() {}
            };
        }
        """
    )
    page.evaluate("window.MenuScanner.startQRScanner()")
    page.locator("#qr-reader").get_by_text("QR okuyucu").wait_for()

    page.evaluate(
        """
        () => {
            window.Html5Qrcode = class {
                constructor(elementId) { this.elementId = elementId; }
                async scanFile() {
                    document.getElementById(this.elementId).textContent = 'No multi-format readers were able to detect the code';
                    throw new Error('No multi-format readers were able to detect the code');
                }
                async clear() {}
            };
        }
        """
    )
    page.set_input_files(
        "#qrImageInput",
        {"name": "not-a-qr.png", "mimeType": "image/png", "buffer": b"not-a-qr"},
    )
    page.locator("#menuScanResult").get_by_text("Bu görselde okunabilir bir QR kod bulunamadı").wait_for()
    assert page.get_by_text("No multi-format readers were able to detect the code").count() == 0
    assert page.locator("[id^='qr-file-reader-']").count() == 0

    page.evaluate(
        """
        () => {
            window.Html5Qrcode = class {
                async start() { throw new Error('NotAllowedError'); }
                async clear() {}
            };
        }
        """
    )
    page.evaluate("window.MenuScanner.startQRScanner()")
    page.locator("#qr-reader").get_by_text("Kameraya erişilemedi").wait_for()

    page.route(
        "**/api/scan-menu-image",
        lambda route: _json(route, {"detail": "E2E gecersiz menu gorseli."}, status=400),
    )
    page.set_input_files(
        "#menuImageInput",
        {"name": "broken.jpg", "mimeType": "image/jpeg", "buffer": b"not-an-image"},
    )
    page.locator("#menuScanResult").get_by_text("E2E gecersiz menu gorseli.").wait_for()

    page.route(
        "**/api/fridge-scan",
        lambda route: _json(
            route,
            {
                "success": True,
                "malzemeler": "Yumurta, domates",
                "tarif": "E2E sebzeli omlet",
                "recipe_ingredients": ["yumurta", "domates"],
                "image_preview_base64": "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII=",
            },
        ),
    )
    page.evaluate("switchTab('buzdolabi')")
    page.set_input_files(
        "#fridgeImageInput",
        {"name": "fridge.png", "mimeType": "image/png", "buffer": b"not-a-real-image-for-mocked-e2e"},
    )
    page.locator("#fridgeScanResult").get_by_text("E2E sebzeli omlet").wait_for()
    assert page.locator('#fridgeScanResult img[alt="Yüklenen buzdolabı fotoğrafı"]').count() == 1
    page.locator("#fridgeHistoryList").get_by_text("Fotoğrafı ve tarifi aç").wait_for()
    assert page.locator("#fridgeHistoryList").get_by_text("Henüz buzdolabı analizi yok").count() == 0

    page.unroute("**/api/fridge-scan")
    page.route(
        "**/api/fridge-scan",
        lambda route: _json(route, {"detail": "E2E gecersiz buzdolabi gorseli."}, status=400),
    )
    page.set_input_files(
        "#fridgeImageInput",
        {"name": "broken.jpg", "mimeType": "image/jpeg", "buffer": b"not-an-image"},
    )
    page.locator("#fridgeScanResult").get_by_text("E2E gecersiz buzdolabi gorseli.").wait_for()
    assert not runtime_errors


def test_curebot_progress_and_duplicate_request_guard(authenticated_page) -> None:
    page, _context, runtime_errors, _user = authenticated_page
    page.locator("[data-cm-assistant-launcher]").click()
    page.evaluate(
        """
        () => {
            window.__e2eChatFetchCalls = 0;
            window.safeFetchStream = async () => {
                window.__e2eChatFetchCalls += 1;
                const encoder = new TextEncoder();
                return new Response(new ReadableStream({
                    start(controller) {
                        setTimeout(() => controller.enqueue(encoder.encode(
                            'event: status\\ndata: {"status":"Öneri sağlık kısıtlarıyla karşılaştırılıyor..."}\\n\\n'
                        )), 750);
                        setTimeout(() => {
                            controller.enqueue(encoder.encode(
                                'event: message\\ndata: {"chunk":"Güvenli test yanıtı."}\\n\\n' +
                                'event: done\\ndata: {}\\n\\n'
                            ));
                            controller.close();
                        }, 1500);
                    }
                }), {status: 200, headers: {'Content-Type': 'text/event-stream'}});
            };
        }
        """
    )
    page.fill("[data-cm-assistant-input]", "Hızlı kahvaltı öner")
    page.locator("[data-cm-assistant-form]").evaluate(
        "form => { form.requestSubmit(); form.requestSubmit(); }"
    )

    assert page.locator("[data-cm-assistant-input]").is_disabled()
    assert page.locator("[data-cm-assistant-send]").get_attribute("aria-busy") == "true"
    page.locator("#cm-assistant-status").get_by_text("Profil bilgilerin kontrol ediliyor").wait_for()
    page.locator("[data-cm-assistant-body]").get_by_text("Güvenli test yanıtı.").wait_for()
    page.wait_for_function("window.ChatWidget.requestInFlight === false")

    assert page.evaluate("window.__e2eChatFetchCalls") == 1
    assert not page.locator("[data-cm-assistant-input]").is_disabled()
    assert page.locator("[data-cm-assistant-send]").get_attribute("aria-busy") == "false"
    assert page.locator("[data-cm-assistant-body]").get_by_text("Yanıt beklenenden uzun sürdü").count() == 0
    assert not runtime_errors


def test_curebot_fetch_error_does_not_show_raw_failed_to_fetch(authenticated_page) -> None:
    page, _context, runtime_errors, _user = authenticated_page
    page.locator("[data-cm-assistant-launcher]").click()
    page.evaluate(
        """
        () => {
            window.safeFetchStream = async () => {
                throw new TypeError('Failed to fetch');
            };
        }
        """
    )

    page.fill("[data-cm-assistant-input]", "Glutensiz makarna ve yoğurtlu sos yiyebilir miyim?")
    page.locator("[data-cm-assistant-form]").evaluate("form => form.requestSubmit()")

    body = page.locator("[data-cm-assistant-body]")
    body.get_by_text("Yanıt oluşturulamadı. Lütfen tekrar deneyin.").wait_for()
    assert body.get_by_text("Failed to fetch").count() == 0
    assert not runtime_errors


def test_mobile_navigation_history_and_menu_layout_regressions(authenticated_page) -> None:
    page, _context, runtime_errors, _user = authenticated_page
    history_requests: list[str] = []

    def history_response(route) -> None:
        history_requests.append(route.request.url)
        _json(route, {"success": True, "loglar": [], "has_more": False})

    page.route("**/api/history?*", history_response)
    page.set_viewport_size({"width": 390, "height": 844})

    mobile_nav = page.locator(".mobile-nav")
    assert mobile_nav.is_visible()
    assert set(mobile_nav.locator(".mobile-tab-btn").evaluate_all("buttons => buttons.map(button => button.dataset.tab)")) == {
        "dashboard",
        "plan",
        "curebot",
        "profile",
        "tahlil",
        "tarayici",
        "buzdolabi",
        "gecmis",
    }

    mobile_nav.locator('[data-tab="plan"]').click()
    assert page.locator("#tab-plan").evaluate("element => element.classList.contains('active')")

    mobile_nav.locator('[data-tab="curebot"]').click()
    assert page.locator("#cm-assistant-root").get_attribute("data-open") == "true"
    page.locator("[data-cm-assistant-close]").click()

    mobile_nav.locator('[data-tab="gecmis"]').click()
    page.locator("#historyGrid").get_by_text("Henüz geçmiş işleminiz bulunmuyor.").wait_for()
    assert history_requests
    assert "limit=10" in history_requests[-1]
    assert not any("HISTORY_LIMIT" in message for message in runtime_errors)
    assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth")

    page.set_viewport_size({"width": 768, "height": 1024})
    page.evaluate("switchTab('tarayici')")
    scan_button = page.get_by_role("button", name="Linki tara")
    tablet_layout = page.evaluate(
        """() => ({
            viewportWidth: window.innerWidth,
            documentWidth: document.documentElement.scrollWidth,
            overflowElements: Array.from(document.querySelectorAll('body *'))
                .filter(element => {
                    const rect = element.getBoundingClientRect();
                    return rect.right > window.innerWidth + 1 || rect.left < -1;
                })
                .slice(0, 10)
                .map(element => ({
                    tag: element.tagName,
                    id: element.id,
                    className: String(element.className || ''),
                    right: Math.round(element.getBoundingClientRect().right),
                })),
        })"""
    )
    assert tablet_layout["documentWidth"] <= tablet_layout["viewportWidth"], tablet_layout
    assert scan_button.evaluate("button => button.getBoundingClientRect().right <= window.innerWidth")

    page.set_viewport_size({"width": 1440, "height": 1000})
    assert page.locator(".app-sidebar").is_visible()
    assert not mobile_nav.is_visible()
    assert page.locator(".menu-scan-controls").evaluate(
        "element => getComputedStyle(element).gridTemplateColumns.split(' ').length === 3"
    )
    assert scan_button.evaluate("button => button.getBoundingClientRect().right <= window.innerWidth")
    assert not runtime_errors


def test_refresh_restores_active_tab_and_persistent_lab_fridge_history(authenticated_page) -> None:
    page, _context, runtime_errors, _user = authenticated_page
    page.set_viewport_size({"width": 390, "height": 844})
    page.wait_for_function("window.currentProfile && window.LabUpload && window.MenuScanner")

    for tab_name in ["profile", "tahlil", "plan", "tarayici", "buzdolabi", "gecmis"]:
        page.evaluate("tab => switchTab(tab)", tab_name)
        page.reload(wait_until="domcontentloaded")
        page.wait_for_function(
            "tab => window.currentProfile && document.querySelector(`#tab-${tab}`).classList.contains('active')",
            arg=tab_name,
        )
        assert page.evaluate("tab => localStorage.getItem('cm_active_tab') === tab", tab_name)

    page.evaluate("switchTab('curebot')")
    page.reload(wait_until="domcontentloaded")
    page.wait_for_function(
        "window.currentProfile && document.querySelector('#cm-assistant-root')?.dataset.open === 'true'"
    )
    assert page.evaluate("localStorage.getItem('cm_active_tab') === 'curebot'")
    assert not runtime_errors


def test_lab_and_fridge_history_empty_state_and_api_error_are_distinct(authenticated_page) -> None:
    page, _context, runtime_errors, _user = authenticated_page
    history_mode = {"value": "empty"}

    def history_response(route) -> None:
        if history_mode["value"] == "error":
            _json(route, {"success": False, "detail": "E2E history unavailable"}, status=503)
            return
        _json(route, {"success": True, "loglar": [], "total": 0, "page": 1, "limit": 10, "has_more": False})

    page.route("**/api/history?*", history_response)
    page.evaluate("switchTab('tahlil')")
    page.locator("#labHistoryList").get_by_text("Yüklenen tahlil yok").wait_for()
    page.evaluate("switchTab('buzdolabi')")
    page.locator("#fridgeHistoryList").get_by_text("Henüz buzdolabı analizi yok").wait_for()

    history_mode["value"] = "error"
    page.evaluate("switchTab('tahlil')")
    page.evaluate("window.LabUpload.loadLabHistory()")
    page.locator("#labHistoryList").get_by_text("Tahlil geçmişi şu anda yüklenemedi").wait_for()
    assert page.locator("#labHistoryList").get_by_text("Bağlantı kurulamadı").count() == 0
    page.evaluate("switchTab('buzdolabi')")
    page.evaluate("window.MenuScanner.loadFridgeHistory()")
    page.locator("#fridgeHistoryList").get_by_text("Buzdolabı geçmişi şu anda yüklenemedi").wait_for()
    assert page.locator("#fridgeHistoryList").get_by_text("Bağlantı kurulamadı").count() == 0
    assert not runtime_errors


def test_curebot_stays_closed_on_fresh_dashboard(authenticated_page) -> None:
    page, _context, runtime_errors, _user = authenticated_page
    root = page.locator("#cm-assistant-root")

    assert root.get_attribute("data-open") != "true"
    assert not root.locator(".cm-assistant-panel").is_visible()
    assert root.locator("[data-cm-assistant-launcher]").is_visible()
    assert page.evaluate("localStorage.getItem('cm_active_tab') !== 'curebot'")
    assert not runtime_errors


def test_fridge_history_restores_photo_detected_ingredients_and_recipe(authenticated_page) -> None:
    page, _context, runtime_errors, _user = authenticated_page
    main_id = page.evaluate("String(window.currentProfile.ana_kullanici.id)")
    preview = "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII="
    metadata = json.dumps(
        {
            "target_id": main_id,
            "target_scope": "self",
            "target_name": "Test Kullanici",
            "profile_fingerprint": "backend-generated-profile-fingerprint",
            "detected_ingredients": ["domates", "salatalık", "yoğurt"],
            "recipe_ingredients": ["domates", "salatalık"],
            "image_preview_base64": preview,
        },
        ensure_ascii=False,
    )

    page.route(
        "**/api/history?*",
        lambda route: _json(
            route,
            {
                "success": True,
                "loglar": [
                    {
                        "eylem": "Buzdolabı",
                        "kullanici_adi": "Test Kullanici",
                        "kullanici_girdisi": "domates, salatalık, yoğurt",
                        "asistan_ciktisi": "Domatesli salatalık kasesi tarifi",
                        "tarih": "2026-08-04T10:00:00",
                        "metadata": metadata,
                    }
                ],
                "has_more": False,
            },
        ),
    )
    page.evaluate("switchTab('buzdolabi')")
    page.evaluate("window.MenuScanner.loadFridgeHistory()")

    history_card = page.locator("#fridgeHistoryList [data-fridge-history-index='0']")
    history_card.get_by_text("Fotoğrafı ve tarifi aç").wait_for()
    assert history_card.locator("img").count() == 1
    history_card.click()
    result = page.locator("#fridgeScanResult")
    result.get_by_text("Domatesli salatalık kasesi tarifi").wait_for()
    assert result.locator("img").count() == 1
    assert "yoğurt" in result.inner_text()
    assert not runtime_errors


def test_lab_chart_model_normalizes_aliases_and_builds_dataset(authenticated_page) -> None:
    page, _context, runtime_errors, _user = authenticated_page
    page.evaluate("switchTab('tahlil')")
    model = page.evaluate(
        """
        () => window.LabUpload.buildLabChartModel([
          {
            tarih: "2026-07-20T10:00:00",
            metadata: JSON.stringify({
              biomarkers: [
                { name: "Hemoglobin A1c", value: 6.1, unit: "%" },
                { name: "Vitamin B12", value: 320, unit: "pg/mL" }
              ]
            })
          },
          {
            tarih: "2026-07-21T10:00:00",
            metadata: JSON.stringify({
              biomarkers: [
                { name: "HbA1c", value: 6.4, unit: "%" },
                { name: "B12", value: 340, unit: "pg/mL" }
              ]
            })
          }
        ])
        """
    )
    labels = {dataset["label"] for dataset in model["datasets"]}
    assert "HbA1c" in labels
    assert "B12" in labels
    assert model["emptyMessage"] == ""
    assert not runtime_errors


def test_lab_history_rehydrates_after_refresh_and_draws_chart(authenticated_page) -> None:
    page, _context, runtime_errors, _user = authenticated_page
    page.wait_for_function("window.currentProfile && window.currentProfile.ana_kullanici")
    profile_context = page.evaluate("window.ProfileManager.getTargetCacheContext('tahlilTarget')")
    page.route(
        "**/api/history?*",
        lambda route: _json(
            route,
            {
                "success": True,
                "loglar": [
                    {
                        "id": 11,
                        "eylem": "Tahlil",
                        "kullanici_adi": "Test Kullanici",
                        "kullanici_girdisi": "Birinci PDF",
                        "asistan_ciktisi": "Hemoglobin A1c sonucu kaydedildi.",
                        "tarih": "2026-07-20T10:00:00",
                        "metadata": json.dumps({
                            "target_id": profile_context["targetId"],
                            "target_scope": profile_context["targetScope"],
                            "profile_fingerprint": profile_context["profileFingerprint"],
                            "biomarkers": [{"name": "Hemoglobin A1c", "value": 6.1, "unit": "%"}],
                        }, ensure_ascii=False),
                    },
                    {
                        "id": 12,
                        "eylem": "Tahlil",
                        "kullanici_adi": "Test Kullanici",
                        "kullanici_girdisi": "İkinci PDF",
                        "asistan_ciktisi": "HbA1c sonucu kaydedildi.",
                        "tarih": "2026-07-21T10:00:00",
                        "metadata": json.dumps({
                            "target_id": profile_context["targetId"],
                            "target_scope": profile_context["targetScope"],
                            "profile_fingerprint": profile_context["profileFingerprint"],
                            "biomarkers": [{"name": "HbA1c", "value": "6,4", "unit": "%"}],
                        }, ensure_ascii=False),
                    },
                ],
                "total": 2,
                "page": 1,
                "limit": 10,
                "has_more": False,
            },
        ),
    )
    page.evaluate(
        """
        () => {
          window.Chart = function (_ctx, config) {
            window.__labChartConfig = config;
            this.destroy = function () {};
          };
          switchTab('tahlil');
        }
        """
    )
    page.locator("#labHistoryList").get_by_text("Birinci PDF").wait_for()
    page.locator("#labHistoryList").get_by_text("İkinci PDF").wait_for()
    assert page.evaluate("window.__labChartConfig?.data?.datasets?.[0]?.label") == "HbA1c"

    page.reload(wait_until="domcontentloaded")
    page.wait_for_function("window.currentProfile && window.LabUpload")
    page.evaluate(
        """
        () => {
          window.Chart = function (_ctx, config) {
            window.__labChartConfig = config;
            this.destroy = function () {};
          };
        }
        """
    )
    page.evaluate("window.LabUpload.loadLabHistory()")
    page.locator("#tab-tahlil.active").wait_for()
    page.locator("#labHistoryList").get_by_text("Birinci PDF").wait_for()
    assert page.evaluate("window.__labChartConfig?.data?.datasets?.[0]?.label") == "HbA1c"
    assert not runtime_errors


def test_lab_history_keeps_records_when_profile_fingerprint_changes(authenticated_page) -> None:
    page, _context, runtime_errors, _user = authenticated_page
    page.wait_for_function("window.currentProfile && window.currentProfile.ana_kullanici")
    profile_context = page.evaluate("window.ProfileManager.getTargetCacheContext('tahlilTarget')")
    page.route(
        "**/api/history?*",
        lambda route: _json(
            route,
            {
                "success": True,
                "loglar": [
                    {
                        "id": 21,
                        "eylem": "Tahlil",
                        "kullanici_adi": "Test Kullanici",
                        "kullanici_girdisi": "Profil guncel oncesi PDF",
                        "asistan_ciktisi": "Ferritin sonucu kaydedildi.",
                        "tarih": "2026-07-20T10:00:00",
                        "metadata": json.dumps({
                            "target_id": profile_context["targetId"],
                            "target_scope": profile_context["targetScope"],
                            "profile_fingerprint": "previous-profile-fingerprint",
                            "biomarkers": [{"name": "Ferritin", "value": 45, "unit": "ng/mL"}],
                        }, ensure_ascii=False),
                    }
                ],
                "total": 1,
                "page": 1,
                "limit": 10,
                "has_more": False,
            },
        ),
    )

    page.evaluate("switchTab('tahlil')")

    page.locator("#labHistoryList").get_by_text("Profil guncel oncesi PDF").wait_for()
    assert page.locator("#labHistoryList").get_by_text("Ferritin sonucu kaydedildi.").count() == 1
    assert not runtime_errors


def test_lab_history_shows_legacy_records_for_matching_target_name(authenticated_page) -> None:
    page, _context, runtime_errors, _user = authenticated_page
    page.wait_for_function("window.currentProfile && window.currentProfile.ana_kullanici")
    page.route(
        "**/api/history?*",
        lambda route: _json(
            route,
            {
                "success": True,
                "loglar": [
                    {
                        "id": 22,
                        "eylem": "Tahlil",
                        "kullanici_adi": "Test Kullanici",
                        "kullanici_girdisi": "Eski tahlil PDF",
                        "asistan_ciktisi": "B12 sonucu kaydedildi.",
                        "tarih": "2026-07-20T10:00:00",
                        "metadata": json.dumps({
                            "biomarkers": [{"name": "Vitamin B12", "value": 320, "unit": "pg/mL"}],
                        }, ensure_ascii=False),
                    }
                ],
                "total": 1,
                "page": 1,
                "limit": 10,
                "has_more": False,
            },
        ),
    )

    page.evaluate("switchTab('tahlil')")

    page.locator("#labHistoryList").get_by_text("Eski tahlil PDF").wait_for()
    assert page.locator("#labHistoryList").get_by_text("B12 sonucu kaydedildi.").count() == 1
    assert not runtime_errors


def test_lab_chart_empty_state_requires_same_numeric_biomarker(authenticated_page) -> None:
    page, _context, runtime_errors, _user = authenticated_page
    page.evaluate("switchTab('tahlil')")
    model = page.evaluate(
        """
        () => window.LabUpload.buildLabChartModel([
          {
            tarih: "2026-07-20T10:00:00",
            metadata: JSON.stringify({ biomarkers: [{ name: "Ferritin", value: 45, unit: "ng/mL" }] })
          },
          {
            tarih: "2026-07-21T10:00:00",
            metadata: JSON.stringify({ biomarkers: [{ name: "TSH", value: 2.1, unit: "mIU/L" }] })
          }
        ])
        """
    )
    assert model["datasets"] == []
    assert "aynı biyomarkerın en az iki sayısal sonucu gerekiyor" in model["emptyMessage"].lower()
    assert not runtime_errors


def test_lab_chart_failure_does_not_hide_history_list(authenticated_page) -> None:
    page, _context, runtime_errors, _user = authenticated_page
    profile_context = page.evaluate("window.ProfileManager.getTargetCacheContext('tahlilTarget')")
    page.route(
        "**/api/history?*",
        lambda route: _json(
            route,
            {
                "success": True,
                "loglar": [
                    {
                        "id": 1,
                        "eylem": "Tahlil",
                        "kullanici_adi": "Test Kullanici",
                        "kullanici_girdisi": "Lab A",
                        "asistan_ciktisi": "Ferritin normal aralıkta.",
                        "tarih": "2026-07-20T10:00:00",
                        "metadata": json.dumps({
                            "target_id": profile_context["targetId"],
                            "target_scope": profile_context["targetScope"],
                            "profile_fingerprint": profile_context["profileFingerprint"],
                            "biomarkers": [{"name": "Ferritin", "value": 45, "unit": "ng/mL"}]
                        }, ensure_ascii=False),
                    }
                ],
                "total": 1,
                "page": 1,
                "limit": 10,
                "has_more": False,
            },
        ),
    )
    page.evaluate(
        """
        () => {
          window.Chart = function () {
            throw new Error("chart failed");
          };
          switchTab('tahlil');
        }
        """
    )
    page.evaluate("window.LabUpload.loadLabHistory()")
    page.locator("#labHistoryList").get_by_text("Lab A").wait_for()
    assert page.locator("#labHistoryList").get_by_text("Ferritin normal aralıkta.").count() == 1
    assert not runtime_errors
