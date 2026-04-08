"""
API REST do veredas de papel.

Exporta routers para os endpoints da API.
"""

from veredas.api.detection import router as detection_router
from veredas.api.schemas import (
    AnomaliaResponse,
    AvailableDetectorsResponse,
    DetectionRequest,
    DetectionResponse,
    DetectorCategoryEnum,
    DetectorResultResponse,
    HealthResponse,
    SeveridadeEnum,
    SingleDetectorRequest,
    TaxaInput,
    TipoAnomaliaEnum,
)

__all__ = [
    # Router
    "detection_router",
    # Schemas
    "TaxaInput",
    "DetectionRequest",
    "SingleDetectorRequest",
    "AnomaliaResponse",
    "DetectorResultResponse",
    "DetectionResponse",
    "AvailableDetectorsResponse",
    "HealthResponse",
    "SeveridadeEnum",
    "TipoAnomaliaEnum",
    "DetectorCategoryEnum",
]
