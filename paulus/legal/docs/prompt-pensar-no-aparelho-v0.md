# PAULUS — Implementação: pensar no aparelho (acesso de fora)

Você vai criar, no acesso de fora do PAULUS Legal (`paulus/legal/`), um **switch que move a escrita da resposta do computador do escritório para o aparelho de quem está acessando**. A condição é não abrir nenhuma brecha de segurança nova. O trabalho é feito **uma etapa por vez**, até o fim. Este prompt é o contrato inteiro: leia tudo antes de começar.

## Foco

Hoje, quem acessa de fora usa o modelo do computador do escritório. Com três ou quatro pessoas de fora, todas esperam na mesma fila, num computador que às vezes é mais fraco que o notebook delas.

**A ideia:** o escritório continua fazendo tudo o que envolve o acervo (entender a pergunta, buscar, escolher os trechos, conferir a resposta). **Só a escrita** vai para o aparelho, que recebe a pergunta e os trechos escolhidos e devolve o texto.

**A regra que manda em tudo:** o aparelho nunca recebe mais do que a pessoa já veria na tela pelo acesso de fora, e nada fica guardado nele. Se alguma etapa exigir quebrar isso, **pare**.

- Não retome planos anteriores; arquivos de progresso antigos são histórico.
- Não trabalhe em outras frentes; o que achar vai para "Fora do foco" no PROGRESSO.
- Na dúvida entre mais amplo e mais seguro, **faça mais seguro**.

---

## 0. Como trabalhar

### 0.1 Retomada

Procure `paulus/legal/docs/PROGRESSO-APARELHO.md`.
- **Não existe:** crie-o com as etapas D0…D6 e F1, todas `pendente`, e comece pela D0.
- **Existe:** continue da primeira etapa que não estiver `feita`.

Atualize ao fim de cada etapa: estado, commit, números do portão e decisões.

### 0.2 Ciclo de cada etapa

1. `git switch main && git switch -c <id>-<nome-curto>` (ex.: `d2-motor-no-navegador`).
2. Leia o código que a etapa toca antes de mudar. Nomes citados aqui podem ter mudado: confira.
3. Escreva o teste do portão primeiro e veja-o falhar.
4. Implemente o mínimo dentro do contrato.
5. Rode a suíte inteira (`tests/test_*.py`) e o banco de provas. Regressão bloqueia.
6. Registre em `docs/ETAPAS.md`.
7. Commit, merge em `main` (ff se possível) e atualize o PROGRESSO.
8. Siga direto para a próxima etapa, salvo nas PAUSAS.

### 0.3 Quando PARAR

- Etapa marcada **⏸ PAUSA**.
- Portão que não passa depois de 3 tentativas honestas.
- Qualquer caminho em que o aparelho receberia algo além do que a pessoa já veria, ou guardaria algo depois de fechar a aba.
- Dependência nova, ou código de terceiros carregado de fora do próprio PAULUS.

### 0.4 Convenções

- Português nos nomes e comentários; o comentário explica o porquê, com o que foi medido.
- Testes são scripts que terminam com `todos os testes passaram`. O que depende de navegador com WebGPU, Ollama ou rede pula com aviso.
- Chaves em `config.PADRAO`, num bloco `aparelho`, **tudo desligado de fábrica**.
- Frontend sem build (`frontend/js/NN-*.js`). Código novo em módulo novo.
- Não publique e não faça `git push` sem perguntar.

---

## 1. A fila hoje (leitura de 30/09/2026; confirmar na D0)

