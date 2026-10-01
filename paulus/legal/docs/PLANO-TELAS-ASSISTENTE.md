# PLANO — As telas do Assistente (pacote de 01/10/2026)

Pedido do dono em 01/10/2026: "Atualize o assistente e suas telas seguindo as
instruções" do pacote `Recriação da página assistente/PAULUS - Telas` (46
mockups `.dc.html` + `LEIA-ME.md`, fora do git porque trazem dados reais). Este
documento é a retomada: uma conversa nova continua da primeira etapa que não
estiver `feita`.

## As regras do pacote (LEIA-ME)

- Os mockups desenham **só a área de conteúdo** (1920 × 1032): a barra de
  ícones e a barra da janela ficam como estão.
- Fiel ao desenho, principalmente nas **larguras**: chat até 1080 px; coluna
  lateral 380 (contexto), 420 (formulário, agenda, gravação, financeiro) ou
  460 (configurações); ferramenta de documento ocupa o resto e o chat fica com
  560 px à esquerda.
- O que ainda não existe, criar, ligado aos dados reais.
- Transições: troca de tela 180–220 ms ease-out; o que surge entra de 0 a 1
  com 4–8 px; **a coluna lateral troca de papel** (contexto → ferramenta →
  contexto) deslizando/alargando, e o chat se ajusta junto. "Animações
  reduzidas" troca direto.
- Mudança de configuração pelo chat: o campo ganha o selo "novo" e o rodapé
  da coluna diz quantas faltam salvar, com Descartar e Salvar alterações.
  Nada é salvo sem o clique.
- Ações sensíveis (assinar, enviar e-mail, mandar à nuvem) continuam pedindo o
  sim, a menos que Limites da IA diga outra coisa.
- Rolagem: barra discreta e fina, da cor das superfícies.
- Ícones só do subconjunto `MaterialSymbolsOutlined-icones.woff2`.

## Etapas

| Etapa | O quê (mockups) | Estado | Commit |
| --- | --- | --- | --- |
| T0 | Casca da conversa: cabeçalho, coluna do chat (1080), caixa de pedido em duas linhas, coluna lateral de altura inteira que troca de papel (380/420/460/ferramenta), contexto (Progresso, Trechos lidos, Como respondi, Onde procurei), rolagem fina | feita | ver git log (T0) |
| T1 | Tela inicial: `Assistente`, `Acontecendo agora`, `Gravando`, `Avisos` (resumo em três cartões e o painel no lugar da lista), `Central de avisos`, `Apoiar`, `Anexar - Google Drive` | feita | ver git log (T1) |
| T2 | Estados da conversa: `Conversa`, `Carregando`, `Feedback`, `Ditando`, `Foco`, `Apoiar`, `Gravando` (transcrição ao vivo com sugestões) | feita | ver git log (T2) |
| T3 | Documentos e ferramentas na coluna: `Documento`, `Editor`, `Planilha`, `Editor de planilha`, `PDF`, `Assinar`, `Agendar`, `Criar agente`, `E-mail`, `Escrever e-mail` | em andamento (documento, PDF, editor, planilha, editor de planilha e assinar feitos) | ver git log (T3) |
| T4 | Cadastros e financeiro pela conversa: `Cadastro`, `Equipe`, `Despesa fixa`, `Lancamento`, `Recebimento`, `Financeiro`, `Relatorio` | a fazer | |
| T5 | Configurações abertas pelo chat: `Meus dados`, `Assistente e modelo`, `Modelos`, `Desempenho`, `Teste`, `Conexoes`, `Word`, `Acesso de fora`, `Escritorio`, `Backup`, `Biblioteca`, `Aparencia`, `Modulos`, `Versao`, `Lixeira` | a fazer | |

## Registro

(cada etapa anota aqui o que foi feito, o que foi medido e o que ficou de fora)

### T0 — casca da conversa (01/10/2026)

- `#lateral` saiu de dentro do corpo e virou a coluna da direita de altura
  inteira (da barra da janela ao pé), com `#lado-contexto` e
  `#lado-ferramenta`. A largura mora em `--lado`, registrada com `@property`
  em `00-tokens.css` (anima sozinha); `--lado-alvo` é a de chegada, que o
  conteúdo usa desde o primeiro quadro, preso à borda direita (efeito de
  gaveta). Na ferramenta o alvo é medido em px por `js/02-lado.js`
  (`--largura-ferramenta`): porcentagem dentro da coluna que anima seria a
  largura dela mesma.
