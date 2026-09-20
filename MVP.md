# Zanella Orchestrator — contrato do MVP

Status: escopo aprovado para desenvolvimento incremental. Data: 2026-09-16.

## Objetivo

Executar e acompanhar automações locais em uma máquina Windows, com prioridade para Python, fila sequencial, histórico persistente e falhas previsíveis. Interface Flet e entrada por linha de comando utilizam o mesmo motor. Nenhuma API paga é obrigatória.

## Escopo

- Cadastro: nome, tipo de executor, alvo, executável de inicialização, argumentos como lista, pasta de trabalho e timeout positivo em segundos.
- Validação de script, interpretador e pasta antes do início. Comandos executados sem shell intermediário.
- Iniciar, acompanhar e cancelar execuções; cancelar também itens ainda na fila.
- Uma execução ativa por instalação, independentemente de ter sido solicitada pelo painel ou pelo Agendador do Windows.
- Processo separado por execução, com runtime ou executável escolhido no cadastro.
- Histórico de início, fim, duração, estado, motivo, código de saída e resultado de negócio.
- Saída padrão e saída de erro capturadas continuamente em arquivos por execução e exibidas pela interface em lotes limitados.
- SQLite local por padrão; PostgreSQL opcional, com os mesmos comportamentos públicos testados em ambos.

Não inclui vários computadores, recorder, editor de fluxos, IA, gestão completa do Agendador, plugins dinâmicos ou reexecução automática.

## Componentes e funcionamento

1. Interface e CLI cadastram solicitações na persistência compartilhada.
2. Um motor independente da interface assume a fila e executa um item por vez.
3. O motor cria o processo do robô, registra saída e acompanha cancelamento e timeout.
4. A interface consulta os estados e lê trechos dos logs; fechar o painel não encerra o motor.

A CLI deve permitir enfileirar, consultar, cancelar e iniciar o motor sem painel. A forma concreta de inicialização automática do motor será definida na preparação do projeto. No MVP, o Agendador poderá iniciar o motor em modo de processamento da fila; solicitações enviadas sem motor ativo devem aparecer como aguardando executor.

A proteção contra motores simultâneos precisa abranger processos diferentes. A tomada do item deve ser transacional. Ao perder a posse exclusiva da execução, o motor não pode continuar disparando trabalhos. O mecanismo será validado nos dois bancos antes da interface.

O escopo continua sendo uma instalação em uma máquina mesmo quando o banco for PostgreSQL. Banco servidor não habilita automaticamente execução distribuída.

## Estados de execução

| Estado | Significado |
|---|---|
| queued | Solicitação persistida, aguardando o motor. |
| starting | Item reservado; validação e criação do processo em andamento. |
| running | Processo criado e acompanhado. |
| cancelling | Cancelamento solicitado; encerramento ainda não confirmado. |
| completed | Processo terminou com código zero. Resultado de negócio é um campo separado. |
| failed | Falha ao iniciar, saída não zero ou falha técnica de supervisão. |
| cancelled | Item retirado da fila ou processo e descendentes encerrados por cancelamento. |
| timed_out | Prazo excedido e encerramento confirmado. |
| interrupted | Execução perdeu supervisão; resultado não pode ser determinado com segurança. |

Estados finais são imutáveis. Uma nova tentativa cria outra execução ligada à anterior e preserva seu histórico.

Cancelamento é uma solicitação: se o processo já terminou, preservar o resultado real. Se o encerramento não puder ser confirmado, registrar a incerteza e impedir o avanço da fila até reconciliação; não declarar cancelamento bem-sucedido.

## Resultado técnico e resultado de negócio

Código de saída zero significa apenas conclusão técnica. Robôs existentes podem executar sem alterações; nesse caso o resultado de negócio fica como `not_reported`.

Integração opcional: o motor entrega por variáveis de ambiente o identificador da execução e um caminho exclusivo para um arquivo JSON de resultado. O robô grava o resultado de forma atômica antes de terminar.

Contrato proposto, versão 1:

```json
{
  "version": 1,
  "run_id": "identificador-fornecido-pelo-motor",
  "status": "success",
  "summary": "Processamento fictício concluído"
}
```

Resultados declarados: `success`, `business_error`, `technical_error` e `partial`. Resultado ausente é `not_reported`; JSON inválido ou identificação incompatível é `invalid_report`. A interface mostra estado técnico e resultado declarado separadamente. Saída não zero, timeout ou cancelamento nunca aparecem como sucesso global, mesmo com arquivo declarando sucesso.

