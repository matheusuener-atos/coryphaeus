// A nuvem vendida do PAULUS (paulus/legal/docs/PLANO-NUVEM.md, V2 e V3): o
// portao entre o PAULUS de cada escritorio e o DeepInfra, com o medidor de
// tokens e a cobranca.
//
// A chave do DeepInfra so existe aqui, como segredo do Worker
// (npx wrangler secret put DEEPINFRA_KEY) - nunca no PAULUS instalado, onde
// qualquer um a tiraria do instalador. Pelo mesmo motivo a cota e contada
// aqui: num arquivo do computador do escritorio ela nao bloquearia nada.
//
// O que passa por aqui e o texto da pergunta e da resposta, de ida e volta ao
// DeepInfra. Nada e guardado: o medidor anota so numeros (tokens, datas, ids
// do Mercado Pago). O registro do que saiu fica no computador do escritorio.
//
//   POST /api/ia/ativar            com o id_token do Google: a conta (uma por
//                                  conta Google) e o segredo desta instalacao
//   GET  /api/ia/conta             plano, ciclo, tokens usados e restantes
//   POST /api/ia/consentimento     o sim do titular (versao do termo), ou o nao
//   GET  /api/ia/modelos           os modelos que o portao aceita
//   POST /api/ia/v1/chat/completions  o formato OpenAI; vai ao DeepInfra
//   POST /api/ia/assinar           a assinatura mensal (link do Mercado Pago)
//   GET  /api/ia/assinatura        a situacao, conferida no Mercado Pago
//   POST /api/ia/assinatura/cancelar
//   POST /api/ia/recarga           o Pix da recarga (QR)
//   GET  /api/ia/recarga/:id       pago? se sim, os tokens entram
//   POST /api/ia/sair              apaga o segredo desta instalacao
//
// Todas, menos ativar, com o segredo da instalacao (Authorization: Bearer
// pia_<conta>_<64 hex>). A conta vem escrita no segredo; quem confere e o
// medidor dela, que guarda so o resumo SHA-256.
//
// O medidor e um Durable Object por conta (ContaIA): os pedidos de uma conta
// passam um de cada vez, e duas perguntas ao mesmo tempo nao gastam as duas o
// ultimo saldo. Cada chamada RESERVA o teto (entrada estimada + saida maxima)
// antes de sair e, quando o DeepInfra diz quanto gastou, LIQUIDA pelo real.
//
// Tudo atras de IA_ATIVA === "1", do binding CONTAS_IA e da chave
// DEEPINFRA_KEY: sem os tres, as rotas respondem 404 (ou 503, sem a chave).

import { donoDoToken } from "./tunel.js";

const DEEPINFRA = "https://api.deepinfra.com/v1/openai/chat/completions";
const RE_SEGREDO = /^pia_([0-9a-f]{24})_([0-9a-f]{64})$/;
const MAX_SEGREDOS = 3;
// Reserva sem liquidar (o Worker caiu no meio): depois disto, conta inteira.
const RESERVA_VENCE_MS = 15 * 60 * 1000;
// Depois do fim do ciclo, com a assinatura ativa, a cobranca do mes pode
// atrasar uns dias no Mercado Pago: o plano continua valendo nesse intervalo.
const TOLERANCIA_MS = 5 * 24 * 3600 * 1000;
// Portugues tem ~4 caracteres por token; 3 estima para cima (a reserva e teto).
const CARACTERES_POR_TOKEN = 3;

export function numeros(env) {
  const n = (v, padrao) => (Number.isFinite(Number(v)) && Number(v) > 0 ? Number(v) : padrao);
  return {
    planoValor: n(env.IA_PLANO_VALOR, 300),
    planoTokens: n(env.IA_PLANO_TOKENS, 30000000),
    recargaValor: n(env.IA_RECARGA_VALOR, 50),
    recargaTokens: n(env.IA_RECARGA_TOKENS, 10000000),
    maxSaida: n(env.IA_MAX_SAIDA, 4000),
    maxEntradaCaracteres: n(env.IA_MAX_ENTRADA_CARACTERES, 240000),
    porMinuto: n(env.IA_POR_MINUTO, 40),
    modelos: String(env.IA_MODELOS || "meta-llama/Llama-3.3-70B-Instruct,Qwen/Qwen2.5-72B-Instruct")
      .split(",").map((m) => m.trim()).filter(Boolean),
  };
}

