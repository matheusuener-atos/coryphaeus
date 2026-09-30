# PROGRESSO — A Conversa e os Agentes

Retomada do plano `docs/prompt-conversa-agentes-v0.md` (C0…C4, T1, T2, C5,
C6, A1…A4). Uma conversa nova, com o mesmo prompt, continua da primeira etapa
que não estiver `feita`.

| Etapa | O quê | Estado | Commit | Portão (medido) |
| --- | --- | --- | --- | --- |
| C0 | Levantamento, tabela e conversas de referência | feita | ver git log (c0) | tabela abaixo |
| C1 | Execução desacoplada da janela | feita | ver git log (c1) | desconectar no meio não perde nada; `desde=n` exato; parcial ao fechar o programa; A não vaza na B; roteiro 41/41 |
| C2 | A tela enquanto pensa | feita | ver git log (c2) | etapas do servidor desde o 1º evento; 0 nome na resposta salva; cartão = painel; 0 texto informativo em vermelho; Tentar de novo |
| C3 | Painel "Sobre esta resposta", barra de escopo, estado por conversa | feita | ver git log (c3) | ver fontes = daquela resposta; ≤ 1 contagem por resposta; rascunho e escopo por conversa; 390 px fechado; sem Progresso no fim |
| C4 | Roteamento: programa e cadastros | feita | b85c012 | 22/22 do programa na tela certa, sem modelo; 10 consultas de cadastro por molde, máx. 27 ms (antes ~165 s); 29/29 de documento no mesmo caminho |
| T1 | A saudação que não se repete | feita | ver git log (t1) | 130 títulos e 82 subtítulos; 30 aberturas sem repetir entre as 20 últimas; prazo hoje vence o dia; feriados e recesso; 0 buraco sem nome; 0,2 ms |
| T2 | Carrossel de avisos, Central de avisos e histórico | feita | f5a425e | 83 ok no portão: ordem, sem duplicado, visto por pessoa e de onde, volta no dia, 390 px, sem cor de erro |
| C5 | As outras superfícies de IA | feita, em parte | ver git log (c5) | documento errado corrigido; 1 leitor de SSE; parecer e resumo de gravação na fila, com posição, parar e resultado que volta; as outras 9 superfícies ficaram para depois |
| C6 | Cerca em todo texto de terceiros | pendente | — | — |
| A1 | Formato de agente: carregar, validar, versionar | feita | 98b228f | 67/67 no portão; permissões 58/58 |
| A2 | Agentes na conversa | feita | ver git log (a2) | @Nome, exemplo e "não usar"; instrução cercada abaixo das regras; ferramenta não declarada recusada; foco não lê outro documento; cartão = item da fila |
| A3 | Tela de agentes | pendente | — | — |
| A4 | Medir os agentes | pendente | — | — |

## Como este trabalho está sendo feito (30/09/2026)

- O dono pediu, às 05h de 30/09: "implemente agora esse .md referente ao chat
  do assistente (…) estou indo dormir, quando acordar quero tudo pronto
  publicado e commitado". Como na Biblioteca, **as pausas do prompt (C0 e A3)
  não param o trabalho**: o que seria mostrado nelas fica registrado aqui (a
  tabela e a ordem da C0; as capturas e os agentes de exemplo da A3), para o
  dono ver quando acordar. Publicar foi pedido; o prompt diria para
  perguntar antes.
- Trabalho no worktree `C:\coryphaeus-conversa` (branch por etapa, juntada à
  `main` da árvore principal), com o `venv` e `data/test_contracts` ligados
  aos da árvore principal por junção. A pasta `data/` do worktree é nova:
  testes que precisam de conversas ou documentos já existentes (a seleção
  múltipla do `test_tela`, por exemplo) só passam na árvore principal.
- Antes deste plano, na mesma madrugada, entrou o ajuste pedido junto: "se o
  modelo que faz transcrição estiver pesado e dando erro por ser pesado,
  sugerir ao usuário a substituição por um mais leve clicando aqui" (versão
  0.9.19, `tests/test_voz_mais_leve.py`).

## C0 — o prompt supõe × o código tem hoje

Leitura de 30/09/2026 sobre a `main` em `dbb8b67` (0.9.19).

### 1.1 Execução e persistência

| O prompt supõe | O código tem | Confere? |
| --- | --- | --- |
| Conversa em JSON; pergunta gravada no início, resposta só no fim; o texto sendo escrito só em `partes` | `jobs.py` (`Mensagem`, `Trabalho`, `Trabalhos.salvar`, `write_text` direto, não atômico); `trabalho.dizer("pessoa")` + `salvar` antes do gerador; `partes` dentro de `_gerar()` em `api.py` | sim |
| Geração presa à conexão; o `finally` marca parada; texto parcial perdido | `trabalhos_perguntar` devolve `StreamingResponse(gerar())`; o `finally` sai da fila, marca `PAUSADO` e **não** grava `partes` nem levanta `parar`: a thread do Ollama (`Ponte`) segue órfã, com a vez na fila já liberada | sim, e pior: a vez na fila é liberada com o modelo ainda ocupado |
| Reiniciar deixa "Parado · etapa N de M"; Retomar refaz do zero | `Trabalhos._carregar` troca `EXECUTANDO` por `PAUSADO` (as etapas ficam `executando`); `retomarTrabalho` → `enviar({retomar})` roda o pipeline inteiro | sim |
| Reentrada sem reconexão (`vigiarTrabalhoEmCurso` só com `!estado.ocupado`) | a condição existe; quando roda, só consulta a cada 3 s e redesenha no fim. Na própria página, `desenharTrabalho` troca `#centro` e o texto ao vivo vai para elementos soltos | em parte (o motivo principal é o DOM solto) |
| Vazamento entre conversas (painel, foco, título) | o laço de `enviar` chama `desenharTrechos`, `desenharProgresso`, `definirFoco`, escreve `conversa-titulo`, `rolar()` e `abrirAoFim` sem conferir a conversa | sim |
| "O que estou fazendo" nunca é salvo | `abrirBastidor`/`anotarBastidor` (`13-editor-na-conversa.js`) só no DOM | sim |
| Rascunho, escopo, rolagem, árvore e anexos perdidos ao trocar | `#pedido` único (o texto **passa** para a outra conversa); `modoEscopo` zerado em `abrirTrabalho`; `rolar()` sempre ao fim; árvore sempre fechada; `definirEscopo([])` | sim (o rascunho não se perde: vaza) |
| `enviar` calado com `estado.ocupado`; "Tentar de novo" sem ação | `if (estado.ocupado) return;`; o cartão de erro põe `data-recarregar`, que nenhum código trata | sim |
| Busca da lista só no título | `desenharListaDeConversas` filtra `titulo`; a lista recebe `Trabalho.resumo()`, sem mensagens | sim |

### 1.2 O que aparece enquanto pensa

| O prompt supõe | O código tem | Confere? |
| --- | --- | --- |
| Três contas de etapas; nomes do cliente ≠ do servidor | `cartaoPlano(dados.etapas, 2)` fixo; o servidor cria 2 etapas e acrescenta a 3ª ("Escrevendo a resposta"): fica "etapa 2 de 3"; o painel conta concluídas; ao reabrir, `etapa_atual`; o cliente começa com "Entender o pedido / Procurar e responder" | sim |
| "Sem trecho sobre isso em: …" com a lista inteira, em vermelho, num quadro bege, salva | a lista inteira (`perguntar.py`, `ignorados`); o vermelho é só na linha do bastidor (`.bastidor-linha.atencao` usa `--acc`); o quadro na resposta (`.aviso-cobertura`) é escuro, não bege; fica salva em `cobertura.ignorados` | em parte (cor e fundo) |
| A mesma contagem em quatro lugares | são cinco: registro, bastidor, botão das fontes, assinatura e o detalhe da etapa (na ordem inversa), mais o contador do painel | sim |

### 1.3 O painel lateral

| O prompt supõe | O código tem | Confere? |
| --- | --- | --- |
| Progresso, Trechos citados (da última com fontes; na verdade os enviados), Propriedades com "Motor" fixo, trechos indexados, pasta, modelo | `index.html` (`#lat-progresso`, `#lat-trechos`, `#lat-propriedades`); "Ollama · 127.0.0.1" fixo, nenhum JS escreve em `prop-motor`; `atualizarPropriedades` usa o estado global | sim |
| Nada é por resposta | nível, caminho, tempo, tokens, truncou: só na mensagem (`cobertura.como`) ou no bastidor | sim |
| No celular a gaveta abre por padrão | `lateralPreferida()` é verdadeiro sem nada gravado; abaixo de 1240 px vira gaveta de 320 px | sim |

### 1.4 A barra acima do campo

| O prompt supõe | O código tem | Confere? |
| --- | --- | --- |
| Mostra `atividade[0]`, 6 linhas no chevron, não atualiza durante a resposta, ponto verde fixo, `registrar()` sobe a conversa | `desenharAtividade` só em `desenharTrabalho` e no fim de `enviar`; `.ponto` com `--verde` fixo; `registrar` grava `atualizado_em`, e a lista ordena por ele | sim |

### 1.5 Roteamento

| O prompt supõe | O código tem | Confere? |
| --- | --- | --- |
| "Pra que serve a busca no DJE?" cai nos documentos | `intencao.ler` → `documentos`; `RE_O_QUE_E` casa "pra que serve", mas o candidato só nasce com o nome de uma tela (`_tela_citada`), e nenhum destino, apelido ou tela do `programa_mapa.json` cobre DJE, Publicações ou a busca Ctrl+K. Publicações moram em Agenda › To-do (`50-busca.js`, filtro "publicacoes"); a busca é `50-busca.js` + `GET /api/busca` | sim |
| "Qual o CPF do cliente Matheus" lê o acervo | `ler_cadastro` só trata cadastrar; a consulta `cadastros` do `programa.py` só conta e só aceita "clientes" no plural. O roteador do metadata reconhece "qual o cpf" (`inteligencia/roteador.py`), mas pega as pessoas de todos os documentos sem filtrar pelo nome e escala por ambiguidade | sim |
| (para a C4) os campos | `cadastros`: nome, documento (CPF **ou** CNPJ, numa coluna só, com máscara), telefone, email, endereco; **não há coluna de OAB** (só `pessoa.oab`/`escritorio.oab` nas preferências). `Cadastros.listar(termo=)` faz `LIKE`; o CPF dos documentos está no metadata (`dados["document"]` das pessoas) | — |

