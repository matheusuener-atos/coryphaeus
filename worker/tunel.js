// O acesso de fora (acesso-remoto/v0, R5): o Worker cria, na conta Cloudflare
// do Atos, o caminho de cada escritorio ate o PAULUS dele - tunel, DNS e a
// aplicacao do Cloudflare Access em <slug>.paulus.ia.br. O advogado nao cria
// conta, nao mexe em DNS e nao abre o painel da Cloudflare.
//
// O Worker cria o CAMINHO, nunca o conteudo: ele nao faz proxy de
// *.paulus.ia.br (esse trafego vai direto da Cloudflare ao tunel do
// escritorio) e nao ve documento nenhum.
//
// O fluxo e o de autorizacao de dispositivo:
//
//   POST /api/tunel/iniciar   o PAULUS pede; recebe um codigo secreto (fica
//                             com ele) e um codigo curto XXXX-XXXX
//   GET  /conectar?c=XXXX     o titular abre no navegador, passa pelo Access
//                             (codigo no e-mail) e ve "Conectar ...?"
//   POST /conectar            confirma: tunel, ingress, DNS, Access, token
//   POST /api/tunel/estado    o PAULUS pergunta a cada 3 s; recebe o token
//                             do tunel UMA vez, e o pedido some
//
// Depois, com o segredo da instalacao (Authorization: Bearer):
//
//   POST /api/tunel/emails    quem pode passar pelo Access (ate 10)
//   POST /api/tunel/porta     a porta do PAULUS mudou
//   GET  /api/tunel/situacao  o tunel esta conectado?
//   POST /api/tunel/remover   apaga app, politica, DNS, tunel e registro
//
// Tudo atras de TUNEL_ATIVO === "1" e do KV ESCRITORIOS: sem os dois, as
// rotas respondem 404. E isso que deixa este codigo ir ao ar no deploy de
// cada push sem ligar nada.
//
// Caminhos da API conferidos na documentacao da Cloudflare em 28/09/2026
// (docs/PROGRESSO-IMPLEMENTACAO.md, R5).

const API = "https://api.cloudflare.com/client/v4";
const DOMINIO = "paulus.ia.br";
const PEDIDO_TTL_S = 15 * 60;
const RE_EMAIL = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
const RE_CODIGO_USUARIO = /^[A-HJ-NP-Z2-9]{4}-[A-HJ-NP-Z2-9]{4}$/;
const LETRAS = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789";
const EMAILS_MAX = 10;
const RESERVADOS = new Set(["www", "api", "conectar", "admin", "app", "mail", "smtp", "ftp", "ns1", "ns2",
  "paulus", "suporte", "contato", "status", "blog", "dev", "teste", "staging", "cdn", "static"]);

// --------------------------------------------------------------- entrada

export function ehRotaDoTunel(url) {
  return url.pathname === "/conectar" || url.pathname.startsWith("/api/tunel/");
}

export async function atenderTunel(request, env, url, { dentroDoLimite, agora = () => Date.now() } = {}) {
  if (env.TUNEL_ATIVO !== "1" || !env.ESCRITORIOS) return texto("rota não existe", 404);
  const p = url.pathname;
  const m = request.method;
  if (p === "/api/tunel/iniciar" && m === "POST") {
    if (dentroDoLimite && !(await dentroDoLimite(request, env))) return json({ erro: "muitas tentativas seguidas - espere um minuto" }, 429);
    return iniciar(request, env, agora);
  }
  if (p === "/conectar" && m === "GET") return paginaConectar(request, env, url, agora);
  if (p === "/conectar" && m === "POST") return confirmar(request, env, agora);
  if (p === "/api/tunel/estado" && m === "POST") return estadoDoPedido(request, env);
  if (p === "/api/tunel/emails" && m === "POST") return comSegredo(request, env, (e, dados) => trocarEmails(env, e, dados));
  if (p === "/api/tunel/porta" && m === "POST") return comSegredo(request, env, (e, dados) => trocarPorta(env, e, dados));
  if (p === "/api/tunel/situacao" && m === "GET") return comSegredo(request, env, (e) => situacao(env, e), false);
  if (p === "/api/tunel/remover" && m === "POST") return comSegredo(request, env, (e) => remover(env, e), false);
  return json({ erro: "rota não existe" }, 404);
}

