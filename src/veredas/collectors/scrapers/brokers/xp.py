"""
Scraper para XP Investimentos.

A XP possui uma API pública para consulta de produtos de renda fixa.
Usa JavaScript rendering para algumas páginas, mas a API é acessível diretamente.
"""

import logging
from decimal import Decimal
from typing import Any

from veredas.collectors.scrapers.base import (
    BaseScraper,
    ScraperResult,
    TaxaColetada,
)
from veredas.storage.models import Indexador

logger = logging.getLogger(__name__)


class XPScraper(BaseScraper):
    """
    Scraper para XP Investimentos.

    Coleta taxas de CDB da plataforma XP através da API pública.
    A XP oferece produtos próprios e de terceiros (marketplace).
    """

    @property
    def broker_name(self) -> str:
        return "xp"

    @property
    def base_url(self) -> str:
        return "https://www.xpi.com.br"

    @property
    def api_url(self) -> str:
        """URL da API de produtos."""
        return "https://www.xpi.com.br/api/renda-fixa/cdb"

    async def _scrape(self) -> ScraperResult:
        """
        Coleta taxas de CDB da XP.

        A XP expõe uma API JSON com os produtos disponíveis.
        Alguns produtos requerem login, mas a listagem é pública.
        """
        result = ScraperResult(fonte=self.broker_name, url=self.api_url)

        try:
            # Tenta API principal
            taxas = await self._fetch_from_api()
            if taxas:
                result.taxas = taxas
                return result

            # Fallback: scraping HTML
            logger.info(f"[{self.broker_name}] API falhou, tentando HTML scraping")
            taxas = await self._fetch_from_html()
            result.taxas = taxas

        except Exception as e:
            logger.exception(f"[{self.broker_name}] Erro no scraping")
            result.erros.append(str(e))

        return result

    async def _fetch_from_api(self) -> list[TaxaColetada]:
        """Coleta via API JSON."""
        taxas = []

        try:
            # Headers específicos para API XP
            headers = {
                "Accept": "application/json",
                "X-Requested-With": "XMLHttpRequest",
                "Referer": "https://www.xpi.com.br/investimentos/renda-fixa/",
            }

            response = await self._fetch_with_retry(
                self.api_url,
                headers=headers,
            )

            data = response.json()

            # Estrutura esperada: {"products": [...]}
            products = data.get("products") or data.get("data") or []

            if isinstance(data, list):
                products = data

            for product in products:
                taxa = self._parse_product(product)
                if taxa:
                    taxas.append(taxa)

        except Exception as e:
            logger.debug(f"[{self.broker_name}] Falha na API: {e}")

        return taxas

    async def _fetch_from_html(self) -> list[TaxaColetada]:
        """Coleta via HTML scraping (fallback)."""
        taxas = []

        try:
            url = f"{self.base_url}/investimentos/renda-fixa/cdb"
            response = await self._fetch_with_retry(url)
            html = response.text

            # Parse básico - XP usa JavaScript para renderizar
            # Em produção, usaria Playwright para JS rendering
            # Por hora, tenta extrair dados do HTML estático

            # Procura por dados embutidos no JavaScript
            import re
            import json

            # Padrão comum: window.__INITIAL_STATE__ ou similar
            patterns = [
                r'window\.__INITIAL_STATE__\s*=\s*({.*?});',
                r'window\.initialData\s*=\s*({.*?});',
                r'"products"\s*:\s*(\[.*?\])',
            ]

            for pattern in patterns:
                match = re.search(pattern, html, re.DOTALL)
                if match:
                    try:
                        data = json.loads(match.group(1))
                        products = data if isinstance(data, list) else data.get("products", [])
                        for product in products:
                            taxa = self._parse_product(product)
                            if taxa:
                                taxas.append(taxa)
                        break
                    except json.JSONDecodeError:
                        continue

        except Exception as e:
            logger.debug(f"[{self.broker_name}] Falha no HTML scraping: {e}")

        return taxas

    def _parse_product(self, product: dict[str, Any]) -> TaxaColetada | None:
        """
        Parse de um produto da XP.

        Args:
            product: Dados do produto da API

        Returns:
            TaxaColetada ou None
        """
        try:
            # Nome do emissor
            nome = (
                product.get("issuer")
                or product.get("emissor")
                or product.get("banco")
                or product.get("name", "")
            )

            if not nome:
                return None

            # CNPJ (pode não estar disponível)
            cnpj = product.get("cnpj") or product.get("issuerCnpj")

            # Indexador
            indexador_str = (
                product.get("indexer")
                or product.get("indexador")
                or product.get("type")
                or ""
            )
            indexador = self._detect_indexador(indexador_str)

            # Taxa
            taxa_raw = (
                product.get("rate")
                or product.get("taxa")
                or product.get("rentabilidade")
                or product.get("yield")
            )
            percentual = self._parse_percentual(taxa_raw)

            if percentual is None:
                return None

            # Taxa adicional (IPCA+)
            taxa_adicional = None
            if indexador == Indexador.IPCA:
                adicional = product.get("spread") or product.get("additionalRate")
                taxa_adicional = self._parse_percentual(adicional)

            # Prazo
            prazo_raw = (
                product.get("maturity")
                or product.get("prazo")
                or product.get("daysToMaturity")
            )
            prazo = self._parse_prazo(prazo_raw)

            # Valor mínimo
            valor_raw = (
                product.get("minimumInvestment")
                or product.get("valorMinimo")
                or product.get("minValue")
            )
            valor_minimo = self._parse_valor(valor_raw)

            # Liquidez
            liquidez = product.get("dailyLiquidity") or product.get("liquidezDiaria")
            if liquidez is None:
                desc = str(product.get("description", ""))
                liquidez = "liquidez diária" in desc.lower()

            return TaxaColetada(
                instituicao_nome=str(nome),
                instituicao_cnpj=cnpj,
                indexador=indexador,
                percentual=percentual,
                taxa_adicional=taxa_adicional,
                prazo_dias=prazo,
                valor_minimo=valor_minimo,
                liquidez_diaria=bool(liquidez),
                raw_data=product,
            )

        except Exception as e:
            logger.debug(f"[{self.broker_name}] Erro ao parsear produto: {e}")
            return None


# Mock de dados para testes (quando API não disponível)
MOCK_DATA = [
    {
        "issuer": "BANCO XP",
        "cnpj": "04.902.979/0001-44",
        "indexer": "CDI",
        "rate": 102,
        "maturity": 365,
        "minimumInvestment": 1000,
        "dailyLiquidity": True,
    },
    {
        "issuer": "BANCO DAYCOVAL",
        "cnpj": "62.232.889/0001-90",
        "indexer": "CDI",
        "rate": 110,
        "maturity": 720,
        "minimumInvestment": 5000,
        "dailyLiquidity": False,
    },
    {
        "issuer": "BANCO SOFISA",
        "cnpj": "60.889.128/0001-80",
        "indexer": "IPCA",
        "rate": 100,
        "spread": 6.5,
        "maturity": 1095,
        "minimumInvestment": 1000,
        "dailyLiquidity": False,
    },
]
