"""
Normalizador de dados de taxas CDB.

Padroniza dados coletados de diferentes corretoras para formato único:
- Normalização de nomes de instituições
- Padronização de CNPJs
- Conversão de formatos de taxa
- Deduplicação
"""

import logging
import re
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Optional

from veredas import TZ_BRASIL
from veredas.collectors.scrapers.base import ScraperResult, TaxaColetada
from veredas.storage.models import Indexador

logger = logging.getLogger(__name__)


# CNPJ placeholder para instituições não identificadas
# Formato válido mas claramente artificial (indica "desconhecido")
CNPJ_DESCONHECIDO: str = "00.000.000/0001-00"

# Mapeamento de nomes comuns para CNPJs
CNPJ_MAP: dict[str, str] = {
    # Grandes bancos
    "BANCO DO BRASIL": "00.000.000/0001-91",
    "BB": "00.000.000/0001-91",
    "BRADESCO": "60.746.948/0001-12",
    "ITAU": "60.701.190/0001-04",
    "ITAÚ": "60.701.190/0001-04",
    "ITAU UNIBANCO": "60.701.190/0001-04",
    "CAIXA": "00.360.305/0001-04",
    "CEF": "00.360.305/0001-04",
    "SANTANDER": "33.657.248/0001-89",
    "SAFRA": "90.400.888/0001-42",
    "BTG": "30.306.294/0001-45",
    "BTG PACTUAL": "30.306.294/0001-45",
    # Bancos digitais
    "NUBANK": "18.236.120/0001-58",
    "NU": "18.236.120/0001-58",
    "INTER": "00.416.968/0001-01",
    "BANCO INTER": "00.416.968/0001-01",
    "C6": "10.573.521/0001-91",
    "C6 BANK": "10.573.521/0001-91",
    "ORIGINAL": "01.181.521/0001-55",
    "BANCO ORIGINAL": "01.181.521/0001-55",
    "NEON": "18.236.120/0001-58",  # Usa estrutura do Nubank
    "NEXT": "60.746.948/0001-12",  # Bradesco
    # Corretoras
    "XP": "04.902.979/0001-44",
    "XP INVESTIMENTOS": "04.902.979/0001-44",
    "RICO": "04.902.979/0001-44",  # Grupo XP
    "CLEAR": "04.902.979/0001-44",  # Grupo XP
    "MODAL": "30.723.886/0001-62",
    "MODALMAIS": "30.723.886/0001-62",
    # Financeiras
    "PAN": "92.874.270/0001-40",
    "BANCO PAN": "92.874.270/0001-40",
    "BMG": "61.186.680/0001-74",
    "DAYCOVAL": "62.232.889/0001-90",
    "SOFISA": "60.889.128/0001-80",
    "PINE": "62.144.175/0001-20",
    "ABC BRASIL": "28.195.667/0001-06",
    "VOITER": "59.118.133/0001-99",
    "PARANÁ BANCO": "14.388.334/0001-99",
}

# Aliases para nomes de instituições
NAME_ALIASES: dict[str, str] = {
    "BB": "Banco do Brasil",
    "CEF": "Caixa Econômica Federal",
    "CAIXA": "Caixa Econômica Federal",
    "BTG": "BTG Pactual",
    "NU": "Nubank",
    "C6": "C6 Bank",
    "XP": "XP Investimentos",
}


@dataclass
class NormalizedTaxa:
    """Taxa normalizada e validada."""

    instituicao_nome: str
    instituicao_cnpj: str
    indexador: Indexador
    percentual: Decimal
    taxa_adicional: Optional[Decimal]
    prazo_dias: int
    valor_minimo: Optional[Decimal]
    liquidez_diaria: bool
    fonte: str
    coletado_em: datetime
    raw_data: Optional[dict] = None