// ------------------------------------------------------------- entrada

export function ehRotaDaIA(url) {
  return url.pathname.startsWith("/api/ia/");
}

export async function atenderIA(request, env, url, ctx, deps = {}) {
  if (env.IA_ATIVA !== "1" || !env.CONTAS_IA) return json({ erro: "rota não existe" }, 404);
  const p = url.pathname;
  const m = request.method;
  const limitado = async () => Boolean(deps.dentroDoLimite) && !(await deps.dentroDoLimite(request, env));
  if (p === "/api/ia/ativar" && m === "POST") {
    if (await limitado()) return json({ erro: "muitas tentativas seguidas - espere um minuto" }, 429);
    return ativar(request, env, deps);
  }
  const quem = await autenticar(request, env);
  if (quem.erro) return json({ erro: quem.erro }, quem.status);
  const conta = quem.conta;
  if (p === "/api/ia/conta" && m === "GET") return json(await conta.pedir("resumo"));
  if (p === "/api/ia/modelos" && m === "GET") return json({ modelos: numeros(env).modelos });
  if (p === "/api/ia/consentimento" && m === "POST") {
    const d = (await lerJSON(request)) || {};
    const versao = String(d.versao || "").slice(0, 40);
    const pessoa = String(d.quem || "").replace(/[\u0000-\u001f<>]/g, "").slice(0, 80);
    if (d.aceito && !versao) return json({ erro: "diga a versão do termo" }, 400);
    return json(await conta.pedir(d.aceito ? "consentir" : "retirar", { versao, quem: pessoa }));
  }
  if (p === "/api/ia/v1/chat/completions" && m === "POST") return completar(request, env, ctx, conta);
  if (p === "/api/ia/sair" && m === "POST") return json(await conta.pedir("sair", { hash: quem.hash }));
  const mp = deps.chamarMP;
  if (p === "/api/ia/assinar" && m === "POST") {
    if (await limitado()) return json({ erro: "muitas tentativas seguidas - espere um minuto" }, 429);
    return assinar(request, env, conta, quem.id, mp);
  }
  if (p === "/api/ia/assinatura" && m === "GET") return situacaoDaAssinatura(env, conta, mp);
  if (p === "/api/ia/assinatura/cancelar" && m === "POST") return cancelar(env, conta, mp);
  if (p === "/api/ia/recarga" && m === "POST") {
    if (await limitado()) return json({ erro: "muitas tentativas seguidas - espere um minuto" }, 429);
    return criarRecarga(request, env, conta, quem.id, mp);
  }
  const rec = p.match(/^\/api\/ia\/recarga\/([A-Za-z0-9_-]{6,64})$/);
  if (rec && m === "GET") return situacaoDaRecarga(env, conta, quem.id, rec[1], mp);
  return json({ erro: "rota não existe" }, 404);
}

// ------------------------------------------------------------ utilidades

function json(dados, status = 200) {
  return new Response(JSON.stringify(dados), {
    status,
    headers: { "content-type": "application/json; charset=utf-8", "cache-control": "no-store" },
  });
}

async function lerJSON(request) {
  try {
    return await request.json();
  } catch {
    return null;
  }
}

async function sha256(texto) {
  const r = await crypto.subtle.digest("SHA-256", new TextEncoder().encode(String(texto)));
  return [...new Uint8Array(r)].map((b) => b.toString(16).padStart(2, "0")).join("");
}

function aleatorio(n) {
  const b = new Uint8Array(n);
  crypto.getRandomValues(b);
  return [...b].map((x) => x.toString(16).padStart(2, "0")).join("");
}

/* O medidor de uma conta: cada pedido e um POST com {acao, ...}. */
export function medidor(env, id) {
  const stub = env.CONTAS_IA.get(env.CONTAS_IA.idFromName(id));
  return {
    async pedir(acao, dados = {}) {
      const r = await stub.fetch("https://conta-ia/" + acao, { method: "POST", body: JSON.stringify({ acao, ...dados, numeros: numeros(env) }) });
      return r.json();
    },
  };
}

