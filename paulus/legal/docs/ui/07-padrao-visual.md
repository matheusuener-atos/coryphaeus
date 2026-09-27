# 07 — Padrão visual aplicado (26/09/2026)

O CSS de `frontend/css` foi padronizado peça a peça: para cada papel
(botão, campo, linha de lista, cartão, etiqueta…) venceu **a versão mais usada
no sistema**, contada em regras de CSS e em emissões no JS. Este arquivo
registra o que venceu, onde a receita mora e o que ficou fora de propósito.
Onde a contagem empatou, decidiu `00-fundamentos.md`/`02-componentes.md`.

O inventário que serviu de base (147 espécimes, 493 versões, com o arquivo e a
linha de cada uma) está publicado como artefato "Inventário Visual PAULUS".

## Fundamentos

| Papel | Receita | Onde |
|---|---|---|
| Fio de cartão, painel, cabeçalho, rodapé, bloco e seção | `1px solid var(--ink-a1)` | em cada peça |
| Fio entre linhas de uma lista | `1px solid var(--ink-a08)`; a última sem fio | em cada lista |
| Fio de campo, busca, select, chip contornado | `1px solid var(--ink-a15)` | `04-acervo.css` (base do campo) |
| Fio de caixa de marcar, opção e interruptor | `--ink-a3` (1,5 px na caixa e na opção) | `04`, `14`, `09` |
| Tracejado (incluir, soltar, convite) | `1px dashed var(--ink-a15)`; hover `--ink-a35`; `.sobre` `--ink` | em cada peça |
| Sombra de cartão | `var(--elev-card)` em **todo** cartão e painel | `00-tokens.css` |
| Sombra do que flutua | `var(--elev-float)` (menu, diálogo, popover, alça, ir-ao-fim) | `00-tokens.css` |
| Sombra do papel | `var(--elev-papel)` (folha, página, prévia) | `00-tokens.css` |
| Raio | botão 8 · botão de ícone, item de menu/lista e pílula preenchida 6 · campo, busca, opção em cartão e popover 10 · cartão, painel e lista emoldurada 12 · caixa pequena 8 · zona de soltar 12 · etiqueta 5 · chip contornado e contador 999 · diálogo 16 | — |

Os tokens antigos saíram de `00-tokens.css`: `--hair`, `--hair2` e
`--elev-cartao` (hoje `--ink-a1`, `--ink-a08` e `--elev-card`), os apelidos
da primeira interface (`--linha`, `--surface-1`, `--acento`, `--forte`,
`--ok`, `--atencao`…), o segundo par verde e âmbar (`--grn`, `--amb`) e os
degraus de véu sem uso (`--ink-a28`, `--ink-a45`, `--ink-a5`, `--ink-a6`).

## Botões (`05-paineis-e-botoes.css`)

- **Texto** — uma base só: `500 12.5px`, `7px 13px`, raio 8, fio `--ink-a1`,
  fundo `--bg`, hover `--fill`. Dentro de cartão e de diálogo o fundo é
  `--surf` (uma regra `:where()` cobre os contêineres). Nenhuma tela redefine
  altura, recuo, raio ou letra; o que sobra nas telas é só layout
  (`display`, `gap`, `white-space`, `margin`).
