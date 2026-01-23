"""
Dependencias compartilhadas para rotas FastAPI.

Este modulo centraliza dependencias comuns como sessao de banco de dados,
evitando duplicacao de codigo entre rotas.
"""

from typing import Generator

from sqlalchemy.orm import Session

from veredas.config import get_settings
from veredas.storage.database import DatabaseManager


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
    settings = get_settings()
    db_manager = DatabaseManager(settings.database.path)

    with db_manager.session_scope() as session:
        yield session
