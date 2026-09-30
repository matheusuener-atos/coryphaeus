# PROGRESSO — Pensar no aparelho (acesso de fora)

Retomada do plano `docs/prompt-pensar-no-aparelho-v0.md` (D0…D6 e F1). Uma
conversa nova, com o mesmo prompt, continua da primeira etapa que não estiver
`feita`.

| Etapa | O quê | Estado | Commit | Portão (medido) |
| --- | --- | --- | --- | --- |
| D0 | Levantamento e medida da fila remota | feita — ⏸ PAUSA: esperando a decisão do dono | ver git log (d0) | tabela e números abaixo |
| F1 | Fila dentro da conversa, fila única, Ctrl+Enter | feita; chave `aparelho.fila` desligada de fábrica — ⏸ o dono decide se seguimos | ver git log (f1) | `tests/test_f1_fila.py` 49 ok (ordem, pendente, 429, Ctrl+Enter com e sem liberação, auditoria, e-mail na mesma fila, Edge) |
| D1 | O pacote e a porta | feita; chave `aparelho.ligado` desligada de fábrica | ver git log (d1) | `tests/test_d1_pacote.py` 30 ok |
| D2 | O motor no navegador | feita (com a D2b: o 3B em partes) | ver git log (d2, d2b) | `tests/test_d2_motor.py` 30 ok; o 3B de verdade no Edge: carrega em 23 s, 4,3 tokens/s, resposta certa |
| D3 | Conferência no escritório e retomada | feita | ver git log (d3) | `tests/test_d3_conferencia.py` 9 ok |
| D4 | O switch e a tela | feita | ver git log (d4) | `tests/test_d4_switch.py` 40 ok |
| D5 | O que o titular controla | feita | ver git log (d5) | `tests/test_d5_titular.py` 29 ok |
| D6 | Política, manual e teste real | ⏸ esperando o teste real do dono | ver git log (d6) | roteiro abaixo |

## D0 — o prompt supõe × o código tem hoje (30/09/2026)

### A fila

| O prompt supõe | O código tem hoje |
| --- | --- |
| Fila única, ordem de chegada, 2 por pessoa, posição e previsão pelo `ritmo.py` | Confere. `src/fila_modelo.py`: uma lista global, `MAX_POR_PESSOA = 2` (a que está sendo respondida conta), previsão = mediana de (lendo + escrevendo) das 25 últimas leituras. O dono é `"local"` ou `"conta:<id>"`: **todo mundo na janela do escritório divide o mesmo `"local"`**. A fila vive só na memória. |
| 3ª pergunta da mesma pessoa: 429 antes de salvar | Confere na conversa (`cabe()` antes de gravar, `api.py` ~3516) e em Serviços. Na tela, o 429 vira "Não consegui responder: Error: <detalhe>" dentro da resposta, sem aviso próprio. |
| Só a conversa e Serviços entram | Entram: conversa, Serviços › conversar, o teste de agente e, pela C5 (`ia_em_fundo`), o parecer e o resumo de gravação — **só na janela local** (`/api/ia/{tipo}` é BLOQUEADO de fora). **Fora da fila:** editor (comentar, folha, assistente), planilha, os resumos e rascunhos de e-mail (a caixa tem uma fila própria de 1+1), reescrever e-mail (a tela ainda chama a rota antiga), resumo de Serviço, parecer e resumo de gravação pelas rotas antigas (de fora é por elas, e o resumo de gravação abre para quem tem "faz"), a classificação (espera CPU livre, não a fila), o juiz do agente e o do programa, as ações da conversa sem documento. |
| Trabalho de segundo plano cede com `ceder()` | Confere: índice do material, leitura das obras (M5) e vetores do Acervo. |
| Sem prioridade | Confere: nenhum campo de prioridade em lugar nenhum. |
| Perguntas de molde (nível 0) não entram | Confere (`_sem_modelo()`). Dentro da vez, o modelo pode ser chamado mais de uma vez (nível 0 sem stream e a repetição de `_conferir_marcas`). |

### A conversa na tela

| O prompt supõe | O código tem hoje |
| --- | --- |
| Com resposta andando, `enviar()` sai calado | **Em parte já mudou (C3).** Com `conversa.painel` ligado (de fábrica), aparece o aviso "A conversa “…” ainda está respondendo." com **Esperar na fila**, que guarda a pergunta **só na memória da página** e a manda quando a outra termina. Ela se perde, sem aviso, se a pessoa trocar de conversa ou recarregar; cabe uma só (a segunda sobrescreve); não aparece na conversa. Com a chave desligada ou o campo vazio, sai calado. |
| Em outra conversa o botão fica "esperando" | Confere. E se o `execucao_id` já chegou, trocar de conversa larga a inscrição e libera o envio na outra; a fila do servidor dá a posição pelos eventos `fila`. |
| Ctrl+Enter não faz nada especial | Confere: o campo trata `Enter` sem Shift como enviar (`03-assistente.js` ~2058, não ~1790); Ctrl+Enter cai no mesmo caminho. O Ctrl global só age em Aprovações. |
| Pergunta pendente guardada no servidor | Não existe. A pergunta vai direto para `trabalho.mensagens`; `NA_FILA` existe em `jobs.py` mas a conversa não usa. |
| Posição à vista | Eventos `fila {posicao, previsao_s}` viram "na fila do modelo: você é o Nº, ~X s" na linha de estado (com `conversa.pensando`) e nos cartões de Acontecendo agora. Não diz **quem** está na frente. |

