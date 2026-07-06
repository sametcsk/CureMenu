/**
 * CureMenu - Frontend JavaScript
 * API bağlantıları ve sayfa mantığı.
 */

const API = '';  // Aynı sunucu

function apiHataMesaji(data, varsayilan = 'Bir hata oluştu. Lütfen tekrar deneyin.') {
    if (!data) return varsayilan;
    const detail = data.detail;
    if (typeof detail === 'string') return detail;
    if (Array.isArray(detail) && detail.length > 0) {
        return detail[0].msg || varsayilan;
    }
    return varsayilan;
}

function baglantiHatasi(e) {
    return 'Bağlantı kurulamadı. Lütfen birazdan tekrar deneyin.';
}

let isRefreshing = false;
let refreshSubscribers = [];

function onRefreshed(token) {
    refreshSubscribers.map(cb => cb(token));
    refreshSubscribers = [];
}

async function safeFetchJson(url, options = {}) {
    options.credentials = 'include'; // Ensure HttpOnly cookies are sent
    let res = await fetch(url, options);
    
    // Auto Refresh Logic
    if (res.status === 401 && url.indexOf('/api/refresh') === -1 && url.indexOf('/api/login') === -1) {
        if (!isRefreshing) {
            isRefreshing = true;
            try {
                const refreshRes = await fetch(API + '/api/refresh', { method: 'POST', credentials: 'include' });
                if (refreshRes.ok) {
                    onRefreshed(true);
                } else {
                    onRefreshed(false);
                    logout(); // If refresh fails, log them out
                }
            } catch (e) {
                onRefreshed(false);
                logout();
            } finally {
                isRefreshing = false;
            }
        }
        
        // Wait for the refresh to finish
        const refreshed = await new Promise(resolve => {
            refreshSubscribers.push(resolve);
        });
        
        if (refreshed) {
            // Retry original request
            res = await fetch(url, options);
        } else {
            return { res, data: null };
        }
    }
    
    let data = null;
    try {
        data = await res.json();
    } catch (_) {
        data = null;
    }
    return { res, data };
}

async function safeFetchStream(url, options = {}) {
    options.credentials = 'include';
    let res = await fetch(url, options);
    
    if (res.status === 401 && url.indexOf('/api/refresh') === -1 && url.indexOf('/api/login') === -1) {
        if (!isRefreshing) {
            isRefreshing = true;
            try {
                const refreshRes = await fetch(API + '/api/refresh', { method: 'POST', credentials: 'include' });
                if (refreshRes.ok) {
                    onRefreshed(true);
                } else {
                    onRefreshed(false);
                    logout();
                }
            } catch (e) {
                onRefreshed(false);
                logout();
            } finally {
                isRefreshing = false;
            }
        }
        
        const refreshed = await new Promise(resolve => {
            refreshSubscribers.push(resolve);
        });
        
        if (refreshed) {
            res = await fetch(url, options);
        } else {
            return res;
        }
    }
    return res;
}

function formatMarkdownSafe(text) {
    if (text == null) return '';
    const safeText = String(text);
    try {
        if (window.marked && window.DOMPurify) {
            return DOMPurify.sanitize(marked.parse(safeText));
        }
    } catch (_) {
        /* markdown parse hatasında düz metne düş */
    }
    return escapeHtml(safeText).replace(/\n/g, '<br>');
}

const AGENT_LOADING_STEPS = [
    'Yönlendirici niyetinizi analiz ediyor...',
    'Beslenme uzmanı öneri hazırlıyor...',
    'Tıbbi denetmen profilinizi kontrol ediyor...',
    'Şef tarif detaylarını topluyor...',
];

function startAgentLoading(loadingId) {
    let step = 0;
    const root = document.getElementById(loadingId);
    const statusEl = root ? root.querySelector('[data-agent-status]') : null;
    if (!statusEl) return () => {};

    const interval = setInterval(() => {
        step = (step + 1) % AGENT_LOADING_STEPS.length;
        statusEl.textContent = AGENT_LOADING_STEPS[step];
    }, 2500);

    return () => clearInterval(interval);
}

const HASTALIK_SECENEKLERI = ['diyabet', 'hipertansiyon', 'çölyak', 'kolesterol', 'böbrek', 'gut'];
const ILAC_SECENEKLERI_FALLBACK = ['metformin', 'insülin', 'warfarin', 'atorvastatin', 'levotiroksin', 'lisinopril', 'omeprazol', 'aspirin'];

function parseListInput(value) {
    return value.split(',').map(s => s.trim()).filter(Boolean);
}

function appendChipValue(inputId, value) {
    const input = document.getElementById(inputId);
    if (!input) return;
    const mevcut = parseListInput(input.value);
    if (!mevcut.includes(value)) {
        mevcut.push(value);
        input.value = mevcut.join(', ');
    }
}

function renderIlacChips(containerId, inputId, ilaclar) {
    const chips = document.getElementById(containerId);
    if (!chips) return;
    chips.innerHTML = '';
    ilaclar.forEach(ilac => {
        const btn = document.createElement('button');
        btn.type = 'button';
        btn.className = 'px-3 py-1 rounded-full border border-outline-variant text-sm hover:bg-secondary-container/30 hover:border-secondary transition-colors ob-chip';
        btn.textContent = ilac;
        btn.onclick = () => {
            appendChipValue(inputId, ilac);
            btn.classList.add('bg-secondary-container/40', 'border-secondary');
        };
        chips.appendChild(btn);
    });
}

function renderGuvenlikBadge(guvenlik, feragatKisa) {
    if (!guvenlik) return '';
    let badge = '';
    if (guvenlik.onayli === true) {
        badge = `<div class="flex items-center gap-1.5 mt-2 px-2 py-1 bg-primary-container/20 text-primary rounded-lg text-[11px] font-medium">
            <span class="material-symbols-outlined text-[14px]" style="font-variation-settings:'FILL' 1">verified</span>Guardrail onaylı</div>`;
    } else if (guvenlik.onayli === false && guvenlik.tip === 'yemek_reddedildi') {
        badge = `<div class="flex items-center gap-1.5 mt-2 px-2 py-1 bg-error-container text-on-error-container rounded-lg text-[11px] font-medium">
            <span class="material-symbols-outlined text-[14px]">block</span>Güvenlik uyarısı</div>`;
    }
    const aciklama = guvenlik.aciklama
        ? `<p class="mt-2 text-[11px] text-outline leading-snug border-t border-outline-variant/20 pt-2">${escapeHtml(guvenlik.aciklama)}</p>`
        : '';
    const feragat = feragatKisa
        ? `<p class="mt-1 text-[10px] text-outline/80 italic">${escapeHtml(feragatKisa)}</p>`
        : '';
    return badge + aciklama + feragat;
}

let publicMetinler = null;

async function loadPublicMetinler() {
    if (publicMetinler) return publicMetinler;
    try {
        const res = await fetch(API + '/api/public/metinler');
        publicMetinler = await res.json();
    } catch (e) {
        publicMetinler = {
            tibbi_feragat_kisa: 'Tedavi yerine geçmez · Doktorunuza danışın',
            ornek_sorular: ['Bugün ne yesem?', 'Diyabetime uygun akşam yemeği öner'],
            yaygin_ilaclar: ILAC_SECENEKLERI_FALLBACK,
        };
    }
    const disc = document.getElementById('chatDisclaimer');
    if (disc && publicMetinler.tibbi_feragat_kisa) disc.textContent = publicMetinler.tibbi_feragat_kisa;
    return publicMetinler;
}

function getUser() {
    return {
        telefon: localStorage.getItem('cm_telefon') || '',
        kullanici_adi: localStorage.getItem('cm_kullanici_adi') || ''
    };
}

function initApp() {
    const user = getUser();
    if (!user.telefon) { window.location.href = '/giris'; return; }
    if (localStorage.getItem('cm_disclaimer_ok') !== 'true') { window.location.href = '/giris'; return; }
    document.getElementById('sidebarUser').textContent = user.kullanici_adi;
    document.getElementById('sidebarPhone').textContent = user.telefon;
    loadPublicMetinler();
    loadProfile().then(() => {
        checkOnboarding();
        loadDashboardOverview(true);
        loadLabHistory();
        
        const savedPlan = localStorage.getItem('cm_saved_plan_' + user.telefon);
        if (savedPlan) {
            renderSavedPlan(savedPlan);
        }
    });
}

async function logout() {
    try {
        await fetch(API + '/api/logout', { method: 'POST', credentials: 'include' });
    } catch(e) {}
    ['cm_telefon', 'cm_kullanici_adi', 'cm_has_profile', 'cm_onboarding_done', 'cm_disclaimer_ok'].forEach(k => localStorage.removeItem(k));
    window.location.href = '/';
}

// switchTab is defined once in the dashboard section below.

// -- Profil Yükleme --
function openCureBotWidget(message) {
    if (typeof window.openCureMenuAssistant === 'function') {
        window.openCureMenuAssistant(message);
        return;
    }
    window.dispatchEvent(new CustomEvent('cm-open-assistant', { detail: { message } }));
}
window.openCureBotWidget = openCureBotWidget;

async function loadProfile() {
    const user = getUser();
    try {
        const { res, data } = await safeFetchJson(API + '/api/profile/me');
        if (!res.ok || !data) { renderEmptyFamily(); return null; }
        window.currentProfile = data.profil;
        renderFamily(data.profil);
        updatePlanDropdown(data.profil);
        renderHealthProfile(data.profil);
        renderMedicationOverview(data.profil);

        const hasMain = !!data.profil.ana_kullanici;
        localStorage.setItem('cm_has_profile', hasMain ? 'true' : 'false');
        return data.profil;
    } catch (e) { console.error(e); renderEmptyFamily(); return null; }
}

async function checkOnboarding() {
    if (localStorage.getItem('cm_onboarding_done') === 'true') return;
    if (localStorage.getItem('cm_has_profile') === 'true') {
        localStorage.setItem('cm_onboarding_done', 'true');
        return;
    }
    await showOnboarding();
}

async function showOnboarding() {
    const metinler = await loadPublicMetinler();
    const modal = document.getElementById('onboardingModal');
    const user = getUser();
    const title = modal?.querySelector('h3');
    if (title) title.textContent = "CureMenu'ye hoş geldin";
    const subtitle = modal?.querySelector('h3 + p');
    if (subtitle) subtitle.textContent = 'Birkaç bilgiyle önerileri daha dikkatli hale getirebiliriz.';
    const submit = modal?.querySelector('[onclick="completeOnboarding()"]');
    if (submit) submit.textContent = 'Profilimi oluştur ve başla';
    document.getElementById('ob_ad').value = user.kullanici_adi || '';
    document.getElementById('ob_feragat').textContent = metinler.tibbi_feragat || metinler.tibbi_feragat_kisa;

    const chips = document.getElementById('ob_hastalik_chips');
    chips.innerHTML = '';
    HASTALIK_SECENEKLERI.forEach(h => {
        const btn = document.createElement('button');
        btn.type = 'button';
        btn.className = 'px-3 py-1 rounded-full border border-outline-variant text-sm hover:bg-primary-container/20 hover:border-primary transition-colors ob-chip';
        btn.textContent = h;
        btn.onclick = () => {
            const input = document.getElementById('ob_hastaliklar');
            const mevcut = input.value.split(',').map(s => s.trim()).filter(Boolean);
            if (!mevcut.includes(h)) {
                mevcut.push(h);
                input.value = mevcut.join(', ');
            }
            btn.classList.add('bg-primary-container/30', 'border-primary');
        };
        chips.appendChild(btn);
    });

    const sorular = document.getElementById('ob_ornek_sorular');
    sorular.innerHTML = '';
    (metinler.ornek_sorular || []).forEach(s => {
        const span = document.createElement('span');
        span.className = 'px-3 py-1 bg-surface-container-low rounded-full text-xs text-on-surface-variant border border-outline-variant/30';
        span.textContent = '"' + s + '"';
        sorular.appendChild(span);
    });

    renderIlacChips('ob_ilac_chips', 'ob_ilaclar', metinler.yaygin_ilaclar || ILAC_SECENEKLERI_FALLBACK);

    modal.classList.remove('hidden');
}



function openProfileEditor() {
    const profil = window.currentProfile?.ana_kullanici;
    if (!profil) {
        showOnboarding();
        return;
    }
    const modal = document.getElementById('onboardingModal');
    if (!modal) return;
    const setValue = (id, value) => {
        const el = document.getElementById(id);
        if (el) el.value = value ?? '';
    };
    setValue('ob_ad', profil.ad || getUser().kullanici_adi || '');
    setValue('ob_yas', profil.yas || 35);
    setValue('ob_cinsiyet', profil.cinsiyet || 'kadın');
    setValue('ob_hedef', profil.hedef || 'Sağlıklı Yaşam (Genel)');
    setValue('ob_hastaliklar', (profil.hastaliklar || []).join(', '));
    setValue('ob_alerjiler', (profil.alerjiler || []).join(', '));
    setValue('ob_ilaclar', (profil.ilaclar || []).join(', '));
    const title = modal.querySelector('h3');
    if (title) title.textContent = 'Sağlık bilgilerini güncelle';
    const subtitle = modal.querySelector('h3 + p');
    if (subtitle) subtitle.textContent = 'Yeni hastalık, alerji veya ilaç bilgisi eklediğinde öneriler daha dikkatli değerlendirilir.';
    const submit = modal.querySelector('[onclick="completeOnboarding()"]');
    if (submit) submit.textContent = 'Bilgilerimi kaydet';
    modal.classList.remove('hidden');
}
window.openProfileEditor = openProfileEditor;

async function completeOnboarding() {
    const user = getUser();
    const ad = document.getElementById('ob_ad').value.trim();
    const nameRegex = /^[A-Za-z\u00C7\u00E7\u011E\u011F\u0130\u0131\u00D6\u00F6\u015E\u015F\u00DC\u00FC\s]+$/;
    if (!ad || !nameRegex.test(ad) || ad.length > 40) { 
        alert('Lütfen geçerli bir ad girin (sadece harfler, maks 40 karakter).'); 
        return; 
    }

    const body = {
        kullanici_adi: user.kullanici_adi,
        ad,
        yas: parseInt(document.getElementById('ob_yas').value) || 30,
        cinsiyet: document.getElementById('ob_cinsiyet').value,
        hastaliklar: parseListInput(document.getElementById('ob_hastaliklar').value),
        alerjiler: parseListInput(document.getElementById('ob_alerjiler').value),
        ilaclar: parseListInput(document.getElementById('ob_ilaclar').value),
        hedef: document.getElementById('ob_hedef').value,
    };

    try {
        const res = await fetch(API + '/api/profile/save', {
            method: 'POST', headers: { 'Content-Type': 'application/json' }, credentials: 'include', body: JSON.stringify(body)
        });
        const data = await res.json();
        if (res.ok && data.success) {
            localStorage.setItem('cm_has_profile', 'true');
            localStorage.setItem('cm_onboarding_done', 'true');
            document.getElementById('onboardingModal').classList.add('hidden');
            await loadProfile();
            openCureBotWidget();
            const metinler = await loadPublicMetinler();
            const ornek = (metinler.ornek_sorular || [])[0];
            if (ornek) {
                openCureBotWidget(ornek);
            }
        } else {
            alert(apiHataMesaji(data, 'Profil kaydedilemedi.'));
        }
    } catch (e) {
        alert(baglantiHatasi(e));
    }
}

