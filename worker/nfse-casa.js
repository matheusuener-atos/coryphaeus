// A ponte da NFS-e (contrato em worker/admin-api.md, "Ponte da NFS-e").
//
// Quem emite as NFS-e dos assinantes e o PAULUS da casa (a tela "Notas do
// PAVLVS", no servidor do dono). Ele fala com o Worker por /api/nfse-casa/*:
// le os clientes (o tomador de cada um) e os pagamentos, e devolve cada nota
// emitida (meta, PDF e XML). O PAULUS de cada cliente busca as proprias notas
// em /api/ia/nfse (worker/ia.js, notasDoCliente, com o segredo da instalacao).
//
// Estas rotas ficam FORA do Cloudflare Access (que protege so /admin e
// /api/admin) e fora da sessao do GitHub: a porta e o segredo NFSE_CASA_TOKEN
// (npx wrangler secret put NFSE_CASA_TOKEN), em Authorization: Bearer.
// Sem o segredo, 503; com o errado, 401.
//
// No KV APOIOS:
//   nfse:tomador:<conta>          o que a casa corrigiu do tomador (vence o cadastro)
//   nfse:nota:<conta>:<id>        a meta da nota
//   nfse:nota-pdf:<conta>:<id>    o PDF (base64)
//   nfse:nota-xml:<conta>:<id>    o XML (base64)
//   admin:nfse-casa:visto         a ultima chamada valida (ISO)
//   admin:nfse:<pagamento>        a fila do painel; a nota emitida a marca

import { contasDaCasa } from "./admin.js";
import { cpfValido, cnpjValido } from "./ia.js";

const PREFIXO = "/api/nfse-casa/";
const MAX_ARQUIVO = 2 * 1024 * 1024;
const RE_CONTA = /^[0-9a-f]{24}$/;
const RE_NOTA = /^[A-Za-z0-9_.-]{1,64}$/;
const UFS = "AC AL AP AM BA CE DF ES GO MA MT MS MG PA PB PR PE PI RJ RN RS RO RR SC SP SE TO".split(" ");
const CAMPOS_TOMADOR = ["nome", "documento", "email", "telefone", "logradouro", "numero", "complemento", "bairro", "cep", "cmun", "uf", "inscricao_municipal"];

export function ehRotaDaCasa(url) {
  return url.pathname.startsWith(PREFIXO);
}

export async function atenderCasa(request, env, url) {
  if (!env.NFSE_CASA_TOKEN) return json({ erro: "a ponte da NFS-e não está configurada (NFSE_CASA_TOKEN)" }, 503);
  if (!env.APOIOS) return json({ erro: "a ponte da NFS-e precisa do KV APOIOS" }, 503);
  const cab = request.headers.get("authorization") || "";
  const token = cab.startsWith("Bearer ") ? cab.slice(7).trim() : "";
  if (!(await iguais(token, env.NFSE_CASA_TOKEN))) return json({ erro: "não autorizado" }, 401);
  const agora = new Date().toISOString();
  await env.APOIOS.put("admin:nfse-casa:visto", agora);

  const p = url.pathname.slice(PREFIXO.length);
  const m = request.method;
  try {
    if (m === "GET" && p === "ping") {
      const contas = (await kvPor(env, "admin:conta:")).length;
      return json({ ok: true, hora: agora, contas });
    }
    if (m === "GET" && p === "clientes") {
      const contas = await contasDaCasa(env);
      const clientes = await Promise.all(contas.map((c) => cliente(env, c)));
      return json({ clientes });
    }
    let r = p.match(/^clientes\/([0-9a-f]{24})$/);
    if (r && m === "POST") return gravarTomador(request, env, r[1]);
    if (m === "GET" && p === "pagamentos") return json(await pagamentos(env));
    if (m === "POST" && p === "notas") return receberNota(request, env);
    r = p.match(/^notas\/([A-Za-z0-9_.-]{1,64})\/cancelada$/);
    if (r && m === "POST") return cancelarNota(request, env, r[1]);
    return json({ erro: "rota não existe" }, 404);
  } catch (e) {
    return json({ erro: String((e && e.message) || e).slice(0, 300) }, 500);
  }
}

// ------------------------------------------------------------ clientes

