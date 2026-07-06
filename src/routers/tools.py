from fastapi import APIRouter, Depends, HTTPException, Request, BackgroundTasks, UploadFile, File, Form
from fastapi.responses import JSONResponse
from fastapi.concurrency import run_in_threadpool
import sqlite3
import json

from src.models import HaftalikPlanRequest, ScanMenuRequest, ScanMenuImageRequest, FridgeScanRequest, PlanActionRequest
from src.database import get_db, etkilesim_logla, klinik_karar_kaydet, profil_getir_db
from src.auth import get_current_user
from src.messages import PLAN_OLUSTURULAMADI, MENU_BOS, MENU_FOTO_OKUNAMADI, BUZDOLABI_FOTO_OKUNAMADI, PROFIL_GEREKLI, PROFIL_BULUNAMADI
from src.nodes import haftalik_plan_olustur, mutfak_asistani
from src.scanner import scrape_menu_from_url, extract_text_from_image_base64, extract_ingredients_from_image_base64
from src.menu_agent import menu_danismani
from src.economist_agent import alisveris_ve_butce_hesapla
from src.profil_utils import profil_ozeti_olustur, aile_profil_ozeti_olustur
from src.memory import hafizadakini_getir, geri_bildirim_ekle
from src.llm import invoke_with_model_fallback, parse_llm_response
import fitz
from src.governance.decision import build_decision_record, calculate_confidence
from src.agent_state import create_initial_state
from pydantic import BaseModel

class ShoppingListRequest(BaseModel):
    plan_metni: str
    location_info: str | None = None

router = APIRouter()

MAX_HEALTH_RECORD_BYTES = 10 * 1024 * 1024
PDF_CONTENT_TYPES = {"application/pdf", "application/x-pdf", "application/octet-stream"}

def _get_profil_ve_hedef(telefon: str, kimin_icin: str, db: sqlite3.Connection):
    profil = profil_getir_db(telefon, conn=db)
    if profil is None:
        raise HTTPException(status_code=404, detail=PROFIL_BULUNAMADI)

    if kimin_icin == "aile":
        return profil, None

    hedef = profil.ana_kullanici
    if kimin_icin != "kendim":
        hedef = next((uye for uye in profil.aile_uyeleri if uye.ad.lower() == kimin_icin.lower()), None)

    if hedef is None:
        raise HTTPException(status_code=400, detail=PROFIL_GEREKLI)

    return profil, hedef

def _profil_baglamini_hazirla(telefon: str, kimin_icin: str, db: sqlite3.Connection):
    profil, hedef = _get_profil_ve_hedef(telefon, kimin_icin, db=db)
    if kimin_icin == "aile":
        return profil, aile_profil_ozeti_olustur(profil), "user_family"

    if hedef is None:
        raise HTTPException(status_code=400, detail=PROFIL_GEREKLI)
    return profil, profil_ozeti_olustur(hedef), f"user_{hedef.ad.lower()}"

@router.post("/api/weekly-plan")
async def weekly_plan(request: Request, req: HaftalikPlanRequest, bg_tasks: BackgroundTasks, telefon: str = Depends(get_current_user), db: sqlite3.Connection = Depends(get_db)):
    _, profil_ozeti, kullanici_id = _profil_baglamini_hazirla(telefon, req.kimin_icin, db=db)
    if kullanici_id is None:
        raise HTTPException(status_code=400, detail=PROFIL_GEREKLI)
        
    gecmis = await run_in_threadpool(hafizadakini_getir, kullanici_id, "yemek", 10)
    hafiza_metni = " ".join(gecmis) if gecmis else "Kayıtlı geri bildirim yok."
    
    try:
        plan = await run_in_threadpool(haftalik_plan_olustur, profil_ozeti, hafiza_metni, req.is_regeneration)
        
        # Governance
        initial_state = create_initial_state(istek="Haftalık plan oluştur", profil_ozeti=profil_ozeti, hafiza=gecmis)
        state = dict(initial_state)
        state["tarif_metni"] = plan
        state["hedef_islem"] = "HAFTALIK_PLAN"
        
        decision_record = build_decision_record(state, telefon=telefon, kimin_icin=req.kimin_icin, final_answer=plan)
        bg_tasks.add_task(klinik_karar_kaydet, decision_record)
        bg_tasks.add_task(etkilesim_logla, telefon, "", "Haftalık Plan", f"{req.kimin_icin} için plan", plan, None)
        
        return {"success": True, "plan": plan}
    except Exception as e:
        import logging
        logging.getLogger(__name__).exception("Haftalik plan olusturulamadi")
        return JSONResponse(status_code=503, content={"success": False, "detail": PLAN_OLUSTURULAMADI})