// ------------------------------------------------------------- utilidades

function json(dados, status = 200) {
  return new Response(JSON.stringify(dados), {
    status, headers: { "content-type": "application/json; charset=utf-8", "cache-control": "no-store" },
  });
}

function texto(t, status) {
  return new Response(t, { status, headers: { "content-type": "text/plain; charset=utf-8", "cache-control": "no-store" } });
}

function aleatorio(n) {
  return [...crypto.getRandomValues(new Uint8Array(n))].map((b) => b.toString(16).padStart(2, "0")).join("");
}

async function resumo(valor) {
  const d = await crypto.subtle.digest("SHA-256", new TextEncoder().encode(String(valor)));
  return [...new Uint8Array(d)].map((b) => b.toString(16).padStart(2, "0")).join("");
}

function codigoUsuario() {
  const b = crypto.getRandomValues(new Uint8Array(8));
  const c = [...b].map((x) => LETRAS[x % LETRAS.length]).join("");
  return c.slice(0, 4) + "-" + c.slice(4);
}

function igual(a, b) {
  a = String(a || ""); b = String(b || "");
  if (a.length !== b.length) return false;
  let d = 0;
  for (let i = 0; i < a.length; i++) d |= a.charCodeAt(i) ^ b.charCodeAt(i);
  return d === 0;
}

async function lerJSON(request) {
  try { return await request.json(); } catch (e) { return null; }
}

async function kvGet(env, chave) {
  const bruto = await env.ESCRITORIOS.get(chave);
  if (!bruto) return null;
  try { return JSON.parse(bruto); } catch (e) { return null; }
}

async function kvPut(env, chave, valor, ttl) {
  await env.ESCRITORIOS.put(chave, JSON.stringify(valor), ttl ? { expirationTtl: ttl } : undefined);
}

// "Escritório Silva & Souza" -> "escritorio-silva-souza", ate 24 caracteres.
export function slugDoNome(nome) {
  const base = String(nome || "").normalize("NFD").replace(/[̀-ͯ]/g, "").toLowerCase()
    .replace(/[^a-z0-9]+/g, "-").replace(/^-+|-+$/g, "").slice(0, 24).replace(/-+$/g, "");
  return base || "escritorio";
}

async function chamarCF(env, metodo, caminho, corpo) {
  const r = await fetch(API + caminho, {
    method: metodo,
    headers: { Authorization: "Bearer " + env.CF_API_TOKEN, "Content-Type": "application/json" },
    body: corpo === undefined ? undefined : JSON.stringify(corpo),
  });
  let dados = {};
  try { dados = await r.json(); } catch (e) { dados = {}; }
  if (!r.ok || dados.success === false) {
    const msg = (dados.errors && dados.errors[0] && dados.errors[0].message) || ("HTTP " + r.status);
    throw new Error(metodo + " " + caminho.replace(/\/accounts\/[^/]+|\/zones\/[^/]+/g, "") + ": " + msg);
  }
  return dados.result;
}

// ------------------------------------------------------------- iniciar

