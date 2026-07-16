/**
 * CureMenu - Shared UI Utilities
 * Small presentation helpers used by multiple dashboard modules.
 */

(function() {
function emptyState(icon, title, text) {
    return `
        <div class="rounded-lg border border-outline-variant bg-surface-container-low p-5 text-center text-on-surface-variant">
            <span class="material-symbols-outlined mb-2 block text-4xl opacity-50">${icon}</span>
            <p class="font-bold text-on-surface">${escapeHtml(title)}</p>
            <p class="mt-1 text-sm">${escapeHtml(text)}</p>
        </div>`;
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

window.UIUtils = {
    emptyState,
    formatDecisionDate,
};

window.emptyState = emptyState;
window.formatDecisionDate = formatDecisionDate;
})();
