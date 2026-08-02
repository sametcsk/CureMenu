# CureMenu Secret Yönetimi

- Production secret'ları Git, ZIP, log, Docker image veya CI çıktısına yazılmaz.
- Yerel `.env` yalnız geliştirici makinesinde ve Git dışında kalır.
- Hosted ortamda Gemini, Tavily, LangSmith, BioPortal, JWT, SMTP ve veritabanı bilgileri platform secret store üzerinden environment variable olarak enjekte edilir.
- Secret değeri uygulama başlangıç mesajında, `/ready` yanıtında veya hata ayrıntısında gösterilmez.
- Erişim en az yetkiyle sınırlandırılır; staging ve production anahtarları ayrıdır.
- Eski paket paylaşılmışsa ilgili tüm anahtarlar sızmış kabul edilip döndürülür.
- Rotasyon sonrası `docs/OPERATIONAL_SECURITY_ROTATION_PLAN.md` smoke sırası ve `docs/ROTATION_LOG_TEMPLATE.md` kullanılır.

Hosting sağlayıcısı seçilmeden belirli bir secret manager entegrasyonu eklenmez. Seçimden sonra erişim politikası, audit log ve rotasyon yetkileri sağlayıcı panelinde doğrulanmalıdır.