// renderEmptyFamily and renderFamily are defined once in the dashboard section below.

function updatePlanDropdown(profil) {
    const sel = document.getElementById('planTarget');
    sel.innerHTML = '<option value="kendim">Kendim İçin</option>';
    (profil.aile_uyeleri || []).forEach(u => {
        const ad = escapeHtml(u.ad);
        sel.innerHTML += `<option value="${ad}">${ad} İçin</option>`;
    });
    if ((profil.aile_uyeleri || []).length > 0) {
        sel.innerHTML += '<option value="aile">Tüm Aile İçin</option>';
    }
    // CureBot dropdown
    const chatSel = document.getElementById('chatTarget');
    if (chatSel) {
    chatSel.innerHTML = '<option value="kendim">Kendim İçin</option>';
    (profil.aile_uyeleri || []).forEach(u => {
        chatSel.innerHTML += `<option value="${escapeHtml(u.ad)}">🧑 ${escapeHtml(u.ad)} İçin</option>`;
    });
    if ((profil.aile_uyeleri || []).length > 0) {
        chatSel.innerHTML += '<option value="aile">👪 Tüm Aile İçin</option>';
    }
    
    // Menü Tarayıcı dropdown
    }
    const menuSel = document.getElementById('menuTarget');
    if (menuSel) {
        menuSel.innerHTML = '<option value="kendim">Kendim İçin</option>';
        (profil.aile_uyeleri || []).forEach(u => {
            menuSel.innerHTML += `<option value="${escapeHtml(u.ad)}">${escapeHtml(u.ad)} İçin</option>`;
        });
        if ((profil.aile_uyeleri || []).length > 0) {
            menuSel.innerHTML += '<option value="aile">Tüm Aile İçin</option>';
        }
    }
    
    // Buzdolabı dropdown
    const fridgeSel = document.getElementById('fridgeTarget');
    if (fridgeSel) {
        fridgeSel.innerHTML = '<option value="kendim">Kendim İçin</option>';
        (profil.aile_uyeleri || []).forEach(u => {
            fridgeSel.innerHTML += `<option value="${escapeHtml(u.ad)}">${escapeHtml(u.ad)} İçin</option>`;
        });
        if ((profil.aile_uyeleri || []).length > 0) {
            fridgeSel.innerHTML += '<option value="aile">Tüm Aile İçin</option>';
        }
    }
    
    // Tahlillerim dropdown
    const tahlilSel = document.getElementById('tahlilTarget');
    if (tahlilSel) {
        tahlilSel.innerHTML = '<option value="kendim">Kendim İçin</option>';
        (profil.aile_uyeleri || []).forEach(u => {
            tahlilSel.innerHTML += `<option value="${escapeHtml(u.ad)}">${escapeHtml(u.ad)} İçin</option>`;
        });
        if ((profil.aile_uyeleri || []).length > 0) {
            tahlilSel.innerHTML += '<option value="aile">Tüm Aile İçin</option>';
        }
    }
}

// -- Üye Ekleme --
async function addMember() {
    const user = getUser();
    const hasProfile = localStorage.getItem('cm_has_profile');
    const endpoint = hasProfile === 'true' ? '/api/family/add' : '/api/profile/save';

    const ad_val = document.getElementById('m_ad').value.trim();
    const nameRegex = /^[A-Za-z\u00C7\u00E7\u011E\u011F\u0130\u0131\u00D6\u00F6\u015E\u015F\u00DC\u00FC\s]+$/;
    if (!ad_val || !nameRegex.test(ad_val) || ad_val.length > 40) { 
        alert('Lütfen geçerli bir ad girin (sadece harfler, maks 40 karakter).'); 
        return; 
    }

    const body = {
        ad: ad_val,
        yas: parseInt(document.getElementById('m_yas').value) || 30,
        cinsiyet: document.getElementById('m_cinsiyet').value,
        boy: parseInt(document.getElementById('m_boy').value) || 170,
        kilo: parseFloat(document.getElementById('m_kilo').value) || 70,
        hastaliklar: parseListInput(document.getElementById('m_hastaliklar').value),
        alerjiler: parseListInput(document.getElementById('m_alerjiler').value),
        ilaclar: parseListInput(document.getElementById('m_ilaclar').value),
        hedef: document.getElementById('m_hedef').value,
        genetik_hastaliklar: parseListInput(document.getElementById('m_genetik').value),
        tibbi_gecmis: document.getElementById('m_tibbi').value.trim() || null,
    };

    try {
        const { res, data } = await safeFetchJson(API + endpoint, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(body),
        });
        if (data && data.success) {
            if (hasProfile !== 'true') {
                localStorage.setItem('cm_has_profile', 'true');
                localStorage.setItem('cm_onboarding_done', 'true');
            }
            document.getElementById('addModal').classList.add('hidden');
            // Formu temizle
            ['m_ad', 'm_yas', 'm_hastaliklar', 'm_alerjiler', 'm_ilaclar', 'm_genetik', 'm_tibbi'].forEach(id => document.getElementById(id).value = '');
            loadProfile();
        } else { alert(apiHataMesaji(data, 'Hata oluştu')); }
    } catch (e) { alert('Bağlantı kurulamadı. Lütfen birazdan tekrar deneyin.'); }
}

async function deleteMember(uyeId) {
    if (!confirm('Bu üyeyi silmek istediğinize emin misiniz?')) return;
    const user = getUser();
    try {
        const { res, data } = await safeFetchJson(API + '/api/family/' + uyeId, { method: 'DELETE' });
        if (res.ok && data?.success) loadProfile();
        else alert(apiHataMesaji(data, 'Üye silinemedi.'));
    } catch (e) { alert(baglantiHatasi(e)); }
}

let chatAbortController = null;

function stopGeneration() {
    if (chatAbortController) {
        chatAbortController.abort();
        chatAbortController = null;
    }
}

// -- CureBot Chat --
async function sendChat() {
    const input = document.getElementById('chatInput');
    const container = document.getElementById('chatMessages');
    if (!input || !container) {
        openCureBotWidget();
        return;
    }
    const msg = input.value.trim();
    if (!msg) return;
    input.value = '';

    const kimin_icin = document.getElementById('chatTarget')?.value || 'kendim';

    // Kullanıcı mesajını ekle
    container.innerHTML += `<div class="flex flex-col items-end gap-1"><div class="bg-[#005c55] text-white p-3.5 rounded-[20px] rounded-br-[4px] max-w-[85%] shadow-sm"><p class="font-body-md text-body-md">${escapeHtml(msg)}</p></div></div>`;

    // Loading indicator ve Stop butonu
    const loadingId = 'loading-' + Date.now();
    const chatBubbleId = 'bubble-' + Date.now();
    const statusTextId = 'status-' + Date.now();
    
    // Geçici Agent mesaj balonu
    container.innerHTML += `
    <div id="${loadingId}" class="flex items-end gap-2 w-full">
        <div class="w-8 h-8 rounded-full bg-primary-container flex items-center justify-center text-on-primary-container flex-shrink-0"><span class="material-symbols-outlined text-[18px]" style="font-variation-settings:'FILL' 1">smart_toy</span></div>
        <div class="flex flex-col gap-2 max-w-[85%] w-full">
            <div class="bg-surface-container-lowest text-on-surface p-4 rounded-[20px] rounded-bl-[4px] border border-outline-variant/20 shadow-sm w-full">
                <p id="${statusTextId}" class="text-xs text-on-surface-variant mb-2 animate-pulse">Sistem hazırlanıyor...</p>
                <div id="${chatBubbleId}" class="font-body-md text-body-md prose prose-sm max-w-none prose-p:my-1 prose-ul:my-1 prose-li:my-0"></div>
                <div class="loading-dots flex gap-1 mt-2" id="${loadingId}-dots">
                    <span class="w-2 h-2 rounded-full bg-outline-variant inline-block"></span>
                    <span class="w-2 h-2 rounded-full bg-outline-variant inline-block"></span>
                    <span class="w-2 h-2 rounded-full bg-outline-variant inline-block"></span>
                </div>
            </div>
            <button onclick="stopGeneration()" id="${loadingId}-stop" class="self-start text-xs text-error border border-error/50 rounded-full px-3 py-1 hover:bg-error/10 transition-colors flex items-center gap-1">
                <span class="material-symbols-outlined text-[14px]">stop_circle</span> Durdur
            </button>
        </div>
    </div>`;
    container.scrollTop = container.scrollHeight;

    chatAbortController = new AbortController();
    const bubbleEl = document.getElementById(chatBubbleId);
    const statusEl = document.getElementById(statusTextId);
    let fullCevap = '';
    updateChatGovernancePanel(null);

    try {
        const res = await safeFetchStream(API + '/api/chat', {
            method: 'POST', 
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ mesaj: msg, kimin_icin }),
            signal: chatAbortController.signal
        });
        
        if (!res.ok) {
            let hataMesaji = 'Yanıt hazırlanamadı.';
            try {
                const errData = await res.json();
                hataMesaji = apiHataMesaji(errData, hataMesaji);
            } catch(e){}
            statusEl.textContent = "Hata";
            statusEl.classList.remove("animate-pulse");
            statusEl.classList.add("text-error");
            bubbleEl.innerHTML = `<span class="text-error">${hataMesaji}</span>`;
            document.getElementById(`${loadingId}-dots`)?.remove();
            document.getElementById(`${loadingId}-stop`)?.remove();
            return;
        }

        const reader = res.body.getReader();
        const decoder = new TextDecoder('utf-8');
        let buffer = '';

        while (true) {
            const { done, value } = await reader.read();
            if (done) break;
            
            buffer += decoder.decode(value, { stream: true });
            let lines = buffer.split('\\n\\n');
            buffer = lines.pop(); // Son eleman yarım kalmış olabilir, buffer'da tut
            
            for (let line of lines) {
                if (line.startsWith('event: ')) {
                    const eventName = line.split('\\n')[0].replace('event: ', '').trim();
                    const dataLine = line.split('\\n')[1];
                    let data = {};
                    if (dataLine && dataLine.startsWith('data: ')) {
                        try {
                            data = JSON.parse(dataLine.replace('data: ', '').trim());
                        } catch(e) {}
                    }
                    
                    if (eventName === 'status') {
                        statusEl.textContent = `${data.agent || 'CureMenu'} ${data.status || 'çalışıyor'}...`;
                    } else if (eventName === 'message') {
                        statusEl.textContent = "CureBot yazıyor...";
                        fullCevap += data.chunk || '';
                        bubbleEl.innerHTML = formatMarkdownSafe(fullCevap);
                        container.scrollTop = container.scrollHeight;
                    } else if (eventName === 'error') {
                        statusEl.textContent = "Uyarı";
                        statusEl.classList.remove("animate-pulse");
                        statusEl.classList.add("text-error");
                        fullCevap = data.message || 'Sistem uyarısı.';
                        bubbleEl.innerHTML = formatMarkdownSafe(fullCevap);
                    } else if (eventName === 'governance') {
                        updateChatGovernancePanel(data);
                    } else if (eventName === 'done') {
                        statusEl.remove();
                        if (fullCevap.length > 300) {
                            const expandBtn = document.createElement('button');
                            expandBtn.className = 'mt-3 text-sm font-bold text-primary flex items-center gap-1 hover:underline';
                            expandBtn.innerHTML = '<span class="material-symbols-outlined text-[18px]">fullscreen</span>Geniş ekranda oku';
                            expandBtn.onclick = () => openReaderModal(fullCevap);
                            const messageRoot = document.getElementById(loadingId) || bubbleEl.closest('.flex') || container;
                            messageRoot.appendChild(expandBtn);
                        }
                    }
            }
        }
        }
    } catch (e) {
        if (e.name === 'AbortError') {
            statusEl.textContent = "İptal edildi";
            statusEl.classList.remove("animate-pulse");
            if (!fullCevap) bubbleEl.innerHTML = "<span class='text-outline-variant italic'>Yanıt iptal edildi.</span>";
        } else {
            statusEl.textContent = "Bağlantı koptu";
            statusEl.classList.remove("animate-pulse");
            statusEl.classList.add("text-error");
        }
    } finally {
        chatAbortController = null;
        document.getElementById(`${loadingId}-dots`)?.remove();
        document.getElementById(`${loadingId}-stop`)?.remove();
        statusEl.classList.remove("animate-pulse");
        if (statusEl.textContent.includes('yazıyor')) {
            statusEl.textContent = "Tamamlandı";
            statusEl.classList.add("text-primary");
        }
    }
}

function openReaderModal(markdownContent) {
    let modal = document.getElementById('readerModal');
    if (!modal) {
        modal = document.createElement('div');
        modal.id = 'readerModal';
        modal.className = 'fixed inset-0 z-[200] hidden items-center justify-center p-4';
        modal.innerHTML = `
        <div class="absolute inset-0 bg-on-background/50 backdrop-blur-sm" onclick="document.getElementById('readerModal').classList.add('hidden'); document.getElementById('readerModal').classList.remove('flex');"></div>
        <div class="card relative flex max-h-[90vh] w-full max-w-3xl flex-col overflow-hidden">
            <div class="flex items-center justify-between border-b border-outline-variant p-5">
                <h3 class="font-display text-2xl font-bold flex items-center gap-2"><span class="material-symbols-outlined text-primary">auto_awesome</span> CureBot Yanıtı</h3>
                <button onclick="document.getElementById('readerModal').classList.add('hidden'); document.getElementById('readerModal').classList.remove('flex');" class="btn-icon"><span class="material-symbols-outlined">close</span></button>
            </div>
            <div class="overflow-y-auto p-6 md:p-8 text-on-surface font-body-lg leading-8" id="readerModalContent"></div>
        </div>`;
        document.body.appendChild(modal);
    }
    document.getElementById('readerModalContent').innerHTML = formatMarkdownSafe(markdownContent);
    modal.classList.remove('hidden');
    modal.classList.add('flex');
}


// -- Haftalık Plan --
async function generatePlan() {
    const user = getUser();
    const kimin_icin = document.getElementById('planTarget').value;
    const result = document.getElementById('planResult');
    result.innerHTML = `<div class="text-center py-12"><div class="loading-dots flex gap-2 justify-center mb-4"><span class="w-3 h-3 rounded-full bg-primary inline-block"></span><span class="w-3 h-3 rounded-full bg-primary inline-block"></span><span class="w-3 h-3 rounded-full bg-primary inline-block"></span></div><p class="text-on-surface-variant font-body-md">Plan hazırlanıyor... Bu işlem 15-30 saniye sürebilir.</p></div>`;

    try {
        const { res, data } = await safeFetchJson(API + '/api/weekly-plan', {
            method: 'POST', headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ kimin_icin })
        });
        if (data && data.success) {
            localStorage.setItem('cm_saved_plan_' + user.telefon, data.plan);
            renderSavedPlan(data.plan);
        } else {
            result.innerHTML = `<div class="text-center py-8 text-error"><p>${apiHataMesaji(data, 'Plan oluşturulamadı.')}</p></div>`;
        }
    } catch (e) {
        result.innerHTML = `<div class="text-center py-8 text-error"><p>${baglantiHatasi(e)}</p></div>`;
    }
}

