"""
Módulo de coletores de dados do veredas de papel.

Exporta coletores para diferentes fontes de dados.
"""

from veredas.collectors.base import BaseCollector, CollectionResult
from veredas.collectors.bcb import (
    BCBCollector,
    DadosBCB,
    TaxaReferenciaBCB,
    get_cdi_atual,
    get_ipca_atual,
    get_selic_atual,
)

__all__ = [
    # Base
    "BaseCollector",
    "CollectionResult",
    # BCB
    "BCBCollector",
    "DadosBCB",
    "TaxaReferenciaBCB",
    "get_selic_atual",
    "get_cdi_atual",
    "get_ipca_atual",
]
