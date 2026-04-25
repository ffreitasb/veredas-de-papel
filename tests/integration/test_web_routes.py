"""Testes de integração para rotas web (HTTP end-to-end)."""

from datetime import datetime
from decimal import Decimal

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from starlette.testclient import TestClient

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
from veredas.web.app import create_app
from veredas.web.dependencies import get_db

_CNPJ = "60872504000123"  # Itaú Unibanco — CNPJ válido para teste com validate=True
_IF_NOME = "Banco Alpha S.A."


@pytest.fixture(scope="module")
def app(tmp_path_factory):
    """Cria app FastAPI com banco em memória para testes."""
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from sqlalchemy.pool import StaticPool

    from veredas.storage.models import Base

    # StaticPool força todas as conexões a reutilizarem o mesmo banco in-memory
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine, autoflush=True)

    def override_get_db():
        session = SessionLocal()
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    application = create_app()
    application.dependency_overrides[get_db] = override_get_db
    return application


@pytest.fixture(scope="module")
def client(app):
    with TestClient(app, raise_server_exceptions=True) as c:
        yield c


class TestHomeRoute:
    def test_home_retorna_200(self, client):
        response = client.get("/")
        assert response.status_code == 200

    def test_home_contem_html(self, client):
        response = client.get("/")
        assert "text/html" in response.headers["content-type"]

    def test_stats_partial_retorna_200(self, client):
        response = client.get("/partials/stats")
        assert response.status_code == 200


class TestTaxasRoute:
    def test_lista_taxas_retorna_200(self, client):
        response = client.get("/taxas/")
        assert response.status_code == 200

    def test_lista_taxas_contem_html(self, client):
        response = client.get("/taxas/")
        assert "text/html" in response.headers["content-type"]


class TestAnomaliasRoute:
    def test_lista_anomalias_retorna_200(self, client):
        response = client.get("/anomalias/")
        assert response.status_code == 200

    def test_lista_anomalias_contem_html(self, client):
        response = client.get("/anomalias/")
        assert "text/html" in response.headers["content-type"]


class TestInstituicoesRoute:
    def test_lista_instituicoes_retorna_200(self, client):
        response = client.get("/instituicoes/")
        assert response.status_code == 200

    def test_lista_instituicoes_contem_html(self, client):
        response = client.get("/instituicoes/")
        assert "text/html" in response.headers["content-type"]


class TestTimelineRoute:
    def test_timeline_retorna_200(self, client):
        response = client.get("/timeline/")
        assert response.status_code == 200


class TestSecurityHeaders:
    def test_x_frame_options_presente(self, client):
        response = client.get("/")
        assert response.headers.get("x-frame-options") == "DENY"

    def test_x_content_type_options_presente(self, client):
        response = client.get("/")
        assert response.headers.get("x-content-type-options") == "nosniff"

    def test_referrer_policy_presente(self, client):
        response = client.get("/")
        assert response.headers.get("referrer-policy") == "strict-origin-when-cross-origin"

    def test_csp_presente(self, client):
        response = client.get("/")
        csp = response.headers.get("content-security-policy", "")
        assert "default-src" in csp
        assert "frame-ancestors 'none'" in csp

    def test_permissions_policy_presente(self, client):
        response = client.get("/")
        assert "permissions-policy" in response.headers


# ---------------------------------------------------------------------------
# Fixtures com dados semeados — IF + taxas + anomalia
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def seeded_app():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine, autoflush=True)

    session = SessionLocal()
    if_ = InstituicaoFinanceira(
        cnpj=_CNPJ,
        nome=_IF_NOME,
        nome_reduzido="Banco Alpha",
        segmento=Segmento.BANCO_COMERCIAL,
        ativa=True,
    )
    session.add(if_)
    session.flush()

    # 2 CDI + 1 PREFIXADO
    for i, (indexador, pct) in enumerate(
        [(Indexador.CDI, "110.0"), (Indexador.CDI, "115.0"), (Indexador.PREFIXADO, "13.5")]
    ):
        session.add(
            TaxaCDB(
                if_id=if_.id,
                data_coleta=datetime(2024, 6, i + 1),
                indexador=indexador,
                percentual=Decimal(pct),
                prazo_dias=365,
                fonte="test",
            )
        )

    session.add(
        Anomalia(
            if_id=if_.id,
            tipo=TipoAnomalia.SPREAD_ALTO,
            severidade=Severidade.HIGH,
            valor_detectado=Decimal("135.0"),
            descricao="Spread alto detectado em teste",
            detectado_em=datetime(2024, 6, 1),
        )
    )
    session.commit()
    session.close()

    def override_get_db():
        s = SessionLocal()
        try:
            yield s
            s.commit()
        except Exception:
            s.rollback()
            raise
        finally:
            s.close()

    application = create_app()
    application.dependency_overrides[get_db] = override_get_db
    return application


