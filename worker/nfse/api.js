// A API interna do emissor da nuvem. AINDA NÃO LIGADA a worker/index.js nem
// ao painel: quem ligar põe na frente a autenticação (Access/sessão do painel,
// papel dono ou financeiro). atenderEmissor NÃO autentica nada sozinho.
//
// Rotas (relativas ao prefixo, por padrão /api/nfse-emissor/):
//   GET  situacao                       configuração, certificado, município, pode_emitir
//   POST prestador {prestador}          grava uma versão nova da configuração
//   POST certificado {certificado, chave, titular, documento, algoritmo?}
//                                       PEM (ou base64 do DER) e PKCS#8 já abertos
//   POST testar                         consulta o convênio do município na Sefin
//   POST notas {conta?, pagamento?, tomador, valor | valor_centavos, descricao, competencia}
//   GET  notas?estado=&limite=          a lista
//   GET  notas/:id                      a nota, os passos e os eventos
//   GET  notas/:id/xml?tipo=nfse|dps    o XML (application/xml)
//   POST notas/:id/tentar               de novo (consulta antes de reenviar)
//   POST notas/:id/descartar            rejeitada: devolve o número
//   POST notas/:id/cancelar {motivo, texto}
//   POST notas/:id/substituir {motivo, texto, ajustes: {tomador?, valor?, descricao?, competencia?}}
//   POST notas/:id/situacao             consulta os eventos da nota (cancelada por ofício...)
//   POST notas/:id/depois               PDF + e-mail em segundo plano (ctx.waitUntil), 202
//   POST fila                           processa a fila agora (o alarme do DO faz sozinho)
//   POST producao/liberar  /  POST producao/voltar
//
// O PDF e o e-mail ficam FORA do pedido que emite: o DANFSe (pdf-lib) custa
// CPU que, somada à da emissão, passaria dos 10 ms do plano grátis. Quem
// emite chama depois, num pedido separado, POST notas/:id/depois (a tela
// faz isso ao receber a nota emitida), que roda depoisDeEmitir em
// ctx.waitUntil e responde na hora.

import { b64 } from "./assinatura.js";
import { danfseEsqueleto } from "./danfse.js";
import { idNoCliente } from "./emissor.js";
import { reais } from "./dinheiro.js";
import { mandarNotaPorEmail } from "../nfse-casa.js";

export const PREFIXO = "/api/nfse-emissor/";

export function emissorDe(env) {
  if (!env.EMISSOR_NFSE) throw new Error("falta o Durable Object EMISSOR_NFSE");
  return env.EMISSOR_NFSE.get(env.EMISSOR_NFSE.idFromName("pavlvs"));
}

/** Chama uma ação do DO: {status, dados}. */
export async function chamar(env, acao, dados = {}) {
  const r = await emissorDe(env).fetch("https://emissor-nfse/" + acao, {
    method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify({ acao, dados }),
  });
  return { status: r.status, dados: await r.json() };
}

function json(dados, status = 200) {
  return new Response(JSON.stringify(dados), { status, headers: { "content-type": "application/json; charset=utf-8", "cache-control": "no-store" } });
}

/**
 * request: o pedido HTTP; opcoes.quem: quem está pedindo (vem da
 * autenticação de quem ligar a rota); opcoes.prefixo.
 */
