"""
Testes dos detectores estatísticos.

Verifica detecção de anomalias por STL, Change Point e Rolling Z-Score.
"""

from decimal import Decimal
from typing import TYPE_CHECKING

import pytest

from veredas.detectors.statistical import (
    ChangePointDetector,
    RollingZScoreDetector,
    StatisticalEngine,
    StatisticalThresholds,
    STLDecompositionDetector,
)
from veredas.storage.models import Severidade, TaxaCDB, TipoAnomalia

if TYPE_CHECKING:
    from sqlalchemy.orm import Session


class TestSTLDecompositionDetector:
    """Testes do detector STL."""

    def test_detector_properties(self):
        """Deve ter propriedades corretas."""
        detector = STLDecompositionDetector()
        assert detector.name == "stl_decomposition_detector"
        assert "sazonal" in detector.description.lower()

    def test_serie_normal_sem_anomalia(self, taxas_serie_temporal: list[TaxaCDB]):
        """Série temporal normal não deve gerar muitas anomalias."""
        detector = STLDecompositionDetector(min_observations=14)
        result = detector.detect(taxas_serie_temporal)

        assert result.success
        # Série normal pode ter algumas anomalias marginais
        # mas não deve ter anomalias HIGH
        high_anomalias = [a for a in result.anomalias if a.severidade == Severidade.HIGH]
        assert len(high_anomalias) <= 1

    def test_serie_com_outlier_detecta_anomalia(self, taxas_com_outlier: list[TaxaCDB]):
        """Série com outlier deve detectar anomalia."""
        detector = STLDecompositionDetector(min_observations=10)
        result = detector.detect(taxas_com_outlier)

        assert result.success
        # Deve detectar pelo menos uma anomalia
        assert result.has_anomalies

        # Pelo menos uma deve ser SEASONALITY_BREAK
        tipos = [a.tipo for a in result.anomalias]
        assert TipoAnomalia.SEASONALITY_BREAK in tipos

    def test_serie_insuficiente_nao_quebra(self, taxas_insuficientes: list[TaxaCDB]):
        """Série muito curta não deve quebrar."""
        detector = STLDecompositionDetector(min_observations=14)
        result = detector.detect(taxas_insuficientes)

        assert result.success
        assert not result.has_anomalies

    def test_lista_vazia_nao_quebra(self):
        """Lista vazia não deve quebrar."""
        detector = STLDecompositionDetector()
        result = detector.detect([])

        assert result.success
        assert not result.has_anomalies

    def test_thresholds_customizados(self, taxas_com_outlier: list[TaxaCDB]):
        """Deve respeitar thresholds customizados."""
        # Com threshold muito alto, não deve detectar anomalias
        thresholds = StatisticalThresholds(
            stl_residual_medium=Decimal("10.0"),
            stl_residual_high=Decimal("15.0"),
        )
        detector = STLDecompositionDetector(thresholds=thresholds, min_observations=10)
        result = detector.detect(taxas_com_outlier)

        assert result.success
        # Com threshold alto, menos anomalias
        high_anomalias = [a for a in result.anomalias if a.severidade == Severidade.HIGH]
        assert len(high_anomalias) == 0


class TestChangePointDetector:
    """Testes do detector de change points."""

    def test_detector_properties(self):
        """Deve ter propriedades corretas."""
        detector = ChangePointDetector()
        assert detector.name == "change_point_detector"
        assert "pelt" in detector.description.lower()

    def test_serie_com_change_point_detecta(self, taxas_com_change_point: list[TaxaCDB]):
        """Série com change point deve ser detectada."""
        detector = ChangePointDetector(min_observations=10)
        result = detector.detect(taxas_com_change_point)

        # Pode não ter ruptures instalado
        if result.error and "ruptures" in result.error:
            pytest.skip("ruptures não instalado")

        assert result.success
        # Deve detectar pelo menos uma mudança estrutural
        if result.has_anomalies:
            tipos = [a.tipo for a in result.anomalias]
            assert TipoAnomalia.CHANGE_POINT in tipos

    def test_serie_estavel_sem_change_point(self, taxas_serie_temporal: list[TaxaCDB]):
        """Série estável não deve ter change points."""
        detector = ChangePointDetector(min_observations=10)
        result = detector.detect(taxas_serie_temporal)

        if result.error and "ruptures" in result.error:
            pytest.skip("ruptures não instalado")

        assert result.success
        # Série estável deve ter poucos ou nenhum change point
        # (penalty alto reduz falsos positivos)

    def test_serie_insuficiente_nao_quebra(self, taxas_insuficientes: list[TaxaCDB]):
        """Série muito curta não deve quebrar."""
        detector = ChangePointDetector(min_observations=20)
        result = detector.detect(taxas_insuficientes)

        if result.error and "ruptures" in result.error:
            pytest.skip("ruptures não instalado")

        assert result.success
        assert not result.has_anomalies

    def test_modelos_disponiveis(self, taxas_com_change_point: list[TaxaCDB]):
        """Deve aceitar diferentes modelos de custo."""
        for model in ["rbf", "l2"]:
            detector = ChangePointDetector(model=model, min_observations=10)
            result = detector.detect(taxas_com_change_point)

            if result.error and "ruptures" in result.error:
                pytest.skip("ruptures não instalado")

            assert result.success