- **Existe uma fila única do modelo** (`src/fila_modelo.py`, etapa R4 antiga): ordem de chegada, no máximo **duas perguntas por pessoa** (a que está sendo respondida conta), posição e previsão tiradas de `ritmo.py`. O trabalho de segundo plano cede a vez com `ceder()`. A 3ª pergunta da mesma pessoa recebe 429 antes de qualquer coisa ser salva.
- **Só a conversa e Serviços entram nela.** Editor, resumos, parecer, e-mail e outras telas chamam o Ollama direto, e por isso a posição mostrada pode estar errada.
- **Não há fila dentro da conversa.** Com uma resposta andando, `enviar()` sai **calado** quando `estado.ocupado` (`03-assistente.js`). Numa outra conversa, o botão mostra "esperando" desabilitado. A pergunta não fica guardada para ir depois.
- **Não há prioridade.** Nada na fila aceita "na frente".
- **Ctrl+Enter não faz nada de especial:** o campo trata `Enter` sem `Shift` como enviar (~1790), e Ctrl+Enter cai no mesmo caminho.
- Perguntas respondidas por molde (nível 0) não entram na fila.

---

## 2. O modelo de segurança

Esta seção é o contrato mais importante. Todas as etapas existem para cumpri-la.

### 2.1 O que o aparelho recebe

| Recebe | Nunca recebe |
|---|---|
| A pergunta | O documento inteiro |
| Os trechos já escolhidos pelo escritório para aquela resposta (no máximo o orçamento da busca, ~3.000 tokens) | O índice léxico, os vetores, o metadata completo |
| As instruções de sistema do PAULUS e, se houver, do agente escolhido | Trechos de documento que a pessoa não poderia abrir (papel, muralha ética, escopo) |
| Os 2 últimos pares da conversa, já cortados como hoje | Lembretes marcados como internos, senhas, tokens, dados de configuração |

**O teste que decide cada caso:** tudo o que vai ao aparelho é algo que a mesma pessoa, com a mesma sessão, já poderia ver na tela pelo acesso de fora. O pacote é montado no servidor, **depois** do filtro de permissões, nunca antes.

### 2.2 O que fica no aparelho

- **Pesos do modelo:** podem ficar no cache do navegador. São públicos e não contêm nada do escritório.
- **Pergunta, trechos e resposta:** vivem **só na memória** de um Web Worker dedicado e são apagados quando a resposta termina. Não entram em `localStorage`, `sessionStorage`, IndexedDB, Cache Storage nem Service Worker.
- Fechar a aba não deixa nada além dos pesos do modelo.

### 2.3 Quem mais participa

- **Ninguém.** O modelo roda no navegador, sem chamada a serviço externo. Sem telemetria.
- **O código do motor** (a biblioteca que roda o modelo no navegador) é servido **pelo próprio PAULUS**, pelo túnel, numa versão fixa. Não vem de CDN de terceiros; isso evita que um CDN comprometido rode código na página que vê os documentos.
- **Os pesos do modelo** vêm de uma origem pública fixa, com **hash conferido** antes de usar. Hash diferente → recusa e volta para o escritório. Se a origem pública for inviável, o PAULUS do escritório pode servir os pesos, com a mesma conferência. Registre qual ficou e por quê.
- A `Content-Security-Policy` da página remota passa a permitir **só** a origem dos pesos em `connect-src`, e nada mais.

### 2.4 O que o aparelho devolve

**O texto que volta do aparelho é tratado como não confiável.** Um aparelho adulterado poderia mandar qualquer coisa. Antes de gravar e exibir, o escritório roda **as mesmas conferências** de uma resposta escrita lá:
- números, datas, CNJ, CPF e valores precisam existir nos trechos;
- marcas de citação precisam apontar para trechos enviados;
- lei ou súmula citada fora dos trechos sai;
- a cerca contra injeção, se existir.

Reprovou → a resposta é refeita no escritório, e isso fica registrado.

### 2.5 Quem decide

- **O titular**, na janela local, liga ou desliga o recurso para o escritório e **por conta**. Desligado de fábrica.
- **Casos "só no escritório":** o titular pode marcar clientes, casos ou pastas cujo conteúdo **nunca** vai para aparelho. Pergunta cujos trechos tocam esses casos é escrita no escritório, mesmo com o switch ligado, e a pessoa vê o motivo em uma linha.
- **Ações sensíveis continuam no escritório** em qualquer caso: ler o documento inteiro, editar documento, redigir peça, e-mail, extração de metadata, OCR e tudo o que é ingestão. O switch vale para **respostas da conversa baseadas em trechos**.

