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
| L8 | Captura pelo celular: destino no Serviço, foto borrada avisada, OCR na entrada | feito | `tests/test_l8_captura.py` |
| L9 | Materiais entre advogados: página no site, "Da comunidade" na Biblioteca, envio por e-mail com conferência de dados pessoais | feito | `tests/test_l9_materiais.py` |
| L10 | Lei com vigência: histórico de cada artigo e o texto vigente numa data (pelo ano da lei) | feito | `tests/test_l10_vigencia.py` |

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

## L8 — captura pelo celular (30/09/2026)

A captura já existia (ideia E do umbrelOS: fotos viram PDF, OCR do Windows,
de fora passa por Aprovações). O que a L8 acrescentou (`src/captura.py`,
`js/51-captura.js`):

- **Foto tremida e foto escura avisadas na prévia**, antes de guardar
  (`POST /api/captura/conferir`, que não grava nada): a nitidez é a
  variância do laplaciano depois de uma mediana (que tira o ruído do sensor
  do celular, que passaria por nitidez), e a luz é a média. Medido numa A4
  de texto: nítida > 2.000, com ou sem ruído; desfocada com raio 4 ou mais
  < 200; limite 350. A prévia diz "tremida ou fora de foco — fotografe de
  novo" só na página que precisa.
- **Guardar em um Serviço**: o documento vai direto para a pasta do Serviço
  escolhido (na janela do escritório) ou, de fora, o pedido em Aprovações
  leva o Serviço e o sim põe lá. De fora, só um Serviço que a pessoa vê.
- **A entrada diz o que a leitura achou**: quantas páginas vieram pelo OCR e
  quantos caracteres, ou por que não leu; o resultado da Aprovação diz o
  mesmo.

**Não feito:** corte automático das bordas e endireitar a perspectiva (a
foto vai como veio); o limite de nitidez foi calibrado com página gerada,
não com fotos de celular de verdade — fica para o teste real.

**Medido:** `tests/test_l8_captura.py` 14 ok (com OCR de verdade: 2 páginas
lidas); `tests/test_umbrel_e_captura.py` continua passando.

## L9 — materiais entre advogados (30/09/2026)

Sem servidor novo e sem custo: o site do PAULUS publica uma lista curada
(`site/dados/materiais.json`) e os arquivos (`site/materiais/<slug>.md`).

- **A página** `paulus.ia.br/materiais/` (no menu do site): título, autor
  (e OAB, se ele quiser), área, data, resumo, licença e "Ler o material".
  Vazia, diz que ainda não há material. Moderada: o dono lê e publica
  (`docs/materiais.md`, com o hash de cada arquivo).
- **Biblioteca › Da comunidade** (janela do escritório): "Ver os materiais"
  lê a lista **só quando a pessoa pede** — vai só o pedido do arquivo
  público. "Trazer para a Biblioteca" confere o SHA-256 publicado na lista
  (diferente, não entra; endereço fora de `/materiais/`, também não) e o
  material entra com a origem **comunidade**, o autor e a licença.
- **Publicar um material seu**: o PAULUS **confere os dados pessoais antes**
  — número de processo, CNPJ, CPF (só o válido), e-mail, telefone e o nome
  de cada cliente do escritório (reconhecido com outro jeito de escrever,
  pela L3) — e diz que nome de pessoa que não é cliente a regra não acha.
  Com o "tirei os dados (ou tenho autorização) e autorizo CC BY 4.0", monta
  o e-mail para contato@paulus.ia.br pela conta da pessoa, que revisa antes
  (a mesma saída do feedback); sem conta, copia.

**Não publicado:** a página, a lista vazia e o menu vão com o próximo
`publicar`.

**Medido:** `tests/test_l9_materiais.py` 21 ok (com o site de mentira no
programa, e a página de verdade servida localmente no Edge).

## L10 — lei com vigência (30/09/2026)

- **O histórico de cada artigo, dispositivo por dispositivo**
  (`src/vigencia.py`): o texto guardado (uma linha só) é separado em caput,
  parágrafos, incisos e alíneas (o "§ 1º" de uma referência no meio da frase
  não vira parágrafo), e cada um ganha as notas do Planalto — redação dada,
  incluído, revogado, renumerado, vide, vetado — com a lei e a data (o dia,
  quando a nota traz; senão, o ano).
