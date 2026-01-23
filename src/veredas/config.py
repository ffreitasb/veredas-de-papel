"""
Configuracoes centralizadas do veredas de papel.

Usa pydantic-settings para gerenciar configuracoes via:
- Variaveis de ambiente (VEREDAS_*)
- Arquivo .env
- Valores padrao
"""

from decimal import Decimal
from pathlib import Path
from functools import lru_cache
from typing import Optional

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class DetectionThresholds(BaseSettings):
    """Thresholds para deteccao de anomalias."""

    model_config = SettingsConfigDict(env_prefix="VEREDAS_")

    # Spread (% do CDI)
    spread_alto: Decimal = Field(
        default=Decimal("130"),
        description="CDB > X% CDI = severidade HIGH",
    )
    spread_critico: Decimal = Field(
        default=Decimal("150"),
        description="CDB > X% CDI = severidade CRITICAL",
    )

    # Variacao em 7 dias (pontos percentuais)
    salto_brusco: Decimal = Field(
        default=Decimal("10"),
        description="Variacao > Xpp em 7 dias = severidade MEDIUM",
    )
    salto_extremo: Decimal = Field(
        default=Decimal("20"),
        description="Variacao > Xpp em 7 dias = severidade HIGH",
    )

    # Divergencia (desvios padrao)
    divergencia: Decimal = Field(
        default=Decimal("2"),
        description="Taxa > X desvios padrao = severidade MEDIUM",
    )
    divergencia_extrema: Decimal = Field(
        default=Decimal("3"),
        description="Taxa > X desvios padrao = severidade HIGH",
    )

    # IPCA+ (spread sobre IPCA)
    ipca_spread_alto: Decimal = Field(
        default=Decimal("10"),
        description="IPCA + X% = severidade HIGH",
    )
    ipca_spread_critico: Decimal = Field(
        default=Decimal("15"),
        description="IPCA + X% = severidade CRITICAL",
    )


class DatabaseSettings(BaseSettings):
    """Configuracoes do banco de dados."""

    model_config = SettingsConfigDict(env_prefix="VEREDAS_DB_")

    path: Path = Field(
        default=Path.home() / ".veredas" / "veredas.db",
        description="Caminho do banco SQLite",
    )
    echo: bool = Field(
        default=False,
        description="Mostrar queries SQL no console",
    )


class CollectorSettings(BaseSettings):
    """Configuracoes dos coletores de dados."""

    model_config = SettingsConfigDict(env_prefix="VEREDAS_COLLECTOR_")

    # Rate limiting
    request_delay: float = Field(
        default=1.0,
        description="Delay entre requisicoes (segundos)",
    )
    max_retries: int = Field(
        default=3,
        description="Numero maximo de tentativas",
    )
    timeout: int = Field(
        default=30,
        description="Timeout de requisicao (segundos)",
    )

    # Cache
    cache_ttl: int = Field(
        default=3600,
        description="Tempo de vida do cache (segundos)",
    )


class WebSettings(BaseSettings):
    """Configuracoes do servidor web."""

    model_config = SettingsConfigDict(env_prefix="VEREDAS_WEB_")

    host: str = Field(
        default="127.0.0.1",
        description="Host para bind do servidor",
    )
    port: int = Field(
        default=8000,
        description="Porta para bind do servidor",
    )


class AlertSettings(BaseSettings):
    """Configuracoes do sistema de alertas."""

    model_config = SettingsConfigDict(env_prefix="VEREDAS_")

    # Email (SMTP)
    smtp_host: Optional[str] = Field(
        default=None,
        description="Servidor SMTP",
    )
    smtp_port: int = Field(
        default=587,
        description="Porta SMTP",
    )
    smtp_user: Optional[str] = Field(
        default=None,
        description="Usuario SMTP",
    )
    smtp_password: Optional[str] = Field(
        default=None,
        description="Senha SMTP",
    )
    alert_email_to: Optional[str] = Field(
        default=None,
        description="Email destino para alertas",
    )

    # Telegram
    telegram_bot_token: Optional[str] = Field(
        default=None,
        description="Token do bot Telegram",
    )
    telegram_chat_id: Optional[str] = Field(
        default=None,
        description="Chat ID do Telegram",
    )

    # Configuracoes gerais
    alert_min_severity: str = Field(
        default="HIGH",
        description="Severidade minima para alertar (LOW, MEDIUM, HIGH, CRITICAL)",
    )
    alert_cooldown_minutes: int = Field(
        default=60,
        description="Minutos entre alertas da mesma anomalia",
    )


