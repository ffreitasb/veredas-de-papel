"""
Testes do coletor BCB.

Testa a coleta de dados do Banco Central (Selic, CDI, IPCA)
com mocks para evitar chamadas reais a API.
"""

from datetime import date
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import pandas as pd
import pytest

from veredas.collectors.bcb import (
    BCBCollector,
    DadosBCB,
    SERIES_CODES,
    TaxaReferenciaBCB,
    get_cdi_atual,
    get_ipca_atual,
    get_selic_atual,
)


class TestTaxaReferenciaBCB:
    """Testes do dataclass TaxaReferenciaBCB."""

    def test_create_taxa_referencia(self):
        taxa = TaxaReferenciaBCB(
            tipo="selic",
            data=date(2025, 1, 15),
            valor=Decimal("13.25"),
        )
        assert taxa.tipo == "selic"
        assert taxa.data == date(2025, 1, 15)
        assert taxa.valor == Decimal("13.25")
        assert taxa.valor_diario is None

    def test_create_taxa_referencia_with_daily_value(self):
        taxa = TaxaReferenciaBCB(
            tipo="cdi",
            data=date(2025, 1, 15),
            valor=Decimal("13.15"),
            valor_diario=Decimal("0.0489"),
        )
        assert taxa.tipo == "cdi"
        assert taxa.valor_diario == Decimal("0.0489")


class TestDadosBCB:
    """Testes do dataclass DadosBCB."""

    def test_create_empty_dados(self):
        dados = DadosBCB()
        assert dados.selic is None
        assert dados.cdi is None
        assert dados.ipca is None

    def test_create_dados_with_values(self):
        selic = TaxaReferenciaBCB(tipo="selic", data=date(2025, 1, 15), valor=Decimal("13.25"))
        cdi = TaxaReferenciaBCB(tipo="cdi", data=date(2025, 1, 15), valor=Decimal("13.15"))

        dados = DadosBCB(selic=selic, cdi=cdi)
        assert dados.selic is not None
        assert dados.cdi is not None
        assert dados.ipca is None


class TestSeriesCodes:
    """Testes dos codigos das series."""

    def test_series_codes_defined(self):
        assert "selic" in SERIES_CODES
        assert "cdi" in SERIES_CODES
        assert "ipca" in SERIES_CODES
        assert "selic_meta" in SERIES_CODES

    def test_series_codes_values(self):
        assert SERIES_CODES["selic"] == 11
        assert SERIES_CODES["cdi"] == 12
        assert SERIES_CODES["ipca"] == 433
        assert SERIES_CODES["selic_meta"] == 432


