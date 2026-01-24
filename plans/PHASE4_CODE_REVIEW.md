# Code Review - Fase 4: Expansao de Fontes

**Projeto:** veredas-de-papel
**Data:** 2026-01-24
**Revisores:** Multi-agent review (code-reviewer, security-reviewer, manual)
**Status:** BLOCK - Issues criticos encontrados

---

## Sumario Executivo

| Severidade | Quantidade | Acao Necessaria |
|------------|------------|-----------------|
| CRITICAL   | 7          | Corrigir antes de deploy |
| HIGH       | 12         | Corrigir antes de merge |
| MEDIUM     | 15         | Recomendado corrigir |
| LOW        | 10         | Melhorias opcionais |

**Veredicto:** O codigo nao deve ir para producao ate que os issues CRITICAL e HIGH sejam resolvidos.

---

## CRITICAL Issues

### [C1] Race Condition em `BaseScraper._get_client()`

**Arquivo:** `src/veredas/collectors/scrapers/base.py:130-138`

**Problema:** Multiplas corrotinas chamando `_get_client()` simultaneamente podem criar multiplos clientes, causando leak de recursos.

```python
async def _get_client(self) -> httpx.AsyncClient:
    if self._client is None or self._client.is_closed:  # Check
        self._client = httpx.AsyncClient(...)  # Set - RACE CONDITION
    return self._client
```

**Correcao:**
```python
def __init__(self, ...):
    self._client_lock = asyncio.Lock()

async def _get_client(self) -> httpx.AsyncClient:
    async with self._client_lock:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(...)
        return self._client
```

**Impacto:** Resource leak, conexoes orfas, memoria crescente em producao.

---

### [C2] Race Condition em `SessionManager.get_client()`

**Arquivo:** `src/veredas/collectors/scrapers/anti_bot.py:223-234`

**Problema:** Mesmo padrao de race condition do C1.

**Correcao:** Adicionar asyncio.Lock similar ao C1.

---

### [C3] Race Condition em `RateLimiter.wait()`

**Arquivo:** `src/veredas/collectors/scrapers/anti_bot.py:87-127`

**Problema:** Rate limiter nao e thread-safe. Multiplas corrotinas podem ler `_last_request`, calcular wait time, e todas prosseguem simultaneamente.

```python
async def wait(self) -> None:
    now = time.time()
    elapsed = now - self._last_request  # Read
    if elapsed < self.current_delay:
        await asyncio.sleep(self.current_delay - elapsed)
    self._last_request = time.time()  # Write - RACE CONDITION
```

**Correcao:**
```python
@dataclass
class RateLimiter:
    _lock: asyncio.Lock = field(default_factory=asyncio.Lock, init=False)

    async def wait(self) -> None:
        async with self._lock:
            now = time.time()
            elapsed = now - self._last_request
            if elapsed < self.current_delay:
                await asyncio.sleep(self.current_delay - elapsed)
            self._last_request = time.time()
```

---

### [C4] Race Condition em `B3MarketDataCollector._get_client()`

**Arquivo:** `src/veredas/collectors/b3/api.py:77-90`

**Problema:** Mesmo padrao de race condition dos anteriores.

**Correcao:** Adicionar asyncio.Lock.

---

### [C5] Divisao por Zero em `SinalReclameAqui.calcular_score()`

**Arquivo:** `src/veredas/collectors/sentiment/aggregator.py:63`

**Problema:** Nao valida que `reclamacoes_30d` pode ser negativo ou causar problemas em edge cases.

```python
score_volume = min(100, self.reclamacoes_30d / 10)
```

**Correcao:**
```python
def calcular_score(self) -> float:
    if self.reclamacoes_30d < 0:
        self.reclamacoes_30d = 0
    score_nota = (10 - max(0, min(10, float(self.nota_geral)))) * 10
    score_solucao = 100 - max(0, min(100, float(self.indice_solucao)))
    score_volume = min(100.0, self.reclamacoes_30d / 10.0)
```

---

### [C6] JSON Response Parsing Sem Validacao

**Arquivo:** `src/veredas/collectors/alternative/bacen_processos.py:313-315`

