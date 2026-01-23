"""
Detectores estatísticos de anomalias em séries temporais.

Implementa algoritmos estatísticos para detecção de anomalias:
- STL Decomposition: Detecta quebra de padrão sazonal
- Change Point Detection: Detecta mudanças estruturais (ruptures PELT)
- Rolling Z-Score: Detecta outliers locais em janelas móveis
"""

from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Optional, Sequence

import numpy as np
import pandas as pd
from statsmodels.tsa.seasonal import STL

from veredas.detectors.base import AnomaliaDetectada, BaseDetector, DetectionResult
from veredas.storage.models import Severidade, TaxaCDB, TipoAnomalia

# Importação condicional do ruptures (opcional dependency)
try:
    import ruptures as rpt

    HAS_RUPTURES = True
except ImportError:
    HAS_RUPTURES = False


@dataclass
class StatisticalThresholds:
    """Thresholds configuráveis para os detectores estatísticos."""

    # STL Decomposition
    stl_period: int = 5  # Período sazonal (dias úteis)
    stl_residual_medium: Decimal = Decimal("2.5")  # > 2.5σ = MEDIUM
    stl_residual_high: Decimal = Decimal("3.5")  # > 3.5σ = HIGH

    # Change Point Detection
    changepoint_penalty: float = 10.0  # Penalidade PELT (maior = menos sensível)
    changepoint_min_size: int = 5  # Tamanho mínimo do segmento

    # Rolling Z-Score
    rolling_window: int = 14  # Janela de 14 dias
    rolling_z_medium: Decimal = Decimal("2.5")  # > 2.5σ = MEDIUM
    rolling_z_high: Decimal = Decimal("3.5")  # > 3.5σ = HIGH


# Thresholds padrão
DEFAULT_THRESHOLDS = StatisticalThresholds()


def _prepare_time_series(
    taxas: Sequence[TaxaCDB], if_id: int
) -> tuple[pd.Series, dict[datetime, TaxaCDB]]:
    """
    Prepara série temporal de taxas para uma instituição.

    Args:
        taxas: Sequência de TaxaCDB.
        if_id: ID da instituição financeira.

    Returns:
        Tupla com (série temporal indexada por data, mapa data->taxa).
    """
    # Filtrar taxas da IF
    if_taxas = [t for t in taxas if t.if_id == if_id]

    if not if_taxas:
        return pd.Series(dtype=float), {}

    # Ordenar por data (BUG-001: usar sorted() para não mutar lista original)
    if_taxas = sorted(if_taxas, key=lambda t: t.data_coleta)

    # Criar série temporal
    dates = [t.data_coleta for t in if_taxas]
    values = [float(t.percentual) for t in if_taxas]

    series = pd.Series(values, index=pd.DatetimeIndex(dates))

    # Mapa para recuperar taxa original
    taxa_map = {t.data_coleta: t for t in if_taxas}

    return series, taxa_map


def _group_by_if(taxas: Sequence[TaxaCDB]) -> dict[int, list[TaxaCDB]]:
    """Agrupa taxas por instituição financeira."""
    grouped: dict[int, list[TaxaCDB]] = defaultdict(list)
    for taxa in taxas:
        grouped[taxa.if_id].append(taxa)
    return grouped


