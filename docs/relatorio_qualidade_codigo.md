# Relatório de Qualidade de Código — veredas-de-papel

**Data:** 2026-04-24
**Versão analisada:** 0.1.0-alpha
**Modelo de análise:** Revisão manual + AST estático
**Escopo:** 57 arquivos Python em `src/veredas/` — 13.094 linhas

---

## Sumário Executivo

O projeto apresenta arquitetura bem estruturada, com separação clara de responsabilidades
entre coletores, detectores, repositórios e camada web. A maior parte do código segue boas
práticas Python modernas (SQLAlchemy 2.x Mapped, `X | Y` em vez de `Optional`, enums `StrEnum`,
type hints consistentes na interface pública). Não há débito técnico estrutural grave.

Os problemas encontrados são, em sua maioria, de **nível médio** e concentrados em três áreas:
(1) funções longas na CLI e no motor de detecção; (2) tratamento excessivamente silencioso de
exceções nos coletores; e (3) inconsistências de estilo que não chegam a comprometer a
manutenibilidade, mas que aumentam o custo de leitura.

Destaque positivo: ausência completa de imports circulares, configuração centralizada com
pydantic-settings, uso idiomático de context managers nos coletores, e proteções de segurança
web (CSRF, Rate Limit, Security Headers) já implementadas de forma correta.

---

## Tabela de Métricas

| Métrica                           | Valor          |
|-----------------------------------|----------------|
| Arquivos Python analisados        | 57             |
| Linhas totais (incluindo vazias)  | 13.094         |
| Funções com CC estimada > 10      | 7              |
| Funções com > 50 linhas           | 20             |
| Funções com > 100 linhas          | 3              |
| Arquivos com > 500 linhas         | 4              |
| Ocorrências de `except Exception:` silencioso | 18 |
| Usos de `Optional[X]` legado      | 6 (só em models.py) |
| f-strings em `logger.debug()`     | 2              |
| Dead code identificado            | 2 trechos      |
| Débito técnico estimado           | ~12 horas      |

---

## Top 10 Piores Ofensores

### 1. `DetectionEngine.analyze` — Complexidade Ciclomática Alta
- **Arquivo:** `src/veredas/detectors/engine.py:186`
- **Severidade:** ALTO
- **Tamanho:** 128 linhas / CC estimada ~23
- **Problema:** O método orquestra três categorias de detectores (regras, estatístico, ML)
  em um único bloco linear com ~12 condicionais aninhados. Toda a lógica de despacho para
  Isolation Forest e DBSCAN fica embotida junto com feature extraction e consolidação.
- **Impacto:** Dificulta testes unitários, impossibilita adicionar novos detectores sem
  crescer o método, e violação do Princípio da Responsabilidade Única.
- **Sugestão:** Extrair três métodos privados: `_run_rule_detectors()`,
  `_run_statistical_detectors()`, `_run_ml_detectors()`. O método `analyze()` passa a ser
  um orquestrador de ~30 linhas que chama os três e chama `_consolidate_anomalias()`.

---

### 2. `cli/main.py` — God Module (994 linhas)
- **Arquivo:** `src/veredas/cli/main.py`
- **Severidade:** ALTO
- **Problema:** O módulo contém 994 linhas misturando: definições de comandos Typer,
  lógica de persistência de dados (mapeamento de entidades, loop sobre ofertas), formatação
  de saída (CSV/JSON) e lógica de negócio de coleta. As funções `_collect_b3` (93 linhas,
  CC~15), `export` (81 linhas, CC~11), `_exportar_anomalias` (CC~18) e
  `_exportar_taxas` (CC~14) são as principais ofensoras.
- **Impacto:** Acoplamento da CLI com lógica de persistência dificulta reutilização e testes.
  Alterar o schema de exportação exige editar a CLI diretamente.
