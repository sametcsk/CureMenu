"""
CureMenu — LLM Ajan Düğümleri (Nodes)
Sistemin beynini oluşturan tüm yapay zeka ajanlarımızı (Yönlendirici, Diyetisyen, Denetmen) burada tanımlıyoruz.
"""
import json
import re

from src.llm import invoke_with_model_fallback, parse_llm_response
from src.agent_state import AgentState
from src.logger import get_logger
from src.memory import klinik_bilgi_getir
from src.prompt_manager import PromptManager
from src.governance.decision import calculate_confidence, extract_citations_from_rag
from src.governance.events import event_update, make_event
from src.medical_knowledge.safety_checker import check_medication_food_safety, medication_safety_events
from src.quality.policy_engine import PolicyEngine
from src.quality.rule_engine import RuleEngine
from src.quality.citation_validator import CitationValidator

logger = get_logger(__name__)


def _governance_update(
    state: AgentState,
    event_type: str,
    component: str,
    *,
    status: str = "ok",
    metadata: dict | None = None,
    **extra,
) -> dict:
    update = event_update(
        state,
        event_type,
        component,
        status=status,
        metadata=metadata,
    )
    update.update(extra)
    return update


def _governance_events_update(
    state: AgentState,
    events: list[dict],
    **extra,
) -> dict:
    current_events = list(state.get("governance_events") or [])
    current_events.extend(events)
    update = {"governance_events": current_events}
    update.update(extra)
    return update


def _hafiza_metni_olustur(state: AgentState, bos_mesaj: str = "Kayıtlı tahlil veya geçmiş bilgi bulunmuyor.") -> str:
    """State'teki hafıza listesini birleştirip tek metin olarak döndürür (DRY)."""
    return " ".join(state['hafiza']) if state.get('hafiza') else bos_mesaj


def _sohbet_gecmisi_metni(state: AgentState, son_n: int = 6) -> str:
    """Son N mesajı role: content formatında birleştirip metin döndürür (DRY)."""
    if not state.get('sohbet_gecmisi'):
        return ""
    satirlar = []
    for m in state['sohbet_gecmisi'][-son_n:]:
        satirlar.append(f"{m['role']}: {m['content']}")
    return "\n".join(satirlar)


def _resolve_numeric_meal_selection(selection: str, state: AgentState) -> str | None:
    text = (selection or "").strip()
    if not text.isdigit():
        return None
    selected_index = int(text) - 1
    if selected_index < 0:
        return None

    numbered_line = re.compile(r"^\s*(?:[-*]\s*)?(\d+)[\.\)]\s+(.+?)\s*$")
    for message in reversed(state.get("sohbet_gecmisi") or []):
        if message.get("role") != "assistant":
            continue
        candidates: list[str] = []
        for line in str(message.get("content") or "").splitlines():
            match = numbered_line.match(line)
            if not match:
                continue
            candidate = re.sub(r"\*\*|__", "", match.group(2)).strip()
            candidate = re.sub(r"\s{2,}", " ", candidate)
            if candidate:
                candidates.append(candidate)
        if selected_index < len(candidates):
            return candidates[selected_index]
    return None


def _profile_field(profil_ozeti: str, field: str) -> str:
    marker = f"{field}:"
    if marker not in profil_ozeti:
        return ""
    rest = profil_ozeti.split(marker, 1)[1]
    for next_marker in [
        "Hastalıklar",
        "Genetik Geçmiş",
        "Tıbbi Geçmiş",
        "Alerjiler",
        "Kullandığı İlaçlar",
    ]:
        token = f", {next_marker}:"
        if token in rest:
            rest = rest.split(token, 1)[0]
            break
    return rest.strip()