- **A situação numa data**: antes de o código vigorar (tabela do início da
  vigência de cada código), ainda não existia, revogado, vetado, redação
  anterior e vigente; e **incerto** quando a lei só tem o ano e a data cai
  nesse ano. O resumo compara com hoje ("estava como hoje" ou quais
  dispositivos estavam diferentes).
- **Onde aparece**: o botão **Vigência** em cada artigo achado (Citar artigo),
  com a data escolhida e "o que mudou, na ordem"; a ferramenta pública
  `vigencia_do_artigo` no MCP (L7); a rota `GET /api/leis/vigencia`.

**O que não dá, e a tela diz:** o texto da redação anterior (o compilado do
Planalto quase nunca o guarda — o CDC não traz nenhum), e a vacatio legis
das leis que mudaram (a data que vale é a da lei). Não é o motor completo de
vigência: é o histórico pelas notas, com esses dois limites à vista.

**Medido:** `tests/test_l10_vigencia.py` 20 ok (texto montado e os códigos
de verdade: CDC 39, CC 1.368-C, CC 421, CC 206, CPC 1.015; MCP; o diálogo no
Edge).

# Segunda volta — as faltas e o que tinha ficado de fora (30/09/2026)

Pedido: "Vamos implantar tudo, inclusive o que ficou de fora de propósito,
como eu decidi". Entram as faltas de cada etapa (as linhas "Não feito"
acima) e os quatro itens que a primeira volta deixou de fora de propósito:
jurisprudência em massa, agente com autonomia sem confirmação, nuvem e
ferramenta do MCP que escreve. As regras da casa continuam: o que sai da
máquina vem desligado de fábrica e é dito na tela; o texto só promete o que
o código garante.

| Etapa | O quê | De onde | Estado | Teste |
| --- | --- | --- | --- | --- |
| N1 | O prazo pelo tipo de ato (sentença, acórdão, decisão, despacho, citação; cível, juizado, trabalho, penal; o prazo que o juiz fixou) | L2 | feito | `tests/test_n1_tipo_de_ato.py` |
| N2 | A publicação do DJEN ligada ao processo acompanhado: um aviso, um pedido de prazo | L2 | feito | `tests/test_n2_djen_processo.py` |
| N3 | A parte contrária sugerida pelos documentos do Serviço | L3 | feito | `tests/test_n3_parte_contraria.py` |
| N4 | O conflito de interesse guardado como pendência, com quem resolveu e como | L3 | feito | `tests/test_n4_conflitos.py` |
| N5 | Cláusula no estilo "1. DO OBJETO" reconhecida | L4 | feito | `tests/test_n5_clausulas.py` |
| N6 | A conversa chama as tarefas de vários passos | L4 | feito | `tests/test_n6_conversa_tarefas.py` |
| N7 | Súmulas e temas na resposta da conversa | L5 | feito | `tests/test_n7_temas_na_conversa.py` |
| N8 | Súmulas do STF, vinculantes e temas de repercussão geral no instalador | L5 | — | `tests/test_n8_stf.py` |
| N9 | MCP: escopo por cliente e ferramentas que escrevem | L7 | feito | `tests/test_n9_mcp_escreve.py` |
| N10 | Captura: corte das bordas e perspectiva endireitada | L8 | feito | `tests/test_n10_corte.py` |
| N11 | A posição na fila da resposta que volta do aparelho | D4 | — | `tests/test_n11_fila_aparelho.py` |
| N12 | Vigência: o texto da redação anterior e a vacatio legis | L10 | — | `tests/test_n12_vigencia.py` |
| N13 | Jurisprudência em massa: os acórdãos do STJ (dados abertos) no computador | fora | — | `tests/test_n13_jurisprudencia.py` |
| N14 | Agente com autonomia sem confirmação | fora | — | `tests/test_n14_autonomia.py` |
| N15 | Nuvem com a chave do escritório | fora | — | `tests/test_n15_nuvem.py` |
| N16 | Os três testes que dependiam desta máquina | testes | — | os próprios |

## N1 — o prazo pelo tipo de ato (30/09/2026)

