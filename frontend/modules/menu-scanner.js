(function() {
const HISTORY_LIMIT = 10;
const MAX_UPLOAD_BYTES = 8 * 1024 * 1024;
const ALLOWED_IMAGE_MIME = new Set(['image/jpeg', 'image/png', 'image/webp', 'image/jpg']);
let fridgeHistoryRecords = [];
let html5QrcodeScanner = null;
let menuScanInFlight = false;
let fridgeScanInFlight = false;

function isAllowedImageFile(file) {
    if (!file || typeof file.size !== 'number') return false;
    if (file.size <= 0 || file.size > MAX_UPLOAD_BYTES) return false;
    const mime = String(file.type || '').toLowerCase();
    if (mime && !ALLOWED_IMAGE_MIME.has(mime)) return false;
    return true;
}

function withMenuScanLock(fn) {
    if (menuScanInFlight) return Promise.resolve(false);
    menuScanInFlight = true;
    return Promise.resolve(fn()).finally(() => {
        menuScanInFlight = false;
    });
}

function withFridgeScanLock(fn) {
    if (fridgeScanInFlight) return Promise.resolve(false);
    fridgeScanInFlight = true;
    return Promise.resolve(fn()).finally(() => {
        fridgeScanInFlight = false;
    });
}

function parseHistoryMetadata(value) {
    if (!value) return {};
    if (typeof value === 'object') return value;
    try {
        return JSON.parse(value);
    } catch (_error) {
        return {};
    }
}

function historyTargetName(log) {
    const metadata = parseHistoryMetadata(log?.metadata);
    return metadata.target_name || log?.kullanici_adi || 'Hedef belirtilmemiş';
}

function historyMatchesCurrentTarget(log, selectId) {
    const context = window.ProfileManager?.getTargetCacheContext?.(selectId);
    if (!context) return true;
    const metadata = parseHistoryMetadata(log?.metadata);
    return window.ProfileManager?.historyMatchesTargetContext?.(metadata, context) ?? false;
}

function validatePublicMenuUrl(value) {
    let parsed;
    try {
        parsed = new URL(String(value || '').trim());
    } catch (_error) {
        return null;
    }
    if (!['http:', 'https:'].includes(parsed.protocol) || parsed.username || parsed.password) return null;
    if (parsed.port && !['80', '443'].includes(parsed.port)) return null;
    const host = parsed.hostname.toLowerCase().replace(/^\[|\]$/g, '');
    if (!host || host === 'localhost' || host.endsWith('.localhost')) return null;
    if (/^(127\.|0\.|10\.|169\.254\.|192\.168\.)/.test(host)) return null;
    const private172 = host.match(/^172\.(\d{1,3})\./);
    if (private172 && Number(private172[1]) >= 16 && Number(private172[1]) <= 31) return null;
    if (host === '::1' || /^(?:fc|fd|fe8|fe9|fea|feb)/.test(host)) return null;
    return parsed.href;
}

function safePreviewDataUrl(value) {
    const text = String(value || '');
    return /^data:image\/(?:jpeg|png|webp);base64,[a-z0-9+/=]+$/i.test(text) ? text : '';
}

function createImagePreview(dataUrl) {
    return new Promise(resolve => {
        const image = new Image();
        image.onload = () => {
            const scale = Math.min(1, 480 / Math.max(image.width, image.height));
            const canvas = document.createElement('canvas');
            canvas.width = Math.max(1, Math.round(image.width * scale));
            canvas.height = Math.max(1, Math.round(image.height * scale));
            canvas.getContext('2d')?.drawImage(image, 0, 0, canvas.width, canvas.height);
            resolve(canvas.toDataURL('image/jpeg', 0.72));
        };
        image.onerror = () => resolve('');
        image.src = dataUrl;
    });
}

const MENU_SECTION_DEFINITIONS = {
    suitable: { icon: '🟢', title: 'Daha Uygun Seçenekler' },
    caution: { icon: '🟡', title: 'Dikkatli Tercih Edilebilecekler' },
    avoid: { icon: '🔴', title: 'Bu Profil İçin Kaçınılması Daha Doğru Olanlar' },
};

function _cleanMenuLine(value) {
    return String(value || '')
        .trim()
        .replace(/^#{1,6}\s*/, '')
        .replace(/^(?:🟢|🟡|🔴)\s*/, '')
        .replace(/^\*\*(.*?)\*\*$/, '$1')
        .replace(/\*+$/, '')
        .trim();
}

function _menuSectionKey(value) {
    const line = _cleanMenuLine(value).replace(/:$/, '').toLocaleLowerCase('tr-TR');
    if (/^(?:sizin için )?(?:daha )?uygun seçenekler$/.test(line) || /^(?:sizin için )?güvenli(?: seçenekler)?$/.test(line)) return 'suitable';
    if (/^dikkatli tercih edilebilecekler$/.test(line) || /^porsiyon kontrolüyle tüketin$/.test(line)) return 'caution';
    if (/^(?:bu profil için )?kaçınılması daha doğru olanlar$/.test(line) || /^(?:profilinizle )?uyuşmayan(?: seçenekler)?$/.test(line)) return 'avoid';
    return '';
}

function _parseMenuSections(text) {
    const sectionItems = new Map();
    const warningParts = [];
    const noteParts = [];
    let currentKey = '';
    let pendingItem = null;
    let textMode = '';

    const ensureItems = key => {
        if (!sectionItems.has(key)) sectionItems.set(key, []);
        return sectionItems.get(key);
    };
    const flushPendingItem = () => {
        if (!pendingItem || !currentKey) return;
        pendingItem.name = _cleanMenuLine(pendingItem.name).replace(/^\[|\]$/g, '').trim();
        pendingItem.description = _cleanMenuLine(pendingItem.description);
        if (pendingItem.name) ensureItems(currentKey).push(pendingItem);
        pendingItem = null;
    };

    String(text || '').split(/\r?\n/).forEach(rawLine => {
        const line = _cleanMenuLine(rawLine);
        if (!line) return;

        const sectionKey = _menuSectionKey(line);
        if (sectionKey) {
            flushPendingItem();
            currentKey = sectionKey;
            textMode = '';
            ensureItems(sectionKey);
            return;
        }

        const warningHeading = /^profil.*güvenlik/i.test(line);
        if (warningHeading) {
            flushPendingItem();
            currentKey = '';
            textMode = 'warning';
            return;
        }

        const noteHeading = line.match(/^not\s*:?\s*(.*)$/i);
        if (noteHeading) {
            flushPendingItem();
            currentKey = '';
            textMode = 'note';
            if (noteHeading[1]) noteParts.push(_cleanMenuLine(noteHeading[1]));
            return;
        }

        if (textMode === 'warning') {
            warningParts.push(_cleanMenuLine(line.replace(/^[-*•]\s*/, '')));
            return;
        }
        if (textMode === 'note') {
            noteParts.push(_cleanMenuLine(line.replace(/^[-*•]\s*/, '')));
            return;
        }
        if (!currentKey) return;

        const withoutBullet = line.replace(/^[-*•]\s*/, '').trim();
        const bracketItem = withoutBullet.match(/^\[([^\]]+)\]\s*:?[\s]*(.*)$/);
        const boldItem = withoutBullet.match(/^\*\*([^*]+)\*\*\s*:?[\s]*(.*)$/);
        const inlineItem = bracketItem || boldItem;
        if (inlineItem) {
            flushPendingItem();
            pendingItem = { name: inlineItem[1], description: inlineItem[2] || '' };
            return;
        }

        const colonIndex = withoutBullet.indexOf(':');
        if (/^[-*•]\s*/.test(line) && colonIndex > 0) {
            flushPendingItem();
            pendingItem = {
                name: withoutBullet.slice(0, colonIndex),
                description: withoutBullet.slice(colonIndex + 1),
            };
            return;
        }

        if (pendingItem) {
            pendingItem.description = `${pendingItem.description} ${withoutBullet}`.trim();
        }
    });
    flushPendingItem();

    const sections = Object.entries(MENU_SECTION_DEFINITIONS)
        .filter(([key]) => (sectionItems.get(key) || []).length)
        .map(([key, definition]) => ({ ...definition, items: sectionItems.get(key) }));

    return {
        warningText: warningParts.join(' ').trim(),
        sections,
        note: noteParts.join(' ').trim(),
        raw: String(text || ''),
    };
}

function _renderMenuSections({ warningText, sections, note, raw }) {
    if (!sections.length) {
        return `<div class="prose prose-sm md:prose-base max-w-none text-on-surface">${formatMarkdownSafe(raw)}</div>`;
    }

    const colorMap = {
        '🟢': { bg: 'bg-emerald-50 dark:bg-emerald-950/30', border: 'border-emerald-200', dot: 'bg-emerald-500', text: 'text-emerald-800', label: 'text-emerald-700' },
        '🟡': { bg: 'bg-amber-50 dark:bg-amber-950/30', border: 'border-amber-200', dot: 'bg-amber-400', text: 'text-amber-800', label: 'text-amber-700' },
        '🔴': { bg: 'bg-red-50 dark:bg-red-950/30', border: 'border-red-200', dot: 'bg-red-400', text: 'text-red-800', label: 'text-red-700' },
    };

    const warningHtml = warningText ? `
        <div class="mb-5 flex gap-3 rounded-xl border border-warning/30 bg-warning-container/50 p-4">
            <span class="material-symbols-outlined text-warning mt-0.5 shrink-0" style="font-size:20px">info</span>
            <p class="text-sm text-on-surface-variant leading-relaxed">${escapeHtml(warningText)}</p>
        </div>` : '';

    const sectionsHtml = sections.map(({ icon, title, items }) => {
        const c = colorMap[icon] || colorMap['🟡'];
        const itemsHtml = items.map(item => {
            return `<li class="flex flex-col gap-0.5 py-2 border-b border-outline-variant/20 last:border-0">
                <span class="font-semibold text-sm ${c.text}">${escapeHtml(item.name)}</span>
                ${item.description ? `<span class="text-xs text-on-surface-variant leading-relaxed">${escapeHtml(item.description)}</span>` : ''}
            </li>`;
        }).join('');
        return `<div class="rounded-xl border ${c.border} ${c.bg} p-4">
            <div class="flex items-center gap-2 mb-3">
                <span class="inline-flex h-5 w-5 rounded-full ${c.dot} shrink-0"></span>
                <h4 class="font-display text-base font-bold ${c.label}">${escapeHtml(title)}</h4>
            </div>
            <ul class="space-y-0 divide-y divide-outline-variant/10">${itemsHtml}</ul>
        </div>`;
    }).join('');

    const noteHtml = note ? `
        <p class="mt-4 text-xs text-on-surface-variant italic border-t border-outline-variant/20 pt-3">${escapeHtml(note)}</p>` : '';

    return warningHtml + `<div class="grid gap-3">${sectionsHtml}</div>` + noteHtml;
}

function renderMenuAnalysis(data) {
    const result = document.getElementById('menuScanResult');
    const context = document.getElementById('menuTargetContext');
    if (context) context.innerHTML = `<div class="rounded-lg bg-primary-container/30 px-4 py-3 text-on-surface"><strong>${escapeHtml(data.analysis_title || 'Menü analizi')}</strong> · ${escapeHtml(data.target_name || 'Seçili kişi')} için değerlendirildi</div>`;
    const parsed = _parseMenuSections(data.analiz || '');
    result.innerHTML = `<div class="rounded-xl border border-outline-variant/20 bg-surface-container-lowest p-6 shadow-sm">${_renderMenuSections(parsed)}</div>`;
}

function _menuPreviewText(raw) {
    return raw
        .replace(/[^\S\n]*#{1,3}[^\n]*/g, '')        // ### başlıkları sil
        .replace(/[\u{1F300}-\u{1FFFF}]/gu, '')       // emoji sil
        .replace(/^[\s\-*•]+/gm, '')                  // satır başı tire/bullet sil
        .replace(/\n{2,}/g, ' ')                      // çift satır → boşluk
        .replace(/\n/g, ' ')                          // tek satır → boşluk
        .replace(/\s{2,}/g, ' ')                      // fazla boşluk sil
        .trim()
        .slice(0, 140);
}

async function loadMenuHistory(delayMs = 0) {
    const list = document.getElementById('menuHistoryList');
    if (!list) return;
    if (delayMs > 0) await new Promise(resolve => setTimeout(resolve, delayMs));
    try {
        const { res, data } = await safeFetchJson(`${API}/api/history?page=1&limit=30`);
        const rows = (data?.loglar || []).filter(log => {
            const meta = parseHistoryMetadata(log.metadata);
            return meta.analysis_type === 'menu' && historyMatchesCurrentTarget(log, 'menuTarget');
        }).slice(0, 5);
        list.innerHTML = rows.length ? rows.map((log, index) => {
            const meta = parseHistoryMetadata(log.metadata);
            const preview = _menuPreviewText(log.asistan_ciktisi || '');
            return `<article class="rounded-lg border border-outline-variant/20 bg-surface-container-lowest p-4"><div class="flex items-start justify-between gap-3"><div><strong>${escapeHtml(meta.restaurant_name || 'Menü analizi')}</strong><p class="text-sm text-on-surface-variant">${escapeHtml(meta.target_label || log.kullanici_adi || 'Hedef belirtilmemiş')} · ${new Date(log.tarih).toLocaleDateString('tr-TR')}</p></div><button class="btn-secondary px-3 py-2 text-sm" data-menu-history-index="${index}">Detayı aç</button></div><p class="mt-2 line-clamp-2 text-sm text-on-surface-variant">${escapeHtml(preview)}</p></article>`;
        }).join('') : '<p class="text-sm text-on-surface-variant">Henüz kayıtlı menü analizi yok.</p>';
        list.querySelectorAll('[data-menu-history-index]').forEach(button => button.addEventListener('click', () => renderMenuAnalysis({ analysis_title: parseHistoryMetadata(rows[button.dataset.menuHistoryIndex].metadata).restaurant_name, target_name: parseHistoryMetadata(rows[button.dataset.menuHistoryIndex].metadata).target_label, analiz: rows[button.dataset.menuHistoryIndex].asistan_ciktisi || '' })));
        if (delayMs === 0) { // target switch
            const resultDiv = document.getElementById('menuScanResult');
            if (resultDiv) {
                if (rows.length > 0) {
                    renderMenuAnalysis({ analysis_title: parseHistoryMetadata(rows[0].metadata).restaurant_name, target_name: parseHistoryMetadata(rows[0].metadata).target_label, analiz: rows[0].asistan_ciktisi || '' });
                } else {
                    resultDiv.innerHTML = '<div class="p-8 text-center text-on-surface-variant"><span class="material-symbols-outlined text-5xl mb-3 opacity-50">restaurant_menu</span><p>Hedef için henüz menü analizi yok.</p></div>';
                }
            }
        }
    } catch (_error) {
        list.innerHTML = '<p class="text-sm text-on-surface-variant">Menü geçmişi şu anda yüklenemedi.</p>';
    }
}

async function scanMenu() {
    return withMenuScanLock(async () => {
    window.CureMenuAnalytics?.track?.('menu_analysis_started', { feature: 'menu_analysis', metadata: { method: 'link' } });
    const urlRaw = document.getElementById('menuUrlInput')?.value?.trim() || '';
    const kimin_icin = document.getElementById('menuTarget')?.value || 'kendim';
    const restoran_adi = document.getElementById('menuRestaurantName')?.value?.trim() || '';
    const result = document.getElementById('menuScanResult');
    if (!result) return;

    if (!urlRaw) {
        alert("Lütfen bir restoran menü linki girin.");
        return;
    }
    const safeUrl = validatePublicMenuUrl(urlRaw);
    if (!safeUrl) {
        renderTextState(result, 'Geçerli bir https menü bağlantısı girin. Yerel ağ veya özel adresler kabul edilmez.', 'bg-error-container text-on-error-container p-6 rounded-lg text-center');
        return;
    }

    renderTextState(result, '', 'text-center py-12');
    result.innerHTML = `<div class="text-center py-12"><div class="loading-dots flex gap-2 justify-center mb-4"><span class="w-3 h-3 rounded-full bg-primary inline-block"></span><span class="w-3 h-3 rounded-full bg-primary inline-block"></span><span class="w-3 h-3 rounded-full bg-primary inline-block"></span></div><p class="text-on-surface-variant font-body-md">Menü taranıyor ve tıbbi profilinize göre analiz ediliyor... Bu işlem 15-20 saniye sürebilir.</p></div>`;

    try {
        const { res, data } = await safeFetchJson(API + '/api/scan-menu', {
            method: 'POST', headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ kimin_icin, url: safeUrl, restoran_adi })
        });
        if (data && data.success) {
            window.CureMenuAnalytics?.track?.('menu_analysis_completed', { feature: 'menu_analysis', metadata: { method: 'link', result: 'success' } });
            renderMenuAnalysis(data);
            loadMenuHistory(800);
        } else {
            renderTextState(result, apiHataMesaji(data, 'Menü okunamadı.'), 'bg-error-container text-on-error-container p-6 rounded-lg text-center');
        }
    } catch (e) {
        renderTextState(result, baglantiHatasi(e), 'bg-error-container text-on-error-container p-6 rounded-lg text-center');
    }
    });
}

async function scanMenuImage(inputEl) {
    const file = inputEl?.files?.[0];
    if (!file) return;
    const result = document.getElementById('menuScanResult');
    if (!isAllowedImageFile(file)) {
        if (result) {
            renderTextState(result, 'Lütfen en fazla 8 MB boyutunda JPEG, PNG veya WebP görseli yükleyin.', 'bg-error-container text-on-error-container p-6 rounded-lg text-center');
        }
        if (inputEl) inputEl.value = '';
        return;
    }
    await withMenuScanLock(() => new Promise(resolve => {
    window.CureMenuAnalytics?.track?.('menu_analysis_started', { feature: 'menu_analysis', metadata: { method: 'photo' } });
    const kimin_icin = document.getElementById('menuTarget')?.value || 'kendim';
    const restoran_adi = document.getElementById('menuRestaurantName')?.value?.trim() || '';
    if (result) {
        result.innerHTML = `<div class="text-center py-12"><div class="loading-dots flex gap-2 justify-center mb-4"><span class="w-3 h-3 rounded-full bg-primary inline-block"></span><span class="w-3 h-3 rounded-full bg-primary inline-block"></span><span class="w-3 h-3 rounded-full bg-primary inline-block"></span></div><p class="text-on-surface-variant font-body-md">Menü fotoğrafı analiz ediliyor...</p></div>`;
    }

    const reader = new FileReader();
    reader.onerror = () => {
        if (result) renderTextState(result, 'Görsel okunamadı. Lütfen başka bir dosya deneyin.', 'bg-error-container text-on-error-container p-6 rounded-lg text-center');
        if (inputEl) inputEl.value = '';
        resolve();
    };
    reader.onload = async () => {
        try {
            const base64 = String(reader.result).split(',')[1] || reader.result;
            const { res, data } = await safeFetchJson(API + '/api/scan-menu-image', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ kimin_icin, image_base64: base64, restoran_adi }),
            });
            if (data && data.success) {
                window.CureMenuAnalytics?.track?.('menu_analysis_completed', { feature: 'menu_analysis', metadata: { method: 'photo', result: 'success' } });
                renderMenuAnalysis(data);
                loadMenuHistory(800);
            } else if (result) {
                renderTextState(result, apiHataMesaji(data, 'Menü fotoğrafı okunamadı.'), 'bg-error-container text-on-error-container p-6 rounded-lg text-center');
            }
        } catch (e) {
            if (result) renderTextState(result, baglantiHatasi(e), 'bg-error-container text-on-error-container p-6 rounded-lg text-center');
        }
        if (inputEl) inputEl.value = '';
        resolve();
    };
    reader.readAsDataURL(file);
    }));
}

