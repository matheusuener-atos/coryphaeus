// Teste do painel admin (worker/admin.js), sem rede:
//   node worker/teste-admin.mjs
// O Cloudflare Access assina com uma chave gerada aqui; o GitHub, o Resend e o
// Mercado Pago sao de mentira; o Durable Object roda aqui sobre um Map.
import { atenderAdmin, enviarCampanhas, varredura, htmlDoEmail } from "./admin.js";
import { atenderIA, ContaIA } from "./ia.js";

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

// ------------------------------------------------ Resend e Mercado Pago
const emails = [];
const mp = [];
globalThis.fetch = async (url, init = {}) => {
  const u = String(url);
  if (u === "https://api.resend.com/emails") {
    emails.push(JSON.parse(init.body));
    return new Response(JSON.stringify({ id: "e" + emails.length }), { status: 200 });
  }
  return new Response("{}", { status: 404 });
};
async function chamarMP(env, caminho, metodo, corpo) {
  mp.push({ caminho, metodo, corpo });
  return { ok: true, status: 200, dados: {} };
}

// ------------------------------------------------ o Access de mentira
const TIME = "paulus.cloudflareaccess.com";
const AUD = "aud-do-painel";
const par = await crypto.subtle.generateKey({ name: "RSASSA-PKCS1-v1_5", modulusLength: 2048, publicExponent: new Uint8Array([1, 0, 1]), hash: "SHA-256" }, true, ["sign", "verify"]);
const jwkPublica = { ...(await crypto.subtle.exportKey("jwk", par.publicKey)), kid: "k1" };
const b64url = (bytes) => Buffer.from(bytes).toString("base64").replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/, "");
async function jwt(email, extra = {}) {
  const cab = b64url(new TextEncoder().encode(JSON.stringify({ alg: "RS256", kid: "k1" })));
  const corpo = b64url(new TextEncoder().encode(JSON.stringify({ email, aud: [AUD], iss: "https://" + TIME, exp: relogio / 1000 + 3600, ...extra })));
  const ass = await crypto.subtle.sign("RSASSA-PKCS1-v1_5", par.privateKey, new TextEncoder().encode(cab + "." + corpo));
  return cab + "." + corpo + "." + b64url(new Uint8Array(ass));
}

// ------------------------------------------------ o GitHub de mentira
let permissao = "write";
const ghCommits = [];
let materiaisJson = { atualizado_em: "2026-09-30", materiais: [{ slug: "antigo", titulo: "Antigo" }] };
async function github(metodo, url, token, corpo) {
  if (url.includes("/login/oauth/access_token")) return { ok: true, status: 200, dados: corpo.code === "bom" ? { access_token: "gho_x" } : {} };
  if (url.endsWith("/user")) return { ok: true, status: 200, dados: { login: "matheus" } };
  if (url.includes("/collaborators/")) return { ok: true, status: 200, dados: { permission: permissao } };
  if (url.includes("/contents/site/dados/materiais.json")) {
    if (metodo === "GET") return { ok: true, status: 200, dados: { sha: "s1", content: Buffer.from(JSON.stringify(materiaisJson)).toString("base64") } };
    materiaisJson = JSON.parse(Buffer.from(corpo.content, "base64").toString("utf8"));
    ghCommits.push(corpo.message);
    return { ok: true, status: 200, dados: { commit: { sha: "abcdef1234" } } };
  }
  if (url.includes("/contents/site/materiais/")) {
    if (metodo === "GET") return { ok: false, status: 404, dados: null };
    ghCommits.push(corpo.message);
    return { ok: true, status: 201, dados: { commit: { sha: "123456abcd" } } };
  }
  return { ok: false, status: 404, dados: null };
}

const env = {
  IA_ATIVA: "1", CONTAS_IA, APOIOS, ACCESS_TEAM: TIME, ACCESS_AUD: AUD,
  GITHUB_CLIENT_ID: "cid", GITHUB_CLIENT_SECRET: "csec", RESEND_API_KEY: "re_x", MP_ACCESS_TOKEN: "mp",
  IA_PLANO_TOKENS: "10000", IA_RECARGA_TOKENS: "5000",
  ADMIN_EQUIPE: JSON.stringify([{ email: "dono@paulus.ia.br", nome: "Matheus", papel: "dono" }, { email: "suporte@paulus.ia.br", nome: "Ana", papel: "suporte" }]),
  ASSETS: { fetch: async () => new Response(JSON.stringify({ versao: "0.9.22" }), { status: 200 }) },
};
const deps = { github, chamarMP, chavesDoAccess: async () => [jwkPublica], agora: () => relogio };