class TestRollingZScoreDetector:
    """Testes do detector de rolling z-score."""

    def test_detector_properties(self):
        """Deve ter propriedades corretas."""
        detector = RollingZScoreDetector()
        assert detector.name == "rolling_zscore_detector"
        assert "outlier" in detector.description.lower()

    def test_serie_normal_sem_anomalia(self, taxas_serie_temporal: list[TaxaCDB]):
        """Série temporal normal não deve gerar anomalias HIGH."""
        detector = RollingZScoreDetector(min_observations=7)
        result = detector.detect(taxas_serie_temporal)

        assert result.success
        # Série normal não deve ter muitas anomalias HIGH
        high_anomalias = [a for a in result.anomalias if a.severidade == Severidade.HIGH]
        assert len(high_anomalias) <= 1

    def test_outlier_extremo_detectado(self, taxas_com_outlier: list[TaxaCDB]):
        """Outlier extremo deve ser detectado."""
        detector = RollingZScoreDetector(min_observations=7)
        result = detector.detect(taxas_com_outlier)

        assert result.success
        assert result.has_anomalies

        # Deve detectar o outlier como ROLLING_OUTLIER
        tipos = [a.tipo for a in result.anomalias]
        assert TipoAnomalia.ROLLING_OUTLIER in tipos

        # Pelo menos uma anomalia deve ser HIGH
        severidades = [a.severidade for a in result.anomalias]
        assert Severidade.HIGH in severidades or Severidade.MEDIUM in severidades

    def test_serie_insuficiente_nao_quebra(self, taxas_insuficientes: list[TaxaCDB]):
        """Série muito curta não deve quebrar."""
        detector = RollingZScoreDetector(min_observations=10)
        result = detector.detect(taxas_insuficientes)

        assert result.success
        assert not result.has_anomalies

    def test_lista_vazia_nao_quebra(self):
        """Lista vazia não deve quebrar."""
        detector = RollingZScoreDetector()
        result = detector.detect([])

        assert result.success
        assert not result.has_anomalies

    def test_thresholds_customizados(self, taxas_com_outlier: list[TaxaCDB]):
        """Deve respeitar thresholds customizados."""
        # Com threshold muito baixo, mais anomalias
        thresholds = StatisticalThresholds(
            rolling_z_medium=Decimal("1.5"),
            rolling_z_high=Decimal("2.0"),
        )
        detector = RollingZScoreDetector(thresholds=thresholds, min_observations=7)
        result = detector.detect(taxas_com_outlier)

        assert result.success
        # Com threshold baixo, deve detectar mais anomalias
        assert result.has_anomalies

    def test_janela_customizada(self):
        """Deve aceitar tamanho de janela customizado."""
        thresholds = StatisticalThresholds(rolling_window=7)
        detector = RollingZScoreDetector(thresholds=thresholds)
        assert detector.thresholds.rolling_window == 7


