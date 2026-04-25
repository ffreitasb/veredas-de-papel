# Relatório de Performance — veredas-de-papel

**Data:** 2026-04-24
**Escopo:** Análise exclusiva de performance (não cobre qualidade, QA, segurança ou arquitetura)
**Versão analisada:** branch `master` — commit `347e5ba`

---

## Sumário Executivo

O projeto está em estado alpha com volume de dados ainda pequeno (dezenas a centenas de IFs, coletas diárias). Nesse perfil, a maioria dos problemas listados é latente — não dói hoje, mas criará regressões mensuráveis quando o banco acumular meses de histórico ou quando o número de IFs monitoradas crescer.

Os dois achados de impacto imediato real são:

1. **`get_desvio_padrao` sem `numpy`** — calcula desvio padrão em Python puro com loop explícito quando `numpy` já está no ambiente e poderia reduzir tempo de CPU em ~10x para séries longas. Baixo custo de correção, moderado de impacto.
2. **`asyncio.run()` em loop síncrono por coletor** — cada corretora abre e fecha um event loop completo, impedindo paralelismo real entre coletores. Com 4 corretoras levando ~45 s cada (Playwright), a coleta total demora ~180 s quando poderia levar ~45 s.

Os demais achados são válidos mas seu impacto só será sentido com crescimento de dados.

---

## Tabela de Achados

| ID | Área | Arquivo:Linha | Descrição | Severidade | Impacto Estimado |
|----|------|---------------|-----------|------------|-----------------|
| P01 | Collectors | `cli/_collect.py:146` | `asyncio.run()` por coletor em loop síncrono — sem paralelismo entre corretoras | HIGH | +135 s/coleta completa com 4 scrapers |
| P02 | SQL/Repository | `storage/repository.py:192` | `get_desvio_padrao`: loop Python puro em vez de `numpy` — O(N) com constante alta | MEDIUM | ~5–10x mais lento em séries longas |
| P03 | SQL/Repository | `storage/repository.py:252–294` | `list_paginated` emite dois `SELECT` independentes (dados + contagem) por request de página | MEDIUM | 2× round-trips em cada listagem paginada |
| P04 | Web/Routes | `web/routes/home.py:49–54` | 4 queries separadas para contagens de severidade (critical/high/medium/low/total) | MEDIUM | 5 queries onde 1 com `GROUP BY` resolve |
| P05 | Web/Routes | `web/routes/home.py:77–89` | Partial HTMX `/partials/stats` repete exatamente as mesmas 5 queries, sem cache | MEDIUM | Duplicação a cada polling HTMX |
| P06 | Cache | `web/cache.py:16–45` | `TTLCache` não é thread-safe — race condition `get → miss → compute → set` possível com workers assíncronos concorrentes | MEDIUM | Cache stampede teórico sob carga |
| P07 | Detectors/Engine | `detectors/engine.py:331` | `calculate_market_stats` chamado duas vezes para o mesmo `all_taxas` (linha 211 e 331) | MEDIUM | Cálculo duplicado de média/desvio sobre todo o histórico |
| P08 | Detectors/Features | `detectors/features.py:291–366` | Loop Python por ponto dentro de `_extract_if_features`: acesso à Series pandas por índice datetime via `_safe_get` → O(N) lookups potencialmente lentos | MEDIUM | Overhead de N lookups de index para cada IF |
| P09 | Detectors/ML | `detectors/ml.py:180–193` | `IsolationForest` re-treina modelo em cada chamada — nenhum cache de modelo entre execuções do mesmo dia | MEDIUM | Re-treinamento desnecessário quando dados não mudaram |
| P10 | SQL/Models | `storage/models.py:218–235` | `Anomalia.taxa_id` sem índice explícito (FK sem `index=True`) | LOW | Full scan ao fazer JOIN `anomalias ↔ taxas_cdb` |
| P11 | SQL/Repository | `storage/repository.py:297–303` | `get_by_instituicao` é alias de `list_by_if` com `limit=100` hardcoded — sem controle externo | LOW | Truncagem silenciosa para IFs com histórico longo |
| P12 | Web/Routes | `web/routes/taxas.py:145–163` | CSV export: `StringIO` recriado por linha dentro do generator — alocação desnecessária em loop | LOW | Pressão de GC em exports grandes |
| P13 | Collectors | `collectors/scraper_client.py:100–112` | `new_context()` por `fetch()` — cria contexto Playwright isolado por URL; para múltiplas páginas seria melhor reusar contexto | LOW | Overhead de inicialização de contexto por scrape |
| P14 | Detectors/Statistical | `detectors/statistical.py:61–90` | `_prepare_time_series` filtra com list comprehension O(N) para cada IF; com muitas IFs no mesmo batch, o mesmo `taxas` é percorrido K vezes | LOW | O(N×K) onde N=taxas totais, K=número de IFs |
| P15 | Web/Routes | `web/routes/timeline.py:46–65` | Timeline combina eventos e anomalias em memória Python e depois pagina — traz `5×por_pagina` de cada fonte antes de cortar | LOW | Memória proporcional a `10 × por_pagina` itens |

