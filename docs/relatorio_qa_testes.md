# Relatório de QA — Cobertura e Qualidade de Testes

**Projeto:** veredas-de-papel  
**Data da análise:** 2026-04-24  
**Analista:** QA Sênior (Claude Sonnet 4.6)  
**Suite atual:** 187 testes passando, 1 skip  
**Cobertura global:** 43% (statements), com cobertura de branches em 1034 ramos

---

## 1. Sumário Executivo

O projeto possui uma base de testes bem estruturada para os módulos centrais (detectores, repositórios, parsers), mas apresenta cobertura zero em módulos críticos de negócio — em especial a camada de alertas, análise de saúde financeira, coletor BCB, scrapers e o CLI completo. A cobertura de 43% é imprecisa para a avaliação de risco: os 57% não cobertos concentram-se nos caminhos de maior criticidade operacional.

---

## 2. Mapeamento de Arquivos de Teste

| Arquivo de Teste | Tipo | Módulo Coberto | Nº de Testes |
|---|---|---|---|
| `tests/conftest.py` | Fixtures | Fábrica global (`make_taxa`, `make_taxa_serie`) | — |
| `tests/unit/detectors/test_rules.py` | Unit | `detectors/rules.py` (Spread, Variação, Divergência) | 23 |
| `tests/unit/detectors/test_statistical.py` | Unit | `detectors/statistical.py` (Rolling Z-Score, STL, ChangePoint) | 10 |
| `tests/unit/detectors/test_ml.py` | Unit | `detectors/ml.py` (IsolationForest, DBSCAN) | 8 |
| `tests/unit/storage/test_repository.py` | Unit/Integração | `storage/repository.py` (4 repositórios) | 27 |
| `tests/unit/collectors/test_scraper_base.py` | Unit | `collectors/scraper_base.py` | 15 |
| `tests/unit/collectors/test_normalize.py` | Unit | `collectors/scrapers/normalize.py` | 40 |
| `tests/unit/test_catalog.py` | Unit | `catalog.py` | 22 |
| `tests/integration/test_pipeline.py` | Integração | `detectors/engine.py` | 13 |
| `tests/integration/test_web_routes.py` | Integração HTTP | `web/routes/*.py` (smoke tests) | 12 |

---

## 3. Cobertura por Módulo (Tabela Detalhada)

### 3.1 Módulos com boa cobertura (>= 80%)

| Módulo | Statements | Miss | Cobertura | Observação |
|---|---|---|---|---|
| `catalog.py` | 34 | 0 | 100% | Lookup de tiers — bem testado |
| `collectors/scraper_base.py` | 72 | 1 | 98% | Retry, rate limit, headers |
| `collectors/scrapers/normalize.py` | 87 | 9 | 89% | parse_taxa, parse_prazo, CNPJ |
| `detectors/rules.py` | 141 | 11 | 91% | SpreadDetector, VariacaoDetector |
| `storage/models.py` | 302 | 14 | 95% | Modelos ORM |
| `detectors/statistical.py` | 212 | 36 | 82% | Rolling Z-Score, STL |
| `detectors/features.py` | 138 | 20 | 82% | FeatureExtractor |
| `detectors/ml.py` | 164 | 38 | 74% | IsolationForest, DBSCAN |
| `detectors/engine.py` | 170 | 24 | 79% | DetectionEngine |
| `web/app.py` | 58 | 2 | 97% | create_app |

### 3.2 Módulos com cobertura parcial (30–79%)

| Módulo | Cobertura | Lacunas principais |
|---|---|---|
| `storage/repository.py` | 64% | Métodos de query avançada, filtros de data, joins |
| `web/cache.py` | 65% | Lógica de TTL, expiração de cache |
| `web/csrf.py` | 57% | Validação de token, middleware |
| `web/ratelimit.py` | 63% | Lógica de janela deslizante, cleanup |
| `web/routes/home.py` | 100% | Apenas smoke test — sem assertivas de conteúdo |
| `web/routes/taxas.py` | 39% | Filtros, paginação, export CSV |
| `web/routes/anomalias.py` | 35% | Filtros, resolução de anomalia, paginação |
| `web/routes/timeline.py` | 72% | Caminhos de dados vazios |
| `collectors/b3/collector.py` | 30% | collect_range, tratamento de erro HTTP |
| `collectors/b3/parser.py` | 31% | parse_linha, validações de campo, tipos |
| `collectors/b3/downloader.py` | 15% | extract_txt — lógica de ZIP aninhado |
| `collectors/bcb.py` | 25% | collect_serie, collect_selic, collect_selic_meta |

### 3.3 Módulos com ZERO cobertura (crítico)

