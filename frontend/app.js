/**
 * CureMenu - Frontend JavaScript
 * API bağlantıları ve sayfa mantığı.
 */

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
window.publicMetinler = window.publicMetinler || null;

async function loadPublicMetinler() {
    if (window.publicMetinler) return window.publicMetinler;
    try {
        const res = await fetch((window.API || '') + '/api/public/metinler');
        window.publicMetinler = await res.json();
    } catch (e) {
        window.publicMetinler = {
            tibbi_feragat_kisa: 'Tedavi yerine geçmez · Doktorunuza danışın',
            ornek_sorular: ['Bugün ne yesem?', 'Diyabetime uygun akşam yemeği öner'],
            yaygin_ilaclar: ILAC_SECENEKLERI_FALLBACK,
        };
    }
    const disc = document.getElementById('chatDisclaimer');
    if (disc && window.publicMetinler.tibbi_feragat_kisa) disc.textContent = window.publicMetinler.tibbi_feragat_kisa;
    return window.publicMetinler;
}

function initApp() {
    const user = window.AuthManager.requireAuth();
    if (!user) return; // requireAuth handles the redirect

    window.WeeklyPlanManager?.init?.();

    document.getElementById('sidebarUser').textContent = user.kullanici_adi;
    document.getElementById('sidebarPhone').textContent = user.telefon;
    loadPublicMetinler();
    loadProfile().then(() => {
        checkOnboarding();
        loadDashboardOverview(true);
        loadLabHistory();
    });
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
    return window.ProfileManager?.loadProfile?.();
}

async function checkOnboarding() {
    return window.ProfileManager?.checkOnboarding?.();
}

window.loadProfile = loadProfile;
window.checkOnboarding = checkOnboarding;
// -- Haftalık Plan --
// Legacy weekly plan implementation removed; see frontend/modules/weekly-plan-manager.js.
// Weekly plan rendering/generation lives in frontend/modules/weekly-plan-manager.js.
// Keep these globals as compatibility wrappers for older inline callers.
function renderSavedPlan(planValue) {
    if (!window.WeeklyPlanManager) return;
    try {
        const plan = typeof planValue === 'string' ? JSON.parse(planValue) : planValue;
        if (plan && plan.days) {
            window.WeeklyPlanManager.renderPlan(plan);
            return;
        }
    } catch (_e) {
        // Legacy markdown plans are no longer rendered by app.js.
    }
    window.WeeklyPlanManager.renderEmptyState?.();
}

async function openSmartGrocery() {
    return window.SmartGrocery?.openSmartGrocery?.();
}

async function calculateBudget() {
    return window.SmartGrocery?.calculateBudget?.();
}

window.openSmartGrocery = openSmartGrocery;
window.calculateBudget = calculateBudget;
// -- Menü Tarayıcı --
async function loadLabHistory() {
    return window.LabUpload?.loadLabHistory?.();
}

async function loadHistory(reset = false) {
    return window.LabUpload?.loadHistory?.(reset);
}

window.loadLabHistory = loadLabHistory;
window.loadHistory = loadHistory;
// -- Geçmiş İşlemlerim (History) --
async function openDecisionTimeline(decisionId) {
    return window.GovernanceDashboard?.openDecisionTimeline?.(decisionId);
}

async function loadClinicalKpis(reset = false) {
    return window.GovernanceDashboard?.loadClinicalKpis?.(reset);
}

function emptyState(icon, title, text) {
    return window.UIUtils?.emptyState?.(icon, title, text) || window.GovernanceDashboard?.emptyState?.(icon, title, text) || '';
}

async function loadDashboardOverview(reset = false) {
    return window.GovernanceDashboard?.loadDashboardOverview?.(reset);
}

function formatDecisionDate(value) {
    return window.UIUtils?.formatDecisionDate?.(value) || window.GovernanceDashboard?.formatDecisionDate?.(value) || String(value || '-');
}

window.loadClinicalKpis = loadClinicalKpis;
window.openDecisionTimeline = openDecisionTimeline;
window.loadDashboardOverview = loadDashboardOverview;
window.emptyState = emptyState;
window.formatDecisionDate = formatDecisionDate;
function renderChatGovernanceSummary(data) {
    return window.ChatGovernancePanel?.renderChatGovernanceSummary?.(data);
}

async function hydrateChatGovernanceDetails(decisionId) {
    return window.ChatGovernancePanel?.hydrateChatGovernanceDetails?.(decisionId);
}

window.renderChatGovernanceSummary = renderChatGovernanceSummary;
window.hydrateChatGovernanceDetails = hydrateChatGovernanceDetails;

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
        window.WeeklyPlanManager?.loadExistingPlan?.();
    }
}




// -- Haftalık Plan Etkileşim ve Oyunlaştırma Fonksiyonları --

window.toggleMealCheck = function(checkboxElement, mealText) {
    return window.WeeklyPlanManager?.toggleMealCheck?.(checkboxElement, mealText);
};
