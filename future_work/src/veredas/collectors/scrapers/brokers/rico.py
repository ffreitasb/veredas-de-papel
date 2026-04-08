"""
Scraper para Rico Investimentos.

A Rico é uma corretora do grupo XP, mas possui plataforma própria.
Usa JavaScript rendering pesado, pode requerer Playwright.
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


class RicoScraper(BaseScraper):
    """
    Scraper para Rico Investimentos.

    A Rico é do grupo XP mas tem catálogo próprio de produtos.
    Usa bastante JavaScript, então a API é preferida quando disponível.
    """

    @property
    def broker_name(self) -> str:
        return "rico"

    @property
    def base_url(self) -> str:
        return "https://www.rico.com.vc"

    @property
    def api_url(self) -> str:
        """URL da API de renda fixa."""
        return "https://www.rico.com.vc/api/renda-fixa/produtos"

    async def _scrape(self) -> ScraperResult:
        """Coleta taxas de CDB da Rico."""
        result = ScraperResult(fonte=self.broker_name, url=self.api_url)

        try:
            # Tenta API primeiro
            taxas = await self._fetch_from_api()

            if not taxas:
                # Fallback para scraping direto
                logger.info(f"[{self.broker_name}] API falhou, tentando scraping direto")
                taxas = await self._fetch_from_page()

            result.taxas = taxas

        except Exception as e:
            logger.exception(f"[{self.broker_name}] Erro no scraping")
            result.erros.append(str(e))

        return result

    async def _fetch_from_api(self) -> list[TaxaColetada]:
        """Coleta via API JSON."""
        taxas = []

        try:
            headers = {
                "Accept": "application/json",
                "X-Requested-With": "XMLHttpRequest",
                "Referer": f"{self.base_url}/investimentos/renda-fixa/",
            }

            # Rico pode ter endpoint específico para CDB
            endpoints = [
                f"{self.api_url}?tipo=cdb",
                f"{self.api_url}/cdb",
                self.api_url,
            ]

            for endpoint in endpoints:
                try:
                    response = await self._fetch_with_retry(endpoint, headers=headers)
                    data = response.json()

                    products = (
                        data.get("produtos")
                        or data.get("products")
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
        """Coleta via scraping de página HTML."""
        taxas = []

        try:
            url = f"{self.base_url}/investimentos/renda-fixa/cdb"
            response = await self._fetch_with_retry(url)
            html = response.text

            # Tenta extrair dados de scripts JSON embutidos
            import re
            import json

            # Rico pode usar diferentes padrões de dados
            patterns = [
                r'window\.__PRELOADED_STATE__\s*=\s*({.*?});',
                r'window\.pageData\s*=\s*({.*?});',
                r'"investmentProducts"\s*:\s*(\[.*?\])',
                r'data-products=\'(\[.*?\])\'',
            ]

            for pattern in patterns:
                match = re.search(pattern, html, re.DOTALL)
                if match:
                    try:
                        raw_data = match.group(1)
                        # Limpa caracteres de escape
                        raw_data = raw_data.replace("\\'", "'")
                        data = json.loads(raw_data)

                        products = data if isinstance(data, list) else []
                        if isinstance(data, dict):
                            products = (
                                data.get("products")
                                or data.get("investmentProducts")
                                or []
                            )

                        for product in products:
                            taxa = self._parse_product(product)
                            if taxa:
                                taxas.append(taxa)

                        if taxas:
                            break

                    except json.JSONDecodeError:
                        continue

        except Exception as e:
            logger.debug(f"[{self.broker_name}] Falha no scraping HTML: {e}")

        return taxas

    def _parse_product(self, product: dict[str, Any]) -> TaxaColetada | None:
        """Parse de um produto da Rico."""
        try:
            # Nome do emissor
            nome = (
                product.get("emissor")
                or product.get("issuer")
                or product.get("banco")
                or product.get("nome")
            )

            if not nome:
                return None

            # CNPJ
            cnpj = product.get("cnpj") or product.get("cnpjEmissor")

            # Indexador
            index_str = (
                product.get("indexador")
                or product.get("indice")
                or product.get("benchmark")
                or ""
            )
            indexador = self._detect_indexador(index_str)

            # Taxa
            taxa_raw = (
                product.get("rentabilidade")
                or product.get("taxa")
                or product.get("percentual")
                or product.get("rate")
            )
            percentual = self._parse_percentual(taxa_raw)

            if percentual is None:
                return None

            # Taxa adicional
            taxa_adicional = None
            if indexador == Indexador.IPCA:
                adicional = product.get("taxaAdicional") or product.get("spread")
                taxa_adicional = self._parse_percentual(adicional)

            # Prazo
            prazo_raw = (
                product.get("prazo")
                or product.get("diasVencimento")
                or product.get("maturity")
            )
            prazo = self._parse_prazo(prazo_raw)

            # Valor mínimo
            valor_raw = (
                product.get("valorMinimo")
                or product.get("aplicacaoMinima")
                or product.get("minValue")
            )
            valor_minimo = self._parse_valor(valor_raw)

            # Liquidez
            liquidez = product.get("liquidezDiaria") or product.get("temLiquidez")

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
        "emissor": "BANCO BMG",
        "cnpj": "61.186.680/0001-74",
        "indexador": "CDI",
        "rentabilidade": 108,
        "prazo": 540,
        "valorMinimo": 1000,
        "liquidezDiaria": False,
    },
    {
        "emissor": "BANCO ORIGINAL",
        "cnpj": "01.181.521/0001-55",
        "indexador": "CDI",
        "rentabilidade": 105,
        "prazo": 365,
        "valorMinimo": 500,
        "liquidezDiaria": True,
    },
]
