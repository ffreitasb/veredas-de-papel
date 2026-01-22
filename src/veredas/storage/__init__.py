"""
Módulo de persistência do veredas de papel.

Exporta modelos, repositórios e gerenciador de banco de dados.
"""

from veredas.storage.database import DatabaseManager, get_session, init_db
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
    # Database
    "DatabaseManager",
    "get_session",
    "init_db",
    "Base",
    # Models
    "InstituicaoFinanceira",
    "TaxaCDB",
    "Anomalia",
    "EventoRegulatorio",
    "TaxaReferencia",
    # Enums
    "Segmento",
    "Indexador",
    "TipoAnomalia",
    "Severidade",
    "TipoEvento",
    # Repositories
    "InstituicaoRepository",
    "TaxaCDBRepository",
    "AnomaliaRepository",
    "TaxaReferenciaRepository",
    "EventoRepository",
]
