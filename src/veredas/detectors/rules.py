"""
Detector de anomalias baseado em regras de negócio.

Implementa regras simples e interpretáveis para detecção de anomalias:
- Spread alto/crítico: CDB pagando muito acima do CDI
- Salto brusco/extremo: Variação rápida nas taxas
- Divergência: Taxa muito acima da média do mercado
"""

import time
from collections.abc import Sequence
from dataclasses import dataclass
from decimal import Decimal

from veredas.detectors.base import AnomaliaDetectada, BaseDetector, DetectionResult
from veredas.storage.models import Indexador, Severidade, TaxaCDB, TipoAnomalia


@dataclass
class RuleThresholds:
    """Thresholds configuráveis para as regras de detecção."""

    # Spread (% do CDI)
    spread_alto: Decimal = Decimal("130")  # > 130% CDI = HIGH
    spread_critico: Decimal = Decimal("150")  # > 150% CDI = CRITICAL

    # Variação em 7 dias (pontos percentuais)
    salto_brusco: Decimal = Decimal("10")  # > 10pp = MEDIUM
    salto_extremo: Decimal = Decimal("20")  # > 20pp = HIGH

    # Divergência (desvios padrão)
    divergencia: Decimal = Decimal("2")  # > 2σ = MEDIUM
    divergencia_extrema: Decimal = Decimal("3")  # > 3σ = HIGH

    # IPCA+ (spread sobre IPCA)
    ipca_spread_alto: Decimal = Decimal("10")  # IPCA + 10% = HIGH
    ipca_spread_critico: Decimal = Decimal("15")  # IPCA + 15% = CRITICAL


# Thresholds padrão
DEFAULT_THRESHOLDS = RuleThresholds()