### 2.6 O que NÃO dá para garantir, e é dito na tela

Um aparelho comprometido (vírus, extensão maliciosa no navegador) pode ler o que a página mostra. **Isso já é verdade hoje, só por ver o documento pelo acesso de fora.** O switch não aumenta esse risco, porque o aparelho recebe o mesmo que já veria, mas também não o elimina.

A tela de ativação diz isso em linguagem simples, e a política de privacidade também.

---

## 3. Como deve ficar para quem usa

- **No acesso de fora**, perto do campo de pergunta (a barra de escopo, se ela existir), um seletor de três posições: **Escritório · Este aparelho · Automático**.
  - Só aparece se o titular liberou para aquela conta **e** o aparelho passou no teste de capacidade.
  - Fica guardado por aparelho, sem conteúdo nenhum.
- **Na primeira vez em "Este aparelho":** o tamanho do download do modelo, o tempo estimado e a explicação curta do §2.6, com "entendi".
- **Automático:** usa o aparelho quando a medida local mostra que ele é mais rápido que o escritório, **contando a fila do escritório naquele momento**. Senão, usa o escritório.
- **Em cada resposta**, no painel da resposta (ou na assinatura, se o painel não existir): "escrita neste aparelho · modelo X · conferida no escritório", ou "escrita no escritório · motivo". Motivos: você escolheu, caso só no escritório, aparelho não suportado, conferência reprovou.
- **Fila à vista e a sugestão de usar o aparelho.** Quando o escritório está ocupado, uma janela pequena, não bloqueante, aparece **antes** de a pergunta entrar na fila: "O escritório está respondendo outras perguntas (3 na sua frente, ~2 min). Responder com este aparelho? ~25 s". Botões: **Usar este aparelho**, **Esperar na fila**, **Não sugerir de novo hoje**.
  - Aparece só se o recurso está liberado para a conta, o aparelho passou no teste de capacidade, a pergunta pode ir ao aparelho (trechos, nada "só no escritório") **e** a espera estimada no escritório passa de um limite (padrão: 30 s, ou 2 ou mais na frente). Com o modelo ainda não baixado, a janela diz o tamanho do download.
  - Em "Automático", não pergunta: decide e mostra a escolha na resposta.
- **Se a aba fechar no meio**, o escritório termina a resposta a partir do texto que já tinha chegado, e a conversa mostra que o fim foi escrito lá.

---

## 4. Etapas

### D0 — Levantamento e medida

Leia o código atual:
- acesso de fora: sessão, permissões por rota, CSP e cabeçalhos;
- a pergunta: montagem do contexto, busca, conferências de citação e de números;
- a fila do modelo;
- a execução, se a execução desacoplada existir;
- o painel da resposta;
- a auditoria.

Escreva no PROGRESSO uma tabela "o prompt supõe × o código tem hoje", **incluindo tudo o que o §1 diz sobre a fila**: se ela existe dentro da conversa, o que acontece com uma segunda pergunta, o que Ctrl+Enter faz, quais telas entram na fila e quais não. Se a conversa já ganhou fila ou aviso para a segunda pergunta em outro trabalho, reaproveite e registre.

**Meça**, com os registros que existirem (ou instrumente, se faltarem): nas perguntas feitas pelo acesso de fora, quanto tempo foi **fila** e quanto foi **leitura e escrita**.

**⏸ PAUSA D0.** Mostre a tabela e os números. Se a fila remota for desprezível, diga isso e pergunte se vale seguir.

---

### F1 — Fila dentro da conversa e Ctrl+Enter

