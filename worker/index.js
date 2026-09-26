// O Worker do paulus.ia.br: o site (pasta site/) e as rotas de pagamento
// do "Apoiar o projeto" no Mercado Pago.
//
// O Access Token do Mercado Pago so existe aqui, como segredo do Worker
// (npx wrangler secret put MP_ACCESS_TOKEN) - nunca no programa que roda na
// maquina de cada usuario, onde qualquer um poderia le-lo.
//
//   POST /api/mp/pix          cria o Pix (Orders API) e devolve o QR
//   GET  /api/mp/pix/:id      a situacao do Pix (pago ou nao)
//   POST /api/mp/assinatura   cria a assinatura no cartao e devolve o link
//                             da pagina do Mercado Pago onde se poe o cartao
//   GET  /api/mp/assinatura/:id  se a assinatura ja foi ativada (cartao posto)
//   POST /api/mp/assinatura/:id/valor        muda o valor mensal  } so com a
//   POST /api/mp/assinatura/:id/interromper  cancela a assinatura } chave dela
//   POST /api/mp/assinatura/:id/pagamentos   as cobrancas mensais }
//   POST /api/mp/aviso        o webhook do Mercado Pago (assinatura conferida)
//
// O que o webhook confirma fica no KV APOIOS (so situacao, valor e data): o
// Pix pago depois de fechado o pop-up e a assinatura concluida no navegador
// aparecem para o programa na proxima consulta. As rotas que criam cobranca
// passam pelo limite LIMITE (10 por minuto por endereco de internet).
//
// Todo o resto e o site estatico.

// Guardado por pouco mais de um ano.
const KV_VALIDADE_S = 400 * 24 * 60 * 60;

const MP = "https://api.mercadopago.com";
const VALOR_MINIMO = 5;
const VALOR_MAXIMO = 50000;
const RE_EMAIL = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
// O aviso do Mercado Pago mais velho que isto e recusado (repeticao).
const AVISO_VALIDADE_MS = 10 * 60 * 1000;

export default {
  async fetch(request, env, ctx) {
    const url = new URL(request.url);
    if (!url.pathname.startsWith("/api/")) return env.ASSETS.fetch(request);
    try {
      const criando = request.method === "POST" && (url.pathname === "/api/mp/pix" || url.pathname === "/api/mp/assinatura");
      if (criando && !(await dentroDoLimite(request, env))) return json({ erro: "muitas tentativas seguidas - espere um minuto" }, 429);
      if (url.pathname === "/api/mp/pix" && request.method === "POST") return await criarPix(request, env);
      const pix = url.pathname.match(/^\/api\/mp\/pix\/([A-Za-z0-9_-]{6,64})$/);
      if (pix && request.method === "GET") return await situacaoDoPix(pix[1], env);
      if (url.pathname === "/api/mp/assinatura" && request.method === "POST") return await criarAssinatura(request, env);
      const ass = url.pathname.match(/^\/api\/mp\/assinatura\/([A-Za-z0-9_-]{6,64})$/);
      if (ass && request.method === "GET") return await situacaoDaAssinatura(ass[1], env);
      const mudar = url.pathname.match(/^\/api\/mp\/assinatura\/([A-Za-z0-9_-]{6,64})\/(valor|interromper|pagamentos)$/);
      if (mudar && request.method === "POST") {
        if (!(await dentroDoLimite(request, env))) return json({ erro: "muitas tentativas seguidas - espere um minuto" }, 429);
        if (mudar[2] === "pagamentos") return await pagamentosDaAssinatura(mudar[1], request, env);
        return mudar[2] === "valor" ? await mudarValor(mudar[1], request, env) : await interromper(mudar[1], request, env);
      }
      if (url.pathname === "/api/mp/aviso" && request.method === "POST") return await receberAviso(request, url, env, ctx);
      return json({ erro: "rota não existe" }, 404);
    } catch (erro) {
      return json({ erro: "falha no servidor de pagamento" }, 500);
    }
  },
};

function json(dados, status = 200) {
  return new Response(JSON.stringify(dados), {
    status,
    headers: { "content-type": "application/json; charset=utf-8", "cache-control": "no-store" },
  });
}

async function dentroDoLimite(request, env) {
  if (!env.LIMITE) return true;
  const chave = request.headers.get("cf-connecting-ip") || "sem-ip";
  const { success } = await env.LIMITE.limit({ key: chave });
  return success;
}

