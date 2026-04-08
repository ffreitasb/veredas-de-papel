"""
Detector de risco baseado em sinais agregados.

Analisa sinais de múltiplas fontes para identificar
instituições com risco elevado.
"""

import logging
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Optional

from veredas import TZ_BRASIL
from veredas.collectors.sentiment.aggregator import (
    NivelRisco,
    RiskSignal,
    SignalAggregator,
    SinalMercadoSecundario,
    SinalProcessosBC,
    SinalReclameAqui,
    SinalSentimento,
)
from veredas.detectors.base import (
    AnomaliaDetectada,
    BaseDetector,
    DetectionResult,
    Severidade,
)
from veredas.storage.models import TipoAnomalia

logger = logging.getLogger(__name__)


@dataclass
class SentimentRiskConfig:
    """Configuração para detecção de risco por sentimento."""

    # Thresholds de score consolidado
    score_medium: float = 40.0  # Score > 40 = MEDIUM
    score_high: float = 60.0  # Score > 60 = HIGH
    score_critical: float = 80.0  # Score > 80 = CRITICAL

    # Mínimo de sinais para alertar
    sinais_minimos: int = 2

    # Weights customizados (opcional)
    weights: Optional[dict[str, float]] = None


class SentimentRiskDetector(BaseDetector):
    """
    Detector de risco baseado em sinais agregados.

    Combina sinais de:
    - Reclame Aqui (reputação)
    - Processos do BC (regulatório)
    - Mercado secundário (preços)
    - Análise de sentimento (mídia/social)
    """

    def __init__(self, config: Optional[SentimentRiskConfig] = None):
        """
        Inicializa o detector.

        Args:
            config: Configuração de thresholds
        """
        self.config = config or SentimentRiskConfig()
        self.aggregator = SignalAggregator(weights=self.config.weights)

    @property
    def name(self) -> str:
        return "sentiment_risk"

    @property
    def description(self) -> str:
        return "Detecta risco elevado baseado em sinais agregados de múltiplas fontes"

    def detect(
        self,
        sinais: list[RiskSignal],
    ) -> DetectionResult:
        """
        Detecta anomalias em sinais de risco.

        Args:
            sinais: Lista de RiskSignal pré-calculados

        Returns:
            DetectionResult com anomalias encontradas
        """
        start_time = datetime.now(TZ_BRASIL)
        anomalias: list[AnomaliaDetectada] = []

        for sinal in sinais:
            # Verifica mínimo de sinais
            if sinal.sinais_disponiveis < self.config.sinais_minimos:
                continue

            # Verifica score consolidado
            if sinal.score_consolidado < self.config.score_medium:
                continue

            # Determina severidade
            if sinal.score_consolidado >= self.config.score_critical:
                severidade = Severidade.CRITICAL
            elif sinal.score_consolidado >= self.config.score_high:
                severidade = Severidade.HIGH
            else:
                severidade = Severidade.MEDIUM

            # Gera descrição
            descricao = self._gerar_descricao(sinal)

            # Determina tipo de anomalia
            tipo = self._determinar_tipo(sinal)

            # Cria anomalia
            anomalia = AnomaliaDetectada(
                tipo=tipo,
                severidade=severidade,
                valor_detectado=Decimal(str(round(sinal.score_consolidado, 2))),
                descricao=descricao,
                if_nome=sinal.instituicao_nome,
                detector=self.name,
                detectado_em=datetime.now(TZ_BRASIL),
                detalhes=self._gerar_evidencia(sinal),
            )
            anomalias.append(anomalia)

        elapsed = (datetime.now(TZ_BRASIL) - start_time).total_seconds() * 1000

        return DetectionResult(
            detector_name=self.name,
            anomalias=anomalias,
            executed_at=datetime.now(TZ_BRASIL),
            execution_time_ms=elapsed,
        )

    def detect_from_raw(
        self,
        dados: list[dict],
    ) -> DetectionResult:
        """
        Detecta anomalias a partir de dados brutos.

        Args:
            dados: Lista de dicts com dados por instituição
                Cada dict deve conter:
                - cnpj: str
                - nome: str
                - reclame_aqui: dict (opcional)
                - processos_bc: dict (opcional)
                - mercado_secundario: dict (opcional)
                - sentimento: dict (opcional)

        Returns:
            DetectionResult
        """
        sinais = []

        for item in dados:
            try:
                # Converte dados brutos para sinais tipados
                reclame_aqui = None
                if "reclame_aqui" in item and item["reclame_aqui"]:
                    ra = item["reclame_aqui"]
                    reclame_aqui = SinalReclameAqui(
                        nota_geral=Decimal(str(ra.get("nota_geral", 0))),
                        indice_solucao=Decimal(str(ra.get("indice_solucao", 0))),
                        total_reclamacoes=int(ra.get("total_reclamacoes", 0)),
                        reclamacoes_30d=int(ra.get("reclamacoes_30d", 0)),
                        variacao_30d=Decimal(str(ra.get("variacao_30d", 0))),
                    )

                processos_bc = None
                if "processos_bc" in item and item["processos_bc"]:
                    pb = item["processos_bc"]
                    processos_bc = SinalProcessosBC(
                        total_processos=int(pb.get("total_processos", 0)),
                        processos_ativos=int(pb.get("processos_ativos", 0)),
                        valor_total_multas=Decimal(str(pb.get("valor_total_multas", 0))),
                        tipos_processos=pb.get("tipos_processos", []),
                    )

                mercado_secundario = None
                if "mercado_secundario" in item and item["mercado_secundario"]:
                    ms = item["mercado_secundario"]
                    mercado_secundario = SinalMercadoSecundario(
                        pu_medio=Decimal(str(ms.get("pu_medio", 1000))),
                        queda_acumulada=Decimal(str(ms.get("queda_acumulada", 0))),
                        volume_30d=Decimal(str(ms.get("volume_30d", 0))),
                        negocios_30d=int(ms.get("negocios_30d", 0)),
                    )

                sentimento = None
                if "sentimento" in item and item["sentimento"]:
                    s = item["sentimento"]
                    sentimento = SinalSentimento(
                        score_medio=Decimal(str(s.get("score_medio", 0))),
                        score_ponderado=Decimal(str(s.get("score_ponderado", 0))),
                        total_textos=int(s.get("total_textos", 0)),
                        textos_negativos=int(s.get("textos_negativos", 0)),
                        tendencia=s.get("tendencia", "ESTAVEL"),
                    )

                # Agrega sinais
                sinal = self.aggregator.agregar(
                    cnpj=item.get("cnpj", ""),
                    nome=item.get("nome", ""),
                    reclame_aqui=reclame_aqui,
                    processos_bc=processos_bc,
                    mercado_secundario=mercado_secundario,
                    sentimento=sentimento,
                )
                sinais.append(sinal)

            except Exception as e:
                logger.warning(f"Erro ao processar dados para {item.get('nome')}: {e}")
                continue

        return self.detect(sinais)

    def _determinar_tipo(self, sinal: RiskSignal) -> TipoAnomalia:
        """Determina o tipo de anomalia baseado nos sinais."""
        # Se o score consolidado é crítico, usa tipo genérico
        if sinal.nivel_risco == NivelRisco.CRITICO:
            return TipoAnomalia.COMPOSITE_RISK_CRITICAL

        # Identifica o sinal dominante
        scores = {
            TipoAnomalia.NEGATIVE_SENTIMENT: sinal.score_sentimento or 0,
            TipoAnomalia.COMPLAINT_SPIKE: sinal.score_reclame_aqui or 0,
            TipoAnomalia.REGULATORY_PROCESS: sinal.score_processos_bc or 0,
            TipoAnomalia.SECONDARY_PRICE_DROP: sinal.score_mercado_secundario or 0,
        }

        # Retorna o tipo com maior score
        return max(scores, key=scores.get)

    def _gerar_descricao(self, sinal: RiskSignal) -> str:
        """Gera descrição da anomalia."""
        partes = [
            f"Risco {sinal.nivel_risco.value} identificado para {sinal.instituicao_nome}"
        ]

        if sinal.fatores_risco:
            partes.append(f"Fatores: {', '.join(sinal.fatores_risco[:3])}")

        return ". ".join(partes)

    def _gerar_evidencia(self, sinal: RiskSignal) -> dict:
        """Gera dict de evidência."""
        evidencia = {
            "instituicao": sinal.instituicao_nome,
            "cnpj": sinal.instituicao_cnpj,
            "score_consolidado": sinal.score_consolidado,
            "nivel_risco": sinal.nivel_risco.value,
            "confianca": sinal.confianca,
            "sinais_disponiveis": sinal.sinais_disponiveis,
            "fatores_risco": sinal.fatores_risco,
            "recomendacoes": sinal.recomendacoes,
        }

        # Adiciona scores individuais
        if sinal.score_reclame_aqui is not None:
            evidencia["score_reclame_aqui"] = sinal.score_reclame_aqui

        if sinal.score_processos_bc is not None:
            evidencia["score_processos_bc"] = sinal.score_processos_bc

        if sinal.score_mercado_secundario is not None:
            evidencia["score_mercado_secundario"] = sinal.score_mercado_secundario

        if sinal.score_sentimento is not None:
            evidencia["score_sentimento"] = sinal.score_sentimento

        return evidencia


def detectar_risco_sentimento(
    dados: list[dict],
    config: Optional[SentimentRiskConfig] = None,
) -> DetectionResult:
    """
    Função utilitária para detecção de risco por sentimento.

    Args:
        dados: Lista de dicts com dados por instituição
        config: Configuração opcional

    Returns:
        DetectionResult
    """
    detector = SentimentRiskDetector(config)
    return detector.detect_from_raw(dados)
