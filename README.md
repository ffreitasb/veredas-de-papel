# veredas de papel

> *"“O real não está no início nem no fim, ele se mostra pra gente é no meio da travessia”."*
   > ROSA, João Guimarães. Grande sertão: veredas. 19. ed. Rio de Janeiro: Nova Fronteira, 1986.

Monitor de taxas de CDB e detecção de anomalias no mercado de renda fixa brasileiro.

## Sobre o Nome

Inspirado na obra-prima de Guimarães Rosa, *Grande Sertão: Veredas*, o nome reconhece que o mercado financeiro brasileiro é um território hostil, vasto e traiçoeiro. Como dizia o jagunço Riobaldo: *"Viver é muito perigoso"*. Investir também é.

- **Vereda**: No sertão, é um oásis em meio à secura. No contexto deste software, representa o *atalho que instituições financeiras em dificuldade tomam* ao oferecer taxas muito acima do mercado.
- **De Papel**: CDBs são "papéis", mas a expressão carrega o peso da fragilidade. A "vereda de papel" é um caminho sem chão firme.

## O Problema

O caso do Banco Master/Will Bank (2025) demonstrou que taxas extremamente atrativas (ex: 120-185% CDI, IPCA+30%) muitas vezes funcionam como sinais claros de risco que acabam sendo ignorados por investidores seduzidos pela alta rentabilidade. O banco oferecia retornos fora da curva porque estava desesperado por liquidez — um padrão histórico que se repetiu em casos clássicos como BVA (2014) e Cruzeiro do Sul (2012).

## A Solução

**veredas de papel** é uma ferramenta open-source (FOSS) que:

1. **Monitora** o mercado de renda fixa (iniciando com dados macroeconômicos do Banco Central).
2. **Detecta** anomalias e padrões de risco através de um motor robusto que combina Regras Determinísticas, Modelos Estatísticos e Machine Learning.
3. **Visualiza** o cenário de forma limpa e objetiva através de um Dashboard Web nativo.

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

Recomenda-se fortemente o uso de um ambiente virtual para isolar as dependências do projeto.

**Linux/macOS:**
```bash
python -m venv .venv
source .venv/bin/activate
```

**Windows:**
```powershell
python -m venv .venv
.venv\Scripts\activate
```

### 3. Instalando as Dependências

Instale o projeto em modo editável com todas as dependências extras necessárias (Machine Learning e Web Dashboard):

```bash
pip install -e ".[dev,web,ml]"
```

### 4. Configuração de Variáveis de Ambiente

O projeto utiliza um arquivo `.env` para gerenciar configurações (banco de dados, portas, chaves de API para alertas, etc). 

Copie o arquivo de exemplo e edite conforme necessário:

**Linux/macOS/Windows:**
```bash
cp .env.example .env
```
*(Para uso local básico usando SQLite, as configurações padrão contidas no arquivo já são suficientes e podem permanecer comentadas).*

---

## 💻 Como Usar

O ecossistema é dividido em uma CLI (`veredas`) para ingestão/análise de dados e um servidor Web (`uvicorn`) para o dashboard.

### Fluxo Básico de Operação

**1. Inicialize o Banco de Dados:**
Prepara a estrutura local (SQLite salvo em `data/veredas.db`).
```bash
veredas init
```

**2. Colete os Dados de Base:**
Faz a ingestão dos dados macroeconômicos (Selic, CDI, IPCA) da API pública do Banco Central.
```bash
veredas collect bcb
```

**3. Execute o Motor de Análise:**
Avalia os dados armazenados em busca de anomalias usando o motor de regras, Z-Score, STL e Isolation Forest.
```bash
veredas analyze
```

**4. Inicie o Dashboard Web:**
Suba o servidor para visualizar os relatórios e as anomalias detectadas.
```bash
uvicorn veredas.web.app:app --reload
```
Acesse: [http://localhost:8000](http://localhost:8000)

### Comandos Úteis da CLI

| Comando | Descrição |
|---------|-----------|
| `veredas init` | Cria/atualiza o esquema do banco de dados. |
| `veredas collect bcb` | Sincroniza dados históricos com o Banco Central. |
| `veredas analyze` | Executa o pipeline de detecção de anomalias. |
| `veredas detectors` | Lista todos os algoritmos de detecção registrados e seus parâmetros. |
| `veredas status` | Exibe a integridade do banco e a quantidade de registros. |

---

## 🧠 Motor de Detecção (MVP)

Atualmente, o motor de detecção é classificado em três verticais:

1. **Regras Determinísticas**:
   - `SPREAD_ALTO`: Discrepância alta em relação à taxa CDI atual.
   - `SALTO_BRUSCO`: Variações anormais (ex: >10pp) num curto espaço de tempo.
2. **Estatística Avançada**:
   - `DIVERGENCIA` / `Z-SCORE`: Detecta taxas que fogem do desvio padrão do mercado.
   - `STL_RESIDUAL`: Decomposição Sazonal para encontrar anomalias isoladas da tendência macro.
   - `CHANGEPOINT`: Detecção algorítmica de quebra estrutural nas curvas de juros das instituições.
3. **Machine Learning**:
   - `ISOLATION_FOREST`: Detecção de outliers em espaço multivariável (Taxa, Prazo, Risco).
   - `DBSCAN_OUTLIER`: Agrupamento de densidade espacial (identifica instituições "isoladas" dos clusters do mercado).

---

## 🗺️ Roadmap e Visão de Futuro

O projeto está em constante evolução. O plano de desenvolvimento é o seguinte:

- [x] **Fase 1 (MVP)**: Estrutura base, CLI, integração BCB e núcleo de detecção (Regras, Estatística, ML).
- [x] **Fase 2**: Interface gráfica limpa (FastAPI + Jinja2) para análise visual.
- [ ] **Fase 3**: Implementação do coletor do portal **IFData**, cruzando taxas altas com a saúde financeira oficial do banco (Índice de Basileia, Liquidez).
- [ ] **Fase 4 (Scrapers e Mercado Secundário)**: Integração de coletores de prateleiras de corretoras (XP, BTG, Inter) e consumo de dados do Mercado Secundário da **B3**. *(Código draft presente em `future_work/`)*.
- [ ] **Fase 5 (Dados Alternativos)**: Integração com fontes de reputação e risco social (**Reclame Aqui**, **Processos Sancionadores do Bacen**).
- [ ] **Fase 6**: Restauração da **API REST** para uso programático e sistema de notificação em tempo real (**Telegram e SMTP Email**).

## 🛠️ Desenvolvimento

Se você deseja contribuir (e encorajamos que o faça!), o ambiente de desenvolvimento já possui as ferramentas necessárias configuradas.

```bash
# Testes unitários (pytest)
pytest

# Linting e Formatação (ruff)
ruff check src/
ruff format src/

# Checagem Estática de Tipagem (mypy)
mypy src/
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
