"""
CureMenu central LLM configuration.

All modules import model instances and helpers from here so model changes,
fallbacks and response parsing stay consistent across text, vision and fast chat.
"""

import time
from collections.abc import Iterable
from typing import Any

from dotenv import load_dotenv
from langchain_google_genai import ChatGoogleGenerativeAI

from src.config import settings
from src.llm_telemetry import extract_usage, record_llm_usage
from src.logger import get_logger

load_dotenv()

logger = get_logger(__name__)


def build_llm(model_name: str, temperature: float = 0.7) -> ChatGoogleGenerativeAI:
    """Create a Gemini chat model for one role."""
    return ChatGoogleGenerativeAI(
        model=model_name,
        temperature=temperature,
        google_api_key=settings.GOOGLE_API_KEY,
    )


llm = build_llm(settings.text_model_name)
vision_llm = build_llm(settings.GEMINI_VISION_MODEL, temperature=0.2)
fast_llm = build_llm(settings.GEMINI_FAST_MODEL, temperature=0.4)
eval_llm = build_llm(settings.GEMINI_EVAL_MODEL, temperature=0.0)


def _model_not_found(error: Exception) -> bool:
    text = str(error).lower()
    return (
        "not_found" in text
        or "404" in text
        or ("model" in text and "not found" in text)
        or ("not supported" in text and "generatecontent" in text)
    )


def _dedupe(values: Iterable[str]) -> list[str]:
    result: list[str] = []
    for value in values:
        if value and value not in result:
            result.append(value)
    return result


def invoke_with_model_fallback(
    payload,
    *,
    preferred_model: str | None = None,
    fallback_models: Iterable[str] | None = None,
    temperature: float = 0.7,
):
    """
    Invoke Gemini and transparently retry with configured fallbacks when a model
    has been deprecated or disabled by the provider.
    """
    models = _dedupe(
        [
            preferred_model or settings.text_model_name,
            *(fallback_models or settings.model_fallback_list),
        ]
    )
    last_error: Exception | None = None
    image_count = _count_images(payload)
    retry = 0

    for model_name in models:
        started = time.perf_counter()
        try:
            response = build_llm(model_name, temperature=temperature).invoke(payload)
            record_llm_usage(
                model=model_name,
                latency_ms=int((time.perf_counter() - started) * 1000),
                success=True,
                retry_count=retry,
                image_count=image_count,
                **extract_usage(response),
            )
            return response
        except Exception as error:
            last_error = error
            if _model_not_found(error):
                retry += 1
                logger.warning("Gemini model unavailable, trying fallback: %s", model_name)
                continue
            record_llm_usage(
                model=model_name,
                latency_ms=int((time.perf_counter() - started) * 1000),
                success=False,
                retry_count=retry,
                image_count=image_count,
            )
            raise

    record_llm_usage(model=models[-1] if models else "", success=False, retry_count=retry, image_count=image_count)
    assert last_error is not None
    raise last_error


def _count_images(payload: Any) -> int:
    """Count image_url parts in a chat payload (0 for plain-text prompts)."""
    def _scan(content: Any) -> int:
        if isinstance(content, list):
            return sum(
                1 for part in content
                if isinstance(part, dict) and part.get("type") == "image_url"
            )
        return 0

    try:
        messages = payload.to_messages() if hasattr(payload, "to_messages") else payload
        if isinstance(messages, (list, tuple)):
            total = 0
            for message in messages:
                content = message.get("content") if isinstance(message, dict) else getattr(message, "content", None)
                total += _scan(content)
            return total
    except Exception:
        return 0
    return 0


def parse_llm_response(response) -> str:
    """
    Gemini sometimes returns a list instead of a string.
    Always return a clean string.
    """
    content = response.content
    if isinstance(content, list):
        content = " ".join(
            str(item.get("text", item)) if isinstance(item, dict) else str(item)
            for item in content
        )
    return str(content).strip()
