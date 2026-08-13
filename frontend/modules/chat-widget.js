// frontend/modules/chat-widget.js

window.ChatWidget = {
    root: null,
    controller: null,
    answerNode: null,
    typingNode: null,
    requestInFlight: false,
    progressTimers: [],
    activeTarget: "kendim",
    CHAT_RESPONSE_TIMEOUT_MS: 85000,
    STORAGE_OPEN: "cm_assistant_open",
    MAX_CACHED_MESSAGES: 12,

    authenticatedQuickPrompts: [
        { label: "Bugün ne yesem?", prompt: "Profilime ve sağlık bilgilerime göre bugün güvenli bir akşam yemeği önerir misin?" },
        { label: "İlaç uyumu", prompt: "Kullandığım ilaçlara göre hangi yiyeceklere dikkat etmeliyim? Kısa ve anlaşılır anlat." },
        { label: "Menüye bak", action: "tarayici", prompt: "Restoran menüsünü sağlık profilime göre kontrol etmek istiyorum." },
        { label: "Tahlil yorumla", action: "tahlil", prompt: "Tahlil sonuçlarımı yükleyip beslenme önerilerimde dikkate almak istiyorum." }
    ],
    publicQuickPrompts: [
        { label: "CureMenu nedir?", prompt: "CureMenu nedir?" },
        { label: "Nasıl çalışır?", prompt: "CureMenu nasıl çalışır?" },
        { label: "Veriler neden gerekli?", prompt: "Verilerimi neden istiyorsunuz?" },
        { label: "Kayıt olunca ne var?", prompt: "Kayıt olduktan sonra neler yapabilirim?" }
    ],

    isAuthenticatedMode() {
        const user = window.AuthManager ? window.AuthManager.getUser() : { telefon: "" };
        return Boolean(user.telefon) && window.location.pathname.startsWith("/dashboard");
    },

    getQuickPrompts() {
        return this.isAuthenticatedMode() ? this.authenticatedQuickPrompts : this.publicQuickPrompts;
    },

    getConversationCacheKey() {
        if (!this.isAuthenticatedMode()) return null;
        const target = this.activeTarget || "kendim";
        const context = window.ProfileManager?.getTargetCacheContext?.(target);
        if (!context) return null;
        return `cm_chat_v2_${context.accountKey}_${context.targetScope}_${context.targetId}_${context.profileFingerprint}`;
    },

    readCachedConversation() {
        const key = this.getConversationCacheKey();
        if (!key) return [];
        try {
            const parsed = JSON.parse(localStorage.getItem(key) || "[]");
            return Array.isArray(parsed) ? parsed.slice(-this.MAX_CACHED_MESSAGES) : [];
        } catch (_error) {
            return [];
        }
    },

    writeCachedConversation(messages) {
        const key = this.getConversationCacheKey();
        if (!key) return;
        const safeMessages = (Array.isArray(messages) ? messages : [])
            .filter(item => ["user", "bot", "soft"].includes(item?.type) && typeof item?.text === "string")
            .slice(-this.MAX_CACHED_MESSAGES)
            .map(item => ({ type: item.type, text: item.text.slice(0, 3000), at: item.at || Date.now() }));
        localStorage.setItem(key, JSON.stringify(safeMessages));
    },

    appendCachedMessage(type, text) {
        if (!this.isAuthenticatedMode()) return;
        const messages = this.readCachedConversation();
        messages.push({ type, text, at: Date.now() });
        this.writeCachedConversation(messages);
    },

    loadCachedConversation() {
        if (!this.root || !this.isAuthenticatedMode()) return false;
        const messages = this.readCachedConversation();
        if (!messages.length) {
            this.renderWelcome(true);
            return false;
        }
        const body = this.root.querySelector("[data-cm-assistant-body]");
        if (!body) return false;
        body.replaceChildren();
        messages.forEach(item => this.addMessage(item.text, item.type, false));
        return true;
    },

    isPersonalHealthRequest(message) {
        const text = String(message || "").toLocaleLowerCase("tr-TR");
        const personalSignals = [
            "profilime", "sağlık bilgilerime", "hastalığıma", "hastalığım",
            "tahlilime", "tahlilim", "ilacımla", "ilaçlarıma", "alerjime",
            "diyabetim", "hipertansiyonum", "çölyak", "böbrek hastalığım"
        ];
        const adviceSignals = [
            "ne yemeliyim", "yemek öner", "kahvaltı öner", "akşam yemeği öner",
            "menü ver", "güvenli", "tüketebilir miyim", "yiyebilir miyim",
            "beslenme öner", "yorum yap"
        ];
        return personalSignals.some(signal => text.includes(signal)) || adviceSignals.some(signal => text.includes(signal));
    },

    publicResponseFor(message) {
        const text = String(message || "").toLocaleLowerCase("tr-TR");
        if (this.isPersonalHealthRequest(message)) {
            return "Bunu kişisel sağlık profili olmadan güvenli şekilde değerlendiremem. CureMenu'de bu tür öneriler için giriş yaptıktan sonra hastalık, alerji, ilaç ve tercih bilgilerinizi kullanırız. İsterseniz size CureMenu'nün nasıl çalıştığını anlatabilirim.";
        }
        if (text.includes("veri") || text.includes("neden ist")) {
            return "CureMenu hastalık, alerji, ilaç, tercih ve tahlil bilgilerini kişiselleştirme ve güvenlik kontrolleri için kullanır. Amaç tanı koymak veya tedavi düzenlemek değil; yemek kararını daha anlaşılır hale getirmek ve riskli durumda uzman değerlendirmesine yönlendirmektir.";
        }
        if (text.includes("nedir") || text.includes("nasıl") || text.includes("kayıt")) {
            return "CureMenu, özel beslenme ihtiyacı olan kişiler için geliştirilen bir beslenme karar destek asistanıdır. Kayıt olduktan sonra profil, alerji, ilaç, hedef ve tahlil bilgileriyle haftalık plan, CureBot, menü analizi, buzdolabı analizi ve Smart Grocery akışlarını kullanabilirsiniz. Doktor veya diyetisyen yerine geçmez; belirsiz durumda uzman görüşüne yönlendirir.";
        }
        return "Ben burada CureMenu'yu tanıtmak ve hangi adımlarla çalıştığını anlatmak için varım. Kişisel beslenme veya sağlık önerileri için önce giriş yapıp profil bilgilerinizi oluşturmanız gerekir.";
    },

    init() {
        if (this.root) return;
        
        this.injectStyles();
        
        this.root = document.createElement("section");
        this.root.id = "cm-assistant-root";
        this.root.className = "cm-assistant-root";
        // Do not reopen the assistant over the dashboard after a new page load.
        // The active dashboard tab is persisted separately; the panel should open
        // only after an explicit user action or a feature shortcut.
        this.root.dataset.open = "false";
        this.root.dataset.mode = this.isAuthenticatedMode() ? "auth" : "public";
        const quickPrompts = this.getQuickPrompts();
        
        this.root.innerHTML = `
            <div class="cm-assistant-panel" role="dialog" aria-label="CureBot yardımcı">
                <header class="cm-assistant-header">
                    <div class="cm-assistant-title">
                        <div class="cm-assistant-avatar"><span class="material-symbols-outlined">smart_toy</span></div>
                        <div>
                            <strong>CureBot</strong>
                            <span id="cm-assistant-status">Her &#246;&#287;&#252;nde, her sorunda yan&#305;nda.</span>
                        </div>
                    </div>
                    <button class="cm-assistant-close" type="button" aria-label="CureBot'u kapat" data-cm-assistant-close>
                        <span class="material-symbols-outlined">close</span>
                    </button>
                </header>
                <div class="cm-assistant-body" data-cm-assistant-body></div>
                <div>
                    <div class="cm-assistant-quick" data-cm-assistant-quick>
                        ${quickPrompts.map((item, i) => `<button type="button" data-cm-quick="${i}">${window.escapeHtml ? escapeHtml(item.label) : item.label}</button>`).join("")}
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
        const status = this.root.querySelector('#cm-assistant-status');
        if (status) status.textContent = 'Her öğünde, her sorunda yanında.';
        const titleBlock = this.root.querySelector('.cm-assistant-title > div:last-child');
        if (titleBlock) {
            const subtitle = document.createElement('small');
            subtitle.className = 'cm-assistant-subtitle';
            subtitle.textContent = 'Profilini, aileni ve günlük yemek kararlarını birlikte değerlendirir.';
            titleBlock.appendChild(subtitle);
            const chip = document.createElement('span');
            chip.className = 'cm-assistant-context-chip';
            chip.dataset.cmHeaderContext = 'true';
            chip.textContent = (window.AuthManager && window.AuthManager.getUser().kullanici_adi) ? window.AuthManager.getUser().kullanici_adi + ' için' : 'Benim için';
            titleBlock.appendChild(chip);
        }
        this.renderWelcome();
        this.loadCachedConversation();
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
                const item = this.getQuickPrompts()[Number(quick.dataset.cmQuick)];
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
            const publicNav = e.target.closest("[data-cm-public-nav]");
            if (publicNav) {
                window.location.href = publicNav.dataset.cmPublicNav || "/kayit";
            }
        });

    },

    resolveTargetFromMessage(message) {
        const normalizeTargetText = value => String(value || '')
            .toLocaleLowerCase('tr-TR')
            .replace(/ı/g, 'i')
            .normalize('NFKD')
            .replace(/[\u0300-\u036f]/g, '');
        const normalizedMessage = normalizeTargetText(message);
        const familyMembers = Array.isArray(window.currentProfile?.aile_uyeleri)
            ? window.currentProfile.aile_uyeleri
            : [];
        if (/tum aile|hepimiz|bize|biz ne yiyelim/.test(normalizedMessage)) {
            return { target: 'aile', label: 'Tüm aile için' };
        }

        const namedMember = familyMembers.find(item => {
            const name = normalizeTargetText(item?.ad).trim();
            return name.length > 1 && normalizedMessage.includes(name);
        });
        if (namedMember?.id) {
            return { target: String(namedMember.id), label: `${namedMember.ad} için` };
        }

        const relationRules = [
            { terms: ['annem', 'anneme'], relations: ['anne', 'mother'] },
            { terms: ['babam', 'babama'], relations: ['baba', 'father'] },
            { terms: ['oğlum', 'oğluma', 'oglum', 'ogluma'], relations: ['oğul', 'ogul', 'son', 'çocuk', 'cocuk'] },
            { terms: ['kızım', 'kızıma', 'kizim', 'kizima'], relations: ['kız', 'kiz', 'daughter', 'çocuk', 'cocuk'] },
            { terms: ['eşim', 'eşime', 'esim', 'esime'], relations: ['eş', 'es', 'spouse'] },
            { terms: ['kardeşim', 'kardeşime', 'kardesim', 'kardesime'], relations: ['kardeş', 'kardes', 'sibling'] },
        ];
        const relationRule = relationRules.find(rule => rule.terms.some(term => normalizedMessage.includes(term)));
        if (relationRule) {
            const relatedMember = familyMembers.find(item => relationRule.relations.some(
                relation => normalizeTargetText(item?.yakinlik).includes(normalizeTargetText(relation))
            ));
            const resolvedMember = relatedMember || (familyMembers.length === 1 ? familyMembers[0] : null);
            if (resolvedMember?.id) {
                return { target: String(resolvedMember.id), label: `${resolvedMember.ad} için` };
            }
        }

        const userName = window.AuthManager?.getUser()?.kullanici_adi;
        return { target: 'kendim', label: userName ? `${userName} için` : 'Benim için' };
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
        if (statusEl) statusEl.textContent = text || "Her \u00f6\u011f\u00fcnde, her sorunda yan\u0131nda.";
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
            if (window.DOMPurify) {
                item.innerHTML = DOMPurify.sanitize(text);
            } else if (window.escapeHtml) {
                item.innerHTML = escapeHtml(text).replace(/\n/g, "<br>");
            } else {
                item.textContent = text;
            }
        } else if (type === "bot" && window.formatMarkdownSafe) {
            item.innerHTML = formatMarkdownSafe(text);
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

    setBusy(isBusy) {
        if (!this.root) return;
        const sendBtn = this.root.querySelector("[data-cm-assistant-send]");
        const input = this.root.querySelector("[data-cm-assistant-input]");
        if (sendBtn) {
            sendBtn.disabled = isBusy;
            sendBtn.setAttribute("aria-busy", isBusy ? "true" : "false");
        }
        if (input) input.disabled = isBusy;
    },

    clearProgressTimers() {
        this.progressTimers.forEach(timerId => clearTimeout(timerId));
        this.progressTimers = [];
    },

    scheduleProgressUpdates() {
        this.clearProgressTimers();
        this.progressTimers = [
            setTimeout(() => {
                if (this.requestInFlight) this.setStatus("Öneri sağlık kısıtlarıyla karşılaştırılıyor...");
            }, 7000),
            setTimeout(() => {
                if (this.requestInFlight) this.setStatus("Yanıt hazırlanıyor...");
            }, 22000)
        ];
    },

    showGovernance(data) {
        // Technical decision records remain on the dedicated traceability screen.
        return;
    },

    resetState() {
        this.hideTyping();
        this.clearProgressTimers();
        this.setStatus("Her \u00f6\u011f\u00fcnde, her sorunda yan\u0131nda.");
        this.answerNode = null;
        this.requestInFlight = false;
        if (this.controller) {
            this.controller.abort();
            this.controller = null;
        }
        this.setBusy(false);
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
        const resolved = this.isAuthenticatedMode() ? this.resolveTargetFromMessage(message) : null;
        if (resolved) {
            this.activeTarget = resolved.target;
            const headerChip = this.root.querySelector('[data-cm-header-context]');
            if (headerChip) headerChip.textContent = resolved.label;
        }
        
        const sendBtn = this.root.querySelector("[data-cm-assistant-send]");
        if (this.requestInFlight || sendBtn.disabled) return;
        
        this.root.querySelector("[data-cm-assistant-quick]")?.classList.add("is-hidden");
        this.addMessage(message, "user");
        if (this.isAuthenticatedMode()) this.appendCachedMessage("user", message);

        if (!this.isAuthenticatedMode()) {
            this.setStatus("CureMenu hakkında yardım");
            this.addMessage(this.publicResponseFor(message), "bot");
            return;
        }
        
        this.requestInFlight = true;
        this.setBusy(true);
        this.setStatus("Profil bilgilerin kontrol ediliyor...");
        this.scheduleProgressUpdates();
        this.showTyping();
        this.answerNode = null;
        
        this.controller = new AbortController();
        let fullAnswer = "";
        let doneSeen = false;
        
        const timeoutId = setTimeout(() => {
            if (!doneSeen) {
                this.controller?.abort();
                this.showError("Yanıt hazırlanması beklenenden uzun sürdü. Bağlantı veya model yanıtı gecikmiş olabilir; birazdan tekrar deneyebilirsiniz.");
            }
        }, this.CHAT_RESPONSE_TIMEOUT_MS);

        try {
            const apiEndpoint = (window.API || '') + '/api/chat';
            const resolvedTarget = resolved?.target || 'kendim';
            
            if (!window.safeFetchStream) throw new Error("API client yüklü değil.");
            
            const response = await window.safeFetchStream(apiEndpoint, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ mesaj: message, kimin_icin: resolvedTarget }),
                signal: this.controller.signal
            });

            if (!response.ok || !response.body) {
                throw new Error(response.status === 401 ? "Oturumunu yenilememiz gerekiyor." : "Şu an yanıtı hazırlayamadım.");
            }

            window.CureMenuAnalytics?.track?.('curebot_message_sent', { feature: 'curebot' });
            const reader = response.body.getReader();
            const decoder = new TextDecoder();
            let buffer = "";

            while (true) {
                const { value, done } = await reader.read();
                
                if (value) {
                    buffer += decoder.decode(value, { stream: true });
                }

                const parts = buffer.split("\n\n");
                buffer = parts.pop() || "";

                for (const part of parts) {
                    const lines = part.split("\n");
                    const eventLine = lines.find(l => l.startsWith("event:"));
                    const dataLines = lines.filter(l => l.startsWith("data:"));
                    if (!eventLine) continue;

                    const eventName = eventLine.replace("event:", "").trim();
                    let payload = {};
                    try {
                        payload = JSON.parse(dataLines.map(l => l.replace("data:", "").trim()).join("\n") || "{}");
                    } catch (_) {}

                    if (eventName === "status") {
                        this.setStatus(payload.status || payload.message || "Yanıt hazırlanıyor...");
                    } else if (eventName === "heartbeat") {
                        this.setStatus("Öneri sağlık kısıtlarıyla karşılaştırılıyor...");
                    } else if (eventName === "message" || eventName === "token") {
                        this.setStatus("CureBot yazıyor...");
                        fullAnswer += (payload.chunk || "");
                        this.appendToken(fullAnswer);
                    } else if (eventName === "error") {
                        this.showError(payload.message || "Yanıtı tamamlayamadım.");
                        doneSeen = true;
                    } else if (eventName === "governance") {
                        this.showGovernance(payload);
                    } else if (eventName === "done") {
                        doneSeen = true;
                    }
                }

                if (done) {
                    break;
                }
            }

            if (buffer.trim()) {
                const lines = buffer.split("\n");
                const eventLine = lines.find(l => l.startsWith("event:"));
                const dataLines = lines.filter(l => l.startsWith("data:"));
                if (eventLine) {
                    const eventName = eventLine.replace("event:", "").trim();
                    if (eventName === "message" || eventName === "token") {
                        try {
                            const payload = JSON.parse(dataLines.map(l => l.replace("data:", "").trim()).join("\n") || "{}");
                            fullAnswer += (payload.chunk || "");
                            this.appendToken(fullAnswer);
                        } catch (_) {}
                    } else if (eventName === "done") {
                        doneSeen = true;
                    }
                }
            }

            if (!doneSeen && !fullAnswer) {
                throw new Error("Yanıt tamamlanamadı.");
            }
            if (fullAnswer) {
                this.appendCachedMessage("bot", fullAnswer);
                window.CureMenuAnalytics?.track?.('curebot_response_received', { feature: 'curebot', metadata: { result: 'success' } });
            }
        } catch (error) {
            if (error.name === "AbortError" || this.controller === null) {
                // Ignore if manually aborted
            } else {
                const safeError = "Yanıt oluşturulamadı. Lütfen tekrar deneyin.";
                this.showError(safeError);
                this.appendCachedMessage("soft", safeError);
            }
        } finally {
            clearTimeout(timeoutId);
            this.resetState();
        }
    },

    renderWelcome(force = false) {
        const body = this.root?.querySelector("[data-cm-assistant-body]");
        if (force && body) body.replaceChildren();
        const user = window.AuthManager ? window.AuthManager.getUser() : {kullanici_adi: ''};
        if (!this.isAuthenticatedMode()) {
            this.setStatus("CureMenu'yu tanıtır");
            this.addMessage("Merhaba, ben CureBot. Giriş yapmadan önce sana CureMenu'nün ne olduğunu, nasıl çalıştığını ve kayıt olduktan sonra hangi özellikleri kullanabileceğini anlatabilirim.");
            const publicHtml = `
                <div>Kişisel beslenme önerileri için önce profil oluşturman gerekir.</div>
                <div class="cm-assistant-actions">
                    <button type="button" data-cm-public-nav="/kayit">Kayıt ol</button>
                    <button type="button" data-cm-public-nav="/giris">Giriş yap</button>
                </div>
            `;
            this.addMessage(publicHtml, "soft", true);
            return;
        }
        const name = user.kullanici_adi || "Merhaba";
        this.addMessage(`${name}, ben CureBot. İstersen hızlıca güvenli öğün seçmene, menü kontrol etmene, tahlil ya da profil adımlarına geçmene yardım ederim.`);
        const html = `
            <div>Buradan hızlıca başlayabilirsin:</div>
            <div class="cm-assistant-actions">
                <button type="button" data-cm-feature="plan">Haftalık plan</button>
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
            .cm-assistant-panel { width: min(390px, calc(100vw - 28px)); height: min(620px, calc(100vh - 110px)); position: absolute; right: 0; bottom: 78px; border-radius: 18px; background: #ffffff; border: 1px solid rgba(189, 201, 198, 0.72); box-shadow: 0 24px 70px rgba(16, 32, 51, 0.2); overflow: hidden; display: none; grid-template-rows: auto auto 1fr auto; }
            .cm-assistant-root[data-open="true"] .cm-assistant-panel { display: grid; animation: cmAssistantEnter 180ms ease both; }
            @keyframes cmAssistantEnter { from { opacity: 0; transform: translateY(10px) scale(0.98); } to { opacity: 1; transform: translateY(0) scale(1); } }
            .cm-assistant-header { padding: 16px; background: linear-gradient(135deg, #005c55 0%, #0b1c30 100%); color: #fff; display: flex; align-items: center; justify-content: space-between; gap: 12px; }
            .cm-assistant-title { display: flex; align-items: center; gap: 10px; min-width: 0; }
            .cm-assistant-avatar { width: 38px; height: 38px; border-radius: 12px; background: rgba(255,255,255,0.14); display: grid; place-items: center; flex: 0 0 auto; }
            .cm-assistant-title strong { display: block; font-size: 15px; line-height: 1.15; }
            .cm-assistant-title span { display: block; margin-top: 2px; font-size: 12px; color: rgba(255,255,255,0.75); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
            .cm-assistant-close { border: 0; width: 34px; height: 34px; border-radius: 10px; background: rgba(255,255,255,0.1); color: #fff; display: grid; place-items: center; cursor: pointer; }
            .cm-assistant-context { padding: 10px 14px; background: #ffffff; border-bottom: 1px solid rgba(189, 201, 198, 0.55); display: flex; align-items: center; gap: 10px; }
            .cm-assistant-root[data-mode="public"] .cm-assistant-context { display: none; }
            .cm-assistant-context label { color: #526762; font-size: 12px; font-weight: 700; white-space: nowrap; }
            .cm-assistant-context select { min-width: 0; flex: 1; height: 36px; border: 1px solid rgba(189, 201, 198, 0.9); border-radius: 10px; padding: 0 10px; background: #ffffff; color: #102033; font-size: 13px; outline: none; }
            .cm-assistant-context select:focus { border-color: #005c55; box-shadow: 0 0 0 3px rgba(0, 92, 85, 0.1); }
            .cm-assistant-subtitle { display: block; margin-top: 3px; font-size: 10px; line-height: 1.25; color: rgba(255,255,255,0.72); max-width: 230px; }
            .cm-assistant-context-chip { display: inline-flex; align-items: center; width: fit-content; border: 1px solid rgba(255,255,255,0.24); border-radius: 999px; padding: 3px 8px; color: rgba(255,255,255,0.9); background: rgba(255,255,255,0.1); font-size: 10px; font-weight: 700; }
            .cm-assistant-body { overflow-y: auto; padding: 14px; background: #f7fbfc; display: flex; flex-direction: column; gap: 10px; }
            .cm-assistant-message { max-width: 86%; border-radius: 14px; padding: 11px 12px; font-size: 13px; line-height: 1.55; border: 1px solid transparent; word-wrap: break-word; }
            .cm-assistant-message.bot { align-self: flex-start; max-width: 94%; padding: 14px 15px; background: #ffffff; border-color: rgba(189, 201, 198, 0.7); color: #243b38; line-height: 1.62; box-shadow: 0 7px 20px rgba(16, 32, 51, 0.045); }
            .cm-assistant-message.bot h1,
            .cm-assistant-message.bot h2,
            .cm-assistant-message.bot h3,
            .cm-assistant-message.bot h4 { margin: 14px 0 7px; color: #0b4f49; font-family: Outfit, Inter, sans-serif; font-weight: 700; line-height: 1.28; letter-spacing: -0.015em; }
            .cm-assistant-message.bot h1:first-child,
            .cm-assistant-message.bot h2:first-child,
            .cm-assistant-message.bot h3:first-child,
            .cm-assistant-message.bot h4:first-child { margin-top: 0; }
            .cm-assistant-message.bot h1,
            .cm-assistant-message.bot h2 { padding-bottom: 7px; border-bottom: 1px solid rgba(0, 92, 85, 0.12); font-size: 16px; }
            .cm-assistant-message.bot h3 { font-size: 14.5px; }
            .cm-assistant-message.bot h4 { font-size: 13.5px; }
            .cm-assistant-message.bot p { margin: 0 0 10px; }
            .cm-assistant-message.bot p:last-child { margin-bottom: 0; }
            .cm-assistant-message.bot ul { display: grid; gap: 7px; margin: 9px 0 11px; padding: 0; list-style: none; }
            .cm-assistant-message.bot ul li { position: relative; margin: 0; padding: 9px 10px 9px 27px; border: 1px solid rgba(0, 92, 85, 0.1); border-radius: 10px; background: #f6faf9; }
            .cm-assistant-message.bot ul li::before { content: ""; position: absolute; top: 15px; left: 11px; width: 6px; height: 6px; border-radius: 50%; background: #0b8a7f; box-shadow: 0 0 0 3px rgba(11, 138, 127, 0.1); }
            .cm-assistant-message.bot ul li strong { display: block; margin-bottom: 3px; color: #064f49; font-family: Outfit, Inter, sans-serif; font-size: 13.5px; font-weight: 750; line-height: 1.3; letter-spacing: -0.01em; }
            .cm-assistant-message.bot ol { margin: 9px 0 11px; padding-left: 24px; }
            .cm-assistant-message.bot ol li { margin: 6px 0; padding-left: 3px; }
            .cm-assistant-message.bot strong { color: #005c55; font-weight: 700; }
            .cm-assistant-message.bot blockquote { margin: 11px 0 0; padding: 9px 11px; border-left: 3px solid #d5a334; border-radius: 0 9px 9px 0; background: #fffbef; color: #5f5131; }
            .cm-assistant-message.bot blockquote p { margin: 0; }
            .cm-assistant-message.bot a { color: #006e65; font-weight: 600; text-decoration-thickness: 1px; text-underline-offset: 2px; }
            .cm-assistant-message.bot code { border-radius: 5px; padding: 1px 4px; background: #edf4f2; color: #164b46; font-family: ui-monospace, SFMono-Regular, Consolas, monospace; font-size: 0.92em; }
            .cm-assistant-message.bot hr { margin: 12px 0; border: 0; border-top: 1px solid rgba(0, 92, 85, 0.12); }
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
                .cm-assistant-message.bot { max-width: 96%; padding: 13px; }
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