- **O ato** (`src/tipo_de_ato.py`), por regra, sem modelo: no DataJud, a
  movimentação anterior do mesmo grau (Procedência, Improcedência, Extinção →
  sentença; Provimento e Não-Provimento no grau recursal → acórdão; Decisão,
  Concessão, Tutela → decisão; Mero expediente, Ato ordinatório → despacho;
  as juntadas de contestação, de recurso e de embargos); no DJEN, o texto
  inteiro ("julgo procedente", "ACÓRDÃO", "DEFIRO", "cite-se", "manifeste-se").
- **O ramo**: trabalho (tribunal TRT/TST ou o segmento 5 do número CNJ),
  penal (classe), juizado (classe, órgão ou grau JE/TR), cível no resto; e o
  cumprimento de sentença e a execução pela classe.
- **A tabela**: apelação 15 úteis; recurso inominado 10; recurso ordinário e
  de revista 8; apelação penal 5 corridos; REsp/RE 15; agravo de instrumento
  15 (com o aviso do rol do art. 1.015); agravo interno 15; embargos de
  declaração 5 (2 no penal); contestação 15; resposta à acusação 10; réplica
  e contrarrazões; pagamento voluntário e impugnação (arts. 523 e 525);
  manifestação 5 (art. 218, § 3º). Citação no juizado e no trabalho: sem
  prazo contado daqui (a defesa é na audiência), e o pedido não é criado.
- **O prazo que o juiz fixou** ("no prazo de 10 (dez) dias", "48 horas")
  vale num despacho ou numa decisão; numa sentença ou num acórdão fica como
  lembrete ("costuma ser o de cumprir, não o de recorrer").
- **No penal**, a conta é em dias corridos e o recesso do art. 220 do CPC
  não suspende (`prazos.calcular(recesso=False)`).
- **Em Aprovações**, o pedido diz o ato, a base, o porquê, a conta e as
  outras opções com o vencimento de cada uma, e o lembrete do prazo em dobro;
  a caixa do pedido deixa **escolher a opção** (a primeira vem marcada), e o
  sim anota a tarefa dela. No DJEN, "Criar prazo" vem com a sugestão e o
  porquê, e a pessoa troca à vontade.

**Não feito:** o PAULUS não sabe de que lado o escritório está (Fazenda,
MP e Defensoria em dobro: é lembrete), nem se a decisão está no rol do
agravo (é aviso); o prazo das leis especiais fora da tabela (mandado de
segurança, eleitoral, falência) cai nos 15 dias genéricos, dito.

**Medido:** `tests/test_n1_tipo_de_ato.py` 36 ok (as regras, a conta sem
recesso, o pedido com três opções escolhido pela tela no Edge, a sugestão
no "Criar prazo"); `test_l2_processos` e `test_prazos_publicacoes`
continuam passando.

## N2 — o DJEN junto do processo (30/09/2026)

- **A ligação** (`processos.ligar_publicacoes`, migração 031): a publicação
  do DJEN com o número de um processo cadastrado fica ligada a ele — depois
  de cada consulta ao DJEN, ao cadastrar um processo, ao "achar nos
  documentos" e no começo da volta do DataJud.
- **Um pedido por intimação**: a publicação é a intimação oficial, então o
  pedido de prazo do processo acompanhado sai dela (pela disponibilização e
  pelo texto inteiro, com a N1). A movimentação do DataJud da mesma intimação
  (até 5 dias depois da publicação) não pede de novo; e a publicação que
  chega depois de um pedido do DataJud se junta a ele. O sim anota a tarefa,
  e a publicação fica com ela, lida. Publicação com mais de 30 dias, de um
  processo recém-cadastrado, liga mas não vira pedido.
- **Um aviso por processo** na Central: "2 movimentações novas e 1
  publicação no DJEN", com a origem "DataJud + DJEN"; a publicação ligada
  não vira aviso à parte. "Marcar como vistas" deixa as publicações do
  processo lidas (e diz isso).
- **As telas**: o detalhe do processo ganha "Publicações no DJEN" (e o que
  houve com o prazo de cada uma); a publicação diz que está ligada e abre o
  processo, ou oferece "Acompanhar este processo".

**Não feito:** duas intimações diferentes do mesmo processo em menos de
5 dias viram um pedido só quando uma vem de cada fonte — é a janela que
junta a publicação ao registro dela no DataJud.