# CNPJs dos maiores bancos brasileiros
# Usado como fallback quando API IF.Data nao retorna lista atualizada
# Fonte: Ranking BCB por ativos totais (atualizado periodicamente)
PRINCIPAIS_BANCOS_CNPJ: list[str] = [
    "00.000.000/0001-91",  # Banco do Brasil
    "60.746.948/0001-12",  # Bradesco
    "60.701.190/0001-04",  # Itau Unibanco
    "00.360.305/0001-04",  # Caixa Economica Federal
    "33.657.248/0001-89",  # Santander Brasil
    "90.400.888/0001-42",  # Banco Safra
    "30.306.294/0001-45",  # Banco BTG Pactual
    "33.042.953/0001-04",  # Citibank
    "62.073.200/0001-21",  # Banco Votorantim (BV)
    "07.237.373/0001-20",  # Banco do Nordeste (BNB)
    "04.902.979/0001-44",  # Banco XP
    "92.874.270/0001-40",  # Banco Pan
    "01.181.521/0001-55",  # Banco Original
    "00.416.968/0001-01",  # Banco Inter
    "18.236.120/0001-58",  # Nubank (Nu Pagamentos)
    "10.573.521/0001-91",  # C6 Bank
    "13.009.717/0001-46",  # Pagseguro / Pagbank
    "02.318.507/0001-81",  # Banco BS2
    "92.702.067/0001-96",  # Banrisul
    "33.172.537/0001-98",  # Banco de Investimentos Credit Suisse
]


class Settings(BaseSettings):
    """Configuracoes principais da aplicacao."""

    model_config = SettingsConfigDict(
        env_prefix="VEREDAS_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Versao
    version: str = "0.1.0"

    # Diretorio de dados
    data_dir: Path = Field(
        default=Path.home() / ".veredas",
        description="Diretorio para armazenar dados",
    )

    # Debug
    debug: bool = Field(
        default=False,
        description="Modo debug",
    )

    # Sub-configuracoes
    detection: DetectionThresholds = Field(default_factory=DetectionThresholds)
    database: DatabaseSettings = Field(default_factory=DatabaseSettings)
    collector: CollectorSettings = Field(default_factory=CollectorSettings)
    web: WebSettings = Field(default_factory=WebSettings)

    # Alertas (campos diretos para facilitar acesso)
    smtp_host: Optional[str] = Field(default=None)
    smtp_port: int = Field(default=587)
    smtp_user: Optional[str] = Field(default=None)
    smtp_password: Optional[str] = Field(default=None)
    alert_email_to: Optional[str] = Field(default=None)
    telegram_bot_token: Optional[str] = Field(default=None)
    telegram_chat_id: Optional[str] = Field(default=None)
    alert_min_severity: str = Field(default="HIGH")
    alert_cooldown_minutes: int = Field(default=60)

    def ensure_data_dir(self) -> Path:
        """Garante que o diretorio de dados existe."""
        self.data_dir.mkdir(parents=True, exist_ok=True)
        return self.data_dir


@lru_cache
def get_settings() -> Settings:
    """
    Retorna instancia singleton das configuracoes.

    Usa lru_cache para garantir que a mesma instancia
    e retornada em todas as chamadas.

    Returns:
        Settings: Configuracoes da aplicacao.
    """
    return Settings()


# Atalhos para acesso rapido
settings = get_settings()
