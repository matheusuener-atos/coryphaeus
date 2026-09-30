# PAULUS — Ideias vindas do umbrelOS 2.0: avaliar, escolher, fazer

(Briefing entregue pelo dono em 30/09/2026, para ser feito logo depois da
Biblioteca — ver docs/PROGRESSO-BIBLIOTECA.md, "Na sequência". O andamento vai
em docs/DECISAO-UMBREL.md.)

Este não é um plano fechado. É um **briefing**: explica seis ideias, o porquê de cada uma e os limites que não podem ser cruzados. **Quem decide o que será feito, em que ordem e de que jeito é você**, depois de ler o código do PAULUS Legal (`paulus/legal/`) como ele está hoje.

Leia tudo antes de começar.

---

## 1. De onde vêm as ideias

Em setembro de 2026 a Umbrel lançou o **umbrelOS 2.0**, um sistema de "nuvem em casa" que roda numa máquina da própria pessoa. Ele tem princípios parecidos com os do PAULUS: local-first, Ollama, contas por pessoa, acesso remoto e backup. A diferença é que o Umbrel é **horizontal** (uma loja com centenas de apps para qualquer coisa), e o PAULUS é **vertical**: um co-worker jurídico que lê, confere e cita.

O que o umbrelOS 2.0 trouxe e interessa aqui:
- um **servidor MCP** embutido, com um token e um nível de acesso por conexão, para agentes externos (Claude Code, Codex e outros) operarem a máquina;
- **"Rewind"**: pontos de restauração do sistema, para voltar a um estado anterior;
- detecção de **GPU NVIDIA, AMD e Intel**, repassada ao Ollama;
- **contas por pessoa**, com área privada e compartilhamento escolhido pelo dono;
- **HTTPS na rede local**;
- um **app de celular** que manda as fotos sozinho para a máquina.

O que o Umbrel **não** tem, e o PAULUS tem: conhecimento jurídico, metadata verificada, citação com página, leis com revogados marcados, biblioteca do escritório, fila de Aprovações, auditoria e acesso de fora com anti-robô, senha, TOTP e permissões por rota. **Não copie o Umbrel. Pegue a ideia e dê a ela a forma de um escritório de advocacia.**

---

## 2. As seis ideias

### A. Servidor MCP do PAULUS

**Problema.** O advogado já usa outros assistentes (Claude, ChatGPT e outros). Hoje eles não enxergam a biblioteca nem o acervo do escritório, e inventam artigo de lei que o PAULUS saberia citar certo.

**Forma.** O PAULUS expõe ferramentas por MCP, reaproveitando o catálogo de ações que já tem contrato JSON (`ferramentas.py` ou o que o substituiu):
- **só leitura, de início:** citar um artigo de lei, buscar na biblioteca, ver o cartão de um documento, listar prazos;
- **um token por conexão**, criado e revogado só na janela local, cada um com a sua lista de ferramentas;
- as mesmas permissões por rota do acesso de fora, com padrão "nega";
- toda ação que muda algo passa pela fila de Aprovações;
- toda chamada vai para a auditoria.

**Risco — o mais sério desta lista.** O que o PAULUS devolve vai para o modelo de **outra empresa**. Isso quebra a promessa de "nada sai da máquina", a menos que o escritório escolha isso de forma explícita e informada, conexão por conexão. Desligado de fábrica, com aviso claro na tela ao criar cada conexão. **Qualquer ferramenta que devolva texto de documento de cliente exige a sua PAUSA (§4).**

### B. Ponto de restauração antes de cada tarefa

**Problema.** Tarefas de vários passos e agentes (inclusive os da ideia A) vão escrever, mover e redigir. Um erro num lote é difícil de desfazer à mão.

**Forma.** Antes de cada tarefa com efeito, o PAULUS guarda um ponto de restauração do que ela pode tocar: metadata, biblioteca, agenda, cadastros, rascunhos e índices. Na tela, cada tarefa ganha **"desfazer tudo o que esta tarefa fez"**. Os pontos mais antigos são apagados por regra de idade e espaço. Reaproveite o `backup.py` ou o que existir hoje.

