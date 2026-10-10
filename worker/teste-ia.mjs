// Teste da nuvem do PAULUS no Worker (worker/ia.js), sem rede:
//   node worker/teste-ia.mjs
// O DeepInfra e o Mercado Pago sao de mentira; o Durable Object roda aqui,
// com a mesma classe, sobre um Map.
import { createHmac } from "node:crypto";
import worker from "./index.js";
import { atenderIA, ContaIA, medidor, usoDoFim } from "./ia.js";

let falhas = 0;
const checar = (ok, descricao, detalhe) => {
  console.log((ok ? "  ok   " : "  FALHA ") + descricao + (ok || detalhe === undefined ? "" : " -> " + JSON.stringify(detalhe)));
  if (!ok) falhas++;
};

// ------------------------------------------------ o Durable Object aqui
let relogio = Date.parse("2026-10-01T12:00:00Z");
const objetos = new Map();
function objeto(nome) {
  if (!objetos.has(nome)) {
    const dados = new Map();
    const o = new ContaIA({ storage: { get: async (k) => structuredClone(dados.get(k)), put: async (k, v) => { dados.set(k, structuredClone(v)); } } }, {});
    o.agora = () => relogio;
    objetos.set(nome, { o, dados });
  }
  return objetos.get(nome);
}
const CONTAS_IA = {
  idFromName: (n) => n,
  get: (n) => ({ fetch: (url, init) => objeto(n).o.fetch(new Request(url, init)) }),
};

// ------------------------------------------------ DeepInfra e Mercado Pago
const deepinfra = [];
let respostaDoModelo = "padrao";
function sse(pedacos, uso) {
  const linhas = pedacos.map((t) => "data: " + JSON.stringify({ choices: [{ delta: { content: t } }] }) + "\n\n");
  if (uso) linhas.push("data: " + JSON.stringify({ choices: [], usage: uso }) + "\n\n");
  linhas.push("data: [DONE]\n\n");
  return new ReadableStream({
    start(c) {
      for (const l of linhas) c.enqueue(new TextEncoder().encode(l));
      c.close();
    },
  });
}
const claude = [];
const mistral = [];
let respostaDoClaude = "padrao";
const mpPagamentos = new Map();
const mpPedidos = [];
const mpOrders = new Map();
const mpPreapprovals = new Map();
globalThis.fetch = async (url, init = {}) => {
  const u = String(url);
  if (u.startsWith("https://api.deepinfra.com/")) {
    const corpo = JSON.parse(init.body);
    deepinfra.push({ corpo, auth: init.headers.Authorization });
    if (respostaDoModelo === "erro") return new Response(JSON.stringify({ error: { message: "model overloaded" } }), { status: 503 });
    if (!corpo.stream) {
      return new Response(JSON.stringify({ choices: [{ message: { content: '{"ok":true}' } }], usage: { prompt_tokens: 120, completion_tokens: 30 } }), { status: 200 });
    }
    const uso = respostaDoModelo === "sem-uso" ? null : { prompt_tokens: 1000, completion_tokens: 200 };
    return new Response(sse(["O contrato ", "vence em ", "10/10."], uso), { status: 200, headers: { "content-type": "text/event-stream" } });
  }
  if (u.startsWith("https://api.anthropic.com/")) {
    const corpo = JSON.parse(init.body);
    claude.push({ corpo, headers: init.headers });
    if (respostaDoClaude === "recusa" && !corpo.stream) {
      return new Response(JSON.stringify({ id: "msg_r", model: corpo.model, content: [], stop_reason: "refusal", usage: { input_tokens: 50, output_tokens: 0 } }), { status: 200 });
    }
    if (!corpo.stream) {
      return new Response(JSON.stringify({ id: "msg_1", model: corpo.model, content: [{ type: "thinking", thinking: "" }, { type: "text", text: '{"ok":true}' }],
        stop_reason: "end_turn", usage: { input_tokens: 100, output_tokens: 20 } }), { status: 200 });
    }
    const ev = (o) => "event: " + o.type + "\ndata: " + JSON.stringify(o) + "\n\n";
    const partes = [
      ev({ type: "message_start", message: { id: "msg_2", model: corpo.model, usage: { input_tokens: 900, cache_read_input_tokens: 100, output_tokens: 1 } } }),
      ev({ type: "content_block_start", index: 0, content_block: { type: "text", text: "" } }),
      ev({ type: "content_block_delta", index: 0, delta: { type: "text_delta", text: "Prazo de " } }),
      ev({ type: "content_block_delta", index: 0, delta: { type: "text_delta", text: "15 dias." } }),
      ev({ type: "content_block_stop", index: 0 }),
      ev({ type: "message_delta", delta: { stop_reason: respostaDoClaude === "recusa" ? "refusal" : "end_turn" }, usage: { output_tokens: 50 } }),
      ev({ type: "message_stop" }),
    ].join("");
    // Partido no meio de uma linha, como a rede entrega.
    const bytes = new TextEncoder().encode(partes);
    return new Response(new ReadableStream({ start(c) { c.enqueue(bytes.slice(0, 137)); c.enqueue(bytes.slice(137)); c.close(); } }),
      { status: 200, headers: { "content-type": "text/event-stream" } });
  }
  if (u.startsWith("https://api.mistral.ai/")) {
    const corpo = JSON.parse(init.body);
    mistral.push({ corpo, auth: init.headers.Authorization });
    return new Response(sse(["Mistral ", "responde."], { prompt_tokens: 500, completion_tokens: 100 }), { status: 200, headers: { "content-type": "text/event-stream" } });
  }
  if (u.startsWith("https://api.mercadopago.com")) {
    const caminho = u.slice("https://api.mercadopago.com".length);
    const metodo = init.method || "GET";
    const corpo = init.body ? JSON.parse(init.body) : null;
    mpPedidos.push({ caminho, metodo, corpo, headers: init.headers || {} });
    if (caminho === "/preapproval" && metodo === "POST") {
      // Com o token do cartao, a assinatura ja nasce autorizada; o token "tokrecusa..." e recusado.
      if (String(corpo.card_token_id || "").startsWith("tokrecusa")) return new Response(JSON.stringify({ message: "Card token invalid" }), { status: 400 });
      const id = "pre" + mpPreapprovals.size + "abc";
      const status = corpo.card_token_id ? "authorized" : "pending";
      mpPreapprovals.set(id, { id, status, external_reference: corpo.external_reference, auto_recurring: corpo.auto_recurring });
      return new Response(JSON.stringify({ id, status, ...(status === "pending" ? { init_point: "https://www.mercadopago.com.br/subscriptions/checkout?preapproval_id=" + id } : {}) }), { status: 201 });
    }
    if (caminho === "/checkout/preferences" && metodo === "POST") {
      const id = "PREF" + mpPedidos.length;
      return new Response(JSON.stringify({ id, init_point: "https://www.mercadopago.com.br/checkout/v1/redirect?pref_id=" + id }), { status: 201 });
    }
    if (caminho === "/v1/payments" && metodo === "POST") {
      // O pagamento do cartao: "tokrecusa..." sem limite, "tokanalise..." em analise, o resto aprovado.
      const id = String(7000 + mpPagamentos.size);
      const t = String(corpo.token || "");
      const pix = corpo.payment_method_id === "pix";
      const status = pix ? "pending" : t.startsWith("tokrecusa") ? "rejected" : t.startsWith("tokanalise") ? "in_process" : "approved";
      const pg = { id: Number(id), status, status_detail: status === "rejected" ? "cc_rejected_insufficient_amount" : status === "approved" ? "accredited" : "pending_contingency",
        external_reference: corpo.external_reference, transaction_amount: corpo.transaction_amount, date_approved: status === "approved" ? new Date(relogio).toISOString() : null,
        payment_method_id: corpo.payment_method_id,
        ...(pix ? { point_of_interaction: { transaction_data: { qr_code: "00020126pix" + id, qr_code_base64: "iVBORpix", ticket_url: "https://www.mercadopago.com.br/payments/" + id + "/ticket" } } } : {}) };
      mpPagamentos.set(id, pg);
      return new Response(JSON.stringify(pg), { status: 201 });
    }
    let m = caminho.match(/^\/preapproval\/(.+)$/);
    if (m) {
      const p = mpPreapprovals.get(decodeURIComponent(m[1]));
      if (!p) return new Response("{}", { status: 404 });
      if (metodo === "PUT") Object.assign(p, corpo);
      return new Response(JSON.stringify(p), { status: 200 });
    }
    if (caminho === "/v1/orders" && metodo === "POST") {
      const id = "ORD" + (mpOrders.size + 1) + "XYZ";
      mpOrders.set(id, { id, status: "action_required", external_reference: corpo.external_reference, total_amount: corpo.total_amount });
      return new Response(JSON.stringify({ id, status: "action_required",
        transactions: { payments: [{ payment_method: { qr_code: "000201pix", qr_code_base64: "iVBOR" } }] } }), { status: 201 });
    }
    m = caminho.match(/^\/v1\/orders\/(.+)$/);
    if (m) {
      const o = mpOrders.get(decodeURIComponent(m[1]));
      return o ? new Response(JSON.stringify(o), { status: 200 }) : new Response("{}", { status: 404 });
    }
    m = caminho.match(/^\/v1\/payments\/(\w+)\/refunds$/);
    if (m && metodo === "POST") {
      const pg = mpPagamentos.get(m[1]);
      if (!pg) return new Response("{}", { status: 404 });
      pg.status = "refunded";
      return new Response(JSON.stringify({ id: 9000 + mpPagamentos.size, payment_id: pg.id, status: "approved", amount: pg.transaction_amount }), { status: 201 });
    }
    m = caminho.match(/^\/v1\/payments\/search\?external_reference=([^&]+)/);
    if (m) {
      const ref = decodeURIComponent(m[1]);
      return new Response(JSON.stringify({ results: [...mpPagamentos.values()].filter((x) => x.external_reference === ref) }), { status: 200 });
    }
    m = caminho.match(/^\/v1\/payments\/(\w+)$/);
    if (m) {
      const pg = mpPagamentos.get(m[1]);
      return pg ? new Response(JSON.stringify(pg), { status: 200 }) : new Response("{}", { status: 404 });
    }
    m = caminho.match(/^\/authorized_payments\/(.+)$/);
    if (m) {
      return new Response(JSON.stringify({ id: m[1], preapproval_id: "pre0abc", payment: { status: "approved" }, transaction_amount: 300,
        debit_date: new Date(relogio).toISOString() }), { status: 200 });
    }
    return new Response("{}", { status: 404 });
  }
  return new Response("{}", { status: 404 });
};

