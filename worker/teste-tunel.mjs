// Teste do acesso de fora no Worker (worker/tunel.js), sem rede:
//   node worker/teste-tunel.mjs      (o teste.mjs tambem chama este)
//
// A API da Cloudflare e o Cloudflare Access sao de mentira: o fetch global
// responde como a API responderia, e o JWT e assinado aqui, com uma chave RSA
// gerada no proprio teste - o Worker confere a assinatura de verdade.
import worker from "./index.js";

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

// ------------------------------------------------------ o Access de mentira
const TIME = "atos.cloudflareaccess.com";
const AUD = "aud-da-pagina-conectar";
const par = await crypto.subtle.generateKey({ name: "RSASSA-PKCS1-v1_5", modulusLength: 2048, publicExponent: new Uint8Array([1, 0, 1]), hash: "SHA-256" }, true, ["sign", "verify"]);
const outroPar = await crypto.subtle.generateKey({ name: "RSASSA-PKCS1-v1_5", modulusLength: 2048, publicExponent: new Uint8Array([1, 0, 1]), hash: "SHA-256" }, true, ["sign", "verify"]);
const jwk = { ...(await crypto.subtle.exportKey("jwk", par.publicKey)), kid: "chave-1", alg: "RS256", use: "sig" };
const b64 = (bytes) => Buffer.from(bytes).toString("base64url");
async function jwt(email, { aud = AUD, iss = "https://" + TIME, exp = Date.now() / 1000 + 600, chave = par.privateKey, kid = "chave-1" } = {}) {
  const cab = b64(new TextEncoder().encode(JSON.stringify({ alg: "RS256", kid, typ: "JWT" })));
  const corpo = b64(new TextEncoder().encode(JSON.stringify({ aud: [aud], email, iss, exp, iat: Date.now() / 1000, type: "app" })));
  const assinatura = await crypto.subtle.sign("RSASSA-PKCS1-v1_5", chave, new TextEncoder().encode(cab + "." + corpo));
  return cab + "." + corpo + "." + b64(new Uint8Array(assinatura));
}

// ------------------------------------------------ a API da Cloudflare de mentira
const chamadas = [];
const conta = { tuneis: new Map(), dns: new Map(), politicas: new Map(), apps: new Map() };
let falharEm = "";
let seq = 0;
const ok = (result) => new Response(JSON.stringify({ success: true, errors: [], messages: [], result }), { status: 200 });
const erro = (msg) => new Response(JSON.stringify({ success: false, errors: [{ message: msg }], result: null }), { status: 400 });

globalThis.fetch = async (url, opcoes = {}) => {
  const u = String(url);
  const metodo = (opcoes.method || "GET").toUpperCase();
  const corpo = opcoes.body ? JSON.parse(opcoes.body) : null;
  if (u === "https://" + TIME + "/cdn-cgi/access/certs") return new Response(JSON.stringify({ keys: [jwk] }), { status: 200 });
  if (!u.startsWith("https://api.cloudflare.com/client/v4/")) return new Response("{}", { status: 404 });
  const caminho = u.replace("https://api.cloudflare.com/client/v4", "");
  chamadas.push(metodo + " " + caminho);
  if (falharEm && (metodo + " " + caminho).includes(falharEm)) return erro("falha simulada em " + falharEm);
  let m;
  if (metodo === "POST" && /\/cfd_tunnel$/.test(caminho)) { const id = "tun-" + (++seq); conta.tuneis.set(id, { ...corpo, status: "inactive" }); return ok({ id, name: corpo.name }); }
  if (metodo === "PUT" && (m = caminho.match(/\/cfd_tunnel\/([^/]+)\/configurations$/))) { conta.tuneis.get(m[1]).config = corpo.config; return ok({}); }
  if (metodo === "GET" && (m = caminho.match(/\/cfd_tunnel\/([^/]+)\/token$/))) return ok("token-do-" + m[1]);
  if (metodo === "GET" && (m = caminho.match(/\/cfd_tunnel\/([^/]+)$/))) return ok({ id: m[1], status: conta.tuneis.get(m[1]).status });
  if (metodo === "DELETE" && (m = caminho.match(/\/cfd_tunnel\/([^/]+)\/connections$/))) return ok({});
  if (metodo === "DELETE" && (m = caminho.match(/\/cfd_tunnel\/([^/]+)$/))) { conta.tuneis.delete(m[1]); return ok({}); }
  if (metodo === "POST" && /\/dns_records$/.test(caminho)) { const id = "dns-" + (++seq); conta.dns.set(id, corpo); return ok({ id }); }
  if (metodo === "DELETE" && (m = caminho.match(/\/dns_records\/([^/]+)$/))) { conta.dns.delete(m[1]); return ok({}); }
  if (metodo === "POST" && /\/access\/policies$/.test(caminho)) { const id = "pol-" + (++seq); conta.politicas.set(id, corpo); return ok({ id }); }
  if (metodo === "PUT" && (m = caminho.match(/\/access\/policies\/([^/]+)$/))) { conta.politicas.set(m[1], corpo); return ok({ id: m[1] }); }
  if (metodo === "DELETE" && (m = caminho.match(/\/access\/policies\/([^/]+)$/))) { conta.politicas.delete(m[1]); return ok({}); }
  if (metodo === "POST" && /\/access\/apps$/.test(caminho)) { const id = "app-" + (++seq); conta.apps.set(id, corpo); return ok({ id, aud: "aud-" + id }); }
  if (metodo === "DELETE" && (m = caminho.match(/\/access\/apps\/([^/]+)$/))) { conta.apps.delete(m[1]); return ok({}); }
  return erro("rota da API não simulada: " + metodo + " " + caminho);
};

