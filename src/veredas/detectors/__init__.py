"""
Módulo de detecção de anomalias do veredas de papel.

Exporta detectores e resultados de detecção.
"""

from veredas.detectors.base import AnomaliaDetectada, BaseDetector, DetectionResult
from veredas.detectors.rules import (
    DivergenciaDetector,
    RuleBasedEngine,
    RuleThresholds,
    SpreadDetector,
    VariacaoDetector,
)

__all__ = [
    # Base
    "BaseDetector",
    "DetectionResult",
    "AnomaliaDetectada",
    # Rules
    "RuleThresholds",
    "SpreadDetector",
    "VariacaoDetector",
    "DivergenciaDetector",
    "RuleBasedEngine",
]