function renderSavedPlan(planText) {
    const result = document.getElementById('planResult');
    let formattedPlan = formatMarkdownSafe(planText);
    
    // Add "Nasıl Yapılır" buttons to the meal cells
    const tempDiv = document.createElement('div');
    tempDiv.innerHTML = formattedPlan;
    
    const tableRows = tempDiv.querySelectorAll('tr');
    tableRows.forEach(row => {
        const cells = row.querySelectorAll('td');
        // The first cell is usually the Day, so we start from index 1 (Breakfast, Lunch, Dinner)
        cells.forEach((cell, index) => {
            if (index > 0 && cell.textContent.trim().length > 3) {
                 const mealText = cell.textContent.trim().replace(/['"]/g, '');
                 const cellId = `meal-${row.rowIndex}-${index}`;
                 
                 // Kapsayıcı oluştur
                 const container = document.createElement('div');
                 container.className = "flex flex-col gap-2 mt-2 pt-2 border-t border-outline-variant/20";
                 
                 // Yedim Checkbox Alanı
                 const checkLabel = document.createElement('label');
                 checkLabel.className = "flex items-center gap-2 cursor-pointer group text-[12px] font-medium text-on-surface-variant hover:text-primary transition-colors";
                 checkLabel.innerHTML = `
                     <div class="relative flex items-center justify-center w-5 h-5 rounded border-2 border-outline-variant group-hover:border-primary transition-colors">
                         <input type="checkbox" id="${cellId}" class="peer sr-only" onchange="window.toggleMealCheck(this, '${mealText.replace(/'/g, "\\'")}')">
                         <span class="material-symbols-outlined text-[16px] text-white bg-primary rounded opacity-0 peer-checked:opacity-100 absolute inset-0 flex items-center justify-center transition-opacity">check</span>
                     </div>
                     <span class="peer-checked:line-through peer-checked:opacity-60 transition-all">Yedim (Tamamla)</span>
                 `;
                 
                 // Aksiyon Butonları (Tarif ve Alternatif)
                 const actionDiv = document.createElement('div');
                 actionDiv.className = "flex items-center gap-3";
                 
                 const btnTarif = document.createElement('button');
                 btnTarif.className = "text-primary text-[11px] underline flex items-center gap-1 hover:text-primary-container";
                 btnTarif.innerHTML = '<span class="material-symbols-outlined text-[12px]">restaurant</span> Tarifi Al';
                 btnTarif.setAttribute('onclick', `window.askRecipeForWeeklyPlan('${mealText.replace(/'/g, "\\'")}')`);
                 
                 const btnAlternatif = document.createElement('button');
                 btnAlternatif.className = "text-error text-[11px] underline flex items-center gap-1 hover:text-error/80";
                 btnAlternatif.innerHTML = '<span class="material-symbols-outlined text-[12px]">swap_horiz</span> Yiyemedim';
                 btnAlternatif.setAttribute('onclick', `window.requestAlternativeMeal('${mealText.replace(/'/g, "\\'")}')`);
                 
                 actionDiv.appendChild(btnTarif);
                 actionDiv.appendChild(btnAlternatif);
                 
                 container.appendChild(checkLabel);
                 container.appendChild(actionDiv);
                 
                 // Restore Checkbox state
                 if (localStorage.getItem('cm_check_' + cellId) === 'true') {
                     checkLabel.querySelector('input').checked = true;
                     cell.classList.add('opacity-60', 'bg-surface-container-high');
                 }
                 
                 cell.appendChild(container);
                 cell.classList.add('transition-all', 'duration-300');
                 cell.dataset.cellId = cellId;
            }
        });
    });
    formattedPlan = tempDiv.innerHTML;
    
    window.currentPlanText = planText;
    
    result.innerHTML = `
    <div class="mb-6 bg-primary-container/30 border border-primary/20 rounded-xl p-4 flex items-center justify-between">
        <div>
            <h4 class="font-display font-bold text-primary flex items-center gap-2">
                <span class="material-symbols-outlined text-2xl">trophy</span> Sağlık Puanın: <span id="uiMealScore" class="text-2xl">0</span>
            </h4>
            <p class="text-xs text-on-surface-variant mt-1">Öğünlerine sadık kalarak puan topla. Alternatif istemek serbest!</p>
        </div>
        <div class="text-center">
            <div class="inline-flex items-center justify-center w-12 h-12 bg-error/10 rounded-full text-error mb-1">
                <span class="material-symbols-outlined text-3xl">local_fire_department</span>
            </div>
            <div class="text-xs font-bold text-error"><span id="uiMealStreak">0</span> Günlük Seri!</div>
        </div>
    </div>
    
    <div class="prose prose-sm md:prose-base max-w-none font-body-md text-on-surface 
                prose-table:w-full prose-table:border-collapse prose-table:border prose-table:border-outline-variant/30
                prose-th:bg-surface-container-high prose-th:p-3 prose-th:text-left prose-th:font-label-md prose-th:border prose-th:border-outline-variant/30
                prose-td:p-3 prose-td:border prose-td:border-outline-variant/30 prose-tr:even:bg-surface-container-lowest prose-tr:odd:bg-surface/50">
        ${formattedPlan}
    </div>
    <div class="mt-8 flex flex-wrap justify-center gap-3">
        <button onclick="openSmartGrocery()" class="btn-primary px-6 py-3 rounded-full font-label-md text-label-md flex items-center gap-2 shadow-sm transition-all active:scale-95">
            <span class="material-symbols-outlined">local_grocery_store</span>
            Akıllı Sepeti Gör
        </button>
        <button onclick="calculateBudget()" class="bg-secondary text-on-secondary px-6 py-3 rounded-full font-label-md text-label-md flex items-center gap-2 hover:bg-secondary/90 shadow-sm transition-all active:scale-95">
            <span class="material-symbols-outlined">shopping_cart</span>
            Bütçe Hesapla ve Alışveriş Listesi Çıkar
        </button>
    </div>
    <div id="budgetResult" class="mt-6 w-full"></div>`;
    
    // Change "Planı Oluştur" to "Yeniden Oluştur"
    const generateBtn = document.querySelector('button[onclick="generatePlan()"]');
    if (generateBtn) {
        generateBtn.innerHTML = '<span class="material-symbols-outlined">refresh</span>Yeniden Oluştur';
    }
    
    // Tablo render edildikten sonra hesaplamayı yap
    recalculateGamification();
}


async function calculateBudget() {
    if (!window.currentPlanText) return;
    const user = getUser();
    const resultDiv = document.getElementById('budgetResult');
    
    resultDiv.innerHTML = `<div class="text-center py-8"><div class="loading-dots flex gap-2 justify-center mb-4"><span class="w-3 h-3 rounded-full bg-secondary inline-block"></span><span class="w-3 h-3 rounded-full bg-secondary inline-block"></span><span class="w-3 h-3 rounded-full bg-secondary inline-block"></span></div><p class="text-on-surface-variant font-body-md" id="budgetLoadingText">Alışveriş listesi hazırlanıyor...<br/>Fiyatlar tahmini aralık olarak gösterilecek.</p></div>`;
    
    let locationStr = "Türkiye geneli tahmini fiyat aralığı; market uygunluğu manuel kontrol edilmelidir.";
    const loadingText = document.getElementById('budgetLoadingText');
    
    // Konum Alma (Promise Wrapper)
    const getLocation = () => new Promise((resolve) => {
        if (!navigator.geolocation) {
            resolve(null);
            return;
        }
        navigator.geolocation.getCurrentPosition(
            pos => resolve(pos.coords),
            err => resolve(null),
            { timeout: 5000, maximumAge: 60000 }
        );
    });

    const coords = await getLocation();
    
    if (coords) {
        if (loadingText) loadingText.innerHTML = "Konum izni alındı.<br/>Yakındaki mağaza uygunluğunu haritada manuel kontrol edebilirsiniz.";
        locationStr = "Stok ve fiyat bilgisi doğrulanmadı; markete göre değişebilir.";
    } else {
        if (loadingText) loadingText.innerHTML = "Konum izni alınamadı.<br/>Türkiye geneli tahmini fiyat aralığı hazırlanıyor.";
    }
    
    try {
        const { res, data } = await safeFetchJson(API + '/api/shopping-list', {
            method: 'POST', headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ plan_metni: window.currentPlanText, location_info: locationStr })
        });
        
        if (data && data.success) {
            const formatted = formatMarkdownSafe(data.rapor);
            resultDiv.innerHTML = `
            <div class="bg-surface-container-low rounded-lg p-6 border border-secondary/20 shadow-inner">
                <div class="prose prose-sm max-w-none font-body-md text-on-surface
                        prose-table:w-full prose-table:border-collapse prose-table:border prose-table:border-outline-variant/30
                        prose-th:bg-surface-container-high prose-th:p-2 prose-th:text-left prose-th:font-label-md prose-th:border prose-th:border-outline-variant/30
                        prose-td:p-2 prose-td:border prose-td:border-outline-variant/30 prose-tr:even:bg-surface-container-lowest prose-tr:odd:bg-surface/50">
                    ${formatted}
                </div>
            </div>`;
        } else {
            resultDiv.innerHTML = `<div class="text-center py-4 text-error"><p>${apiHataMesaji(data, 'Rapor oluşturulamadı.')}</p></div>`;
        }
    } catch (e) {
        resultDiv.innerHTML = `<div class="text-center py-4 text-error"><p>${baglantiHatasi(e)}</p></div>`;
    }
}

function ensureSmartGroceryModal() {
    let modal = document.getElementById('smartGroceryModal');
    if (modal) return modal;
    modal = document.createElement('div');
    modal.id = 'smartGroceryModal';
    modal.className = 'fixed inset-0 z-[180] hidden items-center justify-center p-4';
    modal.innerHTML = `
        <div class="absolute inset-0 bg-on-background/50 backdrop-blur-sm" onclick="closeSmartGrocery()"></div>
        <div class="card relative flex max-h-[90vh] w-full max-w-5xl flex-col overflow-hidden">
            <div class="flex items-center justify-between border-b border-outline-variant p-5">
                <div>
                    <h3 class="font-display text-2xl font-bold">Akıllı Sepet</h3>
                    <p class="mt-1 text-sm text-on-surface-variant">Sağlık profiline göre işaretlenmiş tahmini alışveriş listesi.</p>
                </div>
                <button onclick="closeSmartGrocery()" class="btn-icon"><span class="material-symbols-outlined">close</span></button>
            </div>
            <div id="smartGroceryContent" class="chat-scroll overflow-y-auto p-5"></div>
        </div>`;
    document.body.appendChild(modal);
    return modal;
}

function closeSmartGrocery() {
    const modal = document.getElementById('smartGroceryModal');
    if (modal) {
        modal.classList.add('hidden');
        modal.classList.remove('flex');
    }
}

async function openSmartGrocery() {
    const modal = ensureSmartGroceryModal();
    const content = document.getElementById('smartGroceryContent');
    const target = document.getElementById('planTarget')?.value || 'kendim';
    modal.classList.remove('hidden');
    modal.classList.add('flex');
    if (!window.currentPlanText) {
        content.innerHTML = emptyState('shopping_cart', 'Plan bulunamadı', 'Akıllı sepet için önce haftalık plan oluşturman gerekiyor.');
        return;
    }
    content.innerHTML = `<div class="py-16 text-center text-on-surface-variant"><div class="loading-dots flex gap-2 justify-center mb-4"><span class="w-3 h-3 rounded-full bg-primary inline-block"></span><span class="w-3 h-3 rounded-full bg-primary inline-block"></span><span class="w-3 h-3 rounded-full bg-primary inline-block"></span></div><p>Sepet sağlık profiline göre hazırlanıyor...</p></div>`;

    try {
        const { res, data } = await safeFetchJson(API + '/api/smart-grocery', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                weekly_plan: window.currentPlanText,
                kimin_icin: target,
                location_context: 'Türkiye'
            })
        });
        if (!res.ok || !data?.success) {
            content.innerHTML = `<div class="rounded-lg border border-error/20 bg-error-container p-5 text-on-error-container">${apiHataMesaji(data, 'Akıllı sepet hazırlanamadı.')}</div>`;
            return;
        }
        renderSmartGrocery(data);
    } catch (e) {
        content.innerHTML = `<div class="rounded-lg border border-error/20 bg-error-container p-5 text-on-error-container">${baglantiHatasi(e)}</div>`;
    }
}

function groceryStatusClass(status) {
    const map = {
        safe: 'status-ok',
        caution: 'status-warn',
        avoid: 'status-risk',
        unknown: 'status-info',
    };
    return map[status] || 'status-info';
}

function groceryStatusLabel(status) {
    const map = {
        safe: 'Uygun',
        caution: 'Dikkat',
        avoid: 'Kaçın',
        unknown: 'Belirsiz',
    };
    return map[status] || 'Belirsiz';
}

function groceryPriceRange(item) {
    if (item.estimated_min_price == null || item.estimated_max_price == null) {
        return 'Fiyatlandırmaya alınmadı';
    }
    return `${Number(item.estimated_min_price || 0).toLocaleString('tr-TR')} TL - ${Number(item.estimated_max_price || 0).toLocaleString('tr-TR')} TL`;
}

