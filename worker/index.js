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
//   POST /api/mp/aviso        o webhook do Mercado Pago (assinatura conferida)
//
// Todo o resto e o site estatico.

const MP = "https://api.mercadopago.com";
const VALOR_MINIMO = 5;
const VALOR_MAXIMO = 5000;
const RE_EMAIL = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
// O aviso do Mercado Pago mais velho que isto e recusado (repeticao).
const AVISO_VALIDADE_MS = 10 * 60 * 1000;

export default {
  async fetch(request, env) {
    const url = new URL(request.url);
    if (!url.pathname.startsWith("/api/")) return env.ASSETS.fetch(request);
    try {
      if (url.pathname === "/api/mp/pix" && request.method === "POST") return await criarPix(request, env);
      const pix = url.pathname.match(/^\/api\/mp\/pix\/([A-Za-z0-9_-]{6,64})$/);
      if (pix && request.method === "GET") return await situacaoDoPix(pix[1], env);
      if (url.pathname === "/api/mp/assinatura" && request.method === "POST") return await criarAssinatura(request, env);
      if (url.pathname === "/api/mp/aviso" && request.method === "POST") return await receberAviso(request, url, env);
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
  const r = await chamarMP(env, "/v1/orders/" + encodeURIComponent(id), "GET");
  if (!r.ok) return json({ erro: "não achei esse Pix", status: r.status }, r.status === 404 ? 404 : 502);
  // "processed" e a order paga; "action_required" ainda espera o Pix.
  return json({ id, situacao: r.dados.status, detalhe: r.dados.status_detail, pago: r.dados.status === "processed" });
}

// ----------------------------------------------------------- assinatura

async function criarAssinatura(request, env) {
  const pedido = await lerPedido(request);
  const c = conferir(pedido);
  if (c.erro) return json({ erro: c.erro }, 400);
  const anual = pedido.frequencia === "anual";
  const r = await chamarMP(env, "/preapproval", "POST", {
    reason: "Apoio ao PAULUS " + (anual ? "(anual)" : "(mensal)"),
    external_reference: "apoio-assinatura-" + crypto.randomUUID().slice(0, 18),
    payer_email: c.email,
    auto_recurring: {
      frequency: anual ? 12 : 1,
      frequency_type: "months",
      transaction_amount: c.valor,
      currency_id: "BRL",
    },
    back_url: "https://paulus.ia.br/",
    status: "pending",
  });
  if (!r.ok) return json({ erro: "o Mercado Pago recusou criar a assinatura", status: r.status }, 502);
  return json({ id: r.dados.id, situacao: r.dados.status, link: r.dados.init_point || "" });
}

// ---------------------------------------------------------------- aviso

/* O webhook: so aceita aviso com a assinatura do Mercado Pago certa
   (HMAC-SHA256 do "manifest" com a chave secreta do webhook). Por enquanto
   o aviso so e conferido e respondido - o programa pergunta a situacao do
   Pix direto (GET /api/mp/pix/:id). Guardar o historico dos avisos pede um
   banco (KV/D1), que ainda nao existe aqui. */
async function receberAviso(request, url, env) {
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
