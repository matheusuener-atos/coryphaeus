// A cobranca pela Atos (atos.dev.br; o desenho em C:\atos\docs\COBRANCA.md): a Atos e quem cobra, com o
// Mercado Pago dela; o PAVLVS so recebe o que mudou e libera o plano. Aqui:
//
//   POST /api/atos/eventos   os eventos da Atos Cobranca, assinados (Atos-Assinatura: t=<s>,v1=<HMAC-SHA256 hex
//                            de "<t>.<corpo>" com EVENTOS_SEGREDO_PAVLVS, o mesmo segredo nos dois Workers).
//                            direito.atualizado -> ContaIA "atos_direito" (o plano, ate quando, a assinatura;
//                            so a versao maior que a que ja tem); credito.adicionado -> "atos_credito" (a
//                            recarga, uma vez por pagamento). 2xx = aplicado; senao a Atos manda de novo.
//
// A reserva (conferirNaAtos): a conta fora de dia pergunta a Atos o retrato de agora
// (GET atos.dev.br/api/cobranca/v1/direitos), no maximo a cada 10 minutos - o evento que se perdeu.
//
// A conta cobrada pela Atos nao paga pelas rotas de dinheiro do PAVLVS (NA_ATOS): pagar aqui seria cobrar
// em dobro. Ela muda o plano, paga e cancela em atos.dev.br/conta.

import { medidor } from "./ia.js";

const ATOS = "https://atos.dev.br";
const IDADE_MAXIMA_S = 300;
const TEMPO_MS = 10000;

/* As vendas pela Atos (COBRANCA_PELA_ATOS="1", var do Worker): toda cobranca nova do PAVLVS e no checkout da
   Atos. O caminho antigo (paulus.ia.br/cadastro e /cadastro/pagamento, o Mercado Pago do proprio PAVLVS) leva
   para la, e as rotas que criariam cobranca nova aqui recusam. O que e de uma assinatura antiga do PAVLVS
   (cancelar, desistir nos 7 dias, trocar o cartao) continua aqui ate ela acabar. */
export function cobrancaPelaAtos(env) {
  return env.COBRANCA_PELA_ATOS === "1";
}

/* O checkout da Atos para um plano e um periodo do PAVLVS ("mensal"|"anual" ou "mes"|"ano"), com a volta ao site. */
export function checkoutDaAtos(plano, periodo) {
  const p = periodo === "anual" || periodo === "ano" ? "ano" : "mes";
  return ATOS + "/pavlvs/assinar/?preco=" + encodeURIComponent("pavlvs." + (plano || "escritorio") + "." + p) + "&volta=" + encodeURIComponent("https://paulus.ia.br/");
}

/* A recusa de uma cobranca nova pelo caminho antigo, com o checkout da Atos para seguir. */
export function vendaPelaAtos(plano, periodo) {
  return { erro: "a assinatura do PAVLVS agora é pela Atos: assine, mude o plano ou compre créditos em atos.dev.br", codigo: "cobranca_na_atos", proximo: checkoutDaAtos(plano, periodo) };
}

export const NA_ATOS = {
  erro: "a cobrança desta conta é pela Atos: mude o plano, pague ou cancele em atos.dev.br/conta",
  codigo: "cobranca_na_atos",
  proximo: ATOS + "/conta/",
};

const te = new TextEncoder();
async function hmacHex(segredo, texto) {
  const k = await crypto.subtle.importKey("raw", te.encode(segredo), { name: "HMAC", hash: "SHA-256" }, false, ["sign"]);
  return [...new Uint8Array(await crypto.subtle.sign("HMAC", k, te.encode(texto)))].map((x) => x.toString(16).padStart(2, "0")).join("");
}
function iguais(a, b) {
  a = String(a);
  b = String(b);
  if (a.length !== b.length) return false;
  let d = 0;
  for (let i = 0; i < a.length; i++) d |= a.charCodeAt(i) ^ b.charCodeAt(i);
  return d === 0;
}
async function idDaConta(sub) {
  const h = await crypto.subtle.digest("SHA-256", te.encode("conta-ia:" + sub));
  return [...new Uint8Array(h)].map((x) => x.toString(16).padStart(2, "0")).join("").slice(0, 24);
}
const json = (dados, status = 200) => new Response(JSON.stringify(dados), { status, headers: { "content-type": "application/json; charset=utf-8" } });

