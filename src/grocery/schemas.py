from typing import Literal

from pydantic import BaseModel, Field

from src.grocery.extraction import CATEGORIES


Category = Literal[
    "protein",
    "sebze_meyve",
    "sut_urunleri",
    "bakliyat",
    "tahil",
    "yag",
    "temel_gida",
]
HealthStatus = Literal["safe", "caution", "avoid", "unknown"]


class ShoppingItemInput(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    category: Category | None = None
    quantity: str | None = Field(default=None, max_length=100)


class SmartGroceryRequest(BaseModel):
    weekly_plan: str | None = Field(default=None, max_length=30000)
    shopping_items: list[ShoppingItemInput] | None = None
    location_context: str | None = Field(default=None, max_length=120)
    kimin_icin: str = Field(default="kendim", min_length=1, max_length=40)


class GroceryItem(BaseModel):
    name: str
    category: Category
    estimated_quantity: str | None = None
    estimated_min_price: float | None = None
    estimated_max_price: float | None = None
    channel_name: str | None = None
    product_link: str | None = None
    health_status: HealthStatus
    reason: str


class MarketSearchLink(BaseModel):
    market: str
    label: str
    url: str
    verified: bool = False


class GroceryRiskItem(BaseModel):
    name: str
    status: HealthStatus
    reason: str


class SmartGroceryResponse(BaseModel):
    success: bool
    decision_id: str
    items: list[GroceryItem]
    excluded_items: list[GroceryItem]
    risk_items: list[GroceryRiskItem]
    categories: dict[Category, list[GroceryItem]]
    estimated_min_total: float
    estimated_max_total: float
    health_safe_total_items: int
    caution_items: int
    avoid_items: int
    unknown_items: int
    recommendation_summary: str
    market_search_links: list[MarketSearchLink]
    disclaimer: str
    price_catalog_version: str


VALID_CATEGORIES = set(CATEGORIES)
