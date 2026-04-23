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

---

## Em desenvolvimento — Fase 4: Fontes de Mercado

**Objetivo:** ampliar a base de dados do sistema com taxas reais de prateleiras de corretoras e do mercado secundário B3, aumentando a capacidade de detecção cruzada entre fontes.

**Estratégia de scraping:** HTML direto (Approach A) por ser mais rápido de implementar. Cada coletor terá um `# TODO: migrar para API não-oficial (Approach B)` quando a instabilidade do HTML se mostrar recorrente — endpoints JSON dos apps mobile das corretoras são mais estáveis que o HTML do site.

---

### 4.1 — Fundação de Scrapers

**Objetivo:** infraestrutura reutilizável que todos os coletores da Fase 4 vão herdar. Sem isso, cada corretora vira código duplicado.

**Esforço estimado:** 3–4 dias

#### Entregas

- `collectors/base.py` estendido com `WebCollectorBase`:
  - Rate limiting configurável por domínio
  - Retry exponencial com jitter (3 tentativas, backoff 2×)
  - Rotação de User-Agent a partir de lista curada
  - Headers realistas (Accept, Accept-Language, Referer)
  - Timeout por etapa (connect, read, total)
- Setup **Playwright** (headless Chromium) para páginas JS-rendered:
  - `collectors/scraper_client.py` com contexto de browser gerenciado
  - Suporte a wait_for_selector antes de extrair dados
- Camada de normalização: qualquer fonte externa entra como `TaxaCDB` com campo `fonte` preenchido (`"xp"`, `"btg"`, `"inter"`, `"b3"`)
- CI: GitHub Actions atualizado para instalar `playwright install --with-deps chromium`
- Testes com respostas HTTP mockadas via `pytest-httpx` ou `respx`

**Critério de conclusão:** `WebCollectorBase` instanciável; teste unitário com mock HTTP passa; `playwright chromium` disponível no CI.

---

### 4.2 — Corretoras: Prateleiras Públicas

**Objetivo:** coletar taxas de CDB disponíveis para compra nas principais corretoras, sem autenticação — apenas páginas públicas de produtos.

**Esforço estimado:** 1–2 semanas (4 coletores × 2–3 dias cada)

#### Coletores

| Corretora | Arquivo | Notas |
|-----------|---------|-------|
| XP Investimentos | `collectors/scrapers/xp.py` | Renderização JS; prioridade 1 |
| BTG Pactual Digital | `collectors/scrapers/btg.py` | Renderização JS; prioridade 2 |
| Banco Inter | `collectors/scrapers/inter.py` | App-first; prioridade 3 |
| Rico | `collectors/scrapers/rico.py` | Infraestrutura XP, endpoint diferente |

#### Padrão de implementação

```python
class XPCollector(WebCollectorBase):
    SOURCE = "xp"
    BASE_URL = "https://www.xpi.com.br/investimentos/renda-fixa/cdb/"

    # TODO: migrar para API não-oficial (Approach B)
    # O app XP expõe endpoint JSON em /api/products/fixed-income
    # mais estável que o HTML do site — migrar quando HTML quebrar 2x.

    async def _parse(self, page) -> list[TaxaCDB]:
        ...
```

#### Entrega

- `veredas collect scrapers` — coleta todas as corretoras configuradas
- `veredas collect scrapers --fonte xp` — coleta fonte específica
- Tolerância a falha parcial: se BTG retorna erro, XP continua
- Log claro de sucesso/falha por fonte

**Critério de conclusão:** `veredas collect scrapers` roda sem erro por 7 dias consecutivos; falha de uma corretora não interrompe as demais; dados aparecem no dashboard com o filtro de fonte.

---

### 4.3 — B3: Mercado Secundário

**Objetivo:** capturar preços de CDBs negociados no mercado secundário — diferente da prateleira de captação primária das corretoras.

**Esforço estimado:** 1 semana (dependente de acesso)

#### Avaliação de acesso (pré-requisito)

- [ ] **B3 Market Data API** — verificar se endpoint público existe ou exige contrato
- [ ] **ANBIMA** — dados de debentures e CDBs via `anbima-api` (open, bem documentada)
- [ ] **CETIP/B3 feed** — feed de fechamento disponível via FTP público

Fallback se B3 exigir contrato: **ANBIMA** cobre CDBs negociados e tem API gratuita com registro.

#### Modelo de dados

Campo `mercado` em `TaxaCDB`:
- `"primario"` — prateleira de captação (corretora/emissor)
- `"secundario"` — preço negociado no mercado secundário

#### Entrega

- `collectors/b3/secondary.py` (ou `collectors/anbima.py` conforme avaliação)
- `veredas collect b3` disponível no CLI
- Dashboard: coluna "Mercado" visível na tabela de taxas

**Critério de conclusão:** dados de mercado secundário populados; distinção primário/secundário visível no dashboard.

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
| `v0.2.0-alpha` | Fase 4.1 + 4.2 (fundação + primeiras corretoras) |
| `v0.3.0-alpha` | Fase 4.3 + 4.4 (B3 + inteligência cruzada) |
| `v0.4.0-alpha` | Fase 5 (dados alternativos) |
| `v1.0.0` | Fase D completa (PyPI, binários, demo) |

---

*Atualizado em: abril/2026*
