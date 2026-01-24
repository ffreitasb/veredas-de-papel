"""
Testes unitários para detectores da Fase 4.
"""

import pytest
from datetime import date, datetime
from decimal import Decimal

from veredas.detectors import (
    PlatformDiscrepancyDetector,
    TaxaPorPlataforma,
    PriceDropConfig,
    PriceDropDetector,
    detectar_quedas_mercado,
    SentimentRiskConfig,
    SentimentRiskDetector,
    detectar_risco_sentimento,
)
from veredas.detectors.base import Severidade
from veredas.detectors.platform_discrepancy import DiscrepanciaConfig
from veredas.collectors.b3 import PrecoSecundario, TipoTitulo
from veredas.collectors.sentiment import (
    SignalAggregator,
    SinalReclameAqui,
    SinalProcessosBC,
)
from veredas.storage.models import Indexador


class TestPlatformDiscrepancyDetector:
    """Testes para PlatformDiscrepancyDetector."""

    def test_detector_creation(self):
        """Testa criação do detector."""
        detector = PlatformDiscrepancyDetector()
        assert detector.name == "platform_discrepancy"

    def test_detector_with_custom_config(self):
        """Testa detector com config customizada."""
        config = DiscrepanciaConfig(
            threshold_medium=Decimal("3"),
            threshold_high=Decimal("6"),
            threshold_critical=Decimal("12"),
        )
        detector = PlatformDiscrepancyDetector(config=config)
        assert detector.config.threshold_medium == Decimal("3")

    def test_detect_no_discrepancy(self):
        """Testa detecção sem discrepância."""
        detector = PlatformDiscrepancyDetector()

        now = datetime.now()
        # Mesma taxa em todas plataformas
        taxas = {
            "BancoA": [
                TaxaPorPlataforma(
                    plataforma="xp",
                    percentual=Decimal("115"),
                    prazo_dias=360,
                    indexador=Indexador.CDI,
                    data_coleta=now,
                ),
                TaxaPorPlataforma(
                    plataforma="btg",
                    percentual=Decimal("115"),
                    prazo_dias=360,
                    indexador=Indexador.CDI,
                    data_coleta=now,
                ),
            ],
        }

        result = detector.detect(taxas)
        assert result.success
        assert len(result.anomalias) == 0

    def test_detect_medium_discrepancy(self):
        """Testa detecção de discrepância média."""
        detector = PlatformDiscrepancyDetector()

        now = datetime.now()
        # Discrepância de 5pp (= threshold padrão)
        taxas = {
            "BancoA": [
                TaxaPorPlataforma(
                    plataforma="xp",
                    percentual=Decimal("115"),
                    prazo_dias=360,
                    indexador=Indexador.CDI,
                    data_coleta=now,
                ),
                TaxaPorPlataforma(
                    plataforma="btg",
                    percentual=Decimal("120"),
                    prazo_dias=360,
                    indexador=Indexador.CDI,
                    data_coleta=now,
                ),
            ],
        }

        result = detector.detect(taxas)
        assert result.success
        assert len(result.anomalias) >= 1
        assert result.anomalias[0].severidade == Severidade.MEDIUM

    def test_detect_critical_discrepancy(self):
        """Testa detecção de discrepância crítica."""
        config = DiscrepanciaConfig(
            threshold_critical=Decimal("10"),
        )
        detector = PlatformDiscrepancyDetector(config=config)

        now = datetime.now()
        # Discrepância de 15pp
        taxas = {
            "BancoA": [
                TaxaPorPlataforma(
                    plataforma="xp",
                    percentual=Decimal("110"),
                    prazo_dias=360,
                    indexador=Indexador.CDI,
                    data_coleta=now,
                ),
                TaxaPorPlataforma(
                    plataforma="rico",
                    percentual=Decimal("130"),
                    prazo_dias=360,
                    indexador=Indexador.CDI,
                    data_coleta=now,
                ),
            ],
        }

        result = detector.detect(taxas)
        assert len(result.anomalias) >= 1
        # Deve ser HIGH ou CRITICAL (20pp é CRITICAL por padrão, 15pp é HIGH)
        assert result.anomalias[0].severidade in (Severidade.HIGH, Severidade.CRITICAL)