### A pergunta, as conferências e o painel

| O prompt supõe | O código tem hoje |
| --- | --- |
| Trechos escolhidos, orçamento ~3.000 tokens | Confere no caminho "trechos" (`recuperacao.py`: até 6 trechos, 3.000 tokens, 3 por documento). Mas há outros caminhos: "tudo" (o Acervo inteiro quando cabe), documento nomeado e o nível 0 de fatos — **o pacote do aparelho só pode sair do caminho de trechos**. |
| 2 últimos pares, cortados | Confere: `memoria.historico`, 2 pares, 600 tokens. |
| Conferências: números, marcas, lei fora dos trechos, cerca | Existem, mas **espalhadas e quase todas desligadas de fábrica**: `citacoes.revisar` (marca e lei/súmula/CNJ fora dos trechos) só com `ia.citacao` (desligada) ou com camadas da Biblioteca; números/datas/CPF só no nível 0 (`molde.conferir`); a cerca (`blindagem.tirar_estranhos`) com `conversa.cerca` (desligada). **Não há uma função única** que confira um texto pronto: D3 precisa escrevê-la, e a resposta do escritório tem de passar por ela também ("a mesma função"). |
| Painel da resposta | Existe (C3): Caminho, Tempo, Modelo, Agente… Nenhum campo diz **onde** a resposta foi escrita. |
| Execução desacoplada | Existe (C1): thread por resposta, eventos em `data/execucoes/<id>.jsonl`. As rotas de inscrição não conferem o dono (id aleatório de 16 hex). |

### Acesso de fora e segurança

| O prompt supõe | O código tem hoje |
| --- | --- |
| Filtro de permissões (papel, muralha ética, escopo) antes de montar o pacote | Não há muralha ética nem papel por documento ("todos veem tudo", `equipe.py`). O único filtro por pessoa é o de **Serviços por equipe** (`servicos_acesso` + `search.FILTRO`), posto pelo `PortaDosServicos` em ContextVar. **Furo achado (abaixo).** |
| CSP da página remota | Existe (`acesso/remoto.py`): `connect-src 'self'`, `worker-src 'self' blob:`, script só do próprio PAULUS e do Turnstile (Cloudflare) nas páginas de entrada. |
| Nada da conversa guardado no navegador | **Não confere hoje:** o rascunho da pergunta fica em `localStorage` (`paulus.conversa.<id>`) e nunca é apagado, nem ao apagar a conversa; o rascunho de e-mail (com o resumo de gravação feito pela IA) e a sugestão da IA para um documento também. Nenhum Worker, Service Worker, Cache Storage nem IndexedDB. O portão da D2 ("nenhum armazenamento contém texto da pergunta") precisa que o rascunho saia do `localStorage` ao menos de fora. |
| Auditoria | Existe: `data/acesso/acessos.jsonl`, encadeada por hash. **Perguntas ao modelo não são auditadas.** Nenhuma execução diz se foi de fora ou local (o dono só na memória). |
| Chaves num bloco `aparelho` | `config.PADRAO` descarta chave que não conhece: o bloco precisa de todas as chaves. `/api/chaves` só mexe em booleanos dos blocos listados em `rotas_chaves.BLOCOS`. |

### Furo achado: o filtro de Serviços não chega à thread da resposta

O `search.FILTRO` e o `PESSOA_DA_VEZ` são `ContextVar`. A resposta da
conversa roda numa `threading.Thread` nova (`execucoes.py` ~180), e a C5 idem.
No Python 3.14.3 do venv (`sys.flags.thread_inherit_context = 0`), a thread
nova começa com o contexto vazio — **provado**: `FILTRO` com valor fora,
`None` dentro da thread. A busca da resposta roda dentro do gerador, na
thread. Então um colaborador de fora, restrito por equipe em Serviços,
provavelmente tem a resposta procurada no Acervo inteiro. O teste de Serviços
põe o filtro à mão e não passa pela thread. **Falta a prova de ponta a ponta**
(uma pergunta de colaborador restrito que cite um trecho de fora da equipe).
A correção é pequena (levar o contexto para a thread com
`contextvars.copy_context().run`), mas é de outra frente: registrado aqui e
levado ao dono na pausa, porque a D1 ("o pacote é montado depois do filtro")
depende disso.

**Corrigido em 30/09, a pedido do dono, antes de seguir o plano.** Prova de
ponta a ponta (`tests/test_seg_filtro_na_thread.py`, modelo simulado, busca
de verdade): antes, a Sara (equipe do A) perguntou "o que diz o parecer sobre
a fusão Zebralux?" pela conversa de fora e o parecer sigiloso do B chegou ao
modelo e às fontes da resposta. A thread da execução (`execucoes.py`) e a do
fluxo das habilidades (`habilidade_base.py`) agora rodam dentro de
`contextvars.copy_context()` de quem pediu. Depois: o parecer não chega para
a Sara, chega para o João (equipe do B) e para a janela do escritório.

