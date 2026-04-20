# Guia de Instalação

## Requisitos

- Python 3.11 ou superior
- pip ou uv (gerenciador de pacotes)
- Git

## Instalação

### 1. Clonar o repositório

```bash
git clone https://github.com/ffreitasb/veredas-de-papel.git
cd veredas-de-papel
```

### 2. Criar ambiente virtual

```bash
python -m venv .venv

# Linux/macOS
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
pip install -e ".[dev]"      # ferramentas de desenvolvimento
pip install -e ".[ml]"       # detectores de Machine Learning
pip install -e ".[alerts]"   # alertas Telegram e Email
```

### Instalação via uv (mais rápido)

```bash
pip install uv
git clone https://github.com/ffreitasb/veredas-de-papel.git
cd veredas-de-papel
uv venv && source .venv/bin/activate  # ou .venv\Scripts\activate no Windows
uv pip install -e ".[dev,web,ml,alerts]"
```

## Verificar instalação

```bash
veredas --version
veredas --help
```

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

## Inicializar o banco de dados

O banco de dados é gerenciado via **Alembic** (migrações versionadas). O comando `init` aplica automaticamente todas as migrações pendentes:

```bash
veredas init
```

O banco SQLite é criado em `data/veredas.db` (ou no caminho definido por `VEREDAS_DB_PATH`).

Para aplicar migrações manualmente (usuários avançados):

```bash
python -m alembic upgrade head
```

## Dependências opcionais

| Grupo | Descrição | Comando |
|-------|-----------|---------|
| `dev` | pytest, ruff, mypy | `pip install -e ".[dev]"` |
| `ml` | scikit-learn (Isolation Forest, DBSCAN) | `pip install -e ".[ml]"` |
| `web` | FastAPI, Jinja2, uvicorn | `pip install -e ".[web]"` |
| `alerts` | httpx (Telegram), aiosmtplib (Email) | `pip install -e ".[alerts]"` |

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

## Próximos passos

Após a instalação, consulte o [Guia da CLI](cli-guide.md) para aprender a usar todos os comandos.
