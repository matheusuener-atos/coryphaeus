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
// DeepInfra. Nada e guardado: o medidor anota so numeros (tokens, datas). O
// registro do que saiu fica no computador do escritorio.
//
// A cobranca e da Atos (atos.dev.br; worker/atos.js): o plano chega pelos avisos dela, e o medidor so reconhece
// o que a Atos diz que foi pago, ou a cortesia. As rotas de dinheiro de antes (o Mercado Pago proprio do PAVLVS)
// respondem 409 com o caminho na Atos: sao os PAULUS instalados de antes que ainda as chamam.
//
//   POST /api/ia/ativar            com o id_token do Google: a conta (uma por
//                                  conta Google) e o segredo desta instalacao
//   GET  /api/ia/conta             plano, ciclo, tokens usados e restantes
//   POST /api/ia/consentimento     o sim do titular (versao do termo), ou o nao
//   GET  /api/ia/modelos           os modelos que o portao aceita
//   POST /api/ia/v1/chat/completions  o formato OpenAI; vai ao DeepInfra
//   POST /api/ia/assinar           o link do checkout da Atos (quem cobra e a Atos: worker/atos.js)
//   GET  /api/ia/assinatura        a situacao (o mesmo resumo da conta)
//   POST /api/ia/site/entrar|situacao  a conta pelo id_token, sem segredo de instalacao (o assistente)
//   POST /api/ia/site/cadastro     os dados do escritorio
//   POST /api/ia/sair              apaga o segredo desta instalacao
//   GET  /api/ia/nfse              as NFS-e emitidas para a conta (pela casa)
//   GET  /api/ia/nfse/:id/pdf|xml  o arquivo de uma delas
//   POST /api/ia/google            o que o PAULUS do escritorio usa do Google (so
//                                  os nomes curtos dos escopos) e a ordem que ele
//                                  cumpriu; volta a ordem que falta cumprir
//   GET  /api/ia/cadastro          o cadastro do site desta conta (escritorio,
//                                  documento, OAB, telefone, endereco), para o
//                                  assistente de configuracao mostrar
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
import { checkoutDaAtos, conferirNaAtos, NA_ATOS, vendaPelaAtos } from "./atos.js";

const RE_SEGREDO = /^pia_([0-9a-f]{24})_([0-9a-f]{64})$/;
const MAX_SEGREDOS = 3;
// Os servicos do Google que a Minha conta e o painel ligam e desligam, pelo
// nome curto do escopo (worker/conta.js SERVICOS_G; o PAULUS usa os mesmos):
// e so isso que o PAULUS conta da conta Google dele - nada de e-mail ou token.
export const ESCOPOS_GOOGLE = ["mail.google.com", "calendar.events", "drive.file", "drive.readonly"];
// Reserva sem liquidar (o Worker caiu no meio): depois disto, conta inteira.
const RESERVA_VENCE_MS = 15 * 60 * 1000;
// Depois do fim do ciclo, com a assinatura ativa, a cobranca do mes pode
// atrasar uns dias no Mercado Pago: o plano continua valendo nesse intervalo.
export const TOLERANCIA_MS = 5 * 24 * 3600 * 1000;
// A conta fora de dia pergunta a Atos (o evento que se perdeu) no maximo a cada 10 minutos (worker/atos.js).
const ATOS_RESERVA_MS = 10 * 60 * 1000;
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

// As rotas de dinheiro de antes da Atos: os PAULUS instalados de antes ainda as chamam. Respondem 409 com o
// caminho na Atos (o checkout ou a Conta Atos), e a tela deles mostra a frase.
const ROTAS_ANTIGAS = new Set(["/api/ia/desistir", "/api/ia/plano", "/api/ia/assinatura/cancelar", "/api/ia/recarga"]);
const ROTAS_ANTIGAS_DO_SITE = new Set(["/api/ia/site/plano", "/api/ia/site/oferta", "/api/ia/site/pagar", "/api/ia/site/pagar-fora", "/api/ia/site/desistir", "/api/ia/site/pix"]);

