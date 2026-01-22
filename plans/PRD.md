# PRD: veredas de papel

> *"Nem todo atalho leva ao destino. Monitore o risco."*

## 1. Visão Geral

**Nome**: veredas de papel
**Tipo**: Ferramenta FOSS (Free and Open Source Software)
**Licença**: MIT

### Sobre o Nome

Inspirado na obra-prima de Guimarães Rosa, *Grande Sertão: Veredas*, o nome reconhece que o mercado financeiro brasileiro é um território hostil, vasto e traiçoeiro. Como dizia o jagunço Riobaldo: *"Viver é muito perigoso"*. Investir também é.

- **Vereda**: No sertão, é um oásis, um caminho com água em meio à secura. No contexto deste software, representa o *atalho que instituições financeiras em dificuldade tomam*. Ao oferecerem taxas muito acima do mercado, esses bancos criam um atalho desesperado para captar liquidez rápida. Para o investidor desavisado, parece o caminho mais curto para a riqueza; na realidade, é frequentemente um desvio para a insolvência.

- **De Papel**: CDBs são, no jargão, "papéis". Mas a expressão carrega o peso da fragilidade ("tigre de papel", "castelo de cartas"). A "vereda de papel" é um caminho que não tem chão firme — uma estrada desenhada em contratos e promessas, mas sem lastro real de solvência.

**veredas de papel** é uma ferramenta de inteligência open source que monitora o mercado de renda fixa em busca de anomalias. Ela ilumina os atalhos perigosos criados por emissores de crédito, revelando onde a promessa de rentabilidade é, na verdade, um sinal de fragilidade estrutural.

### Problema
Investidores de varejo não têm ferramentas para identificar comportamentos anômalos nas taxas de CDB oferecidas por instituições financeiras. O caso do Banco Master (2025) demonstrou que taxas extremamente atrativas (120-185% CDI, IPCA+30%) eram sinais claros de risco que a maioria dos investidores ignorou, resultando em perdas significativas.

### Proposta de Valor
Sistema automatizado que:
1. **Monitora** taxas de CDB de múltiplas instituições financeiras
2. **Detecta** anomalias e padrões de risco (spreads anormais, saltos bruscos, distorções)
3. **Alerta** investidores sobre comportamentos suspeitos
4. **Correlaciona** com indicadores de saúde financeira das instituições

### Diferencial vs. Ferramentas Existentes

| Yubb/Comparabem/Investidor10 | monitoraCDB |
|------------------------------|-------------|
| Comparar para investir | Monitorar para proteger |
| Ranking estático | Análise temporal |
| Foco em rentabilidade | Foco em risco/anomalias |
| Sem alertas proativos | Alertas automáticos |
| Sem histórico | Histórico completo |

---

## 2. Personas

### P1: Investidor de Varejo
- Investe em CDBs via corretoras
- Quer saber se uma taxa "boa demais" é sinal de risco
- Não tem tempo para monitorar manualmente

### P2: Analista Financeiro
- Precisa de dados históricos de taxas
- Quer identificar tendências de mercado
- Necessita exportar dados para análises

### P3: Jornalista/Pesquisador
- Investiga comportamento de instituições financeiras
- Precisa de evidências de padrões anômalos
- Requer dados confiáveis e auditáveis

---

## 3. Fontes de Dados

### 3.1 Fontes Primárias (APIs Oficiais)

| Fonte | Dados | Frequência | Acesso |
|-------|-------|------------|--------|
| BC - Taxa Selic | Taxa de referência | Diária | API pública |
| BC - IFData | Saúde das IFs (capital, liquidez) | Trimestral | API pública |
| BC - Taxas de Crédito | Taxas de empréstimo por IF | 5 dias úteis | API pública |
| B3 - Market Data | Dados históricos renda fixa | Diária | API pública |

**Bibliotecas disponíveis**:
- `python-bcb` - Interface Python para APIs do Banco Central
- `bancocentralbrasil` - Taxas oficiais (Selic, IPCA)

### 3.2 Fontes Secundárias (Scraping)

| Fonte | Dados | Desafios |
|-------|-------|----------|
| XP Investimentos | CDBs disponíveis | Autenticação, rate limiting |
| BTG Pactual Digital | CDBs disponíveis | Autenticação, rate limiting |
| Rico | CDBs disponíveis | Autenticação, rate limiting |
| Mercado secundário | CDBs em negociação | Dados esparsos |

### 3.3 Fontes Complementares

