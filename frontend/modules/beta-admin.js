(function () {
  'use strict';
  // Admin token lives only in this module's memory for the session. It is never
  // written to localStorage/sessionStorage, never placed in a URL, and never
  // logged to the console.
  let adminToken = '';
  let connected = false;
  let ixOffset = 0;
  const ixLimit = 50;

  const byId = id => document.getElementById(id);
  const esc = value => String(value == null ? '' : value)
    .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');

  async function api(path) {
    const res = await fetch(path, {
      headers: { Authorization: `Bearer ${adminToken}` },
      credentials: 'same-origin',
    });
    if (res.status === 403) throw new Error('Erişim reddedildi. Anahtarı kontrol edin.');
    if (!res.ok) throw new Error('Veri yüklenemedi (' + res.status + ').');
    return res.json();
  }

  // ---- Tabs ----------------------------------------------------------------
  const tabs = [
    { btn: 'tab-analytics', panel: 'panel-analytics', load: loadAnalytics },
    { btn: 'tab-interactions', panel: 'panel-interactions', load: () => loadInteractions(0) },
    { btn: 'tab-quality', panel: 'panel-quality', load: loadQuality },
  ];
  function selectTab(active) {
    tabs.forEach(tab => {
      const on = tab.btn === active.btn;
      byId(tab.btn).setAttribute('aria-selected', on ? 'true' : 'false');
      byId(tab.panel).classList.toggle('hidden', !on);
    });
    if (connected) active.load();
  }
  tabs.forEach(tab => byId(tab.btn).addEventListener('click', () => selectTab(tab)));

  // ---- Connect -------------------------------------------------------------
  byId('connect').addEventListener('click', async () => {
    adminToken = byId('token').value.trim();
    if (!adminToken) { setStatus('conn-status', 'Bir erişim anahtarı girin.', true); return; }
    setStatus('conn-status', 'Doğrulanıyor...', false);
    try {
      await api('/api/admin/beta/modules');
      connected = true;
      setStatus('conn-status', 'Bağlandı. Anahtar yalnız bellekte tutuluyor.', false);
      await populateModules();
      const active = tabs.find(t => byId(t.btn).getAttribute('aria-selected') === 'true') || tabs[0];
      active.load();
    } catch (err) {
      connected = false;
      setStatus('conn-status', err.message, true);
    }
  });

  function setStatus(id, text, isErr) {
    const el = byId(id);
    el.textContent = text;
    el.classList.toggle('err', !!isErr);
  }

  // ---- Tab 1: Product Analytics (reuse existing admin endpoints) -----------
  async function loadAnalytics() {
    const body = byId('analytics-body');
    body.innerHTML = '<p class="status">Yükleniyor...</p>';
    try {
      const paths = ['summary', 'funnel', 'retention', 'features', 'completions', 'screens', 'ctas'];
      const results = await Promise.all(paths.map(p => api('/api/admin/analytics/' + p)));
      const titles = ['Özet', 'Funnel', 'Retention', 'Özellik kullanımı', 'Tamamlamalar', 'Ekran süreleri', 'Önemli aksiyonlar'];
      body.innerHTML = results.map((data, i) =>
        `<h3>${esc(titles[i])}</h3><pre class="raw">${esc(JSON.stringify(data, null, 2))}</pre>`).join('');
    } catch (err) {
      body.innerHTML = `<p class="status err">${esc(err.message)}</p>`;
    }
  }

  // ---- Tab 2: Interactions -------------------------------------------------
  async function populateModules() {
    try {
      const data = await api('/api/admin/beta/modules');
      const select = byId('f-module');
      const current = select.value;
      select.innerHTML = '<option value="">Tümü</option>' +
        (data.modules || []).map(m => `<option value="${esc(m.module)}">${esc(m.module)} (${m.interactions})</option>`).join('');
      select.value = current;
    } catch (_err) { /* filter dropdown is best-effort */ }
  }

  function buildInteractionsQuery(offset) {
    const params = new URLSearchParams();
    const module = byId('f-module').value;
    const from = byId('f-from').value;
    const to = byId('f-to').value;
    const user = byId('f-user').value.trim();
    const search = byId('f-search').value.trim();
    if (module) params.set('module', module);
    if (from) params.set('date_from', from);
    if (to) params.set('date_to', to);
    if (user) params.set('user', user);
    if (search) params.set('search', search);
    params.set('limit', String(ixLimit));
    params.set('offset', String(offset));
    return params.toString();
  }

  async function loadInteractions(offset) {
    ixOffset = offset;
    setStatus('ix-status', 'Yükleniyor...', false);
    byId('ix-list').innerHTML = '';
    try {
      const data = await api('/api/admin/beta/interactions?' + buildInteractionsQuery(offset));
      const items = data.items || [];
      if (!items.length) {
        setStatus('ix-status', 'Kayıt bulunamadı.', false);
      } else {
        setStatus('ix-status', `${data.total} kayıt bulundu.`, false);
      }
      byId('ix-list').innerHTML = items.map(renderInteraction).join('');
      bindToggles();
      updatePager(data.total || 0);
    } catch (err) {
      setStatus('ix-status', err.message, true);
      updatePager(0);
    }
  }

  function renderInteraction(item) {
    const meta = item.metadata || {};
    const chips = Object.keys(meta).slice(0, 8)
      .map(k => `<span class="chip">${esc(k)}: ${esc(formatMeta(meta[k]))}</span>`).join('');
    return `<div class="ix">
      <div class="meta-line">
        <span>${esc(item.timestamp || '')}</span>
        <span>${esc(item.pseudonymous_user_id || '')}</span>
        <span><b>${esc(item.module || '')}</b></span>
      </div>
      <div class="meta-line" style="margin-top:.3rem">${chips}</div>
      <button class="toggle" data-toggle>İçeriği göster</button>
      <div class="ix-content hidden">
        <pre>${esc(item.input)}</pre>
        <pre>${esc(item.output)}</pre>
      </div>
    </div>`;
  }

  function formatMeta(value) {
    if (Array.isArray(value)) return value.join(', ');
    if (value && typeof value === 'object') return JSON.stringify(value);
    return String(value);
  }

  function bindToggles() {
    byId('ix-list').querySelectorAll('[data-toggle]').forEach(btn => {
      btn.addEventListener('click', () => {
        const content = btn.nextElementSibling;
        const open = !content.classList.contains('hidden');
        content.classList.toggle('hidden', open);
        btn.textContent = open ? 'İçeriği göster' : 'İçeriği gizle';
      });
    });
  }

  function updatePager(total) {
    const start = total ? ixOffset + 1 : 0;
    const end = Math.min(ixOffset + ixLimit, total);
    byId('ix-page').textContent = total ? `${start}–${end} / ${total}` : '';
    byId('ix-prev').disabled = ixOffset <= 0;
    byId('ix-next').disabled = ixOffset + ixLimit >= total;
  }

  byId('f-apply').addEventListener('click', () => loadInteractions(0));
  byId('ix-prev').addEventListener('click', () => { if (ixOffset > 0) loadInteractions(Math.max(0, ixOffset - ixLimit)); });
  byId('ix-next').addEventListener('click', () => loadInteractions(ixOffset + ixLimit));

  // ---- Tab 3: Quality ------------------------------------------------------
  async function loadQuality() {
    const body = byId('quality-body');
    body.innerHTML = '<p class="status">Yükleniyor...</p>';
    try {
      const data = await api('/api/admin/beta/quality');
      const cb = data.curebot || {};
      const kpis = [
        ['Toplam etkileşim', data.total_interactions],
        ['CureBot turn', cb.total_turns],
        ['Benzersiz kullanıcı (CureBot)', cb.unique_users],
        ['Clarification oranı', (cb.clarification_rate ?? 0) + '%'],
        ['Bulgu (finding) oranı', (cb.findings_present_rate ?? 0) + '%'],
        ['Artifact recall oranı', (cb.artifact_recall_rate ?? 0) + '%'],
      ];
      body.innerHTML =
        `<div class="grid">${kpis.map(k => `<div class="kpi"><b>${esc(k[1])}</b><span>${esc(k[0])}</span></div>`).join('')}</div>` +
        `<p class="status">CureBot örneklem: ${esc(cb.sample_size)} turn tarandı (aggregate oranlar bu örneklem üzerinden).</p>` +
        section('Modül dağılımı', tableRows(data.module_distribution, ['module', 'interactions', 'users'], ['Modül', 'Etkileşim', 'Kullanıcı'])) +
        section('Zaman serisi (günlük)', tableRows(data.interactions_over_time, ['date', 'interactions'], ['Tarih', 'Etkileşim'])) +
        section('Response path dağılımı', dictRows(cb.response_path_distribution)) +
        section('Evidence level dağılımı', dictRows(cb.evidence_level_distribution)) +
        section('Target resolution source', dictRows(cb.target_resolution_source_distribution));
    } catch (err) {
      body.innerHTML = `<p class="status err">${esc(err.message)}</p>`;
    }
  }

  function section(title, inner) {
    return `<h3>${esc(title)}</h3>${inner}`;
  }
  function tableRows(rows, keys, headers) {
    if (!rows || !rows.length) return '<p class="status">Veri yok.</p>';
    return `<table><thead><tr>${headers.map(h => `<th>${esc(h)}</th>`).join('')}</tr></thead><tbody>` +
      rows.map(r => `<tr>${keys.map(k => `<td>${esc(r[k])}</td>`).join('')}</tr>`).join('') + '</tbody></table>';
  }
  function dictRows(obj) {
    const entries = Object.entries(obj || {});
    if (!entries.length) return '<p class="status">Veri yok.</p>';
    return `<table><tbody>${entries.map(([k, v]) => `<tr><td>${esc(k)}</td><td>${esc(v)}</td></tr>`).join('')}</tbody></table>`;
  }
})();