- `js/02-lado.js`: `abrirNoLado(papel, {chave, html, ligar, aoFechar})`,
  `voltarAoContexto()`, `fecharLado()`, `largarFerramentaDoLado()`; quem
  abriu recebe o `aoFechar` quando a coluna volta ou outra ferramenta toma o
  lugar. As partes do contexto recolhem pela cabeça.
- Conversa no desenho: cabeçalho a 28 px (seta 30, título 21, Exportar e o
  botão da coluna), fio 1080 com recuo 48, bolha até 560, resposta 15/1,7,
  linha de baixo com as etiquetas dos documentos citados + tempo e modelo +
  quatro ícones; nota do que foi feito num clique com o fio à esquerda;
  caixa de pedido em duas linhas; "A próxima pergunta…" como linha solta.
- Contexto: Progresso volta à coluna (com "k de n etapas", anel desenhado na
  etapa que anda e círculo vazio na que espera); Trechos lidos em cartões
  (documento, página, três linhas; cinco à vista e "mais N"); Como respondi
  em ficha curta (tempo em monoespaço, modelo em etiqueta); Onde procurei com
  a pasta em etiqueta.
- Rolagem: a barra fina de 6 px volta em todo o programa (o pacote pede; até
  aqui ela era escondida, a pedido antigo do dono).
- Testes: `test_frontend` ok; `test_c3_painel` ok (a regra "conversa
  concluída não mostra Progresso" mudou para "mostra k de n etapas", como no
  pacote); `test_tela` ok até o celular, onde o navegador caiu por falta de
  recurso — rodado sozinho, o celular passa inteiro.


### T1 — tela inicial (01/10/2026)

- Lista de conversas aberta de início e na largura toda (recuo de 44 px),
  linhas de 15 px, nome em 600, "trabalhando" sem cor de estado; o recolher
  usa o mesmo glifo desenhado do botão da coluna. No início o escopo
  "Acervo · N documentos" sai da caixa (a frase de baixo da saudação já diz);
  Organizar ganhou o ícone de pasta.
- Acontecendo agora: `cartaoDoTrabalhoAgora` com uma faixa por etapa (a que
  anda é 2,4× mais larga, enche até a previsão desta máquina e tem o brilho;
  sem previsão, só o brilho), o tempo "X s de ~Y s" e o Parar. `/api/agora`
  passou a mandar as etapas da conversa.
- Gravando: `cartaoDaGravacaoAgora` (js/11-gravacoes.js) com o gravador que
  já existia — onda do microfone, a última fala transcrita, Pausar, Marcar
  momento, Abrir gravação e Parar e arquivar. Pausar e parar fora da tela de
  Gravações não levam mais a pessoa para lá (`redesenharGravador`); parar
  arquiva e avisa com "Abrir". O "Abrir conversa" do desenho vira "Abrir
  gravação" até a T2 (a conversa que grava).
- Avisos: o carrossel saiu. No lugar, o resumo em três cartões (atrasados
  com o fio em vinho, vencem hoje, conversas pela metade em âmbar), "ver N"
  abre o painel no lugar da lista (tipos à esquerda com a conta, lista
  agrupada, busca, Hoje/7 dias/30 dias, × volta às conversas) e "Central de
  avisos" abre o mesmo painel numa janela de 920 px, com o histórico e a
  seleção de vários (marcar como visto em lote).
- Apoiar: `js/77-apoiar-convite.js` + `GET /api/apoio/neste-mes` (documentos
  lidos nas respostas do mês e lançamentos criados no mês, contados aqui).
  Aparece só com algo a contar, uma vez por mês ("Agora não" guarda o mês) e
  nunca para quem já apoia. Paga pelo Pix ou cartão de sempre; a tela Apoiar
  não se redesenha mais por cima de outra tela (`apoio.naTela`).
  **Fica de fora:** a "Meta de outubro" só aparece quando o site publicar
  `meta` no mês em `/api/public/desenvolvimento` — hoje o site não publica,
  e a linha mostra só o que entrou no mês (ou nada, sem internet).