**Problema:** API response nao e validada antes de acessar keys. Mudanca de formato da API causa falha silenciosa.

```python
if response.status_code == 200:
    data = response.json()
    items = data.get("value", [])  # Nao valida que 'data' e dict
```

**Correcao:**
```python
if response.status_code == 200:
    try:
        data = response.json()
        if not isinstance(data, dict):
            logger.warning(f"Formato inesperado da API")
            return processos
        items = data.get("value", [])
        if not isinstance(items, list):
            logger.warning(f"Campo 'value' nao e lista")
            return processos
    except json.JSONDecodeError as e:
        logger.error(f"JSON invalido: {e}")
        return processos
```

---

### [C7] Type Mismatch Decimal/Float em f-string

**Arquivo:** `src/veredas/collectors/sentiment/aggregator.py:342`

**Problema:** Mixing Decimal e float em formatacao pode causar erros.

```python
fatores.append(f"Multas significativas (R$ {processos_bc.valor_total_multas:,.2f})")
```

**Correcao:**
```python
fatores.append(f"Multas significativas (R$ {float(processos_bc.valor_total_multas):,.2f})")
```

---

## HIGH Issues

### [H1] Resource Leak - HTTP Client em Excecoes

**Arquivo:** `src/veredas/collectors/scrapers/base.py:152-206`

**Problema:** Se `_fetch_with_retry` lanca excecao apos criar o client, recursos nao sao liberados.

**Correcao:** Implementar `__aenter__` e `__aexit__` para context manager pattern.

---

### [H2] ProxyRotator Nao Thread-Safe

**Arquivo:** `src/veredas/collectors/scrapers/anti_bot.py:130-176`

**Problema:** `_current_index`, `_failed` set, e `_proxies` acessados sem sincronizacao.

**Correcao:** Adicionar threading.Lock ou asyncio.Lock.

---

### [H3] Proxy List Vazia Nao Tratada

**Arquivo:** `src/veredas/collectors/scrapers/anti_bot.py:148-167`

**Problema:** Se inicializado com lista vazia, `get_next()` retorna None sem aviso.

**Correcao:**
```python
def __init__(self, proxies: list[ProxyConfig]):
    if not proxies:
        raise ValueError("ProxyRotator requer ao menos um proxy")
    self._proxies = list(proxies)
```

---

### [H4] CNPJ Placeholder Invalido

**Arquivo:** `src/veredas/collectors/scrapers/normalizer.py:297-299`

**Problema:** CNPJ placeholder `"00.000.000/0000-00"` tem formato invalido (digito verificador errado).

**Correcao:** Usar CNPJ conhecido ou tornar campo nullable.

---

### [H5] ReDoS Vulnerability em Regex

**Arquivo:** `src/veredas/collectors/scrapers/brokers/xp.py:123-127`

**Problema:** Patterns `.*?` com `re.DOTALL` podem causar catastrophic backtracking em HTML malformado.

```python
patterns = [
    r'window\.__INITIAL_STATE__\s*=\s*({.*?});',  # Potential ReDoS
]
```

**Correcao:** Adicionar timeout ou usar patterns mais especificos.

---

### [H6] Lexicon de Sentimento Incompleto

**Arquivo:** `src/veredas/collectors/sentiment/analyzer.py:93-122`

**Problema:** Muitas palavras comuns de reclamacao/elogio em portugues nao estao incluidas.

**Palavras faltando:**
- Negativas: "lixo", "vergonha", "absurdo", "descaso", "enganacao", "mentira", "roubo"
- Positivas: "otimista", "sucesso", "conquista", "beneficio"

---

### [H7] Janela de Negacao Muito Curta

**Arquivo:** `src/veredas/collectors/sentiment/analyzer.py:291-317`

**Problema:** Negacao afeta apenas palavra seguinte. Em portugues, negacao afeta multiplas palavras ("nao foi nada bom" - negacao deveria afetar "bom", nao apenas "foi").

**Correcao:** Implementar janela de negacao de 3 palavras.

---

### [H8] CNPJ Hardcoded em Multiplos Arquivos