### 1.6 As outras superfícies de IA

| O prompt supõe | O código tem | Confere? |
| --- | --- | --- |
| A tabela de doze superfícies | confere linha a linha: editor ao lado da conversa (guarda na conversa, pode parar); painel de Documentos, papel timbrado e planilha (memória JS, não param); comentar (SQLite); resumo de gravação e de Serviços (SQLite, não param); Serviços conversar (a única, além da conversa, na fila do modelo); parecer do Financeiro e reescrever/rascunho de e-mail (memória JS); resumo da caixa e contexto (thread própria, memória do servidor); tomar vista, organizador (para pelo `cancelar`) e levantamento | sim |
| O bug do documento errado (`19-documentos.js`) | `pedirNoEditor` guarda só a URL; depois do `await`, `aplicarNoEditor` usa o `#ed-folha`, a seleção e o `escr.doc.id` da hora da resposta, e grava no documento aberto. O mesmo em `pedirNaFolha` e `pedirFormula`. O "Desfazer" também se perde (`escr.antes` é zerado ao trocar). O editor ao lado da conversa já trata o caso (`dupla.doc.id !== docId`) | sim |
| A fila do modelo furada | só a conversa e Serviços conversar entram; o juiz, a intenção de data, contextos, comentar, documento, folha, planilha, parecer, resumos e os quatro de e-mail chamam o Ollama direto | sim |
| Três leitores de SSE | `lerEventos` (`16-dialogos.js`), o laço do organizador (`14-organizador.js`) e o da conversa | sim |

### 1.8 A tela inicial

| O prompt supõe | O código tem | Confere? |
| --- | --- | --- |
| Saudação sem modelo, cinco títulos, dois ou três subtítulos | `contexto()` e `saudacao()` em `03-assistente.js`: os cinco títulos do prompt; quatro subtítulos (padrão, sem documentos, madrugada, noite alta) e duas frases de situação (conversa pela metade; documentos lidos) | sim |
| "Acontecendo agora" a cada 5 s | `carregarAgora` → `GET /api/agora` (executando com andamento, esperando, pausados); cartões `.cartao-agora` (`03-compositor-e-agora.css`) | sim |
| Avisos espalhados, nada "visto", sem histórico | `prazos.py` é só a calculadora (os prazos processuais viram tarefas); agenda (`compromissos`), tarefas, publicações (`publicacoes`, com `lida`), financeiro (`lancamentos`, `precisa_de_voce`), vencimentos do metadata (`ajuda.prazos`, um documento por vez, e `tarefas.sugerir` do cache), aprovações (`Fila.para_tela`); o `Vigia` (`avisos.py`) só dispara a notificação do Windows, com memória em dicionários, sem ids estáveis nem "visto" | sim |
| Nome de quem entrou; aniversário do escritório | `preferencias.pessoa.nome` (e `escritorio.nome`); de fora, `GET /api/acesso/eu` → `pessoa.nome`. **Não há data de aniversário do escritório** em lugar nenhum: a T1 acrescenta `escritorio.fundacao` nas preferências | em parte |

### 1.7 Agentes e skills

| O prompt supõe | O código tem | Confere? |
| --- | --- | --- |
| Não há agente nem skill em markdown; habilidades em Python com validação e recarga | nenhum SKILL.md/AGENTS.md; `Habilidade` (`habilidade_base.py`) com `id, nome, resumo, grupo, estado, acao, precisa, detalhe, demora, ordem`; `registro.py` vira "Com problema" com mensagem clara; a recarga é manual (`POST /api/habilidades/recarregar`); 9 habilidades: abrir, assinar, buscar, classificar, ocr, organizar, perguntar, redigir, vencimentos | sim |
| Só lembretes (600 caracteres, 4 gavetas, sempre ligados, sem versão) | `contextos.py`: `MAX_TEXTO = 600`, 4 gavetas, `LIMITE_BLOCO = 2400`, sem coluna de ativo nem versão | sim |
| Três catálogos que não se conhecem | `CATALOGO_FERRAMENTAS` (cadastrar_cliente, criar_compromisso, exibir_documento, emitir_nfse — esta `disponivel: False`); `exige_confirmacao` é só declarativo; `/fazer` também grava abrir, tarefa e serviço, fora do catálogo | sim, com a ressalva do `/fazer` |
| A conversa não mostra a habilidade; "/" é menção | `perguntar` é sempre a habilidade da rota; `termoDaMencao()` | sim |
| Dois caminhos de aprovação; sem auditoria | na janela local, `/fazer` grava direto; de fora, a rota é PROPOR e vira `acesso.proposta` na fila; `acesso/auditoria.py` só registra o acesso de fora | em parte (de fora já passa pela fila) |
| Blindagem só no e-mail | `blindagem.py` (`limpar`, `cercar`, `suspeitas`, `aviso`, `conferir_saida`) no `correio.py`; a camada COMUNIDADE da Biblioteca já cerca, mas sem a `REGRA` no prompt | em parte |
| Sem código "Coryphaeus" na raiz | confere | sim |
| (para a A1) YAML | só `config/extratores.yaml`, lido com `yaml.safe_load`; **PyYAML não está no `requirements.txt`** (vem como dependência do huggingface_hub) | — |

