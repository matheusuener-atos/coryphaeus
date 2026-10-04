// O painel de administracao do PAVLVS (paulus.ia.br/admin; o contrato das
// rotas esta em worker/admin-api.md). A equipe ve as contas da nuvem, os
// tuneis do acesso de fora, as nao renovacoes, as campanhas de e-mail, os
// tokens e a receita, os planos, os materiais para moderar, as
// notas fiscais e a propria equipe.
//
// As notas fiscais (NFS-e do PAVLVS) sao emitidas daqui: /api/admin/nfse/emissor/*
// vai ao emissor da nuvem (worker/nfse/api.js, o Durable Object EmissorNFSe),
// atras das mesmas duas portas; dono e financeiro emitem e configuram, suporte
// so le. Essas acoes sao na hora (nao passam pela fila de alteracoes).
//
// Duas portas, nenhuma senha:
//   1. Cloudflare Access na frente de /admin e /api/admin (e-mail da equipe,
//      codigo de uso unico). Aqui o Worker confere o JWT que o Access poe em
//      cada pedido - sem ele, nada passa (e sem ACCESS_TEAM/ACCESS_AUD
//      configurados o painel fica fechado).
//   2. Login social do GitHub: a conta precisa ter escrita no repositorio. A
//      sessao (cookie pv_admin, 24 h) fica no KV APOIOS, "admin:sessao:<id>".
// O papel (dono, financeiro, suporte) vem de ADMIN_EQUIPE (JSON) ou, depois de
// publicado pelo painel, de "admin:equipe" no KV.
//
// O que muda o que esta no ar nao acontece na hora: entra na fila da pessoa
// ("admin:pendentes:<email>") e so e aplicado em "Commitar e pushar"
// (POST /api/admin/publicar, com a frase digitada). Comunicacao (lembrete,
// aviso, e-mail de teste) e marcacao (tratada) sao na hora.
//
// Tudo no KV APOIOS com o prefixo "admin:". O envio de e-mail e pelo Resend
// (RESEND_API_KEY); sem a chave, as rotas de e-mail dizem que falta.

import { MODELOS, PLANO_PADRAO, TOLERANCIA_MS, devolverPagamento, medidor, numeros } from "./ia.js";
import {
  listarParaAdmin, enderecosLivres, motivoDoEnderecoNovo, alterarEndereco, ativarEndereco, liberarEndereco,
  anotarHistorico, cfConfigurado,
} from "./tunel.js";
import { atenderEmissor, faltaDoEmissor, resumoParaPainel, PREFIXO as PREFIXO_EMISSOR } from "./nfse/api.js";

const REPO = "matheusuener-atos/coryphaeus";
const RAMO = "main";
const SITE = "https://paulus.ia.br";
const DE_EMAIL = "PAVLVS <naoresponda@paulus.ia.br>";
const SESSAO_S = 24 * 3600;
const DIA_MS = 24 * 3600 * 1000;
const CONFIRMACAO = "comitar e pushar";
const PAPEIS = ["dono", "financeiro", "suporte"];
const TODOS = PAPEIS;
const RITMO_POR_MINUTO = 50;

// Quem pode o que (o painel mostra a mesma matriz em Equipe).
const PODE = {
  "conta.creditar": ["dono", "financeiro"],
  "conta.instalacao.apagar": ["dono", "suporte"],
  "conta.cancelar": ["dono", "financeiro"],
  "conta.reembolsar": ["dono", "financeiro"],
  "google.servicos": ["dono", "suporte"],
  "google.desvincular": ["dono", "suporte"],
  "tunel.apagar": ["dono", "suporte"],
  "tunel.endereco": ["dono", "suporte"],
  "tunel.ativo": ["dono", "suporte"],
  "campanha.disparar": TODOS,
  "plano.editar": ["dono", "financeiro"],
  "plano.criar": ["dono", "financeiro"],
  "material.situacao": TODOS,
  "nfse.config": ["dono", "financeiro"],
  "equipe.papel": ["dono"],
};
// O emissor de NFS-e (/api/admin/nfse/emissor/*, na hora): quem emite,
// cancela, substitui e configura. Os outros papeis so leem (GET).
const PODE_NFSE = ["dono", "financeiro"];
export const MATRIZ = [
  ["Ver contas, tokens e receita", TODOS],
  ["Mandar e-mails e lembretes", TODOS],
  ["Revogar o Google e desvincular instalações", ["dono", "suporte"]],
  ["Apagar e mudar túneis", ["dono", "suporte"]],
  ["Planos", ["dono", "financeiro"]],
  ["Cancelar assinatura, reembolsar pagamentos e creditar tokens", ["dono", "financeiro"]],
  ["Ver as notas fiscais e baixar PDF e XML", TODOS],
  ["Emitir, cancelar e substituir notas fiscais; certificado e parâmetros", PODE_NFSE],
  ["Mudar papéis da equipe", ["dono"]],
];

// ---------------------------------------------------------------- entrada

export function ehRotaDoAdmin(url) {
  return url.pathname.startsWith("/api/admin/") || url.pathname.startsWith("/api/e/") || url.pathname === "/api/materiais/enviar";
}

export async function atenderAdmin(request, env, url, ctx, deps = {}) {
  const p = url.pathname;
  const m = request.method;
  // Fora do Access: o rastreio dos e-mails e o envio de material pelo PAULUS.
  if (p.startsWith("/api/e/")) return rastreio(env, url);
  if (p === "/api/materiais/enviar" && m === "POST") return receberMaterial(request, env, deps);
  if (!env.APOIOS) return json({ erro: "o painel precisa do KV APOIOS" }, 503);

  const access = await conferirAccess(request, env, deps);
  if (p === "/api/admin/sessao" && m === "GET") return sessaoAtual(request, env, access);
  if (!access.ok) return json({ erro: access.erro, passo: "access" }, access.status || 401);
  const membro = await membroDaEquipe(env, access.email);
  if (!membro) return json({ erro: "o e-mail " + access.email + " não está na equipe do painel", passo: "access" }, 403);
  if (p === "/api/admin/github/entrar" && m === "GET") return githubEntrar(env, access);
  if (p === "/api/admin/github/retorno" && m === "GET") return githubRetorno(env, url, access, membro, deps);

  const sessao = await sessaoDoCookie(request, env, access);
  if (!sessao) return json({ erro: "entre com o GitHub", passo: "github" }, 401);
  const quem = { email: access.email, nome: membro.nome || "", papel: membro.papel, login: sessao.login, token: sessao.token, sessao };
  if (p === "/api/admin/sair" && m === "POST") {
    await env.APOIOS.delete("admin:sessao:" + sessao.id);
    return json({ ok: true, logout: "/cdn-cgi/access/logout" }, 200, { "set-cookie": cookie("", 0) });
  }
  const c = { env, deps, quem, ctx, agora: (deps.agora || Date.now)() };
  try {
    return await rotear(c, request, url, p, m);
  } catch (e) {
    return json({ erro: String((e && e.message) || e).slice(0, 300) }, 500);
  }
}

async function rotear(c, request, url, p, m) {
  // O emissor de NFS-e: na hora, sem a fila. GET para todos; o resto, dono e financeiro.
  if (p.startsWith(PREFIXO_EMISSOR)) {
    if (m !== "GET" && !PODE_NFSE.includes(c.quem.papel)) {
      return json({ erro: "o papel " + c.quem.papel + " só vê as notas fiscais: emitir, cancelar e configurar são do dono e do financeiro" }, 403);
    }
    const falta = faltaDoEmissor(c.env);
    // A busca de município é só a tabela: funciona com o emissor desligado.
    if (falta && !(m === "GET" && p === PREFIXO_EMISSOR + "municipios")) return json({ erro: "o emissor de NFS-e ainda não está ligado: " + falta }, 503);
    return atenderEmissor(request, c.env, c.ctx, { quem: c.quem.email, prefixo: PREFIXO_EMISSOR });
  }
  if (m === "GET") {
    if (p === "/api/admin/visao") return json(await visao(c));
    if (p === "/api/admin/contas") return json(await contasParaTela(c));
    let r = p.match(/^\/api\/admin\/contas\/([0-9a-f]{24})$/);
    if (r) return json(await contaParaTela(c, r[1]));
    if (p === "/api/admin/tuneis") return json(await tuneisParaTela(c));
    if (p === "/api/admin/tuneis/disponivel") {
      const nome = String(url.searchParams.get("nome") || "").trim().toLowerCase();
      const motivo = await motivoDoEnderecoNovo(c.env, nome);
      return json({ ok: !motivo, motivo: motivo || "disponível · CNAME livre na zona" });
    }
    if (p === "/api/admin/renovacoes") return json(await renovacoes(c));
    if (p === "/api/admin/campanhas") return json(await campanhasParaTela(c));
    if (p === "/api/admin/tokens") return json(await tokens(c, url.searchParams.get("visao") || "geral", url.searchParams.get("periodo") || "mes"));
    if (p === "/api/admin/planos") return json(await planos(c));
    if (p === "/api/admin/materiais") return json({ materiais: await materiais(c.env) });
    if (p === "/api/admin/nfse") return json(await nfse(c));
    if (p === "/api/admin/equipe") return json(await equipe(c));
    if (p === "/api/admin/busca") return json(await busca(c, url.searchParams.get("q") || ""));
    if (p === "/api/admin/alteracoes") return json(await alteracoes(c));
  }
  if (m === "POST") {
    const d = (await lerJSON(request)) || {};
    if (p === "/api/admin/alteracoes") return enfileirar(c, d);
    if (p === "/api/admin/publicar") return publicar(c, d);
    let r = p.match(/^\/api\/admin\/tuneis\/([a-z0-9-]{3,24})\/avisar$/);
    if (r) return avisarTunel(c, r[1]);
    r = p.match(/^\/api\/admin\/renovacoes\/([0-9a-f]{24})\/(lembrete|tratar|reabrir)$/);
    if (r) return acaoDeRenovacao(c, r[1], r[2]);
    if (p === "/api/admin/renovacoes/config") return configRenovacoes(c, d);
    if (p === "/api/admin/campanhas/teste") return campanhaTeste(c, d.campanha || d);
  }
  if (m === "DELETE") {
    const r = p.match(/^\/api\/admin\/alteracoes\/([a-z0-9]{6,32})$/);
    if (r) return tirarDaFila(c, r[1]);
  }
  return json({ erro: "rota não existe" }, 404);
}

// ------------------------------------------------------------- utilidades

function json(dados, status = 200, extra = {}) {
  return new Response(JSON.stringify(dados), {
    status,
    headers: { "content-type": "application/json; charset=utf-8", "cache-control": "no-store", ...extra },
  });
}