/* A resposta de uma rota de dinheiro de antes: assinar e comprar e no checkout da Atos; cancelar, desistir e o
   resto, na Conta Atos. */
function pelaAtos(resumo, plano, periodo) {
  return resumo && resumo.cobrador === "atos" ? NA_ATOS : vendaPelaAtos(plano || (resumo && resumo.plano || {}).id, periodo);
}

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
  if (p === "/api/ia/planos" && m === "GET") {
    const n = numeros(env);
    return json({ planos: n.planos.map((x) => ({ ...x, modelos_info: catalogo(modelosDoPlano(x)), recargas: recargasDe(x) })),
      recarga: { valor: n.recargaValor, tokens: n.recargaTokens }, recargas: n.recargas, niveis: NIVEIS });
  }
  // A conta pelo id_token da Conta Atos, sem segredo de instalacao: o assistente do PAULUS (rotas_boas_vindas)
  // pergunta a situacao antes de ativar.
  if (p.startsWith("/api/ia/site/") && m === "POST") {
    if (await limitado()) return json({ erro: "muitas tentativas seguidas - espere um minuto" }, 429);
    return atenderSite(request, env, p, deps);
  }
  const quem = await autenticar(request, env);
  if (quem.erro) return json({ erro: quem.erro }, quem.status);
  const conta = quem.conta;
  if (p === "/api/ia/conta" && m === "GET") {
    let r = await conta.pedir("resumo");
    // Fora de dia: o pagamento pode estar na Atos, com o evento perdido (worker/atos.js).
    if (!r.plano_vigente && (await conferirNaAtos(env, conta, deps))) r = await conta.pedir("resumo");
    return json(r);
  }
  if ((m === "POST" && ROTAS_ANTIGAS.has(p)) || (m === "GET" && /^\/api\/ia\/recarga\/[A-Za-z0-9_-]{6,64}$/.test(p))) {
    return json(pelaAtos(await conta.pedir("resumo")), 409);
  }
  // Os modelos do plano desta conta (o padrao primeiro), com nome e empresa.
  if (p === "/api/ia/modelos" && m === "GET") {
    const r = await conta.pedir("resumo");
    const ids = modelosDoPlano(r.plano);
    return json({ modelos: ids, info: catalogo(ids) });
  }
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
  if (p === "/api/ia/google" && m === "POST") return relatarGoogle(request, conta);
  // O cadastro e da conta dona deste segredo, e so dela: sem o segredo dela, nao se chega aqui.
  if (p === "/api/ia/cadastro" && m === "GET") return json(cadastroDaConta(await conta.pedir("ler_cadastro")));
  // O link que abre a Minha conta ja com a sessao (o "edite no site" e o "Fazer upgrade" do Paulus):
  // vale uma vez, por 2 minutos; quem o pede e a instalacao da conta, e a sessao e a do titular dela.
  if (p === "/api/ia/minha-conta/link" && m === "POST") {
    if (await limitado()) return json({ erro: "muitas tentativas seguidas - espere um minuto" }, 429);
    const d = (await lerJSON(request)) || {};
    const aba = ["cadastro", "plano", "resumo", "pagamento", "escritorio"].includes(d.aba) ? d.aba : "resumo";
    const r = await conta.pedir("minha_conta");
    const dono = r && r.dono;
    if (!dono || !dono.email) return json({ erro: "esta conta ainda não tem dono na nuvem" }, 409);
    const codigo = aleatorio(32);
    await env.APOIOS.put("conta:link:" + (await sha256(codigo)), JSON.stringify({ conta: quem.id, papel: "titular", email: dono.email, sub: dono.sub || "", nome: r.nome || "" }), { expirationTtl: 120 });
    return json({ url: "https://paulus.ia.br/minha-conta/?entrar=" + codigo + "#" + aba });
  }
  // O "Fazer upgrade" do PAULUS: o link do checkout da Atos, no plano e no periodo pedidos (ou nos da conta).
  if (p === "/api/ia/assinar" && m === "POST") {
    if (await limitado()) return json({ erro: "muitas tentativas seguidas - espere um minuto" }, 429);
    const d = (await lerJSON(request)) || {};
    const r = await conta.pedir("resumo");
    const plano = planoDe(numeros(env), String(d.plano || "") || (r.plano || {}).id);
    const periodo = d.periodo === "anual" ? "anual" : "mensal";
    return json({ link: checkoutDaAtos(plano.id, periodo), plano, periodo });
  }
  if (p === "/api/ia/assinatura" && m === "GET") return json(await conta.pedir("resumo"));
  // As NFS-e que o PAVLVS emitiu para esta conta (o emissor da nuvem grava por worker/nfse-casa.js).
  if (p === "/api/ia/nfse" && m === "GET") return json({ notas: await notasDoCliente(env, quem.id) });
  const nf = p.match(/^\/api\/ia\/nfse\/([A-Za-z0-9_.-]{1,64})\/(pdf|xml)$/);
  if (nf && m === "GET") return arquivoDoCliente(env, quem.id, nf[1], nf[2]);
  return json({ erro: "rota não existe" }, 404);
}

