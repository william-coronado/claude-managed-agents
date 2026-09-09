"""Retry helper for transient Anthropic API failures.

The SDK already retries 408/409/429/5xx and connection errors internally, but a
managed-agents run makes several distinct calls (session create, event send,
stream open) and a transient network/overload failure on any one of them aborts
the pipeline. This wraps a callable with exponential backoff so a pipeline step
survives a blip, matching the repo's git-operation retry convention
(4 attempts, 2/4/8/16s).
"""
import logging
import time
from typing import Callable, TypeVar

import anthropic

logger = logging.getLogger(__name__)

T = TypeVar("T")

# Connection/timeout failures carry no HTTP status but are transient.
# (APITimeoutError is a subclass of APIConnectionError.)
_CONNECTION_ERRORS = (anthropic.APIConnectionError,)
# HTTP statuses worth retrying (matches the SDK's own retry policy).
_RETRYABLE_STATUS = frozenset({408, 409, 429})


def _is_transient(exc: Exception) -> bool:
    """True only for network/overload failures — never for programming errors.

    Retries connection/timeout errors, and any exception exposing an integer
    ``status_code`` of 408/409/429 or >= 500 (covers RateLimitError,
    InternalServerError, and APIStatusError). Anything else — a ValueError,
    KeyError, a 4xx client error — is not transient.
    """
    if isinstance(exc, _CONNECTION_ERRORS):
        return True
    status = getattr(exc, "status_code", None)
    if isinstance(status, int):
        return status in _RETRYABLE_STATUS or status >= 500
    return False


def with_retries(
    func: Callable[[], T],
    *,
    attempts: int = 4,
    base_delay: float = 2.0,
    description: str = "operation",
) -> T:
    """Call ``func`` with exponential backoff on transient failures.

    Delays follow base_delay * 2**n (2/4/8/16s by default). Non-transient
    errors are re-raised immediately.
    """
    for attempt in range(attempts):
        try:
            return func()
        except Exception as exc:  # noqa: BLE001 - re-raised below when not transient
            if not _is_transient(exc) or attempt == attempts - 1:
                raise
            delay = base_delay * (2 ** attempt)
            logger.warning(
                "%s failed (attempt %d/%d): %s; retrying in %.0fs",
                description, attempt + 1, attempts, exc, delay,
            )
            time.sleep(delay)
    # Unreachable: the loop either returns or raises.
    raise AssertionError("with_retries exhausted its loop without returning or raising")
