"""
Analise de saude financeira de instituicoes.

Fornece funcionalidades para:
- Analise de indicadores de saude (Basileia, liquidez)
- Comparacao com benchmarks do mercado
- Identificacao de sinais de alerta
"""

from dataclasses import dataclass, field
from decimal import Decimal
from enum import Enum
from typing import Optional

from veredas.storage.models import InstituicaoFinanceira


class HealthStatus(str, Enum):
    """Status de saude da instituicao."""

    SAUDAVEL = "SAUDAVEL"
    ATENCAO = "ATENCAO"
    ALERTA = "ALERTA"
    CRITICO = "CRITICO"


@dataclass
class IndicadorAnalise:
    """Analise de um indicador especifico."""

    nome: str
    valor: Optional[Decimal]
    benchmark: Decimal
    minimo_regulatorio: Optional[Decimal]
    status: HealthStatus
    descricao: str


@dataclass
class HealthAnalysis:
    """Resultado da analise de saude de uma IF."""

    if_id: int
    if_nome: str
    status_geral: HealthStatus
    indicadores: list[IndicadorAnalise] = field(default_factory=list)
    alertas: list[str] = field(default_factory=list)
    recomendacoes: list[str] = field(default_factory=list)

    @property
    def color(self) -> str:
        """Cor CSS do status."""
        colors = {
            HealthStatus.SAUDAVEL: "green",
            HealthStatus.ATENCAO: "yellow",
            HealthStatus.ALERTA: "orange",
            HealthStatus.CRITICO: "red",
        }
        return colors[self.status_geral]


# Benchmarks do mercado (valores tipicos)
BENCHMARK_BASILEIA = Decimal("15.0")  # Bancos medios
BENCHMARK_LIQUIDEZ = Decimal("1.5")  # LCR tipico
MINIMO_BASILEIA = Decimal("10.5")  # Regulatorio


def _analisar_basileia(
    valor: Optional[Decimal],
) -> IndicadorAnalise:
    """Analisa indice de Basileia."""
    if valor is None:
        return IndicadorAnalise(
            nome="Índice de Basileia",
            valor=None,
            benchmark=BENCHMARK_BASILEIA,
            minimo_regulatorio=MINIMO_BASILEIA,
            status=HealthStatus.ATENCAO,
            descricao="Dados não disponíveis",
        )

    if valor < MINIMO_BASILEIA:
        status = HealthStatus.CRITICO
        descricao = f"ABAIXO do mínimo regulatório ({MINIMO_BASILEIA}%)"
    elif valor < Decimal("12.0"):
        status = HealthStatus.ALERTA
        descricao = "Próximo do mínimo regulatório"
    elif valor < BENCHMARK_BASILEIA:
        status = HealthStatus.ATENCAO
        descricao = "Abaixo do benchmark de mercado"
    else:
        status = HealthStatus.SAUDAVEL
        descricao = "Acima do benchmark de mercado"

    return IndicadorAnalise(
        nome="Índice de Basileia",
        valor=valor,
        benchmark=BENCHMARK_BASILEIA,
        minimo_regulatorio=MINIMO_BASILEIA,
        status=status,
        descricao=descricao,
    )


def _analisar_liquidez(
    valor: Optional[Decimal],
) -> IndicadorAnalise:
    """Analisa indice de liquidez."""
    if valor is None:
        return IndicadorAnalise(
            nome="Índice de Liquidez",
            valor=None,
            benchmark=BENCHMARK_LIQUIDEZ,
            minimo_regulatorio=Decimal("1.0"),
            status=HealthStatus.ATENCAO,
            descricao="Dados não disponíveis",
        )

    if valor < Decimal("1.0"):
        status = HealthStatus.CRITICO
        descricao = "Liquidez insuficiente"
    elif valor < Decimal("1.2"):
        status = HealthStatus.ALERTA
        descricao = "Liquidez apertada"
    elif valor < BENCHMARK_LIQUIDEZ:
        status = HealthStatus.ATENCAO
        descricao = "Abaixo do benchmark"
    else:
        status = HealthStatus.SAUDAVEL
        descricao = "Liquidez adequada"

    return IndicadorAnalise(
        nome="Índice de Liquidez",
        valor=valor,
        benchmark=BENCHMARK_LIQUIDEZ,
        minimo_regulatorio=Decimal("1.0"),
        status=status,
        descricao=descricao,
    )