async function chamarMP(env, caminho, metodo, corpo, extra = {}) {
  const r = await fetch("https://api.mercadopago.com" + caminho, { method: metodo, headers: { ...extra }, body: corpo ? JSON.stringify(corpo) : undefined });
  let dados = null;
  try { dados = await r.json(); } catch { dados = null; }
  return { ok: r.ok, status: r.status, dados };
}

const guardados = new Map();
const env = {
  IA_ATIVA: "1",
  CONTAS_IA,
  DEEPINFRA_KEY: "chave-do-deepinfra-so-no-worker",
  IA_PLANOS: JSON.stringify([
    { id: "advogado", nome: "Advogado", valor: 150, valor_anual: 1500, tokens: 12000000, recarga: { valor: 50, tokens: 5000 } },
    { id: "escritorio", nome: "Escritório", valor: 300, valor_anual: 3000, tokens: 30000, recarga: { valor: 50, tokens: 5000 },
      modelos: { padrao: "meta-llama/Llama-3.3-70B-Instruct" } },
    { id: "plus", nome: "Escritório Plus", valor: 550, valor_anual: 5500, tokens: 60000000, recarga: { valor: 50, tokens: 5000 } },
  ]),
  IA_POR_MINUTO: "100",
  MP_WEBHOOK_SECRET: "segredo-de-teste",
  MP_ACCESS_TOKEN: "sem-token",
  ASSETS: { fetch: async () => new Response("site", { status: 200 }) },
  APOIOS: {
    get: async (k) => guardados.get(k) || null,
    getWithMetadata: async (k) => ({ value: guardados.get(k) || null, metadata: null }),
    put: async (k, v) => { guardados.set(k, v); },
    list: async ({ prefix }) => ({ list_complete: true, keys: [...guardados.keys()].filter((k) => k.startsWith(prefix)).map((name) => ({ name })) }),
  },
};
// O painel admin (worker/admin.js) guarda no APOIOS so chaves "admin:" e
// nenhum dado pessoal: o indice das contas e a fila de notas fiscais (conta,
// tipo, valor). Nada com e-mail ou nome.
const soAdminSemPessoa = () => [...guardados.entries()].every(([k, v]) => k.startsWith("admin:") && !/@|dono|escritorio\.com/i.test(String(v)));
const donos = { "token-do-dono": { sub: "1234567890", email: "dono@escritorio.com.br" }, "token-cortesia": { sub: "999", email: "fundador@paulus.ia.br" } };
const deps = { chamarMP, donoDoToken: async (e, t) => donos[t] || null };
const pendentes = [];
const ctx = { waitUntil: (p) => pendentes.push(p) };

