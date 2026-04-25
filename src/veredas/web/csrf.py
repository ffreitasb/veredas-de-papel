"""
CSRF Protection for FastAPI + HTMX.

Implements double-submit cookie pattern:
1. Token stored in cookie (httponly=False for JS access)
2. Token sent in header (X-CSRF-Token) or form field (csrf_token)
3. Both must match for POST/PUT/DELETE requests
"""

import secrets

from fastapi import Request
from markupsafe import Markup
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse, Response

CSRF_COOKIE_NAME = "csrf_token"
CSRF_HEADER_NAME = "X-CSRF-Token"
CSRF_FORM_FIELD = "csrf_token"
SAFE_METHODS = {"GET", "HEAD", "OPTIONS", "TRACE"}


def generate_csrf_token() -> str:
    """Generate a cryptographically secure CSRF token."""
    return secrets.token_urlsafe(32)


def get_csrf_token(request: Request) -> str:
    """
    Get or create CSRF token for request.

    Token is stored in request.state for template access.
    """
    if hasattr(request.state, "csrf_token"):
        return request.state.csrf_token

    # Check cookie first
    token = request.cookies.get(CSRF_COOKIE_NAME)
    if not token:
        token = generate_csrf_token()

    request.state.csrf_token = token
    return token


class CSRFMiddleware(BaseHTTPMiddleware):
    """
    CSRF protection middleware.

    Validates CSRF token on unsafe methods (POST, PUT, DELETE, PATCH).
    """

    async def dispatch(self, request: Request, call_next) -> Response:
        # Always set token in request state
        token = get_csrf_token(request)

        # Validate on unsafe methods
        if request.method not in SAFE_METHODS:
            error_response = await self._validate_csrf(request, token)
            if error_response is not None:
                return error_response

        # Process request
        response = await call_next(request)

        # Set/refresh cookie on response
        if not request.cookies.get(CSRF_COOKIE_NAME):
            response.set_cookie(
                key=CSRF_COOKIE_NAME,
                value=token,
                httponly=False,  # HTMX needs JS access
                samesite="strict",
                secure=request.url.scheme == "https",
                max_age=3600,  # 1 hour
            )

        return response

    async def _validate_csrf(self, request: Request, expected_token: str) -> Response | None:
        """Validate CSRF token from header or form.

        Two-layer defense:
        1. Origin header check — rejects cross-origin requests immediately.
        2. Double-submit cookie — requires matching cookie + submitted token.

        Returns None on success, JSONResponse(403) on failure.
        Must NOT raise — HTTPException raised inside BaseHTTPMiddleware bypasses
        ExceptionMiddleware and reaches ServerErrorMiddleware as a 500.
        """
        # Layer 1: Origin header check.
        # Browsers always send Origin on cross-origin POST. If Origin is present
        # and doesn't match our host, reject regardless of cookie state.
        origin = request.headers.get("origin")
        if origin:
            host = request.url.netloc
            if origin not in (f"http://{host}", f"https://{host}"):
                return JSONResponse(
                    {"detail": "CSRF: Origin não autorizada"},
                    status_code=403,
                )

        # Layer 2: Double-submit cookie.
        # No cookie means the client has not loaded a page yet — block it.
        # (Legitimate HTMX/form flows always start with a GET that sets the cookie.)
        cookie_token = request.cookies.get(CSRF_COOKIE_NAME)
        if not cookie_token:
            return JSONResponse({"detail": "CSRF token ausente"}, status_code=403)

        # Check header first (HTMX sends X-CSRF-Token)
        submitted_token = request.headers.get(CSRF_HEADER_NAME)

        # Fall back to form field
        if not submitted_token:
            content_type = request.headers.get("content-type", "")
            if (
                "application/x-www-form-urlencoded" in content_type
                or "multipart/form-data" in content_type
            ):
                try:
                    form = await request.form()
                    submitted_token = form.get(CSRF_FORM_FIELD)
                except Exception:
                    pass

        if not submitted_token or not secrets.compare_digest(submitted_token, cookie_token):
            return JSONResponse({"detail": "CSRF token inválido"}, status_code=403)

        return None


def csrf_token_input(request: Request) -> Markup:
    """
    Generate hidden input field with CSRF token for templates.

    Returns Markup so Jinja2 renders it as raw HTML without | safe.
    Usage in Jinja2:
        {{ csrf_token_input(request) }}
    """
    token = get_csrf_token(request)
    return Markup(f'<input type="hidden" name="{CSRF_FORM_FIELD}" value="{token}">')
