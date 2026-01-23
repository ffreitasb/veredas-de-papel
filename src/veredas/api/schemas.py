"""
Schemas Pydantic para a API de detecção.

Define modelos de entrada e saída para os endpoints de detecção de anomalias.
"""

from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field


class SeveridadeEnum(str, Enum):
    """Severidade das anomalias."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class TipoAnomaliaEnum(str, Enum):
    """Tipos de anomalia detectados."""

    # Fase 1 - Regras
    SPREAD_ALTO = "spread_alto"
    SPREAD_CRITICO = "spread_critico"
    SALTO_BRUSCO = "salto_brusco"
    SALTO_EXTREMO = "salto_extremo"
    DIVERGENCIA = "divergencia"
    DIVERGENCIA_EXTREMA = "divergencia_extrema"

    # Fase 3 - Estatísticos e ML
    SEASONALITY_BREAK = "seasonality_break"
    CHANGE_POINT = "change_point"
    ROLLING_OUTLIER = "rolling_outlier"
    CLUSTER_OUTLIER = "cluster_outlier"
    ISOLATION_ANOMALY = "isolation_anomaly"


class DetectorCategoryEnum(str, Enum):
    """Categorias de detectores."""

    RULES = "rules"
    STATISTICAL = "statistical"
    ML = "ml"


# ============================================================================
# Schemas de Entrada
# ============================================================================


class TaxaInput(BaseModel):
    """Taxa de CDB para análise."""

    if_id: int = Field(..., description="ID da instituição financeira")
    data_coleta: datetime = Field(..., description="Data/hora da coleta")
    indexador: str = Field(default="cdi", description="Indexador (cdi, ipca, pre)")
    # SEC-004: Range realista para CDB (50-250% do CDI)
    percentual: Decimal = Field(..., description="Percentual da taxa", ge=50, le=250)
    prazo_dias: int = Field(default=365, description="Prazo em dias", ge=1)
    taxa_id: Optional[int] = Field(default=None, description="ID da taxa no banco")


class DetectionRequest(BaseModel):
    """Requisição de detecção de anomalias."""

    taxas: list[TaxaInput] = Field(..., min_length=1, description="Taxas a analisar")
    taxas_anteriores: Optional[list[TaxaInput]] = Field(
        default=None, description="Taxas históricas para comparação"
    )

    # Configuração
    enable_rules: bool = Field(default=True, description="Habilitar detectores de regras")
    enable_statistical: bool = Field(default=True, description="Habilitar detectores estatísticos")
    enable_ml: bool = Field(default=True, description="Habilitar detectores de ML")

    # Filtros
    min_severity: SeveridadeEnum = Field(
        default=SeveridadeEnum.LOW, description="Severidade mínima para retornar"
    )
    deduplicate: bool = Field(default=True, description="Remover anomalias duplicadas")

    # Estatísticas de mercado (opcional)
    media_mercado: Optional[Decimal] = Field(
        default=None, description="Média do mercado (calculada automaticamente se não fornecida)"
    )
    desvio_padrao_mercado: Optional[Decimal] = Field(
        default=None, description="Desvio padrão do mercado"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "taxas": [
                    {
                        "if_id": 1,
                        "data_coleta": "2025-01-20T10:00:00",
                        "indexador": "cdi",
                        "percentual": 145.0,
                        "prazo_dias": 365,
                    }
                ],
                "enable_rules": True,
                "enable_statistical": True,
                "enable_ml": False,
                "min_severity": "medium",
            }
        }


class SingleDetectorRequest(BaseModel):
    """Requisição para executar um detector específico."""

    detector_name: str = Field(
        ...,
        description="Nome do detector a executar",
        examples=["spread_detector", "stl_decomposition_detector", "isolation_forest_detector"],
    )
    taxas: list[TaxaInput] = Field(..., min_length=1, description="Taxas a analisar")


# ============================================================================
# Schemas de Saída
# ============================================================================


class AnomaliaResponse(BaseModel):
    """Anomalia detectada."""

    tipo: TipoAnomaliaEnum = Field(..., description="Tipo da anomalia")
    severidade: SeveridadeEnum = Field(..., description="Severidade")
    valor_detectado: Decimal = Field(..., description="Valor que causou a anomalia")
    descricao: str = Field(..., description="Descrição da anomalia")

    # Contexto
    if_id: Optional[int] = Field(default=None, description="ID da IF")
    taxa_id: Optional[int] = Field(default=None, description="ID da taxa")

    # Valores de referência
    valor_esperado: Optional[Decimal] = Field(default=None, description="Valor esperado/médio")
    desvio: Optional[Decimal] = Field(default=None, description="Desvio (em σ ou pp)")
    threshold: Optional[Decimal] = Field(default=None, description="Threshold usado")

    # Metadados
    detector: str = Field(..., description="Detector que gerou a anomalia")
    detectado_em: datetime = Field(..., description="Quando foi detectada")
    detalhes: Optional[dict[str, Any]] = Field(default=None, description="Detalhes adicionais")

    class Config:
        json_schema_extra = {
            "example": {
                "tipo": "spread_critico",
                "severidade": "critical",
                "valor_detectado": 165.0,
                "descricao": "CDB oferecendo 165% do CDI - spread crítico (>150%)",
                "if_id": 1,
                "taxa_id": 42,
                "valor_esperado": 100.0,
                "desvio": 65.0,
                "threshold": 150.0,
                "detector": "spread_detector",
                "detectado_em": "2025-01-20T10:30:00",
            }
        }


class DetectorResultResponse(BaseModel):
    """Resultado de um detector individual."""

    detector_name: str = Field(..., description="Nome do detector")
    success: bool = Field(..., description="Se a execução foi bem sucedida")
    anomalias_count: int = Field(..., description="Número de anomalias encontradas")
    execution_time_ms: float = Field(..., description="Tempo de execução em ms")
    error: Optional[str] = Field(default=None, description="Mensagem de erro, se houver")


class DetectionResponse(BaseModel):
    """Resposta completa da detecção."""

    # Anomalias consolidadas
    anomalias: list[AnomaliaResponse] = Field(..., description="Anomalias encontradas")
    anomalias_count: int = Field(..., description="Total de anomalias")

    # Contagens por severidade
    critical_count: int = Field(..., description="Anomalias críticas")
    high_count: int = Field(..., description="Anomalias HIGH ou CRITICAL")
    medium_count: int = Field(..., description="Anomalias MEDIUM ou acima")

    # Metadados
    taxas_analyzed: int = Field(..., description="Número de taxas analisadas")
    detectors_used: list[str] = Field(..., description="Detectores executados")
    execution_time_ms: float = Field(..., description="Tempo total de execução")
    executed_at: datetime = Field(..., description="Quando a análise foi executada")

    # Resultados por detector
    detector_results: list[DetectorResultResponse] = Field(
        ..., description="Resultado de cada detector"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "anomalias": [],
                "anomalias_count": 2,
                "critical_count": 1,
                "high_count": 2,
                "medium_count": 2,
                "taxas_analyzed": 30,
                "detectors_used": ["spread_detector", "rolling_zscore_detector"],
                "execution_time_ms": 125.5,
                "executed_at": "2025-01-20T10:30:00",
                "detector_results": [
                    {
                        "detector_name": "spread_detector",
                        "success": True,
                        "anomalias_count": 1,
                        "execution_time_ms": 5.2,
                    }
                ],
            }
        }


class AvailableDetectorsResponse(BaseModel):
    """Lista de detectores disponíveis."""

    rules: list[str] = Field(..., description="Detectores de regras")
    statistical: list[str] = Field(..., description="Detectores estatísticos")
    ml: list[str] = Field(..., description="Detectores de ML")


class HealthResponse(BaseModel):
    """Status de saúde do serviço de detecção."""

    status: str = Field(..., description="Status do serviço")
    version: str = Field(..., description="Versão do veredas")
    detectors_available: int = Field(..., description="Número de detectores disponíveis")
    ml_available: bool = Field(..., description="Se sklearn está disponível")
    ruptures_available: bool = Field(..., description="Se ruptures está disponível")
