"""
Repositórios para acesso aos dados.

Implementa o padrão Repository para abstrair operações de banco de dados.
"""

from collections.abc import Sequence
from datetime import date, datetime, timedelta
from decimal import Decimal

from sqlalchemy import and_, desc, func, select
from sqlalchemy.orm import Session, selectinload

from veredas import TZ_BRASIL
from veredas.storage.models import (
    Anomalia,
    EventoRegulatorio,
    HealthDataIF,
    InstituicaoFinanceira,
    Severidade,
    TaxaCDB,
    TaxaReferencia,
    TipoAnomalia,
)


class InstituicaoRepository:
    """Repositório para instituições financeiras."""

    def __init__(self, session: Session):
        self.session = session

    def get_by_id(self, if_id: int) -> InstituicaoFinanceira | None:
        """Busca IF por ID."""
        return self.session.get(InstituicaoFinanceira, if_id)

    def get_by_cnpj(self, cnpj: str) -> InstituicaoFinanceira | None:
        """Busca IF por CNPJ."""
        stmt = select(InstituicaoFinanceira).where(InstituicaoFinanceira.cnpj == cnpj)
        return self.session.execute(stmt).scalar_one_or_none()

    def get_by_nome(self, nome: str) -> InstituicaoFinanceira | None:
        """Busca IF por nome (case-insensitive, parcial)."""
        stmt = select(InstituicaoFinanceira).where(InstituicaoFinanceira.nome.ilike(f"%{nome}%"))
        return self.session.execute(stmt).scalar_one_or_none()

    def list_all(self, ativas_only: bool = True) -> Sequence[InstituicaoFinanceira]:
        """Lista todas as IFs."""
        stmt = select(InstituicaoFinanceira).order_by(InstituicaoFinanceira.nome)
        if ativas_only:
            stmt = stmt.where(InstituicaoFinanceira.ativa == True)  # noqa: E712
        return self.session.execute(stmt).scalars().all()

    def list_paginated(
        self,
        order_by: str = "nome",
        limit: int = 30,
        offset: int = 0,
    ) -> Sequence[InstituicaoFinanceira]:
        """Lista IFs com paginacao."""
        stmt = select(InstituicaoFinanceira).where(
            InstituicaoFinanceira.ativa == True  # noqa: E712
        )

        # Ordenacao
        if order_by == "nome":
            stmt = stmt.order_by(InstituicaoFinanceira.nome)
        elif order_by == "risco_desc":
            # Menor Basileia = maior risco (ordena por Basileia crescente)
            stmt = stmt.order_by(InstituicaoFinanceira.indice_basileia.asc().nullslast())
        elif order_by == "basileia_asc":
            stmt = stmt.order_by(InstituicaoFinanceira.indice_basileia)

        stmt = stmt.offset(offset).limit(limit)
        return self.session.execute(stmt).scalars().all()

    def count(self) -> int:
        """Conta total de IFs ativas."""
        stmt = select(func.count(InstituicaoFinanceira.id)).where(
            InstituicaoFinanceira.ativa == True  # noqa: E712
        )
        return self.session.execute(stmt).scalar() or 0

    def create(self, **kwargs) -> InstituicaoFinanceira:
        """Cria uma nova IF."""
        instituicao = InstituicaoFinanceira(**kwargs)
        self.session.add(instituicao)
        self.session.flush()
        return instituicao

    def upsert(self, cnpj: str, **kwargs) -> InstituicaoFinanceira:
        """
        Cria ou atualiza IF por CNPJ.

        Nota sobre imutabilidade (M5): A mutacao direta do objeto e IDIOMATICA
        para SQLAlchemy ORM. O ORM rastreia objetos na sessao e detecta mudancas
        automaticamente via Unit of Work pattern. Criar um novo objeto quebraria
        o tracking de mudancas e o relacionamento com a sessao.

        Args:
            cnpj: CNPJ da instituicao.
            **kwargs: Campos a atualizar/criar.

        Returns:
            Instituicao criada ou atualizada (mesma instancia se existia).
        """
        instituicao = self.get_by_cnpj(cnpj)
        if instituicao:
            for key, value in kwargs.items():
                setattr(instituicao, key, value)
        else:
            instituicao = self.create(cnpj=cnpj, **kwargs)
        return instituicao


