"""
Score de risco por instituicao financeira.

Calcula um score de 0-100 baseado em multiplos fatores:
- Spread vs CDI (40%)
- Indice Basileia (30%)
- Volatilidade (20%)
- Tendencia (10%)
"""

from dataclasses import dataclass, field
from decimal import Decimal
from enum import StrEnum

from veredas.storage.models import InstituicaoFinanceira, TaxaCDB


class RiskLevel(StrEnum):
    """Niveis de risco."""

    BAIXO = "BAIXO"  # 0-25
    MEDIO = "MEDIO"  # 26-50
    ALTO = "ALTO"  # 51-75
    CRITICO = "CRITICO"  # 76-100


@dataclass
class ScoreBreakdown:
    """Detalhamento do score por componente."""

    spread_score: float  # 0-40
    basileia_score: float  # 0-30
    volatilidade_score: float  # 0-20
    tendencia_score: float  # 0-10

    @property
    def total(self) -> float:
        """Score total."""
        return (
            self.spread_score + self.basileia_score + self.volatilidade_score + self.tendencia_score
        )


@dataclass
class RiskScore:
    """Resultado do calculo de score de risco."""

    score: float  # 0-100
    level: RiskLevel
    breakdown: ScoreBreakdown
    if_id: int | None = None
    if_nome: str | None = None
    detalhes: dict = field(default_factory=dict)

    @property
    def color(self) -> str:
        """Cor associada ao nivel de risco."""
        colors = {
            RiskLevel.BAIXO: "green",
            RiskLevel.MEDIO: "yellow",
            RiskLevel.ALTO: "orange",
            RiskLevel.CRITICO: "red",
        }
        return colors[self.level]

    @property
    def emoji(self) -> str:
        """Emoji associado ao nivel de risco."""
        emojis = {
            RiskLevel.BAIXO: "✅",
            RiskLevel.MEDIO: "⚠️",
            RiskLevel.ALTO: "🔶",
            RiskLevel.CRITICO: "🔴",
        }
        return emojis[self.level]


def _score_to_level(score: float) -> RiskLevel:
    """Converte score numerico para nivel."""
    if score <= 25:
        return RiskLevel.BAIXO
    elif score <= 50:
        return RiskLevel.MEDIO
    elif score <= 75:
        return RiskLevel.ALTO
    else:
        return RiskLevel.CRITICO


def _calcular_spread_score(
    percentual_cdi: Decimal | None,
    cdi_atual: Decimal | None = None,
) -> float:
    """
    Calcula score baseado no spread vs CDI.

    Peso: 40% do total

    Thresholds:
    - < 100% CDI: 0 pontos (normal)
    - 100-110%: 5 pontos
    - 110-120%: 15 pontos
    - 120-130%: 25 pontos
    - 130-150%: 35 pontos
    - > 150%: 40 pontos (maximo)
    """
    if percentual_cdi is None:
        return 0.0

    pct = float(percentual_cdi)

    if pct < 100:
        return 0.0
    elif pct < 110:
        return 5.0
    elif pct < 120:
        return 15.0
    elif pct < 130:
        return 25.0
    elif pct < 150:
        return 35.0
    else:
        return 40.0


def _calcular_basileia_score(
    indice_basileia: Decimal | None,
) -> float:
    """
    Calcula score baseado no indice de Basileia.

    Peso: 30% do total

    Minimo regulatorio: 10.5%
    Confortavel: > 15%

    Thresholds:
    - > 15%: 0 pontos (confortavel)
    - 12-15%: 10 pontos
    - 10.5-12%: 20 pontos (proximo do minimo)
    - < 10.5%: 30 pontos (abaixo do minimo!)
    """
    if indice_basileia is None:
        return 15.0  # Sem dados = risco medio

    ib = float(indice_basileia)

    if ib > 15:
        return 0.0
    elif ib > 12:
        return 10.0
    elif ib > 10.5:
        return 20.0
    else:
        return 30.0  # Abaixo do minimo regulatorio


def _calcular_volatilidade_score(
    variacao_7d: float | None = None,
    variacao_30d: float | None = None,
) -> float:
    """
    Calcula score baseado na volatilidade das taxas.

    Peso: 20% do total

    Thresholds (variacao em pontos percentuais):
    - < 2pp: 0 pontos
    - 2-5pp: 5 pontos
    - 5-10pp: 10 pontos
    - 10-20pp: 15 pontos
    - > 20pp: 20 pontos
    """
    # Usa a maior variacao entre 7d e 30d
    variacao = max(
        abs(variacao_7d or 0),
        abs(variacao_30d or 0) / 2,  # 30d normalizado
    )

    if variacao < 2:
        return 0.0
    elif variacao < 5:
        return 5.0
    elif variacao < 10:
        return 10.0
    elif variacao < 20:
        return 15.0
    else:
        return 20.0