async function ia(metodo, caminho, corpo, segredo) {
  const headers = { "content-type": "application/json" };
  if (segredo) headers.authorization = "Bearer " + segredo;
  const req = new Request("https://paulus.ia.br" + caminho, { method: metodo, headers, body: corpo ? JSON.stringify(corpo) : undefined });
  return atenderIA(req, env, new URL(req.url), ctx, deps);
}
const corpoDe = async (r) => r.json();
// O que o bloco de cartao do Mercado Pago entrega no onSubmit (o token e de mentira).
const cartao = (token = "tokaprovado00000000001", extra = {}) => ({ token, payment_method_id: "master", issuer_id: "24", installments: 1,
  transaction_amount: 1, payer: { email: "qualquer@x.com", identification: { type: "CPF", number: "529.982.247-25" } }, ...extra });
// Os dados do escritorio (a pagina de cadastro), sem o id_token.
const CADASTRO = { nome_escritorio: "Moura Advogados", documento: "529.982.247-25", telefone: "(91) 98888-7777", oab: "OAB/PA 12.345", aceite: true,
  endereco: { cep: "66.010-000", logradouro: "Av. Presidente Vargas", numero: "100", complemento: "", bairro: "Campina", cidade: "Belém", uf: "PA", cmun: "1501402" } };

// O plano vem da Atos (worker/atos.js): o retrato do direito, aplicado no medidor da conta.
let versaoAtos = 0;
async function daAtos(idConta, retrato) {
  return medidor(env, idConta).pedir("atos_direito", { id: idConta, retrato: { versao: ++versaoAtos, metadados: null, periodo: "mes", pago_por: "assinatura", ...retrato } });
}
async function creditoDaAtos(idConta, origem, tokens, centavos) {
  return medidor(env, idConta).pedir("atos_credito", { id: idConta, credito: { origem, centavos, metadados: { tokens } } });
}
const idDoSegredo = (seg) => seg.slice(4, 28);
const emDias = (n) => new Date(relogio + n * 864e5).toISOString();

// ------------------------------------------------ desligada
{
  const r = await atenderIA(new Request("https://paulus.ia.br/api/ia/conta"), { ...env, IA_ATIVA: "0" }, new URL("https://paulus.ia.br/api/ia/conta"), ctx, deps);
  checar(r.status === 404, "sem IA_ATIVA as rotas não existem");
  const w = await worker.fetch(new Request("https://paulus.ia.br/api/ia/conta"), { ...env, IA_ATIVA: "0" }, ctx);
  checar(w.status === 404, "pelo Worker inteiro também (rota /api/ia/* vai a ia.js)");
}

// ------------------------------------------------ ativar
let segredo;
{
  const r0 = await ia("POST", "/api/ia/ativar", { id_token: "falso", instalacao_id: "inst-0001-abcd" });
  checar(r0.status === 401, "ativar com id_token que não confere é recusado");
  const r = await ia("POST", "/api/ia/ativar", { id_token: "token-do-dono", instalacao_id: "inst-0001-abcd", nome_escritorio: "Moura <b>Advogados</b>" });
  const d = await corpoDe(r);
  segredo = d.segredo;
  checar(r.status === 200 && /^pia_[0-9a-f]{24}_[0-9a-f]{64}$/.test(segredo), "ativar devolve o segredo da instalação", d);
  checar(d.conta.email === "dono@escritorio.com.br" && d.conta.nome === "Moura bAdvogados/b", "a conta é do e-mail do Google; o nome sem marcação", d.conta);
  checar(!d.conta.plano_vigente && d.conta.tokens.restantes === 0, "conta nova não tem plano nem tokens", d.conta);
  const guardado = [...objetos.values()][0].dados.get("conta");
  checar(!JSON.stringify(guardado).includes(segredo.slice(30)), "o medidor guarda só o resumo do segredo");
  const r2 = await ia("GET", "/api/ia/conta", null, "pia_" + "0".repeat(24) + "_" + "1".repeat(64));
  checar(r2.status === 401, "segredo inventado é recusado");
  const r3 = await ia("GET", "/api/ia/conta", null, segredo);
  checar(r3.status === 200, "o segredo dá acesso à conta");
}

// ------------------------------------------------ o portão antes do plano
const pergunta = { model: "meta-llama/Llama-3.3-70B-Instruct", messages: [{ role: "system", content: "Você é o PAULUS." }, { role: "user", content: "Quando vence o contrato?" }], stream: true, max_tokens: 2000 };
{
  const r = await ia("POST", "/api/ia/v1/chat/completions", pergunta, segredo);
  const d = await corpoDe(r);
  checar(r.status === 403 && d.motivo === "consentimento", "sem o sim do titular, nada sai", d);
  await ia("POST", "/api/ia/consentimento", { aceito: true, versao: "2026-10-01", quem: "Dra. Helena" }, segredo);
  const r2 = await ia("POST", "/api/ia/v1/chat/completions", pergunta, segredo);
  const d2 = await corpoDe(r2);
  checar(r2.status === 402 && d2.motivo === "sem_plano", "com o sim mas sem plano: 402", d2);
  checar(deepinfra.length === 0, "nenhum pedido chegou ao DeepInfra");
}

// ------------------------------------------------ assinar (é na Atos)
{
  const r = await ia("POST", "/api/ia/assinar", { plano: "escritorio" }, segredo);
  const d = await corpoDe(r);
  checar(r.status === 200 && d.link === "https://atos.dev.br/pavlvs/assinar/?preco=pavlvs.escritorio.mes&volta=" + encodeURIComponent("https://paulus.ia.br/") && mpPedidos.length === 0,
    "o 'Fazer upgrade' do PAULUS abre o checkout da Atos; nada vai ao Mercado Pago daqui", d);
  const anual = await corpoDe(await ia("POST", "/api/ia/assinar", { plano: "plus", periodo: "anual" }, segredo));
  checar(anual.link.includes("preco=pavlvs.plus.ano"), "no plano e no período pedidos", anual.link);
  const pagar = await ia("POST", "/api/ia/site/pagar", { id_token: "token-do-dono", plano: "escritorio", periodo: "mensal" });
  const dp = await corpoDe(pagar);
  checar(pagar.status === 409 && dp.codigo === "cobranca_na_atos" && dp.proximo.startsWith("https://atos.dev.br/pavlvs/assinar/"), "pagar pelo caminho antigo: 409, para a Atos", dp);
  // A Atos avisa que a mensalidade foi paga: o plano entra.
  const c0 = await daAtos(idDoSegredo(segredo), { plano: "escritorio", ate: emDias(30), assinatura: { id: "atos-a-1", status: "authorized", proxima: emDias(30), preco: "pavlvs.escritorio.mes" } });
  checar(c0.plano_vigente && c0.cobrador === "atos", "o aviso da Atos dá o plano", c0);
  const c = await corpoDe(await ia("GET", "/api/ia/conta", null, segredo));
  checar(c.plano_vigente && c.tokens.do_mes === 30000 && c.tokens.restantes === 7000 && c.assinatura.situacao === "authorized",
    "o plano pago abre o ciclo com a cota do plano; a da semana é 7/30 dela", c.tokens);
  checar(soAdminSemPessoa(), "o plano da Atos só grava no KV APOIOS o que é do painel, sem dado pessoal", [...guardados.keys()]);
}