- **Sugestão:** Criar `src/veredas/services/export_service.py` para as funções
  `_exportar_anomalias`/`_exportar_taxas` e `src/veredas/services/collect_service.py` para
  `_collect_b3`, `_collect_scrapers`, `_collect_ifdata`. A CLI passa a orquestrar chamadas
  a esses serviços.

---

### 3. Tratamento Silencioso de Exceções nos Coletores IFData
- **Arquivo:** `src/veredas/collectors/ifdata.py:186, :228, :268, :277`
- **Severidade:** ALTO
- **Problema:** Quatro blocos `except Exception:` sem log ou reraise. Os mais graves:

  ```python
  # linha 186 — falha na listagem de IFs cai silenciosamente no fallback
  except Exception:
      logger.debug("Falha ao obter lista de IFs da API, usando fallback")

  # linha 228 — f-string com variável em logger.debug (viola PEP 3120/lazy eval)
  except Exception:
      logger.debug(f"Falha ao coletar dados da IF {cnpj}")

  # linha 268 e 277 — parse falha e retorna None sem nenhum diagnóstico
  except Exception:
      return None
  ```

- **Impacto:** Erros de parsing silenciosos tornam impossível distinguir entre "IF não tem
  dados" e "API mudou o formato JSON". Em produção, pode resultar em bancos vazios sem alertas.
- **Sugestão:**
  - Linha 228: mudar para `logger.debug("Falha ao coletar dados da IF %s", cnpj)`.
  - Linhas 268/277: adicionar `logger.debug("_parse_dados_if falhou para %s", cnpj, exc_info=True)`.
  - Linha 186: manter o fallback, mas elevar o nível para `logger.warning`.

---

### 4. Dead Code em `cli/main.py` — `if True:`
- **Arquivo:** `src/veredas/cli/main.py:202`
- **Severidade:** MÉDIO
- **Problema:**
  ```python
  if True:  # Sempre salva no banco padrão
      db = DatabaseManager(db_path)
  ```
  O bloco `if True:` não tem sentido funcional e indica que a lógica de controle foi
  removida sem limpeza adequada.
- **Impacto:** Confunde leitores, sugere que havia uma lógica de branching que foi abandonada.
- **Sugestão:** Remover o `if True:` e dedenter o bloco.

---

### 5. `Optional[X]` Legado em Models — Import Desnecessário
- **Arquivo:** `src/veredas/storage/models.py:14`
- **Severidade:** MÉDIO
- **Problema:** O arquivo importa `Optional` de `typing` na linha 14, mas o projeto já usa
  Python 3.11+ e `X | Y` é a forma moderna. O `Optional` só é usado em 6 anotações de
  relacionamentos SQLAlchemy:
  ```python
  taxa: Mapped[Optional["TaxaCDB"]] = relationship(...)
  instituicao: Mapped[Optional["InstituicaoFinanceira"]] = relationship()
  ```
  O restante do codebase já usa `X | None` corretamente.
- **Impacto:** Inconsistência de estilo, import desnecessário (`F401` de ruff).
- **Sugestão:** Substituir os 6 usos por `"TaxaCDB | None"` e `"InstituicaoFinanceira | None"`,
  remover o import de `Optional`.

---

### 6. `FeatureExtractor._extract_if_features` — Função Longa com Alta Complexidade
- **Arquivo:** `src/veredas/detectors/features.py:251`
- **Severidade:** MÉDIO
- **Tamanho:** 118 linhas / CC estimada ~17
- **Problema:** A função acumula quatro responsabilidades: cálculo de rolling stats, cálculo
  de diffs, cálculo de z-scores locais e construção do objeto `TaxaFeatures`. O loop interno
  (`for i, taxa in enumerate(taxas)`) roda lógica de fim-de-mês com cálculo de `next_month`
  que poderia ser uma função pura separada.
- **Impacto:** Difícil de testar as partes individualmente; futuras features exigem crescer
  ainda mais a função.
- **Sugestão:** Extrair `_calcular_fim_de_mes(date) -> bool` e `_calcular_zscores(value,
  mean, std) -> float | None` como funções de módulo. O loop principal fica com ~40 linhas.

