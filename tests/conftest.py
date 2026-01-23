"""
Fixtures compartilhadas para testes do veredas de papel.

Configura banco de dados em memória e dados de teste.
"""

from datetime import date, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Generator

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from veredas.storage.models import (
    Anomalia,
    Base,
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


@pytest.fixture(scope="function")
def db_engine():
    """Cria engine SQLite em memória para cada teste."""
    engine = create_engine("sqlite:///:memory:", echo=False)
    Base.metadata.create_all(engine)
    yield engine
    Base.metadata.drop_all(engine)
    engine.dispose()


@pytest.fixture(scope="function")
def db_session(db_engine) -> Generator[Session, None, None]:
    """Cria sessão de banco de dados para teste."""
    session_factory = sessionmaker(bind=db_engine)
    session = session_factory()
    try:
        yield session
    finally:
        session.rollback()
        session.close()


@pytest.fixture
def instituicao_exemplo(db_session: Session) -> InstituicaoFinanceira:
    """Cria uma instituição financeira de exemplo."""
    inst = InstituicaoFinanceira(
        cnpj="00.000.000/0001-00",
        nome="Banco Exemplo S.A.",
        nome_reduzido="Banco Exemplo",
        segmento=Segmento.BANCO_MULTIPLO,
        indice_basileia=Decimal("15.5"),
        indice_liquidez=Decimal("120.0"),
        ativo_total=Decimal("1000000000.00"),
        patrimonio_liquido=Decimal("100000000.00"),
        ativa=True,
    )
    db_session.add(inst)
    db_session.commit()
    return inst


@pytest.fixture
def instituicao_risco(db_session: Session) -> InstituicaoFinanceira:
    """Cria uma instituição financeira com indicadores de risco."""
    inst = InstituicaoFinanceira(
        cnpj="11.111.111/0001-11",
        nome="Banco Arriscado S.A.",
        nome_reduzido="Banco Arriscado",
        segmento=Segmento.BANCO_MULTIPLO,
        indice_basileia=Decimal("9.5"),  # Abaixo do mínimo recomendado
        indice_liquidez=Decimal("80.0"),  # Baixa liquidez
        ativo_total=Decimal("500000000.00"),
        patrimonio_liquido=Decimal("30000000.00"),
        ativa=True,
    )
    db_session.add(inst)
    db_session.commit()
    return inst


@pytest.fixture
def taxa_cdb_normal(db_session: Session, instituicao_exemplo: InstituicaoFinanceira) -> TaxaCDB:
    """Cria uma taxa de CDB normal (sem anomalia)."""
    taxa = TaxaCDB(
        if_id=instituicao_exemplo.id,
        data_coleta=datetime.now(),
        indexador=Indexador.CDI,
        percentual=Decimal("110.0"),  # 110% CDI - normal
        prazo_dias=365,
        valor_minimo=Decimal("1000.00"),
        liquidez_diaria=False,
        fonte="teste",
    )
    db_session.add(taxa)
    db_session.commit()
    return taxa


@pytest.fixture
def taxa_cdb_spread_alto(
    db_session: Session, instituicao_risco: InstituicaoFinanceira
) -> TaxaCDB:
    """Cria uma taxa de CDB com spread alto (anomalia HIGH)."""
    taxa = TaxaCDB(
        if_id=instituicao_risco.id,
        data_coleta=datetime.now(),
        indexador=Indexador.CDI,
        percentual=Decimal("140.0"),  # 140% CDI - alto
        prazo_dias=365,
        valor_minimo=Decimal("1000.00"),
        liquidez_diaria=False,
        fonte="teste",
    )
    db_session.add(taxa)
    db_session.commit()
    return taxa


@pytest.fixture
def taxa_cdb_spread_critico(
    db_session: Session, instituicao_risco: InstituicaoFinanceira
) -> TaxaCDB:
    """Cria uma taxa de CDB com spread crítico (anomalia CRITICAL)."""
    taxa = TaxaCDB(
        if_id=instituicao_risco.id,
        data_coleta=datetime.now(),
        indexador=Indexador.CDI,
        percentual=Decimal("165.0"),  # 165% CDI - crítico
        prazo_dias=365,
        valor_minimo=Decimal("1000.00"),
        liquidez_diaria=False,
        fonte="teste",
    )
    db_session.add(taxa)
    db_session.commit()
    return taxa


@pytest.fixture
def taxa_cdb_ipca_alto(
    db_session: Session, instituicao_risco: InstituicaoFinanceira
) -> TaxaCDB:
    """Cria uma taxa de CDB IPCA+ com spread alto."""
    taxa = TaxaCDB(
        if_id=instituicao_risco.id,
        data_coleta=datetime.now(),
        indexador=Indexador.IPCA,
        percentual=Decimal("100.0"),  # Base IPCA
        taxa_adicional=Decimal("12.0"),  # IPCA + 12%
        prazo_dias=730,
        valor_minimo=Decimal("5000.00"),
        liquidez_diaria=False,
        fonte="teste",
    )
    db_session.add(taxa)
    db_session.commit()
    return taxa


@pytest.fixture
def taxas_para_variacao(
    db_session: Session, instituicao_risco: InstituicaoFinanceira
) -> tuple[TaxaCDB, TaxaCDB]:
    """Cria par de taxas para teste de variação (salto brusco)."""
    # Taxa anterior (7 dias atrás)
    taxa_anterior = TaxaCDB(
        if_id=instituicao_risco.id,
        data_coleta=datetime.now() - timedelta(days=7),
        indexador=Indexador.CDI,
        percentual=Decimal("110.0"),
        prazo_dias=365,
        valor_minimo=Decimal("1000.00"),
        fonte="teste",
    )
    db_session.add(taxa_anterior)

    # Taxa atual (com salto de 15pp)
    taxa_atual = TaxaCDB(
        if_id=instituicao_risco.id,
        data_coleta=datetime.now(),
        indexador=Indexador.CDI,
        percentual=Decimal("125.0"),  # +15pp
        prazo_dias=365,
        valor_minimo=Decimal("1000.00"),
        fonte="teste",
    )
    db_session.add(taxa_atual)
    db_session.commit()

    return taxa_anterior, taxa_atual


@pytest.fixture
def taxa_referencia_selic(db_session: Session) -> TaxaReferencia:
    """Cria taxa Selic de referência."""
    taxa = TaxaReferencia(
        data=date.today(),
        tipo="selic",
        valor=Decimal("13.75"),
        fonte="bcb",
    )
    db_session.add(taxa)
    db_session.commit()
    return taxa


@pytest.fixture
def taxa_referencia_cdi(db_session: Session) -> TaxaReferencia:
    """Cria taxa CDI de referência."""
    taxa = TaxaReferencia(
        data=date.today(),
        tipo="cdi",
        valor=Decimal("13.65"),
        fonte="bcb",
    )
    db_session.add(taxa)
    db_session.commit()
    return taxa


@pytest.fixture
def evento_liquidacao(db_session: Session) -> EventoRegulatorio:
    """Cria evento de liquidação de exemplo (Banco Master)."""
    evento = EventoRegulatorio(
        if_nome="Banco Master S.A.",
        tipo=TipoEvento.LIQUIDACAO,
        data_evento=date(2025, 11, 18),
        descricao="Liquidação extrajudicial do Banco Master",
        fonte="https://www.bcb.gov.br/",
        taxas_pre_evento={
            "cdi_percentual": 165,
            "ipca_spread": 30,
        },
        sinais_detectados=[
            "SPREAD_CRITICO",
            "SALTO_EXTREMO",
        ],
    )
    db_session.add(evento)
    db_session.commit()
    return evento


@pytest.fixture
def anomalia_exemplo(
    db_session: Session,
    instituicao_risco: InstituicaoFinanceira,
    taxa_cdb_spread_critico: TaxaCDB,
) -> Anomalia:
    """Cria anomalia de exemplo."""
    anomalia = Anomalia(
        if_id=instituicao_risco.id,
        taxa_id=taxa_cdb_spread_critico.id,
        tipo=TipoAnomalia.SPREAD_CRITICO,
        severidade=Severidade.CRITICAL,
        valor_detectado=Decimal("165.0"),
        valor_esperado=Decimal("100.0"),
        desvio=Decimal("65.0"),
        descricao="CDB oferecendo 165% do CDI - spread crítico (>150%)",
        detectado_em=datetime.now(),
        resolvido=False,
    )
    db_session.add(anomalia)
    db_session.commit()
    return anomalia


@pytest.fixture
def tmp_db_path(tmp_path: Path) -> Path:
    """Caminho temporário para banco de dados de teste."""
    return tmp_path / "test_veredas.db"


# ============================================================================
# Fixtures para detectores estatísticos (Fase 3)
# ============================================================================


@pytest.fixture
def taxas_serie_temporal(
    db_session: Session, instituicao_exemplo: InstituicaoFinanceira
) -> list[TaxaCDB]:
    """Cria série temporal de taxas para análise estatística (30 dias)."""
    import random

    random.seed(42)  # Reprodutibilidade

    taxas = []
    base_rate = 110.0
    now = datetime.now()

    for i in range(30):
        # Pequena variação aleatória (normal)
        noise = random.gauss(0, 1.5)
        # Tendência leve de alta
        trend = i * 0.1
        percentual = Decimal(str(round(base_rate + trend + noise, 2)))

        taxa = TaxaCDB(
            if_id=instituicao_exemplo.id,
            data_coleta=now - timedelta(days=30 - i),
            indexador=Indexador.CDI,
            percentual=percentual,
            prazo_dias=365,
            valor_minimo=Decimal("1000.00"),
            fonte="teste",
        )
        db_session.add(taxa)
        taxas.append(taxa)

    db_session.commit()
    return taxas


@pytest.fixture
def taxas_com_outlier(
    db_session: Session, instituicao_risco: InstituicaoFinanceira
) -> list[TaxaCDB]:
    """Cria série temporal com um outlier extremo no final."""
    import random

    random.seed(42)

    taxas = []
    base_rate = 110.0
    now = datetime.now()

    for i in range(20):
        noise = random.gauss(0, 1.0)
        percentual = Decimal(str(round(base_rate + noise, 2)))

        taxa = TaxaCDB(
            if_id=instituicao_risco.id,
            data_coleta=now - timedelta(days=20 - i),
            indexador=Indexador.CDI,
            percentual=percentual,
            prazo_dias=365,
            valor_minimo=Decimal("1000.00"),
            fonte="teste",
        )
        db_session.add(taxa)
        taxas.append(taxa)

    # Adiciona outlier extremo
    outlier_taxa = TaxaCDB(
        if_id=instituicao_risco.id,
        data_coleta=now,
        indexador=Indexador.CDI,
        percentual=Decimal("145.0"),  # ~35pp acima da média
        prazo_dias=365,
        valor_minimo=Decimal("1000.00"),
        fonte="teste",
    )
    db_session.add(outlier_taxa)
    taxas.append(outlier_taxa)

    db_session.commit()
    return taxas


@pytest.fixture
def taxas_com_change_point(
    db_session: Session, instituicao_risco: InstituicaoFinanceira
) -> list[TaxaCDB]:
    """Cria série temporal com mudança estrutural no meio."""
    import random

    random.seed(42)

    taxas = []
    now = datetime.now()

    # Primeiro segmento: média ~110%
    for i in range(15):
        noise = random.gauss(0, 1.0)
        percentual = Decimal(str(round(110.0 + noise, 2)))

        taxa = TaxaCDB(
            if_id=instituicao_risco.id,
            data_coleta=now - timedelta(days=30 - i),
            indexador=Indexador.CDI,
            percentual=percentual,
            prazo_dias=365,
            valor_minimo=Decimal("1000.00"),
            fonte="teste",
        )
        db_session.add(taxa)
        taxas.append(taxa)

    # Segundo segmento: média ~130% (change point)
    for i in range(15):
        noise = random.gauss(0, 1.0)
        percentual = Decimal(str(round(130.0 + noise, 2)))

        taxa = TaxaCDB(
            if_id=instituicao_risco.id,
            data_coleta=now - timedelta(days=15 - i),
            indexador=Indexador.CDI,
            percentual=percentual,
            prazo_dias=365,
            valor_minimo=Decimal("1000.00"),
            fonte="teste",
        )
        db_session.add(taxa)
        taxas.append(taxa)

    db_session.commit()
    return taxas


@pytest.fixture
def taxas_insuficientes(
    db_session: Session, instituicao_exemplo: InstituicaoFinanceira
) -> list[TaxaCDB]:
    """Cria série temporal muito curta (insuficiente para análise)."""
    taxas = []
    now = datetime.now()

    for i in range(5):
        taxa = TaxaCDB(
            if_id=instituicao_exemplo.id,
            data_coleta=now - timedelta(days=5 - i),
            indexador=Indexador.CDI,
            percentual=Decimal("110.0"),
            prazo_dias=365,
            valor_minimo=Decimal("1000.00"),
            fonte="teste",
        )
        db_session.add(taxa)
        taxas.append(taxa)

    db_session.commit()
    return taxas