async function admin(metodo, caminho, { email = "dono@paulus.ia.br", corpo, cookie = "", semAccess = false, envUsado = env } = {}) {
  const headers = { "content-type": "application/json" };
  if (!semAccess) headers["cf-access-jwt-assertion"] = typeof email === "string" && email.includes(".") && email.split(".").length === 3 && !email.includes("@") ? email : await jwt(email);
  if (cookie) headers.cookie = "pv_admin=" + cookie;
  const req = new Request("https://paulus.ia.br" + caminho, { method: metodo, headers, body: corpo ? JSON.stringify(corpo) : undefined });
  return atenderAdmin(req, envUsado, new URL(req.url), { waitUntil() {} }, deps);
}

// ------------------------------------------------------------ as portas
console.log("portas");
let r = await admin("GET", "/api/admin/sessao", { semAccess: true });
let d = await r.json();
checar(r.status === 200 && !d.access.ok && !d.pronto, "sessao sem o Access: 200, nada liberado", d);
r = await admin("GET", "/api/admin/visao", { semAccess: true });
checar(r.status === 401, "visao sem o Access: 401");
r = await admin("GET", "/api/admin/visao", { envUsado: { ...env, ACCESS_AUD: "" } });
checar(r.status === 503, "sem ACCESS_AUD configurado o painel fica fechado");
const outroTime = await jwt("dono@paulus.ia.br", { iss: "https://outro.cloudflareaccess.com" });
r = await admin("GET", "/api/admin/visao", { email: outroTime });
checar(r.status === 401, "JWT de outro time do Access: 401");
const adulterado = (await jwt("dono@paulus.ia.br")).replace(/\.[^.]+$/, ".AAAA");
r = await admin("GET", "/api/admin/visao", { email: adulterado });
checar(r.status === 401, "JWT com a assinatura errada: 401");
r = await admin("GET", "/api/admin/visao", { email: "intruso@gmail.com" });
checar(r.status === 403, "e-mail fora da equipe: 403");
r = await admin("GET", "/api/admin/visao");
d = await r.json();
checar(r.status === 401 && d.passo === "github", "com o Access e sem o GitHub: 401 passo github", d);

