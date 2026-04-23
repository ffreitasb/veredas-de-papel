"""
Testes unitários para WebCollectorBase.

Usa respx para mockar o httpx sem fazer requisições reais.
"""

from unittest.mock import AsyncMock, patch

import httpx
import pytest
import respx

from veredas.collectors.base import CollectionResult
from veredas.collectors.scraper_base import WebCollectorBase

# ---------------------------------------------------------------------------
# Coletor concreto mínimo para os testes
# ---------------------------------------------------------------------------


class _DummyCollector(WebCollectorBase):
    SOURCE = "dummy"
    BASE_URL = "https://dummy.example.com"
    _RATE_LIMIT_SECONDS = 0.0  # desativa rate limit nos testes

    async def collect(self) -> CollectionResult:
        resp = await self._get(self.BASE_URL)
        return CollectionResult.ok(data=resp.text, source=self.SOURCE)


# ---------------------------------------------------------------------------
# Contexto de ciclo de vida
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_context_manager_opens_and_closes_client():
    async with _DummyCollector() as col:
        assert col._client is not None
    assert col._client is None


@pytest.mark.asyncio
async def test_get_without_context_manager_raises():
    col = _DummyCollector()
    with pytest.raises(RuntimeError, match="context manager"):
        await col._get("https://dummy.example.com")


# ---------------------------------------------------------------------------
# Requisição bem-sucedida
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
@respx.mock
async def test_successful_get_returns_response():
    respx.get("https://dummy.example.com").mock(return_value=httpx.Response(200, text="ok"))

    async with _DummyCollector() as col:
        resp = await col._get("https://dummy.example.com")

    assert resp.status_code == 200
    assert resp.text == "ok"


@pytest.mark.asyncio
@respx.mock
async def test_collect_returns_success_result():
    respx.get("https://dummy.example.com").mock(
        return_value=httpx.Response(200, text="<html>dados</html>")
    )

    async with _DummyCollector() as col:
        result = await col.collect()

    assert result.success is True
    assert result.source == "dummy"
    assert "<html>" in result.data


# ---------------------------------------------------------------------------
# Retry em erros 5xx
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
@respx.mock
async def test_retries_on_500_then_succeeds():
    route = respx.get("https://dummy.example.com")
    route.side_effect = [
        httpx.Response(503),
        httpx.Response(200, text="ok"),
    ]

    async with _DummyCollector() as col:
        col._MAX_RETRIES = 3
        with patch("asyncio.sleep", new_callable=AsyncMock):
            resp = await col._get("https://dummy.example.com")

    assert resp.status_code == 200
    assert route.call_count == 2


@pytest.mark.asyncio
@respx.mock
async def test_raises_after_max_retries_exhausted():
    respx.get("https://dummy.example.com").mock(return_value=httpx.Response(503))

    async with _DummyCollector() as col:
        col._MAX_RETRIES = 3
        with patch("asyncio.sleep", new_callable=AsyncMock), pytest.raises(httpx.HTTPStatusError):
            await col._get("https://dummy.example.com")


@pytest.mark.asyncio
@respx.mock
async def test_does_not_retry_on_404():
    respx.get("https://dummy.example.com").mock(return_value=httpx.Response(404))

    async with _DummyCollector() as col:
        with pytest.raises(httpx.HTTPStatusError) as exc_info:
            await col._get("https://dummy.example.com")

    assert exc_info.value.response.status_code == 404


@pytest.mark.asyncio
@respx.mock
async def test_retries_on_timeout():
    route = respx.get("https://dummy.example.com")
    route.side_effect = [
        httpx.TimeoutException("timeout"),
        httpx.Response(200, text="ok"),
    ]

    async with _DummyCollector() as col:
        col._MAX_RETRIES = 3
        with patch("asyncio.sleep", new_callable=AsyncMock):
            resp = await col._get("https://dummy.example.com")

    assert resp.status_code == 200
    assert route.call_count == 2


# ---------------------------------------------------------------------------
# Backoff delay
# ---------------------------------------------------------------------------


def test_backoff_delay_grows_exponentially():
    delays = [_DummyCollector._backoff_delay(i) for i in range(3)]
    # 2^0 + jitter ≈ 1–2, 2^1 + jitter ≈ 2–3, 2^2 + jitter ≈ 4–5
    assert delays[0] < delays[1] < delays[2]
    assert delays[0] >= 1.0
    assert delays[1] >= 2.0
    assert delays[2] >= 4.0


# ---------------------------------------------------------------------------
# Rate limiting
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
@respx.mock
async def test_rate_limit_called_between_requests():
    respx.get("https://dummy.example.com").mock(return_value=httpx.Response(200, text="ok"))

    sleep_calls: list[float] = []

    async def fake_sleep(seconds: float) -> None:
        sleep_calls.append(seconds)

    class FastCollector(_DummyCollector):
        _RATE_LIMIT_SECONDS = 1.0  # reativa para este teste

    with patch("veredas.collectors.scraper_base.asyncio.sleep", side_effect=fake_sleep):
        async with FastCollector() as col:
            # Primeira chamada: _last_request_at=0 → elapsed grande → sem espera
            await col._get("https://dummy.example.com")
            # Segunda chamada imediata: elapsed ≈ 0 → deve dormir ~1s
            col._last_request_at = col._last_request_at  # sem alterar
            await col._get("https://dummy.example.com")

    # Deve ter dormido ao menos uma vez (segunda requisição)
    assert any(s > 0 for s in sleep_calls)


# ---------------------------------------------------------------------------
# Headers e User-Agent
# ---------------------------------------------------------------------------


def test_build_headers_contains_required_keys():
    col = _DummyCollector()
    headers = col._build_headers()

    assert "User-Agent" in headers
    assert "Accept" in headers
    assert "Accept-Language" in headers
    assert "pt-BR" in headers["Accept-Language"]


def test_user_agent_varies_across_calls():
    col = _DummyCollector()
    agents = {col._build_headers()["User-Agent"] for _ in range(30)}
    # Com 6 UAs no pool, 30 chamadas devem produzir ao menos 2 distintos
    assert len(agents) >= 2


# ---------------------------------------------------------------------------
# source_name e health_check
# ---------------------------------------------------------------------------


def test_source_name_returns_source_constant():
    assert _DummyCollector().source_name == "dummy"


@pytest.mark.asyncio
@respx.mock
async def test_health_check_returns_true_on_200():
    respx.get("https://dummy.example.com").mock(return_value=httpx.Response(200))

    async with _DummyCollector() as col:
        ok = await col.health_check()

    assert ok is True


@pytest.mark.asyncio
@respx.mock
async def test_health_check_returns_false_on_error():
    respx.get("https://dummy.example.com").mock(side_effect=httpx.ConnectError("refused"))

    async with _DummyCollector() as col:
        ok = await col.health_check()

    assert ok is False
