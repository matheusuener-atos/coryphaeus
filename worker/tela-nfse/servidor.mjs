// Servidor local para ver a aba Notas fiscais do painel no navegador, sem rede:
//   node worker/tela-nfse/servidor.mjs [porta]      (padrão 8791)
// e abra http://127.0.0.1:8791/admin/ (ou rode teste_tela.py, com o Playwright).
//
// Serve site/ como arquivos e /api/* com o painel de verdade (worker/admin.js)
// e o emissor de verdade (o DO EmissorNFSe em SQLite do node), com tudo o que
// é de fora simulado: o Cloudflare Access (o JWT entra aqui em cada pedido), a
// sessão do GitHub (já aberta), a Sefin (sefin-simulada.js), a API da
// Cloudflare e o Resend. Duas contas: Ana (cadastro completo) e Bruno (sem
// endereço), e um pagamento da Ana sem nota.
import { createServer } from "node:http";
import { readFileSync, existsSync, statSync } from "node:fs";
import { DatabaseSync } from "node:sqlite";
import { fileURLToPath } from "node:url";
import { dirname, join, normalize, extname } from "node:path";

import { atenderAdmin } from "../admin.js";
import { ContaIA } from "../ia.js";
import { EmissorNFSe } from "../nfse/emissor.js";
import { SefinSimulada } from "../nfse/sefin-simulada.js";
import { b64 } from "../nfse/assinatura.js";
import { hojeBrasilia } from "../nfse/dps.js";

const AQUI = dirname(fileURLToPath(import.meta.url));
const SITE = join(AQUI, "..", "..", "site");
const PORTA = Number(process.argv[2] || 8791);
const PAPEL = process.env.PAPEL || "dono";

const kv = new Map();
const APOIOS = {
  get: async (k) => (kv.has(k) ? kv.get(k) : null),
  put: async (k, v) => { kv.set(k, v); },
  delete: async (k) => { kv.delete(k); },
  list: async ({ prefix }) => ({ list_complete: true, keys: [...kv.keys()].filter((k) => k.startsWith(prefix)).map((name) => ({ name })) }),
};
const objetos = new Map();
const CONTAS_IA = {
  idFromName: (n) => n,
  get: (n) => ({ fetch: (url, init) => {
    if (!objetos.has(n)) {
      const dados = new Map();
      objetos.set(n, new ContaIA({ storage: { get: async (k) => structuredClone(dados.get(k)), put: async (k, v) => { dados.set(k, structuredClone(v)); } } }, { APOIOS }));
    }
    return objetos.get(n).fetch(new Request(url, init));
  } }),
};
const db = new DatabaseSync(":memory:");
let alarme = null;
const storage = {
  sql: { exec(q, ...b) { const l = db.prepare(q).all(...b); return { toArray: () => l }; } },
  transactionSync(fn) {
    db.exec("BEGIN");
    try {
      const r = fn();
      db.exec("COMMIT");
      return r;
    } catch (e) {
      db.exec("ROLLBACK");
      throw e;
    }
  },
  getAlarm: async () => alarme, setAlarm: async (t) => { alarme = Number(t); }, deleteAlarm: async () => { alarme = null; },
};
const sim = new SefinSimulada("sucesso");
let emissor = null;
const EMISSOR_NFSE = { idFromName: (n) => n, get: () => ({ fetch: (url, init) => emissor.fetch(new Request(url, init)) }) };

// A API da Cloudflare e o Resend de mentira (o registro fica em /__chamadas).
const chamadas = [];
let cfSeq = 0;
globalThis.fetch = async (url, init = {}) => {
  const u = String(url);
  if (u === "https://api.resend.com/emails") {
    chamadas.push({ para: "resend", corpo: JSON.parse(init.body).subject });
    return Response.json({ id: "e" + chamadas.length });
  }
  if (u.startsWith("https://api.cloudflare.com/")) {
    chamadas.push({ para: "cloudflare", metodo: init.method, caminho: u.slice(36) });
    if (init.method === "POST") return Response.json({ success: true, result: { id: "mtls-" + ++cfSeq } });
    return Response.json({ success: true, result: {} });
  }
  return new Response("{}", { status: 404 });
};

