"""
Cliente para API de dados de mercado da B3.

A B3 oferece dados de mercado secundário através de:
1. API Market Data (requer credenciais)
2. Arquivos públicos no site da B3
3. Sistema CETIP (para títulos privados)

Este módulo implementa coleta de dados públicos disponíveis.
"""

import asyncio
import logging
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import Any, Optional

import httpx

# H12 FIX: Feriados nacionais brasileiros e fechamentos da B3
# Feriados fixos (mês, dia)
FERIADOS_FIXOS: set[tuple[int, int]] = {
    (1, 1),    # Confraternização Universal
    (4, 21),   # Tiradentes
    (5, 1),    # Dia do Trabalho
    (9, 7),    # Independência do Brasil
    (10, 12),  # Nossa Senhora Aparecida
    (11, 2),   # Finados
    (11, 15),  # Proclamação da República
    (12, 25),  # Natal
}

# Feriados móveis por ano (calculados/conhecidos)
# Formato: {ano: [(mês, dia), ...]}
FERIADOS_MOVEIS: dict[int, list[tuple[int, int]]] = {
    2024: [
        (2, 12), (2, 13),  # Carnaval
        (3, 29),           # Sexta-feira Santa
        (5, 30),           # Corpus Christi
        (11, 20),          # Consciência Negra (se aplicável)
    ],
    2025: [
        (3, 3), (3, 4),    # Carnaval
        (4, 18),           # Sexta-feira Santa
        (6, 19),           # Corpus Christi
        (11, 20),          # Consciência Negra
    ],
    2026: [
        (2, 16), (2, 17),  # Carnaval
        (4, 3),            # Sexta-feira Santa
        (6, 4),            # Corpus Christi
        (11, 20),          # Consciência Negra
    ],
}


def eh_feriado(data: date) -> bool:
    """
    Verifica se uma data é feriado nacional ou fechamento da B3.

    Args:
        data: Data a verificar

    Returns:
        True se for feriado
    """
    # Verifica feriados fixos
    if (data.month, data.day) in FERIADOS_FIXOS:
        return True

    # Verifica feriados móveis do ano
    feriados_ano = FERIADOS_MOVEIS.get(data.year, [])
    if (data.month, data.day) in feriados_ano:
        return True

    return False

from veredas import TZ_BRASIL
from veredas.collectors.base import BaseCollector, CollectionResult
from veredas.collectors.b3.models import (
    NegociacaoB3,
    PrecoSecundario,
    ResumoMercadoSecundario,
    TipoTitulo,
)
from veredas.collectors.b3.parser import B3DataParser

logger = logging.getLogger(__name__)


@dataclass
class B3Config:
    """Configuração para acesso à B3."""

    # URLs públicas
    base_url: str = "https://www.b3.com.br"
    market_data_url: str = "https://arquivos.b3.com.br/apinegociacao"

    # Credenciais (opcional - para API completa)
    api_key: Optional[str] = None
    api_secret: Optional[str] = None

    # Rate limiting
    request_delay: float = 2.0
    max_retries: int = 3
    timeout: int = 60


