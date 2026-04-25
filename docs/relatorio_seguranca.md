# Relatório de Auditoria de Segurança — veredas de papel

**Projeto:** veredas-de-papel v0.1.0  
**Data da auditoria:** 2026-04-24  
**Escopo:** Código-fonte em `src/veredas/` (web, collectors, alerts, storage, CLI)  
**Auditor:** Revisão estática automatizada + análise manual  

---

## Sumário Executivo

O projeto **veredas de papel** demonstra maturidade de segurança acima da média para um projeto FOSS em fase Alpha. O código revela consciência explícita dos principais vetores de ataque: há middleware de CSRF implementado do zero, rate limiting por IP, headers de segurança HTTP, uso exclusivo de ORM parametrizado e gestão de segredos via variáveis de ambiente.

Foram identificadas **11 achados** distribuídos em quatro categorias de severidade. Nenhum achado é de severidade CRÍTICA no contexto padrão de uso (self-hosted local). Entretanto, três achados são classificados como **ALTO** e tornam-se críticos se o dashboard for exposto publicamente sem proxy reverso adequado.

| Severidade | Quantidade |
|------------|-----------|
| CRÍTICO    | 0         |
| ALTO       | 3         |
| MÉDIO      | 5         |
| BAIXO      | 2         |
| INFO       | 1         |

**Pontos fortes identificados:**
- 100% das queries ao banco de dados usam SQLAlchemy ORM com parâmetros vinculados (zero raw SQL)
- Implementação própria e correta de CSRF com `secrets.compare_digest` (timing-safe)
- `.env` presente no `.gitignore`; nenhum segredo hardcoded encontrado no código
- Rate limiting implementado (60 req/min por IP)
- Security headers completos: `X-Frame-Options`, `X-Content-Type-Options`, `Referrer-Policy`, `Permissions-Policy`

**Áreas que requerem atenção prioritária:**
1. Ausência de Content Security Policy (CSP) — alto risco se exposto
2. IP spoofing no rate limiter via header `X-Forwarded-For`
3. Flag `ignore_https_errors=True` no Playwright (risco de coleta de dados falsificados)

---

## Tabela de Vulnerabilidades

| ID   | Título                                         | Arquivo                              | Linha | Severidade | CVSS Aprox. |
|------|------------------------------------------------|--------------------------------------|-------|------------|-------------|
| SEC-01 | Ausência de Content Security Policy (CSP)   | `web/app.py`                         | 51–84 | ALTO       | 7.4         |
| SEC-02 | IP Spoofing no Rate Limiter                  | `web/ratelimit.py`                   | 82–100| ALTO       | 6.5         |
| SEC-03 | `ignore_https_errors=True` no Playwright     | `collectors/scraper_client.py`       | 96    | ALTO       | 6.1         |
| SEC-04 | CSRF — bypass na primeira requisição POST    | `web/csrf.py`                        | 78–82 | MÉDIO      | 5.4         |
| SEC-05 | `csrf_token_input` retorna HTML sem escape   | `web/csrf.py`                        | 116   | MÉDIO      | 5.0         |
| SEC-06 | `ordem` recebida de Query Param sem whitelist| `web/routes/taxas.py`                | 58    | MÉDIO      | 4.3         |
| SEC-07 | Argumento `tipo` (anomalias) sem whitelist   | `web/routes/anomalias.py`            | 73    | MÉDIO      | 4.3         |
| SEC-08 | `--no-sandbox` no Playwright                 | `collectors/scraper_client.py`       | 62    | MÉDIO      | 4.0         |
| SEC-09 | `validate=False` no parse_cnpj de rotas      | `web/routes/instituicoes.py`         | 77,161| BAIXO      | 3.1         |
| SEC-10 | CDNs externos sem Subresource Integrity (SRI)| `web/templates/base.html`            | 18,24 | BAIXO      | 3.1         |
| SEC-11 | `VEREDAS_DB_ECHO=true` expõe queries SQL     | `config.py`                          | 119   | INFO       | —           |

---