async function autenticar(request, env) {
  const cab = request.headers.get("authorization") || "";
  const segredo = cab.startsWith("Bearer ") ? cab.slice(7).trim() : "";
  const m = segredo.match(RE_SEGREDO);
  if (!m) return { erro: "não autorizado", status: 401 };
  const hash = await sha256(segredo);
  const conta = medidor(env, m[1]);
  const r = await conta.pedir("conferir", { hash });
  if (!r.ok) return { erro: "não autorizado", status: 401 };
  return { conta, id: m[1], hash };
}

// ---------------------------------------------------------------- ativar

async function ativar(request, env, deps) {
  const d = await lerJSON(request);
  if (!d) return json({ erro: "pedido inválido" }, 400);
  const instalacao = String(d.instalacao_id || "");
  if (!/^[A-Za-z0-9-]{8,64}$/.test(instalacao)) return json({ erro: "instalação inválida" }, 400);
  const dono = await (deps.donoDoToken || donoDoToken)(env, d.id_token);
  if (!dono) return json({ erro: "a confirmação do Google venceu: entre com o Google de novo" }, 401);
  const id = (await sha256("conta-ia:" + dono.sub)).slice(0, 24);
  const segredo = "pia_" + id + "_" + aleatorio(32);
  const cortesias = String(env.IA_CORTESIA || "").split(",").map((x) => x.trim().toLowerCase()).filter(Boolean);
  const cortesia = cortesias.includes(await sha256(dono.email));
  const nome = String(d.nome_escritorio || "").replace(/[\u0000-\u001f<>]/g, "").replace(/\s+/g, " ").trim().slice(0, 80);
  const resumo = await medidor(env, id).pedir("ativar", { id, dono, nome, instalacao, hash: await sha256(segredo), cortesia });
  return json({ segredo, conta: resumo });
}

// ------------------------------------------------------- o portao

function caracteres(mensagens) {
  let n = 0;
  for (const m of mensagens) n += String((m && m.content) || "").length;
  return n;
}

/* As ultimas linhas "data:" da resposta: o DeepInfra manda o uso no fim. */
export function usoDoFim(cauda) {
  const linhas = String(cauda || "").split("\n");
  for (let i = linhas.length - 1; i >= 0; i--) {
    const l = linhas[i].trim();
    if (!l.startsWith("data:") || !l.includes('"usage"')) continue;
    try {
      const u = JSON.parse(l.slice(5).trim()).usage;
      if (u && Number.isFinite(Number(u.prompt_tokens))) {
        return { entrada: Number(u.prompt_tokens) || 0, saida: Number(u.completion_tokens) || 0 };
      }
    } catch {
      continue;
    }
  }
  return null;
}

