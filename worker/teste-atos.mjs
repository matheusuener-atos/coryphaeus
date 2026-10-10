// Teste da cobranca pela Atos no PAVLVS (worker/atos.js e as acoes atos_* do ContaIA), sem rede:
//   node worker/teste-atos.mjs
// Os eventos sao assinados aqui como a Atos assina (C:\atos\worker\cobranca\eventos.js); o Durable Object roda
// com a mesma classe, sobre um Map; o Mercado Pago do PAVLVS e a Atos (a reserva) sao de mentira.
import { createHmac } from "node:crypto";
import worker from "./index.js";
import { atenderAtos, conferirNaAtos } from "./atos.js";
import { atenderIA, ContaIA, medidor } from "./ia.js";

let falhas = 0;
const checar = (ok, descricao, detalhe) => {
  console.log((ok ? "  ok   " : "  FALHA ") + descricao + (ok || detalhe === undefined ? "" : " -> " + JSON.stringify(detalhe)));
  if (!ok) falhas++;
};

let relogio = Date.parse("2026-10-10T12:00:00Z");
const DIA = 864e5;
const objetos = new Map();
function objeto(nome) {
  if (!objetos.has(nome)) {
    const dados = new Map();
    const o = new ContaIA({ storage: { get: async (k) => structuredClone(dados.get(k)), put: async (k, v) => { dados.set(k, structuredClone(v)); } } }, {});
    o.agora = () => relogio;
    objetos.set(nome, { o, dados });
  }
  return objetos.get(nome);
}
const CONTAS_IA = { idFromName: (n) => n, get: (n) => ({ fetch: (url, init) => objeto(n).o.fetch(new Request(url, init)) }) };
const guardados = new Map();
const SEGREDO = "segredo-dos-eventos";
const env = {
  IA_ATIVA: "1",
  CONTAS_IA,
  EVENTOS_SEGREDO_PAVLVS: SEGREDO,
  APOIOS: {
    get: async (k) => guardados.get(k) || null,
    getWithMetadata: async (k) => ({ value: guardados.get(k) || null, metadata: null }),
    put: async (k, v) => { guardados.set(k, v); },
    delete: async (k) => { guardados.delete(k); },
    list: async ({ prefix }) => ({ list_complete: true, keys: [...guardados.keys()].filter((k) => k.startsWith(prefix)).map((name) => ({ name })) }),
  },
};

// O Mercado Pago do PAVLVS: so o cancelamento da assinatura antiga.
const mpChamadas = [];
let mpFalha = false;
async function chamarMP(e, caminho, metodo, corpo) {
  mpChamadas.push({ caminho, metodo, corpo });
  if (mpFalha) return { ok: false, status: 500, dados: null };
  return { ok: true, status: 200, dados: { id: caminho.split("/").pop(), status: corpo && corpo.status } };
}
const deps = { chamarMP };

async function idDe(sub) {
  const h = await crypto.subtle.digest("SHA-256", new TextEncoder().encode("conta-ia:" + sub));
  return [...new Uint8Array(h)].map((x) => x.toString(16).padStart(2, "0")).join("").slice(0, 24);
}
const resumoDe = async (sub) => medidor(env, await idDe(sub)).pedir("resumo");
const contaDe = async (sub) => objeto(await idDe(sub)).dados.get("conta");

