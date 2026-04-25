# Decisões técnicas — não implementações deliberadas

Registro de itens que foram avaliados e conscientemente descartados. A ausência de cada um é uma decisão, não um esquecimento.

---

## Service layer (camada de serviço)

**O que seria:** Uma camada `services/` entre as rotas FastAPI e o repositório, com classes como `TaxaService`, `AnomaliaService`.

**Por que não foi feito:** Nenhum endpoint atual precisa de transações compostas, orquestração entre múltiplos repositórios, ou lógica que não caiba numa função de rota. O padrão `route → repository → model` cobre todos os casos existentes. Adicionar uma camada de serviço agora introduziria indireção sem benefício observável — cada método de serviço seria um `pass-through` para o repositório correspondente.

**O que justificaria a revisão:** Uma operação que precise escrever em duas tabelas de forma atômica (e.g., criar anomalia + atualizar score de risco em transação única), ou lógica de negócio compartilhada entre três ou mais endpoints distintos.

---

## Typed filter dataclasses no repositório

**O que seria:** Classes como `TaxaFilter(indexador=..., prazo_min=..., if_id=...)` substituindo os `dict[str, Any]` passados às queries do repositório.

**Por que não foi feito:** Os filtros são internos ao repositório e não fazem parte de nenhum contrato de API pública. O `dict` funciona, os testes cobrem os caminhos, e a validação dos valores de entrada acontece nas rotas (onde o FastAPI/Pydantic já tipam os parâmetros). Dataclasses de filtro adicionariam ~200 linhas de boilerplate para zero benefício em runtime — apenas duplicariam a tipagem que as assinaturas de função já expressam.

**O que justificaria a revisão:** Os filtros precisarem ser serializados, cacheados, passados entre camadas, ou se a quantidade de parâmetros de filtro crescer a ponto de tornar o `dict` ilegível nas chamadas.

---

## H1-4: lazy imports do módulo estatístico e de ML

**O que seria:** Importar `statsmodels`, `ruptures`, `sklearn` etc. de forma lazy (dentro dos métodos `detect()`, não no nível do módulo), reduzindo o tempo de startup da aplicação.

**Por que não foi feito:** `enable_statistical` e `enable_ml` são `False` por padrão em `EngineConfig`. Os módulos só são importados se o código de detecção for carregado, e o servidor web não invoca `DetectionEngine` no startup. A otimização resolveria um problema de 0ms percebido: o usuário não espera pelo import de `statsmodels` em nenhum fluxo crítico atual.

**O que justificaria a revisão:** O servidor web passar a instanciar `DetectionEngine` no startup (e.g., para warmup de modelos), ou os detectores estatísticos serem habilitados por padrão.

---

## DOM-02: threshold dinâmico de spread baseado na Selic

**O que seria:** Ajustar automaticamente os thresholds de `SpreadDetector` conforme a taxa Selic vigente — spreads "normais" em Selic a 10% são diferentes dos spreads em Selic a 14%.

**Por que não foi feito:** Nenhum usuário solicitou. O threshold estático funciona para os casos reais detectados até agora (Banco Master, spreads de 120–185% CDI). Implementar ajuste dinâmico exigiria integração com a API do Banco Central para obter a Selic corrente, aumentando dependências externas e superfície de falha sem validação de que o benefício é real.

**O que justificaria a revisão:** Evidência de falsos positivos ou falsos negativos correlacionados com variações da Selic, ou um usuário reportar que um alerta foi disparado num período de Selic alta em que o spread observado era de fato normal.

---

## DBSCANOutlierDetector em produção (dataset atual)

**Precondição documentada:** ≥200 emissores ativos únicos no dataset.

**Por que não é útil agora:** DBSCAN é um algoritmo de clustering por densidade. Com menos de ~200 emissores únicos no espaço de 21 features escaladas, não há densidade suficiente para formar clusters estáveis — todos os pontos tendem a receber label=-1 (outlier), gerando falsos positivos em massa. O mercado brasileiro tem ~50–150 emissores de CDB monitorados ativamente; a precondição provavelmente não será atingida no curto/médio prazo. O detector tem um guard em `detect()` que retorna resultado vazio abaixo de 200 emissores únicos.

**O que justificaria a revisão:** O dataset passar a incluir >200 emissores distintos com histórico contínuo de taxas.

---

## 5ª e 6ª fontes de scraping

**O que seria:** Adicionar scrapers para Nubank, C6, Modalmais, Órama ou outras plataformas de distribuição antes de estabilizar os quatro existentes (BTG, XP, Inter, Rico).

**Por que não foi feito:** As quatro fontes atuais ainda não foram validadas em uso real contínuo. Adicionar fontes antes de validar as existentes comporia o débito técnico: cada scraper quebra com mudanças de layout, exige testes de parser, e tem CNPJ/segmento próprio para classificar. Cobertura ampla não-confiável é pior do que cobertura restrita confiável para um sistema de alerta.

**O que justificaria a revisão:** As 4 fontes estiverem operando com uptime aceitável por 30+ dias sem regressões de parser. A escolha da próxima fonte deve ser guiada por qual instituição tem o histórico mais relevante de comportamento anômalo, não pela facilidade de scraping.
