# Interface Flet: relação com Python

Flet não substitui Python. Ele é uma biblioteca Python que cria controles visuais e usa Flutter para desenhá-los no Windows, web e mobile. A biblioteca padrão do Python não oferece uma interface gráfica única; `tkinter` é a alternativa incluída em muitas instalações, mas não está disponível em todo runtime e possui controles diferentes.

## Recursos usados

| Flet | Função no Control Center | Equivalente conceitual em Python ou tkinter |
| --- | --- | --- |
| `ft.run(main)` | Inicia o runtime visual e chama `main` quando a janela está pronta. | `if __name__ == "__main__"` inicia um programa; em tkinter seria `root.mainloop()`. |
| `ft.Page` | Representa a janela e contém tema, tamanho e controles. | Objeto de contexto; em tkinter se aproxima de `tk.Tk`. |
| `ft.Text` | Exibe títulos, estados e logs. | Uma `str` contém o texto; `tk.Label` o mostra visualmente. |
| `ft.TextField` | Recebe nome, caminhos, argumentos e timeout. | Atributo `str` ou `input()`; em tkinter, `tk.Entry` ou `tk.Text`. |
| `ft.Dropdown` | Restringe o tipo de executor aos valores suportados. | Validação contra uma tupla; em tkinter, `ttk.Combobox`. |
| `ft.Button` | Dispara cadastro, fila, atualização, logs e cancelamento. | Chamada de função; em tkinter, `tk.Button(command=...)`. |
| `on_click` / `on_select` | Guarda uma função callback chamada após o evento do usuário. | Passar uma função como objeto: `botao = minha_funcao`, sem executá-la naquele momento. |
| `ft.Row` | Organiza controles horizontalmente. | Uma lista define ordem; em tkinter, `Frame` com `pack(side="left")` ou `grid`. |
| `ft.Column` | Organiza controles verticalmente. | Uma lista de objetos; em tkinter, `Frame` com `pack` ou `grid`. |
| `ft.ResponsiveRow` | Coloca os painéis lado a lado em tela larga e empilha em janela menor. | Um `if largura >= limite`, declarado no próprio layout. |
| `ft.Container` | Aplica borda, fundo, espaçamento e tamanho ao conteúdo. | Um objeto que compõe outro; em tkinter, `Frame`. |
| `ft.DataTable` | Mostra robôs e histórico em linhas e colunas. | Lista de objetos formatada; em tkinter, `ttk.Treeview`. |
| `ft.ProgressRing` | Indica que o motor está ocupado. | Uma variável booleana de estado; em tkinter, `ttk.Progressbar`. |
| `page.update()` | Envia ao cliente Flet as propriedades alteradas. | Não há equivalente em Python puro; lembra `update_idletasks()` do tkinter. |
| `async def` | Permite que eventos aguardem tarefas sem bloquear o loop visual. | Coroutine nativa do Python criada com `asyncio`. |
| `asyncio.to_thread()` | Executa o motor bloqueante em outra thread. | Recurso da biblioteca padrão para manter a janela responsiva. |

## Funções da interface

### `parse_arguments`

Transforma o campo multilinha em `list[str]`. Cada linha vira exatamente um argumento. Isso evita interpretar comandos por shell e preserva espaços dentro de um argumento.

### `default_launcher`

Usa `shutil.which`, da biblioteca padrão, para localizar Python, PowerShell, CMD, Node.js ou Java no Windows.

### `format_time`

Transforma o timestamp numérico persistido no banco em data e hora legíveis.

### `read_log`

Lê `stdout.log` ou `stderr.log` com tolerância a caracteres inválidos e limita a interface aos últimos 50 mil caracteres.

### `ControlCenterUI.build`

Monta a árvore visual. Flet trabalha com composição: uma `Page` recebe uma `Column`, que contém `Row`, `Container`, campos, botões e tabelas.

### `ControlCenterUI.refresh`

Consulta robôs e execuções pelos serviços do núcleo, recria as linhas das tabelas e chama `page.update()`. Nenhuma regra de execução fica no Flet.

### Callbacks de cadastro, fila, cancelamento e logs

São funções Python associadas aos eventos dos controles. Elas chamam `service.py`, atualizam o estado visual e tratam erros para que uma falha de entrada não feche a aplicação.

### `ControlCenterUI.execute_queue`

