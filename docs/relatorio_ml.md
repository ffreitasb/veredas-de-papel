# Relatório de Análise do Pipeline de Machine Learning
## Veredas de Papel — Monitor de CDB Brasileiro

**Data:** 2026-04-24
**Autor:** Análise técnica automatizada (Claude Sonnet 4.6)
**Escopo:** `detectors/features.py`, `detectors/ml.py`, `detectors/statistical.py`, `detectors/rules.py`, `detectors/engine.py`, `catalog.py`

---

## Sumário Executivo

O pipeline de detecção de anomalias do Veredas de Papel é funcionalmente correto e demonstra boas decisões de design em várias frentes: separação clara de responsabilidades entre camadas (regras, estatística, ML), tiers de emissores com thresholds diferenciados por perfil de risco, e uma deduplicação que pelo menos existe. No entanto, a análise técnica detalhada revela **um problema de alta severidade que compromete toda a camada de ML** (treino e scoring no mesmo conjunto sem separação temporal), **três problemas de média severidade** com impacto direto na taxa de falsos positivos, e **seis achados de baixa severidade** que afetam precisão e manutenibilidade.

O achado mais crítico é que o Isolation Forest e o DBSCAN treinam e avaliam sobre o **mesmo conjunto de dados em cada chamada**, tornando os scores de anomalia matematicamente circulares e invalidando a interpretação probabilística do parâmetro `contamination`. Isso não impede o sistema de funcionar, mas significa que a camada de ML está detectando "quem é diferente dos outros neste lote" e não "quem é diferente do comportamento histórico normal" — uma distinção fundamental para detecção de fraude/risco.

---

## Tabela de Achados

| # | Arquivo | Achado | Severidade | Categoria |
|---|---------|--------|------------|-----------|
| ML-01 | `ml.py` | Treino e scoring no mesmo conjunto: contaminação circular e ausência de baseline histórico | HIGH | Metodologia ML |
| ML-02 | `ml.py` | `contamination=0.05` hardcoded: implica sempre 5% de anomalias independente dos dados reais | HIGH | Metodologia ML |
| ST-01 | `statistical.py` | STL com `period=5` dias úteis em série irregular/esparsa: decomposição pode produzir resíduos espúrios | MEDIUM | Detectores Estatísticos |
| ST-02 | `statistical.py` | Rolling Z-Score com `min_periods=3`: instável com poucos dados e janela fixa não adaptativa à Selic | MEDIUM | Detectores Estatísticos |
| ENG-01 | `engine.py` | Deduplicação suprime tipo de anomalia: mantém apenas a mais severa por `(if_id, taxa_id, data)`, perdendo informação de co-ocorrência entre detectores | MEDIUM | Orquestração |
| FE-01 | `features.py` | Alta multicolinearidade entre features derivadas: `rolling_mean_7d`, `rolling_mean_14d`, `rolling_mean_30d`, `z_score_7d`, `z_score_30d` são linearmente dependentes | LOW | Feature Engineering |
| FE-02 | `features.py` | Preenchimento de `None` com zero (`or 0`) mascara dados ausentes como ausência de variação | LOW | Feature Engineering |
| FE-03 | `features.py` | Features temporais cíclicas (`dia_semana`, `mes`) tratadas como lineares, sem encoding seno/cosseno | LOW | Feature Engineering |
| ST-03 | `statistical.py` | PELT com `pen=10.0` hardcoded: sem base empírica documentada para séries de CDB brasileiro | LOW | Detectores Estatísticos |
| DOM-01 | `rules.py` | Detector de variação ignora quedas de taxa: `variacao <= 0` retorna None — queda brusca também é sinal de risco | LOW | Calibração de Domínio |
| DOM-02 | `catalog.py` + `rules.py` | Thresholds CDI% para Selic alta não revisados: 130%/150% CDI como HIGH/CRITICAL pode ser adequado para Selic a 10,5%, mas não há mecanismo para ajuste dinâmico conforme Selic varia | LOW | Calibração de Domínio |

---

## Análise Técnica Detalhada

### 1. Qualidade das Features (`features.py`)

#### FE-01 — Multicolinearidade entre features derivadas (LOW)

O vetor gerado por `to_array()` contém 21 dimensões, mas várias são derivadas umas das outras com quase zero informação incremental:

- `rolling_mean_7d`, `rolling_mean_14d`, `rolling_mean_30d` são médias do mesmo valor `percentual` em janelas aninhadas. A correlação entre elas, dependendo da volatilidade da série, costuma ficar acima de 0.85.
- `z_score_7d = (percentual - rolling_mean_7d) / rolling_std_7d` e `z_score_30d` estão completamente determinados por `percentual`, `rolling_mean_*d` e `rolling_std_*d`, que já estão no vetor.
- `diff_7d` e `pct_change_7d` carregam essencialmente a mesma informação para taxas de CDB onde os valores raramente cruzam zero.

Para o Isolation Forest isso é problemático porque, ao usar StandardScaler + IsolationForest em espaço euclidiano, dimensões altamente correlacionadas inflam artificialmente o peso desse eixo. O modelo "vê" a mesma informação de variação múltiplas vezes, o que faz com que anomalias em `percentual` absoluto sejam sub-detectadas em relação ao que o conjunto de features promete.

**Recomendação:** Aplicar seleção de features antes de passar ao modelo. Uma abordagem pragmática é usar VIF (Variance Inflation Factor) com limiar 5 para eliminar features redundantes, ou reduzir manualmente para: `[percentual, diff_1d, z_score_30d, percentile_30d, diff_from_market_mean, dia_semana, fim_de_mes]` — 7 features cobrindo os sinais sem redundância.

#### FE-02 — Substituição de `None` por zero mascara ausência de dados (LOW)

Em `to_array()`, o padrão `self.rolling_mean_7d or 0` converte `None` em `0.0`. Para features de variação como `diff_1d`, `diff_7d` e `pct_change_7d`, o valor `0` é semanticamente válido e significa "sem variação". O modelo não consegue distinguir "sem variação" de "dado ausente por ser o primeiro ponto da série".

Isso afeta especialmente os primeiros 30 dias de histórico de uma IF: todas as features de janela longa ficam zeradas, fazendo os primeiros pontos parecerem artificialmente "normais" para o modelo — exatamente quando o risco de dados espúrios é maior.

**Recomendação:** Usar `np.nan` para `None` e aplicar um `SimpleImputer` ou `IterativeImputer` dentro do pipeline, ou sinalizar explicitamente a ausência com uma feature binária `has_30d_history`.

#### FE-03 — Features temporais cíclicas sem encoding adequado (LOW)

`dia_semana` (0–6) e `mes` (1–12) são passados como inteiros. Isso cria descontinuidades artificiais: o modelo "vê" segunda-feira (0) e domingo (6) como opostos, e dezembro (12) e janeiro (1) como extremos opostos de um eixo linear.

Para séries de CDB isso tem impacto limitado, porque os padrões intra-semana em taxas de renda fixa são fracos. Mas para `fim_de_mes` (que já é bool) e `dia_mes`, o efeito de fim de mês não é linear — os dias 29, 30, 31 têm comportamento similar entre si.

**Recomendação:** Transformar `dia_semana` e `mes` em pares seno/cosseno: `sin(2π * x / max_x)`, `cos(2π * x / max_x)`. Para `dia_mes`, o flag `fim_de_mes` já captura o padrão relevante de forma binária.

---

### 2. IsolationForest e DBSCAN (`ml.py`)

#### ML-01 — Treino e scoring no mesmo conjunto (HIGH)

Este é o achado mais crítico do pipeline. Em `detect_with_features()`:

```python
self._model = IsolationForest(contamination=self.thresholds.if_contamination, ...)
self._model.fit(X_scaled)
scores = self._model.decision_function(X_scaled)  # mesmo X
```

O modelo treina e avalia sobre o mesmo conjunto `X_scaled`. No contexto de anomalia, isso tem uma consequência específica: o modelo aprende a estrutura de densidade **incluindo os pontos anômalos**, e então avalia esses mesmos pontos. O resultado é que pontos verdadeiramente anômalos têm seu score de isolamento atenuado — o modelo "acomodou" a anomalia durante o treino.

Para o Isolation Forest isso é menos grave do que em modelos supervisionados (porque IF já é robusto a outliers no treino), mas cria um problema mais profundo: **não existe conceito de "normalidade histórica"**. Se toda uma semana de taxas estiver anômalas (ex.: choque de Selic), o modelo aprende que aquelas taxas são normais para aquele lote. A detecção vira relativa ao lote corrente, não ao histórico.

O correto para um monitor de risco seria:

1. Treinar o modelo em dados históricos validados como normais (ex.: 90 dias de história sem anomalias confirmadas).
2. Serializar o modelo treinado (joblib/pickle).
3. Usar `decision_function()` apenas no novo dado, nunca retreinar por padrão.
4. Retreinar periodicamente (ex.: semanalmente) com dados do período de normalidade mais recente.

O DBSCAN tem o mesmo problema, agravado: DBSCAN não tem conceito de "predição" para novos pontos — ele só pode classificar pontos dentro do conjunto treinado. O uso atual (treinar e classificar no mesmo lote) é a única forma correta de usar DBSCAN online, mas isso confirma que DBSCAN é fundamentalmente inadequado para detecção de novos pontos fora do lote.

#### ML-02 — `contamination=0.05` hardcoded (HIGH)

`contamination=0.05` informa ao Isolation Forest que exatamente 5% dos dados de treino são anomalias. O sklearn usa isso para calibrar o threshold de decisão: pontos no quintil inferior dos scores de anomalia são marcados como outliers.

O problema é duplo:

1. **Auto-cumprimento:** Independente dos dados, sempre serão identificados aproximadamente 5% como anômalos. Em períodos de mercado totalmente normal, isso produz falsos positivos. Em crises reais onde 20% das taxas estão anômalas, o modelo suprime 15% dos alertas reais.

2. **Sem calibração empírica:** Para o mercado de CDB brasileiro, a taxa base de anomalias verdadeiras é desconhecida e provavelmente muito menor que 5% em períodos normais (talvez 0.5–1%). Isso cria um viés estrutural para falsos positivos.

**Recomendação imediata:** Usar `contamination="auto"` do sklearn, que calibra o threshold de decisão em `0.0` (score médio de anomalia dos dados de treino) em vez de forçar um percentil fixo. Isso não resolve o problema do treino online, mas elimina a assunção de 5% de anomalias.

**Recomendação definitiva:** Treinar offline com histórico rotulado ou validado, e usar scores contínuos de `decision_function()` para alertas graduados em vez do binário `predict()`.

---

### 3. Detectores Estatísticos (`statistical.py`)

#### ST-01 — STL com série irregular e `period=5` (MEDIUM)

O STL (`STLDecompositionDetector`) usa `period=5` assumindo uma sazonalidade semanal de 5 dias úteis. Há três problemas:

**Problema A — Irregularidade temporal:** A série é criada como `pd.Series(values, index=pd.DatetimeIndex(dates))` sem reindexação para frequência regular. Se uma IF não reportar taxas em determinados dias (feriados, fins de semana, dias sem coleta), o índice terá gaps. O STL da statsmodels é sensível a séries irregulares — sem `period` bem calibrado para o gap real, a componente sazonal estimada absorve a tendência e vice-versa.

**Problema B — Período sazonal inadequado:** CDBs de renda fixa têm sazonalidade fraca ou inexistente em escala semanal. A sazonalidade dominante em taxas de CDB é mensal (datas de COPOM, reuniões do BCB, vencimento de meses) e semestral. Usar `period=5` pode fazer o STL detectar pseudossazonalidade em ruído, inflando os resíduos de forma não-informativa.

**Problema C — Mínimo de 14 observações:** Com `period=5`, o STL da statsmodels requer pelo menos `2 * period + 1 = 11` observações, então 14 é suficiente. Mas com 14 pontos irregulares, a componente sazonal é altamente instável — qualquer ponto faltante no meio da série pode fazer o STL falhar silenciosamente.

O comportamento atual quando o STL falha é `logger.debug(...)` sem propagar o erro, o que significa que em muitos casos práticos este detector pode estar silenciosamente produzindo zero anomalias.

**Recomendação:** Antes de passar ao STL, reindexar a série para frequência diária com `resample('D').last()` e preencher gaps com `interpolate(method='linear')`. Considerar aumentar `period` para 21 (mensal) ou desabilitar o STL para IFs com menos de 60 observações.

#### ST-02 — Rolling Z-Score com `min_periods=3` e janela fixa (MEDIUM)

O `RollingZScoreDetector` usa `rolling(window=14, min_periods=3)`. O problema é que com apenas 3 observações, o desvio padrão tem 2 graus de liberdade e é altamente instável. Em séries com poucos dados, qualquer variação relativamente pequena produz z-scores altos.