async function completar(request, env, ctx, conta) {
  if (!env.DEEPINFRA_KEY) return json({ erro: "a nuvem do PAULUS ainda não está no ar" }, 503);
  const n = numeros(env);
  const d = await lerJSON(request);
  if (!d || !Array.isArray(d.messages) || !d.messages.length) return json({ erro: "pedido inválido" }, 400);
  const modelo = String(d.model || n.modelos[0] || "");
  if (!n.modelos.includes(modelo)) return json({ erro: "esse modelo não está na nuvem do PAULUS", modelos: n.modelos }, 400);
  const mensagens = d.messages
    .filter((x) => x && ["system", "user", "assistant"].includes(x.role))
    .map((x) => ({ role: x.role, content: String(x.content || "") }));
  const tamanho = caracteres(mensagens);
  if (tamanho > n.maxEntradaCaracteres) {
    return json({ erro: "o texto passa do teto de um pedido; mande menos trechos", teto: n.maxEntradaCaracteres }, 413);
  }
  const entrada = Math.ceil(tamanho / CARACTERES_POR_TOKEN) + 16 * mensagens.length;
  const pedida = Math.min(Math.max(Number(d.max_tokens) || n.maxSaida, 1), n.maxSaida);
  const reserva = await conta.pedir("reservar", { entrada, saida: pedida });
  if (!reserva.ok) return json({ erro: reserva.erro, motivo: reserva.motivo, conta: reserva.conta }, reserva.status || 402);

  const stream = d.stream !== false;
  const corpo = { model: modelo, messages: mensagens, max_tokens: reserva.saida, stream };
  if (stream) corpo.stream_options = { include_usage: true };
  for (const k of ["temperature", "top_p"]) if (Number.isFinite(Number(d[k]))) corpo[k] = Number(d[k]);
  if (d.response_format && d.response_format.type === "json_object") corpo.response_format = { type: "json_object" };

  let up;
  try {
    up = await fetch(DEEPINFRA, {
      method: "POST",
      headers: { Authorization: "Bearer " + env.DEEPINFRA_KEY, "Content-Type": "application/json" },
      body: JSON.stringify(corpo),
    });
  } catch (e) {
    await conta.pedir("liquidar", { reserva: reserva.id, tokens: 0 });
    return json({ erro: "o provedor do modelo não respondeu" }, 502);
  }
  if (!up.ok) {
    await conta.pedir("liquidar", { reserva: reserva.id, tokens: 0 });
    let msg = "";
    try {
      const e = await up.json();
      msg = String((e.error && (e.error.message || e.error)) || e.detail || "").slice(0, 160);
    } catch {
      msg = "";
    }
    return json({ erro: "o provedor do modelo recusou" + (msg ? ": " + msg : ""), status_provedor: up.status }, up.status >= 500 ? 502 : 400);
  }

  if (!stream) {
    const dado = await up.json();
    const u = dado.usage || {};
    const real = (Number(u.prompt_tokens) || entrada) + (Number(u.completion_tokens) || 0);
    const fim = await conta.pedir("liquidar", { reserva: reserva.id, tokens: real });
    dado.paulus = { tokens: real, restantes: fim.restantes };
    return json(dado);
  }

  // Passa os pedacos como vieram. No fim (ou se o PAULUS fechar no meio, o
  // "parar" da conversa), liquida pelo uso que o DeepInfra mandou; sem ele,
  // pela entrada estimada e um token por pedaco.
  const leitor = up.body.getReader();
  const dec = new TextDecoder();
  let cauda = "";
  let pedacos = 0;
  let liquidado = false;
  let avisar;
  const terminou = new Promise((r) => { avisar = r; });
  if (ctx && ctx.waitUntil) ctx.waitUntil(terminou);
  const liquidar = async () => {
    if (liquidado) return;
    liquidado = true;
    const u = usoDoFim(cauda);
    const real = u ? u.entrada + u.saida : entrada + pedacos;
    try {
      await conta.pedir("liquidar", { reserva: reserva.id, tokens: real });
    } finally {
      avisar();
    }
  };
  const saida = new ReadableStream({
    async pull(controle) {
      let lido;
      try {
        lido = await leitor.read();
      } catch (e) {
        controle.error(e);
        await liquidar();
        return;
      }
      if (lido.done) {
        controle.close();
        await liquidar();
        return;
      }
      const texto = dec.decode(lido.value, { stream: true });
      let i = -1;
      while ((i = texto.indexOf("data:", i + 1)) !== -1) pedacos++;
      cauda = (cauda + texto).slice(-6000);
      controle.enqueue(lido.value);
    },
    async cancel(motivo) {
      try {
        await leitor.cancel(motivo);
      } catch {
        // o DeepInfra ja tinha fechado
      }
      await liquidar();
    },
  });
  return new Response(saida, { status: 200, headers: { "content-type": "text/event-stream; charset=utf-8", "cache-control": "no-store" } });
}

// ------------------------------------------------------------- cobranca

async function assinar(request, env, conta, id, mp) {
  const d = (await lerJSON(request)) || {};
  const atual = await conta.pedir("resumo");
  // Sem e-mail no pedido, o da conta Google da nuvem (o pagador recebe o recibo nele).
  const email = String(d.email || atual.email || "").trim().toLowerCase();
  if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email) || email.length > 120) return json({ erro: "e-mail inválido" }, 400);
  if (atual.assinatura && atual.assinatura.situacao === "authorized") return json({ erro: "a assinatura já está ativa" }, 409);
  const n = numeros(env);
  const r = await mp(env, "/preapproval", "POST", {
    reason: "PAULUS na nuvem - plano mensal",
    external_reference: "ia-assinatura-" + id,
    payer_email: email,
    auto_recurring: { frequency: 1, frequency_type: "months", transaction_amount: n.planoValor, currency_id: "BRL" },
    back_url: "https://paulus.ia.br/",
    status: "pending",
  });
  if (!r.ok) return json({ erro: "o Mercado Pago recusou criar a assinatura", status: r.status }, 502);
  await conta.pedir("assinatura", { assinatura: { id: String(r.dados.id), situacao: r.dados.status || "pending", valor: n.planoValor } });
  return json({ id: r.dados.id, situacao: r.dados.status, link: r.dados.init_point || "" });
}

