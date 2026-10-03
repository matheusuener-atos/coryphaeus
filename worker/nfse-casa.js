// A ponte da NFS-e (contrato em worker/admin-api.md, "Ponte da NFS-e").
//
// Quem emite as NFS-e dos assinantes e o PAULUS da casa (a tela "Notas do
// PAVLVS", no servidor do dono). Ele fala com o Worker por /api/nfse-casa/*:
// le os clientes (o tomador de cada um) e os pagamentos, e devolve cada nota
// emitida (meta, PDF e XML). O PAULUS de cada cliente busca as proprias notas
// em /api/ia/nfse (worker/ia.js, notasDoCliente, com o segredo da instalacao).
//
// Estas rotas ficam FORA do Cloudflare Access (que protege so /admin e
// /api/admin) e fora da sessao do GitHub. Nao ha chave propria: a casa manda
// em Authorization: Bearer o segredo da instalacao (pia_<conta>_..., o mesmo
// de /api/ia/*), e o e-mail dessa conta precisa estar na equipe do painel
// (ADMIN_EQUIPE ou "admin:equipe" no KV) como dono ou financeiro.
// Nuvem desligada, 503; segredo ausente ou invalido, 401; fora da equipe, 403.
//
// No KV APOIOS:
//   nfse:tomador:<conta>          o que a casa corrigiu do tomador (vence o cadastro)
//   nfse:nota:<conta>:<id>        a meta da nota
//   nfse:nota-pdf:<conta>:<id>    o PDF (base64)
//   nfse:nota-xml:<conta>:<id>    o XML (base64)
//   admin:nfse-casa:visto         a ultima chamada valida: {quando, email}
//   admin:nfse:<pagamento>        a fila do painel; a nota emitida a marca

//
// Com `email: true` (POST notas e notas/:id/cancelada), a nota tambem vai por
// e-mail pelo Resend (RESEND_API_KEY), ao e-mail do tomador corrigido pela casa
// ou, sem ele, ao e-mail da conta. Falha no e-mail nao falha a nota.

import { contasDaCasa, enviarEmail, listaDaEquipe } from "./admin.js";
import { autenticar, cpfValido, cnpjValido } from "./ia.js";

const PREFIXO = "/api/nfse-casa/";
const MAX_ARQUIVO = 2 * 1024 * 1024;
const RE_CONTA = /^[0-9a-f]{24}$/;
const RE_NOTA = /^[A-Za-z0-9_.-]{1,64}$/;
const UFS = "AC AL AP AM BA CE DF ES GO MA MT MS MG PA PB PR PE PI RJ RN RS RO RR SC SP SE TO".split(" ");
const PAPEIS_DA_CASA = ["dono", "financeiro"];
const CAMPOS_TOMADOR =["nome", "documento", "email", "telefone", "logradouro", "numero", "complemento", "bairro", "cep", "cmun", "uf", "inscricao_municipal"];

export function ehRotaDaCasa(url) {
  return url.pathname.startsWith(PREFIXO);
}

/* Quem esta na porta: a conta do segredo, se o e-mail dela e da equipe do
   painel como dono ou financeiro. Devolve {email, papel} ou {erro, status}. */
async function porteiro(request, env) {
  if (env.IA_ATIVA !== "1" || !env.CONTAS_IA) return { erro: "a ponte da NFS-e precisa da nuvem do PAULUS ligada (IA_ATIVA e CONTAS_IA)", status: 503 };
  if (!env.APOIOS) return { erro: "a ponte da NFS-e precisa do KV APOIOS", status: 503 };
  const quem = await autenticar(request, env);
  if (quem.erro) return { erro: "não autorizado", status: 401 };
  const resumo = (await quem.conta.pedir("resumo")) || {};
  const email = normalEmail(resumo.email);
  const membro = email ? (await listaDaEquipe(env)).find((x) => normalEmail(x && x.email) === email) : null;
  if (!membro || !PAPEIS_DA_CASA.includes(membro.papel)) {
    return { erro: "esta conta do PAULUS não é da equipe do painel (dono ou financeiro)", motivo: "fora_da_equipe", status: 403 };
  }
  return { email, papel: membro.papel };
}

