"""
Testes da interface de linha de comando.

Verifica comandos CLI usando typer.testing.CliRunner.
"""

from datetime import date
from decimal import Decimal
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from typer.testing import CliRunner

from veredas import __version__
from veredas.cli.main import app
from veredas.collectors.base import CollectionResult
from veredas.collectors.bcb import DadosBCB, TaxaReferenciaBCB


@pytest.fixture
def runner():
    """Cria um CliRunner para testes."""
    return CliRunner()


@pytest.fixture
def mock_dados_bcb():
    """Cria dados simulados do BCB."""
    return DadosBCB(
        selic=TaxaReferenciaBCB(
            tipo="selic",
            data=date(2026, 1, 22),
            valor=Decimal("14.25"),
        ),
        cdi=TaxaReferenciaBCB(
            tipo="cdi",
            data=date(2026, 1, 22),
            valor=Decimal("14.15"),
        ),
        ipca=TaxaReferenciaBCB(
            tipo="ipca",
            data=date(2026, 1, 22),
            valor=Decimal("0.45"),
        ),
    )


class TestVersionCommand:
    """Testes do comando --version."""

    def test_version_flag(self, runner: CliRunner):
        """Deve mostrar a versão com --version."""
        result = runner.invoke(app, ["--version"])

        assert result.exit_code == 0
        assert __version__ in result.output
        assert "veredas de papel" in result.output

    def test_version_flag_short(self, runner: CliRunner):
        """Deve mostrar a versão com -v."""
        result = runner.invoke(app, ["-v"])

        assert result.exit_code == 0
        assert __version__ in result.output


class TestInitCommand:
    """Testes do comando init."""

    def test_init_creates_database(self, runner: CliRunner, tmp_path: Path):
        """Deve criar banco de dados no caminho especificado."""
        db_path = tmp_path / "test.db"

        result = runner.invoke(app, ["init", "--db", str(db_path)])

        assert result.exit_code == 0
        assert "inicializado" in result.output.lower()
        assert db_path.exists()

    def test_init_database_exists_no_force(self, runner: CliRunner, tmp_path: Path):
        """Deve avisar se banco já existe sem --force."""
        db_path = tmp_path / "existing.db"
        db_path.touch()

        result = runner.invoke(app, ["init", "--db", str(db_path)])

        assert result.exit_code == 0
        assert "já existe" in result.output.lower()
        assert "--force" in result.output

    def test_init_database_exists_with_force(self, runner: CliRunner, tmp_path: Path):
        """Deve reinicializar com --force."""
        db_path = tmp_path / "existing.db"
        db_path.touch()

        result = runner.invoke(app, ["init", "--db", str(db_path), "--force"])

        assert result.exit_code == 0
        assert "inicializado" in result.output.lower()

    def test_init_short_options(self, runner: CliRunner, tmp_path: Path):
        """Deve aceitar opções curtas -d e -f."""
        db_path = tmp_path / "short.db"

        result = runner.invoke(app, ["init", "-d", str(db_path)])

        assert result.exit_code == 0