---

### 7. `TTLCache` em `web/cache.py` — Cache Não Thread-Safe para Asyncio
- **Arquivo:** `src/veredas/web/cache.py:16`
- **Severidade:** MÉDIO
- **Problema:** O `TTLCache` usa dois dicionários separados (`_cache` e `_timestamps`) e
  o método `get()` realiza deleção condicional fora de lock. Em contexto assíncrono (FastAPI
  com múltiplas corrotinas concorrentes), a sequência `if key not in self._cache` → `del`
  pode gerar `KeyError` por race condition, pois não há `asyncio.Lock`. O estado
  `_reference_cache` e `_counter_cache` são módulos globais mutáveis.
- **Impacto:** Em carga moderada com múltiplas requisições simultâneas, o cache pode lançar
  `KeyError` não tratado, derrubando a requisição.
- **Sugestão:** Usar `functools.lru_cache` com wrapper para TTL, ou adicionar
  `asyncio.Lock` ao `TTLCache`. Como alternativa mínima, refatorar `get()` para usar
  `.pop()` em vez de `del` combinado com verificação prévia:
  ```python
  expired = self._timestamps.pop(key, None)
  if expired and datetime.now() - expired > self._default_ttl:
      self._cache.pop(key, None)
      return None
  ```

---

### 8. `AlertManager._should_alert` — Comparação de Severity via String em vez de Enum
- **Arquivo:** `src/veredas/alerts/manager.py:87`
- **Severidade:** MÉDIO
- **Problema:**
  ```python
  severity_order = ["LOW", "MEDIUM", "HIGH", "CRITICAL"]
  min_idx = severity_order.index(self.min_severity.upper())
  anomalia_idx = severity_order.index(anomalia.severidade.upper())
  ```
  O projeto já tem o enum `Severidade` com `StrEnum`. O `_should_alert` re-implementa
  a ordenação manualmente via lista de strings, ignorando o enum existente e o
  `SEVERITY_ORDER` já definido em `detectors/engine.py:34`. Se uma string inválida
  for passada, `list.index()` lança `ValueError` que é suprimido por `except ValueError: pass`.
- **Impacto:** A supressão silenciosa do `ValueError` (linha 107) significa que uma
  severidade inválida em `min_severity` faz o sistema alertar para *tudo* sem aviso.
  Além disso, há duplicação de lógica com `SEVERITY_ORDER` do engine.
- **Sugestão:** Importar `SEVERITY_ORDER` de `detectors/engine.py` (ou movê-lo para um módulo
  compartilhado) e usar `Severidade(self.min_severity)` com tratamento explícito de `ValueError`.

---

### 9. Duplicação de Lógica de Filtro em Repository — `list_paginated` e `count_with_filters`
- **Arquivo:** `src/veredas/storage/repository.py:245` e `:462`
- **Severidade:** MÉDIO
- **Problema:** As classes `TaxaCDBRepository` e `AnomaliaRepository` têm pares
  `list_paginated`/`count_with_filters` (e `list_with_filters`) que duplicam exatamente
  os mesmos blocos `if "indexador" in filters: stmt = stmt.where(...)`. Para `TaxaCDB`,
  5 filtros são aplicados nos dois lugares. Para `Anomalia`, 4 filtros são duplicados.
  O `TaxaCDBRepository.list_paginated` (CC~13, 51 linhas) aplica a mesma condição de
  `order_by == "spread_desc"` e `order_by == "taxa_desc"` com lógica idêntica (`desc(TaxaCDB.percentual)`).
- **Impacto:** Adicionar um novo filtro exige editar dois métodos por repositório; risco de
  inconsistência entre `list` e `count` quando um é atualizado e o outro não.
- **Sugestão:** Extrair `_build_taxa_query(filters) -> Select` e `_build_anomalia_query(filters) -> Select`
  que retornam a query base com todos os filtros aplicados. `list_paginated` e `count_with_filters`
  chamam essas funções antes de aplicar ordenação/paginação/count.

