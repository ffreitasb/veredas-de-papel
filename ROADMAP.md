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

**Objetivo:** capturar preços de CDBs negociados no mercado secundário via Boletim Diário B3 — a única fonte pública gratuita disponível após validação de todas as alternativas.

**Esforço estimado:** 1,5 semanas

#### Por que não há fonte melhor — resumo da validação (23/04/2026)

| Fonte | Veredicto |
|-------|-----------|
| B3 API (`developers.b3.com.br`) — API "CDB" existe | B2B fechado, contrato pago obrigatório |
| ANBIMA API (`api.anbima.com.br`) | Não tem CDB — só debentures, CRI, CRA |
| CETIP FTP público | Não existe — B3 absorveu CETIP em 2017 |
| **B3 Boletim Diário "Renda Fixa Privada"** | **✓ Fonte escolhida — público, sem login** |

---

#### Plano de implementação

##### Etapa A — Reverse-engineering do download (2–3 dias)

O boletim usa JavaScript dinâmico para construir a URL de download. A estratégia:

1. Usar Playwright para navegar até a página do boletim e interceptar requisições de rede (`page.on("request")`) enquanto o JS monta o link de download do arquivo "Renda Fixa Privada"
2. Identificar o padrão de URL (provável: `https://www.b3.com.br/pesquisapregao/download?filetype=zip&date=DDMMYYYY&code=...`)
3. Verificar se o `contentId` é constante por tipo de arquivo ou varia por pregão
4. Documentar o padrão em `collectors/b3/README_URL_PATTERN.md` para manutenção futura

**Entregável:** função `_resolve_download_url(date: date) -> str` com URL direta, sem interação com JS para datas futuras.

##### Etapa B — Parser do arquivo (3–4 dias)

O arquivo "Renda Fixa Privada" segue layout posicional (padrão histórico B3). Será necessário:

1. Baixar um arquivo de amostra e inspecionar o layout (campo por campo)
2. Identificar o código de instrumento para CDB (provável: `"CDB"` ou `"DI"` no campo `TpInstrd`)
3. Campos de interesse: CNPJ do emissor, taxa DI (%), IPCA+, data de vencimento, volume, data do pregão
4. Implementar `B3BoletimParser` com mapeamento campo → `CDBOferta`

```python
# collectors/b3/parser.py
@dataclass
class B3BoletimRecord:
    data_pregao: date
    cnpj_emissor: str
    tipo_instrumento: str   # CDB, CRI, CRA, ...
    taxa_indicativa: Decimal
    indexador: str          # DI, IPCA, PRE
    vencimento: date
    volume_financeiro: Decimal

class B3BoletimParser:
    def parse(self, filepath: Path) -> list[B3BoletimRecord]: ...
    def to_cdb_oferta(self, record: B3BoletimRecord) -> CDBOferta | None: ...
```

##### Etapa C — Coletor (2 dias)

```
collectors/
  b3/
    __init__.py
    downloader.py   # Playwright + URL resolution
    parser.py       # layout posicional → B3BoletimRecord → CDBOferta
    collector.py    # B3BoletimCollector(WebCollectorBase)
```

- `B3BoletimCollector.collect(date=None)` — baixa e processa o boletim do dia (ou data específica)
- `veredas collect b3 [--data YYYY-MM-DD]` no CLI
- Tolerância a pregão fechado (fins de semana, feriados) — retorna lista vazia sem erro
- Campo `mercado="secundario"` em todos os registros gerados

##### Etapa D — Modelo de dados e dashboard (1–2 dias)

- Migration Alembic: adicionar coluna `mercado` (`"primario"` / `"secundario"`) em `TaxaCDB`
- Dashboard `/taxas/`: novo filtro por mercado via HTMX
- Página de detalhe da IF: seção "Mercado Secundário" com histórico de preços negociados

#### Critério de conclusão

`veredas collect b3` baixa e persiste o boletim do dia sem erro; registros aparecem no dashboard com mercado="secundario"; a coluna `mercado` está presente no CSV exportado.

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
