"""
CureMenu — Profil Özeti Yardımcıları
Profil özeti oluşturma mantığı tek bir yerde toplanmıştır.
chatbot_ui, haftalık plan ve aile sayfaları bu fonksiyonları kullanır.
"""
from src.models import AileUyesi, KullaniciProfili
from src.ilac_etkilesim import ilac_etkilesim_ozeti
from src.llm import invoke_with_model_fallback, parse_llm_response
import json
from src.logger import get_logger, log_failure
from src.database import icd11_cache_get, icd11_cache_set

logger = get_logger(__name__)

_ICD11_COMMON_MAP = {
    "hipertansiyon": "BA00 Essential Hypertension",
    "tansiyon": "BA00 Essential Hypertension",
    "diyabet": "5A11 Type 2 Diabetes Mellitus",
    "şeker": "5A11 Type 2 Diabetes Mellitus",
    "seker": "5A11 Type 2 Diabetes Mellitus",
    "kolesterol": "5C81 Lipid disorders",
    "çölyak": "DA94 Celiac disease",
    "colyak": "DA94 Celiac disease",
    "böbrek": "GB61 Chronic kidney disease",
    "bobrek": "GB61 Chronic kidney disease",
    "gut": "FA25 Gout",
}

def icd_11_cevir(hastaliklar_listesi: list[str]) -> str:
    """Hastanın girdiği lokal/günlük dil hastalık isimlerini WHO ICD-11 standart kodlarına çevirir."""
    if not hastaliklar_listesi:
        return "Bilinen hastalık yok"
    
    cache_key = ",".join(sorted(h.lower().strip() for h in hastaliklar_listesi))
    cached = icd11_cache_get(cache_key)
    if cached:
        return cached

    deterministic = []
    unknown = []
    for hastalik in hastaliklar_listesi:
        key = hastalik.lower().strip()
        mapped = _ICD11_COMMON_MAP.get(key)
        if mapped:
            deterministic.append(f"[{mapped}] ({hastalik})")
        else:
            unknown.append(hastalik)

    if deterministic and not unknown:
        sonuc = ", ".join(deterministic)
        icd11_cache_set(cache_key, sonuc)
        return sonuc
        
    ham_metin = ", ".join(hastaliklar_listesi)
    prompt = f"""
    You are a Clinical Ontology Expert and Medical Coder specializing in the WHO ICD-11 framework.
    Your task is to convert the following patient-provided disease names (often in slang or Turkish layperson terms) into their official international ICD-11 codes and formal medical names.
    
    PATIENT INPUT: {ham_metin}
    
    CRITICAL INSTRUCTIONS:
    1. If the input is something like "Şeker", map it to "5A11 Type 2 Diabetes Mellitus" (or appropriate).
    2. If it's "Tansiyon", map it to "BA00 Essential Hypertension".
    3. Return ONLY a valid JSON array of objects, where each object has "orijinal" (original term) and "icd11" (the official ICD-11 code and name).
    
    Example output format:
    [
        {{"orijinal": "Şeker", "icd11": "5A11 Type 2 Diabetes Mellitus"}},
        {{"orijinal": "Kalp Krizi", "icd11": "BA41 Acute Myocardial Infarction"}}
    ]
    
    RETURN ONLY JSON, no markdown blocks, no other text.
    """
    try:
        cevap = invoke_with_model_fallback(prompt)
        icerik = parse_llm_response(cevap)
        temiz_json = icerik.replace("```json", "").replace("```", "").strip()
        veriler = json.loads(temiz_json)
        
        kodlu_hastaliklar = []
        for v in veriler:
            kodlu_hastaliklar.append(f"[{v.get('icd11', 'Bilinmeyen Kod')}] ({v.get('orijinal', '')})")
            
        sonuc = ", ".join(kodlu_hastaliklar)
        logger.info("ICD-11 cevirimi tamamlandi: %d terim", len(hastaliklar_listesi))
        icd11_cache_set(cache_key, sonuc)
        return sonuc
    except Exception as e:
        log_failure(logger, "icd11_translation", e, component="profile")
        fallback = ", ".join(h.title() for h in hastaliklar_listesi)
        icd11_cache_set(cache_key, fallback)
        return fallback