async function guardar(env, chave, dados) {
  if (!env.APOIOS) return;
  await env.APOIOS.put(chave, JSON.stringify({ ...dados, quando: new Date().toISOString() }), { expirationTtl: KV_VALIDADE_S });
}

async function lerGuardado(env, chave) {
  if (!env.APOIOS) return null;
  const bruto = await env.APOIOS.get(chave);
  try {
    return bruto ? JSON.parse(bruto) : null;
  } catch {
    return null;
  }
}

async function lerPedido(request) {
  try {
    return await request.json();
  } catch {
    return null;
  }
}

/* O valor e o e-mail que chegam do programa: conferidos aqui, porque a rota
   e publica - quem chamar direto nao escolhe valor fora da faixa. */
function conferir(pedido) {
  const valor = Math.round(Number(pedido && pedido.valor) * 100) / 100;
  const email = String((pedido && pedido.email) || "").trim().toLowerCase();
  if (!Number.isFinite(valor) || valor < VALOR_MINIMO || valor > VALOR_MAXIMO) {
    return { erro: `o valor precisa estar entre R$ ${VALOR_MINIMO} e R$ ${VALOR_MAXIMO}` };
  }
  if (!RE_EMAIL.test(email) || email.length > 120) return { erro: "e-mail inválido" };
  return { valor, email };
}

async function chamarMP(env, caminho, metodo, corpo) {
  const headers = { Authorization: `Bearer ${env.MP_ACCESS_TOKEN}`, "Content-Type": "application/json" };
  if (metodo === "POST") headers["X-Idempotency-Key"] = crypto.randomUUID();
  const resposta = await fetch(MP + caminho, { method: metodo, headers, body: corpo ? JSON.stringify(corpo) : undefined });
  let dados = null;
  try {
    dados = await resposta.json();
  } catch {
    dados = null;
  }
  return { ok: resposta.ok, status: resposta.status, dados };
}

// ------------------------------------------------------------------ Pix

async function criarPix(request, env) {
  const c = conferir(await lerPedido(request));
  if (c.erro) return json({ erro: c.erro }, 400);
  const valor = c.valor.toFixed(2);
  const r = await chamarMP(env, "/v1/orders", "POST", {
    type: "online",
    total_amount: valor,
    external_reference: "apoio-pix-" + crypto.randomUUID().slice(0, 18),
    processing_mode: "automatic",
    transactions: {
      payments: [{ amount: valor, payment_method: { id: "pix", type: "bank_transfer" }, expiration_time: "PT30M" }],
    },
    payer: { email: c.email },
  });
  if (!r.ok) return json({ erro: "o Mercado Pago recusou criar o Pix", status: r.status }, 502);
  const pagamento = ((r.dados.transactions || {}).payments || [])[0] || {};
  const meio = pagamento.payment_method || {};
  return json({
    id: r.dados.id,
    situacao: r.dados.status,
    valor,
    qr_code: meio.qr_code || "",
    qr_code_base64: meio.qr_code_base64 || "",
    ticket_url: meio.ticket_url || "",
    vence_em_minutos: 30,
  });
}

async function situacaoDoPix(id, env) {
  const guardado = await lerGuardado(env, "pix:" + id);
  if (guardado && guardado.pago) return json({ id, situacao: guardado.situacao, pago: true, fonte: "aviso" });
  const r = await chamarMP(env, "/v1/orders/" + encodeURIComponent(id), "GET");
  if (!r.ok) return json({ erro: "não achei esse Pix", status: r.status }, r.status === 404 ? 404 : 502);
  // "processed" e a order paga; "action_required" ainda espera o Pix.
  const pago = r.dados.status === "processed";
  if (pago) await guardar(env, "pix:" + id, { situacao: r.dados.status, pago: true, valor: r.dados.total_amount });
  return json({ id, situacao: r.dados.status, detalhe: r.dados.status_detail, pago });
}

/* "authorized" e a assinatura com cartao posto e ativa; "pending" ainda
   espera a pessoa terminar na pagina do Mercado Pago. */
async function situacaoDaAssinatura(id, env) {
  const guardado = await lerGuardado(env, "assinatura:" + id);
  if (guardado && guardado.situacao !== "pending") return json({ id, ...guardado, ativa: guardado.situacao === "authorized", fonte: "aviso" });
  const r = await chamarMP(env, "/preapproval/" + encodeURIComponent(id), "GET");
  if (!r.ok) return json({ erro: "não achei essa assinatura", status: r.status }, r.status === 404 ? 404 : 502);
  const situacao = r.dados.status;
  if (situacao !== "pending") await guardar(env, "assinatura:" + id, { situacao, valor: (r.dados.auto_recurring || {}).transaction_amount });
  return json({ id, situacao, ativa: situacao === "authorized" });
}

/* O que o aviso diz, conferido na fonte: o aviso so traz o id - a situacao
   vem do Mercado Pago, com o token, e so entao e guardada. */
async function registrarAviso(tipo, id, env) {
  if (!id) return;
  if (tipo === "order") {
    const r = await chamarMP(env, "/v1/orders/" + encodeURIComponent(id), "GET");
    if (r.ok && r.dados.status === "processed") await guardar(env, "pix:" + id, { situacao: r.dados.status, pago: true, valor: r.dados.total_amount });
  } else if (tipo === "subscription_preapproval" || tipo === "preapproval") {
    const r = await chamarMP(env, "/preapproval/" + encodeURIComponent(id), "GET");
    if (r.ok) await guardar(env, "assinatura:" + id, { situacao: r.dados.status, valor: (r.dados.auto_recurring || {}).transaction_amount });
  }
}

// ----------------------------------------------------------- assinatura

async function criarAssinatura(request, env) {
  const pedido = await lerPedido(request);
  const c = conferir(pedido);
  if (c.erro) return json({ erro: c.erro }, 400);
  // O apoio no cartao e sempre mensal.
  const r = await chamarMP(env, "/preapproval", "POST", {
    reason: "Apoio mensal ao PAULUS",
    external_reference: "apoio-assinatura-" + crypto.randomUUID().slice(0, 18),
    payer_email: c.email,
    auto_recurring: {
      frequency: 1,
      frequency_type: "months",
      transaction_amount: c.valor,
      currency_id: "BRL",
    },
    back_url: "https://paulus.ia.br/",
    status: "pending",
  });
  if (!r.ok) return json({ erro: "o Mercado Pago recusou criar a assinatura", status: r.status }, 502);
  // A chave da assinatura: so quem a recebeu (o programa de quem assinou)
  // consegue depois diminuir o valor ou interromper.
  return json({ id: r.dados.id, situacao: r.dados.status, link: r.dados.init_point || "", chave: await chaveDaAssinatura(env, r.dados.id) });
}

async function chaveDaAssinatura(env, id) {
  return hmacHex(env.MP_WEBHOOK_SECRET || env.MP_ACCESS_TOKEN, "assinatura:" + id);
}

async function chaveConfere(env, id, chave) {
  return typeof chave === "string" && igual(await chaveDaAssinatura(env, id), chave.toLowerCase());
}

/* Diminuir (ou mudar) o valor da assinatura. */
async function mudarValor(id, request, env) {
  const pedido = (await lerPedido(request)) || {};
  if (!(await chaveConfere(env, id, pedido.chave))) return json({ erro: "essa assinatura não é desta instalação" }, 403);
  const valor = Math.round(Number(pedido.valor) * 100) / 100;
  if (!Number.isFinite(valor) || valor < VALOR_MINIMO || valor > VALOR_MAXIMO) {
    return json({ erro: `o valor precisa estar entre R$ ${VALOR_MINIMO} e R$ ${VALOR_MAXIMO}` }, 400);
  }
  const r = await chamarMP(env, "/preapproval/" + encodeURIComponent(id), "PUT", {
    auto_recurring: { transaction_amount: valor, currency_id: "BRL" },
  });
  if (!r.ok) return json({ erro: "o Mercado Pago recusou mudar o valor", status: r.status }, 502);
  await guardar(env, "assinatura:" + id, { situacao: r.dados.status, valor });
  return json({ id, situacao: r.dados.status, valor });
}

/* As cobrancas mensais da assinatura (as "faturas" do Mercado Pago), para o
   extrato de apoio: data, valor e se foi paga. */
