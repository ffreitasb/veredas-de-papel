# Relatório de Revisão Arquitetural — veredas de papel

**Data:** 2026-04-24  
**Versão analisada:** 0.1.0-alpha  
**Escopo:** `src/veredas/` completo

---

## Sumário Executivo

O projeto veredas de papel é uma aplicação bem estruturada com clara separação de responsabilidades e boa cobertura de funcionalidades. A arquitetura geral é sólida: camadas bem definidas (web → repository → storage), padrão Repository implementado corretamente, hierarquia de detectores extensível e infraestrutura de coletores bem abstraída.

Os problemas encontrados são em sua maioria de grau MÉDIO ou SUGESTÃO e dizem respeito a inconsistências de design que acumulam dívida técnica ao longo do tempo. Há dois problemas de grau ALTO que merecem atenção antes da primeira release pública: configuração duplicada e o acoplamento de rotas ao objeto `templates` global.

**Pontuação geral:** 7,2 / 10 — base sólida, pronto para correções cirúrgicas antes de 0.2.0.

---

## Mapa de Dependências entre Módulos

```
config.py (singleton puro, sem deps internas)
    └── web/dependencies.py
    └── alerts/manager.py, email.py, telegram.py
    └── web/app.py (lifespan)

catalog.py (puro, sem deps internas)
    └── detectors/engine.py
    └── web/app.py (globals de template)

storage/models.py (Base ORM)
    └── storage/database.py
    └── storage/repository.py
    └── collectors/scrapers/normalize.py (importa Indexador)
    └── detectors/* (importam Severidade, TaxaCDB, TipoAnomalia)
    └── alerts/base.py (importa Anomalia)

storage/repository.py
    └── web/routes/* (consumidores diretos)
    └── cli/main.py
    └── web/cache.py

collectors/base.py (ABC)
    └── collectors/bcb.py, ifdata.py
    └── collectors/scraper_base.py (WebCollectorBase)
        └── collectors/scrapers/xp.py, btg.py, inter.py, rico.py
    └── collectors/b3/collector.py

detectors/base.py (ABC, AnomaliaDetectada, DetectionResult)
    └── detectors/rules.py
    └── detectors/statistical.py
    └── detectors/ml.py
    └── detectors/engine.py (orquestra os três)

web/app.py (templates GLOBAL, create_app)
    └── web/routes/* (todos importam `templates` daqui — acoplamento)

alerts/base.py (ABC AlertSender)
    └── alerts/email.py, telegram.py
    └── alerts/manager.py (orquestra)

cli/main.py
    └── storage/* (direto, sem camada de servico)
    └── collectors/* (direto)
    └── detectors/* (direto)
    └── alerts/* (direto)

AUSENTE: camada de servico/use-case entre web/cli e storage
```

---

## Problemas Encontrados

### ALTO — A1: Configuração duplicada com risco de divergência silenciosa

**Arquivo:** `src/veredas/config.py`, linhas 166–212 e 241–283

O objeto `Settings` (classe principal) redeclara todos os campos de alertas (`smtp_host`, `smtp_port`, `smtp_user`, `smtp_password`, `alert_email_to`, `telegram_bot_token`, `telegram_chat_id`, `alert_min_severity`, `alert_cooldown_minutes`) que já existem na `AlertSettings`. A `AlertSettings` também tem `env_prefix="VEREDAS_"` igual ao `Settings`.

Isso cria dois comportamentos problemáticos:
1. Uma variável de ambiente como `VEREDAS_SMTP_HOST` pode ser lida pelo `Settings` diretamente mas a `AlertSettings` independente nunca é usada (ela não está nem aninhada em `Settings`). A hierarquia `Settings.detection: DetectionThresholds`, `Settings.statistical`, `Settings.ml`, `Settings.database`, `Settings.collector`, `Settings.web` tem sub-configurações aninhadas, mas os campos de alerta ficaram soltos no `Settings`.
2. Um desenvolvedor que acesse `get_settings().smtp_host` recebe o valor; outro que instancie `AlertSettings()` recebe o mesmo valor por variável de ambiente, mas são instâncias desconexas. Se a lógica em `alerts/manager.py` e `alerts/email.py` usar `get_settings()`, funciona — mas a existência da `AlertSettings` separada induz o consumidor a instanciá-la diretamente.

