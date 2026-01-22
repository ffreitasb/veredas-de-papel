"""
Configuracao do ambiente Alembic para migrations.
"""

import os
import sys
from logging.config import fileConfig
from pathlib import Path

from sqlalchemy import engine_from_config, pool

from alembic import context

# Adicionar src ao path para importar modelos
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from veredas.storage.models import Base  # noqa: E402

# Alembic Config object
config = context.config

# Interpretar arquivo de configuracao para logging
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Metadata dos modelos para autogenerate
target_metadata = Base.metadata

# Permitir sobrescrever URL via variavel de ambiente
def get_url():
    """Obtem URL do banco de dados."""
    db_path = os.environ.get("VEREDAS_DB_PATH")
    if db_path:
        return f"sqlite:///{db_path}"
    return config.get_main_option("sqlalchemy.url")


def run_migrations_offline() -> None:
    """
    Executar migrations em modo 'offline'.

    Configura o contexto apenas com URL, sem criar Engine.
    Util para gerar scripts SQL sem conexao com o banco.
    """
    url = get_url()
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        render_as_batch=True,  # Necessario para SQLite
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """
    Executar migrations em modo 'online'.

    Cria Engine e associa conexao com o contexto.
    """
    # Sobrescrever URL se variavel de ambiente estiver definida
    configuration = config.get_section(config.config_ini_section, {})
    configuration["sqlalchemy.url"] = get_url()

    connectable = engine_from_config(
        configuration,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            render_as_batch=True,  # Necessario para SQLite (ALTER TABLE)
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
