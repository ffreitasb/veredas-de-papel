"""
Coletor de processos administrativos do Banco Central.

Coleta informações sobre processos administrativos, multas e
sanções aplicadas pelo BC a instituições financeiras.
"""

import asyncio
import logging
import re
from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal
from enum import Enum
from typing import Any, Optional

import httpx

from veredas import TZ_BRASIL
from veredas.collectors.base import BaseCollector, CollectionResult

logger = logging.getLogger(__name__)


class TipoProcesso(str, Enum):
    """Tipos de processos do BC."""

    ADMINISTRATIVO_SANCIONADOR = "PAS"
    MULTA = "MULTA"
    ADVERTENCIA = "ADVERTENCIA"
    INTERVENCAO = "INTERVENCAO"
    LIQUIDACAO = "LIQUIDACAO"
    RAET = "RAET"  # Regime de Administração Especial Temporária
    OUTROS = "OUTROS"


class StatusProcesso(str, Enum):
    """Status do processo."""

    ABERTO = "ABERTO"
    EM_ANDAMENTO = "EM_ANDAMENTO"
    JULGADO = "JULGADO"
    ARQUIVADO = "ARQUIVADO"
    RECURSO = "RECURSO"


@dataclass
class ProcessoBC:
    """Processo administrativo do Banco Central."""

    numero: str
    tipo: TipoProcesso
    status: StatusProcesso

    # Instituição
    instituicao_cnpj: str
    instituicao_nome: str

    # Datas
    data_abertura: date
    data_julgamento: Optional[date] = None
    data_transito_julgado: Optional[date] = None

    # Penalidade
    penalidade: Optional[str] = None
    valor_multa: Optional[Decimal] = None

    # Descrição
    descricao: Optional[str] = None
    fundamentacao: Optional[str] = None

    # Metadata
    url_fonte: Optional[str] = None
    coletado_em: datetime = field(default_factory=lambda: datetime.now(TZ_BRASIL))

    @property
    def eh_grave(self) -> bool:
        """Verifica se é um processo grave."""
        tipos_graves = {
            TipoProcesso.INTERVENCAO,
            TipoProcesso.LIQUIDACAO,
            TipoProcesso.RAET,
        }
        return self.tipo in tipos_graves

    @property
    def valor_multa_significativo(self) -> bool:
        """Verifica se a multa é significativa (> R$ 1M)."""
        return self.valor_multa is not None and self.valor_multa > Decimal("1000000")


@dataclass
class HistoricoProcessosIF:
    """Histórico de processos de uma instituição."""

    cnpj: str
    nome: str

    # Totais
    total_processos: int = 0
    processos_abertos: int = 0
    processos_julgados: int = 0

    # Por tipo
    total_multas: int = 0
    total_advertencias: int = 0
    total_intervencoes: int = 0

    # Valores
    valor_total_multas: Decimal = Decimal("0")
    maior_multa: Decimal = Decimal("0")

    # Lista de processos
    processos: list[ProcessoBC] = field(default_factory=list)

    # Período
    periodo_inicio: date = field(default_factory=date.today)
    periodo_fim: date = field(default_factory=date.today)

    # Metadata
    coletado_em: datetime = field(default_factory=lambda: datetime.now(TZ_BRASIL))

    @property
    def tem_historico_grave(self) -> bool:
        """Verifica se tem histórico grave (intervenções/liquidações)."""
        return self.total_intervencoes > 0

    @property
    def score_risco(self) -> Decimal:
        """
        Score de risco baseado em processos.

        0 = baixo risco, 100 = alto risco
        """
        risco = Decimal("0")

        # Processos abertos
        risco += Decimal(self.processos_abertos) * 5

        # Intervenções
        risco += Decimal(self.total_intervencoes) * 30

        # Volume de multas
        if self.valor_total_multas > Decimal("10000000"):  # > 10M
            risco += Decimal("20")
        elif self.valor_total_multas > Decimal("1000000"):  # > 1M
            risco += Decimal("10")

        # Frequência (mais de 5 processos = preocupante)
        if self.total_processos > 10:
            risco += Decimal("15")
        elif self.total_processos > 5:
            risco += Decimal("10")

        return min(Decimal("100"), risco)


