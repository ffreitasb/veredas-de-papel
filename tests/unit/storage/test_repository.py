"""Testes unitários para repositórios SQLAlchemy."""

from datetime import date, datetime, timedelta
from decimal import Decimal

from veredas.storage.models import (
    Indexador,
    InstituicaoFinanceira,
    Severidade,
    TipoAnomalia,
)
from veredas.storage.repository import (
    AnomaliaRepository,
    InstituicaoRepository,
    TaxaCDBRepository,
    TaxaReferenciaRepository,
)

# ---------------------------------------------------------------------------
# InstituicaoRepository
# ---------------------------------------------------------------------------


class TestInstituicaoRepository:
    def setup_method(self):
        pass

    def _make_if(self, session, nome="Banco Teste", cnpj="00.000.000/0001-00", ativa=True):
        repo = InstituicaoRepository(session)
        return repo.create(nome=nome, cnpj=cnpj, ativa=ativa)

    def test_create_e_get_by_id(self, db_session):
        repo = InstituicaoRepository(db_session)
        if_ = repo.create(nome="Banco Alpha", cnpj="11.111.111/0001-11", ativa=True)
        db_session.commit()

        found = repo.get_by_id(if_.id)
        assert found is not None
        assert found.nome == "Banco Alpha"

    def test_get_by_id_inexistente_retorna_none(self, db_session):
        repo = InstituicaoRepository(db_session)
        assert repo.get_by_id(9999) is None

    def test_get_by_cnpj(self, db_session):
        repo = InstituicaoRepository(db_session)
        repo.create(nome="Banco Beta", cnpj="22.222.222/0001-22", ativa=True)
        db_session.commit()

        found = repo.get_by_cnpj("22.222.222/0001-22")
        assert found is not None
        assert found.nome == "Banco Beta"

    def test_get_by_cnpj_inexistente(self, db_session):
        repo = InstituicaoRepository(db_session)
        assert repo.get_by_cnpj("99.999.999/0001-99") is None

    def test_list_all_apenas_ativas(self, db_session):
        repo = InstituicaoRepository(db_session)
        repo.create(nome="Banco Ativo", cnpj="33.333.333/0001-33", ativa=True)
        repo.create(nome="Banco Inativo", cnpj="44.444.444/0001-44", ativa=False)
        db_session.commit()

        lista = repo.list_all(ativas_only=True)
        nomes = [i.nome for i in lista]
        assert "Banco Ativo" in nomes
        assert "Banco Inativo" not in nomes

    def test_list_all_inclui_inativas(self, db_session):
        repo = InstituicaoRepository(db_session)
        repo.create(nome="Banco X", cnpj="55.555.555/0001-55", ativa=True)
        repo.create(nome="Banco Y", cnpj="66.666.666/0001-66", ativa=False)
        db_session.commit()

        lista = repo.list_all(ativas_only=False)
        assert len(lista) >= 2

    def test_count_apenas_ativas(self, db_session):
        repo = InstituicaoRepository(db_session)
        repo.create(nome="C1", cnpj="77.777.777/0001-77", ativa=True)
        repo.create(nome="C2", cnpj="88.888.888/0001-88", ativa=False)
        db_session.commit()

        assert repo.count() == 1

    def test_upsert_cria_nova(self, db_session):
        repo = InstituicaoRepository(db_session)
        if_ = repo.upsert(cnpj="12.345.678/0001-99", nome="Banco Upsert", ativa=True)
        db_session.commit()

        assert if_.id is not None
        assert if_.nome == "Banco Upsert"

    def test_upsert_atualiza_existente(self, db_session):
        repo = InstituicaoRepository(db_session)
        repo.create(nome="Banco Original", cnpj="98.765.432/0001-00", ativa=True)
        db_session.commit()

        updated = repo.upsert(cnpj="98.765.432/0001-00", nome="Banco Atualizado")
        db_session.commit()

        assert updated.nome == "Banco Atualizado"
        assert repo.count() == 1


# ---------------------------------------------------------------------------
# TaxaCDBRepository
# ---------------------------------------------------------------------------


