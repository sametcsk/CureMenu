# CureMenu Release Readiness

Son güncelleme: 16 Temmuz 2026

## Karar

**RC1 ve kapalı beta durumu: Şartlı hazır.**

Mevcut çalışan demo; güvenlik kontrolleri, veri maskeleme, gerçek tarayıcı testleri,
güncel veritabanı migration'ı ve mobil responsive doğrulamasıyla yerel RC1 adayıdır.
Gerçek kullanıcı daveti gönderilmeden önce aşağıdaki release kapıları tamamlanmalıdır:

1. Gerçek HTTPS staging ortamı kurulmalı; secure cookie, trusted host, CORS,
   reverse proxy body limitleri ve timeout değerleri doğrulanmalıdır.
2. Fiziksel telefonda kamera/QR, dosya seçici ve mobil klavye smoke testi yapılmalıdır.
3. Hosted deployment runbook, backup/rollback ve secret yönetimi yazılmalıdır.
4. Klinik uzmanla sınırlı pilot planı ve klinik doğrulama yöntemi tamamlanmalıdır.
5. Dependency lock ve `pip-audit` benzeri bağımlılık güvenlik taraması ayrı bakım
   adımında uygulanmalıdır.

Eski `.env` içeren dört ZIP silinmeden `security_quarantine/` altına taşınmış ve Git
dışında tutulmuştur. Güvenli release paketi üretilip scanner'dan geçirilmiştir.
Harici servis anahtarlarının rotasyonu kullanıcı kararıyla ertelenmiş kabul edilmiş
operasyon riskidir; eski ZIP'ler daha önce paylaşılmışsa rotasyon tamamlanmalıdır.

## Mevcut Durum

| Alan | Durum | Mevcut kontrol | Kapalı beta öncesi kalan iş |
|---|---|---|---|
| Auth ve rate limit | Hazır | Login enumeration azaltıldı; refresh rotation/revocation DB'de tutuluyor. `JWT_SECRET_KEY` yerel yapılandırmaya güvenli biçimde eklendi; register/login/protected endpoint/refresh replay/logout smoke akışı geçti. | Hosted secret store ve çok sunuculu dağıtımda ortak rate-limit deposu değerlendirilmelidir. Parola hash modernizasyonu sonraki hardening fazıdır. |
| Chroma privacy ve redaction | Hazır | Hesap ve aile üyesi bazlı geri döndürülemez namespace kullanılıyor. Prompt, dosya adı, özet ve nested metadata yazılmadan önce maskeleniyor. Eski ortak namespace'ler okunmuyor. | Chroma verisi disk üzerinde şifreli değildir. Retention ve kullanıcı silme prosedürü production öncesi tanımlanmalıdır. |
| Upload, PDF, URL ve görsel güvenliği | Hazır | PDF byte/sayfa/metin/süre limitleri, şifreli ve bozuk PDF reddi; SSRF, redirect/private IP ve response limitleri; görsel base64, magic byte, format, byte ve piksel kontrolleri mevcut. | Reverse proxy body limiti ve timeout uygulama limitleriyle uyumlu ayarlanmalıdır. Gerçek cihaz/dosya smoke testi yapılmalıdır. |
| RAG, evidence ve klinik iddia sınırı | Şartlı hazır | Sağlık iddialarında registry kapsamındaki resmi/onaylı kaynaklar önceliklidir. Approved evidence yoksa kesin öneri yerine belirsizlik ve uzman yönlendirmesi kullanılır. Pending review durumu klinik doğrulama gibi gösterilmez. | Registry kaynaklarının uzman değerlendirmesi halen `pending`. Klinik doğruluk iddiası ancak uzman pilotu ve tanımlı validasyon sürecinden sonra kullanılabilir. |
| Runtime log privacy | Hazır | Model yanıtı, prompt, sağlık profili, ilaç/alerji/tahlil içeriği ve kişisel tanımlayıcıların ham loglanması engellendi. Başarı ve hata yolları sentetik marker'larla test edildi. | Hosted log erişimi, retention ve silme prosedürü tanımlanmalıdır. |
| Production readiness | Şartlı hazır | Security header'ları, trusted hosts, production fail-fast ayarları, `/live` ve `/ready` kontrolleri var. Gerçek yerel DB `20260715_0002 (head)` revision'ına taşındı; `/ready` içinde `migration_current=true` doğrulandı. | HTTPS/proxy, backup/rollback, hosted deployment runbook ve deployment secret yönetimi doğrulanmalıdır. SQLite yalnızca sınırlı beta yükü için değerlendirilmelidir. Harici CDN bağımlılıkları çevrimdışı kullanım riski taşır. |
| Observability ve tracing privacy | Hazır | LangSmith development ortamında yalnızca açık opt-in ile çalışır; input, output ve metadata trace payload'ları zorunlu olarak gizlenir. Production, staging ve kapalı beta ortamlarında tracing isteği fail-fast ile reddedilir. | Gerçek kullanıcı verisiyle LangSmith tracing açılmamalıdır. Tanısal inceleme yalnızca sentetik veriyle development ortamında yapılmalıdır. |
| Playwright E2E ve mobil | Hazır | Gerçek Edge tarayıcısında auth, profil, weekly plan/actions, Smart Grocery, CureBot SSE/governance, PDF, menü, buzdolabı, Geçmiş ve hata durumları test ediliyor. `360x800`, `390x844`, `412x915` ve `768x1024` görsel/overflow doğrulaması geçti; sonuç `MOBILE DEMO READY`. | Fiziksel QR/kamera izni ve gerçek telefon dosya seçici/klavye kontrolü HTTPS staging smoke kapsamında kalır. |
| Otomatik test paketi | Hazır | `206 passed, 1 warning`; Playwright paketi `5 passed`; `app.js` ve tüm frontend modülleri parse kontrolünden geçti; package/source scanner sonucu `SOURCE_SAFE`. | Starlette/httpx deprecation uyarısı ve dependency lock/`pip-audit` planlı bakımda ele alınmalıdır. |

