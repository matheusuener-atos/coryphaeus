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
//   POST /api/tunel/dono       de que conta Google e este escritorio (id_token)
//
// O endereco e da conta Google que vinculou o PAULUS: POST /api/tunel/meus
// (com o id_token) lista os dela, e conectar com o mesmo id_token retoma um
// deles em outra instalacao.
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
    const dono = await donoDoToken(env, request.headers.get("x-paulus-google"), agora);
    return json(await disponibilidade(env, url.searchParams.get("nome"), url.searchParams.get("instalacao") || "", dono));
  }
  if (p === "/api/tunel/meus" && m === "POST") {
    if (await limitado()) return json({ erro: "muitas tentativas seguidas - espere um minuto" }, 429);
    return meus(request, env, agora);
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
  if (p === "/api/tunel/dono" && m === "POST") return comSegredo(request, env, (e, d) => definirDono(env, e, d, agora));
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

export async function disponibilidade(env, nome, instalacao = "", dono = null) {
  const slug = String(nome || "").trim().toLowerCase();
  const motivo = motivoDoFormato(slug);
  if (motivo) {
    const limpo = limpar(slug);
    let alternativa = "";
    if (limpo.length >= 3 && !motivoDoFormato(limpo) && !(await tomado(env, limpo, instalacao))) alternativa = limpo;
    else alternativa = await sugestao(env, limpo.length >= 3 ? limpo : "escritorio", instalacao);
    return { disponivel: false, motivo, sugestao: alternativa };
  }
  if (dono && mesmoDono(await kvGet(env, "escritorio:" + slug), dono)) {
    // O endereco e desta conta Google, de outra instalacao (ou de antes de
    // reinstalar): conectar de novo o retoma - o PAULUS antigo e desligado.
    return { disponivel: true, retomar: true, motivo: "", sugestao: "" };
  }
  if (await tomado(env, slug, instalacao)) {
    return { disponivel: false, motivo: "esse endereço já está em uso", sugestao: await sugestao(env, slug, instalacao),
      em_uso: true };
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
  // A conta Google de quem conecta (o PAULUS manda o id_token do vinculo).
  // Sem ele, o endereco nasce sem dono - o PAULUS de antes desta versao.
  const dono = d.id_token ? await donoDoToken(env, d.id_token, agora) : null;
  if (d.id_token && !dono) return json({ erro: "a confirmação do Google venceu: entre com o Google de novo" }, 401);
  const disp = await disponibilidade(env, slug, instalacao, dono);
  if (!disp.disponivel) return json({ erro: disp.motivo, sugestao: disp.sugestao }, 409);
  if (await env.ESCRITORIOS.get("instalacao:" + instalacao)) {
    return json({ erro: "esta instalação do PAULUS já tem acesso de fora: remova antes de conectar de novo" }, 409);
  }
  const limite = Number(env.MAX_ESCRITORIOS || 0);
  if (limite && !disp.retomar && (await contarEscritorios(env)) >= limite) {
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
  await kvPut(env, "pedido:" + h, { estado: "pendente", codigo_usuario: usuario, slug, nome, instalacao_id: instalacao, porta, expira,
    dono, retomar: Boolean(disp.retomar) }, PEDIDO_TTL_S);
  await kvPut(env, "usuario:" + usuario, { pedido: h }, PEDIDO_TTL_S);
  return json({
    codigo_dispositivo: dispositivo,
    codigo_usuario: usuario,
    retomar: Boolean(disp.retomar),
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

// ------------------------------------------------ o dono (a conta Google)

// O endereco pertence a conta Google que vinculou o PAULUS (E5), e nao so a
// instalacao: reinstalou, trocou de computador, perdeu os dados - a mesma
// conta retoma o mesmo endereco. A prova e o id_token do Google, assinado por
// ele, que o PAULUS recebe no login do vinculo (vale 1 hora). Daqui so fica
// o `sub` (o numero da conta no Google) e o e-mail.
const GOOGLE_CERTS = "https://www.googleapis.com/oauth2/v3/certs";
let chavesDoGoogle = { em: 0, chaves: null };

function b64url(s) {
  const b = atob(String(s).replace(/-/g, "+").replace(/_/g, "/") + "===".slice((String(s).length + 3) % 4));
  return Uint8Array.from(b, (c) => c.charCodeAt(0));
}

async function chaveDoGoogle(kid, agora) {
  if (!chavesDoGoogle.chaves || agora() - chavesDoGoogle.em > 3600 * 1000 || !chavesDoGoogle.chaves.some((k) => k.kid === kid)) {
    const r = await fetch(GOOGLE_CERTS);
    const d = await r.json();
    chavesDoGoogle = { em: agora(), chaves: Array.isArray(d.keys) ? d.keys : [] };
  }
  return chavesDoGoogle.chaves.find((k) => k.kid === kid) || null;
}

// { sub, email } de um id_token valido para um dos clientes do PAULUS; ou null.
export async function donoDoToken(env, token, agora = () => Date.now()) {
  const t = String(token || "");
  const partes = t.split(".");
  if (partes.length !== 3 || t.length > 4096) return null;
  try {
    const cab = JSON.parse(new TextDecoder().decode(b64url(partes[0])));
    const info = JSON.parse(new TextDecoder().decode(b64url(partes[1])));
    if (cab.alg !== "RS256") return null;
    const jwk = await chaveDoGoogle(cab.kid, agora);
    if (!jwk) return null;
    const chave = await crypto.subtle.importKey("jwk", { kty: "RSA", n: jwk.n, e: jwk.e, alg: "RS256", ext: true },
      { name: "RSASSA-PKCS1-v1_5", hash: "SHA-256" }, false, ["verify"]);
    const ok = await crypto.subtle.verify("RSASSA-PKCS1-v1_5", chave, b64url(partes[2]),
      new TextEncoder().encode(partes[0] + "." + partes[1]));
    if (!ok) return null;
    const clientes = String(env.GOOGLE_CLIENT_IDS || "").split(",").map((x) => x.trim()).filter(Boolean);
    if (!["accounts.google.com", "https://accounts.google.com"].includes(info.iss)) return null;
    if (!clientes.includes(info.aud)) return null;
    if (!(Number(info.exp) * 1000 > agora())) return null;
    if (info.email_verified !== true && info.email_verified !== "true") return null;
    if (!info.sub || !info.email) return null;
    return { sub: String(info.sub), email: String(info.email).toLowerCase() };
  } catch (e) {
    return null;
  }
}

function mesmoDono(registro, dono) {
  return Boolean(dono && registro && registro.dono && registro.dono.sub === dono.sub);
}

async function enderecosDoDono(env, dono) {
  if (!dono) return [];
  const indice = (await kvGet(env, "dono:" + dono.sub)) || { slugs: [] };
  const lista = [];
  for (const slug of indice.slugs || []) {
    const r = await kvGet(env, "escritorio:" + slug);
    if (mesmoDono(r, dono)) lista.push({ slug, nome: r.nome || "", ultima_conexao: r.ultima_conexao || null });
  }
  return lista;
}

async function anotarDono(env, slug, dono) {
  if (!dono) return;
  const indice = (await kvGet(env, "dono:" + dono.sub)) || { slugs: [] };
  if (!indice.slugs.includes(slug)) await kvPut(env, "dono:" + dono.sub, { slugs: [...indice.slugs, slug] });
}

async function esquecerDono(env, registro) {
  if (!registro || !registro.dono) return;
  const indice = await kvGet(env, "dono:" + registro.dono.sub);
  if (!indice) return;
  const slugs = (indice.slugs || []).filter((s) => s !== registro.slug);
  if (slugs.length) await kvPut(env, "dono:" + registro.dono.sub, { slugs });
  else await env.ESCRITORIOS.delete("dono:" + registro.dono.sub);
}

// Os enderecos desta conta Google (o PAULUS mostra "retomar").
async function meus(request, env, agora) {
  const d = await lerJSON(request);
  const dono = await donoDoToken(env, d && d.id_token, agora);
  if (!dono) return json({ erro: "confirme a conta Google de novo" }, 401);
  return json({ email: dono.email, enderecos: await enderecosDoDono(env, dono) });
}

// Um PAULUS ja conectado diz de que conta Google ele e (os conectados antes
// disso, e a cada vinculo novo).
async function definirDono(env, registro, dados, agora) {
  const dono = await donoDoToken(env, dados.id_token, agora);
  if (!dono) return json({ erro: "confirme a conta Google de novo" }, 401);
  if (registro.dono && registro.dono.sub !== dono.sub) await esquecerDono(env, registro);
  await kvPut(env, "escritorio:" + registro.slug, { ...registro, dono });
  await anotarDono(env, registro.slug, dono);
  return json({ ok: true, email: dono.email });
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

// As paginas do Worker no desenho "Conectar escritorio" (docs/ui, export
// retorno-google): a marca e o tema no topo, o texto a esquerda e o painel a
// direita. Escuro por padrao; o botao do canto troca e lembra (o mesmo
// "paulus.tema" do programa). As fontes sao as do site.
const TONS = { ok: "var(--ok)", aviso: "var(--warn)", erro: "var(--erro)", neutro: "var(--ink3)" };
const SETA = '<svg viewBox="0 0 24 24" width="16" height="16" aria-hidden="true" fill="currentColor"><path d="M16.2 13H4v-2h12.2l-5.6-5.6L12 4l8 8-8 8-1.4-1.4 5.6-5.6Z"/></svg>';
const SETA_FORA = '<svg viewBox="0 0 24 24" width="16" height="16" aria-hidden="true" fill="currentColor"><path d="M6.4 18 5 16.6 14.6 7H6V5h12v12h-2V8.4L6.4 18Z"/></svg>';

// O script da pagina: o tema e, com o Turnstile, o widget desenhado no tema
// da vez (render explicito). Vai na CSP pelo hash - nenhum outro script inline roda.
const SCRIPT_PAGINA = `(function(){var d=document.documentElement,t="escuro";try{var g=localStorage.getItem("paulus.tema");if(g==="claro"||g==="escuro")t=g}catch(e){}d.dataset.tema=t;
var SOL='<svg viewBox="0 0 24 24" width="18" height="18" fill="currentColor" aria-hidden="true"><path d="M12 17q-2.08 0-3.54-1.46Q7 14.08 7 12t1.46-3.54Q9.92 7 12 7t3.54 1.46Q17 9.92 17 12t-1.46 3.54Q14.08 17 12 17ZM2 13v-2h3v2H2Zm17 0v-2h3v2h-3ZM11 5V2h2v3h-2Zm0 17v-3h2v3h-2ZM6.35 7.75 4.5 5.9l1.4-1.4 1.85 1.85-1.4 1.4Zm11.75 11.75-1.85-1.85 1.4-1.4 1.85 1.85-1.4 1.4Zm-1.85-13.15L18.1 4.5l1.4 1.4-1.85 1.85-1.4-1.4ZM4.5 18.1l1.85-1.85 1.4 1.4L5.9 19.5l-1.4-1.4Z"/></svg>';
var LUA='<svg viewBox="0 0 24 24" width="18" height="18" fill="currentColor" aria-hidden="true"><path d="M12 21q-3.75 0-6.37-2.63Q3 15.75 3 12t2.63-6.37Q8.25 3 12 3q.35 0 .69.02.34.03.66.08-1.03.72-1.64 1.89Q11.1 6.15 11.1 7.5q0 2.25 1.58 3.83Q14.25 12.9 16.5 12.9q1.38 0 2.53-.61 1.16-.61 1.87-1.64.05.33.08.66Q21 11.65 21 12q0 3.75-2.63 6.37Q15.75 21 12 21Z"/></svg>';
var robo=null;function desenharRobo(){var el=document.getElementById("robo");if(!window.turnstile)return;if(!el){if(document.readyState==="loading")document.addEventListener("DOMContentLoaded",desenharRobo,{once:true});return}if(robo!==null){window.turnstile.remove(robo)}
robo=window.turnstile.render(el,{sitekey:el.dataset.sitekey,language:"pt-br",theme:d.dataset.tema==="escuro"?"dark":"light",
callback:function(){var b=document.getElementById("confirmar");if(b)b.disabled=false}})}
window.paulusRobo=desenharRobo;
document.addEventListener("DOMContentLoaded",function(){var b=document.getElementById("tema");if(!b)return;
var pintar=function(){b.innerHTML=d.dataset.tema==="escuro"?SOL:LUA};pintar();
b.addEventListener("click",function(){d.dataset.tema=d.dataset.tema==="escuro"?"claro":"escuro";try{localStorage.setItem("paulus.tema",d.dataset.tema)}catch(e){}pintar();desenharRobo()})})})();`;
let hashDoScript = "";

async function hashScript() {
  if (!hashDoScript) {
    const d = await crypto.subtle.digest("SHA-256", new TextEncoder().encode(SCRIPT_PAGINA));
    hashDoScript = "'sha256-" + btoa(String.fromCharCode(...new Uint8Array(d))) + "'";
  }
  return hashDoScript;
}

// A tabela do painel: rotulo e valor, uma linha cada.
function linhas(pares) {
  return '<div class="linhas">' + pares.map(([r, v]) => `<div class="linha"><span class="r">${r}</span><span>${v}</span></div>`).join("") + "</div>";
}

async function pagina(titulo, { rotulo, tom = "neutro", h1, texto = "", nota = "", painel = "", topo = DOMINIO }, status = 200, comTurnstile = false) {
  const html = `<!doctype html><html lang="pt-BR" data-tema="escuro"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<title>PAULUS — ${esc(titulo)}</title><link rel="icon" href="/favicon.ico" sizes="any"><link rel="icon" type="image/png" href="/assets/favicon-32.png">
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=EB+Garamond:ital,wght@0,400;0,500;1,400&family=Manrope:wght@400;500;600&family=Fira+Code:wght@400;500&display=swap">
<script>${SCRIPT_PAGINA}</script>
${comTurnstile ? '<script src="https://challenges.cloudflare.com/turnstile/v0/api.js?render=explicit&onload=paulusRobo" async defer></script>' : ""}<style>
[data-tema="claro"]{--bg:#fff;--ink:#171716;--ink2:#5c5c59;--ink3:#8a8a86;--line:rgba(23,23,22,.1);--line2:rgba(23,23,22,.22);
--fill:#f1f1ee;--btn:#171716;--btnt:#f6f6f4;--ok:#2f6b42;--warn:#8a5a12;--erro:#a3322b;color-scheme:light}
[data-tema="escuro"]{--bg:#111110;--ink:#f6f6f4;--ink2:#b5b5b0;--ink3:#8a8a86;--line:rgba(255,255,255,.12);--line2:rgba(255,255,255,.26);--fill:#242422;
--btn:#f6f6f4;--btnt:#171716;--ok:#8fd0a3;--warn:#e8c283;--erro:#f0a19c;color-scheme:dark}
*{box-sizing:border-box}html,body{margin:0;min-height:100%}
body{min-height:100vh;display:flex;flex-direction:column;background:var(--bg);color:var(--ink);font-family:Manrope,system-ui,-apple-system,"Segoe UI",sans-serif;
font-size:15px;line-height:1.6;-webkit-font-smoothing:antialiased}
a{color:inherit}.mono{font-family:"Fira Code",ui-monospace,monospace}.serif{font-family:"EB Garamond",Georgia,serif}
header{padding:10px clamp(20px,5vw,88px);min-height:64px;display:flex;align-items:center;justify-content:space-between;gap:12px 24px;border-bottom:1px solid var(--line)}
.marca{font-size:24px;letter-spacing:.14em;font-weight:500;line-height:1;text-decoration:none}
.topo{display:flex;align-items:center;gap:18px}.dominio{font-size:12px;color:var(--ink3)}
.tema{width:36px;height:36px;border:0;background:transparent;color:var(--ink2);display:flex;align-items:center;justify-content:center;cursor:pointer;padding:0}
.tema:hover{color:var(--ink)}
main{flex:1;width:100%;max-width:1280px;margin:0 auto;padding:clamp(56px,9vw,120px) clamp(20px,5vw,48px);display:flex;flex-wrap:wrap;
gap:48px clamp(48px,8vw,112px);align-items:start}
.texto{flex:1 1 380px;min-width:0;display:grid;gap:20px}
.rotulo{display:flex;align-items:center;gap:8px;font-size:11px;letter-spacing:.16em;color:var(--tom)}
.rotulo i{display:block;width:6px;height:6px;border-radius:50%;background:var(--tom)}
h1{margin:0;font-weight:400;font-size:clamp(44px,6vw,68px);line-height:1;letter-spacing:-.02em;text-wrap:balance}
.texto p{margin:0;font-size:clamp(17px,1.8vw,19px);line-height:1.6;color:var(--ink2);text-wrap:pretty;max-width:480px}
.texto p b{color:var(--ink);font-weight:600}
.nota{font-style:italic;font-size:19px;color:var(--ink3)}
.painel{flex:1 1 360px;min-width:0;max-width:520px;border-left:1px solid var(--line);padding-left:clamp(24px,3vw,40px);display:grid;gap:24px}
.painel:empty{display:none}
form{display:grid;gap:22px;margin:0}
.linhas{display:grid;gap:2px}
.linha{display:grid;grid-template-columns:120px minmax(0,1fr);gap:12px;padding:12px 0;border-bottom:1px solid var(--line);font-size:14px}
.linha .r{color:var(--ink2)}.linha b{font-weight:600}
.linha .end{font-family:"Fira Code",ui-monospace,monospace;font-size:13px;word-break:break-all}
.bloco{display:grid;gap:8px}
.etiqueta{font-size:11px;letter-spacing:.14em;color:var(--ink3)}
.codigo{font:500 clamp(30px,3.4vw,38px)/1.1 "Fira Code",ui-monospace,monospace;letter-spacing:.18em}
.ajuda{margin:0;font-size:13.5px;line-height:1.6;color:var(--ink2);text-wrap:pretty}
.robo{min-height:65px;display:flex;align-items:center;gap:10px;border-top:1px solid var(--line);border-bottom:1px solid var(--line);font-size:13.5px;color:var(--ink2)}
.acoes{display:flex;align-items:center;gap:18px;flex-wrap:wrap}
.dica{font-size:12.5px;color:var(--ink3)}
.principal{height:36px;padding:0 18px;border:0;border-radius:999px;background:var(--btn);color:var(--btnt);font:inherit;font-size:13.5px;font-weight:600;
cursor:pointer;display:inline-flex;align-items:center;gap:6px;text-decoration:none}
.principal:hover{opacity:.88}.principal:disabled{opacity:.5;cursor:default}
.detalhe{font-family:"Fira Code",ui-monospace,monospace;font-size:13.5px;color:var(--ink2);word-break:break-all;padding-bottom:14px;border-bottom:1px solid var(--line)}
footer{border-top:1px solid var(--line);padding:24px clamp(20px,5vw,88px)}
footer p{margin:0;max-width:720px;font-size:13px;line-height:1.65;color:var(--ink3);text-wrap:pretty}
@media (max-width:760px){.painel{border-left:0;padding-left:0;max-width:none}main{padding-top:40px}}
</style></head><body style="--tom:${TONS[tom] || TONS.neutro}">
<header><a class="marca serif" href="/">PAVLVS</a><div class="topo"><span class="dominio mono">${esc(topo)}</span>
<button type="button" class="tema" id="tema" aria-label="Alternar tema"></button></div></header>
<main><section class="texto"><span class="rotulo mono"><i></i>${esc(rotulo)}</span><h1 class="serif">${h1}</h1>${texto}
${nota ? `<span class="nota serif">${nota}</span>` : ""}</section>
<section class="painel">${painel}</section></main>
<footer><p>Os documentos e o modelo de IA continuam no computador do escritório. O Atos cria o endereço e não roteia, não inspeciona nem registra o conteúdo que passa por ele.</p></footer>
</body></html>`;
  const csp = "default-src 'none'; style-src 'unsafe-inline' https://fonts.googleapis.com; font-src https://fonts.gstatic.com; img-src 'self'; form-action 'self'; frame-ancestors 'none'; base-uri 'none'" +
    "; script-src " + (await hashScript()) + (comTurnstile ? " https://challenges.cloudflare.com; frame-src https://challenges.cloudflare.com; connect-src https://challenges.cloudflare.com" : "");
  return new Response(html, { status, headers: { "content-type": "text/html; charset=utf-8", "cache-control": "no-store",
    "x-frame-options": "DENY", "referrer-policy": "no-referrer", "x-content-type-options": "nosniff", "content-security-policy": csp } });
}

const VOLTE = '<div class="acoes"><span class="dica">Volte ao PAVLVS do escritório: ele mostra o próximo passo.</span></div>';

function vencido() {
  return pagina("Código vencido", { rotulo: "CÓDIGO VENCIDO", tom: "erro", h1: "Este código expirou.",
    texto: "<p>Ele vale por 15 minutos. Comece de novo no PAVLVS do escritório — o nome escolhido continua lá.</p>",
    nota: "Nada foi criado.", painel: VOLTE }, 410);
}

function jaConectado() {
  return pagina("Já conectado", { rotulo: "CONECTADO", tom: "ok", h1: "Este pedido já foi confirmado.",
    texto: "<p>O endereço já existe e o PAVLVS do escritório já o recebeu.</p>", nota: "Já pode fechar esta página.", painel: VOLTE });
}

function linhasDoPedido(pedido, endereco) {
  return linhas([
    ["Escritório", `<b>${esc(pedido.nome)}</b>`],
    ["Endereço", `<span class="end">${esc(endereco)}</span>`],
    ...(pedido.retomar && pedido.dono ? [["Conta Google", esc(pedido.dono.email)]] : []),
    ["Entrada", "conta Google e código do celular"],
  ]);
}

async function paginaConectar(env, url) {
  const achado = await pedidoDoCodigo(env, url.searchParams.get("c"));
  if (!achado) return vencido();
  const { pedido } = achado;
  if (pedido.estado !== "pendente") return jaConectado();
  const endereco = "https://" + pedido.slug + "." + DOMINIO;
  return pagina("Conectar", {
    topo: DOMINIO + "/conectar",
    rotulo: pedido.retomar ? "ENDEREÇO DA SUA CONTA" : "NOVO ENDEREÇO",
    h1: pedido.retomar ? "Retomar o endereço do escritório?" : "Conectar o PAVLVS do escritório?",
    texto: pedido.retomar
      ? `<p>Este endereço já é da conta Google <b>${esc(pedido.dono.email)}</b>. Confirmando, ele passa para o PAVLVS de <b>${esc(pedido.nome)}</b> neste computador, e o de antes deixa de atender por ele.</p>`
      : `<p>O PAVLVS de <b>${esc(pedido.nome)}</b> passa a atender neste endereço pelo túnel da Cloudflare. Quem entrar por ele passa por uma verificação contra robôs, pela conta Google e pelo código do celular de cada pessoa.</p>`,
    nota: "Você pode desligar o acesso de fora quando quiser.",
    painel: linhasDoPedido(pedido, endereco) + `<form method="post" action="/conectar"><input type="hidden" name="c" value="${esc(pedido.codigo_usuario)}">
<div class="bloco"><span class="etiqueta mono">CÓDIGO NO PAVLVS</span><span class="codigo">${esc(pedido.codigo_usuario)}</span>
<span class="ajuda">Confira se é o mesmo código que aparece na tela do PAVLVS.</span></div>
<div class="robo" aria-label="Verificação contra robôs"><div id="robo" data-sitekey="${esc(env.TURNSTILE_SITEKEY || "")}"></div></div>
<div class="acoes"><button class="principal" type="submit" id="confirmar">${pedido.retomar ? "Retomar" : "Confirmar"}${SETA}</button>
<span class="dica">código diferente? feche esta página</span></div></form>`,
  }, 200, true);
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
  if (pedido.estado !== "pendente") return jaConectado();
  const tentar = `<div class="acoes"><a class="principal" href="/conectar?c=${esc(pedido.codigo_usuario)}">Tentar de novo${SETA}</a></div>`;
  // A barreira contra criacao de enderecos em massa: nada e criado sem o
  // Turnstile resolvido nesta pagina.
  if (!(await turnstileValido(env, token, DOMINIO, request.headers.get("cf-connecting-ip")))) {
    return pagina("Verificação", { rotulo: "VERIFICAÇÃO", tom: "aviso", h1: "Não deu para confirmar.",
      texto: "<p>A verificação contra robôs não passou ou venceu.</p>", nota: "Nada foi criado.", painel: tentar }, 403);
  }
  const antigo = await kvGet(env, "escritorio:" + pedido.slug);
  if (antigo && pedido.retomar && mesmoDono(antigo, pedido.dono)) {
    // O mesmo dono: o tunel, o DNS e o segredo antigos saem (o nome do tunel
    // e o DNS nao podem existir duas vezes); o PAULUS antigo, se ainda
    // existir, ouve "endereço removido" na proxima conversa.
    await remover(env, antigo, "retomado pela mesma conta Google em outra instalação");
  } else if (antigo) {
    return pagina("Nome em uso", { rotulo: "NOME EM USO", tom: "aviso", h1: "Esse endereço acabou de ser usado.",
      texto: "<p>Outro escritório ficou com ele há pouco. Volte ao PAVLVS do escritório e escolha outro nome.</p>",
      nota: "Nada foi criado.", painel: VOLTE }, 409);
  }
  let criado;
  try {
    criado = await provisionar(env, pedido.slug, pedido, agora);
  } catch (e) {
    return pagina("Não deu certo", { rotulo: "NÃO DEU CERTO", tom: "erro", h1: "Não consegui criar o endereço.",
      texto: "<p>O que tinha sido criado foi desfeito. Tente de novo em alguns minutos.</p>", nota: "Nada ficou pela metade.",
      painel: `<div class="bloco"><span class="etiqueta mono">DETALHE</span><span class="detalhe">${esc(e.message)}</span></div>` + tentar }, 502);
  }
  await env.ESCRITORIOS.delete("reserva:" + pedido.slug);
  await kvPut(env, "pedido:" + hash, { ...pedido, estado: "pronto", entrega: criado.entrega }, PEDIDO_TTL_S);
  return pagina("Conectado", {
    topo: DOMINIO + "/conectar",
    rotulo: "CONECTADO", tom: "ok", h1: "Endereço conectado.",
    texto: "<p>O PAVLVS do escritório já recebeu o endereço e liga o túnel sozinho. A partir de agora, a equipe pode entrar de fora com a própria conta.</p>",
    nota: "Já pode fechar esta página.",
    painel: linhasDoPedido(pedido, criado.entrega.endereco) +
      `<div class="acoes"><a class="principal" href="${esc(criado.entrega.endereco)}">Abrir o endereço${SETA_FORA}</a><span class="dica">ou feche esta página</span></div>`,
  });
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
      dono: pedido.dono || null,
    };
    await kvPut(env, "escritorio:" + slug, registro);
    feito.push(() => env.ESCRITORIOS.delete("escritorio:" + slug));
    await kvPut(env, "segredo:" + registro.hash_segredo, { slug });
    await kvPut(env, "instalacao:" + pedido.instalacao_id, { slug });
    await anotarDono(env, slug, registro.dono);
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
  await esquecerDono(env, registro);
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
