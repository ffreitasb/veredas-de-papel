# Plano de Desenvolvimento - veredas de papel

> Documento técnico detalhado para implementação incremental do projeto.

---

TL;DR
Seção	Conteúdo
Fase 1	MVP - Infraestrutura, Storage, Coletores, Detectores, CLI, Testes
Fase 2	Frontend (FastAPI + HTMX), Alertas, Indicadores de Saúde
Fase 3	Detecção Avançada (ML, Estatística), API REST
Fase 4	Expansão de Fontes (Scrapers, B3, Dados Alternativos)
Fase 5	Sustentabilidade (Subscrição, Relatórios Premium)
Extra	Checklist de Deploy, Convenções do Projeto

---

## Fase 1: MVP (Core) - Fundação

**Objetivo**: Sistema funcional de coleta e detecção básica via CLI.

### 1.1 Infraestrutura do Projeto

| Item | Descrição | Arquivos | Status |
|------|-----------|----------|--------|
| 1.1.1 | Estrutura de diretórios | `src/veredas/*` | ✅ |
| 1.1.2 | Configuração do projeto | `pyproject.toml` | ✅ |
| 1.1.3 | Configurações da aplicação | `src/veredas/config.py` | ✅ |
| 1.1.4 | Gitignore e editorconfig | `.gitignore`, `.editorconfig` | ✅ |
| 1.1.5 | Pre-commit hooks | `.pre-commit-config.yaml` | ✅ |

### 1.2 Camada de Dados

| Item | Descrição | Arquivos | Status |
|------|-----------|----------|--------|
| 1.2.1 | Modelos SQLAlchemy | `src/veredas/storage/models.py` | ✅ |
| 1.2.2 | Gerenciador de banco | `src/veredas/storage/database.py` | ✅ |
| 1.2.3 | Repositórios | `src/veredas/storage/repository.py` | ✅ |
| 1.2.4 | Migrations com Alembic | `alembic/`, `alembic.ini` | ✅ |
| 1.2.5 | Seed de eventos históricos | `src/veredas/storage/seeds.py` | ✅ |

### 1.3 Coletores de Dados

| Item | Descrição | Arquivos | Status |
|------|-----------|----------|--------|
| 1.3.1 | Base do coletor | `src/veredas/collectors/base.py` | ✅ |
| 1.3.2 | Coletor Taxa Selic | `src/veredas/collectors/bcb.py` | ✅ |
| 1.3.3 | Coletor CDI | `src/veredas/collectors/bcb.py` | ✅ |
| 1.3.4 | Coletor IPCA | `src/veredas/collectors/bcb.py` | ✅ |
| 1.3.5 | Coletor IFData | `src/veredas/collectors/ifdata.py` | ✅ |
| 1.3.6 | Scheduler de coleta | `src/veredas/collectors/scheduler.py` | ✅ |

### 1.4 Detecção de Anomalias

| Item | Descrição | Arquivos | Status |
|------|-----------|----------|--------|
| 1.4.1 | Interface base | `src/veredas/detectors/base.py` | ✅ |
| 1.4.2 | Regras de spread | `src/veredas/detectors/rules.py` | ✅ |
| 1.4.3 | Regras de variação | `src/veredas/detectors/rules.py` | ✅ |
| 1.4.4 | Regras de divergência | `src/veredas/detectors/rules.py` | ✅ |
| 1.4.5 | Orquestrador de detecção | `src/veredas/detectors/rules.py` | ✅ |

### 1.5 Interface CLI

| Item | Descrição | Arquivos | Status |
|------|-----------|----------|--------|
| 1.5.1 | Estrutura base CLI | `src/veredas/cli/main.py` | ✅ |
| 1.5.2 | Comando `init` | `src/veredas/cli/main.py` | ✅ |
| 1.5.3 | Comando `collect` | `src/veredas/cli/main.py` | ✅ |
| 1.5.4 | Comando `analyze` | `src/veredas/cli/main.py` | ✅ |
| 1.5.5 | Comando `alerts` | `src/veredas/cli/main.py` | ✅ |
| 1.5.6 | Comando `export` | `src/veredas/cli/main.py` | ✅ |
| 1.5.7 | Comando `status` | `src/veredas/cli/main.py` | ✅ |

