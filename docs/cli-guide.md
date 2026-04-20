# Guia da CLI

O veredas de papel oferece uma interface de linha de comando (CLI) completa para coleta de dados, análise de anomalias e gerenciamento de alertas.

```bash
veredas --help
```

## Referência de comandos

| Comando | Descrição |
|---------|-----------|
| `veredas init` | Inicializa o banco de dados (aplica migrações Alembic) |
| `veredas collect bcb` | Coleta dados macroeconômicos do Banco Central |
| `veredas collect ifdata` | Importa indicadores prudenciais das IFs (IFData) |
| `veredas analyze` | Detecta anomalias no conjunto de dados |
| `veredas detectors` | Lista detectores registrados e seus parâmetros |
| `veredas status` | Mostra integridade do banco e quantidade de registros |
| `veredas alerts status` | Exibe canais de alerta configurados |
| `veredas alerts test` | Envia mensagem de teste pelos canais configurados |

---

## init

```bash
veredas init
```

Aplica todas as migrações pendentes do Alembic, criando ou atualizando o esquema do banco de dados. Seguro para executar múltiplas vezes (idempotente).

O banco SQLite é criado em `data/veredas.db` (ou no caminho definido por `VEREDAS_DB_PATH`).

---

## collect

### bcb — Banco Central do Brasil

```bash
veredas collect bcb
```

Sincroniza dados históricos de taxas de referência da API pública do Banco Central: Selic, CDI e IPCA.

```bash
# Especificar banco de dados
veredas collect bcb --db /caminho/banco.db
```

### ifdata — Indicadores Prudenciais das IFs

```bash
veredas collect ifdata
```

Importa indicadores de saúde financeira das instituições financeiras do portal **IFData** do Banco Central. Os dados incluem:

- Índice de Basileia (solvência)
- Índice de Liquidez
- Patrimônio Líquido
- Ativos Totais e Depósitos
- Inadimplência
- ROA e ROE

Esses dados são utilizados pelos detectores `BASILEIA_BAIXO` e `LIQUIDEZ_CRITICA` para cruzar taxas de CDB elevadas com indicadores reais de fragilidade financeira.

```bash
# Especificar banco de dados
veredas collect ifdata --db /caminho/banco.db
```

---

## analyze

```bash
veredas analyze
```

Executa o pipeline completo de detecção de anomalias sobre todas as taxas armazenadas.

```bash
# Analisar IF específica
veredas analyze --if "Banco Master"

# Usar thresholds personalizados
veredas analyze --spread-alto 140 --spread-critico 160

# Especificar banco de dados
veredas analyze --db /caminho/banco.db
```

### Tipos de anomalias detectadas

**Regras Determinísticas**

| Tipo | Condição | Severidade |
|------|----------|------------|
| `SPREAD_ALTO` | CDB > 130% CDI | HIGH |
| `SPREAD_CRITICO` | CDB > 150% CDI | CRITICAL |
| `SALTO_BRUSCO` | Variação > 10pp em 7 dias | MEDIUM |
| `SALTO_EXTREMO` | Variação > 20pp em 7 dias | HIGH |

**Estatística Avançada**

| Tipo | Método |
|------|--------|
| `DIVERGENCIA` | Z-Score > 2σ acima da média do mercado |
| `DIVERGENCIA_EXTREMA` | Z-Score > 3σ |
| `STL_RESIDUAL` | Resíduo alto na decomposição sazonal STL |
| `CHANGEPOINT` | Quebra estrutural detectada na curva de juros da IF |

**Machine Learning**

| Tipo | Método |
|------|--------|
| `ISOLATION_FOREST` | Outlier multivariável (Taxa, Prazo, Risco) |
| `DBSCAN_OUTLIER` | IF isolada dos clusters de mercado |

**Saúde Financeira (requer `collect ifdata`)**

| Tipo | Condição | Severidade |
|------|----------|------------|
| `BASILEIA_BAIXO` | Basileia < 11% e taxa CDI > 120% | HIGH |
| `BASILEIA_BAIXO` | Basileia < 9% e taxa CDI > 120% | CRITICAL |
| `LIQUIDEZ_CRITICA` | Liquidez < 110% e taxa CDI > 115% | HIGH |
| `LIQUIDEZ_CRITICA` | Liquidez < 100% e taxa CDI > 115% | CRITICAL |

---

## alerts

O comando `alerts` é um sub-grupo com dois subcomandos:

### alerts status

```bash
veredas alerts status
```

Exibe uma tabela com os canais de alerta configurados e seus respectivos status:

```
Canal      Status        Detalhes
─────────────────────────────────────────
Telegram   Configurado   Chat: -100123456
Email      Não config.   SMTP não definido
```

### alerts test

```bash
# Testar todos os canais configurados
veredas alerts test

# Testar canal específico
veredas alerts test --channel telegram
veredas alerts test --channel email
```

Envia uma mensagem de teste para confirmar que o canal está funcionando. Útil para validar credenciais após configurar o `.env`.

Para configurar os canais de alerta, veja a seção de configuração em [installation.md](installation.md).

---

## detectors

```bash
veredas detectors
```

Lista todos os detectores de anomalias registrados no motor, com seus parâmetros e status (ativo/inativo).

---

## status

```bash
veredas status
```

Exibe:
- Versão do veredas
- Caminho do banco de dados
- Número de registros por entidade (taxas, anomalias, IFs, HealthData)
- Data da última coleta
- Contagem de anomalias ativas por severidade

---

## Exemplos de uso

### Fluxo completo de monitoramento

```bash
# 1. Inicializar (apenas primeira vez)
veredas init

# 2. Coletar dados macroeconômicos
veredas collect bcb

# 3. Coletar dados de saúde das IFs
veredas collect ifdata

# 4. Executar análise completa
veredas analyze

# 5. Ver status do sistema
veredas status

# 6. Acompanhar pelo dashboard
uvicorn veredas.web.app:app --reload
# Acesse http://localhost:8000
```

### Monitoramento automatizado (cron)

```bash
# Adicionar ao crontab (Linux/macOS)
# Executa coleta e análise a cada hora
0 * * * * cd /path/to/veredas-de-papel && .venv/bin/veredas collect bcb && .venv/bin/veredas analyze

# Coleta de IFData diariamente às 6h (dados publicados com atraso)
0 6 * * * cd /path/to/veredas-de-papel && .venv/bin/veredas collect ifdata && .venv/bin/veredas analyze
```

### Testar configuração de alertas

```bash
# Verificar o que está configurado
veredas alerts status

# Testar Telegram
veredas alerts test --channel telegram

# Testar Email
veredas alerts test --channel email
```

---

## Opções globais

| Opção | Descrição |
|-------|-----------|
| `--help` | Mostra ajuda |
| `--version` | Mostra versão |
| `--db PATH` | Especifica o caminho do banco de dados |

## Códigos de saída

| Código | Significado |
|--------|-------------|
| 0 | Sucesso |
| 1 | Erro geral |
| 2 | Erro de argumentos |
