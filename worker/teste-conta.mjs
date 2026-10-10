// Teste da Minha conta (worker/conta.js), sem rede. A cobranca e da Atos: o plano chega pelo aviso dela
// (worker/atos.js), simulado aqui no medidor; as rotas de dinheiro de antes mandam para a Atos.
//   node worker/teste-conta.mjs
// O Durable Object roda aqui sobre um Map; o Mercado Pago, o Google, a
// Cloudflare e o e-mail sao de mentira. O relogio e um so (Date.now tambem).
import worker from "./index.js";
import { ContaIA, atenderIA, medidor } from "./ia.js";
import { atenderConta, consumoDo } from "./conta.js";

let falhas = 0;
const checar = (ok, descricao, detalhe) => {
  console.log((ok ? "  ok   " : "  FALHA ") + descricao + (ok || detalhe === undefined ? "" : " -> " + JSON.stringify(detalhe)));
  if (!ok) falhas++;
};

let relogio = Date.parse("2026-10-07T15:00:00Z");
Date.now = () => relogio;
const DIA = 24 * 3600 * 1000;

// ------------------------------------------------ o Durable Object aqui
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

// ------------------------------------------------ Mercado Pago e Cloudflare
const mpPedidos = [];
const mpPreapprovals = new Map();
const mpPagamentos = new Map();
const recusarPut = new Set();
const cf = [];
globalThis.fetch = async (url, init = {}) => {
  const u = String(url);
  const metodo = init.method || "GET";
  const corpo = init.body ? JSON.parse(init.body) : null;
  if (u.startsWith("https://api.cloudflare.com/")) {
    cf.push({ u, metodo, corpo });
    return new Response(JSON.stringify({ success: true, result: { status: "healthy", id: "x" } }), { status: 200 });
  }
  if (!u.startsWith("https://api.mercadopago.com")) return new Response("{}", { status: 404 });
  const caminho = u.slice("https://api.mercadopago.com".length);
  mpPedidos.push({ caminho, metodo, corpo });
  if (caminho === "/preapproval" && metodo === "POST") {
    const id = "pre" + mpPreapprovals.size;
    mpPreapprovals.set(id, { id, status: "authorized", external_reference: corpo.external_reference, auto_recurring: { ...corpo.auto_recurring } });
    return new Response(JSON.stringify({ id, status: "authorized" }), { status: 201 });
  }
  let m = caminho.match(/^\/preapproval\/(.+)$/);
  if (m) {
    const p = mpPreapprovals.get(decodeURIComponent(m[1]));
    if (!p) return new Response("{}", { status: 404 });
    if (metodo === "PUT") {
      if (recusarPut.has(p.id)) return new Response("{}", { status: 500 });
      if (corpo.status) p.status = corpo.status;
      if (corpo.auto_recurring) p.auto_recurring = { ...p.auto_recurring, ...corpo.auto_recurring };
      if (corpo.card_token_id) p.card_token_id = corpo.card_token_id;
    }
    return new Response(JSON.stringify(p), { status: 200 });
  }
  m = caminho.match(/^\/v1\/card_tokens\/(.+)$/);
  if (m) return new Response(JSON.stringify({ id: m[1], last_four_digits: "4242", expiration_month: 3, expiration_year: 2031, cardholder: { name: "HELENA MOURA" } }), { status: 200 });
  if (caminho === "/v1/orders" && metodo === "POST") {
    return new Response(JSON.stringify({ id: "ORD1", transactions: { payments: [{ payment_method: { qr_code: "000201pix-recarga", qr_code_base64: "iVBORrec" } }] } }), { status: 201 });
  }
  if (caminho === "/v1/payments" && metodo === "POST") {
    const id = String(8000 + mpPagamentos.size);
    const pg = { id: Number(id), status: "pending", external_reference: corpo.external_reference, transaction_amount: corpo.transaction_amount, payment_method_id: corpo.payment_method_id,
      point_of_interaction: { transaction_data: { qr_code: "00020126pix-mes-" + id, qr_code_base64: "iVBORmes", ticket_url: "https://mp/ticket/" + id } } };
    mpPagamentos.set(id, pg);
    return new Response(JSON.stringify(pg), { status: 201 });
  }
  return new Response("{}", { status: 404 });
};
async function chamarMP(env, caminho, metodo, corpo, extra = {}) {
  const r = await fetch("https://api.mercadopago.com" + caminho, { method: metodo, headers: { ...extra }, body: corpo ? JSON.stringify(corpo) : undefined });
  let dados = null;
  try { dados = await r.json(); } catch { dados = null; }
  return { ok: r.ok, status: r.status, dados };
}

