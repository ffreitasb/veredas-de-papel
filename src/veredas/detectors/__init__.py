"""
Módulo de detecção de anomalias do veredas de papel.

Exporta detectores e resultados de detecção.
"""

from veredas.detectors.base import AnomaliaDetectada, BaseDetector, DetectionResult
from veredas.detectors.engine import DetectionEngine, DetectorCategory, EngineConfig, EngineResult
from veredas.detectors.features import FeatureExtractor, TaxaFeatures, calculate_market_stats
from veredas.detectors.ml import (
    DBSCANOutlierDetector,
    IsolationForestDetector,
    MLEngine,
    MLThresholds,
)
from veredas.detectors.rules import (
    DivergenciaDetector,
    RuleBasedEngine,
    RuleThresholds,
    SpreadDetector,
    VariacaoDetector,
)
from veredas.detectors.statistical import (
    ChangePointDetector,
    RollingZScoreDetector,
    StatisticalEngine,
    StatisticalThresholds,
    STLDecompositionDetector,
)
from veredas.detectors.platform_discrepancy import (
    PlatformDiscrepancyConfig,
    PlatformDiscrepancyDetector,
    TaxaPorPlataforma,
)
from veredas.detectors.price_drop import (
    PriceDropConfig,
    PriceDropDetector,
    detectar_quedas_mercado,
)
from veredas.detectors.sentiment_risk import (
    SentimentRiskConfig,
    SentimentRiskDetector,
    detectar_risco_sentimento,
)

__all__ = [
    # Base
    "BaseDetector",
    "DetectionResult",
    "AnomaliaDetectada",
    # Unified Engine
    "DetectionEngine",
    "EngineConfig",
    "EngineResult",
    "DetectorCategory",
    # Features
    "FeatureExtractor",
    "TaxaFeatures",
    "calculate_market_stats",
    # Rules
    "RuleThresholds",
    "SpreadDetector",
    "VariacaoDetector",
    "DivergenciaDetector",
    "RuleBasedEngine",
    # Statistical
    "StatisticalThresholds",
    "STLDecompositionDetector",
    "ChangePointDetector",
    "RollingZScoreDetector",
    "StatisticalEngine",
    # ML
    "MLThresholds",
    "IsolationForestDetector",
    "DBSCANOutlierDetector",
    "MLEngine",
    # Platform Discrepancy (F4.1)
    "PlatformDiscrepancyConfig",
    "PlatformDiscrepancyDetector",
    "TaxaPorPlataforma",
    # Price Drop (F4.2)
    "PriceDropConfig",
    "PriceDropDetector",
    "detectar_quedas_mercado",
    # Sentiment Risk (F4.3)
    "SentimentRiskConfig",
    "SentimentRiskDetector",
    "detectar_risco_sentimento",
]
