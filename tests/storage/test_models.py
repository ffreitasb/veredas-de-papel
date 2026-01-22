"""
Testes dos modelos SQLAlchemy.

Verifica criação, relacionamentos e propriedades dos modelos.
"""

from datetime import date, datetime
from decimal import Decimal

import pytest
from sqlalchemy.orm import Session

from veredas.storage.models import (
    Anomalia,
    EventoRegulatorio,
    Indexador,
    InstituicaoFinanceira,
    Segmento,
    Severidade,
    TaxaCDB,
    TaxaReferencia,
    TipoAnomalia,
    TipoEvento,
)


class TestInstituicaoFinanceira:
    """Testes do modelo InstituicaoFinanceira."""

    def test_criar_instituicao(self, db_session: Session):
        """Deve criar uma instituição financeira."""
        inst = InstituicaoFinanceira(
            cnpj="12.345.678/0001-90",
            nome="Banco Teste S.A.",
            segmento=Segmento.BANCO_MULTIPLO,
        )
        db_session.add(inst)
        db_session.commit()

        assert inst.id is not None
        assert inst.cnpj == "12.345.678/0001-90"
        assert inst.nome == "Banco Teste S.A."
        assert inst.segmento == Segmento.BANCO_MULTIPLO
        assert inst.ativa is True

    def test_instituicao_com_indicadores(self, instituicao_exemplo: InstituicaoFinanceira):
        """Deve armazenar indicadores de saúde financeira."""
        assert instituicao_exemplo.indice_basileia == Decimal("15.5")
        assert instituicao_exemplo.indice_liquidez == Decimal("120.0")
        assert instituicao_exemplo.ativo_total == Decimal("1000000000.00")

    def test_instituicao_repr(self, instituicao_exemplo: InstituicaoFinanceira):
        """Deve ter representação string legível."""
        repr_str = repr(instituicao_exemplo)
        assert "Banco Exemplo" in repr_str
        assert "00.000.000/0001-00" in repr_str

    def test_relacionamento_taxas(
        self,
        db_session: Session,
        instituicao_exemplo: InstituicaoFinanceira,
        taxa_cdb_normal: TaxaCDB,
    ):
        """Deve ter relacionamento com taxas de CDB."""
        db_session.refresh(instituicao_exemplo)
        assert len(instituicao_exemplo.taxas) == 1
        assert instituicao_exemplo.taxas[0].id == taxa_cdb_normal.id


class TestTaxaCDB:
    """Testes do modelo TaxaCDB."""

    def test_criar_taxa_cdi(self, db_session: Session, instituicao_exemplo: InstituicaoFinanceira):
        """Deve criar uma taxa indexada ao CDI."""
        taxa = TaxaCDB(
            if_id=instituicao_exemplo.id,
            data_coleta=datetime.now(),
            indexador=Indexador.CDI,
            percentual=Decimal("115.0"),
            prazo_dias=365,
            fonte="teste",
        )
        db_session.add(taxa)
        db_session.commit()

        assert taxa.id is not None
        assert taxa.indexador == Indexador.CDI
        assert taxa.percentual == Decimal("115.0")

    def test_criar_taxa_ipca(self, db_session: Session, instituicao_exemplo: InstituicaoFinanceira):
        """Deve criar uma taxa IPCA+."""
        taxa = TaxaCDB(
            if_id=instituicao_exemplo.id,
            data_coleta=datetime.now(),
            indexador=Indexador.IPCA,
            percentual=Decimal("100.0"),
            taxa_adicional=Decimal("6.5"),  # IPCA + 6.5%
            prazo_dias=730,
            fonte="teste",
        )
        db_session.add(taxa)
        db_session.commit()

        assert taxa.indexador == Indexador.IPCA
        assert taxa.taxa_adicional == Decimal("6.5")

    def test_spread_cdi_property(self, taxa_cdb_normal: TaxaCDB):
        """Deve calcular spread em relação ao CDI."""
        assert taxa_cdb_normal.spread_cdi == Decimal("10.0")  # 110 - 100

    def test_spread_cdi_none_para_ipca(self, taxa_cdb_ipca_alto: TaxaCDB):
        """Spread CDI deve ser None para taxas IPCA."""
        assert taxa_cdb_ipca_alto.spread_cdi is None

    def test_taxa_repr(self, taxa_cdb_normal: TaxaCDB):
        """Deve ter representação string legível."""
        repr_str = repr(taxa_cdb_normal)
        assert "110" in repr_str
        assert "cdi" in repr_str.lower()

    def test_relacionamento_instituicao(
        self, taxa_cdb_normal: TaxaCDB, instituicao_exemplo: InstituicaoFinanceira
    ):
        """Deve ter relacionamento com instituição."""
        assert taxa_cdb_normal.instituicao.id == instituicao_exemplo.id