**Risco.** Espaço em disco, e a restauração parcial deixar índice e metadata desencontrados. Restaurar precisa ser tudo ou nada, e testado.

### C. Acesso pela rede do escritório, sem sair para a internet

**Problema.** O colaborador na sala ao lado hoje ou usa o computador do PAULUS, ou entra pelo túnel da Cloudflare, e aí o tráfego sai do prédio para voltar.

**Forma.** Um modo "rede do escritório", desligado de fábrica:
- o PAULUS também escuta no endereço da rede local, **só nele** (nunca `0.0.0.0` em interface pública);
- HTTPS com certificado próprio da instalação e instrução de confiança para as outras máquinas;
- as mesmas contas, TOTP, permissões e auditoria do acesso de fora;
- aviso na tela quando a rede parecer pública (Wi-Fi sem senha, nome de rede de hotel e similares).

**Risco.** Abre uma porta que hoje não existe. O firewall do Windows, a escolha de interface e o certificado precisam ser feitos com cuidado. A regra de ouro atual ("escuta só em 127.0.0.1") é quebrada de propósito, e isso **exige a sua PAUSA** antes de implementar.

### D. Muralha ética entre casos

**Problema.** O Umbrel dá uma pasta privada por pessoa. Um escritório precisa de mais: quando há conflito de interesse, ou por pedido do cliente, um advogado não pode ver o caso do outro.

**Forma.** Casos ou clientes com **equipe definida**. Quem não está na equipe não vê o documento, não recebe trecho dele na busca, não vê o cartão e nem sabe que ele existe. O filtro vale **antes** da recuperação, em todo índice (léxico, denso e biblioteca), e não depois. O titular define a equipe na janela local, e tudo fica na auditoria.

**Risco.** Vazamento por um caminho esquecido: busca, sugestões, agenda, prazos, cartão, lista de arquivos, "ler tudo". O portão precisa percorrer todas as rotas, como a R3 fez com as permissões.

### E. Capturar documento pelo celular

**Problema.** O advogado recebe papel no fórum ou no cliente, e ele só entra no PAULUS quando alguém escaneia no escritório.

**Forma.** Uma tela de câmera na interface web, que já roda no celular pelo acesso de fora. O advogado fotografa uma ou várias páginas e confirma. O documento entra no Acervo com OCR, cartão e prazos propostos pela fila. Sem app nativo.

**Risco.** OCR de foto ruim, e página torta ou cortada. Mostrar a prévia antes de confirmar, e medir o OCR com fotos reais.

### F. GPU AMD e Intel

**Problema.** Muito computador de escritório tem só a placa integrada Intel ou AMD. Se o PAULUS só reconhece NVIDIA, ele escolhe um modelo menor do que a máquina aguentaria.

**Forma.** Ampliar a leitura de recursos da máquina (`maquina.py` ou o que o substituiu) e a escolha de modelo por faixa, confirmando **pela medida**, e não pela tabela, que o Ollama realmente usa a placa naquela máquina.

**Risco.** Baixo. Placa detectada que o Ollama não usa: a medida decide.

### O que não entra

- **Loja de apps.** O valor do PAULUS está em ser estreito e confiável no direito. O equivalente certo de uma loja é o futuro espaço de materiais compartilhados entre advogados, que tem outro briefing.
- **Vender ou exigir hardware.** Decisão de produto: o PAULUS roda no computador que o escritório já tem.
- **Backup contínuo para nuvem de terceiros como padrão.** Pode existir como opção do escritório, nunca ligado de fábrica.

---

## 3. Como decidir

### 3.1 Primeiro, o levantamento

Antes de escolher, leia o código atual de tudo o que as ideias tocam: ferramentas, permissões por rota, acesso de fora, fila de Aprovações, auditoria, backup, leitura da máquina, acervo, busca e contas. Leia também `docs/ETAPAS.md`, do fim para o começo. O projeto muda rápido: algo daqui pode já existir, em parte ou inteiro.

