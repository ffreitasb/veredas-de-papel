# Diario de Desenvolvimento - Fase 3

**Projeto:** veredas de papel
**Fase:** 3 - Deteccao Avancada (Statistical + ML + Engine Unificada)
**Data:** 2026-01-23
**Testes:** 232 passando, 5 skipped (dependencias opcionais)
**Status:** COMPLETA

---

## Indice

1. [Visao Geral](#1-visao-geral)
2. [Decisoes de Arquitetura](#2-decisoes-de-arquitetura)
3. [Stack Tecnologico](#3-stack-tecnologico)
4. [Estrutura de Modulos](#4-estrutura-de-modulos)
5. [Implementacao Detalhada](#5-implementacao-detalhada)
6. [API REST de Deteccao](#6-api-rest-de-deteccao)
7. [Integracao CLI](#7-integracao-cli)
8. [Code Review e Debugging](#8-code-review-e-debugging)
9. [Aprendizados](#9-aprendizados)
10. [Conclusao e Status Final](#10-conclusao-e-status-final)

---

## 1. Visao Geral

### Objetivo da Fase 3

Evoluir o sistema de deteccao de anomalias de regras simples para um motor hibrido que combina:

- **Regras de Negocio**: Thresholds conhecidos do mercado financeiro
- **Analise Estatistica**: Decomposicao de series temporais, deteccao de change points
- **Machine Learning**: Deteccao de outliers nao-supervisionada

### Escopo Implementado

| Componente | Funcionalidade |
|------------|----------------|
| Statistical Detectors | STL Decomposition, Change Point (PELT), Rolling Z-Score |
| Feature Extractor | 21 features para ML (temporal, rolling, z-scores, contexto) |
| ML Detectors | Isolation Forest, DBSCAN Clustering |
| Detection Engine | Orquestracao unificada de todos os detectores |
| REST API | 5 endpoints para analise programatica |
| CLI Integration | Comandos `analyze` e `detectors` atualizados |

### Metricas Finais

| Metrica | Valor |
|---------|-------|
| Testes passando | 232 |
| Testes skipped | 5 (ruptures opcional) |
| Cobertura | 42% (foco em modulos criticos) |
| Detectores disponiveis | 8 (3 rules, 3 statistical, 2 ML) |
| Features extraidas | 21 |
| Endpoints API | 5 |

---

## 2. Decisoes de Arquitetura

### 2.1 Arquitetura de Detectores em Camadas

**Decisao:** Tres camadas de detectores com engine de orquestracao

```
                    +-------------------+
                    | DetectionEngine   |
                    | (orquestrador)    |
                    +--------+----------+
                             |
         +-------------------+-------------------+
         |                   |                   |
+--------v--------+  +-------v--------+  +-------v--------+
| RulesEngine     |  | StatisticalEng |  | MLEngine       |
| (Fase 1)        |  | (Fase 3)       |  | (Fase 3)       |
+-----------------+  +----------------+  +----------------+
| - SpreadAlto    |  | - STL Decomp   |  | - IsolationF   |
| - SaltoBrusco   |  | - ChangePoint  |  | - DBSCAN       |
| - Divergencia   |  | - RollingZ     |  |                |
+-----------------+  +----------------+  +----------------+
```

**Justificativa:**
1. **Separacao de responsabilidades**: Cada engine cuida de um tipo de analise
2. **Graceful degradation**: Se sklearn/ruptures nao instalados, ML/Statistical desabilitados
3. **Configuracao granular**: Usuario escolhe quais categorias habilitar
4. **Extensibilidade**: Novos detectores adicionados em sua categoria

### 2.2 Feature Engineering Centralizado

**Decisao:** Modulo `features.py` dedicado a extracao de features

**Alternativas Consideradas:**
- Features dentro de cada detector ML: Duplicacao, inconsistencia
- Features como metodo do modelo TaxaCDB: Acoplamento excessivo

**Justificativa:**
1. **Reusabilidade**: Mesmas features para Isolation Forest e DBSCAN
2. **Testabilidade**: Features testadas isoladamente
3. **Documentacao**: Lista clara de todas as features usadas
4. **Flexibilidade**: Facil adicionar/remover features

### 2.3 Dependencias Opcionais com Graceful Degradation

**Decisao:** sklearn e ruptures como dependencias opcionais

```python
# Verificacao no inicio do modulo
try:
    from sklearn.ensemble import IsolationForest
    SKLEARN_AVAILABLE = True
except ImportError:
    SKLEARN_AVAILABLE = False

class IsolationForestDetector(BaseDetector):
    def detect(self, taxas):
        if not SKLEARN_AVAILABLE:
            return DetectionResult.empty(
                detector_name=self.name,
                message="sklearn nao instalado"
            )
        # ... implementacao real
```

**Justificativa:**
1. **Instalacao minima**: Usuario basico nao precisa de ML
2. **Mensagens claras**: Sistema informa o que esta desabilitado
3. **Sem crashes**: ImportError tratado graciosamente
4. **Testes isolados**: @pytest.mark.skipif para testes de ML

### 2.4 Engine Result com Filtragem

**Decisao:** EngineResult com metodos de filtragem encadeados

```python
@dataclass
class EngineResult:
    results: list[DetectionResult]

    def filter_by_severity(self, min_severity: Severidade) -> "EngineResult":
        """Retorna novo EngineResult com anomalias filtradas."""
        filtered = [r.filter_by_severity(min_severity) for r in self.results]
        return EngineResult(results=filtered, ...)

    def filter_by_category(self, category: DetectorCategory) -> "EngineResult":
        """Filtra por categoria de detector."""
        ...
```

**Justificativa:**
1. **Imutabilidade**: Metodos retornam novo objeto, nao mutam
2. **Fluent API**: Encadeamento `result.filter_by_severity(HIGH).filter_by_category(ML)`
3. **Flexibilidade**: Filtragem pos-deteccao sem re-executar

---

## 3. Stack Tecnologico

### 3.1 Bibliotecas de Analise Estatistica

| Biblioteca | Versao | Proposito | Justificativa |
|------------|--------|-----------|---------------|
| statsmodels | >=0.14.0 | STL Decomposition | Referencia para decomposicao sazonal |
| ruptures | >=1.1.9 | Change Point Detection | PELT algorithm, eficiente O(n) |
| numpy | >=1.24.0 | Operacoes numericas | Base para todos os calculos |

### 3.2 Bibliotecas de Machine Learning

| Biblioteca | Versao | Proposito | Justificativa |
|------------|--------|-----------|---------------|
| scikit-learn | >=1.3.0 | Isolation Forest, DBSCAN | Padrao industria para ML |
| pandas | >=2.0.0 | DataFrames para features | Manipulacao eficiente de dados |

### 3.3 Por que STL Decomposition?

STL (Seasonal and Trend decomposition using Loess) separa serie temporal em:

```
Serie Original = Tendencia + Sazonalidade + Residuo
```

```python
from statsmodels.tsa.seasonal import STL

stl = STL(series, period=7)  # Sazonalidade semanal
result = stl.fit()

trend = result.trend      # Tendencia de longo prazo
seasonal = result.seasonal  # Padrao repetitivo
resid = result.resid      # Anomalias potenciais!
```

**Beneficios para deteccao de anomalias:**
- Residuo alto = ponto anomalo
- Remove falsos positivos de sazonalidade (ex: taxas mais altas as sextas)
- Detecta quebras de tendencia

### 3.4 Por que PELT para Change Points?

PELT (Pruned Exact Linear Time) detecta mudancas bruscas na serie:

```
                    Change Point
                         |
    Regime A             v        Regime B
    ~~~~~~~              |        ~~~~~~~~
    -------              |        --------
                         |
```

```python
import ruptures as rpt

algo = rpt.Pelt(model="rbf").fit(signal)
change_points = algo.predict(pen=3)  # Penalidade controla sensibilidade
```

**Por que PELT vs outros algoritmos:**
- **BinSeg**: O(n log n) mas aproximado
- **PELT**: O(n) e exato
- **BottomUp**: O(n^2), lento para series grandes

### 3.5 Por que Isolation Forest?

Isolation Forest detecta outliers pela "facilidade de isolar" um ponto:

```
Pontos normais: Muitos cortes para isolar
Anomalias: Poucos cortes para isolar (estao "sozinhas")
```

```python
from sklearn.ensemble import IsolationForest

model = IsolationForest(
    contamination=0.05,  # Esperamos 5% de anomalias
    random_state=42,
)
predictions = model.fit_predict(features)  # -1 = anomalia
scores = model.decision_function(features)  # Score de anomalia
```

**Vantagens:**
- Nao-supervisionado (nao precisa rotulos)
- Escala bem para muitas features
- Robusto a diferentes distribuicoes

### 3.6 Por que DBSCAN?

DBSCAN agrupa pontos densos e marca isolados como outliers:

```
    *  *
   * ** *        o  <- Outlier (nao pertence a nenhum cluster)
    * *

   ****
  * ** *     o   <- Outro outlier
   ****
```

```python
from sklearn.cluster import DBSCAN

model = DBSCAN(eps=0.5, min_samples=5)
labels = model.fit_predict(features)  # -1 = outlier
```

**Complementar ao Isolation Forest:**
- IF: Anomalias globais (pontos extremos)
- DBSCAN: Anomalias locais (pontos fora de clusters)

---

## 4. Estrutura de Modulos

### 4.1 `detectors/statistical.py` - Detectores Estatisticos

```python
# Configuracao compartilhada
@dataclass
class StatisticalThresholds:
    residual_zscore: float = 3.0    # STL: zscore do residuo
    min_samples: int = 30           # Minimo de pontos para analise
    penalty: float = 3.0            # PELT: penalidade para change points
    rolling_window: int = 14        # Janela para media movel

# Detectores individuais
class STLDecompositionDetector(BaseDetector):
    """Detecta anomalias via residuo da decomposicao STL."""

class ChangePointDetector(BaseDetector):
    """Detecta mudancas bruscas de regime via PELT."""

class RollingZScoreDetector(BaseDetector):
    """Detecta outliers com z-score sobre janela movel."""

# Orquestrador
class StatisticalEngine:
    """Executa todos os detectores estatisticos."""

    def run_all(self, taxas: Sequence[TaxaCDB]) -> list[DetectionResult]:
        results = []
        results.append(self.stl_detector.detect(taxas))
        results.append(self.change_point_detector.detect(taxas))
        results.append(self.rolling_zscore_detector.detect(taxas))
        return results
```

**Responsabilidades:**
- STL: Detectar residuos anomalos apos remover tendencia/sazonalidade
- ChangePoint: Detectar mudancas de regime (ex: banco entra em crise)
- RollingZ: Detectar spikes locais com contexto temporal

### 4.2 `detectors/features.py` - Extracao de Features

```python
@dataclass
class TaxaFeatures:
    """21 features extraidas de uma TaxaCDB."""

    # Identificacao
    taxa_id: int

    # Features temporais
    dia_semana: int           # 0-6
    dia_mes: int              # 1-31
    mes: int                  # 1-12
    trimestre: int            # 1-4

    # Features de valor
    percentual: float         # Taxa bruta
    spread_sobre_cdi: float   # Taxa - CDI
    prazo_dias: int

    # Features de rolling stats
    media_7d: float           # Media 7 dias
    std_7d: float             # Desvio padrao 7 dias
    media_30d: float
    std_30d: float

    # Features de variacao
    variacao_1d: float        # Variacao vs dia anterior
    variacao_7d: float        # Variacao vs 7 dias atras
    variacao_30d: float

    # Z-scores
    zscore_7d: float          # Desvio da media 7d
    zscore_30d: float         # Desvio da media 30d

    # Contexto de mercado
    posicao_mercado: float    # Percentil no mercado
    dist_media_mercado: float # Distancia da media
    dist_mediana_mercado: float

class FeatureExtractor:
    """Extrai features de uma lista de taxas."""

    def extract(self, taxa: TaxaCDB, ...) -> TaxaFeatures:
        """Extrai features de uma taxa."""

    def extract_to_dataframe(self, taxas) -> pd.DataFrame:
        """Extrai features de multiplas taxas para DataFrame."""

    def extract_to_matrix(self, taxas) -> np.ndarray:
        """Extrai features como matriz numpy para ML."""
```

**Design Decisions:**
- Dataclass imutavel para features
- Metodos de conversao para diferentes formatos (ML, analise)
- Features normalizadas (z-scores) para ML

### 4.3 `detectors/ml.py` - Detectores de Machine Learning

```python
@dataclass
class MLThresholds:
    contamination: float = 0.05     # % esperada de anomalias
    min_samples: int = 20           # Minimo para treinar
    isolation_n_estimators: int = 100
    dbscan_eps: float = 0.5
    dbscan_min_samples: int = 5

class IsolationForestDetector(BaseDetector):
    """Detecta anomalias globais via Isolation Forest."""

    def detect(self, taxas: Sequence[TaxaCDB], ...) -> DetectionResult:
        if not SKLEARN_AVAILABLE:
            return self._unavailable_result()

        features = self.feature_extractor.extract_to_matrix(taxas)

        model = IsolationForest(
            contamination=self.thresholds.contamination,
            n_estimators=self.thresholds.isolation_n_estimators,
        )

        predictions = model.fit_predict(features)
        scores = model.decision_function(features)

        anomalias = self._build_anomalies(taxas, predictions, scores)
        return DetectionResult(anomalias=anomalias, ...)

class DBSCANOutlierDetector(BaseDetector):
    """Detecta anomalias via clustering DBSCAN."""

class MLEngine:
    """Orquestra detectores de ML."""

    def run_all(self, taxas, ...) -> list[DetectionResult]:
        return [
            self.isolation_detector.detect(taxas, ...),
            self.dbscan_detector.detect(taxas, ...),
        ]
```

**Responsabilidades:**
- IsolationForest: Outliers globais (pontos muito diferentes)
- DBSCAN: Outliers de cluster (pontos isolados)
- MLEngine: Coordenacao e configuracao compartilhada

### 4.4 `detectors/engine.py` - Engine Unificada

```python
class DetectorCategory(Enum):
    RULES = "rules"
    STATISTICAL = "statistical"
    ML = "ml"

@dataclass
class EngineConfig:
    enable_rules: bool = True
    enable_statistical: bool = True
    enable_ml: bool = False  # Requer sklearn
    min_severity: Optional[Severidade] = None

@dataclass
class EngineResult:
    results: list[DetectionResult]
    config: EngineConfig
    execution_time_ms: float

    @property
    def all_anomalies(self) -> list[AnomaliaDetectada]:
        """Todas as anomalias de todos os detectores."""

    @property
    def has_anomalies(self) -> bool:

    def filter_by_severity(self, min_sev) -> "EngineResult":
        """Filtra anomalias por severidade minima."""

    def filter_by_category(self, cat) -> "EngineResult":
        """Filtra por categoria de detector."""

class DetectionEngine:
    """Engine principal que orquestra todos os detectores."""

    def __init__(self, config: Optional[EngineConfig] = None):
        self.config = config or EngineConfig()
        self.rules_engine = RulesEngine()
        self.statistical_engine = StatisticalEngine()
        self.ml_engine = MLEngine()

    def analyze(
        self,
        taxas_atuais: Sequence[TaxaCDB],
        taxas_anteriores: Optional[Sequence[TaxaCDB]] = None,
        media_mercado: Optional[Decimal] = None,
        cdi_atual: Optional[Decimal] = None,
    ) -> EngineResult:
        """Executa analise completa."""

    def analyze_single_detector(
        self,
        detector_name: str,
        taxas: Sequence[TaxaCDB],
        **kwargs,
    ) -> DetectionResult:
        """Executa um detector especifico."""

    @staticmethod
    def available_detectors() -> dict[DetectorCategory, list[str]]:
        """Lista todos os detectores disponiveis."""
```

**Fluxo de Execucao:**

```
analyze(taxas, ...)
    |
    +--[rules enabled?]---> RulesEngine.run_all()
    |                              |
    |                              v
    |                       DetectionResult[]
    |
    +--[statistical enabled?]---> StatisticalEngine.run_all()
    |                                    |
    |                                    v
    |                             DetectionResult[]
    |
    +--[ml enabled?]---> MLEngine.run_all()
    |                          |
    |                          v
    |                    DetectionResult[]
    |
    v
EngineResult(results=[...], execution_time=...)
```

---

## 5. Implementacao Detalhada

### 5.1 STL Decomposition Detector

**Algoritmo:**

```python
def detect(self, taxas: Sequence[TaxaCDB]) -> DetectionResult:
    # 1. Validar dados suficientes
    if len(taxas) < self.thresholds.min_samples:
        return DetectionResult.empty("Dados insuficientes")

    # 2. Preparar serie temporal
    series = pd.Series(
        [float(t.percentual) for t in taxas],
        index=[t.data_coleta for t in taxas],
    ).sort_index()

    # 3. Decomposicao STL
    stl = STL(series, period=7)  # Sazonalidade semanal
    result = stl.fit()

    # 4. Calcular z-scores dos residuos
    residuals = result.resid
    zscore = (residuals - residuals.mean()) / residuals.std()

    # 5. Identificar anomalias
    anomalias = []
    for i, z in enumerate(zscore):
        if abs(z) > self.thresholds.residual_zscore:
            anomalias.append(AnomaliaDetectada(
                tipo=TipoAnomalia.SEASONALITY_BREAK,
                severidade=self._calc_severity(z),
                taxa_referencia=taxas[i],
                descricao=f"Residuo anomalo: z-score={z:.2f}",
            ))

    return DetectionResult(anomalias=anomalias, ...)
```

**Calculo de Severidade:**

| Z-Score | Severidade |
|---------|------------|
| 3.0 - 4.0 | MEDIUM |
| 4.0 - 5.0 | HIGH |
| > 5.0 | CRITICAL |

### 5.2 Change Point Detector

**Algoritmo:**

```python
def detect(self, taxas: Sequence[TaxaCDB]) -> DetectionResult:
    if not RUPTURES_AVAILABLE:
        return self._unavailable_result()

    # 1. Preparar sinal
    signal = np.array([float(t.percentual) for t in taxas])

    # 2. Detectar change points com PELT
    algo = rpt.Pelt(model="rbf").fit(signal)
    change_points = algo.predict(pen=self.thresholds.penalty)

    # 3. Filtrar ultimo ponto (sempre retornado pelo ruptures)
    change_points = [cp for cp in change_points if cp < len(taxas)]

    # 4. Criar anomalias
    anomalias = []
    for cp in change_points:
        # Calcular magnitude da mudanca
        before = signal[max(0, cp-5):cp].mean()
        after = signal[cp:min(len(signal), cp+5)].mean()
        magnitude = abs(after - before)

        anomalias.append(AnomaliaDetectada(
            tipo=TipoAnomalia.CHANGE_POINT,
            severidade=self._calc_severity(magnitude),
            taxa_referencia=taxas[cp],
            descricao=f"Change point: {before:.2f}% -> {after:.2f}%",
        ))

    return DetectionResult(anomalias=anomalias, ...)
```

### 5.3 Isolation Forest Detector

**Fluxo Completo:**

```
taxas[] ---> FeatureExtractor ---> features matrix (n x 21)
                                         |
                                         v
                               IsolationForest.fit_predict()
                                         |
                                         v
                               predictions[] (-1 = anomalia)
                               scores[] (quanto menor, mais anomalo)
                                         |
                                         v
                               AnomaliaDetectada[]
```

**Codigo:**

```python
def detect(self, taxas, taxas_anteriores=None, ...):
    # 1. Extrair features
    features = self.feature_extractor.extract_to_matrix(
        taxas,
        taxas_anteriores=taxas_anteriores,
        media_mercado=media_mercado,
    )

    # 2. Treinar e predizer
    model = IsolationForest(
        contamination=self.thresholds.contamination,
        n_estimators=self.thresholds.isolation_n_estimators,
        random_state=42,
    )
    predictions = model.fit_predict(features)
    scores = model.decision_function(features)

    # 3. Criar anomalias para predictions == -1
    anomalias = []
    for i, (pred, score) in enumerate(zip(predictions, scores)):
        if pred == -1:
            anomalias.append(AnomaliaDetectada(
                tipo=TipoAnomalia.ISOLATION_ANOMALY,
                severidade=self._score_to_severity(score),
                taxa_referencia=taxas[i],
                descricao=f"Isolation score: {score:.4f}",
                dados_extras={"isolation_score": score},
            ))

    return DetectionResult(anomalias=anomalias, ...)
```

---

## 6. API REST de Deteccao

### 6.1 Endpoints Implementados

| Metodo | Endpoint | Proposito |
|--------|----------|-----------|
| GET | `/api/v1/detection/health` | Health check |
| GET | `/api/v1/detection/detectors` | Lista detectores disponiveis |
| POST | `/api/v1/detection/analyze` | Analise completa |
| POST | `/api/v1/detection/analyze/single` | Detector individual |
| GET | `/api/v1/detection/stats` | Estatisticas |

### 6.2 Schemas Pydantic

```python
# Request
class TaxaInput(BaseModel):
    id: int
    percentual: Decimal
    indexador: str
    prazo_dias: int
    data_coleta: datetime
    instituicao_id: Optional[int] = None

class DetectionRequest(BaseModel):
    taxas: list[TaxaInput]
    taxas_anteriores: Optional[list[TaxaInput]] = None
    media_mercado: Optional[Decimal] = None
    cdi_atual: Optional[Decimal] = None
    enable_rules: bool = True
    enable_statistical: bool = True
    enable_ml: bool = False
    min_severity: Optional[str] = None

# Response
class AnomaliaResponse(BaseModel):
    tipo: str
    severidade: str
    descricao: str
    confianca: float
    taxa_id: Optional[int]
    dados_extras: Optional[dict]

class DetectorResultResponse(BaseModel):
    detector_name: str
    category: str
    anomalias: list[AnomaliaResponse]
    execution_time_ms: float
    message: Optional[str]

class DetectionResponse(BaseModel):
    success: bool
    results: list[DetectorResultResponse]
    total_anomalies: int
    execution_time_ms: float
```

### 6.3 Exemplo de Uso

```bash
# Listar detectores
curl http://localhost:8000/api/v1/detection/detectors

# Response:
{
  "rules": ["spread_alto", "salto_brusco", "divergencia_mercado"],
  "statistical": ["stl_decomposition", "change_point", "rolling_zscore"],
  "ml": ["isolation_forest", "dbscan_outlier"]
}

# Analise completa
curl -X POST http://localhost:8000/api/v1/detection/analyze \
  -H "Content-Type: application/json" \
  -d '{
    "taxas": [...],
    "enable_ml": true,
    "min_severity": "HIGH"
  }'
```

---

## 7. Integracao CLI

### 7.1 Comando `analyze` Atualizado

```bash
veredas analyze [OPTIONS]

Options:
  --db PATH          Caminho do banco de dados
  -i, --if-id INT    Filtrar por ID de instituicao
  --ml               Habilitar detectores ML (requer sklearn)
  --severity TEXT    Severidade minima (low/medium/high/critical)
  --days INT         Dias de historico para analise [default: 30]
```

**Implementacao:**

```python
@app.command()
def analyze(
    db: Path = typer.Option(...),
    if_id: Optional[int] = typer.Option(None, "--if-id", "-i"),
    ml: bool = typer.Option(False, "--ml"),
    severity: Optional[str] = typer.Option(None, "--severity"),
    days: int = typer.Option(30, "--days"),
):
    """Executa analise de anomalias."""

    # 1. Validar banco
    if not db.exists():
        console.print("[red]Banco nao encontrado[/]")
        raise typer.Exit(1)

    # 2. Validar severidade
    min_severity = None
    if severity:
        try:
            min_severity = Severidade(severity.upper())
        except ValueError:
            console.print(f"[red]Severidade invalida: {severity}[/]")
            raise typer.Exit(1)

    # 3. Configurar engine
    config = EngineConfig(
        enable_rules=True,
        enable_statistical=True,
        enable_ml=ml,
        min_severity=min_severity,
    )
    engine = DetectionEngine(config)

    # 4. Exibir detectores habilitados
    _show_detectors_table(engine, ml)

    # 5. Instrucoes de uso
    console.print(Panel(
        "Para executar analise completa, use a API REST:\n"
        "  veredas web --port 8000\n"
        "  curl http://localhost:8000/api/v1/detection/analyze",
        title="Proximos Passos"
    ))
```

### 7.2 Comando `detectors` (Novo)

```bash
veredas detectors [OPTIONS]

Options:
  --category TEXT  Filtrar por categoria (rules/statistical/ml)
```

**Output:**

```
Detectores Disponiveis
=====================

Rules (3 detectores):
  - spread_alto
  - salto_brusco
  - divergencia_mercado

Statistical (3 detectores):
  - stl_decomposition
  - change_point
  - rolling_zscore

ML (2 detectores) [requer sklearn]:
  - isolation_forest
  - dbscan_outlier
```

---

## 8. Code Review e Debugging

### 8.1 Bugs Encontrados

| ID | Severidade | Descricao | Causa Raiz |
|----|------------|-----------|------------|
| BUG-001 | HIGH | Typo `has_anomalias` vs `has_anomalies` | Inconsistencia PT/EN |
| BUG-002 | MEDIUM | Testes CLI falhando apos refatoracao | Assinaturas alteradas |
| BUG-003 | LOW | TipoAnomalia faltando novos tipos | Modelo nao atualizado |

### 8.2 Analise de Causa Raiz

**Bug-001: has_anomalias vs has_anomalies**

```python
# test_statistical.py (ERRADO)
assert result.has_anomalias == True

# engine.py (CORRETO)
@property
def has_anomalies(self) -> bool:
    return any(r.has_anomalies for r in self.results)
```

**Processo de Debug:**
1. Teste falhou com `AttributeError: 'EngineResult' object has no attribute 'has_anomalias'`
2. Grep por `has_anomal` revelou inconsistencia
3. Correcao: replace_all `has_anomalias` -> `has_anomalies`

**Bug-002: CLI Tests Failing**

```python
# ANTES (test esperava)
result = runner.invoke(app, ["analyze", "--if", "Banco Master"])

# DEPOIS (novo parametro)
result = runner.invoke(app, ["analyze", "--if-id", "123", "--db", str(db_path)])
```

**Mudancas na assinatura:**
- `--if` (string) -> `--if-id` (int)
- `--db` agora obrigatorio
- Nova validacao de severidade
- Novo exit code para erros

**Correcao:**
- Reescrever testes para nova assinatura
- Adicionar mock de arquivo DB
- Testar cenarios de erro

### 8.3 Processo de Debug

```
1. Rodar testes completos
   $ pytest --tb=short

2. Identificar falhas
   FAILED tests/cli/test_commands.py::TestAnalyzeCommand::test_analyze_*

3. Ler teste falhando
   $ Read tests/cli/test_commands.py

4. Comparar com implementacao
   $ Read src/veredas/cli/main.py (funcao analyze)

5. Identificar divergencia
   - Teste usa --if, codigo usa --if-id
   - Teste nao passa --db

6. Corrigir testes
   $ Edit tests/cli/test_commands.py

7. Verificar correcao
   $ pytest tests/cli/test_commands.py -v
```

---

## 9. Aprendizados

### 9.1 Licoes Tecnicas

#### L1: Nomenclatura Consistente PT/EN

**Problema:** Mistura de `anomalias` (PT) e `anomalies` (EN) em propriedades.

**Regra Adotada:**
- Codigo interno: Ingles (`has_anomalies`, `filter_by_severity`)
- Mensagens usuario: Portugues ("Anomalia detectada", "Taxa anormal")
- Nomes de campos DB: Ingles (`detected_at`, `resolved`)

#### L2: Testes Devem Refletir Interface Publica

**Problema:** Testes quebraram quando assinatura do CLI mudou.

**Solucao:**
```python
# Testes devem ser atualizados junto com a interface
# Usar fixtures para parametros comuns

@pytest.fixture
def db_path(tmp_path):
    db = tmp_path / "test.db"
    db.touch()
    return db

def test_analyze_with_ml(runner, db_path):
    result = runner.invoke(app, ["analyze", "--ml", "--db", str(db_path)])
    assert result.exit_code == 0
```

#### L3: Graceful Degradation para Dependencias Opcionais

**Pattern:**
```python
# No topo do modulo
try:
    import sklearn
    SKLEARN_AVAILABLE = True
except ImportError:
    SKLEARN_AVAILABLE = False

# Na classe
class MLDetector:
    def detect(self, ...):
        if not SKLEARN_AVAILABLE:
            return DetectionResult.empty(
                message="sklearn nao instalado. pip install scikit-learn"
            )
        # ... implementacao normal
```

**Beneficios:**
- Instalacao minima funciona
- Erro claro sobre o que falta
- Testes podem usar `@pytest.mark.skipif`

#### L4: Feature Engineering Separado de Deteccao

**Anti-pattern:**
```python
class IsolationForestDetector:
    def _extract_features(self, taxa):  # Duplicado em cada detector
        ...
```

**Pattern Correto:**
```python
class FeatureExtractor:
    """Centraliza extracao de features."""

class IsolationForestDetector:
    def __init__(self):
        self.feature_extractor = FeatureExtractor()

    def detect(self, taxas):
        features = self.feature_extractor.extract_to_matrix(taxas)
```

#### L5: EngineResult Imutavel com Filtragem

**Anti-pattern:**
```python
def filter_by_severity(self, min_sev):
    self.results = [r for r in self.results if r.severity >= min_sev]
    return self  # Mutou o objeto!
```

**Pattern Correto:**
```python
def filter_by_severity(self, min_sev) -> "EngineResult":
    filtered = [r.filter_by_severity(min_sev) for r in self.results]
    return EngineResult(
        results=filtered,
        config=self.config,
        execution_time_ms=self.execution_time_ms,
    )  # Novo objeto, original intacto
```

### 9.2 Licoes de Arquitetura

#### A1: Engine Pattern para Orquestracao

```
+---------------+
| DetectionEngine| <-- Ponto de entrada unico
+-------+-------+
        |
        +---> RulesEngine
        +---> StatisticalEngine
        +---> MLEngine
```

**Beneficios:**
- Usuario interage com uma classe
- Configuracao centralizada
- Facil adicionar novas categorias

#### A2: Detector como Interface

```python
class BaseDetector(ABC):
    @property
    @abstractmethod
    def name(self) -> str: ...

    @abstractmethod
    def detect(self, taxas, **kwargs) -> DetectionResult: ...
```

**Beneficios:**
- Todos os detectores tem mesma interface
- Engine nao precisa saber detalhes
- Facil adicionar novos detectores

### 9.3 Licoes de Processo

#### P1: Testar Apos Cada Modulo

**Sequencia:**
1. Implementar modulo
2. Criar testes
3. Rodar testes
4. Commit
5. Proximo modulo

**Nao:**
1. Implementar tudo
2. Testar tudo
3. Debugar tudo (muito mais dificil)

#### P2: Documentar Decisoes Durante Implementacao

Este diario foi escrito durante a implementacao, nao depois.

**Beneficios:**
- Contexto fresco
- Nao esquece justificativas
- Util para onboarding

---

## 10. Conclusao e Status Final

### 10.1 Entregaveis

| Componente | Arquivos | Linhas | Testes |
|------------|----------|--------|--------|
| Statistical | statistical.py | ~650 | 29 |
| Features | features.py | ~390 | 15 |
| ML | ml.py | ~450 | 12 |
| Engine | engine.py | ~395 | 20 |
| API | detection.py, schemas.py | ~380 | 0* |
| CLI | main.py (updates) | ~100 | 8 |

*API testada via integracao

### 10.2 Detectores Disponiveis

| Categoria | Detector | Tipo Anomalia | Severidade |
|-----------|----------|---------------|------------|
| Rules | spread_alto | SPREAD_ALTO | HIGH/CRITICAL |
| Rules | salto_brusco | SALTO_BRUSCO | MEDIUM/HIGH |
| Rules | divergencia_mercado | DIVERGENCIA_MERCADO | MEDIUM/HIGH |
| Statistical | stl_decomposition | SEASONALITY_BREAK | MEDIUM-CRITICAL |
| Statistical | change_point | CHANGE_POINT | MEDIUM-CRITICAL |
| Statistical | rolling_zscore | ROLLING_OUTLIER | MEDIUM-HIGH |
| ML | isolation_forest | ISOLATION_ANOMALY | LOW-HIGH |
| ML | dbscan_outlier | CLUSTER_OUTLIER | LOW-HIGH |

### 10.3 Proximos Passos (Fase 4)

1. **Automacao**
   - Scheduler para coleta periodica
   - Triggers de alerta automaticos

2. **Producao**
   - Docker compose
   - CI/CD com GitHub Actions
   - Monitoramento com healthchecks

3. **Observabilidade**
   - Metricas de detectores (precision, recall)
   - Dashboard de performance
   - Logs estruturados

### 10.4 Debito Tecnico

- [ ] Testes de API (atualmente via integracao)
- [ ] Benchmarks de performance dos detectores
- [ ] Documentacao OpenAPI completa
- [ ] Cache de features extraidas
- [ ] Persistencia de modelos ML treinados

---

## Anexos

### A. Arquivos Criados/Modificados na Fase 3

```
src/veredas/
├── detectors/
│   ├── __init__.py          # Atualizado: exports
│   ├── statistical.py       # Novo: ~650 linhas
│   ├── features.py          # Novo: ~390 linhas
│   ├── ml.py                # Novo: ~450 linhas
│   └── engine.py            # Novo: ~395 linhas
├── storage/
│   └── models.py            # Atualizado: TipoAnomalia
├── api/
│   ├── __init__.py          # Atualizado: exports
│   ├── detection.py         # Novo: ~310 linhas
│   └── schemas.py           # Novo: ~245 linhas
├── web/
│   └── app.py               # Atualizado: include router
└── cli/
    └── main.py              # Atualizado: analyze, detectors

tests/
├── conftest.py              # Atualizado: fixtures
└── detectors/
    ├── test_statistical.py  # Novo: 29 testes
    ├── test_ml.py           # Novo: 15 testes
    └── test_engine.py       # Existente: 20 testes

Total: ~2.800 linhas de codigo novo
```

### B. Dependencias Adicionadas

```toml
# pyproject.toml
[project.optional-dependencies]
ml = [
    "scikit-learn>=1.3.0",
    "pandas>=2.0.0",
]
statistical = [
    "statsmodels>=0.14.0",
    "ruptures>=1.1.9",
]
full = [
    "veredas[web,ml,statistical]",
]
```

### C. Comandos Uteis

```bash
# Instalar com ML
pip install -e ".[ml]"

# Instalar completo
pip install -e ".[full]"

# Rodar testes (pula ML se sklearn nao instalado)
pytest tests/

# Rodar apenas testes de statistical
pytest tests/detectors/test_statistical.py -v

# Verificar detectores disponiveis
veredas detectors

# Analise com ML habilitado
veredas analyze --ml --db ~/.veredas/veredas.db
```

---

**Autor:** Claude Opus 4.5
**Data:** 2026-01-23
**Versao:** 1.0
