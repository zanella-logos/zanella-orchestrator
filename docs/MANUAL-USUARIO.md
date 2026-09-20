# Manual do Usuário — Zanella Orchestrator Community

Este manual explica como instalar e operar o Zanella Orchestrator Community no Windows. O sistema cadastra, executa, agenda e acompanha automações locais. A interface pode permanecer fechada durante execuções agendadas.

A interface inicia no tema escuro. O botão com símbolo de sol ou lua, no cabeçalho, alterna entre os temas escuro e claro. O indicador ao lado informa o estado operacional do painel.

## 1. Instalação pelo código-fonte

Requisitos:

- Windows 10 ou 11;
- Python 3.12 ou superior;
- `uv` instalado;
- runtimes exigidos pelos robôs, como Node.js ou Java.

Na pasta do projeto, execute:

```powershell
uv sync --extra ui
.venv\Scripts\rcc-ui.exe
```

Também é possível abrir `Iniciar Orquestrador.bat`. O arquivo usa sua própria pasta como referência e funciona independentemente do local onde o projeto foi extraído.

O SQLite é criado automaticamente. PostgreSQL é opcional e requer configuração técnica adicional.

## 2. Cadastro de automações

Use a seção **Cadastrar automação** e preencha:

| Campo | Uso |
| --- | --- |
| Nome | Identificação exibida no painel e histórico. |
| Tipo | Define como o comando será montado. |
| Arquivo principal | Script, executável ou JAR que será iniciado. |
| Runtime ou launcher | Interpretador responsável pelo arquivo. Não é usado para executáveis nativos. |
| Pasta de trabalho | Diretório no qual o processo será iniciado. |
| Argumentos | Um argumento por linha, mantendo a ordem esperada pelo programa. |
| Timeout | Limite máximo da execução, em segundos. |

Tipos suportados:

| Tipo | Arquivo | Runtime típico |
| --- | --- | --- |
| Python | `.py` | `python.exe` |
| PowerShell | `.ps1` | `powershell.exe` |
| Batch | `.bat` ou `.cmd` | `cmd.exe` |
| Executável | `.exe` | O próprio executável; runtime ignorado. |
| Node.js | `.js` | `node.exe` |
| Java | `.jar` | `java.exe` |

O Python global é sugerido para os robôs. O ambiente `.venv` pertence ao Zanella Orchestrator e não deve ser usado automaticamente como ambiente de todos os robôs. Node.js, Java e outros runtimes não são distribuídos pelo produto.

Exemplo de argumentos:

```text
--empresa
123
--arquivo
C:\Relatórios\Fechamento mensal.xlsx
```

Cada linha vira um único argumento. Evite informar senhas, pois argumentos podem ser visíveis em ferramentas do sistema.

Clique em **Cadastrar**. Depois, **Editar** altera somente execuções futuras. Histórico anterior conserva a configuração utilizada na ocasião.

## 3. Execução manual

- **Enfileirar:** cria uma execução pendente. Clique em **Executar fila** para processar os itens na ordem FIFO.
- **Play:** prioriza a automação escolhida e ignora a ordem dos itens que já estavam na fila.
- **Stop/Cancelar:** solicita o encerramento da execução e de seus processos filhos.
- **Desativar:** impede novos enfileiramentos e agendamentos, preservando cadastro e histórico.

O Play não cria execução paralela. O mutex da instalação mantém apenas uma automação em execução por vez. Se outro motor estiver ocupado, o Play aguarda a liberação antes de iniciar a automação selecionada.

## 4. Agendamentos

Na seção **Agendamentos**:

1. Selecione uma automação ativa.
2. Escolha a frequência:
   - **Diário:** todos os dias no horário definido;
   - **Semanal:** um dia da semana;
   - **Personalizado:** qualquer combinação de dias, como segunda a sexta.
3. Informe o horário no formato `HH:MM`.
4. Clique em **Agendar**.
5. Clique uma única vez em **Instalar gatilho global**.

Todos os horários usam uma tarefa do Windows chamada `RPA Control Center Scheduler`. Ela consulta agendas vencidas a cada cinco minutos, cria as execuções correspondentes e processa a fila. Por isso, o início pode ocorrer até aproximadamente cinco minutos depois do horário cadastrado. O painel Flet pode permanecer fechado.

O gatilho deve ser instalado apenas uma vez. Cadastrar novos horários não exige reinstalação. Na tabela de agendamentos é possível pausar, reativar ou remover cada horário. Essas ações não apagam o histórico.