Chama `run_engine` por `asyncio.to_thread()`. Enquanto a thread trabalha, a coroutine atualiza histórico e logs a cada meio segundo. Assim a janela continua aceitando rolagem e cancelamento.

### `main`

Configura a janela, executa migrations, cria a conexão com o banco, monta a interface e carrega os dados existentes.

### `run`

É a entrada do comando `rcc-ui`. Sua única responsabilidade é entregar `main` ao runtime Flet.

## Separação arquitetural

```text
Flet: entrada e apresentação
        ↓
service.py: casos de uso
        ↓
engine.py: execução e supervisão
        ↓
SQLAlchemy + Job Objects: persistência e processos
```

Fechar a janela não altera o motor usado pela CLI ou pelo Agendador. O Flet é cliente do núcleo, não seu supervisor obrigatório.

## Onde ajustar o visual

Os ajustes ficam em `src/rpa_control_center/ui.py`:

- `ControlCenterUI.__init__`: textos, campos, tabelas, alturas de linha e espaçamentos.
- `ControlCenterUI.build`: ordem dos blocos, cartões, bordas, preenchimento e layout responsivo.
- `robots_card`, `history_card` e `logs_card`: cada painel ocupa 12 colunas em janela menor. Em telas `XL`, usam respectivamente 5, 4 e 3 colunas, ficando lado a lado.
- As áreas de automações, histórico e logs possuem rolagem vertical e horizontal próprias quando o conteúdo excede o espaço disponível.
- `main`: tema, cor de fundo, tamanho inicial e modo claro/escuro.

Alterações de cor, padding, borda, tamanho de texto e espaçamento são ajustes de baixo risco. Depois delas, abrir a janela restaurada e maximizada continua sendo a validação necessária. Mudanças em callbacks, serviços, banco ou motor não são apenas visuais e devem manter os testes automatizados.

### Ajustes de baixo risco

- cores;
- tamanhos de texto;
- `padding`;
- `spacing`;
- bordas e raios dos cartões;
- altura dos painéis;
- ordem dos cartões;
- tamanho inicial da janela;
- proporção das colunas do `ResponsiveRow`.

Depois de qualquer ajuste, conferir a janela restaurada e maximizada, com escala de tela normal e ampliada quando possível.

### Áreas que exigem revisão técnica

- callbacks como `save_robot`, `edit_handler`, `toggle_robot_handler`, `execute_queue`, `confirm_remove_robot` e `confirm_remove_run`;
- cores dos indicadores em `STATE_COLORS` e composição em `status_badge`;
- execução individual em `execute_now_handler`, que preserva a fila sequencial;
- consultas e transações do banco;
- cancelamento e timeout;
- atualização periódica dos logs;
- integração com o motor;
- tratamento de caminhos e argumentos;
- regras de estado de botões e execuções.

Esses pontos alteram comportamento e devem preservar os testes automatizados.

### Decisões visuais atuais

- **Marca:** Zanella Orchestrator Community Edition, com o símbolo Z-Flow no cabeçalho e no futuro executável.
- **Tema:** escuro por padrão, com alternância para o tema claro pelo botão no cabeçalho.
- **Fonte da interface:** Inter, incorporada localmente em `assets/fonts` para funcionar sem internet.
- **Fonte dos logs:** JetBrains Mono, também incorporada ao aplicativo.
- **Cores principais:** azul cobalto `#2563EB`, ciano `#06B6D4` e fundo Deep Slate `#0F172A`.
- **Cores semânticas:** verde `#10B981` para sucesso, vermelho `#E11D48` para falha e âmbar `#F59E0B` para atenção.
- **Cartões e tabelas:** usam cores semânticas do tema Flet para conservar contraste nos modos claro e escuro.
- **Logo:** carregada como bytes no controle visual, evitando dependência do diretório atual. `assets/icon.png` será usado pelo `flet build` como ícone do Windows.

### Como localizar mesmo após mudanças de linha

Pesquisar por estes símbolos em `ui.py`:

- `ControlCenterUI.__init__`: controles, tabelas e valores iniciais;
- `ControlCenterUI.build`: composição visual completa;
- `registration`: formulário de cadastro;
- `robots_card`: painel de automações;
- `history_card` e `logs_card`: histórico e logs;
- `activity_card`: agrupamento da coluna direita;
- `ft.ResponsiveRow`: comportamento restaurado e maximizado;
- `main`: tema, fundo e dimensões da janela.
