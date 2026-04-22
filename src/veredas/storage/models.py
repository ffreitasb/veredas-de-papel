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

    # Fase 4 - Scrapers e dados alternativos
    PLATFORM_DISCREPANCY = "platform_discrepancy"  # Discrepância entre plataformas
    RATE_SPIKE_CROSS_PLATFORM = "rate_spike_cross_platform"  # Spike em múltiplas plataformas

    # Fase 4 - Mercado secundário
    SECONDARY_PRICE_DROP = "secondary_price_drop"  # Queda de preço no secundário
    SECONDARY_DAILY_DROP = "secondary_daily_drop"  # Queda diária no secundário
    SECONDARY_RATE_SPIKE = "secondary_rate_spike"  # Spike de taxa no secundário

    # Fase 4 - Dados alternativos
    COMPLAINT_SPIKE = "complaint_spike"  # Spike de reclamações
    REGULATORY_PROCESS = "regulatory_process"  # Processo regulatório
    NEGATIVE_SENTIMENT = "negative_sentiment"  # Sentimento negativo
    COMPOSITE_RISK_CRITICAL = "composite_risk_critical"  # Risco composto crítico

    # Saúde financeira (IFData)
    BASILEIA_BAIXO = "basileia_baixo"  # Basileia < threshold com taxa elevada
    LIQUIDEZ_CRITICA = "liquidez_critica"  # Liquidez abaixo do mínimo regulatório


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
    nome_reduzido: Mapped[str | None] = mapped_column(String(100))
    segmento: Mapped[Segmento] = mapped_column(Enum(Segmento), default=Segmento.OUTRO)

    # Indicadores de saúde (IFData)
    indice_basileia: Mapped[Decimal | None] = mapped_column(Numeric(10, 4))
    indice_liquidez: Mapped[Decimal | None] = mapped_column(Numeric(10, 4))
    ativo_total: Mapped[Decimal | None] = mapped_column(Numeric(20, 2))
    patrimonio_liquido: Mapped[Decimal | None] = mapped_column(Numeric(20, 2))

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
    taxa_adicional: Mapped[Decimal | None] = mapped_column(
        Numeric(10, 4)
    )  # Para IPCA+X%, guarda o X

    # Características do produto
    prazo_dias: Mapped[int] = mapped_column(Integer, nullable=False)
    valor_minimo: Mapped[Decimal | None] = mapped_column(Numeric(15, 2))
    liquidez_diaria: Mapped[bool] = mapped_column(Boolean, default=False)

    # Score de risco calculado pelo pipeline de detecção (0.0 = normal, 1.0 = máximo risco)
    risk_score: Mapped[Decimal | None] = mapped_column(Numeric(5, 4))

    # Metadados da coleta
    fonte: Mapped[str] = mapped_column(String(50), nullable=False)  # xp, btg, rico, etc
    url_fonte: Mapped[str | None] = mapped_column(Text)
    raw_data: Mapped[dict | None] = mapped_column(JSON)  # Dados brutos da coleta

    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    # Relacionamentos
    instituicao: Mapped["InstituicaoFinanceira"] = relationship(back_populates="taxas")
    anomalias: Mapped[list["Anomalia"]] = relationship(back_populates="taxa")

    def __repr__(self) -> str:
        return f"<TaxaCDB {self.percentual}% {self.indexador.value} - {self.prazo_dias}d>"

    @property
    def spread_cdi(self) -> Decimal | None:
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
    taxa_id: Mapped[int | None] = mapped_column(ForeignKey("taxas_cdb.id"))

    # Classificação
    tipo: Mapped[TipoAnomalia] = mapped_column(Enum(TipoAnomalia), nullable=False)
    severidade: Mapped[Severidade] = mapped_column(Enum(Severidade), nullable=False)

    # Valores
    valor_detectado: Mapped[Decimal] = mapped_column(Numeric(10, 4), nullable=False)
    valor_esperado: Mapped[Decimal | None] = mapped_column(Numeric(10, 4))
    desvio: Mapped[Decimal | None] = mapped_column(Numeric(10, 4))  # Número de desvios padrão

    # Descrição
    descricao: Mapped[str] = mapped_column(Text, nullable=False)
    detalhes: Mapped[dict | None] = mapped_column(JSON)  # Dados adicionais

    # Status
    detectado_em: Mapped[datetime] = mapped_column(DateTime, nullable=False, index=True)
    resolvido: Mapped[bool] = mapped_column(Boolean, default=False)
    resolvido_em: Mapped[datetime | None] = mapped_column(DateTime)
    notas_resolucao: Mapped[str | None] = mapped_column(Text)

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
    if_id: Mapped[int | None] = mapped_column(ForeignKey("instituicoes_financeiras.id"))
    if_nome: Mapped[str] = mapped_column(
        String(255), nullable=False
    )  # Nome para IFs que não existem mais

    # Evento
    tipo: Mapped[TipoEvento] = mapped_column(Enum(TipoEvento), nullable=False)
    data_evento: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    descricao: Mapped[str] = mapped_column(Text, nullable=False)

    # Fontes e evidências
    fonte: Mapped[str] = mapped_column(Text, nullable=False)  # URL da fonte oficial
    fontes_adicionais: Mapped[list | None] = mapped_column(JSON)

    # Análise retrospectiva
    taxas_pre_evento: Mapped[dict | None] = mapped_column(JSON)  # Snapshot das taxas antes
    sinais_detectados: Mapped[list | None] = mapped_column(JSON)  # Anomalias que precederam

    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )

    # Relacionamentos
    instituicao: Mapped[Optional["InstituicaoFinanceira"]] = relationship(back_populates="eventos")

    def __repr__(self) -> str:
        return f"<Evento {self.tipo.value} - {self.if_nome} ({self.data_evento})>"


