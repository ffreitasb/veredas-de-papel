"""Testes unitários para detectores estatísticos."""

import pytest

from tests.conftest import make_taxa_serie
from veredas.detectors.statistical import RollingZScoreDetector, StatisticalThresholds


# ---------------------------------------------------------------------------
# RollingZScoreDetector  (mais rápido e sem dependência de ruptures/sklearn)
# ---------------------------------------------------------------------------

class TestRollingZScoreDetector:
    def setup_method(self):
        self.detector = RollingZScoreDetector(min_observations=7)

    def test_sem_dados_suficientes_retorna_vazio(self):
        taxas = make_taxa_serie(if_id=1, valores=[100.0, 102.0, 101.0])
        result = self.detector.detect(taxas)
        assert result.success
        assert len(result.anomalias) == 0

    def test_serie_estavel_sem_anomalias(self):
        # Série com pequenas variações normais (30 pontos)
        valores = [100.0 + (i % 3) * 0.5 for i in range(30)]
        taxas = make_taxa_serie(if_id=1, valores=valores)
        result = self.detector.detect(taxas)
        assert result.success
        assert len(result.anomalias) == 0

    def test_outlier_detectado(self):
        # 29 pontos normais + 1 outlier extremo
        valores = [100.0] * 29 + [200.0]
        taxas = make_taxa_serie(if_id=1, valores=valores)
        result = self.detector.detect(taxas)
        assert result.success
        assert len(result.anomalias) >= 1
        severidades = {a.severidade.value for a in result.anomalias}
        assert "high" in severidades or "medium" in severidades

    def test_resultado_tem_nome_do_detector(self):
        taxas = make_taxa_serie(if_id=1, valores=[100.0] * 20)
        result = self.detector.detect(taxas)
        assert result.detector_name == "rolling_zscore_detector"

    def test_multiplas_ifs_independentes(self):
        # IF 1 normal, IF 2 com outlier
        taxas_normais = make_taxa_serie(if_id=1, valores=[100.0] * 20)
        taxas_outlier = make_taxa_serie(if_id=2, valores=[100.0] * 19 + [300.0])
        result = self.detector.detect(taxas_normais + taxas_outlier)
        assert result.success
        if_ids_anomalos = {a.if_id for a in result.anomalias}
        assert 2 in if_ids_anomalos
        assert 1 not in if_ids_anomalos

    def test_thresholds_customizados_mais_sensiveis(self):
        from decimal import Decimal
        thresholds = StatisticalThresholds(rolling_window=7, rolling_z_medium=Decimal("1.5"))
        detector = RollingZScoreDetector(thresholds=thresholds, min_observations=7)
        # Outlier moderado que passaria com threshold padrão mas não com 1.5σ
        valores = [100.0] * 14 + [110.0]
        taxas = make_taxa_serie(if_id=1, valores=valores)
        result = detector.detect(taxas)
        assert result.success


# ---------------------------------------------------------------------------
# STLDecompositionDetector
# ---------------------------------------------------------------------------

class TestSTLDecompositionDetector:
    def test_sem_dados_suficientes_retorna_vazio(self):
        from veredas.detectors.statistical import STLDecompositionDetector
        detector = STLDecompositionDetector(min_observations=14)
        taxas = make_taxa_serie(if_id=1, valores=[100.0] * 5)
        result = detector.detect(taxas)
        assert result.success
        assert len(result.anomalias) == 0

    def test_serie_suficiente_executa_sem_erro(self):
        from veredas.detectors.statistical import STLDecompositionDetector
        detector = STLDecompositionDetector(min_observations=14)
        # 30 pontos com padrão sazonal leve
        valores = [100.0 + (i % 5) * 2 for i in range(30)]
        taxas = make_taxa_serie(if_id=1, valores=valores)
        result = detector.detect(taxas)
        assert result.success
        assert result.detector_name == "stl_decomposition_detector"


# ---------------------------------------------------------------------------
# ChangePointDetector
# ---------------------------------------------------------------------------

class TestChangePointDetector:
    def test_sem_ruptures_retorna_erro_descritivo(self):
        from veredas.detectors.statistical import ChangePointDetector, HAS_RUPTURES
        if HAS_RUPTURES:
            pytest.skip("ruptures instalado — teste de fallback não se aplica")
        detector = ChangePointDetector(min_observations=20)
        taxas = make_taxa_serie(if_id=1, valores=[100.0] * 30)
        result = detector.detect(taxas)
        assert not result.success
        assert "ruptures" in result.error.lower()

    def test_com_ruptures_detecta_mudanca_estrutural(self):
        from veredas.detectors.statistical import ChangePointDetector, HAS_RUPTURES
        if not HAS_RUPTURES:
            pytest.skip("ruptures não instalado")
        detector = ChangePointDetector(min_observations=20)
        # Série com mudança brusca na metade
        valores = [100.0] * 20 + [150.0] * 20
        taxas = make_taxa_serie(if_id=1, valores=valores)
        result = detector.detect(taxas)
        assert result.success
        assert len(result.anomalias) >= 1