class STLDecompositionDetector(BaseDetector):
    """
    Detecta quebras de padrão sazonal usando STL Decomposition.

    O STL (Seasonal-Trend decomposition using LOESS) decompõe a série
    temporal em tendência, sazonalidade e resíduos. Resíduos anormalmente
    altos indicam anomalias.

    Regras:
    - SEASONALITY_BREAK (MEDIUM): Resíduo > 2.5σ
    - SEASONALITY_BREAK (HIGH): Resíduo > 3.5σ
    """

    def __init__(
        self,
        thresholds: Optional[StatisticalThresholds] = None,
        min_observations: int = 14,
    ):
        """
        Inicializa o detector STL.

        Args:
            thresholds: Thresholds de detecção.
            min_observations: Mínimo de observações para análise.
        """
        self.thresholds = thresholds or DEFAULT_THRESHOLDS
        self.min_observations = min_observations

    @property
    def name(self) -> str:
        return "stl_decomposition_detector"

    @property
    def description(self) -> str:
        return "Detecta quebras de padrão sazonal via STL decomposition"

    def detect(self, taxas: Sequence[TaxaCDB]) -> DetectionResult:
        """
        Analisa séries temporais de taxas e detecta anomalias sazonais.

        Args:
            taxas: Sequência de TaxaCDB a analisar.

        Returns:
            DetectionResult com anomalias encontradas.
        """
        start_time = datetime.now()
        anomalias: list[AnomaliaDetectada] = []

        try:
            # Agrupar por IF
            grouped = _group_by_if(taxas)

            for if_id, if_taxas in grouped.items():
                if len(if_taxas) < self.min_observations:
                    continue

                # Preparar série temporal
                series, taxa_map = _prepare_time_series(if_taxas, if_id)

                if len(series) < self.min_observations:
                    continue

                # Detectar anomalias para esta IF
                if_anomalias = self._analyze_series(series, taxa_map, if_id)
                anomalias.extend(if_anomalias)

        except Exception as e:
            elapsed = (datetime.now() - start_time).total_seconds() * 1000
            return DetectionResult(
                detector_name=self.name,
                anomalias=[],
                execution_time_ms=elapsed,
                error=str(e),
            )

        elapsed = (datetime.now() - start_time).total_seconds() * 1000
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
        """Analisa uma série temporal com STL."""
        anomalias = []

        try:
            # Aplicar STL
            stl = STL(
                series,
                period=self.thresholds.stl_period,
                robust=True,
            )
            result = stl.fit()

            # Calcular estatísticas dos resíduos
            residuals = result.resid
            residual_std = residuals.std()

            if residual_std == 0:
                return []

            # Calcular z-scores dos resíduos
            z_scores = (residuals - residuals.mean()) / residual_std

            # Verificar cada ponto
            for date, z_score in z_scores.items():
                anomalia = self._check_residual(
                    z_score=z_score,
                    date=date,
                    taxa_map=taxa_map,
                    if_id=if_id,
                    residual_std=residual_std,
                )
                if anomalia:
                    anomalias.append(anomalia)

        except Exception:
            # STL pode falhar com dados insuficientes ou irregulares
            pass

        return anomalias

    def _check_residual(
        self,
        z_score: float,
        date: datetime,
        taxa_map: dict[datetime, TaxaCDB],
        if_id: int,
        residual_std: float,
    ) -> Optional[AnomaliaDetectada]:
        """Verifica se um resíduo é anômalo."""
        abs_z = abs(z_score)
        taxa = taxa_map.get(date)

        # HIGH: > 3.5σ
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

        # MEDIUM: > 2.5σ
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


