// O Worker do paulus.ia.br: o site (pasta site/) e as rotas de pagamento
// do "Apoiar o projeto" no Mercado Pago.
//
// O Access Token do Mercado Pago so existe aqui, como segredo do Worker
// (npx wrangler secret put MP_ACCESS_TOKEN) - nunca no programa que roda na
// maquina de cada usuario, onde qualquer um poderia le-lo.
//
//   POST /api/mp/pix          cria o Pix (Orders API) e devolve o QR
//   GET  /api/mp/pix/:id      a situacao do Pix (pago ou nao)
//   POST /api/mp/pix/recuperar  os Pix pagos de um e-mail nas datas dadas
//   POST /api/mp/assinatura   cria a assinatura no cartao e devolve o link
//                             da pagina do Mercado Pago onde se poe o cartao
//   GET  /api/mp/assinatura/:id  se a assinatura ja foi ativada (cartao posto)
//   POST /api/mp/assinatura/:id/valor        muda o valor mensal  } so com a
//   POST /api/mp/assinatura/:id/interromper  cancela a assinatura } chave dela
//   POST /api/mp/assinatura/:id/pagamentos   as cobrancas mensais }
//   POST /api/mp/aviso        o webhook do Mercado Pago (assinatura conferida)
//   POST /api/mp/cartao       contribuicao unica no cartao (Checkout Pro), do site
//   POST /api/calibracao      medidas de maquina e modelo, de quem escolheu
//                             participar (so numeros; veja receberCalibracao)
//   GET  /api/calibracao      todas as medidas, para o programa estimar melhor
//   GET  /api/public/desenvolvimento  versoes e apoio consolidado, mes a mes
//   GET  /api/public/apoiadores       o mural: so nome e desde quando
//
// O que o webhook confirma fica no KV APOIOS (so situacao, valor e data): o
// Pix pago depois de fechado o pop-up e a assinatura concluida no navegador
// aparecem para o programa na proxima consulta. As rotas que criam cobranca
// passam pelo limite LIMITE (10 por minuto por endereco de internet).
//
// A parte publica e montada separada da privada: cada contribuicao
// confirmada vira uma chave "contrib:AAAA-MM:<id>" com so o valor, e cada
// nome autorizado vira "mural:<impressao do e-mail>" com so nome e mes. As
// rotas /api/public/* leem so essas chaves - nada de e-mail, id do Mercado
// Pago, forma ou valor individual sai delas.
//
// Todo o resto e o site estatico.
//
// O acesso de fora (worker/tunel.js): /conectar e /api/tunel/*, que criam o
// caminho de cada escritorio ate o PAULUS dele. Desligado sem TUNEL_ATIVO.

