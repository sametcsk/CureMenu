(function() {
function formatPercent(value) {
    const num = Number(value || 0);
    return `${num.toFixed(1)}%`;
}

function renderKpiCard(label, value, icon, tone = 'primary') {
    const color = tone === 'error' ? 'text-error bg-error-container border-error/20' : 'text-primary bg-primary-container border-primary/20';
    return `
        <article class="card p-5">
            <div class="mb-4 flex items-center justify-between gap-3">
                <span class="material-symbols-outlined ${color} rounded-lg border p-2">${icon}</span>
            </div>
            <p class="metric-label">${escapeHtml(label)}</p>
            <p class="mt-1 font-display text-3xl font-extrabold text-on-surface">${escapeHtml(String(value))}</p>
        </article>`;
}

function clampScore(value) {
    const number = Number(value || 0);
    return Math.max(0, Math.min(100, number));
}

function renderKpiEventBreakdown(kpis) {
    const root = document.getElementById('kpiEventBreakdown');
    if (!root) return;
    if (!kpis || Number(kpis.total_decisions || 0) === 0) {
        root.innerHTML = `
            <div class="text-center py-8 text-on-surface-variant">
                <span class="material-symbols-outlined text-5xl mb-3 block opacity-30">health_and_safety</span>
                <p>Henüz yeterli kontrol kaydı yok. CureBot ile birkaç görüşmeden sonra burada güvenlik özeti oluşur.</p>
            </div>`;
        return;
    }

    const metrics = [
        {
            label: 'Profil uyumu',
            desc: 'Yanıtlar profil bilgilerinle eşleştirildi.',
            icon: 'person_check',
            value: clampScore(Number(kpis.average_confidence || 0) * 100),
        },
        {
            label: 'Risk kontrolü',
            desc: 'Yüksek riskli durumlarda daha temkinli davranıldı.',
            icon: 'shield',
            value: clampScore(100 - Number(kpis.high_risk_rate || 0)),
        },
        {
            label: 'Kaynak kaydı',
            desc: 'Kaynak veya izleme kaydı bulunan karar oranı.',
            icon: 'menu_book',
            value: clampScore(kpis.evidence_coverage_rate || kpis.retrieval_evidence_rate || 0),
        },
        {
            label: 'Yönlendirme hassasiyeti',
            desc: 'Belirsiz durumlarda güvenli tarafa çekme oranı.',
            icon: 'support_agent',
            value: clampScore(100 - Number(kpis.blocked_event_rate || 0)),
        },
    ];

    root.innerHTML = metrics.map((metric) => `
        <div class="rounded-lg border border-outline-variant/20 bg-surface p-4">
            <div class="flex items-start gap-3">
                <span class="material-symbols-outlined text-primary bg-primary-container/15 rounded-full p-2">${metric.icon}</span>
                <div class="flex-1 min-w-0">
                    <div class="flex items-center justify-between gap-3">
                        <p class="font-label-md text-on-surface">${escapeHtml(metric.label)}</p>
                        <span class="font-label-sm text-primary">${metric.value.toFixed(0)}%</span>
                    </div>
                    <div class="mt-2 h-2 rounded-full bg-surface-container overflow-hidden">
                        <div class="h-full rounded-full bg-primary" style="width:${metric.value}%"></div>
                    </div>
                    <p class="mt-2 text-xs leading-5 text-on-surface-variant">${escapeHtml(metric.desc)}</p>
                </div>
            </div>
        </div>`).join('');
}

function renderClinicalDecisions(decisions) {
    const root = document.getElementById('clinicalDecisionList');
    if (!root) return;
    if (!decisions || decisions.length === 0) {
        root.innerHTML = '<p class="text-on-surface-variant">Henuz klinik karar kaydi yok. CureBot ile bir konusma yaptiktan sonra burada gorunur.</p>';
        return;
    }
    root.innerHTML = decisions.map((decision) => {
        const risk = Number(decision.risk_score || 0);
        const confidence = Number(decision.confidence_score || 0);
        const riskTone = risk >= 0.7 ? 'text-error bg-error-container/40' : 'text-primary bg-primary-container/20';
        const decisionId = String(decision.decision_id || '').replace(/[^a-zA-Z0-9_-]/g, '');
        return `
            <article class="rounded-lg border border-outline-variant/20 bg-surface p-4">
                <div class="flex flex-col md:flex-row md:items-center justify-between gap-3">
                    <div class="min-w-0">
                        <p class="font-label-sm text-outline truncate">${escapeHtml(decision.decision_id || '')}</p>
                        <p class="font-body-md text-on-surface mt-1 line-clamp-2">${escapeHtml(decision.istek || '')}</p>
                    </div>
                    <div class="flex items-center gap-2 shrink-0 flex-wrap">
                        <span class="px-2 py-1 rounded-full text-xs ${riskTone}">Risk ${risk.toFixed(2)}</span>
                        <span class="px-2 py-1 rounded-full text-xs bg-surface-container text-primary">Operasyonel güven ${confidence.toFixed(2)}</span>
                        <button type="button" onclick="window.GovernanceDashboard.openDecisionTimeline('${decisionId}')" class="inline-flex items-center justify-center w-9 h-9 rounded-full border border-outline-variant/30 text-primary hover:bg-primary-container/20 transition-colors" title="Karar adımları">
                            <span class="material-symbols-outlined text-[20px]">timeline</span>
                        </button>
                    </div>
                </div>
            </article>`;
    }).join('');
}

function formatDecisionDate(value) {
    return window.UIUtils?.formatDecisionDate?.(value) || String(value || '-');
}

function renderMetadata(metadata) {
    const entries = Object.entries(metadata || {});
    if (entries.length === 0) return '';
    return `
        <dl class="mt-3 grid grid-cols-1 md:grid-cols-2 gap-2">
            ${entries.map(([key, value]) => {
                const text = typeof value === 'object' ? JSON.stringify(value) : String(value);
                return `
                    <div class="rounded-lg bg-surface-container p-3 border border-outline-variant/20">
                        <dt class="font-label-sm text-outline">${escapeHtml(key)}</dt>
                        <dd class="font-body-sm text-on-surface break-words">${escapeHtml(text)}</dd>
                    </div>`;
            }).join('')}
        </dl>`;
}

function humanizeEventType(value) {
    const map = {
        ConversationStarted: 'Soru alındı',
        PatientProfileLoaded: 'Profil bilgileri hazırlandı',
        ConversationRouted: 'İstek doğru alana yönlendirildi',
        ClinicalPriorityResolved: 'Öncelikler kontrol edildi',
        NutritionOptionsGenerated: 'Öneri hazırlandı',
        RetrieverExecuted: 'Kaynaklar tarandı',
        RuleChecked: 'Güvenlik kuralı kontrol edildi',
        RuleTriggered: 'Riskli eşleşme durduruldu',
        RiskClassified: 'Risk seviyesi belirlendi',
        FinalAnswerGenerated: 'Yanıt hazırlandı',
        ClinicalDocumentationGenerated: 'Kayıt oluşturuldu',
        FastAnswerGenerated: 'Hızlı yanıt verildi',
        AIFallbackActivated: 'Güvenli yedek yanıt kullanıldı',
        InputGuardrailBlocked: 'Güvenlik sınırı devreye girdi',
    };
    return map[value] || 'Kontrol adımı';
}

function humanizeComponent(value) {
    const map = {
        'api.chat': 'CureBot',
        profile_context: 'Profil',
        supervisor: 'Yönlendirme',
        triage: 'Öncelik kontrolü',
        nutrition_capability: 'Beslenme önerisi',
        medication_safety: 'İlaç-besin kural kontrolü',
        evidence_retrieval: 'Kaynak kontrolü',
        auditor: 'Güvenlik denetimi',
        chef_capability: 'Tarif hazırlama',
        conversation_capability: 'Sohbet',
        nemo_guardrails: 'Güvenlik sınırı',
    };
    return map[value] || 'CureMenu kontrolü';
}

function humanizeAction(value) {
    const map = {
        SOHBET: 'Bilgilendirici sohbet',
        SOHBET_FALLBACK: 'Güvenli yedek yanıt',
        SECENEK_SUN: 'Seçenek hazırlama',
        SECENEK_SUN_BITTI: 'Seçenek sunuldu',
        RAPORLANDI: 'Raporlandı',
        INPUT_GUARDRAIL_BLOCKED: 'Güvenlik nedeniyle durduruldu',
        APPROVE: 'Otomatik akışa devam edildi',
        REVIEW_REQUIRED: 'Dikkatli inceleme gerekli',
        REJECT: 'Uygun değil',
    };
    return map[value] || 'Kontrollü yanıt';
}

function renderDecisionTimeline(decision) {
    const events = decision.events || [];
    const versions = Object.entries(decision.component_versions || {});
    const citations = decision.citations || [];
    const confidence = decision.confidence_data || decision.confidence || {};
    const risk = Number(decision.risk_score || 0);
    const confidenceScore = Number(decision.confidence_score || 0);

    return `
        <div class="space-y-5">
            <section class="rounded-lg border border-outline-variant/20 bg-surface p-4">
                <div class="flex flex-col md:flex-row md:items-start justify-between gap-4">
                    <div class="min-w-0">
                        <p class="font-label-sm text-outline break-all">${escapeHtml(decision.decision_id || '')}</p>
                        <h4 class="font-headline-md text-on-surface mt-1">${escapeHtml(humanizeAction(decision.final_action))}</h4>
                        <p class="font-body-sm text-on-surface-variant mt-2">${escapeHtml(decision.istek || '')}</p>
                    </div>
                    <div class="flex flex-wrap gap-2">
                        <span class="px-3 py-1 rounded-full text-xs bg-error-container/30 text-error">Risk ${risk.toFixed(2)}</span>
                        <span class="px-3 py-1 rounded-full text-xs bg-primary-container/20 text-primary">Operasyonel güven ${confidenceScore.toFixed(2)}</span>
                        <span class="px-3 py-1 rounded-full text-xs bg-surface-container text-on-surface-variant">${escapeHtml(humanizeAction(confidence.action))}</span>
                    </div>
                </div>
                ${decision.final_answer ? `<div class="mt-4 rounded-lg bg-surface-container p-4 border border-outline-variant/20 font-body-sm text-on-surface-variant max-h-40 overflow-y-auto">${formatMarkdownSafe(decision.final_answer)}</div>` : ''}
            </section>

            <section class="grid grid-cols-1 lg:grid-cols-2 gap-4">
                <div class="rounded-lg border border-outline-variant/20 bg-surface p-4">
                    <h5 class="font-label-md text-on-surface mb-3">Sistem kaydı</h5>
                    ${versions.length ? versions.slice(0, 5).map(([key, value]) => `
                        <div class="flex items-center justify-between gap-3 border-b border-outline-variant/20 py-2 last:border-b-0">
                            <span class="font-body-sm text-on-surface-variant">${escapeHtml(humanizeComponent(key))}</span>
                            <span class="font-label-sm text-primary text-right break-all">${escapeHtml(String(value))}</span>
                        </div>`).join('') : '<p class="text-on-surface-variant">Versiyon kaydi yok.</p>'}
                </div>
                <div class="rounded-lg border border-outline-variant/20 bg-surface p-4">
                    <h5 class="font-label-md text-on-surface mb-3">Kaynak desteği</h5>
                    ${citations.length ? citations.map((citation) => `
                        <div class="rounded-lg bg-surface-container p-3 border border-outline-variant/20 mb-2">
                            <p class="font-label-sm text-primary">${escapeHtml(citation.title || citation.source_id || 'source')}</p>
                            <p class="font-body-sm text-on-surface-variant">${escapeHtml(citation.evidence_span || citation.chunk_id || '')}</p>
                        </div>`).join('') : '<p class="text-on-surface-variant">Bu yanıtta ek kaynak kaydı bulunmuyor.</p>'}
                </div>
            </section>

            <section class="rounded-lg border border-outline-variant/20 bg-surface p-4">
                <h5 class="font-label-md text-on-surface mb-4">Kontrol adımları</h5>
                ${events.length ? events.map((event) => `
                    <div class="relative pl-8 pb-5 last:pb-0">
                        <span class="absolute left-0 top-1 w-4 h-4 rounded-full ${event.status === 'blocked' ? 'bg-error' : 'bg-primary'}"></span>
                        <span class="absolute left-[7px] top-5 bottom-0 w-px bg-outline-variant/40 last:hidden"></span>
                        <div class="flex flex-col md:flex-row md:items-center justify-between gap-1">
                            <div>
                                <p class="font-label-md text-on-surface">${escapeHtml(humanizeEventType(event.event_type))}</p>
                                <p class="font-body-sm text-on-surface-variant">${escapeHtml(humanizeComponent(event.component))} · ${escapeHtml(event.status || 'ok')}</p>
                            </div>
                            <p class="font-label-sm text-outline">${escapeHtml(formatDecisionDate(event.created_at))}</p>
                        </div>
                        ${renderMetadata(event.metadata)}
                    </div>`).join('') : '<p class="text-on-surface-variant">Event kaydi yok.</p>'}
            </section>
        </div>`;
}

async function openDecisionTimeline(decisionId) {
    const modal = document.getElementById('decisionTimelineModal');
    const content = document.getElementById('decisionTimelineContent');
    if (!modal || !content || !decisionId) return;

    modal.classList.remove('hidden');
    content.innerHTML = '<p class="text-on-surface-variant">Karar adımları yükleniyor...</p>';
    try {
        const { res, data } = await safeFetchJson(API + `/api/clinical-decisions/${encodeURIComponent(decisionId)}`);
        if (!res.ok || !data?.success) {
            content.innerHTML = `<p class="text-error">${apiHataMesaji(data, 'Karar detayi alinamadi.')}</p>`;
            return;
        }
        content.innerHTML = renderDecisionTimeline(data.decision || {});
    } catch (e) {
        content.innerHTML = `<p class="text-error">${baglantiHatasi(e)}</p>`;
    }
}

function closeDecisionTimeline() {
    const modal = document.getElementById('decisionTimelineModal');
    if (modal) modal.classList.add('hidden');
}

window.openDecisionTimeline = openDecisionTimeline;
window.closeDecisionTimeline = closeDecisionTimeline;

async function loadClinicalKpis(reset = false) {
    const summary = document.getElementById('kpiSummaryGrid');
    if (summary && reset) {
        summary.innerHTML = '<div class="text-center py-16 text-on-surface-variant col-span-full"><div class="loading-dots flex gap-2 justify-center mb-4"><span class="w-3 h-3 rounded-full bg-primary inline-block"></span><span class="w-3 h-3 rounded-full bg-primary inline-block"></span><span class="w-3 h-3 rounded-full bg-primary inline-block"></span></div><p>İzlenebilirlik özeti yükleniyor...</p></div>';
    }
    try {
        const [{ res: kpiRes, data: kpiData }, { res: decisionRes, data: decisionData }] = await Promise.all([
            safeFetchJson(API + '/api/clinical-kpis'),
            safeFetchJson(API + '/api/clinical-decisions?limit=8'),
        ]);
        if (!kpiRes.ok || !kpiData?.success) throw new Error('Klinik özet alınamadı');
        const kpis = kpiData.kpis || {};
        if (summary) {
            summary.innerHTML = [
                renderKpiCard('Toplam karar', kpis.total_decisions || 0, 'fact_check'),
                renderKpiCard('Ortalama guven', Number(kpis.average_confidence || 0).toFixed(2), 'verified'),
                renderKpiCard('Yuksek risk orani', formatPercent(kpis.high_risk_rate), 'warning', Number(kpis.high_risk_rate || 0) > 0 ? 'error' : 'primary'),
                renderKpiCard('Kanit kapsami', formatPercent(kpis.evidence_coverage_rate), 'menu_book'),
            ].join('');
        }
        renderKpiEventBreakdown(kpis);
        if (decisionRes.ok && decisionData?.success) renderClinicalDecisions(decisionData.decisions || []);
        else renderClinicalDecisions([]);
    } catch (e) {
        if (summary) summary.innerHTML = `<div class="text-center py-12 text-error col-span-full">${baglantiHatasi(e)}</div>`;
        renderKpiEventBreakdown([]);
        renderClinicalDecisions([]);
    }
}
function emptyState(icon, title, text) {
    return window.UIUtils?.emptyState?.(icon, title, text) || '';
}

function scoreTone(value, reverse = false) {
    const score = Number(value || 0);
    if (reverse) {
        if (score >= 0.7) return 'status-risk';
        if (score >= 0.35) return 'status-warn';
        return 'status-ok';
    }
    if (score >= 0.75) return 'status-ok';
    if (score >= 0.45) return 'status-warn';
    return 'status-risk';
}

function renderDashboardMetrics(kpis = {}) {
    const root = document.getElementById('dashboardMetricGrid');
    if (!root) return;
    const items = [
        { label: 'Toplam karar', value: kpis.total_decisions || 0, icon: 'fact_check', desc: 'Kaydedilen izlenebilir öneri sayısı' },
        { label: 'Operasyonel güven', value: Number(kpis.average_confidence || 0).toFixed(2), icon: 'verified', desc: 'Karar kayıtlarındaki iç kontrol ortalaması' },
        { label: 'Tahmini risk', value: Number(kpis.average_risk || kpis.average_medical_risk || 0).toFixed(2), icon: 'health_and_safety', desc: 'İç kontrol kayıtlarından türetilir' },
        { label: 'Kaynak kaydı', value: formatPercent(kpis.evidence_coverage_rate), icon: 'menu_book', desc: 'Kaynak/citation bilgisi olan kayıtlar' },
    ];
    root.innerHTML = items.map(item => `
        <article class="card p-5">
            <div class="flex items-start justify-between gap-3">
                <div>
                    <p class="metric-label">${escapeHtml(item.label)}</p>
                    <p class="mt-2 font-display text-3xl font-extrabold text-on-surface">${escapeHtml(String(item.value))}</p>
                    <p class="mt-2 text-sm text-on-surface-variant">${escapeHtml(item.desc)}</p>
                </div>
                <span class="material-symbols-outlined rounded-lg bg-primary-container p-2 text-primary">${item.icon}</span>
            </div>
        </article>`).join('');
}

function renderDashboardDecision(decision) {
    const root = document.getElementById('dashboardLastDecision');
    if (!root) return;
    if (!decision) {
        root.innerHTML = emptyState('timeline', 'Henüz karar kaydı yok', 'CureBot veya plan araçlarını kullandığında burada son kayıt görünür.');
        return;
    }
    const risk = Number(decision.risk_score || 0);
    const confidence = Number(decision.confidence_score || 0);
    const decisionId = String(decision.decision_id || '').replace(/[^a-zA-Z0-9_-]/g, '');
    root.innerHTML = `
        <div class="space-y-3">
            <div>
                <p class="text-xs font-bold uppercase text-outline">Decision ID</p>
                <p class="break-all text-sm font-bold text-primary">${escapeHtml(decision.decision_id || '-')}</p>
            </div>
            <p class="line-clamp-3 text-sm text-on-surface">${escapeHtml(decision.istek || 'Son öneri kaydı')}</p>
            <div class="flex flex-wrap gap-2">
                <span class="status-pill ${scoreTone(risk, true)}">Risk ${risk.toFixed(2)}</span>
                <span class="status-pill ${scoreTone(confidence)}">Operasyonel güven ${confidence.toFixed(2)}</span>
            </div>
            ${decisionId ? `<button onclick="window.GovernanceDashboard.openDecisionTimeline('${decisionId}')" class="btn-secondary px-4 py-2 text-sm font-bold">Detayı gör</button>` : ''}
        </div>`;
}

function renderDailySummary(profile, kpis = {}, histories = []) {
    const root = document.getElementById('dailySummaryGrid');
    if (!root) return;
    const main = profile?.ana_kullanici;
    const meds = main?.ilaclar || [];
    const diseases = main?.hastaliklar || [];
    const allergies = main?.alerjiler || [];
    const lastLab = histories.find(log => String(log.eylem || '').toLowerCase().includes('tahlil'));
    const items = [
        {
            icon: 'person',
            title: 'Profil durumu',
            text: main ? `${main.ad || 'Ana profil'} için ${diseases.length} hastalık, ${allergies.length} alerji kaydı var.` : 'Profil tamamlanınca öneriler daha dikkatli olur.',
            tone: main ? 'status-ok' : 'status-warn'
        },
        {
            icon: 'medication',
            title: 'İlaç-besin dikkati',
            text: meds.length ? `${meds.length} ilaç kaydı önerilerde dikkate alınır.` : 'Kayıtlı ilaç yok. Varsa profil alanından ekleyebilirsin.',
            tone: meds.length ? 'status-info' : 'status-warn'
        },
        {
            icon: 'vaccines',
            title: 'Son tahlil durumu',
            text: lastLab ? `${formatDecisionDate(lastLab.tarih)} tarihinde tahlil özeti oluştu.` : 'Henüz yüklenmiş tahlil özeti bulunmuyor.',
            tone: lastLab ? 'status-ok' : 'status-info'
        },
        {
            icon: 'verified_user',
            title: 'İzlenebilirlik özeti',
            text: `${Number(kpis.average_confidence || 0).toFixed(2)} operasyonel güven, ${formatPercent(kpis.evidence_coverage_rate)} kaynak kaydı.`,
            tone: Number(kpis.total_decisions || 0) ? 'status-ok' : 'status-info'
        },
    ];
    root.innerHTML = items.map(item => `
        <article class="quiet-card p-4">
            <div class="mb-3 flex items-center justify-between gap-3">
                <span class="material-symbols-outlined text-primary">${item.icon}</span>
                <span class="status-pill ${item.tone}">Durum</span>
            </div>
            <h4 class="font-bold text-on-surface">${escapeHtml(item.title)}</h4>
            <p class="mt-1 text-sm leading-6 text-on-surface-variant">${escapeHtml(item.text)}</p>
        </article>`).join('');
}


async function loadDashboardOverview(reset = false) {
    if (reset) {
        const metricRoot = document.getElementById('dashboardMetricGrid');
        if (metricRoot) metricRoot.innerHTML = '<div class="card col-span-full p-6 text-on-surface-variant">Dashboard yükleniyor...</div>';
    }
    try {
        const [profileRes, kpiRes, decisionRes, historyRes] = await Promise.all([
            safeFetchJson(API + '/api/profile/me'),
            safeFetchJson(API + '/api/clinical-kpis'),
            safeFetchJson(API + '/api/clinical-decisions?limit=3'),
            safeFetchJson(API + '/api/history?page=1&limit=5'),
        ]);
        const profile = profileRes.data?.profil || null;
        const kpis = kpiRes.data?.kpis || {};
        const decisions = decisionRes.data?.decisions || [];
        const logs = historyRes.data?.loglar || [];
        renderDashboardMetrics(kpis);
        renderDashboardDecision(decisions[0]);
        renderDailySummary(profile, kpis, logs);
    } catch (e) {
        renderDashboardMetrics({});
        renderDashboardDecision(null);
    }
}


    window.GovernanceDashboard = {
        init() {
            // Initialization if any
        },
        renderKpiCard,
        clampScore,
        scoreTone,
        emptyState,
        formatPercent,
        renderClinicalDecisions,
        renderDecisionTimeline,
        openDecisionTimeline,
        closeDecisionTimeline,
        loadClinicalKpis,
        renderKpiEventBreakdown,
        renderDashboardMetrics,
        renderDashboardDecision,
        loadDashboardOverview,
        renderDailySummary,
        humanizeEventType,
        humanizeComponent,
        humanizeAction,
        formatDecisionDate,
        renderMetadata
    };

    window.loadClinicalKpis = loadClinicalKpis;
    window.openDecisionTimeline = openDecisionTimeline;
    window.closeDecisionTimeline = closeDecisionTimeline;
    window.loadDashboardOverview = loadDashboardOverview;
    window.renderDashboardMetrics = renderDashboardMetrics;
    window.renderDashboardDecision = renderDashboardDecision;
    window.renderDailySummary = renderDailySummary;
    window.emptyState = emptyState;
    window.scoreTone = scoreTone;
    window.renderKpiCard = renderKpiCard;
    window.renderKpiEventBreakdown = renderKpiEventBreakdown;
    window.renderClinicalDecisions = renderClinicalDecisions;
    window.renderDecisionTimeline = renderDecisionTimeline;
})();
