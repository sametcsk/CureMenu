"""CureMenu — merkezi log yapılandırması."""

import logging
import os

_configured = False


def setup_logging() -> None:
    global _configured
    if _configured:
        return

    level_name = os.getenv("LOG_LEVEL", "INFO").upper()
    level = getattr(logging, level_name, logging.INFO)
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    _configured = True


def get_logger(name: str) -> logging.Logger:
    setup_logging()
    return logging.getLogger(name)


def log_failure(
    logger: logging.Logger,
    event: str,
    exc: BaseException,
    *,
    component: str | None = None,
) -> None:
    """Log an operational failure without serializing exception content."""
    if component:
        logger.error(
            "event=%s component=%s status=failed error_type=%s",
            event,
            component,
            type(exc).__name__,
        )
        return
    logger.error("event=%s status=failed error_type=%s", event, type(exc).__name__)