def _quality_profile_from_summary(profil_ozeti: str) -> dict:
    allergies = [
        item.strip()
        for item in _profile_field(profil_ozeti, "Alerjiler").split(",")
        if item.strip() and item.strip().lower() != "yok"
    ]
    diseases = [
        item.strip()
        for item in _profile_field(profil_ozeti, "Hastalıklar (ICD-11 Standart)").split(",")
        if item.strip() and item.strip().lower() != "yok"
    ]
    return {
        "alerjiler": allergies,
        "hastaliklar": diseases,
        "yas": 30,
        "cinsiyet": "",
        "hedef": _profile_field(profil_ozeti, "Beslenme Hedefi"),
    }


def supervisor_node(state: AgentState) -> dict:
    """
    Dinamik Medical Supervisor Agent.
    Kullanıcının niyetini analiz eder ve LangGraph'ta hangi ajanların (node) tetikleneceğine karar verir.
    (Örn: Basit sohbet ise diğer ajanları yormadan doğrudan yanıt döner).
    """
    istek = state['istek']
    
    hafiza_metni = _hafiza_metni_olustur(state)
    sohbet_gecmisi_str = _sohbet_gecmisi_metni(state)
    
    template = PromptManager.get_agent_prompt("supervisor", "v1")
    prompt = PromptManager.hydrate_prompt(template, {
        "profil_ozeti": state['profil_ozeti'],
        "hafiza_metni": hafiza_metni,
        "sohbet_gecmisi_str": sohbet_gecmisi_str,
        "istek": istek
    })
    
    cevap = invoke_with_model_fallback(prompt)
    icerik = parse_llm_response(cevap)
    
    try:
        temiz = icerik.replace("```json", "").replace("```", "").strip()
        veri = json.loads(temiz)
        
        next_node = veri.get("next_node", "FINISH")
        hedef_islem = veri.get("hedef_islem", "SOHBET")
        return _governance_update(
            state,
            "ConversationRouted",
            "supervisor",
            metadata={"next_node": next_node, "target_action": hedef_islem},
            next_node=next_node,
            hedef_islem=hedef_islem,
            uzman_onerisi=veri.get("uzman_onerisi", ""),
        )
    except Exception as e:
        logger.error("Supervisor JSON parse hatası: %s - Gelen: %s", e, icerik[:200])
        # Fallback to diet if failed
        return _governance_update(
            state,
            "ConversationRouted",
            "supervisor",
            status="fallback",
            metadata={"reason": "json_parse_error"},
            next_node="DIETITIAN",
            hedef_islem="SECENEK_SUN",
            uzman_onerisi="",
        )


def onceliklendirme_node(state: AgentState) -> dict:
    """
    Klinik Triyaj Ajanı (Health Prioritization Agent).
    Hastanın hastalıklarını, ilaçlarını ve hedeflerini alıp birbiriyle çelişen durumları çözer.
    Örn: Kilo alma hedefi vs Diyabet kısıtlaması -> Tıbbi kısıtlama her zaman önceliklidir.
    """
    template = PromptManager.get_agent_prompt("triage", "v1")
    prompt = PromptManager.hydrate_prompt(template, {
        "profil_ozeti": state['profil_ozeti'],
        "ilaclar": state.get('ilaclar', []),
        "istek": state['istek']
    })
    cevap = invoke_with_model_fallback(prompt)
    icerik = parse_llm_response(cevap)
    logger.info("Triyaj Uzmanı çakışmaları çözdü: %s", icerik[:100] + "...")
    return _governance_update(
        state,
        "ClinicalPriorityResolved",
        "triage",
        metadata={"output_chars": len(icerik)},
        klinik_oncelik=icerik,
    )

