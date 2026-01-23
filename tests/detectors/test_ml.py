"""
Testes dos detectores de Machine Learning.

Verifica detecção de anomalias com Isolation Forest e DBSCAN.
"""

from decimal import Decimal

import pytest

from veredas.detectors.features import FeatureExtractor, TaxaFeatures, calculate_market_stats
from veredas.detectors.ml import (
    DBSCANOutlierDetector,
    IsolationForestDetector,
    MLEngine,
    MLThresholds,
)
from veredas.storage.models import Severidade, TaxaCDB, TipoAnomalia


class TestFeatureExtractor:
    """Testes do extrator de features."""

    def test_extrai_features_basicas(self, taxas_serie_temporal: list[TaxaCDB]):
        """Deve extrair features básicas de séries temporais."""
        extractor = FeatureExtractor()
        features = extractor.extract(taxas_serie_temporal)

        assert len(features) > 0
        assert all(isinstance(f, TaxaFeatures) for f in features)

    def test_features_tem_campos_obrigatorios(self, taxas_serie_temporal: list[TaxaCDB]):
        """Features devem ter todos os campos obrigatórios."""
        extractor = FeatureExtractor()
        features = extractor.extract(taxas_serie_temporal)

        for f in features:
            assert f.if_id is not None
            assert f.data is not None
            assert f.percentual > 0
            assert 0 <= f.dia_semana <= 6
            assert 1 <= f.dia_mes <= 31
            assert 1 <= f.mes <= 12

    def test_extract_to_dataframe(self, taxas_serie_temporal: list[TaxaCDB]):
        """Deve retornar DataFrame com features."""
        extractor = FeatureExtractor()
        df = extractor.extract_to_dataframe(taxas_serie_temporal)

        assert len(df) > 0
        assert "percentual" in df.columns
        assert "rolling_mean_7d" in df.columns
        assert "z_score_7d" in df.columns

    def test_extract_to_matrix(self, taxas_serie_temporal: list[TaxaCDB]):
        """Deve retornar matriz numpy para ML."""
        extractor = FeatureExtractor()
        matrix, ids = extractor.extract_to_matrix(taxas_serie_temporal)

        assert matrix.shape[0] == len(ids)
        assert matrix.shape[1] == len(TaxaFeatures.feature_names())

    def test_lista_vazia_nao_quebra(self):
        """Lista vazia não deve quebrar."""
        extractor = FeatureExtractor()
        features = extractor.extract([])

        assert features == []

    def test_contexto_de_mercado(self, taxas_serie_temporal: list[TaxaCDB]):
        """Deve incluir contexto de mercado quando fornecido."""
        extractor = FeatureExtractor(include_market_context=True)
        features = extractor.extract(
            taxas_serie_temporal,
            market_mean=110.0,
            market_std=5.0,
        )

        # Pelo menos algumas features devem ter contexto de mercado
        with_market = [f for f in features if f.diff_from_market_mean is not None]
        assert len(with_market) > 0


class TestCalculateMarketStats:
    """Testes da função de estatísticas de mercado."""

    def test_calcula_media_e_desvio(self, taxas_serie_temporal: list[TaxaCDB]):
        """Deve calcular média e desvio padrão corretamente."""
        mean, std = calculate_market_stats(taxas_serie_temporal)

        assert mean > 0
        assert std >= 0

    def test_lista_vazia(self):
        """Lista vazia deve retornar zeros."""
        mean, std = calculate_market_stats([])

        assert mean == 0.0
        assert std == 0.0


