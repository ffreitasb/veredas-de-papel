# Relatório de Engenharia Backend — veredas-de-papel

**Data:** 2026-04-24
**Escopo:** Padrões de engenharia backend (FastAPI, SQLAlchemy, Alembic, coletores assíncronos, configuração, modelos de dados)
**Versão analisada:** branch `master` — commit `347e5ba`

---

## Sumário Executivo

O projeto demonstra maturidade acima da média para um monorepo em estágio alpha. Os padrões FastAPI modernos (`lifespan`, factory function, dependency injection com `Depends`) são usados corretamente em toda a aplicação. O SQLAlchemy 2.0 com `Mapped`/`mapped_column` está corretamente adotado, o Alembic tem `render_as_batch=True` para SQLite, e as migrações são reversíveis. Os coletores assíncronos usam `asyncio.to_thread` para bibliotecas síncronas de terceiros (abordagem correta) e a classe `WebCollectorBase` implementa retry com backoff exponencial e rate limiting.

Os problemas encontrados concentram-se em três áreas: (1) criação de engine e session factory sem connection pool configurado e sem `check_same_thread=False` obrigatório para SQLite com FastAPI; (2) `get_session()` no módulo `database.py` cria uma nova engine por chamada — função legada que ainda existe mas nunca deveria ser usada no path da web; (3) o cache em memória global (`web/cache.py`) armazena objetos SQLAlchemy detachados da sessão que os criou, o que pode gerar `DetachedInstanceError` em lazy loads posteriores. Há também um achado de configuração onde `AlertSettings` e `Settings` duplicam os campos de alertas, e a senha SMTP não usa `SecretStr` de pydantic.

Nenhum achado é bloqueante para uso em desenvolvimento single-instance. Para produção os itens HIGH precisam ser resolvidos antes do lançamento.

**Distribuição por severidade:** 3 HIGH · 5 MEDIUM · 5 LOW

---

## Tabela de Achados

| # | Área | Arquivo:Linha | Severidade | Título |
|---|------|---------------|------------|--------|
| B-01 | SQLAlchemy | `storage/database.py:34` | HIGH | Engine SQLite sem `check_same_thread=False` e sem pool configurado |
| B-02 | SQLAlchemy | `storage/database.py:49-70` | HIGH | `get_session()` cria nova engine por chamada — vazamento de recursos |
| B-03 | Cache/SQLAlchemy | `web/cache.py:82-84` | HIGH | Cache global armazena objetos ORM fora da sessão — risco de `DetachedInstanceError` |
| B-04 | Configuração | `config.py:241-283` | MEDIUM | Duplicação de campos de alerta entre `AlertSettings` e `Settings`; `smtp_password` sem `SecretStr` |
| B-05 | Alembic | `alembic/versions/7f39d0510ecc_*.py:27` | MEDIUM | Enum SQLAlchemy criado com valores StrEnum (valores lowercase) mas migration usa strings uppercase |
| B-06 | SQLAlchemy/Modelos | `storage/models.py:139-142` | MEDIUM | `updated_at` com `onupdate=func.now()` não funciona em SQLite sem trigger |
| B-07 | Coletores | `collectors/ifdata.py:96-105` | MEDIUM | `IFDataCollector` — cliente HTTP criado lazily sem fechar se `collect()` for chamado sem context manager |
| B-08 | FastAPI/Rotas | `web/routes/taxas.py:47` | MEDIUM | Conversão direta `Indexador(indexador)` sem tratamento de `ValueError` — retorna HTTP 500 ao invés de 400 |
| B-09 | SQLAlchemy | `storage/repository.py:44-45` | LOW | `get_by_nome` com `scalar_one_or_none()` lança `MultipleResultsFound` se houver mais de uma IF com nome similar |
| B-10 | Modelos | `storage/models.py:345-355` | LOW | `TaxaReferencia` sem constraint único `(data, tipo)` — permite duplicatas silenciosas |
| B-11 | Alembic | `alembic/versions/c7e9f3a5b2d1_*.py` | LOW | Migração `mercado` sem `server_default` — rows existentes ficam NULL mas código trata OK |
| B-12 | FastAPI | `web/app.py:41` | LOW | `templates.env.globals["now"] = datetime.now` expõe função não-timezone-aware em todos os templates |
| B-13 | Coletores | `collectors/bcb.py:167` | LOW | `_collect_serie` silencia exceções com `except Exception: return None` sem logging |

