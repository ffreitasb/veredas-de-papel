"""
Coletor de dados do Banco Central do Brasil.

Utiliza a biblioteca python-bcb para acessar as séries temporais
do Sistema Gerenciador de Séries Temporais (SGS) do BCB.

Séries coletadas:
- Selic (código 11): Taxa de juros - Selic acumulada no mês
- CDI (código 12): Taxa de juros - CDI
- IPCA (código 433): Índice nacional de preços ao consumidor-amplo
"""

import asyncio
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal
from typing import Any, Optional

import httpx
from bcb import sgs

from veredas.collectors.base import BaseCollector, CollectionResult


@dataclass
class TaxaReferenciaBCB:
    """Dados de uma taxa de referência coletada do BCB."""

    tipo: str  # selic, cdi, ipca
    data: date
    valor: Decimal
    valor_diario: Optional[Decimal] = None


@dataclass
class DadosBCB:
    """Conjunto de dados coletados do BCB."""

    selic: Optional[TaxaReferenciaBCB] = None
    cdi: Optional[TaxaReferenciaBCB] = None
    ipca: Optional[TaxaReferenciaBCB] = None


# Códigos das séries no SGS do BCB
SERIES_CODES = {
    "selic": 11,      # Taxa de juros - Selic acumulada no mês
    "cdi": 12,        # Taxa de juros - CDI
    "ipca": 433,      # IPCA - Variação mensal
    "selic_meta": 432,  # Taxa Selic - Meta definida pelo Copom
}


def _sgs_get_sync(codes: dict[str, int], **kwargs: Any) -> Any:
    """
    Wrapper síncrono para sgs.get().

    Necessário para uso com asyncio.to_thread().
    """
    return sgs.get(codes=codes, **kwargs)