class TestAnomalia:
    """Testes do modelo Anomalia."""

    def test_criar_anomalia(
        self,
        db_session: Session,
        instituicao_risco: InstituicaoFinanceira,
        taxa_cdb_spread_critico: TaxaCDB,
    ):
        """Deve criar uma anomalia."""
        anomalia = Anomalia(
            if_id=instituicao_risco.id,
            taxa_id=taxa_cdb_spread_critico.id,
            tipo=TipoAnomalia.SPREAD_CRITICO,
            severidade=Severidade.CRITICAL,
            valor_detectado=Decimal("165.0"),
            descricao="Teste de anomalia",
            detectado_em=datetime.now(),
        )
        db_session.add(anomalia)
        db_session.commit()

        assert anomalia.id is not None
        assert anomalia.tipo == TipoAnomalia.SPREAD_CRITICO
        assert anomalia.severidade == Severidade.CRITICAL
        assert anomalia.resolvido is False

    def test_anomalia_resolvida(self, db_session: Session, anomalia_exemplo: Anomalia):
        """Deve marcar anomalia como resolvida."""
        anomalia_exemplo.resolvido = True
        anomalia_exemplo.resolvido_em = datetime.now()
        anomalia_exemplo.notas_resolucao = "Banco foi liquidado"
        db_session.commit()

        assert anomalia_exemplo.resolvido is True
        assert anomalia_exemplo.resolvido_em is not None

    def test_anomalia_repr(self, anomalia_exemplo: Anomalia):
        """Deve ter representação string legível."""
        repr_str = repr(anomalia_exemplo)
        assert "spread_critico" in repr_str.lower()
        assert "critical" in repr_str.lower()


class TestTaxaReferencia:
    """Testes do modelo TaxaReferencia."""

    def test_criar_taxa_selic(self, db_session: Session):
        """Deve criar taxa Selic."""
        taxa = TaxaReferencia(
            data=date.today(),
            tipo="selic",
            valor=Decimal("13.75"),
            fonte="bcb",
        )
        db_session.add(taxa)
        db_session.commit()

        assert taxa.id is not None
        assert taxa.tipo == "selic"
        assert taxa.valor == Decimal("13.75")

    def test_taxa_referencia_repr(self, taxa_referencia_selic: TaxaReferencia):
        """Deve ter representação string legível."""
        repr_str = repr(taxa_referencia_selic)
        assert "selic" in repr_str.lower()


class TestEventoRegulatorio:
    """Testes do modelo EventoRegulatorio."""

    def test_criar_evento(self, db_session: Session):
        """Deve criar evento regulatório."""
        evento = EventoRegulatorio(
            if_nome="Banco XYZ",
            tipo=TipoEvento.INTERVENCAO,
            data_evento=date(2024, 1, 15),
            descricao="Intervenção do BC",
            fonte="https://bcb.gov.br/",
        )
        db_session.add(evento)
        db_session.commit()

        assert evento.id is not None
        assert evento.tipo == TipoEvento.INTERVENCAO

    def test_evento_com_sinais(self, evento_liquidacao: EventoRegulatorio):
        """Deve armazenar sinais detectados antes do evento."""
        assert evento_liquidacao.sinais_detectados is not None
        assert "SPREAD_CRITICO" in evento_liquidacao.sinais_detectados

    def test_evento_repr(self, evento_liquidacao: EventoRegulatorio):
        """Deve ter representação string legível."""
        repr_str = repr(evento_liquidacao)
        assert "liquidacao" in repr_str.lower()
        assert "Banco Master" in repr_str


class TestEnums:
    """Testes dos enums."""

    def test_segmentos(self):
        """Deve ter todos os segmentos esperados."""
        assert Segmento.BANCO_COMERCIAL == "banco_comercial"
        assert Segmento.BANCO_MULTIPLO == "banco_multiplo"
        assert Segmento.FINANCEIRA == "financeira"

    def test_indexadores(self):
        """Deve ter todos os indexadores esperados."""
        assert Indexador.CDI == "cdi"
        assert Indexador.IPCA == "ipca"
        assert Indexador.PREFIXADO == "pre"

    def test_severidades(self):
        """Deve ter todas as severidades esperadas."""
        assert Severidade.LOW == "low"
        assert Severidade.MEDIUM == "medium"
        assert Severidade.HIGH == "high"
        assert Severidade.CRITICAL == "critical"

    def test_tipos_anomalia(self):
        """Deve ter todos os tipos de anomalia esperados."""
        assert TipoAnomalia.SPREAD_ALTO == "spread_alto"
        assert TipoAnomalia.SPREAD_CRITICO == "spread_critico"
        assert TipoAnomalia.SALTO_BRUSCO == "salto_brusco"
