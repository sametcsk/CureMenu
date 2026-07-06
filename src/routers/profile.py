from fastapi import APIRouter, Depends, HTTPException
import sqlite3

from src.models import KullaniciProfili, ProfilKaydetRequest, AileUyesiEkleRequest, AileUyesi, Cinsiyet
from src.database import get_db, profil_getir_db, profil_kaydet_db
from src.auth import get_current_user
from src.messages import PROFIL_BULUNAMADI, ONCE_PROFIL_OLUSTUR

router = APIRouter()

@router.get("/api/profile/me")
async def get_profile(telefon: str = Depends(get_current_user), db: sqlite3.Connection = Depends(get_db)):
    """Profil bilgisini JWT içindeki kullanıcıya göre getir."""
    profil = profil_getir_db(telefon, conn=db)
    if profil is None:
        raise HTTPException(status_code=404, detail=PROFIL_BULUNAMADI)
    
    data = profil.model_dump()
    return {"success": True, "profil": data}

@router.post("/api/profile/save")
async def save_profile(req: ProfilKaydetRequest, telefon: str = Depends(get_current_user), db: sqlite3.Connection = Depends(get_db)):
    """Ana kullanıcı profilini kaydet."""
    profil = profil_getir_db(telefon, conn=db)
    if profil is None:
        profil = KullaniciProfili()
    
    cinsiyet = Cinsiyet.ERKEK if req.cinsiyet.lower() in ["erkek", "male"] else Cinsiyet.KADIN
    
    ana_kullanici = AileUyesi(
        ad=req.ad,
        yas=req.yas,
        cinsiyet=cinsiyet,
        boy=req.boy,
        kilo=req.kilo,
        hastaliklar=req.hastaliklar,
        alerjiler=req.alerjiler,
        genetik_hastaliklar=req.genetik_hastaliklar,
        tibbi_gecmis=req.tibbi_gecmis,
        ilaclar=req.ilaclar,
        hedef=req.hedef,
    )
    profil.ana_kullanici = ana_kullanici
    profil_kaydet_db(telefon, req.kullanici_adi, profil, conn=db)
    
    return {"success": True, "message": "Profil kaydedildi"}

@router.post("/api/family/add")
async def add_family_member(req: AileUyesiEkleRequest, telefon: str = Depends(get_current_user), db: sqlite3.Connection = Depends(get_db)):
    """Aile üyesi ekle."""
    profil = profil_getir_db(telefon, conn=db)
    if profil is None:
        raise HTTPException(status_code=404, detail=ONCE_PROFIL_OLUSTUR)
    
    cinsiyet = Cinsiyet.ERKEK if req.cinsiyet.lower() in ["erkek", "male"] else Cinsiyet.KADIN
    
    uye = AileUyesi(
        ad=req.ad,
        yas=req.yas,
        cinsiyet=cinsiyet,
        boy=req.boy,
        kilo=req.kilo,
        hastaliklar=req.hastaliklar,
        alerjiler=req.alerjiler,
        genetik_hastaliklar=req.genetik_hastaliklar,
        tibbi_gecmis=req.tibbi_gecmis,
        ilaclar=req.ilaclar,
        hedef=req.hedef,
    )
    profil.aile_uyeleri.append(uye)
    profil_kaydet_db(telefon, "", profil, conn=db)
    
    return {"success": True, "message": f"{req.ad} aileye eklendi", "uye_id": uye.id}

@router.delete("/api/family/{uye_id}")
async def delete_family_member(uye_id: str, telefon: str = Depends(get_current_user), db: sqlite3.Connection = Depends(get_db)):
    """Aile üyesini sil."""
    profil = profil_getir_db(telefon, conn=db)
    if profil is None:
        raise HTTPException(status_code=404, detail=PROFIL_BULUNAMADI)
    
    profil.aile_uyeleri = [u for u in profil.aile_uyeleri if u.id != uye_id]
    profil_kaydet_db(telefon, "", profil, conn=db)
    
    return {"success": True, "message": "Üye silindi"}