class SpreadDetector(BaseDetector):
    """
    Detecta spreads anormalmente altos em CDBs indexados ao CDI.

    Regras:
    - SPREAD_ALTO: CDB > threshold% CDI (severidade HIGH)
    - SPREAD_CRITICO: CDB > threshold% CDI (severidade CRITICAL)

    Os thresholds variam por tier do emissor: bancões disparam anomalia
    com spreads menores do que pequenas financeiras, porque qualquer
    desvio da normalidade de um bancão é mais suspeito.
    """

    def __init__(self, thresholds: RuleThresholds | None = None):
        self.thresholds = thresholds or DEFAULT_THRESHOLDS

    @property
    def name(self) -> str:
        return "spread_detector"

    @property
    def description(self) -> str:
        return "Detecta CDBs com spread anormalmente alto em relação ao CDI"

    def detect(
        self,
        taxas: Sequence[TaxaCDB],
        tier_thresholds: "dict[int, RuleThresholds] | None" = None,
    ) -> DetectionResult:
        """
        Analisa taxas de CDB e detecta spreads anormais.

        Args:
            taxas: Sequência de TaxaCDB a analisar.
            tier_thresholds: Mapa opcional {if_id → RuleThresholds} com limiares
                ajustados por tier de emissor. Quando ausente, usa os thresholds
                padrão da instância para todas as IFs.

        Returns:
            DetectionResult com anomalias encontradas.
        """
        start_time = time.perf_counter()
        anomalias: list[AnomaliaDetectada] = []

        for taxa in taxas:
            override = tier_thresholds.get(taxa.if_id) if tier_thresholds else None
            anomalia = self._check_taxa(taxa, override)
            if anomalia:
                anomalias.append(anomalia)

        elapsed = (time.perf_counter() - start_time) * 1000

        return DetectionResult(
            detector_name=self.name,
            anomalias=anomalias,
            execution_time_ms=elapsed,
        )

    def _check_taxa(
        self,
        taxa: TaxaCDB,
        thresholds_override: "RuleThresholds | None" = None,
    ) -> AnomaliaDetectada | None:
        """Verifica uma taxa individual, com thresholds opcionalmente sobrescritos."""
        thresholds = thresholds_override or self.thresholds

        if taxa.indexador != Indexador.CDI:
            return self._check_ipca(taxa, thresholds) if taxa.indexador == Indexador.IPCA else None

        percentual = taxa.percentual

        # CRITICAL
        if percentual > thresholds.spread_critico:
            return AnomaliaDetectada(
                tipo=TipoAnomalia.SPREAD_CRITICO,
                severidade=Severidade.CRITICAL,
                valor_detectado=percentual,
                valor_esperado=Decimal("100"),
                threshold=thresholds.spread_critico,
                descricao=(
                    f"CDB oferecendo {percentual}% do CDI - "
                    f"spread crítico (>{thresholds.spread_critico}%)"
                ),
                if_id=taxa.if_id,
                taxa_id=taxa.id,
                detector=self.name,
                detalhes={
                    "indexador": taxa.indexador.value,
                    "prazo_dias": taxa.prazo_dias,
                    "fonte": taxa.fonte,
                },
            )

        # HIGH
        if percentual > thresholds.spread_alto:
            return AnomaliaDetectada(
                tipo=TipoAnomalia.SPREAD_ALTO,
                severidade=Severidade.HIGH,
                valor_detectado=percentual,
                valor_esperado=Decimal("100"),
                threshold=thresholds.spread_alto,
                descricao=(
                    f"CDB oferecendo {percentual}% do CDI - "
                    f"spread alto (>{thresholds.spread_alto}%)"
                ),
                if_id=taxa.if_id,
                taxa_id=taxa.id,
                detector=self.name,
                detalhes={
                    "indexador": taxa.indexador.value,
                    "prazo_dias": taxa.prazo_dias,
                    "fonte": taxa.fonte,
                },
            )

        return None

    def _check_ipca(
        self, taxa: TaxaCDB, thresholds: "RuleThresholds | None" = None
    ) -> AnomaliaDetectada | None:
        """Verifica taxas IPCA+."""
        if taxa.indexador != Indexador.IPCA or taxa.taxa_adicional is None:
            return None

        t = thresholds or self.thresholds
        spread = taxa.taxa_adicional

        # CRITICAL
        if spread > t.ipca_spread_critico:
            return AnomaliaDetectada(
                tipo=TipoAnomalia.SPREAD_CRITICO,
                severidade=Severidade.CRITICAL,
                valor_detectado=spread,
                threshold=t.ipca_spread_critico,
                descricao=(
                    f"CDB oferecendo IPCA + {spread}% - "
                    f"spread crítico (>IPCA+{t.ipca_spread_critico}%)"
                ),
                if_id=taxa.if_id,
                taxa_id=taxa.id,
                detector=self.name,
                detalhes={
                    "indexador": "ipca",
                    "prazo_dias": taxa.prazo_dias,
                    "fonte": taxa.fonte,
                },
            )

        # HIGH
        if spread > t.ipca_spread_alto:
            return AnomaliaDetectada(
                tipo=TipoAnomalia.SPREAD_ALTO,
                severidade=Severidade.HIGH,
                valor_detectado=spread,
                threshold=t.ipca_spread_alto,
                descricao=(
                    f"CDB oferecendo IPCA + {spread}% - spread alto (>IPCA+{t.ipca_spread_alto}%)"
                ),
                if_id=taxa.if_id,
                taxa_id=taxa.id,
                detector=self.name,
                detalhes={
                    "indexador": "ipca",
                    "prazo_dias": taxa.prazo_dias,
                    "fonte": taxa.fonte,
                },
            )

        return None


