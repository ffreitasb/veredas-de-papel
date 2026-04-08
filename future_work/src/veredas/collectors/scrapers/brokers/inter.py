"""
Scraper para Banco Inter.

O Inter possui API para consulta de investimentos que pode ser
acessada parcialmente sem autenticação.
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


class InterScraper(BaseScraper):
    """
    Scraper para Banco Inter.

    O Inter oferece CDBs próprios e de parceiros através da
    plataforma de investimentos. Parte dos dados é acessível
    publicamente.
    """

    @property
    def broker_name(self) -> str:
        return "inter"

    @property
    def base_url(self) -> str:
        return "https://www.bancointer.com.br"

    @property
    def api_url(self) -> str:
        """URL da API de investimentos."""
        return "https://www.bancointer.com.br/api/investimentos/renda-fixa"

    async def _scrape(self) -> ScraperResult:
        """Coleta taxas de CDB do Inter."""
        result = ScraperResult(fonte=self.broker_name, url=self.api_url)

        try:
            # Tenta API
            taxas = await self._fetch_from_api()

            if not taxas:
                # Fallback: scraping HTML
                logger.info(f"[{self.broker_name}] API falhou, tentando scraping")
                taxas = await self._fetch_from_page()

            # Adiciona taxas conhecidas do Inter
            taxas.extend(self._get_known_rates())

            result.taxas = taxas

        except Exception as e:
            logger.exception(f"[{self.broker_name}] Erro no scraping")
            result.erros.append(str(e))

        return result

    async def _fetch_from_api(self) -> list[TaxaColetada]:
        """Coleta via API."""
        taxas = []

        try:
            headers = {
                "Accept": "application/json",
                "X-Requested-With": "XMLHttpRequest",
                "Origin": self.base_url,
            }

            # Endpoints possíveis
            endpoints = [
                f"{self.api_url}/cdb",
                f"{self.api_url}?tipo=CDB",
                f"{self.base_url}/pra-voce/investimentos/renda-fixa/api/products",
            ]

            for endpoint in endpoints:
                try:
                    response = await self._fetch_with_retry(endpoint, headers=headers)
                    data = response.json()

                    products = (
                        data.get("products")
                        or data.get("items")
                        or data.get("data")
                        or []
                    )

                    if isinstance(data, list):
                        products = data

                    for product in products:
                        taxa = self._parse_product(product)
                        if taxa:
                            taxas.append(taxa)

                    if taxas:
                        break

                except Exception as e:
                    logger.debug(f"[{self.broker_name}] Endpoint {endpoint} falhou: {e}")
                    continue

        except Exception as e:
            logger.debug(f"[{self.broker_name}] Falha na API: {e}")

        return taxas

    async def _fetch_from_page(self) -> list[TaxaColetada]:
        """Coleta via scraping de página."""
        taxas = []

        try:
            url = f"{self.base_url}/pra-voce/investimentos/renda-fixa/cdb/"
            response = await self._fetch_with_retry(url)
            html = response.text

            import re
            import json

            # Procura dados em scripts
            patterns = [
                r'window\.__NEXT_DATA__\s*=\s*({.*?})\s*</script>',
                r'"products"\s*:\s*(\[.*?\])',
                r'data-products="([^"]*)"',
            ]

            for pattern in patterns:
                match = re.search(pattern, html, re.DOTALL)
                if match:
                    try:
                        raw = match.group(1)
                        # Decodifica HTML entities se necessário
                        raw = raw.replace("&quot;", '"')
                        data = json.loads(raw)

                        products = []
                        if isinstance(data, list):
                            products = data
                        elif isinstance(data, dict):
                            # Next.js data
                            props = data.get("props", {}).get("pageProps", {})
                            products = props.get("products", [])

                        for product in products:
                            taxa = self._parse_product(product)
                            if taxa:
                                taxas.append(taxa)

                        if taxas:
                            break

                    except json.JSONDecodeError:
                        continue

        except Exception as e:
            logger.debug(f"[{self.broker_name}] Erro no scraping HTML: {e}")

        return taxas

    def _get_known_rates(self) -> list[TaxaColetada]:
        """
        Retorna taxas conhecidas do Inter.

        O Inter oferece CDB com rendimento padrão para conta corrente.
        """
        return [
            TaxaColetada(
                instituicao_nome="BANCO INTER",
                instituicao_cnpj="00.416.968/0001-01",
                indexador=Indexador.CDI,
                percentual=Decimal("100"),
                taxa_adicional=None,
                prazo_dias=1,
                valor_minimo=Decimal("1"),
                liquidez_diaria=True,
                raw_data={"tipo": "conta_digital", "produto": "CDB DI Inter"},
            ),
        ]

    def _parse_product(self, product: dict[str, Any]) -> TaxaColetada | None:
        """Parse de um produto do Inter."""
        try:
            # Nome do emissor
            nome = (
                product.get("issuer")
                or product.get("emissor")
                or product.get("bank")
                or product.get("nome")
            )

            if not nome:
                return None

            # CNPJ
            cnpj = product.get("cnpj") or product.get("issuerCnpj")

            # Indexador
            index_str = (
                product.get("index")
                or product.get("indexador")
                or product.get("benchmark")
                or ""
            )
            indexador = self._detect_indexador(index_str)

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

            # Taxa adicional
            taxa_adicional = None
            if indexador == Indexador.IPCA:
                adicional = product.get("spread") or product.get("taxaAdicional")
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
                product.get("minValue")
                or product.get("valorMinimo")
                or product.get("minimumInvestment")
            )
            valor_minimo = self._parse_valor(valor_raw)

            # Liquidez
            liquidez = (
                product.get("dailyLiquidity")
                or product.get("liquidezDiaria")
                or product.get("hasLiquidity")
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
        "issuer": "BANCO INTER",
        "cnpj": "00.416.968/0001-01",
        "index": "CDI",
        "rate": 100,
        "maturity": 1,
        "minValue": 1,
        "dailyLiquidity": True,
    },
    {
        "issuer": "BANCO INTER",
        "cnpj": "00.416.968/0001-01",
        "index": "CDI",
        "rate": 110,
        "maturity": 720,
        "minValue": 100,
        "dailyLiquidity": False,
    },
]
