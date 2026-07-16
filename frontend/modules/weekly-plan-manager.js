/**
 * CureMenu - Weekly Plan Manager Module
 * Handles UI interactions, API calls and rendering for Weekly Plans
 */

window.WeeklyPlanManager = {
    init() {
        const generateBtn = document.getElementById('generatePlanBtn');
        if (generateBtn) {
            generateBtn.addEventListener('click', () => this.generatePlan());
        }

        // The regenerate button is created dynamically inside renderPlan

        this.loadExistingPlan();
    },

    async generatePlan() {
        if (!window.AuthManager) return;

        try {
            const user = window.AuthManager.requireAuth();
            if (!user) return; // Will redirect to login

            const kimin_icin = document.getElementById('planTarget')?.value || 'kendim';
            this.showLoading();

            const isRegeneration = localStorage.getItem('cm_saved_plan_json_' + user.telefon) !== null;

            const { res, data } = await safeFetchJson(API + '/api/weekly-plan', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ kimin_icin, is_regeneration: isRegeneration })
            });

            if (data && (data.ok || data.success) && data.plan) {
                localStorage.setItem('cm_saved_plan_json_' + user.telefon, JSON.stringify(data.plan));
                this.renderPlan(data.plan);
            } else {
                this.showError(data?.error?.message || "Plan oluşturulamadı. Lütfen daha sonra tekrar deneyin.");
            }
        } catch (e) {
            console.error("WeeklyPlanManager error:", e);
            this.showError("Bağlantı kurulamadı. Lütfen internet bağlantınızı kontrol edip tekrar deneyin.");
        }
    },

    loadExistingPlan() {
        if (!window.AuthManager) return;
        const user = window.AuthManager.getUser();
        if (!user) return;

        const savedPlanStr = localStorage.getItem('cm_saved_plan_json_' + user.telefon);
        if (savedPlanStr) {
            try {
                const plan = JSON.parse(savedPlanStr);
                this.renderPlan(plan);
            } catch (e) {
                this.renderEmptyState();
            }
        } else {
            this.renderEmptyState();
        }
    },

    renderPlan(plan) {
        const resultContainer = document.getElementById('planResult');
        if (!resultContainer || !plan.days) return;

        let html = `
            <div class="mb-4">
                <p class="text-sm text-on-surface-variant mb-2">${window.escapeHtml ? escapeHtml(plan.summary) : plan.summary}</p>
        `;

        if (plan.warnings && plan.warnings.length > 0) {
            html += `<div class="bg-error-container text-on-error-container p-3 rounded-lg mb-4 text-xs font-medium">`;
            plan.warnings.forEach(w => {
                html += `<p>⚠️ ${window.escapeHtml ? escapeHtml(w) : w}</p>`;
            });
            html += `</div>`;
        }

        html += `<div class="overflow-x-auto"><table class="w-full text-left text-sm border-collapse">
            <thead>
                <tr class="bg-surface-container-high border-b border-outline-variant">
                    <th class="p-3 font-medium text-on-surface">Gün</th>
                    <th class="p-3 font-medium text-on-surface">Kahvaltı</th>
                    <th class="p-3 font-medium text-on-surface">Öğle</th>
                    <th class="p-3 font-medium text-on-surface">Akşam</th>
                </tr>
            </thead>
            <tbody>
        `;

        plan.days.forEach((dayData, rowIndex) => {
            html += `<tr class="border-b border-outline-variant/30 hover:bg-surface-container/50 transition-colors">`;
            html += `<td class="p-3 font-medium text-on-surface whitespace-nowrap">${escapeHtml(dayData.day)}</td>`;

            ['breakfast', 'lunch', 'dinner'].forEach((mealType, colIndex) => {
                const mealText = escapeHtml(dayData[mealType]);
                const cellId = `meal-${rowIndex}-${colIndex}`;
                html += `<td class="p-3 text-on-surface-variant min-w-[200px]" id="td-${cellId}">
                    <div class="mb-2">${mealText}</div>
                    <div class="flex flex-col gap-2 mt-2 pt-2 border-t border-outline-variant/20">
                        <label class="flex items-center gap-2 cursor-pointer group text-[12px] font-medium text-on-surface-variant hover:text-primary transition-colors">
                            <div class="relative flex items-center justify-center w-5 h-5 rounded border-2 border-outline-variant group-hover:border-primary transition-colors">
                                <input type="checkbox" id="${cellId}" class="peer sr-only" onchange="window.WeeklyPlanManager.toggleMealCheck(this, '${mealText.replace(/'/g, "\\'")}')">
                                <span class="material-symbols-outlined text-[16px] text-white bg-primary rounded opacity-0 peer-checked:opacity-100 absolute inset-0 flex items-center justify-center transition-opacity">check</span>
                            </div>
                            <span class="peer-checked:line-through peer-checked:opacity-60 transition-all">Yedim (Tamamla)</span>
                        </label>
                        <div class="flex items-center gap-3">
                            <button type="button" class="text-primary text-[11px] underline flex items-center gap-1 hover:text-primary-container" data-weekly-action="recipe" data-meal="${mealText}">
                                <span class="material-symbols-outlined text-[12px]">restaurant</span> Tarifi Al
                            </button>
                            <button type="button" class="text-error text-[11px] underline flex items-center gap-1 hover:text-error/80" data-weekly-action="alternative" data-meal="${mealText}">
                                <span class="material-symbols-outlined text-[12px]">swap_horiz</span> Yiyemedim
                            </button>
                        </div>
                    </div>
                </td>`;
            });
            html += `</tr>`;
        });

        html += `</tbody></table></div></div>
        <div class="mt-6 flex flex-wrap justify-center gap-3">
            <button type="button" data-grocery-action="open" class="btn-primary px-6 py-3 rounded-full font-label-md text-label-md inline-flex items-center gap-2 shadow-sm transition-all active:scale-95">
                <span class="material-symbols-outlined">local_grocery_store</span>
                Akıllı Sepeti Gör
            </button>
            <button type="button" data-grocery-action="calculate-budget" class="bg-secondary text-on-secondary px-6 py-3 rounded-full font-label-md text-label-md inline-flex items-center gap-2 hover:bg-secondary/90 shadow-sm transition-all active:scale-95">
                <span class="material-symbols-outlined">shopping_cart</span>
                Bütçe Hesapla
            </button>
        </div>
        <div id="budgetResult" class="mt-6 w-full"></div>
        <div class="mt-4 text-right">
            <button id="regeneratePlanBtn" class="btn-primary text-sm px-4 py-2 inline-flex items-center gap-2">
                <span class="material-symbols-outlined text-[18px]">refresh</span>Yeniden Oluştur
            </button>
        </div>`;
        resultContainer.innerHTML = html;
        this.hideLoading();
        window.currentPlanText = JSON.stringify(plan);

        // Bind the regenerate button that was just created dynamically!
        const regenBtn = document.getElementById('regeneratePlanBtn');
        if (regenBtn) {
            regenBtn.addEventListener('click', () => this.generatePlan(true));
        }

        // Restore checkboxes
        plan.days.forEach((dayData, rowIndex) => {
            ['breakfast', 'lunch', 'dinner'].forEach((mealType, colIndex) => {
                const cellId = `meal-${rowIndex}-${colIndex}`;
                const isChecked = localStorage.getItem('cm_check_' + cellId) === 'true';
                if (isChecked) {
                    const cb = document.getElementById(cellId);
                    if (cb) {
                        cb.checked = true;
                        const td = document.getElementById(`td-${cellId}`);
                        if (td) td.classList.add('opacity-60', 'bg-surface-container-high');
                    }
                }
            });
        });

        const generateBtn = document.getElementById('generatePlanBtn');
        if (generateBtn) {
            generateBtn.innerHTML = '<span class="material-symbols-outlined">refresh</span>Yeniden Oluştur';
        }

        if (window.recalculateGamification) {
            window.recalculateGamification();
        }
    },

    toggleMealCheck(checkbox, mealText) {
        const isChecked = checkbox.checked;
        const cellId = checkbox.id;
        const td = document.getElementById(`td-${cellId}`);

        localStorage.setItem('cm_check_' + cellId, isChecked);

        if (isChecked) {
            td?.classList.add('opacity-60', 'bg-surface-container-high');
            window.triggerConfetti?.(checkbox);
            if (window.safeFetchJson) {
                // Log compliance silently
                const user = window.AuthManager.getUser();
                if (user) {
                    safeFetchJson(API + '/api/compliance', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ meal: mealText, status: 'consumed' })
                    }).catch(console.error);
                }
            }
        } else {
            td?.classList.remove('opacity-60', 'bg-surface-container-high');
        }
        if (window.recalculateGamification) {
            window.recalculateGamification();
        }
    },

    renderEmptyState() {
        const resultContainer = document.getElementById('planResult');
        if (!resultContainer) return;
        resultContainer.innerHTML = `<div class="text-center py-12">
            <span class="material-symbols-outlined text-4xl text-outline mb-2">calendar_month</span>
            <p class="text-on-surface-variant">Henüz bir haftalık planınız yok. Yukarıdaki butona tıklayarak profilinize özel bir plan oluşturabilirsiniz.</p>
        </div>`;
    },

    showLoading() {
        const resultContainer = document.getElementById('planResult');
        if (!resultContainer) return;
        resultContainer.innerHTML = `
            <div class="text-center py-12">
                <div class="loading-dots flex gap-2 justify-center mb-4">
                    <span class="w-3 h-3 rounded-full bg-primary inline-block"></span>
                    <span class="w-3 h-3 rounded-full bg-primary inline-block"></span>
                    <span class="w-3 h-3 rounded-full bg-primary inline-block"></span>
                </div>
                <p class="text-on-surface-variant font-body-md">Plan hazırlanıyor... Bu işlem 15-30 saniye sürebilir.</p>
            </div>
        `;
    },

    hideLoading() {
        // Handled directly by renderPlan
    },

    showError(message) {
        const resultContainer = document.getElementById('planResult');
        if (!resultContainer) return;
        resultContainer.innerHTML = `
            <div class="text-center py-8 text-error">
                <span class="material-symbols-outlined text-4xl mb-2">warning</span>
                <p>${escapeHtml(message)}</p>
            </div>
        `;
    },

    resetState() {
        const user = window.AuthManager.getUser();
        if (user) {
            localStorage.removeItem('cm_saved_plan_json_' + user.telefon);
        }
        this.renderEmptyState();
    }
};