class TaxaCDBRepository:
    """Repositório para taxas de CDB."""

    def __init__(self, session: Session):
        self.session = session

    def get_by_id(self, taxa_id: int) -> TaxaCDB | None:
        """Busca taxa por ID."""
        stmt = (
            select(TaxaCDB)
            .where(TaxaCDB.id == taxa_id)
            .options(selectinload(TaxaCDB.instituicao))
        )
        return self.session.execute(stmt).scalar_one_or_none()

    def list_by_if(
        self,
        if_id: int,
        limit: int = 100,
        desde: datetime | None = None,
    ) -> Sequence[TaxaCDB]:
        """Lista taxas de uma IF."""
        stmt = (
            select(TaxaCDB)
            .where(TaxaCDB.if_id == if_id)
            .options(selectinload(TaxaCDB.instituicao))
            .order_by(desc(TaxaCDB.data_coleta))
            .limit(limit)
        )
        if desde:
            stmt = stmt.where(TaxaCDB.data_coleta >= desde)
        return self.session.execute(stmt).scalars().all()

    def list_recent(
        self,
        dias: int = 7,
        indexador: str | None = None,
    ) -> Sequence[TaxaCDB]:
        """Lista taxas recentes."""
        desde = datetime.now(TZ_BRASIL) - timedelta(days=dias)
        stmt = (
            select(TaxaCDB).where(TaxaCDB.data_coleta >= desde).order_by(desc(TaxaCDB.data_coleta))
        )
        if indexador:
            stmt = stmt.where(TaxaCDB.indexador == indexador)
        return self.session.execute(stmt).scalars().all()

    def get_media_mercado(
        self,
        indexador: str,
        dias: int = 7,
    ) -> Decimal | None:
        """Calcula média do mercado para um indexador."""
        desde = datetime.now(TZ_BRASIL) - timedelta(days=dias)
        stmt = select(func.avg(TaxaCDB.percentual)).where(
            and_(
                TaxaCDB.indexador == indexador,
                TaxaCDB.data_coleta >= desde,
            )
        )
        result = self.session.execute(stmt).scalar()
        return Decimal(str(result)) if result else None

    def get_desvio_padrao(
        self,
        indexador: str,
        dias: int = 30,
    ) -> Decimal | None:
        """
        Calcula desvio padrão do mercado.

        SQLite não tem STDDEV nativo, então calculamos manualmente em Python.

        Args:
            indexador: Tipo de indexador (CDI, IPCA, etc.).
            dias: Quantidade de dias para calcular.

        Returns:
            Desvio padrão como Decimal ou None se não houver dados suficientes.
        """
        desde = datetime.now(TZ_BRASIL) - timedelta(days=dias)

        # Buscar todos os valores
        stmt = select(TaxaCDB.percentual).where(
            and_(
                TaxaCDB.indexador == indexador,
                TaxaCDB.data_coleta >= desde,
            )
        )
        result = self.session.execute(stmt).scalars().all()

        # Precisa de pelo menos 2 valores para calcular desvio padrão
        if len(result) < 2:
            return None

        # Converter para float para cálculos
        valores = [float(v) for v in result]
        n = len(valores)

        # Calcular média
        media = sum(valores) / n

        # Calcular variância (soma dos quadrados das diferenças / n)
        soma_quadrados = sum((x - media) ** 2 for x in valores)
        variancia = soma_quadrados / n

        # Desvio padrão = raiz quadrada da variância
        desvio = variancia**0.5

        return Decimal(str(round(desvio, 6)))

    def create(self, **kwargs) -> TaxaCDB:
        """Cria uma nova taxa."""
        taxa = TaxaCDB(**kwargs)
        self.session.add(taxa)
        self.session.flush()
        return taxa

    def bulk_create(self, taxas: list[dict]) -> list[TaxaCDB]:
        """Cria múltiplas taxas."""
        objetos = [TaxaCDB(**t) for t in taxas]
        self.session.add_all(objetos)
        self.session.flush()
        return objetos

    def count(self) -> int:
        """Conta total de taxas."""
        stmt = select(func.count(TaxaCDB.id))
        return self.session.execute(stmt).scalar() or 0

    def count_distinct_ifs(self) -> int:
        """Conta IFs distintas com taxas."""
        stmt = select(func.count(func.distinct(TaxaCDB.if_id)))
        return self.session.execute(stmt).scalar() or 0

    def list_paginated(
        self,
        filters: dict | None = None,
        order_by: str = "data_desc",
        page: int = 1,
        per_page: int = 20,
    ) -> tuple[Sequence[TaxaCDB], int]:
        """Lista taxas com filtros e paginacao."""
        stmt = select(TaxaCDB)
        count_stmt = select(func.count(TaxaCDB.id))

        # Aplicar filtros
        if filters:
            if "indexador" in filters:
                stmt = stmt.where(TaxaCDB.indexador == filters["indexador"])
                count_stmt = count_stmt.where(TaxaCDB.indexador == filters["indexador"])
            if "prazo_min" in filters:
                stmt = stmt.where(TaxaCDB.prazo_dias >= filters["prazo_min"])
                count_stmt = count_stmt.where(TaxaCDB.prazo_dias >= filters["prazo_min"])
            if "prazo_max" in filters:
                stmt = stmt.where(TaxaCDB.prazo_dias <= filters["prazo_max"])
                count_stmt = count_stmt.where(TaxaCDB.prazo_dias <= filters["prazo_max"])
            if "instituicao_id" in filters:
                stmt = stmt.where(TaxaCDB.if_id == filters["instituicao_id"])
                count_stmt = count_stmt.where(TaxaCDB.if_id == filters["instituicao_id"])
            if "mercado" in filters:
                stmt = stmt.where(TaxaCDB.mercado == filters["mercado"])
                count_stmt = count_stmt.where(TaxaCDB.mercado == filters["mercado"])

        # Ordenacao
        if order_by == "data_desc":
            stmt = stmt.order_by(desc(TaxaCDB.data_coleta))
        elif order_by == "data_asc":
            stmt = stmt.order_by(TaxaCDB.data_coleta)
        elif order_by == "spread_desc":
            stmt = stmt.order_by(desc(TaxaCDB.percentual))
        elif order_by == "spread_asc":
            stmt = stmt.order_by(TaxaCDB.percentual)
        elif order_by == "taxa_desc":
            stmt = stmt.order_by(desc(TaxaCDB.percentual))
        elif order_by == "taxa_asc":
            stmt = stmt.order_by(TaxaCDB.percentual)

        # Eager load da IF para evitar N+1 no template
        stmt = stmt.options(selectinload(TaxaCDB.instituicao))

        # Paginacao
        offset = (page - 1) * per_page
        stmt = stmt.offset(offset).limit(per_page)

        taxas = self.session.execute(stmt).scalars().all()
        total = self.session.execute(count_stmt).scalar() or 0

        return taxas, total

    def get_by_instituicao(
        self,
        instituicao_id: int,
        limit: int = 100,
    ) -> Sequence[TaxaCDB]:
        """Lista taxas de uma instituicao."""
        return self.list_by_if(instituicao_id, limit=limit)