---

## Análise Detalhada por Área

### 1. Pipeline de Detecção (`src/veredas/detectors/`)

#### P07 — `calculate_market_stats` chamado duas vezes (MEDIUM)

**Arquivo:** `detectors/engine.py`, linhas 211 e 331

```python
# Linha 211: chamada para taxas_atuais
market_mean, market_std = calculate_market_stats(taxas_atuais)

# Linha 331: chamada para all_taxas (taxas_anteriores + taxas_atuais)
ml_market_mean, ml_market_std = calculate_market_stats(all_taxas)
```

As duas chamadas são semanticamente distintas (uma sobre `taxas_atuais`, outra sobre `all_taxas`), mas a função `calculate_market_stats` é O(N) com construção de lista Python + duas chamadas `np.mean`/`np.std`. Com histórico longo (ex: 6 meses × 50 IFs = ~10.000 registros), a segunda chamada percorre 10.000 floats desnecessariamente se o chamador já calculou os stats para `all_taxas` antes.

**Impacto:** baixo em volume atual, escala linearmente com histórico.

**Sugestão:** calcular uma vez para `all_taxas` e derivar os stats de `taxas_atuais` a partir de um slice, ou memoizar por hash do conjunto de IDs.

---

#### P08 — Loop Python com `_safe_get` em `_extract_if_features` (MEDIUM)

**Arquivo:** `detectors/features.py`, linhas 291–366

```python
for i, taxa in enumerate(taxas):
    date = taxa.data_coleta
    rolling_mean_7d = _safe_get(rolling_stats.get("mean_7d", pd.Series()), date)
    rolling_std_7d  = _safe_get(rolling_stats.get("std_7d",  pd.Series()), date)
    # ... 6 _safe_get calls por ponto
    d1  = _safe_get(diff_1d, date)
    d7  = _safe_get(diff_7d, date)
    # ...
```

A função `_safe_get` faz `s.get(idx)` em cada iteração — para `pd.Series` indexada por `DatetimeIndex`, isso é O(log N) no melhor caso (pesquisa por índice) mas, na prática, pandas lança warnings e cai em busca linear se o índice não for único ou tiver `datetime` com timezone misto. O padrão idiomático pandas seria `.loc[idx]` vetorizado, ou — melhor — reconstruir o DataFrame com `pd.concat` das séries e retornar linhas diretamente.

Há também 6 chamadas `rolling_stats.get(key, pd.Series())` por iteração, criando instâncias vazias de `pd.Series()` no caso de miss — uma alocação desnecessária.

**Sugestão:** substituir o loop por `pd.concat` dos vetores pré-calculados em um `DataFrame` e então retornar `.itertuples()` ou converter diretamente para `np.ndarray` com `to_numpy()`:

```python
df = pd.DataFrame({
    "percentual": series.values,
    "rolling_mean_7d": rolling_stats.get("mean_7d", pd.Series(dtype=float)).values,
    # ...
}, index=series.index)
```

---

