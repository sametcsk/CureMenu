(function() {
let smartGroceryEventsBound = false;

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
        <div class="absolute inset-0 bg-on-background/50 backdrop-blur-sm" data-grocery-action="close"></div>
        <div class="card relative flex max-h-[90vh] w-full max-w-5xl flex-col overflow-hidden">
            <div class="flex items-center justify-between border-b border-outline-variant p-5">
                <div>
                    <h3 class="font-display text-2xl font-bold">Akıllı Sepet</h3>
                    <p class="mt-1 text-sm text-on-surface-variant">Sağlık profiline göre işaretlenmiş tahmini alışveriş listesi.</p>
                </div>
                <button type="button" data-grocery-action="close" class="btn-icon"><span class="material-symbols-outlined">close</span></button>
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

function bindSmartGroceryEvents() {
    if (smartGroceryEventsBound) return;
    smartGroceryEventsBound = true;
    document.addEventListener('click', async (event) => {
        const trigger = event.target.closest('[data-grocery-action]');
        if (!trigger) return;
        const action = trigger.dataset.groceryAction;
        if (!action) return;
        event.preventDefault();

        if (action === 'open') {
            await openSmartGrocery();
        } else if (action === 'close') {
            closeSmartGrocery();
        } else if (action === 'calculate-budget') {
            await calculateBudget();
        } else if (action === 'feedback') {
            await sendFeedback(trigger.dataset.meal || trigger.dataset.itemName || '');
        }
    });
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
// Weekly recipe modal behavior lives in frontend/modules/weekly-actions.js.

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

    window.SmartGrocery = {
        init() {
            bindSmartGroceryEvents();
        },
        bindSmartGroceryEvents,
        calculateBudget,
        ensureSmartGroceryModal,
        closeSmartGrocery,
        openSmartGrocery,
        groceryStatusClass,
        groceryStatusLabel,
        groceryPriceRange,
        renderSmartGrocery,
        sendFeedback
    };

    // Maintain global references for dynamic HTML/markdown buttons
    window.sendFeedback = window.SmartGrocery.sendFeedback;
    window.calculateBudget = window.SmartGrocery.calculateBudget;
    window.openSmartGrocery = window.SmartGrocery.openSmartGrocery;
    window.closeSmartGrocery = window.SmartGrocery.closeSmartGrocery;
    window.ensureSmartGroceryModal = window.SmartGrocery.ensureSmartGroceryModal;
    window.groceryStatusClass = window.SmartGrocery.groceryStatusClass;
    window.groceryStatusLabel = window.SmartGrocery.groceryStatusLabel;
    window.groceryPriceRange = window.SmartGrocery.groceryPriceRange;
    window.renderSmartGrocery = window.SmartGrocery.renderSmartGrocery;
    bindSmartGroceryEvents();
})();
