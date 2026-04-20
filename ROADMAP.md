# ROADMAP — veredas de papel

> Ordem de execução: Quick Wins → High Impact → Polishing.
> Cada item tem esforço estimado e critério de conclusão claro.

---

## Fase A — Quick Wins
> Desbloqueiam o que está quebrado e removem peso morto. Esforço baixo, retorno imediato.

### A1 — Corrigir bugs críticos do dashboard (Fase 2)
**Esforço:** 1–2 dias  
**Bloqueia:** qualquer teste manual da interface

| # | Arquivo | Problema | Correção |
|---|---------|----------|----------|
| 1 | `web/routes/home.py:51–53` | Taxa consultada como `"SELIC"` mas salva como `"selic"` | Padronizar para minúsculo |
| 2 | `web/routes/instituicoes.py:143` | Campo `taxa.taxa_percentual` não existe (é `percentual`) | Renomear referência |
| 3 | Templates anomalias | Campo `anomalia.resolvida` (não existe; é `resolvido`) | Corrigir em 2 templates |
| 4 | Templates taxas/instituicoes | `risk_score` referenciado mas ausente no modelo ORM | Remover ou adicionar campo |
| 5 | `web/routes/taxas.py` | HTMX aponta para `/taxas/partials/table` (rota inexistente) | Corrigir para `/taxas/` |
| 6 | Templates instituicao | `instituicao.tipo_instituicao` → usar `instituicao.segmento.value` | Corrigir referência |

**Critério de conclusão:** `uvicorn` sobe sem erro, todas as 5 rotas retornam HTTP 200, dashboard navegável do início ao fim.

---

### A2 — Criar templates ausentes
**Esforço:** meio dia  
**Bloqueia:** rotas que já existem mas lançam `TemplateNotFound`

- `web/templates/evento.html` — página de detalhe de evento regulatório
- `web/templates/taxa_detail.html` — detalhe de uma taxa CDB específica
- `web/templates/partials/instituicao_chart.html` — gráfico HTMX de evolução de taxas por IF

**Critério de conclusão:** nenhuma rota lança `TemplateNotFound`; páginas renderizam com dados reais.

---

### A3 — Remover código morto (simplificação)
**Esforço:** 2–3 horas  
**Impacto:** ~45% de redução de LOC, elimina falsa sensação de "feature pronta"

Remover integralmente de `future_work/src/veredas/`:

- `collectors/b3/` — stub com dados mock
- `scrapers/` — XP, BTG, Rico, Nubank, Inter (dados mock, nunca funcionaram)
- `collectors/alternative/` — ReclameAqui, BACEN processos (stubs)
- `analysis/sentiment/` — aggregator e analyzer, nunca integrados
- `api/` — duplicata da camada `web/`, routes redundantes

**Não remover:** `future_work/src/veredas/alerts/` — email e Telegram têm código real, entram na Fase B.

**Critério de conclusão:** `git diff --stat` mostra remoção líquida de ≥ 5.000 linhas; nenhum import quebrado em `src/veredas/`.

---

### A4 — Corrigir bugs de performance e correção na Fase 3
**Esforço:** 1 dia  
**Impacto:** pipeline de detecção ≥ 2× mais rápido, sem crashes silenciosos

| # | Arquivo | Problema | Correção |
|---|---------|----------|----------|
| 1 | `detectors/ml.py` | Features extraídas duas vezes (IsolationForest + DBSCAN) | Extrair uma vez, reutilizar |
| 2 | `detectors/features.py:296` | Função definida dentro de loop (recriada N vezes) | Mover para escopo do módulo |
| 3 | `detectors/features.py` | Cálculo de percentil O(N²) com loop manual | Substituir por `pandas.rolling.rank` |
| 4 | `detectors/engine.py` | `variacao_detector` e `divergencia_detector` ausentes do `mapa` | Registrar no dicionário |
| 5 | `detectors/statistical.py` | `lista.sort()` muta entrada (efeito colateral) | Usar `sorted()` |
| 6 | `detectors/ml.py` | Type hints com string entre aspas para sklearn (quebra mypy) | Usar `TYPE_CHECKING` guard |

**Critério de conclusão:** `veredas analyze` roda sem warning, `mypy src/` sem erros de tipo nos módulos detectors.

---

### A5 — Extrair `get_db()` duplicado e padronizar paginação
**Esforço:** 2 horas  
**Impacto:** elimina código duplicado em 5 arquivos de rotas

- Centralizar `get_db()` em `web/dependencies.py` (já existe, só não é usado)
- Padronizar parâmetro de paginação: `page` em todos os endpoints (hoje mistura `page` e `pagina`)

