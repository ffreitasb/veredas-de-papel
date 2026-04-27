<div align="center">
  <img src="assets/veredas_icon.png" alt="veredas de papel" width="72">
</div>

# ROADMAP — veredas de papel

> *"A vida é assim: esquenta e esfria, aperta e daí afrouxa, sossega e depois desinquieta. O que ela quer da gente é coragem."*
> — João Guimarães Rosa, Grande Sertão: Veredas

> Documento vivo. Atualizado a cada fase concluída ou replaneada.
> Para o histórico de mudanças, veja o [CHANGELOG.md](CHANGELOG.md).

---

## Status atual — v0.2.0-alpha

[**Release v0.2.0-alpha**](https://github.com/ffreitasb/veredas-de-papel/releases/tag/v0.2.0-alpha) publicada em abril/2026.

### Concluído

| Fase | Conteúdo | Release |
|------|----------|---------|
| **Fase 1 — MVP** | CLI, integração BCB (Selic/CDI/IPCA), modelo de dados, detecção por regras | — |
| **Fase 2 — Dashboard** | FastAPI + Jinja2 + HTMX, 5 rotas, partials, gráficos Plotly | — |
| **Fase 3 — IFData** | Coletor IFData/BCB, HealthDataIF, detectores de Basileia e Liquidez | — |
| **Fase B — Infraestrutura** | 60+ testes, Alembic, alertas Telegram/Email, CSV export, filtros HTMX | — |
| **Fase C — CI** | GitHub Actions (pytest 3.11/3.12, ruff, mypy) | v0.1.0-alpha |
| **Fase 4.1 — Fundação de Scrapers** | `WebCollectorBase` (rate limit, retry, UA rotation), `PlaywrightClient`, normalização `CDBOferta` | v0.2.0-alpha |
| **Fase 4.2 — Corretoras: Prateleiras** | Scrapers XP, BTG, Inter, Rico; `veredas collect scrapers --fonte`; 28 testes de parser | v0.2.0-alpha |
| **Fase 4.3-A/B/D — B3 parcial** | Downloader ZIP aninhado, parser Renda Fixa Privada, coluna `mercado`, filtro no dashboard | v0.2.0-alpha |
| **Tier Clustering** | `TierEmissor` (`BANCAO`/`MEDIO`/`PEQUENO`/`FINTECH`); thresholds de spread por tier | v0.2.0-alpha |
| **Hardening detectores** | ENG-01 cross-category, STL → experimental/, DBSCAN guard ≥200, `enable_statistical=False` | v0.2.0-alpha |
| **SEC-02/04/05/06/07/09** | CSRF, whitelist de parâmetros, CNPJ validation, Markup return type | v0.2.0-alpha |

---

## Em desenvolvimento — v0.3.0-alpha

**Próximas entregas:** validação em produção das novas fontes + inteligência cruzada (Fase 4.4).

> **Nota:** a Fase 4.3 (B3BoletimCollector + CLI `veredas collect b3`) foi concluída ainda durante a v0.2.0-alpha. A v0.3 foca em validação real contra os sites e nos detectores de inteligência cruzada.

---

### Etapa 0 — Validação em produção das fontes v0.2 *(1–2 dias)*

**Objetivo:** confirmar que scrapers e B3 collector funcionam contra os sites reais antes de construir detectores em cima deles.

| Fonte | Validação necessária |
|-------|---------------------|
| XP Investimentos | `veredas collect scrapers --fonte xp` retorna ≥ 1 taxa com valor > 0 |
| BTG Pactual | `veredas collect scrapers --fonte btg` retorna ≥ 1 taxa com valor > 0 |
| Banco Inter | `veredas collect scrapers --fonte inter` retorna ≥ 1 taxa com valor > 0 |
| Rico | `veredas collect scrapers --fonte rico` retorna ≥ 1 taxa com valor > 0 |
| B3 Boletim | `veredas collect b3` baixa boletim do último pregão sem erro |

- Ajustar parsers que falhem (HTML/JS dos sites pode ter mudado desde os testes)
- Registrar taxa de sucesso: % das corretoras operacionais em dia 1
- Critério de prosseguir: ≥ 3 corretoras e B3 operacionais

---

### Fase 4.4 — Inteligência Cruzada *(3–4 dias)*

**Objetivo:** usar as múltiplas fontes para detectar padrões que nenhuma fonte isolada revelaria.

#### Etapa A — `TipoAnomalia` e modelos *(meio dia)*

Adicionar em `src/veredas/storage/models.py`:

```python
# Fase 4.4 - Inteligência cruzada
SPREAD_CORRETORA = "spread_corretora"          # prateleira vs benchmark BCB
DIVERGENCIA_FONTES = "divergencia_fontes"       # mesma IF, corretoras divergem
PRIMARIO_VS_SECUNDARIO = "primario_vs_secundario"  # emissão vs deságio B3
```

Adicionar campo `fonte` em `Anomalia` (ou usar `detalhes["fonte"]` para evitar migração).

---

#### Etapa B — `CrossSourceDetector` *(1,5 dias)*

Novo arquivo: `src/veredas/detectors/cross_source.py`

```python
class CrossSourceDetector:
    """Detecta anomalias que exigem cruzamento entre múltiplas fontes."""

    def detect_spread_corretora(
        self,
        taxas_corretora: list[TaxaCDB],   # fonte="xp"|"btg"|"inter"|"rico"
        benchmark_bcb: Decimal,            # CDI atual
        threshold_pp: Decimal = Decimal("15"),
    ) -> list[Anomalia]:
        """Taxa corretora ≥ threshold_pp acima do benchmark BCB → SPREAD_CORRETORA (HIGH)."""
        ...

    def detect_divergencia_fontes(
        self,
        taxas_por_fonte: dict[str, list[TaxaCDB]],  # fonte → taxas
        threshold_pp: Decimal = Decimal("10"),
    ) -> list[Anomalia]:
        """Mesma IF com diferença ≥ threshold_pp entre duas corretoras → DIVERGENCIA_FONTES (MEDIUM)."""
        ...

    def detect_primario_vs_secundario(
        self,
        taxas_primario: list[TaxaCDB],   # fonte="bcb"|corretoras
        taxas_b3: list[TaxaCDB],          # fonte="b3", mercado="secundario"
        threshold_pp: Decimal = Decimal("20"),
    ) -> list[Anomalia]:
        """Taxa de emissão nova muito abaixo do preço implícito no secundário → PRIMARIO_VS_SECUNDARIO (HIGH)."""
        ...
```

Integrar em `DetectionEngine.analyze()` como quarta categoria (além de rules/statistical/ml).
Atualizar `_DETECTOR_CATEGORY` em `engine.py`:

```python
"cross_source_detector": "cross_source",
```

---

#### Etapa C — Dashboard: filtro de fonte em `/taxas/` *(1 dia)*

- Adicionar campo `fonte` na query de `/taxas/` (já existe na coluna `TaxaCDB.fonte`)
- Novo filtro HTMX no template `taxas/index.html`: dropdown `bcb | xp | btg | inter | rico | b3`
- Whitelist de validação em `_validar_fonte()` (padrão SEC-06)
- CSV export inclui coluna `fonte`

---

#### Etapa D — Perfil da IF: comparativo por fonte *(meio dia)*

Na rota `/instituicoes/{cnpj}`, adicionar seção "Taxas por Fonte":

- Tabela agrupada por fonte mostrando taxa mais recente de cada plataforma
- Destaque visual quando desvio entre fontes > 5 pp

---

#### Etapa E — Scheduler inclui scrapers e B3 *(meio dia)*

Em `src/veredas/scheduler.py`, adicionar tarefas:

```python
# Coleta diária (junto com BCB)
{"type": "scrapers_all", "frequency": "daily", "hour": 8}
{"type": "b3_boletim",   "frequency": "daily", "hour": 9}

# Ou via veredas collect all
```

`veredas collect all` passa a incluir scrapers e B3.

---

#### Critério de conclusão v0.3

- `veredas analyze` detecta `SPREAD_CORRETORA` e `DIVERGENCIA_FONTES` quando os dados estão presentes
- Anomalias de inteligência cruzada aparecem no dashboard com atribuição de fonte
- Filtro de fonte funciona em `/taxas/`
- Página de detalhe da IF exibe comparativo por fonte
- `veredas collect all` inclui scrapers e B3

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
| `v0.2.0-alpha` | Fase 4.1 + 4.2 + 4.3 parcial + Tier Clustering + hardening — **publicada** |
| `v0.3.0-alpha` | Validação PRD scrapers/B3 + Fase 4.4 (inteligência cruzada) |
| `v0.4.0-alpha` | Fase 5 (dados alternativos: Reclame Aqui, sanções BCB) |
| `v1.0.0` | Fase D completa (PyPI, binários, demo) |

---

*Atualizado em: 27/abril/2026 — v0.2.0-alpha publicada; v0.3.0-alpha: validação PRD + Fase 4.4 em desenvolvimento*
