# Plano de Desenvolvimento - veredas de papel

> Documento técnico detalhado para implementação incremental do projeto.

---

## Fase 1: MVP (Core) - Fundação

**Objetivo**: Sistema funcional de coleta e detecção básica via CLI.

### 1.1 Infraestrutura do Projeto

| Item | Descrição | Arquivos | Status |
|------|-----------|----------|--------|
| 1.1.1 | Estrutura de diretórios | `src/veredas/*` | ✅ |
| 1.1.2 | Configuração do projeto | `pyproject.toml` | ✅ |
| 1.1.3 | Configurações da aplicação | `src/veredas/config.py` | ⬜ |
| 1.1.4 | Gitignore e editorconfig | `.gitignore`, `.editorconfig` | ⬜ |
| 1.1.5 | Pre-commit hooks | `.pre-commit-config.yaml` | ⬜ |

### 1.2 Camada de Dados

| Item | Descrição | Arquivos | Status |
|------|-----------|----------|--------|
| 1.2.1 | Modelos SQLAlchemy | `src/veredas/storage/models.py` | ✅ |
| 1.2.2 | Gerenciador de banco | `src/veredas/storage/database.py` | ✅ |
| 1.2.3 | Repositórios | `src/veredas/storage/repository.py` | ✅ |
| 1.2.4 | Migrations com Alembic | `alembic/`, `alembic.ini` | ⬜ |
| 1.2.5 | Seed de eventos históricos | `src/veredas/storage/seeds.py` | ⬜ |

### 1.3 Coletores de Dados

| Item | Descrição | Arquivos | Status |
|------|-----------|----------|--------|
| 1.3.1 | Base do coletor | `src/veredas/collectors/base.py` | ⬜ |
| 1.3.2 | Coletor Taxa Selic | `src/veredas/collectors/bcb.py` | ⬜ |
| 1.3.3 | Coletor CDI | `src/veredas/collectors/bcb.py` | ⬜ |
| 1.3.4 | Coletor IPCA | `src/veredas/collectors/bcb.py` | ⬜ |
| 1.3.5 | Coletor IFData | `src/veredas/collectors/ifdata.py` | ⬜ |
| 1.3.6 | Scheduler de coleta | `src/veredas/collectors/scheduler.py` | ⬜ |

### 1.4 Detecção de Anomalias

| Item | Descrição | Arquivos | Status |
|------|-----------|----------|--------|
| 1.4.1 | Interface base | `src/veredas/detectors/base.py` | ⬜ |
| 1.4.2 | Regras de spread | `src/veredas/detectors/rules.py` | ⬜ |
| 1.4.3 | Regras de variação | `src/veredas/detectors/rules.py` | ⬜ |
| 1.4.4 | Regras de divergência | `src/veredas/detectors/rules.py` | ⬜ |
| 1.4.5 | Orquestrador de detecção | `src/veredas/detectors/engine.py` | ⬜ |

### 1.5 Interface CLI

| Item | Descrição | Arquivos | Status |
|------|-----------|----------|--------|
| 1.5.1 | Estrutura base CLI | `src/veredas/cli/main.py` | ⬜ |
| 1.5.2 | Comando `init` | `src/veredas/cli/commands/init.py` | ⬜ |
| 1.5.3 | Comando `collect` | `src/veredas/cli/commands/collect.py` | ⬜ |
| 1.5.4 | Comando `analyze` | `src/veredas/cli/commands/analyze.py` | ⬜ |
| 1.5.5 | Comando `alerts` | `src/veredas/cli/commands/alerts.py` | ⬜ |
| 1.5.6 | Comando `export` | `src/veredas/cli/commands/export.py` | ⬜ |
| 1.5.7 | Comando `status` | `src/veredas/cli/commands/status.py` | ⬜ |

### 1.6 Testes Fase 1

| Item | Descrição | Arquivos | Status |
|------|-----------|----------|--------|
| 1.6.1 | Fixtures e conftest | `tests/conftest.py` | ⬜ |
| 1.6.2 | Testes de modelos | `tests/storage/test_models.py` | ⬜ |
| 1.6.3 | Testes de repositórios | `tests/storage/test_repository.py` | ⬜ |
| 1.6.4 | Testes do coletor BCB | `tests/collectors/test_bcb.py` | ⬜ |
| 1.6.5 | Testes de regras | `tests/detectors/test_rules.py` | ⬜ |
| 1.6.6 | Testes da CLI | `tests/cli/test_commands.py` | ⬜ |

### 1.7 Documentação Fase 1