class TestBCBCollector:
    """Testes da classe BCBCollector."""

    @pytest.fixture
    def collector(self):
        return BCBCollector()

    @pytest.fixture
    def mock_sgs_dataframe(self):
        """DataFrame simulando resposta do SGS."""
        dates = pd.date_range("2025-01-10", "2025-01-15", freq="D")
        return pd.DataFrame(
            {"selic": [13.20, 13.22, 13.23, 13.24, 13.25, 13.25]},
            index=dates,
        )

    @pytest.fixture
    def mock_cdi_dataframe(self):
        """DataFrame simulando resposta do CDI."""
        dates = pd.date_range("2025-01-10", "2025-01-15", freq="D")
        return pd.DataFrame(
            {"cdi": [13.10, 13.12, 13.13, 13.14, 13.15, 13.15]},
            index=dates,
        )

    @pytest.fixture
    def mock_ipca_dataframe(self):
        """DataFrame simulando resposta do IPCA."""
        dates = pd.date_range("2025-01-01", "2025-01-01", freq="MS")
        return pd.DataFrame(
            {"ipca": [0.52]},
            index=dates,
        )

    def test_source_name(self, collector: BCBCollector):
        assert collector.source_name == "bcb"

    @pytest.mark.asyncio
    async def test_collect_success(
        self,
        collector: BCBCollector,
        mock_sgs_dataframe: pd.DataFrame,
        mock_cdi_dataframe: pd.DataFrame,
        mock_ipca_dataframe: pd.DataFrame,
    ):
        """Testa coleta completa com sucesso."""
        def mock_sgs_get(codes, start, end):
            key = list(codes.keys())[0]
            if key == "selic":
                return mock_sgs_dataframe
            elif key == "cdi":
                return mock_cdi_dataframe
            elif key == "ipca":
                return mock_ipca_dataframe
            return pd.DataFrame()

        with patch("veredas.collectors.bcb.sgs.get", side_effect=mock_sgs_get):
            result = await collector.collect(dias_retroativos=30)

        assert result.success
        assert result.data is not None
        assert result.data.selic is not None
        assert result.data.cdi is not None
        assert result.data.ipca is not None
        assert result.data.selic.valor == Decimal("13.25")
        assert result.data.cdi.valor == Decimal("13.15")
        assert result.data.ipca.valor == Decimal("0.52")

    @pytest.mark.asyncio
    async def test_collect_empty_response(self, collector: BCBCollector):
        """Testa coleta quando API retorna vazio."""
        with patch("veredas.collectors.bcb.sgs.get", return_value=pd.DataFrame()):
            result = await collector.collect(dias_retroativos=30)

        assert result.success
        assert result.data is not None
        assert result.data.selic is None
        assert result.data.cdi is None
        assert result.data.ipca is None

    @pytest.mark.asyncio
    async def test_collect_partial_failure(self, collector: BCBCollector):
        """Testa coleta quando series individuais falham (retorna dados vazios)."""
        with patch("veredas.collectors.bcb.sgs.get", side_effect=Exception("API Error")):
            result = await collector.collect(dias_retroativos=30)

        # Quando series individuais falham, collect ainda retorna sucesso mas com dados None
        assert result.success
        assert result.data is not None
        assert result.data.selic is None
        assert result.data.cdi is None
        assert result.data.ipca is None

    @pytest.mark.asyncio
    async def test_collect_selic_success(
        self,
        collector: BCBCollector,
        mock_sgs_dataframe: pd.DataFrame,
    ):
        """Testa coleta de historico Selic."""
        with patch("veredas.collectors.bcb.sgs.get", return_value=mock_sgs_dataframe):
            result = await collector.collect_selic(dias=30)

        assert result.success
        assert result.data is not None
        assert len(result.data) == 6
        assert all(t.tipo == "selic" for t in result.data)

    @pytest.mark.asyncio
    async def test_collect_selic_empty(self, collector: BCBCollector):
        """Testa coleta de Selic quando nao ha dados."""
        with patch("veredas.collectors.bcb.sgs.get", return_value=pd.DataFrame()):
            result = await collector.collect_selic(dias=30)

        assert not result.success
        assert "Nenhum dado de Selic encontrado" in result.error

    @pytest.mark.asyncio
    async def test_collect_selic_exception(self, collector: BCBCollector):
        """Testa coleta de Selic com excecao."""
        with patch("veredas.collectors.bcb.sgs.get", side_effect=Exception("API Error")):
            result = await collector.collect_selic(dias=30)

        assert not result.success
        assert "Erro ao coletar Selic" in result.error

    @pytest.mark.asyncio
    async def test_collect_selic_meta_success(self, collector: BCBCollector):
        """Testa coleta da meta Selic."""
        dates = pd.date_range("2025-01-01", "2025-01-01", freq="D")
        mock_df = pd.DataFrame({"selic_meta": [13.25]}, index=dates)

        with patch("veredas.collectors.bcb.sgs.get", return_value=mock_df):
            result = await collector.collect_selic_meta()

        assert result.success
        assert result.data is not None
        assert result.data.tipo == "selic_meta"
        assert result.data.valor == Decimal("13.25")

    @pytest.mark.asyncio
    async def test_collect_selic_meta_empty(self, collector: BCBCollector):
        """Testa coleta da meta Selic quando nao ha dados."""
        with patch("veredas.collectors.bcb.sgs.get", return_value=pd.DataFrame()):
            result = await collector.collect_selic_meta()

        assert not result.success
        assert "Nenhum dado de Selic Meta encontrado" in result.error

    @pytest.mark.asyncio
    async def test_collect_selic_meta_exception(self, collector: BCBCollector):
        """Testa coleta da meta Selic com excecao."""
        with patch("veredas.collectors.bcb.sgs.get", side_effect=Exception("API Error")):
            result = await collector.collect_selic_meta()

        assert not result.success
        assert "Erro ao coletar Selic Meta" in result.error

    @pytest.mark.asyncio
    async def test_health_check_success(self, collector: BCBCollector):
        """Testa health check com sucesso."""
        mock_response = MagicMock()
        mock_response.status_code = 200

        with patch("httpx.AsyncClient") as mock_client:
            mock_client.return_value.__aenter__ = AsyncMock(
                return_value=MagicMock(get=AsyncMock(return_value=mock_response))
            )
            mock_client.return_value.__aexit__ = AsyncMock(return_value=None)

            result = await collector.health_check()

        assert result is True

    @pytest.mark.asyncio
    async def test_health_check_failure(self, collector: BCBCollector):
        """Testa health check com falha."""
        mock_response = MagicMock()
        mock_response.status_code = 500

        with patch("httpx.AsyncClient") as mock_client:
            mock_client.return_value.__aenter__ = AsyncMock(
                return_value=MagicMock(get=AsyncMock(return_value=mock_response))
            )
            mock_client.return_value.__aexit__ = AsyncMock(return_value=None)

            result = await collector.health_check()

        assert result is False

    @pytest.mark.asyncio
    async def test_health_check_exception(self, collector: BCBCollector):
        """Testa health check com excecao."""
        with patch("httpx.AsyncClient") as mock_client:
            mock_client.return_value.__aenter__ = AsyncMock(
                side_effect=Exception("Connection Error")
            )

            result = await collector.health_check()

        assert result is False

    @pytest.mark.asyncio
    async def test_collect_serie_invalid_type(self, collector: BCBCollector):
        """Testa coleta de serie com tipo invalido."""
        result = await collector._collect_serie(
            tipo="invalid",
            data_inicio=date(2025, 1, 1),
            data_fim=date(2025, 1, 15),
        )
        assert result is None

    @pytest.mark.asyncio
    async def test_collect_serie_exception(self, collector: BCBCollector):
        """Testa coleta de serie com excecao."""
        with patch("veredas.collectors.bcb.sgs.get", side_effect=Exception("API Error")):
            result = await collector._collect_serie(
                tipo="selic",
                data_inicio=date(2025, 1, 1),
                data_fim=date(2025, 1, 15),
            )
        assert result is None