| Fonte | Dados | Uso |
|-------|-------|-----|
| Yubb | Ranking de CDBs | Validação cruzada |
| Comparabem | Taxas agregadas | Validação cruzada |
| FGC | Instituições cobertas | Verificação de garantia |

### 3.4 Fontes para Histórico de Eventos

| Fonte | Dados | Acesso |
|-------|-------|--------|
| BC - Comunicados | Intervenções, RAET, liquidações | Site BC (scraping) |
| BC - IF.Data Histórico | Dados históricos de IFs extintas | API pública |
| Diário Oficial da União | Atos normativos | API dados.gov.br |
| Notícias financeiras | Cobertura jornalística | APIs de notícias |

**Eventos Históricos Relevantes (seed data)**:
- 2025: Banco Master (liquidação)
- 2024: Will Bank (subsidiária Master)
- 2019: Banco Neon (intervenção)
- 2016: Banco Bonsucesso (liquidação)
- 2014: BVA (liquidação)
- 2012: Banco Cruzeiro do Sul (liquidação)

---

## 4. Funcionalidades por Fase

### Fase 1: MVP (Core)

**Objetivo**: Coletar dados públicos e detectar anomalias básicas

#### F1.1 - Coleta de Dados do BC
- [ ] Integrar com API do Banco Central via `python-bcb`
- [ ] Coletar taxa Selic diariamente
- [ ] Coletar dados IFData trimestralmente
- [ ] Armazenar em banco de dados SQLite

#### F1.2 - Monitoramento de Taxas de CDB
- [ ] Scraping básico de 1-2 plataformas públicas
- [ ] Armazenamento histórico de taxas
- [ ] Cálculo de spread vs CDI/Selic

#### F1.3 - Detecção de Anomalias (Básica)
- [ ] **Spread anormal**: CDB > 130% CDI = alerta
- [ ] **Salto brusco**: Variação > 10% em 7 dias = alerta
- [ ] **Divergência de mercado**: IF oferece >20% acima da média = alerta

#### F1.4 - Interface CLI
- [ ] Comando para consultar taxas atuais
- [ ] Comando para listar alertas ativos
- [ ] Comando para exportar dados (CSV)

**Entregáveis Fase 1**:
- Coleta automatizada de dados públicos
- Banco de dados SQLite com histórico
- CLI funcional com alertas básicos
- Documentação de instalação

---

### Fase 2: Dashboard e Alertas

**Objetivo**: Interface visual e notificações proativas

#### F2.1 - Dashboard Web
- [ ] Interface web com Streamlit ou Dash
- [ ] Gráficos de evolução de taxas por IF
- [ ] Visualização de anomalias detectadas
- [ ] Filtros por IF, período, tipo de indexador

#### F2.2 - Sistema de Alertas
- [ ] Alertas via email (SMTP)
- [ ] Alertas via Telegram bot
- [ ] Configuração de thresholds personalizados
- [ ] Histórico de alertas

#### F2.3 - Indicadores de Saúde das IFs
- [ ] Integrar dados IFData (Basileia, liquidez)
- [ ] Score de risco por instituição
- [ ] Correlação entre taxa oferecida e saúde financeira

#### F2.4 - Histórico de Eventos Regulatórios
- [ ] Timeline de intervenções do BC em instituições financeiras
- [ ] Registro de liquidações, RAET, intervenções
- [ ] Correlação de eventos com comportamento de taxas pré-crise
- [ ] Biblioteca de "casos de estudo" (ex: Banco Master, BVA, Cruzeiro do Sul)

**Entregáveis Fase 2**:
- Dashboard web funcional
- Sistema de alertas configurável
- Score de risco por IF
- Timeline de eventos históricos

---

### Fase 3: Detecção Avançada

**Objetivo**: Algoritmos sofisticados de detecção de anomalias

#### F3.1 - Análise de Séries Temporais
- [ ] Decomposição STL (sazonalidade, tendência, ruído)
- [ ] Detecção de change points
- [ ] Previsão de tendências

#### F3.2 - Machine Learning
- [ ] Isolation Forest para detecção de outliers
- [ ] Clustering (DBSCAN) para agrupamento de comportamentos
- [ ] LSTM para detecção de padrões sequenciais anômalos

#### F3.3 - Análise Comparativa
- [ ] Benchmark contra pares (bancos de mesmo porte)
- [ ] Índice de "desespero de captação"
- [ ] Correlação com notícias e eventos

