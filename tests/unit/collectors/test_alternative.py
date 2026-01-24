"""
Testes unitários para coletores de dados alternativos (Fase 4).
"""

import pytest
from datetime import date, datetime
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

from veredas.collectors.alternative import (
    ReclameAquiCollector,
    BacenProcessosCollector,
    ReputacaoRA,
    Reclamacao,
    ProcessoBC,
    HistoricoProcessosIF,
    TipoProcesso,
    StatusProcesso,
)


class TestReputacaoRA:
    """Testes para dataclass ReputacaoRA."""

    def test_reputacao_creation(self):
        """Testa criação de ReputacaoRA."""
        reputacao = ReputacaoRA(
            empresa_nome="Itaú Unibanco",
            empresa_cnpj="60.701.190/0001-04",
            nota_geral=Decimal("7.5"),
            total_reclamacoes=50000,
            reclamacoes_respondidas=47500,
            reclamacoes_resolvidas=42500,
            indice_solucao=Decimal("85.0"),
            nota_consumidor=Decimal("8.0"),
            voltariam_a_fazer_negocio=Decimal("75.0"),
        )

        assert reputacao.empresa_nome == "Itaú Unibanco"
        assert reputacao.nota_geral == Decimal("7.5")
        assert reputacao.indice_solucao == Decimal("85.0")

    def test_reputacao_ruim(self):
        """Testa reputação ruim."""
        reputacao = ReputacaoRA(
            empresa_nome="Banco XYZ",
            nota_geral=Decimal("3.5"),
            indice_solucao=Decimal("30.0"),
            total_reclamacoes=10000,
            reclamacoes_respondidas=5000,
            reclamacoes_resolvidas=3000,
        )

        assert reputacao.nota_geral < Decimal("6.0")
        assert reputacao.reputacao_ruim is True

    def test_taxa_resposta(self):
        """Testa cálculo da taxa de resposta."""
        reputacao = ReputacaoRA(
            empresa_nome="Banco Teste",
            total_reclamacoes=100,
            reclamacoes_respondidas=80,
        )
        assert reputacao.taxa_resposta == Decimal("80")


class TestReclamacao:
    """Testes para dataclass Reclamacao."""

    def test_reclamacao_creation(self):
        """Testa criação de Reclamacao."""
        reclamacao = Reclamacao(
            titulo="Problema com saque",
            descricao="Não consegui sacar meu dinheiro",
            data_reclamacao=date(2024, 1, 15),
            categoria="Saque",
            status="RESPONDIDA",
            avaliacao=8,
            resolvido=True,
        )

        assert reclamacao.titulo == "Problema com saque"
        assert reclamacao.resolvido is True
        assert reclamacao.avaliacao == 8


class TestTipoProcesso:
    """Testes para enum TipoProcesso."""

    def test_tipos_processo(self):
        """Verifica valores do enum."""
        assert TipoProcesso.ADMINISTRATIVO_SANCIONADOR.value == "PAS"
        assert TipoProcesso.MULTA.value == "MULTA"
        assert TipoProcesso.INTERVENCAO.value == "INTERVENCAO"
        assert TipoProcesso.LIQUIDACAO.value == "LIQUIDACAO"


class TestStatusProcesso:
    """Testes para enum StatusProcesso."""

    def test_status_processo(self):
        """Verifica valores do enum."""
        assert StatusProcesso.ABERTO.value == "ABERTO"
        assert StatusProcesso.ARQUIVADO.value == "ARQUIVADO"
        assert StatusProcesso.JULGADO.value == "JULGADO"
        assert StatusProcesso.EM_ANDAMENTO.value == "EM_ANDAMENTO"


class TestProcessoBC:
    """Testes para dataclass ProcessoBC."""

    def test_processo_creation(self):
        """Testa criação de ProcessoBC."""
        processo = ProcessoBC(
            numero="12345/2024",
            tipo=TipoProcesso.ADMINISTRATIVO_SANCIONADOR,
            status=StatusProcesso.ABERTO,
            instituicao_cnpj="00.000.000/0001-00",
            instituicao_nome="Banco Teste",
            data_abertura=date(2024, 1, 10),
            descricao="Descumprimento de normas",
        )

        assert processo.numero == "12345/2024"
        assert processo.tipo == TipoProcesso.ADMINISTRATIVO_SANCIONADOR
        assert processo.status == StatusProcesso.ABERTO

    def test_processo_com_multa(self):
        """Testa processo com multa."""
        processo = ProcessoBC(
            numero="67890/2023",
            tipo=TipoProcesso.MULTA,
            status=StatusProcesso.JULGADO,
            instituicao_cnpj="00.000.000/0001-00",
            instituicao_nome="Financeira ABC",
            data_abertura=date(2023, 6, 15),
            data_julgamento=date(2024, 1, 20),
            valor_multa=Decimal("500000.00"),
            descricao="Irregularidades contábeis",
        )

        assert processo.valor_multa == Decimal("500000.00")
        assert processo.status == StatusProcesso.JULGADO

    def test_processo_eh_grave(self):
        """Testa verificação de processo grave."""
        processo = ProcessoBC(
            numero="99999/2024",
            tipo=TipoProcesso.INTERVENCAO,
            status=StatusProcesso.ABERTO,
            instituicao_cnpj="00.000.000/0001-00",
            instituicao_nome="Banco Problemático",
            data_abertura=date(2024, 1, 1),
        )

        assert processo.eh_grave is True


class TestHistoricoProcessosIF:
    """Testes para dataclass HistoricoProcessosIF."""

    def test_historico_creation(self):
        """Testa criação de histórico."""
        processos = [
            ProcessoBC(
                numero="111/2024",
                tipo=TipoProcesso.ADMINISTRATIVO_SANCIONADOR,
                status=StatusProcesso.ABERTO,
                instituicao_cnpj="00.000.000/0001-00",
                instituicao_nome="Banco X",
                data_abertura=date(2024, 1, 5),
            ),
            ProcessoBC(
                numero="222/2023",
                tipo=TipoProcesso.MULTA,
                status=StatusProcesso.ARQUIVADO,
                instituicao_cnpj="00.000.000/0001-00",
                instituicao_nome="Banco X",
                data_abertura=date(2023, 3, 10),
            ),
        ]

        historico = HistoricoProcessosIF(
            cnpj="00.000.000/0001-00",
            nome="Banco X",
            processos=processos,
            total_processos=2,
            processos_abertos=1,
            valor_total_multas=Decimal("0"),
        )

        assert historico.total_processos == 2
        assert historico.processos_abertos == 1


class TestReclameAquiCollector:
    """Testes para ReclameAquiCollector."""

    def test_collector_source_name(self):
        """Testa nome da fonte."""
        collector = ReclameAquiCollector()
        assert collector.source_name == "reclame_aqui"

    @pytest.mark.asyncio
    async def test_health_check_success(self):
        """Testa health check com sucesso."""
        collector = ReclameAquiCollector()

        with patch.object(collector, "_client") as mock_client:
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_client.get = AsyncMock(return_value=mock_response)

            result = await collector.health_check()
            assert result is True


class TestBacenProcessosCollector:
    """Testes para BacenProcessosCollector."""

    def test_collector_source_name(self):
        """Testa nome da fonte."""
        collector = BacenProcessosCollector()
        assert collector.source_name == "bacen_processos"

    @pytest.mark.asyncio
    async def test_health_check_success(self):
        """Testa health check com sucesso."""
        collector = BacenProcessosCollector()

        with patch.object(collector, "_client") as mock_client:
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_client.get = AsyncMock(return_value=mock_response)

            result = await collector.health_check()
            assert result is True