function renderSmartGrocery(data) {
    const content = document.getElementById('smartGroceryContent');
    if (!content) return;
    const categoryLabels = {
        protein: 'Protein',
        sebze_meyve: 'Sebze & meyve',
        sut_urunleri: 'Süt ürünleri',
        bakliyat: 'Bakliyat',
        tahil: 'Tahıl',
        yag: 'Yağ',
        temel_gida: 'Temel gıda',
    };
    const categoryHtml = Object.entries(data.categories || {})
        .filter(([, items]) => Array.isArray(items) && items.length)
        .map(([category, items]) => `
            <section class="rounded-lg border border-outline-variant bg-surface p-4">
                <h4 class="mb-3 font-display text-xl font-bold text-on-surface">${escapeHtml(categoryLabels[category] || category)}</h4>
                <div class="grid gap-3">
                    ${items.map(item => `
                        <article class="rounded-lg bg-surface-container-low p-4">
                            <div class="flex flex-col gap-3 md:flex-row md:items-start md:justify-between">
                                <div class="min-w-0">
                                    <p class="font-bold text-on-surface">${escapeHtml(item.name)}</p>
                                    <p class="mt-1 text-sm text-on-surface-variant">${escapeHtml(item.estimated_quantity || 'Tahmini miktar')}</p>
                                    <p class="mt-2 text-sm text-on-surface-variant">${escapeHtml(item.reason || '')}</p>
                                </div>
                                <div class="flex flex-col items-start gap-2 md:items-end">
                                    <span class="status-pill ${groceryStatusClass(item.health_status)}">${groceryStatusLabel(item.health_status)}</span>
                                    <span class="text-sm font-bold text-primary">${groceryPriceRange(item)}</span>
                                </div>
                            </div>
                        </article>`).join('')}
                </div>
            </section>`)
        .join('');
    const excludedHtml = (data.excluded_items || [])
        .map(item => `
            <article class="rounded-lg border border-error/20 bg-error-container/30 p-4">
                <div class="flex flex-col gap-3 md:flex-row md:items-start md:justify-between">
                    <div class="min-w-0">
                        <p class="font-bold text-on-surface">${escapeHtml(item.name)}</p>
                        <p class="mt-1 text-sm text-on-surface-variant">${escapeHtml(item.estimated_quantity || 'Belirtilmedi')}</p>
                        <p class="mt-2 text-sm text-on-surface-variant">${escapeHtml(item.reason || '')}</p>
                    </div>
                    <div class="flex flex-col items-start gap-2 md:items-end">
                        <span class="status-pill status-risk">${groceryStatusLabel(item.health_status)}</span>
                        <span class="text-sm font-bold text-error">${groceryPriceRange(item)}</span>
                    </div>
                </div>
            </article>`)
        .join('');
    const decisionHtml = data.decision_id
        ? `<div class="mb-5 rounded-lg border border-outline-variant bg-surface p-4 text-sm text-on-surface-variant"><span class="font-bold text-on-surface">Karar kaydı:</span> ${escapeHtml(data.decision_id)}${data.price_catalog_version ? ` · ${escapeHtml(data.price_catalog_version)}` : ''}</div>`
        : '';

    content.innerHTML = `
        <div class="mb-5 grid gap-3 md:grid-cols-4">
            <div class="quiet-card p-4"><p class="metric-label">Toplam aralık</p><p class="mt-1 font-display text-2xl font-bold">${Number(data.estimated_min_total || 0).toLocaleString('tr-TR')} TL - ${Number(data.estimated_max_total || 0).toLocaleString('tr-TR')} TL</p></div>
            <div class="quiet-card p-4"><p class="metric-label">Uygun</p><p class="mt-1 font-display text-2xl font-bold">${data.health_safe_total_items || 0}</p></div>
            <div class="quiet-card p-4"><p class="metric-label">Dikkat</p><p class="mt-1 font-display text-2xl font-bold">${data.caution_items || 0}</p></div>
            <div class="quiet-card p-4"><p class="metric-label">Kaçın</p><p class="mt-1 font-display text-2xl font-bold">${data.avoid_items || 0}</p></div>
        </div>
        <div class="mb-5 rounded-lg border border-warning/20 bg-warning-container p-4 text-sm text-on-surface-variant">${escapeHtml(data.disclaimer || 'Stok ve fiyat bilgisi doğrulanmadı; markete göre değişebilir.')}</div>
        <p class="mb-5 text-on-surface-variant">${escapeHtml(data.recommendation_summary || '')}</p>
        <div class="grid gap-4 xl:grid-cols-2">${categoryHtml || emptyState('shopping_cart', 'Sepet kalemi bulunamadı', 'Haftalık plan oluşturulduğunda alışveriş listesi burada görünür.')}</div>
        <div class="mt-6 rounded-lg border border-outline-variant bg-surface p-4">
            <h4 class="mb-3 font-display text-xl font-bold">Haritada manuel kontrol</h4>
            <div class="flex flex-wrap gap-2">
                ${(data.market_search_links || []).map(link => `<a class="btn-secondary px-4 py-2 text-sm font-bold" href="${escapeHtml(link.url)}" target="_blank" rel="noopener">${escapeHtml(link.market || 'Market')}</a>`).join('')}
            </div>
        </div>`;
    if (decisionHtml) {
        content.querySelector('.mb-5.grid')?.insertAdjacentHTML('afterend', decisionHtml);
    }
    if (excludedHtml) {
        content.querySelector('.mt-6.rounded-lg')?.insertAdjacentHTML('beforebegin', `
        <section class="mt-6 rounded-lg border border-error/20 bg-surface p-4">
            <h4 class="mb-3 font-display text-xl font-bold">Sağlık nedeniyle dışlandı</h4>
            <div class="grid gap-3">${excludedHtml}</div>
        </section>`);
    }
}

// Global olarak çağrılabilmesi için window objesine ekliyoruz
window.askRecipeForWeeklyPlan = async function(mealText) {
    const modal = document.getElementById('actionModal');
    const title = document.getElementById('actionModalTitle');
    const subtitle = document.getElementById('actionModalSubtitle');
    const content = document.getElementById('actionModalContent');
    
    if (!modal) return;
    
    title.innerHTML = '<span class="material-symbols-outlined align-middle mr-2">restaurant</span> Tarif Hazırlanıyor...';
    subtitle.textContent = `"${mealText}" için CureBot'tan detaylı tarif alınıyor.`;
    content.innerHTML = `<div class="py-12 text-center"><div class="loading-dots flex gap-2 justify-center mb-4"><span class="w-3 h-3 rounded-full bg-primary inline-block"></span><span class="w-3 h-3 rounded-full bg-primary inline-block"></span><span class="w-3 h-3 rounded-full bg-primary inline-block"></span></div><p class="text-on-surface-variant font-body-md">Şefimiz malzemeleri topluyor...</p></div>`;
    modal.classList.remove('hidden');
    
    try {
        const { res, data } = await safeFetchJson(API + '/api/plan-action', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ action_type: 'recipe', meal_text: mealText })
        });
        
        if (data && data.success) {
            title.innerHTML = '<span class="material-symbols-outlined align-middle mr-2">menu_book</span> Tarif: ' + escapeHtml(mealText);
            subtitle.textContent = "Afiyet olsun! İşte yemeğinizin tarifi.";
            content.innerHTML = `<div class="prose max-w-none text-on-surface">${formatMarkdownSafe(data.result)}</div>`;
        } else {
            content.innerHTML = `<div class="p-6 text-center text-error font-bold">Tarif alınamadı: ${escapeHtml(data?.detail || 'Bilinmeyen hata')}</div>`;
        }
    } catch (e) {
        content.innerHTML = `<div class="p-6 text-center text-error font-bold">Bağlantı hatası oluştu.</div>`;
    }
};

async function sendFeedback(yemekAdi) {
    if (!yemekAdi) return;
    const user = getUser();
    const kimin_icin = document.getElementById('planTarget')?.value
        || document.getElementById('menuTarget')?.value
        || document.getElementById('fridgeTarget')?.value
        || 'kendim';
    try {
        const { res, data } = await safeFetchJson(API + '/api/feedback', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                yemek_adi: yemekAdi,
                kimin_icin,
            }),
        });
        if (res.ok && data?.success) alert(data.message || 'Geri bildiriminiz kaydedildi.');
        else alert(apiHataMesaji(data, 'Geri bildirim kaydedilemedi.'));
    } catch (e) {
        alert(baglantiHatasi(e));
    }
}
window.sendFeedback = sendFeedback;

// -- Menü Tarayıcı --
async function scanMenu() {
    const user = getUser();
    const url = document.getElementById('menuUrlInput').value.trim();
    const kimin_icin = document.getElementById('menuTarget').value;
    const result = document.getElementById('menuScanResult');
    
    if (!url) {
        alert("Lütfen bir restoran menü linki girin.");
        return;
    }
    
    result.innerHTML = `<div class="text-center py-12"><div class="loading-dots flex gap-2 justify-center mb-4"><span class="w-3 h-3 rounded-full bg-primary inline-block"></span><span class="w-3 h-3 rounded-full bg-primary inline-block"></span><span class="w-3 h-3 rounded-full bg-primary inline-block"></span></div><p class="text-on-surface-variant font-body-md">Menü taranıyor ve tıbbi profilinize göre analiz ediliyor... Bu işlem 15-20 saniye sürebilir.</p></div>`;

    try {
        const { res, data } = await safeFetchJson(API + '/api/scan-menu', {
            method: 'POST', headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ kimin_icin, url })
        });
        if (data && data.success) {
            const formatted = formatMarkdownSafe(data.analiz);
            result.innerHTML = `
            <div class="bg-surface-container-lowest rounded-lg p-8 shadow-l1 border border-outline-variant/20">
                <div class="prose prose-sm md:prose-base max-w-none font-body-md text-on-surface">
                    ${formatted}
                </div>
            </div>`;
        } else {
            result.innerHTML = `<div class="bg-error-container text-on-error-container p-6 rounded-lg text-center"><p>${apiHataMesaji(data, 'Menü okunamadı.')}</p></div>`;
        }
    } catch (e) {
        result.innerHTML = `<div class="bg-error-container text-on-error-container p-6 rounded-lg text-center"><p>${baglantiHatasi(e)}</p></div>`;
    }
}

async function scanMenuImage(inputEl) {
    const file = inputEl?.files?.[0];
    if (!file) return;
    const user = getUser();
    const kimin_icin = document.getElementById('menuTarget').value;
    const result = document.getElementById('menuScanResult');

    result.innerHTML = `<div class="text-center py-12"><div class="loading-dots flex gap-2 justify-center mb-4"><span class="w-3 h-3 rounded-full bg-primary inline-block"></span><span class="w-3 h-3 rounded-full bg-primary inline-block"></span><span class="w-3 h-3 rounded-full bg-primary inline-block"></span></div><p class="text-on-surface-variant font-body-md">Menü fotoğrafı analiz ediliyor...</p></div>`;

    const reader = new FileReader();
    reader.onload = async () => {
        try {
            const base64 = String(reader.result).split(',')[1] || reader.result;
            const { res, data } = await safeFetchJson(API + '/api/scan-menu-image', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ kimin_icin, image_base64: base64 }),
            });
            if (data && data.success) {
                result.innerHTML = `<div class="bg-surface-container-lowest rounded-lg p-8 shadow-l1 border border-outline-variant/20"><div class="prose prose-sm md:prose-base max-w-none font-body-md text-on-surface">${formatMarkdownSafe(data.analiz)}</div></div>`;
            } else {
                result.innerHTML = `<div class="bg-error-container text-on-error-container p-6 rounded-lg text-center"><p>${apiHataMesaji(data, 'Menü fotoğrafı okunamadı.')}</p></div>`;
            }
        } catch (e) {
            result.innerHTML = `<div class="bg-error-container text-on-error-container p-6 rounded-lg text-center"><p>${baglantiHatasi(e)}</p></div>`;
        }
        inputEl.value = '';
    };
    reader.readAsDataURL(file);
}
window.scanMenuImage = scanMenuImage;

let html5QrcodeScanner;

function startQRScanner() {
    const qrReaderDiv = document.getElementById('qr-reader');
    qrReaderDiv.style.display = "block";
    
    if (html5QrcodeScanner) {
        html5QrcodeScanner.clear();
    }
    
    html5QrcodeScanner = new Html5QrcodeScanner(
        "qr-reader", 
        { fps: 10, qrbox: {width: 250, height: 250} },
        false
    );
    
    html5QrcodeScanner.render(onScanSuccess, onScanFailure);
}

function onScanSuccess(decodedText, decodedResult) {
    html5QrcodeScanner.clear();
    document.getElementById('qr-reader').style.display = "none";
    
    // Okunan linki URL kutusuna yaz ve analizi başlat
    document.getElementById('menuUrlInput').value = decodedText;
    scanMenu();
}

function onScanFailure(error) {
    // Tarayıcı arka planda okuma yaparken sürekli hata fırlatabilir, logları temiz tutmak için yoruma aldım.
    // console.warn(`Code scan error = ${error}`);
}

function escapeHtml(str) {
    const div = document.createElement('div');
    div.textContent = str;
    return div.innerHTML;
}

// -- Buzdolabım (Fridge Scanner) --
function handleFridgeImage(event) {
    const file = event.target.files[0];
    if (!file) return;

    const reader = new FileReader();
    reader.onload = function(e) {
        const base64String = e.target.result;
        scanFridge(base64String);
    };
    reader.readAsDataURL(file);
}

// -- Tahlil / Sağlık Raporu Yükleme --
async function uploadHealthRecord(event) {
    const file = event.target.files[0];
    if (!file) return;

    const user = getUser();
    const kimin_icin = document.getElementById('tahlilTarget')?.value || 'kendim';
    const result = document.getElementById('healthRecordResult');
    
    // Reset file input
    document.getElementById('healthRecordInput').value = '';
    
    result.innerHTML = `<div class="text-center py-12"><div class="loading-dots flex gap-2 justify-center mb-4"><span class="w-3 h-3 rounded-full bg-primary inline-block"></span><span class="w-3 h-3 rounded-full bg-primary inline-block"></span><span class="w-3 h-3 rounded-full bg-primary inline-block"></span></div><p class="text-on-surface-variant font-body-md">Tahlil dosyanı güvenli şekilde okuyorum...<br/>Bu işlem biraz sürebilir.</p></div>`;

    const formData = new FormData();
    formData.append("file", file);
    formData.append("kimin_icin", kimin_icin);

    try {
        const res = await fetch(API + '/api/upload-health-record', {
            method: 'POST',
            credentials: 'include',
            body: formData
        });
        const data = await res.json();
        
        if (res.ok && data.success) {
            result.innerHTML = `
            <div class="bg-primary-container/20 border border-primary/30 rounded-lg p-6 text-center">
                <span class="material-symbols-outlined text-primary text-4xl mb-2">task_alt</span>
                <h4 class="font-headline-md text-primary mb-2">Başarıyla Yüklendi!</h4>
                <p class="font-body-md text-on-surface">${data.message || 'Tahlil notların kaydedildi. CureBot sonraki yanıtlarda bu bilgileri dikkate alabilir.'}</p>
                <button onclick="openCureBotWidget('Tahlillerimi yükledim. Beslenme açısından nelere dikkat etmeliyim?')" class="mt-4 bg-primary text-on-primary px-6 py-2 rounded-full font-label-md hover:bg-primary/90 transition-colors shadow-sm">CureBot ile Konuşmaya Başla</button>
            </div>`;
        } else {
            result.innerHTML = `<div class="bg-error-container text-on-error-container p-6 rounded-lg text-center"><p>${apiHataMesaji(data, 'PDF yüklenemedi.')}</p></div>`;
        }
    } catch (e) {
        result.innerHTML = `<div class="bg-error-container text-on-error-container p-6 rounded-lg text-center"><p>${baglantiHatasi(e)}</p></div>`;
    }
}




// -- Sesli Asistan (Voice AI) --

let recognition;
let isRecording = false;

if ('webkitSpeechRecognition' in window || 'SpeechRecognition' in window) {
    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
    recognition = new SpeechRecognition();
    recognition.lang = 'tr-TR';
    recognition.continuous = false;
    recognition.interimResults = false;

    recognition.onresult = function(event) {
        const transcript = event.results[0][0].transcript;
        const input = document.getElementById('chatInput');
        if (input) {
            input.value = transcript;
            sendChat(); // Otomatik gönder
        } else {
            openCureBotWidget(transcript);
        }
    };

    recognition.onerror = function(event) {
        console.error('Ses tanıma hatası:', event.error);
        stopVoiceRecognition();
    };

    recognition.onend = function() {
        stopVoiceRecognition();
    };
}

