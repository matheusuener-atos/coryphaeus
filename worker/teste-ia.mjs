// Teste da nuvem do PAULUS no Worker (worker/ia.js), sem rede:
//   node worker/teste-ia.mjs
// O DeepInfra e o Mercado Pago sao de mentira; o Durable Object roda aqui,
// com a mesma classe, sobre um Map.
import { createHmac } from "node:crypto";
import worker from "./index.js";
import { atenderIA, ContaIA, usoDoFim } from "./ia.js";

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
  if (u.startsWith("https://api.mercadopago.com")) {
    const caminho = u.slice("https://api.mercadopago.com".length);
    const metodo = init.method || "GET";
    const corpo = init.body ? JSON.parse(init.body) : null;
    mpPedidos.push({ caminho, metodo, corpo });
    if (caminho === "/preapproval" && metodo === "POST") {
      const id = "pre" + mpPreapprovals.size + "abc";
      mpPreapprovals.set(id, { id, status: "pending", external_reference: corpo.external_reference, auto_recurring: corpo.auto_recurring });
      return new Response(JSON.stringify({ id, status: "pending", init_point: "https://mp/assinar/" + id }), { status: 201 });
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
    m = caminho.match(/^\/authorized_payments\/(.+)$/);
    if (m) {
      return new Response(JSON.stringify({ id: m[1], preapproval_id: "pre0abc", payment: { status: "approved" }, transaction_amount: 300,
        debit_date: new Date(relogio).toISOString() }), { status: 200 });
    }
    return new Response("{}", { status: 404 });
  }
  return new Response("{}", { status: 404 });
};

async function chamarMP(env, caminho, metodo, corpo) {
  const r = await fetch("https://api.mercadopago.com" + caminho, { method: metodo, headers: {}, body: corpo ? JSON.stringify(corpo) : undefined });
  let dados = null;
  try { dados = await r.json(); } catch { dados = null; }
  return { ok: r.ok, status: r.status, dados };
}

