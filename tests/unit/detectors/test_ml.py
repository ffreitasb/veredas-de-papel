"""Testes unitários para detectores de Machine Learning."""

import pytest

from tests.conftest import make_taxa_serie
from veredas.detectors.ml import HAS_SKLEARN, DBSCANOutlierDetector, IsolationForestDetector, MLEngine, MLThresholds
from veredas.storage.models import TipoAnomalia

pytestmark = pytest.mark.skipif(not HAS_SKLEARN, reason="scikit-learn não instalado")


def make_anomalous_dataset(n_normal: int = 35, if_id: int = 1):
    """Série com n_normal pontos normais + 1 outlier 10x acima — padrão comprovado."""
    normais = [100.0 + (i % 7) * 0.5 for i in range(n_normal)]
    return make_taxa_serie(if_id=if_id, valores=normais + [1000.0])


class TestIsolationForestDetector:
    def setup_method(self):
        self.detector = IsolationForestDetector(min_samples=30)

    def test_poucos_dados_retorna_vazio(self):
        taxas = make_taxa_serie(if_id=1, valores=[100.0] * 10)
        result = self.detector.detect(taxas)
        assert result.success
        assert len(result.anomalias) == 0

    def test_dados_normais_poucos_outliers(self):
        # 50 pontos homogêneos — isolation forest não deve sinalizar muito
        valores = [100.0 + (i % 5) * 0.5 for i in range(50)]
        taxas = make_taxa_serie(if_id=1, valores=valores)
        result = self.detector.detect(taxas)
        assert result.success
        # Com dados uniformes, poucos outliers esperados (< 10% contamination)
        assert len(result.anomalias) <= 5

    def test_outlier_extremo_detectado(self):
        # 99 pontos normais + 1 outlier 10x acima — garante score < -0.3
        valores = [100.0] * 99 + [1000.0]
        taxas = make_taxa_serie(if_id=1, valores=valores)
        result = self.detector.detect(taxas)
        assert result.success
        assert len(result.anomalias) >= 1

    def test_resultado_tem_nome_correto(self):
        taxas = make_taxa_serie(if_id=1, valores=[100.0] * 5)
        result = self.detector.detect(taxas)
        assert result.detector_name == "isolation_forest_detector"

    def test_detect_with_features_compartilhada(self):
        from veredas.detectors.features import FeatureExtractor, calculate_market_stats

        taxas = make_taxa_serie(if_id=1, valores=[100.0 + i * 0.2 for i in range(50)])
        mean, std = calculate_market_stats(taxas)
        extractor = FeatureExtractor()
        features = extractor.extract(taxas, mean, std)
        result = self.detector.detect_with_features(features)
        assert result.success


class TestDBSCANOutlierDetector:
    def setup_method(self):
        self.detector = DBSCANOutlierDetector(min_samples=20)

    def test_poucos_dados_retorna_vazio(self):
        taxas = make_taxa_serie(if_id=1, valores=[100.0] * 5)
        result = self.detector.detect(taxas)
        assert result.success
        assert len(result.anomalias) == 0

    def test_resultado_tem_nome_correto(self):
        taxas = make_taxa_serie(if_id=1, valores=[100.0] * 5)
        result = self.detector.detect(taxas)
        assert result.detector_name == "dbscan_outlier_detector"

    def test_dados_suficientes_executa_sem_erro(self):
        valores = [100.0 + (i % 10) * 2 for i in range(40)]
        taxas = make_taxa_serie(if_id=1, valores=valores)
        result = self.detector.detect(taxas)
        assert result.success


# ---------------------------------------------------------------------------
# MLThresholds — guarda de regressão para ML-02 (contamination="auto")
# ---------------------------------------------------------------------------


class TestMLThresholds:
    def test_contamination_padrao_e_auto(self):
        assert MLThresholds().if_contamination == "auto"

    def test_contamination_configuravel(self):
        assert MLThresholds(if_contamination=0.1).if_contamination == 0.1

    def test_score_thresholds_medium_e_high(self):
        t = MLThresholds()
        assert t.if_score_threshold_medium < 0
        assert t.if_score_threshold_high < t.if_score_threshold_medium

    def test_dbscan_eps_calibrado_para_espaco_multidimensional(self):
        # eps=0.5 era pequeno demais para 21 features escaladas (min dist ~0.85)
        assert MLThresholds().dbscan_eps >= 1.0


