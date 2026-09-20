# Zanella Orchestrator Community 0.1.0-rc1

Primeira versão candidata pública do Zanella Orchestrator Community, um orquestrador local para automações Windows.

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

Baixe e execute `Zanella-Orchestrator-Setup-0.1.0-rc1-windows-x64.exe`.

Também existe um pacote portátil em ZIP. Extraia todo o conteúdo antes de abrir `Zanella-Orchestrator.exe`.

## Validação

- Windows 10/11 x64;
- 38 testes automatizados aprovados;
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
