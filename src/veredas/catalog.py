"""
Catálogo de instituições financeiras e plataformas de distribuição.

Define dois eixos de classificação independentes:

  TierEmissor   — quem emitiu o CDB (risco do papel)
  TierPlataforma — onde o CDB está sendo ofertado (contexto de distribuição)

Os dois eixos são usados pelo detector de anomalias para ajustar os limiares:
um bancão oferecendo 110% CDI é mais suspeito do que uma pequena financeira
oferecendo a mesma taxa, porque bancões normalmente ficam abaixo de 100%.

Uso:

    from veredas.catalog import get_tier_emissor, get_tier_plataforma, TierEmissor

    tier = get_tier_emissor("60.872.504/0001-23")  # → TierEmissor.BANCAO
    tier = get_tier_plataforma("xp")               # → TierPlataforma.TIER_S

Este módulo é puro (sem imports de outros módulos veredas) para evitar
importações circulares — qualquer módulo pode importar daqui livremente.
"""

from decimal import Decimal
from enum import StrEnum


class TierEmissor(StrEnum):
    """Tier do emissor do CDB (instituição que captou o recurso)."""

    BANCAO = "bancao"    # Grandes bancos sistêmicos (Itaú, Bradesco, BB, CEF, Santander...)
    MEDIO = "medio"      # Bancos médios regionais (ABC, Daycoval, Banrisul, Sofisa...)
    FINTECH = "fintech"  # Bancos digitais (Nubank, Inter, C6, PagBank...)
    PEQUENO = "pequeno"  # Demais pequenas instituições e financeiras
    OUTROS = "outros"    # CNPJ não mapeado — assume thresholds conservadores


class TierPlataforma(StrEnum):
    """Tier da plataforma que distribui (não afeta risco, afeta peso da evidência)."""

    TIER_S = "tier_s"                          # XP, BTG Digital, Rico, Clear, Genial
    BANCO_DIGITAL = "banco_digital"            # Inter, Nubank, C6, PagBank — app próprio
    BANCAO_PROPRIO = "bancao_proprio"          # Canal próprio de bancão
    MERCADO_SECUNDARIO = "mercado_secundario"  # B3 / CETIP — maior evidência de stress
    OUTROS = "outros"                          # Plataforma não mapeada


# ---------------------------------------------------------------------------
# Metadados de exibição (label, cor CSS)
# ---------------------------------------------------------------------------

TIER_EMISSOR_META: dict[TierEmissor, dict] = {
    TierEmissor.BANCAO:  {"label": "Bancão",  "css": "tier-bancao",  "cor": "blue"},
    TierEmissor.MEDIO:   {"label": "Médio",   "css": "tier-medio",   "cor": "yellow"},
    TierEmissor.FINTECH: {"label": "Fintech", "css": "tier-fintech", "cor": "purple"},
    TierEmissor.PEQUENO: {"label": "Pequeno", "css": "tier-pequeno", "cor": "orange"},
    TierEmissor.OUTROS:  {"label": "Outros",  "css": "tier-outros",  "cor": "gray"},
}

TIER_PLATAFORMA_META: dict[TierPlataforma, dict] = {
    TierPlataforma.TIER_S:               {"label": "Tier S",        "css": "plat-tier-s",      "cor": "green"},
    TierPlataforma.BANCO_DIGITAL:        {"label": "Banco Digital", "css": "plat-digital",     "cor": "teal"},
    TierPlataforma.BANCAO_PROPRIO:       {"label": "Bancão",        "css": "plat-bancao",      "cor": "blue"},
    TierPlataforma.MERCADO_SECUNDARIO:   {"label": "B3 Secundário", "css": "plat-secundario",  "cor": "red"},
    TierPlataforma.OUTROS:               {"label": "Outros",        "css": "plat-outros",      "cor": "gray"},
}


# ---------------------------------------------------------------------------
# Mapeamento CNPJ → TierEmissor
#
# CNPJs no formato "XX.XXX.XXX/XXXX-XX" (com pontuação).
# Fonte: Banco Central — Lista de IFs (https://www.bcb.gov.br/fis/info/ifcadastro.asp)
# Adicione novas entradas conforme as IFs aparecerem no banco de dados.
# ---------------------------------------------------------------------------