**Medido:** `tests/test_n2_djen_processo.py` 17 ok (o DJEN primeiro, o
DataJud primeiro, processo não cadastrado, publicação antiga, e as telas no
Edge); `test_l2_processos`, `test_prazos_publicacoes`, `test_t2_avisos` e
`test_n1_tipo_de_ato` continuam passando.

## N3 — a parte contrária pelos documentos (30/09/2026)

- **Onde procura** (`clientes.sugerir_partes`): nos documentos lidos do
  Serviço — os da pasta dele no Acervo e os ligados a ele — as partes que a
  leitura já achou e conferiu, com o papel de cada uma.
- **O lado**: onde o cliente do Serviço aparece entre as partes (pela regra
  da L3: sem acento, sem a forma jurídica), a parte do papel oposto é a
  sugestão — réu para autor, locador para locatário, contratado para
  contratante, comprador para vendedor, e os demais pares. O fiador do outro
  lado entra como interessado; o do cliente, o advogado e a testemunha não.
- **O que vem junto**: o documento e o porquê ("em “contrato.pdf”, a
  Construtora Alfa aparece como locatário e a Imobiliária Beta, como
  locador"), o CPF ou CNPJ válido escrito logo depois do nome (a
  qualificação), e os outros nomes da mesma entidade, que juntam numa
  sugestão só.
- **Onde o cliente não aparece**, não dá para saber o lado: a seção diz em
  quantos documentos. Serviço sem cliente diz por quê.
- **A pessoa confirma**: "Anotar" põe a parte (e confere o conflito, como
  antes); "Não é" guarda a dispensa no Serviço (migração 032), e a sugestão
  não volta, nem escrita de outro jeito.

**Não feito:** o PAULUS não tira sozinho a parte de documento cuja
leitura não achou partes (os que ainda não foram lidos pela camada de
inteligência entram quando forem).

**Medido:** `tests/test_n3_parte_contraria.py` 15 ok (papéis opostos,
fiador dos dois lados, outra grafia, documento ligado e da pasta, de outro
Serviço, sem lado, dispensa, e a seção no Edge em 1280 e 390 px);
`test_l3_clientes` continua passando.

## N4 — o conflito como pendência (30/09/2026)

- **Guardado** (tabela `conflitos`, migração 033): cada conflito achado — ao
  anotar a parte contrária, ao abrir o Serviço, ao gravar a ficha do cliente,
  na visão do cliente — fica guardado uma vez. A mesma situação vista dos dois
  lados (a Alfa é cliente e é parte contrária no Serviço da Maria) é uma
  pendência só.
- **Resolver** diz como: não é a mesma pessoa; os clientes autorizaram por
  escrito; muralha aplicada (a pessoa saiu de uma das equipes); o escritório
  recusou ou deixou um dos casos; outro motivo (com a frase, obrigatória). Fica
  quem resolveu (o nome de Meus dados, ou a pessoa de fora) e quando, com a
  anotação. Reabrir volta, anotado.
- **Onde aparece**: um aviso por conflito aberto na Central (tipo
  "Conflito", abre a caixa de resolver); a seção Partes do Serviço, com
  "Resolver"/"Ver"; a visão do cliente, com os abertos no alto e os resolvidos
  embaixo; Cadastros › **Conflitos**, que confere todos os Serviços em
  andamento na hora e lista abertos e resolvidos.
