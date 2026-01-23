"""
API REST para detecção de anomalias.

Expõe endpoints para executar detecção de anomalias em taxas de CDB.
"""

import logging
from datetime import datetime
from decimal import Decimal
from typing import Any

from fastapi import APIRouter, HTTPException, Query, status

from veredas import __version__
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
from veredas.detectors.engine import DetectionEngine, DetectorCategory, EngineConfig
from veredas.storage.models import Indexador, Severidade, TaxaCDB, TipoAnomalia

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/detection", tags=["detection"])


def _taxa_input_to_model(taxa_input: TaxaInput) -> TaxaCDB:
    """Converte TaxaInput para TaxaCDB model."""
    return TaxaCDB(
        id=taxa_input.taxa_id,
        if_id=taxa_input.if_id,
        data_coleta=taxa_input.data_coleta,
        indexador=Indexador(taxa_input.indexador.lower()),
        percentual=taxa_input.percentual,
        prazo_dias=taxa_input.prazo_dias,
        fonte="api",
    )


def _anomalia_to_response(anomalia: Any) -> AnomaliaResponse:
    """Converte AnomaliaDetectada para AnomaliaResponse."""
    return AnomaliaResponse(
        tipo=TipoAnomaliaEnum(anomalia.tipo.value),
        severidade=SeveridadeEnum(anomalia.severidade.value),
        valor_detectado=anomalia.valor_detectado,
        descricao=anomalia.descricao,
        if_id=anomalia.if_id,
        taxa_id=anomalia.taxa_id,
        valor_esperado=anomalia.valor_esperado,
        desvio=anomalia.desvio,
        threshold=anomalia.threshold,
        detector=anomalia.detector,
        detectado_em=anomalia.detectado_em,
        detalhes=anomalia.detalhes,
    )


def _severity_enum_to_model(severity: SeveridadeEnum) -> Severidade:
    """Converte SeveridadeEnum para Severidade model."""
    return Severidade(severity.value)


@router.get("/health", response_model=HealthResponse)
async def health_check() -> HealthResponse:
    """
    Verifica a saúde do serviço de detecção.

    Retorna informações sobre a disponibilidade dos detectores.
    """
    # Verificar disponibilidade de dependências
    ml_available = False
    ruptures_available = False

    try:
        import sklearn  # noqa: F401
        ml_available = True
    except ImportError:
        pass

    try:
        import ruptures  # noqa: F401
        ruptures_available = True
    except ImportError:
        pass

    detectors = DetectionEngine.available_detectors()
    total_detectors = sum(len(d) for d in detectors.values())

    return HealthResponse(
        status="healthy",
        version=__version__,
        detectors_available=total_detectors,
        ml_available=ml_available,
        ruptures_available=ruptures_available,
    )


@router.get("/detectors", response_model=AvailableDetectorsResponse)
async def list_detectors() -> AvailableDetectorsResponse:
    """
    Lista todos os detectores disponíveis.

    Retorna detectores agrupados por categoria (rules, statistical, ml).
    """
    detectors = DetectionEngine.available_detectors()

    return AvailableDetectorsResponse(
        rules=detectors.get(DetectorCategory.RULES, []),
        statistical=detectors.get(DetectorCategory.STATISTICAL, []),
        ml=detectors.get(DetectorCategory.ML, []),
    )