function toggleVoiceRecognition() {
    if (!recognition) {
        alert('Tarayıcınız sesli komut özelliğini desteklemiyor. Lütfen Chrome, Edge veya Safari kullanın.');
        return;
    }
    
    // Mute active speech synthesis when microphone is activated / Mikrofon açıldığında aktif seslendirmeyi durdur
    if ('speechSynthesis' in window) {
        window.speechSynthesis.cancel();
    }
    
    if (isRecording) {
        recognition.stop();
    } else {
        recognition.start();
        isRecording = true;
        const micBtn = document.getElementById('micBtn');
        const micIcon = document.getElementById('micIcon');
        micBtn.classList.add('bg-error', 'text-on-error', 'animate-pulse');
        micBtn.classList.remove('hover:bg-surface-container', 'text-on-surface-variant');
        micIcon.textContent = 'mic_none';
        const input = document.getElementById('chatInput');
        if (input) input.placeholder = 'Sizi dinliyorum...';
    }
}

function stopVoiceRecognition() {
    isRecording = false;
    const micBtn = document.getElementById('micBtn');
    const micIcon = document.getElementById('micIcon');
    if(micBtn) {
        micBtn.classList.remove('bg-error', 'text-on-error', 'animate-pulse');
        micBtn.classList.add('hover:bg-surface-container', 'text-on-surface-variant');
        micIcon.textContent = 'mic';
    }
    const input = document.getElementById('chatInput');
    if(input) input.placeholder = "CureBot'a bir şey sor...";
}

