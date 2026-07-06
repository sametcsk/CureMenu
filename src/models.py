# Veri Modelleri
from pydantic import BaseModel, Field   
from enum import Enum   
from typing import Optional, List, Dict    
import uuid


class Cinsiyet(str, Enum):
    ERKEK = "erkek"
    KADIN = "kadın"

class BeslenmeHedefi(str, Enum):
    GENEL = "Sağlıklı Yaşam (Genel)"
    KILO_VERME = "Kilo Verme / Yağ Yakımı"
    SPORCU = "Kas Kazanımı / Sporcu Beslenmesi"
    KADIN_SAGLIGI = "Kadın Sağlığı (PCOS / Hormon Dengesi)"
    HAMILELIK = "Hamilelik / Emzirme Beslenmesi"
    SINDIRIM = "Sindirim / Bağırsak Sağlığı"
    ZIHIN = "Zihin Açıklığı / Odaklanma"
    DETOKS = "Detoks / Ödem Atma"
    COCUK_GELISIMI = "Çocuk Gelişimi"


class UygunlukDurumu(str, Enum):
    UYGUN = "uygun"
    DIKKATLI = "dikkatli"
    ONERILMEZ = "onerilmez"



class AileUyesi(BaseModel): 
    id: str = Field(default_factory=lambda: str(uuid.uuid4())[:8])
    ad: str
    yas: int = Field(ge=1, le=100)
    cinsiyet: Cinsiyet
    boy: int = Field(default=170, description="cm", ge=1, le=250)
    kilo: float = Field(default=70, description="kg", ge=1, le=200)
    genetik_hastaliklar: list[str] = Field(default_factory=list)
    tibbi_gecmis: Optional[str] = None
    hastaliklar: list[str] = Field(default_factory=list)
    alerjiler: list[str] = Field(default_factory=list)
    ilaclar: list[str] = Field(default_factory=list)
    hedef: str = Field(default=BeslenmeHedefi.GENEL.value, description="Beslenme amacı (Kilo verme, Kas vb.)")
    notlar: Optional[str] = None

class KullaniciProfili(BaseModel):
    ana_kullanici: Optional[AileUyesi] = None
    aile_uyeleri: list[AileUyesi] = Field(default_factory=list)

    def tum_uyeler(self) -> list[AileUyesi]:
        uyeler = []
        if self.ana_kullanici:
            uyeler.append(self.ana_kullanici)
        uyeler.extend(self.aile_uyeleri)
        return uyeler

class YemekUygunluk(BaseModel):
    yemek_id: str
    yemek_adi: str
    uygunluk: UygunlukDurumu
    aciklama: str
    uyari_detaylari: list[str] = Field(default_factory=list)
    skor: int = 0

# ── API İSTEK MODELLERİ ──

class LoginRequest(BaseModel):
    telefon: str = Field(..., pattern=r"^(05\d{9}|5\d{9}|\+905\d{9})$", description="Türkiye standartlarında geçerli bir telefon numarası giriniz.")
    sifre: str = Field(..., min_length=6, description="Kullanıcı şifresi")

class RegisterRequest(BaseModel):
    telefon: str = Field(..., pattern=r"^(05\d{9}|5\d{9}|\+905\d{9})$", description="Türkiye standartlarında geçerli bir telefon numarası giriniz.")
    kullanici_adi: str = Field(..., min_length=2, max_length=40, pattern=r"^[A-Za-zÇçĞğİıÖöŞşÜü\s]+$", description="Kullanıcı adı sadece harflerden oluşmalı ve çok uzun olmamalıdır.")
    sifre: str = Field(..., min_length=6, description="Kullanıcı şifresi")

class ProfilKaydetRequest(BaseModel):
    kullanici_adi: str = Field(..., min_length=2, max_length=40, pattern=r"^[A-Za-zÇçĞğİıÖöŞşÜü\s]+$")
    ad: str = Field(..., min_length=2, max_length=40, pattern=r"^[A-Za-zÇçĞğİıÖöŞşÜü\s]+$")
    yas: int
    cinsiyet: str
    boy: int = 170
    kilo: float = 70
    hastaliklar: list[str] = Field(default_factory=list)
    alerjiler: list[str] = Field(default_factory=list)
    genetik_hastaliklar: list[str] = Field(default_factory=list)
    tibbi_gecmis: Optional[str] = None
    ilaclar: list[str] = Field(default_factory=list)
    hedef: str = "Sağlıklı Yaşam (Genel)"

class AileUyesiEkleRequest(BaseModel):
    ad: str = Field(..., min_length=2, max_length=40, pattern=r"^[A-Za-zÇçĞğİıÖöŞşÜü\s]+$")
    yas: int
    cinsiyet: str
    boy: int = 170
    kilo: float = 70
    hastaliklar: list[str] = Field(default_factory=list)
    alerjiler: list[str] = Field(default_factory=list)
    genetik_hastaliklar: list[str] = Field(default_factory=list)
    tibbi_gecmis: Optional[str] = None
    ilaclar: list[str] = Field(default_factory=list)
    hedef: str = "Sağlıklı Yaşam (Genel)"

class ChatRequest(BaseModel):
    mesaj: str
    kimin_icin: str = "kendim"
    history_context: Optional[str] = None

class HaftalikPlanRequest(BaseModel):
    kimin_icin: str = "kendim"

class GeriBildirimRequest(BaseModel):
    yemek_adi: str
    kimin_icin: str = "kendim"

class ScanMenuRequest(BaseModel):
    kimin_icin: str = "kendim"
    url: str

class ScanMenuImageRequest(BaseModel):
    kimin_icin: str = "kendim"
    image_base64: str

class ShoppingListRequest(BaseModel):
    plan_metni: str
    location_info: Optional[str] = None

class FridgeScanRequest(BaseModel):
    kimin_icin: str = "kendim"
    image_base64: str

# ── QUALITY ASSURANCE (QA) MODELLERİ ──
class StructuredCitation(BaseModel):
    source_id: str
    chunk_id: str
    title: str
    evidence_span: str
    page: Optional[int] = None

class AgentConfidence(BaseModel):
    model_confidence: float = Field(..., ge=0.0, le=1.0, description="LLM'in öznel güveni (0-1)")
    justification: str = Field(..., description="LLM'in bu güven skoruna dair gerekçesi")

class ExplainabilityLog(BaseModel):
    applied_rules: list[str] = Field(default_factory=list)
    applied_policies: list[str] = Field(default_factory=list)
    found_risks: list[str] = Field(default_factory=list)
    medical_guideline: str = "TBD"

class DenetleyiciKarari(BaseModel):
    guvenli_mi: bool
    uyari_mesaji: Optional[str] = None
    clinical_risk_level: str = Field(..., description="Low Risk, Medium Risk, High Risk, Emergency Referral")
    agent_confidence: AgentConfidence
    citations: list[StructuredCitation] = Field(default_factory=list)
    explainability: Optional[ExplainabilityLog] = None

class PlanActionRequest(BaseModel):
    action_type: str = Field(..., description="'recipe' veya 'alternative'")
    meal_text: str = Field(..., description="Aksiyon alınacak öğünün adı")
    plan_text: Optional[str] = Field(None, description="Mevcut haftalık plan metni (alternatif için)")