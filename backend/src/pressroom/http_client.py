"""Pre-configured httpx.AsyncClient and tenacity retry helpers."""

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

import httpx
from tenacity import retry, retry_if_exception, stop_after_attempt, wait_exponential

from pressroom.config import settings


def _is_retryable(exc: BaseException) -> bool:
    """Return True for 5xx responses, connection errors, and timeouts.

    4xx responses are NOT retried — they indicate a client-side problem that
    won't resolve on its own.
    """
    if isinstance(exc, httpx.HTTPStatusError):
        return exc.response.status_code >= 500
    return isinstance(exc, (httpx.ConnectError, httpx.TimeoutException))


retry_on_transient = retry(
    retry=retry_if_exception(_is_retryable),
    wait=wait_exponential(multiplier=1, min=1, max=4),
    stop=stop_after_attempt(3),
    reraise=True,
)


@asynccontextmanager
async def get_client(
    *,
    transport: httpx.AsyncBaseTransport | None = None,
) -> AsyncGenerator[httpx.AsyncClient, None]:
    """Yield a configured ``httpx.AsyncClient``.

    Sets the project User-Agent and per-request timeout from settings.
    Pass *transport* to inject a mock transport for tests.
    """
    async with httpx.AsyncClient(
        headers={"User-Agent": settings.user_agent},
        timeout=httpx.Timeout(settings.fetch_timeout),
        follow_redirects=True,
        transport=transport,
    ) as client:
        yield client
