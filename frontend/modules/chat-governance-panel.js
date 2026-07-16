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
            <div data-chat-governance-citations class="rounded-lg border border-outline-variant bg-surface-container-low p-3 text-sm text-on-surface-variant">Kaynak bilgisi kontrol ediliyor...</div>
            ${decisionId ? `<button onclick="openDecisionTimeline('${decisionId}')" class="btn-secondary px-4 py-2 text-sm font-bold">Olay zincirini gör</button>` : ''}
        </div>`;
    if (decisionId) {
        hydrateChatGovernanceDetails(
            decisionId,
            root.querySelector('[data-chat-governance-citations]')
        );
    }
}

async function hydrateChatGovernanceDetails(decisionId, targetRoot = null) {
    const root = targetRoot || document.querySelector('[data-chat-governance-citations]');
    if (!root) return;
    try {
        const { res, data } = await safeFetchJson((window.API || '') + `/api/clinical-decisions/${encodeURIComponent(decisionId)}`);
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

window.ChatGovernancePanel = {
    renderChatGovernanceSummary,
    hydrateChatGovernanceDetails,
};

window.renderChatGovernanceSummary = renderChatGovernanceSummary;
window.hydrateChatGovernanceDetails = hydrateChatGovernanceDetails;
})();