// --------------------------------------------- o Google do escritorio
// A Minha conta (google_ordem) e o painel (admin_google) guardam a ordem em
// conta.google_pendente: que servicos do Google o PAULUS do escritorio
// continua usando. O PAULUS instalado conta aqui o que usa de fato e, quando
// cumpre a ordem, manda o id dela em `aplicado` - so entao ela sai da conta.
// O que ele faz com cada ordem e dele (paulus/legal/src/google_nuvem.py): o
// Google nao revoga um servico sozinho, entao desligar um e o PAULUS parar de
// usa-lo; so a lista vazia (desvincular) revoga a concessao no Google.

/* POST /api/ia/google {escopos: [nome curto], aplicado?: id} -> {ok, pendente: {id, ligados, quando, por} | null}. */
async function relatarGoogle(request, conta) {
  const d = (await lerJSON(request)) || {};
  const escopos = [...new Set((Array.isArray(d.escopos) ? d.escopos : []).map(String).filter((x) => ESCOPOS_GOOGLE.includes(x)))];
  const aplicado = /^[A-Za-z0-9_-]{1,40}$/.test(String(d.aplicado || "")) ? String(d.aplicado) : "";
  const r = await conta.pedir("google_relatar", { escopos, aplicado });
  if (r.ok === false) return json({ erro: r.erro || "não foi possível guardar agora" }, r.status || 400);
  const g = r.google_pendente;
  return json({ ok: true, pendente: g && g.id ? { id: g.id, ligados: g.ligados || [], quando: g.quando || "", por: g.por || "" } : null });
}

/* GET /api/ia/cadastro: o que a pagina de cadastro do site guardou desta conta
   (conferirCadastro), so os campos que o assistente de configuracao do PAULUS
   mostra em "Seus dados" - sem os termos aceitos nem o e-mail das faturas. */
export function cadastroDaConta(r) {
  const c = r && r.cadastro;
  return {
    ok: true,
    email: (r && r.email) || "",
    cadastro: c ? { nome_escritorio: c.nome_escritorio || "", documento: c.documento || "", oab: c.oab || "", telefone: c.telefone || "",
      endereco: c.endereco || null } : null,
  };
}

// --------------------------------------------- as NFS-e da conta
// Gravadas pela ponte da casa (worker/nfse-casa.js) em "nfse:nota:<conta>:<id>"
// e os arquivos em "nfse:nota-pdf:..." e "nfse:nota-xml:..." (base64).