**Entregáveis Fase 3**:
- Algoritmos de ML integrados
- Scores de anomalia refinados
- API REST para integrações

---

### Fase 4: Expansão de Fontes

**Objetivo**: Aumentar cobertura de dados

#### F4.1 - Mais Corretoras
- [ ] Scraping de 5+ plataformas principais
- [ ] Normalização de dados entre plataformas
- [ ] Detecção de discrepâncias entre plataformas

#### F4.2 - Mercado Secundário
- [ ] Monitorar preços de CDBs no secundário
- [ ] Detectar quedas de preço (sinal de risco)

#### F4.3 - Dados Alternativos
- [ ] Monitorar reclamações no Reclame Aqui
- [ ] Monitorar processos no Bacen
- [ ] Análise de sentimento em redes sociais

---

### Fase 5: Sustentabilidade (Opcional)

**Objetivo**: Cobrir custos de infraestrutura de forma sustentável

#### F5.1 - Relatórios Premium por Email
- [ ] Sistema de subscrição (valor simbólico: R$5-10/mês)
- [ ] Relatórios semanais detalhados por email
- [ ] Análises exclusivas de IFs específicas
- [ ] Alertas prioritários (antes do público geral)
- [ ] Integração com Stripe/PagSeguro para pagamentos

#### F5.2 - API para Desenvolvedores
- [ ] Plano gratuito com rate limiting
- [ ] Plano pago para uso comercial
- [ ] Documentação OpenAPI/Swagger

**Modelo de Sustentabilidade**:
- Core da ferramenta sempre FOSS e gratuito
- Subscrições cobrem apenas custos de infra (servidores, domínio)
- Transparência total sobre uso dos recursos
- Sem paywall para funcionalidades essenciais

---

## 5. Arquitetura Técnica

### 5.1 Stack Tecnológica

```
┌─────────────────────────────────────────────────────────────┐
│                        FRONTEND                              │
│  Streamlit/Dash (Python) │ CLI (Click/Typer)                │
└─────────────────────────────────────────────────────────────┘
                              │
┌─────────────────────────────────────────────────────────────┐
│                        BACKEND                               │
│  FastAPI (API REST)  │  Celery (Jobs)  │  Redis (Cache)     │
└─────────────────────────────────────────────────────────────┘
                              │
┌─────────────────────────────────────────────────────────────┐
│                      DATA LAYER                              │
│  SQLite/PostgreSQL  │  TimescaleDB (séries)  │  MinIO (raw) │
└─────────────────────────────────────────────────────────────┘
                              │
┌─────────────────────────────────────────────────────────────┐
│                      COLLECTORS                              │
│  python-bcb  │  Scrapy/Playwright  │  Requests              │
└─────────────────────────────────────────────────────────────┘
```

### 5.2 Estrutura de Diretórios (Proposta)

```
veredas-de-papel/
├── src/
│   ├── collectors/          # Coletores de dados
│   │   ├── bcb.py           # Banco Central
│   │   ├── b3.py            # B3
│   │   └── scrapers/        # Scrapers de corretoras
│   ├── detectors/           # Algoritmos de detecção
│   │   ├── statistical.py   # Z-score, STL
│   │   ├── ml.py            # Isolation Forest, DBSCAN
│   │   └── rules.py         # Regras de negócio
│   ├── storage/             # Persistência
│   │   ├── models.py        # SQLAlchemy models
│   │   └── repository.py    # Data access
│   ├── alerts/              # Sistema de alertas
│   │   ├── email.py
│   │   └── telegram.py
│   ├── api/                 # API REST
│   │   └── routes.py
│   └── cli/                 # Interface CLI
│       └── commands.py
├── dashboard/               # Interface web
├── tests/
├── docs/
├── docker-compose.yml
├── pyproject.toml
└── README.md
```

### 5.3 Modelo de Dados (Core)