r = await admin("GET", "/api/admin/github/entrar");
const loc = new URL(r.headers.get("location"));
const state = loc.searchParams.get("state");
checar(r.status === 302 && loc.hostname === "github.com" && loc.searchParams.get("scope") === "public_repo read:user", "entrar com o GitHub: 302 com o escopo do repositorio");
r = await admin("GET", "/api/admin/github/retorno?code=bom&state=errado");
checar(r.status === 302 && r.headers.get("location").includes("erro="), "state errado volta com erro");
permissao = "read";
r = await admin("GET", "/api/admin/github/retorno?code=bom&state=" + state);
checar(r.headers.get("location").includes("escrita"), "conta sem escrita no repositorio nao entra", r.headers.get("location"));
permissao = "write";
r = await admin("GET", "/api/admin/github/entrar");
const state2 = new URL(r.headers.get("location")).searchParams.get("state");
r = await admin("GET", "/api/admin/github/retorno?code=bom&state=" + state2, { email: "suporte@paulus.ia.br" });
checar(r.headers.get("location").includes("erro="), "o state de uma pessoa nao serve para outra");
r = await admin("GET", "/api/admin/github/entrar");
const state3 = new URL(r.headers.get("location")).searchParams.get("state");
r = await admin("GET", "/api/admin/github/retorno?code=bom&state=" + state3);
const sessao = (r.headers.get("set-cookie") || "").match(/pv_admin=([0-9a-f]+)/)?.[1];
checar(r.status === 302 && r.headers.get("location") === "/admin/" && sessao && /HttpOnly; Secure; SameSite=Lax/.test(r.headers.get("set-cookie")), "login completo: cookie HttpOnly e volta ao painel");
r = await admin("GET", "/api/admin/visao", { email: "suporte@paulus.ia.br", cookie: sessao });
checar(r.status === 401, "o cookie de uma pessoa nao vale com o Access de outra");
r = await admin("GET", "/api/admin/sessao", { cookie: sessao });
d = await r.json();
checar(d.pronto && d.papel === "dono" && d.github.login === "matheus" && d.worker === "0.9.22" && d.config.nfse.ligado === false, "sessao pronta, papel e o que falta configurar", d);
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
await CONTAS_IA.get(idAna).fetch("https://conta-ia/creditar", { method: "POST", body: JSON.stringify({ acao: "creditar", pedido: "ORD1", valor: 50 }) });
r = await admin("GET", "/api/admin/contas", como());
d = await r.json();
checar(d.contas.length === 2 && d.contas.every((c) => c.email.endsWith("@escritorio.com.br") && !c._d), "lista as contas da nuvem (sem o detalhe cru)", d.contas);
r = await admin("GET", "/api/admin/contas/" + idAna, como());
d = await r.json();
checar(d.pagamentos.length === 1 && d.pagamentos[0].valor === 50 && d.instalacoes.length === 1 && d.instalacoes[0].hash8.length === 8, "detalhe da conta: pagamentos e instalacoes", d);
const hash8 = d.instalacoes[0].hash8;
r = await admin("GET", "/api/admin/visao", como());
d = await r.json();
checar(d.kpi.contas === 2 && d.kpi.receita_recargas === 50 && d.dias.length === 42, "visao geral: contas, receita do mes e 14 dias x 3 turnos", d.kpi);
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
r = await admin("POST", "/api/admin/alteracoes", como({ corpo: { tipo: "cupom.criar", dados: { codigo: "piloto30", desconto: 30, meses: 3, brinde: 5, limite: 10, planos: [] }, texto: "Criei PILOTO30" } }));
r = await admin("POST", "/api/admin/alteracoes", como({ corpo: { tipo: "plano.editar", dados: { id: "escritorio", valor: 320, tokens: 32 }, texto: "Escritório a R$ 320" } }));
r = await admin("POST", "/api/admin/alteracoes", como({ corpo: { tipo: "coisa.estranha", dados: {} } }));
checar(r.status === 400, "tipo desconhecido e recusado");
r = await admin("POST", "/api/admin/alteracoes", como({ corpo: { tipo: "cupom.criar", dados: { codigo: "x", desconto: 10, meses: 1 } } }));
checar(r.status === 400, "codigo de cupom invalido e recusado antes da fila");
r = await admin("POST", "/api/admin/publicar", como({ corpo: { confirmacao: "commitar e pushar" } }));
checar(r.status === 400, "publicar com a frase errada nao publica");
r = await admin("POST", "/api/admin/publicar", como({ corpo: { confirmacao: "comitar e pushar" } }));
d = await r.json();
checar(d.ok && d.resultados.length === 4 && d.publicacao.n === 4, "publicar aplica as quatro", d);
resumoBruno = await (await CONTAS_IA.get(idBruno).fetch("https://conta-ia/resumo", { method: "POST", body: JSON.stringify({ acao: "resumo" }) })).json();
checar(resumoBruno.recargas.length === 1 && resumoBruno.recargas[0].tokens === 1000, "depois de publicar, os tokens estao na conta");
const resumoAna = await (await CONTAS_IA.get(idAna).fetch("https://conta-ia/resumo", { method: "POST", body: JSON.stringify({ acao: "resumo" }) })).json();
checar(resumoAna.instalacoes === 0, "a instalacao da Ana saiu");
r = await (await fetch("https://nada")).status; // so para nao ficar fetch pendurado
const cupom = JSON.parse(guardados.get("admin:cupom:PILOTO30"));
checar(cupom.ativo && cupom.desconto === 30 && cupom.brinde === 5e6, "cupom gravado em maiusculas com o brinde em tokens", cupom);
const planosKV = JSON.parse(guardados.get("admin:planos"));
checar(planosKV.find((p) => p.id === "escritorio").valor === 320 && planosKV.find((p) => p.id === "escritorio").tokens === 32e6, "plano editado no KV", planosKV);
r = await admin("GET", "/api/admin/alteracoes", como());
d = await r.json();
checar(!d.pendentes.length && d.publicacoes.length === 1, "fila vazia e a publicacao no historico");

// papel
r = await admin("GET", "/api/admin/github/entrar", { email: "suporte@paulus.ia.br" });
const st = new URL(r.headers.get("location")).searchParams.get("state");
r = await admin("GET", "/api/admin/github/retorno?code=bom&state=" + st, { email: "suporte@paulus.ia.br" });
const sessaoSuporte = (r.headers.get("set-cookie") || "").match(/pv_admin=([0-9a-f]+)/)?.[1];
r = await admin("POST", "/api/admin/alteracoes", { email: "suporte@paulus.ia.br", cookie: sessaoSuporte, corpo: { tipo: "conta.creditar", dados: { id: idAna, tokens: 5 } } });
checar(r.status === 403, "suporte nao credita tokens");
r = await admin("POST", "/api/admin/alteracoes", { email: "suporte@paulus.ia.br", cookie: sessaoSuporte, corpo: { tipo: "equipe.papel", dados: { email: "dono@paulus.ia.br", papel: "suporte" } } });
checar(r.status === 403, "suporte nao muda papeis");

