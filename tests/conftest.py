"""Fixtures compartilhadas para toda a suíte de testes."""

from datetime import datetime, timedelta
from decimal import Decimal

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from veredas.storage.models import (
    Anomalia,
    Base,
    Indexador,
    InstituicaoFinanceira,
    Segmento,
    Severidade,
    TaxaCDB,
    TipoAnomalia,
)


@pytest.fixture(scope="function")
def engine():
    eng = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(eng)
    yield eng
    Base.metadata.drop_all(eng)
    eng.dispose()


@pytest.fixture(scope="function")
def db_session(engine) -> Session:
    SessionLocal = sessionmaker(bind=engine)
    session = SessionLocal()
    yield session
    session.rollback()
    session.close()


@pytest.fixture
def sample_if(db_session) -> InstituicaoFinanceira:
    instituicao = InstituicaoFinanceira(
        cnpj="12.345.678/0001-00",
        nome="Banco Teste S.A.",
        nome_reduzido="Banco Teste",
        segmento=Segmento.BANCO_COMERCIAL,
        ativa=True,
    )
    db_session.add(instituicao)
    db_session.flush()
    return instituicao


@pytest.fixture
def sample_if2(db_session) -> InstituicaoFinanceira:
    instituicao = InstituicaoFinanceira(
        cnpj="98.765.432/0001-99",
        nome="Financeira Exemplo S.A.",
        nome_reduzido="Fin Exemplo",
        segmento=Segmento.FINANCEIRA,
        ativa=True,
    )
    db_session.add(instituicao)
    db_session.flush()
    return instituicao


def make_taxa(
    if_id: int,
    percentual: float,
    indexador: Indexador = Indexador.CDI,
    prazo_dias: int = 365,
    data_coleta: datetime | None = None,
    taxa_adicional: float | None = None,
    fonte: str = "test",
) -> TaxaCDB:
    """Fábrica de TaxaCDB para testes (sem persistência)."""
    return TaxaCDB(
        if_id=if_id,
        data_coleta=data_coleta or datetime.now(),
        indexador=indexador,
        percentual=Decimal(str(percentual)),
        prazo_dias=prazo_dias,
        fonte=fonte,
        taxa_adicional=Decimal(str(taxa_adicional)) if taxa_adicional is not None else None,
    )


def make_taxa_serie(
    if_id: int,
    valores: list[float],
    indexador: Indexador = Indexador.CDI,
    data_inicio: datetime | None = None,
) -> list[TaxaCDB]:
    """Gera uma série temporal de taxas para um IF."""
    inicio = data_inicio or datetime(2024, 1, 1)
    return [
        make_taxa(if_id, v, indexador=indexador, data_coleta=inicio + timedelta(days=i))
        for i, v in enumerate(valores)
    ]