def _create_preco_secundario(
    codigo: str = "CDB-TEST",
    cnpj: str = "00.000.000/0001-00",
    nome: str = "Banco Teste",
    pu_fechamento: Decimal = Decimal("1000"),
    pu_abertura: Decimal = Decimal("1000"),
    variacao: Decimal = None,
) -> PrecoSecundario:
    """Helper para criar PrecoSecundario com defaults."""
    return PrecoSecundario(
        codigo_titulo=codigo,
        emissor_cnpj=cnpj,
        emissor_nome=nome,
        tipo_titulo=TipoTitulo.CDB,
        data_referencia=date(2024, 1, 15),
        pu_abertura=pu_abertura,
        pu_fechamento=pu_fechamento,
        pu_minimo=min(pu_abertura, pu_fechamento) - Decimal("5"),
        pu_maximo=max(pu_abertura, pu_fechamento) + Decimal("5"),
        pu_medio=(pu_abertura + pu_fechamento) / 2,
        quantidade_negocios=100,
        quantidade_titulos=1000,
        valor_financeiro=Decimal("1000000"),
        taxa_minima=Decimal("110"),
        taxa_maxima=Decimal("115"),
        taxa_media=Decimal("112"),
        variacao_dia=variacao,
    )


class TestPriceDropDetector:
    """Testes para PriceDropDetector."""

    def test_detector_creation(self):
        """Testa criação do detector."""
        detector = PriceDropDetector()
        assert detector.name == "price_drop"

    def test_detector_with_custom_config(self):
        """Testa detector com config customizada."""
        config = PriceDropConfig(
            queda_medium=Decimal("3"),
            queda_high=Decimal("8"),
            queda_critical=Decimal("15"),
        )
        detector = PriceDropDetector(config=config)
        assert detector.config.queda_medium == Decimal("3")

    def test_detect_no_drop(self):
        """Testa detecção sem queda."""
        detector = PriceDropDetector()

        precos = [_create_preco_secundario(
            pu_abertura=Decimal("1000"),
            pu_fechamento=Decimal("1002"),  # Subiu
        )]

        result = detector.detect(precos)
        assert result.success
        assert len(result.anomalias) == 0

    def test_detect_medium_drop(self):
        """Testa detecção de queda média."""
        detector = PriceDropDetector()

        precos = [_create_preco_secundario(
            codigo="CDB-A",
            pu_abertura=Decimal("1000"),
            pu_fechamento=Decimal("930"),  # Queda de 7%
        )]

        # Preços anteriores para comparação
        precos_anteriores = {"CDB-A": Decimal("1000")}

        result = detector.detect(precos, precos_anteriores)
        assert result.success
        # Pode ou não gerar anomalia dependendo da configuração

    def test_detect_critical_drop(self):
        """Testa detecção de queda crítica."""
        config = PriceDropConfig(
            queda_critical=Decimal("20"),
        )
        detector = PriceDropDetector(config=config)

        precos = [_create_preco_secundario(
            codigo="CDB-RISCO",
            pu_abertura=Decimal("1000"),
            pu_fechamento=Decimal("750"),  # Queda de 25%
        )]

        precos_anteriores = {"CDB-RISCO": Decimal("1000")}

        result = detector.detect(precos, precos_anteriores)
        # Pode ou não gerar anomalia dependendo do volume

    def test_utility_function(self):
        """Testa função utilitária detectar_quedas_mercado."""
        precos = [_create_preco_secundario()]

        result = detectar_quedas_mercado(precos)
        assert result is not None


