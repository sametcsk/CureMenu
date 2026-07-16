(function() {
const HISTORY_LIMIT = 10;
let currentHistoryPage = 1;

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
            result.innerHTML = `
            <div class="bg-primary-container/20 border border-primary/30 rounded-lg p-6 text-center">
                <span class="material-symbols-outlined text-primary text-4xl mb-2">task_alt</span>
                <h4 class="font-headline-md text-primary mb-2">Başarıyla Yüklendi!</h4>
                <p class="font-body-md text-on-surface">${data.message || 'Tahlil notların kaydedildi. CureBot sonraki yanıtlarda bu bilgileri dikkate alabilir.'}</p>
                <button onclick="openCureBotWidget('Tahlillerimi yükledim. Beslenme açısından nelere dikkat etmeliyim?')" class="mt-4 bg-primary text-on-primary px-6 py-2 rounded-full font-label-md hover:bg-primary/90 transition-colors shadow-sm">CureBot ile Konuşmaya Başla</button>
            </div>`;
        } else {
            result.innerHTML = `<div class="bg-error-container text-on-error-container p-6 rounded-lg text-center"><p>${apiHataMesaji(data, 'PDF yüklenemedi.')}</p></div>`;
        }
    } catch (e) {
        result.innerHTML = `<div class="bg-error-container text-on-error-container p-6 rounded-lg text-center"><p>${baglantiHatasi(e)}</p></div>`;
    }
}


async function loadLabHistory() {
    const root = document.getElementById('labHistoryList');
    if (!root) return;
    root.innerHTML = '<p class="text-on-surface-variant">Tahlil geçmişi yükleniyor...</p>';
    try {
        const { res, data } = await safeFetchJson(API + '/api/history?page=1&limit=50');
        if (!res.ok || !data?.success) throw new Error('history');

        const labs = (data.loglar || []).filter(log => String(log.eylem || '').toLowerCase().includes('tahlil'));

        // Draw Chart
        drawTahlilChart(labs);

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
                                <span class="font-medium text-primary">${escapeHtml(log.kullanici_adi || 'Kendim')} İçin</span> •
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
        root.innerHTML = emptyState('error', 'Tahlil geçmişi alınamadı', 'Bağlantı kurulamadı. Birazdan tekrar deneyebilirsin.');
    }
}


function drawTahlilChart(labs) {
    const ctx = document.getElementById('tahlilChart');
    if (!ctx) return;

    if (!window.Chart) {
        ctx.style.display = 'none';
        const existing = document.getElementById('noChartData');
        if (!existing) {
            ctx.parentElement.insertAdjacentHTML('afterbegin', '<div id="noChartData" class="absolute inset-0 grid place-items-center text-sm text-on-surface-variant font-medium">Grafik bileşeni yüklenemedi. Tahlil geçmişi metin olarak kullanılabilir.</div>');
        }
        console.warn("[CureMenu] Chart dependency unavailable.");
        return;
    }

    // Yalnızca metadata barındıran lab'leri eski tarihten yeni tarihe sırala
    const validLabs = labs
        .filter(l => l.metadata)
        .sort((a, b) => new Date(a.tarih) - new Date(b.tarih));

    const biomarkerMap = {};
    const dates = validLabs.map(l => formatDecisionDate(l.tarih).split(' ')[0]);

    validLabs.forEach((log, index) => {
        try {
            const parsed = JSON.parse(log.metadata);
            if (parsed.biomarkers && Array.isArray(parsed.biomarkers)) {
                parsed.biomarkers.forEach(b => {
                    const name = b.name.toUpperCase();
                    if (!biomarkerMap[name]) biomarkerMap[name] = new Array(validLabs.length).fill(null);
                    biomarkerMap[name][index] = parseFloat(b.value);
                });
            }
        } catch(e) {}
    });

    const datasets = Object.keys(biomarkerMap).map((key, i) => {
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

    if (tahlilChartInstance) {
        tahlilChartInstance.destroy();
    }

    if (datasets.length === 0) {
        ctx.style.display = 'none';
        ctx.parentElement.insertAdjacentHTML('afterbegin', '<div id="noChartData" class="absolute inset-0 grid place-items-center text-sm text-on-surface-variant font-medium">Grafik çizilebilecek sayısal veri (biyomarker) bulunamadı. Lütfen kantitatif sonuçları olan yeni bir PDF yükleyin.</div>');
        return;
    } else {
        ctx.style.display = 'block';
        const emptyStateEl = document.getElementById('noChartData');
        if (emptyStateEl) emptyStateEl.remove();
    }

    tahlilChartInstance = new Chart(ctx, {
        type: 'line',
        data: {
            labels: dates,
            datasets: datasets
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: { position: 'right' }
            },
            scales: {
                y: { beginAtZero: false }
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
            if (grid && reset) grid.innerHTML = `<div class="text-center py-12 text-error">${apiHataMesaji(data, 'Geçmiş yüklenemedi.')}</div>`;
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
        if (grid && reset) grid.innerHTML = `<div class="text-center py-12 text-error">${baglantiHatasi(e)}</div>`;
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
        loadHistory,
        loadMoreHistory
    };

    window.uploadHealthRecord = uploadHealthRecord;
    window.loadLabHistory = loadLabHistory;
    window.drawTahlilChart = drawTahlilChart;
    window.loadHistory = loadHistory;
    window.loadMoreHistory = loadMoreHistory;
})();
