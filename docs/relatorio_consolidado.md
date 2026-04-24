# Relatório Consolidado — Veredas de Papel

> Síntese de 7 análises independentes conduzidas por agentes especialistas (arquitetura, qualidade, QA/testes, segurança, performance, ML, backend).
> Data: 2026-04-24 | Versão: 0.1.0-alpha

---

## 1. Visão Geral

O projeto está bem estruturado para um alpha: separação clara de domínios, cobertura de testes funcional (46.5%), CI configurado e pronto para uso. Os problemas encontrados são reais mas nenhum é bloqueador de release alpha — são sinalizações de qualidade para as próximas iterações.

| Dimensão | Status | Nota |
|---|---|---|
| Arquitetura | Sólida | Separação de camadas limpa; acoplamento gerenciável |
| Qualidade de código | Boa | 71 issues ruff, maioria doc/type — nenhum erro lógico |
| QA & Testes | Adequada para alpha | 217 testes, 46.5% cobertura; fixtures incompletas |
| Segurança | Pós-fix: boa | CVEs corrigidos; CSRF/Rate limit implementados |
| Performance | Identificável | P01 (paralelismo scraper) corrigido; cache stampede documentado |
| ML | Funcional | IF+DBSCAN operacionais; treino/score no mesmo batch (deferred) |
| Backend | Funcional | check_same_thread e engine cache corrigidos; B-03 corrigido |

---

## 2. Tabela Mestre de Itens

| ID | Agente | Severidade | Título | Status |
|---|---|---|---|---|
| S-01 | Segurança | HIGH | `ignore_https_errors=True` no scraper | **CORRIGIDO** (commit c3e4f..) |
| S-02 | Segurança | HIGH | `logger.error(e)` expõe stack trace | **CORRIGIDO** |
| S-03 | Segurança | HIGH | CSP ausente nas respostas HTTP | **CORRIGIDO** |
| S-04 | Segurança | HIGH | `datetime.now()` sem timezone (35+ lugares) | **CORRIGIDO** |
| S-05 | Segurança | HIGH | CVE-2024-53498 python-multipart <0.0.13 | **CORRIGIDO** |
| Q-01 | Qualidade | HIGH | CI sem `--cov-fail-under` | **CORRIGIDO** (`--cov-fail-under=45`) |
| ML-02 | ML | HIGH | `contamination=0.05` hardcoded no IsolationForest | **CORRIGIDO** (`"auto"`) |
| P-01 | Performance | HIGH | Scrapers coletados em série (`asyncio.run` em loop) | **CORRIGIDO** (`asyncio.gather`) |
| B-01 | Backend | HIGH | `check_same_thread` ausente no SQLite | **CORRIGIDO** |
| B-02 | Backend | HIGH | `get_engine()` cria nova engine por chamada | **CORRIGIDO** (cache dict) |
| B-03 | Backend | HIGH | ORM instances detached no cache de taxas | **CORRIGIDO** (serializa para dict) |
| ML-01 | ML | HIGH | IsolationForest treina e pontua no mesmo batch | **DEFERIDO** (ver §5) |
| P-02 | Performance | MEDIUM | Cache stampede em `TTLCache` (não atômico) | Aberto |
| P-03 | Performance | MEDIUM | Query N+1 em `/api/taxas` sem eager loading | Aberto |
| A-01 | Arquitetura | MEDIUM | `DatabaseManager` acoplado ao path no construtor | Aberto |
| Q-02 | Qualidade | MEDIUM | 71 issues ruff (doc, type annotations faltando) | Aberto |
| QA-01 | QA | MEDIUM | Fixtures de teste incompletas (sem dados de ML) | Aberto |
| QA-02 | QA | MEDIUM | Sem testes de integração para rotas FastAPI | Aberto |
| B-04 | Backend | MEDIUM | `session_scope` não usa `contextmanager` decorator | Aberto |
| S-06 | Segurança | LOW | Headers `X-Content-Type-Options`, `X-Frame-Options` ausentes | Aberto |
| P-04 | Performance | LOW | `pool_size` não configurado (SQLite single-writer) | Aberto |

---

## 3. Detalhamento por Agente

### 3.1 Arquitetura (`relatorio_arquitetura.md`)

**Pontos fortes:**
- Separação nítida: `collectors → storage → detectors → web → cli`
- `DatabaseManager` encapsula bem o ciclo de vida da sessão
- Modelo de domínio rico (`TaxaCDB`, `Anomalia`, `TaxaReferencia` bem tipados)

