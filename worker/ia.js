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
//   POST /api/ia/assinar           o link da pagina de pagamento (paulus.ia.br/cadastro/pagamento)
//   GET  /api/ia/mp-config         a chave publica do Mercado Pago (para o formulario do cartao)
//   POST /api/ia/site/oferta|pagar o valor da assinatura e a cobranca com o token do cartao
//   GET  /api/ia/assinatura        a situacao, conferida no Mercado Pago
//   POST /api/ia/assinatura/cancelar
//   POST /api/ia/recarga           o Pix da recarga (QR)
//   GET  /api/ia/recarga/:id       pago? se sim, os tokens entram
//   POST /api/ia/sair              apaga o segredo desta instalacao
//   GET  /api/ia/nfse              as NFS-e emitidas para a conta (pela casa)
//   GET  /api/ia/nfse/:id/pdf|xml  o arquivo de uma delas
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
import { chamar as chamarEmissor, emitirAutomatico, faltaDoEmissor } from "./nfse/api.js";

const RE_SEGREDO = /^pia_([0-9a-f]{24})_([0-9a-f]{64})$/;
const MAX_SEGREDOS = 3;
// Reserva sem liquidar (o Worker caiu no meio): depois disto, conta inteira.
const RESERVA_VENCE_MS = 15 * 60 * 1000;
// Depois do fim do ciclo, com a assinatura ativa, a cobranca do mes pode
// atrasar uns dias no Mercado Pago: o plano continua valendo nesse intervalo.
export const TOLERANCIA_MS = 5 * 24 * 3600 * 1000;
// Portugues tem ~4 caracteres por token; 3 estima para cima (a reserva e teto).
const CARACTERES_POR_TOKEN = 3;

// Os modelos da nuvem (03/10/2026): o id que o PAULUS pede, o provedor que
// responde, o peso em creditos (quantos creditos da cota cada token gasta) e
// o preco em dolar por milhao de tokens (entrada, saida), que o painel usa
// para o custo. `folga`: tokens a mais na saida para o modelo pensar antes de
// escrever (o Opus 5.5 sempre pensa, e o pensamento conta como saida).
export const MODELOS = {
  "meta-llama/Llama-3.3-70B-Instruct": { nome: "Llama 3.3 70B", empresa: "Meta", provedor: "deepinfra", peso: 1, usd: [0.23, 0.4] },
  "Qwen/Qwen2.5-72B-Instruct": { nome: "Qwen 2.5 72B", empresa: "Alibaba", provedor: "deepinfra", peso: 1, usd: [0.23, 0.4] },
  "mistral-large-latest": { nome: "Mistral Large 3", empresa: "Mistral AI", provedor: "mistral", peso: 1, usd: [0.5, 1.5] },
  "claude-sonnet-5-5": { nome: "Claude Sonnet 5.5", empresa: "Anthropic", provedor: "anthropic", peso: 1, usd: [2, 10] },
  "claude-opus-5-5": { nome: "Claude Opus 5.5", empresa: "Anthropic", provedor: "anthropic", peso: 2, usd: [4, 20], folga: 4000 },
};

// A ordem da profundidade (paulus/legal/src/profundidade.py): o plano diz ate onde vai.
export const NIVEIS = ["estagiario", "bacharel", "advogado", "juiz", "ministro"];

// Os planos (03/10/2026). Cada um: o valor mensal e o anual (o anual paga o
// ano de uma vez, parcelavel no cartao; a cota continua mensal), os creditos
// do mes, as pessoas, o modelo de cada nivel ("padrao" para os outros), a
// recarga e os recursos que o PAULUS instalado libera. Nos recursos, null e
// "sem limite". IA_PLANOS (JSON, a lista publicada pelo painel admin) troca os
// numeros sem mexer no codigo; o que faltar num plano vem do de fabrica.
export const PLANO_PADRAO = "escritorio";

const RECURSOS_ESCRITORIO = { profundidade: "juiz", agentes: null, equipe: true, emails: null, consumo_por_pessoa: true,
  nfse_mes: 20, nfse_recorrente: false, datajud: true, gravacao: true, ao_vivo: false, horas: true, muralha: true,
  autonomia: true, jurisprudencia_stj: true, word: false, mcp: false, pagina_cliente: false };

export const PLANOS_DE_FABRICA = [
  { id: "advogado", nome: "Advogado", valor: 449, valor_anual: 3990, tokens: 30000000, pessoas: 1,
    modelos: { padrao: "meta-llama/Llama-3.3-70B-Instruct" }, recarga: { valor: 50, tokens: 10000000 },
    recursos: { ...RECURSOS_ESCRITORIO, profundidade: "advogado", agentes: 3, equipe: false, emails: 1, consumo_por_pessoa: false,
      nfse_mes: 0, datajud: false, gravacao: false, horas: false, muralha: false, autonomia: false, jurisprudencia_stj: false } },
  { id: PLANO_PADRAO, nome: "Escritório", valor: 1290, valor_anual: 11490, tokens: 60000000, pessoas: 5,
    modelos: { padrao: "mistral-large-latest" }, recarga: { valor: 120, tokens: 10000000 }, recursos: { ...RECURSOS_ESCRITORIO } },
  { id: "plus", nome: "Escritório Plus", valor: 3490, valor_anual: 30990, tokens: 40000000, pessoas: 15,
    modelos: { padrao: "claude-sonnet-5-5", ministro: "claude-opus-5-5" }, recarga: { valor: 300, tokens: 5000000 },
    recursos: { ...RECURSOS_ESCRITORIO, profundidade: "ministro", nfse_mes: null, nfse_recorrente: true, ao_vivo: true,
      word: true, mcp: true, pagina_cliente: true } },
];

/* Um plano completo: o publicado por cima do de fabrica do mesmo id (ou do Escritorio, se for novo). */
function planoCompleto(p) {
  const base = PLANOS_DE_FABRICA.find((x) => x.id === p.id) || PLANOS_DE_FABRICA.find((x) => x.id === PLANO_PADRAO);
  const modelos = { ...base.modelos, ...(p.modelos || {}) };
  for (const [nivel, m] of Object.entries(modelos)) if (!MODELOS[m]) modelos[nivel] = base.modelos[nivel] || base.modelos.padrao;
  return {
    id: p.id, nome: String(p.nome || base.nome), valor: Number(p.valor) || base.valor, valor_anual: Number(p.valor_anual) || base.valor_anual,
    tokens: Number(p.tokens) || base.tokens, pessoas: Number(p.pessoas) || base.pessoas, modelos,
    recarga: { ...base.recarga, ...(p.recarga || {}) }, recursos: { ...base.recursos, ...(p.recursos || {}) },
  };
}

function lerPlanos(env) {
  try {
    const l = JSON.parse(env.IA_PLANOS || "");
    // A lista de antes dos planos de 03/10 (sem valor anual) nao vale mais: fica a de fabrica.
    const ok = Array.isArray(l) && l.length && l.every((p) => p && /^[a-z0-9-]{2,24}$/.test(p.id) && p.nome && Number(p.valor) > 0
      && Number(p.valor_anual) > 0 && Number(p.tokens) > 0);
    if (ok && l.some((p) => p.id === PLANO_PADRAO)) return l.map(planoCompleto);
  } catch {
    // sem a lista (ou quebrada): a de fabrica
  }
  return PLANOS_DE_FABRICA.map(planoCompleto);
}

export function planoDe(n, id) {
  return n.planos.find((p) => p.id === id) || n.planos.find((p) => p.id === PLANO_PADRAO) || n.planos[0];
}

/* Os pacotes da recarga de um plano: metade, a recarga do plano e o dobro, no mesmo preco por credito. */
export function recargasDe(plano) {
  return [0.5, 1, 2].map((f) => ({ id: String(f), tokens: Math.round(plano.recarga.tokens * f), valor: Math.round(plano.recarga.valor * f * 100) / 100 }));
}

/* Os modelos de um plano, sem repetir, o padrao primeiro. */
export function modelosDoPlano(plano) {
  return [...new Set([plano.modelos.padrao, ...Object.values(plano.modelos)])];
}

/* Ate quando vale a primeira semana da assinatura (ISO), ou "" fora dela: nela,
   so o modelo principal do plano responde. A cortesia nao tem a trava. */
export function primeiraSemanaAte(resumo) {
  const a = (resumo && resumo.assinatura) || {};
  if (!resumo || resumo.cortesia || !a.desde) return "";
  const ate = Date.parse(a.desde) + 7 * 24 * 3600 * 1000;
  const agora = Date.parse(resumo.agora || "") || Date.now();
  return agora < ate ? new Date(ate).toISOString() : "";
}

/* O modelo que responde: o do nivel no plano; senao o pedido, se o plano o
   tem; senao o padrao do plano (o PAULUS antigo pede sempre o Llama). */
export function modeloParaPedido(plano, pedido, nivel) {
  if (nivel && plano.modelos[nivel]) return plano.modelos[nivel];
  if (pedido && modelosDoPlano(plano).includes(pedido)) return pedido;
  return plano.modelos.padrao;
}

export function numeros(env) {
  const n = (v, padrao) => (Number.isFinite(Number(v)) && Number(v) > 0 ? Number(v) : padrao);
  const planos = lerPlanos(env);
  const padrao = planoDe({ planos }, PLANO_PADRAO);
  return {
    planos,
    // A recarga do Escritorio, para quem ainda le um numero so (o painel, o PAULUS antigo).
    recargaValor: padrao.recarga.valor,
    recargaTokens: padrao.recarga.tokens,
    recargas: recargasDe(padrao),
    maxSaida: n(env.IA_MAX_SAIDA, 4000),
    maxEntradaCaracteres: n(env.IA_MAX_ENTRADA_CARACTERES, 240000),
    porMinuto: n(env.IA_POR_MINUTO, 40),
    modelos: Object.keys(MODELOS),
  };
}

/* Os modelos para a tela: id, nome e empresa. */
export function catalogo(ids) {
  return ids.filter((m) => MODELOS[m]).map((m) => ({ id: m, nome: MODELOS[m].nome, empresa: MODELOS[m].empresa }));
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
    const r = await conferirCupom(env, url.searchParams.get("codigo"), url.searchParams.get("plano"), url.searchParams.get("periodo") === "anual" ? "anual" : "mensal");
    return json(r.erro ? { ok: false, erro: r.erro } : { ok: true, ...r.cupom, valor: r.valor, valor_cheio: r.valor_cheio });
  }
  // A chave publica do Mercado Pago, para o formulario do cartao da pagina de
  // pagamento. Nao e segredo (o token de acesso fica so aqui, como segredo).
  if (p === "/api/ia/mp-config" && m === "GET") {
    if (!env.MP_PUBLIC_KEY) return json({ erro: "a chave pública do Mercado Pago não está configurada" }, 503);
    return new Response(JSON.stringify({ publicKey: env.MP_PUBLIC_KEY }), {
      status: 200, headers: { "content-type": "application/json; charset=utf-8", "cache-control": "no-store, max-age=0" } });
  }
  if (p === "/api/ia/planos" && m === "GET") {
    const n = numeros(env);
    return json({ planos: n.planos.map((x) => ({ ...x, modelos_info: catalogo(modelosDoPlano(x)), recargas: recargasDe(x) })),
      recarga: { valor: n.recargaValor, tokens: n.recargaTokens }, recargas: n.recargas, niveis: NIVEIS });
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
  if (p === "/api/ia/conta" && m === "GET") return json(await comDesistencia(env, conta, await conta.pedir("resumo")));
  // Os modelos do plano desta conta (o padrao primeiro), com nome e empresa.
  if (p === "/api/ia/modelos" && m === "GET") {
    const r = await conta.pedir("resumo");
    const ids = modelosDoPlano(r.plano);
    return json({ modelos: ids, info: catalogo(ids) });
  }
  if (p === "/api/ia/desistir" && m === "POST") return desistir(env, conta, quem.id, deps.chamarMP, "o cliente, pelo PAULUS");
  if (p === "/api/ia/adiantar" && m === "POST") {
    const r = await conta.pedir("adiantar");
    return json(r, r.ok === false ? r.status || 409 : 200);
  }
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
  // As NFS-e que o PAVLVS emitiu para esta conta (o emissor da nuvem grava por worker/nfse-casa.js).
  if (p === "/api/ia/nfse" && m === "GET") return json({ notas: await notasDoCliente(env, quem.id) });
  const nf = p.match(/^\/api\/ia\/nfse\/([A-Za-z0-9_.-]{1,64})\/(pdf|xml)$/);
  if (nf && m === "GET") return arquivoDoCliente(env, quem.id, nf[1], nf[2]);
  return json({ erro: "rota não existe" }, 404);
}

