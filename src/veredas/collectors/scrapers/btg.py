"""
Coletor de CDBs do BTG Pactual Digital.

Estratégia: Approach A — scraping HTML via Playwright (JS-rendered).
# TODO: migrar para API não-oficial (Approach B)

O BTG Digital renderiza a prateleira de renda fixa via Next.js/React.
O Playwright aguarda o seletor de produto antes de capturar o HTML.

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
_WAIT_FOR = ".fixed-income-card, [class*='FixedIncome'], [class*='product-card'], .renda-fixa-card"
_CARD_SEL = "[class*='FixedIncomeCard'], [class*='product-card'], .renda-fixa-item"
_EMISSOR_SEL = "[class*='issuer'], [class*='emissor'], .card-issuer"
_TAXA_SEL = "[class*='rate'], [class*='taxa'], .card-rate, .rentability"
_PRAZO_SEL = "[class*='term'], [class*='prazo'], .card-term"
_VALOR_MIN_SEL = "[class*='minValue'], [class*='valorMinimo'], .card-min-value"
_LIQUIDEZ_SEL = "[class*='liquidity'], [class*='liquidez'], .card-liquidity"

_URL = "https://www.btgpactualdigital.com/renda-fixa"
_FONTE = "btg"


class BTGCollector(WebCollectorBase):
    """Coleta prateleira de CDB/RF do BTG Pactual Digital."""

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
            logger.exception("BTG: falha ao carregar página")
            return CollectionResult.error(str(exc), source=self.SOURCE)

        ofertas = self._parse(html)
        logger.info("BTG: %d ofertas extraídas", len(ofertas))
        return CollectionResult.ok(data=ofertas, source=self.SOURCE)

    def _parse(self, html: str) -> list[CDBOferta]:
        try:
            from bs4 import BeautifulSoup
        except ImportError:
            logger.exception("beautifulsoup4 não instalado — execute: uv sync --extra scrapers")
            return []

        soup = BeautifulSoup(html, "html.parser")
        cards = soup.select(_CARD_SEL)

        if not cards:
            logger.warning(
                "BTG: nenhum card encontrado — seletor '%s' pode estar desatualizado", _CARD_SEL
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
            logger.debug("BTG: erro ao parsear card — %s", exc)
            return None

    async def health_check(self) -> bool:
        try:
            async with httpx.AsyncClient(timeout=httpx.Timeout(10.0)) as client:
                resp = await client.get(self.BASE_URL, follow_redirects=True)
                return resp.status_code < 500
        except Exception:
            return False