Além disso, a janela de 14 dias é **fixada independente da volatilidade do período**. Em períodos de alta Selic com ajustes frequentes de COPOM (ex.: Selic movendo 50–75bps por reunião), a média e desvio padrão de 14 dias vão capturar uma transição de regime, fazendo com que taxas absolutamente normais para o novo nível de Selic produzam z-scores elevados por até 2 semanas após cada decisão do COPOM.

**Recomendação:** Aumentar `min_periods` para pelo menos 7. Considerar uma janela dupla: janela curta (7d) para detectar saltos rápidos, janela longa (60d) para a linha de base do regime. A detecção de anomalia seria sobre o desvio da janela curta em relação à longa.

#### ST-03 — PELT com `pen=10.0` sem base empírica (LOW)

A penalidade `pen=10.0` no algoritmo PELT determina a sensibilidade para detecção de change points: valores menores detectam mais mudanças (mais falsos positivos), valores maiores são mais conservadores. O valor `10.0` é o default sugerido na documentação do `ruptures`, mas é calibrado para séries genéricas normalizadas.

Para séries de taxa de CDB em % do CDI (tipicamente 90–150), a escala dos dados é muito diferente de uma série normalizada. O modelo `rbf` internamente normaliza por variância, então a penalidade efetiva depende da variância da série. Sem calibração específica para o domínio, não é possível afirmar que `pen=10.0` é adequado.

**Recomendação:** Documentar a base para o valor escolhido. Idealmente, calibrar com dados históricos usando a regra `pen = log(n) * σ²` (critério BIC), ou usar a penalidade linear do ruptures com critério automático.

---

### 4. Deduplicação e Agregação (`engine.py`)

#### ENG-01 — Deduplicação destrói informação de co-ocorrência (MEDIUM)

O método `_deduplicate()` agrupa anomalias por `(if_id, taxa_id, data)` e mantém apenas a de maior severidade. Isso resolve o problema de ruído (a mesma taxa não aparece 5 vezes), mas destrói uma informação valiosa: **a co-ocorrência de múltiplos detectores independentes na mesma taxa é evidência muito mais forte de anomalia real**.

Por exemplo: se `spread_detector` (HIGH), `rolling_zscore_detector` (MEDIUM) e `isolation_forest_detector` (MEDIUM) apontam para a mesma taxa, a anomalia resultante seria HIGH (da regra de spread). Mas o fato de 3 detectores independentes concordarem — cada um usando metodologia diferente — elevaria a confiança para próximo de CRITICAL.

O comportamento atual também tem um efeito perverso: detectores ML e estatísticos que corroboram uma anomalia de regra são silenciados, fazendo parecer que as regras estão "dominando" quando na verdade há consenso.

**Recomendação:** Mudar a estratégia de deduplicação para um modelo de votação ponderada:
- 1 detector: severidade original
- 2 detectores independentes concordando: elevar um nível (MEDIUM → HIGH)
- 3+ detectores concordando: elevar dois níveis ou forçar HIGH
- Armazenar a lista de detectores que votaram no campo `detalhes` da anomalia final

#### Ausência de timeout efetivo na detecção

O `EngineConfig` define `detection_timeout_ms=30000` (linha 72 do engine.py), mas este campo nunca é usado na lógica de `analyze()`. Os detectores ML (especialmente DBSCAN em datasets grandes) podem exceder facilmente 30s sem que haja interrupção. Isso não é um achado de ML estritamente, mas afeta a confiabilidade operacional do pipeline.

---

### 5. Calibração para o Domínio Financeiro Brasileiro

#### DOM-01 — Quedas bruscas ignoradas pelo VariacaoDetector (LOW)

Em `_check_variacao()`, a regra retorna `None` para `variacao <= 0`:

```python
if variacao <= 0:
    return None
```

Isso significa que uma queda brusca de taxa — por exemplo, uma IF que de repente reduz de 120% CDI para 90% CDI — não dispara nenhum alerta. No domínio de risco de crédito, uma queda abrupta pode ser tão ou mais relevante quanto uma alta: pode indicar que a IF está com dificuldade de captar (reduziu a oferta) ou que houve um repricing de risco não comunicado.

**Recomendação:** Tratar variações negativas com thresholds específicos — ou no mínimo o mesmo threshold com severidade reduzida (ex.: queda > 10pp em 7 dias → LOW, queda > 20pp → MEDIUM).

#### DOM-02 — Thresholds de spread sem mecanismo de ajuste dinâmico à Selic (LOW)