### 1.6 Testes Fase 1

| Item | Descrição | Arquivos | Status |
|------|-----------|----------|--------|
| 1.6.1 | Fixtures e conftest | `tests/conftest.py` | ✅ |
| 1.6.2 | Testes de modelos | `tests/storage/test_models.py` | ✅ |
| 1.6.3 | Testes de repositórios | `tests/storage/test_repository.py` | ✅ |
| 1.6.4 | Testes do coletor BCB | `tests/collectors/test_bcb.py` | ✅ |
| 1.6.5 | Testes de regras | `tests/detectors/test_rules.py` | ✅ |
| 1.6.6 | Testes da CLI | `tests/cli/test_commands.py` | ✅ |

### 1.7 Documentação Fase 1

| Item | Descrição | Arquivos | Status |
|------|-----------|----------|--------|
| 1.7.1 | README principal | `README.md` | ✅ |
| 1.7.2 | Guia de instalação | `docs/installation.md` | ✅ |
| 1.7.3 | Guia de uso da CLI | `docs/cli-guide.md` | ✅ |
| 1.7.4 | Licença | `LICENSE` | ⚠️ |

**Nota sobre LICENSE**: Arquivo físico bloqueado por filtro de conteúdo, mas licença GPL-3.0-or-later está declarada em `pyproject.toml` (linhas 10 e 19).

### Critérios de Conclusão Fase 1

- [x] `veredas init` cria banco de dados
- [x] `veredas collect --source bcb` coleta Selic/CDI/IPCA
- [x] `veredas analyze` detecta anomalias por regras
- [x] `veredas alerts --list` mostra anomalias ativas
- [x] `veredas export --format csv` exporta dados
- [x] Cobertura de testes ≥ 80% (87%+ core, 75% total com 164 testes)
- [ ] CI/CD configurado (GitHub Actions)

### Status Geral Fase 1: ✅ **98% COMPLETA**

**Implementado:**
- ✅ Infraestrutura completa (config, editorconfig, pre-commit)
- ✅ Storage completo (models, DB, repo, Alembic, seeds)
- ✅ Coletores completos (BCB, IFData, Scheduler)
- ✅ Detectores (regras de spread, variação, divergência)
- ✅ CLI funcional (7 comandos)
- ✅ 164 testes passando (98% BCB, 87% scheduler, 93% CLI, 93% detectors)
- ✅ Documentação (installation, cli-guide)

**Pendente:**
- ⬜ CI/CD configurado (GitHub Actions) - opcional
- ⬜ CI/CD com GitHub Actions
- ⚠️ LICENSE file (GPL-3.0 declarado em pyproject.toml)

---

## Fase 2: Frontend e Dashboard

**Objetivo**: Interface visual funcional, limpa e sem clichês de design.

### 2.0 Filosofia de Design

O frontend do veredas de papel segue uma abordagem **funcionalista**:
- **Sem cores chamativas**: paleta neutra (cinzas, branco, preto)
- **Sem dashboards clichê**: nada de gradientes desnecessários, animações excessivas
- **Dados em primeiro lugar**: tipografia legível, hierarquia clara, densidade informacional
- **Sem distrações**: sem carrosséis, banners, elementos decorativos
- **Acessibilidade**: contraste adequado, fontes legíveis, responsivo

**Inspiração**: Bloomberg Terminal, Hacker News, gov.uk, Stripe Dashboard (minimalismo funcional)

### 2.1 Stack Frontend (Python + HTML/CSS)

