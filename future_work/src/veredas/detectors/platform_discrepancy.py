"""
Detector de discrepâncias entre plataformas.

Identifica quando a mesma instituição oferece taxas significativamente
diferentes em plataformas distintas, o que pode indicar:
- Erro de atualização em uma das plataformas
- Oferta especial exclusiva
- Problema de precificação
"""

import logging
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from typing import Optional

from veredas import TZ_BRASIL
from veredas.detectors.base import (
    AnomaliaDetectada,
    BaseDetector,
    DetectionResult,
    Severidade,
)
from veredas.storage.models import Indexador, TipoAnomalia

logger = logging.getLogger(__name__)


@dataclass
class TaxaPorPlataforma:
    """Taxa coletada de uma plataforma específica."""

    plataforma: str
    percentual: Decimal
    prazo_dias: int
    indexador: Indexador
    data_coleta: datetime


@dataclass
class DiscrepanciaConfig:
    """Configuração para detecção de discrepâncias."""

    # Diferença mínima em pontos percentuais para considerar discrepância
    threshold_medium: Decimal = Decimal("5")  # 5pp = MEDIUM
    threshold_high: Decimal = Decimal("10")  # 10pp = HIGH
    threshold_critical: Decimal = Decimal("20")  # 20pp = CRITICAL

    # Tolerância para considerar mesmo prazo (dias)
    prazo_tolerance: int = 30

    # Mínimo de plataformas para comparação
    min_plataformas: int = 2


# Alias para compatibilidade
PlatformDiscrepancyConfig = DiscrepanciaConfig


