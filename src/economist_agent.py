import json
from src.llm import invoke_with_model_fallback, parse_llm_response

def alisveris_ve_butce_hesapla(haftalik_plan_metni: str, location_info: str = None) -> str:
    """
    Haftalık plan metninden malzemeleri çıkarır, 
    Yapay Zekanın genel fiyat bilgisiyle (Tahmini) 
    kullanıcıya ekonomik bir alışveriş listesi raporu sunar.
    """
    # 1. Adım: Plandan malzemeleri çıkar (Kısa liste)
    prompt_extract = f"""
    Aşağıdaki haftalık beslenme planını oku ve bu menüleri yapmak için gereken temel malzemelerin
    kısa bir alışveriş listesini (sadece en önemli et, sebze, bakliyat ve süt ürünleri) çıkar.
    Liste formatı virgülle ayrılmış kelimeler olsun. Örn: Tavuk göğsü, Domates, Kıyma, Yulaf, Süt.
    
    Haftalık Plan:
    {haftalik_plan_metni[:3000]}
    
    Sadece virgülle ayrılmış malzeme listesi ver.
    """
    malzemeler_ham = invoke_with_model_fallback(prompt_extract)
    malzemeler = parse_llm_response(malzemeler_ham).strip()
    
    if not malzemeler:
        malzemeler = "Tavuk, Kıyma, Mevsim Sebzeleri, Yumurta, Süt"
        
    # 2. Adım: Ekonomist Raporu (Markdown Tablo)
    location_context = ""
    if location_info:
        location_context = f"\nUSER LOCATION: {location_info}\nPlease provide market recommendations tailored to this specific location (e.g. suggesting physical store chains likely to be in this area) and include online delivery options (Getir, Yemeksepeti, Migros Sanal Market, Trendyol Go, etc.) for specific items.\n"

    prompt_report = f"""
    You are an Expert Economist and Smart Shopper in Turkey.
    
    INGREDIENTS NEEDED: {malzemeler}{location_context}
    
    YOUR TASK:
    Create a budget-friendly shopping list report in Turkish for these ingredients.
    Estimate realistic AVERAGE market prices in Turkey (in TRY - ₺).
    
    OUTPUT FORMAT (Strictly Markdown):
    
    ### 🛒 Haftalık Akıllı Alışveriş Listeniz ve Bütçeniz
    Bu haftaki sağlıklı menünüz için gerekli temel malzemeler ve tahmini ortalama fiyatları:
    
    | Ürün (Kategori) | Önerilen Tür/Market | Tahmini Birim Fiyat (₺) |
    |---|---|---|
    | ... | ... | ... |
    
    **💡 Tasarruf İpucu:** [Sadece 1-2 cümlelik, menüdeki malzemelerle ilgili zekice bir mutfak tasarrufu veya saklama tavsiyesi]
    
    ### 📍 Nereden Alınır? (Size Özel Öneriler)
    Aşağıdaki konum veya bilgiye göre en mantıklı market zincirlerini (fiziksel) ve online sipariş platformlarını yaz:
    **Kullanıcı Konumu/Durumu:** {location_info}
    - Fiziki Market Önerileri: [Konuma uygun 2-3 zincir market]
    - E-Ticaret / Hızlı Teslimat Önerileri: [Migros Sanal Market, Getir, Trendyol Go, Wefood vb. linkleriyle]
    
    **Tahmini Toplam Mutfak Masrafı:** ... ₺
    """
    
    rapor_ham = invoke_with_model_fallback(prompt_report)
    rapor = parse_llm_response(rapor_ham)
    
    return rapor
