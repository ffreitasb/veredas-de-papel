"""
Scrapers para coleta de taxas de CDB de corretoras.

Este módulo implementa a infraestrutura de web scraping para
coletar taxas de CDB de múltiplas plataformas de investimento.
"""

from veredas.collectors.scrapers.base import (
    BaseScraper,
    ScraperResult,
    TaxaColetada,
)
from veredas.collectors.scrapers.normalizer import (
    TaxaNormalizer,
    NormalizedTaxa,
    normalize_cnpj,
    normalize_nome,
    find_cnpj_by_name,
    merge_results,
)
from veredas.collectors.scrapers.anti_bot import (
    BrowserFingerprint,
    CaptchaSolver,
    ProxyConfig,
    ProxyRotator,
    RateLimiter,
    SessionManager,
)
from veredas.collectors.scrapers.brokers import SCRAPERS_REGISTRY

# Aliases para compatibilidade
DataNormalizer = TaxaNormalizer
TaxaNormalizada = NormalizedTaxa

__all__ = [
    # Base
    "BaseScraper",
    "ScraperResult",
    "TaxaColetada",
    # Normalização
    "TaxaNormalizer",
    "NormalizedTaxa",
    "normalize_cnpj",
    "normalize_nome",
    "find_cnpj_by_name",
    "merge_results",
    # Aliases
    "DataNormalizer",
    "TaxaNormalizada",
    # Anti-bot
    "BrowserFingerprint",
    "CaptchaSolver",
    "ProxyConfig",
    "ProxyRotator",
    "RateLimiter",
    "SessionManager",
    # Registry
    "SCRAPERS_REGISTRY",
]
