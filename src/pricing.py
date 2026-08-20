"""Central AI provider/model pricing.

Prices are intentionally NOT hard-coded across the codebase and are NOT invented
here: the built-in table ships with prices set to ``None`` (unknown). Real,
verified per-model prices are loaded from a JSON file (``CUREMENU_PRICING_PATH``
env, default ``config/pricing.json``) so operations can update them from the
provider's official page without a code change.

When a needed price is unknown, ``estimate_cost`` returns ``None`` — usage is
still recorded, only the cost is left null. Nothing is fabricated.

JSON shape (all price fields optional; per 1M tokens unless noted):
    {
      "currency": "USD",
      "models": {
        "gemini-2.5-flash": {
          "input_price": 0.30, "output_price": 2.50,
          "cached_input_price": 0.075, "image_price": null,
          "currency": "USD", "effective_date": "2026-01-01"
        }
      }
    }
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from src.logger import get_logger

logger = get_logger(__name__)

DEFAULT_CURRENCY = "USD"
_TOKENS_PER_UNIT = 1_000_000  # prices are per 1M tokens


@dataclass(frozen=True)
class ModelPrice:
    input_price: float | None = None       # per 1M input tokens
    output_price: float | None = None      # per 1M output tokens
    cached_input_price: float | None = None  # per 1M cached input tokens
    image_price: float | None = None       # per image (flat)
    currency: str = DEFAULT_CURRENCY
    effective_date: str = ""


# Built-in models known to the app. Prices left None on purpose — fill via JSON.
_BUILTIN_MODELS = (
    "gemini-2.5-flash",
    "gemini-2.5-pro",
    "gemini-2.0-flash",
    "gemini-1.5-flash",
    "gemini-1.5-pro",
)


def _pricing_path() -> Path:
    return Path(str(os.environ.get("CUREMENU_PRICING_PATH", "") or "config/pricing.json"))


def _load_table() -> tuple[dict[str, ModelPrice], str]:
    table: dict[str, ModelPrice] = {name: ModelPrice() for name in _BUILTIN_MODELS}
    currency = DEFAULT_CURRENCY
    path = _pricing_path()
    try:
        if path.is_file():
            data: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
            currency = str(data.get("currency") or DEFAULT_CURRENCY)
            for name, cfg in (data.get("models") or {}).items():
                if not isinstance(cfg, dict):
                    continue
                table[str(name)] = ModelPrice(
                    input_price=_num(cfg.get("input_price")),
                    output_price=_num(cfg.get("output_price")),
                    cached_input_price=_num(cfg.get("cached_input_price")),
                    image_price=_num(cfg.get("image_price")),
                    currency=str(cfg.get("currency") or currency),
                    effective_date=str(cfg.get("effective_date") or ""),
                )
    except (OSError, ValueError, TypeError) as exc:
        logger.warning("Pricing config unreadable (%s); using unknown prices.", exc)
    return table, currency


def _num(value: Any) -> float | None:
    try:
        return float(value) if value is not None else None
    except (TypeError, ValueError):
        return None


# Loaded once at import; small and static for the process lifetime.
_TABLE, _CURRENCY = _load_table()


def price_for(model: str) -> ModelPrice:
    return _TABLE.get(str(model or ""), ModelPrice(currency=_CURRENCY))


def estimate_cost(
    model: str,
    *,
    input_tokens: int = 0,
    output_tokens: int = 0,
    cached_tokens: int = 0,
    image_count: int = 0,
) -> tuple[float | None, str]:
    """Return (estimated_cost, currency). Cost is None when any required price is
    unknown — never a fabricated number."""
    price = price_for(model)
    billable_input = max(int(input_tokens) - int(cached_tokens), 0)
    components: list[float] = []
    if billable_input:
        if price.input_price is None:
            return None, price.currency
        components.append(billable_input * price.input_price / _TOKENS_PER_UNIT)
    if cached_tokens:
        rate = price.cached_input_price if price.cached_input_price is not None else price.input_price
        if rate is None:
            return None, price.currency
        components.append(int(cached_tokens) * rate / _TOKENS_PER_UNIT)
    if output_tokens:
        if price.output_price is None:
            return None, price.currency
        components.append(int(output_tokens) * price.output_price / _TOKENS_PER_UNIT)
    if image_count:
        if price.image_price is None:
            return None, price.currency
        components.append(int(image_count) * price.image_price)
    if not components:
        return 0.0, price.currency
    return round(sum(components), 8), price.currency


def pricing_is_configured() -> bool:
    return any(mp.input_price is not None or mp.output_price is not None for mp in _TABLE.values())
