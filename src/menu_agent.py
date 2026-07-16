"""
CureMenu — QR Menü Analiz Ajanı
Restoran menüsünü tarayıp, hastanın profiline göre güvenli/riskli sınıflandırma yapar.
3 aşamalı pipeline: Diyetisyen → Müfettiş (Guardrail) → Doktor (Düzeltme)
"""
import json
from src.llm import invoke_with_model_fallback, parse_llm_response
from src.logger import get_logger

logger = get_logger(__name__)


def menu_danismani(ham_metin: str, profil_ozeti: str) -> str:
    # --- 1. ADIM: İLK ANALİZ (Diyetisyen) ---
    prompt_1 = f"""
    You are a clinical dietitian and a smart restaurant assistant helping a patient navigate a menu safely.

    PATIENT PROFILE:
    {profil_ozeti}

    RESTAURANT MENU (raw text extracted from QR code):
    ---
    {ham_metin}
    ---

    YOUR TASK:
    Analyze the menu above and classify each dish based on the patient's medical profile
    (diseases, allergies, medications, genetic background, etc.).

    STRICT RULES:
    1. ONLY use dishes that appear in the menu text. Do NOT invent or add dishes.
    2. Every dish in the menu must appear in exactly one category below.
    3. If a dish contains an allergen for this patient, it MUST go to the red category.
    4. If a dish conflicts with the patient's medications (drug-food interaction), it MUST go to the red category.
    5. Be concise — one short sentence per dish explaining why.
    6. If the menu text is empty or unreadable, respond only with:
       "⚠️ Menu could not be read. Please try scanning again."

    OUTPUT FORMAT (Markdown only, no extra text before or after):

    ### 🟢 Sizin İçin Güvenli
    - [Yemek Adı]: [Neden güvenli olduğu - tek cümle]

    ### 🟡 Porsiyon Kontrolüyle Tüketin
    - [Yemek Adı]: [Neden dikkatli olunması gerektiği - tek cümle]

    ### 🔴 Kesinlikle Uzak Durun
    - [Yemek Adı]: [Neden zararlı veya riskli olduğu - tek cümle]
    """
    
    ilk_cevap = parse_llm_response(invoke_with_model_fallback(prompt_1))
    
    logger.info("Diyetisyen analizi tamamlandi, mufettise gidiyor.")

    # --- 2. ADIM: MÜFETTİŞ (Guardrail) ---
    prompt_2 = f"""
    You are a deterministic risk-control reviewer for a diet assistant app.

    PATIENT PROFILE:
    {profil_ozeti}

    A dietitian AI just produced the following menu analysis:
    ---
    {ilk_cevap}
    ---

    YOUR TASK:
    Review the analysis above for known profile conflicts and uncertainty.

    CHECK FOR:
    1. Has any dish been placed in the WRONG category for this patient's conditions?
    2. Are there allergen risks that were missed?
    3. Does the response contain any medical diagnosis, treatment advice, or drug recommendations?
       (These are NOT allowed — we are a food recommendation app only.)

    OUTPUT (JSON only, no extra text):
    {{
      "is_safe": true or false,
      "issues": ["issue 1", "issue 2"],
      "corrected_analysis": "Full corrected markdown analysis, or empty string if no correction needed"
    }}

    If is_safe is true, corrected_analysis must be an empty string "".
    If is_safe is false, corrected_analysis must contain the full corrected markdown.
    """
    
    mufettis_cevap = parse_llm_response(invoke_with_model_fallback(prompt_2))
    
    temiz_json_metni = mufettis_cevap.replace("```json", "").replace("```", "").strip()
    
    try:
        denetim_sonucu = json.loads(temiz_json_metni)
    except Exception:
        logger.warning("Mufettis JSON formatini bozdu, kurtarma yapiliyor.")
        denetim_sonucu = {"is_safe": False, "issues": ["Format hatası veya genel risk."], "corrected_analysis": ""}

    # --- 3. ADIM: KARAR VE DOKTOR MÜDAHALESİ ---
    # Handle boolean/string type variations from LLM output / LLM çıktısındaki boolean/string tip farklılıklarını yönet
    is_safe = denetim_sonucu.get("is_safe")
    if is_safe is True or (isinstance(is_safe, str) and is_safe.lower() == "true"):
        logger.info("Mufettis onayladi! Ilk analiz guvenli.")
        return ilk_cevap
    else:
        issues = denetim_sonucu.get("issues") or []
        logger.warning(
            "event=menu_safety_review component=menu_guardrail status=blocked issue_count=%d",
            len(issues) if isinstance(issues, list) else 1,
        )
        
        # Prefer corrected analysis from guardrail if available / Varsa guardrail'den gelen düzeltilmiş analizi tercih et
        corrected = denetim_sonucu.get("corrected_analysis", "")
        if corrected and len(corrected) > 20:
            logger.info("Mufettis duzeltmeyi kendisi sagladi.")
            return corrected
            
        logger.info("Klinik uzman devreye girip listeyi düzeltiyor.")
        prompt_3 = f"""
        You are a medical advisor reviewing a restaurant menu analysis for a patient.

        PATIENT PROFILE:
        {profil_ozeti}

        The safety checker flagged the following issues with the analysis:
        Issues found: {denetim_sonucu.get('issues')}

        Original analysis:
        ---
        {ilk_cevap}
        ---

        YOUR TASK:
        Fix the flagged issues and rewrite the full analysis safely.

        RULES:
        1. Do NOT provide medical diagnosis or treatment advice.
        2. Do NOT recommend medications or supplements.
        3. Only classify dishes as safe / portion-controlled / avoid.
        4. Add a brief disclaimer at the end.

        OUTPUT FORMAT (Markdown only):

        ### 🟢 Sizin İçin Güvenli
        - [Yemek Adı]: [Sebep]

        ### 🟡 Porsiyon Kontrolüyle Tüketin
        - [Yemek Adı]: [Sebep]

        ### 🔴 Kesinlikle Uzak Durun
        - [Yemek Adı]: [Sebep]

        ---
        ⚕️ *Bu analiz genel beslenme rehberi niteliğindedir, tıbbi tavsiye yerine geçmez.
        Köklü diyet değişikliklerinden önce doktorunuza danışın.*
        """
        
        return parse_llm_response(invoke_with_model_fallback(prompt_3))