def normalize_cnpj(cnpj: Optional[str]) -> Optional[str]:
    """
    Normaliza CNPJ para formato padrão (XX.XXX.XXX/XXXX-XX).

    Args:
        cnpj: CNPJ em qualquer formato

    Returns:
        CNPJ formatado ou None se inválido
    """
    if not cnpj:
        return None

    # Remove tudo que não é dígito
    digits = re.sub(r"\D", "", cnpj)

    if len(digits) != 14:
        return None

    # Formata
    return f"{digits[:2]}.{digits[2:5]}.{digits[5:8]}/{digits[8:12]}-{digits[12:]}"


def normalize_nome(nome: str) -> str:
    """
    Normaliza nome de instituição.

    Args:
        nome: Nome original

    Returns:
        Nome padronizado
    """
    nome_upper = nome.upper().strip()

    # Verifica aliases
    if nome_upper in NAME_ALIASES:
        return NAME_ALIASES[nome_upper]

    # Remove sufixos comuns
    suffixes = [" S.A.", " S/A", " SA", " LTDA", " BANCO", " BANK"]
    for suffix in suffixes:
        if nome_upper.endswith(suffix):
            nome_upper = nome_upper[: -len(suffix)]

    # Title case
    return nome_upper.title()


def find_cnpj_by_name(nome: str) -> Optional[str]:
    """
    Busca CNPJ pelo nome da instituição.

    Args:
        nome: Nome da instituição

    Returns:
        CNPJ ou None se não encontrado
    """
    nome_upper = nome.upper().strip()

    # Busca direta
    if nome_upper in CNPJ_MAP:
        return CNPJ_MAP[nome_upper]

    # Busca parcial
    for key, cnpj in CNPJ_MAP.items():
        if key in nome_upper or nome_upper in key:
            return cnpj

    return None


def validate_percentual(
    percentual: Decimal,
    indexador: Indexador,
) -> bool:
    """
    Valida se o percentual está em faixa razoável.

    Args:
        percentual: Valor do percentual
        indexador: Tipo de indexador

    Returns:
        True se válido
    """
    if indexador == Indexador.CDI:
        # CDI geralmente entre 80% e 200%
        return Decimal("50") <= percentual <= Decimal("250")
    elif indexador == Indexador.IPCA:
        # IPCA+ geralmente entre 3% e 15%
        return Decimal("1") <= percentual <= Decimal("20")
    elif indexador == Indexador.PREFIXADO:
        # Prefixado geralmente entre 5% e 25%
        return Decimal("3") <= percentual <= Decimal("30")
    elif indexador == Indexador.SELIC:
        # Selic+ geralmente entre 0% e 5%
        return Decimal("-5") <= percentual <= Decimal("10")

    return True


def validate_prazo(prazo_dias: int) -> bool:
    """
    Valida se o prazo está em faixa razoável.

    Args:
        prazo_dias: Prazo em dias

    Returns:
        True se válido (1 dia a 10 anos)
    """
    return 1 <= prazo_dias <= 3650