let seq = 0;
function evento(tipo, sub, dados, extra = {}) {
  return { id: "ev-" + ++seq, tipo, produto: "pavlvs", criado: new Date(relogio).toISOString(), conta: { sub, email: sub + "@escritorio.adv.br" }, dados, ...extra };
}
function pedido(ev, { segredo = SEGREDO, ts = Math.floor(Date.now() / 1000), corpo } = {}) {
  const texto = corpo || JSON.stringify(ev);
  const v1 = createHmac("sha256", segredo).update(`${ts}.${texto}`).digest("hex");
  return new Request("https://paulus.ia.br/api/atos/eventos", { method: "POST", headers: { "content-type": "application/json", "Atos-Evento": ev.id, "Atos-Assinatura": `t=${ts},v1=${v1}` }, body: texto });
}
const entregar = async (ev, opcoes, e = env) => {
  const req = pedido(ev, opcoes);
  const r = await atenderAtos(req, e, new URL(req.url), deps);
  return { status: r.status, d: await r.json() };
};
const iso = (t) => new Date(t).toISOString();
const retrato = (versao, extra = {}) => ({ versao, plano: "escritorio", metadados: { plano: "escritorio", tokens_por_ciclo: 60000000, pessoas: 5 }, ate: null, periodo: null, assinatura: null, ...extra });

console.log("a assinatura da Atos");
{
  const ev = evento("direito.atualizado", "pv-ana", retrato(1));
  let r = await entregar(ev, {}, { ...env, EVENTOS_SEGREDO_PAVLVS: "" });
  checar(r.status === 503, "sem o segredo no Worker: 503 (a Atos tenta de novo)", r);
  r = await entregar(ev, { segredo: "outro" });
  checar(r.status === 401, "assinada com outro segredo: 401", r);
  r = await entregar(ev, { ts: Math.floor(Date.now() / 1000) - 600 });
  checar(r.status === 401, "assinada ha 10 minutos (repeticao): 401", r);
  const adulterado = pedido(ev);
  const outro = new Request(adulterado.url, { method: "POST", headers: adulterado.headers, body: JSON.stringify({ ...ev, conta: { sub: "pv-outro", email: "x@y" } }) });
  const r2 = await atenderAtos(outro, env, new URL(outro.url), deps);
  checar(r2.status === 401, "o corpo trocado depois de assinado: 401", r2.status);
  checar(!(await contaDe("pv-outro")), "e nada foi aplicado");
}

console.log("o ano pago na Atos, por quem nunca abriu o PAVLVS");
const ateAno = (() => { let t = relogio; for (let i = 0; i < 12; i++) { const d = new Date(t); const dia = d.getUTCDate(); d.setUTCMonth(d.getUTCMonth() + 1); if (d.getUTCDate() < dia) d.setUTCDate(0); t = d.getTime(); } return t; })();
{
  const r = await entregar(evento("direito.atualizado", "pv-ana", retrato(2, { ate: iso(ateAno), periodo: "ano" })));
  checar(r.status === 200 && r.d.aplicado === true, "aplicado (200)", r);
  const s = await resumoDe("pv-ana");
  checar(s.cobrador === "atos" && s.plano_vigente && s.plano.id === "escritorio" && s.periodo === "anual" && s.pago_ate === iso(ateAno),
    "a conta nasce cobrada pela Atos: Escritório, anual, pago até o que a Atos disse", { cobrador: s.cobrador, plano: s.plano.id, periodo: s.periodo, pago_ate: s.pago_ate });
  checar(s.ciclo && s.ciclo.tokens === 60000000 && s.ciclo.inicio === iso(relogio) && s.email === "pv-ana@escritorio.adv.br",
    "o ciclo do mês abre agora, com os tokens do plano; o dono é o da Conta Atos", s.ciclo);
  const de = await entregar(evento("direito.atualizado", "pv-ana", retrato(2, { ate: iso(ateAno), periodo: "ano" })));
  checar(de.status === 200 && de.d.aplicado === false, "a mesma versão de novo: recebida, não aplicada", de.d);
  const velho = await entregar(evento("direito.atualizado", "pv-ana", retrato(1, { ate: iso(relogio + DIA), periodo: "mes" })));
  const s2 = await resumoDe("pv-ana");
  checar(velho.d.aplicado === false && s2.pago_ate === iso(ateAno), "uma versão velha fora de ordem não encurta nada", s2.pago_ate);
  const inicio = relogio;
  relogio += 40 * DIA;
  const s3 = await resumoDe("pv-ana");
  checar(s3.plano_vigente && Date.parse(s3.ciclo.inicio) > inicio && s3.ciclo.usados === 0, "um mês depois, o ciclo seguinte abre sozinho (o ano está pago)", s3.ciclo);
  relogio = inicio;
}