async function situacaoDaAssinatura(env, conta, mp) {
  const atual = await conta.pedir("resumo");
  const a = atual.assinatura;
  if (!a || !a.id) return json(atual);
  const r = await mp(env, "/preapproval/" + encodeURIComponent(a.id), "GET");
  if (r.ok && r.dados && r.dados.status && r.dados.status !== a.situacao) {
    return json(await conta.pedir("assinatura", { assinatura: { ...a, situacao: r.dados.status } }));
  }
  return json(atual);
}

async function cancelar(env, conta, mp) {
  const atual = await conta.pedir("resumo");
  const a = atual.assinatura;
  if (!a || !a.id || a.situacao === "cancelled") return json({ erro: "não há assinatura ativa" }, 409);
  const r = await mp(env, "/preapproval/" + encodeURIComponent(a.id), "PUT", { status: "cancelled" });
  if (!r.ok) return json({ erro: "o Mercado Pago recusou cancelar", status: r.status }, 502);
  return json(await conta.pedir("assinatura", { assinatura: { ...a, situacao: "cancelled" } }));
}

async function criarRecarga(request, env, conta, id, mp) {
  const d = (await lerJSON(request)) || {};
  const atual = await conta.pedir("resumo");
  // Sem e-mail no pedido, o da conta Google da nuvem (o pagador recebe o recibo nele).
  const email = String(d.email || atual.email || "").trim().toLowerCase();
  if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email) || email.length > 120) return json({ erro: "e-mail inválido" }, 400);
  if (!atual.plano_vigente) return json({ erro: "a recarga é para quem tem o plano em dia: assine antes" }, 409);
  const n = numeros(env);
  const valor = n.recargaValor.toFixed(2);
  const r = await mp(env, "/v1/orders", "POST", {
    type: "online",
    total_amount: valor,
    external_reference: "ia-recarga-" + id + "-" + aleatorio(6),
    processing_mode: "automatic",
    transactions: { payments: [{ amount: valor, payment_method: { id: "pix", type: "bank_transfer" }, expiration_time: "PT30M" }] },
    payer: { email },
  });
  if (!r.ok) return json({ erro: "o Mercado Pago recusou criar o Pix", status: r.status }, 502);
  const pagamento = ((r.dados.transactions || {}).payments || [])[0] || {};
  const meio = pagamento.payment_method || {};
  return json({
    id: r.dados.id, valor, tokens: n.recargaTokens, vence_em_minutos: 30,
    qr_code: meio.qr_code || "", qr_code_base64: meio.qr_code_base64 || "", ticket_url: meio.ticket_url || "",
  });
}

async function situacaoDaRecarga(env, conta, id, pedido, mp) {
  const r = await mp(env, "/v1/orders/" + encodeURIComponent(pedido), "GET");
  if (!r.ok) return json({ erro: "não achei esse Pix", status: r.status }, r.status === 404 ? 404 : 502);
  const ref = String(r.dados.external_reference || "");
  if (!ref.startsWith("ia-recarga-" + id + "-")) return json({ erro: "esse Pix não é desta conta" }, 403);
  const pago = r.dados.status === "processed";
  if (!pago) return json({ id: pedido, pago: false, situacao: r.dados.status });
  const feito = await conta.pedir("creditar", { pedido, valor: Number(r.dados.total_amount) || 0 });
  return json({ id: pedido, pago: true, conta: feito });
}

/* O aviso do Mercado Pago (worker/index.js, registrarAviso) que e da nuvem:
   true quando tratou (e o apoio nao deve contar), false quando nao e daqui. */
