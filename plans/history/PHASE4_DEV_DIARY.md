# Diário de Desenvolvimento - Fase 4: Expansão de Fontes

**Projeto:** veredas-de-papel
**Fase:** 4 - Expansão de Fontes de Dados
**Período:** Janeiro 2025
**Status:** ✅ Concluído
**Testes:** 325 passando (vs 232 na Fase 3)

---

## 1. Visão Geral

A Fase 4 expande significativamente as fontes de dados do sistema de monitoramento de CDBs, adicionando:

- **Scrapers de corretoras** para coleta de taxas em tempo real
- **Integração com B3** para dados do mercado secundário
- **Dados alternativos** (Reclame Aqui, processos BC, análise de sentimento)
- **Novos detectores** especializados para cada fonte

### Objetivos Alcançados

| Objetivo | Entrega |
|----------|---------|
| F4.1 - Framework de Scrapers | 5 scrapers + anti-bot + normalização |
| F4.2 - B3 Mercado Secundário | API + parser + PriceDropDetector |
| F4.3 - Dados Alternativos | Reclame Aqui + BC + Sentimento |
| F4.4 - Integração | Modelos + CLI + DetectionEngine |

---

## 2. Decisões de Arquitetura

### 2.1 Padrão de Scrapers

**Decisão:** Estender `BaseCollector` ao invés de criar nova hierarquia.

**Justificativa:**
- Mantém consistência com coletores existentes (BCB, IFData)
- Reutiliza interface `collect()` e `health_check()`
- Facilita integração com `DetectionEngine`
- Permite uso no scheduler existente

**Implementação:**
```
BaseCollector (abc)
    └── BaseScraper (web-specific)
            ├── XPScraper
            ├── BTGScraper
            ├── RicoScraper
            ├── NubankScraper
            └── InterScraper
```

### 2.2 Estratégia Anti-Bot em Camadas

**Decisão:** Implementar defesas em múltiplas camadas independentes.

**Justificativa:**
- Cada camada pode ser ativada/desativada conforme necessidade
- Permite ajuste fino por corretora
- Reduz chance de detecção

**Camadas:**
1. **RateLimiter** - Controle de taxa adaptativo (aumenta delay em 429/503)
2. **SessionManager** - Fingerprint de browser realista
3. **ProxyRotator** - Pool de proxies com health tracking
4. **User-Agent Rotation** - 5 browsers reais pré-configurados

### 2.3 Normalização Centralizada

**Decisão:** Criar `TaxaNormalizer` com mapeamento CNPJ centralizado.

**Justificativa:**
- Cada corretora usa nomes diferentes para mesma IF
- "ITAU", "Itaú Unibanco", "ITAÚ" devem ser tratados igual
- Mapeamento manual mais confiável que fuzzy matching

**Implementação:**
```python
CNPJ_MAP = {
    "ITAU UNIBANCO": "60.701.190/0001-04",
    "ITAU": "60.701.190/0001-04",
    "BRADESCO": "60.746.948/0001-12",
    # ... 50+ instituições
}
```

### 2.4 Modelos B3 Orientados a Análise

**Decisão:** Criar modelos ricos com properties calculadas.

**Justificativa:**
- PU (Preço Unitário) é métrica central do mercado secundário
- Properties evitam recálculo e encapsulam lógica de negócio
- Facilita detecção de anomalias

**Exemplo:**
```python
@dataclass
class PrecoSecundario:
    pu_abertura: Decimal
    pu_fechamento: Decimal

    @property
    def variacao_pu_dia(self) -> Decimal:
        return self.pu_fechamento - self.pu_abertura

    @property
    def amplitude_dia(self) -> Decimal:
        return self.pu_maximo - self.pu_minimo
```

### 2.5 Análise de Sentimento Lexicon-First

**Decisão:** Usar análise baseada em léxico antes de ML.

**Justificativa:**
- Léxico financeiro PT-BR é especializado e pequeno
- Não requer treinamento ou GPU
- Interpretável e ajustável
- ML pode ser adicionado depois (transformers opcional)