- **O que muda sozinho, dito**: a conferência geral fecha o conflito que
  deixou de existir (a parte saiu, a pessoa saiu da equipe), com "PAULUS"
  como quem resolveu; se ele volta, reabre ("voltou a aparecer"). Muralha dada
  por aplicada com a pessoa ainda nas duas equipes reabre ("a pessoa continua
  nas duas equipes").
- As rotas são da janela do escritório (a conferência cruza todos os
  clientes).

**Não feito:** a conferência geral roda quando alguém abre a lista, não
sozinha todo dia.

**Medido:** `tests/test_n4_conflitos.py` 21 ok (guardar sem duplicar, os dois
lados, a Central, resolver e reabrir, a muralha que reabre, o que some e
volta, e no Edge: Cadastros › Conflitos, resolver pela caixa, o aviso, 390
px); `test_l3_clientes`, `test_n3_parte_contraria`, `test_t2_avisos` e
`test_tela` continuam passando.

## N5 — a cláusula "1. DO OBJETO" (30/09/2026)

- **O estilo novo** (`redacao.RE_TITULO`, estilo "titulo"): o número, um
  separador (". ", " – ", ") ", ": ") e o título em maiúsculas, no começo do
  parágrafo — "1. DO OBJETO", "4 – DAS OBRIGAÇÕES DA LOCATÁRIA", "5) DA
  MULTA", "01 - DO OBJETO". O "1.1" das subcláusulas e a lista numerada em
  minúsculas não entram.
- **Com cuidado**: só vale quando o documento não tem nenhuma cláusula com a
  palavra "cláusula", quando há pelo menos duas, e quando a numeração anda (1,
  2, 3…) — um "1. DOS FATOS" solto ou um texto todo em maiúsculas não vira
  contrato.
- **Renumerar** troca só o número (o zero à esquerda de "01" fica) e leva a
  referência "cláusula 3" junto; a revisão contra o padrão (L4) alinha
  "CLÁUSULA 3ª – DAS OBRIGAÇÕES" com "4 – DAS OBRIGAÇÕES" pelo título.
- Os contratos reais do escritório usam "01 - DO ...": com a regra nova,
  `tests/test_redacao.py` passou a achar as 8 cláusulas deles, e o texto fica
  intacto ao renumerar.

**Medido:** `tests/test_n5_clausulas.py` 14 ok; `test_redacao` e
`test_l4_tarefas` continuam passando.

## N6 — a conversa chama as tarefas de vários passos (30/09/2026)

- **A regra** (`intencao.ler_passos`, sem modelo): "quais contratos vencem
  nos próximos 60 dias?", "contratos que terminam em 3 meses", "este mês",
  "este ano", "o próximo mês" (sem período: 90 dias, e o cartão diz); "revise o
  contrato X contra o padrão", "compare o X com o Padrão de locação" (o padrão
  pelo nome, ou o único do Acervo com "padrão", "modelo" ou "minuta" no nome;
  sem o contrato, o cartão diz o que falta). O plural ou o "quais" separa a
  lista da pergunta sobre um contrato — "qual o vencimento do contrato X?"
  continua indo para os documentos.
- **O catálogo** ganha `tarefa_de_varios_passos` (proposta "passos"), com
  confirmação, como as outras: a pergunta vira cartão (o período, o contrato,
  o padrão, "propor na Agenda", "o assistente explica"), a pessoa corrige, e o
  sim começa a tarefa da L4. O cartão acompanha os passos ali mesmo, com
  "Abrir o relatório", "Parar" e "Desfazer".
- Um agente só usa a ferramenta se a declarar no AGENTE.md (A2); de fora, a
  conversa diz que as tarefas de vários passos são da janela do escritório.

**Medido:** `tests/test_n6_conversa_tarefas.py` 22 ok (a regra, as duas
receitas pela conversa até o relatório, a recusa do contrato que não está
no Acervo, de fora, e no Edge: o cartão, o período corrigido, os passos e o
relatório); `test_ferramentas`, `test_intencao`, `test_c4_roteamento`,
`test_a1_agentes` e `test_l4_tarefas` continuam passando.

## N7 — temas e súmulas na resposta da conversa (30/09/2026)