async function clearQRScannerSession() {
    const scanner = html5QrcodeScanner;
    html5QrcodeScanner = null;
    window.html5QrcodeScanner = null;
    try {
        if (scanner?.isScanning) await scanner.stop();
    } catch (_error) {
        // Camera may already be stopped after a successful scan or permission error.
    }
    try {
        await scanner?.clear?.();
    } catch (_error) {
        // Scanner may be only partially initialized when camera access fails.
    }
    const host = document.getElementById('qr-reader');
    if (host) {
        host.replaceChildren();
        host.style.display = 'none';
    }
}

async function startQRScanner() {
    const qrReaderDiv = document.getElementById('qr-reader');
    if (!qrReaderDiv) return;
    await clearQRScannerSession();
    qrReaderDiv.style.display = "block";

    if (!window.Html5Qrcode) {
        qrReaderDiv.innerHTML = '<div class="rounded-lg border border-outline-variant bg-surface-container-low p-4 text-sm text-on-surface-variant">QR okuyucu yüklenemedi. Menü bağlantısını elle girebilirsin.</div>';
        console.warn("[CureMenu] QR scanner dependency unavailable.");
        return;
    }

    html5QrcodeScanner = new window.Html5Qrcode("qr-reader");
    window.html5QrcodeScanner = html5QrcodeScanner;
    try {
        await html5QrcodeScanner.start(
            { facingMode: "environment" },
            { fps: 10, qrbox: { width: 250, height: 250 } },
            onScanSuccess,
            onScanFailure,
        );
    } catch (_error) {
        await clearQRScannerSession();
        qrReaderDiv.style.display = "block";
        renderTextState(qrReaderDiv, 'Kameraya erişilemedi. Tarayıcı iznini kontrol edin veya HTTPS üzerinden deneyin; isterseniz galeriden QR görseli seçebilirsiniz.', 'rounded-lg border border-outline-variant bg-surface-container-low p-4 text-sm text-on-surface-variant');
    }
}