async function cliente(env, conta) {
  const d = conta._d || {};
  const cad = d.cadastro || {};
  const base = {
    nome: cad.nome_escritorio || conta.nome || "", documento: soDigitos(cad.documento), email: conta.email || "",
    telefone: soDigitos(cad.telefone), logradouro: "", numero: "", complemento: "", bairro: "", cep: "", cmun: "", uf: "", inscricao_municipal: "",
  };
  const ajuste = (await kvJSON(env, "nfse:tomador:" + conta.id)) || {};
  const tomador = { ...base };
  for (const k of CAMPOS_TOMADOR) if (ajuste[k] !== undefined && ajuste[k] !== "") tomador[k] = ajuste[k];
  const plano = conta.plano ? { id: conta.plano.id, nome: conta.plano.nome, valor: conta.plano.valor } : null;
  return {
    id: conta.id, nome: conta.nome, email: conta.email, telefone: soDigitos(cad.telefone), oab: conta.oab || "",
    plano, situacao: conta.situacao, tomador, ajustado: Object.keys(ajuste).length > 0,
  };
}

/* O tomador conferido, ou {erro}. So os campos enviados entram; "" apaga o
   ajuste daquele campo (volta o do cadastro). */
export function conferirTomador(t) {
  if (!t || typeof t !== "object") return { erro: "mande o tomador" };
  const limpo = (v, max) => String(v == null ? "" : v).replace(/[\u0000-\u001f<>]/g, " ").replace(/\s+/g, " ").trim().slice(0, max);
  const saida = {};
  for (const k of CAMPOS_TOMADOR) {
    if (t[k] === undefined) continue;
    let v = limpo(t[k], k === "nome" ? 150 : k === "logradouro" ? 125 : 60);
    if (v === "") { saida[k] = ""; continue; }
    if (k === "documento") {
      v = soDigitos(v);
      if (!(v.length === 11 ? cpfValido(v) : cnpjValido(v))) return { erro: "o CPF ou CNPJ do tomador não confere" };
    } else if (k === "cep") {
      v = soDigitos(v);
      if (v.length !== 8) return { erro: "o CEP tem 8 dígitos" };
    } else if (k === "cmun") {
      v = soDigitos(v);
      if (v.length !== 7) return { erro: "o código do município (IBGE) tem 7 dígitos" };
    } else if (k === "uf") {
      v = v.toUpperCase();
      if (!UFS.includes(v)) return { erro: "a UF tem 2 letras (ex.: PA)" };
    } else if (k === "email") {
      if (!/^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(v) || v.length > 120) return { erro: "o e-mail do tomador não confere" };
    } else if (k === "telefone") {
      v = soDigitos(v);
      if (v.length < 10 || v.length > 13) return { erro: "o telefone precisa do DDD" };
    } else if (k === "nome") {
      if (v.length < 2) return { erro: "o nome do tomador é curto demais" };
    }
    saida[k] = v;
  }
  return { tomador: saida };
}

async function gravarTomador(request, env, id) {
  const d = await lerJSON(request);
  if (!d) return json({ erro: "pedido inválido" }, 400);
  const c = conferirTomador(d.tomador);
  if (c.erro) return json({ erro: c.erro }, 400);
  const conta = (await contasDaCasa(env)).find((x) => x.id === id);
  if (!conta) return json({ erro: "essa conta não existe" }, 404);
  const antes = (await kvJSON(env, "nfse:tomador:" + id)) || {};
  const novo = { ...antes, ...c.tomador };
  for (const k of Object.keys(novo)) if (novo[k] === "") delete novo[k];
  if (Object.keys(novo).length) await env.APOIOS.put("nfse:tomador:" + id, JSON.stringify(novo));
  else await env.APOIOS.delete("nfse:tomador:" + id);
  return json(await cliente(env, conta));
}

// ------------------------------------------------------------ pagamentos

async function pagamentos(env) {
  const contas = await contasDaCasa(env);
  const porId = new Map(contas.map((x) => [x.id, x]));
  const lista = [];
  for (const k of await kvPor(env, "admin:nfse:")) {
    if (k === "admin:nfse:config") continue;
    const x = await kvJSON(env, k);
    if (!x) continue;
    const conta = porId.get(x.conta);
    lista.push({ id: x.id, conta: x.conta || "", cliente: conta ? conta.nome : "", tipo: x.tipo, valor: x.valor, quando: x.quando, nota: x.nota || "pendente", numero: x.numero || "" });
  }
  lista.sort((a, b) => String(b.quando).localeCompare(String(a.quando)));
  const config = { auto: false, email: false, ...((await kvJSON(env, "admin:nfse:config")) || {}) };
  return { pagamentos: lista, config };
}

// ------------------------------------------------------------ notas

function bytesDoBase64(b64) {
  const s = String(b64 || "").replace(/\s+/g, "");
  if (!s) return { tamanho: 0, b64: "" };
  if (!/^[A-Za-z0-9+/]*={0,2}$/.test(s)) return { erro: true };
  const tamanho = Math.floor((s.length * 3) / 4) - (s.endsWith("==") ? 2 : s.endsWith("=") ? 1 : 0);
  return { tamanho, b64: s };
}

