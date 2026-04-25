"""
Motor de detecção unificado.

Orquestra todos os detectores de anomalias (regras, estatísticos e ML)
em uma interface única e consistente.
"""

import logging
import time
from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from enum import StrEnum

from veredas import TZ_BRASIL
from veredas.catalog import TIER_SPREAD_THRESHOLDS, get_tier_emissor
from veredas.detectors.base import AnomaliaDetectada, DetectionResult
from veredas.detectors.features import FeatureExtractor, calculate_market_stats
from veredas.detectors.ml import DBSCANOutlierDetector, IsolationForestDetector, MLThresholds
from veredas.detectors.rules import (
    RuleBasedEngine,
    RuleThresholds,
)
from veredas.detectors.experimental.stl import STLDecompositionDetector
from veredas.detectors.statistical import (
    ChangePointDetector,
    RollingZScoreDetector,
    StatisticalThresholds,
)
from veredas.storage.models import Severidade, TaxaCDB

logger = logging.getLogger(__name__)

# PERF-007: Constante de módulo (evita recriação em cada chamada)
SEVERITY_ORDER = [Severidade.LOW, Severidade.MEDIUM, Severidade.HIGH, Severidade.CRITICAL]

# Mapeamento detector → categoria para votação cruzada (ENG-01).
# Detectores da mesma categoria não são evidência independente.
_DETECTOR_CATEGORY: dict[str, str] = {
    "spread_detector": "rules",
    "variacao_detector": "rules",
    "divergencia_detector": "rules",
    "stl_decomposition_detector": "statistical",
    "change_point_detector": "statistical",
    "rolling_zscore_detector": "statistical",
    "isolation_forest_detector": "ml",
    "dbscan_outlier_detector": "ml",
}


class DetectorCategory(StrEnum):
    """Categorias de detectores disponíveis."""

    RULES = "rules"
    STATISTICAL = "statistical"
    ML = "ml"


@dataclass
class EngineConfig:
    """Configuração do motor de detecção."""

    # Quais categorias de detectores usar
    enable_rules: bool = True
    enable_statistical: bool = False
    enable_ml: bool = True

    # Detectores específicos (se False, usa todos da categoria)
    detectors: dict[DetectorCategory, list[str]] = field(default_factory=dict)

    # Thresholds
    rule_thresholds: RuleThresholds | None = None
    statistical_thresholds: StatisticalThresholds | None = None
    ml_thresholds: MLThresholds | None = None

    # Filtros de saída
    min_severity: Severidade = Severidade.LOW
    deduplicate: bool = True  # Remove anomalias duplicadas entre detectores

    # Mínimo de dados
    min_observations_statistical: int = 14
    min_observations_ml: int = 30

    # L4 FIX: Timeout configurável para detecção (ms)
    detection_timeout_ms: int = 30000  # 30 segundos padrão


@dataclass
class EngineResult:
    """Resultado consolidado do motor de detecção."""

    # Resultados por detector
    results: list[DetectionResult]

    # Anomalias consolidadas (após dedup e filtros)
    anomalias: list[AnomaliaDetectada]

    # Metadados
    executed_at: datetime = field(default_factory=lambda: datetime.now(TZ_BRASIL))
    execution_time_ms: float = 0
    detectors_used: list[str] = field(default_factory=list)
    taxas_analyzed: int = 0

    @property
    def has_anomalias(self) -> bool:
        """Verifica se foram encontradas anomalias."""
        return len(self.anomalias) > 0

    @property
    def critical_count(self) -> int:
        """Conta anomalias críticas."""
        return sum(1 for a in self.anomalias if a.severidade == Severidade.CRITICAL)

    @property
    def high_count(self) -> int:
        """Conta anomalias HIGH ou CRITICAL."""
        return sum(
            1 for a in self.anomalias if a.severidade in (Severidade.HIGH, Severidade.CRITICAL)
        )

    @property
    def medium_count(self) -> int:
        """Conta anomalias MEDIUM ou acima."""
        return sum(
            1
            for a in self.anomalias
            if a.severidade in (Severidade.MEDIUM, Severidade.HIGH, Severidade.CRITICAL)
        )

    def by_severity(self, severity: Severidade) -> list[AnomaliaDetectada]:
        """Filtra anomalias por severidade."""
        return [a for a in self.anomalias if a.severidade == severity]

    def by_if(self, if_id: int) -> list[AnomaliaDetectada]:
        """Filtra anomalias por instituição financeira."""
        return [a for a in self.anomalias if a.if_id == if_id]