async function pagamentosDaAssinatura(id, request, env) {
  const pedido = (await lerPedido(request)) || {};
  if (!(await chaveConfere(env, id, pedido.chave))) return json({ erro: "essa assinatura não é desta instalação" }, 403);
  const r = await chamarMP(env, "/authorized_payments/search?preapproval_id=" + encodeURIComponent(id) + "&limit=100", "GET");
  if (!r.ok) return json({ erro: "o Mercado Pago não devolveu as cobranças", status: r.status }, 502);
  const pagamentos = ((r.dados && r.dados.results) || []).map((f) => {
    const pagamento = f.payment || {};
    return {
      id: String(f.id || ""),
      data: f.debit_date || f.date_created || "",
      valor: Number(f.transaction_amount) || 0,
      situacao: pagamento.status || f.status || "",
      pago: pagamento.status === "approved",
    };
  });
  return json({ id, pagamentos });
}

/* Interromper: a assinatura e cancelada no Mercado Pago - nada mais e cobrado. */
async function interromper(id, request, env) {
  const pedido = (await lerPedido(request)) || {};
  if (!(await chaveConfere(env, id, pedido.chave))) return json({ erro: "essa assinatura não é desta instalação" }, 403);
  const r = await chamarMP(env, "/preapproval/" + encodeURIComponent(id), "PUT", { status: "cancelled" });
  if (!r.ok) return json({ erro: "o Mercado Pago recusou interromper", status: r.status }, 502);
  await guardar(env, "assinatura:" + id, { situacao: "cancelled" });
  return json({ id, situacao: "cancelled" });
}

// ---------------------------------------------------------------- aviso

/* O webhook: so aceita aviso com a assinatura do Mercado Pago certa
   (HMAC-SHA256 do "manifest" com a chave secreta do webhook). Aceito, a
   situacao e buscada no Mercado Pago e guardada no KV - depois da resposta,
   para o Mercado Pago nao esperar. */
async function receberAviso(request, url, env, ctx) {
  const assinatura = request.headers.get("x-signature") || "";
  const requestId = request.headers.get("x-request-id") || "";
  const partes = Object.fromEntries(assinatura.split(",").map((p) => p.trim().split("=")).filter((p) => p.length === 2));
  const ts = partes.ts || "";
  const v1 = (partes.v1 || "").toLowerCase();
  if (!ts || !v1 || !env.MP_WEBHOOK_SECRET) return json({ erro: "aviso sem assinatura" }, 401);

  const dataId = url.searchParams.get("data.id") || "";
  // O id alfanumerico entra no manifest em minusculas; o numerico, como veio.
  const candidatos = [...new Set([dataId, dataId.toLowerCase()])];
  let valido = false;
  for (const id of candidatos) {
    const manifest = (id ? `id:${id};` : "") + (requestId ? `request-id:${requestId};` : "") + `ts:${ts};`;
    if (igual(await hmacHex(env.MP_WEBHOOK_SECRET, manifest), v1)) valido = true;
  }
  if (!valido) return json({ erro: "assinatura não confere" }, 401);

  const quando = Number(ts) < 1e12 ? Number(ts) * 1000 : Number(ts);
  if (Math.abs(Date.now() - quando) > AVISO_VALIDADE_MS) return json({ erro: "aviso velho" }, 401);
  const tipo = url.searchParams.get("type") || url.searchParams.get("topic") || "";
  const trabalho = registrarAviso(tipo, dataId, env).catch(() => null);
  if (ctx && ctx.waitUntil) ctx.waitUntil(trabalho);
  else await trabalho;
  return json({ recebido: true });
}

async function hmacHex(segredo, mensagem) {
  const chave = await crypto.subtle.importKey("raw", new TextEncoder().encode(segredo), { name: "HMAC", hash: "SHA-256" }, false, ["sign"]);
  const assinado = await crypto.subtle.sign("HMAC", chave, new TextEncoder().encode(mensagem));
  return [...new Uint8Array(assinado)].map((b) => b.toString(16).padStart(2, "0")).join("");
}

/* Comparacao em tempo constante: nao revela em que letra a assinatura errou. */
function igual(a, b) {
  if (a.length !== b.length) return false;
  let diferenca = 0;
  for (let i = 0; i < a.length; i++) diferenca |= a.charCodeAt(i) ^ b.charCodeAt(i);
  return diferenca === 0;
}
