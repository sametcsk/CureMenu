"""Kullanıcıya gösterilen Türkçe hata ve bilgi mesajları."""

PROFIL_BULUNAMADI = "Profil bulunamadı."
ONCE_PROFIL_OLUSTUR = "Önce profil oluşturun."
PROFIL_GEREKLI = (
    "Önce sağlık profilinizi doldurmalısınız. "
    "Güvenliğiniz için profiliniz olmadan size tavsiye veremeyiz."
)
ONERI_OLUSTURULAMADI = "Üzgünüm, şu an bir öneri oluşturamadım. Lütfen tekrar deneyin."
GUARDRAIL_UYARI = "Güvenli öneri oluşturulamadı: {sebep}"
GENEL_HATA = "Beklenmeyen bir hata oluştu. Lütfen daha sonra tekrar deneyin."
AI_YAPILANDIRMA_HATASI = (
    "Yapay zeka servisi şu an kullanılamıyor. "
    "API anahtarlarının doğru yapılandırıldığından emin olun."
)
ZAMAN_ASIMI = "İstek zaman aşımına uğradı. Lütfen tekrar deneyin."
BAGLANTI_HATASI = "Sunucuya bağlanılamadı. İnternet bağlantınızı kontrol edin."
COK_FAZLA_ISTEK = "Çok fazla istek gönderdiniz. Lütfen biraz bekleyip tekrar deneyin."
MENU_BOS = "Menü okunamadı veya sayfa boş."
MENU_FOTO_OKUNAMADI = "Fotoğraftan menü okunamadı. Lütfen daha net bir menü fotoğrafı yükleyin."
PLAN_OLUSTURULAMADI = (
    "Haftalık planı şu an hazırlayamadım. Birazdan tekrar deneyebiliriz."
)
BUZDOLABI_FOTO_OKUNAMADI = (
    "Fotoğraftaki malzemeleri şu an net okuyamadım. "
    "Işığı daha iyi olan, malzemelerin göründüğü bir fotoğrafla tekrar deneyin."
)
RAPOR_OLUSTURULAMADI = "Alışveriş raporu şu an oluşturulamadı. Lütfen tekrar deneyin."

# ── Konumlandırma & güven metinleri ──

POSITIONING_TAGLINE = (
    "CureMenu; hastalık, alerji, ilaç ve tahlil notlarını dikkate alarak "
    "daha güvenli yemek seçimleri yapmana yardım eden klinik beslenme karar destek asistanıdır."
)

TIBBI_FERAGAT = (
    "CureMenu teşhis koymaz, tedavi planı yazmaz ve doktorun yerini almaz. "
    "Öneriler, girdiğiniz sağlık bilgilerine dayalı beslenme karar desteğidir. "
    "İlaç, doz veya diyet değişikliklerinde doktorunuza ya da diyetisyeninize danışın. "
    "Acil durumlarda 112'yi arayın."
)

TIBBI_FERAGAT_KISA = "Tedavi yerine geçmez · Doktorunuza danışın · Acilde 112"

GUARDRAIL_ONAY_ACIKLAMA = (
    "Bu öneri, profilinizdeki hastalık ve alerji bilgilerine göre güvenlik kontrolünden geçti."
)

SOHBET_ACIKLAMA = (
    "Genel sağlık bilgisi sunulmuştur; kişisel tedavi planı yerine geçmez."
)

ONBOARDING_ORNEK_SORULAR = [
    "Bugün ne yesem?",
    "Diyabetime uygun akşam yemeği öner",
    "Tüm aile için ortak menü hazırla",
]


def kullanici_hatasi(hata: Exception | str) -> str:
    """Teknik hata metnini kullanıcı dostu Türkçe mesaja çevirir."""
    mesaj = str(hata).lower()

    if "timeout" in mesaj or "zaman aşımı" in mesaj:
        return ZAMAN_ASIMI
    if "api key" in mesaj or "api_key" in mesaj or "invalid api" in mesaj:
        return AI_YAPILANDIRMA_HATASI
    if "connection" in mesaj or "bağlantı" in mesaj:
        return BAGLANTI_HATASI
    if "rate limit" in mesaj or "429" in mesaj:
        return COK_FAZLA_ISTEK
    if "güvenlik ihlali" in mesaj or "iç ağ" in mesaj:
        return str(hata)
    if "buzdolab" in mesaj or "malzeme" in mesaj:
        return BUZDOLABI_FOTO_OKUNAMADI
    if "menü" in mesaj or "fotoğraf" in mesaj or "gemini" in mesaj or "model" in mesaj:
        return MENU_FOTO_OKUNAMADI

    return GENEL_HATA