---

## Análise Detalhada por Área

### 1. Padrões FastAPI (`src/veredas/web/`)

**O que está correto:**

- `app.py` usa `@asynccontextmanager` com `lifespan` (padrão correto, `on_event` está deprecado).
- `create_app()` é uma factory function — funciona corretamente com `uvicorn factory=True`.
- Todas as rotas usam `Depends(get_db)` que delega para `DatabaseManager.session_scope()` — ciclo de sessão correto.
- Middleware stack está na ordem certa: RateLimit (externo) → CSRF → SecurityHeaders (interno), que em ASGI significa execução na ordem inversa à adição.
- Responses de erro 404 usam `status_code=404` no `TemplateResponse` corretamente.
- HTMX requests são detectados via `request.headers.get("HX-Request")` e retornam partials.

**B-08 — MEDIUM — Conversão de enum sem tratamento de ValueError**

`web/routes/taxas.py:47`:
```python
if indexador:
    filters["indexador"] = Indexador(indexador)  # ValueError se valor inválido
```

A rota `anomalias.py` tem o helper `_parse_severidade()` que trata corretamente o `ValueError` e levanta `HTTPException(400)`. A rota `taxas.py` não replica esse padrão para o parâmetro `indexador`. Um valor inválido como `?indexador=xyz` gera HTTP 500 (traceback interno) ao invés de HTTP 400.

**Correção:** Usar o mesmo padrão de `_parse_severidade`, ou adicionar validação:
```python
try:
    filters["indexador"] = Indexador(indexador)
except ValueError:
    raise HTTPException(status_code=400, detail=f"Indexador inválido: '{indexador}'")
```

**B-12 — LOW — `datetime.now` não-timezone-aware em templates globais**

`web/app.py:41`:
```python
templates.env.globals["now"] = datetime.now
```

`datetime.now()` sem argumento retorna datetime naive (sem timezone). O projeto usa `TZ_BRASIL` consistentemente no resto do código. Se um template usar `{{ now() }}` para exibir horário, o resultado será horário local da máquina (pode ser UTC em servidor Linux), sem indicação de fuso.

**Correção:**
```python
from veredas import TZ_BRASIL
templates.env.globals["now"] = lambda: datetime.now(TZ_BRASIL)
```

**Middleware de rate limiting — observação:**

`ratelimit.py` usa `RateLimitStore` em memória com estado global singleton (`_store`). O comentário no código já menciona que para produção multi-instância seria necessário Redis. Para single-instance (uso atual) está correto. O store não é thread-safe para acessos concorrentes de múltiplas coroutines no mesmo event loop — não há `asyncio.Lock` protegendo `_store`. Em FastAPI com servidor único (Uvicorn single worker), isso é tecnicamente seguro porque o event loop é single-threaded, mas é um detalhe frágil se workers forem adicionados.

---

### 2. SQLAlchemy (`src/veredas/storage/`)

**O que está correto:**

- Modelos usam `Mapped[T]` e `mapped_column()` com tipos explícitos — SQLAlchemy 2.0 style correto.
- `Numeric` para todos os campos monetários e percentuais — sem `Float`.
- `session_scope()` com `try/except/finally` — commit em sucesso, rollback em exceção, `close()` sempre.
- Repositórios injetam `Session` via construtor — padrão repository correto.
- `selectinload` usado em `list_with_filters(eager_load=True)` para evitar N+1.
- Uso de `session.flush()` após `add()` em `create()` — permite acessar o ID gerado dentro da mesma transação.

**B-01 — HIGH — Engine SQLite sem `check_same_thread=False` e sem pool configurado**

`storage/database.py:34-35`:
```python
db_url = f"sqlite:///{db_path}"
return create_engine(db_url, echo=False)
```

SQLite por padrão lança `ProgrammingError: SQLite objects created in a thread can only be used in that same thread` quando acessado de uma thread diferente da criadora. FastAPI com Starlette executa as dependências de rota na thread do event loop, mas `session_scope()` é um generator síncrono usado com `Depends` — o Starlette o executa em um thread pool (via `run_in_threadpool`). Na prática isso não explode com Uvicorn single-worker, mas é uma bomba relógio.

Adicionalmente, sem `pool_pre_ping=True`, conexões idle podem ser fechadas pelo SO sem SQLAlchemy saber, gerando erros esporádicos em produção.

**Correção:**
```python
return create_engine(
    db_url,
    echo=False,
    connect_args={"check_same_thread": False},
    pool_pre_ping=True,
)
```

**B-02 — HIGH — `get_session()` cria nova engine por chamada**

`storage/database.py:49-70`:
```python
def get_session(db_path=None) -> Generator[Session, None, None]:
    engine = get_engine(db_path)           # nova engine a cada chamada
    session_factory = sessionmaker(bind=engine)  # novo factory a cada chamada
    session = session_factory()
    ...
```

Esta função module-level cria uma engine nova em cada invocação. Engines são pesadas (pool de conexões, metadata cache). A classe `DatabaseManager` resolve isso corretamente (engine criada uma vez no `__init__`). O problema é que `get_session()` ainda existe no módulo e pode ser usada por código que não passou pela revisão. Verificação: ela não é importada pelas rotas (que usam `dependencies.py → get_db_manager() → DatabaseManager`), mas está exportada pelo módulo e pode ser usada em testes ou CLI.

**Correção:** Deprecar e eventualmente remover `get_session()`. No curto prazo, adicionar `@deprecated` ou docstring clara. Se mantida, reescrever para usar um singleton de engine:
```python
_engine_cache: dict[str, Engine] = {}

def get_session(db_path=None):
    path = str(db_path or DEFAULT_DB_PATH)
    if path not in _engine_cache:
        _engine_cache[path] = get_engine(db_path)
    engine = _engine_cache[path]
    ...
```

**B-06 — MEDIUM — `onupdate=func.now()` não funciona em SQLite**

`storage/models.py:140-142`:
```python
updated_at: Mapped[datetime] = mapped_column(
    DateTime, server_default=func.now(), onupdate=func.now()
)
```

`onupdate` é uma diretiva de server-side que SQLAlchemy passa como `ON UPDATE` DDL — suportado em MySQL/PostgreSQL mas **ignorado pelo SQLite**. O SQLite não tem suporte nativo a `ON UPDATE CURRENT_TIMESTAMP`. Em SQLite, `updated_at` nunca será atualizado automaticamente pelo banco.

Afeta: `InstituicaoFinanceira`, `EventoRegulatorio`, `ProcessoRegulatorio`.

**Correção:** Usar ORM-level com evento `@event.listens_for` ou atualizar explicitamente nos métodos de upsert:
```python
# Opção A — ORM event (limpo, automático):
from sqlalchemy import event
@event.listens_for(InstituicaoFinanceira, "before_update")
def receive_before_update(mapper, connection, target):
    target.updated_at = datetime.now(TZ_BRASIL)

# Opção B — Explícito no upsert (já parcialmente feito):
for key, value in kwargs.items():
    setattr(instituicao, key, value)
instituicao.updated_at = datetime.now(TZ_BRASIL)  # adicionar esta linha
```

---

### 3. Cache e Objetos ORM Detachados

**B-03 — HIGH — Cache global armazena objetos ORM fora da sessão**

