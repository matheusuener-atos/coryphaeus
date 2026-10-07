// Testes da conta PAVLVS por e-mail e senha (worker/identidade.js) e do
// donoDoToken (worker/tunel.js) com o token proprio.
//   node worker/teste-identidade.mjs
import { atenderIdentidade, emitirToken } from "./identidade.js";
import { donoDoToken } from "./tunel.js";

let falhas = 0;
function checar(cond, texto, extra) {
  console.log((cond ? "  ok   " : "  FALHA ") + texto + (cond || extra === undefined ? "" : " -> " + JSON.stringify(extra)));
  if (!cond) falhas++;
}

const guardados = new Map();
const APOIOS = {
  async get(k, tipo) { const v = guardados.get(k); return v === undefined ? null : tipo === "json" ? JSON.parse(v) : v; },
  async put(k, v) { guardados.set(k, v); },
  async delete(k) { guardados.delete(k); },
};
const env = { APOIOS, ID_SEGREDO: "segredo-de-teste-0123456789", GOOGLE_CLIENT_IDS: "cliente" };
const emails = [];
const deps = { enviarEmail: async (_env, m) => { emails.push(m); return { ok: true }; }, dentroDoLimite: async () => true };
async function pedir(rota, corpo, { envUsado = env, origem } = {}) {
  const headers = { "content-type": "application/json" };
  if (origem) headers.origin = origem;
  const req = new Request("https://paulus.ia.br/api/id/" + rota, { method: "POST", headers, body: JSON.stringify(corpo) });
  const r = await atenderIdentidade(req, envUsado, new URL(req.url), deps);
  return { status: r.status, d: await r.json() };
}
const codigoDe = (m) => (m.texto.match(/\b(\d{6})\b/) || [])[1];

console.log("criar a conta");
let r = await pedir("cadastrar", { email: "Ana@Escritorio.adv.br", senha: "curta1" });
checar(r.status === 400 && r.d.erro.includes("10 caracteres"), "senha curta: recusada", r.d);
r = await pedir("cadastrar", { email: "ana@escritorio.adv.br", senha: "somenteletrasaqui" });
checar(r.status === 400 && r.d.erro.includes("letras e números"), "senha sem número: recusada", r.d);
r = await pedir("cadastrar", { email: "não é e-mail", senha: "senhaforte123" });
checar(r.status === 400, "e-mail inválido: recusado");
r = await pedir("cadastrar", { email: "Ana@Escritorio.adv.br", senha: "senhaforte123", nome: "Ana <b>Lima</b>" });
const cod1 = codigoDe(emails[0]);
checar(r.status === 200 && r.d.enviado && emails[0].para === "ana@escritorio.adv.br" && cod1 && !guardados.has("id:conta:ana@escritorio.adv.br"),
  "cadastrar manda o código ao e-mail (minúsculo) e ainda não cria a conta", r.d);
checar(!String(guardados.get("id:pend:ana@escritorio.adv.br")).includes("senhaforte123") && !String(guardados.get("id:pend:ana@escritorio.adv.br")).includes(cod1),
  "nem a senha nem o código ficam guardados em claro");
r = await pedir("confirmar", { email: "ana@escritorio.adv.br", codigo: "000000" === cod1 ? "111111" : "000000" });
checar(r.status === 400 && r.d.erro.includes("não confere"), "código errado: recusado");
r = await pedir("confirmar", { email: "ana@escritorio.adv.br", codigo: cod1 });
checar(r.status === 200 && r.d.token && r.d.email === "ana@escritorio.adv.br" && guardados.has("id:conta:ana@escritorio.adv.br") && !guardados.has("id:pend:ana@escritorio.adv.br"),
  "código certo: cria a conta e já devolve o token", r.d);
let dono = await donoDoToken(env, r.d.token);
const subAna = JSON.parse(guardados.get("id:conta:ana@escritorio.adv.br")).sub;
checar(dono && dono.sub === subAna && /^pv-[0-9a-f]{24}$/.test(subAna) && dono.email === "ana@escritorio.adv.br", "o donoDoToken aceita o token próprio: {sub, email}", dono);
checar(JSON.parse(guardados.get("id:conta:ana@escritorio.adv.br")).nome === "Ana bLima/b", "o nome fica sem marcação");

console.log("entrar");
r = await pedir("entrar", { email: "ana@escritorio.adv.br", senha: "errada12345" });
checar(r.status === 401 && r.d.erro === "e-mail ou senha não conferem", "senha errada: 401");
r = await pedir("entrar", { email: "ninguem@escritorio.adv.br", senha: "errada12345" });
checar(r.status === 401 && r.d.erro === "e-mail ou senha não conferem", "e-mail sem conta: a mesma resposta");
r = await pedir("entrar", { email: " ANA@escritorio.adv.br ", senha: "senhaforte123" });
checar(r.status === 200 && r.d.token && !guardados.has("id:erros:ana@escritorio.adv.br"), "senha certa: token (e zera os erros)", r.d);
emails.length = 0;
r = await pedir("cadastrar", { email: "ana@escritorio.adv.br", senha: "outrasenha123" });
checar(r.status === 200 && r.d.enviado && emails[0].assunto.includes("já tem conta") && !codigoDe(emails[0]),
  "cadastrar um e-mail que já tem conta: a mesma resposta, e o e-mail avisa (sem código)", emails[0]);
for (let i = 0; i < 8; i++) await pedir("entrar", { email: "ana@escritorio.adv.br", senha: "errada12345" });
r = await pedir("entrar", { email: "ana@escritorio.adv.br", senha: "senhaforte123" });
checar(r.status === 429 && r.d.erro.includes("15 minutos"), "8 erros: espera, mesmo com a senha certa", r.d);
guardados.delete("id:erros:ana@escritorio.adv.br");

console.log("esqueci a senha");
emails.length = 0;
r = await pedir("esqueci", { email: "ninguem@escritorio.adv.br" });
checar(r.status === 200 && r.d.enviado && emails.length === 0, "e-mail sem conta: a mesma resposta, e nenhum e-mail sai");
r = await pedir("esqueci", { email: "ana@escritorio.adv.br" });
const cod2 = codigoDe(emails[0]);
checar(r.status === 200 && cod2 && emails[0].titulo === "Trocar a senha", "com conta: o código para trocar a senha", emails[0]);
r = await pedir("redefinir", { email: "ana@escritorio.adv.br", codigo: cod2, senha: "fraca" });
checar(r.status === 400, "senha nova fraca: recusada");
r = await pedir("redefinir", { email: "ana@escritorio.adv.br", codigo: cod2, senha: "novasenha2026" });
checar(r.status === 200 && r.d.token && JSON.parse(guardados.get("id:conta:ana@escritorio.adv.br")).sub === subAna, "código certo: troca a senha, o mesmo sub", r.d);
r = await pedir("entrar", { email: "ana@escritorio.adv.br", senha: "senhaforte123" });
checar(r.status === 401, "a senha antiga não vale mais");
r = await pedir("entrar", { email: "ana@escritorio.adv.br", senha: "novasenha2026" });
checar(r.status === 200, "a nova vale");
r = await pedir("redefinir", { email: "ana@escritorio.adv.br", codigo: cod2, senha: "outra2026senha" });
checar(r.status === 400 && r.d.erro.includes("venceu"), "o código só vale uma vez");

console.log("a mesma conta do Google");
guardados.set("id:google:bruno@gmail.com", JSON.stringify({ sub: "109876543210" }));
emails.length = 0;
await pedir("cadastrar", { email: "bruno@gmail.com", senha: "senhadobruno1" });
r = await pedir("confirmar", { email: "bruno@gmail.com", codigo: codigoDe(emails[0]) });
dono = await donoDoToken(env, r.d.token);
checar(dono && dono.sub === "109876543210", "quem já entrou com o Google: a conta por senha é a mesma conta da nuvem (o mesmo sub)", dono);
emails.length = 0;
guardados.set("id:google:carla@gmail.com", JSON.stringify({ sub: "555" }));
r = await pedir("esqueci", { email: "carla@gmail.com" });
checar(emails.length === 1 && emails[0].titulo === "Criar uma senha", "só Google: \"esqueci a senha\" cria uma senha para a mesma conta", emails[0]);
r = await pedir("redefinir", { email: "carla@gmail.com", codigo: codigoDe(emails[0]), senha: "senhadacarla1" });
checar(r.status === 200 && (await donoDoToken(env, r.d.token)).sub === "555", "e a senha nova cai no sub do Google");

console.log("o token");
const vencido = await emitirToken(env, { sub: "pv-1", email: "x@y.com" }, Date.now() - 2 * 3600e3);
checar((await donoDoToken(env, vencido)) === null, "token vencido: recusado");
const outro = await emitirToken({ ID_SEGREDO: "outro-segredo" }, { sub: "pv-1", email: "x@y.com" });
checar((await donoDoToken(env, outro)) === null, "token assinado com outra chave: recusado");
const [a, b, c] = (await emitirToken(env, { sub: "pv-1", email: "x@y.com" })).split(".");
const mexido = a + "." + Buffer.from(JSON.stringify({ iss: "https://paulus.ia.br", aud: "paulus", sub: "109876543210", email: "bruno@gmail.com", exp: 9e9 })).toString("base64url") + "." + c;
checar((await donoDoToken(env, mexido)) === null, "token com o corpo trocado: recusado");
checar((await donoDoToken({ ...env, ID_SEGREDO: "" }, r.d.token)) === null, "sem ID_SEGREDO, nenhum token próprio vale");

console.log("as portas");
r = await pedir("entrar", { email: "ana@escritorio.adv.br", senha: "novasenha2026" }, { envUsado: { APOIOS } });
checar(r.status === 503, "sem ID_SEGREDO: desligado (503)");
r = await pedir("entrar", { email: "ana@escritorio.adv.br", senha: "novasenha2026" }, { origem: "https://golpe.example" });
checar(r.status === 403, "de outra origem: recusado");

console.log(falhas ? "\n  identidade: " + falhas + " falha(s)" : "\n  identidade: todos os testes passaram");
process.exit(falhas ? 1 : 0);
