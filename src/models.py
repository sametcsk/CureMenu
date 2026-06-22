# Veri Modelleri - buraya birlikte yazacağız
from pydantic import BaseModel, Field   
from enum import Enum   
from typing import Optional, List, Dict    
import uuid

class Hastalik(str, Enum):
    DIYABET = "diyabet"
    COLYAK = "colyak"
    HIPERTANSIYON = "hipertansiyon"
    KOLESTEROL = "kolesterol"


class Cinsiyet(str, Enum):
    ERKEK = "erkek"
    KADIN = "kadın"


class UygunlukDurumu(str, Enum):
    UYGUN = "uygun"
    DIKKATLI = "dikkatli"
    ONERILMEZ = "onerilmez"



class AileUyesi(BaseModel): 
    id: str = Field(default_factory=lambda: str(uuid.uuid4())[:8])
    ad:str
    yas: int = Field(ge=1, le=120)
    cinsiyet: Cinsiyet
    hastaliklar:list[Hastalik]=[]
    alerjiler:list[str]=[]
    notlar:Optional[str]=None

class KullaniciProfili(BaseModel):
    ana_kullanici:Optional[AileUyesi]=None
    aile_uyeleri:list[AileUyesi]=[]

    def tum_uyeler(self)-> list[AileUyesi]:
        uyeler= []
        if self.ana_kullanici:
            uyeler.append(self.ana_kullanici)
        uyeler.extend(self.aile_uyeleri)
        return uyeler

class YemekUygunluk(BaseModel):
    yemek_id:str
    yemek_adi:str
    uygunluk:UygunlukDurumu
    aciklama:str
    uyari_detaylari:list[str]=[]
    skor:int=0
    
        

    
    