- **Abrir Agendador:** abre o console nativo do Windows para consultar a tarefa.
- **Remover gatilho global:** remove somente a tarefa do Windows. Os horários continuam salvos, mas deixam de disparar até nova instalação.

Automações de navegador ou desktop exigem uma sessão Windows interativa. Bloquear a estação pode afetar robôs que dependem da interface gráfica.

## 5. Histórico, estados e resultados

O histórico separa estado técnico do resultado de negócio.

Estados técnicos:

| Estado | Significado |
| --- | --- |
| `queued` | Execução aguardando motor. |
| `starting` | Execução reservada e sendo iniciada. |
| `running` | Processo ativo. |
| `cancelling` | Cancelamento solicitado. |
| `completed` | Processo terminou com código de saída zero. |
| `failed` | Processo falhou ou não pôde iniciar. |
| `cancelled` | Operador cancelou a execução. |
| `timed_out` | Timeout excedido. |
| `interrupted` | Supervisão anterior foi interrompida. |

Resultados de negócio:

| Resultado | Significado |
| --- | --- |
| `success` | Robô declarou sucesso. |
| `business_error` | Processo terminou, mas declarou problema de negócio. |
| `technical_error` | Robô declarou falha técnica. |
| `partial` | Resultado parcialmente concluído. |
| `not_reported` | Robô não produziu contrato JSON de resultado. |
| `invalid_report` | Arquivo de resultado existe, mas não segue o contrato esperado. |

Use a pesquisa, os filtros de estado e negócio e os botões de paginação. **Logs** mostra `stdout` e `stderr`; **Abrir pasta de logs** mostra os arquivos no Explorer. Remover uma execução finalizada apaga também sua pasta de logs.

## 6. Manutenção e portabilidade

- **Limpar antigos:** remove execuções finalizadas anteriores ao número de dias informado e tenta remover seus logs.
- **Exportar cadastros:** cria JSON com configurações dos robôs. Não inclui histórico, logs, IDs nem credenciais.
- **Importar cadastros:** cria ou atualiza robôs pelo nome.
- **Backup SQLite:** cria uma cópia íntegra do banco local usando a API de backup do SQLite.
- **Restaurar SQLite:** valida integridade e estrutura antes de substituir o banco atual.

Retenção, importação e restauração são bloqueadas enquanto existirem execuções na fila ou ativas. Backup e restauração completos estão disponíveis somente com SQLite. Em PostgreSQL, use as ferramentas administrativas próprias do servidor; exportar e importar cadastros continuam disponíveis.

Os ícones de lixeira dos painéis permitem limpar todos os robôs ou todo o histórico após confirmação. A exclusão também é bloqueada quando há execuções pendentes ou ativas.

## 7. Atualização e desinstalação

Antes de atualizar, faça backup e encerre o painel. Atualize os arquivos do projeto e execute:

```powershell
uv sync --extra ui
uv run alembic upgrade head
```

Para desinstalar:

1. Use **Remover gatilho global** se ele estiver instalado.
2. Faça o backup desejado.
3. Feche o Zanella Orchestrator.
4. Exclua a pasta do projeto.

## 8. Diagnóstico básico

- **Arquivo ou runtime não encontrado:** confirme caminhos e instalação do runtime selecionado.
- **Robô funciona no terminal, mas não no Zanella Orchestrator:** confira pasta de trabalho, argumentos e Python/runtime cadastrado.
- **Agendamento não dispara:** confirme que o gatilho global está instalado, que a agenda e a automação estão ativas e que a conta Windows possui sessão adequada ao tipo de robô.
- **Painel não abre:** execute `.venv\Scripts\rcc-ui.exe` em um terminal para visualizar o erro.
- **Falha PostgreSQL:** execute o setup com a mesma conta Windows usada pelo Zanella Orchestrator; a senha do aplicativo fica no Windows Credential Manager.
- **Logs vazios:** o programa executado precisa escrever em `stdout` ou `stderr`.

## 9. Contrato opcional de resultado

O código de saída controla o estado técnico. Para informar resultado de negócio, o robô pode gravar JSON no caminho fornecido pela variável `RCC_RESULT_PATH`:

```json
{
  "version": 1,
  "run_id": "valor recebido em RCC_RUN_ID",
  "status": "success",
  "summary": "Processo concluído"
}
```

Status aceitos: `success`, `business_error`, `technical_error` e `partial`.