- **Estados** — `.primario` (fundo `--casca`), `.perigo` (vinho no texto e no
  fio, hover `--accbg2`; vale também no rodapé do diálogo), `.sucesso` (par
  verde), `.fantasma` (sem fio nem fundo; engloba cancelar do diálogo, "ver
  mais", migalha e "ver" de linha).
- **Ligação** (botão que parece texto) — uma lista de seletores com a receita
  da `.sv-ligacao`: `500 13px`, `--ink2`, hover `--ink`, sem sublinhado;
  `.forte` e `.acc` são os únicos estados.
- **Ícone** — 28 px, raio 6, sem fundo em repouso, hover `--fill`, cor
  `--ink`; `.com-texto` para os de barra com rótulo.
- **Pílula preenchida** — 28 px, raio 6, `--fill`, hover `--fill2`
  (`.pilula`, recente, ir à página, atalhos de escrita, comandos).
- **Redondo** — 34 px (enviar, ditar, mais da agenda); o play do tocador
  fica em 40 e o ir-ao-fim em 36, com `--elev-float`.

## Campos (`04-acervo.css`)

- **Campo de texto e caixa de escolha** — `400 14px`, 40 px de altura,
  `0 12px`, fio `--ink-a15`, raio 10, fundo `--surf`; foco: fio `--ink`, sem
  halo. A caixa do diálogo, a senha, a anotação da agenda e o campo das contas
  de e-mail entraram nessa receita.
- **Área de texto** — a mesma, com 96 px de altura mínima e alça vertical.
  Só a caixa de pedido (`.cartao-campo textarea`) continua sem borda.
- **Compacto** (barra e linha) — 28 px, raio 6, 12.5 px. **Embutido** (campo
  nu dentro de linha ou chip) — 13.5 px, foco por fio embaixo em tinta.
- **Busca** — 34 px, fio `--ink-a15`, raio 10 (o do campo), lupa 18; uma
  regra só para `.busca-tela` e `.lc-busca`, que diferem só na largura.
- **Rótulo** — `500 12px` `--ink3`, em cima; ao lado só em tabela de
  formulário.
- **Caixa de escolha** = campo + seta (`melhorarSelect`); a escolha embutida
  (ordenar, ficha) é `600 12.5px` sem fio.

## Marcar (`04`, `14`, `09`, `17`)

- Caixa: `.marcar` 16 px, raio 4; marcada `--ink` com check 12 px. Caixas e
  opções nativas (onde o JS lê `.checked`): 16 px com `accent-color: --ink`.
- Opção (rádio): 16 px, borda 5 px quando marcada.
- Interruptor: 34×20, botão de 14 (`.ag-toggle` para a linha, `.interruptor-min`
  para a chave solta); o de 40×24 saiu.
- Círculo de concluir: 18 px; feito = `check_circle` em `--okt`.
- Opção em cartão: raio 10, fio `--ink-a1`; escolhida = fio `--ink` +
  `inset 0 0 0 1px`.

## Etiquetas, chips, glifos e avatares (`04`, `11`, `17`)

- **Etiqueta** — `.etiqueta`: `2px 8px`, raio 5, `600 11.5px`; cores por
  significado: neutro `--fill/--ink2`, ok `--okbg/--okt`, atenção
  `--warnbg/--warnt`, prazo/erro `--accbg/--acc`, forte `--ink/--bg`. Com
  ponto de estado: a mesma etiqueta com `<i>` de 6 px. Os cinco nomes
  antigos (`pill-papel`, `cad-pill`, `em-pilula`, `cfg-pill`, `selo-decisao`)
  e os selos em mono viraram `.etiqueta`.
- **Chip de filtro** — `.chip`: 30 px, 999, fio `--ink-a15`, `500 13px`;
  ligado `--ink`. **Chip de atalho** — 30 px, 999, `--fill`. **Chip de
  informação** (escopo, pasta, destinatário, anexo) — 28 px, raio 6, `--fill`.
- **Glifo** 20 px, raio 4. **Caixa de ícone** 32 px, raio 8, `--fill`.
- **Avatar** — `.cad-avatar` 32 px, `--fill2`, `700 11px`; escala 20→8,
  24→9, 40→13, 56→18. **Contador** 18 px, 999, `--destaque`.

## Listas e tabelas (`04-acervo.css`)

- **Linha** — `11px 16px`, 14 px, fio `--ink-a08`, hover `--sub`; selecionada
  `--fill` + fio de 3 px na tinta; aberta `--bg` + fio de 3 px `--ink`, sem
  fio embaixo. Recuo pelo `padding`, não pela margem.
- **Cabeçalho de coluna** — `500 12px` `--ink3`, fio `--ink-a1`, fundo do
  cartão (vale para a tabela em grade, a planilha e os dias da agenda).
- **Barra da tabela e barra de seleção** — 49 px, `--surf`, fio `--ink-a1`;
  solta, ganha fio e raio 12.
- **O que a linha revela** — `--bg`, fio `--ink-a08`, sem raio, abre por
  `abrirEmAltura` (260 ms) e fecha em 180 ms; nenhuma ficha anima por CSS.
- **Par chave-valor** — 34 px, `6px 0`, fio `--ink-a08`, valor `600 12.5px` à
  direita em 60 %. **Grade de ficha** (dt/dd) — 112 px, `9px 0`.
- **Rodapé** — `9px` de recuo, fio `--ink-a1`, `500 12.5px` `--ink3`.
- **Item de sumário lateral** — `8px 10px`, raio 6, `500 13.5px` `--ink2`,
  hover `--fill`, ativo `--fill` + 600.

## Cabeçalhos e títulos

- Título de página editorial: `400 30px` serif. Título de item/assunto:
  `400 20px` serif. Título de painel: `600 16px` sans (sem sobrescritas).
- Cabeçalho de cartão: `600 14px`, `12px 16px`, fio `--ink-a1`. Título de
  bloco: `600 14px`. Meta: `500 12.5px` `--ink3`.
- Rótulo técnico: `.rotulo` (mono 10.5, caixa alta, `.1em`). Rótulo de seção:
  `.sv-kicker` (sans `600 11px`, caixa alta, `.09em`). Nada fora dos dois.
- Número grande: sans `600 22px` (cartão) e `600 26px` (destaque), tabular.
- Vazio com título: `28px 18px`, título `600 15px`, texto 13.5 `--ink2`.
  Vazio de uma linha: `18px 14px`, 13 px `--ink3`.

## Navegação, cartões, pop-ups, estados, divisores

- Seletor de visões: `.visoes` (fundo `--fill` raio 8; item raio 6; ativo
  `--surf` + 600 + sombra de 1 px); as variantes só guardam layout.
- Painel lateral = cartão; blocos `12px 18px` com fio `--ink-a1`; entrada
  `pv-troca .46s`.
- Cartão: fio `--ink-a1`, raio 12, `--surf`, `--elev-card`; cabeça
  `12px 16px`; corpo `14px 16px`. Caixa pequena: fio `--ink-a1`, raio 8,
  `10px 12px`. Cartão de estado por significado: erro `--accln/--accbg2`;
  destaque `--destaque-linha/--destaque-fundo`; atenção `--warnbg/--warnt`;
  informativo `--fill` sem fio; aviso em tinta `--destaque`.
- Bolha da pessoa: `--fill`, raio 12, `10px 14px`, 13.5 px.
- Diálogo: 440 / 520 (`.larga`) / 760 (anexar e imprimir). Menu e popover:
  fio `--ink-a1`, raio 10, `--elev-float`, item `8px 10px` raio 6, entrada
  `menu-entra .16s`.
- Trabalhando: anel `.indicador` (20 px, 1,6 s) e pulso `pv-pulse 3,2 s`.
  Não há barra indeterminada: sem previsão, o cartão mostra o anel e o tempo;
  a barra aparece quando o servidor diz a previsão.
  Ponto de estado: 6 px, cor por significado. Barra de progresso: 4 px, raio
  2, trilho `--fill2`, andado `--ink`. Erro em linha: `500 12.5px` `--acc`.
- Divisa vertical: `.divisa-v` (1×18, `--ink-a15`). Risco horizontal:
  `1px --ink-a08`, `8px 0`.

## O que ficou de fora, de propósito

Trilho, menu e barra de título da casca (peças únicas, geometria casada);
diálogo (raio 16, título sans 17); botões da janela; bolhas de fala com o
canto assimétrico da conversa; papel do PDF e do editor (é papel); seleção
múltipla ao segurar o clique; a faixa de aviso (o desenho previa um toast que
nunca existiu, e não foi criado).

## Listas: seleção e menu (27/09/2026)

Uma forma só em todas as listas: Assistente, Gravações, Acervo, Assinatura, E-mail, Cadastros, Lançamentos, Tarefas, Serviços, Documentos e Aprovações.

- **Sem caixinha nas linhas.** Segurar a linha, ou Ctrl+clique, marca. Shift+clique marca o intervalo. A linha escolhida ganha a barra vertical à esquerda (`.escolhida`).
- **A barra de cima** (`barraDeSelecao`, em `js/16-selecao.js`) mostra a caixa, "N selecionadas" e as ações. A caixa é o "marcar todas / limpar": com parte marcada ela mostra o traço e marca todas, e com todas marcadas mostra o check e limpa. Não há "Selecionar todas" nem "Limpar" em texto. Esc limpa, Ctrl+A marca todas e Delete apaga.
- **Toda linha tem o "…"** (`.mais-linha` com o ícone `more_horiz`), e o menu sai pelo `menuNaLinha`.
- **Botão direito** numa linha abre o mesmo menu do "…", no ponto do clique. Isso fica no `16-selecao.js`, por delegação. Linha sem "…" fica com o menu do navegador.
- Caixinhas que são escolha dentro de um formulário continuam caixinhas. É o caso de anexar documentos, das pastas do Organizar e da equipe de um serviço.

O teste é `tests/test_listas.py`, que roda na base de demonstração.
