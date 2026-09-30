# Plano do piloto — o que o dono propôs em 30/09/2026

Pedido: "quero que você implemente tudo o que eu propus, até os passos
futuros, agora". Fica de fora, como ele mesmo disse: busca de
jurisprudência em massa, agente com autonomia sem confirmação, e qualquer
coisa que dependa de nuvem.

Regras que valem em todas as etapas (as da casa): nada publicado sem ele
pedir; o que sai da máquina vem desligado de fábrica e é dito na tela;
modelo só quando a regra não basta; o que o sistema gera vai para
subpastas do Acervo; texto de tela só promete o que o código garante;
cada etapa com teste que termina em "todos os testes passaram".

| Etapa | O quê | Estado | Teste |
| --- | --- | --- | --- |
| L1 | Aprender com o uso: 👍/👎 em cada resposta, caderno de falhas, a correção vira caso de teste | feito | `tests/test_l1_aprender.py` |
| L2 | Acompanhamento de processos pelo DataJud: movimentação nova vira aviso; prazo sugerido com a conta, pela Aprovação | feito | `tests/test_l2_processos.py` |
| L3 | Visão por cliente e muralha ética: a mesma entidade com nomes diferentes, parte contrária, "tudo sobre o cliente", aviso de conflito | feito | `tests/test_l3_clientes.py` |
| L4 | Tarefas de vários passos com ponto de restauração: contratos vencendo em N dias, revisar contrato contra o padrão da casa | feito | `tests/test_l4_tarefas.py` |
| L5 | A Biblioteca ajudando a escrever: fundamentação sugerida no editor, súmulas e temas repetitivos, posição da casa por artigo | feito | `tests/test_l5_fundamentacao.py` |
| L6 | Modelo por máquina: perfis por faixa de hardware, com GPU NVIDIA, AMD e Intel | feito | `tests/test_l6_perfis.py` |
| L7 | Servidor MCP além das leis: Acervo só leitura, permissão e escopo por conexão | feito | `tests/test_l7_mcp.py` |
| L8 | Captura pelo celular: destino no Serviço, foto borrada avisada, OCR na entrada | pendente | `tests/test_l8_captura.py` |
| L9 | Materiais entre advogados: página no site, "Da comunidade" na Biblioteca, envio por e-mail com conferência de dados pessoais | pendente | `tests/test_l9_materiais.py` |
| L10 | Lei com vigência: histórico de cada artigo e o texto vigente numa data (pelo ano da lei) | pendente | `tests/test_l10_vigencia.py` |

O que cada etapa fez, decidiu e mediu fica numa seção abaixo, na ordem.

## L1 — aprender com o uso (30/09/2026)

- **👍/👎** na assinatura de cada resposta de uma pergunta
  (`js/63-aprendizado.js`; os polegares são SVG, porque o recorte da fonte
  de ícones não os tem). A nota fica por resposta e por pessoa ("local" ou
  a conta de fora), com a cópia da pergunta, da resposta, dos documentos
  citados, do caminho, do modelo e de onde foi escrita (tabela
  `avaliacoes`, migração 027): a conversa pode mudar ou ir para a lixeira, e
  o caderno continua contando o que houve.
- **O cartão da 👎**: motivo (errou um fato, faltou informação, citou errado
  ou sem fonte, não entendeu a pergunta, demorou demais, outro), o que
  estava errado, a resposta certa e **o que a resposta certa precisa ter**.
  Com esse último preenchido, a pergunta vira **caso de teste** no conjunto
  real (`data/medicao/conjunto-real.jsonl`, o mesmo das correções do cartão
  do documento), com cada termo obrigatório (`todas`), e `tools/medir.py`
  mede cada troca contra ele.
- **O caderno de falhas** (Configurações › Feedback, só na janela do
  escritório): as 👎 dos últimos 30 dias, as contas por caminho e por
  motivo, "abrir a conversa", "virar caso de teste" depois, "resolvida" e
  "reabrir". A chave `aprendizado.avaliar` fica ali, **ligada de fábrica**:
  o piloto mede desde o primeiro dia, e nada sai do computador.
- De fora, cada pessoa avalia as próprias respostas (com o nome dela) e não
  lê o caderno. O painel "Sobre esta resposta" ganha a linha "Avaliação".