async function onScanSuccess(decodedText, decodedResult) {
    const safeUrl = validatePublicMenuUrl(decodedText);
    if (!safeUrl) {
        renderTextState(document.getElementById('menuScanResult'), 'QR kodundaki bağlantı güvenli bir web adresi değil.', 'bg-error-container text-on-error-container p-6 rounded-lg text-center');
        return;
    }
    await clearQRScannerSession();
    document.getElementById('menuUrlInput').value = safeUrl;
    renderTextState(document.getElementById('menuScanResult'), 'Menü bağlantısı okundu. Hazır olduğunda “Linki tara” düğmesine basabilirsin.', 'bg-primary-container text-on-primary-container p-6 rounded-lg text-center');
}

function onScanFailure(error) {
    // Tarayıcı arka planda okuma yaparken sürekli hata fırlatabilir, logları temiz tutmak için yoruma aldım.
    // console.warn(`Code scan error = ${error}`);
}

function handleFridgeImage(event) {
    const file = event?.target?.files?.[0];
    const result = document.getElementById('fridgeScanResult');
    if (!file) return;
    if (!isAllowedImageFile(file)) {
        if (result) {
            renderTextState(result, 'Lütfen en fazla 8 MB boyutunda JPEG, PNG veya WebP fotoğrafı yükleyin.', 'card border-error-container bg-error-container p-6 text-center text-on-error-container');
        }
        if (event.target) event.target.value = '';
        return;
    }

    const reader = new FileReader();
    reader.onerror = () => {
        if (result) renderTextState(result, 'Fotoğraf okunamadı. Lütfen tekrar deneyin.', 'card border-error-container bg-error-container p-6 text-center text-on-error-container');
        if (event.target) event.target.value = '';
    };
    reader.onload = async function(e) {
        const base64String = e.target?.result;
        if (!base64String) {
            reader.onerror();
            return;
        }
        const preview = await createImagePreview(base64String);
        await scanFridge(base64String, preview);
    };
    reader.readAsDataURL(file);
}