console.log("a recarga paga na Atos");
{
  const antes = (await resumoDe("pv-ana")).tokens.da_recarga;
  const dados = { origem: "order:ORD01", preco: "pavlvs.escritorio.recarga", centavos: 12000, metadados: { plano: "escritorio", tokens: 10000000 } };
  let r = await entregar(evento("credito.adicionado", "pv-ana", dados));
  checar(r.status === 200 && r.d.aplicado === true && (await resumoDe("pv-ana")).tokens.da_recarga === antes + 10000000, "os 10 milhões de tokens do catálogo da Atos entram", r.d);
  r = await entregar(evento("credito.adicionado", "pv-ana", dados));
  checar(r.d.aplicado === false && (await resumoDe("pv-ana")).tokens.da_recarga === antes + 10000000, "o mesmo pagamento de novo: credita uma vez só", r.d);
  r = await entregar(evento("credito.adicionado", "pv-ana", { origem: "order:ORD02", metadados: {} }));
  checar(r.status === 200 && r.d.ignorado, "o crédito sem tokens: recebido e ignorado (não fica voltando)", r.d);
  r = await entregar(evento("cupom.novo", "pv-ana", {}));
  checar(r.status === 200 && r.d.ignorado, "um tipo de evento que o PAVLVS não conhece: recebido e ignorado", r.d);
}

console.log("a assinatura mensal no cartão");
{
  const t0 = relogio;
  const as = (status) => ({ id: "atos-a-assinatura-1", status, proxima: null, preco: "pavlvs.advogado.mes" });
  await entregar(evento("direito.atualizado", "pv-bia", retrato(1, { plano: "advogado", assinatura: as("authorized") })));
  let s = await resumoDe("pv-bia");
  checar(s.cobrador === "atos" && !s.plano_vigente && s.assinatura.situacao === "authorized", "autorizada mas sem cobrança paga: ainda sem plano", { v: s.plano_vigente, a: s.assinatura });
  const ate1 = Date.parse("2026-11-10T12:00:00Z");
  await entregar(evento("direito.atualizado", "pv-bia", retrato(2, { plano: "advogado", ate: iso(ate1), periodo: "mes", assinatura: as("authorized") })));
  s = await resumoDe("pv-bia");
  checar(s.plano_vigente && s.periodo === "mensal" && s.plano.id === "advogado" && s.ciclo.fim === iso(ate1) && s.ciclo.tokens === 30000000,
    "a primeira cobrança paga: o ciclo vai até o pago da Atos", { periodo: s.periodo, ciclo: s.ciclo });
  // A cobrança de novembro chega antes do fim do ciclo: ao virar, o ciclo seguinte abre sozinho.
  const ate2 = Date.parse("2026-12-10T12:00:00Z");
  relogio = ate1 - DIA;
  await entregar(evento("direito.atualizado", "pv-bia", retrato(3, { plano: "advogado", ate: iso(ate2), periodo: "mes", assinatura: as("authorized") })));
  relogio = ate1 + 3600e3;
  s = await resumoDe("pv-bia");
  checar(s.plano_vigente && s.ciclo.inicio === iso(ate1) && s.ciclo.fim === iso(ate2), "paga antes do fim: o ciclo seguinte abre no dia certo", s.ciclo);
  // A de dezembro atrasa: os dias de tolerância seguram o plano, e o ciclo novo abre quando ela chega.
  relogio = ate2 + 2 * DIA;
  s = await resumoDe("pv-bia");
  checar(s.plano_vigente && s.ciclo.fim === iso(ate2), "a cobrança atrasada: o plano segue na tolerância", s.ciclo);
  const ate3 = Date.parse("2027-01-12T12:00:00Z");
  await entregar(evento("direito.atualizado", "pv-bia", retrato(4, { plano: "advogado", ate: iso(ate3), periodo: "mes", assinatura: as("authorized") })));
  s = await resumoDe("pv-bia");
  checar(s.plano_vigente && s.ciclo.inicio === iso(relogio) && s.ciclo.usados === 0, "e quando ela chega, o ciclo novo abre agora", s.ciclo);
  // Cancelada: o mês pago fica até o fim, e acaba.
  await entregar(evento("direito.atualizado", "pv-bia", retrato(5, { plano: "advogado", ate: iso(ate3), periodo: "mes", assinatura: as("canceled") })));
  s = await resumoDe("pv-bia");
  checar(s.plano_vigente && s.assinatura.situacao === "cancelled", "cancelada: o mês pago continua", s.assinatura);
  relogio = ate3 + DIA;
  s = await resumoDe("pv-bia");
  checar(!s.plano_vigente, "e passado o pago, a conta fica sem plano (sem tolerância: não há cobrança a esperar)", { v: s.plano_vigente, ciclo: s.ciclo });
  relogio = t0;
}

