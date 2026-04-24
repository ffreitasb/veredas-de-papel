"""
Parser do arquivo RF{DDMMYY}.txt — Renda Fixa Privada B3.

Formato confirmado (pregão 23/04/2026):
    Linha 1:  YYYYMMDD  (data do pregão)
    Demais:   TICKER;VENCIMENTO;DIAS_CORRIDOS;DIAS_UTEIS;PU_MERCADO;PU_PAR;TAXA_MERCADO;FATOR_ACUMULADO
    Ex:       EGIE-DEB71;20250715;557;811;1348.48;1311.18;1.606608;311.1753

O campo TICKER segue o padrão EMIS-TIPOnn onde:
    - EMIS   = código do emissor (ex: EGIE, PETR, VALE, ITUB)
    - TIPO   = tipo do instrumento (DEB=debênture, ETF=ETF de RF, CRI, CRA...)
    - nn     = número da série
"""

import logging
import re
from dataclasses import dataclass
from datetime import date
from decimal import Decimal, InvalidOperation

logger = logging.getLogger(__name__)

# Tipos de instrumento reconhecidos no ticker
_TIPO_RE = re.compile(r"-([A-Z]+)\d+$")

# Mapeamento de prefixo de emissor → CNPJ (complementa catalog.py para emissores
# que aparecem no boletim B3 e são IFs relevantes para o projeto)
# Chave: prefixo do ticker B3 (até 4 letras). Valor: CNPJ formatado.
TICKER_PREFIX_TO_CNPJ: dict[str, str] = {
    "ITUB": "60.872.504/0001-23",  # Itaú Unibanco
    "BBDC": "60.746.948/0001-12",  # Bradesco
    "SANB": "90.400.888/0001-42",  # Santander Brasil
    "BTGP": "30.306.294/0001-45",  # BTG Pactual
    "BVMF": "09.346.601/0001-25",  # B3 S.A.
    "BMST": "33.156.031/0001-48",  # Banco Master
    "BSLI": "00.556.603/0001-56",  # Banco Bari
    "BPAN": "59.285.411/0001-13",  # Banco Pan
    "PINE": "62.144.175/0001-20",  # Banco Pine
    "DAYC": "62.232.889/0001-90",  # Daycoval
    "BRSR": "92.702.067/0001-96",  # Banrisul
    "ABCB": "28.195.667/0001-06",  # ABC Brasil
    "MODL": "45.233.749/0001-40",  # Modal / Banco XP
    "BIDI": "00.416.968/0001-01",  # Banco Inter
    "CASH": "18.236.120/0001-58",  # Nu / Nubank
}


@dataclass
class B3RendaFixaRecord:
    """Um registro do boletim de Renda Fixa Privada da B3."""

    data_pregao: date
    codigo: str  # ticker completo, ex: EGIE-DEB71
    emissor_codigo: str  # prefixo, ex: EGIE
    tipo: str  # DEB, ETF, CRI, CRA, OUTRO
    vencimento: date
    dias_corridos: int
    dias_uteis: int
    pu_mercado: Decimal
    pu_par: Decimal
    taxa_mercado: Decimal  # % a.a.
    fator_acumulado: Decimal

    @property
    def cnpj_emissor(self) -> str | None:
        """CNPJ do emissor se mapeado em TICKER_PREFIX_TO_CNPJ, senão None."""
        return TICKER_PREFIX_TO_CNPJ.get(self.emissor_codigo)

    @property
    def is_financeira(self) -> bool:
        """True se o emissor for uma instituição financeira conhecida."""
        return self.emissor_codigo in TICKER_PREFIX_TO_CNPJ


class B3RendaFixaParser:
    """Converte o conteúdo do TXT do boletim em lista de B3RendaFixaRecord."""

    def parse(self, conteudo: str) -> list[B3RendaFixaRecord]:
        """
        Lê o conteúdo do arquivo RF*.txt e retorna lista de registros.

        A primeira linha é a data do pregão (YYYYMMDD).
        Linhas seguintes são campos separados por ";".
        Linhas malformadas são ignoradas com aviso de log.
        """
        linhas = conteudo.strip().splitlines()
        if not linhas:
            return []

        data_pregao = self._parse_data_pregao(linhas[0].strip())
        if data_pregao is None:
            logger.warning("B3Parser: primeira linha inválida — '%s'", linhas[0][:20])
            return []

        records: list[B3RendaFixaRecord] = []
        for i, linha in enumerate(linhas[1:], start=2):
            linha = linha.strip()
            if not linha:
                continue
            record = self._parse_linha(linha, data_pregao, i)
            if record is not None:
                records.append(record)

        logger.debug("B3Parser: %d registros lidos do pregão %s", len(records), data_pregao)
        return records

    # ------------------------------------------------------------------
    # helpers privados
    # ------------------------------------------------------------------

    @staticmethod
    def _parse_data_pregao(s: str) -> date | None:
        try:
            return date(int(s[:4]), int(s[4:6]), int(s[6:8]))
        except (ValueError, IndexError):
            return None

    @staticmethod
    def _parse_date(s: str) -> date | None:
        try:
            return date(int(s[:4]), int(s[4:6]), int(s[6:8]))
        except (ValueError, IndexError):
            return None

    @staticmethod
    def _parse_decimal(s: str) -> Decimal | None:
        try:
            return Decimal(s.replace(",", "."))
        except InvalidOperation:
            return None

    @staticmethod
    def _parse_int(s: str) -> int | None:
        try:
            return int(s)
        except ValueError:
            return None

    @staticmethod
    def _tipo_from_ticker(ticker: str) -> str:
        m = _TIPO_RE.search(ticker)
        if not m:
            return "OUTRO"
        t = m.group(1)
        if t == "DEB":
            return "DEB"
        if "ETF" in t:
            return "ETF"
        if t in ("CRI", "CRA", "LCI", "LCA", "CDB", "CCB"):
            return t
        return "OUTRO"

    def _parse_linha(self, linha: str, data_pregao: date, num: int) -> "B3RendaFixaRecord | None":
        partes = linha.split(";")
        if len(partes) < 8:
            logger.debug("B3Parser: linha %d ignorada — campos insuficientes", num)
            return None

        codigo = partes[0].strip()
        vencimento = self._parse_date(partes[1].strip())
        dias_corridos = self._parse_int(partes[2].strip())
        dias_uteis = self._parse_int(partes[3].strip())
        pu_mercado = self._parse_decimal(partes[4].strip())
        pu_par = self._parse_decimal(partes[5].strip())
        taxa_mercado = self._parse_decimal(partes[6].strip())
        fator = self._parse_decimal(partes[7].strip())

        if any(
            v is None
            for v in [
                vencimento,
                dias_corridos,
                dias_uteis,
                pu_mercado,
                pu_par,
                taxa_mercado,
                fator,
            ]
        ):
            logger.debug("B3Parser: linha %d ignorada — valores inválidos (%s)", num, codigo)
            return None

        emissor_codigo = codigo.split("-")[0] if "-" in codigo else codigo[:4]

        return B3RendaFixaRecord(
            data_pregao=data_pregao,
            codigo=codigo,
            emissor_codigo=emissor_codigo,
            tipo=self._tipo_from_ticker(codigo),
            vencimento=vencimento,
            dias_corridos=dias_corridos,
            dias_uteis=dias_uteis,
            pu_mercado=pu_mercado,
            pu_par=pu_par,
            taxa_mercado=taxa_mercado,
            fator_acumulado=fator,
        )
