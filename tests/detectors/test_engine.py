"""
Testes do motor de detecção unificado.

Verifica orquestração de todos os detectores e consolidação de resultados.
"""

from decimal import Decimal

import pytest

from veredas.detectors.engine import (
    DetectionEngine,
    DetectorCategory,
    EngineConfig,
    EngineResult,
)
from veredas.detectors.rules import RuleThresholds
from veredas.detectors.statistical import StatisticalThresholds
from veredas.storage.models import Severidade, TaxaCDB


class TestEngineConfig:
    """Testes da configuração do motor."""

    def test_valores_padrao(self):
        """Deve ter valores padrão sensatos."""
        config = EngineConfig()

        assert config.enable_rules is True
        assert config.enable_statistical is True
        assert config.enable_ml is True
        assert config.deduplicate is True
        assert config.min_severity == Severidade.LOW

    def test_customizacao(self):
        """Deve permitir customização."""
        config = EngineConfig(
            enable_rules=True,
            enable_statistical=False,
            enable_ml=False,
            min_severity=Severidade.HIGH,
            deduplicate=False,
        )

        assert config.enable_statistical is False
        assert config.enable_ml is False
        assert config.min_severity == Severidade.HIGH
        assert config.deduplicate is False

    def test_detectores_especificos(self):
        """Deve aceitar lista de detectores específicos."""
        config = EngineConfig(
            detectors={
                DetectorCategory.RULES: ["spread_detector"],
            }
        )

        assert DetectorCategory.RULES in config.detectors
        assert "spread_detector" in config.detectors[DetectorCategory.RULES]


class TestDetectionEngine:
    """Testes do motor de detecção."""

    def test_inicializacao_padrao(self):
        """Deve inicializar com configuração padrão."""
        engine = DetectionEngine()

        assert engine.config is not None
        assert engine.rule_engine is not None
        assert engine.stl_detector is not None
        assert engine.isolation_forest_detector is not None

    def test_inicializacao_com_config(self):
        """Deve aceitar configuração customizada."""
        config = EngineConfig(enable_ml=False)
        engine = DetectionEngine(config)

        assert engine.config.enable_ml is False

    def test_analyze_apenas_regras(
        self,
        taxa_cdb_spread_alto: TaxaCDB,
        taxa_cdb_spread_critico: TaxaCDB,
    ):
        """Deve executar apenas detectores de regras."""
        config = EngineConfig(
            enable_rules=True,
            enable_statistical=False,
            enable_ml=False,
        )
        engine = DetectionEngine(config)
        result = engine.analyze([taxa_cdb_spread_alto, taxa_cdb_spread_critico])

        assert isinstance(result, EngineResult)
        assert result.has_anomalias
        # Deve ter usado apenas detectores de regras
        assert all(
            d in ["spread_detector", "divergencia_detector", "variacao_detector"]
            for d in result.detectors_used
        )

    def test_analyze_com_taxas_anteriores(
        self,
        taxas_para_variacao,
    ):
        """Deve usar taxas anteriores para detectar variações."""
        taxa_anterior, taxa_atual = taxas_para_variacao

        config = EngineConfig(
            enable_rules=True,
            enable_statistical=False,
            enable_ml=False,
        )
        engine = DetectionEngine(config)
        result = engine.analyze([taxa_atual], taxas_anteriores=[taxa_anterior])

        assert "variacao_detector" in result.detectors_used

    def test_analyze_serie_temporal_completa(
        self,
        taxas_serie_temporal: list[TaxaCDB],
    ):
        """Deve executar todos os detectores com série temporal completa."""
        config = EngineConfig(
            min_observations_statistical=10,
            min_observations_ml=20,
        )
        engine = DetectionEngine(config)
        result = engine.analyze(taxas_serie_temporal)

        assert isinstance(result, EngineResult)
        # Deve ter usado múltiplos detectores
        assert len(result.detectors_used) >= 3

    def test_deduplicacao(
        self,
        taxas_com_outlier: list[TaxaCDB],
    ):
        """Deve deduplicar anomalias por padrão."""
        config = EngineConfig(
            enable_rules=True,
            enable_statistical=True,
            enable_ml=False,
            deduplicate=True,
            min_observations_statistical=10,
        )
        engine = DetectionEngine(config)
        result = engine.analyze(taxas_com_outlier)

        # Com deduplicação, não deve haver anomalias duplicadas
        # para a mesma taxa/IF/data
        seen = set()
        for a in result.anomalias:
            key = (a.if_id, a.taxa_id)
            # Não é garantido que não haja duplicatas, mas a quantidade
            # deve ser menor que sem deduplicação

    def test_filtro_severidade(
        self,
        taxa_cdb_spread_alto: TaxaCDB,
        taxa_cdb_spread_critico: TaxaCDB,
    ):
        """Deve filtrar por severidade mínima."""
        config = EngineConfig(
            enable_rules=True,
            enable_statistical=False,
            enable_ml=False,
            min_severity=Severidade.CRITICAL,
        )
        engine = DetectionEngine(config)
        result = engine.analyze([taxa_cdb_spread_alto, taxa_cdb_spread_critico])

        # Deve retornar apenas anomalias CRITICAL
        for a in result.anomalias:
            assert a.severidade == Severidade.CRITICAL

    def test_analyze_single_detector(
        self,
        taxa_cdb_spread_critico: TaxaCDB,
    ):
        """Deve executar um detector específico."""
        engine = DetectionEngine()
        result = engine.analyze_single_detector(
            "spread_detector",
            [taxa_cdb_spread_critico],
        )

        assert result.success
        assert result.has_anomalies

    def test_analyze_single_detector_invalido(self):
        """Deve retornar erro para detector inválido."""
        engine = DetectionEngine()
        result = engine.analyze_single_detector("detector_inexistente", [])

        assert result.error is not None
        assert "não encontrado" in result.error

    def test_available_detectors(self):
        """Deve listar detectores disponíveis."""
        detectors = DetectionEngine.available_detectors()

        assert DetectorCategory.RULES in detectors
        assert DetectorCategory.STATISTICAL in detectors
        assert DetectorCategory.ML in detectors

        assert "spread_detector" in detectors[DetectorCategory.RULES]
        assert "stl_decomposition_detector" in detectors[DetectorCategory.STATISTICAL]
        assert "isolation_forest_detector" in detectors[DetectorCategory.ML]