| Módulo | Statements | Risco | Justificativa |
|---|---|---|---|
| `alerts/base.py` | 95 | ALTO | Contratos de AlertSender, AlertMessage |
| `alerts/email.py` | 57 | ALTO | Envio de email — silenciosamente falha |
| `alerts/telegram.py` | 72 | ALTO | Envio de Telegram |
| `alerts/manager.py` | 98 | CRÍTICO | Cooldown, filtro de severidade, orquestração |
| `analysis/health.py` | 117 | ALTO | Basileia, liquidez — decisões financeiras |
| `analysis/risk_score.py` | 124 | ALTO | Score de risco 0–100 — UI e decisões |
| `analysis/charts.py` | 102 | MÉDIO | Geração de gráficos Plotly |
| `collectors/ifdata.py` | 122 | ALTO | Coletor IF.Data BCB |
| `collectors/scheduler.py` | 173 | ALTO | Agendamento, timeout, callbacks |
| `collectors/scraper_client.py` | 40 | MÉDIO | PlaywrightClient |
| `collectors/scrapers/btg.py` | 81 | MÉDIO | Scraper BTG Pactual |
| `collectors/scrapers/inter.py` | 81 | MÉDIO | Scraper Banco Inter |
| `collectors/scrapers/rico.py` | 81 | MÉDIO | Scraper Rico |
| `collectors/scrapers/xp.py` | 81 | MÉDIO | Scraper XP Investimentos |
| `detectors/health.py` | 71 | ALTO | Health check dos detectores |
| `storage/seeds.py` | 35 | BAIXO | Seeds de dados iniciais |
| `cli/main.py` | 404 | MÉDIO | CLI Typer completo |
| `validators.py` | 42 | ALTO | validar_cnpj, parse_cnpj com HTTPException |
| `web/routes/instituicoes.py` | 33% miss | MÉDIO | Página de detalhes de IF |

---

## 4. Avaliação de Qualidade dos Testes Existentes

### 4.1 Pontos Fortes

**Fixtures bem projetadas.** O `conftest.py` global fornece `make_taxa()` e `make_taxa_serie()` como fábricas parametrizáveis sem persistência. O uso de `engine` + `db_session` com SQLite `:memory:` garante isolamento total entre testes — padrão correto para unit tests de repositório.

**Testes comportamentais, não de implementação.** Os testes de `SpreadDetector`, `VariacaoDetector` e `DivergenciaDetector` verificam saída (anomalias geradas, severidade, tipo) sem acessar atributos internos do detector. Isso resiste bem a refatorações.

**Uso correto de `respx`.** `test_scraper_base.py` usa `respx.mock` para interceptar chamadas `httpx` em vez de monkeypatch manual. Os testes de retry e timeout são realistas e testam o comportamento esperado em produção.

**`pytest.mark.parametrize` em `test_normalize.py`.** Cobertura de múltiplos formatos de entrada com tabelas declarativas — boa prática. Cobre variações regionais (vírgula vs ponto, "a.a.", "mês").

**Skip condicional para dependências opcionais.** `test_ml.py` usa `pytest.mark.skipif(not HAS_SKLEARN)` e `test_statistical.py` usa `pytest.skip()` condicional para `ruptures` — padrão correto para extras opcionais.

### 4.2 Fragilidades Identificadas

**Smoke tests de rotas sem assertions de conteúdo.** `test_web_routes.py` verifica apenas `status_code == 200` e `content-type`. Nenhum teste verifica se o template renderizou dados corretos, se counters de anomalias aparecem, ou se a paginação funciona. A rota `home.py` tem 100% de cobertura de linhas mas 0% de cobertura de comportamento verificável.

**`test_repository.py` usa setup/teardown implícito sem isolamento por teste.** Vários métodos chamam `db_session.commit()` dentro do teste e dependem de estado acumulado (ex: `test_count_apenas_ativas` assume banco vazio). Se a ordem de execução mudar ou outro teste vazar estado, os contadores ficam inconsistentes.

**`ResourceWarning: unclosed database`** aparece no output do pytest (sqlite3.Connection não fechada). O fixture `engine` faz `drop_all` + `dispose`, mas a fixture de escopo `module` em `test_web_routes.py` usa `StaticPool` sem fechar a conexão ao fim do módulo.

**Testes de ML têm assertions fracas.** `test_dados_normais_poucos_outliers` aceita `len(anomalias) <= 5` — uma margem tão larga que não detectaria regressão do algoritmo. `test_outlier_extremo_detectado` verifica apenas `>= 1` anomalia, sem verificar o IF correto ou a severidade esperada.

**Ausência de testes de erro controlado.** Nenhum teste verifica o que acontece quando um repositório recebe dados inválidos (CNPJ mal formatado, percentual negativo, prazo zero). As regras de negócio são testadas via detectores, mas os modelos SQLAlchemy não têm testes de constraint.

---

## 5. Caminhos Críticos Sem Cobertura

### 5.1 Motor de Alertas — Risco CRÍTICO

O `AlertManager._should_alert()` implementa a lógica de cooldown e filtro de severidade. Um bug nessa função pode resultar em: (a) zero alertas enviados apesar de anomalias críticas, ou (b) spam de notificações a cada coleta. Nenhuma linha testada.

### 5.2 Score de Risco — Risco ALTO

`calcular_score_risco()` em `analysis/risk_score.py` alimenta diretamente a UI com scores de 0–100 que os usuários usam para decisões de investimento. Os thresholds hardcoded (`< 100% CDI = 0 pontos`, `> 150% CDI = 40 pontos`) nunca foram verificados contra casos reais. Um erro nos pesos compostos (`spread_score + basileia_score + volatilidade_score + tendencia_score`) poderia gerar scores errados silenciosamente.