**Léxico:**
```python
LEXICO_FINANCEIRO = {
    # Muito Negativos (score -1.0)
    "insolvência": -1.0, "falência": -1.0, "fraude": -1.0,

    # Negativos (score -0.5 a -0.8)
    "prejuízo": -0.7, "inadimplência": -0.6, "multa": -0.5,

    # Positivos
    "lucro": 0.7, "crescimento": 0.5, "solidez": 0.8,
}
```

### 2.6 Agregação de Sinais com Pesos

**Decisão:** Criar `SignalAggregator` com pesos configuráveis.

**Justificativa:**
- Diferentes sinais têm diferentes poderes preditivos
- Processos BC são mais graves que reclamações
- Permite calibração baseada em backtesting futuro

**Pesos Default:**
```python
PESOS_DEFAULT = {
    "reclame_aqui": 0.15,      # Leading indicator
    "processos_bc": 0.35,      # Risco regulatório
    "mercado_secundario": 0.30, # Percepção de mercado
    "sentimento": 0.20,        # Sinais antecipados
}
```

---

## 3. Escolha de Bibliotecas

### 3.1 HTTP Client: httpx

**Escolha:** `httpx` ao invés de `aiohttp` ou `requests`

**Motivos:**
- API similar a `requests` (familiar)
- Suporte nativo a async
- Proxy support robusto
- Já usado no projeto (BCB collector)

### 3.2 HTML Parsing: BeautifulSoup + lxml

**Escolha:** `beautifulsoup4` com parser `lxml`

**Motivos:**
- Standard da indústria para scraping
- lxml é 10x mais rápido que html.parser
- CSS selectors familiares

### 3.3 Dados Estruturados: dataclasses

**Escolha:** `dataclasses` nativas ao invés de Pydantic

**Motivos:**
- Já usado extensivamente no projeto
- Menor overhead
- Pydantic seria overkill para dataclasses internas
- Validação feita manualmente onde necessário

### 3.4 Processamento de Texto: re (stdlib)

**Escolha:** `re` ao invés de spaCy ou NLTK

**Motivos:**
- Análise de sentimento é simples (lookup de palavras)
- Não precisa de NER ou parsing sintático
- spaCy seria 100MB+ de dependência para pouco ganho

---

## 4. Módulos Implementados

### 4.1 Framework de Scrapers

#### `scrapers/base.py`

**Propósito:** Classe base abstrata para scrapers de corretoras.

**Como funciona:**
1. Herda de `BaseCollector`
2. Cria cliente HTTP com timeout e retry
3. Rotaciona user-agent a cada requisição
4. Implementa backoff exponencial em falhas
5. Define `scrape()` abstrato para cada corretora

**Dataclasses:**
- `TaxaColetada` - Uma taxa coletada (IF, percentual, prazo, indexador)
- `ScraperResult` - Resultado com lista de taxas + erros

#### `scrapers/anti_bot.py`

**Propósito:** Estratégias para evitar detecção/bloqueio.

**Classes:**

| Classe | Função |
|--------|--------|
| `RateLimiter` | Controla taxa de requisições, adapta em 429 |
| `ProxyRotator` | Gerencia pool de proxies, remove falhos |
| `SessionManager` | Mantém cookies/sessão, simula browser |
| `BrowserFingerprint` | Headers/viewport realistas |
| `CaptchaSolver` | Interface para 2captcha/anticaptcha |

#### `scrapers/normalizer.py`

**Propósito:** Padroniza dados de diferentes fontes.

**Funções principais:**
- `normalize_nome()` - Padroniza nomes de IFs
- `normalize_cnpj()` - Formata CNPJ consistentemente
- `find_cnpj_by_name()` - Busca CNPJ por nome
- `validate_percentual()` - Valida taxa está em range esperado

**Classe:**
- `TaxaNormalizer` - Normaliza batch de taxas, deduplica

#### `scrapers/brokers/*.py`

**5 scrapers implementados:**

| Scraper | URL | Método |
|---------|-----|--------|
| XPScraper | investimentos.xp.com.br | API JSON |
| BTGScraper | btgpactualdigital.com | API JSON |
| RicoScraper | rico.com.vc | HTML scraping |
| NubankScraper | nubank.com.br | API JSON |
| InterScraper | bancointer.com.br | HTML + JSON |

