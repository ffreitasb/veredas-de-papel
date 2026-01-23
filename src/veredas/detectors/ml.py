"""
Detectores de anomalias baseados em Machine Learning.

Implementa algoritmos de ML para detecção de anomalias:
- Isolation Forest: Detecta outliers em espaço de features
- DBSCAN: Detecta outliers baseado em densidade
"""

import logging
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Optional, Sequence

import numpy as np

from veredas.detectors.base import AnomaliaDetectada, BaseDetector, DetectionResult
from veredas.detectors.features import FeatureExtractor, TaxaFeatures, calculate_market_stats
from veredas.storage.models import Severidade, TaxaCDB, TipoAnomalia

logger = logging.getLogger(__name__)

# Importação condicional do scikit-learn
try:
    from sklearn.ensemble import IsolationForest
    from sklearn.preprocessing import StandardScaler

    HAS_SKLEARN = True
except ImportError:
    HAS_SKLEARN = False

try:
    from sklearn.cluster import DBSCAN

    HAS_DBSCAN = True
except ImportError:
    HAS_DBSCAN = False


@dataclass
class MLThresholds:
    """Thresholds configuráveis para detectores ML."""

    # Isolation Forest
    if_contamination: float = 0.05  # % esperado de anomalias (5%)
    if_n_estimators: int = 100  # Número de árvores
    if_random_state: int = 42  # Seed para reprodutibilidade
    if_score_threshold_medium: float = -0.3  # Score < -0.3 = MEDIUM
    if_score_threshold_high: float = -0.5  # Score < -0.5 = HIGH

    # DBSCAN
    dbscan_eps: float = 0.5  # Raio de vizinhança
    dbscan_min_samples: int = 5  # Mínimo de pontos no cluster
    dbscan_metric: str = "euclidean"


DEFAULT_ML_THRESHOLDS = MLThresholds()


class IsolationForestDetector(BaseDetector):
    """
    Detecta anomalias usando Isolation Forest.

    Isolation Forest isola anomalias ao invés de modelar a normalidade.
    Pontos que requerem menos splits para serem isolados são anomalias.

    Regras:
    - ISOLATION_ANOMALY (MEDIUM): Score de isolamento < -0.3
    - ISOLATION_ANOMALY (HIGH): Score de isolamento < -0.5
    """

    def __init__(
        self,
        thresholds: Optional[MLThresholds] = None,
        feature_extractor: Optional[FeatureExtractor] = None,
        min_samples: int = 30,
    ):
        """
        Inicializa o detector Isolation Forest.

        Args:
            thresholds: Thresholds de detecção.
            feature_extractor: Extrator de features customizado.
            min_samples: Mínimo de amostras para treinar o modelo.
        """
        self.thresholds = thresholds or DEFAULT_ML_THRESHOLDS
        self.feature_extractor = feature_extractor or FeatureExtractor()
        self.min_samples = min_samples
        self._model: Optional["IsolationForest"] = None
        self._scaler: Optional["StandardScaler"] = None

    @property
    def name(self) -> str:
        return "isolation_forest_detector"

    @property
    def description(self) -> str:
        return "Detecta anomalias usando Isolation Forest em espaço de features"

    def detect(self, taxas: Sequence[TaxaCDB]) -> DetectionResult:
        """
        Analisa taxas usando Isolation Forest.

        Args:
            taxas: Sequência de TaxaCDB a analisar.

        Returns:
            DetectionResult com anomalias encontradas.
        """
        start_time = datetime.now()

        if not HAS_SKLEARN:
            return DetectionResult(
                detector_name=self.name,
                anomalias=[],
                execution_time_ms=0,
                error="scikit-learn não instalado. Use: pip install scikit-learn",
            )

        if len(taxas) < self.min_samples:
            elapsed = (datetime.now() - start_time).total_seconds() * 1000
            return DetectionResult(
                detector_name=self.name,
                anomalias=[],
                execution_time_ms=elapsed,
            )

        anomalias: list[AnomaliaDetectada] = []

        try:
            # Calcular estatísticas de mercado
            market_mean, market_std = calculate_market_stats(taxas)

            # Extrair features
            features_list = self.feature_extractor.extract(
                taxas, market_mean, market_std
            )

            if len(features_list) < self.min_samples:
                elapsed = (datetime.now() - start_time).total_seconds() * 1000
                return DetectionResult(
                    detector_name=self.name,
                    anomalias=[],
                    execution_time_ms=elapsed,
                )

            # Converter para matriz
            X = np.array([f.to_array() for f in features_list])

            # Normalizar features
            self._scaler = StandardScaler()
            X_scaled = self._scaler.fit_transform(X)

            # Treinar modelo
            self._model = IsolationForest(
                contamination=self.thresholds.if_contamination,
                n_estimators=self.thresholds.if_n_estimators,
                random_state=self.thresholds.if_random_state,
            )
            self._model.fit(X_scaled)

            # Obter scores de anomalia
            scores = self._model.decision_function(X_scaled)
            predictions = self._model.predict(X_scaled)

            # Criar anomalias para outliers
            for i, (pred, score, features) in enumerate(
                zip(predictions, scores, features_list)
            ):
                if pred == -1:  # Outlier
                    anomalia = self._create_anomalia(features, score)
                    if anomalia:
                        anomalias.append(anomalia)

        except Exception as e:
            elapsed = (datetime.now() - start_time).total_seconds() * 1000
            logger.error(f"Erro no Isolation Forest: {e}")
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

    def _create_anomalia(
        self, features: TaxaFeatures, score: float
    ) -> Optional[AnomaliaDetectada]:
        """Cria anomalia baseada no score de isolamento."""
        # Determinar severidade baseado no score
        if score < self.thresholds.if_score_threshold_high:
            severidade = Severidade.HIGH
        elif score < self.thresholds.if_score_threshold_medium:
            severidade = Severidade.MEDIUM
        else:
            return None

        return AnomaliaDetectada(
            tipo=TipoAnomalia.ISOLATION_ANOMALY,
            severidade=severidade,
            valor_detectado=Decimal(str(round(features.percentual, 2))),
            desvio=Decimal(str(round(abs(score), 4))),
            descricao=(
                f"Anomalia detectada por Isolation Forest: taxa {features.percentual:.1f}% "
                f"com score de isolamento {score:.3f}"
            ),
            if_id=features.if_id,
            taxa_id=features.taxa_id,
            detector=self.name,
            detalhes={
                "isolation_score": round(score, 4),
                "data": str(features.data),
                "z_score_7d": round(features.z_score_7d, 3) if features.z_score_7d else None,
                "z_score_30d": round(features.z_score_30d, 3) if features.z_score_30d else None,
                "diff_7d": round(features.diff_7d, 2) if features.diff_7d else None,
            },
        )


