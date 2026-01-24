"""
Base para scrapers de corretoras.

Estende BaseCollector com funcionalidades específicas para web scraping:
- Gerenciamento de sessão HTTP
- Estratégias anti-bot
- Normalização de dados
- Retry com backoff exponencial
"""

import asyncio
import logging
import random
import re
from abc import abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from typing import Any, Optional

import httpx

from veredas import TZ_BRASIL
from veredas.collectors.base import BaseCollector, CollectionResult
from veredas.storage.models import Indexador

logger = logging.getLogger(__name__)


@dataclass
class TaxaColetada:
    """Taxa de CDB coletada de uma corretora."""

    instituicao_nome: str
    instituicao_cnpj: Optional[str]
    indexador: Indexador
    percentual: Decimal
    taxa_adicional: Optional[Decimal] = None  # Para IPCA+X%
    prazo_dias: int = 365
    valor_minimo: Optional[Decimal] = None
    liquidez_diaria: bool = False
    raw_data: Optional[dict] = None


@dataclass
class ScraperResult:
    """Resultado de scraping de uma corretora."""

    taxas: list[TaxaColetada] = field(default_factory=list)
    timestamp: datetime = field(default_factory=lambda: datetime.now(TZ_BRASIL))
    fonte: str = ""
    url: str = ""
    erros: list[str] = field(default_factory=list)


# User agents reais para rotação
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2 Safari/605.1.15",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
]