def _calcular_tendencia_score(
    tendencia: str | None = None,
) -> float:
    """
    Calcula score baseado na tendencia das taxas.

    Peso: 10% do total

    Tendencias:
    - estavel/queda: 0 pontos
    - subindo_leve: 3 pontos
    - subindo: 6 pontos
    - subindo_forte: 10 pontos
    """
    if tendencia is None:
        return 0.0

    tendencia = tendencia.lower()

    if tendencia in ("estavel", "queda", "caindo"):
        return 0.0
    elif tendencia in ("subindo_leve", "leve_alta"):
        return 3.0
    elif tendencia in ("subindo", "alta"):
        return 6.0
    elif tendencia in ("subindo_forte", "forte_alta"):
        return 10.0
    else:
        return 0.0


def calcular_score_risco(
    if_data: InstituicaoFinanceira | None = None,
    taxa_atual: TaxaCDB | None = None,
    percentual_cdi: Decimal | None = None,
    indice_basileia: Decimal | None = None,
    variacao_7d: float | None = None,
    variacao_30d: float | None = None,
    tendencia: str | None = None,
) -> RiskScore:
    """
    Calcula o score de risco de uma instituicao financeira.

    Args:
        if_data: Dados da instituicao (opcional).
        taxa_atual: Taxa CDB atual (opcional).
        percentual_cdi: Percentual do CDI oferecido.
        indice_basileia: Indice de Basileia da IF.
        variacao_7d: Variacao da taxa nos ultimos 7 dias (pp).
        variacao_30d: Variacao da taxa nos ultimos 30 dias (pp).
        tendencia: Tendencia da taxa ('estavel', 'subindo', etc).

    Returns:
        RiskScore com score, nivel e breakdown.
    """
    # Extrair dados da IF se fornecida
    if if_data and indice_basileia is None:
        indice_basileia = if_data.indice_basileia

    # Extrair dados da taxa se fornecida
    if taxa_atual and percentual_cdi is None:
        percentual_cdi = taxa_atual.percentual

    # Calcular cada componente
    spread_score = _calcular_spread_score(percentual_cdi)
    basileia_score = _calcular_basileia_score(indice_basileia)
    volatilidade_score = _calcular_volatilidade_score(variacao_7d, variacao_30d)
    tendencia_score = _calcular_tendencia_score(tendencia)

    breakdown = ScoreBreakdown(
        spread_score=spread_score,
        basileia_score=basileia_score,
        volatilidade_score=volatilidade_score,
        tendencia_score=tendencia_score,
    )

    score = breakdown.total
    level = _score_to_level(score)

    return RiskScore(
        score=score,
        level=level,
        breakdown=breakdown,
        if_id=if_data.id if if_data else None,
        if_nome=if_data.nome if if_data else None,
        detalhes={
            "percentual_cdi": float(percentual_cdi) if percentual_cdi else None,
            "indice_basileia": float(indice_basileia) if indice_basileia else None,
            "variacao_7d": variacao_7d,
            "variacao_30d": variacao_30d,
            "tendencia": tendencia,
        },
    )


def calcular_score_batch(
    instituicoes: list[InstituicaoFinanceira],
    taxas_por_if: dict[int, list[TaxaCDB]],
) -> list[RiskScore]:
    """
    Calcula score de risco para multiplas instituicoes.

    Args:
        instituicoes: Lista de IFs.
        taxas_por_if: Dicionario {if_id: [taxas]}.

    Returns:
        Lista de RiskScore ordenada por score (maior primeiro).
    """
    scores = []

    for if_data in instituicoes:
        taxas = taxas_por_if.get(if_data.id, [])

        # Pegar taxa mais recente
        taxa_atual = taxas[0] if taxas else None

        # Calcular variacoes se houver historico
        variacao_7d = None
        variacao_30d = None

        if len(taxas) >= 2:
            taxa_recente = float(taxas[0].percentual)
            taxa_7d = float(taxas[min(7, len(taxas) - 1)].percentual)
            variacao_7d = taxa_recente - taxa_7d

        if len(taxas) >= 30:
            taxa_recente = float(taxas[0].percentual)
            taxa_30d = float(taxas[29].percentual)
            variacao_30d = taxa_recente - taxa_30d

        score = calcular_score_risco(
            if_data=if_data,
            taxa_atual=taxa_atual,
            variacao_7d=variacao_7d,
            variacao_30d=variacao_30d,
        )

        scores.append(score)

    # Ordenar por score (maior risco primeiro)
    scores.sort(key=lambda s: s.score, reverse=True)

    return scores
