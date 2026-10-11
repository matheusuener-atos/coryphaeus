// Teste do painel admin (worker/admin.js), sem rede:
//   node worker/teste-admin.mjs
// O painel mora na Atos (atos.dev.br/admin): os pedidos chegam assinados por ela (PAINEL_SEGREDO_PAVLVS), e a
// assinatura e feita aqui pelo contrato (worker/admin-api.md). O GitHub (a reversao), o Resend, o Mercado Pago
// e a API da Cloudflare (tuneis) sao de mentira; o Durable Object roda aqui sobre um Map.
import { atenderAdmin, comPlanosDoPainel, ehRotaDoAdmin, enviarCampanhas, htmlDoEmail } from "./admin.js";
import { atenderIA, ContaIA } from "./ia.js";
import { atenderTunel, limparEscritorios, provisionar } from "./tunel.js";

let falhas = 0;
const checar = (ok, descricao, detalhe) => {
  console.log((ok ? "  ok   " : "  FALHA ") + descricao + (ok || detalhe === undefined ? "" : " -> " + JSON.stringify(detalhe)));
  if (!ok) falhas++;
};

// ------------------------------------------------------------ o KV
const guardados = new Map();
const kv = () => ({
  get: async (k) => guardados.get(k) || null,
  put: async (k, v) => { guardados.set(k, v); },
  delete: async (k) => { guardados.delete(k); },
  list: async ({ prefix }) => ({ list_complete: true, keys: [...guardados.keys()].filter((k) => k.startsWith(prefix)).map((name) => ({ name })) }),
});
const APOIOS = kv();

// ------------------------------------------------ o Durable Object aqui
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

// ------------------------------------- Resend, Mercado Pago e a Cloudflare
const emails = [];
const mp = [];
// A API da Cloudflare: os tuneis e o DNS (worker/tunel.js).
const cf = { tuneis: new Map(), dns: new Map(), chamadas: [], seq: 0, recusar: "" };
const respCF = (result, ok = true, status = ok ? 200 : 400, msg = "falha de mentira") =>
  new Response(JSON.stringify({ success: ok, errors: ok ? [] : [{ message: msg }], result }), { status });
globalThis.fetch = async (url, init = {}) => {
  const u = String(url);
  if (u === "https://api.resend.com/emails") {
    emails.push(JSON.parse(init.body));
    return new Response(JSON.stringify({ id: "e" + emails.length }), { status: 200 });
  }
  if (u.startsWith("https://api.cloudflare.com/client/v4/")) {
    const caminho = u.slice("https://api.cloudflare.com/client/v4".length);
    const metodo = (init.method || "GET").toUpperCase();
    const corpo = init.body ? JSON.parse(init.body) : null;
    cf.chamadas.push({ metodo, caminho, corpo, auth: (init.headers || {}).Authorization });
    if (cf.recusar && caminho.includes(cf.recusar)) return respCF(null, false);
    let m;
    if (metodo === "POST" && /\/cfd_tunnel$/.test(caminho)) { const id = "tun-" + ++cf.seq; cf.tuneis.set(id, { status: "inactive" }); return respCF({ id }); }
    if (metodo === "PUT" && /\/cfd_tunnel\/[^/]+\/configurations$/.test(caminho)) return respCF({});
    if (metodo === "GET" && (m = caminho.match(/\/cfd_tunnel\/([^/]+)\/token$/))) return respCF("token-" + m[1]);
    if (metodo === "GET" && (m = caminho.match(/\/cfd_tunnel\/([^/]+)$/))) return cf.tuneis.has(m[1]) ? respCF({ id: m[1], status: cf.tuneis.get(m[1]).status }) : respCF(null, false);
    if (metodo === "DELETE" && /\/cfd_tunnel\/[^/]+(\/connections)?$/.test(caminho)) return respCF({});
    if (metodo === "POST" && /\/dns_records$/.test(caminho)) { const id = "dns-" + ++cf.seq; cf.dns.set(id, corpo); return respCF({ id }); }
    if ((metodo === "PUT" || metodo === "DELETE") && /\/dns_records\/[^/]+$/.test(caminho)) return respCF({});
    return respCF(null, false);
  }
  return new Response("{}", { status: 404 });
};
// O Mercado Pago de mentira: so anota. A cobranca e da Atos; o painel nao chama mais o Mercado Pago.
async function chamarMP(env, caminho, metodo, corpo, extra = {}) {
  mp.push({ caminho, metodo, corpo, extra });
  return { ok: true, status: 200, dados: {} };
}

// A conta com o plano pago na Atos (worker/atos.js -> ContaIA "atos_direito"): o unico caminho, alem da cortesia.
const versaoNaAtos = new Map();
async function naAtos(id, plano, assinatura = null, dias = 30) {
  const versao = (versaoNaAtos.get(id) || 0) + 1;
  versaoNaAtos.set(id, versao);
  const r = await CONTAS_IA.get(id).fetch("https://conta-ia/", { method: "POST", body: JSON.stringify({ acao: "atos_direito", id,
    retrato: { versao, plano, ate: new Date(relogio + dias * 864e5).toISOString(), periodo: "mes", assinatura } }) });
  return r.json();
}

// ------------------------------------------------ a Atos de mentira
// O painel mora na Atos: ela encaminha /api/admin/pavlvs/* com quem pede assinado (HMAC-SHA256 com
// PAINEL_SEGREDO_PAVLVS). Aqui a assinatura e feita a parte, pelo contrato (worker/admin-api.md), sem usar o
// codigo da Atos nem o do PAVLVS.
const SEGREDO = "segredo-do-painel-de-teste";
const EQUIPE = { "dono@paulus.ia.br": { nome: "Matheus", papel: "dono" }, "suporte@paulus.ia.br": { nome: "Ana", papel: "suporte" } };
const GH_TOKEN = { login: "matheus", token: "gho_x" };
const hexDe = (b) => [...new Uint8Array(b)].map((x) => x.toString(16).padStart(2, "0")).join("");
async function assinar(segredo, metodo, caminho, corpo, quem64, ts) {
  const k = await crypto.subtle.importKey("raw", new TextEncoder().encode(segredo), { name: "HMAC", hash: "SHA-256" }, false, ["sign"]);
  const resumo = hexDe(await crypto.subtle.digest("SHA-256", corpo));
  return "t=" + ts + ",v1=" + hexDe(await crypto.subtle.sign("HMAC", k, new TextEncoder().encode([ts, metodo, caminho, resumo, quem64].join("."))));
}

// ------------------------------------------------ o GitHub de mentira
let permissao = "write";
// A reversao de um commit antigo (a publicacao de um material, antes de 07/10):
// o commit abc1234 criou peca.md e mudou materiais.json; a main esta em cabeca000.
const GH = "https://api.github.com/repos/matheusuener-atos/coryphaeus";
const ghReversao = { conflito: false, chamadas: [] };
async function github(metodo, url, token, corpo) {
  if (url.includes("/login/oauth/access_token")) return { ok: true, status: 200, dados: corpo.code === "bom" ? { access_token: "gho_x" } : {} };
  if (url.endsWith("/user")) return { ok: true, status: 200, dados: { login: "matheus" } };
  if (url.includes("/collaborators/")) return { ok: true, status: 200, dados: { permission: permissao } };
  if (url.startsWith(GH + "/git/") || url.startsWith(GH + "/commits/") || url.startsWith(GH + "/contents/")) ghReversao.chamadas.push({ metodo, url, corpo, token });
  if (url === GH + "/git/ref/heads/main") return { ok: true, status: 200, dados: { object: { sha: "cabeca000" } } };
  if (url === GH + "/git/commits/cabeca000") return { ok: true, status: 200, dados: { tree: { sha: "arvore000" } } };
  if (url === GH + "/commits/abc1234") {
    return { ok: true, status: 200, dados: { sha: "abc1234ffff", parents: [{ sha: "pai000" }], files: [
      { filename: "site/materiais/peca.md", status: "added", sha: "blobMd" }, { filename: "site/dados/materiais.json", status: "modified", sha: "blobJson2" }] } };
  }
  if (url === GH + "/contents/site/dados/materiais.json?ref=pai000") return { ok: true, status: 200, dados: { sha: "blobJson1" } };
  if (url === GH + "/contents/site/materiais/peca.md?ref=cabeca000") return { ok: true, status: 200, dados: { sha: "blobMd" } };
  if (url === GH + "/contents/site/dados/materiais.json?ref=cabeca000") return { ok: true, status: 200, dados: { sha: ghReversao.conflito ? "blobJson3" : "blobJson2" } };
  if (metodo === "POST" && url === GH + "/git/trees") return { ok: true, status: 201, dados: { sha: "arvore001" } };
  if (metodo === "POST" && url === GH + "/git/commits") return { ok: true, status: 201, dados: { sha: "reverte0001112223334445556667778889990000" } };
  if (metodo === "PATCH" && url === GH + "/git/refs/heads/main") return { ok: true, status: 200, dados: {} };
  return { ok: false, status: 404, dados: null };
}

const env = {
  IA_ATIVA: "1", CONTAS_IA, APOIOS, PAINEL_SEGREDO_PAVLVS: SEGREDO, RESEND_API_KEY: "re_x", MP_ACCESS_TOKEN: "mp",
  IA_PLANO_TOKENS: "10000", IA_RECARGA_TOKENS: "5000",
  ASSETS: { fetch: async () => new Response(JSON.stringify({ versao: "0.9.22" }), { status: 200 }) },
};
const deps = { github, chamarMP, agora: () => relogio };

/* Um pedido ao painel como a Atos encaminha. `caminho` no formato de sempre (/api/admin/x): vira
   /api/admin/pavlvs/x. `cookie` diz se o GitHub esta ligado na sessao da Atos: "gh" (ligado) ou "sem-gh".
   semAtos: sem assinatura nenhuma (um pedido direto da internet). `adulterar(cabecalhos)` mexe no pedido
   depois de assinado. `cru`: o caminho vai como esta (sem o pavlvs/). */