`web/cache.py:76-84`:
```python
def get_cached_reference_rates(session: Session) -> dict:
    cache_key = "reference_rates"
    cached = _reference_cache.get(cache_key)
    if cached is not None:
        return cached  # retorna objetos TaxaReferencia de uma sessão já fechada

    repo = TaxaReferenciaRepository(session)
    rates = {
        "selic": repo.get_latest("selic"),  # objetos ORM vinculados à sessão atual
        ...
    }
    _reference_cache.set(cache_key, rates)
    return rates
```

O cache armazena instâncias de `TaxaReferencia` que pertencem à sessão que as carregou. Quando a sessão é fechada (o que acontece ao final do request via `session_scope()`), os objetos tornam-se "detached" (desvinculados de qualquer sessão). Na próxima request que usar o cache, os objetos retornados são detached. Se o template acessar um atributo lazy-loaded (não há nenhum no modelo atual, mas isso pode mudar), ocorrerá `DetachedInstanceError`.

O problema é mais sutil: os objetos têm atributos simples (não lazy), então **não falha agora**. Mas é uma armadilha arquitetural: qualquer acesso futuro a um relacionamento causará erro silencioso em produção.

**Correção:** Armazenar apenas os valores primitivos no cache, não os objetos ORM:
```python
def get_cached_reference_rates(session: Session) -> dict:
    cache_key = "reference_rates"
    cached = _reference_cache.get(cache_key)
    if cached is not None:
        return cached

    repo = TaxaReferenciaRepository(session)
    def _to_dict(taxa):
        if taxa is None:
            return None
        return {"valor": taxa.valor, "data": taxa.data, "tipo": taxa.tipo}

    rates = {
        "selic": _to_dict(repo.get_latest("selic")),
        "cdi": _to_dict(repo.get_latest("cdi")),
        "ipca": _to_dict(repo.get_latest("ipca")),
    }
    _reference_cache.set(cache_key, rates)
    return rates
```

---

### 4. Migrações Alembic (`alembic/`)

**O que está correto:**

- `render_as_batch=True` em ambos os modos (offline e online) — obrigatório para SQLite.
- `target_metadata = Base.metadata` — autogenerate está configurado.
- `pool.NullPool` no modo online — correto para SQLite (evita pool desnecessário para banco de arquivo).
- `get_url()` com override via `VEREDAS_DB_PATH` — permite CI/CD com banco alternativo.
- Todas as migrações têm `downgrade()` implementado — reversíveis.
- `batch_alter_table` usado consistentemente nas migrações existentes.

**B-05 — MEDIUM — Discrepância entre valores de Enum no ORM e na migração**

`storage/models.py:97-103` (StrEnum):
```python
class Severidade(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"
```

`alembic/versions/7f39d0510ecc_initial_schema.py:229-230` (migration):
```python
sa.Column('severidade', sa.Enum('LOW', 'MEDIUM', 'HIGH', 'CRITICAL', name='severidade'), ...)
```

O ORM declara os valores como lowercase (`"low"`, `"medium"`, etc.) porque usa `StrEnum` cujo `value` é o nome em lowercase. A migração hardcoda os valores do enum como uppercase (`'LOW'`, `'HIGH'`). O mesmo ocorre com `TipoAnomalia`, `Segmento`, `Indexador` e outros.

**Impacto real:** Em SQLite, colunas `Enum` são armazenadas como `VARCHAR` sem validação de restrição. O ORM grava `"low"` e lê de volta `"low"` — funciona porque o SQLite não valida. Em PostgreSQL (se o projeto migrar), a discrepância causaria erros de constraint imediatos.

**Por que aconteceu:** O `autogenerate` do Alembic capturou os nomes dos membros do enum (uppercase, `LOW`, `HIGH`) ao invés dos valores (lowercase, `low`, `high`). Isso é um comportamento do SQLAlchemy com `StrEnum` — ele usa `member.name` ao criar o tipo `Enum`.

**Verificação:** Os dados gravados no banco via ORM serão lowercase. Se uma consulta futura via SQL raw usar os valores uppercase (como nas migrações), haverá 0 resultados.