class DBSCANOutlierDetector(BaseDetector):
    """
    Detecta anomalias usando DBSCAN (clustering baseado em densidade).

    DBSCAN agrupa pontos próximos e marca pontos isolados como outliers.
    Pontos que não pertencem a nenhum cluster são anomalias.

    Regras:
    - CLUSTER_OUTLIER (MEDIUM): Ponto não pertence a nenhum cluster
    - CLUSTER_OUTLIER (HIGH): Ponto muito distante do cluster mais próximo
    """

    def __init__(
        self,
        thresholds: Optional[MLThresholds] = None,
        feature_extractor: Optional[FeatureExtractor] = None,
        min_samples: int = 20,
    ):
        """
        Inicializa o detector DBSCAN.

        Args:
            thresholds: Thresholds de detecção.
            feature_extractor: Extrator de features customizado.
            min_samples: Mínimo de amostras para análise.
        """
        self.thresholds = thresholds or DEFAULT_ML_THRESHOLDS
        self.feature_extractor = feature_extractor or FeatureExtractor()
        self.min_samples = min_samples

    @property
    def name(self) -> str:
        return "dbscan_outlier_detector"

    @property
    def description(self) -> str:
        return "Detecta anomalias usando DBSCAN baseado em densidade"

    def detect(self, taxas: Sequence[TaxaCDB]) -> DetectionResult:
        """
        Analisa taxas usando DBSCAN.

        Args:
            taxas: Sequência de TaxaCDB a analisar.

        Returns:
            DetectionResult com anomalias encontradas.
        """
        start_time = datetime.now()

        if not HAS_SKLEARN or not HAS_DBSCAN:
            return DetectionResult(
                detector_name=self.name,
                anomalias=[],
                execution_time_ms=0,
                error="scikit-learn não instalado. Use: pip install scikit-learn",
            )

        if len(taxas) < self.min_samples:
            elapsed = (datetime.now() - start_time).total_seconds() * 1000
            return DetectionResult(
                detector_name=self.name,
                anomalias=[],
                execution_time_ms=elapsed,
            )

        anomalias: list[AnomaliaDetectada] = []

        try:
            # Calcular estatísticas de mercado
            market_mean, market_std = calculate_market_stats(taxas)

            # Extrair features
            features_list = self.feature_extractor.extract(
                taxas, market_mean, market_std
            )

            if len(features_list) < self.min_samples:
                elapsed = (datetime.now() - start_time).total_seconds() * 1000
                return DetectionResult(
                    detector_name=self.name,
                    anomalias=[],
                    execution_time_ms=elapsed,
                )

            # Converter para matriz
            X = np.array([f.to_array() for f in features_list])

            # Normalizar features
            scaler = StandardScaler()
            X_scaled = scaler.fit_transform(X)

            # Aplicar DBSCAN
            dbscan = DBSCAN(
                eps=self.thresholds.dbscan_eps,
                min_samples=self.thresholds.dbscan_min_samples,
                metric=self.thresholds.dbscan_metric,
            )
            labels = dbscan.fit_predict(X_scaled)

            # Encontrar outliers (label = -1)
            for i, (label, features) in enumerate(zip(labels, features_list)):
                if label == -1:  # Outlier
                    # Calcular distância ao cluster mais próximo
                    distance = self._calculate_min_cluster_distance(
                        X_scaled[i], X_scaled, labels
                    )

                    anomalia = self._create_anomalia(features, distance)
                    if anomalia:
                        anomalias.append(anomalia)

        except Exception as e:
            elapsed = (datetime.now() - start_time).total_seconds() * 1000
            logger.error(f"Erro no DBSCAN: {e}")
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

    def _calculate_min_cluster_distance(
        self, point: np.ndarray, X: np.ndarray, labels: np.ndarray
    ) -> float:
        """Calcula distância mínima do ponto aos clusters."""
        cluster_labels = set(labels) - {-1}

        if not cluster_labels:
            return 1.0  # Sem clusters, distância padrão

        min_distance = float("inf")

        for cluster_label in cluster_labels:
            cluster_points = X[labels == cluster_label]
            if len(cluster_points) > 0:
                # Distância ao centróide do cluster
                centroid = cluster_points.mean(axis=0)
                distance = np.linalg.norm(point - centroid)
                min_distance = min(min_distance, distance)

        return float(min_distance) if min_distance != float("inf") else 1.0

    def _create_anomalia(
        self, features: TaxaFeatures, distance: float
    ) -> AnomaliaDetectada:
        """Cria anomalia baseada na distância do cluster."""
        # Determinar severidade baseado na distância
        # Distância > 2.0 após normalização indica outlier mais extremo
        if distance > 2.0:
            severidade = Severidade.HIGH
        else:
            severidade = Severidade.MEDIUM

        return AnomaliaDetectada(
            tipo=TipoAnomalia.CLUSTER_OUTLIER,
            severidade=severidade,
            valor_detectado=Decimal(str(round(features.percentual, 2))),
            desvio=Decimal(str(round(distance, 4))),
            descricao=(
                f"Outlier de cluster detectado: taxa {features.percentual:.1f}% "
                f"não pertence a nenhum cluster (distância={distance:.2f})"
            ),
            if_id=features.if_id,
            taxa_id=features.taxa_id,
            detector=self.name,
            detalhes={
                "cluster_distance": round(distance, 4),
                "data": str(features.data),
                "z_score_7d": round(features.z_score_7d, 3) if features.z_score_7d else None,
                "percentile_30d": round(features.percentile_30d, 1)
                if features.percentile_30d
                else None,
            },
        )