class AnomaliaRepository:
    """Repositório para anomalias."""

    def __init__(self, session: Session):
        self.session = session

    def get_by_id(self, anomalia_id: int) -> Anomalia | None:
        """Busca anomalia por ID."""
        return self.session.get(Anomalia, anomalia_id)

    def list_ativas(
        self,
        severidade_minima: Severidade | None = None,
        limit: int = 100,
    ) -> Sequence[Anomalia]:
        """Lista anomalias não resolvidas.

        Args:
            severidade_minima: Filtrar por severidade minima.
            limit: Limite de resultados (default 100, evita memory leak).

        Returns:
            Lista de anomalias nao resolvidas.
        """
        stmt = (
            select(Anomalia)
            .where(Anomalia.resolvido == False)  # noqa: E712
            .order_by(desc(Anomalia.detectado_em))
            .limit(limit)
        )
        if severidade_minima:
            severidades = {
                Severidade.CRITICAL: [Severidade.CRITICAL],
                Severidade.HIGH: [Severidade.CRITICAL, Severidade.HIGH],
                Severidade.MEDIUM: [Severidade.CRITICAL, Severidade.HIGH, Severidade.MEDIUM],
                Severidade.LOW: list(Severidade),
            }
            stmt = stmt.where(Anomalia.severidade.in_(severidades[severidade_minima]))
        return self.session.execute(stmt).scalars().all()

    def list_by_if(
        self,
        if_id: int,
        incluir_resolvidas: bool = False,
    ) -> Sequence[Anomalia]:
        """Lista anomalias de uma IF."""
        stmt = select(Anomalia).where(Anomalia.if_id == if_id).order_by(desc(Anomalia.detectado_em))
        if not incluir_resolvidas:
            stmt = stmt.where(Anomalia.resolvido == False)  # noqa: E712
        return self.session.execute(stmt).scalars().all()

    def create(
        self,
        if_id: int,
        tipo: TipoAnomalia,
        severidade: Severidade,
        valor_detectado: Decimal,
        descricao: str,
        **kwargs,
    ) -> Anomalia:
        """Cria uma nova anomalia."""
        anomalia = Anomalia(
            if_id=if_id,
            tipo=tipo,
            severidade=severidade,
            valor_detectado=valor_detectado,
            descricao=descricao,
            detectado_em=datetime.now(TZ_BRASIL),
            **kwargs,
        )
        self.session.add(anomalia)
        self.session.flush()
        return anomalia

    def resolver(
        self,
        anomalia_id: int,
        notas: str | None = None,
    ) -> Anomalia | None:
        """Marca anomalia como resolvida."""
        anomalia = self.get_by_id(anomalia_id)
        if anomalia:
            anomalia.resolvido = True
            anomalia.resolvido_em = datetime.now(TZ_BRASIL)
            anomalia.notas_resolucao = notas
        return anomalia

    # Alias para compatibilidade com web routes
    mark_resolved = resolver

    def count_by_severity(self, severidade: Severidade) -> int:
        """Conta anomalias ativas por severidade."""
        stmt = select(func.count(Anomalia.id)).where(
            and_(
                Anomalia.severidade == severidade,
                Anomalia.resolvido == False,  # noqa: E712
            )
        )
        return self.session.execute(stmt).scalar() or 0

    def count_active(self) -> int:
        """Conta total de anomalias ativas."""
        stmt = select(func.count(Anomalia.id)).where(
            Anomalia.resolvido == False  # noqa: E712
        )
        return self.session.execute(stmt).scalar() or 0

    def get_recent(self, limit: int = 5) -> Sequence[Anomalia]:
        """Busca anomalias mais recentes."""
        stmt = (
            select(Anomalia)
            .where(Anomalia.resolvido == False)  # noqa: E712
            .order_by(desc(Anomalia.detectado_em))
            .limit(limit)
        )
        return self.session.execute(stmt).scalars().all()

    def list_with_filters(
        self,
        filters: dict | None = None,
        limit: int = 20,
        offset: int = 0,
        eager_load: bool = False,
    ) -> Sequence[Anomalia]:
        """Lista anomalias com filtros.

        Args:
            filters: Filtros opcionais (severidade, tipo, cnpj, resolvida).
            limit: Limite de resultados.
            offset: Offset para paginacao.
            eager_load: Se True, carrega instituicao junto (evita N+1).

        Returns:
            Lista de anomalias.
        """
        stmt = select(Anomalia).order_by(desc(Anomalia.detectado_em))

        # Eager loading para evitar N+1 queries
        if eager_load:
            stmt = stmt.options(selectinload(Anomalia.instituicao))

        if filters:
            if "severidade" in filters:
                stmt = stmt.where(Anomalia.severidade == filters["severidade"])
            if "tipo" in filters:
                stmt = stmt.where(Anomalia.tipo == filters["tipo"])
            if "cnpj" in filters:
                stmt = stmt.join(InstituicaoFinanceira).where(
                    InstituicaoFinanceira.cnpj == filters["cnpj"]
                )
            if "resolvido" in filters:
                stmt = stmt.where(Anomalia.resolvido == filters["resolvido"])

        stmt = stmt.offset(offset).limit(limit)
        return self.session.execute(stmt).scalars().all()

    def count_with_filters(self, filters: dict | None = None) -> int:
        """Conta anomalias com filtros."""
        stmt = select(func.count(Anomalia.id))

        if filters:
            if "severidade" in filters:
                stmt = stmt.where(Anomalia.severidade == filters["severidade"])
            if "tipo" in filters:
                stmt = stmt.where(Anomalia.tipo == filters["tipo"])
            if "cnpj" in filters:
                stmt = stmt.join(InstituicaoFinanceira).where(
                    InstituicaoFinanceira.cnpj == filters["cnpj"]
                )
            if "resolvido" in filters:
                stmt = stmt.where(Anomalia.resolvido == filters["resolvido"])

        return self.session.execute(stmt).scalar() or 0

    def get_distinct_tipos(self) -> list[str]:
        """Lista tipos distintos de anomalias."""
        stmt = select(func.distinct(Anomalia.tipo))
        result = self.session.execute(stmt).scalars().all()
        return [str(t) for t in result if t]

    def get_by_instituicao(
        self,
        instituicao_id: int,
        limit: int = 20,
    ) -> Sequence[Anomalia]:
        """Lista anomalias de uma instituicao."""
        stmt = (
            select(Anomalia)
            .where(Anomalia.if_id == instituicao_id)
            .order_by(desc(Anomalia.detectado_em))
            .limit(limit)
        )
        return self.session.execute(stmt).scalars().all()


