"""
Interface base para detectores de anomalias.

Define o contrato que todos os detectores devem implementar.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from typing import Any, Optional

from veredas.storage.models import Severidade, TipoAnomalia


@dataclass
class AnomaliaDetectada:
    """Representa uma anomalia detectada por um detector."""

    tipo: TipoAnomalia
    severidade: Severidade
    valor_detectado: Decimal
    descricao: str

    # Contexto
    if_id: Optional[int] = None
    if_nome: Optional[str] = None
    taxa_id: Optional[int] = None

    # Valores de referência
    valor_esperado: Optional[Decimal] = None
    desvio: Optional[Decimal] = None
    threshold: Optional[Decimal] = None

    # Metadados
    detector: str = ""
    detectado_em: datetime = field(default_factory=datetime.now)
    detalhes: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        if not self.detector:
            self.detector = "unknown"

    @property
    def is_critical(self) -> bool:
        """Verifica se a anomalia é crítica."""
        return self.severidade == Severidade.CRITICAL

    @property
    def is_high_or_above(self) -> bool:
        """Verifica se a anomalia é HIGH ou CRITICAL."""
        return self.severidade in (Severidade.HIGH, Severidade.CRITICAL)


@dataclass
class DetectionResult:
    """Resultado de uma execução de detecção."""

    detector_name: str
    anomalias: list[AnomaliaDetectada]
    executed_at: datetime = field(default_factory=datetime.now)
    execution_time_ms: float = 0
    error: Optional[str] = None

    @property
    def success(self) -> bool:
        """Verifica se a detecção foi bem sucedida."""
        return self.error is None

    @property
    def has_anomalies(self) -> bool:
        """Verifica se foram encontradas anomalias."""
        return len(self.anomalias) > 0

    @property
    def critical_count(self) -> int:
        """Conta anomalias críticas."""
        return sum(1 for a in self.anomalias if a.is_critical)

    @property
    def high_count(self) -> int:
        """Conta anomalias HIGH ou CRITICAL."""
        return sum(1 for a in self.anomalias if a.is_high_or_above)


class BaseDetector(ABC):
    """
    Classe base abstrata para detectores de anomalias.

    Todos os detectores devem herdar desta classe e implementar
    os métodos abstratos.
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Nome identificador do detector."""
        ...

    @property
    @abstractmethod
    def description(self) -> str:
        """Descrição do que o detector faz."""
        ...

    @abstractmethod
    def detect(self, data: Any) -> DetectionResult:
        """
        Executa a detecção de anomalias.

        Args:
            data: Dados a serem analisados.

        Returns:
            DetectionResult com as anomalias encontradas.
        """
        ...

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__} name={self.name}>"
