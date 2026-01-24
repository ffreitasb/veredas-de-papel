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

**UTILIZE O ds-engineer e suas skills para desenvolver essa parte**

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

- [ ] **Frontend Python** funcional com todas as páginas
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

**Status**: ✅ **COMPLETA** (232 testes passando, 5 skipped)

### 3.1 Análise Estatística

| Item | Descrição | Arquivos | Status |
|------|-----------|----------|--------|
| 3.1.1 | Z-Score com janela móvel | `src/veredas/detectors/statistical.py` | ✅ |
| 3.1.2 | Decomposição STL | `src/veredas/detectors/statistical.py` | ✅ |
| 3.1.3 | Detecção de change points | `src/veredas/detectors/statistical.py` | ✅ |

### 3.2 Machine Learning

| Item | Descrição | Arquivos | Status |
|------|-----------|----------|--------|
| 3.2.1 | Isolation Forest | `src/veredas/detectors/ml.py` | ✅ |
| 3.2.2 | DBSCAN clustering | `src/veredas/detectors/ml.py` | ✅ |
| 3.2.3 | Pipeline de features | `src/veredas/detectors/features.py` | ✅ |

### 3.3 Detection Engine

| Item | Descrição | Arquivos | Status |
|------|-----------|----------|--------|
| 3.3.1 | Engine unificada | `src/veredas/detectors/engine.py` | ✅ |
| 3.3.2 | Configuração centralizada | `src/veredas/config.py` | ✅ |

### 3.4 API REST de Detecção

| Item | Descrição | Arquivos | Status |
|------|-----------|----------|--------|
| 3.4.1 | Endpoints de detecção | `src/veredas/api/detection.py` | ✅ |
| 3.4.2 | Schemas Pydantic | `src/veredas/api/schemas.py` | ✅ |
| 3.4.3 | Integração web | `src/veredas/web/app.py` | ✅ |

### 3.5 Testes Fase 3

| Item | Descrição | Arquivos | Status |
|------|-----------|----------|--------|
| 3.5.1 | Testes estatísticos | `tests/detectors/test_statistical.py` | ✅ (29 testes) |
| 3.5.2 | Testes de ML | `tests/detectors/test_ml.py` | ✅ (15 testes) |
| 3.5.3 | Testes da engine | `tests/detectors/test_engine.py` | ✅ (20 testes) |

### 3.6 Code Review Fase 3

| Categoria | Issues | Status |
|-----------|--------|--------|
| Security | 4 | ✅ Corrigidas |
| Bugs HIGH | 3 | ✅ Corrigidos |
| Bugs MEDIUM | 7 | ✅ Corrigidos |
| Architecture | 2 | ✅ Corrigidas |
| Performance | 4 | ✅ Otimizadas |
| Code Quality | 4 | ✅ Melhoradas |

### Critérios de Conclusão Fase 3

- [x] Detecção com Isolation Forest funcional
- [x] Decomposição STL implementada
- [x] API REST de detecção (5 endpoints)
- [x] Score de anomalia refinado por ML
- [x] 232 testes passando

---

## Fase 4: Expansão de Fontes

**Objetivo**: Aumentar cobertura de dados através de scrapers de corretoras, mercado secundário e dados alternativos.

**Estimativa**: ~274 horas (10 semanas)

### 4.0 Estrutura de Arquivos

```
src/veredas/
├── collectors/
│   ├── scrapers/
│   │   ├── __init__.py
│   │   ├── base.py              # BaseScraper (extends BaseCollector)
│   │   ├── auth.py              # Autenticação (cookies, sessions)
│   │   ├── anti_bot.py          # Estratégias anti-bot
│   │   ├── normalizer.py        # Normalização de dados
│   │   ├── discrepancy.py       # Detector de discrepâncias
│   │   ├── brokers/             # F4.1 - Scrapers de corretoras
│   │   │   ├── xp.py, btg.py, rico.py, nubank.py, inter.py
│   │   └── alternative/         # F4.3 - Dados alternativos
│   │       ├── reclame_aqui.py, bacen_processos.py
│   ├── b3/                      # F4.2 - Mercado secundário
│   │   ├── api.py, parser.py, models.py
│   └── sentiment/               # F4.3 - Análise de sentimento
│       ├── analyzer.py, aggregator.py
├── detectors/
│   ├── price_drop.py            # F4.2 - Queda de preço secundário
│   ├── platform_discrepancy.py  # F4.1 - Discrepância entre plataformas
│   └── sentiment_risk.py        # F4.3 - Risco por sentimento
```

### 4.1 Framework de Scrapers (Semanas 1-3, ~92h)

| Item | Descrição | Arquivos | Horas | Status |
|------|-----------|----------|-------|--------|
| 4.1.1 | Base de scraper | `scrapers/base.py` | 8h | ⬜ |
| 4.1.2 | Autenticação | `scrapers/auth.py` | 6h | ⬜ |
| 4.1.3 | Anti-bot | `scrapers/anti_bot.py` | 8h | ⬜ |
| 4.1.4 | Normalização | `scrapers/normalizer.py` | 4h | ⬜ |
| 4.1.5 | Scraper XP | `scrapers/brokers/xp.py` | 12h | ⬜ |
| 4.1.6 | Scraper BTG | `scrapers/brokers/btg.py` | 8h | ⬜ |
| 4.1.7 | Scraper Rico | `scrapers/brokers/rico.py` | 12h | ⬜ |
| 4.1.8 | Scraper Nubank | `scrapers/brokers/nubank.py` | 12h | ⬜ |
| 4.1.9 | Scraper Inter | `scrapers/brokers/inter.py` | 8h | ⬜ |
| 4.1.10 | Discrepância | `scrapers/discrepancy.py` | 6h | ⬜ |
| 4.1.11 | Detector | `detectors/platform_discrepancy.py` | 8h | ⬜ |