async function admin(metodo, caminho, { email = "dono@paulus.ia.br", corpo, cookie = "", semAtos = false, envUsado = env, papel, nome, segredo = SEGREDO, ts, adulterar, cru = false } = {}) {
  const final = cru || !caminho.startsWith("/api/admin/") ? caminho : "/api/admin/pavlvs/" + caminho.slice("/api/admin/".length);
  const bytes = corpo === undefined ? new Uint8Array(0) : new TextEncoder().encode(typeof corpo === "string" ? corpo : JSON.stringify(corpo));
  const headers = { "content-type": "application/json" };
  if (!semAtos && final.startsWith("/api/admin/")) {
    const m = EQUIPE[email] || {};
    const quem = { email, nome: nome ?? m.nome ?? "", papel: papel ?? m.papel ?? "suporte", github: cookie === "gh" ? GH_TOKEN : null };
    const quem64 = Buffer.from(JSON.stringify(quem)).toString("base64url");
    const u = new URL("https://paulus.ia.br" + final);
    headers["Atos-Painel-Quem"] = quem64;
    headers["Atos-Painel-Assinatura"] = await assinar(segredo, metodo, u.pathname + u.search, bytes, quem64, ts ?? Math.floor(relogio / 1000));
  }
  if (adulterar) adulterar(headers);
  const req = new Request("https://paulus.ia.br" + final, { method: metodo, headers, body: metodo === "GET" || metodo === "HEAD" ? undefined : adulterar && adulterar.corpo ? adulterar.corpo : bytes });
  return atenderAdmin(req, envUsado, new URL(req.url), { waitUntil() {} }, deps);
}

// ------------------------------------------------------------ as portas
console.log("portas (o pedido assinado pela Atos)");
let r = await admin("GET", "/api/admin/visao", { semAtos: true });
let d = await r.json();
checar(r.status === 401 && !JSON.stringify(d).includes("PAINEL_SEGREDO"), "sem a assinatura da Atos (direto da internet): 401", d);
r = await admin("GET", "/api/admin/visao", { cru: true });
checar(r.status === 404, "o caminho antigo (/api/admin/* sem pavlvs/) não existe mais: 404");
r = await admin("GET", "/api/admin/sessao", { cru: true, semAtos: true });
checar(r.status === 404, "nem a sessão antiga");
r = await admin("GET", "/api/admin/visao", { envUsado: { ...env, PAINEL_SEGREDO_PAVLVS: "" } });
d = await r.json();
checar(r.status === 503 && !d.erro.includes("PAINEL_SEGREDO"), "sem o segredo configurado o painel fica fechado (503, sem o nome do segredo)", d);
r = await admin("GET", "/api/admin/visao", { segredo: "outro-segredo" });
checar(r.status === 401, "assinado com outro segredo: 401");
r = await admin("GET", "/api/admin/visao", { ts: Math.floor(relogio / 1000) - 61 });
checar(r.status === 401, "assinatura de mais de 60 s atrás: 401 (não dá para repetir um pedido velho)");
r = await admin("GET", "/api/admin/visao", { ts: Math.floor(relogio / 1000) + 61 });
checar(r.status === 401, "e do futuro também");
r = await admin("GET", "/api/admin/visao", { ts: Math.floor(relogio / 1000) - 50 });
checar(r.status === 200, "dentro da janela: abre");
r = await admin("GET", "/api/admin/visao", { adulterar: (h) => { h["Atos-Painel-Quem"] = Buffer.from(JSON.stringify({ email: "dono@paulus.ia.br", papel: "dono", github: null })).toString("base64url"); }, papel: "suporte" });
checar(r.status === 401, "trocar quem pede depois de assinado (o suporte se dizendo dono): 401");
const corpoAssinado = JSON.stringify({ tipo: "conta.creditar", dados: { id: "a".repeat(24), tokens: 5 } });
const trocaCorpo = (h) => {};
trocaCorpo.corpo = new TextEncoder().encode(JSON.stringify({ tipo: "conta.creditar", dados: { id: "a".repeat(24), tokens: 5000000 } }));
r = await admin("POST", "/api/admin/alteracoes", { corpo: corpoAssinado, adulterar: trocaCorpo });
checar(r.status === 401, "trocar o corpo depois de assinado: 401");
r = await admin("GET", "/api/admin/tokens?visao=conta", { adulterar: (h) => {} });
checar(r.status === 200, "a query faz parte do que é assinado (e confere)");
r = await admin("GET", "/api/admin/visao", { papel: "rei" });
checar(r.status === 401, "papel que não existe: 401");
r = await admin("GET", "/api/admin/visao", { email: "sem-arroba" });
checar(r.status === 401, "e-mail que não serve: 401");
const semGitHub = "sem-gh";
r = await admin("GET", "/api/admin/sessao", { cookie: semGitHub });
d = await r.json();
checar(r.status === 200 && d.pronto && d.access.ok && d.access.email === "dono@paulus.ia.br" && !d.github.ok && d.papel === "dono" && d.nome === "Matheus" && d.worker === "0.9.22"
  && !("nfse" in d.config) && !("access" in d.config) && !("equipe" in d.config) && d.config.tuneis.ligado === false, "a sessão: quem a Atos assinou, sem o GitHub, e o que falta configurar aqui", d);
r = await admin("GET", "/api/admin/visao", { cookie: semGitHub });
checar(r.status === 200, "sem o GitHub, o painel abre");
r = await admin("POST", "/api/admin/publicar", { cookie: semGitHub, corpo: { confirmacao: "comitar e pushar" } });
d = await r.json();
checar(r.status === 403 && d.passo === "github" && d.erro.includes("comitar e pushar"), "comitar e pushar sem o GitHub: 403 passo github", d);
r = await admin("POST", "/api/admin/retroagir", { cookie: semGitHub, corpo: { commit: "abc1234", confirmacao: "retroagir" } });
d = await r.json();
checar(r.status === 403 && d.passo === "github" && d.erro.includes("retroagir"), "retroagir sem o GitHub: 403 passo github", d);
for (const rota of ["/api/admin/github/entrar", "/api/admin/github/retorno?code=bom&state=x", "/api/admin/equipe"]) {
  r = await admin("GET", rota, { cookie: "gh" });
  checar(r.status === 404, "GET " + rota.split("?")[0] + " saiu do PAVLVS (é da Atos): 404");
}
for (const rota of ["/api/admin/sair", "/api/admin/sessoes/encerrar"]) {
  r = await admin("POST", rota, { cookie: "gh" });
  checar(r.status === 404, "POST " + rota + " saiu (a sessão é a da Conta Atos): 404");
}
const sessao = "gh";
r = await admin("GET", "/api/admin/sessao", { cookie: sessao });
d = await r.json();
checar(d.github.ok && d.github.login === "matheus", "com o GitHub ligado na Atos, a sessão diz o login", d.github);
r = await admin("GET", "/api/admin/papeis", { cookie: sessao, email: "suporte@paulus.ia.br" });
d = await r.json();
checar(r.status === 200 && d.matriz.length >= 6 && d.matriz.some((x) => x.acao === "Creditar tokens" && x.dono && x.financeiro && !x.suporte) && !d.matriz.some((x) => /nota|equipe/i.test(x.acao)),
  "a matriz do PAVLVS (sem notas fiscais nem equipe, que são da Atos)", d.matriz);
const como = (extra = {}) => ({ cookie: sessao, ...extra });

// ------------------------------------------------------------ as contas
console.log("contas");
const iaCtx = { waitUntil() {} };
async function ia(caminho, corpo) {
  const req = new Request("https://paulus.ia.br" + caminho, { method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify(corpo) });
  return atenderIA(req, env, new URL(req.url), iaCtx, { chamarMP, donoDoToken: async (e, t) => ({ sub: t, email: t + "@escritorio.com.br" }) });
}
const segredos = {};
for (const quem of ["ana", "bruno"]) {
  const x = await (await ia("/api/ia/ativar", { id_token: quem, instalacao_id: "inst-" + quem + "-123", nome_escritorio: "Escritório " + quem })).json();
  segredos[quem] = x.segredo;
}
const idAna = segredos.ana.split("_")[1];
const idBruno = segredos.bruno.split("_")[1];
checar(guardados.has("admin:conta:" + idAna) && guardados.has("admin:conta:" + idBruno), "cada conta se anota no indice do painel");
// Um pagamento de antes da Atos que o medidor ainda guarda: o painel le, e nada novo grava pagamentos.
await mexerNaConta(idAna, (x) => { x.pagamentos = [{ tipo: "recarga", ref: "ORD1", valor: 50, quando: new Date(relogio).toISOString() }]; });
r = await admin("GET", "/api/admin/contas", como());
d = await r.json();
checar(d.contas.length === 2 && d.contas.every((c) => c.email.endsWith("@escritorio.com.br") && !c._d), "lista as contas da nuvem (sem o detalhe cru)", d.contas);
r = await admin("GET", "/api/admin/contas/" + idAna, como());
d = await r.json();
checar(d.pagamentos.length === 1 && d.pagamentos[0].valor === 50 && d.instalacoes.length === 1 && d.instalacoes[0].hash8.length === 8, "detalhe da conta: pagamentos e instalacoes", d);
checar(!("forma" in d.pagamentos[0]) && !("pendentes" in d) && !("plano_proximo" in d) && !mp.length, "a ficha não pergunta nada ao Mercado Pago (sem a forma, os pendentes e a troca marcada)", d.pagamentos[0]);
const hash8 = d.instalacoes[0].hash8;
r = await admin("GET", "/api/admin/visao", como());
d = await r.json();
checar(d.kpi.contas === 2 && d.kpi.receita_recargas === 50 && d.dias.length === 42, "visao geral: contas, receita do mes e 14 dias x 3 turnos", d.kpi);
checar(!("avisos" in d), "a visão geral não tem mais os avisos do Mercado Pago do PAVLVS");
r = await admin("GET", "/api/admin/busca?q=bruno", como());
d = await r.json();
checar(d.contas.length === 1 && d.contas[0].alvo === idBruno, "busca acha a conta pelo nome");
r = await admin("GET", "/api/admin/tokens?visao=conta&periodo=mes", como());
d = await r.json();
checar(d.linhas.length === 2 && d.kpis.receita === 50, "tokens por conta com a receita", d.kpis);

