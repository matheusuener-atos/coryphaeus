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
| L5 | A Biblioteca ajudando a escrever: fundamentação sugerida no editor, súmulas e temas repetitivos, posição da casa por artigo | pendente | `tests/test_l5_fundamentacao.py` |
| L6 | Modelo por máquina: perfis por faixa de hardware, com GPU NVIDIA, AMD e Intel | pendente | `tests/test_l6_perfis.py` |
| L7 | Servidor MCP além das leis: Acervo só leitura, permissão e escopo por conexão | pendente | `tests/test_l7_mcp.py` |
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
