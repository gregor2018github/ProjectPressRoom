"""Tests for pressroom.http_client."""

import httpx

from pressroom.config import settings
from pressroom.http_client import get_client
from tests.conftest import make_async_transport


async def test_user_agent_header_is_sent() -> None:
    captured: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        captured.append(request.headers.get("user-agent", ""))
        return httpx.Response(200)

    async with get_client(transport=make_async_transport(handler)) as client:
        await client.get("http://test.local/feed")

    assert len(captured) == 1
    assert captured[0] == settings.user_agent


async def test_timeout_comes_from_settings() -> None:
    async with get_client() as client:
        assert client.timeout.read == settings.fetch_timeout