Cada um implementa:
- `scrape()` - Coleta taxas
- `_parse_response()` - Extrai dados do formato específico
- `_build_taxa()` - Converte para `TaxaColetada`

### 4.2 Integração B3

#### `b3/models.py`

**Propósito:** Modelos de dados do mercado secundário.

**Classes principais:**

```
TipoTitulo (Enum)
├── CDB, LCI, LCA, LC, DEBENTURE, CRI, CRA, OUTROS

StatusNegociacao (Enum)
├── EXECUTADA, CANCELADA, PENDENTE

PrecoSecundario (dataclass)
├── codigo_titulo, emissor_cnpj, emissor_nome
├── pu_abertura, pu_fechamento, pu_minimo, pu_maximo, pu_medio
├── quantidade_negocios, valor_financeiro
├── taxa_minima, taxa_maxima, taxa_media
├── variacao_dia (opcional)
└── Properties: variacao_pu_dia, amplitude_dia, spread_taxa

NegociacaoB3 (dataclass)
├── Individual trade record

ResumoMercadoSecundario (dataclass)
├── Resumo diário do mercado
```

#### `b3/api.py`

**Propósito:** Coletor de dados da B3.

**Como funciona:**
1. Busca dados na API pública da B3
2. Fallback para arquivos CSV públicos
3. Parser normaliza diferentes formatos
4. Retorna `CollectionResult[list[PrecoSecundario]]`

**Métodos:**
- `collect()` - Interface padrão
- `coletar_precos_dia()` - Preços de um dia
- `coletar_negociacoes()` - Negociações individuais
- `health_check()` - Verifica conectividade

#### `b3/parser.py`

**Propósito:** Parser multi-formato para dados B3.

**Formatos suportados:**
- JSON de APIs
- CSV de arquivos públicos
- HTML de páginas web

**Métodos:**
- `parse_json_response()` - Parse API JSON
- `parse_csv_file()` - Parse arquivo CSV
- `parse_html_table()` - Parse tabela HTML

### 4.3 Dados Alternativos

#### `alternative/reclame_aqui.py`

**Propósito:** Coleta reputação no Reclame Aqui.

**Dataclasses:**
- `Reclamacao` - Uma reclamação (título, status, resolvido)
- `ReputacaoRA` - Reputação consolidada (nota, índice solução)

**Como funciona:**
1. Busca empresa por nome/CNPJ
2. Coleta nota geral, índice solução, tempo resposta
3. Conta reclamações últimos 30/90 dias
4. Calcula tendência vs período anterior

**Indicadores de risco:**
- Nota < 6.0
- Índice solução < 50%
- Spike de reclamações (> 2σ)

#### `alternative/bacen_processos.py`

**Propósito:** Coleta processos administrativos do BC.

**Enums:**
```python
TipoProcesso
├── ADMINISTRATIVO_SANCIONADOR (PAS)
├── MULTA, ADVERTENCIA
├── INTERVENCAO, LIQUIDACAO, RAET

StatusProcesso
├── ABERTO, EM_ANDAMENTO, JULGADO, ARQUIVADO, RECURSO
```

**Dataclasses:**
- `ProcessoBC` - Um processo (número, tipo, status, multa)
- `HistoricoProcessosIF` - Histórico consolidado de uma IF

**Como funciona:**
1. Busca processos por CNPJ
2. Classifica por tipo e gravidade
3. Soma multas aplicadas
4. Identifica processos graves (intervenção, liquidação)

#### `sentiment/analyzer.py`

**Propósito:** Análise de sentimento de textos financeiros.

**Enum:**
```python
Sentimento
├── MUITO_NEGATIVO, NEGATIVO, NEUTRO, POSITIVO, MUITO_POSITIVO
```

**Classe `SentimentAnalyzer`:**
1. Tokeniza texto (lowercase, remove pontuação)
2. Busca cada palavra no léxico financeiro
3. Calcula score médio ponderado
4. Classifica em Sentimento baseado em thresholds