console.log("a assinatura cancelada e o ano pago à parte (o teste de 10/10)");
{
  const as = { id: "atos-a-assinatura-9", status: "canceled", proxima: null, preco: "pavlvs.advogado.mes" };
  await entregar(evento("direito.atualizado", "pv-jon", retrato(1, { plano: "advogado", assinatura: as })));
  await entregar(evento("direito.atualizado", "pv-jon", retrato(2, { plano: "advogado", ate: iso(relogio + 365 * DIA), periodo: "ano", pago_por: "compra", assinatura: as })));
  const s = await resumoDe("pv-jon");
  checar(s.plano_vigente && s.periodo === "anual" && s.assinatura.situacao === "authorized",
    "o ano pago numa compra: em dia (e não 'cancelada' por causa da assinatura antiga)", { periodo: s.periodo, a: s.assinatura });
}

console.log("a devolução encurta o direito");
{
  const ate = relogio + 30 * DIA;
  await entregar(evento("direito.atualizado", "pv-cid", retrato(1, { ate: iso(ate), periodo: "mes" })));
  checar((await resumoDe("pv-cid")).plano_vigente, "o mês no Pix pago");
  await entregar(evento("direito.atualizado", "pv-cid", retrato(2, { ate: iso(relogio), periodo: "mes" })));
  const s = await resumoDe("pv-cid");
  checar(!s.plano_vigente && s.ciclo.fim === iso(relogio), "a Atos devolveu: o ciclo acaba agora", s.ciclo);
}

