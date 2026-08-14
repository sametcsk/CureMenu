(function () {
    'use strict';
    const byId = id => document.getElementById(id);
    async function load(path, token) {
        const res = await fetch(path, { headers: { Authorization: `Bearer ${token}` }, credentials: 'same-origin' });
        if (!res.ok) throw new Error('Erişim doğrulanamadı veya veri yüklenemedi.');
        return res.json();
    }
    byId('load').addEventListener('click', async () => {
        const token = byId('token').value;
        byId('status').textContent = 'Yükleniyor...';
        try {
            const [summary, funnel, retention, features, completions, screens, ctas] = await Promise.all(
                ['/summary', '/funnel', '/retention', '/features', '/completions', '/screens', '/ctas'].map(path => load('/api/admin/analytics' + path, token))
            );
            byId('summary').textContent = JSON.stringify(summary, null, 2);
            byId('funnel').textContent = JSON.stringify(funnel.funnel, null, 2);
            const retentionDisplay = Object.fromEntries(Object.entries(retention.retention).map(([day, value]) => [day, value.rate === null ? { ...value, rate: 'N/A / henüz ölçülemez' } : value]));
            byId('retention').textContent = JSON.stringify(retentionDisplay, null, 2);
            byId('features').textContent = JSON.stringify(features.features, null, 2);
            byId('completions').textContent = JSON.stringify(completions.completions, null, 2);
            byId('screens').textContent = JSON.stringify(screens.screens, null, 2);
            byId('ctas').textContent = JSON.stringify(ctas.ctas, null, 2);
            byId('status').textContent = 'Güncellendi.';
        } catch (err) {
            byId('status').textContent = err.message;
        }
    });
})();