// ------------------------------------------------------------ a fila
console.log("fila");
r = await admin("POST", "/api/admin/alteracoes", como({ corpo: { tela: "contas", tipo: "conta.creditar", alvo: idBruno, dados: { id: idBruno, tokens: 1000 }, texto: "Creditei 1.000 tokens ao Bruno" } }));
checar(r.status === 200 && (await r.json()).pendentes.length === 1, "creditar entra na fila, nao acontece na hora");
let resumoBruno = await (await CONTAS_IA.get(idBruno).fetch("https://conta-ia/resumo", { method: "POST", body: JSON.stringify({ acao: "resumo" }) })).json();
checar(!resumoBruno.recargas.length, "antes de publicar, a conta nao mudou");
r = await admin("POST", "/api/admin/alteracoes", como({ corpo: { tipo: "conta.instalacao.apagar", dados: { id: idAna, hash8 }, texto: "Desvinculei a instalação da Ana" } }));
r = await admin("POST", "/api/admin/alteracoes", como({ corpo: { tipo: "plano.editar", dados: { id: "escritorio", valor: 320, valor_anual: 3200, tokens: 32 }, texto: "Escritório a R$ 320" } }));
r = await admin("POST", "/api/admin/alteracoes", como({ corpo: { tipo: "coisa.estranha", dados: {} } }));
checar(r.status === 400, "tipo desconhecido e recusado");
r = await admin("POST", "/api/admin/alteracoes", como({ corpo: { tipo: "cupom.criar", dados: { codigo: "PILOTO30", desconto: 30, meses: 3 } } }));
checar(r.status === 400, "o cupom saiu do sistema: criar cupom e alteracao desconhecida");
checar((await admin("GET", "/api/admin/cupons", como())).status === 404, "e a tela de cupons nao tem mais rota");
r = await admin("POST", "/api/admin/publicar", como({ corpo: { confirmacao: "commitar e pushar" } }));
checar(r.status === 400, "publicar com a frase errada nao publica");
r = await admin("POST", "/api/admin/publicar", como({ corpo: { confirmacao: "comitar e pushar" } }));
d = await r.json();
checar(d.ok && d.resultados.length === 3 && d.publicacao.n === 3, "publicar aplica as tres", d);
resumoBruno = await (await CONTAS_IA.get(idBruno).fetch("https://conta-ia/resumo", { method: "POST", body: JSON.stringify({ acao: "resumo" }) })).json();
checar(resumoBruno.recargas.length === 1 && resumoBruno.recargas[0].tokens === 1000, "depois de publicar, os tokens estao na conta");
const resumoAna = await (await CONTAS_IA.get(idAna).fetch("https://conta-ia/resumo", { method: "POST", body: JSON.stringify({ acao: "resumo" }) })).json();
checar(resumoAna.instalacoes === 0, "a instalacao da Ana saiu");
r = await (await fetch("https://nada")).status; // so para nao ficar fetch pendurado
const planosKV = JSON.parse(guardados.get("admin:planos"));
checar(planosKV.find((p) => p.id === "escritorio").valor === 320 && planosKV.find((p) => p.id === "escritorio").valor_anual === 3200 && planosKV.find((p) => p.id === "escritorio").tokens === 32e6, "plano editado no KV, com o valor do ano", planosKV);
r = await admin("GET", "/api/admin/alteracoes", como());
d = await r.json();
checar(!d.pendentes.length && d.publicacoes.length === 1, "fila vazia e a publicacao no historico");

// papel (o suporte com o GitHub ligado na Atos)
const sessaoSuporte = "gh";
r = await admin("POST", "/api/admin/alteracoes", { email: "suporte@paulus.ia.br", cookie: sessaoSuporte, corpo: { tipo: "conta.creditar", dados: { id: idAna, tokens: 5 } } });
checar(r.status === 403, "suporte nao credita tokens");
r = await admin("POST", "/api/admin/alteracoes", { email: "suporte@paulus.ia.br", cookie: sessaoSuporte, corpo: { tipo: "plano.editar", dados: { id: "escritorio", valor: 1, valor_anual: 10, tokens: 1 } } });
checar(r.status === 403, "suporte nao mexe nos planos");

// --------------------------------------------------------- e-mail e campanhas
console.log("e-mail");
r = await admin("POST", "/api/admin/campanhas/teste", como({ corpo: { campanha: { assunto: "Olá {nome}", titulo: "Novidade", texto: "Oi {nome}, tudo bem?" } } }));
checar(r.status === 200 && emails.length === 1 && emails[0].to[0] === "dono@paulus.ia.br" && !emails[0].subject.startsWith("[teste]"), "e-mail de teste vai para quem esta na sessao", emails[0]);
r = await admin("POST", "/api/admin/campanhas/teste", { ...como(), envUsado: { ...env, RESEND_API_KEY: "" }, corpo: { campanha: { assunto: "x", texto: "y" } } });
checar(r.status === 503 && (await r.json()).erro.includes("RESEND_API_KEY"), "sem o provedor de e-mail: 503 dizendo o que falta");
r = await admin("POST", "/api/admin/alteracoes", como({ corpo: { tipo: "campanha.disparar", dados: { nome: "Boas-vindas", publico: "todos", assunto: "Bem-vindo, {nome}", texto: "O PAULUS chegou.", botao: "Abrir", link: "https://paulus.ia.br/", quando: "agora" }, texto: "Disparei Boas-vindas" } }));
r = await admin("POST", "/api/admin/publicar", como({ corpo: { confirmacao: "comitar e pushar" } }));
checar((await r.json()).ok, "a campanha entra na fila de envio");
emails.length = 0;
const enviados = await enviarCampanhas(env, relogio);
checar(enviados.enviados === 2 && emails.length === 2 && emails.every((e) => e.html.includes("/api/e/")), "o Cron manda a leva com pixel e link rastreados", enviados);
const idCamp = [...guardados.keys()].find((k) => k.startsWith("admin:campanha:")).split(":")[2];
const campanha = JSON.parse(guardados.get("admin:campanha:" + idCamp));
checar(campanha.situacao === "enviada" && campanha.destinatarios.every((x) => !x.email), "terminado o envio, os e-mails saem do KV", campanha);
checar(JSON.parse(guardados.get("admin:campanhas:fila")).length === 0, "e a campanha sai do indice do Cron");
const t = campanha.destinatarios[0].t;
const ab = await admin("GET", "/api/e/" + idCamp + "/" + t + "/a.gif", { semAtos: true });
await admin("GET", "/api/e/" + idCamp + "/" + t + "/a.gif", { semAtos: true });
const cl = await admin("GET", "/api/e/" + idCamp + "/" + t + "/c", { semAtos: true });
const depois = JSON.parse(guardados.get("admin:campanha:" + idCamp));
checar(ab.headers.get("content-type") === "image/gif" && cl.status === 302 && cl.headers.get("location") === "https://paulus.ia.br/" && depois.abertos === 1 && depois.cliques === 1, "abertura conta uma vez; clique redireciona", depois);
checar(htmlDoEmail({ titulo: "<b>", texto: "a\n\nb" }).includes("&lt;b&gt;"), "o HTML do e-mail escapa o texto");

// --------------------------------------------------------- renovacoes
console.log("renovacoes");
await naAtos(idBruno, "escritorio", { id: "atos-b1", status: "authorized" });
relogio += 40 * 24 * 3600 * 1000;
r = await admin("GET", "/api/admin/renovacoes", como());
d = await r.json();
checar(d.abertas.length === 1 && d.abertas[0].id === idBruno && d.abertas[0].dias_vencido >= 1 && d.abertas[0].motivo.includes("da Atos") && !("oferta" in d.abertas[0]),
  "ciclo vencido da conta cobrada pela Atos aparece em nao renovacoes, com o motivo da Atos", d);
emails.length = 0;
r = await admin("POST", "/api/admin/renovacoes/" + idBruno + "/lembrete", como());
d = await r.json();
checar(emails.length === 1 && emails[0].to[0] === "bruno@escritorio.com.br" && d.abertas[0].lembrete_em && emails[0].text.includes("atos.dev.br/conta") && !emails[0].text.includes("Mercado Pago"),
  "lembrete enviado (para a Conta Atos) e anotado", emails[0] && emails[0].text);
r = await admin("POST", "/api/admin/renovacoes/" + idBruno + "/tratar", como());
d = await r.json();
checar(!d.abertas.length && d.tratadas.length === 1, "marcar como tratada");

// --------------------------------------------------------- materiais
console.log("materiais (saíram)");
const semMateriais = await atenderAdmin(new Request("https://paulus.ia.br/api/materiais/enviar", { method: "POST", body: "{}" }), env, new URL("https://paulus.ia.br/api/materiais/enviar"), {}, deps);
checar(semMateriais.status !== 200 && !ehRotaDoAdmin(new URL("https://paulus.ia.br/api/materiais/enviar")), "o envio de material saiu do painel");
r = await admin("GET", "/api/admin/materiais", como());
checar(r.status === 404, "a fila de materiais saiu do painel", r.status);

