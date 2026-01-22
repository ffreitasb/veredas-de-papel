"""
veredas de papel - Monitor de taxas de CDB e detecção de anomalias.

"Nem todo atalho leva ao destino. Monitore o risco."

Uma ferramenta FOSS que monitora o mercado de renda fixa brasileiro
em busca de anomalias, iluminando os atalhos perigosos criados por
emissores de crédito em dificuldade.
"""

from datetime import timedelta, timezone

__version__ = "0.1.0"
__author__ = "ffreitasb"
__license__ = "MIT"

# Fuso horário de Brasília (UTC-3)
# Usado em todo o projeto para consistência com horários do mercado brasileiro
TZ_BRASIL = timezone(timedelta(hours=-3))

from veredas.storage import DatabaseManager

__all__ = [
    "__version__",
    "__author__",
    "__license__",
    "TZ_BRASIL",
    "DatabaseManager",
]
