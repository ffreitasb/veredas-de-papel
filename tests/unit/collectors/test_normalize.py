"""
Testes unitários para veredas.collectors.scrapers.normalize.

Cobre parse_taxa, parse_prazo_dias, parse_valor_minimo e normalizar_cnpj.
Todos os inputs são strings típicas de prateleiras de corretoras brasileiras.
"""

from decimal import Decimal

import pytest

from veredas.collectors.scrapers.normalize import (
    CDBOferta,
    normalizar_cnpj,
    parse_prazo_dias,
    parse_taxa,
    parse_valor_minimo,
)
from veredas.storage.models import Indexador

# ---------------------------------------------------------------------------
# parse_taxa — CDI puro
# ---------------------------------------------------------------------------


def test_parse_taxa_cdi_puro_simples():
    idx, pct, ta = parse_taxa("120% CDI")
    assert idx == Indexador.CDI
    assert pct == Decimal("120")
    assert ta is None


def test_parse_taxa_cdi_puro_com_virgula():
    idx, pct, ta = parse_taxa("120,50% do CDI")
    assert idx == Indexador.CDI
    assert pct == Decimal("120.50")
    assert ta is None


def test_parse_taxa_cdi_puro_cdi_na_frente():
    idx, pct, ta = parse_taxa("CDI 115%")
    assert idx == Indexador.CDI
    assert pct == Decimal("115")
    assert ta is None


# ---------------------------------------------------------------------------
# parse_taxa — CDI + spread
# ---------------------------------------------------------------------------


def test_parse_taxa_cdi_mais_spread():
    idx, pct, ta = parse_taxa("CDI + 2,5%")
    assert idx == Indexador.CDI
    assert pct == Decimal("100")
    assert ta == Decimal("2.5")


def test_parse_taxa_cdi_mais_spread_sem_espaco():
    idx, pct, ta = parse_taxa("CDI+2%")
    assert idx == Indexador.CDI
    assert pct == Decimal("100")
    assert ta == Decimal("2")


def test_parse_taxa_cdi_mais_spread_ponto_decimal():
    idx, pct, ta = parse_taxa("CDI + 1.75% a.a.")
    assert idx == Indexador.CDI
    assert pct == Decimal("100")
    assert ta == Decimal("1.75")


# ---------------------------------------------------------------------------
# parse_taxa — IPCA+
# ---------------------------------------------------------------------------


def test_parse_taxa_ipca_mais():
    idx, pct, ta = parse_taxa("IPCA + 6,50% a.a.")
    assert idx == Indexador.IPCA
    assert pct == Decimal("0")
    assert ta == Decimal("6.50")


def test_parse_taxa_ipca_mais_sem_espaco():
    idx, pct, ta = parse_taxa("IPCA+5%")
    assert idx == Indexador.IPCA
    assert pct == Decimal("0")
    assert ta == Decimal("5")


def test_parse_taxa_ipca_sem_plus():
    idx, pct, ta = parse_taxa("IPCA 100%")
    assert idx == Indexador.IPCA
    assert ta is None


# ---------------------------------------------------------------------------
# parse_taxa — PREFIXADO
# ---------------------------------------------------------------------------


def test_parse_taxa_prefixado_virgula():
    idx, pct, ta = parse_taxa("12,5% a.a.")
    assert idx == Indexador.PREFIXADO
    assert pct == Decimal("12.5")
    assert ta is None


def test_parse_taxa_prefixado_ponto():
    idx, pct, ta = parse_taxa("11.75% a.a.")
    assert idx == Indexador.PREFIXADO
    assert pct == Decimal("11.75")
    assert ta is None


def test_parse_taxa_prefixado_inteiro():
    idx, pct, ta = parse_taxa("13% a.a.")
    assert idx == Indexador.PREFIXADO
    assert pct == Decimal("13")
    assert ta is None


# ---------------------------------------------------------------------------
# parse_taxa — SELIC
# ---------------------------------------------------------------------------


def test_parse_taxa_selic_percentual():
    idx, pct, ta = parse_taxa("100% da Selic")
    assert idx == Indexador.SELIC
    assert pct == Decimal("100")
    assert ta is None


def test_parse_taxa_selic_mais_spread():
    idx, pct, ta = parse_taxa("Selic + 0,5%")
    assert idx == Indexador.SELIC
    assert pct == Decimal("100")
    assert ta == Decimal("0.5")


def test_parse_taxa_selic_uppercase():
    idx, pct, ta = parse_taxa("SELIC + 1%")
    assert idx == Indexador.SELIC
    assert pct == Decimal("100")
    assert ta == Decimal("1")


# ---------------------------------------------------------------------------
# parse_prazo_dias
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("texto", "esperado"),
    [
        ("360 dias", 360),
        ("90 dias", 90),
        ("1 ano", 360),
        ("2 anos", 720),
        ("6 meses", 180),
        ("18 meses", 540),
        ("3 mês", 90),
        ("720", 720),
        ("1080 dias corridos", 1080),
    ],
)
def test_parse_prazo_dias(texto, esperado):
    assert parse_prazo_dias(texto) == esperado


def test_parse_prazo_dias_sem_unidade_retorna_numero():
    assert parse_prazo_dias("365") == 365


def test_parse_prazo_dias_vazio_retorna_zero():
    assert parse_prazo_dias("sem prazo") == 0


# ---------------------------------------------------------------------------
# parse_valor_minimo
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("texto", "esperado"),
    [
        ("R$ 1.000,00", Decimal("1000.00")),
        ("R$ 500,00", Decimal("500.00")),
        ("R$ 500", Decimal("500")),
        ("R$ 100,00", Decimal("100.00")),
        ("A partir de R$ 1.000,00", Decimal("1000.00")),
        ("Mínimo R$ 5.000,00", Decimal("5000.00")),
    ],
)
def test_parse_valor_minimo(texto, esperado):
    assert parse_valor_minimo(texto) == esperado


def test_parse_valor_minimo_sem_valor_retorna_none():
    assert parse_valor_minimo("sem mínimo") is None


def test_parse_valor_minimo_texto_vazio_retorna_none():
    assert parse_valor_minimo("") is None


# ---------------------------------------------------------------------------
# normalizar_cnpj
# ---------------------------------------------------------------------------


def test_normalizar_cnpj_so_digitos():
    assert normalizar_cnpj("12345678000199") == "12.345.678/0001-99"


def test_normalizar_cnpj_ja_formatado():
    assert normalizar_cnpj("12.345.678/0001-99") == "12.345.678/0001-99"


def test_normalizar_cnpj_invalido_retorna_vazio():
    assert normalizar_cnpj("123") == ""


def test_normalizar_cnpj_vazio_retorna_vazio():
    assert normalizar_cnpj("") == ""


def test_normalizar_cnpj_none_retorna_vazio():
    assert normalizar_cnpj(None) == ""  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# CDBOferta — smoke test de construção
# ---------------------------------------------------------------------------


def test_cdb_oferta_construcao():
    oferta = CDBOferta(
        emissor_nome="Banco Exemplo S.A.",
        emissor_cnpj="12.345.678/0001-99",
        indexador=Indexador.CDI,
        percentual=Decimal("120"),
        taxa_adicional=None,
        prazo_dias=360,
        valor_minimo=Decimal("1000"),
        liquidez_diaria=False,
        fonte="xp",
        url_fonte="https://www.xpi.com.br/investimentos/renda-fixa/",
    )
    assert oferta.indexador == Indexador.CDI
    assert oferta.percentual == Decimal("120")
    assert oferta.raw == {}
