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
| L3 | Visão por cliente e muralha ética: a mesma entidade com nomes diferentes, parte contrária, "tudo sobre o cliente", aviso de conflito | pendente | `tests/test_l3_clientes.py` |
| L4 | Tarefas de vários passos com ponto de restauração: contratos vencendo em N dias, revisar contrato contra o padrão da casa | pendente | `tests/test_l4_tarefas.py` |
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