console.log("quem já pagava o PAVLVS passa para a Atos");
{
  // Uma assinatura mensal do Mercado Pago do PAVLVS, autorizada, com o ciclo aberto.
  const id = await idDe("pv-dani");
  const conta = medidor(env, id);
  await conta.pedir("abrir", { id, dono: { sub: "pv-dani", email: "dani@x.br" } });
  await conta.pedir("assinatura", { plano: "plus", assinatura: { id: "pre-antiga", situacao: "authorized", valor: 3490 } });
  const fimAntigo = (await conta.pedir("resumo")).ciclo.fim;
  mpFalha = true;
  const ev = evento("direito.atualizado", "pv-dani", retrato(1, { plano: "plus", ate: iso(relogio + 365 * DIA), periodo: "ano" }));
  const req = pedido(ev);
  const recusou = await atenderAtos(req, env, new URL(req.url), deps).then(() => false, () => true);
  checar(recusou, "o Mercado Pago do PAVLVS fora: o evento falha (500 no Worker) e a Atos manda de novo");
  mpFalha = false;
  let r = await entregar(ev);
  const c = await contaDe("pv-dani");
  const cancel = mpChamadas.filter((x) => x.caminho === "/preapproval/pre-antiga" && x.metodo === "PUT" && x.corpo.status === "cancelled");
  checar(r.status === 200 && cancel.length >= 2 && c.mensal_cancelado && c.mensal_cancelado.id === "pre-antiga",
    "na entrega seguinte, a assinatura antiga sai no Mercado Pago do PAVLVS", { status: r.status, cancel: cancel.length, mc: c.mensal_cancelado });
  const s = await resumoDe("pv-dani");
  checar(s.cobrador === "atos" && s.plano.id === "plus" && s.periodo === "anual" && Date.parse(s.pago_ate) > Date.parse(fimAntigo), "e o plano passa a ser o da Atos", s.pago_ate);
  const antes = mpChamadas.length;
  r = await entregar(ev);
  checar(r.d.aplicado === false && mpChamadas.length === antes, "repetido depois de cancelada: não chama o Mercado Pago de novo");
  await conta.pedir("assinatura", { assinatura: { id: "pre-antiga", situacao: "cancelled" } });
  checar((await resumoDe("pv-dani")).assinatura.id.startsWith("atos-"), "o aviso da assinatura antiga cancelada não mexe na conta da Atos");
}
{
  // O anual pago no PAVLVS: o tempo que falta fica.
  const id = await idDe("pv-eli");
  const conta = medidor(env, id);
  await conta.pedir("abrir", { id, dono: { sub: "pv-eli", email: "eli@x.br" } });
  await conta.pedir("anual_pago", { plano: "advogado", pagamento: "pg-1", valor: 3990, meses: 12 });
  const pagoAntes = (await conta.pedir("resumo")).pago_ate;
  await entregar(evento("direito.atualizado", "pv-eli", retrato(1, { plano: "advogado", ate: iso(relogio + 30 * DIA), periodo: "mes" })));
  const s = await resumoDe("pv-eli");
  checar(s.cobrador === "atos" && s.pago_ate === pagoAntes && s.plano_vigente, "o ano já pago no PAVLVS não se perde ao passar para a Atos", { antes: pagoAntes, depois: s.pago_ate });
}

console.log("as rotas de dinheiro do PAVLVS não servem a conta da Atos");
{
  const donos = { "tk-ana": { sub: "pv-ana", email: "pv-ana@escritorio.adv.br" }, "tk-novo": { sub: "pv-fab", email: "fab@x.br" } };
  const depsIA = { chamarMP, donoDoToken: async (e, t) => donos[t] || null };
  const ia = async (metodo, caminho, corpo, segredo) => {
    const headers = { "content-type": "application/json" };
    if (segredo) headers.authorization = "Bearer " + segredo;
    const req = new Request("https://paulus.ia.br" + caminho, { method: metodo, headers, body: corpo ? JSON.stringify(corpo) : undefined });
    const r = await atenderIA(req, env, new URL(req.url), { waitUntil() {} }, depsIA);
    return { status: r.status, d: await r.json() };
  };
  const antes = mpChamadas.length;
  let r = await ia("POST", "/api/ia/site/pagar", { id_token: "tk-ana", plano: "plus", periodo: "anual", meio: "pix" });
  checar(r.status === 409 && r.d.codigo === "cobranca_na_atos" && r.d.proximo === "https://atos.dev.br/conta/", "pagar pelo site do PAVLVS: 409, para a Atos", r);
  r = await ia("POST", "/api/ia/site/desistir", { id_token: "tk-ana" });
  checar(r.status === 409 && r.d.codigo === "cobranca_na_atos", "desistir pelo site do PAVLVS: 409", r.status);
  const at = await ia("POST", "/api/ia/ativar", { id_token: "tk-ana", instalacao_id: "inst-ana-0001" });
  r = await ia("POST", "/api/ia/recarga", { pacote: "1" }, at.d.segredo);
  checar(r.status === 409 && r.d.codigo === "cobranca_na_atos", "a recarga pelo PAULUS instalado: 409", r.status);
  r = await ia("POST", "/api/ia/assinatura/cancelar", {}, at.d.segredo);
  checar(r.status === 409, "cancelar pelo PAULUS instalado: 409", r.status);
  checar(mpChamadas.length === antes, "e nenhuma chamada ao Mercado Pago do PAVLVS");
  r = await ia("GET", "/api/ia/conta", null, at.d.segredo);
  checar(r.status === 200 && r.d.cobrador === "atos" && r.d.plano_vigente, "a conta continua aberta ao PAULUS instalado", { s: r.status, c: r.d.cobrador });
}

