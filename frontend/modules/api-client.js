/**
 * CureMenu - API Client Module
 * Core network logic and string manipulation utilities.
 */

const API = '';  // Aynı sunucu

let isRefreshing = false;
let refreshSubscribers = [];

function onRefreshed(token) {
    refreshSubscribers.map(cb => cb(token));
    refreshSubscribers = [];
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
                    window.logout?.(); // If refresh fails, log them out
                }
            } catch (e) {
                onRefreshed(false);
                window.logout?.();
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
                    window.logout?.();
                }
            } catch (e) {
                onRefreshed(false);
                window.logout?.();
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
window.apiHataMesaji = apiHataMesaji;
window.baglantiHatasi = baglantiHatasi;
window.onRefreshed = onRefreshed;
window.formatMarkdownSafe = formatMarkdownSafe;
window.escapeHtml = escapeHtml;