@router.post("/api/shopping-list")
async def shopping_list(request: Request, req: ShoppingListRequest, telefon: str = Depends(get_current_user)):
    try:
        rapor = await run_in_threadpool(alisveris_ve_butce_hesapla, req.plan_metni, req.location_info)
        return {"success": True, "rapor": rapor}
    except Exception as e:
        import logging
        logging.getLogger(__name__).exception("Alisveris listesi olusturulamadi")
        return JSONResponse(status_code=503, content={"success": False, "detail": "Alışveriş listesi şu anda oluşturulamadı. Lütfen birazdan tekrar deneyin."})

@router.post("/api/scan-menu")
async def scan_menu(request: Request, req: ScanMenuRequest, bg_tasks: BackgroundTasks, telefon: str = Depends(get_current_user), db: sqlite3.Connection = Depends(get_db)):
    _, profil_ozeti, _ = _profil_baglamini_hazirla(telefon, req.kimin_icin, db=db)
        
    ham_metin = await run_in_threadpool(scrape_menu_from_url, req.url)
    if not ham_metin or len(ham_metin) < 10:
        return {"success": False, "detail": MENU_BOS}
        
    analiz_sonucu = await run_in_threadpool(menu_danismani, ham_metin, profil_ozeti)
    
    initial_state = create_initial_state(istek=f"Menü Tarama: {req.url}", profil_ozeti=profil_ozeti, hafiza=[])
    state = dict(initial_state)
    state["tarif_metni"] = analiz_sonucu
    state["hedef_islem"] = "MENU_TARAMA"
    
    decision_record = build_decision_record(state, telefon=telefon, kimin_icin=req.kimin_icin, final_answer=analiz_sonucu)
    bg_tasks.add_task(klinik_karar_kaydet, decision_record)
    bg_tasks.add_task(etkilesim_logla, telefon, "", "QR Menü", req.url, analiz_sonucu, None)
    
    return {"success": True, "analiz": analiz_sonucu}

@router.post("/api/scan-menu-image")
async def scan_menu_image(request: Request, req: ScanMenuImageRequest, bg_tasks: BackgroundTasks, telefon: str = Depends(get_current_user), db: sqlite3.Connection = Depends(get_db)):
    _, profil_ozeti, _ = _profil_baglamini_hazirla(telefon, req.kimin_icin, db=db)
    
    try:
        ham_metin = await run_in_threadpool(extract_text_from_image_base64, req.image_base64)
        if not ham_metin or len(ham_metin) < 5:
            return {"success": False, "detail": MENU_FOTO_OKUNAMADI}
            
        analiz_sonucu = await run_in_threadpool(menu_danismani, ham_metin, profil_ozeti)
        
        initial_state = create_initial_state(istek="Menü Fotoğrafı Tarama", profil_ozeti=profil_ozeti, hafiza=[])
        state = dict(initial_state)
        state["tarif_metni"] = analiz_sonucu
        state["hedef_islem"] = "MENU_TARAMA"
        
        decision_record = build_decision_record(state, telefon=telefon, kimin_icin=req.kimin_icin, final_answer=analiz_sonucu)
        bg_tasks.add_task(klinik_karar_kaydet, decision_record)
        bg_tasks.add_task(etkilesim_logla, telefon, "", "Menü Foto", "Fotoğraf yüklendi", analiz_sonucu, None)
        
        return {"success": True, "analiz": analiz_sonucu}
    except Exception as e:
        import logging
        logging.getLogger(__name__).exception("Menü okunamadı")
        return JSONResponse(status_code=503, content={"success": False, "detail": "Menü fotoğrafı şu anda okunamadı. Lütfen daha net bir görsel ile tekrar deneyin."})

