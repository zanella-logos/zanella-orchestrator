# Aprovação de textos visíveis ao usuário

- Antes de adicionar ou alterar textos da interface do Zanella Orchestrator, READMEs, documentação pública ou notas de release, mostrar neste chat o texto exato proposto e aguardar aprovação explícita de Victor.
- A aprovação deve ocorrer antes de aplicar o texto aos arquivos ou incluí-lo em uma build, não apenas antes de publicar no GitHub.
- Autorização geral para implementar uma funcionalidade não autoriza decidir os textos visíveis sem essa revisão.
- Uma alteração textual exata já solicitada ou aprovada por Victor pode ser aplicada sem pedir novamente a mesma aprovação.
- Avisar explicitamente, antes da implementação, quando uma solicitação puder prejudicar a execução do Zanella ou dos robôs.

## Pendência autorizada para RC7

- Renomear a tarefa do Agendador do Windows de `RPA Control Center Scheduler` para `Zanella Orchestrator`.
- Ao atualizar instalações existentes, migrar a tarefa antiga preservando configuração e evitando dois gatilhos ativos. Não implementar essa mudança na RC6.
