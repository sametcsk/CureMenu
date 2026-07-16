(function() {
function parseListInput(value) {
    return value.split(',').map(s => s.trim()).filter(Boolean);
}

function appendChipValue(inputId, value) {
    const input = document.getElementById(inputId);
    if (!input) return;
    const mevcut = parseListInput(input.value);
    if (!mevcut.includes(value)) {
        mevcut.push(value);
        input.value = mevcut.join(', ');
    }
}

function renderIlacChips(containerId, inputId, ilaclar) {
    const chips = document.getElementById(containerId);
    if (!chips) return;
    chips.innerHTML = '';
    ilaclar.forEach(ilac => {
        const btn = document.createElement('button');
        btn.type = 'button';
        btn.className = 'px-3 py-1 rounded-full border border-outline-variant text-sm hover:bg-secondary-container/30 hover:border-secondary transition-colors ob-chip';
        btn.textContent = ilac;
        btn.onclick = () => {
            appendChipValue(inputId, ilac);
            btn.classList.add('bg-secondary-container/40', 'border-secondary');
        };
        chips.appendChild(btn);
    });
}

function renderGuvenlikBadge(guvenlik, feragatKisa) {
    if (!guvenlik) return '';
    let badge = '';
    if (guvenlik.onayli === true) {
        badge = `<div class="flex items-center gap-1.5 mt-2 px-2 py-1 bg-primary-container/20 text-primary rounded-lg text-[11px] font-medium">
            <span class="material-symbols-outlined text-[14px]" style="font-variation-settings:'FILL' 1">verified</span>Guardrail onaylı</div>`;
    } else if (guvenlik.onayli === false && guvenlik.tip === 'yemek_reddedildi') {
        badge = `<div class="flex items-center gap-1.5 mt-2 px-2 py-1 bg-error-container text-on-error-container rounded-lg text-[11px] font-medium">
            <span class="material-symbols-outlined text-[14px]">block</span>Güvenlik uyarısı</div>`;
    }
    const aciklama = guvenlik.aciklama
        ? `<p class="mt-2 text-[11px] text-outline leading-snug border-t border-outline-variant/20 pt-2">${escapeHtml(guvenlik.aciklama)}</p>`
        : '';
    const feragat = feragatKisa
        ? `<p class="mt-1 text-[10px] text-outline/80 italic">${escapeHtml(feragatKisa)}</p>`
        : '';
    return badge + aciklama + feragat;
}

async function loadProfile() {
    const user = window.AuthManager.getUser();
    try {
        const { res, data } = await safeFetchJson(API + '/api/profile/me');
        if (!res.ok || !data) { renderEmptyFamily(); return null; }
        window.currentProfile = data.profil;
        renderFamily(data.profil);
        updatePlanDropdown(data.profil);
        renderHealthProfile(data.profil);
        renderMedicationOverview(data.profil);

        const hasMain = !!data.profil.ana_kullanici;
        localStorage.setItem('cm_has_profile', hasMain ? 'true' : 'false');
        return data.profil;
    } catch (e) { console.error(e); renderEmptyFamily(); return null; }
}

async function checkOnboarding() {
    if (localStorage.getItem('cm_onboarding_done') === 'true') return;
    if (localStorage.getItem('cm_has_profile') === 'true') {
        localStorage.setItem('cm_onboarding_done', 'true');
        return;
    }
    await showOnboarding();
}

async function showOnboarding() {
    const metinler = await loadPublicMetinler();
    const modal = document.getElementById('onboardingModal');
    const user = window.AuthManager.getUser();
    const title = modal?.querySelector('h3');
    if (title) title.textContent = "CureMenu'ye hoş geldin";
    const subtitle = modal?.querySelector('h3 + p');
    if (subtitle) subtitle.textContent = 'Birkaç bilgiyle önerileri daha dikkatli hale getirebiliriz.';
    const submit = modal?.querySelector('[onclick="window.ProfileManager.completeOnboarding()"]');
    if (submit) submit.textContent = 'Profilimi oluştur ve başla';
    document.getElementById('ob_ad').value = user.kullanici_adi || '';
    document.getElementById('ob_feragat').textContent = metinler.tibbi_feragat || metinler.tibbi_feragat_kisa;

    const chips = document.getElementById('ob_hastalik_chips');
    chips.innerHTML = '';
    HASTALIK_SECENEKLERI.forEach(h => {
        const btn = document.createElement('button');
        btn.type = 'button';
        btn.className = 'px-3 py-1 rounded-full border border-outline-variant text-sm hover:bg-primary-container/20 hover:border-primary transition-colors ob-chip';
        btn.textContent = h;
        btn.onclick = () => {
            const input = document.getElementById('ob_hastaliklar');
            const mevcut = input.value.split(',').map(s => s.trim()).filter(Boolean);
            if (!mevcut.includes(h)) {
                mevcut.push(h);
                input.value = mevcut.join(', ');
            }
            btn.classList.add('bg-primary-container/30', 'border-primary');
        };
        chips.appendChild(btn);
    });

    const sorular = document.getElementById('ob_ornek_sorular');
    sorular.innerHTML = '';
    (metinler.ornek_sorular || []).forEach(s => {
        const span = document.createElement('span');
        span.className = 'px-3 py-1 bg-surface-container-low rounded-full text-xs text-on-surface-variant border border-outline-variant/30';
        span.textContent = '"' + s + '"';
        sorular.appendChild(span);
    });

    renderIlacChips('ob_ilac_chips', 'ob_ilaclar', metinler.yaygin_ilaclar || ILAC_SECENEKLERI_FALLBACK);

    modal.classList.remove('hidden');
}

function openProfileEditor() {
    const profil = window.currentProfile?.ana_kullanici;
    if (!profil) {
        showOnboarding();
        return;
    }
    const modal = document.getElementById('onboardingModal');
    if (!modal) return;
    const setValue = (id, value) => {
        const el = document.getElementById(id);
        if (el) el.value = value ?? '';
    };
    setValue('ob_ad', profil.ad || window.AuthManager.getUser().kullanici_adi || '');
    setValue('ob_yas', profil.yas || 35);
    setValue('ob_cinsiyet', profil.cinsiyet || 'kadın');
    setValue('ob_hedef', profil.hedef || 'Sağlıklı Yaşam (Genel)');
    setValue('ob_hastaliklar', (profil.hastaliklar || []).join(', '));
    setValue('ob_alerjiler', (profil.alerjiler || []).join(', '));
    setValue('ob_ilaclar', (profil.ilaclar || []).join(', '));
    const title = modal.querySelector('h3');
    if (title) title.textContent = 'Sağlık bilgilerini güncelle';
    const subtitle = modal.querySelector('h3 + p');
    if (subtitle) subtitle.textContent = 'Yeni hastalık, alerji veya ilaç bilgisi eklediğinde öneriler daha dikkatli değerlendirilir.';
    const submit = modal.querySelector('[onclick="window.ProfileManager.completeOnboarding()"]');
    if (submit) submit.textContent = 'Bilgilerimi kaydet';
    modal.classList.remove('hidden');
}

async function completeOnboarding() {
    const user = window.AuthManager.getUser();
    const ad = document.getElementById('ob_ad').value.trim();
    const nameRegex = /^[A-Za-z\u00C7\u00E7\u011E\u011F\u0130\u0131\u00D6\u00F6\u015E\u015F\u00DC\u00FC\s]+$/;
    if (!ad || !nameRegex.test(ad) || ad.length > 40) {
        alert('Lütfen geçerli bir ad girin (sadece harfler, maks 40 karakter).');
        return;
    }

    const body = {
        kullanici_adi: user.kullanici_adi,
        ad,
        yas: parseInt(document.getElementById('ob_yas').value) || 30,
        cinsiyet: document.getElementById('ob_cinsiyet').value,
        hastaliklar: parseListInput(document.getElementById('ob_hastaliklar').value),
        alerjiler: parseListInput(document.getElementById('ob_alerjiler').value),
        ilaclar: parseListInput(document.getElementById('ob_ilaclar').value),
        hedef: document.getElementById('ob_hedef').value,
    };

    try {
        const res = await fetch(API + '/api/profile/save', {
            method: 'POST', headers: { 'Content-Type': 'application/json' }, credentials: 'include', body: JSON.stringify(body)
        });
        const data = await res.json();
        if (res.ok && data.success) {
            localStorage.setItem('cm_has_profile', 'true');
            localStorage.setItem('cm_onboarding_done', 'true');
            document.getElementById('onboardingModal').classList.add('hidden');
            await loadProfile();
            openCureBotWidget();
            const metinler = await loadPublicMetinler();
            const ornek = (metinler.ornek_sorular || [])[0];
            if (ornek) {
                openCureBotWidget(ornek);
            }
        } else {
            alert(apiHataMesaji(data, 'Profil kaydedilemedi.'));
        }
    } catch (e) {
        alert(baglantiHatasi(e));
    }
}

function updatePlanDropdown(profil) {
    const sel = document.getElementById('planTarget');
    sel.innerHTML = '<option value="kendim">Kendim İçin</option>';
    (profil.aile_uyeleri || []).forEach(u => {
        const ad = escapeHtml(u.ad);
        sel.innerHTML += `<option value="${ad}">${ad} İçin</option>`;
    });
    if ((profil.aile_uyeleri || []).length > 0) {
        sel.innerHTML += '<option value="aile">Tüm Aile İçin</option>';
    }
    // CureBot dropdown
    const chatSel = document.getElementById('chatTarget');
    if (chatSel) {
    chatSel.innerHTML = '<option value="kendim">Kendim İçin</option>';
    (profil.aile_uyeleri || []).forEach(u => {
        chatSel.innerHTML += `<option value="${escapeHtml(u.ad)}">🧑 ${escapeHtml(u.ad)} İçin</option>`;
    });
    if ((profil.aile_uyeleri || []).length > 0) {
        chatSel.innerHTML += '<option value="aile">👪 Tüm Aile İçin</option>';
    }

    // Menü Tarayıcı dropdown
    }
    const menuSel = document.getElementById('menuTarget');
    if (menuSel) {
        menuSel.innerHTML = '<option value="kendim">Kendim İçin</option>';
        (profil.aile_uyeleri || []).forEach(u => {
            menuSel.innerHTML += `<option value="${escapeHtml(u.ad)}">${escapeHtml(u.ad)} İçin</option>`;
        });
        if ((profil.aile_uyeleri || []).length > 0) {
            menuSel.innerHTML += '<option value="aile">Tüm Aile İçin</option>';
        }
    }

    // Buzdolabı dropdown
    const fridgeSel = document.getElementById('fridgeTarget');
    if (fridgeSel) {
        fridgeSel.innerHTML = '<option value="kendim">Kendim İçin</option>';
        (profil.aile_uyeleri || []).forEach(u => {
            fridgeSel.innerHTML += `<option value="${escapeHtml(u.ad)}">${escapeHtml(u.ad)} İçin</option>`;
        });
        if ((profil.aile_uyeleri || []).length > 0) {
            fridgeSel.innerHTML += '<option value="aile">Tüm Aile İçin</option>';
        }
    }

    // Tahlillerim dropdown
    const tahlilSel = document.getElementById('tahlilTarget');
    if (tahlilSel) {
        tahlilSel.innerHTML = '<option value="kendim">Kendim İçin</option>';
        (profil.aile_uyeleri || []).forEach(u => {
            tahlilSel.innerHTML += `<option value="${escapeHtml(u.ad)}">${escapeHtml(u.ad)} İçin</option>`;
        });
        if ((profil.aile_uyeleri || []).length > 0) {
            tahlilSel.innerHTML += '<option value="aile">Tüm Aile İçin</option>';
        }
    }
}

async function addMember() {
    const user = window.AuthManager.getUser();
    const hasProfile = localStorage.getItem('cm_has_profile');
    const endpoint = hasProfile === 'true' ? '/api/family/add' : '/api/profile/save';

    const ad_val = document.getElementById('m_ad').value.trim();
    const nameRegex = /^[A-Za-z\u00C7\u00E7\u011E\u011F\u0130\u0131\u00D6\u00F6\u015E\u015F\u00DC\u00FC\s]+$/;
    if (!ad_val || !nameRegex.test(ad_val) || ad_val.length > 40) {
        alert('Lütfen geçerli bir ad girin (sadece harfler, maks 40 karakter).');
        return;
    }

    const body = {
        ad: ad_val,
        yas: parseInt(document.getElementById('m_yas').value) || 30,
        cinsiyet: document.getElementById('m_cinsiyet').value,
        boy: parseInt(document.getElementById('m_boy').value) || 170,
        kilo: parseFloat(document.getElementById('m_kilo').value) || 70,
        hastaliklar: parseListInput(document.getElementById('m_hastaliklar').value),
        alerjiler: parseListInput(document.getElementById('m_alerjiler').value),
        ilaclar: parseListInput(document.getElementById('m_ilaclar').value),
        hedef: document.getElementById('m_hedef').value,
        genetik_hastaliklar: parseListInput(document.getElementById('m_genetik').value),
        tibbi_gecmis: document.getElementById('m_tibbi').value.trim() || null,
    };

    try {
        const { res, data } = await safeFetchJson(API + endpoint, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(body),
        });
        if (data && data.success) {
            if (hasProfile !== 'true') {
                localStorage.setItem('cm_has_profile', 'true');
                localStorage.setItem('cm_onboarding_done', 'true');
            }
            document.getElementById('addModal').classList.add('hidden');
            // Formu temizle
            ['m_ad', 'm_yas', 'm_hastaliklar', 'm_alerjiler', 'm_ilaclar', 'm_genetik', 'm_tibbi'].forEach(id => document.getElementById(id).value = '');
            loadProfile();
        } else { alert(apiHataMesaji(data, 'Hata oluştu')); }
    } catch (e) { alert('Bağlantı kurulamadı. Lütfen birazdan tekrar deneyin.'); }
}

async function deleteMember(uyeId) {
    if (!confirm('Bu üyeyi silmek istediğinize emin misiniz?')) return;
    const user = window.AuthManager.getUser();
    try {
        const { res, data } = await safeFetchJson(API + '/api/family/' + uyeId, { method: 'DELETE' });
        if (res.ok && data?.success) loadProfile();
        else alert(apiHataMesaji(data, 'Üye silinemedi.'));
    } catch (e) { alert(baglantiHatasi(e)); }
}

function renderHealthProfile(profil) {
    const root = document.getElementById('healthProfileSummary');
    if (root) root.remove(); // Remove the summary section as requested
}

function renderEmptyFamily() {
    const grid = document.getElementById('familyGrid');
    if (!grid) return;
    grid.innerHTML = emptyState('group_add', 'Henüz profil yok', 'İlk profil oluşturulduğunda veya aile üyesi eklendiğinde burada görünür.');
}

function renderFamily(profil) {
    const grid = document.getElementById('familyGrid');
    if (!grid) return;
    grid.innerHTML = '';
    const members = [];
    if (profil?.ana_kullanici) members.push({ ...profil.ana_kullanici, isMain: true });
    (profil?.aile_uyeleri || []).forEach(u => members.push({ ...u, isMain: false }));
    if (!members.length) {
        renderEmptyFamily();
        return;
    }

    grid.innerHTML = members.map(member => {
        const diseases = member.hastaliklar || [];
        const allergies = member.alerjiler || [];
        const meds = member.ilaclar || [];
        const memberId = escapeHtml(member.id || '');
        const isMain = member.isMain;
        return `
            <article class="rounded-xl border border-outline-variant bg-surface-container-low p-6 transition hover:border-primary">
                <div class="flex items-center justify-between">
                    <h4 class="font-display text-xl font-bold text-on-surface">${escapeHtml(member.ad || 'İsimsiz')}</h4>
                    <span class="rounded-full bg-primary-container px-3 py-1 text-xs font-bold text-primary">${isMain ? 'Ana Profil' : 'Aile Üyesi'}</span>
                </div>
                <div class="mt-4 grid gap-4">
                    <div><p class="metric-label font-bold">Hastalıklar</p><div class="mt-2 flex flex-wrap gap-2">${diseases.length ? diseases.map(v => `<span class="status-pill status-warn">${escapeHtml(v)}</span>`).join('') : '<span class="text-sm text-on-surface-variant">Kayıt yok</span>'}</div></div>
                    <div><p class="metric-label font-bold">Alerjiler</p><div class="mt-2 flex flex-wrap gap-2">${allergies.length ? allergies.map(v => `<span class="status-pill status-risk">${escapeHtml(v)}</span>`).join('') : '<span class="text-sm text-on-surface-variant">Kayıt yok</span>'}</div></div>
                    <div><p class="metric-label font-bold">İlaçlar</p><div class="mt-2 flex flex-wrap gap-2">${meds.length ? meds.map(v => `<span class="status-pill status-info">${escapeHtml(v)}</span>`).join('') : '<span class="text-sm text-on-surface-variant">Kayıt yok</span>'}</div></div>
                </div>
            </article>`;
    }).join('');
}

function renderMedicationOverview(profil) {
    const listRoot = document.getElementById('medicationList');
    const riskRoot = document.getElementById('medicationRiskPanel');
    if (!listRoot && !riskRoot) return;

    const members = [];
    if (profil?.ana_kullanici) members.push({ ...profil.ana_kullanici, scope: 'Ana profil' });
    (profil?.aile_uyeleri || []).forEach(member => members.push({ ...member, scope: 'Aile profili' }));
    const rows = members.flatMap(member => (member.ilaclar || []).map(ilac => ({ ilac, member })));

    if (listRoot) {
        listRoot.innerHTML = rows.length
            ? rows.map(row => `
                <article class="rounded-lg border border-outline-variant bg-surface-container-low p-4">
                    <p class="font-bold text-on-surface">${escapeHtml(row.ilac)}</p>
                    <p class="mt-1 text-sm text-on-surface-variant">${escapeHtml(row.member.ad || row.member.scope)} · ${escapeHtml(row.member.scope)}</p>
                </article>`).join('')
            : emptyState('medication', 'Kayıtlı ilaç yok', 'İlaç eklediğinde yemek önerileri buna göre daha dikkatli kontrol edilir.');
    }

    if (riskRoot) {
        riskRoot.innerHTML = `
            <div class="rounded-lg border border-outline-variant bg-surface-container-low p-4">
                <p class="font-bold text-on-surface">Dikkat edilmesi gereken eşleşmeler</p>
                <p class="mt-1 text-sm leading-6 text-on-surface-variant">İlaçlarınla birlikte sakıncalı olabilecek bir yiyecek fark edilirse burada sade bir uyarı olarak görünür.</p>
            </div>
            <div class="rounded-lg border border-outline-variant bg-surface-container-low p-4">
                <p class="font-bold text-on-surface">Kaynaklı açıklamalar</p>
                <p class="mt-1 text-sm leading-6 text-on-surface-variant">Bir öneri kaynak bilgisiyle desteklenirse detayını karar geçmişinde görebilirsin. Veri yoksa CureMenu bunu varmış gibi göstermez.</p>
            </div>`;
    }
}

    window.ProfileManager = {
        init() {
        },
        parseListInput,
        appendChipValue,
        renderIlacChips,
        renderGuvenlikBadge,
        loadProfile,
        checkOnboarding,
        showOnboarding,
        completeOnboarding,
        openProfileEditor,
        updatePlanDropdown,
        addMember,
        deleteMember,
        renderHealthProfile,
        renderEmptyFamily,
        renderFamily,
        renderMedicationOverview
    };
    window.ProfileFamilyManager = window.ProfileManager;

    window.loadProfile = loadProfile;
    window.checkOnboarding = checkOnboarding;
    window.showOnboarding = showOnboarding;
    window.openProfileEditor = openProfileEditor;
    window.completeOnboarding = completeOnboarding;
    window.updatePlanDropdown = updatePlanDropdown;
    window.addMember = addMember;
    window.deleteMember = deleteMember;
    window.renderHealthProfile = renderHealthProfile;
    window.renderEmptyFamily = renderEmptyFamily;
    window.renderFamily = renderFamily;
    window.renderMedicationOverview = renderMedicationOverview;
})();