export async function atenderCasa(request, env, url) {
  const quem = await porteiro(request, env);
  if (quem.erro) {
    const corpo = { erro: quem.erro };
    if (quem.motivo) corpo.motivo = quem.motivo;
    return json(corpo, quem.status);
  }
  const agora = new Date().toISOString();
  await env.APOIOS.put("admin:nfse-casa:visto", JSON.stringify({ quando: agora, email: quem.email }));

  const p = url.pathname.slice(PREFIXO.length);
  const m = request.method;
  try {
    if (m === "GET" && p === "ping") {
      const contas = (await kvPor(env, "admin:conta:")).length;
      return json({ ok: true, hora: agora, contas, email: quem.email, papel: quem.papel });
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
  // O endereco que o cliente deu em /cadastro (contas antigas nao tem).
  const end = cad.endereco || {};
  const base = {
    nome: cad.nome_escritorio || conta.nome || "", documento: soDigitos(cad.documento), email: conta.email || "",
    telefone: soDigitos(cad.telefone), logradouro: end.logradouro || "", numero: end.numero || "", complemento: end.complemento || "",
    bairro: end.bairro || "", cep: soDigitos(end.cep), cmun: soDigitos(end.cmun), uf: end.uf || "", inscricao_municipal: "",
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
  const config = { auto: false, email: false, mail: false, ...((await kvJSON(env, "admin:nfse:config")) || {}) };
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
  if (d.email !== true) return json({ ok: true });
  const anexos = [];
  const arquivo = "NFS-e " + (meta.numero || id).replace(/[^A-Za-z0-9_.-]/g, "");
  if (pdf.b64) anexos.push({ nome: arquivo + ".pdf", b64: pdf.b64 });
  if (xml.b64) anexos.push({ nome: arquivo + ".xml", b64: xml.b64 });
  const linhas = [
    "Segue a NFS-e da sua assinatura do PAVLVS, com o PDF e o XML anexos.",
    "Número: " + (meta.numero || "—") + "\nValor: " + brl(meta.valor) + "\nCompetência: " + mesAno(competencia),
  ];
  if (ambiente === "producao_restrita") linhas.push("Esta nota foi emitida no ambiente de testes, sem valor fiscal.");
  const email = await mandarEmail(env, conta, {
    assunto: "Sua NFS-e de " + mesAno(competencia) + " — PAVLVS", titulo: "Sua NFS-e de " + mesAno(competencia), texto: linhas.join("\n\n"), anexos,
  });
  return json({ ok: true, email });
}

const MESES = ["janeiro", "fevereiro", "março", "abril", "maio", "junho", "julho", "agosto", "setembro", "outubro", "novembro", "dezembro"];
function mesAno(competencia) {
  const [a, m] = String(competencia || "").split("-");
  return MESES[Number(m) - 1] ? MESES[Number(m) - 1] + "/" + a : String(competencia || "");
}
function brl(v) {
  return "R$ " + Number(v || 0).toFixed(2).replace(".", ",").replace(/\B(?=(\d{3})+(?!\d))/g, ".");
}

/* Manda o e-mail da nota ao e-mail do tomador (o ajuste da casa) ou, sem ele,
   ao da conta. Devolve "enviado" | "sem RESEND_API_KEY" | "sem e-mail do
   cliente" | "falhou: <motivo>"; nunca lanca. */
async function mandarEmail(env, contaId, { assunto, titulo, texto, anexos }) {
  if (!env.RESEND_API_KEY) return "sem RESEND_API_KEY";
  try {
    const ajuste = (await kvJSON(env, "nfse:tomador:" + contaId)) || {};
    let para = ajuste.email || "";
    if (!para) {
      const conta = (await contasDaCasa(env)).find((x) => x.id === contaId);
      para = (conta && conta.email) || "";
    }
    if (!para) return "sem e-mail do cliente";
    const r = await enviarEmail(env, { para, assunto, titulo, texto, anexos });
    return r.ok ? "enviado" : "falhou: " + (r.erro || "o provedor de e-mail recusou");
  } catch (e) {
    return "falhou: " + String((e && e.message) || e).slice(0, 200);
  }
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
  const substituta = d.substituta && typeof d.substituta === "object" ? String(d.substituta.numero || "").replace(/[\u0000-\u001f<>]/g, "").trim().slice(0, 30) : "";
  if (substituta) {
    meta.substituta = substituta;
    await env.APOIOS.put(chave, JSON.stringify(meta));
  }
  if (d.email !== true) return json({ ok: true });
  const linhas = [
    "A NFS-e nº " + (meta.numero || id) + " (" + mesAno(meta.competencia) + ", " + brl(meta.valor) + ") da sua assinatura do PAVLVS foi cancelada.",
  ];
  if (substituta) linhas.push("Ela foi substituída pela nota nº " + substituta + ", que você recebe à parte.");
  if (meta.ambiente === "producao_restrita") linhas.push("Esta nota era do ambiente de testes, sem valor fiscal.");
  const email = await mandarEmail(env, conta, {
    assunto: "NFS-e nº " + (meta.numero || id) + " cancelada — PAVLVS", titulo: "NFS-e cancelada", texto: linhas.join("\n\n"),
  });
  return json({ ok: true, email });
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

function normalEmail(e) {
  return String(e || "").replace(/\s+/g, "").toLowerCase();
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
