"""Shared pytest fixtures and helpers."""

from collections.abc import Callable

import httpx


def make_async_transport(
    handler: Callable[[httpx.Request], httpx.Response],
) -> httpx.AsyncBaseTransport:
    """Wrap a sync request handler into an ``AsyncBaseTransport`` for testing."""

    class _AsyncTransport(httpx.AsyncBaseTransport):
        async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
            return handler(request)

    return _AsyncTransport()