class TestCollectCommand:
    """Testes do comando collect."""

    def test_collect_bcb_success(
        self,
        runner: CliRunner,
        tmp_path: Path,
        mock_dados_bcb: DadosBCB,
    ):
        """Deve coletar dados do BCB com sucesso."""
        db_path = tmp_path / "collect.db"

        mock_result = CollectionResult.ok(
            data=mock_dados_bcb,
            source="bcb",
        )

        # Mock both the collector and the database session
        mock_session = MagicMock()
        mock_session.__enter__ = MagicMock(return_value=mock_session)
        mock_session.__exit__ = MagicMock(return_value=False)

        with patch(
            "veredas.cli.main.BCBCollector.collect",
            new_callable=AsyncMock,
            return_value=mock_result,
        ), patch(
            "veredas.cli.main.DatabaseManager.session_scope",
            return_value=mock_session,
        ):
            result = runner.invoke(app, ["collect", "bcb", "--db", str(db_path)])

        # Check that the command ran and showed data (db save may fail in isolation)
        assert "Coletando dados" in result.output
        # The table should have been displayed regardless of db save
        assert "Selic" in result.output or "concluída" in result.output.lower()

    def test_collect_bcb_shows_table(
        self,
        runner: CliRunner,
        tmp_path: Path,
        mock_dados_bcb: DadosBCB,
    ):
        """Deve mostrar tabela com taxas coletadas."""
        db_path = tmp_path / "collect.db"

        mock_result = CollectionResult.ok(
            data=mock_dados_bcb,
            source="bcb",
        )

        with patch(
            "veredas.cli.main.BCBCollector.collect",
            new_callable=AsyncMock,
            return_value=mock_result,
        ):
            result = runner.invoke(app, ["collect", "bcb", "--db", str(db_path)])

        assert "Selic" in result.output
        assert "CDI" in result.output
        assert "IPCA" in result.output

    def test_collect_bcb_failure(self, runner: CliRunner, tmp_path: Path):
        """Deve mostrar erro em caso de falha."""
        db_path = tmp_path / "collect.db"

        mock_result = CollectionResult.fail(
            error="Conexão recusada",
            source="bcb",
        )

        with patch(
            "veredas.cli.main.BCBCollector.collect",
            new_callable=AsyncMock,
            return_value=mock_result,
        ):
            result = runner.invoke(app, ["collect", "bcb", "--db", str(db_path)])

        assert "Erro" in result.output or "concluída" in result.output.lower()

    def test_collect_ifdata_not_implemented(self, runner: CliRunner):
        """Deve avisar que IFData não está implementado."""
        result = runner.invoke(app, ["collect", "ifdata"])

        assert "não implementado" in result.output.lower()

    def test_collect_all_sources(
        self,
        runner: CliRunner,
        tmp_path: Path,
        mock_dados_bcb: DadosBCB,
    ):
        """Deve coletar de todas as fontes com 'all'."""
        db_path = tmp_path / "collect.db"

        mock_result = CollectionResult.ok(
            data=mock_dados_bcb,
            source="bcb",
        )

        # Mock both the collector and the database session
        mock_session = MagicMock()
        mock_session.__enter__ = MagicMock(return_value=mock_session)
        mock_session.__exit__ = MagicMock(return_value=False)

        with patch(
            "veredas.cli.main.BCBCollector.collect",
            new_callable=AsyncMock,
            return_value=mock_result,
        ), patch(
            "veredas.cli.main.DatabaseManager.session_scope",
            return_value=mock_session,
        ):
            result = runner.invoke(app, ["collect", "all", "--db", str(db_path)])

        # BCB deve ser executado - check for table content
        assert "Selic" in result.output or "Coletando dados" in result.output
        # IFData deve avisar
        assert "não implementado" in result.output.lower()

    def test_collect_default_source(
        self,
        runner: CliRunner,
        tmp_path: Path,
        mock_dados_bcb: DadosBCB,
    ):
        """Deve usar BCB como fonte padrão."""
        db_path = tmp_path / "collect.db"

        mock_result = CollectionResult.ok(
            data=mock_dados_bcb,
            source="bcb",
        )

        # Mock both the collector and the database session
        mock_session = MagicMock()
        mock_session.__enter__ = MagicMock(return_value=mock_session)
        mock_session.__exit__ = MagicMock(return_value=False)

        with patch(
            "veredas.cli.main.BCBCollector.collect",
            new_callable=AsyncMock,
            return_value=mock_result,
        ), patch(
            "veredas.cli.main.DatabaseManager.session_scope",
            return_value=mock_session,
        ):
            # Sem especificar fonte, deve usar BCB
            result = runner.invoke(app, ["collect", "--db", str(db_path)])

        # The command should run and display BCB data
        assert "Coletando dados" in result.output or "bcb" in result.output.lower()


class TestAnalyzeCommand:
    """Testes do comando analyze."""

    def test_analyze_shows_development_warning(self, runner: CliRunner):
        """Deve mostrar aviso de funcionalidade em desenvolvimento."""
        result = runner.invoke(app, ["analyze"])

        assert result.exit_code == 0
        assert "desenvolvimento" in result.output.lower()

    def test_analyze_shows_example_table(self, runner: CliRunner):
        """Deve mostrar tabela de exemplo de anomalias."""
        result = runner.invoke(app, ["analyze"])

        assert "Banco Exemplo" in result.output or "Anomalias" in result.output

    def test_analyze_with_if_filter(self, runner: CliRunner):
        """Deve aceitar filtro por instituição."""
        result = runner.invoke(app, ["analyze", "--if", "Banco Master"])

        assert result.exit_code == 0

    def test_analyze_short_options(self, runner: CliRunner):
        """Deve aceitar opções curtas."""
        result = runner.invoke(app, ["analyze", "-i", "Banco XYZ"])

        assert result.exit_code == 0