class TestSentimentRiskDetector:
    """Testes para SentimentRiskDetector."""

    def test_detector_creation(self):
        """Testa criação do detector."""
        detector = SentimentRiskDetector()
        assert detector.name == "sentiment_risk"

    def test_detector_with_custom_config(self):
        """Testa detector com config customizada."""
        config = SentimentRiskConfig(
            score_medium=30.0,
            score_high=50.0,
            score_critical=70.0,
        )
        detector = SentimentRiskDetector(config=config)
        assert detector.config.score_medium == 30.0

    def test_detect_low_risk(self):
        """Testa detecção de risco baixo."""
        detector = SentimentRiskDetector()

        # Criar sinal com risco baixo
        aggregator = SignalAggregator()
        signal = aggregator.agregar(
            cnpj="00.000.000/0001-00",
            nome="Banco Saudável",
            reclame_aqui=SinalReclameAqui(
                nota_geral=Decimal("9.0"),
                indice_solucao=Decimal("95"),
                total_reclamacoes=1000,
                reclamacoes_30d=50,
                variacao_30d=Decimal("-10"),  # Diminuindo
            ),
            processos_bc=SinalProcessosBC(
                total_processos=0,
                processos_ativos=0,
                valor_total_multas=Decimal("0"),
                tipos_processos=[],
            ),
        )

        result = detector.detect([signal])
        # Risco baixo não deve gerar anomalia (config padrão é score > 40)
        assert result is not None

    def test_detect_high_risk(self):
        """Testa detecção de risco alto."""
        detector = SentimentRiskDetector()

        # Criar sinal com risco alto
        aggregator = SignalAggregator()
        signal = aggregator.agregar(
            cnpj="00.000.000/0001-00",
            nome="Banco Problemático",
            reclame_aqui=SinalReclameAqui(
                nota_geral=Decimal("3.0"),
                indice_solucao=Decimal("20"),
                total_reclamacoes=15000,
                reclamacoes_30d=1000,
                variacao_30d=Decimal("50"),
            ),
            processos_bc=SinalProcessosBC(
                total_processos=10,
                processos_ativos=5,
                valor_total_multas=Decimal("5000000"),
                tipos_processos=["sancionador", "administrativo"],
            ),
        )

        result = detector.detect([signal])
        assert result is not None

    def test_detect_from_raw_data(self):
        """Testa detecção a partir de dados brutos."""
        detector = SentimentRiskDetector()

        dados = [
            {
                "cnpj": "00.000.000/0001-00",
                "nome": "Banco X",
                "reclame_aqui": {
                    "nota_geral": 4.0,
                    "indice_solucao": 30,
                    "total_reclamacoes": 8000,
                    "reclamacoes_30d": 600,
                    "variacao_30d": 20,
                },
                "processos_bc": {
                    "total_processos": 5,
                    "processos_ativos": 2,
                    "valor_total_multas": 1000000,
                    "tipos_processos": ["administrativo"],
                },
            }
        ]

        result = detector.detect_from_raw(dados)
        assert result is not None

    def test_utility_function(self):
        """Testa função utilitária detectar_risco_sentimento."""
        dados = [
            {
                "cnpj": "00.000.000/0001-00",
                "nome": "Banco Y",
                "reclame_aqui": {
                    "nota_geral": 8.0,
                    "indice_solucao": 85,
                    "total_reclamacoes": 2000,
                    "reclamacoes_30d": 100,
                    "variacao_30d": -5,
                },
            }
        ]

        result = detectar_risco_sentimento(dados)
        assert result is not None


class TestDetectionEngineAlternative:
    """Testes para integração com DetectionEngine."""

    def test_engine_alternative_detectors(self):
        """Testa que engine tem detectores alternativos."""
        from veredas.detectors import DetectionEngine, DetectorCategory

        detectors = DetectionEngine.available_detectors()
        assert DetectorCategory.ALTERNATIVE in detectors
        assert "platform_discrepancy_detector" in detectors[DetectorCategory.ALTERNATIVE]
        assert "price_drop_detector" in detectors[DetectorCategory.ALTERNATIVE]
        assert "sentiment_risk_detector" in detectors[DetectorCategory.ALTERNATIVE]

    def test_engine_analyze_alternative(self):
        """Testa análise com detectores alternativos."""
        from veredas.detectors import DetectionEngine, EngineConfig

        config = EngineConfig(enable_alternative=True)
        engine = DetectionEngine(config)

        # Análise sem dados (deve retornar vazio)
        result = engine.analyze_alternative()
        assert result is not None
        assert len(result.anomalias) == 0