async function iniciar(request, env, agora) {
  const d = await lerJSON(request);
  if (!d) return json({ erro: "pedido inválido" }, 400);
  const email = String(d.email_titular || "").trim().toLowerCase();
  const nome = String(d.nome_escritorio || "").trim().replace(/\s+/g, " ");
  const instalacao = String(d.instalacao_id || "");
  const porta = Number(d.porta);
  if (!RE_EMAIL.test(email) || email.length > 200) return json({ erro: "e-mail do titular inválido" }, 400);
  if (nome.length < 2 || nome.length > 80) return json({ erro: "diga o nome do escritório (2 a 80 letras)" }, 400);
  if (!/^[A-Za-z0-9-]{8,64}$/.test(instalacao)) return json({ erro: "instalação inválida" }, 400);
  if (!Number.isInteger(porta) || porta < 1024 || porta > 65535) return json({ erro: "porta inválida" }, 400);
  if (RESERVADOS.has(slugDoNome(nome))) return json({ erro: "esse nome é reservado: use o nome do escritório" }, 400);

  if (await env.ESCRITORIOS.get("titular:" + (await resumo(email)))) {
    return json({ erro: "já existe um escritório conectado com este e-mail de titular: remova o acesso de fora dele antes" }, 409);
  }
  if (await env.ESCRITORIOS.get("instalacao:" + instalacao)) {
    return json({ erro: "esta instalação do PAULUS já tem acesso de fora: remova antes de conectar de novo" }, 409);
  }
  const limite = Number(env.MAX_ESCRITORIOS || 0);
  if (limite && (await contarEscritorios(env)) >= limite) {
    return json({ erro: "o acesso de fora chegou ao limite de escritórios desta fase. Escreva para contato@paulus.ia.br para entrar na lista." }, 503);
  }

  const dispositivo = aleatorio(32);
  let usuario = codigoUsuario();
  for (let i = 0; i < 5 && (await env.ESCRITORIOS.get("usuario:" + usuario)); i++) usuario = codigoUsuario();
  const h = await resumo(dispositivo);
  const expira = agora() + PEDIDO_TTL_S * 1000;
  await kvPut(env, "pedido:" + h, { estado: "pendente", codigo_usuario: usuario, email_titular: email, nome, instalacao_id: instalacao, porta, expira }, PEDIDO_TTL_S);
  await kvPut(env, "usuario:" + usuario, { pedido: h }, PEDIDO_TTL_S);
  return json({
    codigo_dispositivo: dispositivo,
    codigo_usuario: usuario,
    url: "https://" + DOMINIO + "/conectar?c=" + usuario,
    expira_em: new Date(expira).toISOString(),
  });
}

async function contarEscritorios(env) {
  let total = 0, cursor;
  do {
    const lista = await env.ESCRITORIOS.list({ prefix: "escritorio:", cursor });
    total += lista.keys.length;
    cursor = lista.list_complete ? undefined : lista.cursor;
  } while (cursor);
  return total;
}

// ------------------------------------------------ JWT do Cloudflare Access

let certsEmCache = { quando: 0, dominio: "", chaves: [] };

function b64url(s) {
  s = s.replace(/-/g, "+").replace(/_/g, "/");
  while (s.length % 4) s += "=";
  return Uint8Array.from(atob(s), (c) => c.charCodeAt(0));
}

async function chavesDoAccess(env, agora) {
  const dominio = env.ACCESS_TEAM_DOMAIN;
  if (certsEmCache.dominio === dominio && agora() - certsEmCache.quando < 3600 * 1000 && certsEmCache.chaves.length) {
    return certsEmCache.chaves;
  }
  const r = await fetch("https://" + dominio + "/cdn-cgi/access/certs");
  if (!r.ok) throw new Error("certs do Access indisponíveis");
  const dados = await r.json();
  certsEmCache = { quando: agora(), dominio, chaves: dados.keys || [] };
  return certsEmCache.chaves;
}