| Item | Descrição | Arquivos | Status |
|------|-----------|----------|--------|
| 1.7.1 | README principal | `README.md` | ⬜ |
| 1.7.2 | Guia de instalação | `docs/installation.md` | ⬜ |
| 1.7.3 | Guia de uso da CLI | `docs/cli-guide.md` | ⬜ |
| 1.7.4 | Licença | `LICENSE` | ⬜ |

### Critérios de Conclusão Fase 1

- [ ] `veredas init` cria banco de dados
- [ ] `veredas collect --source bcb` coleta Selic/CDI/IPCA
- [ ] `veredas analyze` detecta anomalias por regras
- [ ] `veredas alerts --list` mostra anomalias ativas
- [ ] `veredas export --format csv` exporta dados
- [ ] Cobertura de testes ≥ 80%
- [ ] CI/CD configurado (GitHub Actions)

---

## Fase 2: Dashboard e Alertas

**Objetivo**: Interface visual e notificações proativas.

### 2.1 Dashboard Web

| Item | Descrição | Arquivos | Status |
|------|-----------|----------|--------|
| 2.1.1 | Estrutura Streamlit | `dashboard/app.py` | ⬜ |
| 2.1.2 | Página principal | `dashboard/pages/home.py` | ⬜ |
| 2.1.3 | Página de taxas | `dashboard/pages/taxas.py` | ⬜ |
| 2.1.4 | Página de anomalias | `dashboard/pages/anomalias.py` | ⬜ |
| 2.1.5 | Página de IFs | `dashboard/pages/instituicoes.py` | ⬜ |
| 2.1.6 | Componentes reutilizáveis | `dashboard/components/*.py` | ⬜ |
| 2.1.7 | Gráficos interativos | `dashboard/charts.py` | ⬜ |

### 2.2 Sistema de Alertas

| Item | Descrição | Arquivos | Status |
|------|-----------|----------|--------|
| 2.2.1 | Interface base alertas | `src/veredas/alerts/base.py` | ⬜ |
| 2.2.2 | Alertas por email | `src/veredas/alerts/email.py` | ⬜ |
| 2.2.3 | Bot Telegram | `src/veredas/alerts/telegram.py` | ⬜ |
| 2.2.4 | Configuração de thresholds | `src/veredas/alerts/config.py` | ⬜ |
| 2.2.5 | Histórico de alertas | `src/veredas/alerts/history.py` | ⬜ |
| 2.2.6 | Templates de mensagem | `src/veredas/alerts/templates/` | ⬜ |

### 2.3 Indicadores de Saúde

| Item | Descrição | Arquivos | Status |
|------|-----------|----------|--------|
| 2.3.1 | Parser IFData completo | `src/veredas/collectors/ifdata.py` | ⬜ |
| 2.3.2 | Cálculo Índice Basileia | `src/veredas/analysis/health.py` | ⬜ |
| 2.3.3 | Cálculo Liquidez | `src/veredas/analysis/health.py` | ⬜ |
| 2.3.4 | Score de risco composto | `src/veredas/analysis/risk_score.py` | ⬜ |
| 2.3.5 | Correlação taxa vs saúde | `src/veredas/analysis/correlation.py` | ⬜ |

### 2.4 Histórico de Eventos

| Item | Descrição | Arquivos | Status |
|------|-----------|----------|--------|
| 2.4.1 | Coletor de comunicados BC | `src/veredas/collectors/bc_comunicados.py` | ⬜ |
| 2.4.2 | Parser Diário Oficial | `src/veredas/collectors/dou.py` | ⬜ |
| 2.4.3 | Timeline de eventos | `dashboard/pages/timeline.py` | ⬜ |
| 2.4.4 | Casos de estudo | `data/casos_estudo/*.json` | ⬜ |
| 2.4.5 | Análise retrospectiva | `src/veredas/analysis/retrospective.py` | ⬜ |

### 2.5 Testes Fase 2

| Item | Descrição | Arquivos | Status |
|------|-----------|----------|--------|
| 2.5.1 | Testes de alertas | `tests/alerts/test_*.py` | ⬜ |
| 2.5.2 | Testes de análise | `tests/analysis/test_*.py` | ⬜ |
| 2.5.3 | Testes E2E dashboard | `tests/e2e/test_dashboard.py` | ⬜ |

### Critérios de Conclusão Fase 2

- [ ] Dashboard funcional com gráficos interativos
- [ ] Alertas por email configuráveis
- [ ] Bot Telegram operacional
- [ ] Score de risco por IF visível
- [ ] Timeline de eventos históricos
- [ ] Casos de estudo documentados (Master, BVA, etc.)

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

*Última atualização: Janeiro 2026*
