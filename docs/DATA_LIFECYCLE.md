# CureMenu Veri Yaşam Döngüsü

## Veri Sınıfları

| Veri | Saklama | Silme yolu |
|---|---|---|
| Profil ve aile üyeleri | Hesap açık olduğu sürece | `DELETE /api/account` |
| Etkileşim ve tahlil özetleri | Varsayılan 365 gün | Retention komutu veya hesap silme |
| Klinik karar audit kayıtları | Varsayılan 365 gün | Retention komutu veya hesap silme |
| Kullanıcı Chroma hafızası | Varsayılan 365 gün | Retention komutu veya hesap silme |
| Resmi klinik kanıt koleksiyonları | Kaynak politikasıyla yönetilir | Kullanıcı hesabı silme işlemine dahil değildir |

`CUREMENU_RETENTION_DAYS` değeri en az 1 olmalıdır. Aşağıdaki komut varsayılan olarak yalnız sayı raporlar:

```powershell
.\.venv\Scripts\python.exe scripts\enforce_data_retention.py
```

Onaylı bakım penceresinde silme:

```powershell
.\.venv\Scripts\python.exe scripts\enforce_data_retention.py --apply
```

Yeni Chroma kayıtları zaman damgası ve geri döndürülemez hesap anahtarı taşır. Eski zaman damgasız kayıtlar otomatik retention temizliğine girmez; hesap silmede geçmiş profil metadata'sından türetilen namespace'ler ayrıca silinir. Eski kayıtların toplu temizliği yedek alınmış bakım penceresinde yapılmalıdır.

Hesap dışa aktarımı `GET /api/account/export` ile makinece okunabilir JSON döndürür ve parola hash'i içermez. Hesap silme parola ve açık `DELETE` onayı ister. Kullanıcı hafızası temizlenemezse ilişkisel hesap silme başlatılmaz.
