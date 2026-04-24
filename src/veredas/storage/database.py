"""
Configuração do banco de dados.

Gerencia a conexão com o banco SQLite e sessões.
"""

import contextlib
from collections.abc import Generator
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from veredas.storage.models import Base

# Diretório padrão para dados
DATA_DIR = Path.home() / ".veredas"
DATA_DIR.mkdir(exist_ok=True)

# Caminho padrão do banco de dados
DEFAULT_DB_PATH = DATA_DIR / "veredas.db"

_engine_cache: dict[str, object] = {}


def get_engine(db_path: Path | str | None = None):
    """
    Cria ou reutiliza engine do SQLAlchemy para o caminho dado.

    Args:
        db_path: Caminho para o banco de dados SQLite.
                 Se None, usa o caminho padrão ~/.veredas/veredas.db
    """
    if db_path is None:
        db_path = DEFAULT_DB_PATH

    key = str(db_path)
    if key not in _engine_cache:
        db_url = f"sqlite:///{db_path}"
        _engine_cache[key] = create_engine(
            db_url,
            echo=False,
            connect_args={"check_same_thread": False},
            pool_pre_ping=True,
        )
    return _engine_cache[key]


def init_db(db_path: Path | str | None = None) -> None:
    """
    Inicializa o banco de dados criando todas as tabelas.

    Args:
        db_path: Caminho para o banco de dados SQLite.
    """
    engine = get_engine(db_path)
    Base.metadata.create_all(engine)


def get_session(db_path: Path | str | None = None) -> Generator[Session, None, None]:
    """
    Cria uma sessão do banco de dados.

    Args:
        db_path: Caminho para o banco de dados SQLite.

    Yields:
        Session: Sessão do SQLAlchemy.
    """
    engine = get_engine(db_path)
    session_factory = sessionmaker(bind=engine)

    session = session_factory()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


class DatabaseManager:
    """Gerenciador de conexões com o banco de dados."""

    def __init__(self, db_path: Path | str | None = None):
        """
        Inicializa o gerenciador.

        Args:
            db_path: Caminho para o banco de dados SQLite.
        """
        self.db_path = db_path or DEFAULT_DB_PATH
        self.engine = get_engine(self.db_path)
        self._session_factory = sessionmaker(bind=self.engine)

    def init_db(self) -> None:
        """Cria todas as tabelas no banco de dados."""
        Base.metadata.create_all(self.engine)

    def get_session(self) -> Session:
        """Retorna uma nova sessão."""
        return self._session_factory()

    @contextlib.contextmanager
    def session_scope(self) -> Generator[Session, None, None]:
        """
        Context manager para sessões.

        Exemplo:
            with db.session_scope() as session:
                session.add(obj)
        """
        session = self.get_session()
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()
