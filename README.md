<div align="center">
  <img src="assets/veredas_hero.png" alt="Mandacaru de papel com taxas de CDB no sertão — veredas de papel" width="720">
  <br><br>
  <i>"O real não está no início nem no fim, ele se mostra pra gente é no meio da travessia."</i>
  <br>
  <sub>ROSA, João Guimarães. <i>Grande sertão: veredas</i>. 19. ed. Rio de Janeiro: Nova Fronteira, 1986.</sub>
  <br><br>
  <img src="assets/veredas_icon.png" alt="veredas de papel icon" width="72">
</div>

<br>

# veredas de papel

<div align="center">

[![CI](https://github.com/ffreitasb/veredas-de-papel/actions/workflows/ci.yml/badge.svg)](https://github.com/ffreitasb/veredas-de-papel/actions/workflows/ci.yml)
[![Python](https://img.shields.io/badge/python-3.11%2B-3776ab?logo=python&logoColor=white)](https://python.org)
[![Licença: GPL v3](https://img.shields.io/badge/licen%C3%A7a-GPL--3.0-blue.svg)](https://www.gnu.org/licenses/gpl-3.0)
[![Versão](https://img.shields.io/badge/vers%C3%A3o-0.1.0--alpha-orange)](https://github.com/ffreitasb/veredas-de-papel/releases)
[![Ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json)](https://github.com/astral-sh/ruff)
[![Feito no Brasil](https://img.shields.io/badge/feito%20no-Brasil%20%F0%9F%87%A7%F0%9F%87%B7-009c3b)](https://github.com/ffreitasb/veredas-de-papel)

[![BCB Open Data](https://img.shields.io/badge/dados-BCB%20Open%20Data-009c3b)](https://dadosabertos.bcb.gov.br)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.109%2B-009688?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
[![HTMX](https://img.shields.io/badge/HTMX-1.9-3366cc)](https://htmx.org)
[![pandas](https://img.shields.io/badge/pandas-2.2%2B-150458?logo=pandas&logoColor=white)](https://pandas.pydata.org)
[![Não é recomendação de investimento](https://img.shields.io/badge/aviso-n%C3%A3o%20%C3%A9%20recomenda%C3%A7%C3%A3o%20de%20investimento-red)](https://github.com/ffreitasb/veredas-de-papel#%EF%B8%8F-disclaimer)

</div>

Monitor de taxas de CDB e detecção de anomalias no mercado de renda fixa brasileiro.

## Sobre o Nome

Inspirado na obra-prima de Guimarães Rosa, *Grande Sertão: Veredas*, o nome reconhece que o mercado financeiro brasileiro é um território hostil, vasto e traiçoeiro. Como dizia o jagunço Riobaldo: *"Viver é muito perigoso"*. Investir também é.

- **Vereda**: No sertão, é um oásis em meio à secura. No contexto deste software, representa o *atalho que instituições financeiras em dificuldade tomam* ao oferecer taxas muito acima do mercado.
- **De Papel**: CDBs são "papéis", mas a expressão carrega o peso da fragilidade. A "vereda de papel" é um caminho sem chão firme.

## O Problema

O caso do Banco Master/Will Bank (2025) demonstrou que taxas extremamente atrativas (ex: 120-185% CDI, IPCA+30%) muitas vezes funcionam como sinais claros de risco que acabam sendo ignorados por investidores seduzidos pela alta rentabilidade. O banco oferecia retornos fora da curva porque estava desesperado por liquidez — um padrão histórico que se repetiu em casos clássicos como BVA (2014) e Cruzeiro do Sul (2012).

## A Solução

**veredas de papel** é uma ferramenta open-source (FOSS) que:

1. **Monitora** o mercado de renda fixa com dados macroeconômicos do Banco Central e indicadores prudenciais oficiais das IFs (IFData/Banco Central).
2. **Detecta** anomalias e padrões de risco através de um motor robusto que combina Regras Determinísticas, Modelos Estatísticos e Machine Learning.
3. **Visualiza** o cenário de forma limpa e objetiva através de um Dashboard Web com filtros, ordenação e exportação CSV.
4. **Alerta** via Telegram e Email quando anomalias críticas são detectadas.

---

## 🚀 Instalação e Configuração

### Pré-requisitos
- **Python 3.11 ou superior**
- Git

### 1. Clonando o Repositório

```bash
git clone https://github.com/ffreitasb/veredas-de-papel.git
cd veredas-de-papel
```

### 2. Ambiente Virtual

```bash
# Linux/macOS
python -m venv .venv
source .venv/bin/activate

# Windows
python -m venv .venv
.venv\Scripts\activate
```

### 3. Instalando as Dependências

```bash
# Instalação completa (recomendada)
pip install -e ".[dev,web,ml,alerts]"
```

### 4. Configuração de Variáveis de Ambiente

Copie o arquivo de exemplo e edite conforme necessário:

```bash
cp .env.example .env
```

Para uso local básico (SQLite), as configurações padrão já são suficientes.

Para habilitar alertas, adicione ao `.env`:

```env
# Telegram
VEREDAS_TELEGRAM_BOT_TOKEN=seu_token_aqui
VEREDAS_TELEGRAM_CHAT_ID=seu_chat_id_aqui

# Email (SMTP)
VEREDAS_SMTP_HOST=smtp.gmail.com
VEREDAS_SMTP_PORT=587
VEREDAS_SMTP_USER=seu@email.com
VEREDAS_SMTP_PASSWORD=sua_senha_app
VEREDAS_ALERT_EMAIL_TO=destinatario@email.com
```

### 5. Inicializando o Banco de Dados

```bash
# Cria o esquema via Alembic (migrações versionadas)
veredas init
```

---

## 💻 Como Usar

### Fluxo Básico de Operação

**1. Colete os Dados Macroeconômicos:**
```bash
veredas collect bcb
```
Sincroniza Selic, CDI e IPCA da API pública do Banco Central.

**2. Colete Dados de Saúde das IFs:**
```bash
veredas collect ifdata
```
Importa indicadores prudenciais (Índice de Basileia, Liquidez, ROA/ROE) do portal IFData do Banco Central. Permite cruzar taxas altas com fragilidade financeira real.

**3. Execute o Motor de Análise:**
```bash
veredas analyze
```
Avalia os dados em busca de anomalias usando regras determinísticas, Z-Score, STL, Isolation Forest e detectores de saúde financeira.

**4. Inicie o Dashboard Web:**
```bash
uvicorn veredas.web.app:app --reload
```
Acesse: [http://localhost:8000](http://localhost:8000)

### Comandos da CLI

| Comando | Descrição |
|---------|-----------|
| `veredas init` | Cria/atualiza o esquema do banco de dados via Alembic. |
| `veredas collect bcb` | Sincroniza dados históricos com o Banco Central. |
| `veredas collect ifdata` | Importa indicadores prudenciais das IFs do portal IFData. |
| `veredas analyze` | Executa o pipeline completo de detecção de anomalias. |
| `veredas detectors` | Lista todos os algoritmos de detecção registrados. |
| `veredas status` | Exibe integridade do banco e quantidade de registros. |
| `veredas alerts status` | Mostra os canais de alerta configurados (Telegram, Email). |
| `veredas alerts test` | Envia mensagem de teste pelos canais configurados. |

---

## 🌐 Dashboard Web

O dashboard oferece visualização interativa de todas as informações coletadas, com atualizações parciais via HTMX (sem recarregar a página inteira).

### Telas disponíveis

| Rota | Conteúdo |
|------|----------|
| `/` | Resumo geral: totais, anomalias críticas, alertas recentes |
| `/taxas/` | Tabela de taxas de CDB com filtros e ordenação por coluna |
| `/anomalias/` | Lista de anomalias com filtros por severidade, tipo e IF |
| `/instituicoes/` | Lista de instituições financeiras monitoradas |
| `/instituicoes/{cnpj}` | Perfil completo da IF com histórico de saúde financeira trimestral |

### Exportação CSV

Todas as listagens possuem botão **↓ CSV** que gera arquivos compatíveis com Excel brasileiro (UTF-8-BOM, delimitador `;`):

- `/taxas/export.csv` — até 10.000 registros com os filtros ativos
- `/anomalias/export.csv` — até 10.000 anomalias com os filtros ativos

---

## 🧠 Motor de Detecção

O motor combina três verticais de análise:

### Regras Determinísticas
| Tipo | Condição | Severidade |
|------|----------|------------|
| `SPREAD_ALTO` | CDB > 130% CDI | HIGH |
| `SPREAD_CRITICO` | CDB > 150% CDI | CRITICAL |
| `SALTO_BRUSCO` | Variação > 10pp em 7 dias | MEDIUM |
| `SALTO_EXTREMO` | Variação > 20pp em 7 dias | HIGH |

### Estatística Avançada
| Tipo | Método |
|------|--------|
| `DIVERGENCIA` / `DIVERGENCIA_EXTREMA` | Z-Score (2σ / 3σ acima da média) |
| `STL_RESIDUAL` | Decomposição sazonal STL — anomalia isolada da tendência macro |
| `CHANGEPOINT` | Detecção de quebra estrutural na curva de juros da IF |

### Machine Learning
| Tipo | Método |
|------|--------|
| `ISOLATION_FOREST` | Detecção de outliers multivariável (Taxa, Prazo, Risco) |
| `DBSCAN_OUTLIER` | Agrupamento de densidade — IFs "isoladas" dos clusters do mercado |

### Saúde Financeira (IFData)
| Tipo | Condição | Severidade |
|------|----------|------------|
| `BASILEIA_BAIXO` | Basileia < 11% **e** taxa CDI > 120% | HIGH |
| `BASILEIA_BAIXO` | Basileia < 9% **e** taxa CDI > 120% | CRITICAL |
| `LIQUIDEZ_CRITICA` | Liquidez < 110% **e** taxa CDI > 115% | HIGH |
| `LIQUIDEZ_CRITICA` | Liquidez < 100% **e** taxa CDI > 115% | CRITICAL |

---

## 🗺️ Roadmap

- [x] **Fase 1 (MVP)**: Estrutura base, CLI, integração BCB, núcleo de detecção (Regras, Estatística, ML).
- [x] **Fase 2**: Dashboard web (FastAPI + Jinja2 + HTMX) para análise visual.
- [x] **Fase 3**: Coletor IFData — cruzamento de taxas altas com saúde financeira oficial (Basileia, Liquidez, ROA/ROE).
- [x] **Fase B (atual)**: Suite de testes, migrações Alembic, sistema de alertas (Telegram/Email), detectores de saúde, CSV export, filtros e ordenação no dashboard.
- [ ] **Fase 4 (Scrapers)**: Integração de prateleiras de corretoras (XP, BTG, Inter) e Mercado Secundário B3.
- [ ] **Fase 5 (Dados Alternativos)**: Reclame Aqui, Processos Sancionadores Bacen.
- [ ] **Fase C**: GitHub Actions CI/CD, empacotamento PyInstaller, deploy demo.

---

## 🛠️ Desenvolvimento

```bash
# Testes (pytest)
pytest

# Linting e Formatação (ruff)
ruff check src/
ruff format src/

# Checagem de Tipagem (mypy)
mypy src/

# Migrações de banco de dados (Alembic)
python -m alembic upgrade head          # Aplicar migrações
python -m alembic revision --autogenerate -m "descricao"  # Nova migração
python -m alembic history               # Histórico de versões
```

## 🤝 Contribuindo

Sinta-se à vontade para abrir *Issues* relatando bugs ou sugerindo features. Se quiser colocar a mão na massa, faça um Fork do projeto, crie uma branch e envie seu *Pull Request*.

Nosso objetivo primário é fornecer inteligência de dados transparente para o investidor brasileiro.

## 📄 Licença

Distribuído sob a licença **GPL-3.0-or-later**. Veja o arquivo `pyproject.toml` para mais informações.

## ⚠️ Disclaimer

**Este software tem caráter puramente educacional e analítico.**
Não constitui, de forma alguma, recomendação de investimento, compra, venda ou retenção de ativos financeiros. Os dados processados podem conter atrasos, distorções ou incorreções inerentes às fontes públicas. Sempre consulte um profissional certificado e faça sua própria diligência antes de investir.

---

*Desenvolvido com ☕, Python e preocupação legítima com o investidor brasileiro.*
