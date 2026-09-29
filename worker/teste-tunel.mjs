// Teste do acesso de fora no Worker (worker/tunel.js), sem rede:
//   node worker/teste-tunel.mjs      (o teste.mjs tambem chama este)
//
// A API da Cloudflare e o Turnstile sao de mentira: o fetch global responde
// como eles responderiam. O token de Turnstile "ok:<hostname>" passa como
// resolvido naquele hostname; qualquer outro, nao.
import worker from "./index.js";
import { limparEscritorios } from "./tunel.js";

let falhas = 0;
const checar = (ok, descricao, detalhe) => {
  console.log((ok ? "  ok   " : "  FALHA ") + descricao + (ok || detalhe === undefined ? "" : "  -> " + JSON.stringify(detalhe)));
  if (!ok) falhas++;
};

// ----------------------------------------------------------- o KV de mentira
function kv() {
  const m = new Map();
  return {
    m,
    get: async (k) => (m.has(k) ? m.get(k) : null),
    put: async (k, v) => { m.set(k, v); },
    delete: async (k) => { m.delete(k); },
    list: async ({ prefix }) => ({ list_complete: true, keys: [...m.keys()].filter((k) => k.startsWith(prefix)).map((name) => ({ name })) }),
  };
}

// ------------------------------------ a Cloudflare e o Turnstile de mentira
const chamadas = [];
const conta = { tuneis: new Map(), dns: new Map() };
let falharEm = "";
let seq = 0;
const ok = (result) => new Response(JSON.stringify({ success: true, errors: [], messages: [], result }), { status: 200 });
const erro = (msg) => new Response(JSON.stringify({ success: false, errors: [{ message: msg }], result: null }), { status: 400 });

// O Google de mentira: um par de chaves RSA deste teste assina os id_tokens,
// e a chave publica sai em /oauth2/v3/certs, como a do Google.
const parGoogle = await crypto.subtle.generateKey({ name: "RSASSA-PKCS1-v1_5", modulusLength: 2048, publicExponent: new Uint8Array([1, 0, 1]), hash: "SHA-256" }, true, ["sign", "verify"]);
const jwkGoogle = { ...(await crypto.subtle.exportKey("jwk", parGoogle.publicKey)), kid: "chave-1", use: "sig", alg: "RS256" };
const CLIENTE = "cliente-desktop.apps.googleusercontent.com";
const b64 = (x) => Buffer.from(typeof x === "string" ? x : JSON.stringify(x)).toString("base64url");
async function idToken(campos = {}, { chave = parGoogle.privateKey, kid = "chave-1" } = {}) {
  const info = { iss: "https://accounts.google.com", aud: CLIENTE, sub: "111", email: "Dono@Gmail.com", email_verified: true,
    exp: Math.floor(Date.now() / 1000) + 3600, ...campos };
  const corpo = b64({ alg: "RS256", kid, typ: "JWT" }) + "." + b64(info);
  const ass = await crypto.subtle.sign("RSASSA-PKCS1-v1_5", chave, new TextEncoder().encode(corpo));
  return corpo + "." + Buffer.from(ass).toString("base64url");
}