const guardados = new Map();
const env = {
  IA_ATIVA: "1",
  CONTAS_IA,
  DEEPINFRA_KEY: "chave-do-deepinfra-so-no-worker",
  IA_PLANO_TOKENS: "10000",
  IA_RECARGA_TOKENS: "5000",
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

// ------------------------------------------------ assinar
let preId;
{
  const r = await ia("POST", "/api/ia/assinar", { email: "dono@escritorio.com.br" }, segredo);
  const d = await corpoDe(r);
  preId = d.id;
  const criado = mpPedidos.find((p) => p.caminho === "/preapproval" && p.metodo === "POST");
  checar(r.status === 200 && d.link.includes(preId), "assinar devolve o link do Mercado Pago", d);
  checar(criado.corpo.auto_recurring.transaction_amount === 300 && /^ia-assinatura-[0-9a-f]{24}$/.test(criado.corpo.external_reference),
    "a assinatura é de R$ 300/mês com a referência da conta", criado.corpo);
  // O cartão posto: o aviso do Mercado Pago chega pelo Worker inteiro.
  mpPreapprovals.get(preId).status = "authorized";
  const av = await worker.fetch(aviso(preId, "subscription_preapproval"), env, ctx);
  await Promise.all(pendentes.splice(0));
  checar(av.status === 200, "o aviso da assinatura é aceito");
  const c = await corpoDe(await ia("GET", "/api/ia/conta", null, segredo));
  checar(c.plano_vigente && c.tokens.restantes === 10000 && c.assinatura.situacao === "authorized", "assinatura ativa abre o ciclo com a cota do plano", c);
  checar(guardados.size === 0, "a assinatura da nuvem não grava nada no KV APOIOS", [...guardados.keys()]);
  // A primeira cobrança (logo depois) só confirma o ciclo aberto.
  await worker.fetch(aviso("cob-1", "subscription_authorized_payment"), env, ctx);
  await Promise.all(pendentes.splice(0));
  const c2 = await corpoDe(await ia("GET", "/api/ia/conta", null, segredo));
  checar(c2.ciclo.inicio === c.ciclo.inicio && c2.tokens.restantes === 10000, "a primeira cobrança não abre um segundo ciclo", c2.ciclo);
  checar(guardados.size === 0, "a cobrança do plano não grava nada no KV APOIOS");
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
  checar(c.tokens.restantes === 10000 - 1200 && c.tokens.reservados === 0 && c.tokens.hoje === 1200, "desconta o uso real (1.000 + 200) e solta a reserva", c.tokens);
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

// ------------------------------------------------ recarga
{
  const r = await ia("POST", "/api/ia/recarga", {}, segredo);
  const d = await corpoDe(r);
  checar(mpPedidos.filter((p) => p.caminho === "/v1/orders").pop().corpo.payer.email === "dono@escritorio.com.br", "sem e-mail no pedido, vai o da conta Google");
  checar(r.status === 200 && d.qr_code === "000201pix" && d.tokens === 5000 && d.valor === "50.00", "a recarga é um Pix de R$ 50 com o QR", d);
  const pend = await corpoDe(await ia("GET", "/api/ia/recarga/" + d.id, null, segredo));
  checar(pend.pago === false, "antes de pagar, nada entra");
  mpOrders.get(d.id).status = "processed";
  // O aviso do Pix pago, pelo Worker inteiro.
  await worker.fetch(aviso(d.id, "order"), env, ctx);
  await Promise.all(pendentes.splice(0));
  const c = await corpoDe(await ia("GET", "/api/ia/conta", null, segredo));
  checar(c.tokens.da_recarga === 5000 && c.tokens.restantes === 5200 && c.recargas.length === 1, "o Pix pago põe os tokens da recarga", c.tokens);
  checar(guardados.size === 0, "a recarga não grava nada no KV APOIOS");
  // Conferir de novo (o PAULUS pergunta) não credita duas vezes.
  await ia("GET", "/api/ia/recarga/" + d.id, null, segredo);
  const c2 = await corpoDe(await ia("GET", "/api/ia/conta", null, segredo));
  checar(c2.tokens.da_recarga === 5000, "o mesmo Pix não credita duas vezes");
  // A antiga rota do Pix do apoio saiu.
  checar((await worker.fetch(new Request("https://paulus.ia.br/api/mp/pix/" + d.id), env, ctx)).status === 404, "a rota do Pix do apoio não existe mais");
  // Gasta do ciclo e depois da recarga.
  await (await ia("POST", "/api/ia/v1/chat/completions", pergunta, segredo)).text();
  await Promise.all(pendentes.splice(0));
  const c3 = await corpoDe(await ia("GET", "/api/ia/conta", null, segredo));
  checar(c3.tokens.do_ciclo === 0 && c3.tokens.da_recarga === 5000 - 1000, "gasta o ciclo primeiro, o resto da recarga", c3.tokens);
}

// ------------------------------------------------ renovação
{
  relogio += 31 * 24 * 3600 * 1000;
  await worker.fetch(aviso("cob-2", "subscription_authorized_payment"), env, ctx);
  await Promise.all(pendentes.splice(0));
  const c = await corpoDe(await ia("GET", "/api/ia/conta", null, segredo));
  checar(c.tokens.do_ciclo === 10000 && c.tokens.da_recarga === 4000, "a cobrança do mês seguinte abre o ciclo novo; a recarga continua", c.tokens);
  await worker.fetch(aviso("cob-2", "subscription_authorized_payment"), env, ctx);
  await Promise.all(pendentes.splice(0));
  const c2 = await corpoDe(await ia("GET", "/api/ia/conta", null, segredo));
  checar(c2.ciclo.inicio === c.ciclo.inicio, "o mesmo aviso repetido não abre outro ciclo");
}

// ------------------------------------------------ cancelar e vencer
{
  const r = await ia("POST", "/api/ia/assinatura/cancelar", null, segredo);
  const d = await corpoDe(r);
  checar(r.status === 200 && d.assinatura.situacao === "cancelled" && d.plano_vigente, "cancelar: o ciclo pago continua até o fim", d);
  relogio += 32 * 24 * 3600 * 1000;
  const c = await corpoDe(await ia("GET", "/api/ia/conta", null, segredo));
  checar(!c.plano_vigente && c.tokens.restantes === 0, "fim do ciclo sem assinatura: nada mais sai", c);
  const r2 = await ia("POST", "/api/ia/v1/chat/completions", pergunta, segredo);
  checar(r2.status === 402, "e o portão bloqueia");
  const r3 = await ia("POST", "/api/ia/recarga", { email: "dono@escritorio.com.br" }, segredo);
  checar(r3.status === 409, "recarga sem plano em dia é recusada");
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
  checar(f.conta.cortesia && f.conta.plano_vigente && f.conta.tokens.restantes === 10000, "o e-mail da cortesia tem o plano sem pagar", f.conta);
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

// ------------------------------------------------ aviso que não é da nuvem
{
  mpOrders.set("ORDAPOIO1", { id: "ORDAPOIO1", status: "processed", external_reference: "apoio-pix-abc", total_amount: "40.00" });
  const r = await worker.fetch(aviso("ORDAPOIO1", "order"), env, ctx);
  await Promise.all(pendentes.splice(0));
  checar(r.status === 200 && guardados.size === 0, "o aviso de um Pix que não é da nuvem (o antigo apoio) é aceito e ignorado");
}

// ------------------------------------------------ os planos e o cadastro pelo site
{
  donos["token-novo"] = { sub: "555", email: "nova@advocacia.com.br" };
  const planos = await corpoDe(await ia("GET", "/api/ia/planos"));
  checar(planos.planos.map((p) => p.id).join() === "advogado,escritorio,plus" && planos.planos[1].tokens === 10000,
    "três planos; o Escritório é o de antes (IA_PLANO_TOKENS)", planos.planos);

  let r = await ia("POST", "/api/ia/site/entrar", { id_token: "vencido" });
  checar(r.status === 401, "sem o Google confirmado, o site não entra");
  const entrou = await corpoDe(await ia("POST", "/api/ia/site/entrar", { id_token: "token-novo" }));
  checar(entrou.ok && entrou.email === "nova@advocacia.com.br" && entrou.cadastro === null && !entrou.plano_vigente && entrou.instalacoes === 0,
    "entrar pelo site abre a conta, sem cadastro, sem plano e sem instalação", entrou);

  const base = { id_token: "token-novo", nome_escritorio: "Nova Advocacia", documento: "529.982.247-25", telefone: "(91) 98888-7777",
    oab: "OAB/PA 12.345", aceite: true };
  const erro = async (mudanca) => (await corpoDe(await ia("POST", "/api/ia/site/cadastro", { ...base, ...mudanca }))).erro || "";
  checar((await erro({ documento: "111.111.111-11" })).includes("CPF ou CNPJ"), "CPF com dígito errado é recusado");
  checar((await erro({ telefone: "98888-7777" })).includes("DDD"), "telefone sem DDD é recusado");
  checar((await erro({ oab: "12345" })).includes("UF"), "OAB sem a UF é recusada");
  checar((await erro({ aceite: false })).includes("aceitar"), "sem aceitar os termos, não cadastra");
  checar((await erro({ plano: "ouro" })) === "esse plano não existe", "plano que não existe é recusado");

  const antes = mpPreapprovals.size;
  r = await ia("POST", "/api/ia/site/cadastro", { ...base, plano: "advogado" });
  const assinou = await corpoDe(r);
  const pre = [...mpPreapprovals.values()].at(-1);
  checar(r.status === 200 && assinou.link && mpPreapprovals.size === antes + 1 && pre.auto_recurring.transaction_amount === 150,
    "o cadastro com o plano Advogado cria a assinatura de R$ 150 no Mercado Pago", assinou);
  const pedidoMP = mpPedidos.filter((x) => x.caminho === "/preapproval" && x.metodo === "POST").at(-1).corpo;
  checar(pedidoMP.back_url === "https://paulus.ia.br/cadastro/?voltou=1" && pedidoMP.payer_email === "nova@advocacia.com.br",
    "quem assina pelo site volta para a página de cadastro; o recibo vai ao e-mail do Google", pedidoMP);

  pre.status = "authorized";
  const situacao = await corpoDe(await ia("POST", "/api/ia/site/situacao", { id_token: "token-novo" }));
  checar(situacao.plano_vigente && situacao.plano.id === "advogado" && situacao.ciclo.tokens === 12000000,
    "cartão aceito: o plano Advogado vale, com 12 milhões de tokens", { plano: situacao.plano, ciclo: situacao.ciclo });
  checar(situacao.cadastro && situacao.cadastro.documento === "52998224725" && situacao.cadastro.oab === "PA 12345" && situacao.nome === "Nova Advocacia",
    "o cadastro fica na conta, conferido e normalizado", situacao.cadastro);

  // Trocar de plano: o valor muda no Mercado Pago, os tokens na renovação.
  let troca = await ia("POST", "/api/ia/site/plano", { id_token: "token-novo", plano: "ouro" });
  checar(troca.status === 400, "trocar para plano que não existe é recusado");
  troca = await corpoDe(await ia("POST", "/api/ia/site/plano", { id_token: "token-novo", plano: "plus" }));
  checar(pre.auto_recurring.transaction_amount === 550 && troca.plano.id === "advogado" && troca.plano_proximo && troca.plano_proximo.id === "plus"
    && troca.ciclo.tokens === 12000000, "trocar para o Plus: o Mercado Pago cobra R$ 550, e o ciclo pago continua no Advogado",
    { valor: pre.auto_recurring.transaction_amount, plano: troca.plano, proximo: troca.plano_proximo });
  const desfeita = await corpoDe(await ia("POST", "/api/ia/site/plano", { id_token: "token-novo", plano: "advogado" }));
  checar(desfeita.plano_proximo === null && pre.auto_recurring.transaction_amount === 150, "pedir o plano de agora desfaz a troca");
  await ia("POST", "/api/ia/site/plano", { id_token: "token-novo", plano: "plus" });
  const contaNova = [...objetos.values()].find((x) => (x.dados.get("conta") || {}).dono?.sub === "555");
  relogio += 31 * 24 * 3600 * 1000;
  const renovada = contaNova.o.fazer("renovar", contaNova.dados.get("conta"), { cobranca: "cob-plus-1", quando: new Date(relogio).toISOString() }, (await import("./ia.js")).numeros(env))[0];
  checar(renovada.plano.id === "plus" && renovada.ciclo.tokens === 60000000 && renovada.plano_proximo === null,
    "na renovação, o Plus entra com 60 milhões de tokens", { plano: renovada.plano, ciclo: renovada.ciclo });
  relogio -= 31 * 24 * 3600 * 1000;

  // Depois, o PAULUS instalado entra com a mesma conta Google e já encontra o plano.
  const ativou = await corpoDe(await ia("POST", "/api/ia/ativar", { id_token: "token-novo", instalacao_id: "inst-nova-0001" }));
  const pacote = await corpoDe(await ia("POST", "/api/ia/recarga", { pacote: "2" }, ativou.segredo));
  checar(pacote.valor === "100.00" && pacote.tokens === 10000, "a recarga do dobro: R$ 100 pelo dobro de tokens", pacote);
  mpOrders.get(pacote.id).status = "processed";
  mpOrders.get(pacote.id).total_amount = "100.00";
  const creditada = await corpoDe(await ia("GET", "/api/ia/recarga/" + pacote.id, null, ativou.segredo));
  checar(creditada.pago && creditada.conta.recargas[0].tokens === 10000, "paga, entram os tokens do pacote", creditada.conta && creditada.conta.recargas);
  checar((await ia("POST", "/api/ia/recarga", { pacote: "7" }, ativou.segredo)).status === 400, "pacote que não existe é recusado");
  checar(ativou.conta.plano_vigente && ativou.conta.plano.id === "plus" && ativou.conta.instalacoes === 1,
    "o PAULUS instalado entra com a mesma conta e já tem o plano", ativou.conta);

  // Quem assinava antes dos três planos fica no Escritório.
  const { numeros } = await import("./ia.js");
  const medidorAntigo = objeto("conta-de-antes-dos-planos").o;
  const contaAntiga = { id: "x", segredos: [], extra: 0, reservas: {}, recargas: [], cobrancas: [], uso: [],
    assinatura: { id: "pre-velha", situacao: "authorized", valor: 300 } };
  medidorAntigo.abrirCiclo(contaAntiga, numeros(env), relogio, "assinatura");
  const resumoAntigo = medidorAntigo.resumo(contaAntiga, numeros(env), relogio);
  checar(resumoAntigo.plano.id === "escritorio" && contaAntiga.ciclo.tokens === 10000 && resumoAntigo.plano_vigente,
    "quem assinava antes dos três planos fica no Escritório, com os mesmos tokens", resumoAntigo.plano);
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