// --------------------------------------------------------- NFS-e e equipe (sairam do painel do PAVLVS)
console.log("nfse e equipe: saíram do PAVLVS");
r = await admin("GET", "/api/admin/nfse", como());
checar(r.status === 404, "a aba Notas fiscais do PAVLVS saiu do painel (a Atos tem a dela): 404");
r = await admin("GET", "/api/admin/nfse/emissor/situacao", como());
checar(r.status === 404, "as rotas do emissor não são expostas: 404");
r = await admin("POST", "/api/admin/nfse/emissor/notas", como({ corpo: { valor: 1 } }));
checar(r.status === 404, "nem para emitir");
for (const tipo of ["nfse.config", "nfse.emitir", "equipe.papel", "equipe.membro"]) {
  r = await admin("POST", "/api/admin/alteracoes", como({ corpo: { tipo, dados: { email: "dono@paulus.ia.br", papel: "suporte", acao: "excluir" }, texto: tipo } }));
  d = await r.json();
  checar(r.status === 400 && d.erro.includes("desconhecida"), tipo + " saiu da fila do PAVLVS (a equipe é a fila da Atos): alteração desconhecida", d);
}
r = await admin("POST", "/api/admin/equipe/convite/" + encodeURIComponent("x@paulus.ia.br") + "/reenviar", como());
checar(r.status === 404, "reenviar convite saiu do PAVLVS (é da Atos): 404");
checar(!ehRotaDoAdmin(new URL("https://paulus.ia.br/api/equipe/convite")), "a página do convite da equipe saiu do Worker");

// ----------------------------------------------------------- o medidor por dentro
const contaDo = (id, acao, dados = {}) => CONTAS_IA.get(id).fetch("https://conta-ia/" + acao, { method: "POST", body: JSON.stringify({ acao, ...dados }) }).then((x) => x.json());
const fila = async () => (await (await admin("GET", "/api/admin/alteracoes", como())).json()).pendentes;

// ================================================ etapa 6: o que o painel pedia ao servidor
const DIA = 24 * 3600 * 1000;
const publicarFila = async (extra = {}) => (await admin("POST", "/api/admin/publicar", como({ ...extra, corpo: { confirmacao: "comitar e pushar" } }))).json();
const pedir = (tipo, dados, texto = tipo, extra = {}) => admin("POST", "/api/admin/alteracoes", como({ ...extra, corpo: { tela: "teste", tipo, alvo: String(dados.id || dados.slug || dados.email || ""), dados, texto } }));
const comoSuporte = (extra = {}) => ({ email: "suporte@paulus.ia.br", cookie: sessaoSuporte, ...extra });
const limparFila = async () => { for (const x of await fila()) await admin("DELETE", "/api/admin/alteracoes/" + x.id, como()); };
async function novaConta(nome) {
  const x = await (await ia("/api/ia/ativar", { id_token: nome, instalacao_id: "inst-" + nome + "-123", nome_escritorio: "Escritório " + nome })).json();
  return x.segredo.split("_")[1];
}
// Mexe direto no que o medidor guarda (o uso de meses atras, um ciclo que ja venceu).
async function mexerNaConta(id, f) {
  const st = objetos.get(id).state.storage;
  const conta = await st.get("conta");
  f(conta);
  await st.put("conta", conta);
}
const retroagir = (corpo, extra = {}) => admin("POST", "/api/admin/retroagir", como({ ...extra, corpo: { confirmacao: "retroagir", ...corpo } }));
let antesMP2, det;

// ---------------------------------------------- conta: o cadastro (a cobranca e da Atos)
console.log("conta: cadastro; as ações de dinheiro saíram");
await limparFila();
const idEva = await novaConta("eva");
for (const tipo of ["conta.reembolsar", "conta.cancelar", "conta.pausar", "conta.plano", "renov.oferta"]) {
  r = await pedir(tipo, { id: idEva, plano: "plus", pagamento: "PAY1", tipo: "creditos", tokens: 10e6 });
  d = await r.json();
  if (!(r.status === 400 && String(d.erro).includes("desconhecida"))) checar(false, tipo + " saiu do painel: alteração desconhecida", { s: r.status, d });
}
checar(!(await fila()).length && !mp.length, "devolver, cancelar, pausar, trocar o plano e a oferta de volta saíram do painel (a cobrança é da Atos)");
const cadEva = { nome_escritorio: "Eva Advocacia", documento: "52998224725", telefone: "91988887777", oab: "PA 12345", termos: "2026-10-03", quando: "2026-10-01T12:00:00.000Z",
  endereco: { cep: "66010000", logradouro: "Rua A", numero: "10", complemento: "", bairro: "Centro", cidade: "Belém", uf: "PA", cmun: "1501402" } };
await contaDo(idEva, "cadastro", { cadastro: cadEva });
det = await (await admin("GET", "/api/admin/contas/" + idEva, como())).json();
checar(det.cadastro.cep === "66010000" && det.cadastro.cidade === "Belém" && det.cadastro.logradouro === "Rua A" && det.cadastro.cmun === "1501402" && det.cadastro.documento === "52998224725",
  "a ficha traz o endereço do cadastro achatado (CEP, rua, cidade...), como o Editar cadastro lê", det.cadastro);
r = await pedir("conta.cadastro", { id: idEva, documento: "123" });
d = await r.json();
checar(r.status === 400 && d.erro.includes("CPF ou CNPJ"), "cadastro com CPF que não confere: recusado na fila", d);
r = await pedir("conta.cadastro", { id: idEva, telefone: "(91) 3222-1111", cidade: "Ananindeua" }, "Editei o cadastro da Eva (2 campos)", comoSuporte());
checar(r.status === 200, "o suporte também edita cadastro (pela fila dele)");
d = await (await admin("POST", "/api/admin/publicar", comoSuporte({ corpo: { confirmacao: "comitar e pushar" } }))).json();
const pubCadastro = d.publicacao;
const cadDepois = (await contaDo(idEva, "admin_detalhe")).cadastro;
checar(d.ok && cadDepois.telefone === "9132221111" && cadDepois.endereco.cidade === "Ananindeua" && cadDepois.endereco.cmun === "1500800" && cadDepois.endereco.logradouro === "Rua A"
  && cadDepois.termos === "2026-10-03" && cadDepois.quando === "2026-10-01T12:00:00.000Z" && cadDepois.ajustado.por === "suporte@paulus.ia.br",
  "publicado: telefone e cidade novos com o código IBGE da cidade; o aceite dos termos continua o da pessoa", cadDepois);

// ---------------------------------------------- o registro de enderecos
console.log("registro de endereços");
const escritorios = new Map();
const metadados = new Map();
const ESCRITORIOS = {
  get: async (k) => (escritorios.has(k) ? escritorios.get(k) : null),
  put: async (k, v, o = {}) => { escritorios.set(k, v); if (o.metadata) metadados.set(k, o.metadata); },
  delete: async (k) => { escritorios.delete(k); metadados.delete(k); },
  list: async ({ prefix }) => ({ list_complete: true, keys: [...escritorios.keys()].filter((k) => k.startsWith(prefix)).sort().map((name) => ({ name, metadata: metadados.get(name) })) }),
};
const envT = { ...env, ESCRITORIOS, TUNEL_ATIVO: "1", CF_API_TOKEN: "cf-tuneis", CF_ACCOUNT_ID: "conta1", CF_ZONE_ID: "zona1" };
const umMinuto = () => { relogio += 60 * 1000; };
await provisionar(envT, "moura", { nome: "Moura Advocacia", porta: 47123, instalacao_id: "inst-moura-0001", dono: { sub: "111", email: "titular@moura.adv.br" } }, () => relogio);
umMinuto();
for (const [tipo, dados] of [["tunel.endereco", { slug: "moura", novo: "moura-adv" }], ["tunel.ativo", { slug: "moura-adv", ativo: false }], ["tunel.ativo", { slug: "moura-adv", ativo: true }], ["tunel.apagar", { slug: "moura-adv" }]]) {
  r = await pedir(tipo, dados, tipo, { envUsado: envT });
  d = await publicarFila({ envUsado: envT });
  if (!d.ok) checar(false, "publicar " + tipo, d);
  umMinuto();
}
const silva = await provisionar(envT, "silva", { nome: "Silva", porta: 47124, instalacao_id: "inst-silva-0001", dono: { sub: "222", email: "titular@silva.adv.br" } }, () => relogio);
umMinuto();
const pedidoRemover = new Request("https://paulus.ia.br/api/tunel/remover", { method: "POST", headers: { authorization: "Bearer " + silva.entrega.segredo_instalacao } });
r = await atenderTunel(pedidoRemover, envT, new URL(pedidoRemover.url), { agora: () => relogio });
checar(r.status === 200, "o escritório remove o próprio endereço");
umMinuto();
await provisionar(envT, "retomado", { nome: "Retomado", porta: 47125, instalacao_id: "inst-reto-0001", dono: { sub: "333", email: "titular@retomado.adv.br" }, retomar: true }, () => relogio);
umMinuto();
const oitoDiasAtras = relogio - 8 * DIA;
await provisionar(envT, "parado", { nome: "Parado", porta: 47126, instalacao_id: "inst-parado-01", dono: null }, () => oitoDiasAtras);
const limpeza = await limparEscritorios(envT, () => relogio);
checar(limpeza.removidos.length === 1 && limpeza.removidos[0].slug === "parado", "a limpeza diária libera o que nunca conectou", limpeza);
r = await admin("GET", "/api/admin/tuneis", como({ envUsado: envT }));
d = await r.json();
const reg = d.registro || [];
const ev = (slug, evento) => reg.find((x) => x.slug === slug && x.evento === evento) || {};
checar(reg.length === 10, "dez eventos no registro (cada mudança de endereço registra sozinha)", reg);
checar(reg[0].evento === "liberado" && reg[0].slug === "parado" && reg[0].quem === "limpeza automática" && reg[0].motivo === "nunca conectou em 7 dias" && reg[0].estado === "livre",
  "do mais novo ao mais velho: a limpeza automática liberou parado", reg[0]);
checar(ev("moura", "criado").quem === "titular@moura.adv.br" && ev("moura", "criado").estado === "ativo", "criado: quem conectou (o dono do endereço)", ev("moura", "criado"));
checar(ev("moura-adv", "alterado").de === "moura" && ev("moura-adv", "alterado").quem === "dono@paulus.ia.br" && ev("moura-adv", "alterado").estado === "ativo",
  "alterado: o endereço novo, o de antes e quem trocou pelo painel", ev("moura-adv", "alterado"));
