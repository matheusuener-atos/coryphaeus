# 00 — Fundamentos

## Cor

Tudo é variável CSS. O valor do tema claro é o padrão, declarado em `:root`; o
tema escuro sobrescreve o mesmo nome em `[data-tema="escuro"]`. Nenhum
componente conhece cor literal — só o nome da variável.

### Neutros

| Variável | Claro | Escuro | Uso |
|---|---|---|---|
| `--bg` | `#f6f6f4` | `#141413` | Fundo da janela, trilho, menu |
| `--surf` | `#ffffff` | `#1c1c1b` | Cartão, painel, campo, linha ativa |
| `--sub` | `#fafaf9` | `#202020` | Fundo de cabeçalho de tabela, faixa secundária |
| `--paper` | `#fbfaf6` | `#232322` | Folha do editor e da pré-visualização |
| `--fill` | `#f1f1ee` | `#262625` | Preenchimento fraco: etiqueta, seletor, avatar |
| `--fill2` | `#ebebe8` | `#2c2c2a` | Preenchimento em passagem do mouse |
| `--act` | `#e6e6e2` | `#343432` | Item ativo do trilho e do menu |
| `--ink` | `#171716` | `#f0f0ec` | Texto principal, botão primário |
| `--ink2` | `#5c5c59` | `#b3b3ae` | Texto secundário |
| `--ink3` | `#8a8a86` | `#8f8f8a` | Texto de apoio, unidade, data |
| `--mute` | `#c9c9c4` | `#5a5a57` | Traço de grade, ícone desligado |
| `--mute2` | `#a3a39f` | `#6f6f6b` | Traço médio |
| `--ink0` | `#000000` | `#ffffff` | Passagem do mouse no botão primário |
| `--btn` / `--btnt` | `#171716` / `#f6f6f4` | invertidos | Botão primário e seu texto |

### Linhas e véus

Derivados de `rgba(23,23,22,α)` no claro e `rgba(246,246,244,α)` no escuro.

`--ink-a06` `.06` · `--ink-a08` `.08` · `--ink-a1` `.1` · `--ink-a12` `.12` ·
`--ink-a15` `.15` · `--ink-a2` `.2` · `--ink-a25` `.25` · `--ink-a28` `.28` ·
`--ink-a3` `.3` · `--ink-a35` `.35`

Regra prática: divisória interna `--ink-a06`; borda de cartão e de painel
`--ink-a1`; borda de campo e de botão secundário `--ink-a15`; caixa de seleção
e botão de opção desmarcados `--ink-a3`.

### Sombras

No claro são `rgba(23,23,22,α)`; no escuro vão a preto quase sólido, porque
sombra clara sobre fundo escuro suja.

| Variável | Claro | Escuro |
|---|---|---|
| `--sh-a12` | `rgba(23,23,22,.12)` | `rgba(0,0,0,.45)` |
| `--sh-a35` | `rgba(23,23,22,.35)` | `rgba(0,0,0,.77)` |
| `--sh-a45` | `rgba(23,23,22,.45)` | `rgba(0,0,0,.99)` |
| `--sh-a5` / `--sh-a6` | `.5` / `.6` | `rgba(0,0,0,1)` |

Três sombras em uso, e só três:

```css
--elev-card:  0 8px 24px -16px var(--sh-a12);   /* cartão */
--elev-panel: 18px 0 40px -30px var(--sh-a45);  /* menu sobreposto */
--elev-float: 0 14px 30px -12px var(--sh-a35);  /* diálogo, folha, botão flutuante */
```

### Acento (vinho) e semânticos

Acento é vinho, sempre em oklch, nunca em hex. Serve a: prazo, atraso, ação
destrutiva, citação, contador de pendência, "Apoiar".

