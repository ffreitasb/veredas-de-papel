"""
Testes unitários para análise de sentimento e agregador de sinais (Fase 4).
"""

import pytest
from datetime import datetime
from decimal import Decimal

from veredas.collectors.sentiment import (
    SentimentAnalyzer,
    SignalAggregator,
    Sentimento,
    AnaliseTexto,
    SentimentoAgregado,
    RiskSignal,
    NivelRisco,
    TendenciaRisco,
    SinalReclameAqui,
    SinalProcessosBC,
    SinalMercadoSecundario,
    SinalSentimento,
)


class TestSentimento:
    """Testes para enum Sentimento."""

    def test_sentimento_values(self):
        """Verifica valores do enum."""
        assert Sentimento.MUITO_NEGATIVO.value == "MUITO_NEGATIVO"
        assert Sentimento.NEGATIVO.value == "NEGATIVO"
        assert Sentimento.NEUTRO.value == "NEUTRO"
        assert Sentimento.POSITIVO.value == "POSITIVO"
        assert Sentimento.MUITO_POSITIVO.value == "MUITO_POSITIVO"


class TestSentimentAnalyzer:
    """Testes para SentimentAnalyzer."""

    def test_analyzer_creation(self):
        """Testa criação do analyzer."""
        analyzer = SentimentAnalyzer()
        assert analyzer is not None

    def test_analyze_positive_text(self):
        """Testa análise de texto positivo."""
        analyzer = SentimentAnalyzer()

        texto = "Excelente banco! Ótimo atendimento, recomendo muito."
        resultado = analyzer.analisar(texto)

        assert resultado is not None
        assert resultado.score > 0
        assert resultado.sentimento in (Sentimento.POSITIVO, Sentimento.MUITO_POSITIVO)

    def test_analyze_negative_text(self):
        """Testa análise de texto negativo."""
        analyzer = SentimentAnalyzer()

        texto = "Péssimo banco! Cobrança indevida, atendimento horrível."
        resultado = analyzer.analisar(texto)

        assert resultado is not None
        assert resultado.score < 0
        assert resultado.sentimento in (Sentimento.NEGATIVO, Sentimento.MUITO_NEGATIVO)

    def test_analyze_neutral_text(self):
        """Testa análise de texto neutro."""
        analyzer = SentimentAnalyzer()

        texto = "Fui ao banco ontem."
        resultado = analyzer.analisar(texto)

        assert resultado is not None
        assert resultado.sentimento == Sentimento.NEUTRO

    def test_analyze_with_source(self):
        """Testa análise com fonte especificada."""
        analyzer = SentimentAnalyzer()

        texto = "Problema com o aplicativo"
        resultado = analyzer.analisar(texto, fonte="reclame_aqui")

        assert resultado.fonte == "reclame_aqui"

    def test_aggregate_sentiment(self):
        """Testa agregação de sentimento."""
        analyzer = SentimentAnalyzer()

        analises = [
            analyzer.analisar("Ótimo banco!"),
            analyzer.analisar("Bom atendimento"),
            analyzer.analisar("Péssimo app"),
        ]

        agregado = analyzer.agregar_sentimento(
            analises,
            cnpj="00.000.000/0001-00",
            nome="Banco Teste",
        )

        assert agregado is not None
        assert agregado.total_textos == 3


class TestSinalReclameAqui:
    """Testes para SinalReclameAqui."""

    def test_sinal_creation(self):
        """Testa criação de sinal."""
        sinal = SinalReclameAqui(
            nota_geral=Decimal("7.5"),
            indice_solucao=Decimal("80"),
            total_reclamacoes=5000,
            reclamacoes_30d=200,
            variacao_30d=Decimal("10"),
        )

        assert sinal.nota_geral == Decimal("7.5")

    def test_sinal_score_calculation(self):
        """Testa cálculo de score."""
        sinal = SinalReclameAqui(
            nota_geral=Decimal("3.0"),  # Nota ruim
            indice_solucao=Decimal("30"),  # Baixa resolução
            total_reclamacoes=10000,
            reclamacoes_30d=500,  # Muitas reclamações
            variacao_30d=Decimal("50"),  # Aumentando
        )

        score = sinal.calcular_score()
        assert score > 50  # Deve indicar risco elevado


