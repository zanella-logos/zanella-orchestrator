---
tipo: decisao
status: ativo
projeto: Zanella Orchestrator
tecnologias: [Python, Windows, SQLite, PostgreSQL, SQLAlchemy, Alembic, pywin32]
criado_em: 2026-09-16
atualizado_em: 2026-09-17
---

# Fundação local e persistência do Control Center

## Identificação

- Data: 2026-09-16
- Projeto: Zanella Orchestrator
- Status: Aceita e validada em SQLite e PostgreSQL 18.

## Contexto

Executar robôs Python sequencialmente em uma máquina Windows, inclusive quando disparados pelo Agendador, com evolução da interface independente do motor e suporte aos mesmos comportamentos em SQLite e PostgreSQL.

## Opções consideradas

### Opção 1
- Descrição: SQLite local e PostgreSQL opcional via SQLAlchemy e Alembic.
- Vantagens: instalação local simples, modelo relacional comum e migrations versionadas.
- Desvantagens: exige testar dois bancos e seus comportamentos transacionais.

### Opção 2
- Descrição: PostgreSQL obrigatório.
- Vantagens: único banco para validar.
- Desvantagens: instalação e operação de servidor também para uso individual.

### Opção 3
- Descrição: arquivos JSON como persistência principal.
- Vantagens: ausência de banco.
- Desvantagens: implementação própria de concorrência e consulta de histórico.

## Decisão tomada

SQLite padrão e PostgreSQL opcional. Mutex Windows por instalação protege a execução sequencial entre processos; uma operação UPDATE condicional reserva o item em transação curta. Job Objects controlam a árvore de processos. O processo nasce suspenso e somente inicia após associação ao job.

## Motivos

Evitar bloqueios de banco durante execução e separar exclusividade do motor de tomada de itens. Preservar instalação local simples, histórico relacional e encerramento delimitado aos processos pertencentes à execução.

## Consequências

### Positivas

- Separação de interface, persistência e mecanismos Windows.
- Dependências fixadas e testes com processos reais.

### Negativas / trade-offs

- Executor específico de Windows nesta etapa.
- O Agendador foi validado com a conta operacional conectada; execução por outras contas ainda exige teste específico.
- A conta Windows e o identificador da instalação influenciam acesso ao mutex.
- Migrations não transferem dados automaticamente entre bancos.

## Impacto técnico

Modelos Robot e Run, migration inicial, reserva transacional, mutex e Job Objects. A suíte comum passou em SQLite e PostgreSQL 18 em 2026-09-17. Interface, CLI, recuperação e executor completo ainda não implementados.

## Como revisar esta decisão

Reavaliar ao introduzir múltiplas máquinas, múltiplas contas Windows ou exigências incompatíveis com execução local sequencial. Um banco servidor não habilita automaticamente workers distribuídos.

## Relacionados

- Projeto:
- Tecnologia:
- Incidente:
- Padrão:
- Decisão:

## Referências

- Documentação: https://docs.sqlalchemy.org/en/20/dialects/sqlite.html
- Documentação: https://learn.microsoft.com/en-us/windows/win32/procthread/job-objects
- Documentação: https://alembic.sqlalchemy.org/en/latest/tutorial.html
- Issues:
- Commits:
- Outros:
