# 01 — Casca (shell)

A casca é igual em todas as telas do desktop, de A1 a A16. Muda só o conteúdo da
área central e do painel direito. Implantar uma vez, reutilizar sempre.

```
┌────────────────────────────────────────────────────────────────┐
│ barra de título · 36px                                         │
├──────┬─────────────────────────────────────────┬───────────────┤
│      │ cabeçalho de página · 52px              │               │
│ tri- ├─────────────────────────────────────────┤ painel        │
│ lho  │ barra de ferramentas · 52px (opcional)  │ direito       │
│ 64px ├─────────────────────────────────────────┤ 320–400px     │
│      │ conteúdo (rola)                         │ (rola)        │
│      ├─────────────────────────────────────────┤               │
│      │ rodapé de garantia · 32px (opcional)    │               │
└──────┴─────────────────────────────────────────┴───────────────┘
```

## Barra de título

Altura 36px, fundo `--bg`, borda inferior `1px solid var(--ink-a1)`.
A janela é sem moldura (pywebview `frameless`), então esta barra é a área de
arrasto: `-webkit-app-region: drag` nela, `no-drag` nos botões.

- Esquerda: logo 16×16, raio 4, `filter: var(--logo)`; ao lado, "PAULUS Legal"
  em 12px, cor `--ink2`. Recuo esquerdo 12px, intervalo 8px.
- Direita: três botões de 46px de largura e altura cheia, ícones `remove` (16),
  `crop_square` (14), `close` (16). Passagem do mouse: fundo `--ink-a06`; no
  fechar, fundo `#c42b1c` e ícone `--surf`.

## Trilho (estado padrão)

Largura 64px, fundo `--bg`, borda direita `1px solid var(--ink-a1)`, sombra
`4px 0 16px -8px var(--sh-a12)`, `z-index:2`. Respiro `12px 0 10px`, intervalo
2px, itens centralizados.

- Logo 30×30, raio 7, margem inferior 12px. Quando o assistente trabalha, um
  anel gira ao redor do logo (`pv-spin`) — é o único indicador global de trabalho.
- Item: 40×40, raio 8, ícone 22px, cor `--ink`. Passagem do mouse: fundo
  `--fill2`. Ativo: fundo `--act`.
- Divisórias: `28×1px`, `--ink-a12`, margem `5px 0`.
- Contador de pendência (Aprovações): topo 2px, direita 2px, altura 16px,
  largura mínima 16px, respiro lateral 4px, raio 8px, fundo `--acc`, texto
  `--surf` 10px/700.
- Rodapé do trilho, na ordem: `favorite` (cor `--acc`), alternar tema,
  `settings`, avatar 28px redondo com iniciais 11px/700 sobre `--fill2`.

Ordem dos destinos, separada por divisórias:

1. `add` Nova conversa
2. `forum` Assistente · `work` Serviços · `mic` Gravações · `calendar_month` Agenda · `self_improvement` Foco e bem-estar
3. `inventory_2` Acervo · `description` Documentos · `draw` Assinatura
4. `mail` E-mail · `payments` Financeiro · `contacts` Cadastros · `verified` Aprovações

## Menu (sobreposto)

Não existe botão de expandir. Passar o mouse sobre o trilho abre o menu de
260px **por cima** do conteúdo, sem deslocar a tela; sair dele fecha.
`onMouseEnter` no trilho abre, `onMouseLeave` no menu fecha.

Largura 260px, `box-sizing:border-box`, fundo `--bg`, borda direita
`1px solid var(--ink-a1)`, sombra `18px 0 40px -30px var(--sh-a45)`, respiro
`12px 12px 10px`, intervalo 2px.

- Cabeça: logo 30×30 raio 7 + "PAVLVS" em Garamond 20px/500, intervalo 10px,
  altura 30px, margem inferior 12px, recuo esquerdo 5px.