def profil_ozeti_olustur(uye: AileUyesi) -> str:
    """Tek bir kullanıcı/aile üyesi için LLM'e gönderilecek profil özet metni üretir."""
    # ICD-11 Çeviriciyi devreye sokuyoruz
    hastaliklar = icd_11_cevir(uye.hastaliklar)
    
    genetik = ", ".join(
        g.title() for g in getattr(uye, "genetik_hastaliklar", [])
    ) or "Yok"
    tibbi = getattr(uye, "tibbi_gecmis", "") or "Yok"
    alerjiler = ", ".join(uye.alerjiler) if uye.alerjiler else "Yok"
    ilaclar = getattr(uye, "ilaclar", []) or []
    ilac_listesi = ", ".join(i.title() for i in ilaclar) or "Bildirilmedi"
    ilac_kurallari = ilac_etkilesim_ozeti(ilaclar)

    return (
        f"{uye.ad}, "
        f"Yas: {uye.yas}, Cinsiyet: {uye.cinsiyet.value}, "
        f"Boy: {getattr(uye, 'boy', 170)} cm, Kilo: {getattr(uye, 'kilo', 70.0)} kg, "
        f"Beslenme Hedefi: {getattr(uye, 'hedef', 'Sağlıklı Yaşam (Genel)')}, "
        f"Hastalıklar (ICD-11 Standart): {hastaliklar}, "
        f"Genetik Geçmiş: {genetik}, "
        f"Tıbbi Geçmiş: {tibbi}, "
        f"Alerjiler: {alerjiler}, "
        f"Kullandığı İlaçlar: {ilac_listesi}\n"
        f"{ilac_kurallari}"
    )


def aile_profil_ozeti_olustur(profil: KullaniciProfili) -> str:
    """Tüm aile üyelerinin ortak profil özet metnini üretir."""
    satirlar = ["TÜM AİLE ORTAK PROFİLİ:"]
    for uye in profil.tum_uyeler():
        h = ", ".join(uye.hastaliklar) if uye.hastaliklar else "Yok"
        a = ", ".join(getattr(uye, "alerjiler", [])) if getattr(uye, "alerjiler", []) else "Yok"
        ilac = ", ".join(getattr(uye, "ilaclar", []) or []) or "Yok"
        hedef = getattr(uye, "hedef", "Sağlıklı Yaşam (Genel)")
        satirlar.append(
            f"- {uye.ad}: Yas: {uye.yas}, Cinsiyet: {uye.cinsiyet.value}, "
            f"Hedefi: {hedef}, Hastalıkları: {h}, Alerjileri: {a}, İlaçları: {ilac}"
        )
        ilac_ozet = ilac_etkilesim_ozeti(getattr(uye, "ilaclar", []) or [])
        if "ZORUNLU" in ilac_ozet:
            satirlar.append(f"  {ilac_ozet.replace(chr(10), ' ')}")
    satirlar.append(
        "\nBU BİR AİLE ORTAK İSTEĞİDİR. "
        "Önerilen yemek tüm bu kısıtlamalara ve ilaç-yemek etkileşimlerine AYNI ANDA uymak ZORUNDADIR."
    )
    return "\n".join(satirlar)


def hedef_ilaclari(profil: KullaniciProfili, kimin_icin: str) -> list[str]:
    """Seçilen hedef için ilaç listesini döndürür (aile modunda birleşik)."""
    if kimin_icin == "aile":
        ilaclar: list[str] = []
        for uye in profil.tum_uyeler():
            ilaclar.extend(getattr(uye, "ilaclar", []) or [])
        return ilaclar

    hedef = profil.ana_kullanici
    if kimin_icin != "kendim":
        hedef = next(
            (u for u in profil.aile_uyeleri if u.ad.lower() == kimin_icin.lower()),
            hedef,
        )
    if hedef is None:
        return []
    return getattr(hedef, "ilaclar", []) or []