globalThis.fetch = async (url, opcoes = {}) => {
  const u = String(url);
  const metodo = (opcoes.method || "GET").toUpperCase();
  if (u === "https://www.googleapis.com/oauth2/v3/certs") return new Response(JSON.stringify({ keys: [jwkGoogle] }));
  if (u === "https://challenges.cloudflare.com/turnstile/v0/siteverify") {
    const corpo = new URLSearchParams(String(opcoes.body));
    const token = corpo.get("response") || "";
    chamadas.push("SITEVERIFY " + token);
    if (corpo.get("secret") !== "segredo-turnstile") return new Response(JSON.stringify({ success: false, "error-codes": ["invalid-input-secret"] }));
    if (token.startsWith("ok:")) return new Response(JSON.stringify({ success: true, hostname: token.slice(3) }));
    return new Response(JSON.stringify({ success: false, "error-codes": ["invalid-input-response"] }));
  }
  if (!u.startsWith("https://api.cloudflare.com/client/v4/")) return new Response("{}", { status: 404 });
  const caminho = u.replace("https://api.cloudflare.com/client/v4", "");
  const corpo = opcoes.body ? JSON.parse(opcoes.body) : null;
  chamadas.push(metodo + " " + caminho);
  if (falharEm && (metodo + " " + caminho).includes(falharEm)) return erro("falha simulada em " + falharEm);
  let m;
  if (metodo === "POST" && /\/cfd_tunnel$/.test(caminho)) { const id = "tun-" + (++seq); conta.tuneis.set(id, { ...corpo, status: "inactive" }); return ok({ id, name: corpo.name }); }
  if (metodo === "PUT" && (m = caminho.match(/\/cfd_tunnel\/([^/]+)\/configurations$/))) { conta.tuneis.get(m[1]).config = corpo.config; return ok({}); }
  if (metodo === "GET" && (m = caminho.match(/\/cfd_tunnel\/([^/]+)\/token$/))) return ok("token-do-" + m[1]);
  if (metodo === "GET" && (m = caminho.match(/\/cfd_tunnel\/([^/]+)$/))) {
    const t = conta.tuneis.get(m[1]);
    return t ? ok({ id: m[1], status: t.status, conns_inactive_at: t.conns_inactive_at || null }) : erro("túnel não existe");
  }
  if (metodo === "DELETE" && (m = caminho.match(/\/cfd_tunnel\/([^/]+)\/connections$/))) return ok({});
  if (metodo === "DELETE" && (m = caminho.match(/\/cfd_tunnel\/([^/]+)$/))) { conta.tuneis.delete(m[1]); return ok({}); }
  if (metodo === "POST" && /\/dns_records$/.test(caminho)) { const id = "dns-" + (++seq); conta.dns.set(id, corpo); return ok({ id }); }
  if (metodo === "DELETE" && (m = caminho.match(/\/dns_records\/([^/]+)$/))) { conta.dns.delete(m[1]); return ok({}); }
  return erro("rota da API não simulada: " + metodo + " " + caminho);
};

function ambiente(extra = {}) {
  return {
    TUNEL_ATIVO: "1", ESCRITORIOS: kv(), CF_API_TOKEN: "t", CF_ACCOUNT_ID: "conta1", CF_ZONE_ID: "zona1",
    TURNSTILE_SECRET: "segredo-turnstile", TURNSTILE_SITEKEY: "chave-publica-do-widget", MAX_ESCRITORIOS: "3",
    ASSETS: { fetch: async () => new Response("site", { status: 200 }) },
    ...extra,
  };
}

const pedir = (env, caminho, { metodo = "GET", corpo, cab = {} } = {}) =>
  worker.fetch(new Request("https://paulus.ia.br" + caminho, {
    method: metodo, headers: cab, body: corpo === undefined ? undefined : (typeof corpo === "string" ? corpo : JSON.stringify(corpo)),
  }), env, { waitUntil() {} });

async function lerResposta(r) {
  const t = await r.text();
  try { return JSON.parse(t); } catch (e) { return { texto: t }; }
}

async function disponivel(env, nome, instalacao = "") {
  return lerResposta(await pedir(env, "/api/tunel/disponivel?nome=" + encodeURIComponent(nome) + (instalacao ? "&instalacao=" + instalacao : "")));
}

async function iniciar(env, slug, instalacao = "inst-00000001", nome = "Moura & Associados Advocacia") {
  const r = await pedir(env, "/api/tunel/iniciar", { metodo: "POST", corpo: { instalacao_id: instalacao, nome_escritorio: nome, slug, porta: 47123 } });
  return { status: r.status, dados: await lerResposta(r) };
}

function confirmar(env, codigo, token) {
  const corpo = "c=" + codigo + (token === undefined ? "" : "&cf-turnstile-response=" + encodeURIComponent(token));
  return pedir(env, "/conectar", { metodo: "POST", corpo, cab: { "content-type": "application/x-www-form-urlencoded", "cf-connecting-ip": "200.1.2.3" } });
}

async function conectar(env, slug, instalacao, nome) {
  const i = await iniciar(env, slug, instalacao, nome);
  await confirmar(env, i.dados.codigo_usuario, "ok:paulus.ia.br");
  return (await pedir(env, "/api/tunel/estado", { metodo: "POST", corpo: { codigo_dispositivo: i.dados.codigo_dispositivo } })).json();
}

