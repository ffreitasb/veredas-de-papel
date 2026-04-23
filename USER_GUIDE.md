# Guia do Usuário — veredas de papel

> *"O real não está no início nem no fim, ele se mostra pra gente é no meio da travessia."*
> — Guimarães Rosa

Este guia foi escrito para quem quer usar o **veredas de papel** sem necessariamente ter experiência com programação. Se você consegue abrir um terminal e copiar comandos, você consegue usar esta ferramenta.

---

## Sumário

1. [O que é o veredas de papel?](#1-o-que-é-o-veredas-de-papel)
2. [Antes de começar](#2-antes-de-começar)
3. [Instalação passo a passo](#3-instalação-passo-a-passo)
4. [Configuração inicial](#4-configuração-inicial)
5. [Usando a linha de comando (CLI)](#5-usando-a-linha-de-comando-cli)
   - [veredas init](#51-veredas-init)
   - [veredas collect](#52-veredas-collect)
   - [veredas analyze](#53-veredas-analyze)
   - [veredas web](#54-veredas-web)
   - [veredas status](#55-veredas-status)
   - [veredas detectors](#56-veredas-detectors)
   - [veredas alerts](#57-veredas-alerts)
6. [Usando o Dashboard Web](#6-usando-o-dashboard-web)
   - [Página inicial](#61-página-inicial--painel-de-controle)
   - [Taxas de CDB](#62-taxas-de-cdb)
   - [Anomalias](#63-anomalias)
   - [Instituições Financeiras](#64-instituições-financeiras)
   - [Timeline](#65-timeline)
7. [Configurando Alertas](#7-configurando-alertas)
   - [Telegram](#71-alerta-via-telegram)
   - [Email](#72-alerta-via-email)
8. [Fluxo de uso diário recomendado](#8-fluxo-de-uso-diário-recomendado)
9. [Entendendo as Anomalias](#9-entendendo-as-anomalias)
10. [FAQ — Perguntas Frequentes](#10-faq--perguntas-frequentes)
11. [Solução de Problemas](#11-solução-de-problemas)

---

## 1. O que é o veredas de papel?

O **veredas de papel** é uma ferramenta gratuita e de código aberto que monitora o mercado de renda fixa brasileiro em busca de sinais de risco. Em outras palavras: ele observa as taxas de CDB oferecidas pelas instituições financeiras e avisa quando algo parece fora do padrão.

### Por que isso importa?

Quando um banco está com dificuldades financeiras, ele frequentemente tenta atrair depósitos oferecendo taxas muito acima do mercado — às vezes 130%, 150% ou até 185% do CDI. Isso aconteceu com o Banco Master (2025), com o BVA (2014) e com o Cruzeiro do Sul (2012). Investidores que não perceberam o sinal acabaram assumindo riscos sem saber.

Esta ferramenta não impede que você perca dinheiro, mas te ajuda a enxergar esses sinais com antecedência.

### O que ela faz na prática?

- **Coleta** dados públicos do Banco Central (taxas de referência como Selic, CDI, IPCA) e indicadores de saúde das instituições financeiras
- **Detecta** taxas e padrões suspeitos usando algoritmos de regras, estatística e machine learning
- **Exibe** tudo em um painel web simples e visual
- **Avisa** você por Telegram ou e-mail quando detecta algo crítico

> ⚠️ **Aviso importante**: Esta ferramenta tem finalidade educacional e analítica. Ela **não é** uma recomendação de investimento. Sempre consulte um profissional certificado antes de tomar decisões financeiras.

---

## 2. Antes de começar

### O que você vai precisar

| Requisito | Para que serve | Como verificar |
|-----------|---------------|----------------|
| **Python 3.11 ou superior** | Linguagem em que o programa é escrito | `python --version` no terminal |
| **Git** | Para baixar o código | `git --version` no terminal |
| **Terminal** | Para digitar os comandos | PowerShell (Windows) ou Terminal (Mac/Linux) |
| **Conexão com internet** | Para coletar dados do Banco Central | — |

### Como abrir o terminal

- **Windows**: pressione `Windows + R`, digite `powershell` e pressione Enter
- **macOS**: pressione `Command + Espaço`, digite `Terminal` e pressione Enter
- **Linux**: `Ctrl + Alt + T` na maioria das distribuições

### Verificando o Python

No terminal, digite:
```
python --version
```

Se aparecer `Python 3.11.x` ou superior, está pronto. Se aparecer uma versão mais antiga ou um erro, [baixe o Python](https://www.python.org/downloads/) e instale antes de continuar.

---

## 3. Instalação passo a passo

Existem duas formas de instalar. A **Opção A (uv)** é mais rápida e recomendada para iniciantes. A **Opção B (pip)** é a forma clássica.

### Opção A — Instalação com uv (recomendada)

O `uv` é uma ferramenta moderna que cuida de tudo automaticamente: baixa dependências, cria o ambiente isolado e configura o projeto em um único comando.

**Passo 1: Instalar o uv**

No terminal, cole o comando correspondente ao seu sistema:

```bash
# macOS ou Linux
curl -LsSf https://astral.sh/uv/install.sh | sh

# Windows (PowerShell)
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
```

Feche e reabra o terminal após a instalação.

**Passo 2: Baixar o projeto**

```bash
git clone https://github.com/ffreitasb/veredas-de-papel.git
cd veredas-de-papel
```

**Passo 3: Instalar as dependências**

```bash
uv sync --extra dev --extra web --extra ml --extra alerts
```

Isso pode levar 1 a 3 minutos na primeira vez. O `uv` vai baixar e instalar tudo automaticamente.

**Passo 4: Verificar a instalação**

```bash
uv run veredas --version
```

Deve aparecer algo como `veredas de papel v0.1.0`.

---

### Opção B — Instalação com pip (clássica)

**Passo 1: Baixar o projeto**

```bash
git clone https://github.com/ffreitasb/veredas-de-papel.git
cd veredas-de-papel
```

**Passo 2: Criar o ambiente virtual**

Um ambiente virtual isola as dependências do projeto do restante do seu computador.

```bash
# macOS ou Linux
python -m venv .venv
source .venv/bin/activate

# Windows
python -m venv .venv
.venv\Scripts\activate
```

Quando o ambiente virtual está ativo, você verá `(.venv)` no início da linha do terminal.

**Passo 3: Instalar as dependências**

```bash
pip install -e ".[dev,web,ml,alerts]"
```

**Passo 4: Verificar a instalação**

```bash
veredas --version
```

> **Nota para usuários de uv**: nos exemplos a seguir, substitua `veredas` por `uv run veredas` se preferir não ativar o ambiente virtual manualmente.

---

## 4. Configuração inicial

### Criando o arquivo de configuração

O veredas usa um arquivo `.env` para armazenar configurações. Copie o exemplo:

```bash
cp .env.example .env
```

Abra o arquivo `.env` com qualquer editor de texto (Bloco de Notas, VS Code, etc.). Ele tem este conteúdo:

```env
# Banco de dados (deixe em branco para usar o padrão: data/veredas.db)
VEREDAS_DB_PATH=

# Modo debug (deixe como false em uso normal)
VEREDAS_DEBUG=false

# Thresholds de detecção — valores padrão, altere se quiser
VEREDAS_SPREAD_ALTO=130
VEREDAS_SPREAD_CRITICO=150

# Alertas via Telegram (preencha se quiser receber alertas)
VEREDAS_TELEGRAM_BOT_TOKEN=
VEREDAS_TELEGRAM_CHAT_ID=

# Alertas via Email (preencha se quiser receber alertas)
VEREDAS_SMTP_HOST=smtp.gmail.com
VEREDAS_SMTP_PORT=587
VEREDAS_SMTP_USER=
VEREDAS_SMTP_PASSWORD=
VEREDAS_ALERT_EMAIL_TO=
```

Para uso básico (sem alertas), você pode deixar o arquivo como está. Veja a seção [7. Configurando Alertas](#7-configurando-alertas) para configurar Telegram ou e-mail.

### Inicializando o banco de dados

O banco de dados guarda todas as taxas coletadas e anomalias detectadas. Crie-o com:

```bash
veredas init
```

Mensagem esperada:
```
✓ Banco de dados inicializado em: data/veredas.db
```

Isso só precisa ser feito uma vez. O banco fica salvo em `data/veredas.db` na pasta do projeto.

---

## 5. Usando a linha de comando (CLI)

A linha de comando é como você conversa com o veredas de papel para executar tarefas. Todos os comandos começam com `veredas`.

Para ver todos os comandos disponíveis a qualquer momento:
```bash
veredas --help
```

---

### 5.1 `veredas init`

**O que faz**: Cria o banco de dados (ou atualiza sua estrutura se já existir).

**Quando usar**: Uma vez na primeira instalação. Pode ser executado novamente com segurança — não apaga dados existentes.

```bash
veredas init
```

**Opções disponíveis**:

| Opção | O que faz |
|-------|-----------|
| `--db /caminho/arquivo.db` | Salva o banco num local específico em vez do padrão |
| `--force` | Recria o banco do zero (⚠️ apaga todos os dados!) |

**Exemplo com banco personalizado**:
```bash
veredas init --db /home/usuario/meus-dados/veredas.db
```

---

### 5.2 `veredas collect`

**O que faz**: Busca dados de fontes públicas do Banco Central e salva no banco local.

Existem duas fontes de coleta:

#### `veredas collect bcb`

Coleta as taxas de referência do mercado diretamente da **API pública do Banco Central**:
- **Selic**: taxa básica de juros da economia
- **CDI**: referência para CDBs pós-fixados
- **IPCA**: índice de inflação oficial

Esses valores são usados como base para detectar se um CDB está sendo oferecido com spread excessivo.

```bash
veredas collect bcb
```

**O que aparece na tela**:
```
Coletando dados de: bcb
┌──────────────────────────────────────────┐
│     Taxas de Referência - BCB            │
├───────────┬────────┬─────────────────────┤
│ Indicador │ Valor  │ Data                │
├───────────┼────────┼─────────────────────┤
│ Selic     │ 10.5%  │ 2025-04-01          │
│ CDI       │ 10.4%  │ 2025-04-01          │
│ IPCA      │ 5.1%   │ 2025-03-01          │
└───────────┴────────┴─────────────────────┘
✓ Dados salvos no banco
```

#### `veredas collect ifdata`

Coleta os **indicadores de saúde financeira** das principais instituições financeiras do portal **IFData** do Banco Central. Isso inclui:

- **Índice de Basileia**: mede a solidez de capital do banco (mínimo regulatório: 10,5%)
- **Índice de Liquidez**: mede a capacidade de honrar compromissos de curto prazo
- **ROA / ROE**: indicadores de rentabilidade
- **Inadimplência**: percentual de créditos em atraso
- **Ativos Totais e Patrimônio Líquido**

Esses dados permitem cruzar taxas altas com fragilidade financeira real — o coração da análise de risco.

```bash
veredas collect ifdata
```

> **Frequência recomendada**: os dados do IFData são publicados trimestralmente pelo Banco Central. Executar uma vez por mês é suficiente.

#### `veredas collect all`

Executa ambas as coletas em sequência:

```bash
veredas collect all
```

---

### 5.3 `veredas analyze`

**O que faz**: Analisa todos os dados coletados e detecta anomalias. É o coração do sistema.

```bash
veredas analyze
```

O motor de detecção aplica três camadas de análise:

1. **Regras determinísticas**: verifica se taxas ultrapassam limites absolutos (ex: CDB > 130% CDI)
2. **Modelos estatísticos**: detecta desvios em relação ao comportamento histórico da IF e do mercado
3. **Machine Learning** *(opcional)*: identifica padrões multivariáveis anormais

**Opções disponíveis**:

| Opção | O que faz | Exemplo |
|-------|-----------|---------|
| `--ml` | Ativa detectores de Machine Learning | `veredas analyze --ml` |
| `--severity low/medium/high/critical` | Filtra por severidade mínima | `veredas analyze --severity high` |
| `--if-id N` | Analisa apenas uma IF específica (pelo ID) | `veredas analyze --if-id 5` |
| `--days N` | Considera apenas os últimos N dias | `veredas analyze --days 90` |
| `--db /caminho` | Usa banco de dados específico | — |

**Quando usar Machine Learning?**

Os detectores de ML (Isolation Forest e DBSCAN) precisam de no mínimo 30 amostras por instituição financeira para funcionar bem. Se o banco ainda tem poucos dados, eles retornam vazio automaticamente, sem erro. À medida que você acumula dados com coletas regulares, os resultados ficam mais precisos.

```bash
# Análise completa com ML
veredas analyze --ml

# Apenas anomalias graves ou críticas
veredas analyze --severity high
```

---

### 5.4 `veredas web`

**O que faz**: Inicia o painel visual no seu navegador.

```bash
veredas web
```

Depois de rodar o comando, abra seu navegador e acesse: **http://localhost:8000**

**Opções disponíveis**:

| Opção | Padrão | O que faz |
|-------|--------|-----------|
| `--host` | `127.0.0.1` | Endereço de rede (use `0.0.0.0` para acessar de outros dispositivos na rede) |
| `--port` | `8000` | Porta do servidor |
| `--reload` | desativado | Recarrega automaticamente quando o código muda (para desenvolvedores) |

```bash
# Acesso na rede local (outros dispositivos podem acessar pelo IP da máquina)
veredas web --host 0.0.0.0 --port 8080
```

Para parar o servidor, pressione `Ctrl + C` no terminal.

---

### 5.5 `veredas status`

**O que faz**: Mostra um resumo do estado atual do sistema — quantos dados foram coletados, status da conexão com o Banco Central, e taxas atuais.

```bash
veredas status
```

**Exemplo de saída**:
```
╭────────────────────────────────────────╮
│ veredas de papel v0.1.0                │
│ Monitor de taxas de CDB                │
╰────────────────────────────────────────╯

Status das Fontes:
  ✓ Banco Central (BCB): Online

Taxas Atuais:
  • Selic: 10.5% a.m.
  • CDI: 10.4% a.m.

Banco de Dados: data/veredas.db
  • Tamanho: 142.3 KB
```

Use este comando para verificar rapidamente se tudo está funcionando antes de uma análise.

---

### 5.6 `veredas detectors`

**O que faz**: Lista todos os algoritmos de detecção disponíveis, organizados por categoria, e indica quais dependências estão instaladas.

```bash
veredas detectors
```

**Exemplo de saída**:
```
Detectores de Anomalias Disponíveis

Detectores de Regras:
  • spread_detector
  • variacao_detector

Detectores Estatísticos:
  • zscore_detector                ✓
  • stl_detector                  ✓
  • change_point_detector         ⚠ ruptures não instalado

Detectores de Machine Learning:
  • isolation_forest_detector     ✓
  • dbscan_outlier_detector       ✓

Use --ml com 'veredas analyze' para habilitar detectores ML
```

Se aparecer `⚠ ruptures não instalado`, o detector de change point não está disponível. Para instalar:
```bash
pip install ruptures
# ou
uv add ruptures
```

---

### 5.7 `veredas alerts`

O comando `alerts` tem dois subcomandos para gerenciar os canais de notificação.

#### `veredas alerts status`

Mostra quais canais de alerta estão configurados:

```bash
veredas alerts status
```

```
┌───────────┬──────────────────────┐
│ Canal     │ Estado               │
├───────────┼──────────────────────┤
│ telegram  │ ✓ Configurado        │
│ email     │ ✗ Não configurado    │
└───────────┴──────────────────────┘
```

#### `veredas alerts test`

Envia uma mensagem de teste para confirmar que tudo está funcionando:

```bash
# Testar todos os canais configurados
veredas alerts test

# Testar apenas Telegram
veredas alerts test --channel telegram

# Testar apenas Email
veredas alerts test --channel email
```

Se a mensagem de teste chegar, os alertas automáticos também vão funcionar. Se não chegar, veja a seção [7. Configurando Alertas](#7-configurando-alertas).

---

## 6. Usando o Dashboard Web

O dashboard é a interface visual do veredas de papel. Acesse-o após rodar `veredas web` em **http://localhost:8000**.

---

### 6.1 Página Inicial — Painel de Controle

A página inicial (`/`) exibe um resumo de tudo que está acontecendo:

**Cards de Taxas de Referência**
Mostram os valores atuais de Selic, CDI e IPCA coletados do Banco Central. São a linha de base usada nas análises.

**Contadores de Anomalias**
Exibem quantas anomalias estão ativas por nível de severidade:
- 🔴 **CRITICAL**: requer atenção imediata
- 🟠 **HIGH**: situação preocupante
- 🟡 **MEDIUM**: observar com atenção
- 🟢 **LOW**: dentro dos parâmetros, mas registrado

**Últimas Anomalias Detectadas**
Lista as 5 anomalias mais recentes com tipo, severidade, instituição e data.

**Estatísticas Gerais**
Total de taxas de CDB coletadas e número de instituições monitoradas.

> Os dados do painel são atualizados automaticamente via HTMX — sem precisar recarregar a página manualmente.

---

### 6.2 Taxas de CDB

Acesse pelo menu: **Taxas** (`/taxas/`)

Esta tela lista todas as taxas de CDB coletadas, com filtros avançados.

**Filtros disponíveis**:

| Filtro | O que faz |
|--------|-----------|
| **Indexador** | Filtra por tipo: CDI, IPCA, Prefixado |
| **Prazo mínimo / máximo** | Filtra por prazo em dias |
| **Instituição** | Filtra por banco/financeira específica |
| **Ordenação** | Ordena por data, spread, valor |

**Colunas da tabela**:
- **Data**: quando a taxa foi coletada
- **Instituição**: nome do banco ou financeira
- **Indexador**: tipo de remuneração (CDI%, IPCA+, Prefixado)
- **Percentual**: valor da taxa
- **Prazo**: em dias
- **Liquidez diária**: se permite resgate antes do vencimento
- **Risk Score**: pontuação de risco calculada pelo sistema (quanto maior, mais suspeito)

**Exportar para Excel**

Clique no botão **↓ CSV** para baixar todas as taxas com os filtros ativos em formato compatível com Excel. O arquivo usa ponto-e-vírgula como separador e encoding UTF-8 com BOM — padrão para o Excel brasileiro.

---

### 6.3 Anomalias

Acesse pelo menu: **Anomalias** (`/anomalias/`)

Esta é a tela mais importante da ferramenta. Lista todas as anomalias detectadas com opções de filtro e ação.

**Filtros disponíveis**:

| Filtro | O que faz |
|--------|-----------|
| **Severidade** | LOW / MEDIUM / HIGH / CRITICAL |
| **Tipo** | Tipo de anomalia detectada |
| **Instituição** | Filtrar por banco específico |
| **Status** | "Ativas" (não resolvidas) ou "Todas" |

**O que cada coluna significa**:

| Coluna | Significado |
|--------|-------------|
| **Tipo** | Qual detector identificou o problema (veja tabela na seção 9) |
| **Severidade** | Gravidade da anomalia |
| **Instituição** | Banco ou financeira envolvida |
| **Valor detectado** | Taxa que chamou atenção |
| **Valor esperado** | O que seria normal para o mercado |
| **Desvio** | Diferença entre o detectado e o esperado |
| **Detectado em** | Data e hora da detecção |

**Marcando como Resolvida**

Quando uma anomalia já foi investigada e não é mais relevante, você pode marcá-la como resolvida clicando no botão correspondente. Isso move a anomalia para o histórico sem apagá-la — os dados ficam preservados para auditoria.

**Exportar para Excel**

Clique em **↓ CSV** para exportar todas as anomalias filtradas.

---

### 6.4 Instituições Financeiras

Acesse pelo menu: **Instituições** (`/instituicoes/`)

Lista todas as instituições financeiras monitoradas com seus principais indicadores de saúde.

**Colunas da lista**:
- **Nome**: nome da instituição
- **CNPJ**: identificação fiscal
- **Basileia (%)**: índice de adequação de capital — abaixo de 11% é sinal de alerta
- **Liquidez (%)**: capacidade de honrar compromissos — abaixo de 110% merece atenção
- **Ativo Total**: tamanho da instituição

**Perfil de uma Instituição**

Clique em qualquer instituição para ver seu perfil completo (`/instituicoes/{cnpj}`):

- **Indicadores de saúde**: evolução trimestral de Basileia, Liquidez, ROA, ROE
- **Histórico de taxas**: todas as taxas de CDB coletadas desta instituição
- **Anomalias associadas**: todas as anomalias registradas para esta IF
- **Gráfico de evolução**: visualização da trajetória das taxas ao longo do tempo

---

### 6.5 Timeline

Acesse pelo menu: **Timeline** (`/timeline/`)

Exibe um histórico cronológico combinando:
- **Eventos regulatórios**: intervenções do Banco Central, liquidações, falências e casos históricos (Master, BVA, Cruzeiro do Sul, etc.)
- **Anomalias críticas**: detectadas pelo sistema e classificadas como CRITICAL

**Filtros**:
- **Ano**: filtre por período
- **Tipo**: categoria do evento

A Timeline serve como contexto histórico — ajuda a entender padrões que se repetem e a calibrar a leitura das anomalias atuais.

---

## 7. Configurando Alertas

Os alertas enviam notificações automáticas quando anomalias de alta severidade são detectadas. Você pode configurar Telegram, e-mail, ou ambos.

---

### 7.1 Alerta via Telegram

O Telegram é o canal de alerta mais fácil de configurar e o mais recomendado.

**Passo 1: Criar um Bot no Telegram**

1. Abra o Telegram e pesquise por `@BotFather`
2. Envie o comando `/newbot`
3. Escolha um nome para o bot (ex: "Meu Veredas Bot")
4. Escolha um username para o bot (deve terminar em `bot`, ex: `meu_veredas_bot`)
5. O BotFather vai te enviar um **token** — uma sequência de números e letras como `123456789:ABCdefGhIJklmNoPQRSTuVwXyZ`. **Guarde esse token.**

**Passo 2: Obter seu Chat ID**

1. Abra uma conversa com o bot que você acabou de criar
2. Envie qualquer mensagem (ex: "olá")
3. No navegador, acesse: `https://api.telegram.org/bot{SEU_TOKEN}/getUpdates`
   (substitua `{SEU_TOKEN}` pelo token do passo anterior)
4. Procure por `"chat":{"id": NUMERO}` — o `NUMERO` é seu Chat ID

**Passo 3: Configurar o `.env`**

Abra o arquivo `.env` e preencha:
```env
VEREDAS_TELEGRAM_BOT_TOKEN=123456789:ABCdefGhIJklmNoPQRSTuVwXyZ
VEREDAS_TELEGRAM_CHAT_ID=-100123456789
```

**Passo 4: Testar**

```bash
veredas alerts test --channel telegram
```

Se a mensagem chegar no Telegram, está funcionando.

---

### 7.2 Alerta via Email

**Passo 1: Preparar uma senha de aplicativo (Gmail)**

Se você usa Gmail, é necessário criar uma **Senha de Aplicativo** (não sua senha normal):

1. Acesse [myaccount.google.com](https://myaccount.google.com)
2. Vá em **Segurança** → **Verificação em duas etapas** (ative se não estiver ativa)
3. Volte em **Segurança** → **Senhas de aplicativo**
4. Selecione "Outro (nome personalizado)", escreva "veredas" e clique em Gerar
5. Copie a senha de 16 caracteres gerada

**Passo 2: Configurar o `.env`**

```env
VEREDAS_SMTP_HOST=smtp.gmail.com
VEREDAS_SMTP_PORT=587
VEREDAS_SMTP_USER=seu@gmail.com
VEREDAS_SMTP_PASSWORD=abcd efgh ijkl mnop
VEREDAS_ALERT_EMAIL_TO=destinatario@email.com
```

**Para outros provedores de e-mail**:

| Provedor | SMTP Host | Porta |
|----------|-----------|-------|
| Gmail | smtp.gmail.com | 587 |
| Outlook/Hotmail | smtp-mail.outlook.com | 587 |
| Yahoo | smtp.mail.yahoo.com | 587 |

**Passo 3: Testar**

```bash
veredas alerts test --channel email
```

---

## 8. Fluxo de uso diário recomendado

Para quem quer monitorar o mercado de forma consistente, aqui está um fluxo de trabalho simples:

### Primeira vez (setup único)

```bash
# 1. Clonar e instalar (veja seção 3)
git clone https://github.com/ffreitasb/veredas-de-papel.git
cd veredas-de-papel
uv sync --extra dev --extra web --extra ml --extra alerts

# 2. Configurar (veja seção 4)
cp .env.example .env
# edite o .env com suas configurações

# 3. Inicializar o banco
veredas init

# 4. Primeira coleta
veredas collect bcb
veredas collect ifdata

# 5. Primeira análise
veredas analyze

# 6. Abrir o painel
veredas web
```

### Uso diário (a partir da segunda vez)

```bash
# Atualizar dados do Banco Central
veredas collect bcb

# Rodar análise
veredas analyze

# Abrir o painel (opcional — abra só quando quiser visualizar)
veredas web
```

### Uso semanal / mensal

```bash
# Atualizar dados de saúde das IFs (dados publicados trimestralmente, mas vale coletar mensalmente)
veredas collect ifdata

# Rodar análise completa incluindo ML (requer mais dados acumulados)
veredas analyze --ml
```

### Automatização com Agendador de Tarefas

**Linux / macOS (cron)**

Abra o crontab: `crontab -e`

Adicione as linhas:
```bash
# Coleta BCB todo dia às 7h
0 7 * * * cd /caminho/para/veredas-de-papel && .venv/bin/veredas collect bcb && .venv/bin/veredas analyze

# Coleta IFData todo domingo às 6h
0 6 * * 0 cd /caminho/para/veredas-de-papel && .venv/bin/veredas collect ifdata
```

**Windows (Agendador de Tarefas)**

1. Abra o Agendador de Tarefas (busque por "Task Scheduler")
2. Crie uma nova tarefa básica
3. Configure para executar diariamente
4. No campo "Programa/script", coloque o caminho do `veredas.exe` dentro da pasta `.venv\Scripts\`
5. Nos argumentos, coloque `collect bcb`

---

## 9. Entendendo as Anomalias

Quando o sistema detecta algo suspeito, ele registra uma anomalia com um tipo e uma severidade. Esta seção explica o que cada um significa em linguagem simples.

### Níveis de Severidade

| Cor | Nível | Significado prático |
|-----|-------|---------------------|
| 🔴 | **CRITICAL** | Sinal forte de risco. Investir sem entender o porquê é imprudente. |
| 🟠 | **HIGH** | Situação preocupante que merece investigação. |
| 🟡 | **MEDIUM** | Comportamento fora do padrão, mas pode ter explicação legítima. |
| 🟢 | **LOW** | Desvio leve registrado para histórico. |

### Tipos de Anomalias

#### Regras Determinísticas (simples de entender)

| Tipo | Em português | Significa |
|------|-------------|-----------|
| `SPREAD_ALTO` | Spread alto | CDB oferecido a mais de 130% do CDI — fora da curva do mercado |
| `SPREAD_CRITICO` | Spread crítico | CDB acima de 150% do CDI — nível historicamente associado a bancos em aperto |
| `SALTO_BRUSCO` | Salto brusco | A taxa subiu mais de 10 pontos percentuais em 7 dias — comportamento incomum |
| `SALTO_EXTREMO` | Salto extremo | Subida de mais de 20 pontos percentuais em 7 dias — extremamente anormal |

#### Estatísticas Avançadas

| Tipo | Em português | Significa |
|------|-------------|-----------|
| `DIVERGENCIA` | Divergência | A taxa desta IF está a mais de 2 desvios padrão acima da média do mercado — muito acima dos pares |
| `DIVERGENCIA_EXTREMA` | Divergência extrema | A mais de 3 desvios padrão — um outlier estatístico expressivo |
| `STL_RESIDUAL` | Resíduo STL | Após extrair a tendência e sazonalidade histórica desta IF, resta uma anomalia que não tem explicação pelo padrão habitual |
| `CHANGEPOINT` | Ponto de ruptura | Houve uma mudança estrutural na trajetória de taxas desta IF — algo mudou no comportamento dela |

#### Machine Learning

| Tipo | Em português | Significa |
|------|-------------|-----------|
| `ISOLATION_FOREST` | Isolamento anormal | O conjunto de características desta taxa (valor, prazo, risco) é tão incomum que o algoritmo a "isolou" de todas as outras |
| `DBSCAN_OUTLIER` | Fora dos clusters | Esta IF não se agrupa com nenhum conjunto de instituições similares — ela está sozinha no espaço de comparações |

#### Saúde Financeira

| Tipo | Em português | Significa |
|------|-------------|-----------|
| `BASILEIA_BAIXO` | Basileia baixa | O banco tem pouco capital em relação ao que o regulador exige, **e** está pagando taxas altas para captar dinheiro — combinação de risco |
| `LIQUIDEZ_CRITICA` | Liquidez crítica | O banco pode ter dificuldade para honrar resgates de curto prazo, **e** está oferecendo taxas acima da média — sinal de pressão de caixa |

### Como interpretar uma anomalia

Quando você encontrar uma anomalia no painel, responda estas perguntas:

1. **Qual é a severidade?** CRITICAL e HIGH merecem atenção imediata.
2. **É uma anomalia isolada ou combinada?** Uma IF que aparece em múltiplos tipos ao mesmo tempo (ex: SPREAD_CRITICO + BASILEIA_BAIXO + DBSCAN_OUTLIER) é um sinal muito mais forte do que uma anomalia isolada.
3. **Há histórico?** Consulte o perfil da IF na aba Instituições — a anomalia é nova ou é um padrão recorrente?
4. **Tem contexto público?** Pesquise o nome da instituição em notícias recentes. O Banco Central publica alertas e processos administrativos no [site do BCB](https://www.bcb.gov.br).

> Lembre-se: a ferramenta detecta padrões anômalos, mas **não sabe o motivo**. Uma taxa alta pode ser uma estratégia comercial legítima de crescimento — ou pode ser sinal de aperto de liquidez. A interpretação é sempre sua.

---

## 10. FAQ — Perguntas Frequentes

**P: O veredas de papel tem acesso às taxas de CDB das corretoras (XP, BTG, etc.)?**

Ainda não. Na versão atual (0.1.0-alpha), o sistema coleta dados do Banco Central (taxas macroeconômicas e indicadores das IFs). A integração com prateleiras de corretoras está planejada para uma versão futura.

---

**P: Com que frequência os dados do IFData são atualizados?**

O Banco Central publica os dados do IFData com frequência trimestral. Há um atraso de cerca de 60 a 90 dias em relação à data de referência. Por isso, esses dados refletem a situação passada, não o momento presente.

---

**P: Onde ficam salvos os dados coletados?**

No arquivo `data/veredas.db`, dentro da pasta do projeto. É um banco de dados SQLite — um único arquivo que você pode copiar para fazer backup. Não há servidor externo; tudo fica na sua máquina.

---

**P: Posso usar em mais de um computador?**

Sim. Copie o arquivo `data/veredas.db` para o outro computador. Para manter sincronizado, você precisaria de uma solução externa (ex: Dropbox, Google Drive) ou rodar o servidor web em uma máquina central e acessar pelo navegador de outras máquinas.

---

**P: O sistema funciona sem internet?**

O dashboard web funciona offline com os dados já coletados. Mas para coletar dados novos (`veredas collect`), você precisa de conexão com a internet para acessar as APIs do Banco Central.

---

**P: Preciso deixar o terminal aberto para o dashboard funcionar?**

Sim, enquanto o terminal com `veredas web` estiver aberto, o servidor está rodando. Se você fechar o terminal, o painel deixa de funcionar. Para uso contínuo, é possível rodar o servidor como serviço em background no Linux/macOS, mas isso exige um pouco mais de configuração técnica.

---

**P: Por que o dashboard está em branco quando acesso pela primeira vez?**

Porque o banco de dados está vazio. Execute:
```bash
veredas collect bcb
veredas collect ifdata
veredas analyze
```
Depois recarregue o painel.

---

**P: Posso alterar os limiares de detecção? Por exemplo, avisar só acima de 140% CDI?**

Sim. No arquivo `.env`, altere os valores:
```env
VEREDAS_SPREAD_ALTO=140
VEREDAS_SPREAD_CRITICO=160
```
As mudanças serão aplicadas na próxima análise.

---

**P: O que acontece com anomalias antigas quando executo analyze novamente?**

O sistema deduplica anomalias automaticamente — não cria duplicatas para o mesmo evento na mesma IF. Anomalias já registradas permanecem no banco até você marcá-las como resolvidas.

---

**P: Os dados enviados para o Telegram são seguros?**

O bot do Telegram envia as notificações via HTTPS para os servidores do Telegram. Nenhum dado é enviado para servidores de terceiros além do próprio Telegram. Os dados ficam na sua máquina local.

---

**P: Posso contribuir com o projeto?**

Sim! O projeto é open source sob licença GPL-3.0. Acesse o [repositório no GitHub](https://github.com/ffreitasb/veredas-de-papel), abra uma Issue ou envie um Pull Request.

---

## 11. Solução de Problemas

### "python não é reconhecido como um comando"

**Windows**: O Python não está no PATH. Reinstale-o marcando a opção "Add Python to PATH" durante a instalação.

**macOS/Linux**: Tente `python3 --version` em vez de `python --version`.

---

### "veredas não é reconhecido como um comando"

Você provavelmente não ativou o ambiente virtual. Se está usando pip:
```bash
# macOS/Linux
source .venv/bin/activate

# Windows
.venv\Scripts\activate
```

Se está usando uv, prefixe o comando:
```bash
uv run veredas --help
```

---

### "Banco de dados não encontrado"

Execute `veredas init` antes de qualquer outro comando. Se estiver usando um caminho personalizado via `VEREDAS_DB_PATH`, certifique-se de que o diretório pai existe:
```bash
mkdir -p /caminho/para/o/diretório
veredas init
```

---

### "Erro ao conectar com o Banco Central"

A API pública do Banco Central pode estar temporariamente indisponível. Verifique:

```bash
veredas status
```

Se mostrar "Offline", aguarde alguns minutos e tente novamente. O BCB realiza manutenções programadas, geralmente nos finais de semana.

---

### "O dashboard abre mas está em branco"

Banco de dados vazio. Execute o fluxo de coleta e análise:
```bash
veredas collect bcb
veredas collect ifdata
veredas analyze
veredas web
```

---

### "O detector change_point está marcado como indisponível"

O detector CHANGEPOINT precisa da biblioteca `ruptures`. Instale:
```bash
pip install ruptures
# ou, com uv:
uv add ruptures
```

---

### "Os detectores de ML não encontram nada"

Normal em bancos com poucos dados. Os detectores de Machine Learning (Isolation Forest e DBSCAN) precisam de no mínimo 30 amostras por instituição financeira. Continue coletando dados regularmente e os resultados vão aparecer.

---

### "O alerta de Telegram não está chegando"

Verifique passo a passo:

1. Confirme que o bot token está correto no `.env`
2. Confirme que você enviou pelo menos uma mensagem para o bot antes de tentar
3. Confirme que o Chat ID está correto (é um número negativo para grupos, positivo para DMs)
4. Teste novamente: `veredas alerts test --channel telegram`
5. Veja se aparece algum erro na saída do comando

---

### "Erro: unhashable type" ou erros estranhos ao iniciar o web"

Certifique-se de estar usando a versão mais recente do repositório:
```bash
git pull origin master
uv sync --extra dev --extra web --extra ml --extra alerts
```

---

### "O pip install está demorando muito ou travando"

Tente atualizar o pip primeiro:
```bash
python -m pip install --upgrade pip
pip install -e ".[dev,web,ml,alerts]"
```

Ou use o `uv` que é significativamente mais rápido.

---

### Como obter ajuda

Se o problema persistir:

1. Execute `veredas --version` e anote a versão
2. Copie a mensagem de erro completa
3. Abra uma [Issue no GitHub](https://github.com/ffreitasb/veredas-de-papel/issues) com essas informações

---

*Desenvolvido com ☕, Python e preocupação legítima com o investidor brasileiro.*

> ⚠️ **Disclaimer**: Este software tem caráter puramente educacional e analítico. Não constitui recomendação de investimento, compra, venda ou retenção de ativos financeiros. Os dados processados podem conter atrasos ou incorreções inerentes às fontes públicas. Sempre consulte um profissional certificado antes de investir.