class BacenProcessosCollector(BaseCollector):
    """
    Coletor de processos do Banco Central.

    Coleta dados de processos administrativos do BC através
    de APIs públicas e página de dados abertos.
    """

    # URLs do BC
    BASE_URL = "https://www.bcb.gov.br"
    DADOS_ABERTOS_URL = "https://olinda.bcb.gov.br/olinda/servico"
    API_IF_URL = "https://olinda.bcb.gov.br/olinda/servico/selic/versao/v1/odata"

    def __init__(self, timeout: int = 60, max_retries: int = 3):
        """Inicializa o coletor."""
        self.timeout = timeout
        self.max_retries = max_retries
        self._client: Optional[httpx.AsyncClient] = None

    @property
    def source_name(self) -> str:
        return "bacen_processos"

    async def _get_client(self) -> httpx.AsyncClient:
        """Retorna cliente HTTP."""
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                timeout=self.timeout,
                headers={
                    "User-Agent": "Mozilla/5.0 veredas-de-papel/1.0",
                    "Accept": "application/json",
                },
                follow_redirects=True,
            )
        return self._client

    async def _close_client(self) -> None:
        """Fecha cliente HTTP."""
        if self._client and not self._client.is_closed:
            await self._client.aclose()
            self._client = None

    async def collect(self) -> CollectionResult[list[HistoricoProcessosIF]]:
        """
        Coleta histórico de processos das principais IFs.

        Returns:
            CollectionResult com lista de HistoricoProcessosIF
        """
        try:
            # CNPJs das principais IFs
            cnpjs = [
                "00.000.000/0001-91",  # BB
                "60.746.948/0001-12",  # Bradesco
                "60.701.190/0001-04",  # Itau
                "33.657.248/0001-89",  # Santander
                "00.360.305/0001-04",  # Caixa
                "30.306.294/0001-45",  # BTG
                "04.902.979/0001-44",  # XP
                "18.236.120/0001-58",  # Nubank
                "00.416.968/0001-01",  # Inter
            ]

            historicos = []

            for cnpj in cnpjs:
                try:
                    historico = await self.coletar_historico_if(cnpj)
                    if historico:
                        historicos.append(historico)
                    await asyncio.sleep(1)  # Rate limiting
                except Exception as e:
                    logger.warning(f"[{self.source_name}] Erro ao coletar {cnpj}: {e}")

            if historicos:
                return CollectionResult.ok(
                    data=historicos,
                    source=self.source_name,
                    raw_response={"count": len(historicos)},
                )
            else:
                return CollectionResult.fail(
                    error="Nenhum histórico coletado",
                    source=self.source_name,
                )

        except Exception as e:
            logger.exception(f"[{self.source_name}] Erro na coleta")
            return CollectionResult.fail(error=str(e), source=self.source_name)
        finally:
            await self._close_client()

    async def health_check(self) -> bool:
        """Verifica se o BC está acessível."""
        try:
            client = await self._get_client()
            response = await client.get(self.BASE_URL, timeout=10)
            await self._close_client()
            return response.status_code < 500
        except Exception:
            await self._close_client()
            return False

    async def coletar_historico_if(
        self,
        cnpj: str,
        anos: int = 5,
    ) -> Optional[HistoricoProcessosIF]:
        """
        Coleta histórico de processos de uma IF.

        Args:
            cnpj: CNPJ da instituição
            anos: Anos de histórico

        Returns:
            HistoricoProcessosIF ou None
        """
        try:
            # Normaliza CNPJ
            cnpj_limpo = re.sub(r"\D", "", cnpj)

            # Tenta API de dados abertos
            processos = await self._buscar_processos_api(cnpj_limpo)

            if not processos:
                # Fallback: scraping de página de penalidades
                processos = await self._buscar_processos_scraping(cnpj_limpo)

            # Consolida histórico
            return self._consolidar_historico(cnpj, processos, anos)

        except Exception as e:
            logger.error(f"[{self.source_name}] Erro ao coletar histórico: {e}")
            return None

    async def _buscar_processos_api(
        self,
        cnpj: str,
    ) -> list[ProcessoBC]:
        """Busca processos via API de dados abertos."""
        processos = []

        try:
            client = await self._get_client()

            # Endpoint de penalidades aplicadas
            url = f"{self.DADOS_ABERTOS_URL}/penalidades/versao/v1/odata/Penalidades"
            params = {
                "$filter": f"contains(CNPJ,'{cnpj}')",
                "$format": "json",
            }

            response = await client.get(url, params=params)

            if response.status_code == 200:
                data = response.json()
                items = data.get("value", [])

                for item in items:
                    processo = self._parse_processo_api(item)
                    if processo:
                        processos.append(processo)

        except Exception as e:
            logger.debug(f"[{self.source_name}] API falhou: {e}")

        return processos

    async def _buscar_processos_scraping(
        self,
        cnpj: str,
    ) -> list[ProcessoBC]:
        """Busca processos via scraping."""
        processos = []

        try:
            client = await self._get_client()

            # Página de penalidades
            url = f"{self.BASE_URL}/estabilidadefinanceira/penalidades"
            response = await client.get(url)

            if response.status_code == 200:
                html = response.text
                # Parse simplificado - em produção usaria BeautifulSoup
                processos = self._parse_html_penalidades(html, cnpj)

        except Exception as e:
            logger.debug(f"[{self.source_name}] Scraping falhou: {e}")

        return processos

    def _parse_processo_api(
        self,
        item: dict[str, Any],
    ) -> Optional[ProcessoBC]:
        """Parse de processo da API."""
        try:
            numero = item.get("NumeroProcesso") or item.get("Processo") or ""
            if not numero:
                return None

            # Tipo
            tipo_str = item.get("TipoPenalidade") or item.get("Tipo") or "OUTROS"
            tipo = self._parse_tipo_processo(tipo_str)

            # Status
            status_str = item.get("Situacao") or item.get("Status") or "JULGADO"
            status = self._parse_status_processo(status_str)

            # Instituição
            cnpj = item.get("CNPJ") or ""
            nome = item.get("Instituicao") or item.get("RazaoSocial") or ""

            # Datas
            data_abertura = self._parse_data(item.get("DataAbertura") or item.get("DataInicio"))
            data_julgamento = self._parse_data(item.get("DataJulgamento"))

            # Valores
            valor_str = item.get("ValorMulta") or item.get("Valor")
            valor_multa = Decimal(str(valor_str)) if valor_str else None

            # Descrição
            descricao = item.get("Descricao") or item.get("Motivo") or ""

            return ProcessoBC(
                numero=numero,
                tipo=tipo,
                status=status,
                instituicao_cnpj=cnpj,
                instituicao_nome=nome,
                data_abertura=data_abertura or date.today(),
                data_julgamento=data_julgamento,
                penalidade=tipo_str,
                valor_multa=valor_multa,
                descricao=descricao,
            )

        except Exception as e:
            logger.debug(f"Erro ao parsear processo: {e}")
            return None

    def _parse_html_penalidades(
        self,
        html: str,
        cnpj: str,
    ) -> list[ProcessoBC]:
        """Parse de HTML de penalidades."""
        processos = []

        try:
            # Busca por tabelas ou divs com dados
            # Implementação simplificada
            import json

            # Tenta JSON embutido
            match = re.search(r'"penalidades"\s*:\s*(\[.*?\])', html, re.DOTALL)
            if match:
                items = json.loads(match.group(1))
                for item in items:
                    if cnpj in str(item.get("CNPJ", "")):
                        processo = self._parse_processo_api(item)
                        if processo:
                            processos.append(processo)

        except Exception as e:
            logger.debug(f"Erro no parse HTML: {e}")

        return processos

    def _parse_tipo_processo(self, tipo_str: str) -> TipoProcesso:
        """Parse de tipo de processo."""
        tipo_upper = tipo_str.upper()

        if "MULTA" in tipo_upper:
            return TipoProcesso.MULTA
        elif "ADVERTENCIA" in tipo_upper or "ADVERTÊNCIA" in tipo_upper:
            return TipoProcesso.ADVERTENCIA
        elif "INTERVENCAO" in tipo_upper or "INTERVENÇÃO" in tipo_upper:
            return TipoProcesso.INTERVENCAO
        elif "LIQUIDACAO" in tipo_upper or "LIQUIDAÇÃO" in tipo_upper:
            return TipoProcesso.LIQUIDACAO
        elif "RAET" in tipo_upper:
            return TipoProcesso.RAET
        elif "PAS" in tipo_upper or "SANCIONADOR" in tipo_upper:
            return TipoProcesso.ADMINISTRATIVO_SANCIONADOR
        else:
            return TipoProcesso.OUTROS

    def _parse_status_processo(self, status_str: str) -> StatusProcesso:
        """Parse de status do processo."""
        status_upper = status_str.upper()

        if "ABERTO" in status_upper:
            return StatusProcesso.ABERTO
        elif "ANDAMENTO" in status_upper:
            return StatusProcesso.EM_ANDAMENTO
        elif "JULGADO" in status_upper or "CONCLUIDO" in status_upper:
            return StatusProcesso.JULGADO
        elif "ARQUIVADO" in status_upper:
            return StatusProcesso.ARQUIVADO
        elif "RECURSO" in status_upper:
            return StatusProcesso.RECURSO
        else:
            return StatusProcesso.JULGADO

    def _parse_data(self, value: Any) -> Optional[date]:
        """Parse de data."""
        if value is None:
            return None

        if isinstance(value, date):
            return value

        if isinstance(value, datetime):
            return value.date()

        if isinstance(value, str):
            for fmt in ["%Y-%m-%d", "%d/%m/%Y", "%Y%m%d"]:
                try:
                    return datetime.strptime(value.strip()[:10], fmt).date()
                except ValueError:
                    continue

        return None

    def _consolidar_historico(
        self,
        cnpj: str,
        processos: list[ProcessoBC],
        anos: int,
    ) -> HistoricoProcessosIF:
        """Consolida histórico de processos."""
        # Filtra por período
        data_limite = date.today().replace(year=date.today().year - anos)
        processos_periodo = [p for p in processos if p.data_abertura >= data_limite]

        # Contabiliza
        total = len(processos_periodo)
        abertos = sum(1 for p in processos_periodo if p.status == StatusProcesso.ABERTO)
        julgados = sum(1 for p in processos_periodo if p.status == StatusProcesso.JULGADO)

        multas = [p for p in processos_periodo if p.tipo == TipoProcesso.MULTA]
        advertencias = [p for p in processos_periodo if p.tipo == TipoProcesso.ADVERTENCIA]
        intervencoes = [p for p in processos_periodo if p.tipo == TipoProcesso.INTERVENCAO]

        valores_multa = [p.valor_multa for p in processos_periodo if p.valor_multa]
        valor_total = sum(valores_multa, Decimal("0"))
        maior_multa = max(valores_multa) if valores_multa else Decimal("0")

        nome = processos_periodo[0].instituicao_nome if processos_periodo else ""

        return HistoricoProcessosIF(
            cnpj=cnpj,
            nome=nome,
            total_processos=total,
            processos_abertos=abertos,
            processos_julgados=julgados,
            total_multas=len(multas),
            total_advertencias=len(advertencias),
            total_intervencoes=len(intervencoes),
            valor_total_multas=valor_total,
            maior_multa=maior_multa,
            processos=processos_periodo,
            periodo_inicio=data_limite,
            periodo_fim=date.today(),
        )