checar(ev("moura-adv", "desativado").estado === "desativado" && ev("moura-adv", "reativado").estado === "ativo" && ev("moura-adv", "desativado").quem === "dono@paulus.ia.br",
  "desativado e reativado, com quem e o estado");
checar(ev("moura-adv", "liberado").quem === "dono@paulus.ia.br" && ev("moura-adv", "liberado").motivo === "apagado pelo painel" && ev("moura-adv", "liberado").estado === "livre",
  "liberado pelo painel", ev("moura-adv", "liberado"));
checar(ev("silva", "liberado").quem === "titular@silva.adv.br" && ev("silva", "liberado").motivo === "removido pelo escritório", "liberado pelo próprio escritório", ev("silva", "liberado"));
checar(String(ev("retomado", "criado").motivo).includes("retomado") && !ev("retomado", "liberado").evento, "a retomada é um criado só, com o motivo", ev("retomado", "criado"));
checar(ev("parado", "criado").quem === "o escritório" && ev("parado", "criado").quando === new Date(oitoDiasAtras).toISOString(), "sem dono: \"o escritório\"; o criado fica com a hora em que nasceu");
checar([...metadados.keys()].filter((k) => k.startsWith("evento:")).length === 10 && reg.every((x) => !JSON.stringify(x).includes("segredo")),
  "cada evento é uma chave com os metadados (a lista lê sem um get por evento), sem segredo nenhum");

// ---------------------------------------------- a mensagem da nao renovacao
console.log("mensagem na não renovação");
emails.length = 0;
r = await admin("POST", "/api/admin/renovacoes/" + idBruno + "/mensagem", como({ corpo: { texto: "Oi, Bruno. Vi que o cartão recusou: quer ajuda?" } }));
d = await r.json();
const msgBruno = emails[0];
checar(r.status === 200 && msgBruno && msgBruno.to[0] === "bruno@escritorio.com.br" && msgBruno.from === "Matheus (PAVLVS) <naoresponda@paulus.ia.br>" && msgBruno.text.includes("quer ajuda?")
  && msgBruno.text.includes("Equipe PAVLVS") && msgBruno.reply_to === "contato@paulus.ia.br", "a mensagem vai para a conta, com o nome de quem escreveu", msgBruno);
const itemBruno = [...d.abertas, ...d.tratadas].find((x) => x.id === idBruno);
checar(itemBruno && itemBruno.mensagem_em && !guardados.get("admin:renov:" + idBruno).includes("quer ajuda"), "fica anotada na renovação (quando e quem; o texto não fica guardado)", itemBruno);
r = await admin("POST", "/api/admin/renovacoes/" + idBruno + "/mensagem", como({ corpo: { texto: "   " } }));
checar(r.status === 400, "mensagem vazia: recusada");
r = await admin("POST", "/api/admin/renovacoes/" + idBruno + "/mensagem", { ...como(), envUsado: { ...env, RESEND_API_KEY: "" }, corpo: { texto: "Oi" } });
checar(r.status === 503 && (await r.json()).erro.includes("RESEND_API_KEY"), "sem o provedor de e-mail: 503 dizendo o que falta");
r = await admin("POST", "/api/admin/renovacoes/" + "0".repeat(24) + "/mensagem", como({ corpo: { texto: "Oi" } }));
checar(r.status === 404, "conta sem ciclo vencido: 404");

// ---------------------------------------------- tokens: por modelo e outro periodo
console.log("tokens: por modelo e outro período");
relogio = Math.max(relogio, Date.parse("2026-11-12T18:00:00Z"));
const LLAMA = "meta-llama/Llama-3.3-70B-Instruct";
const SONNET = "claude-sonnet-5-5";
const MISTRAL = "mistral-large-latest";
const idTok = await novaConta("toka");
await mexerNaConta(idTok, (x) => {
  x.uso = [
    { dia: "2026-10-20", tokens: 5000, entrada: 3000, saida: 2000, modelos: { [MISTRAL]: { entrada: 3000, saida: 2000 } } },
    { dia: "2026-11-10", tokens: 1500, entrada: 1000, saida: 500, modelos: { [LLAMA]: { entrada: 1000, saida: 500 } } },
    { dia: "2026-11-11", tokens: 3000, entrada: 2000, saida: 1000, modelos: { [SONNET]: { entrada: 2000, saida: 1000 } } },
  ];
  // Outubro inteiro tem mais que o dia 20: os dias de antes ja nao estao guardados.
  x.uso_mes = { "2026-10": { entrada: 8000, saida: 3000, modelos: { [MISTRAL]: { entrada: 8000, saida: 3000 } } },
    "2026-11": { entrada: 3000, saida: 1500, modelos: { [LLAMA]: { entrada: 1000, saida: 500 }, [SONNET]: { entrada: 2000, saida: 1000 } } } };
  x.pagamentos = [{ tipo: "assinatura", ref: "TOK1", valor: 300, quando: "2026-11-05T15:00:00.000Z" }];
});
const tok = async (q) => { const x = await admin("GET", "/api/admin/tokens?" + q, como()); return { status: x.status, d: await x.json() }; };
const daToka = (t) => (t.d.linhas || []).find((l) => l.nome.startsWith("Escritório toka")) || {};
let t1 = await tok("visao=conta&periodo=mes");
checar(t1.status === 200 && daToka(t1).entrada === 3000 && daToka(t1).saida === 1500 && !t1.d.incompleto && t1.d.periodo.de === "2026-11-01" && t1.d.periodo.ate === "2026-11-12",
  "este mês: o mês inteiro do medidor", { linha: daToka(t1), p: t1.d.periodo });
t1 = await tok("visao=conta&periodo=30");
checar(daToka(t1).entrada === 6000 && daToka(t1).saida === 3500 && t1.d.incompleto && t1.d.desde === "2026-10-20" && t1.d.aviso.includes("20/10/2026"),
  "30 dias: o pedaço de outubro pelos dias guardados, e a resposta diz que antes de 20/10 o medidor não guarda", { linha: daToka(t1), t: { inc: t1.d.incompleto, desde: t1.d.desde, aviso: t1.d.aviso } });
t1 = await tok("visao=conta&periodo=custom&de=2026-10-25&ate=2026-11-10");
checar(t1.status === 200 && daToka(t1).entrada === 1000 && daToka(t1).saida === 500 && !t1.d.incompleto && t1.d.periodo.de === "2026-10-25" && t1.d.periodo.ate === "2026-11-10",
  "outro período (de a ate): só os dias dele, sem faltar nada", { linha: daToka(t1), p: t1.d.periodo, inc: t1.d.incompleto });
t1 = await tok("visao=conta&periodo=90");
checar(t1.d.periodo.de === "2026-08-15" && daToka(t1).receita === 300, "90 dias: de 15/08 a hoje, com o arrecadado", t1.d.periodo);
for (const q of ["periodo=custom&de=2026-11-10&ate=2026-10-25", "periodo=custom&de=2026-02-30&ate=2026-03-01", "periodo=custom", "periodo=semana", "visao=cliente"]) {
  t1 = await tok(q);
  if (t1.status !== 400) checar(false, "período ou visão inválidos: 400 (" + q + ")", t1);
}
checar(true, "período ao contrário, dia que não existe, sem as datas e visão desconhecida: 400");
t1 = await tok("visao=modelo&periodo=mes");
const lSonnet = t1.d.linhas.find((l) => l.modelo === SONNET) || {};
const lLlama = t1.d.linhas.find((l) => l.modelo === LLAMA) || {};
checar(lSonnet.nome === "Claude Sonnet 5.5" && lSonnet.fabricante === "Anthropic" && lSonnet.planos.includes("Escritório Plus") && lSonnet.sub.includes("Anthropic")
  && lSonnet.preco[0] === 2 && lSonnet.preco[1] === 10 && lSonnet.entrada === 2000 && lSonnet.saida === 1000 && Math.abs(lSonnet.receita - 200) < 1e-9
  && Math.abs(lSonnet.custo_usd - ((2000 / 1e6) * 2 + (1000 / 1e6) * 10)) < 1e-12,
  "por modelo: fabricante, planos, preço por milhão, uso, custo e o arrecadado da conta dividido pelo uso de cada modelo", lSonnet);
checar(lLlama.fabricante === "Meta" && lLlama.planos.includes("Advogado") && lLlama.receita >= 100 && !t1.d.linhas.some((l) => l.modelo === MISTRAL),
  "o Llama com o que a Toka pagou pelo uso dele (e o das contas do Advogado sem uso no mês); o Mistral não usou no mês", lLlama);
checar(Math.abs(t1.d.linhas.reduce((s, l) => s + l.receita, 0) - t1.d.kpis.receita) < 1e-6, "a soma do arrecadado por modelo é o arrecadado do período");
t1 = await tok("visao=modelo&periodo=custom&de=2026-10-01&ate=2026-10-31");
const lMistral = t1.d.linhas.find((l) => l.modelo === MISTRAL) || {};
checar(lMistral.entrada === 8000 && lMistral.saida === 3000 && lMistral.planos.includes("Escritório") && !t1.d.incompleto, "outubro inteiro sai do total do mês (nada falta)", lMistral);