/* A Atos-Assinatura de um corpo recebido confere, e e de agora (5 minutos)? */
export async function eventoConfere(segredo, corpo, cabecalho, agora = Date.now()) {
  const p = Object.fromEntries(String(cabecalho || "").split(",").map((x) => x.trim().split("=")).filter((x) => x.length === 2));
  const ts = Number(p.t);
  if (!segredo || !ts || !p.v1 || Math.abs(agora / 1000 - ts) > IDADE_MAXIMA_S) return false;
  return iguais(await hmacHex(segredo, `${ts}.${corpo}`), String(p.v1).toLowerCase());
}

export function ehRotaDaAtos(url) {
  return url.pathname === "/api/atos/eventos";
}

export async function atenderAtos(request, env, url, deps = {}) {
  if (request.method !== "POST") return json({ erro: "use POST" }, 405);
  const segredo = String(env.EVENTOS_SEGREDO_PAVLVS || "");
  if (!segredo || !env.CONTAS_IA) return json({ erro: "os eventos da Atos não estão ligados aqui" }, 503);
  const corpo = await request.text();
  if (corpo.length > 64 * 1024 || !(await eventoConfere(segredo, corpo, request.headers.get("atos-assinatura")))) {
    return json({ erro: "assinatura da Atos não confere" }, 401);
  }
  let ev;
  try {
    ev = JSON.parse(corpo);
  } catch {
    return json({ erro: "evento ilegível" }, 400);
  }
  if (!ev || ev.produto !== "pavlvs" || !ev.conta || !ev.conta.sub || !ev.dados) return json({ erro: "evento sem produto, conta ou dados" }, 400);
  return json(await aplicarEvento(env, ev, deps));
}

/* Aplica um evento da Atos na conta. Lanca (-> 500, a Atos manda de novo) se o Mercado Pago do PAVLVS nao
   cancelou a assinatura antiga: na proxima entrega ele tenta outra vez. */
export async function aplicarEvento(env, ev, deps = {}) {
  const sub = String(ev.conta.sub);
  const id = await idDaConta(sub);
  const conta = medidor(env, id);
  const dono = { sub, email: String(ev.conta.email || "") };
  if (ev.tipo === "direito.atualizado") {
    const r = await conta.pedir("atos_direito", { id, dono, evento: String(ev.id || ""), retrato: ev.dados });
    await cancelarLegado(env, conta, r, deps);
    return { ok: true, aplicado: !r.repetido };
  }
  if (ev.tipo === "credito.adicionado") {
    const r = await conta.pedir("atos_credito", { id, dono, evento: String(ev.id || ""), credito: ev.dados });
    if (r.ok === false) return { ok: true, ignorado: r.erro };
    return { ok: true, aplicado: !r.repetido };
  }
  // Um tipo que este PAVLVS ainda nao conhece: recebido (2xx), para a Atos nao insistir.
  return { ok: true, ignorado: "tipo desconhecido" };
}

/* A assinatura mensal que o PAVLVS cobrava no Mercado Pago dele sai quando a conta passa para a Atos. */
async function cancelarLegado(env, conta, r, deps) {
  const id = r && r.legado_para_cancelar;
  if (!id) return;
  const mp = deps.chamarMP;
  if (!mp) throw new Error("sem o Mercado Pago para cancelar a assinatura antiga");
  const c = await mp(env, "/preapproval/" + encodeURIComponent(id), "PUT", { status: "cancelled" });
  // Ja cancelada no Mercado Pago tambem serve.
  const ja = c.dados && c.dados.status === "cancelled";
  if (!c.ok && !ja) throw new Error("o Mercado Pago não cancelou a assinatura antiga do PAVLVS");
  await conta.pedir("mensal_cancelado", { id });
}

/* A reserva: a conta fora de dia pergunta a Atos. Sem o segredo, ou sem nada de novo, nao faz nada. */
export async function conferirNaAtos(env, conta, deps = {}) {
  const segredo = String(env.EVENTOS_SEGREDO_PAVLVS || "");
  if (!segredo) return false;
  const q = await conta.pedir("atos_reserva");
  if (!q.conferir) return false;
  const buscar = deps.fetch || fetch;
  let retrato;
  try {
    const r = await buscar(ATOS + "/api/cobranca/v1/direitos?produto=pavlvs&sub=" + encodeURIComponent(q.sub), {
      headers: { authorization: "Bearer " + segredo }, signal: AbortSignal.timeout(TEMPO_MS) });
    if (!r.ok) return false;
    retrato = await r.json();
  } catch {
    return false;
  }
  if (!retrato || !(Number(retrato.versao) > 0)) return false;
  const r = await conta.pedir("atos_direito", { evento: "reserva", retrato });
  await cancelarLegado(env, conta, r, deps).catch(() => null);
  return !r.repetido;
}
