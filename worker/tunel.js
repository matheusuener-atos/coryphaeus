// O acesso de fora (acesso-remoto/v0, R5): o Worker cria, na conta Cloudflare
// do Atos, o caminho de cada escritorio ate o PAULUS dele - tunel e DNS em
// <slug>.paulus.ia.br. O advogado nao cria conta, nao mexe em DNS e nao abre
// o painel da Cloudflare. SEM Cloudflare Access, em parte nenhuma: a
// seguranca de quem entra fica toda no PAULUS (Turnstile, senha e TOTP), e
// nenhuma vaga do Zero Trust e gasta por escritorio.
//
// O Worker cria o CAMINHO, nunca o conteudo: ele nao faz proxy de
// *.paulus.ia.br (esse trafego vai direto da Cloudflare ao tunel do
// escritorio) e nao ve documento nenhum. O unico dado que passa por aqui
// depois de conectado e o token do Turnstile do login, para ser conferido.
//
// O titular escolhe o nome, e a confirmacao e a de autorizacao de dispositivo:
//
//   GET  /api/tunel/disponivel?nome=  o nome esta livre? senao, uma sugestao
//   POST /api/tunel/iniciar           o PAULUS pede com o nome escolhido;
//                                     o nome fica reservado 15 min; volta um
//                                     codigo secreto e um codigo XXXX-XXXX
//   GET  /conectar?c=XXXX-XXXX        o titular confere o codigo e passa pelo
//                                     Turnstile - a barreira contra robo
//   POST /conectar                    confirma: tunel, ingress, DNS, token
//   POST /api/tunel/estado            o PAULUS pergunta a cada 3 s; recebe o
//                                     token do tunel UMA vez
//
// Depois, com o segredo da instalacao (Authorization: Bearer):
//
//   POST /api/tunel/turnstile  confere o token do Turnstile de um login
//   POST /api/tunel/porta      a porta do PAULUS mudou
//   GET  /api/tunel/situacao   o tunel esta conectado?
//   POST /api/tunel/remover    apaga DNS, tunel e registro; o nome fica livre
//
// E, uma vez por dia (Cron Trigger), a limpeza: endereco que nunca conectou
// em 7 dias, ou parado ha mais de 180, e removido.
//
// Tudo atras de TUNEL_ATIVO === "1" e do KV ESCRITORIOS: sem os dois, as
// rotas respondem 404 e a limpeza nao faz nada. E isso que deixa este codigo
// ir ao ar no deploy de cada push sem ligar nada.
//
// Caminhos da API conferidos na documentacao da Cloudflare em 28/09/2026
// (docs/PROGRESSO-IMPLEMENTACAO.md, R5).

const API = "https://api.cloudflare.com/client/v4";
const SITEVERIFY = "https://challenges.cloudflare.com/turnstile/v0/siteverify";
const DOMINIO = "paulus.ia.br";
const PEDIDO_TTL_S = 15 * 60;
const DIA_MS = 24 * 3600 * 1000;
const NUNCA_CONECTOU_DIAS = 7;
const PARADO_DIAS = 180;
// O que foi removido fica lembrado por mais de um ano: e assim que o PAULUS
// sabe dizer "o endereco foi liberado por falta de uso", e nao "segredo errado".
const LEMBRAR_REMOVIDO_S = 400 * 24 * 3600;
const RE_CODIGO_USUARIO = /^[A-HJ-NP-Z2-9]{4}-[A-HJ-NP-Z2-9]{4}$/;
const LETRAS = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789";
export const RESERVADOS = new Set(["www", "api", "conectar", "admin", "suporte", "paulus", "atos", "app", "mail",
  "email", "smtp", "imap", "pop", "ftp", "ns1", "ns2", "contato", "status", "blog", "dev", "teste", "testes",
  "staging", "cdn", "static", "assets", "login", "entrar", "conta", "contas", "painel", "ajuda", "site",
  "oficial", "seguranca", "pagamento", "apoio", "apoiar", "loja"]);

// --------------------------------------------------------------- entrada

export function ehRotaDoTunel(url) {
  return url.pathname === "/conectar" || url.pathname.startsWith("/api/tunel/") || url.pathname === "/oauth/google";
}

