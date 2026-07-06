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