@router.post("/api/fridge-scan")
async def fridge_scan(request: Request, req: FridgeScanRequest, bg_tasks: BackgroundTasks, telefon: str = Depends(get_current_user), db: sqlite3.Connection = Depends(get_db)):
    _, profil_ozeti, _ = _profil_baglamini_hazirla(telefon, req.kimin_icin, db=db)
    
    try:
        malzemeler = await run_in_threadpool(extract_ingredients_from_image_base64, req.image_base64)
        if not malzemeler or len(malzemeler) < 3:
            return {"success": False, "detail": BUZDOLABI_FOTO_OKUNAMADI}
            
        tarif = await run_in_threadpool(mutfak_asistani, profil_ozeti, malzemeler)
        
        initial_state = create_initial_state(istek="Buzdolabı Tarama", profil_ozeti=profil_ozeti, hafiza=[])
        state = dict(initial_state)
        state["tarif_metni"] = tarif
        state["hedef_islem"] = "BUZDOLABI_TARAMA"
        
        decision_record = build_decision_record(state, telefon=telefon, kimin_icin=req.kimin_icin, final_answer=tarif)
        bg_tasks.add_task(klinik_karar_kaydet, decision_record)
        bg_tasks.add_task(etkilesim_logla, telefon, "", "Buzdolabı", malzemeler[:100], tarif, None)
        
        return {"success": True, "malzemeler": malzemeler, "tarif": tarif}
    except Exception as e:
        import logging
        logging.getLogger(__name__).exception("Buzdolabı okunamadı")
        return JSONResponse(status_code=503, content={"success": False, "detail": BUZDOLABI_FOTO_OKUNAMADI})

@router.post("/api/upload-health-record")
async def upload_health_record(
    bg_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    kimin_icin: str = Form("kendim"),
    telefon: str = Depends(get_current_user),
    db: sqlite3.Connection = Depends(get_db)
):
    profil, hedef = _get_profil_ve_hedef(telefon, kimin_icin, db=db)
    if kimin_icin == "aile":
        kullanici_id = "user_family"
        ad_soyad = profil.ana_kullanici.ad if profil.ana_kullanici else ""
    else:
        kullanici_id = f"user_{hedef.ad.lower()}"
        ad_soyad = hedef.ad
    
    try:
        filename = (file.filename or "").lower()
        content_type = (file.content_type or "").lower()
        if not filename.endswith(".pdf") or (content_type and content_type not in PDF_CONTENT_TYPES):
            return JSONResponse(status_code=400, content={"success": False, "detail": "Lütfen PDF formatında bir tahlil dosyası yükleyin."})

        content = await file.read(MAX_HEALTH_RECORD_BYTES + 1)
        if not content:
            return JSONResponse(status_code=400, content={"success": False, "detail": "Yüklenen PDF boş görünüyor."})
        if len(content) > MAX_HEALTH_RECORD_BYTES:
            return JSONResponse(status_code=413, content={"success": False, "detail": "PDF dosyası çok büyük. Lütfen 10 MB altında bir dosya yükleyin."})

        doc = fitz.open(stream=content, filetype="pdf")
        text = "\n".join([page.get_text() for page in doc])
        doc.close()
        if not text.strip():
            return JSONResponse(status_code=422, content={"success": False, "detail": "PDF içindeki metin okunamadı. Daha net veya metin içeren bir PDF yükleyin."})
        
        prompt_template = """Read the following health/lab report and write a VERY SHORT summary (max 4-5 sentences) of the dietary considerations (deficiencies, excesses). Do not make long lists.
Also, extract the QUANTITATIVE (numerical) biomarkers from the report and MUST append a JSON block at the very end of your text in exactly this format:
```json
{"biomarkers": [{"name": "Glucose", "value": 95.0, "unit": "mg/dL"}]}
```
Focus only on biomarkers relevant to nutrition. Write the summary text entirely in Turkish.

Health Report:
%s"""
        prompt = prompt_template % (text[:5000])
        cevap = invoke_with_model_fallback(prompt)
        from src.llm import parse_llm_response
        ozet = parse_llm_response(cevap)
        
        import re, json
        metadata_json = None
        
        # Locate potential JSON blocks / Olası JSON bloklarını tespit et
        json_start_match = re.search(r'```json\s*\{|\{\s*"biomarkers"', ozet)
        
        if json_start_match:
            json_start_index = json_start_match.start()
            json_text = ozet[json_start_index:]
            ozet = ozet[:json_start_index].strip()
            
            # Clean trailing markdown ticks / Sondaki markdown kalıntılarını temizle
            if ozet.endswith('```json'):
                ozet = ozet[:-7].strip()
            elif ozet.endswith('```'):
                ozet = ozet[:-3].strip()
                
            # Strip markdown formatting / Markdown formatlamasını temizle
            clean_json_text = json_text.replace('```json', '').split('```')[0].strip()
            
            # Parse JSON block / JSON bloğunu ayrıştır
            try:
                # Ensure object notation starts correctly / Obje gösteriminin doğru başladığından emin ol
                if not clean_json_text.startswith('{'):
                    clean_json_text = '{' + clean_json_text
                    
                parsed_json = json.loads(clean_json_text)
                metadata_json = json.dumps(parsed_json, ensure_ascii=False)
            except Exception:
                pass
        
        geri_bildirim_ekle(kullanici_id, f"{file.filename} Özeti: {ozet}")
        bg_tasks.add_task(etkilesim_logla, telefon, ad_soyad, "Tahlil", file.filename, ozet, metadata_json)
        
        return {"success": True, "ozet": ozet}
    except Exception as e:
        import logging
        logging.getLogger(__name__).exception("Tahlil okunamadı")
        return JSONResponse(status_code=503, content={"success": False, "detail": "Tahlil şu anda okunamadı. Lütfen dosyayı kontrol edip birazdan tekrar deneyin."})