export async function atenderEmissor(request, env, ctx, { quem = "PAVLVS", prefixo = PREFIXO } = {}) {
  const url = new URL(request.url);
  if (!url.pathname.startsWith(prefixo)) return json({ erro: "rota não existe" }, 404);
  const p = url.pathname.slice(prefixo.length).replace(/\/+$/, "");
  const m = request.method;
  let corpo = {};
  if (m === "POST") {
    try {
      const t = await request.text();
      corpo = t ? JSON.parse(t) : {};
    } catch {
      return json({ erro: "pedido inválido" }, 400);
    }
    if (!corpo || typeof corpo !== "object" || Array.isArray(corpo)) return json({ erro: "pedido inválido" }, 400);
  }
  const via = async (acao, dados) => {
    const r = await chamar(env, acao, dados);
    return json(r.dados, r.status);
  };
  try {
    if (m === "GET" && p === "situacao") return via("situacao", {});
    if (m === "POST" && p === "prestador") return via("configurar", { prestador: corpo.prestador, quem, motivo: corpo.motivo || "" });
    if (m === "POST" && p === "certificado") {
      return via("certificado", { certificado: corpo.certificado, chave: corpo.chave, titular: corpo.titular, documento: corpo.documento,
        algoritmo: corpo.algoritmo || "sha1", quem });
    }
    if (m === "POST" && p === "testar") return via("testar", {});
    if (m === "POST" && p === "notas") return via("emitir", { ...corpo, quem });
    if (m === "GET" && p === "notas") return via("listar", { estado: url.searchParams.get("estado") || "", limite: url.searchParams.get("limite") || 300 });
    if (m === "POST" && p === "fila") return via("fila", { quem });
    if (m === "POST" && p === "producao/liberar") return via("liberar_producao", { quem });
    if (m === "POST" && p === "producao/voltar") return via("voltar_testes", { quem });
    const r = p.match(/^notas\/(\d{1,12})(?:\/([a-z]+))?$/);
    if (r) {
      const id = Number(r[1]);
      const sub = r[2] || "";
      if (m === "GET" && !sub) return via("nota", { id });
      if (m === "GET" && sub === "xml") {
        const x = await chamar(env, "xml", { id, tipo: url.searchParams.get("tipo") === "dps" ? "dps" : "nfse" });
        if (x.status !== 200) return json(x.dados, x.status);
        return new Response(x.dados.xml, { headers: { "content-type": "application/xml; charset=utf-8",
          "content-disposition": `attachment; filename="${x.dados.nome.replace(/[^A-Za-z0-9 ._-]/g, "")}"` } });
      }
      if (m === "POST" && sub === "tentar") return via("tentar", { id, quem });
      if (m === "POST" && sub === "descartar") return via("descartar", { id, quem });
      if (m === "POST" && sub === "cancelar") return via("cancelar", { id, motivo: corpo.motivo, texto: corpo.texto, quem });
      if (m === "POST" && sub === "substituir") return via("substituir", { id, motivo: corpo.motivo, texto: corpo.texto, ajustes: corpo.ajustes || {}, quem });
      if (m === "POST" && sub === "situacao") return via("atualizar_situacao", { id, quem });
      if (m === "POST" && sub === "depois") {
        const trabalho = depoisDeEmitir(env, id);
        if (ctx && ctx.waitUntil) ctx.waitUntil(trabalho.catch(() => {}));
        else await trabalho;
        return json({ ok: true, agendado: true }, 202);
      }
    }
    return json({ erro: "rota não existe" }, 404);
  } catch (e) {
    return json({ erro: String((e && e.message) || e).slice(0, 300) }, 500);
  }
}

/**
 * Depois de emitida, num pedido SEPARADO: o DANFSe (esqueleto, pdf-lib) vai
 * para nfse:nota-pdf:<conta>:nuvem-<id> (a meta passa a dizer tem_pdf) e, com
 * "mandar também por e-mail" ligado no painel (admin:nfse:config.mail), o
 * e-mail com PDF e XML vai ao cliente. Marca na nota (pdf_em, email).
 * Devolve {ok, pdf_bytes, email}. Chamável por ctx.waitUntil.
 */
export async function depoisDeEmitir(env, id) {
  const r = await chamar(env, "para_pdf", { id });
  if (r.status !== 200) return { ok: false, erro: r.dados.erro };
  const { nota, xml_nfse: xml, prestador, calculo } = r.dados;
  if (nota.estado !== "emitida") return { ok: false, erro: "a nota não está emitida" };
  const t = nota.tomador || {};
  const c = calculo || {};
  const v = nota.sefin || {};
  const pdf = await danfseEsqueleto({
    chave: nota.chave, numero: nota.numero, emissao: String(nota.quando || "").slice(0, 10).split("-").reverse().join("/"),
    producaoRestrita: nota.ambiente === "producao_restrita", prestador,
    tomador: { nome: t.nome, documento: t.documento, email: t.email,
      endereco: [t.logradouro, t.numero, t.complemento, t.bairro, t.cep, t.uf].filter(Boolean).join(", ") },
    descricao: nota.descricao,
    valores: { servico: reais(nota.centavos), desconto: reais(c.v_desc_incond || 0), iss: reais(v.v_issqn ?? c.iss ?? 0),
      retencoes: reais(v.v_total_ret ?? c.v_total_ret ?? 0), liquido: reais(v.v_liq || c.v_liq || 0) },
  });
  const pdfB64 = b64(pdf);
  let email = "";
  if (nota.conta && env.APOIOS) {
    const base = nota.conta + ":" + idNoCliente(nota.id);
    const metaTexto = await env.APOIOS.get("nfse:nota:" + base);
    if (metaTexto) {
      await env.APOIOS.put("nfse:nota-pdf:" + base, pdfB64);
      const meta = { ...JSON.parse(metaTexto), tem_pdf: true };
      await env.APOIOS.put("nfse:nota:" + base, JSON.stringify(meta));
      let cfg = {};
      try {
        cfg = JSON.parse((await env.APOIOS.get("admin:nfse:config")) || "{}") || {};
      } catch {
        cfg = {};
      }
      if (cfg.mail) email = await mandarNotaPorEmail(env, meta, pdfB64, b64(new TextEncoder().encode(xml)));
    } else email = "a nota não está no app do cliente";
  }
  await chamar(env, "marcar_depois", { id, pdf_em: new Date().toISOString(), email });
  return { ok: true, pdf_bytes: pdf.length, email };
}
