import json
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Protocol


CATALOG_PATH = Path(__file__).resolve().parents[2] / "data" / "estimated_price_bands.json"


@dataclass(frozen=True)
class PriceEstimate:
    min_price: float
    max_price: float
    quantity: str
    channel_name: str | None = None
    product_link: str | None = None


class PriceProvider(Protocol):
    version: str

    def estimate(self, item_name: str, category: str) -> PriceEstimate:
        """Return an estimated price range; implementations must not claim live prices."""


@lru_cache(maxsize=1)
def _load_price_bands() -> dict:
    with CATALOG_PATH.open("r", encoding="utf-8") as fh:
        return json.load(fh)


class EstimatedCatalogPriceProvider:
    def __init__(self) -> None:
        catalog = _load_price_bands()
        self.version = str(catalog.get("version", "estimated_price_bands:unknown"))
        self._channel_name = str(catalog.get("channel_name", "Kategori tahmini"))
        self._default = catalog.get("default", {})
        self._categories = catalog.get("categories", {})

    def estimate(self, item_name: str, category: str) -> PriceEstimate:
        band = self._categories.get(category) or self._default
        return PriceEstimate(
            min_price=float(band.get("min_price", 25.0)),
            max_price=float(band.get("max_price", 60.0)),
            quantity=str(band.get("quantity", "1 paket/adet")),
            channel_name=self._channel_name,
            product_link=None,
        )
