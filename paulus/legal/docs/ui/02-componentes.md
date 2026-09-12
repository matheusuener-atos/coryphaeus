# 02 — Componentes

Inventário fechado. Se uma tela precisar de algo que não está aqui, ou ela está
errada ou o inventário cresce por decisão explícita — não por improviso local.

Os valores abaixo são os do desenho aprovado. As medidas de celular (alvo 44px,
raio maior) estão marcadas onde diferem.

---

## Botão

Quatro tipos, um só formato.

| Tipo | Fundo | Borda | Texto |
|---|---|---|---|
| Primário | `--ink` | — | `--bg`, peso 600 |
| Secundário | transparente | `1px solid var(--ink-a15)` | `--ink`, peso 500 |
| Fantasma | transparente | — | `--ink2`, peso 500 |
| Destrutivo | transparente | `1px solid var(--accln)` | `--acc`, peso 500 |

Desktop: altura 32px (`36px` quando é a ação principal da tela), respiro
`8px 14px`, raio 8px, 13px, intervalo 6px entre ícone (18px) e rótulo.
Celular: altura mínima 44px, respiro `10px 16px`, raio 10px, 14px.
Miúdo (dentro de cartão e de linha): altura 36px, respiro `6px 12px`, raio 8px, 13px.

Passagem do mouse: primário vai a `--ink0`; os demais ganham fundo `--fill2`.
Foco de teclado: `outline: 2px solid var(--acc); outline-offset: 2px`.
Desligado: `opacity:.4; pointer-events:none`.

**Botão de ícone:** quadrado de 40px (44px no celular), raio 8/10px, ícone 22px,
cor `--ink`, fundo `--fill2` na passagem do mouse. Sempre com `aria-label` e
`title` — o app é cheio deles.

**Botão flutuante (só celular):** `position:absolute; right:16px; bottom:96px`,
altura 48px, respiro `0 18px 0 14px`, raio 14px, fundo `--ink`, texto `--bg`
14px/600, ícone 20px, sombra `--elev-float`.

## Campo

Altura 40px no desktop, 46px no celular. Respiro `10px 14px`, borda
`1px solid var(--ink-a15)`, raio 10px, fundo `--surf`, 14–15px.
Com foco: borda `1px solid var(--ink)` — sem halo colorido, sem sombra.
Ícone à esquerda 20px, cor `--ink3`. Texto de exemplo em `--ink3`.

**Campo com rótulo:** grade de 6px — rótulo 12px/500 `--ink3`, campo, e ajuda
opcional 12px `--ink3` com `line-height:1.5`.

**Erro:** borda `--acc`, e a mensagem abaixo em 12px `--acc`. Nunca vermelho
puro, nunca ícone de alerta piscando.

**Área de texto:** mesmo tratamento, altura mínima 96px, `resize: vertical`.

## Interruptor, caixa de seleção, opção

- **Interruptor:** 40×24, raio 12. Ligado: fundo `--ink`, botão 18px `--bg` a
  3px da direita. Desligado: borda `1px solid var(--ink-a25)`, botão 18px
  `--ink-a3` a 2px da esquerda. Linha inteira com altura mínima 44px, rótulo à
  esquerda (`--ink` quando ligado, `--ink2` quando não), subtítulo 12px `--ink3`.
- **Caixa de seleção:** 20×20, raio 5. Marcada: fundo `--ink`, ícone `check` 14px
  em `--bg`. Desmarcada: borda `1.5px solid var(--ink-a3)`.
- **Opção (radio):** 20×20, raio 50%. Marcada: `border: 6px solid var(--ink)`.
  Desmarcada: `border: 1.5px solid var(--ink-a3)`.

## Seletor de visões (segmented)

É a peça central da nova navegação: o que era tela virou visão.

Fundo `--fill`, raio 10px, respiro 3px, intervalo 2px. Cada item: respiro
`8px 6px` (desktop `6px 14px`), raio 8px, 13px. Ativo: fundo `--surf`, peso 600,
cor `--ink`, sombra `0 1px 2px var(--sh-a12)`. Inativo: peso 500, `--ink2`.

No celular ocupa a largura toda, com `flex:1` por item e reticências.

## Chips (filtros)

Altura 30px, respiro `7px 12px`, raio 999px, 13px. Ativo: fundo `--ink`, texto
`--bg`, peso 600. Inativo: borda `1px solid var(--ink-a15)`, texto `--ink`,
peso 500. Rolam na horizontal no celular, sangrando 16px para fora do respiro
da tela.

## Etiqueta (pílula)

Respiro `2px 8px`, raio 5px, 11.5px/600, sem quebra. Cores por significado:

| Significado | Fundo | Texto |
|---|---|---|
| Neutro | `--fill` | `--ink2` |
| Concluído / em dia | `--okbg` | `--okt` |
| Atenção / aguardando | `--warnbg` | `--warnt` |
| Prazo / atraso / pendência | `--accbg` | `--acc` |

## Cartão

Borda `1px solid var(--ink-a1)`, raio 12px (14px no celular), fundo `--surf`,
sombra `--elev-card`, respiro 14–16px. Cabeça do cartão: título 15px/600 à
esquerda, apoio 12.5px `--ink3` à direita, na mesma linha de base.

Cartões lado a lado usam grade com `minmax(0,1fr)` — nunca `1fr` puro, senão o
conteúdo longo estoura a coluna.

## Tabela

