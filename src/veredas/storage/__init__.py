"""
Módulo de persistência do veredas de papel.

Exporta modelos, repositórios e gerenciador de banco de dados.
"""

from veredas.storage.database import DatabaseManager, init_db
from veredas.storage.models import (
    Anomalia,
    Base,
    EventoRegulatorio,
    Indexador,
    InstituicaoFinanceira,
    Segmento,
    Severidade,
    TaxaCDB,
    TaxaReferencia,
    TipoAnomalia,
    TipoEvento,
)
from veredas.storage.repository import (
    AnomaliaRepository,
    EventoRepository,
    InstituicaoRepository,
    TaxaCDBRepository,
    TaxaReferenciaRepository,
)

__all__ = [
    "Anomalia",
    "AnomaliaRepository",
    "Base",
    # Database
    "DatabaseManager",
    "EventoRegulatorio",
    "EventoRepository",
    "Indexador",
    # Models
    "InstituicaoFinanceira",
    # Repositories
    "InstituicaoRepository",
    # Enums
    "Segmento",
    "Severidade",
    "TaxaCDB",
    "TaxaCDBRepository",
    "TaxaReferencia",
    "TaxaReferenciaRepository",
    "TipoAnomalia",
    "TipoEvento",
    "init_db",
]
