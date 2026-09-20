---
tipo: decisao
status: ativo
projeto: Zanella Orchestrator
tecnologias: [Python, PowerShell, Batch, Node.js, Java, Windows]
criado_em: 2026-09-17
atualizado_em: 2026-09-17
---

# Executor genérico de processos locais

## Identificação

- Data: 2026-09-17
- Projeto: Zanella Orchestrator
- Status: Aceita e validada em SQLite e PostgreSQL 18.

## Contexto

O motor nasceu com comando fixo para Python. O produto precisa orquestrar processos locais de outras tecnologias sem duplicar fila, logs, cancelamento, timeout, Job Objects ou contrato de resultado.

## Opções consideradas

### Opção 1
- Descrição: manter o núcleo exclusivo para Python.
- Vantagens: menor superfície inicial.
- Desvantagens: limita automações executáveis pelo mesmo mecanismo do Windows.

### Opção 2
- Descrição: executor genérico com adaptadores pequenos por tipo.
- Vantagens: preserva o motor e mantém comandos como listas de argumentos.
- Desvantagens: cada runtime exige validação própria e instalação externa.

### Opção 3
- Descrição: executar uma linha de comando livre por shell.
- Vantagens: flexibilidade máxima.
- Desvantagens: quoting frágil, maior risco de injeção e comportamento difícil de validar.

## Decisão tomada

Usar adaptadores explícitos para `python`, `powershell`, `batch`, `node`, `java` e `executable`. O motor continua recebendo uma lista de argumentos, inicia o processo diretamente e mantém o mesmo Job Object e contrato JSON. Python permanece o tipo padrão para preservar cadastros existentes.

## Motivos

Ampliar o uso do produto sem introduzir shell genérico, serviços externos ou novas filas. Separar a montagem do comando da supervisão permite adicionar tipos futuros sem reescrever o motor.

## Consequências

### Positivas

- Um único histórico e protocolo para tecnologias diferentes.
- Runtimes externos continuam opcionais.
- Núcleo gratuito pode oferecer execução ampla e servir como base para módulos profissionais.

### Negativas / trade-offs

- Compatibilidade depende do runtime instalado na máquina.
- Scripts gráficos ainda dependem de sessão Windows interativa.
- PowerShell 5.1 exige atenção a execution policy e codificação de arquivos.

## Impacto técnico

Novo campo `executor_type`, adaptadores de comando e migration `0003`. Doze testes passaram em SQLite e PostgreSQL 18. A execução foi validada com Python/Flet, um executável iniciado diretamente, Windows PowerShell 5.1, Node.js 22.16.0 e OpenJDK 25.0.3 LTS.

## Como revisar esta decisão

Reavaliar ao incluir shell livre, execução remota, containers ou runtimes com contratos incompatíveis com processos locais Windows.

## Relacionados

- Projeto: [Zanella Orchestrator](../PROJETOS/RPA-Control-Center/README.md)
- Decisão: [Fundação local](2026-09-16-RPA-CONTROL-CENTER-FUNDACAO.md)

## Referências

- Documentação: https://learn.microsoft.com/windows-server/administration/windows-commands/powershell
- Issues:
- Commits:
- Outros:
