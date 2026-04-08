"""
Scrapers de corretoras brasileiras.

Cada scraper coleta taxas de CDB da respectiva plataforma.
"""

from veredas.collectors.scrapers.brokers.xp import XPScraper
from veredas.collectors.scrapers.brokers.btg import BTGScraper
from veredas.collectors.scrapers.brokers.rico import RicoScraper
from veredas.collectors.scrapers.brokers.nubank import NubankScraper
from veredas.collectors.scrapers.brokers.inter import InterScraper

__all__ = [
    "XPScraper",
    "BTGScraper",
    "RicoScraper",
    "NubankScraper",
    "InterScraper",
    "SCRAPERS",
    "SCRAPERS_REGISTRY",
    "get_scraper",
    "get_all_scrapers",
]

# Registry de scrapers disponíveis
SCRAPERS = {
    "xp": XPScraper,
    "btg": BTGScraper,
    "rico": RicoScraper,
    "nubank": NubankScraper,
    "inter": InterScraper,
}

# Alias para compatibilidade
SCRAPERS_REGISTRY = SCRAPERS


from veredas.collectors.scrapers.base import BaseScraper


# M12 FIX: Adicionados type hints nas funções
def get_scraper(name: str) -> BaseScraper:
    """
    Retorna instância do scraper pelo nome.

    Args:
        name: Nome da corretora (xp, btg, rico, nubank, inter)

    Returns:
        Instância do scraper

    Raises:
        ValueError: Se scraper não encontrado
    """
    name_lower = name.lower()
    if name_lower not in SCRAPERS:
        available = ", ".join(SCRAPERS.keys())
        raise ValueError(f"Scraper '{name}' não encontrado. Disponíveis: {available}")
    return SCRAPERS[name_lower]()


def get_all_scrapers() -> list[BaseScraper]:
    """Retorna instâncias de todos os scrapers."""
    return [scraper_class() for scraper_class in SCRAPERS.values()]
