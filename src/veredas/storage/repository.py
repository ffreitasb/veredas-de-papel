"""
Repositórios para acesso aos dados.

Implementa o padrão Repository para abstrair operações de banco de dados.
"""

from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import Optional, Sequence

from sqlalchemy import and_, desc, func, select
from sqlalchemy.orm import Session

from veredas import TZ_BRASIL
from veredas.storage.models import (
    Anomalia,
    EventoRegulatorio,
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

    def get_by_id(self, if_id: int) -> Optional[InstituicaoFinanceira]:
        """Busca IF por ID."""
        return self.session.get(InstituicaoFinanceira, if_id)

    def get_by_cnpj(self, cnpj: str) -> Optional[InstituicaoFinanceira]:
        """Busca IF por CNPJ."""
        stmt = select(InstituicaoFinanceira).where(InstituicaoFinanceira.cnpj == cnpj)
        return self.session.execute(stmt).scalar_one_or_none()

    def get_by_nome(self, nome: str) -> Optional[InstituicaoFinanceira]:
        """Busca IF por nome (case-insensitive, parcial)."""
        stmt = select(InstituicaoFinanceira).where(
            InstituicaoFinanceira.nome.ilike(f"%{nome}%")
        )
        return self.session.execute(stmt).scalar_one_or_none()

    def list_all(self, ativas_only: bool = True) -> Sequence[InstituicaoFinanceira]:
        """Lista todas as IFs."""
        stmt = select(InstituicaoFinanceira).order_by(InstituicaoFinanceira.nome)
        if ativas_only:
            stmt = stmt.where(InstituicaoFinanceira.ativa == True)  # noqa: E712
        return self.session.execute(stmt).scalars().all()

    def create(self, **kwargs) -> InstituicaoFinanceira:
        """Cria uma nova IF."""
        instituicao = InstituicaoFinanceira(**kwargs)
        self.session.add(instituicao)
        self.session.flush()
        return instituicao

    def upsert(self, cnpj: str, **kwargs) -> InstituicaoFinanceira:
        """Cria ou atualiza IF por CNPJ."""
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

    def get_by_id(self, taxa_id: int) -> Optional[TaxaCDB]:
        """Busca taxa por ID."""
        return self.session.get(TaxaCDB, taxa_id)

    def list_by_if(
        self,
        if_id: int,
        limit: int = 100,
        desde: Optional[datetime] = None,
    ) -> Sequence[TaxaCDB]:
        """Lista taxas de uma IF."""
        stmt = (
            select(TaxaCDB)
            .where(TaxaCDB.if_id == if_id)
            .order_by(desc(TaxaCDB.data_coleta))
            .limit(limit)
        )
        if desde:
            stmt = stmt.where(TaxaCDB.data_coleta >= desde)
        return self.session.execute(stmt).scalars().all()

    def list_recent(
        self,
        dias: int = 7,
        indexador: Optional[str] = None,
    ) -> Sequence[TaxaCDB]:
        """Lista taxas recentes."""
        desde = datetime.now(TZ_BRASIL) - timedelta(days=dias)
        stmt = (
            select(TaxaCDB)
            .where(TaxaCDB.data_coleta >= desde)
            .order_by(desc(TaxaCDB.data_coleta))
        )
        if indexador:
            stmt = stmt.where(TaxaCDB.indexador == indexador)
        return self.session.execute(stmt).scalars().all()

    def get_media_mercado(
        self,
        indexador: str,
        dias: int = 7,
    ) -> Optional[Decimal]:
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
    ) -> Optional[Decimal]:
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
        desvio = variancia ** 0.5

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


class AnomaliaRepository:
    """Repositório para anomalias."""

    def __init__(self, session: Session):
        self.session = session

    def get_by_id(self, anomalia_id: int) -> Optional[Anomalia]:
        """Busca anomalia por ID."""
        return self.session.get(Anomalia, anomalia_id)

    def list_ativas(
        self,
        severidade_minima: Optional[Severidade] = None,
    ) -> Sequence[Anomalia]:
        """Lista anomalias não resolvidas."""
        stmt = (
            select(Anomalia)
            .where(Anomalia.resolvido == False)  # noqa: E712
            .order_by(desc(Anomalia.detectado_em))
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
        stmt = (
            select(Anomalia)
            .where(Anomalia.if_id == if_id)
            .order_by(desc(Anomalia.detectado_em))
        )
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
        notas: Optional[str] = None,
    ) -> Optional[Anomalia]:
        """Marca anomalia como resolvida."""
        anomalia = self.get_by_id(anomalia_id)
        if anomalia:
            anomalia.resolvido = True
            anomalia.resolvido_em = datetime.now(TZ_BRASIL)
            anomalia.notas_resolucao = notas
        return anomalia


class TaxaReferenciaRepository:
    """Repositório para taxas de referência."""

    def __init__(self, session: Session):
        self.session = session

    def get_ultima(self, tipo: str) -> Optional[TaxaReferencia]:
        """Busca última taxa de um tipo."""
        stmt = (
            select(TaxaReferencia)
            .where(TaxaReferencia.tipo == tipo)
            .order_by(desc(TaxaReferencia.data))
            .limit(1)
        )
        return self.session.execute(stmt).scalar_one_or_none()

    def get_por_data(self, tipo: str, data: date) -> Optional[TaxaReferencia]:
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
        """Cria ou atualiza taxa de referência."""
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

    def get_by_id(self, evento_id: int) -> Optional[EventoRegulatorio]:
        """Busca evento por ID."""
        return self.session.get(EventoRegulatorio, evento_id)

    def list_all(self, limit: int = 100) -> Sequence[EventoRegulatorio]:
        """Lista todos os eventos."""
        stmt = (
            select(EventoRegulatorio)
            .order_by(desc(EventoRegulatorio.data_evento))
            .limit(limit)
        )
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