// AI cevabını seslendirme (Akıcı ve tatlı bir anlatım)
function speakText(text) {
    if (!('speechSynthesis' in window)) return;
    
    // Zaten konuşuyorsa sustur
    window.speechSynthesis.cancel();
    
    // Markdown ve emojileri büyük ölçüde temizle
    let cleanText = text.replace(/[#*`_|>]/g, '');
    cleanText = cleanText.replace(/-/g, '.'); // Liste maddelerini cümleye çevir
    
    // Tarifin tamamını okursa sıkıcı olabilir. Normal bir diyalog gibi okutalım.
    let textToSpeak = cleanText;
    if (cleanText.includes('Malzemeler') || cleanText.includes('Yapılışı')) {
        const splitText = cleanText.split('Malzemeler');
        // Sadece giriş kısmını okuyacak
        textToSpeak = splitText[0].trim() + ". Harika bir tarif hazırladım! Detaylı malzemeleri ve yapılışını ekrandan okuyabilirsiniz. Şimdiden afiyet olsun.";
    }
    
    const utterance = new SpeechSynthesisUtterance(textToSpeak);
    utterance.lang = 'tr-TR';
    utterance.rate = 1.0; // Konuşma hızı (normal)
    utterance.pitch = 1.0; // Ses tonu (normal)
    
    // Türkçe sesi bulmaya çalış
    const setVoice = () => {
        const voices = window.speechSynthesis.getVoices();
        // Tercihen Google Türkçe sesi (daha doğal gelir)
        const trVoice = voices.find(v => v.lang.includes('tr') && v.name.includes('Google')) || voices.find(v => v.lang.includes('tr'));
        if (trVoice) {
            utterance.voice = trVoice;
        }
        window.speechSynthesis.speak(utterance);
    };

    // Sesler henüz yüklenmemişse bekle
    if (window.speechSynthesis.getVoices().length === 0) {
        window.speechSynthesis.onvoiceschanged = setVoice;
    } else {
        setVoice();
    }
}

// -- Geçmiş İşlemlerim (History) --
function formatPercent(value) {
    const num = Number(value || 0);
    return `${num.toFixed(1)}%`;
}

function renderKpiCard(label, value, icon, tone = 'primary') {
    const color = tone === 'error' ? 'text-error bg-error-container border-error/20' : 'text-primary bg-primary-container border-primary/20';
    return `
        <article class="card p-5">
            <div class="mb-4 flex items-center justify-between gap-3">
                <span class="material-symbols-outlined ${color} rounded-lg border p-2">${icon}</span>
            </div>
            <p class="metric-label">${escapeHtml(label)}</p>
            <p class="mt-1 font-display text-3xl font-extrabold text-on-surface">${escapeHtml(String(value))}</p>
        </article>`;
}

function clampScore(value) {
    const number = Number(value || 0);
    return Math.max(0, Math.min(100, number));
}

function renderKpiEventBreakdown(kpis) {
    const root = document.getElementById('kpiEventBreakdown');
    if (!root) return;
    if (!kpis || Number(kpis.total_decisions || 0) === 0) {
        root.innerHTML = `
            <div class="text-center py-8 text-on-surface-variant">
                <span class="material-symbols-outlined text-5xl mb-3 block opacity-30">health_and_safety</span>
                <p>Henüz yeterli kontrol kaydı yok. CureBot ile birkaç görüşmeden sonra burada güvenlik özeti oluşur.</p>
            </div>`;
        return;
    }

    const metrics = [
        {
            label: 'Profil uyumu',
            desc: 'Yanıtlar profil bilgilerinle eşleştirildi.',
            icon: 'person_check',
            value: clampScore(Number(kpis.average_confidence || 0) * 100),
        },
        {
            label: 'Risk kontrolü',
            desc: 'Yüksek riskli durumlarda daha temkinli davranıldı.',
            icon: 'shield',
            value: clampScore(100 - Number(kpis.high_risk_rate || 0)),
        },
        {
            label: 'Kaynak kaydı',
            desc: 'Kaynak veya izleme kaydı bulunan karar oranı.',
            icon: 'menu_book',
            value: clampScore(kpis.evidence_coverage_rate || kpis.retrieval_evidence_rate || 0),
        },
        {
            label: 'Yönlendirme hassasiyeti',
            desc: 'Belirsiz durumlarda güvenli tarafa çekme oranı.',
            icon: 'support_agent',
            value: clampScore(100 - Number(kpis.blocked_event_rate || 0)),
        },
    ];

    root.innerHTML = metrics.map((metric) => `
        <div class="rounded-lg border border-outline-variant/20 bg-surface p-4">
            <div class="flex items-start gap-3">
                <span class="material-symbols-outlined text-primary bg-primary-container/15 rounded-full p-2">${metric.icon}</span>
                <div class="flex-1 min-w-0">
                    <div class="flex items-center justify-between gap-3">
                        <p class="font-label-md text-on-surface">${escapeHtml(metric.label)}</p>
                        <span class="font-label-sm text-primary">${metric.value.toFixed(0)}%</span>
                    </div>
                    <div class="mt-2 h-2 rounded-full bg-surface-container overflow-hidden">
                        <div class="h-full rounded-full bg-primary" style="width:${metric.value}%"></div>
                    </div>
                    <p class="mt-2 text-xs leading-5 text-on-surface-variant">${escapeHtml(metric.desc)}</p>
                </div>
            </div>
        </div>`).join('');
}

function renderClinicalDecisions(decisions) {
    const root = document.getElementById('clinicalDecisionList');
    if (!root) return;
    if (!decisions || decisions.length === 0) {
        root.innerHTML = '<p class="text-on-surface-variant">Henuz klinik karar kaydi yok. CureBot ile bir konusma yaptiktan sonra burada gorunur.</p>';
        return;
    }
    root.innerHTML = decisions.map((decision) => {
        const risk = Number(decision.risk_score || 0);
        const confidence = Number(decision.confidence_score || 0);
        const riskTone = risk >= 0.7 ? 'text-error bg-error-container/40' : 'text-primary bg-primary-container/20';
        const decisionId = String(decision.decision_id || '').replace(/[^a-zA-Z0-9_-]/g, '');
        return `
            <article class="rounded-lg border border-outline-variant/20 bg-surface p-4">
                <div class="flex flex-col md:flex-row md:items-center justify-between gap-3">
                    <div class="min-w-0">
                        <p class="font-label-sm text-outline truncate">${escapeHtml(decision.decision_id || '')}</p>
                        <p class="font-body-md text-on-surface mt-1 line-clamp-2">${escapeHtml(decision.istek || '')}</p>
                    </div>
                    <div class="flex items-center gap-2 shrink-0 flex-wrap">
                        <span class="px-2 py-1 rounded-full text-xs ${riskTone}">Risk ${risk.toFixed(2)}</span>
                        <span class="px-2 py-1 rounded-full text-xs bg-surface-container text-primary">Operasyonel güven ${confidence.toFixed(2)}</span>
                        <button type="button" onclick="openDecisionTimeline('${decisionId}')" class="inline-flex items-center justify-center w-9 h-9 rounded-full border border-outline-variant/30 text-primary hover:bg-primary-container/20 transition-colors" title="Karar adımları">
                            <span class="material-symbols-outlined text-[20px]">timeline</span>
                        </button>
                    </div>
                </div>
            </article>`;
    }).join('');
}

function formatDecisionDate(value) {
    if (!value) return '-';
    const date = new Date(value);
    if (Number.isNaN(date.getTime())) return String(value);
    return date.toLocaleString('tr-TR', {
        day: '2-digit',
        month: 'short',
        hour: '2-digit',
        minute: '2-digit',
    });
}

function renderMetadata(metadata) {
    const entries = Object.entries(metadata || {});
    if (entries.length === 0) return '';
    return `
        <dl class="mt-3 grid grid-cols-1 md:grid-cols-2 gap-2">
            ${entries.map(([key, value]) => {
                const text = typeof value === 'object' ? JSON.stringify(value) : String(value);
                return `
                    <div class="rounded-lg bg-surface-container p-3 border border-outline-variant/20">
                        <dt class="font-label-sm text-outline">${escapeHtml(key)}</dt>
                        <dd class="font-body-sm text-on-surface break-words">${escapeHtml(text)}</dd>
                    </div>`;
            }).join('')}
        </dl>`;
}

function humanizeEventType(value) {
    const map = {
        ConversationStarted: 'Soru alındı',
        PatientProfileLoaded: 'Profil bilgileri hazırlandı',
        ConversationRouted: 'İstek doğru alana yönlendirildi',
        ClinicalPriorityResolved: 'Öncelikler kontrol edildi',
        NutritionOptionsGenerated: 'Öneri hazırlandı',
        RetrieverExecuted: 'Kaynaklar tarandı',
        RuleChecked: 'Güvenlik kuralı kontrol edildi',
        RuleTriggered: 'Riskli eşleşme durduruldu',
        RiskClassified: 'Risk seviyesi belirlendi',
        FinalAnswerGenerated: 'Yanıt hazırlandı',
        ClinicalDocumentationGenerated: 'Kayıt oluşturuldu',
        FastAnswerGenerated: 'Hızlı yanıt verildi',
        AIFallbackActivated: 'Güvenli yedek yanıt kullanıldı',
        InputGuardrailBlocked: 'Güvenlik sınırı devreye girdi',
    };
    return map[value] || 'Kontrol adımı';
}

function humanizeComponent(value) {
    const map = {
        'api.chat': 'CureBot',
        profile_context: 'Profil',
        supervisor: 'Yönlendirme',
        triage: 'Öncelik kontrolü',
        nutrition_capability: 'Beslenme önerisi',
        medication_safety: 'İlaç ve besin güvenliği',
        evidence_retrieval: 'Kaynak kontrolü',
        auditor: 'Güvenlik denetimi',
        chef_capability: 'Tarif hazırlama',
        conversation_capability: 'Sohbet',
        nemo_guardrails: 'Güvenlik sınırı',
    };
    return map[value] || 'CureMenu kontrolü';
}

function humanizeAction(value) {
    const map = {
        SOHBET: 'Bilgilendirici sohbet',
        SOHBET_FALLBACK: 'Güvenli yedek yanıt',
        SECENEK_SUN: 'Seçenek hazırlama',
        SECENEK_SUN_BITTI: 'Seçenek sunuldu',
        RAPORLANDI: 'Raporlandı',
        INPUT_GUARDRAIL_BLOCKED: 'Güvenlik nedeniyle durduruldu',
        APPROVE: 'Uygun göründü',
        REVIEW_REQUIRED: 'Dikkatli inceleme gerekli',
        REJECT: 'Uygun değil',
    };
    return map[value] || 'Kontrollü yanıt';
}

function renderDecisionTimeline(decision) {
    const events = decision.events || [];
    const versions = Object.entries(decision.component_versions || {});
    const citations = decision.citations || [];
    const confidence = decision.confidence_data || decision.confidence || {};
    const risk = Number(decision.risk_score || 0);
    const confidenceScore = Number(decision.confidence_score || 0);

    return `
        <div class="space-y-5">
            <section class="rounded-lg border border-outline-variant/20 bg-surface p-4">
                <div class="flex flex-col md:flex-row md:items-start justify-between gap-4">
                    <div class="min-w-0">
                        <p class="font-label-sm text-outline break-all">${escapeHtml(decision.decision_id || '')}</p>
                        <h4 class="font-headline-md text-on-surface mt-1">${escapeHtml(humanizeAction(decision.final_action))}</h4>
                        <p class="font-body-sm text-on-surface-variant mt-2">${escapeHtml(decision.istek || '')}</p>
                    </div>
                    <div class="flex flex-wrap gap-2">
                        <span class="px-3 py-1 rounded-full text-xs bg-error-container/30 text-error">Risk ${risk.toFixed(2)}</span>
                        <span class="px-3 py-1 rounded-full text-xs bg-primary-container/20 text-primary">Operasyonel güven ${confidenceScore.toFixed(2)}</span>
                        <span class="px-3 py-1 rounded-full text-xs bg-surface-container text-on-surface-variant">${escapeHtml(humanizeAction(confidence.action))}</span>
                    </div>
                </div>
                ${decision.final_answer ? `<div class="mt-4 rounded-lg bg-surface-container p-4 border border-outline-variant/20 font-body-sm text-on-surface-variant max-h-40 overflow-y-auto">${formatMarkdownSafe(decision.final_answer)}</div>` : ''}
            </section>

            <section class="grid grid-cols-1 lg:grid-cols-2 gap-4">
                <div class="rounded-lg border border-outline-variant/20 bg-surface p-4">
                    <h5 class="font-label-md text-on-surface mb-3">Sistem kaydı</h5>
                    ${versions.length ? versions.slice(0, 5).map(([key, value]) => `
                        <div class="flex items-center justify-between gap-3 border-b border-outline-variant/20 py-2 last:border-b-0">
                            <span class="font-body-sm text-on-surface-variant">${escapeHtml(humanizeComponent(key))}</span>
                            <span class="font-label-sm text-primary text-right break-all">${escapeHtml(String(value))}</span>
                        </div>`).join('') : '<p class="text-on-surface-variant">Versiyon kaydi yok.</p>'}
                </div>
                <div class="rounded-lg border border-outline-variant/20 bg-surface p-4">
                    <h5 class="font-label-md text-on-surface mb-3">Kaynak desteği</h5>
                    ${citations.length ? citations.map((citation) => `
                        <div class="rounded-lg bg-surface-container p-3 border border-outline-variant/20 mb-2">
                            <p class="font-label-sm text-primary">${escapeHtml(citation.title || citation.source_id || 'source')}</p>
                            <p class="font-body-sm text-on-surface-variant">${escapeHtml(citation.evidence_span || citation.chunk_id || '')}</p>
                        </div>`).join('') : '<p class="text-on-surface-variant">Bu yanıtta ek kaynak kaydı bulunmuyor.</p>'}
                </div>
            </section>

            <section class="rounded-lg border border-outline-variant/20 bg-surface p-4">
                <h5 class="font-label-md text-on-surface mb-4">Kontrol adımları</h5>
                ${events.length ? events.map((event) => `
                    <div class="relative pl-8 pb-5 last:pb-0">
                        <span class="absolute left-0 top-1 w-4 h-4 rounded-full ${event.status === 'blocked' ? 'bg-error' : 'bg-primary'}"></span>
                        <span class="absolute left-[7px] top-5 bottom-0 w-px bg-outline-variant/40 last:hidden"></span>
                        <div class="flex flex-col md:flex-row md:items-center justify-between gap-1">
                            <div>
                                <p class="font-label-md text-on-surface">${escapeHtml(humanizeEventType(event.event_type))}</p>
                                <p class="font-body-sm text-on-surface-variant">${escapeHtml(humanizeComponent(event.component))} · ${escapeHtml(event.status || 'ok')}</p>
                            </div>
                            <p class="font-label-sm text-outline">${escapeHtml(formatDecisionDate(event.created_at))}</p>
                        </div>
                        ${renderMetadata(event.metadata)}
                    </div>`).join('') : '<p class="text-on-surface-variant">Event kaydi yok.</p>'}
            </section>
        </div>`;
}

async function openDecisionTimeline(decisionId) {
    const modal = document.getElementById('decisionTimelineModal');
    const content = document.getElementById('decisionTimelineContent');
    if (!modal || !content || !decisionId) return;

    modal.classList.remove('hidden');
    content.innerHTML = '<p class="text-on-surface-variant">Karar adımları yükleniyor...</p>';
    try {
        const { res, data } = await safeFetchJson(API + `/api/clinical-decisions/${encodeURIComponent(decisionId)}`);
        if (!res.ok || !data?.success) {
            content.innerHTML = `<p class="text-error">${apiHataMesaji(data, 'Karar detayi alinamadi.')}</p>`;
            return;
        }
        content.innerHTML = renderDecisionTimeline(data.decision || {});
    } catch (e) {
        content.innerHTML = `<p class="text-error">${baglantiHatasi(e)}</p>`;
    }
}

function closeDecisionTimeline() {
    const modal = document.getElementById('decisionTimelineModal');
    if (modal) modal.classList.add('hidden');
}

window.openDecisionTimeline = openDecisionTimeline;
window.closeDecisionTimeline = closeDecisionTimeline;

async function loadClinicalKpis(reset = false) {
    const summary = document.getElementById('kpiSummaryGrid');
    if (summary && reset) {
        summary.innerHTML = '<div class="text-center py-16 text-on-surface-variant col-span-full"><div class="loading-dots flex gap-2 justify-center mb-4"><span class="w-3 h-3 rounded-full bg-primary inline-block"></span><span class="w-3 h-3 rounded-full bg-primary inline-block"></span><span class="w-3 h-3 rounded-full bg-primary inline-block"></span></div><p>İzlenebilirlik özeti yükleniyor...</p></div>';
    }
    try {
        const [{ res: kpiRes, data: kpiData }, { res: decisionRes, data: decisionData }] = await Promise.all([
            safeFetchJson(API + '/api/clinical-kpis'),
            safeFetchJson(API + '/api/clinical-decisions?limit=8'),
        ]);
        if (!kpiRes.ok || !kpiData?.success) throw new Error('Klinik özet alınamadı');
        const kpis = kpiData.kpis || {};
        if (summary) {
            summary.innerHTML = [
                renderKpiCard('Toplam karar', kpis.total_decisions || 0, 'fact_check'),
                renderKpiCard('Ortalama guven', Number(kpis.average_confidence || 0).toFixed(2), 'verified'),
                renderKpiCard('Yuksek risk orani', formatPercent(kpis.high_risk_rate), 'warning', Number(kpis.high_risk_rate || 0) > 0 ? 'error' : 'primary'),
                renderKpiCard('Kanit kapsami', formatPercent(kpis.evidence_coverage_rate), 'menu_book'),
            ].join('');
        }
        renderKpiEventBreakdown(kpis);
        if (decisionRes.ok && decisionData?.success) renderClinicalDecisions(decisionData.decisions || []);
        else renderClinicalDecisions([]);
    } catch (e) {
        if (summary) summary.innerHTML = `<div class="text-center py-12 text-error col-span-full">${baglantiHatasi(e)}</div>`;
        renderKpiEventBreakdown([]);
        renderClinicalDecisions([]);
    }
}
function emptyState(icon, title, text) {
    return `
        <div class="rounded-lg border border-outline-variant bg-surface-container-low p-5 text-center text-on-surface-variant">
            <span class="material-symbols-outlined mb-2 block text-4xl opacity-50">${icon}</span>
            <p class="font-bold text-on-surface">${escapeHtml(title)}</p>
            <p class="mt-1 text-sm">${escapeHtml(text)}</p>
        </div>`;
}

function scoreTone(value, reverse = false) {
    const score = Number(value || 0);
    if (reverse) {
        if (score >= 0.7) return 'status-risk';
        if (score >= 0.35) return 'status-warn';
        return 'status-ok';
    }
    if (score >= 0.75) return 'status-ok';
    if (score >= 0.45) return 'status-warn';
    return 'status-risk';
}

function renderDashboardMetrics(kpis = {}) {
    const root = document.getElementById('dashboardMetricGrid');
    if (!root) return;
    const items = [
        { label: 'Toplam karar', value: kpis.total_decisions || 0, icon: 'fact_check', desc: 'Kaydedilen izlenebilir öneri sayısı' },
        { label: 'Operasyonel güven', value: Number(kpis.average_confidence || 0).toFixed(2), icon: 'verified', desc: 'Karar kayıtlarındaki iç kontrol ortalaması' },
        { label: 'Tahmini risk', value: Number(kpis.average_risk || kpis.average_medical_risk || 0).toFixed(2), icon: 'health_and_safety', desc: 'İç kontrol kayıtlarından türetilir' },
        { label: 'Kaynak kaydı', value: formatPercent(kpis.evidence_coverage_rate), icon: 'menu_book', desc: 'Kaynak/citation bilgisi olan kayıtlar' },
    ];
    root.innerHTML = items.map(item => `
        <article class="card p-5">
            <div class="flex items-start justify-between gap-3">
                <div>
                    <p class="metric-label">${escapeHtml(item.label)}</p>
                    <p class="mt-2 font-display text-3xl font-extrabold text-on-surface">${escapeHtml(String(item.value))}</p>
                    <p class="mt-2 text-sm text-on-surface-variant">${escapeHtml(item.desc)}</p>
                </div>
                <span class="material-symbols-outlined rounded-lg bg-primary-container p-2 text-primary">${item.icon}</span>
            </div>
        </article>`).join('');
}

function renderDashboardDecision(decision) {
    const root = document.getElementById('dashboardLastDecision');
    if (!root) return;
    if (!decision) {
        root.innerHTML = emptyState('timeline', 'Henüz karar kaydı yok', 'CureBot veya plan araçlarını kullandığında burada son kayıt görünür.');
        return;
    }
    const risk = Number(decision.risk_score || 0);
    const confidence = Number(decision.confidence_score || 0);
    const decisionId = String(decision.decision_id || '').replace(/[^a-zA-Z0-9_-]/g, '');
    root.innerHTML = `
        <div class="space-y-3">
            <div>
                <p class="text-xs font-bold uppercase text-outline">Decision ID</p>
                <p class="break-all text-sm font-bold text-primary">${escapeHtml(decision.decision_id || '-')}</p>
            </div>
            <p class="line-clamp-3 text-sm text-on-surface">${escapeHtml(decision.istek || 'Son öneri kaydı')}</p>
            <div class="flex flex-wrap gap-2">
                <span class="status-pill ${scoreTone(risk, true)}">Risk ${risk.toFixed(2)}</span>
                <span class="status-pill ${scoreTone(confidence)}">Operasyonel güven ${confidence.toFixed(2)}</span>
            </div>
            ${decisionId ? `<button onclick="openDecisionTimeline('${decisionId}')" class="btn-secondary px-4 py-2 text-sm font-bold">Detayı gör</button>` : ''}
        </div>`;
}

function renderDailySummary(profile, kpis = {}, histories = []) {
    const root = document.getElementById('dailySummaryGrid');
    if (!root) return;
    const main = profile?.ana_kullanici;
    const meds = main?.ilaclar || [];
    const diseases = main?.hastaliklar || [];
    const allergies = main?.alerjiler || [];
    const lastLab = histories.find(log => String(log.eylem || '').toLowerCase().includes('tahlil'));
    const items = [
        {
            icon: 'person',
            title: 'Profil durumu',
            text: main ? `${main.ad || 'Ana profil'} için ${diseases.length} hastalık, ${allergies.length} alerji kaydı var.` : 'Profil tamamlanınca öneriler daha dikkatli olur.',
            tone: main ? 'status-ok' : 'status-warn'
        },
        {
            icon: 'medication',
            title: 'İlaç-besin dikkati',
            text: meds.length ? `${meds.length} ilaç kaydı önerilerde dikkate alınır.` : 'Kayıtlı ilaç yok. Varsa profil alanından ekleyebilirsin.',
            tone: meds.length ? 'status-info' : 'status-warn'
        },
        {
            icon: 'vaccines',
            title: 'Son tahlil durumu',
            text: lastLab ? `${formatDecisionDate(lastLab.tarih)} tarihinde tahlil özeti oluştu.` : 'Henüz yüklenmiş tahlil özeti bulunmuyor.',
            tone: lastLab ? 'status-ok' : 'status-info'
        },
        {
            icon: 'verified_user',
            title: 'İzlenebilirlik özeti',
            text: `${Number(kpis.average_confidence || 0).toFixed(2)} operasyonel güven, ${formatPercent(kpis.evidence_coverage_rate)} kaynak kaydı.`,
            tone: Number(kpis.total_decisions || 0) ? 'status-ok' : 'status-info'
        },
    ];
    root.innerHTML = items.map(item => `
        <article class="quiet-card p-4">
            <div class="mb-3 flex items-center justify-between gap-3">
                <span class="material-symbols-outlined text-primary">${item.icon}</span>
                <span class="status-pill ${item.tone}">Durum</span>
            </div>
            <h4 class="font-bold text-on-surface">${escapeHtml(item.title)}</h4>
            <p class="mt-1 text-sm leading-6 text-on-surface-variant">${escapeHtml(item.text)}</p>
        </article>`).join('');
}


async function loadDashboardOverview(reset = false) {
    if (reset) {
        const metricRoot = document.getElementById('dashboardMetricGrid');
        if (metricRoot) metricRoot.innerHTML = '<div class="card col-span-full p-6 text-on-surface-variant">Dashboard yükleniyor...</div>';
    }
    try {
        const [profileRes, kpiRes, decisionRes, historyRes] = await Promise.all([
            safeFetchJson(API + '/api/profile/me'),
            safeFetchJson(API + '/api/clinical-kpis'),
            safeFetchJson(API + '/api/clinical-decisions?limit=3'),
            safeFetchJson(API + '/api/history?page=1&limit=5'),
        ]);
        const profile = profileRes.data?.profil || null;
        const kpis = kpiRes.data?.kpis || {};
        const decisions = decisionRes.data?.decisions || [];
        const logs = historyRes.data?.loglar || [];
        renderDashboardMetrics(kpis);
        renderDashboardDecision(decisions[0]);
        renderDailySummary(profile, kpis, logs);
    } catch (e) {
        renderDashboardMetrics({});
        renderDashboardDecision(null);
    }
}

function renderHealthProfile(profil) {
    const root = document.getElementById('healthProfileSummary');
    if (root) root.remove(); // Remove the summary section as requested
}

function renderEmptyFamily() {
    const grid = document.getElementById('familyGrid');
    if (!grid) return;
    grid.innerHTML = emptyState('group_add', 'Henüz profil yok', 'İlk profil oluşturulduğunda veya aile üyesi eklendiğinde burada görünür.');
}

function renderFamily(profil) {
    const grid = document.getElementById('familyGrid');
    if (!grid) return;
    grid.innerHTML = '';
    const members = [];
    if (profil?.ana_kullanici) members.push({ ...profil.ana_kullanici, isMain: true });
    (profil?.aile_uyeleri || []).forEach(u => members.push({ ...u, isMain: false }));
    if (!members.length) {
        renderEmptyFamily();
        return;
    }

    grid.innerHTML = members.map(member => {
        const diseases = member.hastaliklar || [];
        const allergies = member.alerjiler || [];
        const meds = member.ilaclar || [];
        const memberId = escapeHtml(member.id || '');
        const isMain = member.isMain;
        return `
            <article class="rounded-xl border border-outline-variant bg-surface-container-low p-6 transition hover:border-primary">
                <div class="flex items-center justify-between">
                    <h4 class="font-display text-xl font-bold text-on-surface">${escapeHtml(member.ad || 'İsimsiz')}</h4>
                    <span class="rounded-full bg-primary-container px-3 py-1 text-xs font-bold text-primary">${isMain ? 'Ana Profil' : 'Aile Üyesi'}</span>
                </div>
                <div class="mt-4 grid gap-4">
                    <div><p class="metric-label font-bold">Hastalıklar</p><div class="mt-2 flex flex-wrap gap-2">${diseases.length ? diseases.map(v => `<span class="status-pill status-warn">${escapeHtml(v)}</span>`).join('') : '<span class="text-sm text-on-surface-variant">Kayıt yok</span>'}</div></div>
                    <div><p class="metric-label font-bold">Alerjiler</p><div class="mt-2 flex flex-wrap gap-2">${allergies.length ? allergies.map(v => `<span class="status-pill status-risk">${escapeHtml(v)}</span>`).join('') : '<span class="text-sm text-on-surface-variant">Kayıt yok</span>'}</div></div>
                    <div><p class="metric-label font-bold">İlaçlar</p><div class="mt-2 flex flex-wrap gap-2">${meds.length ? meds.map(v => `<span class="status-pill status-info">${escapeHtml(v)}</span>`).join('') : '<span class="text-sm text-on-surface-variant">Kayıt yok</span>'}</div></div>
                </div>
            </article>`;
    }).join('');
}

async function loadLabHistory() {
    const root = document.getElementById('labHistoryList');
    if (!root) return;
    root.innerHTML = '<p class="text-on-surface-variant">Tahlil geçmişi yükleniyor...</p>';
    try {
        const { res, data } = await safeFetchJson(API + '/api/history?page=1&limit=50');
        if (!res.ok || !data?.success) throw new Error('history');
        
        const labs = (data.loglar || []).filter(log => String(log.eylem || '').toLowerCase().includes('tahlil'));
        
        // Draw Chart
        drawTahlilChart(labs);

        if (!labs.length) {
            root.innerHTML = emptyState('vaccines', 'Yüklenen tahlil yok', 'PDF yüklediğinde özet burada görünür. Biyomarker listesi otomatik çekilerek grafiğe yansır.');
            return;
        }
        root.innerHTML = labs.map((log, index) => {
            const summaryId = `lab-summary-${index}`;
            return `
            <article class="rounded-lg border border-outline-variant bg-surface overflow-hidden">
                <button onclick="document.getElementById('${summaryId}').classList.toggle('hidden')" class="w-full flex items-center justify-between p-4 hover:bg-surface-container-low transition-colors text-left">
                    <div class="flex items-center gap-3">
                        <span class="material-symbols-outlined rounded-lg bg-primary-container p-2 text-primary">description</span>
                        <div>
                            <p class="font-bold text-on-surface">${escapeHtml(log.kullanici_girdisi || 'Tahlil Raporu')}</p>
                            <p class="text-xs text-on-surface-variant mt-0.5">
                                <span class="font-medium text-primary">${escapeHtml(log.kullanici_adi || 'Kendim')} İçin</span> • 
                                ${escapeHtml(formatDecisionDate(log.tarih))}
                            </p>
                        </div>
                    </div>
                    <span class="material-symbols-outlined text-outline-variant">expand_more</span>
                </button>
                <div id="${summaryId}" class="hidden border-t border-outline-variant/30 bg-surface-container-lowest p-4 text-sm text-on-surface-variant leading-relaxed">
                    ${formatMarkdownSafe(log.asistan_ciktisi || log.ai_yanit || 'Özet kaydı bulunamadı.')}
                </div>
            </article>`;
        }).join('');
    } catch (e) {
        root.innerHTML = emptyState('error', 'Tahlil geçmişi alınamadı', 'Bağlantı kurulamadı. Birazdan tekrar deneyebilirsin.');
    }
}

let tahlilChartInstance = null;
function drawTahlilChart(labs) {
    const ctx = document.getElementById('tahlilChart');
    if (!ctx) return;
    
    // Yalnızca metadata barındıran lab'leri eski tarihten yeni tarihe sırala
    const validLabs = labs
        .filter(l => l.metadata)
        .sort((a, b) => new Date(a.tarih) - new Date(b.tarih));
        
    const biomarkerMap = {};
    const dates = validLabs.map(l => formatDecisionDate(l.tarih).split(' ')[0]);

    validLabs.forEach((log, index) => {
        try {
            const parsed = JSON.parse(log.metadata);
            if (parsed.biomarkers && Array.isArray(parsed.biomarkers)) {
                parsed.biomarkers.forEach(b => {
                    const name = b.name.toUpperCase();
                    if (!biomarkerMap[name]) biomarkerMap[name] = new Array(validLabs.length).fill(null);
                    biomarkerMap[name][index] = parseFloat(b.value);
                });
            }
        } catch(e) {}
    });

    const datasets = Object.keys(biomarkerMap).map((key, i) => {
        const hue = (i * 137.508) % 360; 
        return {
            label: key,
            data: biomarkerMap[key],
            borderColor: `hsl(${hue}, 70%, 40%)`,
            backgroundColor: `hsl(${hue}, 70%, 40%, 0.1)`,
            tension: 0.3,
            spanGaps: true
        };
    });

    if (tahlilChartInstance) {
        tahlilChartInstance.destroy();
    }
    
    if (datasets.length === 0) {
        ctx.style.display = 'none';
        ctx.parentElement.insertAdjacentHTML('afterbegin', '<div id="noChartData" class="absolute inset-0 grid place-items-center text-sm text-on-surface-variant font-medium">Grafik çizilebilecek sayısal veri (biyomarker) bulunamadı. Lütfen kantitatif sonuçları olan yeni bir PDF yükleyin.</div>');
        return;
    } else {
        ctx.style.display = 'block';
        const emptyStateEl = document.getElementById('noChartData');
        if (emptyStateEl) emptyStateEl.remove();
    }

    tahlilChartInstance = new Chart(ctx, {
        type: 'line',
        data: {
            labels: dates,
            datasets: datasets
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: { position: 'right' }
            },
            scales: {
                y: { beginAtZero: false }
            }
        }
    });
}

function updateChatGovernancePanel(data) {
    const root = document.getElementById('chatGovernancePanel');
    if (!root) return;
    if (!data) {
        root.innerHTML = `
            <div class="rounded-lg border border-outline-variant bg-surface-container-low p-4">
                <p class="font-bold text-on-surface">Yanıt bekleniyor</p>
                <p class="mt-1 text-sm text-on-surface-variant">CureBot yanıt verdiğinde karar kaydı, operasyonel güven ve tahmini risk özeti burada görünür.</p>
            </div>`;
        return;
    }
    const decisionId = String(data.decision_id || '').replace(/[^a-zA-Z0-9_-]/g, '');
    const risk = Number(data.risk_score || 0);
    const confidence = Number(data.confidence_score || 0);
    root.innerHTML = `
        <div class="space-y-4">
            <div>
                <p class="text-xs font-bold uppercase text-outline">Decision ID</p>
                <p class="break-all text-sm font-bold text-primary">${escapeHtml(data.decision_id || '-')}</p>
            </div>
            <div class="grid grid-cols-2 gap-3">
                <div class="rounded-lg border border-outline-variant bg-surface p-3">
                    <p class="metric-label">Operasyonel güven</p>
                    <p class="mt-1 font-display text-2xl font-bold">${confidence.toFixed(2)}</p>
                </div>
                <div class="rounded-lg border border-outline-variant bg-surface p-3">
                    <p class="metric-label">Risk</p>
                    <p class="mt-1 font-display text-2xl font-bold">${risk.toFixed(2)}</p>
                </div>
            </div>
            <p class="rounded-lg border border-warning/20 bg-warning-container p-3 text-sm text-on-surface-variant">Bu yanıt tedavi yerine geçmez. Yüksek risk, yeni belirti veya ilaç değişikliği varsa sağlık profesyoneline danış.</p>
            <div id="chatGovernanceCitations" class="rounded-lg border border-outline-variant bg-surface-container-low p-3 text-sm text-on-surface-variant">Kaynak bilgisi kontrol ediliyor...</div>
            ${decisionId ? `<button onclick="openDecisionTimeline('${decisionId}')" class="btn-secondary px-4 py-2 text-sm font-bold">Olay zincirini gör</button>` : ''}
        </div>`;
    if (decisionId) hydrateChatGovernanceDetails(decisionId);
}

async function hydrateChatGovernanceDetails(decisionId) {
    const root = document.getElementById('chatGovernanceCitations');
    if (!root) return;
    try {
        const { res, data } = await safeFetchJson(API + `/api/clinical-decisions/${encodeURIComponent(decisionId)}`);
        if (!res.ok || !data?.success) throw new Error('decision');
        const citations = data.decision?.citations || [];
        if (!citations.length) {
            root.innerHTML = 'Bu yanıtta ayrı kaynak kaydı bulunmuyor.';
            return;
        }
        root.innerHTML = `
            <p class="mb-2 font-bold text-on-surface">Kullanılan kaynaklar</p>
            <div class="space-y-2">
                ${citations.slice(0, 3).map(citation => `
                    <div class="rounded-lg border border-outline-variant bg-white p-3">
                        <p class="font-bold text-primary">${escapeHtml(citation.title || citation.source_id || 'Kaynak')}</p>
                        <p class="mt-1 text-xs text-on-surface-variant">${escapeHtml(citation.evidence_span || citation.chunk_id || '')}</p>
                    </div>`).join('')}
            </div>`;
    } catch (e) {
        root.innerHTML = 'Kaynak bilgisi alınamadı.';
    }
}

function switchTab(tab) {
    const tabContent = document.getElementById('tab-' + tab);
    if (!tabContent) {
        if (tab === 'curebot') openCureBotWidget();
        return;
    }

    document.querySelectorAll('.tab-content').forEach(el => el.classList.remove('active'));
    document.querySelectorAll('.tab-btn').forEach(el => {
        el.classList.remove('active');
        el.classList.add('text-on-surface-variant');
    });
    document.querySelectorAll('.mobile-tab-btn').forEach(el => {
        el.classList.remove('text-primary');
        el.classList.add('text-on-surface-variant');
    });
    tabContent.classList.add('active');

    const titles = {
        dashboard: 'Dashboard',
        curebot: 'CureBot',
        profile: 'Sağlık Profilim',
        meds: 'İlaçlarım',
        plan: 'Haftalık Plan',
        tarayici: 'Menü Analizi',
        buzdolabi: 'Buzdolabı',
        gecmis: 'Geçmiş',
        tahlil: 'Tahlillerim',
        governance: 'İzlenebilirlik'
    };
    const subtitles = {
        dashboard: 'Kanıta dayalı öneri, güvenlik kontrolü ve izlenebilir karar kaydı.',
        curebot: 'Yanıtla birlikte operasyonel güven, tahmini risk ve kaynak özetini takip et.',
        profile: 'Hastalık, alerji, ilaç ve hedef bilgilerini yönet.',
        meds: 'Kayıtlı ilaçlar ve riskli etkileşim sinyalleri.',
        governance: 'Denetim, teknik inceleme ve yatırımcı sunumu için karar kayıtları.'
    };
    const pageTitle = document.getElementById('pageTitle');
    if (pageTitle) pageTitle.textContent = titles[tab] || '';
    const subtitle = document.getElementById('pageSubtitle');
    if (subtitle) subtitle.textContent = subtitles[tab] || 'CureMenu klinik beslenme karar destek konsolu.';

    const navLink = document.querySelector(`#sideNav .tab-btn[data-tab="${tab}"]`);
    if (navLink) {
        navLink.classList.add('active');
        navLink.classList.remove('text-on-surface-variant');
    }
    const mobileBtn = document.querySelector(`.mobile-tab-btn[data-tab="${tab}"]`);
    if (mobileBtn) {
        mobileBtn.classList.add('text-primary');
        mobileBtn.classList.remove('text-on-surface-variant');
    }

    if (tab === 'dashboard') {
        loadDashboardOverview(true);
    } else if (tab === 'gecmis') {
        loadHistory(true);
    } else if (tab === 'governance') {
        loadClinicalKpis(true);
    } else if (tab === 'tahlil') {
        loadLabHistory();
    } else if (tab === 'plan') {
        const savedPlan = localStorage.getItem('cm_saved_plan');
        if (savedPlan) renderSavedPlan(savedPlan);
    }
}

let currentHistoryPage = 1;
const HISTORY_LIMIT = 10;

async function loadHistory(reset = false) {
    const user = getUser();
    if (!user.telefon) return;
    
    if (reset) {
        currentHistoryPage = 1;
        const grid = document.getElementById('historyGrid');
        if(grid) grid.innerHTML = '<div class="text-center py-20 text-on-surface-variant"><div class="loading-dots flex gap-2 justify-center mb-4"><span class="w-3 h-3 rounded-full bg-secondary inline-block"></span><span class="w-3 h-3 rounded-full bg-secondary inline-block"></span><span class="w-3 h-3 rounded-full bg-secondary inline-block"></span></div><p>Geçmiş yükleniyor...</p></div>';
        const page = document.getElementById('historyPagination');
        if(page) page.classList.add('hidden');
    }
    
    try {
        const { res, data } = await safeFetchJson(`${API}/api/history?page=${currentHistoryPage}&limit=${HISTORY_LIMIT}`);
        if (!res.ok || !data?.success) {
            const grid = document.getElementById('historyGrid');
            if (grid && reset) grid.innerHTML = `<div class="text-center py-12 text-error">${apiHataMesaji(data, 'Geçmiş yüklenemedi.')}</div>`;
            return;
        }
        const grid = document.getElementById('historyGrid');
        if (reset && grid) grid.innerHTML = '';
        
        const loglar = data.loglar || [];
        if (loglar.length === 0 && reset && grid) {
            grid.innerHTML = `
                <div class="text-center py-20 text-on-surface-variant">
                    <span class="material-symbols-outlined text-6xl mb-4 block opacity-30">history</span>
                    <p>Henüz geçmiş işleminiz bulunmuyor.</p>
                </div>`;
            return;
        }
        
        loglar.forEach(log => {
            const date = new Date(log.tarih);
            const formattedDate = date.toLocaleDateString('tr-TR', { day: 'numeric', month: 'long', hour: '2-digit', minute:'2-digit' });
            
            let icon = 'history';
            let bg = 'bg-surface-container-low';
            const title = log.eylem || 'İşlem';
            
            if (title.includes('Buzdolabı')) { icon = 'kitchen'; bg = 'bg-primary-container/10'; }
            else if (title.includes('QR Menü')) { icon = 'document_scanner'; bg = 'bg-secondary-container/10'; }
            else if (title.includes('CureBot')) { icon = 'smart_toy'; bg = 'bg-surface-variant/30'; }
            else if (title.includes('Haftalık Plan')) { icon = 'restaurant_menu'; bg = 'bg-primary-container/5'; }
            
            const assistantOutput = log.asistan_ciktisi || log.ai_yanit || '';
            const responseHtml = assistantOutput ? `<div class="mt-4 p-4 bg-surface rounded-lg border border-outline-variant/20 text-sm text-on-surface-variant max-h-[150px] overflow-y-auto chat-scroll">${formatMarkdownSafe(assistantOutput)}</div>` : '';
            
            if(grid) {
                grid.innerHTML += `
                    <article class="bg-surface-container-lowest rounded-lg p-6 shadow-sm border border-outline-variant/20 flex flex-col md:flex-row gap-4">
                        <div class="w-12 h-12 rounded-full ${bg} flex items-center justify-center flex-shrink-0 text-primary">
                            <span class="material-symbols-outlined">${icon}</span>
                        </div>
                        <div class="flex-1 min-w-0">
                            <div class="flex justify-between items-start mb-2">
                                <div>
                                    <h3 class="font-headline-md text-[18px] font-semibold text-on-surface">${escapeHtml(title)}</h3>
                                    <p class="font-label-sm text-outline">${formattedDate}${log.kullanici_adi ? ' · ' + escapeHtml(log.kullanici_adi) : ''}</p>
                                </div>
                            </div>
                            <p class="font-body-sm text-on-surface line-clamp-2 mt-2"><strong>Girdi:</strong> ${escapeHtml(log.kullanici_girdisi || 'Sistem isteği')}</p>
                            ${responseHtml}
                        </div>
                    </article>
                `;
            }
        });
        
        const pagination = document.getElementById('historyPagination');
        if (pagination) {
            if (data.has_more) pagination.classList.remove('hidden');
            else pagination.classList.add('hidden');
        }
    } catch (e) {
        console.error("Geçmiş yüklenirken hata:", e);
        const grid = document.getElementById('historyGrid');
        if (grid && reset) grid.innerHTML = `<div class="text-center py-12 text-error">${baglantiHatasi(e)}</div>`;
    }
}

function loadMoreHistory() {
    currentHistoryPage += 1;
    loadHistory(false);
}

async function scanFridge(imageBase64) {
    const kimin_icin = document.getElementById('fridgeTarget')?.value || 'kendim';
    const result = document.getElementById('fridgeScanResult');
    const inputEl = document.getElementById('fridgeImageInput');
    if (inputEl) inputEl.value = '';
    if (!result) return;

    result.innerHTML = `<div class="card p-8 text-center text-on-surface-variant"><div class="loading-dots text-primary text-4xl mb-3"><span>.</span><span>.</span><span>.</span></div><p>Buzdolabı fotoğrafını inceliyorum. Malzemeleri okuyup sana uygun bir fikir hazırlayacağım.</p></div>`;

    try {
        const { res, data } = await safeFetchJson(API + '/api/fridge-scan', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ kimin_icin, image_base64: imageBase64 })
        });

        if (!res.ok || !data?.success) {
            result.innerHTML = `<div class="card border-error-container bg-error-container p-6 text-center text-on-error-container"><p>${apiHataMesaji(data, 'Fotoğraftaki malzemeler okunamadı. Daha net ışıkta, ürünleri kadraja alarak tekrar deneyebilirsin.')}</p></div>`;
            return;
        }

        const malzemeler = data.malzemeler || data.analiz?.bulunan_malzemeler || data.sonuc?.bulunan_malzemeler || '';
        const tarif = data.tarif || data.analiz?.tarif_metni || data.sonuc?.tarif_metni || data.analiz?.uyari_mesaji || '';
        result.innerHTML = `
            <div class="grid gap-5 xl:grid-cols-[360px_minmax(0,1fr)]">
                <section class="card p-5">
                    <div class="mb-3 flex items-center gap-2 text-primary"><span class="material-symbols-outlined">kitchen</span><h3 class="font-display text-xl font-bold">Gördüğüm malzemeler</h3></div>
                    <p class="leading-7 text-on-surface-variant">${malzemeler ? escapeHtml(malzemeler) : 'Malzeme listesi ayrıca dönmedi.'}</p>
                </section>
                <section class="card p-5">
                    <div class="mb-3 flex items-center gap-2 text-primary"><span class="material-symbols-outlined">restaurant</span><h3 class="font-display text-xl font-bold">Tarif önerisi</h3></div>
                    <div class="prose prose-sm max-w-none text-on-surface">${tarif ? formatMarkdownSafe(tarif) : 'Tarif oluşturulamadı. Fotoğrafı yeniden yükleyebilirsin.'}</div>
                </section>
            </div>`;
    } catch (e) {
        result.innerHTML = `<div class="card border-error-container bg-error-container p-6 text-center text-on-error-container"><p>${baglantiHatasi(e)}</p></div>`;
    }
}