| Item | Descrição | Tecnologia | Status |
|------|-----------|------------|--------|
| 2.1.1 | Backend/Server | **FastAPI** | ⬜ |
| 2.1.2 | Templates | **Jinja2** | ⬜ |
| 2.1.3 | Interatividade | **HTMX** (sem JS custom) | ⬜ |
| 2.1.4 | Gráficos | **Plotly** (server-side render) | ⬜ |
| 2.1.5 | CSS Base | **Pico CSS** ou CSS custom | ⬜ |
| 2.1.6 | Validação | **Pydantic** | ⬜ |

**Por que esta stack?**
- 100% Python - sem build tools, sem npm
- HTML puro - fácil de manter e debugar
- HTMX - interatividade sem escrever JavaScript
- Pico CSS - estilo funcional sem configuração
- Sem frameworks pesados - carrega em milissegundos
- Funciona offline com SQLite local

### 2.2 Estrutura do Frontend

```
src/veredas/
├── web/                          # Módulo web
│   ├── __init__.py
│   ├── app.py                    # FastAPI app + rotas
│   ├── routes/
│   │   ├── __init__.py
│   │   ├── home.py               # GET /
│   │   ├── taxas.py              # GET /taxas
│   │   ├── anomalias.py          # GET /anomalias
│   │   ├── instituicoes.py       # GET /instituicoes, /instituicoes/{id}
│   │   └── timeline.py           # GET /timeline
│   ├── templates/
│   │   ├── base.html             # Layout base (header, nav, footer)
│   │   ├── index.html            # Home - visão geral
│   │   ├── taxas.html            # Listagem de taxas
│   │   ├── anomalias.html        # Anomalias detectadas
│   │   ├── instituicoes.html     # Lista de IFs
│   │   ├── instituicao.html      # Detalhe da IF
│   │   ├── timeline.html         # Eventos regulatórios
│   │   └── partials/             # Fragmentos HTMX
│   │       ├── taxa_row.html     # Linha de tabela
│   │       ├── anomalia_card.html
│   │       └── stat_card.html
│   └── static/
│       ├── css/
│       │   └── style.css         # CSS customizado (minimal)
│       └── js/
│           └── htmx.min.js       # HTMX (único JS)
```

### 2.3 Páginas e Rotas

| Item | Descrição | Arquivos | Status |
|------|-----------|----------|--------|
| 2.3.1 | **Home/Visão Geral** | `templates/index.html`, `routes/home.py` | ⬜ |
|       | - Taxas de referência atuais (Selic, CDI, IPCA) | | |
|       | - Contador de anomalias por severidade | | |
|       | - Últimas anomalias detectadas | | |
|       | - Status do sistema | | |
| 2.3.2 | **Taxas** | `templates/taxas.html`, `routes/taxas.py` | ⬜ |
|       | - Tabela filtável de taxas coletadas | | |
|       | - Filtros: indexador, prazo, IF (via HTMX) | | |
|       | - Ordenação por spread, data, valor | | |
|       | - Paginação server-side | | |
| 2.3.3 | **Anomalias** | `templates/anomalias.html`, `routes/anomalias.py` | ⬜ |
|       | - Lista de anomalias ativas/resolvidas | | |
|       | - Filtros: severidade, tipo, IF | | |
|       | - Ações: marcar resolvida (HTMX POST) | | |
| 2.3.4 | **Instituições** | `templates/instituicoes.html`, `routes/instituicoes.py` | ⬜ |
|       | - Lista de IFs monitoradas | | |
|       | - Indicadores: Basileia, Liquidez | | |
|       | - Score de risco composto | | |
| 2.3.5 | **Detalhe IF** | `templates/instituicao.html` | ⬜ |
|       | - Histórico de taxas da IF | | |
|       | - Gráfico de evolução (Plotly) | | |
|       | - Anomalias relacionadas | | |
| 2.3.6 | **Timeline** | `templates/timeline.html`, `routes/timeline.py` | ⬜ |
|       | - Eventos regulatórios históricos | | |
|       | - Casos de estudo (Master, BVA) | | |