**Arquivos:**
- `reclame_aqui.py:111-125`
- `bacen_processos.py:209-219`
- `analyzer.py:150-169`

**Problema:** CNPJs duplicados em varios arquivos, criando burden de manutencao e risco de inconsistencia.

**Correcao:** Centralizar mapeamentos em arquivo de configuracao unico.

---

### [H9] Signal Aggregation - Sem Dados = Risco Baixo

**Arquivo:** `src/veredas/collectors/sentiment/aggregator.py:371-382`

**Problema:** Quando nenhum sinal e fornecido, `score_consolidado` fica 0 e `nivel_risco` e BAIXO. Ausencia de dados nao deveria significar baixo risco.

**Correcao:**
```python
if scores:
    # ... calculo normal
else:
    signal.score_consolidado = 50.0  # Neutro
    signal.confianca = 0.0
    signal.fatores_risco.append("Dados insuficientes para avaliacao")
```

---

### [H10] Tendencia Nunca Calculada em SentimentoAgregado

**Arquivo:** `src/veredas/collectors/sentiment/analyzer.py:464-476`

**Problema:** Campo `tendencia` sempre default "ESTAVEL", nunca calculado de fato.

**Correcao:** Calcular tendencia comparando primeira metade vs segunda metade dos dados ordenados por tempo.

---

### [H11] Detectors Nao Medem Tempo de Execucao

**Arquivos:** `platform_discrepancy.py:120-125`, `price_drop.py:123-128`

**Problema:** `execution_time_ms` sempre 0, nao medido de fato.

**Correcao:** Medir tempo como em `sentiment_risk.py:132`.

---

### [H12] B3 Calendario de Feriados Ausente

**Arquivo:** `src/veredas/collectors/b3/api.py:341-345`

**Problema:** TODO nao implementado - calendario de feriados ausente pode causar tentativas de coleta em dias sem dados.

---

## MEDIUM Issues

### [M1] Memory Leak - TaxaNormalizer `_seen` Set

**Arquivo:** `src/veredas/collectors/scrapers/normalizer.py:230, 260-262`

**Problema:** Set `_seen` cresce indefinidamente se instancia e reutilizada.

**Correcao:** Adicionar limite maximo ou TTL.

---

### [M2] MD5 Usado para Session ID

**Arquivo:** `src/veredas/collectors/scrapers/anti_bot.py:202-204`

**Problema:** MD5 e deprecated, embora aqui seja apenas para unicidade.

**Correcao:** Usar `secrets.token_hex(4)`.

---

### [M3] Sem Retry em Erros 5xx

**Arquivo:** `src/veredas/collectors/scrapers/base.py:193-200`

**Problema:** Retry logic trata 429 mas nao 5xx (erros de servidor), que sao tipicamente transientes.

---

### [M4] Import Dentro de Funcao

**Arquivo:** `src/veredas/collectors/scrapers/base.py:333`

**Problema:** `import re` feito dentro de `_parse_prazo()`, chamado repetidamente.

**Correcao:** Mover import para topo do arquivo.

---

### [M5] Logging Inconsistente

**Arquivos:** Multiplos

**Problema:** Alguns metodos usam `logger.exception()`, outros `logger.debug()` para erros similares.

---

### [M6] Date Parsing Falha Silenciosamente

**Arquivo:** `src/veredas/collectors/alternative/bacen_processos.py:465-483`

**Problema:** `_parse_data` retorna None sem logging quando parse falha.

---

### [M7] Normalizacao de Weights Inconsistente

**Arquivo:** `src/veredas/collectors/sentiment/aggregator.py:278-281`

**Problema:** Se todos weights sao 0, divisao por zero ocorre.

---

### [M8] Enum Value Mismatch Risk

**Arquivo:** `src/veredas/collectors/sentiment/aggregator.py:182-186`

**Problema:** `tendencia` tipado como `str` mas comparado contra strings literais.

---

### [M9] Async Resource Cleanup

**Arquivo:** `src/veredas/collectors/alternative/reclame_aqui.py:148-187`

**Problema:** Excecao entre criar client e finally pode causar leak.

