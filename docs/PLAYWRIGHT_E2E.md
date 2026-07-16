# Playwright E2E

Kritik tarayıcı akışları gerçek Edge/Chromium üzerinde çalışır. Auth ve profil
geçici SQLite veritabanını kullanır; Gemini, Tavily ve maliyetli analiz uçları
Playwright ağ taklitleriyle sabit yanıt döndürür.

Kurulum:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
```

Windows'ta testler varsayılan olarak kurulu Microsoft Edge'i kullanır:

```powershell
.\.venv\Scripts\python.exe -m pytest tests\e2e -q
```

Edge bulunmayan CI ortamında Chromium kurulabilir:

```powershell
.\.venv\Scripts\python.exe -m playwright install chromium
$env:PLAYWRIGHT_BROWSER_CHANNEL = "chromium"
.\.venv\Scripts\python.exe -m pytest tests\e2e -q
```

Test sunucusu otomatik başlatılır ve her çalışmada geçici DB/Chroma dizini
oluşturulur. Gerçek `.env`, üretim veritabanı veya dış AI anahtarı kullanılmaz.