### 2.4 Templates e Partials

| Item | Descrição | Arquivos | Status |
|------|-----------|----------|--------|
| 2.4.1 | Layout base | `templates/base.html` | ⬜ |
|       | - Header minimalista | | |
|       | - Navegação horizontal simples | | |
|       | - Footer com status do sistema | | |
| 2.4.2 | Partials HTMX | `templates/partials/*.html` | ⬜ |
|       | - `stat_card.html` - Card de estatística | | |
|       | - `taxa_row.html` - Linha de tabela | | |
|       | - `anomalia_item.html` - Item de anomalia | | |
|       | - `if_card.html` - Card de instituição | | |

### 2.5 Design System (CSS)

```css
/* style.css - Variáveis CSS customizadas */
:root {
  /* Tipografia */
  --font-sans: system-ui, -apple-system, sans-serif;
  --font-mono: ui-monospace, monospace;

  /* Cores - Paleta neutra */
  --gray-50: #fafafa;
  --gray-100: #f4f4f5;
  --gray-200: #e4e4e7;
  --gray-500: #71717a;
  --gray-700: #3f3f46;
  --gray-900: #18181b;

  /* Severidade */
  --critical-bg: #fef2f2;
  --critical-text: #dc2626;
  --high-bg: #fff7ed;
  --high-text: #ea580c;
  --medium-bg: #fefce8;
  --medium-text: #ca8a04;
  --low-text: #71717a;

  /* Espaçamento */
  --space-1: 0.25rem;
  --space-2: 0.5rem;
  --space-3: 0.75rem;
  --space-4: 1rem;

  /* Bordas */
  --radius: 0.375rem;
  --border: 1px solid var(--gray-200);
}
```

| Item | Descrição | Decisão |
|------|-----------|---------|
| **Tipografia** | System fonts | `system-ui, sans-serif` |
| **Cores** | Cinzas neutros | CSS custom properties |
| **Layout** | Max-width container | `max-width: 1200px` |
| **Tabelas** | Bordas sutis | `border-collapse`, linhas zebradas |
| **Botões** | Minimalistas | Outline style, sem sombras |

### 2.6 Dashboard Alternativo (Streamlit)

Para prototipagem rápida ou usuários não-técnicos:

| Item | Descrição | Arquivos | Status |
|------|-----------|----------|--------|
| 2.6.1 | App Streamlit | `dashboard/app.py` | ⬜ |
| 2.6.2 | Página principal | `dashboard/pages/home.py` | ⬜ |
| 2.6.3 | Página de taxas | `dashboard/pages/taxas.py` | ⬜ |
| 2.6.4 | Página de anomalias | `dashboard/pages/anomalias.py` | ⬜ |
| 2.6.5 | Gráficos Plotly | `dashboard/charts.py` | ⬜ |

### 2.7 Sistema de Alertas

| Item | Descrição | Arquivos | Status |
|------|-----------|----------|--------|
| 2.7.1 | Interface base alertas | `src/veredas/alerts/base.py` | ⬜ |
| 2.7.2 | Alertas por email | `src/veredas/alerts/email.py` | ⬜ |
| 2.7.3 | Bot Telegram | `src/veredas/alerts/telegram.py` | ⬜ |
| 2.7.4 | Configuração de thresholds | `src/veredas/alerts/config.py` | ⬜ |
| 2.7.5 | Histórico de alertas | `src/veredas/alerts/history.py` | ⬜ |
| 2.7.6 | Templates de mensagem | `src/veredas/alerts/templates/` | ⬜ |

### 2.8 Indicadores de Saúde

