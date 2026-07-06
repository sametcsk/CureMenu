(function () {
    const STORAGE_OPEN = "cm_assistant_open";
    const API = "";

    const quickPrompts = [
        {
            label: "Bugün ne yesem?",
            prompt: "Profilime ve sağlık bilgilerime göre bugün güvenli bir akşam yemeği önerir misin?",
        },
        {
            label: "İlaç uyumu",
            prompt: "Kullandığım ilaçlara göre hangi yiyeceklere dikkat etmeliyim? Kısa ve anlaşılır anlat.",
        },
        {
            label: "Menüye bak",
            action: "tarayici",
            prompt: "Restoran menüsünü sağlık profilime göre kontrol etmek istiyorum.",
        },
        {
            label: "Tahlil yorumla",
            action: "tahlil",
            prompt: "Tahlil sonuçlarımı yükleyip beslenme önerilerimde dikkate almak istiyorum.",
        },
    ];

    function escapeHtml(value) {
        const div = document.createElement("div");
        div.textContent = value || "";
        return div.innerHTML;
    }

    function renderAssistantText(value) {
        const text = value || "";
        try {
            if (window.marked && window.DOMPurify) {
                return DOMPurify.sanitize(marked.parse(text));
            }
        } catch (_) {
            /* plain-text fallback */
        }
        return escapeHtml(text).replace(/\n/g, "<br>");
    }

    function getUser() {
        return {
            telefon: localStorage.getItem("cm_telefon") || "",
            kullanici_adi: localStorage.getItem("cm_kullanici_adi") || "",
            hasProfile: localStorage.getItem("cm_has_profile") === "true",
            disclaimerOk: localStorage.getItem("cm_disclaimer_ok") === "true",
        };
    }

    function isDashboard() {
        return window.location.pathname === "/dashboard";
    }

    function canUseChat() {
        const user = getUser();
        return Boolean(user.telefon && user.disclaimerOk);
    }

    function injectStyles() {
        if (document.getElementById("cm-assistant-style")) return;

        const style = document.createElement("style");
        style.id = "cm-assistant-style";
        style.textContent = `
            .cm-assistant-root {
                position: fixed;
                right: 22px;
                bottom: 22px;
                z-index: 160;
                font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
                color: #102033;
            }
            .cm-assistant-launcher {
                width: 64px;
                height: 64px;
                border: 0;
                border-radius: 18px;
                background: #005c55;
                color: #fff;
                box-shadow: 0 20px 44px rgba(0, 92, 85, 0.28);
                display: grid;
                place-items: center;
                cursor: pointer;
                transition: transform 180ms ease, box-shadow 180ms ease, background 180ms ease;
            }
            .cm-assistant-launcher:hover {
                transform: translateY(-2px);
                background: #007168;
                box-shadow: 0 24px 52px rgba(0, 92, 85, 0.34);
            }
            .cm-assistant-launcher .material-symbols-outlined {
                font-size: 30px;
                font-variation-settings: "FILL" 1;
            }
            .cm-assistant-panel {
                width: min(390px, calc(100vw - 28px));
                height: min(620px, calc(100vh - 110px));
                position: absolute;
                right: 0;
                bottom: 78px;
                border-radius: 18px;
                background: #ffffff;
                border: 1px solid rgba(189, 201, 198, 0.72);
                box-shadow: 0 24px 70px rgba(16, 32, 51, 0.2);
                overflow: hidden;
                display: none;
                grid-template-rows: auto 1fr auto;
            }
            .cm-assistant-root[data-open="true"] .cm-assistant-panel {
                display: grid;
                animation: cmAssistantEnter 180ms ease both;
            }
            @keyframes cmAssistantEnter {
                from { opacity: 0; transform: translateY(10px) scale(0.98); }
                to { opacity: 1; transform: translateY(0) scale(1); }
            }
            .cm-assistant-header {
                padding: 16px;
                background: linear-gradient(135deg, #005c55 0%, #0b1c30 100%);
                color: #fff;
                display: flex;
                align-items: center;
                justify-content: space-between;
                gap: 12px;
            }
            .cm-assistant-title {
                display: flex;
                align-items: center;
                gap: 10px;
                min-width: 0;
            }
            .cm-assistant-avatar {
                width: 38px;
                height: 38px;
                border-radius: 12px;
                background: rgba(255,255,255,0.14);
                display: grid;
                place-items: center;
                flex: 0 0 auto;
            }
            .cm-assistant-title strong {
                display: block;
                font-size: 15px;
                line-height: 1.15;
            }
            .cm-assistant-title span {
                display: block;
                margin-top: 2px;
                font-size: 12px;
                color: rgba(255,255,255,0.75);
                white-space: nowrap;
                overflow: hidden;
                text-overflow: ellipsis;
            }
            .cm-assistant-close {
                border: 0;
                width: 34px;
                height: 34px;
                border-radius: 10px;
                background: rgba(255,255,255,0.1);
                color: #fff;
                display: grid;
                place-items: center;
                cursor: pointer;
            }
            .cm-assistant-body {
                overflow-y: auto;
                padding: 14px;
                background: #f7fbfc;
                display: flex;
                flex-direction: column;
                gap: 10px;
            }
            .cm-assistant-message {
                max-width: 86%;
                border-radius: 14px;
                padding: 11px 12px;
                font-size: 13px;
                line-height: 1.5;
                border: 1px solid transparent;
                word-wrap: break-word;
            }
            .cm-assistant-message.bot {
                align-self: flex-start;
                background: #ffffff;
                border-color: rgba(189, 201, 198, 0.7);
                color: #102033;
            }
            .cm-assistant-message.user {
                align-self: flex-end;
                background: #005c55;
                color: #ffffff;
            }
            .cm-assistant-message.soft {
                max-width: 100%;
                background: #e9f7f4;
                border-color: rgba(0, 92, 85, 0.16);
                color: #31514d;
            }
            .cm-assistant-quick {
                display: flex;
                gap: 8px;
                flex-wrap: wrap;
                padding: 0 14px 12px;
                background: #ffffff;
                border-top: 1px solid rgba(189, 201, 198, 0.42);
            }
            .cm-assistant-quick.is-hidden {
                display: none;
            }
            .cm-assistant-quick button {
                border: 1px solid rgba(189, 201, 198, 0.7);
                background: #ffffff;
                color: #005c55;
                border-radius: 999px;
                min-height: 32px;
                padding: 0 10px;
                font-size: 12px;
                font-weight: 700;
                cursor: pointer;
                transition: background 160ms ease, border-color 160ms ease;
            }
            .cm-assistant-quick button:hover {
                background: #e9f7f4;
                border-color: rgba(0, 92, 85, 0.34);
            }
            .cm-assistant-inputbar {
                padding: 12px;
                background: #ffffff;
                border-top: 1px solid rgba(189, 201, 198, 0.55);
                display: flex;
                gap: 8px;
                align-items: flex-end;
            }
            .cm-assistant-inputbar textarea {
                flex: 1;
                min-height: 42px;
                max-height: 96px;
                resize: none;
                border: 1px solid rgba(189, 201, 198, 0.9);
                border-radius: 14px;
                padding: 10px 12px;
                outline: none;
                color: #102033;
                line-height: 1.35;
                font-size: 13px;
            }
            .cm-assistant-inputbar textarea:focus {
                border-color: #005c55;
                box-shadow: 0 0 0 4px rgba(0, 92, 85, 0.1);
            }
            .cm-assistant-send {
                width: 42px;
                height: 42px;
                border: 0;
                border-radius: 14px;
                background: #005c55;
                color: #fff;
                display: grid;
                place-items: center;
                cursor: pointer;
                flex: 0 0 auto;
            }
            .cm-assistant-send:disabled {
                opacity: 0.55;
                cursor: wait;
            }
            .cm-assistant-actions {
                display: grid;
                grid-template-columns: 1fr 1fr;
                gap: 8px;
                margin-top: 4px;
            }
            .cm-assistant-actions button {
                border: 1px solid rgba(189, 201, 198, 0.8);
                border-radius: 12px;
                min-height: 38px;
                padding: 8px 10px;
                background: #ffffff;
                color: #005c55;
                font-weight: 800;
                cursor: pointer;
                text-align: left;
                font-size: 12px;
            }
            .cm-assistant-typing {
                display: inline-flex;
                gap: 4px;
                align-items: center;
            }
            .cm-assistant-typing span {
                width: 6px;
                height: 6px;
                border-radius: 50%;
                background: #8aa09c;
                animation: cmAssistantBlink 1.2s infinite both;
            }
            .cm-assistant-typing span:nth-child(2) { animation-delay: 0.16s; }
            .cm-assistant-typing span:nth-child(3) { animation-delay: 0.32s; }
            @keyframes cmAssistantBlink {
                0%, 80%, 100% { opacity: 0.25; transform: translateY(0); }
                40% { opacity: 1; transform: translateY(-2px); }
            }
            @media (max-width: 768px) {
                .cm-assistant-root {
                    right: 14px;
                    bottom: 84px;
                }
                .cm-assistant-panel {
                    right: -2px;
                    bottom: 76px;
                    width: calc(100vw - 24px);
                    height: min(620px, calc(100vh - 184px));
                }
                .cm-assistant-launcher {
                    width: 58px;
                    height: 58px;
                    border-radius: 16px;
                }
            }
        `;
        document.head.appendChild(style);
    }

    function addMessage(root, text, type = "bot") {
        const body = root.querySelector("[data-cm-assistant-body]");
        const item = document.createElement("div");
        item.className = `cm-assistant-message ${type}`;
        item.innerHTML = escapeHtml(text).replace(/\n/g, "<br>");
        body.appendChild(item);
        body.scrollTop = body.scrollHeight;
        return item;
    }

    function addRichMessage(root, html, type = "bot") {
        const body = root.querySelector("[data-cm-assistant-body]");
        const item = document.createElement("div");
        item.className = `cm-assistant-message ${type}`;
        item.innerHTML = window.DOMPurify ? DOMPurify.sanitize(html) : html;
        body.appendChild(item);
        body.scrollTop = body.scrollHeight;
        return item;
    }

    function setOpen(root, value) {
        root.dataset.open = value ? "true" : "false";
        localStorage.setItem(STORAGE_OPEN, value ? "true" : "false");
        if (value) {
            setTimeout(() => root.querySelector("[data-cm-assistant-input]")?.focus(), 80);
        }
    }

    function hideQuickPrompts(root) {
        root.querySelector("[data-cm-assistant-quick]")?.classList.add("is-hidden");
    }

    function switchDashboardTab(tab) {
        if (isDashboard() && typeof window.switchTab === "function") {
            window.switchTab(tab);
            return true;
        }
        return false;
    }

    function handleFeatureAction(root, action) {
        const labels = {
            aile: "Profil sayfasını açıyorum.",
            plan: "Haftalık plan alanını açıyorum.",
            tarayici: "Menü tarama alanını açıyorum.",
            tahlil: "Tahlil yükleme alanını açıyorum.",
            kpi: "Güvenlik özetini açıyorum.",
            curebot: "CureBot'u burada açıyorum.",
        };

        if (action === "curebot") {
            setOpen(root, true);
            addMessage(root, labels[action], "soft");
            return;
        }

        if (switchDashboardTab(action)) {
            addMessage(root, labels[action] || "İlgili alanı açıyorum.", "soft");
            return;
        }

        if (!canUseChat()) {
            addMessage(root, "Bunu kişisel hale getirmek için önce kısa profilini oluşturalım.", "soft");
            setTimeout(() => {
                window.location.href = "/giris";
            }, 650);
            return;
        }

        addMessage(root, "Bunu dashboard içinde açabilirim. Seni oraya yönlendireyim.", "soft");
        setTimeout(() => {
            window.location.href = "/dashboard";
        }, 650);
    }

    function renderWelcome(root) {
        const user = getUser();
        const name = user.kullanici_adi || "Merhaba";

        addMessage(
            root,
            `${name}, ben CureBot. İstersen hızlıca güvenli öğün seçmene, menü kontrol etmene, tahlil ya da profil adımlarına geçmene yardım ederim.`
        );

        const html = `
            <div>Buradan hızlıca başlayabilirsin:</div>
            <div class="cm-assistant-actions">
                <button type="button" data-cm-feature="plan">Haftalık plan</button>
                <button type="button" data-cm-feature="tarayici">Menü tara</button>
                <button type="button" data-cm-feature="tahlil">Tahlil yükle</button>
                <button type="button" data-cm-feature="aile">Profilim</button>
            </div>
        `;
        addRichMessage(root, html, "soft");

        if (!canUseChat()) {
            addMessage(
                root,
                "Sohbeti kişisel hale getirmek için önce giriş yapman ve sağlık profilini oluşturman gerekiyor. Yine de sana uygulama içinde yol gösterebilirim.",
                "soft"
            );
        }
    }

    async function fetchChatWithRefresh(body, signal) {
        const request = () => fetch(`${API}/api/chat`, {
            method: "POST",
            credentials: "include",
            headers: { "Content-Type": "application/json" },
            body,
            signal,
        });

        let response = await request();
        if (response.status !== 401) return response;

        const refresh = await fetch(`${API}/api/refresh`, {
            method: "POST",
            credentials: "include",
        });
        if (!refresh.ok) return response;
        return request();
    }

    async function sendToChat(root, message) {
        const input = root.querySelector("[data-cm-assistant-input]");
        const send = root.querySelector("[data-cm-assistant-send]");
        const text = (message || input.value || "").trim();
        if (!text || send.disabled) return;

        hideQuickPrompts(root);
        input.value = "";
        addMessage(root, text, "user");

        if (!canUseChat()) {
            addMessage(
                root,
                "Bunu sana özel yanıtlayabilmem için önce kısa profilini oluşturalım. Seni giriş ekranına yönlendirebilirim.",
                "soft"
            );
            setTimeout(() => {
                window.location.href = "/giris";
            }, 900);
            return;
        }

        send.disabled = true;
        const typing = addRichMessage(
            root,
            '<span class="cm-assistant-typing"><span></span><span></span><span></span></span>',
            "bot"
        );

        let answerNode = null;
        let answer = "";
        let doneSeen = false;
        const controller = new AbortController();
        const timeoutId = setTimeout(() => controller.abort(), 90000);

        try {
            const response = await fetchChatWithRefresh(
                JSON.stringify({ mesaj: text, kimin_icin: "kendim" }),
                controller.signal
            );

            if (!response.ok || !response.body) {
                throw new Error(response.status === 401 ? "Oturumunu yenilememiz gerekiyor." : "Şu an yanıtı hazırlayamadım.");
            }

            const reader = response.body.getReader();
            const decoder = new TextDecoder();
            let buffer = "";
            typing.remove();

            while (true) {
                const { value, done } = await reader.read();
                if (done) break;
                buffer += decoder.decode(value, { stream: true });
                const parts = buffer.split("\n\n");
                buffer = parts.pop() || "";

                for (const part of parts) {
                    const lines = part.split("\n");
                    const eventLine = lines.find((line) => line.startsWith("event:"));
                    const dataLines = lines.filter((line) => line.startsWith("data:"));
                    if (!eventLine) continue;

                    const eventName = eventLine.replace("event:", "").trim();
                    let payload = {};
                    try {
                        payload = JSON.parse(dataLines.map((line) => line.replace("data:", "").trim()).join("\n") || "{}");
                    } catch (_) {
                        payload = {};
                    }

                    if ((eventName === "message" || eventName === "token") && payload.chunk) {
                        answer += payload.chunk;
                        if (!answerNode) answerNode = addMessage(root, "", "bot");
                        answerNode.innerHTML = renderAssistantText(answer);
                        answerNode.scrollIntoView({ block: "end" });
                    }

                    if (eventName === "error") {
                        if (!answerNode) answerNode = addMessage(root, "", "bot");
                        answerNode.innerHTML = renderAssistantText(payload.message || "Yanıtı tamamlayamadım; istersen birazdan tekrar deneyelim.");
                    }

                    if (eventName === "done") {
                        doneSeen = true;
                    }
                }
            }

            if (!answerNode && !doneSeen) {
                addMessage(root, "Yanıt tamamlanamadı. Birazdan tekrar deneyebiliriz.", "soft");
            }
        } catch (error) {
            if (error.name === "AbortError") {
                addMessage(root, "Yanıt süresi uzadı. İstersen aynı soruyu biraz daha kısa yazarak tekrar deneyelim.", "soft");
            } else {
                addMessage(root, `${error.message || "Bağlantı kurulamadı."} Birazdan tekrar deneyebiliriz.`, "soft");
            }
        } finally {
            clearTimeout(timeoutId);
            typing.remove();
            send.disabled = false;
        }
    }

    function createRoot() {
        if (document.getElementById("cm-assistant-root")) return;

        injectStyles();

        const root = document.createElement("section");
        root.id = "cm-assistant-root";
        root.className = "cm-assistant-root";
        root.dataset.open = localStorage.getItem(STORAGE_OPEN) === "true" ? "true" : "false";
        root.innerHTML = `
            <div class="cm-assistant-panel" role="dialog" aria-label="CureBot yardımcı">
                <header class="cm-assistant-header">
                    <div class="cm-assistant-title">
                        <div class="cm-assistant-avatar"><span class="material-symbols-outlined">smart_toy</span></div>
                        <div>
                            <strong>CureBot</strong>
                            <span>Her sayfada yanında</span>
                        </div>
                    </div>
                    <button class="cm-assistant-close" type="button" aria-label="CureBot'u kapat" data-cm-assistant-close>
                        <span class="material-symbols-outlined">close</span>
                    </button>
                </header>
                <div class="cm-assistant-body" data-cm-assistant-body></div>
                <div>
                    <div class="cm-assistant-quick" data-cm-assistant-quick>
                        ${quickPrompts.map((item, index) => `<button type="button" data-cm-quick="${index}">${escapeHtml(item.label)}</button>`).join("")}
                    </div>
                    <form class="cm-assistant-inputbar" data-cm-assistant-form>
                        <textarea rows="1" data-cm-assistant-input placeholder="CureBot'a kısa bir şey sor..."></textarea>
                        <button class="cm-assistant-send" type="submit" data-cm-assistant-send aria-label="Gönder">
                            <span class="material-symbols-outlined">send</span>
                        </button>
                    </form>
                </div>
            </div>
            <button class="cm-assistant-launcher" type="button" aria-label="CureBot'u aç" data-cm-assistant-launcher>
                <span class="material-symbols-outlined">support_agent</span>
            </button>
        `;

        document.body.appendChild(root);
        renderWelcome(root);

        root.querySelector("[data-cm-assistant-launcher]").addEventListener("click", () => {
            setOpen(root, root.dataset.open !== "true");
        });

        root.querySelector("[data-cm-assistant-close]").addEventListener("click", () => setOpen(root, false));

        root.querySelector("[data-cm-assistant-form]").addEventListener("submit", (event) => {
            event.preventDefault();
            sendToChat(root);
        });

        root.querySelector("[data-cm-assistant-input]").addEventListener("keydown", (event) => {
            if (event.key === "Enter" && !event.shiftKey) {
                event.preventDefault();
                sendToChat(root);
            }
        });

        root.addEventListener("click", (event) => {
            const quick = event.target.closest("[data-cm-quick]");
            if (quick) {
                const item = quickPrompts[Number(quick.dataset.cmQuick)];
                if (!item) return;
                if (item.action) handleFeatureAction(root, item.action);
                sendToChat(root, item.prompt);
                return;
            }

            const feature = event.target.closest("[data-cm-feature]");
            if (feature) {
                handleFeatureAction(root, feature.dataset.cmFeature);
            }
        });

        window.openCureMenuAssistant = function (message) {
            setOpen(root, true);
            if (message) {
                sendToChat(root, String(message));
            }
        };
        window.askCureBot = window.openCureMenuAssistant;
        window.addEventListener("cm-open-assistant", (event) => {
            window.openCureMenuAssistant(event.detail && event.detail.message);
        });
    }

    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", createRoot);
    } else {
        createRoot();
    }
})();