console.log("a reserva: o evento que se perdeu");
{
  const chamadas = [];
  let resposta = { produto: "pavlvs", sub: "pv-gil", versao: 3, plano: "escritorio", metadados: {}, ate: iso(relogio + 365 * DIA), periodo: "ano", assinatura: null };
  const depsR = { chamarMP, fetch: async (url, init) => { chamadas.push({ url: String(url), auth: init.headers.authorization }); return new Response(JSON.stringify(resposta), { status: 200 }); } };
  const id = await idDe("pv-gil");
  const conta = medidor(env, id);
  await conta.pedir("abrir", { id, dono: { sub: "pv-gil", email: "gil@x.br" } });
  checar(!(await conta.pedir("resumo")).plano_vigente, "pagou na Atos, mas o evento não chegou: sem plano");
  checar(await conferirNaAtos(env, conta, depsR), "a conta fora de dia pergunta à Atos e aplica o retrato");
  const s = await conta.pedir("resumo");
  checar(s.plano_vigente && s.cobrador === "atos" && s.periodo === "anual", "agora com o plano", { v: s.plano_vigente, c: s.cobrador });
  checar(chamadas.length === 1 && chamadas[0].url === "https://atos.dev.br/api/cobranca/v1/direitos?produto=pavlvs&sub=pv-gil" && chamadas[0].auth === "Bearer " + SEGREDO,
    "com o segredo do PAVLVS e o sub da conta", chamadas);
  checar(!(await conferirNaAtos(env, conta, depsR)) && chamadas.length === 1, "com o plano em dia, não pergunta");
  const id2 = await idDe("pv-hel");
  const c2 = medidor(env, id2);
  await c2.pedir("abrir", { id: id2, dono: { sub: "pv-hel", email: "hel@x.br" } });
  resposta = { produto: "pavlvs", sub: "pv-hel", versao: 0, plano: null, ate: null, assinatura: null };
  await conferirNaAtos(env, c2, depsR);
  await conferirNaAtos(env, c2, depsR);
  checar(chamadas.length === 2, "sem nada na Atos: pergunta uma vez a cada 10 minutos, não a cada pedido", chamadas.length);
  relogio += 11 * 60e3;
  await conferirNaAtos(env, c2, depsR);
  checar(chamadas.length === 3 && !(await c2.pedir("resumo")).plano_vigente, "passados 10 minutos, pergunta de novo");
}