| Variável | Claro | Escuro |
|---|---|---|
| `--acc` | `oklch(42% 0.13 25)` | `oklch(74% 0.12 25)` |
| `--accbg` | `oklch(95% 0.02 25)` | `oklch(27% 0.05 25)` |
| `--accbg2` | `oklch(97.5% 0.01 25)` | `oklch(22% 0.03 25)` |
| `--accbg3` | `oklch(98.5% 0.005 25)` | `#1f1d1c` |
| `--accln` | `oklch(80% 0.06 25)` | `oklch(40% 0.08 25)` |
| `--accln2` | `oklch(70% 0.1 25)` | `oklch(50% 0.1 25)` |
| `--okt` (texto ok) | `oklch(38% 0.1 150)` | `oklch(78% 0.12 150)` |
| `--okbg` | `oklch(95% 0.03 150)` | `oklch(28% 0.05 150)` |
| `--warnt` | `oklch(45% 0.1 70)` | `oklch(82% 0.12 80)` |
| `--warnbg` | `oklch(96% 0.05 85)` | `oklch(30% 0.06 85)` |

Pontos cheios (bolinha de estado, barra de gráfico), iguais nos dois temas:
verde `oklch(60% 0.15 150)`, âmbar `oklch(75% 0.15 80)`.

Formatos de arquivo, também iguais nos dois temas:
PDF `oklch(58% 0.19 35)` · Word `oklch(48% 0.14 255)` · Excel `oklch(50% 0.13 150)`.

Fechar janela em passagem do mouse: `#c42b1c` (padrão do Windows), com texto
branco. Único hex fora do sistema, e é de propósito.

### Logo no escuro

Não existe segundo arquivo. `--logo: none` no claro e
`--logo: invert(1) hue-rotate(180deg)` no escuro, aplicado como `filter` na
`<img>` do logo. Vale para trilho, menu, barra de título, papel timbrado e selo.

## Tipografia

Três famílias, carregadas do Google Fonts hoje; na implantação, empacotar como
`.woff2` local — o aplicativo roda sem internet.

| Família | Pesos | Onde |
|---|---|---|
| **EB Garamond** | 400, 500, itálico 400 | Título de tela, título de diálogo, saudação, nome de documento no editor, papel timbrado |
| **Manrope** | 400, 500, 600, 700, 800 | Todo o resto |
| **Fira Code** | 400, 500 | Número de citação, código de vínculo, série de certificado, carimbo de tempo, rótulo técnico com `letter-spacing:.1em` |

Nada de fonte de sistema como primeira opção; ela entra só como reserva:
`'Manrope', system-ui, sans-serif` · `'EB Garamond', Georgia, serif` ·
`'Fira Code', ui-monospace, monospace`.

### Escala (desktop)

| Papel | Tamanho | Peso | Família |
|---|---|---|---|
| Título de tela | 22px, `letter-spacing:-.01em` | 400/500 | Garamond |
| Saudação do Assistente | 30–34px | 400 | Garamond |
| Título de cartão | 15px | 600 | Manrope |
| Título de seção | 13px | 600 | Manrope |
| Corpo | 14px, `line-height:1.5` | 400 | Manrope |
| Item de menu / linha de tabela | 13px | 500 (600 quando ativo) | Manrope |
| Apoio, data, unidade | 12.5px | 500 | Manrope, cor `--ink3` |
| Etiqueta e contador | 11.5px | 600 | Manrope |
| Rótulo técnico | 10.5px, `letter-spacing:.1em` | 500 | Fira Code |
| Número grande (Financeiro, Foco) | 28–34px, `font-variant-numeric: tabular-nums` | 600 | Manrope |

Todo número que aparece em coluna, em tabela ou em comparação usa
`font-variant-numeric: tabular-nums`. Sem exceção — valor que dança entre linhas
é o defeito visual mais visível do app atual.

## Espaçamento

Base 4. Valores em uso: 2 · 4 · 6 · 8 · 10 · 12 · 14 · 16 · 20 · 24 · 28 · 32.

