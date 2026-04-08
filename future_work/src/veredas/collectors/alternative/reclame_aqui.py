"""
Coletor de dados do Reclame Aqui.

Coleta reclamações de clientes sobre instituições financeiras,
um indicador leading de problemas operacionais ou financeiros.

Histórico mostra que aumento de reclamações frequentemente
precede problemas maiores em bancos.
"""

import asyncio
import logging
import re
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import Any, Optional

import httpx

from veredas import TZ_BRASIL
from veredas.collectors.base import BaseCollector, CollectionResult

logger = logging.getLogger(__name__)


@dataclass
class Reclamacao:
    """Representa uma reclamação no Reclame Aqui."""

    titulo: str
    descricao: str
    data_reclamacao: date
    categoria: str
    status: str  # RESPONDIDA, NAO_RESPONDIDA, AVALIADA, RESOLVIDA
    avaliacao: Optional[int] = None  # 1-10
    tempo_resposta_horas: Optional[int] = None
    resolvido: bool = False


@dataclass
class ReputacaoRA:
    """Reputação de uma empresa no Reclame Aqui."""

    empresa_nome: str
    empresa_cnpj: Optional[str] = None
    nota_geral: Decimal = Decimal("0")  # 0-10
    total_reclamacoes: int = 0
    reclamacoes_respondidas: int = 0
    reclamacoes_resolvidas: int = 0
    indice_solucao: Decimal = Decimal("0")  # %
    tempo_medio_resposta: Optional[str] = None
    nota_consumidor: Decimal = Decimal("0")  # 0-10
    voltariam_a_fazer_negocio: Decimal = Decimal("0")  # %

    # Histórico recente
    reclamacoes_ultimos_30_dias: int = 0
    reclamacoes_ultimos_90_dias: int = 0

    # Tendência
    variacao_30_dias: Optional[Decimal] = None  # % vs período anterior

    # Metadata
    coletado_em: datetime = field(default_factory=lambda: datetime.now(TZ_BRASIL))
    url_perfil: Optional[str] = None

    @property
    def taxa_resposta(self) -> Decimal:
        """Taxa de resposta às reclamações."""
        if self.total_reclamacoes == 0:
            return Decimal("0")
        return Decimal(self.reclamacoes_respondidas) / Decimal(self.total_reclamacoes) * 100

    @property
    def reputacao_ruim(self) -> bool:
        """Verifica se a reputação é considerada ruim."""
        return self.nota_geral < Decimal("6") or self.indice_solucao < Decimal("50")