### Por etapa

| Etapa | Situação na C0 |
| --- | --- |
| C1 | a fazer |
| C2 | a fazer |
| C3 | a fazer |
| C4 | a fazer |
| T1 | a fazer |
| T2 | a fazer |
| C5 | a fazer |
| C6 | em parte (a cerca existe no e-mail e na COMUNIDADE) |
| A1…A4 | a fazer |

**Ordem:** a do prompt (C1 → C2 → C3 → C4 → T1 → T2 → C5 → C6 → A1 → A2 →
A3 → A4). Nada no código pede outra.

### As duas conversas de referência

Do roteiro da demonstração (`tools/demo/roteiro.py`), medidas em 30/09 com o
llama3.2:3b nesta máquina e a execução da C1 ligada:

- **longa, que lê os documentos:** "o que acontece se a Rio Fresco não
  regularizar as entregas no prazo?" — 48,9 s (consequência; lê o contrato e a
  notificação);
- **curta, de nível 0:** "quanto são os honorários fixos do João Batista?" —
  0,3 s (pelos fatos já conferidos, sem o modelo).

`roteiro.py --so "regularizar as entregas"` e `--so "honorários fixos"` rodam só
uma delas.

## C5 — o que foi medido e decidido

- **O bug do documento errado** (primeiro, como pedia o contrato): o painel de
  Documentos guarda o documento que fez o pedido. Se a resposta chega com
  outro aberto, ela não toca nele: fica esperando o de origem (nesta janela)
  e aparece marcada no fim dele quando ele abre, com Manter e Descartar. A
  folha timbrada vai para o documento de origem pelo servidor, aberto ou não.
  A fórmula da planilha nunca cai em outra planilha (e o Manter confere).
- **Um leitor de SSE só:** `eventosSSE` (`16-dialogos.js`), um gerador
  assíncrono; o `lerEventos`, o organizador e a conversa passaram a usá-lo, e
  o `break` fecha a leitura.
- **As chamadas de IA como execução** (`src/ia_em_fundo.py`,
  `POST /api/ia/{tipo}`): o parecer do Financeiro, o resumo da gravação e o
  reescrever do e-mail rodam como execução do mesmo registro da C1, com a vez
  na fila do modelo (a posição aparece: "Na fila do modelo: você é o 2º"),
  Parar (`POST /api/execucoes/{id}/parar`) e o resultado guardado no registro.
  A inscrição lê do disco a execução de antes de reabrir o programa, então
  sair da tela, recarregar ou reabrir e voltar mostra o resultado. Um
  componente só na tela (`frontend/js/56-ia-em-fundo.js`: `blocoIA`,
  `chamarIA`, `acompanharIA`). Ligados na tela: o parecer e o resumo da
  gravação. A rota nova é só da janela do escritório; de fora, as telas usam
  a rota de antes.
- **Ficou para depois, e por quê:** as outras nove superfícies (painel de
  Documentos, folha e planilha como execução; comentar; resumo e perguntar de
  Serviços; reescrever e rascunho de e-mail na tela; resumo da caixa;
  organizador e levantamento) continuam como antes — o componente e a rota
  genérica estão prontos para elas, uma por uma, cada uma com o próprio
  "sair e voltar". O texto chegando aos poucos (streaming) no parecer e nos
  resumos também ficou de fora: as funções de hoje pedem ao modelo a
  resposta inteira. **A fila do modelo continua furada** para as superfícies
  não convertidas: pôr a fila dentro do cliente do modelo pediria levar a
  marca de "já tenho a vez" para as threads que a conversa abre, e um erro ali
  trava o programa; não foi feito sem poder medir.
- Chave `conversa.superficies`, **ligada de fábrica** depois do portão.

**Medido:** `tests/test_c5_superficies.py` — um só `getReader()` na tela; com
a conversa respondendo, o parecer entra na fila, diz a posição e depois
devolve o JSON de antes; tirada da memória (reabrir), a execução devolve o
resultado do disco; parar funciona; com a chave desligada, 409. No Edge:
pedir a sugestão no A e trocar para o B deixa o B intacto (na tela e no
servidor), e o A, ao abrir, mostra a sugestão marcada; o parecer guardado
aparece ao voltar ao Financeiro.

## T2 — o que foi medido e decidido

Feita por um agente num worktree à parte (`C:\coryphaeus-t2`), com o contrato
inteiro, e juntada aqui.

- `src/central_avisos.py` junta prazo processual (lista "Prazos" ou tarefa
  tirada do DJEN), compromisso (hoje e amanhã), data de documento do Acervo, a
  pagar e a receber (até 7 dias ou atrasado), publicação nova do DJEN, tarefa
  do dia ou atrasada, aprovação esperando, conversa pela metade e lembrete do
  Vigia vencido, sem mudar a regra de nenhuma fonte.