function ambiente(extra = {}) {
  return {
    TUNEL_ATIVO: "1", ESCRITORIOS: kv(), CF_API_TOKEN: "t", CF_ACCOUNT_ID: "conta1", CF_ZONE_ID: "zona1",
    ACCESS_TEAM_DOMAIN: TIME, ACCESS_AUD_CONECTAR: AUD, MAX_ESCRITORIOS: "2",
    ASSETS: { fetch: async () => new Response("site", { status: 200 }) },
    ...extra,
  };
}

const pedir = (env, caminho, { metodo = "GET", corpo, cab = {} } = {}) =>
  worker.fetch(new Request("https://paulus.ia.br" + caminho, {
    method: metodo, headers: cab, body: corpo === undefined ? undefined : (typeof corpo === "string" ? corpo : JSON.stringify(corpo)),
  }), env, { waitUntil() {} });

async function iniciar(env, email = "titular@escritorio.com", instalacao = "inst-00000001", nome = "Escritório Silva & Souza") {
  const r = await pedir(env, "/api/tunel/iniciar", { metodo: "POST", corpo: { instalacao_id: instalacao, email_titular: email, nome_escritorio: nome, porta: 47123 } });
  const t = await r.text();
  let dados;
  try { dados = JSON.parse(t); } catch (e) { dados = { texto: t }; }
  return { status: r.status, dados };
}

async function confirmarComo(env, email, codigo) {
  const cab = { "cf-access-jwt-assertion": await jwt(email), "content-type": "application/x-www-form-urlencoded" };
  return pedir(env, "/conectar", { metodo: "POST", corpo: "c=" + codigo, cab });
}

console.log("\nsem TUNEL_ATIVO, nada existe");
{
  const env = ambiente({ TUNEL_ATIVO: undefined });
  checar((await iniciar(env)).status === 404, "iniciar: 404");
  checar((await pedir(env, "/conectar?c=ABCD-EFGH")).status === 404, "conectar: 404");
  checar((await pedir(ambiente({ ESCRITORIOS: undefined }), "/api/tunel/estado", { metodo: "POST", corpo: {} })).status === 404, "sem o KV: 404");
}

console.log("\no fluxo completo");
const env = ambiente();
const inicio = await iniciar(env);
checar(inicio.status === 200 && /^[0-9a-f]{64}$/.test(inicio.dados.codigo_dispositivo) && /^[A-Z2-9]{4}-[A-Z2-9]{4}$/.test(inicio.dados.codigo_usuario),
  "iniciar devolve o código secreto e o código curto", inicio.dados);
checar(inicio.dados.url === "https://paulus.ia.br/conectar?c=" + inicio.dados.codigo_usuario, "e o endereço de conectar");
const perguntar = async () => (await pedir(env, "/api/tunel/estado", { metodo: "POST", corpo: { codigo_dispositivo: inicio.dados.codigo_dispositivo } })).json();
checar((await perguntar()).estado === "pendente", "antes da confirmação: pendente");
checar((await pedir(env, "/conectar?c=" + inicio.dados.codigo_usuario)).status === 403, "conectar sem o JWT do Access: recusado");
const outroEmail = await pedir(env, "/conectar?c=" + inicio.dados.codigo_usuario, { cab: { "cf-access-jwt-assertion": await jwt("intruso@x.com") } });
checar(outroEmail.status === 403 && (await outroEmail.text()).includes("outro e-mail"), "JWT de outro e-mail: recusado");
const forjado = await pedir(env, "/conectar?c=" + inicio.dados.codigo_usuario, { cab: { "cf-access-jwt-assertion": await jwt("titular@escritorio.com", { chave: outroPar.privateKey }) } });
checar(forjado.status === 403, "JWT assinado com outra chave: recusado");
const audErrado = await pedir(env, "/conectar?c=" + inicio.dados.codigo_usuario, { cab: { "cf-access-jwt-assertion": await jwt("titular@escritorio.com", { aud: "outra-app" }) } });
checar(audErrado.status === 403, "JWT de outra aplicação (aud): recusado");
const vencido = await pedir(env, "/conectar?c=" + inicio.dados.codigo_usuario, { cab: { "cf-access-jwt-assertion": await jwt("titular@escritorio.com", { exp: Date.now() / 1000 - 5 }) } });
checar(vencido.status === 403, "JWT vencido: recusado");
const pagina = await pedir(env, "/conectar?c=" + inicio.dados.codigo_usuario, { cab: { "cf-access-jwt-assertion": await jwt("titular@escritorio.com") } });
const html = await pagina.text();
checar(pagina.status === 200 && /escritorio-silva-souza-[0-9a-f]{4}\.paulus\.ia\.br/.test(html) && html.includes("Confirmar"),
  "o titular vê “Conectar o PAULUS do escritório … a <slug>.paulus.ia.br?”", html.slice(0, 200));
const conf = await confirmarComo(env, "titular@escritorio.com", inicio.dados.codigo_usuario);
checar(conf.status === 200, "confirmar provisiona", await conf.clone().text().then((t) => t.slice(0, 300)));
checar(conta.tuneis.size === 1 && conta.dns.size === 1 && conta.apps.size === 1 && conta.politicas.size === 1, "túnel, DNS, app e política criados", {
  tuneis: conta.tuneis.size, dns: conta.dns.size, apps: conta.apps.size, pol: conta.politicas.size });
const tunel = [...conta.tuneis.values()][0];
checar(tunel.config_src === "cloudflare" && tunel.config.ingress[0].service === "http://127.0.0.1:47123" && tunel.config.ingress[1].service === "http_status:404",
  "túnel gerenciado remotamente, ingress para 127.0.0.1 e o resto 404", tunel);
const dns = [...conta.dns.values()][0];
checar(dns.type === "CNAME" && dns.proxied === true && /\.cfargotunnel\.com$/.test(dns.content), "CNAME com proxy para o túnel", dns);
const app = [...conta.apps.values()][0];
checar(app.type === "self_hosted" && app.session_duration === "12h", "Access self_hosted com sessão de 12 h", app);
const pol = [...conta.politicas.values()][0];
checar(JSON.stringify(pol.include) === JSON.stringify([{ email: { email: "titular@escritorio.com" } }]), "a política inclui só o titular", pol);
const entrega = await perguntar();
checar(entrega.estado === "pronto" && entrega.tunnel_token.startsWith("token-do-tun-") && /^[0-9a-f]{64}$/.test(entrega.segredo_instalacao) && entrega.team_domain === TIME,
  "estado entrega hostname, token, aud, time e segredo", entrega);
checar((await perguntar()).estado === "expirado", "a segunda leitura não entrega de novo");
const registro = JSON.parse(env.ESCRITORIOS.m.get("escritorio:" + entrega.hostname.split(".")[0]));
checar(registro.hash_segredo && !JSON.stringify(registro).includes(entrega.segredo_instalacao) && !JSON.stringify([...env.ESCRITORIOS.m.values()]).includes(entrega.tunnel_token),
  "o KV guarda só o hash do segredo, e o token não fica guardado");

