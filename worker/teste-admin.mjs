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
async function chamarMP(env, caminho, metodo, corpo, extra = {}) {
  mp.push({ caminho, metodo, corpo, extra });
  // A cobranca da assinatura traz o pagamento dela (o reembolso da mensalidade).
  if (/^\/authorized_payments\//.test(caminho)) return { ok: true, status: 200, dados: { id: caminho.split("/").pop(), payment: { id: 555 } } };
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
checar(d.pronto && d.papel === "dono" && d.github.login === "matheus" && d.worker === "0.9.22" && d.config.nfse.ligado === false && d.config.nfse.falta.includes("EMISSOR_NFSE") && d.config.tuneis.ligado === false, "sessao pronta, papel e o que falta configurar (sem o DO, o emissor de NFS-e diz que falta)", d);
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
r = await admin("POST", "/api/admin/alteracoes", como({ corpo: { tipo: "plano.editar", dados: { id: "escritorio", valor: 320, valor_anual: 3200, tokens: 32 }, texto: "Escritório a R$ 320" } }));
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
checar(planosKV.find((p) => p.id === "escritorio").valor === 320 && planosKV.find((p) => p.id === "escritorio").valor_anual === 3200 && planosKV.find((p) => p.id === "escritorio").tokens === 32e6, "plano editado no KV, com o valor do ano", planosKV);
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
checar(r.status === 200 && !d.emissor.ligado && d.emissor.falta.includes("EMISSOR_NFSE") && Array.isArray(d.notas) && Array.isArray(d.pagamentos) && d.pode.emitir === true,
  "sem o DO do emissor: a aba abre e diz o que falta (o resto em teste-nfse-admin.mjs)", d);
r = await admin("POST", "/api/admin/nfse/emissor/notas", como({ corpo: { valor: 1 } }));
d = await r.json();
checar(r.status === 503 && d.erro.includes("EMISSOR_NFSE"), "emitir sem o DO: 503 dizendo o que falta", d);
r = await admin("POST", "/api/admin/alteracoes", como({ corpo: { tipo: "nfse.config", dados: { auto: true, email: false, mail: true }, texto: "Liguei: mandar também por e-mail" } }));
r = await admin("POST", "/api/admin/publicar", como({ corpo: { confirmacao: "comitar e pushar" } }));
d = await r.json();
checar(d.ok && JSON.stringify(JSON.parse(guardados.get("admin:nfse:config"))) === JSON.stringify({ auto: true, email: false, mail: true }), "nfse.config grava os tres interruptores (auto, email, mail)", { d, cfg: guardados.get("admin:nfse:config") });
r = await admin("GET", "/api/admin/nfse", como());
d = await r.json();
checar(d.config.mail === true && d.config.auto === true, "e o painel le o mail de volta", d.config);
guardados.delete("admin:nfse:config");
r = await admin("POST", "/api/admin/alteracoes", como({ corpo: { tipo: "nfse.emitir", dados: { ids: ["x"] }, texto: "Emiti" } }));
checar(r.status === 400, "nfse.emitir saiu da fila: emitir e na hora, pelo emissor");
r = await admin("POST", "/api/admin/alteracoes", como({ corpo: { tipo: "equipe.papel", dados: { email: "dono@paulus.ia.br", papel: "suporte" }, texto: "Rebaixei o dono" } }));
r = await admin("POST", "/api/admin/publicar", como({ corpo: { confirmacao: "comitar e pushar" } }));
d = await r.json();
checar(!d.ok && d.resultados[0].erro.includes("pelo menos um dono"), "a equipe nao fica sem dono", d);
r = await admin("GET", "/api/admin/equipe", como());
d = await r.json();
checar(d.membros.length === 2 && d.matriz.length >= 6, "equipe e matriz de permissoes");

// ----------------------------------------------------------- reembolso
console.log("reembolso");
const contaDo = (id, acao, dados = {}) => CONTAS_IA.get(id).fetch("https://conta-ia/" + acao, { method: "POST", body: JSON.stringify({ acao, ...dados }) }).then((x) => x.json());
for (const quem of ["carla", "dani"]) await ia("/api/ia/ativar", { id_token: quem, instalacao_id: "inst-" + quem + "-123", nome_escritorio: "Escritório " + quem });
const idCarla = (await (await ia("/api/ia/ativar", { id_token: "carla", instalacao_id: "inst-carla-123" })).json()).segredo.split("_")[1];
const idDani = (await (await ia("/api/ia/ativar", { id_token: "dani", instalacao_id: "inst-dani-123" })).json()).segredo.split("_")[1];
// Carla: um mês no Pix e uma recarga; Dani: a assinatura mensal no cartão, com a primeira cobrança.
let rc = await contaDo(idCarla, "anual_pago", { pagamento: "PAYMES1", plano: "advogado", valor: 449, meses: 1 });
checar(rc.plano_vigente && rc.periodo === "avulso", "Carla com o mês no Pix", rc.periodo);
guardados.set("admin:nfse:PAYMES1", JSON.stringify({ id: "PAYMES1", conta: idCarla, tipo: "mês avulso", valor: 449, quando: new Date(relogio).toISOString(), nota: "pendente" }));
rc = await contaDo(idCarla, "creditar", { pedido: "ORD9", valor: 120, plano: "advogado" });
const extraAntes = (await contaDo(idCarla, "admin_detalhe")).extra;
await contaDo(idDani, "assinatura", { plano: "advogado", assinatura: { id: "preDani", situacao: "authorized", valor: 449 } });
let rd = await contaDo(idDani, "renovar", { cobranca: "COB1", valor: 449, quando: new Date(relogio).toISOString() });
checar(rd.plano_vigente, "Dani com a mensalidade paga", rd.ciclo);
const fila = async () => (await (await admin("GET", "/api/admin/alteracoes", como())).json()).pendentes;
for (const x of await fila()) await admin("DELETE", "/api/admin/alteracoes/" + x.id, como());
const reemb = (id, pagamento) => admin("POST", "/api/admin/alteracoes", como({ corpo: { tela: "contas", tipo: "conta.reembolsar", alvo: id + ":" + pagamento, dados: { id, pagamento }, texto: "Reembolsei " + pagamento } }));
checar((await reemb(idCarla, "NAOEXISTE")).status === 400, "reembolsar pagamento que não é da conta: recusado na fila");
checar((await reemb(idCarla, "PAYMES1")).status === 200 && (await reemb(idCarla, "ORD9")).status === 200 && (await reemb(idDani, "COB1")).status === 200, "três reembolsos na fila");
let antesMP = mp.length;
checar(!(await contaDo(idCarla, "resumo")).pagamentos, "na fila, nada mudou ainda");
r = await admin("POST", "/api/admin/publicar", como({ corpo: { confirmacao: "comitar e pushar" } }));
d = await r.json();
checar(d.ok && d.resultados.length === 3, "publicar aplica os três", d);
const feitos = mp.slice(antesMP);
checar(feitos.some((x) => x.caminho === "/v1/payments/PAYMES1/refunds" && x.metodo === "POST" && x.extra["X-Idempotency-Key"] === "reembolso-PAYMES1"),
  "o mês no Pix volta pelo /v1/payments/<id>/refunds, com a chave de idempotência do pagamento", feitos);
checar(feitos.some((x) => x.caminho === "/v1/orders/ORD9/refund"), "a recarga volta pelo /v1/orders/<id>/refund", feitos);
checar(feitos.some((x) => x.caminho === "/authorized_payments/COB1") && feitos.some((x) => x.caminho === "/v1/payments/555/refunds")
  && feitos.some((x) => x.caminho === "/preapproval/preDani" && x.corpo.status === "cancelled"), "a mensalidade: acha o pagamento da cobrança, devolve e cancela a assinatura", feitos);
const dc = await contaDo(idCarla, "admin_detalhe");
checar(!dc.plano_vigente && dc.assinatura.situacao === "refunded" && dc.pagamentos.find((x) => x.ref === "PAYMES1").reembolso.por === "dono@paulus.ia.br",
  "Carla: o mês acaba na hora e o pagamento fica marcado com quem devolveu", dc.assinatura);
checar(extraAntes > 0 && dc.extra === 0 && dc.pagamentos.find((x) => x.ref === "ORD9").tokens_tirados === extraAntes, "a recarga devolvida sai dos créditos", { antes: extraAntes, depois: dc.extra, pg: dc.pagamentos.find((x) => x.ref === "ORD9") });
checar(JSON.parse(guardados.get("admin:nfse:PAYMES1")).nota === "reembolsado", "a fila de notas não pede nota do pagamento devolvido");
const dd = await contaDo(idDani, "admin_detalhe");
checar(!dd.plano_vigente && dd.assinatura.situacao === "cancelled", "Dani: a assinatura cancelada e o ciclo pago fechado", { a: dd.assinatura, c: dd.ciclo });
checar((await reemb(idCarla, "PAYMES1")).status === 400, "reembolsar de novo: recusado");
// O aviso do estorno, que o Mercado Pago manda depois, não mexe de novo.
const estornoDepois = await contaDo(idCarla, "anual_estornado", { pagamento: "PAYMES1" });
checar(estornoDepois.assinatura.situacao === "refunded", "o aviso do estorno depois do painel não muda nada");
d = await (await admin("GET", "/api/admin/visao", como())).json();
checar((d.avisos || []).some((x) => x.tipo === "reembolso" && x.texto.startsWith("Reembolso pelo painel")), "o reembolso aparece nos avisos da visão geral", d.avisos);
// O suporte não reembolsa.
r = await admin("POST", "/api/admin/alteracoes", { email: "suporte@paulus.ia.br", corpo: { tipo: "conta.reembolsar", dados: { id: idCarla, pagamento: "ORD9" } } });
checar(r.status === 401 || r.status === 403, "o suporte não reembolsa", r.status);

// --------------------------------------------------------- privacidade
const pessoais = [...guardados.entries()].filter(([k]) => !k.startsWith("admin:"));
checar(!pessoais.length, "o painel so grava chaves admin: no APOIOS", pessoais.map(([k]) => k));

r = await admin("POST", "/api/admin/sair", como());
checar(r.status === 200 && /Max-Age=0/.test(r.headers.get("set-cookie")) && !guardados.has("admin:sessao:" + sessao), "sair apaga a sessao");

console.log(falhas ? `\n  ${falhas} falha(s)` : "\n  painel admin: todos os testes passaram");
process.exit(falhas ? 1 : 0);
