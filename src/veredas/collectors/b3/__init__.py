"""
Coletor do Boletim Diário de Renda Fixa Privada da B3.

Baixa e processa o arquivo RF{DDMMYY}.ex_ publicado diariamente (~19:53 BRT)
contendo debêntures negociadas no mercado secundário B3/CETIP.

Uso:
    from veredas.collectors.b3 import B3BoletimCollector

    collector = B3BoletimCollector()
    async with collector:
        result = await collector.collect()
"""

from veredas.collectors.b3.collector import B3BoletimCollector

__all__ = ["B3BoletimCollector"]