/* As notas da conta, para GET /api/ia/nfse (sem os arquivos). Tambem a Minha conta (worker/conta.js). */
export async function notasDoCliente(env, conta) {
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
export async function arquivoDoCliente(env, conta, id, tipo) {
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
  // A versao do PAULUS que pede (X-PAULUS-Versao), para a lista de instalacoes da Minha conta.
  const v = String(request.headers.get("x-paulus-versao") || "");
  const r = await conta.pedir("conferir", { hash, versao: /^\d{1,3}(?:\.\d{1,3}){1,3}$/.test(v) ? v : "" });
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

// ------------------------------------------------------------- os periodos

// Os periodos pagos de uma vez (o ano, o mes no Pix): valem ate pago_ate e cada mes abre o seu ciclo. Vem do
// retrato da Atos (direitoDaAtos); a assinatura no cartao e o "mensal".
const PREPAGOS = ["anual", "avulso"];
export const prepago = (periodo) => PREPAGOS.includes(periodo);

/* A data em Brasilia, dd/mm/aaaa. */
function dataBR(iso) {
  const t = Date.parse(iso || "");
  if (!Number.isFinite(t)) return "";
  return new Date(t - 3 * 3600 * 1000).toISOString().slice(0, 10).split("-").reverse().join("/");
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
  let aberta = await conta.pedir("abrir", { id, dono, cortesia: cortesias.includes(await sha256(dono.email)) });
  if (p === "/api/ia/site/entrar" || p === "/api/ia/site/situacao") {
    if (!aberta.plano_vigente && (await conferirNaAtos(env, conta, deps))) aberta = await conta.pedir("ler_cadastro");
    return json(p === "/api/ia/site/entrar" ? aberta : await conta.pedir("ler_cadastro"));
  }
  if (ROTAS_ANTIGAS_DO_SITE.has(p)) return json(pelaAtos(aberta, String(d.plano || ""), d.periodo), 409);
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
    // Com o plano: o proximo passo e o checkout da Atos.
    return json({ ...salvo, proximo: checkoutDaAtos(String(d.plano), d.periodo) });
  }
  return json({ erro: "rota não existe" }, 404);
}

// ------------------------------------------------------------- o medidor

const SEMANA_MS = 7 * 24 * 3600 * 1000;
// Os primeiros 7 dias da assinatura sao o prazo de arrependimento (CDC, art.
// 49): neles a cota e so a da semana, sem adiantamento - quem desiste nao
// leva mais do que uma semana de IA.
const ARREPENDIMENTO_MS = 7 * 24 * 3600 * 1000;
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
      return [{ ok: false, erro: "esta conta Google foi desvinculada da nuvem do Paulus; fale com contato@paulus.ia.br", status: 403 }, null];
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
    if (acao === "atos_direito" || acao === "atos_credito") {
      // A cobranca pela Atos (worker/atos.js): quem pagou na Atos antes de abrir o PAVLVS ganha a conta aqui.
      const conta = c || { id: d.id, criada: new Date(agora).toISOString(), segredos: [], extra: 0, reservas: {}, recargas: [], cobrancas: [], uso: [] };
      if (!conta.dono && d.dono && d.dono.sub) conta.dono = { sub: String(d.dono.sub), email: String(d.dono.email || "") };
      this.limparReservas(conta, agora);
      return acao === "atos_direito" ? this.direitoDaAtos(conta, d, n, agora) : this.creditoDaAtos(conta, d, n, agora);
    }
    if (!c) return [{ ok: false, erro: "conta não existe", status: 401 }, null];
    const conta = c;
    this.limparReservas(conta, agora);
    if (acao === "conferir") {
      const s = (conta.segredos || []).find((x) => x.hash === d.hash);
      if (!s) return [{ ok: false }, null];
      // Quando esta instalacao falou com a nuvem pela ultima vez, e em que
      // versao (a lista de instalacoes da Minha conta): anotado no maximo de
      // hora em hora, para nao gravar a cada pergunta.
      const versao = String(d.versao || "").slice(0, 20);
      if (agora - (Date.parse(s.visto || "") || 0) > 3600 * 1000 || (versao && versao !== s.versao)) {
        s.visto = new Date(agora).toISOString();
        if (versao) s.versao = versao;
        return [{ ok: true }, conta];
      }
      return [{ ok: true }, null];
    }
    if (acao === "resumo") return [this.resumo(conta, n, agora), conta];
    if (acao === "atos_reserva") {
      const atos = conta.atos || {};
      const sub = (conta.dono || {}).sub || "";
      if (!sub || this.vigente(conta, n, agora) || agora - (Date.parse(atos.conferido || "") || 0) < ATOS_RESERVA_MS) return [{ ok: true, conferir: false }, null];
      conta.atos = { ...atos, conferido: new Date(agora).toISOString() };
      return [{ ok: true, conferir: true, sub }, conta];
    }
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
    if (acao === "adiantar") {
      const motivo = this.motivoParaNaoAdiantar(conta, n, agora);
      if (motivo) return [{ ok: false, status: 409, erro: motivo, conta: this.resumo(conta, n, agora) }, null];
      const c = conta.ciclo;
      c.adiantamento = { semana: this.semanaDe(c, agora), quando: new Date(agora).toISOString() };
      return [this.resumo(conta, n, agora), conta];
    }
    // O que o PAULUS instalado conta da conta Google dele (so o nome dos
    // servicos que usa: POST /api/ia/google) e a confirmacao de que cumpriu a
    // ordem da Minha conta ou do painel. So sai a ordem com o mesmo id: uma
    // nova, dada enquanto ele cumpria a anterior, continua esperando.
    if (acao === "google_relatar") {
      const escopos = (Array.isArray(d.escopos) ? d.escopos : []).map(String).filter((x) => /^[a-z.:\/_-]{2,60}$/i.test(x)).slice(0, 10);
      conta.google = escopos.length ? { escopos, conferido: new Date(agora).toISOString() } : null;
      if (d.aplicado && conta.google_pendente && conta.google_pendente.id === d.aplicado) delete conta.google_pendente;
      return [this.resumo(conta, n, agora), conta];
    }
    if (acao.startsWith("admin_")) return this.fazerAdmin(acao, conta, d, n, agora);
    return this.fazerConta(acao, conta, d, n, agora);
  }

  /* A Minha conta (worker/conta.js) e as ofertas: o que a conta guarda. O
     Mercado Pago e chamado antes, de fora (as funcoes exportadas abaixo de
     trocarPlano); aqui so a anotacao, sem I/O. */
  fazerConta(acao, conta, d, n, agora) {
    const iso = (t) => new Date(t).toISOString();
    if (acao === "minha_conta") return [this.minhaConta(conta, n, agora), conta];
    if (acao === "remover_instalacao") {
      const antes = (conta.segredos || []).length;
      conta.segredos = (conta.segredos || []).filter((s) => s.instalacao !== d.instalacao);
      if (conta.segredos.length === antes) return [{ ok: false, status: 404, erro: "esse computador não está na conta" }, null];
      return [this.resumo(conta, n, agora), conta];
    }
    if (acao === "pessoa_convidar") {
      const email = String(d.email || "").toLowerCase();
      const outras = (conta.pessoas || []).filter((p) => p.email !== email);
      if (outras.length >= 10) return [{ ok: false, status: 409, erro: "a Minha conta aceita até 10 pessoas além do titular" }, null];
      conta.pessoas = [...outras, { email, papel: "financeiro", convite: { hash: String(d.hash), ate: String(d.ate), quando: iso(agora) }, por: String(d.por || "").slice(0, 120) }];
      return [{ ok: true }, conta];
    }
    if (acao === "pessoa_aceitar") {
      const email = String(d.email || "").toLowerCase();
      const p = (conta.pessoas || []).find((x) => x.email === email && x.convite && x.convite.hash === d.hash);
      if (!p || !(Date.parse(p.convite.ate) > agora)) return [{ ok: false, status: 410, erro: "este convite venceu ou é de outra conta Google; peça outro ao titular" }, null];
      delete p.convite;
      p.aceito = iso(agora);
      p.nome = String(d.nome || "").replace(/[\u0000-\u001f<>]/g, "").slice(0, 80);
      return [{ ok: true, papel: p.papel }, conta];
    }
    if (acao === "pessoa_papel") {
      const p = (conta.pessoas || []).find((x) => x.email === String(d.email || "").toLowerCase() && x.aceito);
      return [{ ok: Boolean(p), papel: p ? p.papel : "" }, null];
    }
    if (acao === "pessoa_remover") {
      const email = String(d.email || "").toLowerCase();
      const antes = (conta.pessoas || []).length;
      conta.pessoas = (conta.pessoas || []).filter((p) => p.email !== email);
      if (conta.pessoas.length === antes) return [{ ok: false, status: 404, erro: "essa pessoa não está na conta" }, null];
      return [{ ok: true }, conta];
    }
    if (acao === "google_ordem") {
      // A mesma ordem do painel (admin_google): que servicos do Google o PAULUS do escritorio mantem ligados.
      conta.google_pendente = { id: "g" + agora, ligados: (d.ligados || []).map(String).slice(0, 10), quando: iso(agora), por: "Minha conta" };
      return [this.resumo(conta, n, agora), conta];
    }
    return [{ ok: false, erro: "ação desconhecida", status: 400 }, null];
  }

  /* O que a Minha conta mostra (worker/conta.js), alem do resumo. */
  minhaConta(conta, n, agora) {
    return {
      ...this.resumo(conta, n, agora),
      dono: conta.dono || null,
      criada: conta.criada || "",
      cadastro: conta.cadastro || null,
      uso: conta.uso || [],
      uso_mes: conta.uso_mes || {},
      ciclo_completo: conta.ciclo ? { ...conta.ciclo } : null,
      instalacoes_lista: (conta.segredos || []).map((s) => ({ instalacao: s.instalacao, criado: s.criado || "", visto: s.visto || "", versao: s.versao || "" })),
      google: conta.google || null,
      pessoas: (conta.pessoas || []).map((p) => ({ email: p.email, nome: p.nome || "", papel: p.papel, convite: Boolean(p.convite), aceito: p.aceito || "" })),
    };
  }

  /* "" se a conta pode receber a oferta para ficar (ao cancelar); senao, o porque. */

  /* A oferta de volta do painel, com um pagamento confirmado: os creditos
     entram agora; o preco especial ja foi usado na cobranca. Vencida, sai sem nada. */

  /* As cobrancas com valor proprio (o desconto para ficar, a diferenca da troca
     de plano, o preco especial da volta): a cobranca de `valor` acabou de ser
     paga. Se era a ajustada, passa para a seguinte e devolve o valor que a
     assinatura deve ter daqui em diante (0 quando nao muda); a ultima devolve
     o valor cheio, e o ajuste acaba. Cobranca de outro valor (a que ja estava
     marcada antes do ajuste) nao conta. */

  /* O retrato do direito que a Atos mandou (direito.atualizado; worker/atos.js). Aplica so versao maior que a
     que ja tem: o evento repetido, ou o que chegou fora de ordem, nao estraga nada. A primeira vez, a conta
     passa a ser cobrada pela Atos: o tempo que o PAVLVS ja tinha cobrado fica, e a assinatura mensal dele
     sai no Mercado Pago (quem chamou cancela, pela resposta). */
  direitoDaAtos(conta, d, n, agora) {
    const iso = (t) => new Date(t).toISOString();
    const r = d.retrato || {};
    const versao = Math.round(Number(r.versao) || 0);
    const atos = { ...(conta.atos || {}) };
    if (versao <= (atos.versao || 0)) {
      return [{ ...this.resumo(conta, n, agora), repetido: true }, null];
    }
    if (conta.cobrador !== "atos") {
      // A primeira vez: a conta passa a ser da Atos, e o que o caminho antigo tinha anotado sai.
      conta.cobrador = "atos";
      delete conta.ciclo;
      for (const k of ["plano_proximo", "anual_pendente", "ajuste", "forma", "cartao", "oferta_volta", "cancelamento"]) delete conta[k];
    }
    const fim = Date.parse(r.ate || "") || 0;
    Object.assign(atos, { versao, evento: String(d.evento || ""), recebido: iso(agora) });
    conta.atos = atos;
    if (r.plano && n.planos.some((x) => x.id === r.plano)) conta.plano = r.plano;
    // A assinatura que vale e a viva. A cancelada que a Atos ainda manda no retrato nao manda na situacao quando
    // o periodo pago veio de uma compra a parte (pago_por "compra": o ano, o mes no Pix): quem pagou o ano esta em
    // dia, nao "cancelado". Se o mes pago e o da propria assinatura cancelada, "cancelada" e o certo.
    const recebida = r.assinatura || null;
    const viva = recebida && ["authorized", "paused", "pending"].includes(recebida.status);
    const as = viva || !(fim > agora && r.pago_por === "compra") ? recebida : null;
    const situacao = as ? (as.status === "canceled" ? "cancelled" : String(as.status || "")) : fim > agora ? "authorized" : "expired";
    // Os nomes de periodo que as telas ja conhecem: a assinatura no cartao e o "mensal"; o ano, "anual"; o mes no Pix, "avulso".
    conta.periodo = as && situacao === "authorized" ? "mensal" : r.periodo === "ano" ? "anual" : r.periodo === "mes" ? "avulso" : conta.periodo || "avulso";
    const plano = planoDe(n, conta.plano);
    conta.assinatura = { id: "atos-" + (as ? as.id : versao), situacao, valor: conta.periodo === "anual" ? plano.valor_anual : plano.valor,
      periodo: conta.periodo, desde: (conta.assinatura || {}).desde || iso(agora), cobrador: "atos" };
    conta.pago_ate = fim ? iso(fim) : null;
    const c = this.cicloAberto(conta, agora);
    if (c && fim < Date.parse(c.fim)) {
      // O direito encurtou (a devolucao, ou o mes que nao veio): o ciclo acaba com ele.
      c.fim = iso(Math.max(fim, Date.parse(c.inicio)));
    } else if (!c && fim > agora) {
      // O primeiro pagamento, ou a cobranca que veio depois do fim do ciclo: o ciclo comeca agora.
      this.abrirCiclo(conta, n, agora, "atos");
    }
    return [this.resumo(conta, n, agora), conta];
  }

  /* Uma compra avulsa paga na Atos (credito.adicionado): a recarga, com os tokens que o catalogo da Atos
     diz. Uma vez por origem (o pagamento). */
  creditoDaAtos(conta, d, n, agora) {
    const c = d.credito || {};
    const tokens = Math.max(0, Math.round(Number((c.metadados || {}).tokens) || 0));
    if (!c.origem || !tokens) return [{ ok: false, status: 400, erro: "o crédito precisa da origem e dos tokens" }, null];
    const pedido = "atos:" + String(c.origem);
    conta.recargas = conta.recargas || [];
    if (conta.recargas.some((x) => x.pedido === pedido)) return [{ ...this.resumo(conta, n, agora), repetido: true }, null];
    conta.extra = (conta.extra || 0) + tokens;
    conta.recargas = [...conta.recargas, { pedido, tokens, valor: (Number(c.centavos) || 0) / 100, quando: new Date(agora).toISOString(), por: "atos" }].slice(-50);
    return [this.resumo(conta, n, agora), conta];
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
    // O plano e o que a Atos diz que foi pago (cobrador "atos"), ou a cortesia. O que o caminho antigo do PAVLVS
    // (o Mercado Pago proprio, ate 10/10/2026) deixou anotado nao vale.
    if (conta.cobrador !== "atos" && !conta.cortesia) return false;
    // Pago ate uma data (o ano, o mes no Pix, ou a assinatura que a Atos estende a cada cobranca): cada mes abre o
    // seu ciclo, com a cota do mes.
    const pagoAte = Date.parse(conta.pago_ate || "");
    if (!conta.cortesia && conta.ciclo && !this.cicloAberto(conta, agora) && agora < pagoAte) {
      let inicio = Date.parse(conta.ciclo.fim);
      while (maisUmMes(inicio) <= agora) inicio = maisUmMes(inicio);
      this.abrirCiclo(conta, n, inicio, conta.periodo);
    }
    const a = conta.assinatura || {};
    const c = conta.ciclo;
    if (!c) return false;
    const fim = Date.parse(c.fim);
    if (fim > agora) return true;
    // A tolerancia e da assinatura no cartao, cuja cobranca do mes pode atrasar uns dias no Mercado Pago.
    return !conta.cortesia && conta.periodo === "mensal" && a.situacao === "authorized" && agora < fim + TOLERANCIA_MS;
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
      conta.uso = [...conta.uso, u].slice(-400);
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
    // O mes inteiro, que fica depois que o dia sai (400 dias; o "2026" do painel).
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
      // Quem cobra esta conta: o PAVLVS (o Mercado Pago dele) ou a Atos (atos.dev.br; worker/atos.js).
      cobrador: conta.cobrador || "pavlvs",
      consentimento: conta.consentimento || null,
      assinatura: a ? { id: a.id, situacao: a.situacao, valor: a.valor, desde: a.desde, periodo: a.periodo || "mensal" } : null,
      plano_vigente: vigente,
      plano,
      modelos: catalogo(modelosDoPlano(plano)),
      // Mensal ou anual; no anual, ate quando o ano esta pago.
      periodo: conta.periodo || "mensal",
      pago_ate: conta.pago_ate || null,
      agora: new Date(agora).toISOString(),
      // Ainda no prazo de arrependimento (os 7 primeiros dias da assinatura).
      arrependimento_ate: a && a.desde ? new Date(Date.parse(a.desde) + ARREPENDIMENTO_MS).toISOString() : null,
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
      // A ordem da Minha conta ou do painel para o PAULUS instalado: que
      // servicos do Google ele continua usando. O resto ele para de usar (o
      // Google nao revoga um servico sozinho: a permissao continua concedida
      // la); nenhum: ele revoga a concessao inteira no Google.
      google_pendente: conta.google_pendente || null,
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
        // A Minha conta: o motivo de quem cancelou (Nao renovacoes), as ofertas, a cobranca ajustada, o cartao e a forma.
        cancelamento: conta.cancelamento || null, ofertas: conta.ofertas || [], ajuste: conta.ajuste || null,
        cartao: conta.cartao || null, forma: conta.forma || null, valor_a_restaurar: conta.valor_a_restaurar || null,
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
      // "painel": o PAULUS diz ao escritorio que quem desligou foi a equipe do PAULUS.
      conta.google_pendente = { id: "g" + agora, ligados: (d.ligados || []).map(String).slice(0, 10), quando: new Date(agora).toISOString(), por: "painel" };
      return [this.resumo(conta, n, agora), conta];
    }
    if (acao === "admin_desvincular") {
      // A conta Google sai da nuvem: as instalacoes param (o segredo some) e
      // a mesma conta Google nao entra de novo. Plano, tokens e historico ficam.
      conta.desvinculado = { quando: new Date(agora).toISOString(), por: d.por || "", email: (conta.dono || {}).email || "" };
      conta.segredos = [];
      return [this.resumo(conta, n, agora), conta];
    }
    return [{ ok: false, erro: "ação desconhecida", status: 400 }, null];
  }
}