class HealthDataIF(Base):
    """
    Snapshot de saúde financeira de uma IF em uma data base.

    Armazena indicadores do IFData (trimestral) para rastrear evolução
    de Basileia, liquidez e tamanho ao longo do tempo.
    """

    __tablename__ = "health_data_if"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    if_id: Mapped[int] = mapped_column(ForeignKey("instituicoes_financeiras.id"), index=True)

    # Data de referência (trimestral, ex: 2024-03-01 = 1T2024)
    data_base: Mapped[date] = mapped_column(Date, nullable=False, index=True)

    # Indicadores de capital
    indice_basileia: Mapped[Decimal | None] = mapped_column(Numeric(10, 4))
    patrimonio_liquido: Mapped[Decimal | None] = mapped_column(Numeric(20, 2))

    # Indicadores de liquidez
    indice_liquidez: Mapped[Decimal | None] = mapped_column(Numeric(10, 4))
    ativos_liquidos: Mapped[Decimal | None] = mapped_column(Numeric(20, 2))

    # Tamanho
    ativo_total: Mapped[Decimal | None] = mapped_column(Numeric(20, 2))
    depositos_totais: Mapped[Decimal | None] = mapped_column(Numeric(20, 2))

    # Qualidade da carteira
    inadimplencia: Mapped[Decimal | None] = mapped_column(Numeric(10, 4))

    # Rentabilidade
    roa: Mapped[Decimal | None] = mapped_column(Numeric(10, 4))
    roe: Mapped[Decimal | None] = mapped_column(Numeric(10, 4))

    # Fonte
    fonte: Mapped[str] = mapped_column(String(50), default="ifdata")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    # Relacionamentos
    instituicao: Mapped["InstituicaoFinanceira"] = relationship()

    def __repr__(self) -> str:
        return f"<HealthDataIF if_id={self.if_id} {self.data_base} basileia={self.indice_basileia}>"


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
    valor_diario: Mapped[Decimal | None] = mapped_column(Numeric(15, 10))  # Taxa diária

    fonte: Mapped[str] = mapped_column(String(50), default="bcb")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    def __repr__(self) -> str:
        return f"<TaxaRef {self.tipo} {self.data}: {self.valor}%>"


class TipoTituloSecundario(StrEnum):
    """Tipo de título no mercado secundário."""

    CDB = "CDB"
    LCI = "LCI"
    LCA = "LCA"
    LC = "LC"
    DEBENTURE = "DEBENTURE"
    CRI = "CRI"
    CRA = "CRA"
    OUTROS = "OUTROS"


class PrecoSecundarioDB(Base):
    """
    Preço de título no mercado secundário (B3).

    Armazena preços de negociação de CDBs e outros títulos
    de renda fixa no mercado secundário.
    """

    __tablename__ = "precos_secundarios"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    if_id: Mapped[int | None] = mapped_column(ForeignKey("instituicoes_financeiras.id"), index=True)

    # Identificação do título
    codigo_titulo: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    emissor_cnpj: Mapped[str] = mapped_column(String(18), nullable=False, index=True)
    emissor_nome: Mapped[str] = mapped_column(String(255))
    tipo_titulo: Mapped[TipoTituloSecundario] = mapped_column(
        Enum(TipoTituloSecundario), default=TipoTituloSecundario.CDB
    )

    # Dados de preço
    data_referencia: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    pu_abertura: Mapped[Decimal] = mapped_column(Numeric(15, 4), nullable=False)
    pu_fechamento: Mapped[Decimal] = mapped_column(Numeric(15, 4), nullable=False)
    pu_minimo: Mapped[Decimal] = mapped_column(Numeric(15, 4), nullable=False)
    pu_maximo: Mapped[Decimal] = mapped_column(Numeric(15, 4), nullable=False)
    pu_medio: Mapped[Decimal] = mapped_column(Numeric(15, 4), nullable=False)

    # Volume
    quantidade_negocios: Mapped[int] = mapped_column(Integer, default=0)
    quantidade_titulos: Mapped[int] = mapped_column(Integer, default=0)
    valor_financeiro: Mapped[Decimal] = mapped_column(Numeric(20, 2), default=Decimal("0"))

    # Taxas
    taxa_minima: Mapped[Decimal | None] = mapped_column(Numeric(10, 4))
    taxa_maxima: Mapped[Decimal | None] = mapped_column(Numeric(10, 4))
    taxa_media: Mapped[Decimal | None] = mapped_column(Numeric(10, 4))

    # Variação
    variacao_dia: Mapped[Decimal | None] = mapped_column(Numeric(10, 4))

    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    # Relacionamentos
    instituicao: Mapped[Optional["InstituicaoFinanceira"]] = relationship()

    def __repr__(self) -> str:
        return f"<PrecoSec {self.codigo_titulo} {self.data_referencia}: R$ {self.pu_fechamento}>"