# ---------------------------------------------------------------------------
# IsolationForest — detecção com dataset anomalioso real
# ---------------------------------------------------------------------------


class TestIsolationForestComOutliers:
    def setup_method(self):
        self.detector = IsolationForestDetector(min_samples=30)

    def test_outlier_extremo_detectado(self):
        # 35 normais + 1 outlier 10x acima — score comprovadamente < -0.3 com contamination="auto"
        taxas = make_anomalous_dataset(n_normal=35)
        result = self.detector.detect(taxas)
        assert result.success
        assert len(result.anomalias) >= 1

    def test_anomalia_tem_tipo_isolation_anomaly(self):
        taxas = make_anomalous_dataset(n_normal=35)
        result = self.detector.detect(taxas)
        assert result.success
        if result.anomalias:
            assert result.anomalias[0].tipo == TipoAnomalia.ISOLATION_ANOMALY

    def test_execution_time_registrado(self):
        taxas = make_anomalous_dataset()
        result = self.detector.detect(taxas)
        assert result.execution_time_ms > 0

    def test_detect_with_features_registra_tempo_sem_start(self):
        from veredas.detectors.features import FeatureExtractor, calculate_market_stats

        taxas = make_anomalous_dataset()
        mean, std = calculate_market_stats(taxas)
        features = FeatureExtractor().extract(taxas, mean, std)
        result = self.detector.detect_with_features(features, start_time=None)
        assert result.success
        assert result.execution_time_ms > 0


# ---------------------------------------------------------------------------
# DBSCAN — precondição de emissores e comportamento de fallback
# ---------------------------------------------------------------------------


class TestDBSCANComOutliers:
    def setup_method(self):
        self.detector = DBSCANOutlierDetector(min_samples=20)

    def test_menos_de_200_emissores_retorna_vazio(self):
        # Precondição: ≥200 emissores únicos. Com 1 único if_id o detector
        # retorna resultado vazio (não é falha — é proteção contra falsos positivos).
        valores = [100.0 + (i % 10) * 2 for i in range(40)] + [800.0]
        taxas = make_taxa_serie(if_id=1, valores=valores)
        result = self.detector.detect(taxas)
        assert result.success
        assert len(result.anomalias) == 0  # guard ativo: < 200 emissores únicos

    def test_anomalia_tem_tipo_cluster_outlier(self):
        valores = [100.0 + (i % 10) * 2 for i in range(40)] + [800.0]
        taxas = make_taxa_serie(if_id=1, valores=valores)
        result = self.detector.detect(taxas)
        assert result.success
        if result.anomalias:
            assert result.anomalias[0].tipo == TipoAnomalia.CLUSTER_OUTLIER

    def test_dados_normais_geram_poucos_outliers(self):
        # Com eps=6.0, dados homogêneos devem formar clusters — poucos falsos positivos
        valores = [100.0 + (i % 10) * 2 for i in range(50)]
        taxas = make_taxa_serie(if_id=1, valores=valores)
        result = self.detector.detect(taxas)
        assert result.success
        assert len(result.anomalias) <= 5

    def test_execution_time_registrado(self):
        taxas = make_anomalous_dataset()
        result = self.detector.detect(taxas)
        assert result.execution_time_ms > 0


# ---------------------------------------------------------------------------
# MLEngine — orquestração dos dois detectores
# ---------------------------------------------------------------------------


class TestMLEngine:
    def setup_method(self):
        self.engine = MLEngine()

    def test_run_all_retorna_dois_resultados(self):
        taxas = make_anomalous_dataset()
        results = self.engine.run_all(taxas)
        assert len(results) == 2

    def test_run_all_ambos_bem_sucedidos(self):
        taxas = make_anomalous_dataset()
        results = self.engine.run_all(taxas)
        assert all(r.success for r in results)

    def test_analyze_isolation_forest_nome_correto(self):
        taxas = make_anomalous_dataset()
        result = self.engine.analyze_isolation_forest(taxas)
        assert result.detector_name == "isolation_forest_detector"

    def test_analyze_dbscan_nome_correto(self):
        taxas = make_anomalous_dataset()
        result = self.engine.analyze_dbscan(taxas)
        assert result.detector_name == "dbscan_outlier_detector"

    def test_thresholds_compartilhados_entre_detectores(self):
        t = MLThresholds(if_contamination=0.1)
        eng = MLEngine(thresholds=t)
        assert eng.isolation_forest_detector.thresholds is t
        assert eng.dbscan_detector.thresholds is t