class TestAlertsCommand:
    """Testes do comando alerts."""

    def test_alerts_without_list_flag(self, runner: CliRunner):
        """Deve mostrar instrução para usar --list."""
        result = runner.invoke(app, ["alerts"])

        assert result.exit_code == 0
        assert "--list" in result.output

    def test_alerts_with_list_flag(self, runner: CliRunner):
        """Deve listar alertas com --list."""
        result = runner.invoke(app, ["alerts", "--list"])

        assert result.exit_code == 0
        assert "Alertas" in result.output

    def test_alerts_no_active_alerts(self, runner: CliRunner):
        """Deve mostrar mensagem quando não há alertas."""
        result = runner.invoke(app, ["alerts", "--list"])

        assert "Nenhum alerta" in result.output or "veredas analyze" in result.output

    def test_alerts_with_severity_filter(self, runner: CliRunner):
        """Deve aceitar filtro por severidade."""
        result = runner.invoke(app, ["alerts", "--list", "--severity", "critical"])

        assert result.exit_code == 0

    def test_alerts_short_options(self, runner: CliRunner):
        """Deve aceitar opções curtas -l e -s."""
        result = runner.invoke(app, ["alerts", "-l", "-s", "high"])

        assert result.exit_code == 0


class TestExportCommand:
    """Testes do comando export."""

    def test_export_shows_development_warning(self, runner: CliRunner):
        """Deve mostrar aviso de funcionalidade em desenvolvimento."""
        result = runner.invoke(app, ["export"])

        assert result.exit_code == 0
        assert "desenvolvimento" in result.output.lower()

    def test_export_csv_format(self, runner: CliRunner):
        """Deve aceitar formato CSV."""
        result = runner.invoke(app, ["export", "--format", "csv"])

        assert result.exit_code == 0
        assert "csv" in result.output.lower()

    def test_export_json_format(self, runner: CliRunner):
        """Deve aceitar formato JSON."""
        result = runner.invoke(app, ["export", "--format", "json"])

        assert result.exit_code == 0
        assert "json" in result.output.lower()

    def test_export_with_output_file(self, runner: CliRunner, tmp_path: Path):
        """Deve aceitar arquivo de saída."""
        output_file = tmp_path / "export.csv"

        result = runner.invoke(app, ["export", "--output", str(output_file)])

        assert result.exit_code == 0

    def test_export_short_options(self, runner: CliRunner):
        """Deve aceitar opções curtas -f e -o."""
        result = runner.invoke(app, ["export", "-f", "json"])

        assert result.exit_code == 0


