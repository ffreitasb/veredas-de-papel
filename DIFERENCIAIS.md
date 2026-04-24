<div align="center">
  <img src="assets/veredas_icon.png" alt="veredas de papel" width="72">
</div>

# Por que veredas de papel é diferente

> *"O sertão é do tamanho do mundo."*
> — João Guimarães Rosa, Grande Sertão: Veredas

O mercado de renda fixa brasileiro é um sertão: vasto, sem mapas, com caminhos que parecem seguros e escondem o abismo. Este documento registra a pesquisa de due diligence que fizemos antes de construir:
> mapeamento do ecossistema existente, tentativas de reutilizar fontes de dados disponíveis
> e a conclusão de que o que estamos construindo não tem equivalente em código aberto.

---

## O ecossistema de dados financeiros brasileiro para Python

### Bibliotecas existentes

| Biblioteca | O que cobre | CDB? | Status |
|-----------|------------|------|--------|
| `yfinance` | Ações brasileiras (B3) via Yahoo Finance | Não | Ativo |
| `brapi` / `brapi-py` | Ações, FIIs, fundos via BRAPI | Não | Ativo |
| `investpy` | Ações, Tesouro Direto, fundos | Não | **Descontinuado** |
| `python-bcb` | Séries SGS do Banco Central (CDI, IPCA, Selic) | Apenas taxa de referência | Ativo |
| `anbima-api` | Debêntures, CRI, CRA via ANBIMA | Não | Requer cadastro ANBIMA |
| [`pybov`](https://github.com/glourencoffee/pybov) | Ações listadas, cotações históricas B3, boletim diário da bolsa | Não | Abandonado (último commit: mai/2023, 3 stars) |

**Nenhuma biblioteca Python cobre CDB como ativo monitorável — nem mercado primário, nem secundário.**

### Por que pybov não ajuda

`pybov` é um wrapper em torno da API pública do site da B3 focado em *equities* e derivativos listados. CDB não é um produto da B3 — é emitido e gerido no sistema CETIP/B3, com acesso restrito a participantes qualificados. O escopo da biblioteca é inteiramente mercado de capitais: ações, opções, contratos futuros. Renda fixa bancária está completamente fora do seu design.

---

## A busca por fontes de CDB secundário — todas as opções eliminadas

Antes de construir o coletor B3 do zero, validamos exaustivamente cada alternativa disponível:

| Fonte | O que tentamos | Resultado |
|-------|---------------|-----------|
| **B3 API** (`developers.b3.com.br`) | API "CDB" v1.0.2 existe no catálogo | B2B exclusivo — requer contrato institucional e OAuth2 pago. Zero acesso sem credencial corporativa. |
| **ANBIMA API** (`api.anbima.com.br`) | Endpoints de precificação | Cobre debêntures, CRI, CRA, LF — **CDB não é marcado a mercado pela ANBIMA**. Produto errado. |
| **CETIP FTP público** | Feed de fechamento de CDB via FTP | **Não existe.** B3 absorveu a CETIP em 2017; todos os feeds migraram para o portal B2B fechado. |
| **Yubb** (`yubb.com.br`) | Endpoint JSON de agregação | Bloqueio por bot-protection (HTTP 403 sistemático). Mesmo com Playwright exigiria session cookie e perfil autêntico. Cobre apenas mercado primário. |
| **Status Invest** | Seção de CDB | **Não tem CDB.** Foco em ações, FIIs e Tesouro Direto. |
| **Mais Retorno** | Comparador de renda fixa | API comercial paga. CDB não está no sitemap público. |
| **Tesouro Direto** | JSON de preços e taxas | Endpoint fechado (HTTP 403) desde redesign 2024–2025. Cobre apenas títulos públicos. |

**Conclusão:** CDB secundário — o preço de um CDB negociado antes do vencimento — é uma **lacuna estrutural do mercado financeiro brasileiro**, não um problema de descoberta de endpoint. Os dados existem na B3/CETIP, mas ficam atrás de contratos B2B reservados a participantes qualificados (corretoras, gestoras). Nenhum proxy público confiável existe.

A fonte mais próxima que encontramos é o **Boletim Diário de Renda Fixa Privada da B3** (`RF{DDMMYY}.ex_`) — que contém debêntures, CRI, CRA e similares, não CDB puro. Mesmo assim, debêntures de instituições financeiras funcionam como proxy de stress de crédito do emissor.

---

## O que existe no GitHub sobre CDB

Fizemos uma varredura. O que há:

- **Scripts pontuais de scraping** de uma única corretora (geralmente XP ou BTG), sem testes, sem normalização, sem manutenção — a maioria abandonada há mais de 2 anos.
- **Bots de Telegram** que avisam quando alguma taxa supera um threshold fixo hardcoded.
- **Planilhas Google Sheets** conectadas à API não-oficial do Yubb via token pessoal — funcionam enquanto o Yubb não muda o endpoint.
- **Notebooks Jupyter** de análise pontual de retorno de CDB vs. Tesouro Direto — sem coleta, sem detecção de anomalias.

Nenhum projeto público combina coleta multi-fonte + normalização + detecção de anomalias + dados prudenciais do Banco Central.

---

## O que o veredas de papel faz que é inédito

### 1. Coleta multi-fonte normalizada

Nenhum outro projeto público ingere, em pipeline único com modelo de dados unificado:
- BCB Open Data (Selic, CDI, IPCA)
- IFData/Bacen (Basileia, Liquidez, ROA/ROE das IFs)
- Prateleiras públicas de corretoras (XP, BTG, Inter, Rico) via Playwright/BeautifulSoup
- Boletim Diário B3 — Renda Fixa Privada (debêntures de IFs como proxy de crédito)

### 2. Motor de detecção de anomalias com 5 camadas independentes

Aplicado especificamente a CDB, em produção, em código aberto:

| Camada | O que detecta |
|--------|--------------|
| Regras determinísticas | Spreads abusivos (>130% CDI), saltos bruscos de taxa em 24h |
| Z-Score (2σ / 3σ) | Desvio estatístico da média de mercado |
| STL Decomposition | Resíduo anômalo isolado de tendência e sazonalidade |
| PELT (ruptures) | Quebra estrutural na curva de juros da IF |
| Isolation Forest + DBSCAN | Outliers multivariáveis (taxa × prazo × liquidez × saúde) |

### 3. Cruzamento com dados prudenciais oficiais do Banco Central

Taxa alta + índice de Basileia abaixo do mínimo regulatório + liquidez crítica = sinal composto de risco. O padrão histórico — Banco Master (2025), BVA (2014), Cruzeiro do Sul (2012) — mostra exatamente esse comportamento antes da intervenção. Nenhum projeto público faz esse cruzamento.

### 4. Clusterização de emissores por tier com limiares calibrados

Um bancão oferecendo 110% CDI é muito mais suspeito do que uma pequena financeira oferecendo o mesmo. O `catalog.py` implementa dois eixos independentes:

- **TierEmissor**: bancão (alarme a 108% CDI) → médio (125%) → fintech (118%) → pequeno (130%)
- **TierPlataforma**: Tier S (XP, BTG, Rico) / banco digital / bancão próprio / mercado secundário

Isso não existe em nenhuma outra ferramenta pública.

### 5. GPL — código completamente aberto e auditável

Os poucos projetos relevantes que existem são proprietary (Yubb) ou não têm licença. veredas de papel é GPL-3.0: qualquer pessoa pode auditar o código, verificar os algoritmos, propor melhorias e redistribuir.

---

## Comparação direta: veredas de papel vs. Yubb

[Yubb](https://yubb.com.br) é o projeto mais próximo do nosso em termos de proposta — mas as diferenças são fundamentais:

| Dimensão | Yubb | veredas de papel |
|----------|------|-----------------|
| Código | Fechado (SaaS) | Aberto (GPL-3.0) |
| Dados prudenciais BCB | Não | Sim (Basileia, Liquidez, ROA/ROE) |
| Detecção de anomalias | Não — exibe taxas, não detecta risco | Sim — 5 camadas de detecção |
| Mercado secundário B3 | Não | Sim (Boletim Diário RF Privada) |
| Alertas configuráveis | Não | Sim (Telegram, Email) |
| API de acesso programático | Não pública | CLI completa + exportação JSON/CSV |
| Self-hosted | Não | Sim — roda 100% local, sem dependência de nuvem |
| Histórico e séries temporais | Não — snapshot atual | Sim — banco de dados com histórico completo |
| Tier de emissor no alarme | Não | Sim — bancão a 108% CDI já é suspeito |
| Licença | Proprietária | GPL-3.0-or-later |

Yubb é um excelente comparador de taxas. veredas de papel é uma ferramenta de **inteligência de risco** — a diferença é a mesma que há entre uma vitrine de preços e um sistema de vigilância.

---

## Por que isso importa

O caso Banco Master/Will Bank (2025) mostrou que taxas de 120–185% CDI e IPCA+30% estavam disponíveis em prateleiras públicas de grandes corretoras por meses. Qualquer sistema de detecção automática teria sinalizado anomalia crítica. Nenhum existia.

veredas de papel é a primeira ferramenta FOSS que combina **coleta automática de prateleiras**, **cruzamento com saúde financeira oficial** e **detecção multicamada** — exatamente o que faltava.

---

*Documento atualizado em: abril/2026*