**Impacto:** Dificulta testes de unidade (mock de configuração fragmentado), e a `AlertSettings` isolada é letra morta.

**Correção:** Mover os campos de alerta para dentro de `AlertSettings`, criar `alerts: AlertSettings = Field(default_factory=AlertSettings)` dentro de `Settings` e remover as duplicatas do `Settings`. Atualizar `alerts/manager.py`, `alerts/email.py` e `alerts/telegram.py` para acessar `settings.alerts.smtp_host` etc.

---

### ALTO — A2: Objeto `templates` global acoplado a todas as rotas

**Arquivo:** `src/veredas/web/app.py`, linha 36; consumido em `web/routes/home.py:19`, `anomalias.py:18`, `taxas.py:18`, `instituicoes.py:20`, `timeline.py:17`

Todas as rotas importam `templates` diretamente de `veredas.web.app`:

```python
from veredas.web.app import templates
```

Isso cria um acoplamento estrutural das rotas ao módulo app: o objeto singleton `Jinja2Templates` é um estado global. Em testes unitários das rotas é necessário importar `veredas.web.app` inteiro apenas para ter o objeto de templates, o que puxa as dependências de `catalog`, `csrf`, `ratelimit` e outras.

**Impacto:** Torna as rotas não testáveis de forma isolada. Qualquer mudança no inicializador do `app.py` pode quebrar testes de rotas.

**Correção sugerida (two-step):**
1. Curto prazo: mover `templates` para `web/templates_config.py` (módulo independente sem imports pesados).
2. Médio prazo: injetar `templates` via `Request.app.state.templates` (FastAPI permite popular `app.state` no lifespan) e ler nas rotas como `request.app.state.templates`.

---

### MÉDIO — M1: Ausência completa de camada de serviço (use-cases)

**Arquivo:** `src/veredas/cli/main.py`, funções `_collect_bcb` (linha 174), `_collect_ifdata` (linha 221), `_collect_scrapers` (linha 288), `_collect_b3` (linha 359)

**Arquivo:** `src/veredas/web/routes/home.py`, `anomalias.py`, `taxas.py`

A CLI e as rotas web manipulam diretamente os repositórios e orquestram lógica de negócio que não pertence à camada de apresentação. Exemplos concretos:

- `_collect_bcb` (cli/main.py:174): coleta, valida dados e persiste — mistura I/O de rede, decisão de negócio e I/O de banco.
- `_collect_b3` (cli/main.py:359): faz upsert de IF, cria TaxaCDB, infere indexador como `Indexador.CDI` hardcoded na linha 427 — regra de negócio dentro de função CLI.
- `home.py:27-73`: uma rota HTTP executa 6 queries separadas sem nenhuma camada de agregação.

**Impacto:** Lógica duplicável (a web e a CLI que quiserem fazer a mesma coisa precisam copiar código), não testável sem inicializar banco real, e dificulta futuras migrações de interface (ex: adicionar uma API REST JSON mantendo a mesma lógica).

**Correção:** Introduzir `src/veredas/services/` com `CollectionService`, `DetectionService`, `DashboardService`. As rotas e a CLI passam a chamar esses serviços. Os serviços recebem sessão por injeção.

---

### MÉDIO — M2: `get_session` em `database.py` cria engine a cada chamada

**Arquivo:** `src/veredas/storage/database.py`, linhas 49–70

```python
def get_session(db_path: Path | str | None = None) -> Generator[Session, None, None]:
    engine = get_engine(db_path)          # cria engine novo
    session_factory = sessionmaker(bind=engine)  # cria factory nova
    session = session_factory()
    ...
```

A função `get_session` (módulo-nível, não o método do `DatabaseManager`) cria uma nova engine e uma nova `sessionmaker` a cada invocação. Embora o `get_engine` não faça `create_engine` de forma explicitamente problemática no SQLite (o arquivo é o mesmo), o padrão correto é reutilizar a engine via pool. Mais importante: essa função existe em paralelo com `DatabaseManager.session_scope()` e as rotas web usam o `DatabaseManager` via `dependencies.py` (correto), mas nada impede que código novo use `get_session` diretamente.

A função `get_session` na verdade é usada em zero lugares atualmente (nenhum `grep` revelou imports dela em código de produção), mas está exportada no `storage/__init__.py`, induzindo uso equivocado.

