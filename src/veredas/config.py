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