class TaxaReferenciaRepository:
    """Repositório para taxas de referência."""

    def __init__(self, session: Session):
        self.session = session

    def get_ultima(self, tipo: str) -> TaxaReferencia | None:
        """Busca última taxa de um tipo."""
        stmt = (
            select(TaxaReferencia)
            .where(TaxaReferencia.tipo == tipo)
            .order_by(desc(TaxaReferencia.data))
            .limit(1)
        )
        return self.session.execute(stmt).scalar_one_or_none()

    # Alias para compatibilidade com web routes
    get_latest = get_ultima

    def get_por_data(self, tipo: str, data: date) -> TaxaReferencia | None:
        """Busca taxa por tipo e data."""
        stmt = select(TaxaReferencia).where(
            and_(
                TaxaReferencia.tipo == tipo,
                TaxaReferencia.data == data,
            )
        )
        return self.session.execute(stmt).scalar_one_or_none()

    def list_historico(
        self,
        tipo: str,
        dias: int = 30,
    ) -> Sequence[TaxaReferencia]:
        """Lista histórico de taxas."""
        desde = date.today() - timedelta(days=dias)
        stmt = (
            select(TaxaReferencia)
            .where(
                and_(
                    TaxaReferencia.tipo == tipo,
                    TaxaReferencia.data >= desde,
                )
            )
            .order_by(TaxaReferencia.data)
        )
        return self.session.execute(stmt).scalars().all()

    def create(self, **kwargs) -> TaxaReferencia:
        """Cria uma nova taxa de referência."""
        taxa = TaxaReferencia(**kwargs)
        self.session.add(taxa)
        self.session.flush()
        return taxa

    def upsert(self, tipo: str, data: date, valor: Decimal, **kwargs) -> TaxaReferencia:
        """
        Cria ou atualiza taxa de referencia.

        Nota sobre imutabilidade (M5): A mutacao direta do objeto e IDIOMATICA
        para SQLAlchemy ORM. Ver nota em InstituicaoRepository.upsert().

        Args:
            tipo: Tipo da taxa (selic, cdi, ipca).
            data: Data da taxa.
            valor: Valor da taxa.
            **kwargs: Campos adicionais.

        Returns:
            Taxa criada ou atualizada.
        """
        taxa = self.get_por_data(tipo, data)
        if taxa:
            taxa.valor = valor
            for key, value in kwargs.items():
                setattr(taxa, key, value)
        else:
            taxa = self.create(tipo=tipo, data=data, valor=valor, **kwargs)
        return taxa