async function scanFridge(imageBase64, imagePreviewBase64 = '') {
    return withFridgeScanLock(async () => {
    window.CureMenuAnalytics?.track?.('fridge_analysis_started', { feature: 'fridge' });
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
            body: JSON.stringify({ kimin_icin, image_base64: imageBase64, image_preview_base64: imagePreviewBase64 || null })
        });

        if (!res.ok || !data?.success) {
            renderTextState(result, apiHataMesaji(data, 'Fotoğraftaki malzemeler okunamadı. Daha net ışıkta, ürünleri kadraja alarak tekrar deneyebilirsin.'), 'card border-error-container bg-error-container p-6 text-center text-on-error-container');
            return;
        }

        const malzemeler = data.malzemeler || data.analiz?.bulunan_malzemeler || data.sonuc?.bulunan_malzemeler || '';
        window.CureMenuAnalytics?.track?.('fridge_analysis_completed', { feature: 'fridge', metadata: { result: 'success' } });
        const tarif = data.tarif || data.analiz?.tarif_metni || data.sonuc?.tarif_metni || data.analiz?.uyari_mesaji || '';
        const preview = safePreviewDataUrl(data.image_preview_base64 || imagePreviewBase64);
        result.innerHTML = `
            <div class="grid gap-5 xl:grid-cols-[360px_minmax(0,1fr)]">
                <section class="card p-5">
                    ${preview ? `<img src="${preview}" alt="Yüklenen buzdolabı fotoğrafı" class="mb-4 aspect-video w-full rounded-lg object-cover"/>` : ''}
                    <div class="mb-3 flex items-center gap-2 text-primary"><span class="material-symbols-outlined">kitchen</span><h3 class="font-display text-xl font-bold">Gördüğüm malzemeler</h3></div>
                    <p class="leading-7 text-on-surface-variant">${malzemeler ? escapeHtml(malzemeler) : 'Malzeme listesi ayrıca dönmedi.'}</p>
                </section>
                <section class="card p-5">
                    <div class="mb-3 flex items-center gap-2 text-primary"><span class="material-symbols-outlined">restaurant</span><h3 class="font-display text-xl font-bold">Tarif önerisi</h3></div>
                    <div class="prose prose-sm max-w-none text-on-surface">${tarif ? formatMarkdownSafe(tarif) : 'Tarif oluşturulamadı. Fotoğrafı yeniden yükleyebilirsin.'}</div>
                </section>
            </div>`;
        const targetContext = window.ProfileManager?.getTargetCacheContext?.('fridgeTarget') || {};
        const targetSelect = document.getElementById('fridgeTarget');
        const fallbackRecord = data.history_record || {
            eylem: 'Buzdolabı',
            kullanici_adi: targetSelect?.selectedOptions?.[0]?.textContent?.trim() || 'Seçili profil',
            kullanici_girdisi: malzemeler || 'Buzdolabı analizi',
            asistan_ciktisi: tarif,
            ai_yanit: tarif,
            tarih: new Date().toISOString(),
            metadata: {
                target_id: targetContext.targetId || '',
                target_scope: targetContext.targetScope || '',
                target_name: targetSelect?.selectedOptions?.[0]?.textContent?.trim() || '',
                detected_ingredients: String(malzemeler || '').split(',').map(item => item.trim()).filter(Boolean),
                recipe_ingredients: Array.isArray(data.recipe_ingredients) ? data.recipe_ingredients : [],
                image_preview_base64: preview,
            },
        };
        await loadFridgeHistory(fallbackRecord);
    } catch (e) {
        renderTextState(result, baglantiHatasi(e), 'card border-error-container bg-error-container p-6 text-center text-on-error-container');
    }
    });
}