// --------------------------------------------------------- e-mail e campanhas
console.log("e-mail");
r = await admin("POST", "/api/admin/campanhas/teste", como({ corpo: { campanha: { assunto: "Olá {nome}", titulo: "Novidade", texto: "Oi {nome}, tudo bem?" } } }));
checar(r.status === 200 && emails.length === 1 && emails[0].to[0] === "dono@paulus.ia.br" && emails[0].subject.startsWith("[teste]"), "e-mail de teste vai para quem esta na sessao", emails[0]);
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
const ab = await admin("GET", "/api/e/" + idCamp + "/" + t + "/a.gif", { semAccess: true });
await admin("GET", "/api/e/" + idCamp + "/" + t + "/a.gif", { semAccess: true });
const cl = await admin("GET", "/api/e/" + idCamp + "/" + t + "/c", { semAccess: true });
const depois = JSON.parse(guardados.get("admin:campanha:" + idCamp));
checar(ab.headers.get("content-type") === "image/gif" && cl.status === 302 && cl.headers.get("location") === "https://paulus.ia.br/" && depois.abertos === 1 && depois.cliques === 1, "abertura conta uma vez; clique redireciona", depois);
checar(htmlDoEmail({ titulo: "<b>", texto: "a\n\nb" }).includes("&lt;b&gt;"), "o HTML do e-mail escapa o texto");

// --------------------------------------------------------- renovacoes
console.log("renovacoes");
await CONTAS_IA.get(idBruno).fetch("https://conta-ia/assinatura", { method: "POST", body: JSON.stringify({ acao: "assinatura", assinatura: { id: "pre1", situacao: "authorized", valor: 300 } }) });
relogio += 40 * 24 * 3600 * 1000;
r = await admin("GET", "/api/admin/renovacoes", como());
d = await r.json();
checar(d.abertas.length === 1 && d.abertas[0].id === idBruno && d.abertas[0].dias_vencido >= 1, "ciclo vencido aparece em nao renovacoes", d);
emails.length = 0;
r = await admin("POST", "/api/admin/renovacoes/" + idBruno + "/lembrete", como());
d = await r.json();
checar(emails.length === 1 && emails[0].to[0] === "bruno@escritorio.com.br" && d.abertas[0].lembrete_em, "lembrete enviado e anotado");
r = await admin("POST", "/api/admin/renovacoes/" + idBruno + "/tratar", como());
d = await r.json();
checar(!d.abertas.length && d.tratadas.length === 1, "marcar como tratada");

// --------------------------------------------------------- materiais
console.log("materiais");
const textoMat = "Este modelo de contrato de honorários traz as cláusulas usuais. ".repeat(6) + " CPF 123.456.789-09 e processo 0001234-56.2024.8.13.0024.";
const semSegredo = await atenderAdmin(new Request("https://paulus.ia.br/api/materiais/enviar", { method: "POST", body: "{}" }), env, new URL("https://paulus.ia.br/api/materiais/enviar"), {}, deps);
checar(semSegredo.status === 401, "enviar material sem o segredo da nuvem: 401");
const reqMat = new Request("https://paulus.ia.br/api/materiais/enviar", { method: "POST", headers: { authorization: "Bearer " + segredos.bruno, "content-type": "application/json" },
  body: JSON.stringify({ titulo: "Contrato de honorários", autor: "Bruno", tipo: "modelo", texto: textoMat, areas: ["civil"] }) });
r = await atenderAdmin(reqMat, env, new URL(reqMat.url), {}, deps);
d = await r.json();
checar(r.status === 200 && d.situacao === "fila", "material enviado pelo PAULUS entra na fila", d);
r = await admin("GET", "/api/admin/materiais", como());
const mats = (await r.json()).materiais;
checar(mats.length === 1 && mats[0].varredura.cpf === 1 && mats[0].varredura.processo === 1, "a varredura acha o CPF e o processo", mats[0] && mats[0].varredura);
r = await admin("POST", "/api/admin/alteracoes", como({ corpo: { tipo: "material.situacao", dados: { id: mats[0].id, situacao: "publicado" }, texto: "Publiquei o contrato" } }));
r = await admin("POST", "/api/admin/publicar", como({ corpo: { confirmacao: "comitar e pushar" } }));
d = await r.json();
checar(d.ok && d.publicacao.commit === "abcdef1" && materiaisJson.materiais[0].slug === "contrato-de-honorarios" && ghCommits.length === 2, "publicar material grava o .md e a lista pelo GitHub", { d, ghCommits });
checar(varredura("CNPJ 12.345.678/0001-90").cnpj === 1 && varredura("CNPJ 12.345.678/0001-90").cpf === 0, "CNPJ nao conta como CPF");