### 5.3 Validação CNPJ — Risco ALTO

`validators.py` contém `validar_cnpj()` com cálculo de dígitos verificadores. Nenhum teste cobre: CNPJ com todos dígitos iguais (deve falhar), CNPJ com 13 dígitos (deve falhar), CNPJ válido sem formatação (deve passar). A função `parse_cnpj()` levanta `HTTPException` — nunca testado.

### 5.4 Parser B3 ZIP Aninhado — Risco ALTO

`downloader.extract_txt()` implementa extração de ZIP dentro de executável SFX. A lógica de `rfind(b"PK\x03\x04")` é frágil: se o SFX tiver múltiplos blocos PK (compressão diferente), a função falha silenciosamente retornando `""`. Nenhum teste com fixture de arquivo real ou mock de bytes.

### 5.5 Scheduler — Risco ALTO

`CollectionScheduler._calculate_next_run()` tem lógica de timezone (America/Sao_Paulo) para tarefas diárias. O cálculo de `datetime.combine(now.date(), time_of_day, tzinfo=TZ_BRASIL)` pode gerar horário errado no horário de verão. A lógica de "se já passou hoje, agendar para amanhã" nunca foi testada.

### 5.6 Análise de Saúde — Risco ALTO

`analisar_saude_if()` em `analysis/health.py` usa thresholds regulatórios de Basileia (mínimo 10,5%) que são regras do Banco Central. Um erro de operador (`<` vs `<=`) nos comparadores pode mudar a classificação de CRITICO para SAUDAVEL para uma instituição com 10,5% exato — caso de boundary não testado.

### 5.7 Coletores Scraper — Risco MÉDIO

Os coletores `inter.py`, `xp.py`, `btg.py`, `rico.py` têm método `_parse_card()` que pode retornar `None` silenciosamente para cards malformados. Nenhum teste com HTML fixture verifica: (a) cards sem campo de taxa, (b) prazo_dias <= 0 descartado, (c) liquidez_diaria detectada por palavras-chave.

---

## 6. Avaliação de Fixtures, Factories e Parametrize

### Uso atual

- **Factories:** `make_taxa()` e `make_taxa_serie()` em `conftest.py` — bem projetadas, mas limitadas a `TaxaCDB`. Não existe factory para `InstituicaoFinanceira` (cada test_repository cria manualmente via `repo.create()`).
- **`@pytest.mark.parametrize`:** Usado em `test_normalize.py` (prazo_dias e valor_minimo) e `test_catalog.py` (tiers conhecidos). Não usado em `test_rules.py` — os 23 testes de regras poderiam ser reduzidos com tabelas.
- **`scope` de fixture:** `db_session` usa `scope="function"` (correto). O `app` e `client` em `test_web_routes.py` usam `scope="module"` — os testes acumulam estado entre classes (ex: dados inseridos por uma classe ficam visíveis para outra).

### Gaps

- Nenhuma fixture de `InstituicaoFinanceira` pré-configurada para análise de saúde (Basileia, liquidez).
- Nenhuma fixture de bytes de ZIP B3 para `test_downloader`.
- Nenhuma fixture de HTML para testar parsers de scrapers.
- Nenhum `factory_boy` ou `polyfactory` — construção de objetos é manual e repetitiva.

---

## 7. Top 10 Testes Prioritários

### #1 — `validators.py` — Validação de CNPJ

**Impacto:** Funcionalidade transversal usada em rotas, repositório e scrapers. Cobertura atual: 21%.

```python
# tests/unit/test_validators.py
import pytest
from fastapi import HTTPException
from veredas.validators import validar_cnpj, parse_cnpj, formatar_cnpj

@pytest.mark.parametrize("cnpj, esperado", [
    ("11.222.333/0001-81", True),   # CNPJ válido real (Itaú)
    ("60.872.504/0001-23", True),
    ("11.111.111/1111-11", False),  # todos iguais
    ("12.345.678/0001-00", False),  # dígito verificador errado
    ("123", False),                  # curto demais
    ("", False),
])
def test_validar_cnpj(cnpj, esperado):
    assert validar_cnpj(cnpj) == esperado

def test_parse_cnpj_required_levanta_quando_vazio():
    with pytest.raises(HTTPException) as exc_info:
        parse_cnpj(None, required=True)
    assert exc_info.value.status_code == 400

def test_parse_cnpj_invalido_levanta_400():
    with pytest.raises(HTTPException) as exc_info:
        parse_cnpj("12.345.678/0001-00", validate=True)
    assert exc_info.value.status_code == 400

def test_formatar_cnpj_sem_pontuacao():
    assert formatar_cnpj("60872504000123") == "60.872.504/0001-23"
```

---

### #2 — `analysis/risk_score.py` — Cálculo de Score de Risco

**Impacto:** Alimenta UI e decisões de investimento. Cobertura atual: 0%.