console.log("\ncom o segredo da instalação");
const bearer = (s) => ({ authorization: "Bearer " + s, "content-type": "application/json" });
checar((await pedir(env, "/api/tunel/situacao", { cab: bearer("0".repeat(64)) })).status === 401, "segredo errado: 401");
checar((await pedir(env, "/api/tunel/situacao")).status === 401, "sem segredo: 401");
const sit = await (await pedir(env, "/api/tunel/situacao", { cab: bearer(entrega.segredo_instalacao) })).json();
checar(sit.hostname === entrega.hostname && sit.conectado === false, "situação: túnel ainda não conectado", sit);
const em = await (await pedir(env, "/api/tunel/emails", { metodo: "POST", corpo: { emails: ["colab@escritorio.com"] }, cab: bearer(entrega.segredo_instalacao) })).json();
checar(em.ok && em.emails[0] === "titular@escritorio.com" && em.emails.includes("colab@escritorio.com"), "e-mails: o titular sempre fica na lista", em);
checar([...conta.politicas.values()][0].include.length === 2, "a política do Access foi atualizada");
const muitos = await pedir(env, "/api/tunel/emails", { metodo: "POST", corpo: { emails: Array.from({ length: 11 }, (_, i) => `p${i}@x.com`) }, cab: bearer(entrega.segredo_instalacao) });
checar(muitos.status === 400, "mais de 10 e-mails: recusado");
const porta = await (await pedir(env, "/api/tunel/porta", { metodo: "POST", corpo: { porta: 47200 }, cab: bearer(entrega.segredo_instalacao) })).json();
checar(porta.ok && [...conta.tuneis.values()][0].config.ingress[0].service === "http://127.0.0.1:47200", "trocar a porta atualiza o ingress");

console.log("\nlimites");
checar((await iniciar(env)).status === 409, "o mesmo e-mail de titular não conecta dois escritórios");
checar((await iniciar(env, "outro@escritorio.com", "inst-00000001")).status === 409, "a mesma instalação não conecta duas vezes");
checar((await iniciar(env, "a@x.com", "inst-00000009", "www")).status === 400, "nome reservado: recusado");
const segundo = await iniciar(env, "segundo@x.com", "inst-00000002", "Segundo Escritório");
await confirmarComo(env, "segundo@x.com", segundo.dados.codigo_usuario);
const terceiro = await iniciar(env, "terceiro@x.com", "inst-00000003", "Terceiro");
checar(terceiro.status === 503 && terceiro.dados.erro.includes("limite"), "MAX_ESCRITORIOS respeitado, com frase clara", terceiro.dados);

console.log("\nfalha no meio desfaz o que foi feito");
{
  const env2 = ambiente({ MAX_ESCRITORIOS: "10" });
  const antes = { t: conta.tuneis.size, d: conta.dns.size, p: conta.politicas.size, a: conta.apps.size };
  const i = await iniciar(env2, "falha@x.com", "inst-00000004", "Escritório Que Falha");
  await pedir(env2, "/conectar?c=" + i.dados.codigo_usuario, { cab: { "cf-access-jwt-assertion": await jwt("falha@x.com") } });
  falharEm = "POST /accounts/conta1/access/apps";
  const r = await confirmarComo(env2, "falha@x.com", i.dados.codigo_usuario);
  falharEm = "";
  checar(r.status === 502, "a falha no passo 5 (app do Access) chega como erro", r.status);
  checar(conta.tuneis.size === antes.t && conta.dns.size === antes.d && conta.politicas.size === antes.p && conta.apps.size === antes.a,
    "túnel, DNS e política criados antes foram desfeitos", { antes, depois: { t: conta.tuneis.size, d: conta.dns.size, p: conta.politicas.size, a: conta.apps.size } });
  checar(![...env2.ESCRITORIOS.m.keys()].some((k) => k.startsWith("escritorio:")), "nada ficou registrado no KV");
}

console.log("\nremover");
{
  const antes = conta.tuneis.size;
  const r = await (await pedir(env, "/api/tunel/remover", { metodo: "POST", cab: bearer(entrega.segredo_instalacao) })).json();
  checar(r.ok && conta.tuneis.size === antes - 1, "remover apaga o túnel", r);
  checar(![...env.ESCRITORIOS.m.keys()].some((k) => k === "escritorio:" + entrega.hostname.split(".")[0]), "e o registro");
  checar((await pedir(env, "/api/tunel/situacao", { cab: bearer(entrega.segredo_instalacao) })).status === 401, "o segredo deixa de valer");
  checar((await iniciar(env)).status === 200, "e o titular pode conectar de novo");
}

console.log("\no Worker não atende *.paulus.ia.br");
{
  const r = await worker.fetch(new Request("https://escritorio-x-1a2b.paulus.ia.br/qualquer"), env, { waitUntil() {} });
  checar(r.status === 404, "subdomínio de escritório: 404 no Worker (o tráfego é do túnel)", r.status);
}

console.log(falhas ? `\n  ${falhas} FALHA(S) no túnel` : "\n  túnel: todos os testes passaram");
if (import.meta.url === `file://${process.argv[1].replace(/\\/g, "/")}` || process.argv[1].endsWith("teste-tunel.mjs")) process.exit(falhas ? 1 : 0);
export default falhas;
