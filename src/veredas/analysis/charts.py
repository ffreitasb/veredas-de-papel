"""
Geracao de graficos com Plotly.

Fornece graficos para:
- Evolucao de taxas ao longo do tempo
- Comparacao entre instituicoes
- Distribuicao de anomalias
- Score de risco
"""

from decimal import Decimal

import plotly.graph_objects as go

from veredas.storage.models import Anomalia, TaxaCDB, TaxaReferencia

# Cores do tema veredas
CORES = {
    "primaria": "#1a1a2e",
    "secundaria": "#16213e",
    "accent": "#0f3460",
    "destaque": "#e94560",
    "verde": "#00d9a6",
    "amarelo": "#ffc107",
    "laranja": "#fd7e14",
    "vermelho": "#dc3545",
    "cinza": "#6c757d",
    "branco": "#ffffff",
}

# Cores por severidade
CORES_SEVERIDADE = {
    "LOW": CORES["verde"],
    "MEDIUM": CORES["amarelo"],
    "HIGH": CORES["laranja"],
    "CRITICAL": CORES["vermelho"],
}


def _layout_padrao() -> dict:
    """Retorna layout padrao para graficos."""
    return {
        "template": "plotly_dark",
        "paper_bgcolor": CORES["primaria"],
        "plot_bgcolor": CORES["secundaria"],
        "font": {"color": CORES["branco"], "family": "Arial, sans-serif"},
        "margin": {"l": 50, "r": 30, "t": 50, "b": 50},
    }


def grafico_evolucao_taxa(
    taxas: list[TaxaCDB],
    titulo: str = "Evolucao da Taxa",
    mostrar_referencia: bool = True,
    taxa_referencia: Decimal | None = None,
) -> str:
    """
    Gera grafico de evolucao de taxa ao longo do tempo.

    Args:
        taxas: Lista de taxas ordenadas por data.
        titulo: Titulo do grafico.
        mostrar_referencia: Se deve mostrar linha de referencia.
        taxa_referencia: Valor da taxa de referencia (ex: CDI).

    Returns:
        HTML do grafico Plotly.
    """
    if not taxas:
        return _grafico_vazio("Sem dados para exibir")

    # Ordenar por data
    taxas_ordenadas = sorted(taxas, key=lambda t: t.data_coleta)

    datas = [t.data_coleta for t in taxas_ordenadas]
    valores = [float(t.percentual) for t in taxas_ordenadas]

    fig = go.Figure()

    # Linha principal
    fig.add_trace(
        go.Scatter(
            x=datas,
            y=valores,
            mode="lines+markers",
            name="Taxa",
            line={"color": CORES["destaque"], "width": 2},
            marker={"size": 6},
            hovertemplate="%{x|%d/%m/%Y}<br>%{y:.2f}%<extra></extra>",
        )
    )

    # Linha de referencia
    if mostrar_referencia and taxa_referencia:
        fig.add_hline(
            y=float(taxa_referencia),
            line_dash="dash",
            line_color=CORES["verde"],
            annotation_text=f"Referencia: {taxa_referencia}%",
        )

    # Linhas de threshold
    fig.add_hline(
        y=130,
        line_dash="dot",
        line_color=CORES["laranja"],
        annotation_text="Alerta (130%)",
    )
    fig.add_hline(
        y=150,
        line_dash="dot",
        line_color=CORES["vermelho"],
        annotation_text="Critico (150%)",
    )

    fig.update_layout(
        **_layout_padrao(),
        title=titulo,
        xaxis_title="Data",
        yaxis_title="% CDI",
        showlegend=False,
        height=400,
    )

    return fig.to_html(full_html=False, include_plotlyjs="cdn")