// ------------------------------------------------ o ambiente
const kv = () => {
  const m = new Map();
  return {
    m,
    get: async (k) => (m.has(k) ? m.get(k) : null),
    put: async (k, v) => { m.set(k, v); },
    delete: async (k) => { m.delete(k); },
    list: async ({ prefix }) => ({ list_complete: true, keys: [...m.keys()].filter((k) => k.startsWith(prefix)).map((name) => ({ name })) }),
  };
};
const APOIOS = kv();
const ESCRITORIOS = kv();
const env = {
  IA_ATIVA: "1", CONTAS_IA, APOIOS, ESCRITORIOS, RESEND_API_KEY: "re_teste", MP_PUBLIC_KEY: "APP_USR-publica",
  IA_PLANOS: JSON.stringify([
    { id: "advogado", nome: "Advogado", valor: 449, valor_anual: 3990, tokens: 30000000 },
    { id: "escritorio", nome: "Escritório", valor: 1290, valor_anual: 11490, tokens: 60000000 },
    { id: "plus", nome: "Escritório Plus", valor: 3490, valor_anual: 30990, tokens: 40000000 },
  ]),
  ASSETS: { fetch: async () => new Response("<!doctype html><title>site</title>", { status: 200, headers: { "content-type": "text/html" } }) },
};
const donos = {
  "tk-helena": { sub: "111", email: "helena@moura.adv.br" },
  "tk-bruno": { sub: "222", email: "bruno@moura.adv.br" },
  "tk-sem": { sub: "333", email: "ninguem@x.com" },
  "tk-ana": { sub: "444", email: "ana@silva.adv.br" },
  "tk-dora": { sub: "555", email: "dora@lima.adv.br" },
};
const emails = [];
const enviar = async (e, carta) => { emails.push(carta); return { ok: true }; };
const deps = { chamarMP, donoDoToken: async (e, t) => donos[t] || null, enviarEmail: enviar };

async function ia(caminho, corpo) {
  const req = new Request("https://paulus.ia.br" + caminho, { method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify(corpo) });
  return atenderIA(req, env, new URL(req.url), { waitUntil: () => null }, deps);
}
async function conta(metodo, caminho, corpo, cookie, origem = "https://paulus.ia.br") {
  const headers = { "content-type": "application/json", origin: origem };
  if (cookie) headers.cookie = "pv_conta=" + cookie;
  const req = new Request("https://paulus.ia.br" + caminho, { method: metodo, headers, body: corpo ? JSON.stringify(corpo) : undefined });
  const r = await atenderConta(req, env, new URL(req.url), { waitUntil: () => null }, deps);
  let d = null;
  try { d = await r.clone().json(); } catch { d = null; }
  return { r, d, status: r.status };
}
const cookieDe = (r) => ((r.headers.get("set-cookie") || "").match(/pv_conta=([0-9a-f]*)/) || [])[1];
async function idDe(sub) {
  const d = await crypto.subtle.digest("SHA-256", new TextEncoder().encode("conta-ia:" + sub));
  return [...new Uint8Array(d)].map((x) => x.toString(16).padStart(2, "0")).join("").slice(0, 24);
}
const CADASTRO = { nome_escritorio: "Moura Advogados", documento: "529.982.247-25", telefone: "(91) 98888-7777", oab: "OAB/PA 12.345", aceite: true,
  endereco: { cep: "66010-000", logradouro: "Av. Presidente Vargas", numero: "100", complemento: "", bairro: "Campina", cidade: "Belém", uf: "PA", cmun: "1501402" } };