def beslenme_uzmani(state: AgentState) -> dict:
    """
    Hastalık profilini, klinik öncelikleri ve geçmiş mesajları birleştirip Klinik Diyetisyenimize iletiyoruz.
    Buradan sadece tek bir net yemek önerisi dönmesini bekliyoruz.
    """
    hata_notu = f"Previous error to avoid: {state.get('uyari_mesaji')}. Do NOT suggest this meal again!" if state.get('uyari_mesaji') else ""
    
    hafiza_metni = _hafiza_metni_olustur(state, "No past negative feedback or lab records.")
    sohbet_gecmisi_str = _sohbet_gecmisi_metni(state, son_n=5)
            
    template = PromptManager.get_agent_prompt("dietitian", "v1")
    prompt = PromptManager.hydrate_prompt(template, {
        "profil_ozeti": state['profil_ozeti'],
        "klinik_oncelik": state.get('klinik_oncelik', 'Bulunmuyor.'),
        "hafiza_metni": hafiza_metni,
        "sohbet_gecmisi_str": sohbet_gecmisi_str,
        "istek": state['istek'],
        "hata_notu": hata_notu
    })
    
    cevap = invoke_with_model_fallback(prompt)
    icerik = parse_llm_response(cevap)
    
    deneme = state.get("deneme_sayisi", 0) + 1
    return _governance_update(
        state,
        "NutritionOptionsGenerated",
        "nutrition_capability",
        metadata={"attempt": deneme, "output_chars": len(icerik)},
        uzman_onerisi=icerik,
        deneme_sayisi=deneme,
        hedef_islem="SECENEK_SUN_BITTI",
    )


