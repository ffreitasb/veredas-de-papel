"""Testes de integração para rotas web (HTTP end-to-end)."""

import pytest
from starlette.testclient import TestClient

from veredas.web.app import create_app
from veredas.web.dependencies import get_db


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
