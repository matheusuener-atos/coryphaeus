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

## Os planos de 03/10/2026: modelo, recursos, semana e anual

O dono fechou três planos que diferem em IA e em recursos, não só em tokens:

| | Advogado | Escritório | Escritório Plus |
|---|---|---|---|
| Mensal / anual | R$ 449 / R$ 3.990 | R$ 1.290 / R$ 11.490 | R$ 3.490 / R$ 30.990 |
| Modelo | Llama 3.3 70B (DeepInfra) | Mistral Large 3 (Mistral AI) | Claude Sonnet 5.5; no Ministro, Claude Opus 5.5 (Anthropic) |
| Créditos por mês | 30 mi | 60 mi | 40 mi (o Opus gasta 2 por token) |
| Pessoas | 1 | 5 | 15 |
| Recarga | 10 mi por R$ 50 | 10 mi por R$ 120 | 5 mi por R$ 300 |

**Feito:**
- **Worker** (`worker/ia.js`): `PLANOS_DE_FABRICA` com valor anual, pessoas,
  modelo por nível, recarga e recursos; `MODELOS` com provedor, peso em
  créditos e preço (o painel calcula o custo por modelo). O portão escolhe o
  modelo pelo plano e pelo `paulus_nivel` (o PAULUS antigo, que pede o Llama,
  recebe o do plano) e recusa nível acima do plano (403). Ponte para a
  Mistral (formato OpenAI) e para o Claude (Messages API traduzida para o
  formato OpenAI, com `fallbacks: "default"`; Sonnet sem pensar,
  `between_tools`; Opus com esforço alto e 4.000 tokens de folga). Cota da
  semana (mês × 7/30, não acumula) e adiantamento da semana seguinte uma vez
  por mês, nunca nos 7 primeiros dias (`POST /api/ia/adiantar`). Anual pelo
  Checkout Pro em até 12× (`/checkout/preferences`, referência
  `ia-anual-<conta>-<plano>-<n>`), confirmado pelo aviso `payment` ou pela
  consulta; cada mês abre o seu ciclo; o mensal antigo é cancelado; estorno
  acaba o plano; não renova sozinho (renova nos últimos 45 dias). 121 testes
  em `worker/teste-ia.mjs`.
- **Painel admin**: valor anual nos planos, custo por modelo.
- **App** (`src/recursos_do_plano.py`, `tests/test_recursos_do_plano.py`): o
  plano e os recursos guardados em prefs `plano`; travas na profundidade,
  equipe (contas e colaborador de fora), agentes, agente sozinho e passos,
  NFS-e (teto do mês só em produção, recorrência), DataJud, gravações,
  sugestões ao vivo, horas, muralha, jurisprudência STJ, Word, MCP, contas de
  e-mail e limite por pessoa. Sem cobrança (terminal, testes), tudo liberado.
  Tela Plano e consumo: semana, adiantar, comparação dos planos com mensal e
  anual. Termo da nuvem na versão 2026-10-03 (os três provedores).
- **Site**: cadastro com mensal/anual e o que cada plano tem; termos e
  política PT/EN (provedores, anual, semana, arrependimento de 7 dias).

**Falta do dono antes do push** (o push na main publica o Worker):
- `npx wrangler secret put MISTRAL_KEY` e `npx wrangler secret put ANTHROPIC_KEY`
  (sem elas, Escritório e Plus respondem 503);
- no Mercado Pago, ligar o tópico **Pagamentos** no webhook (o anual chega
  como `payment`); conferir se a conta não oferece parcelamento sem juros
  (o combinado é o juro por conta de quem parcela);
- rodar a bateria com `mistral-large-latest` e com o Claude antes de anunciar;
- o reembolso dos 7 dias é feito à mão no Mercado Pago (o estorno chega pelo
  aviso e acaba o plano).

**Não feito:** a IA explicando a movimentação do DataJud e a página do
cliente (não aparecem nas telas nem no site); o desconto do uso
de IA no reembolso (CDC, art. 49: devolução integral; a semana sem
adiantamento limita o risco).

### O pagamento embutido (03/10/2026)

O cartão deixou de ir para a página do Mercado Pago: ele é digitado em
`paulus.ia.br/cadastro/pagamento/`, no bloco de cartão do Mercado Pago (Card
Payment Brick, `site/assets/pagamento.js`). Os campos do cartão são quadros do
Mercado Pago (`secure-fields.mercadopago.com`); a página recebe só o token.

- **Um lugar só cobra:** `pagar` em `worker/ia.js` (`POST /api/ia/site/pagar`).
  Mensal: `/preapproval` com `card_token_id` e `status: authorized` (o plano vale
  na hora). Anual: `/v1/payments` em até 12 parcelas, com a `X-Idempotency-Key`
  da página (nova depois de uma recusa). O valor é o de `ofertaDoPagamento`,
  nunca o do bloco. Recusas com o motivo em português (`RECUSAS`).
- **O PAULUS instalado** não cria mais cobrança: `/api/ia/assinar` devolve o
  link da página de pagamento, que se abre no navegador com a mesma conta Google.
- **Chave pública:** `MP_PUBLIC_KEY` no `wrangler.jsonc` (a da aba Produção do
  app "PAULUS Apoio"), lida pela página em `GET /api/ia/mp-config`, sem cache.
- **CSP** em `/cadastro/*` (`CSP_CADASTRO` em `worker/index.js`; `/cadastro`
  entrou no `run_worker_first`): só scripts do site, do Mercado Pago e do Google.
  Conferido no Edge com a chave de teste: o bloco monta sob a CSP; fica bloqueado
  só um script inline de telemetria do SDK (`sendCookies`), de propósito.
- **Validadores do plugin do Mercado Pago** (`validate-bricks-integration`,
  `validate-subscriptions-integration`): não passam, por convenções de app
  Node/Express (rotas `/api/mp-config` e `/api/subscriptions/:id`,
  `process.env.PORT`, a URL da API literal no `fetch`); o equivalente de cada
  um existe aqui com outro nome.

**Falta do dono:** testar um pagamento com usuário e cartão de teste do Mercado
Pago (`/mp-integrate test-setup`) e rodar `/mp-review` antes de produção; ligar
a verificação em duas etapas no GitHub e na Cloudflare (quem publica o site
publica a página do cartão).

**Depois (03/10):** o formulário virou CardForm (campos do site; número, validade
e código seguem em quadros do Mercado Pago), com a miniatura da bandeira, as
parcelas cortadas em 12 e o total com juros abaixo delas. **Plano B:** se o
formulário não carrega (bloqueador, rede, 15 s sem os quadros), aparece "Pagar na
página do Mercado Pago": `POST /api/ia/site/pagar-fora` cria a assinatura pendente
(mensal) ou a preferência do Checkout Pro (anual), com o valor da mesma oferta; a
volta é `/cadastro/?voltou=1`, que confere a situação. Agora há dois lugares que
criam cobrança (`pagar` e `pagarFora`), os dois a partir de `ofertaDoPagamento`.

## Pix na assinatura (03/10)

A página de pagamento tem **Pix | Cartão**, com o Pix primeiro e escolhido de saída.

- **Mês no Pix (avulso):** um pagamento (`/v1/payments`, `payment_method_id: pix`, referência `ia-mes-<conta>-<plano>-<x>`) que vale um mês e acaba sozinho, sem renovação. Na conta fica `periodo: "avulso"`, com `pago_ate`, como um "anual de 1 mês". O mês seguinte pode ser pago antes e começa no fim do que já está pago.
- **Ano no Pix:** o mesmo anual de antes (`ia-anual-...`), só que à vista no Pix.
- **Confirmação:**
  - o aviso `payment` do Mercado Pago, pelo mesmo `confirmarAnual`;
  - a consulta do pendente;
  - a própria página, que pergunta a cada 4 s em `/api/ia/site/pix` (confere se o pagamento é da conta) e de novo ao voltar para a aba.
- **O QR** vence em 30 min (`date_of_expiration` no fuso -03:00). Vencido, a página pede para gerar outro.
- **O que cada meio permite** vem da oferta (`meios`): com a assinatura mensal no cartão ativa, o mês no Pix fica fechado (passar ao anual pode); com o mês no Pix pago, a assinatura no cartão espera ele vencer.
- **A regra dos 45 dias** de renovação usa a hora do medidor (`agora` no resumo), e não a do Worker.
- **O cupom** é gasto ao gerar o Pix, como no Checkout Pro do plano B.
