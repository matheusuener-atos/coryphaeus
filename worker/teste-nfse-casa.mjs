// Teste da ponte da NFS-e (worker/nfse-casa.js) e das notas do cliente
// (/api/ia/nfse em worker/ia.js), sem rede:
//   node worker/teste-nfse-casa.mjs
// Passa pelo Worker inteiro (index.js), para conferir tambem o roteamento:
// /api/nfse-casa/* nao passa pelo Access nem pela sessao do GitHub.
import worker from "./index.js";
import { ContaIA } from "./ia.js";
import { atenderAdmin } from "./admin.js";

let falhas = 0;
const checar = (ok, descricao, detalhe) => {
  console.log((ok ? "  ok   " : "  FALHA ") + descricao + (ok || detalhe === undefined ? "" : " -> " + JSON.stringify(detalhe)));
  if (!ok) falhas++;
};

const guardados = new Map();
const APOIOS = {
  get: async (k) => (guardados.has(k) ? guardados.get(k) : null),
  put: async (k, v) => { guardados.set(k, v); },
  delete: async (k) => { guardados.delete(k); },
  list: async ({ prefix }) => ({ list_complete: true, keys: [...guardados.keys()].filter((k) => k.startsWith(prefix)).map((name) => ({ name })) }),
};
let relogio = Date.parse("2026-10-03T15:00:00Z");
const objetos = new Map();
const CONTAS_IA = {
  idFromName: (n) => n,
  get: (n) => ({
    fetch: (url, init) => {
      if (!objetos.has(n)) {
        const dados = new Map();
        const o = new ContaIA({ storage: { get: async (k) => structuredClone(dados.get(k)), put: async (k, v) => { dados.set(k, structuredClone(v)); } } }, { APOIOS });
        o.agora = () => relogio;
        objetos.set(n, o);
      }
      return objetos.get(n).fetch(new Request(url, init));
    },
  }),
};
const TOKEN = "casa-" + "x".repeat(40);
const env = {
  IA_ATIVA: "1", CONTAS_IA, APOIOS, NFSE_CASA_TOKEN: TOKEN, DEEPINFRA_KEY: "k",
  GOOGLE_CLIENT_IDS: "cid",
  ASSETS: { fetch: async () => new Response("site", { status: 200 }) },
};
const ctx = { waitUntil() {} };

async function pedir(metodo, caminho, { token = TOKEN, corpo, envUsado = env } = {}) {
  const headers = { "content-type": "application/json" };
  if (token) headers.authorization = "Bearer " + token;
  const req = new Request("https://paulus.ia.br" + caminho, { method: metodo, headers, body: corpo ? JSON.stringify(corpo) : undefined });
  return worker.fetch(req, envUsado, ctx);
}

// As contas: ativadas pelo DO direto, com o cadastro do site.
async function doDe(id, acao, dados = {}) {
  const r = await CONTAS_IA.get(id).fetch("https://conta-ia/" + acao, { method: "POST", body: JSON.stringify({ acao, ...dados, numeros: { planos: [{ id: "escritorio", nome: "Escritório", valor: 300, tokens: 1000 }], recargas: [] } }) });
  return r.json();
}
const ID_ANA = "a".repeat(24);
const ID_BRUNO = "b".repeat(24);
for (const [id, nome] of [[ID_ANA, "ana"], [ID_BRUNO, "bruno"]]) {
  await doDe(id, "ativar", { id, dono: { sub: nome, email: nome + "@escritorio.com.br" }, nome: "Escritório " + nome, instalacao: "inst-" + nome + "-123", hash: "h-" + nome });
}
await doDe(ID_ANA, "cadastro", { cadastro: { nome_escritorio: "Ana Advocacia", documento: "52998224725", telefone: "91988887777", oab: "PA 12345", termos: "x" } });
// Os segredos de instalacao, para as rotas do cliente (o DO guarda o SHA-256).
const sha = async (t) => [...new Uint8Array(await crypto.subtle.digest("SHA-256", new TextEncoder().encode(t)))].map((b) => b.toString(16).padStart(2, "0")).join("");
const segredo = (id) => "pia_" + id + "_" + id.slice(0, 1).repeat(64);
for (const id of [ID_ANA, ID_BRUNO]) await doDe(id, "ativar", { id, dono: { sub: id === ID_ANA ? "ana" : "bruno", email: (id === ID_ANA ? "ana" : "bruno") + "@escritorio.com.br" }, instalacao: "inst-2-" + id.slice(0, 4), hash: await sha(segredo(id)) });
// Dois pagamentos confirmados (o que anotarPagamento grava).
guardados.set("admin:nfse:PAY1", JSON.stringify({ id: "PAY1", conta: ID_ANA, tipo: "mensalidade", valor: 300, quando: "2026-10-02T10:00:00Z", nota: "pendente" }));
guardados.set("admin:nfse:PAY2", JSON.stringify({ id: "PAY2", conta: ID_BRUNO, tipo: "recarga pix", valor: 50, quando: "2026-10-03T10:00:00Z", nota: "pendente" }));