```python
# tests/unit/analysis/test_risk_score.py
import pytest
from decimal import Decimal
from veredas.analysis.risk_score import (
    calcular_score_risco, RiskLevel, _calcular_spread_score,
    _calcular_basileia_score, _score_to_level,
)

@pytest.mark.parametrize("pct_cdi, spread_score_esperado", [
    (Decimal("95"),  0.0),   # abaixo de 100% — sem risco por spread
    (Decimal("105"), 5.0),   # faixa 100-110
    (Decimal("115"), 15.0),  # faixa 110-120
    (Decimal("125"), 25.0),  # faixa 120-130
    (Decimal("140"), 35.0),  # faixa 130-150
    (Decimal("160"), 40.0),  # acima de 150 — máximo
])
def test_calcular_spread_score(pct_cdi, spread_score_esperado):
    assert _calcular_spread_score(pct_cdi) == spread_score_esperado

@pytest.mark.parametrize("basileia, basileia_score_esperado", [
    (Decimal("20.0"), 0.0),   # confortável
    (Decimal("13.5"), 10.0),  # entre 12-15
    (Decimal("11.0"), 20.0),  # entre 10.5-12
    (Decimal("9.5"),  30.0),  # abaixo do mínimo regulatório
    (None,            15.0),  # sem dados — risco médio
])
def test_calcular_basileia_score(basileia, basileia_score_esperado):
    assert _calcular_basileia_score(basileia) == basileia_score_esperado

@pytest.mark.parametrize("score, level", [
    (0,   RiskLevel.BAIXO),
    (25,  RiskLevel.BAIXO),
    (26,  RiskLevel.MEDIO),
    (50,  RiskLevel.MEDIO),
    (51,  RiskLevel.ALTO),
    (75,  RiskLevel.ALTO),
    (76,  RiskLevel.CRITICO),
    (100, RiskLevel.CRITICO),
])
def test_score_to_level_boundaries(score, level):
    assert _score_to_level(score) == level

def test_calcular_score_sem_dados_retorna_medio():
    result = calcular_score_risco()
    # Sem dados: spread=0, basileia=15, vol=0, tendencia=0 → score=15
    assert result.score == 15.0
    assert result.level == RiskLevel.BAIXO
```

---

### #3 — `collectors/b3/downloader.py` — Extração ZIP B3

**Impacto:** Pipeline de dados B3 depende inteiramente desta função. Cobertura atual: 15%.

```python
# tests/unit/collectors/test_b3_downloader.py
import io, zipfile
from veredas.collectors.b3.downloader import extract_txt, build_url
from datetime import date

def _make_b3_zip(txt_content: str) -> bytes:
    """Cria o ZIP aninhado que a B3 entrega."""
    # ZIP interno com o TXT
    inner_buf = io.BytesIO()
    with zipfile.ZipFile(inner_buf, "w") as z:
        z.writestr("RF230426.txt", txt_content)
    inner_bytes = inner_buf.getvalue()

    # SFX simulado: bytes aleatórios + ZIP interno
    sfx_bytes = b"\x00" * 512 + inner_bytes

    # ZIP externo com o SFX
    outer_buf = io.BytesIO()
    with zipfile.ZipFile(outer_buf, "w") as z:
        z.writestr("RF230426.ex_", sfx_bytes)
    return outer_buf.getvalue()

def test_extract_txt_retorna_conteudo():
    conteudo = "20260423\nITUB-DEB71;20250715;100;80;100.0;95.0;12.5;1.5"
    raw = _make_b3_zip(conteudo)
    resultado = extract_txt(raw)
    assert "ITUB-DEB71" in resultado

def test_extract_txt_bytes_vazios_retorna_str_vazia():
    assert extract_txt(b"") == ""

def test_extract_txt_zip_corrompido_retorna_str_vazia():
    assert extract_txt(b"not a zip file at all") == ""

def test_extract_txt_zip_externo_vazio_retorna_str_vazia():
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w"):
        pass  # ZIP externo sem arquivos
    assert extract_txt(buf.getvalue()) == ""

def test_build_url_formata_data_corretamente():
    url = build_url(date(2026, 4, 23))
    assert "RF230426.ex_" in url
```

---

### #4 — `collectors/b3/parser.py` — Parser do Boletim B3

**Impacto:** Qualidade dos dados do mercado secundário. Cobertura atual: 31%.