function renderMedicationOverview(profil) {
    const listRoot = document.getElementById('medicationList');
    const riskRoot = document.getElementById('medicationRiskPanel');
    if (!listRoot && !riskRoot) return;

    const members = [];
    if (profil?.ana_kullanici) members.push({ ...profil.ana_kullanici, scope: 'Ana profil' });
    (profil?.aile_uyeleri || []).forEach(member => members.push({ ...member, scope: 'Aile profili' }));
    const rows = members.flatMap(member => (member.ilaclar || []).map(ilac => ({ ilac, member })));

    if (listRoot) {
        listRoot.innerHTML = rows.length
            ? rows.map(row => `
                <article class="rounded-lg border border-outline-variant bg-surface-container-low p-4">
                    <p class="font-bold text-on-surface">${escapeHtml(row.ilac)}</p>
                    <p class="mt-1 text-sm text-on-surface-variant">${escapeHtml(row.member.ad || row.member.scope)} · ${escapeHtml(row.member.scope)}</p>
                </article>`).join('')
            : emptyState('medication', 'Kayıtlı ilaç yok', 'İlaç eklediğinde yemek önerileri buna göre daha dikkatli kontrol edilir.');
    }

    if (riskRoot) {
        riskRoot.innerHTML = `
            <div class="rounded-lg border border-outline-variant bg-surface-container-low p-4">
                <p class="font-bold text-on-surface">Dikkat edilmesi gereken eşleşmeler</p>
                <p class="mt-1 text-sm leading-6 text-on-surface-variant">İlaçlarınla birlikte sakıncalı olabilecek bir yiyecek fark edilirse burada sade bir uyarı olarak görünür.</p>
            </div>
            <div class="rounded-lg border border-outline-variant bg-surface-container-low p-4">
                <p class="font-bold text-on-surface">Kaynaklı açıklamalar</p>
                <p class="mt-1 text-sm leading-6 text-on-surface-variant">Bir öneri kaynak bilgisiyle desteklenirse detayını karar geçmişinde görebilirsin. Veri yoksa CureMenu bunu varmış gibi göstermez.</p>
            </div>`;
    }
}