## Evidências e Análise Detalhada

### SEC-01 — Ausência de Content Security Policy (CSP)
**Severidade: ALTO | CVSS: ~7.4 (AV:N/AC:L/PR:N/UI:R/S:C/C:H/I:N/A:N)**

O middleware `SecurityHeadersMiddleware` em `src/veredas/web/app.py` (linhas 51–84) implementa vários headers de segurança, mas omite o `Content-Security-Policy`. Essa ausência é especialmente impactante porque:

1. O template `base.html` carrega recursos de CDNs externos sem hash SRI:
   ```html
   <!-- base.html, linha 18 -->
   <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/@picocss/pico@2/css/pico.min.css">
   <!-- linha 24 -->
   <script src="https://unpkg.com/htmx.org@1.9.10"></script>
   ```
2. Os templates Jinja2 embarcam dados em blocos `<script>` inline via `| tojson`:
   ```html
   <!-- instituicao.html, linha 184 -->
   x: {{ chart_data.dates | tojson }},
   y: {{ chart_data.values | tojson }},
   text: {{ chart_data.labels | tojson }},
   ```
   Sem CSP, qualquer XSS injetado via um campo de dado (ex: nome de emissor proveniente de scraper) executará no contexto do dashboard.

3. O comentário em `app.py` linha 72 menciona "browsers modernos usam CSP", mas o header não foi adicionado.

**Impacto:** Sem CSP, um atacante que conseguir injetar conteúdo malicioso no banco de dados (via scraper comprometido ou dados B3 adulterados) pode executar JavaScript no navegador do usuário.

**Recomendação:**
```python
# Em SecurityHeadersMiddleware.dispatch():
response.headers["Content-Security-Policy"] = (
    "default-src 'self'; "
    "script-src 'self' https://cdn.plot.ly https://unpkg.com 'nonce-{nonce}'; "
    "style-src 'self' https://cdn.jsdelivr.net; "
    "img-src 'self' data: https://raw.githubusercontent.com; "
    "connect-src 'self'; "
    "frame-ancestors 'none';"
)
```

---

### SEC-02 — IP Spoofing no Rate Limiter
**Severidade: ALTO | CVSS: ~6.5 (AV:N/AC:L/PR:N/UI:N/S:U/C:N/I:N/A:H)**

A função `get_client_ip` em `src/veredas/web/ratelimit.py` (linhas 82–100) confia cegamente no header `X-Forwarded-For`:

```python
# ratelimit.py, linhas 88–91
forwarded_for = request.headers.get("X-Forwarded-For")
if forwarded_for:
    # Primeiro IP da lista e o cliente original
    return forwarded_for.split(",")[0].strip()
```

Sem proxy reverso configurado, qualquer cliente pode enviar `X-Forwarded-For: 1.2.3.4` e contornar o rate limiting completamente. O mesmo vale para `X-Real-IP`.

**Impacto:** Bypass total do rate limiting, permitindo DoS ou enumeração irrestrita de endpoints.

**Recomendação:**
```python
# Opção A: Confiar apenas no IP de conexão (uso local/sem proxy)
def get_client_ip(request: Request) -> str:
    if request.client:
        return request.client.host
    return "unknown"

# Opção B: Configurar lista de proxies confiáveis
TRUSTED_PROXIES = {"127.0.0.1", "::1"}  # Adicionar IP do seu nginx/caddy

def get_client_ip(request: Request) -> str:
    direct_ip = request.client.host if request.client else "unknown"
    if direct_ip in TRUSTED_PROXIES:
        forwarded = request.headers.get("X-Forwarded-For", "").split(",")
        return forwarded[0].strip() or direct_ip
    return direct_ip
```

---

### SEC-03 — `ignore_https_errors=True` no Playwright
**Severidade: ALTO | CVSS: ~6.1 (AV:N/AC:H/PR:N/UI:N/S:U/C:H/I:L/A:N)**

Em `src/veredas/collectors/scraper_client.py`, linha 96:

```python
context_kwargs: dict = {"ignore_https_errors": True}
```