- Respiro interno de cartão: 14–16px; de painel: 16px; de diálogo: 20–24px.
- Distância entre cartões: 12px (denso) ou 16px (padrão).
- Distância entre rótulo e campo: 6px. Entre campos: 12px.
- Faixa lateral do conteúdo em 1440: 20–24px.

## Raio

`4px` etiqueta pequena · `5px` pílula e glifo de arquivo · `8px` botão, item de
menu, campo pequeno · `10px` campo, cartão pequeno, seletor (`--rp`, `--rg`) ·
`12–14px` cartão · `16px` caixa de pedido · `24px` folha de celular ·
`999px` chip redondo · `50%` avatar e ponto.

## Ícones

Material Symbols Outlined, eixos `opsz 20..24, wght 300..400, FILL 0..1, GRAD 0`,
`display=block`. Nunca emoji, nunca desenho vetorial próprio fora do logo e do
selo de assinatura.

Todo ícone é quadrado e recortado, para não empurrar o texto enquanto a fonte
carrega:

```css
.ic{font-family:'Material Symbols Outlined';font-weight:300;font-size:22px;
    line-height:1;display:block;width:22px;height:22px;overflow:hidden;flex:none}
```

Tamanhos: 14 (dentro de caixa de seleção), 16 (barra de título, apoio),
18 (botão, linha de tabela), 20 (campo), 22 (trilho, menu, botão de ícone),
24 (barra inferior do celular).

Ícone por destino, fixo no sistema inteiro:
`forum` Assistente · `work` Serviços · `mic` Gravações · `calendar_month` Agenda ·
`self_improvement` Foco · `inventory_2` Acervo · `description` Documentos ·
`draw` Assinatura · `mail` E-mail · `payments` Financeiro · `contacts` Cadastros ·
`verified` Aprovações · `settings` Configurações · `favorite` Apoiar ·
`add` Nova conversa · `grid_view` Mais (celular).

## Movimento

Quatro animações no sistema inteiro, todas já nomeadas nos mockups:

```css
@keyframes pv-pulse{0%,100%{opacity:.35}50%{opacity:1}}   /* ponto "trabalhando" */
@keyframes pv-spin {to{transform:rotate(360deg)}}          /* anel no logo */
@keyframes pv-caret{0%,45%{opacity:1}50%,95%{opacity:.1}100%{opacity:1}} /* cursor */
@keyframes pv-grow {from{width:0}to{width:64%}}            /* barra de progresso */
```

Transição padrão: `.18s ease` para cor e fundo; `.25s ease` para tema.
Menu sobreposto abre em `.15s`. Nada acima de `.3s`. Respeitar
`prefers-reduced-motion: reduce` desligando `pv-spin` e `pv-grow`.

## Barras de rolagem

Ocultas em todo o aplicativo, inclusive no escuro:

```css
*{scrollbar-width:none} *::-webkit-scrollbar{width:0;height:0;display:none}
```

Onde há rolagem, ela é sinalizada por sombra de borda no topo/base da área, não
por barra. Regra herdada do desenho: a janela não deve parecer um site.

## Links

`a{color:oklch(42% 0.13 25)}` e `a:hover{color:oklch(36% 0.13 25)}` no claro; no
escuro o acento já vira `oklch(74% 0.12 25)`. Link de navegação interna (trilho,
menu, linha de tabela) não é vinho: herda `--ink` e não sublinha.

## Densidade e limites

- A tela de referência é **1440×900**. Tudo cabe sem rolagem da página: só o
  painel direito e as listas rolam.
- Altura de linha de tabela: 40px. Altura de barra de ferramentas: 52px.
- Alvo de clique mínimo no desktop: 28px; no celular: 44px.
- Contraste mínimo: 4.5:1 para texto, 3:1 para texto de 22px ou maior.
  `--ink3` sobre `--surf` é o limite inferior aceito; abaixo disso, não use.
