"""
Detector de quedas de preço no mercado secundário.

Monitora o PU (Preço Unitário) de títulos no mercado secundário
e identifica quedas significativas que podem indicar:
- Deterioração da qualidade de crédito do emissor
- Necessidade de liquidação forçada
- Percepção de risco elevado pelo mercado
"""

import logging
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from typing import Optional

from veredas import TZ_BRASIL
from veredas.collectors.b3.models import PrecoSecundario
from veredas.detectors.base import (
    AnomaliaDetectada,
    BaseDetector,
    DetectionResult,
    Severidade,
)
from veredas.storage.models import TipoAnomalia

logger = logging.getLogger(__name__)


@dataclass
class PriceDropConfig:
    """Configuração para detecção de quedas de preço."""

    # M13 FIX: Valor nominal configurável (padrão R$ 1000 para CDBs)
    valor_nominal: Decimal = Decimal("1000")

    # Queda em relação ao PU de emissão (valor nominal)
    queda_medium: Decimal = Decimal("5")  # > 5% = MEDIUM
    queda_high: Decimal = Decimal("10")  # > 10% = HIGH
    queda_critical: Decimal = Decimal("20")  # > 20% = CRITICAL

    # Queda diária (variação em um dia)
    queda_diaria_medium: Decimal = Decimal("2")  # > 2% = MEDIUM
    queda_diaria_high: Decimal = Decimal("5")  # > 5% = HIGH
    queda_diaria_critical: Decimal = Decimal("10")  # > 10% = CRITICAL

    # Volume mínimo para considerar
    volume_minimo: Decimal = Decimal("100000")  # R$ 100k

    # Número mínimo de negócios
    negocios_minimo: int = 3


class PriceDropDetector(BaseDetector):
    """
    Detector de quedas de preço no mercado secundário.

    Identifica títulos com:
    1. Queda significativa do PU em relação ao valor de emissão
    2. Queda abrupta em um único dia
    3. Padrão de quedas consecutivas
    """

    def __init__(self, config: Optional[PriceDropConfig] = None):
        """
        Inicializa o detector.

        Args:
            config: Configuração de thresholds
        """
        self.config = config or PriceDropConfig()

    @property
    def name(self) -> str:
        return "price_drop"

    @property
    def description(self) -> str:
        return "Detecta quedas significativas de preço no mercado secundário"

    def detect(
        self,
        precos: list[PrecoSecundario],
        precos_anteriores: Optional[dict[str, Decimal]] = None,
    ) -> DetectionResult:
        """
        Detecta quedas de preço.

        Args:
            precos: Lista de preços do dia atual
            precos_anteriores: Dict mapeando código_titulo -> PU do dia anterior

        Returns:
            DetectionResult com anomalias encontradas
        """
        anomalias: list[AnomaliaDetectada] = []

        for preco in precos:
            # Filtra por volume mínimo
            if preco.valor_financeiro < self.config.volume_minimo:
                continue

            if preco.quantidade_negocios < self.config.negocios_minimo:
                continue

            # Verifica queda em relação ao valor nominal (1000)
            anomalia_nominal = self._verificar_queda_nominal(preco)
            if anomalia_nominal:
                anomalias.append(anomalia_nominal)

            # Verifica variação diária
            if preco.variacao_dia is not None:
                anomalia_diaria = self._verificar_queda_diaria(preco)
                if anomalia_diaria:
                    anomalias.append(anomalia_diaria)

            # Verifica contra preço anterior (se disponível)
            if precos_anteriores and preco.codigo_titulo in precos_anteriores:
                pu_anterior = precos_anteriores[preco.codigo_titulo]
                anomalia_comparativa = self._verificar_queda_comparativa(
                    preco, pu_anterior
                )
                if anomalia_comparativa:
                    anomalias.append(anomalia_comparativa)

        return DetectionResult(
            detector_name=self.name,
            anomalias=anomalias,
            executed_at=datetime.now(TZ_BRASIL),
            execution_time_ms=0,
        )

    def _verificar_queda_nominal(
        self,
        preco: PrecoSecundario,
    ) -> Optional[AnomaliaDetectada]:
        """
        Verifica queda em relação ao valor nominal.

        O PU de um CDB deveria, em condições normais, estar próximo
        ou acima do valor nominal. Quedas significativas indicam
        que o mercado está precificando risco adicional.
        """
        # M13 FIX: Usa valor nominal configurável
        valor_nominal = self.config.valor_nominal
        pu = preco.pu_fechamento

        if pu >= valor_nominal:
            return None

        queda_percentual = ((valor_nominal - pu) / valor_nominal) * 100

        # Determina severidade
        if queda_percentual >= self.config.queda_critical:
            severidade = Severidade.CRITICAL
        elif queda_percentual >= self.config.queda_high:
            severidade = Severidade.HIGH
        elif queda_percentual >= self.config.queda_medium:
            severidade = Severidade.MEDIUM
        else:
            return None

        descricao = (
            f"PU de {preco.emissor_nome} negociado a R$ {pu:.2f} "
            f"({queda_percentual:.1f}% abaixo do valor nominal)"
        )

        return AnomaliaDetectada(
            tipo=TipoAnomalia.SECONDARY_PRICE_DROP,
            severidade=severidade,
            valor_detectado=Decimal(str(round(float(queda_percentual), 2))),
            descricao=descricao,
            if_nome=preco.emissor_nome,
            detector=self.name,
            detectado_em=datetime.now(TZ_BRASIL),
            detalhes={
                "codigo_titulo": preco.codigo_titulo,
                "emissor": preco.emissor_nome,
                "emissor_cnpj": preco.emissor_cnpj,
                "pu_fechamento": float(pu),
                "valor_nominal": float(valor_nominal),
                "queda_percentual": float(queda_percentual),
                "volume": float(preco.valor_financeiro),
                "negocios": preco.quantidade_negocios,
                "data_referencia": preco.data_referencia.isoformat(),
            },
        )

    def _verificar_queda_diaria(
        self,
        preco: PrecoSecundario,
    ) -> Optional[AnomaliaDetectada]:
        """
        Verifica queda abrupta no dia.

        Quedas significativas em um único dia podem indicar
        eventos negativos repentinos (notícias, rebaixamento, etc).
        """
        variacao = preco.variacao_dia

        if variacao is None or variacao >= 0:
            return None

        queda = abs(variacao)

        # Determina severidade
        if queda >= self.config.queda_diaria_critical:
            severidade = Severidade.CRITICAL
        elif queda >= self.config.queda_diaria_high:
            severidade = Severidade.HIGH
        elif queda >= self.config.queda_diaria_medium:
            severidade = Severidade.MEDIUM
        else:
            return None

        descricao = (
            f"Queda de {queda:.1f}% no dia para títulos de {preco.emissor_nome}"
        )

        return AnomaliaDetectada(
            tipo=TipoAnomalia.SECONDARY_DAILY_DROP,
            severidade=severidade,
            valor_detectado=Decimal(str(round(float(queda), 2))),
            descricao=descricao,
            if_nome=preco.emissor_nome,
            detector=self.name,
            detectado_em=datetime.now(TZ_BRASIL),
            detalhes={
                "codigo_titulo": preco.codigo_titulo,
                "emissor": preco.emissor_nome,
                "emissor_cnpj": preco.emissor_cnpj,
                "pu_abertura": float(preco.pu_abertura),
                "pu_fechamento": float(preco.pu_fechamento),
                "variacao_dia": float(variacao),
                "volume": float(preco.valor_financeiro),
                "data_referencia": preco.data_referencia.isoformat(),
            },
        )

    def _verificar_queda_comparativa(
        self,
        preco: PrecoSecundario,
        pu_anterior: Decimal,
    ) -> Optional[AnomaliaDetectada]:
        """
        Verifica queda em relação ao preço anterior.

        Compara com o PU do dia útil anterior.
        """
        pu_atual = preco.pu_fechamento

        if pu_atual >= pu_anterior:
            return None

        queda = ((pu_anterior - pu_atual) / pu_anterior) * 100

        # Usa thresholds de queda diária
        if queda >= self.config.queda_diaria_critical:
            severidade = Severidade.CRITICAL
        elif queda >= self.config.queda_diaria_high:
            severidade = Severidade.HIGH
        elif queda >= self.config.queda_diaria_medium:
            severidade = Severidade.MEDIUM
        else:
            return None

        descricao = (
            f"Queda de {queda:.1f}% vs dia anterior para {preco.emissor_nome} "
            f"(PU: R$ {pu_anterior:.2f} -> R$ {pu_atual:.2f})"
        )

        return AnomaliaDetectada(
            tipo=TipoAnomalia.SECONDARY_PRICE_DROP,
            severidade=severidade,
            valor_detectado=Decimal(str(round(float(queda), 2))),
            descricao=descricao,
            if_nome=preco.emissor_nome,
            detector=self.name,
            detectado_em=datetime.now(TZ_BRASIL),
            detalhes={
                "codigo_titulo": preco.codigo_titulo,
                "emissor": preco.emissor_nome,
                "emissor_cnpj": preco.emissor_cnpj,
                "pu_anterior": float(pu_anterior),
                "pu_atual": float(pu_atual),
                "queda_percentual": float(queda),
                "data_referencia": preco.data_referencia.isoformat(),
            },
        )


