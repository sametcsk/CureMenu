"""
CureMenu central LLM configuration.

All modules import model instances and helpers from here so model changes,
fallbacks and response parsing stay consistent across text, vision and fast chat.
"""

from collections.abc import Iterable

from dotenv import load_dotenv
from langchain_google_genai import ChatGoogleGenerativeAI

from src.config import settings
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

    for model_name in models:
        try:
            return build_llm(model_name, temperature=temperature).invoke(payload)
        except Exception as error:
            last_error = error
            if _model_not_found(error):
                logger.warning("Gemini model unavailable, trying fallback: %s", model_name)
                continue
            raise

    assert last_error is not None
    raise last_error


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
