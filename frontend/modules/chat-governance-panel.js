/**
 * CureMenu - Chat Governance Panel Module
 * Renders the decision summary next to CureBot answers.
 */

(function() {
function sanitizeDecisionId(value) {
    return String(value || '').replace(/[^a-zA-Z0-9_-]/g, '');
}

function renderChatGovernanceSummary(data, targetRoot = null) {
    const root = targetRoot || document.getElementById('chatGovernancePanel');
    if (!root || !data) return;
    const decisionId = sanitizeDecisionId(data.decision_id);
    const risk = Number(data.risk_score || 0);
    const explanation = risk >= 0.75
        ? 'Profilinizle çakışabilecek bir durum bulunduğu için yanıt sınırlandı ve sağlık profesyoneli görüşü önerildi.'
        : risk >= 0.4
            ? 'Sağlık bilgileriniz nedeniyle ek dikkat gerektiren noktalar var; yanıt bu sınırlar dikkate alınarak hazırlandı.'
            : 'Yanıt, profilinizdeki bilgiler ve güvenlik kontrolleri dikkate alınarak hazırlandı.';
    root.innerHTML = `
        <div class="space-y-3">
            <div class="rounded-lg border border-outline-variant bg-surface p-3">
                <p class="mb-1 font-bold text-on-surface">Yanıt nasıl değerlendirildi?</p>
                <p class="text-sm text-on-surface-variant">${explanation}</p>
            </div>
            <div data-chat-governance-citations class="rounded-lg border border-outline-variant bg-surface-container-low p-3 text-sm text-on-surface-variant">Kaynak bilgisi kontrol ediliyor...</div>
        </div>`;
    if (decisionId) {
        hydrateChatGovernanceDetails(
            decisionId,
            root.querySelector('[data-chat-governance-citations]')
        );
    }
}

function friendlySourceTitle(citation) {
    const raw = String(citation?.title || '').trim();
    const normalized = raw.toLocaleLowerCase('tr-TR');
    if (normalized.includes('kdigo')) return 'KDIGO böbrek rehberi';
    if (normalized.includes('levothyroxine') || normalized.includes('levotiroksin')) return 'Levothyroxine ilaç etiketi';
    if (normalized.includes('metformin')) return 'Metformin ilaç etiketi';
    const cleaned = raw
        .replace(/\.pdf$/i, '')
        .replace(/[_-]+/g, ' ')
        .replace(/\s+/g, ' ')
        .trim();
    return cleaned || 'Sağlık kaynağı';
}

async function hydrateChatGovernanceDetails(decisionId, targetRoot = null) {
    const root = targetRoot || document.querySelector('[data-chat-governance-citations]');
    if (!root) return;
    try {
        const { res, data } = await safeFetchJson((window.API || '') + `/api/clinical-decisions/${encodeURIComponent(decisionId)}`);
        if (!res.ok || !data?.success) throw new Error('decision');
        const citations = data.decision?.citations || [];
        if (!citations.length) {
            root.textContent = 'Bu yanıt için ayrıca gösterilebilir bir kaynak kaydı bulunmuyor.';
            return;
        }
        root.innerHTML = `
            <p class="mb-2 font-bold text-on-surface">Kullanılan kaynaklar</p>
            <div class="space-y-2">
                ${citations.slice(0, 3).map(citation => `
                    <div class="rounded-lg border border-outline-variant bg-white p-3">
                        <p class="font-bold text-primary">${escapeHtml(friendlySourceTitle(citation))}</p>
                    </div>`).join('')}
            </div>`;
    } catch (e) {
        root.textContent = 'Kaynak bilgisi şu anda gösterilemiyor.';
    }
}

window.ChatGovernancePanel = {
    renderChatGovernanceSummary,
    hydrateChatGovernanceDetails,
};

window.renderChatGovernanceSummary = renderChatGovernanceSummary;
window.hydrateChatGovernanceDetails = hydrateChatGovernanceDetails;
})();