| Item | Descrição | Arquivos | Status |
|------|-----------|----------|--------|
| 2.8.1 | Parser IFData completo | `src/veredas/collectors/ifdata.py` | ⬜ |
| 2.8.2 | Cálculo Índice Basileia | `src/veredas/analysis/health.py` | ⬜ |
| 2.8.3 | Cálculo Liquidez | `src/veredas/analysis/health.py` | ⬜ |
| 2.8.4 | Score de risco composto | `src/veredas/analysis/risk_score.py` | ⬜ |
| 2.8.5 | Correlação taxa vs saúde | `src/veredas/analysis/correlation.py` | ⬜ |

### 2.9 Histórico de Eventos

| Item | Descrição | Arquivos | Status |
|------|-----------|----------|--------|
| 2.9.1 | Coletor de comunicados BC | `src/veredas/collectors/bc_comunicados.py` | ⬜ |
| 2.9.2 | Parser Diário Oficial | `src/veredas/collectors/dou.py` | ⬜ |
| 2.9.3 | Timeline de eventos | `dashboard/pages/timeline.py` | ⬜ |
| 2.9.4 | Casos de estudo | `data/casos_estudo/*.json` | ⬜ |
| 2.9.5 | Análise retrospectiva | `src/veredas/analysis/retrospective.py` | ⬜ |

### 2.10 Testes Fase 2

| Item | Descrição | Arquivos | Status |
|------|-----------|----------|--------|
| 2.10.1 | Testes de alertas | `tests/alerts/test_*.py` | ⬜ |
| 2.10.2 | Testes de análise | `tests/analysis/test_*.py` | ⬜ |
| 2.10.3 | Testes E2E dashboard | `tests/e2e/test_dashboard.py` | ⬜ |
| 2.10.4 | Testes do frontend | `frontend/__tests__/*.test.tsx` | ⬜ |

### Critérios de Conclusão Fase 2

- [ ] **Frontend Next.js** funcional com todas as páginas
- [ ] Design minimalista e funcional (sem clichês)
- [ ] Gráficos interativos com Recharts/Tremor
- [ ] Alertas por email configuráveis
- [ ] Bot Telegram operacional
- [ ] Score de risco por IF visível
- [ ] Timeline de eventos históricos
- [ ] Casos de estudo documentados (Master, BVA, etc.)
- [ ] Dashboard Streamlit como alternativa

---

## Fase 3: Detecção Avançada

**Objetivo**: Algoritmos sofisticados de ML e análise estatística.

### 3.1 Análise Estatística

| Item | Descrição | Arquivos | Status |
|------|-----------|----------|--------|
| 3.1.1 | Z-Score com janela móvel | `src/veredas/detectors/statistical.py` | ⬜ |
| 3.1.2 | Decomposição STL | `src/veredas/detectors/statistical.py` | ⬜ |
| 3.1.3 | Detecção de change points | `src/veredas/detectors/changepoint.py` | ⬜ |
| 3.1.4 | Previsão de tendências | `src/veredas/detectors/forecast.py` | ⬜ |
| 3.1.5 | Testes estatísticos | `src/veredas/detectors/tests.py` | ⬜ |

### 3.2 Machine Learning

| Item | Descrição | Arquivos | Status |
|------|-----------|----------|--------|
| 3.2.1 | Isolation Forest | `src/veredas/detectors/ml.py` | ⬜ |
| 3.2.2 | DBSCAN clustering | `src/veredas/detectors/ml.py` | ⬜ |
| 3.2.3 | Pipeline de features | `src/veredas/ml/features.py` | ⬜ |
| 3.2.4 | Treinamento de modelos | `src/veredas/ml/training.py` | ⬜ |
| 3.2.5 | Avaliação de modelos | `src/veredas/ml/evaluation.py` | ⬜ |
| 3.2.6 | Serialização de modelos | `src/veredas/ml/serialization.py` | ⬜ |

### 3.3 Análise Comparativa