// ------------------------------------------------ chamar
{
  const r = await ia("POST", "/api/ia/v1/chat/completions", pergunta, segredo);
  checar(r.status === 200 && r.headers.get("content-type").startsWith("text/event-stream"), "com plano, a resposta vem aos pedaços");
  const texto = await r.text();
  await Promise.all(pendentes.splice(0));
  checar(texto.includes("vence em ") && texto.includes('"usage"'), "os pedaços passam como vieram");
  const enviado = deepinfra[deepinfra.length - 1];
  checar(enviado.auth === "Bearer chave-do-deepinfra-so-no-worker" && enviado.corpo.stream_options.include_usage, "vai ao DeepInfra com a chave do Worker e pedindo o uso");
  const c = await corpoDe(await ia("GET", "/api/ia/conta", null, segredo));
  checar(c.tokens.restantes === 7000 - 1200 && c.semana.usados === 1200 && c.tokens.reservados === 0 && c.tokens.hoje === 1200,
    "desconta o uso real (1.000 + 200) da semana e solta a reserva", c.tokens);
  // max_tokens acima do teto é cortado.
  await (await ia("POST", "/api/ia/v1/chat/completions", { ...pergunta, max_tokens: 99999 }, segredo)).text();
  await Promise.all(pendentes.splice(0));
  checar(deepinfra[deepinfra.length - 1].corpo.max_tokens === 4000, "a saída pedida passa do teto: vai com 4.000");
  // Modelo fora da lista.
  const r3 = await ia("POST", "/api/ia/v1/chat/completions", { ...pergunta, model: "gpt-4o" }, segredo);
  checar(r3.status === 400, "modelo fora da lista é recusado");
  // Texto grande demais.
  const r4 = await ia("POST", "/api/ia/v1/chat/completions", { ...pergunta, messages: [{ role: "user", content: "x".repeat(250000) }] }, segredo);
  checar(r4.status === 413, "texto acima do teto de um pedido é recusado");
  // Sem o uso no fim: entrada estimada + um token por pedaço.
  respostaDoModelo = "sem-uso";
  const antes = (await corpoDe(await ia("GET", "/api/ia/conta", null, segredo))).tokens.restantes;
  await (await ia("POST", "/api/ia/v1/chat/completions", { ...pergunta, max_tokens: 500 }, segredo)).text();
  await Promise.all(pendentes.splice(0));
  const depois = (await corpoDe(await ia("GET", "/api/ia/conta", null, segredo))).tokens.restantes;
  const gasto = antes - depois;
  checar(gasto > 0 && gasto < 500, "sem o uso, cobra pela estimativa (e não a reserva inteira)", gasto);
  // O provedor com erro: nada é cobrado.
  respostaDoModelo = "erro";
  const r5 = await ia("POST", "/api/ia/v1/chat/completions", pergunta, segredo);
  const d5 = await corpoDe(r5);
  const depois2 = (await corpoDe(await ia("GET", "/api/ia/conta", null, segredo))).tokens;
  checar(r5.status === 502 && d5.erro.includes("overloaded") && depois2.restantes === depois && depois2.reservados === 0, "erro do provedor: 502 e a reserva volta", { d5, depois2 });
  respostaDoModelo = "padrao";
  // Sem stream (o pedido de JSON).
  const r6 = await ia("POST", "/api/ia/v1/chat/completions", { ...pergunta, stream: false, response_format: { type: "json_object" } }, segredo);
  const d6 = await corpoDe(r6);
  checar(r6.status === 200 && d6.paulus.tokens === 150 && deepinfra[deepinfra.length - 1].corpo.response_format.type === "json_object", "sem stream: o JSON e o uso", d6.paulus);
}

// ------------------------------------------------ a cota acaba
{
  const c = await corpoDe(await ia("GET", "/api/ia/conta", null, segredo));
  // Gasta quase tudo de uma vez, direto no medidor.
  const o = [...objetos.values()][0];
  const conta = o.dados.get("conta");
  conta.ciclo.usados = conta.ciclo.tokens - 200;
  o.dados.set("conta", conta);
  const r = await ia("POST", "/api/ia/v1/chat/completions", pergunta, segredo);
  const d = await corpoDe(r);
  checar(r.status === 402 && d.motivo === "cota" && d.conta.tokens.restantes === 200, "sem saldo para a pergunta: 402, com o que resta", d);
  checar(c.tokens.restantes > 200, "(antes havia mais)");
}

// ------------------------------------------------ recarga (é na Atos)
{
  const r = await ia("POST", "/api/ia/recarga", {}, segredo);
  const d = await corpoDe(r);
  checar(r.status === 409 && d.codigo === "cobranca_na_atos", "a recarga pelo caminho antigo: 409, para a Conta Atos", d);
  checar((await ia("GET", "/api/ia/recarga/ORD1234567", null, segredo)).status === 409, "e a consulta de um Pix antigo também");
  await creditoDaAtos(idDoSegredo(segredo), "order:R1", 5000, 5000);
  const c = await corpoDe(await ia("GET", "/api/ia/conta", null, segredo));
  checar(c.tokens.da_recarga === 5000 && c.tokens.restantes === 5200 && c.recargas.length === 1, "os créditos comprados na Atos entram", c.tokens);
  await creditoDaAtos(idDoSegredo(segredo), "order:R1", 5000, 5000);
  checar((await corpoDe(await ia("GET", "/api/ia/conta", null, segredo))).tokens.da_recarga === 5000, "o mesmo pagamento não credita duas vezes");
  checar((await worker.fetch(new Request("https://paulus.ia.br/api/mp/pix/R1"), env, ctx)).status === 404, "a rota do Pix do apoio não existe mais");
  // Gasta do ciclo e depois da recarga.
  await (await ia("POST", "/api/ia/v1/chat/completions", pergunta, segredo)).text();
  await Promise.all(pendentes.splice(0));
  const c3 = await corpoDe(await ia("GET", "/api/ia/conta", null, segredo));
  checar(c3.tokens.do_ciclo === 0 && c3.tokens.da_recarga === 5000 - 1000, "gasta o ciclo primeiro, o resto da recarga", c3.tokens);
}