**Correção de longo prazo:** Alterar os modelos para usar `native_enum=False` explicitando os valores:
```python
segmento: Mapped[Segmento] = mapped_column(
    Enum(Segmento, values_callable=lambda e: [m.value for m in e]),
    default=Segmento.OUTRO
)
```
Ou, mais simples para SQLite: usar `String` com validação no código e ignorar o tipo `Enum` do SQLAlchemy.

**B-11 — LOW — Migração `mercado` sem `server_default`**

`alembic/versions/c7e9f3a5b2d1_*.py:22`:
```python
batch_op.add_column(sa.Column("mercado", sa.String(length=20), nullable=True))
```

Correto como está (`nullable=True` — coluna opcional). Rows existentes ficam com `NULL`, o que é o comportamento desejado (sem informação de mercado antes da coluna ser adicionada). O código da aplicação trata `mercado` como `str | None` corretamente.

---

### 5. Coleta Assíncrona (`src/veredas/collectors/`)

**O que está correto:**

- `BCBCollector._collect_serie()` usa `asyncio.to_thread()` para a biblioteca síncrona `python-bcb` — correto e idiomático.
- `IFDataCollector` implementa `__aenter__`/`__aexit__` — context manager completo.
- `WebCollectorBase` tem retry com backoff exponencial e jitter (`2^attempt + random.uniform(0,1)`), rate limiting com `asyncio.Lock`, e rotação de User-Agent.
- `PlaywrightClient` fecha `page` e `context` no `finally` — sem resource leak.
- `CollectionScheduler._execute_task()` usa `asyncio.wait_for()` com timeout configurável.
- Erros de callback são capturados e logados sem interromper o scheduler.

**B-07 — MEDIUM — `IFDataCollector` sem context manager: cliente não é fechado**

`collectors/ifdata.py:96-105`:
```python
async def _get_client(self) -> httpx.AsyncClient:
    if self._client is None:
        self._client = httpx.AsyncClient(...)
    return self._client
```

`IFDataCollector.collect()` e `collect_por_cnpj()` chamam `_get_client()` que cria o cliente lazily. Se o coletor for usado **fora** de um `async with` (ex: `collector = IFDataCollector(); result = await collector.collect()`), o `httpx.AsyncClient` nunca é fechado — resource leak silencioso.

O CLI em `_collect.py:62-63` usa corretamente `async with IFDataCollector() as collector`. Mas `health_check()` no mesmo módulo chama `_get_client()` diretamente sem garantir fechamento:

```python
async def health_check(self) -> bool:
    client = await self._get_client()  # cria cliente sem fechar
    response = await client.get(...)
```

**Correção:** Eliminar o padrão lazy-client. Criar o cliente sempre via context manager, ou fazer `health_check` usar um client dedicado de curta duração:
```python
async def health_check(self) -> bool:
    async with httpx.AsyncClient(timeout=10) as client:
        response = await client.get(...)
        return response.status_code == 200
```

**B-13 — LOW — `_collect_serie` silencia exceções sem logging**

`collectors/bcb.py:163-167`:
```python
except Exception:
    return None
```

Falhas de parsing, erros de rede ou respostas inesperadas da API do BCB são silenciadas. O chamador (`collect()`) não sabe se a série foi omitida por ausência de dados ou por erro técnico — `dados.selic` fica `None` em ambos os casos.

**Correção:** Logar no nível `DEBUG` ou `WARNING`:
```python
except Exception as exc:
    logger.debug("Falha ao coletar série %s: %s", tipo, exc)
    return None
```

---

### 6. Configuração (`src/veredas/config.py`)

**O que está correto:**

- `pydantic-settings` com `SettingsConfigDict` — correto.
- `@lru_cache` em `get_settings()` — singleton correto.
- Sub-configurações organizadas em classes separadas (`DatabaseSettings`, `CollectorSettings`, etc.).
- `Decimal` para todos os thresholds numéricos — evita imprecisão de float.
- `extra="ignore"` — não falha com variáveis de ambiente extras.
- `ensure_data_dir()` cria diretório de dados.

