"""
Testes dos repositórios de acesso a dados.

Verifica operações CRUD e queries dos repositórios.
"""

from datetime import date, datetime, timedelta
from decimal import Decimal

import pytest
from sqlalchemy.orm import Session

from veredas.storage.models import (
    Indexador,
    InstituicaoFinanceira,
    Severidade,
    TaxaCDB,
    TipoAnomalia,
)
from veredas.storage.repository import (
    AnomaliaRepository,
    InstituicaoRepository,
    TaxaCDBRepository,
    TaxaReferenciaRepository,
)


class TestInstituicaoRepository:
    """Testes do repositório de instituições financeiras."""

    def test_create(self, db_session: Session):
        """Deve criar uma instituição."""
        repo = InstituicaoRepository(db_session)
        inst = repo.create(
            cnpj="99.999.999/0001-99",
            nome="Banco Novo S.A.",
        )
        db_session.commit()

        assert inst.id is not None
        assert inst.cnpj == "99.999.999/0001-99"

    def test_get_by_id(self, db_session: Session, instituicao_exemplo: InstituicaoFinanceira):
        """Deve buscar instituição por ID."""
        repo = InstituicaoRepository(db_session)
        found = repo.get_by_id(instituicao_exemplo.id)

        assert found is not None
        assert found.id == instituicao_exemplo.id

    def test_get_by_id_not_found(self, db_session: Session):
        """Deve retornar None se não encontrar."""
        repo = InstituicaoRepository(db_session)
        found = repo.get_by_id(99999)

        assert found is None

    def test_get_by_cnpj(self, db_session: Session, instituicao_exemplo: InstituicaoFinanceira):
        """Deve buscar instituição por CNPJ."""
        repo = InstituicaoRepository(db_session)
        found = repo.get_by_cnpj(instituicao_exemplo.cnpj)

        assert found is not None
        assert found.cnpj == instituicao_exemplo.cnpj

    def test_get_by_nome(self, db_session: Session, instituicao_exemplo: InstituicaoFinanceira):
        """Deve buscar instituição por nome parcial."""
        repo = InstituicaoRepository(db_session)
        found = repo.get_by_nome("Exemplo")

        assert found is not None
        assert "Exemplo" in found.nome

    def test_list_all(
        self,
        db_session: Session,
        instituicao_exemplo: InstituicaoFinanceira,
        instituicao_risco: InstituicaoFinanceira,
    ):
        """Deve listar todas as instituições ativas."""
        repo = InstituicaoRepository(db_session)
        all_inst = repo.list_all()

        assert len(all_inst) == 2

    def test_list_all_incluindo_inativas(
        self,
        db_session: Session,
        instituicao_exemplo: InstituicaoFinanceira,
    ):
        """Deve poder incluir instituições inativas."""
        # Desativar instituição
        instituicao_exemplo.ativa = False
        db_session.commit()

        repo = InstituicaoRepository(db_session)

        # Sem inativas
        ativas = repo.list_all(ativas_only=True)
        assert len(ativas) == 0

        # Com inativas
        todas = repo.list_all(ativas_only=False)
        assert len(todas) == 1

    def test_upsert_create(self, db_session: Session):
        """Deve criar se não existir."""
        repo = InstituicaoRepository(db_session)
        inst = repo.upsert(
            cnpj="88.888.888/0001-88",
            nome="Banco Upsert S.A.",
        )
        db_session.commit()

        assert inst.id is not None
        assert inst.nome == "Banco Upsert S.A."

    def test_upsert_update(self, db_session: Session, instituicao_exemplo: InstituicaoFinanceira):
        """Deve atualizar se existir."""
        repo = InstituicaoRepository(db_session)
        inst = repo.upsert(
            cnpj=instituicao_exemplo.cnpj,
            nome="Nome Atualizado",
        )
        db_session.commit()

        assert inst.id == instituicao_exemplo.id
        assert inst.nome == "Nome Atualizado"