Os thresholds de spread estão definidos como % do CDI (ex.: 130% CDI = HIGH para emissores PEQUENO). Essa escala percentual tem uma vantagem: é agnóstica ao nível absoluto da Selic. Se a Selic está a 10,5% e um CDB paga 130%, isso equivale a 13,65% ao ano bruto — que é alto. Se a Selic está a 13,75% e um CDB paga 130%, são 17,875% ao ano — ainda mais alto em termos absolutos, mas a dinâmica do mercado é diferente.

O problema maior é que os thresholds dos diferentes tiers (bancão: 108%, fintech: 118%, pequeno: 130%) parecem calibrados de forma heurística sem documentação de base empírica. Em períodos de stress de liquidez (como ocorreu com algumas fintechs em 2022–2023), taxas de 140–150% CDI foram vistas em emissores PEQUENO/MEDIO sem necessariamente indicar fraude — eram simplesmente o preço de mercado.

Os thresholds atuais para **BANCAO** (HIGH: 108%, CRITICAL: 120%) parecem bem calibrados — um bancão sistêmico raramente ultrapassa 105% CDI no varejo, então 108% já é sinal forte. Para **FINTECH** (HIGH: 118%), há risco de falsos positivos: em períodos de aperto monetário, fintechs como Inter e Nubank rotineiramente oferecem 110–115% CDI, o que aproxima do threshold de 118%.

**Recomendação:** Documentar a base empírica dos thresholds com referências a dados históricos. Criar um mecanismo de revisão trimestral explícito no código (ex.: comentário com data de última revisão e referência à Selic vigente). Para fintechs, considerar elevar o threshold de HIGH para 122–125%.

---

## Recomendações Prioritárias

### Prioridade 1 — Separar treino de scoring no Isolation Forest (HIGH, ~2 dias)

Criar um `IsolationForestBaseline` que:
1. Recebe um conjunto de dados históricos validados como normais
2. Treina e serializa o modelo com joblib
3. Expõe um método `score(features)` que usa o modelo serializado sem retreinar

Adicionar um CLI `veredas baseline build --days=90` para construir o baseline inicial.

### Prioridade 2 — Mudar `contamination` para `"auto"` (HIGH, 30 min)

Mudança de uma linha em `ml.py`:
```python
# Antes
contamination=self.thresholds.if_contamination,  # 0.05
# Depois
contamination="auto",
```
Isso elimina a assunção de 5% de anomalias sem requerer baseline histórico.

### Prioridade 3 — Deduplicação por votação em vez de supressão (MEDIUM, ~4h)

Refatorar `_deduplicate()` para computar um score de confiança baseado no número de detectores que concordam, e usar esse score para elevar a severidade da anomalia final.

### Prioridade 4 — Reindexação regular antes do STL (MEDIUM, ~2h)

Na função `_analyze_series()` do `STLDecompositionDetector`, adicionar:
```python
series = series.resample('D').last().interpolate(method='linear')
```
antes de passar ao `STL()`.

### Prioridade 5 — Aumentar `min_periods` do Rolling Z-Score (MEDIUM, 15 min)

```python
rolling_mean = series.rolling(window=window, min_periods=max(7, window // 3)).mean()
rolling_std  = series.rolling(window=window, min_periods=max(7, window // 3)).std()
```

### Prioridade 6 — Reduzir multicolinearidade de features (LOW, ~3h)

Reduzir o vetor de features de 21 para 8–10 dimensões, eliminando features derivadas redundantes e mantendo apenas as de maior poder discriminativo.

---

## Considerações Finais

O pipeline tem uma arquitetura sólida: a separação em três camadas (regras, estatística, ML) com agregação no engine é a abordagem correta para um domínio onde interpretabilidade importa. As regras de negócio são a camada mais confiável e bem calibrada. Os detectores estatísticos têm problemas de parametrização mas a lógica é correta. A camada de ML, como implementada, funciona como um detector de outliers **relativo ao lote corrente** — o que é menos do que o prometido pelo Isolation Forest em seu uso canônico, mas ainda agrega sinal em cenários onde várias IFs são analisadas simultaneamente.

O investimento mais importante é a separação treino/scoring com persistência de modelo, que transformaria a camada de ML de "detector de outliers de lote" para "detector de desvio do comportamento histórico normal" — que é o que o domínio financeiro exige.
