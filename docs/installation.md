# Guia de Instalacao

## Requisitos

- Python 3.11 ou superior
- pip ou uv (gerenciador de pacotes)
- Git (opcional, para clonar o repositorio)

## Instalacao via pip

### 1. Clonar o repositorio

```bash
git clone https://github.com/ffreitasb/veredas-de-papel.git
cd veredas-de-papel
```

### 2. Criar ambiente virtual (recomendado)

```bash
python -m venv .venv

# Linux/macOS
source .venv/bin/activate

# Windows
.venv\Scripts\activate
```

### 3. Instalar dependencias

```bash
# Instalacao basica
pip install -e .

# Com dependencias de desenvolvimento
pip install -e ".[dev]"

# Com todas as dependencias opcionais
pip install -e ".[dev,ml,dashboard,alerts]"
```

## Instalacao via uv (mais rapido)

```bash
# Instalar uv se nao tiver
pip install uv

# Clonar e instalar
git clone https://github.com/ffreitasb/veredas-de-papel.git
cd veredas-de-papel
uv venv
source .venv/bin/activate  # ou .venv\Scripts\activate no Windows
uv pip install -e ".[dev]"
```

## Verificar instalacao

```bash
# Verificar versao
veredas --version

# Ver ajuda
veredas --help
```

## Inicializar o banco de dados

```bash
# Criar banco de dados SQLite
veredas init

# Inicializar com dados de exemplo (seeds)
veredas init --seed
```

O banco de dados sera criado em `~/.veredas/veredas.db`.

## Configuracao

### Variaveis de ambiente

O veredas pode ser configurado via variaveis de ambiente:

```bash
# Caminho do banco de dados
export VEREDAS_DB_PATH=/caminho/personalizado/veredas.db

# Modo debug
export VEREDAS_DEBUG=true

# Thresholds de deteccao
export VEREDAS_SPREAD_ALTO=130
export VEREDAS_SPREAD_CRITICO=150
```

### Arquivo .env

Voce tambem pode criar um arquivo `.env` na raiz do projeto:

```env
VEREDAS_DB_PATH=~/.veredas/veredas.db
VEREDAS_DEBUG=false
VEREDAS_SPREAD_ALTO=130
VEREDAS_SPREAD_CRITICO=150
```

## Dependencias opcionais

| Grupo | Descricao | Comando |
|-------|-----------|---------|
| `dev` | Ferramentas de desenvolvimento (pytest, ruff, mypy) | `pip install -e ".[dev]"` |
| `ml` | Machine Learning (scikit-learn) | `pip install -e ".[ml]"` |
| `dashboard` | Dashboard web (streamlit) | `pip install -e ".[dashboard]"` |
| `alerts` | Sistema de alertas (telegram) | `pip install -e ".[alerts]"` |

## Problemas comuns

### Erro ao instalar python-bcb

Se encontrar erros ao instalar a biblioteca `python-bcb`:

```bash
pip install --upgrade pip setuptools wheel
pip install python-bcb
```

### Erro de permissao ao criar ~/.veredas

Se nao conseguir criar o diretorio de dados:

```bash
# Especificar outro diretorio
export VEREDAS_DATA_DIR=/outro/diretorio
veredas init
```

### Erro de conexao com o Banco Central

A API do Banco Central pode estar temporariamente indisponivel. Verifique:

```bash
# Testar conectividade
veredas status
```

## Proximos passos

Apos a instalacao, consulte o [Guia da CLI](cli-guide.md) para aprender a usar os comandos.
