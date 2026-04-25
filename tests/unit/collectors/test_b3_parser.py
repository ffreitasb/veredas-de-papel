"""Testes unitários para collectors/b3/parser.py — parser do boletim B3."""

from datetime import date
from decimal import Decimal

import pytest

from veredas.collectors.b3.parser import B3RendaFixaParser, TICKER_PREFIX_TO_CNPJ

PREGAO = "20260423"
# Linha realista do boletim (8 campos separados por ";")
LINHA_ITUB = "ITUB-DEB71;20250715;557;811;1348.48;1311.18;1.606608;311.1753"
LINHA_VALE = "VALE-DEB12;20280101;730;520;1100.00;1050.00;8.5;2.1"


@pytest.fixture
def parser():
    return B3RendaFixaParser()


# ---------------------------------------------------------------------------
# parse — casos gerais
# ---------------------------------------------------------------------------


class TestParse:
    def test_conteudo_vazio_retorna_lista_vazia(self, parser):
        assert parser.parse("") == []

    def test_apenas_whitespace_retorna_lista_vazia(self, parser):
        assert parser.parse("   \n\n  ") == []

    def test_primeira_linha_invalida_bloqueia_parse(self, parser):
        """Se a data do pregão não for parseable, nenhuma linha é processada."""
        assert parser.parse("INVALIDO\n" + LINHA_ITUB) == []

    def test_linha_valida_retorna_1_record(self, parser):
        conteudo = f"{PREGAO}\n{LINHA_ITUB}"
        records = parser.parse(conteudo)
        assert len(records) == 1

    def test_linha_com_campos_insuficientes_ignorada(self, parser):
        conteudo = f"{PREGAO}\nTICKER;20250715;100"
        assert parser.parse(conteudo) == []

    def test_linha_vazia_entre_dados_ignorada(self, parser):
        conteudo = f"{PREGAO}\n{LINHA_ITUB}\n\n{LINHA_VALE}"
        records = parser.parse(conteudo)
        assert len(records) == 2

    def test_multiplas_linhas_validas(self, parser):
        conteudo = f"{PREGAO}\n{LINHA_ITUB}\n{LINHA_VALE}"
        assert len(parser.parse(conteudo)) == 2


# ---------------------------------------------------------------------------
# Campos do record
# ---------------------------------------------------------------------------


class TestCamposRecord:
    def test_data_pregao_correta(self, parser):
        r = parser.parse(f"{PREGAO}\n{LINHA_ITUB}")[0]
        assert r.data_pregao == date(2026, 4, 23)

    def test_codigo_correto(self, parser):
        r = parser.parse(f"{PREGAO}\n{LINHA_ITUB}")[0]
        assert r.codigo == "ITUB-DEB71"

    def test_emissor_codigo_extraido(self, parser):
        r = parser.parse(f"{PREGAO}\n{LINHA_ITUB}")[0]
        assert r.emissor_codigo == "ITUB"

    def test_pu_mercado_decimal(self, parser):
        r = parser.parse(f"{PREGAO}\n{LINHA_ITUB}")[0]
        assert r.pu_mercado == Decimal("1348.48")

    def test_taxa_mercado_decimal(self, parser):
        r = parser.parse(f"{PREGAO}\n{LINHA_ITUB}")[0]
        assert r.taxa_mercado == Decimal("1.606608")

    def test_dias_corridos_int(self, parser):
        r = parser.parse(f"{PREGAO}\n{LINHA_ITUB}")[0]
        assert r.dias_corridos == 557
        assert r.dias_uteis == 811


# ---------------------------------------------------------------------------
# Tipo de instrumento
# ---------------------------------------------------------------------------


class TestTipoFromTicker:
    @pytest.mark.parametrize(
        "ticker, tipo_esperado",
        [
            ("ITUB-DEB71", "DEB"),
            ("VALE-CRI12", "CRI"),
            ("XPTO-CRA5", "CRA"),
            ("XPTO-LCI3", "LCI"),
            ("XPTO-LCA2", "LCA"),
            ("XPTO-CDB1", "CDB"),
            ("XPTO-SEM", "OUTRO"),   # sem número no final → regex não bate
            ("SEMTRACO", "OUTRO"),   # sem "-"
        ],
    )
    def test_tipo_detectado(self, parser, ticker, tipo_esperado):
        linha = f"{ticker};20280101;100;80;100.0;95.0;10.0;1.5"
        records = parser.parse(f"{PREGAO}\n{linha}")
        assert records[0].tipo == tipo_esperado


# ---------------------------------------------------------------------------
# CNPJ e is_financeira
# ---------------------------------------------------------------------------


class TestCnpjEmissor:
    def test_cnpj_mapeado_para_itub(self, parser):
        r = parser.parse(f"{PREGAO}\n{LINHA_ITUB}")[0]
        assert r.cnpj_emissor == TICKER_PREFIX_TO_CNPJ["ITUB"]
        assert r.is_financeira is True

    def test_emissor_nao_financeiro_sem_cnpj(self, parser):
        r = parser.parse(f"{PREGAO}\n{LINHA_VALE}")[0]
        assert r.cnpj_emissor is None
        assert r.is_financeira is False

    def test_todos_prefixos_no_mapa_tem_cnpj_formatado(self):
        for prefixo, cnpj in TICKER_PREFIX_TO_CNPJ.items():
            assert "/" in cnpj, f"CNPJ de {prefixo} parece não estar formatado: {cnpj}"
            assert len(cnpj.replace(".", "").replace("/", "").replace("-", "")) == 14