class ChangePointDetector(BaseDetector):
    """
    Detecta mudanças estruturais na série temporal usando PELT.

    O algoritmo PELT (Pruned Exact Linear Time) identifica pontos onde
    há uma mudança significativa na distribuição dos dados.

    Requer a biblioteca `ruptures` (opcional dependency: pip install ruptures).

    Regras:
    - CHANGE_POINT (HIGH): Mudança estrutural detectada
    """

    def __init__(
        self,
        thresholds: Optional[StatisticalThresholds] = None,
        model: str = "rbf",
        min_observations: int = 20,
    ):
        """
        Inicializa o detector de change points.

        Args:
            thresholds: Thresholds de detecção.
            model: Modelo de custo ('rbf', 'l2', 'linear').
            min_observations: Mínimo de observações para análise.
        """
        self.thresholds = thresholds or DEFAULT_THRESHOLDS
        self.model = model
        self.min_observations = min_observations

    @property
    def name(self) -> str:
        return "change_point_detector"

    @property
    def description(self) -> str:
        return "Detecta mudanças estruturais na série temporal via PELT"

    def detect(self, taxas: Sequence[TaxaCDB]) -> DetectionResult:
        """
        Analisa séries temporais e detecta change points.

        Args:
            taxas: Sequência de TaxaCDB a analisar.

        Returns:
            DetectionResult com anomalias encontradas.
        """
        start_time = datetime.now()

        if not HAS_RUPTURES:
            return DetectionResult(
                detector_name=self.name,
                anomalias=[],
                execution_time_ms=0,
                error="Biblioteca ruptures não instalada. Use: pip install ruptures",
            )

        anomalias: list[AnomaliaDetectada] = []

        try:
            # Agrupar por IF
            grouped = _group_by_if(taxas)

            for if_id, if_taxas in grouped.items():
                if len(if_taxas) < self.min_observations:
                    continue

                # Preparar série temporal
                series, taxa_map = _prepare_time_series(if_taxas, if_id)

                if len(series) < self.min_observations:
                    continue

                # Detectar change points
                if_anomalias = self._detect_change_points(series, taxa_map, if_id)
                anomalias.extend(if_anomalias)

        except Exception as e:
            elapsed = (datetime.now() - start_time).total_seconds() * 1000
            return DetectionResult(
                detector_name=self.name,
                anomalias=[],
                execution_time_ms=elapsed,
                error=str(e),
            )

        elapsed = (datetime.now() - start_time).total_seconds() * 1000
        return DetectionResult(
            detector_name=self.name,
            anomalias=anomalias,
            execution_time_ms=elapsed,
        )

    def _detect_change_points(
        self,
        series: pd.Series,
        taxa_map: dict[datetime, TaxaCDB],
        if_id: int,
    ) -> list[AnomaliaDetectada]:
        """Detecta change points em uma série temporal."""
        anomalias = []

        # Converter para array numpy
        signal = series.values.reshape(-1, 1)
        dates = list(series.index)

        # Aplicar PELT
        algo = rpt.Pelt(model=self.model, min_size=self.thresholds.changepoint_min_size)
        algo.fit(signal)

        try:
            # Detectar change points
            change_points = algo.predict(pen=self.thresholds.changepoint_penalty)

            # Remover o último ponto (sempre é o tamanho da série)
            change_points = [cp for cp in change_points if cp < len(series)]

            # Criar anomalia para cada change point
            for cp_idx in change_points:
                if cp_idx >= len(dates):
                    continue

                date = dates[cp_idx]
                taxa = taxa_map.get(date)

                # Calcular magnitude da mudança
                before_mean = np.mean(signal[max(0, cp_idx - 5) : cp_idx])
                after_mean = np.mean(signal[cp_idx : min(len(signal), cp_idx + 5)])
                magnitude = abs(after_mean - before_mean)

                anomalia = AnomaliaDetectada(
                    tipo=TipoAnomalia.CHANGE_POINT,
                    severidade=Severidade.HIGH,
                    valor_detectado=Decimal(str(taxa.percentual)) if taxa else Decimal("0"),
                    desvio=Decimal(str(round(magnitude, 2))),
                    descricao=(
                        f"Mudança estrutural detectada: "
                        f"média {before_mean:.1f}% → {after_mean:.1f}% "
                        f"(variação de {magnitude:.1f}pp)"
                    ),
                    if_id=if_id,
                    taxa_id=taxa.id if taxa else None,
                    detector=self.name,
                    detalhes={
                        "change_point_index": cp_idx,
                        "before_mean": round(before_mean, 4),
                        "after_mean": round(after_mean, 4),
                        "magnitude": round(magnitude, 4),
                        "data": date.isoformat() if isinstance(date, datetime) else str(date),
                        "penalty": self.thresholds.changepoint_penalty,
                    },
                )
                anomalias.append(anomalia)

        except Exception:
            # PELT pode falhar com dados insuficientes
            pass

        return anomalias