```python
# tests/unit/collectors/test_b3_parser.py
import pytest
from datetime import date
from decimal import Decimal
from veredas.collectors.b3.parser import B3RendaFixaParser, TICKER_PREFIX_TO_CNPJ

PREGAO_VALIDO = "20260423"
LINHA_VALIDA = "ITUB-DEB71;20250715;557;811;1348.48;1311.18;1.606608;311.1753"

@pytest.fixture
def parser():
    return B3RendaFixaParser()

def test_parse_linha_valida(parser):
    conteudo = f"{PREGAO_VALIDO}\n{LINHA_VALIDA}"
    records = parser.parse(conteudo)
    assert len(records) == 1
    r = records[0]
    assert r.data_pregao == date(2026, 4, 23)
    assert r.codigo == "ITUB-DEB71"
    assert r.emissor_codigo == "ITUB"
    assert r.tipo == "DEB"
    assert r.pu_mercado == Decimal("1348.48")
    assert r.taxa_mercado == Decimal("1.606608")

def test_parse_conteudo_vazio(parser):
    assert parser.parse("") == []

def test_parse_primeira_linha_invalida(parser):
    assert parser.parse("INVALIDO\n" + LINHA_VALIDA) == []

def test_parse_linha_com_campos_insuficientes(parser):
    conteudo = f"{PREGAO_VALIDO}\nTICKER;20250715;100"
    records = parser.parse(conteudo)
    assert len(records) == 0

def test_cnpj_emissor_mapeado(parser):
    conteudo = f"{PREGAO_VALIDO}\n{LINHA_VALIDA}"
    r = parser.parse(conteudo)[0]
    assert r.cnpj_emissor == TICKER_PREFIX_TO_CNPJ["ITUB"]
    assert r.is_financeira is True

def test_emissor_nao_financeiro(parser):
    linha = "VALE-DEB12;20280101;730;520;1100.00;1050.00;8.5;2.1"
    conteudo = f"{PREGAO_VALIDO}\n{linha}"
    r = parser.parse(conteudo)[0]
    assert r.is_financeira is False
    assert r.cnpj_emissor is None

@pytest.mark.parametrize("ticker, tipo_esperado", [
    ("ITUB-DEB71",  "DEB"),
    ("VALE-ETF1",   "ETF"),
    ("XPTO-CRI12",  "CRI"),
    ("XPTO-CRA5",   "CRA"),
    ("XPTO-SEM",    "OUTRO"),
])
def test_tipo_from_ticker(ticker, tipo_esperado):
    linha = f"{ticker};20280101;100;80;100.0;95.0;10.0;1.5"
    conteudo = f"{PREGAO_VALIDO}\n{linha}"
    records = B3RendaFixaParser().parse(conteudo)
    assert records[0].tipo == tipo_esperado
```

---

### #5 — `analysis/health.py` — Análise de Saúde Financeira

**Impacto:** Thresholds regulatórios de Basileia e liquidez. Cobertura atual: 0%.

```python
# tests/unit/analysis/test_health.py
import pytest
from decimal import Decimal
from unittest.mock import MagicMock
from veredas.analysis.health import (
    analisar_saude_if, comparar_com_benchmark,
    HealthStatus, MINIMO_BASILEIA,
)

def _make_if(basileia=None, liquidez=None):
    mock = MagicMock()
    mock.id = 1
    mock.nome = "Banco Teste"
    mock.segmento = "Banco Comercial"
    mock.indice_basileia = Decimal(str(basileia)) if basileia is not None else None
    mock.indice_liquidez = Decimal(str(liquidez)) if liquidez is not None else None
    return mock

# Teste de boundary: exatamente no mínimo regulatório
def test_basileia_exatamente_no_minimo_nao_e_critico():
    if_data = _make_if(basileia=10.5)  # exatamente MINIMO_BASILEIA
    resultado = analisar_saude_if(if_data)
    # 10.5 não é MENOR que 10.5, portanto não deve ser CRITICO
    basileia_ind = resultado.indicadores[0]
    assert basileia_ind.status != HealthStatus.CRITICO

def test_basileia_abaixo_do_minimo_e_critico():
    if_data = _make_if(basileia=9.0)
    resultado = analisar_saude_if(if_data)
    assert resultado.status_geral == HealthStatus.CRITICO
    assert any("Basileia" in a for a in resultado.alertas)

def test_basileia_saudavel():
    if_data = _make_if(basileia=18.0)
    resultado = analisar_saude_if(if_data)
    assert resultado.indicadores[0].status == HealthStatus.SAUDAVEL

def test_liquidez_insuficiente_e_critica():
    if_data = _make_if(basileia=20.0, liquidez=0.8)
    resultado = analisar_saude_if(if_data)
    assert resultado.status_geral == HealthStatus.CRITICO

def test_status_geral_pior_dos_indicadores():
    # Basileia saudável mas liquidez crítica → geral crítico
    if_data = _make_if(basileia=18.0, liquidez=0.5)
    resultado = analisar_saude_if(if_data)
    assert resultado.status_geral == HealthStatus.CRITICO

def test_sem_dados_retorna_atencao():
    if_data = _make_if()
    resultado = analisar_saude_if(if_data)
    assert resultado.status_geral == HealthStatus.ATENCAO
```

---

### #6 — `alerts/manager.py` — Gerenciador de Alertas

**Impacto:** Núcleo da notificação. Um bug silencia todos os alertas críticos. Cobertura atual: 0%.