Essa configuração instrui o Playwright a aceitar certificados TLS inválidos, expirados ou autoassinados. Em um cenário de ataque Man-in-the-Middle (ex: rede corporativa com inspeção TLS, ou DNS poisoning contra as URLs das corretoras), o coletor aceitaria dados falsificados silenciosamente.

**Impacto:** Dados coletados (taxas de CDB) podem ser adulterados por um atacante intermediário. Anomalias falsas seriam detectadas, ou anomalias reais seriam suprimidas. Em contexto financeiro, isso representa risco de integridade de dados.

**Recomendação:**
```python
# Remover ignore_https_errors ou tornar configurável
context_kwargs: dict = {}  # Verificação TLS habilitada por padrão

# Se necessário para desenvolvimento local, usar variável de ambiente:
import os
if os.getenv("VEREDAS_PLAYWRIGHT_IGNORE_TLS", "false").lower() == "true":
    context_kwargs["ignore_https_errors"] = True
```

---

### SEC-04 — CSRF: Bypass na Primeira Requisição POST
**Severidade: MÉDIO | CVSS: ~5.4 (AV:N/AC:L/PR:N/UI:R/S:U/C:L/I:L/A:N)**

Em `src/veredas/web/csrf.py`, linhas 78–82:

```python
async def _validate_csrf(self, request: Request, expected_token: str) -> None:
    """Validate CSRF token from header or form."""
    # Skip if no token expected (first request)
    cookie_token = request.cookies.get(CSRF_COOKIE_NAME)
    if not cookie_token:
        return  # <-- BYPASS: qualquer POST sem cookie passa
```

Um atacante pode fazer um POST malicioso sem o cookie CSRF e ele será aceito. O cookie é criado na resposta, mas um `fetch()` cross-origin sem credenciais não enviará o cookie — e mesmo assim o POST passará pela validação.

**Impacto:** Um atacante em uma página cross-origin pode fazer um POST ao endpoint `POST /anomalias/{id}/resolver` sem cookie, e o middleware deixará passar.

**Recomendação:**
```python
async def _validate_csrf(self, request: Request, expected_token: str) -> None:
    cookie_token = request.cookies.get(CSRF_COOKIE_NAME)
    # Remover o bypass: exigir token mesmo na primeira requisição POST
    # Alternativa: verificar Origin/Referer header como segunda linha de defesa
    origin = request.headers.get("origin", "")
    host = request.url.netloc
    if origin and not origin.endswith(host):
        raise HTTPException(status_code=403, detail="Origin não autorizada")

    submitted_token = request.headers.get(CSRF_HEADER_NAME)
    if not submitted_token and cookie_token:
        # ... ler form
        pass
    if not submitted_token or (cookie_token and not secrets.compare_digest(submitted_token, cookie_token)):
        raise HTTPException(status_code=403, detail="CSRF token missing or invalid")
```

---

### SEC-05 — `csrf_token_input` Retorna HTML Não-Escapado
**Severidade: MÉDIO | CVSS: ~5.0 (AV:N/AC:H/PR:N/UI:R/S:C/C:L/I:L/A:N)**

Em `src/veredas/web/csrf.py`, linhas 108–116:

```python
def csrf_token_input(request: Request) -> str:
    """
    Usage in Jinja2:
        {{ csrf_token_input(request) | safe }}
    """
    token = get_csrf_token(request)
    return f'<input type="hidden" name="{CSRF_FORM_FIELD}" value="{token}">'
```

A docstring instrui o uso do filtro `| safe` em templates. O token é gerado com `secrets.token_urlsafe(32)`, cujos caracteres são restritos a `[A-Za-z0-9_-]`, o que torna a XSS improvável neste campo específico. Porém, a prática de documentar `| safe` como padrão é perigosa: se a função for modificada ou reutilizada com dados de outra fonte, o contexto de segurança desaparece sem aviso.