// O plano pago na Atos: o aviso dela, aplicado no medidor da conta.
let versaoAtos = 0;
async function daAtos(sub, retrato) {
  const id = await idDe(sub);
  return medidor(env, id).pedir("atos_direito", { id, dono: donos[Object.keys(donos).find((k) => donos[k].sub === sub)],
    retrato: { versao: ++versaoAtos, metadados: null, periodo: "mes", pago_por: "assinatura", ...retrato } });
}
const resumoDe = async (id) => (await CONTAS_IA.get(id).fetch("https://x/minha_conta", { method: "POST", body: JSON.stringify({ acao: "minha_conta" }) })).json();

// A Helena: o cadastro pelo site e o Escritorio pago na Atos.
const helena = await idDe("111");
await ia("/api/ia/site/cadastro", { ...CADASTRO, id_token: "tk-helena" });
await daAtos("111", { plano: "escritorio", ate: new Date(relogio + 30 * DIA).toISOString(),
  assinatura: { id: "atos-h", status: "authorized", proxima: new Date(relogio + 30 * DIA).toISOString(), preco: "pavlvs.escritorio.mes" } });

// ================================================= a Minha conta (worker/conta.js)
console.log("\nentrar");
let ck;
{
  checar((await conta("GET", "/api/conta")).status === 401, "sem sessão: 401 (a tela de entrar)");
  checar((await conta("POST", "/api/conta/entrar", { credential: "falso" })).status === 401, "id_token que não confere: 401");
  const sem = await conta("POST", "/api/conta/entrar", { credential: "tk-sem" });
  checar(sem.status === 404 && sem.d.sem_conta, "conta Google sem assinatura nem convite: diz como assinar", sem.d);
  checar((await conta("POST", "/api/conta/entrar", { credential: "tk-helena" }, null, "https://outro.site")).status === 403, "POST de outra origem é recusado");
  const e = await conta("POST", "/api/conta/entrar", { credential: "tk-helena" });
  ck = cookieDe(e.r);
  checar(e.status === 200 && e.d.papel === "titular" && /^[0-9a-f]{64}$/.test(ck) && /HttpOnly/.test(e.r.headers.get("set-cookie")) && /SameSite=Lax/.test(e.r.headers.get("set-cookie")),
    "o titular entra: cookie HttpOnly, SameSite", e.r.headers.get("set-cookie"));
  checar(![...APOIOS.m.keys()].some((k) => k.includes(ck)), "o KV guarda só o resumo do cookie");
}

console.log("\no que a tela lê");
{
  const { d, status } = await conta("GET", "/api/conta", null, ck);
  checar(status === 200 && d.perfil.papel === "titular" && d.perfil.email === "helena@moura.adv.br", "o perfil", d && d.perfil);
  checar(d.assinatura.nome === "Escritório" && d.assinatura.situacao === "ativa" && d.assinatura.periodo === "mensal" && d.assinatura.ciclo.tokens > 0, "a assinatura e o ciclo", d.assinatura);
  checar(!d.pagamento && !d.faturas && d.atos.assinaturas === "https://atos.dev.br/conta/assinaturas" && d.atos.checkout.plus.anual.includes("preco=pavlvs.plus.ano")
    && /pavlvs\.escritorio\.recarga/.test(decodeURIComponent(d.atos.recarga)), "o dinheiro não é daqui: os links da Conta Atos e do checkout", d.atos);
  checar(d.cadastro.nome === "Moura Advogados" && d.cadastro.documento === "529.982.247-25" && d.cadastro.cidade === "Belém", "o cadastro", d.cadastro);
  checar(d.planos.length === 3 && d.planos[0].modelos_info, "os planos para trocar");
  checar(d.escritorio === null && Array.isArray(d.instalacoes) && d.google.informado === false, "sem endereço, sem instalação, o Google não informado");
  checar(Array.isArray(d.consumo.dias) && d.consumo.dias.length >= 28 && d.consumo.pessoas.length === 0, "o consumo por dia (por pessoa, no PAULUS do escritório)", d.consumo.dias.length);
}