export async function atenderTunel(request, env, url, { dentroDoLimite, agora = () => Date.now() } = {}) {
  if (env.TUNEL_ATIVO !== "1" || !env.ESCRITORIOS) return texto("rota não existe", 404);
  const p = url.pathname;
  const m = request.method;
  const limitado = async () => Boolean(dentroDoLimite) && !(await dentroDoLimite(request, env));
  if (p === "/api/tunel/disponivel" && m === "GET") {
    if (await limitado()) return json({ erro: "muitas tentativas seguidas - espere um minuto" }, 429);
    return json(await disponibilidade(env, url.searchParams.get("nome"), url.searchParams.get("instalacao") || ""));
  }
  if (p === "/api/tunel/iniciar" && m === "POST") {
    if (await limitado()) return json({ erro: "muitas tentativas seguidas - espere um minuto" }, 429);
    return iniciar(request, env, agora);
  }
  if (p === "/oauth/google" && m === "GET") return retornoDoGoogle(env, url);
  if (p === "/conectar" && m === "GET") return paginaConectar(env, url);
  if (p === "/conectar" && m === "POST") return confirmar(request, env, agora);
  if (p === "/api/tunel/estado" && m === "POST") return estadoDoPedido(request, env);
  if (p === "/api/tunel/turnstile" && m === "POST") return comSegredo(request, env, (e, d) => conferirTurnstile(env, e, d, agora));
  if (p === "/api/tunel/porta" && m === "POST") return comSegredo(request, env, (e, d) => trocarPorta(env, e, d));
  if (p === "/api/tunel/situacao" && m === "GET") return comSegredo(request, env, (e) => situacao(env, e, agora), false);
  if (p === "/api/tunel/remover" && m === "POST") return comSegredo(request, env, (e) => remover(env, e, "removido pelo escritório"), false);
  return json({ erro: "rota não existe" }, 404);
}

// ------------------------------------------------------------- utilidades

// Entrar com o Google, na equipe de um escritorio (PAULUS, E3a): o Google
// so aceita enderecos de retorno cadastrados um a um, e cada escritorio tem o
// seu <slug>.paulus.ia.br. O retorno cadastrado e este; o `state` que o PAULUS
// mandou comeca pelo slug, e daqui a volta segue para o escritorio - com o
// mesmo codigo e o mesmo state, sem guardar nada. O codigo sozinho nao vale:
// a troca pede o verificador PKCE e o segredo, que ficam no PAULUS.
async function retornoDoGoogle(env, url) {
  const state = url.searchParams.get("state") || "";
  const slug = state.split("~")[0];
  if (!slug || motivoDoFormato(slug) || !(await env.ESCRITORIOS.get("escritorio:" + slug))) {
    return texto("este login não é de um escritório conectado ao PAULUS", 400);
  }
  const destino = new URL("https://" + slug + "." + DOMINIO + "/api/acesso/google/retorno");
  for (const chave of ["code", "state", "error"]) {
    const v = url.searchParams.get(chave);
    if (v) destino.searchParams.set(chave, v);
  }
  return new Response(null, {
    status: 302, headers: { location: destino.toString(), "cache-control": "no-store", "referrer-policy": "no-referrer" },
  });
}

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

// ---------------------------------------------------------------- o nome

// O motivo, em linguagem de gente, de um nome nao servir - ou "" se serve.
export function motivoDoFormato(slug) {
  const s = String(slug || "");
  if (s.length < 3) return "use pelo menos 3 letras";
  if (s.length > 24) return "use no máximo 24 letras";
  if (!/^[a-z0-9-]+$/.test(s)) return "use só letras minúsculas sem acento, números e hífen";
  if (s.startsWith("-") || s.endsWith("-")) return "não comece nem termine com hífen";
  if (RESERVADOS.has(s)) return "esse nome é reservado";
  return "";
}

function limpar(bruto) {
  return String(bruto || "").normalize("NFD").replace(/[̀-ͯ]/g, "").toLowerCase()
    .replace(/[^a-z0-9]+/g, "-").replace(/^-+|-+$/g, "").slice(0, 24).replace(/-+$/g, "");
}

// Tomado por um escritorio conectado, ou reservado por OUTRA instalacao que
// esta no meio da conexao.
async function tomado(env, slug, instalacao) {
  if (await env.ESCRITORIOS.get("escritorio:" + slug)) return true;
  const reserva = await kvGet(env, "reserva:" + slug);
  return Boolean(reserva && reserva.instalacao_id !== instalacao);
}