- Anexar › Google Drive: o quadro sem o Drive para computador no desenho
  (marca, título em serifa, Instalar — recomendado — com o botão da página
  de download, e Sem instalar nada com o caminho Acervo › Incluir pasta ›
  Google Drive, que abre o Acervo). A conta e o seletor do Windows foram para
  o pé da janela; a janela tem 810 px.
- Testes: `test_frontend`, `test_listas` ok; `test_t2_avisos` reescrito na
  parte da tela para o resumo e o painel (o vinho agora é permitido no
  cartão dos atrasados, como no pacote) — todos ok.


### T2 — estados da conversa (01/10/2026)

- Carregando: o plano virou o cartão "Trabalhando · etapa k de n" com uma
  faixa por etapa (a que anda enche até a previsão), "X s de ~Y s", o Parar
  e, embaixo, o registro do que o programa fez (o bastidor sem cabeçalho, só
  as linhas). Na coluna, "Como estou respondendo" enquanto anda (caminho,
  janela, modelo) e "Como respondi" quando termina. O registro fica guardado
  na resposta.
- Feedback: o cartão "O que houve com esta resposta?" no desenho (motivos em
  etiqueta com o visto, os dois campos lado a lado, "Precisa ter" com o
  ícone de regra, o pé com a explicação, Cancelar e Anotar); o "não gostei"
  fica marcado enquanto o cartão está aberto.
- Ditando: o cartão toma o lugar da caixa (ponto vermelho, "o texto entra na
  caixa ao concluir", tempo, a onda do microfone, o texto ouvido) com
  Cancelar, Pausar, "Concluir e editar" e "Concluir e enviar".
- Foco: `js/78-conversa-foco.js` põe o ciclo de foco no alto da coluna
  (`/api/bemestar`): tarefa, contagem regressiva, a faixa do ciclo, pausar e,
  quando há lembrete vencido ("Levante e caminhe um pouco"), o Feito.
- Apoiar: depois de uma resposta que leu documentos, o convite aparece uma vez
  no mês dentro da conversa ("Pronto — esse foi o Nº documento…"), com as
  mesmas contas da T1; o convite da tela inicial some quando há conversa.
- Gravando: "grave a reunião com a Rio Fresco e me ajude a responder" vira
  pedido de gravar (`intencao.ler_gravacao`, antes de tudo); a conversa ganha
  o nome da gravação, começa a gravar e mostra as falas conforme o Whisper
  transcreve (`js/79-conversa-gravando.js`). A coluna (420) traz o gravador,
  o contexto do caso (os documentos do Serviço do cliente ou com o nome dele),
  os pontos do caso, marcadores e a chave "Sugerir respostas". Cada fala com
  número, data ou palavra de contrato é conferida contra os documentos do caso
  (`src/sugestoes_ao_vivo.py`, `POST /api/gravacoes/sugerir`): regra antes,
  busca só nos documentos do caso, o modelo responde em JSON e a sugestão só
  passa se o número dela estiver no trecho. Medido com o Ollama: na fala "o
  contrato fala em vencimento no fim do mês", a refutação "O contrato
  estabelece o vencimento no dia 5 de cada mês" saiu do contrato da Clínica
  Bem Viver. Parar arquiva a gravação e a registra na conversa.
  **Fica de fora:** as falas não têm nome de quem falou (o Whisper local não
  separa vozes); a pergunta feita durante a gravação lê os documentos do caso,
  não o que foi dito (a caixa diz "Pergunte sobre o caso enquanto grava…").
- Testes: `test_frontend`, `test_intencao`, `test_c2_pensando` (o plano agora
  é `.trab-cartao`), `test_c3_painel` e `test_t2_avisos` ok. `test_gravacoes`
  falha nesta máquina agora por memória (1,4 GB livres, o Whisper turbo pede
  1,9 GB) — o mesmo aviso que o programa dá; não vem desta etapa.


### T3 — documentos e ferramentas na coluna (01/10/2026, em andamento)

Primeira parte: documento, PDF, editor, planilha e editor de planilha.

- `js/80-visor-ao-lado.js`: "Mostrar aqui" (e o clique num trecho lido ou
  num [T1] da resposta) abre o documento na coluna da direita, como
  ferramenta: marca do formato, nome com a extensão apagada, "só leitura · N
  páginas · K trechos citados" (no PDF, "PDF · …" e "assinado digitalmente"
  quando tem assinatura), No Windows, Abrir editor (e Assinar, no PDF), o
  quadro com "Trechos citados 1 de 2", a página, a lupa e o zoom,
  miniaturas quando há mais de uma página, e o pé "N páginas · tamanho/
  palavras · o arquivo original não é alterado". O cartão da oferta fica,
  com o botão do que está aberto marcado, e a nota diz o que foi feito. A
  próxima pergunta passa a ler só o documento aberto.