**Contrato.**
- **Todas as chamadas ao modelo entram na fila única**, de todas as telas, com um rótulo de origem ("conversa", "editor", "resumo de gravação"…). Se a execução desacoplada já existir, use-a; senão, o ponto de entrada é o cliente do modelo, e não cada rota.
- **Fila dentro da conversa:** uma pergunta enviada com outra andando **não some mais**.
  - Ela aparece na conversa como uma bolha "na fila · 2º · ~40 s", com **editar** e **cancelar**, e vai sozinha quando chegar a vez.
  - Sobrevive a trocar de conversa e a recarregar a página: fica guardada no servidor, na conversa, como pergunta pendente.
  - O limite continua **duas por pessoa** no total. A terceira mostra "você já tem duas perguntas esperando", em vez de 429 silencioso ou toast.
- **Ctrl+Enter = enviar com prioridade**, com regras justas:
  - passa **na frente das suas próprias** perguntas na fila e de todo trabalho de segundo plano. Isso vale sempre, para qualquer pessoa;
  - passar **na frente de outras pessoas** só se o titular liberou prioridade para aquela conta (Acesso de fora › Contas), e com um limite por hora (padrão: 3). Sem liberação, Ctrl+Enter reordena só as suas e diz isso em uma linha;
  - **nunca interrompe** uma resposta que já está sendo escrita. "Na frente" é o próximo lugar da fila, não o lugar de quem está sendo atendido;
  - quem foi passado para trás vê a posição mudar, com o motivo "pergunta prioritária de <primeiro nome>";
  - toda prioridade vai para a auditoria;
  - a dica "Ctrl+Enter envia com prioridade" aparece no campo só quando existe fila, para não poluir o uso normal. `Enter` continua enviando e `Shift+Enter` continua quebrando a linha.
- **Mostrar a fila:** com alguém na frente, a linha de estado da pergunta mostra a posição, a previsão e **quem** está na frente, pelo primeiro nome e a origem ("Helena · conversa"). Quem está na janela local vê a fila inteira. O conteúdo das perguntas dos outros **nunca** aparece.
- Chave: `aparelho.fila` (esta etapa vale mesmo sem o recurso de aparelho ligado).

**Portão.** `tests/test_f1_fila.py` + Playwright:
- segunda pergunta na mesma conversa vira "na fila", sobrevive a recarregar e vai sozinha na vez;
- editar e cancelar uma pergunta na fila funcionam;
- terceira pergunta: mensagem clara, nada salvo;
- Ctrl+Enter sem liberação passa na frente só das próprias e do segundo plano;
- Ctrl+Enter com liberação passa na frente de outra pessoa, respeita o limite por hora, fica na auditoria e **não** interrompe quem está sendo atendido;
- a posição mostrada bate com a ordem real, porque todas as telas entram na mesma fila;
- ninguém vê o texto da pergunta de outra pessoa;
- `roteiro --tudo` não cai.

---

### D1 — O pacote e a porta

**Contrato.**
- Módulo novo (ex.: `src/aparelho.py`) que monta o **pacote de escrita**: pergunta, trechos numerados, instruções de sistema, histórico cortado e o id da execução.
- O pacote é montado **depois** do filtro de permissões e escopo. É assinado pelo servidor e vale para **uma** resposta, com validade curta (ex.: 10 min), ligado à sessão remota que pediu.
- Rotas:
  - pedir o pacote (só sessão remota com o recurso liberado);
  - devolver o texto (só com o pacote válido e da mesma sessão);
  - avisar que abandonou (volta para o escritório).
- **Recusa no servidor**, e não só na tela:
  - pergunta que exige documento inteiro, edição, redação ou ingestão;
  - trechos de caso "só no escritório";
  - conta sem liberação.
- Toda entrega e toda devolução vão para a auditoria do acesso de fora: pessoa, aparelho (sem identificador invasivo), execução, quantos trechos, de quais documentos, e o resultado da conferência.
- Chave: `aparelho.ligado`.

**Portão.** `tests/test_d1_pacote.py`:
- pacote de uma conta sem liberação → recusa;
- pacote com trecho de caso "só no escritório" → recusa, e a resposta vai para o escritório;
- trecho que a pessoa não poderia abrir (papel, escopo) nunca aparece no pacote;
- o pacote nunca passa do orçamento de trechos, e nunca contém documento inteiro;
- devolver com pacote vencido, de outra sessão ou já usado → recusa;
- tudo registrado na auditoria.