class BCBCollector(BaseCollector):
    """
    Coletor de taxas de referência do Banco Central.

    Coleta as séries temporais de Selic, CDI e IPCA do SGS.
    """

    @property
    def source_name(self) -> str:
        return "bcb"

    async def collect(
        self,
        dias_retroativos: int = 30,
    ) -> CollectionResult[DadosBCB]:
        """
        Coleta dados de taxas do BCB.

        Args:
            dias_retroativos: Quantos dias no passado buscar.

        Returns:
            CollectionResult com DadosBCB.
        """
        try:
            data_fim = date.today()
            data_inicio = data_fim - timedelta(days=dias_retroativos)

            dados = DadosBCB()

            # Coletar Selic
            selic_data = await self._collect_serie("selic", data_inicio, data_fim)
            if selic_data:
                dados.selic = selic_data

            # Coletar CDI
            cdi_data = await self._collect_serie("cdi", data_inicio, data_fim)
            if cdi_data:
                dados.cdi = cdi_data

            # Coletar IPCA
            ipca_data = await self._collect_serie("ipca", data_inicio, data_fim)
            if ipca_data:
                dados.ipca = ipca_data

            return CollectionResult.ok(
                data=dados,
                source=self.source_name,
                raw_response={
                    "selic": selic_data,
                    "cdi": cdi_data,
                    "ipca": ipca_data,
                },
            )

        except Exception as e:
            return CollectionResult.fail(
                error=f"Erro ao coletar dados do BCB: {e}",
                source=self.source_name,
            )

    async def _collect_serie(
        self,
        tipo: str,
        data_inicio: date,
        data_fim: date,
    ) -> Optional[TaxaReferenciaBCB]:
        """
        Coleta uma série específica do SGS.

        Args:
            tipo: Tipo da série (selic, cdi, ipca).
            data_inicio: Data inicial.
            data_fim: Data final.

        Returns:
            TaxaReferenciaBCB com o último valor ou None.
        """
        try:
            codigo = SERIES_CODES.get(tipo)
            if not codigo:
                return None

            # python-bcb é síncrono, executa em thread para não bloquear event loop
            df = await asyncio.to_thread(
                _sgs_get_sync,
                {tipo: codigo},
                start=data_inicio.strftime("%Y-%m-%d"),
                end=data_fim.strftime("%Y-%m-%d"),
            )

            if df.empty:
                return None

            # Pegar o último valor disponível
            ultima_data = df.index[-1].date()
            ultimo_valor = df.iloc[-1][tipo]

            return TaxaReferenciaBCB(
                tipo=tipo,
                data=ultima_data,
                valor=Decimal(str(ultimo_valor)),
            )

        except Exception:
            return None

    async def collect_selic(self, dias: int = 30) -> CollectionResult[list[TaxaReferenciaBCB]]:
        """
        Coleta histórico da taxa Selic.

        Args:
            dias: Quantos dias de histórico.

        Returns:
            CollectionResult com lista de TaxaReferenciaBCB.
        """
        try:
            data_fim = date.today()
            data_inicio = data_fim - timedelta(days=dias)

            # python-bcb é síncrono, executa em thread para não bloquear event loop
            df = await asyncio.to_thread(
                _sgs_get_sync,
                {"selic": SERIES_CODES["selic"]},
                start=data_inicio.strftime("%Y-%m-%d"),
                end=data_fim.strftime("%Y-%m-%d"),
            )

            if df.empty:
                return CollectionResult.fail(
                    error="Nenhum dado de Selic encontrado",
                    source=self.source_name,
                )

            taxas = [
                TaxaReferenciaBCB(
                    tipo="selic",
                    data=idx.date(),
                    valor=Decimal(str(row["selic"])),
                )
                for idx, row in df.iterrows()
            ]

            return CollectionResult.ok(
                data=taxas,
                source=self.source_name,
            )

        except Exception as e:
            return CollectionResult.fail(
                error=f"Erro ao coletar Selic: {e}",
                source=self.source_name,
            )

    async def collect_selic_meta(self) -> CollectionResult[TaxaReferenciaBCB]:
        """
        Coleta a meta da taxa Selic definida pelo Copom.

        Returns:
            CollectionResult com TaxaReferenciaBCB.
        """
        try:
            data_fim = date.today()
            data_inicio = data_fim - timedelta(days=90)  # Copom se reúne ~45 dias

            # python-bcb é síncrono, executa em thread para não bloquear event loop
            df = await asyncio.to_thread(
                _sgs_get_sync,
                {"selic_meta": SERIES_CODES["selic_meta"]},
                start=data_inicio.strftime("%Y-%m-%d"),
                end=data_fim.strftime("%Y-%m-%d"),
            )

            if df.empty:
                return CollectionResult.fail(
                    error="Nenhum dado de Selic Meta encontrado",
                    source=self.source_name,
                )

            ultima_data = df.index[-1].date()
            ultimo_valor = df.iloc[-1]["selic_meta"]

            return CollectionResult.ok(
                data=TaxaReferenciaBCB(
                    tipo="selic_meta",
                    data=ultima_data,
                    valor=Decimal(str(ultimo_valor)),
                ),
                source=self.source_name,
            )

        except Exception as e:
            return CollectionResult.fail(
                error=f"Erro ao coletar Selic Meta: {e}",
                source=self.source_name,
            )

    async def health_check(self) -> bool:
        """
        Verifica se a API do BCB está acessível.

        Returns:
            True se a API está respondendo.
        """
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                response = await client.get(
                    "https://api.bcb.gov.br/dados/serie/bcdata.sgs.11/dados/ultimos/1",
                    params={"formato": "json"},
                )
                return response.status_code == 200
        except Exception:
            return False


# Funções de conveniência para uso síncrono

def get_selic_atual() -> Optional[Decimal]:
    """
    Retorna a taxa Selic atual (síncrono).

    Returns:
        Decimal com a taxa ou None em caso de erro.
    """
    try:
        df = sgs.get(codes={"selic": 11}, last=1)
        if df.empty:
            return None
        return Decimal(str(df.iloc[-1]["selic"]))
    except Exception:
        return None


def get_cdi_atual() -> Optional[Decimal]:
    """
    Retorna a taxa CDI atual (síncrono).

    Returns:
        Decimal com a taxa ou None em caso de erro.
    """
    try:
        df = sgs.get(codes={"cdi": 12}, last=1)
        if df.empty:
            return None
        return Decimal(str(df.iloc[-1]["cdi"]))
    except Exception:
        return None


def get_ipca_atual() -> Optional[Decimal]:
    """
    Retorna o IPCA atual (variação mensal, síncrono).

    Returns:
        Decimal com a taxa ou None em caso de erro.
    """
    try:
        df = sgs.get(codes={"ipca": 433}, last=1)
        if df.empty:
            return None
        return Decimal(str(df.iloc[-1]["ipca"]))
    except Exception:
        return None