import { atenderTunel, ehRotaDoTunel, limparEscritorios } from "./tunel.js";

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
    // O Worker nunca atende <escritorio>.paulus.ia.br: esse trafego e do tunel
    // de cada escritorio, direto da Cloudflare ao computador dele. Se uma rota
    // curinga um dia apontar para ca por engano, nada passa por aqui.
    if (url.hostname.endsWith(".paulus.ia.br") && url.hostname !== "www.paulus.ia.br") {
      return new Response("não encontrado", { status: 404 });
    }
    if (ehRotaDoTunel(url)) {
      try {
        return await atenderTunel(request, env, url, { dentroDoLimite });
      } catch (erro) {
        return json({ erro: "falha no servidor do acesso de fora" }, 500);
      }
    }
    if (!url.pathname.startsWith("/api/")) return env.ASSETS.fetch(request);
    try {
      if (url.pathname === "/api/public/desenvolvimento" && request.method === "GET") return await publicoEmCache(request, ctx, () => desenvolvimento(request, env));
      if (url.pathname === "/api/public/apoiadores" && request.method === "GET") return await publicoEmCache(request, ctx, () => apoiadores(env));
      const criando = request.method === "POST" && ["/api/mp/pix", "/api/mp/assinatura", "/api/mp/cartao"].includes(url.pathname);
      if (criando && !(await dentroDoLimite(request, env))) return json({ erro: "muitas tentativas seguidas - espere um minuto" }, 429);
      if (url.pathname === "/api/mp/pix" && request.method === "POST") return await criarPix(request, env);
      if (url.pathname === "/api/mp/cartao" && request.method === "POST") return await criarCartao(request, env);
      if (url.pathname === "/api/mp/pix/recuperar" && request.method === "POST") {
        if (!(await dentroDoLimite(request, env))) return json({ erro: "muitas tentativas seguidas - espere um minuto" }, 429);
        return await recuperarPix(request, env);
      }
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
      if (url.pathname === "/api/calibracao" && request.method === "POST") {
        if (!(await dentroDoLimite(request, env))) return json({ erro: "muitas tentativas seguidas - espere um minuto" }, 429);
        return await receberCalibracao(request, env);
      }
      if (url.pathname === "/api/calibracao" && request.method === "GET") return await entregarCalibracao(env);
      return json({ erro: "rota não existe" }, 404);
    } catch (erro) {
      return json({ erro: "falha no servidor de pagamento" }, 500);
    }
  },

  // O Cron Trigger diario (wrangler.jsonc): libera os enderecos do acesso de
  // fora que nunca conectaram em 7 dias ou estao parados ha mais de 180.
  // Sem TUNEL_ATIVO e sem o KV, nao faz nada.
  async scheduled(controller, env, ctx) {
    ctx.waitUntil(limparEscritorios(env));
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

/* Guarda somando ao que ja havia (a impressao do e-mail, gravada na criacao,
   continua quando o pagamento e confirmado). */
async function guardar(env, chave, dados) {
  if (!env.APOIOS) return;
  const antes = (await lerGuardado(env, chave)) || {};
  await env.APOIOS.put(chave, JSON.stringify({ ...antes, ...dados, quando: new Date().toISOString() }), { expirationTtl: KV_VALIDADE_S });
}

/* A impressao (SHA-256) do e-mail: da para conferir quem pagou sem guardar
   o e-mail em si. O Mercado Pago nao devolve o e-mail do pagador do Pix. */
async function impressaoDoEmail(email) {
  const resumo = await crypto.subtle.digest("SHA-256", new TextEncoder().encode(String(email || "").trim().toLowerCase()));
  return [...new Uint8Array(resumo)].map((b) => b.toString(16).padStart(2, "0")).join("");
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
  return { valor, email, mural: nomeDoMural(pedido && pedido.mural) };
}

/* O nome que a pessoa autorizou publicar no mural ("" = nao aparecer). Texto
   simples, uma linha, ate 60 letras: nada de marcacao nem de endereco. */
function nomeDoMural(bruto) {
  if (typeof bruto !== "string") return "";
  const nome = bruto.replace(/[\u0000-\u001f\u007f<>]/g, "").replace(/\s+/g, " ").trim().slice(0, 60);
  if (/https?:|www\.|@/i.test(nome)) return "";
  return nome;
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
  // Para achar este Pix de novo pelo e-mail (recuperar), sem guardar o e-mail.
  // O nome do mural so vai para o mural quando o Pix for pago.
  await guardar(env, "pix:" + r.dados.id, { pago: false, valor, emails: [await impressaoDoEmail(c.email)], mural: c.mural });
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
  if (pago) await pixPago(env, id, r.dados);
  return json({ id, situacao: r.dados.status, detalhe: r.dados.status_detail, pago });
}

/* O Pix pago: a situacao privada, a contribuicao do mes e, se autorizado, o mural. */
async function pixPago(env, id, order) {
  await guardar(env, "pix:" + id, { situacao: order.status, pago: true, valor: order.total_amount });
  const g = (await lerGuardado(env, "pix:" + id)) || {};
  await contribuicao(env, "pix-" + id, Number(order.total_amount) || Number(g.valor) || 0, g.quando);
  await noMural(env, g.mural, (g.emails || [])[0], g.quando);
}

/* A data de um instante no horario de Brasilia, "dd/mm/aaaa". */
function dataBrasilia(iso) {
  const ms = Date.parse(iso || "");
  if (!Number.isFinite(ms)) return "";
  const d = new Date(ms - 3 * 60 * 60 * 1000).toISOString().slice(0, 10).split("-");
  return `${d[2]}/${d[1]}/${d[0]}`;
}

/* Os Pix pagos que o programa perdeu (de uma versao que nao guardava o
   numero): so os do e-mail E das datas que o programa ja conhece - quem so
   sabe o e-mail de alguem nao descobre as doacoes dele. */
async function recuperarPix(request, env) {
  const pedido = (await lerPedido(request)) || {};
  const emails = [...new Set((pedido.emails || []).map((e) => String(e || "").trim().toLowerCase()).filter((e) => RE_EMAIL.test(e)))].slice(0, 3);
  const datas = new Set((pedido.datas || []).map((d) => String(d || "").trim()).filter((d) => /^\d{2}\/\d{2}\/\d{4}$/.test(d)).slice(0, 20));
  if (!emails.length || !datas.size || !env.APOIOS) return json({ pix: [] });
  // O Mercado Pago nao devolve o e-mail do pagador: vale a impressao gravada
  // quando o Pix foi criado.
  const impressoes = await Promise.all(emails.map(impressaoDoEmail));
  const achados = [];
  const lista = await env.APOIOS.list({ prefix: "pix:", limit: 1000 });
  for (const chave of lista.keys) {
    const guardado = await lerGuardado(env, chave.name);
    if (!guardado || !guardado.pago || !datas.has(dataBrasilia(guardado.quando))) continue;
    if (!(guardado.emails || []).some((e) => impressoes.includes(e))) continue;
    achados.push({ id: chave.name.slice(4), valor: Number(guardado.valor) || 0, data: guardado.quando });
  }
  return json({ pix: achados });
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
    if (r.ok && r.dados.status === "processed") await pixPago(env, id, r.dados);
  } else if (tipo === "subscription_preapproval" || tipo === "preapproval") {
    const r = await chamarMP(env, "/preapproval/" + encodeURIComponent(id), "GET");
    if (r.ok) await guardar(env, "assinatura:" + id, { situacao: r.dados.status, valor: (r.dados.auto_recurring || {}).transaction_amount });
  } else if (tipo === "subscription_authorized_payment") {
    // Cada cobranca mensal da assinatura.
    const r = await chamarMP(env, "/authorized_payments/" + encodeURIComponent(id), "GET");
    if (r.ok) await cobrancaPaga(env, r.dados);
  } else if (tipo === "payment") {
    // A contribuicao unica no cartao (Checkout Pro, feita no site).
    const r = await chamarMP(env, "/v1/payments/" + encodeURIComponent(id), "GET");
    const ref = String((r.dados && r.dados.external_reference) || "");
    if (r.ok && r.dados.status === "approved" && ref.startsWith("apoio-cartao-")) {
      const g = (await lerGuardado(env, "cartao:" + ref)) || {};
      await contribuicao(env, "cartao-" + id, Number(r.dados.transaction_amount) || 0, r.dados.date_approved);
      await noMural(env, g.mural, (g.emails || [])[0], r.dados.date_approved);
    }
  }
}

