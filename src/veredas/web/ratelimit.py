"""
Rate Limiting Middleware for FastAPI.

Implementa rate limiting simples baseado em IP usando
armazenamento em memoria (adequado para single-instance).

Para producao com multiplas instancias, considere usar Redis.
"""

import time
from collections import defaultdict
from collections.abc import Callable
from dataclasses import dataclass, field

from fastapi import HTTPException, Request, status
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response


@dataclass
class RateLimitState:
    """Estado do rate limiter para um IP."""

    requests: list[float] = field(default_factory=list)

    def cleanup(self, window_seconds: int) -> None:
        """Remove requests fora da janela de tempo."""
        now = time.time()
        cutoff = now - window_seconds
        self.requests = [t for t in self.requests if t > cutoff]

    def add_request(self) -> None:
        """Registra nova request."""
        self.requests.append(time.time())

    def count(self) -> int:
        """Retorna numero de requests na janela."""
        return len(self.requests)


class RateLimitStore:
    """
    Armazenamento em memoria para rate limiting.

    Thread-safe para uso com asyncio.
    """

    def __init__(self):
        self._store: dict[str, RateLimitState] = defaultdict(RateLimitState)
        self._last_cleanup = time.time()
        self._cleanup_interval = 60  # segundos

    def get_state(self, key: str, window_seconds: int) -> RateLimitState:
        """Obtem estado para uma chave, fazendo cleanup se necessario."""
        # Cleanup periodico global
        now = time.time()
        if now - self._last_cleanup > self._cleanup_interval:
            self._global_cleanup(window_seconds)
            self._last_cleanup = now

        state = self._store[key]
        state.cleanup(window_seconds)
        return state

    def _global_cleanup(self, window_seconds: int) -> None:
        """Remove entradas vazias do store."""
        empty_keys = []
        for key, state in self._store.items():
            state.cleanup(window_seconds)
            if state.count() == 0:
                empty_keys.append(key)

        for key in empty_keys:
            del self._store[key]


# Store global (singleton)
_store = RateLimitStore()


def get_client_ip(request: Request) -> str:
    """
    Extrai IP do cliente da request.

    Considera headers de proxy reverso (X-Forwarded-For, X-Real-IP).
    """
    # Verificar headers de proxy
    forwarded_for = request.headers.get("X-Forwarded-For")
    if forwarded_for:
        # Primeiro IP da lista e o cliente original
        return forwarded_for.split(",")[0].strip()

    real_ip = request.headers.get("X-Real-IP")
    if real_ip:
        return real_ip.strip()

    # Fallback para IP direto
    if request.client:
        return request.client.host

    return "unknown"


class RateLimitMiddleware(BaseHTTPMiddleware):
    """
    Middleware de rate limiting.

    Limita requisicoes por IP dentro de uma janela de tempo.

    Args:
        app: Aplicacao FastAPI.
        requests_per_minute: Numero maximo de requests por minuto.
        window_seconds: Janela de tempo em segundos (default 60).
        exclude_paths: Paths a excluir do rate limiting.
    """

    def __init__(
        self,
        app,
        requests_per_minute: int = 60,
        window_seconds: int = 60,
        exclude_paths: list[str] | None = None,
    ):
        super().__init__(app)
        self.requests_per_minute = requests_per_minute
        self.window_seconds = window_seconds
        self.exclude_paths = exclude_paths or ["/static", "/health"]

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Processa request aplicando rate limiting."""
        # Verificar exclusoes
        path = request.url.path
        for excluded in self.exclude_paths:
            if path.startswith(excluded):
                return await call_next(request)

        # Obter IP do cliente
        client_ip = get_client_ip(request)

        # Verificar rate limit
        state = _store.get_state(client_ip, self.window_seconds)

        if state.count() >= self.requests_per_minute:
            # Calcular tempo ate reset
            if state.requests:
                oldest = min(state.requests)
                retry_after = int(self.window_seconds - (time.time() - oldest)) + 1
            else:
                retry_after = self.window_seconds

            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Muitas requisicoes. Tente novamente em breve.",
                headers={"Retry-After": str(retry_after)},
            )

        # Registrar request
        state.add_request()

        # Processar request
        response = await call_next(request)

        # Adicionar headers informativos
        remaining = max(0, self.requests_per_minute - state.count())
        response.headers["X-RateLimit-Limit"] = str(self.requests_per_minute)
        response.headers["X-RateLimit-Remaining"] = str(remaining)
        response.headers["X-RateLimit-Reset"] = str(int(time.time()) + self.window_seconds)

        return response


class StrictRateLimitMiddleware(RateLimitMiddleware):
    """
    Rate limiting mais restrito para endpoints sensiveis.

    Usa limite menor (10 req/min) para proteger contra brute force.
    """

    def __init__(
        self,
        app,
        requests_per_minute: int = 10,
        window_seconds: int = 60,
        strict_paths: list[str] | None = None,
    ):
        super().__init__(
            app,
            requests_per_minute=requests_per_minute,
            window_seconds=window_seconds,
        )
        self.strict_paths = strict_paths or ["/api/", "/anomalias/"]

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Aplica rate limiting apenas em paths especificos."""
        path = request.url.path

        # Verificar se e um path estrito
        is_strict = any(path.startswith(p) for p in self.strict_paths)
        if not is_strict:
            return await call_next(request)

        # Aplicar rate limiting restrito
        return await super().dispatch(request, call_next)
