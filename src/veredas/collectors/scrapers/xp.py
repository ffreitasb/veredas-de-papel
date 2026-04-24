"""
Coletor de CDBs da XP Investimentos.

Estratégia: Approach A — scraping HTML via Playwright (JS-rendered).
# TODO: migrar para API não-oficial (Approach B)

A XP renderiza sua prateleira de renda fixa via React. O Playwright
aguarda o seletor de produto antes de capturar o HTML.

Seletores marcados com "# SELECTOR:" precisam ser verificados contra
o site ao vivo caso o scraper pare de funcionar.
"""

import logging

import httpx

from veredas.collectors.base import CollectionResult
from veredas.collectors.scraper_base import WebCollectorBase
from veredas.collectors.scrapers.normalize import (
    CDBOferta,
    normalizar_cnpj,
    parse_prazo_dias,
    parse_taxa,
    parse_valor_minimo,
)

logger = logging.getLogger(__name__)

# SELECTOR: verificar contra o site ao vivo caso o scraper pare de funcionar
_WAIT_FOR = ".product-shelf, [data-testid='product-card'], .renda-fixa-produto"
_CARD_SEL = "[data-testid='product-card'], .renda-fixa-card, .product-shelf-item"
_EMISSOR_SEL = ".emissor-nome, .product-issuer, [data-testid='issuer-name']"
_TAXA_SEL = ".taxa-rentabilidade, .product-rate, [data-testid='product-rate']"
_PRAZO_SEL = ".prazo-dias, .product-term, [data-testid='product-term']"
_VALOR_MIN_SEL = ".valor-minimo, .product-min-value, [data-testid='min-investment']"
_LIQUIDEZ_SEL = ".liquidez-diaria, .product-liquidity, [data-testid='liquidity']"

_URL = "https://www.xpi.com.br/investimentos/renda-fixa/"
_FONTE = "xp"


class XPCollector(WebCollectorBase):
    """Coleta prateleira de CDB/RF da XP Investimentos."""

    SOURCE = _FONTE
    BASE_URL = _URL

    # TODO: migrar para API não-oficial (Approach B)

    async def collect(self) -> CollectionResult:
        try:
            from veredas.collectors.scraper_client import PlaywrightClient
        except ImportError:
            return CollectionResult.error(
                "playwright não instalado — execute: uv sync --extra scrapers && playwright install chromium",
                source=self.SOURCE,
            )

        try:
            async with PlaywrightClient() as browser:
                html = await browser.fetch(self.BASE_URL, wait_for=_WAIT_FOR, timeout_ms=45_000)
        except Exception as exc:
            logger.error("XP: falha ao carregar página — %s", exc)
            return CollectionResult.error(str(exc), source=self.SOURCE)

        ofertas = self._parse(html)
        logger.info("XP: %d ofertas extraídas", len(ofertas))
        return CollectionResult.ok(data=ofertas, source=self.SOURCE)

    def _parse(self, html: str) -> list[CDBOferta]:
        try:
            from bs4 import BeautifulSoup
        except ImportError:
            logger.error("beautifulsoup4 não instalado — execute: uv sync --extra scrapers")
            return []

        soup = BeautifulSoup(html, "html.parser")
        cards = soup.select(_CARD_SEL)

        if not cards:
            logger.warning(
                "XP: nenhum card encontrado — seletor '%s' pode estar desatualizado", _CARD_SEL
            )
            return []

        ofertas: list[CDBOferta] = []
        for card in cards:
            oferta = self._parse_card(card)
            if oferta:
                ofertas.append(oferta)
        return ofertas

    def _parse_card(self, card) -> CDBOferta | None:
        try:
            emissor_tag = card.select_one(_EMISSOR_SEL)
            taxa_tag = card.select_one(_TAXA_SEL)
            prazo_tag = card.select_one(_PRAZO_SEL)

            if not (emissor_tag and taxa_tag and prazo_tag):
                return None

            emissor_nome = emissor_tag.get_text(strip=True)
            taxa_text = taxa_tag.get_text(strip=True)
            prazo_text = prazo_tag.get_text(strip=True)

            indexador, percentual, taxa_adicional = parse_taxa(taxa_text)
            prazo_dias = parse_prazo_dias(prazo_text)
            if prazo_dias <= 0:
                return None

            valor_tag = card.select_one(_VALOR_MIN_SEL)
            valor_minimo = parse_valor_minimo(valor_tag.get_text(strip=True)) if valor_tag else None

            liquidez_tag = card.select_one(_LIQUIDEZ_SEL)
            liquidez_text = (liquidez_tag.get_text(strip=True) if liquidez_tag else "").lower()
            liquidez_diaria = (
                "diária" in liquidez_text or "diario" in liquidez_text or "d+" in liquidez_text
            )

            cnpj_text = card.get("data-cnpj", "") or ""
            emissor_cnpj = normalizar_cnpj(cnpj_text)

            return CDBOferta(
                emissor_nome=emissor_nome,
                emissor_cnpj=emissor_cnpj,
                indexador=indexador,
                percentual=percentual,
                taxa_adicional=taxa_adicional,
                prazo_dias=prazo_dias,
                valor_minimo=valor_minimo,
                liquidez_diaria=liquidez_diaria,
                fonte=_FONTE,
                url_fonte=_URL,
                raw={
                    "taxa_raw": taxa_text,
                    "prazo_raw": prazo_text,
                    "emissor_raw": emissor_nome,
                },
            )
        except Exception as exc:
            logger.debug("XP: erro ao parsear card — %s", exc)
            return None

    async def health_check(self) -> bool:
        try:
            async with httpx.AsyncClient(timeout=httpx.Timeout(10.0)) as client:
                resp = await client.get(self.BASE_URL, follow_redirects=True)
                return resp.status_code < 500
        except Exception:
            return False