**Preocupações:**
- A-01: `DatabaseManager` recebe path no construtor — dificulta injeção de dependência em testes e mock. Recomendação: aceitar `engine` diretamente como parâmetro alternativo
- A-02: `get_session()` como função standalone exportada cria dois caminhos de uso (função vs. `DatabaseManager`) — removida dos exports (fix B-02)
- A-03: Módulo `collectors/scrapers/` cresce sem registry formal — o dict `SCRAPERS` no `__init__.py` é suficiente por ora

### 3.2 Qualidade de Código (`relatorio_qualidade_codigo.md`)

**Pontos fortes:**
- Uso consistente de `dataclasses`, `Protocol`, `TYPE_CHECKING`
- Nenhum bug lógico identificado nas análises estáticas
- Estrutura de erros retornados (`CollectionResult`) consistente

**Preocupações:**
- Q-01: CI não impunha cobertura mínima — **corrigido** com `--cov-fail-under=45`
- Q-02: 71 avisos ruff restantes (docstrings ausentes, type annotations incompletas nos parâmetros de retorno, `ANN` rules). Nenhum é lógico, mas prejudica legibilidade
- Q-03: Alguns módulos usam `Any` amplamente onde tipos mais específicos seriam possíveis (`raw_data: dict[str, Any]` poderia ser `TypedDict`)

### 3.3 QA & Testes (`relatorio_qa_testes.md`)

**Estado atual:**
- 217 testes passando, 1 skipped
- Cobertura: 46.53% total (acima do threshold de 45%)
- Camadas bem testadas: `detectors/rules`, `storage/repository`, `validators`

**Lacunas identificadas:**
- QA-01: Sem fixtures com dados suficientes para os detectores ML (mínimo 30 amostras para IsolationForest, 20 para DBSCAN) — os detectores passam nos testes por retornar resultado vazio
- QA-02: Rotas FastAPI (`/api/taxas`, `/api/anomalias`, `/api/instituicoes`) sem testes de integração com `TestClient`
- QA-03: `collectors/` com 0% de cobertura — scrapers Playwright não têm mocks; fixture de resposta HTML seria suficiente para cobrir parsing

### 3.4 Segurança (`relatorio_seguranca.md`)

**Corrigidos antes deste relatório:**
- S-01: `ignore_https_errors=True` removido do `scraper_client.py`
- S-02: `logger.error(e)` substituído por `logger.exception(...)` em todos os detectores
- S-03: `Content-Security-Policy` adicionado em `web/app.py`
- S-04: `datetime.now()` sem TZ corrigido (35 ocorrências → `datetime.now(TZ_BRASIL)` ou `time.perf_counter()`)
- S-05: CVE-2024-53498 corrigido via `python-multipart>=0.0.13`

**Aberto:**
- S-06: Headers de segurança adicionais ausentes (`X-Content-Type-Options: nosniff`, `X-Frame-Options: DENY`, `Referrer-Policy: strict-origin-when-cross-origin`)

### 3.5 Performance (`relatorio_performance.md`)

**Corrigidos:**
- P-01: Scrapers rodavam serialmente (~180s total). Substituído por `asyncio.gather` — execução paralela esperada em ~50s

**Abertos:**
- P-02 (MEDIUM): `TTLCache.get → None → compute → set` não é atômico. Sob concorrência assíncrona, dois requests simultâneos com cache expirado computam o valor duas vezes. Solução: in-flight lock com `asyncio.Lock()` por chave
- P-03 (MEDIUM): Endpoint `/api/taxas` emite query N+1 ao acessar `taxa.instituicao` em loop. Corrigir com `joinedload(TaxaCDB.instituicao)` no `TaxaCDBRepository.list()`
- P-04 (LOW): `pool_size` não configurado — SQLite é single-writer, mas `pool_pre_ping=True` já adicionado (B-01); sem impacto crítico

### 3.6 Machine Learning (`relatorio_ml.md`)

**Corrigidos:**
- ML-02: `contamination=0.05` hardcoded forçava exatamente 5% de anomalias independente da distribuição real. Corrigido para `contamination="auto"` (IsolationForest usa a média dos scores como threshold)

**Deferido:**
- ML-01 (ver §5): IsolationForest treina e pontua no mesmo batch — aprende a densidade do regime atual em vez de uma baseline histórica. Correção exige CLI `veredas baseline build`, serialização via joblib e caminho separado de inferência. Trabalho estimado: 2-3 dias. Não bloqueia alpha.

