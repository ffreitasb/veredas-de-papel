"""
Modulo de analise do veredas de papel.

Fornece funcionalidades de:
- Score de risco por instituicao
- Indicadores de saude financeira
- Geracao de graficos
"""

from veredas.analysis.health import (
    HealthAnalysis,
    analisar_saude_if,
    comparar_com_benchmark,
)
from veredas.analysis.risk_score import (
    RiskLevel,
    RiskScore,
    ScoreBreakdown,
    calcular_score_batch,
    calcular_score_risco,
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
