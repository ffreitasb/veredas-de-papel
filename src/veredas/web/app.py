"""
FastAPI application factory.

Cria e configura a aplicacao web do veredas de papel.
"""

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from datetime import datetime
from pathlib import Path

from fastapi import FastAPI, Request, Response
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint

from veredas.config import get_settings
from veredas.storage.database import DatabaseManager
from veredas.web.csrf import CSRFMiddleware, csrf_token_input, get_csrf_token
from veredas.web.ratelimit import RateLimitMiddleware

# Paths
WEB_DIR = Path(__file__).parent
TEMPLATES_DIR = WEB_DIR / "templates"
STATIC_DIR = WEB_DIR / "static"

# Templates singleton
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))

# Globals disponíveis em todos os templates
templates.env.globals["csrf_token_input"] = csrf_token_input
templates.env.globals["get_csrf_token"] = get_csrf_token
templates.env.globals["now"] = datetime.now


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """
    Middleware que adiciona headers de seguranca HTTP.

    Adiciona protecoes contra:
    - Clickjacking (X-Frame-Options)
    - MIME type sniffing (X-Content-Type-Options)
    - XSS reflexivo (X-XSS-Protection)
    - Referrer leakage (Referrer-Policy)
    - Feature abuse (Permissions-Policy)
    """

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        response = await call_next(request)

        # Protecao contra clickjacking
        response.headers["X-Frame-Options"] = "DENY"

        # Evita MIME type sniffing
        response.headers["X-Content-Type-Options"] = "nosniff"

        # Protecao XSS legacy (browsers modernos usam CSP)
        response.headers["X-XSS-Protection"] = "1; mode=block"

        # Controla informacoes de referrer
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"

        # Desabilita features potencialmente perigosas
        response.headers["Permissions-Policy"] = (
            "accelerometer=(), camera=(), geolocation=(), gyroscope=(), "
            "magnetometer=(), microphone=(), payment=(), usb=()"
        )

        return response


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Gerencia o ciclo de vida da aplicacao."""
    # Startup
    settings = get_settings()
    settings.ensure_data_dir()

    # Inicializa banco se necessario
    db_manager = DatabaseManager(settings.database.path)
    db_manager.init_db()

    yield

    # Shutdown (cleanup se necessario)


def create_app() -> FastAPI:
    """
    Cria a aplicacao FastAPI.

    Returns:
        FastAPI: Aplicacao configurada.
    """
    app = FastAPI(
        title="veredas de papel",
        description="Monitor de taxas de CDB e deteccao de anomalias",
        version="0.1.0",
        lifespan=lifespan,
    )

    # Security middlewares (ordem importa: primeiro adicionado = ultimo executado)
    # Rate limiting (executa primeiro, antes do CSRF)
    app.add_middleware(
        RateLimitMiddleware,
        requests_per_minute=60,
        exclude_paths=["/static", "/health", "/favicon.ico"],
    )
    # CSRF protection
    app.add_middleware(CSRFMiddleware)
    # Security headers (executa por ultimo, adiciona headers a todas respostas)
    app.add_middleware(SecurityHeadersMiddleware)

    # Static files
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

    # Register routes
    from veredas.web.routes import anomalias, home, instituicoes, taxas, timeline

    app.include_router(home.router)
    app.include_router(taxas.router, prefix="/taxas", tags=["taxas"])
    app.include_router(anomalias.router, prefix="/anomalias", tags=["anomalias"])
    app.include_router(instituicoes.router, prefix="/instituicoes", tags=["instituicoes"])
    app.include_router(timeline.router, prefix="/timeline", tags=["timeline"])

    return app


# CLI entry point
def run_server(host: str = "127.0.0.1", port: int = 8000, reload: bool = False) -> None:
    """
    Executa o servidor de desenvolvimento.

    Args:
        host: Host para bind.
        port: Porta para bind.
        reload: Habilita hot reload.
    """
    import uvicorn

    uvicorn.run(
        "veredas.web.app:create_app",
        factory=True,
        host=host,
        port=port,
        reload=reload,
    )