```python
# tests/unit/alerts/test_manager.py
import pytest
from unittest.mock import AsyncMock, MagicMock
from datetime import datetime, timedelta
from veredas.alerts.manager import AlertManager
from veredas.alerts.base import AlertChannel, AlertResult

def _make_anomalia(severidade="HIGH", id=1):
    mock = MagicMock()
    mock.id = id
    mock.severidade = severidade
    return mock

def _make_sender(channel=AlertChannel.EMAIL, success=True):
    sender = AsyncMock()
    sender.channel = channel
    sender.is_configured = True
    sender.send.return_value = AlertResult(success=success, channel=channel)
    return sender

@pytest.mark.asyncio
async def test_notify_envia_para_todos_canais():
    sender1 = _make_sender(AlertChannel.EMAIL)
    sender2 = _make_sender(AlertChannel.TELEGRAM)
    manager = AlertManager(senders=[sender1, sender2], min_severity="LOW", cooldown_minutes=5)
    
    results = await manager.notify(_make_anomalia(severidade="HIGH"))
    
    assert len(results) == 2
    sender1.send.assert_called_once()
    sender2.send.assert_called_once()

@pytest.mark.asyncio
async def test_notify_respeita_severidade_minima():
    sender = _make_sender()
    manager = AlertManager(senders=[sender], min_severity="HIGH", cooldown_minutes=5)
    
    results = await manager.notify(_make_anomalia(severidade="LOW"))
    
    assert not results[0].success
    sender.send.assert_not_called()

@pytest.mark.asyncio
async def test_notify_respeita_cooldown():
    sender = _make_sender()
    manager = AlertManager(senders=[sender], min_severity="LOW", cooldown_minutes=60)
    anomalia = _make_anomalia()
    
    # Primeiro envio: deve passar
    await manager.notify(anomalia)
    # Segundo envio imediato: deve ser bloqueado por cooldown
    results = await manager.notify(anomalia)
    
    assert not results[0].success
    assert "Cooldown" in results[0].error
    assert sender.send.call_count == 1  # apenas 1 envio real

@pytest.mark.asyncio
async def test_notify_sem_senders_configurados():
    manager = AlertManager(senders=[], min_severity="LOW", cooldown_minutes=5)
    results = await manager.notify(_make_anomalia())
    assert not results[0].success
```

---

### #7 — `collectors/bcb.py` — Coletor BCB

**Impacto:** Fonte das taxas de referência (Selic, CDI, IPCA). Cobertura atual: 25%.

```python
# tests/unit/collectors/test_bcb.py
import pytest
from unittest.mock import patch, MagicMock
from datetime import date
from decimal import Decimal
import pandas as pd
from veredas.collectors.bcb import BCBCollector, TaxaReferenciaBCB, SERIES_CODES

def _make_df(tipo: str, valor: float, data: date) -> pd.DataFrame:
    return pd.DataFrame(
        {tipo: [valor]},
        index=pd.DatetimeIndex([pd.Timestamp(data)])
    )

@pytest.mark.asyncio
async def test_collect_retorna_dados_bcb_com_sucesso():
    selic_df = _make_df("selic", 10.75, date(2026, 4, 23))
    cdi_df   = _make_df("cdi",   10.65, date(2026, 4, 23))
    ipca_df  = _make_df("ipca",  0.38,  date(2026, 4, 23))

    def fake_sgs_get(codes, **kwargs):
        key = list(codes.keys())[0]
        return {"selic": selic_df, "cdi": cdi_df, "ipca": ipca_df}[key]

    with patch("veredas.collectors.bcb._sgs_get_sync", side_effect=fake_sgs_get):
        collector = BCBCollector()
        result = await collector.collect()

    assert result.success
    assert result.data.selic.valor == Decimal("10.75")
    assert result.data.cdi.tipo == "cdi"

@pytest.mark.asyncio
async def test_collect_retorna_falha_em_excecao():
    with patch("veredas.collectors.bcb._sgs_get_sync", side_effect=Exception("timeout BCB")):
        collector = BCBCollector()
        result = await collector.collect()

    assert not result.success
    assert "BCB" in result.error

@pytest.mark.asyncio
async def test_collect_serie_retorna_none_quando_df_vazio():
    vazio = pd.DataFrame({"selic": []})
    with patch("veredas.collectors.bcb._sgs_get_sync", return_value=vazio):
        collector = BCBCollector()
        taxa = await collector._collect_serie("selic", date(2026, 1, 1), date(2026, 4, 23))
    assert taxa is None
```

---

### #8 — `collectors/scheduler.py` — Agendamento com Timezone

**Impacto:** Coletas silenciosamente atrasadas ou duplicadas em troca de fuso. Cobertura atual: 0%.

```python
# tests/unit/collectors/test_scheduler.py
import pytest
from datetime import datetime, time, timedelta
from unittest.mock import AsyncMock, MagicMock
from veredas.collectors.scheduler import CollectionScheduler, FrequencyType
from veredas import TZ_BRASIL

def _make_collector(success=True):
    col = AsyncMock()
    col.source_name = "mock"
    result = MagicMock()
    result.success = success
    result.error = None if success else "erro simulado"
    col.collect.return_value = result
    return col

def test_add_remove_task():
    scheduler = CollectionScheduler()
    col = _make_collector()
    scheduler.add_once("t1", col)
    assert "t1" in scheduler.tasks
    assert scheduler.remove_task("t1") is True
    assert "t1" not in scheduler.tasks
    assert scheduler.remove_task("t1") is False  # já removida

def test_disable_enable_task():
    scheduler = CollectionScheduler()
    scheduler.add_once("t1", _make_collector())
    scheduler.disable_task("t1")
    assert not scheduler.tasks["t1"].enabled
    scheduler.enable_task("t1")
    assert scheduler.tasks["t1"].enabled

@pytest.mark.asyncio
async def test_execute_task_atualiza_estatisticas():
    scheduler = CollectionScheduler()
    col = _make_collector(success=True)
    task = scheduler.add_once("t1", col)
    
    updated = await scheduler._execute_task(task)
    
    assert updated.run_count == 1
    assert updated.success_count == 1
    assert updated.error_count == 0

@pytest.mark.asyncio
async def test_execute_task_com_falha_registra_erro():
    scheduler = CollectionScheduler()
    col = _make_collector(success=False)
    task = scheduler.add_once("t1", col)
    
    updated = await scheduler._execute_task(task)
    
    assert updated.error_count == 1
    assert updated.success_count == 0

def test_calculate_next_run_daily_se_passou_hoje():
    scheduler = CollectionScheduler()
    col = _make_collector()
    # Horário no passado hoje → next_run deve ser amanhã
    hora_passada = (datetime.now(TZ_BRASIL) - timedelta(hours=2)).time()
    task = scheduler.add_daily("t1", col, time_of_day=hora_passada)
    
    assert task.next_run.date() > datetime.now(TZ_BRASIL).date()

@pytest.mark.asyncio
async def test_run_com_max_iterations():
    scheduler = CollectionScheduler(check_interval=0)
    col = _make_collector()
    # Tarefa que já venceu (next_run = agora)
    scheduler.add_interval("t1", col, seconds=0)
    
    await scheduler.run(max_iterations=2)
    
    assert col.collect.call_count >= 1
```

