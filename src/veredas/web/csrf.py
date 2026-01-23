"""
CSRF Protection for FastAPI + HTMX.

Implements double-submit cookie pattern:
1. Token stored in cookie (httponly=False for JS access)
2. Token sent in header (X-CSRF-Token) or form field (csrf_token)
3. Both must match for POST/PUT/DELETE requests
"""

import secrets
from typing import Optional

from fastapi import Request, HTTPException, status
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response


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
            await self._validate_csrf(request, token)

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

    async def _validate_csrf(self, request: Request, expected_token: str) -> None:
        """Validate CSRF token from header or form."""
        # Skip if no token expected (first request)
        cookie_token = request.cookies.get(CSRF_COOKIE_NAME)
        if not cookie_token:
            return

        # Check header first (HTMX sends this)
        submitted_token = request.headers.get(CSRF_HEADER_NAME)

        # Check form field if no header
        if not submitted_token:
            # Try to get from form data
            content_type = request.headers.get("content-type", "")
            if "application/x-www-form-urlencoded" in content_type or "multipart/form-data" in content_type:
                try:
                    form = await request.form()
                    submitted_token = form.get(CSRF_FORM_FIELD)
                except Exception:
                    pass

        # Validate
        if not submitted_token or not secrets.compare_digest(submitted_token, cookie_token):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="CSRF token missing or invalid",
            )


def csrf_token_input(request: Request) -> str:
    """
    Generate hidden input field with CSRF token for templates.

    Usage in Jinja2:
        {{ csrf_token_input(request) | safe }}
    """
    token = get_csrf_token(request)
    return f'<input type="hidden" name="{CSRF_FORM_FIELD}" value="{token}">'