class RollingZScoreDetector(BaseDetector):
    """
    Detecta outliers locais usando Z-score em janela móvel.

    Calcula a média e desvio padrão móveis, e identifica pontos
    que se desviam significativamente.

    Regras:
    - ROLLING_OUTLIER (MEDIUM): Z-score > 2.5
    - ROLLING_OUTLIER (HIGH): Z-score > 3.5
    """

    def __init__(
        self,
        thresholds: Optional[StatisticalThresholds] = None,
        min_observations: int = 7,
    ):
        """
        Inicializa o detector de rolling z-score.

        Args:
            thresholds: Thresholds de detecção.
            min_observations: Mínimo de observações para análise.
        """
        self.thresholds = thresholds or DEFAULT_THRESHOLDS
        self.min_observations = min_observations

    @property
    def name(self) -> str:
        return "rolling_zscore_detector"

    @property
    def description(self) -> str:
        return f"Detecta outliers locais com janela móvel de {self.thresholds.rolling_window} dias"

    def detect(self, taxas: Sequence[TaxaCDB]) -> DetectionResult:
        """
        Analisa séries temporais e detecta outliers locais.

        Args:
            taxas: Sequência de TaxaCDB a analisar.

        Returns:
            DetectionResult com anomalias encontradas.
        """
        start_time = datetime.now()
        anomalias: list[AnomaliaDetectada] = []

        try:
            # Agrupar por IF
            grouped = _group_by_if(taxas)

            for if_id, if_taxas in grouped.items():
                if len(if_taxas) < self.min_observations:
                    continue

                # Preparar série temporal
                series, taxa_map = _prepare_time_series(if_taxas, if_id)

                if len(series) < self.min_observations:
                    continue

                # Detectar outliers
                if_anomalias = self._analyze_rolling(series, taxa_map, if_id)
                anomalias.extend(if_anomalias)

        except Exception as e:
            elapsed = (datetime.now() - start_time).total_seconds() * 1000
            return DetectionResult(
                detector_name=self.name,
                anomalias=[],
                execution_time_ms=elapsed,
                error=str(e),
            )

        elapsed = (datetime.now() - start_time).total_seconds() * 1000
        return DetectionResult(
            detector_name=self.name,
            anomalias=anomalias,
            execution_time_ms=elapsed,
        )

    def _analyze_rolling(
        self,
        series: pd.Series,
        taxa_map: dict[datetime, TaxaCDB],
        if_id: int,
    ) -> list[AnomaliaDetectada]:
        """Analisa série com rolling z-score."""
        anomalias = []
        window = self.thresholds.rolling_window

        # Calcular rolling mean e std
        rolling_mean = series.rolling(window=window, min_periods=3).mean()
        rolling_std = series.rolling(window=window, min_periods=3).std()

        # Calcular z-scores
        z_scores = (series - rolling_mean) / rolling_std

        # Verificar cada ponto
        for date, z_score in z_scores.items():
            if pd.isna(z_score):
                continue

            taxa = taxa_map.get(date)
            anomalia = self._check_zscore(
                z_score=z_score,
                date=date,
                taxa=taxa,
                if_id=if_id,
                rolling_mean=rolling_mean.get(date),
                rolling_std=rolling_std.get(date),
            )
            if anomalia:
                anomalias.append(anomalia)

        return anomalias

    def _check_zscore(
        self,
        z_score: float,
        date: datetime,
        taxa: Optional[TaxaCDB],
        if_id: int,
        rolling_mean: Optional[float],
        rolling_std: Optional[float],
    ) -> Optional[AnomaliaDetectada]:
        """Verifica se um z-score indica anomalia."""
        abs_z = abs(z_score)

        # HIGH: > 3.5σ
        if abs_z > float(self.thresholds.rolling_z_high):
            return AnomaliaDetectada(
                tipo=TipoAnomalia.ROLLING_OUTLIER,
                severidade=Severidade.HIGH,
                valor_detectado=Decimal(str(taxa.percentual)) if taxa else Decimal("0"),
                valor_esperado=Decimal(str(round(rolling_mean, 2))) if rolling_mean else None,
                desvio=Decimal(str(round(z_score, 2))),
                threshold=self.thresholds.rolling_z_high,
                descricao=(
                    f"Outlier local severo: taxa {z_score:.1f}σ "
                    f"acima da média móvel (>{self.thresholds.rolling_z_high}σ)"
                ),
                if_id=if_id,
                taxa_id=taxa.id if taxa else None,
                detector=self.name,
                detalhes={
                    "z_score": round(z_score, 4),
                    "rolling_mean": round(rolling_mean, 4) if rolling_mean else None,
                    "rolling_std": round(rolling_std, 4) if rolling_std else None,
                    "window_size": self.thresholds.rolling_window,
                    "data": date.isoformat() if isinstance(date, datetime) else str(date),
                },
            )

        # MEDIUM: > 2.5σ
        if abs_z > float(self.thresholds.rolling_z_medium):
            return AnomaliaDetectada(
                tipo=TipoAnomalia.ROLLING_OUTLIER,
                severidade=Severidade.MEDIUM,
                valor_detectado=Decimal(str(taxa.percentual)) if taxa else Decimal("0"),
                valor_esperado=Decimal(str(round(rolling_mean, 2))) if rolling_mean else None,
                desvio=Decimal(str(round(z_score, 2))),
                threshold=self.thresholds.rolling_z_medium,
                descricao=(
                    f"Outlier local: taxa {z_score:.1f}σ "
                    f"acima da média móvel (>{self.thresholds.rolling_z_medium}σ)"
                ),
                if_id=if_id,
                taxa_id=taxa.id if taxa else None,
                detector=self.name,
                detalhes={
                    "z_score": round(z_score, 4),
                    "rolling_mean": round(rolling_mean, 4) if rolling_mean else None,
                    "rolling_std": round(rolling_std, 4) if rolling_std else None,
                    "window_size": self.thresholds.rolling_window,
                    "data": date.isoformat() if isinstance(date, datetime) else str(date),
                },
            )

        return None


