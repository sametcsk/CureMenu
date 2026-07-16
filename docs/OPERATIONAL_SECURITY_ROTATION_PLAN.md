# CureMenu Operational Security Rotation Plan

Bu plan eski `.env` iceren arsivlerin paylasilmis olabilecegi varsayimiyla
hazirlanmistir. Secret degerleri bu dokumana, terminal gecmisine, ekran
goruntusune, issue kaydina veya rotasyon loguna yazilmaz.

## 1. Environment Variable Envanteri

### Rotasyona Giren Secret'lar

| Servis | Environment variable | Kullanim durumu | Rotasyon karari |
| --- | --- | --- | --- |
| Google / Gemini | `GOOGLE_API_KEY` | Metin ve gorsel model cagrilarinin temel kimlik bilgisi | Eski ZIP paylasildiysa mutlaka dondur |
| Tavily | `TAVILY_API_KEY` | Config'de tanimli; mevcut kaynak kodda aktif Tavily istemci cagrisi bulunmadi | Tanimliysa dondur; kullanilmiyorsa eski anahtari iptal edip yeniden eklememe karari verilebilir |
| LangSmith | `LANGCHAIN_API_KEY` | Istege bagli izleme/tracing katmani | Tanimli ve kullaniliyorsa dondur |
| BioPortal | `BIOPORTAL_API_KEY` | Tibbi terim/ilac normalizasyon istemcisinde kullaniliyor | Eski ZIP paylasildiysa mutlaka dondur |
| CureMenu JWT | `JWT_SECRET_KEY` | Access ve refresh token imzalama/dogrulama | En son dondur; mevcut oturumlari gecersiz kilacagini planla |

Kaynak kodda SMTP, harici veritabani parolasi, Redis, Sentry, OpenAI veya
Anthropic icin aktif bir secret environment variable referansi bulunmadi.
Deployment platformundaki secret store yine de yalnizca **degisken adlari**
uzerinden ayrica kontrol edilmelidir.

### Secret Olmayan Operasyon Ayarlari

Asagidaki degiskenler rotasyon anahtari degildir; degerleri bu dokumanda
kaydedilmemelidir:

- Uygulama: `APP_ENV`, `DEBUG`, `PORT`, `CORS_ORIGINS`,
  `CUREMENU_COOKIE_SECURE`, `LOG_LEVEL`, `ENABLE_NEMO_GUARDRAILS`
- Modeller: `GOOGLE_MODEL`, `GEMINI_TEXT_MODEL`, `GEMINI_VISION_MODEL`,
  `GEMINI_FAST_MODEL`, `GEMINI_EVAL_MODEL`, `GEMINI_MODEL_FALLBACKS`
- Veri: `CUREMENU_DB_PATH`, `CUREMENU_DB_TIMEOUT`, `CHROMA_PERSIST_DIR`
- RAG: `RAG_FOLDER`, `CLINICAL_RAG_COLLECTION`, `HF_HUB_OFFLINE`,
  `TRANSFORMERS_OFFLINE`
- LangSmith metadata: `LANGCHAIN_TRACING_V2`, `LANGCHAIN_ENDPOINT`,
  `LANGCHAIN_PROJECT`
- E2E: `CUREMENU_E2E_TMP`, `PLAYWRIGHT_BROWSER_CHANNEL`

## 2. Her Servis Icin Standart Rotasyon Akisi

Her servis tek tek dondurulur. Bir servis PASS olmadan digerine gecilmez.

1. Saglayici panelinde yeni credential'i kullanici manuel olusturur.
2. Yeni deger yalnizca deployment secret store'a veya gerekli yerel `.env`
   dosyasina manuel yazilir.
3. Uygulama yeniden baslatilir; secret degeri komut satirina arguman olarak
   verilmez.
4. Liveness ve readiness kontrol edilir:

   ```powershell
   $BaseUrl = "http://127.0.0.1:8000"
   Invoke-RestMethod "$BaseUrl/live"
   Invoke-RestMethod "$BaseUrl/ready"
   ```

5. Servise ozel smoke testi yapilir.
6. Loglarda credential, token veya gercek saglik verisi bulunmadigi kontrol
   edilir. Secret degeriyle `rg`/arama yapilmaz.
7. Smoke PASS olduktan sonra eski credential saglayici panelinden iptal edilir.
8. Sonuc `ROTATION_LOG_TEMPLATE.md` kopyasina deger yazmadan kaydedilir.

Yeni credential calismazsa aciga cikmis olabilecek eski credential tekrar aktif
edilmez. Sorun duzeltilir veya ikinci bir yeni credential uretilir.

## 3. Rotasyon Sirasi ve Smoke Testleri

### 1. Google / Gemini

Manuel islem:

- Yeni API anahtarini saglayici panelinde olustur.
- `GOOGLE_API_KEY` degerini secret store veya yerel `.env` icinde manuel
  guncelle ve uygulamayi yeniden baslat.
- Yeni anahtar dogrulandiktan sonra eski anahtari iptal et.

Minimum smoke:

1. `/live` ve `/ready` PASS olmali.
2. Kisisel veya tibbi veri icermeyen kisa bir CureBot sorusu gonderilmeli.
3. Yanit tamamlanmali; kullaniciya provider/auth hatasi gorunmemeli.
4. Kapali betada gorsel akis kullanilacaksa kucuk ve hassas veri icermeyen bir
   menu gorseliyle tek vision smoke yapilmali.

Bu smoke model davranisinin klinik dogrulamasini degil, yeni credential ile
servis baglantisinin calistigini kanitlar.

### 2. Tavily

Mevcut kod taramasinda `TAVILY_API_KEY` config'de tanimli olsa da aktif Tavily
istemci cagrisi bulunmadi. Bu nedenle `/ready` veya CureBot smoke'u Tavily
credential'ini dogrulamaz.

Manuel islem ve minimum smoke:

- Tavily aktif kullanilacaksa yeni anahtar olustur ve provider'in kendi test
  konsolunda hassas veri icermeyen tek bir genel sorguyla baglantiyi dogrula.
- Uygulamada kullanilmiyorsa yeni anahtar eklemek yerine eski anahtari iptal et
  ve durumu `NOT_IN_ACTIVE_RUNTIME` olarak kaydet.
- Anahtar degerini terminal komutuna veya rotasyon loguna yazma.

### 3. LangSmith

Manuel islem:

- Tracing kullaniliyorsa `LANGCHAIN_API_KEY` dondurulur.
- `LANGCHAIN_ENDPOINT`, `LANGCHAIN_PROJECT` ve `LANGCHAIN_TRACING_V2` secret
  degildir; yalnizca dogru ortam/proje secimi kontrol edilir.

Minimum smoke:

1. `/live` ve `/ready` PASS olmali.
2. Saglik verisi icermeyen tek bir kisa CureBot istegi yapilmali.
3. LangSmith panelinde yeni bir trace olustugu kontrol edilmeli.
4. Trace payload'inda token, authorization header veya kisisel saglik verisi
   bulunmadigi teyit edilmeli.

Tracing kapaliysa sonuc `NOT_ENABLED` olarak kaydedilir ve eski credential
iptal edilir.

### 4. BioPortal

Manuel islem:

- `BIOPORTAL_API_KEY` yeni credential ile secret store veya yerel `.env`
  icinde manuel guncellenir.
- Uygulama yeniden baslatilir; eski credential smoke PASS sonrasinda iptal
  edilir.

Minimum smoke:

1. `/live` ve `/ready` PASS olmali.
2. Gercek kisi verisi yerine genel bir ilac/terim kullanilarak mevcut ilac
   normalizasyon veya guvenlik akisi bir kez calistirilmali.
3. Yetkilendirme/provider hatasi olmamali; uygulamanin guvenli fallback'i ile
   gercek provider basarisi birbirine karistirilmamali.
4. Saglayici panelindeki istek kaydi veya hassas veri icermeyen uygulama
   telemetry'si ile gercek dis cagrinin yapildigi teyit edilmeli.

### 5. JWT Secret

JWT en son dondurulur, cunku degisiklik mevcut access/refresh token'lari ve
aktif kullanici oturumlarini gecersiz kilabilir.

Manuel islem:

- Bakim penceresi belirle ve test kullanicilarina yeniden login gerekecegini
  bildir.
- Yeni `JWT_SECRET_KEY` degerini yalnizca secret store veya yerel `.env` icinde
  manuel guncelle.
- Uygulamanin tum instance'larini ayni anda yeniden baslat.
- Eski secret'i geri donus araci olarak saklama; problem olursa baska bir yeni
  secret kullan.

Regresyon testleri:

```powershell
.\.venv\Scripts\python.exe -m pytest -q tests\test_auth_security.py tests\test_production_readiness.py
```

Manuel JWT smoke:

1. Rotasyon oncesinden kalan bir test oturumu korumali endpoint'e erisememeli.
2. Yeni login basarili olmali ve yeni cookie'ler `HttpOnly`, uygun `SameSite`
   ve production HTTPS ortaminda `Secure` olmali.
3. Refresh bir kez basarili olmali; eski refresh token replay reddedilmeli.
4. Logout sonrasi ayni refresh token tekrar kullanilamamali.
5. `/ready` yeniden PASS olmali.

## 4. Rotasyon Sonu Ortak Kontroller

```powershell
.\.venv\Scripts\python.exe scripts\check_package_safety.py --source-root .
.\.venv\Scripts\python.exe -m pytest -q
```

- [ ] Tum servis kayitlari PASS, `NOT_ENABLED` veya `NOT_IN_ACTIVE_RUNTIME`.
- [ ] Eski credential'lar saglayici panellerinde iptal edildi.
- [ ] Provider kullanim/maliyet ekranlarinda beklenmeyen hareket yok.
- [ ] `/live` ve `/ready` PASS.
- [ ] Login, CureBot ve gerekli provider smoke akislari PASS.
- [ ] Loglarda token, authorization header veya gercek saglik verisi yok.
- [ ] Rotasyon logunda secret degeri, parmak izi veya anahtar son karakterleri
  yok.

Bu plan baglanti ve operasyon guvenligini dogrular; klinik dogrulama veya tibbi
etkinlik kaniti degildir.
