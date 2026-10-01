# PROGRESSO — O PAULUS dentro do Word

Retomada do plano do suplemento do Word (W0…W8). Uma conversa nova, com o
mesmo prompt, continua da primeira etapa que não estiver `feita`.

| Etapa | O quê | Estado | Commit | Portão (medido) |
| --- | --- | --- | --- | --- |
| W0 | Levantamento, prova de conceito das montagens e maquete do painel (⏸ escolha e visual) | ⏸ esperando o ok do dono (montagem e visual) | ver git log (w0) | A, B e C medidas no Word 2021 desta máquina; maquete com 19 telas × 3 temas × 2 larguras, 0 erro de página |
| W1 | Painel fiel à maquete, aba PAULUS, menu do botão direito, pareamento, política de rota e auditoria | pendente | — | — |
| W2 | Conferir as citações do documento (sem modelo) | pendente | — | — |
| W3 | Inserir lei, fundamentação e qualificação | pendente | — | — |
| W4 | Perguntar sobre o documento aberto | pendente | — | — |
| W5 | Revisar com um agente, em comentários | pendente | — | — |
| W6 | Guardar no PAULUS e instalação | pendente | — | — |
| W7 | Polimento e medida (matriz B.5, orçamentos B.4, acessibilidade, textos, desfazer) | pendente | — | — |
| W8 | Teste real (⏸ roteiro, com tema escuro e 150%) | pendente | — | — |

## Atualizações do contrato

- **01/10/2026 — atualização 1** (chegou durante a W0, antes da pausa):
  - o suplemento é o único caminho para o Word: nada de Word lado a lado,
    automação por COM ou editor embutido;
  - entra a seção "bem-feito" (B.1 presença no Word, B.2 aparência e estados,
    B.3 comportamento, B.4 orçamentos, B.5 matriz);
  - a W0 ganha a maquete navegável `word/prova/maquete.html` (320 e 480 px,
    claro e escuro, todos os estados, aba da faixa e menu do botão direito), e
    a pausa da W0 mostra as capturas; **esta pausa não pode ser pulada**;
  - a W1 faz o painel fiel à maquete aprovada, a aba "PAULUS" e o menu do
    botão direito; botão de etapa futura só desabilitado com "em breve", e só
    durante o trabalho;
  - entra a W7 nova (polimento e medida); o antigo teste real vira a W8, com
    o passo 10 (tema escuro e 150%).

## W0 — o que foi medido (01/10/2026)

Word desta máquina: **Office Professional Plus 2021 (volume), 16.0.14334.20918,
x64**, painel no **WebView2 154**. A prova está em `word/prova/`
(`pagina.html/js`, `servidor.py`, `certificado_local.py`, `montar.py`) e o
que a página relatou, em `word/prova/relatos-w0.jsonl`. O suplemento foi
carregado pelo registro de desenvolvedor (`HKCU\…\WEF\Developer`) e um .docx
que abre o painel sozinho; o Word só lê esse registro ao iniciar.

### As montagens

| Montagem | Word 2021 (Windows) | Medida | Word na web |
| --- | --- | --- | --- |
| **A** — página em `https://localhost`, certificado da instalação | **funcionou** | página pronta em ~0,5–1 s; `/api/status` no mesmo endereço em 4–8 ms; de `https://localhost` para `http://127.0.0.1` também (preflight passou) | não medido (exige login Microsoft); a medir pelo dono |
| **B** — página pública chamando `http://127.0.0.1` | **funcionou** | 9 ms; o WebView2 do Word não aplicou a regra de rede local (sem cabeçalho de rede privada, sem pergunta) | não medido; no Edge/Chrome atuais a página pública deve pedir permissão de "rede local" |
| **C** — página e chamadas pelo endereço público (túnel) | **funcionou** | 135 ms por chamada pelo túnel da Cloudflare (medido com um túnel rápido temporário, já fechado, apontando só para o servidor de prova) | deve funcionar (é um site HTTPS comum); não medido |

**Escolha proposta:** **A** no computador do escritório (nada sai da
máquina e o código do painel vem do próprio PAULUS) e **C** para o Word em
outro computador, no Word na web e no Mac. **B** não entra: funciona, mas põe
o site no caminho do código que vê o documento, e A já resolve o mesmo caso.

A montagem A pede, na W1: uma porta HTTPS **fixa** por instalação (o manifesto
leva o endereço; hoje a porta local é 8000 ou qualquer uma), CORS só para a
origem do painel e uma passagem no porteiro para o token do suplemento (hoje
só `/mcp` passa antes da chave da janela).

### O certificado da montagem A

- Autoridade própria **restrita por name constraints a `localhost` e
  `127.0.0.1`**; a chave dela **nunca é gravada**: emite o certificado do
  servidor e é descartada. Mesmo copiada, a pasta não emite certificado para
  outro nome. Validade de 825 dias; renovar = gerar outra e o Windows pergunta
  de novo.
- Entra em `CurrentUser\Root` **sem administrador**; o Windows mostra
  "Aviso de Segurança" e a pessoa clica em Sim. Instalado e conferido
  (impressão 1350…A535).
- Armadilha medida: `Import-Certificate` num processo sem janela respondeu
  "Interface do usuário não permitida" **mesmo com o certificado instalado**.
  Na W1, instalar a partir da janela do PAULUS e conferir lendo o repositório
  depois, nunca pelo retorno do comando.

### Conjuntos de API (medidos no Word 2021)

