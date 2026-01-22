"""
Interface base para coletores de dados.

Define o contrato que todos os coletores devem implementar.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Generic, TypeVar

T = TypeVar("T")


@dataclass
class CollectionResult(Generic[T]):
    """Resultado de uma coleta de dados."""

    success: bool
    data: T | None
    source: str
    collected_at: datetime
    error: str | None = None
    raw_response: Any | None = None

    @classmethod
    def ok(cls, data: T, source: str, raw_response: Any = None) -> "CollectionResult[T]":
        """Cria um resultado de sucesso."""
        return cls(
            success=True,
            data=data,
            source=source,
            collected_at=datetime.now(),
            error=None,
            raw_response=raw_response,
        )

    @classmethod
    def fail(cls, error: str, source: str) -> "CollectionResult[T]":
        """Cria um resultado de falha."""
        return cls(
            success=False,
            data=None,
            source=source,
            collected_at=datetime.now(),
            error=error,
            raw_response=None,
        )


class BaseCollector(ABC):
    """
    Classe base abstrata para coletores de dados.

    Todos os coletores devem herdar desta classe e implementar
    os métodos abstratos.
    """

    @property
    @abstractmethod
    def source_name(self) -> str:
        """Nome identificador da fonte de dados."""
        ...

    @abstractmethod
    async def collect(self) -> CollectionResult:
        """
        Executa a coleta de dados.

        Returns:
            CollectionResult com os dados coletados ou erro.
        """
        ...

    @abstractmethod
    async def health_check(self) -> bool:
        """
        Verifica se a fonte de dados está acessível.

        Returns:
            True se a fonte está operacional.
        """
        ...

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__} source={self.source_name}>"