## Kapalı Beta Checklist

### Secrets ve Eski ZIP Temizliği

- [x] `healmenu_check.zip`, `healmenu_clean.zip`, `healmenu_final.zip` ve
      `healmenu_v5.zip` silinmeden `security_quarantine/` altına taşındı.
- [x] Karantina dizini Git dışında tutuluyor ve paylaşılmaması gerektiği belgeleniyor.
- [x] Yeni paket `.env`, local DB, Chroma, outputs ve geçici dosyalar olmadan üretildi.
- [x] Yeni paket `scripts/check_package_safety.py` ile `SAFE` sonucu verdi.
- [ ] Eski ZIP'lerin eriştiği kişiler/kanallar manuel olarak kayıt altına alınmalı.
- [ ] Eski ZIP'ler paylaşılmışsa potansiyel olarak açığa çıkmış anahtarlar döndürülmeli.

### Environment Variables

- [ ] `APP_ENV=production` veya staging için açık ortam değeri kullanılıyor.
- [ ] `GOOGLE_API_KEY` secret store üzerinden sağlanıyor.
- [ ] Kullanılıyorsa `TAVILY_API_KEY`, `LANGCHAIN_API_KEY` ve
      `BIOPORTAL_API_KEY` secret store üzerinden sağlanıyor.
- [x] Uzun ve rastgele `JWT_SECRET_KEY` yerel yapılandırmada tanımlı; auth smoke geçti.
- [ ] `CORS_ORIGINS`, `ALLOWED_HOSTS` ve `CUREMENU_DB_PATH` açıkça tanımlı.
- [ ] `DEBUG=false`, `CUREMENU_COOKIE_SECURE=true`.
- [x] `LANGCHAIN_TRACING=false`; staging, production ve kapalı beta ortamında LangSmith tracing fail-fast ile kapalı.
- [ ] Tanısal tracing gerekiyorsa yalnızca sentetik veriyle development ortamında açık opt-in kullanılıyor.
- [x] `.env` image, artifact, ZIP, log veya kaynak kontrolüne dahil değil.

### Database ve Readiness

- [ ] Staging DB yedeği alındı.
- [x] Gerçek yerel DB için doğrulanmış yedek alındı ve korundu.
- [x] Gerçek yerel DB üzerinde `alembic upgrade head` başarıyla tamamlandı.
- [x] `alembic current` çıktısı `20260715_0002 (head)` gösteriyor.
- [x] `/live` HTTP 200 dönüyor.
- [x] `/ready` HTTP 200, `ready: true` ve `migration_current=true` dönüyor.
- [x] Registry, Chroma ve DB readiness kontrolleri ayrı ayrı başarılı.
- [ ] Hosted staging DB yedeği ve migration smoke testi deployment sonrasında yapılmalı.

### Test ve Gerçek Servis Kontrolü

- [x] `python -m pytest -q`: `206 passed, 1 warning`.
- [x] `python -m pytest -q tests/e2e`: `5 passed`.
- [x] Frontend JavaScript parse kontrolleri başarılı.
- [x] Package/source safety kontrolü `SOURCE_SAFE`.
- [ ] Gerçek sağlayıcı staging smoke planı bir kez tamamlandı.
- [ ] Gerçek API kullanım maliyeti ve rate-limit davranışı gözlendi.
- [x] Desktop ve dört responsive viewport'ta otomatik mobil demo doğrulaması tamamlandı.
- [ ] En az bir fiziksel mobil cihazda temel akış tamamlanmalı.
- [ ] Kamera, QR, dosya seçici ve mobil klavye davranışı kontrol edildi.

