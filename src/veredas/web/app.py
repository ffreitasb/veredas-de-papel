"""
FastAPI application factory.

Cria e configura a aplicacao web do veredas de papel.
"""

from pathlib import Path
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from veredas.config import get_settings
from veredas.storage.database import DatabaseManager
from veredas.web.csrf import CSRFMiddleware, csrf_token_input, get_csrf_token

# Paths
WEB_DIR = Path(__file__).parent
TEMPLATES_DIR = WEB_DIR / "templates"
STATIC_DIR = WEB_DIR / "static"

# Templates singleton
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))

# Add CSRF helper to templates
templates.env.globals["csrf_token_input"] = csrf_token_input
templates.env.globals["get_csrf_token"] = get_csrf_token


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

    # CSRF protection middleware
    app.add_middleware(CSRFMiddleware)

    # Static files
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

    # Register routes
    from veredas.web.routes import home, taxas, anomalias, instituicoes, timeline

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
