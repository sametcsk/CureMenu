(function() {
async function scanMenu() {
    const user = getUser();
    const url = document.getElementById('menuUrlInput').value.trim();
    const kimin_icin = document.getElementById('menuTarget').value;
    const result = document.getElementById('menuScanResult');

    if (!url) {
        alert("Lütfen bir restoran menü linki girin.");
        return;
    }

    result.innerHTML = `<div class="text-center py-12"><div class="loading-dots flex gap-2 justify-center mb-4"><span class="w-3 h-3 rounded-full bg-primary inline-block"></span><span class="w-3 h-3 rounded-full bg-primary inline-block"></span><span class="w-3 h-3 rounded-full bg-primary inline-block"></span></div><p class="text-on-surface-variant font-body-md">Menü taranıyor ve tıbbi profilinize göre analiz ediliyor... Bu işlem 15-20 saniye sürebilir.</p></div>`;

    try {
        const { res, data } = await safeFetchJson(API + '/api/scan-menu', {
            method: 'POST', headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ kimin_icin, url })
        });
        if (data && data.success) {
            const formatted = formatMarkdownSafe(data.analiz);
            result.innerHTML = `
            <div class="bg-surface-container-lowest rounded-lg p-8 shadow-l1 border border-outline-variant/20">
                <div class="prose prose-sm md:prose-base max-w-none font-body-md text-on-surface">
                    ${formatted}
                </div>
            </div>`;
        } else {
            result.innerHTML = `<div class="bg-error-container text-on-error-container p-6 rounded-lg text-center"><p>${apiHataMesaji(data, 'Menü okunamadı.')}</p></div>`;
        }
    } catch (e) {
        result.innerHTML = `<div class="bg-error-container text-on-error-container p-6 rounded-lg text-center"><p>${baglantiHatasi(e)}</p></div>`;
    }
}

async function scanMenuImage(inputEl) {
    const file = inputEl?.files?.[0];
    if (!file) return;
    const user = getUser();
    const kimin_icin = document.getElementById('menuTarget').value;
    const result = document.getElementById('menuScanResult');

    result.innerHTML = `<div class="text-center py-12"><div class="loading-dots flex gap-2 justify-center mb-4"><span class="w-3 h-3 rounded-full bg-primary inline-block"></span><span class="w-3 h-3 rounded-full bg-primary inline-block"></span><span class="w-3 h-3 rounded-full bg-primary inline-block"></span></div><p class="text-on-surface-variant font-body-md">Menü fotoğrafı analiz ediliyor...</p></div>`;

    const reader = new FileReader();
    reader.onload = async () => {
        try {
            const base64 = String(reader.result).split(',')[1] || reader.result;
            const { res, data } = await safeFetchJson(API + '/api/scan-menu-image', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ kimin_icin, image_base64: base64 }),
            });
            if (data && data.success) {
                result.innerHTML = `<div class="bg-surface-container-lowest rounded-lg p-8 shadow-l1 border border-outline-variant/20"><div class="prose prose-sm md:prose-base max-w-none font-body-md text-on-surface">${formatMarkdownSafe(data.analiz)}</div></div>`;
            } else {
                result.innerHTML = `<div class="bg-error-container text-on-error-container p-6 rounded-lg text-center"><p>${apiHataMesaji(data, 'Menü fotoğrafı okunamadı.')}</p></div>`;
            }
        } catch (e) {
            result.innerHTML = `<div class="bg-error-container text-on-error-container p-6 rounded-lg text-center"><p>${baglantiHatasi(e)}</p></div>`;
        }
        inputEl.value = '';
    };
    reader.readAsDataURL(file);
}

function startQRScanner() {
    const qrReaderDiv = document.getElementById('qr-reader');
    qrReaderDiv.style.display = "block";

    if (!window.Html5QrcodeScanner) {
        qrReaderDiv.innerHTML = '<div class="rounded-lg border border-outline-variant bg-surface-container-low p-4 text-sm text-on-surface-variant">QR okuyucu yüklenemedi. Menü bağlantısını elle girebilirsin.</div>';
        console.warn("[CureMenu] QR scanner dependency unavailable.");
        return;
    }

    if (html5QrcodeScanner) {
        html5QrcodeScanner.clear();
    }

    html5QrcodeScanner = new Html5QrcodeScanner(
        "qr-reader",
        { fps: 10, qrbox: {width: 250, height: 250} },
        false
    );

    html5QrcodeScanner.render(onScanSuccess, onScanFailure);
}