**Lição (vale para as próximas rotas):** com `from __future__ import
annotations`, modelo pydantic ou `Request` importados dentro de `montar`
não se resolvem — o FastAPI trata o corpo como query e o `request` chega
`None` (e `so_local` passa a achar que tudo é local). Tudo no nível do
módulo.

**Medido:** `tests/test_l1_aprender.py` 24 ok (API, contas de fora, chave
desligada, e no Edge: polegares, cartão, marca que volta ao reabrir,
caderno).

## L2 — processos pelo DataJud (30/09/2026)

- **Os processos** (`src/processos.py`, tabelas `processos` e `movimentos`,
  migração 028): número à mão (entra acompanhado) ou **"Achar nos
  documentos"**, que traz os números CNJ que a leitura já validou
  (`meta_fatos`, seção `case`), ligados sozinhos ao Serviço da pasta de onde
  o documento veio, e **sem acompanhar** até alguém ligar.
- **A volta diária** (thread `processos`, como a das publicações): cada
  processo acompanhado é consultado no DataJud (`tribunais.consultar_datajud`,
  agora com todos os movimentos). **Só o número sai deste computador.**
  Chave `processos.acompanhar`, **desligada de fábrica**, na própria tela.
  A primeira consulta de um processo só guarda o que já havia — sem isso, o
  escritório ganharia cem avisos de coisa antiga.
- **Movimentação nova** → um aviso por processo na Central (tipo "Processo",
  com "Marcar como vistas"). **Intimação, citação ou publicação** → um pedido
  em Aprovações ("Prazo? …") com a conta inteira de `src/prazos.py` (15 dias
  úteis, pela disponibilização quando é publicação). O sim cria a tarefa em
  Tarefas › Prazos, com a conta na anotação e o lembrete: a data do DataJud é
  a do registro do movimento; confira a data da ciência.
- **A tela**: Serviços › **Processos** (a lista, a chave, adicionar, achar,
  consultar todos) e a aba **Processos** de cada Serviço; o detalhe de um
  processo mostra as movimentações, com as novas marcadas, e deixa trocar o
  Serviço, ligar o acompanhamento, consultar agora e tirar da lista.
- **De fora**: a pessoa vê só os processos dos Serviços dela e marca como
  vistas; acompanhar, consultar e mudar são da janela do escritório (é o
  que faz o número sair).

**Não feito:** o tempo do prazo não sabe o tipo de ato (contestação,
apelação): é sempre 15 dias úteis, e a tela diz que é sugestão. Não há
ligação ainda entre a publicação do DJEN e o processo acompanhado (duas
fontes, dois avisos).

**Medido:** `tests/test_l2_processos.py` 25 ok (com o DataJud de mentira:
prazo sugerido, achar nos documentos, a base da primeira consulta, o aviso,
a Aprovação e a tarefa, vistas, sem duplicar, erro guardado, de fora, e a
tela no Edge).

## L3 — visão por cliente e muralha ética (30/09/2026)

- **A mesma entidade** (`src/clientes.py`, `chave` e `mesma`): sem acento,
  sem pontuação, sem a forma jurídica (Ltda., S/A, ME, EPP, EIRELI…) e sem
  "de/da/do": "Empresa X Ltda." = "EMPRESA X" = "Empresa X - ME". Com os
  dois documentos, **o documento manda**: CPF igual, ou a mesma raiz do CNPJ
  (matriz e filiais); documento diferente não é a mesma, mesmo com o nome
  igual. Nome quase igual (a ordem trocada, uma palavra a mais) é **"parece
  ser"**, e a tela diz qual das duas.
- **A parte contrária** de cada Serviço (coluna `servicos.partes`, migração
  029), na seção **Partes** da visão geral do Serviço.
- **Conflito de interesse** — avisa, não bloqueia: a parte contrária que é
  cliente do escritório; a que é o próprio cliente do Serviço; o cliente que
  é parte contrária em outro Serviço (ao gravar a ficha, e na seção Partes
  do Serviço dele).
- **Muralha ética**: a separação por equipe já existia (quem não está na
  equipe não vê o Serviço de fora). O conflito diz agora **quem está na
  equipe dos dois lados** — é essa pessoa que a muralha precisa separar.
- **Tudo sobre o cliente** (botão na ficha do cliente): o conflito no alto,
  os Serviços, os processos (L2), os prazos e compromissos em aberto, a parte
  contrária dos Serviços dele, os documentos (os ligados à ficha e aos
  Serviços, e os em que ele aparece como parte, pelos fatos da leitura) e
  "também aparece como" (os outros nomes com que ele aparece).