```python
# Evento Regulatório (Histórico)
class EventoRegulatorio:
    id: int
    if_id: int  # FK InstituicaoFinanceira (pode ser NULL se IF não existir mais)
    if_nome: str  # Nome para casos de IFs extintas
    tipo: str  # INTERVENCAO, RAET, LIQUIDACAO, FALENCIA
    data_evento: date
    descricao: str
    fonte: str  # URL da fonte
    taxas_pre_evento: list  # Snapshot das taxas antes do evento
    sinais_detectados: list  # Anomalias que precederam o evento

# Instituição Financeira
class InstituicaoFinanceira:
    id: int
    cnpj: str
    nome: str
    segmento: str  # banco, financeira, etc
    indice_basileia: float  # do IFData
    indice_liquidez: float
    ativo_total: float
    updated_at: datetime

# Taxa de CDB
class TaxaCDB:
    id: int
    if_id: int  # FK InstituicaoFinanceira
    data_coleta: datetime
    indexador: str  # CDI, IPCA, PRE
    percentual: float  # ex: 120.0 para 120% CDI
    prazo_dias: int
    valor_minimo: float
    fonte: str  # xp, btg, etc
    liquidez_diaria: bool

# Anomalia Detectada
class Anomalia:
    id: int
    if_id: int
    taxa_id: int
    tipo: str  # SPREAD_ALTO, SALTO_BRUSCO, etc
    severidade: str  # LOW, MEDIUM, HIGH, CRITICAL
    valor_detectado: float
    valor_esperado: float
    descricao: str
    detectado_em: datetime
    resolvido: bool
```

---

## 6. Algoritmos de Detecção de Anomalias

### 6.1 Regras de Negócio (Fase 1)

| Tipo | Condição | Severidade |
|------|----------|------------|
| SPREAD_ALTO | CDB > 130% CDI | HIGH |
| SPREAD_CRITICO | CDB > 150% CDI | CRITICAL |
| SALTO_BRUSCO | Variação > 10% em 7 dias | MEDIUM |
| SALTO_EXTREMO | Variação > 20% em 7 dias | HIGH |
| DIVERGENCIA | Taxa > média + 2σ | MEDIUM |
| DIVERGENCIA_EXTREMA | Taxa > média + 3σ | HIGH |

### 6.2 Análise Estatística (Fase 2)

```python
# Z-Score com janela móvel
def detectar_anomalia_zscore(taxas: pd.Series, janela: int = 30) -> pd.Series:
    media_movel = taxas.rolling(window=janela).mean()
    std_movel = taxas.rolling(window=janela).std()
    zscore = (taxas - media_movel) / std_movel
    return zscore.abs() > 2.5  # threshold

# Decomposição STL
def detectar_anomalia_stl(taxas: pd.Series) -> pd.Series:
    decomposition = STL(taxas, period=7).fit()
    residuals = decomposition.resid
    threshold = 3 * residuals.std()
    return residuals.abs() > threshold
```

### 6.3 Machine Learning (Fase 3)

```python
# Isolation Forest
def treinar_isolation_forest(dados: pd.DataFrame) -> IsolationForest:
    features = ['spread_cdi', 'variacao_7d', 'variacao_30d',
                'rank_percentil', 'indice_basileia']
    model = IsolationForest(contamination=0.05, random_state=42)
    model.fit(dados[features])
    return model

# DBSCAN para clustering
def detectar_clusters_anomalos(dados: pd.DataFrame) -> np.ndarray:
    features = StandardScaler().fit_transform(dados[['spread_cdi', 'prazo']])
    clustering = DBSCAN(eps=0.5, min_samples=5).fit(features)
    return clustering.labels_ == -1  # -1 = outlier
```

---

## 7. Indicadores-Chave de Risco

### 7.1 Por Instituição

| Indicador | Descrição | Threshold de Alerta |
|-----------|-----------|---------------------|
| Spread Médio | Média das taxas vs CDI | > 125% |
| Volatilidade | Desvio padrão das taxas | > 5% |
| Índice Basileia | Capital vs ativos ponderados | < 11% |
| Liquidez | Capacidade de honrar obrigações | < 100% |

### 7.2 Score de Risco Composto

```python
def calcular_score_risco(if_data: dict) -> float:
    """
    Score de 0 a 100, onde maior = mais arriscado
    """
    score = 0

    # Spread (peso 40%)
    if if_data['spread_cdi'] > 150:
        score += 40
    elif if_data['spread_cdi'] > 130:
        score += 30
    elif if_data['spread_cdi'] > 120:
        score += 20

    # Basileia (peso 30%)
    if if_data['basileia'] < 10:
        score += 30
    elif if_data['basileia'] < 12:
        score += 20
    elif if_data['basileia'] < 15:
        score += 10

    # Volatilidade (peso 20%)
    if if_data['volatilidade'] > 10:
        score += 20
    elif if_data['volatilidade'] > 5:
        score += 10

    # Tendência (peso 10%)
    if if_data['tendencia_7d'] > 5:
        score += 10

    return score
```