#### P09 — `IsolationForest` re-treina a cada chamada (MEDIUM)

**Arquivo:** `detectors/ml.py`, linhas 180–193

```python
self._scaler = StandardScaler()
X_scaled = self._scaler.fit_transform(X)

self._model = IsolationForest(
    contamination=self.thresholds.if_contamination,
    n_estimators=self.thresholds.if_n_estimators,
    random_state=self.thresholds.if_random_state,
)
self._model.fit(X_scaled)
```

O modelo é instanciado e treinado toda vez que `detect_with_features` é chamado. Com `n_estimators=100` e séries de 200–500 pontos, o treino leva tipicamente 50–200 ms. Se o pipeline rodar múltiplas vezes por dia (ex: via scheduler a cada hora), esse custo acumula sem necessidade quando o histórico não mudou.

O `DBSCAN` não tem esse problema (não há treino persistível), mas aplica `fit_predict` que igualmente não é cacheado.

**Sugestão:** cachear modelo por hash dos IDs das taxas (ou data da última coleta). Se o hash não mudou, reusar `self._model` e `self._scaler` sem re-treino. Um TTL de 1 hora seria suficiente para o scheduler atual.

---

#### P14 — `_prepare_time_series` itera sobre lista global por IF (LOW)

**Arquivo:** `detectors/statistical.py`, linhas 61–73

```python
def _prepare_time_series(taxas, if_id):
    if_taxas = [t for t in taxas if t.if_id == if_id]  # O(N) por IF
```

Os três detectores estatísticos chamam `_group_by_if(taxas)` e depois `_prepare_time_series(if_taxas, if_id)`. O agrupamento com `defaultdict` é correto e O(N). O problema é que `_prepare_time_series` recebe `if_taxas` já filtrado mas ainda recebe `if_id` e refaz o filtro (`[t for t in taxas if t.if_id == if_id]`). Na assinatura atual, `taxas` é o parâmetro que deveria ser `if_taxas` — o filtro é redundante, mas inofensivo. No entanto, se chamado diretamente com a lista global (caminho externo), seria O(N×K).

**Sugestão:** renomear parâmetro para `if_taxas` e remover o filtro interno, confiando que o chamador já filtrou.

---

### 2. Queries SQL (`src/veredas/storage/repository.py`)

#### P02 — `get_desvio_padrao` com loop Python puro (MEDIUM)

**Arquivo:** `storage/repository.py`, linhas 192–219

```python
# Buscar todos os valores
stmt = select(TaxaCDB.percentual).where(...)
result = self.session.execute(stmt).scalars().all()

valores = [float(v) for v in result]
n = len(valores)
media = sum(valores) / n
soma_quadrados = sum((x - media) ** 2 for x in valores)  # loop puro
variancia = soma_quadrados / n
desvio = variancia**0.5
```

O comentário no código justifica: "SQLite não tem STDDEV nativo". Correto, mas `numpy` já é dependência do projeto. A solução com `np.std(valores)` seria ~10× mais rápida para séries longas e mais legível. Para 1.000 valores (30 dias × ~33 IFs CDI), a diferença é ~0.5 ms vs ~0.05 ms — marginal hoje, mas o padrão é ruim para manutenção.

**Sugestão:**

```python
import numpy as np
valores = np.array([float(v) for v in result], dtype=np.float64)
return Decimal(str(round(float(np.std(valores)), 6)))
```

---

#### P03 — Dois `SELECT` independentes em `list_paginated` (MEDIUM)

**Arquivo:** `storage/repository.py`, linhas 252–295

```python
stmt       = select(TaxaCDB)
count_stmt = select(func.count(TaxaCDB.id))

# Filtros aplicados separadamente em stmt e count_stmt (código duplicado)
if "indexador" in filters:
    stmt = stmt.where(TaxaCDB.indexador == filters["indexador"])
    count_stmt = count_stmt.where(TaxaCDB.indexador == filters["indexador"])
# ...

taxas = self.session.execute(stmt).scalars().all()
total = self.session.execute(count_stmt).scalar() or 0
```

