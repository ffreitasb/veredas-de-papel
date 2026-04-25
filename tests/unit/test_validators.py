"""Testes unitários para validators.py — CNPJ e utilitários."""

from decimal import Decimal

import pytest
from fastapi import HTTPException

from veredas.validators import formatar_cnpj, normalizar_cnpj, parse_cnpj, round_decimal, validar_cnpj

# ---------------------------------------------------------------------------
# validar_cnpj
# ---------------------------------------------------------------------------

CNPJ_VALIDO_ITAU = "60.872.504/0001-23"
CNPJ_VALIDO_SEM_MASK = "60872504000123"
CNPJ_VALIDO_SIMPLES = "11.222.333/0001-81"


class TestValidarCnpj:
    @pytest.mark.parametrize(
        "cnpj, esperado",
        [
            (CNPJ_VALIDO_ITAU, True),
            (CNPJ_VALIDO_SEM_MASK, True),
            (CNPJ_VALIDO_SIMPLES, True),
            ("11.111.111/1111-11", False),  # todos dígitos iguais
            ("00.000.000/0000-00", False),  # zeros
            ("12.345.678/0001-00", False),  # dígitos verificadores errados
            ("123", False),  # curto demais
            ("", False),  # vazio
            ("12345678901234", False),  # 14 dígitos mas inválido
        ],
    )
    def test_validar_cnpj(self, cnpj, esperado):
        assert validar_cnpj(cnpj) == esperado

    def test_aceita_cnpj_com_ou_sem_formatacao(self):
        assert validar_cnpj(CNPJ_VALIDO_ITAU) is True
        assert validar_cnpj(CNPJ_VALIDO_SEM_MASK) is True

    def test_rejeita_cnpj_com_13_digitos(self):
        assert validar_cnpj("1234567890123") is False

    def test_rejeita_cnpj_com_15_digitos(self):
        assert validar_cnpj("123456789012345") is False


# ---------------------------------------------------------------------------
# normalizar_cnpj
# ---------------------------------------------------------------------------


class TestNormalizarCnpj:
    def test_remove_pontos_barra_traco(self):
        assert normalizar_cnpj("60.872.504/0001-23") == "60872504000123"

    def test_ja_normalizado_permanece_igual(self):
        assert normalizar_cnpj("60872504000123") == "60872504000123"


# ---------------------------------------------------------------------------
# formatar_cnpj
# ---------------------------------------------------------------------------


class TestFormatarCnpj:
    def test_formata_cnpj_numerico(self):
        assert formatar_cnpj("60872504000123") == "60.872.504/0001-23"

    def test_formata_cnpj_ja_formatado(self):
        # Aceita formatado e reformata corretamente
        assert formatar_cnpj("60.872.504/0001-23") == "60.872.504/0001-23"

    def test_cnpj_invalido_retorna_original(self):
        assert formatar_cnpj("123") == "123"


# ---------------------------------------------------------------------------
# parse_cnpj
# ---------------------------------------------------------------------------


class TestParseCnpj:
    def test_retorna_cnpj_normalizado_valido(self):
        result = parse_cnpj(CNPJ_VALIDO_ITAU)
        assert result == "60872504000123"

    def test_retorna_none_quando_vazio_e_nao_required(self):
        assert parse_cnpj(None) is None
        assert parse_cnpj("") is None
        assert parse_cnpj("   ") is None

    def test_levanta_400_quando_vazio_e_required(self):
        with pytest.raises(HTTPException) as exc_info:
            parse_cnpj(None, required=True)
        assert exc_info.value.status_code == 400

    def test_levanta_400_para_cnpj_com_tamanho_errado(self):
        with pytest.raises(HTTPException) as exc_info:
            parse_cnpj("12345")
        assert exc_info.value.status_code == 400

    def test_levanta_400_para_digitos_verificadores_errados(self):
        with pytest.raises(HTTPException) as exc_info:
            parse_cnpj("12.345.678/0001-00", validate=True)
        assert exc_info.value.status_code == 400

    def test_validate_false_aceita_cnpj_invalido(self):
        # Com validate=False, apenas normaliza sem checar dígitos
        result = parse_cnpj("12.345.678/0001-00", validate=False)
        assert result == "12345678000100"

    def test_string_vazia_required_levanta_400(self):
        with pytest.raises(HTTPException) as exc_info:
            parse_cnpj("  ", required=True)
        assert exc_info.value.status_code == 400


# ---------------------------------------------------------------------------
# round_decimal
# ---------------------------------------------------------------------------


class TestRoundDecimal:
    def test_arredonda_para_2_casas_por_padrao(self):
        assert round_decimal(Decimal("1.235")) == Decimal("1.24")

    def test_arredonda_para_0_casas(self):
        assert round_decimal(Decimal("1.6"), places=0) == Decimal("2")

    def test_arredonda_para_4_casas(self):
        result = round_decimal(Decimal("1.23456"), places=4)
        assert result == Decimal("1.2346")

    def test_valor_exato_nao_muda(self):
        assert round_decimal(Decimal("1.50")) == Decimal("1.50")