| Conjunto | Word 2021 | Para quê |
| --- | --- | --- |
| WordApi 1.1–1.3 | sim | ler, buscar (`search`), inserir, `insertOoxml`, `getOoxml` |
| WordApi 1.4+ (comentários, modo de alteração controlada) | **não** | — |
| WordApiDesktop | não | — |
| AddinCommands 1.1 | sim | a aba própria e o menu do botão direito pelo manifesto |
| AddinCommands 1.3, SharedRuntime 1.1, KeyboardShortcuts 1.1, RibbonApi, ContextMenuApi | **não** | atalhos de teclado e faixa dinâmica **não existem** neste Word |
| DialogApi 1.1 | sim | — |
| Tema (`officeTheme`) | sim | lido: fundo `#262626`, texto `#f0f0f0`, escuro |

**O achado que decide:** sem a 1.4, comentário e alteração controlada não
existem pela API, mas **pelo OOXML da 1.1 funcionam**: um pacote com
`<w:ins w:author="PAULUS">` entrou como alteração controlada (barra na
margem, aceitar/rejeitar no Word) e um com `commentRangeStart/End` +
`comments.xml` virou comentário de autor PAULUS (conferido na tela e no
`getOoxml`). Proposta:

- **mínimo exigido: WordApi 1.3** (Word 2021, 2024, Microsoft 365);
- com 1.4/1.6, usar comentário e alteração controlada nativos; sem, o
  caminho OOXML; com menos que 1.3, a tela "Word antigo" e nada mais;
- **atalhos de teclado só onde houver KeyboardShortcuts** (não no 2021); sem
  suporte, não aparecem;
- Word 2019 por volume usa o motor do Internet Explorer para suplementos: não
  suportado até ser medido; Word 2016 sem a 1.3: não suportado.

A conferir na W1/W7: se uma inserção por OOXML sai inteira com um Ctrl+Z, e
como ancorar comentário OOXML sem reescrever o trecho (a prova inseriu texto
novo já comentado; comentar texto existente pelo OOXML troca o trecho por ele
mesmo, e isso pode mexer na formatação).

### Como o advogado instala (sem loja e sem administrador)

- **Word no Windows, mesmo computador (A):** o PAULUS grava o manifesto e o
  registra **no registro do usuário**, sem administrador. Medido aqui pela
  chave de desenvolvedor (`WEF\Developer`); o caminho documentado para uso
  normal é o **catálogo confiável** (`WEF\TrustedCatalogs`, também por
  usuário), mas ele aponta para uma **pasta compartilhada** (`\\máquina\pasta`)
  e criar compartilhamento no Windows exige administrador. Passos manuais do
  catálogo: Arquivo › Opções › Central de Confiabilidade › Configurações da
  Central de Confiabilidade › Catálogos de Suplementos Confiáveis › colar
  `\\máquina\pasta` › Adicionar catálogo › marcar "Mostrar no Menu" › OK ›
  reabrir o Word › Inserir › Meus Suplementos › PASTA COMPARTILHADA.
  **Decisão para o dono:** chave de desenvolvedor (funciona sem admin, é a
  usada por ferramentas da Microsoft para testes) ou catálogo (o caminho
  oficial, com um passo de administrador uma vez).
- **Word na web (C):** Inserir › Suplementos › Meus Suplementos › Carregar
  Meu Suplemento › escolher o `manifesto.xml` que a tela do PAULUS gera.
  Não medido aqui.

### A maquete

`word/prova/maquete.html` (abra no navegador; barra no alto troca estado,
largura e tema). Capturas em `word/prova/capturas/`:

- `todos-<tema>-<320|480>.png`: as 19 telas lado a lado (os 9 estados da B.2
  e as telas das funções);
- `faixa-<tema>.png`: a aba PAULUS com a dica;
- `menu-<tema>.png`: o menu do botão direito;
- `word-<tema>.png`: o Word inteiro com o painel a 480 px;
- uma captura por tela (`<tema>-<largura>-<estado>.png`), gerada por
  `capturar_maquete.py` e fora do git.

Os textos usam só o que o código vai garantir. Os exemplos jurídicos são
verdadeiros: art. 384 da CLT revogado pela Lei 13.467/2017, art. 1.520 do CC
com a redação da Lei 13.811/2019, CDC até o art. 119, e número CNJ com dígito
errado calculado pelo `regras_processo`.

### O que o levantamento achou para as próximas etapas

- **Reaproveita:** `regras_leis.achar` / `regras_processo.achar` (com posição),
  `leis.CODIGO_DO_INSTRUMENTO` + `Leis.artigo` + `vigencia.do_artigo`,
  `fundamentacao.sugerir`, `redacao.qualificar` (já usa `[ESTADO CIVIL]` e
  `[PROFISSÃO]`), as conexões MCP como molde do token (hash, revogar, só a
  janela local cria), a auditoria encadeada e `ia_em_fundo` para a fila.
- **Falta:**
  - rota que confira as citações de um texto;
  - nacionalidade, estado civil e profissão no cadastro;
  - citação ABNT da doutrina;
  - agente sobre um texto com apontamentos ancorados;
  - documento temporário na pergunta;
  - envio de bytes para a pasta de um Serviço, com versão;
  - `/api/cadastros` filtrado pelo escopo da pessoa.

## Fora do foco

- Quatro processos `cloudflared tunnel run` de 29 e 30/09 continuam rodando
  sem o PAULUS que os abriu (os pais não existem mais): o túnel não está sendo
  encerrado quando o PAULUS cai. Não mexi neles.
- `regras_leis.py:47` tem a chave `"ecа"` com "а" cirílico (inofensiva; a
  linha seguinte tem `"eca"`).
- `/api/cadastros` não é filtrado por Serviço; a muralha ética (`clientes.py`)
  avisa e não bloqueia. Pesa na W3 ("cadastro fora da muralha não aparece").
