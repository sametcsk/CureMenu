# CureMenu Rotation Log Template

Bu dosyayi her rotasyon icin kopyalayin. Secret degeri, anahtar parcasi,
fingerprint, authorization header, token, parola veya `.env` icerigi yazmayin.
Ekran goruntulerinde credential alanlarini tamamen kapatin.

## Rotasyon Ozeti

- Rotasyon kayit no:
- Tarih ve saat dilimi:
- Ortam: `development / staging / production`
- Islemi yapan:
- Gozden geciren:
- Neden: `legacy ZIP exposure / periodic rotation / incident / other`
- Eski ZIP paylasim durumu: `yes / no / unknown`
- Bakim penceresi:
- Kullanici etkisi:
- Genel sonuc: `PASS / PARTIAL / FAIL`

## Servis Kaydi

Her servis icin bu blogu cogaltin.

- Servis:
- Environment variable adi:
- Ortam:
- Kullanim durumu: `ACTIVE / NOT_ENABLED / NOT_IN_ACTIVE_RUNTIME`
- Yeni credential olusturma zamani:
- Secret store guncelleme zamani:
- Uygulama yeniden baslatma zamani:
- `/live` sonucu: `PASS / FAIL / NOT_APPLICABLE`
- `/ready` sonucu: `PASS / FAIL / NOT_APPLICABLE`
- Servise ozel smoke sonucu: `PASS / FAIL / NOT_APPLICABLE`
- Smoke adiminin kisa tanimi:
- Eski credential iptal zamani:
- Provider audit/kullanim kontrolu: `PASS / FAIL / NOT_APPLICABLE`
- Log privacy kontrolu: `PASS / FAIL`
- Hassas veri icermeyen kanit referansi:
- Sorun/aksiyon notu:
- Islemi yapan:
- Gozden geciren:

## JWT Oturum Kontrolu

- JWT rotasyon zamani:
- Tum instance'lar yeniden baslatildi: `YES / NO / NOT_APPLICABLE`
- Eski oturum reddedildi: `PASS / FAIL / NOT_APPLICABLE`
- Yeni login: `PASS / FAIL / NOT_APPLICABLE`
- Refresh rotation/replay testi: `PASS / FAIL / NOT_APPLICABLE`
- Logout sonrasi refresh reddi: `PASS / FAIL / NOT_APPLICABLE`
- Cookie guvenlik nitelikleri: `PASS / FAIL / NOT_APPLICABLE`
- Auth regresyon testleri: `PASS / FAIL / NOT_RUN`

## Rotasyon Sonu Kontrolleri

- [ ] Eski credential'lar iptal edildi.
- [ ] `/live` ve `/ready` beklenen sonucu verdi.
- [ ] Zorunlu servis smoke testleri tamamlandi.
- [ ] `pytest -q` sonucu kaydedildi.
- [ ] Package/source safety scanner sonucu kaydedildi.
- [ ] Loglarda secret, token veya ham saglik verisi bulunmadi.
- [ ] Provider kullanim/maliyet ekranlari kontrol edildi.
- [ ] Bu kayitta secret degeri veya anahtar parcasi bulunmadigi ikinci kisi
  tarafindan kontrol edildi.

## Sonuc ve Onay

- Kalan riskler:
- Takip aksiyonlari ve sorumlular:
- Kapali beta karari: `GO / CONDITIONAL GO / NO-GO`
- Operasyon onayi:
- Guvenlik gozden gecirme onayi:
- Kapanis tarihi:
