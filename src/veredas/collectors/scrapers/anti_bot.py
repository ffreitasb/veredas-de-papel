"""
Estratégias anti-bot para scrapers.

Implementa técnicas para evitar detecção e bloqueio:
- Rotação de proxies
- Fingerprint de browser
- Captcha handling (via serviços externos)
- Session management
"""

import asyncio
import hashlib
import logging
import random
import time
from dataclasses import dataclass, field
from typing import Optional

import httpx

logger = logging.getLogger(__name__)


@dataclass
class ProxyConfig:
    """Configuração de proxy."""

    host: str
    port: int
    username: Optional[str] = None
    password: Optional[str] = None
    protocol: str = "http"

    @property
    def url(self) -> str:
        """URL formatada do proxy."""
        auth = ""
        if self.username and self.password:
            auth = f"{self.username}:{self.password}@"
        return f"{self.protocol}://{auth}{self.host}:{self.port}"


@dataclass
class BrowserFingerprint:
    """Fingerprint de navegador para simulação."""

    user_agent: str
    accept_language: str = "pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7"
    accept_encoding: str = "gzip, deflate, br"
    viewport_width: int = 1920
    viewport_height: int = 1080
    timezone: str = "America/Sao_Paulo"
    platform: str = "Win32"
    webgl_vendor: str = "Google Inc. (Intel)"
    webgl_renderer: str = "ANGLE (Intel, Intel(R) UHD Graphics)"


# Fingerprints pré-configurados (Windows, Mac, Linux)
FINGERPRINTS = [
    BrowserFingerprint(
        user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36",
        platform="Win32",
        viewport_width=1920,
        viewport_height=1080,
    ),
    BrowserFingerprint(
        user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36",
        platform="MacIntel",
        viewport_width=1440,
        viewport_height=900,
    ),
    BrowserFingerprint(
        user_agent="Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36",
        platform="Linux x86_64",
        viewport_width=1920,
        viewport_height=1080,
    ),
    BrowserFingerprint(
        user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0",
        platform="Win32",
        viewport_width=1366,
        viewport_height=768,
    ),
]


@dataclass
class RateLimiter:
    """
    Rate limiter adaptativo (thread-safe).

    Ajusta delays baseado em respostas do servidor.
    """

    min_delay: float = 1.0
    max_delay: float = 10.0
    current_delay: float = 1.0
    success_decrease: float = 0.9  # Fator de redução em sucesso
    failure_increase: float = 2.0  # Fator de aumento em falha
    _last_request: float = field(default=0.0, init=False)
    _lock: asyncio.Lock = field(default_factory=asyncio.Lock, init=False)

    async def wait(self) -> None:
        """Aguarda o delay necessário antes da próxima requisição (thread-safe)."""
        async with self._lock:
            now = time.time()
            elapsed = now - self._last_request

            if elapsed < self.current_delay:
                await asyncio.sleep(self.current_delay - elapsed)

            self._last_request = time.time()

    def on_success(self) -> None:
        """Reduz delay após sucesso."""
        self.current_delay = max(
            self.min_delay,
            self.current_delay * self.success_decrease,
        )

    def on_failure(self, status_code: int) -> None:
        """Aumenta delay após falha."""
        if status_code == 429:  # Too Many Requests
            self.current_delay = self.max_delay
        else:
            self.current_delay = min(
                self.max_delay,
                self.current_delay * self.failure_increase,
            )


class ProxyRotator:
    """
    Rotacionador de proxies.

    Gerencia pool de proxies e remove proxies com falha.
    """

    def __init__(self, proxies: list[ProxyConfig]):
        """
        Inicializa o rotacionador.

        Args:
            proxies: Lista de configurações de proxy
        """
        self._proxies = list(proxies)
        self._failed: set[str] = set()
        self._current_index = 0

    def get_next(self) -> Optional[ProxyConfig]:
        """
        Retorna o próximo proxy disponível.

        Returns:
            ProxyConfig ou None se não houver proxies
        """
        available = [p for p in self._proxies if p.url not in self._failed]

        if not available:
            # Reset failures e tenta novamente
            logger.warning("Todos os proxies falharam, resetando...")
            self._failed.clear()
            available = self._proxies

        if not available:
            return None

        self._current_index = (self._current_index + 1) % len(available)
        return available[self._current_index]

    def mark_failed(self, proxy: ProxyConfig) -> None:
        """Marca um proxy como falho."""
        self._failed.add(proxy.url)
        logger.warning(f"Proxy marcado como falho: {proxy.host}:{proxy.port}")

    def mark_success(self, proxy: ProxyConfig) -> None:
        """Remove proxy da lista de falhos após sucesso."""
        self._failed.discard(proxy.url)