CNPJ_TO_TIER_EMISSOR: dict[str, TierEmissor] = {
    # ── BANCÕES ──────────────────────────────────────────────────────────────
    "00.000.000/0001-91": TierEmissor.BANCAO,  # Banco do Brasil
    "00.360.305/0001-04": TierEmissor.BANCAO,  # Caixa Econômica Federal
    "60.872.504/0001-23": TierEmissor.BANCAO,  # Itaú Unibanco
    "60.746.948/0001-12": TierEmissor.BANCAO,  # Bradesco
    "90.400.888/0001-42": TierEmissor.BANCAO,  # Santander Brasil
    "30.306.294/0001-45": TierEmissor.BANCAO,  # BTG Pactual (banco)
    "58.160.789/0001-28": TierEmissor.BANCAO,  # Banco Safra
    "59.588.111/0001-03": TierEmissor.BANCAO,  # Banco BV (Votorantim)
    "33.479.023/0001-80": TierEmissor.BANCAO,  # Citibank Brasil
    "33.657.248/0001-89": TierEmissor.BANCAO,  # BNDES

    # ── MÉDIOS ───────────────────────────────────────────────────────────────
    "28.195.667/0001-06": TierEmissor.MEDIO,   # Banco ABC Brasil
    "92.702.067/0001-96": TierEmissor.MEDIO,   # Banrisul
    "62.232.889/0001-90": TierEmissor.MEDIO,   # Banco Daycoval
    "61.186.680/0001-74": TierEmissor.MEDIO,   # Banco BMG
    "60.889.128/0001-80": TierEmissor.MEDIO,   # Banco Sofisa
    "92.894.922/0001-08": TierEmissor.MEDIO,   # Banco Original
    "00.000.208/0001-00": TierEmissor.MEDIO,   # BRB — Banco de Brasília
    "14.388.334/0001-99": TierEmissor.MEDIO,   # Paraná Banco
    "68.900.810/0001-38": TierEmissor.MEDIO,   # Banco Rendimento
    "33.156.031/0001-48": TierEmissor.MEDIO,   # Banco Master  ← monitorar de perto
    "17.184.037/0001-10": TierEmissor.MEDIO,   # Banco Mercantil do Brasil
    "62.144.175/0001-20": TierEmissor.MEDIO,   # Banco Pine
    "00.556.603/0001-56": TierEmissor.MEDIO,   # Banco Bari

    # ── FINTECHS / BANCOS DIGITAIS ───────────────────────────────────────────
    "18.236.120/0001-58": TierEmissor.FINTECH,  # Nubank (Nu Pagamentos)
    "00.416.968/0001-01": TierEmissor.FINTECH,  # Banco Inter
    "31.872.495/0001-72": TierEmissor.FINTECH,  # C6 Bank
    "08.667.783/0001-42": TierEmissor.FINTECH,  # PagBank (PagSeguro)
    "10.573.521/0001-91": TierEmissor.FINTECH,  # Mercado Pago
    "20.855.875/0001-82": TierEmissor.FINTECH,  # Banco Neon
    "13.673.855/0001-40": TierEmissor.FINTECH,  # Will Bank
    "10.664.513/0001-50": TierEmissor.FINTECH,  # Agibank
    "33.264.668/0001-03": TierEmissor.FINTECH,  # Banco XP
    "45.233.749/0001-40": TierEmissor.FINTECH,  # Banco Modal (Modalmais)
}


# ---------------------------------------------------------------------------
# Mapeamento fonte → TierPlataforma
#
# "fonte" é o valor do campo TaxaCDB.fonte / CDBOferta.fonte.
# ---------------------------------------------------------------------------

FONTE_TO_TIER_PLATAFORMA: dict[str, TierPlataforma] = {
    # Tier S
    "xp":      TierPlataforma.TIER_S,
    "btg":     TierPlataforma.TIER_S,
    "rico":    TierPlataforma.TIER_S,
    "clear":   TierPlataforma.TIER_S,
    "genial":  TierPlataforma.TIER_S,
    "modal":   TierPlataforma.TIER_S,
    # Bancos digitais (canal próprio)
    "inter":      TierPlataforma.BANCO_DIGITAL,
    "nubank":     TierPlataforma.BANCO_DIGITAL,
    "c6":         TierPlataforma.BANCO_DIGITAL,
    "pagbank":    TierPlataforma.BANCO_DIGITAL,
    "picpay":     TierPlataforma.BANCO_DIGITAL,
    "mercadopago": TierPlataforma.BANCO_DIGITAL,
    # Canal próprio de bancão
    "itau":      TierPlataforma.BANCAO_PROPRIO,
    "bradesco":  TierPlataforma.BANCAO_PROPRIO,
    "bb":        TierPlataforma.BANCAO_PROPRIO,
    "caixa":     TierPlataforma.BANCAO_PROPRIO,
    "santander": TierPlataforma.BANCAO_PROPRIO,
    "safra":     TierPlataforma.BANCAO_PROPRIO,
    # Mercado secundário (B3)
    "b3":        TierPlataforma.MERCADO_SECUNDARIO,
    "cetip":     TierPlataforma.MERCADO_SECUNDARIO,
    "secundario": TierPlataforma.MERCADO_SECUNDARIO,
}