const bearer = (s) => ({ authorization: "Bearer " + s, "content-type": "application/json" });

console.log("\nsem TUNEL_ATIVO, nada existe");
{
  const env = ambiente({ TUNEL_ATIVO: undefined });
  checar((await pedir(env, "/api/tunel/disponivel?nome=moura")).status === 404, "disponivel: 404");
  checar((await iniciar(env, "moura")).status === 404, "iniciar: 404");
  checar((await pedir(env, "/conectar?c=ABCD-EFGH")).status === 404, "conectar: 404");
  checar((await pedir(ambiente({ ESCRITORIOS: undefined }), "/api/tunel/estado", { metodo: "POST", corpo: {} })).status === 404, "sem o KV: 404");
  const limpeza = await limparEscritorios(env);
  checar(limpeza.removidos.length === 0 && chamadas.length === 0, "e a limpeza não faz nada");
}

console.log("\no nome");
const env = ambiente();
{
  const www = await disponivel(env, "www");
  checar(www.disponivel === false && www.motivo.includes("reservado") && www.sugestao === "www-2", "reservado: recusado, com sugestão", www);
  const atos = await disponivel(env, "atos");
  checar(atos.disponivel === false && atos.motivo.includes("reservado"), "“atos” é reservado");
  const torto = await disponivel(env, "Moura_Advogados");
  checar(torto.disponivel === false && torto.motivo.includes("minúsculas") && torto.sugestao === "moura-advogados", "formato inválido: diz o porquê e sugere", torto);
  const curto = await disponivel(env, "ab");
  checar(curto.disponivel === false && curto.motivo.includes("3"), "menos de 3 letras: recusado", curto);
  const hifen = await disponivel(env, "-moura");
  checar(hifen.disponivel === false && hifen.motivo.includes("hífen"), "hífen no começo: recusado", hifen);
  const livre = await disponivel(env, "moura-associados");
  checar(livre.disponivel === true && !livre.sugestao, "nome livre: disponível", livre);
}

console.log("\no fluxo completo");
const inicio = await iniciar(env, "moura-associados");
checar(inicio.status === 200 && /^[0-9a-f]{64}$/.test(inicio.dados.codigo_dispositivo) && /^[A-Z2-9]{4}-[A-Z2-9]{4}$/.test(inicio.dados.codigo_usuario),
  "iniciar devolve o código secreto e o código curto", inicio.dados);
checar(inicio.dados.url === "https://paulus.ia.br/conectar?c=" + inicio.dados.codigo_usuario, "e o endereço de conectar");
const reservado = await disponivel(env, "moura-associados", "inst-00000009");
checar(reservado.disponivel === false && reservado.sugestao === "moura-associados-2", "reservado por 15 min para quem iniciou; outra instalação vê em uso", reservado);
const minha = await disponivel(env, "moura-associados", "inst-00000001");
checar(minha.disponivel === true, "a própria instalação continua vendo o nome livre", minha);
const perguntar = async () => (await pedir(env, "/api/tunel/estado", { metodo: "POST", corpo: { codigo_dispositivo: inicio.dados.codigo_dispositivo } })).json();
checar((await perguntar()).estado === "pendente", "antes da confirmação: pendente");
const pagina = await pedir(env, "/conectar?c=" + inicio.dados.codigo_usuario);
const html = await pagina.text();
checar(pagina.status === 200 && html.includes("moura-associados.paulus.ia.br") && html.includes(inicio.dados.codigo_usuario)
  && html.includes('data-sitekey="chave-publica-do-widget"') && html.includes("challenges.cloudflare.com/turnstile"),
  "a página mostra o endereço, o código e o widget do Turnstile", html.slice(0, 200));
checar(!/cloudflareaccess|access/i.test(pagina.headers.get("content-security-policy") || "") && pagina.headers.get("x-frame-options") === "DENY",
  "sem Access, e com cabeçalhos de segurança");