// ------------------------------------------------------------ portas
console.log("portas");
let r = await pedir("GET", "/api/nfse-casa/ping", { envUsado: { ...env, NFSE_CASA_TOKEN: "" } });
let d = await r.json();
checar(r.status === 503 && d.erro.includes("NFSE_CASA_TOKEN"), "sem NFSE_CASA_TOKEN: 503 dizendo o que falta", d);
r = await pedir("GET", "/api/nfse-casa/ping", { token: "errado" });
checar(r.status === 401, "token errado: 401");
r = await pedir("GET", "/api/nfse-casa/ping", { token: "" });
checar(r.status === 401, "sem token: 401");
checar(!guardados.has("admin:nfse-casa:visto"), "chamada recusada nao conta como conexao");
r = await pedir("GET", "/api/nfse-casa/ping");
d = await r.json();
checar(r.status === 200 && d.ok && d.contas === 2 && d.hora, "ping: ok, hora e contas (sem Access nem GitHub)", d);
checar(Boolean(guardados.get("admin:nfse-casa:visto")), "a chamada valida grava admin:nfse-casa:visto");

// ------------------------------------------------------------ clientes
console.log("clientes");
r = await pedir("GET", "/api/nfse-casa/clientes");
d = await r.json();
const ana = d.clientes.find((c) => c.id === ID_ANA);
checar(d.clientes.length === 2 && ana.tomador.nome === "Ana Advocacia" && ana.tomador.documento === "52998224725" && ana.tomador.email === "ana@escritorio.com.br" && ana.oab === "PA 12345" && ana.tomador.telefone === "91988887777", "clientes: tomador vem do cadastro", ana);
r = await pedir("POST", "/api/nfse-casa/clientes/" + ID_ANA, { corpo: { tomador: { documento: "123" } } });
checar(r.status === 400 && (await r.json()).erro.includes("CPF ou CNPJ"), "documento com digito errado: 400");
r = await pedir("POST", "/api/nfse-casa/clientes/" + ID_ANA, { corpo: { tomador: { cep: "6600" } } });
checar(r.status === 400, "CEP curto: 400");
r = await pedir("POST", "/api/nfse-casa/clientes/" + ID_ANA, { corpo: { tomador: { cmun: "150140" } } });
checar(r.status === 400, "cMun com 6 digitos: 400");
r = await pedir("POST", "/api/nfse-casa/clientes/" + ID_ANA, { corpo: { tomador: { uf: "XX" } } });
checar(r.status === 400, "UF inexistente: 400");
r = await pedir("POST", "/api/nfse-casa/clientes/" + ID_ANA, { corpo: { tomador: { email: "sem-arroba" } } });
checar(r.status === 400, "e-mail sem @: 400");
r = await pedir("POST", "/api/nfse-casa/clientes/" + "c".repeat(24), { corpo: { tomador: { uf: "PA" } } });
checar(r.status === 404, "conta inexistente: 404");
r = await pedir("POST", "/api/nfse-casa/clientes/" + ID_ANA, { corpo: { tomador: { documento: "11.222.333/0001-81", nome: "  Ana   Advocacia\u0000 S/S  ", cep: "66.010-000", cmun: "1501402", uf: "pa", logradouro: "Av. Presidente Vargas", numero: "100", bairro: "Campina" } } });
d = await r.json();
checar(r.status === 200 && d.tomador.documento === "11222333000181" && d.tomador.nome === "Ana Advocacia S/S" && d.tomador.cep === "66010000" && d.tomador.uf === "PA" && d.tomador.email === "ana@escritorio.com.br", "override gravado, limpo, e funde com o cadastro", d.tomador);
const cadastroDepois = await doDe(ID_ANA, "ler_cadastro");
checar(cadastroDepois.cadastro.documento === "52998224725", "o cadastro original da conta nao muda");
r = await pedir("GET", "/api/nfse-casa/clientes");
d = await r.json();
checar(d.clientes.find((c) => c.id === ID_ANA).tomador.cmun === "1501402" && d.clientes.find((c) => c.id === ID_ANA).tomador.documento === "11222333000181", "clientes: o override vence o cadastro");

