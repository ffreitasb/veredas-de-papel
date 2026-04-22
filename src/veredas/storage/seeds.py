"""
Seeds de dados historicos para o banco de dados.

Contem eventos regulatorios e dados de instituicoes financeiras
que passaram por intervencoes do Banco Central.
"""

from datetime import date
from decimal import Decimal

from sqlalchemy.orm import Session

from veredas.storage.models import (
    EventoRegulatorio,
    InstituicaoFinanceira,
    Segmento,
    TipoEvento,
)

# Eventos regulatorios historicos de IFs brasileiras
EVENTOS_HISTORICOS: list[dict] = [
    # 2025 - Banco Master
    {
        "if_nome": "Banco Master S.A.",
        "if_cnpj": "03.569.123/0001-98",
        "tipo": TipoEvento.LIQUIDACAO,
        "data_evento": date(2025, 4, 1),
        "descricao": (
            "Liquidacao extrajudicial decretada pelo Banco Central. "
            "Taxas de CDB chegaram a 185% do CDI e IPCA+30% antes da intervencao. "
            "Sinais de estresse incluiam spread anormalmente alto, "
            "captacao agressiva e indicadores de liquidez deteriorados."
        ),
        "fonte": "https://www.bcb.gov.br/",
        "sinais_pre_evento": [
            "CDB pos-fixado 140-185% CDI",
            "CDB IPCA+ ate 30%",
            "Captacao agressiva via fintechs",
            "Baixo indice de liquidez",
        ],
    },
    # 2024 - Will Bank (subsidiaria Master)
    {
        "if_nome": "Will Financeira S.A.",
        "if_cnpj": "50.585.090/0001-06",
        "tipo": TipoEvento.INTERVENCAO,
        "data_evento": date(2024, 11, 15),
        "descricao": (
            "Intervencao do BC na financeira Will Bank, subsidiaria do Banco Master. "
            "Operacoes de credito com taxas abaixo do mercado e capital insuficiente."
        ),
        "fonte": "https://www.bcb.gov.br/",
        "sinais_pre_evento": [
            "Taxas de credito abaixo do mercado",
            "Crescimento rapido da carteira",
            "Vinculo com Banco Master",
        ],
    },
    # 2019 - Banco Neon
    {
        "if_nome": "Banco Neon S.A.",
        "if_cnpj": "20.855.875/0001-82",
        "tipo": TipoEvento.INTERVENCAO,
        "data_evento": date(2019, 5, 3),
        "descricao": (
            "Intervencao do Banco Central no Banco Neon. "
            "Problemas de governanca e gestao de riscos. "
            "Posteriormente adquirido por investidores."
        ),
        "fonte": "https://www.bcb.gov.br/",
        "sinais_pre_evento": [
            "Problemas de governanca",
            "Gestao de riscos deficiente",
            "Crescimento descontrolado",
        ],
    },
    # 2016 - Banco Bonsucesso
    {
        "if_nome": "Banco Bonsucesso S.A.",
        "if_cnpj": "71.027.866/0001-34",
        "tipo": TipoEvento.LIQUIDACAO,
        "data_evento": date(2016, 8, 24),
        "descricao": (
            "Liquidacao extrajudicial do Banco Bonsucesso. "
            "Especializado em credito consignado, apresentou "
            "deterioracao da carteira e problemas de liquidez."
        ),
        "fonte": "https://www.bcb.gov.br/",
        "sinais_pre_evento": [
            "Deterioracao da carteira de credito",
            "Problemas de liquidez",
            "Concentracao em consignado",
        ],
    },
    # 2014 - BVA
    {
        "if_nome": "Banco BVA S.A.",
        "if_cnpj": "32.254.138/0001-03",
        "tipo": TipoEvento.LIQUIDACAO,
        "data_evento": date(2014, 6, 20),
        "descricao": (
            "Liquidacao extrajudicial do Banco BVA. "
            "Oferecia taxas de CDB muito acima do mercado para captar recursos. "
            "Fraudes contabeis foram descobertas apos a intervencao."
        ),
        "fonte": "https://www.bcb.gov.br/",
        "sinais_pre_evento": [
            "CDB com taxas muito acima do mercado",
            "Crescimento acelerado",
            "Exposicao a setores de alto risco",
        ],
    },
    # 2012 - Cruzeiro do Sul
    {
        "if_nome": "Banco Cruzeiro do Sul S.A.",
        "if_cnpj": "62.136.254/0001-99",
        "tipo": TipoEvento.LIQUIDACAO,
        "data_evento": date(2012, 9, 14),
        "descricao": (
            "Liquidacao extrajudicial do Banco Cruzeiro do Sul. "
            "Fraudes contabeis bilionarias envolvendo creditos podres. "
            "Taxas de CDB atrativas eram usadas para captar recursos."
        ),
        "fonte": "https://www.bcb.gov.br/",
        "sinais_pre_evento": [
            "Taxas de CDB acima da media",
            "Crescimento rapido da carteira",
            "Creditos podres escondidos",
        ],
    },
    # 2010 - Banco Panamericano
    {
        "if_nome": "Banco Panamericano S.A.",
        "if_cnpj": "59.285.411/0001-13",
        "tipo": TipoEvento.INTERVENCAO,
        "data_evento": date(2010, 11, 9),
        "descricao": (
            "Intervencao no Banco Panamericano apos descoberta de "
            "rombo bilionario. Carteiras de credito vendidas mas nao baixadas. "
            "FGC e Caixa realizaram aporte para evitar liquidacao."
        ),
        "fonte": "https://www.bcb.gov.br/",
        "sinais_pre_evento": [
            "Inconsistencias contabeis",
            "Carteiras vendidas nao baixadas",
            "Crescimento agressivo",
        ],
    },
    # 2004 - Banco Santos
    {
        "if_nome": "Banco Santos S.A.",
        "if_cnpj": "58.017.179/0001-18",
        "tipo": TipoEvento.LIQUIDACAO,
        "data_evento": date(2004, 11, 12),
        "descricao": (
            "Liquidacao extrajudicial do Banco Santos. "
            "Emprestimos irregulares a empresas do grupo economico. "
            "Um dos maiores casos de fraude bancaria no Brasil."
        ),
        "fonte": "https://www.bcb.gov.br/",
        "sinais_pre_evento": [
            "Emprestimos a partes relacionadas",
            "Concentracao de credito",
            "Falta de transparencia",
        ],
    },
]