// ------------------------------------------------ renovação (a Atos estende)
{
  relogio += 31 * 24 * 3600 * 1000;
  await daAtos(idDoSegredo(segredo), { plano: "escritorio", ate: emDias(29), assinatura: { id: "atos-a-1", status: "authorized", proxima: emDias(29), preco: "pavlvs.escritorio.mes" } });
  const c = await corpoDe(await ia("GET", "/api/ia/conta", null, segredo));
  checar(c.tokens.do_ciclo === 30000 && c.tokens.da_recarga === 4000, "a mensalidade seguinte paga abre o ciclo novo; a recarga continua", c.tokens);
}

// ------------------------------------------------ cancelar e vencer (na Atos)
{
  const r = await ia("POST", "/api/ia/assinatura/cancelar", null, segredo);
  checar(r.status === 409 && (await corpoDe(r)).proximo === "https://atos.dev.br/conta/", "cancelar pelo caminho antigo: 409, para a Conta Atos");
  const sit = await corpoDe(await ia("GET", "/api/ia/assinatura", null, segredo));
  checar(sit.plano_vigente && sit.assinatura.situacao === "authorized", "a situação da assinatura é a do resumo", sit.assinatura);
  const ate = (await corpoDe(await ia("GET", "/api/ia/conta", null, segredo))).pago_ate;
  await daAtos(idDoSegredo(segredo), { plano: "escritorio", ate, assinatura: { id: "atos-a-1", status: "canceled", proxima: null, preco: "pavlvs.escritorio.mes" } });
  const d = await corpoDe(await ia("GET", "/api/ia/conta", null, segredo));
  checar(d.assinatura.situacao === "cancelled" && d.plano_vigente, "cancelada na Atos: o mês pago continua até o fim", d.assinatura);
  relogio += 32 * 24 * 3600 * 1000;
  const c = await corpoDe(await ia("GET", "/api/ia/conta", null, segredo));
  checar(!c.plano_vigente && c.tokens.restantes === 0, "fim do mês pago sem assinatura: nada mais sai", c);
  const r2 = await ia("POST", "/api/ia/v1/chat/completions", pergunta, segredo);
  checar(r2.status === 402, "e o portão bloqueia");
}

// ------------------------------------------------ retirar o sim, sair, cortesia, por minuto
{
  await ia("POST", "/api/ia/consentimento", { aceito: false }, segredo);
  const c = await corpoDe(await ia("GET", "/api/ia/conta", null, segredo));
  checar(c.consentimento === null, "retirar o sim apaga o consentimento");
  const outro = await corpoDe(await ia("POST", "/api/ia/ativar", { id_token: "token-do-dono", instalacao_id: "inst-0002-abcd" }));
  checar(outro.conta.instalacoes === 2, "outra instalação da mesma conta ganha outro segredo");
  await ia("POST", "/api/ia/sair", null, outro.segredo);
  checar((await ia("GET", "/api/ia/conta", null, outro.segredo)).status === 401, "sair apaga o segredo desta instalação");
  checar((await ia("GET", "/api/ia/conta", null, segredo)).status === 200, "e o da outra continua");

  const { createHash } = await import("node:crypto");
  const envCortesia = { ...env, IA_CORTESIA: createHash("sha256").update("fundador@paulus.ia.br").digest("hex") };
  const req = new Request("https://paulus.ia.br/api/ia/ativar", { method: "POST", body: JSON.stringify({ id_token: "token-cortesia", instalacao_id: "inst-funda-0001" }) });
  const f = await (await atenderIA(req, envCortesia, new URL(req.url), ctx, deps)).json();
  checar(f.conta.cortesia && f.conta.plano_vigente && f.conta.tokens.restantes === 7000, "o e-mail da cortesia tem o plano sem pagar", f.conta);
  const fs = f.segredo;
  await atenderIA(new Request("https://paulus.ia.br/api/ia/consentimento", { method: "POST", headers: { authorization: "Bearer " + fs }, body: JSON.stringify({ aceito: true, versao: "v" }) }),
    envCortesia, new URL("https://paulus.ia.br/api/ia/consentimento"), ctx, deps);
  const envMinuto = { ...envCortesia, IA_POR_MINUTO: "2" };
  const status = [];
  for (let i = 0; i < 3; i++) {
    const q = new Request("https://paulus.ia.br/api/ia/v1/chat/completions", { method: "POST", headers: { authorization: "Bearer " + fs }, body: JSON.stringify({ ...pergunta, max_tokens: 300 }) });
    const r = await atenderIA(q, envMinuto, new URL(q.url), ctx, deps);
    status.push(r.status);
    await r.text();
    await Promise.all(pendentes.splice(0));
  }
  checar(status.join() === "200,200,429", "o teto de pedidos por minuto para o terceiro", status);
}

// ------------------------------------------------ o uso no fim, partido
checar(usoDoFim('data: {"choices":[]}\n\ndata: {"choices":[],"usage":{"prompt_tokens":7,"completion_tokens":3}}\n\ndata: [DONE]').entrada === 7, "lê o uso da última linha");
checar(usoDoFim("data: {\"usa") === null, "linha partida não quebra");

// ------------------------------------------------ o aviso do Mercado Pago de antes
{
  const antes = guardados.size;
  const r = await worker.fetch(aviso("ORDAPOIO1", "order"), env, ctx);
  await Promise.all(pendentes.splice(0));
  checar(r.status === 200 && (await corpoDe(r)).ignorado && guardados.size === antes && mpPedidos.length === 0,
    "o webhook do Mercado Pago de antes da Atos responde 200 e não faz nada");
}

