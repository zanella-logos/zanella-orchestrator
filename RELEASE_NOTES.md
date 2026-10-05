# Zanella Orchestrator Community 0.1.0-rc6

A RC6 corrige o padrão de limite de execução da RC5. Novas automações usam **Sem limite**. O campo passa a se chamar **Tempo máximo de execução**. Não há detecção automática de travamento.

- Histórico Free: apenas Estado; filtro e coluna Negócio removidos. Iniciando e Cancelando permanecem internos, fora das opções do filtro.
- Atualização preserva limites antigos. Use **Remover limites de execução** para desativá-los nos cadastros e itens na fila após backup e confirmação. Não altera o histórico e não opera enquanto um robô estiver executando.
- OAuthlib atualizado para 4.0.0, com verificação de compatibilidade com Flet.
- Fila contínua FIFO, agendamentos e intervalo configurável de 1 a 59 minutos da RC5 preservados.

Feche o aplicativo, aguarde os robôs terminarem e instale `Zanella-Orchestrator-Setup-0.1.0-rc6-windows-x64.exe` por cima, no mesmo usuário Windows. Não precisa desinstalar.

Sem limite, um robô travado pode segurar a fila até ser cancelado. Runtimes e dependências dos robôs continuam sendo responsabilidade do ambiente em que rodam. Automações de desktop exigem sessão interativa.

Validação local: 88 testes aprovados, 1 PostgreSQL ignorado; executável conferido com fontes atuais, OAuthlib 4.0.0, Flet 1.0.0, sequência e limites reais, sem janela extra.