async function lerJSON(request) {
  try {
    return await request.json();
  } catch {
    return null;
  }
}

function aleatorio(n) {
  const b = new Uint8Array(n);
  crypto.getRandomValues(b);
  return [...b].map((x) => x.toString(16).padStart(2, "0")).join("");
}

async function sha256Hex(texto) {
  const r = await crypto.subtle.digest("SHA-256", new TextEncoder().encode(String(texto)));
  return [...new Uint8Array(r)].map((b) => b.toString(16).padStart(2, "0")).join("");
}

async function kvJSON(env, chave, padrao = null) {
  try {
    const v = await env.APOIOS.get(chave);
    return v ? JSON.parse(v) : padrao;
  } catch {
    return padrao;
  }
}

async function kvPor(env, prefixo) {
  const saida = [];
  let cursor;
  do {
    const lista = await env.APOIOS.list({ prefix: prefixo, cursor });
    for (const k of lista.keys) saida.push(k.name);
    cursor = lista.list_complete ? undefined : lista.cursor;
  } while (cursor);
  return saida;
}

function cookie(valor, maxAge) {
  return "pv_admin=" + valor + "; Path=/; HttpOnly; Secure; SameSite=Lax; Max-Age=" + maxAge;
}

function cookies(request) {
  const saida = {};
  for (const parte of String(request.headers.get("cookie") || "").split(";")) {
    const i = parte.indexOf("=");
    if (i > 0) saida[parte.slice(0, i).trim()] = parte.slice(i + 1).trim();
  }
  return saida;
}

function b64urlBytes(s) {
  const b = atob(String(s).replace(/-/g, "+").replace(/_/g, "/") + "===".slice((String(s).length + 3) % 4));
  return Uint8Array.from(b, (ch) => ch.charCodeAt(0));
}

function mesBRT(ms) {
  return new Date(ms - 3 * 3600 * 1000).toISOString().slice(0, 7);
}

function diaBRT(ms) {
  return new Date(ms - 3 * 3600 * 1000).toISOString().slice(0, 10);
}

function brl(v) {
  return "R$ " + Number(v || 0).toLocaleString("pt-BR", { minimumFractionDigits: Number(v) % 1 ? 2 : 0, maximumFractionDigits: 2 });
}

function precos(env) {
  let p = {};
  try {
    p = JSON.parse(env.IA_PRECOS || "{}");
  } catch {
    p = {};
  }
  const n = (v, d) => (Number.isFinite(Number(v)) && Number(v) > 0 ? Number(v) : d);
  return { entrada: n(p.entrada, 0.23), saida: n(p.saida, 0.4), cambio: n(env.IA_CAMBIO || p.cambio, 5.6) };
}

/* O custo em dolar: pelo preco do modelo, quando se sabe qual (MODELOS, em
   worker/ia.js); sem modelo (o uso de antes do registro por modelo), pelo
   IA_PRECOS. */
function custoUSD(env, entrada, saida, modelo) {
  const m = modelo && MODELOS[modelo];
  const pr = m ? { entrada: m.usd[0], saida: m.usd[1] } : precos(env);
  return (entrada / 1e6) * pr.entrada + (saida / 1e6) * pr.saida;
}

/* O custo de um uso com o detalhe por modelo: cada modelo no preco dele, o resto no IA_PRECOS. */
function custoDoUso(env, uso) {
  let entrada = uso.entrada || 0;
  let saida = uso.saida || 0;
  let total = 0;
  for (const [nome, x] of Object.entries(uso.modelos || {})) {
    total += custoUSD(env, x.entrada || 0, x.saida || 0, nome);
    entrada -= x.entrada || 0;
    saida -= x.saida || 0;
  }
  return total + custoUSD(env, Math.max(0, entrada), Math.max(0, saida));
}

// ------------------------------------------------------------- as portas