@router.post("/api/plan-action")
async def plan_action(request: Request, req: PlanActionRequest, bg_tasks: BackgroundTasks, telefon: str = Depends(get_current_user), db: sqlite3.Connection = Depends(get_db)):
    from src.llm import invoke_with_model_fallback, parse_llm_response
    import json
    import re
    
    # Kullanıcı profilini çekiyoruz (Ana profil sayılır)
    cursor = db.cursor()
    cursor.execute("SELECT profil_data FROM profiles WHERE telefon=?", (telefon,))
    row = cursor.fetchone()
    if not row:
        return JSONResponse(status_code=400, content={"success": False, "detail": "Profil bulunamadı."})
    
    profil_ozeti = row[0]
    
    if req.action_type == "recipe":
        prompt = f"""The user is requesting a detailed recipe for the following meal: "{req.meal_text}"
Patient Profile: {profil_ozeti}

Write a healthy, delicious, and detailed recipe for this meal, calculated specifically for this user's profile. Include estimated macronutrient values.
Format the output in Markdown. Include sections for Title, Ingredients, and Instructions.
Write the final response entirely in Turkish."""
        
        try:
            tarif_cevap_obj = await run_in_threadpool(invoke_with_model_fallback, prompt)
            tarif_metni = parse_llm_response(tarif_cevap_obj)
            bg_tasks.add_task(etkilesim_logla, telefon, "", "Plan-Tarif", req.meal_text, tarif_metni, None)
            return {"success": True, "result": tarif_metni}
        except Exception:
            return JSONResponse(status_code=503, content={"success": False, "detail": "Tarif şu anda hazırlanamadı. Lütfen birazdan tekrar deneyin."})

    elif req.action_type == "alternative":
        prompt = f"""The user stated they cannot eat the following meal from their weekly plan: "{req.meal_text}"
Patient Profile: {profil_ozeti}
Relevant Section of Current Weekly Plan: {req.plan_text}

TASK:
1. Find a COMPLETELY DIFFERENT alternative meal instead of "{req.meal_text}". The user explicitly wants a change, do not suggest the same meal.
2. If the calories or macros (Protein, Carbs, Fats) of this new meal differ from the old one, analyze the OTHER meals for THAT SAME DAY (Breakfast, Lunch, Dinner, etc.). Adjust the portions or ingredients of those other meals to maintain the daily macro and calorie balance. (e.g., if breakfast has less protein now, add chicken to dinner).
3. Add both the originally replaced meal AND any other meals you modified for balance to the `degisen_ogunler` JSON array. If no other meals needed changing, just add the replaced meal.
4. For the "eski" (old) field, write the EXACT string of the meal from the Current Weekly Plan text (including calorie values) so the system can find and replace it. For the "yeni" (new) field, write your new suggested meal in the exact same format.

WARNING: Provide your response ONLY in the following JSON format. Do not use markdown code blocks (` ```json `). All meal names and text inside the JSON must be in Turkish:
{{
  "degisen_ogunler": [
    {{"eski": "Mercimek Çorbası (300 kcal...)", "yeni": "Ezogelin Çorbası (300 kcal...)"}}
  ]
}}"""
        try:
            cevap_obj = await run_in_threadpool(invoke_with_model_fallback, prompt)
            cevap = parse_llm_response(cevap_obj)
            # Extract JSON block using regex / Regex kullanarak JSON bloğunu çıkar
            json_match = re.search(r'\{.*\}', cevap, re.DOTALL)
            if json_match:
                json_text = json_match.group(0)
                try:
                    data = json.loads(json_text)
                    bg_tasks.add_task(etkilesim_logla, telefon, "", "Plan-Alternatif", req.meal_text, json.dumps(data, ensure_ascii=False), None)
                    return {"success": True, "result": data}
                except:
                    pass
            
            # Fallback to raw text on parse error / Ayrıştırma hatasında ham metne dön
            return {"success": True, "result": {"yeni_ogun": "CureBot Özel Alternatifi", "aciklama": cevap}}
        except Exception:
            return JSONResponse(status_code=503, content={"success": False, "detail": "Alternatif öğün şu anda hazırlanamadı. Lütfen birazdan tekrar deneyin."})
            
    elif req.action_type == "snack":
        import datetime
        gunler = ["Pazartesi", "Salı", "Çarşamba", "Perşembe", "Cuma", "Cumartesi", "Pazar"]
        bugun = gunler[datetime.datetime.now().weekday()]
        
        prompt = f"""The user stated they are currently craving a snack/dessert.
CURRENT SYSTEM DAY: Today is {bugun}. Please use the menu for {bugun} as your reference point.

Current Weekly Plan:
{req.plan_text}

Patient Profile:
{profil_ozeti}

TASK:
Suggest 2-3 logical, clinically safe, and portion-controlled alternative snacks/desserts that are COMPLETELY APPROPRIATE for this user's health profile and perfectly balance the macros of their {bugun} menu. 
Briefly explain the recipes and your clinical reasoning in Markdown format.
Do NOT reference the wrong day!
Write the final response entirely in Turkish.

WARNING: Provide your response ONLY in the following JSON format. Do not use markdown code blocks (` ```json `):
{{
  "snack_onerileri": "Buraya Markdown formatında 2-3 atıştırmalık önerisi ve tariflerini, ayrıca bugünkü menüyle nasıl dengelendiğinin açıklamasını yaz."
}}"""
        try:
            snack_cevap_obj = await run_in_threadpool(invoke_with_model_fallback, prompt)
            snack_metni = parse_llm_response(snack_cevap_obj)
            json_match = re.search(r'\{.*\}', snack_metni, re.DOTALL)
            data = {"snack_onerileri": snack_metni}
            if json_match:
                try:
                    data = json.loads(json_match.group(0))
                except:
                    pass
            bg_tasks.add_task(etkilesim_logla, telefon, "", "Plan-Snack", "Atıştırmalık İsteği", snack_metni, None)
            return {"success": True, "result": data}
        except Exception:
            return JSONResponse(status_code=503, content={"success": False, "detail": "Ara öğün önerisi şu anda hazırlanamadı. Lütfen birazdan tekrar deneyin."})
    
    return JSONResponse(status_code=400, content={"success": False, "detail": "Geçersiz action_type"})