def grafico_comparacao_ifs(
    dados: list[tuple[str, Decimal]],
    titulo: str = "Comparacao entre Instituicoes",
) -> str:
    """
    Gera grafico de barras comparando taxas entre IFs.

    Args:
        dados: Lista de tuplas (nome_if, taxa).
        titulo: Titulo do grafico.

    Returns:
        HTML do grafico Plotly.
    """
    if not dados:
        return _grafico_vazio("Sem dados para comparacao")

    # Ordenar por taxa (maior para menor)
    dados_ordenados = sorted(dados, key=lambda x: x[1], reverse=True)

    nomes = [d[0] for d in dados_ordenados]
    valores = [float(d[1]) for d in dados_ordenados]

    # Cores baseadas no valor
    cores = []
    for v in valores:
        if v >= 150:
            cores.append(CORES["vermelho"])
        elif v >= 130:
            cores.append(CORES["laranja"])
        elif v >= 110:
            cores.append(CORES["amarelo"])
        else:
            cores.append(CORES["verde"])

    fig = go.Figure()

    fig.add_trace(
        go.Bar(
            x=nomes,
            y=valores,
            marker_color=cores,
            text=[f"{v:.1f}%" for v in valores],
            textposition="outside",
            hovertemplate="%{x}<br>%{y:.2f}%<extra></extra>",
        )
    )

    fig.update_layout(
        **_layout_padrao(),
        title=titulo,
        xaxis_title="Instituicao",
        yaxis_title="% CDI",
        height=400,
        xaxis_tickangle=-45,
    )

    return fig.to_html(full_html=False, include_plotlyjs="cdn")


def grafico_anomalias_por_severidade(
    anomalias: list[Anomalia],
    titulo: str = "Anomalias por Severidade",
) -> str:
    """
    Gera grafico de pizza com distribuicao de anomalias.

    Args:
        anomalias: Lista de anomalias.
        titulo: Titulo do grafico.

    Returns:
        HTML do grafico Plotly.
    """
    if not anomalias:
        return _grafico_vazio("Nenhuma anomalia detectada")

    # Contar por severidade
    contagem = {"LOW": 0, "MEDIUM": 0, "HIGH": 0, "CRITICAL": 0}
    for a in anomalias:
        sev = a.severidade.upper()
        if sev in contagem:
            contagem[sev] += 1

    # Filtrar zeros
    labels = [k for k, v in contagem.items() if v > 0]
    values = [contagem[k] for k in labels]
    colors = [CORES_SEVERIDADE[k] for k in labels]

    fig = go.Figure()

    fig.add_trace(
        go.Pie(
            labels=labels,
            values=values,
            marker_colors=colors,
            hole=0.4,
            textinfo="label+value",
            hovertemplate="%{label}: %{value}<extra></extra>",
        )
    )

    fig.update_layout(
        **_layout_padrao(),
        title=titulo,
        height=350,
        showlegend=True,
        legend={"orientation": "h", "y": -0.1},
    )

    return fig.to_html(full_html=False, include_plotlyjs="cdn")


def grafico_timeline_anomalias(
    anomalias: list[Anomalia],
    titulo: str = "Timeline de Anomalias",
) -> str:
    """
    Gera grafico de timeline com anomalias.

    Args:
        anomalias: Lista de anomalias.
        titulo: Titulo do grafico.

    Returns:
        HTML do grafico Plotly.
    """
    if not anomalias:
        return _grafico_vazio("Nenhuma anomalia para exibir")

    # Ordenar por data
    anomalias_ordenadas = sorted(anomalias, key=lambda a: a.detectado_em)

    fig = go.Figure()

    for sev in ["CRITICAL", "HIGH", "MEDIUM", "LOW"]:
        anomalias_sev = [a for a in anomalias_ordenadas if a.severidade.upper() == sev]

        if anomalias_sev:
            fig.add_trace(
                go.Scatter(
                    x=[a.detectado_em for a in anomalias_sev],
                    y=[sev] * len(anomalias_sev),
                    mode="markers",
                    name=sev,
                    marker={
                        "color": CORES_SEVERIDADE[sev],
                        "size": 12,
                        "symbol": "circle",
                    },
                    hovertemplate=(
                        "%{x|%d/%m/%Y %H:%M}<br>"
                        "Tipo: %{customdata}<extra></extra>"
                    ),
                    customdata=[a.tipo for a in anomalias_sev],
                )
            )

    fig.update_layout(
        **_layout_padrao(),
        title=titulo,
        xaxis_title="Data",
        yaxis_title="Severidade",
        height=300,
        showlegend=True,
    )

    return fig.to_html(full_html=False, include_plotlyjs="cdn")