---

### #9 — `web/routes/taxas.py` — Filtros e Export CSV

**Impacto:** Funcionalidade de filtro por indexador, prazo, mercado — nunca testada com dados reais. Cobertura atual: 39%.

```python
# tests/integration/test_web_routes_taxas.py
import pytest
from starlette.testclient import TestClient
from decimal import Decimal
from datetime import datetime

# (reutilizar o fixture `client` do conftest ou do test_web_routes.py)

class TestTaxasFilters:
    def test_filtro_por_indexador_cdi(self, client, db_with_data):
        response = client.get("/taxas/?indexador=CDI")
        assert response.status_code == 200
        # Verificar que o filtro foi aplicado na resposta HTML
        assert "CDI" in response.text

    def test_filtro_por_mercado_secundario(self, client):
        response = client.get("/taxas/?mercado=secundario")
        assert response.status_code == 200

    def test_paginacao_pagina_invalida_retorna_422(self, client):
        response = client.get("/taxas/?pagina=0")
        assert response.status_code == 422  # Pydantic validation

    def test_export_csv_retorna_stream(self, client):
        response = client.get("/taxas/export")
        assert response.status_code == 200
        assert "text/csv" in response.headers.get("content-type", "")

    def test_indexador_invalido_retorna_erro(self, client):
        response = client.get("/taxas/?indexador=INVALIDO")
        # Deve retornar 400 ou 422, não 500
        assert response.status_code in (400, 422)
```

---

### #10 — `web/routes/anomalias.py` — Resolução de Anomalia (POST)

**Impacto:** Ação destrutiva de estado — marcar anomalia como resolvida. Cobertura atual: 35%.

```python
# (adicionar à TestAnomaliasRoute em test_web_routes.py)

class TestAnomaliasResolver:
    def test_resolver_anomalia_existente_retorna_sucesso(self, client, db_com_anomalia):
        anomalia_id = db_com_anomalia.id
        response = client.post(f"/anomalias/{anomalia_id}/resolver", 
                               data={"notas": "Verificado — falso positivo"})
        assert response.status_code in (200, 302)

    def test_resolver_anomalia_inexistente_retorna_404(self, client):
        response = client.post("/anomalias/99999/resolver",
                               data={"notas": ""})
        assert response.status_code == 404

    def test_lista_anomalias_filtro_severidade(self, client):
        response = client.get("/anomalias/?severidade=CRITICAL")
        assert response.status_code == 200

    def test_lista_anomalias_filtro_resolvido(self, client):
        response = client.get("/anomalias/?resolvido=false")
        assert response.status_code == 200
```

---

## 8. Candidatos a Property-Based Testing (Hypothesis)

Os seguintes módulos têm lógica de parsing de entrada arbitrária que se beneficiaria de Hypothesis para encontrar edge cases imprevistos:

### `validators.validar_cnpj` — candidate ideal
A função recebe qualquer string e deve nunca levantar exceção. Com Hypothesis, podemos verificar que strings arbitrárias (Unicode, vazias, com espaços) sempre retornam `bool` sem crash:

```python
from hypothesis import given, strategies as st
from veredas.validators import validar_cnpj

@given(st.text())
def test_validar_cnpj_nunca_levanta(cnpj):
    result = validar_cnpj(cnpj)
    assert isinstance(result, bool)
```

### `collectors/scrapers/normalize.parse_taxa` — candidate prioritário
A função `parse_taxa()` recebe texto de prateleiras de corretoras e deve sempre retornar uma tupla válida. Com Hypothesis podemos testar que strings arbitrárias nunca causam `InvalidOperation` ou `AttributeError`:

```python
@given(st.text(max_size=200))
def test_parse_taxa_nunca_levanta(texto):
    from veredas.collectors.scrapers.normalize import parse_taxa
    # Não deve levantar exceção para entrada arbitrária
    resultado = parse_taxa(texto)
    assert len(resultado) == 3
```

### `collectors/b3/parser.B3RendaFixaParser.parse` — candidate
O parser ignora linhas malformadas com `logger.debug()`. Hypothesis pode confirmar que nunca retorna `None` na lista nem levanta exceção:

```python
@given(st.text())
def test_parser_b3_nunca_levanta(conteudo):
    records = B3RendaFixaParser().parse(conteudo)
    assert isinstance(records, list)
    assert all(r is not None for r in records)
```

### `analysis/risk_score._score_to_level` — candidate simples
Score é `float` de 0 a 100 (e potencialmente fora da faixa). Verificar que qualquer float retorna um `RiskLevel` válido sem `KeyError`:

```python
@given(st.floats(allow_nan=False))
def test_score_to_level_qualquer_float(score):
    from veredas.analysis.risk_score import _score_to_level, RiskLevel
    result = _score_to_level(score)
    assert isinstance(result, RiskLevel)
```

---

## 9. Avaliação do CI (`.github/workflows/ci.yml`)

### O que está correto

- Matrix Python 3.11 e 3.12 com `fail-fast: false` — bom.
- Instalação completa de extras: `[dev,web,ml,alerts,scrapers]` — todos os módulos disponíveis para teste.
- Cobertura reportada com `--cov-report=term-missing` — visível no log do CI.
- Job separado para lint (`ruff check` + `ruff format --check`) — bom.
- Job de type checking com mypy, porém com `continue-on-error: true` — mypy não bloqueia o CI.

### Lacunas Críticas

**1. Sem threshold de cobertura.** O CI não falha quando a cobertura cai. Adicionar ao `pyproject.toml`:
```toml
[tool.coverage.report]
fail_under = 50  # aumentar progressivamente
```
E no workflow: `pytest --cov-fail-under=50`

**2. Sem cache de virtualenv.** O `cache: pip` do `setup-python` só cacheia o download de wheels, não o ambiente instalado. Com 50+ dependências, cada run instala tudo do zero (~3–4min). Usar `uv` com cache seria mais eficiente.

**3. `continue-on-error: true` no mypy oculta regressões de tipo.** Remover para que erros de tipo bloqueiem o merge após estabilização do código.

**4. Sem job de segurança.** Recomendado adicionar:
```yaml
- name: Security scan
  run: pip install bandit && bandit -r src/ -c pyproject.toml
```

**5. Nenhuma execução de cobertura com upload para serviço externo.** Codecov ou Coveralls dariam visibilidade histórica das tendências de cobertura:
```yaml
- name: Upload coverage
  uses: codecov/codecov-action@v4
  with:
    token: ${{ secrets.CODECOV_TOKEN }}
```

**6. Playwright instalado mas sem testes E2E.** O workflow instala `chromium` mas os únicos testes de rota são `TestClient` (não usam Playwright). O custo de ~2min de instalação é pago sem benefício — considerar mover para job separado condicionado a arquivos modificados em `tests/e2e/`.

**7. Nenhum `dependabot.yml`** para atualização automática de dependências (especialmente segurança).

---

## 10. Recomendações de Ferramentas

| Ferramenta | Uso | Prioridade |
|---|---|---|
| **`hypothesis`** | Property-based testing para parsers e validadores | Alta |
| **`factory_boy`** ou **`polyfactory`** | Factories para SQLAlchemy models (substituir setup manual) | Alta |
| **`pytest-httpx`** | Alternativa ao respx para mock de httpx (suporte nativo ao pytest) | Média |
| **`freezegun`** | Congelar tempo em testes de scheduler e cooldown de alertas | Alta |
| **`codecov`** | Dashboard de cobertura histórica integrado ao CI | Média |
| **`pytest-xdist`** | Paralelização dos testes (atualmente 13s para 188 testes — escalará mal) | Baixa |
| **`bandit`** | Análise estática de segurança (já em `pyproject.toml`, falta no CI) | Média |
| **`pytest-benchmark`** | Benchmarks para detectores com séries grandes (>1000 taxas) | Baixa |
| **`responses`** ou **`aioresponses`** | Mock de `requests`/`aiohttp` para coletor IF.Data | Média |

---

## 11. Caminho Prioritário para 70% de Cobertura

A cobertura atual de 43% pode subir para ~70% com os seguintes passos ordenados por impacto/esforço:

1. `tests/unit/test_validators.py` — +2% de cobertura, 1h de trabalho
2. `tests/unit/analysis/test_risk_score.py` — +3% de cobertura, 2h
3. `tests/unit/analysis/test_health.py` — +3% de cobertura, 2h
4. `tests/unit/collectors/test_b3_downloader.py` — +1%, 1h
5. `tests/unit/collectors/test_b3_parser.py` — +2%, 2h
6. `tests/unit/collectors/test_bcb.py` — +2%, 2h
7. `tests/unit/alerts/test_manager.py` — +2%, 2h
8. `tests/unit/collectors/test_scheduler.py` — +4%, 3h
9. `tests/integration/test_web_routes_filters.py` — +3%, 3h
10. `tests/unit/test_validators_hypothesis.py` (Hypothesis) — +1% + qualidade, 2h

**Total estimado:** ~20h de desenvolvimento para +27 pontos percentuais de cobertura e eliminação dos maiores riscos de regressão silenciosa.

---

*Relatório gerado em 2026-04-24 por análise estática e dinâmica da suite de testes.*