async function scanQRImage(inputEl) {
    const file = inputEl?.files?.[0];
    const result = document.getElementById('menuScanResult');
    if (!file || !result) return;
    if (!isAllowedImageFile(file)) {
        renderTextState(result, 'QR okumak için JPEG, PNG veya WebP görseli seçin (en fazla 8 MB).', 'bg-error-container text-on-error-container p-6 rounded-lg text-center');
        inputEl.value = '';
        return;
    }
    await clearQRScannerSession();
    renderTextState(result, 'QR görseli okunuyor...', 'bg-surface-container-low p-6 rounded-lg text-center text-on-surface-variant');

    const readerHost = document.createElement('div');
    readerHost.id = `qr-file-reader-${Date.now()}`;
    readerHost.setAttribute('aria-hidden', 'true');
    readerHost.style.cssText = 'position:fixed;left:-10000px;top:0;width:640px;height:480px;overflow:hidden;opacity:0;pointer-events:none;z-index:-1;';
    document.body.appendChild(readerHost);
    let scanner = null;
    try {
        if (!window.Html5Qrcode) throw new Error('QR_LIBRARY_UNAVAILABLE');
        scanner = new window.Html5Qrcode(readerHost.id);
        const decodedText = await scanner.scanFile(file, false);
        const safeUrl = validatePublicMenuUrl(decodedText);
        if (!safeUrl) {
            renderTextState(result, 'QR kodundaki bağlantı güvenli bir web adresi değil.', 'bg-error-container text-on-error-container p-6 rounded-lg text-center');
            return;
        }
        document.getElementById('menuUrlInput').value = safeUrl;
        renderTextState(result, 'Menü bağlantısı okundu. Hazır olduğunda “Linki tara” düğmesine basabilirsin.', 'bg-primary-container text-on-primary-container p-6 rounded-lg text-center');
    } catch (_error) {
        renderTextState(result, 'Bu görselde okunabilir bir QR kod bulunamadı. Daha net bir fotoğraf veya kamera ile tekrar deneyin.', 'bg-error-container text-on-error-container p-6 rounded-lg text-center');
    } finally {
        try {
            await scanner?.clear?.();
        } catch (_error) {
            // The file scanner may not have initialized far enough to clear.
        }
        readerHost.remove();
        inputEl.value = '';
    }
}