**Impacto:** Baixo em produção (SQLite single-file), alto em confusão de design. Em uma migração para PostgreSQL a engine sem pool seria crítica.

**Correção:** Remover `get_session` e `init_db` do módulo `database.py` (ou marcá-las como `_get_session_impl` internas) e mantê-las apenas via `DatabaseManager`. Remover exports de `storage/__init__.py`.

---

### MÉDIO — M3: `datetime.now()` sem timezone em múltiplos detectores

**Arquivos:** `detectors/rules.py:85,94,254,275,381,397`; `detectors/statistical.py:146,176,338,377,497,527`; `detectors/ml.py:112,123,155,166,205,215`; `detectors/engine.py:206,305`; `alerts/manager.py:114,115,175`; `web/cache.py:28,39`

O projeto usa corretamente `TZ_BRASIL` ao criar timestamps persistidos (por exemplo, `repository.py` usa `datetime.now(TZ_BRASIL)` nas anomalias), mas os detectores usam `datetime.now()` sem timezone para timestamps intermediários de medição de performance (`start_time`, `executed_at`, `detectado_em` no `AnomaliaDetectada`).

O campo `detectado_em` de `AnomaliaDetectada` (dataclass em `detectors/base.py:41`) é `field(default_factory=datetime.now)` — sem timezone. Este timestamp acaba sendo persistido em `AnomaliaRepository.create()` (linha 373), onde o parâmetro `detectado_em` vem da anomalia detectada. Assim timestamps persistidos podem ser naive enquanto os criados direto pelo repository são aware, impossibilitando comparações corretas.

**Impacto:** Comparação entre `Anomalia.detectado_em` (pode ser naive) e consultas temporais com `datetime.now(TZ_BRASIL)` produz `TypeError` ou resultados incorretos no SQLite.

**Correção:** Substituir `default_factory=datetime.now` por `default_factory=lambda: datetime.now(TZ_BRASIL)` em `AnomaliaDetectada`. Criar constante `TZ_BRASIL` em `detectors/base.py` ou importar de `veredas`.

---

### MÉDIO — M4: `TaxaCDBRepository.get_desvio_padrao` é lógica de domínio no repositório

**Arquivo:** `src/veredas/storage/repository.py`, linhas 173–219

O método `get_desvio_padrao` busca todos os valores de uma coluna e calcula o desvio padrão em Python com um loop manual. Há dois problemas:

1. **Violação do SRP no padrão Repository:** Repositórios devem coordenar persistência, não executar cálculos analíticos. Cálculo de desvio padrão é domínio da camada de detecção.
2. **Escalabilidade:** Para N taxas (pode ser dezenas de milhares), carrega tudo em memória para calcular uma estatística. SQLite não tem `STDDEV`, mas a extensão `sqlite-vec` ou uma subquery com `variance` via `julianday` podem ajudar. Alternativamente, calcular no Python após uma query com `GROUP BY` já seria menos invasivo.

O comentário no código (`SQLite não tem STDDEV nativo`) está correto, mas a solução escolhida viola camadas.

**Correção:** Mover o cálculo para `detectors/features.py` ou para um futuro `services/statistics_service.py`. O repositório expõe apenas `list_percentuais(indexador, desde)` retornando a sequência bruta.

---

### MÉDIO — M5: Dois padrões de filtro incompatíveis no mesmo repositório

**Arquivo:** `src/veredas/storage/repository.py`

`TaxaCDBRepository.list_paginated` (linha 245) e `AnomaliaRepository.list_with_filters` (linha 423) aceitam `filters: dict | None` com chaves string. `AnomaliaRepository.count_with_filters` (linha 462) repete toda a lógica de filtragem por dict, duplicando código. Em contraste, `InstituicaoRepository.list_paginated` (linha 54) recebe parâmetros explícitos (`order_by: str`, `limit: int`, `offset: int`).

Há dois estilos incompatíveis no mesmo arquivo:
- Parâmetros tipados e explícitos (`InstituicaoRepository`)
- Dict não tipado (`TaxaCDBRepository`, `AnomaliaRepository`)

O dict não tipado perde a verificação estática do mypy/pyright: `filters["indexador"] = Indexador(indexador)` (taxas.py:46) pode lançar `ValueError` sem tratamento.