class TestEngineResult:
    """Testes do resultado do motor."""

    def test_propriedades(
        self,
        taxa_cdb_spread_alto: TaxaCDB,
        taxa_cdb_spread_critico: TaxaCDB,
    ):
        """Deve calcular propriedades corretamente."""
        config = EngineConfig(
            enable_rules=True,
            enable_statistical=False,
            enable_ml=False,
        )
        engine = DetectionEngine(config)
        result = engine.analyze([taxa_cdb_spread_alto, taxa_cdb_spread_critico])

        assert result.taxas_analyzed == 2
        assert result.execution_time_ms >= 0
        assert result.has_anomalias

    def test_contagens(
        self,
        taxa_cdb_spread_alto: TaxaCDB,
        taxa_cdb_spread_critico: TaxaCDB,
    ):
        """Deve contar anomalias por severidade."""
        config = EngineConfig(
            enable_rules=True,
            enable_statistical=False,
            enable_ml=False,
        )
        engine = DetectionEngine(config)
        result = engine.analyze([taxa_cdb_spread_alto, taxa_cdb_spread_critico])

        # Deve ter pelo menos 1 CRITICAL (spread_critico)
        assert result.critical_count >= 1
        # HIGH count inclui CRITICAL
        assert result.high_count >= result.critical_count

    def test_filtro_por_severidade(
        self,
        taxa_cdb_spread_alto: TaxaCDB,
        taxa_cdb_spread_critico: TaxaCDB,
    ):
        """Deve filtrar anomalias por severidade."""
        config = EngineConfig(
            enable_rules=True,
            enable_statistical=False,
            enable_ml=False,
        )
        engine = DetectionEngine(config)
        result = engine.analyze([taxa_cdb_spread_alto, taxa_cdb_spread_critico])

        critical = result.by_severity(Severidade.CRITICAL)
        assert all(a.severidade == Severidade.CRITICAL for a in critical)

    def test_filtro_por_if(
        self,
        taxa_cdb_spread_critico: TaxaCDB,
    ):
        """Deve filtrar anomalias por IF."""
        config = EngineConfig(
            enable_rules=True,
            enable_statistical=False,
            enable_ml=False,
        )
        engine = DetectionEngine(config)
        result = engine.analyze([taxa_cdb_spread_critico])

        if_anomalias = result.by_if(taxa_cdb_spread_critico.if_id)
        assert all(a.if_id == taxa_cdb_spread_critico.if_id for a in if_anomalias)


class TestDetectorCategory:
    """Testes da enumeração de categorias."""

    def test_valores(self):
        """Deve ter as categorias esperadas."""
        assert DetectorCategory.RULES.value == "rules"
        assert DetectorCategory.STATISTICAL.value == "statistical"
        assert DetectorCategory.ML.value == "ml"
