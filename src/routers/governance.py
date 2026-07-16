from fastapi import APIRouter, Depends, HTTPException, Query
import sqlite3

from src.database import get_db, klinik_kpi_getir, klinik_kararlari_getir, klinik_karar_getir, log_sayisi_getir_db, loglari_getir_db
from src.auth import get_current_user

router = APIRouter()

@router.get("/api/clinical-kpis")
async def get_clinical_kpis(telefon: str = Depends(get_current_user), db: sqlite3.Connection = Depends(get_db)):
    """Operasyonel kontrol ve izlenebilirlik KPI'larını döndürür."""
    # Sadece kendi telefon numarasının verilerini döndür (Multitenant safety)
    kpis = klinik_kpi_getir(telefon, conn=db)
    return {"success": True, "kpis": kpis}

@router.get("/api/clinical-decisions")
async def list_clinical_decisions(
    limit: int = 50, 
    offset: int = 0,
    telefon: str = Depends(get_current_user), 
    db: sqlite3.Connection = Depends(get_db)
):
    decisions = klinik_kararlari_getir(telefon, limit, offset, conn=db)
    return {"success": True, "decisions": decisions}

@router.get("/api/clinical-decisions/{decision_id}")
async def get_clinical_decision(
    decision_id: str, 
    telefon: str = Depends(get_current_user), 
    db: sqlite3.Connection = Depends(get_db)
):
    decision = klinik_karar_getir(decision_id, conn=db)
    if not decision:
        raise HTTPException(status_code=404, detail="Karar kaydı bulunamadı")
    # Multitenant safety check
    if decision.get("telefon") != telefon:
        raise HTTPException(status_code=403, detail="Erişim reddedildi")
    return {"success": True, "decision": decision}

@router.get("/api/history")
async def get_history(
    page: int = Query(1, ge=1),
    limit: int = Query(10, ge=1, le=50),
    telefon: str = Depends(get_current_user),
    db: sqlite3.Connection = Depends(get_db)
):
    """Kullanıcının geçmiş etkileşim loglarını (Pagination destekli) getirir."""
    offset = (page - 1) * limit
    total_logs = log_sayisi_getir_db(telefon, conn=db)
    log_kayitlari = loglari_getir_db(telefon, limit, offset, conn=db)
    
    formatted_logs = []
    for log in log_kayitlari:
        formatted_logs.append({
            "id": log["kullanici_adi"], # Aslında ID değil ama frontend bu keyi kullanmayabilir
            "tarih": log["tarih"],
            "eylem": log["sayfa"],
            "kullanici_girdisi": log["istek"],
            "asistan_ciktisi": log["cevap"],
            "ai_yanit": log["cevap"],
            "metadata": log.get("metadata")
        })
        
    return {
        "success": True,
        "total": total_logs,
        "page": page,
        "limit": limit,
        "has_more": offset + len(formatted_logs) < total_logs,
        "loglar": formatted_logs
    }