// -- Global TTS Cancellation / Ekrana Dokunarak Sesi Susturma --
// Cancel active speech synthesis upon document click / Sayfaya tıklandığında aktif seslendirmeyi durdur
document.addEventListener('click', function(e) {
    // Exclude mic button as it has internal cancellation logic / Mikrofon butonu kendi mantığına sahip olduğu için hariç tutulur
    if (!e.target.closest('#micBtn') && 'speechSynthesis' in window && window.speechSynthesis.speaking) {
        window.speechSynthesis.cancel();
    }
});

// -- Haftalık Plan Etkileşim ve Oyunlaştırma Fonksiyonları --

window.recalculateGamification = function() {
    const tableRows = document.querySelectorAll('#planResult tr');
    let totalScore = 0;
    let totalCompletedDays = 0;
    
    tableRows.forEach(row => {
        const checkboxes = row.querySelectorAll('input[type="checkbox"]');
        if (checkboxes.length === 0) return;
        
        let checkedCount = 0;
        checkboxes.forEach(cb => {
            if (cb.checked) {
                checkedCount++;
                totalScore += 10;
            }
        });
        
        // Günün tüm öğünleri tamamlandıysa (+30 puana ek olarak +20 tamamlama bonusu ve +1 Seri)
        if (checkedCount > 0 && checkedCount === checkboxes.length) {
            totalCompletedDays += 1;
            totalScore += 20;
        }
        
        // Eğer tablodaki o günün ismini gösteren ilk hücre varsa altına "0/3" gibi ufak bir metin ekleyelim
        const dayCell = row.querySelector('td:first-child');
        if (dayCell) {
            let progressSpan = dayCell.querySelector('.day-progress');
            if (!progressSpan) {
                progressSpan = document.createElement('div');
                progressSpan.className = "day-progress text-[11px] font-bold mt-2 py-1 px-2 rounded " + (checkedCount === checkboxes.length ? "bg-success/20 text-success" : "bg-outline-variant/20 text-on-surface-variant");
                dayCell.appendChild(progressSpan);
            } else {
                progressSpan.className = "day-progress text-[11px] font-bold mt-2 py-1 px-2 rounded " + (checkedCount === checkboxes.length ? "bg-success/20 text-success" : "bg-outline-variant/20 text-on-surface-variant");
            }
            progressSpan.textContent = `Durum: ${checkedCount}/${checkboxes.length}`;
        }
    });
    
    const uiScore = document.getElementById('uiMealScore');
    const uiStreak = document.getElementById('uiMealStreak');
    if (uiScore) uiScore.textContent = totalScore;
    if (uiStreak) uiStreak.textContent = totalCompletedDays;
};

window.toggleMealCheck = function(checkboxElement, mealText) {
    const cellId = checkboxElement.id;
    const tdElement = document.querySelector(`[data-cell-id="${cellId}"]`);
    
    if (checkboxElement.checked) {
        localStorage.setItem('cm_check_' + cellId, 'true');
        if (tdElement) tdElement.classList.add('opacity-60', 'bg-surface-container-high');
        triggerConfetti(checkboxElement);
    } else {
        localStorage.removeItem('cm_check_' + cellId);
        if (tdElement) tdElement.classList.remove('opacity-60', 'bg-surface-container-high');
    }
    
    recalculateGamification();
};

window.requestSnack = async function() {
    const today = new Date().toLocaleDateString('tr-TR', { weekday: 'long' });
    const modal = document.getElementById('actionModal');
    const title = document.getElementById('actionModalTitle');
    const subtitle = document.getElementById('actionModalSubtitle');
    const content = document.getElementById('actionModalContent');
    
    if (!modal) return;
    
    title.innerHTML = '<span class="material-symbols-outlined align-middle mr-2 text-warning">nutrition</span> Atıştırmalık Önerisi Aranıyor...';
    subtitle.textContent = `Bugün günlerden ${today}. Günlük planınıza uygun, sağlıklı ve lezzetli atıştırmalıklar taranıyor.`;
    content.innerHTML = `<div class="py-12 text-center"><div class="loading-dots flex gap-2 justify-center mb-4"><span class="w-3 h-3 rounded-full bg-warning inline-block"></span><span class="w-3 h-3 rounded-full bg-warning inline-block"></span><span class="w-3 h-3 rounded-full bg-warning inline-block"></span></div><p class="text-on-surface-variant font-body-md">Profilinize ve tahlillerinize uygun tarifler düşünülüyor...</p></div>`;
    modal.classList.remove('hidden');
    
    try {
        const { res, data } = await safeFetchJson(API + '/api/plan-action', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ action_type: 'snack', meal_text: "Snack Request", plan_text: window.currentPlanText || 'Henüz plan oluşturulmadı.' })
        });
        
        if (data && data.success && data.result) {
            const oneriler = data.result.snack_onerileri || "Özel atıştırmalık önerisi bulunamadı.";
            
            title.innerHTML = '<span class="material-symbols-outlined align-middle mr-2 text-success">check_circle</span> Atıştırmalıklarınız Hazır!';
            subtitle.textContent = `Profilinize uygun sağlıklı alternatifler bulundu.`;
            content.innerHTML = `
                <div class="bg-surface-container-low border border-outline-variant p-5 rounded-xl mb-4">
                    <div class="prose prose-sm md:prose-base max-w-none text-on-surface">${formatMarkdownSafe(oneriler)}</div>
                </div>
                <p class="text-sm text-on-surface-variant">Afiyet olsun! Bu öneriler haftalık planınızı bozmayacak şekilde özel olarak dengelenmiştir.</p>
            `;
        } else {
            throw new Error(data?.detail || "Sunucu yanıt vermedi.");
        }
    } catch (err) {
        title.innerHTML = '<span class="material-symbols-outlined align-middle mr-2 text-error">error</span> Alternatif Bulunamadı';
        subtitle.textContent = "Beklenmeyen bir hata oluştu.";
        content.innerHTML = `<div class="py-12 text-center text-error"><span class="material-symbols-outlined text-4xl mb-2">warning</span><p>${err.message}</p></div>`;
    }
};

window.requestAlternativeMeal = async function(mealText) {
    const modal = document.getElementById('actionModal');
    const title = document.getElementById('actionModalTitle');
    const subtitle = document.getElementById('actionModalSubtitle');
    const content = document.getElementById('actionModalContent');
    
    if (!modal) return;
    
    title.innerHTML = '<span class="material-symbols-outlined align-middle mr-2 text-warning">swap_horiz</span> Alternatif Aranıyor...';
    subtitle.textContent = `"${mealText}" yerine size daha uygun bir öğün bakılıyor.`;
    content.innerHTML = `<div class="py-12 text-center"><div class="loading-dots flex gap-2 justify-center mb-4"><span class="w-3 h-3 rounded-full bg-warning inline-block"></span><span class="w-3 h-3 rounded-full bg-warning inline-block"></span><span class="w-3 h-3 rounded-full bg-warning inline-block"></span></div><p class="text-on-surface-variant font-body-md">Profilinize ve alerjilerinize uygun alternatif düşünülüyor...</p></div>`;
    modal.classList.remove('hidden');
    
    try {
        const { res, data } = await safeFetchJson(API + '/api/plan-action', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ action_type: 'alternative', meal_text: mealText, plan_text: window.currentPlanText || '' })
        });
        
        if (data && data.success && data.result) {
            const degisenOgunler = data.result.degisen_ogunler || [];
            const aciklama = data.result.aciklama || "";
            
            // Eğer yeni JSON formatı yoksa, eski formata göre fallback yapalım
            if (degisenOgunler.length === 0 && data.result.yeni_ogun) {
                degisenOgunler.push({
                    "eski": mealText,
                    "yeni": data.result.yeni_ogun
                });
            }
            
            title.innerHTML = '<span class="material-symbols-outlined align-middle mr-2 text-success">check_circle</span> Plan Güncellendi!';
            subtitle.textContent = `Plandaki yemeğiniz ve makro dengeniz başarıyla ayarlandı.`;
            
            let ogunlerHtml = '';
            degisenOgunler.forEach(item => {
                ogunlerHtml += `<div class="mb-3 border-b border-success/10 pb-3 last:border-0 last:pb-0">
                    <p class="text-xs text-on-surface-variant line-through mb-1">${escapeHtml(item.eski)}</p>
                    <h4 class="font-bold text-success text-[15px]">${escapeHtml(item.yeni)}</h4>
                </div>`;
            });

            content.innerHTML = `
                <div class="bg-success-container/30 border border-success/20 p-5 rounded-xl mb-4">
                    <h4 class="font-bold text-success text-sm mb-3 opacity-80 uppercase tracking-wider">Değişen Öğünler</h4>
                    ${ogunlerHtml}
                    <div class="mt-4 pt-4 border-t border-success/20 prose prose-sm max-w-none text-on-surface">${formatMarkdownSafe(aciklama)}</div>
                </div>
                <p class="text-sm text-on-surface-variant">Arka planda haftalık plan tablonuz güncellendi. Sayfayı yenileseniz de bu öğünler kalacaktır.</p>
            `;
            
            // Tabloyu ve localStorage'i güncelle
            if (window.currentPlanText) {
                let newPlanText = window.currentPlanText;
                
                degisenOgunler.forEach(item => {
                    if (item.eski && item.yeni) {
                        // Sadece exact string'i değiştir
                        newPlanText = newPlanText.replace(item.eski, item.yeni);
                    }
                });
                
                window.currentPlanText = newPlanText;
                
                const user = getUser();
                if (user) {
                    localStorage.setItem('cm_saved_plan_' + user.telefon, newPlanText);
                }
                
                // UI'ı yeniden çiz
                renderSavedPlan(newPlanText);
            }
        } else {
            content.innerHTML = `<div class="p-6 text-center text-error font-bold">Alternatif bulunamadı: ${escapeHtml(data?.detail || 'Bilinmeyen hata')}</div>`;
        }
    } catch (e) {
        content.innerHTML = `<div class="p-6 text-center text-error font-bold">Bağlantı hatası oluştu.</div>`;
    }
};

window.closeActionModal = function() {
    document.getElementById('actionModal')?.classList.add('hidden');
};

function triggerConfetti(element) {
    // Sadece minik bir CSS tabanlı feedback
    const particle = document.createElement('div');
    particle.className = "absolute text-[24px] pointer-events-none transition-all duration-700 ease-out z-50";
    particle.textContent = "✨";
    
    const rect = element.getBoundingClientRect();
    particle.style.left = rect.left + window.scrollX + "px";
    particle.style.top = rect.top + window.scrollY - 20 + "px";
    
    document.body.appendChild(particle);
    
    setTimeout(() => {
        particle.style.transform = "translateY(-40px) scale(1.5)";
        particle.style.opacity = "0";
    }, 50);
    
    setTimeout(() => {
        particle.remove();
    }, 750);
}
