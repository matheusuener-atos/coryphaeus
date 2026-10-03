# Plano da nuvem vendida — inferência no DeepInfra + cobrança (01/10/2026)

Pedido do dono: implementar o pacote `paulus-docs-deepinfra` (estratégia de
inferência, precificação e roteiro de 4 semanas). O PAULUS continua no
computador do escritório; só a chamada ao modelo sai, e a nuvem passa a ser o
produto vendido (o modelo local fica como reserva técnica).

Decisões do dono nesta conversa (01/10/2026):

- **A cota é em tokens**, não em documentos ("não quero atrelar a documentos,
  mas a tokens mesmo"). A tela mostra tokens.
- **Consentimento uma vez, pelo titular**, com o aviso de LGPD e de
  transferência; depois, cada resposta diz que foi escrita na nuvem. O sim a
  cada envio (N15) vira opção.
- **Alcance:** conversa, resumos e redação. Tudo o que vem do e-mail, o juiz
  de uma letra e a leitura do Acervo ficam no computador.

Decisões técnicas (minhas, explicadas):

- **A chave do DeepInfra fica no Worker de paulus.ia.br**, nunca no PAULUS
  instalado: chave no instalador seria de qualquer um, e a cota num arquivo
  local não bloqueia nada. O Worker é o portão: confere a conta, reserva os
  tokens, chama o DeepInfra e desconta o gasto real.
- **O medidor é um Durable Object por conta** (`ContaIA`, SQLite, cabe no
  plano grátis): uma conta, uma fila — duas perguntas ao mesmo tempo não
  passam as duas pelo último saldo, como passariam pelo KV.
- **Os números ficam em variáveis do Worker** (`wrangler.jsonc`), mudáveis sem
  código. Provisórios, até o dono decidir: plano R$ 300 com 30 milhões de
  tokens por ciclo; recarga R$ 50 com 10 milhões (não vence na renovação).
  Pior caso de custo no DeepInfra (tudo saída, US$ 0,40/M): ~US$ 12 por plano.
- **O DeepInfra também entra como provedor com chave própria** (o mesmo da
  N15), para a bateria da semana 1 rodar antes do portão estar no ar.

| Etapa | O quê | Estado | Teste |
| --- | --- | --- | --- |
| V1 | DeepInfra como provedor (chave própria); bateria local × nuvem e comparação lado a lado | feito (falta a rodada com a chave) | `tests/test_v_nuvem.py`, `tools/demo/roteiro.py --nuvem` |
| V2 | Worker: conta da nuvem (Google), segredo da instalação, medidor (reserva, desconto, bloqueio, teto por pedido e por minuto) e o portão `/api/ia/v1/chat/completions` | feito | `node worker/teste-ia.mjs` |
| V3 | Worker: assinatura R$ 300/mês ligada à cota, renovação pela cobrança paga, recarga por Pix; nada disso conta como apoio | feito | `node worker/teste-ia.mjs` |
| V4 | App: o provedor "PAULUS (nuvem)" — ativar com o Google, chamar o portão, a cota acabou volta ao computador com aviso | feito | `tests/test_v_nuvem.py` |
| V5 | App: consentimento do titular (termo com versão, guardado aqui e no Worker); sem o sim a cada envio; de fora também | feito | `tests/test_v_nuvem.py`, `tests/test_n15_nuvem.py` |
| V6 | App: resumos e redação pela nuvem (chave por funcionalidade), cada chamada no registro; e-mail sempre aqui | feito | `tests/test_v_nuvem.py` |
| V7 | Tela de consumo: tokens restantes, usados, renovação, recarga e assinatura; sem gráfico | feito | `tests/test_v_nuvem.py` (Edge) |
| V8 | Site e política: o operador (DeepInfra), a transferência, o consentimento, a cobrança | feito | conferência frase a frase |

O que só o dono faz: criar a conta no DeepInfra e pôr crédito; a chave como
segredo do Worker (`npx wrangler secret put DEEPINFRA_KEY`); `IA_ATIVA` em
`"1"`; rodar a bateria com a chave; decidir os números; push do site e do
Worker; o contrato do endpoint dedicado quando houver cliente pagante.

## O que ficou feito e medido (01/10/2026)

- **Worker** (`worker/ia.js`, `node worker/teste-ia.mjs`, 54 ok): ativar pela
  conta Google; segredo `pia_<conta>_<hex>` (o medidor guarda só o SHA-256,
  até 3 instalações); o sim do titular exigido no servidor; reserva antes de
  chamar (entrada estimada por 3 caracteres/token + saída pedida, cortada em
  `IA_MAX_SAIDA`), liquidação pelo `usage` do DeepInfra (sem ele, a estimativa
  + um token por pedaço; o "parar" no meio também liquida); erro do provedor
  devolve a reserva; teto de entrada e de pedidos por minuto; 402 com o motivo
  (`cota`, `sem_plano`), 403 (`consentimento`). Assinatura R$ 300 abre o ciclo;
  a primeira cobrança só confirma, as seguintes abrem o ciclo novo (aviso
  repetido não duplica); cancelada, o ciclo pago vale até o fim; recarga por
  Pix credita uma vez só, gasta depois do ciclo e não vence. Nada da nuvem
  conta como apoio (nem pela rota do Pix do Apoiar). Cortesia por SHA-256 do
  e-mail (`IA_CORTESIA`). `wrangler deploy --dry-run` aceitou o Durable Object.
- **App** (`tests/test_v_nuvem.py`, 58 ok com o Edge; `tests/test_n15_nuvem.py`
  41 ok): os provedores PAULUS (nuvem), DeepInfra, Anthropic, OpenAI; o termo
  com versão, o sim por provedor (guardado aqui, em `nuvem/consentimentos.jsonl`,
  e no Worker); sem pedir a cada envio depois do sim (opção de pedir); de fora
  com o sim; resumos (serviços, gravações) e redação (editor, comentário,
  fórmula, comparar com o padrão) pelo `ClienteNuvem`, com as mesmas
  exclusões (pasta, serviço e cliente só no escritório, e-mail, Drive);
  reescrita de e-mail e parecer do Financeiro marcados `local=True`; nuvem
  falhou ou cota acabou: o modelo local escreve e a resposta diz por quê. A
  tela de consumo em Configurações › Modelos (tokens restantes, usados, hoje,
  recarga, renovação; assinar, recarregar por Pix com o QR e a conferência
  sozinha, cancelar, desligar a instalação), sem gráfico.
- **Bateria**: `tools/demo/roteiro.py --tudo --nuvem deepinfra:meta-llama/Llama-3.3-70B-Instruct`
  (chave em `DEEPINFRA_API_KEY`) e `tools/demo/comparar.py` lado a lado. Não
  rodada: falta a chave.
- **Site**: política PT/EN (seção Nuvem reescrita: os dois jeitos, o
  DeepInfra pela política publicada dele, a transferência, o que nunca vai, o
  que o site guarda da conta), termos PT/EN (item 7 novo, Nuvem paga; os
  seguintes renumerados) e as frases da página inicial que ficariam falsas.

**Não feito:**
- a rodada real da bateria e a escolha do modelo (semana 1) - precisa da chave;
- o endpoint dedicado (fase 2) e o contrato de sigilo;
- apagar a conta da nuvem pelo programa (hoje, por contato@paulus.ia.br, à mão);
- recarga no cartão (só Pix: "um clique" que abre o QR);
- o reposicionamento comercial da página inicial (nuvem como o produto
  vendido, "preço de pioneiro"): é decisão do dono, e o site só pode dizer
  isso quando `IA_ATIVA` estiver em "1";
- medir o tempo economizado por escritório.