class PlatformDiscrepancyDetector(BaseDetector):
    """
    Detector de discrepâncias entre plataformas.

    Compara taxas da mesma instituição em diferentes corretoras
    e identifica divergências significativas.
    """

    def __init__(self, config: Optional[DiscrepanciaConfig] = None):
        """
        Inicializa o detector.

        Args:
            config: Configuração de thresholds
        """
        self.config = config or DiscrepanciaConfig()

    @property
    def name(self) -> str:
        return "platform_discrepancy"

    @property
    def description(self) -> str:
        return "Detecta diferenças significativas de taxa para a mesma IF em plataformas diferentes"

    def detect(
        self,
        taxas_por_plataforma: dict[str, list[TaxaPorPlataforma]],
    ) -> DetectionResult:
        """
        Detecta discrepâncias entre plataformas.

        Args:
            taxas_por_plataforma: Dict mapeando CNPJ/nome da IF para lista de taxas
                                  coletadas de diferentes plataformas

        Returns:
            DetectionResult com anomalias encontradas
        """
        anomalias: list[AnomaliaDetectada] = []

        for instituicao, taxas in taxas_por_plataforma.items():
            if len(taxas) < self.config.min_plataformas:
                continue

            # Agrupa por indexador e prazo similar
            grupos = self._agrupar_taxas(taxas)

            for grupo_key, grupo_taxas in grupos.items():
                if len(grupo_taxas) < self.config.min_plataformas:
                    continue

                # Encontra discrepâncias no grupo
                discrepancias = self._encontrar_discrepancias(grupo_taxas)

                for disc in discrepancias:
                    anomalia = self._criar_anomalia(instituicao, grupo_key, disc)
                    anomalias.append(anomalia)

        return DetectionResult(
            detector_name=self.name,
            anomalias=anomalias,
            executed_at=datetime.now(TZ_BRASIL),
            execution_time_ms=0,
        )

    def _agrupar_taxas(
        self,
        taxas: list[TaxaPorPlataforma],
    ) -> dict[str, list[TaxaPorPlataforma]]:
        """
        Agrupa taxas por indexador e prazo similar.

        Args:
            taxas: Lista de taxas da mesma instituição

        Returns:
            Dict com chave (indexador, faixa_prazo) e lista de taxas
        """
        grupos: dict[str, list[TaxaPorPlataforma]] = defaultdict(list)

        for taxa in taxas:
            # Normaliza prazo para faixas (30, 90, 180, 360, 720, 1080+)
            faixa = self._normalizar_prazo(taxa.prazo_dias)
            chave = f"{taxa.indexador.value}_{faixa}"
            grupos[chave].append(taxa)

        return dict(grupos)

    def _normalizar_prazo(self, dias: int) -> str:
        """
        Normaliza prazo para faixa.

        M15 FIX: Faixas ajustadas para cobrir todos os prazos típicos de CDB:
        - 1-45 dias: 30d (curto prazo)
        - 46-75 dias: 60d
        - 76-120 dias: 90d
        - 121-270 dias: 180d
        - 271-450 dias: 360d (1 ano)
        - 451-630 dias: 540d (18 meses)
        - 631-900 dias: 720d (2 anos)
        - 901-1260 dias: 1080d (3 anos)
        - 1261+ dias: 1440d+ (4+ anos)
        """
        if dias <= 45:
            return "30d"
        elif dias <= 75:
            return "60d"
        elif dias <= 120:
            return "90d"
        elif dias <= 270:
            return "180d"
        elif dias <= 450:
            return "360d"
        elif dias <= 630:
            return "540d"
        elif dias <= 900:
            return "720d"
        elif dias <= 1260:
            return "1080d"
        else:
            return "1440d+"

    def _encontrar_discrepancias(
        self,
        taxas: list[TaxaPorPlataforma],
    ) -> list[dict]:
        """
        Encontra discrepâncias entre taxas do mesmo grupo.

        Args:
            taxas: Taxas do mesmo indexador/prazo de plataformas diferentes

        Returns:
            Lista de discrepâncias encontradas
        """
        discrepancias = []

        # Ordena por percentual
        taxas_ordenadas = sorted(taxas, key=lambda t: t.percentual, reverse=True)

        # Compara maior com menor
        maior = taxas_ordenadas[0]
        menor = taxas_ordenadas[-1]

        diferenca = maior.percentual - menor.percentual

        if diferenca >= self.config.threshold_medium:
            discrepancias.append({
                "maior": maior,
                "menor": menor,
                "diferenca": diferenca,
                "todas_taxas": taxas_ordenadas,
            })

        return discrepancias

    def _criar_anomalia(
        self,
        instituicao: str,
        grupo_key: str,
        discrepancia: dict,
    ) -> AnomaliaDetectada:
        """
        Cria uma anomalia a partir de uma discrepância.

        Args:
            instituicao: Nome/CNPJ da instituição
            grupo_key: Chave do grupo (indexador_prazo)
            discrepancia: Dados da discrepância

        Returns:
            AnomaliaDetectada
        """
        diferenca = discrepancia["diferenca"]
        maior = discrepancia["maior"]
        menor = discrepancia["menor"]

        # Determina severidade
        if diferenca >= self.config.threshold_critical:
            severidade = Severidade.CRITICAL
        elif diferenca >= self.config.threshold_high:
            severidade = Severidade.HIGH
        else:
            severidade = Severidade.MEDIUM

        # Monta descrição
        descricao = (
            f"Discrepância de {diferenca:.1f}pp entre plataformas para {instituicao}. "
            f"Maior: {maior.percentual}% ({maior.plataforma}), "
            f"Menor: {menor.percentual}% ({menor.plataforma})"
        )

        # Monta evidência
        todas_taxas = discrepancia["todas_taxas"]
        evidencia = {
            "instituicao": instituicao,
            "grupo": grupo_key,
            "diferenca_pp": float(diferenca),
            "taxas": [
                {
                    "plataforma": t.plataforma,
                    "percentual": float(t.percentual),
                    "prazo_dias": t.prazo_dias,
                    "data_coleta": t.data_coleta.isoformat(),
                }
                for t in todas_taxas
            ],
        }

        return AnomaliaDetectada(
            tipo=TipoAnomalia.PLATFORM_DISCREPANCY,
            severidade=severidade,
            valor_detectado=Decimal(str(round(float(diferenca), 2))),
            descricao=descricao,
            if_nome=instituicao,
            detector=self.name,
            detectado_em=datetime.now(TZ_BRASIL),
            detalhes=evidencia,
        )


def comparar_taxas_plataformas(
    taxas_coletadas: list[dict],
    config: Optional[DiscrepanciaConfig] = None,
) -> DetectionResult:
    """
    Função utilitária para comparar taxas de múltiplas plataformas.

    Args:
        taxas_coletadas: Lista de dicts com campos:
            - instituicao: Nome ou CNPJ
            - plataforma: Nome da corretora
            - percentual: Taxa em %
            - prazo_dias: Prazo em dias
            - indexador: Enum Indexador ou string
            - data_coleta: datetime

        config: Configuração opcional

    Returns:
        DetectionResult
    """
    # Agrupa por instituição
    taxas_por_if: dict[str, list[TaxaPorPlataforma]] = defaultdict(list)

    for taxa in taxas_coletadas:
        instituicao = taxa.get("instituicao", "")
        if not instituicao:
            continue

        indexador = taxa.get("indexador")
        if isinstance(indexador, str):
            try:
                indexador = Indexador(indexador.upper())
            except ValueError:
                indexador = Indexador.CDI

        taxas_por_if[instituicao].append(
            TaxaPorPlataforma(
                plataforma=taxa.get("plataforma", "unknown"),
                percentual=Decimal(str(taxa.get("percentual", 0))),
                prazo_dias=int(taxa.get("prazo_dias", 365)),
                indexador=indexador,
                data_coleta=taxa.get("data_coleta", datetime.now(TZ_BRASIL)),
            )
        )

    detector = PlatformDiscrepancyDetector(config)
    return detector.detect(dict(taxas_por_if))