Dois problemas: (a) os filtros são aplicados duas vezes manualmente — se um filtro for adicionado em `stmt` mas esquecido em `count_stmt`, a paginação fica errada silenciosamente; (b) são dois round-trips ao banco.

SQLite suporta `SELECT COUNT(*) OVER ()` como window function, permitindo obter contagem e dados em um único `SELECT`. Alternativamente, pode-se derivar `count_stmt` a partir de `stmt` antes de aplicar `LIMIT/OFFSET`:

```python
count_stmt = select(func.count()).select_from(stmt.subquery())
```

Isso garante que filtros só precisam ser aplicados uma vez.

---

#### P04 / P05 — 5 queries para contagens de anomalias em `home.py` (MEDIUM)

**Arquivo:** `web/routes/home.py`, linhas 49–54 e 77–89

```python
anomalias_count = {
    "critical": anomalia_repo.count_by_severity(Severidade.CRITICAL),  # SELECT COUNT
    "high":     anomalia_repo.count_by_severity(Severidade.HIGH),       # SELECT COUNT
    "medium":   anomalia_repo.count_by_severity(Severidade.MEDIUM),     # SELECT COUNT
    "low":      anomalia_repo.count_by_severity(Severidade.LOW),        # SELECT COUNT
    "total":    anomalia_repo.count_active(),                           # SELECT COUNT
}
```

5 queries individuais onde uma única com `GROUP BY` resolveria. O padrão se repete identicamente no endpoint `/partials/stats` (linha 83), que é chamado a cada polling HTMX do dashboard.

A função `get_cached_anomaly_counts` em `web/cache.py` existe para isso, mas **não é usada** no handler `home()` — só `get_cached_reference_rates` é aplicado.

**Sugestão — duas ações:**

1. Adicionar ao `AnomaliaRepository`:

```python
def count_all_severities(self) -> dict[Severidade, int]:
    stmt = (
        select(Anomalia.severidade, func.count(Anomalia.id))
        .where(Anomalia.resolvido == False)
        .group_by(Anomalia.severidade)
    )
    rows = self.session.execute(stmt).all()
    return {sev: cnt for sev, cnt in rows}
```

2. Usar `get_cached_anomaly_counts` com essa nova função no handler `home()` e no partial `stats_partial`.

---

#### P10 — `Anomalia.taxa_id` sem índice (LOW)

**Arquivo:** `storage/models.py`, linha 219

```python
taxa_id: Mapped[int | None] = mapped_column(ForeignKey("taxas_cdb.id"))
```

`if_id` tem `index=True`, mas `taxa_id` não. Se algum relatório ou query futura for "quais anomalias foram geradas por esta taxa?", haverá full scan em `anomalias`. Já `InstituicaoFinanceira.id` referenciado por `Anomalia.if_id` tem índice.

**Sugestão:** `mapped_column(ForeignKey("taxas_cdb.id"), index=True)`.

---

### 3. Cache (`src/veredas/web/cache.py`)

#### P06 — `TTLCache` sem thread-safety (MEDIUM)

**Arquivo:** `web/cache.py`, linhas 16–45

```python
class TTLCache:
    def __init__(self, ...):
        self._cache: dict[str, Any] = {}
        self._timestamps: dict[str, datetime] = {}

    def get(self, key):
        if key not in self._cache:
            return None
        # ... verifica expiração, deleta se expirado
        return self._cache[key]

    def set(self, key, value):
        self._cache[key] = value
        self._timestamps[key] = datetime.now(TZ_BRASIL)
```

Em FastAPI com múltiplos workers `asyncio` (ou com Uvicorn multi-worker), o padrão `get → None → compute → set` não é protegido por lock. Dois coroutines concorrentes podem ambos receber `None` do `get`, ambos computar o valor (2× round-trips ao DB e 2× processamento), e ambos escrever no cache. Isso é um **cache stampede** clássico.

Para o contexto atual (single-process Uvicorn), o GIL do CPython protege a maioria das operações de `dict`, mas o intervalo entre `get` e `set` não é atômico — e com `asyncio`, o `await` dentro de `count_func(session)` pode ceder controle e permitir outra coroutine entrar no mesmo path.

