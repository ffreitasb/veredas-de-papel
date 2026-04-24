"""Tests for veredas.catalog — tier lookup and label helpers."""

import pytest

from veredas.catalog import (
    TierEmissor,
    TierPlataforma,
    css_tier_emissor,
    css_tier_plataforma,
    get_tier_emissor,
    get_tier_plataforma,
    label_tier_emissor,
    label_tier_plataforma,
)

# ---------------------------------------------------------------------------
# get_tier_emissor
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "cnpj, expected",
    [
        ("60.872.504/0001-23", TierEmissor.BANCAO),  # Itaú
        ("60.746.948/0001-12", TierEmissor.BANCAO),  # Bradesco
        ("00.000.000/0001-91", TierEmissor.BANCAO),  # Banco do Brasil
        ("90.400.888/0001-42", TierEmissor.BANCAO),  # Santander
        ("33.156.031/0001-48", TierEmissor.MEDIO),  # Banco Master
        ("62.232.889/0001-90", TierEmissor.MEDIO),  # Daycoval
        ("18.236.120/0001-58", TierEmissor.FINTECH),  # Nubank
        ("00.416.968/0001-01", TierEmissor.FINTECH),  # Inter
        ("31.872.495/0001-72", TierEmissor.FINTECH),  # C6 Bank
    ],
)
def test_get_tier_emissor_known(cnpj, expected):
    assert get_tier_emissor(cnpj) == expected


def test_get_tier_emissor_unknown_cnpj():
    assert get_tier_emissor("99.999.999/0001-99") == TierEmissor.OUTROS


def test_get_tier_emissor_empty():
    assert get_tier_emissor("") == TierEmissor.OUTROS


def test_get_tier_emissor_digits_only():
    """CNPJ sem pontuação deve ser normalizado e encontrado no catálogo."""
    assert get_tier_emissor("60872504000123") == TierEmissor.BANCAO


def test_get_tier_emissor_digits_only_unknown():
    assert get_tier_emissor("99999999000199") == TierEmissor.OUTROS


def test_get_tier_emissor_strips_whitespace():
    assert get_tier_emissor("  60.872.504/0001-23  ") == TierEmissor.BANCAO


# ---------------------------------------------------------------------------
# get_tier_plataforma
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "fonte, expected",
    [
        ("xp", TierPlataforma.TIER_S),
        ("btg", TierPlataforma.TIER_S),
        ("rico", TierPlataforma.TIER_S),
        ("clear", TierPlataforma.TIER_S),
        ("genial", TierPlataforma.TIER_S),
        ("modal", TierPlataforma.TIER_S),
        ("inter", TierPlataforma.BANCO_DIGITAL),
        ("nubank", TierPlataforma.BANCO_DIGITAL),
        ("c6", TierPlataforma.BANCO_DIGITAL),
        ("pagbank", TierPlataforma.BANCO_DIGITAL),
        ("itau", TierPlataforma.BANCAO_PROPRIO),
        ("bradesco", TierPlataforma.BANCAO_PROPRIO),
        ("b3", TierPlataforma.MERCADO_SECUNDARIO),
        ("cetip", TierPlataforma.MERCADO_SECUNDARIO),
        ("secundario", TierPlataforma.MERCADO_SECUNDARIO),
    ],
)
def test_get_tier_plataforma_known(fonte, expected):
    assert get_tier_plataforma(fonte) == expected


def test_get_tier_plataforma_unknown():
    assert get_tier_plataforma("desconhecida") == TierPlataforma.OUTROS


def test_get_tier_plataforma_empty():
    assert get_tier_plataforma("") == TierPlataforma.OUTROS


def test_get_tier_plataforma_case_insensitive():
    assert get_tier_plataforma("XP") == TierPlataforma.TIER_S
    assert get_tier_plataforma("BTG") == TierPlataforma.TIER_S
    assert get_tier_plataforma("Inter") == TierPlataforma.BANCO_DIGITAL


# ---------------------------------------------------------------------------
# label and css helpers
# ---------------------------------------------------------------------------


def test_label_tier_emissor_all_tiers():
    for tier in TierEmissor:
        label = label_tier_emissor(tier)
        assert isinstance(label, str)
        assert len(label) > 0


def test_label_tier_plataforma_all_tiers():
    for tier in TierPlataforma:
        label = label_tier_plataforma(tier)
        assert isinstance(label, str)
        assert len(label) > 0


def test_css_tier_emissor_all_tiers():
    for tier in TierEmissor:
        css = css_tier_emissor(tier)
        assert isinstance(css, str)
        assert len(css) > 0


def test_css_tier_plataforma_all_tiers():
    for tier in TierPlataforma:
        css = css_tier_plataforma(tier)
        assert isinstance(css, str)
        assert len(css) > 0


def test_label_tier_emissor_bancao():
    assert label_tier_emissor(TierEmissor.BANCAO) == "Bancão"


def test_label_tier_plataforma_tier_s():
    assert label_tier_plataforma(TierPlataforma.TIER_S) == "Tier S"


def test_css_tier_emissor_bancao():
    assert css_tier_emissor(TierEmissor.BANCAO) == "tier-bancao"


def test_css_tier_plataforma_mercado_secundario():
    assert css_tier_plataforma(TierPlataforma.MERCADO_SECUNDARIO) == "plat-secundario"