class TestTaxaCDBRepository:
    """Testes do repositório de taxas de CDB."""

    def test_create(self, db_session: Session, instituicao_exemplo: InstituicaoFinanceira):
        """Deve criar uma taxa."""
        repo = TaxaCDBRepository(db_session)
        taxa = repo.create(
            if_id=instituicao_exemplo.id,
            data_coleta=datetime.now(),
            indexador=Indexador.CDI,
            percentual=Decimal("112.0"),
            prazo_dias=365,
            fonte="teste",
        )
        db_session.commit()

        assert taxa.id is not None

    def test_get_by_id(self, db_session: Session, taxa_cdb_normal: TaxaCDB):
        """Deve buscar taxa por ID."""
        repo = TaxaCDBRepository(db_session)
        found = repo.get_by_id(taxa_cdb_normal.id)

        assert found is not None
        assert found.id == taxa_cdb_normal.id

    def test_list_by_if(
        self,
        db_session: Session,
        instituicao_exemplo: InstituicaoFinanceira,
        taxa_cdb_normal: TaxaCDB,
    ):
        """Deve listar taxas de uma instituição."""
        repo = TaxaCDBRepository(db_session)
        taxas = repo.list_by_if(instituicao_exemplo.id)

        assert len(taxas) == 1
        assert taxas[0].id == taxa_cdb_normal.id

    def test_list_recent(
        self,
        db_session: Session,
        taxa_cdb_normal: TaxaCDB,
        taxa_cdb_spread_alto: TaxaCDB,
    ):
        """Deve listar taxas recentes."""
        repo = TaxaCDBRepository(db_session)
        recentes = repo.list_recent(dias=7)

        assert len(recentes) == 2

    def test_list_recent_por_indexador(
        self,
        db_session: Session,
        taxa_cdb_normal: TaxaCDB,
        taxa_cdb_ipca_alto: TaxaCDB,
    ):
        """Deve filtrar por indexador."""
        repo = TaxaCDBRepository(db_session)

        cdi_taxas = repo.list_recent(dias=7, indexador="cdi")
        assert len(cdi_taxas) == 1
        assert cdi_taxas[0].indexador == Indexador.CDI

    def test_bulk_create(self, db_session: Session, instituicao_exemplo: InstituicaoFinanceira):
        """Deve criar múltiplas taxas."""
        repo = TaxaCDBRepository(db_session)
        taxas_data = [
            {
                "if_id": instituicao_exemplo.id,
                "data_coleta": datetime.now(),
                "indexador": Indexador.CDI,
                "percentual": Decimal("110.0"),
                "prazo_dias": 365,
                "fonte": "teste",
            },
            {
                "if_id": instituicao_exemplo.id,
                "data_coleta": datetime.now(),
                "indexador": Indexador.CDI,
                "percentual": Decimal("112.0"),
                "prazo_dias": 730,
                "fonte": "teste",
            },
        ]

        taxas = repo.bulk_create(taxas_data)
        db_session.commit()

        assert len(taxas) == 2


