# Plano do editor inteligente — o Paulus edita junto (13/10/2026)

Pedido do dono: "dar autonomia para ele abrir e realizar edições dentro do
próprio editor lateral, não pegar PDF e transformar em DOCX
automaticamente, nem vice-versa, mas fazer com que seja um documento
exclusivo da conversa até que haja confirmação explícita de conclusão,
seleção de trechos, alteração do texto dentro do editor de forma condizente
(hoje ele só adiciona um parágrafo ao fim), faça ele ficar super
inteligente, inteligente mesmo [...] tão bom quanto algo profissional,
nível Anthropic ou OpenAI".

## Onde estamos (levantamento de 13/10/2026)

O levantamento completo, com arquivo e linha, foi feito na tela e no
servidor. O essencial:

- **Não há documento, há HTML solto.** O editor é um `contenteditable` com
  `execCommand`; nenhum parágrafo tem identidade. Tudo é achado pela
  posição, por `:nth-child` ou pelo texto.
- **O assistente edita às cegas.** Ele lê o corpo gravado no banco, não o
  que está na tela (até 1,6 s de digitação fica de fora). Só sabe duas
  coisas: `trocas` (de → para, que a tela aplica no documento inteiro, em
  toda ocorrência) e `acrescentar` (que vai sempre para o fim, num
  parágrafo só, e é descartado quando vêm trocas).
- **A marca de sugestão é conteúdo.** `<mark class="ed-novo">` é gravado
  pelo autosave, e o texto não aceito sai no PDF, no DOCX, na assinatura e
  no Acervo. Descartar devolve o documento inteiro de antes e apaga o que
  foi digitado no meio. O texto trocado some (não fica riscado).
- **A seleção se perde** ao focar a caixa de pedido. Mesmo assim, a
  resposta diz "troquei o trecho que você selecionou".
- **Abrir do Acervo destrói o documento.** A importação usa o texto
  extraído: uma linha visual vira um parágrafo, entram `[pagina N]` e
  rodapés, as tabelas do DOCX vão para o fim e somem os estilos. Cada
  reabertura cria outra cópia. A conversa "Contrato Obedi Lourenço" tem três
  (docs 28, 30 e 33).
- **O documento não é da conversa.** No banco não existe vínculo. O
  rascunho aparece na lista geral, e "Salvar na biblioteca" ou "guardar ao
  sair" grava PDF no Acervo (que vira foco de outras conversas). A conversa
  lê o original do Acervo, não o rascunho editado.
- **Versão a cada pausa de digitação**, sem nota (23 versões em 70 min no
  doc 28).
- **O editor ignora a profundidade** e o modelo do nível. O rascunho perde a
  origem e pode ir à nuvem mesmo sendo "só no escritório".
- **Nada mede a qualidade da edição.** O único teste troca "SEMA" por
  "SEMAS".

## Aonde queremos chegar: a régua

"Profissional", aqui, quer dizer estes dez compromissos. Cada um vira teste
e número no banco de provas.

1. **O documento é da conversa.** Nasce na conversa, vive nela, aparece no
   editor lateral dela e em nenhum outro lugar. Só vira arquivo no Acervo
   depois de uma conclusão explícita, no formato escolhido.
2. **Nada de conversão automática.** DOCX é editado como DOCX. PDF continua
   PDF: lido, citado, comentado. Um PDF só vira documento editável quando a
   pessoa pede, e o formato de saída é ela quem escolhe.
3. **Edição no lugar certo.** Trocar uma palavra, reescrever um parágrafo,
   inserir uma cláusula entre a 4ª e a 5ª, apagar um inciso, mover uma
   cláusula. Nunca "anexar no fim" por falta de jeito. Nunca trocar em todo
   o documento o que foi pedido num lugar.
4. **Toda mudança é uma sugestão marcada, como no Word.** O que entra
   aparece sublinhado, o que sai aparece riscado, e cada mudança tem
   Aceitar e Rejeitar. Desfazer uma resposta desfaz só o que ela mudou.
   Sugestão pendente nunca vai para PDF, DOCX, assinatura ou Acervo.
