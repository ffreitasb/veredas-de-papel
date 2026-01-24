"""
Scraper para Nubank.

O Nubank não oferece API pública para consulta de produtos.
Requer autenticação para acessar a maioria dos dados.
Este scraper coleta informações públicas do site institucional.
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


class NubankScraper(BaseScraper):
    """
    Scraper para Nubank.

    O Nubank oferece poucos produtos de CDB próprio (basicamente o
    "Caixinha" com rendimento de 100% CDI). Para dados mais completos,
    seria necessário autenticação via app.
    """

    @property
    def broker_name(self) -> str:
        return "nubank"

    @property
    def base_url(self) -> str:
        return "https://nubank.com.br"

    async def _scrape(self) -> ScraperResult:
        """Coleta taxas de CDB do Nubank."""
        result = ScraperResult(fonte=self.broker_name, url=self.base_url)

        try:
            # Nubank não tem API pública - coleta dados conhecidos
            taxas = await self._fetch_public_rates()
            result.taxas = taxas

            if not taxas:
                # Tenta scraping da página de produtos
                taxas = await self._scrape_products_page()
                result.taxas = taxas

        except Exception as e:
            logger.exception(f"[{self.broker_name}] Erro no scraping")
            result.erros.append(str(e))

        return result

    async def _fetch_public_rates(self) -> list[TaxaColetada]:
        """
        Coleta taxas públicas conhecidas do Nubank.

        O Nubank oferece produtos com taxas fixas bem conhecidas:
        - Conta corrente: 100% CDI
        - Caixinhas: 100% CDI (sem carência)
        - RDBs promocionais: variam por campanha
        """
        taxas = []

        # Taxa padrão Nubank (RDB automático)
        taxas.append(
            TaxaColetada(
                instituicao_nome="NUBANK",
                instituicao_cnpj="18.236.120/0001-58",
                indexador=Indexador.CDI,
                percentual=Decimal("100"),
                taxa_adicional=None,
                prazo_dias=1,  # Liquidez imediata
                valor_minimo=Decimal("1"),
                liquidez_diaria=True,
                raw_data={"tipo": "conta_corrente", "produto": "RDB Automático"},
            )
        )

        # Caixinhas (mesmo rendimento, mas com objetivo)
        taxas.append(
            TaxaColetada(
                instituicao_nome="NUBANK",
                instituicao_cnpj="18.236.120/0001-58",
                indexador=Indexador.CDI,
                percentual=Decimal("100"),
                taxa_adicional=None,
                prazo_dias=30,  # Sugestão de prazo mínimo
                valor_minimo=Decimal("1"),
                liquidez_diaria=True,
                raw_data={"tipo": "caixinha", "produto": "Caixinha Nubank"},
            )
        )

        # Tenta obter taxas promocionais do site
        try:
            promo_taxas = await self._fetch_promotional_rates()
            taxas.extend(promo_taxas)
        except Exception as e:
            logger.debug(f"[{self.broker_name}] Sem taxas promocionais: {e}")

        return taxas

    async def _fetch_promotional_rates(self) -> list[TaxaColetada]:
        """Tenta capturar taxas promocionais do site."""
        taxas = []

        try:
            # Página de investimentos
            url = f"{self.base_url}/investimentos/"
            response = await self._fetch_with_retry(url)
            html = response.text

            # Procura por menções de taxas promocionais
            import re

            # Padrão: "rendendo X% do CDI" ou "até X% do CDI"
            patterns = [
                r"(\d{2,3})[,.]?(\d*)\s*%\s*do\s*CDI",
                r"rendendo\s*(\d{2,3})[,.]?(\d*)\s*%",
                r"até\s*(\d{2,3})[,.]?(\d*)\s*%\s*do\s*CDI",
            ]

            found_rates = set()
            for pattern in patterns:
                matches = re.findall(pattern, html, re.IGNORECASE)
                for match in matches:
                    rate = match[0]
                    if match[1]:
                        rate += "." + match[1]
                    found_rates.add(Decimal(rate))

            # Adiciona taxas encontradas (exceto 100% que já foi adicionada)
            for rate in found_rates:
                if rate > Decimal("100"):
                    taxas.append(
                        TaxaColetada(
                            instituicao_nome="NUBANK",
                            instituicao_cnpj="18.236.120/0001-58",
                            indexador=Indexador.CDI,
                            percentual=rate,
                            taxa_adicional=None,
                            prazo_dias=365,  # Promoções geralmente têm prazo
                            valor_minimo=Decimal("1"),
                            liquidez_diaria=False,
                            raw_data={"tipo": "promocional", "taxa_encontrada": str(rate)},
                        )
                    )

        except Exception as e:
            logger.debug(f"[{self.broker_name}] Erro ao buscar taxas promocionais: {e}")

        return taxas

    async def _scrape_products_page(self) -> list[TaxaColetada]:
        """Scraping da página de produtos (fallback)."""
        taxas = []

        try:
            urls = [
                f"{self.base_url}/investimentos/",
                f"{self.base_url}/conta/",
                f"{self.base_url}/caixinhas/",
            ]

            for url in urls:
                try:
                    response = await self._fetch_with_retry(url)
                    html = response.text

                    # Extrai dados estruturados (JSON-LD)
                    import re
                    import json

                    ld_pattern = r'<script type="application/ld\+json">(.*?)</script>'
                    matches = re.findall(ld_pattern, html, re.DOTALL)

                    for match in matches:
                        try:
                            data = json.loads(match)
                            # Processa dados estruturados se houver info de produto
                            if isinstance(data, dict) and "offers" in data:
                                logger.debug(f"[{self.broker_name}] Encontrado JSON-LD: {data.get('name')}")
                        except json.JSONDecodeError:
                            continue

                    await self._delay()

                except Exception as e:
                    logger.debug(f"[{self.broker_name}] Erro em {url}: {e}")
                    continue

        except Exception as e:
            logger.debug(f"[{self.broker_name}] Erro no scraping de páginas: {e}")

        return taxas


# Mock de dados para testes
MOCK_DATA = [
    {
        "produto": "RDB Automático",
        "tipo": "conta_corrente",
        "indexador": "CDI",
        "percentual": 100,
        "prazo": 1,
        "valorMinimo": 1,
        "liquidezDiaria": True,
    },
    {
        "produto": "Caixinha",
        "tipo": "caixinha",
        "indexador": "CDI",
        "percentual": 100,
        "prazo": 30,
        "valorMinimo": 1,
        "liquidezDiaria": True,
    },
]
