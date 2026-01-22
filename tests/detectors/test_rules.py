"""
Testes dos detectores baseados em regras.

Verifica detecção de anomalias por spread, variação e divergência.
"""

from decimal import Decimal

import pytest

from veredas.detectors.rules import (
    DivergenciaDetector,
    RuleBasedEngine,
    RuleThresholds,
    SpreadDetector,
    VariacaoDetector,
)
from veredas.storage.models import Severidade, TaxaCDB, TipoAnomalia


class TestSpreadDetector:
    """Testes do detector de spread."""

    def test_taxa_normal_sem_anomalia(self, taxa_cdb_normal: TaxaCDB):
        """Taxa normal não deve gerar anomalia."""
        detector = SpreadDetector()
        result = detector.detect([taxa_cdb_normal])

        assert result.success
        assert not result.has_anomalies
        assert len(result.anomalias) == 0

    def test_spread_alto_gera_anomalia_high(self, taxa_cdb_spread_alto: TaxaCDB):
        """Spread > 130% deve gerar anomalia HIGH."""
        detector = SpreadDetector()
        result = detector.detect([taxa_cdb_spread_alto])

        assert result.has_anomalies
        assert len(result.anomalias) == 1

        anomalia = result.anomalias[0]
        assert anomalia.tipo == TipoAnomalia.SPREAD_ALTO
        assert anomalia.severidade == Severidade.HIGH
        assert anomalia.valor_detectado == Decimal("140.0")

    def test_spread_critico_gera_anomalia_critical(self, taxa_cdb_spread_critico: TaxaCDB):
        """Spread > 150% deve gerar anomalia CRITICAL."""
        detector = SpreadDetector()
        result = detector.detect([taxa_cdb_spread_critico])

        assert result.has_anomalies
        anomalia = result.anomalias[0]
        assert anomalia.tipo == TipoAnomalia.SPREAD_CRITICO
        assert anomalia.severidade == Severidade.CRITICAL

    def test_ipca_spread_alto(self, taxa_cdb_ipca_alto: TaxaCDB):
        """IPCA + X% alto deve gerar anomalia."""
        detector = SpreadDetector()
        result = detector.detect([taxa_cdb_ipca_alto])

        assert result.has_anomalies
        anomalia = result.anomalias[0]
        assert anomalia.tipo == TipoAnomalia.SPREAD_ALTO
        # IPCA + 12% > threshold de 10%

    def test_thresholds_customizados(self, taxa_cdb_spread_alto: TaxaCDB):
        """Deve respeitar thresholds customizados."""
        # Com threshold mais alto, 140% não deveria ser anomalia
        thresholds = RuleThresholds(spread_alto=Decimal("145"))
        detector = SpreadDetector(thresholds)
        result = detector.detect([taxa_cdb_spread_alto])

        assert not result.has_anomalies

    def test_multiplas_taxas(
        self,
        taxa_cdb_normal: TaxaCDB,
        taxa_cdb_spread_alto: TaxaCDB,
        taxa_cdb_spread_critico: TaxaCDB,
    ):
        """Deve detectar anomalias em múltiplas taxas."""
        detector = SpreadDetector()
        result = detector.detect([
            taxa_cdb_normal,
            taxa_cdb_spread_alto,
            taxa_cdb_spread_critico,
        ])

        assert len(result.anomalias) == 2
        assert result.critical_count == 1
        assert result.high_count == 2  # HIGH + CRITICAL

    def test_detector_properties(self):
        """Deve ter propriedades corretas."""
        detector = SpreadDetector()
        assert detector.name == "spread_detector"
        assert "spread" in detector.description.lower()


