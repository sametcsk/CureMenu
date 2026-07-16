# CureMenu Secret Rotation Checklist

Bu kontrol listesi, `.env` içeren eski arşivlerin paylaşılmış olabileceği varsayımıyla
uygulanmalıdır. Anahtar değerlerini bu dokümana, kaynak koda, issue kaydına veya
ekran görüntüsüne yazmayın.

## Önce

- [ ] Dört eski ZIP'in paylaşılmış olabileceği kişi ve kanallar belirlendi.
- [ ] Eski ZIP'ler `security_quarantine/` altında ve paylaşım dışı tutuluyor.
- [ ] Yeni değerlerin yalnızca secret manager veya yerel `.env` içinde tutulacağı doğrulandı.
- [ ] Rotasyon sırasında hangi servislerin kısa süreli kesintiye uğrayabileceği kaydedildi.

## Servis Anahtarları

- [ ] Google/Gemini API anahtarı sağlayıcı panelinden yenilendi.
- [ ] Eski Google/Gemini anahtarı iptal edildi ve kullanım logları kontrol edildi.
- [ ] Tavily kullanılıyorsa anahtar yenilendi, eskisi iptal edildi.
- [ ] LangSmith kullanılıyorsa API anahtarı yenilendi, eskisi iptal edildi.
- [ ] BioPortal kullanılıyorsa API anahtarı yenilendi, eskisi iptal edildi.
- [ ] SMTP kullanılıyorsa kullanıcı/parola veya uygulama parolası yenilendi.
- [ ] Harici DB kullanılıyorsa DB kullanıcı parolası ve bağlantı secret'ı yenilendi.
- [ ] Deployment, object storage, monitoring veya başka servis anahtarları varsa yenilendi.

## JWT ve Oturumlar

- [ ] Yeni, uzun ve rastgele `JWT_SECRET_KEY` üretildi.
- [ ] Yeni JWT secret yalnızca deployment secret store ve gerekli yerel `.env` içine yazıldı.
- [ ] JWT değişiminin mevcut oturumları geçersiz kılacağı kullanıcı planında dikkate alındı.
- [ ] Rotasyon sonrası eski access/refresh token'ların kullanılamadığı doğrulandı.

## Sonra

- [ ] Yeni anahtarlarla `/live` ve `/ready` kontrol edildi.
- [ ] Bir login, bir kısa CureBot isteği ve gerekiyorsa bir Tavily/RAG smoke testi yapıldı.
- [ ] Sağlayıcı panellerinde beklenmeyen kullanım veya maliyet bulunmadığı kontrol edildi.
- [ ] Log, ZIP, build artefact ve ekran görüntülerinde yeni anahtar olmadığı tarandı.
- [ ] Güvenli paylaşım paketi üretildi ve `check_package_safety.py` sonucu `SAFE` oldu.
- [ ] Rotasyon tarihi ve işlemi yapan kişi kaydedildi; anahtar değerleri kaydedilmedi.

Eski ZIP'ler herhangi bir kişiye, bulut klasörüne, e-postaya veya mesajlaşma
kanalına gönderildiyse içlerindeki bütün anahtarlar açığa çıkmış kabul edilmelidir.