---

### D2 — O motor no navegador

**Contrato.**
- Escolha a biblioteca de inferência no navegador (WebGPU) que rode um modelo de 1B a 3B em português com qualidade medida.
  - Registre as opções avaliadas, a escolhida e o porquê.
  - A biblioteca é **servida pelo PAULUS**, com versão fixa e o hash conferido no teste.
  - **⏸ PAUSA** se ela trouxer dependência de build ou exigir código de fora do PAULUS.
- **Web Worker dedicado:** recebe o pacote, escreve, devolve e **apaga** tudo o que recebeu.
  - Nada em `localStorage`, `sessionStorage`, IndexedDB, Cache Storage ou Service Worker, exceto os pesos do modelo.
  - Os pesos ficam no armazenamento que a biblioteca usar, sob uma chave que contém só o nome e o hash do modelo.
- **Pesos:** origem fixa, hash conferido antes do primeiro uso e a cada atualização. Hash errado → apaga e recusa.
- **Teste de capacidade** na primeira vez: verifica se há WebGPU, a memória disponível e mede a velocidade num texto de exemplo **sem dados do escritório**. Não passou → o seletor não aparece, com o motivo em "Configurações do aparelho".
- **CSP:** `connect-src` inclui só a origem dos pesos; nenhuma outra origem nova.
- Parâmetros de escrita iguais aos do escritório (temperatura, teto de resposta), e o perfil vem do registry de modelos.

**Portão.** `tests/test_d2_motor.py` + Playwright com um navegador que tenha WebGPU (pula com aviso sem ele):
- depois de uma resposta, nenhum armazenamento do navegador contém texto da pergunta, dos trechos ou da resposta (varra todos os armazenamentos);
- pesos com hash adulterado → recusa;
- a página não faz nenhuma requisição para origem que não seja o PAULUS ou a origem dos pesos;
- o teste de capacidade não envia nada ao servidor além do resultado numérico.

---

### D3 — Conferência no escritório e retomada

**Contrato.**
- O texto devolvido passa pelas mesmas conferências de uma resposta escrita no escritório, **na mesma função**, e não numa cópia.
- Reprovou → refaz no escritório, marca "conferência reprovou" e registra o que reprovou.
- **Abandono:** aba fechada, aparelho sem sinal ou pacote vencido. O escritório termina a resposta a partir do texto parcial já recebido, se houver (o aparelho envia pedaços durante a escrita, pela mesma execução), ou do zero.
- A resposta final registra onde foi escrita, o modelo e se foi conferida ou refeita.

**Portão.** `tests/test_d3_conferencia.py`, com um aparelho simulado:
- texto com número que não está nos trechos → refeito no escritório;
- texto com citação para trecho inexistente → refeito;
- texto com lei inventada → a lei sai, como no escritório;
- aparelho que some no meio → o escritório termina, e a conversa mostra onde cada parte foi escrita;
- resposta aprovada fica igual à que o aparelho mandou, com a marca "escrita neste aparelho".

---

### D4 — O switch e a tela

**Contrato (§3):**
- seletor Escritório · Este aparelho · Automático, só para contas liberadas e aparelhos aprovados; guardado por aparelho;
- **a janela de sugestão do §3**, antes de a pergunta entrar na fila, com as condições e os três botões de lá. "Não sugerir de novo hoje" é guardado por aparelho até a meia-noite. Com Ctrl+Enter, a sugestão aparece do mesmo jeito: prioridade no escritório e aparelho são escolhas diferentes;
- primeira vez: tamanho, tempo e o aviso do §2.6, com "entendi";
- Automático: compara a velocidade medida no aparelho com a fila e a velocidade do escritório **naquele momento**;
- em cada resposta, onde foi escrita e por quê, em linguagem simples;
- "Configurações do aparelho", no acesso de fora: estado do teste, tamanho do modelo guardado e "apagar o modelo deste aparelho".
- No celular, o seletor só aparece se o teste de capacidade passar. Na prática, espere que a maioria dos celulares não passe, e deixe o motivo claro.