// ---------------------------------------------- campanha agendada
console.log("campanha agendada");
await limparFila();
emails.length = 0;
r = await pedir("campanha.disparar", { nome: "Novidade", publico: "todos", assunto: "Oi", texto: "Novidade no Paulus", quando: "agendado", de: "2026-11-20" });
checar(r.status === 400 && (await r.json()).erro.includes("hora"), "agendada sem a hora: recusada");
r = await pedir("campanha.disparar", { nome: "Novidade", publico: "todos", assunto: "Oi", texto: "Novidade", quando: "agendado", de: "2026-11-01", hora: "10:00" });
checar(r.status === 400 && (await r.json()).erro.includes("já passou"), "agendada para trás: recusada");
r = await pedir("campanha.disparar", { nome: "Novidade", publico: "escolhidas", contas: [], assunto: "Oi", texto: "Novidade", quando: "agora" });
checar(r.status === 400, "escolher contas sem nenhuma conta: recusada");
r = await pedir("campanha.disparar", { nome: "Novidade", publico: "escolhidas", contas: [idAna, idEva], assunto: "Oi, {nome}", texto: "Novidade", quando: "agendado", de: "2026-11-20", hora: "14:30" },
  "Pedi o disparo \"Novidade\" para 2 contas (20/11 às 14:30)");
checar(r.status === 200, "agendada para 20/11 às 14:30 (Brasília), para duas contas escolhidas");
d = await publicarFila();
let camps = (await (await admin("GET", "/api/admin/campanhas", como())).json()).campanhas;
const novidade = camps.find((x) => x.nome === "Novidade") || {};
checar(d.ok && novidade.situacao === "agendada" && novidade.quando === "2026-11-20T17:30:00.000Z" && novidade.publico.id === "escolhidas" && novidade.publico.label === "2 contas escolhidas",
  "fica guardada para 17:30 UTC (14:30 em Brasília), e a tela vê a hora", novidade);
let envio = await enviarCampanhas(env, Date.parse("2026-11-20T17:29:00Z"));
checar(envio.enviados === 0 && emails.length === 0, "o Cron de um minuto antes não manda nada", envio);
envio = await enviarCampanhas(env, Date.parse("2026-11-20T17:30:00Z"));
checar(envio.enviados === 2 && emails.map((e) => e.to[0]).sort().join() === "ana@escritorio.com.br,eva@escritorio.com.br" && emails.some((e) => e.subject === "Oi, Eva"),
  "na hora marcada, o Cron manda para as duas escolhidas", emails.map((e) => e.to[0] + " · " + e.subject));
const daqui = new Date(relogio + 3 * 60 * 1000 - 3 * 3600 * 1000).toISOString();
r = await pedir("campanha.disparar", { nome: "Atrasada", publico: "todos", assunto: "x", texto: "y", quando: "agendado", de: daqui.slice(0, 10), hora: daqui.slice(11, 16) });
checar(r.status === 200, "agendada para daqui a três minutos");
relogio += 10 * 60 * 1000;
d = await publicarFila();
checar(!d.ok && d.resultados[0].erro.includes("passou antes de publicar"), "publicada depois da hora: não sai atrasada sozinha, volta para a fila com o porquê", d);
await limparFila();

// ---------------------------------------------- o extrato com as NFS-e
console.log("extrato com as NFS-e");
const notasFalsas = [
  { id: 7, conta: idAna, pagamento: "ORD1", estado: "substituida", numero: "10", ambiente: "producao_restrita" },
  { id: 9, conta: idAna, pagamento: "ORD1", estado: "emitida", numero: "12", ambiente: "producao_restrita" },
  { id: 11, conta: idBruno, pagamento: "ORD1", estado: "emitida", numero: "13" },
];
const EMISSOR_NFSE = { idFromName: (n) => n, get: () => ({ fetch: async (url, init) => {
  const { acao, dados } = JSON.parse(init.body);
  if (acao === "listar") return Response.json({ notas: notasFalsas });
  if (acao === "nota") return Response.json({ nota: notasFalsas.find((x) => x.id === dados.id) || {} });
  if (acao === "xml") return Response.json({ xml: "<NFSe>12</NFSe>", nome: "NFS-e 12.xml" });
  return Response.json({ erro: "ação de mentira" }, { status: 400 });
} }) };
const envNf = { ...env, EMISSOR_NFSE, NFSE_CHAVE_MESTRA: "chave-de-teste" };
det = await (await admin("GET", "/api/admin/contas/" + idAna, como({ envUsado: envNf }))).json();
const pgOrd1 = (det.pagamentos || []).find((x) => x.ref === "ORD1") || {};
checar(pgOrd1.nfse && pgOrd1.nfse.id === 9 && pgOrd1.nfse.numero === "12" && pgOrd1.nfse.estado === "emitida"
  && pgOrd1.nfse.pdf === null && pgOrd1.nfse.xml === null,
  "cada pagamento traz a NFS-e (a substituta, não a substituída; a de outra conta não entra), sem os links do emissor (saíram do painel)", pgOrd1);
det = await (await admin("GET", "/api/admin/contas/" + idAna, como())).json();
checar(det.pagamentos.every((x) => x.nfse === null), "sem o emissor, o extrato não inventa nota");
r = await admin("GET", "/api/admin/nfse/emissor/notas/9/pdf?baixar=1", comoSuporte({ envUsado: envNf }));
checar(r.status === 404, "e o PDF da nota não abre mais pelo painel");

// ---------------------------------------------- nao renovacoes: so a Atos
console.log("não renovações: só a conta cobrada pela Atos");
const idJoe = await novaConta("joe");
await mexerNaConta(idJoe, (x) => {
  x.plano = "advogado";
  x.ciclo = { inicio: new Date(relogio - 32 * DIA).toISOString(), fim: new Date(relogio - 2 * DIA).toISOString(), tokens: 1e6, usados: 0 };
  x.assinatura = { id: "preJoe", situacao: "authorized", valor: 449 };
});
d = await (await admin("GET", "/api/admin/renovacoes", como())).json();
checar(![...d.abertas, ...d.tratadas].some((x) => x.id === idJoe), "o ciclo vencido do caminho antigo (fora da Atos) não entra em Não renovações", d.abertas.map((x) => x.id));

// ---------------------------------------------- retroagir
console.log("retroagir");
await limparFila();
const planosAntesNf = guardados.get("admin:planos");
await pedir("plano.editar", { id: "plus", valor: 999, valor_anual: 9990, tokens: 90 }, "Plus a R$ 999");
d = await publicarFila();
const pubNf = d.publicacao;
checar(d.ok && pubNf.id && pubNf.retroagivel && !("retrato" in pubNf) && guardados.has("admin:retrato:" + pubNf.id), "cada publicação guarda o retrato (fora da lista que a tela lê)", pubNf);
r = await retroagir({ publicacao: pubNf.id, confirmacao: "retroagi" });
checar(r.status === 400, "sem a palavra certa: 400");
r = await admin("POST", "/api/admin/retroagir", comoSuporte({ corpo: { publicacao: pubNf.id, confirmacao: "retroagir" } }));
checar(r.status === 403, "o suporte não retroage");
r = await retroagir({ commit: pubNf.commit });
d = await r.json();
checar(r.status === 200 && d.ok && d.commit.startsWith("kv-") && d.publicacao.revertida && guardados.get("admin:planos") === planosAntesNf,
  "retroagir pelo commit (como a tela manda): os planos voltam ao que eram", d);
r = await retroagir({ commit: pubNf.commit });
checar(r.status === 409, "de novo: já foi retroagida");
d = await (await admin("GET", "/api/admin/alteracoes", como())).json();
checar(d.publicacoes.find((x) => x.id === pubNf.id).revertida.por === "matheus", "o histórico mostra a publicação retroagida");

await pedir("conta.creditar", { id: idAna, tokens: 1000 }, "Creditei 1.000 tokens à Ana");
const planosAntesTudo = guardados.get("admin:planos");
await pedir("plano.editar", { id: "plus", valor: 998, valor_anual: 9980, tokens: 90 }, "Plus a R$ 998");
d = await publicarFila();
r = await retroagir({ publicacao: d.publicacao.id });
const naoVolta = await r.json();
checar(r.status === 409 && naoVolta.erro.includes("créditos já estão na conta") && JSON.parse(guardados.get("admin:planos")).find((p) => p.id === "plus").valor === 998,
  "com uma alteração que não volta, nada volta (tudo ou nada), e a resposta diz qual e por quê", naoVolta);

const idHana = await novaConta("hana");
await naAtos(idHana, "advogado", { id: "atos-h1", status: "authorized" });
const mpAntesDosPlanos = mp.length;
const planosAntesA = guardados.get("admin:planos");
await pedir("plano.editar", { id: "advogado", valor: 459, valor_anual: 4090, tokens: 30 }, "Advogado a R$ 459");
const pA = (await publicarFila()).publicacao;
await pedir("plano.editar", { id: "advogado", valor: 469, valor_anual: 4190, tokens: 30 }, "Advogado a R$ 469");
const pB = (await publicarFila()).publicacao;
checar(mp.length === mpAntesDosPlanos, "mudar o valor do plano não mexe em assinatura nenhuma (a cobrança é da Atos)");
r = await retroagir({ publicacao: pA.id });
checar(r.status === 409 && (await r.json()).erro.includes("mudaram depois"), "retroagir a mais velha com uma mais nova por cima: recusado");
r = await retroagir({ publicacao: pB.id });
checar(r.status === 200 && JSON.parse(guardados.get("admin:planos")).find((p) => p.id === "advogado").valor === 459 && mp.length === mpAntesDosPlanos,
  "a mais nova volta primeiro, sem chamar o Mercado Pago");
r = await retroagir({ publicacao: pA.id });
checar(r.status === 200 && guardados.get("admin:planos") === planosAntesA, "depois, a mais velha: os planos ficam como eram antes das duas");

r = await admin("POST", "/api/admin/retroagir", comoSuporte({ corpo: { publicacao: pubCadastro.id, confirmacao: "retroagir" } }));
checar(r.status === 403, "nem a publicação do próprio suporte: só o dono retroage");
r = await retroagir({ publicacao: pubCadastro.id });
const cadVolta = (await contaDo(idEva, "admin_detalhe")).cadastro;
checar(r.status === 200 && cadVolta.telefone === "91988887777" && cadVolta.endereco.cidade === "Belém" && !cadVolta.ajustado, "o cadastro editado volta ao que era", cadVolta);

