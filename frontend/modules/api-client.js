/**
 * CureMenu - API Client Module
 * Core network logic and string manipulation utilities.
 */

const API = '';  // Aynı sunucu

let refreshPromise = null;

function refreshAccessToken() {
    if (!refreshPromise) {
        refreshPromise = fetch(API + '/api/refresh', {
            method: 'POST',
            credentials: 'include',
        })
            .then(response => response.ok)
            .catch(() => false)
            .finally(() => {
                refreshPromise = null;
            });
    }
    return refreshPromise;
}

function apiHataMesaji(data, varsayilan = 'Bir hata oluştu. Lütfen tekrar deneyin.') {
    if (!data) return varsayilan;
    if (data.error && typeof data.error.message === 'string') return data.error.message;
    if (typeof data.message === 'string') return data.message;
    const detail = data.detail;
    if (typeof detail === 'string') return detail;
    if (Array.isArray(detail) && detail.length > 0) {
        return detail[0].msg || varsayilan;
    }
    return varsayilan;
}

function baglantiHatasi(_error) {
    return 'Bağlantı kurulamadı. Lütfen birazdan tekrar deneyin.';
}

function renderTextState(container, message, className = '', tagName = 'div') {
    if (!container) return null;
    const allowedTags = new Set(['div', 'p']);
    const node = document.createElement(allowedTags.has(tagName) ? tagName : 'div');
    if (className) node.className = className;
    node.textContent = message == null ? '' : String(message);
    container.replaceChildren(node);
    return node;
}

async function safeFetchJson(url, options = {}) {
    options.credentials = 'include'; // Ensure HttpOnly cookies are sent
    let res = await fetch(url, options);
    
    // Auto Refresh Logic
    if (res.status === 401 && url.indexOf('/api/refresh') === -1 && url.indexOf('/api/login') === -1) {
        const refreshed = await refreshAccessToken();
        if (refreshed) {
            // Retry original request
            res = await fetch(url, options);
        } else {
            window.logout?.();
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

async function fetchHistoryRecords({ limit = 25, maxPages = 4 } = {}) {
    const records = [];
    for (let page = 1; page <= maxPages; page += 1) {
        const { res, data } = await safeFetchJson(`${API}/api/history?page=${page}&limit=${limit}`);
        if (!res.ok || !data?.success) {
            return { ok: false, status: res.status, records, data };
        }
        records.push(...(data.loglar || []));
        if (!data.has_more) break;
    }
    return { ok: true, status: 200, records, data: { success: true } };
}

async function safeFetchStream(url, options = {}) {
    options.credentials = 'include';
    let res = await fetch(url, options);
    
    if (res.status === 401 && url.indexOf('/api/refresh') === -1 && url.indexOf('/api/login') === -1) {
        const refreshed = await refreshAccessToken();
        if (refreshed) {
            res = await fetch(url, options);
        } else {
            window.logout?.();
            return res;
        }
    }
    return res;
}

function escapeHtml(str) {
    const div = document.createElement('div');
    div.textContent = str;
    return div.innerHTML;
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

window.API = API;
window.safeFetchJson = safeFetchJson;
window.safeFetchStream = safeFetchStream;
window.fetchHistoryRecords = fetchHistoryRecords;
window.apiHataMesaji = apiHataMesaji;
window.baglantiHatasi = baglantiHatasi;
window.renderTextState = renderTextState;
window.formatMarkdownSafe = formatMarkdownSafe;
window.escapeHtml = escapeHtml;