**Recomendação:**
```python
from markupsafe import Markup

def csrf_token_input(request: Request) -> Markup:
    """Retorna Markup (HTML seguro) — não requer | safe no template."""
    token = get_csrf_token(request)
    # Markup escapa automaticamente caracteres HTML perigosos
    return Markup(
        f'<input type="hidden" name="{CSRF_FORM_FIELD}" value="{token}">'
    )
```
Com `Markup`, o Jinja2 não re-escapa o resultado e não é necessário `| safe`.

---

### SEC-06 — Parâmetro `ordem` Sem Whitelist em `/taxas`
**Severidade: MÉDIO | CVSS: ~4.3 (AV:N/AC:L/PR:N/UI:N/S:U/C:L/I:N/A:N)**

Em `src/veredas/web/routes/taxas.py`, linha 33:

```python
ordem: str = Query("data_desc", description="Ordenacao"),
```

O valor de `ordem` é passado diretamente para `TaxaCDBRepository.list_paginated()` (linha 58), onde é comparado em uma cadeia `if/elif`:

```python
# repository.py, linhas 275–286
if order_by == "data_desc":
    stmt = stmt.order_by(desc(TaxaCDB.data_coleta))
elif order_by == "data_asc":
    ...
elif order_by == "spread_desc":
    ...
```

O padrão if/elif é seguro contra SQL injection (o valor nunca é interpolado em SQL raw). No entanto, valores não reconhecidos simplesmente ignoram a ordenação sem retornar erro, o que pode ser explorado para inferir comportamento interno via enumeração. O risco real é de information disclosure sobre a lógica de ordenação.

**Recomendação:**
```python
ORDENS_VALIDAS = {"data_desc", "data_asc", "spread_desc", "spread_asc", "taxa_desc", "taxa_asc"}

ordem: str = Query(
    "data_desc",
    description="Ordenacao",
    pattern="^(data_desc|data_asc|spread_desc|spread_asc|taxa_desc|taxa_asc)$",
)
```

---

### SEC-07 — Parâmetro `tipo` (Anomalias) Sem Whitelist
**Severidade: MÉDIO | CVSS: ~4.3 (AV:N/AC:L/PR:N/UI:N/S:U/C:L/I:N/A:N)**

Em `src/veredas/web/routes/anomalias.py`, linha 55:

```python
tipo: str | None = Query(None, description="Filtro por tipo de anomalia"),
```

O `tipo` é passado para `AnomaliaRepository.list_with_filters()`, que o usa como:

```python
# repository.py, linha 451
stmt = stmt.where(Anomalia.tipo == filters["tipo"])
```

O SQLAlchemy vincula o valor como parâmetro (sem SQL injection). Porém, qualquer string arbitrária pode ser enviada. Se o valor não corresponder a nenhum `TipoAnomalia`, a query retorna zero resultados sem erro — vazamento de informação sobre a estrutura interna via oracle de enumeração.

**Recomendação:**
```python
# Em anomalias.py: validar contra o enum antes de usar
if tipo:
    try:
        TipoAnomalia(tipo)  # Valida o valor
        filters["tipo"] = tipo
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Tipo de anomalia inválido: '{tipo}'")
```

---

### SEC-08 — `--no-sandbox` no Chromium do Playwright
**Severidade: MÉDIO | CVSS: ~4.0 (AV:L/AC:H/PR:L/UI:N/S:U/C:H/I:H/A:N)**

Em `src/veredas/collectors/scraper_client.py`, linha 62:

```python
self._browser = await self._playwright.chromium.launch(
    headless=self._headless,
    args=["--no-sandbox", "--disable-dev-shm-usage"],
)
```

A flag `--no-sandbox` desabilita o sandbox do processo renderizador do Chromium. Em ambientes Linux com restrições de namespace (ex: Docker sem `--privileged`, CI/CD), essa flag é tecnicamente necessária. Porém, ela expande o impacto de qualquer exploit de execução de código no browser (ex: JavaScript malicioso em páginas coletadas que explore uma vulnerabilidade do Chromium) para escalar para o processo host.