class StatisticalEngine:
    """
    Motor de detecção que orquestra os detectores estatísticos.

    Executa todos os detectores estatísticos e agrega os resultados.
    """

    def __init__(self, thresholds: Optional[StatisticalThresholds] = None):
        """
        Inicializa o motor estatístico.

        Args:
            thresholds: Thresholds para todos os detectores.
        """
        self.thresholds = thresholds or DEFAULT_THRESHOLDS
        self.stl_detector = STLDecompositionDetector(thresholds=self.thresholds)
        self.change_point_detector = ChangePointDetector(thresholds=self.thresholds)
        self.rolling_zscore_detector = RollingZScoreDetector(thresholds=self.thresholds)

    def analyze_seasonality(self, taxas: Sequence[TaxaCDB]) -> DetectionResult:
        """Executa detecção de quebras sazonais com STL."""
        return self.stl_detector.detect(taxas)

    def analyze_change_points(self, taxas: Sequence[TaxaCDB]) -> DetectionResult:
        """Executa detecção de change points com PELT."""
        return self.change_point_detector.detect(taxas)

    def analyze_local_outliers(self, taxas: Sequence[TaxaCDB]) -> DetectionResult:
        """Executa detecção de outliers locais com rolling z-score."""
        return self.rolling_zscore_detector.detect(taxas)

    def run_all(self, taxas: Sequence[TaxaCDB]) -> list[DetectionResult]:
        """
        Executa todos os detectores estatísticos.

        Args:
            taxas: Sequência de TaxaCDB a analisar.

        Returns:
            Lista de DetectionResult de cada detector.
        """
        return [
            self.analyze_seasonality(taxas),
            self.analyze_change_points(taxas),
            self.analyze_local_outliers(taxas),
        ]
