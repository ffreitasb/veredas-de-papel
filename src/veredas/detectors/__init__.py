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
]
