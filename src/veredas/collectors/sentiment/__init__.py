"""
Análise de sentimento para instituições financeiras.

Agrega sinais de múltiplas fontes (Reclame Aqui, processos BC,
mercado secundário) em um score de risco consolidado.
"""

from veredas.collectors.sentiment.analyzer import (
    AnaliseTexto,
    Sentimento,
    SentimentoAgregado,
    SentimentAnalyzer,
)
from veredas.collectors.sentiment.aggregator import (
    NivelRisco,
    RiskSignal,
    SignalAggregator,
    SinalMercadoSecundario,
    SinalProcessosBC,
    SinalReclameAqui,
    SinalSentimento,
    TendenciaRisco,
)

__all__ = [
    # Analyzer
    "AnaliseTexto",
    "Sentimento",
    "SentimentoAgregado",
    "SentimentAnalyzer",
    # Aggregator
    "NivelRisco",
    "RiskSignal",
    "SignalAggregator",
    "SinalMercadoSecundario",
    "SinalProcessosBC",
    "SinalReclameAqui",
    "SinalSentimento",
    "TendenciaRisco",
]