def denetleyici_node(state: AgentState) -> dict:
    """
    Sistemin en kritik katmanı olan Tıbbi Denetim Kurulu (Guardrail) burada kuruyoruz.
    Diyetisyenin önerdiği yemeği, kullanıcının tıbbi profiliyle çapraz kontrole (audit) sokuyoruz.
    """
    onerilen_yemek = state["uzman_onerisi"]
    quality_profile = _quality_profile_from_summary(state.get("profil_ozeti", ""))
    policy_result = PolicyEngine().check_policy(quality_profile, state.get("hedef_islem", "meal_recommendation"))
    rule_result = RuleEngine().check_rules(quality_profile, onerilen_yemek, [onerilen_yemek])
    quality_events = [
        make_event(
            "PolicyChecked",
            "policy_engine",
            status="review" if policy_result.get("requires_review") else "ok",
            metadata={
                "requires_review": bool(policy_result.get("requires_review")),
                "policies_count": len(policy_result.get("applied_policies", [])),
            },
        ),
        make_event(
            "RuleChecked",
            "rule_engine",
            status="blocked" if rule_result.get("found_risks") else "ok",
            metadata={
                "risk_count": len(rule_result.get("found_risks", [])),
                "medical_risk_score": rule_result.get("medical_risk_score", 0.0),
            },
        ),
    ]
    state = dict(state)
    state["governance_events"] = list(state.get("governance_events") or []) + quality_events

    if rule_result.get("found_risks"):
        confidence = calculate_confidence(
            safe=False,
            evidence_found=True,
            citations=[],
            deterministic_block=True,
        )
        return _governance_update(
            state,
            "RuleTriggered",
            "rule_engine",
            status="blocked",
            metadata={"risks": rule_result["found_risks"]},
            guvenli_mi=False,
            uyari_mesaji=" ".join(rule_result["found_risks"]),
            risk_score=confidence["medical_risk"],
            confidence=confidence,
        )
    
    # Yönlendirici ajan bazen yemek ismini çekemeyip doğrudan kullanıcının girdiği sayıyı ("3") yollayabiliyor.
    # Bu durumda tıbbi denetim "3 bir yemek değildir" deyip reddediyor ve sistem başa sarıyordu.
    # Şef ajanımız sayıları algılayıp geçmişten yemeği bulabildiği için, kısa/sayısal girdileri otomatik onaylıyoruz.
    if onerilen_yemek.strip().isdigit():
        resolved_meal = _resolve_numeric_meal_selection(onerilen_yemek, state)
        if resolved_meal:
            state = dict(state)
            selected_index = int(onerilen_yemek.strip())
            state["uzman_onerisi"] = resolved_meal
            onerilen_yemek = resolved_meal
            state["governance_events"] = list(state.get("governance_events") or []) + [
                make_event(
                    "MealSelectionResolved",
                    "conversation_context",
                    metadata={"selected_index": selected_index},
                )
            ]
        else:
            warning = (
                "Seçtiğin numarayı önceki seçeneklerle güvenli biçimde eşleştiremedim. "
                "İlaç-besin etkileşimini doğrulayabilmem için yemek adını açıkça yazar mısın? "
                "Emin olmadığın durumda doktoruna veya eczacına danış."
            )
            confidence = calculate_confidence(
                safe=True,
                evidence_found=False,
                citations=[],
            )
            confidence["medical_risk"] = max(float(confidence.get("medical_risk", 0.0)), 0.5)
            return _governance_update(
                state,
                "MedicationSafetyChecked",
                "medical_knowledge.safety_checker",
                status="review",
                metadata={"severity": "unknown", "reason": "numeric_selection_unresolved"},
                hedef_islem="SOHBET",
                guvenli_mi=True,
                uyari_mesaji=warning,
                tarif_metni=warning,
                uzman_onerisi=None,
                risk_score=confidence["medical_risk"],
                confidence=confidence,
            )

    if not onerilen_yemek.strip().isdigit() and len(onerilen_yemek.strip()) <= 3:
        warning = (
            "Yemek adını net anlayamadığım için ilaç-besin etkileşimini doğrulayamadım. "
            "Lütfen yemeğin adını açıkça yaz; emin olmadığın durumda sağlık profesyoneline danış."
        )
        confidence = calculate_confidence(
            safe=True,
            evidence_found=False,
            citations=[],
        )
        confidence["medical_risk"] = max(float(confidence.get("medical_risk", 0.0)), 0.5)
        return _governance_update(
            state,
            "MedicationSafetyChecked",
            "medical_knowledge.safety_checker",
            status="review",
            metadata={"severity": "unknown", "reason": "short_selection_unresolved"},
            hedef_islem="SOHBET",
            guvenli_mi=True,
            uyari_mesaji=warning,
            tarif_metni=warning,
            uzman_onerisi=None,
            risk_score=confidence["medical_risk"],
            confidence=confidence,
        )

    ilaclar = state.get("ilaclar") or []
    medication_safety = check_medication_food_safety(ilaclar, onerilen_yemek)
    state = dict(state)
    state["governance_events"] = list(state.get("governance_events") or []) + medication_safety_events(medication_safety)
    deterministik_ilac_riskleri = [
        f"{rule['medication']}: {rule['explanation']}"
        for rule in medication_safety.get("matched_rules", [])
    ]
    if medication_safety.get("severity") == "unknown" and medication_safety.get("needs_professional_review"):
        warning = (
            "İlaç-besin etkileşimi doğrulanamadı; kayıtlı ilacın güvenli eşleşmesini yapamadım. "
            "Bu öneriyi uygulamadan önce doktoruna veya eczacına danış."
        )
        confidence = calculate_confidence(
            safe=True,
            evidence_found=False,
            citations=[],
        )
        confidence["medical_risk"] = max(float(confidence.get("medical_risk", 0.0)), 0.5)
        updated = {
            "guvenli_mi": True,
            "uyari_mesaji": warning,
            "risk_score": confidence["medical_risk"],
            "confidence": confidence,
        }
        if state.get("hedef_islem") in {"SOHBET", "SECENEK_SUN", "SECENEK_SUN_BITTI"}:
            updated["uzman_onerisi"] = f"{onerilen_yemek}\n\n{warning}"
        return _governance_update(
            state,
            "MedicationReviewRequired",
            "medical_knowledge.safety_checker",
            status="review",
            metadata={
                "severity": medication_safety.get("severity"),
                "needs_professional_review": True,
            },
            **updated,
        )
    if deterministik_ilac_riskleri:
        sebep = " ".join(deterministik_ilac_riskleri)
        logger.warning("Deterministik ilac-besin kurali calisti: %s", sebep)
        confidence = calculate_confidence(
            safe=False,
            evidence_found=True,
            citations=[],
            deterministic_block=True,
        )
        return _governance_update(
            state,
            "RuleTriggered",
            "medication_safety",
            status="blocked" if medication_safety.get("severity") == "avoid" else "review",
            metadata={
                "risks": deterministik_ilac_riskleri,
                "severity": medication_safety.get("severity"),
                "needs_professional_review": medication_safety.get("needs_professional_review"),
            },
            guvenli_mi=False,
            uyari_mesaji=sebep,
            risk_score=confidence["medical_risk"],
            confidence=confidence,
        )

    # RAG: Veritabanındaki makalelerden yemeğe veya hasta profiline uygun bilimsel kuralları getir
    ilac_sorgu_metni = ", ".join(ilaclar) if ilaclar else "Yok"
    sorgu = f"İlaç Besin Etkileşimi: Kullanılan İlaçlar: {ilac_sorgu_metni} - Önerilen Yemek: {onerilen_yemek} - Profil: {state['profil_ozeti']}"
    
    klinik_kanit = klinik_bilgi_getir(sorgu, k_adet=4)
    citations = extract_citations_from_rag(klinik_kanit)
    citation_scores = [
        CitationValidator().validate_citation(
            citation.get("chunk_id") or citation.get("source_id") or "unknown",
            citation.get("evidence_span") or "",
        )
        for citation in citations
    ]
    if klinik_kanit:
        logger.info("Tıbbi Denetim Kurulu RAG çalıştırdı. %d karakterlik kanıt bulundu.", len(klinik_kanit))
        
    hafiza_metni = _hafiza_metni_olustur(state, "No past negative feedback or lab records.")
    
    template = PromptManager.get_agent_prompt("auditor", "v1")
    prompt = PromptManager.hydrate_prompt(template, {
        "profil_ozeti": state['profil_ozeti'],
        "hafiza_metni": hafiza_metni,
        "onerilen_yemek": onerilen_yemek,
        "klinik_kanit": klinik_kanit or ""
    })
    
    cevap = invoke_with_model_fallback(prompt)
    icerik = parse_llm_response(cevap)
    
    if "SAFE: NO" in icerik.upper():
        sebep = icerik.split("REASON:")[1].strip() if "REASON:" in icerik else "Tıbbi profilinize uygun değil."
        logger.warning("Tıbbi kalkanımız devrede: %s yemeğini sizin için güvenli bulmadık. Sebep: %s", onerilen_yemek, sebep)
        confidence = calculate_confidence(
            safe=False,
            evidence_found=bool(klinik_kanit),
            citations=citations,
        )
        return _governance_events_update(
            state,
            [
                make_event(
                    "RetrieverExecuted",
                    "evidence_retrieval",
                    metadata={
                        "evidence_found": bool(klinik_kanit),
                        "citation_count": len(citations),
                        "citation_validation_min": min(citation_scores) if citation_scores else 0.0,
                    },
                ),
                make_event(
                    "RiskClassified",
                    "auditor",
                    status="blocked",
                    metadata={"reason": sebep, "risk_score": confidence["medical_risk"]},
                ),
            ],
            guvenli_mi=False,
            uyari_mesaji=sebep,
            risk_score=confidence["medical_risk"],
            confidence=confidence,
            citations=citations,
        )
        
    logger.info("Harika haber! %s yemeği tıbbi profilinize %%100 uygun bulundu.", onerilen_yemek)
    confidence = calculate_confidence(
        safe=True,
        evidence_found=bool(klinik_kanit),
        citations=citations,
    )
    return _governance_events_update(
        state,
        [
            make_event(
                "RetrieverExecuted",
                "evidence_retrieval",
                    metadata={
                        "evidence_found": bool(klinik_kanit),
                        "citation_count": len(citations),
                        "citation_validation_min": min(citation_scores) if citation_scores else 0.0,
                    },
                ),
            make_event(
                "RiskClassified",
                "auditor",
                metadata={"safe": True, "risk_score": confidence["medical_risk"]},
            ),
        ],
        guvenli_mi=True,
        uyari_mesaji="",
        risk_score=confidence["medical_risk"],
        confidence=confidence,
        citations=citations,
    )

