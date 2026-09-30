# PROGRESSO — Pensar no aparelho (acesso de fora)

Retomada do plano `docs/prompt-pensar-no-aparelho-v0.md` (D0…D6 e F1). Uma
conversa nova, com o mesmo prompt, continua da primeira etapa que não estiver
`feita`.

| Etapa | O quê | Estado | Commit | Portão (medido) |
| --- | --- | --- | --- | --- |
| D0 | Levantamento e medida da fila remota | feita — ⏸ PAUSA: esperando a decisão do dono | ver git log (d0) | tabela e números abaixo |
| F1 | Fila dentro da conversa, fila única, Ctrl+Enter | feita; chave `aparelho.fila` desligada de fábrica — ⏸ o dono decide se seguimos | ver git log (f1) | `tests/test_f1_fila.py` 49 ok (ordem, pendente, 429, Ctrl+Enter com e sem liberação, auditoria, e-mail na mesma fila, Edge) |
| D1 | O pacote e a porta | pendente (o furo do filtro foi corrigido antes, ver abaixo) | | |
| D2 | O motor no navegador | pendente | | |
| D3 | Conferência no escritório e retomada | pendente | | |
| D4 | O switch e a tela | pendente | | |
| D5 | O que o titular controla | pendente | | |
| D6 | Política, manual e teste real | pendente | | |

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
