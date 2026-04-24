# ROADMAP — veredas de papel

> Documento vivo. Atualizado a cada fase concluída ou replaneada.
> Para o histórico de mudanças, veja o [CHANGELOG.md](CHANGELOG.md).

---

## Status atual — v0.1.0-alpha

[**Release v0.1.0-alpha**](https://github.com/ffreitasb/veredas-de-papel/releases/tag/v0.1.0-alpha) publicada em abril/2026.

### Concluído

| Fase | Conteúdo | Release |
|------|----------|---------|
| **Fase 1 — MVP** | CLI, integração BCB (Selic/CDI/IPCA), modelo de dados, detecção por regras | — |
| **Fase 2 — Dashboard** | FastAPI + Jinja2 + HTMX, 5 rotas, partials, gráficos Plotly | — |
| **Fase 3 — IFData** | Coletor IFData/BCB, HealthDataIF, detectores de Basileia e Liquidez | — |
| **Fase B — Infraestrutura** | 60+ testes, Alembic, alertas Telegram/Email, CSV export, filtros HTMX | — |
| **Fase C — CI** | GitHub Actions (pytest 3.11/3.12, ruff, mypy) | v0.1.0-alpha |
| **Fase 4.1 — Fundação de Scrapers** | `WebCollectorBase` (rate limit, retry, UA rotation), `PlaywrightClient`, camada de normalização `CDBOferta` | — |
| **Fase 4.2 — Corretoras: Prateleiras** | Scrapers XP, BTG, Inter, Rico; `veredas collect scrapers --fonte`; 40 testes do parser | — |
| **Tier Clustering** | `catalog.py`: `TierEmissor`/`TierPlataforma`, limiares por tier (bancão alarma a 108% CDI, pequeno a 130%); `SpreadDetector` e `DetectionEngine` com thresholds por if_id; globals Jinja2 | — |

---

## Em desenvolvimento — Fase 4: Fontes de Mercado (continuação)

**Fases 4.1 e 4.2 concluídas.** Próximas entregas: mercado secundário B3 (4.3) e inteligência cruzada entre fontes (4.4).

---

### 4.3 — B3: Mercado Secundário

**Objetivo:** capturar preços de CDBs negociados no mercado secundário — diferente da prateleira de captação primária das corretoras.

**Esforço estimado:** 1 semana (dependente de acesso)

#### Avaliação de acesso — validada em 23/04/2026

- [x] **B3 Market Data API** (`developers.b3.com.br`) — API "CDB" existe, mas é **B2B fechada**. Requer contrato institucional e OAuth2 pago. Inviável sem contrato.
- [x] **ANBIMA API** (`api.anbima.com.br`) — Cobre debentures, CRI, CRA, LF — **não tem API de CDB**. CDB não é marcado a mercado pela ANBIMA. Requer registro OAuth2; sandbox aparentemente gratuito, produção exige vínculo com membro ANBIMA.
- [x] **CETIP/B3 FTP público** — **Não existe.** B3 absorveu a CETIP em 2017; todos os feeds migraram para o portal B2B fechado.

**Fonte viável identificada: B3 Boletim Diário — arquivo "Renda Fixa Privada"**
URL pública: `https://www.b3.com.br/pt_br/market-data-e-indices/servicos-de-dados/market-data/historico/boletins-diarios/pesquisa-por-pregao/pesquisa-por-pregao/`
- Dado público, sem login, atualização diária (~19:53 BRT)
- Cobre o segmento "Renda Fixa Privada" (inclui CDB, CRI, CRA, debentures, LCI, LCA)
- Download via JavaScript dinâmico (sem URL estática) — requer Playwright para extrair `contentId` e baixar o arquivo
- Formato provável: TXT posicional ou CSV (padrão histórico B3)
- Abordagem: reverse-engineering da requisição de download no browser para montar URL programaticamente

#### Modelo de dados

Campo `mercado` em `TaxaCDB`:
- `"primario"` — prateleira de captação (corretora/emissor)
- `"secundario"` — preço negociado no mercado secundário

#### Entrega

- `collectors/b3/secondary.py` (ou `collectors/anbima.py` conforme avaliação)
- `veredas collect b3` disponível no CLI
- Dashboard: coluna "Mercado" visível na tabela de taxas

**Critério de conclusão:** dados de mercado secundário populados via Boletim Diário B3; distinção primário/secundário visível no dashboard.

---

### 4.4 — Inteligência Cruzada

**Objetivo:** usar as múltiplas fontes para detectar padrões que nenhuma fonte isolada revelaria.

**Esforço estimado:** 1 semana

#### Novos tipos de anomalia

| Tipo | Lógica | Severidade |
|------|--------|------------|
| `SPREAD_CORRETORA` | Taxa na prateleira da corretora ≥ X% acima do benchmark de mercado primário (BCB) | HIGH |
| `DIVERGENCIA_FONTES` | Mesma IF ofertando taxas com diferença ≥ Y pp entre duas corretoras | MEDIUM |
| `PRIMARIO_VS_SECUNDARIO` | Taxa de emissão nova muito abaixo do preço implícito no secundário (sinal de deságio) | HIGH |

#### Integração

- Novas fontes entram no ciclo do `scheduler.py` (coleta automática junto com BCB/IFData)
- `veredas collect all` inclui scrapers e B3
- Dashboard: filtro de fonte (`bcb`, `xp`, `btg`, `inter`, `b3`) em `/taxas/`
- Página de detalhe da IF exibe comparativo de taxas por fonte

**Critério de conclusão:** `veredas analyze` detecta `SPREAD_CORRETORA` e `DIVERGENCIA_FONTES`; anomalias aparecem no dashboard com atribuição de fonte.

---

## Fase 5 — Dados Alternativos

**Objetivo:** complementar os dados financeiros com sinais de comportamento e reputação das IFs.

**Esforço estimado:** 2–3 semanas | **Dependência:** Fase 4 concluída

### 5.1 — Reclame Aqui

- Coletor de reclamações por IF (volume, índice de resolução, nota)
- Modelo `ReclamacaoIF` com série temporal
- Detector `REPUTACAO_QUEDA`: aumento súbito de reclamações correlacionado com taxa alta
- Dashboard: indicador de reputação na página de detalhe da IF

### 5.2 — Processos Sancionadores Bacen

- Scraper do portal de sanções do Banco Central (`www.bcb.gov.br/estabilidadefinanceira/processos`)
- Modelo `ProcessoSancionador` com data, tipo e IF envolvida
- Integração com timeline de eventos regulatórios

### 5.3 — Correlação entre fontes alternativas

- Detector `CONVERGENCIA_SINAIS`: taxa alta + reputação caindo + processo aberto = CRITICAL automático
- Timeline unificada: taxa, anomalia, reclamação e processo no mesmo eixo temporal

---

## Fase D — Distribuição

**Objetivo:** tornar o software instalável sem Python e disponível publicamente.

**Dependência:** base funcional (Fases 1–4 concluídas)

### D1 — Empacotamento PyInstaller

- `veredas.spec` com bundle de templates, static e binários do Playwright
- Binários: `.exe` Windows, binário Linux (Ubuntu 22.04)
- GitHub Actions release job: build automático ao criar tag `v*`

**Critério:** `./veredas init && ./veredas collect bcb` funciona em Windows sem Python.

### D2 — Release no PyPI

- `pip install veredas-de-papel` instala o CLI funcional
- Extras: `pip install "veredas-de-papel[web,ml,alerts,scrapers]"`
- Workflow de publicação automática via Trusted Publisher (PyPI OIDC)

### D3 — Demo Público

- Deploy no Koyeb free tier (ou Railway) com dados históricos pré-populados
- Banco somente-leitura no ambiente demo
- Atualização diária via cron job
- Badge "Live Demo" no README

---

## Fora do escopo (por ora)

| Item | Motivo |
|------|--------|
| API REST pública documentada | Só após schema estabilizar na v1.0 |
| App mobile | Fora do perfil FOSS/CLI do projeto |
| Multi-usuário / autenticação | Escopo significativo; baixo retorno para o público-alvo atual |
| Redis / cache externo | Otimização prematura — SQLite in-process é suficiente |
| Dados B3 via contrato pago | Reavaliar se ANBIMA não cobrir o caso de uso na Fase 4.3 |

---

## Visão de versões

| Versão | Conteúdo esperado |
|--------|------------------|
| `v0.1.0-alpha` | Fases 1–3 + B + C — **publicada** |
| `v0.2.0-alpha` | Fase 4.1 + 4.2 + Tier Clustering — **concluído, release pendente** |
| `v0.3.0-alpha` | Fase 4.3 + 4.4 (B3 + inteligência cruzada) |
| `v0.4.0-alpha` | Fase 5 (dados alternativos) |
| `v1.0.0` | Fase D completa (PyPI, binários, demo) |

---

*Atualizado em: 23/abril/2026 — 4.1, 4.2 e Tier Clustering concluídos; endpoints 4.3 validados*
