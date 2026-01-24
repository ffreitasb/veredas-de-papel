"""
Agregador de sinais de risco para instituições financeiras.

Combina sinais de múltiplas fontes em um score de risco consolidado:
- Reclame Aqui (reputação e reclamações)
- Processos administrativos do BC
- Mercado secundário (preços e volume)
- Análise de sentimento
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import Optional

from veredas import TZ_BRASIL

logger = logging.getLogger(__name__)


class NivelRisco(str, Enum):
    """Classificação de nível de risco."""

    BAIXO = "BAIXO"
    MODERADO = "MODERADO"
    ELEVADO = "ELEVADO"
    ALTO = "ALTO"
    CRITICO = "CRITICO"


class TendenciaRisco(str, Enum):
    """Tendência do risco ao longo do tempo."""

    MELHORANDO = "MELHORANDO"
    ESTAVEL = "ESTAVEL"
    PIORANDO = "PIORANDO"


@dataclass
class SinalReclameAqui:
    """Sinal de risco baseado no Reclame Aqui."""

    nota_geral: Decimal  # 0-10
    indice_solucao: Decimal  # 0-100%
    total_reclamacoes: int
    reclamacoes_30d: int
    variacao_30d: Decimal  # Variação percentual

    # Score normalizado (0-100, maior = mais risco)
    score: float = 0.0

    def calcular_score(self) -> float:
        """Calcula score de risco normalizado."""
        # Nota invertida (10 = bom -> 0 risco, 0 = ruim -> 100 risco)
        score_nota = (10 - float(self.nota_geral)) * 10

        # Índice de solução invertido
        score_solucao = 100 - float(self.indice_solucao)

        # Volume de reclamações (normalizado)
        score_volume = min(100, self.reclamacoes_30d / 10)

        # Tendência (variação positiva = mais reclamações = mais risco)
        score_tendencia = min(100, max(-100, float(self.variacao_30d)))
        score_tendencia = (score_tendencia + 100) / 2  # Normaliza para 0-100

        # Peso: nota (40%), solução (30%), volume (20%), tendência (10%)
        self.score = (
            score_nota * 0.4
            + score_solucao * 0.3
            + score_volume * 0.2
            + score_tendencia * 0.1
        )

        return self.score


@dataclass
class SinalProcessosBC:
    """Sinal de risco baseado em processos do BC."""

    total_processos: int
    processos_ativos: int
    valor_total_multas: Decimal
    tipos_processos: list[str]

    # Score normalizado
    score: float = 0.0

    def calcular_score(self) -> float:
        """Calcula score de risco normalizado."""
        # Processos ativos (alto peso)
        score_ativos = min(100, self.processos_ativos * 20)

        # Valor de multas (normalizado por R$ 1M)
        valor_normalizado = float(self.valor_total_multas) / 1_000_000
        score_multas = min(100, valor_normalizado * 10)

        # Tipos de processos (mais tipos = mais problemas)
        score_tipos = min(100, len(self.tipos_processos) * 15)

        # Peso: ativos (50%), multas (30%), tipos (20%)
        self.score = (
            score_ativos * 0.5
            + score_multas * 0.3
            + score_tipos * 0.2
        )

        return self.score


@dataclass
class SinalMercadoSecundario:
    """Sinal de risco baseado no mercado secundário."""

    pu_medio: Decimal  # Preço unitário médio
    queda_acumulada: Decimal  # Queda em % vs nominal
    volume_30d: Decimal  # Volume negociado
    negocios_30d: int  # Quantidade de negócios

    # Score normalizado
    score: float = 0.0

    def calcular_score(self) -> float:
        """Calcula score de risco normalizado."""
        # Queda de preço (principal indicador)
        # Queda > 0 indica PU abaixo do nominal
        score_queda = min(100, max(0, float(self.queda_acumulada) * 5))

        # Volume alto pode indicar saída de investidores
        # Volume normalizado por R$ 10M
        volume_normalizado = float(self.volume_30d) / 10_000_000
        score_volume = min(100, volume_normalizado * 20)

        # Muitos negócios pequenos podem indicar panic selling
        if self.negocios_30d > 0 and float(self.volume_30d) > 0:
            ticket_medio = float(self.volume_30d) / self.negocios_30d
            # Ticket médio baixo (< R$ 50k) = mais risco
            score_ticket = min(100, max(0, (50_000 - ticket_medio) / 500))
        else:
            score_ticket = 0

        # Peso: queda (60%), volume (25%), ticket (15%)
        self.score = (
            score_queda * 0.6
            + score_volume * 0.25
            + score_ticket * 0.15
        )

        return self.score


@dataclass
class SinalSentimento:
    """Sinal de risco baseado em análise de sentimento."""

    score_medio: Decimal  # -1 a +1
    score_ponderado: Decimal  # Ponderado por confiança
    total_textos: int
    textos_negativos: int
    tendencia: str  # MELHORANDO, ESTAVEL, PIORANDO

    # Score normalizado
    score: float = 0.0

    def calcular_score(self) -> float:
        """Calcula score de risco normalizado."""
        # Score invertido e normalizado
        # -1 (muito negativo) -> 100, +1 (muito positivo) -> 0
        score_sentimento = (1 - float(self.score_ponderado)) * 50

        # Proporção de textos negativos
        if self.total_textos > 0:
            prop_negativos = self.textos_negativos / self.total_textos
            score_negativos = prop_negativos * 100
        else:
            score_negativos = 50  # Neutro sem dados

        # Tendência
        if self.tendencia == "PIORANDO":
            score_tendencia = 80
        elif self.tendencia == "ESTAVEL":
            score_tendencia = 50
        else:  # MELHORANDO
            score_tendencia = 20

        # Confiança baseada no volume de textos
        confianca = min(1.0, self.total_textos / 50)

        # Score base com peso da confiança
        score_base = (
            score_sentimento * 0.5
            + score_negativos * 0.3
            + score_tendencia * 0.2
        )

        # Ajusta pela confiança (menos textos = score tende ao neutro)
        self.score = score_base * confianca + 50 * (1 - confianca)

        return self.score


@dataclass
class RiskSignal:
    """Sinal de risco consolidado para uma instituição."""

    instituicao_cnpj: str
    instituicao_nome: str

    # Sinais individuais (opcionais)
    sinal_reclame_aqui: Optional[SinalReclameAqui] = None
    sinal_processos_bc: Optional[SinalProcessosBC] = None
    sinal_mercado_secundario: Optional[SinalMercadoSecundario] = None
    sinal_sentimento: Optional[SinalSentimento] = None

    # Scores normalizados (0-100)
    score_reclame_aqui: Optional[float] = None
    score_processos_bc: Optional[float] = None
    score_mercado_secundario: Optional[float] = None
    score_sentimento: Optional[float] = None

    # Score consolidado
    score_consolidado: float = 0.0
    nivel_risco: NivelRisco = NivelRisco.BAIXO
    tendencia: TendenciaRisco = TendenciaRisco.ESTAVEL

    # Metadata
    sinais_disponiveis: int = 0
    confianca: float = 0.0
    calculado_em: datetime = field(default_factory=lambda: datetime.now(TZ_BRASIL))

    # Detalhes
    fatores_risco: list[str] = field(default_factory=list)
    recomendacoes: list[str] = field(default_factory=list)


class SignalAggregator:
    """
    Agregador de sinais de risco.

    Combina múltiplas fontes de dados em um score de risco consolidado
    usando pesos configuráveis.
    """

    # Pesos padrão para cada fonte
    DEFAULT_WEIGHTS = {
        "reclame_aqui": 0.20,
        "processos_bc": 0.30,
        "mercado_secundario": 0.35,
        "sentimento": 0.15,
    }

    # Thresholds para classificação de risco
    THRESHOLDS = {
        "baixo": 20,
        "moderado": 40,
        "elevado": 60,
        "alto": 80,
    }

    def __init__(
        self,
        weights: Optional[dict[str, float]] = None,
        thresholds: Optional[dict[str, float]] = None,
    ):
        """
        Inicializa o agregador.

        Args:
            weights: Pesos customizados para cada fonte
            thresholds: Thresholds customizados para classificação
        """
        self.weights = weights or self.DEFAULT_WEIGHTS.copy()
        self.thresholds = thresholds or self.THRESHOLDS.copy()

        # Normaliza pesos para somar 1
        total = sum(self.weights.values())
        if total > 0:
            self.weights = {k: v / total for k, v in self.weights.items()}

    def agregar(
        self,
        cnpj: str,
        nome: str,
        reclame_aqui: Optional[SinalReclameAqui] = None,
        processos_bc: Optional[SinalProcessosBC] = None,
        mercado_secundario: Optional[SinalMercadoSecundario] = None,
        sentimento: Optional[SinalSentimento] = None,
    ) -> RiskSignal:
        """
        Agrega sinais de múltiplas fontes.

        Args:
            cnpj: CNPJ da instituição
            nome: Nome da instituição
            reclame_aqui: Sinal do Reclame Aqui
            processos_bc: Sinal de processos do BC
            mercado_secundario: Sinal do mercado secundário
            sentimento: Sinal de sentimento

        Returns:
            RiskSignal consolidado
        """
        signal = RiskSignal(
            instituicao_cnpj=cnpj,
            instituicao_nome=nome,
            sinal_reclame_aqui=reclame_aqui,
            sinal_processos_bc=processos_bc,
            sinal_mercado_secundario=mercado_secundario,
            sinal_sentimento=sentimento,
        )

        scores = []
        pesos_usados = []
        fatores = []

        # Processa cada sinal disponível
        if reclame_aqui:
            score = reclame_aqui.calcular_score()
            signal.score_reclame_aqui = score
            scores.append(score)
            pesos_usados.append(self.weights["reclame_aqui"])
            signal.sinais_disponiveis += 1

            if score > 60:
                fatores.append(f"Reputação baixa no Reclame Aqui (score: {score:.0f})")
            if reclame_aqui.reclamacoes_30d > 100:
                fatores.append(f"Alto volume de reclamações recentes ({reclame_aqui.reclamacoes_30d})")

        if processos_bc:
            score = processos_bc.calcular_score()
            signal.score_processos_bc = score
            scores.append(score)
            pesos_usados.append(self.weights["processos_bc"])
            signal.sinais_disponiveis += 1

            if score > 60:
                fatores.append(f"Processos regulatórios ativos ({processos_bc.processos_ativos})")
            if float(processos_bc.valor_total_multas) > 1_000_000:
                fatores.append(f"Multas significativas (R$ {processos_bc.valor_total_multas:,.2f})")

        if mercado_secundario:
            score = mercado_secundario.calcular_score()
            signal.score_mercado_secundario = score
            scores.append(score)
            pesos_usados.append(self.weights["mercado_secundario"])
            signal.sinais_disponiveis += 1

            if score > 60:
                fatores.append(f"Pressão no mercado secundário (queda: {mercado_secundario.queda_acumulada:.1f}%)")
            if float(mercado_secundario.queda_acumulada) > 5:
                fatores.append(f"PU significativamente abaixo do nominal")

        if sentimento:
            score = sentimento.calcular_score()
            signal.score_sentimento = score
            scores.append(score)
            pesos_usados.append(self.weights["sentimento"])
            signal.sinais_disponiveis += 1

            if score > 60:
                fatores.append(f"Sentimento negativo detectado (score: {score:.0f})")
            if sentimento.tendencia == "PIORANDO":
                fatores.append("Tendência de sentimento piorando")

        signal.fatores_risco = fatores

        # Calcula score consolidado
        if scores:
            # Normaliza pesos usados
            total_peso = sum(pesos_usados)
            pesos_norm = [p / total_peso for p in pesos_usados]

            # Média ponderada
            signal.score_consolidado = sum(
                s * p for s, p in zip(scores, pesos_norm)
            )

            # Confiança baseada no número de sinais
            signal.confianca = signal.sinais_disponiveis / 4

        # Classifica nível de risco
        signal.nivel_risco = self._classificar_risco(signal.score_consolidado)

        # Gera recomendações
        signal.recomendacoes = self._gerar_recomendacoes(signal)

        return signal

    def _classificar_risco(self, score: float) -> NivelRisco:
        """Classifica o nível de risco baseado no score."""
        if score < self.thresholds["baixo"]:
            return NivelRisco.BAIXO
        elif score < self.thresholds["moderado"]:
            return NivelRisco.MODERADO
        elif score < self.thresholds["elevado"]:
            return NivelRisco.ELEVADO
        elif score < self.thresholds["alto"]:
            return NivelRisco.ALTO
        else:
            return NivelRisco.CRITICO

    def _gerar_recomendacoes(self, signal: RiskSignal) -> list[str]:
        """Gera recomendações baseadas no nível de risco."""
        recomendacoes = []

        if signal.nivel_risco == NivelRisco.BAIXO:
            recomendacoes.append("Monitoramento padrão recomendado")

        elif signal.nivel_risco == NivelRisco.MODERADO:
            recomendacoes.append("Aumentar frequência de monitoramento")
            recomendacoes.append("Verificar limite de exposição")

        elif signal.nivel_risco == NivelRisco.ELEVADO:
            recomendacoes.append("Monitoramento intensivo recomendado")
            recomendacoes.append("Reduzir exposição gradualmente")
            recomendacoes.append("Verificar garantias e colaterais")

        elif signal.nivel_risco == NivelRisco.ALTO:
            recomendacoes.append("ATENÇÃO: Risco alto identificado")
            recomendacoes.append("Avaliar redução imediata de exposição")
            recomendacoes.append("Notificar gestão de risco")

        elif signal.nivel_risco == NivelRisco.CRITICO:
            recomendacoes.append("ALERTA CRÍTICO")
            recomendacoes.append("Suspender novas operações")
            recomendacoes.append("Avaliar liquidação de posições")
            recomendacoes.append("Escalação imediata para diretoria")

        # Recomendações específicas por fonte
        if signal.score_reclame_aqui and signal.score_reclame_aqui > 70:
            recomendacoes.append("Monitorar resolução de reclamações")

        if signal.score_processos_bc and signal.score_processos_bc > 70:
            recomendacoes.append("Acompanhar andamento de processos no BC")

        if signal.score_mercado_secundario and signal.score_mercado_secundario > 70:
            recomendacoes.append("Verificar liquidez e spread de títulos")

        return recomendacoes

    def comparar_historico(
        self,
        atual: RiskSignal,
        anterior: RiskSignal,
    ) -> TendenciaRisco:
        """
        Compara sinal atual com anterior para determinar tendência.

        Args:
            atual: Sinal atual
            anterior: Sinal anterior

        Returns:
            Tendência do risco
        """
        diff = atual.score_consolidado - anterior.score_consolidado

        if diff < -5:
            return TendenciaRisco.MELHORANDO
        elif diff > 5:
            return TendenciaRisco.PIORANDO
        else:
            return TendenciaRisco.ESTAVEL

    def agregar_lote(
        self,
        dados: list[dict],
    ) -> list[RiskSignal]:
        """
        Agrega sinais para múltiplas instituições.

        Args:
            dados: Lista de dicts com dados por instituição

        Returns:
            Lista de RiskSignal
        """
        sinais = []

        for item in dados:
            try:
                sinal = self.agregar(
                    cnpj=item.get("cnpj", ""),
                    nome=item.get("nome", ""),
                    reclame_aqui=item.get("reclame_aqui"),
                    processos_bc=item.get("processos_bc"),
                    mercado_secundario=item.get("mercado_secundario"),
                    sentimento=item.get("sentimento"),
                )
                sinais.append(sinal)

            except Exception as e:
                logger.warning(f"Erro ao agregar sinal para {item.get('nome')}: {e}")
                continue

        # Ordena por score (maior risco primeiro)
        sinais.sort(key=lambda s: s.score_consolidado, reverse=True)

        return sinais