// ------------------------------------------------ os planos e o cadastro pelo site
{
  donos["token-novo"] = { sub: "555", email: "nova@advocacia.com.br" };
  const planos = await corpoDe(await ia("GET", "/api/ia/planos"));
  checar(planos.planos.map((p) => p.id).join() === "advogado,escritorio,plus" && planos.planos[1].tokens === 30000
    && planos.planos[2].recursos.word && !planos.planos[0].recursos.equipe && planos.planos[2].modelos_info[0].nome === "Claude Sonnet 5.5",
    "três planos (IA_PLANOS), com o que falta vindo do de fábrica: recursos e modelos", planos.planos);

  let r = await ia("POST", "/api/ia/site/entrar", { id_token: "vencido" });
  checar(r.status === 401, "sem o Google confirmado, o site não entra");
  const entrou = await corpoDe(await ia("POST", "/api/ia/site/entrar", { id_token: "token-novo" }));
  checar(entrou.ok && entrou.email === "nova@advocacia.com.br" && entrou.cadastro === null && !entrou.plano_vigente && entrou.instalacoes === 0,
    "entrar pelo site abre a conta, sem cadastro, sem plano e sem instalação", entrou);

  const base = { id_token: "token-novo", nome_escritorio: "Nova Advocacia", documento: "529.982.247-25", telefone: "(91) 98888-7777",
    oab: "OAB/PA 12.345", aceite: true,
    endereco: { cep: "66.010-000", logradouro: "  Av. Presidente\u0000 Vargas ", numero: "100", complemento: "", bairro: "Campina", cidade: "Belém", uf: "pa", cmun: "1501402" } };
  const erro = async (mudanca) => (await corpoDe(await ia("POST", "/api/ia/site/cadastro", { ...base, ...mudanca }))).erro || "";
  checar((await erro({ endereco: undefined })).includes("endereço"), "cadastro novo sem endereço é recusado");
  checar((await erro({ endereco: { ...base.endereco, cep: "6601" } })).includes("CEP"), "CEP sem 8 dígitos é recusado");
  checar((await erro({ endereco: { ...base.endereco, numero: " " } })).includes("número"), "endereço sem número é recusado");
  checar((await erro({ endereco: { ...base.endereco, bairro: "" } })).includes("bairro"), "endereço sem bairro é recusado");
  checar((await erro({ endereco: { ...base.endereco, uf: "XX" } })).includes("UF"), "UF inexistente é recusada");
  checar((await erro({ endereco: { ...base.endereco, cmun: "150140" } })).includes("IBGE"), "código IBGE com 6 dígitos é recusado");
  checar((await erro({ documento: "111.111.111-11" })).includes("CPF ou CNPJ"), "CPF com dígito errado é recusado");
  checar((await erro({ telefone: "98888-7777" })).includes("DDD"), "telefone sem DDD é recusado");
  checar((await erro({ oab: "abc" })).includes("RG"), "sem OAB, RG ou CNH é recusado");
  checar((await erro({ aceite: false })).includes("aceitar"), "sem aceitar os termos, não cadastra");
  checar((await erro({ plano: "ouro" })) === "esse plano não existe", "plano que não existe é recusado");

  r = await ia("POST", "/api/ia/site/cadastro", { ...base, plano: "advogado" });
  const assinou = await corpoDe(r);
  checar(r.status === 200 && assinou.proximo.startsWith("https://atos.dev.br/pavlvs/assinar/?preco=pavlvs.advogado.mes") && mpPedidos.length === 0,
    "o cadastro com o plano Advogado leva ao checkout da Atos", assinou);
  const situacao = await corpoDe(await ia("POST", "/api/ia/site/situacao", { id_token: "token-novo" }));
  checar(!situacao.plano_vigente, "antes de pagar na Atos, sem plano", situacao.plano_vigente);
  checar(situacao.cadastro && situacao.cadastro.documento === "52998224725" && situacao.cadastro.oab === "PA 12345" && situacao.nome === "Nova Advocacia",
    "o cadastro fica na conta, conferido e normalizado", situacao.cadastro);
  const end = situacao.cadastro.endereco || {};
  checar(end.cep === "66010000" && end.logradouro === "Av. Presidente Vargas" && end.uf === "PA" && end.cmun === "1501402" && end.cidade === "Belém" && end.complemento === "",
    "o endereço fica no cadastro, limpo (CEP só dígitos, UF maiúscula, código IBGE)", end);
  for (const rota of ["/api/ia/site/plano", "/api/ia/site/oferta", "/api/ia/site/pix", "/api/ia/site/pagar-fora", "/api/ia/site/desistir"]) {
    const x = await ia("POST", rota, { id_token: "token-novo", plano: "plus" });
    checar(x.status === 409 && (await corpoDe(x)).codigo === "cobranca_na_atos", rota + ": 409, para a Atos");
  }

  // A conta antiga, cadastrada antes do endereço, continua valendo sem ele.
  donos["token-antigo"] = { sub: "666", email: "antiga@advocacia.com.br" };
  await ia("POST", "/api/ia/site/entrar", { id_token: "token-antigo" });
  const contaSemEndereco = [...objetos.values()].find((x) => (x.dados.get("conta") || {}).dono?.sub === "666");
  const guardada = contaSemEndereco.dados.get("conta");
  guardada.cadastro = { nome_escritorio: "Antiga Advocacia", documento: "52998224725", telefone: "91988887777", oab: "PA 12345", termos: "2026-10-02" };
  contaSemEndereco.dados.set("conta", guardada);
  const antiga = await ia("POST", "/api/ia/site/cadastro", { ...base, id_token: "token-antigo", endereco: undefined, nome_escritorio: "Antiga Advocacia" });
  const antigaCorpo = await corpoDe(antiga);
  checar(antiga.status === 200 && antigaCorpo.cadastro && !antigaCorpo.cadastro.endereco, "conta antiga sem endereço: o cadastro continua aceito sem ele", antigaCorpo);
  const antigaRuim = await ia("POST", "/api/ia/site/cadastro", { ...base, id_token: "token-antigo", endereco: { ...base.endereco, cep: "1" } });
  checar(antigaRuim.status === 400, "mas, se mandar o endereço, ele é conferido");

  // Pago na Atos: o PAULUS instalado entra com a mesma conta e já encontra o plano.
  const contaNova = [...objetos.entries()].find(([, x]) => (x.dados.get("conta") || {}).dono?.sub === "555")[0];
  await daAtos(contaNova, { plano: "plus", ate: emDias(30), metadados: { plano: "plus", tokens_por_ciclo: 60000000, pessoas: 15 },
    assinatura: { id: "atos-a-555", status: "authorized", proxima: emDias(30), preco: "pavlvs.plus.mes" } });
  const ativou = await corpoDe(await ia("POST", "/api/ia/ativar", { id_token: "token-novo", instalacao_id: "inst-nova-0001" }));
  checar(ativou.conta.plano_vigente && ativou.conta.plano.id === "plus" && ativou.conta.instalacoes === 1 && ativou.conta.ciclo.tokens === 60000000,
    "o PAULUS instalado entra com a mesma conta e já tem o plano pago na Atos", ativou.conta);
}