class TestTaxaCDBRepository:
    def _seed_if(self, session) -> InstituicaoFinanceira:
        repo = InstituicaoRepository(session)
        if_ = repo.create(nome="Banco Seed", cnpj="00.111.222/0001-33", ativa=True)
        session.commit()
        return if_

    def test_create_e_get_by_id(self, db_session):
        if_ = self._seed_if(db_session)
        repo = TaxaCDBRepository(db_session)
        taxa = repo.create(
            if_id=if_.id,
            data_coleta=datetime.now(),
            indexador=Indexador.CDI,
            percentual=Decimal("110.0"),
            prazo_dias=365,
            fonte="test",
        )
        db_session.commit()

        found = repo.get_by_id(taxa.id)
        assert found is not None
        assert found.percentual == Decimal("110.0")

    def test_list_by_if(self, db_session):
        if_ = self._seed_if(db_session)
        repo = TaxaCDBRepository(db_session)
        for i in range(5):
            repo.create(
                if_id=if_.id,
                data_coleta=datetime.now() - timedelta(days=i),
                indexador=Indexador.CDI,
                percentual=Decimal(f"{100 + i}.0"),
                prazo_dias=365,
                fonte="test",
            )
        db_session.commit()

        taxas = repo.list_by_if(if_.id)
        assert len(taxas) == 5

    def test_count(self, db_session):
        if_ = self._seed_if(db_session)
        repo = TaxaCDBRepository(db_session)
        assert repo.count() == 0

        repo.create(
            if_id=if_.id,
            data_coleta=datetime.now(),
            indexador=Indexador.CDI,
            percentual=Decimal("105.0"),
            prazo_dias=180,
            fonte="test",
        )
        db_session.commit()

        assert repo.count() == 1

    def test_count_distinct_ifs(self, db_session):
        repo_if = InstituicaoRepository(db_session)
        if1 = repo_if.create(nome="IF1", cnpj="01.001.001/0001-01", ativa=True)
        if2 = repo_if.create(nome="IF2", cnpj="02.002.002/0001-02", ativa=True)
        db_session.commit()

        repo = TaxaCDBRepository(db_session)
        repo.create(
            if_id=if1.id,
            data_coleta=datetime.now(),
            indexador=Indexador.CDI,
            percentual=Decimal("100.0"),
            prazo_dias=365,
            fonte="test",
        )
        repo.create(
            if_id=if1.id,
            data_coleta=datetime.now(),
            indexador=Indexador.CDI,
            percentual=Decimal("101.0"),
            prazo_dias=365,
            fonte="test",
        )
        repo.create(
            if_id=if2.id,
            data_coleta=datetime.now(),
            indexador=Indexador.CDI,
            percentual=Decimal("102.0"),
            prazo_dias=365,
            fonte="test",
        )
        db_session.commit()

        assert repo.count_distinct_ifs() == 2

    def test_bulk_create(self, db_session):
        if_ = self._seed_if(db_session)
        repo = TaxaCDBRepository(db_session)
        taxas_data = [
            {
                "if_id": if_.id,
                "data_coleta": datetime.now() - timedelta(days=i),
                "indexador": Indexador.CDI,
                "percentual": Decimal(f"{100 + i}.0"),
                "prazo_dias": 365,
                "fonte": "test",
            }
            for i in range(10)
        ]
        criadas = repo.bulk_create(taxas_data)
        db_session.commit()

        assert len(criadas) == 10
        assert repo.count() == 10

    def test_list_paginated_com_filtro_indexador(self, db_session):
        if_ = self._seed_if(db_session)
        repo = TaxaCDBRepository(db_session)
        repo.create(
            if_id=if_.id,
            data_coleta=datetime.now(),
            indexador=Indexador.CDI,
            percentual=Decimal("110.0"),
            prazo_dias=365,
            fonte="test",
        )
        repo.create(
            if_id=if_.id,
            data_coleta=datetime.now(),
            indexador=Indexador.IPCA,
            percentual=Decimal("108.0"),
            prazo_dias=365,
            taxa_adicional=Decimal("8.0"),
            fonte="test",
        )
        db_session.commit()

        taxas, total = repo.list_paginated(filters={"indexador": Indexador.CDI})
        assert total == 1
        assert taxas[0].indexador == Indexador.CDI


# ---------------------------------------------------------------------------
# AnomaliaRepository
# ---------------------------------------------------------------------------