**Contexto:** O risco é baixo para uso local no Windows (onde o `--no-sandbox` tem impacto menor que no Linux). Torna-se relevante se o coletor for executado em container Linux.

**Recomendação:**
```python
import platform, os

args = []
# --no-sandbox necessário apenas em Linux sem user namespace
if platform.system() == "Linux" and os.getenv("VEREDAS_PLAYWRIGHT_NO_SANDBOX"):
    args = ["--no-sandbox", "--disable-dev-shm-usage"]

self._browser = await self._playwright.chromium.launch(
    headless=self._headless,
    args=args,
)
```
Para produção em Docker, prefira `--cap-add SYS_ADMIN` ou use a imagem oficial `mcr.microsoft.com/playwright`.

---

### SEC-09 — `validate=False` no parse_cnpj de Rotas
**Severidade: BAIXO | CVSS: ~3.1 (AV:N/AC:H/PR:N/UI:N/S:U/C:L/I:N/A:N)**

Em `src/veredas/web/routes/instituicoes.py`, linhas 77 e 161:

```python
cnpj_normalizado = parse_cnpj(cnpj, required=True, validate=False)
```

O parâmetro `validate=False` desabilita a verificação dos dígitos verificadores do CNPJ. Qualquer string de 14 dígitos é aceita como CNPJ válido. Isso pode ser usado para testar a existência de registros no banco (oracle de enumeração) sem precisar conhecer um CNPJ matematicamente válido.

**Recomendação:**
```python
cnpj_normalizado = parse_cnpj(cnpj, required=True, validate=True)
```

---

### SEC-10 — CDNs Externos Sem Subresource Integrity (SRI)
**Severidade: BAIXO | CVSS: ~3.1 (AV:N/AC:H/PR:N/UI:R/S:C/C:L/I:L/A:N)**

Em `src/veredas/web/templates/base.html` e `instituicao.html`:

```html
<!-- base.html, linha 18 -->
<link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/@picocss/pico@2/css/pico.min.css">
<!-- base.html, linha 24 -->
<script src="https://unpkg.com/htmx.org@1.9.10"></script>
<!-- instituicao.html, linha 7 -->
<script src="https://cdn.plot.ly/plotly-2.27.0.min.js"></script>
```

Sem atributos `integrity` (SRI), se os CDNs forem comprometidos (supply chain attack), JavaScript malicioso seria carregado automaticamente por todos os usuários do dashboard.

**Recomendação:**
```html
<script src="https://unpkg.com/htmx.org@1.9.10"
        integrity="sha384-D1Kt99CQMDuVetoL1lrYwg5t+9QdHe7NLX/SoJYkXDFfX37iInKRy5ViYgSibmK"
        crossorigin="anonymous"></script>
```
Gere os hashes com: `curl -s URL | openssl dgst -sha384 -binary | openssl base64 -A`

---

### SEC-11 — `VEREDAS_DB_ECHO=true` Expõe Queries SQL
**Severidade: INFO**

Em `src/veredas/config.py`, linha 119:

```python
echo: bool = Field(
    default=False,
    description="Mostrar queries SQL no console",
)
```

A opção `VEREDAS_DB_ECHO=true` habilita logging de todas as queries SQL pelo SQLAlchemy, incluindo queries com valores sensíveis (ex: valores de taxas, status de anomalias). Embora o padrão seja `False`, não há aviso na documentação de que isso não deve ser habilitado em produção.

**Recomendação:** Adicionar aviso no `.env.example`:
```
# ATENÇÃO: Nunca habilite em produção — expõe queries com dados financeiros nos logs
# VEREDAS_DB_ECHO=false
```

---

## Análise por Categoria

### 1. Injeção SQL

**Resultado: SEM VULNERABILIDADES**

Todo acesso ao banco de dados utiliza SQLAlchemy 2.0 com queries parametrizadas via ORM. Não foi encontrada nenhuma chamada a `text()`, `execute()` com interpolação de string, ou qualquer forma de raw SQL com entrada de usuário. Os filtros passados via query parameters são todos comparados contra valores ORM:

```python
# repository.py — exemplo típico
stmt = stmt.where(Anomalia.severidade == filters["severidade"])  # parametrizado
stmt = stmt.where(InstituicaoFinanceira.cnpj == filters["cnpj"])  # parametrizado
```

### 2. Cross-Site Scripting (XSS)

**Resultado: RISCO RESIDUAL — sem instâncias imediatas, vetor futuro identificado**

- Nenhum uso de `| safe` encontrado nos templates
- Nenhum uso de `Markup()` com dados externos
- O Jinja2 tem autoescape habilitado por padrão para HTML
- **Risco futuro:** Dados de scrapers (nomes de emissores, textos de taxas) são armazenados no banco e renderizados em templates. Se um site de corretora for comprometido e retornar um nome de emissor com payload XSS (`<script>alert(1)</script>`), o Jinja2 fará o escape. Porém, esses mesmos dados são serializados como JSON em blocos `<script>` inline via `| tojson` — o filtro `tojson` do Jinja2 escapa corretamente os caracteres perigosos para contexto JavaScript, mas a ausência de CSP (SEC-01) amplifica qualquer falha nessa cadeia.

### 3. Server-Side Request Forgery (SSRF)

**Resultado: RISCO BAIXO — URLs hardcoded, sem input de usuário**

Os coletores fazem requests a URLs fixas definidas como constantes:

```python
# xp.py
_URL = "https://www.xpi.com.br/investimentos/renda-fixa/"
# btg.py
_URL = "https://www.btgpactualdigital.com/renda-fixa"
```

Nenhuma URL é construída a partir de input de usuário. O SSRF não é aplicável no estado atual do código.

### 4. Segredos em Código

**Resultado: SEM VULNERABILIDADES**

- `.env` está no `.gitignore` (confirmado)
- Tokens do Telegram e credenciais SMTP são lidos exclusivamente de variáveis de ambiente via `pydantic-settings`
- O `.env` presente no repositório é **idêntico** ao `.env.example` — contém apenas comentários, sem valores reais
- Nenhum token, API key ou senha foi encontrado hardcoded

### 5. CSRF

**Resultado: IMPLEMENTAÇÃO PRESENTE COM FALHA PARCIAL (SEC-04)**

O middleware `CSRFMiddleware` usa o padrão Double Submit Cookie com `secrets.compare_digest` (timing-safe). O HTMX está configurado para enviar o header `X-CSRF-Token` em todas as requisições mutáveis. A falha está no bypass para requisições POST sem cookie pré-existente (SEC-04).

### 6. Validação de Entrada

**Resultado: BOA COBERTURA, LACUNAS PONTUAIS**

- Tipos numéricos (`taxa_id: int`, `pagina: int`, `por_pagina: int`) são validados pelo FastAPI
- Limites aplicados: `ge=1`, `le=100` em parâmetros de paginação
- Enums (`indexador`, `severidade`) são validados explicitamente
- CNPJ tem validador dedicado com dígitos verificadores
- **Lacunas:** `ordem` e `tipo` sem whitelist formal (SEC-06, SEC-07)

### 7. Playwright (Browser Automation)

**Resultado: DOIS ACHADOS — SEC-03 e SEC-08**

- `ignore_https_errors=True` (SEC-03): aceita certificados inválidos
- `--no-sandbox` (SEC-08): reduz sandbox de processo em Linux
- URLs de coleta são hardcoded (sem SSRF via Playwright)
- O browser opera apenas no modo de leitura (GET), sem executar ações autenticadas

### 8. Dependências

**Resultado: INFO — versões mínimas definidas, sem CVEs conhecidos no momento da auditoria**

Dependências relevantes no `pyproject.toml`:

| Pacote | Versão mínima | Observação |
|--------|--------------|-----------|
| `fastapi` | `>=0.109.0` | Versão atual sem CVEs críticos conhecidos |
| `sqlalchemy` | `>=2.0.0` | API moderna, parametrização padrão |
| `playwright` | `>=1.44.0` | Atualizar regularmente (Chromium engine) |
| `jinja2` | `>=3.1.0` | Autoescape habilitado por padrão em HTML |
| `httpx` | `>=0.27.0` | Sem CVEs conhecidos |
| `pydantic` | `>=2.6.0` | v2, sem CVEs críticos conhecidos |
| `python-multipart` | `>=0.0.9` | CVE-2024-53498 corrigido em 0.0.13 — **atualizar** |

**Ação recomendada:** Atualizar `python-multipart` para `>=0.0.13`:
```toml
"python-multipart>=0.0.13",  # CVE-2024-53498: ReDoS em multipart parsing
```

### 9. Configuração e Logs

**Resultado: BOM — sem dados sensíveis nos logs padrão**

- Nenhum log expõe tokens, senhas ou dados financeiros individuais
- O `logger.exception()` nos módulos de alertas não registra credenciais (apenas mensagens genéricas de falha)
- `VEREDAS_DB_ECHO=false` por padrão (SEC-11 apenas informativo)

### 10. Rate Limiting e DoS

**Resultado: IMPLEMENTADO, COM VETOR DE BYPASS (SEC-02)**

- 60 req/min por IP no middleware global
- Paths estáticos e `/health` excluídos corretamente
- Sliding window com cleanup periódico de memória
- `StrictRateLimitMiddleware` (10 req/min) definido mas não registrado no `create_app()` — considerar aplicar em `/anomalias/` e endpoints de exportação CSV

---

## Recomendações Consolidadas por Prioridade

### Prioridade 1 — Implementar antes de qualquer exposição pública

**1.1 Adicionar Content-Security-Policy** (`web/app.py`)
```python
# Em SecurityHeadersMiddleware.dispatch():
response.headers["Content-Security-Policy"] = (
    "default-src 'self'; "
    "script-src 'self' https://cdn.plot.ly https://unpkg.com; "
    "style-src 'self' https://cdn.jsdelivr.net; "
    "img-src 'self' data:; "
    "connect-src 'self'; "
    "frame-ancestors 'none';"
)
```

**1.2 Corrigir rate limiter para não confiar em X-Forwarded-For sem proxy confiável** (`web/ratelimit.py`)

**1.3 Remover `ignore_https_errors=True`** (`collectors/scraper_client.py`)

### Prioridade 2 — Implementar no próximo ciclo de desenvolvimento

**2.1 Corrigir bypass CSRF na primeira requisição** (`web/csrf.py`)

**2.2 Trocar `csrf_token_input` para retornar `Markup`** (`web/csrf.py`)

**2.3 Adicionar whitelist para `ordem` com `pattern=` no Query param** (`web/routes/taxas.py`)

**2.4 Validar `tipo` contra `TipoAnomalia` enum** (`web/routes/anomalias.py`)

**2.5 Atualizar `python-multipart` para `>=0.0.13`** (`pyproject.toml`)

### Prioridade 3 — Melhorias de hardening

**3.1 Habilitar `validate=True` no parse_cnpj das rotas** (`web/routes/instituicoes.py`)

**3.2 Adicionar SRI aos recursos de CDN** (`web/templates/base.html`, `instituicao.html`)

**3.3 Condicionar `--no-sandbox` à variável de ambiente** (`collectors/scraper_client.py`)

**3.4 Registrar `StrictRateLimitMiddleware` nos endpoints de exportação CSV**

---

## Checklist de Boas Práticas para Projeto FOSS Financeiro

### Gestão de Segredos
- [x] Segredos via variáveis de ambiente (`pydantic-settings`)
- [x] `.env` no `.gitignore`
- [x] `.env.example` com valores placeholder (sem dados reais)
- [ ] Considerar `detect-secrets` como hook de pre-commit
- [ ] Documentar rotação de tokens Telegram e senhas SMTP

### Autenticação e Autorização
- [x] Rate limiting implementado
- [x] CSRF protection com `secrets.compare_digest`
- [ ] Adicionar autenticação básica para deploy público (Basic Auth ou OAuth2)
- [ ] Considerar endpoint `/health` separado, sem autenticação

