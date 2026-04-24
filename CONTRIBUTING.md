<div align="center">
  <img src="assets/veredas_icon.png" alt="veredas de papel" width="72">
</div>

# Contribuindo para o Veredas de Papel

> *"Mestre não é quem sempre ensina, mas quem de repente aprende."*
> — João Guimarães Rosa, Grande Sertão: Veredas

Agradecemos o seu interesse em contribuir! O processo de colaboração é simples, e encorajamos PRs de todos os níveis.

## Como contribuir

1. Faça o fork do repositório
2. Crie uma branch para a sua feature (`git checkout -b feature/minha-feature`)
3. Faça commit das mudanças (`git commit -m 'feat: minha nova feature'`)
4. Faça push para a branch (`git push origin feature/minha-feature`)
5. Abra um Pull Request

## Padrões de Código

Utilizamos as seguintes ferramentas para garantir a qualidade do código. Certifique-se de executá-las antes de abrir o PR:

- **Ruff**: Para linting e formatação `ruff check src/`
- **Mypy**: Para checagem de tipos estáticos `mypy src/`
- **Pytest**: Para executar os testes `pytest`

## Padrões de Commit

Pedimos que você utilize [Conventional Commits](https://www.conventionalcommits.org/):
- `feat:` para novas funcionalidades
- `fix:` para correção de bugs
- `docs:` para alterações de documentação
- `refactor:` para refatoração de código
- `test:` para adição ou correção de testes
- `chore:` para manutenção.

## Relatório de Bugs

Para relatar um problema ou sugerir uma funcionalidade abra uma Issue descrevendo o problema ou sugestão com o máximo de detalhes possível, de preferência com passos para reprodução, versão do SO, etc.
