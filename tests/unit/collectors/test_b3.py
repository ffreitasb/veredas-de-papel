"""
Testes unitários para integração B3 mercado secundário (Fase 4).
"""

import pytest
from datetime import date, datetime
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

from veredas.collectors.b3 import (
    B3MarketDataCollector,
    B3DataParser,
    TipoTitulo,
    StatusNegociacao,
)
from veredas.collectors.b3.models import (
    PrecoSecundario,
    NegociacaoB3,
    ResumoMercadoSecundario,
    TituloRendaFixa,
)


def _create_preco_secundario(**kwargs) -> PrecoSecundario:
    """Helper para criar PrecoSecundario com valores padrão."""
    defaults = {
        "codigo_titulo": "CDB001",
        "emissor_cnpj": "00.000.000/0001-00",
        "emissor_nome": "Banco Teste",
        "tipo_titulo": TipoTitulo.CDB,
        "data_referencia": date(2024, 1, 15),
        "pu_abertura": Decimal("1000.00"),
        "pu_fechamento": Decimal("995.00"),
        "pu_minimo": Decimal("990.00"),
        "pu_maximo": Decimal("1005.00"),
        "pu_medio": Decimal("997.50"),
        "quantidade_negocios": 10,
        "quantidade_titulos": 100,
        "valor_financeiro": Decimal("100000.00"),
        "taxa_minima": Decimal("100.0"),
        "taxa_maxima": Decimal("105.0"),
        "taxa_media": Decimal("102.5"),
    }
    defaults.update(kwargs)
    return PrecoSecundario(**defaults)


class TestTipoTitulo:
    """Testes para enum TipoTitulo."""

    def test_tipos_titulo_values(self):
        """Verifica valores do enum."""
        assert TipoTitulo.CDB.value == "CDB"
        assert TipoTitulo.LCI.value == "LCI"
        assert TipoTitulo.LCA.value == "LCA"
        assert TipoTitulo.DEBENTURE.value == "DEBENTURE"


class TestStatusNegociacao:
    """Testes para enum StatusNegociacao."""

    def test_status_negociacao_values(self):
        """Verifica valores do enum."""
        assert StatusNegociacao.EXECUTADA.value == "EXECUTADA"
        assert StatusNegociacao.CANCELADA.value == "CANCELADA"
        assert StatusNegociacao.PENDENTE.value == "PENDENTE"


class TestPrecoSecundario:
    """Testes para dataclass PrecoSecundario."""

    def test_preco_secundario_creation(self):
        """Testa criação de PrecoSecundario."""
        preco = _create_preco_secundario(
            codigo_titulo="CDB-ITAU-2025",
            emissor_cnpj="60.701.190/0001-04",
            emissor_nome="Itaú Unibanco",
        )

        assert preco.codigo_titulo == "CDB-ITAU-2025"
        assert preco.tipo_titulo == TipoTitulo.CDB
        assert preco.pu_fechamento == Decimal("995.00")

    def test_preco_secundario_variacao(self):
        """Testa cálculo de variação."""
        preco = _create_preco_secundario(variacao_dia=Decimal("-1.0"))

        assert preco.variacao_dia == Decimal("-1.0")

    def test_preco_secundario_com_volume(self):
        """Testa PrecoSecundario com dados de volume."""
        preco = _create_preco_secundario(
            quantidade_negocios=150,
            quantidade_titulos=10000,
            valor_financeiro=Decimal("10050000.00"),
        )

        assert preco.quantidade_negocios == 150
        assert preco.valor_financeiro == Decimal("10050000.00")

    def test_variacao_pu_dia_property(self):
        """Testa property variacao_pu_dia."""
        preco = _create_preco_secundario(
            pu_abertura=Decimal("1000.00"),
            pu_fechamento=Decimal("990.00"),
        )
        assert preco.variacao_pu_dia == Decimal("-10.00")

    def test_amplitude_dia_property(self):
        """Testa property amplitude_dia."""
        preco = _create_preco_secundario(
            pu_minimo=Decimal("980.00"),
            pu_maximo=Decimal("1010.00"),
        )
        assert preco.amplitude_dia == Decimal("30.00")

    def test_spread_taxa_property(self):
        """Testa property spread_taxa."""
        preco = _create_preco_secundario(
            taxa_minima=Decimal("100.0"),
            taxa_maxima=Decimal("110.0"),
        )
        assert preco.spread_taxa == Decimal("10.0")


class TestNegociacaoB3:
    """Testes para dataclass NegociacaoB3."""

    def test_negociacao_b3_creation(self):
        """Testa criação de NegociacaoB3."""
        negociacao = NegociacaoB3(
            codigo_titulo="CDB-BRAD-2024",
            data_negociacao=date(2024, 1, 15),
            preco_unitario=Decimal("1001.50"),
            quantidade=100,
            valor_financeiro=Decimal("100150.00"),
            taxa_negociada=Decimal("102.5"),
        )

        assert negociacao.codigo_titulo == "CDB-BRAD-2024"
        assert negociacao.preco_unitario == Decimal("1001.50")
        assert negociacao.status == StatusNegociacao.EXECUTADA

    def test_negociacao_with_corretoras(self):
        """Testa negociação com dados de corretoras."""
        negociacao = NegociacaoB3(
            codigo_titulo="CDB-XYZ",
            data_negociacao=date(2024, 1, 15),
            preco_unitario=Decimal("1000.00"),
            quantidade=50,
            valor_financeiro=Decimal("50000.00"),
            taxa_negociada=Decimal("100.0"),
            codigo_corretora_compra="XP123",
            codigo_corretora_venda="BTG456",
        )

        assert negociacao.codigo_corretora_compra == "XP123"
        assert negociacao.codigo_corretora_venda == "BTG456"


class TestResumoMercadoSecundario:
    """Testes para dataclass ResumoMercadoSecundario."""

    def test_resumo_mercado(self):
        """Testa criação de resumo do mercado."""
        preco1 = _create_preco_secundario(codigo_titulo="CDB-1")
        preco2 = _create_preco_secundario(
            codigo_titulo="CDB-2",
            variacao_dia=Decimal("-5.0"),
        )

        resumo = ResumoMercadoSecundario(
            data_referencia=date(2024, 1, 15),
            total_titulos_negociados=2,
            total_negocios=300,
            valor_financeiro_total=Decimal("5000000"),
            maiores_quedas=[preco2],
        )

        assert resumo.total_titulos_negociados == 2
        assert len(resumo.maiores_quedas) == 1


class TestTituloRendaFixa:
    """Testes para dataclass TituloRendaFixa."""

    def test_titulo_creation(self):
        """Testa criação de TituloRendaFixa."""
        titulo = TituloRendaFixa(
            codigo="CDB001",
            tipo=TipoTitulo.CDB,
            emissor_cnpj="00.000.000/0001-00",
            emissor_nome="Banco Teste",
            data_emissao=date(2023, 1, 1),
            data_vencimento=date(2025, 1, 1),
            valor_nominal=Decimal("1000.00"),
            indexador="CDI",
            taxa_emissao=Decimal("110.0"),
        )

        assert titulo.codigo == "CDB001"
        assert titulo.tipo == TipoTitulo.CDB


class TestB3DataParser:
    """Testes para B3DataParser."""

    def test_parser_creation(self):
        """Testa criação do parser."""
        parser = B3DataParser()
        assert parser is not None

    def test_parser_has_parse_method(self):
        """Testa que parser tem método de parse."""
        parser = B3DataParser()
        assert hasattr(parser, "parse_json_response")


class TestB3MarketDataCollector:
    """Testes para B3MarketDataCollector."""

    def test_collector_source_name(self):
        """Testa nome da fonte."""
        collector = B3MarketDataCollector()
        assert collector.source_name == "b3_market_data"

    @pytest.mark.asyncio
    async def test_collector_health_check_success(self):
        """Testa health check com sucesso."""
        collector = B3MarketDataCollector()

        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_client.get = AsyncMock(return_value=mock_response)

        with patch.object(collector, "_get_client", new=AsyncMock(return_value=mock_client)):
            with patch.object(collector, "_close_client", new=AsyncMock()):
                result = await collector.health_check()
                assert result is True

    @pytest.mark.asyncio
    async def test_collector_health_check_failure(self):
        """Testa health check com falha."""
        collector = B3MarketDataCollector()

        with patch.object(collector, "_get_client", new=AsyncMock(side_effect=Exception("Connection failed"))):
            with patch.object(collector, "_close_client", new=AsyncMock()):
                result = await collector.health_check()
                assert result is False