def grafico_score_risco(
    score: float,
    breakdown: dict | None = None,
    titulo: str = "Score de Risco",
) -> str:
    """
    Gera grafico gauge de score de risco.

    Args:
        score: Score de 0-100.
        breakdown: Detalhamento do score (opcional).
        titulo: Titulo do grafico.

    Returns:
        HTML do grafico Plotly.
    """
    # Determinar cor baseada no score
    if score <= 25:
        cor = CORES["verde"]
    elif score <= 50:
        cor = CORES["amarelo"]
    elif score <= 75:
        cor = CORES["laranja"]
    else:
        cor = CORES["vermelho"]

    fig = go.Figure()

    fig.add_trace(
        go.Indicator(
            mode="gauge+number",
            value=score,
            title={"text": titulo},
            gauge={
                "axis": {"range": [0, 100], "tickwidth": 1},
                "bar": {"color": cor},
                "steps": [
                    {"range": [0, 25], "color": CORES["verde"] + "40"},
                    {"range": [25, 50], "color": CORES["amarelo"] + "40"},
                    {"range": [50, 75], "color": CORES["laranja"] + "40"},
                    {"range": [75, 100], "color": CORES["vermelho"] + "40"},
                ],
                "threshold": {
                    "line": {"color": CORES["branco"], "width": 2},
                    "thickness": 0.75,
                    "value": score,
                },
            },
        )
    )

    fig.update_layout(
        **_layout_padrao(),
        height=300,
    )

    return fig.to_html(full_html=False, include_plotlyjs="cdn")


def grafico_taxas_referencia(
    taxas: list[TaxaReferencia],
    titulo: str = "Taxas de Referencia",
) -> str:
    """
    Gera grafico com evolucao das taxas de referencia (Selic, CDI, IPCA).

    Args:
        taxas: Lista de taxas de referencia.
        titulo: Titulo do grafico.

    Returns:
        HTML do grafico Plotly.
    """
    if not taxas:
        return _grafico_vazio("Sem dados de referencia")

    # Agrupar por indicador
    indicadores: dict[str, list] = {}
    for t in taxas:
        nome = t.indicador.upper()
        if nome not in indicadores:
            indicadores[nome] = {"datas": [], "valores": []}
        indicadores[nome]["datas"].append(t.data)
        indicadores[nome]["valores"].append(float(t.valor_diario or t.valor_anual or 0))

    cores_indicadores = {
        "SELIC": CORES["destaque"],
        "CDI": CORES["verde"],
        "IPCA": CORES["amarelo"],
    }

    fig = go.Figure()

    for nome, dados in indicadores.items():
        # Ordenar por data
        pares = sorted(zip(dados["datas"], dados["valores"], strict=False))
        datas_ord = [p[0] for p in pares]
        valores_ord = [p[1] for p in pares]

        fig.add_trace(
            go.Scatter(
                x=datas_ord,
                y=valores_ord,
                mode="lines",
                name=nome,
                line={"color": cores_indicadores.get(nome, CORES["cinza"]), "width": 2},
                hovertemplate=f"{nome}<br>%{{x|%d/%m/%Y}}<br>%{{y:.4f}}%<extra></extra>",
            )
        )

    fig.update_layout(
        **_layout_padrao(),
        title=titulo,
        xaxis_title="Data",
        yaxis_title="Taxa (%)",
        height=400,
        showlegend=True,
        legend={"orientation": "h", "y": -0.15},
    )

    return fig.to_html(full_html=False, include_plotlyjs="cdn")


def _grafico_vazio(mensagem: str) -> str:
    """Gera grafico placeholder quando nao ha dados."""
    fig = go.Figure()

    fig.add_annotation(
        text=mensagem,
        xref="paper",
        yref="paper",
        x=0.5,
        y=0.5,
        showarrow=False,
        font={"size": 16, "color": CORES["cinza"]},
    )

    fig.update_layout(
        **_layout_padrao(),
        height=300,
        xaxis={"visible": False},
        yaxis={"visible": False},
    )

    return fig.to_html(full_html=False, include_plotlyjs="cdn")
