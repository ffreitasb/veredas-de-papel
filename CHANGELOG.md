<div align="center">
  <img src="assets/veredas_icon.png" alt="veredas de papel" width="72">
</div>

# Changelog

> *"Contar é muito dificultoso. Não pelos anos que já se passaram. Mas pela astúcia que têm certas coisas passadas — de fazerem balancê, de se remexerem nos lugares."*
> — João Guimarães Rosa, Grande Sertão: Veredas

## [Unreleased]

---

## [0.2.0-alpha] — 2026-04-27

Release que consolida as Fases 4.1, 4.2 e 4.3 (parcial), Tier Clustering, hardening de segurança e maturidade dos detectores. Marca a transição de ferramenta de análise local para sistema multi-fonte com scrapers de corretoras e mercado secundário B3.

### Fontes de mercado (Fase 4)
- **Fase 4.1** — `WebCollectorBase`: fundação para scrapers com Playwright (páginas JS-heavy) e BeautifulSoup (HTML estático), com rate limiting, retry exponencial e rotação de User-Agent
- **Fase 4.2** — Scrapers de corretoras: XP Investimentos, BTG Pactual, Banco Inter e Rico; normalização de taxas entre plataformas; `veredas collect scrapers --fonte xp|btg|inter|rico`
- **Fase 4.3 (parcial)** — B3 Boletim Diário: `downloader.py` extrai ZIP aninhado (ZIP → SFX Windows → ZIP interno → TXT); `parser.py` processa Renda Fixa Privada com mapeamento CNPJ; coluna `mercado` (`primario`/`secundario`) em `TaxaCDB`; filtro por fonte no dashboard
- **Tier Clustering** — `catalog.py`: `TierEmissor` (`BANCAO`, `MEDIO`, `PEQUENO`, `FINTECH`); thresholds de spread por tier no `SpreadDetector` e `DetectionEngine`

### Detectores
- **DOM-01** — `VariacaoDetector` detecta quedas bruscas: `QUEDA_BRUSCA` (>10 pp, LOW) e `QUEDA_EXTREMA` (>20 pp, MEDIUM)
- **ENG-01** — `_deduplicate()` com votação cross-category: elevação de severidade só ocorre entre detectores de categorias distintas (rules/statistical/ml); dois detectores ML concordando não é evidência independente; constante `_DETECTOR_CATEGORY` define o mapeamento
- **STL → experimental/** — `STLDecompositionDetector` movido para `veredas.detectors.experimental.stl`; semântica incompatível com CDB (STL pressupõe periodicidade sazonal inexistente no domínio); `StatisticalEngine` passa a orquestrar apenas `ChangePointDetector` + `RollingZScoreDetector`
- **DBSCAN guard** — `DBSCANOutlierDetector.detect()` retorna vazio se `unique(if_id) < 200`; mercado brasileiro tem ~50–150 emissores — precondição documentada no docstring
- `EngineConfig.enable_statistical` passa a `False` por padrão (opt-in consciente)
- Guard em `STLDecompositionDetector`: mínimo de 30 pontos por IF (hardcoded)

### Segurança
- **SEC-02** — `get_client_ip` só confia em `X-Forwarded-For`/`X-Real-IP` para IPs em `VEREDAS_TRUSTED_PROXIES`
- **SEC-04** — `CSRFMiddleware` corrigido: `_validate_csrf` retorna `JSONResponse(403)` em vez de `raise HTTPException`; Origin header check como Layer 1
- **SEC-05** — `csrf_token_input` retorna `Markup` (Jinja2 não re-escapa HTML)
- **SEC-06** — Whitelist de ordenação em `/taxas/` via `frozenset` + `_validar_ordem()`
- **SEC-07** — `_parse_tipo()` valida enum `TipoAnomalia` em `/anomalias/` (3 endpoints)
- **SEC-09** — `parse_cnpj` com `validate=True` em `/instituicoes/{cnpj}`

### Infraestrutura e qualidade
- CI/CD: GitHub Actions com 4 jobs (test Python 3.11/3.12, ruff, mypy, format)
- 70 testes de detectores passando; suite total acima de 479 testes
- `docs/decisoes_tecnicas.md`: registro de não-implementações deliberadas (service layer, typed filters, lazy imports, DOM-02, fontes extras, DBSCAN)
- `TipoAnomalia` expandido com `QUEDA_BRUSCA` e `QUEDA_EXTREMA`

> **Nota alpha:** scrapers de corretoras (XP, BTG, Inter, Rico) têm cobertura de parser (28 testes), mas ainda não foram validados contra os sites reais em produção contínua. Use com cautela e reporte regressões.

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