def haftalik_plan_olustur(profil_ozeti: str, hafiza_metni: str) -> str:
    """
    Tıbbi profil ve hafızadaki negatif geri bildirimleri (sevmediklerini) birleştirip,
    kullanıcıya özel 7 günlük (3 öğün) bir haftalık diyet planı hazırlıyoruz.
    """
    prompt = f"""
    You are an expert Clinical Dietitian.
    
    PATIENT PROFILE (Diseases, Allergies): {profil_ozeti}
    PATIENT'S NEGATIVE FEEDBACK (Do not suggest these): {hafiza_metni}
    
    YOUR TASK:
    Create a complete 7-day meal plan (Monday to Sunday) with 3 meals per day (Breakfast, Lunch, Dinner).
    
    STRICT MEDICAL GUARDRAILS (CRITICAL):
    1. You must independently identify ALL dietary restrictions associated with the patient's listed diseases (e.g., if Gut disease is present, strictly eliminate all high-purine foods, yeast, specific meats, and certain dairy).
    2. Before adding ANY meal to the table, mentally verify it against EVERY disease and allergy in the profile. If there is even a 1% risk of it being contraindicated, DO NOT use it.
    3. Another AI agent will verify your menu later. If you suggest a harmful food, the system will crash and the patient will lose trust. Be extremely conservative.
    4. Exclude any allergies or negatively reviewed items completely.
    
    REQUIREMENTS:
    - HIGH VARIETY & PSYCHOLOGICAL SUSTAINABILITY: The most important aspect of a diet is adherence. Create a highly varied, engaging, and delicious menu so the patient never feels restricted or bored.
    - DIETARY BALANCE & ENJOYMENT: Leave room for enjoyment. Automatically include safe, profile-compliant desserts, snacks, or comforting meals (e.g., sugar-free alternatives for diabetics) to keep the patient motivated.
    - Let your clinical intelligence decide the best culinary variety. Do not stick to monotonous or repetitive meal patterns.
    - Use accessible ingredients but combine them in exciting ways.
    - Output the result as a beautiful Markdown table in Turkish.
    - The table should have columns for 'Gün' (Day), 'Sabah' (Breakfast), 'Öğle' (Lunch), and 'Akşam' (Dinner).
    - CRITICAL: Inside the table cells, next to each meal name, you MUST include the estimated Calories and Macros (Protein, Carbs, Fats) in parentheses. Example: "Menemen (320 kcal, 15g P, 10g K, 20g Y)".
    - Provide ONLY the Markdown table, without any conversational text before or after.
    """
    
    logger.info("Sizin için özenle 7 günlük, sağlıklı ve lezzetli bir beslenme planı hazırlıyoruz...")
    cevap = invoke_with_model_fallback(prompt)
    return parse_llm_response(cevap)