5. **A seleção vale.** O trecho selecionado fica fixo enquanto a pessoa
   pede, e a mudança fica dentro dele. Há atalhos sobre a seleção
   (reescrever, mais formal, encurtar, comentar, citar a lei aqui).
6. **O Paulus aponta.** Ao falar do documento, cita o parágrafo ("Cláusula
   4ª, §1º"). Um clique leva o editor até lá. Cada mudança tem "ir para".
7. **Confere antes de entregar.** Numeração e referências cruzadas, termos
   definidos, nomes e qualificação das partes, valor em número e por
   extenso, datas, CPF/CNPJ, lacunas `[●]` e artigos de lei (que existem e
   estão em vigor, pela Biblioteca). Nos níveis Max e Ultra, uma segunda
   leitura pergunta: "fiz o que foi pedido? mudei algo além? contradiz
   outra cláusula?".
8. **Honestidade.** A resposta diz só o que foi aplicado de fato (o servidor
   é quem aplica). O que não deu, ela diz por quê.
9. **Medido.** Um banco de provas de edição com metas por categoria, rodado
   a cada etapa e por modelo (local, Llama 70B, Claude). Nenhuma etapa
   piora o que já estava bom.
10. **Ao vivo.** A pessoa vê "editando a Cláusula 4ª…" e as mudanças
    entrando no documento enquanto o modelo escreve, não um minuto de
    espera muda.

## Regras da casa (valem em todas as etapas)

- Nada publicado sem o dono pedir. Commit e push na main só com os testes
  passando.
- A regra decide o que dá para decidir, o modelo propõe e o programa
  confere. Modelo só quando a regra não basta.
- O texto de tela só promete o que o código garante.
- Privacidade: o documento da conversa herda a origem. O que é "só no
  escritório" não vai à nuvem, nem pelo editor.
- O Paulus é autônomo (decide o que fazer e onde procurar), sem modos para a
  pessoa alternar. Dentro do documento da conversa, ele edita sem pedir
  licença, porque toda mudança é uma sugestão reversível. Concluir, salvar
  no Acervo, assinar e enviar só com confirmação explícita.
- Cada etapa termina com testes que dizem "todos os testes passaram", com
  os números do banco de provas e com esta página atualizada.

## Etapas

| Etapa | O quê | Estado (13/10/2026) | Teste |
| --- | --- | --- | --- |
| E0 | Banco de provas de edição e a linha de base (medir antes de mudar) | feita | `tests/test_editor_bench.py`, `tools/medir_editor.py` |
| E1 | Documento da conversa: vínculo, ciclo de vida, formatos sem conversão automática, importação fiel de DOCX e PDF limpo, conclusão explícita | feita, menos a pasta pela regra de cliente/serviço | `tests/test_editor_documento_da_conversa.py` |
| E2 | Blocos com identidade (`data-b`), HTML saneado, o assistente lendo a tela, versões por rodada | feita | `tests/test_editor_blocos.py` |
| E3 | Sugestões marcadas de verdade: operações aplicadas no servidor, `ins`/`del` por mudança, aceitar e rejeitar uma a uma, desfazer por rodada | feita | `tests/test_editor_blocos.py`, `tests/test_editor_agente.py`, `tests/test_editor_tela.py` |
| E4 | Seleção fixa e o Paulus apontando: atalhos sobre a seleção, citação de parágrafo, ir até lá, coluna com abas | em parte: falta a coluna com abas | `tests/test_editor_tela.py` |
| E5 | O agente de edição: entender, localizar, planejar, editar, aplicar, conferir, responder, ao vivo e com a profundidade | feita, sem o "planejar" como passo à parte | `tests/test_editor_agente.py` + banco de provas |
| E6 | Conferência jurídica: motor de regras e a segunda leitura | feita; os avisos ficam no painel, não na margem | `tests/test_editor_conferencia.py` |
| E7 | O jeito do escritório e a memória do documento: regras de redação, cláusulas da casa, o histórico de pedidos | feita | `tests/test_editor_agente.py` |
| E8 | Acabamento da tela: painel de mudanças, linha do tempo, comentários na margem, atalhos de teclado, celular | em parte: cabeçalho e painel feitos | `tests/test_editor_tela.py` |
| E9 | Afinação contínua: o banco de provas como portão, 👍/👎 por edição virando caso de teste | começou | `tools/medir_editor.py` |

## Como ficou e o que falta (13/10/2026)

**Onde está cada parte:**

- **Servidor:**
  - `src/blocos.py`: os blocos com nome e as sugestões;
  - `src/esboco.py`: o mapa do documento;
  - `src/edicao.py`: aplica as operações;
  - `src/agente_de_edicao.py`: a rodada;
  - `src/conferencia_juridica.py`: a conferência;
  - `src/docx_ida_e_volta.py` e `src/pdf_em_texto.py`: os formatos.
- **Rotas:** `/api/documentos/{id}/editar`, `/sugestoes`, `/conferencia`, `/concluir`, `/reabrir`, `/rodadas`.
- **Tela:** `frontend/js/95-editor-inteligente.js` e `css/59-editor-inteligente.css`.
- **Banco de provas:** `tools/bancada_editor/`. Os resultados ficam em `tools/bancada_editor/resultados/`.

**Diferenças em relação ao texto das etapas abaixo:**

- **E1:**
  - A conclusão propõe a pasta do original, com o nome " - revisado", ou Acervo › Editor. A pasta pela regra de cliente ou serviço ficou para depois.
  - Assinar passa pela conclusão em PDF.
  - O editor lateral não envia por e-mail nem por WhatsApp. O envio sai do arquivo concluído no Acervo, e o rascunho da conversa não vai ao Word nem ao Acervo por fora da conclusão (`_so_concluido`).
- **E2:**
  - O editor ao lado da conversa confere a revisão. Em conflito, o que estava na tela vai só para o Histórico (`so_historico`), e a tela passa a mostrar o que está gravado.
  - O editor de tela cheia (Documentos) ainda grava sem a revisão: o último vence.
  - No fim da rodada, o servidor junta o que a tela gravou no meio; o remendo que já estava lá não entra de novo.
  - Quem volta ao documento no meio da rodada recebe, no fim, o documento inteiro do servidor. O que foi digitado e não estava salvo fica no Histórico.
- **E3:** quando uma operação não bate com o texto, o agente tenta corrigir uma vez; nos níveis Max e Ultra, duas vezes.
- **E5:**
  - Não há um passo "planejar" à parte. O modelo diz o que entendeu numa frase (o campo `entendi`), e a frase aparece no bastidor da conversa.
  - **O programa confere o modelo:**
    - o número do pedido posto em outra unidade ("24 meses" virando "24 dias" em outro parágrafo) não entra e vira sugestão;
    - o dado novo do pedido (nome, valor, data, quantidade) que não entrou no texto volta ao modelo uma vez; se ainda faltar, a resposta diz;
    - o trecho pedido em pedaços separados do bloco: a correção diz isso ao modelo;
    - a mesma troca pedida duas vezes não vira "ALVES ALVES".
- **E6:**
  - Os avisos aparecem no painel de alterações (botão Conferir), não na margem.
  - A única correção que vira sugestão sozinha é a renumeração.
- **E9:**
  - A nota (👍/👎) de cada rodada é gravada em `data/medicao/editor-avaliacoes.jsonl`.
  - Transformar uma nota em tarefa do banco ainda é feito à mão.

**O que falta:**

- **E2:** o editor de tela cheia conferir a revisão, como o editor ao lado da conversa já faz.
- **E4:** a coluna da direita com abas (Documento | Original | Planilha).
- **E8:**
  - a linha do tempo por rodada, com a diferença;
  - comentários na margem do editor lateral;
  - atalhos de teclado e "anterior/próxima" no painel;
  - o acabamento no celular.
- **E9:** o banco rodado como portão a cada mudança no agente e a medida com o Claude, que depende da chave.

**Ordem:**
- **Alicerce, nesta ordem:** E0 → E1 → E2 → E3.
- **Depois:** a E5 depende da E2 e da E3; a E4 e a E6 podem correr em paralelo à E5.
- **Por último:** a E7 e a E8, enquanto a E9 acompanha tudo.

## E0 — Banco de provas de edição e a linha de base

**Objetivo:** saber, com número, o quanto o editor acerta hoje e a cada
etapa.

- **Corpus:** 6 documentos fictícios e realistas: compra e venda de
  imóvel, locação, procuração, petição inicial, partilha e notificação.
  - Os blocos já trazem `data-b` (o formato da E2).
  - Cada documento tem cláusulas numeradas, parágrafos, incisos, termos
    definidos, qualificação, valores por extenso e lacunas.
- **Tarefas (≥ 60):**
  - trocar num lugar só;
  - reescrever um parágrafo (com e sem seleção);
  - inserir cláusula no lugar certo e renumerar;
  - apagar inciso; mover cláusula;
  - mudar o nome de uma parte em todo o documento (aqui o "em tudo" é
    pedido);
  - deixar mais formal; encurtar;
  - os "4 ajustes" do caso real;
  - perguntar sobre o documento (e apontar);
  - recusar editar PDF sem pedido; concluir.
- **Checagens automáticas por tarefa:**
  - o alvo mudou e o resto ficou intacto (dano colateral = 0);
  - o conteúdo exigido está presente e o proibido, ausente;
  - a posição está certa;
  - a numeração e as referências estão válidas;
  - toda mudança está marcada;
  - o que a resposta diz bate com o que foi aplicado.
- **Ferramentas:**
  - `tools/medir_editor.py --adaptador agente|hoje|gabarito|troca_global|no_fim
    --modelo nuvem|local --nivel <nível> [--so <ids>]` roda as tarefas e
    grava o resultado em
    `tools/bancada_editor/resultados/<data>-<adaptador>-<modelo>-<nível>.json`.
    Só entram documentos fictícios; nada sai de `data/`.
  - `tests/test_editor_bench.py` confere o próprio banco (as checagens
    pegam erro de verdade) com um modelo falso.
- **Linha de base:** o sistema de hoje simulado fielmente (trocas globais,
  acrescentar no fim, `mark`), medido com o Llama 70B da nuvem.

## E1 — Documento da conversa

**Objetivo:** o rascunho pertence à conversa até a conclusão, e os
formatos são respeitados.

- **Banco:** `documentos` ganha:
  - `trabalho_id`;
  - `origem` (JSON: `tipo` redigido|acervo|novo, `nome`, `sha1`,
    `formato_original`);
  - `situacao` (`rascunho_da_conversa` | `concluido` | `livre`);
  - `concluido_em` e `arquivo`.
- **Documento da conversa:**
  - **Visibilidade:** fica fora da lista geral do Editor, fora do Acervo e
    do índice. "Guardar ao sair" e "Salvar na biblioteca" não valem para
    ele.
  - **Reabertura:** reabrir o mesmo original na mesma conversa usa o mesmo
    rascunho, pelo `sha1` e não pelo nome.
  - **Conversa apagada:** o rascunho não concluído vai junto para a
    lixeira.
- **Formatos sem conversão automática:**
  - **DOCX do Acervo:** importação estrutural com python-docx.
    - Mantém: títulos, estilos, listas numeradas, negrito, itálico e
      sublinhado, tabelas no lugar e alinhamento.
    - Cabeçalho e rodapé ficam guardados à parte.
    - A conclusão volta a DOCX com essa estrutura.
  - **PDF do Acervo:** continua PDF, no visor ao lado: lê, aponta e
    comenta.
    - "Criar um documento editável a partir deste PDF" só com pedido
      explícito.
    - O texto entra limpo: linhas juntadas em parágrafos, hifenização
      desfeita e cabeçalhos, rodapés e `[pagina N]` removidos.
    - Na conclusão, a pessoa escolhe o formato.
  - **Documento redigido na conversa:** nasce como documento da conversa.
    - O padrão de conclusão é DOCX; PDF só se ela escolher.
    - "Notas para o advogado" e a frase de abertura ficam fora do corpo.
- **Conclusão explícita:**
  - **Como pedir:** botão "Concluir documento" no editor lateral, ou uma
    frase reconhecida ("pode concluir", "está pronto, salve").
  - **O cartão de conclusão** mostra o formato (o original por padrão), o
    nome e a pasta de destino (pela regra de cliente/serviço; senão,
    Acervo › Editor).
  - **Sugestões pendentes** precisam ser resolvidas antes de concluir.
  - **Depois de concluir:** o documento fica concluído (só leitura, com o
    arquivo). Mexer de novo abre uma nova rodada a partir dele, só a pedido.
- **Assinar, enviar por e-mail ou WhatsApp** partem do documento concluído.
  Se não estiver concluído, o cartão oferece concluir antes, e nunca faz
  isso calado.
- **O editor volta com a conversa:** reabrir a conversa reabre o documento
  dela ao lado.

## E2 — Blocos com identidade e o assistente lendo a tela

**Objetivo:** toda parte do documento tem nome, e o assistente vê o que a
pessoa vê.

- **Identidade:** cada bloco (título, cláusula, parágrafo, item, tabela,
  citação) ganha `data-b` estável.
  - O editor preserva o atributo e o normalizador dá id aos blocos novos
    (colar, Enter).
  - O `ler_html` passa a entender `data-b`, `blockquote`, `h4`, `ins` e
    `del`.
- **Esboço por regra:** títulos, cláusulas com número (1ª / PRIMEIRA),
  parágrafos (§, "Parágrafo único") e incisos. É o mapa que o assistente usa
  para achar "a cláusula 5ª".
- **HTML saneado no servidor**, por lista do que é permitido (sem `style`
  colado da interface).
- **O pedido leva o HTML da tela e a versão de base.** Gravar confere a
  versão (sem "o último vence").
- **Versões por rodada:**
  - nascem a cada resposta do assistente, a cada conclusão e a cada 10
    minutos de digitação, sempre com nota;
  - o autosave atualiza o documento sem criar versão.

## E3 — Sugestões marcadas de verdade

**Objetivo:** o modelo propõe operações; o servidor as aplica como
sugestões; a pessoa decide cada uma.

- **Operações (JSON validado):**
  - `substituir {bloco, de, para}`: dentro de um bloco só;
  - `substituir_em_tudo {de, para}`: só quando o pedido é "em todo o
    documento";
  - `reescrever {bloco, texto}`;
  - `inserir {antes_de|depois_de, blocos[]}`, com tipo e nível;
  - `apagar {bloco}` e `apagar_trecho {bloco, de}`;
  - `mover {bloco, depois_de}`;
  - `comentar {bloco, de?, texto}`;
  - `renumerar {}`, por regra.
- **Aplicação no servidor:**
  - vira `<ins data-s>` e `<del data-s>` (e bloco inteiro inserido ou
    apagado), com autor, rodada e motivo;
  - o `de` precisa existir no bloco; se não existir, o agente relocaliza
    (até duas vezes); nunca anexa no fim por fracasso.
- **Na tela:**
  - aceitar ou rejeitar uma por uma, todas, ou as de uma rodada;
  - "desfazer esta resposta" rejeita só as dela;
  - o texto digitado no meio fica.
- **Exportações** (PDF, DOCX, assinatura, Acervo) recusam o documento com
  sugestão pendente e oferecem "aceitar todas / rejeitar todas / revisar".
  Acaba o vazamento do texto não aceito.
- **O que sai do caminho velho:**
  - a troca global por padrão;
  - o `acrescentar` descartado;
  - o parágrafo único para texto de vários parágrafos;
  - "Descartar" que restaura o documento inteiro.

## E4 — Seleção fixa e o Paulus apontando

**Objetivo:** a pessoa mostra onde, e o Paulus mostra onde.

- **Seleção guardada como faixa de blocos** (bloco e posição no início e
  no fim). Ela fica pintada enquanto a pessoa digita o pedido, e um chip
  "Trecho selecionado: '…' ×" aparece na caixa.
- **Barrinha flutuante sobre a seleção:** Pedir ao Paulus, Reescrever,
  Mais formal, Encurtar, Explicar, Comentar, Citar a lei aqui.
- **Pedido com seleção:** as operações ficam presas aos blocos
  selecionados (o validador recusa as de fora).
- **Respostas sobre o documento citam o bloco** (`[§b12]`, chip "Cláusula
  4ª"). O clique leva o editor até lá e pisca o trecho. Cada sugestão tem
  "ir para".
- **A coluna da direita ganha abas** (Documento | Original | Planilha):
  abrir o visor ou a citação não fecha mais o editor.

## E5 — O agente de edição

**Objetivo:** o cérebro.

- **A rodada, para cada pedido no documento da conversa (no servidor, ao
  vivo):**
  1. **Entender:** a regra primeiro, o modelo só na dúvida. O tipo pode ser
     editar trecho, inserir, revisar e melhorar, uniformizar, mudar o
     estilo, perguntar, comentar, concluir ou desfazer. Junto vem o escopo:
     seleção, cláusula N ou tudo.
  2. **Localizar:**
     - o esboço com o número da cláusula;
     - busca por palavra nos blocos (BM25);
     - termos definidos;
     - o modelo escolhe só quando há empate.
  3. **Planejar:** só nos níveis Max e Ultra ou com vários pontos. É uma
     lista curta, mostrada na conversa.
  4. **Editar:**
     - o modelo recebe o pedido, os blocos-alvo exatos com id, os vizinhos,
       o esboço, os termos definidos, as regras de redação da casa e os
       artigos da Biblioteca que importam;
     - devolve operações (E3);
     - o JSON é reparado e validado, com nova tentativa se precisar.
  5. **Aplicar como sugestões:** a tela recebe as operações ao vivo
     (evento `documento_alterado`) e as desenha no lugar, rolando até a
     primeira.
  6. **Conferir:** o motor da E6 roda; nos níveis Max e Ultra, a segunda
     leitura também roda, e o que ela apontar vira nova operação.
  7. **Responder curto:**
     - o que mudou, com "ir para";
     - o que não deu e por quê;
     - as lacunas.
- **Modelo:**
  - o melhor disponível no nível (Claude quando houver a chave; Llama 70B
    hoje);
  - o local de 3B só para mudanças pequenas e por regra, dizendo isso.
- **A conversa lê o documento da conversa.** Perguntas sobre "o contrato"
  respondem pelo rascunho, não pelo original do Acervo.
- **Verbos e pedidos** que hoje escapam ("adicione", "inclua a cláusula de…",
  "a cláusula 5 precisa prever multa") entram na regra.
- **Documento longo:** o esboço, os alvos e os vizinhos; o documento
  inteiro só quando cabe.

## E6 — Conferência jurídica

**Motor de regras**, reaproveitando `redacao.renumerar`,
`conferir_clausulas`, `documento.conferir`, `campos_br` e `leis`. Ele
confere:
- numeração e referências cruzadas, depois de cada inserção ou remoção;
- termos definidos ("doravante denominados VENDEDORES"): o uso coerente e
  o termo usado sem definição;
- partes: nome e qualificação iguais em todo o documento e iguais à ficha
  de Cadastros;
- valor em número igual ao por extenso; datas válidas; CPF/CNPJ;
- lacunas `[●]` e `[VALOR]` listadas;
- artigo citado que existe, com a redação vigente, pela Biblioteca;
- "Notas para o advogado" e conversa de assistente fora do corpo.

O que o motor achar vira aviso na margem e, quando a correção é óbvia, uma
sugestão. A segunda leitura do modelo, nos níveis Max e Ultra, pega
contradição entre cláusulas e pedido não cumprido.

## E7 — O jeito do escritório e a memória do documento

- **Regras de redação da casa** (Contextos) entram em toda edição.
- **Cláusulas do escritório** (`data/clausulas.json`) e modelos marcados no
  Acervo: "use a cláusula de foro da casa" insere a da casa, adaptada às
  partes.
- **Memória do documento:** o que já foi pedido e decidido nele ("você
  pediu multa de 10% na rodada 3"). Ela guia as próximas rodadas e evita
  desfazer uma decisão sem querer.

## E8 — Acabamento da tela

- **Cabeçalho honesto:** "Documento da conversa · rascunho"; nada de
  ".docx" falso nem de "o original não é alterado" sem original.
- **Painel de mudanças:** quantas são, a lista, anterior e próxima, aceitar
  e rejeitar todas.
- **Linha do tempo por rodada**, com a diferença.
- **Comentários na margem**, também no editor lateral.
- **Atalhos de teclado:** aceitar/rejeitar, próxima mudança, pedir sobre a
  seleção.
- **Celular:** o documento da conversa legível e as sugestões decidíveis.

## E9 — Afinação contínua

- **O banco de provas como portão:** nenhuma etapa entra com piora.
  - Rodar: `PYTHONIOENCODING=utf-8 venv/Scripts/python.exe tools/medir_editor.py --adaptador agente --modelo nuvem --nivel advogado`.
    Leva de 11 a 14 minutos e gasta uns 190 mil tokens do plano.
  - Comparar com o último resultado em `tools/bancada_editor/resultados/`: nenhuma categoria cai sem explicação.
  - O modelo varia de uma rodada para outra. A tarefa que falha uma vez se confere com `--so <id>` três vezes antes de mexer no agente.
- **👍/👎 por rodada de edição**, como na L1. A 👎 com "o que deveria ter
  feito" vira tarefa nova no banco.
- **Medir por modelo** (Llama 70B, Mistral, Claude) e escolher, por tipo de
  pedido, o que acerta mais pelo menor custo.

## Metas do banco de provas

Medido em 13/10/2026 com o Llama 3.3 70B da nuvem, no nível Advogado, nas 62 tarefas. Os dois rodaram com as mesmas checagens. Os arquivos estão em `tools/bancada_editor/resultados/`: `2026-10-13-1749-hoje-…` (editor antigo) e `2026-10-13-1909-agente-…` (agente).

| Medida | Editor antigo (medido) | Agente (medido) | Meta com o Llama 70B | Meta com o Claude |
| --- | --- | --- | --- | --- |
| Acerto geral | 53,2% | 98,4% | — | — |
| Tarefa de lugar único feita no lugar certo | 56,9% | 98,0% | ≥ 90% | ≥ 97% |
| Tarefa de vários pontos completa | 1 de 2 | 2 de 2 | ≥ 80% | ≥ 92% |
| Sem dano colateral | 96,4% | 100% | 100% nas tarefas de lugar único | 100% |
| Toda mudança marcada e reversível uma a uma | 32,3% | 100% | 100% (é do programa) | 100% |
| Resposta que diz só o que foi aplicado | 100%¹ | 100% | 100% (é do programa) | 100% |
| Numeração e referências válidas depois da edição | 81,8% | 100% | 100% (regra) | 100% |
| Tempo da rodada inteira | 9,0 s em média | 18,1 s em média; mediana 12 s, p90 37,5 s | — | — |
| Primeira mudança visível no editor | só no fim | não medido pelo banco | < 8 s | < 6 s |

¹ A resposta do editor antigo era genérica ("escrevi no fim do documento") e não afirmava nada que a checagem pudesse pegar.

**Como ler estes números:**

- **Evolução do agente no dia:**
  - 82,3% na primeira rodada, com as checagens mais duras;
  - 95,2% depois de corrigidas as checagens que reprovavam respostas certas;
  - 96,8% e 96,8% nas duas rodadas seguintes;
  - 98,4% com as conferências do programa (unidade do número, dado novo do pedido, pedaços separados, troca repetida).
- **Pode estar otimista.** As checagens foram corrigidas olhando as respostas do agente. A comparação com o editor antigo vale, porque os dois usam as mesmas checagens. O número absoluto, não necessariamente: o banco precisa crescer com tarefas novas, inclusive as que vierem das notas 👎.
- **A falha que resta (cv-10):** o modelo não pôs o nome da esposa na qualificação do comprador e explicou por quê. A resposta diz isso ao advogado.
- **O tempo** da rodada inteira inclui as chamadas de correção e de complemento. A mais longa levou 97 s. As mudanças entram no editor enquanto o modelo escreve, mas o banco não mede a primeira.

## O que depende do dono

- **A chave do Claude (`ANTHROPIC_KEY`) no Worker.** É o maior salto de
  qualidade de edição. Com o Llama 70B as metas são as do meio; com o
  Claude, as da direita.
- **Formato padrão da conclusão de um documento novo:** a proposta é DOCX.
- **Pasta de destino padrão na conclusão:** a proposta é a pasta do
  cliente ou do serviço, quando houver; senão, Acervo › Editor.