def detectar_quedas_mercado(
    precos: list[dict],
    config: Optional[PriceDropConfig] = None,
) -> DetectionResult:
    """
    Função utilitária para detectar quedas de preço.

    Args:
        precos: Lista de dicts com dados de preço
        config: Configuração opcional

    Returns:
        DetectionResult
    """
    from veredas.collectors.b3.models import TipoTitulo

    precos_obj = []

    for p in precos:
        try:
            tipo_str = p.get("tipo_titulo", "CDB")
            tipo = TipoTitulo(tipo_str) if isinstance(tipo_str, str) else tipo_str

            precos_obj.append(
                PrecoSecundario(
                    codigo_titulo=p.get("codigo", ""),
                    emissor_cnpj=p.get("emissor_cnpj", ""),
                    emissor_nome=p.get("emissor_nome", ""),
                    tipo_titulo=tipo,
                    data_referencia=p.get("data_referencia", date.today()),
                    pu_abertura=Decimal(str(p.get("pu_abertura", 1000))),
                    pu_fechamento=Decimal(str(p.get("pu_fechamento", 1000))),
                    pu_minimo=Decimal(str(p.get("pu_minimo", 1000))),
                    pu_maximo=Decimal(str(p.get("pu_maximo", 1000))),
                    pu_medio=Decimal(str(p.get("pu_medio", 1000))),
                    quantidade_negocios=int(p.get("quantidade_negocios", 0)),
                    quantidade_titulos=int(p.get("quantidade_titulos", 0)),
                    valor_financeiro=Decimal(str(p.get("valor_financeiro", 0))),
                    taxa_minima=Decimal(str(p.get("taxa_minima", 0))),
                    taxa_maxima=Decimal(str(p.get("taxa_maxima", 0))),
                    taxa_media=Decimal(str(p.get("taxa_media", 0))),
                    variacao_dia=Decimal(str(p["variacao_dia"])) if p.get("variacao_dia") else None,
                )
            )
        except Exception as e:
            logger.debug(f"Erro ao converter preço: {e}")
            continue

    detector = PriceDropDetector(config)
    return detector.detect(precos_obj)