**Complexidade por Plataforma:**

| Plataforma | Complexidade | Autenticação | JS Rendering |
|------------|--------------|--------------|--------------|
| XP | Alta | Não | Sim (Playwright) |
| BTG | Média | Não | Não (API) |
| Rico | Alta | Não | Sim |
| Nubank | Alta | Sim | Não (API) |
| Inter | Média | Não | Não (API) |

### 4.2 Mercado Secundário B3 (Semanas 4-5, ~40h)

| Item | Descrição | Arquivos | Horas | Status |
|------|-----------|----------|-------|--------|
| 4.2.1 | Modelos B3 | `b3/models.py` | 4h | ⬜ |
| 4.2.2 | API B3 | `b3/api.py` | 16h | ⬜ |
| 4.2.3 | Parser preços | `b3/parser.py` | 8h | ⬜ |
| 4.2.4 | Detector quedas | `detectors/price_drop.py` | 8h | ⬜ |
| 4.2.5 | Migrations | `alembic/` | 4h | ⬜ |

**Thresholds PriceDropDetector:**
- PU drop > 5% → MEDIUM
- PU drop > 10% → HIGH
- PU drop > 20% → CRITICAL

### 4.3 Dados Alternativos (Semanas 6-8, ~56h)

| Item | Descrição | Arquivos | Horas | Status |
|------|-----------|----------|-------|--------|
| 4.3.1 | Reclame Aqui | `alternative/reclame_aqui.py` | 10h | ⬜ |
| 4.3.2 | Processos BC | `alternative/bacen_processos.py` | 10h | ⬜ |
| 4.3.3 | Sentimento | `sentiment/analyzer.py` | 16h | ⬜ |
| 4.3.4 | Agregador | `sentiment/aggregator.py` | 8h | ⬜ |
| 4.3.5 | Detector | `detectors/sentiment_risk.py` | 8h | ⬜ |
| 4.3.6 | Migrations | `alembic/` | 4h | ⬜ |

**Pesos do Agregador de Sinais:**
```python
WEIGHTS = {
    "reclame_aqui": 0.20,
    "bacen_processos": 0.30,
    "sentiment": 0.15,
    "secondary_market": 0.35,
}
```

### 4.4 Integração e Testes (Semanas 9-10, ~86h)

| Item | Descrição | Arquivos | Horas | Status |
|------|-----------|----------|-------|--------|
| 4.4.1 | Engine integration | `detectors/engine.py` | 8h | ⬜ |
| 4.4.2 | CLI commands | `cli/main.py` | 6h | ⬜ |
| 4.4.3 | API endpoints | `api/` | 12h | ⬜ |
| 4.4.4 | Unit tests | `tests/` | 24h | ⬜ |
| 4.4.5 | Integration tests | `tests/integration/` | 16h | ⬜ |
| 4.4.6 | E2E tests | `tests/e2e/` | 12h | ⬜ |
| 4.4.7 | Documentação | `docs/` | 8h | ⬜ |

### 4.5 Novos Comandos CLI

```bash
veredas scrape [all|xp|btg|rico|nubank|inter]
veredas secondary --cnpj 12345678000199 --days 30
veredas complaints --cnpj 12345678000199
veredas processes --cnpj 12345678000199
veredas scrapers  # status
```

### 4.6 Novos Modelos de Banco

```python
# Novos TipoAnomalia
PLATFORM_DISCREPANCY = "platform_discrepancy"
SECONDARY_PRICE_DROP = "secondary_price_drop"
COMPLAINT_SPIKE = "complaint_spike"
REGULATORY_PROCESS = "regulatory_process"
NEGATIVE_SENTIMENT = "negative_sentiment"

# Novos modelos SQLAlchemy
class PrecoSecundario(Base): ...      # Preços B3
class ReclamacaoHistorico(Base): ...  # Reclame Aqui
class ProcessoRegulatorio(Base): ...  # Processos BC
```

### 4.7 Dependências Python

```toml
[project.optional-dependencies]
scrapers = ["playwright>=1.40", "beautifulsoup4>=4.12", "lxml>=5.0", "fake-useragent>=1.4"]
b3 = ["oauthlib>=3.2", "requests-oauthlib>=1.3"]
sentiment = ["transformers>=4.35", "torch>=2.0", "nltk>=3.8"]
```

### 4.8 Riscos e Mitigações

| Risco | Impacto | Mitigação |
|-------|---------|-----------|
| Bloqueio anti-bot | Alto | User agent rotation, delays, Playwright |
| Acesso B3 negado | Alto | Aplicar cedo, fontes alternativas |
| Mudança de HTML | Médio | Seletores abstraídos, monitoramento |
| Rate limiting | Médio | Delays configuráveis, backoff |

### Critérios de Conclusão Fase 4

- [ ] ≥5 corretoras sendo monitoradas
- [ ] Dados do mercado secundário coletados
- [ ] Score de sentimento implementado
- [ ] Discrepâncias entre plataformas detectadas
- [ ] 80%+ cobertura de testes
- [ ] CLI funcional para todas as fontes

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

*Última atualização: 24 de Janeiro de 2026*