class TestSinalProcessosBC:
    """Testes para SinalProcessosBC."""

    def test_sinal_creation(self):
        """Testa criação de sinal."""
        sinal = SinalProcessosBC(
            total_processos=5,
            processos_ativos=2,
            valor_total_multas=Decimal("1000000"),
            tipos_processos=["sancionador", "administrativo"],
        )

        assert sinal.processos_ativos == 2

    def test_sinal_score_high_risk(self):
        """Testa score de alto risco."""
        sinal = SinalProcessosBC(
            total_processos=10,
            processos_ativos=5,  # Muitos ativos
            valor_total_multas=Decimal("5000000"),  # Multas altas
            tipos_processos=["sancionador", "administrativo", "fiscalizacao"],
        )

        score = sinal.calcular_score()
        assert score > 60


class TestSinalMercadoSecundario:
    """Testes para SinalMercadoSecundario."""

    def test_sinal_creation(self):
        """Testa criação de sinal."""
        sinal = SinalMercadoSecundario(
            pu_medio=Decimal("950"),  # PU abaixo do nominal
            queda_acumulada=Decimal("5"),  # 5% de queda
            volume_30d=Decimal("1000000"),
            negocios_30d=100,
        )

        assert float(sinal.queda_acumulada) == 5

    def test_sinal_score_price_drop(self):
        """Testa score com queda de preço."""
        sinal = SinalMercadoSecundario(
            pu_medio=Decimal("850"),
            queda_acumulada=Decimal("15"),  # 15% de queda
            volume_30d=Decimal("50000000"),  # Alto volume
            negocios_30d=500,  # Muitos negócios
        )

        score = sinal.calcular_score()
        assert score > 60


class TestSinalSentimento:
    """Testes para SinalSentimento."""

    def test_sinal_creation(self):
        """Testa criação de sinal."""
        sinal = SinalSentimento(
            score_medio=Decimal("-0.3"),
            score_ponderado=Decimal("-0.35"),
            total_textos=100,
            textos_negativos=60,
            tendencia="PIORANDO",
        )

        assert sinal.textos_negativos == 60

    def test_sinal_score_negative(self):
        """Testa score negativo."""
        sinal = SinalSentimento(
            score_medio=Decimal("-0.7"),
            score_ponderado=Decimal("-0.65"),
            total_textos=200,
            textos_negativos=150,
            tendencia="PIORANDO",
        )

        score = sinal.calcular_score()
        assert score > 60


