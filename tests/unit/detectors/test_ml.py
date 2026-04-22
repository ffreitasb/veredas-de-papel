"""Testes unitários para detectores de Machine Learning."""

import pytest

from tests.conftest import make_taxa, make_taxa_serie
from veredas.detectors.ml import IsolationForestDetector, DBSCANOutlierDetector, HAS_SKLEARN


pytestmark = pytest.mark.skipif(not HAS_SKLEARN, reason="scikit-learn não instalado")


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