class SessionManager:
    """
    Gerenciador de sessões HTTP.

    Mantém cookies e estado entre requisições.
    """

    def __init__(
        self,
        fingerprint: Optional[BrowserFingerprint] = None,
        proxy: Optional[ProxyConfig] = None,
    ):
        """
        Inicializa o gerenciador de sessão.

        Args:
            fingerprint: Fingerprint do navegador
            proxy: Configuração de proxy
        """
        self.fingerprint = fingerprint or random.choice(FINGERPRINTS)
        self.proxy = proxy
        self._cookies: dict[str, str] = {}
        self._client: Optional[httpx.AsyncClient] = None
        self._client_lock = asyncio.Lock()  # Prevents race condition in get_client
        self._session_id = hashlib.md5(
            f"{time.time()}{random.random()}".encode()
        ).hexdigest()[:8]

    @property
    def headers(self) -> dict[str, str]:
        """Headers baseados no fingerprint."""
        return {
            "User-Agent": self.fingerprint.user_agent,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": self.fingerprint.accept_language,
            "Accept-Encoding": self.fingerprint.accept_encoding,
            "Connection": "keep-alive",
            "Upgrade-Insecure-Requests": "1",
            "Sec-Fetch-Dest": "document",
            "Sec-Fetch-Mode": "navigate",
            "Sec-Fetch-Site": "none",
            "Sec-Fetch-User": "?1",
            "Cache-Control": "max-age=0",
        }

    async def get_client(self) -> httpx.AsyncClient:
        """Retorna cliente HTTP com sessão configurada (thread-safe)."""
        async with self._client_lock:
            if self._client is None or self._client.is_closed:
                proxy_url = self.proxy.url if self.proxy else None
                self._client = httpx.AsyncClient(
                    headers=self.headers,
                    cookies=self._cookies,
                    proxy=proxy_url,
                    follow_redirects=True,
                    timeout=30.0,
                )
            return self._client

    async def close(self) -> None:
        """Fecha a sessão."""
        if self._client and not self._client.is_closed:
            # Preserva cookies antes de fechar
            self._cookies.update(dict(self._client.cookies))
            await self._client.aclose()
            self._client = None

    def update_cookies(self, cookies: dict[str, str]) -> None:
        """Atualiza cookies da sessão."""
        self._cookies.update(cookies)

    def clear_cookies(self) -> None:
        """Limpa cookies da sessão."""
        self._cookies.clear()


class CaptchaSolver:
    """
    Interface para resolução de captchas.

    Integra com serviços como 2captcha, anticaptcha, etc.
    Nota: Requer API key do serviço escolhido.
    """

    def __init__(self, api_key: Optional[str] = None, service: str = "2captcha"):
        """
        Inicializa o solver.

        Args:
            api_key: Chave da API do serviço
            service: Nome do serviço (2captcha, anticaptcha)
        """
        self.api_key = api_key
        self.service = service

    async def solve_recaptcha_v2(
        self,
        site_key: str,
        page_url: str,
        timeout: int = 120,
    ) -> Optional[str]:
        """
        Resolve reCAPTCHA v2.

        Args:
            site_key: Chave do site (data-sitekey)
            page_url: URL da página com o captcha
            timeout: Timeout em segundos

        Returns:
            Token de resposta ou None
        """
        if not self.api_key:
            logger.warning("API key não configurada para captcha solver")
            return None

        # Implementação placeholder - requer integração real com serviço
        logger.info(f"Captcha solving solicitado para {page_url}")
        return None

    async def solve_hcaptcha(
        self,
        site_key: str,
        page_url: str,
        timeout: int = 120,
    ) -> Optional[str]:
        """
        Resolve hCaptcha.

        Args:
            site_key: Chave do site
            page_url: URL da página
            timeout: Timeout em segundos

        Returns:
            Token de resposta ou None
        """
        if not self.api_key:
            logger.warning("API key não configurada para captcha solver")
            return None

        logger.info(f"hCaptcha solving solicitado para {page_url}")
        return None


def generate_device_id() -> str:
    """
    Gera um device ID consistente para a sessão.

    Returns:
        Device ID hexadecimal
    """
    seed = f"{time.time()}{random.random()}"
    return hashlib.sha256(seed.encode()).hexdigest()[:32]


def randomize_request_timing() -> float:
    """
    Gera delay humanizado entre requisições.

    Returns:
        Delay em segundos (1-5s com distribuição gaussiana)
    """
    # Distribuição gaussiana centrada em 2s
    delay = random.gauss(2.0, 0.8)
    return max(0.5, min(5.0, delay))  # Clamp entre 0.5 e 5 segundos