export async function avisoDaIA(env, tipo, dados, mp) {
  if (!env.CONTAS_IA) return false;
  const ref = String((dados && dados.external_reference) || "");
  if (tipo === "order") {
    const m = ref.match(/^ia-recarga-([0-9a-f]{24})-/);
    if (!m) return false;
    if (dados.status === "processed") await medidor(env, m[1]).pedir("creditar", { pedido: String(dados.id), valor: Number(dados.total_amount) || 0 });
    return true;
  }
  if (tipo === "preapproval") {
    const m = ref.match(/^ia-assinatura-([0-9a-f]{24})$/);
    if (!m) return false;
    await medidor(env, m[1]).pedir("assinatura", { assinatura: { id: String(dados.id), situacao: dados.status, valor: (dados.auto_recurring || {}).transaction_amount } });
    return true;
  }
  if (tipo === "cobranca") {
    // A cobranca mensal so traz o id da assinatura: a referencia vem dela.
    const pre = await mp(env, "/preapproval/" + encodeURIComponent(dados.preapproval_id || ""), "GET");
    const m = String((pre.ok && pre.dados && pre.dados.external_reference) || "").match(/^ia-assinatura-([0-9a-f]{24})$/);
    if (!m) return false;
    const pagamento = dados.payment || {};
    if (pagamento.status === "approved" && dados.id) {
      await medidor(env, m[1]).pedir("renovar", { cobranca: String(dados.id), quando: dados.debit_date || dados.date_created || "" });
    }
    return true;
  }
  return false;
}

// ------------------------------------------------------------- o medidor

function maisUmMes(ms) {
  const d = new Date(ms);
  const dia = d.getUTCDate();
  d.setUTCMonth(d.getUTCMonth() + 1);
  // 31/01 + 1 mes = 28/02, e nao 03/03.
  if (d.getUTCDate() < dia) d.setUTCDate(0);
  return d.getTime();
}

export class ContaIA {
  constructor(state, env) {
    this.state = state;
    this.env = env;
    this.agora = () => Date.now();
  }

  async fetch(request) {
    const d = await request.json();
    const c = (await this.state.storage.get("conta")) || null;
    const [resposta, nova] = this.fazer(d.acao, c, d, d.numeros || numeros(this.env || {}));
    if (nova) await this.state.storage.put("conta", nova);
    return new Response(JSON.stringify(resposta), { headers: { "content-type": "application/json" } });
  }