// --------------------------------------------- as NFS-e da conta
// Gravadas pela ponte da casa (worker/nfse-casa.js) em "nfse:nota:<conta>:<id>"
// e os arquivos em "nfse:nota-pdf:..." e "nfse:nota-xml:..." (base64).

/* As notas da conta, para GET /api/ia/nfse (sem os arquivos). */
async function notasDoCliente(env, conta) {
  if (!env.APOIOS) return [];
  const notas = [];
  const chaves = [];
  let cursor;
  do {
    const lista = await env.APOIOS.list({ prefix: "nfse:nota:" + conta + ":", cursor });
    for (const k of lista.keys) chaves.push(k.name);
    cursor = lista.list_complete ? undefined : lista.cursor;
  } while (cursor);
  for (const k of chaves) {
    const x = await lerKV(env, k);
    if (!x || x.conta !== conta) continue;
    notas.push({ id: x.id, numero: x.numero, competencia: x.competencia, valor: x.valor, descricao: x.descricao, emitida_em: x.emitida_em, ambiente: x.ambiente, cancelada: Boolean(x.cancelada) });
  }
  notas.sort((a, b) => String(b.emitida_em).localeCompare(String(a.emitida_em)));
  return notas;
}

/* O PDF ou o XML de uma nota da conta, como Response; 404 se nao houver. */
async function arquivoDoCliente(env, conta, id, tipo) {
  if (!env.APOIOS || !/^[A-Za-z0-9_.-]{1,64}$/.test(id) || !["pdf", "xml"].includes(tipo)) return json({ erro: "não encontrado" }, 404);
  const meta = await lerKV(env, "nfse:nota:" + conta + ":" + id);
  if (!meta || meta.conta !== conta) return json({ erro: "essa nota não existe" }, 404);
  const b64 = await env.APOIOS.get("nfse:nota-" + tipo + ":" + conta + ":" + id);
  if (!b64) return json({ erro: "essa nota não tem " + tipo.toUpperCase() }, 404);
  const bin = atob(b64);
  const bytes = new Uint8Array(bin.length);
  for (let i = 0; i < bin.length; i++) bytes[i] = bin.charCodeAt(i);
  const nome = "NFS-e " + (meta.numero || id) + "." + tipo;
  return new Response(bytes, {
    status: 200,
    headers: {
      "content-type": tipo === "pdf" ? "application/pdf" : "application/xml",
      "content-disposition": 'attachment; filename="' + nome.replace(/[^A-Za-z0-9 ._-]/g, "_") + '"',
      "cache-control": "no-store",
    },
  });
}

async function lerKV(env, chave) {
  try {
    const v = await env.APOIOS.get(chave);
    return v ? JSON.parse(v) : null;
  } catch {
    return null;
  }
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

export async function autenticar(request, env) {
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

// Os provedores: a chave de cada um e segredo do Worker (npx wrangler secret
// put DEEPINFRA_KEY / MISTRAL_KEY / ANTHROPIC_KEY). Os tres falam ao PAULUS
// no formato OpenAI: o do Claude e traduzido aqui (claudeParaOpenAI).
const PROVEDORES = {
  deepinfra: { url: "https://api.deepinfra.com/v1/openai/chat/completions", chave: "DEEPINFRA_KEY" },
  mistral: { url: "https://api.mistral.ai/v1/chat/completions", chave: "MISTRAL_KEY" },
  anthropic: { url: "https://api.anthropic.com/v1/messages", chave: "ANTHROPIC_KEY" },
};

/* O pedido no formato do Claude: o system a parte, os papeis alternados e o
   ultimo do usuario (o Claude 5.5 nao aceita resposta comecada). */
export function pedidoParaClaude(modelo, mensagens, maxTokens, stream, jsonPedido) {
  const system = mensagens.filter((x) => x.role === "system").map((x) => x.content).join("\n\n");
  const msgs = [];
  for (const x of mensagens.filter((y) => y.role !== "system")) {
    const ultima = msgs[msgs.length - 1];
    if (ultima && ultima.role === x.role) ultima.content += "\n\n" + x.content;
    else msgs.push({ role: x.role, content: x.content });
  }
  while (msgs.length && msgs[0].role !== "user") msgs.shift();
  while (msgs.length && msgs[msgs.length - 1].role !== "user") msgs.pop();
  const corpo = { model: modelo, max_tokens: maxTokens, messages: msgs, stream, fallbacks: "default" };
  const instrucao = system + (jsonPedido ? "\n\nResponda somente com um objeto JSON válido, sem texto antes ou depois." : "");
  if (instrucao.trim()) corpo.system = instrucao.trim();
  // O Sonnet responde sem pensar antes (o dia a dia, mais barato); o Opus, que
  // e o do nivel Ministro, pensa com esforco alto.
  if (modelo === "claude-sonnet-5-5") corpo.thinking = { type: "between_tools" };
  if (modelo === "claude-opus-5-5") corpo.output_config = { effort: "high" };
  return corpo;
}

function usoDoClaude(u) {
  const x = u || {};
  return { entrada: (Number(x.input_tokens) || 0) + (Number(x.cache_creation_input_tokens) || 0) + (Number(x.cache_read_input_tokens) || 0),
    saida: Number(x.output_tokens) || 0 };
}

/* A resposta inteira do Claude no formato OpenAI; null se ele recusou. */
export function respostaDoClaude(dado) {
  if (!dado || dado.stop_reason === "refusal") return null;
  const texto = (dado.content || []).filter((b) => b && b.type === "text").map((b) => b.text || "").join("");
  const u = usoDoClaude(dado.usage);
  return { id: dado.id, model: dado.model, choices: [{ index: 0, message: { role: "assistant", content: texto }, finish_reason: dado.stop_reason === "max_tokens" ? "length" : "stop" }],
    usage: { prompt_tokens: u.entrada, completion_tokens: u.saida } };
}

/* Os eventos do Claude (message_start, content_block_delta, message_delta,
   message_stop) viram os pedacos do OpenAI, com o uso no fim - o mesmo que o
   DeepInfra manda, e o PAULUS ja le. */
export function claudeParaOpenAI() {
  const enc = new TextEncoder();
  const dec = new TextDecoder();
  let resto = "";
  let uso = { entrada: 0, saida: 0 };
  let modelo = "";
  let fechado = false;
  const pedaco = (obj) => enc.encode("data: " + JSON.stringify(obj) + "\n\n");
  const fim = (c) => {
    if (fechado) return;
    fechado = true;
    c.enqueue(pedaco({ model: modelo, choices: [], usage: { prompt_tokens: uso.entrada, completion_tokens: uso.saida } }));
    c.enqueue(enc.encode("data: [DONE]\n\n"));
  };
  const linha = (l, c) => {
    if (!l.startsWith("data:")) return;
    let e;
    try {
      e = JSON.parse(l.slice(5).trim());
    } catch {
      return;
    }
    if (e.type === "message_start" && e.message) {
      modelo = e.message.model || modelo;
      uso = usoDoClaude(e.message.usage);
    } else if (e.type === "content_block_delta" && e.delta && e.delta.type === "text_delta") {
      c.enqueue(pedaco({ model: modelo, choices: [{ index: 0, delta: { content: e.delta.text || "" } }] }));
    } else if (e.type === "message_delta") {
      if (e.usage && Number.isFinite(Number(e.usage.output_tokens))) uso.saida = Number(e.usage.output_tokens);
      if (e.delta && e.delta.stop_reason === "refusal") {
        c.enqueue(pedaco({ model: modelo, choices: [{ index: 0, delta: { content: "\n\n(O provedor do modelo interrompeu esta resposta.)" }, finish_reason: "content_filter" }] }));
      }
    } else if (e.type === "message_stop") {
      fim(c);
    }
  };
  return new TransformStream({
    transform(chunk, c) {
      resto += dec.decode(chunk, { stream: true });
      const linhas = resto.split("\n");
      resto = linhas.pop();
      for (const l of linhas) linha(l.trim(), c);
    },
    flush(c) {
      if (resto.trim()) linha(resto.trim(), c);
      fim(c);
    },
  });
}

/* O pedido ao provedor do modelo; a resposta sempre no formato OpenAI (ou o erro dele). */
async function chamarProvedor(env, modelo, corpoOpenAI) {
  const info = MODELOS[modelo];
  const prov = PROVEDORES[info.provedor];
  const chave = env[prov.chave];
  if (info.provedor !== "anthropic") {
    const corpo = { ...corpoOpenAI };
    // O DeepInfra so manda o uso no fim quando pedido; a Mistral manda sempre.
    if (corpo.stream && info.provedor === "deepinfra") corpo.stream_options = { include_usage: true };
    return fetch(prov.url, { method: "POST", headers: { Authorization: "Bearer " + chave, "Content-Type": "application/json" }, body: JSON.stringify(corpo) });
  }
  const corpo = pedidoParaClaude(modelo, corpoOpenAI.messages, corpoOpenAI.max_tokens, corpoOpenAI.stream, Boolean(corpoOpenAI.response_format));
  const up = await fetch(prov.url, {
    method: "POST",
    headers: { "x-api-key": chave, "anthropic-version": "2023-06-01", "anthropic-beta": "server-side-fallback-2026-07-01", "content-type": "application/json" },
    body: JSON.stringify(corpo),
  });
  if (!up.ok) return up;
  if (corpoOpenAI.stream) return new Response(up.body.pipeThrough(claudeParaOpenAI()), { status: 200, headers: { "content-type": "text/event-stream" } });
  const convertido = respostaDoClaude(await up.json());
  if (!convertido) return new Response(JSON.stringify({ error: { message: "o modelo recusou responder a este pedido" } }), { status: 422 });
  return new Response(JSON.stringify(convertido), { status: 200, headers: { "content-type": "application/json" } });
}

/* Tokens -> creditos da cota, pelo peso do modelo. */
const creditos = (modelo, entrada, saida) => Math.ceil((entrada + saida) * ((MODELOS[modelo] || {}).peso || 1));

async function completar(request, env, ctx, conta) {
  const n = numeros(env);
  const d = await lerJSON(request);
  if (!d || !Array.isArray(d.messages) || !d.messages.length) return json({ erro: "pedido inválido" }, 400);
  const pedido = String(d.model || "");
  if (pedido && !MODELOS[pedido]) return json({ erro: "esse modelo não está na nuvem do PAULUS", modelos: n.modelos }, 400);
  // O plano da conta diz o modelo e ate que nivel de profundidade vai.
  const atual = await conta.pedir("resumo");
  const plano = atual.plano;
  const nivel = NIVEIS.includes(String(d.paulus_nivel || "")) ? String(d.paulus_nivel) : "";
  if (nivel && NIVEIS.indexOf(nivel) > NIVEIS.indexOf(plano.recursos.profundidade)) {
    const quem = n.planos.find((x) => NIVEIS.indexOf(x.recursos.profundidade) >= NIVEIS.indexOf(nivel));
    return json({ erro: "a profundidade " + nivel + " não faz parte do plano " + plano.nome + (quem ? "; ela vem no plano " + quem.nome : ""),
      motivo: "profundidade" }, 403);
  }
  let modelo = modeloParaPedido(plano, pedido, nivel);
  // Nos 7 primeiros dias da assinatura (o prazo de arrependimento), so o modelo
  // principal do plano: no Plus, o Sonnet; o Opus libera no 8o dia.
  const travadoAte = primeiraSemanaAte(atual);
  let aviso = "";
  if (travadoAte && modelo !== plano.modelos.padrao) {
    aviso = (MODELOS[modelo] || {}).nome + " libera no 8º dia da assinatura (" + dataBR(travadoAte) + "); até lá, responde o " + (MODELOS[plano.modelos.padrao] || {}).nome;
    modelo = plano.modelos.padrao;
  }
  const info = MODELOS[modelo];
  const peso = info.peso || 1;
  const mensagens = d.messages
    .filter((x) => x && ["system", "user", "assistant"].includes(x.role))
    .map((x) => ({ role: x.role, content: String(x.content || "") }));
  const tamanho = caracteres(mensagens);
  if (tamanho > n.maxEntradaCaracteres) {
    return json({ erro: "o texto passa do teto de um pedido; mande menos trechos", teto: n.maxEntradaCaracteres }, 413);
  }
  const entrada = Math.ceil(tamanho / CARACTERES_POR_TOKEN) + 16 * mensagens.length;
  const pedida = Math.min(Math.max(Number(d.max_tokens) || n.maxSaida, 1), n.maxSaida) + (info.folga || 0);
  // A reserva e em creditos; a saida que o modelo pode escrever sai dela.
  const reserva = await conta.pedir("reservar", { entrada: Math.ceil(entrada * peso), saida: Math.ceil(pedida * peso) });
  if (!reserva.ok) return json({ erro: reserva.erro, motivo: reserva.motivo, conta: reserva.conta }, reserva.status || 402);
  if (!env[PROVEDORES[info.provedor].chave]) {
    await conta.pedir("liquidar", { reserva: reserva.id, tokens: 0 });
    return json({ erro: "o modelo " + info.nome + " ainda não está no ar na nuvem do PAULUS" }, 503);
  }
  const maxTokens = Math.max(1, Math.floor(reserva.saida / peso));

  const stream = d.stream !== false;
  const corpo = { model: modelo, messages: mensagens, max_tokens: maxTokens, stream };
  if (info.provedor !== "anthropic") for (const k of ["temperature", "top_p"]) if (Number.isFinite(Number(d[k]))) corpo[k] = Number(d[k]);
  if (d.response_format && d.response_format.type === "json_object") corpo.response_format = { type: "json_object" };
  const cabecalhos = { "cache-control": "no-store", "x-paulus-modelo": modelo };
  if (aviso) cabecalhos["x-paulus-aviso"] = encodeURIComponent(aviso);

  let up;
  try {
    up = await chamarProvedor(env, modelo, corpo);
  } catch (e) {
    await conta.pedir("liquidar", { reserva: reserva.id, tokens: 0 });
    return json({ erro: "o provedor do modelo não respondeu" }, 502);
  }
  if (!up.ok) {
    await conta.pedir("liquidar", { reserva: reserva.id, tokens: 0 });
    let msg = "";
    try {
      const e = await up.json();
      msg = String((e.error && (e.error.message || e.error)) || e.detail || e.message || "").slice(0, 160);
    } catch {
      msg = "";
    }
    return json({ erro: "o provedor do modelo recusou" + (msg ? ": " + msg : ""), status_provedor: up.status }, up.status >= 500 ? 502 : 400);
  }

  if (!stream) {
    const dado = await up.json();
    const u = dado.usage || {};
    const ent = Number(u.prompt_tokens) || entrada;
    const sai = Number(u.completion_tokens) || 0;
    const real = creditos(modelo, ent, sai);
    const fim = await conta.pedir("liquidar", { reserva: reserva.id, tokens: real, entrada: ent, saida: sai, modelo });
    dado.paulus = { tokens: real, restantes: fim.restantes, modelo };
    return new Response(JSON.stringify(dado), { status: 200, headers: { "content-type": "application/json; charset=utf-8", ...cabecalhos } });
  }

  // Passa os pedacos como vieram. No fim (ou se o PAULUS fechar no meio, o
  // "parar" da conversa), liquida pelo uso que o provedor mandou; sem ele,
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
    const ent = u ? u.entrada : entrada;
    const sai = u ? u.saida : pedacos;
    try {
      await conta.pedir("liquidar", { reserva: reserva.id, tokens: creditos(modelo, ent, sai), entrada: ent, saida: sai, modelo });
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
        // o provedor ja tinha fechado
      }
      await liquidar();
    },
  });
  return new Response(saida, { status: 200, headers: { "content-type": "text/event-stream; charset=utf-8", ...cabecalhos } });
}

