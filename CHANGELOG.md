<div align="center">
  <img src="assets/veredas_icon.png" alt="veredas de papel" width="72">
</div>

# Changelog

> *"Contar é muito dificultoso. Não pelos anos que já se passaram. Mas pela astúcia que têm certas coisas passadas — de fazerem balancê, de se remexerem nos lugares."*
> — João Guimarães Rosa, Grande Sertão: Veredas

## [Unreleased]

---

## [0.1.0-alpha.3] — 2026-04-24

### Segurança
- **SEC-02** — `get_client_ip` só respeita `X-Forwarded-For`/`X-Real-IP` quando o IP de conexão está em `VEREDAS_TRUSTED_PROXIES`; sem proxies configurados, headers de proxy são ignorados (prevenção de IP spoofing)
- **SEC-04** — `CSRFMiddleware` corrigido: bypass do primeiro POST removido; `_validate_csrf` retorna `JSONResponse(403)` em vez de `raise HTTPException` (HTTPException em middleware Starlette alcançava `ServerErrorMiddleware` e retornava 500); `Origin` header check adicionado como Layer 1 de defesa
- **SEC-03/08/09** — Integração Playwright condicionada a env vars; `validate=True` por padrão em `parse_cnpj`

### Detectores
- **DOM-01** — `VariacaoDetector` agora detecta quedas bruscas de taxa: `QUEDA_BRUSCA` (>10pp, LOW) e `QUEDA_EXTREMA` (>20pp, MEDIUM) — repricing abrupto e dificuldade de captação são sinais de risco tanto quanto altas
- **ENG-01** — `_deduplicate()` implementa votação ponderada: 2 detectores independentes elevam severidade +1 nível (MEDIUM→HIGH), 3+ elevam +2 (MEDIUM→CRITICAL); lista de detectores votantes registrada em `detalhes["detectores"]`
- `TipoAnomalia` expandido com `QUEDA_BRUSCA` e `QUEDA_EXTREMA`

### Arquitetura
- **A1** — `AlertSettings` extraído como sub-config aninhado em `Settings`; `alerts/email.py`, `telegram.py` e `manager.py` atualizados para `get_settings().alerts.*` — elimina 9 campos duplicados
- **A2** — `web/templates_config.py` criado; instância `Jinja2Templates` e globals de template desacoplados de `app.py`; todas as rotas migradas para `from veredas.web.templates_config import templates`
- **M3** — Todos os `field(default_factory=datetime.now)` em `base.py` e `engine.py` trocados por `lambda: datetime.now(TZ_BRASIL)` — timestamps nunca mais naive

### Qualidade de código (quick wins)
- `Optional[X]` → `X | None` em todos os `Mapped` de `models.py`
- `get_desvio_padrao` usa `np.std` via numpy em vez de loop Python
- `get_by_nome` usa `.scalars().first()` em vez de `.scalar_one_or_none()` (previne `MultipleResultsFound`)
- `health_check` em `ifdata.py` usa `AsyncClient` isolado em vez do cliente compartilhado
- F-strings em logger substituídas por lazy format strings em `scheduler.py`, `ifdata.py` e `bcb.py`
- Exceções silenciosas em `bcb.py` agora logam `DEBUG` com tipo e causa
- **Q-02** — `raise X` em blocos `except` corrigidos com `raise X from exc` (B904) via ruff

### Testes (+319 novos, total 479)
| Arquivo | Testes | Cobertura |
|---|---|---|
| `test_csrf.py` | 11 | SEC-04: POST sem cookie, Origin inválida, fluxo legítimo GET→POST |
| `test_ratelimit.py` | 11 | SEC-02: sem proxy, com proxy confiável, edge cases (client=None, XFF com espaços) |
| `test_engine.py` | 10 | ENG-01: votação ponderada, cap CRITICAL, detector duplicado não infla votos |
| `test_rules.py` | +4 | DOM-01: QUEDA_BRUSCA/QUEDA_EXTREMA, queda pequena ignorada |
| `test_validators.py` | 28 | CNPJ válido/inválido, todos iguais, `parse_cnpj` required/validate, `round_decimal` |
| `test_risk_score.py` | 58 | Todos os thresholds de spread/basileia/volatilidade/tendência com boundaries exatos |
| `test_health.py` | 23 | Basileia 10,5% exato = ALERTA (não CRÍTICO), `comparar_com_benchmark` |
| `test_b3_downloader.py` | 10 | ZIP aninhado real, ZIP corrompido, SFX sem magic PK, `build_url` |
| `test_b3_parser.py` | 23 | Parse completo, campos decimais, tipo via regex, mapeamento CNPJ, `is_financeira` |
| `test_scheduler.py` | 18 | `_calculate_next_run` para todos os tipos de frequência com `now` fixo em BRT |
| `test_manager.py` | 33 | Filtro de severidade, cooldown, batch, exceção em sender, histórico |
| `test_scraper_parser.py` | 28 | BTG, XP, Inter, Rico: parse HTML, normalização, campos obrigatórios |