class TestConvenienceFunctions:
    """Testes das funcoes de conveniencia sincronas."""

    def test_get_selic_atual_success(self):
        """Testa get_selic_atual com sucesso."""
        dates = pd.date_range("2025-01-15", "2025-01-15", freq="D")
        mock_df = pd.DataFrame({"selic": [13.25]}, index=dates)

        with patch("veredas.collectors.bcb.sgs.get", return_value=mock_df):
            result = get_selic_atual()

        assert result == Decimal("13.25")

    def test_get_selic_atual_empty(self):
        """Testa get_selic_atual quando nao ha dados."""
        with patch("veredas.collectors.bcb.sgs.get", return_value=pd.DataFrame()):
            result = get_selic_atual()

        assert result is None

    def test_get_selic_atual_exception(self):
        """Testa get_selic_atual com excecao."""
        with patch("veredas.collectors.bcb.sgs.get", side_effect=Exception("API Error")):
            result = get_selic_atual()

        assert result is None

    def test_get_cdi_atual_success(self):
        """Testa get_cdi_atual com sucesso."""
        dates = pd.date_range("2025-01-15", "2025-01-15", freq="D")
        mock_df = pd.DataFrame({"cdi": [13.15]}, index=dates)

        with patch("veredas.collectors.bcb.sgs.get", return_value=mock_df):
            result = get_cdi_atual()

        assert result == Decimal("13.15")

    def test_get_cdi_atual_empty(self):
        """Testa get_cdi_atual quando nao ha dados."""
        with patch("veredas.collectors.bcb.sgs.get", return_value=pd.DataFrame()):
            result = get_cdi_atual()

        assert result is None

    def test_get_cdi_atual_exception(self):
        """Testa get_cdi_atual com excecao."""
        with patch("veredas.collectors.bcb.sgs.get", side_effect=Exception("API Error")):
            result = get_cdi_atual()

        assert result is None

    def test_get_ipca_atual_success(self):
        """Testa get_ipca_atual com sucesso."""
        dates = pd.date_range("2025-01-01", "2025-01-01", freq="MS")
        mock_df = pd.DataFrame({"ipca": [0.52]}, index=dates)

        with patch("veredas.collectors.bcb.sgs.get", return_value=mock_df):
            result = get_ipca_atual()

        assert result == Decimal("0.52")

    def test_get_ipca_atual_empty(self):
        """Testa get_ipca_atual quando nao ha dados."""
        with patch("veredas.collectors.bcb.sgs.get", return_value=pd.DataFrame()):
            result = get_ipca_atual()

        assert result is None

    def test_get_ipca_atual_exception(self):
        """Testa get_ipca_atual com excecao."""
        with patch("veredas.collectors.bcb.sgs.get", side_effect=Exception("API Error")):
            result = get_ipca_atual()

        assert result is None
