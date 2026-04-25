"""Testes unitários para analysis/risk_score.py — score 0-100 e thresholds."""

from decimal import Decimal

import pytest

from veredas.analysis.risk_score import (
    RiskLevel,
    ScoreBreakdown,
    _calcular_basileia_score,
    _calcular_spread_score,
    _calcular_tendencia_score,
    _calcular_volatilidade_score,
    _score_to_level,
    calcular_score_batch,
    calcular_score_risco,
)


# ---------------------------------------------------------------------------
# _calcular_spread_score
# ---------------------------------------------------------------------------


class TestSpreadScore:
    @pytest.mark.parametrize(
        "pct_cdi, esperado",
        [
            (Decimal("95"), 0.0),   # abaixo de 100% — sem risco
            (Decimal("99.9"), 0.0),
            (Decimal("100"), 5.0),  # exato 100%: pct < 100 é False → cai em pct < 110 → 5.0
            (Decimal("105"), 5.0),  # faixa 100-110
            (Decimal("109.9"), 5.0),
            (Decimal("110"), 15.0),  # faixa 110-120 (110 >= 110, < 120)
            (Decimal("115"), 15.0),
            (Decimal("120"), 25.0),  # faixa 120-130
            (Decimal("125"), 25.0),
            (Decimal("130"), 35.0),  # faixa 130-150
            (Decimal("140"), 35.0),
            (Decimal("150"), 40.0),  # >= 150 → máximo
            (Decimal("160"), 40.0),
        ],
    )
    def test_spread_score(self, pct_cdi, esperado):
        assert _calcular_spread_score(pct_cdi) == esperado

    def test_none_retorna_zero(self):
        assert _calcular_spread_score(None) == 0.0


# ---------------------------------------------------------------------------
# _calcular_basileia_score
# ---------------------------------------------------------------------------


class TestBasileiaScore:
    @pytest.mark.parametrize(
        "basileia, esperado",
        [
            (Decimal("20.0"), 0.0),   # > 15% — confortável
            (Decimal("15.1"), 0.0),
            (Decimal("15.0"), 10.0),  # exato 15%: ib > 15 é False → cai em ib > 12 → 10.0
            (Decimal("13.5"), 10.0),  # 12 < x <= 15
            (Decimal("12.1"), 10.0),
            (Decimal("12.0"), 20.0),  # boundary: > 12 é False, > 10.5 é True → 20.0
            (Decimal("11.0"), 20.0),  # 10.5 < x <= 12
            (Decimal("10.5"), 30.0),  # <= 10.5 → abaixo do mínimo regulatório
            (Decimal("9.0"), 30.0),
            (None, 15.0),             # sem dados → risco médio
        ],
    )
    def test_basileia_score(self, basileia, esperado):
        assert _calcular_basileia_score(basileia) == esperado

    def test_exatamente_minimo_regulatorio_e_30(self):
        """10.5% exato: não é > 10.5, logo cai no else → 30 (abaixo do mínimo)."""
        assert _calcular_basileia_score(Decimal("10.5")) == 30.0

    def test_acima_minimo_e_20(self):
        """10.51% é > 10.5 mas < 12 → 20."""
        assert _calcular_basileia_score(Decimal("10.51")) == 20.0


# ---------------------------------------------------------------------------
# _score_to_level — boundaries críticos
# ---------------------------------------------------------------------------


class TestScoreToLevel:
    @pytest.mark.parametrize(
        "score, level",
        [
            (0, RiskLevel.BAIXO),
            (25, RiskLevel.BAIXO),
            (25.1, RiskLevel.MEDIO),
            (50, RiskLevel.MEDIO),
            (50.1, RiskLevel.ALTO),
            (75, RiskLevel.ALTO),
            (75.1, RiskLevel.CRITICO),
            (100, RiskLevel.CRITICO),
        ],
    )
    def test_boundaries(self, score, level):
        assert _score_to_level(score) == level


# ---------------------------------------------------------------------------
# _calcular_volatilidade_score
# ---------------------------------------------------------------------------


