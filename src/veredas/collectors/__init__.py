"""
Módulo de coletores de dados do veredas de papel.

Exporta coletores para diferentes fontes de dados.
"""

from veredas.collectors.b3 import B3BoletimCollector
from veredas.collectors.base import BaseCollector, CollectionResult
from veredas.collectors.bcb import (
    BCBCollector,
    DadosBCB,
    TaxaReferenciaBCB,
    get_cdi_atual,
    get_ipca_atual,
    get_selic_atual,
)
from veredas.collectors.scraper_base import WebCollectorBase

__all__ = [
    # Base
    "BaseCollector",
    "CollectionResult",
    "WebCollectorBase",
    # BCB
    "BCBCollector",
    "DadosBCB",
    "TaxaReferenciaBCB",
    "get_selic_atual",
    "get_cdi_atual",
    "get_ipca_atual",
    # B3
    "B3BoletimCollector",
]