## D0 — a medida

- **Uso real do acesso de fora nesta máquina: zero.** `data/acesso/contas.db`
  tem 0 contas e 0 sessões; as 209 linhas da auditoria são todas do teste de
  tela ("Teste de Tela", 28 a 30/09). Não há pergunta de fora para medir.
- As 75 execuções em `data/execucoes/` são de hoje, dos testes (modelo
  simulado, ~2 s): nenhuma passou pela fila. Não servem de medida.
- **O custo de cada lugar na fila** vem do `data/ritmo.json` (25 respostas
  reais do llama3.2:3b nesta máquina, em CPU): **mediana 34 s por resposta**
  (8,8 s lendo + 12,2 s escrevendo), **p90 102 s**, máximo 468 s. Com 3
  pessoas na frente, a espera típica seria ~1,5 a 5 min.
- **Faltava instrumento:** a execução não grava o tempo de fila à parte
  (`total_s` inclui a espera) nem se foi de fora. Para medir de verdade é
  preciso gravar `fila_s` e a origem em cada execução.

## F1 — a fila à vista (30/09/2026)

Pedido do dono: fazer a fila primeiro, explicar, e ele decide se o plano
segue. Tudo atrás de `aparelho.fila` (desligada de fábrica, como o prompt
manda); Configurações › Assistente e modelo › "A fila do modelo" liga.

**Como ficou**
- **Uma fila para todas as telas.** A chamada ao modelo entra na fila no
  próprio cliente (`llama_client._chat` → `fila_modelo.vez_para_o_modelo`),
  e não em cada rota: conversa, editor, planilha, e-mail, resumos, parecer,
  medida de modelo. A origem vem da rota (middleware `QuemPedeAoModelo`,
  por dentro do porteiro) e o nome é o primeiro nome da conta (de fora) ou
  o de Meus dados (a janela do escritório; "Escritório" sem nome). Thread
  sem requisição é "segundo plano" e fica atrás de toda pergunta. Quem já
  tem a vez (a conversa, que a pega antes de ler) não entra de novo: a marca
  é a ContextVar `VEZ`, que chega às threads da resposta desde a correção do
  filtro de Serviços. O limite de duas por pessoa vale em todas as telas: a
  terceira recebe 429 "você já tem duas perguntas esperando" (handler único).
- **O juiz de uma letra não espera a vez.** Com a fila ocupada, ele não é
  chamado e a regra decide — o mesmo que já acontecia quando ele passava dos
  20 s, sem esperar os 20 s.
- **A pergunta que espera na conversa** fica no servidor
  (`contexto["pendentes"]` do trabalho, fora do `to_dict`: o texto só sai
  pela rota dela, e só para quem escreveu), com um lugar de verdade na fila.
  Na vez, vai sozinha pela execução desacoplada (C1), no contexto de quem a
  mandou (filtro de Serviços, pessoa e origem vão juntos). Editar e cancelar
  valem de fora, com o dono conferido. **Decisão:** se o programa reinicia
  com uma na fila, ela vira "não foi enviada" com Enviar agora / Descartar —
  mandar sozinha depois de reiniciar seria mandar sem o contexto de quem
  pediu (sem o filtro dele).
- **Ctrl+Enter.** "Própria": a nova troca de lugar só com as perguntas da
  mesma pessoa (os lugares dos outros não mudam) e passa na frente do
  segundo plano. "Geral": passa na frente de todos que esperam, nunca de
  quem já começou; quem foi passado vê "pergunta prioritária de <nome>". A
  liberação é um nível novo na grade de permissões (Acesso de fora ›
  Contas: "Passar na frente na fila (Ctrl+Enter)", só entre as próprias ×
  passa na frente), com `aparelho.prioridade_por_hora` (3). **Decisão:** a
  janela do escritório conta como o titular (liberada, com o mesmo limite).
  Toda prioridade vai para o registro de acessos (ação `prioridade`).
- **A tela.** A bolha "na fila · 1º · ~40 s · na frente: Helena · conversa",
  com Editar e Cancelar; a linha de estado diz quem está na frente e o
  motivo; a dica "Ctrl+Enter envia com prioridade" só com fila; a janela do
  escritório tem "Ver a fila" (nome, tela e há quanto tempo — nunca o texto).

**Medido:** `tests/test_f1_fila.py` 49 ok — com o cliente do modelo de
verdade e a rede trocada por um Ollama de mentira que o teste segura e
solta: a ordem real em que o modelo atendeu (escritório, Helena com
prioridade, Helena, Rui, Rui, e-mail do escritório) bate com a fila
mostrada; a Helena com duas não manda a terceira nem pelo e-mail. **Roteiro** (`tools/demo/roteiro.py --tudo`, llama3.2:3b, com a chave ligada no demo só para a medida, e já com a Constituição, os códigos e as súmulas da Biblioteca no demo): **41/41** (programa 11/11, documentos 29/29, mediana 12,7 s). Suíte: 116/120 — test_r4_fila ajustado à frase nova do 429 e passa; ficam as três de antes (a2 pelo Acervo real, gravacoes por falta de memória, inteligencia_regressao).

