"""Testes unitários para detectores baseados em regras."""

from decimal import Decimal

from tests.conftest import make_taxa
from veredas.detectors.rules import (
    DivergenciaDetector,
    RuleThresholds,
    SpreadDetector,
    VariacaoDetector,
)
from veredas.storage.models import Indexador, Severidade, TipoAnomalia

# ---------------------------------------------------------------------------
# SpreadDetector — CDI
# ---------------------------------------------------------------------------

class TestSpreadDetectorCDI:
    def setup_method(self):
        self.detector = SpreadDetector()

    def test_taxa_normal_nao_gera_anomalia(self):
        taxas = [make_taxa(if_id=1, percentual=110.0)]
        result = self.detector.detect(taxas)
        assert result.success
        assert len(result.anomalias) == 0

    def test_spread_alto_gera_high(self):
        taxas = [make_taxa(if_id=1, percentual=140.0)]
        result = self.detector.detect(taxas)
        assert len(result.anomalias) == 1
        a = result.anomalias[0]
        assert a.tipo == TipoAnomalia.SPREAD_ALTO
        assert a.severidade == Severidade.HIGH
        assert a.valor_detectado == Decimal("140.0")

    def test_spread_critico_gera_critical(self):
        taxas = [make_taxa(if_id=1, percentual=160.0)]
        result = self.detector.detect(taxas)
        assert len(result.anomalias) == 1
        a = result.anomalias[0]
        assert a.tipo == TipoAnomalia.SPREAD_CRITICO
        assert a.severidade == Severidade.CRITICAL

    def test_exatamente_no_threshold_nao_gera(self):
        # 130% exato não ultrapassa o threshold (usa >)
        taxas = [make_taxa(if_id=1, percentual=130.0)]
        result = self.detector.detect(taxas)
        assert len(result.anomalias) == 0

    def test_multiplas_taxas_detecta_todas_anomalas(self):
        taxas = [
            make_taxa(if_id=1, percentual=110.0),
            make_taxa(if_id=2, percentual=135.0),
            make_taxa(if_id=3, percentual=155.0),
        ]
        result = self.detector.detect(taxas)
        assert len(result.anomalias) == 2

    def test_lista_vazia_retorna_sem_anomalias(self):
        result = self.detector.detect([])
        assert result.success
        assert len(result.anomalias) == 0

    def test_thresholds_customizados(self):
        thresholds = RuleThresholds(spread_alto=Decimal("120"), spread_critico=Decimal("140"))
        detector = SpreadDetector(thresholds=thresholds)
        taxas = [make_taxa(if_id=1, percentual=125.0)]
        result = detector.detect(taxas)
        assert len(result.anomalias) == 1
        assert result.anomalias[0].severidade == Severidade.HIGH

    def test_indexador_nao_cdi_ignorado(self):
        taxas = [make_taxa(if_id=1, percentual=200.0, indexador=Indexador.PREFIXADO)]
        result = self.detector.detect(taxas)
        assert len(result.anomalias) == 0


# ---------------------------------------------------------------------------
# SpreadDetector — IPCA+
# ---------------------------------------------------------------------------

class TestSpreadDetectorIPCA:
    def setup_method(self):
        self.detector = SpreadDetector()

    def test_ipca_normal_nao_gera(self):
        taxas = [make_taxa(if_id=1, percentual=108.0, indexador=Indexador.IPCA, taxa_adicional=8.0)]
        result = self.detector.detect(taxas)
        assert len(result.anomalias) == 0

    def test_ipca_spread_alto_gera_high(self):
        taxas = [make_taxa(if_id=1, percentual=112.0, indexador=Indexador.IPCA, taxa_adicional=12.0)]
        result = self.detector.detect(taxas)
        assert len(result.anomalias) == 1
        assert result.anomalias[0].severidade == Severidade.HIGH

    def test_ipca_spread_critico_gera_critical(self):
        taxas = [make_taxa(if_id=1, percentual=120.0, indexador=Indexador.IPCA, taxa_adicional=20.0)]
        result = self.detector.detect(taxas)
        assert len(result.anomalias) == 1
        assert result.anomalias[0].severidade == Severidade.CRITICAL

    def test_ipca_sem_taxa_adicional_ignorado(self):
        taxas = [make_taxa(if_id=1, percentual=120.0, indexador=Indexador.IPCA)]
        result = self.detector.detect(taxas)
        assert len(result.anomalias) == 0