O conteúdo é uma declaração do robô; o Control Center não comprova sozinho que uma operação externa foi concluída corretamente. Resumos e logs públicos devem usar dados fictícios.

## Cancelamento, timeout e isolamento

- O timeout começa quando o processo é criado; tempo de fila é registrado separadamente.
- No Windows, a implementação deve controlar o processo e seus descendentes, preferencialmente com Job Objects, e testar encerramento inclusive quando o motor cai.
- Não encerrar processos por nome global, como todos os navegadores ou todos os Python da máquina.
- Processo separado não isola perfil de navegador, arquivos, sessão do desktop ou contas externas.
- Cada robô é responsável por seu perfil de navegador e limpeza de recursos. Qualquer protocolo adicional de isolamento deve ser validado com um exemplo fictício antes de entrar no núcleo.
- Logs podem conter saída atrasada pelo buffering do processo; usar o modo sem buffering quando o runtime permitir e limitar o volume mantido na interface.

## Queda e reinicialização

Na retomada, reconciliar execuções não finalizadas com identidade do processo, posse do motor e registros persistidos. Não confiar somente em PID, pois ele pode ser reutilizado.

Trabalhos pendentes permanecem na fila. Trabalhos que perderam supervisão ficam como interrompidos quando não for possível confirmar seu resultado. Nenhuma execução interrompida é repetida automaticamente. A fila só prossegue após confirmar que o trabalho anterior não continua ativo.

Não há garantia de exatamente uma operação de negócio: uma queda pode ocorrer após a ação externa e antes do registro do resultado. Reexecutar exige decisão explícita do operador e atenção à idempotência do robô.

## Persistência e compatibilidade

SQLAlchemy e Alembic são a proposta para acesso a dados e evolução do esquema. Interface e execução não devem conter consultas SQL espalhadas.

Entidades mínimas: robôs, execuções e coordenação do motor. A execução preserva uma cópia da configuração usada, para que editar o cadastro não altere a descrição de execuções passadas.

Logs completos ficam em arquivos locais, com referências no banco. Usar PostgreSQL não transporta esses arquivos para outro computador.

Compatibilidade significa: mesmos estados, comandos, integridade e resultados observáveis. Não significa SQL, desempenho ou locks idênticos. Testar cadastro, tomada da fila, concorrência entre motores, cancelamento, histórico e migrations nos dois bancos.

Uma troca de banco precisa de exportação/importação validada; migrations de esquema não transferem dados entre SQLite e PostgreSQL. Migração de dados de instalações existentes fica fora do MVP, sem promessa de troca automática.

## Containers e evoluções

Docker poderá fornecer um ambiente opcional para PostgreSQL e testes. Aplicação Flet e executor de automações Windows continuam nativos. Container Linux não reproduz a sessão gráfica Windows nem executa seus aplicativos desktop.

Redis não faz parte do MVP. Mesmo uma evolução com vários workers deve primeiro avaliar se PostgreSQL já atende à coordenação necessária.

Módulos futuros: RPA Doctor e evidências, integração com Automation Studio e ROI Analyzer. Preservar separação entre motor, persistência e interface sem criar um sistema genérico de plugins agora.

## Critérios de aceite

1. Script fictício com saída zero: conclusão técnica e resultado de negócio não informado.
2. Script com resultado válido: apresentação separada do estado e resultado declarado.
3. Exceção, script ausente e interpretador inválido: falha registrada, sem travar a fila.
4. Script travado: timeout encerra processo e descendentes.
5. Cancelamento pendente e em execução: estados corretos e nenhum filho remanescente.
6. Grande volume em stdout e stderr: coleta sem deadlock e interface responsiva.
7. Painel fechado: motor continua e histórico aparece ao reabrir.
8. Dois motores e disparos simultâneos: nenhuma execução indevidamente sobreposta.
9. Queda do motor e reinício: reconciliação sem repetir operações automaticamente.
10. Mesma suíte de persistência e coordenação passa em SQLite e PostgreSQL reais.
11. Caminhos com espaços e caracteres Unicode, argumentos e ambientes virtuais funcionam no Windows.

## Próxima etapa

Fundação, posse exclusiva e compatibilidade SQLite/PostgreSQL foram validadas. Próxima etapa: implementar execução e histórico com robôs fictícios. Interface vem após validação do motor.

As decisões aceitas devem ser registradas no DevKB conforme o template oficial de decisão. A fundação validada está descrita em `docs/decisao-fundacao.md`.