Além disso, `list_with_filters` e `count_with_filters` têm lógica idêntica de filtragem duplicada (linhas 447–457 vs. 466–476).

**Correção:** Extrair um dataclass `AnomaliaFilter(severidade, tipo, cnpj, resolvido)` e um `TaxaFilter(indexador, prazo_min, prazo_max, instituicao_id, mercado)`. Ambos `list_*` e `count_*` recebem o mesmo objeto, eliminando duplicação e trazendo tipagem estática.

---

### MÉDIO — M6: `AlertManager` mantém estado em memória sem estratégia de persistência

**Arquivo:** `src/veredas/alerts/manager.py`, linha 55

```python
self._alert_history: dict[int, datetime] = {}
```

O cooldown de alertas é mantido em dicionário na instância do `AlertManager`. Toda vez que o processo reinicia, o histórico é perdido. Se a CLI criar um `AlertManager` para enviar alertas e a web criar outro, eles não compartilham histórico — um mesmo evento pode gerar dois alertas.

**Impacto:** Médio para o uso atual (ferramenta local), mas se o scheduler for integrado ao processo web via lifespan, o problema escala.

**Correção sugerida:** Persistir cooldowns na tabela `anomalias` (adicionar coluna `ultimo_alerta_em`) ou em uma tabela `alertas_enviados`. O `AlertManager` consulta o banco em vez de manter dicionário.

---

### MÉDIO — M7: `DetectionEngine._setup_detectors` instancia scikit-learn no construtor

**Arquivo:** `src/veredas/detectors/engine.py`, linhas 152–184

Os detectores `IsolationForestDetector` e `DBSCANOutlierDetector` são sempre instanciados no `_setup_detectors`, mesmo quando `config.enable_ml = False`. Como esses detectores importam `sklearn` no topo do módulo `ml.py`, a importação ocorre mesmo quando ML está desativado.

**Impacto:** Tempo de startup maior e falha de import em ambientes sem `scikit-learn` instalado, mesmo quando ML é explicitamente desativado via `EngineConfig(enable_ml=False)`.

**Correção:** Mover a instanciação dos detectores ML para dentro do bloco condicional:

```python
if self.config.enable_ml:
    # importação e instanciação somente aqui
    from veredas.detectors.ml import IsolationForestDetector, DBSCANOutlierDetector
    self.isolation_forest_detector = ...
    self.dbscan_detector = ...
```

---

### SUGESTÃO — S1: `scraper_client.py` com import condicional obscurece dependência

**Arquivo:** `src/veredas/collectors/scrapers/xp.py`, linha 52

```python
try:
    from veredas.collectors.scraper_client import PlaywrightClient
except ImportError:
    return CollectionResult.error(...)
```

O import condicional de `PlaywrightClient` dentro do método `collect()` esconde que Playwright é uma dependência necessária. O erro só aparece em runtime ao coletar, não no startup.

**Impacto:** UX ruim. O usuário executa `veredas collect scrapers` e recebe erro na metade da coleta, não em tempo de verificação.

**Sugestão:** Mover a verificação de disponibilidade do Playwright para um método `_check_dependencies()` chamado no `__aenter__`, ou fornecer um `can_run: bool = property` nos coletores que dependem de extras.

---

### SUGESTÃO — S2: `RuleBasedEngine` tem dois pontos de entrada com sobreposição

**Arquivo:** `src/veredas/detectors/rules.py`, linhas 467–539

`RuleBasedEngine` expõe tanto `analyze_spreads`, `analyze_variacoes`, `analyze_divergencias` individualmente quanto `run_all`. O `DetectionEngine` usa apenas os métodos individuais (chama `rule_engine.analyze_spreads(...)` etc.). O método `run_all` existe mas não é chamado por nenhum consumidor.

**Sugestão:** Ou remover `run_all` (YAGNI) ou torná-lo o único ponto de entrada e ter `DetectionEngine` usar-o.

---

### SUGESTÃO — S3: `filters: dict | None` aceita chave `"resolvido"` como bool ou string

**Arquivo:** `src/veredas/storage/repository.py`, linha 456; `web/routes/anomalias.py`, linha 77

```python
if status == "ativas":
    filters["resolvido"] = False
```

