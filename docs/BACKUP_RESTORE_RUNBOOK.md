# CureMenu Yedekleme ve Geri Yükleme

## Yedekleme

1. Deployment ve migration öncesi yazma trafiğini durdur.
2. SQLite için dosya kopyası yerine SQLite backup API kullanan doğrulanmış bakım akışını kullan.
3. Yedeğin SHA-256 ve `PRAGMA integrity_check` sonucunu kaydet; veri satırlarını loglama.
   Karşılaştırmalı doğrulama: `python scripts/verify_sqlite_backup.py --source <aktif.db> --backup <yedek.db>`
4. Uygulama kapalıyken Chroma persistent dizininin snapshot'ını al.
5. DB ve Chroma snapshot'larını aynı sürüm etiketi ve zaman damgasıyla eşleştir.
6. Yedekleri uygulama sunucusundan ayrı, şifreli ve erişimi sınırlı depoda tut.

## Geri Yükleme Provası

1. Üretim dosyalarının üstüne yazmadan ayrı geçici dizine geri yükle.
2. SQLite integrity, Alembic head ve tablo kayıt sayılarını doğrula.
3. Chroma koleksiyonlarının açıldığını ve kullanıcı hafızasının hesaplar arasında karışmadığını sentetik verilerle doğrula.
4. Auth, profil, history ve `/ready` smoke testlerini çalıştır.
5. Prova sonuçlarını tarih, yedek kimliği ve test sonucu olarak kaydet; sağlık verisi kaydetme.

## Sorumluluk

Yedek alma otomasyonu hosting seçildikten sonra sağlayıcının snapshot/secret/KMS özellikleriyle tamamlanmalıdır. Bu belge prosedürü tanımlar; tek başına hosted backup garantisi değildir.