async function receberNota(request, env) {
  const d = await lerJSON(request);
  if (!d) return json({ erro: "pedido inválido" }, 400);
  const id = String(d.id || "");
  const conta = String(d.conta || "");
  if (!RE_NOTA.test(id)) return json({ erro: "o id da nota vai com letras, números, ponto, _ ou - (até 64)" }, 400);
  if (!RE_CONTA.test(conta)) return json({ erro: "conta inválida" }, 400);
  if (!(await env.APOIOS.get("admin:conta:" + conta))) return json({ erro: "essa conta não existe" }, 404);
  const competencia = String(d.competencia || "");
  if (!/^\d{4}-(0[1-9]|1[0-2])$/.test(competencia)) return json({ erro: "a competência vai como AAAA-MM" }, 400);
  const valor = Number(d.valor);
  if (!Number.isFinite(valor) || valor < 0) return json({ erro: "o valor é um número em reais" }, 400);
  const ambiente = d.ambiente === "producao_restrita" ? "producao_restrita" : d.ambiente === "producao" ? "producao" : "";
  if (!ambiente) return json({ erro: "o ambiente é producao ou producao_restrita" }, 400);
  const pdf = bytesDoBase64(d.pdf_b64);
  const xml = bytesDoBase64(d.xml_b64);
  if (pdf.erro || xml.erro) return json({ erro: "o PDF e o XML vão em base64" }, 400);
  if (pdf.tamanho > MAX_ARQUIVO || xml.tamanho > MAX_ARQUIVO) return json({ erro: "cada arquivo pode ter até 2 MB" }, 413);
  const pagamento = d.pagamento ? String(d.pagamento).slice(0, 80) : "";
  const limpo = (v, max) => String(v == null ? "" : v).replace(/[\u0000-\u0009\u000b-\u001f]/g, " ").trim().slice(0, max);
  const meta = {
    id, conta, pagamento, numero: limpo(d.numero, 30), chave: limpo(d.chave, 60), competencia, valor: Math.round(valor * 100) / 100,
    descricao: limpo(d.descricao, 2000), ambiente, emitida_em: limpo(d.emitida_em, 40) || new Date().toISOString(),
    tem_pdf: Boolean(pdf.b64), tem_xml: Boolean(xml.b64), cancelada: false, recebida: new Date().toISOString(),
  };
  const base = conta + ":" + id;
  if (pdf.b64) await env.APOIOS.put("nfse:nota-pdf:" + base, pdf.b64);
  else await env.APOIOS.delete("nfse:nota-pdf:" + base);
  if (xml.b64) await env.APOIOS.put("nfse:nota-xml:" + base, xml.b64);
  else await env.APOIOS.delete("nfse:nota-xml:" + base);
  await env.APOIOS.put("nfse:nota:" + base, JSON.stringify(meta));
  if (pagamento) await marcarPagamento(env, pagamento, { nota: "emitida", numero: meta.numero, nota_id: id, erro: "" });
  return json({ ok: true });
}

async function marcarPagamento(env, pagamento, campos) {
  const chave = "admin:nfse:" + pagamento;
  const x = await kvJSON(env, chave);
  if (!x) return;
  await env.APOIOS.put(chave, JSON.stringify({ ...x, ...campos }));
}

async function cancelarNota(request, env, id) {
  const d = (await lerJSON(request)) || {};
  const conta = String(d.conta || "");
  if (!RE_CONTA.test(conta)) return json({ erro: "conta inválida" }, 400);
  const chave = "nfse:nota:" + conta + ":" + id;
  const meta = await kvJSON(env, chave);
  if (!meta) return json({ erro: "essa nota não existe" }, 404);
  meta.cancelada = true;
  meta.cancelada_em = new Date().toISOString();
  await env.APOIOS.put(chave, JSON.stringify(meta));
  if (meta.pagamento) await marcarPagamento(env, meta.pagamento, { nota: "cancelada" });
  return json({ ok: true });
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

function soDigitos(t) {
  return String(t || "").replace(/\D/g, "");
}

/* Compara o token em tempo constante: os dois passam pelo SHA-256 (mesmo
   tamanho) e a diferenca e somada byte a byte, sem sair no primeiro. */
async function iguais(a, b) {
  const enc = new TextEncoder();
  const [ha, hb] = await Promise.all([crypto.subtle.digest("SHA-256", enc.encode(String(a))), crypto.subtle.digest("SHA-256", enc.encode(String(b)))]);
  const x = new Uint8Array(ha);
  const y = new Uint8Array(hb);
  let dif = 0;
  for (let i = 0; i < x.length; i++) dif |= x[i] ^ y[i];
  return dif === 0 && String(a).length > 0;
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
