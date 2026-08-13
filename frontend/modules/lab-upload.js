(function() {
const HISTORY_LIMIT = 10;
let currentHistoryPage = 1;
let tahlilChartInstance = null;
const BIOMARKER_ALIAS_MAP = new Map([
    ['glucose', 'Glucose'],
    ['glukoz', 'Glucose'],
    ['kan sekeri', 'Glucose'],
    ['hba1c', 'HbA1c'],
    ['hemoglobin a1c', 'HbA1c'],
    ['hemoglobin-a1c', 'HbA1c'],
    ['glycated hemoglobin', 'HbA1c'],
    ['b12', 'B12'],
    ['vitamin b12', 'B12'],
    ['vitamin-b12', 'B12'],
    ['ferritin', 'Ferritin'],
    ['hemoglobin', 'Hemoglobin'],
    ['hgb', 'Hemoglobin'],
    ['mcv', 'MCV'],
    ['tsh', 'TSH'],
    ['tiroid stimulan hormon', 'TSH'],
    ['tiroid stimule edici hormon', 'TSH'],
    ['thyroid stimulating hormone', 'TSH'],
    ['toplam kolesterol', 'Total Kolesterol'],
    ['total kolesterol', 'Total Kolesterol'],
    ['total cholesterol', 'Total Kolesterol'],
    ['kolesterol total', 'Total Kolesterol'],
    ['kreatinin', 'Kreatinin'],
    ['creatinine', 'Kreatinin'],
]);

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

function normalizeTargetLabel(value) {
    return String(value || '')
        .replace(/\s+İçin$/i, '')
        .replace(/\s+Icin$/i, '')
        .trim()
        .toLocaleLowerCase('tr-TR');
}

function selectedTargetLabel(selectId) {
    const select = document.getElementById(selectId);
    return select?.selectedOptions?.[0]?.textContent || '';
}

function currentTargetDisplayName(context, selectId) {
    if (context.targetScope === 'self') {
        return window.currentProfile?.ana_kullanici?.ad || window.AuthManager?.getUser?.()?.ad || '';
    }
    return selectedTargetLabel(selectId);
}

function legacyHistoryMatchesCurrentTarget(log, context, selectId) {
    if (context.targetScope === 'family') return true;
    const selectedName = normalizeTargetLabel(currentTargetDisplayName(context, selectId));
    const recordName = normalizeTargetLabel(log?.kullanici_adi);
    if (selectedName && recordName) return selectedName === recordName;
    return context.targetScope === 'self';
}

function historyMatchesCurrentTarget(log, selectId) {
    const context = window.ProfileManager?.getTargetCacheContext?.(selectId);
    if (!context) return true;
    const metadata = parseHistoryMetadata(log?.metadata);
    if (!metadata.target_id && !metadata.target_scope) {
        return legacyHistoryMatchesCurrentTarget(log, context, selectId);
    }
    return window.ProfileManager?.historyMatchesTargetContext?.(metadata, context) ?? false;
}

function normalizeBiomarkerName(name) {
    const raw = String(name || '').trim();
    if (!raw) return null;
    const compact = raw
        .normalize('NFD')
        .replace(/[\u0300-\u036f]/g, '')
        .toLocaleLowerCase('tr-TR')
        .replace(/[^a-z0-9]+/g, ' ')
        .trim();
    return BIOMARKER_ALIAS_MAP.get(compact) || raw;
}

function toNumericValue(value) {
    if (typeof value === 'number' && Number.isFinite(value)) return value;
    const normalized = String(value ?? '')
        .replace(',', '.')
        .match(/-?\d+(?:\.\d+)?/);
    if (!normalized) return null;
    const parsed = Number.parseFloat(normalized[0]);
    return Number.isFinite(parsed) ? parsed : null;
}

function formatLabChartDate(value) {
    const date = new Date(value);
    if (Number.isNaN(date.getTime())) return String(value || '-');
    return date.toLocaleDateString('tr-TR', {
        day: '2-digit',
        month: '2-digit',
        year: 'numeric',
    });
}

function buildLabChartModel(labs) {
    const observationDate = (log) => {
        const metadata = parseHistoryMetadata(log?.metadata);
        return metadata?.lab_report_date || log?.tarih;
    };
    const validLabs = (Array.isArray(labs) ? labs : [])
        .filter(l => l?.metadata)
        .sort((a, b) => new Date(observationDate(a)) - new Date(observationDate(b)));
    const labels = validLabs.map(l => formatLabChartDate(observationDate(l)));
    const biomarkerMap = {};
    let numericObservationCount = 0;

    validLabs.forEach((log, index) => {
        try {
            const parsed = parseHistoryMetadata(log.metadata);
            if (!Array.isArray(parsed?.biomarkers)) {
                return;
            }
            parsed.biomarkers.forEach((biomarker) => {
                const normalizedName = normalizeBiomarkerName(biomarker?.name);
                const numericValue = toNumericValue(biomarker?.value);
                if (!normalizedName || numericValue === null) {
                    return;
                }
                numericObservationCount += 1;
                if (!biomarkerMap[normalizedName]) {
                    biomarkerMap[normalizedName] = new Array(validLabs.length).fill(null);
                }
                biomarkerMap[normalizedName][index] = numericValue;
            });
        } catch (_error) {
            // Invalid metadata should not break the chart or history list.
        }
    });

    const datasets = Object.keys(biomarkerMap)
        .filter((key) => biomarkerMap[key].filter((value) => value !== null).length >= 2)
        .map((key, i) => {
            const hue = (i * 137.508) % 360;
            return {
                label: key,
                data: biomarkerMap[key],
                borderColor: `hsl(${hue}, 70%, 40%)`,
                backgroundColor: `hsl(${hue}, 70%, 40%, 0.1)`,
                tension: 0.3,
                spanGaps: true
            };
        });

    let emptyMessage = '';
    if (!datasets.length) {
        emptyMessage = numericObservationCount > 0
            ? 'Grafik için aynı biyomarkerın en az iki sayısal sonucu gerekiyor.'
            : 'Grafik çizilebilecek sayısal veri (biyomarker) bulunamadı. Lütfen kantitatif sonuçları olan yeni bir PDF yükleyin.';
    }

    return { labels, datasets, emptyMessage };
}

async function uploadHealthRecord(event) {
    const file = event.target.files[0];
    if (!file) return;

    const user = getUser();
    const kimin_icin = document.getElementById('tahlilTarget')?.value || 'kendim';
    const result = document.getElementById('healthRecordResult');

    // Reset file input
    document.getElementById('healthRecordInput').value = '';

    result.innerHTML = `<div class="text-center py-12"><div class="loading-dots flex gap-2 justify-center mb-4"><span class="w-3 h-3 rounded-full bg-primary inline-block"></span><span class="w-3 h-3 rounded-full bg-primary inline-block"></span><span class="w-3 h-3 rounded-full bg-primary inline-block"></span></div><p class="text-on-surface-variant font-body-md">Tahlil dosyanı güvenli şekilde okuyorum...<br/>Bu işlem biraz sürebilir.</p></div>`;

    const formData = new FormData();
    window.CureMenuAnalytics?.track?.('lab_analysis_started', { feature: 'lab' });
    formData.append("file", file);
    formData.append("kimin_icin", kimin_icin);

    try {
        const res = await fetch(API + '/api/upload-health-record', {
            method: 'POST',
            credentials: 'include',
            body: formData
        });
        const data = await res.json();

        if (res.ok && data.success) {
            window.CureMenuAnalytics?.track?.('lab_analysis_completed', { feature: 'lab', metadata: { result: 'success' } });
            result.innerHTML = `
            <div class="bg-primary-container/20 border border-primary/30 rounded-lg p-6 text-center">
                <span class="material-symbols-outlined text-primary text-4xl mb-2">task_alt</span>
                <h4 class="font-headline-md text-primary mb-2">Başarıyla Yüklendi!</h4>
                <p class="font-body-md text-on-surface" data-upload-message></p>
                <button onclick="openCureBotWidget('Tahlillerimi yükledim. Beslenme açısından nelere dikkat etmeliyim?')" class="mt-4 bg-primary text-on-primary px-6 py-2 rounded-full font-label-md hover:bg-primary/90 transition-colors shadow-sm">CureBot ile Konuşmaya Başla</button>
            </div>`;
            const uploadMessage = result.querySelector('[data-upload-message]');
            if (uploadMessage) {
                uploadMessage.textContent = data.message || 'Tahlil notların kaydedildi. CureBot sonraki yanıtlarda bu bilgileri dikkate alabilir.';
            }
            await new Promise(r => setTimeout(r, 800));
            await loadLabHistory();
        } else {
            renderTextState(result, apiHataMesaji(data, 'PDF yüklenemedi.'), 'bg-error-container text-on-error-container p-6 rounded-lg text-center');
        }
    } catch (e) {
        renderTextState(result, baglantiHatasi(e), 'bg-error-container text-on-error-container p-6 rounded-lg text-center');
    }
}


async function loadLabHistory() {
    const root = document.getElementById('labHistoryList');
    if (!root) return;
    root.innerHTML = '<p class="text-on-surface-variant">Tahlil geçmişi yükleniyor...</p>';
    try {
        const history = await fetchHistoryRecords({ limit: 25, maxPages: 4 });
        if (!history.ok) {
            console.warn('[CureMenu] Tahlil geçmişi API hatası.', {
                status: history.status,
                success: Boolean(history.data?.success),
            });
            root.innerHTML = emptyState('error', 'Tahlil geçmişi şu anda yüklenemedi', 'Birazdan tekrar deneyebilirsin.');
            return;
        }

        const labs = (history.records || []).filter(log =>
            String(log.eylem || '').toLocaleLowerCase('tr-TR').includes('tahlil') && historyMatchesCurrentTarget(log, 'tahlilTarget')
        );

        // Draw Chart
        try {
            drawTahlilChart(labs);
        } catch (error) {
            // A chart failure must not hide the persisted lab history.
            console.warn('[CureMenu] Tahlil grafiği oluşturulamadı; liste gösteriliyor.', error?.name || 'ChartError');
        }

        if (!labs.length) {
            root.innerHTML = emptyState('vaccines', 'Yüklenen tahlil yok', 'PDF yüklediğinde özet burada görünür. Biyomarker listesi otomatik çekilerek grafiğe yansır.');
            return;
        }
        root.innerHTML = labs.map((log, index) => {
            const summaryId = `lab-summary-${index}`;
            return `
            <article class="rounded-lg border border-outline-variant bg-surface overflow-hidden">
                <button onclick="document.getElementById('${summaryId}').classList.toggle('hidden')" class="w-full flex items-center justify-between p-4 hover:bg-surface-container-low transition-colors text-left">
                    <div class="flex items-center gap-3">
                        <span class="material-symbols-outlined rounded-lg bg-primary-container p-2 text-primary">description</span>
                        <div>
                            <p class="font-bold text-on-surface">${escapeHtml(log.kullanici_girdisi || 'Tahlil Raporu')}</p>
                            <p class="text-xs text-on-surface-variant mt-0.5">
                                <span class="font-medium text-primary">${escapeHtml(historyTargetName(log))} İçin</span> •
                                ${escapeHtml(formatDecisionDate(log.tarih))}
                            </p>
                        </div>
                    </div>
                    <span class="material-symbols-outlined text-outline-variant">expand_more</span>
                </button>
                <div id="${summaryId}" class="hidden border-t border-outline-variant/30 bg-surface-container-lowest p-4 text-sm text-on-surface-variant leading-relaxed">
                    ${formatMarkdownSafe(log.asistan_ciktisi || log.ai_yanit || 'Özet kaydı bulunamadı.')}
                </div>
            </article>`;
        }).join('');
    } catch (e) {
        console.warn('[CureMenu] Tahlil geçmişine bağlanılamadı.', { name: e?.name || 'Error' });
        root.innerHTML = emptyState('error', 'Tahlil geçmişi alınamadı', 'Bağlantı kurulamadı. Birazdan tekrar deneyebilirsin.');
    }
}


function drawTahlilChart(labs) {
    const ctx = document.getElementById('tahlilChart');
    if (!ctx) return;
    const emptyStateEl = document.getElementById('noChartData');
    if (emptyStateEl) emptyStateEl.remove();

    if (!window.Chart) {
        ctx.style.display = 'none';
        ctx.parentElement.insertAdjacentHTML('afterbegin', '<div id="noChartData" class="absolute inset-0 grid place-items-center text-sm text-on-surface-variant font-medium">Grafik bileşeni yüklenemedi. Tahlil geçmişi metin olarak kullanılabilir.</div>');
        console.warn("[CureMenu] Chart dependency unavailable.");
        return;
    }
    const chartModel = buildLabChartModel(labs);

    if (tahlilChartInstance) {
        tahlilChartInstance.destroy();
    }

    if (!chartModel.datasets.length) {
        ctx.style.display = 'none';
        ctx.parentElement.insertAdjacentHTML('afterbegin', `<div id="noChartData" class="absolute inset-0 grid place-items-center text-sm text-on-surface-variant font-medium">${escapeHtml(chartModel.emptyMessage)}</div>`);
        return;
    }
    ctx.style.display = 'block';

    const allValues = [].concat(...chartModel.datasets.map(d => d.data.filter(v => v !== null)));
    const maxVal = Math.max(...allValues);
    const minVal = Math.min(...allValues);
    const delta = maxVal === minVal ? (maxVal * 0.1) || 10 : (maxVal - minVal) * 0.1;

    tahlilChartInstance = new Chart(ctx, {
        type: 'line',
        data: {
            labels: chartModel.labels,
            datasets: chartModel.datasets
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            layout: {
                padding: { top: 10, bottom: 10, left: 5, right: 20 }
            },
            plugins: {
                legend: { position: 'right' }
            },
            scales: {
                y: { 
                    beginAtZero: false,
                    suggestedMin: minVal - delta,
                    suggestedMax: maxVal + delta
                }
            }
        }
    });
}


async function loadHistory(reset = false) {
    const user = getUser();
    if (!user.telefon) return;

    if (reset) {
        currentHistoryPage = 1;
        const grid = document.getElementById('historyGrid');
        if(grid) grid.innerHTML = '<div class="text-center py-20 text-on-surface-variant"><div class="loading-dots flex gap-2 justify-center mb-4"><span class="w-3 h-3 rounded-full bg-secondary inline-block"></span><span class="w-3 h-3 rounded-full bg-secondary inline-block"></span><span class="w-3 h-3 rounded-full bg-secondary inline-block"></span></div><p>Geçmiş yükleniyor...</p></div>';
        const page = document.getElementById('historyPagination');
        if(page) page.classList.add('hidden');
    }

    try {
        const { res, data } = await safeFetchJson(`${API}/api/history?page=${currentHistoryPage}&limit=${HISTORY_LIMIT}`);
        if (!res.ok || !data?.success) {
            const grid = document.getElementById('historyGrid');
            if (grid && reset) renderTextState(grid, apiHataMesaji(data, 'Geçmiş yüklenemedi.'), 'text-center py-12 text-error');
            return;
        }
        const grid = document.getElementById('historyGrid');
        if (reset && grid) grid.innerHTML = '';

        const loglar = data.loglar || [];
        if (loglar.length === 0 && reset && grid) {
            grid.innerHTML = `
                <div class="text-center py-20 text-on-surface-variant">
                    <span class="material-symbols-outlined text-6xl mb-4 block opacity-30">history</span>
                    <p>Henüz geçmiş işleminiz bulunmuyor.</p>
                </div>`;
            return;
        }

        loglar.forEach(log => {
            const date = new Date(log.tarih);
            const formattedDate = date.toLocaleDateString('tr-TR', { day: 'numeric', month: 'long', hour: '2-digit', minute:'2-digit' });

            let icon = 'history';
            let bg = 'bg-surface-container-low';
            const title = log.eylem || 'İşlem';

            if (title.includes('Buzdolabı')) { icon = 'kitchen'; bg = 'bg-primary-container/10'; }
            else if (title.includes('QR Menü')) { icon = 'document_scanner'; bg = 'bg-secondary-container/10'; }
            else if (title.includes('CureBot')) { icon = 'smart_toy'; bg = 'bg-surface-variant/30'; }
            else if (title.includes('Haftalık Plan')) { icon = 'restaurant_menu'; bg = 'bg-primary-container/5'; }

            const assistantOutput = log.asistan_ciktisi || log.ai_yanit || '';
            const responseHtml = assistantOutput ? `<div class="mt-4 p-4 bg-surface rounded-lg border border-outline-variant/20 text-sm text-on-surface-variant max-h-[150px] overflow-y-auto chat-scroll">${formatMarkdownSafe(assistantOutput)}</div>` : '';

            if(grid) {
                grid.innerHTML += `
                    <article class="bg-surface-container-lowest rounded-lg p-6 shadow-sm border border-outline-variant/20 flex flex-col md:flex-row gap-4">
                        <div class="w-12 h-12 rounded-full ${bg} flex items-center justify-center flex-shrink-0 text-primary">
                            <span class="material-symbols-outlined">${icon}</span>
                        </div>
                        <div class="flex-1 min-w-0">
                            <div class="flex justify-between items-start mb-2">
                                <div>
                                    <h3 class="font-headline-md text-[18px] font-semibold text-on-surface">${escapeHtml(title)}</h3>
                                    <p class="font-label-sm text-outline">${formattedDate}${log.kullanici_adi ? ' · ' + escapeHtml(log.kullanici_adi) : ''}</p>
                                </div>
                            </div>
                            <p class="font-body-sm text-on-surface line-clamp-2 mt-2"><strong>Girdi:</strong> ${escapeHtml(log.kullanici_girdisi || 'Sistem isteği')}</p>
                            ${responseHtml}
                        </div>
                    </article>
                `;
            }
        });

        const pagination = document.getElementById('historyPagination');
        if (pagination) {
            if (data.has_more) pagination.classList.remove('hidden');
            else pagination.classList.add('hidden');
        }
    } catch (e) {
        console.error("Geçmiş yüklenirken hata:", e);
        const grid = document.getElementById('historyGrid');
        if (grid && reset) renderTextState(grid, baglantiHatasi(e), 'text-center py-12 text-error');
    }
}


function loadMoreHistory() {
    currentHistoryPage += 1;
    loadHistory(false);
}

    window.LabUpload = {
        init() {},
        uploadHealthRecord,
        loadLabHistory,
        drawTahlilChart,
        buildLabChartModel,
        normalizeBiomarkerName,
        loadHistory,
        loadMoreHistory
    };

    window.uploadHealthRecord = uploadHealthRecord;
    window.loadLabHistory = loadLabHistory;
    window.drawTahlilChart = drawTahlilChart;
    window.loadHistory = loadHistory;
    window.loadMoreHistory = loadMoreHistory;
})();