class EventoRepository:
    """Repositório para eventos regulatórios."""

    def __init__(self, session: Session):
        self.session = session

    def get_by_id(self, evento_id: int) -> EventoRegulatorio | None:
        """Busca evento por ID."""
        return self.session.get(EventoRegulatorio, evento_id)

    def list_all(self, limit: int = 100) -> Sequence[EventoRegulatorio]:
        """Lista todos os eventos."""
        stmt = select(EventoRegulatorio).order_by(desc(EventoRegulatorio.data_evento)).limit(limit)
        return self.session.execute(stmt).scalars().all()

    def list_by_if(self, if_id: int) -> Sequence[EventoRegulatorio]:
        """Lista eventos de uma IF."""
        stmt = (
            select(EventoRegulatorio)
            .where(EventoRegulatorio.if_id == if_id)
            .order_by(desc(EventoRegulatorio.data_evento))
        )
        return self.session.execute(stmt).scalars().all()

    def create(self, **kwargs) -> EventoRegulatorio:
        """Cria um novo evento."""
        evento = EventoRegulatorio(**kwargs)
        self.session.add(evento)
        self.session.flush()
        return evento

    def list_with_filters(
        self,
        filters: dict | None = None,
        order_by: str = "data_desc",
        limit: int = 100,
        eager_load: bool = False,
    ) -> Sequence[EventoRegulatorio]:
        """Lista eventos com filtros.

        Args:
            filters: Filtros opcionais (ano, tipo).
            order_by: Ordenacao (data_desc ou data_asc).
            limit: Limite de resultados (default 100).
            eager_load: Se True, carrega instituicao junto (evita N+1).

        Returns:
            Lista de eventos filtrados.
        """
        stmt = select(EventoRegulatorio)

        # Eager loading para evitar N+1 queries
        if eager_load:
            stmt = stmt.options(selectinload(EventoRegulatorio.instituicao))

        if filters:
            if "ano" in filters:
                stmt = stmt.where(
                    func.extract("year", EventoRegulatorio.data_evento) == filters["ano"]
                )
            if "tipo" in filters:
                stmt = stmt.where(EventoRegulatorio.tipo == filters["tipo"])

        if order_by == "data_desc":
            stmt = stmt.order_by(desc(EventoRegulatorio.data_evento))
        else:
            stmt = stmt.order_by(EventoRegulatorio.data_evento)

        stmt = stmt.limit(limit)
        return self.session.execute(stmt).scalars().all()

    def get_distinct_years(self) -> list[int]:
        """Lista anos distintos com eventos."""
        stmt = select(func.distinct(func.extract("year", EventoRegulatorio.data_evento)))
        result = self.session.execute(stmt).scalars().all()
        return sorted([int(y) for y in result if y], reverse=True)

    def get_distinct_types(self) -> list[str]:
        """Lista tipos distintos de eventos."""
        stmt = select(func.distinct(EventoRegulatorio.tipo))
        result = self.session.execute(stmt).scalars().all()
        return [str(t) for t in result if t]


