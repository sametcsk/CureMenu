/**
 * CureMenu - Chat Governance Panel Module
 * Renders the decision summary next to CureBot answers.
 */

(function() {
function renderChatGovernanceSummary(data, targetRoot = null) {
    const root = targetRoot || document.getElementById('chatGovernancePanel');
    if (!root || !data) return;
    root.replaceChildren();
    root.hidden = true;
}

async function hydrateChatGovernanceDetails(decisionId, targetRoot = null) {
    const root = targetRoot || document.querySelector('[data-chat-governance-citations]');
    if (!root) return;
    root.replaceChildren();
    root.hidden = true;
}

window.ChatGovernancePanel = {
    renderChatGovernanceSummary,
    hydrateChatGovernanceDetails,
};

window.renderChatGovernanceSummary = renderChatGovernanceSummary;
window.hydrateChatGovernanceDetails = hydrateChatGovernanceDetails;
})();