- Item: altura 40px, raio 8; caixa de ícone 40×40 fixa (assim o ícone fica
  exatamente sobre o do trilho quando o menu abre); rótulo 13px/500, 600 quando
  ativo, `text-overflow: ellipsis`, respiro direito 12px.
- Divisória: `height:1px`, `--ink-a12`, margem `5px 6px`.
- Fim da lista: Recentes (últimas conversas, 12.5px, cor `--ink2`) e a nota
  "Software livre".

Há um estado fixo (`sidebar="expanded"`) usado no mockup 3d: o menu ocupa a
coluna e empurra o conteúdo, com um espaçador de 260px no lugar do trilho. É
estado de demonstração; na implantação, o comportamento padrão é o sobreposto.

## Cabeçalho de página

Altura 52px, respiro lateral 20px, borda inferior `1px solid var(--ink-a1)`.

- Esquerda: título em Garamond 22px, `letter-spacing:-.01em`. Abaixo ou ao lado,
  o contexto em 12.5px `--ink3` ("42 clientes · 6 colaboradores · 2 sócios").
- Centro ou direita: o **seletor de visões** (ver `02-componentes.md`), que é o
  que substitui as 26 telas antigas por 11 destinos.
- Direita: ações da tela. No máximo uma primária; o resto é secundário ou vira
  botão de ícone. Botão com menu usa sufixo "▾" no rótulo ("Novo ▾").

## Painel direito

Largura 320px (Assistente) a 400px (Acervo, Documentos, Assinatura). Fundo
`--surf`, borda esquerda `1px solid var(--ink-a1)`, respiro 16px, rola sozinho.

- Telas com alça de redimensionamento: A4, A5, A6, A7 (faixa de 4px na borda,
  cursor `col-resize`, limites 280–520px, valor guardado por tela).
- Telas de coluna fixa, sem alça: A9, A11, A12.
- Quando o painel rola, sombra de 1px no topo e na base da área rolável.
- O painel nunca é obrigatório: em janela menor que 1240px ele recolhe para uma
  gaveta aberta por botão de ícone no cabeçalho.

Colunas auxiliares à esquerda do conteúdo (árvore de pastas no Acervo, contas e
pastas no E-mail, abas de documentos) têm 220–260px e a mesma borda.

## Rodapé de garantia

Faixa de 32px, fundo `--bg`, borda superior `--ink-a06`, texto 11.5px `--ink3`,
recuo 20px. Aparece nas telas que usam IA e traz uma frase fixa:

- Assistente: "nenhuma requisição à internet"
- Gravações: áudio, transcrição e resumo ficam nesta máquina
- Foco: tudo calculado só com uso local; nada é compartilhado
- Celular: a IA roda na máquina do escritório; este aparelho fala com ela pela
  rede local

Não é decoração. É o argumento de venda do produto, repetido onde a dúvida
aparece.

## Tema

Um botão no rodapé do trilho (`dark_mode` / `light_mode`) alterna
`data-tema="claro" | "escuro"` no elemento raiz e grava a escolha. Só o conjunto
de variáveis muda; nenhuma regra de componente conhece o tema. A logo é
invertida por `filter`, conforme `00-fundamentos.md`.

No celular, o mesmo botão vive no cabeçalho do Assistente e na lista "Mais".

## Modo limitado (vínculo pendente)

Quando a pessoa entrou com código e o responsável ainda não validou, a casca
continua inteira, mas os destinos que dependem da rede ficam a `opacity:.4` e
`pointer-events:none`: Serviços, Gravações, Agenda, Acervo, E-mail, Financeiro,
Cadastros, Aprovações. Seguem livres: Assistente, Documentos, Assinatura, Foco,
Configurações, Apoiar.

O Assistente exibe, no lugar de "Acontecendo agora", o cartão de espera com o
código da pessoa e o que ela já pode fazer. Ver A0b em `03-telas-desktop.md`.