console.log("\no cadastro e o plano");
{
  const ruim = await conta("POST", "/api/conta/cadastro", { nome: "Moura", documento: "111.111.111-11", telefone: "91988887777", oab: "OAB/PA 1", cep: "66010000", logradouro: "Rua", numero: "1", bairro: "B", cidade: "Belém", uf: "PA" }, ck);
  checar(ruim.status === 400 && /CPF ou CNPJ/.test(ruim.d.erro), "o CPF/CNPJ é conferido", ruim.d);
  const ok = await conta("POST", "/api/conta/cadastro", { nome: "Moura e Souza Advogados", documento: "529.982.247-25", telefone: "(91) 98888-7777", oab: "OAB/PA 12.345",
    email_cobranca: "financeiro@moura.adv.br", cep: "66010-000", logradouro: "Av. Presidente Vargas", numero: "200", complemento: "sala 3", bairro: "Campina", cidade: "Belém", uf: "PA" }, ck);
  const r = await resumoDe(helena);
  checar(ok.status === 200 && r.cadastro.nome_escritorio === "Moura e Souza Advogados" && r.cadastro.email_cobranca === "financeiro@moura.adv.br"
    && r.cadastro.endereco.cmun === "1501402", "salvo; o mesmo CEP mantém o código do município", r.cadastro);
}