async function sugestao(env, slug, instalacao) {
  const base = (slug.replace(/-\d+$/, "").slice(0, 21).replace(/-+$/, "")) || "escritorio";
  for (let n = 2; n < 100; n++) {
    const s = base + "-" + n;
    if (!motivoDoFormato(s) && !(await tomado(env, s, instalacao))) return s;
  }
  return "";
}

export async function disponibilidade(env, nome, instalacao = "") {
  const slug = String(nome || "").trim().toLowerCase();
  const motivo = motivoDoFormato(slug);
  if (motivo) {
    const limpo = limpar(slug);
    let alternativa = "";
    if (limpo.length >= 3 && !motivoDoFormato(limpo) && !(await tomado(env, limpo, instalacao))) alternativa = limpo;
    else alternativa = await sugestao(env, limpo.length >= 3 ? limpo : "escritorio", instalacao);
    return { disponivel: false, motivo, sugestao: alternativa };
  }
  if (await tomado(env, slug, instalacao)) {
    return { disponivel: false, motivo: "esse endereço já está em uso", sugestao: await sugestao(env, slug, instalacao) };
  }
  return { disponivel: true, motivo: "", sugestao: "" };
}

// ------------------------------------------------------------- iniciar

async function iniciar(request, env, agora) {
  const d = await lerJSON(request);
  if (!d) return json({ erro: "pedido inválido" }, 400);
  const nome = String(d.nome_escritorio || "").trim().replace(/\s+/g, " ");
  const slug = String(d.slug || "").trim().toLowerCase();
  const instalacao = String(d.instalacao_id || "");
  const porta = Number(d.porta);
  if (nome.length < 2 || nome.length > 80) return json({ erro: "diga o nome do escritório (2 a 80 letras)" }, 400);
  if (!/^[A-Za-z0-9-]{8,64}$/.test(instalacao)) return json({ erro: "instalação inválida" }, 400);
  if (!Number.isInteger(porta) || porta < 1024 || porta > 65535) return json({ erro: "porta inválida" }, 400);
  const disp = await disponibilidade(env, slug, instalacao);
  if (!disp.disponivel) return json({ erro: disp.motivo, sugestao: disp.sugestao }, 409);
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
  // O nome fica guardado para esta instalacao enquanto o pedido vale: outro
  // escritorio que escolher o mesmo nome nesses 15 minutos ve "em uso".
  await kvPut(env, "reserva:" + slug, { instalacao_id: instalacao, expira }, PEDIDO_TTL_S);
  await kvPut(env, "pedido:" + h, { estado: "pendente", codigo_usuario: usuario, slug, nome, instalacao_id: instalacao, porta, expira }, PEDIDO_TTL_S);
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

// ------------------------------------------------------------ Turnstile

// Confere um token do Turnstile na Cloudflare. `hostname` e onde o desafio
// tem de ter sido resolvido: paulus.ia.br, na pagina de conectar; o endereco
// do escritorio, no login de cada PAULUS - um token resolvido no endereco de
// outro escritorio nao vale. Um token so vale uma vez e por 5 minutos.
// Um widget so, com paulus.ia.br na lista de hostnames, vale para todos os
// subdominios (documentacao do Turnstile, 28/09/2026).
export async function turnstileValido(env, token, hostname, ip) {
  const t = String(token || "");
  if (!t || t.length > 2048 || !env.TURNSTILE_SECRET) return false;
  const corpo = new URLSearchParams({ secret: env.TURNSTILE_SECRET, response: t });
  if (ip) corpo.set("remoteip", String(ip));
  try {
    const r = await fetch(SITEVERIFY, { method: "POST", body: corpo });
    const d = await r.json();
    return Boolean(d && d.success === true && String(d.hostname || "").toLowerCase() === hostname);
  } catch (e) {
    return false;
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

function pagina(titulo, corpo, status = 200, comTurnstile = false) {
  const html = `<!doctype html><html lang="pt-BR"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>PAULUS — ${esc(titulo)}</title>${comTurnstile ? '<script src="https://challenges.cloudflare.com/turnstile/v0/api.js" async defer></script>' : ""}<style>
body{margin:0;min-height:100vh;display:grid;place-items:center;background:#faf9f6;color:#1c1c1a;font-family:Manrope,system-ui,-apple-system,"Segoe UI",sans-serif;padding:24px 16px;box-sizing:border-box}
main{max-width:520px;width:100%}h1{font-family:"EB Garamond",Georgia,serif;font-weight:500;font-size:30px;line-height:1.15;margin:0 0 10px}
p{color:#6b6b65;line-height:1.55;font-size:15px}code{font-family:"Fira Code",ui-monospace,monospace;color:#1c1c1a}
a{color:#1c1c1a}.codigo{display:block;font:600 28px/1.2 "Fira Code",ui-monospace,monospace;letter-spacing:.16em;color:#1c1c1a;margin:6px 0 14px}
.cartao{background:#fff;border:1px solid rgba(28,28,26,.08);border-radius:14px;padding:22px;margin-top:18px}
.cf-turnstile{margin:6px 0 16px;min-height:65px}
button{font:inherit;font-weight:600;min-height:44px;width:100%;border:0;border-radius:10px;background:#26251f;color:#f2f1ec;cursor:pointer}
.pe{font-size:12.5px;color:#9a9a93;margin-top:18px}</style></head><body><main>${corpo}</main></body></html>`;
  const csp = "default-src 'none'; style-src 'unsafe-inline'; form-action 'self'; frame-ancestors 'none'; base-uri 'none'" +
    (comTurnstile ? "; script-src https://challenges.cloudflare.com; frame-src https://challenges.cloudflare.com; connect-src https://challenges.cloudflare.com" : "");
  return new Response(html, { status, headers: { "content-type": "text/html; charset=utf-8", "cache-control": "no-store",
    "x-frame-options": "DENY", "referrer-policy": "no-referrer", "x-content-type-options": "nosniff", "content-security-policy": csp } });
}

function vencido() {
  return pagina("Código vencido", "<h1>Este código não vale mais</h1><p>Ele dura 15 minutos. Comece de novo no PAULUS do escritório — o nome escolhido continua lá.</p>", 410);
}

async function paginaConectar(env, url) {
  const achado = await pedidoDoCodigo(env, url.searchParams.get("c"));
  if (!achado) return vencido();
  const { pedido } = achado;
  if (pedido.estado !== "pendente") return pagina("Já conectado", "<h1>Pronto</h1><p>Este pedido já foi confirmado. Volte ao PAULUS do escritório.</p>");
  const host = pedido.slug + "." + DOMINIO;
  return pagina("Conectar", `<h1>Conectar o PAULUS do escritório?</h1>
<p>O PAULUS de <b>${esc(pedido.nome)}</b> vai atender em <code>https://${esc(host)}</code>, pelo túnel da Cloudflare. Quem entrar por esse endereço passa por uma verificação contra robôs, pela senha e pelo código do autenticador de cada pessoa.</p>
<form class="cartao" method="post" action="/conectar"><input type="hidden" name="c" value="${esc(pedido.codigo_usuario)}">
<p style="margin-top:0">Confira se é o mesmo código que aparece no PAULUS:</p><span class="codigo">${esc(pedido.codigo_usuario)}</span>
<div class="cf-turnstile" data-sitekey="${esc(env.TURNSTILE_SITEKEY || "")}" data-language="pt-br"></div>
<button type="submit">Confirmar</button></form>
<p class="pe">Os documentos e o modelo de IA continuam no computador do escritório. O Atos cria o endereço e não roteia, não inspeciona nem registra o conteúdo que passa por ele.</p>`, 200, true);
}

async function confirmar(request, env, agora) {
  let codigo = "", token = "";
  try {
    const f = await request.formData();
    codigo = String(f.get("c") || "");
    token = String(f.get("cf-turnstile-response") || "");
  } catch (e) { /* formulario torto: cai no "codigo vencido" */ }
  const achado = await pedidoDoCodigo(env, codigo);
  if (!achado) return vencido();
  const { hash, pedido } = achado;
  if (pedido.estado !== "pendente") return pagina("Já conectado", "<h1>Pronto</h1><p>Volte ao PAULUS do escritório.</p>");
  // A barreira contra criacao de enderecos em massa: nada e criado sem o
  // Turnstile resolvido nesta pagina.
  if (!(await turnstileValido(env, token, DOMINIO, request.headers.get("cf-connecting-ip")))) {
    return pagina("Verificação", `<h1>Não deu para confirmar</h1><p>A verificação contra robôs não passou ou venceu. <a href="/conectar?c=${esc(pedido.codigo_usuario)}">Tente de novo</a>.</p>`, 403);
  }
  if (await env.ESCRITORIOS.get("escritorio:" + pedido.slug)) {
    return pagina("Nome em uso", "<h1>Esse endereço acabou de ser usado</h1><p>Volte ao PAULUS do escritório e escolha outro nome.</p>", 409);
  }
  let criado;
  try {
    criado = await provisionar(env, pedido.slug, pedido, agora);
  } catch (e) {
    return pagina("Não deu certo", `<h1>Não consegui criar o endereço</h1><p>Nada ficou pela metade: o que tinha sido criado foi desfeito. Tente de novo em alguns minutos.</p><p class="pe">${esc(e.message)}</p>`, 502);
  }
  await env.ESCRITORIOS.delete("reserva:" + pedido.slug);
  await kvPut(env, "pedido:" + hash, { ...pedido, estado: "pronto", entrega: criado.entrega }, PEDIDO_TTL_S);
  return pagina("Conectado", `<h1>Conectado</h1><p>O PAULUS do escritório já recebeu o endereço <code>${esc(criado.entrega.endereco)}</code> e liga o túnel sozinho. Pode fechar esta página.</p>`);
}

// Os passos, na ordem do contrato. Falha em qualquer um desfaz os anteriores:
// escritorio pela metade na conta do Atos e lixo que ninguem ve.
export async function provisionar(env, slug, pedido, agora = () => Date.now()) {
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
    const token = await chamarCF(env, "GET", a + "/cfd_tunnel/" + tunel.id + "/token");
    const segredo = aleatorio(32);
    const registro = {
      slug, tunnel_id: tunel.id, dns_id: dns.id, instalacao_id: pedido.instalacao_id, nome: pedido.nome,
      hash_segredo: await resumo(segredo), porta: pedido.porta, criado_em: new Date(agora()).toISOString(), ultima_conexao: null,
    };
    await kvPut(env, "escritorio:" + slug, registro);
    feito.push(() => env.ESCRITORIOS.delete("escritorio:" + slug));
    await kvPut(env, "segredo:" + registro.hash_segredo, { slug });
    await kvPut(env, "instalacao:" + pedido.instalacao_id, { slug });
    return {
      registro,
      entrega: { endereco: "https://" + host, hostname: host, tunnel_token: token, turnstile_sitekey: env.TURNSTILE_SITEKEY || "",
        segredo_instalacao: segredo },
    };
  } catch (e) {
    await desfazer();
    throw e;
  }
}

function ingress(host, porta) {
  return { config: { ingress: [{ hostname: host, service: "http://127.0.0.1:" + porta, originRequest: {} }, { service: "http_status:404" }] } };
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
  if (!registro || !igual(registro.hash_segredo, h)) {
    // O endereco foi removido (pelo escritorio ou pela limpeza): o PAULUS
    // precisa saber, para desligar e avisar - e nao ficar tentando.
    const removido = await kvGet(env, "removido:" + h);
    if (removido) return json({ erro: "endereço removido", removido: true, motivo: removido.motivo }, 410);
    return json({ erro: "não autorizado" }, 401);
  }
  const dados = comCorpo ? await lerJSON(request) : null;
  if (comCorpo && !dados) return json({ erro: "pedido inválido" }, 400);
  try {
    return await fazer(registro, dados);
  } catch (e) {
    return json({ erro: e.message }, 502);
  }
}

async function marcarConexao(env, registro, quando) {
  await kvPut(env, "escritorio:" + registro.slug, { ...registro, ultima_conexao: new Date(quando).toISOString() });
}

// So o token do Turnstile passa por aqui - nunca conteudo. O segredo do
// Turnstile fica no Worker e nunca vai para o PAULUS instalado.
async function conferirTurnstile(env, registro, dados, agora) {
  const host = registro.slug + "." + DOMINIO;
  const ok = await turnstileValido(env, dados.token, host, dados.ip);
  await marcarConexao(env, registro, agora());
  return json({ ok });
}

async function trocarPorta(env, registro, dados) {
  const porta = Number(dados.porta);
  if (!Number.isInteger(porta) || porta < 1024 || porta > 65535) return json({ erro: "porta inválida" }, 400);
  await chamarCF(env, "PUT", "/accounts/" + env.CF_ACCOUNT_ID + "/cfd_tunnel/" + registro.tunnel_id + "/configurations",
    ingress(registro.slug + "." + DOMINIO, porta));
  await kvPut(env, "escritorio:" + registro.slug, { ...registro, porta });
  return json({ ok: true, porta });
}

async function situacao(env, registro, agora) {
  const t = await chamarCF(env, "GET", "/accounts/" + env.CF_ACCOUNT_ID + "/cfd_tunnel/" + registro.tunnel_id);
  const conectado = t.status === "healthy" || t.status === "degraded";
  await marcarConexao(env, registro, agora());
  return json({ hostname: registro.slug + "." + DOMINIO, status: t.status || "desconhecido", conectado, porta: registro.porta });
}

async function remover(env, registro, motivo) {
  const a = "/accounts/" + env.CF_ACCOUNT_ID;
  const erros = [];
  const tentar = async (f) => { try { await f(); } catch (e) { erros.push(e.message); } };
  await tentar(() => chamarCF(env, "DELETE", "/zones/" + env.CF_ZONE_ID + "/dns_records/" + registro.dns_id));
  await tentar(() => chamarCF(env, "DELETE", a + "/cfd_tunnel/" + registro.tunnel_id + "/connections"));
  await tentar(() => chamarCF(env, "DELETE", a + "/cfd_tunnel/" + registro.tunnel_id));
  await env.ESCRITORIOS.delete("escritorio:" + registro.slug);
  await env.ESCRITORIOS.delete("segredo:" + registro.hash_segredo);
  await env.ESCRITORIOS.delete("instalacao:" + registro.instalacao_id);
  await kvPut(env, "removido:" + registro.hash_segredo, { slug: registro.slug, motivo, quando: new Date().toISOString() }, LEMBRAR_REMOVIDO_S);
  return json({ ok: true, avisos: erros });
}

// ------------------------------------------------------------ limpeza

// Roda uma vez por dia (Cron Trigger, worker/index.js). Endereco que nunca
// conectou em 7 dias e o que ficou parado mais de 180 sao removidos, e o
// nome volta a ficar livre. A "ultima conexao" e a mais nova entre o que o
// PAULUS contou (turnstile, situacao) e o que a Cloudflare sabe do tunel.
export async function limparEscritorios(env, agora = () => Date.now()) {
  const feito = { removidos: [], mantidos: 0 };
  if (env.TUNEL_ATIVO !== "1" || !env.ESCRITORIOS) return feito;
  let cursor;
  do {
    const lista = await env.ESCRITORIOS.list({ prefix: "escritorio:", cursor });
    for (const { name } of lista.keys) {
      const registro = await kvGet(env, name);
      if (!registro) continue;
      const antes = registro.ultima_conexao ? Date.parse(registro.ultima_conexao) || 0 : 0;
      let ultima = antes;
      let conectadoAgora = false;
      try {
        const t = await chamarCF(env, "GET", "/accounts/" + env.CF_ACCOUNT_ID + "/cfd_tunnel/" + registro.tunnel_id);
        conectadoAgora = t.status === "healthy" || t.status === "degraded";
        if (conectadoAgora) ultima = agora();
        else if (t.conns_inactive_at) ultima = Math.max(ultima, Date.parse(t.conns_inactive_at) || 0);
      } catch (e) {
        // Sem resposta da API, nada e removido hoje: remover por engano um
        // escritorio que funciona e muito pior que esperar um dia.
        feito.mantidos++;
        continue;
      }
      const criado = Date.parse(registro.criado_em) || agora();
      let motivo = "";
      if (!conectadoAgora && !ultima && agora() - criado > NUNCA_CONECTOU_DIAS * DIA_MS) motivo = "nunca conectou em 7 dias";
      else if (!conectadoAgora && ultima && agora() - ultima > PARADO_DIAS * DIA_MS) motivo = "parado há mais de 180 dias";
      if (motivo) {
        await remover(env, registro, motivo);
        feito.removidos.push({ slug: registro.slug, motivo });
      } else {
        if (ultima !== antes) await marcarConexao(env, registro, ultima);
        feito.mantidos++;
      }
    }
    cursor = lista.list_complete ? undefined : lista.cursor;
  } while (cursor);
  return feito;
}