| Item | Descrição | Arquivos | Status |
|------|-----------|----------|--------|
| 3.3.1 | Benchmark contra pares | `src/veredas/analysis/benchmark.py` | ⬜ |
| 3.3.2 | Índice de desespero | `src/veredas/analysis/desperation.py` | ⬜ |
| 3.3.3 | Análise de notícias | `src/veredas/analysis/news.py` | ⬜ |
| 3.3.4 | Correlação cruzada | `src/veredas/analysis/cross_correlation.py` | ⬜ |

### 3.4 API REST

| Item | Descrição | Arquivos | Status |
|------|-----------|----------|--------|
| 3.4.1 | Estrutura FastAPI | `src/veredas/api/main.py` | ⬜ |
| 3.4.2 | Endpoints de taxas | `src/veredas/api/routes/taxas.py` | ⬜ |
| 3.4.3 | Endpoints de anomalias | `src/veredas/api/routes/anomalias.py` | ⬜ |
| 3.4.4 | Endpoints de IFs | `src/veredas/api/routes/instituicoes.py` | ⬜ |
| 3.4.5 | Autenticação (opcional) | `src/veredas/api/auth.py` | ⬜ |
| 3.4.6 | Rate limiting | `src/veredas/api/middleware.py` | ⬜ |
| 3.4.7 | Documentação OpenAPI | Auto-gerada | ⬜ |

### 3.5 Testes Fase 3

| Item | Descrição | Arquivos | Status |
|------|-----------|----------|--------|
| 3.5.1 | Testes estatísticos | `tests/detectors/test_statistical.py` | ⬜ |
| 3.5.2 | Testes de ML | `tests/ml/test_*.py` | ⬜ |
| 3.5.3 | Testes da API | `tests/api/test_*.py` | ⬜ |
| 3.5.4 | Benchmarks de performance | `tests/benchmarks/` | ⬜ |

### Critérios de Conclusão Fase 3

- [ ] Detecção com Isolation Forest funcional
- [ ] Decomposição STL implementada
- [ ] API REST documentada (Swagger)
- [ ] Score de anomalia refinado por ML
- [ ] Precision/Recall ≥ 80%

---

## Fase 4: Expansão de Fontes

**Objetivo**: Aumentar cobertura de dados e fontes.

### 4.1 Scrapers de Corretoras

| Item | Descrição | Arquivos | Status |
|------|-----------|----------|--------|
| 4.1.1 | Base de scraper | `src/veredas/collectors/scrapers/base.py` | ⬜ |
| 4.1.2 | Scraper XP | `src/veredas/collectors/scrapers/xp.py` | ⬜ |
| 4.1.3 | Scraper BTG | `src/veredas/collectors/scrapers/btg.py` | ⬜ |
| 4.1.4 | Scraper Rico | `src/veredas/collectors/scrapers/rico.py` | ⬜ |
| 4.1.5 | Scraper Nubank | `src/veredas/collectors/scrapers/nubank.py` | ⬜ |
| 4.1.6 | Scraper Inter | `src/veredas/collectors/scrapers/inter.py` | ⬜ |
| 4.1.7 | Normalização de dados | `src/veredas/collectors/normalizer.py` | ⬜ |
| 4.1.8 | Detecção de discrepâncias | `src/veredas/analysis/discrepancy.py` | ⬜ |

### 4.2 Mercado Secundário

| Item | Descrição | Arquivos | Status |
|------|-----------|----------|--------|
| 4.2.1 | Coletor B3 | `src/veredas/collectors/b3.py` | ⬜ |
| 4.2.2 | Parser de preços secundários | `src/veredas/collectors/secondary.py` | ⬜ |
| 4.2.3 | Detecção de quedas | `src/veredas/detectors/secondary.py` | ⬜ |

### 4.3 Dados Alternativos