// Resolve a history record's preview. Newer records reference the media store by
// uid (the base64 is no longer stored in the log, where redaction truncated it);
// older records may still carry an inline base64.
async function resolveHistoryPreview(metadata) {
    const inline = safePreviewDataUrl(metadata.image_preview_base64);
    if (inline) return inline;
    if (metadata.media_uid) {
        try {
            const url = API + '/api/media?media_type=' + encodeURIComponent(metadata.media_type || 'fridge')
                + '&media_uid=' + encodeURIComponent(metadata.media_uid);
            const { res, data } = await safeFetchJson(url);
            if (res.ok && data?.media?.image_base64) return safePreviewDataUrl(data.media.image_base64);
        } catch (e) { /* no preview */ }
    }
    return '';
}

function renderFridgeHistoryRecords(root, records) {
    fridgeHistoryRecords = records.slice(0, 3);
    root.innerHTML = fridgeHistoryRecords.map((log, index) => {
        return `
        <button type="button" data-fridge-history-index="${index}" class="w-full rounded-lg border border-outline-variant bg-surface-container-lowest p-4 text-left hover:bg-surface-container-low">
            <img data-fridge-thumb="${index}" alt="Geçmiş buzdolabı fotoğrafı" class="mb-3 aspect-video w-full max-w-xs rounded-lg object-cover hidden"/>
            <p class="text-xs text-on-surface-variant mb-2"><span class="font-medium text-primary">${escapeHtml(historyTargetName(log))} İçin</span> • ${escapeHtml(formatDecisionDate(log.tarih))}</p>
            <p class="font-medium text-on-surface">${escapeHtml(log.kullanici_girdisi || 'Buzdolabı analizi')}</p>
            <p class="mt-2 text-sm text-primary">Fotoğrafı ve tarifi aç</p>
        </button>`;
    }).join('');
    root.querySelectorAll('[data-fridge-history-index]').forEach(button => {
        button.addEventListener('click', () => showFridgeHistoryDetail(fridgeHistoryRecords[Number(button.dataset.fridgeHistoryIndex)]));
    });
    // Lazy-load each thumbnail from the media store (or inline legacy base64).
    root.querySelectorAll('img[data-fridge-thumb]').forEach(async img => {
        const log = fridgeHistoryRecords[Number(img.dataset.fridgeThumb)];
        const url = await resolveHistoryPreview(parseHistoryMetadata(log?.metadata));
        if (url) { img.src = url; img.classList.remove('hidden'); }
    });
}