class TestSignalAggregator:
    """Testes para SignalAggregator."""

    def test_aggregator_creation(self):
        """Testa criação do agregador."""
        aggregator = SignalAggregator()
        assert aggregator is not None

    def test_aggregator_with_custom_weights(self):
        """Testa agregador com pesos customizados."""
        weights = {
            "reclame_aqui": 0.40,
            "processos_bc": 0.40,
            "mercado_secundario": 0.10,
            "sentimento": 0.10,
        }
        aggregator = SignalAggregator(weights=weights)

        # Pesos devem ser normalizados
        total = sum(aggregator.weights.values())
        assert abs(total - 1.0) < 0.01

    def test_agregar_single_signal(self):
        """Testa agregação com um único sinal."""
        aggregator = SignalAggregator()

        reclame = SinalReclameAqui(
            nota_geral=Decimal("5.0"),
            indice_solucao=Decimal("50"),
            total_reclamacoes=5000,
            reclamacoes_30d=200,
            variacao_30d=Decimal("0"),
        )

        signal = aggregator.agregar(
            cnpj="00.000.000/0001-00",
            nome="Banco Teste",
            reclame_aqui=reclame,
        )

        assert signal.sinais_disponiveis == 1
        assert signal.confianca == 0.25  # 1/4 sinais

    def test_agregar_multiple_signals(self):
        """Testa agregação com múltiplos sinais."""
        aggregator = SignalAggregator()

        reclame = SinalReclameAqui(
            nota_geral=Decimal("3.0"),
            indice_solucao=Decimal("30"),
            total_reclamacoes=10000,
            reclamacoes_30d=500,
            variacao_30d=Decimal("20"),
        )

        processos = SinalProcessosBC(
            total_processos=5,
            processos_ativos=3,
            valor_total_multas=Decimal("2000000"),
            tipos_processos=["sancionador"],
        )

        secundario = SinalMercadoSecundario(
            pu_medio=Decimal("900"),
            queda_acumulada=Decimal("10"),
            volume_30d=Decimal("20000000"),
            negocios_30d=200,
        )

        signal = aggregator.agregar(
            cnpj="00.000.000/0001-00",
            nome="Banco Risco",
            reclame_aqui=reclame,
            processos_bc=processos,
            mercado_secundario=secundario,
        )

        assert signal.sinais_disponiveis == 3
        assert signal.confianca == 0.75  # 3/4 sinais
        assert signal.nivel_risco != NivelRisco.BAIXO

    def test_agregar_critical_risk(self):
        """Testa agregação com risco crítico."""
        aggregator = SignalAggregator()

        # Todos os sinais indicando alto risco
        reclame = SinalReclameAqui(
            nota_geral=Decimal("2.0"),
            indice_solucao=Decimal("10"),
            total_reclamacoes=20000,
            reclamacoes_30d=2000,
            variacao_30d=Decimal("100"),
        )

        processos = SinalProcessosBC(
            total_processos=20,
            processos_ativos=10,
            valor_total_multas=Decimal("50000000"),
            tipos_processos=["sancionador", "administrativo", "fiscalizacao", "denuncia"],
        )

        secundario = SinalMercadoSecundario(
            pu_medio=Decimal("700"),
            queda_acumulada=Decimal("30"),
            volume_30d=Decimal("100000000"),
            negocios_30d=1000,
        )

        sentimento = SinalSentimento(
            score_medio=Decimal("-0.9"),
            score_ponderado=Decimal("-0.85"),
            total_textos=500,
            textos_negativos=450,
            tendencia="PIORANDO",
        )

        signal = aggregator.agregar(
            cnpj="00.000.000/0001-00",
            nome="Banco Crítico",
            reclame_aqui=reclame,
            processos_bc=processos,
            mercado_secundario=secundario,
            sentimento=sentimento,
        )

        assert signal.sinais_disponiveis == 4
        assert signal.confianca == 1.0
        assert signal.nivel_risco in (NivelRisco.ALTO, NivelRisco.CRITICO)
        assert len(signal.fatores_risco) > 0
        assert len(signal.recomendacoes) > 0


class TestNivelRisco:
    """Testes para enum NivelRisco."""

    def test_nivel_risco_values(self):
        """Verifica valores do enum."""
        assert NivelRisco.BAIXO.value == "BAIXO"
        assert NivelRisco.MODERADO.value == "MODERADO"
        assert NivelRisco.ELEVADO.value == "ELEVADO"
        assert NivelRisco.ALTO.value == "ALTO"
        assert NivelRisco.CRITICO.value == "CRITICO"


class TestTendenciaRisco:
    """Testes para enum TendenciaRisco."""

    def test_tendencia_values(self):
        """Verifica valores do enum."""
        assert TendenciaRisco.MELHORANDO.value == "MELHORANDO"
        assert TendenciaRisco.ESTAVEL.value == "ESTAVEL"
        assert TendenciaRisco.PIORANDO.value == "PIORANDO"
