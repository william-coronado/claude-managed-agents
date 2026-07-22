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

logger = logging.getLogger(__name__)

T = TypeVar("T")

# Retry only on errors that are plausibly transient. Import lazily so the module
# is usable (and testable) without the anthropic package installed.
_TRANSIENT_MESSAGE_HINTS = ("overloaded", "timeout", "timed out", "connection", "temporarily")


def _is_transient(exc: Exception) -> bool:
    status = getattr(exc, "status_code", None)
    if status is not None:
        return status == 408 or status == 409 or status == 429 or status >= 500
    msg = str(exc).lower()
    return any(hint in msg for hint in _TRANSIENT_MESSAGE_HINTS)


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
    last_exc: Exception | None = None
    for attempt in range(attempts):
        try:
            return func()
        except Exception as exc:  # noqa: BLE001 - re-raised below when not transient
            if not _is_transient(exc) or attempt == attempts - 1:
                raise
            last_exc = exc
            delay = base_delay * (2 ** attempt)
            logger.warning(
                "%s failed (attempt %d/%d): %s; retrying in %.0fs",
                description, attempt + 1, attempts, exc, delay,
            )
            time.sleep(delay)
    # Unreachable (loop either returns or raises), but keep type-checkers happy.
    raise last_exc  # type: ignore[misc]