// ------------------------------------------------------------ pagamentos e notas
console.log("notas");
r = await pedir("GET", "/api/nfse-casa/pagamentos");
d = await r.json();
checar(d.pagamentos.length === 2 && d.pagamentos[0].id === "PAY2" && d.pagamentos[1].cliente === "Ana Advocacia" && d.pagamentos[1].nota === "pendente", "pagamentos: mais novos primeiro, com o cliente", d);
const pdf = Buffer.from("%PDF-1.4 nota da Ana").toString("base64");
const xml = Buffer.from("<NFSe><nNFSe>42</nNFSe></NFSe>").toString("base64");
const nota = { id: "n-1", conta: ID_ANA, pagamento: "PAY1", numero: "42", chave: "1501402" + "9".repeat(43), competencia: "2026-10", valor: 300, descricao: "Licença do PAVLVS - outubro", ambiente: "producao_restrita", emitida_em: "2026-10-03T12:00:00Z", pdf_b64: pdf, xml_b64: xml };
r = await pedir("POST", "/api/nfse-casa/notas", { corpo: { ...nota, competencia: "10/2026" } });
checar(r.status === 400, "competencia fora de AAAA-MM: 400");
r = await pedir("POST", "/api/nfse-casa/notas", { corpo: { ...nota, pdf_b64: Buffer.alloc(2 * 1024 * 1024 + 10).toString("base64") } });
checar(r.status === 413, "arquivo acima de 2 MB: 413");
r = await pedir("POST", "/api/nfse-casa/notas", { corpo: nota });
d = await r.json();
checar(r.status === 200 && d.ok, "nota recebida", d);
const pag = JSON.parse(guardados.get("admin:nfse:PAY1"));
checar(pag.nota === "emitida" && pag.numero === "42", "o pagamento fica marcado emitida com o numero", pag);
r = await pedir("POST", "/api/nfse-casa/notas", { corpo: { ...nota, numero: "43" } });
checar(JSON.parse(guardados.get("nfse:nota:" + ID_ANA + ":n-1")).numero === "43" && [...guardados.keys()].filter((k) => k.startsWith("nfse:nota:")).length === 1, "reenviar o mesmo id substitui");

// ------------------------------------------------------------ o cliente
console.log("cliente");
async function cliente(caminho, id) {
  const req = new Request("https://paulus.ia.br" + caminho, { headers: { authorization: "Bearer " + segredo(id) } });
  return worker.fetch(req, env, ctx);
}
r = await cliente("/api/ia/nfse", ID_ANA);
d = await r.json();
checar(r.status === 200 && d.notas.length === 1 && d.notas[0].numero === "43" && d.notas[0].competencia === "2026-10" && d.notas[0].ambiente === "producao_restrita" && !d.notas[0].cancelada && !("pdf_b64" in d.notas[0]), "a Ana ve a nota dela (sem os arquivos)", d);
r = await cliente("/api/ia/nfse", ID_BRUNO);
d = await r.json();
checar(r.status === 200 && d.notas.length === 0, "o Bruno nao ve a nota da Ana");
r = await cliente("/api/ia/nfse/n-1/pdf", ID_BRUNO);
checar(r.status === 404, "o Bruno nao baixa o PDF da Ana");
r = await cliente("/api/ia/nfse/n-1/pdf", ID_ANA);
const bytes = Buffer.from(await r.arrayBuffer()).toString();
checar(r.status === 200 && r.headers.get("content-type") === "application/pdf" && bytes === "%PDF-1.4 nota da Ana" && r.headers.get("content-disposition").includes("NFS-e 43.pdf"), "a Ana baixa o PDF", { status: r.status, bytes });
r = await cliente("/api/ia/nfse/n-1/xml", ID_ANA);
checar(r.status === 200 && r.headers.get("content-type") === "application/xml" && (await r.text()).includes("<nNFSe>42"), "e o XML");
r = await cliente("/api/ia/nfse/nao-existe/xml", ID_ANA);
checar(r.status === 404, "nota inexistente: 404");
r = await worker.fetch(new Request("https://paulus.ia.br/api/ia/nfse"), env, ctx);
checar(r.status === 401, "sem o segredo da instalacao: 401");

// cancelada
r = await pedir("POST", "/api/nfse-casa/notas/n-1/cancelada", { corpo: { conta: ID_BRUNO } });
checar(r.status === 404, "cancelar com a conta errada: 404");
r = await pedir("POST", "/api/nfse-casa/notas/n-1/cancelada", { corpo: { conta: ID_ANA } });
checar(r.status === 200, "cancelar a nota");
d = await (await cliente("/api/ia/nfse", ID_ANA)).json();
checar(d.notas[0].cancelada === true && JSON.parse(guardados.get("admin:nfse:PAY1")).nota === "cancelada", "o cliente ve a nota cancelada e o pagamento tambem", d);

// ------------------------------------------------------------ o painel
console.log("painel");
const reqSessao = new Request("https://paulus.ia.br/api/admin/sessao");
r = await atenderAdmin(reqSessao, env, new URL(reqSessao.url), ctx, { chavesDoAccess: async () => [] });
d = await r.json();
checar(d.config.nfse.ligado === true, "com NFSE_CASA_TOKEN, a NFS-e aparece ligada no painel", d.config.nfse);
r = await atenderAdmin(reqSessao, { ...env, NFSE_CASA_TOKEN: "" }, new URL(reqSessao.url), ctx, { chavesDoAccess: async () => [] });
d = await r.json();
checar(d.config.nfse.ligado === false && d.config.nfse.falta.includes("NFSE_CASA_TOKEN"), "sem o token, diz que a ponte esta desligada", d.config.nfse);

console.log(falhas ? `\n  ${falhas} falha(s)` : "\n  ponte da NFS-e: todos os testes passaram");
process.exit(falhas ? 1 : 0);