/* Uma cobranca mensal paga: conta no mes dela; o nome, se autorizado quando
   a assinatura foi criada, entra no mural. */
async function cobrancaPaga(env, f) {
  const pagamento = (f && f.payment) || {};
  if (pagamento.status !== "approved" || !f.id) return;
  const quando = f.debit_date || f.date_created || "";
  await contribuicao(env, "cobranca-" + f.id, Number(f.transaction_amount) || 0, quando);
  const g = (await lerGuardado(env, "assinatura:" + (f.preapproval_id || ""))) || {};
  await noMural(env, g.mural, (g.emails || [])[0], quando);
}

// -------------------------------------------------------- cartao, uma vez

/* A contribuicao unica no cartao, feita no site: o Checkout Pro do Mercado
   Pago. O cartao e digitado na pagina do Mercado Pago; volta para /apoiar. */
async function criarCartao(request, env) {
  const c = conferir(await lerPedido(request));
  if (c.erro) return json({ erro: c.erro }, 400);
  const ref = "apoio-cartao-" + crypto.randomUUID().slice(0, 18);
  const volta = (s) => "https://paulus.ia.br/apoiar/?cartao=" + s;
  const r = await chamarMP(env, "/checkout/preferences", "POST", {
    items: [{ id: "apoio", title: "Contribuição voluntária ao PAVLVS", quantity: 1, currency_id: "BRL", unit_price: c.valor }],
    payer: { email: c.email },
    external_reference: ref,
    back_urls: { success: volta("aprovado"), pending: volta("pendente"), failure: volta("recusado") },
    auto_return: "approved",
    payment_methods: { excluded_payment_types: [{ id: "ticket" }, { id: "bank_transfer" }, { id: "atm" }], installments: 1 },
    statement_descriptor: "PAVLVS",
  });
  if (!r.ok) return json({ erro: "o Mercado Pago recusou abrir o pagamento", status: r.status }, 502);
  await guardar(env, "cartao:" + ref, { valor: c.valor, emails: [await impressaoDoEmail(c.email)], mural: c.mural });
  return json({ link: r.dados.init_point || "" });
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
    // Quem assina pelo site volta para a pagina Apoiar; pelo programa, para o inicio.
    back_url: pedido && pedido.origem === "site" ? "https://paulus.ia.br/apoiar/?assinatura=voltou" : "https://paulus.ia.br/",
    status: "pending",
  });
  if (!r.ok) return json({ erro: "o Mercado Pago recusou criar a assinatura", status: r.status }, 502);
  await guardar(env, "assinatura:" + r.dados.id, { situacao: r.dados.status, valor: c.valor, emails: [await impressaoDoEmail(c.email)], mural: c.mural });
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
  const resultados = (r.dados && r.dados.results) || [];
  // As cobrancas pagas antes de existir o total do mes entram nele agora.
  for (const f of resultados) await cobrancaPaga(env, { ...f, preapproval_id: id });
  const pagamentos = resultados.map((f) => {
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

// ---------------------------------------------------------- o que e publico

/* O mes ("AAAA-MM") de um instante, no horario de Brasilia. */
function mesBrasilia(iso) {
  const ms = Date.parse(iso || "");
  return new Date((Number.isFinite(ms) ? ms : Date.now()) - 3 * 60 * 60 * 1000).toISOString().slice(0, 7);
}

/* Uma contribuicao confirmada, no mes dela. A chave e o id do pagamento: o
   mesmo aviso repetido nao conta duas vezes. So o valor vai junto. */
async function contribuicao(env, id, valor, quando) {
  if (!env.APOIOS || !id || !(valor > 0)) return;
  await env.APOIOS.put(`contrib:${mesBrasilia(quando)}:${id}`, "1", { metadata: { v: Math.round(valor * 100) / 100 } });
}

/* O nome autorizado entra no mural uma vez por pessoa (pela impressao do
   e-mail), com o mes da primeira contribuicao; o nome mais recente vale. */
async function noMural(env, nome, impressao, quando) {
  if (!env.APOIOS || !nome || !impressao) return;
  const chave = "mural:" + impressao;
  const antes = env.APOIOS.getWithMetadata ? (await env.APOIOS.getWithMetadata(chave)).metadata : null;
  const desde = (antes && antes.desde) || mesBrasilia(quando);
  await env.APOIOS.put(chave, "1", { metadata: { nome, desde } });
}

async function listar(env, prefixo) {
  const chaves = [];
  let cursor;
  do {
    const pagina = await env.APOIOS.list({ prefix: prefixo, cursor, limit: 1000 });
    chaves.push(...pagina.keys);
    cursor = pagina.list_complete ? undefined : pagina.cursor;
  } while (cursor);
  return chaves;
}

async function arquivoDoSite(request, env, caminho) {
  try {
    const r = await env.ASSETS.fetch(new Request(new URL(caminho, request.url)));
    return r.ok ? await r.json() : null;
  } catch {
    return null;
  }
}

/* A resposta publica fica 15 minutos no cache da borda: a pagina e o
   programa podem pedir a vontade sem ler o KV inteiro a cada vez. */
async function publicoEmCache(request, ctx, montar) {
  const cache = typeof caches !== "undefined" ? caches.default : null;
  const chave = new Request(new URL(request.url).toString(), { method: "GET" });
  const guardada = cache ? await cache.match(chave) : null;
  if (guardada) return guardada;
  const resposta = new Response(JSON.stringify(await montar()), {
    headers: {
      "content-type": "application/json; charset=utf-8",
      "cache-control": "public, max-age=900",
      "access-control-allow-origin": "*",
    },
  });
  if (cache && ctx && ctx.waitUntil) ctx.waitUntil(cache.put(chave, resposta.clone()));
  return resposta;
}

/* Os Pix pagos antes de existir o total do mes entram nele uma vez. */
async function migrarContribuicoes(env) {
  if (!env.APOIOS || (await env.APOIOS.get("migracao:contrib-1"))) return;
  for (const k of await listar(env, "pix:")) {
    const g = await lerGuardado(env, k.name);
    if (g && g.pago) await contribuicao(env, "pix-" + k.name.slice(4), Number(g.valor) || 0, g.quando);
  }
  await env.APOIOS.put("migracao:contrib-1", new Date().toISOString());
}

/* Mes a mes: as versoes publicadas (site/dados/versoes.json, montado das
   releases) e o apoio consolidado - soma e quantidade, nunca um valor
   individual. O ITCD so aparece quando o recolhimento esta registrado em
   site/dados/itcd.json; sem registro, null. */
async function desenvolvimento(request, env) {
  await migrarContribuicoes(env);
  const versoes = (await arquivoDoSite(request, env, "/dados/versoes.json")) || {};
  const itcd = (await arquivoDoSite(request, env, "/dados/itcd.json")) || {};
  const meses = {};
  const mes = (m) => (meses[m] = meses[m] || { month: m, contributions: { total: 0, count: 0, itcdPaid: null }, releases: [] });
  for (const r of versoes.releases || []) {
    if (/^\d{4}-\d{2}-\d{2}$/.test(r.date || "")) mes(r.date.slice(0, 7)).releases.push(r);
  }
  if (env.APOIOS) {
    for (const k of await listar(env, "contrib:")) {
      const m = k.name.slice(8, 15);
      if (!/^\d{4}-\d{2}$/.test(m)) continue;
      const c = mes(m).contributions;
      c.total = Math.round((c.total + (Number(k.metadata && k.metadata.v) || 0)) * 100) / 100;
      c.count += 1;
    }
  }
  for (const m of Object.values(meses)) {
    const pago = itcd[m.month];
    m.contributions.itcdPaid = typeof pago === "number" ? pago : null;
    m.releases.sort((a, b) => b.date.localeCompare(a.date));
  }
  return {
    atualizadoEm: mesBrasilia().slice(0, 7) + "-" + new Date(Date.now() - 3 * 60 * 60 * 1000).toISOString().slice(8, 10),
    meses: Object.values(meses).sort((a, b) => b.month.localeCompare(a.month)),
  };
}

/* O mural: so nome e mes, de quem autorizou. */
async function apoiadores(env) {
  if (!env.APOIOS) return { apoiadores: [] };
  const lista = (await listar(env, "mural:"))
    .map((k) => ({ name: String((k.metadata && k.metadata.nome) || ""), since: String((k.metadata && k.metadata.desde) || "") }))
    .filter((a) => a.name && /^\d{4}-\d{2}$/.test(a.since));
  lista.sort((a, b) => a.since.localeCompare(b.since) || a.name.localeCompare(b.name, "pt-BR"));
  return { apoiadores: lista };
}

// ------------------------------------------------------------ calibracao
//
// A estimativa de quanto cada modelo de IA demora numa maquina
// (paulus/legal/src/maquina.py) melhora com medidas de muitas maquinas. Quem
// escolhe participar, no programa, manda as medidas da maquina dele e recebe
// as de todos. So numeros da maquina e do modelo: processador, memoria, as
// duas velocidades medidas, o modelo e as palavras por segundo dele. Nada do
// escritorio, nada de pessoa. Cada amostra e conferida campo a campo; o que
// nao cabe no formato e jogado fora.
//
// Tudo numa chave so do KV APOIOS (prefixo "calibracao:"), para nao pedir
// configuracao nova no Cloudflare. Uma amostra por maquina e modelo: medir de
// novo troca a antiga. Guarda as 5000 mais recentes.

const CAL_CHAVE = "calibracao:todas";
const CAL_MAXIMO = 5000;
const CAL_POR_PEDIDO = 50;

function calNumero(v, min, max) {
  return typeof v === "number" && Number.isFinite(v) && v >= min && v <= max;
}

function calTexto(v, max, re) {
  return typeof v === "string" && v.length <= max && (!re || re.test(v));
}

function limparAmostra(a) {
  if (!a || typeof a !== "object") return null;
  const m = a.maquina || {};
  const ok =
    calTexto(m.id, 32, /^[0-9a-f]{6,32}$/) && calNumero(m.versao, 1, 99) &&
    calTexto(m.processador, 120, /^[\x20-\x7EÀ-ſ]*$/) && calNumero(m.nucleos, 1, 512) &&
    calNumero(m.ram_total_gb, 0.5, 4096) && calNumero(m.banda_gbs, 0.1, 2000) && calNumero(m.gflops, 0.1, 100000) &&
    calTexto(a.modelo, 120, /^[a-z0-9][a-z0-9._:\/-]*$/i) && calNumero(a.tamanho_gb, 0.01, 500) &&
    calNumero(a.parametros_b, 0.01, 2000) && calTexto(a.quantizacao || "", 20, /^[A-Za-z0-9_]*$/) &&
    calNumero(a.escrita_tps, 0.01, 10000) && calNumero(a.leitura_tps || 0, 0, 100000);
  if (!ok) return null;
  return {
    maquina: {
      id: m.id, versao: m.versao, processador: m.processador, nucleos: m.nucleos, ram_total_gb: m.ram_total_gb,
      avx2: m.avx2 === true ? true : m.avx2 === false ? false : null, banda_gbs: m.banda_gbs, gflops: m.gflops,
      na_bateria: m.na_bateria === true ? true : m.na_bateria === false ? false : null,
    },
    gpu: a.gpu === true,
    modelo: a.modelo, tamanho_gb: a.tamanho_gb, parametros_b: a.parametros_b, quantizacao: a.quantizacao || "",
    escrita_tps: a.escrita_tps, leitura_tps: a.leitura_tps || 0,
    quando: new Date().toISOString().slice(0, 16).replace("T", " "),
  };
}

async function receberCalibracao(request, env) {
  if (!env.APOIOS) return json({ erro: "armazenamento indisponível" }, 503);
  const corpo = await lerPedido(request);
  const lista = Array.isArray(corpo && corpo.amostras) ? corpo.amostras.slice(0, CAL_POR_PEDIDO) : [];
  const limpas = lista.map(limparAmostra).filter(Boolean);
  if (!limpas.length) return json({ erro: "nenhuma amostra válida" }, 400);
  let todas = [];
  try {
    todas = JSON.parse((await env.APOIOS.get(CAL_CHAVE)) || "[]");
  } catch {
    todas = [];
  }
  for (const a of limpas) {
    const i = todas.findIndex((x) => x.maquina.id === a.maquina.id && x.modelo === a.modelo);
    if (i >= 0) todas.splice(i, 1);
    todas.push(a);
  }
  todas = todas.slice(-CAL_MAXIMO);
  await env.APOIOS.put(CAL_CHAVE, JSON.stringify(todas));
  return json({ recebidas: limpas.length, total: todas.length });
}

async function entregarCalibracao(env) {
  const bruto = env.APOIOS ? await env.APOIOS.get(CAL_CHAVE) : null;
  let amostras = [];
  try {
    amostras = bruto ? JSON.parse(bruto) : [];
  } catch {
    amostras = [];
  }
  return new Response(JSON.stringify({ versao: 1, amostras }), {
    headers: { "content-type": "application/json; charset=utf-8", "cache-control": "public, max-age=3600" },
  });
}