def mutfak_sefi_node(state: AgentState) -> dict:
    """
    Tıbbi denetimden (Guardrail) başarıyla geçen yemeğin en güncel tarifini 
    ve malzemelerini üretiyoruz. İnternet bağımlılığını kaldırdık, LLM kendi şeflik 
    becerilerini kullanıyor (Hız ve kararlılık artışı).
    """
    onerilen_yemek = str(state.get("uzman_onerisi", "Sağlıklı Yemek"))[:50]
    logger.info("Mutfak şefimiz %s yemeğinin en güzel tarifini hazırlıyor...", onerilen_yemek)
    
    sohbet_gecmisi_str = _sohbet_gecmisi_metni(state)
    
    prompt = f"""
    You are an expert Clinical Dietitian and Master Chef. Create a detailed recipe for the meal provided.
    If the meal name looks like a full paragraph instead of a name, extract the main dish idea and write a recipe for it.
    
    MEAL REQUESTED: '{state.get("uzman_onerisi", "Sağlıklı Yemek")}'
    
    CRITICAL INSTRUCTION: If the "MEAL REQUESTED" is just a number (e.g. "2", "3", "option 1"), you MUST look at the RECENT CHAT HISTORY below, find the exact meal name that corresponds to that number from the assistant's previous suggestions, and write the recipe for THAT specific meal. DO NOT invent a random meal.
    
    PATIENT PROFILE (CRITICAL): {state['profil_ozeti']}
    USER'S ORIGINAL CRAVING/REQUEST: {state.get('istek', 'Bilinmiyor')}
    
    RECENT CHAT HISTORY:
    {sohbet_gecmisi_str}
    
    Format the response in markdown:
    
    ### 👨‍🍳 Şefin Mesajı
    (Acknowledge the user's original request here. If they asked for something unhealthy for their profile like "meat" but you are suggesting a vegetable/egg dish instead, kindly explain WHY you changed it for their health. Example: "Canınız et çekmiş ancak Gut hastalığınız olduğu için pürin riskini göze alamayız, bu yüzden size harika bir alternatif hazırladım...")

    ### 🛒 Malzemeler
    (Bullet points)
    
    ### 🍳 Yapılışı
    (Numbered list)
    
    ### 📊 Porsiyon, Kalori ve Makro Değerleri
    (Provide a DETAILED estimate per portion: Total Calories, Protein (g), Carbohydrates (g), and Fats (g). This is CRITICAL for the user's fitness/diet goals!)
    
    MEDICAL GUARDRAIL: You MUST adjust the recipe based on the patient's profile. 
    For example, if the patient has "hipertansiyon" (hypertension), you MUST strictly reduce or eliminate salt (tuz) in the recipe and add a "Chef's Medical Note" about it.
    If they have diabetes, remove added sugar.
    
    IMPORTANT: Write the entire recipe in Turkish language.
    """
    
    cevap = invoke_with_model_fallback(prompt)
    tarif = parse_llm_response(cevap)
    if state.get("uyari_mesaji"):
        tarif = f"{state['uyari_mesaji']}\n\n{tarif}"
    return _governance_update(
        state,
        "FinalAnswerGenerated",
        "chef_capability",
        metadata={"output_chars": len(tarif)},
        tarif_metni=tarif,
    )