---

### 10. `config.py` — Duplicação de Campos entre `Settings` e `AlertSettings`
- **Arquivo:** `src/veredas/config.py:241`
- **Severidade:** BAIXO
- **Problema:** A classe `Settings` duplica explicitamente todos os campos de `AlertSettings`
  (linhas 275–283: `smtp_host`, `smtp_port`, `smtp_user`, etc.) com comentário
  `# Alertas (campos diretos para facilitar acesso)`. `AlertSettings` existe mas não é usada
  como sub-configuração de `Settings`, tornando-a uma classe órfã. O resultado é que os
  mesmos campos são declarados duas vezes com os mesmos defaults, criando possibilidade de
  divergência futura.
- **Sugestão:** Ou remover `AlertSettings` e mantê-la apenas dentro de `Settings`, ou
  adicionar `alerts: AlertSettings = Field(default_factory=AlertSettings)` como sub-objeto
  e remover os campos duplicados de `Settings`. O `AlertManager` acessaria
  `settings.alerts.smtp_host` em vez de `settings.smtp_host`.

---

## Code Smells Adicionais

### Erros Silenciosos em Coletores (BCB e B3)

- `src/veredas/collectors/bcb.py:166` — `_collect_serie`: `except Exception: return None`
  sem log. A coleta de CDI/Selic/IPCA pode falhar silenciosamente.
- `src/veredas/collectors/bcb.py:274, :293, :309, :325` — `get_selic_atual()`,
  `get_cdi_atual()`, `get_ipca_atual()`: `except Exception: return None` sem log nenhum.
  Em produção, impossível distinguir se o BCB está fora do ar ou se houve erro de parsing.
- `src/veredas/collectors/b3/collector.py:122` — `health_check`: `except Exception: return False`.
  Aceitável para health checks, mas a exceção deveria ser logada em `DEBUG`.

### f-string em Chamadas de Logger

- `src/veredas/collectors/ifdata.py:229` — `logger.debug(f"Falha ao coletar dados da IF {cnpj}")`.
  f-strings em `logger` forçam interpolação da string mesmo quando o nível de log está
  desabilitado. Custo pequeno, mas viola a prática padrão de lazy evaluation.
  Substituir por: `logger.debug("Falha ao coletar dados da IF %s", cnpj)`.
- `src/veredas/collectors/scheduler.py:334, :343, :358` — mesma situação com f-strings.

### `datetime.now()` Naive em Detectores

- `src/veredas/detectors/rules.py:85`, `src/veredas/detectors/statistical.py:146, :338, :497`,
  `src/veredas/detectors/ml.py:112, :302` — todos usam `datetime.now()` sem timezone para
  medir tempo de execução dos detectores (elapsed time). Isso é harmless para medição de
  latência, mas inconsistente com o restante do projeto, que usa `datetime.now(TZ_BRASIL)`.
- `src/veredas/alerts/manager.py:114, :115, :175` — `datetime.now()` no gerenciador de
  cooldown: se o sistema for executado em servidor com timezone diferente de `America/Sao_Paulo`,
  o cooldown pode ser calculado incorretamente.

### `DatabaseManager.db_path` — Tipo Misto Path/str sem Normalização

- `src/veredas/storage/database.py:83` — `self.db_path = db_path or DEFAULT_DB_PATH`.
  O construtor aceita `Path | str | None` mas atribui direto. Chamadores que passam `str`
  podem ter surpresas ao chamar `db.db_path.exists()` (funciona) ou `db.db_path.stat()`
  (funciona), mas `db.db_path / "subdir"` só funciona com `Path`. Adicionalmente,
  `cli/main.py:987` chama `db.db_path.stat().st_size` — que funciona mesmo com `str`
  em Python, mas poderia lançar `AttributeError` para paths None.
  Correção: `self.db_path = Path(db_path) if db_path else DEFAULT_DB_PATH`.