---

## 8. Considerações Legais e Éticas

### 8.1 Scraping
- Respeitar `robots.txt` das plataformas
- Implementar rate limiting (1 req/segundo)
- Não armazenar dados pessoais de usuários
- Usar dados apenas para fins informativos

### 8.2 Disclaimer
- Ferramenta não constitui recomendação de investimento
- Dados podem ter atrasos ou imprecisões
- Usuário deve fazer sua própria análise

### 8.3 Privacidade
- Não coletar dados de usuários
- Logs anonimizados
- Sem tracking ou analytics

---

## 9. Métricas de Sucesso

### MVP (Fase 1)
- [ ] Coleta automatizada funcionando 24/7
- [ ] Pelo menos 50 IFs monitoradas
- [ ] Taxa de disponibilidade > 99%
- [ ] Latência de detecção < 1 hora

### Fase 2
- [ ] 100+ usuários ativos
- [ ] Alertas enviados com antecedência de eventos de risco
- [ ] Taxa de falsos positivos < 20%

### Fase 3
- [ ] Detecção de anomalias com >80% precisão
- [ ] Contribuições da comunidade FOSS
- [ ] Citações em mídia financeira

---

## 10. Roadmap

```
2026 Q1 (Jan-Mar)
├── Fase 1: MVP
│   ├── Semana 1-2: Setup projeto, integração BC
│   ├── Semana 3-4: Banco de dados, coleta básica
│   ├── Semana 5-6: Detecção de anomalias (regras)
│   └── Semana 7-8: CLI, documentação, testes

2026 Q2 (Abr-Jun)
├── Fase 2: Dashboard e Alertas
│   ├── Mês 1: Dashboard Streamlit
│   ├── Mês 2: Sistema de alertas
│   └── Mês 3: Indicadores de saúde IF

2026 Q3 (Jul-Set)
├── Fase 3: Detecção Avançada
│   ├── Mês 1: Análise estatística avançada
│   ├── Mês 2: Modelos ML
│   └── Mês 3: API REST

2026 Q4 (Out-Dez)
├── Fase 4: Expansão
│   ├── Mais fontes de dados
│   ├── App mobile (opcional)
│   └── Comunidade FOSS

2027 Q1+ (Futuro)
├── Fase 5: Sustentabilidade (Opcional)
│   ├── Sistema de subscrição para relatórios
│   ├── API para desenvolvedores
│   └── Parcerias com fintechs
```

---

## 11. Riscos e Mitigações

| Risco | Probabilidade | Impacto | Mitigação |
|-------|---------------|---------|-----------|
| Plataformas bloqueiam scraping | Alta | Alto | Usar proxies, múltiplas fontes |
| APIs do BC mudam | Baixa | Médio | Monitorar changelog, testes |
| Falsos positivos geram pânico | Média | Alto | Calibrar thresholds, disclaimers |
| Baixa adoção | Média | Médio | Marketing em comunidades, UX simples |

---

## 12. Arquivos Críticos para Implementação

Para iniciar a Fase 1, os seguintes arquivos serão criados:

1. `src/collectors/bcb.py` - Integração com python-bcb
2. `src/storage/models.py` - Modelos SQLAlchemy
3. `src/detectors/rules.py` - Regras de detecção
4. `src/cli/commands.py` - Interface CLI
5. `tests/test_collectors.py` - Testes de coleta
6. `pyproject.toml` - Dependências do projeto
7. `docker-compose.yml` - Ambiente de desenvolvimento

---

## 13. Verificação e Testes

### Como validar a implementação:

1. **Coleta de dados**:
   ```bash
   python -m veredas collect --source bcb
   # Deve coletar taxa Selic atual e armazenar no banco
   ```

2. **Detecção de anomalias**:
   ```bash
   python -m veredas analyze --if "Banco Master"
   # Deve identificar anomalias baseado em regras
   ```

3. **Alertas**:
   ```bash
   python -m veredas alerts --list
   # Deve listar alertas ativos
   ```

4. **Testes automatizados**:
   ```bash
   pytest tests/ --cov=src --cov-report=term-missing
   # Coverage mínimo: 80%
   ```

---

## Próximos Passos

Após aprovação deste PRD:

1. Criar repositório GitHub com estrutura inicial
2. Configurar CI/CD (GitHub Actions)
3. Implementar Fase 1 seguindo TDD
4. Documentar API e CLI
5. Publicar primeira release (v0.1.0)
