"""Testes de integração para o pipeline de detecção end-to-end."""

from datetime import datetime

from tests.conftest import make_taxa, make_taxa_serie
from veredas.detectors.engine import DetectionEngine, EngineConfig, EngineResult
from veredas.storage.models import Severidade


class TestDetectionEnginePipeline:
    def setup_method(self):
        # Config mínima: apenas regras (sem dependências externas)
        self.config = EngineConfig(
            enable_rules=True,
            enable_statistical=False,
            enable_ml=False,
        )
        self.engine = DetectionEngine(config=self.config)

    def test_analyze_retorna_engine_result(self):
        taxas = make_taxa_serie(if_id=1, valores=[110.0, 112.0, 108.0])
        result = self.engine.analyze(taxas)
        assert isinstance(result, EngineResult)

    def test_analyze_sem_anomalias_em_taxas_normais(self):
        taxas = make_taxa_serie(if_id=1, valores=[110.0, 112.0, 108.0])
        result = self.engine.analyze(taxas)
        assert not result.has_anomalias
        assert result.taxas_analyzed == 3

    def test_spread_alto_cdi_detectado(self):
        # 140% CDI é spread alto
        taxas = [make_taxa(if_id=1, percentual=140.0)]
        result = self.engine.analyze(taxas)
        assert result.has_anomalias
        assert result.high_count >= 1

    def test_spread_critico_cdi_gera_critical(self):
        taxas = [make_taxa(if_id=1, percentual=160.0)]
        result = self.engine.analyze(taxas)
        assert result.critical_count >= 1

    def test_detectors_used_registrado(self):
        taxas = make_taxa_serie(if_id=1, valores=[110.0])
        result = self.engine.analyze(taxas)
        assert "spread_detector" in result.detectors_used

    def test_variacao_detectada_com_historico(self):
        anteriores = make_taxa_serie(if_id=1, valores=[100.0])
        atuais = make_taxa_serie(if_id=1, valores=[125.0], data_inicio=datetime(2024, 1, 2))
        result = self.engine.analyze(atuais, taxas_anteriores=anteriores)
        # Salto de 25% em relação ao anterior deve ser SALTO_EXTREMO
        assert result.has_anomalias

    def test_by_severity_filtra_corretamente(self):
        taxas = [
            make_taxa(if_id=1, percentual=140.0),  # HIGH
            make_taxa(if_id=2, percentual=160.0),  # CRITICAL
        ]
        result = self.engine.analyze(taxas)
        criticas = result.by_severity(Severidade.CRITICAL)
        assert len(criticas) >= 1
        for a in criticas:
            assert a.severidade == Severidade.CRITICAL

    def test_by_if_filtra_por_instituicao(self):
        taxas = [
            make_taxa(if_id=1, percentual=110.0),  # normal
            make_taxa(if_id=2, percentual=160.0),  # critical
        ]
        result = self.engine.analyze(taxas)
        anomalias_if2 = result.by_if(2)
        assert all(a.if_id == 2 for a in anomalias_if2)

    def test_execution_time_registrado(self):
        taxas = make_taxa_serie(if_id=1, valores=[110.0, 120.0])
        result = self.engine.analyze(taxas)
        assert result.execution_time_ms >= 0

    def test_lista_vazia_nao_gera_erro(self):
        result = self.engine.analyze([])
        assert isinstance(result, EngineResult)
        assert not result.has_anomalias

    def test_deduplicacao_remove_duplicatas(self):
        # Mesma IF, mesmo dia, mesma taxa — dois detectores podem sinalizar
        # Com deduplicate=True, deve manter apenas a mais severa
        config = EngineConfig(
            enable_rules=True,
            enable_statistical=False,
            enable_ml=False,
            deduplicate=True,
        )
        engine = DetectionEngine(config=config)
        taxas = [make_taxa(if_id=1, percentual=160.0)]
        result = engine.analyze(taxas)
        # Não deve ter entradas duplicadas para o mesmo (if_id, taxa_id, data)
        seen = set()
        for a in result.anomalias:
            date_key = a.detectado_em.strftime("%Y-%m-%d") if a.detectado_em else "unknown"
            key = (a.if_id, a.taxa_id, date_key)
            assert key not in seen, f"Anomalia duplicada: {key}"
            seen.add(key)


class TestDetectionEngineComEstatistico:
    """Testa pipeline com detectores estatísticos (sem sklearn/ruptures)."""

    def test_rolling_zscore_integrado(self):
        config = EngineConfig(
            enable_rules=False,
            enable_statistical=True,
            enable_ml=False,
            min_observations_statistical=7,
        )
        engine = DetectionEngine(config=config)

        # 29 pontos normais + 1 outlier extremo
        taxas = make_taxa_serie(if_id=1, valores=[100.0] * 29 + [300.0])
        result = engine.analyze(taxas)
        assert isinstance(result, EngineResult)
        assert "rolling_zscore_detector" in result.detectors_used
        assert result.has_anomalias

    def test_insuficiente_nao_executa_estatistico(self):
        config = EngineConfig(
            enable_rules=False,
            enable_statistical=True,
            enable_ml=False,
            min_observations_statistical=14,
        )
        engine = DetectionEngine(config=config)

        # Apenas 5 taxas — menos que o mínimo
        taxas = make_taxa_serie(if_id=1, valores=[100.0] * 5)
        result = engine.analyze(taxas)
        # Nenhum detector estatístico deve ter sido executado
        stat_detectors = {
            "stl_decomposition_detector",
            "change_point_detector",
            "rolling_zscore_detector",
        }
        assert not stat_detectors.intersection(result.detectors_used)
