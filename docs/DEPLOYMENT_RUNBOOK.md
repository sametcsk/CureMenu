# CureMenu Kapalı Beta Deployment Runbook

## Desteklenen Topoloji

- Python 3.12 ve `constraints.txt` ile tekrarlanabilir kurulum.
- HTTPS sonlandıran reverse proxy arkasında tek uygulama instance'i.
- SQLite yalnız düşük trafikli, tek instance kapalı beta için kullanılabilir.
- Birden fazla instance için ortak rate-limit deposu zorunludur; SQLite bu topoloji için onaylı değildir.
- Chroma yalnız yerel persistent dizin olarak kullanılır. Chroma HTTP servisi internete veya yerel ağa açılmaz.

## Deployment Öncesi

1. Secret değerlerini hosting sağlayıcısının secret store'una gir; `.env` yükleme.
2. `APP_ENV=staging` veya `production`, `CUREMENU_COOKIE_SECURE=true`, açık CORS ve trusted host değerlerini ayarla.
3. `CUREMENU_DB_PATH` ve `CHROMA_PERSIST_DIR` kalıcı diskleri göstermeli.
4. `pip install -c constraints.txt -r requirements.txt` çalıştır.
5. Yedek al, sonra `alembic upgrade head` çalıştır.
6. `/live` ve `/ready` yanıtlarını doğrula.
7. `python scripts/check_package_safety.py --source-root .` çalıştır.

## Reverse Proxy

- Yalnız HTTPS kabul et; HTTP'yi HTTPS'ye yönlendir.
- PDF ve görseller için uygulamadaki limitlerle uyumlu body limiti koy.
- AI endpoint'lerinde proxy timeout'u uygulama timeout'undan kısa olmamalı.
- `X-Forwarded-Proto` yalnız güvenilen proxy tarafından yazılmalı ve `TRUST_PROXY_HEADERS=true` sadece bu durumda kullanılmalı.

## Smoke Sırası

`/live` -> `/ready` -> kayıt/giriş -> profil -> kısa CureBot -> haftalık plan -> küçük PDF -> güvenli menü URL -> Smart Grocery -> log privacy kontrolü.

## Rollback

1. Trafiği durdur.
2. Uygulama sürümünü önceki doğrulanmış pakete döndür.
3. Migration geri dönüş SQL'i çalıştırma; doğrulanmış migration öncesi SQLite yedeğini ayrı dosyaya geri yükle.
4. Chroma dizinini yalnız eşleşen snapshot ile geri yükle.
5. `/ready`, auth ve bir sentetik kullanıcı smoke'u geçmeden trafiği açma.

## Ölçekleme Kararı

İkinci instance, eşzamanlı yazma baskısı veya uzaktan çalışan worker ihtiyacı doğduğunda PostgreSQL ve ortak Redis planı tamamlanmadan yatay ölçekleme yapılmaz.