// As claims do JWT do Access que vale para `aud`, ou null. RS256, com a chave
// escolhida pelo `kid` (as chaves giram a cada 6 semanas), iss e aud
// conferidos. Sem chave alcancavel, nega.
export async function conferirJWT(token, env, aud, agora = () => Date.now()) {
  try {
    const partes = String(token || "").split(".");
    if (partes.length !== 3) return null;
    const cab = JSON.parse(new TextDecoder().decode(b64url(partes[0])));
    const claims = JSON.parse(new TextDecoder().decode(b64url(partes[1])));
    if (cab.alg !== "RS256" || !cab.kid) return null;
    const jwk = (await chavesDoAccess(env, agora)).find((k) => k.kid === cab.kid);
    if (!jwk) return null;
    const chave = await crypto.subtle.importKey("jwk", jwk, { name: "RSASSA-PKCS1-v1_5", hash: "SHA-256" }, false, ["verify"]);
    const ok = await crypto.subtle.verify("RSASSA-PKCS1-v1_5", chave, b64url(partes[2]),
      new TextEncoder().encode(partes[0] + "." + partes[1]));
    if (!ok) return null;
    const auds = Array.isArray(claims.aud) ? claims.aud : [claims.aud];
    const agoraS = agora() / 1000;
    if (!aud || !auds.includes(aud)) return null;
    if (claims.iss !== "https://" + env.ACCESS_TEAM_DOMAIN) return null;
    if (!claims.exp || claims.exp < agoraS) return null;
    if (claims.nbf && claims.nbf > agoraS + 60) return null;
    return claims;
  } catch (e) {
    return null;
  }
}

// ---------------------------------------------------------- conectar

async function pedidoDoCodigo(env, codigo) {
  const c = String(codigo || "").trim().toUpperCase();
  if (!RE_CODIGO_USUARIO.test(c)) return null;
  const u = await kvGet(env, "usuario:" + c);
  if (!u) return null;
  const pedido = await kvGet(env, "pedido:" + u.pedido);
  return pedido ? { hash: u.pedido, pedido } : null;
}

function esc(s) {
  return String(s).replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]);
}

function pagina(titulo, corpo, status = 200) {
  const html = `<!doctype html><html lang="pt-BR"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>PAULUS — ${esc(titulo)}</title><style>
body{margin:0;min-height:100vh;display:grid;place-items:center;background:#faf9f6;color:#1c1c1a;font-family:Manrope,system-ui,-apple-system,"Segoe UI",sans-serif;padding:24px 16px;box-sizing:border-box}
main{max-width:520px;width:100%}h1{font-family:"EB Garamond",Georgia,serif;font-weight:500;font-size:30px;line-height:1.15;margin:0 0 10px}
p{color:#6b6b65;line-height:1.55;font-size:15px}code{font-family:"Fira Code",ui-monospace,monospace;color:#1c1c1a}
.cartao{background:#fff;border:1px solid rgba(28,28,26,.08);border-radius:14px;padding:22px;margin-top:18px}
button{font:inherit;font-weight:600;min-height:44px;width:100%;border:0;border-radius:10px;background:#26251f;color:#f2f1ec;cursor:pointer}
.pe{font-size:12.5px;color:#9a9a93;margin-top:18px}</style></head><body><main>${corpo}</main></body></html>`;
  return new Response(html, { status, headers: { "content-type": "text/html; charset=utf-8", "cache-control": "no-store",
    "x-frame-options": "DENY", "referrer-policy": "no-referrer" } });
}

async function quemEsta(request, env, agora) {
  const claims = await conferirJWT(request.headers.get("cf-access-jwt-assertion"), env, env.ACCESS_AUD_CONECTAR, agora);
  return claims && claims.email ? String(claims.email).toLowerCase() : "";
}

