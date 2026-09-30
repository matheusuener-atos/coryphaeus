# PROGRESSO — A Conversa e os Agentes

Retomada do plano `docs/prompt-conversa-agentes-v0.md` (C0…C4, T1, T2, C5,
C6, A1…A4). Uma conversa nova, com o mesmo prompt, continua da primeira etapa
que não estiver `feita`.

| Etapa | O quê | Estado | Commit | Portão (medido) |
| --- | --- | --- | --- | --- |
| C0 | Levantamento, tabela e conversas de referência | feita | ver git log (c0) | tabela abaixo |
| C1 | Execução desacoplada da janela | feita | ver git log (c1) | desconectar no meio não perde nada; `desde=n` exato; parcial ao fechar o programa; A não vaza na B; roteiro 41/41 |
| C2 | A tela enquanto pensa | feita | ver git log (c2) | etapas do servidor desde o 1º evento; 0 nome na resposta salva; cartão = painel; 0 texto informativo em vermelho; Tentar de novo |
| C3 | Painel "Sobre esta resposta", barra de escopo, estado por conversa | pendente | — | — |
| C4 | Roteamento: programa e cadastros | pendente | — | — |
| T1 | A saudação que não se repete | pendente | — | — |
| T2 | Carrossel de avisos, Central de avisos e histórico | pendente | — | — |
| C5 | As outras superfícies de IA | pendente | — | — |
| C6 | Cerca em todo texto de terceiros | pendente | — | — |
| A1 | Formato de agente: carregar, validar, versionar | pendente | — | — |
| A2 | Agentes na conversa | pendente | — | — |
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