console.log("\npessoas: o financeiro");
let ckBruno;
{
  const c = await conta("POST", "/api/conta/pessoas", { email: "bruno@moura.adv.br", papel: "financeiro" }, ck);
  const link = (emails.at(-1) || {}).link || "";
  const token = (link.match(/#convite=([0-9a-f]+)/) || [])[1];
  checar(c.status === 200 && token && emails.at(-1).para === "bruno@moura.adv.br", "o convite vai por e-mail, com o link de 7 dias", c.d);
  const errado = await conta("POST", "/api/conta/entrar", { credential: "tk-ana", convite: token });
  checar(errado.status === 403, "o convite só abre com a conta Google convidada");
  const e = await conta("POST", "/api/conta/entrar", { credential: "tk-bruno", convite: token });
  ckBruno = cookieDe(e.r);
  checar(e.status === 200 && e.d.papel === "financeiro", "o convidado entra como financeiro", e.d);
  checar((await conta("POST", "/api/conta/entrar", { credential: "tk-bruno", convite: token })).status === 410, "o link vale uma vez");
  const v = await conta("GET", "/api/conta", null, ckBruno);
  checar(v.status === 200 && v.d.perfil.papel === "financeiro" && v.d.assinatura.nome === "Escritório", "o financeiro vê a conta do titular", v.d && v.d.perfil);
  checar((await conta("POST", "/api/conta/cadastro", { nome: "x" }, ckBruno)).status === 403, "mexer no cadastro é só do titular");
  const lista = (await conta("GET", "/api/conta", null, ck)).d.pessoas;
  checar(lista.length === 2 && lista[1].email === "bruno@moura.adv.br" && lista[1].papel === "financeiro" && !lista[1].convite, "a lista de pessoas", lista);
  await conta("POST", "/api/conta/pessoas/" + encodeURIComponent("bruno@moura.adv.br") + "/remover", {}, ck);
  checar((await conta("GET", "/api/conta", null, ckBruno)).status === 401, "tirado pelo titular: a sessão dele acaba na hora");
}

console.log("\nescritório, instalações, Google e notas");
{
  await ESCRITORIOS.put("escritorio:moura", JSON.stringify({ slug: "moura", nome: "Moura Advogados", tunnel_id: "t1", dns_id: "d1", porta: 8000, hash_segredo: "h1",
    instalacao_id: "inst-0001-abcd", dono: { sub: "111", email: "helena@moura.adv.br" }, ultima_conexao: new Date(relogio).toISOString(), criado_em: "2026-10-01T00:00:00Z" }));
  await ESCRITORIOS.put("dono:111", JSON.stringify({ slugs: ["moura"] }));
  await ESCRITORIOS.put("escritorio:ocupado", JSON.stringify({ slug: "ocupado", dono: { sub: "999", email: "x@x.com" } }));
  env.CF_ACCOUNT_ID = "acc";
  env.CF_ZONE_ID = "zona";
  env.CF_API_TOKEN = "cf";
  env.TUNEL_ATIVO = "1";
  const ativa = await (await ia("/api/ia/ativar", { id_token: "tk-helena", instalacao_id: "inst-0001-abcd" })).json();
  // O link de entrada que o Paulus pede ("edite no site", "Fazer upgrade"): abre a Minha conta ja com a sessao.
  const pedirLink = async (corpo, segredo) => {
    const req = new Request("https://paulus.ia.br/api/ia/minha-conta/link", { method: "POST", headers: { "content-type": "application/json", authorization: "Bearer " + segredo }, body: JSON.stringify(corpo) });
    const r = await atenderIA(req, env, new URL(req.url), { waitUntil: () => null }, deps);
    return { status: r.status, d: await r.json() };
  };
  const lk = await pedirLink({ aba: "cadastro" }, ativa.segredo);
  const codigoLink = ((lk.d.url || "").match(/\?entrar=([0-9a-f]{64})#cadastro$/) || [])[1];
  checar(lk.status === 200 && lk.d.url.startsWith("https://paulus.ia.br/minha-conta/?entrar=") && codigoLink, "o Paulus pede o link da Minha conta, na aba Cadastro", lk.d);
  checar((await pedirLink({ aba: "plano" }, "pia_" + "0".repeat(24) + "_" + "0".repeat(64))).status === 401, "sem o segredo da instalação: 401");
  const porLink = await conta("POST", "/api/conta/entrar", { link: codigoLink });
  const ckLink = cookieDe(porLink.r);
  const dLink = ckLink && (await conta("GET", "/api/conta", null, ckLink)).d;
  checar(porLink.status === 200 && porLink.d.papel === "titular" && dLink && !dLink.entrar, "o link abre a sessão do titular, sem pedir login", [porLink.status, porLink.d, dLink && Object.keys(dLink)]);
  checar((await conta("POST", "/api/conta/entrar", { link: codigoLink })).status === 410, "o link vale uma vez");
  // Uma sessao nova do titular.
  ck = cookieDe((await conta("POST", "/api/conta/entrar", { credential: "tk-helena" })).r);
  const d = (await conta("GET", "/api/conta", null, ck)).d;
  checar(d.escritorio && d.escritorio.slug === "moura" && d.escritorio.online, "o endereço do escritório, no ar", d.escritorio);
  checar(d.instalacoes.length === 1 && d.instalacoes[0].principal, "a instalação do túnel é a principal", d.instalacoes);
  checar((await conta("GET", "/api/conta/endereco/disponivel?slug=ocupado", null, ck)).d.disponivel === false, "endereço em uso: não");
  checar((await conta("GET", "/api/conta/endereco/disponivel?slug=moura-souza", null, ck)).d.disponivel === true, "endereço livre: sim");
  const troca = await conta("POST", "/api/conta/endereco", { slug: "moura-souza" }, ck);
  checar(troca.status === 200 && JSON.parse(await ESCRITORIOS.get("escritorio:moura-souza")).slug === "moura-souza" && !(await ESCRITORIOS.get("escritorio:moura")),
    "trocar o endereço move o registro do túnel", troca.d);
  const evs = [];
  for (const [k, v] of ESCRITORIOS.m) if (k.startsWith("evento:")) evs.push(JSON.parse(v));
  checar(evs.some((e) => e.evento === "alterado" && e.slug === "moura-souza" && e.de === "moura" && e.quem === "Minha conta (helena@moura.adv.br)"),
    "o registro de endereços do painel diz que foi pela Minha conta, e de quem", evs);
  const g = await conta("POST", "/api/conta/google/servico", { id: "gmail", ligado: true }, ck);
  const g2 = await conta("POST", "/api/conta/google/servico", { id: "agenda", ligado: true }, ck);
  const g3 = await conta("POST", "/api/conta/google/servico", { id: "gmail", ligado: false }, ck);
  checar(g.status === 200 && g3.d.ligados.length === 1 && g3.d.ligados[0] === "calendar.events" && (await resumoDe(helena)).google_pendente.ligados[0] === "calendar.events",
    "os serviços do Google viram a ordem para o PAULUS do escritório", g3.d);
  await conta("POST", "/api/conta/google/desvincular", {}, ck);
  checar((await resumoDe(helena)).google_pendente.ligados.length === 0, "desvincular: nenhum serviço fica");
  // As notas da conta, como o emissor grava.
  await APOIOS.put("nfse:nota:" + helena + ":nuvem-1", JSON.stringify({ id: "nuvem-1", conta: helena, numero: "41", competencia: "2026-10", valor: 1290 }));
  await APOIOS.put("nfse:nota-pdf:" + helena + ":nuvem-1", btoa("%PDF-1.4 nota"));
  await APOIOS.put("nfse:nota-xml:" + helena + ":nuvem-1", btoa("<NFSe/>"));
  const z = await conta("GET", "/api/conta/nfse.zip?ano=2026", null, ck);
  const bytes = new Uint8Array(await z.r.arrayBuffer());
  checar(z.status === 200 && bytes[0] === 0x50 && bytes[1] === 0x4b && new TextDecoder().decode(bytes).includes("NFS-e 41.pdf"), "as NFS-e do ano num .zip", bytes.length);
  checar((await conta("GET", "/api/conta/nfse/nuvem-1/xml", null, ck)).status === 200, "o XML de uma nota");
  checar((await conta("GET", "/api/conta/nfse.zip?ano=2019", null, ck)).status === 404, "ano sem notas: 404");
  const rm = await conta("POST", "/api/conta/instalacoes/inst-0001-abcd/remover", {}, ck);
  checar(rm.status === 200 && (await resumoDe(helena)).instalacoes_lista.length === 0, "tirar o computador apaga o segredo dele");
}

console.log("\no consumo de outro ciclo e o sair");
{
  const r = await resumoDe(helena);
  const ant = consumoDo(r, "anterior", relogio);
  checar(ant.dias.length >= 28 && ant.de < ant.ate, "o ciclo anterior, dia a dia", { de: ant.de, ate: ant.ate });
  const sai = await conta("POST", "/api/conta/sair", {}, ck);
  checar(/Max-Age=0/.test(sai.r.headers.get("set-cookie")) && (await conta("GET", "/api/conta", null, ck)).status === 401, "sair apaga a sessão");
}

console.log("\npelo Worker inteiro");
{
  const w = await worker.fetch(new Request("https://paulus.ia.br/api/conta"), env, { waitUntil: () => null });
  checar(w.status === 401, "/api/conta vai à Minha conta");
  const p = await worker.fetch(new Request("https://paulus.ia.br/minha-conta/"), env, { waitUntil: () => null });
  const csp = p.headers.get("content-security-policy") || "";
  checar(/script-src 'self';/.test(csp) && !/mercadopago/.test(csp), "a página tem a CSP dela: só scripts do site, nada do Mercado Pago", csp);
}

console.log("a conta cobrada pela Atos");
{
  // O dinheiro esta na Atos (worker/atos.js): a Minha conta do PAVLVS nao paga, troca nem cancela por aqui.
  donos["tk-atos"] = { sub: "pv-atos-mc", email: "atos@escritorio.adv.br" };
  const id = await idDe("pv-atos-mc");
  await CONTAS_IA.get(id).fetch("https://conta-ia/", { method: "POST", body: JSON.stringify({ acao: "atos_direito", id, dono: donos["tk-atos"],
    retrato: { versao: 1, plano: "escritorio", ate: new Date(relogio + 30 * DIA).toISOString(), periodo: "mes", assinatura: null } }) });
  const e = await conta("POST", "/api/conta/entrar", { credential: "tk-atos" });
  const ck = cookieDe(e.r);
  checar(e.status === 200 && ck, "a pessoa entra na Minha conta", e.d);
  let mpChamadas = 0;
  const original = deps.chamarMP;
  deps.chamarMP = async (...a) => { mpChamadas++; return original(...a); };
  for (const [caminho, corpo] of [["/api/conta/recarga", { pacote: "1" }], ["/api/conta/plano", { plano: "plus" }], ["/api/conta/cancelar", { motivo: "preco" }], ["/api/conta/cartao", { token: "x" }]]) {
    const r = await conta("POST", caminho, corpo, ck);
    checar(r.status === 409 && r.d.codigo === "cobranca_na_atos" && r.d.proximo === "https://atos.dev.br/conta/", caminho + ": 409, para a Atos", r.d);
  }
  const o = await conta("GET", "/api/conta/plano/orcar?plano=plus", null, ck);
  checar(o.status === 409 && o.d.codigo === "cobranca_na_atos", "orçar a troca: 409 também", o.status);
  checar(mpChamadas === 0, "e o Mercado Pago do PAVLVS não foi chamado", mpChamadas);
  deps.chamarMP = original;
  const g = await conta("GET", "/api/conta", null, ck);
  checar(g.status === 200, "a Minha conta continua abrindo (o consumo, as pessoas, o escritório)", g.status);

  // A situação é a do medidor, e o dinheiro é na Conta Atos.
  const ga = await conta("GET", "/api/conta", null, ck);
  checar(ga.d.assinatura.situacao === "ativa" && ga.d.atos.checkout.advogado.anual.startsWith("https://atos.dev.br/pavlvs/assinar/?preco=pavlvs.advogado.ano"),
    "a conta paga na Atos: ativa, com os links do checkout da Atos", ga.d.assinatura);
  // O caso de 10/10: o caminho antigo deixou a conta "ativa" sem pagamento (anotado direto no medidor).
  donos["tk-velho"] = { sub: "pv-velho-mc", email: "velho@escritorio.adv.br" };
  const idV = await idDe("pv-velho-mc");
  await CONTAS_IA.get(idV).fetch("https://conta-ia/", { method: "POST", body: JSON.stringify({ acao: "abrir", id: idV, dono: donos["tk-velho"] }) });
  const ov = objeto(idV);
  const velha = ov.dados.get("conta");
  Object.assign(velha, { plano: "escritorio", assinatura: { id: "pre-sem-pagamento", situacao: "authorized", valor: 1290 },
    ciclo: { inicio: new Date(relogio).toISOString(), fim: new Date(relogio + 30 * DIA).toISOString(), tokens: 60000000, usados: 0, origem: "assinatura" } });
  ov.dados.set("conta", velha);
  const ev = await conta("POST", "/api/conta/entrar", { credential: "tk-velho" });
  const gv = await conta("GET", "/api/conta", null, cookieDe(ev.r));
  checar(gv.status === 200 && gv.d.assinatura.situacao === "nenhuma", "a conta que o caminho antigo deixou 'ativa' sem pagar aparece sem assinatura", gv.d && gv.d.assinatura);
}

console.log(falhas ? "\n  Minha conta: " + falhas + " falha(s)" : "\n  Minha conta: todos os testes passaram");
process.exit(falhas ? 1 : 0);