O dict aceita `False` (bool) como valor de `"resolvido"`. Em `AnomaliaRepository.list_with_filters:456`:
```python
stmt = stmt.where(Anomalia.resolvido == filters["resolvido"])
```

SQLAlchemy compara com `False` (correto), mas a ausência de tipagem torna frágil: um `filters["resolvido"] = "false"` (string) passaria a verificação de tipo e silenciosamente não filtraria nada.

---

### SUGESTÃO — S4: `_collect_b3` em `cli/main.py` importa `Indexador` dentro do loop

**Arquivo:** `src/veredas/cli/main.py`, linha 423

```python
from veredas.storage.models import Indexador
```

Import dentro de loop. Python cacheia módulos então não há custo extra de importação, mas o padrão é confuso e foi documentado como comentário `BUG` em outros pontos do código.

---

### SUGESTÃO — S5: `TaxaColetadaPlataforma` e `TaxaCDB` têm esquemas sobrepostos

**Arquivo:** `src/veredas/storage/models.py`, linhas 153–198 (`TaxaCDB`) e 597–639 (`TaxaColetadaPlataforma`)

Os dois modelos guardam informações muito similares: `emissor_cnpj`, `indexador`, `percentual`, `taxa_adicional`, `prazo_dias`, `valor_minimo`, `liquidez_diaria`, `raw_data`. A distinção é que `TaxaCDB` tem `fonte` (string) enquanto `TaxaColetadaPlataforma` tem `plataforma` (string) e foca em detectores de discrepância.

À medida que a plataforma cresce, manter duas tabelas com dados quase idênticos gera inconsistências. Considere se `TaxaColetadaPlataforma` deveria ser uma view ou uma flag `mercado='plataforma'` dentro de `TaxaCDB`, ou se justifica a separação com documentação explícita dos casos de uso distintos.

---

### SUGESTÃO — S6: `alias` de compatibilidade como dívida técnica

**Arquivo:** `src/veredas/storage/repository.py`, linhas 393–394 e 517–518 e 734–735

```python
# Alias para compatibilidade com web routes
mark_resolved = resolver
get_latest = get_ultima
InstituicaoFinanceiraRepository = InstituicaoRepository
EventoRegulatorioRepository = EventoRepository
```

Quatro aliases de compatibilidade indicam que houve renomeação mas os consumidores não foram totalmente atualizados. É dívida técnica visível.

**Sugestão:** Em um dia de refactoring, atualizar todos os consumidores para usar os nomes canônicos e remover os aliases. Manter apenas um dos dois nomes.

---

## Pontos Positivos

Estes aspectos merecem reconhecimento e devem ser preservados em refatorações:

1. **`database.py` + `dependencies.py`:** A gestão de sessão FastAPI está correta. O `get_db_manager()` com `@lru_cache(maxsize=1)` garante singleton de engine, e `session_scope()` com commit/rollback/close é idiomático.

2. **`BaseDetector` / `BaseCollector` como ABCs:** Os contratos abstratos são bem definidos, com `name`, `description` e `detect`/`collect` forçados nas subclasses.

3. **`catalog.py` puro:** O módulo não importa nada do próprio projeto, o que evita imports circulares e é explicitamente documentado. Decisão de design correta.

4. **`WebCollectorBase`:** Rate limiting, retry exponencial com jitter, pool de User-Agents e contexto assíncrono são implementados no lugar certo — na base, não em cada scraper.

5. **`EngineConfig` + `EngineResult` como dataclasses:** A engine de detecção recebe suas dependências via objeto de configuração imutável, o que facilita testes e parametrização.

6. **`AnomaliaRepository.list_with_filters` com `eager_load=True`:** O uso de `selectinload` para prevenir N+1 queries nas rotas de anomalia está corretamente implementado e documentado.

7. **`scraper/normalize.py` com funções puras:** O parsing de texto financeiro brasileiro está isolado em funções sem side effects, bem documentado e com exemplos inline.

8. **Middlewares de segurança no `app.py`:** CSRF, rate limiting e security headers são aplicados na camada certa (middleware), não dispersos nas rotas.

---

## Roadmap de Refatoração em 3 Horizontes

### Horizonte 1 — Quick Wins (1-2 dias, antes da release 0.1.x)