---

### [M10] Magic Numbers

**Arquivos:** Multiplos

**Problema:** Numeros como `10`, `50`, `365`, `1_000_000` hardcoded sem constantes nomeadas.

---

### [M11] MOCK_DATA Nao Usados

**Arquivos:** Todos os scrapers de brokers

**Problema:** Constantes `MOCK_DATA` definidas mas nunca usadas.

---

### [M12] Type Hints Faltando

**Arquivo:** `src/veredas/collectors/scrapers/brokers/__init__.py:38, 58`

**Problema:** `get_scraper` e `get_all_scrapers` sem return type hints.

---

### [M13] PriceDropDetector - Valor Nominal Hardcoded

**Arquivo:** `src/veredas/detectors/price_drop.py:141`

**Problema:** Valor nominal R$ 1000 hardcoded. Alguns CDBs podem ter valor nominal diferente.

---

### [M14] Context Manager Pattern Ausente

**Arquivo:** `src/veredas/collectors/scrapers/base.py`

**Problema:** `BaseScraper` deveria implementar `__aenter__` e `__aexit__`.

---

### [M15] Prazo Normalization Gaps

**Arquivo:** `src/veredas/detectors/platform_discrepancy.py:150-163`

**Problema:** Faixas de prazo tem gaps (ex: 46-89 dias nao mapeados claramente).

---

## LOW Issues

### [L1] User Agent Strings Desatualizados

Chrome 120 pode ficar desatualizado, tornando scraping mais detectavel.

### [L2] Docstrings Faltando em Properties

`taxa_resposta`, `reputacao_ruim` em `reclame_aqui.py` sem docstrings.

### [L3] Rate Limiting Nao Configuravel

Delay de 2.0s hardcoded em varios coletores.

### [L4] Timeout Nao Configuravel em Detectors

Sem configuracao de timeout para deteccao.

### [L5] Decimal Precision Inconsistente

Alguns lugares usam `round(float(...), 2)`, outros nao arredondam.

### [L6] Empty List Handling

Varios metodos nao tratam explicitamente listas vazias.

### [L7] Exception Messages Genericas

Mensagens de erro poderiam ser mais especificas.

### [L8] No Connection Pooling

Cada request cria nova conexao, poderia usar pooling.

### [L9] Falta Retry Configuration

`max_retries` hardcoded em varios lugares.

### [L10] Log Levels Inconsistentes

DEBUG vs WARNING vs ERROR usados inconsistentemente.

---

## Security Findings

### [S1] SSRF Potencial

**Arquivos:** Todos os scrapers/coletores

**Problema:** URLs externas processadas sem validacao. Se usuario puder injetar URL, SSRF e possivel.

**Mitigacao:** Validar URLs contra whitelist de dominios permitidos.

### [S2] Secrets em Logs

**Potencial:** Logs podem conter dados sensiveis (CNPJs, proxies com credenciais).

**Mitigacao:** Sanitizar logs, nao logar credenciais.

### [S3] Certificate Validation

**Arquivo:** httpx clients criados sem configuracao explicita de SSL.

**Status:** httpx valida certificados por default, OK.

### [S4] Input Validation

**Problema:** Dados de APIs externas nao sao completamente validados antes de uso.

**Mitigacao:** Adicionar validacao com Pydantic ou similar.

---

## Recomendacoes de Otimizacao

### Performance

1. **Connection Pooling:** Usar pool de conexoes em vez de criar nova conexao por request
2. **Batch Processing:** Agrupar multiplos requests quando possivel
3. **Caching:** Cache de dados de referencia (CNPJs, taxas historicas)
4. **Async Batching:** Usar `asyncio.gather()` para requests paralelos

### Code Quality

1. **Centralizar Configuracoes:** Mover todos CNPJs/thresholds para arquivo de config
2. **Type Safety:** Adicionar type hints completos e usar mypy
3. **Error Handling:** Padronizar tratamento de erros
4. **Testing:** Adicionar testes para race conditions e edge cases

### Maintainability