class DetectionEngine:
    """
    Motor unificado de detecção de anomalias.

    Orquestra todos os detectores (regras, estatísticos e ML) e consolida
    os resultados em uma interface única.

    Exemplo de uso:
        ```python
        engine = DetectionEngine()
        result = engine.analyze(taxas_atuais, taxas_anteriores)

        for anomalia in result.anomalias:
            print(f"{anomalia.tipo}: {anomalia.descricao}")
        ```
    """

    def __init__(self, config: EngineConfig | None = None):
        """
        Inicializa o motor de detecção.

        Args:
            config: Configuração do motor. Se não fornecida, usa defaults.
        """
        self.config = config or EngineConfig()
        self._setup_detectors()

    def _setup_detectors(self) -> None:
        """Configura os detectores baseado na configuração."""
        # Rules
        self.rule_engine = RuleBasedEngine(self.config.rule_thresholds)

        # Statistical
        stat_thresholds = self.config.statistical_thresholds or StatisticalThresholds()
        self.stl_detector = STLDecompositionDetector(
            thresholds=stat_thresholds,
            min_observations=self.config.min_observations_statistical,
        )
        self.change_point_detector = ChangePointDetector(
            thresholds=stat_thresholds,
            min_observations=self.config.min_observations_statistical + 6,
        )
        self.rolling_zscore_detector = RollingZScoreDetector(
            thresholds=stat_thresholds,
            min_observations=7,
        )

        # ML
        ml_thresholds = self.config.ml_thresholds or MLThresholds()
        feature_extractor = FeatureExtractor()
        self.isolation_forest_detector = IsolationForestDetector(
            thresholds=ml_thresholds,
            feature_extractor=feature_extractor,
            min_samples=self.config.min_observations_ml,
        )
        self.dbscan_detector = DBSCANOutlierDetector(
            thresholds=ml_thresholds,
            feature_extractor=feature_extractor,
            min_samples=self.config.min_observations_ml - 10,
        )

    def analyze(
        self,
        taxas_atuais: Sequence[TaxaCDB],
        taxas_anteriores: Sequence[TaxaCDB] | None = None,
        media_mercado: Decimal | None = None,
        desvio_padrao_mercado: Decimal | None = None,
        if_cnpj_map: dict[int, str] | None = None,
    ) -> EngineResult:
        """
        Executa análise completa de detecção de anomalias.

        Args:
            taxas_atuais: Taxas mais recentes a analisar.
            taxas_anteriores: Taxas históricas para comparação (opcional).
            media_mercado: Média do mercado para divergência (opcional, calculada se não fornecida).
            desvio_padrao_mercado: Desvio padrão do mercado (opcional, calculado se não fornecido).
            if_cnpj_map: Mapa if_id → CNPJ para thresholds por tier (opcional).

        Returns:
            EngineResult com todas as anomalias encontradas.
        """
        start_time = time.perf_counter()

        if media_mercado is None or desvio_padrao_mercado is None:
            market_mean, market_std = calculate_market_stats(taxas_atuais)
            if media_mercado is None:
                media_mercado = Decimal(str(round(market_mean, 4)))
            if desvio_padrao_mercado is None:
                desvio_padrao_mercado = Decimal(str(round(market_std, 4)))

        all_taxas = list(taxas_anteriores or []) + list(taxas_atuais)
        tier_thresholds_map = self._build_tier_thresholds(if_cnpj_map)

        results: list[DetectionResult] = []
        detectors_used: list[str] = []

        if self.config.enable_rules:
            r, d = self._run_rules(
                taxas_atuais,
                taxas_anteriores,
                media_mercado,
                desvio_padrao_mercado,
                tier_thresholds_map,
            )
            results.extend(r)
            detectors_used.extend(d)

        if self.config.enable_statistical:
            r, d = self._run_statistical(all_taxas)
            results.extend(r)
            detectors_used.extend(d)

        if self.config.enable_ml:
            r, d = self._run_ml(all_taxas)
            results.extend(r)
            detectors_used.extend(d)

        anomalias = self._consolidate_anomalias(results)
        elapsed = (time.perf_counter() - start_time) * 1000

        return EngineResult(
            results=results,
            anomalias=anomalias,
            execution_time_ms=elapsed,
            detectors_used=detectors_used,
            taxas_analyzed=len(taxas_atuais),
        )

    def _build_tier_thresholds(
        self, if_cnpj_map: dict[int, str] | None
    ) -> dict[int, RuleThresholds] | None:
        if not if_cnpj_map:
            return None
        return {
            if_id: RuleThresholds(**TIER_SPREAD_THRESHOLDS[get_tier_emissor(cnpj)])
            for if_id, cnpj in if_cnpj_map.items()
        }

    def _run_rules(
        self,
        taxas_atuais: Sequence[TaxaCDB],
        taxas_anteriores: Sequence[TaxaCDB] | None,
        media_mercado: Decimal,
        desvio_padrao_mercado: Decimal,
        tier_thresholds_map: dict[int, RuleThresholds] | None,
    ) -> tuple[list[DetectionResult], list[str]]:
        results: list[DetectionResult] = []
        detectors_used: list[str] = []

        if self._should_run("rules", "spread_detector"):
            results.append(
                self.rule_engine.analyze_spreads(taxas_atuais, tier_thresholds=tier_thresholds_map)
            )
            detectors_used.append("spread_detector")

        if self._should_run("rules", "variacao_detector") and taxas_anteriores:
            results.append(self.rule_engine.analyze_variacoes(taxas_atuais, taxas_anteriores))
            detectors_used.append("variacao_detector")

        if self._should_run("rules", "divergencia_detector"):
            results.append(
                self.rule_engine.analyze_divergencias(
                    taxas_atuais, media_mercado, desvio_padrao_mercado
                )
            )
            detectors_used.append("divergencia_detector")

        return results, detectors_used

    def _run_statistical(self, all_taxas: list[TaxaCDB]) -> tuple[list[DetectionResult], list[str]]:
        results: list[DetectionResult] = []
        detectors_used: list[str] = []

        if len(all_taxas) < self.config.min_observations_statistical:
            return results, detectors_used

        if self._should_run("statistical", "stl_decomposition_detector"):
            results.append(self.stl_detector.detect(all_taxas))
            detectors_used.append("stl_decomposition_detector")

        if self._should_run("statistical", "change_point_detector"):
            results.append(self.change_point_detector.detect(all_taxas))
            detectors_used.append("change_point_detector")

        if self._should_run("statistical", "rolling_zscore_detector"):
            results.append(self.rolling_zscore_detector.detect(all_taxas))
            detectors_used.append("rolling_zscore_detector")

        return results, detectors_used

    def _run_ml(self, all_taxas: list[TaxaCDB]) -> tuple[list[DetectionResult], list[str]]:
        results: list[DetectionResult] = []
        detectors_used: list[str] = []

        if len(all_taxas) < self.config.min_observations_ml:
            return results, detectors_used

        run_if = self._should_run("ml", "isolation_forest_detector")
        run_dbscan = self._should_run("ml", "dbscan_outlier_detector")

        if not (run_if or run_dbscan):
            return results, detectors_used

        # PERF-006: Extrair features uma vez e compartilhar entre detectores
        ml_market_mean, ml_market_std = calculate_market_stats(all_taxas)
        shared_features = self.isolation_forest_detector.feature_extractor.extract(
            all_taxas, ml_market_mean, ml_market_std
        )

        if run_if:
            results.append(self.isolation_forest_detector.detect_with_features(shared_features))
            detectors_used.append("isolation_forest_detector")

        if run_dbscan:
            results.append(self.dbscan_detector.detect_with_features(shared_features))
            detectors_used.append("dbscan_outlier_detector")

        return results, detectors_used

    def analyze_single_detector(
        self,
        detector_name: str,
        taxas: Sequence[TaxaCDB],
        **kwargs,
    ) -> DetectionResult:
        """
        Executa apenas um detector específico.

        Args:
            detector_name: Nome do detector a executar.
            taxas: Taxas a analisar.
            **kwargs: Argumentos adicionais para o detector.

        Returns:
            DetectionResult do detector.
        """
        # BUG-011: Mapa completo incluindo variacao_detector e divergencia_detector
        detector_map = {
            # Rules
            "spread_detector": lambda: self.rule_engine.spread_detector.detect(taxas),
            "variacao_detector": lambda: self.rule_engine.variacao_detector.detect(
                taxas, kwargs.get("taxas_anteriores", [])
            ),
            "divergencia_detector": lambda: self.rule_engine.divergencia_detector.detect(
                taxas,
                kwargs.get("media_mercado"),
                kwargs.get("desvio_padrao_mercado"),
            ),
            # Statistical
            "stl_decomposition_detector": lambda: self.stl_detector.detect(taxas),
            "change_point_detector": lambda: self.change_point_detector.detect(taxas),
            "rolling_zscore_detector": lambda: self.rolling_zscore_detector.detect(taxas),
            # ML
            "isolation_forest_detector": lambda: self.isolation_forest_detector.detect(taxas),
            "dbscan_outlier_detector": lambda: self.dbscan_detector.detect(taxas),
        }

        if detector_name not in detector_map:
            return DetectionResult(
                detector_name=detector_name,
                anomalias=[],
                error=f"Detector '{detector_name}' não encontrado",
            )

        return detector_map[detector_name]()

    def _should_run(self, category: str, detector_name: str) -> bool:
        """Verifica se um detector específico deve ser executado."""
        cat_key = DetectorCategory(category)
        if cat_key not in self.config.detectors:
            return True  # Se não especificado, executa todos
        return detector_name in self.config.detectors[cat_key]

    def _consolidate_anomalias(self, results: list[DetectionResult]) -> list[AnomaliaDetectada]:
        """Consolida anomalias de múltiplos detectores."""
        all_anomalias: list[AnomaliaDetectada] = []

        for result in results:
            if result.success:
                all_anomalias.extend(result.anomalias)

        # Filtrar por severidade mínima (PERF-007: usa constante de módulo)
        min_idx = SEVERITY_ORDER.index(self.config.min_severity)
        all_anomalias = [a for a in all_anomalias if SEVERITY_ORDER.index(a.severidade) >= min_idx]

        # Deduplicar se configurado
        if self.config.deduplicate:
            all_anomalias = self._deduplicate(all_anomalias)

        # Ordenar por severidade (mais críticas primeiro) e depois por data
        # BUG-012: Tratar detectado_em None para evitar TypeError na comparação
        all_anomalias.sort(
            key=lambda a: (
                -SEVERITY_ORDER.index(a.severidade),
                a.detectado_em or datetime.min,
            )
        )

        return all_anomalias

    def _deduplicate(self, anomalias: list[AnomaliaDetectada]) -> list[AnomaliaDetectada]:
        """Remove anomalias duplicadas com votação ponderada por categorias distintas.

        Elevação de severidade ocorre apenas quando detectores de *categorias*
        diferentes concordam (rules, statistical, ml). Dois detectores da mesma
        categoria não são evidência independente — e.g., IsolationForest + DBSCAN
        ambos encontrando a mesma taxa não é cruzamento de metodologias.

        - 1 categoria   → severidade original
        - 2 categorias  → +1 nível (MEDIUM → HIGH)
        - 3+ categorias → +2 níveis (MEDIUM → CRITICAL)

        detalhes["detectores"] lista os detectores que votaram.
        detalhes["votos"] registra o número de categorias distintas (quando ≥ 2).
        """
        groups: dict[tuple, list[AnomaliaDetectada]] = {}
        for anomalia in anomalias:
            date_key = (
                anomalia.detectado_em.strftime("%Y-%m-%d") if anomalia.detectado_em else "unknown"
            )
            key = (anomalia.if_id, anomalia.taxa_id, date_key)
            groups.setdefault(key, []).append(anomalia)

        deduplicated = []
        for group_anomalias in groups.values():
            group_anomalias.sort(key=lambda a: SEVERITY_ORDER.index(a.severidade), reverse=True)
            winner = group_anomalias[0]

            unique_detectors = sorted({a.detector for a in group_anomalias})
            unique_categories = {_DETECTOR_CATEGORY.get(d, "unknown") for d in unique_detectors}
            n_categories = len(unique_categories)

            if n_categories >= 2:
                levels_up = 1 if n_categories == 2 else 2
                current_idx = SEVERITY_ORDER.index(winner.severidade)
                new_idx = min(current_idx + levels_up, len(SEVERITY_ORDER) - 1)
                winner.severidade = SEVERITY_ORDER[new_idx]

            winner.detalhes["detectores"] = unique_detectors
            if n_categories >= 2:
                winner.detalhes["votos"] = n_categories

            deduplicated.append(winner)

        return deduplicated

    @staticmethod
    def available_detectors() -> dict[DetectorCategory, list[str]]:
        """Retorna lista de detectores disponíveis por categoria."""
        return {
            DetectorCategory.RULES: [
                "spread_detector",
                "variacao_detector",
                "divergencia_detector",
            ],
            DetectorCategory.STATISTICAL: [
                "stl_decomposition_detector",
                "change_point_detector",
                "rolling_zscore_detector",
            ],
            DetectorCategory.ML: [
                "isolation_forest_detector",
                "dbscan_outlier_detector",
            ],
        }
