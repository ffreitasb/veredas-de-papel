"""Testes unitários para get_client_ip — prevenção de IP spoofing (SEC-02)."""

from unittest.mock import MagicMock

import pytest

from veredas.web.ratelimit import get_client_ip


def _request(direct_ip: str, forwarded_for: str | None = None, real_ip: str | None = None):
    """Monta um Request falso com o mínimo necessário."""
    req = MagicMock()
    req.client.host = direct_ip
    headers = {}
    if forwarded_for is not None:
        headers["X-Forwarded-For"] = forwarded_for
    if real_ip is not None:
        headers["X-Real-IP"] = real_ip
    req.headers.get = lambda key, default=None: headers.get(key, default)
    return req


class TestGetClientIpSemProxy:
    """Sem proxies confiáveis: headers de proxy devem ser ignorados."""

    def test_usa_ip_direto_sem_headers(self):
        req = _request("203.0.113.5")
        assert get_client_ip(req, frozenset()) == "203.0.113.5"

    def test_ignora_x_forwarded_for_sem_proxy_confiavel(self):
        req = _request("203.0.113.5", forwarded_for="1.2.3.4")
        assert get_client_ip(req, frozenset()) == "203.0.113.5"

    def test_ignora_x_real_ip_sem_proxy_confiavel(self):
        req = _request("203.0.113.5", real_ip="9.9.9.9")
        assert get_client_ip(req, frozenset()) == "203.0.113.5"

    def test_multiplos_ips_no_forwarded_ignorados(self):
        req = _request("10.0.0.1", forwarded_for="1.1.1.1, 2.2.2.2, 3.3.3.3")
        assert get_client_ip(req, frozenset()) == "10.0.0.1"


class TestGetClientIpComProxy:
    """Com proxy confiável configurado: headers de proxy são respeitados."""

    TRUSTED = frozenset({"127.0.0.1", "10.0.0.1"})

    def test_le_x_forwarded_for_quando_proxy_confiavel(self):
        req = _request("127.0.0.1", forwarded_for="203.0.113.5")
        assert get_client_ip(req, self.TRUSTED) == "203.0.113.5"

    def test_usa_primeiro_ip_da_lista_forwarded(self):
        req = _request("127.0.0.1", forwarded_for="1.2.3.4, 5.6.7.8, 127.0.0.1")
        assert get_client_ip(req, self.TRUSTED) == "1.2.3.4"

    def test_le_x_real_ip_quando_sem_forwarded(self):
        req = _request("10.0.0.1", real_ip="203.0.113.5")
        assert get_client_ip(req, self.TRUSTED) == "203.0.113.5"

    def test_ip_nao_confiavel_nao_usa_headers(self):
        req = _request("8.8.8.8", forwarded_for="1.2.3.4")
        assert get_client_ip(req, self.TRUSTED) == "8.8.8.8"

    def test_sem_headers_retorna_direto(self):
        req = _request("127.0.0.1")
        assert get_client_ip(req, self.TRUSTED) == "127.0.0.1"


class TestGetClientIpEdgeCases:
    def test_client_none_retorna_unknown(self):
        req = MagicMock()
        req.client = None
        req.headers.get = lambda key, default=None: default
        assert get_client_ip(req, frozenset()) == "unknown"

    def test_forwarded_for_com_espacos(self):
        req = _request("127.0.0.1", forwarded_for="  203.0.113.5  ,  1.2.3.4  ")
        assert get_client_ip(req, frozenset({"127.0.0.1"})) == "203.0.113.5"