Adicionalmente, a função `get_cached_anomaly_counts` existe mas **não é usada** nos handlers que deveriam consumi-la (`home.py`).

**Sugestão:**

```python
import asyncio

class TTLCache:
    def __init__(self, ...):
        self._cache: dict[str, Any] = {}
        self._timestamps: dict[str, datetime] = {}
        self._lock = asyncio.Lock()

    async def get_or_set(self, key: str, compute_fn) -> Any:
        """Atomic get-or-compute com lock."""
        cached = self.get(key)
        if cached is not None:
            return cached
        async with self._lock:
            # Double-check após adquirir lock
            cached = self.get(key)
            if cached is not None:
                return cached
            value = await compute_fn()
            self.set(key, value)
            return value
```

---

### 4. Collectors Assíncronos (`src/veredas/collectors/`)

#### P01 — `asyncio.run()` por coletor em loop síncrono (HIGH)

**Arquivo:** `cli/_collect.py`, linhas 143–149

```python
for f in fontes_alvo:                          # loop síncrono
    col = get_collector(f)
    with console.status(...):
        result = asyncio.run(_run(col))        # abre e fecha event loop por coletor
```

Cada `asyncio.run()` cria um event loop novo, executa a coroutine até completar e destrói o loop. Isso é **serialização forçada** de todas as coletas. O `PlaywrightClient` leva até 45 s por corretora (timeout configurado). Com 4 corretoras (btg, xp, rico, inter), o tempo total é ~180 s em série.

A solução é coletar todas as corretoras em paralelo com `asyncio.gather`:

```python
async def _collect_all(fontes: list[str]) -> list[CollectionResult]:
    async def _run_one(fonte: str):
        col = get_collector(fonte)
        async with col:
            return fonte, await col.collect()

    return await asyncio.gather(*[_run_one(f) for f in fontes], return_exceptions=True)

results = asyncio.run(_collect_all(fontes_alvo))
```

**Impacto real:** redução de ~180 s para ~45–60 s (tempo do coletor mais lento + overhead de orquestração).

**Nota:** Playwright abre um processo Chromium por instância de `PlaywrightClient`. Paralelizar 4 instâncias cria 4 processos Chromium simultâneos (~800 MB RAM total). Aceitável em desktop, mas documentar o requisito de memória é necessário.

---

#### P13 — Novo `BrowserContext` por chamada `fetch()` (LOW)

**Arquivo:** `collectors/scraper_client.py`, linhas 100–112

```python
async def fetch(self, url, ...):
    context = await self._browser.new_context(**context_kwargs)
    page = await context.new_page()
    try:
        await page.goto(url, ...)
        return await page.content()
    finally:
        await page.close()
        await context.close()
```

Para um scraper que faz uma única `fetch()` por `collect()` (como BTG, XP), isso é aceitável. Para futuros coletores que precisarem percorrer múltiplas páginas (ex: paginação da prateleira), criar um contexto por URL é overhead desnecessário. O contexto Playwright carrega cookies/cache isolados — para scraping sem estado, um único contexto por `collect()` seria suficiente.

**Sugestão:** Expor método `fetch_many(urls)` que reutiliza o mesmo contexto para múltiplas páginas dentro de uma coleta.

---

### 5. Web Routes (`src/veredas/web/routes/`)

#### P05 — `/partials/stats` sem cache (MEDIUM)

**Arquivo:** `web/routes/home.py`, linhas 77–89

O endpoint `/partials/stats` é projetado para polling HTMX (atualização periódica do dashboard). Ele executa as mesmas 5 queries de contagem sem nenhum cache. Se o intervalo de polling for 30 s, são 10 queries/minuto × 5 = 50 queries/minuto apenas para contadores do dashboard. Para um único usuário isso é inofensivo; com uso real, o overhead de SQLite é negligível — mas o padrão é inconsistente com a infraestrutura de cache já existente.