// --------------------------------------------------------- NFS-e e equipe
console.log("nfse e equipe");
r = await admin("GET", "/api/admin/nfse", como());
d = await r.json();
checar(!d.emissor.ligado && d.fatos.some((f) => f.k === "Emissor" && f.v.includes("falta NFSE_CASA_TOKEN")), "NFS-e sem o token: ponte desligada", d.fatos);
r = await admin("GET", "/api/admin/nfse", { ...como(), envUsado: { ...env, NFSE_CASA_TOKEN: "t" } });
d = await r.json();
checar(d.emissor.ligado && d.fatos.some((f) => f.k === "Emissor" && f.v === "PAULUS da casa · nunca conectou"), "com o token e sem conexao: nunca conectou", d.fatos);
guardados.set("admin:nfse-casa:visto", "2026-10-03T15:00:00.000Z");
r = await admin("GET", "/api/admin/nfse", { ...como(), envUsado: { ...env, NFSE_CASA_TOKEN: "t" } });
d = await r.json();
checar(d.fatos.some((f) => f.k === "Emissor" && f.v.startsWith("PAULUS da casa · última conexão 03/10/2026")), "e a ultima conexao da casa", d.fatos);
guardados.delete("admin:nfse-casa:visto");
checar(d.config.mail === false, "o interruptor do e-mail da nota comeca desligado", d.config);
r = await admin("POST", "/api/admin/alteracoes", como({ corpo: { tipo: "nfse.config", dados: { auto: true, email: false, mail: true }, texto: "Liguei: mandar também por e-mail" } }));
r = await admin("POST", "/api/admin/publicar", como({ corpo: { confirmacao: "comitar e pushar" } }));
d = await r.json();
checar(d.ok && JSON.stringify(JSON.parse(guardados.get("admin:nfse:config"))) === JSON.stringify({ auto: true, email: false, mail: true }), "nfse.config grava os tres interruptores (auto, email, mail)", { d, cfg: guardados.get("admin:nfse:config") });
r = await admin("GET", "/api/admin/nfse", como());
d = await r.json();
checar(d.config.mail === true && d.config.auto === true, "e o painel le o mail de volta", d.config);
guardados.delete("admin:nfse:config");
r = await admin("POST", "/api/admin/alteracoes", como({ corpo: { tipo: "nfse.emitir", dados: { ids: ["x"] }, texto: "Emiti" } }));
r = await admin("POST", "/api/admin/publicar", como({ corpo: { confirmacao: "comitar e pushar" } }));
d = await r.json();
checar(!d.ok && d.resultados[0].erro.includes("Notas do PAVLVS"), "o painel nao emite: diz que e no PAULUS da casa", d);
await admin("DELETE", "/api/admin/alteracoes/" + d.resultados[0].id, como());
r = await admin("POST", "/api/admin/alteracoes", como({ corpo: { tipo: "equipe.papel", dados: { email: "dono@paulus.ia.br", papel: "suporte" }, texto: "Rebaixei o dono" } }));
r = await admin("POST", "/api/admin/publicar", como({ corpo: { confirmacao: "comitar e pushar" } }));
d = await r.json();
checar(!d.ok && d.resultados[0].erro.includes("pelo menos um dono"), "a equipe nao fica sem dono", d);
r = await admin("GET", "/api/admin/equipe", como());
d = await r.json();
checar(d.membros.length === 2 && d.matriz.length >= 6, "equipe e matriz de permissoes");

// --------------------------------------------------------- privacidade
const pessoais = [...guardados.entries()].filter(([k]) => !k.startsWith("admin:"));
checar(!pessoais.length, "o painel so grava chaves admin: no APOIOS", pessoais.map(([k]) => k));

r = await admin("POST", "/api/admin/sair", como());
checar(r.status === 200 && /Max-Age=0/.test(r.headers.get("set-cookie")) && !guardados.has("admin:sessao:" + sessao), "sair apaga a sessao");

console.log(falhas ? `\n  ${falhas} falha(s)` : "\n  painel admin: todos os testes passaram");
process.exit(falhas ? 1 : 0);