async function loadFridgeHistory(fallbackRecord = null) {
    const root = document.getElementById('fridgeHistoryList');
    if (!root) return;
    if (fallbackRecord) {
        renderFridgeHistoryRecords(root, [fallbackRecord]);
    } else {
        root.innerHTML = '<p class="text-on-surface-variant">Buzdolabı geçmişi yükleniyor...</p>';
    }
    try {
        const history = await fetchHistoryRecords({ limit: 25, maxPages: 4 });
        if (!history.ok) {
            console.warn('[CureMenu] Buzdolabı geçmişi API hatası.', {
                status: history.status,
                success: Boolean(history.data?.success),
            });
            if (fallbackRecord) {
                renderFridgeHistoryRecords(root, [fallbackRecord]);
                return;
            }
            root.innerHTML = '<p class="text-on-surface-variant">Buzdolabı geçmişi şu anda yüklenemedi. Birazdan tekrar deneyebilirsin.</p>';
            return;
        }
        const records = (history.records || []).filter(log => {
            const action = String(log.eylem || '').toLocaleLowerCase('tr-TR');
            const isFridge = action.includes('buzdolabı') || action.includes('buzdolabi');
            return isFridge && historyMatchesCurrentTarget(log, 'fridgeTarget');
        });
        if (!records.length) {
            if (fallbackRecord) {
                renderFridgeHistoryRecords(root, [fallbackRecord]);
                return;
            }
            root.innerHTML = '<p class="text-on-surface-variant">Henüz buzdolabı analizi yok. Yeni bir fotoğraf yüklediğinde sonuç burada görünür.</p>';
            const resultDiv = document.getElementById('fridgeScanResult');
            if (resultDiv) {
                resultDiv.innerHTML = '<div class="card p-8 text-center text-on-surface-variant"><span class="material-symbols-outlined text-5xl mb-3 opacity-50">kitchen</span><p>Hedef için henüz buzdolabı analizi yok.</p></div>';
            }
            return;
        }
        const visibleRecords = fallbackRecord
            ? [fallbackRecord, ...records.filter(log => (
                log.asistan_ciktisi !== fallbackRecord.asistan_ciktisi
                || log.kullanici_girdisi !== fallbackRecord.kullanici_girdisi
            ))]
            : records;
        renderFridgeHistoryRecords(root, visibleRecords);
        if (!fallbackRecord) {
            const resultDiv = document.getElementById('fridgeScanResult');
            if (resultDiv && visibleRecords.length > 0) {
                showFridgeHistoryDetail(visibleRecords[0]);
            }
        }
    } catch (error) {
        console.warn('[CureMenu] Buzdolabı geçmişine bağlanılamadı.', { name: error?.name || 'Error' });
        if (fallbackRecord) return;
        root.innerHTML = '<p class="text-on-surface-variant">Buzdolabı geçmişi şu anda yüklenemedi. Birazdan tekrar deneyebilirsin.</p>';
    }
}

