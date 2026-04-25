"""
Coletores de prateleiras de corretoras — Fase 4.2.

Cada módulo implementa um coletor para uma corretora específica,
herdando de WebCollectorBase (collectors/scraper_base.py).

Uso rápido:
    from veredas.collectors.scrapers import get_collector, SCRAPERS

    collector = get_collector("xp")      # XPCollector
    collector = get_collector("all")     # None (use loop)
    for nome in SCRAPERS:
        col = get_collector(nome)
"""

from veredas.collectors.scrapers.btg import BTGCollector
from veredas.collectors.scrapers.inter import InterCollector
from veredas.collectors.scrapers.normalize import CDBOferta
from veredas.collectors.scrapers.rico import RicoCollector
from veredas.collectors.scrapers.xp import XPCollector

# Registro de coletores disponíveis: nome → classe
SCRAPERS: dict[str, type] = {
    "xp": XPCollector,
    "btg": BTGCollector,
    "inter": InterCollector,
    "rico": RicoCollector,
}


def get_collector(fonte: str):
    """
    Retorna uma instância do coletor para a fonte informada.

    Args:
        fonte: "xp", "btg", "inter" ou "rico".

    Returns:
        Instância do coletor, ou None se a fonte for desconhecida.
    """
    cls = SCRAPERS.get(fonte.lower())
    return cls() if cls else None


__all__ = [
    "SCRAPERS",
    "BTGCollector",
    "CDBOferta",
    "InterCollector",
    "RicoCollector",
    "XPCollector",
    "get_collector",
]