class ReclameAquiCollector(BaseCollector):
    """
    Coletor de dados do Reclame Aqui.

    Nota: O Reclame Aqui não possui API pública oficial.
    Este coletor faz scraping do site público respeitando
    rate limits e termos de uso.
    """

    def __init__(
        self,
        timeout: int = 30,
        delay: float = 2.0,
    ):
        """
        Inicializa o coletor.

        Args:
            timeout: Timeout em segundos
            delay: Delay entre requisições
        """
        self.timeout = timeout
        self.delay = delay
        self.base_url = "https://www.reclameaqui.com.br"
        self._client: Optional[httpx.AsyncClient] = None

    @property
    def source_name(self) -> str:
        """L2 FIX: Nome identificador da fonte de dados."""
        return "reclame_aqui"

    # Mapeamento de instituições para slugs do Reclame Aqui
    INSTITUICOES_SLUG = {
        "00.000.000/0001-91": "banco-do-brasil",
        "60.746.948/0001-12": "bradesco",
        "60.701.190/0001-04": "itau",
        "33.657.248/0001-89": "santander-brasil",
        "00.360.305/0001-04": "caixa-economica-federal",
        "90.400.888/0001-42": "banco-safra",
        "30.306.294/0001-45": "btg-pactual",
        "04.902.979/0001-44": "xp-investimentos",
        "18.236.120/0001-58": "nubank",
        "00.416.968/0001-01": "banco-inter",
        "10.573.521/0001-91": "c6-bank",
        "92.874.270/0001-40": "banco-pan",
        "01.181.521/0001-55": "banco-original",
    }

    async def _get_client(self) -> httpx.AsyncClient:
        """Retorna cliente HTTP."""
        if self._client is None or self._client.is_closed:
            # L1 FIX: User agent atualizado
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/131.0.0.0",
                "Accept": "text/html,application/xhtml+xml,*/*",
                "Accept-Language": "pt-BR,pt;q=0.9",
            }
            self._client = httpx.AsyncClient(
                timeout=self.timeout,
                headers=headers,
                follow_redirects=True,
            )
        return self._client

    async def _close_client(self) -> None:
        """Fecha cliente HTTP."""
        if self._client and not self._client.is_closed:
            await self._client.aclose()
            self._client = None

    async def collect(self) -> CollectionResult[list[ReputacaoRA]]:
        """
        Coleta reputação de todas as instituições mapeadas.

        Returns:
            CollectionResult com lista de ReputacaoRA
        """
        try:
            reputacoes = []

            for cnpj, slug in self.INSTITUICOES_SLUG.items():
                try:
                    rep = await self.coletar_reputacao(cnpj, slug)
                    if rep:
                        reputacoes.append(rep)
                    await asyncio.sleep(self.delay)
                except Exception as e:
                    logger.warning(f"[{self.source_name}] Erro ao coletar {slug}: {e}")
                    continue

            if reputacoes:
                return CollectionResult.ok(
                    data=reputacoes,
                    source=self.source_name,
                    raw_response={"count": len(reputacoes)},
                )
            else:
                return CollectionResult.fail(
                    error="Nenhuma reputação coletada",
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
        """Verifica se o Reclame Aqui está acessível."""
        try:
            client = await self._get_client()
            response = await client.get(self.base_url, timeout=10)
            await self._close_client()
            return response.status_code < 500
        except Exception:
            await self._close_client()
            return False

    async def coletar_reputacao(
        self,
        cnpj: str,
        slug: Optional[str] = None,
    ) -> Optional[ReputacaoRA]:
        """
        Coleta reputação de uma instituição específica.

        Args:
            cnpj: CNPJ da instituição
            slug: Slug da empresa no Reclame Aqui (opcional)

        Returns:
            ReputacaoRA ou None
        """
        if slug is None:
            slug = self.INSTITUICOES_SLUG.get(cnpj)

        if not slug:
            logger.warning(f"[{self.source_name}] Slug não encontrado para {cnpj}")
            return None

        try:
            url = f"{self.base_url}/empresa/{slug}/"
            client = await self._get_client()
            response = await client.get(url)

            if response.status_code != 200:
                logger.warning(f"[{self.source_name}] HTTP {response.status_code} para {slug}")
                return None

            html = response.text
            return self._parse_perfil_empresa(html, cnpj, slug, url)

        except Exception as e:
            logger.error(f"[{self.source_name}] Erro ao coletar {slug}: {e}")
            return None

    def _parse_perfil_empresa(
        self,
        html: str,
        cnpj: str,
        slug: str,
        url: str,
    ) -> Optional[ReputacaoRA]:
        """
        Parse do HTML do perfil da empresa.

        Args:
            html: HTML da página
            cnpj: CNPJ
            slug: Slug da empresa
            url: URL do perfil

        Returns:
            ReputacaoRA ou None
        """
        try:
            import json

            # Tenta extrair dados de JSON-LD ou scripts
            patterns = {
                "nota": r'"ratingValue"\s*:\s*"?(\d+[.,]?\d*)"?',
                "total": r'"reviewCount"\s*:\s*"?(\d+)"?',
                "nome": r'"name"\s*:\s*"([^"]+)"',
            }

            dados: dict[str, Any] = {
                "empresa_nome": slug.replace("-", " ").title(),
                "empresa_cnpj": cnpj,
                "url_perfil": url,
            }

            # Extrai dados com regex
            for key, pattern in patterns.items():
                match = re.search(pattern, html)
                if match:
                    if key == "nota":
                        dados["nota_geral"] = Decimal(match.group(1).replace(",", "."))
                    elif key == "total":
                        dados["total_reclamacoes"] = int(match.group(1))
                    elif key == "nome":
                        dados["empresa_nome"] = match.group(1)

            # Padrões específicos do Reclame Aqui
            indices = {
                r"Índice de Solução.*?(\d+[.,]?\d*)%": "indice_solucao",
                r"Voltariam a fazer negócio.*?(\d+[.,]?\d*)%": "voltariam_a_fazer_negocio",
                r"Nota do Consumidor.*?(\d+[.,]?\d*)": "nota_consumidor",
                r"Tempo Médio de Resposta.*?(\d+ (?:horas?|dias?))": "tempo_medio_resposta",
                r"(\d+)\s*reclamações?\s*respondidas?": "reclamacoes_respondidas",
            }

            for pattern, key in indices.items():
                match = re.search(pattern, html, re.IGNORECASE)
                if match:
                    value = match.group(1)
                    if key in ("indice_solucao", "voltariam_a_fazer_negocio", "nota_consumidor"):
                        dados[key] = Decimal(value.replace(",", "."))
                    elif key == "reclamacoes_respondidas":
                        dados[key] = int(value)
                    else:
                        dados[key] = value

            # Busca reclamações recentes (30/90 dias)
            recentes_30 = re.search(r"últimos 30 dias.*?(\d+)", html, re.IGNORECASE)
            recentes_90 = re.search(r"últimos (?:90|3 meses).*?(\d+)", html, re.IGNORECASE)

            if recentes_30:
                dados["reclamacoes_ultimos_30_dias"] = int(recentes_30.group(1))
            if recentes_90:
                dados["reclamacoes_ultimos_90_dias"] = int(recentes_90.group(1))

            # Calcula variação se tiver dados
            if dados.get("reclamacoes_ultimos_30_dias") and dados.get("reclamacoes_ultimos_90_dias"):
                media_mensal = dados["reclamacoes_ultimos_90_dias"] / 3
                if media_mensal > 0:
                    variacao = ((dados["reclamacoes_ultimos_30_dias"] - media_mensal) / media_mensal) * 100
                    dados["variacao_30_dias"] = Decimal(str(round(variacao, 1)))

            return ReputacaoRA(**dados)

        except Exception as e:
            logger.error(f"[{self.source_name}] Erro ao parsear perfil: {e}")
            return None

    async def coletar_reclamacoes(
        self,
        cnpj: str,
        limite: int = 50,
    ) -> list[Reclamacao]:
        """
        Coleta reclamações recentes de uma instituição.

        Args:
            cnpj: CNPJ da instituição
            limite: Número máximo de reclamações

        Returns:
            Lista de Reclamacao
        """
        reclamacoes = []
        slug = self.INSTITUICOES_SLUG.get(cnpj)

        if not slug:
            return reclamacoes

        try:
            # URL de reclamações
            url = f"{self.base_url}/empresa/{slug}/lista-reclamacoes/"
            client = await self._get_client()
            response = await client.get(url)

            if response.status_code != 200:
                return reclamacoes

            html = response.text
            reclamacoes = self._parse_lista_reclamacoes(html, limite)

        except Exception as e:
            logger.error(f"[{self.source_name}] Erro ao coletar reclamações: {e}")

        return reclamacoes

    def _parse_lista_reclamacoes(
        self,
        html: str,
        limite: int,
    ) -> list[Reclamacao]:
        """Parse da lista de reclamações."""
        reclamacoes = []

        try:
            # Padrão para cards de reclamação
            # O HTML específico varia, então usamos padrões genéricos
            card_pattern = r'<div[^>]*class="[^"]*complaint[^"]*"[^>]*>(.*?)</div>\s*</div>'
            cards = re.findall(card_pattern, html, re.DOTALL | re.IGNORECASE)

            for card in cards[:limite]:
                try:
                    titulo_match = re.search(r'<h\d[^>]*>(.*?)</h\d>', card)
                    data_match = re.search(r'(\d{2}/\d{2}/\d{4})', card)
                    status_match = re.search(r'(respondida|não respondida|resolvida|avaliada)', card, re.IGNORECASE)

                    if titulo_match:
                        reclamacoes.append(
                            Reclamacao(
                                titulo=re.sub(r'<[^>]+>', '', titulo_match.group(1)).strip(),
                                descricao="",
                                data_reclamacao=datetime.strptime(
                                    data_match.group(1), "%d/%m/%Y"
                                ).date() if data_match else date.today(),
                                categoria="Geral",
                                status=status_match.group(1).upper() if status_match else "NAO_RESPONDIDA",
                            )
                        )
                except Exception:
                    continue

        except Exception as e:
            logger.debug(f"[{self.source_name}] Erro no parse de reclamações: {e}")

        return reclamacoes


# Dados mock para testes
MOCK_REPUTACOES = [
    ReputacaoRA(
        empresa_nome="Nubank",
        empresa_cnpj="18.236.120/0001-58",
        nota_geral=Decimal("7.8"),
        total_reclamacoes=150000,
        reclamacoes_respondidas=145000,
        reclamacoes_resolvidas=120000,
        indice_solucao=Decimal("82.7"),
        nota_consumidor=Decimal("7.5"),
        voltariam_a_fazer_negocio=Decimal("68.5"),
        reclamacoes_ultimos_30_dias=5000,
        reclamacoes_ultimos_90_dias=14000,
    ),
    ReputacaoRA(
        empresa_nome="Banco Inter",
        empresa_cnpj="00.416.968/0001-01",
        nota_geral=Decimal("6.2"),
        total_reclamacoes=80000,
        reclamacoes_respondidas=70000,
        reclamacoes_resolvidas=50000,
        indice_solucao=Decimal("62.5"),
        nota_consumidor=Decimal("5.8"),
        voltariam_a_fazer_negocio=Decimal("52.0"),
        reclamacoes_ultimos_30_dias=3500,
        reclamacoes_ultimos_90_dias=9000,
        variacao_30_dias=Decimal("16.7"),  # Aumento de 16.7%
    ),
]
