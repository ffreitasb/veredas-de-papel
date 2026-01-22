# CLAUDE.md - Instruções do Projeto

Este arquivo contém instruções específicas para o Claude ao trabalhar neste projeto.

## Sobre o Projeto

**veredas de papel** é uma ferramenta FOSS para monitoramento de taxas de CDB e detecção de anomalias no mercado de renda fixa brasileiro.

## Arquitetura

```
src/veredas/
├── collectors/     # Coletores de dados externos
│   ├── base.py     # Interface base para coletores
│   ├── bcb.py      # Coletor do Banco Central (Selic, CDI, IPCA)
│   └── scrapers/   # Scrapers de corretoras (futuro)
├── detectors/      # Algoritmos de detecção de anomalias
│   ├── base.py     # Interface base para detectores
│   ├── rules.py    # Detecção baseada em regras
│   └── ml.py       # Detecção com ML (futuro)
├── storage/        # Persistência de dados
│   ├── models.py   # Modelos SQLAlchemy
│   ├── database.py # Gerenciador de banco
│   └── repository.py # Padrão Repository
├── alerts/         # Sistema de notificações (futuro)
├── api/            # API REST FastAPI (futuro)
└── cli/            # Interface de linha de comando
    └── main.py     # Comandos Typer
```

## Convenções de Código

### Python
- Python 3.11+
- Type hints obrigatórios em todas as funções públicas
- Docstrings no formato Google
- Imutabilidade: criar novos objetos, não mutar
- Arquivos pequenos e focados (< 500 linhas)

### Naming
- Classes: PascalCase
- Funções/variáveis: snake_case
- Constantes: UPPER_SNAKE_CASE
- Arquivos: snake_case.py

### Testes
- Cobertura mínima: 80%
- TDD quando possível
- Fixtures em conftest.py
- Mocks para APIs externas

## Padrões do Projeto

### Coletores
Todos os coletores herdam de `BaseCollector` e implementam:
- `source_name`: Nome identificador
- `collect()`: Executa a coleta (async)
- `health_check()`: Verifica disponibilidade

### Detectores
Todos os detectores herdam de `BaseDetector` e implementam:
- `name`: Nome identificador
- `description`: O que o detector faz
- `detect()`: Executa a detecção

### Resultados
- `CollectionResult`: Resultado de coleta
- `DetectionResult`: Resultado de detecção
- `AnomaliaDetectada`: Anomalia encontrada

## Banco de Dados

SQLite por padrão, armazenado em `~/.veredas/veredas.db`.

### Modelos Principais
- `InstituicaoFinanceira`: Bancos e financeiras
- `TaxaCDB`: Taxas coletadas
- `Anomalia`: Anomalias detectadas
- `TaxaReferencia`: Selic, CDI, IPCA
- `EventoRegulatorio`: Histórico de intervenções

## CLI

Usa Typer com Rich para formatação. Comandos principais:
- `veredas init` - Inicializa banco
- `veredas collect` - Coleta dados
- `veredas analyze` - Detecta anomalias
- `veredas alerts` - Gerencia alertas
- `veredas status` - Status do sistema

## Regras de Detecção

### Thresholds Padrão
```python
spread_alto = 130        # CDB > 130% CDI = HIGH
spread_critico = 150     # CDB > 150% CDI = CRITICAL
salto_brusco = 10        # Variação > 10pp = MEDIUM
salto_extremo = 20       # Variação > 20pp = HIGH
divergencia = 2          # > 2σ = MEDIUM
divergencia_extrema = 3  # > 3σ = HIGH
```

## Dependências Principais

- `python-bcb`: API do Banco Central
- `sqlalchemy`: ORM
- `typer`: CLI
- `rich`: Formatação terminal
- `pydantic`: Validação
- `httpx`: HTTP client async

## Documentação

- `PRD.md`: Product Requirements Document
- `DEVELOPMENT_PLAN.md`: Plano detalhado de implementação
- `manifesto_veredas.md`: Explicação do nome

## Ao Desenvolver

1. Sempre verificar se existe teste para a funcionalidade
2. Seguir TDD quando possível
3. Usar agents especializados (tdd-guide, code-reviewer)
4. Commitar com mensagens descritivas (conventional commits)
5. Não committar arquivos sensíveis (.env, credentials)

## Próximos Passos (Fase 1)

1. Completar testes unitários
2. Adicionar coletor IFData
3. Implementar seed de eventos históricos
4. Melhorar CLI com mais funcionalidades
5. Configurar CI/CD (GitHub Actions)
