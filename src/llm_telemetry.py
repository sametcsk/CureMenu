"""Non-critical AI usage telemetry.

Captures anonymized operational metadata for every AI/model call so per-feature
and per-user cost can be measured later. NOTHING sensitive is stored: no prompt
text, no chat content, no disease/medication/allergy/lab data, no image content
— only counts and identifiers.

Design:
- One central recorder used by the LLM wrapper (and the vision call sites).
- Per-request context (feature / conversation_id / anonymized user / graph flag)
  is carried in a contextvar set at each feature entry, so call sites don't each
  duplicate telemetry plumbing.
- Best-effort: any telemetry failure is swallowed; it must never break the
  product request. Logging is non-critical.
"""
from __future__ import annotations

import contextvars
import hashlib
import hmac
import time
import uuid
from dataclasses import asdict, dataclass, field
from typing import Any

from src.config import settings
from src.logger import get_logger

logger = get_logger(__name__)


@dataclass
class LLMContext:
    feature: str = "unknown"
    conversation_id: str = ""
    anon_user_id: str = ""
    graph_used: bool = False
    node: str = ""
    request_id: str = field(default_factory=lambda: uuid.uuid4().hex[:16])


_CTX: contextvars.ContextVar[LLMContext] = contextvars.ContextVar("llm_ctx", default=LLMContext())


def anonymize_account(account_id: str) -> str:
    """Deterministic, non-reversible per-account id for cost aggregation."""
    key = (settings.CUREMENU_ANALYTICS_HASH_KEY or settings.jwt_secret_key or "").encode("utf-8")
    return hmac.new(key, str(account_id or "").encode("utf-8"), hashlib.sha256).hexdigest()[:16]


def set_llm_context(
    *,
    feature: str = "unknown",
    conversation_id: str = "",
    account_id: str = "",
    anon_user_id: str = "",
    graph_used: bool = False,
    node: str = "",
) -> None:
    """Set the whole telemetry context at a feature entry point (overwrites)."""
    if account_id and not anon_user_id:
        anon_user_id = anonymize_account(account_id)
    _CTX.set(LLMContext(
        feature=feature or "unknown",
        conversation_id=str(conversation_id or ""),
        anon_user_id=str(anon_user_id or ""),
        graph_used=bool(graph_used),
        node=str(node or ""),
    ))


def update_llm_context(**fields: Any) -> None:
    ctx = _CTX.get()
    _CTX.set(LLMContext(**{**asdict(ctx), **fields}))


def get_llm_context() -> LLMContext:
    return _CTX.get()


def extract_usage(response: Any) -> dict[str, int]:
    """Pull token counts from a LangChain AIMessage; defensive against shape."""
    usage = getattr(response, "usage_metadata", None) or {}
    if not isinstance(usage, dict):
        usage = {}
    details = usage.get("input_token_details") or {}
    cached = 0
    if isinstance(details, dict):
        cached = int(details.get("cache_read") or details.get("cached") or 0)
    return {
        "input_tokens": int(usage.get("input_tokens") or 0),
        "output_tokens": int(usage.get("output_tokens") or 0),
        "total_tokens": int(usage.get("total_tokens") or 0),
        "cached_tokens": cached,
    }


def record_llm_usage(
    *,
    model: str,
    provider: str = "google",
    input_tokens: int = 0,
    output_tokens: int = 0,
    total_tokens: int = 0,
    cached_tokens: int = 0,
    image_count: int = 0,
    latency_ms: int = 0,
    success: bool = True,
    retry_count: int = 0,
) -> None:
    """Best-effort write of one AI call's anonymized metadata. Never raises."""
    try:
        from src.database import llm_usage_kaydet
        from src.pricing import estimate_cost

        ctx = _CTX.get()
        cost, currency = estimate_cost(
            model,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cached_tokens=cached_tokens,
            image_count=image_count,
        )
        llm_usage_kaydet({
            "request_id": ctx.request_id,
            "conversation_id": ctx.conversation_id,
            "anon_user_id": ctx.anon_user_id,
            "feature": ctx.feature,
            "provider": provider,
            "model": str(model or ""),
            "graph_used": 1 if ctx.graph_used else 0,
            "node": ctx.node,
            "input_tokens": int(input_tokens),
            "output_tokens": int(output_tokens),
            "total_tokens": int(total_tokens or (int(input_tokens) + int(output_tokens))),
            "cached_tokens": int(cached_tokens),
            "image_input": 1 if image_count else 0,
            "image_count": int(image_count),
            "call_count": 1,
            "latency_ms": int(latency_ms),
            "success": 1 if success else 0,
            "retry_count": int(retry_count),
            "estimated_cost": cost,
            "currency": currency,
        })
    except Exception as exc:  # telemetry is strictly non-critical
        logger.debug("LLM telemetry skipped: %s", exc)


class timed:
    """Context manager returning elapsed ms; used to time model calls."""

    def __enter__(self) -> "timed":
        self._start = time.perf_counter()
        self.ms = 0
        return self

    def __exit__(self, *exc: Any) -> None:
        self.ms = int((time.perf_counter() - self._start) * 1000)