const daqui2 = new Date(relogio + 2 * DIA - 3 * 3600 * 1000).toISOString();
await pedir("campanha.disparar", { nome: "Volta", publico: "todos", assunto: "x", texto: "y", quando: "agendado", de: daqui2.slice(0, 10), hora: daqui2.slice(11, 16) }, "Agendei Volta");
const pCamp = (await publicarFila()).publicacao;
const idVolta = (await (await admin("GET", "/api/admin/campanhas", como())).json()).campanhas.find((x) => x.nome === "Volta").id;
r = await retroagir({ publicacao: pCamp.id });
const volta = JSON.parse(guardados.get("admin:campanha:" + idVolta));
checar(r.status === 200 && volta.situacao === "cancelada" && !JSON.parse(guardados.get("admin:campanhas:fila")).includes(idVolta) && volta.destinatarios.every((x) => !x.email),
  "a campanha agendada que ainda não saiu é cancelada", volta.situacao);

const pubs0 = JSON.parse(guardados.get("admin:publicacoes"));
pubs0.push({ quando: "2026-10-01T12:00:00.000Z", commit: "kv-0a1b2", resumo: "Antiga", n: 1, por: "matheus" });
pubs0.push({ quando: "2026-09-30T12:00:00.000Z", commit: "abc1234", resumo: "Publiquei a peça", n: 2, por: "matheus" });
guardados.set("admin:publicacoes", JSON.stringify(pubs0));
r = await retroagir({ commit: "kv-0a1b2" });
checar(r.status === 409 && (await r.json()).erro.includes("antes do retrato"), "publicação de antes do retrato: não dá para retroagir, e a resposta diz");
ghReversao.conflito = true;
r = await retroagir({ commit: "abc1234" });
checar(r.status === 502 && (await r.json()).erro.includes("mudou depois"), "commit cujo arquivo mudou depois na main: não reverte");
ghReversao.conflito = false;
ghReversao.chamadas.length = 0;
r = await retroagir({ commit: "abc1234" });
d = await r.json();
const arvore = ghReversao.chamadas.find((x) => x.metodo === "POST" && x.url === GH + "/git/trees") || {};
const commitNovo = ghReversao.chamadas.find((x) => x.metodo === "POST" && x.url === GH + "/git/commits") || {};
const mover = ghReversao.chamadas.find((x) => x.metodo === "PATCH") || {};
checar(r.status === 200 && d.commit === "reverte" && arvore.corpo.base_tree === "arvore000" && arvore.corpo.tree.find((x) => x.path === "site/materiais/peca.md").sha === null
  && arvore.corpo.tree.find((x) => x.path === "site/dados/materiais.json").sha === "blobJson1" && commitNovo.corpo.parents[0] === "cabeca000" && commitNovo.corpo.tree === "arvore001"
  && mover.corpo.sha.startsWith("reverte") && mover.corpo.force === false && arvore.token === "gho_x",
  "commit no GitHub: um commit de reversão na main (o arquivo criado sai, o mudado volta), com o token de quem está logado", { d, arvore: arvore.corpo, commitNovo: commitNovo.corpo });
r = await retroagir({ publicacao: "naoexiste" });
checar(r.status === 404, "publicação que não está no histórico: 404");

// ================================================ etapa 6, segunda volta: o que a tela ainda pedia
// ---------------------------------------------- planos: os textos da pagina, o .JSON e as versoes
console.log("planos: textos da página, .JSON e versões");
await limparFila();
let pl = await (await admin("GET", "/api/admin/planos", como())).json();
const plAdv = pl.planos.find((p) => p.id === "advogado") || {};
checar(plAdv.para === "Para quem advoga sozinho." && plAdv.heranca === null && plAdv.textos && !plAdv.textos.itens && plAdv.itens[0].titulo.startsWith("IA Llama")
  && plAdv.itens.some((x) => x.titulo === "Biblioteca jurídica"), "cada plano traz os textos da página (os padrão, montados com os números do plano)", plAdv.itens && plAdv.itens.slice(0, 2));
const plEsc = pl.planos.find((p) => p.id === "escritorio") || {};
checar(plAdv.textos_padrao && plAdv.textos_padrao.heranca === "" && plAdv.textos_padrao.para === "Para quem advoga sozinho."
  && plEsc.textos_padrao && plEsc.textos_padrao.heranca === "Tudo do plano Advogado, e mais",
  "e o padrão da frase e do texto antes dos itens (o que vale com o campo vazio)", [plAdv.textos_padrao, plEsc.textos_padrao]);
checar(Array.isArray(pl.versoes) && pl.versoes.length >= 2 && pl.versoes[0].quem === "antes do histórico" && pl.versoes[0].resumo.includes("fábrica")
  && pl.versoes.every((v, i) => !i || v.n === pl.versoes[i - 1].n + 1) && pl.versoes[1].resumo === "Escritório a R$ 320",
  "o histórico: a versão de antes (os planos de fábrica) e uma por publicação, com quem e o resumo", pl.versoes.map((v) => [v.n, v.quem, v.resumo]));
// Como o worker/index.js: os planos do painel (o cache de 60 s do IA_PLANOS) no env de cada pedido.
const publico = async (caminho) => atenderAdmin(new Request("https://paulus.ia.br" + caminho), await comPlanosDoPainel(env), new URL("https://paulus.ia.br" + caminho), { waitUntil() {} }, deps);
checar(ehRotaDoAdmin(new URL("https://paulus.ia.br/api/planos/textos")), "os textos dos planos são rota do Worker, fora do /api/admin (e do Access)");
r = await publico("/api/planos/textos");
let txt = await r.json();
checar(r.status === 200 && /public, max-age=60/.test(r.headers.get("cache-control")) && JSON.stringify(txt.planos.find((p) => p.id === "advogado").itens) === JSON.stringify(plAdv.itens),
  "a página de assinatura lê os mesmos textos, sem o Access (60 s de cache)");
r = await atenderAdmin(new Request("https://paulus.ia.br/api/planos/textos", { method: "POST", body: "{}" }), env, new URL("https://paulus.ia.br/api/planos/textos"), {}, deps);
checar(r.status === 404, "só GET");
// A aba Edicao manda tudo: numeros, pessoas, recarga e os textos (aqui, os de agora).
const edicao = (extra) => ({ id: "advogado", nome: plAdv.nome, para: plAdv.para, heranca: null, valor: plAdv.valor, valor_anual: plAdv.valor_anual, tokens: plAdv.tokens,
  pessoas: plAdv.pessoas, recarga: plAdv.recarga, itens: plAdv.itens, ...extra });
r = await pedir("plano.editar", edicao({ pessoas: 0 }));
checar(r.status === 400 && (await r.json()).erro.includes("pessoas"), "pessoas fora de 1 a 500: recusado");
r = await pedir("plano.editar", edicao({ recarga: { valor: 60, tokens: 0 } }));
checar(r.status === 400 && (await r.json()).erro.includes("recarga"), "recarga sem créditos: recusada");
r = await pedir("plano.editar", edicao({ itens: [{ titulo: "", descricao: "x" }] }));
checar(r.status === 400 && (await r.json()).erro.includes("sem título"), "item sem título: recusado");
await pedir("plano.editar", edicao({ pessoas: 2, recarga: { valor: 60, tokens: 12e6 } }), "Advogado com 2 pessoas e recarga de R$ 60");
d = await publicarFila();
let advKV = JSON.parse(guardados.get("admin:planos")).find((p) => p.id === "advogado");
checar(d.ok && advKV.pessoas === 2 && advKV.recarga.valor === 60 && advKV.recarga.tokens === 12e6 && !("itens" in advKV) && !("para" in advKV) && !("heranca" in advKV),
  "pessoas e recarga entram no plano; os textos iguais aos padrão não são guardados (continuam acompanhando os números)", advKV);
pl = await (await admin("GET", "/api/admin/planos", como())).json();
const advDepois = pl.planos.find((p) => p.id === "advogado");
checar(advDepois.pessoas === 2 && advDepois.recarga.valor === 60 && advDepois.recarga.tokens === 12e6 && advDepois.textos.itens === false,
  "o painel lê o plano com as pessoas e a recarga novas, e os itens continuam os padrão", { pessoas: advDepois.pessoas, recarga: advDepois.recarga });
const itensProprios = [{ titulo: "IA para o dia a dia", descricao: "Perguntas, peças e prazos (em breve: mais)." }, { titulo: "Suporte por e-mail", descricao: "Em até um dia útil." }];
await pedir("plano.editar", edicao({ pessoas: 2, recarga: { valor: 60, tokens: 12e6 }, para: "Para quem trabalha sozinho.", heranca: "Comece por aqui", itens: itensProprios }), "Textos novos no Advogado");
d = await publicarFila();
advKV = JSON.parse(guardados.get("admin:planos")).find((p) => p.id === "advogado");
txt = await (await publico("/api/planos/textos")).json();
const txtAdv = txt.planos.find((p) => p.id === "advogado");
checar(d.ok && advKV.para === "Para quem trabalha sozinho." && advKV.heranca === "Comece por aqui" && advKV.itens.length === 2 && txtAdv.para === "Para quem trabalha sozinho."
  && txtAdv.heranca === "Comece por aqui" && JSON.stringify(txtAdv.itens) === JSON.stringify(itensProprios), "os textos próprios valem na página de assinatura", txtAdv);
pl = await (await admin("GET", "/api/admin/planos", como())).json();
checar(pl.planos.find((p) => p.id === "advogado").textos.itens === true, "e o painel diz que os itens são escritos no painel");
await pedir("plano.editar", edicao({ pessoas: 2, recarga: { valor: 60, tokens: 12e6 }, para: "", heranca: "", itens: [] }), "Textos do Advogado de volta ao padrão");
d = await publicarFila();
advKV = JSON.parse(guardados.get("admin:planos")).find((p) => p.id === "advogado");
txt = await (await publico("/api/planos/textos")).json();
checar(d.ok && !("itens" in advKV) && !("para" in advKV) && txt.planos.find((p) => p.id === "advogado").para === "Para quem advoga sozinho.", "vazio volta ao padrão");

