"""
Cliente Playwright para páginas com renderização JavaScript.

Usado por coletores cujo alvo não entrega dados via HTML estático
(a maioria das corretoras renderiza a prateleira de CDBs via JS).

Requer o extra 'scrapers':
    uv sync --extra scrapers
    playwright install chromium

Uso:

    async with PlaywrightClient() as browser:
        html = await browser.fetch(
            "https://exemplo.com/renda-fixa",
            wait_for=".product-list",   # aguarda esse seletor antes de capturar
        )
        # html contém o DOM completamente renderizado
"""

import logging
from typing import TYPE_CHECKING

logger = logging.getLogger(__name__)

try:
    from playwright.async_api import Browser, Page, async_playwright

    HAS_PLAYWRIGHT = True
except ImportError:
    HAS_PLAYWRIGHT = False

if TYPE_CHECKING:
    from playwright.async_api import Browser, Page


class PlaywrightClient:
    """
    Gerencia um browser Chromium headless via Playwright.

    Context manager assíncrono: abre o browser no __aenter__
    e fecha no __aexit__, liberando todos os recursos.

    Raises:
        ImportError: se playwright não estiver instalado.
    """

    def __init__(self, headless: bool = True) -> None:
        if not HAS_PLAYWRIGHT:
            raise ImportError(
                "playwright não está instalado.\n"
                "Execute: uv sync --extra scrapers && playwright install chromium"
            )
        self._headless = headless
        self._playwright = None
        self._browser: Browser | None = None

    async def __aenter__(self) -> "PlaywrightClient":
        self._playwright = await async_playwright().start()
        self._browser = await self._playwright.chromium.launch(
            headless=self._headless,
            args=["--no-sandbox", "--disable-dev-shm-usage"],
        )
        logger.debug("PlaywrightClient: browser iniciado (headless=%s)", self._headless)
        return self

    async def __aexit__(self, *_args: object) -> None:
        if self._browser:
            await self._browser.close()
        if self._playwright:
            await self._playwright.stop()
        logger.debug("PlaywrightClient: browser encerrado")

    async def fetch(
        self,
        url: str,
        wait_for: str | None = None,
        timeout_ms: int = 30_000,
        user_agent: str | None = None,
    ) -> str:
        """
        Navega até url e retorna o HTML do DOM renderizado.

        Args:
            url: URL a ser carregada.
            wait_for: Seletor CSS a aguardar antes de capturar o HTML.
                      Útil para garantir que o conteúdo JS já foi injetado.
            timeout_ms: Timeout em milissegundos (padrão: 30s).
            user_agent: User-Agent customizado para esta requisição.

        Returns:
            HTML completo da página após renderização.
        """
        assert self._browser is not None, "Use PlaywrightClient como context manager"

        context_kwargs: dict = {"ignore_https_errors": True}
        if user_agent:
            context_kwargs["user_agent"] = user_agent

        context = await self._browser.new_context(**context_kwargs)
        page: Page = await context.new_page()

        try:
            await page.goto(url, timeout=timeout_ms, wait_until="domcontentloaded")

            if wait_for:
                await page.wait_for_selector(wait_for, timeout=timeout_ms)

            return await page.content()
        finally:
            await page.close()
            await context.close()