- De fora, a visão e a conferência (que cruzam todos os clientes) não
  respondem; mudar as partes segue o nível de Serviços.

**Não feito:** a parte contrária não é tirada sozinha dos documentos (a
leitura acha as partes, mas não sabe de que lado está o cliente); o aviso
de conflito não fica guardado como pendência — ele aparece de novo onde a
mesma entidade é conferida.

**Medido:** `tests/test_l3_clientes.py` 26 ok.

## L4 — tarefas de vários passos, com ponto de restauração (30/09/2026)

- **O executor** (`src/passos.py`): uma tarefa é uma receita de passos que
  roda em segundo plano, com cada passo à vista (esperando, fazendo, feito,
  falhou), para ser parada, e deixa um relatório no editor. Guardada em
  `<dados>/passos/<id>/`. Os passos que usam o modelo passam pela fila única
  (F1), como toda chamada.
- **O ponto de restauração** (`Restauracao`): antes de criar ou mudar, a
  tarefa anota — o documento do relatório, os pedidos em Aprovações, as
  tarefas, os arquivos criados (com o hash) e a **cópia do original** de
  cada arquivo que vai alterar. **Desfazer** volta tudo do último para o
  primeiro e diz, item por item, o que fez. Não apaga nem volta o que alguém
  mudou depois (seria apagar trabalho de outra pessoa), e o pedido que já foi
  aprovado fica (o que ele fez é do sim de alguém): a tarefa vira "desfeita
  em parte" e diz o quê.
- **Contratos vencendo nos próximos N dias**: pelas datas **conferidas** da
  leitura (vencimento e fim de vigência, `ajuda.prazos`), só contratos (pela
  classificação), sem modelo; o relatório em tabela com a página e o
  trecho; opcional, cada data vira pedido em Aprovações para a Agenda.
- **Revisar contra o padrão da casa**: as cláusulas dos dois (`redacao.
  achar_clausulas` — "CLÁUSULA 1ª", "CLÁUSULA PRIMEIRA"), alinhadas pelo
  título e pelo texto mesmo fora de ordem, e comparadas palavra por palavra:
  igual, alterada (o que saiu do padrão e o que entrou), faltando, a mais.
  Só se a pessoa pedir, o modelo explica em uma frase até 6 cláusulas
  alteradas, e a frase vai marcada "O assistente (confira)". O padrão pode
  ser um documento do Acervo ou do editor.
- **A tela**: Agentes › **Tarefas de vários passos** (as receitas, rodar, os
  passos, abrir o relatório, parar, desfazer). Só na janela do escritório.

**Não feito:** o agente em markdown ainda não chama uma receita sozinho (a
tarefa é pedida pela tela); cláusula no estilo "1. DO OBJETO", sem a
palavra "cláusula", não é reconhecida (a mesma regra do editor).

**Medido:** `tests/test_l4_tarefas.py` 20 ok.

## L5 — a Biblioteca ajudando a escrever (30/09/2026)