### Network ve Deployment

- [ ] HTTPS sertifikası geçerli.
- [ ] Auth cookie'lerinde `Secure`, `HttpOnly` ve `SameSite=Lax` doğrulandı.
- [ ] Reverse proxy upload body limiti uygulama limitleriyle uyumlu.
- [ ] Proxy/API timeout değeri CureBot üst sınırını kontrollü karşılıyor.
- [ ] Trusted proxy/header ayarı yalnızca güvenilen proxy için açık.
- [ ] Rate limit gerçek istemci IP'sini güvenli biçimde görüyor.
- [ ] Harici CDN kesintisinde dashboard blank screen olmuyor.

### Log, Privacy, Backup ve Kullanıcı Bilgilendirmesi

- [x] Runtime log privacy testlerinde token, authorization header, e-posta, telefon, sağlık profili ve model yanıtı ham halde bulunmadı.
- [ ] Interaction, decision event ve Chroma kayıtları sentetik veriyle kontrol edildi.
- [ ] Log erişimi yalnızca yetkili kişilerle sınırlandı.
- [ ] Retention, kullanıcı silme ve veri dışa aktarma prosedürü yazıldı.
- [ ] DB ve gerekli Chroma/evidence verisi için yedekleme çalıştı.
- [ ] Rollback adımları ve sorumlusu belirlendi.
- [ ] Beta kullanıcı metni karar destek sınırını açıkça anlatıyor.
- [ ] "Tanı koymaz, tedavi düzenlemez, doktor/diyetisyen yerine geçmez" uyarısı görünür.
- [ ] Belirsiz veya riskli durumda sağlık profesyoneline yönlendirme doğrulandı.

## Staging Smoke Test Planı

Tüm testler sentetik bir kullanıcıyla yapılmalıdır. Gerçek hasta adı, telefon,
tahlil veya ilaç geçmişi kullanılmamalıdır. Test boyunca yalnızca gerekli sekmeler
açılmalı ve her dış servis çağrısı bir kez yapılmalıdır.

| Sıra | Test | Beklenen sonuç | Kaydedilecek kanıt |
|---|---|---|---|
| 1 | `/live` ve `/ready` | İkisi de 200; `/ready` içinde DB, migration, registry ve Chroma kontrolleri başarılı. | Zaman damgalı response özeti; secret içermeyen ekran görüntüsü. |
| 2 | Bir kullanıcı kaydı | Kayıt tamamlanır, secure/httponly cookie oluşur, dashboard açılır. | Status kodu ve cookie flag kontrolü; cookie değeri kaydedilmez. |
| 3 | Logout, hatalı ve başarılı login | Logout sonrası refresh reddedilir; yanlış şifre güvenli tek tip hata; doğru şifreyle giriş başarılı. | Status ve kullanıcıya görünen mesaj. |
| 4 | Bir profil kaydı | Sentetik hastalık, alerji ve ilaç bilgisi kaydolur ve dashboard'da görünür. | Profil ekranı; kişisel tanımlayıcı kullanılmaz. |
| 5 | Bir haftalık plan | Tek gerçek sağlayıcı çağrısıyla plan oluşur; uyarılar ve disclaimer görünür. | Süre, model adı/sürümü, decision ID ve kullanıcıya görünen sonuç özeti. |
| 6 | Bir kısa CureBot sorusu | Kısa yanıt tamamlanır; stream kesilmez; risk/governance özeti güvenli render edilir. | Süre, status akışı, decision ID; prompt veya sağlık verisi loga kopyalanmaz. |
| 7 | Bir küçük PDF | Sentetik ve küçük PDF yüklenir; güvenli özet görünür; ham metin loga sızmaz. | Dosya boyutu, status ve maskelenmiş log kontrolü. |
| 8 | Bir güvenli menü URL'si | Public HTTPS URL taranır; redirect/limit davranışı normal çalışır. | Hedef domain, status ve analiz özeti; URL'de token bulunmaz. |
| 9 | Smart Grocery ve bütçe | Haftalık plandan sepet açılır; excluded/risk items ve tahmini bütçe görünür. | Decision ID, katalog sürümü ve disclaimer. Canlı fiyat/stok iddiası yapılmaz. |
| 10 | Log ve privacy incelemesi | API anahtarı, bearer token, ham telefon/e-posta/TC/IBAN ve ham tahlil metni bulunmaz. | Scanner çıktısı ve manuel kontrol notu; ham secret rapora yazılmaz. |
| 11 | Mobil smoke | Login, plan, CureBot, PDF seçici ve modal kapatma en az bir mobil cihazda çalışır. | Cihaz/tarayıcı sürümü ve sonuç; gerçek sağlık verisi içermeyen ekran görüntüsü. |
| 12 | Temizlik | Sentetik kullanıcı/veri kaldırılır veya test DB geri yüklenir; test anahtarı bütçe limiti kontrol edilir. | Temizlik onayı ve rollback sonucu. |

