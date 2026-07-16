from __future__ import annotations

import json

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

    page.locator('button[onclick="logout()"]').first.click()
    page.wait_for_url(e2e_base_url + "/", timeout=10_000)

    page.goto(f"{e2e_base_url}/giris", wait_until="domcontentloaded")
    page.fill("#phoneNumber", phone)
    page.fill("#password", "wrong-password")
    page.click("#submitBtn")
    page.locator("#loginError").wait_for(state="visible")
    assert page.locator("#loginError").inner_text().strip()

    page.fill("#password", password)
    page.click("#submitBtn")
    page.wait_for_url("**/dashboard", timeout=10_000)
    assert not runtime_errors


def test_weekly_plan_actions_and_gamification(authenticated_page) -> None:
    page, _context, runtime_errors, _user = authenticated_page
    plan = _weekly_plan()

    page.route("**/api/weekly-plan", lambda route: _json(route, {"ok": True, "plan": plan}))

    def plan_action(route) -> None:
        request = json.loads(route.request.post_data or "{}")
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
    assert page.locator('[data-weekly-action="recipe"]').count() == 3

    page.locator('[data-weekly-action="recipe"]').first.click()
    page.locator("#actionModalContent").get_by_text("Test tarifi").wait_for()
    page.locator('#actionModal [data-weekly-action="close"]').last.click()
    assert "hidden" in page.locator("#actionModal").get_attribute("class")

    page.locator('[data-weekly-action="alternative"]').first.click()
    page.locator("#actionModalContent").get_by_text("Sebzeli omlet").wait_for()
    page.locator('#actionModal [data-weekly-action="close"]').last.click()

    page.locator('[data-weekly-action="snack"]').click()
    page.locator("#actionModalContent").get_by_text("Bir porsiyon elma").wait_for()
    page.locator('#actionModal [data-weekly-action="close"]').last.click()

    checkbox = page.locator('#planResult input[type="checkbox"]').first
    checkbox.check(force=True)
    assert page.evaluate("localStorage.getItem('cm_check_meal-0-0')") == "true"
    page.locator("#planResult .day-progress").get_by_text("Durum: 1/3").wait_for()

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
    page.route("**/api/smart-grocery", lambda route: _json(route, smart_grocery_response))
    page.route("**/api/shopping-list", lambda route: _json(route, {"success": True, "rapor": "Tahmini toplam: 120 TL"}))
    page.route("**/api/feedback", lambda route: _json(route, {"success": True, "message": "Geri bildirim kaydedildi."}))

    page.locator('[data-grocery-action="open"]').click()
    page.locator("#smartGroceryContent").get_by_text("e2e-grocery-decision").wait_for()
    assert page.locator("#smartGroceryContent").get_by_text("Ispanak").count() == 1
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

    def chat_stream(route) -> None:
        body = "".join(
            [
                'event: status\ndata: {"status":"Kontroller calisiyor"}\n\n',
                'event: token\ndata: {"chunk":"Profiline gore test yaniti."}\n\n',
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
    page.fill("[data-cm-assistant-input]", "Aksam ne yiyebilirim?")
    page.locator("[data-cm-assistant-form]").evaluate("form => form.requestSubmit()")
    page.locator("[data-cm-assistant-body]").get_by_text("Profiline gore test yaniti.").wait_for()
    page.locator("[data-cm-assistant-body]").get_by_text("e2e-chat-decision").wait_for()
    page.locator("[data-cm-assistant-body]").get_by_text("E2E resmi kaynak").wait_for()

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

    page.evaluate("window.MenuScanner.startQRScanner()")
    page.locator("#qr-reader").get_by_text("QR okuyucu").wait_for()

    page.route(
        "**/api/scan-menu-image",
        lambda route: _json(route, {"detail": "E2E gecersiz menu gorseli."}, status=400),
    )
    page.set_input_files(
        "#menuImageInput",
        {"name": "broken.txt", "mimeType": "text/plain", "buffer": b"not-an-image"},
    )
    page.locator("#menuScanResult").get_by_text("E2E gecersiz menu gorseli.").wait_for()

    page.route(
        "**/api/fridge-scan",
        lambda route: _json(
            route,
            {"success": True, "malzemeler": "Yumurta, domates", "tarif": "E2E sebzeli omlet"},
        ),
    )
    page.evaluate("switchTab('buzdolabi')")
    page.set_input_files(
        "#fridgeImageInput",
        {"name": "fridge.png", "mimeType": "image/png", "buffer": b"not-a-real-image-for-mocked-e2e"},
    )
    page.locator("#fridgeScanResult").get_by_text("E2E sebzeli omlet").wait_for()

    page.unroute("**/api/fridge-scan")
    page.route(
        "**/api/fridge-scan",
        lambda route: _json(route, {"detail": "E2E gecersiz buzdolabi gorseli."}, status=400),
    )
    page.set_input_files(
        "#fridgeImageInput",
        {"name": "broken.txt", "mimeType": "text/plain", "buffer": b"not-an-image"},
    )
    page.locator("#fridgeScanResult").get_by_text("E2E gecersiz buzdolabi gorseli.").wait_for()
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