async function paginaConectar(request, env, url, agora) {
  const email = await quemEsta(request, env, agora);
  if (!email) return pagina("Entrada recusada", "<h1>Entrada recusada</h1><p>Esta página só abre depois da confirmação do e-mail pela Cloudflare.</p>", 403);
  const achado = await pedidoDoCodigo(env, url.searchParams.get("c"));
  if (!achado) return pagina("Código vencido", "<h1>Este código não vale mais</h1><p>Ele dura 15 minutos. Comece de novo no PAULUS do escritório, em Configurações › Acesso de fora.</p>", 410);
  const { hash, pedido } = achado;
  if (email !== pedido.email_titular) {
    return pagina("E-mail diferente", `<h1>Este pedido é de outro e-mail</h1><p>O PAULUS pediu para conectar com <code>${esc(pedido.email_titular)}</code>, e você entrou como <code>${esc(email)}</code>. Entre com o e-mail do titular.</p>`, 403);
  }
  if (pedido.estado !== "pendente") return pagina("Já conectado", "<h1>Pronto</h1><p>Este pedido já foi confirmado. Volte ao PAULUS do escritório.</p>");
  if (!pedido.slug) {
    pedido.slug = slugDoNome(pedido.nome) + "-" + aleatorio(2);
    await kvPut(env, "pedido:" + hash, pedido, PEDIDO_TTL_S);
  }
  const host = pedido.slug + "." + DOMINIO;
  return pagina("Conectar", `<h1>Conectar o PAULUS do escritório?</h1>
<p>O PAULUS de <b>${esc(pedido.nome)}</b> vai atender em <code>https://${esc(host)}</code>, pelo túnel da Cloudflare. Só passa quem confirmar um e-mail autorizado e depois entrar com a conta do PAULUS.</p>
<form class="cartao" method="post" action="/conectar"><input type="hidden" name="c" value="${esc(pedido.codigo_usuario)}">
<p style="margin-top:0">Código mostrado no PAULUS: <code>${esc(pedido.codigo_usuario)}</code>. Confira que é o mesmo.</p>
<button type="submit">Confirmar</button></form>
<p class="pe">Os documentos e o modelo de IA continuam no computador do escritório. O Atos cria o endereço e não roteia, não inspeciona nem registra o conteúdo que passa por ele.</p>`);
}

async function confirmar(request, env, agora) {
  const email = await quemEsta(request, env, agora);
  if (!email) return pagina("Entrada recusada", "<h1>Entrada recusada</h1><p>Esta página só abre depois da confirmação do e-mail pela Cloudflare.</p>", 403);
  let codigo = "";
  try { codigo = String((await request.formData()).get("c") || ""); } catch (e) { codigo = ""; }
  const achado = await pedidoDoCodigo(env, codigo);
  if (!achado) return pagina("Código vencido", "<h1>Este código não vale mais</h1><p>Comece de novo no PAULUS do escritório.</p>", 410);
  const { hash, pedido } = achado;
  if (email !== pedido.email_titular) return pagina("E-mail diferente", "<h1>Este pedido é de outro e-mail</h1>", 403);
  if (pedido.estado !== "pendente") return pagina("Já conectado", "<h1>Pronto</h1><p>Volte ao PAULUS do escritório.</p>");
  const slug = pedido.slug || (slugDoNome(pedido.nome) + "-" + aleatorio(2));
  if (await env.ESCRITORIOS.get("escritorio:" + slug)) return pagina("Tente de novo", "<h1>Esse endereço acabou de ser usado</h1><p>Recarregue esta página.</p>", 409);
  let criado;
  try {
    criado = await provisionar(env, slug, pedido);
  } catch (e) {
    return pagina("Não deu certo", `<h1>Não consegui criar o endereço</h1><p>Nada ficou pela metade: o que tinha sido criado foi desfeito. Tente de novo em alguns minutos.</p><p class="pe">${esc(e.message)}</p>`, 502);
  }
  await kvPut(env, "pedido:" + hash, { ...pedido, estado: "pronto", entrega: criado.entrega }, PEDIDO_TTL_S);
  return pagina("Conectado", `<h1>Conectado</h1><p>O PAULUS do escritório já recebeu o endereço <code>https://${esc(criado.entrega.hostname)}</code> e liga o túnel sozinho. Pode fechar esta página.</p>`);
}

