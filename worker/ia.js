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
export const TOLERANCIA_MS = 5 * 24 * 3600 * 1000;
// Portugues tem ~4 caracteres por token; 3 estima para cima (a reserva e teto).
const CARACTERES_POR_TOKEN = 3;

// Os planos (02/10/2026). O "escritorio" e o de antes: quem ja assinava fica
// nele, com o valor e os tokens de IA_PLANO_VALOR e IA_PLANO_TOKENS. IA_PLANOS
// (JSON, [{id, nome, valor, tokens}]) troca a lista inteira sem mexer no codigo.
export const PLANO_PADRAO = "escritorio";

function lerPlanos(env, valor, tokens) {
  try {
    const l = JSON.parse(env.IA_PLANOS || "");
    const ok = Array.isArray(l) && l.length && l.every((p) => p && /^[a-z0-9-]{2,24}$/.test(p.id) && p.nome && Number(p.valor) > 0 && Number(p.tokens) > 0);
    if (ok && l.some((p) => p.id === PLANO_PADRAO)) return l.map((p) => ({ id: p.id, nome: String(p.nome), valor: Number(p.valor), tokens: Number(p.tokens) }));
  } catch {
    // sem a lista (ou quebrada): a de fabrica
  }
  return [
    { id: "advogado", nome: "Advogado", valor: 150, tokens: 12000000 },
    { id: PLANO_PADRAO, nome: "Escritório", valor, tokens },
    { id: "plus", nome: "Escritório Plus", valor: 550, tokens: 60000000 },
  ];
}

export function planoDe(n, id) {
  return n.planos.find((p) => p.id === id) || n.planos.find((p) => p.id === PLANO_PADRAO) || n.planos[0];
}