class StatusProcesso(StrEnum):
    """Status de processo administrativo."""

    ATIVO = "ativo"
    SUSPENSO = "suspenso"
    ARQUIVADO = "arquivado"
    CONCLUIDO = "concluido"


class TipoProcessoBC(StrEnum):
    """Tipo de processo do Banco Central."""

    ADMINISTRATIVO = "administrativo"
    SANCIONADOR = "sancionador"
    CONSULTA = "consulta"
    DENUNCIA = "denuncia"
    FISCALIZACAO = "fiscalizacao"
    OUTRO = "outro"


class ProcessoRegulatorio(Base):
    """
    Processo administrativo do Banco Central.

    Armazena processos e sanções aplicadas pelo BC
    às instituições financeiras.
    """

    __tablename__ = "processos_regulatorios"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    if_id: Mapped[int | None] = mapped_column(ForeignKey("instituicoes_financeiras.id"), index=True)

    # Identificação
    numero_processo: Mapped[str] = mapped_column(String(50), nullable=False, unique=True)
    cnpj_envolvido: Mapped[str | None] = mapped_column(String(18), index=True)
    nome_envolvido: Mapped[str] = mapped_column(String(255))

    # Classificação
    tipo: Mapped[TipoProcessoBC] = mapped_column(
        Enum(TipoProcessoBC), default=TipoProcessoBC.ADMINISTRATIVO
    )
    status: Mapped[StatusProcesso] = mapped_column(
        Enum(StatusProcesso), default=StatusProcesso.ATIVO
    )
    assunto: Mapped[str | None] = mapped_column(Text)

    # Datas
    data_abertura: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    data_atualizacao: Mapped[date | None] = mapped_column(Date)
    data_conclusao: Mapped[date | None] = mapped_column(Date)

    # Sanções
    valor_multa: Mapped[Decimal | None] = mapped_column(Numeric(20, 2))
    outras_penalidades: Mapped[str | None] = mapped_column(Text)

    # Fontes
    url_fonte: Mapped[str | None] = mapped_column(Text)
    raw_data: Mapped[dict | None] = mapped_column(JSON)

    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )

    # Relacionamentos
    instituicao: Mapped[Optional["InstituicaoFinanceira"]] = relationship()

    def __repr__(self) -> str:
        return f"<Processo {self.numero_processo} [{self.status.value}]>"


class ReclamacaoHistorico(Base):
    """
    Histórico de reclamações do Reclame Aqui.

    Armazena métricas de reputação e reclamações
    coletadas periodicamente.
    """

    __tablename__ = "reclamacoes_historico"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    if_id: Mapped[int | None] = mapped_column(ForeignKey("instituicoes_financeiras.id"), index=True)

    # Identificação
    empresa_id: Mapped[str | None] = mapped_column(String(100))  # ID no Reclame Aqui
    empresa_nome: Mapped[str] = mapped_column(String(255), nullable=False)
    cnpj: Mapped[str | None] = mapped_column(String(18), index=True)

    # Métricas
    data_coleta: Mapped[datetime] = mapped_column(DateTime, nullable=False, index=True)
    nota_geral: Mapped[Decimal] = mapped_column(Numeric(4, 2), nullable=False)  # 0-10
    indice_solucao: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False)  # 0-100%
    indice_resposta: Mapped[Decimal | None] = mapped_column(Numeric(5, 2))  # 0-100%

    # Contagens
    total_reclamacoes: Mapped[int] = mapped_column(Integer, default=0)
    reclamacoes_respondidas: Mapped[int] = mapped_column(Integer, default=0)
    reclamacoes_resolvidas: Mapped[int] = mapped_column(Integer, default=0)
    reclamacoes_nao_resolvidas: Mapped[int] = mapped_column(Integer, default=0)

    # Período recente (30 dias)
    reclamacoes_30d: Mapped[int] = mapped_column(Integer, default=0)
    nota_30d: Mapped[Decimal | None] = mapped_column(Numeric(4, 2))

    # Variações
    variacao_nota: Mapped[Decimal | None] = mapped_column(Numeric(6, 2))  # vs período anterior
    variacao_reclamacoes: Mapped[Decimal | None] = mapped_column(Numeric(8, 2))  # %

    # Raw
    raw_data: Mapped[dict | None] = mapped_column(JSON)

    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    # Relacionamentos
    instituicao: Mapped[Optional["InstituicaoFinanceira"]] = relationship()

    def __repr__(self) -> str:
        return f"<Reclamacao {self.empresa_nome} {self.data_coleta.date()}: {self.nota_geral}>"


