# Guia da CLI

O veredas de papel oferece uma interface de linha de comando (CLI) completa para monitorar taxas de CDB e detectar anomalias.

## Comandos disponiveis

```bash
veredas --help
```

| Comando | Descricao |
|---------|-----------|
| `init` | Inicializa o banco de dados |
| `collect` | Coleta dados de taxas |
| `analyze` | Analisa e detecta anomalias |
| `alerts` | Gerencia alertas |
| `export` | Exporta dados |
| `status` | Mostra status do sistema |

## init - Inicializar banco de dados

```bash
# Criar banco de dados
veredas init

# Criar banco em caminho especifico
veredas init --db /caminho/para/banco.db

# Inicializar com dados de exemplo
veredas init --seed
```

## collect - Coletar dados

### Coletar do Banco Central (BCB)

```bash
# Coletar Selic, CDI e IPCA
veredas collect bcb

# Especificar banco de dados
veredas collect bcb --db /caminho/banco.db
```

### Fontes disponiveis

| Fonte | Dados coletados |
|-------|-----------------|
| `bcb` | Taxa Selic, CDI, IPCA |
| `ifdata` | Indicadores das IFs (futuro) |

## analyze - Detectar anomalias

```bash
# Analisar todas as taxas
veredas analyze

# Analisar IF especifica
veredas analyze --if "Banco Master"

# Analisar com thresholds personalizados
veredas analyze --spread-alto 140 --spread-critico 160

# Especificar banco de dados
veredas analyze --db /caminho/banco.db
```

### Tipos de anomalias detectadas

| Tipo | Descricao | Severidade |
|------|-----------|------------|
| `SPREAD_ALTO` | CDB > 130% CDI | HIGH |
| `SPREAD_CRITICO` | CDB > 150% CDI | CRITICAL |
| `SALTO_BRUSCO` | Variacao > 10pp em 7 dias | MEDIUM |
| `SALTO_EXTREMO` | Variacao > 20pp em 7 dias | HIGH |
| `DIVERGENCIA` | Taxa > media + 2 desvios | MEDIUM |
| `DIVERGENCIA_EXTREMA` | Taxa > media + 3 desvios | HIGH |

## alerts - Gerenciar alertas

```bash
# Listar alertas ativos
veredas alerts --list

# Filtrar por severidade
veredas alerts --list --severity critical

# Marcar alerta como resolvido
veredas alerts --resolve <id>

# Limpar alertas antigos
veredas alerts --clear --older-than 30
```

## export - Exportar dados

```bash
# Exportar taxas para CSV
veredas export --format csv --output taxas.csv

# Exportar anomalias para JSON
veredas export --format json --output anomalias.json --type anomalias

# Exportar periodo especifico
veredas export --format csv --start 2025-01-01 --end 2025-01-31
```

### Formatos suportados

| Formato | Descricao |
|---------|-----------|
| `csv` | Valores separados por virgula |
| `json` | JSON estruturado |

### Tipos de dados

| Tipo | Descricao |
|------|-----------|
| `taxas` | Taxas de CDB coletadas |
| `anomalias` | Anomalias detectadas |
| `instituicoes` | Instituicoes financeiras |

## status - Status do sistema

```bash
# Mostrar status geral
veredas status

# Formato detalhado
veredas status --verbose
```

Exibe:
- Versao do veredas
- Caminho do banco de dados
- Numero de registros
- Ultima coleta
- Anomalias ativas

## Exemplos de uso

### Fluxo basico de monitoramento

```bash
# 1. Inicializar (apenas primeira vez)
veredas init --seed

# 2. Coletar dados
veredas collect bcb

# 3. Analisar
veredas analyze

# 4. Ver alertas
veredas alerts --list

# 5. Exportar relatorio
veredas export --format csv --output relatorio.csv
```

### Monitoramento automatizado (cron)

```bash
# Adicionar ao crontab (Linux/macOS)
# Executa coleta e analise a cada hora

0 * * * * /usr/local/bin/veredas collect bcb && /usr/local/bin/veredas analyze
```

### Script de monitoramento

```bash
#!/bin/bash
# monitor.sh - Script de monitoramento

set -e

echo "Coletando dados..."
veredas collect bcb

echo "Analisando..."
veredas analyze

echo "Alertas ativos:"
veredas alerts --list --severity high

echo "Exportando..."
veredas export --format json --output "relatorio_$(date +%Y%m%d).json"
```

## Opcoes globais

| Opcao | Descricao |
|-------|-----------|
| `--help` | Mostra ajuda |
| `--version` | Mostra versao |
| `--db PATH` | Especifica banco de dados |

## Codigos de saida

| Codigo | Significado |
|--------|-------------|
| 0 | Sucesso |
| 1 | Erro geral |
| 2 | Erro de argumentos |

## Proximos passos

- Configure alertas por email ou Telegram (fase 2)
- Explore o dashboard web (fase 2)
- Contribua com o projeto no GitHub