Escreva `paulus/legal/docs/DECISAO-UMBREL.md` com uma linha por ideia:

| Ideia | Existe hoje? | Valor para o advogado | Risco | Esforço | Depende de | Decisão |
|---|---|---|---|---|---|---|

**Decisão** é uma de três: **fazer agora**, **fazer depois** (e depois de quê) ou **não fazer** (e por quê). "Não fazer" é uma resposta válida e deve ser usada quando o custo ou o risco não se pagam.

### 3.2 Critérios, nesta ordem de peso

1. **Não quebrar promessas do produto:** nada sai da máquina sem escolha explícita; a confirmação humana continua; o que é citado é conferível.
2. **Valor no dia a dia do advogado**, não na lista de recursos.
3. **Reaproveitamento:** ideia que usa peças prontas vem antes de ideia que pede peça nova.
4. **Uma ideia que torna outra segura vem antes dela.** Por exemplo, B antes de dar poder de escrita a agentes pela A.
5. **Esforço e dependências novas.** Dependência nova só com justificativa.

### 3.3 Depois de decidir

- Escolha **no máximo três** ideias para "fazer agora".
- Para cada uma, escreva no `DECISAO-UMBREL.md` um contrato curto: o que entra, o que fica de fora, a chave que a liga e o **portão** (teste automatizado ou número medido).
- Implemente uma por vez, na ordem que você definiu, e siga direto de uma para a outra, salvo nas PAUSAS do §4.

---

## 4. Quando PARAR e perguntar

Pare, explique em poucas linhas e espere resposta **somente** quando:
- a ideia escolhida fizer **conteúdo do escritório sair da máquina** (a ideia A com qualquer ferramenta que devolva texto de documento de cliente, por exemplo);
- a ideia escolhida **abrir uma porta de rede nova** (a ideia C);
- a ideia mudar o que o advogado vê em toda resposta ou em toda tela;
- o portão não passar depois de 3 tentativas honestas (mostre o que mediu);
- o código contradisser este briefing de um jeito que exija escolha de produto;
- uma dependência nova parecer necessária.

**Ao fim do levantamento**, mande-me a tabela do `DECISAO-UMBREL.md` com a sua escolha e siga para a implementação sem esperar, **a menos que** a escolha inclua algum item dos dois primeiros pontos acima. Nesse caso, espere a minha resposta.

Fora disso, decida, registre e continue.

---

## 5. Como trabalhar (vale para tudo o que for feito)

- **Uma ideia por branch** (`umbrel-a-mcp`, `umbrel-b-restauracao`…). Leia o código antes de mudar e escreva o teste do portão primeiro.
- **Rode a suíte inteira** (`tests/test_*.py`) e o banco de provas que existir hoje. Regressão bloqueia.
- **Toda mudança de comportamento nasce atrás de chave** em `config.PADRAO`, desligada até o portão fechar.
- **Código novo em módulo novo.** O `api.py` só registra rotas e chama.
- **Nomes e comentários em português.** O comentário explica o porquê, de preferência com o que foi medido. Testes são scripts que terminam com `todos os testes passaram`; o que depende de Windows, Ollama ou rede pula com aviso.
- **Registre** cada ideia feita em `docs/ETAPAS.md` e o andamento no `DECISAO-UMBREL.md`: o que entrou, o que foi medido, o que a verificação achou.
- **Não publique e não faça `git push`** sem perguntar.
- **Segredos** (tokens MCP, certificados) só pelo mecanismo de segredos que o projeto já usa, nunca em JSON puro nem em log.

---

## 6. Ao terminar

Atualize o `DECISAO-UMBREL.md` com o que foi feito, os números dos portões e o que ficou para depois, com o motivo. Depois pergunte se deve publicar e fazer push.

Comece pelo levantamento (§3.1).
