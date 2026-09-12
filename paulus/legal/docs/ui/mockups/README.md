# PAULUS Legal — desenho de interface

Pacote de entrega: a especificação escrita e os mockups que ela descreve.

```
entrega-paulus-ui/
├── docs/ui/          especificação (copiar para paulus/legal/docs/ui/)
│   ├── README.md                  índice, mapa mockup→tela, regras do sistema
│   ├── 00-fundamentos.md          cor, tipografia, espaçamento, raio, ícone, movimento
│   ├── 01-shell.md                barra de título, trilho, menu, painel, tema
│   ├── 02-componentes.md          inventário fechado, com CSS exato
│   ├── 03-telas-desktop.md        A0a–A16, visão a visão
│   ├── 04-telas-mobile.md         M0–M14 e as regras de adaptação
│   ├── 05-interacoes-e-estados.md diálogos, avisos, vazio/carregando/erro, teclado
│   └── 06-ordem-de-implantacao.md fases, dados por tela, critérios de aceite
└── mockups/          37 telas em HTML, abrem direto no navegador
    ├── PAULUS Legal - Mockups.dc.html   ← comece por aqui: todas as telas juntas
    ├── A0a … A16                        desktop, 1440×900
    ├── M0 … M16                         celular, 390×844
    ├── P - Popups                       diálogos e avisos
    ├── Plataforma                       página pública de download e apoio
    ├── support.js                       runtime dos mockups
    └── assets/                          logo
```

## Como abrir

Abra `mockups/PAULUS Legal - Mockups.dc.html` no navegador. Ele reúne as 37
telas em um quadro só, com o contexto de cada uma e o botão de alternar tema no
canto superior direito. Cada arquivo também abre sozinho.

Os mockups precisam estar todos na mesma pasta: um importa o outro por nome,
e todos usam `support.js` e `assets/`.

## O que estes arquivos são

Referência de desenho. Foram escritos com estilo em linha para ler rápido, não
para virar produção. A implantação recria este desenho na interface que já
existe (`paulus/legal/frontend/`), com as variáveis CSS de
`docs/ui/00-fundamentos.md`.

Nada aqui propõe stack, framework ou mudança de arquitetura.

## Por onde começar a implantar

`docs/ui/06-ordem-de-implantacao.md`. Fase 0 é fundamento e casca; fase 1 é
Assistente → Acervo → Aprovações, que é a demonstração inteira do produto.
