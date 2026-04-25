"""Testes unitários para analysis/health.py — thresholds regulatórios de Basileia e liquidez."""

from decimal import Decimal
from unittest.mock import MagicMock

import pytest

from veredas.analysis.health import (
    BENCHMARK_BASILEIA,
    BENCHMARK_LIQUIDEZ,
    MINIMO_BASILEIA,
    HealthStatus,
    analisar_saude_if,
    comparar_com_benchmark,
)


def _make_if(basileia=None, liquidez=None, id=1, nome="Banco Teste"):
    mock = MagicMock()
    mock.id = id
    mock.nome = nome
    mock.segmento = "Banco Comercial"
    mock.indice_basileia = Decimal(str(basileia)) if basileia is not None else None
    mock.indice_liquidez = Decimal(str(liquidez)) if liquidez is not None else None
    return mock


# ---------------------------------------------------------------------------
# Basileia — boundaries críticos
# ---------------------------------------------------------------------------


class TestBasileia:
    def test_abaixo_do_minimo_e_critico(self):
        """9% < 10.5% → CRITICO."""
        resultado = analisar_saude_if(_make_if(basileia=9.0))
        assert resultado.indicadores[0].status == HealthStatus.CRITICO

    def test_exatamente_no_minimo_nao_e_critico(self):
        """10.5% exato: `valor < MINIMO_BASILEIA` é False → não é CRITICO."""
        resultado = analisar_saude_if(_make_if(basileia=10.5))
        assert resultado.indicadores[0].status != HealthStatus.CRITICO
        assert resultado.indicadores[0].status == HealthStatus.ALERTA

    def test_ligeiramente_acima_do_minimo_e_alerta(self):
        """10.51% > 10.5 mas < 12 → ALERTA."""
        resultado = analisar_saude_if(_make_if(basileia=10.51))
        assert resultado.indicadores[0].status == HealthStatus.ALERTA

    def test_proximo_do_benchmark_e_atencao(self):
        """12.5%: entre 12 e BENCHMARK_BASILEIA (15) → ATENCAO."""
        resultado = analisar_saude_if(_make_if(basileia=12.5))
        assert resultado.indicadores[0].status == HealthStatus.ATENCAO

    def test_acima_do_benchmark_e_saudavel(self):
        """18% > 15% → SAUDAVEL."""
        resultado = analisar_saude_if(_make_if(basileia=18.0))
        assert resultado.indicadores[0].status == HealthStatus.SAUDAVEL

    def test_sem_dados_basileia_e_atencao(self):
        resultado = analisar_saude_if(_make_if())
        assert resultado.indicadores[0].status == HealthStatus.ATENCAO


# ---------------------------------------------------------------------------
# Liquidez — boundaries
# ---------------------------------------------------------------------------


class TestLiquidez:
    def test_abaixo_de_1_e_critico(self):
        resultado = analisar_saude_if(_make_if(basileia=20.0, liquidez=0.8))
        assert resultado.indicadores[1].status == HealthStatus.CRITICO

    def test_exatamente_1_nao_e_critico(self):
        """1.0 exato: `valor < 1.0` é False → ALERTA (entre 1.0 e 1.2)."""
        resultado = analisar_saude_if(_make_if(basileia=20.0, liquidez=1.0))
        assert resultado.indicadores[1].status == HealthStatus.ALERTA

    def test_entre_1_2_e_1_5_e_atencao(self):
        resultado = analisar_saude_if(_make_if(basileia=20.0, liquidez=1.3))
        assert resultado.indicadores[1].status == HealthStatus.ATENCAO

    def test_acima_do_benchmark_e_saudavel(self):
        resultado = analisar_saude_if(_make_if(basileia=20.0, liquidez=2.0))
        assert resultado.indicadores[1].status == HealthStatus.SAUDAVEL

    def test_sem_dados_liquidez_e_atencao(self):
        resultado = analisar_saude_if(_make_if(basileia=20.0))
        assert resultado.indicadores[1].status == HealthStatus.ATENCAO


# ---------------------------------------------------------------------------
# status_geral — pior dos indicadores
# ---------------------------------------------------------------------------


class TestStatusGeral:
    def test_basileia_critico_domina(self):
        resultado = analisar_saude_if(_make_if(basileia=9.0, liquidez=2.0))
        assert resultado.status_geral == HealthStatus.CRITICO

    def test_liquidez_critica_domina(self):
        resultado = analisar_saude_if(_make_if(basileia=18.0, liquidez=0.5))
        assert resultado.status_geral == HealthStatus.CRITICO

    def test_ambos_saudaveis(self):
        resultado = analisar_saude_if(_make_if(basileia=18.0, liquidez=2.0))
        assert resultado.status_geral == HealthStatus.SAUDAVEL

    def test_sem_dados_ambos_e_atencao(self):
        resultado = analisar_saude_if(_make_if())
        assert resultado.status_geral == HealthStatus.ATENCAO


# ---------------------------------------------------------------------------
# alertas e recomendações
# ---------------------------------------------------------------------------


class TestAlertas:
    def test_basileia_critico_gera_alerta(self):
        resultado = analisar_saude_if(_make_if(basileia=9.0))
        assert any("Basileia" in a for a in resultado.alertas)

    def test_liquidez_critica_gera_alerta(self):
        resultado = analisar_saude_if(_make_if(basileia=20.0, liquidez=0.5))
        assert any("Liquidez" in a for a in resultado.alertas)

    def test_saudavel_sem_alertas_criticos(self):
        resultado = analisar_saude_if(_make_if(basileia=18.0, liquidez=2.0))
        assert all("ABAIXO" not in a and "INSUFICIENTE" not in a for a in resultado.alertas)

    def test_retorna_if_id_e_nome(self):
        resultado = analisar_saude_if(_make_if(id=42, nome="Banco XYZ"))
        assert resultado.if_id == 42
        assert resultado.if_nome == "Banco XYZ"


# ---------------------------------------------------------------------------
# comparar_com_benchmark
# ---------------------------------------------------------------------------


class TestCompararComBenchmark:
    def test_diff_positivo_acima_do_benchmark(self):
        resultado = comparar_com_benchmark(_make_if(basileia=18.0, liquidez=2.0))
        assert resultado.basileia_diff == Decimal("18.0") - BENCHMARK_BASILEIA
        assert resultado.basileia_diff > 0

    def test_diff_negativo_abaixo_do_benchmark(self):
        resultado = comparar_com_benchmark(_make_if(basileia=12.0, liquidez=1.0))
        assert resultado.basileia_diff < 0

    def test_sem_dados_diff_e_none(self):
        resultado = comparar_com_benchmark(_make_if())
        assert resultado.basileia_diff is None
        assert resultado.liquidez_diff is None

    def test_benchmark_customizado(self):
        custom = Decimal("20.0")
        resultado = comparar_com_benchmark(_make_if(basileia=18.0), benchmark_basileia=custom)
        assert resultado.basileia_benchmark == custom
        assert resultado.basileia_diff == Decimal("18.0") - custom
