"""
Modelos de dados para integração B3.

Define estruturas para representar dados do mercado secundário
de títulos de renda fixa.
"""

from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal
from enum import Enum
from typing import Optional

from veredas import TZ_BRASIL


class TipoTitulo(str, Enum):
    """Tipos de títulos de renda fixa."""

    CDB = "CDB"
    LCI = "LCI"
    LCA = "LCA"
    LC = "LC"
    DEBENTURE = "DEBENTURE"
    CRI = "CRI"
    CRA = "CRA"
    OUTROS = "OUTROS"


class StatusNegociacao(str, Enum):
    """Status da negociação."""

    EXECUTADA = "EXECUTADA"
    CANCELADA = "CANCELADA"
    PENDENTE = "PENDENTE"


@dataclass
class TituloRendaFixa:
    """Representa um título de renda fixa."""

    codigo: str  # Código CETIP/B3
    tipo: TipoTitulo
    emissor_cnpj: str
    emissor_nome: str
    data_emissao: date
    data_vencimento: date
    valor_nominal: Decimal
    indexador: str  # CDI, IPCA, PRE, etc.
    taxa_emissao: Decimal  # Taxa na emissão (% CDI ou % a.a.)
    isin: Optional[str] = None  # Código ISIN internacional

    @property
    def prazo_dias(self) -> int:
        """Prazo até vencimento em dias."""
        hoje = date.today()
        return (self.data_vencimento - hoje).days

    @property
    def prazo_total(self) -> int:
        """Prazo total do título em dias."""
        return (self.data_vencimento - self.data_emissao).days


@dataclass
class NegociacaoB3:
    """Representa uma negociação no mercado secundário."""

    codigo_titulo: str
    data_negociacao: date
    preco_unitario: Decimal  # PU - Preço Unitário
    quantidade: int
    valor_financeiro: Decimal
    taxa_negociada: Decimal  # Taxa implícita na negociação
    status: StatusNegociacao = StatusNegociacao.EXECUTADA

    # Dados opcionais
    hora_negociacao: Optional[datetime] = None
    codigo_corretora_compra: Optional[str] = None
    codigo_corretora_venda: Optional[str] = None


@dataclass
class PrecoSecundario:
    """
    Preço no mercado secundário de um título.

    Representa o resumo diário de negociações de um título,
    útil para análise de tendências e detecção de anomalias.
    """

    codigo_titulo: str
    emissor_cnpj: str
    emissor_nome: str
    tipo_titulo: TipoTitulo
    data_referencia: date

    # Preços
    pu_abertura: Decimal
    pu_fechamento: Decimal
    pu_minimo: Decimal
    pu_maximo: Decimal
    pu_medio: Decimal

    # Volume
    quantidade_negocios: int
    quantidade_titulos: int
    valor_financeiro: Decimal

    # Taxas
    taxa_minima: Decimal
    taxa_maxima: Decimal
    taxa_media: Decimal

    # Variação
    variacao_dia: Optional[Decimal] = None  # Variação % em relação ao dia anterior

    # Metadata
    coletado_em: datetime = field(default_factory=lambda: datetime.now(TZ_BRASIL))

    @property
    def variacao_pu_dia(self) -> Decimal:
        """Variação do PU no dia (fechamento - abertura)."""
        return self.pu_fechamento - self.pu_abertura

    @property
    def amplitude_dia(self) -> Decimal:
        """Amplitude do PU no dia (máximo - mínimo)."""
        return self.pu_maximo - self.pu_minimo

    @property
    def spread_taxa(self) -> Decimal:
        """Spread entre taxa máxima e mínima."""
        return self.taxa_maxima - self.taxa_minima


@dataclass
class ResumoMercadoSecundario:
    """Resumo do mercado secundário para uma data."""

    data_referencia: date
    total_titulos_negociados: int
    total_negocios: int
    valor_financeiro_total: Decimal
    titulos_por_tipo: dict[TipoTitulo, int] = field(default_factory=dict)
    maiores_quedas: list[PrecoSecundario] = field(default_factory=list)
    maiores_altas: list[PrecoSecundario] = field(default_factory=list)


@dataclass
class AlertaPrecoSecundario:
    """Alerta gerado por variação no mercado secundário."""

    codigo_titulo: str
    emissor_cnpj: str
    emissor_nome: str
    tipo_alerta: str  # QUEDA_EXPRESSIVA, VOLUME_ANORMAL, SPREAD_ELEVADO
    severidade: str  # LOW, MEDIUM, HIGH, CRITICAL
    descricao: str
    valor_referencia: Decimal
    valor_atual: Decimal
    variacao_percentual: Decimal
    data_referencia: date
    gerado_em: datetime = field(default_factory=lambda: datetime.now(TZ_BRASIL))