**Sugestão:** usar `get_cached_anomaly_counts` com TTL de 5 minutos para ambos os handlers.

---

#### P12 — `StringIO` recriado por linha no CSV export (LOW)

**Arquivo:** `web/routes/taxas.py`, linhas 124–163; `web/routes/anomalias.py`, linhas 142–183

```python
def _gerar_csv():
    buf = io.StringIO()  # buffer inicial para header
    # ...
    yield buf.getvalue()

    for taxa in taxas:
        buf = io.StringIO()        # recriado para cada linha
        writer = csv.writer(buf, delimiter=";")
        writer.writerow([...])
        yield buf.getvalue()
```

Para 10.000 linhas (limite do export), isso cria 10.001 objetos `StringIO` e `csv.writer`. O overhead é ~1–2 μs por objeto no CPython, totalizando ~20 ms — perceptível mas não crítico. O padrão também quebra o benefício do `StreamingResponse` (dados fluem linha a linha, o que é correto), mas cada "chunk" é uma única linha em vez de um batch.

**Sugestão:** usar um único `StringIO` com `truncate(0); seek(0)` entre linhas, ou acumular N linhas por chunk:

```python
def _gerar_csv():
    buf = io.StringIO()
    buf.write("﻿")
    writer = csv.writer(buf, delimiter=";")
    writer.writerow([...])  # header
    for i, taxa in enumerate(taxas):
        writer.writerow([...])
        if i % 100 == 99:          # flush a cada 100 linhas
            yield buf.getvalue()
            buf.seek(0); buf.truncate(0)
    yield buf.getvalue()
```

---

#### P15 — Timeline com paginação em memória (LOW)

**Arquivo:** `web/routes/timeline.py`, linhas 46–65

```python
max_items = por_pagina * 5
eventos = evento_repo.list_with_filters(limit=max_items, ...)
anomalias_criticas = anomalia_repo.list_with_filters(limit=max_items, ...)
all_items = _build_timeline(eventos, anomalias_criticas)
# ... ordena em Python e pagina com slice
```

A timeline combina duas fontes heterogêneas que precisam ser ordenadas por data. A solução atual traz `10 × por_pagina` itens de cada fonte, mescla em memória e corta. Isso é adequado enquanto o banco tiver poucos eventos históricos (o dataset de seeds tem ~20 eventos). Se eventos crescerem para centenas, o padrão degrada.

Não há solução simples em SQL puro para `UNION` ordenado com paginação entre tabelas com esquemas diferentes. A abordagem mais escalável seria paginar apenas a primeira fonte para cada página e misturar no cursor de aplicação, mas isso aumenta a complexidade. Para o volume atual, o padrão é aceitável.

---

## Database: Índices e Configuração SQLite

**Arquivo:** `storage/database.py`

O engine é criado sem opções de performance para SQLite:

```python
return create_engine(db_url, echo=False)
```

Para SQLite com cargas de leitura concorrente (múltiplos workers Uvicorn), as seguintes configurações são relevantes:

```python
from sqlalchemy import event

engine = create_engine(
    db_url,
    echo=False,
    connect_args={
        "check_same_thread": False,
        "timeout": 30,
    },
)

@event.listens_for(engine, "connect")
def set_sqlite_pragma(dbapi_conn, connection_record):
    cursor = dbapi_conn.cursor()
    cursor.execute("PRAGMA journal_mode=WAL")    # permite leituras concorrentes
    cursor.execute("PRAGMA synchronous=NORMAL")  # mais rápido, seguro suficiente
    cursor.execute("PRAGMA cache_size=-64000")   # 64 MB de cache
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()
```

O modo WAL é especialmente importante se o FastAPI rodar com múltiplos workers (`uvicorn --workers N`), pois o modo padrão (DELETE journal) serializa escritas e leituras.

**Índices faltantes identificados:**

| Tabela | Coluna | Justificativa |
|--------|--------|---------------|
| `anomalias` | `taxa_id` | FK sem `index=True` — JOIN com `taxas_cdb` fará full scan |
| `taxas_cdb` | `(if_id, data_coleta)` | Índice composto para `list_by_if` com filtro de data — atualmente há índice só em `if_id` e índice separado em `data_coleta`, mas não composto |
| `taxas_referencia` | `(tipo, data)` | Índice composto para `get_ultima(tipo)` — atualmente só `data` tem índice |

