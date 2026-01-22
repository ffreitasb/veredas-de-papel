Plano de Implementação - veredas de papel
Progresso Atual

Fase 1 ████████████░░░░ ~75% completa
Fase 2 ░░░░░░░░░░░░░░░░ Não iniciada
Fase 3 ░░░░░░░░░░░░░░░░ Não iniciada
Fase 4 ░░░░░░░░░░░░░░░░ Não iniciada
Fase 5 ░░░░░░░░░░░░░░░░ Opcional/Futuro
Fase 1: MVP (Core) — 75% ✅
Componente	Status	Itens Pendentes
Infraestrutura	✅	config.py, pre-commit hooks
Modelos/Storage	✅	Alembic migrations, seeds
Coletores BCB	✅	IFData, scheduler
Detectores	✅	—
CLI	✅	—
Testes	✅ 81%	test_bcb.py
Docs	🔶	installation.md, LICENSE
Itens faltantes na Fase 1:

1.1.3 Configurações da aplicação (config.py)
1.2.4 Migrations com Alembic
1.2.5 Seed de eventos históricos
1.3.5 Coletor IFData
1.6.4 Testes do coletor BCB
1.7.2-4 Documentação (guias, LICENSE)
Fase 2: Frontend e Dashboard
Stack escolhida: FastAPI + Jinja2 + HTMX + Pico CSS

Componente	Arquivos
Web Server	src/veredas/web/app.py
Rotas	routes/home.py, taxas.py, anomalias.py, etc.
Templates	templates/*.html + partials/ (HTMX)
Alertas	alerts/email.py, telegram.py
Indicadores	analysis/health.py, risk_score.py
Páginas planejadas:

Home (visão geral + taxas atuais)
Taxas (tabela filtável)
Anomalias (lista com ações)
Instituições (lista + detalhe)
Timeline (eventos históricos)
Fase 3: Detecção Avançada
Z-Score com janela móvel
Decomposição STL
Isolation Forest / DBSCAN
API REST (FastAPI + OpenAPI)
Fase 4: Expansão de Fontes
Scrapers de corretoras (XP, BTG, Rico, Nubank, Inter)
Mercado secundário (B3)
Dados alternativos (Reclame Aqui, processos BC)
Fase 5: Sustentabilidade (Opcional)
Sistema de subscrição (Stripe)
Relatórios premium por email
API comercial com tiers