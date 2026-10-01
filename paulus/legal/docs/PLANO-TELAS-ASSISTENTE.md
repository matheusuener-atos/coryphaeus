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
| T2 | Estados da conversa: `Conversa`, `Carregando`, `Feedback`, `Ditando`, `Foco`, `Apoiar`, `Gravando` (transcrição ao vivo com sugestões) | a fazer | |
| T3 | Documentos e ferramentas na coluna: `Documento`, `Editor`, `Planilha`, `Editor de planilha`, `PDF`, `Assinar`, `Agendar`, `Criar agente`, `E-mail`, `Escrever e-mail` | a fazer | |
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
