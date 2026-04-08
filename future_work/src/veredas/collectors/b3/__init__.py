"""
Integração com B3 para dados do mercado secundário.

Coleta preços de negociação de títulos de renda fixa no mercado secundário,
permitindo identificar descolamentos entre preço de emissão e preço de mercado.
"""

from veredas.collectors.b3.api import B3MarketDataCollector
from veredas.collectors.b3.parser import B3DataParser
from veredas.collectors.b3.models import (
    TipoTitulo,
    StatusNegociacao,
    TituloRendaFixa,
    NegociacaoB3,
    PrecoSecundario,
    ResumoMercadoSecundario,
    AlertaPrecoSecundario,
)

__all__ = [
    "B3MarketDataCollector",
    "B3DataParser",
    "TipoTitulo",
    "StatusNegociacao",
    "TituloRendaFixa",
    "NegociacaoB3",
    "PrecoSecundario",
    "ResumoMercadoSecundario",
    "AlertaPrecoSecundario",
]