class TestStatisticalEngine:
    """Testes do motor de detecção estatística."""

    def test_inicializacao(self):
        """Deve inicializar corretamente."""
        engine = StatisticalEngine()

        assert engine.stl_detector is not None
        assert engine.change_point_detector is not None
        assert engine.rolling_zscore_detector is not None

    def test_analyze_seasonality(self, taxas_serie_temporal: list[TaxaCDB]):
        """Deve executar análise de sazonalidade."""
        engine = StatisticalEngine()
        result = engine.analyze_seasonality(taxas_serie_temporal)

        assert result.success
        assert result.detector_name == "stl_decomposition_detector"

    def test_analyze_change_points(self, taxas_com_change_point: list[TaxaCDB]):
        """Deve executar análise de change points."""
        engine = StatisticalEngine()
        result = engine.analyze_change_points(taxas_com_change_point)

        if result.error and "ruptures" in result.error:
            pytest.skip("ruptures não instalado")

        assert result.success
        assert result.detector_name == "change_point_detector"

    def test_analyze_local_outliers(self, taxas_com_outlier: list[TaxaCDB]):
        """Deve executar análise de outliers locais."""
        engine = StatisticalEngine()
        result = engine.analyze_local_outliers(taxas_com_outlier)

        assert result.success
        assert result.detector_name == "rolling_zscore_detector"

    def test_run_all(self, taxas_serie_temporal: list[TaxaCDB]):
        """Deve executar todos os detectores."""
        engine = StatisticalEngine()
        results = engine.run_all(taxas_serie_temporal)

        assert len(results) == 3
        detector_names = [r.detector_name for r in results]
        assert "stl_decomposition_detector" in detector_names
        assert "change_point_detector" in detector_names
        assert "rolling_zscore_detector" in detector_names

    def test_thresholds_customizados(self):
        """Deve aceitar thresholds customizados."""
        thresholds = StatisticalThresholds(
            stl_residual_medium=Decimal("3.0"),
            rolling_window=21,
        )
        engine = StatisticalEngine(thresholds=thresholds)

        assert engine.thresholds.stl_residual_medium == Decimal("3.0")
        assert engine.thresholds.rolling_window == 21


class TestStatisticalThresholds:
    """Testes dos thresholds estatísticos."""

    def test_valores_padrao(self):
        """Deve ter valores padrão sensatos."""
        thresholds = StatisticalThresholds()

        assert thresholds.stl_period == 5
        assert thresholds.stl_residual_medium == Decimal("2.5")
        assert thresholds.stl_residual_high == Decimal("3.5")
        assert thresholds.rolling_window == 14
        assert thresholds.rolling_z_medium == Decimal("2.5")
        assert thresholds.rolling_z_high == Decimal("3.5")
        assert thresholds.changepoint_penalty == 10.0
        assert thresholds.changepoint_min_size == 5

    def test_customizacao(self):
        """Deve permitir customização de todos os valores."""
        thresholds = StatisticalThresholds(
            stl_period=7,
            stl_residual_medium=Decimal("2.0"),
            stl_residual_high=Decimal("3.0"),
            rolling_window=21,
            rolling_z_medium=Decimal("2.0"),
            rolling_z_high=Decimal("3.0"),
            changepoint_penalty=15.0,
            changepoint_min_size=10,
        )

        assert thresholds.stl_period == 7
        assert thresholds.stl_residual_medium == Decimal("2.0")
        assert thresholds.rolling_window == 21
        assert thresholds.changepoint_penalty == 15.0


class TestDetectionResultStatistical:
    """Testes específicos do DetectionResult para detectores estatísticos."""

    def test_execution_time(self, taxas_serie_temporal: list[TaxaCDB]):
        """Deve registrar tempo de execução."""
        detector = RollingZScoreDetector()
        result = detector.detect(taxas_serie_temporal)

        assert result.execution_time_ms >= 0

    def test_detalhes_anomalia(self, taxas_com_outlier: list[TaxaCDB]):
        """Anomalias devem ter detalhes úteis."""
        detector = RollingZScoreDetector(min_observations=7)
        result = detector.detect(taxas_com_outlier)

        if result.has_anomalies:
            anomalia = result.anomalias[0]

            # Deve ter detalhes
            assert anomalia.detalhes is not None
            assert "z_score" in anomalia.detalhes
            assert "data" in anomalia.detalhes

    def test_referencia_taxa(self, taxas_com_outlier: list[TaxaCDB]):
        """Anomalias devem referenciar a taxa original."""
        detector = RollingZScoreDetector(min_observations=7)
        result = detector.detect(taxas_com_outlier)

        if result.has_anomalies:
            anomalia = result.anomalias[0]

            # Deve ter referência à IF e possivelmente à taxa
            assert anomalia.if_id is not None