class MLEngine:
    """
    Motor de detecção que orquestra os detectores de ML.

    Executa todos os detectores de ML e agrega os resultados.
    """

    def __init__(
        self,
        thresholds: Optional[MLThresholds] = None,
        feature_extractor: Optional[FeatureExtractor] = None,
    ):
        """
        Inicializa o motor de ML.

        Args:
            thresholds: Thresholds para todos os detectores.
            feature_extractor: Extrator de features compartilhado.
        """
        self.thresholds = thresholds or DEFAULT_ML_THRESHOLDS
        self.feature_extractor = feature_extractor or FeatureExtractor()

        self.isolation_forest_detector = IsolationForestDetector(
            thresholds=self.thresholds,
            feature_extractor=self.feature_extractor,
        )
        self.dbscan_detector = DBSCANOutlierDetector(
            thresholds=self.thresholds,
            feature_extractor=self.feature_extractor,
        )

    def analyze_isolation_forest(self, taxas: Sequence[TaxaCDB]) -> DetectionResult:
        """Executa detecção com Isolation Forest."""
        return self.isolation_forest_detector.detect(taxas)

    def analyze_dbscan(self, taxas: Sequence[TaxaCDB]) -> DetectionResult:
        """Executa detecção com DBSCAN."""
        return self.dbscan_detector.detect(taxas)

    def run_all(self, taxas: Sequence[TaxaCDB]) -> list[DetectionResult]:
        """
        Executa todos os detectores de ML.

        Args:
            taxas: Sequência de TaxaCDB a analisar.

        Returns:
            Lista de DetectionResult de cada detector.
        """
        return [
            self.analyze_isolation_forest(taxas),
            self.analyze_dbscan(taxas),
        ]