- Ids pela origem e pela data (`prazo:<id>:<data>`, com `:antes` antes do dia:
  o "em 3 dias" visto não esconde o "vence hoje"). Atrasado e "no dia" têm o
  mesmo id: o atrasado visto não volta todo dia. O mesmo prazo na Agenda e em
  Tarefas é um aviso só.
- Tabela `avisos_vistos` (migração 026): pessoa (`local`/`conta:<id>`), hora,
  de onde, cópia do título e do "quando". O titular vê os vistos de todos no
  histórico e só desmarca os próprios.
- Rotas em `/api/central-avisos/…` (`/api/avisos` já era dos avisos do
  Windows), PERMITIDO de fora; o que cada pessoa recebe segue a política da
  rota de origem, e a ação direta do colaborador vira proposta em Aprovações.
- Ações diretas ("Concluir tarefa", "Marcar como pago/recebido") sempre
  perguntam antes, com o diálogo do sistema — as telas de origem não pedem.
- O Vigia usa os mesmos ids e não notifica o que já foi visto na janela local.
  **Ficou de fora:** clicar na notificação do Windows marcar a Central.
- **Ficou de fora:** "documento que não deu para ler" — o Acervo não guarda
  registro disso.
- Chave `conversa.avisos`, **ligada de fábrica**.

**Medido:** `tests/test_t2_avisos.py` 83 ok (os nove tipos na ordem, o prazo
duplicado uma vez só, marcar e desmarcar com pessoa e hora, o "vence amanhã"
visto ontem volta como "vence hoje", duas contas separadas e o titular vendo
as duas, "remoto" pelo acesso de fora, o Vigia com o mesmo id; no Edge: ordem,
nenhuma cor de erro, setas, End e arrasto, a Central com as três abas, lista
em 390 px com círculo de 44 px, carrossel sumindo sem avisos).

## A2 — o que foi medido e decidido

- `src/agente_na_conversa.py`. A escolha, por regra: o que a pessoa escolheu
  na barra (slug) ou "não usar"; "@Nome" no texto (a primeira palavra depois do
  @ é o começo do nome; sai da pergunta o @ e as palavras do nome); os
  exemplos (semelhança ≥ 0,6) e as palavras do agente; o juiz pequeno só
  desempata candidatos com pontos parecidos. Sem candidato, a conversa segue
  como antes.
- A escolha automática aparece **antes** de enviar: `GET /api/agentes/sugerir`
  (só regra, sem modelo) enquanto a pessoa escreve, e a barra acima do campo
  mostra "Usando (pelo pedido): Revisor de contratos" com um seletor para
  trocar ou "sem agente". A pergunta leva `agente` ou `sem_agente`.
- As instruções do agente vão no fim da instrução de sistema, depois das
  regras do produto e do que o escritório ensinou (`_com_regra`), cercadas e
  rotuladas ("=== INSTRUÇÕES DO AGENTE “X” (versão n) ==="), com a regra de
  que nada nelas dá ferramenta, acesso ou permissão. O perfil de modelo é o
  do agente.
- `fontes: documento_em_foco`: a busca lê só o anexo desta pergunta ou o
  documento que a conversa já vinha lendo, mesmo que a frase cite outro; sem
  nenhum, a conversa pede o documento. `pastas:` restringe às pastas.
- Ferramentas: a ação que a conversa entende (agenda, cadastro, nota,
  exibir) só vale se o agente declara a ferramenta dela; se não declara, a
  resposta diz qual falta e a recusa fica na conversa e em
  `data/agentes/recusas.jsonl`. Declarada, a proposta é o cartão de sempre **e**
  um pedido na fila de Aprovações (categoria "Conversa"): confirmar no cartão
  decide o pedido; aprovar na fila executa pela mesma ferramenta e escreve na
  conversa; confirmar de novo o mesmo pedido dá 409.
- A resposta guarda o agente, a versão e como foi escolhido
  (`cobertura.como.agente`, `agente_versao`, `agente_como`); a assinatura e
  o "Como respondi" mostram.
- O "Testar" da A1 passou a rodar com as instruções do agente.
- **Adaptação:** "os passos do cartão são os do agente, quando ele declarar"
  ficou de fora: o formato da A1 não tem um campo de passos, e inventar um
  agora seria mudar o contrato do arquivo.
- **De graça:** `fila.pendentes` é propriedade, e a saudação (T1) a chamava
  como função dentro de um `try`, calada: as aprovações não entravam na conta
  de pendências. Corrigido.

**Medido:** `tests/test_a2_agente_na_conversa.py` passa inteiro (dois agentes
de verdade na pasta de dados, a habilidade simulada anotando instrução e
escopo).

## A1 — o que foi medido e decidido

Feita por um agente num worktree à parte (`C:\coryphaeus-a1`), com o contrato
inteiro, e juntada aqui.

