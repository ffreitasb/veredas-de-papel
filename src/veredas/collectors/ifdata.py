"""
Coletor de dados do IF.Data do Banco Central.

O IF.Data e o sistema de informacoes do Banco Central que disponibiliza
dados financeiros das instituicoes financeiras brasileiras, incluindo:
- Indice de Basileia (adequacao de capital)
- Indice de Liquidez
- Ativos totais
- Patrimonio liquido
- Informacoes contabeis

API: https://www3.bcb.gov.br/ifdata/
"""

from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from typing import Optional

import httpx

from veredas.collectors.base import BaseCollector, CollectionResult


@dataclass
class DadosIF:
    """Dados financeiros de uma instituicao financeira."""

    cnpj: str
    nome: str
    data_base: date  # Data de referencia dos dados (trimestral)

    # Indicadores de capital
    indice_basileia: Optional[Decimal] = None  # Indice de Basileia (%)
    patrimonio_liquido: Optional[Decimal] = None  # Em R$ mil

    # Indicadores de liquidez
    indice_liquidez: Optional[Decimal] = None  # Indice de liquidez (%)
    ativos_liquidos: Optional[Decimal] = None  # Em R$ mil

    # Tamanho
    ativo_total: Optional[Decimal] = None  # Em R$ mil
    depositos_totais: Optional[Decimal] = None  # Em R$ mil

    # Qualidade da carteira
    inadimplencia: Optional[Decimal] = None  # Taxa de inadimplencia (%)

    # Rentabilidade
    roa: Optional[Decimal] = None  # Return on Assets (%)
    roe: Optional[Decimal] = None  # Return on Equity (%)


@dataclass
class ResultadoIFData:
    """Resultado da consulta ao IF.Data."""

    data_consulta: date
    instituicoes: list[DadosIF] = field(default_factory=list)


# Endpoints da API IF.Data
IFDATA_BASE_URL = "https://www3.bcb.gov.br/ifdata/rest"
IFDATA_ENDPOINTS = {
    "lista_ifs": "/listaIFs",
    "dados_if": "/dados",
    "resumo": "/resumo",
}


