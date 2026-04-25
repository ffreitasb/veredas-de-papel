"""
Configuração do Jinja2Templates isolada do ciclo de vida da aplicação.

Separado de web/app.py para que as rotas não dependam do módulo app
(que puxa CSRF, rate-limit, catalog e outros no import).
"""

from datetime import datetime
from pathlib import Path

from fastapi.templating import Jinja2Templates

from veredas import TZ_BRASIL
from veredas.catalog import (
    css_tier_emissor,
    css_tier_plataforma,
    get_tier_emissor,
    get_tier_plataforma,
    label_tier_emissor,
    label_tier_plataforma,
)
from veredas.web.csrf import csrf_token_input, get_csrf_token

TEMPLATES_DIR = Path(__file__).parent / "templates"

templates = Jinja2Templates(directory=str(TEMPLATES_DIR))

templates.env.globals["csrf_token_input"] = csrf_token_input
templates.env.globals["get_csrf_token"] = get_csrf_token
templates.env.globals["now"] = lambda: datetime.now(TZ_BRASIL)
templates.env.globals["get_tier_emissor"] = get_tier_emissor
templates.env.globals["get_tier_plataforma"] = get_tier_plataforma
templates.env.globals["label_tier_emissor"] = label_tier_emissor
templates.env.globals["label_tier_plataforma"] = label_tier_plataforma
templates.env.globals["css_tier_emissor"] = css_tier_emissor
templates.env.globals["css_tier_plataforma"] = css_tier_plataforma
