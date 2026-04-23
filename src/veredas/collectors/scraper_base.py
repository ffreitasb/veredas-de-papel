"""
Base para coletores web (scrapers de corretoras e fontes externas).

Fornece infraestrutura reutilizável para todos os coletores da Fase 4:
- Rate limiting por instância (evita banimento por flood)
- Retry com backoff exponencial e jitter
- Rotação de User-Agent
- Headers realistas (simula navegador desktop)
- Context manager assíncrono (gerencia ciclo de vida do httpx.AsyncClient)

Uso:

    class XPCollector(WebCollectorBase):
        SOURCE = "xp"
        BASE_URL = "https://www.xpi.com.br/..."

        async def collect(self) -> CollectionResult:
            resp = await self._get(self.BASE_URL)
            return CollectionResult.ok(self._parse(resp.text), self.SOURCE)

        async def _parse(self, html: str) -> list[TaxaCDB]:
            ...
"""

import asyncio
import logging
import random
import time
from abc import abstractmethod

import httpx

from veredas.collectors.base import BaseCollector, CollectionResult

logger = logging.getLogger(__name__)

# Pool de User-Agents de navegadores desktop reais (Chrome/Firefox, atualizados 2025)
_USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:125.0) Gecko/20100101 Firefox/125.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14.4; rv:125.0) Gecko/20100101 Firefox/125.0",
]


class WebCollectorBase(BaseCollector):
    """
    Base para coletores de páginas web.

    Subclasses devem definir as constantes de classe SOURCE e BASE_URL,
    e implementar `collect()` e `_parse()`.

    Configuração via atributos de classe (sobrescreva conforme necessário):
        _RATE_LIMIT_SECONDS: pausa mínima entre requisições (padrão: 2s)
        _MAX_RETRIES: tentativas em caso de erro 5xx ou timeout (padrão: 3)
        _TIMEOUT: timeout total da requisição (padrão: 30s)
    """

    SOURCE: str  # identificador da fonte, ex: "xp", "btg"
    BASE_URL: str  # URL raiz do site alvo

    _RATE_LIMIT_SECONDS: float = 2.0
    _MAX_RETRIES: int = 3
    _TIMEOUT: httpx.Timeout = httpx.Timeout(30.0, connect=10.0)

    def __init__(self) -> None:
        self._client: httpx.AsyncClient | None = None
        self._last_request_at: float = 0.0
        self._lock = asyncio.Lock()

    # ------------------------------------------------------------------
    # Context manager
    # ------------------------------------------------------------------

    async def __aenter__(self) -> "WebCollectorBase":
        self._client = httpx.AsyncClient(
            headers=self._build_headers(),
            timeout=self._TIMEOUT,
            follow_redirects=True,
        )
        return self

    async def __aexit__(self, *_args: object) -> None:
        if self._client:
            await self._client.aclose()
            self._client = None

    # ------------------------------------------------------------------
    # Propriedades obrigatórias de BaseCollector
    # ------------------------------------------------------------------

    @property
    def source_name(self) -> str:
        return self.SOURCE

    async def health_check(self) -> bool:
        try:
            resp = await self._get(self.BASE_URL)
            return resp.status_code < 400
        except Exception:
            return False

    # ------------------------------------------------------------------
    # Interface para subclasses
    # ------------------------------------------------------------------

    @abstractmethod
    async def collect(self) -> CollectionResult:
        """Executa a coleta e retorna CollectionResult."""
        ...

    # ------------------------------------------------------------------
    # HTTP helpers
    # ------------------------------------------------------------------

    async def _get(self, url: str, **kwargs: object) -> httpx.Response:
        """
        GET com rate limiting e retry exponencial.

        Aplica pausa entre requisições para evitar banimento,
        e retenta até _MAX_RETRIES vezes em caso de erro transitório.
        """
        if self._client is None:
            raise RuntimeError(
                f"{self.__class__.__name__} deve ser usado como context manager "
                "(async with XPCollector() as c: ...)"
            )

        async with self._lock:
            await self._enforce_rate_limit()

            last_exc: Exception = RuntimeError("sem tentativas")
            for attempt in range(self._MAX_RETRIES):
                try:
                    response = await self._client.get(url, **kwargs)
                    response.raise_for_status()
                    self._last_request_at = time.monotonic()
                    return response

                except httpx.HTTPStatusError as exc:
                    # Só retenta em erros de servidor (5xx); 4xx é definitivo
                    if exc.response.status_code < 500:
                        raise
                    last_exc = exc

                except (httpx.TimeoutException, httpx.TransportError) as exc:
                    last_exc = exc

                if attempt < self._MAX_RETRIES - 1:
                    delay = self._backoff_delay(attempt)
                    logger.warning(
                        "%s: tentativa %d/%d falhou (%s) — aguardando %.1fs",
                        self.SOURCE,
                        attempt + 1,
                        self._MAX_RETRIES,
                        type(last_exc).__name__,
                        delay,
                    )
                    await asyncio.sleep(delay)

            logger.error("%s: todas as %d tentativas falharam", self.SOURCE, self._MAX_RETRIES)
            raise last_exc

    async def _enforce_rate_limit(self) -> None:
        """Aguarda o tempo necessário para respeitar o rate limit."""
        elapsed = time.monotonic() - self._last_request_at
        wait = self._RATE_LIMIT_SECONDS - elapsed
        if wait > 0:
            await asyncio.sleep(wait)

    @staticmethod
    def _backoff_delay(attempt: int) -> float:
        """Backoff exponencial com jitter: 2^attempt + random[0, 1)."""
        return (2**attempt) + random.uniform(0, 1)  # noqa: S311

    def _build_headers(self) -> dict[str, str]:
        """Headers realistas que simulam um navegador desktop."""
        return {
            "User-Agent": random.choice(_USER_AGENTS),  # noqa: S311
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
            "Accept-Language": "pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7",
            "Accept-Encoding": "gzip, deflate, br",
            "Connection": "keep-alive",
            "Upgrade-Insecure-Requests": "1",
            "Sec-Fetch-Dest": "document",
            "Sec-Fetch-Mode": "navigate",
            "Sec-Fetch-Site": "none",
        }
