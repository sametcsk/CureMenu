# Ürün analitiği

CureMenu, klinik karar/audit kayıtlarından ayrı, isteğe bağlı ve birinci taraf ürün analitiği kullanır. Amaç yalnız ekran, özellik ve dönüşüm kullanımını toplulaştırarak ürünü iyileştirmektir.

## Gizlilik sınırı

- Ham telefon, ad, e-posta, profil kimliği, mesaj metni, sağlık bilgisi, PDF/görsel/link, ilaç-hastalık-alerji değeri veya serbest metin kaydedilmez.
- Kimliği doğrulanmış kullanıcılar `CUREMENU_ANALYTICS_HASH_KEY` ile HMAC-SHA-256 takma kimliğe dönüştürülür. Anahtar değiştirilirse eski ve yeni dönem kullanıcıları ilişkilendirilemez.
- Kimliği doğrulanmamış ziyaretçilerde yalnız cihazda üretilen rastgele UUID kullanılır.
- Olay adları, ekranlar, özellikler ve metadata anahtar/değerleri sunucuda allowlist ile doğrulanır. Geçersiz veri reddedilir veya atılır.
- Analytics kapalıyken endpoint başarılı ancak no-op (`recorded: false`) yanıt verir.

## Yapılandırma

```env
CUREMENU_ANALYTICS_ENABLED=true
CUREMENU_ANALYTICS_RETENTION_DAYS=90
CUREMENU_ANALYTICS_HASH_KEY=uzun-rastgele-bir-gizli-deger
CUREMENU_ANALYTICS_ADMIN_TOKEN=ayri-bir-yonetici-gizli-degeri
```

Bu değerleri kaynak koda veya frontend'e koymayın. Yönetim uçları `Authorization: Bearer <CUREMENU_ANALYTICS_ADMIN_TOKEN>` ister. Dahili sayfa `/analytics` anahtarı yalnız o anki tarayıcı belleğinde kullanır; localStorage'a yazmaz.

## Saklama ve silme

Varsayılan analytics saklama süresi 90 gündür. Planlı bakım için `python scripts/enforce_data_retention.py --apply` kullanılır; komut önce `--apply` olmadan dry-run yapılmalıdır. Hesap silme, ilgili HMAC kimlikli analytics olaylarını da siler.

## İzlenen ürün olayları

Kayıt/profil dönüşümü, ekran görüntülenmesi ve aktif süre, CureBot/haftalık plan/menü/buzdolabı/tahlil/alışveriş açılması veya tamamlanması, aile profil geçişi ve geri bildirim gibi whitelist'li ürün olayları izlenir. Olaylar hiçbir zaman klinik kararın içeriğini taşımaz.

## API

- `POST /api/analytics/event`: best-effort olay kaydı; ürün akışını başarısız kılmaz.
- `GET /api/admin/analytics/{summary,funnel,retention,features,screens,cohorts}`: token korumalı toplulaştırılmış metrikler.

Bu metrikler klinik etkinlik, teşhis doğruluğu veya tıbbi validasyon ölçümü değildir.