  /* -> [resposta, conta nova (ou null se nada mudou)]. Sem I/O: o teste chama direto. */
  fazer(acao, c, d, n) {
    const agora = this.agora();
    if (acao === "ativar") {
      const conta = c || { id: d.id, criada: new Date(agora).toISOString(), segredos: [], extra: 0, reservas: {}, recargas: [], cobrancas: [], uso: [] };
      conta.dono = d.dono;
      conta.nome = d.nome || conta.nome || "";
      conta.cortesia = Boolean(d.cortesia);
      // Uma instalacao, um segredo: ativar de novo troca o dela; no maximo tres.
      conta.segredos = (conta.segredos || []).filter((s) => s.instalacao !== d.instalacao);
      conta.segredos.push({ hash: d.hash, instalacao: d.instalacao, criado: new Date(agora).toISOString() });
      conta.segredos = conta.segredos.slice(-MAX_SEGREDOS);
      this.vigente(conta, n, agora);
      return [this.resumo(conta, n, agora), conta];
    }
    if (!c) return [{ ok: false, erro: "conta não existe", status: 401 }, null];
    const conta = c;
    this.limparReservas(conta, agora);
    if (acao === "conferir") {
      const ok = (conta.segredos || []).some((s) => s.hash === d.hash);
      return [{ ok }, null];
    }
    if (acao === "resumo") return [this.resumo(conta, n, agora), conta];
    if (acao === "sair") {
      conta.segredos = (conta.segredos || []).filter((s) => s.hash !== d.hash);
      return [{ ok: true }, conta];
    }
    if (acao === "consentir") {
      conta.consentimento = { versao: d.versao, quem: d.quem || "", quando: new Date(agora).toISOString() };
      return [this.resumo(conta, n, agora), conta];
    }
    if (acao === "retirar") {
      conta.consentimento = null;
      return [this.resumo(conta, n, agora), conta];
    }
    if (acao === "reservar") return this.reservar(conta, d, n, agora);
    if (acao === "liquidar") {
      const r = (conta.reservas || {})[d.reserva];
      if (!r) return [{ ok: false, restantes: this.restantes(conta, n, agora) }, null];
      delete conta.reservas[d.reserva];
      this.gastar(conta, Math.max(0, Math.round(Number(d.tokens) || 0)));
      return [{ ok: true, restantes: this.restantes(conta, n, agora) }, conta];
    }
    if (acao === "assinatura") {
      const antes = conta.assinatura || {};
      conta.assinatura = { ...antes, ...d.assinatura, desde: antes.desde || new Date(agora).toISOString() };
      // Cartao posto e aceito: o primeiro ciclo comeca agora; a cobranca do
      // Mercado Pago, que vem em seguida, so confirma (renovar e idempotente).
      if (conta.assinatura.situacao === "authorized" && !this.cicloAberto(conta, agora)) this.abrirCiclo(conta, n, agora, "assinatura");
      return [this.resumo(conta, n, agora), conta];
    }
    if (acao === "renovar") {
      conta.cobrancas = conta.cobrancas || [];
      if (conta.cobrancas.includes(d.cobranca)) return [this.resumo(conta, n, agora), null];
      conta.cobrancas = [...conta.cobrancas, d.cobranca].slice(-36);
      const quando = Date.parse(d.quando || "") || agora;
      // A primeira cobranca logo depois da assinatura e a do ciclo que acabou
      // de abrir; as outras abrem o ciclo seguinte.
      const aberto = this.cicloAberto(conta, agora);
      if (aberto && aberto.origem === "assinatura" && !aberto.cobranca && quando - Date.parse(aberto.inicio) < 3 * 24 * 3600 * 1000) {
        aberto.cobranca = d.cobranca;
      } else {
        this.abrirCiclo(conta, n, Math.min(quando, agora), "cobranca", d.cobranca);
      }
      return [this.resumo(conta, n, agora), conta];
    }
    if (acao === "creditar") {
      conta.recargas = conta.recargas || [];
      if (conta.recargas.some((r) => r.pedido === d.pedido)) return [this.resumo(conta, n, agora), null];
      conta.extra = (conta.extra || 0) + n.recargaTokens;
      conta.recargas = [...conta.recargas, { pedido: d.pedido, tokens: n.recargaTokens, valor: d.valor, quando: new Date(agora).toISOString() }].slice(-50);
      return [this.resumo(conta, n, agora), conta];
    }
    return [{ ok: false, erro: "ação desconhecida", status: 400 }, null];
  }

  cicloAberto(conta, agora) {
    const c = conta.ciclo;
    return c && Date.parse(c.fim) > agora ? c : null;
  }

  abrirCiclo(conta, n, inicio, origem, cobranca = "") {
    conta.ciclo = { inicio: new Date(inicio).toISOString(), fim: new Date(maisUmMes(inicio)).toISOString(), tokens: n.planoTokens, usados: 0, origem };
    if (cobranca) conta.ciclo.cobranca = cobranca;
  }

  /* O plano vale agora? A cortesia abre o ciclo do mes sozinha. */
  vigente(conta, n, agora) {
    if (conta.cortesia && !this.cicloAberto(conta, agora)) this.abrirCiclo(conta, n, agora, "cortesia");
    const c = conta.ciclo;
    if (!c) return false;
    const fim = Date.parse(c.fim);
    if (fim > agora) return true;
    const a = conta.assinatura || {};
    return a.situacao === "authorized" && agora < fim + TOLERANCIA_MS;
  }

  reservado(conta) {
    return Object.values(conta.reservas || {}).reduce((s, r) => s + r.tokens, 0);
  }

  restantes(conta, n, agora) {
    if (!this.vigente(conta, n, agora)) return 0;
    const c = conta.ciclo;
    return Math.max(0, c.tokens - c.usados) + (conta.extra || 0) - this.reservado(conta);
  }