export function numeros(env) {
  const n = (v, padrao) => (Number.isFinite(Number(v)) && Number(v) > 0 ? Number(v) : padrao);
  const planoValor = n(env.IA_PLANO_VALOR, 300);
  const planoTokens = n(env.IA_PLANO_TOKENS, 30000000);
  return {
    planoValor,
    planoTokens,
    planos: lerPlanos(env, planoValor, planoTokens),
    recargaValor: n(env.IA_RECARGA_VALOR, 50),
    recargaTokens: n(env.IA_RECARGA_TOKENS, 10000000),
    // Os pacotes da recarga rapida (02/10/2026): metade, a recarga de sempre e
    // o dobro, no mesmo preco por token.
    recargas: [0.5, 1, 2].map((f) => ({ id: String(f), tokens: Math.round(n(env.IA_RECARGA_TOKENS, 10000000) * f),
      valor: Math.round(n(env.IA_RECARGA_VALOR, 50) * f * 100) / 100 })),
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
  // O cupom da pagina Assinar: vale? quanto fica? (sem conta: so o codigo e o plano)
  if (p === "/api/ia/cupom" && m === "GET") {
    if (await limitado()) return json({ erro: "muitas tentativas seguidas - espere um minuto" }, 429);
    const r = await conferirCupom(env, url.searchParams.get("codigo"), url.searchParams.get("plano"));
    return json(r.erro ? { ok: false, erro: r.erro } : { ok: true, ...r.cupom, valor: r.valor, valor_cheio: r.valor_cheio });
  }
  if (p === "/api/ia/planos" && m === "GET") {
    const n = numeros(env);
    return json({ planos: n.planos, recarga: { valor: n.recargaValor, tokens: n.recargaTokens }, recargas: n.recargas });
  }
  // A pagina de cadastro do site (site/cadastro): o id_token do Google a cada
  // pedido, sem segredo de instalacao - quem assina pelo site ainda nao
  // instalou o PAULUS.
  if (p.startsWith("/api/ia/site/") && m === "POST") {
    if (await limitado()) return json({ erro: "muitas tentativas seguidas - espere um minuto" }, 429);
    return atenderSite(request, env, p, deps);
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
  if (p === "/api/ia/plano" && m === "POST") {
    if (await limitado()) return json({ erro: "muitas tentativas seguidas - espere um minuto" }, 429);
    const d = (await lerJSON(request)) || {};
    return trocarPlano(env, conta, mp, String(d.plano || ""));
  }
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
    const fim = await conta.pedir("liquidar", { reserva: reserva.id, tokens: real, entrada: Number(u.prompt_tokens) || entrada,
      saida: Number(u.completion_tokens) || 0, modelo });
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
      await conta.pedir("liquidar", { reserva: reserva.id, tokens: real, entrada: u ? u.entrada : entrada, saida: u ? u.saida : pedacos, modelo });
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
  return criarAssinatura(env, conta, id, mp, { email: d.email, plano: d.plano, origem: "", cupom: d.cupom });
}

/* A assinatura mensal do plano escolhido: o link da pagina do Mercado Pago
   onde a pessoa poe o cartao. Sem plano no pedido, o da conta (ou o padrao). */
async function criarAssinatura(env, conta, id, mp, { email, plano, origem, cupom }) {
  const atual = await conta.pedir("resumo");
  // Sem e-mail no pedido, o da conta Google da nuvem (o pagador recebe o recibo nele).
  const para = String(email || atual.email || "").trim().toLowerCase();
  if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(para) || para.length > 120) return json({ erro: "e-mail inválido" }, 400);
  if (atual.assinatura && atual.assinatura.situacao === "authorized") return json({ erro: "a assinatura já está ativa" }, 409);
  const n = numeros(env);
  if (plano && !n.planos.some((x) => x.id === plano)) return json({ erro: "esse plano não existe" }, 400);
  const escolhido = planoDe(n, plano || (atual.plano || {}).id);
  // O cupom (painel admin): o valor com desconto pelos meses combinados; depois
  // deles, a renovacao volta ao valor cheio (avisoDaIA, cupom_voltar).
  let comCupom = null;
  let valor = escolhido.valor;
  if (cupom) {
    const c = await conferirCupom(env, cupom, escolhido.id);
    if (c.erro) return json({ erro: c.erro }, 400);
    comCupom = { codigo: c.cupom.codigo, desconto: c.cupom.desconto, meses: c.cupom.meses, brinde: c.cupom.brinde, valor_cheio: escolhido.valor, cobrados: 0 };
    valor = c.valor;
  }
  const r = await mp(env, "/preapproval", "POST", {
    reason: "PAULUS - plano " + escolhido.nome + (comCupom ? " (cupom " + comCupom.codigo + ")" : ""),
    external_reference: "ia-assinatura-" + id,
    payer_email: para,
    auto_recurring: { frequency: 1, frequency_type: "months", transaction_amount: valor, currency_id: "BRL" },
    // Quem assina pelo site volta para a pagina de cadastro, que diz o que fazer em seguida.
    back_url: origem === "site" ? "https://paulus.ia.br/cadastro/?voltou=1" : "https://paulus.ia.br/",
    status: "pending",
  });
  if (!r.ok) return json({ erro: "o Mercado Pago recusou criar a assinatura", status: r.status }, 502);
  await conta.pedir("assinatura", { plano: escolhido.id, cupom: comCupom, assinatura: { id: String(r.dados.id), situacao: r.dados.status || "pending", valor } });
  if (comCupom) await usarCupom(env, comCupom.codigo);
  return json({ id: r.dados.id, situacao: r.dados.status, link: r.dados.init_point || "", plano: escolhido, valor, cupom: comCupom });
}

/* Trocar de plano com a assinatura ativa: o Mercado Pago passa a cobrar o
   valor novo, e os tokens novos entram no ciclo seguinte - o ciclo ja pago
   fica com o plano em que foi pago. Pedir o plano de agora desfaz a troca
   marcada. */
async function trocarPlano(env, conta, mp, plano) {
  const n = numeros(env);
  if (!n.planos.some((x) => x.id === plano)) return json({ erro: "esse plano não existe" }, 400);
  const atual = await conta.pedir("resumo");
  const a = atual.assinatura;
  if (!a || !a.id || a.situacao !== "authorized") return json({ erro: "a troca é para quem tem a assinatura ativa; sem ela, é só assinar o plano escolhido" }, 409);
  const novo = planoDe(n, plano);
  const r = await mp(env, "/preapproval/" + encodeURIComponent(a.id), "PUT", {
    reason: "PAULUS - plano " + novo.nome,
    auto_recurring: { transaction_amount: novo.valor, currency_id: "BRL" },
  });
  if (!r.ok) return json({ erro: "o Mercado Pago recusou mudar o valor da assinatura", status: r.status }, 502);
  return json(await conta.pedir("plano_proximo", { plano: novo.id, valor: novo.valor }));
}

// ------------------------------------------------------------- o cupom
//
// Criado no painel admin (worker/admin.js) e guardado no KV APOIOS em
// "admin:cupom:<CODIGO>": {codigo, desconto (%), meses, brinde (tokens),
// limite (0 = sem), usos, validade (ISO), planos [id], ativo}.

export async function lerCupom(env, codigo) {
  const c = String(codigo || "").trim().toUpperCase();
  if (!/^[A-Z0-9-]{3,24}$/.test(c) || !env.APOIOS) return null;
  try {
    return JSON.parse((await env.APOIOS.get("admin:cupom:" + c)) || "null");
  } catch {
    return null;
  }
}

/* {cupom, valor, valor_cheio} ou {erro}. */
export async function conferirCupom(env, codigo, plano) {
  const c = await lerCupom(env, codigo);
  if (!c || !c.ativo) return { erro: "esse cupom não existe ou está pausado" };
  if (c.validade && Date.parse(c.validade) < Date.now()) return { erro: "esse cupom venceu" };
  if (c.limite && (c.usos || 0) >= c.limite) return { erro: "esse cupom chegou ao limite de usos" };
  const n = numeros(env);
  const p = n.planos.find((x) => x.id === plano) || planoDe(n, plano);
  if (Array.isArray(c.planos) && c.planos.length && !c.planos.includes(p.id)) return { erro: "esse cupom não vale para o plano " + p.nome };
  const valor = Math.round(p.valor * (1 - Math.min(100, Math.max(0, Number(c.desconto) || 0)) / 100) * 100) / 100;
  return { cupom: { codigo: c.codigo, desconto: Number(c.desconto) || 0, meses: Number(c.meses) || 1, brinde: Number(c.brinde) || 0 }, valor, valor_cheio: p.valor };
}

async function usarCupom(env, codigo) {
  const c = await lerCupom(env, codigo);
  if (!c) return;
  c.usos = (c.usos || 0) + 1;
  await env.APOIOS.put("admin:cupom:" + c.codigo, JSON.stringify(c));
}

// ------------------------------------------------------- o site (cadastro)

const UFS = "AC AL AP AM BA CE DF ES GO MA MT MS MG PA PB PR PE PI RJ RN RS RO RR SC SP SE TO".split(" ");
// A versao dos termos e da politica que a pessoa aceita no cadastro.
export const TERMOS_VERSAO = "2026-10-02";

function soDigitos(t) {
  return String(t || "").replace(/\D/g, "");
}

export function cpfValido(d) {
  if (!/^\d{11}$/.test(d) || /^(\d)\1+$/.test(d)) return false;
  for (const k of [9, 10]) {
    let s = 0;
    for (let i = 0; i < k; i++) s += Number(d[i]) * (k + 1 - i);
    if ((s * 10) % 11 % 10 !== Number(d[k])) return false;
  }
  return true;
}

export function cnpjValido(d) {
  if (!/^\d{14}$/.test(d) || /^(\d)\1+$/.test(d)) return false;
  for (const k of [12, 13]) {
    const pesos = k === 12 ? [5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2] : [6, 5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2];
    const s = pesos.reduce((t, p, i) => t + Number(d[i]) * p, 0);
    const dv = s % 11 < 2 ? 0 : 11 - (s % 11);
    if (dv !== Number(d[k])) return false;
  }
  return true;
}

/* "OAB/PA 12.345", "12345-PA", "pa 12345" -> "PA 12345"; "" se nao for. */
export function oabNormal(t) {
  const s = String(t || "").toUpperCase().replace(/OAB/g, " ").replace(/[^A-Z0-9]/g, " ").trim();
  const uf = (s.match(/\b([A-Z]{2})\b/) || [])[1] || "";
  const numero = (s.replace(/\b[A-Z]{2}\b/, " ").replace(/\s+/g, "").match(/^(\d{3,7})([A-Z])?$/) || []);
  if (!UFS.includes(uf) || !numero[1]) return "";
  return uf + " " + numero[1] + (numero[2] || "");
}

/* O cadastro conferido, ou {erro}. */
export function conferirCadastro(d) {
  const nome = String(d.nome_escritorio || "").replace(/[\u0000-\u001f<>]/g, "").replace(/\s+/g, " ").trim();
  if (nome.length < 2 || nome.length > 80) return { erro: "diga o nome do escritório (ou o seu, se trabalha sozinho)" };
  const documento = soDigitos(d.documento);
  if (!(documento.length === 11 ? cpfValido(documento) : cnpjValido(documento))) return { erro: "o CPF ou CNPJ não confere" };
  const telefone = soDigitos(d.telefone);
  if (telefone.length < 10 || telefone.length > 13) return { erro: "o telefone precisa do DDD" };
  const oab = oabNormal(d.oab);
  if (!oab) return { erro: "a OAB vai com a UF e o número, por exemplo: PA 12345" };
  if (d.aceite !== true) return { erro: "é preciso aceitar os termos de uso e a política de privacidade" };
  return { cadastro: { nome_escritorio: nome, documento, telefone, oab, termos: TERMOS_VERSAO } };
}

async function atenderSite(request, env, p, deps) {
  const d = (await lerJSON(request)) || {};
  const dono = await (deps.donoDoToken || donoDoToken)(env, d.id_token);
  if (!dono) return json({ erro: "a confirmação do Google venceu: entre com o Google de novo" }, 401);
  const id = (await sha256("conta-ia:" + dono.sub)).slice(0, 24);
  const conta = medidor(env, id);
  const cortesias = String(env.IA_CORTESIA || "").split(",").map((x) => x.trim().toLowerCase()).filter(Boolean);
  // Entrar abre a conta (a mesma que o PAULUS instalado usa, pela conta Google), sem segredo de instalacao.
  const aberta = await conta.pedir("abrir", { id, dono, cortesia: cortesias.includes(await sha256(dono.email)) });
  if (p === "/api/ia/site/entrar") return json(aberta);
  if (p === "/api/ia/site/plano") {
    const r = await trocarPlano(env, conta, deps.chamarMP, String(d.plano || ""));
    if (!r.ok) return r;
    return json(await conta.pedir("ler_cadastro"));
  }
  if (p === "/api/ia/site/situacao") {
    const a = aberta.assinatura;
    const mp = deps.chamarMP;
    if (a && a.id && mp) {
      const r = await mp(env, "/preapproval/" + encodeURIComponent(a.id), "GET");
      if (r.ok && r.dados && r.dados.status && r.dados.status !== a.situacao) {
        await conta.pedir("assinatura", { assinatura: { ...a, situacao: r.dados.status } });
      }
    }
    return json(await conta.pedir("ler_cadastro"));
  }
  if (p === "/api/ia/site/cadastro") {
    const c = conferirCadastro(d);
    if (c.erro) return json({ erro: c.erro }, 400);
    await conta.pedir("cadastro", { cadastro: { ...c.cadastro, quando: new Date().toISOString() } });
    if (!d.plano) return json(await conta.pedir("ler_cadastro"));
    return criarAssinatura(env, conta, id, deps.chamarMP, { email: dono.email, plano: String(d.plano), origem: "site", cupom: d.cupom });
  }
  return json({ erro: "rota não existe" }, 404);
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
  const pacote = n.recargas.find((x) => x.id === String(d.pacote || "1")) || n.recargas.find((x) => x.id === "1");
  if (d.pacote && !n.recargas.some((x) => x.id === String(d.pacote))) return json({ erro: "esse pacote de recarga não existe" }, 400);
  const valor = pacote.valor.toFixed(2);
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
    id: r.dados.id, valor, tokens: pacote.tokens, vence_em_minutos: 30,
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

/* Cada pagamento confirmado vira uma linha da fila de notas fiscais do painel
   (worker/admin.js, Notas fiscais): "admin:nfse:<id>". */
async function anotarPagamento(env, p) {
  if (!env.APOIOS) return;
  const chave = "admin:nfse:" + p.id;
  if (await env.APOIOS.get(chave)) return;
  await env.APOIOS.put(chave, JSON.stringify({ ...p, quando: new Date().toISOString(), nota: "pendente" }));
}

/* Os ultimos avisos tratados, para a Visao geral do painel: so o id da conta,
   o tipo, a situacao e o valor ("admin:avisos", os 50 mais novos). */
async function anotarAviso(env, a) {
  if (!env.APOIOS) return;
  let lista = [];
  try {
    lista = JSON.parse((await env.APOIOS.get("admin:avisos")) || "[]");
  } catch {
    lista = [];
  }
  lista.unshift({ ...a, quando: new Date().toISOString() });
  await env.APOIOS.put("admin:avisos", JSON.stringify(lista.slice(0, 50)));
}

/* O aviso do Mercado Pago (worker/index.js, registrarAviso) que e da nuvem:
   true quando tratou, false quando nao e daqui (e entao o aviso e ignorado). */
export async function avisoDaIA(env, tipo, dados, mp) {
  if (!env.CONTAS_IA) return false;
  const ref = String((dados && dados.external_reference) || "");
  if (tipo === "order") {
    const m = ref.match(/^ia-recarga-([0-9a-f]{24})-/);
    if (!m) return false;
    if (dados.status === "processed") await medidor(env, m[1]).pedir("creditar", { pedido: String(dados.id), valor: Number(dados.total_amount) || 0 });
    if (dados.status === "processed") await anotarPagamento(env, { id: String(dados.id), conta: m[1], tipo: "recarga pix", valor: Number(dados.total_amount) || 0 });
    await anotarAviso(env, { conta: m[1], tipo: "order · pix", status: String(dados.status || ""), valor: Number(dados.total_amount) || 0 });
    return true;
  }
  if (tipo === "preapproval") {
    const m = ref.match(/^ia-assinatura-([0-9a-f]{24})$/);
    if (!m) return false;
    await medidor(env, m[1]).pedir("assinatura", { assinatura: { id: String(dados.id), situacao: dados.status, valor: (dados.auto_recurring || {}).transaction_amount } });
    await anotarAviso(env, { conta: m[1], tipo: "preapproval", status: String(dados.status || ""), valor: Number((dados.auto_recurring || {}).transaction_amount) || 0 });
    return true;
  }
  if (tipo === "cobranca") {
    // A cobranca mensal so traz o id da assinatura: a referencia vem dela.
    const pre = await mp(env, "/preapproval/" + encodeURIComponent(dados.preapproval_id || ""), "GET");
    const m = String((pre.ok && pre.dados && pre.dados.external_reference) || "").match(/^ia-assinatura-([0-9a-f]{24})$/);
    if (!m) return false;
    const pagamento = dados.payment || {};
    await anotarAviso(env, { conta: m[1], tipo: "authorized_payment", status: String(pagamento.status || dados.status || ""), valor: Number(dados.transaction_amount) || 0 });
    if (pagamento.status === "approved" && dados.id) {
      const r = await medidor(env, m[1]).pedir("renovar", { cobranca: String(dados.id), quando: dados.debit_date || dados.date_created || "",
        valor: Number(dados.transaction_amount) || 0 });
      await anotarPagamento(env, { id: String(dados.id), conta: m[1], tipo: "mensalidade", valor: Number(dados.transaction_amount) || 0 });
      // O cupom acabou: a proxima cobranca volta ao valor cheio do plano.
      if (r && r.cupom && r.cupom.voltar && pre.dados && pre.dados.id) {
        const v = await mp(env, "/preapproval/" + encodeURIComponent(pre.dados.id), "PUT",
          { auto_recurring: { transaction_amount: r.cupom.valor_cheio, currency_id: "BRL" } });
        if (v.ok) await medidor(env, m[1]).pedir("cupom_voltou", {});
      }
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
    const conta = nova || c;
    // O painel admin precisa saber que contas existem (um Durable Object nao
    // se lista): cada conta se anota uma vez no KV, na primeira vez que e usada.
    if (conta && conta.id && !conta.indexado && this.env && this.env.APOIOS) {
      try {
        await this.env.APOIOS.put("admin:conta:" + conta.id, JSON.stringify({ id: conta.id, criada: conta.criada || "" }));
        conta.indexado = true;
        await this.state.storage.put("conta", conta);
      } catch {
        // sem o KV agora: anota na proxima
      }
    } else if (nova) {
      await this.state.storage.put("conta", nova);
    }
    return new Response(JSON.stringify(resposta), { headers: { "content-type": "application/json" } });
  }

  /* -> [resposta, conta nova (ou null se nada mudou)]. Sem I/O: o teste chama direto. */
  fazer(acao, c, d, n) {
    const agora = this.agora();
    if ((acao === "ativar" || acao === "abrir") && c && c.desvinculado) {
      return [{ ok: false, erro: "esta conta Google foi desvinculada da nuvem do PAULUS; fale com contato@paulus.ia.br", status: 403 }, null];
    }
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
    if (acao === "abrir") {
      // O cadastro pelo site: a mesma conta (pela conta Google), sem segredo
      // de instalacao - o PAULUS instalado entra depois, com o "ativar".
      const conta = c || { id: d.id, criada: new Date(agora).toISOString(), segredos: [], extra: 0, reservas: {}, recargas: [], cobrancas: [], uso: [] };
      conta.dono = d.dono;
      conta.cortesia = Boolean(d.cortesia);
      this.vigente(conta, n, agora);
      return [{ ...this.resumo(conta, n, agora), cadastro: conta.cadastro || null }, conta];
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
      this.gastar(conta, Math.max(0, Math.round(Number(d.tokens) || 0)), { entrada: d.entrada, saida: d.saida, modelo: d.modelo });
      return [{ ok: true, restantes: this.restantes(conta, n, agora) }, conta];
    }
    if (acao === "cadastro") {
      conta.cadastro = d.cadastro;
      conta.nome = d.cadastro.nome_escritorio || conta.nome || "";
      return [{ ...this.resumo(conta, n, agora), cadastro: conta.cadastro }, conta];
    }
    if (acao === "ler_cadastro") return [{ ...this.resumo(conta, n, agora), cadastro: conta.cadastro || null }, null];
    if (acao === "plano_proximo") {
      // O plano de agora de novo: desfaz a troca marcada.
      if (d.plano === planoDe(n, conta.plano).id) delete conta.plano_proximo;
      else conta.plano_proximo = d.plano;
      if (conta.assinatura) conta.assinatura.valor = d.valor;
      return [this.resumo(conta, n, agora), conta];
    }
    if (acao === "assinatura") {
      // O plano escolhido entra com a assinatura nova; o ciclo aberto continua o dele.
      if (d.plano) conta.plano = d.plano;
      if (d.cupom !== undefined) conta.cupom = d.cupom || null;
      const antes = conta.assinatura || {};
      conta.assinatura = { ...antes, ...d.assinatura, desde: antes.desde || new Date(agora).toISOString() };
      // Cartao posto e aceito: o primeiro ciclo comeca agora; a cobranca do
      // Mercado Pago, que vem em seguida, so confirma (renovar e idempotente).
      if (conta.assinatura.situacao === "authorized" && !this.cicloAberto(conta, agora)) this.abrirCiclo(conta, n, agora, "assinatura");
      // O brinde do cupom entra uma vez, quando a assinatura fica ativa.
      if (conta.assinatura.situacao === "authorized" && conta.cupom && conta.cupom.brinde > 0 && !conta.cupom.brinde_dado) {
        conta.extra = (conta.extra || 0) + Math.round(conta.cupom.brinde);
        conta.cupom.brinde_dado = true;
      }
      return [this.resumo(conta, n, agora), conta];
    }
    if (acao === "renovar") {
      conta.cobrancas = conta.cobrancas || [];
      if (conta.cobrancas.includes(d.cobranca)) return [this.resumo(conta, n, agora), null];
      conta.cobrancas = [...conta.cobrancas, d.cobranca].slice(-36);
      const quando = Date.parse(d.quando || "") || agora;
      conta.pagamentos = [...(conta.pagamentos || []), { tipo: "assinatura", ref: d.cobranca,
        valor: Number(d.valor) || (conta.assinatura || {}).valor || planoDe(n, conta.plano).valor, quando: new Date(quando).toISOString() }].slice(-60);
      if (conta.cupom) conta.cupom.cobrados = (conta.cupom.cobrados || 0) + 1;
      // A primeira cobranca logo depois da assinatura e a do ciclo que acabou
      // de abrir; as outras abrem o ciclo seguinte.
      const aberto = this.cicloAberto(conta, agora);
      if (aberto && aberto.origem === "assinatura" && !aberto.cobranca && quando - Date.parse(aberto.inicio) < 3 * 24 * 3600 * 1000) {
        aberto.cobranca = d.cobranca;
      } else {
        // A troca de plano marcada vale a partir deste ciclo, o primeiro cobrado no valor novo.
        if (conta.plano_proximo) {
          conta.plano = conta.plano_proximo;
          delete conta.plano_proximo;
        }
        this.abrirCiclo(conta, n, Math.min(quando, agora), "cobranca", d.cobranca);
      }
      return [this.resumo(conta, n, agora), conta];
    }
    if (acao === "creditar") {
      conta.recargas = conta.recargas || [];
      if (conta.recargas.some((r) => r.pedido === d.pedido)) return [this.resumo(conta, n, agora), null];
      // Os tokens pelo valor pago, no preco por token da recarga: vale para
      // qualquer pacote, e para o Pix criado antes dos pacotes.
      const pago = Number(d.valor) || 0;
      const tokens = pago > 0 ? Math.round((pago / n.recargaValor) * n.recargaTokens) : n.recargaTokens;
      conta.extra = (conta.extra || 0) + tokens;
      conta.recargas = [...conta.recargas, { pedido: d.pedido, tokens, valor: d.valor, quando: new Date(agora).toISOString() }].slice(-50);
      conta.pagamentos = [...(conta.pagamentos || []), { tipo: "recarga", ref: d.pedido, valor: pago, quando: new Date(agora).toISOString() }].slice(-60);
      return [this.resumo(conta, n, agora), conta];
    }
    if (acao === "cupom_voltou") {
      if (conta.cupom) conta.cupom.voltou = true;
      return [this.resumo(conta, n, agora), conta];
    }
    // O que o PAULUS instalado conta da conta Google dele (so o nome dos
    // servicos ligados) e a confirmacao de que cumpriu a ordem do painel.
    if (acao === "google_relatar") {
      const escopos = (Array.isArray(d.escopos) ? d.escopos : []).map(String).filter((x) => /^[a-z.:\/_-]{2,60}$/i.test(x)).slice(0, 10);
      conta.google = escopos.length ? { escopos, conferido: new Date(agora).toISOString() } : null;
      if (d.aplicado && conta.google_pendente && conta.google_pendente.id === d.aplicado) delete conta.google_pendente;
      return [this.resumo(conta, n, agora), conta];
    }
    if (acao.startsWith("admin_")) return this.fazerAdmin(acao, conta, d, n, agora);
    return [{ ok: false, erro: "ação desconhecida", status: 400 }, null];
  }

  cicloAberto(conta, agora) {
    const c = conta.ciclo;
    return c && Date.parse(c.fim) > agora ? c : null;
  }

  abrirCiclo(conta, n, inicio, origem, cobranca = "") {
    // Os tokens do plano da conta; sem plano escolhido (quem assinava antes
    // dos tres planos), o Escritorio.
    const tokens = planoDe(n, conta.plano).tokens;
    conta.ciclo = { inicio: new Date(inicio).toISOString(), fim: new Date(maisUmMes(inicio)).toISOString(), tokens, usados: 0, origem };
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
  gastar(conta, tokens, det = {}) {
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
    // Entrada e saida separadas, o turno (manha, tarde, noite, no horario de
    // Brasilia) e o modelo: o painel admin conta o custo por eles.
    const brt = new Date(this.agora() - 3 * 3600 * 1000);
    const dia = brt.toISOString().slice(0, 10);
    const hora = brt.getUTCHours();
    const turno = hora < 12 ? 0 : hora < 18 ? 1 : 2;
    const saida = Math.max(0, Math.min(tokens, Math.round(Number(det.saida) || 0)));
    const entrada = tokens - saida;
    conta.uso = conta.uso || [];
    let u = conta.uso[conta.uso.length - 1];
    if (!u || u.dia !== dia) {
      u = { dia, tokens: 0 };
      conta.uso = [...conta.uso, u].slice(-62);
    }
    u.tokens += tokens;
    u.entrada = (u.entrada || 0) + entrada;
    u.saida = (u.saida || 0) + saida;
    u.turnos = u.turnos || [0, 0, 0];
    u.turnos[turno] += tokens;
    u.turnos_saida = u.turnos_saida || [0, 0, 0];
    u.turnos_saida[turno] += saida;
    if (det.modelo) {
      u.modelos = u.modelos || {};
      const m = String(det.modelo).slice(0, 80);
      u.modelos[m] = u.modelos[m] || { entrada: 0, saida: 0 };
      u.modelos[m].entrada += entrada;
      u.modelos[m].saida += saida;
    }
    // O mes inteiro, que nao sai depois de 62 dias (o "2026" do painel).
    const mes = dia.slice(0, 7);
    conta.uso_mes = conta.uso_mes || {};
    const um = (conta.uso_mes[mes] = conta.uso_mes[mes] || { entrada: 0, saida: 0, modelos: {} });
    um.entrada += entrada;
    um.saida += saida;
    if (det.modelo) {
      const m = String(det.modelo).slice(0, 80);
      um.modelos[m] = um.modelos[m] || { entrada: 0, saida: 0 };
      um.modelos[m].entrada += entrada;
      um.modelos[m].saida += saida;
    }
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
      plano: planoDe(n, conta.plano),
      // A troca marcada: vale a partir da proxima renovacao (fim do ciclo).
      plano_proximo: conta.plano_proximo ? planoDe(n, conta.plano_proximo) : null,
      planos: n.planos,
      cadastro_completo: Boolean(conta.cadastro),
      recarga: { valor: n.recargaValor, tokens: n.recargaTokens },
      recargas_pacotes: n.recargas,
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
      // A ordem do painel para o PAULUS instalado: que servicos do Google
      // continuam ligados (o resto ele desliga; nenhum: revoga o acesso todo).
      google_pendente: conta.google_pendente || null,
      cupom: conta.cupom ? { codigo: conta.cupom.codigo, desconto: conta.cupom.desconto, meses: conta.cupom.meses,
        cobrados: conta.cupom.cobrados || 0, valor_cheio: conta.cupom.valor_cheio,
        voltar: !conta.cupom.voltou && (conta.cupom.cobrados || 0) >= conta.cupom.meses } : null,
    };
  }

  /* As acoes do painel admin (worker/admin.js). Nenhuma mexe em dinheiro no
     Mercado Pago - isso e do admin.js; aqui so o que a conta guarda. */
  fazerAdmin(acao, conta, d, n, agora) {
    if (acao === "admin_detalhe") {
      return [{
        ...this.resumo(conta, n, agora), id: conta.id, criada: conta.criada || "", cadastro: conta.cadastro || null,
        instalacoes_lista: (conta.segredos || []).map((x) => ({ instalacao: x.instalacao, hash8: String(x.hash).slice(0, 8), criado: x.criado })),
        pagamentos: conta.pagamentos || [], uso: conta.uso || [], uso_mes: conta.uso_mes || {}, google: conta.google || null,
        desvinculado: conta.desvinculado || null, plano_id: conta.plano || null,
      }, null];
    }
    if (acao === "admin_creditar") {
      const tokens = Math.max(0, Math.min(1e9, Math.round(Number(d.tokens) || 0)));
      conta.extra = (conta.extra || 0) + tokens;
      conta.recargas = [...(conta.recargas || []), { pedido: "cortesia-" + agora, tokens, valor: 0, quando: new Date(agora).toISOString(), cortesia: true, por: d.por || "" }].slice(-50);
      return [this.resumo(conta, n, agora), conta];
    }
    if (acao === "admin_apagar_segredo") {
      const antes = (conta.segredos || []).length;
      conta.segredos = (conta.segredos || []).filter((x) => String(x.hash).slice(0, 8) !== String(d.hash8));
      return [{ ...this.resumo(conta, n, agora), apagados: antes - conta.segredos.length }, conta];
    }
    if (acao === "admin_google") {
      conta.google_pendente = { id: "g" + agora, ligados: (d.ligados || []).map(String).slice(0, 10), quando: new Date(agora).toISOString() };
      return [this.resumo(conta, n, agora), conta];
    }
    if (acao === "admin_desvincular") {
      // A conta Google sai da nuvem: as instalacoes param (o segredo some) e
      // a mesma conta Google nao entra de novo. Plano, tokens e historico ficam.
      conta.desvinculado = { quando: new Date(agora).toISOString(), por: d.por || "", email: (conta.dono || {}).email || "" };
      conta.segredos = [];
      return [this.resumo(conta, n, agora), conta];
    }
    if (acao === "admin_assinatura_cancelada") {
      if (conta.assinatura) conta.assinatura = { ...conta.assinatura, situacao: "cancelled" };
      return [this.resumo(conta, n, agora), conta];
    }
    return [{ ok: false, erro: "ação desconhecida", status: 400 }, null];
  }
}