// ------------------------------------------------ os planos de 03/10: modelos, profundidade, semana e anual
{
  const { createHash } = await import("node:crypto");
  const hash = (e) => createHash("sha256").update(e).digest("hex");
  // Os planos de fabrica (sem IA_PLANOS), com as chaves dos tres provedores.
  const envReal = { ...env, IA_PLANOS: undefined, MISTRAL_KEY: "chave-mistral", ANTHROPIC_KEY: "chave-anthropic",
    IA_CORTESIA: ["plus@a.br", "adv@a.br", "esc@a.br"].map(hash).join(",") };
  const pedir = async (e, metodo, caminho, corpo, seg) => {
    const headers = { "content-type": "application/json" };
    if (seg) headers.authorization = "Bearer " + seg;
    const req = new Request("https://paulus.ia.br" + caminho, { method: metodo, headers, body: corpo ? JSON.stringify(corpo) : undefined });
    return atenderIA(req, e, new URL(req.url), ctx, deps);
  };
  const objetoDe = (sub) => [...objetos.values()].find((x) => (x.dados.get("conta") || {}).dono?.sub === sub);
  // Uma conta de cortesia no plano pedido, com o sim dado.
  const contaNoPlano = async (sub, email, plano, e = envReal) => {
    donos["tk-" + sub] = { sub, email };
    const a = await corpoDe(await pedir(e, "POST", "/api/ia/ativar", { id_token: "tk-" + sub, instalacao_id: "inst-" + sub + "-0001" }));
    const o = objetoDe(sub);
    const c = o.dados.get("conta");
    c.plano = plano;
    delete c.ciclo;
    o.dados.set("conta", c);
    await pedir(e, "POST", "/api/ia/consentimento", { aceito: true, versao: "v" }, a.segredo);
    return a.segredo;
  };

  // O Plus fala com o Claude: o Sonnet no dia a dia, o Opus no Ministro.
  const sp = await contaNoPlano("801", "plus@a.br", "plus");
  const conta = await corpoDe(await pedir(envReal, "GET", "/api/ia/conta", null, sp));
  checar(conta.plano.id === "plus" && conta.tokens.do_mes === 40000000 && conta.semana.cota === Math.round(40000000 * 7 / 30)
    && conta.modelos.map((x) => x.nome).join() === "Claude Sonnet 5.5,Claude Opus 5.5",
    "a conta do Plus: 40 milhões de créditos no mês, a semana em 7/30, os modelos do Claude", { semana: conta.semana, modelos: conta.modelos });
  let r = await pedir(envReal, "POST", "/api/ia/v1/chat/completions", { ...pergunta, messages: [...pergunta.messages, { role: "assistant", content: "começo" }] }, sp);
  const texto = await r.text();
  await Promise.all(pendentes.splice(0));
  const pc = claude.at(-1);
  checar(r.status === 200 && r.headers.get("x-paulus-modelo") === "claude-sonnet-5-5" && pc.corpo.model === "claude-sonnet-5-5",
    "o PAULUS pede o Llama, mas o Plus responde com o Claude Sonnet 5.5", { status: r.status, modelo: pc && pc.corpo.model });
  checar(pc.headers["x-api-key"] === "chave-anthropic" && pc.headers["anthropic-beta"] === "server-side-fallback-2026-07-01" && pc.corpo.fallbacks === "default"
    && pc.corpo.thinking.type === "between_tools" && pc.corpo.system === "Você é o PAULUS." && pc.corpo.messages.length === 1 && pc.corpo.messages[0].role === "user"
    && pc.corpo.temperature === undefined, "o pedido ao Claude: chave do Worker, fallback, sem pensar, system à parte, termina no usuário", pc.corpo);
  checar(texto.includes('"content":"Prazo de "') && texto.includes('"content":"15 dias."') && texto.includes('"prompt_tokens":1000') && texto.includes('"completion_tokens":50')
    && texto.trim().endsWith("data: [DONE]"), "os eventos do Claude viram os pedaços do OpenAI, com o uso no fim", texto);
  let depois = await corpoDe(await pedir(envReal, "GET", "/api/ia/conta", null, sp));
  checar(depois.semana.usados === 1050 && depois.tokens.hoje === 1050, "o Sonnet gasta um crédito por token", depois.semana);
  r = await pedir(envReal, "POST", "/api/ia/v1/chat/completions", { ...pergunta, paulus_nivel: "ministro", max_tokens: 1000 }, sp);
  await r.text();
  await Promise.all(pendentes.splice(0));
  checar(claude.at(-1).corpo.model === "claude-opus-5-5" && claude.at(-1).corpo.output_config.effort === "high" && claude.at(-1).corpo.max_tokens === 5000
    && !claude.at(-1).corpo.thinking, "no Ministro, o Opus 5.5 com esforço alto e folga para pensar", claude.at(-1).corpo);
  depois = await corpoDe(await pedir(envReal, "GET", "/api/ia/conta", null, sp));
  checar(depois.semana.usados === 1050 + 2 * 1050, "o Opus gasta dois créditos por token", depois.semana);
  // Nos 7 primeiros dias da assinatura paga, o Plus responde só com o Sonnet; no 8º dia, o Opus.
  const spPago = await contaNoPlano("8011", "pluspago@a.br", "plus");
  const oPago = objetoDe("8011");
  const cPago = oPago.dados.get("conta");
  cPago.cortesia = false;
  cPago.cobrador = "atos";
  cPago.periodo = "mensal";
  cPago.pago_ate = new Date(relogio + 30 * 864e5).toISOString();
  cPago.assinatura = { id: "atos-plus", situacao: "authorized", valor: 3490, desde: new Date(relogio).toISOString() };
  cPago.ciclo = { inicio: new Date(relogio).toISOString(), fim: new Date(relogio + 30 * 864e5).toISOString(), tokens: 40000000, usados: 0, origem: "assinatura",
    semana: Math.round(40000000 * 7 / 30), por_semana: {} };
  oPago.dados.set("conta", cPago);
  r = await pedir(envReal, "POST", "/api/ia/v1/chat/completions", { ...pergunta, paulus_nivel: "ministro", max_tokens: 1000 }, spPago);
  await r.text();
  await Promise.all(pendentes.splice(0));
  checar(r.status === 200 && claude.at(-1).corpo.model === "claude-sonnet-5-5" && r.headers.get("x-paulus-modelo") === "claude-sonnet-5-5"
    && /Opus 5.5 libera no 8º dia/.test(decodeURIComponent(r.headers.get("x-paulus-aviso") || "")), "primeira semana do Plus: o Ministro responde com o Sonnet, e o aviso diz quando o Opus libera",
    { modelo: claude.at(-1).corpo.model, aviso: decodeURIComponent(r.headers.get("x-paulus-aviso") || "") });
  relogio += 8 * 864e5;
  r = await pedir(envReal, "POST", "/api/ia/v1/chat/completions", { ...pergunta, paulus_nivel: "ministro", max_tokens: 1000 }, spPago);
  await r.text();
  await Promise.all(pendentes.splice(0));
  checar(claude.at(-1).corpo.model === "claude-opus-5-5" && !r.headers.get("x-paulus-aviso"), "no 8º dia, o Opus", claude.at(-1).corpo.model);
  relogio -= 8 * 864e5;
  r = await pedir(envReal, "POST", "/api/ia/v1/chat/completions", { ...pergunta, stream: false, response_format: { type: "json_object" } }, sp);
  const dj = await corpoDe(r);
  checar(r.status === 200 && dj.choices[0].message.content === '{"ok":true}' && dj.paulus.tokens === 120 && dj.paulus.modelo === "claude-sonnet-5-5"
    && claude.at(-1).corpo.system.includes("JSON"), "sem stream: o JSON do Claude no formato OpenAI", dj);
  respostaDoClaude = "recusa";
  r = await pedir(envReal, "POST", "/api/ia/v1/chat/completions", { ...pergunta, stream: false }, sp);
  checar(r.status === 400 && (await corpoDe(r)).erro.includes("recusou"), "o Claude recusou (depois do fallback): erro, e nada é cobrado");
  const rs = await pedir(envReal, "POST", "/api/ia/v1/chat/completions", pergunta, sp);
  const ts = await rs.text();
  await Promise.all(pendentes.splice(0));
  checar(ts.includes("interrompeu esta resposta"), "recusa no meio do stream: a resposta diz que foi interrompida", ts);
  respostaDoClaude = "padrao";
  checar((await pedir({ ...envReal, ANTHROPIC_KEY: undefined }, "POST", "/api/ia/v1/chat/completions", pergunta, sp)).status === 503,
    "sem a chave do Anthropic no Worker: 503");

  // O Advogado: o Llama, e a profundidade só até Advogado.
  const sa = await contaNoPlano("802", "adv@a.br", "advogado");
  r = await pedir(envReal, "POST", "/api/ia/v1/chat/completions", { ...pergunta, paulus_nivel: "juiz" }, sa);
  const dn = await corpoDe(r);
  checar(r.status === 403 && dn.motivo === "profundidade" && dn.erro.includes("Escritório"), "o nível Juiz não é do Advogado: 403, dizendo o plano que tem", dn);
  r = await pedir(envReal, "POST", "/api/ia/v1/chat/completions", { ...pergunta, model: "claude-opus-5-5", paulus_nivel: "advogado" }, sa);
  await r.text();
  await Promise.all(pendentes.splice(0));
  checar(r.headers.get("x-paulus-modelo") === "meta-llama/Llama-3.3-70B-Instruct" && deepinfra.at(-1).corpo.model === "meta-llama/Llama-3.3-70B-Instruct",
    "pedir um modelo de outro plano não adianta: vai o do plano");
  const modelosAdv = await corpoDe(await pedir(envReal, "GET", "/api/ia/modelos", null, sa));
  checar(modelosAdv.modelos.join() === "meta-llama/Llama-3.3-70B-Instruct", "os modelos da conta são os do plano", modelosAdv);

  // O Escritório: a Mistral, no formato OpenAI dela.
  const se = await contaNoPlano("803", "esc@a.br", "escritorio");
  r = await pedir(envReal, "POST", "/api/ia/v1/chat/completions", { ...pergunta, temperature: 0.2 }, se);
  const tm = await r.text();
  await Promise.all(pendentes.splice(0));
  const pm = mistral.at(-1);
  checar(r.status === 200 && pm.auth === "Bearer chave-mistral" && pm.corpo.model === "mistral-large-latest" && !pm.corpo.stream_options && pm.corpo.temperature === 0.2
    && tm.includes("Mistral "), "o Escritório responde com o Mistral Large 3, sem stream_options", pm.corpo);
  const ce = await corpoDe(await pedir(envReal, "GET", "/api/ia/conta", null, se));
  checar(ce.semana.usados === 600, "o uso da Mistral sai do fim do stream", ce.semana);

  // A semana: acabou a cota da semana, com o mês ainda cheio.
  const oe = objetoDe("803");
  let c = oe.dados.get("conta");
  c.ciclo.por_semana = { 0: c.ciclo.semana - 100 };
  c.ciclo.usados = c.ciclo.semana - 100;
  oe.dados.set("conta", c);
  r = await pedir(envReal, "POST", "/api/ia/v1/chat/completions", pergunta, se);
  const dsem = await corpoDe(r);
  checar(r.status === 402 && dsem.motivo === "semana" && dsem.erro.includes("volta em"), "a cota da semana acabou: 402, dizendo quando volta", dsem);
  r = await pedir(envReal, "POST", "/api/ia/adiantar", null, se);
  const dad = await corpoDe(r);
  checar(r.status === 409 && dad.erro.includes("7 primeiros dias"), "nos 7 primeiros dias, não adianta a semana", dad);
  // No 9º dia (semana 2): adianta uma vez, a semana dobra e a seguinte fica vazia.
  relogio += 8 * 24 * 3600 * 1000;
  c = oe.dados.get("conta");
  c.ciclo.por_semana[1] = c.ciclo.semana;
  c.ciclo.usados += c.ciclo.semana;
  oe.dados.set("conta", c);
  let cs = await corpoDe(await pedir(envReal, "GET", "/api/ia/conta", null, se));
  checar(cs.semana.numero === 2 && cs.semana.livres === 0 && cs.semana.adiantamento.pode, "na semana 2, sem cota, o adiantamento está liberado", cs.semana);
  r = await pedir(envReal, "POST", "/api/ia/adiantar", null, se);
  cs = await corpoDe(r);
  checar(r.status === 200 && cs.semana.limite === 2 * cs.semana.cota && cs.semana.livres === cs.semana.cota && cs.semana.adiantamento.usado,
    "adiantar: a semana ganha a cota da seguinte", cs.semana);
  r = await pedir(envReal, "POST", "/api/ia/v1/chat/completions", pergunta, se);
  await r.text();
  await Promise.all(pendentes.splice(0));
  checar(r.status === 200, "e a pergunta volta a sair");
  checar((await pedir(envReal, "POST", "/api/ia/adiantar", null, se)).status === 409, "o segundo adiantamento do mês é recusado");
  relogio += 7 * 24 * 3600 * 1000;
  cs = await corpoDe(await pedir(envReal, "GET", "/api/ia/conta", null, se));
  checar(cs.semana.numero === 3 && cs.semana.limite === 0 && cs.tokens.restantes === 0, "a semana seguinte, já adiantada, fica vazia", cs.semana);
  relogio -= 15 * 24 * 3600 * 1000;

}

function aviso(dataId, tipo, ts = Date.now()) {
  const requestId = "4ed4fa2b-0b31-42ec-a62f-ad793c486c59";
  const id = /^[A-Z0-9]+$/.test(dataId) && /[A-Z]/.test(dataId) ? dataId.toLowerCase() : dataId;
  const manifest = `id:${id};request-id:${requestId};ts:${ts};`;
  const v1 = createHmac("sha256", env.MP_WEBHOOK_SECRET).update(manifest).digest("hex");
  return new Request(`https://paulus.ia.br/api/mp/aviso?data.id=${dataId}&type=${tipo}`, {
    method: "POST",
    headers: { "x-signature": `ts=${ts},v1=${v1}`, "x-request-id": requestId },
    body: "{}",
  });
}

console.log(falhas ? `\n  ${falhas} falha(s)` : "\n  nuvem: todos os testes passaram");
process.exit(falhas ? 1 : 0);
