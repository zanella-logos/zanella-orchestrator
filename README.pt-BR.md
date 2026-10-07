<p align="right"><a href="README.md">English</a> · <strong>Português (Brasil)</strong></p>

<p align="center">
  <img src="assets/branding/zanella-orchestrator-icon.png" alt="Logo do Zanella Orchestrator" width="160">
</p>

# Zanella Orchestrator

**Local-first orchestration for automation workflows.**

[![License](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](https://opensource.org/licenses/Apache-2.0)
[![Windows](https://img.shields.io/badge/Windows-10%20%7C%2011-06B6D4)](https://www.microsoft.com/windows)
[![Python](https://img.shields.io/badge/Python-3.12%2B-3B82F6)](https://www.python.org/)
RC7 disponível para download: rolagem vertical nos agendamentos e tarefa Windows com o nome Zanella Orchestrator.

[![Release](https://img.shields.io/badge/release-0.1.0--rc7-F59E0B)](RELEASE_NOTES.md)

## Download para Windows

[![Baixar o instalador para Windows](https://img.shields.io/badge/Download-Instalador%20Windows-06B6D4?style=for-the-badge&logo=windows11&logoColor=white)](https://github.com/zanella-logos/zanella-orchestrator/releases/download/v0.1.0-rc7/Zanella-Orchestrator-Setup-0.1.0-rc7-windows-x64.exe)

**[Baixar diretamente o instalador `.exe`](https://github.com/zanella-logos/zanella-orchestrator/releases/download/v0.1.0-rc7/Zanella-Orchestrator-Setup-0.1.0-rc7-windows-x64.exe)** · [Ver todas as versões](https://github.com/zanella-logos/zanella-orchestrator/releases) · [Checksum](https://github.com/zanella-logos/zanella-orchestrator/releases/tag/v0.1.0-rc7)

Compatível com Windows 10 e 11 de 64 bits. O aplicativo ainda não possui assinatura digital; por isso, o Windows pode exibir um aviso de segurança. Confira o checksum SHA-256 publicado na release antes da instalação.

O **Zanella Orchestrator Community** é um motor de execução e orquestração local focado em simplicidade, privacidade e controle. Ideal para desenvolvedores RPA e equipes pequenas, permite gerenciar scripts Python, executáveis, `.bat` e Node.js em um único painel, sem a complexidade de infraestruturas em nuvem logo no primeiro dia.

**Por que o Zanella Orchestrator Community?**
- **Local-first:** Tudo roda na sua máquina ou servidor local. Sem vendor lock-in.
- **SQLite Out-of-the-Box:** Nenhuma configuração de banco necessária para começar. O PostgreSQL é opcional.
- **Múltiplos executores:** Suporte nativo a scripts `.py`, executáveis `.exe`, scripts batch `.bat`, entre outros.
- **Gestão limpa:** Fila FIFO, histórico de execuções, captura nativa de logs e estados de execução.
- **Agendamento Básico:** Integração direta com gatilhos do Agendador de Tarefas do Windows para automação local.

*(Módulos avançados planejados para o **Zanella Orchestrator Pro** incluirão controle de múltiplas máquinas (Remote Nodes), calendários de execução complexos com dependências e retries, RBAC, e Dashboards Avançados de SLA).*

## Tempo máximo de execução

Novas automações vêm com **Sem limite** marcado. Para definir um limite total opcional, desmarque essa opção e informe segundos positivos em **Tempo máximo de execução**. Ao atingir esse tempo, o robô e seus processos filhos são encerrados, mesmo se estiverem trabalhando. Esse campo não detecta inatividade, erro ou travamento.

Sem limite, um robô travado poderá segurar a fila sequencial até ser cancelado. O cancelamento manual continua disponível.

### Atualizando o Zanella Orchestrator

Feche o Zanella Orchestrator, aguarde os robôs em execução terminarem e instale a RC7 por cima, no mesmo usuário Windows. Não precisa desinstalar. A migração do esquema SQLite salva um backup antes de alterar a estrutura e preserva cadastros, limites existentes, histórico e agendamentos.

**Limites existentes, inclusive 180 ou 300 segundos, não são removidos automaticamente.** Em **Manutenção e portabilidade**, clique em **Remover limites de execução** e confirme para retirar os limites de todos os cadastros e itens na fila. Antes da mudança, são salvos backups dos cadastros e das configurações enfileiradas; no SQLite, também há backup completo do banco. O histórico anterior permanece intacto. Para backup completo do PostgreSQL, use as ferramentas do servidor. A ação fica bloqueada enquanto um robô estiver executando.

Se preferir, edite cada automação e marque **Sem limite**. A edição individual exige que essa automação não tenha execução ativa ou na fila.

## Executar pelo código-fonte

Esta opção evita o instalador sem assinatura e é indicada para desenvolvedores. Requer [Git](https://git-scm.com/downloads/win), [Python 3.12+](https://www.python.org/downloads/windows/) e [uv](https://docs.astral.sh/uv/getting-started/installation/).

```powershell
git clone https://github.com/zanella-logos/zanella-orchestrator.git
cd zanella-orchestrator
uv sync --extra ui
uv run rcc-ui
```

O comando `uv sync --extra ui` cria um ambiente isolado `.venv`, instala as versões exatas registradas no `uv.lock` e adiciona a interface desktop Flet. Ele não instala runtimes externos usados pelos robôs, como Node.js ou Java.

Se o processo falhar, copie a saída do terminal e [abra uma issue no GitHub](https://github.com/zanella-logos/zanella-orchestrator/issues/new). Os erros não são enviados automaticamente.

## Ambiente de desenvolvimento

Para incluir o suporte opcional ao PostgreSQL e executar os testes:

```powershell
uv sync --extra postgres --extra ui
uv run pytest -q
```

SQLAlchemy e Alembic cuidam da persistência; pywin32 fornece os controles de processos Windows e Flet fornece a interface desktop.

O primeiro painel permite cadastrar automações, enfileirar, executar a fila sem bloquear a janela, cancelar, consultar histórico e acompanhar logs. Consulte [Flet versus Python](docs/FLET-INTERFACE.md) para entender cada controle e callback usado.

Instruções operacionais dos campos da interface estão no [Manual do usuário](docs/MANUAL-USUARIO.md).

## PostgreSQL local

O servidor é opcional para uso normal, mas requerido para validar a compatibilidade. Com PostgreSQL instalado e ativo:

```powershell
uv run python scripts/setup_postgresql.py
uv run python scripts/validate_postgresql.py
```

O primeiro comando solicita a senha administrativa sem exibi-la. Ele cria o usuário limitado `rcc_app`, o banco operacional `rpa_control_center` e o banco descartável `rpa_control_center_test`. Uma senha aleatória do aplicativo é guardada no Windows Credential Manager; a senha administrativa não é armazenada.

Execute o setup com a mesma conta Windows que executará o Zanella Orchestrator e o Agendador. O script para ao encontrar o usuário existente e não altera instalações anteriores automaticamente.

## Implementado

- Modelos de robôs e execuções, com cópia da configuração por execução.
- Migration inicial e reserva transacional de um item da fila, validadas em SQLite e PostgreSQL 18.
- Mutex Windows entre sessões, identificado por instalação.
- Processo criado suspenso, associado a Job Object e depois iniciado.
- Encerramento da árvore de processos ao fechar o último handle do Job Object.
- Testes com processos reais para concorrência, encerramento e queda do supervisor.
- Motor sequencial com logs contínuos em UTF-8, limite total opcional, cancelamento e recuperação.
- CLI inicial para migrations, cadastro, fila, consulta, cancelamento e processamento.
- Robô demonstrativo em Flet que abre uma janela, captura e valida sua imagem e apaga o arquivo temporário.
- Demonstração com Chrome, página local controlada e evidência persistida na Área de Trabalho.
- Robô de validação com cenários de sucesso, falha de negócio, falha técnica, timeout e cancelamento.
- Remoção de uma automação com seu próprio histórico e logs, bloqueada durante execuções ativas.
- Remoção individual de uma execução finalizada e da respectiva pasta de logs.
- Edição do cadastro sem alterar as configurações congeladas nas execuções anteriores.
- Ativação e desativação de automações com bloqueio durante itens ativos ou enfileirados.
- Execução imediata por automação, iniciando o motor e ignorando a fila.
- Indicadores coloridos de execução; a interface Community mantém apenas o filtro Estado.
- Adaptadores de comando para Python, PowerShell, Batch, executáveis, Node.js e arquivos JAR.
- Migração compatível com os robôs Python existentes; o tipo padrão continua sendo `python`.

O mutex deve usar o mesmo identificador em todas as entradas de uma instalação. A execução pelo Agendador foi validada com a mesma conta Windows; contas diferentes ainda exigem teste específico. A reserva transacional sozinha não impede dois itens diferentes de rodarem ao mesmo tempo: o mutex também é obrigatório.

Validação local RC6 em 2026-10-05: 88 testes aprovados e 1 teste PostgreSQL ignorado. O agendador empacotado concluiu um robô sem limite, aplicou um limite explícito, continuou FIFO imediatamente, recusou execução concorrente e não abriu janela extra. O teste do usuário na VDI ainda está pendente.

## Banco e migrations

Para o banco SQLite padrão, criar uma pasta `data` e executar:

```powershell
uv run alembic upgrade head
```

`RCC_DATABASE_URL` permite selecionar um banco PostgreSQL via driver psycopg. Não guardar senhas em arquivos versionados. A migration foi validada localmente em SQLite e PostgreSQL 18.

O validador monta `RCC_TEST_POSTGRES_URL` apenas no processo de teste usando o cofre. O teste recusa bancos com tabelas existentes; cria tabelas e testa downgrade/upgrade, deixando o esquema de teste instalado. Nunca apontar para banco operacional.

## Validação operacional pela interface

Cadastre `demo/browser_evidence_robot.py` como Python para validar um processo filho real do Chrome. A demonstração usa uma página local, perfil temporário e salva `RCC-evidencia-<run>.png` na Área de Trabalho. Ela não depende de internet nem de um site externo.

Cadastre `demo/validation_robot.py` mais de uma vez e informe um argumento por cadastro:

- `success`: produz logs graduais e resultado de negócio `success`;
- `business_error`: processo termina com código zero, mas declara falha de negócio;
- `technical_error`: termina com código 7 e estado técnico de falha;
- `hang`: cria um processo filho e aguarda timeout ou cancelamento.

No cenário `hang`, habilite um limite total curto para validar `timed_out`, ou use **Cancelar** com Sem limite para validar `cancelled`. A interface Community mostra apenas estados de execução; código zero significa conclusão técnica, não comprovação de sucesso de negócio. Enfileire dois cenários `success` para confirmar a ordem sequencial.

## Versão candidata

A RC6 adota **Sem limite** como padrão, esclarece o limite total de execução, simplifica o histórico Community para Estado e atualiza OAuthlib para 4.0.0. Mantém a fila contínua FIFO e a consulta configurável de 1 a 59 minutos da RC5. RC6 disponível para download. Novas automações usam Sem limite; limites antigos exigem remoção explícita.

## Executável Windows

O projeto segue a estrutura oficial do `flet build`, com entrada em `main.py` e configuração no `pyproject.toml`. No aplicativo empacotado, banco, logs e configuração usam `FLET_APP_STORAGE_DATA`; no desenvolvimento continuam na pasta `data` do projeto.

Após autorizar o download oficial do Flutter no primeiro build:

```powershell
uv pip install "flet[cli]==1.0.0"
.venv\Scripts\python.exe scripts\prepare_windows_build.py
.venv\Scripts\flet.exe build windows "<caminho-da-pasta-gerada>" --python-version 3.13 --no-compile-app --build-version 0.1.0 --build-number 10 --output build/windows-rc6-final --yes --no-rich-output
```

Substitua `<caminho-da-pasta-gerada>` pelo caminho completo impresso pelo script. As fontes Python permanecem no pacote porque o Alembic precisa descobrir os arquivos de revisão em `migrations\versions`. As fontes da release são preparadas com `scripts/prepare_windows_build.py`, sem dados locais de testes. O build RC6 gera a aplicação em `build\windows-rc6-final`. O instalador oficial é produzido pelo Inno Setup a partir de `installer\Zanella-Orchestrator.iss`.

Instalador da versão: `dist\Zanella-Orchestrator-Setup-0.1.0-rc6-windows-x64.exe`. O arquivo `dist\SHA256SUMS-0.1.0-rc6.txt` permite conferir a integridade do pacote.

## CLI inicial

```powershell
uv run rcc init
uv run rcc robot-add "Exemplo" "C:\caminho\robo.py" --python "C:\caminho\.venv\Scripts\python.exe" --cwd "C:\caminho"
uv run rcc robot-add "PowerShell" "C:\caminho\robo.ps1" --type powershell --executable "C:\Windows\System32\WindowsPowerShell\v1.0\powershell.exe" --cwd "C:\caminho"
uv run rcc enqueue ID_DO_ROBO
uv run rcc engine
uv run rcc runs
uv run rcc scheduler
uv run rcc cancel ID_DA_EXECUCAO
```

O comando `engine` processa a fila até esvaziar. O Agendador usará essa mesma entrada. Logs completos ficam em `data/logs/<run_id>`; o banco mantém caminhos, estados, horários, código de saída. Resultados de negócio não são exibidos na interface Community.

Os runtimes externos não são distribuídos pelo Zanella Orchestrator. Node.js, Java ou outro executável precisam estar instalados e seus caminhos devem ser cadastrados. O adaptador PowerShell usa `ExecutionPolicy Bypass` somente na sessão filha; não modifica a política global do Windows.

Validação multilíngue de 2026-09-17: Python/Flet, PowerShell 5.1, Node.js 22.16.0 e OpenJDK 25.0.3 LTS foram executados pela fila real com código de saída `0` e resultado de negócio `success`. Um executável também foi iniciado diretamente pelo adaptador genérico.

## Direção de produto

| Zanella Orchestrator Community (Gratuito) | Zanella Orchestrator Pro |
| --- | --- |
| Python, PowerShell, EXE, Batch, Node.js e Java | Remote Nodes (Controle central de múltiplas máquinas) |
| Execução manual e fila sequencial local | Instalação como serviço Windows invisível |
| Logs, histórico, limite opcional de execução e cancelamento | Resultados de negócio, acompanhamento de progresso e SLA avançado (planejados) |
| SQLite out-of-the-box e PostgreSQL opcional | Autenticação Empresarial (RBAC, Active Directory / SSO) |
| Agendamento básico e gatilho automático único do Windows | Calendários de execução avançados (dependências, retries, cron) |
| API básica para módulos | Alertas avançados (Teams, Slack, Webhooks) |

Docker será opcional para infraestrutura. Executor Windows permanece nativo; mobile poderá ser um painel remoto futuro. Redis não é necessário para esta etapa.

Escopo: [MVP](MVP.md). Decisões técnicas: [fundação](docs/decisao-fundacao.md) e [executor genérico](docs/decisao-executor-generico.md).

## Licença

Copyright 2026 Victor César Zanella

Este projeto é licenciado sob a licença [Apache 2.0](LICENSE).

## Autor

**Victor César Zanella** é profissional de automação e RPA, criador de conteúdo e autor. Criou o Zanella Orchestrator para tornar a execução local de automações mais organizada, transparente e acessível — porque até robô precisa de alguém organizando a fila.

- [LinkedIn](https://www.linkedin.com/in/victor-zlogos)
- [GitHub](https://github.com/zanella-logos)
- [Nerd Profeta no YouTube](https://www.youtube.com/@nerdprofeta) — conteúdo nerd e gamer, lives e reflexões bíblicas.
- Livro: [**A Jornada do Nerd para se tornar um Profeta**](https://link.amazon/B09CPEwfe).
