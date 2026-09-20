# Como contribuir

Obrigado pelo interesse no Zanella Orchestrator.

## Antes de começar

- confira se já existe uma issue sobre o assunto;
- descreva o comportamento atual e o comportamento esperado;
- nunca publique senhas, tokens, caminhos pessoais, bancos ou logs com dados sensíveis.

## Ambiente local

Requisitos: Windows 10/11, Python 3.12 ou superior e `uv`.

```powershell
uv sync --extra ui
uv run pytest -q
```

## Pull requests

1. Faça uma alteração focada por pull request.
2. Inclua testes quando mudar regras de negócio ou persistência.
3. Atualize a documentação quando mudar comportamento visível.
4. Confirme que a suíte de testes passa.
5. Explique problema, solução e validação na descrição.

Ao contribuir, você concorda que sua contribuição será licenciada sob a Apache License 2.0.
