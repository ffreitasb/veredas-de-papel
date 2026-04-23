"""
Detectores de saúde financeira baseados em dados IFData.

Detecta anomalias cruzando taxas de CDB com indicadores de capitalização
e liquidez das instituições financeiras (Índice de Basileia, Liquidez).
"""

from collections.abc import Sequence
from dataclasses import dataclass
from decimal import Decimal

from veredas.detectors.base import AnomaliaDetectada, DetectionResult
from veredas.storage.models import HealthDataIF, Severidade, TaxaCDB, TipoAnomalia


@dataclass
class HealthThresholds:
    """Thresholds para detectores de saúde financeira."""

    # Basileia: mínimo regulatório Brasil é 8%, alerta em 11%, crítico em 9%
    basileia_alerta: Decimal = Decimal("11.0")
    basileia_critico: Decimal = Decimal("9.0")

    # Taxa mínima para acionar detector de Basileia (só alerta se taxa estiver elevada)
    taxa_minima_cdi: Decimal = Decimal("120.0")

    # Liquidez: mínimo regulatório é 100% (LCR), alerta em 110%, crítico em 100%
    liquidez_alerta: Decimal = Decimal("110.0")
    liquidez_critico: Decimal = Decimal("100.0")

    # Taxa mínima para acionar detector de liquidez
    taxa_minima_liquidez: Decimal = Decimal("115.0")


class BasileiaBaixoDetector:
    """
    Detecta IFs com Índice de Basileia baixo e taxa CDB elevada.

    A combinação é o sinal mais forte do sistema: a IF está captando acima
    da média (taxa alta) enquanto seu capital regulatório está próximo do mínimo.
    """

    def __init__(self, thresholds: HealthThresholds | None = None):
        self.thresholds = thresholds or HealthThresholds()

    @property
    def name(self) -> str:
        return "basileia_baixo_detector"

    def detect(
        self,
        taxas: Sequence[TaxaCDB],
        health_data: Sequence[HealthDataIF],
    ) -> DetectionResult:
        """
        Detecta anomalias de Basileia baixo cruzando taxas com saúde financeira.

        Args:
            taxas: Taxas de CDB mais recentes (uma por IF).
            health_data: Snapshots de saúde (um por IF, o mais recente).

        Returns:
            DetectionResult com anomalias encontradas.
        """
        anomalias: list[AnomaliaDetectada] = []

        # Indexar health data por if_id
        health_by_if: dict[int, HealthDataIF] = {h.if_id: h for h in health_data}

        # Agrupar taxa mais alta por IF
        taxa_max_by_if: dict[int, TaxaCDB] = {}
        for taxa in taxas:
            if (
                taxa.if_id not in taxa_max_by_if
                or taxa.percentual > taxa_max_by_if[taxa.if_id].percentual
            ):
                taxa_max_by_if[taxa.if_id] = taxa

        for if_id, taxa in taxa_max_by_if.items():
            health = health_by_if.get(if_id)
            if not health or health.indice_basileia is None:
                continue

            basileia = health.indice_basileia

            # Só aciona se a taxa estiver elevada
            if taxa.percentual <= self.thresholds.taxa_minima_cdi:
                continue

            if basileia < self.thresholds.basileia_critico:
                severidade = Severidade.CRITICAL
                tipo = TipoAnomalia.BASILEIA_BAIXO
            elif basileia < self.thresholds.basileia_alerta:
                severidade = Severidade.HIGH
                tipo = TipoAnomalia.BASILEIA_BAIXO
            else:
                continue

            descricao = (
                f"Taxa CDB de {taxa.percentual:.1f}% CDI com Basileia de "
                f"{basileia:.1f}% (mínimo alertar: {self.thresholds.basileia_alerta}%)"
            )

            anomalias.append(
                AnomaliaDetectada(
                    tipo=tipo,
                    severidade=severidade,
                    valor_detectado=taxa.percentual,
                    descricao=descricao,
                    if_id=if_id,
                    taxa_id=taxa.id,
                    valor_esperado=self.thresholds.basileia_alerta,
                    threshold=self.thresholds.basileia_alerta,
                    detector=self.name,
                    detalhes={
                        "indice_basileia": float(basileia),
                        "taxa_percentual": float(taxa.percentual),
                        "data_base_saude": str(health.data_base),
                    },
                )
            )

        return DetectionResult(
            detector_name=self.name,
            anomalias=anomalias,
        )


class LiquidezCriticaDetector:
    """
    Detecta IFs com liquidez abaixo do mínimo regulatório e taxa elevada.

    Sinal: a IF está captando ativamente (taxa alta) enquanto sua posição
    de liquidez está abaixo do LCR mínimo regulatório.
    """

    def __init__(self, thresholds: HealthThresholds | None = None):
        self.thresholds = thresholds or HealthThresholds()

    @property
    def name(self) -> str:
        return "liquidez_critica_detector"

    def detect(
        self,
        taxas: Sequence[TaxaCDB],
        health_data: Sequence[HealthDataIF],
    ) -> DetectionResult:
        """
        Detecta anomalias de liquidez crítica cruzando taxas com saúde financeira.

        Args:
            taxas: Taxas de CDB mais recentes (uma por IF).
            health_data: Snapshots de saúde (um por IF, o mais recente).

        Returns:
            DetectionResult com anomalias encontradas.
        """
        anomalias: list[AnomaliaDetectada] = []

        health_by_if: dict[int, HealthDataIF] = {h.if_id: h for h in health_data}

        taxa_max_by_if: dict[int, TaxaCDB] = {}
        for taxa in taxas:
            if (
                taxa.if_id not in taxa_max_by_if
                or taxa.percentual > taxa_max_by_if[taxa.if_id].percentual
            ):
                taxa_max_by_if[taxa.if_id] = taxa

        for if_id, taxa in taxa_max_by_if.items():
            health = health_by_if.get(if_id)
            if not health or health.indice_liquidez is None:
                continue

            liquidez = health.indice_liquidez

            # Só aciona se a taxa estiver elevada
            if taxa.percentual <= self.thresholds.taxa_minima_liquidez:
                continue

            if liquidez < self.thresholds.liquidez_critico:
                severidade = Severidade.CRITICAL
            elif liquidez < self.thresholds.liquidez_alerta:
                severidade = Severidade.HIGH
            else:
                continue

            descricao = (
                f"Taxa CDB de {taxa.percentual:.1f}% CDI com Liquidez de "
                f"{liquidez:.1f}% (mínimo regulatório: {self.thresholds.liquidez_critico}%)"
            )

            anomalias.append(
                AnomaliaDetectada(
                    tipo=TipoAnomalia.LIQUIDEZ_CRITICA,
                    severidade=severidade,
                    valor_detectado=taxa.percentual,
                    descricao=descricao,
                    if_id=if_id,
                    taxa_id=taxa.id,
                    valor_esperado=self.thresholds.liquidez_alerta,
                    threshold=self.thresholds.liquidez_alerta,
                    detector=self.name,
                    detalhes={
                        "indice_liquidez": float(liquidez),
                        "taxa_percentual": float(taxa.percentual),
                        "data_base_saude": str(health.data_base),
                    },
                )
            )

        return DetectionResult(
            detector_name=self.name,
            anomalias=anomalias,
        )