class VariacaoDetector(BaseDetector):
    """
    Detecta variações bruscas nas taxas oferecidas.

    Regras:
    - SALTO_BRUSCO: Variação > 10pp em 7 dias (severidade MEDIUM)
    - SALTO_EXTREMO: Variação > 20pp em 7 dias (severidade HIGH)
    """

    def __init__(
        self,
        thresholds: RuleThresholds | None = None,
        janela_dias: int = 7,
    ):
        self.thresholds = thresholds or DEFAULT_THRESHOLDS
        self.janela_dias = janela_dias

    @property
    def name(self) -> str:
        return "variacao_detector"

    @property
    def description(self) -> str:
        return f"Detecta variações bruscas de taxa em {self.janela_dias} dias"

    def detect(
        self,
        taxas_atuais: Sequence[TaxaCDB],
        taxas_anteriores: Sequence[TaxaCDB],
    ) -> DetectionResult:
        """
        Compara taxas atuais com anteriores para detectar saltos.

        Args:
            taxas_atuais: Taxas mais recentes.
            taxas_anteriores: Taxas de referência (N dias atrás).

        Returns:
            DetectionResult com anomalias encontradas.
        """
        start_time = time.perf_counter()
        anomalias: list[AnomaliaDetectada] = []

        # Indexar taxas anteriores por IF e indexador
        anteriores_map: dict[tuple[int, str], TaxaCDB] = {}
        for taxa in taxas_anteriores:
            key = (taxa.if_id, taxa.indexador.value)
            # Manter a mais recente por IF/indexador
            if key not in anteriores_map or taxa.data_coleta > anteriores_map[key].data_coleta:
                anteriores_map[key] = taxa

        # Comparar cada taxa atual
        for taxa_atual in taxas_atuais:
            key = (taxa_atual.if_id, taxa_atual.indexador.value)
            taxa_anterior = anteriores_map.get(key)

            if taxa_anterior:
                anomalia = self._check_variacao(taxa_atual, taxa_anterior)
                if anomalia:
                    anomalias.append(anomalia)

        elapsed = (time.perf_counter() - start_time) * 1000

        return DetectionResult(
            detector_name=self.name,
            anomalias=anomalias,
            execution_time_ms=elapsed,
        )

    def _check_variacao(
        self,
        atual: TaxaCDB,
        anterior: TaxaCDB,
    ) -> AnomaliaDetectada | None:
        """Verifica variação entre duas taxas."""
        variacao = atual.percentual - anterior.percentual

        # Apenas variações positivas (aumento de taxa = sinal de risco)
        if variacao <= 0:
            return None

        # SALTO_EXTREMO: > 20pp
        if variacao > self.thresholds.salto_extremo:
            return AnomaliaDetectada(
                tipo=TipoAnomalia.SALTO_EXTREMO,
                severidade=Severidade.HIGH,
                valor_detectado=atual.percentual,
                valor_esperado=anterior.percentual,
                desvio=variacao,
                threshold=self.thresholds.salto_extremo,
                descricao=(
                    f"Taxa saltou de {anterior.percentual}% para {atual.percentual}% "
                    f"(+{variacao}pp em {self.janela_dias} dias)"
                ),
                if_id=atual.if_id,
                taxa_id=atual.id,
                detector=self.name,
                detalhes={
                    "taxa_anterior": str(anterior.percentual),
                    "data_anterior": anterior.data_coleta.isoformat(),
                    "variacao_pp": str(variacao),
                },
            )

        # SALTO_BRUSCO: > 10pp
        if variacao > self.thresholds.salto_brusco:
            return AnomaliaDetectada(
                tipo=TipoAnomalia.SALTO_BRUSCO,
                severidade=Severidade.MEDIUM,
                valor_detectado=atual.percentual,
                valor_esperado=anterior.percentual,
                desvio=variacao,
                threshold=self.thresholds.salto_brusco,
                descricao=(
                    f"Taxa aumentou de {anterior.percentual}% para {atual.percentual}% "
                    f"(+{variacao}pp em {self.janela_dias} dias)"
                ),
                if_id=atual.if_id,
                taxa_id=atual.id,
                detector=self.name,
                detalhes={
                    "taxa_anterior": str(anterior.percentual),
                    "data_anterior": anterior.data_coleta.isoformat(),
                    "variacao_pp": str(variacao),
                },
            )

        return None