**B-04 — MEDIUM — Duplicação de campos de alerta; `smtp_password` sem `SecretStr`**

`config.py:166-211` — classe `AlertSettings` define os campos de alerta completos.
`config.py:274-283` — classe `Settings` redefine os mesmos campos manualmente:

```python
# Em AlertSettings:
smtp_password: str | None = Field(default=None, ...)

# Em Settings (duplicado):
smtp_password: str | None = Field(default=None)
```

`AlertSettings` existe mas não é usada como sub-configuração de `Settings` (diferente de `database`, `collector`, `web` que estão como `Field(default_factory=...)`). Isso significa que `VEREDAS_SMTP_PASSWORD` popula `Settings.smtp_password` corretamente, mas `AlertSettings` existe como classe autônoma não conectada.

Adicionalmente, `smtp_password` e `telegram_bot_token` deveriam ser `SecretStr` para evitar que apareçam em logs e em `repr()`:

```python
from pydantic import SecretStr

smtp_password: SecretStr | None = Field(default=None)
telegram_bot_token: SecretStr | None = Field(default=None)
```

**Correção:** Remover os campos duplicados de `Settings` e usar `AlertSettings` como sub-configuração:
```python
class Settings(BaseSettings):
    ...
    alerts: AlertSettings = Field(default_factory=AlertSettings)
```
E atualizar os acessos de `settings.smtp_password` para `settings.alerts.smtp_password`.

---

### 7. Modelos de Dados (`src/veredas/storage/models.py`)

**O que está correto:**

- Uso consistente de `Numeric` ao invés de `Float` para valores monetários e percentuais.
- `Decimal` nos type hints Python (`Mapped[Decimal]`).
- Índices declarados onde esperado: FK columns, `data_coleta`, `cnpj`, `data_evento`.
- `StrEnum` para enums — serializa como string lowercase automaticamente.
- Relacionamentos bidirecionais com `back_populates`.
- `server_default=func.now()` para `created_at` — correto.
- `UniqueConstraint` em `numero_processo` de `ProcessoRegulatorio`.

**B-09 — LOW — `get_by_nome` lança `MultipleResultsFound` silenciosamente**

`storage/repository.py:44-45`:
```python
def get_by_nome(self, nome: str) -> InstituicaoFinanceira | None:
    stmt = select(InstituicaoFinanceira).where(InstituicaoFinanceira.nome.ilike(f"%{nome}%"))
    return self.session.execute(stmt).scalar_one_or_none()
```

`scalar_one_or_none()` lança `MultipleResultsFound` se mais de uma IF tiver nome que contém a substring. Busca parcial (`ilike("%nome%")`) é muito permissiva para retornar exatamente um resultado.

**Correção:** Usar `scalars().first()` ou documentar a expectativa:
```python
return self.session.execute(stmt).scalars().first()
```

**B-10 — LOW — `TaxaReferencia` sem constraint único `(data, tipo)`**

`storage/models.py:344-355`: `TaxaReferencia` não tem `UniqueConstraint` em `(data, tipo)`. O método `upsert()` em `TaxaReferenciaRepository` busca e atualiza se existir, mas uma condição de corrida (duas coletas simultâneas do BCB) pode inserir duplicatas.

**Correção:** Adicionar constraint:
```python
from sqlalchemy import UniqueConstraint

class TaxaReferencia(Base):
    __tablename__ = "taxas_referencia"
    __table_args__ = (UniqueConstraint("data", "tipo", name="uq_taxa_ref_data_tipo"),)
    ...
```
E criar migração correspondente.

---

## Recomendações Priorizadas

### Prioridade 1 — Corrigir antes de qualquer ambiente compartilhado

**B-01 — `check_same_thread=False` e `pool_pre_ping=True`**
Arquivo: `src/veredas/storage/database.py`, função `get_engine()`, linha 34.
Mudança mínima: adicionar `connect_args={"check_same_thread": False}, pool_pre_ping=True` ao `create_engine()`.