/* O JWT do Cloudflare Access (RS256), conferido com as chaves do time. */
async function conferirAccess(request, env, deps) {
  if (!env.ACCESS_TEAM || !env.ACCESS_AUD) {
    return { ok: false, status: 503, erro: "o Cloudflare Access do painel ainda não foi configurado (ACCESS_TEAM e ACCESS_AUD)" };
  }
  const token = request.headers.get("cf-access-jwt-assertion") || cookies(request).CF_Authorization || "";
  const partes = token.split(".");
  if (partes.length !== 3) return { ok: false, erro: "entre pelo Cloudflare Access" };
  let cab, corpo;
  try {
    cab = JSON.parse(new TextDecoder().decode(b64urlBytes(partes[0])));
    corpo = JSON.parse(new TextDecoder().decode(b64urlBytes(partes[1])));
  } catch {
    return { ok: false, erro: "a sessão do Cloudflare Access não confere" };
  }
  const time = String(env.ACCESS_TEAM).replace(/^https?:\/\//, "").replace(/\/$/, "");
  const agora = (deps.agora || Date.now)() / 1000;
  const auds = Array.isArray(corpo.aud) ? corpo.aud : [corpo.aud];
  if (cab.alg !== "RS256" || !auds.includes(env.ACCESS_AUD) || corpo.iss !== "https://" + time || !(corpo.exp > agora) || !corpo.email) {
    return { ok: false, erro: "a sessão do Cloudflare Access venceu ou não é deste painel" };
  }
  const chaves = await (deps.chavesDoAccess || chavesDoAccess)(time);
  const jwk = (chaves || []).find((k) => k.kid === cab.kid);
  if (!jwk) return { ok: false, erro: "a sessão do Cloudflare Access não confere" };
  try {
    const chave = await crypto.subtle.importKey("jwk", jwk, { name: "RSASSA-PKCS1-v1_5", hash: "SHA-256" }, false, ["verify"]);
    const ok = await crypto.subtle.verify("RSASSA-PKCS1-v1_5", chave, b64urlBytes(partes[2]), new TextEncoder().encode(partes[0] + "." + partes[1]));
    if (!ok) return { ok: false, erro: "a sessão do Cloudflare Access não confere" };
  } catch {
    return { ok: false, erro: "a sessão do Cloudflare Access não confere" };
  }
  return { ok: true, email: String(corpo.email).toLowerCase() };
}

let CHAVES_CACHE = { quando: 0, time: "", chaves: null };
async function chavesDoAccess(time) {
  if (CHAVES_CACHE.chaves && CHAVES_CACHE.time === time && Date.now() - CHAVES_CACHE.quando < 3600 * 1000) return CHAVES_CACHE.chaves;
  const r = await fetch("https://" + time + "/cdn-cgi/access/certs");
  const d = r.ok ? await r.json() : {};
  CHAVES_CACHE = { quando: Date.now(), time, chaves: d.keys || [] };
  return CHAVES_CACHE.chaves;
}

export async function listaDaEquipe(env) {
  const doKV = await kvJSON(env, "admin:equipe", null);
  if (Array.isArray(doKV) && doKV.length) return doKV;
  try {
    const l = JSON.parse(env.ADMIN_EQUIPE || "[]");
    return Array.isArray(l) ? l : [];
  } catch {
    return [];
  }
}

async function membroDaEquipe(env, email) {
  const lista = await listaDaEquipe(env);
  const m = lista.find((x) => String(x.email || "").toLowerCase() === String(email || "").toLowerCase());
  if (!m || !PAPEIS.includes(m.papel)) return null;
  return { email: String(m.email).toLowerCase(), nome: m.nome || "", papel: m.papel };
}

async function sessaoDoCookie(request, env, access) {
  const id = cookies(request).pv_admin || "";
  if (!/^[0-9a-f]{48}$/.test(id)) return null;
  const s = await kvJSON(env, "admin:sessao:" + id, null);
  if (!s || s.email !== access.email) return null;
  return { ...s, id };
}

function configuracao(env) {
  const cfg = (ligado, falta) => ({ ligado: Boolean(ligado), falta: ligado ? "" : falta });
  return {
    access: cfg(env.ACCESS_TEAM && env.ACCESS_AUD, "falta ACCESS_TEAM e ACCESS_AUD"),
    github: cfg(env.GITHUB_CLIENT_ID && env.GITHUB_CLIENT_SECRET, "falta o OAuth App do GitHub (GITHUB_CLIENT_ID e GITHUB_CLIENT_SECRET)"),
    email: cfg(env.RESEND_API_KEY, "o envio de e-mail ainda não está ligado: falta RESEND_API_KEY"),
    // O emissor de NFS-e da nuvem (worker/nfse/api.js): o DO e a chave mestra.
    nfse: cfg(!faltaDoEmissor(env), "o emissor de NFS-e ainda não está ligado: " + faltaDoEmissor(env)),
    tuneis: cfg(cfConfigurado(env), "falta a chave da Cloudflare (CF_API_TOKEN, CF_ACCOUNT_ID, CF_ZONE_ID)"),
    mercado_pago: cfg(env.MP_ACCESS_TOKEN, "falta MP_ACCESS_TOKEN"),
    nuvem: cfg(env.IA_ATIVA === "1" && env.CONTAS_IA, "a nuvem do PAULUS está desligada (IA_ATIVA)"),
  };
}

async function sessaoAtual(request, env, access) {
  const membro = access.ok ? await membroDaEquipe(env, access.email) : null;
  const sessao = access.ok && membro ? await sessaoDoCookie(request, env, access) : null;
  return json({
    access: { ok: Boolean(access.ok && membro), email: access.ok ? access.email : "", erro: access.ok ? (membro ? "" : "esse e-mail não está na equipe do painel") : access.erro },
    github: { ok: Boolean(sessao), login: sessao ? sessao.login : "" },
    papel: membro ? membro.papel : "", nome: membro ? membro.nome : "",
    worker: await versaoDoSite(env), pronto: Boolean(sessao), config: configuracao(env),
  });
}

async function versaoDoSite(env) {
  try {
    const r = await env.ASSETS.fetch(new Request(SITE + "/atualizacao.json"));
    return r.ok ? String((await r.json()).versao || "") : "";
  } catch {
    return "";
  }
}

async function githubEntrar(env, access) {
  if (!env.GITHUB_CLIENT_ID || !env.GITHUB_CLIENT_SECRET) return json({ erro: "falta o OAuth App do GitHub (GITHUB_CLIENT_ID e GITHUB_CLIENT_SECRET)" }, 503);
  const state = aleatorio(16);
  await env.APOIOS.put("admin:gh:" + state, JSON.stringify({ email: access.email }), { expirationTtl: 600 });
  const q = new URLSearchParams({ client_id: env.GITHUB_CLIENT_ID, redirect_uri: SITE + "/api/admin/github/retorno", scope: "public_repo read:user", state, allow_signup: "false" });
  return new Response(null, { status: 302, headers: { location: "https://github.com/login/oauth/authorize?" + q.toString(), "cache-control": "no-store" } });
}

function voltarComErro(frase) {
  return new Response(null, { status: 302, headers: { location: "/admin/?erro=" + encodeURIComponent(frase), "cache-control": "no-store" } });
}

async function githubRetorno(env, url, access, membro, deps) {
  const state = url.searchParams.get("state") || "";
  const code = url.searchParams.get("code") || "";
  const guardado = /^[0-9a-f]{32}$/.test(state) ? await kvJSON(env, "admin:gh:" + state, null) : null;
  if (!guardado || guardado.email !== access.email || !code) return voltarComErro("o login do GitHub venceu; tente de novo");
  await env.APOIOS.delete("admin:gh:" + state);
  const gh = deps.github || chamarGitHub;
  const t = await gh("POST", "https://github.com/login/oauth/access_token", null, {
    client_id: env.GITHUB_CLIENT_ID, client_secret: env.GITHUB_CLIENT_SECRET, code, redirect_uri: SITE + "/api/admin/github/retorno",
  });
  const token = t.ok && t.dados && t.dados.access_token;
  if (!token) return voltarComErro("o GitHub não confirmou o login");
  const u = await gh("GET", "https://api.github.com/user", token);
  const login = u.ok && u.dados && u.dados.login;
  if (!login) return voltarComErro("o GitHub não disse quem é a conta");
  const perm = await gh("GET", "https://api.github.com/repos/" + REPO + "/collaborators/" + encodeURIComponent(login) + "/permission", token);
  const nivel = perm.ok && perm.dados ? String(perm.dados.permission || "") : "";
  if (!["admin", "write", "maintain"].includes(nivel)) return voltarComErro("a conta " + login + " não tem escrita em " + REPO);
  const id = aleatorio(24);
  await env.APOIOS.put("admin:sessao:" + id, JSON.stringify({ email: access.email, login, token, criada: new Date().toISOString() }), { expirationTtl: SESSAO_S });
  await env.APOIOS.put("admin:acesso:" + access.email, JSON.stringify({ ultimo: new Date().toISOString(), login }));
  return new Response(null, { status: 302, headers: { location: "/admin/", "set-cookie": cookie(id, SESSAO_S), "cache-control": "no-store" } });
}

async function chamarGitHub(metodo, url, token, corpo) {
  const headers = { "User-Agent": "PAVLVS-admin", Accept: url.includes("/login/oauth/") ? "application/json" : "application/vnd.github+json" };
  if (token) headers.Authorization = "Bearer " + token;
  if (corpo) headers["Content-Type"] = "application/json";
  const r = await fetch(url, { method: metodo, headers, body: corpo ? JSON.stringify(corpo) : undefined });
  let dados = null;
  try {
    dados = await r.json();
  } catch {
    dados = null;
  }
  return { ok: r.ok, status: r.status, dados };
}

// ---------------------------------------------------------- as contas

/* As contas como o painel as monta, com o detalhe cru em _d (para o tomador
   das notas fiscais, worker/nfse-casa.js). */
export async function contasDaCasa(env, agora = Date.now()) {
  return lerContas({ env, agora });
}

/* Todas as contas da nuvem, com o detalhe de cada uma (um pedido por medidor). */
async function lerContas(c) {
  if (c._contas) return c._contas;
  const { env } = c;
  if (env.IA_ATIVA !== "1" || !env.CONTAS_IA) return (c._contas = []);
  const ids = (await kvPor(env, "admin:conta:")).map((k) => k.slice("admin:conta:".length)).filter((x) => /^[0-9a-f]{24}$/.test(x));
  const lidas = await Promise.all(ids.map((id) => medidor(env, id).pedir("admin_detalhe").catch(() => null)));
  c._contas = lidas.filter((x) => x && x.id && x.ok !== false).map((d) => montarConta(c, d));
  return c._contas;
}

function situacaoDe(d, agora) {
  const a = d.assinatura || {};
  if (d.cortesia && d.plano_vigente) return "cortesia";
  if (a.situacao === "cancelled") return "cancelada";
  const fim = d.ciclo ? Date.parse(d.ciclo.fim) : 0;
  if (fim && fim < agora) return "vencida";
  if (a.situacao === "authorized" && d.plano_vigente) return "ativa";
  return "pendente";
}

function montarConta(c, d) {
  const cad = d.cadastro || {};
  const ultimoUso = (d.uso || []).filter((u) => u.tokens > 0).map((u) => u.dia).pop() || null;
  return {
    id: d.id, nome: cad.nome_escritorio || d.nome || (d.email || "").split("@")[0], email: d.email || "",
    escritorio: { nome: cad.nome_escritorio || d.nome || "", slug: "", documento: cad.documento || "" },
    oab: cad.oab || "", plano: d.plano || null, situacao: situacaoDe(d, c.agora),
    restantes: (d.tokens || {}).restantes || 0, usados: (d.ciclo || {}).usados || 0, extra: (d.tokens || {}).da_recarga || 0,
    ultimo_uso: ultimoUso, google: d.google || null,
    _d: d,
  };
}

function publica(conta) {
  const { _d, ...resto } = conta;
  return resto;
}

/* O escritorio de cada conta: o endereco do acesso de fora da mesma conta Google
   (pelo dono do tunel) e, para agrupar, o CNPJ ou o nome do cadastro. */
async function comEscritorios(c, contas) {
  const tuneis = await lerTuneis(c);
  for (const conta of contas) {
    const t = tuneis.find((x) => x.responsavel && x.responsavel.toLowerCase() === conta.email.toLowerCase());
    if (t) conta.escritorio.slug = t.slug;
  }
  const grupos = new Map();
  const mes = mesBRT(c.agora);
  for (const conta of contas) {
    const chave = conta.escritorio.documento || conta.escritorio.slug || conta.escritorio.nome || conta.id;
    if (!grupos.has(chave)) grupos.set(chave, { nome: conta.escritorio.nome || conta.nome, slug: conta.escritorio.slug, documento: conta.escritorio.documento, contas: [], tokens_mes: 0, receita_mes: 0 });
    const g = grupos.get(chave);
    g.contas.push(conta.id);
    const um = (conta._d.uso_mes || {})[mes] || {};
    g.tokens_mes += (um.entrada || 0) + (um.saida || 0);
    g.receita_mes += (conta._d.pagamentos || []).filter((p) => mesBRT(Date.parse(p.quando)) === mes).reduce((s, p) => s + (Number(p.valor) || 0), 0);
    if (!g.slug && conta.escritorio.slug) g.slug = conta.escritorio.slug;
  }
  return [...grupos.values()];
}

async function contasParaTela(c) {
  const contas = await lerContas(c);
  const escritorios = await comEscritorios(c, contas);
  return { contas: contas.map(publica), escritorios };
}

async function contaParaTela(c, id) {
  const contas = await lerContas(c);
  await comEscritorios(c, contas);
  const conta = contas.find((x) => x.id === id);
  if (!conta) return { erro: "conta não encontrada" };
  const d = conta._d;
  return {
    ...publica(conta), criada: d.criada, ciclo: d.ciclo || null,
    cadastro: d.cadastro ? { documento: d.cadastro.documento, telefone: d.cadastro.telefone, oab: d.cadastro.oab, termos: d.cadastro.termos, quando: d.cadastro.quando } : null,
    consentimento: d.consentimento || null, assinatura: d.assinatura || null, plano_proximo: d.plano_proximo || null,
    instalacoes: d.instalacoes_lista || [], pagamentos: d.pagamentos || [], recargas: d.recargas || [],
    google_pendente: d.google_pendente || null, desvinculado: d.desvinculado || null, pago_ate: d.pago_ate || null, periodo: d.periodo || "mensal",
  };
}

// ------------------------------------------------------------ os tuneis

async function lerTuneis(c) {
  if (c._tuneis) return c._tuneis;
  c._tuneis = c.env.ESCRITORIOS ? await listarParaAdmin(c.env, c.agora) : [];
  return c._tuneis;
}

async function tuneisParaTela(c) {
  return {
    tuneis: await lerTuneis(c), livres: c.env.ESCRITORIOS ? await enderecosLivres(c.env) : [],
    cf: configuracao(c.env).tuneis,
  };
}

async function avisarTunel(c, slug) {
  const t = (await lerTuneis(c)).find((x) => x.slug === slug);
  if (!t) return json({ erro: "esse endereço não existe mais" }, 404);
  if (!t.responsavel) return json({ erro: "esse endereço não tem responsável com e-mail" }, 409);
  const prazo = t.limpeza ? (t.limpeza.dias <= 0 ? "hoje" : "em " + t.limpeza.dias + (t.limpeza.dias === 1 ? " dia" : " dias")) : "";
  const r = await enviarEmail(c.env, {
    para: t.responsavel, assunto: "O acesso de fora do PAULUS está parado",
    titulo: "O endereço " + slug + ".paulus.ia.br está sem conexão",
    texto: "O PAULUS do escritório não se conecta a este endereço há um tempo." + (prazo ? " Se continuar assim, a limpeza automática libera o endereço " + prazo + "." : "") +
      "\n\nPara manter, abra o PAULUS no computador do escritório com a internet ligada. Se não usa mais o acesso de fora, não precisa fazer nada.",
  });
  if (!r.ok) return json({ erro: r.erro }, r.status || 502);
  await anotarHistorico(c.env, slug, "Aviso enviado a " + t.responsavel + (prazo ? " · limpeza " + prazo : ""), c.agora);
  return json({ ok: true });
}

// ------------------------------------------------------------ o reembolso

/* O reembolso pelo painel (a fila): o mesmo de worker/ia.js, devolverPagamento,
   que tambem cuida da nota fiscal. */
async function reembolsar(c, d) {
  const mp = c.deps.chamarMP;
  if (!mp) throw new Error("sem o Mercado Pago");
  const r = await devolverPagamento(c.env, mp, d.id, String(d.pagamento), { por: c.quem.email, agora: c.agora });
  if (r.aviso) throw new Error(r.aviso);
  return r.conta;
}

// ------------------------------------------------------- a visao geral

async function visao(c) {
  const { env } = c;
  const contas = await lerContas(c);
  const mes = mesBRT(c.agora);
  let assinaturas = 0, recargas = 0, entrada = 0, saida = 0, hoje = 0;
  const dias = new Map();
  for (let i = 13; i >= 0; i--) dias.set(diaBRT(c.agora - i * DIA_MS), [[0, 0], [0, 0], [0, 0]]);
  for (const conta of contas) {
    const d = conta._d;
    for (const pg of d.pagamentos || []) {
      if (mesBRT(Date.parse(pg.quando)) !== mes) continue;
      if (pg.tipo === "recarga") recargas += Number(pg.valor) || 0;
      else assinaturas += Number(pg.valor) || 0;
    }
    const um = (d.uso_mes || {})[mes];
    if (um) {
      entrada += um.entrada || 0;
      saida += um.saida || 0;
    }
    for (const u of d.uso || []) {
      if (u.dia === diaBRT(c.agora)) hoje += u.tokens || 0;
      const slot = dias.get(u.dia);
      if (!slot) continue;
      const turnos = u.turnos || [0, u.tokens || 0, 0];
      const turnosSaida = u.turnos_saida || [0, u.saida || 0, 0];
      for (let t = 0; t < 3; t++) {
        slot[t][0] += turnos[t] || 0;
        slot[t][1] += turnosSaida[t] || 0;
      }
    }
  }
  const tuneis = await lerTuneis(c);
  const escritorios = await comEscritorios(c, contas);
  const listaDias = [];
  for (const [dia, turnos] of dias) turnos.forEach(([total, s], turno) => listaDias.push({ dia, turno, total, saida: s }));
  const pr = precos(env);
  const kpi = {
    receita_mes: assinaturas + recargas, receita_assinaturas: assinaturas, receita_recargas: recargas,
    custo_usd_mes: custoUSD(env, entrada, saida), cambio: pr.cambio, entrada_mes: entrada, saida_mes: saida,
    contas: contas.length, contas_ativas: contas.filter((x) => x.situacao === "ativa" || x.situacao === "cortesia").length,
    escritorios: escritorios.length, tokens_hoje: hoje,
  };
  return { agora: new Date(c.agora).toISOString(), kpi, dias: listaDias, pendencias: await pendencias(c, contas, tuneis), avisos: await avisos(c, contas) };
}

async function pendencias(c, contas, tuneis) {
  const lista = [];
  const ren = (await renovacoes(c)).abertas.length;
  if (ren) lista.push({ icone: "warning", titulo: ren + (ren === 1 ? " ciclo venceu sem cobrança" : " ciclos venceram sem cobrança"), sub: "tolerância de 5 dias correndo", tela: "renovacoes" });
  const parados = tuneis.filter((t) => t.limpeza).length;
  if (parados) lista.push({ icone: "dns", titulo: parados + (parados === 1 ? " túnel parado" : " túneis parados"), sub: "sem conexão ou nunca conectaram; a limpeza diária está contando", tela: "tuneis", filtro: "parados" });
  const semDoc = contas.filter((x) => (x.situacao === "ativa" || x.situacao === "vencida") && !x.escritorio.documento).length;
  if (semDoc) lista.push({ icone: "contacts", titulo: semDoc + (semDoc === 1 ? " cadastro sem CPF/CNPJ" : " cadastros sem CPF/CNPJ"), sub: "assinaram antes da página Assinar pedir o cadastro", tela: "contas" });
  const fila = (await materiais(c.env)).filter((m) => m.situacao === "fila").length;
  if (fila) lista.push({ icone: "menu_book", titulo: fila + (fila === 1 ? " material na fila" : " materiais na fila"), sub: "esperando a leitura antes de publicar", tela: "materiais", filtro: "fila" });
  return lista;
}

/* Os avisos do Mercado Pago que a nuvem tratou (worker/ia.js, avisoDaIA, anota). */
async function avisos(c, contas) {
  const lista = await kvJSON(c.env, "admin:avisos", []);
  const porId = new Map(contas.map((x) => [x.id, x]));
  return lista.slice(0, 12).map((a) => {
    const conta = porId.get(a.conta);
    const nome = conta ? conta.nome : "conta " + String(a.conta || "").slice(0, 6);
    const plano = conta && conta.plano ? " · " + conta.plano.nome : "";
    let texto = a.texto || "";
    if (a.tipo === "authorized_payment") texto = (a.status === "approved" ? "Cobrança mensal · " : "Cobrança recusada · ") + nome + plano;
    else if (a.tipo === "order · pix") texto = (a.status === "processed" ? "Recarga · " : "Pix " + a.status + " · ") + nome;
    else if (a.tipo === "reembolso") texto = "Reembolso pelo painel · " + nome + plano;
    else if (/^payment · /.test(a.tipo || "")) {
      const o_que = String(a.tipo).slice(10);
      texto = ({ approved: "Pagamento · ", refunded: "Reembolso · ", charged_back: "Contestação · " }[a.status] || "Pagamento " + a.status + " · ") + o_que + " · " + nome + plano;
    } else if (a.tipo === "preapproval") texto = ({ authorized: "Assinatura ativa · ", cancelled: "Assinatura cancelada · ", paused: "Assinatura pausada · ", pending: "Assinatura pendente · " }[a.status] || "Assinatura · ") + nome + plano;
    const tom = a.status === "approved" || a.status === "processed" || a.status === "authorized" ? "entrada" : a.status === "cancelled" || a.status === "refunded" || a.status === "charged_back" ? "cancelado" : a.status === "rejected" ? "recusado" : "neutro";
    return { quando: a.quando, tipo: a.tipo, texto, valor: Number(a.valor) || 0, tom };
  });
}

// ------------------------------------------------------ nao renovacoes

async function renovacoes(c) {
  if (c._renovacoes) return c._renovacoes;
  const contas = await lerContas(c);
  const abertas = [], tratadas = [];
  for (const conta of contas) {
    const d = conta._d;
    const a = d.assinatura || {};
    if (!d.ciclo || conta.situacao === "cortesia" || a.situacao === "cancelled") continue;
    const fim = Date.parse(d.ciclo.fim);
    if (!(fim < c.agora)) continue;
    const dias = Math.floor((c.agora - fim) / DIA_MS);
    const marca = await kvJSON(c.env, "admin:renov:" + conta.id, null);
    const motivo = { paused: "assinatura pausada no Mercado Pago", pending: "a assinatura está pendente: o cartão não foi confirmado", authorized: "a cobrança do mês não chegou do Mercado Pago (cartão recusado ou sem limite)" }[a.situacao] ||
      (a.situacao ? "assinatura " + a.situacao + " no Mercado Pago" : "sem assinatura no Mercado Pago");
    const r = {
      id: conta.id, nome: conta.nome, email: conta.email, plano: conta.plano ? { nome: conta.plano.nome, valor: conta.plano.valor } : null,
      fim: d.ciclo.fim, dias_vencido: dias, tolerancia_dias: a.situacao === "authorized" ? Math.round(TOLERANCIA_MS / DIA_MS) : 0,
      motivo, lembrete_em: marca && marca.fim === d.ciclo.fim ? marca.lembrete_em || null : null,
    };
    if (marca && marca.fim === d.ciclo.fim && marca.tratada) tratadas.push(r);
    else abertas.push(r);
  }
  abertas.sort((x, y) => y.dias_vencido - x.dias_vencido);
  const config = { email: true, resumo: true, whats: false, tol: false, ...((await kvJSON(c.env, "admin:renov:config", {})) || {}) };
  c._renovacoes = { abertas, tratadas, config };
  return c._renovacoes;
}

async function acaoDeRenovacao(c, id, acao) {
  const r = await renovacoes(c);
  const item = [...r.abertas, ...r.tratadas].find((x) => x.id === id);
  if (!item) return json({ erro: "essa conta não tem ciclo vencido" }, 404);
  const marca = { fim: item.fim, ...((await kvJSON(c.env, "admin:renov:" + id, {})) || {}) };
  if (marca.fim !== item.fim) Object.assign(marca, { fim: item.fim, tratada: false, lembrete_em: null });
  if (acao === "lembrete") {
    const e = await enviarEmail(c.env, {
      para: item.email, assunto: "Seu plano do PAULUS não renovou",
      titulo: "O plano " + ((item.plano || {}).nome || "") + " não renovou",
      texto: "O ciclo do seu plano venceu em " + new Date(item.fim).toLocaleDateString("pt-BR") + " e o Mercado Pago não confirmou a cobrança do mês." +
        "\n\nEnquanto isso, o PAULUS funciona sem a IA da nuvem. Para voltar, confira o cartão na sua conta do Mercado Pago ou assine de novo em paulus.ia.br/assinatura.",
      botao: "Abrir a página Assinar", link: SITE + "/assinatura/",
    });
    if (!e.ok) return json({ erro: e.erro }, e.status || 502);
    marca.lembrete_em = new Date(c.agora).toISOString();
  } else marca.tratada = acao === "tratar";
  await c.env.APOIOS.put("admin:renov:" + id, JSON.stringify(marca));
  c._renovacoes = null;
  return json(await renovacoes(c));
}

async function configRenovacoes(c, d) {
  const atual = (await renovacoes(c)).config;
  const novo = {};
  for (const k of ["email", "resumo", "whats", "tol"]) novo[k] = k in d ? Boolean(d[k]) : atual[k];
  await c.env.APOIOS.put("admin:renov:config", JSON.stringify(novo));
  return json({ config: novo });
}

// -------------------------------------------------------- os e-mails

/* O e-mail no desenho do site: PAVLVS, o titulo, o texto, o botao e o rodape. */
export function htmlDoEmail({ titulo = "", texto = "", botao = "", link = "", pre = "", pixel = "", rodape = "" }) {
  const esc = (t) => String(t || "").replace(/[&<>"]/g, (ch) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[ch]));
  const paragrafos = esc(texto).split(/\n{2,}/).map((p) => '<p style="margin:0 0 16px;font:400 15px/1.65 Arial,sans-serif;color:#44433f">' + p.replace(/\n/g, "<br>") + "</p>").join("");
  return '<!doctype html><html><body style="margin:0;background:#f6f5f1">' +
    (pre ? '<div style="display:none;max-height:0;overflow:hidden">' + esc(pre) + "</div>" : "") +
    '<div style="max-width:560px;margin:0 auto;padding:32px 24px">' +
    // A marca em EB Garamond (site/assets/pavlvs-marca.png): o e-mail não carrega fonte da internet.
    '<div style="margin-bottom:24px"><img src="https://paulus.ia.br/assets/pavlvs-marca.png?v=2" width="120" height="22" alt="PAVLVS" ' +
    'style="display:block;border:0;font:400 18px Georgia,serif;letter-spacing:.12em;color:#8a8982"></div>' +
    (titulo ? '<h1 style="margin:0 0 18px;font:400 26px/1.2 Georgia,serif;color:#1c1c1a">' + esc(titulo) + "</h1>" : "") + paragrafos +
    (botao && link ? '<p style="margin:24px 0"><a href="' + esc(link) + '" style="display:inline-block;padding:10px 22px;border-radius:8px;background:#2a2a27;color:#f2f1ec;font:500 14px Arial,sans-serif;text-decoration:none">' + esc(botao) + "</a></p>" : "") +
    '<p style="margin:32px 0 0;padding-top:14px;border-top:1px solid #e2e1db;font:400 12px Arial,sans-serif;color:#77766f">' +
    esc(rodape || "PAVLVS · Este e-mail é automático e não recebe respostas. Dúvidas ou para não receber mais avisos: contato@paulus.ia.br") + "</p>" +
    (pixel ? '<img src="' + esc(pixel) + '" width="1" height="1" alt="" style="display:block">' : "") +
    "</div></body></html>";
}

/* `anexos` (opcional): [{nome, b64}] -> attachments do Resend (content em base64). */
export async function enviarEmail(env, { para, assunto, titulo, texto, botao, link, pre, pixel, anexos, de, rodape }) {
  if (!env.RESEND_API_KEY) return { ok: false, status: 503, erro: "o envio de e-mail ainda não está ligado: falta RESEND_API_KEY" };
  if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(String(para || ""))) return { ok: false, status: 400, erro: "e-mail do destinatário inválido" };
  try {
    const r = await fetch("https://api.resend.com/emails", {
      method: "POST",
      headers: { Authorization: "Bearer " + env.RESEND_API_KEY, "Content-Type": "application/json" },
      body: JSON.stringify({ from: de || env.EMAIL_DE || DE_EMAIL, reply_to: "contato@paulus.ia.br", to: [para], subject: String(assunto || "").slice(0, 200),
        html: htmlDoEmail({ titulo, texto, botao, link, pre, pixel, rodape }), text: [titulo, texto, botao && link ? botao + ": " + link : ""].filter(Boolean).join("\n\n"),
        ...(anexos && anexos.length ? { attachments: anexos.map((x) => ({ filename: x.nome, content: x.b64 })) } : {}) }),
    });
    if (!r.ok) {
      let msg = "";
      try {
        msg = (await r.json()).message || "";
      } catch {
        msg = "";
      }
      return { ok: false, status: 502, erro: "o provedor de e-mail recusou" + (msg ? ": " + msg : "") };
    }
    return { ok: true };
  } catch (e) {
    return { ok: false, status: 502, erro: "o provedor de e-mail não respondeu" };
  }
}

function preencher(texto, campos) {
  return String(texto || "").replace(/\{(nome|escritorio|plano|vence_em)\}/g, (_, k) => campos[k] || "");
}

function camposDe(conta) {
  const fim = conta._d && conta._d.ciclo ? new Date(conta._d.ciclo.fim).toLocaleDateString("pt-BR") : "";
  return { nome: String(conta.nome || "").split(" ")[0], escritorio: conta.escritorio.nome || conta.nome, plano: conta.plano ? conta.plano.nome : "", vence_em: fim };
}

function publicosDe(contas, extra) {
  const lista = [
    ["todos", "Todas as contas", contas],
    ["ativos", "Assinaturas ativas", contas.filter((x) => x.situacao === "ativa")],
    ["vencidos", "Vencidas e pendentes", contas.filter((x) => x.situacao === "vencida" || x.situacao === "pendente")],
    ["plus", "Plano Escritório Plus", contas.filter((x) => x.plano && x.plano.id === "plus")],
    ["semgoogle", "Sem Google ligado", contas.filter((x) => !x.google)],
  ];
  if (extra && extra.startsWith("conta:")) {
    const conta = contas.find((x) => x.id === extra.slice(6));
    if (conta) lista.unshift([extra, "Só " + conta.nome, [conta]]);
  }
  return lista;
}

async function campanhasParaTela(c) {
  const contas = await lerContas(c);
  const campanhas = [];
  for (const k of await kvPor(c.env, "admin:campanha:")) {
    const x = await kvJSON(c.env, k, null);
    if (x) campanhas.push({ id: x.id, nome: x.nome, situacao: x.situacao, publico: x.publico, enviados: x.enviados || 0, abertos: x.abertos || 0, cliques: x.cliques || 0, devolvidos: x.devolvidos || 0, quando: x.quando });
  }
  campanhas.sort((a, b) => String(b.quando).localeCompare(String(a.quando)));
  const enviadas = campanhas.filter((x) => x.enviados);
  const soma = (k) => enviadas.reduce((s, x) => s + (x[k] || 0), 0);
  const env = soma("enviados");
  const cfg = configuracao(c.env).email;
  return {
    campanhas, publicos: publicosDe(contas).map(([id, label, cs]) => ({ id, label, n: cs.length, gmail: cs.filter((x) => /@gmail\.com$/i.test(x.email)).length })),
    stats: { enviados: env, abertura: env ? Math.round((soma("abertos") / env) * 100) : 0, cliques: env ? Math.round((soma("cliques") / env) * 100) : 0, devolvidos: soma("devolvidos") },
    envio: { ligado: cfg.ligado, falta: cfg.falta, de: "naoresponda@paulus.ia.br", ritmo: RITMO_POR_MINUTO },
  };
}

async function campanhaTeste(c, camp) {
  const contas = await lerContas(c);
  const ex = contas[0] || { nome: c.quem.nome || "Teste", escritorio: { nome: "Escritório de teste" }, plano: { nome: "Escritório" }, _d: {} };
  const campos = camposDe(ex);
  const r = await enviarEmail(c.env, {
    para: c.quem.email, assunto: preencher(camp.assunto, campos), titulo: preencher(camp.titulo, campos),
    texto: preencher(camp.texto, campos), botao: camp.botao, link: camp.link, pre: preencher(camp.pre, campos),
  });
  if (!r.ok) return json({ erro: r.erro }, r.status || 502);
  return json({ ok: true, para: c.quem.email });
}

/* O Cron de cada minuto: a proxima leva de cada campanha na hora. */
export async function enviarCampanhas(env, agora = Date.now()) {
  if (!env.APOIOS || !env.RESEND_API_KEY) return { enviados: 0 };
  // Uma leitura por minuto: so o indice das que faltam enviar (listar o KV a
  // cada minuto passaria do limite diario de listagens do plano gratis).
  const fila = (await kvJSON(env, "admin:campanhas:fila", [])) || [];
  if (!fila.length) return { enviados: 0 };
  let enviados = 0;
  const restam = [];
  for (const id of fila) {
    const k = "admin:campanha:" + id;
    const camp = await kvJSON(env, k, null);
    if (!camp || !["na fila", "agendada", "enviando"].includes(camp.situacao)) continue;
    restam.push(id);
    if (camp.situacao === "agendada" && Date.parse(camp.envio_em) > agora) continue;
    const leva = (camp.destinatarios || []).slice(camp.cursor || 0, (camp.cursor || 0) + RITMO_POR_MINUTO);
    for (const dest of leva) {
      const base = SITE + "/api/e/" + camp.id + "/" + dest.t;
      const r = await enviarEmail(env, {
        para: dest.email, assunto: preencher(camp.assunto, dest), titulo: preencher(camp.titulo, dest), texto: preencher(camp.texto, dest),
        botao: camp.botao, link: camp.link ? base + "/c" : "", pre: preencher(camp.pre, dest), pixel: base + "/a.gif",
      });
      if (r.ok) camp.enviados = (camp.enviados || 0) + 1;
      else camp.devolvidos = (camp.devolvidos || 0) + 1;
      enviados++;
    }
    camp.cursor = (camp.cursor || 0) + leva.length;
    camp.situacao = camp.cursor >= (camp.destinatarios || []).length ? "enviada" : "enviando";
    // Terminou: a lista de e-mails sai do KV; ficam so os numeros.
    if (camp.situacao === "enviada") {
      camp.destinatarios = (camp.destinatarios || []).map((x) => ({ t: x.t }));
      restam.pop();
    }
    await env.APOIOS.put(k, JSON.stringify(camp));
  }
  if (restam.length !== fila.length) await env.APOIOS.put("admin:campanhas:fila", JSON.stringify(restam));
  return { enviados };
}

/* Abertura (pixel) e clique (redirecionador) de um e-mail de campanha. */
async function rastreio(env, url) {
  const m = url.pathname.match(/^\/api\/e\/([a-z0-9]{8,32})\/([a-z0-9]{8,32})\/(a\.gif|c)$/);
  const pixel = new Uint8Array([71, 73, 70, 56, 57, 97, 1, 0, 1, 0, 128, 0, 0, 0, 0, 0, 255, 255, 255, 33, 249, 4, 1, 0, 0, 0, 0, 44, 0, 0, 0, 0, 1, 0, 1, 0, 0, 2, 2, 68, 1, 0, 59]);
  if (!m || !env.APOIOS) return new Response(pixel, { headers: { "content-type": "image/gif", "cache-control": "no-store" } });
  const camp = await kvJSON(env, "admin:campanha:" + m[1], null);
  if (camp && (camp.destinatarios || []).some((x) => x.t === m[2])) {
    const marca = "admin:e:" + m[1] + ":" + m[2] + ":" + (m[3] === "c" ? "c" : "a");
    if (!(await env.APOIOS.get(marca))) {
      await env.APOIOS.put(marca, "1", { expirationTtl: 180 * 24 * 3600 });
      if (m[3] === "c") camp.cliques = (camp.cliques || 0) + 1;
      else camp.abertos = (camp.abertos || 0) + 1;
      await env.APOIOS.put("admin:campanha:" + m[1], JSON.stringify(camp));
    }
  }
  if (m[3] === "c") {
    const destino = camp && /^https:\/\//.test(String(camp.link || "")) ? camp.link : SITE + "/";
    return new Response(null, { status: 302, headers: { location: destino, "cache-control": "no-store" } });
  }
  return new Response(pixel, { headers: { "content-type": "image/gif", "cache-control": "no-store" } });
}

// ---------------------------------------------- tokens, custos e receita

async function tokens(c, visaoEscolhida, periodo) {
  const contas = await lerContas(c);
  const escritorios = await comEscritorios(c, contas);
  const agora = c.agora;
  const mes = mesBRT(agora);
  const ano = mes.slice(0, 4);
  const desde30 = diaBRT(agora - 29 * DIA_MS);
  const usoDe = (d) => {
    // {entrada, saida, modelos} do periodo
    const t = { entrada: 0, saida: 0, modelos: {} };
    const somar = (u) => {
      const e = u.entrada !== undefined ? u.entrada : u.tokens || 0;
      t.entrada += e;
      t.saida += u.saida || 0;
      for (const [nome, x] of Object.entries(u.modelos || {})) {
        t.modelos[nome] = t.modelos[nome] || { entrada: 0, saida: 0 };
        t.modelos[nome].entrada += x.entrada || 0;
        t.modelos[nome].saida += x.saida || 0;
      }
    };
    if (periodo === "30") (d.uso || []).filter((u) => u.dia >= desde30).forEach(somar);
    else Object.entries(d.uso_mes || {}).filter(([m]) => (periodo === "ano" ? m.startsWith(ano) : m === mes)).forEach(([, u]) => somar(u));
    return t;
  };
  const receitaDe = (d) => (d.pagamentos || []).filter((p) => {
    const q = Date.parse(p.quando);
    if (periodo === "30") return diaBRT(q) >= desde30;
    if (periodo === "ano") return mesBRT(q).startsWith(ano);
    return mesBRT(q) === mes;
  }).reduce((s, p) => s + (Number(p.valor) || 0), 0);
  const porConta = contas.map((x) => ({ conta: x, uso: usoDe(x._d), receita: receitaDe(x._d) }));
  const linha = (nome, itens) => {
    const entrada = itens.reduce((s, i) => s + i.uso.entrada, 0);
    const saida = itens.reduce((s, i) => s + i.uso.saida, 0);
    return { nome, entrada, saida, custo_usd: itens.reduce((s, i) => s + custoDoUso(c.env, i.uso), 0), receita: itens.reduce((s, i) => s + i.receita, 0) };
  };
  let linhas;
  if (visaoEscolhida === "conta") linhas = porConta.map((i) => linha(i.conta.nome + (i.conta.escritorio.nome && i.conta.escritorio.nome !== i.conta.nome ? " · " + i.conta.escritorio.nome : ""), [i]));
  else if (visaoEscolhida === "escritorio") linhas = escritorios.map((e) => linha(e.nome, porConta.filter((i) => e.contas.includes(i.conta.id))));
  else {
    // Geral: um por modelo (a receita das contas pagas dividida pelo uso de cada modelo) e as cortesias.
    const pagas = porConta.filter((i) => i.conta.situacao !== "cortesia");
    const receitaPaga = pagas.reduce((s, i) => s + i.receita, 0);
    const modelos = {};
    for (const i of pagas) {
      for (const [nome, x] of Object.entries(i.uso.modelos)) {
        modelos[nome] = modelos[nome] || { entrada: 0, saida: 0 };
        modelos[nome].entrada += x.entrada;
        modelos[nome].saida += x.saida;
      }
    }
    const totalPago = pagas.reduce((s, i) => s + i.uso.entrada + i.uso.saida, 0) || 1;
    const semModelo = { entrada: pagas.reduce((s, i) => s + i.uso.entrada, 0), saida: pagas.reduce((s, i) => s + i.uso.saida, 0) };
    linhas = Object.entries(modelos).map(([nome, x]) => {
      semModelo.entrada -= x.entrada;
      semModelo.saida -= x.saida;
      const m = MODELOS[nome];
      return { nome: m ? m.nome + " · " + m.empresa : nome.split("/").pop(), entrada: x.entrada, saida: x.saida, custo_usd: custoUSD(c.env, x.entrada, x.saida, nome),
        receita: receitaPaga * ((x.entrada + x.saida) / totalPago) };
    });
    if (semModelo.entrada + semModelo.saida > 0) {
      linhas.push({ nome: "Antes do registro por modelo", entrada: semModelo.entrada, saida: semModelo.saida, custo_usd: custoUSD(c.env, semModelo.entrada, semModelo.saida),
        receita: receitaPaga * ((semModelo.entrada + semModelo.saida) / totalPago) });
    }
    const cortesias = porConta.filter((i) => i.conta.situacao === "cortesia");
    if (cortesias.length) linhas.push({ ...linha("Cortesias (sem receita)", cortesias), receita: 0 });
  }
  linhas.sort((a, b) => b.entrada + b.saida - (a.entrada + a.saida));
  const tot = linha("total", porConta);
  return { kpis: { entrada: tot.entrada, saida: tot.saida, custo_usd: tot.custo_usd, receita: tot.receita, contas: contas.length }, linhas, precos: precos(c.env) };
}

// ------------------------------------------------------------ planos

async function planos(c) {
  const n = numeros(c.env);
  const contas = await lerContas(c);
  return {
    planos: n.planos.map((p) => ({ ...p, assinantes: contas.filter((x) => x.plano && x.plano.id === p.id && x.situacao === "ativa").length,
      modelo_nome: (MODELOS[p.modelos.padrao] || {}).nome || p.modelos.padrao, custo_modelo: (MODELOS[p.modelos.padrao] || {}).usd || null })),
    padrao: PLANO_PADRAO, recarga: { valor: n.recargaValor, tokens: n.recargaTokens }, precos: precos(c.env),
    json: JSON.stringify(n.planos.map(({ id, nome, valor, valor_anual, tokens: t, pessoas, modelos, recarga }) => ({ id, nome, valor, valor_anual, tokens: t, pessoas, modelos, recarga })), null, 2),
  };
}

/* Os planos publicados pelo painel ficam no KV e valem no lugar de IA_PLANOS.
   O index.js chama isto antes de atender (cache de 60 s por isolado). */
let PLANOS_CACHE = { quando: 0, valor: null };
export async function comPlanosDoPainel(env) {
  if (!env.APOIOS) return env;
  if (Date.now() - PLANOS_CACHE.quando > 60 * 1000) {
    let v = null;
    try {
      v = await env.APOIOS.get("admin:planos");
    } catch {
      v = null;
    }
    PLANOS_CACHE = { quando: Date.now(), valor: v };
  }
  return PLANOS_CACHE.valor ? { ...env, IA_PLANOS: PLANOS_CACHE.valor } : env;
}

// ---------------------------------------------------------- materiais

const RE_CPF = /\b\d{3}\.?\d{3}\.?\d{3}-?\d{2}\b/g;
const RE_CNPJ = /\b\d{2}\.?\d{3}\.?\d{3}\/?\d{4}-?\d{2}\b/g;
const RE_PROCESSO = /\b\d{7}-?\d{2}\.?\d{4}\.?\d\.?\d{2}\.?\d{4}\b/g;

export function varredura(texto) {
  const t = String(texto || "");
  const cnpj = (t.match(RE_CNPJ) || []).length;
  const processo = (t.match(RE_PROCESSO) || []).length;
  const semOutros = t.replace(RE_CNPJ, " ").replace(RE_PROCESSO, " ");
  return { cpf: (semOutros.match(RE_CPF) || []).length, cnpj, processo, nomes: null };
}

async function materiais(env) {
  const lista = [];
  for (const k of await kvPor(env, "admin:material:")) {
    const x = await kvJSON(env, k, null);
    if (!x) continue;
    lista.push({ id: x.id, slug: x.slug, tipo: x.tipo, titulo: x.titulo, areas: x.areas || [], licenca: x.licenca || "CC BY 4.0", autor: x.autor, oab: x.oab || "",
      enviado: x.enviado, situacao: x.situacao, palavras: String(x.md || "").split(/\s+/).filter(Boolean).length, texto: x.md || "", resumo: x.resumo || "", varredura: varredura(x.md) });
  }
  return lista.sort((a, b) => String(b.enviado).localeCompare(String(a.enviado)));
}

/* O PAULUS manda um material da aba Da comunidade (com o segredo da nuvem). */
async function receberMaterial(request, env, deps) {
  if (!env.APOIOS || env.IA_ATIVA !== "1" || !env.CONTAS_IA) return json({ erro: "o envio de materiais ainda não está ligado" }, 503);
  if (deps.dentroDoLimite && !(await deps.dentroDoLimite(request, env))) return json({ erro: "muitas tentativas seguidas - espere um minuto" }, 429);
  const cab = request.headers.get("authorization") || "";
  const segredo = cab.startsWith("Bearer ") ? cab.slice(7).trim() : "";
  const m = segredo.match(/^pia_([0-9a-f]{24})_([0-9a-f]{64})$/);
  if (!m) return json({ erro: "não autorizado" }, 401);
  const conta = medidor(env, m[1]);
  if (!(await conta.pedir("conferir", { hash: await sha256Hex(segredo) })).ok) return json({ erro: "não autorizado" }, 401);
  const d = (await lerJSON(request)) || {};
  const md = String(d.texto || "").slice(0, 200000);
  const titulo = String(d.titulo || "").replace(/[\u0000-\u001f<>]/g, "").trim().slice(0, 160);
  const autor = String(d.autor || "").replace(/[\u0000-\u001f<>]/g, "").trim().slice(0, 100);
  const tipo = ["artigo", "modelo", "tabela"].includes(d.tipo) ? d.tipo : "artigo";
  if (titulo.length < 3 || md.length < 200 || !autor) return json({ erro: "faltam o título, o autor ou o texto (pelo menos 200 caracteres)" }, 400);
  const slug = titulo.normalize("NFD").replace(/[̀-ͯ]/g, "").toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "").slice(0, 60) || "material";
  const id = "m" + aleatorio(6);
  await env.APOIOS.put("admin:material:" + id, JSON.stringify({
    id, slug, tipo, titulo, autor, oab: String(d.oab || "").slice(0, 20), areas: (Array.isArray(d.areas) ? d.areas : []).map(String).slice(0, 6),
    licenca: "CC BY 4.0", resumo: String(d.resumo || "").slice(0, 400), md, enviado: new Date().toISOString(), situacao: "fila", conta: m[1],
  }));
  return json({ ok: true, id, situacao: "fila" });
}

// ------------------------------------------------------------- NFS-e

/* A aba Notas fiscais: o emissor da nuvem (situacao, notas, pagamentos sem
   nota, Cloudflare) e o que o papel pode (worker/nfse/api.js, resumoParaPainel). */
async function nfse(c) {
  const r = await resumoParaPainel(c.env);
  return { ...r, pode: { emitir: PODE_NFSE.includes(c.quem.papel) } };
}

// ------------------------------------------------------------- equipe

async function equipe(c) {
  const lista = await listaDaEquipe(c.env);
  const membros = [];
  for (const m of lista) {
    const ac = await kvJSON(c.env, "admin:acesso:" + String(m.email).toLowerCase(), null);
    membros.push({ email: String(m.email).toLowerCase(), nome: m.nome || "", papel: m.papel, ultimo: ac ? ac.ultimo : null });
  }
  return { membros, matriz: MATRIZ.map(([acao, papeis]) => ({ acao, dono: papeis.includes("dono"), financeiro: papeis.includes("financeiro"), suporte: papeis.includes("suporte") })) };
}

// -------------------------------------------------------------- busca

async function busca(c, q) {
  const nq = String(q || "").toLowerCase().normalize("NFD").replace(/[̀-ͯ]/g, "").trim();
  const vazio = { contas: [], escritorios: [], tuneis: [], planos: [], materiais: [] };
  if (nq.length < 2) return vazio;
  const bate = (...t) => t.join(" ").toLowerCase().normalize("NFD").replace(/[̀-ͯ]/g, "").includes(nq);
  const contas = await lerContas(c);
  const escritorios = await comEscritorios(c, contas);
  const tuneis = await lerTuneis(c);
  return {
    contas: contas.filter((x) => bate(x.nome, x.email, x.oab, x.escritorio.nome)).slice(0, 6).map((x) => ({ titulo: x.nome, desc: x.email + (x.plano ? " · " + x.plano.nome : "") + " · " + x.situacao, tela: "contas", alvo: x.id })),
    escritorios: escritorios.filter((e) => bate(e.nome, e.slug, e.documento)).slice(0, 6).map((e) => ({ titulo: e.nome, desc: e.contas.length + (e.contas.length === 1 ? " conta" : " contas") + (e.slug ? " · " + e.slug + ".paulus.ia.br" : ""), tela: "contas", alvo: e.nome })),
    tuneis: tuneis.filter((t) => bate(t.slug, t.nome, t.responsavel)).slice(0, 6).map((t) => ({ titulo: t.slug + ".paulus.ia.br", desc: t.nome + " · " + t.estado, tela: "tuneis", alvo: t.slug })),
    planos: numeros(c.env).planos.filter((p) => bate(p.nome, p.id)).slice(0, 6).map((p) => ({ titulo: p.nome, desc: brl(p.valor) + "/mês · " + brl(p.valor_anual) + "/ano · " + Math.round(p.tokens / 1e6) + "M créditos", tela: "planos", alvo: p.id })),
    materiais: (await materiais(c.env)).filter((x) => bate(x.titulo, x.autor, (x.areas || []).join(" "))).slice(0, 6).map((x) => ({ titulo: x.titulo, desc: x.autor + " · " + x.situacao, tela: "materiais", alvo: x.id })),
  };
}

// ----------------------------------------------------------- a fila

function chaveDaFila(c) {
  return "admin:pendentes:" + c.quem.email;
}

async function alteracoes(c) {
  return { pendentes: (await kvJSON(c.env, chaveDaFila(c), [])) || [], publicacoes: (await kvJSON(c.env, "admin:publicacoes", [])) || [] };
}

async function enfileirar(c, d) {
  const tipo = String(d.tipo || "");
  if (!PODE[tipo]) return json({ erro: "alteração desconhecida: " + tipo }, 400);
  if (!PODE[tipo].includes(c.quem.papel)) return json({ erro: "o papel " + c.quem.papel + " não pode fazer isso" }, 403);
  const erro = await conferirAlteracao(c, tipo, d.dados || {});
  if (erro) return json({ erro }, 400);
  const lista = (await kvJSON(c.env, chaveDaFila(c), [])) || [];
  lista.push({ id: aleatorio(6), quando: new Date(c.agora).toISOString(), tela: String(d.tela || "").slice(0, 40), tipo, alvo: String(d.alvo || "").slice(0, 120),
    dados: d.dados || {}, texto: String(d.texto || tipo).slice(0, 300) });
  await c.env.APOIOS.put(chaveDaFila(c), JSON.stringify(lista));
  return json({ pendentes: lista });
}

async function tirarDaFila(c, id) {
  const lista = ((await kvJSON(c.env, chaveDaFila(c), [])) || []).filter((x) => x.id !== id);
  await c.env.APOIOS.put(chaveDaFila(c), JSON.stringify(lista));
  return json({ pendentes: lista });
}

/* O que da para conferir antes de entrar na fila (formato, existencia). */
async function conferirAlteracao(c, tipo, d) {
  if (tipo.startsWith("conta.") || tipo.startsWith("google.")) {
    if (!/^[0-9a-f]{24}$/.test(String(d.id || ""))) return "conta inválida";
  }
  if (tipo === "conta.creditar" && !(Number(d.tokens) > 0 && Number(d.tokens) <= 1e9)) return "quantos tokens?";
  if (tipo === "conta.reembolsar") {
    if (!/^[A-Za-z0-9-]{3,40}$/.test(String(d.pagamento || ""))) return "qual pagamento?";
    const det = await medidor(c.env, d.id).pedir("admin_detalhe");
    const p = (det.pagamentos || []).find((x) => String(x.ref) === String(d.pagamento));
    if (!p) return "esse pagamento não está na conta";
    if (p.reembolso) return "esse pagamento já foi reembolsado";
  }
  if (tipo.startsWith("tunel.") && !/^[a-z0-9-]{3,24}$/.test(String(d.slug || ""))) return "endereço inválido";
  if (tipo === "tunel.endereco") {
    const motivo = await motivoDoEnderecoNovo(c.env, String(d.novo || ""));
    if (motivo) return d.novo + ": " + motivo;
  }
  if (tipo === "plano.criar") {
    if (!/^[a-z0-9-]{2,24}$/.test(String(d.id || ""))) return "o id tem de 2 a 24 letras minúsculas, números e hífen";
    if (numeros(c.env).planos.some((p) => p.id === d.id)) return "esse id já existe";
    if (!String(d.nome || "").trim()) return "dê um nome ao plano";
  }
  if ((tipo === "plano.criar" || tipo === "plano.editar") && !(Number(d.valor) > 0 && Number(d.tokens) > 0)) return "valor e tokens precisam ser maiores que zero";
  if (tipo === "plano.criar" && !(Number(d.valor_anual) > 0)) return "diga o valor do ano";
  if (tipo === "plano.editar" && d.valor_anual !== undefined && !(Number(d.valor_anual) > 0)) return "o valor do ano precisa ser maior que zero";
  if (tipo === "equipe.papel" && !PAPEIS.includes(d.papel)) return "papel inválido";
  if (tipo === "campanha.disparar") {
    if (!String(d.assunto || "").trim() || !String(d.texto || "").trim()) return "a campanha precisa de assunto e texto";
  }
  return "";
}

/* Publicar: aplica a fila na ordem. Uma que falha nao desfaz as outras. */
async function publicar(c, d) {
  if (String(d.confirmacao || "").trim().toLowerCase() !== CONFIRMACAO) return json({ erro: "digite exatamente: " + CONFIRMACAO }, 400);
  const lista = (await kvJSON(c.env, chaveDaFila(c), [])) || [];
  if (!lista.length) return json({ erro: "nada para publicar" }, 409);
  const resultados = [];
  const commits = [];
  for (const alt of lista) {
    if (!PODE[alt.tipo] || !PODE[alt.tipo].includes(c.quem.papel)) {
      resultados.push({ id: alt.id, ok: false, erro: "o papel " + c.quem.papel + " não pode" });
      continue;
    }
    try {
      const r = await aplicar(c, alt);
      if (r && r.commit) commits.push(r.commit);
      resultados.push({ id: alt.id, ok: true });
    } catch (e) {
      resultados.push({ id: alt.id, ok: false, erro: String((e && e.message) || e).slice(0, 200) });
    }
  }
  const falharam = lista.filter((alt) => resultados.find((r) => r.id === alt.id && !r.ok));
  await c.env.APOIOS.put(chaveDaFila(c), JSON.stringify(falharam));
  const feitas = lista.length - falharam.length;
  const publicacao = {
    quando: new Date(c.agora).toISOString(), commit: commits.length ? commits[commits.length - 1].slice(0, 7) : "kv-" + aleatorio(3).slice(0, 5),
    resumo: lista.filter((a) => !falharam.includes(a)).map((a) => a.texto).slice(0, 3).join(" · ") + (feitas > 3 ? " · +" + (feitas - 3) : ""),
    n: feitas, por: c.quem.login || c.quem.email,
  };
  if (feitas) {
    const pubs = (await kvJSON(c.env, "admin:publicacoes", [])) || [];
    pubs.unshift(publicacao);
    await c.env.APOIOS.put("admin:publicacoes", JSON.stringify(pubs.slice(0, 30)));
  }
  return json({ ok: !falharam.length, resultados, publicacao });
}

async function aplicar(c, alt) {
  const { env } = c;
  const d = alt.dados || {};
  const mp = c.deps.chamarMP;
  switch (alt.tipo) {
    case "conta.creditar":
      return medidor(env, d.id).pedir("admin_creditar", { tokens: Number(d.tokens), por: c.quem.email });
    case "conta.instalacao.apagar": {
      const r = await medidor(env, d.id).pedir("admin_apagar_segredo", { hash8: d.hash8 });
      if (!r.apagados) throw new Error("essa instalação já não estava na conta");
      return r;
    }
    case "conta.reembolsar":
      return reembolsar(c, d);
    case "conta.cancelar": {
      const r = await medidor(env, d.id).pedir("resumo");
      const a = r.assinatura;
      if (!a || !a.id || a.situacao === "cancelled") throw new Error("não há assinatura ativa");
      if (a.periodo === "anual" || a.periodo === "avulso") throw new Error("o plano pago de uma vez não renova sozinho: não há o que cancelar (para devolver o dinheiro, use Reembolsar)");
      if (!mp) throw new Error("sem o Mercado Pago");
      const res = await mp(env, "/preapproval/" + encodeURIComponent(a.id), "PUT", { status: "cancelled" });
      if (!res.ok) throw new Error("o Mercado Pago recusou cancelar (HTTP " + res.status + ")");
      return medidor(env, d.id).pedir("admin_assinatura_cancelada");
    }
    case "google.servicos":
      return medidor(env, d.id).pedir("admin_google", { ligados: d.ligados || [] });
    case "google.desvincular":
      return medidor(env, d.id).pedir("admin_desvincular", { por: c.quem.email });
    case "tunel.apagar":
      return liberarEndereco(env, d.slug, "apagado pelo painel");
    case "tunel.endereco":
      return alterarEndereco(env, d.slug, String(d.novo), c.agora);
    case "tunel.ativo":
      return ativarEndereco(env, d.slug, Boolean(d.ativo), c.agora);
    case "campanha.disparar":
      return dispararCampanha(c, d);
    case "plano.criar":
    case "plano.editar":
      return aplicarPlano(c, alt.tipo, d);
    case "material.situacao":
      return aplicarMaterial(c, d);
    case "nfse.config":
      await env.APOIOS.put("admin:nfse:config", JSON.stringify({ auto: Boolean(d.auto), email: Boolean(d.email), mail: Boolean(d.mail) }));
      return {};
    case "equipe.papel": {
      const lista = await listaDaEquipe(env);
      const m = lista.find((x) => String(x.email).toLowerCase() === String(d.email).toLowerCase());
      if (!m) throw new Error("essa pessoa não está na equipe");
      m.papel = d.papel;
      if (!lista.some((x) => x.papel === "dono")) throw new Error("a equipe precisa de pelo menos um dono");
      await env.APOIOS.put("admin:equipe", JSON.stringify(lista));
      return {};
    }
    default:
      throw new Error("alteração desconhecida");
  }
}

async function aplicarPlano(c, tipo, d) {
  const { env } = c;
  const lista = numeros(env).planos.map((p) => ({ ...p }));
  const valor = Math.round(Number(d.valor) * 100) / 100;
  const tokensDoPlano = Math.round(Number(d.tokens) < 10000 ? Number(d.tokens) * 1e6 : Number(d.tokens));
  if (tipo === "plano.criar") {
    if (lista.some((p) => p.id === d.id)) throw new Error("esse id já existe");
    lista.push({ id: String(d.id), nome: String(d.nome).trim().slice(0, 40), valor, valor_anual: Math.round(Number(d.valor_anual) * 100) / 100, tokens: tokensDoPlano });
  } else {
    const p = lista.find((x) => x.id === d.id);
    if (!p) throw new Error("esse plano não existe");
    p.valor = valor;
    p.tokens = tokensDoPlano;
    if (d.valor_anual !== undefined) p.valor_anual = Math.round(Number(d.valor_anual) * 100) / 100;
  }
  await env.APOIOS.put("admin:planos", JSON.stringify(lista));
  PLANOS_CACHE = { quando: 0, valor: null };
  if (tipo !== "plano.editar") return {};
  // Quem ja assina passa a pagar o valor novo a partir da proxima cobranca
  // (o Mercado Pago cobra o que o preapproval disser); o ciclo pago fica.
  const contas = await lerContas(c);
  const mp = c.deps.chamarMP;
  const erros = [];
  for (const conta of contas.filter((x) => x.plano && x.plano.id === d.id && (x._d.assinatura || {}).situacao === "authorized")) {
    const a = conta._d.assinatura;
    if (!mp) continue;
    const r = await mp(env, "/preapproval/" + encodeURIComponent(a.id), "PUT", { auto_recurring: { transaction_amount: valor, currency_id: "BRL" } });
    if (!r.ok) erros.push(conta.nome);
  }
  if (erros.length) throw new Error("o plano mudou, mas o Mercado Pago recusou o valor novo de: " + erros.join(", "));
  return {};
}

async function aplicarMaterial(c, d) {
  const { env } = c;
  const mat = await kvJSON(env, "admin:material:" + d.id, null);
  if (!mat) throw new Error("esse material não existe mais");
  let commit = "";
  if (d.situacao === "publicado") commit = await publicarMaterial(c, mat);
  if (d.situacao === "recusado" && mat.situacao === "publicado") commit = await tirarMaterial(c, mat);
  mat.situacao = d.situacao;
  mat.recado = String(d.recado || "").slice(0, 2000);
  await env.APOIOS.put("admin:material:" + mat.id, JSON.stringify(mat));
  // O autor fica sabendo (se o e-mail estiver ligado; sem ele, segue sem avisar).
  const conta = mat.conta ? await medidor(env, mat.conta).pedir("resumo").catch(() => null) : null;
  if (conta && conta.email && env.RESEND_API_KEY) {
    const frases = {
      publicado: ["Seu material foi publicado", "“" + mat.titulo + "” está em paulus.ia.br/materiais, com o seu nome e a licença " + mat.licenca + "."],
      ajustes: ["Seu material precisa de um ajuste", "Lemos “" + mat.titulo + "” e ele precisa de um ajuste antes de publicar."],
      recusado: ["Seu material não foi publicado", "Lemos “" + mat.titulo + "” e ele não vai para paulus.ia.br/materiais."],
    }[d.situacao];
    if (frases) await enviarEmail(env, { para: conta.email, assunto: frases[0], titulo: frases[0], texto: frases[1] + (mat.recado ? "\n\n" + mat.recado : "") });
  }
  return { commit };
}

/* O .md em site/materiais e a linha em site/dados/materiais.json, pelo GitHub
   (com o token do login social de quem publica). O push dispara o deploy. */
async function publicarMaterial(c, mat) {
  const gh = c.deps.github || chamarGitHub;
  const token = c.quem.token;
  if (!token) throw new Error("entre com o GitHub de novo para publicar");
  const caminho = "site/materiais/" + mat.slug + ".md";
  const conteudo = mat.md;
  const b64 = btoa(String.fromCharCode(...new TextEncoder().encode(conteudo)));
  const atual = await gh("GET", "https://api.github.com/repos/" + REPO + "/contents/" + caminho + "?ref=" + RAMO, token);
  const md = await gh("PUT", "https://api.github.com/repos/" + REPO + "/contents/" + caminho, token, {
    message: "Materiais: publica \"" + mat.titulo + "\" de " + mat.autor + " (painel admin, " + c.quem.login + ")",
    content: b64, branch: RAMO, ...(atual.ok && atual.dados && atual.dados.sha ? { sha: atual.dados.sha } : {}),
  });
  if (!md.ok) throw new Error("o GitHub recusou gravar " + caminho + " (HTTP " + md.status + ")");
  const lista = await gh("GET", "https://api.github.com/repos/" + REPO + "/contents/site/dados/materiais.json?ref=" + RAMO, token);
  if (!lista.ok || !lista.dados) throw new Error("não consegui ler site/dados/materiais.json no GitHub");
  const json_ = JSON.parse(new TextDecoder().decode(Uint8Array.from(atob(String(lista.dados.content).replace(/\n/g, "")), (ch) => ch.charCodeAt(0))));
  json_.materiais = (json_.materiais || []).filter((x) => x.slug !== mat.slug);
  json_.materiais.unshift({
    slug: mat.slug, titulo: mat.titulo, autor: mat.autor, oab: mat.oab || "", areas: mat.areas || [], tipo: mat.tipo, resumo: mat.resumo || "",
    publicado_em: new Date(c.agora).toISOString().slice(0, 10), licenca: mat.licenca, arquivo: "/materiais/" + mat.slug + ".md", sha256: await sha256Hex(conteudo),
  });
  json_.atualizado_em = new Date(c.agora).toISOString().slice(0, 10);
  const texto = JSON.stringify(json_, null, 2) + "\n";
  const r = await gh("PUT", "https://api.github.com/repos/" + REPO + "/contents/site/dados/materiais.json", token, {
    message: "Materiais: \"" + mat.titulo + "\" na lista (painel admin)", content: btoa(String.fromCharCode(...new TextEncoder().encode(texto))),
    branch: RAMO, sha: lista.dados.sha,
  });
  if (!r.ok) throw new Error("o GitHub recusou atualizar site/dados/materiais.json (HTTP " + r.status + ")");
  return (r.dados && r.dados.commit && r.dados.commit.sha) || (md.dados && md.dados.commit && md.dados.commit.sha) || "";
}

async function tirarMaterial(c, mat) {
  const gh = c.deps.github || chamarGitHub;
  const token = c.quem.token;
  if (!token) throw new Error("entre com o GitHub de novo para tirar do ar");
  const lista = await gh("GET", "https://api.github.com/repos/" + REPO + "/contents/site/dados/materiais.json?ref=" + RAMO, token);
  if (!lista.ok || !lista.dados) throw new Error("não consegui ler site/dados/materiais.json no GitHub");
  const json_ = JSON.parse(new TextDecoder().decode(Uint8Array.from(atob(String(lista.dados.content).replace(/\n/g, "")), (ch) => ch.charCodeAt(0))));
  json_.materiais = (json_.materiais || []).filter((x) => x.slug !== mat.slug);
  const texto = JSON.stringify(json_, null, 2) + "\n";
  const r = await gh("PUT", "https://api.github.com/repos/" + REPO + "/contents/site/dados/materiais.json", token, {
    message: "Materiais: tira \"" + mat.titulo + "\" do ar (painel admin)", content: btoa(String.fromCharCode(...new TextEncoder().encode(texto))),
    branch: RAMO, sha: lista.dados.sha,
  });
  if (!r.ok) throw new Error("o GitHub recusou atualizar site/dados/materiais.json (HTTP " + r.status + ")");
  return (r.dados && r.dados.commit && r.dados.commit.sha) || "";
}

/* O disparo de uma campanha: a lista de quem recebe fica no KV ate o fim do
   envio (o Cron manda 50 por minuto) e sai depois; ficam so os numeros. */
async function dispararCampanha(c, d) {
  const contas = await lerContas(c);
  const pub = publicosDe(contas, d.publico).find((x) => x[0] === d.publico);
  if (!pub) throw new Error("esse público não existe mais");
  const id = "c" + aleatorio(7);
  const agora = c.agora;
  // As 9 h de Brasilia (12 h UTC) de amanha ou da proxima segunda.
  const proxima = (diaSemana) => {
    const hoje = new Date(agora - 3 * 3600 * 1000);
    const base = Date.UTC(hoje.getUTCFullYear(), hoje.getUTCMonth(), hoje.getUTCDate(), 12);
    const dias = diaSemana === undefined ? 1 : ((diaSemana - hoje.getUTCDay() + 7) % 7) || 7;
    return new Date(base + dias * DIA_MS).toISOString();
  };
  const envioEm = d.quando === "amanha" ? proxima() : d.quando === "segunda" ? proxima(1) : new Date(agora).toISOString();
  const camp = {
    id, nome: String(d.nome || d.assunto || "Campanha").slice(0, 80), publico: { id: pub[0], label: pub[1] },
    assunto: String(d.assunto).slice(0, 200), pre: String(d.pre || "").slice(0, 200), titulo: String(d.titulo || "").slice(0, 160),
    texto: String(d.texto).slice(0, 8000), botao: String(d.botao || "").slice(0, 40), link: /^https:\/\//.test(String(d.link || "")) ? String(d.link) : "",
    situacao: d.quando === "agora" || !d.quando ? "na fila" : "agendada", envio_em: envioEm, quando: envioEm, por: c.quem.email,
    destinatarios: pub[2].filter((x) => x.email).map((x) => ({ t: aleatorio(6), email: x.email, ...camposDe(x) })), cursor: 0, enviados: 0, abertos: 0, cliques: 0, devolvidos: 0,
  };
  await c.env.APOIOS.put("admin:campanha:" + id, JSON.stringify(camp));
  const fila = (await kvJSON(c.env, "admin:campanhas:fila", [])) || [];
  await c.env.APOIOS.put("admin:campanhas:fila", JSON.stringify([...fila, id]));
  return { id };
}