Smoke testi aşağıdaki durumda başarısız sayılır:

- `/ready` 503 veya migration head uyumsuzsa,
- Ham secret ya da kişisel tanımlayıcı loglarda görünüyorsa,
- Riskli/belirsiz durumda kesin sağlık önerisi veriliyorsa,
- Auth cookie güvenlik flag'leri eksikse,
- Kritik UI akışında JavaScript hatası veya boş ekran oluşuyorsa.

## ZIP ve Anahtar Rotasyonu Aksiyon Planı

15 Temmuz 2026 taramasında aşağıdaki paketlerin her birinde `.env` bulundu:

| Paket | Tarama sonucu | Bu turdaki işlem |
|---|---|---|
| `healmenu_check.zip` | Unsafe: `.env` içeriyor | Silinmedi; Git dışı `security_quarantine/` altında. |
| `healmenu_clean.zip` | Unsafe: `.env` içeriyor | Silinmedi; Git dışı `security_quarantine/` altında. |
| `healmenu_final.zip` | Unsafe: `.env` içeriyor | Silinmedi; Git dışı `security_quarantine/` altında. |
| `healmenu_v5.zip` | Unsafe: `.env` içeriyor | Silinmedi; Git dışı `security_quarantine/` altında. |

Güvenli paylaşım paketi `healmenu_safe_release_20260715_163322.zip` olarak üretildi
ve package scanner tarafından `SAFE` bulundu. Paket `*.zip` kuralıyla Git dışında tutulur.

Önerilen sıra:

1. Kullanıcı eski ZIP'lerin silinmesini veya karantinaya alınmasını açıkça onaylar.
2. ZIP'ler daha önce paylaşılmışsa içeriklerindeki tüm değerler açığa çıkmış kabul edilir.
3. Google/Gemini, Tavily, LangSmith ve BioPortal anahtarları kullanılıyorsa
   sağlayıcı panellerinden döndürülür; eski anahtarlar iptal edilir.
4. `JWT_SECRET_KEY` değiştirilir. Bu işlem mevcut oturumları geçersiz kılabilir;
   planlı bakım olarak uygulanır.
5. Deployment/platform secret'ları ve varsa DB kimlik bilgileri gözden geçirilir.
6. Temiz kaynak ağacından yeni paket üretilir; `.env`, DB, Chroma, outputs,
   cache ve geçici dosyalar dahil edilmez.
7. Paket paylaşılmadan önce şu kontrol geçmelidir:

```powershell
.\.venv\Scripts\python.exe scripts\check_package_safety.py yeni_paket.zip
```

Silme, karantina, yeniden paketleme ve anahtar rotasyonu dış sistemlerde geri
döndürülemeyen sonuçlar doğurabileceği için açık kullanıcı onayı olmadan
uygulanmamalıdır.

## Sunum ve Başvuru İçin Sade Teknik Güvenilirlik Dili

- Yapay zeka tek başına karar vermiyor; öneriler kullanıcı profili ve önceden
  tanımlanmış güvenlik kontrollerinden geçiriliyor.
- İlaç, alerji veya sağlık bilgisiyle ilgili risk görüldüğünde sistem bunu
  görmezden gelmiyor; uyarı veriyor ve gerektiğinde uzmana yönlendiriyor.
- Kullanılan kaynakların kaydı tutuluyor. Kaynağı veya doğruluğu yeterince açık
  olmayan konularda sistem kesin konuşmuyor.
- Kişisel tanımlayıcılar kalıcı kayıtlara yazılmadan önce maskeleniyor; kullanıcı
  hafızaları hesap ve aile üyesi bazında birbirinden ayrılıyor.
- Kayıt, profil, haftalık plan, CureBot, tahlil ve alışveriş akışları gerçek bir
  tarayıcıyla otomatik olarak test edildi.
- Dosya yükleme ve internet bağlantısı üzerinden menü tarama işlemlerinde boyut,
  format ve güvenli adres kontrolleri uygulanıyor.
- CureMenu bir karar destek ürünüdür; tanı koymaz ve tedavi düzenlemez. Klinik
  doğrulama iddiası için uzmanlarla yürütülecek sınırlı pilot ve doğrulama süreci
  halen gereklidir.

## Standart Doğrulama Komutları

```powershell
.\.venv\Scripts\alembic.exe current
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m pytest -q tests\e2e
.\.venv\Scripts\python.exe scripts\check_package_safety.py --source-root .
```

Staging migration komutu yalnızca yedek alındıktan ve doğru DB hedefi açıkça
doğrulandıktan sonra çalıştırılmalıdır:

```powershell
.\.venv\Scripts\alembic.exe upgrade head
```