class TestVariacaoDetector:
    """Testes do detector de variação."""

    def test_variacao_brusca_gera_anomalia(self, taxas_para_variacao):
        """Variação > 10pp deve gerar anomalia MEDIUM."""
        taxa_anterior, taxa_atual = taxas_para_variacao
        detector = VariacaoDetector()
        result = detector.detect([taxa_atual], [taxa_anterior])

        assert result.has_anomalies
        anomalia = result.anomalias[0]
        assert anomalia.tipo == TipoAnomalia.SALTO_BRUSCO
        assert anomalia.severidade == Severidade.MEDIUM
        assert anomalia.desvio == Decimal("15.0")  # 125 - 110

    def test_variacao_extrema_gera_anomalia_high(
        self,
        db_session,
        instituicao_risco,
    ):
        """Variação > 20pp deve gerar anomalia HIGH."""
        from datetime import datetime, timedelta

        # Taxa anterior
        taxa_anterior = TaxaCDB(
            if_id=instituicao_risco.id,
            data_coleta=datetime.now() - timedelta(days=7),
            indexador="cdi",
            percentual=Decimal("110.0"),
            prazo_dias=365,
            fonte="teste",
        )
        db_session.add(taxa_anterior)

        # Taxa atual com salto extremo (+25pp)
        taxa_atual = TaxaCDB(
            if_id=instituicao_risco.id,
            data_coleta=datetime.now(),
            indexador="cdi",
            percentual=Decimal("135.0"),
            prazo_dias=365,
            fonte="teste",
        )
        db_session.add(taxa_atual)
        db_session.commit()

        detector = VariacaoDetector()
        result = detector.detect([taxa_atual], [taxa_anterior])

        assert result.has_anomalies
        anomalia = result.anomalias[0]
        assert anomalia.tipo == TipoAnomalia.SALTO_EXTREMO
        assert anomalia.severidade == Severidade.HIGH

    def test_variacao_negativa_ignorada(self, db_session, instituicao_exemplo):
        """Variação negativa (queda de taxa) não deve gerar anomalia."""
        from datetime import datetime, timedelta

        taxa_anterior = TaxaCDB(
            if_id=instituicao_exemplo.id,
            data_coleta=datetime.now() - timedelta(days=7),
            indexador="cdi",
            percentual=Decimal("120.0"),
            prazo_dias=365,
            fonte="teste",
        )
        db_session.add(taxa_anterior)

        taxa_atual = TaxaCDB(
            if_id=instituicao_exemplo.id,
            data_coleta=datetime.now(),
            indexador="cdi",
            percentual=Decimal("105.0"),  # Queda de 15pp
            prazo_dias=365,
            fonte="teste",
        )
        db_session.add(taxa_atual)
        db_session.commit()

        detector = VariacaoDetector()
        result = detector.detect([taxa_atual], [taxa_anterior])

        assert not result.has_anomalies

    def test_sem_taxa_anterior(self, taxa_cdb_normal: TaxaCDB):
        """Sem taxa anterior para comparar, não gera anomalia."""
        detector = VariacaoDetector()
        result = detector.detect([taxa_cdb_normal], [])

        assert not result.has_anomalies

    def test_janela_customizada(self):
        """Deve aceitar janela de dias customizada."""
        detector = VariacaoDetector(janela_dias=14)
        assert detector.janela_dias == 14


class TestDivergenciaDetector:
    """Testes do detector de divergência."""

    def test_divergencia_acima_2_sigma(
        self,
        db_session,
        instituicao_risco,
    ):
        """Taxa > média + 2σ deve gerar anomalia MEDIUM."""
        from datetime import datetime

        taxa = TaxaCDB(
            if_id=instituicao_risco.id,
            data_coleta=datetime.now(),
            indexador="cdi",
            percentual=Decimal("130.0"),  # 2.5σ acima
            prazo_dias=365,
            fonte="teste",
        )
        db_session.add(taxa)
        db_session.commit()

        detector = DivergenciaDetector()
        # Média 110, desvio 8 -> 130 = 2.5σ acima
        result = detector.detect(
            [taxa],
            media=Decimal("110.0"),
            desvio_padrao=Decimal("8.0"),
        )

        assert result.has_anomalies
        anomalia = result.anomalias[0]
        assert anomalia.tipo == TipoAnomalia.DIVERGENCIA
        assert anomalia.severidade == Severidade.MEDIUM

    def test_divergencia_acima_3_sigma(
        self,
        db_session,
        instituicao_risco,
    ):
        """Taxa > média + 3σ deve gerar anomalia HIGH."""
        from datetime import datetime

        taxa = TaxaCDB(
            if_id=instituicao_risco.id,
            data_coleta=datetime.now(),
            indexador="cdi",
            percentual=Decimal("145.0"),  # 4.375σ acima
            prazo_dias=365,
            fonte="teste",
        )
        db_session.add(taxa)
        db_session.commit()

        detector = DivergenciaDetector()
        # Média 110, desvio 8 -> 145 = 4.375σ acima
        result = detector.detect(
            [taxa],
            media=Decimal("110.0"),
            desvio_padrao=Decimal("8.0"),
        )

        assert result.has_anomalies
        anomalia = result.anomalias[0]
        assert anomalia.tipo == TipoAnomalia.DIVERGENCIA_EXTREMA
        assert anomalia.severidade == Severidade.HIGH

    def test_taxa_dentro_da_media(self, taxa_cdb_normal: TaxaCDB):
        """Taxa dentro de 2σ não deve gerar anomalia."""
        detector = DivergenciaDetector()
        # 110% com média 108 e desvio 5 = 0.4σ
        result = detector.detect(
            [taxa_cdb_normal],
            media=Decimal("108.0"),
            desvio_padrao=Decimal("5.0"),
        )

        assert not result.has_anomalies

    def test_desvio_zero_nao_quebra(self, taxa_cdb_normal: TaxaCDB):
        """Desvio padrão zero não deve causar erro."""
        detector = DivergenciaDetector()
        result = detector.detect(
            [taxa_cdb_normal],
            media=Decimal("110.0"),
            desvio_padrao=Decimal("0"),
        )

        assert result.success
        assert not result.has_anomalies