def seed_eventos_historicos(session: Session) -> int:
    """
    Popula o banco com eventos regulatorios historicos.

    Args:
        session: Sessao do SQLAlchemy.

    Returns:
        Numero de eventos inseridos.
    """
    count = 0

    for evento_data in EVENTOS_HISTORICOS:
        # Verificar se evento ja existe
        existing = (
            session.query(EventoRegulatorio)
            .filter(
                EventoRegulatorio.if_nome == evento_data["if_nome"],
                EventoRegulatorio.data_evento == evento_data["data_evento"],
            )
            .first()
        )

        if existing:
            continue

        # Criar ou buscar IF
        if_obj = (
            session.query(InstituicaoFinanceira)
            .filter(InstituicaoFinanceira.cnpj == evento_data["if_cnpj"])
            .first()
        )

        if not if_obj:
            if_obj = InstituicaoFinanceira(
                cnpj=evento_data["if_cnpj"],
                nome=evento_data["if_nome"],
                segmento=Segmento.BANCO,
                ativo=False,  # IFs com problemas geralmente nao estao mais ativas
            )
            session.add(if_obj)
            session.flush()

        # Criar evento
        evento = EventoRegulatorio(
            if_id=if_obj.id if if_obj.id else None,
            if_nome=evento_data["if_nome"],
            tipo=evento_data["tipo"],
            data_evento=evento_data["data_evento"],
            descricao=evento_data["descricao"],
            fonte=evento_data["fonte"],
            sinais_pre_evento=evento_data.get("sinais_pre_evento", []),
        )
        session.add(evento)
        count += 1

    session.commit()
    return count


def seed_instituicoes_exemplo(session: Session) -> int:
    """
    Popula o banco com algumas instituicoes financeiras de exemplo.

    Args:
        session: Sessao do SQLAlchemy.

    Returns:
        Numero de IFs inseridas.
    """
    instituicoes = [
        {
            "cnpj": "00.000.000/0001-91",
            "nome": "Banco do Brasil S.A.",
            "segmento": Segmento.BANCO,
            "indice_basileia": Decimal("15.5"),
            "indice_liquidez": Decimal("150.0"),
        },
        {
            "cnpj": "60.746.948/0001-12",
            "nome": "Banco Bradesco S.A.",
            "segmento": Segmento.BANCO,
            "indice_basileia": Decimal("14.8"),
            "indice_liquidez": Decimal("145.0"),
        },
        {
            "cnpj": "60.701.190/0001-04",
            "nome": "Itau Unibanco S.A.",
            "segmento": Segmento.BANCO,
            "indice_basileia": Decimal("14.2"),
            "indice_liquidez": Decimal("140.0"),
        },
        {
            "cnpj": "00.360.305/0001-04",
            "nome": "Caixa Economica Federal",
            "segmento": Segmento.BANCO,
            "indice_basileia": Decimal("16.0"),
            "indice_liquidez": Decimal("160.0"),
        },
        {
            "cnpj": "33.657.248/0001-89",
            "nome": "Banco Santander Brasil S.A.",
            "segmento": Segmento.BANCO,
            "indice_basileia": Decimal("13.5"),
            "indice_liquidez": Decimal("135.0"),
        },
    ]

    count = 0
    for if_data in instituicoes:
        existing = (
            session.query(InstituicaoFinanceira)
            .filter(InstituicaoFinanceira.cnpj == if_data["cnpj"])
            .first()
        )

        if existing:
            continue

        if_obj = InstituicaoFinanceira(
            cnpj=if_data["cnpj"],
            nome=if_data["nome"],
            segmento=if_data["segmento"],
            indice_basileia=if_data.get("indice_basileia"),
            indice_liquidez=if_data.get("indice_liquidez"),
            ativo=True,
        )
        session.add(if_obj)
        count += 1

    session.commit()
    return count


def run_all_seeds(session: Session) -> dict[str, int]:
    """
    Executa todos os seeds do banco de dados.

    Args:
        session: Sessao do SQLAlchemy.

    Returns:
        Dicionario com contagem de registros inseridos por tipo.
    """
    return {
        "instituicoes": seed_instituicoes_exemplo(session),
        "eventos": seed_eventos_historicos(session),
    }