### `_DBSCAN.dbscan_metric` sem Anotação de Tipo Literal

- `src/veredas/detectors/ml.py:56` — `dbscan_metric: str = "euclidean"`.
  O campo deveria ser `Literal["euclidean", "cosine", "manhattan"]` para garantir que
  apenas métricas válidas sejam aceitas. Atualmente, passar `dbscan_metric="invalido"` só
  falharia em runtime dentro do `DBSCAN()` do sklearn, sem mensagem clara.

### `B3Parser._parse_data_pregao` e `_parse_date` — Código Duplicado

- `src/veredas/collectors/b3/parser.py:111` e `:119` — dois métodos estáticos com
  implementações idênticas (mesmo corpo, mesma assinatura `(s: str) -> date | None`).
  `_parse_data_pregao` poderia simplesmente chamar `_parse_date`.

### `config.py` — `settings = get_settings()` em Nível de Módulo

- `src/veredas/config.py:306` — `settings = get_settings()` executado no import do módulo.
  Isso significa que, na primeira vez que qualquer módulo importar `from veredas.config import settings`,
  as variáveis de ambiente já devem estar definidas. Em testes, isso pode causar problemas se
  o ambiente não estiver completamente configurado. A instância `settings` em nível de módulo
  também não pode ser "resetada" entre testes sem trabalho extra.
  Sugestão: remover o atalho `settings = get_settings()` do módulo e fazer chamadores usarem
  a função `get_settings()` diretamente (já protegida por `@lru_cache`).

---

## Oportunidades de Refatoração de Alto Impacto

### 1. Extrair `_run_*_detectors()` de `DetectionEngine.analyze`
**Benefício:** Reduz o método mais complexo do projeto de CC~23 para ~5. Cada categoria
de detectores pode ser testada isoladamente. Adicionar um novo detector de regras
deixa de exigir editar um método de 128 linhas.

### 2. Criar `ExportService` para isolar lógica de CSV/JSON da CLI
**Benefício:** A lógica de serialização de `Anomalia` e `TaxaCDB` para CSV/JSON existe
hoje em quatro lugares (`cli/main.py:724`, `cli/main.py:784`, `web/routes/anomalias.py:142`,
`web/routes/taxas.py:124`). Centralizar num serviço elimina a duplicação e facilita
adicionar novos formatos (Excel, Parquet) sem tocar em múltiplos módulos.

### 3. `_build_query(filters)` para Repositórios
**Benefício:** Elimina a duplicação de lógica de filtro entre `list_*` e `count_*`.
Garante que `list` e `count` sempre retornem resultados consistentes para os mesmos filtros.

### 4. Adicionar Lock ao `TTLCache`
**Benefício:** Elimina potencial `KeyError` em produção sob carga. A implementação é
trivial (`asyncio.Lock` no `get`/`set`) e não afeta performance na ausência de contenção.

### 5. Consolidar `SEVERITY_ORDER` em Módulo Compartilhado
**Benefício:** Atualmente a ordem de severidade é replicada como lista de strings em
`alerts/manager.py:95` e como `SEVERITY_ORDER` em `detectors/engine.py:34`. Centralizar
em `storage/models.py` (junto com o enum `Severidade`) elimina a divergência potencial.

---

## Achados Positivos

- **Arquitetura modular bem executada:** a separação `collectors / detectors / storage /
  web / cli / alerts` respeita responsabilidades distintas. `catalog.py` é puro (sem imports
  de outros módulos do projeto), eliminando risco de import circular.

- **SQLAlchemy 2.x idiomático:** uso de `Mapped[X]`, `mapped_column`, `DeclarativeBase`,
  `selectinload` para evitar N+1. Repositórios explícitos com `session_scope()` como context
  manager previnem sessions perdidas.