Não é `<table>` com larguras automáticas: é grade CSS com colunas declaradas,
para que todas as linhas fiquem alinhadas. As colunas de cada tela estão em
`03-telas-desktop.md`.

- Cabeçalho: altura 36px, fundo `--sub`, 11.5px/600 `--ink3`, borda inferior
  `--ink-a1`, grudado no topo ao rolar.
- Linha: altura 40px, borda inferior `--ink-a06`, 13px. Passagem do mouse:
  fundo `--fill`. Selecionada: fundo `--fill2`.
- Última coluna: 28px, para o menu da linha (`more_horiz`), que aparece na
  passagem do mouse.
- Números: à direita, `tabular-nums`. Datas: 12.5px `--ink3`.
- Seleção: caixa de 20px na primeira coluna; ao marcar, a barra de seleção
  substitui o cabeçalho da tabela, com a contagem e as ações em lote.

## Linha de lista (celular e painéis)

Altura mínima 56px, respiro `10px 14px`, borda inferior `--ink-a06`, intervalo
12px. Elemento à esquerda (avatar, glifo, ícone), título 14px/600 com
reticências, subtítulo 12px `--ink3`, valor à direita, `chevron_right` 18px
`--ink3`.

## Par chave-valor

Altura mínima 40px, borda inferior `--ink-a06`. Chave `--ink2` 14px à esquerda;
valor 13px/600 à direita, `tabular-nums`. É o formato de toda ficha: cliente,
documento, certificado, lançamento.

## Avatar

Círculo de 28px (desktop) ou 32px (celular), fundo `--fill`, iniciais em
peso 700, tamanho = um terço do diâmetro, cor `--ink2`. Sem foto por padrão;
com foto, mesmo círculo e `object-fit: cover`.

## Glifo de arquivo

Quadrado 22px, raio 5px, texto branco 800. PDF `oklch(58% 0.19 35)` com "PDF"
em 7px; Word `oklch(48% 0.14 255)` com "W" em 11px; Excel `oklch(50% 0.13 150)`
com "X" em 11px.

## Citação

Âncora numerada dentro do texto do assistente: largura mínima 18px, altura 18px,
respiro lateral 5px, raio 5px, fundo `--accbg`, texto `--acc`, Fira Code
10.5px/500, `vertical-align: 2px`. Clicar abre o trecho no painel, com o
documento, a página e o texto exato — a origem é sempre visível.

## Indicador "trabalhando"

Ponto de 6px em `--okt` com `pv-pulse`, seguido de rótulo em Fira Code 10.5px,
`letter-spacing:.1em`. No trilho, o mesmo estado aparece como anel girando ao
redor do logo. Nunca use barra indeterminada.

## Caixa de pedido (composer)

A peça mais usada do produto.

Desktop: largura máxima 760px centralizada, borda `1px solid var(--ink-a15)`,
raio 16px, fundo `--surf`, sombra `0 8px 30px -18px var(--sh-a35)`, respiro
`12px 12px 10px`. Dentro: linha do texto (15px, cursor `pv-caret`) e, abaixo,
a linha de ações — anexar (36px), etiqueta de contexto ("pasta X"), espaço,
microfone (36px) e o botão de envio: círculo de 36px, fundo `--ink`, ícone
`arrow_upward` 18px em `--bg`.

Celular: mesma peça, largura cheia, fixa acima da barra inferior.

## Diálogo

Largura 420–520px conforme o conteúdo (renomear 440; mover 460; excluir 480;
compartilhar 520). Fundo `--surf`, raio 14px, sombra `--elev-float`, respiro
20–24px, véu `rgba(0,0,0,.35)`.

- Título em Garamond 20px + contexto ("onde estou") em 12.5px `--ink3`.
- Campo com foco preto; a extensão do arquivo fica **fora** do campo, à direita,
  em `--ink3` — não se renomeia a extensão sem querer.
- Ações à direita: primária à direita de tudo, "Cancelar" como texto.
  Destrutiva em vinho, com o efeito escrito ("vai para a lixeira por 30 dias",
  "3 citações deixam de apontar para este arquivo").
- Enter confirma, Esc fecha, foco inicial no campo, foco preso no diálogo.

## Aviso (toast)

Canto inferior direito no desktop, acima da barra inferior no celular. Fundo
`--ink`, texto `--bg`, raio 10px, respiro `10px 14px`, 13px, sombra
`--elev-float`, 6 segundos. Sempre com "Desfazer" à direita em peso 600 quando
a ação é reversível. Conflito de nome é aviso, não diálogo: "já existe um
arquivo com esse nome — renomeei para (2)", com Desfazer.

## Folha (só celular)

Sobe de baixo: raio `24px 24px 0 0`, fundo `--surf`, respiro `10px 16px 28px`,
alça de 40×4px em `--ink-a15` centralizada, título Garamond 20px, sombra
`0 -20px 60px -20px var(--sh-a35)`, véu `rgba(0,0,0,.35)`. Substitui o painel
direito do desktop.

## Barra inferior (só celular)

Cinco destinos: Assistente, Serviços, Agenda, Acervo, Mais. Borda superior
`--ink-a1`, fundo `--bg`, respiro `6px 6px 22px` (a base é a área segura),
sombra `0 -6px 24px -12px var(--sh-a12)`. Item: ícone 24px (`FILL 1` quando
ativo), rótulo 10.5px (700 ativo, 500 inativo), cor `--ink` ou `--ink3`.
Pendência em "Mais": ponto de 8px em `--acc` com borda de 2px em `--bg`.