### Transporte e Headers
- [x] `X-Frame-Options: DENY`
- [x] `X-Content-Type-Options: nosniff`
- [x] `Referrer-Policy: strict-origin-when-cross-origin`
- [x] `Permissions-Policy` configurado
- [ ] **Adicionar Content-Security-Policy** (SEC-01)
- [ ] Adicionar SRI em recursos de CDN (SEC-10)
- [ ] Configurar HSTS se exposto via HTTPS

### Banco de Dados
- [x] Uso exclusivo de ORM parametrizado (zero raw SQL)
- [x] Migrações com Alembic
- [x] Banco em diretório fora do código (`~/.veredas/`)
- [ ] Considerar criptografia do banco SQLite em produção (SQLCipher)
- [ ] Backup automático do banco

### Dependências
- [x] Versões mínimas especificadas no `pyproject.toml`
- [x] Ferramentas de qualidade: `ruff`, `mypy`, `bandit` configurados
- [ ] Executar `pip-audit` ou `safety check` no CI/CD
- [ ] Atualizar `python-multipart` para `>=0.0.13`
- [ ] Atualizar Playwright/Chromium regularmente

### Coleta de Dados Externos
- [x] URLs hardcoded (sem SSRF via input de usuário)
- [x] Rate limiting nos coletores (2s entre requests)
- [x] Retry com backoff exponencial
- [x] Timeout configurável
- [ ] Remover `ignore_https_errors=True` (SEC-03)
- [ ] Validar e sanitizar dados coletados antes de persistir no banco
- [ ] Considerar assinatura/hash dos dados coletados para detectar adulteração

### Logging e Auditoria
- [x] Logs de falhas nos alertas sem exposição de credenciais
- [x] Sem dados sensíveis nos logs padrão
- [ ] Log de auditoria para ações mutáveis do dashboard (resolver anomalia)
- [ ] Configurar nível de log via variável de ambiente em produção

### Deployment Self-Hosted
- [ ] Documentar uso obrigatório de proxy reverso (nginx/caddy) com HTTPS
- [ ] Instruções de firewall: expor apenas portas 80/443
- [ ] Desabilitar `--reload` em produção (`uvicorn` com `reload=False`)
- [ ] Considerar `systemd` unit file para gerenciamento do processo

---

## Apêndice — Arquivos Auditados

| Arquivo | Linhas analisadas |
|---------|------------------|
| `src/veredas/web/app.py` | Completo |
| `src/veredas/web/csrf.py` | Completo |
| `src/veredas/web/ratelimit.py` | Completo |
| `src/veredas/web/cache.py` | Completo |
| `src/veredas/web/dependencies.py` | Completo |
| `src/veredas/web/routes/home.py` | Completo |
| `src/veredas/web/routes/taxas.py` | Completo |
| `src/veredas/web/routes/anomalias.py` | Completo |
| `src/veredas/web/routes/instituicoes.py` | Completo |
| `src/veredas/web/templates/base.html` | Completo |
| `src/veredas/web/templates/instituicao.html` | Completo |
| `src/veredas/web/templates/partials/*.html` | Completo |
| `src/veredas/collectors/scraper_base.py` | Completo |
| `src/veredas/collectors/scraper_client.py` | Completo |
| `src/veredas/collectors/scrapers/xp.py` | Completo |
| `src/veredas/collectors/scrapers/btg.py` | Completo |
| `src/veredas/collectors/b3/downloader.py` | Completo |
| `src/veredas/alerts/telegram.py` | Completo |
| `src/veredas/alerts/email.py` | Completo |
| `src/veredas/storage/models.py` | Completo |
| `src/veredas/storage/repository.py` | Completo |
| `src/veredas/storage/database.py` | Completo |
| `src/veredas/config.py` | Completo |
| `src/veredas/validators.py` | Completo |
| `src/veredas/cli/main.py` | Completo |
| `pyproject.toml` | Completo |
| `.env`, `.env.example`, `.gitignore` | Completo |