// ------------------------------------------------------------- cobranca

async function assinar(request, env, conta, id, mp) {
  const d = (await lerJSON(request)) || {};
  return json(await linkDoPagamento(env, conta, { plano: d.plano, periodo: d.periodo }));
}

// O anual pode ser renovado nos ultimos 45 dias: o ano novo comeca no fim do pago.
const RENOVA_ANUAL_MS = 45 * 24 * 3600 * 1000;
// Os periodos pagos de uma vez, sem renovar sozinhos: o anual (cartao ou Pix)
// e o mes avulso (Pix). Vale ate pago_ate; cada mes abre o seu ciclo.
const PREPAGOS = ["anual", "avulso"];
const prepago = (periodo) => PREPAGOS.includes(periodo);
// O Pix vence em 30 minutos; depois, gera-se outro.
const PIX_VENCE_MS = 30 * 60 * 1000;
const PAGINA_DO_PAGAMENTO = "https://paulus.ia.br/cadastro/pagamento/";

/* O PAULUS instalado nao cobra: ele abre a pagina de pagamento do site, onde
   o cartao e digitado nos campos seguros do Mercado Pago (CardForm), na conta
   Google de quem assina. Volta o endereco com o plano e o periodo. */
async function linkDoPagamento(env, conta, { plano, periodo }) {
  const atual = await conta.pedir("resumo");
  const n = numeros(env);
  const escolhido = planoDe(n, plano || (atual.plano || {}).id);
  const p = periodo === "anual" ? "anual" : "mensal";
  return { link: PAGINA_DO_PAGAMENTO + "?plano=" + encodeURIComponent(escolhido.id) + "&periodo=" + p, plano: escolhido, periodo: p };
}

/* O que a assinatura pedida custa, conferido no servidor: o plano, o periodo,
   o meio (cartao ou Pix), o valor (com o cupom) e por que nao pode, se nao
   puder. Usado pela pagina de pagamento (o total que ela mostra) e pela
   cobranca. No Pix, o mensal e um mes avulso: vale ate vencer e nao renova. */
async function ofertaDoPagamento(env, atual, { plano, periodo, cupom, meio }) {
  if (!["mensal", "anual"].includes(periodo)) return { erro: "o período é mensal ou anual", status: 400 };
  const n = numeros(env);
  if (!n.planos.some((x) => x.id === plano)) return { erro: "esse plano não existe", status: 400 };
  const escolhido = planoDe(n, plano);
  const anual = periodo === "anual";
  const pix = meio === "pix";
  const a = atual.assinatura;
  if (atual.cortesia && atual.plano_vigente) return { erro: "esta conta tem o plano de cortesia: não há o que pagar", status: 409 };
  if (a && a.situacao === "authorized") {
    if (prepago(atual.periodo)) {
      const ate = dataBR(atual.pago_ate);
      if (!anual && !pix) return { erro: "o plano está pago até " + ate + "; a assinatura mensal no cartão pode começar quando ele vencer", status: 409 };
      // A hora do medidor (a mesma do pago_ate), e nao a do Worker.
      if (Date.parse(atual.pago_ate) - (Date.parse(atual.agora || "") || Date.now()) > RENOVA_ANUAL_MS) {
        return { erro: "o plano " + (atual.periodo === "anual" ? "anual " : "") + "está pago até " + ate + "; a renovação abre 45 dias antes", status: 409 };
      }
    } else if (!anual) {
      return { erro: pix ? "a assinatura mensal no cartão já está ativa: o mês no Pix é para quem não tem a assinatura no cartão"
        : "a assinatura mensal já está ativa; para mudar de plano, use a troca de plano", status: 409 };
    }
  }
  const cheio = anual ? escolhido.valor_anual : escolhido.valor;
  let valor = cheio;
  let comCupom = null;
  if (cupom) {
    const c = await conferirCupom(env, cupom, escolhido.id, periodo);
    if (c.erro) return { erro: c.erro, status: 400 };
    comCupom = { codigo: c.cupom.codigo, desconto: c.cupom.desconto, meses: c.cupom.meses, brinde: c.cupom.brinde, valor_cheio: cheio, cobrados: 0 };
    valor = c.valor;
  }
  return { plano: escolhido, periodo, meio: pix ? "pix" : "cartao", valor, cupom: comCupom, parcelas_max: anual && !pix ? 12 : 1, meses: anual ? 12 : 1 };
}

// Os motivos de recusa do cartao, em portugues (status_detail do Mercado Pago).
const RECUSAS = {
  cc_rejected_insufficient_amount: "o cartão não tem limite suficiente para este valor",
  cc_rejected_bad_filled_security_code: "o código de segurança não confere",
  cc_rejected_bad_filled_date: "a validade do cartão não confere",
  cc_rejected_bad_filled_card_number: "o número do cartão não confere",
  cc_rejected_bad_filled_other: "confira os dados do cartão",
  cc_rejected_call_for_authorize: "o banco pede que você autorize este pagamento: ligue para ele e tente de novo",
  cc_rejected_card_disabled: "o cartão está desativado: ligue para o banco ou use outro",
  cc_rejected_duplicated_payment: "esse pagamento já foi feito há pouco: confira antes de tentar de novo",
  cc_rejected_high_risk: "o pagamento foi recusado pela análise de risco: tente outro cartão",
  cc_rejected_max_attempts: "foram muitas tentativas com este cartão: use outro",
  cc_rejected_invalid_installments: "o cartão não aceita esse número de parcelas",
  cc_rejected_blacklist: "o cartão não pode ser usado: tente outro",
};
function motivoDaRecusa(detalhe) {
  return RECUSAS[String(detalhe || "")] || "o pagamento foi recusado: confira os dados ou use outro cartão";
}

/* O que veio do formulario do cartao (o token do CardForm e o que o Mercado
   Pago precisa), conferido. O valor nunca vem daqui (ofertaDoPagamento). */