function onScanSuccess(decodedText, decodedResult) {
    html5QrcodeScanner.clear();
    document.getElementById('qr-reader').style.display = "none";

    // Okunan linki URL kutusuna yaz ve analizi başlat
    document.getElementById('menuUrlInput').value = decodedText;
    scanMenu();
}

function onScanFailure(error) {
    // Tarayıcı arka planda okuma yaparken sürekli hata fırlatabilir, logları temiz tutmak için yoruma aldım.
    // console.warn(`Code scan error = ${error}`);
}

function handleFridgeImage(event) {
    const file = event.target.files[0];
    if (!file) return;

    const reader = new FileReader();
    reader.onload = function(e) {
        const base64String = e.target.result;
        scanFridge(base64String);
    };
    reader.readAsDataURL(file);
}

async function scanFridge(imageBase64) {
    const kimin_icin = document.getElementById('fridgeTarget')?.value || 'kendim';
    const result = document.getElementById('fridgeScanResult');
    const inputEl = document.getElementById('fridgeImageInput');
    if (inputEl) inputEl.value = '';
    if (!result) return;

    result.innerHTML = `<div class="card p-8 text-center text-on-surface-variant"><div class="loading-dots text-primary text-4xl mb-3"><span>.</span><span>.</span><span>.</span></div><p>Buzdolabı fotoğrafını inceliyorum. Malzemeleri okuyup sana uygun bir fikir hazırlayacağım.</p></div>`;

    try {
        const { res, data } = await safeFetchJson(API + '/api/fridge-scan', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ kimin_icin, image_base64: imageBase64 })
        });

        if (!res.ok || !data?.success) {
            result.innerHTML = `<div class="card border-error-container bg-error-container p-6 text-center text-on-error-container"><p>${apiHataMesaji(data, 'Fotoğraftaki malzemeler okunamadı. Daha net ışıkta, ürünleri kadraja alarak tekrar deneyebilirsin.')}</p></div>`;
            return;
        }

        const malzemeler = data.malzemeler || data.analiz?.bulunan_malzemeler || data.sonuc?.bulunan_malzemeler || '';
        const tarif = data.tarif || data.analiz?.tarif_metni || data.sonuc?.tarif_metni || data.analiz?.uyari_mesaji || '';
        result.innerHTML = `
            <div class="grid gap-5 xl:grid-cols-[360px_minmax(0,1fr)]">
                <section class="card p-5">
                    <div class="mb-3 flex items-center gap-2 text-primary"><span class="material-symbols-outlined">kitchen</span><h3 class="font-display text-xl font-bold">Gördüğüm malzemeler</h3></div>
                    <p class="leading-7 text-on-surface-variant">${malzemeler ? escapeHtml(malzemeler) : 'Malzeme listesi ayrıca dönmedi.'}</p>
                </section>
                <section class="card p-5">
                    <div class="mb-3 flex items-center gap-2 text-primary"><span class="material-symbols-outlined">restaurant</span><h3 class="font-display text-xl font-bold">Tarif önerisi</h3></div>
                    <div class="prose prose-sm max-w-none text-on-surface">${tarif ? formatMarkdownSafe(tarif) : 'Tarif oluşturulamadı. Fotoğrafı yeniden yükleyebilirsin.'}</div>
                </section>
            </div>`;
    } catch (e) {
        result.innerHTML = `<div class="card border-error-container bg-error-container p-6 text-center text-on-error-container"><p>${baglantiHatasi(e)}</p></div>`;
    }
}
    window.MenuScanner = {
        init() {
        },
        scanMenu,
        scanMenuImage,
        startQRScanner,
        onScanSuccess,
        onScanFailure,
        handleFridgeImage,
        scanFridge
    };

    window.scanMenu = scanMenu;
    window.scanMenuImage = scanMenuImage;
    window.startQRScanner = startQRScanner;
    window.onScanSuccess = onScanSuccess;
    window.onScanFailure = onScanFailure;
    window.handleFridgeImage = handleFridgeImage;
    window.scanFridge = scanFridge;
    window.html5QrcodeScanner = null; // Used by QR scanner
})();