class B3MarketDataCollector(BaseCollector):
    """
    Coletor de dados de mercado secundário da B3.

    Coleta:
    - Preços de negociação de títulos de renda fixa
    - Volume e quantidade de negócios
    - Taxas implícitas nas negociações
    """

    def __init__(self, config: Optional[B3Config] = None):
        """
        Inicializa o coletor.

        Args:
            config: Configuração opcional
        """
        self.config = config or B3Config()
        self.parser = B3DataParser()
        self._client: Optional[httpx.AsyncClient] = None
        self._client_lock = asyncio.Lock()  # Prevents race condition in _get_client

    @property
    def source_name(self) -> str:
        return "b3_market_data"

    async def _get_client(self) -> httpx.AsyncClient:
        """Retorna cliente HTTP (thread-safe)."""
        async with self._client_lock:
            if self._client is None or self._client.is_closed:
                # L1 FIX: User agent atualizado
                headers = {
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/131.0.0.0",
                    "Accept": "application/json, text/html, */*",
                    "Accept-Language": "pt-BR,pt;q=0.9",
                }
                self._client = httpx.AsyncClient(
                    timeout=self.config.timeout,
                    headers=headers,
                    follow_redirects=True,
                )
            return self._client

    async def _close_client(self) -> None:
        """Fecha cliente HTTP."""
        if self._client and not self._client.is_closed:
            await self._client.aclose()
            self._client = None

    async def collect(self) -> CollectionResult[list[PrecoSecundario]]:
        """
        Coleta dados do mercado secundário.

        Returns:
            CollectionResult com lista de PrecoSecundario
        """
        try:
            # Coleta dados do dia útil mais recente
            precos = await self.coletar_precos_dia()

            if precos:
                logger.info(f"[{self.source_name}] Coletados {len(precos)} preços")
                return CollectionResult.ok(
                    data=precos,
                    source=self.source_name,
                    raw_response={"count": len(precos)},
                )
            else:
                return CollectionResult.fail(
                    error="Nenhum dado disponível",
                    source=self.source_name,
                )

        except Exception as e:
            logger.exception(f"[{self.source_name}] Erro na coleta")
            return CollectionResult.fail(
                error=str(e),
                source=self.source_name,
            )
        finally:
            await self._close_client()

    async def health_check(self) -> bool:
        """Verifica se a B3 está acessível."""
        try:
            client = await self._get_client()
            response = await client.get(self.config.base_url, timeout=10)
            await self._close_client()
            return response.status_code < 500
        except Exception:
            await self._close_client()
            return False

    async def coletar_precos_dia(
        self,
        data: Optional[date] = None,
    ) -> list[PrecoSecundario]:
        """
        Coleta preços do mercado secundário para uma data.

        Args:
            data: Data de referência (default: último dia útil)

        Returns:
            Lista de PrecoSecundario
        """
        if data is None:
            data = self._ultimo_dia_util()

        precos = []

        try:
            # Tenta API de arquivos públicos
            precos = await self._coletar_arquivo_publico(data)

            if not precos:
                # Fallback: scraping da página
                precos = await self._coletar_via_scraping(data)

        except Exception as e:
            logger.error(f"[{self.source_name}] Erro ao coletar preços: {e}")

        return precos

    async def _coletar_arquivo_publico(
        self,
        data: date,
    ) -> list[PrecoSecundario]:
        """
        Coleta dados do arquivo público da B3.

        A B3 disponibiliza arquivos diários com dados de negociação.
        """
        precos = []

        try:
            # Formato da URL do arquivo
            data_str = data.strftime("%Y%m%d")
            urls = [
                f"{self.config.market_data_url}/renda-fixa/{data_str}",
                f"{self.config.base_url}/pt_br/market-data-e-indices/servicos-de-dados/market-data/consultas/mercado-de-balcao/dados-publicos/titulos-privados/{data_str}",
            ]

            client = await self._get_client()

            for url in urls:
                try:
                    response = await client.get(url)

                    if response.status_code == 200:
                        content_type = response.headers.get("content-type", "")

                        if "json" in content_type:
                            data_json = response.json()
                            precos = self.parser.parse_json_response(data_json, data)
                        elif "text" in content_type or "csv" in content_type:
                            precos = self.parser.parse_csv_response(response.text, data)

                        if precos:
                            break

                except Exception as e:
                    logger.debug(f"[{self.source_name}] Falha em {url}: {e}")
                    continue

                await asyncio.sleep(self.config.request_delay)

        except Exception as e:
            logger.error(f"[{self.source_name}] Erro no arquivo público: {e}")

        return precos

    async def _coletar_via_scraping(
        self,
        data: date,
    ) -> list[PrecoSecundario]:
        """
        Coleta dados via scraping da página da B3.

        Fallback quando arquivos não estão disponíveis.
        """
        precos = []

        try:
            # Página de consulta de títulos privados
            url = f"{self.config.base_url}/pt_br/market-data-e-indices/servicos-de-dados/market-data/consultas/mercado-de-balcao/titulos-privados"

            client = await self._get_client()
            response = await client.get(url)

            if response.status_code == 200:
                html = response.text
                precos = self.parser.parse_html_page(html, data)

        except Exception as e:
            logger.error(f"[{self.source_name}] Erro no scraping: {e}")

        return precos

    async def coletar_historico(
        self,
        cnpj: str,
        dias: int = 30,
    ) -> list[PrecoSecundario]:
        """
        Coleta histórico de preços para uma instituição.

        Args:
            cnpj: CNPJ da instituição
            dias: Número de dias de histórico

        Returns:
            Lista de PrecoSecundario ordenada por data
        """
        precos = []
        data_fim = date.today()
        data_inicio = data_fim - timedelta(days=dias)

        current = data_inicio
        while current <= data_fim:
            if self._eh_dia_util(current):
                try:
                    precos_dia = await self.coletar_precos_dia(current)
                    # Filtra por CNPJ
                    precos_if = [p for p in precos_dia if p.emissor_cnpj == cnpj]
                    precos.extend(precos_if)

                    await asyncio.sleep(self.config.request_delay)

                except Exception as e:
                    logger.warning(f"[{self.source_name}] Erro em {current}: {e}")

            current += timedelta(days=1)

        return sorted(precos, key=lambda p: p.data_referencia)

    async def obter_resumo_mercado(
        self,
        data: Optional[date] = None,
    ) -> ResumoMercadoSecundario:
        """
        Obtém resumo consolidado do mercado secundário.

        Args:
            data: Data de referência

        Returns:
            ResumoMercadoSecundario
        """
        if data is None:
            data = self._ultimo_dia_util()

        precos = await self.coletar_precos_dia(data)

        # Agrupa por tipo
        por_tipo: dict[TipoTitulo, int] = {}
        for preco in precos:
            tipo = preco.tipo_titulo
            por_tipo[tipo] = por_tipo.get(tipo, 0) + 1

        # Identifica maiores movimentos
        precos_com_variacao = [p for p in precos if p.variacao_dia is not None]
        precos_ordenados = sorted(
            precos_com_variacao,
            key=lambda p: p.variacao_dia or Decimal("0"),
        )

        maiores_quedas = precos_ordenados[:10]  # 10 maiores quedas
        maiores_altas = precos_ordenados[-10:][::-1]  # 10 maiores altas

        return ResumoMercadoSecundario(
            data_referencia=data,
            total_titulos_negociados=len(precos),
            total_negocios=sum(p.quantidade_negocios for p in precos),
            valor_financeiro_total=sum(p.valor_financeiro for p in precos),
            titulos_por_tipo=por_tipo,
            maiores_quedas=maiores_quedas,
            maiores_altas=maiores_altas,
        )

    def _ultimo_dia_util(self) -> date:
        """Retorna o último dia útil (considerando feriados)."""
        data = date.today() - timedelta(days=1)

        # Retrocede até encontrar um dia útil
        while not self._eh_dia_util(data):
            data -= timedelta(days=1)

        return data

    def _eh_dia_util(self, data: date) -> bool:
        """Verifica se é dia útil (considera fins de semana e feriados)."""
        # Fins de semana
        if data.weekday() >= 5:
            return False

        # Feriados
        if eh_feriado(data):
            return False

        return True


# Dados mock para testes
MOCK_PRECOS = [
    PrecoSecundario(
        codigo_titulo="CDB123456",
        emissor_cnpj="00.000.000/0001-91",
        emissor_nome="BANCO DO BRASIL",
        tipo_titulo=TipoTitulo.CDB,
        data_referencia=date.today(),
        pu_abertura=Decimal("980.50"),
        pu_fechamento=Decimal("975.20"),
        pu_minimo=Decimal("972.00"),
        pu_maximo=Decimal("985.00"),
        pu_medio=Decimal("978.50"),
        quantidade_negocios=15,
        quantidade_titulos=1500,
        valor_financeiro=Decimal("1467750.00"),
        taxa_minima=Decimal("102.5"),
        taxa_maxima=Decimal("105.0"),
        taxa_media=Decimal("103.5"),
        variacao_dia=Decimal("-0.54"),
    ),
]