class TestVolatilidadeScore:
    @pytest.mark.parametrize(
        "var7d, var30d, esperado",
        [
            (None, None, 0.0),
            (1.0, None, 0.0),   # < 2pp → 0
            (2.0, None, 5.0),   # >= 2pp → 5
            (5.0, None, 10.0),  # >= 5pp → 10
            (10.0, None, 15.0), # >= 10pp → 15
            (20.0, None, 20.0), # >= 20pp → 20
            (None, 10.0, 10.0),  # 30d normalizado: 10/2=5 → max(0,5)=5 >= 5 → 10
        ],
    )
    def test_volatilidade_score(self, var7d, var30d, esperado):
        assert _calcular_volatilidade_score(var7d, var30d) == esperado


# ---------------------------------------------------------------------------
# _calcular_tendencia_score
# ---------------------------------------------------------------------------


class TestTendenciaScore:
    @pytest.mark.parametrize(
        "tendencia, esperado",
        [
            (None, 0.0),
            ("estavel", 0.0),
            ("queda", 0.0),
            ("caindo", 0.0),
            ("subindo_leve", 3.0),
            ("leve_alta", 3.0),
            ("subindo", 6.0),
            ("alta", 6.0),
            ("subindo_forte", 10.0),
            ("forte_alta", 10.0),
            ("SUBINDO_FORTE", 10.0),  # case insensitive
            ("desconhecido", 0.0),
        ],
    )
    def test_tendencia_score(self, tendencia, esperado):
        assert _calcular_tendencia_score(tendencia) == esperado


# ---------------------------------------------------------------------------
# calcular_score_risco — integração dos componentes
# ---------------------------------------------------------------------------


class TestCalcularScoreRisco:
    def test_sem_dados_score_15_baixo(self):
        """Sem dados: spread=0, basileia=15 (None), vol=0, tendencia=0 → 15 → BAIXO."""
        result = calcular_score_risco()
        assert result.score == 15.0
        assert result.level == RiskLevel.BAIXO

    def test_score_e_soma_dos_componentes(self):
        result = calcular_score_risco(
            percentual_cdi=Decimal("140"),  # spread=35
            indice_basileia=Decimal("9.0"),  # basileia=30
            variacao_7d=25.0,               # vol=20
            tendencia="subindo_forte",       # tendencia=10
        )
        assert result.score == 95.0
        assert result.level == RiskLevel.CRITICO
        assert result.breakdown.spread_score == 35.0
        assert result.breakdown.basileia_score == 30.0
        assert result.breakdown.volatilidade_score == 20.0
        assert result.breakdown.tendencia_score == 10.0

    def test_breakdown_total_igual_score(self):
        result = calcular_score_risco(
            percentual_cdi=Decimal("120"),
            indice_basileia=Decimal("13.0"),
        )
        assert result.breakdown.total == result.score

    def test_if_data_extrai_basileia(self):
        from unittest.mock import MagicMock

        mock_if = MagicMock()
        mock_if.id = 1
        mock_if.nome = "Banco Teste"
        mock_if.indice_basileia = Decimal("20.0")

        result = calcular_score_risco(if_data=mock_if)
        assert result.breakdown.basileia_score == 0.0
        assert result.if_id == 1
        assert result.if_nome == "Banco Teste"

    def test_taxa_atual_extrai_percentual(self):
        from unittest.mock import MagicMock

        mock_taxa = MagicMock()
        mock_taxa.percentual = Decimal("160")

        result = calcular_score_risco(taxa_atual=mock_taxa)
        assert result.breakdown.spread_score == 40.0

    def test_nivel_correto_para_score_medio(self):
        result = calcular_score_risco(
            percentual_cdi=Decimal("115"),  # 15
            indice_basileia=Decimal("13.0"),  # 10
        )
        assert result.score == 25.0
        assert result.level == RiskLevel.BAIXO

    def test_detalhes_populados(self):
        result = calcular_score_risco(
            percentual_cdi=Decimal("110"),
            variacao_7d=3.0,
            tendencia="queda",
        )
        assert result.detalhes["percentual_cdi"] == 110.0
        assert result.detalhes["variacao_7d"] == 3.0
        assert result.detalhes["tendencia"] == "queda"


# ---------------------------------------------------------------------------
# ScoreBreakdown.total
# ---------------------------------------------------------------------------


class TestScoreBreakdown:
    def test_total_e_soma(self):
        b = ScoreBreakdown(
            spread_score=25.0,
            basileia_score=10.0,
            volatilidade_score=5.0,
            tendencia_score=3.0,
        )
        assert b.total == 43.0