**Portão.** `tests/test_d4_switch.py` + Playwright:
- conta sem liberação não vê o seletor;
- Automático com a fila do escritório vazia e o aparelho lento escolhe o escritório; com fila cheia e aparelho rápido, escolhe o aparelho;
- a resposta mostra onde foi escrita;
- "apagar o modelo" remove os pesos;
- com a fila do escritório acima do limite, a janela de sugestão aparece; abaixo, não aparece;
- pergunta de caso "só no escritório" nunca mostra a sugestão;
- "Usar este aparelho" na janela escreve no aparelho e tira a pergunta da fila do escritório;
- "Não sugerir de novo hoje" some até o dia seguinte.

---

### D5 — O que o titular controla

**Contrato (§2.5):**
- na janela local, em Acesso de fora: ligar o recurso para o escritório e **por conta**;
- **"Só no escritório"** por cliente, caso ou pasta, respeitado **na montagem do pacote**, no servidor;
- relatório na auditoria: quantas respostas foram escritas em aparelho, por pessoa, e quantas foram refeitas por conferência reprovada;
- desligar o recurso invalida na hora todo pacote em andamento, e as respostas terminam no escritório.

**Portão.** `tests/test_d5_titular.py`:
- colaborador não consegue ligar para si mesmo, nem pelo acesso de fora;
- marcar um caso como "só no escritório" faz perguntas sobre ele irem ao escritório, mesmo com o switch ligado;
- desligar no meio de uma resposta faz ela terminar no escritório.

---

### D6 — Política, manual e teste real

**Contrato.**
- Atualize a política de privacidade e os termos com o que o §2 diz, em linguagem simples: o que vai ao aparelho, o que fica nele, o que o escritório confere, o que não dá para garantir e quem decide. **Não publique.**
- `docs/pensar-no-aparelho.md`: como ligar, como marcar casos "só no escritório", como apagar o modelo do aparelho e a solução de problemas.

**⏸ PAUSA D6 — teste real.** Dê-me um roteiro para eu fazer de um notebook fora do escritório:
1. ligar o recurso para a minha conta na janela local;
2. entrar pelo acesso de fora, passar pelo teste de capacidade e baixar o modelo;
3. fazer 5 perguntas em "Este aparelho" e conferir que foram escritas lá e conferidas no escritório;
4. marcar um caso como "só no escritório" e perguntar sobre ele;
5. fechar a aba no meio de uma resposta e ver o escritório terminar;
6. abrir as ferramentas do navegador e conferir que nenhum armazenamento guarda texto da conversa;
7. apagar o modelo do aparelho.

Espere o meu resultado e corrija o que eu reportar, cada correção com teste.

---

## 5. Não fazer

- Mandar documento inteiro, índice, vetores ou metadata para o aparelho.
- Ingestão, OCR, extração ou edição de documento no aparelho.
- Carregar a biblioteca do motor de CDN de terceiros, ou usar pesos sem hash conferido.
- Guardar pergunta, trecho ou resposta em qualquer armazenamento do navegador.
- Confiar no texto que volta sem conferir no escritório.
- Deixar o colaborador ligar o recurso para si mesmo.
- Ligar por padrão.

---

## Resumo da ordem

```text
D0 levantamento e medida da fila remota (⏸ números)
→ F1 fila dentro da conversa, fila única de todas as telas, Ctrl+Enter com prioridade
→ D1 o pacote e a porta (o que pode sair, montado depois das permissões)
→ D2 o motor no navegador (Worker, nada guardado, pesos com hash)
→ D3 conferência no escritório e retomada
→ D4 o switch, a tela e a sugestão de usar o aparelho quando o escritório está ocupado
→ D5 o que o titular controla (por conta, casos "só no escritório")
→ D6 política, manual e teste real (⏸ roteiro)
→ [perguntar: publicar?]
```

Comece pelo passo 0.1.