**Critério de conclusão:** grep por `def get_db` retorna apenas 1 resultado; grep por `pagina=` retorna 0 nos arquivos de rota.

---

## Fase B — High Impact
> Novas capacidades que entregam valor real ao usuário final. Esforço médio a alto.

### B1 — Escrever testes automatizados
**Esforço:** 3–5 dias  
**Prioridade:** mais alta da fase B — sem testes, qualquer refactor é andar no escuro

Cobertura mínima por módulo:

```
tests/
├── unit/
│   ├── detectors/     → regras determinísticas, z-score, STL, IsolationForest
│   ├── collectors/    → mock da API BCB, parsing de resposta, erros de rede
│   └── storage/       → CRUD de modelos, queries do repository
├── integration/
│   ├── test_pipeline.py   → collect → analyze → anomalias persistidas
│   └── test_web_routes.py → httpx TestClient em todas as 5 rotas
└── conftest.py            → banco SQLite in-memory, fixtures reutilizáveis
```

**Meta:** cobertura ≥ 70% em `detectors/` e `storage/`; CI verde.

**Critério de conclusão:** `pytest --cov=src/veredas` reporta ≥ 70% de cobertura; nenhum teste marcado como `xfail` desnecessariamente.

---

### B2 — Migrations Alembic
**Esforço:** meio dia  
**Bloqueia:** qualquer deploy em produção ou atualização segura de schema

- Gerar migration inicial a partir dos models ORM existentes
- Adicionar campo `risk_score` em `TaxaCDB` (referenciado no dashboard, ausente no modelo)
- Documentar: `alembic upgrade head` no fluxo de instalação

**Critério de conclusão:** `alembic upgrade head` em banco vazio cria schema completo; `alembic downgrade -1` reverte sem erro.

---

### B3 — Sistema de alertas completo
**Esforço:** 3–4 dias  
**Valor:** notificação proativa é o diferencial para o investidor pessoa física

Etapas:

1. **AlertManager** em `alerts/manager.py` — despacha para canais configurados com cooldown por instituição
2. **Integração com DetectionEngine** — ao persistir `Anomalia` de severidade ALTA ou CRÍTICA, dispara alerta
3. **Telegram** (`alerts/telegram.py`) — já existe em `future_work/`, integrar e testar
4. **Email SMTP** (`alerts/email.py`) — já existe em `future_work/`, integrar e testar
5. **CLI**: `veredas alerts test` — envia mensagem de teste para canal configurado

**Critério de conclusão:** com `.env` configurado, `veredas analyze` gera anomalia CRÍTICA e mensagem chega no Telegram/email em < 30s.

---

### B4 — Coletor IFData (saúde financeira das IFs)
**Esforço:** 4–5 dias  
**Valor:** cruzar taxa alta com Índice de Basileia baixo é o sinal mais poderoso do sistema

- Expandir `collectors/ifdata.py` para coletar: Índice de Basileia, Índice de Liquidez, Ativo Total, Patrimônio Líquido
- Adicionar modelo ORM `HealthDataIF` em `storage/models.py`
- Novo detector: `BASILEIA_BAIXO` — IF com taxa > referência e Basileia < threshold (ex: 11%)
- Novo detector: `LIQUIDEZ_CRITICA` — Liquidez abaixo do mínimo regulatório enquanto taxa sobe
- Dashboard: painel de saúde financeira por IF na página `instituicao.html`

**Critério de conclusão:** `veredas collect ifdata` popula `HealthDataIF`; `veredas analyze` detecta e persiste anomalias dos 2 novos tipos.

---

### B5 — Filtros HTMX e exportação no dashboard
**Esforço:** 2–3 dias  
**Valor:** usabilidade — sem filtros o dashboard é uma lista ilegível

- Filtros sem reload de página em `/taxas/`: indexador (CDI, IPCA, Prefixado), prazo, instituição
- Filtro de severidade em `/anomalias/`
- Botão **Exportar CSV** em `/taxas/` e `/anomalias/` (stream direto pelo FastAPI)
- Ordenação clicável nas tabelas (por taxa, por data, por risco)

**Critério de conclusão:** filtros funcionam com JS desabilitado (degradação graciosa via query string); export gera CSV válido com encoding UTF-8-BOM (compatível com Excel brasileiro).

---

### B6 — Configurar CI com GitHub Actions
**Esforço:** meio dia  
**Bloqueia:** qualquer contribuição externa com confiança

```yaml
# .github/workflows/ci.yml
on: [push, pull_request]
jobs:
  test:    # pytest + cobertura
  lint:    # ruff check + ruff format --check
  types:   # mypy src/
```

**Critério de conclusão:** badge CI verde no README; PR sem testes passando é bloqueado pelo status check.

