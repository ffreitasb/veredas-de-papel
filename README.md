# veredas de papel

> *"Nem todo atalho leva ao destino. Monitore o risco."*

Monitor de taxas de CDB e detecção de anomalias no mercado de renda fixa brasileiro.

## Sobre o Nome

Inspirado na obra-prima de Guimarães Rosa, *Grande Sertão: Veredas*, o nome reconhece que o mercado financeiro brasileiro é um território hostil, vasto e traiçoeiro. Como dizia o jagunço Riobaldo: *"Viver é muito perigoso"*. Investir também é.

- **Vereda**: No sertão, é um oásis em meio à secura. No contexto deste software, representa o *atalho que instituições financeiras em dificuldade tomam* ao oferecer taxas muito acima do mercado.

- **De Papel**: CDBs são "papéis", mas a expressão carrega o peso da fragilidade. A "vereda de papel" é um caminho sem chão firme.

## O Problema

O caso do Banco Master (2025) demonstrou que taxas extremamente atrativas (120-185% CDI, IPCA+30%) eram sinais claros de risco que muitos investidores ignoraram. O banco oferecia retornos absurdos porque estava desesperado por liquidez — um padrão que se repetiu com BVA (2014), Cruzeiro do Sul (2012) e outros.

## A Solução

**veredas de papel** é uma ferramenta FOSS que:

1. **Monitora** taxas de CDB de múltiplas instituições financeiras
2. **Detecta** anomalias e padrões de risco (spreads anormais, saltos bruscos)
3. **Alerta** investidores sobre comportamentos suspeitos
4. **Correlaciona** com indicadores de saúde financeira das instituições

## Instalação

```bash
# Clone o repositório
git clone https://github.com/ffreitasb/veredas-de-papel.git
cd veredas-de-papel

# Crie um ambiente virtual
python -m venv .venv
source .venv/bin/activate  # Linux/Mac
# ou
.venv\Scripts\activate     # Windows

# Instale as dependências
pip install -e ".[dev]"
```

## Uso Rápido

```bash
# Inicializa o banco de dados
veredas init

# Coleta taxas do Banco Central
veredas collect bcb

# Verifica status do sistema
veredas status

# Executa análise de anomalias
veredas analyze

# Lista alertas ativos
veredas alerts --list
```

## Comandos

| Comando | Descrição |
|---------|-----------|
| `veredas init` | Inicializa o banco de dados |
| `veredas collect <fonte>` | Coleta dados (bcb, ifdata, all) |
| `veredas analyze` | Executa detecção de anomalias |
| `veredas alerts --list` | Lista alertas ativos |
| `veredas export --format csv` | Exporta dados |
| `veredas status` | Mostra status do sistema |

## Regras de Detecção

| Tipo | Condição | Severidade |
|------|----------|------------|
| SPREAD_ALTO | CDB > 130% CDI | HIGH |
| SPREAD_CRITICO | CDB > 150% CDI | CRITICAL |
| SALTO_BRUSCO | Variação > 10pp em 7 dias | MEDIUM |
| SALTO_EXTREMO | Variação > 20pp em 7 dias | HIGH |
| DIVERGENCIA | Taxa > média + 2σ | MEDIUM |
| DIVERGENCIA_EXTREMA | Taxa > média + 3σ | HIGH |

## Fontes de Dados

- **Banco Central do Brasil** (BCB): Taxa Selic, CDI, IPCA via API pública
- **IFData**: Indicadores de saúde das instituições financeiras (Basileia, liquidez)
- **Corretoras**: Taxas de CDB oferecidas (XP, BTG, Rico, etc.) - em desenvolvimento

## Estrutura do Projeto

```
veredas-de-papel/
├── src/veredas/
│   ├── collectors/     # Coletores de dados
│   ├── detectors/      # Algoritmos de detecção
│   ├── storage/        # Modelos e banco de dados
│   ├── alerts/         # Sistema de alertas
│   ├── api/            # API REST (futuro)
│   └── cli/            # Interface de linha de comando
├── tests/              # Testes automatizados
├── docs/               # Documentação
├── PRD.md              # Product Requirements Document
└── DEVELOPMENT_PLAN.md # Plano de desenvolvimento
```

## Desenvolvimento

```bash
# Instala dependências de desenvolvimento
pip install -e ".[dev]"

# Executa testes
pytest

# Executa linter
ruff check src/

# Executa type checker
mypy src/
```

## Roadmap

- [x] **Fase 1**: MVP com coleta do BC e regras básicas
- [ ] **Fase 2**: Dashboard web (Streamlit) e alertas (email/Telegram)
- [ ] **Fase 3**: Detecção avançada com ML (Isolation Forest, DBSCAN)
- [ ] **Fase 4**: Scraping de corretoras e mercado secundário
- [ ] **Fase 5**: Sustentabilidade (relatórios premium, API)

## Contribuindo

Contribuições são bem-vindas! Por favor, leia o [CONTRIBUTING.md](CONTRIBUTING.md) antes de enviar um PR.

## Licença

MIT License - veja [LICENSE](LICENSE) para detalhes.

## Disclaimer

Esta ferramenta não constitui recomendação de investimento. Os dados podem ter atrasos ou imprecisões. Faça sempre sua própria análise.

---

*Desenvolvido com ☕ e preocupação com o investidor brasileiro.*
