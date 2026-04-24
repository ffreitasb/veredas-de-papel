"""
Normalização de ofertas de CDB coletadas das corretoras.

Fornece o dataclass CDBOferta (estrutura intermediária entre scraper e banco)
e funções puras de parsing de texto financeiro brasileiro.

Todas as funções são puras e não lançam exceções — retornam None / Decimal("0")
em caso de falha de parsing para que o scraper possa continuar.
"""

import re
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation

from veredas.storage.models import Indexador


@dataclass
class CDBOferta:
    """
    Oferta de CDB/renda fixa capturada de uma corretora.

    Estrutura intermediária entre scraper e repositório.
    O caller (CLI ou tarefa agendada) é responsável por resolver
    o if_id via InstituicaoRepository.upsert(cnpj, ...) antes de
    criar o TaxaCDB no banco.
    """

    emissor_nome: str
    emissor_cnpj: str  # "XX.XXX.XXX/XXXX-XX" ou "" se não disponível na página
    indexador: Indexador
    percentual: Decimal  # % do CDI (120.0) ou taxa pré (12.5) — ver docstring abaixo
    taxa_adicional: Decimal | None  # spread para IPCA+X% ou CDI+X%
    prazo_dias: int
    valor_minimo: Decimal | None
    liquidez_diaria: bool
    fonte: str  # "xp", "btg", "inter", "rico"
    url_fonte: str
    raw: dict = field(default_factory=dict)

    # percentual semântica por indexador:
    #   CDI puro:    percentual = % do CDI (ex: 120.0 = 120% CDI), taxa_adicional = None
    #   CDI+spread:  percentual = 100.0, taxa_adicional = spread (ex: CDI + 2% → ta=2.0)
    #   IPCA+:       percentual = 0.0,   taxa_adicional = spread (ex: IPCA + 6.5% → ta=6.5)
    #   PREFIXADO:   percentual = taxa a.a. (ex: 12.5), taxa_adicional = None
    #   SELIC puro:  percentual = % da Selic (ex: 100.0), taxa_adicional = None
    #   SELIC+:      percentual = 100.0, taxa_adicional = spread


# ---------------------------------------------------------------------------
# Parsing helpers (internos)
# ---------------------------------------------------------------------------


def _extract_first_number(text: str) -> Decimal | None:
    """Extrai o primeiro número decimal encontrado no texto."""
    m = re.search(r"(\d+)(?:[,.](\d{1,4}))?", text)
    if not m:
        return None
    inteiro, dec = m.group(1), m.group(2) or ""
    try:
        return Decimal(f"{inteiro}.{dec}") if dec else Decimal(inteiro)
    except InvalidOperation:
        return None


def _extract_after_plus(text: str) -> Decimal | None:
    """Extrai o número imediatamente após '+' (spread)."""
    m = re.search(r"\+\s*(\d+)(?:[,.](\d{1,4}))?", text)
    if not m:
        return None
    inteiro, dec = m.group(1), m.group(2) or ""
    try:
        return Decimal(f"{inteiro}.{dec}") if dec else Decimal(inteiro)
    except InvalidOperation:
        return None


# ---------------------------------------------------------------------------
# API pública
# ---------------------------------------------------------------------------


def parse_taxa(text: str) -> tuple[Indexador, Decimal, Decimal | None]:
    """
    Extrai (indexador, percentual, taxa_adicional) de um texto de taxa.

    Exemplos:
        "120% CDI"           → (CDI,       Decimal("120"),  None)
        "CDI + 2,5%"         → (CDI,       Decimal("100"),  Decimal("2.5"))
        "IPCA + 6,50% a.a."  → (IPCA,      Decimal("0"),    Decimal("6.5"))
        "12,5% a.a."         → (PREFIXADO, Decimal("12.5"), None)
        "100% da Selic"      → (SELIC,     Decimal("100"),  None)
        "Selic + 0,5%"       → (SELIC,     Decimal("100"),  Decimal("0.5"))
    """
    t = text.strip().upper()
    has_plus = "+" in t

    if "IPCA" in t:
        spread = _extract_after_plus(t) if has_plus else None
        return Indexador.IPCA, Decimal("0"), spread

    if "SELIC" in t:
        if has_plus:
            spread = _extract_after_plus(t)
            return Indexador.SELIC, Decimal("100"), spread
        num = _extract_first_number(t)
        return Indexador.SELIC, num or Decimal("100"), None

    if "CDI" in t:
        if has_plus:
            spread = _extract_after_plus(t)
            return Indexador.CDI, Decimal("100"), spread
        num = _extract_first_number(t)
        return Indexador.CDI, num or Decimal("0"), None

    # PREFIXADO (nenhuma palavra-chave encontrada)
    num = _extract_first_number(t)
    return Indexador.PREFIXADO, num or Decimal("0"), None


_DIAS_POR_MES = 30
_DIAS_POR_ANO = 360


def parse_prazo_dias(text: str) -> int:
    """
    Converte texto de prazo em número de dias úteis/corridos.

    "360 dias" → 360 | "1 ano" → 360 | "6 meses" → 180 | "18 meses" → 540
    Sem unidade reconhecida: retorna o primeiro inteiro encontrado (assume dias).
    """
    t = text.strip().lower()
    m = re.search(r"(\d+)\s*(dia|m[eê]s|meses|ano)", t)
    if not m:
        nums = re.findall(r"\d+", t)
        return int(nums[0]) if nums else 0

    quantidade, unidade = int(m.group(1)), m.group(2)
    if unidade.startswith("dia"):
        return quantidade
    if unidade.startswith("m"):  # mês / meses
        return quantidade * _DIAS_POR_MES
    if unidade.startswith("ano"):
        return quantidade * _DIAS_POR_ANO
    return quantidade


def parse_valor_minimo(text: str) -> Decimal | None:
    """
    Extrai valor mínimo de investimento de um texto com moeda brasileira.

    "R$ 1.000,00" → Decimal("1000.00")
    "R$ 500"      → Decimal("500")
    "A partir de R$ 100,00" → Decimal("100.00")
    Retorna None se não encontrar nenhum número.
    """
    t = re.sub(r"[Rr]\$\s*", "", text.strip())
    # Remove separador de milhar (ponto antes de 3 dígitos), mantém decimal com vírgula
    t = re.sub(r"\.(?=\d{3}\b)", "", t)
    t = t.replace(",", ".")
    nums = re.findall(r"\d+(?:\.\d+)?", t)
    if not nums:
        return None
    try:
        return Decimal(nums[0])
    except InvalidOperation:
        return None


def normalizar_cnpj(text: str) -> str:
    """
    Normaliza CNPJ para o formato XX.XXX.XXX/XXXX-XX.

    Aceita texto já formatado ou só dígitos.
    Retorna '' se inválido (diferente de 14 dígitos).
    """
    digits = re.sub(r"\D", "", text or "")
    if len(digits) != 14:
        return ""
    return f"{digits[:2]}.{digits[2:5]}.{digits[5:8]}/{digits[8:12]}-{digits[12:14]}"