**Léxico:** ~200 palavras financeiras PT-BR com scores -1.0 a +1.0

#### `sentiment/aggregator.py`

**Propósito:** Agrega múltiplos sinais em score de risco.

**Sinais de entrada:**
```python
SinalReclameAqui    # nota, reclamações, tendência
SinalProcessosBC    # processos ativos, multas
SinalMercadoSecundario  # variação PU, volume
SinalSentimento     # score, confiança
```

**Saída:**
```python
RiskSignal
├── instituicao_nome, instituicao_cnpj
├── score_consolidado (0-100)
├── nivel_risco (BAIXO, MODERADO, ELEVADO, CRITICO)
├── tendencia (MELHORANDO, ESTAVEL, PIORANDO)
├── sinais_ativos (lista de sinais que contribuíram)
└── detalhes (breakdown por fonte)
```

**Algoritmo:**
1. Normaliza cada sinal para 0-1
2. Aplica peso configurável
3. Soma ponderada → score 0-100
4. Classifica em nível de risco

### 4.4 Novos Detectores

#### `detectors/platform_discrepancy.py`

**Propósito:** Detecta diferenças de taxa entre plataformas.

**Lógica:**
1. Agrupa taxas por IF + indexador + faixa de prazo
2. Compara maior vs menor taxa do grupo
3. Gera anomalia se diferença > threshold

**Thresholds:**
- MEDIUM: > 5pp
- HIGH: > 10pp
- CRITICAL: > 20pp

**Exemplo de anomalia:**
> "Discrepância de 15pp entre plataformas para Banco X.
> Maior: 130% CDI (XP), Menor: 115% CDI (BTG)"

#### `detectors/price_drop.py`

**Propósito:** Detecta quedas de preço no mercado secundário.

**3 tipos de detecção:**
1. **Queda Nominal** - PU abaixo de R$ 1000 (valor par)
2. **Queda Diária** - Variação negativa expressiva no dia
3. **Queda Comparativa** - Queda vs dia anterior

**Thresholds:**
- MEDIUM: > 5% (nominal) / > 2% (diária)
- HIGH: > 10% / > 5%
- CRITICAL: > 20% / > 10%

#### `detectors/sentiment_risk.py`

**Propósito:** Detecta risco elevado por sinais agregados.

**Como funciona:**
1. Recebe `RiskSignal` do agregador
2. Classifica severidade pelo `nivel_risco`
3. Gera anomalia com breakdown dos sinais

**Tipos de anomalia:**
- `COMPLAINT_SPIKE` - Aumento de reclamações
- `REGULATORY_PROCESS` - Processo BC grave
- `NEGATIVE_SENTIMENT` - Sentimento negativo
- `COMPOSITE_RISK_CRITICAL` - Múltiplos sinais

---

## 5. Aprendizados dos Debugs

### 5.1 Consistência de Dataclasses

**Problema:** Testes falhando com `TypeError: got unexpected keyword argument`

**Causa:** Nomes de campos inconsistentes entre definição e uso.

**Exemplos encontrados:**
```python
# ERRADO - nomes inventados no teste
ReputacaoEmpresa(empresa_id="itau", ...)

# CORRETO - nomes reais da dataclass
ReputacaoRA(empresa_nome="Itaú Unibanco", ...)
```

**Solução:** Sempre verificar assinatura real da dataclass antes de usar.

**Lição:** Criar helper functions de teste com defaults para dataclasses complexas:
```python
def _create_preco_secundario(**kwargs) -> PrecoSecundario:
    defaults = {
        "codigo_titulo": "CDB001",
        "emissor_cnpj": "00.000.000/0001-00",
        # ... todos os campos obrigatórios
    }
    defaults.update(kwargs)
    return PrecoSecundario(**defaults)
```

### 5.2 DetectionResult vs AnomaliaDetectada

**Problema:** `TypeError: DetectionResult got unexpected keyword 'detector'`

**Causa:** Confusão entre campos das duas dataclasses.

