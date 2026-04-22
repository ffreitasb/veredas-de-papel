"""
Dependencias compartilhadas para rotas FastAPI.

Este modulo centraliza dependencias comuns como sessao de banco de dados,
evitando duplicacao de codigo entre rotas.
"""

from collections.abc import Generator
from functools import lru_cache

from sqlalchemy.orm import Session

from veredas.config import get_settings
from veredas.storage.database import DatabaseManager


@lru_cache(maxsize=1)
def get_db_manager() -> DatabaseManager:
    """
    Singleton para DatabaseManager.

    Reutiliza a mesma engine SQLAlchemy entre requests,
    evitando leak de conexoes e reducao de uso de memoria.

    Returns:
        DatabaseManager: Instancia unica do gerenciador.
    """
    settings = get_settings()
    return DatabaseManager(settings.database.path)


def get_db() -> Generator[Session, None, None]:
    """
    Dependency para obter sessao do banco de dados.

    Uso:
        @router.get("/")
        async def my_route(session=Depends(get_db)):
            ...

    Yields:
        Session: Sessao SQLAlchemy gerenciada.
    """
    db_manager = get_db_manager()  # Reutiliza singleton

    with db_manager.session_scope() as session:
        yield session