class BaseScraper(BaseCollector):
    """
    Classe base para scrapers de corretoras.

    Fornece:
    - Cliente HTTP async com retry
    - Rotação de user agent
    - Rate limiting configurável
    - Parsing de taxas normalizado
    """

    def __init__(
        self,
        timeout: int = 30,
        max_retries: int = 3,
        base_delay: float = 1.0,
        jitter: float = 0.5,
    ):
        """
        Inicializa o scraper.

        Args:
            timeout: Timeout em segundos para requisições
            max_retries: Número máximo de tentativas
            base_delay: Delay base entre requisições (segundos)
            jitter: Variação aleatória no delay (0-1)
        """
        self.timeout = timeout
        self.max_retries = max_retries
        self.base_delay = base_delay
        self.jitter = jitter
        self._client: Optional[httpx.AsyncClient] = None
        self._client_lock = asyncio.Lock()  # Prevents race condition in _get_client

    @property
    @abstractmethod
    def broker_name(self) -> str:
        """Nome da corretora."""
        ...

    @property
    @abstractmethod
    def base_url(self) -> str:
        """URL base da corretora."""
        ...

    @property
    def source_name(self) -> str:
        """Nome da fonte (implementa BaseCollector)."""
        return f"scraper_{self.broker_name}"

    def _get_random_user_agent(self) -> str:
        """Retorna um user agent aleatório."""
        return random.choice(USER_AGENTS)

    def _get_headers(self) -> dict[str, str]:
        """Retorna headers padrão para requisições."""
        return {
            "User-Agent": self._get_random_user_agent(),
            "Accept": "application/json, text/html, */*",
            "Accept-Language": "pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7",
            "Accept-Encoding": "gzip, deflate, br",
            "Connection": "keep-alive",
            "Cache-Control": "no-cache",
        }

    async def _get_client(self) -> httpx.AsyncClient:
        """Retorna cliente HTTP reutilizável (thread-safe)."""
        async with self._client_lock:
            if self._client is None or self._client.is_closed:
                self._client = httpx.AsyncClient(
                    timeout=self.timeout,
                    follow_redirects=True,
                    headers=self._get_headers(),
                )
            return self._client

    async def __aenter__(self) -> "BaseScraper":
        """Context manager entry."""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        """Context manager exit - ensures client cleanup."""
        await self._close_client()

    async def _close_client(self) -> None:
        """Fecha o cliente HTTP."""
        if self._client and not self._client.is_closed:
            await self._client.aclose()
            self._client = None

    async def _delay(self) -> None:
        """Aplica delay com jitter entre requisições."""
        jitter_amount = random.uniform(-self.jitter, self.jitter) * self.base_delay
        delay = max(0.1, self.base_delay + jitter_amount)
        await asyncio.sleep(delay)

    async def _fetch_with_retry(
        self,
        url: str,
        method: str = "GET",
        **kwargs: Any,
    ) -> httpx.Response:
        """
        Faz requisição HTTP com retry e backoff exponencial.

        Args:
            url: URL para requisição
            method: Método HTTP (GET, POST, etc)
            **kwargs: Argumentos adicionais para httpx

        Returns:
            httpx.Response

        Raises:
            httpx.HTTPError: Se todas as tentativas falharem
        """
        client = await self._get_client()
        last_error: Optional[Exception] = None

        for attempt in range(self.max_retries):
            try:
                if attempt > 0:
                    backoff = self.base_delay * (2**attempt)
                    logger.debug(
                        f"[{self.broker_name}] Retry {attempt + 1}/{self.max_retries}, "
                        f"aguardando {backoff:.1f}s"
                    )
                    await asyncio.sleep(backoff)

                # Atualiza headers a cada tentativa
                kwargs.setdefault("headers", {})
                kwargs["headers"]["User-Agent"] = self._get_random_user_agent()

                response = await client.request(method, url, **kwargs)
                response.raise_for_status()
                return response

            except httpx.HTTPStatusError as e:
                last_error = e
                status = e.response.status_code
                logger.warning(
                    f"[{self.broker_name}] HTTP {status} em {url}"
                )
                if status in (401, 403, 429):
                    # Auth error ou rate limit - backoff maior
                    await asyncio.sleep(self.base_delay * 5)
                elif status >= 500:
                    # M3 FIX: Erros 5xx são transientes - retry com backoff
                    logger.info(f"[{self.broker_name}] Erro de servidor {status}, tentando novamente...")
                    await asyncio.sleep(self.base_delay * 2)

            except httpx.RequestError as e:
                last_error = e
                logger.warning(f"[{self.broker_name}] Erro de conexão: {e}")

        raise last_error or httpx.RequestError(f"Falha após {self.max_retries} tentativas")

    @abstractmethod
    async def _scrape(self) -> ScraperResult:
        """
        Implementa a lógica de scraping específica da corretora.

        Returns:
            ScraperResult com taxas coletadas
        """
        ...

    async def collect(self) -> CollectionResult[ScraperResult]:
        """
        Executa a coleta de taxas (implementa BaseCollector).

        Returns:
            CollectionResult com ScraperResult
        """
        try:
            result = await self._scrape()
            await self._close_client()

            if result.taxas:
                logger.info(
                    f"[{self.broker_name}] Coletadas {len(result.taxas)} taxas"
                )
                return CollectionResult.ok(
                    data=result,
                    source=self.source_name,
                    raw_response={"taxas_count": len(result.taxas)},
                )
            else:
                return CollectionResult.fail(
                    error=f"Nenhuma taxa encontrada: {', '.join(result.erros)}",
                    source=self.source_name,
                )

        except Exception as e:
            logger.exception(f"[{self.broker_name}] Erro na coleta")
            await self._close_client()
            return CollectionResult.fail(
                error=str(e),
                source=self.source_name,
            )

    async def health_check(self) -> bool:
        """
        Verifica se a corretora está acessível (implementa BaseCollector).

        Returns:
            True se o site responde
        """
        try:
            client = await self._get_client()
            response = await client.get(self.base_url, timeout=10)
            await self._close_client()
            return response.status_code < 500
        except Exception:
            await self._close_client()
            return False

    def _parse_percentual(self, value: Any) -> Optional[Decimal]:
        """
        Converte valor para Decimal de percentual.

        Args:
            value: Valor a converter (string, float, int)

        Returns:
            Decimal ou None se inválido
        """
        if value is None:
            return None

        try:
            if isinstance(value, str):
                # Remove caracteres não numéricos exceto . e ,
                cleaned = value.replace("%", "").replace(" ", "").strip()
                cleaned = cleaned.replace(",", ".")
                return Decimal(cleaned)
            return Decimal(str(value))
        except Exception:
            return None

    def _parse_valor(self, value: Any) -> Optional[Decimal]:
        """
        Converte valor monetário para Decimal.

        Args:
            value: Valor a converter

        Returns:
            Decimal ou None se inválido
        """
        if value is None:
            return None

        try:
            if isinstance(value, str):
                # Remove R$, pontos de milhar, etc
                cleaned = value.replace("R$", "").replace(" ", "").strip()
                # Formato BR: 1.000,00 -> 1000.00
                if "," in cleaned:
                    cleaned = cleaned.replace(".", "").replace(",", ".")
                return Decimal(cleaned)
            return Decimal(str(value))
        except Exception:
            return None

    def _parse_prazo(self, value: Any) -> int:
        """
        Converte prazo para dias.

        Args:
            value: Prazo em dias, meses ou anos

        Returns:
            Prazo em dias (padrão 365)
        """
        if value is None:
            return 365

        try:
            if isinstance(value, str):
                value_lower = value.lower().strip()
                # M4 FIX: import moved to top of file
                numbers = re.findall(r"\d+", value_lower)
                if not numbers:
                    return 365
                num = int(numbers[0])

                # Converte unidade
                if "ano" in value_lower or "year" in value_lower:
                    return num * 365
                elif "mes" in value_lower or "month" in value_lower:
                    return num * 30
                else:
                    return num  # Assume dias
            return int(value)
        except Exception:
            return 365

    def _detect_indexador(self, text: str) -> Indexador:
        """
        Detecta o indexador a partir do texto.

        Args:
            text: Texto descritivo do produto

        Returns:
            Indexador detectado
        """
        text_upper = text.upper()

        if "IPCA" in text_upper:
            return Indexador.IPCA
        elif "PRE" in text_upper or "PREFIXAD" in text_upper:
            return Indexador.PREFIXADO
        elif "SELIC" in text_upper:
            return Indexador.SELIC
        else:
            return Indexador.CDI  # Padrão
