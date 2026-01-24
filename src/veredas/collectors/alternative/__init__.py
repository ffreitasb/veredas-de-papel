"""
Coletores de dados alternativos.

Fontes de dados não-financeiros que podem indicar
problemas em instituições financeiras:
- Reclame Aqui: Reclamações de clientes
- Processos BC: Processos administrativos do Banco Central
- Notícias: Análise de sentimento em notícias
"""

from veredas.collectors.alternative.reclame_aqui import (
    ReclameAquiCollector,
    Reclamacao,
    ReputacaoRA,
)
from veredas.collectors.alternative.bacen_processos import (
    BacenProcessosCollector,
    ProcessoBC,
    HistoricoProcessosIF,
    TipoProcesso,
    StatusProcesso,
)

# Aliases para compatibilidade com os testes
ReputacaoEmpresa = ReputacaoRA
ReclamacaoInfo = Reclamacao

__all__ = [
    # Reclame Aqui
    "ReclameAquiCollector",
    "Reclamacao",
    "ReputacaoRA",
    # Aliases
    "ReputacaoEmpresa",
    "ReclamacaoInfo",
    # Banco Central
    "BacenProcessosCollector",
    "ProcessoBC",
    "HistoricoProcessosIF",
    "TipoProcesso",
    "StatusProcesso",
]