**Diferenças importantes:**
```python
# DetectionResult - resultado de execução
DetectionResult(
    detector_name="price_drop",     # NÃO 'detector'
    anomalias=[...],
    executed_at=datetime.now(),     # NÃO 'executado_em'
    execution_time_ms=150,
)

# AnomaliaDetectada - uma anomalia encontrada
AnomaliaDetectada(
    tipo=TipoAnomalia.SPREAD_ALTO,  # Enum, NÃO string
    severidade=Severidade.HIGH,
    valor_detectado=Decimal("150"), # OBRIGATÓRIO
    descricao="...",
    detector="price_drop",          # Campo 'detector', não 'detector_name'
    detalhes={...},                 # NÃO 'evidencia'
)
```

**Lição:** Manter referência rápida das dataclasses críticas.

### 5.3 Enums com `str, Enum`

**Problema:** Testes esperando `.value == "muito_negativo"` mas obtendo `"MUITO_NEGATIVO"`

**Causa:** Enum definido com uppercase:
```python
class Sentimento(str, Enum):
    MUITO_NEGATIVO = "MUITO_NEGATIVO"  # value é uppercase
```

**Lição:** Verificar como o enum foi definido antes de assumir o value.

### 5.4 Imports em `__init__.py`

**Problema:** `ImportError: cannot import name 'SCRAPERS_REGISTRY'`

**Causa:** Nome definido como `SCRAPERS` mas importado como `SCRAPERS_REGISTRY`.

**Solução:** Criar alias para compatibilidade:
```python
SCRAPERS = {"xp": XPScraper, ...}
SCRAPERS_REGISTRY = SCRAPERS  # Alias
```

**Lição:** Ao renomear, sempre criar alias para não quebrar imports existentes.

### 5.5 Mocking de Métodos Async

**Problema:** `health_check()` retornando `True` mesmo com mock de exception.

**Causa:** Mock aplicado em `_client` mas método usa `_get_client()` que cria novo client.

**Código problemático:**
```python
# ERRADO - _get_client() ignora _client pré-existente
with patch.object(collector, "_client") as mock_client:
    mock_client.get = AsyncMock(side_effect=Exception())
```

**Solução:**
```python
# CORRETO - mocka o método que retorna o client
with patch.object(collector, "_get_client", new=AsyncMock(side_effect=Exception())):
    result = await collector.health_check()
```

**Lição:** Entender o fluxo de criação de dependências antes de mockar.

### 5.6 Dataclasses com Muitos Campos Obrigatórios

**Problema:** `PrecoSecundario` tem 13 campos obrigatórios, testes ficam verbosos.

**Solução:** Helper factory com defaults sensatos:
```python
def _create_preco_secundario(**kwargs) -> PrecoSecundario:
    defaults = {...}  # Todos os campos com valores válidos
    defaults.update(kwargs)
    return PrecoSecundario(**defaults)

# Uso no teste - só especifica o que importa
preco = _create_preco_secundario(variacao_dia=Decimal("-5.0"))
```

**Lição:** Para dataclasses complexas, sempre criar factory helpers nos testes.

---

## 6. Métricas Finais

### Cobertura de Código

| Módulo | Cobertura |
|--------|-----------|
| `collectors/scrapers/` | 54% |
| `collectors/b3/` | 30% |
| `collectors/alternative/` | 32% |
| `collectors/sentiment/` | 77% |
| `detectors/` (Phase 4) | 72% |

### Testes por Categoria

| Arquivo | Testes |
|---------|--------|
| test_scrapers.py | 19 |
| test_b3.py | 18 |
| test_alternative.py | 14 |
| test_sentiment.py | 22 |
| test_phase4_detectors.py | 19 |
| **Total Phase 4** | **92** |
| **Total Projeto** | **325** |

---

## 7. Próximos Passos (Fase 5)

1. **Dashboard Web** - Visualização de anomalias e tendências
2. **API REST** - Endpoints para integração externa
3. **Alertas** - Notificações por email/Telegram
4. **Backtesting** - Validação de detectores com dados históricos
5. **ML Enhancement** - Modelo treinado para sentimento

---

*Documento gerado em Janeiro/2025*