class DivergenciaDetector(BaseDetector):
    """
    Detecta taxas que divergem significativamente da média do mercado.

    Regras:
    - DIVERGENCIA: Taxa > média + 2σ (severidade MEDIUM)
    - DIVERGENCIA_EXTREMA: Taxa > média + 3σ (severidade HIGH)
    """

    def __init__(self, thresholds: RuleThresholds | None = None):
        self.thresholds = thresholds or DEFAULT_THRESHOLDS

    @property
    def name(self) -> str:
        return "divergencia_detector"

    @property
    def description(self) -> str:
        return "Detecta taxas que divergem da média do mercado"

    def detect(
        self,
        taxas: Sequence[TaxaCDB],
        media: Decimal,
        desvio_padrao: Decimal,
    ) -> DetectionResult:
        """
        Analisa taxas em relação à média do mercado.

        Args:
            taxas: Sequência de TaxaCDB a analisar.
            media: Média do mercado para o indexador.
            desvio_padrao: Desvio padrão do mercado.

        Returns:
            DetectionResult com anomalias encontradas.
        """
        start_time = time.perf_counter()
        anomalias: list[AnomaliaDetectada] = []

        if desvio_padrao == 0:
            # Sem variação no mercado, não há como calcular divergência
            return DetectionResult(
                detector_name=self.name,
                anomalias=[],
                execution_time_ms=0,
            )

        for taxa in taxas:
            anomalia = self._check_divergencia(taxa, media, desvio_padrao)
            if anomalia:
                anomalias.append(anomalia)

        elapsed = (time.perf_counter() - start_time) * 1000

        return DetectionResult(
            detector_name=self.name,
            anomalias=anomalias,
            execution_time_ms=elapsed,
        )

    def _check_divergencia(
        self,
        taxa: TaxaCDB,
        media: Decimal,
        desvio_padrao: Decimal,
    ) -> AnomaliaDetectada | None:
        """Verifica divergência de uma taxa."""
        z_score = (taxa.percentual - media) / desvio_padrao

        # Apenas divergências positivas (taxa acima da média)
        if z_score <= 0:
            return None

        # DIVERGENCIA_EXTREMA: > 3σ
        if z_score > self.thresholds.divergencia_extrema:
            return AnomaliaDetectada(
                tipo=TipoAnomalia.DIVERGENCIA_EXTREMA,
                severidade=Severidade.HIGH,
                valor_detectado=taxa.percentual,
                valor_esperado=media,
                desvio=z_score,
                threshold=self.thresholds.divergencia_extrema,
                descricao=(
                    f"Taxa {taxa.percentual}% está {z_score:.1f} desvios padrão "
                    f"acima da média do mercado ({media}%)"
                ),
                if_id=taxa.if_id,
                taxa_id=taxa.id,
                detector=self.name,
                detalhes={
                    "media_mercado": str(media),
                    "desvio_padrao": str(desvio_padrao),
                    "z_score": str(z_score),
                },
            )

        # DIVERGENCIA: > 2σ
        if z_score > self.thresholds.divergencia:
            return AnomaliaDetectada(
                tipo=TipoAnomalia.DIVERGENCIA,
                severidade=Severidade.MEDIUM,
                valor_detectado=taxa.percentual,
                valor_esperado=media,
                desvio=z_score,
                threshold=self.thresholds.divergencia,
                descricao=(
                    f"Taxa {taxa.percentual}% está {z_score:.1f} desvios padrão "
                    f"acima da média do mercado ({media}%)"
                ),
                if_id=taxa.if_id,
                taxa_id=taxa.id,
                detector=self.name,
                detalhes={
                    "media_mercado": str(media),
                    "desvio_padrao": str(desvio_padrao),
                    "z_score": str(z_score),
                },
            )

        return None


class RuleBasedEngine:
    """
    Motor de detecção que orquestra múltiplos detectores baseados em regras.

    Executa todos os detectores e agrega os resultados.
    """

    def __init__(self, thresholds: RuleThresholds | None = None):
        self.thresholds = thresholds or DEFAULT_THRESHOLDS
        self.spread_detector = SpreadDetector(self.thresholds)
        self.variacao_detector = VariacaoDetector(self.thresholds)
        self.divergencia_detector = DivergenciaDetector(self.thresholds)

    def analyze_spreads(
        self,
        taxas: Sequence[TaxaCDB],
        tier_thresholds: "dict[int, RuleThresholds] | None" = None,
    ) -> DetectionResult:
        """Executa detecção de spreads, com limiares opcionais por tier de emissor."""
        return self.spread_detector.detect(taxas, tier_thresholds=tier_thresholds)

    def analyze_variacoes(
        self,
        taxas_atuais: Sequence[TaxaCDB],
        taxas_anteriores: Sequence[TaxaCDB],
    ) -> DetectionResult:
        """Executa detecção de variações."""
        return self.variacao_detector.detect(taxas_atuais, taxas_anteriores)

    def analyze_divergencias(
        self,
        taxas: Sequence[TaxaCDB],
        media: Decimal,
        desvio_padrao: Decimal,
    ) -> DetectionResult:
        """Executa detecção de divergências."""
        return self.divergencia_detector.detect(taxas, media, desvio_padrao)

    def run_all(
        self,
        taxas_atuais: Sequence[TaxaCDB],
        taxas_anteriores: Sequence[TaxaCDB] | None = None,
        media_mercado: Decimal | None = None,
        desvio_padrao_mercado: Decimal | None = None,
    ) -> list[DetectionResult]:
        """
        Executa todos os detectores.

        Args:
            taxas_atuais: Taxas mais recentes.
            taxas_anteriores: Taxas de referência para variação.
            media_mercado: Média do mercado para divergência.
            desvio_padrao_mercado: Desvio padrão para divergência.

        Returns:
            Lista de DetectionResult de cada detector.
        """
        results = []

        # Sempre executa spread
        results.append(self.analyze_spreads(taxas_atuais))

        # Variação se tiver dados anteriores
        if taxas_anteriores:
            results.append(self.analyze_variacoes(taxas_atuais, taxas_anteriores))

        # Divergência se tiver estatísticas de mercado
        if media_mercado is not None and desvio_padrao_mercado is not None:
            results.append(
                self.analyze_divergencias(taxas_atuais, media_mercado, desvio_padrao_mercado)
            )

        return results