// Os passos, na ordem do contrato. Falha em qualquer um desfaz os anteriores:
// escritorio pela metade na conta do Atos e lixo que ninguem ve.
export async function provisionar(env, slug, pedido) {
  const a = "/accounts/" + env.CF_ACCOUNT_ID;
  const host = slug + "." + DOMINIO;
  const feito = [];
  const desfazer = async () => {
    for (const passo of feito.reverse()) {
      try { await passo(); } catch (e) { /* o resto do desfazer continua */ }
    }
  };
  try {
    const tunel = await chamarCF(env, "POST", a + "/cfd_tunnel", { name: "paulus-" + slug, config_src: "cloudflare" });
    feito.push(async () => {
      await chamarCF(env, "DELETE", a + "/cfd_tunnel/" + tunel.id + "/connections");
      await chamarCF(env, "DELETE", a + "/cfd_tunnel/" + tunel.id);
    });
    await chamarCF(env, "PUT", a + "/cfd_tunnel/" + tunel.id + "/configurations", ingress(host, pedido.porta));
    const dns = await chamarCF(env, "POST", "/zones/" + env.CF_ZONE_ID + "/dns_records",
      { type: "CNAME", name: host, content: tunel.id + ".cfargotunnel.com", proxied: true, ttl: 1, comment: "PAULUS: acesso de fora de " + slug });
    feito.push(() => chamarCF(env, "DELETE", "/zones/" + env.CF_ZONE_ID + "/dns_records/" + dns.id));
    const politica = await chamarCF(env, "POST", a + "/access/policies", politicaDe(slug, [pedido.email_titular]));
    feito.push(() => chamarCF(env, "DELETE", a + "/access/policies/" + politica.id));
    const app = await chamarCF(env, "POST", a + "/access/apps", {
      name: "PAULUS " + slug, domain: host, type: "self_hosted", session_duration: "12h",
      policies: [{ id: politica.id, precedence: 1 }],
    });
    feito.push(() => chamarCF(env, "DELETE", a + "/access/apps/" + app.id));
    const token = await chamarCF(env, "GET", a + "/cfd_tunnel/" + tunel.id + "/token");
    const segredo = aleatorio(32);
    const registro = {
      slug, tunnel_id: tunel.id, dns_id: dns.id, app_id: app.id, policy_id: politica.id, aud: app.aud,
      emails: [pedido.email_titular], email_titular: pedido.email_titular, instalacao_id: pedido.instalacao_id,
      hash_segredo: await resumo(segredo), porta: pedido.porta, criado_em: new Date().toISOString(),
    };
    await kvPut(env, "escritorio:" + slug, registro);
    feito.push(() => env.ESCRITORIOS.delete("escritorio:" + slug));
    await kvPut(env, "segredo:" + registro.hash_segredo, { slug });
    await kvPut(env, "titular:" + (await resumo(pedido.email_titular)), { slug });
    await kvPut(env, "instalacao:" + pedido.instalacao_id, { slug });
    return {
      registro,
      entrega: { hostname: host, tunnel_token: token, aud: app.aud, team_domain: env.ACCESS_TEAM_DOMAIN, segredo_instalacao: segredo },
    };
  } catch (e) {
    await desfazer();
    throw e;
  }
}

function ingress(host, porta) {
  return { config: { ingress: [{ hostname: host, service: "http://127.0.0.1:" + porta, originRequest: {} }, { service: "http_status:404" }] } };
}

function politicaDe(slug, emails) {
  return { name: "PAULUS " + slug, decision: "allow", include: emails.map((email) => ({ email: { email } })) };
}

// ----------------------------------------------------------- estado

async function estadoDoPedido(request, env) {
  const d = await lerJSON(request);
  const codigo = String((d && d.codigo_dispositivo) || "");
  if (!/^[0-9a-f]{64}$/.test(codigo)) return json({ estado: "expirado" });
  const h = await resumo(codigo);
  const pedido = await kvGet(env, "pedido:" + h);
  if (!pedido) return json({ estado: "expirado" });
  if (pedido.estado !== "pronto" || !pedido.entrega) return json({ estado: "pendente" });
  // Uma vez so: o token do tunel sai daqui e o pedido deixa de existir.
  await env.ESCRITORIOS.delete("pedido:" + h);
  await env.ESCRITORIOS.delete("usuario:" + pedido.codigo_usuario);
  return json({ estado: "pronto", ...pedido.entrega });
}

// ------------------------------------------------- com o segredo da instalacao

