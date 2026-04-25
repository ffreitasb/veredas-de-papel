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
from veredas.detectors.experimental.stl import STLDecompositionDetector
from veredas.detectors.statistical import (
    ChangePointDetector,
    RollingZScoreDetector,
    StatisticalEngine,
    StatisticalThresholds,
)

__all__ = [
    "AnomaliaDetectada",
    # Base
    "BaseDetector",
    "ChangePointDetector",
    "DBSCANOutlierDetector",
    # Unified Engine
    "DetectionEngine",
    "DetectionResult",
    "DetectorCategory",
    "DivergenciaDetector",
    "EngineConfig",
    "EngineResult",
    # Features
    "FeatureExtractor",
    "IsolationForestDetector",
    "MLEngine",
    # ML
    "MLThresholds",
    "RollingZScoreDetector",
    "RuleBasedEngine",
    # Rules
    "RuleThresholds",
    "STLDecompositionDetector",
    "SpreadDetector",
    "StatisticalEngine",
    # Statistical
    "StatisticalThresholds",
    "TaxaFeatures",
    "VariacaoDetector",
    "calculate_market_stats",
]