**B-03 — Cache ORM detachado**
Arquivo: `src/veredas/web/cache.py`, função `get_cached_reference_rates()`.
Mudança: extrair apenas valores primitivos antes de cachear, não as instâncias ORM.

**B-02 — Remover/deprecar `get_session()`**
Arquivo: `src/veredas/storage/database.py`, linhas 49-70.
A função legada deve ser removida ou convertida para usar o singleton. O path da web não a usa, mas sua existência é perigosa.

### Prioridade 2 — Corrigir antes de produção

**B-04 — Consolidar configuração de alertas e usar `SecretStr`**
Arquivo: `src/veredas/config.py`.
Usar `AlertSettings` como sub-configuração de `Settings`, e `SecretStr` para credenciais.

**B-06 — `updated_at` em SQLite**
Arquivo: `src/veredas/storage/models.py`.
Adicionar SQLAlchemy ORM event `before_update` nos três modelos afetados, ou atualizar manualmente nos métodos de upsert dos repositórios.

**B-07 — Fechar cliente HTTP em `health_check()` de `IFDataCollector`**
Arquivo: `src/veredas/collectors/ifdata.py`.
Criar client local e descartável em `health_check()`.

**B-08 — Tratar `ValueError` em conversão de `Indexador` nas rotas**
Arquivo: `src/veredas/web/routes/taxas.py:47`.
Replicar o padrão `_parse_severidade()` já existente em `anomalias.py`.

### Prioridade 3 — Melhorias de qualidade

**B-05 — Enum uppercase vs lowercase**
Documentar explicitamente o comportamento esperado para SQLite. Para portabilidade futura para PostgreSQL, adicionar `values_callable=lambda e: [m.value for m in e]` nos `mapped_column(Enum(...))`.

**B-09 — `get_by_nome` com `scalar_one_or_none`**
Trocar por `.scalars().first()`.

**B-10 — UniqueConstraint em `TaxaReferencia`**
Adicionar `__table_args__` com constraint único `(data, tipo)` e criar migração.

**B-12 — `datetime.now` sem timezone em template global**
Trocar por `lambda: datetime.now(TZ_BRASIL)`.

**B-13 — Logging silenciado em `_collect_serie`**
Adicionar `logger.debug(...)` no `except`.

---

## Pontos de Excelência Identificados

Os seguintes padrões merecem destaque positivo e devem ser mantidos como referência para evolução do projeto:

1. **Dependency injection correto**: `get_db()` em `dependencies.py` usa o singleton `get_db_manager()` para reutilizar a engine e o `session_scope()` para gerenciar o ciclo da sessão. Nenhuma sessão vaza para fora do request.

2. **Repository pattern bem executado**: Cada repositório recebe `Session` no construtor, não tem estado próprio, e os métodos retornam tipos específicos. O uso de `session.flush()` após `add()` permite acessar o ID gerado dentro da mesma transação sem `commit` prematuro.

3. **`WebCollectorBase` com retry e rate limiting**: Backoff exponencial com jitter, separação de erros 4xx (definitivos) vs 5xx (retriáveis), e rate limiting por instância com `asyncio.Lock`. É um padrão de produção correto.

4. **Alembic configurado corretamente para SQLite**: `render_as_batch=True` em ambos os modos, `NullPool` no online mode, e override via variável de ambiente. As três migrações existentes são todas reversíveis.

5. **Scheduler com imutabilidade**: `ScheduledTask` é um `dataclass` e o scheduler usa `dataclasses.replace()` para criar novas instâncias ao atualizar estatísticas — evita mutação acidental de estado compartilhado.

6. **Modelos financeiros com `Numeric`**: Nenhum campo monetário ou percentual usa `Float` — todos usam `Numeric(precision, scale)` com `Decimal` no Python. Isso é crítico para aplicações financeiras.

---

*Relatório gerado por análise estática do código-fonte. Arquivo de referência: `o:/OneDrive/Documents/_DEV_/2. PESSOAL/myFOSS/veredas-de-papel/docs/relatorio_backend.md`*
