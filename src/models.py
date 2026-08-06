# Veri Modelleri
from pydantic import BaseModel, Field   
from enum import Enum   
from typing import Annotated, Literal, Optional, List, Dict
import uuid


class Cinsiyet(str, Enum):
    ERKEK = "erkek"
    KADIN = "kadın"

class BeslenmeHedefi(str, Enum):
    GENEL = "Sağlıklı Yaşam"
    KILO_KONTROLU = "Kilo Kontrolü"
    YAG_YAKIMI = "Yağ Yakımı"
    KAS_KAZANIMI = "Kas Kazanımı"
    KALP_SAGLIGI = "Kalp Sağlığı"
    SINDIRIM = "Sindirim ve Bağırsak Sağlığı"
    ENERJI_PERFORMANS = "Enerji ve Performans"


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


class AccountDeletionRequest(BaseModel):
    sifre: str = Field(..., min_length=6, max_length=256)
    confirmation: Literal["DELETE"]

class ProfilKaydetRequest(BaseModel):
    kullanici_adi: str = Field(..., min_length=2, max_length=40, pattern=r"^[A-Za-zÇçĞğİıÖöŞşÜü\s]+$")
    ad: str = Field(..., min_length=2, max_length=40, pattern=r"^[A-Za-zÇçĞğİıÖöŞşÜü\s]+$")
    yas: int = Field(..., ge=1, le=100)
    cinsiyet: Cinsiyet
    boy: int = Field(default=170, ge=1, le=250)
    kilo: float = Field(default=70, ge=1, le=200)
    hastaliklar: list[str] = Field(default_factory=list)
    alerjiler: list[str] = Field(default_factory=list)
    genetik_hastaliklar: list[str] = Field(default_factory=list)
    tibbi_gecmis: Optional[str] = None
    ilaclar: list[str] = Field(default_factory=list)
    hedef: str = BeslenmeHedefi.GENEL.value

class AileUyesiEkleRequest(BaseModel):
    ad: str = Field(..., min_length=2, max_length=40, pattern=r"^[A-Za-zÇçĞğİıÖöŞşÜü\s]+$")
    yas: int = Field(..., ge=1, le=100)
    cinsiyet: Cinsiyet
    boy: int = Field(default=170, ge=1, le=250)
    kilo: float = Field(default=70, ge=1, le=200)
    hastaliklar: list[str] = Field(default_factory=list)
    alerjiler: list[str] = Field(default_factory=list)
    genetik_hastaliklar: list[str] = Field(default_factory=list)
    tibbi_gecmis: Optional[str] = None
    ilaclar: list[str] = Field(default_factory=list)
    hedef: str = BeslenmeHedefi.GENEL.value

class ChatRequest(BaseModel):
    mesaj: str
    kimin_icin: str = "kendim"
    history_context: Optional[str] = None

class HaftalikPlanRequest(BaseModel):
    kimin_icin: str = "kendim"
    is_regeneration: bool = False
    plan_style: str = Field(default="balanced", max_length=40)
    plan_preferences: list[str] = Field(default_factory=list, max_length=6)

class GeriBildirimRequest(BaseModel):
    yemek_adi: str = Field(..., min_length=1, max_length=500)
    kimin_icin: str = Field(default="kendim", min_length=1, max_length=40)

class ComplianceRequest(BaseModel):
    meal: str = Field(..., min_length=1, max_length=500)
    status: Literal["consumed"]

class ScanMenuRequest(BaseModel):
    kimin_icin: str = Field(default="kendim", min_length=1, max_length=40)
    url: str = Field(..., min_length=4, max_length=2048)
    restoran_adi: Optional[str] = Field(default=None, max_length=120)

class ScanMenuImageRequest(BaseModel):
    kimin_icin: str = Field(default="kendim", min_length=1, max_length=40)
    image_base64: str = Field(..., min_length=1, max_length=8_000_100)
    restoran_adi: Optional[str] = Field(default=None, max_length=120)

class ShoppingListRequest(BaseModel):
    plan_metni: str
    location_info: Optional[str] = None

class FridgeScanRequest(BaseModel):
    kimin_icin: str = Field(default="kendim", min_length=1, max_length=40)
    image_base64: str = Field(..., min_length=1, max_length=8_000_100)
    image_preview_base64: str | None = Field(default=None, max_length=500_000)

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
    action_type: Literal["recipe", "alternative", "snack"] = Field(..., description="'recipe', 'alternative' veya 'snack'")
    meal_text: str = Field(..., min_length=1, max_length=500, description="Aksiyon alınacak öğünün adı")
    plan_text: Optional[str] = Field(None, max_length=50_000, description="Mevcut haftalık plan metni (alternatif için)")
    kimin_icin: str = Field(default="kendim", min_length=1, max_length=40)


IngredientText = Annotated[str, Field(min_length=1, max_length=200)]


class StructuredMealRecommendation(BaseModel):
    name: str = Field(..., min_length=2, max_length=160)
    ingredients: list[IngredientText] = Field(..., min_length=1, max_length=30)
    preparation: str = Field(default="", max_length=2000)
    portion: str = Field(default="", max_length=500)
    why_it_fits: str = Field(default="", max_length=1000)


class RecipeRecommendation(StructuredMealRecommendation):
    preparation: str = Field(..., min_length=2, max_length=2000)


class MealReplacement(BaseModel):
    eski: str = Field(..., min_length=1, max_length=500)
    yeni: str = Field(..., min_length=2, max_length=500)
    ingredients: list[IngredientText] = Field(..., min_length=1, max_length=30)


class AlternativeMealsPayload(BaseModel):
    degisen_ogunler: list[MealReplacement] = Field(..., min_length=1, max_length=8)


class SnackSuggestion(BaseModel):
    name: str = Field(..., min_length=2, max_length=120)
    ingredients: list[str] = Field(..., min_length=1, max_length=20)
    preparation: str = Field(..., min_length=2, max_length=1000)
    why_it_fits: str = Field(..., min_length=2, max_length=1000)


class SnackSuggestionsPayload(BaseModel):
    snacks: list[SnackSuggestion] = Field(..., min_length=1, max_length=3)

class WeeklyPlanDay(BaseModel):
    day: str
    breakfast: str
    lunch: str
    dinner: str
    snacks: list[str] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)
    meal_details: dict[str, StructuredMealRecommendation] = Field(default_factory=dict)
    snack_details: list[StructuredMealRecommendation] = Field(default_factory=list)

class WeeklyPlan(BaseModel):
    days: list[WeeklyPlanDay]
    summary: str
    warnings: list[str] = Field(default_factory=list)
    confidence: dict = Field(default_factory=dict)