- **Temas repetitivos e IAC do STJ, oficiais**: o `Temas.csv` do [Portal de
  Dados Abertos do STJ](https://dadosabertos.web.stj.jus.br/dataset/precedentes-qualificados)
  (licença CC-BY), baixado em 30/09/2026 e posto no instalador
  (`config/acervo-inicial/temas-stj.jsonl.gz`, 269 KB, montado por
  `tools/temas_stj.py`): 1.330 linhas, 1.301 temas (o STJ repete o número dos
  revisados; fica a última), 1.181 com tese firmada. Saem cancelados,
  controvérsias, vinculados a outro tema e sem processo. Entram na primeira
  abertura (tabela `temas`, migração 030). **"Atualizar pelo STJ"** (rota)
  baixa do portal só quando pedido; arquivo com menos de 100 temas não troca
  nada. Cada tema fica ligado, por regra, aos artigos que a tese e a questão
  citam ("art. 206 do CC" → `cc:206`; CPC/73 e CC/1916 ficam de fora): 240
  temas ligados.
- **A posição da casa** por artigo (tabela `posicoes`): escrita pelo titular,
  na janela do escritório, embaixo de cada artigo achado em "Citar artigo",
  junto dos temas do STJ que citam o artigo.
- **Fundamentar** (novo botão no painel do editor): para o trecho escolhido
  (ou o parágrafo do cursor), os artigos citados nele (primeiro), os achados
  pelos pares de palavras do trecho ("multa moratória", "cláusula penal") e
  pelas palavras soltas, em rodízio para cada ideia ter lugar; as súmulas do
  STJ; os temas; a posição da casa junto do artigo. Cada item diz o porquê e
  insere o texto oficial. Sem modelo.

**Não feito:** súmulas do STF e repercussão geral (o STF barra programa; ver
B1); os temas não entram na resposta da conversa sozinhos — só pela
fundamentação do editor e pelo artigo.

**Medido:** `tests/test_l5_fundamentacao.py` 23 ok (no trecho de teste, o
Tema 970/STJ — cláusula penal moratória — é sugerido).

## L6 — modelo por máquina (30/09/2026)

- **O perfil** (`src/perfis.py`), a partir do teste da máquina que já existia
  (memória, placas pelo nvidia-smi e pelo Windows, fabricante, integrada):
  - **NVIDIA** (CUDA, sozinho): de 10 GB, o 3B em 8 bits e, como
    alternativa, um 7-8B — **sem nota no roteiro desta casa: meça antes**; de
    6 GB, o 3B em 8 bits inteiro na placa; de 3,5 GB, o 3B de fábrica; abaixo,
    divide com o processador;
  - **AMD**: ROCm nas Radeon da lista do Ollama no Windows (RX 7600–7900,
    RX 6800–6950, Vega, PRO W6800/W7x00); nas outras, **Vulkan**;
  - **Intel Arc**: Vulkan; **placa integrada**: o processador, e dito;
  - **só processador**: abaixo de 8 GB, o 1B (acerta 22 de 41 — dito); de
    8 GB, o 3B de fábrica (41 de 41).
  A memória que o Windows dá das placas AMD e Intel para em 4 GB: o perfil
  avisa que é ordem de grandeza.
- **Configurações › Modelos › Perfil desta máquina**: a faixa, a placa, por
  onde o Ollama roda, a sugestão e o porquê. **Nada é trocado sozinho**: o
  perfil sugere, a pessoa mede em "Nesta máquina" e troca.
- **Usar a placa pelo Vulkan** (quando o perfil é Vulkan): grava
  `OLLAMA_VULKAN=1` na conta do Windows (HKCU\Environment) e diz para
  reabrir o Ollama; desligar apaga a variável. Só na janela do escritório.

**Não medido:** nenhuma placa AMD, Intel ou NVIDIA de verdade — esta
máquina é só processador (o perfil dela: "Só o processador · llama3.2:3b").
O efeito do Vulkan fica para quem tiver a placa: medir antes e depois em
Modelos (a medida já diz se o modelo rodou na placa).

**Medido:** `tests/test_l6_perfis.py` 18 ok (máquinas de mentira por faixa,
a rota, e o cartão no Edge).

## L7 — o servidor MCP além das leis (30/09/2026)

O `/mcp` (src/mcp_leis.py, ideia A do umbrelOS) só dava as leis. Agora,
conexão por conexão, na janela do escritório:

- **Públicas** (como a lei): `sumulas_stj` e `temas_stj` (L5), além das três
  das leis.
- **Do escritório, só leitura**: `acervo_documentos`, `acervo_procurar` (até
  6 trechos, com a página), `acervo_cartao` (os fatos conferidos, com página
  e trecho) e `posicao_da_casa`. Só com um **escopo** — o Acervo inteiro,
  pastas do Acervo ou Serviços — e com o **"entendi que sai"** marcado: o
  trecho vai para o assistente conectado e dali para a empresa dele. A
  criação recusa sem os dois. **Caso "só no escritório" nunca sai**, nem com
  o Acervo inteiro liberado.
- As travas de antes continuam: desligado de fábrica, só deste computador
  (nunca pelo túnel), token por conexão guardado só pelo resumo, cada chamada
  na auditoria; a criação anota o que é do escritório e o escopo.
- O servidor se apresenta como `paulus` (era `paulus-leis`), e o cartão de
  Configurações › Conexões deixou de dizer "só texto de lei": diz o que cada
  conexão pode ter e o que nunca sai (cadastros, financeiro, e-mail, agenda).

**Não feito:** ferramenta que escreve (de propósito: o plano diz só
leitura); escopo por cliente (pelos Serviços dele dá).

**Medido:** `tests/test_l7_mcp.py` 16 ok; `tests/test_umbrel_a_mcp.py`
continua passando (com o nome novo).