@router.post("/analyze", response_model=DetectionResponse)
async def analyze_taxas(request: DetectionRequest) -> DetectionResponse:
    """
    Executa análise de detecção de anomalias.

    Analisa as taxas fornecidas usando os detectores habilitados
    e retorna anomalias encontradas.

    **Detectores disponíveis:**

    - **Rules**: spread_detector, variacao_detector, divergencia_detector
    - **Statistical**: stl_decomposition_detector, change_point_detector, rolling_zscore_detector
    - **ML**: isolation_forest_detector, dbscan_outlier_detector

    **Exemplo de uso:**

    ```json
    {
      "taxas": [
        {"if_id": 1, "data_coleta": "2025-01-20T10:00:00", "percentual": 145.0, "prazo_dias": 365}
      ],
      "enable_rules": true,
      "enable_statistical": true,
      "enable_ml": false,
      "min_severity": "medium"
    }
    ```
    """
    try:
        # Converter taxas de input para model
        taxas = [_taxa_input_to_model(t) for t in request.taxas]
        taxas_anteriores = None
        if request.taxas_anteriores:
            taxas_anteriores = [_taxa_input_to_model(t) for t in request.taxas_anteriores]

        # Configurar engine
        config = EngineConfig(
            enable_rules=request.enable_rules,
            enable_statistical=request.enable_statistical,
            enable_ml=request.enable_ml,
            min_severity=_severity_enum_to_model(request.min_severity),
            deduplicate=request.deduplicate,
        )

        engine = DetectionEngine(config)

        # Executar análise
        result = engine.analyze(
            taxas,
            taxas_anteriores=taxas_anteriores,
            media_mercado=request.media_mercado,
            desvio_padrao_mercado=request.desvio_padrao_mercado,
        )

        # Converter anomalias para response
        anomalias_response = [_anomalia_to_response(a) for a in result.anomalias]

        # Converter resultados por detector
        detector_results = [
            DetectorResultResponse(
                detector_name=r.detector_name,
                success=r.success,
                anomalias_count=len(r.anomalias),
                execution_time_ms=r.execution_time_ms,
                error=r.error,
            )
            for r in result.results
        ]

        return DetectionResponse(
            anomalias=anomalias_response,
            anomalias_count=len(result.anomalias),
            critical_count=result.critical_count,
            high_count=result.high_count,
            medium_count=result.medium_count,
            taxas_analyzed=result.taxas_analyzed,
            detectors_used=result.detectors_used,
            execution_time_ms=result.execution_time_ms,
            executed_at=result.executed_at,
            detector_results=detector_results,
        )

    except Exception as e:
        logger.exception("Erro na análise de detecção")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erro na análise: {str(e)}",
        )


@router.post("/analyze/single", response_model=DetectionResponse)
async def analyze_single_detector(request: SingleDetectorRequest) -> DetectionResponse:
    """
    Executa um detector específico.

    Útil para testar ou debugar um detector individual.

    **Detectores disponíveis:**

    - spread_detector
    - variacao_detector
    - divergencia_detector
    - stl_decomposition_detector
    - change_point_detector
    - rolling_zscore_detector
    - isolation_forest_detector
    - dbscan_outlier_detector
    """
    try:
        # Converter taxas
        taxas = [_taxa_input_to_model(t) for t in request.taxas]

        # Validar detector
        available = DetectionEngine.available_detectors()
        all_detectors = []
        for d in available.values():
            all_detectors.extend(d)

        if request.detector_name not in all_detectors:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Detector '{request.detector_name}' não encontrado. "
                f"Disponíveis: {', '.join(all_detectors)}",
            )

        # Executar detector
        engine = DetectionEngine()
        result = engine.analyze_single_detector(request.detector_name, taxas)

        # Converter anomalias
        anomalias_response = [_anomalia_to_response(a) for a in result.anomalias]

        # Contar por severidade
        critical_count = sum(1 for a in result.anomalias if a.severidade == Severidade.CRITICAL)
        high_count = sum(
            1 for a in result.anomalias if a.severidade in (Severidade.HIGH, Severidade.CRITICAL)
        )
        medium_count = sum(
            1
            for a in result.anomalias
            if a.severidade in (Severidade.MEDIUM, Severidade.HIGH, Severidade.CRITICAL)
        )

        return DetectionResponse(
            anomalias=anomalias_response,
            anomalias_count=len(result.anomalias),
            critical_count=critical_count,
            high_count=high_count,
            medium_count=medium_count,
            taxas_analyzed=len(taxas),
            detectors_used=[result.detector_name],
            execution_time_ms=result.execution_time_ms,
            executed_at=result.executed_at,
            detector_results=[
                DetectorResultResponse(
                    detector_name=result.detector_name,
                    success=result.success,
                    anomalias_count=len(result.anomalias),
                    execution_time_ms=result.execution_time_ms,
                    error=result.error,
                )
            ],
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Erro na análise de detector único")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erro na análise: {str(e)}",
        )


@router.get("/stats")
async def detection_stats(
    if_id: int = Query(..., description="ID da instituição financeira"),
    days: int = Query(default=30, ge=1, le=365, description="Dias para análise"),
) -> dict:
    """
    Retorna estatísticas de detecção para uma IF.

    **Nota:** Este endpoint requer acesso ao banco de dados.
    Em produção, deve ser integrado com o repository.
    """
    # TODO: Integrar com repository para buscar dados do banco
    return {
        "if_id": if_id,
        "period_days": days,
        "message": "Endpoint em desenvolvimento. Requer integração com banco de dados.",
        "status": "not_implemented",
    }