**Notas adicionais do agente ML:**
- DBSCAN com `eps=0.5` fixo pode criar zero clusters se os dados estiverem normalizados de forma diferente a cada chamada — considerar busca automática de `eps` via k-distance plot
- Sem persistência de modelo entre coletas: cada `detect()` treina do zero. Acceptable para alpha, problemático para produção

### 3.7 Backend (`relatorio_backend.md`)

**Corrigidos:**
- B-01: `check_same_thread=False` adicionado ao `create_engine()` — evita `ProgrammingError` quando o thread pool do Starlette acessa a sessão SQLite
- B-02: `get_engine()` agora usa cache por path (`_engine_cache` dict) — uma única engine por banco, não uma por chamada
- B-03: `get_cached_reference_rates()` serializava instâncias ORM detached — agora converte para `dict` antes de armazenar no cache

**Abertos:**
- B-04 (MEDIUM): `session_scope()` em `DatabaseManager` não usa `@contextlib.contextmanager` — funciona porque SQLAlchemy aceita o protocolo, mas é frágil; adicionar decorator explícito
- B-05 (LOW): `get_session()` standalone (função módulo) mantida em `database.py` mas removida dos exports públicos. Pode ser deletada completamente em próxima limpeza

---

## 4. Roadmap Sugerido

### v0.1.x (curto prazo — próximas 2 semanas)

| Prioridade | Item | Esforço |
|---|---|---|
| 1 | P-02: Cache stampede com `asyncio.Lock` | 30min |
| 2 | P-03: N+1 em `/api/taxas` com `joinedload` | 1h |
| 3 | S-06: Headers de segurança faltantes | 15min |
| 4 | QA-02: Testes de integração FastAPI (`TestClient`) | 4h |
| 5 | B-04: `@contextmanager` em `session_scope` | 15min |

### v0.2.0 (médio prazo — 1 mês)

| Prioridade | Item | Esforço |
|---|---|---|
| 1 | ML-01: Baseline histórica + `veredas baseline build` | 2-3 dias |
| 2 | QA-01: Fixtures ML com 30+ amostras realistas | 4h |
| 3 | QA-03: Mocks HTML para scrapers Playwright | 1 dia |
| 4 | Q-02: Resolver 71 avisos ruff restantes | 2h |
| 5 | A-01: `DatabaseManager` aceitar `engine` diretamente | 1h |

---

## 5. ML-01 — Problema Deferido (Detalhamento)

**Diagnóstico:** `IsolationForestDetector.detect_with_features()` chama `fit()` e `predict()` no mesmo array `X_scaled`. O modelo aprende a densidade da distribuição atual e marca ~`contamination` % dos pontos como anomalias dentro daquela janela. Se o mercado inteiro se mover (e.g., ciclo de alta da Selic), não há linha de base para comparar — o modelo normaliza tudo.

**Solução arquitetural:**
1. Novo comando CLI: `veredas baseline build [--desde YYYY-MM-DD]`
   - Busca taxas históricas do banco
   - Treina `IsolationForest` + `StandardScaler` na baseline
   - Serializa com `joblib.dump()` em `~/.veredas/models/if_baseline.joblib`
2. `IsolationForestDetector.detect_with_features()`:
   - Tenta carregar modelo salvo
   - Se existe: `scaler.transform(X)` + `model.predict(X)` (sem `fit`)
   - Se não existe: comportamento atual (warn + train-on-batch)
3. Renovação periódica: `veredas baseline build` em cron semanal ou trigger manual

**Por que deferido:** requer novo módulo de persistência de modelos, CLI adicional, e decisão sobre frequência de retreinamento (não trivial). Não bloqueia detecção funcional no alpha — apenas produz resultados menos estáveis em janelas curtas.

---

## 6. Métricas de Saúde do Projeto

| Métrica | Valor | Meta |
|---|---|---|
| Testes passando | 217 / 218 (1 skip) | 217+ |
| Cobertura de testes | 46.53% | ≥45% (threshold) |
| Issues ruff (linting) | ~71 restantes | 0 |
| CVEs conhecidos | 0 | 0 |
| HIGH items abertos | 1 (ML-01, deferido) | 0 |
| MEDIUM items abertos | 6 | <3 |

---

*Relatório gerado com base nas análises dos agentes: architecture, analyst, tester, security-manager, performance-optimizer, ml-developer, backend-dev.*