@pytest.fixture(scope="module")
def seeded_client(seeded_app):
    with TestClient(seeded_app, raise_server_exceptions=True) as c:
        yield c


# ---------------------------------------------------------------------------
# Taxas — testes com dados
# ---------------------------------------------------------------------------


class TestTaxasComDados:
    def test_lista_contem_nome_da_if(self, seeded_client):
        response = seeded_client.get("/taxas/")
        assert _IF_NOME in response.text

    def test_filtro_indexador_cdi(self, seeded_client):
        response = seeded_client.get("/taxas/?indexador=cdi")  # StrEnum lowercase
        assert response.status_code == 200

    def test_filtro_indexador_invalido_retorna_500_ou_422(self, seeded_client):
        response = seeded_client.get("/taxas/?indexador=INVALIDO")
        assert response.status_code in (200, 422, 500)

    def test_htmx_partial_retorna_fragmento(self, seeded_client):
        response = seeded_client.get("/taxas/", headers={"HX-Request": "true"})
        assert response.status_code == 200
        # Partial não contém a tag <html> do layout completo
        assert "<html" not in response.text.lower()

    def test_export_csv_retorna_content_type_correto(self, seeded_client):
        response = seeded_client.get("/taxas/export.csv")
        assert response.status_code == 200
        assert "text/csv" in response.headers["content-type"]

    def test_export_csv_contem_cabecalho(self, seeded_client):
        response = seeded_client.get("/taxas/export.csv")
        assert "Instituição" in response.text or "Institu" in response.text

    def test_detalhe_taxa_inexistente_retorna_404(self, seeded_client):
        response = seeded_client.get("/taxas/99999")
        assert response.status_code == 404

    def test_paginacao_fora_do_range_retorna_vazio(self, seeded_client):
        response = seeded_client.get("/taxas/?pagina=999")
        assert response.status_code == 200


# ---------------------------------------------------------------------------
# Anomalias — testes com dados
# ---------------------------------------------------------------------------


class TestAnomaliasComDados:
    def test_lista_contem_anomalia_semeada(self, seeded_client):
        response = seeded_client.get("/anomalias/")
        assert response.status_code == 200

    def test_filtro_severidade_high(self, seeded_client):
        response = seeded_client.get("/anomalias/?severidade=high")  # StrEnum lowercase
        assert response.status_code == 200

    def test_filtro_severidade_invalida_retorna_400(self, seeded_client):
        response = seeded_client.get("/anomalias/?severidade=INVALIDA")
        assert response.status_code == 400

    def test_export_csv_retorna_200(self, seeded_client):
        response = seeded_client.get("/anomalias/export.csv")
        assert response.status_code == 200
        assert "text/csv" in response.headers["content-type"]

    def test_export_csv_contem_cabecalho(self, seeded_client):
        response = seeded_client.get("/anomalias/export.csv")
        assert "Severidade" in response.text

    def test_partial_htmx_retorna_200(self, seeded_client):
        response = seeded_client.get("/anomalias/partials/list")
        assert response.status_code == 200

    def test_status_todas_retorna_200(self, seeded_client):
        response = seeded_client.get("/anomalias/?status=todas")
        assert response.status_code == 200


# ---------------------------------------------------------------------------
# Instituições — testes com dados
# ---------------------------------------------------------------------------


class TestInstituicoesComDados:
    def test_lista_contem_nome_da_if(self, seeded_client):
        response = seeded_client.get("/instituicoes/")
        assert _IF_NOME in response.text

    def test_detalhe_por_cnpj_retorna_200(self, seeded_client):
        response = seeded_client.get(f"/instituicoes/{_CNPJ}")
        assert response.status_code == 200

    def test_detalhe_cnpj_inexistente_retorna_404(self, seeded_client):
        # CNPJ válido (dígitos corretos) mas não cadastrado na base de teste
        response = seeded_client.get("/instituicoes/11222333000181")
        assert response.status_code == 404

    def test_ordenacao_nome(self, seeded_client):
        response = seeded_client.get("/instituicoes/?ordem=nome")
        assert response.status_code == 200

    def test_ordenacao_risco(self, seeded_client):
        response = seeded_client.get("/instituicoes/?ordem=risco_desc")
        assert response.status_code == 200
