"""
Testes unitários para o framework de scrapers (Fase 4).
"""

import pytest
from datetime import datetime
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

from veredas.collectors.scrapers import (
    BaseScraper,
    SCRAPERS_REGISTRY,
    ScraperResult,
    TaxaColetada,
)
from veredas.collectors.scrapers.anti_bot import (
    RateLimiter,
    ProxyRotator,
    ProxyConfig,
    SessionManager,
)
from veredas.collectors.scrapers.normalizer import TaxaNormalizer
from veredas.storage.models import Indexador


class TestBaseScraper:
    """Testes para BaseScraper."""

    def test_scrapers_registry_has_all_platforms(self):
        """Verifica que todas as plataformas estão registradas."""
        expected = {"xp", "btg", "rico", "nubank", "inter"}
        assert set(SCRAPERS_REGISTRY.keys()) == expected

    def test_scraper_classes_inherit_from_base(self):
        """Verifica que todos os scrapers herdam de BaseScraper."""
        for name, scraper_class in SCRAPERS_REGISTRY.items():
            assert issubclass(scraper_class, BaseScraper), f"{name} não herda de BaseScraper"


class TestTaxaColetada:
    """Testes para dataclass TaxaColetada."""

    def test_taxa_coletada_creation(self):
        """Testa criação de TaxaColetada."""
        taxa = TaxaColetada(
            instituicao_nome="Banco Teste",
            instituicao_cnpj="00.000.000/0001-00",
            indexador=Indexador.CDI,
            percentual=Decimal("120.5"),
            prazo_dias=365,
        )

        assert taxa.instituicao_nome == "Banco Teste"
        assert taxa.percentual == Decimal("120.5")
        assert taxa.indexador == Indexador.CDI

    def test_taxa_coletada_optional_fields(self):
        """Testa campos opcionais de TaxaColetada."""
        taxa = TaxaColetada(
            instituicao_nome="Banco Teste",
            instituicao_cnpj="00.000.000/0001-00",
            indexador=Indexador.IPCA,
            percentual=Decimal("6.5"),
            prazo_dias=720,
            taxa_adicional=Decimal("5.0"),
            valor_minimo=Decimal("1000.00"),
            liquidez_diaria=True,
        )

        assert taxa.taxa_adicional == Decimal("5.0")
        assert taxa.valor_minimo == Decimal("1000.00")
        assert taxa.liquidez_diaria is True


class TestScraperResult:
    """Testes para dataclass ScraperResult."""

    def test_scraper_result_success(self):
        """Testa ScraperResult de sucesso."""
        taxas = [
            TaxaColetada(
                instituicao_nome="Banco A",
                instituicao_cnpj="00.000.000/0001-01",
                indexador=Indexador.CDI,
                percentual=Decimal("115"),
                prazo_dias=360,
            ),
        ]

        result = ScraperResult(
            taxas=taxas,
            fonte="rico",
            url="https://rico.com.vc",
        )

        assert result.fonte == "rico"
        assert len(result.taxas) == 1
        assert result.taxas[0].instituicao_nome == "Banco A"

    def test_scraper_result_empty(self):
        """Testa ScraperResult vazio."""
        result = ScraperResult(
            taxas=[],
            fonte="nubank",
            url="https://nubank.com.br",
            erros=["Nenhuma taxa encontrada"],
        )

        assert len(result.taxas) == 0
        assert len(result.erros) == 1


class TestRateLimiter:
    """Testes para RateLimiter."""

    def test_rate_limiter_creation(self):
        """Testa criação do RateLimiter."""
        limiter = RateLimiter(min_delay=0.5, max_delay=5.0)
        assert limiter.min_delay == 0.5
        assert limiter.max_delay == 5.0

    def test_rate_limiter_on_success(self):
        """Testa que delay diminui após sucesso."""
        limiter = RateLimiter(min_delay=0.5, max_delay=5.0)
        limiter.current_delay = 2.0
        limiter.on_success()
        assert limiter.current_delay < 2.0

    def test_rate_limiter_on_failure(self):
        """Testa que delay aumenta após falha."""
        limiter = RateLimiter(min_delay=0.5, max_delay=5.0)
        limiter.current_delay = 1.0
        limiter.on_failure(429)
        assert limiter.current_delay > 1.0