const TIME = "paulus.cloudflareaccess.com";
const AUD = "aud";
const par = await crypto.subtle.generateKey({ name: "RSASSA-PKCS1-v1_5", modulusLength: 2048, publicExponent: new Uint8Array([1, 0, 1]), hash: "SHA-256" }, true, ["sign", "verify"]);
const jwk = { ...(await crypto.subtle.exportKey("jwk", par.publicKey)), kid: "k1" };
const b64url = (x) => Buffer.from(x).toString("base64").replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/, "");
async function jwt(email) {
  const cab = b64url(JSON.stringify({ alg: "RS256", kid: "k1" }));
  const corpo = b64url(JSON.stringify({ email, aud: [AUD], iss: "https://" + TIME, exp: Date.now() / 1000 + 3600 }));
  return cab + "." + corpo + "." + b64url(new Uint8Array(await crypto.subtle.sign("RSASSA-PKCS1-v1_5", par.privateKey, new TextEncoder().encode(cab + "." + corpo))));
}
const EMAIL = PAPEL + "@paulus.ia.br";
const env = {
  IA_ATIVA: "1", CONTAS_IA, APOIOS, ACCESS_TEAM: TIME, ACCESS_AUD: AUD, GITHUB_CLIENT_ID: "cid", GITHUB_CLIENT_SECRET: "x", RESEND_API_KEY: "re_x",
  EMISSOR_NFSE, NFSE_CHAVE_MESTRA: b64(crypto.getRandomValues(new Uint8Array(32))), SEFIN_MTLS: { fetch: sim.fetch }, CF_ACCOUNT_ID: "54164f67b5d5eb33c0a1d325dfebb449",
  ADMIN_EQUIPE: JSON.stringify([{ email: EMAIL, nome: "Teste", papel: PAPEL }, { email: "dono@paulus.ia.br", nome: "Dono", papel: "dono" }]),
  ASSETS: { fetch: async () => Response.json({ versao: "0.9.22" }) },
};
emissor = new EmissorNFSe({ storage }, env);
const deps = {
  chavesDoAccess: async () => [jwk], chamarMP: async () => ({ ok: true, status: 200, dados: {} }),
  github: async (m, url) => (url.includes("access_token") ? { ok: true, dados: { access_token: "gho_t" } } : url.endsWith("/user") ? { ok: true, dados: { login: "teste" } } : { ok: true, dados: { permission: "write" } }),
};
const ctx = { waitUntil: (p) => p.catch(() => {}) };
async function painel(req) {
  return atenderAdmin(req, env, new URL(req.url), ctx, deps);
}
// a sessão do GitHub já aberta
let r = await painel(new Request("http://x/api/admin/github/entrar", { headers: { "cf-access-jwt-assertion": await jwt(EMAIL) } }));
const state = new URL(r.headers.get("location")).searchParams.get("state");
r = await painel(new Request("http://x/api/admin/github/retorno?code=c&state=" + state, { headers: { "cf-access-jwt-assertion": await jwt(EMAIL) } }));
const SESSAO = r.headers.get("set-cookie").match(/pv_admin=([0-9a-f]+)/)[1];

// as contas e um pagamento
async function doDe(id, acao, dados = {}) {
  return (await CONTAS_IA.get(id).fetch("https://c/" + acao, { method: "POST", body: JSON.stringify({ acao, ...dados, numeros: { planos: [{ id: "escritorio", nome: "Escritório", valor: 300, tokens: 1000 }], recargas: [] } }) })).json();
}
const ANA = "a".repeat(24);
const BRUNO = "b".repeat(24);
for (const [id, nome] of [[ANA, "ana"], [BRUNO, "bruno"]]) await doDe(id, "ativar", { id, dono: { sub: nome, email: nome + "@escritorio.com.br" }, nome: "Escritório " + nome, instalacao: "inst-" + nome + "-1", hash: "h" + nome });
await doDe(ANA, "cadastro", { cadastro: { nome_escritorio: "Ana Advocacia", documento: "52998224725", telefone: "91988887777", oab: "PA 12345", termos: "x",
  endereco: { cep: "66010000", logradouro: "Rua dos Mundurucus", numero: "1500", complemento: "Sala 3", bairro: "Batista Campos", cidade: "Belém", uf: "PA", cmun: "1501402" } } });
kv.set("admin:nfse:PAY1", JSON.stringify({ id: "PAY1", conta: ANA, tipo: "mensalidade", valor: 300, quando: hojeBrasilia() + "T10:00:00Z", nota: "pendente" }));
kv.set("admin:nfse:PAY2", JSON.stringify({ id: "PAY2", conta: BRUNO, tipo: "recarga pix", valor: 50, quando: hojeBrasilia() + "T11:00:00Z", nota: "pendente", motivo: "emissão automática parada: falta CEP, rua do cliente (Notas fiscais › Clientes)" }));

const TIPOS = { ".html": "text/html; charset=utf-8", ".js": "text/javascript; charset=utf-8", ".css": "text/css; charset=utf-8", ".svg": "image/svg+xml", ".png": "image/png", ".ico": "image/x-icon", ".json": "application/json" };
createServer(async (req, res) => {
  try {
    const url = new URL(req.url, "http://127.0.0.1:" + PORTA);
    if (url.pathname === "/__chamadas") {
      res.writeHead(200, { "content-type": "application/json" });
      return res.end(JSON.stringify(chamadas));
    }
    if (url.pathname.startsWith("/api/")) {
      const corpo = await new Promise((ok) => { const p = []; req.on("data", (c) => p.push(c)); req.on("end", () => ok(Buffer.concat(p))); });
      const headers = new Headers({ "cf-access-jwt-assertion": await jwt(EMAIL), cookie: "pv_admin=" + SESSAO });
      if (req.headers["content-type"]) headers.set("content-type", req.headers["content-type"]);
      const resposta = await painel(new Request("https://paulus.ia.br" + url.pathname + url.search, { method: req.method, headers, body: ["GET", "HEAD"].includes(req.method) ? undefined : corpo }));
      const h = {};
      resposta.headers.forEach((v, k) => { if (k !== "set-cookie") h[k] = v; });
      res.writeHead(resposta.status, h);
      return res.end(Buffer.from(await resposta.arrayBuffer()));
    }
    let caminho = normalize(join(SITE, decodeURIComponent(url.pathname)));
    if (!caminho.startsWith(SITE)) { res.writeHead(403); return res.end(); }
    if (existsSync(caminho) && statSync(caminho).isDirectory()) caminho = join(caminho, "index.html");
    if (!existsSync(caminho)) { res.writeHead(404); return res.end("não encontrado"); }
    res.writeHead(200, { "content-type": TIPOS[extname(caminho)] || "application/octet-stream" });
    res.end(readFileSync(caminho));
  } catch (e) {
    res.writeHead(500);
    res.end(String(e && e.stack || e));
  }
}).listen(PORTA, "127.0.0.1", () => console.log("painel local em http://127.0.0.1:" + PORTA + "/admin/ (papel " + PAPEL + ")"));
