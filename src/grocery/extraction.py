import re


CATEGORIES = (
    "protein",
    "sebze_meyve",
    "sut_urunleri",
    "bakliyat",
    "tahil",
    "yag",
    "temel_gida",
)

TR_MAP = str.maketrans(
    {
        "ç": "c",
        "ğ": "g",
        "ı": "i",
        "ö": "o",
        "ş": "s",
        "ü": "u",
        "Ç": "c",
        "Ğ": "g",
        "İ": "i",
        "I": "i",
        "Ö": "o",
        "Ş": "s",
        "Ü": "u",
    }
)


KEYWORD_CATALOG: dict[str, tuple[str, str]] = {
    "tavuk": ("Tavuk göğsü", "protein"),
    "hindi": ("Hindi göğsü", "protein"),
    "balik": ("Balık", "protein"),
    "somon": ("Somon", "protein"),
    "ton baligi": ("Ton balığı", "protein"),
    "yumurta": ("Yumurta", "protein"),
    "kirmizi et": ("Kırmızı et", "protein"),
    "yogurt": ("Yoğurt", "sut_urunleri"),
    "sut": ("Süt", "sut_urunleri"),
    "peynir": ("Peynir", "sut_urunleri"),
    "kefir": ("Kefir", "sut_urunleri"),
    "mercimek": ("Mercimek", "bakliyat"),
    "nohut": ("Nohut", "bakliyat"),
    "fasulye": ("Kuru fasulye", "bakliyat"),
    "bulgur": ("Bulgur", "tahil"),
    "pirinc": ("Pirinç", "tahil"),
    "makarna": ("Makarna", "tahil"),
    "yulaf": ("Yulaf", "tahil"),
    "karabugday": ("Karabuğday", "tahil"),
    "ekmek": ("Ekmek", "tahil"),
    "zeytinyagi": ("Zeytinyağı", "yag"),
    "tereyagi": ("Tereyağı", "yag"),
    "domates": ("Domates", "sebze_meyve"),
    "salata": ("Mevsim salata malzemeleri", "sebze_meyve"),
    "salatalik": ("Salatalık", "sebze_meyve"),
    "brokoli": ("Brokoli", "sebze_meyve"),
    "ispanak": ("Ispanak", "sebze_meyve"),
    "kabak": ("Kabak", "sebze_meyve"),
    "elma": ("Elma", "sebze_meyve"),
    "muz": ("Muz", "sebze_meyve"),
    "cilek": ("Çilek", "sebze_meyve"),
    "ceviz": ("Ceviz", "temel_gida"),
    "badem": ("Badem", "temel_gida"),
    "seker": ("Şeker", "temel_gida"),
    "tuz": ("Tuz", "temel_gida"),
}


def fold_text(value: str) -> str:
    return (value or "").lower().translate(TR_MAP)


def normalize_item_name(value: str) -> str:
    cleaned = re.sub(r"\([^)]*\)", " ", value or "")
    cleaned = re.sub(r"[^0-9A-Za-zÇĞİÖŞÜçğıöşü\s/-]", " ", cleaned)
    return re.sub(r"\s+", " ", cleaned).strip()


def extract_items_from_plan(weekly_plan: str | None) -> list[dict[str, str]]:
    text = fold_text(weekly_plan or "")
    found: dict[str, dict[str, str]] = {}
    for keyword, (name, category) in KEYWORD_CATALOG.items():
        if keyword in text:
            key = fold_text(name)
            found[key] = {
                "name": name,
                "category": category,
                "quantity": "Haftalık plana göre tahmini",
            }
    return list(found.values())


def normalize_input_items(shopping_items: list[dict] | None) -> list[dict[str, str]]:
    normalized = []
    for raw in shopping_items or []:
        if isinstance(raw, str):
            name = normalize_item_name(raw)
            category = infer_category(name)
            quantity = "Belirtilmedi"
        else:
            name = normalize_item_name(str(raw.get("name") or raw.get("ad") or ""))
            category = raw.get("category") or raw.get("kategori") or infer_category(name)
            quantity = str(raw.get("quantity") or raw.get("miktar") or "Belirtilmedi")
        if name:
            normalized.append({"name": name, "category": category, "quantity": quantity})
    return normalized


def infer_category(item_name: str) -> str:
    normalized = fold_text(item_name)
    for keyword, (_, category) in KEYWORD_CATALOG.items():
        if keyword in normalized:
            return category
    return "temel_gida"