class HealthDataRepository:
    """Repositório para dados de saúde financeira (IFData)."""

    def __init__(self, session: Session):
        self.session = session

    def get_latest(self, if_id: int) -> HealthDataIF | None:
        """Retorna o snapshot mais recente de uma IF."""
        stmt = (
            select(HealthDataIF)
            .where(HealthDataIF.if_id == if_id)
            .order_by(desc(HealthDataIF.data_base))
            .limit(1)
        )
        return self.session.execute(stmt).scalar_one_or_none()

    def list_historico(self, if_id: int, limit: int = 8) -> Sequence[HealthDataIF]:
        """Lista histórico de snapshots de uma IF (ordem cronológica)."""
        stmt = (
            select(HealthDataIF)
            .where(HealthDataIF.if_id == if_id)
            .order_by(HealthDataIF.data_base)
            .limit(limit)
        )
        return self.session.execute(stmt).scalars().all()

    def upsert(self, if_id: int, data_base: date, **kwargs) -> HealthDataIF:
        """Cria ou atualiza snapshot de saúde para uma IF/data_base."""
        stmt = select(HealthDataIF).where(
            and_(HealthDataIF.if_id == if_id, HealthDataIF.data_base == data_base)
        )
        existing = self.session.execute(stmt).scalar_one_or_none()
        if existing:
            for key, value in kwargs.items():
                setattr(existing, key, value)
            return existing

        health = HealthDataIF(if_id=if_id, data_base=data_base, **kwargs)
        self.session.add(health)
        self.session.flush()
        return health

    def list_all_low_basileia(self, threshold: Decimal = Decimal("11")) -> Sequence[HealthDataIF]:
        """Lista IFs com Basileia abaixo do threshold no snapshot mais recente."""
        subq = (
            select(HealthDataIF.if_id, func.max(HealthDataIF.data_base).label("max_date"))
            .group_by(HealthDataIF.if_id)
            .subquery()
        )
        stmt = (
            select(HealthDataIF)
            .join(
                subq,
                and_(
                    HealthDataIF.if_id == subq.c.if_id,
                    HealthDataIF.data_base == subq.c.max_date,
                ),
            )
            .where(
                and_(
                    HealthDataIF.indice_basileia.is_not(None),
                    HealthDataIF.indice_basileia < threshold,
                )
            )
        )
        return self.session.execute(stmt).scalars().all()


# Aliases para compatibilidade com web routes
InstituicaoFinanceiraRepository = InstituicaoRepository
EventoRegulatorioRepository = EventoRepository
