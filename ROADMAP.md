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

**Próximas entregas:** B3 Collector completo (4.3-C) e inteligência cruzada entre fontes (4.4).

---

### 4.3 — B3: Mercado Secundário

**Objetivo:** capturar preços de CDBs negociados no mercado secundário via Boletim Diário B3 — a única fonte pública gratuita disponível após validação de todas as alternativas.

**Esforço estimado:** 1,5 semanas

#### Por que não há fonte melhor — validação completa (23/04/2026)

| Fonte | CDB secundário? | Veredicto |
|-------|----------------|-----------|
| B3 API (`developers.b3.com.br`) | Sim (API "CDB" existe) | B2B fechado, contrato pago |
| ANBIMA API | Não — só debentures/CRI/CRA | OAuth2; sem CDB |
| CETIP FTP público | — | Não existe (B3 absorveu em 2017) |
| Yubb, Status Invest, Mais Retorno | Mercado primário apenas | Anti-bot ou sem CDB |
| **B3 Boletim Diário RF Privada** | **Debêntures (não CDB puro)** | **✓ Fonte escolhida** |

> **Nota:** CDB secundário real fica no sistema B3/CETIP com acesso restrito a participantes qualificados. É uma lacuna estrutural do mercado — não um problema de descoberta de endpoint. A alternativa pública mais próxima são as **debêntures** de IFs no mesmo arquivo, que funcionam como proxy de stress de crédito: se os spreads das debêntures do Banco X sobem, os CDBs do mesmo emissor estão sob risco similar.

---

#### URL e formato — confirmados sem JS

```
GET https://www.b3.com.br/pesquisapregao/download?filelist=RF{DDMMYY}.ex_,
```
- `DDMMYY` = dia+mês+ano com 2 dígitos cada (ex.: 23/04/2026 → `230426`)
- Retorna ZIP aninhado: ZIP externo → executável SFX Windows → `RF{DDMMYY}.txt`
- Arquivo TXT: primeira linha = data do pregão (`YYYYMMDD`); linhas seguintes = CSV com `;`
- Campos: `TICKER;VENCIMENTO;DIAS_CORRIDOS;DIAS_UTEIS;PU_MERCADO;PU_PAR;TAXA_MERCADO;FATOR_ACUMULADO`
- Janela: ~2 pregões disponíveis simultaneamente — coleta deve ser **diária**

---

#### Plano de implementação

##### ~~Etapa A — Reverse-engineering do download~~ ✓ concluído

URL confirmada e formato documentado (ver acima).

##### Etapa B — Parser do arquivo (2–3 dias)

Arquivo CSV semicolon, layout simples:

```python
# collectors/b3/parser.py
@dataclass
class B3RendaFixaRecord:
    data_pregao: date
    codigo: str          # ex: AGRU-DEB21
    vencimento: date
    dias_corridos: int
    dias_uteis: int
    pu_mercado: Decimal
    pu_par: Decimal
    taxa_mercado: Decimal   # % a.a.
    fator_acumulado: Decimal
    emissor_codigo: str     # prefixo do ticker (ex: AGRU, EGIE)
    tipo: str               # "DEB", "ETF", ou "OUTRO"

class B3RendaFixaParser:
    def parse(self, conteudo: str, data_pregao: date) -> list[B3RendaFixaRecord]: ...
```

Extração do ZIP aninhado (SFX dentro de ZIP):

```python
pk_pos = sfx_bytes.rfind(b'PK\x03\x04')
with zipfile.ZipFile(io.BytesIO(sfx_bytes[pk_pos:])) as inner:
    txt = inner.read(inner.namelist()[0]).decode("latin-1")
```

##### Etapa C — Coletor (1–2 dias)

```
collectors/b3/
  __init__.py
  downloader.py   # _build_url(date) + download + extração do ZIP aninhado
  parser.py       # B3RendaFixaRecord + B3RendaFixaParser
  collector.py    # B3BoletimCollector(WebCollectorBase)
```

- `B3BoletimCollector.collect(data: date | None = None)` — boletim do dia ou data específica
- `veredas collect b3 [--data YYYY-MM-DD]` no CLI
- Tolerância a pregão fechado (fin de semana, feriado) — retorna lista vazia sem erro

##### Etapa D — Modelo de dados e dashboard (1–2 dias)

- Migration Alembic: coluna `mercado` (`"primario"` / `"secundario"`) em `TaxaCDB`
- Dashboard `/taxas/`: filtro por mercado via HTMX
- Registros B3 persistidos apenas para emissores já cadastrados em `InstituicaoFinanceira` (matching por prefixo do ticker → CNPJ do catálogo)

#### Critério de conclusão

`veredas collect b3` baixa o boletim do dia sem erro; debêntures de IFs financeiras aparecem no dashboard com `mercado="secundario"`; coluna `mercado` presente no CSV exportado.

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
| `v0.2.0-alpha` | Fase 4.1 + 4.2 + 4.3 parcial + Tier Clustering + hardening — **publicada** |
| `v0.3.0-alpha` | Fase 4.3-C (B3BoletimCollector + CLI) + 4.4 (inteligência cruzada) |
| `v0.4.0-alpha` | Fase 5 (dados alternativos: Reclame Aqui, sanções BCB) |
| `v1.0.0` | Fase D completa (PyPI, binários, demo) |

---

*Atualizado em: 27/abril/2026 — v0.2.0-alpha publicada; v0.3.0-alpha em desenvolvimento*
