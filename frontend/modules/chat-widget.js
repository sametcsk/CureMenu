// frontend/modules/chat-widget.js

window.ChatWidget = {
    root: null,
    controller: null,
    answerNode: null,
    typingNode: null,
    STORAGE_OPEN: "cm_assistant_open",

    quickPrompts: [
        { label: "Bugün ne yesem?", prompt: "Profilime ve sağlık bilgilerime göre bugün güvenli bir akşam yemeği önerir misin?" },
        { label: "İlaç uyumu", prompt: "Kullandığım ilaçlara göre hangi yiyeceklere dikkat etmeliyim? Kısa ve anlaşılır anlat." },
        { label: "Menüye bak", action: "tarayici", prompt: "Restoran menüsünü sağlık profilime göre kontrol etmek istiyorum." },
        { label: "Tahlil yorumla", action: "tahlil", prompt: "Tahlil sonuçlarımı yükleyip beslenme önerilerimde dikkate almak istiyorum." }
    ],

    init() {
        if (this.root) return;
        
        this.injectStyles();
        
        this.root = document.createElement("section");
        this.root.id = "cm-assistant-root";
        this.root.className = "cm-assistant-root";
        this.root.dataset.open = localStorage.getItem(this.STORAGE_OPEN) === "true" ? "true" : "false";
        
        this.root.innerHTML = `
            <div class="cm-assistant-panel" role="dialog" aria-label="CureBot yardımcı">
                <header class="cm-assistant-header">
                    <div class="cm-assistant-title">
                        <div class="cm-assistant-avatar"><span class="material-symbols-outlined">smart_toy</span></div>
                        <div>
                            <strong>CureBot</strong>
                            <span id="cm-assistant-status">Her sayfada yanında</span>
                        </div>
                    </div>
                    <button class="cm-assistant-close" type="button" aria-label="CureBot'u kapat" data-cm-assistant-close>
                        <span class="material-symbols-outlined">close</span>
                    </button>
                </header>
                <div class="cm-assistant-body" data-cm-assistant-body></div>
                <div>
                    <div class="cm-assistant-quick" data-cm-assistant-quick>
                        ${this.quickPrompts.map((item, i) => `<button type="button" data-cm-quick="${i}">${window.escapeHtml ? escapeHtml(item.label) : item.label}</button>`).join("")}
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

        document.body.appendChild(this.root);
        this.renderWelcome();
        this.bindEvents();

        window.openCureMenuAssistant = (msg) => this.open(msg);
        window.askCureBot = (msg) => this.open(msg);
        window.addEventListener("cm-open-assistant", (e) => this.open(e.detail?.message));
    },

    bindEvents() {
        this.root.querySelector("[data-cm-assistant-launcher]").addEventListener("click", () => this.toggle());
        this.root.querySelector("[data-cm-assistant-close]").addEventListener("click", () => this.close());
        
        const form = this.root.querySelector("[data-cm-assistant-form]");
        const input = this.root.querySelector("[data-cm-assistant-input]");
        
        form.addEventListener("submit", (e) => {
            e.preventDefault();
            this.handleSend();
        });

        input.addEventListener("keydown", (e) => {
            if (e.key === "Enter" && !e.shiftKey) {
                e.preventDefault();
                this.handleSend();
            }
        });

        this.root.addEventListener("click", (e) => {
            const quick = e.target.closest("[data-cm-quick]");
            if (quick) {
                const item = this.quickPrompts[Number(quick.dataset.cmQuick)];
                if (!item) return;
                if (item.action && typeof window.switchTab === 'function') {
                    window.switchTab(item.action);
                }
                this.sendMessage(item.prompt);
                return;
            }
            const feature = e.target.closest("[data-cm-feature]");
            if (feature) {
                if (typeof window.switchTab === 'function') {
                    window.switchTab(feature.dataset.cmFeature);
                } else {
                    window.location.href = "/dashboard";
                }
            }
        });
    },

    open(message) {
        if (!this.root) this.init();
        this.root.dataset.open = "true";
        localStorage.setItem(this.STORAGE_OPEN, "true");
        if (message) {
            this.sendMessage(message);
        } else {
            setTimeout(() => this.root.querySelector("[data-cm-assistant-input]")?.focus(), 80);
        }
    },

    close() {
        if (!this.root) return;
        this.root.dataset.open = "false";
        localStorage.setItem(this.STORAGE_OPEN, "false");
    },

    toggle() {
        if (!this.root) return;
        const isOpen = this.root.dataset.open === "true";
        isOpen ? this.close() : this.open();
    },

    setStatus(text) {
        if (!this.root) return;
        const statusEl = this.root.querySelector("#cm-assistant-status");
        if (statusEl) statusEl.textContent = text || "Her sayfada yanında";
    },

    showTyping() {
        this.hideTyping();
        const body = this.root.querySelector("[data-cm-assistant-body]");
        this.typingNode = document.createElement("div");
        this.typingNode.className = "cm-assistant-message bot";
        this.typingNode.innerHTML = '<span class="cm-assistant-typing"><span></span><span></span><span></span></span>';
        body.appendChild(this.typingNode);
        body.scrollTop = body.scrollHeight;
    },

    hideTyping() {
        if (this.typingNode) {
            this.typingNode.remove();
            this.typingNode = null;
        }
    },

    addMessage(text, type = "bot", isHtml = false) {
        const body = this.root.querySelector("[data-cm-assistant-body]");
        const item = document.createElement("div");
        item.className = `cm-assistant-message ${type}`;
        
        if (isHtml) {
            item.innerHTML = window.DOMPurify ? DOMPurify.sanitize(text) : text;
        } else {
            if (window.escapeHtml) {
                item.innerHTML = escapeHtml(text).replace(/\n/g, "<br>");
            } else {
                item.textContent = text;
            }
        }
        
        body.appendChild(item);
        body.scrollTop = body.scrollHeight;
        return item;
    },

    appendToken(token) {
        if (!this.answerNode) {
            this.hideTyping();
            this.answerNode = this.addMessage("", "bot", true);
        }
        if (window.formatMarkdownSafe) {
            this.answerNode.innerHTML = formatMarkdownSafe(token);
        } else if (window.escapeHtml) {
            this.answerNode.innerHTML = escapeHtml(token).replace(/\n/g, "<br>");
        } else {
            this.answerNode.textContent = token;
        }
        
        const body = this.root.querySelector("[data-cm-assistant-body]");
        body.scrollTop = body.scrollHeight;
    },

    showError(msg) {
        this.hideTyping();
        this.addMessage(msg, "soft");
        this.resetState();
    },

    resetState() {
        this.hideTyping();
        this.setStatus("Her sayfada yanında");
        this.answerNode = null;
        if (this.controller) {
            this.controller.abort();
            this.controller = null;
        }
        const sendBtn = this.root.querySelector("[data-cm-assistant-send]");
        if (sendBtn) sendBtn.disabled = false;
    },

    stopGeneration() {
        if (this.controller) {
            this.controller.abort();
            this.controller = null;
        }
        this.resetState();
    },

    handleSend() {
        const input = this.root.querySelector("[data-cm-assistant-input]");
        const text = input.value.trim();
        if (!text) return;
        input.value = "";
        this.sendMessage(text);
    },

    async sendMessage(message) {
        if (!this.root) this.init();
        
        const sendBtn = this.root.querySelector("[data-cm-assistant-send]");
        if (sendBtn.disabled) return;
        
        if (window.AuthManager && !window.AuthManager.getUser().telefon) {
            this.addMessage("Bunu sana özel yanıtlayabilmem için önce kısa profilini oluşturalım.", "soft");
            setTimeout(() => window.location.href = "/giris", 900);
            return;
        }

        this.root.querySelector("[data-cm-assistant-quick]")?.classList.add("is-hidden");
        this.addMessage(message, "user");
        
        sendBtn.disabled = true;
        this.setStatus("Sistem hazırlanıyor...");
        this.showTyping();
        this.answerNode = null;
        
        this.controller = new AbortController();
        let fullAnswer = "";
        let doneSeen = false;
        
        const timeoutId = setTimeout(() => {
            if (!doneSeen) {
                this.stopGeneration();
                this.showError("Yanıt beklenenden uzun sürdü. Lütfen tekrar deneyin.");
            }
        }, 60000);

        try {
            const apiEndpoint = (window.API || '') + '/api/chat';
            
            if (!window.safeFetchStream) throw new Error("API client yüklü değil.");
            
            const response = await window.safeFetchStream(apiEndpoint, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ mesaj: message, kimin_icin: "kendim" }),
                signal: this.controller.signal
            });

            if (!response.ok || !response.body) {
                throw new Error(response.status === 401 ? "Oturumunu yenilememiz gerekiyor." : "Şu an yanıtı hazırlayamadım.");
            }

            const reader = response.body.getReader();
            const decoder = new TextDecoder();
            let buffer = "";

            while (true) {
                const { value, done } = await reader.read();
                if (done) break;
                
                buffer += decoder.decode(value, { stream: true });
                const parts = buffer.split("\\n\\n");
                buffer = parts.pop() || "";

                for (const part of parts) {
                    const lines = part.split("\\n");
                    const eventLine = lines.find(l => l.startsWith("event:"));
                    const dataLines = lines.filter(l => l.startsWith("data:"));
                    if (!eventLine) continue;

                    const eventName = eventLine.replace("event:", "").trim();
                    let payload = {};
                    try {
                        payload = JSON.parse(dataLines.map(l => l.replace("data:", "").trim()).join("\\n") || "{}");
                    } catch (_) {}

                    if (eventName === "status") {
                        this.setStatus(payload.status || "çalışıyor...");
                    } else if (eventName === "message" || eventName === "token") {
                        this.setStatus("CureBot yazıyor...");
                        fullAnswer += (payload.chunk || "");
                        this.appendToken(fullAnswer);
                    } else if (eventName === "error") {
                        this.showError(payload.message || "Yanıtı tamamlayamadım.");
                        doneSeen = true;
                    } else if (eventName === "done") {
                        doneSeen = true;
                    }
                }
            }

            if (!doneSeen && !fullAnswer) {
                throw new Error("Yanıt tamamlanamadı.");
            }
        } catch (error) {
            if (error.name === "AbortError" || this.controller === null) {
                // Ignore if manually aborted
            } else {
                this.showError(`${error.message || "Bağlantı kurulamadı."}`);
            }
        } finally {
            clearTimeout(timeoutId);
            this.resetState();
        }
    },

    renderWelcome() {
        const user = window.AuthManager ? window.AuthManager.getUser() : {kullanici_adi: ''};
        const name = user.kullanici_adi || "Merhaba";
        this.addMessage(`${name}, ben CureBot. İstersen hızlıca güvenli öğün seçmene, menü kontrol etmene, tahlil ya da profil adımlarına geçmene yardım ederim.`);
        const html = `
            <div>Buradan hızlıca başlayabilirsin:</div>
            <div class="cm-assistant-actions">
                <button type="button" data-cm-feature="dashboard">Haftalık plan</button>
                <button type="button" data-cm-feature="tahlil">Tahlil yükle</button>
                <button type="button" data-cm-feature="profile">Profilim</button>
            </div>
        `;
        this.addMessage(html, "soft", true);
    },

    injectStyles() {
        if (document.getElementById("cm-assistant-style")) return;
        const style = document.createElement("style");
        style.id = "cm-assistant-style";
        style.textContent = `
            .cm-assistant-root { position: fixed; right: 22px; bottom: 22px; z-index: 160; font-family: Inter, sans-serif; color: #102033; }
            .cm-assistant-launcher { width: 64px; height: 64px; border: 0; border-radius: 18px; background: #005c55; color: #fff; box-shadow: 0 20px 44px rgba(0, 92, 85, 0.28); display: grid; place-items: center; cursor: pointer; transition: transform 180ms ease, box-shadow 180ms ease, background 180ms ease; }
            .cm-assistant-launcher:hover { transform: translateY(-2px); background: #007168; box-shadow: 0 24px 52px rgba(0, 92, 85, 0.34); }
            .cm-assistant-launcher .material-symbols-outlined { font-size: 30px; font-variation-settings: "FILL" 1; }
            .cm-assistant-panel { width: min(390px, calc(100vw - 28px)); height: min(620px, calc(100vh - 110px)); position: absolute; right: 0; bottom: 78px; border-radius: 18px; background: #ffffff; border: 1px solid rgba(189, 201, 198, 0.72); box-shadow: 0 24px 70px rgba(16, 32, 51, 0.2); overflow: hidden; display: none; grid-template-rows: auto 1fr auto; }
            .cm-assistant-root[data-open="true"] .cm-assistant-panel { display: grid; animation: cmAssistantEnter 180ms ease both; }
            @keyframes cmAssistantEnter { from { opacity: 0; transform: translateY(10px) scale(0.98); } to { opacity: 1; transform: translateY(0) scale(1); } }
            .cm-assistant-header { padding: 16px; background: linear-gradient(135deg, #005c55 0%, #0b1c30 100%); color: #fff; display: flex; align-items: center; justify-content: space-between; gap: 12px; }
            .cm-assistant-title { display: flex; align-items: center; gap: 10px; min-width: 0; }
            .cm-assistant-avatar { width: 38px; height: 38px; border-radius: 12px; background: rgba(255,255,255,0.14); display: grid; place-items: center; flex: 0 0 auto; }
            .cm-assistant-title strong { display: block; font-size: 15px; line-height: 1.15; }
            .cm-assistant-title span { display: block; margin-top: 2px; font-size: 12px; color: rgba(255,255,255,0.75); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
            .cm-assistant-close { border: 0; width: 34px; height: 34px; border-radius: 10px; background: rgba(255,255,255,0.1); color: #fff; display: grid; place-items: center; cursor: pointer; }
            .cm-assistant-body { overflow-y: auto; padding: 14px; background: #f7fbfc; display: flex; flex-direction: column; gap: 10px; }
            .cm-assistant-message { max-width: 86%; border-radius: 14px; padding: 11px 12px; font-size: 13px; line-height: 1.5; border: 1px solid transparent; word-wrap: break-word; }
            .cm-assistant-message.bot { align-self: flex-start; background: #ffffff; border-color: rgba(189, 201, 198, 0.7); color: #102033; }
            .cm-assistant-message.user { align-self: flex-end; background: #005c55; color: #ffffff; }
            .cm-assistant-message.soft { max-width: 100%; background: #e9f7f4; border-color: rgba(0, 92, 85, 0.16); color: #31514d; }
            .cm-assistant-quick { display: flex; gap: 8px; flex-wrap: wrap; padding: 0 14px 12px; background: #ffffff; border-top: 1px solid rgba(189, 201, 198, 0.42); }
            .cm-assistant-quick.is-hidden { display: none; }
            .cm-assistant-quick button { border: 1px solid rgba(189, 201, 198, 0.7); background: #ffffff; color: #005c55; border-radius: 999px; min-height: 32px; padding: 0 10px; font-size: 12px; font-weight: 700; cursor: pointer; transition: background 160ms ease, border-color 160ms ease; }
            .cm-assistant-quick button:hover { background: #e9f7f4; border-color: rgba(0, 92, 85, 0.34); }
            .cm-assistant-inputbar { padding: 12px; background: #ffffff; border-top: 1px solid rgba(189, 201, 198, 0.55); display: flex; gap: 8px; align-items: flex-end; }
            .cm-assistant-inputbar textarea { flex: 1; min-height: 42px; max-height: 96px; resize: none; border: 1px solid rgba(189, 201, 198, 0.9); border-radius: 14px; padding: 10px 12px; outline: none; color: #102033; line-height: 1.35; font-size: 13px; }
            .cm-assistant-inputbar textarea:focus { border-color: #005c55; box-shadow: 0 0 0 4px rgba(0, 92, 85, 0.1); }
            .cm-assistant-send { width: 42px; height: 42px; border: 0; border-radius: 14px; background: #005c55; color: #fff; display: grid; place-items: center; cursor: pointer; flex: 0 0 auto; }
            .cm-assistant-send:disabled { opacity: 0.55; cursor: wait; }
            .cm-assistant-actions { display: grid; grid-template-columns: 1fr 1fr; gap: 8px; margin-top: 4px; }
            .cm-assistant-actions button { border: 1px solid rgba(189, 201, 198, 0.8); border-radius: 12px; min-height: 38px; padding: 8px 10px; background: #ffffff; color: #005c55; font-weight: 800; cursor: pointer; text-align: left; font-size: 12px; }
            .cm-assistant-typing { display: inline-flex; gap: 4px; align-items: center; }
            .cm-assistant-typing span { width: 6px; height: 6px; border-radius: 50%; background: #8aa09c; animation: cmAssistantBlink 1.2s infinite both; }
            .cm-assistant-typing span:nth-child(2) { animation-delay: 0.16s; }
            .cm-assistant-typing span:nth-child(3) { animation-delay: 0.32s; }
            @keyframes cmAssistantBlink { 0%, 80%, 100% { opacity: 0.25; transform: translateY(0); } 40% { opacity: 1; transform: translateY(-2px); } }
            @media (max-width: 768px) {
                .cm-assistant-root { right: 14px; bottom: 84px; }
                .cm-assistant-panel { right: -2px; bottom: 76px; width: calc(100vw - 24px); height: min(620px, calc(100vh - 184px)); }
                .cm-assistant-launcher { width: 58px; height: 58px; border-radius: 16px; }
            }
        `;
        document.head.appendChild(style);
    }
};

document.addEventListener("DOMContentLoaded", () => {
    if (window.ChatWidget) {
        window.ChatWidget.init();
    }
});
