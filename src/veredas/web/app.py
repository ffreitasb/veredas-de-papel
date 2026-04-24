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

from veredas.catalog import (
    css_tier_emissor,
    css_tier_plataforma,
    get_tier_emissor,
    get_tier_plataforma,
    label_tier_emissor,
    label_tier_plataforma,
)
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
# Tier catalog helpers (badges de emissor e plataforma)
templates.env.globals["get_tier_emissor"] = get_tier_emissor
templates.env.globals["get_tier_plataforma"] = get_tier_plataforma
templates.env.globals["label_tier_emissor"] = label_tier_emissor
templates.env.globals["label_tier_plataforma"] = label_tier_plataforma
templates.env.globals["css_tier_emissor"] = css_tier_emissor
templates.env.globals["css_tier_plataforma"] = css_tier_plataforma


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """
    Middleware que adiciona headers de seguranca HTTP.

    Adiciona protecoes contra:
    - XSS e injecao de conteudo (Content-Security-Policy)
    - Clickjacking (X-Frame-Options / frame-ancestors)
    - MIME type sniffing (X-Content-Type-Options)
    - Referrer leakage (Referrer-Policy)
    - Feature abuse (Permissions-Policy)
    """

    # CSP para dashboard self-hosted com HTMX e Plotly (servidos de /static).
    # unsafe-inline em script-src necessário para Plotly inline charts;
    # tightening com nonces é o próximo passo quando templates suportarem.
    _CSP = (
        "default-src 'self'; "
        "script-src 'self' 'unsafe-inline'; "
        "style-src 'self' 'unsafe-inline'; "
        "img-src 'self' data:; "
        "connect-src 'self'; "
        "font-src 'self'; "
        "frame-ancestors 'none'; "
        "base-uri 'self'; "
        "form-action 'self';"
    )

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        response = await call_next(request)

        response.headers["Content-Security-Policy"] = self._CSP
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
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