- Os trechos citados ficam marcados NA FRASE: `citacao.marcas_dos_trechos`
  procura cada trecho no PDF desenhado (o arquivo, ou o que o gerador do
  editor monta para o Word), primeiro inteiro e depois pelos pedaços, com a
  marca indo até o fim da palavra. `POST /api/biblioteca/leitura` (sem anotar
  na conversa) e `POST /api/biblioteca/procurar-no-documento` (a lupa).
- Editor: saiu o cartão flutuante; o editor é ferramenta da coluna, no
  desenho (rascunho · versão · o original não é alterado; No Windows quando o
  Word com o PAVLVS está instalado; Assinar; Salvar na biblioteca; a barra
  com Parágrafo, B/I/U, lista, Numerar, Qualificar, Citar a lei e
  Alterações; o pé com o ponto de salvo). Na caixa, "No documento / Na
  conversa" e os pedidos prontos numa linha.
- `js/81-planilha-ao-lado.js`: a planilha do Acervo abre como grade
  (`POST /api/biblioteca/planilha`), com a barra da fórmula, as linhas
  citadas marcadas (`ferramentas.linhas_citadas_da_planilha`), "a pagar" e
  "a receber" com cor, as abas no pé. "Abrir editor" no .xlsx cria uma
  planilha do editor (`/api/documentos/importar`) e a grade passa a editar:
  escrever na célula, desfazer/refazer, negrito, itálico, R$, %, ,00, Σ
  Somar, Ordenar (a linha de total fica), Filtrar (só da tela), + Linha; a
  célula que mudou fica verde com o valor de antes riscado. "Na planilha":
  o modelo escreve a FÓRMULA (rota de sempre) e o motor calcula; "Ordenar
  por vencimento" e "Destacar atrasados" são regra, sem modelo.
- `planilha.de_xlsx` traduz a fórmula do Excel (=SUM → =SOMA, vírgula →
  ponto e vírgula) e traz formato e negrito — antes a planilha importada
  mostrava #NOME? no total.
- Botão cheio no tema escuro: claro sobre escuro, como no pacote
  (`--primario`), em todo o programa.
- **Fica de fora:** "Destacar atrasados" não grava cor (a planilha do editor
  não guarda fundo de célula; a nota diz isso). Janela estreita (perto de
  900 px) deixa a ferramenta com 320 px.
- Assinar (`js/82-assinar-na-conversa.js`): "assine o contrato de
  honorários" (`intencao.ler_assinatura`: o verbo abre a frase e o resto
  nomeia UM documento; com .docx e .pdf do mesmo nome, o PDF) abre o PDF na
  coluna com o selo já posto no canto que o certificado guarda, e o chat
  traz o cartão em três passos (onde entra — Só a última, Todas, Primeira e
  última, Intervalo e a posição; com qual certificado; depois de assinar —
  Acervo, original, baixar, senha) com "1 assinatura · página 4", Cancelar e
  Assinar agora. O selo arrasta e muda de tamanho como na tela Assinatura
  (o mesmo código de js/17-assinar.js). Assinar continua pedindo o sim e a
  senha; com Aprovações no caminho, o cartão diz que falta o sim. O
  resultado entra na conversa (`/fazer` "assinatura", que confere que o
  assinado existe). O Assinar do visor e do editor abre o mesmo fluxo; só
  Word: a conversa diz que só assina PDF e oferece abrir o documento.
- Testes: `test_frontend`, `test_ferramentas`, `test_m5_leitura`,
  `test_escrita`, `test_planilha_excel`, `test_c2_pensando`,
  `test_c3_painel`, `test_intencao` e `test_c5_superficies` (sozinho) ok.