  /* Do ciclo primeiro; o que passar, da recarga. */
  gastar(conta, tokens) {
    const c = conta.ciclo || { tokens: 0, usados: 0 };
    const doCiclo = Math.min(tokens, Math.max(0, c.tokens - c.usados));
    c.usados += doCiclo;
    const resto = tokens - doCiclo;
    const daRecarga = Math.min(resto, conta.extra || 0);
    conta.extra = (conta.extra || 0) - daRecarga;
    // Passou do que havia (a entrada real maior que a estimada): fica no ciclo.
    c.usados += resto - daRecarga;
    if (conta.ciclo) conta.ciclo = c;
    // O uso de cada dia, para a tela dizer "hoje" e "nos ultimos 7 dias".
    const dia = new Date(this.agora() - 3 * 3600 * 1000).toISOString().slice(0, 10);
    conta.uso = conta.uso || [];
    const ultimo = conta.uso[conta.uso.length - 1];
    if (ultimo && ultimo.dia === dia) ultimo.tokens += tokens;
    else conta.uso = [...conta.uso, { dia, tokens }].slice(-62);
  }

  limparReservas(conta, agora) {
    for (const [id, r] of Object.entries(conta.reservas || {})) {
      if (agora - r.quando > RESERVA_VENCE_MS) {
        delete conta.reservas[id];
        this.gastar(conta, r.tokens);
      }
    }
  }

  reservar(conta, d, n, agora) {
    const negar = (status, motivo, erro) => [{ ok: false, status, motivo, erro, conta: this.resumo(conta, n, agora) }, conta];
    if (!conta.consentimento) return negar(403, "consentimento", "o titular ainda não deu o sim para a nuvem");
    if (!this.vigente(conta, n, agora)) return negar(402, "sem_plano", "o plano da nuvem não está em dia");
    // O teto por minuto: um laco que dispara pedidos para no medidor.
    const minuto = Math.floor(agora / 60000);
    if (!conta.janela || conta.janela.minuto !== minuto) conta.janela = { minuto, n: 0 };
    if (conta.janela.n >= n.porMinuto) return negar(429, "por_minuto", "muitos pedidos neste minuto; espere um pouco");
    const livres = this.restantes(conta, n, agora);
    const entrada = Math.max(1, Math.round(Number(d.entrada) || 0));
    // Saldo curto: a saida encolhe para caber; menos de 256 tokens de folga, para.
    const saida = Math.min(Math.round(Number(d.saida) || n.maxSaida), livres - entrada);
    if (saida < 256) return negar(402, "cota", "os tokens deste ciclo acabaram");
    conta.janela.n++;
    const id = aleatorio(8);
    conta.reservas = conta.reservas || {};
    conta.reservas[id] = { tokens: entrada + saida, quando: agora };
    return [{ ok: true, id, saida }, conta];
  }

  resumo(conta, n, agora) {
    const vigente = this.vigente(conta, n, agora);
    const c = conta.ciclo;
    const a = conta.assinatura || null;
    const doCiclo = c && vigente ? Math.max(0, c.tokens - c.usados) : 0;
    const hoje = new Date(agora - 3 * 3600 * 1000).toISOString().slice(0, 10);
    return {
      ok: true,
      conta: conta.id,
      email: (conta.dono || {}).email || "",
      nome: conta.nome || "",
      cortesia: Boolean(conta.cortesia),
      consentimento: conta.consentimento || null,
      assinatura: a ? { id: a.id, situacao: a.situacao, valor: a.valor, desde: a.desde } : null,
      plano_vigente: vigente,
      plano: { valor: n.planoValor, tokens: n.planoTokens },
      recarga: { valor: n.recargaValor, tokens: n.recargaTokens },
      ciclo: c ? { inicio: c.inicio, fim: c.fim, tokens: c.tokens, usados: c.usados, origem: c.origem } : null,
      tokens: {
        do_ciclo: doCiclo,
        da_recarga: vigente ? conta.extra || 0 : 0,
        reservados: this.reservado(conta),
        restantes: this.restantes(conta, n, agora),
        hoje: ((conta.uso || []).find((u) => u.dia === hoje) || {}).tokens || 0,
      },
      recargas: (conta.recargas || []).slice(-10).reverse(),
      instalacoes: (conta.segredos || []).length,
    };
  }
}
