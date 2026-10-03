# PROGRESSO — Profundidade jurídica e conversa modular

Pedido do dono em 03/10/2026, de madrugada ("pretendo ir dormir; ao acordar,
quero pronto, commitado e pushado"): o assistente entregava a solução mais
básica e começava a produzir antes de entender o pedido. Duas camadas:

1. **Entender antes de trabalhar** — a entrevista contextual
   (`src/entrevista.py`): o formulário nasce do pedido.
2. **Trabalhar com a profundidade escolhida** — Estagiário → Bacharel →
   Advogado → Juiz → Ministro (`src/profundidade.py`, `src/elaboracao.py`).

## O que foi feito

| Peça | Onde | O quê |
| --- | --- | --- |
| Os níveis | `src/profundidade.py` | 5 receitas: teto de perguntas e de rodadas, postura da entrevista, etapas da elaboração, teto de tokens, quanto do anexo entra, consumo aproximado. Modelo: o de Configurações › Modelos, ou um por nível em `profundidade.modelos`. |
| É pedido de trabalho? | `entrevista.e_trabalho` | Por regra, sem modelo: elaborar/redigir/fazer/revisar + uma peça (contrato, petição, contestação, recurso, parecer, notificação, procuração...). "Explique o art. X", "qual o valor do contrato?", "resuma..." seguem o caminho de sempre, sem entrevista. 22 frases no teste. |
| A entrevista | `entrevista.avaliar` | Uma chamada à nuvem decide executar ou perguntar, e monta as perguntas DESTE pedido: tipo (escolha, múltipla, texto, data, valor, parte, documento, sim/não), opções, sugestão e o porquê (o que muda no texto). Rodadas: só o que as respostas fizeram surgir. |
| A conferência | `entrevista.conferir` | Regra, não instrução: pergunta sem porquê, de qualificação (nome, CPF, estado civil, "quem é o arrendatário?") ou vaga ("há cláusulas adicionais?") não passa; "Outro"/"Não sei" saem das opções; teto e rodadas do nível; Estagiário só pergunta o que IMPEDE o trabalho, Bacharel o que impede ou tem impacto alto, do Advogado para cima impacto alto ou médio. |
| O raciocínio | `ANALISE_LIVRE` | Juiz e Ministro escrevem uma análise em texto livre antes do JSON (regime jurídico, escolhas típicas, premissas a questionar; Ministro também divergências e litígios típicos). Advogado raciocina dentro do JSON (campo `analise`). A análise vai junto para a elaboração. |
| A elaboração | `src/elaboracao.py` | Estagiário e Bacharel redigem direto; Advogado planeja (com as exigências e VEDAÇÕES legais) e redige; Juiz planeja com alternativas, redige, revisa criticamente e reescreve o que a revisão apontar (alta/média); Ministro começa por uma análise de riscos. Uma máscara para o pedido inteiro ([CPF 1] é o mesmo em todas as etapas). Extensão esperada por nível. Sem markdown. Notas para o advogado no fim. |
| A rota | `src/api.py` (`_seguir_entrevista`, `_responder_trabalho`) | Pedido de trabalho com a nuvem → entrevista ou execução, como execução desacoplada (C1). Respostas pelo cartão, ou texto livre com a entrevista aberta (outra pergunta segue o caminho de sempre e as perguntas ficam para depois). "Continuar com o que temos" e "Decida por mim" executam direto. |
| A resposta comum | `nuvem.Envio` | Pergunta sobre documento ou lei, na nuvem, leva a instrução do nível e o teto dele (1.200 a 5.000 tokens). |
| A tela | `js/92-entrevista.js`, `css/54-profundidade.css` | A pílula do nível na caixa da pergunta (só com a nuvem ligada), com o menu dos 5 níveis, o técnico discreto e o consumo; "Entender antes de trabalhar" liga/desliga. O cartão do módulo de perguntas (o porquê embaixo de cada pergunta; "Não sei", "Decida por mim", "Depois" em cada uma; Enviar, Continuar com o que temos, Decida por mim, Quero explicar com minhas palavras, Responder depois). O cartão "trabalho pronto" com as etapas, o que a revisão apontou, as citações a conferir e "Abrir no editor". O nível na assinatura e no painel "Como respondi". |
| Consumo | `src/consumo.py`, `js/91-plano-consumo.js` | Plano e consumo ganhou a seção "Profundidade": tokens e pedidos do ciclo por nível, e o "~N× da franquia" de cada um. Cada envio registra `etapa` e `profundidade`. |
| Worker | `wrangler.jsonc` | `IA_MAX_SAIDA` 4.000 → 8.000 (o Ministro escreve até 8 mil tokens). |

## Medido com a nuvem de verdade (Worker, Llama 3.3 70B), 03/10

- **Entrevista**: 6 pedidos (arrendamento rural em 3 níveis, contestação,
  notificação por denúncia vazia, procuração simples). Com a primeira
  instrução, o modelo pedia nome das partes e estado civil e escrevia
  "porquês" genéricos; a conferência por regra e a instrução nova tiraram
  isso. Ficou: "O escritório representa o arrendador ou o arrendatário?",
  "Qual o tipo de exploração: agrícola, pecuária ou mista?", "O contrato é
  residencial ou comercial?" (denúncia vazia), "O divórcio é consensual ou
  litigioso?". Tempo: 30–55 s por rodada no Advogado; 60–110 s com a análise
  livre (por isso ela ficou só no Juiz e no Ministro).
- **Qwen 2.5 72B** (a outra opção do Worker): parecido; um JSON quebrou ao
  passar de 1.800 tokens (o teto subiu para 2.200/3.000).
- **Elaboração** do arrendamento já definido: Advogado, 130 s, 8 cláusulas
  (antes da extensão esperada); Juiz, 248 s, plano + redação + revisão +
  reescrita, com benfeitorias indenizáveis e garantia definidas. A reescrita
  inventou "20 sacas" quando a revisão pediu "o valor exato" — agora dado não
  informado não é defeito (fica [●]), por instrução e por regra
  (`RE_DADO_FALTANTE`). Medido de novo: Juiz em 197 s, sem número inventado.
- **Extensão**: o Llama 70B escreve curto (600–700 palavras num contrato,
  mesmo com a extensão esperada e "todas as seções do plano" na instrução).
  O Qwen 72B, no mesmo pedido, escreveu 814 palavras e mais completo
  (qualificação, assinaturas, testemunhas), mas em markdown e com marcadores
  inventados ("[CPF 3]") — a regra limpa (`limpar_texto`): sem "####"/"**", e
  marcador que a máscara não criou vira [●]. O modelo padrão continua o de
  Configurações › Modelos; `profundidade.modelos` escolhe outro por nível.

## O limite que ficou (e a alavanca)

O Llama 3.3 70B erra direito material que um advogado pegaria: no
arrendamento, não lembrou que o Decreto 59.566/66 veda fixar o preço em
quantidade de produto, e citou artigos do Estatuto da Terra com o número
errado. A conferência automática de artigos só cobre os códigos da
Biblioteca (o Estatuto da Terra não está lá) — o cartão "trabalho pronto"
diz isso. **A alavanca é o modelo**: `profundidade.modelos` já aceita um
modelo por nível (por exemplo, um modelo maior no Juiz e no Ministro), mas o
Worker só aceita os de `IA_MODELOS` (hoje Llama 3.3 70B e Qwen 2.5 72B), e o
preço por token do DeepInfra muda de modelo para modelo. É decisão do dono.

## Fora do escopo desta volta

- Sem a nuvem, o modelo deste computador (3B) não faz entrevista nem etapas:
  a pílula do nível nem aparece, e o pedido segue o caminho de sempre.
- Com "pedir o sim a cada envio" ligado, o trabalho em etapas não roda (seriam
  várias aprovações por pedido): segue o caminho de sempre.
- O tipo "documento" do módulo oferece os nomes do Acervo para escolher, mas
  não anexa arquivo novo pelo cartão (a caixa da pergunta anexa).
- A página de assinatura no site não mostra o consumo por nível; está na tela
  Plano e consumo do programa.

## Testes

- `tests/test_profundidade.py` — níveis, regra do pedido de trabalho,
  conferência, o fluxo inteiro pela rota com a nuvem de mentira (todas as
  etapas de cada nível, máscara, editor, texto livre, pedir a cada envio).
- `tests/test_profundidade_tela.py` — no Edge: pílula, menu, cartão,
  responder, trabalho pronto, reabrir a conversa, celular 390 px.
- Regressão rodada: c1–c4, a2, f1, consumo (e tela), config_conversa,
  navegacao, n6, i4, intencao, r9, email/fichas/lancamento/financeiro na
  conversa, m2, habilidades, v_nuvem, n15, bateria_nuvem, r3, worker
  (`node worker/teste-ia.mjs`).
