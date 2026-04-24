"""
Coletor do Boletim Diário de Renda Fixa Privada da B3.

Baixa o arquivo RF{DDMMYY}.ex_ via HTTP direto (sem Playwright), extrai
o TXT do ZIP aninhado e converte os registros em B3RendaFixaRecord.

Uso:
    from datetime import date
    from veredas.collectors.b3 import B3BoletimCollector

    async with B3BoletimCollector() as c:
        result = await c.collect()                      # pregão do dia
        result = await c.collect(date(2026, 4, 23))     # pregão específico
"""

import logging
from datetime import date, timedelta

from veredas.collectors.b3.downloader import build_url, extract_txt
from veredas.collectors.b3.parser import B3RendaFixaParser, B3RendaFixaRecord
from veredas.collectors.base import CollectionResult
from veredas.collectors.scraper_base import WebCollectorBase

logger = logging.getLogger(__name__)

SOURCE = "b3"
BASE_URL = "https://www.b3.com.br"


class B3BoletimCollector(WebCollectorBase):
    """
    Coletor do arquivo de Renda Fixa Privada do Boletim Diário B3.

    Usa httpx direto (sem Playwright) pois a URL é estática e não depende
    de JavaScript após o reverse-engineering do padrão.

    Dados retornados: lista de B3RendaFixaRecord contendo debêntures
    negociadas no mercado secundário, úteis como proxy de stress de crédito
    dos emissores (IFs financeiras identificadas via TICKER_PREFIX_TO_CNPJ).
    """

    SOURCE = SOURCE
    BASE_URL = BASE_URL

    def __init__(self) -> None:
        super().__init__()
        self._parser = B3RendaFixaParser()

    async def collect(
        self,
        pregao: date | None = None,
    ) -> CollectionResult[list[B3RendaFixaRecord]]:
        """
        Baixa e processa o boletim de um pregão.

        Args:
            pregao: Data do pregão. Se None, usa o dia atual.
                    Em fins de semana e feriados o arquivo estará vazio
                    — retorna lista vazia sem erro.

        Returns:
            CollectionResult com lista de B3RendaFixaRecord (pode ser vazia).
        """
        alvo = pregao or date.today()
        url = build_url(alvo)

        logger.info("B3Boletim: baixando pregão %s — %s", alvo.isoformat(), url)

        try:
            response = await self._get(url)
        except Exception as exc:
            return CollectionResult.fail(
                error=f"Erro ao baixar boletim B3 ({alvo}): {exc}",
                source=SOURCE,
            )

        conteudo = extract_txt(response.content)

        if not conteudo:
            # Pregão fechado ou arquivo vazio — não é erro
            logger.info("B3Boletim: pregão %s sem dados (feriado/fim de semana?)", alvo.isoformat())
            return CollectionResult.ok([], SOURCE)

        records = self._parser.parse(conteudo)
        logger.info(
            "B3Boletim: pregão %s — %d registros (%d de IFs financeiras)",
            alvo.isoformat(),
            len(records),
            sum(1 for r in records if r.is_financeira),
        )
        return CollectionResult.ok(records, SOURCE, raw_response=conteudo)

    async def collect_range(
        self,
        inicio: date,
        fim: date | None = None,
    ) -> list[B3RendaFixaRecord]:
        """
        Coleta múltiplos pregões em sequência (uso para backfill limitado).

        AVISO: O endpoint mantém apenas ~2 pregões disponíveis.
        Pregões mais antigos retornam lista vazia sem erro.
        """
        fim = fim or date.today()
        todos: list[B3RendaFixaRecord] = []
        atual = inicio
        while atual <= fim:
            result = await self.collect(atual)
            if result.success and result.data:
                todos.extend(result.data)
            atual += timedelta(days=1)
        return todos

    async def health_check(self) -> bool:
        """Verifica se o endpoint da B3 responde."""
        import httpx

        try:
            async with httpx.AsyncClient(timeout=10.0, follow_redirects=True) as client:
                resp = await client.get(BASE_URL)
                return resp.status_code < 500
        except Exception:
            return False