class TestRuleBasedEngine:
    """Testes do motor de regras."""

    def test_analyze_spreads(
        self,
        taxa_cdb_normal: TaxaCDB,
        taxa_cdb_spread_critico: TaxaCDB,
    ):
        """Deve executar análise de spreads."""
        engine = RuleBasedEngine()
        result = engine.analyze_spreads([taxa_cdb_normal, taxa_cdb_spread_critico])

        assert result.success
        assert len(result.anomalias) == 1

    def test_run_all_apenas_spread(
        self,
        taxa_cdb_spread_alto: TaxaCDB,
    ):
        """Deve rodar apenas spread se não tiver outros dados."""
        engine = RuleBasedEngine()
        results = engine.run_all([taxa_cdb_spread_alto])

        assert len(results) == 1  # Apenas spread
        assert results[0].has_anomalies

    def test_run_all_completo(
        self,
        taxa_cdb_spread_alto: TaxaCDB,
        taxas_para_variacao,
    ):
        """Deve rodar todos os detectores com dados completos."""
        taxa_anterior, taxa_atual = taxas_para_variacao

        engine = RuleBasedEngine()
        results = engine.run_all(
            taxas_atuais=[taxa_cdb_spread_alto, taxa_atual],
            taxas_anteriores=[taxa_anterior],
            media_mercado=Decimal("110.0"),
            desvio_padrao_mercado=Decimal("5.0"),
        )

        # Spread, variação e divergência
        assert len(results) == 3

    def test_thresholds_customizados(self):
        """Deve aceitar thresholds customizados."""
        thresholds = RuleThresholds(
            spread_alto=Decimal("140"),
            spread_critico=Decimal("160"),
        )
        engine = RuleBasedEngine(thresholds)

        assert engine.thresholds.spread_alto == Decimal("140")


class TestDetectionResult:
    """Testes do resultado de detecção."""

    def test_critical_count(self, taxa_cdb_spread_critico: TaxaCDB):
        """Deve contar anomalias críticas."""
        detector = SpreadDetector()
        result = detector.detect([taxa_cdb_spread_critico])

        assert result.critical_count == 1

    def test_high_count(
        self,
        taxa_cdb_spread_alto: TaxaCDB,
        taxa_cdb_spread_critico: TaxaCDB,
    ):
        """Deve contar anomalias HIGH ou CRITICAL."""
        detector = SpreadDetector()
        result = detector.detect([taxa_cdb_spread_alto, taxa_cdb_spread_critico])

        # HIGH + CRITICAL = 2
        assert result.high_count == 2

    def test_execution_time(self, taxa_cdb_normal: TaxaCDB):
        """Deve registrar tempo de execução."""
        detector = SpreadDetector()
        result = detector.detect([taxa_cdb_normal])

        assert result.execution_time_ms >= 0


class TestAnomaliaDetectada:
    """Testes da classe AnomaliaDetectada."""

    def test_is_critical(self, taxa_cdb_spread_critico: TaxaCDB):
        """Deve identificar anomalia crítica."""
        detector = SpreadDetector()
        result = detector.detect([taxa_cdb_spread_critico])

        anomalia = result.anomalias[0]
        assert anomalia.is_critical

    def test_is_high_or_above(self, taxa_cdb_spread_alto: TaxaCDB):
        """Deve identificar anomalia HIGH ou CRITICAL."""
        detector = SpreadDetector()
        result = detector.detect([taxa_cdb_spread_alto])

        anomalia = result.anomalias[0]
        assert anomalia.is_high_or_above
