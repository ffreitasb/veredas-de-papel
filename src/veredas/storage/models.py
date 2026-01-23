"""
Modelos de dados para o veredas de papel.

Define as entidades principais:
- InstituicaoFinanceira: Bancos e financeiras monitoradas
- TaxaCDB: Taxas de CDB coletadas
- Anomalia: Anomalias detectadas
- EventoRegulatorio: Histórico de intervenções do BC
"""

from datetime import date, datetime
from decimal import Decimal
from enum import StrEnum
from typing import Optional

from sqlalchemy import (
    JSON,
    Boolean,
    Date,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    func,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    """Base class for all models."""

    pass


class Segmento(StrEnum):
    """Segmento da instituição financeira."""

    BANCO_COMERCIAL = "banco_comercial"
    BANCO_MULTIPLO = "banco_multiplo"
    BANCO_INVESTIMENTO = "banco_investimento"
    FINANCEIRA = "financeira"
    COOPERATIVA = "cooperativa"
    OUTRO = "outro"


class Indexador(StrEnum):
    """Indexador do CDB."""

    CDI = "cdi"
    IPCA = "ipca"
    PREFIXADO = "pre"
    SELIC = "selic"


class TipoAnomalia(StrEnum):
    """Tipos de anomalia detectados."""

    # Fase 1 - Regras de negócio
    SPREAD_ALTO = "spread_alto"
    SPREAD_CRITICO = "spread_critico"
    SALTO_BRUSCO = "salto_brusco"
    SALTO_EXTREMO = "salto_extremo"
    DIVERGENCIA = "divergencia"
    DIVERGENCIA_EXTREMA = "divergencia_extrema"

    # Fase 3 - Detectores estatísticos e ML
    SEASONALITY_BREAK = "seasonality_break"  # STL decomposition
    CHANGE_POINT = "change_point"  # Ruptures PELT
    ROLLING_OUTLIER = "rolling_outlier"  # Rolling z-score
    CLUSTER_OUTLIER = "cluster_outlier"  # DBSCAN
    ISOLATION_ANOMALY = "isolation_anomaly"  # Isolation Forest


class Severidade(StrEnum):
    """Severidade da anomalia."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class TipoEvento(StrEnum):
    """Tipos de evento regulatório."""

    INTERVENCAO = "intervencao"
    RAET = "raet"  # Regime de Administração Especial Temporária
    LIQUIDACAO = "liquidacao"
    FALENCIA = "falencia"
    INCORPORACAO = "incorporacao"


class InstituicaoFinanceira(Base):
    """
    Instituição financeira monitorada.

    Armazena dados básicos e indicadores de saúde financeira
    obtidos do IFData do Banco Central.
    """

    __tablename__ = "instituicoes_financeiras"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    cnpj: Mapped[str] = mapped_column(String(18), unique=True, nullable=False, index=True)
    nome: Mapped[str] = mapped_column(String(255), nullable=False)
    nome_reduzido: Mapped[Optional[str]] = mapped_column(String(100))
    segmento: Mapped[Segmento] = mapped_column(Enum(Segmento), default=Segmento.OUTRO)

    # Indicadores de saúde (IFData)
    indice_basileia: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 4))
    indice_liquidez: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 4))
    ativo_total: Mapped[Optional[Decimal]] = mapped_column(Numeric(20, 2))
    patrimonio_liquido: Mapped[Optional[Decimal]] = mapped_column(Numeric(20, 2))

    # Metadados
    ativa: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )

    # Relacionamentos
    taxas: Mapped[list["TaxaCDB"]] = relationship(back_populates="instituicao")
    anomalias: Mapped[list["Anomalia"]] = relationship(back_populates="instituicao")
    eventos: Mapped[list["EventoRegulatorio"]] = relationship(back_populates="instituicao")

    def __repr__(self) -> str:
        return f"<IF {self.nome_reduzido or self.nome} ({self.cnpj})>"


class TaxaCDB(Base):
    """
    Taxa de CDB coletada.

    Armazena as taxas oferecidas pelas instituições financeiras,
    incluindo indexador, percentual, prazo e fonte da coleta.
    """

    __tablename__ = "taxas_cdb"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    if_id: Mapped[int] = mapped_column(ForeignKey("instituicoes_financeiras.id"), index=True)

    # Dados da taxa
    data_coleta: Mapped[datetime] = mapped_column(DateTime, nullable=False, index=True)
    indexador: Mapped[Indexador] = mapped_column(Enum(Indexador), nullable=False)
    percentual: Mapped[Decimal] = mapped_column(
        Numeric(10, 4), nullable=False
    )  # Ex: 120.0 para 120% CDI
    taxa_adicional: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(10, 4)
    )  # Para IPCA+X%, guarda o X

    # Características do produto
    prazo_dias: Mapped[int] = mapped_column(Integer, nullable=False)
    valor_minimo: Mapped[Optional[Decimal]] = mapped_column(Numeric(15, 2))
    liquidez_diaria: Mapped[bool] = mapped_column(Boolean, default=False)

    # Metadados da coleta
    fonte: Mapped[str] = mapped_column(String(50), nullable=False)  # xp, btg, rico, etc
    url_fonte: Mapped[Optional[str]] = mapped_column(Text)
    raw_data: Mapped[Optional[dict]] = mapped_column(JSON)  # Dados brutos da coleta

    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    # Relacionamentos
    instituicao: Mapped["InstituicaoFinanceira"] = relationship(back_populates="taxas")
    anomalias: Mapped[list["Anomalia"]] = relationship(back_populates="taxa")

    def __repr__(self) -> str:
        return f"<TaxaCDB {self.percentual}% {self.indexador.value} - {self.prazo_dias}d>"

    @property
    def spread_cdi(self) -> Optional[Decimal]:
        """Retorna o spread em relação ao CDI, se aplicável."""
        if self.indexador == Indexador.CDI:
            return self.percentual - Decimal("100")
        return None


class Anomalia(Base):
    """
    Anomalia detectada.

    Registra anomalias identificadas pelos algoritmos de detecção,
    incluindo tipo, severidade e valores detectados.
    """

    __tablename__ = "anomalias"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    if_id: Mapped[int] = mapped_column(ForeignKey("instituicoes_financeiras.id"), index=True)
    taxa_id: Mapped[Optional[int]] = mapped_column(ForeignKey("taxas_cdb.id"))

    # Classificação
    tipo: Mapped[TipoAnomalia] = mapped_column(Enum(TipoAnomalia), nullable=False)
    severidade: Mapped[Severidade] = mapped_column(Enum(Severidade), nullable=False)

    # Valores
    valor_detectado: Mapped[Decimal] = mapped_column(Numeric(10, 4), nullable=False)
    valor_esperado: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 4))
    desvio: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 4))  # Número de desvios padrão

    # Descrição
    descricao: Mapped[str] = mapped_column(Text, nullable=False)
    detalhes: Mapped[Optional[dict]] = mapped_column(JSON)  # Dados adicionais

    # Status
    detectado_em: Mapped[datetime] = mapped_column(DateTime, nullable=False, index=True)
    resolvido: Mapped[bool] = mapped_column(Boolean, default=False)
    resolvido_em: Mapped[Optional[datetime]] = mapped_column(DateTime)
    notas_resolucao: Mapped[Optional[str]] = mapped_column(Text)

    # Relacionamentos
    instituicao: Mapped["InstituicaoFinanceira"] = relationship(back_populates="anomalias")
    taxa: Mapped[Optional["TaxaCDB"]] = relationship(back_populates="anomalias")

    def __repr__(self) -> str:
        return f"<Anomalia {self.tipo.value} [{self.severidade.value}]>"


class EventoRegulatorio(Base):
    """
    Evento regulatório histórico.

    Registra intervenções, liquidações e outros eventos do BC
    para correlação com comportamento de taxas.
    """

    __tablename__ = "eventos_regulatorios"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    if_id: Mapped[Optional[int]] = mapped_column(ForeignKey("instituicoes_financeiras.id"))
    if_nome: Mapped[str] = mapped_column(
        String(255), nullable=False
    )  # Nome para IFs que não existem mais

    # Evento
    tipo: Mapped[TipoEvento] = mapped_column(Enum(TipoEvento), nullable=False)
    data_evento: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    descricao: Mapped[str] = mapped_column(Text, nullable=False)

    # Fontes e evidências
    fonte: Mapped[str] = mapped_column(Text, nullable=False)  # URL da fonte oficial
    fontes_adicionais: Mapped[Optional[list]] = mapped_column(JSON)

    # Análise retrospectiva
    taxas_pre_evento: Mapped[Optional[dict]] = mapped_column(JSON)  # Snapshot das taxas antes
    sinais_detectados: Mapped[Optional[list]] = mapped_column(JSON)  # Anomalias que precederam

    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )

    # Relacionamentos
    instituicao: Mapped[Optional["InstituicaoFinanceira"]] = relationship(back_populates="eventos")

    def __repr__(self) -> str:
        return f"<Evento {self.tipo.value} - {self.if_nome} ({self.data_evento})>"


class TaxaReferencia(Base):
    """
    Taxas de referência (Selic, CDI, IPCA).

    Armazena histórico das taxas de referência para cálculo de spreads.
    """

    __tablename__ = "taxas_referencia"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    data: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    tipo: Mapped[str] = mapped_column(String(20), nullable=False)  # selic, cdi, ipca

    valor: Mapped[Decimal] = mapped_column(Numeric(10, 6), nullable=False)  # Taxa anual
    valor_diario: Mapped[Optional[Decimal]] = mapped_column(Numeric(15, 10))  # Taxa diária

    fonte: Mapped[str] = mapped_column(String(50), default="bcb")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    def __repr__(self) -> str:
        return f"<TaxaRef {self.tipo} {self.data}: {self.valor}%>"