---

## Recomendações Priorizadas

### Prioridade 1 — Impacto imediato, baixo custo

**R1 (P01):** Paralelizar coleta de scrapers com `asyncio.gather` em `cli/_collect.py`.
- Arquivo: `src/veredas/cli/_collect.py`, função `collect_scrapers`
- Esforço: ~30 linhas de refatoração
- Ganho: coleta de 4 corretoras de ~180 s para ~50 s

**R2 (P04/P05):** Substituir 5 queries individuais por 1 `GROUP BY` + usar cache existente.
- Arquivos: `src/veredas/storage/repository.py` (novo método `count_all_severities`), `src/veredas/web/routes/home.py`
- Esforço: ~20 linhas
- Ganho: 5→1 query no hot path do dashboard

### Prioridade 2 — Prevenção de regressão com crescimento de dados

**R3 (P03):** Derivar `count_stmt` de `stmt` via subquery em `list_paginated`.
- Arquivo: `src/veredas/storage/repository.py`
- Esforço: ~15 linhas; elimina duplicação de filtros e garante contagem correta
- Ganho: eliminação de bug latente + 1 round-trip a menos

**R4 (P02):** Substituir loop Python em `get_desvio_padrao` por `np.std`.
- Arquivo: `src/veredas/storage/repository.py`, linhas 205–218
- Esforço: 5 linhas
- Ganho: ~10× para séries longas

**R5 (P06):** Adicionar lock async em `TTLCache.get_or_set`.
- Arquivo: `src/veredas/web/cache.py`
- Esforço: ~20 linhas
- Ganho: elimina cache stampede; **também ativar o cache no handler `home()`** — que atualmente ignora `get_cached_anomaly_counts`

**R6 (P09):** Cachear modelo `IsolationForest` entre execuções com mesmos dados.
- Arquivo: `src/veredas/detectors/ml.py`
- Esforço: ~20 linhas (hash dos IDs + TTL)
- Ganho: elimina re-treino desnecessário a cada ciclo do scheduler

### Prioridade 3 — Melhorias incrementais

**R7 (P10):** Adicionar `index=True` em `Anomalia.taxa_id` + criar migração Alembic.

**R8 (P08):** Refatorar `_extract_if_features` para usar `pd.DataFrame` vetorizado em vez de loop com `_safe_get`.

**R9 (database):** Configurar SQLite com `PRAGMA journal_mode=WAL` no startup da aplicação + adicionar índice composto `(if_id, data_coleta)` em `taxas_cdb`.

**R10 (P12):** Refatorar CSV export para reutilizar `StringIO` com batch de 100 linhas.

---

## Observações sobre Pontos Positivos

As análises revelaram vários padrões de performance já corretos no código que merecem registro:

- **PERF-006 (engine.py:330–343):** features ML extraídas uma única vez e compartilhadas entre `IsolationForest` e `DBSCAN` — evita dupla extração, que seria o custo dominante.
- **PERF-007 (engine.py:35):** `SEVERITY_ORDER` como constante de módulo evita recriação em cada `_consolidate_anomalias`.
- **Eager loading em anomalias:** `list_with_filters(eager_load=True)` usa `selectinload` corretamente nas rotas de listagem de anomalias e timeline, evitando N+1 nos templates que acessam `anomalia.instituicao.nome`.
- **Paginação server-side:** todas as listagens usam `LIMIT/OFFSET` em SQL — não há carregamento de tabela inteira em memória.
- **`rolling_percentile` pré-computado:** `features.py:287` calcula percentil 30d via `rolling().rank()` vetorizado em vez de O(N²) loop — decisão correta.
- **`asyncio.Lock` no `WebCollectorBase._get`:** o rate limiter usa `async with self._lock` corretamente, evitando flood paralelo dentro de um mesmo coletor.