**Fica para depois / não feito**
- A bolha da pendente atualiza por consulta a cada 2 s, não por evento.
- A conversa do `enviar()` em outra conversa enquanto uma responde continua
  como era (o botão "esperando" até a execução chegar).
- O "Esperar na fila" antigo (só na memória) continua com a chave desligada.

## D1 — o pacote e a porta (30/09/2026)

**Como ficou** (`src/aparelho.py`, gancho em `habilidades/perguntar.py`)
- A pergunta pede o aparelho (`Pergunta.aparelho`). O servidor decide
  (`pode_escrever`): `aparelho.ligado`, sessão de fora, o nível novo
  "Escrever a resposta no próprio aparelho" da conta (grade de permissões,
  só na janela local — o colaborador não liga para si) e a conta vê o
  Acervo. Não pode: escrita no escritório, com o motivo na resposta
  (`cobertura.como.escrita`).
- **O pacote é montado no ponto exato em que o escritório chamaria o
  modelo** (`_responder`), depois do escopo, do filtro de Serviços e da
  busca: as mesmas mensagens (`llama_client.montar_mensagens`, que o `ask`
  passou a usar), **sem os lembretes do escritório** (de fora ninguém os
  vê), com os parâmetros de escrita da conversa.
- Recusa no servidor, e a resposta segue no escritório: caminho que não é o
  de trechos (Acervo inteiro, documento em foco lido inteiro, fatos já
  lidos, ações da conversa); trecho de caso "só no escritório" (pasta ou
  Serviço, `<dados>/aparelho/so-no-escritorio.json`; a tela é da D5);
  trecho fora do filtro da pessoa (defesa em profundidade — a busca já
  filtrou); trechos acima de 9.000 caracteres (o orçamento da busca).
- Passou: **a vez do modelo volta para a fila** (quem escreve é o
  aparelho) e a execução espera. O evento da execução — que fica no disco —
  leva só o id, a assinatura (HMAC com segredo do processo, ligada à sessão)
  e a validade (10 min). O conteúdo sai por `GET /api/aparelho/pacote/{id}`,
  uma vez, para a mesma sessão; devolver e abandonar conferem sessão,
  assinatura, validade e uso único.