- **Configuração centralizada com pydantic-settings:** thresholds de detecção todos
  configuráveis via variáveis de ambiente (`VEREDAS_*`), com defaults bem documentados.
  `@lru_cache` em `get_settings()` garante singleton sem singleton explícito.

- **Tratamento correto de opcional nas interfaces públicas:** todo o codebase novo usa
  `X | None` e `X | Y` (Python 3.10+ union syntax). Apenas `models.py` tem os 6 resquícios
  de `Optional` — facilmente corrigíveis.

- **Segurança web bem implementada:** CSRF (double-submit cookie), Rate Limiting por IP com
  cleanup automático, Security Headers (X-Frame-Options, CSP prep, HSTS-ready). A proteção
  de tempo constante em `secrets.compare_digest` no CSRF está correta.

- **Context managers assíncronos:** todos os coletores implementam `__aenter__`/`__aexit__`
  evitando resource leaks de `httpx.AsyncClient` e clientes Playwright.

- **Constantes nomeadas em vez de magic numbers:** thresholds como `Decimal("130")`,
  `Decimal("10.5")`, `_DIAS_POR_MES = 30` são nomeados e comentados com suas origens
  regulatórias. `TIER_SPREAD_THRESHOLDS` em `catalog.py` é especialmente bem documentado.

- **Logging configurado corretamente no nível de módulo:** `logger = logging.getLogger(__name__)`
  em todos os módulos relevantes. O uso de `logger.exception()` em `detectors/ml.py:207`
  para capturar stacktrace é a prática correta.

- **Deduplicação de anomalias implementada:** `DetectionEngine._deduplicate` evita que
  múltiplos detectores gerem ruído ao detectar a mesma anomalia. A lógica de `_consolidate_anomalias`
  com filtro por severidade mínima é bem pensada.

- **Cobertura de testes presente:** 16 arquivos de teste existem, cobrindo `unit/detectors`,
  `unit/storage`, `unit/collectors` e `integration`. A configuração de pytest com `asyncio_mode = auto`
  e `--cov` está correta.

---

## Recomendações Priorizadas

| Prioridade | Ação                                                                 | Esforço |
|------------|----------------------------------------------------------------------|---------|
| P1 ALTO    | Extrair `_run_*_detectors()` em `DetectionEngine.analyze`            | 1h      |
| P1 ALTO    | Adicionar logs a bare `except Exception:` em `ifdata.py`             | 0.5h    |
| P1 ALTO    | Adicionar `asyncio.Lock` ao `TTLCache`                               | 0.5h    |
| P2 MÉDIO   | Criar `ExportService` e mover lógica CSV/JSON para fora da CLI       | 3h      |
| P2 MÉDIO   | Extrair `_build_query(filters)` nos repositórios (remove duplicação) | 2h      |
| P2 MÉDIO   | Corrigir `Optional[X]` para `X | None` em `models.py`               | 0.5h    |
| P2 MÉDIO   | Remover `if True:` em `cli/main.py:202`                              | 5min    |
| P2 MÉDIO   | Corrigir f-strings em `logger.debug` para lazy `%s`                  | 0.5h    |
| P3 BAIXO   | Normalizar `db_path` para `Path` em `DatabaseManager.__init__`      | 0.5h    |
| P3 BAIXO   | Consolidar `SEVERITY_ORDER` em `storage/models.py`                  | 0.5h    |
| P3 BAIXO   | Unificar `_parse_data_pregao` e `_parse_date` em `b3/parser.py`     | 0.25h   |
| P3 BAIXO   | Remover `settings = get_settings()` de nível de módulo em `config.py` | 0.5h  |
| P3 BAIXO   | Adicionar `Literal[...]` ao tipo de `dbscan_metric`                  | 0.25h   |
| P3 BAIXO   | Adicionar `datetime.now(TZ_BRASIL)` no cooldown de `AlertManager`   | 0.5h    |

**Débito técnico total estimado: ~12 horas**

---

*Relatório gerado por análise estática com leitura integral dos 57 arquivos Python do projeto.*
