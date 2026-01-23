"""
Modulo de analise do veredas de papel.

Fornece funcionalidades de:
- Score de risco por instituicao
- Indicadores de saude financeira
- Geracao de graficos
"""

from veredas.analysis.risk_score import (
    RiskScore,
    RiskLevel,
    ScoreBreakdown,
    calcular_score_risco,
    calcular_score_batch,
)
from veredas.analysis.health import (
    HealthAnalysis,
    analisar_saude_if,
    comparar_com_benchmark,
)
from veredas.analysis.charts import (
    criar_grafico_evolucao_taxas,
    criar_grafico_anomalias_por_severidade,
    criar_grafico_anomalias_timeline,
    criar_grafico_scores_risco,
    criar_grafico_comparativo_spread,
    criar_grafico_indicadores_saude,
)

__all__ = [
    # Risk Score
    "RiskScore",
    "RiskLevel",
    "ScoreBreakdown",
    "calcular_score_risco",
    "calcular_score_batch",
    # Health Analysis
    "HealthAnalysis",
    "analisar_saude_if",
    "comparar_com_benchmark",
]
