"""Testes unitários para CSRFMiddleware — bypass removido e Origin check (SEC-04)."""

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from veredas.web.csrf import (
    CSRF_COOKIE_NAME,
    CSRF_HEADER_NAME,
    CSRFMiddleware,
    generate_csrf_token,
)


def _make_app() -> FastAPI:
    """App mínimo com CSRFMiddleware e uma rota POST para testes."""
    app = FastAPI()
    app.add_middleware(CSRFMiddleware)

    @app.get("/ping")
    def ping():
        return {"ok": True}

    @app.post("/action")
    def action():
        return {"done": True}

    return app


@pytest.fixture
def app():
    return _make_app()


@pytest.fixture
def client(app):
    return TestClient(app, raise_server_exceptions=False)


# ---------------------------------------------------------------------------
# Cenário: POST sem cookie (bypass SEC-04 foi removido)
# ---------------------------------------------------------------------------


class TestPostSemCookie:
    def test_post_sem_cookie_retorna_403(self, client):
        """O bypass foi removido: POST sem cookie deve ser bloqueado."""
        resp = client.post("/action", headers={CSRF_HEADER_NAME: "qualquer"})
        assert resp.status_code == 403
        assert "ausente" in resp.json()["detail"].lower()

    def test_post_sem_cookie_sem_header_retorna_403(self, client):
        resp = client.post("/action")
        assert resp.status_code == 403

    def test_get_ainda_passa_sem_cookie(self, client):
        resp = client.get("/ping")
        assert resp.status_code == 200


# ---------------------------------------------------------------------------
# Cenário: POST com cookie válido + token correto
# ---------------------------------------------------------------------------


class TestPostComTokenValido:
    def test_post_com_cookie_e_header_correto_retorna_200(self, client):
        token = generate_csrf_token()
        resp = client.post(
            "/action",
            cookies={CSRF_COOKIE_NAME: token},
            headers={CSRF_HEADER_NAME: token},
        )
        assert resp.status_code == 200

    def test_post_com_token_errado_retorna_403(self, client):
        token = generate_csrf_token()
        resp = client.post(
            "/action",
            cookies={CSRF_COOKIE_NAME: token},
            headers={CSRF_HEADER_NAME: "token_errado"},
        )
        assert resp.status_code == 403
        assert "inválido" in resp.json()["detail"].lower()

    def test_post_com_cookie_sem_header_retorna_403(self, client):
        token = generate_csrf_token()
        resp = client.post("/action", cookies={CSRF_COOKIE_NAME: token})
        assert resp.status_code == 403


# ---------------------------------------------------------------------------
# Cenário: GET define cookie automaticamente
# ---------------------------------------------------------------------------


class TestCookieSetOnGet:
    def test_get_define_cookie_csrf(self, client):
        resp = client.get("/ping")
        assert CSRF_COOKIE_NAME in resp.cookies

    def test_token_no_cookie_permite_post_seguinte(self, client):
        """Fluxo legítimo: GET define cookie, POST subsequente usa o mesmo token."""
        get_resp = client.get("/ping")
        token = get_resp.cookies[CSRF_COOKIE_NAME]

        post_resp = client.post(
            "/action",
            cookies={CSRF_COOKIE_NAME: token},
            headers={CSRF_HEADER_NAME: token},
        )
        assert post_resp.status_code == 200


# ---------------------------------------------------------------------------
# Cenário: Origin header check
# ---------------------------------------------------------------------------


class TestOriginCheck:
    def test_origin_diferente_retorna_403(self, client):
        """Cross-origin POST deve ser bloqueado pelo Origin check."""
        token = generate_csrf_token()
        resp = client.post(
            "/action",
            cookies={CSRF_COOKIE_NAME: token},
            headers={
                CSRF_HEADER_NAME: token,
                "Origin": "https://evil.com",
            },
        )
        assert resp.status_code == 403
        assert "origin" in resp.json()["detail"].lower()

    def test_origin_correto_permite_post(self, client):
        """Origin igual ao host não deve bloquear."""
        token = generate_csrf_token()
        resp = client.post(
            "/action",
            cookies={CSRF_COOKIE_NAME: token},
            headers={
                CSRF_HEADER_NAME: token,
                "Origin": "http://testserver",
            },
        )
        assert resp.status_code == 200

    def test_sem_origin_header_depende_apenas_do_cookie(self, client):
        """Sem Origin header, apenas o cookie e o token são verificados."""
        token = generate_csrf_token()
        resp = client.post(
            "/action",
            cookies={CSRF_COOKIE_NAME: token},
            headers={CSRF_HEADER_NAME: token},
        )
        assert resp.status_code == 200