console.log("as vendas pela Atos (COBRANCA_PELA_ATOS)");
{
  const envVenda = { ...env, COBRANCA_PELA_ATOS: "1", ASSETS: { fetch: async () => new Response("site", { status: 200 }) } };
  const donos = { "tk-novo": { sub: "pv-kim", email: "kim@x.br" } };
  const mpAntes = mpChamadas.length;
  const depsV = { chamarMP, donoDoToken: async (e, t) => donos[t] || null };
  const ia = async (e, metodo, caminho, corpo, segredo) => {
    const headers = { "content-type": "application/json" };
    if (segredo) headers.authorization = "Bearer " + segredo;
    const req = new Request("https://paulus.ia.br" + caminho, { method: metodo, headers, body: corpo ? JSON.stringify(corpo) : undefined });
    const r = await atenderIA(req, e, new URL(req.url), { waitUntil() {} }, depsV);
    return { status: r.status, d: await r.json() };
  };
  const ATOS_CK = "https://atos.dev.br/pavlvs/assinar/?preco=";
  let r = await ia(envVenda, "POST", "/api/ia/site/pagar", { id_token: "tk-novo", plano: "plus", periodo: "anual", meio: "pix" });
  checar(r.status === 409 && r.d.codigo === "cobranca_na_atos" && r.d.proximo.startsWith(ATOS_CK + "pavlvs.plus.ano"),
    "conta nova pagando pelo caminho antigo: 409, com o checkout da Atos no mesmo plano e período", r.d);
  r = await ia(envVenda, "POST", "/api/ia/site/pagar-fora", { id_token: "tk-novo", plano: "advogado" });
  checar(r.status === 409 && r.d.proximo.startsWith(ATOS_CK + "pavlvs.advogado.mes"), "o pagar-fora também", r.status);
  const at = await ia(envVenda, "POST", "/api/ia/ativar", { id_token: "tk-novo", instalacao_id: "inst-kim-0001" });
  r = await ia(envVenda, "POST", "/api/ia/assinar", { plano: "escritorio", periodo: "anual" }, at.d.segredo);
  checar(r.status === 200 && r.d.link === ATOS_CK + "pavlvs.escritorio.ano&volta=" + encodeURIComponent("https://paulus.ia.br/"),
    "o 'Fazer upgrade' do PAULUS instalado abre o checkout da Atos", r.d);
  r = await ia(envVenda, "POST", "/api/ia/recarga", { pacote: "1" }, at.d.segredo);
  checar(r.status === 409 && r.d.codigo === "cobranca_na_atos", "a recarga pelo caminho antigo: 409", r.status);
  r = await ia(envVenda, "POST", "/api/ia/site/cadastro", { id_token: "tk-novo", nome_escritorio: "Kim Advocacia", documento: "529.982.247-25", telefone: "(91) 98888-7777",
    oab: "OAB/PA 1", aceite: true, plano: "plus", periodo: "mensal",
    endereco: { cep: "66010-000", logradouro: "Av. P", numero: "1", complemento: "", bairro: "C", cidade: "Belém", uf: "PA", cmun: "1501402" } });
  checar(r.status === 200 && String(r.d.proximo).startsWith(ATOS_CK + "pavlvs.plus.mes"), "o cadastro com plano segue para o checkout da Atos", r.d.proximo);
  checar(mpChamadas.length === mpAntes, "e o Mercado Pago do PAVLVS não foi chamado");
  const w = await worker.fetch(new Request("https://paulus.ia.br/cadastro/pagamento/?plano=advogado&periodo=anual"), envVenda, { waitUntil() {} });
  checar(w.status === 302 && w.headers.get("location").startsWith(ATOS_CK + "pavlvs.advogado.ano"), "/cadastro/pagamento leva ao checkout da Atos (302)", w.headers.get("location"));
  const w2 = await worker.fetch(new Request("https://paulus.ia.br/cadastro/"), { ...envVenda, COBRANCA_PELA_ATOS: "" }, { waitUntil() {} });
  checar(w2.status !== 302, "sem a chave, o cadastro antigo continua (para abrir só quando a Atos abrir)", w2.status);
  const sem = await ia(env, "POST", "/api/ia/assinar", { plano: "escritorio" }, at.d.segredo);
  checar(String(sem.d.link || "").startsWith("https://paulus.ia.br/cadastro/pagamento/"), "e sem a chave, o link é o antigo", sem.d);
}

console.log("pelo Worker inteiro");
{
  const ev = evento("direito.atualizado", "pv-ivo", retrato(1, { ate: iso(relogio + 30 * DIA), periodo: "mes" }));
  const r = await worker.fetch(pedido(ev), env, { waitUntil() {} });
  checar(r.status === 200 && (await resumoDe("pv-ivo")).plano_vigente, "POST /api/atos/eventos chega a atos.js", r.status);
  const g = await worker.fetch(new Request("https://paulus.ia.br/api/atos/eventos"), env, { waitUntil() {} });
  checar(g.status === 405, "GET: 405", g.status);
}

console.log(falhas ? `\n  ${falhas} falha(s)` : "\n  atos: todos os testes passaram");
process.exit(falhas ? 1 : 0);
