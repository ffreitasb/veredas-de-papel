"""Testes unitários para o método _parse() dos scrapers de corretora.

Usa HTML estático para cobrir a lógica de parsing sem Playwright.
Cada scraper exporta `_parse(html: str) -> list[CDBOferta]`.
"""

from decimal import Decimal

import pytest

from veredas.collectors.scrapers.btg import BTGCollector
from veredas.collectors.scrapers.inter import InterCollector
from veredas.collectors.scrapers.rico import RicoCollector
from veredas.collectors.scrapers.xp import XPCollector
from veredas.storage.models import Indexador

pytestmark = pytest.mark.skipif(
    __import__("importlib").util.find_spec("bs4") is None,
    reason="beautifulsoup4 não instalado",
)

# ---------------------------------------------------------------------------
# Helpers de HTML mínimo por scraper
# ---------------------------------------------------------------------------


def _btg_html(
    emissor: str = "Banco Alpha S.A.",
    taxa: str = "120% CDI",
    prazo: str = "365 dias",
    valor_min: str = "R$ 1.000,00",
    liquidez: str = "D+0 diária",
    cnpj: str = "12345678000100",
) -> str:
    return f"""
    <div class="FixedIncomeCard" data-cnpj="{cnpj}">
      <span class="issuer">{emissor}</span>
      <span class="rate">{taxa}</span>
      <span class="term">{prazo}</span>
      <span class="minValue">{valor_min}</span>
      <span class="liquidity">{liquidez}</span>
    </div>
    """


def _xp_html(
    emissor: str = "Banco Beta S.A.",
    taxa: str = "IPCA + 6,50% a.a.",
    prazo: str = "2 anos",
    valor_min: str = "R$ 500,00",
    liquidez: str = "No vencimento",
) -> str:
    return f"""
    <div data-testid="product-card">
      <span class="emissor-nome">{emissor}</span>
      <span class="taxa-rentabilidade">{taxa}</span>
      <span class="prazo-dias">{prazo}</span>
      <span class="valor-minimo">{valor_min}</span>
      <span class="liquidez-diaria">{liquidez}</span>
    </div>
    """


def _inter_html(
    emissor: str = "Banco Gamma S.A.",
    taxa: str = "12,5% a.a.",
    prazo: str = "180 dias",
    valor_min: str = "R$ 100,00",
    liquidez: str = "diária",
) -> str:
    return f"""
    <div class="InvestmentCard">
      <span class="issuer">{emissor}</span>
      <span class="rate">{taxa}</span>
      <span class="term">{prazo}</span>
      <span class="minValue">{valor_min}</span>
      <span class="liquidity">{liquidez}</span>
    </div>
    """


def _rico_html(
    emissor: str = "Banco Delta S.A.",
    taxa: str = "CDI + 2,0%",
    prazo: str = "1 ano",
    valor_min: str = "R$ 1.000",
    liquidez: str = "No vencimento",
) -> str:
    return f"""
    <div data-testid="product-card">
      <span class="emissor-nome">{emissor}</span>
      <span class="taxa-rentabilidade">{taxa}</span>
      <span class="prazo-dias">{prazo}</span>
      <span class="valor-minimo">{valor_min}</span>
      <span class="liquidez-diaria">{liquidez}</span>
    </div>
    """


# ---------------------------------------------------------------------------
# BTGCollector._parse
# ---------------------------------------------------------------------------


class TestBTGParse:
    def setup_method(self):
        self.parser = BTGCollector()

    def test_html_vazio_retorna_lista_vazia(self):
        assert self.parser._parse("") == []

    def test_html_sem_cards_retorna_lista_vazia(self):
        assert self.parser._parse("<html><body><p>sem cards</p></body></html>") == []

    def test_card_cdi_retorna_oferta(self):
        ofertas = self.parser._parse(_btg_html(taxa="120% CDI"))
        assert len(ofertas) == 1
        o = ofertas[0]
        assert o.indexador == Indexador.CDI
        assert o.percentual == Decimal("120")
        assert o.emissor_nome == "Banco Alpha S.A."
        assert o.prazo_dias == 365
        assert o.fonte == "btg"

    def test_card_prefixado_retorna_oferta(self):
        ofertas = self.parser._parse(_btg_html(taxa="13,5% a.a.", prazo="360 dias"))
        assert len(ofertas) == 1
        assert ofertas[0].indexador == Indexador.PREFIXADO
        assert ofertas[0].percentual == Decimal("13.5")

    def test_card_ipca_retorna_oferta(self):
        ofertas = self.parser._parse(_btg_html(taxa="IPCA + 6,5%", prazo="2 anos"))
        assert len(ofertas) == 1
        assert ofertas[0].indexador == Indexador.IPCA
        assert ofertas[0].taxa_adicional == Decimal("6.5")
        assert ofertas[0].prazo_dias == 720

    def test_liquidez_diaria_detectada(self):
        ofertas = self.parser._parse(_btg_html(liquidez="D+0 diária"))
        assert len(ofertas) == 1
        assert ofertas[0].liquidez_diaria is True

    def test_sem_liquidez_diaria(self):
        ofertas = self.parser._parse(_btg_html(liquidez="No vencimento"))
        assert len(ofertas) == 1
        assert ofertas[0].liquidez_diaria is False

    def test_valor_minimo_parseado(self):
        ofertas = self.parser._parse(_btg_html(valor_min="R$ 1.000,00"))
        assert len(ofertas) == 1
        assert ofertas[0].valor_minimo == Decimal("1000.00")

    def test_card_sem_taxa_ignorado(self):
        html = """
        <div class="FixedIncomeCard">
          <span class="issuer">Banco X</span>
          <span class="term">365 dias</span>
        </div>
        """
        assert self.parser._parse(html) == []

    def test_card_prazo_zero_ignorado(self):
        html = """
        <div class="FixedIncomeCard">
          <span class="issuer">Banco X</span>
          <span class="rate">120% CDI</span>
          <span class="term">sem prazo</span>
        </div>
        """
        assert self.parser._parse(html) == []

    def test_multiplos_cards(self):
        html = _btg_html() + _btg_html(emissor="Banco Y", taxa="115% CDI")
        ofertas = self.parser._parse(html)
        assert len(ofertas) == 2