- **O texto que volta não é gravado sem conferência.** Até a D3, a
  conferência reprova tudo: o escritório reescreve e a resposta diz
  "conferência reprovou". Abandonou ou venceu: o escritório escreve ("o
  aparelho não terminou").
- Auditoria (`aparelho`): entrega (quantos trechos, de quais documentos),
  devolução e abandono, com a pessoa e "navegador" + 6 caracteres do hash
  do navegador (sem identificador invasivo).

**Achado para a D5:** de fábrica, a conversa lê pelo caminho "tudo"
(`ia.leitura = "tudo"`: o Acervo inteiro quando cabe). O aparelho só recebe
pacote no caminho de trechos (`ia.leitura = "trechos"`, I7). Com o de
fábrica, quase toda pergunta seria escrita no escritório ("a pergunta pede
o Acervo inteiro"). Ligar a escrita no aparelho precisa ligar a leitura por
trechos junto — decisão do dono, porque muda como o escritório também lê.

**Medido:** `tests/test_d1_pacote.py` 30 ok (sem liberação, desligado,
janela local, pacote só com trechos e sem lembrete nem Serviço alheio,
outra sessão, assinatura errada, uso único, vencido, abandonado, caso só no
escritório, auditoria).

## D2 — o motor no navegador (30/09/2026)

**A biblioteca.** Avaliadas: **wllama 3.6.1** (llama.cpp em WebAssembly, MIT,
sem dependências, GGUF - o formato do Ollama -, WebGPU desde a 3.1, roda num
worker próprio), **web-llm 0.2.85** (Apache-2.0, WebGPU, mas o código do
modelo é um wasm por modelo que vem do GitHub e os pesos no formato MLC) e
**transformers.js 4.3** (Apache-2.0, depende do onnxruntime-web, 144 MB).
Escolhida a wllama, aprovada pelo dono. Vai em `frontend/vendor/wllama-3.6.1/`
(index.js, wllama.wasm, LICENCE - 8,8 MB), servida por `/motor/...` só se o
SHA-256 bate com o fixo em `src/aparelho_motor.py`. Sem build e sem CDN: as
URLs de fora que a biblioteca conhece (jsDelivr, Hugging Face) são de funções
que o PAULUS não chama, e a CSP barraria.

**Os pesos** saem do Ollama deste escritório: o blob do Ollama tem o SHA-256
no nome; o servidor confere o conteúdo antes de entregar e o aparelho confere
de novo antes de usar (hash errado: apaga e recusa). Decisão (o dono não
escolheu; o prompt manda o mais seguro na dúvida): servidos pelo PAULUS, e não
de uma origem pública - a CSP continua com `connect-src 'self'`. Custo: o
upload do escritório, uma vez por aparelho.

**O trabalhador** (`frontend/motor/trabalhador.js`): Web Worker dedicado; a
pergunta, os trechos e a resposta só nas variáveis da escrita, soltas no fim.
Os pesos no Cache Storage "paulus-modelo", sob `/api/aparelho/modelo/<sha256>`;
sem espaço (a cota do navegador), usa sem guardar e baixa de novo na próxima.

**A capacidade** (`js/60-aparelho.js`): WebGPU, memória, e a velocidade num
texto de exemplo sem nada do escritório; ao servidor vão só esses números
(`POST /api/aparelho/capacidade` recusa qualquer outro campo).

**CSP de fora:** `'wasm-unsafe-eval'` em script-src (compilar WebAssembly; não
libera eval de JavaScript nem origem nova).

**Medido:**
- `tests/test_d2_motor.py` 25 ok - com o motor falso (o mesmo trabalhador, sem
  a biblioteca): nenhum armazenamento guarda pergunta, trecho ou resposta; o
  único cache é o dos pesos, sob o hash; nada em IndexedDB, OPFS nem Service
  Worker; peso adulterado apagado e recusado; nenhuma requisição para fora; a
  capacidade só com números.
- **Motor de verdade**, no Edge desta máquina (WebGPU, 16 GB): o llama3.2:1b
  (Q8_0, 1,32 GB) carrega em 16–22 s, escreve a 7,9–8,7 tokens/s, e responde a
  uma pergunta curta em 2,5–3,1 s.
- **A qualidade do 1B** (`roteiro.py --tudo --modelo llama3.2:1b`): programa
  11/11, **documentos 12/29** (o 3B: 29/29) - "Não achou…" em perguntas que o
  trecho responde. Com a conferência da D3, a maior parte voltaria ao
  escritório.
- **O 3B não carrega no navegador:** o arquivo (Q4_K_M, 2,02 GB) passa do
  limite de ~2 GB por arquivo da wllama ("File read failed: NotReadableError";
  soltar a cópia em memória não resolveu). Carregar o 3B exige dividir o GGUF
  no formato de partes do llama.cpp (gguf-split) - ferramenta nova.

**⏸ PAUSA D2 — o modelo.** O padrão (`aparelho.modelo`) ficou o llama3.2:1b,
que carrega. Decisão do dono: (a) seguir com o 1B, sabendo que acerta 12 de 29
e que a conferência mandará muita coisa de volta; (b) trazer o gguf-split do
llama.cpp (ferramenta nova, versão fixa) para dividir o 3B em partes de 512 MB
e servir as partes; (c) medir outro modelo pequeno (ex.: Qwen 2.5 1.5B) no
roteiro antes.

## D2b — o 3B em partes (30/09/2026)

O dono escolheu a opção 2 da pausa: trazer o gguf-split do llama.cpp.

- **O divisor:** `llama-gguf-split.exe` do llama.cpp **b11292** (zip oficial
  `llama-b11292-bin-win-cpu-x64.zip`, SHA-256 conferido com o que o GitHub
  publica: `50b68f61…8e11`), só com o que ele precisa para rodar (ggml-base,
  ggml, llama, llama-common e libomp - 13 MB), em `src/bin/llama-cpp-b11292/`,
  com as licenças (MIT; libomp: Apache-2.0 com a exceção do LLVM) e o hash de
  cada arquivo em `aparelho_motor.PARTIDOR`. A pasta está com `-text` no
  .gitattributes.
- **A divisão:** na primeira vez que um aparelho pede o modelo, o servidor
  confere o hash do blob do Ollama e divide em partes de 512 MB em
  `<dados>/aparelho/partes/<sha256>/`, anotando o hash de cada parte (3,4 s
  no 3B: 4 partes, 255 tensores). Parte trocada no disco com o mesmo tamanho:
  409; com outro tamanho: divide de novo do modelo conferido.
- **No aparelho:** cada parte é baixada, conferida pelo hash e guardada no
  Cache Storage sob `/api/aparelho/modelo/<sha>/parte/<n>`; o Blob vem do
  cache (o navegador lê do disco) - somando as partes em memória, o 3B
  estourava ("NotReadableError"). Parte com hash errado: apagada e recusada.
- **O padrão voltou a ser o llama3.2:3b** (o do escritório; 29/29 no roteiro).

**Medido:** o 3B de verdade, no Edge com perfil de verdade (WebGPU, 16 GB):
carrega em 23,2 s, escreve a 4,3 tokens/s, e respondeu "O IGP-M" à pergunta
de exemplo em 4,4 s. No perfil anônimo do Edge de teste não carrega (ele não
guarda Blob grande em disco nem dá cota ao Cache Storage): o teste real da D6
tem de ser num navegador normal. `tests/test_d2_motor.py` 30 ok, com o
gguf-split de verdade dividindo o 3B desta máquina em 4 s.

## D3 — conferência e retomada (30/09/2026)

**A conferência** (`src/aparelho_conferencia.py`), com as funções que já
conferem as respostas do escritório - nenhuma cópia: marca para trecho que
não foi mandado reprova (`citacoes.revisar`); lei, súmula, artigo ou CNJ fora
dos trechos sai do texto (`citacoes.revisar`, regra 3); número (valor, data,
percentual, prazo, CPF, CNPJ, CNJ) que não está nos trechos nem na pergunta
reprova (`molde.numeros_de`; a numeração de lista e as marcas [Tn] não
contam); link e e-mail estranhos saem (`blindagem.tirar_estranhos`). Depois
dela, o texto passa pelo mesmo caminho do escritório (`_responder`). O que
reprovou e o que saiu vão para a auditoria.

**Decisão:** as conferências de marca e de número são mais estritas que as
que o escritório aplica ao próprio texto de fábrica (`ia.citacao` e a cerca
vêm desligadas; números só no nível 0). Ligá-las para o texto do escritório
mudaria respostas medidas no roteiro; ficou só para o texto do aparelho.

**A retomada.** O aparelho manda o texto parcial enquanto escreve
(`POST /api/aparelho/pacote/{id}/pedaco`). Abandonou, venceu ou ficou 45 s
sem sinal (`SILENCIO_S`): o parcial passa pela mesma conferência; passou, o
escritório continua dali - vai ao modelo como o começo da resposta do
assistente (o Ollama continua: medido com `"1, 2, 3, 4,"` → `" 5, 6, 7, 8, 9,
10."`, `LlamaClient.ask(continuar=...)`); não passou, escreve do zero. A
resposta guarda onde cada parte foi escrita (`como.escrita.partes`).

**Medido:** `tests/test_d3_conferencia.py` 9 ok (número inventado e marca
inexistente refeitos; lei inventada tirada e o resto fica do aparelho;
aprovado igual ao mandado; sumiu no meio: parcial + continuação, com as
partes; parcial com número inventado: do zero; auditoria). A D1 passou a
devolver um número inventado para conferir a reprovação.

## D4 — o switch e a tela (30/09/2026)

**O seletor** (`js/61-aparelho-tela.js`): Escritório · Este aparelho ·
Automático, uma pílula na caixa da pergunta, ao lado do microfone. Aparece
só de fora, para a conta que o titular liberou (`/api/aparelho/estado`), e só
neste aparelho depois de passar no teste de capacidade (WebGPU, memória e
pelo menos 3 palavras por segundo). Fica guardado neste navegador, em
`localStorage["paulus.aparelho"]`: só a escolha, os números do teste, o
"entendi" e a data do "não sugerir hoje". Nada da conversa.

**Antes de mandar** (`ondeEscrever`, chamado por `enviar` antes do POST):
`POST /api/aparelho/sugestao` recebe só o escopo (os documentos em foco) e os
números do teste, e devolve a fila do escritório de agora
(`FilaDoModelo.espera_de_quem_chega`), se a pergunta pode ir ao aparelho, se
a janela deve aparecer e o que o Automático escolhe. Não guarda nada.

- **A janela de sugestão**: um balão acima da caixa da pergunta, não trava a
  tela, com os três botões do §3. Aparece com a espera estimada acima de 30 s
  ou 2 ou mais na frente, só com o recurso liberado, o teste passado e a
  conversa fora de caso "só no escritório". "Não sugerir de novo hoje" vale
  até a meia-noite. Com Ctrl+Enter, aparece do mesmo jeito.
- **O Automático** (`aparelho.decidir`): o aparelho só quando a estimativa
  dele é menor que a espera na fila mais uma resposta do escritório, agora.
  A estimativa do aparelho usa a medida DELE: ~250 tokens de resposta pela
  velocidade de escrita, ~1.500 de pergunta pela de leitura (o teste agora
  mede as duas), mais carregar o modelo se não estiver carregado, mais o
  download se não estiver guardado (a 8 MB/s: um palpite de rede, dito com
  "~"). Sem ritmo medido no escritório, uma resposta conta 60 s.
- **Primeira vez em "Este aparelho"**: o aviso do §2.6 (o que vai, o que
  fica — só o modelo, com o tamanho —, que o escritório confere, e o que não
  dá para garantir), com "Entendi".

**A pergunta que vai ao aparelho não entra na fila do escritório.** A busca
não usa a vez do modelo; quem escreve é o aparelho. Se a resposta voltar
para o escritório (reprovada, abandonada), a chamada ao modelo entra na fila
sozinha (`vez_para_o_modelo`). Medido: com 3 na fila segurando a vez, o
pacote sai na hora e a pessoa nunca aparece na fila.

**Decisão (sua, para rever):** de fábrica a conversa lê o escopo inteiro
quando cabe (`ia.leitura = "tudo"`, o achado da D1), e aí o aparelho nunca
receberia pacote. Fiz a pergunta que pede o aparelho ir **por trechos só
nela** (`_por_trechos` em habilidades/perguntar.py), qualquer que seja
`ia.leitura` e o tamanho do escopo; as outras perguntas leem como sempre. O
pedido de ler o documento inteiro continua indo ao escritório. A resposta
diz "li N trechos", como qualquer resposta por trechos.

**O caminho no aparelho**: o evento `aparelho` da resposta dispara
`escreverPacoteNoAparelho` — pega o pacote (uma vez, desta sessão), escreve
mostrando o texto enquanto sai, manda o parcial a cada 1,5 s, devolve.
Erro: abandona com o parcial. Aba fechando: `pagehide` abandona com
`keepalive` (sem ele, o escritório termina depois de 45 s sem sinal). O
evento `aparelho_fim` diz onde ficou; se o escritório assumiu, o aparelho
para.

**Em cada resposta**: no painel "Sobre esta resposta", a linha "Escrita" —
"escrita neste aparelho · modelo · conferida no escritório", "começou neste
aparelho e o escritório terminou · motivo" ou "escrita no escritório ·
motivo" (você escolheu o escritório, você escolheu esperar na fila, no
automático o escritório estava mais rápido, caso só no escritório, pede o
documento inteiro, conferência reprovou, o aparelho não terminou). Na
assinatura, "neste aparelho" e o modelo do aparelho. Vista na janela do
escritório, a frase diz "no aparelho de quem perguntou".

**Minha conta › Este aparelho**: o teste de capacidade (fazer de novo), o
tamanho do modelo guardado aqui e "Apagar o modelo deste aparelho" (apaga
os pesos e o teste; o seletor some até o próximo teste). Sem WebGPU, o
motivo, com a nota de que a maioria dos celulares ainda não tem.

**O que ficou de fora:** enquanto uma resposta que voltou do aparelho
espera a vez no escritório, a tela não mostra a posição na fila (a pergunta
entra na fila na chamada ao modelo, e não pela conversa). A checagem "só no
escritório" antes de mandar vê só os documentos em foco; na busca livre, o
caso marcado só aparece nos trechos, e aí o servidor recusa o pacote (D1) e
a resposta diz o motivo — a janela de sugestão pode ter aparecido antes.

**Medido:** `tests/test_d4_switch.py` 40 ok (a conta do Automático e do
limite; pela API: sem liberação, abaixo e acima do limite, caso só no
escritório, pergunta ao aparelho sem passar pela fila cheia, a escolha dita
na resposta; no Edge como conta de fora, com o motor falso: sem liberação
sem seletor, teste que passa e que não passa, Automático com fila vazia e
cheia, janela com os três botões, "não sugerir hoje" até o dia seguinte,
nenhuma janela no caso só no escritório, "Usar este aparelho" com o aviso da
primeira vez, resposta escrita aqui com o modelo do escritório sem ser
chamado, painel e assinatura, nada da conversa no navegador, apagar o
modelo, largura de celular).

## D5 — o que o titular controla (30/09/2026)

Tudo só na janela do escritório: as rotas novas são BLOQUEADO de fora e
conferem `so_local` de novo; a chave e a permissão por conta já eram. Nem o
colaborador liga para si, nem o titular pelo acesso de fora.

**Configurações › Acesso de fora › "Escrever no aparelho"**
(`js/62-aparelho-titular.js`):
- **para o escritório**: ligar e desligar (a chave `aparelho.ligado`);
- **por conta**: a liberação continua em Contas › Permissões ("Escrever a
  resposta no próprio aparelho", já aparecia sozinha na grade desde a D1); o
  cartão lista quem está liberado;
- **só no escritório**: marcar cliente, Serviço ou pasta do Acervo; a marca
  é conferida ao gravar (o Serviço, o cliente e a pasta existem) e marcar e
  tirar vão para a auditoria. Cliente marcado vale para as pastas de todos
  os Serviços dele (`cadastro_id`), inclusive os abertos depois. A regra
  continua na montagem do pacote, no servidor (`Escrita.preparar`);
- **relatório**: por pessoa, quantas respostas foram escritas no aparelho,
  quantas foram refeitas pela conferência e quantas o escritório terminou.
  Sai da auditoria: cada resposta com pacote ganha uma linha de fim
  (`Escrita.fechar`), e a lista inteira continua em "Quem acessou".

**Desligar vale na hora** (`ainda_pode`): enquanto o aparelho escreve, a
cada meio segundo o escritório confere a chave e o nível da conta, lido de
novo da conta (e não da sessão de quando a pergunta saiu). Desligou: a
resposta termina no escritório — do parcial conferido, se houver — com o
motivo ("o escritório desligou a escrita no aparelho" ou "o titular desligou
a escrita no aparelho para a sua conta"), e toda rota do pacote responde
410. O aparelho para no próximo pedaço recusado.

**A decisão de `ia.leitura`** (o achado da D1) ficou resolvida na D4 sem
mudar como o escritório lê: só a pergunta que pede o aparelho vai por
trechos. O cartão diz isso ao titular.

**Medido:** `tests/test_d5_titular.py` 29 ok (colaborador e titular de fora
recusados na permissão, na chave, nas marcas e no relatório; marca inválida
recusada; cliente e Serviço marcados mandam a pergunta ao escritório com o
motivo; desligar para o escritório e tirar a liberação da conta no meio de
uma resposta: termina aqui, com o motivo, e o pacote não vale mais;
relatório 1 no aparelho, 1 refeita, 2 terminadas aqui; auditoria das
marcas; no Edge, o cartão com estado, liberadas e relatório, marcar e tirar
uma pasta, desligar pela tela).

## D6 — política, manual e teste real (30/09/2026)

**Política de privacidade e termos** (`site/`, as páginas em português e
em inglês), **não publicados**: vão ao ar com o próximo `publicar` (é ele
quem faz o push do site). Na política, a seção nova "Escrever a resposta no
aparelho (opcional)": vem desligado, quem liga, o que continua no
escritório, o que vai ao aparelho a cada pergunta e uma vez, o que fica
nele, o que o escritório confere, o que o escritório recebe do aparelho
(os números do teste e o registro, com o código curto do navegador), o que
não dá para garantir; o "O que continua no computador do escritório" do
acesso de fora deixou de dizer que o modelo nunca sai; a retenção do modelo
guardado. Nos termos, um item em "Acesso de fora": quem decide, a
segurança do aparelho é de quem o usa, e o texto conferido continua sendo
resposta de IA sujeita à revisão do profissional.

**Manual**: `docs/pensar-no-aparelho.md` (como funciona, ligar, casos só no
escritório, o relatório, usar de fora, apagar o modelo, solução de
problemas, conferir o navegador); `docs/acesso-de-fora.md` aponta para ele.

### ⏸ Roteiro do teste real (para o dono, de um notebook fora do escritório)

Antes de sair: no computador do escritório, o PAULUS rodando pelo terminal
com esta versão (a main), o acesso de fora ligado e o `llama3.2:3b` no
Ollama. No notebook: Edge ou Chrome atualizado, **janela normal** (a
anônima não guarda o modelo), e ~3 GB livres.

1. **Ligar** (no escritório, antes de sair): Configurações › Acesso de
   fora › Escrever no aparelho › **Ligar**. A sua conta de titular já pode;
   para testar também uma conta da equipe, Contas › Permissões › "Escrever
   a resposta no próprio aparelho: pode".
2. **Entrar e testar o aparelho** (no notebook): entre pelo acesso de fora;
   seu nome no alto › **Este aparelho** › **Fazer o teste**. Anote: quanto
   tempo levou o download, se passou, e as palavras por segundo. Feche e
   confira que apareceu **Escritório ▾** na caixa da pergunta.
3. **Cinco perguntas em "Este aparelho"**: troque para **Este aparelho**,
   clique **Entendi** no aviso, e faça 5 perguntas sobre documentos (de
   preferência uma com valor ou data, e uma que peça uma cláusula). Em cada
   uma, confira na assinatura "neste aparelho" e em Sobre esta resposta ›
   Escrita "escrita neste aparelho · llama3.2:3b · conferida no
   escritório" (ou o motivo, se o escritório refez). Anote o tempo de cada
   uma. Se quiser ver a janela de sugestão: volte para **Escritório** e
   pergunte enquanto alguém usa o PAULUS no escritório.
4. **Caso só no escritório**: no escritório (ou peça a alguém lá), Acesso
   de fora › Escrever no aparelho › Só no escritório › marque o cliente ou o
   Serviço de um documento. Do notebook, pergunte sobre esse documento: a
   resposta tem de dizer "escrita no escritório · a resposta usa um caso
   marcado só no escritório". Tire a marca depois.
5. **Fechar a aba no meio**: pergunte algo que peça uma resposta longa e,
   quando o texto começar a aparecer, feche a aba. Espere ~1 minuto, entre
   de novo e abra a conversa: a resposta tem de estar lá, com Escrita
   "começou neste aparelho e o escritório terminou · o aparelho não
   terminou" (ou "escrita no escritório", se nada tinha chegado).
6. **Nada guardado**: F12 › Aplicativo (Application) › Armazenamento. Em
   Cache Storage, só `paulus-modelo` (as partes do modelo); em
   Armazenamento local, só `paulus.aparelho` (escolha e números); nada em
   IndexedDB. Procure uma palavra de uma das perguntas: não pode aparecer.
7. **Apagar**: seu nome › Este aparelho › **Apagar o modelo deste
   aparelho**. Confira em F12 que `paulus-modelo` sumiu e que o seletor
   saiu da caixa da pergunta.

No fim, de volta ao escritório: Acesso de fora › Escrever no aparelho ›
Relatório (as respostas do teste, por pessoa) e "Quem acessou" (as
entregas, devoluções e o fim de cada uma).

Me mande o que deu diferente do esperado em cada passo, com o texto da
tela; cada correção vem com teste.

## Fora do foco

- O rascunho de e-mail e a sugestão da IA ficam no `localStorage` (ver acima).
- As rotas de inscrição de execução não conferem o dono.
- `test_a2_agente_na_conversa` falha com o Acervo real desta máquina (três
  PDFs com nomes quase iguais): o documento citado toma o lugar do foco. Já
  falhava sem as mudanças de hoje.
- Arquivar uma gravação ao vivo sem memória livre para o Whisper dá 500
  (`transcricao.SemMemoria` sobe de `ao_vivo_fim` em `gravacoes_guardar`), em
  vez da mensagem "troque para o small". O `test_gravacoes` usa os dados de
  verdade e deixava "Teste — ao vivo" para trás nesse caso: agora acha pelo
  título e apaga.
- `test_listas` clicava fora da janela quando a lista do Assistente descia
  (saudação, avisos e "Acontecendo agora" acima dela, conforme a hora): agora
  rola a linha até a vista antes do botão direito.