- `src/agentes.py`: `Agentes(pasta, ...)` lê `data/agentes/<slug>/AGENTE.md`
  (cabeçalho YAML + instruções) a cada consulta, sem cache, e valida contra as
  capacidades carregadas (`estado.registro`), o `CATALOGO_FERRAMENTAS`, os
  perfis de modelo, as áreas da Biblioteca e as leis. Erro de digitação num
  campo também é erro, com sugestão. `modelo: llama3.2:3b` é recusado (é
  perfil de tarefa). Avisos que não bloqueiam: ferramenta indisponível (a
  NFS-e), agente sem testes, sem exemplos.
- Estado em `estado.json` ao lado do arquivo (ligar não é edição e não gera
  versão); a versão fica no cabeçalho, e cada edição guarda a anterior em
  `versoes/<n>.md`, mudando só a linha `versao:`.
- Importar: `name`/`description` → `nome`/`descricao`, campos de outro
  programa listados na ficha, `original.md` guardado, suspeitas da blindagem
  anotadas; entra desligado e só liga com `vi_o_conteudo: true`, com quem
  aprovou.
- Rotas (`src/rotas_agentes.py`): ler e testar, PERMITIDO; criar, salvar,
  ativar, desativar e importar, TITULAR. O teste da A1 roda as perguntas sem
  as instruções do agente e diz isso (a A2 põe o agente na conversa).
- `pyyaml` entrou no `requirements.txt` (já vinha pelo huggingface_hub).
- Chave `conversa.agentes`, **ligada de fábrica**: sozinha, não muda nada na
  conversa.

**Medido:** `tests/test_a1_agentes.py` 67/67; `tests/test_r3_permissoes.py`
58/58 (477 pares de rota com política).

## C4 — o que foi medido e decidido

Feita por um agente num worktree à parte (`C:\coryphaeus-c4`), com o contrato
inteiro, e juntada aqui.

- Mapa ampliado (`programa_mapa.json`, marcas `c4`): Publicações e DJE (moram
  em Agenda › To-do), Buscar em tudo (Ctrl+K), Biblioteca (o destino
  `habilidades`, que a tela chama de Biblioteca), Códigos de lei e Acesso de
  fora, com 4 ou 5 perguntas cada, e mais 5 em Agenda, To-do e Aprovações;
  cada passo com o arquivo:linha do frontend. O botão "Abrir" leva a cada
  lugar de verdade (`abrirTelaDaConversa`). **Agentes** fica para quando a
  tela existir (A3).