---

## [0.1.0-alpha.2] — 2026-04-23 (Fase 4 — Fontes Adicionais)

### Adicionado
- **Fase 4.1** — `WebCollectorBase` e `PlaywrightClient`: fundação de scrapers com Playwright para páginas JS-heavy e BeautifulSoup para HTML estático
- **Fase 4.2** — Scrapers para XP Investimentos, BTG Pactual, Banco Inter e Rico; normalização de taxas entre plataformas; detecção de discrepância cross-platform
- **Fase 4.3-A** — Coletor do Boletim Diário B3: `downloader.py` extrai ZIP aninhado (ZIP externo → SFX Windows → ZIP interno → TXT), `parser.py` processa registros de Renda Fixa Privada (debêntures, CRI, CRA) com mapeamento CNPJ para IFs
- **Fase 4.3** — Tier clustering de emissores (`BANCAO`, `FINTECH`, `PEQUENO`, `MEDIO`); thresholds de spread ajustados por tier em `catalog.py`
- **Fase 4.3-D** — Coluna `mercado` nas tabelas de taxas; migração Alembic gerada; filtro por fonte no dashboard
- CI/CD: GitHub Actions com 4 jobs (test, lint/ruff, type check/mypy, format check)
- Assets: ícone do projeto, apple-touch-icon, Open Graph e theme-color

### Corrigido
- `TemplateResponse` migrado para API Starlette 1.0
- Todas as violações ruff zeraram antes da Fase 4
- Import circular resolvido

---

## [0.1.0-alpha.1] — 2026-01-23 (Fases 2 e 3)

### Adicionado
- **Fase 2** — Frontend web com FastAPI + Jinja2 + HTMX: dashboard de anomalias, tabela de taxas, timeline, página de instituições
- **Fase 2** — Sistema de alertas: `AlertManager` com cooldown, filtro de severidade e canais Email (SMTP) e Telegram
- **Fase 2** — CSRF protection (double-submit cookie), rate limiting por IP, headers de segurança
- **Fase 3** — `DetectionEngine` unificando detectores de regras, estatísticos e ML
- **Fase 3** — Detectores estatísticos: `RollingZScoreDetector`, `STLDecompositionDetector`, `ChangePointDetector` (ruptures PELT)
- **Fase 3** — Detectores ML: `IsolationForestDetector`, `DBSCANOutlierDetector`
- **Fase 3** — Extração de features: `FeatureExtractor`, `calculate_market_stats`
- **Fase 3** — CLI integrado com `DetectionEngine`; REST API para detecção de anomalias
- **Fase 3** — `EngineConfig` com flags `enable_rules`, `enable_statistical`, `enable_ml`, `deduplicate`
- `analysis/risk_score.py` — score de risco 0-100 por instituição (spread 40% + basileia 30% + volatilidade 20% + tendência 10%)
- `analysis/health.py` — análise de indicadores regulatórios (Basileia mínimo 10,5%, LCR)
- `analysis/charts.py` — dados formatados para Chart.js
- Migração Alembic inicial; `DatabaseManager` com `session_scope` context manager
- Filtros HTMX, cabeçalhos ordenáveis e exportação CSV no dashboard

### Corrigido
- Bugs críticos de dashboard (rotas HTMX, paginação)
- ORM detached objects em cache
- Thread-safety do SQLite em contexto async

---

## [0.1.0] - Versão Inicial (Fase 1 + WIP)

### Adicionado
- Estrutura base do projeto
- Models do banco de dados (SQLite via SQLAlchemy/Alembic)
- Sistema base de detecção de anomalias com regras (CDB Spreads)
- Coletores do Banco Central do Brasil (BCB) e IFData
- Aplicação cli básica (`veredas`)
- Servidor Web/Frontend para visualização de anomalias (CDB/Taxas) e stats
