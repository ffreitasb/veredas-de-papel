"""
Cache em memoria para dados frequentemente acessados.

Implementa cache TTL simples para reduzir queries ao banco.
"""

from datetime import datetime, timedelta
from typing import Any

from sqlalchemy.orm import Session

from veredas import TZ_BRASIL
from veredas.storage.repository import TaxaReferenciaRepository


class TTLCache:
    """Cache simples com TTL (Time To Live)."""

    def __init__(self, default_ttl: timedelta = timedelta(hours=1)):
        self._cache: dict[str, Any] = {}
        self._timestamps: dict[str, datetime] = {}
        self._default_ttl = default_ttl

    def get(self, key: str) -> Any | None:
        """Busca valor do cache se ainda valido."""
        if key not in self._cache:
            return None

        if datetime.now(TZ_BRASIL) - self._timestamps[key] > self._default_ttl:
            # Expirado
            del self._cache[key]
            del self._timestamps[key]
            return None

        return self._cache[key]

    def set(self, key: str, value: Any) -> None:
        """Armazena valor no cache."""
        self._cache[key] = value
        self._timestamps[key] = datetime.now(TZ_BRASIL)

    def invalidate(self, key: str) -> None:
        """Remove entrada do cache."""
        self._cache.pop(key, None)
        self._timestamps.pop(key, None)

    def clear(self) -> None:
        """Limpa todo o cache."""
        self._cache.clear()
        self._timestamps.clear()


# Cache global para taxas de referencia (TTL 1 hora)
_reference_cache = TTLCache(default_ttl=timedelta(hours=1))

# Cache para contadores (TTL 5 minutos)
_counter_cache = TTLCache(default_ttl=timedelta(minutes=5))


def get_cached_reference_rates(session: Session) -> dict:
    """
    Busca taxas de referencia com cache de 1 hora.

    Args:
        session: Sessao do banco de dados.

    Returns:
        Dict com selic, cdi, ipca.
    """
    cache_key = "reference_rates"
    cached = _reference_cache.get(cache_key)

    if cached is not None:
        return cached

    repo = TaxaReferenciaRepository(session)
    rates = {
        "selic": repo.get_latest("selic"),
        "cdi": repo.get_latest("cdi"),
        "ipca": repo.get_latest("ipca"),
    }

    _reference_cache.set(cache_key, rates)
    return rates


def get_cached_anomaly_counts(session: Session, count_func) -> dict:
    """
    Busca contadores de anomalias com cache de 5 minutos.

    Args:
        session: Sessao do banco de dados.
        count_func: Funcao que retorna os contadores.

    Returns:
        Dict com contadores por severidade.
    """
    cache_key = "anomaly_counts"
    cached = _counter_cache.get(cache_key)

    if cached is not None:
        return cached

    counts = count_func(session)
    _counter_cache.set(cache_key, counts)
    return counts


def invalidate_reference_cache() -> None:
    """Invalida cache de taxas de referencia."""
    _reference_cache.invalidate("reference_rates")


def invalidate_anomaly_cache() -> None:
    """Invalida cache de anomalias."""
    _counter_cache.invalidate("anomaly_counts")


def clear_all_caches() -> None:
    """Limpa todos os caches."""
    _reference_cache.clear()
    _counter_cache.clear()