class TestProxyRotator:
    """Testes para ProxyRotator."""

    def test_proxy_rotator_empty_list(self):
        """Testa ProxyRotator com lista vazia."""
        rotator = ProxyRotator(proxies=[])
        proxy = rotator.get_next()
        assert proxy is None

    def test_proxy_rotator_with_proxies(self):
        """Testa ProxyRotator com proxies configurados."""
        proxies = [
            ProxyConfig(host="proxy1.example.com", port=8080),
            ProxyConfig(host="proxy2.example.com", port=8080),
        ]
        rotator = ProxyRotator(proxies=proxies)

        proxy = rotator.get_next()
        assert proxy is not None
        assert proxy.host in ["proxy1.example.com", "proxy2.example.com"]

    def test_proxy_mark_failed(self):
        """Testa marcação de proxy como falho."""
        proxies = [
            ProxyConfig(host="proxy1.example.com", port=8080),
        ]
        rotator = ProxyRotator(proxies=proxies)
        proxy = rotator.get_next()
        rotator.mark_failed(proxy)
        # Após reset (quando todos falham), proxy volta a estar disponível
        next_proxy = rotator.get_next()
        assert next_proxy is not None


class TestProxyConfig:
    """Testes para ProxyConfig."""

    def test_proxy_config_url(self):
        """Testa geração de URL do proxy."""
        proxy = ProxyConfig(host="proxy.example.com", port=8080)
        assert proxy.url == "http://proxy.example.com:8080"

    def test_proxy_config_url_with_auth(self):
        """Testa URL com autenticação."""
        proxy = ProxyConfig(
            host="proxy.example.com",
            port=8080,
            username="user",
            password="pass",
        )
        assert proxy.url == "http://user:pass@proxy.example.com:8080"


class TestSessionManager:
    """Testes para SessionManager."""

    def test_session_manager_creation(self):
        """Testa criação do SessionManager."""
        manager = SessionManager()
        assert manager is not None
        assert manager.fingerprint is not None

    def test_session_manager_headers(self):
        """Testa headers do SessionManager."""
        manager = SessionManager()
        headers = manager.headers
        assert "User-Agent" in headers
        assert "Accept-Language" in headers

    @pytest.mark.asyncio
    async def test_session_manager_get_client(self):
        """Testa obtenção de cliente HTTP."""
        manager = SessionManager()
        client = await manager.get_client()
        assert client is not None
        await manager.close()


class TestTaxaNormalizer:
    """Testes para TaxaNormalizer."""

    def test_normalizer_creation(self):
        """Testa criação do normalizador."""
        normalizer = TaxaNormalizer()
        assert normalizer is not None
        assert normalizer.strict is False

    def test_normalizer_strict_mode(self):
        """Testa normalizador em modo estrito."""
        normalizer = TaxaNormalizer(strict=True)
        assert normalizer.strict is True

    def test_normalizer_normalize_single(self):
        """Testa normalização de taxa individual."""
        normalizer = TaxaNormalizer()

        taxa = TaxaColetada(
            instituicao_nome="ITAU UNIBANCO",
            instituicao_cnpj="60.701.190/0001-04",
            indexador=Indexador.CDI,
            percentual=Decimal("110.0"),
            prazo_dias=365,
        )

        result = normalizer.normalize_single(
            taxa,
            fonte="xp",
            timestamp=datetime.now(),
        )

        assert result is not None
        assert result.instituicao_nome is not None

    def test_normalizer_normalize_batch(self):
        """Testa normalização em lote."""
        normalizer = TaxaNormalizer()

        taxas = [
            TaxaColetada(
                instituicao_nome="Banco A",
                instituicao_cnpj="00.000.000/0001-01",
                indexador=Indexador.CDI,
                percentual=Decimal("110.0"),
            ),
            TaxaColetada(
                instituicao_nome="Banco B",
                instituicao_cnpj="00.000.000/0001-02",
                indexador=Indexador.CDI,
                percentual=Decimal("115.0"),
            ),
        ]

        scraper_result = ScraperResult(
            taxas=taxas,
            fonte="btg",
            url="https://btg.com",
        )

        normalized = normalizer.normalize(scraper_result)
        assert len(normalized) == 2