- Regras novas, só com a chave: nome contido em outro não conta ("busca no
  DJE" é Publicações), a tela de dentro vence, "busca e apreensão" não é tela,
  termo com "=" só casa junto, o empate desempata pelo verbo, "como funciona
  X" com tela citada responde pela tela.
- Consulta de cadastro (`src/consulta_cadastro.py`): CPF, CNPJ, telefone,
  e-mail, endereço e OAB de alguém, por molde: Cadastros → Meus dados → fatos
  conferidos dos documentos (com documento e página) → "não encontrei", com a
  oferta de ler os documentos (só com o clique). Nome ambíguo vira lista; CPF
  pedido com CNPJ cadastrado diz o que há. **Exceção de propósito:** CPF, CNPJ
  ou OAB de um nome que não está em lugar nenhum e sem "do cliente" na frase
  segue para os documentos, como antes ("qual o CNPJ da Transportes Rio
  Fresco?" é do banco de provas).
- De graça: os passos "clique em Aprendizado" (a seção não existe mais)
  viraram "Biblioteca".
- Chave `conversa.roteamento`, **ligada de fábrica** depois do roteiro com o
  modelo (abaixo).

**Medido:** `tests/test_c4_roteamento.py` — 22/22 perguntas sobre o programa
na tela certa, sem modelo nem juiz; 10 consultas de cadastro pela API por
molde, máx. 27 ms (antes ~165 s lendo 21 documentos); pelos fatos, 17 ms;
banco de provas: 29/29 de documento no mesmo caminho, 0 viraram programa ou
cadastro; com a chave, 36/36 de `test_programa` e 34/34 da regressão da
inteligência nos documentos.

## T1 — o que foi medido e decidido

- O banco (`config/saudacoes.json`): 130 títulos e 82 subtítulos escritos
  aqui, com as cinco frases de antes dentro dele. Condições: momento (oito
  faixas), dia, calendário, chegada e situação; marcas `{nome}`, `{conversa}`,
  `{feriado}`, `{prazo}`, `{n_prazos}`, `{pendencias}` — frase com marca só vale
  quando a marca tem valor (sem nome, nenhuma frase com nome).
- A escolha (`src/saudacao.py`), no servidor e sem modelo: a situação forte
  (prazo hoje, vários prazos, acervo vazio, muita pendência) fica sozinha e
  nunca cede; as outras camadas, da mais específica para a mais geral —
  situação, chegada, calendário, madrugada/noite alta, dia, "tudo em dia",
  momento, geral —, cedendo a vez quando todas as frases de uma camada estão
  entre as 20 últimas mostradas. **Ajuste medido pelos exemplos:** "tudo em
  dia" ficou abaixo do calendário (senão o Natal dizia "Tudo em dia por
  aqui") e madrugada acima do dia (às 3 h de uma terça saía "a semana está na
  metade").
- Feriados e recesso: `src/prazos.py` (a tabela dos prazos, com Carnaval,
  Sexta-feira Santa e Corpus Christi pela Páscoa, e o recesso de 20/12 a
  20/01). Prazo de hoje = tarefa aberta da lista "Prazos" com prazo hoje.
  Pendências = tarefas atrasadas + aprovações esperando.
- A tela (`frontend/js/55-saudacao.js`) manda as 40 últimas frases vistas
  (títulos e subtítulos), a abertura anterior e a última conversa aberta; a
  frase de antes aparece na hora e é trocada quando a resposta chega. "De
  volta. Seguimos com “X”?" tem o título da conversa como atalho para abri-la.
- `escritorio.fundacao` (AAAA-MM-DD) entrou nas preferências para o
  aniversário do escritório. **Falta:** um campo para ela em Configurações;
  hoje só por `POST /api/preferencias`.
- Chave `conversa.saudacao`, **ligada de fábrica** depois do portão.

**Dez exemplos** (um de cada tipo de condição, do teste):

- madrugada: “Silêncio lá fora. Bom momento para adiantar.” / “Uma pergunta
  de cada vez, sem pressa.”
- manhã de segunda: “Boa segunda, Helena. A semana começa aqui.” / “Pergunte
  que compromissos a agenda tem esta semana.”
- fim de tarde de sexta: “Boa sexta, Helena. Algo para encerrar?” / “Pergunte
  que tarefas ficaram abertas nesta semana.”
- domingo, 11/10 (véspera de Nossa Senhora Aparecida): “Véspera de feriado.
  Deixamos tudo pronto?” / “Na conta de um prazo, o feriado não entra como dia
  útil.”
- fim de mês: “O mês está chegando ao fim. Tudo encaminhado?” / “Pergunte
  quanto está para receber este mês.”
- 25/12: “Natal e você por aqui? Eu ajudo.”
- recesso (12/01): “Recesso forense, Helena. O que fica para depois do dia
  20?” / “Pergunte o que vence logo depois do recesso.”
- volta rápida: “Helena, de volta. Continuamos com “Contrato ACME”?” / “A
  conversa continua de onde parou.”
- prazo hoje: “Helena, tem prazo vencendo hoje. Começamos por ele?” / “Abra o
  cartão do prazo, ou pergunte sobre o processo dele.”
- acervo vazio, sem nome: “Primeiro passo: me mostre os documentos do
  escritório.” / “O que eu ler fica neste computador. Comece pela pasta do
  escritório.”

**Medido:** `tests/test_t1_saudacao.py` — 30 aberturas seguidas sem repetir
entre as 20 últimas; prazo hoje fala do prazo nos sete dias da semana e no
Natal; 25/12, Sexta-feira Santa, Carnaval e 10/01 escolhem frases dessas
condições; 672 aberturas sem nome e nenhum buraco; nenhum título acima de 90
caracteres com as marcas no tamanho máximo; 0,2 ms por escolha, sem modelo; na
tela, três aberturas, três frases.

## C3 — o que foi medido e decidido

- O painel descreve **uma** resposta (`frontend/js/54-sobre-a-resposta.js`):
  a última com fontes, ou a clicada em "ver fontes". "Fontes citadas" são as
  marcas [Tn] do texto, com a numeração da resposta; sem marcas, o título é
  "Trechos lidos". O que foi lido e não citado vai para "Também lidas",
  recolhido. "Como respondi" e "Onde procurei" saem do que a resposta guardou
  (`cobertura.como` ganhou modelo, escopo, continuação e truncou); resposta
  antiga, sem esses campos, mostra só o que houver.
- O Progresso sai do painel (mora na linha de estado da C2). Motor, trechos
  indexados e pasta só com `conversa.diagnostico` (desligada); o motor vem do
  `/api/status` (`motor.host`), e não do "127.0.0.1" fixo do HTML.
- A barra acima do campo diz o que vai acontecer com a próxima pergunta ("A
  próxima pergunta procura em todo o Acervo · 29 documentos"); com uma
  resposta andando nesta conversa, o que ela faz e o Parar. A lista de
  atividade sai dela; o registro continua em "ver detalhes".
- `Trabalho.registrar(mexer_na_ordem=False)`: uma linha de registro não sobe
  a conversa na lista.
- Por conversa: rascunho, anexos pendentes e rolagem no `localStorage`
  (`paulus.conversa.<id>`); o modo de escopo no servidor
  (`POST /api/trabalhos/{id}/escopo`, em `contexto.modo_escopo`).
- A segunda pergunta com outra respondendo diz "A conversa “X” ainda está
  respondendo" e oferece "Esperar na fila": ela vai sozinha quando a primeira
  termina. (Com a execução da C1, a pergunta numa outra conversa já vai, e a
  fila do modelo mostra a posição.)
- No celular (< 600 px) o painel começa fechado e abre como folha de baixo.
- A busca de conversas procura também no texto das mensagens
  (`GET /api/conversas/buscar`, sem acento).
- **Adaptação:** as chaves da conversa (`painelNovo()`, `diagnostico()`)
  ficaram em `00-base.js`: o código que roda na abertura, antes dos arquivos
  de cada etapa, já as consulta.
- Chave `conversa.painel`, **ligada de fábrica** depois do portão.

**Medido:** `tests/test_c3_painel.py` passa inteiro (modelo simulado e o
Edge, em 1440 e em 390 px).

## C2 — o que foi medido e decidido

- A linha de estado fica dentro da resposta, até a primeira palavra: "Um
  instante…" → "Procurando em 29 documentos…" → "Lendo 1 documento · ~42 s…"
  → "Escrevendo…". A estimativa só aparece acima de 10 s e vem do ritmo
  medido nesta máquina.
- O "o que estou fazendo" nasce recolhido, com o nome "ver detalhes". Na
  resposta guardada, as linhas saem do registro da execução
  (`src/detalhes.py`), e não do navegador: `cobertura.detalhes`, com o
  `execucao_id`.
- A resposta guardada leva `ignorados_n` e a lista vazia; ao vivo, a lista
  fica recolhida em "ver lista". A linha do bastidor diz só a contagem.
- As etapas: o servidor manda `etapas` logo depois do id, com os nomes dele, e
  a tela não desenha as suas. Cartão e painel usam a mesma conta
  (`etapaAtual`: a que executa, ou a última concluída).
- Vermelho só para erro: `.pensando .bastidor-linha.atencao` usa `--ink2`, e só
  a linha de erro do "ver detalhes" (`.erro`) usa `--acc`. O aviso de
  cobertura já era escuro (`--destaque`), e não vermelho.
- "Tentar de novo" refaz a pergunta na mesma conversa.
- Chave `conversa.pensando` (a casca a lê em `/api/preferencias` e marca a
  raiz com `.pensando`), **ligada de fábrica** depois do portão.

**Medido:** `tests/test_c2_pensando.py` — as etapas do servidor chegam logo
depois do id; a resposta salva não tem nenhum dos 12 nomes (só a contagem) e
tem o "ver detalhes"; na tela, a linha de estado com a estimativa, cartão e
painel com a mesma conta em 14 amostras, nenhum texto informativo na cor de
erro, a lista recolhida, a resposta reaberta só com a contagem, e o "Tentar de
novo" fazendo a pergunta de novo; com a chave desligada, a resposta salva
como antes.

## C1 — o que foi medido e decidido

- `src/execucoes.py`: a execução (id, conversa, dono, tipo, estado) com o
  registro só acrescentado, na memória e em `data/execucoes/<id>.jsonl`, uma
  linha por evento gravada na hora; `inscrever(desde=n)` entrega o que houve
  depois de `n` e continua ao vivo. `src/rotas_execucoes.py`: a inscrição
  (`GET /api/execucoes/{id}/eventos?desde=`) e a execução da conversa
  (`GET /api/trabalhos/{id}/execucao`), PERMITIDO como as rotas da conversa.
- **Adaptação:** a rota da pergunta continua devolvendo SSE, mas agora é uma
  inscrição desde o evento 0 na execução que ela cria (o primeiro evento é
  `execucao`, com o id). Assim o frontend de antes continua lendo do mesmo
  jeito, e a thread de trabalho é a que consome o gerador de sempre - a
  lógica de responder não mudou.
- A tela: a leitura dos eventos saiu de `enviar()` para `lerResposta()`; todo
  efeito fora da resposta (título, foco, painel, rolagem, abrir tela no fim)
  só vale com a conversa dela aberta. Trocar de conversa larga a inscrição
  (a resposta segue no servidor); voltar ou recarregar se reinscreve desde o
  0 (`acompanharExecucao`) e redesenha etapas, "o que estou fazendo" e o
  texto que já saiu.
- **Texto parcial ao fechar o programa:** ao abrir, o registro sem evento de
  fim vira mensagem com o texto parcial, `interrompida`, com as fontes que já
  tinham chegado, e a conversa fica parada. **Adaptação:** "Continuar" é o
  Retomar de sempre (a pergunta de novo, trocando o texto parcial);
  continuar o texto do ponto em que parou pediria mandar o parcial ao modelo
  como começo da resposta, e isso não foi medido.
- De graça: antes, fechar a janela deixava a thread do Ollama órfã com a vez
  na fila já liberada (a próxima pergunta entrava com o modelo ocupado).
  Agora a vez só sai quando a resposta acaba.
- Retenção: registro com mais de 30 dias vira `<id>.resumo.json` (etapas,
  medida, contagem por tipo, fim), sem o texto, ao abrir o programa.
- Chave `conversa.execucao`, **ligada de fábrica** depois do portão.

**Medido:** `tests/test_c1_execucao.py` — desconectar no meio: a resposta
termina e fica inteira; `desde=8` entrega do 9 ao fim, sem repetir nem pular;
dois inscritos, a mesma sequência; registro sem fim em disco vira texto
parcial interrompido, uma vez só; parar a A não para a B; com a chave
desligada, o gerador de antes. Na tela (Edge): com a A respondendo, a B
mantém título, texto e painel; voltar à A mostra a resposta inteira;
recarregar no meio mostra a resposta do começo, e ela termina ao vivo; nenhum
erro de JavaScript. Roteiro `--tudo` com a execução ligada: **41/41**
(controle 40/41).