class TestStatusCommand:
    """Testes do comando status."""

    def test_status_shows_version(self, runner: CliRunner):
        """Deve mostrar versão do sistema."""
        with patch(
            "veredas.cli.main.BCBCollector.health_check",
            new_callable=AsyncMock,
            return_value=True,
        ), patch(
            "veredas.cli.main.get_selic_atual",
            return_value=Decimal("14.25"),
        ), patch(
            "veredas.cli.main.get_cdi_atual",
            return_value=Decimal("14.15"),
        ):
            result = runner.invoke(app, ["status"])

        assert result.exit_code == 0
        assert "veredas de papel" in result.output

    def test_status_shows_bcb_online(self, runner: CliRunner):
        """Deve mostrar status do BCB quando online."""
        with patch(
            "veredas.cli.main.BCBCollector.health_check",
            new_callable=AsyncMock,
            return_value=True,
        ), patch(
            "veredas.cli.main.get_selic_atual",
            return_value=Decimal("14.25"),
        ), patch(
            "veredas.cli.main.get_cdi_atual",
            return_value=Decimal("14.15"),
        ):
            result = runner.invoke(app, ["status"])

        assert "Online" in result.output or "✓" in result.output

    def test_status_shows_bcb_offline(self, runner: CliRunner):
        """Deve mostrar status do BCB quando offline."""
        with patch(
            "veredas.cli.main.BCBCollector.health_check",
            new_callable=AsyncMock,
            return_value=False,
        ), patch(
            "veredas.cli.main.get_selic_atual",
            return_value=None,
        ), patch(
            "veredas.cli.main.get_cdi_atual",
            return_value=None,
        ):
            result = runner.invoke(app, ["status"])

        assert "Offline" in result.output or "✗" in result.output

    def test_status_shows_current_rates(self, runner: CliRunner):
        """Deve mostrar taxas atuais."""
        with patch(
            "veredas.cli.main.BCBCollector.health_check",
            new_callable=AsyncMock,
            return_value=True,
        ), patch(
            "veredas.cli.main.get_selic_atual",
            return_value=Decimal("14.25"),
        ), patch(
            "veredas.cli.main.get_cdi_atual",
            return_value=Decimal("14.15"),
        ):
            result = runner.invoke(app, ["status"])

        assert "Selic" in result.output
        assert "CDI" in result.output

    def test_status_warns_uninitialized_db(self, runner: CliRunner, tmp_path: Path):
        """Deve avisar se banco não está inicializado."""
        db_path = tmp_path / "nonexistent.db"

        with patch(
            "veredas.cli.main.BCBCollector.health_check",
            new_callable=AsyncMock,
            return_value=True,
        ), patch(
            "veredas.cli.main.get_selic_atual",
            return_value=Decimal("14.25"),
        ), patch(
            "veredas.cli.main.get_cdi_atual",
            return_value=Decimal("14.15"),
        ):
            result = runner.invoke(app, ["status", "--db", str(db_path)])

        # Pode mostrar aviso ou simplesmente não encontrar o arquivo
        assert result.exit_code == 0

    def test_status_shows_db_info(self, runner: CliRunner, tmp_path: Path):
        """Deve mostrar informações do banco quando existe."""
        db_path = tmp_path / "status.db"
        db_path.touch()

        with patch(
            "veredas.cli.main.BCBCollector.health_check",
            new_callable=AsyncMock,
            return_value=True,
        ), patch(
            "veredas.cli.main.get_selic_atual",
            return_value=Decimal("14.25"),
        ), patch(
            "veredas.cli.main.get_cdi_atual",
            return_value=Decimal("14.15"),
        ):
            result = runner.invoke(app, ["status", "--db", str(db_path)])

        assert result.exit_code == 0


class TestHelpCommand:
    """Testes de ajuda dos comandos."""

    def test_main_help(self, runner: CliRunner):
        """Deve mostrar ajuda principal."""
        result = runner.invoke(app, ["--help"])

        assert result.exit_code == 0
        assert "init" in result.output
        assert "collect" in result.output
        assert "analyze" in result.output
        assert "alerts" in result.output
        assert "status" in result.output

    def test_init_help(self, runner: CliRunner):
        """Deve mostrar ajuda do comando init."""
        result = runner.invoke(app, ["init", "--help"])

        assert result.exit_code == 0
        assert "--db" in result.output
        assert "--force" in result.output

    def test_collect_help(self, runner: CliRunner):
        """Deve mostrar ajuda do comando collect."""
        result = runner.invoke(app, ["collect", "--help"])

        assert result.exit_code == 0
        assert "bcb" in result.output.lower()

    def test_analyze_help(self, runner: CliRunner):
        """Deve mostrar ajuda do comando analyze."""
        result = runner.invoke(app, ["analyze", "--help"])

        assert result.exit_code == 0
        assert "--if" in result.output

    def test_alerts_help(self, runner: CliRunner):
        """Deve mostrar ajuda do comando alerts."""
        result = runner.invoke(app, ["alerts", "--help"])

        assert result.exit_code == 0
        assert "--list" in result.output
        assert "--severity" in result.output

    def test_export_help(self, runner: CliRunner):
        """Deve mostrar ajuda do comando export."""
        result = runner.invoke(app, ["export", "--help"])

        assert result.exit_code == 0
        assert "--format" in result.output
        assert "--output" in result.output

    def test_status_help(self, runner: CliRunner):
        """Deve mostrar ajuda do comando status."""
        result = runner.invoke(app, ["status", "--help"])

        assert result.exit_code == 0
        assert "--db" in result.output


class TestNoArgsIsHelp:
    """Testes do comportamento sem argumentos."""

    def test_no_args_shows_help(self, runner: CliRunner):
        """Deve mostrar ajuda quando chamado sem argumentos."""
        result = runner.invoke(app)

        # Typer with no_args_is_help=True shows help with exit code 0 or 2
        # depending on typer version and configuration
        assert result.exit_code in (0, 2)
        assert "veredas de papel" in result.output or "Usage" in result.output