function cartaoDoFormulario(c, parcelasMax) {
  const x = c && typeof c === "object" ? c : {};
  const token = String(x.token || "");
  if (!/^[A-Za-z0-9]{16,64}$/.test(token)) return { erro: "o cartão não foi lido: digite de novo" };
  const metodo = String(x.payment_method_id || "");
  if (!/^[a-z0-9_]{2,30}$/.test(metodo)) return { erro: "a bandeira do cartão não foi reconhecida" };
  const parcelas = Math.round(Number(x.installments) || 1);
  if (parcelas < 1 || parcelas > parcelasMax) return { erro: parcelasMax === 1 ? "a assinatura mensal é sem parcelas" : "o anual vai em até " + parcelasMax + " parcelas" };
  const pagador = x.payer && typeof x.payer === "object" ? x.payer : {};
  const ident = pagador.identification && typeof pagador.identification === "object" ? pagador.identification : {};
  const tipo = String(ident.type || "").toUpperCase();
  const numero = soDigitos(ident.number);
  const identificacao = (tipo === "CPF" && cpfValido(numero)) || (tipo === "CNPJ" && cnpjValido(numero)) ? { type: tipo, number: numero } : null;
  if (!identificacao) return { erro: "o CPF ou CNPJ do titular do cartão não confere" };
  const emissor = Number(x.issuer_id);
  return { token, metodo, parcelas, identificacao, emissor: Number.isFinite(emissor) && emissor > 0 ? emissor : null };
}

/* A cobranca, com o token do cartao que o CardForm do Mercado Pago gerou na
   pagina /cadastro/pagamento. Mensal: a assinatura ja autorizada no cartao
   (/preapproval, status authorized), que o Mercado Pago cobra todo mes. Anual:
   o pagamento do ano (/v1/payments), em ate 12 parcelas, com os juros do
   parcelamento por conta de quem parcela. E o unico lugar que cria cobranca
   do plano. */
/* O plano B: se o formulario do cartao nao carregar na pagina (bloqueador,
   rede, o MercadoPago.js fora do ar), a pessoa paga na pagina do Mercado Pago.
   Mensal: a assinatura pendente (/preapproval, status pending), que vira
   autorizada quando o cartao entra la (o aviso subscription_preapproval).
   Anual: o pagamento do ano no Checkout Pro (/checkout/preferences), em ate 12
   parcelas, confirmado pelo aviso payment ou pela consulta do pendente. O
   valor e o mesmo da oferta, conferido aqui. */
async function pagarFora(env, conta, id, dono, mp, d) {
  const atual = await conta.pedir("ler_cadastro");
  if (!atual.cadastro) return json({ erro: "preencha os dados do escritório antes de pagar" }, 409);
  const oferta = await ofertaDoPagamento(env, atual, { plano: String(d.plano || ""), periodo: String(d.periodo || ""), cupom: d.cupom });
  if (oferta.erro) return json({ erro: oferta.erro }, oferta.status);
  const { plano, valor } = oferta;
  const volta = "https://paulus.ia.br/cadastro/?voltou=1";
  if (oferta.periodo === "mensal") {
    const r = await mp(env, "/preapproval", "POST", {
      reason: "PAULUS - plano " + plano.nome + (oferta.cupom ? " (cupom " + oferta.cupom.codigo + ")" : ""),
      external_reference: "ia-assinatura-" + id,
      payer_email: dono.email,
      auto_recurring: { frequency: 1, frequency_type: "months", transaction_amount: valor, currency_id: "BRL" },
      back_url: volta,
      status: "pending",
    });
    if (!r.ok || !r.dados || !r.dados.init_point) return json({ erro: "o Mercado Pago não abriu a página de assinatura: tente de novo em instantes" }, 502);
    await conta.pedir("assinatura", { plano: plano.id, cupom: oferta.cupom, assinatura: { id: String(r.dados.id), situacao: r.dados.status || "pending", valor } });
    if (oferta.cupom) await usarCupom(env, oferta.cupom.codigo);
    return json({ link: r.dados.init_point, periodo: "mensal" });
  }
  const ref = "ia-anual-" + id + "-" + plano.id + "-" + aleatorio(4);
  const r = await mp(env, "/checkout/preferences", "POST", {
    items: [{ id: "paulus-" + plano.id + "-anual", title: "PAULUS - plano " + plano.nome + " (anual)", quantity: 1, unit_price: valor, currency_id: "BRL" }],
    payer: { email: dono.email },
    external_reference: ref,
    payment_methods: { installments: 12 },
    back_urls: { success: volta, pending: volta, failure: volta },
    auto_return: "approved",
    statement_descriptor: "PAULUS",
  });
  if (!r.ok || !r.dados || !r.dados.init_point) return json({ erro: "o Mercado Pago não abriu a página de pagamento: tente de novo em instantes" }, 502);
  await conta.pedir("anual_pendente", { ref, plano: plano.id, valor, cupom: oferta.cupom });
  if (oferta.cupom) await usarCupom(env, oferta.cupom.codigo);
  return json({ link: r.dados.init_point, periodo: "anual" });
}

async function pagar(env, conta, id, dono, mp, d) {
  const atual = await conta.pedir("ler_cadastro");
  if (!atual.cadastro) return json({ erro: "preencha os dados do escritório antes de pagar" }, 409);
  const oferta = await ofertaDoPagamento(env, atual, { plano: String(d.plano || ""), periodo: String(d.periodo || ""), cupom: d.cupom });
  if (oferta.erro) return json({ erro: oferta.erro }, oferta.status);
  const cartao = cartaoDoFormulario(d.cartao, oferta.parcelas_max);
  if (cartao.erro) return json({ erro: cartao.erro }, 400);
  await conta.pedir("documento", { hash: await resumoDoDocumento(cartao.identificacao.number) });
  const { plano, valor } = oferta;
  if (oferta.periodo === "mensal") {
    const r = await mp(env, "/preapproval", "POST", {
      reason: "PAULUS - plano " + plano.nome + (oferta.cupom ? " (cupom " + oferta.cupom.codigo + ")" : ""),
      external_reference: "ia-assinatura-" + id,
      payer_email: dono.email,
      card_token_id: cartao.token,
      auto_recurring: { frequency: 1, frequency_type: "months", transaction_amount: valor, currency_id: "BRL" },
      back_url: "https://paulus.ia.br/cadastro/",
      status: "authorized",
    });
    if (!r.ok || !r.dados || !r.dados.id) {
      return json({ erro: "o Mercado Pago não aceitou o cartão para a assinatura: confira os dados ou use outro cartão de crédito", status_mp: r.status }, 402);
    }
    const resumo = await conta.pedir("assinatura", { plano: plano.id, cupom: oferta.cupom,
      assinatura: { id: String(r.dados.id), situacao: r.dados.status || "pending", valor } });
    if (oferta.cupom) await usarCupom(env, oferta.cupom.codigo);
    return json({ ok: true, periodo: "mensal", situacao: r.dados.status, conta: resumo });
  }
  // O anual: a referencia leva a conta e o plano; o pendente fica anotado para a conferencia.
  const ref = "ia-anual-" + id + "-" + plano.id + "-" + aleatorio(4);
  await conta.pedir("anual_pendente", { ref, plano: plano.id, valor, cupom: oferta.cupom });
  const chave = /^[A-Za-z0-9-]{16,64}$/.test(String(d.idempotencia || "")) ? String(d.idempotencia) : crypto.randomUUID();
  const corpo = {
    transaction_amount: valor,
    token: cartao.token,
    description: "PAULUS - plano " + plano.nome + " (anual)",
    installments: cartao.parcelas,
    payment_method_id: cartao.metodo,
    payer: { email: dono.email, identification: cartao.identificacao },
    external_reference: ref,
    statement_descriptor: "PAULUS",
  };
  if (cartao.emissor) corpo.issuer_id = cartao.emissor;
  const r = await mp(env, "/v1/payments", "POST", corpo, { "X-Idempotency-Key": chave });
  if (!r.ok || !r.dados) return json({ erro: "o Mercado Pago não respondeu ao pagamento: tente de novo em instantes", status_mp: r.status }, 502);
  const pg = r.dados;
  if (oferta.cupom && pg.status !== "rejected") await usarCupom(env, oferta.cupom.codigo);
  if (pg.status === "approved") {
    await confirmarAnual(env, pg, mp);
    return json({ ok: true, periodo: "anual", situacao: "approved", pagamento: String(pg.id), paymentId: pg.id, conta: await conta.pedir("ler_cadastro") });
  }
  if (pg.status === "in_process" || pg.status === "pending") {
    return json({ ok: true, periodo: "anual", situacao: "in_process", pagamento: String(pg.id), paymentId: pg.id,
      mensagem: "o pagamento está em análise no Mercado Pago; o plano entra assim que for aprovado (costuma levar minutos)" });
  }
  return json({ erro: motivoDaRecusa(pg.status_detail), situacao: pg.status || "rejected" }, 402);
}

/* O Pix (/v1/payments, payment_method_id pix): o ano a vista ou um mes avulso,
   que vale ate vencer e nao renova. O QR vence em 30 minutos. A confirmacao e
   a mesma do anual no cartao: o aviso payment, a consulta do pendente ou a
   pagina perguntando por este pagamento (/api/ia/site/pix). */
async function pagarPix(env, conta, id, dono, mp, d) {
  const atual = await conta.pedir("ler_cadastro");
  if (!atual.cadastro) return json({ erro: "preencha os dados do escritório antes de pagar" }, 409);
  const oferta = await ofertaDoPagamento(env, atual, { plano: String(d.plano || ""), periodo: String(d.periodo || ""), cupom: d.cupom, meio: "pix" });
  if (oferta.erro) return json({ erro: oferta.erro }, oferta.status);
  const { plano, valor } = oferta;
  const anual = oferta.periodo === "anual";
  const ref = "ia-" + (anual ? "anual" : "mes") + "-" + id + "-" + plano.id + "-" + aleatorio(4);
  await conta.pedir("anual_pendente", { ref, plano: plano.id, valor, cupom: oferta.cupom, meses: oferta.meses });
  const doc = soDigitos(atual.cadastro.documento);
  const chave = /^[A-Za-z0-9-]{16,64}$/.test(String(d.idempotencia || "")) ? String(d.idempotencia) : crypto.randomUUID();
  // A data no fuso de Brasilia, no formato que o Mercado Pago pede (yyyy-MM-ddTHH:mm:ss.SSS-03:00).
  const vence = new Date(Date.now() + PIX_VENCE_MS - 3 * 3600 * 1000).toISOString().replace("Z", "-03:00");
  const r = await mp(env, "/v1/payments", "POST", {
    transaction_amount: valor,
    description: "PAULUS - plano " + plano.nome + (anual ? " (anual)" : " (um mês)"),
    payment_method_id: "pix",
    payer: { email: dono.email, identification: { type: doc.length === 11 ? "CPF" : "CNPJ", number: doc } },
    external_reference: ref,
    date_of_expiration: vence,
  }, { "X-Idempotency-Key": chave });
  const pg = (r.ok && r.dados) || null;
  const t = (pg && pg.point_of_interaction && pg.point_of_interaction.transaction_data) || {};
  if (!pg || !t.qr_code) return json({ erro: "o Mercado Pago não gerou o Pix: tente de novo em instantes", status_mp: r.status }, 502);
  if (oferta.cupom) await usarCupom(env, oferta.cupom.codigo);
  return json({ ok: true, meio: "pix", periodo: oferta.periodo, pagamento: String(pg.id), valor, vence,
    qr_code: t.qr_code, qr_code_base64: t.qr_code_base64 || "", ticket_url: t.ticket_url || "" });
}

/* A pagina do Pix pergunta se ele ja entrou: o pagamento e desta conta? Pago,
   o plano entra agora (confirmarAnual e idempotente). */
async function situacaoDoPix(env, conta, id, mp, pagamento) {
  if (!/^\d{1,20}$/.test(String(pagamento || ""))) return json({ erro: "pagamento inválido" }, 400);
  const r = await mp(env, "/v1/payments/" + encodeURIComponent(pagamento), "GET");
  if (!r.ok || !r.dados) return json({ erro: "não achei esse Pix", status: r.status }, r.status === 404 ? 404 : 502);
  const m = String(r.dados.external_reference || "").match(/^ia-(?:anual|mes)-([0-9a-f]{24})-/);
  if (!m || m[1] !== id) return json({ erro: "esse Pix não é desta conta" }, 403);
  if (r.dados.status === "approved") await confirmarAnual(env, r.dados, mp);
  return json({ pagamento, situacao: r.dados.status, pago: r.dados.status === "approved", conta: await conta.pedir("ler_cadastro") });
}