- **Por regra** (`fundamentacao.relacionados`, sem modelo): depois de cada
  resposta, os artigos que a pergunta e a resposta citam ("art. 206, § 3º, do
  CC") e os que vieram como fonte de lei; para cada um, os temas do STJ
  ligados a ele (até 3), a posição da casa; e o tema e a súmula do STJ citados
  pelo número ("Tema 970", "Súmula 297 do STJ"). A súmula do STF e a
  vinculante ficam para a N8 (não viram STJ).
- **Embaixo da resposta**, fechado: "Na Biblioteca: 4 temas, 1 súmula,
  posição da casa · art. 206 do CC"; aberto, cada item com o porquê ("a tese
  cita o art. 206 do CC", "a conversa cita o Tema 970") e o aviso: "ligados por
  regra … não pelo modelo. Confira se se aplicam ao caso." A resposta não
  muda; o bloco é guardado com ela (`cobertura.relacionados`) e volta ao
  reabrir.
- **A chave** `conversa.relacionados`, ligada de fábrica (nada sai do
  computador), em Configurações › Conversa.

**Não feito:** a ligação é pelo artigo citado — tema relevante que não
cita o artigo não aparece, e tema que cita o artigo mas trata de outra
situação aparece (é para isso o "confira").

**Medido:** `tests/test_n7_temas_na_conversa.py` 16 ok (a regra, a
conversa com o modelo simulado, a chave, e o bloco no Edge em 1280 e 390
px); `test_l5_fundamentacao`, `test_c1_execucao`, `test_c2_pensando` e
`test_c3_painel` continuam passando.

## N9 — MCP: escopo por cliente e ferramentas que escrevem (30/09/2026)

- **Escopo por cliente** (`escopo.clientes`): os Serviços de cada cliente
  escolhido e os documentos ligados à ficha dele (pelo sha1 do vínculo). O
  documento de outro cliente não sai; "só no escritório" continua nunca
  saindo.
- **As que escrevem** (de propósito na L7, liberadas agora por decisão do
  dono), marcadas `escreve`: nenhuma apaga, move, envia nem edita o que
  existe.
  - `criar_rascunho`: documento novo no editor, com o título "(rascunho do
    assistente)" e a primeira linha dizendo quem criou;
  - `anotar_no_servico`: uma linha na trilha de um Serviço liberado,
    marcada com o nome da conexão (pede escopo);
  - `propor_tarefa` e `propor_compromisso`: pedidos em Aprovações (`mcp.tarefa`,
    `mcp.compromisso`) — a tarefa e o compromisso só existem depois do sim.
- **A conexão** com uma que escreve pede o segundo "entendi" ("esta conexão
  vai criar coisas no PAULUS"); a auditoria anota o que ela escreve; o
  diálogo da conexão nova ganha os clientes no escopo e as que escrevem
  num grupo à parte.

**Medido:** `tests/test_n9_mcp_escreve.py` 20 ok (o escopo por cliente, as
quatro que escrevem, os dois "entendi", a recusa fora do escopo e da
conexão, a auditoria, e o diálogo no Edge); `test_l7_mcp` (com a checagem
"só leitura" trocada por "as que escrevem estão marcadas") e
`test_umbrel_a_mcp` continuam passando.

## N10 — cortar a mesa e endireitar a folha (30/09/2026)

- **Achar a folha** (`src/corte_da_foto.py`, sem OpenCV e sem modelo: PIL e
  numpy): a foto pequena em cinza, o limiar de Otsu (folha clara, mesa
  escura), um fechamento que tapa as letras, a região clara ligada ao centro
  (o `floodfill` do PIL) e os quatro cantos pelos extremos de x+y e x−y.
  Serve para a folha girada até uns 40° e para a perspectiva de quem
  fotografa de pé. Cerca de 0,6 s por foto de 12 megapixels.
- **Com cuidado**: só corta quando a região é uma folha plausível — de 20% a
  97% da foto, cantos convexos, e a região preenchendo o quadrilátero.
  Senão a foto vai como veio, e a prévia diz por quê ("não vi borda entre a
  folha e o fundo", "a folha ocupa pouco da foto: aproxime").
- **Endireitar**: a transformação de perspectiva do PIL, na foto inteira; a
  folha sai retangular, pelo lado maior.
- **Na captura**: a conferência (L8) devolve também os cantos; a prévia
  desenha o contorno da folha e o botão "corta e endireita", ligado quando a
  folha foi achada, e a pessoa desliga em cada foto. O corte é refeito no
  servidor (a tela só diz sim ou não), e a resposta diz quantas páginas
  foram endireitadas.

**Não feito:** ajustar os cantos à mão na prévia; a folha sobre fundo
claro (mesa branca) não é achada — vai como veio, dito. O limiar foi medido
com fotos montadas; fotos de celular de verdade ficam para o teste do dono
(junto do da L8).

**Medido:** `tests/test_n10_corte.py` 16 ok (cantos a menos de 1,5% na
folha torta, em perspectiva e reta; os três casos de não cortar; o OCR do
Windows lê mais palavras certas na folha endireitada que na foto crua; a
captura com e sem corte; e a prévia no Edge); `test_l8_captura` e
`test_umbrel_e_captura` continuam passando.
