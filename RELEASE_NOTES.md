# Zanella Orchestrator Community 0.1.0-rc5

A RC5 mantém as correções da RC4 e melhora o agendamento e a fila de execução.

- Fila contínua: ao finalizar um robô, o próximo começa sem aguardar outro disparo do Windows. Inclui itens manuais e agendamentos vencidos, com execução sequencial FIFO e proteção contra execuções paralelas por executores concorrentes.
- Intervalo do gatilho: padrão de 1 minuto, opções de 3 e 5 minutos e personalizado de 1 a 59. Valores como 7 e 07 representam sete minutos.
- Atualizar gatilho fica disponível apenas quando o intervalo válido difere do instalado.
- Timeout padrão da Home: 180 segundos (3 minutos), incluindo após cadastrar uma automação.
- Campo personalizado permite apagar todos os dígitos com Backspace; mensagens usam Zanella Orchestrator.

Para atualizar, feche o aplicativo e execute `Zanella-Orchestrator-Setup-0.1.0-rc5-windows-x64.exe` no mesmo usuário Windows. Cadastros existentes são preservados. Para alterar o intervalo de um gatilho já instalado, selecione o novo valor e clique em **Atualizar gatilho global**. A instalação não muda automaticamente o intervalo anterior nem o timeout dos robôs já cadastrados.

Validação: 74 testes aprovados, 1 teste PostgreSQL ignorado; executável empacotado validado com fila manual e agendada no mesmo ciclo, e disparo concorrente sem execução paralela.

Runtimes e dependências dos robôs precisam estar instalados na máquina. Automações de desktop e navegador exigem sessão Windows interativa. Instalador sem assinatura digital nesta versão candidata.

## Histórico: 0.1.0-rc4


A RC4 corrige a execução de robôs Python externos e o disparo automático no Windows. O agendador agora inicia sem abrir uma janela extra do Zanella, e a pasta de dados passa a ser `%APPDATA%\Zanella\Zanella Orchestrator\data`.

Os dados da pasta antiga são copiados na primeira abertura, sem apagá-la. Para atualizar, feche o Zanella e execute `Zanella-Orchestrator-Setup-0.1.0-rc4-windows-x64.exe` no mesmo usuário Windows. Robôs Python continuam precisando de um Python e das dependências do próprio robô instalados nessa máquina.

Validação: 51 testes aprovados, 1 ignorado; disparo automático de robô Python confirmado em outra máquina Windows com a RC4.

## Histórico: 0.1.0-rc3

Esta versão corrige a instalação do gatilho global pelo aplicativo Windows empacotado. O agendador passa a chamar o executável instalado do Zanella Orchestrator em modo de execução sem interface, sem depender de um `rcc.exe` ausente no pacote.

Validação: 48 testes aprovados e 1 ignorado; aplicativo empacotado executou o agendador com banco SQLite isolado e terminou sem erro.

Para atualizar uma instalação RC2, execute o instalador RC3 no mesmo usuário Windows. Depois abra o aplicativo e clique em **Instalar gatilho global** para criar ou atualizar a tarefa do Agendador de Tarefas.

## Histórico: 0.1.0-rc2

Segunda versão candidata pública do Zanella Orchestrator Community, um orquestrador local para automações Windows.

## Correção crítica

- os seletores de arquivo e pasta agora usam o serviço nativo do Flet;
- removida a dependência de `tkinter`, ausente no runtime empacotado da RC1;
- falhas ao abrir um seletor passam a ser exibidas no status sem encerrar a interface;
- adicionados testes automatizados dos seletores e de todos os grupos de botões da interface.

## Destaques

- cadastro e execução de automações Python, PowerShell, Batch, EXE, Node.js e Java;
- fila FIFO com execução sequencial e ação de execução imediata;
- histórico técnico separado do resultado de negócio;
- logs, timeout, cancelamento e encerramento da árvore de processos;
- agendamentos diários, semanais ou por combinação de dias;
- gatilho global do Agendador de Tarefas com painel fechado;
- busca, filtros e paginação real no banco;
- retenção, exportação e importação de cadastros;
- backup e restauração do SQLite;
- SQLite por padrão e PostgreSQL opcional;
- tema escuro, tema claro e identidade visual Z-Flow.

## Instalação

Baixe e execute `Zanella-Orchestrator-Setup-0.1.0-rc2-windows-x64.exe`.

Também existe um pacote portátil em ZIP. Extraia todo o conteúdo antes de abrir `Zanella-Orchestrator.exe`.

## Validação

- Windows 10/11 x64;
- 47 testes automatizados aprovados;
- 1 teste PostgreSQL ignorado na execução final local;
- executável e ZIP validados com armazenamento SQLite vazio;
- checksum SHA-256 publicado com os artefatos.

## Observações

- runtimes externos usados pelos robôs, como Node.js e Java, precisam estar instalados na máquina;
- automações de navegador e desktop exigem sessão Windows interativa;
- o executável ainda não possui assinatura digital, então o Windows SmartScreen pode exibir um aviso;
- esta é uma versão candidata: faça backup antes de testar com processos críticos.

## Licença

Apache License 2.0. Copyright 2026 Victor César Zanella.
