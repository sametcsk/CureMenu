/**
 * CureMenu - Weekly Actions Module
 * Handles weekly-plan action modal behavior: recipe, snack, alternatives,
 * gamification and small completion feedback.
 */

(function() {
    let weeklyActionEventsBound = false;

    function getActionModal() {
        const modal = document.getElementById('actionModal');
        const title = document.getElementById('actionModalTitle');
        const subtitle = document.getElementById('actionModalSubtitle');
        const content = document.getElementById('actionModalContent');
        if (!modal || !title || !subtitle || !content) return null;
        return { modal, title, subtitle, content };
    }

    function openModal(titleHtml, subtitleText, contentHtml) {
        const refs = getActionModal();
        if (!refs) return null;
        refs.title.innerHTML = titleHtml;
        refs.subtitle.textContent = subtitleText;
        refs.content.innerHTML = contentHtml;
        refs.modal.classList.remove('hidden');
        refs.modal.classList.add('flex');
        return refs;
    }

    function closeActionModal() {
        const modal = document.getElementById('actionModal');
        modal?.classList.add('hidden');
        modal?.classList.remove('flex');
    }

    function bindWeeklyActionEvents() {
        if (weeklyActionEventsBound) return;
        weeklyActionEventsBound = true;
        document.addEventListener('click', (event) => {
            const trigger = event.target.closest('[data-weekly-action]');
            if (!trigger) return;
            const action = trigger.dataset.weeklyAction;
            if (action === 'close') {
                event.preventDefault();
                closeActionModal();
            } else if (action === 'snack') {
                event.preventDefault();
                requestSnack();
            } else if (action === 'recipe') {
                event.preventDefault();
                askRecipeForWeeklyPlan(trigger.dataset.meal || '');
            } else if (action === 'alternative') {
                event.preventDefault();
                requestAlternativeMeal(trigger.dataset.meal || '');
            }
        });
    }

    function loadingHtml(colorClass, text) {
        return `<div class="py-12 text-center">
            <div class="loading-dots flex gap-2 justify-center mb-4">
                <span class="w-3 h-3 rounded-full ${colorClass} inline-block"></span>
                <span class="w-3 h-3 rounded-full ${colorClass} inline-block"></span>
                <span class="w-3 h-3 rounded-full ${colorClass} inline-block"></span>
            </div>
            <p class="text-on-surface-variant font-body-md">${window.escapeHtml(text)}</p>
        </div>`;
    }

    function selectedPlanTarget() {
        return document.getElementById('planTarget')?.value || 'kendim';
    }

    async function askRecipeForWeeklyPlan(mealText) {
        const refs = openModal(
            '<span class="material-symbols-outlined align-middle mr-2">restaurant</span> Tarif hazırlanıyor...',
            `"${mealText}" için detaylı tarif alınıyor.`,
            loadingHtml('bg-primary', 'Tarif bilgileri hazırlanıyor...')
        );
        if (!refs) return;

        try {
            const { data } = await safeFetchJson(API + '/api/plan-action', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    action_type: 'recipe',
                    meal_text: mealText,
                    kimin_icin: selectedPlanTarget()
                })
            });

            if (data && data.success) {
                refs.title.innerHTML = '<span class="material-symbols-outlined align-middle mr-2">menu_book</span> Tarif: ' + escapeHtml(mealText);
                refs.subtitle.textContent = 'Afiyet olsun. Yemeğin tarifi hazır.';
                refs.content.innerHTML = `<div class="prose max-w-none text-on-surface">${formatMarkdownSafe(data.result)}</div>`;
                return;
            }
            refs.content.innerHTML = `<div class="p-6 text-center text-error font-bold">Tarif alınamadı: ${escapeHtml(data?.detail || 'Bilinmeyen hata')}</div>`;
        } catch (_e) {
            refs.content.innerHTML = '<div class="p-6 text-center text-error font-bold">Bağlantı hatası oluştu.</div>';
        }
    }

    async function requestSnack() {
        const today = new Date().toLocaleDateString('tr-TR', { weekday: 'long' });
        const refs = openModal(
            '<span class="material-symbols-outlined align-middle mr-2 text-warning">nutrition</span> Atıştırmalık önerisi aranıyor...',
            `Bugün ${today}. Günlük planınıza uygun bir ara öğün bakılıyor.`,
            loadingHtml('bg-warning', 'Profilinize uygun seçenekler hazırlanıyor...')
        );
        if (!refs) return;

        try {
            const { data } = await safeFetchJson(API + '/api/plan-action', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    action_type: 'snack',
                    meal_text: 'Snack Request',
                    plan_text: window.currentPlanText || 'Henüz plan oluşturulmadı.',
                    kimin_icin: selectedPlanTarget()
                })
            });

            if (data && data.success && data.result) {
                const suggestions = data.result.snack_onerileri || 'Uygun atıştırmalık önerisi bulunamadı.';
                refs.title.innerHTML = '<span class="material-symbols-outlined align-middle mr-2 text-success">check_circle</span> Atıştırmalık hazır';
                refs.subtitle.textContent = 'Profilinize uygun seçenekler bulundu.';
                refs.content.innerHTML = `
                    ${data.result.warning ? `<div class="mb-4 rounded-xl border border-warning/30 bg-warning-container p-4 text-sm text-on-warning-container">${escapeHtml(data.result.warning)}</div>` : ''}
                    <div class="bg-surface-container-low border border-outline-variant p-5 rounded-xl mb-4">
                        <div class="prose prose-sm md:prose-base max-w-none text-on-surface">${formatMarkdownSafe(suggestions)}</div>
                    </div>`;
                return;
            }
            throw new Error(data?.detail || 'Sunucu yanıt vermedi.');
        } catch (err) {
            refs.title.innerHTML = '<span class="material-symbols-outlined align-middle mr-2 text-error">error</span> Öneri alınamadı';
            refs.subtitle.textContent = 'Beklenmeyen bir hata oluştu.';
            refs.content.innerHTML = `<div class="py-12 text-center text-error"><span class="material-symbols-outlined text-4xl mb-2">warning</span><p>${escapeHtml(err.message)}</p></div>`;
        }
    }

    function persistUpdatedPlan(newPlanText) {
        window.currentPlanText = newPlanText;
        const fallbackUser = typeof getUser === 'function' ? getUser() : null;
        const user = window.AuthManager?.getUser?.() || fallbackUser;
        if (user?.telefon) {
            localStorage.setItem('cm_saved_plan_json_' + user.telefon, newPlanText);
            localStorage.setItem('cm_saved_plan_' + user.telefon, newPlanText);
        }
        window.renderSavedPlan?.(newPlanText);
    }

    function applyMealChanges(planText, changedMeals) {
        try {
            const plan = JSON.parse(planText);
            (plan.days || []).forEach(day => {
                ['breakfast', 'lunch', 'dinner'].forEach(key => {
                    changedMeals.forEach(item => {
                        if (day[key] === item.eski) day[key] = item.yeni;
                    });
                });
                if (Array.isArray(day.snacks)) {
                    day.snacks = day.snacks.map(snack => {
                        const change = changedMeals.find(item => item.eski === snack);
                        return change?.yeni || snack;
                    });
                }
            });
            return JSON.stringify(plan);
        } catch (_e) {
            let updated = planText;
            changedMeals.forEach(item => {
                if (item.eski && item.yeni) updated = updated.replace(item.eski, item.yeni);
            });
            return updated;
        }
    }

    async function requestAlternativeMeal(mealText) {
        const refs = openModal(
            '<span class="material-symbols-outlined align-middle mr-2 text-warning">swap_horiz</span> Alternatif aranıyor...',
            `"${mealText}" yerine size daha uygun bir öğün bakılıyor.`,
            loadingHtml('bg-warning', 'Profilinize uygun alternatif hazırlanıyor...')
        );
        if (!refs) return;

        try {
            const { data } = await safeFetchJson(API + '/api/plan-action', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    action_type: 'alternative',
                    meal_text: mealText,
                    plan_text: window.currentPlanText || '',
                    kimin_icin: selectedPlanTarget()
                })
            });

            if (!(data && data.success && data.result)) {
                refs.content.innerHTML = `<div class="p-6 text-center text-error font-bold">Alternatif bulunamadı: ${escapeHtml(data?.detail || 'Bilinmeyen hata')}</div>`;
                return;
            }

            const changedMeals = data.result.degisen_ogunler || [];
            const explanation = data.result.aciklama || '';
            if (changedMeals.length === 0 && data.result.yeni_ogun) {
                changedMeals.push({ eski: mealText, yeni: data.result.yeni_ogun });
            }

            refs.title.innerHTML = '<span class="material-symbols-outlined align-middle mr-2 text-success">check_circle</span> Plan güncellendi';
            refs.subtitle.textContent = 'Öğün alternatifiniz hazırlandı.';

            const mealHtml = changedMeals.map(item => `<div class="mb-3 border-b border-success/10 pb-3 last:border-0 last:pb-0">
                <p class="text-xs text-on-surface-variant line-through mb-1">${escapeHtml(item.eski || '')}</p>
                <h4 class="font-bold text-success text-[15px]">${escapeHtml(item.yeni || '')}</h4>
            </div>`).join('');

            refs.content.innerHTML = `
                ${data.result.warning ? `<div class="mb-4 rounded-xl border border-warning/30 bg-warning-container p-4 text-sm text-on-warning-container">${escapeHtml(data.result.warning)}</div>` : ''}
                <div class="bg-success-container/30 border border-success/20 p-5 rounded-xl mb-4">
                    <h4 class="font-bold text-success text-sm mb-3 opacity-80 uppercase tracking-wider">Değişen öğünler</h4>
                    ${mealHtml}
                    <div class="mt-4 pt-4 border-t border-success/20 prose prose-sm max-w-none text-on-surface">${formatMarkdownSafe(explanation)}</div>
                </div>`;

            if (window.currentPlanText) {
                const newPlanText = applyMealChanges(window.currentPlanText, changedMeals);
                persistUpdatedPlan(newPlanText);
            }
        } catch (_e) {
            refs.content.innerHTML = '<div class="p-6 text-center text-error font-bold">Bağlantı hatası oluştu.</div>';
        }
    }

    function recalculateGamification() {
        const tableRows = document.querySelectorAll('#planResult tr');
        let totalScore = 0;
        let totalCompletedDays = 0;

        tableRows.forEach(row => {
            const checkboxes = row.querySelectorAll('input[type="checkbox"]');
            if (checkboxes.length === 0) return;

            let checkedCount = 0;
            checkboxes.forEach(cb => {
                if (cb.checked) {
                    checkedCount += 1;
                    totalScore += 10;
                }
            });

            if (checkedCount > 0 && checkedCount === checkboxes.length) {
                totalCompletedDays += 1;
                totalScore += 20;
            }

            const dayCell = row.querySelector('td:first-child');
            if (dayCell) {
                let progressSpan = dayCell.querySelector('.day-progress');
                if (!progressSpan) {
                    progressSpan = document.createElement('div');
                    dayCell.appendChild(progressSpan);
                }
                progressSpan.className = 'day-progress text-[11px] font-bold mt-2 py-1 px-2 rounded ' +
                    (checkedCount === checkboxes.length ? 'bg-success/20 text-success' : 'bg-outline-variant/20 text-on-surface-variant');
                progressSpan.textContent = `Durum: ${checkedCount}/${checkboxes.length}`;
            }
        });

        const uiScore = document.getElementById('uiMealScore');
        const uiStreak = document.getElementById('uiMealStreak');
        if (uiScore) uiScore.textContent = totalScore;
        if (uiStreak) uiStreak.textContent = totalCompletedDays;
    }

    function triggerConfetti(element) {
        if (!element) return;
        const particle = document.createElement('div');
        particle.className = 'absolute text-[24px] pointer-events-none transition-all duration-700 ease-out z-50';
        particle.textContent = '+';

        const rect = element.getBoundingClientRect();
        particle.style.left = rect.left + window.scrollX + 'px';
        particle.style.top = rect.top + window.scrollY - 20 + 'px';
        document.body.appendChild(particle);

        setTimeout(() => {
            particle.style.transform = 'translateY(-40px) scale(1.5)';
            particle.style.opacity = '0';
        }, 50);

        setTimeout(() => particle.remove(), 750);
    }

    window.WeeklyActions = {
        bindWeeklyActionEvents,
        askRecipeForWeeklyPlan,
        requestSnack,
        requestAlternativeMeal,
        closeActionModal,
        recalculateGamification,
        triggerConfetti
    };

    window.recalculateGamification = recalculateGamification;
    window.triggerConfetti = triggerConfetti;
    bindWeeklyActionEvents();
})();