class NivelRiscoDB(StrEnum):
    """Nível de risco para sinais agregados."""

    BAIXO = "baixo"
    MODERADO = "moderado"
    ELEVADO = "elevado"
    ALTO = "alto"
    CRITICO = "critico"


class SinalRiscoAgregado(Base):
    """
    Sinal de risco agregado para uma instituição.

    Consolida sinais de múltiplas fontes em um score único.
    """

    __tablename__ = "sinais_risco_agregados"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    if_id: Mapped[int] = mapped_column(ForeignKey("instituicoes_financeiras.id"), index=True)

    # Scores individuais (0-100, maior = mais risco)
    score_reclame_aqui: Mapped[Decimal | None] = mapped_column(Numeric(6, 2))
    score_processos_bc: Mapped[Decimal | None] = mapped_column(Numeric(6, 2))
    score_mercado_secundario: Mapped[Decimal | None] = mapped_column(Numeric(6, 2))
    score_sentimento: Mapped[Decimal | None] = mapped_column(Numeric(6, 2))

    # Score consolidado
    score_consolidado: Mapped[Decimal] = mapped_column(Numeric(6, 2), nullable=False)
    nivel_risco: Mapped[NivelRiscoDB] = mapped_column(
        Enum(NivelRiscoDB), default=NivelRiscoDB.BAIXO
    )

    # Confiança e metadados
    confianca: Mapped[Decimal] = mapped_column(Numeric(4, 2), default=Decimal("0"))  # 0-1
    sinais_disponiveis: Mapped[int] = mapped_column(Integer, default=0)

    # Detalhes
    fatores_risco: Mapped[list | None] = mapped_column(JSON)
    recomendacoes: Mapped[list | None] = mapped_column(JSON)

    # Timestamps
    calculado_em: Mapped[datetime] = mapped_column(DateTime, nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    # Relacionamentos
    instituicao: Mapped["InstituicaoFinanceira"] = relationship()

    def __repr__(self) -> str:
        return f"<SinalRisco IF={self.if_id} {self.nivel_risco.value}: {self.score_consolidado}>"


class TaxaColetadaPlataforma(Base):
    """
    Taxa coletada de plataforma de corretora.

    Armazena taxas coletadas dos scrapers de corretoras
    para detecção de discrepâncias entre plataformas.
    """

    __tablename__ = "taxas_coletadas_plataformas"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    if_id: Mapped[int | None] = mapped_column(ForeignKey("instituicoes_financeiras.id"), index=True)

    # Plataforma
    plataforma: Mapped[str] = mapped_column(String(50), nullable=False, index=True)  # xp, btg, rico, etc

    # Dados da taxa
    data_coleta: Mapped[datetime] = mapped_column(DateTime, nullable=False, index=True)
    emissor_cnpj: Mapped[str] = mapped_column(String(18), nullable=False, index=True)
    emissor_nome: Mapped[str] = mapped_column(String(255))

    # Taxa
    indexador: Mapped[Indexador] = mapped_column(Enum(Indexador), nullable=False)
    percentual: Mapped[Decimal] = mapped_column(Numeric(10, 4), nullable=False)
    taxa_adicional: Mapped[Decimal | None] = mapped_column(Numeric(10, 4))

    # Características
    prazo_dias: Mapped[int] = mapped_column(Integer, nullable=False)
    valor_minimo: Mapped[Decimal | None] = mapped_column(Numeric(15, 2))
    liquidez_diaria: Mapped[bool] = mapped_column(Boolean, default=False)

    # Raw
    raw_data: Mapped[dict | None] = mapped_column(JSON)

    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    # Relacionamentos
    instituicao: Mapped[Optional["InstituicaoFinanceira"]] = relationship()

    def __repr__(self) -> str:
        return f"<TaxaPlat {self.plataforma} {self.percentual}% {self.indexador.value}>"