# ---------------------------------------------------------------------------
# XPCollector._parse
# ---------------------------------------------------------------------------


class TestXPParse:
    def setup_method(self):
        self.parser = XPCollector()

    def test_html_vazio_retorna_lista_vazia(self):
        assert self.parser._parse("") == []

    def test_card_ipca_retorna_oferta(self):
        ofertas = self.parser._parse(_xp_html())
        assert len(ofertas) == 1
        o = ofertas[0]
        assert o.indexador == Indexador.IPCA
        assert o.taxa_adicional == Decimal("6.5")
        assert o.emissor_nome == "Banco Beta S.A."
        assert o.fonte == "xp"

    def test_card_cdi_retorna_oferta(self):
        ofertas = self.parser._parse(_xp_html(taxa="110% CDI", prazo="365 dias"))
        assert len(ofertas) == 1
        assert ofertas[0].indexador == Indexador.CDI
        assert ofertas[0].percentual == Decimal("110")

    def test_prazo_em_meses(self):
        ofertas = self.parser._parse(_xp_html(prazo="6 meses"))
        assert len(ofertas) == 1
        assert ofertas[0].prazo_dias == 180

    def test_liquidez_diaria_por_texto(self):
        ofertas = self.parser._parse(_xp_html(liquidez="Liquidez diária"))
        assert len(ofertas) == 1
        assert ofertas[0].liquidez_diaria is True

    def test_multiplos_cards(self):
        html = _xp_html() + _xp_html(emissor="Banco Z", taxa="100% CDI", prazo="90 dias")
        assert len(self.parser._parse(html)) == 2


# ---------------------------------------------------------------------------
# InterCollector._parse
# ---------------------------------------------------------------------------


class TestInterParse:
    def setup_method(self):
        self.parser = InterCollector()

    def test_html_vazio_retorna_lista_vazia(self):
        assert self.parser._parse("") == []

    def test_card_prefixado_retorna_oferta(self):
        ofertas = self.parser._parse(_inter_html())
        assert len(ofertas) == 1
        o = ofertas[0]
        assert o.indexador == Indexador.PREFIXADO
        assert o.percentual == Decimal("12.5")
        assert o.emissor_nome == "Banco Gamma S.A."
        assert o.fonte == "inter"

    def test_card_cdi_puro(self):
        ofertas = self.parser._parse(_inter_html(taxa="125% CDI", prazo="720 dias"))
        assert len(ofertas) == 1
        assert ofertas[0].indexador == Indexador.CDI
        assert ofertas[0].prazo_dias == 720

    def test_liquidez_diaria_detectada(self):
        ofertas = self.parser._parse(_inter_html(liquidez="Liquidez diária"))
        assert len(ofertas) == 1
        assert ofertas[0].liquidez_diaria is True

    def test_card_sem_emissor_ignorado(self):
        html = """
        <div class="InvestmentCard">
          <span class="rate">120% CDI</span>
          <span class="term">365 dias</span>
        </div>
        """
        assert self.parser._parse(html) == []


# ---------------------------------------------------------------------------
# RicoCollector._parse
# ---------------------------------------------------------------------------


class TestRicoParse:
    def setup_method(self):
        self.parser = RicoCollector()

    def test_html_vazio_retorna_lista_vazia(self):
        assert self.parser._parse("") == []

    def test_card_cdi_spread_retorna_oferta(self):
        ofertas = self.parser._parse(_rico_html())
        assert len(ofertas) == 1
        o = ofertas[0]
        assert o.indexador == Indexador.CDI
        assert o.percentual == Decimal("100")
        assert o.taxa_adicional == Decimal("2.0")
        assert o.emissor_nome == "Banco Delta S.A."
        assert o.fonte == "rico"

    def test_card_selic_puro(self):
        ofertas = self.parser._parse(_rico_html(taxa="100% da Selic", prazo="365 dias"))
        assert len(ofertas) == 1
        assert ofertas[0].indexador == Indexador.SELIC
        assert ofertas[0].percentual == Decimal("100")

    def test_prazo_em_anos(self):
        ofertas = self.parser._parse(_rico_html(prazo="2 anos"))
        assert len(ofertas) == 1
        assert ofertas[0].prazo_dias == 720

    def test_multiplos_cards(self):
        html = _rico_html() + _rico_html(emissor="Banco E", taxa="130% CDI", prazo="180 dias")
        assert len(self.parser._parse(html)) == 2

    def test_card_sem_prazo_ignorado(self):
        html = """
        <div data-testid="product-card">
          <span class="emissor-nome">Banco F</span>
          <span class="taxa-rentabilidade">110% CDI</span>
        </div>
        """
        assert self.parser._parse(html) == []
