from urllib.parse import quote_plus

from src.grocery.extraction import CATEGORIES
from src.grocery.health import assess_item_health
from src.grocery.price_provider import PriceProvider


DISCLAIMER = "Stok ve fiyat bilgisi doğrulanmadı; markete göre değişebilir."
DEFAULT_MARKETS = ("Migros", "CarrefourSA", "A101", "BİM", "Şok")


def build_market_search_links(location_context: str | None = None) -> list[dict[str, str]]:
    suffix = f" {location_context.strip()}" if location_context and location_context.strip() else ""
    return [
        {
            "market": market,
            "label": f"{market} haritada aç",
            "url": f"https://www.google.com/maps/search/{quote_plus(market + suffix)}",
            "verified": False,
        }
        for market in DEFAULT_MARKETS
    ]


def build_basket_summary(
    raw_items: list[dict[str, str]],
    *,
    price_provider: PriceProvider,
    allergies: list[str],
    diseases: list[str],
    medications: list[str] | None = None,
    location_context: str | None = None,
) -> dict:
    items = []
    excluded_items = []
    risk_items = []
    categories = {category: [] for category in CATEGORIES}
    status_counts = {"safe": 0, "caution": 0, "avoid": 0, "unknown": 0}
    estimated_min_total = 0.0
    estimated_max_total = 0.0

    for raw in raw_items:
        name = raw["name"]
        category = raw.get("category") if raw.get("category") in CATEGORIES else "temel_gida"
        health = assess_item_health(
            name,
            allergies=allergies,
            diseases=diseases,
            medications=medications or [],
        )
        status_counts[health.status] += 1

        if health.status != "safe":
            risk_items.append({"name": name, "status": health.status, "reason": health.reason})

        if health.status == "avoid":
            excluded_items.append(
                {
                    "name": name,
                    "category": category,
                    "estimated_quantity": raw.get("quantity") or "Belirtilmedi",
                    "estimated_min_price": None,
                    "estimated_max_price": None,
                    "channel_name": None,
                    "product_link": None,
                    "health_status": health.status,
                    "reason": health.reason,
                }
            )
            continue

        price = price_provider.estimate(name, category)
        item = {
            "name": name,
            "category": category,
            "estimated_quantity": raw.get("quantity") or price.quantity,
            "estimated_min_price": round(price.min_price, 2),
            "estimated_max_price": round(price.max_price, 2),
            "channel_name": price.channel_name,
            "product_link": price.product_link,
            "health_status": health.status,
            "reason": health.reason,
        }
        items.append(item)
        categories[category].append(item)
        estimated_min_total += price.min_price
        estimated_max_total += price.max_price

    recommendation_summary = _recommendation_summary(status_counts, items, excluded_items)
    return {
        "items": items,
        "excluded_items": excluded_items,
        "risk_items": risk_items,
        "categories": categories,
        "estimated_min_total": round(estimated_min_total, 2),
        "estimated_max_total": round(estimated_max_total, 2),
        "health_safe_total_items": status_counts["safe"],
        "caution_items": status_counts["caution"],
        "avoid_items": status_counts["avoid"],
        "unknown_items": status_counts["unknown"],
        "recommendation_summary": recommendation_summary,
        "market_search_links": build_market_search_links(location_context),
        "disclaimer": DISCLAIMER,
        "price_catalog_version": getattr(price_provider, "version", "estimated_price_bands:unknown"),
    }


def _recommendation_summary(status_counts: dict[str, int], items: list[dict], excluded_items: list[dict]) -> str:
    if not items and not excluded_items:
        return "Sepet oluşturmak için haftalık plan veya alışveriş kalemi gerekiyor."
    if status_counts["avoid"]:
        return "Bazı ürünler sağlık profiliyle çakıştığı için ekonomik sepete dahil edilmedi; uygun alternatif seçilmeli."
    if status_counts["caution"]:
        return "Sepet genel olarak uygulanabilir görünüyor; dikkat işaretli ürünlerde porsiyon veya alternatif seçimi yap."
    if status_counts["unknown"]:
        return "Bazı ürünler için sağlık uygunluğu belirsiz; profil bilgilerini tamamlamak daha güvenli olur."
    return "Sepet mevcut profil kayıtlarıyla uyumlu görünüyor; fiyatlar tahmini aralıktır."