class TestAnomaliaRepository:
    def _seed_if(self, session) -> InstituicaoFinanceira:
        repo = InstituicaoRepository(session)
        if_ = repo.create(nome="Banco Anomalia", cnpj="10.203.040/0001-50", ativa=True)
        session.commit()
        return if_

    def _create_anomalia(self, session, if_id, severidade=Severidade.HIGH, resolvido=False):
        repo = AnomaliaRepository(session)
        a = repo.create(
            if_id=if_id,
            tipo=TipoAnomalia.SPREAD_ALTO,
            severidade=severidade,
            valor_detectado=Decimal("140.0"),
            descricao="Spread alto detectado",
        )
        if resolvido:
            a.resolvido = True
        session.commit()
        return a

    def test_create_e_get_by_id(self, db_session):
        if_ = self._seed_if(db_session)
        anomalia = self._create_anomalia(db_session, if_.id)

        repo = AnomaliaRepository(db_session)
        found = repo.get_by_id(anomalia.id)
        assert found is not None
        assert found.tipo == TipoAnomalia.SPREAD_ALTO

    def test_list_ativas_exclui_resolvidas(self, db_session):
        if_ = self._seed_if(db_session)
        self._create_anomalia(db_session, if_.id, resolvido=False)
        self._create_anomalia(db_session, if_.id, resolvido=True)

        repo = AnomaliaRepository(db_session)
        ativas = repo.list_ativas()
        assert len(ativas) == 1
        assert not ativas[0].resolvido

    def test_count_active(self, db_session):
        if_ = self._seed_if(db_session)
        self._create_anomalia(db_session, if_.id)
        self._create_anomalia(db_session, if_.id)

        repo = AnomaliaRepository(db_session)
        assert repo.count_active() == 2

    def test_count_by_severity(self, db_session):
        if_ = self._seed_if(db_session)
        self._create_anomalia(db_session, if_.id, severidade=Severidade.CRITICAL)
        self._create_anomalia(db_session, if_.id, severidade=Severidade.HIGH)

        repo = AnomaliaRepository(db_session)
        assert repo.count_by_severity(Severidade.CRITICAL) == 1
        assert repo.count_by_severity(Severidade.HIGH) == 1
        assert repo.count_by_severity(Severidade.MEDIUM) == 0

    def test_resolver_marca_resolvido(self, db_session):
        if_ = self._seed_if(db_session)
        anomalia = self._create_anomalia(db_session, if_.id)

        repo = AnomaliaRepository(db_session)
        resolvida = repo.resolver(anomalia.id, notas="Falso positivo")
        db_session.commit()

        assert resolvida.resolvido is True
        assert resolvida.notas_resolucao == "Falso positivo"
        assert repo.count_active() == 0

    def test_resolver_id_inexistente_retorna_none(self, db_session):
        repo = AnomaliaRepository(db_session)
        assert repo.resolver(9999) is None

    def test_list_by_if(self, db_session):
        repo_if = InstituicaoRepository(db_session)
        if1 = repo_if.create(nome="IF A", cnpj="11.100.100/0001-10", ativa=True)
        if2 = repo_if.create(nome="IF B", cnpj="22.200.200/0001-20", ativa=True)
        db_session.commit()

        repo = AnomaliaRepository(db_session)
        repo.create(
            if_id=if1.id,
            tipo=TipoAnomalia.SPREAD_ALTO,
            severidade=Severidade.HIGH,
            valor_detectado=Decimal("140.0"),
            descricao="IF A anomalia",
        )
        repo.create(
            if_id=if2.id,
            tipo=TipoAnomalia.SPREAD_ALTO,
            severidade=Severidade.HIGH,
            valor_detectado=Decimal("145.0"),
            descricao="IF B anomalia",
        )
        db_session.commit()

        anomalias_if1 = repo.list_by_if(if1.id)
        assert len(anomalias_if1) == 1
        assert anomalias_if1[0].if_id == if1.id

    def test_get_recent(self, db_session):
        if_ = self._seed_if(db_session)
        for _ in range(7):
            self._create_anomalia(db_session, if_.id)

        repo = AnomaliaRepository(db_session)
        recentes = repo.get_recent(limit=5)
        assert len(recentes) == 5

    def test_list_with_filters_resolvido(self, db_session):
        if_ = self._seed_if(db_session)
        self._create_anomalia(db_session, if_.id, resolvido=False)
        self._create_anomalia(db_session, if_.id, resolvido=True)

        repo = AnomaliaRepository(db_session)
        nao_resolvidas = repo.list_with_filters(filters={"resolvido": False})
        resolvidas = repo.list_with_filters(filters={"resolvido": True})

        assert len(nao_resolvidas) == 1
        assert len(resolvidas) == 1


# ---------------------------------------------------------------------------
# TaxaReferenciaRepository
# ---------------------------------------------------------------------------


class TestTaxaReferenciaRepository:
    def test_create_e_get_ultima(self, db_session):
        repo = TaxaReferenciaRepository(db_session)
        repo.create(tipo="selic", data=date(2024, 1, 1), valor=Decimal("10.50"))
        repo.create(tipo="selic", data=date(2024, 1, 2), valor=Decimal("10.75"))
        db_session.commit()

        ultima = repo.get_ultima("selic")
        assert ultima is not None
        assert ultima.valor == Decimal("10.75")

    def test_get_ultima_sem_dados_retorna_none(self, db_session):
        repo = TaxaReferenciaRepository(db_session)
        assert repo.get_ultima("selic") is None

    def test_upsert_cria_e_atualiza(self, db_session):
        repo = TaxaReferenciaRepository(db_session)
        t = repo.upsert(tipo="cdi", data=date(2024, 3, 1), valor=Decimal("10.00"))
        db_session.commit()
        assert t.valor == Decimal("10.00")

        # Atualiza mesmo registro
        repo.upsert(tipo="cdi", data=date(2024, 3, 1), valor=Decimal("10.50"))
        db_session.commit()

        ultima = repo.get_ultima("cdi")
        assert ultima.valor == Decimal("10.50")