# ---------------------------------------------------------------------------
# Limiares de anomalia ajustados por tier
#
# Chaves mapeiam direto para os kwargs de RuleThresholds (rules.py).
# Quanto menor o tier (mais estabelecido o banco), menor o threshold que
# dispara o alarme — porque qualquer desvio da normalidade é mais suspeito.
#
#  bancão: 108% CDI → HIGH  (Itaú normalmente fica em 95-100%)
#  médio:  125% CDI → HIGH  (ABC, Daycoval normalmente 105-115%)
#  fintech: 118% CDI → HIGH (Inter, Nubank normalmente 100-112%)
#  pequeno: 130% CDI → HIGH (atual default, base de comparação)
# ---------------------------------------------------------------------------

TIER_SPREAD_THRESHOLDS: dict[TierEmissor, dict[str, Decimal]] = {
    TierEmissor.BANCAO: {
        "spread_alto":         Decimal("108"),
        "spread_critico":      Decimal("120"),
        "salto_brusco":        Decimal("5"),
        "salto_extremo":       Decimal("10"),
        "ipca_spread_alto":    Decimal("7"),
        "ipca_spread_critico": Decimal("10"),
        "divergencia":         Decimal("2"),
        "divergencia_extrema": Decimal("3"),
    },
    TierEmissor.MEDIO: {
        "spread_alto":         Decimal("125"),
        "spread_critico":      Decimal("145"),
        "salto_brusco":        Decimal("8"),
        "salto_extremo":       Decimal("15"),
        "ipca_spread_alto":    Decimal("9"),
        "ipca_spread_critico": Decimal("13"),
        "divergencia":         Decimal("2"),
        "divergencia_extrema": Decimal("3"),
    },
    TierEmissor.FINTECH: {
        "spread_alto":         Decimal("118"),
        "spread_critico":      Decimal("135"),
        "salto_brusco":        Decimal("7"),
        "salto_extremo":       Decimal("14"),
        "ipca_spread_alto":    Decimal("8"),
        "ipca_spread_critico": Decimal("12"),
        "divergencia":         Decimal("2"),
        "divergencia_extrema": Decimal("3"),
    },
    TierEmissor.PEQUENO: {
        "spread_alto":         Decimal("130"),  # defaults atuais
        "spread_critico":      Decimal("150"),
        "salto_brusco":        Decimal("10"),
        "salto_extremo":       Decimal("20"),
        "ipca_spread_alto":    Decimal("10"),
        "ipca_spread_critico": Decimal("15"),
        "divergencia":         Decimal("2"),
        "divergencia_extrema": Decimal("3"),
    },
    TierEmissor.OUTROS: {
        "spread_alto":         Decimal("130"),  # conservador = igual a PEQUENO
        "spread_critico":      Decimal("150"),
        "salto_brusco":        Decimal("10"),
        "salto_extremo":       Decimal("20"),
        "ipca_spread_alto":    Decimal("10"),
        "ipca_spread_critico": Decimal("15"),
        "divergencia":         Decimal("2"),
        "divergencia_extrema": Decimal("3"),
    },
}


# ---------------------------------------------------------------------------
# API pública
# ---------------------------------------------------------------------------


def get_tier_emissor(cnpj: str) -> TierEmissor:
    """
    Retorna o tier do emissor pelo CNPJ.

    Aceita CNPJ formatado ("XX.XXX.XXX/XXXX-XX") ou só dígitos.
    Retorna TierEmissor.OUTROS se não encontrado no catálogo.
    """
    cnpj = cnpj.strip() if cnpj else ""

    # Normalizar para formato pontilhado se vier só dígitos
    if cnpj.isdigit() and len(cnpj) == 14:
        cnpj = f"{cnpj[:2]}.{cnpj[2:5]}.{cnpj[5:8]}/{cnpj[8:12]}-{cnpj[12:14]}"

    return CNPJ_TO_TIER_EMISSOR.get(cnpj, TierEmissor.OUTROS)


def get_tier_plataforma(fonte: str) -> TierPlataforma:
    """
    Retorna o tier da plataforma pelo nome da fonte.

    Retorna TierPlataforma.OUTROS se não encontrado.
    """
    return FONTE_TO_TIER_PLATAFORMA.get((fonte or "").lower().strip(), TierPlataforma.OUTROS)


def label_tier_emissor(tier: TierEmissor) -> str:
    """Rótulo legível do tier do emissor (usado em templates)."""
    return TIER_EMISSOR_META[tier]["label"]


def label_tier_plataforma(tier: TierPlataforma) -> str:
    """Rótulo legível do tier da plataforma (usado em templates)."""
    return TIER_PLATAFORMA_META[tier]["label"]


def css_tier_emissor(tier: TierEmissor) -> str:
    """Classe CSS do badge de tier (usado em templates)."""
    return TIER_EMISSOR_META[tier]["css"]


def css_tier_plataforma(tier: TierPlataforma) -> str:
    """Classe CSS do badge de plataforma (usado em templates)."""
    return TIER_PLATAFORMA_META[tier]["css"]