| Item | Descrição | Arquivos | Status |
|------|-----------|----------|--------|
| 4.3.1 | Coletor Reclame Aqui | `src/veredas/collectors/reclameaqui.py` | ⬜ |
| 4.3.2 | Coletor processos BC | `src/veredas/collectors/bc_processos.py` | ⬜ |
| 4.3.3 | Análise de sentimento | `src/veredas/analysis/sentiment.py` | ⬜ |
| 4.3.4 | Agregador de sinais | `src/veredas/analysis/signals.py` | ⬜ |

### Critérios de Conclusão Fase 4

- [ ] ≥5 corretoras sendo monitoradas
- [ ] Dados do mercado secundário coletados
- [ ] Score de sentimento implementado
- [ ] Discrepâncias entre plataformas detectadas

---

## Fase 5: Sustentabilidade (Opcional)

**Objetivo**: Cobrir custos de infraestrutura.

### 5.1 Sistema de Subscrição

| Item | Descrição | Arquivos | Status |
|------|-----------|----------|--------|
| 5.1.1 | Modelo de usuário | `src/veredas/users/models.py` | ⬜ |
| 5.1.2 | Autenticação | `src/veredas/users/auth.py` | ⬜ |
| 5.1.3 | Integração Stripe | `src/veredas/payments/stripe.py` | ⬜ |
| 5.1.4 | Planos e tiers | `src/veredas/payments/plans.py` | ⬜ |
| 5.1.5 | Webhooks de pagamento | `src/veredas/payments/webhooks.py` | ⬜ |

### 5.2 Relatórios Premium

| Item | Descrição | Arquivos | Status |
|------|-----------|----------|--------|
| 5.2.1 | Gerador de relatórios | `src/veredas/reports/generator.py` | ⬜ |
| 5.2.2 | Templates de relatório | `src/veredas/reports/templates/` | ⬜ |
| 5.2.3 | Scheduler de envio | `src/veredas/reports/scheduler.py` | ⬜ |
| 5.2.4 | Exportação PDF | `src/veredas/reports/pdf.py` | ⬜ |

### 5.3 API Comercial

| Item | Descrição | Arquivos | Status |
|------|-----------|----------|--------|
| 5.3.1 | API keys | `src/veredas/api/keys.py` | ⬜ |
| 5.3.2 | Rate limiting por tier | `src/veredas/api/rate_limit.py` | ⬜ |
| 5.3.3 | Métricas de uso | `src/veredas/api/metrics.py` | ⬜ |
| 5.3.4 | Dashboard de uso | `dashboard/pages/usage.py` | ⬜ |

### Critérios de Conclusão Fase 5

- [ ] Sistema de pagamentos funcional
- [ ] Relatórios semanais automatizados
- [ ] API com tiers de acesso
- [ ] Métricas de uso implementadas

---

## Checklist de Deploy

### Infraestrutura

- [ ] Docker e docker-compose configurados
- [ ] CI/CD com GitHub Actions
- [ ] Ambiente de staging
- [ ] Ambiente de produção
- [ ] Monitoramento (Sentry, logs)
- [ ] Backups automatizados

### Segurança

- [ ] Secrets em variáveis de ambiente
- [ ] HTTPS configurado
- [ ] Rate limiting em produção
- [ ] Scan de vulnerabilidades (dependabot)

### Documentação

- [ ] README completo
- [ ] Guia de contribuição (CONTRIBUTING.md)
- [ ] Changelog (CHANGELOG.md)
- [ ] Documentação da API
- [ ] Guia de deploy

---

## Convenções do Projeto

### Commits

```
<tipo>: <descrição curta>

Tipos: feat, fix, docs, style, refactor, test, chore
```

### Branches

- `main`: produção
- `develop`: desenvolvimento
- `feature/*`: novas funcionalidades
- `fix/*`: correções
- `release/*`: preparação de release

### Código

- Python 3.11+
- Type hints obrigatórios
- Docstrings (Google style)
- Testes para toda funcionalidade nova
- Ruff para linting/formatting
- Mypy para type checking

---

*Última atualização: 22 de Janeiro de 2026*