# ---------------------------------------------------------------------------
# VariacaoDetector
# ---------------------------------------------------------------------------

class TestVariacaoDetector:
    def setup_method(self):
        self.detector = VariacaoDetector()

    def _taxa_par(self, percentual_anterior: float, percentual_atual: float):
        anterior = [make_taxa(if_id=1, percentual=percentual_anterior)]
        atual = [make_taxa(if_id=1, percentual=percentual_atual)]
        return atual, anterior

    def test_sem_variacao_nao_gera(self):
        atual, anterior = self._taxa_par(100.0, 100.0)
        result = self.detector.detect(atual, anterior)
        assert len(result.anomalias) == 0

    def test_queda_ignorada(self):
        atual, anterior = self._taxa_par(120.0, 100.0)
        result = self.detector.detect(atual, anterior)
        assert len(result.anomalias) == 0

    def test_salto_brusco_gera_medium(self):
        atual, anterior = self._taxa_par(100.0, 115.0)
        result = self.detector.detect(atual, anterior)
        assert len(result.anomalias) == 1
        assert result.anomalias[0].tipo == TipoAnomalia.SALTO_BRUSCO
        assert result.anomalias[0].severidade == Severidade.MEDIUM

    def test_salto_extremo_gera_high(self):
        atual, anterior = self._taxa_par(100.0, 125.0)
        result = self.detector.detect(atual, anterior)
        assert len(result.anomalias) == 1
        assert result.anomalias[0].tipo == TipoAnomalia.SALTO_EXTREMO
        assert result.anomalias[0].severidade == Severidade.HIGH

    def test_sem_historico_anterior_nao_detecta(self):
        atual = [make_taxa(if_id=1, percentual=150.0)]
        result = self.detector.detect(atual, [])
        assert len(result.anomalias) == 0

    def test_if_sem_historico_ignorado(self):
        # IF 1 não tem dado anterior — não deve gerar anomalia
        atual = [make_taxa(if_id=1, percentual=130.0)]
        anterior = [make_taxa(if_id=2, percentual=100.0)]
        result = self.detector.detect(atual, anterior)
        assert len(result.anomalias) == 0


# ---------------------------------------------------------------------------
# DivergenciaDetector
# ---------------------------------------------------------------------------

class TestDivergenciaDetector:
    def setup_method(self):
        self.detector = DivergenciaDetector()

    def test_taxa_normal_nao_gera(self):
        taxas = [make_taxa(if_id=1, percentual=105.0)]
        result = self.detector.detect(taxas, media=Decimal("100"), desvio_padrao=Decimal("5"))
        assert len(result.anomalias) == 0

    def test_divergencia_medium(self):
        # z-score = (115 - 100) / 5 = 3.0 > 2σ
        taxas = [make_taxa(if_id=1, percentual=115.0)]
        result = self.detector.detect(taxas, media=Decimal("100"), desvio_padrao=Decimal("5"))
        assert len(result.anomalias) == 1
        assert result.anomalias[0].tipo == TipoAnomalia.DIVERGENCIA
        assert result.anomalias[0].severidade == Severidade.MEDIUM

    def test_divergencia_extrema_high(self):
        # z-score = (120 - 100) / 5 = 4.0 > 3σ
        taxas = [make_taxa(if_id=1, percentual=120.0)]
        result = self.detector.detect(taxas, media=Decimal("100"), desvio_padrao=Decimal("5"))
        assert len(result.anomalias) == 1
        assert result.anomalias[0].tipo == TipoAnomalia.DIVERGENCIA_EXTREMA
        assert result.anomalias[0].severidade == Severidade.HIGH

    def test_abaixo_da_media_ignorado(self):
        taxas = [make_taxa(if_id=1, percentual=80.0)]
        result = self.detector.detect(taxas, media=Decimal("100"), desvio_padrao=Decimal("5"))
        assert len(result.anomalias) == 0

    def test_desvio_zero_retorna_sem_anomalias(self):
        taxas = [make_taxa(if_id=1, percentual=200.0)]
        result = self.detector.detect(taxas, media=Decimal("100"), desvio_padrao=Decimal("0"))
        assert result.success
        assert len(result.anomalias) == 0