def aile_ortak_menu_olustur(profil_ozeti_listesi: str) -> str:
    """
    Tüm aile üyelerinin profillerini alıp ortak 5 yemeklik bir menü üretir.
    """
    prompt = f"""
    You are an expert Clinical Dietitian and Family Chef specializing in Turkish cuisine.
    
    FAMILY PROFILES (Allergies, Diseases, Needs):
    {profil_ozeti_listesi}
    
    YOUR TASK:
    Analyze ALL family members' medical restrictions. 
    You must find the "lowest common denominator" — meaning you must ONLY suggest foods that are 100% safe for EVERY SINGLE MEMBER of the family.
    If one person has diabetes and another has celiac, the food MUST be BOTH sugar-free and gluten-free.
    
    REQUIREMENTS:
    - Suggest exactly 5 traditional Turkish main courses (Ana Yemek).
    - For each dish, explain BRIEFLY why it is perfectly safe for the specific diseases in the family (e.g. "Ahmet'in diyabeti için şekersiz, Ayşe'nin çölyak hastalığı için glütensizdir").
    - Format as a beautiful Markdown list in Turkish. Do not add any extra conversational text.
    """
    
    logger.info("Tüm ailenin güvenle yiyebileceği ortak, sağlıklı bir sofra hazırlıyoruz...")
    cevap = invoke_with_model_fallback(prompt)
    return parse_llm_response(cevap)