def analisar_saude_if(
    if_data: InstituicaoFinanceira,
) -> HealthAnalysis:
    """
    Analisa a saude financeira de uma instituicao.

    Args:
        if_data: Dados da instituicao financeira.

    Returns:
        HealthAnalysis com status, indicadores e alertas.
    """
    indicadores = []
    alertas = []
    recomendacoes = []

    # Analisa Basileia
    basileia = _analisar_basileia(if_data.indice_basileia)
    indicadores.append(basileia)

    if basileia.status == HealthStatus.CRITICO:
        alertas.append("⚠️ Índice de Basileia ABAIXO do mínimo regulatório!")
        recomendacoes.append("Evitar investimentos nesta instituição")
    elif basileia.status == HealthStatus.ALERTA:
        alertas.append("Índice de Basileia próximo do limite")
        recomendacoes.append("Monitorar evolução dos indicadores")

    # Analisa Liquidez
    liquidez = _analisar_liquidez(if_data.indice_liquidez)
    indicadores.append(liquidez)

    if liquidez.status == HealthStatus.CRITICO:
        alertas.append("⚠️ Liquidez INSUFICIENTE!")
        recomendacoes.append("Alto risco de problemas de pagamento")
    elif liquidez.status == HealthStatus.ALERTA:
        alertas.append("Liquidez apertada")

    # Determina status geral (pior dos indicadores)
    status_list = [i.status for i in indicadores]

    if HealthStatus.CRITICO in status_list:
        status_geral = HealthStatus.CRITICO
    elif HealthStatus.ALERTA in status_list:
        status_geral = HealthStatus.ALERTA
    elif HealthStatus.ATENCAO in status_list:
        status_geral = HealthStatus.ATENCAO
    else:
        status_geral = HealthStatus.SAUDAVEL

    # Recomendacoes gerais
    if status_geral == HealthStatus.SAUDAVEL:
        recomendacoes.append("Instituição com indicadores saudáveis")
    elif not recomendacoes:
        recomendacoes.append("Acompanhar próximas divulgações de indicadores")

    return HealthAnalysis(
        if_id=if_data.id,
        if_nome=if_data.nome,
        status_geral=status_geral,
        indicadores=indicadores,
        alertas=alertas,
        recomendacoes=recomendacoes,
    )


@dataclass
class BenchmarkComparison:
    """Comparacao de uma IF com benchmark."""

    if_id: int
    if_nome: str
    segmento: str
    basileia_if: Optional[Decimal]
    basileia_benchmark: Decimal
    basileia_diff: Optional[Decimal]
    liquidez_if: Optional[Decimal]
    liquidez_benchmark: Decimal
    liquidez_diff: Optional[Decimal]
    posicao_ranking: Optional[int] = None
    total_segmento: Optional[int] = None


def comparar_com_benchmark(
    if_data: InstituicaoFinanceira,
    benchmark_basileia: Optional[Decimal] = None,
    benchmark_liquidez: Optional[Decimal] = None,
) -> BenchmarkComparison:
    """
    Compara indicadores da IF com benchmarks.

    Args:
        if_data: Dados da instituicao.
        benchmark_basileia: Benchmark de Basileia (default: BENCHMARK_BASILEIA).
        benchmark_liquidez: Benchmark de liquidez (default: BENCHMARK_LIQUIDEZ).

    Returns:
        BenchmarkComparison com diferencas.
    """
    b_bench = benchmark_basileia or BENCHMARK_BASILEIA
    l_bench = benchmark_liquidez or BENCHMARK_LIQUIDEZ

    basileia_diff = None
    if if_data.indice_basileia is not None:
        basileia_diff = if_data.indice_basileia - b_bench

    liquidez_diff = None
    if if_data.indice_liquidez is not None:
        liquidez_diff = if_data.indice_liquidez - l_bench

    return BenchmarkComparison(
        if_id=if_data.id,
        if_nome=if_data.nome,
        segmento=if_data.segmento or "N/A",
        basileia_if=if_data.indice_basileia,
        basileia_benchmark=b_bench,
        basileia_diff=basileia_diff,
        liquidez_if=if_data.indice_liquidez,
        liquidez_benchmark=l_bench,
        liquidez_diff=liquidez_diff,
    )