async function comSegredo(request, env, fazer, comCorpo = true) {
  const cab = request.headers.get("authorization") || "";
  const segredo = cab.startsWith("Bearer ") ? cab.slice(7).trim() : "";
  if (!/^[0-9a-f]{64}$/.test(segredo)) return json({ erro: "não autorizado" }, 401);
  const h = await resumo(segredo);
  const indice = await kvGet(env, "segredo:" + h);
  const registro = indice ? await kvGet(env, "escritorio:" + indice.slug) : null;
  if (!registro || !igual(registro.hash_segredo, h)) return json({ erro: "não autorizado" }, 401);
  const dados = comCorpo ? await lerJSON(request) : null;
  if (comCorpo && !dados) return json({ erro: "pedido inválido" }, 400);
  try {
    return await fazer(registro, dados);
  } catch (e) {
    return json({ erro: e.message }, 502);
  }
}

async function trocarEmails(env, registro, dados) {
  const emails = [...new Set((Array.isArray(dados.emails) ? dados.emails : []).map((e) => String(e).trim().toLowerCase()).filter(Boolean))];
  if (!emails.every((e) => RE_EMAIL.test(e))) return json({ erro: "e-mail inválido na lista" }, 400);
  // O titular esta sempre na lista: sem ele, ninguem conserta nada de fora.
  if (!emails.includes(registro.email_titular)) emails.unshift(registro.email_titular);
  if (emails.length > EMAILS_MAX) return json({ erro: "no máximo " + EMAILS_MAX + " e-mails" }, 400);
  await chamarCF(env, "PUT", "/accounts/" + env.CF_ACCOUNT_ID + "/access/policies/" + registro.policy_id, politicaDe(registro.slug, emails));
  await kvPut(env, "escritorio:" + registro.slug, { ...registro, emails });
  return json({ ok: true, emails });
}

async function trocarPorta(env, registro, dados) {
  const porta = Number(dados.porta);
  if (!Number.isInteger(porta) || porta < 1024 || porta > 65535) return json({ erro: "porta inválida" }, 400);
  await chamarCF(env, "PUT", "/accounts/" + env.CF_ACCOUNT_ID + "/cfd_tunnel/" + registro.tunnel_id + "/configurations",
    ingress(registro.slug + "." + DOMINIO, porta));
  await kvPut(env, "escritorio:" + registro.slug, { ...registro, porta });
  return json({ ok: true, porta });
}

async function situacao(env, registro) {
  const t = await chamarCF(env, "GET", "/accounts/" + env.CF_ACCOUNT_ID + "/cfd_tunnel/" + registro.tunnel_id);
  return json({ hostname: registro.slug + "." + DOMINIO, status: t.status || "desconhecido",
    conectado: t.status === "healthy" || t.status === "degraded", emails: registro.emails, porta: registro.porta });
}

async function remover(env, registro) {
  const a = "/accounts/" + env.CF_ACCOUNT_ID;
  const erros = [];
  const tentar = async (f) => { try { await f(); } catch (e) { erros.push(e.message); } };
  await tentar(() => chamarCF(env, "DELETE", a + "/access/apps/" + registro.app_id));
  await tentar(() => chamarCF(env, "DELETE", a + "/access/policies/" + registro.policy_id));
  await tentar(() => chamarCF(env, "DELETE", "/zones/" + env.CF_ZONE_ID + "/dns_records/" + registro.dns_id));
  await tentar(() => chamarCF(env, "DELETE", a + "/cfd_tunnel/" + registro.tunnel_id + "/connections"));
  await tentar(() => chamarCF(env, "DELETE", a + "/cfd_tunnel/" + registro.tunnel_id));
  await env.ESCRITORIOS.delete("escritorio:" + registro.slug);
  await env.ESCRITORIOS.delete("segredo:" + registro.hash_segredo);
  await env.ESCRITORIOS.delete("titular:" + (await resumo(registro.email_titular)));
  await env.ESCRITORIOS.delete("instalacao:" + registro.instalacao_id);
  return json({ ok: true, avisos: erros });
}