def mutfak_asistani(profil_ozeti: str, malzemeler: str) -> str:
    """
    Buzdolabındaki malzemeleri ve hastanın tıbbi profilini alarak,
    kullanıcıya özel %100 güvenli bir yemek tarifi üretir.
    """
    logger.info("Mutfaktaki malzemelerinize bakıyoruz... Size özel, pratik ve güvenli bir tarif yolda!")
    
    prompt = f"""
    You are an expert Clinical Dietitian and Master Chef of Traditional Turkish Cuisine.
    
    PATIENT'S MEDICAL PROFILE (Diseases, Allergies, Medications, Height, Weight):
    {profil_ozeti}
    
    AVAILABLE INGREDIENTS IN THE PATIENT'S FRIDGE/KITCHEN:
    {malzemeler}
    
    YOUR TASK:
    Create a delicious and traditional Turkish recipe using MAINLY the available ingredients.
    (You may assume basic pantry staples like salt, pepper, olive oil, water, onion, and garlic are always available).
    
    STRICT MEDICAL GUARDRAILS (CRITICAL):
    1. The recipe MUST be 100% safe and compliant with the patient's medical profile.
    2. If the available ingredients list contains ANY item that is HARMFUL or RISKY for the patient's conditions (e.g., sugar for a diabetic, gluten for celiac), you MUST NOT use that ingredient in the recipe!
    3. If you eliminate a harmful ingredient, you MUST warn the patient in the "Şefin Yorumu ve Tıbbi Uyarı" section explaining medically why you didn't use it.
    4. CUREBOT INTEGRATION (CRITICAL): If you see an "Unknown Container/Sauce" or "Bilinmeyen Kap/Sos" in the ingredients, YOU MUST explicitly tell the user: "⚠️ Fotoğrafta ne olduğunu anlayamadığım bir sos/kap gördüm. Eğer bunun ne olduğunu sayfanın yanındaki **CureBot** asistanına yazarsanız (Örn: 'Buzdolabındaki o sos mayonezdi'), tarifi sizin için anında güncelleyebilir."
    
    OUTPUT FORMAT (Use Markdown and write strictly in TURKISH):
    
    # 🥘 Yemek Adı: [Geliştirdiğiniz Yemeğin Adı]
    
    ### 👨‍🍳 Şefin Yorumu ve Tıbbi Uyarı
    (Briefly explain to the patient why this meal is safe for them, and if you excluded any harmful ingredients they had, explain the medical reason).
    
    ### 🛒 Kullanılan Malzemeler
    (Bullet points)
    
    ### 🍳 Yapılışı
    (Numbered list of step-by-step cooking instructions)
    """
    
    cevap = invoke_with_model_fallback(prompt)
    return parse_llm_response(cevap)

def adime_raporlayici_node(state: AgentState) -> dict:
    """
    Sistemin ürettiği nihai tarifi/planı uluslararası ADIME (JSON) formatına dönüştürür.
    """
    prompt = f"""
    You are a Clinical Documentation Specialist. Your task is to convert the generated meal plan and patient data into a strict JSON object following the ADIME structure.
    
    Patient Profile: {state['profil_ozeti']}
    Final Meal/Intervention: {state.get('tarif_metni', state.get('uzman_onerisi', 'Bulunmuyor.'))}
    Guardrail Warnings: {state.get('uyari_mesaji', 'Yok')}
    Triage Priorities: {state.get('klinik_oncelik', 'Yok')}
    
    Convert this into a valid JSON block exactly following this schema:
    {{
        "assessment": "Summary of patient profile and current state",
        "diagnosis": "The primary nutritional diagnosis and risks",
        "intervention": "The final approved meal and its macros",
        "monitoring_evaluation": "What the patient should monitor (e.g. blood sugar after 2 hours)"
    }}
    
    RETURN ONLY JSON.
    """
    cevap = invoke_with_model_fallback(prompt)
    icerik = parse_llm_response(cevap)
    # Temizleme (Eğer LLM markdown ile dönerse)
    icerik = icerik.replace("```json", "").replace("```", "").strip()
    return _governance_update(
        state,
        "ClinicalDocumentationGenerated",
        "adime_reporter",
        metadata={"output_chars": len(icerik)},
        adime_raporu=icerik,
        hedef_islem="RAPORLANDI",
    )