async function showFridgeHistoryDetail(log) {
    if (!log) return;
    const result = document.getElementById('fridgeScanResult');
    if (!result) return;
    const metadata = parseHistoryMetadata(log.metadata);
    const preview = await resolveHistoryPreview(metadata);
    const detected = Array.isArray(metadata.detected_ingredients) ? metadata.detected_ingredients.join(', ') : (log.kullanici_girdisi || '');
    result.innerHTML = `<div class="grid gap-5 xl:grid-cols-[360px_minmax(0,1fr)]">
        <section class="card p-5">${preview ? `<img src="${preview}" alt="Geçmiş buzdolabı fotoğrafı" class="mb-4 aspect-video w-full rounded-lg object-cover"/>` : ''}<h3 class="font-display text-xl font-bold">Gördüğüm malzemeler</h3><p class="mt-3 leading-7 text-on-surface-variant">${escapeHtml(detected)}</p></section>
        <section class="card p-5"><h3 class="font-display text-xl font-bold">Tarif önerisi</h3><div class="prose prose-sm mt-3 max-w-none text-on-surface">${formatMarkdownSafe(log.asistan_ciktisi || log.ai_yanit || 'Tarif bulunamadı.')}</div></section>
    </div>`;
}
    window.MenuScanner = {
        init() {
        },
        scanMenu,
        scanMenuImage,
        startQRScanner,
        scanQRImage,
        onScanSuccess,
        onScanFailure,
        handleFridgeImage,
        scanFridge,
        loadFridgeHistory,
        loadMenuHistory,
        validatePublicMenuUrl,
        renderMenuAnalysis,
    };

    window.scanMenu = scanMenu;
    window.scanMenuImage = scanMenuImage;
    window.startQRScanner = startQRScanner;
    window.scanQRImage = scanQRImage;
    window.onScanSuccess = onScanSuccess;
    window.onScanFailure = onScanFailure;
    window.handleFridgeImage = handleFridgeImage;
    window.scanFridge = scanFridge;
    window.loadFridgeHistory = loadFridgeHistory;
    window.loadMenuHistory = loadMenuHistory;
    window.html5QrcodeScanner = null;
})();