function dataBR(iso) {
  const t = Date.parse(iso || "");
  if (!Number.isFinite(t)) return "";
  return new Date(t - 3 * 3600 * 1000).toISOString().slice(0, 10).split("-").reverse().join("/");
}

/* O pagamento de uma vez confirmado (pelo aviso do Mercado Pago ou pela
   consulta): o ano ("ia-anual-", cartao ou Pix) ou o mes avulso ("ia-mes-",
   Pix) entra na conta e, se havia a assinatura mensal, ela e cancelada no
   Mercado Pago. Estornado (o reembolso dos 7 dias), o plano acaba agora. */
async function confirmarAnual(env, pagamento, mp) {
  const ref = String((pagamento && pagamento.external_reference) || "").match(/^ia-(anual|mes)-([0-9a-f]{24})-([a-z0-9-]{2,24})-[0-9a-f]+$/);
  if (!ref) return null;
  const m = [ref[0], ref[2], ref[3]];
  const anual = ref[1] === "anual";
  const conta = medidor(env, m[1]);
  const valor = Number(pagamento.transaction_amount) || 0;
  const tipo = "payment · " + (anual ? "anual" : "mês avulso") + (pagamento.payment_method_id === "pix" ? " (Pix)" : "");
  if (pagamento.status === "approved") {
    const r = await conta.pedir("anual_pago", { pagamento: String(pagamento.id), plano: m[2], valor, quando: pagamento.date_approved || "", meses: anual ? 12 : 1 });
    if (r.novo) await anotarPagamento(env, { id: String(pagamento.id), conta: m[1], tipo: anual ? "anual" : "mês avulso", valor });
    if (r.mensal_para_cancelar && mp) {
      const c = await mp(env, "/preapproval/" + encodeURIComponent(r.mensal_para_cancelar), "PUT", { status: "cancelled" });
      if (c.ok) await conta.pedir("mensal_cancelado", { id: r.mensal_para_cancelar });
    }
    await anotarAviso(env, { conta: m[1], tipo, status: "approved", valor });
    return r;
  }
  if (pagamento.status === "refunded" || pagamento.status === "charged_back") {
    await anotarAviso(env, { conta: m[1], tipo, status: String(pagamento.status), valor });
    return conta.pedir("anual_estornado", { pagamento: String(pagamento.id) });
  }
  return conta.pedir("resumo");
}