class TestAnomaliaRepository:
    """Testes do repositório de anomalias."""

    def test_create(
        self,
        db_session: Session,
        instituicao_risco: InstituicaoFinanceira,
    ):
        """Deve criar uma anomalia."""
        repo = AnomaliaRepository(db_session)
        anomalia = repo.create(
            if_id=instituicao_risco.id,
            tipo=TipoAnomalia.SPREAD_ALTO,
            severidade=Severidade.HIGH,
            valor_detectado=Decimal("140.0"),
            descricao="Teste de anomalia",
        )
        db_session.commit()

        assert anomalia.id is not None
        assert anomalia.detectado_em is not None

    def test_list_ativas(self, db_session: Session, anomalia_exemplo):
        """Deve listar anomalias não resolvidas."""
        repo = AnomaliaRepository(db_session)
        ativas = repo.list_ativas()

        assert len(ativas) == 1
        assert ativas[0].resolvido is False

    def test_list_ativas_por_severidade(
        self,
        db_session: Session,
        instituicao_risco: InstituicaoFinanceira,
    ):
        """Deve filtrar por severidade mínima."""
        repo = AnomaliaRepository(db_session)

        # Criar anomalias de diferentes severidades
        repo.create(
            if_id=instituicao_risco.id,
            tipo=TipoAnomalia.SALTO_BRUSCO,
            severidade=Severidade.MEDIUM,
            valor_detectado=Decimal("15.0"),
            descricao="Anomalia MEDIUM",
        )
        repo.create(
            if_id=instituicao_risco.id,
            tipo=TipoAnomalia.SPREAD_CRITICO,
            severidade=Severidade.CRITICAL,
            valor_detectado=Decimal("160.0"),
            descricao="Anomalia CRITICAL",
        )
        db_session.commit()

        # Filtrar por HIGH ou acima
        high_or_above = repo.list_ativas(severidade_minima=Severidade.HIGH)
        assert len(high_or_above) == 1
        assert high_or_above[0].severidade == Severidade.CRITICAL

    def test_list_by_if(
        self,
        db_session: Session,
        anomalia_exemplo,
        instituicao_risco: InstituicaoFinanceira,
    ):
        """Deve listar anomalias de uma instituição."""
        repo = AnomaliaRepository(db_session)
        anomalias = repo.list_by_if(instituicao_risco.id)

        assert len(anomalias) == 1

    def test_resolver(self, db_session: Session, anomalia_exemplo):
        """Deve resolver anomalia."""
        repo = AnomaliaRepository(db_session)
        resolved = repo.resolver(
            anomalia_exemplo.id,
            notas="Resolvido pelo teste",
        )
        db_session.commit()

        assert resolved is not None
        assert resolved.resolvido is True
        assert resolved.notas_resolucao == "Resolvido pelo teste"


class TestTaxaReferenciaRepository:
    """Testes do repositório de taxas de referência."""

    def test_create(self, db_session: Session):
        """Deve criar taxa de referência."""
        repo = TaxaReferenciaRepository(db_session)
        taxa = repo.create(
            data=date.today(),
            tipo="selic",
            valor=Decimal("14.25"),
            fonte="bcb",
        )
        db_session.commit()

        assert taxa.id is not None

    def test_get_ultima(self, db_session: Session, taxa_referencia_selic):
        """Deve buscar última taxa de um tipo."""
        repo = TaxaReferenciaRepository(db_session)
        ultima = repo.get_ultima("selic")

        assert ultima is not None
        assert ultima.tipo == "selic"

    def test_get_por_data(self, db_session: Session, taxa_referencia_selic):
        """Deve buscar taxa por data específica."""
        repo = TaxaReferenciaRepository(db_session)
        taxa = repo.get_por_data("selic", date.today())

        assert taxa is not None

    def test_upsert_create(self, db_session: Session):
        """Deve criar se não existir."""
        repo = TaxaReferenciaRepository(db_session)
        taxa = repo.upsert(
            tipo="ipca",
            data=date.today(),
            valor=Decimal("0.45"),
            fonte="bcb",
        )
        db_session.commit()

        assert taxa.id is not None
        assert taxa.valor == Decimal("0.45")

    def test_upsert_update(self, db_session: Session, taxa_referencia_selic):
        """Deve atualizar se existir."""
        repo = TaxaReferenciaRepository(db_session)
        taxa = repo.upsert(
            tipo="selic",
            data=date.today(),
            valor=Decimal("14.00"),  # Valor atualizado
        )
        db_session.commit()

        assert taxa.id == taxa_referencia_selic.id
        assert taxa.valor == Decimal("14.00")

    def test_list_historico(self, db_session: Session):
        """Deve listar histórico de taxas."""
        repo = TaxaReferenciaRepository(db_session)

        # Criar várias taxas
        for i in range(5):
            repo.create(
                data=date.today() - timedelta(days=i),
                tipo="selic",
                valor=Decimal(f"13.{75 - i}"),
                fonte="bcb",
            )
        db_session.commit()

        historico = repo.list_historico("selic", dias=10)
        assert len(historico) == 5
