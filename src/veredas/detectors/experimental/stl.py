"""
STLDecompositionDetector — EXPERIMENTAL.

Por que está aqui
-----------------
STL (Seasonal-Trend decomposition using LOESS) pressupõe periodicidade nos dados:
sazonalidade diária, semanal, mensal. Taxas de CDB são determinadas por decisões
discricionárias dos emissores em resposta a condições de captação — não há ciclo
sazonal. Aplicar STL a esse domínio produz "quebras de padrão sazonal" que são
artefatos do algoritmo, não sinais reais de anomalia.

Alternativa recomendada
-----------------------
ChangePointDetector (veredas.detectors.statistical): detecta mudanças de regime
usando PELT sem pressupor periodicidade, alinhado à natureza real das séries.

Precondição mínima: ≥30 observações por instituição (hardcoded em detect()).
"""

import logging
import time
from collections.abc import Sequence
from datetime import datetime
from decimal import Decimal

import pandas as pd
from statsmodels.tsa.seasonal import STL

from veredas.detectors.base import AnomaliaDetectada, BaseDetector, DetectionResult
from veredas.detectors.statistical import (
    DEFAULT_THRESHOLDS,
    StatisticalThresholds,
    _group_by_if,
    _prepare_time_series,
)
from veredas.storage.models import Severidade, TaxaCDB, TipoAnomalia

logger = logging.getLogger(__name__)


class STLDecompositionDetector(BaseDetector):
    """
    [EXPERIMENTAL] Detecta quebras de padrão sazonal via STL decomposition.

    Semântica errada para CDB — use ChangePointDetector em produção.
    Mantido para comparação e pesquisa.
    """

    def __init__(
        self,
        thresholds: StatisticalThresholds | None = None,
        min_observations: int = 14,
    ):
        self.thresholds = thresholds or DEFAULT_THRESHOLDS
        self.min_observations = min_observations

    @property
    def name(self) -> str:
        return "stl_decomposition_detector"

    @property
    def description(self) -> str:
        return "[EXPERIMENTAL] Detecta quebras de padrão sazonal via STL decomposition"

    def detect(self, taxas: Sequence[TaxaCDB]) -> DetectionResult:
        start_time = time.perf_counter()
        anomalias: list[AnomaliaDetectada] = []

        try:
            grouped = _group_by_if(taxas)

            for if_id, if_taxas in grouped.items():
                if len(if_taxas) < 30:
                    continue

                series, taxa_map = _prepare_time_series(if_taxas, if_id)

                if len(series) < 30:
                    continue

                if_anomalias = self._analyze_series(series, taxa_map, if_id)
                anomalias.extend(if_anomalias)

        except Exception as e:
            elapsed = (time.perf_counter() - start_time) * 1000
            return DetectionResult(
                detector_name=self.name,
                anomalias=[],
                execution_time_ms=elapsed,
                error=str(e),
            )

        elapsed = (time.perf_counter() - start_time) * 1000
        return DetectionResult(
            detector_name=self.name,
            anomalias=anomalias,
            execution_time_ms=elapsed,
        )

    def _analyze_series(
        self,
        series: pd.Series,
        taxa_map: dict[datetime, TaxaCDB],
        if_id: int,
    ) -> list[AnomaliaDetectada]:
        anomalias = []
        try:
            stl = STL(series, period=self.thresholds.stl_period, robust=True)
            result = stl.fit()

            residuals = result.resid
            residual_std = residuals.std()

            if residual_std == 0 or pd.isna(residual_std):
                return []

            z_scores = (residuals - residuals.mean()) / residual_std

            for date, z_score in z_scores.items():
                anomalia = self._check_residual(z_score, date, taxa_map, if_id, residual_std)
                if anomalia:
                    anomalias.append(anomalia)

        except Exception:
            logger.debug("STL falhou para IF %s (dados insuficientes ou irregulares)", if_id)

        return anomalias

    def _check_residual(
        self,
        z_score: float,
        date: datetime,
        taxa_map: dict[datetime, TaxaCDB],
        if_id: int,
        residual_std: float,
    ) -> AnomaliaDetectada | None:
        abs_z = abs(z_score)
        taxa = taxa_map.get(date)

        if abs_z > float(self.thresholds.stl_residual_high):
            return AnomaliaDetectada(
                tipo=TipoAnomalia.SEASONALITY_BREAK,
                severidade=Severidade.HIGH,
                valor_detectado=Decimal(str(taxa.percentual)) if taxa else Decimal("0"),
                desvio=Decimal(str(round(z_score, 2))),
                threshold=self.thresholds.stl_residual_high,
                descricao=(
                    f"Quebra de padrão sazonal detectada: "
                    f"resíduo {z_score:.1f}σ (>{self.thresholds.stl_residual_high}σ)"
                ),
                if_id=if_id,
                taxa_id=taxa.id if taxa else None,
                detector=self.name,
                detalhes={
                    "z_score": round(z_score, 4),
                    "residual_std": round(residual_std, 4),
                    "data": date.isoformat() if isinstance(date, datetime) else str(date),
                },
            )

        if abs_z > float(self.thresholds.stl_residual_medium):
            return AnomaliaDetectada(
                tipo=TipoAnomalia.SEASONALITY_BREAK,
                severidade=Severidade.MEDIUM,
                valor_detectado=Decimal(str(taxa.percentual)) if taxa else Decimal("0"),
                desvio=Decimal(str(round(z_score, 2))),
                threshold=self.thresholds.stl_residual_medium,
                descricao=(
                    f"Possível quebra de padrão sazonal: "
                    f"resíduo {z_score:.1f}σ (>{self.thresholds.stl_residual_medium}σ)"
                ),
                if_id=if_id,
                taxa_id=taxa.id if taxa else None,
                detector=self.name,
                detalhes={
                    "z_score": round(z_score, 4),
                    "residual_std": round(residual_std, 4),
                    "data": date.isoformat() if isinstance(date, datetime) else str(date),
                },
            )

        return None