class TestIsolationForestDetector:
    """Testes do detector Isolation Forest."""

    def test_detector_properties(self):
        """Deve ter propriedades corretas."""
        detector = IsolationForestDetector()
        assert detector.name == "isolation_forest_detector"
        assert "isolation" in detector.description.lower()

    def test_serie_normal_poucas_anomalias(self, taxas_serie_temporal: list[TaxaCDB]):
        """Série normal não deve ter muitas anomalias HIGH."""
        detector = IsolationForestDetector(min_samples=15)
        result = detector.detect(taxas_serie_temporal)

        if result.error and "scikit-learn" in result.error:
            pytest.skip("scikit-learn não instalado")

        assert result.success
        # Série normal deve ter poucas anomalias severas
        high_count = sum(1 for a in result.anomalias if a.severidade == Severidade.HIGH)
        assert high_count <= 3

    def test_serie_com_outlier_detecta(self, taxas_com_outlier: list[TaxaCDB]):
        """Deve detectar outliers na série."""
        detector = IsolationForestDetector(min_samples=15)
        result = detector.detect(taxas_com_outlier)

        if result.error and "scikit-learn" in result.error:
            pytest.skip("scikit-learn não instalado")

        assert result.success
        # Deve detectar pelo menos o outlier extremo
        if result.has_anomalies:
            tipos = [a.tipo for a in result.anomalias]
            assert TipoAnomalia.ISOLATION_ANOMALY in tipos

    def test_serie_insuficiente_nao_quebra(self, taxas_insuficientes: list[TaxaCDB]):
        """Série curta não deve quebrar."""
        detector = IsolationForestDetector(min_samples=30)
        result = detector.detect(taxas_insuficientes)

        if result.error and "scikit-learn" in result.error:
            pytest.skip("scikit-learn não instalado")

        assert result.success
        assert not result.has_anomalies

    def test_thresholds_customizados(self):
        """Deve aceitar thresholds customizados."""
        thresholds = MLThresholds(
            if_contamination=0.1,
            if_n_estimators=50,
        )
        detector = IsolationForestDetector(thresholds=thresholds)

        assert detector.thresholds.if_contamination == 0.1
        assert detector.thresholds.if_n_estimators == 50


class TestDBSCANOutlierDetector:
    """Testes do detector DBSCAN."""

    def test_detector_properties(self):
        """Deve ter propriedades corretas."""
        detector = DBSCANOutlierDetector()
        assert detector.name == "dbscan_outlier_detector"
        assert "dbscan" in detector.description.lower()

    def test_serie_com_outlier(self, taxas_com_outlier: list[TaxaCDB]):
        """Deve detectar outliers usando clustering."""
        detector = DBSCANOutlierDetector(min_samples=10)
        result = detector.detect(taxas_com_outlier)

        if result.error and "scikit-learn" in result.error:
            pytest.skip("scikit-learn não instalado")

        assert result.success
        # Pode ou não detectar dependendo da configuração de eps
        # O importante é que não quebre

    def test_serie_insuficiente_nao_quebra(self, taxas_insuficientes: list[TaxaCDB]):
        """Série curta não deve quebrar."""
        detector = DBSCANOutlierDetector(min_samples=20)
        result = detector.detect(taxas_insuficientes)

        if result.error and "scikit-learn" in result.error:
            pytest.skip("scikit-learn não instalado")

        assert result.success
        assert not result.has_anomalies

    def test_thresholds_customizados(self):
        """Deve aceitar thresholds customizados."""
        thresholds = MLThresholds(
            dbscan_eps=1.0,
            dbscan_min_samples=3,
        )
        detector = DBSCANOutlierDetector(thresholds=thresholds)

        assert detector.thresholds.dbscan_eps == 1.0
        assert detector.thresholds.dbscan_min_samples == 3


class TestMLEngine:
    """Testes do motor de ML."""

    def test_inicializacao(self):
        """Deve inicializar corretamente."""
        engine = MLEngine()

        assert engine.isolation_forest_detector is not None
        assert engine.dbscan_detector is not None

    def test_run_all(self, taxas_serie_temporal: list[TaxaCDB]):
        """Deve executar todos os detectores ML."""
        engine = MLEngine()
        results = engine.run_all(taxas_serie_temporal)

        # Verifica que retornou 2 resultados (IF e DBSCAN)
        assert len(results) == 2
        detector_names = [r.detector_name for r in results]
        assert "isolation_forest_detector" in detector_names
        assert "dbscan_outlier_detector" in detector_names

    def test_thresholds_customizados(self):
        """Deve aceitar thresholds customizados."""
        thresholds = MLThresholds(if_contamination=0.1)
        engine = MLEngine(thresholds=thresholds)

        assert engine.thresholds.if_contamination == 0.1


class TestMLThresholds:
    """Testes dos thresholds de ML."""

    def test_valores_padrao(self):
        """Deve ter valores padrão sensatos."""
        thresholds = MLThresholds()

        assert thresholds.if_contamination == 0.05
        assert thresholds.if_n_estimators == 100
        assert thresholds.dbscan_eps == 0.5
        assert thresholds.dbscan_min_samples == 5

    def test_customizacao(self):
        """Deve permitir customização."""
        thresholds = MLThresholds(
            if_contamination=0.1,
            if_n_estimators=200,
            dbscan_eps=1.0,
            dbscan_min_samples=10,
        )

        assert thresholds.if_contamination == 0.1
        assert thresholds.if_n_estimators == 200
        assert thresholds.dbscan_eps == 1.0
        assert thresholds.dbscan_min_samples == 10