---

## Fase C — Polishing
> Refinamento, distribuição e sustentabilidade do projeto a longo prazo.

### C1 — Headers de segurança faltantes
**Esforço:** 2 horas  
**Impacto:** fechar últimos LOW do SECURITY_REPORT

- Adicionar `Content-Security-Policy` no middleware FastAPI
- `X-Frame-Options: DENY`
- `X-Content-Type-Options: nosniff`
- `Referrer-Policy: strict-origin-when-cross-origin`

**Critério de conclusão:** `curl -I http://localhost:8000` mostra todos os 4 headers.

---

### C2 — Logging estruturado
**Esforço:** 1 dia  
**Impacto:** debugar problemas em produção sem `print()` espalhados

- Substituir todos os `print()` por `logging.getLogger(__name__)`
- Configurar formato JSON para produção, formato legível para desenvolvimento
- Nível configurável via `.env` (`LOG_LEVEL=INFO`)
- Log de auditoria para detecções (`INFO`) e erros de coleta (`WARNING`)

**Critério de conclusão:** grep por `print(` em `src/veredas/` retorna 0 resultados (exceto `cli/main.py` onde Rich é usado intencionalmente).

---

### C3 — Dark mode e UX final
**Esforço:** 1 dia  
**Impacto:** qualidade visual para uso prolongado e screenshots de divulgação

- Toggle dark/light mode com preferência salva em `localStorage`
- Notificações toast (HTMX `hx-swap="outerHTML"`) para ações confirmadas
- Favicon e `<meta>` Open Graph para compartilhamento
- Página 500 customizada (hoje só existe 404)

**Critério de conclusão:** Lighthouse score ≥ 90 em Performance e Accessibility na home.

---

### C4 — Empacotamento e distribuição
**Esforço:** 2–3 dias  
**Valor:** usuário instala com um comando, sem precisar de Python

- `veredas.spec` para PyInstaller — bundle único incluindo templates e static
- GitHub Actions release: `.exe` (Windows), binário Linux (Ubuntu)
- Tag de release com `CHANGELOG.md` atualizado automaticamente via `git cliff`
- `brew tap` (opcional, v2.0)

**Critério de conclusão:** `./veredas-de-papel.exe init && ./veredas-de-papel.exe collect bcb` funciona em Windows limpo sem Python instalado.

---

### C5 — Demo público
**Esforço:** 1 dia  
**Valor:** vitrine do projeto para novos colaboradores e investidores curiosos

- Deploy no Koyeb free tier (ou Railway) com dados históricos pré-populados
- Banco de dados somente-leitura no demo (sem `veredas init` exposto)
- Link no README com badge "Live Demo"
- Dados atualizados diariamente via cron job no próprio serviço

**Critério de conclusão:** URL pública acessível, dados com no máximo 24h de defasagem.

---

### C6 — Scrapers de corretoras (Fase 4 do README)
**Esforço:** 2–4 semanas (esforço alto, dependência externa)  
**Colocado em polishing:** HTML de corretoras muda frequentemente — só faz sentido após base estável

- Coletor XP Investimentos (tabela de CDBs disponíveis)
- Coletor BTG Pactual Digital
- Coletor Inter
- Infraestrutura anti-scraping: retry, backoff, rotação de User-Agent
- Detector `PRATELEIRA_VS_MERCADO`: taxa na corretora diverge do mercado primário

**Critério de conclusão:** `veredas collect corretoras` coleta sem erro por 7 dias consecutivos; tolerância a falha parcial (se BTG cai, XP continua).

---

## Visão Geral de Versões

| Versão | Conteúdo | Estimativa |
|--------|----------|------------|
| **v0.2.0** | Fases A completas — dashboard funcionando, código limpo | 1 semana |
| **v0.3.0** | B1 + B2 + B6 — testes, migrations, CI verde | 1–2 semanas |
| **v0.4.0** | B3 + B4 — alertas e IFData operacionais | 2 semanas |
| **v0.5.0** | B5 — dashboard com filtros e export | 1 semana |
| **v1.0.0** | Fase C completa — polishing, empacotamento, demo | 2–3 semanas |
| **v1.1.0** | C6 — scrapers de corretoras | a definir |

---

## Fora do Escopo (por ora)

- **API REST pública** (Fase 6 do README) — só após v1.0 estabilizar o schema
- **Dados B3 mercado secundário** — requer acesso pago ou parceria
- **ReclameAqui / Processos BACEN** — dados alternativos de alto valor, mas coleta frágil; aguardar base estável
- **App mobile** — fora do perfil FOSS/CLI deste projeto

---

*Atualizado em: abril 2026*