const atuais = JSON.parse(pl.json);
const comMudanca = (f) => { const l = structuredClone(atuais); f(l); return l; };
for (const [lista, frase, descricao] of [
  [comMudanca((l) => l.splice(l.findIndex((p) => p.id === "escritorio"), 1)), "plano escritorio", "sem o plano padrão"],
  [comMudanca((l) => { l[0].preco = 10; }), "não é campo", "campo que não é de plano"],
  [comMudanca((l) => { l[0].modelos = { padrao: "gpt-9" }; }), "não está no catálogo", "modelo fora do catálogo"],
  [comMudanca((l) => { l[0].recursos = { teletransporte: true }; }), "não existe", "recurso que não existe"],
  [comMudanca((l) => { l[0].tokens = "30M"; }), "tokens", "tokens que não é número inteiro"],
  [comMudanca((l) => l.splice(l.findIndex((p) => p.id === "advogado"), 1)), "contas estão nele", "tirar um plano com contas"],
]) {
  r = await pedir("planos.json", { planos: lista });
  const e = await r.json();
  if (!(r.status === 400 && String(e.erro).includes(frase))) checar(false, "o .JSON recusa " + descricao, e);
}
checar(true, "o .JSON recusa: sem o plano padrão, campo de fora, modelo fora do catálogo, recurso que não existe, tokens que não é número e tirar um plano com contas (com o porquê)");
// O que a aba .JSON manda sem mexer (site/assets/admin.js, planosAtuais): os campos do plano como o GET devolve,
// com os textos que valem (os padrão inclusive) e heranca null. Entra, e os padrão não vão para o KV.
const CAMPOS_DA_ABA = ["id", "nome", "para", "valor", "valor_anual", "tokens", "pessoas", "modelos", "recarga", "recursos", "heranca", "itens"];
pl = await (await admin("GET", "/api/admin/planos", como())).json();
const comoAba = pl.planos.map((p) => Object.fromEntries(CAMPOS_DA_ABA.filter((k) => p[k] !== undefined).map((k) => [k, p[k]])));
r = await pedir("planos.json", { planos: comoAba }, "Atualizei o IA_PLANOS (como a aba manda)");
const rAba = await r.json();
d = await publicarFila();
const kvAba = JSON.parse(guardados.get("admin:planos"));
checar(r.status === 200 && d.ok && kvAba.every((p) => !("itens" in p) && !("para" in p) && !("heranca" in p)),
  "a lista como a aba .JSON manda (textos padrão, heranca null) entra, e os textos padrão não são guardados", rAba.erro || kvAba.map((p) => Object.keys(p)));
pl = await (await admin("GET", "/api/admin/planos", como())).json();
const idPlus = await novaConta("plusa");
await naAtos(idPlus, "plus", { id: "atos-p1", status: "authorized" });
const novaLista = comMudanca((l) => {
  l.find((p) => p.id === "plus").valor = 3590;
  l.push({ id: "socio", nome: "Sócio", valor: 990, valor_anual: 9900, tokens: 20000000, pessoas: 3, itens: [{ titulo: "Para dois sócios", descricao: "Com a IA do Escritório." }] });
});
const planosAntesJson = guardados.get("admin:planos");
pl = await (await admin("GET", "/api/admin/planos", como())).json();
const versoesAntes = pl.versoes.length;
antesMP2 = mp.length;
r = await pedir("planos.json", { planos: novaLista }, "Atualizei o IA_PLANOS (4 planos)");
checar(r.status === 200, "a lista inteira entra na fila");
d = await publicarFila();
const pubJson = d.publicacao;
const kvJson = JSON.parse(guardados.get("admin:planos"));
pl = await (await admin("GET", "/api/admin/planos", como())).json();
checar(d.ok && kvJson.length === 4 && kvJson.find((p) => p.id === "socio").itens.length === 1 && !("itens" in kvJson.find((p) => p.id === "plus"))
  && mp.length === antesMP2,
  "publicado: o plano novo com os itens dele, os textos padrão não guardados, e nenhuma assinatura mexida (a cobrança é da Atos)", kvJson.map((p) => p.id));
checar(pl.versoes.length === versoesAntes + 1 && pl.versoes[pl.versoes.length - 1].resumo === "Atualizei o IA_PLANOS (4 planos)" && pl.versoes[pl.versoes.length - 1].quem === "matheus"
  && pl.versoes[pl.versoes.length - 1].planos.length === 4, "e entra uma versão nova no histórico, com a lista guardada");
txt = await (await publico("/api/planos/textos")).json();
checar(JSON.stringify((txt.planos.find((p) => p.id === "socio") || {}).itens) === JSON.stringify([{ titulo: "Para dois sócios", descricao: "Com a IA do Escritório." }]),
  "o plano novo chega à página de assinatura com os itens dele");
antesMP2 = mp.length;
r = await retroagir({ publicacao: pubJson.id });
d = await r.json();
pl = await (await admin("GET", "/api/admin/planos", como())).json();
checar(r.status === 200 && guardados.get("admin:planos") === planosAntesJson && mp.length === antesMP2
  && pl.versoes[pl.versoes.length - 1].resumo === "Retroagi: Atualizei o IA_PLANOS (4 planos)", "retroagir o .JSON: a lista de antes volta e o histórico anota", d);

// ---------------------------------------------- cancelar a campanha agendada
console.log("cancelar a campanha agendada");
await limparFila();
const daqui3 = new Date(relogio + 2 * DIA - 3 * 3600 * 1000).toISOString();
await pedir("campanha.disparar", { nome: "Lançamento", publico: "todos", assunto: "Novidade", texto: "Texto", quando: "agendado", de: daqui3.slice(0, 10), hora: daqui3.slice(11, 16) }, "Agendei Lançamento");
await publicarFila();
camps = (await (await admin("GET", "/api/admin/campanhas", como())).json()).campanhas;
const lanc = camps.find((x) => x.nome === "Lançamento");
r = await pedir("campanha.cancelar", { id: "c123" });
checar(r.status === 400, "campanha inválida: recusada");
r = await admin("POST", "/api/admin/alteracoes", comoSuporte({ corpo: { tela: "emails", tipo: "campanha.cancelar", alvo: lanc.id, dados: { id: lanc.id }, texto: "Cancelei o envio de Lançamento" } }));
checar(r.status === 200, "o cancelamento entra na fila (qualquer papel que dispara também cancela)");
d = await (await admin("POST", "/api/admin/publicar", comoSuporte({ corpo: { confirmacao: "comitar e pushar" } }))).json();
const lancKV = JSON.parse(guardados.get("admin:campanha:" + lanc.id));
checar(d.ok && lancKV.situacao === "cancelada" && lancKV.cancelada.por === "suporte@paulus.ia.br" && !JSON.parse(guardados.get("admin:campanhas:fila")).includes(lanc.id)
  && lancKV.destinatarios.every((x) => !x.email), "publicado: a campanha fica cancelada, sai da fila do Cron e a lista de e-mails some", lancKV.situacao);
emails.length = 0;
envio = await enviarCampanhas(env, relogio + 3 * DIA);
checar(!emails.some((e) => e.subject === "Novidade"), "e o Cron não manda nada dela na hora marcada");
r = await pedir("campanha.cancelar", { id: lanc.id });
checar(r.status === 400 && (await r.json()).erro.includes("já foi cancelada"), "cancelar de novo: recusado");
const enviada = camps.find((x) => x.situacao === "enviada");
r = await pedir("campanha.cancelar", { id: enviada.id });
checar(r.status === 400 && (await r.json()).erro.includes("saiu inteira"), "a que já saiu inteira não cancela: os e-mails não voltam");

// --------------------------------------------------------- privacidade
const pessoais = [...guardados.entries()].filter(([k]) => !k.startsWith("admin:"));
checar(!pessoais.length, "o painel so grava chaves admin: no APOIOS", pessoais.map(([k]) => k));

console.log("a conta cobrada pela Atos");
{
  const idAtos = "a7a7a7a7a7a7a7a7a7a7a7a7";
  const t0 = relogio;
  await CONTAS_IA.get(idAtos).fetch("https://conta-ia/", { method: "POST", body: JSON.stringify({ acao: "atos_direito", id: idAtos, dono: { sub: "pv-atos", email: "atos@x.br" },
    retrato: { versao: 1, plano: "escritorio", ate: new Date(relogio + 30 * 864e5).toISOString(), periodo: "mes", assinatura: { id: "atos-a1", status: "canceled", preco: "pavlvs.escritorio.mes" } } }) });
  await APOIOS.put("admin:conta:" + idAtos, JSON.stringify({ id: idAtos, criada: new Date(relogio).toISOString() }));
  // Passado o mes pago, sem renovar: entra em Nao renovacoes com o motivo da Atos, e o lembrete aponta para a Atos.
  relogio += 35 * 864e5;
  const rr = await admin("GET", "/api/admin/renovacoes", como());
  const item = ((await rr.json()).abertas || []).find((x) => x.id === idAtos);
  checar(item && item.motivo === "cancelou a assinatura na Atos" && item.tolerancia_dias === 0, "em Não renovações, com o motivo da Atos (e não do Mercado Pago do PAVLVS)", item);
  emails.length = 0;
  await admin("POST", "/api/admin/renovacoes/" + idAtos + "/lembrete", como());
  const em = emails[0] || {};
  checar(em.html && em.html.includes("atos.dev.br/conta") && !em.html.includes("Mercado Pago"), "o lembrete manda à Conta Atos", (em.html || "").slice(0, 200));
  relogio = t0;
}

console.log(falhas ? `\n  ${falhas} falha(s)` : "\n  painel admin: todos os testes passaram");
process.exit(falhas ? 1 : 0);
