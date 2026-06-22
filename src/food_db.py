# Yemek Veritabanı 

import json
from pathlib import Path

PROJE_DIZIN = Path(__file__).parent.parent
FOODS_DOSYA = PROJE_DIZIN / "data" / "foods.json"


def yemekleri_yukle():
    with open (FOODS_DOSYA, "r", encoding="utf-8") as f:
        return json.load(f)

def yemek_bul(yemek_id):
    yemekler=yemekleri_yukle()
    for yemek in yemekler:
        if yemek["id"]==yemek_id:
            return yemek
    return None

def kategoriye_gore_filtrele(kategori):
    yemekler=yemekleri_yukle()
    return [yemek for yemek in yemekler if yemek["kategori"]==kategori]

def tum_kategoriler():
    """Veritabanındaki tüm kategorileri döndürür"""
    yemekler=yemekleri_yukle()
    return sorted(list(set(yemek["kategori"]for yemek in yemekler)))



KATEGORI_ISIMLERI = {
    "corba": "Çorbalar",
    "et_yemekleri": "Et Yemekleri",
    "sebze_yemekleri": "Sebze Yemekleri",
    "baklagil": "Baklagiller",
    "pilav_makarna": "Pilav & Makarna",
    "salata": "Salatalar",
    "borek_hamur": "Börek & Hamur İşi",
    "tatli": "Tatlılar",
    "kahvalti": "Kahvaltılıklar",
    "meze": "Mezeler",
}

def kategori_goster(kategori_id):
    return KATEGORI_ISIMLERI.get(kategori_id, kategori_id)

    