1. **Extract Constants:** Todos magic numbers devem virar constantes nomeadas
2. **DRY:** Remover duplicacao de codigo entre scrapers
3. **Documentation:** Adicionar docstrings para todos metodos publicos

---

## Plano de Acao

### Fase 1 - CRITICAL (Antes de Deploy)

1. [ ] Adicionar locks para race conditions (C1, C2, C3, C4)
2. [ ] Corrigir validacao de JSON responses (C6)
3. [ ] Corrigir divisao por zero em scores (C5)
4. [ ] Corrigir type mismatch Decimal/float (C7)

### Fase 2 - HIGH (Antes de Merge)

1. [ ] Implementar context manager para cleanup (H1)
2. [ ] Corrigir ProxyRotator thread-safety (H2, H3)
3. [ ] Corrigir CNPJ placeholder (H4)
4. [ ] Mitigar ReDoS (H5)
5. [ ] Expandir lexicon de sentimento (H6, H7)
6. [ ] Centralizar CNPJs (H8)
7. [ ] Corrigir signal aggregation edge case (H9)
8. [ ] Implementar calculo de tendencia (H10)
9. [ ] Medir tempo de execucao em todos detectors (H11)

### Fase 3 - MEDIUM (Sprint Seguinte)

1. [ ] Corrigir memory leak em normalizer (M1)
2. [ ] Substituir MD5 por secrets (M2)
3. [ ] Adicionar retry para 5xx (M3)
4. [ ] Mover imports para topo (M4)
5. [ ] Padronizar logging (M5)
6. [ ] Adicionar context managers (M14)

---

## Metricas de Qualidade

```
Arquivos Revisados: 24
Linhas de Codigo: ~9,653
Cobertura de Testes: 325 testes passando
Issues Encontrados: 44 total
  - CRITICAL: 7 (15.9%)
  - HIGH: 12 (27.3%)
  - MEDIUM: 15 (34.1%)
  - LOW: 10 (22.7%)
```

---

## Testes Adicionais Necessarios

### Testes de Concorrencia
```python
# Teste para race condition em _get_client
async def test_get_client_concurrent_access():
    scraper = XPScraper()
    clients = await asyncio.gather(*[scraper._get_client() for _ in range(10)])
    # Todos devem ser o mesmo cliente
    assert all(c is clients[0] for c in clients)

# Teste para RateLimiter sob carga
async def test_rate_limiter_concurrent():
    limiter = RateLimiter(min_delay=0.1)
    start = time.time()
    await asyncio.gather(*[limiter.wait() for _ in range(5)])
    elapsed = time.time() - start
    # Deve respeitar delays mesmo com chamadas concorrentes
    assert elapsed >= 0.4
```

### Testes de Edge Cases
```python
# Score com valores extremos
def test_score_edge_cases():
    sinal = SinalReclameAqui(
        nota_geral=Decimal("-5"),  # Valor invalido
        indice_solucao=Decimal("200"),  # Acima do maximo
        reclamacoes_30d=-10,  # Negativo
    )
    score = sinal.calcular_score()
    assert 0 <= score <= 100

# Aggregation sem sinais
def test_aggregation_no_signals():
    aggregator = SignalAggregator()
    signal = aggregator.agregar("123", "Banco X")
    assert signal.confianca == 0.0
    assert signal.nivel_risco != NivelRisco.BAIXO
```

---

## Dependencias com Vulnerabilidades Conhecidas

Execute `pip audit` regularmente para verificar vulnerabilidades:

```bash
pip install pip-audit
pip-audit
```

---

## Checklist Pre-Merge

- [ ] Todos issues CRITICAL corrigidos
- [ ] Todos issues HIGH corrigidos ou com ticket criado
- [ ] Testes de concorrencia adicionados
- [ ] Testes de edge cases adicionados
- [ ] Code coverage >= 80%
- [ ] Nenhum secret hardcoded
- [ ] Documentacao atualizada
- [ ] Changelog atualizado

---

**Assinatura:** Multi-agent Code Review System (Claude Opus 4.5)
**Versao:** Phase 4 - Commit 86aaaea
**Agentes Utilizados:** code-reviewer, security-reviewer, manual review
