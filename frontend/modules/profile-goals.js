(function() {
    const DEFAULT_GOAL = 'Sağlıklı Yaşam';
    const GOALS = Object.freeze([
        'Sağlıklı Yaşam',
        'Kilo Kontrolü',
        'Yağ Yakımı',
        'Kas Kazanımı',
        'Kalp Sağlığı',
        'Sindirim ve Bağırsak Sağlığı',
        'Enerji ve Performans',
    ]);

    const LEGACY_GOAL_ALIASES = Object.freeze({
        'Sağlıklı Yaşam (Genel)': 'Sağlıklı Yaşam',
        'Kilo Verme / Yağ Yakımı': 'Yağ Yakımı',
        'Kas Kazanımı / Sporcu Beslenmesi': 'Kas Kazanımı',
        'Diyabet Dostu Beslenme': 'Sağlıklı Yaşam',
        'Kalp Dostu Beslenme': 'Kalp Sağlığı',
        'Sindirim / Bağırsak Sağlığı': 'Sindirim ve Bağırsak Sağlığı',
        'Hamilelik / Emzirme Beslenmesi': 'Sağlıklı Yaşam',
        'Çocuk Gelişimi': 'Sağlıklı Yaşam',
    });

    function normalize(value) {
        const candidate = String(value || '').trim();
        const normalized = LEGACY_GOAL_ALIASES[candidate] || candidate;
        return GOALS.includes(normalized) ? normalized : DEFAULT_GOAL;
    }

    function populateSelect(select, selectedValue) {
        if (!select) return;
        const normalized = normalize(selectedValue || select.dataset.selectedGoal);
        select.replaceChildren();
        GOALS.forEach(goal => {
            const option = document.createElement('option');
            option.value = goal;
            option.textContent = goal;
            select.appendChild(option);
        });
        select.value = normalized;
    }

    function initialize(root = document) {
        root.querySelectorAll('[data-profile-goal-select]').forEach(select => {
            populateSelect(select, select.value || select.dataset.selectedGoal);
        });
    }

    window.ProfileGoals = Object.freeze({
        DEFAULT_GOAL,
        GOALS,
        normalize,
        populateSelect,
        initialize,
    });

    initialize();
})();