class IFDataCollector(BaseCollector):
    """
    Coletor de dados do sistema IF.Data do Banco Central.

    Coleta indicadores financeiros das instituicoes financeiras
    como Indice de Basileia, liquidez, ativos, etc.
    """

    def __init__(self, timeout: int = 30):
        """
        Inicializa o coletor.

        Args:
            timeout: Timeout das requisicoes HTTP em segundos.
        """
        self.timeout = timeout
        self._client: Optional[httpx.AsyncClient] = None

    @property
    def source_name(self) -> str:
        return "ifdata"

    async def _get_client(self) -> httpx.AsyncClient:
        """Retorna o cliente HTTP, criando se necessario."""
        if self._client is None:
            self._client = httpx.AsyncClient(
                timeout=self.timeout,
                headers={
                    "Accept": "application/json",
                    "User-Agent": "veredas-de-papel/0.1.0",
                },
            )
        return self._client

    async def collect(
        self,
        cnpjs: Optional[list[str]] = None,
        data_base: Optional[date] = None,
    ) -> CollectionResult[ResultadoIFData]:
        """
        Coleta dados do IF.Data para as instituicoes especificadas.

        Args:
            cnpjs: Lista de CNPJs das IFs a consultar. Se None, coleta top 20.
            data_base: Data base dos dados (trimestral). Se None, usa mais recente.

        Returns:
            CollectionResult com ResultadoIFData.
        """
        try:
            client = await self._get_client()

            resultado = ResultadoIFData(
                data_consulta=date.today(),
                instituicoes=[],
            )

            # Se nenhum CNPJ especificado, buscar lista das maiores IFs
            if cnpjs is None:
                cnpjs = await self._get_principais_ifs(client)

            # Coletar dados de cada IF
            for cnpj in cnpjs:
                dados = await self._collect_dados_if(client, cnpj, data_base)
                if dados:
                    resultado.instituicoes.append(dados)

            return CollectionResult.ok(
                data=resultado,
                source=self.source_name,
            )

        except Exception as e:
            return CollectionResult.fail(
                error=f"Erro ao coletar dados do IF.Data: {e}",
                source=self.source_name,
            )

    async def _get_principais_ifs(
        self,
        client: httpx.AsyncClient,
        limite: int = 20,
    ) -> list[str]:
        """
        Obtem lista das principais IFs por ativo total.

        Args:
            client: Cliente HTTP.
            limite: Numero maximo de IFs a retornar.

        Returns:
            Lista de CNPJs.
        """
        # Lista de CNPJs dos maiores bancos brasileiros (fallback)
        principais_bancos = [
            "00.000.000/0001-91",  # Banco do Brasil
            "60.746.948/0001-12",  # Bradesco
            "60.701.190/0001-04",  # Itau
            "00.360.305/0001-04",  # Caixa
            "33.657.248/0001-89",  # Santander
            "90.400.888/0001-42",  # Banco Safra
            "30.306.294/0001-45",  # Banco BTG Pactual
            "33.042.953/0001-04",  # Citibank
            "62.073.200/0001-21",  # Banco Votorantim
            "07.237.373/0001-20",  # Banco do Nordeste
        ]

        try:
            # Tentar obter lista atualizada da API
            response = await client.get(
                f"{IFDATA_BASE_URL}{IFDATA_ENDPOINTS['lista_ifs']}",
                params={"tipo": "Banco"},
            )

            if response.status_code == 200:
                data = response.json()
                if isinstance(data, list):
                    return [if_data.get("cnpj") for if_data in data[:limite] if if_data.get("cnpj")]

        except Exception:
            pass

        return principais_bancos[:limite]

    async def _collect_dados_if(
        self,
        client: httpx.AsyncClient,
        cnpj: str,
        data_base: Optional[date] = None,
    ) -> Optional[DadosIF]:
        """
        Coleta dados de uma IF especifica.

        Args:
            client: Cliente HTTP.
            cnpj: CNPJ da instituicao.
            data_base: Data base dos dados.

        Returns:
            DadosIF ou None se nao encontrar.
        """
        try:
            params = {"cnpj": cnpj.replace("/", "").replace("-", "").replace(".", "")}
            if data_base:
                params["dataBase"] = data_base.strftime("%Y%m")

            response = await client.get(
                f"{IFDATA_BASE_URL}{IFDATA_ENDPOINTS['resumo']}",
                params=params,
            )

            if response.status_code != 200:
                return None

            data = response.json()
            if not data:
                return None

            return self._parse_dados_if(cnpj, data)

        except Exception:
            return None

    def _parse_dados_if(self, cnpj: str, data: dict) -> Optional[DadosIF]:
        """
        Faz o parse dos dados JSON para DadosIF.

        Args:
            cnpj: CNPJ da IF.
            data: Dados JSON da API.

        Returns:
            DadosIF ou None.
        """
        try:
            # Extrair data base
            data_base_str = data.get("dataBase", "")
            if data_base_str:
                ano = int(data_base_str[:4])
                mes = int(data_base_str[4:6])
                data_base = date(ano, mes, 1)
            else:
                data_base = date.today()

            return DadosIF(
                cnpj=cnpj,
                nome=data.get("nomeInstituicao", ""),
                data_base=data_base,
                indice_basileia=self._to_decimal(data.get("indiceBasileia")),
                patrimonio_liquido=self._to_decimal(data.get("patrimonioLiquido")),
                indice_liquidez=self._to_decimal(data.get("indiceLiquidez")),
                ativos_liquidos=self._to_decimal(data.get("ativosLiquidos")),
                ativo_total=self._to_decimal(data.get("ativoTotal")),
                depositos_totais=self._to_decimal(data.get("depositosTotais")),
                inadimplencia=self._to_decimal(data.get("taxaInadimplencia")),
                roa=self._to_decimal(data.get("roa")),
                roe=self._to_decimal(data.get("roe")),
            )

        except Exception:
            return None

    def _to_decimal(self, value) -> Optional[Decimal]:
        """Converte valor para Decimal de forma segura."""
        if value is None:
            return None
        try:
            return Decimal(str(value))
        except Exception:
            return None

    async def health_check(self) -> bool:
        """
        Verifica se a API do IF.Data esta acessivel.

        Returns:
            True se a API esta respondendo.
        """
        try:
            client = await self._get_client()
            response = await client.get(
                f"{IFDATA_BASE_URL}/status",
                timeout=10,
            )
            return response.status_code in (200, 404)  # 404 = endpoint nao existe mas servidor responde
        except Exception:
            return False

    async def collect_por_cnpj(self, cnpj: str) -> CollectionResult[DadosIF]:
        """
        Coleta dados de uma IF especifica pelo CNPJ.

        Args:
            cnpj: CNPJ da instituicao.

        Returns:
            CollectionResult com DadosIF.
        """
        try:
            client = await self._get_client()
            dados = await self._collect_dados_if(client, cnpj)

            if dados:
                return CollectionResult.ok(
                    data=dados,
                    source=self.source_name,
                )
            else:
                return CollectionResult.fail(
                    error=f"Nenhum dado encontrado para CNPJ: {cnpj}",
                    source=self.source_name,
                )

        except Exception as e:
            return CollectionResult.fail(
                error=f"Erro ao coletar dados da IF: {e}",
                source=self.source_name,
            )

    async def close(self) -> None:
        """Fecha o cliente HTTP."""
        if self._client:
            await self._client.aclose()
            self._client = None