class TaxaNormalizer:
    """
    Normalizador de taxas coletadas.

    Padroniza, valida e deduplica taxas de diferentes fontes.
    """

    # M1 FIX: Limite máximo para evitar memory leak
    MAX_SEEN_SIZE: int = 10000

    def __init__(self, strict: bool = False, max_seen: int = MAX_SEEN_SIZE):
        """
        Inicializa o normalizador.

        Args:
            strict: Se True, rejeita taxas sem CNPJ
            max_seen: Tamanho máximo do cache de deduplicação
        """
        self.strict = strict
        self._max_seen = max_seen
        self._seen: set[str] = set()

    def _generate_key(self, taxa: TaxaColetada, fonte: str) -> str:
        """Gera chave única para deduplicação."""
        return (
            f"{taxa.instituicao_nome}|{taxa.indexador.value}|"
            f"{taxa.percentual}|{taxa.prazo_dias}|{fonte}"
        )

    def normalize(
        self,
        result: ScraperResult,
    ) -> list[NormalizedTaxa]:
        """
        Normaliza todas as taxas de um resultado de scraping.

        Args:
            result: Resultado do scraper

        Returns:
            Lista de taxas normalizadas
        """
        normalized: list[NormalizedTaxa] = []

        for taxa in result.taxas:
            try:
                norm = self.normalize_single(taxa, result.fonte, result.timestamp)
                if norm:
                    # Deduplicação com limite de memória
                    key = self._generate_key(taxa, result.fonte)
                    if key not in self._seen:
                        # M1 FIX: Limpa cache se atingir limite
                        if len(self._seen) >= self._max_seen:
                            logger.debug(f"Cache de deduplicação cheio ({self._max_seen}), limpando...")
                            self._seen.clear()
                        self._seen.add(key)
                        normalized.append(norm)
            except Exception as e:
                logger.warning(f"Erro ao normalizar taxa: {e}")

        return normalized

    def normalize_single(
        self,
        taxa: TaxaColetada,
        fonte: str,
        timestamp: datetime,
    ) -> Optional[NormalizedTaxa]:
        """
        Normaliza uma única taxa.

        Args:
            taxa: Taxa coletada
            fonte: Nome da fonte
            timestamp: Timestamp da coleta

        Returns:
            Taxa normalizada ou None se inválida
        """
        # Normaliza nome
        nome = normalize_nome(taxa.instituicao_nome)

        # Busca/normaliza CNPJ
        cnpj = normalize_cnpj(taxa.instituicao_cnpj)
        if not cnpj:
            cnpj = find_cnpj_by_name(taxa.instituicao_nome)

        if not cnpj and self.strict:
            logger.debug(f"CNPJ não encontrado para {nome}")
            return None

        # Usa CNPJ placeholder se não encontrado
        if not cnpj:
            cnpj = CNPJ_DESCONHECIDO

        # Valida percentual
        if not validate_percentual(taxa.percentual, taxa.indexador):
            logger.warning(
                f"Percentual suspeito: {taxa.percentual}% {taxa.indexador.value} ({nome})"
            )
            # Não rejeita, apenas loga

        # Valida prazo
        if not validate_prazo(taxa.prazo_dias):
            logger.warning(f"Prazo suspeito: {taxa.prazo_dias} dias ({nome})")
            return None

        return NormalizedTaxa(
            instituicao_nome=nome,
            instituicao_cnpj=cnpj,
            indexador=taxa.indexador,
            percentual=taxa.percentual,
            taxa_adicional=taxa.taxa_adicional,
            prazo_dias=taxa.prazo_dias,
            valor_minimo=taxa.valor_minimo,
            liquidez_diaria=taxa.liquidez_diaria,
            fonte=fonte,
            coletado_em=timestamp,
            raw_data=taxa.raw_data,
        )

    def reset(self) -> None:
        """Limpa cache de deduplicação."""
        self._seen.clear()


def merge_results(results: list[ScraperResult]) -> list[NormalizedTaxa]:
    """
    Combina resultados de múltiplos scrapers.

    Args:
        results: Lista de resultados de scrapers

    Returns:
        Lista consolidada de taxas normalizadas
    """
    normalizer = TaxaNormalizer()
    all_taxas: list[NormalizedTaxa] = []

    for result in results:
        taxas = normalizer.normalize(result)
        all_taxas.extend(taxas)

    return all_taxas


def calculate_average_by_institution(
    taxas: list[NormalizedTaxa],
) -> dict[str, dict[str, Decimal]]:
    """
    Calcula médias de taxas por instituição e indexador.

    Args:
        taxas: Lista de taxas normalizadas

    Returns:
        Dict com médias: {cnpj: {indexador: media}}
    """
    from collections import defaultdict

    sums: dict[str, dict[str, list[Decimal]]] = defaultdict(
        lambda: defaultdict(list)
    )

    for taxa in taxas:
        sums[taxa.instituicao_cnpj][taxa.indexador.value].append(taxa.percentual)

    result: dict[str, dict[str, Decimal]] = {}
    for cnpj, indexadores in sums.items():
        result[cnpj] = {}
        for indexador, valores in indexadores.items():
            result[cnpj][indexador] = sum(valores) / len(valores)

    return result


# Aliases para compatibilidade
DataNormalizer = TaxaNormalizer
TaxaNormalizada = NormalizedTaxa
