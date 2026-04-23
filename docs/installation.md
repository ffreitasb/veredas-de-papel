# Guia de Instalação

## Requisitos

- Python 3.11 ou superior
- Git

---

## Instalação com uv (recomendado)

[uv](https://docs.astral.sh/uv/) é um gerenciador de pacotes Python ultrarrápido (escrito em Rust) que cuida de Python, venv e dependências em um único fluxo — sem etapas manuais de ativação de ambiente.

### 1. Instalar o uv

```bash
# macOS / Linux
curl -LsSf https://astral.sh/uv/install.sh | sh

# Windows (PowerShell)
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"

# Alternativa via pip ou brew
pip install uv
brew install uv
```

### 2. Clonar o repositório

```bash
git clone https://github.com/ffreitasb/veredas-de-papel.git
cd veredas-de-papel
```

### 3. Criar venv e instalar dependências

```bash
# Instalação completa (recomendada)
uv sync --extra dev --extra web --extra ml --extra alerts

# Apenas funcionalidades básicas
uv sync

# Por grupo de funcionalidade
uv sync --extra web        # dashboard web
uv sync --extra ml         # detectores de Machine Learning
uv sync --extra alerts     # alertas Telegram e Email
uv sync --extra dev        # ferramentas de desenvolvimento
```

O uv cria automaticamente o `.venv` na raiz do projeto. Para rodar comandos:

```bash
# Prefixar com uv run (sem precisar ativar o venv)
uv run veredas --version
uv run pytest

# Ou ativar o venv manualmente
source .venv/bin/activate      # Linux/macOS
.venv\Scripts\activate         # Windows
veredas --version
```

---

## Instalação com pip e venv (alternativa clássica)

### 1. Clonar o repositório

```bash
git clone https://github.com/ffreitasb/veredas-de-papel.git
cd veredas-de-papel
```

### 2. Criar e ativar ambiente virtual

```bash
python -m venv .venv

# Linux / macOS
source .venv/bin/activate

# Windows
.venv\Scripts\activate
```

### 3. Instalar dependências

```bash
# Instalação completa (recomendada)
pip install -e ".[dev,web,ml,alerts]"

# Apenas funcionalidades básicas
pip install -e .

# Por grupo de funcionalidade
pip install -e ".[dev]"       # ferramentas de desenvolvimento
pip install -e ".[web]"       # dashboard web
pip install -e ".[ml]"        # detectores de Machine Learning
pip install -e ".[alerts]"    # alertas Telegram e Email
```

---

## Verificar instalação

```bash
veredas --version
veredas --help
```

---

## Dependências opcionais

| Grupo | Descrição |
|-------|-----------|
| `dev` | pytest, ruff, mypy, pre-commit |
| `web` | FastAPI, Jinja2, uvicorn, plotly |
| `ml` | scikit-learn (Isolation Forest, DBSCAN), ruptures (PELT) |
| `alerts` | Telegram Bot API, aiosmtplib (Email SMTP) |

---

## Configuração

### Arquivo .env

Copie o arquivo de exemplo e edite conforme necessário:

```bash
cp .env.example .env
```

As variáveis disponíveis:

```env
# Banco de dados (padrão: data/veredas.db na raiz do projeto)
VEREDAS_DB_PATH=/caminho/personalizado/veredas.db

# Modo debug
VEREDAS_DEBUG=false

# Thresholds de detecção (valores padrão)
VEREDAS_SPREAD_ALTO=130
VEREDAS_SPREAD_CRITICO=150

# Alertas — Telegram
VEREDAS_TELEGRAM_BOT_TOKEN=
VEREDAS_TELEGRAM_CHAT_ID=

# Alertas — Email (SMTP)
VEREDAS_SMTP_HOST=smtp.gmail.com
VEREDAS_SMTP_PORT=587
VEREDAS_SMTP_USER=
VEREDAS_SMTP_PASSWORD=
VEREDAS_ALERT_EMAIL_TO=
```

Para uso local básico as variáveis de alerta podem permanecer vazias — os canais são simplesmente ignorados quando não configurados.

---

## Inicializar o banco de dados

O banco de dados é gerenciado via **Alembic** (migrações versionadas):

```bash
veredas init
```

Cria o banco SQLite em `data/veredas.db` (ou no caminho definido por `VEREDAS_DB_PATH`).

Para aplicar migrações manualmente (usuários avançados):

```bash
python -m alembic upgrade head
# ou
uv run python -m alembic upgrade head
```

---

## Problemas comuns

### Erro ao instalar python-bcb

```bash
pip install --upgrade pip setuptools wheel
pip install python-bcb
```

### Banco de dados não encontrado

Certifique-se de ter rodado `veredas init` antes de qualquer outro comando. Se estiver usando `VEREDAS_DB_PATH`, verifique se o diretório pai existe.

### Erro de conexão com o Banco Central

A API do Banco Central pode estar temporariamente indisponível:

```bash
veredas status
```

### Alertas não funcionam

Verifique se os tokens/credenciais estão corretamente definidos no `.env` e teste com:

```bash
veredas alerts status   # mostra canais configurados
veredas alerts test     # envia mensagem de teste
```

---

## Próximos passos

Após a instalação, consulte o [Guia da CLI](cli-guide.md) para aprender a usar todos os comandos.