const antes = { t: conta.tuneis.size, d: conta.dns.size };
const semTurnstile = await confirmar(env, inicio.dados.codigo_usuario);
checar(semTurnstile.status === 403 && conta.tuneis.size === antes.t && conta.dns.size === antes.d, "confirmar sem Turnstile: recusado, nada criado");
const tokenRuim = await confirmar(env, inicio.dados.codigo_usuario, "robo");
checar(tokenRuim.status === 403 && conta.tuneis.size === antes.t, "Turnstile inválido: recusado, nada criado");
const outroHost = await confirmar(env, inicio.dados.codigo_usuario, "ok:outro-site.com");
checar(outroHost.status === 403 && conta.tuneis.size === antes.t, "Turnstile resolvido em outro site: recusado");
const conf = await confirmar(env, inicio.dados.codigo_usuario, "ok:paulus.ia.br");
checar(conf.status === 200, "confirmar com Turnstile válido provisiona", await conf.clone().text().then((t) => t.slice(0, 300)));
checar(conta.tuneis.size === 1 && conta.dns.size === 1, "túnel e DNS criados", { tuneis: conta.tuneis.size, dns: conta.dns.size });
checar(!chamadas.some((c) => /\/access\//.test(c)), "nenhuma chamada ao Cloudflare Access", chamadas.filter((c) => /access/.test(c)));
const tunel = [...conta.tuneis.values()][0];
checar(tunel.config_src === "cloudflare" && tunel.config.ingress[0].hostname === "moura-associados.paulus.ia.br"
  && tunel.config.ingress[0].service === "http://127.0.0.1:47123" && tunel.config.ingress[1].service === "http_status:404",
  "túnel gerenciado remotamente, ingress para 127.0.0.1 e o resto 404", tunel);
const dns = [...conta.dns.values()][0];
checar(dns.type === "CNAME" && dns.name === "moura-associados.paulus.ia.br" && dns.proxied === true && /\.cfargotunnel\.com$/.test(dns.content),
  "CNAME com proxy para o túnel", dns);
const entrega = await perguntar();
checar(entrega.estado === "pronto" && entrega.endereco === "https://moura-associados.paulus.ia.br" && entrega.tunnel_token.startsWith("token-do-tun-")
  && entrega.turnstile_sitekey === "chave-publica-do-widget" && /^[0-9a-f]{64}$/.test(entrega.segredo_instalacao),
  "estado entrega endereço, token, sitekey e segredo", entrega);
checar(!("turnstile_secret" in entrega) && !JSON.stringify(entrega).includes("segredo-turnstile"), "o secret do Turnstile nunca vai para o PAULUS");
checar((await perguntar()).estado === "expirado", "a segunda leitura não entrega de novo");
const registro = JSON.parse(env.ESCRITORIOS.m.get("escritorio:moura-associados"));
checar(registro.hash_segredo && registro.tunnel_id && registro.dns_id && registro.instalacao_id === "inst-00000001" && registro.porta === 47123
  && registro.criado_em && "ultima_conexao" in registro, "o KV guarda túnel, DNS, instalação, porta, criação e última conexão", registro);
checar(!JSON.stringify([...env.ESCRITORIOS.m.values()]).includes(entrega.segredo_instalacao) && !JSON.stringify([...env.ESCRITORIOS.m.values()]).includes(entrega.tunnel_token),
  "só o hash do segredo fica guardado, e o token não fica");
checar(!env.ESCRITORIOS.m.has("reserva:moura-associados"), "a reserva do nome acaba quando o endereço nasce");
const tomado = await disponivel(env, "moura-associados", "inst-00000009");
checar(tomado.disponivel === false && tomado.sugestao === "moura-associados-2", "o nome conectado fica tomado, com sugestão", tomado);

console.log("\ncom o segredo da instalação");
checar((await pedir(env, "/api/tunel/situacao", { cab: bearer("0".repeat(64)) })).status === 401, "segredo errado: 401");
checar((await pedir(env, "/api/tunel/situacao")).status === 401, "sem segredo: 401");
const sit = await (await pedir(env, "/api/tunel/situacao", { cab: bearer(entrega.segredo_instalacao) })).json();
checar(sit.hostname === "moura-associados.paulus.ia.br" && sit.conectado === false, "situação: túnel ainda não conectado", sit);
const tsOk = await (await pedir(env, "/api/tunel/turnstile", { metodo: "POST", corpo: { token: "ok:moura-associados.paulus.ia.br", ip: "200.1.2.3" }, cab: bearer(entrega.segredo_instalacao) })).json();
checar(tsOk.ok === true && Object.keys(tsOk).join() === "ok", "Turnstile do próprio endereço: ok (e só ok)", tsOk);
const tsOutro = await (await pedir(env, "/api/tunel/turnstile", { metodo: "POST", corpo: { token: "ok:outro-escritorio.paulus.ia.br" }, cab: bearer(entrega.segredo_instalacao) })).json();
checar(tsOutro.ok === false, "Turnstile resolvido no endereço de outro escritório: ok false", tsOutro);
const tsRuim = await (await pedir(env, "/api/tunel/turnstile", { metodo: "POST", corpo: { token: "robo" }, cab: bearer(entrega.segredo_instalacao) })).json();
checar(tsRuim.ok === false, "Turnstile inválido: ok false");
checar(JSON.parse(env.ESCRITORIOS.m.get("escritorio:moura-associados")).ultima_conexao, "cada chamada atualiza a última conexão");
const porta = await (await pedir(env, "/api/tunel/porta", { metodo: "POST", corpo: { porta: 47200 }, cab: bearer(entrega.segredo_instalacao) })).json();
checar(porta.ok && [...conta.tuneis.values()][0].config.ingress[0].service === "http://127.0.0.1:47200", "trocar a porta atualiza o ingress");

console.log("\nlimites");
checar((await iniciar(env, "outro-nome")).status === 409, "a mesma instalação não conecta dois escritórios");
await conectar(env, "segundo-escritorio", "inst-00000002", "Segundo");
await conectar(env, "terceiro-escritorio", "inst-00000003", "Terceiro");
const quarto = await iniciar(env, "quarto-escritorio", "inst-00000004", "Quarto");
checar(quarto.status === 503 && quarto.dados.erro.includes("limite"), "MAX_ESCRITORIOS respeitado, com frase clara", quarto.dados);
const nomeTomado = await iniciar(env, "segundo-escritorio", "inst-00000005", "Quinto");
checar(nomeTomado.status === 409 && nomeTomado.dados.sugestao === "segundo-escritorio-2", "iniciar com nome tomado: 409 com sugestão", nomeTomado.dados);

console.log("\nfalha no meio desfaz o que foi feito");
{
  const env2 = ambiente({ MAX_ESCRITORIOS: "10" });
  const antes2 = { t: conta.tuneis.size, d: conta.dns.size };
  const i = await iniciar(env2, "escritorio-que-falha", "inst-00000006", "Que Falha");
  falharEm = "GET /accounts/conta1/cfd_tunnel/";
  const r = await confirmar(env2, i.dados.codigo_usuario, "ok:paulus.ia.br");
  falharEm = "";
  checar(r.status === 502, "a falha no passo do token chega como erro", r.status);
  checar(conta.tuneis.size === antes2.t && conta.dns.size === antes2.d, "túnel e DNS criados antes foram desfeitos",
    { antes: antes2, depois: { t: conta.tuneis.size, d: conta.dns.size } });
  checar(![...env2.ESCRITORIOS.m.keys()].some((k) => k.startsWith("escritorio:")), "nada ficou registrado no KV");
  falharEm = "POST /zones/zona1/dns_records";
  const r3 = await confirmar(env2, i.dados.codigo_usuario, "ok:paulus.ia.br");
  falharEm = "";
  checar(r3.status === 502 && conta.tuneis.size === antes2.t, "a falha no passo 3 (DNS) desfaz os passos 1 e 2");
}

console.log("\nremover");
{
  const antesT = conta.tuneis.size;
  const r = await (await pedir(env, "/api/tunel/remover", { metodo: "POST", cab: bearer(entrega.segredo_instalacao) })).json();
  checar(r.ok && conta.tuneis.size === antesT - 1, "remover apaga o túnel", r);
  checar(!env.ESCRITORIOS.m.has("escritorio:moura-associados"), "e o registro");
  const depois = await pedir(env, "/api/tunel/situacao", { cab: bearer(entrega.segredo_instalacao) });
  const corpo = await depois.json();
  checar(depois.status === 410 && corpo.removido === true, "o segredo passa a dizer “endereço removido” (410)", corpo);
  checar((await disponivel(env, "moura-associados")).disponivel === true, "e o nome volta a ficar disponível");
}

console.log("\na limpeza diária");
{
  const env3 = ambiente({ MAX_ESCRITORIOS: "10" });
  const agora = Date.now();
  const dia = 24 * 3600 * 1000;
  const nunca = await conectar(env3, "nunca-conectou", "inst-00000011", "Nunca");
  const parado = await conectar(env3, "parado-muito", "inst-00000012", "Parado");
  await conectar(env3, "recente", "inst-00000013", "Recente");
  const vivo = await conectar(env3, "conectado-agora", "inst-00000014", "Vivo");
  const mexer = (slug, f) => { const r = JSON.parse(env3.ESCRITORIOS.m.get("escritorio:" + slug)); f(r); env3.ESCRITORIOS.m.set("escritorio:" + slug, JSON.stringify(r)); return r; };
  mexer("nunca-conectou", (r) => { r.criado_em = new Date(agora - 8 * dia).toISOString(); r.ultima_conexao = null; });
  const rp = mexer("parado-muito", (r) => { r.criado_em = new Date(agora - 400 * dia).toISOString(); r.ultima_conexao = new Date(agora - 181 * dia).toISOString(); });
  mexer("recente", (r) => { r.criado_em = new Date(agora - 3 * dia).toISOString(); r.ultima_conexao = null; });
  const rv = mexer("conectado-agora", (r) => { r.criado_em = new Date(agora - 300 * dia).toISOString(); r.ultima_conexao = new Date(agora - 200 * dia).toISOString(); });
  conta.tuneis.get(rv.tunnel_id).status = "healthy";
  conta.tuneis.get(rp.tunnel_id).conns_inactive_at = new Date(agora - 190 * dia).toISOString();
  const feito = await limparEscritorios(env3, () => agora);
  const removidos = feito.removidos.map((x) => x.slug).sort();
  checar(JSON.stringify(removidos) === JSON.stringify(["nunca-conectou", "parado-muito"]), "remove o que nunca conectou em 7 dias e o parado há mais de 180", feito);
  checar(env3.ESCRITORIOS.m.has("escritorio:recente") && env3.ESCRITORIOS.m.has("escritorio:conectado-agora"), "preserva o recente e o conectado agora");
  const avisado = await pedir(env3, "/api/tunel/situacao", { cab: bearer(nunca.segredo_instalacao) });
  const motivo = await avisado.json();
  checar(avisado.status === 410 && motivo.motivo.includes("7 dias"), "o PAULUS do endereço liberado fica sabendo o motivo", motivo);
  checar((await disponivel(env3, "parado-muito")).disponivel === true, "o nome liberado volta a ficar disponível");
  checar(Boolean(JSON.parse(env3.ESCRITORIOS.m.get("escritorio:conectado-agora")).ultima_conexao), "o conectado agora tem a última conexão atualizada");
  const semApi = ambiente();
  semApi.ESCRITORIOS.m.set("escritorio:sem-api", JSON.stringify({ slug: "sem-api", tunnel_id: "tun-que-nao-existe", criado_em: new Date(agora - 30 * dia).toISOString(), ultima_conexao: null }));
  const f2 = await limparEscritorios(semApi, () => agora);
  checar(f2.removidos.length === 0 && semApi.ESCRITORIOS.m.has("escritorio:sem-api"), "sem resposta da API, nada é removido nesse dia");
  checar(Boolean(vivo), "(o quarto escritório conectou para o teste)");
}

console.log("\no Worker não atende *.paulus.ia.br");
{
  const r = await worker.fetch(new Request("https://moura-associados.paulus.ia.br/qualquer"), env, { waitUntil() {} });
  checar(r.status === 404, "subdomínio de escritório: 404 no Worker (o tráfego é do túnel)", r.status);
}

console.log("\na volta do Google (entrar com o Google, E3a)");
{
  const chamar = (q) => worker.fetch(new Request("https://paulus.ia.br/oauth/google?" + q), env, { waitUntil() {} });
  const r = await chamar("code=4%2Fabc&state=segundo-escritorio~xyz");
  const para = r.headers.get("location") || "";
  checar(r.status === 302 && para.startsWith("https://segundo-escritorio.paulus.ia.br/api/acesso/google/retorno?")
    && para.includes("code=4%2Fabc") && para.includes("state=segundo-escritorio%7Exyz"),
  "repassa código e state ao escritório do state", para);
  checar(r.headers.get("referrer-policy") === "no-referrer", "sem referer no repasse");
  checar((await chamar("code=x&state=nao-existe~xyz")).status === 400, "escritório que não existe: 400");
  checar((await chamar("code=x&state=..%2Fevil.com~xyz")).status === 400, "slug fora da regra: 400");
  const e = await chamar("error=access_denied&state=segundo-escritorio~xyz");
  checar(e.status === 302 && (e.headers.get("location") || "").includes("error=access_denied"), "cancelado no Google: repassa o erro");
}

console.log("\no endereço é da conta Google (retomar depois de reinstalar)");
{
  const envD = ambiente({ GOOGLE_CLIENT_IDS: "outro-cliente, " + CLIENTE, MAX_ESCRITORIOS: "20" });
  const token = await idToken();
  const iniciarCom = async (slug, instalacao, id_token) => {
    const r = await pedir(envD, "/api/tunel/iniciar", { metodo: "POST", corpo: { instalacao_id: instalacao, nome_escritorio: "Uener Advocacia", slug, porta: 47123, id_token } });
    return { status: r.status, dados: await lerResposta(r) };
  };
  const conectarCom = async (slug, instalacao, id_token) => {
    const i = await iniciarCom(slug, instalacao, id_token);
    const pag = await (await pedir(envD, "/conectar?c=" + i.dados.codigo_usuario)).text();
    await confirmar(envD, i.dados.codigo_usuario, "ok:paulus.ia.br");
    const e = await (await pedir(envD, "/api/tunel/estado", { metodo: "POST", corpo: { codigo_dispositivo: i.dados.codigo_dispositivo } })).json();
    return { i, pag, e };
  };
  const a = await conectarCom("uener", "inst-aaaaaaaa", token);
  const reg = JSON.parse(envD.ESCRITORIOS.m.get("escritorio:uener"));
  checar(a.e.estado === "pronto" && reg.dono && reg.dono.sub === "111" && reg.dono.email === "dono@gmail.com",
    "conectar com o id_token grava o dono (sub e e-mail)", reg.dono);
  checar(!a.pag.includes("Retomar"), "a primeira vez não é “retomar”");

  const semToken = await disponivel(envD, "uener", "inst-bbbbbbbb");
  checar(semToken.disponivel === false && semToken.em_uso === true, "sem o Google: em uso", semToken);
  const comToken = await lerResposta(await pedir(envD, "/api/tunel/disponivel?nome=uener&instalacao=inst-bbbbbbbb", { cab: { "x-paulus-google": token } }));
  checar(comToken.disponivel === true && comToken.retomar === true, "com o Google da mesma conta: dá para retomar", comToken);
  const outro = await lerResposta(await pedir(envD, "/api/tunel/disponivel?nome=uener&instalacao=inst-bbbbbbbb", { cab: { "x-paulus-google": await idToken({ sub: "222" }) } }));
  checar(outro.disponivel === false, "outra conta Google: em uso", outro);

  const lista = async (t) => { const r = await pedir(envD, "/api/tunel/meus", { metodo: "POST", corpo: { id_token: t } }); return { status: r.status, d: await lerResposta(r) }; };
  const m1 = await lista(token);
  checar(m1.status === 200 && m1.d.enderecos.length === 1 && m1.d.enderecos[0].slug === "uener", "/meus lista o endereço da conta", m1);
  checar((await lista(await idToken({ sub: "222" }))).d.enderecos.length === 0, "/meus de outra conta: vazio");
  const falsos = {
    "vencido": await idToken({ exp: Math.floor(Date.now() / 1000) - 10 }),
    "de outro cliente": await idToken({ aud: "cliente-de-outro-app" }),
    "de outro emissor": await idToken({ iss: "https://evil.example" }),
    "e-mail não verificado": await idToken({ email_verified: false }),
    "assinatura trocada": token.slice(0, token.lastIndexOf(".") + 1) + (await idToken({ sub: "999" })).split(".")[2],
    "sem assinatura": token.split(".").slice(0, 2).join(".") + ".",
  };
  for (const [nome, t] of Object.entries(falsos)) checar((await lista(t)).status === 401, "id_token " + nome + ": recusado (401)");
  const chaveFalsa = (await crypto.subtle.generateKey({ name: "RSASSA-PKCS1-v1_5", modulusLength: 2048, publicExponent: new Uint8Array([1, 0, 1]), hash: "SHA-256" }, true, ["sign"])).privateKey;
  checar((await lista(await idToken({}, { chave: chaveFalsa }))).status === 401, "id_token assinado por outra chave: recusado");

  const intruso = await iniciarCom("uener", "inst-cccccccc", await idToken({ sub: "222" }));
  checar(intruso.status === 409, "outra conta não inicia no endereço de ninguém", intruso);
  checar((await iniciarCom("uener", "inst-cccccccc", falsos["vencido"])).status === 401, "iniciar com id_token vencido: 401, com a frase");

  const tuneis = conta.tuneis.size;
  const b = await conectarCom("uener", "inst-bbbbbbbb", token);
  checar(b.i.dados.retomar === true && b.pag.includes("Retomar o endereço") && b.pag.includes("dono@gmail.com"),
    "a página diz que é retomar, e de que conta", b.pag.slice(0, 120));
  const reg2 = JSON.parse(envD.ESCRITORIOS.m.get("escritorio:uener"));
  checar(b.e.estado === "pronto" && reg2.instalacao_id === "inst-bbbbbbbb" && reg2.dono.sub === "111" && conta.tuneis.size === tuneis,
    "retomado: o endereço é da instalação nova; o túnel antigo saiu", { reg2, tuneis, agora: conta.tuneis.size });
  const velho = await pedir(envD, "/api/tunel/situacao", { cab: bearer(a.e.segredo_instalacao) });
  const vd = await lerResposta(velho);
  checar(velho.status === 410 && vd.removido === true && String(vd.motivo).includes("retomado"), "o PAULUS antigo ouve “removido: retomado”", vd);
  checar((await lista(token)).d.enderecos.length === 1, "o índice da conta continua com um endereço só");

  // Um escritorio conectado antes desta versao (sem dono) ganha o dono.
  const c = await conectarCom("antigo", "inst-dddddddd", undefined);
  checar(!JSON.parse(envD.ESCRITORIOS.m.get("escritorio:antigo")).dono, "sem id_token: nasce sem dono (PAULUS antigo)");
  const r = await pedir(envD, "/api/tunel/dono", { metodo: "POST", corpo: JSON.stringify({ id_token: token }), cab: bearer(c.e.segredo_instalacao) });
  checar(r.status === 200 && JSON.parse(envD.ESCRITORIOS.m.get("escritorio:antigo")).dono.sub === "111", "/dono, com o segredo: grava o dono");
  checar((await lista(token)).d.enderecos.map((x) => x.slug).sort().join() === "antigo,uener", "e ele aparece em /meus");
  const semSegredo = await pedir(envD, "/api/tunel/dono", { metodo: "POST", corpo: JSON.stringify({ id_token: token }), cab: { "content-type": "application/json" } });
  checar(semSegredo.status === 401, "/dono sem o segredo da instalação: 401");
  await pedir(envD, "/api/tunel/remover", { metodo: "POST", corpo: "{}", cab: bearer(c.e.segredo_instalacao) });
  checar((await lista(token)).d.enderecos.map((x) => x.slug).join() === "uener", "removido: sai do índice da conta");
}

console.log(falhas ? `\n  ${falhas} FALHA(S) no túnel` : "\n  túnel: todos os testes passaram");
if (import.meta.url === `file://${process.argv[1].replace(/\\/g, "/")}` || process.argv[1].endsWith("teste-tunel.mjs")) process.exit(falhas ? 1 : 0);
export default falhas;