/* Sem o aviso (ou antes dele): pergunta ao Mercado Pago pelo pagamento do ano pendente. */
async function conferirAnualPendente(env, conta, mp) {
  const atual = await conta.pedir("resumo");
  const p = atual.anual_pendente;
  if (!p || !p.ref || !mp) return atual;
  const r = await mp(env, "/v1/payments/search?external_reference=" + encodeURIComponent(p.ref) + "&sort=date_created&criteria=desc", "GET");
  const achados = (r.ok && r.dados && r.dados.results) || [];
  const pago = achados.find((x) => x.status === "approved");
  if (!pago) return atual;
  await confirmarAnual(env, pago, mp);
  return conta.pedir("resumo");
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
  if (prepago(atual.periodo)) {
    return json({ erro: "no plano pago de uma vez, a troca de plano é na renovação (pago até " + dataBR(atual.pago_ate) + "); para antecipar, escreva para contato@paulus.ia.br" }, 409);
  }
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

/* {cupom, valor, valor_cheio} ou {erro}. No anual, o desconto vale sobre o valor do ano. */
export async function conferirCupom(env, codigo, plano, periodo = "mensal") {
  const c = await lerCupom(env, codigo);
  if (!c || !c.ativo) return { erro: "esse cupom não existe ou está pausado" };
  if (c.validade && Date.parse(c.validade) < Date.now()) return { erro: "esse cupom venceu" };
  if (c.limite && (c.usos || 0) >= c.limite) return { erro: "esse cupom chegou ao limite de usos" };
  const n = numeros(env);
  const p = n.planos.find((x) => x.id === plano) || planoDe(n, plano);
  if (Array.isArray(c.planos) && c.planos.length && !c.planos.includes(p.id)) return { erro: "esse cupom não vale para o plano " + p.nome };
  const cheio = periodo === "anual" ? p.valor_anual : p.valor;
  const valor = Math.round(cheio * (1 - Math.min(100, Math.max(0, Number(c.desconto) || 0)) / 100) * 100) / 100;
  return { cupom: { codigo: c.codigo, desconto: Number(c.desconto) || 0, meses: Number(c.meses) || 1, brinde: Number(c.brinde) || 0 }, valor, valor_cheio: cheio };
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
export const TERMOS_VERSAO = "2026-10-03";

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

/* O documento de quem assina: OAB, RG ou CNH (nenhum se consulta daqui, entao
   so a forma e conferida). OAB reconhecida vai normalizada ("PA 12345"); o
   resto vai como veio, em maiusculas, com 5 a 20 letras e numeros. "" se nao
   servir. */
export function identificacaoNormal(t) {
  const oab = oabNormal(t);
  if (oab) return oab;
  const s = String(t || "").toUpperCase().replace(/[^A-Z0-9./\- ]/g, "").replace(/\s+/g, " ").trim();
  const n = s.replace(/[^A-Z0-9]/g, "").length;
  return n >= 5 && n <= 20 && /\d/.test(s) ? s : "";
}

/* O endereco do cadastro (vai como tomador na NFS-e) conferido, ou {erro}.
   cmun e o codigo IBGE do municipio (a pagina preenche pela ViaCEP); vazio
   quando a pessoa digitou a mao. */
export function conferirEndereco(e) {
  if (!e || typeof e !== "object") return { erro: "preencha o endereço (CEP, rua, número, bairro, cidade e UF)" };
  const limpo = (v, max) => String(v == null ? "" : v).replace(/[\u0000-\u001f<>]/g, " ").replace(/\s+/g, " ").trim().slice(0, max);
  const cep = soDigitos(e.cep);
  if (cep.length !== 8) return { erro: "o CEP tem 8 dígitos" };
  const logradouro = limpo(e.logradouro, 125);
  if (logradouro.length < 2) return { erro: "diga a rua do endereço" };
  const numero = limpo(e.numero, 20);
  if (!numero) return { erro: "diga o número do endereço (ou S/N)" };
  const complemento = limpo(e.complemento, 60);
  const bairro = limpo(e.bairro, 60);
  if (!bairro) return { erro: "diga o bairro do endereço" };
  const cidade = limpo(e.cidade, 60);
  if (cidade.length < 2) return { erro: "diga a cidade do endereço" };
  const uf = limpo(e.uf, 2).toUpperCase();
  if (!UFS.includes(uf)) return { erro: "a UF tem 2 letras (ex.: PA)" };
  const cmun = soDigitos(e.cmun);
  if (cmun && cmun.length !== 7) return { erro: "o código do município (IBGE) tem 7 dígitos" };
  return { endereco: { cep, logradouro, numero, complemento, bairro, cidade, uf, cmun } };
}

/* O cadastro conferido, ou {erro}. O endereco e obrigatorio para quem cadastra
   agora (exigirEndereco); a conta antiga, cadastrada sem ele, continua valendo. */
export function conferirCadastro(d, { exigirEndereco = true } = {}) {
  const nome = String(d.nome_escritorio || "").replace(/[\u0000-\u001f<>]/g, "").replace(/\s+/g, " ").trim();
  if (nome.length < 2 || nome.length > 80) return { erro: "diga o nome do escritório (ou o seu, se trabalha sozinho)" };
  const documento = soDigitos(d.documento);
  if (!(documento.length === 11 ? cpfValido(documento) : cnpjValido(documento))) return { erro: "o CPF ou CNPJ não confere" };
  const telefone = soDigitos(d.telefone);
  if (telefone.length < 10 || telefone.length > 13) return { erro: "o telefone precisa do DDD" };
  const oab = identificacaoNormal(d.oab);
  if (!oab) return { erro: "falta o número da OAB, do RG ou da CNH" };
  let endereco = null;
  if ((d.endereco !== undefined && d.endereco !== null) || exigirEndereco) {
    const e = conferirEndereco(d.endereco);
    if (e.erro) return { erro: e.erro };
    endereco = e.endereco;
  }
  if (d.aceite !== true) return { erro: "é preciso aceitar os termos de uso e a política de privacidade" };
  const cadastro = { nome_escritorio: nome, documento, telefone, oab, termos: TERMOS_VERSAO };
  if (endereco) cadastro.endereco = endereco;
  return { cadastro };
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
  if (p === "/api/ia/site/entrar") return json(await comDesistencia(env, conta, aberta));
  if (p === "/api/ia/site/plano") {
    const r = await trocarPlano(env, conta, deps.chamarMP, String(d.plano || ""));
    if (!r.ok) return r;
    return json(await conta.pedir("ler_cadastro"));
  }
  if (p === "/api/ia/site/situacao") {
    const a = aberta.assinatura;
    const mp = deps.chamarMP;
    if (aberta.anual_pendente) await conferirAnualPendente(env, conta, mp);
    if (a && a.id && mp && !prepago(a.periodo)) {
      const r = await mp(env, "/preapproval/" + encodeURIComponent(a.id), "GET");
      if (r.ok && r.dados && r.dados.status && r.dados.status !== a.situacao) {
        await conta.pedir("assinatura", { assinatura: { ...a, situacao: r.dados.status } });
      }
    }
    return json(await comDesistencia(env, conta, await conta.pedir("ler_cadastro")));
  }
  if (p === "/api/ia/site/cadastro") {
    // Conta que ja tinha cadastro sem endereco (de antes do endereco) continua
    // valendo sem ele; cadastro novo, ou conta que ja tem endereco, precisa dele.
    const antes = aberta.cadastro || null;
    const c = conferirCadastro(d, { exigirEndereco: !antes || Boolean(antes.endereco) });
    if (c.erro) return json({ erro: c.erro }, 400);
    if (d.plano && !numeros(env).planos.some((x) => x.id === String(d.plano))) return json({ erro: "esse plano não existe" }, 400);
    await conta.pedir("cadastro", { cadastro: { ...c.cadastro, quando: new Date().toISOString() } });
    const salvo = await conta.pedir("ler_cadastro");
    if (!d.plano) return json(salvo);
    // Com o plano: o proximo passo e a pagina de pagamento, com o cartao nos campos seguros do Mercado Pago.
    const ida = await linkDoPagamento(env, conta, { plano: String(d.plano), periodo: d.periodo });
    return json({ ...salvo, proximo: ida.link });
  }
  if (p === "/api/ia/site/oferta") {
    // O que a pagina de pagamento mostra: o valor calculado aqui, e nao no
    // navegador, com o que cada meio permite ("" quando pode; senao, o porque).
    const atual = await conta.pedir("ler_cadastro");
    const pedido = { plano: String(d.plano || ""), periodo: String(d.periodo || ""), cupom: d.cupom };
    const cartao = await ofertaDoPagamento(env, atual, { ...pedido, meio: "cartao" });
    const pix = await ofertaDoPagamento(env, atual, { ...pedido, meio: "pix" });
    if (cartao.erro && pix.erro) return json({ erro: cartao.erro }, cartao.status);
    const o = cartao.erro ? pix : cartao;
    return json({ ...o, parcelas_max: cartao.erro ? 1 : cartao.parcelas_max, meios: { cartao: cartao.erro || "", pix: pix.erro || "" },
      email: dono.email, cadastro_completo: Boolean(aberta.cadastro) });
  }
  if (p === "/api/ia/site/pagar") return d.meio === "pix" ? pagarPix(env, conta, id, dono, deps.chamarMP, d) : pagar(env, conta, id, dono, deps.chamarMP, d);
  if (p === "/api/ia/site/desistir") return desistir(env, conta, id, deps.chamarMP, "o cliente, pelo site (" + dono.email + ")");
  if (p === "/api/ia/site/pix") return situacaoDoPix(env, conta, id, deps.chamarMP, String(d.pagamento || ""));
  if (p === "/api/ia/site/pagar-fora") return pagarFora(env, conta, id, dono, deps.chamarMP, d);
  return json({ erro: "rota não existe" }, 404);
}

async function situacaoDaAssinatura(env, conta, mp) {
  const atual = await conferirAnualPendente(env, conta, mp);
  const a = atual.assinatura;
  if (!a || !a.id || prepago(a.periodo)) return json(atual);
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
  if (prepago(a.periodo)) {
    return json({ erro: "o plano pago de uma vez não renova sozinho: ele vale até " + dataBR(atual.pago_ate) + ". Para o reembolso dos 7 dias, escreva para contato@paulus.ia.br" }, 409);
  }
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
  // Os pacotes sao os do plano da conta; a referencia leva o plano, para o
  // Pix pago creditar pelo preco dele mesmo se o plano mudar antes.
  const plano = planoDe(numeros(env), (atual.plano || {}).id);
  const pacotes = recargasDe(plano);
  const pacote = pacotes.find((x) => x.id === String(d.pacote || "1")) || pacotes.find((x) => x.id === "1");
  if (d.pacote && !pacotes.some((x) => x.id === String(d.pacote))) return json({ erro: "esse pacote de recarga não existe" }, 400);
  const valor = pacote.valor.toFixed(2);
  const r = await mp(env, "/v1/orders", "POST", {
    type: "online",
    total_amount: valor,
    external_reference: "ia-recarga-" + id + "-" + aleatorio(6) + "-" + plano.id,
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
  const feito = await conta.pedir("creditar", { pedido, valor: Number(r.dados.total_amount) || 0, plano: planoDaRecarga(ref) });
  return json({ id: pedido, pago: true, conta: feito });
}

// ------------------------------------------------------------- o reembolso

/* Devolve um pagamento inteiro pelo Mercado Pago (o cartao ou o Pix de origem)
   e tira da conta o que ele pagou: o anual e o mes no Pix acabam (ou, se eram
   a renovacao paga antes, o pago_ate volta); a mensalidade cancela a
   assinatura e fecha o ciclo dela; a recarga tira os creditos que sobram dela.
   A nota fiscal do pagamento sai: descartada, cancelada no prazo do municipio
   ou, fora dele, com a analise fiscal pedida (nfse/emissor.js, notaDoReembolso).
   A chave de idempotencia e a do pagamento: de novo, nao devolve duas vezes.
   Usado pelo painel (admin.js, a fila) e pela desistencia do cliente.
   -> {conta, nota, aviso}: aviso quando algo ficou por fazer. */
export async function devolverPagamento(env, mp, contaId, ref, { por = "", agora = Date.now(), texto = "" } = {}) {
  const conta = medidor(env, contaId);
  const det = await conta.pedir("admin_detalhe");
  const p = (det.pagamentos || []).find((x) => String(x.ref) === String(ref));
  if (!p) throw new Error("esse pagamento não está na conta");
  if (p.reembolso) throw new Error("esse pagamento já foi reembolsado");
  const chave = { "X-Idempotency-Key": "reembolso-" + p.ref };
  let res;
  if (p.tipo === "recarga") {
    res = await mp(env, "/v1/orders/" + encodeURIComponent(p.ref) + "/refund", "POST", {}, chave);
  } else {
    let pagamento = p.ref;
    if (p.tipo === "assinatura") {
      // A mensalidade guarda a cobranca da assinatura; o pagamento e o dela.
      const ap = await mp(env, "/authorized_payments/" + encodeURIComponent(p.ref), "GET");
      pagamento = ap.ok && ap.dados && ap.dados.payment && ap.dados.payment.id;
      if (!pagamento) throw new Error("o Mercado Pago não achou o pagamento desta mensalidade");
    }
    res = await mp(env, "/v1/payments/" + encodeURIComponent(pagamento) + "/refunds", "POST", {}, chave);
  }
  if (!res.ok) {
    const msg = res.dados && (res.dados.message || (res.dados.errors && res.dados.errors[0] && res.dados.errors[0].message));
    throw new Error("o Mercado Pago recusou o reembolso (HTTP " + res.status + (msg ? ": " + msg : "") + ")");
  }
  // A mensalidade devolvida: a assinatura sai do Mercado Pago, para nao cobrar de novo.
  let cancelada = false;
  const a = det.assinatura;
  const mensalAtiva = p.tipo === "assinatura" && a && a.id && !prepago(a.periodo) && a.situacao !== "cancelled";
  if (mensalAtiva) {
    const r = await mp(env, "/preapproval/" + encodeURIComponent(a.id), "PUT", { status: "cancelled" });
    cancelada = r.ok;
  }
  const r = await conta.pedir("admin_reembolsado", { ref: p.ref, por, cancelada });
  // A nota fiscal do pagamento.
  let nota = { acao: "sem_emissor", frase: "o emissor de NFS-e não está ligado: confira a nota em Notas fiscais" };
  if (!faltaDoEmissor(env)) {
    try {
      const n = await chamarEmissor(env, "nota_do_reembolso", { pagamento: String(p.ref), quem: por || "PAVLVS", texto });
      nota = n.status === 200 ? n.dados : { acao: "erro", frase: "a nota não foi cancelada: " + ((n.dados && n.dados.erro) || "HTTP " + n.status) };
    } catch (e) {
      nota = { acao: "erro", frase: "a nota não foi cancelada: " + String((e && e.message) || e).slice(0, 160) };
    }
  }
  // A fila das notas: o pagamento devolvido nao pede mais nota.
  if (env.APOIOS) {
    const chaveNf = "admin:nfse:" + p.ref;
    let nf = null;
    try {
      nf = JSON.parse((await env.APOIOS.get(chaveNf)) || "null");
    } catch {
      nf = null;
    }
    if (nf) {
      nf.reembolso = { quando: new Date(agora).toISOString(), por, nota: nota.frase };
      if (!nf.nota || nf.nota === "pendente") nf.nota = "reembolsado";
      await env.APOIOS.put(chaveNf, JSON.stringify(nf));
    }
    await anotarAviso(env, { conta: contaId, tipo: "reembolso", status: "refunded", valor: Number(p.valor) || 0, texto: "" });
  }
  const aviso = mensalAtiva && !cancelada
    ? "o dinheiro foi devolvido, mas o Mercado Pago não cancelou a assinatura: cancele em Ações para não cobrar de novo"
    : ["erro", "cancelamento_recusado", "analise_recusada", "em_andamento"].includes(nota.acao) ? "o dinheiro foi devolvido; " + nota.frase : "";
  return { conta: r, nota, aviso };
}

/* O documento (CPF ou CNPJ) de quem assina, em resumo: o do cadastro e o do
   titular do cartao. Guardado so o resumo, para a desistencia valer uma vez
   por documento, e nao so por conta Google. */
async function resumoDoDocumento(doc) {
  const d = soDigitos(doc);
  return d.length === 11 || d.length === 14 ? (await sha256("documento:" + d)).slice(0, 32) : "";
}

/* Algum documento desta conta ja desistiu (em qualquer conta)? -> a conta que desistiu, ou "". */
async function documentoJaDesistiu(env, x) {
  if (!env.APOIOS) return "";
  const docs = new Set([...(x.docs || []), await resumoDoDocumento(x.doc_cadastro)].filter(Boolean));
  for (const h of docs) {
    const v = await env.APOIOS.get("admin:desistencia:" + h);
    if (v) return v;
  }
  return "";
}

const JA_DESISTIU = "a desistência pelo PAULUS já foi usada por este CPF ou CNPJ; para outro reembolso, escreva para contato@paulus.ia.br";

/* O resumo com a desistencia conferida tambem pelo documento (o medidor so sabe da conta). */
async function comDesistencia(env, conta, r) {
  if (!r || !r.desistencia || !r.desistencia.pode) return r;
  const x = await conta.pedir("desistencia");
  if (await documentoJaDesistiu(env, x)) r.desistencia = { pode: false, motivo: JA_DESISTIU, valor: 0, ate: "" };
  return r;
}

/* A desistencia do cliente, nos 7 dias (CDC, art. 49), sem passar pelo painel:
   devolve os pagamentos do plano feitos nesse prazo e acaba o plano. Uma vez por
   conta; depois, so pelo painel. Sem a primeira cobranca do cartao ainda (o
   aviso chega depois), a assinatura e cancelada e a cobranca, quando vier, e
   devolvida sozinha (avisoDaIA, desistencia_pendente). */
async function desistir(env, conta, id, mp, por) {
  if (!mp) return json({ erro: "o Mercado Pago não está ligado" }, 503);
  const x = await conta.pedir("desistencia");
  if (!x.pode) return json({ erro: x.motivo }, 409);
  if (await documentoJaDesistiu(env, x)) return json({ erro: JA_DESISTIU }, 409);
  const notas = [];
  const avisos = [];
  for (const ref of x.refs) {
    try {
      const r = await devolverPagamento(env, mp, id, ref, { por });
      notas.push(r.nota);
      if (r.aviso) avisos.push(r.aviso);
    } catch (e) {
      return json({ erro: "não consegui devolver agora: " + String((e && e.message) || e) + ". Tente de novo ou escreva para contato@paulus.ia.br" }, 502);
    }
  }
  // O cartao sem cobranca ainda: so a assinatura sai.
  if (x.mensal_sem_cobranca) {
    const r = await mp(env, "/preapproval/" + encodeURIComponent(x.mensal_sem_cobranca), "PUT", { status: "cancelled" });
    if (!r.ok) return json({ erro: "o Mercado Pago não cancelou a assinatura agora: tente de novo em instantes" }, 502);
    await conta.pedir("admin_assinatura_cancelada");
  }
  const fim = await conta.pedir("desistiu", { sem_cobranca: Boolean(x.mensal_sem_cobranca), valor: x.valor, por });
  // Os documentos desta conta ficam marcados: a proxima desistencia deles e pelo painel.
  if (env.APOIOS) {
    const marca = JSON.stringify({ conta: id, quando: new Date().toISOString() });
    for (const h of new Set([...(x.docs || []), await resumoDoDocumento(x.doc_cadastro)].filter(Boolean))) await env.APOIOS.put("admin:desistencia:" + h, marca);
  }
  return json({ ok: true, valor: x.valor, conta: fim, notas, avisos });
}

/* O plano escrito na referencia do Pix da recarga ("" no Pix de antes dos planos de 03/10). */
function planoDaRecarga(ref) {
  return (String(ref || "").match(/^ia-recarga-[0-9a-f]{24}-[0-9a-f]+-([a-z0-9-]{2,24})$/) || [])[1] || "";
}

/* Cada pagamento confirmado vira uma linha da fila de notas fiscais do painel
   (worker/admin.js, Notas fiscais): "admin:nfse:<id>". */
async function anotarPagamento(env, p) {
  if (!env.APOIOS) return;
  const chave = "admin:nfse:" + p.id;
  if (await env.APOIOS.get(chave)) return;
  await env.APOIOS.put(chave, JSON.stringify({ ...p, quando: new Date().toISOString(), nota: "pendente" }));
  // Com "Emitir ao confirmar o pagamento" ligado no painel, a NFS-e sai agora
  // (o aviso do Mercado Pago ja roda em ctx.waitUntil, worker/index.js). Sem o
  // tomador completo, o motivo fica no pagamento e a nota fica pendente.
  await emitirAutomatico(env, p.id);
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
    if (dados.status === "processed") await medidor(env, m[1]).pedir("creditar", { pedido: String(dados.id), valor: Number(dados.total_amount) || 0, plano: planoDaRecarga(ref) });
    if (dados.status === "processed") await anotarPagamento(env, { id: String(dados.id), conta: m[1], tipo: "recarga pix", valor: Number(dados.total_amount) || 0 });
    await anotarAviso(env, { conta: m[1], tipo: "order · pix", status: String(dados.status || ""), valor: Number(dados.total_amount) || 0 });
    return true;
  }
  if (tipo === "pagamento") return Boolean(await confirmarAnual(env, dados, mp));
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
      // O cliente desistiu antes de a primeira cobranca chegar: ela volta agora.
      if (r && r.desistencia_pendente && mp) {
        await devolverPagamento(env, mp, m[1], String(dados.id), { por: "o cliente (desistência)" }).catch(() => null);
        await medidor(env, m[1]).pedir("desistencia_paga");
      }
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

const SEMANA_MS = 7 * 24 * 3600 * 1000;
// Os primeiros 7 dias da assinatura sao o prazo de arrependimento (CDC, art.
// 49): neles a cota e so a da semana, sem adiantamento - quem desiste nao
// leva mais do que uma semana de IA.
const ARREPENDIMENTO_MS = 7 * 24 * 3600 * 1000;

function menosUmMes(ms) {
  const d = new Date(ms);
  const dia = d.getUTCDate();
  d.setUTCMonth(d.getUTCMonth() - 1);
  if (d.getUTCDate() < dia) d.setUTCDate(0);
  return d.getTime();
}

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
    if (acao === "adiantar") {
      const motivo = this.motivoParaNaoAdiantar(conta, n, agora);
      if (motivo) return [{ ok: false, status: 409, erro: motivo, conta: this.resumo(conta, n, agora) }, null];
      const c = conta.ciclo;
      c.adiantamento = { semana: this.semanaDe(c, agora), quando: new Date(agora).toISOString() };
      return [this.resumo(conta, n, agora), conta];
    }
    if (acao === "anual_pendente") {
      conta.anual_pendente = { ref: d.ref, plano: d.plano, valor: d.valor, cupom: d.cupom || null, meses: Number(d.meses) === 1 ? 1 : 12, quando: new Date(agora).toISOString() };
      return [this.resumo(conta, n, agora), conta];
    }
    if (acao === "anual_pago") {
      // O ano (12 meses) ou o mes avulso do Pix (1): pago de uma vez, sem renovar sozinho.
      const meses = Number(d.meses) === 1 ? 1 : 12;
      const tipo = meses === 12 ? "anual" : "avulso";
      conta.pagamentos = conta.pagamentos || [];
      if (conta.pagamentos.some((p) => prepago(p.tipo) && p.ref === d.pagamento)) return [{ ...this.resumo(conta, n, agora), novo: false }, null];
      const antes = conta.assinatura || {};
      // A assinatura mensal que existia sai no Mercado Pago (confirmarAnual).
      const mensal = antes.id && !prepago(antes.periodo) && antes.situacao === "authorized" ? antes.id : "";
      // A renovacao antecipada comeca no fim do que ja esta pago; a primeira, agora.
      const pagoAte = Date.parse(conta.pago_ate || "");
      const inicio = prepago(conta.periodo) && pagoAte > agora ? pagoAte : agora;
      let ate = inicio;
      for (let i = 0; i < meses; i++) ate = maisUmMes(ate);
      conta.pago_ate = new Date(ate).toISOString();
      conta.periodo = tipo;
      conta.plano = d.plano;
      delete conta.plano_proximo;
      if (conta.anual_pendente && conta.anual_pendente.cupom) conta.cupom = { ...conta.anual_pendente.cupom, cobrados: 1, voltou: true };
      delete conta.anual_pendente;
      conta.assinatura = { id: tipo + "-" + d.pagamento, situacao: "authorized", valor: Number(d.valor) || 0, periodo: tipo,
        desde: antes.desde || new Date(agora).toISOString() };
      conta.pagamentos = [...conta.pagamentos, { tipo, ref: d.pagamento, valor: Number(d.valor) || 0,
        quando: new Date(Date.parse(d.quando || "") || agora).toISOString() }].slice(-60);
      // O ano pago abre um ciclo novo agora, com os creditos do plano pago (a
      // renovacao antecipada espera o fim do ciclo aberto, que ja esta pago).
      if (inicio === agora) this.abrirCiclo(conta, n, agora, tipo, d.pagamento);
      if (conta.cupom && conta.cupom.brinde > 0 && !conta.cupom.brinde_dado) {
        conta.extra = (conta.extra || 0) + Math.round(conta.cupom.brinde);
        conta.cupom.brinde_dado = true;
      }
      return [{ ...this.resumo(conta, n, agora), novo: true, mensal_para_cancelar: mensal }, conta];
    }
    if (acao === "mensal_cancelado") {
      conta.mensal_cancelado = { id: d.id, quando: new Date(agora).toISOString() };
      return [this.resumo(conta, n, agora), conta];
    }
    if (acao === "anual_estornado") {
      // Ja devolvido pelo painel (admin_reembolsado): o aviso do estorno nao mexe de novo.
      const pg = (conta.pagamentos || []).find((p) => prepago(p.tipo) && String(p.ref) === String(d.pagamento));
      if (pg && pg.reembolso) return [this.resumo(conta, n, agora), null];
      if (pg) pg.reembolso = { quando: new Date(agora).toISOString(), por: "Mercado Pago" };
      const a = conta.assinatura || {};
      if ((a.id !== "anual-" + d.pagamento && a.id !== "avulso-" + d.pagamento) || a.situacao === "refunded") return [this.resumo(conta, n, agora), null];
      // O reembolso (os 7 dias): o plano acaba agora, e o ciclo junto.
      conta.assinatura = { ...a, situacao: "refunded" };
      conta.pago_ate = new Date(agora).toISOString();
      if (conta.ciclo && Date.parse(conta.ciclo.fim) > agora) conta.ciclo.fim = new Date(agora).toISOString();
      return [this.resumo(conta, n, agora), conta];
    }
    if (acao === "assinatura") {
      // Com o anual em dia, o aviso da assinatura mensal antiga (cancelada ao
      // passar para o anual) nao mexe mais na conta.
      if (prepago(conta.periodo) && conta.assinatura && d.assinatura && conta.assinatura.id !== d.assinatura.id) {
        return [this.resumo(conta, n, agora), null];
      }
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
      const r = planoDe(n, d.plano || conta.plano).recarga;
      const tokens = pago > 0 ? Math.round((pago / r.valor) * r.tokens) : r.tokens;
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
    if (acao === "desistencia") return [this.desistencia(conta, agora), null];
    if (acao === "documento") {
      // O resumo do documento do titular do cartao (o do cadastro vem dele mesmo).
      if (!d.hash || (conta.docs || []).includes(d.hash)) return [{ ok: true }, null];
      conta.docs = [...(conta.docs || []), String(d.hash)].slice(-5);
      return [{ ok: true }, conta];
    }
    if (acao === "desistiu") {
      conta.desistencias = (conta.desistencias || 0) + 1;
      conta.desistencia = { quando: new Date(agora).toISOString(), valor: Number(d.valor) || 0, por: d.por || "" };
      if (d.sem_cobranca) {
        // A primeira cobranca do cartao ainda vem: o plano acaba agora e ela volta quando chegar.
        conta.desistencia_pendente = true;
        const c = this.cicloAberto(conta, agora);
        if (c) c.fim = new Date(agora).toISOString();
      }
      return [this.resumo(conta, n, agora), conta];
    }
    if (acao === "desistencia_paga") {
      delete conta.desistencia_pendente;
      return [this.resumo(conta, n, agora), conta];
    }
    if (acao.startsWith("admin_")) return this.fazerAdmin(acao, conta, d, n, agora);
    return [{ ok: false, erro: "ação desconhecida", status: 400 }, null];
  }

  /* A desistencia nos 7 dias: o que se devolve, ou por que nao. Os pagamentos do
     plano feitos nos ultimos 7 dias; da mensalidade no cartao, so a do contrato
     novo (a assinatura de ate 7 dias). Uma vez por conta. */
  desistencia(conta, agora) {
    const a = conta.assinatura || {};
    if (conta.cortesia) return { pode: false, motivo: "o plano de cortesia não tem o que devolver" };
    if ((conta.desistencias || 0) >= 1) {
      return { pode: false, motivo: "a desistência pelo PAULUS já foi usada nesta conta; para outro reembolso, escreva para contato@paulus.ia.br" };
    }
    const novo = agora - Date.parse(a.desde || "") <= ARREPENDIMENTO_MS;
    const pgs = (conta.pagamentos || []).filter((p) => !p.reembolso && (prepago(p.tipo) || (p.tipo === "assinatura" && novo))
      && agora - Date.parse(p.quando) <= ARREPENDIMENTO_MS);
    const temCobranca = pgs.some((p) => p.tipo === "assinatura");
    const semCobranca = a.id && !prepago(a.periodo) && a.situacao === "authorized" && novo && !temCobranca ? a.id : "";
    if (!pgs.length && !semCobranca) return { pode: false, motivo: "o prazo de 7 dias para desistir já passou, ou não há pagamento nele" };
    const inicio = Math.min(...pgs.map((p) => Date.parse(p.quando)), semCobranca ? Date.parse(a.desde) : Infinity);
    const valor = pgs.reduce((t, p) => t + (Number(p.valor) || 0), 0) + (semCobranca ? Number(a.valor) || 0 : 0);
    return { pode: true, refs: pgs.map((p) => p.ref), mensal_sem_cobranca: semCobranca, valor, ate: new Date(inicio + ARREPENDIMENTO_MS).toISOString(),
      docs: conta.docs || [], doc_cadastro: (conta.cadastro || {}).documento || "" };
  }

  cicloAberto(conta, agora) {
    const c = conta.ciclo;
    return c && Date.parse(c.fim) > agora ? c : null;
  }

  abrirCiclo(conta, n, inicio, origem, cobranca = "") {
    // Os tokens do plano da conta; sem plano escolhido (quem assinava antes
    // dos tres planos), o Escritorio.
    // A cota da semana: a do mes vezes 7/30. Nao acumula de uma semana para
    // a outra; o ciclo inteiro continua sendo o teto.
    const tokens = planoDe(n, conta.plano).tokens;
    conta.ciclo = { inicio: new Date(inicio).toISOString(), fim: new Date(maisUmMes(inicio)).toISOString(), tokens, usados: 0, origem,
      semana: Math.round((tokens * 7) / 30), por_semana: {} };
    if (cobranca) conta.ciclo.cobranca = cobranca;
  }

  semanaDe(c, agora) {
    return Math.max(0, Math.floor((agora - Date.parse(c.inicio)) / SEMANA_MS));
  }

  /* O teto da semana k: a cota, mais a da semana seguinte se foi adiantada
     nela, menos a cota se a semana anterior a adiantou. Sem semana (ciclo de
     antes de 03/10), sem teto semanal. */
  limiteDaSemana(c, k) {
    if (!c.semana) return Infinity;
    const a = c.adiantamento;
    let l = c.semana;
    if (a && a.semana === k) l += c.semana;
    if (a && a.semana === k - 1) l -= c.semana;
    return Math.max(0, l);
  }

  livreNaSemana(c, agora) {
    if (!c || !c.semana) return Infinity;
    const k = this.semanaDe(c, agora);
    return Math.max(0, this.limiteDaSemana(c, k) - ((c.por_semana || {})[k] || 0));
  }

  /* "" se pode adiantar a semana que vem; senao, o porque. */
  motivoParaNaoAdiantar(conta, n, agora) {
    if (!this.vigente(conta, n, agora)) return "o plano não está em dia";
    const c = this.cicloAberto(conta, agora);
    if (!c || !c.semana) return "este ciclo não tem cota semanal";
    if (c.adiantamento) return "o adiantamento deste mês já foi usado";
    const desde = Date.parse((conta.assinatura || {}).desde || conta.criada || "");
    if (!(agora - desde >= ARREPENDIMENTO_MS)) return "o adiantamento libera depois dos 7 primeiros dias da assinatura (o prazo de arrependimento)";
    const k = this.semanaDe(c, agora);
    if (Date.parse(c.inicio) + (k + 1) * SEMANA_MS >= Date.parse(c.fim)) return "esta é a última semana do ciclo: não há semana seguinte para adiantar";
    return "";
  }

  /* O plano vale agora? A cortesia abre o ciclo do mes sozinha. */
  vigente(conta, n, agora) {
    if (conta.cortesia && !this.cicloAberto(conta, agora)) this.abrirCiclo(conta, n, agora, "cortesia");
    // O anual: o ano esta pago, e cada mes abre o seu ciclo, com a cota do mes.
    const pagoAte = Date.parse(conta.pago_ate || "");
    if (prepago(conta.periodo) && conta.ciclo && !this.cicloAberto(conta, agora) && agora < pagoAte) {
      let inicio = Date.parse(conta.ciclo.fim);
      while (maisUmMes(inicio) <= agora) inicio = maisUmMes(inicio);
      this.abrirCiclo(conta, n, inicio, conta.periodo);
    }
    const a = conta.assinatura || {};
    if (prepago(conta.periodo) && a.situacao === "authorized" && agora >= pagoAte) conta.assinatura = { ...a, situacao: "expired" };
    const c = conta.ciclo;
    if (!c) return false;
    const fim = Date.parse(c.fim);
    if (fim > agora) return true;
    // A tolerancia e da cobranca mensal, que pode atrasar uns dias no Mercado Pago.
    return !prepago(conta.periodo) && a.situacao === "authorized" && agora < fim + TOLERANCIA_MS;
  }

  reservado(conta) {
    return Object.values(conta.reservas || {}).reduce((s, r) => s + r.tokens, 0);
  }

  restantes(conta, n, agora) {
    if (!this.vigente(conta, n, agora)) return 0;
    const c = conta.ciclo;
    const doCiclo = Math.min(Math.max(0, c.tokens - c.usados), this.livreNaSemana(c, agora));
    return doCiclo + (conta.extra || 0) - this.reservado(conta);
  }

  /* Do ciclo primeiro; o que passar, da recarga. */
  /* `tokens` sao creditos (o token vezes o peso do modelo); det.entrada e
     det.saida sao os tokens de verdade, para o custo por modelo no painel. */
  gastar(conta, tokens, det = {}) {
    const agora = this.agora();
    const c = conta.ciclo || { tokens: 0, usados: 0 };
    const k = c.semana ? this.semanaDe(c, agora) : 0;
    const doCiclo = Math.min(tokens, Math.max(0, Math.min(c.tokens - c.usados, this.livreNaSemana(c, agora))));
    const resto = tokens - doCiclo;
    const daRecarga = Math.min(resto, conta.extra || 0);
    conta.extra = (conta.extra || 0) - daRecarga;
    // Passou do que havia (a entrada real maior que a estimada): fica no ciclo.
    const doCicloTudo = doCiclo + resto - daRecarga;
    c.usados += doCicloTudo;
    if (c.semana) {
      c.por_semana = c.por_semana || {};
      c.por_semana[k] = (c.por_semana[k] || 0) + doCicloTudo;
    }
    if (conta.ciclo) conta.ciclo = c;
    // O uso de cada dia, para a tela dizer "hoje" e "nos ultimos 7 dias".
    // Entrada e saida separadas, o turno (manha, tarde, noite, no horario de
    // Brasilia) e o modelo: o painel admin conta o custo por eles.
    const brt = new Date(this.agora() - 3 * 3600 * 1000);
    const dia = brt.toISOString().slice(0, 10);
    const hora = brt.getUTCHours();
    const turno = hora < 12 ? 0 : hora < 18 ? 1 : 2;
    const reais = det.modelo && Number.isFinite(Number(det.entrada));
    const saida = reais ? Math.max(0, Math.round(Number(det.saida) || 0)) : Math.max(0, Math.min(tokens, Math.round(Number(det.saida) || 0)));
    const entrada = reais ? Math.max(0, Math.round(Number(det.entrada) || 0)) : tokens - saida;
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
    if (saida < 256) {
      const c = conta.ciclo;
      const semanal = c && c.semana && c.tokens - c.usados > entrada + 256 && this.livreNaSemana(c, agora) < entrada + 256;
      if (semanal) {
        const volta = Math.min(Date.parse(c.inicio) + (this.semanaDe(c, agora) + 1) * SEMANA_MS, Date.parse(c.fim));
        return negar(402, "semana", "a cota desta semana acabou; ela volta em " + dataBR(new Date(volta).toISOString())
          + ". Dá para adiantar a da semana que vem (uma vez por mês) ou fazer uma recarga");
      }
      return negar(402, "cota", "os créditos deste ciclo acabaram");
    }
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
    const plano = planoDe(n, conta.plano);
    // A semana do ciclo: a cota, o que ja foi, quando volta e o adiantamento.
    let semana = null;
    if (c && vigente && c.semana && Date.parse(c.fim) > agora) {
      const k = this.semanaDe(c, agora);
      const motivo = this.motivoParaNaoAdiantar(conta, n, agora);
      semana = { numero: k + 1, cota: c.semana, limite: this.limiteDaSemana(c, k), usados: (c.por_semana || {})[k] || 0,
        livres: Math.min(this.livreNaSemana(c, agora), doCiclo),
        volta_em: new Date(Math.min(Date.parse(c.inicio) + (k + 1) * SEMANA_MS, Date.parse(c.fim))).toISOString(),
        adiantamento: { usado: Boolean(c.adiantamento), pode: !motivo, motivo } };
    }
    return {
      ok: true,
      conta: conta.id,
      email: (conta.dono || {}).email || "",
      nome: conta.nome || "",
      cortesia: Boolean(conta.cortesia),
      consentimento: conta.consentimento || null,
      assinatura: a ? { id: a.id, situacao: a.situacao, valor: a.valor, desde: a.desde, periodo: a.periodo || "mensal" } : null,
      plano_vigente: vigente,
      plano,
      modelos: catalogo(modelosDoPlano(plano)),
      // Mensal ou anual; no anual, ate quando o ano esta pago.
      periodo: conta.periodo || "mensal",
      pago_ate: conta.pago_ate || null,
      agora: new Date(agora).toISOString(),
      // A desistencia nos 7 dias: se pode, quanto volta e ate quando (sem as referencias).
      desistencia: (({ pode, motivo, valor, ate }) => ({ pode, motivo: motivo || "", valor: valor || 0, ate: ate || "" }))(this.desistencia(conta, agora)),
      desistencia_pendente: Boolean(conta.desistencia_pendente),
      anual_pendente: conta.anual_pendente ? { ref: conta.anual_pendente.ref, plano: conta.anual_pendente.plano, valor: conta.anual_pendente.valor } : null,
      // Ainda no prazo de arrependimento (os 7 primeiros dias da assinatura).
      arrependimento_ate: a && a.desde ? new Date(Date.parse(a.desde) + ARREPENDIMENTO_MS).toISOString() : null,
      // A troca marcada: vale a partir da proxima renovacao (fim do ciclo).
      plano_proximo: conta.plano_proximo ? planoDe(n, conta.plano_proximo) : null,
      planos: n.planos.map((x) => ({ ...x, modelos_info: catalogo(modelosDoPlano(x)) })),
      cadastro_completo: Boolean(conta.cadastro),
      recarga: { valor: plano.recarga.valor, tokens: plano.recarga.tokens },
      recargas_pacotes: recargasDe(plano),
      ciclo: c ? { inicio: c.inicio, fim: c.fim, tokens: c.tokens, usados: c.usados, origem: c.origem } : null,
      semana,
      tokens: {
        do_ciclo: doCiclo,
        da_recarga: vigente ? conta.extra || 0 : 0,
        reservados: this.reservado(conta),
        restantes: this.restantes(conta, n, agora),
        // O que o ciclo ainda tem no mes (a semana pode estar no teto antes).
        do_mes: doCiclo,
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
        desvinculado: conta.desvinculado || null, plano_id: conta.plano || null, extra: conta.extra || 0, recargas: conta.recargas || [],
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
    if (acao === "admin_reembolsado") {
      const pg = (conta.pagamentos || []).find((p) => String(p.ref) === String(d.ref));
      if (!pg) return [{ ok: false, erro: "pagamento não encontrado", status: 404 }, null];
      if (pg.reembolso) return [this.resumo(conta, n, agora), null];
      const agoraIso = new Date(agora).toISOString();
      pg.reembolso = { quando: agoraIso, por: d.por || "" };
      const c = this.cicloAberto(conta, agora);
      if (prepago(pg.tipo)) {
        const a = conta.assinatura || {};
        const meses = pg.tipo === "anual" ? 12 : 1;
        let inicio = Date.parse(conta.pago_ate || "");
        for (let i = 0; i < meses; i++) inicio = menosUmMes(inicio);
        if (a.id !== pg.tipo + "-" + pg.ref) {
          // Um pagamento que nao e o mais novo (o ano passado, por exemplo): so o dinheiro volta.
        } else if (inicio > agora) {
          // A renovacao paga antes, que ainda nao comecou: o pago_ate volta ao fim do anterior.
          conta.pago_ate = new Date(inicio).toISOString();
        } else {
          // O periodo em curso: o plano acaba agora, e o ciclo junto.
          conta.assinatura = { ...a, situacao: "refunded" };
          conta.pago_ate = agoraIso;
          if (c) c.fim = agoraIso;
        }
      } else if (pg.tipo === "assinatura") {
        if (d.cancelada && conta.assinatura) conta.assinatura = { ...conta.assinatura, situacao: "cancelled" };
        // O mes devolvido: o ciclo que ele pagou acaba agora.
        if (c && (c.cobranca === pg.ref || (c.origem === "assinatura" && !c.cobranca))) c.fim = agoraIso;
      } else if (pg.tipo === "recarga") {
        const r = (conta.recargas || []).find((x) => x.pedido === pg.ref);
        const tirar = Math.min(conta.extra || 0, r ? r.tokens : 0);
        conta.extra = (conta.extra || 0) - tirar;
        pg.tokens_tirados = tirar;
        if (r) r.reembolso = { quando: agoraIso };
      }
      return [{ ...this.resumo(conta, n, agora), reembolsado: pg }, conta];
    }
    if (acao === "admin_assinatura_cancelada") {
      if (conta.assinatura) conta.assinatura = { ...conta.assinatura, situacao: "cancelled" };
      return [this.resumo(conta, n, agora), conta];
    }
    return [{ ok: false, erro: "ação desconhecida", status: 400 }, null];
  }
}
