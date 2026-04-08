"""
Scraper para BTG Pactual Digital.

O BTG possui uma API REST bem documentada para consulta de produtos.
Não requer autenticação para listagem pública de CDBs.
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


class BTGScraper(BaseScraper):
    """
    Scraper para BTG Pactual Digital.

    O BTG oferece CDBs próprios e de outras instituições através
    do marketplace de renda fixa. A API é relativamente estável.
    """

    @property
    def broker_name(self) -> str:
        return "btg"

    @property
    def base_url(self) -> str:
        return "https://www.btgpactualdigital.com"

    @property
    def api_url(self) -> str:
        """URL da API de produtos de renda fixa."""
        return "https://www.btgpactualdigital.com/api/v1/fixed-income/cdb"

    async def _scrape(self) -> ScraperResult:
        """Coleta taxas de CDB do BTG."""
        result = ScraperResult(fonte=self.broker_name, url=self.api_url)

        try:
            taxas = await self._fetch_products()
            result.taxas = taxas

        except Exception as e:
            logger.exception(f"[{self.broker_name}] Erro no scraping")
            result.erros.append(str(e))

        return result

    async def _fetch_products(self) -> list[TaxaColetada]:
        """Coleta produtos via API."""
        taxas = []

        try:
            headers = {
                "Accept": "application/json",
                "X-Requested-With": "XMLHttpRequest",
            }

            # BTG pode ter paginação
            page = 1
            max_pages = 10

            while page <= max_pages:
                url = f"{self.api_url}?page={page}&pageSize=50"

                response = await self._fetch_with_retry(url, headers=headers)
                data = response.json()

                products = data.get("items") or data.get("products") or data.get("data") or []

                if isinstance(data, list):
                    products = data

                if not products:
                    break

                for product in products:
                    taxa = self._parse_product(product)
                    if taxa:
                        taxas.append(taxa)

                # Verifica se há mais páginas
                total_pages = data.get("totalPages") or data.get("pages") or 1
                if page >= total_pages:
                    break

                page += 1
                await self._delay()

        except Exception as e:
            logger.debug(f"[{self.broker_name}] Falha na API: {e}")

        return taxas

    def _parse_product(self, product: dict[str, Any]) -> TaxaColetada | None:
        """Parse de um produto do BTG."""
        try:
            # Nome do emissor
            nome = (
                product.get("issuerName")
                or product.get("issuer")
                or product.get("emissor")
                or product.get("bankName")
            )

            if not nome:
                return None

            # CNPJ
            cnpj = product.get("issuerCnpj") or product.get("cnpj")

            # Indexador
            index_type = (
                product.get("indexType")
                or product.get("indexador")
                or product.get("benchmark")
                or ""
            )
            indexador = self._detect_indexador(index_type)

            # Taxa
            taxa_raw = (
                product.get("grossRate")
                or product.get("rate")
                or product.get("taxa")
                or product.get("yield")
            )
            percentual = self._parse_percentual(taxa_raw)

            if percentual is None:
                return None

            # Taxa adicional para IPCA+
            taxa_adicional = None
            if indexador == Indexador.IPCA:
                adicional = product.get("spread") or product.get("additionalRate")
                taxa_adicional = self._parse_percentual(adicional)

            # Prazo
            prazo_raw = (
                product.get("daysToMaturity")
                or product.get("maturityDays")
                or product.get("prazo")
            )
            prazo = self._parse_prazo(prazo_raw)

            # Valor mínimo
            valor_raw = (
                product.get("minimumValue")
                or product.get("minInvestment")
                or product.get("valorMinimo")
            )
            valor_minimo = self._parse_valor(valor_raw)

            # Liquidez
            liquidez = (
                product.get("hasLiquidity")
                or product.get("dailyLiquidity")
                or product.get("liquidezDiaria")
            )

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


# Mock de dados para testes
MOCK_DATA = [
    {
        "issuerName": "BTG PACTUAL",
        "issuerCnpj": "30.306.294/0001-45",
        "indexType": "CDI",
        "grossRate": 103,
        "daysToMaturity": 365,
        "minimumValue": 500,
        "hasLiquidity": True,
    },
    {
        "issuerName": "BANCO PINE",
        "issuerCnpj": "62.144.175/0001-20",
        "indexType": "CDI",
        "grossRate": 115,
        "daysToMaturity": 1080,
        "minimumValue": 10000,
        "hasLiquidity": False,
    },
]