| # | Ação | Arquivo(s) | Impacto |
|---|------|-----------|---------|
| H1-1 | Consolidar campos de alerta no `Settings` como `alerts: AlertSettings` | `config.py` | Elimina A1 (duplicação de configuração) |
| H1-2 | Mover `templates` para `web/templates_config.py` | `web/app.py`, `web/routes/*.py` | Reduz acoplamento (A2 — step 1) |
| H1-3 | Substituir `datetime.now()` por `datetime.now(TZ_BRASIL)` nos detectores | `detectors/base.py`, `detectors/rules.py`, `detectors/ml.py`, `detectors/statistical.py`, `alerts/manager.py` | Elimina M3 (bug de timezone) |
| H1-4 | Lazy-import ML dentro do bloco `if enable_ml` | `detectors/engine.py` | Elimina M7 (startup com sklearn) |
| H1-5 | Remover aliases de compatibilidade atualizando consumidores | `storage/repository.py`, `web/routes/*.py` | Elimina S6 (dívida técnica visível) |

### Horizonte 2 — Médio Prazo (1-2 semanas, release 0.2.0)

| # | Ação | Arquivo(s) | Impacto |
|---|------|-----------|---------|
| H2-1 | Introduzir `services/collection_service.py` e `services/detection_service.py` | Novo; adaptar `cli/main.py`, `web/routes/*.py` | Elimina M1 (ausência de camada de serviço) |
| H2-2 | Criar dataclasses `AnomaliaFilter` e `TaxaFilter` | `storage/repository.py` | Elimina M5 (dict não tipado, duplicação de filtros) |
| H2-3 | Mover `get_desvio_padrao` para `services/statistics_service.py` | `storage/repository.py` | Elimina M4 (cálculo analítico no repositório) |
| H2-4 | Deprecar `get_session` e `init_db` module-level em `database.py` | `storage/database.py`, `storage/__init__.py` | Elimina M2 (engine recriada a cada chamada) |
| H2-5 | Escrever testes unitários para detectores de regras e parsers | `tests/detectors/`, `tests/collectors/` | Infra de qualidade para refatorações futuras |

### Horizonte 3 — Longo Prazo (1-2 meses, release 0.3.0)

| # | Ação | Arquivo(s) | Impacto |
|---|------|-----------|---------|
| H3-1 | Injetar `templates` via `app.state` no lifespan | `web/app.py`, `web/routes/*.py` | Elimina A2 completamente (rotas sem acoplamento a app.py) |
| H3-2 | Persistir histórico de cooldown de alertas no banco | `alerts/manager.py`, nova tabela `alertas_enviados` | Elimina M6 (estado de alerta perdido no restart) |
| H3-3 | Avaliar unificação de `TaxaCDB` e `TaxaColetadaPlataforma` | `storage/models.py` | Elimina S5 (esquemas sobrepostos) |
| H3-4 | Introduzir protocolo formal `Collector` com `Protocol` (PEP 544) | `collectors/base.py` | Permite composição sem herança obrigatória |
| H3-5 | API REST JSON (FastAPI JSON routes) para integração externa | `web/routes/` | Habilita clientes não-HTML |
| H3-6 | Migrações Alembic para todas as novas tabelas da Fase 4 | `alembic/` | Gestão de schema production-safe |

---

## Apêndice: Checklist de Violações SOLID

| Princípio | Status | Evidência |
|-----------|--------|-----------|
| SRP | Parcial | `cli/main.py`: funções `_collect_*` misturam I/O de rede, negócio e banco. `TaxaCDBRepository.get_desvio_padrao` faz cálculo analítico. |
| OCP | Bom | Detectores e coletores são extensíveis via herança de ABC sem modificar código existente. |
| LSP | Bom | Hierarquias `BaseDetector` → detectores concretos, `BaseCollector` → coletores concretos são substituíveis. |
| ISP | Aceitável | `BaseDetector.detect(data: Any)` usa `Any` como tipo de entrada, o que enfraquece o contrato. |
| DIP | Parcial | `alerts/email.py` e `alerts/telegram.py` chamam `get_settings()` diretamente no `__init__` em vez de receber configuração por injeção. `DetectionEngine` instancia todos os detectores internamente — não há como injetar detectores externos sem subclassing. |
