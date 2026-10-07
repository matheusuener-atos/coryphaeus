// Teste da rota do Google do escritorio (POST /api/ia/google, worker/ia.js),
// sem rede:
//   node worker/teste-google.mjs
// O PAULUS instalado conta que servicos do Google usa e confirma a ordem da
// Minha conta ou do painel que cumpriu. O Durable Object roda aqui, com a
// mesma classe, sobre um Map; o Google do login e de mentira.
import worker from "./index.js";
import { ContaIA, ESCOPOS_GOOGLE, atenderIA, medidor } from "./ia.js";

let falhas = 0;
const checar = (ok, descricao, detalhe) => {
  console.log((ok ? "  ok   " : "  FALHA ") + descricao + (ok || detalhe === undefined ? "" : " -> " + JSON.stringify(detalhe)));
  if (!ok) falhas++;
};

// ------------------------------------------------ o Durable Object aqui
let relogio = Date.parse("2026-10-07T12:00:00Z");
const objetos = new Map();
function objeto(nome) {
  if (!objetos.has(nome)) {
    const dados = new Map();
    const o = new ContaIA({ storage: { get: async (k) => structuredClone(dados.get(k)), put: async (k, v) => { dados.set(k, structuredClone(v)); } } }, {});
    o.agora = () => relogio;
    objetos.set(nome, { o, dados });
  }
  return objetos.get(nome);
}
const CONTAS_IA = { idFromName: (n) => n, get: (n) => ({ fetch: (url, init) => objeto(n).o.fetch(new Request(url, init)) }) };
const guardados = new Map();
const env = {
  IA_ATIVA: "1",
  CONTAS_IA,
  ASSETS: { fetch: async () => new Response("site", { status: 200 }) },
  APOIOS: {
    get: async (k) => guardados.get(k) || null,
    getWithMetadata: async (k) => ({ value: guardados.get(k) || null, metadata: null }),
    put: async (k, v) => { guardados.set(k, v); },
    list: async ({ prefix }) => ({ list_complete: true, keys: [...guardados.keys()].filter((k) => k.startsWith(prefix)).map((name) => ({ name })) }),
  },
};
globalThis.fetch = async () => new Response("{}", { status: 404 });
const donos = { "token-do-dono": { sub: "1234567890", email: "dono@escritorio.com.br" } };
const deps = { donoDoToken: async (e, t) => donos[t] || null };
const ctx = { waitUntil: () => null };

async function ia(metodo, caminho, corpo, segredo) {
  const headers = { "content-type": "application/json" };
  if (segredo) headers.authorization = "Bearer " + segredo;
  const req = new Request("https://paulus.ia.br" + caminho, { method: metodo, headers, body: corpo ? JSON.stringify(corpo) : undefined });
  const r = await atenderIA(req, env, new URL(req.url), ctx, deps);
  let d = null;
  try { d = await r.json(); } catch { d = null; }
  return { status: r.status, d };
}
const relatar = (corpo, segredo) => ia("POST", "/api/ia/google", corpo, segredo);

// ------------------------------------------------ a conta
const ativada = await ia("POST", "/api/ia/ativar", { id_token: "token-do-dono", instalacao_id: "inst-0001-abcd" });
const segredo = ativada.d.segredo;
const id = ativada.d.conta.conta;
const conta = medidor(env, id);
checar(ativada.status === 200 && /^pia_/.test(segredo), "a conta da nuvem ativada, com o segredo da instalação");

console.log("\nsem o segredo");
{
  checar((await relatar({ escopos: ["mail.google.com"] })).status === 401, "sem o segredo: 401");
  checar((await relatar({ escopos: ["mail.google.com"] }, "pia_" + "0".repeat(24) + "_" + "1".repeat(64))).status === 401, "segredo inventado: 401");
  const w = await worker.fetch(new Request("https://paulus.ia.br/api/ia/google", { method: "POST", body: "{}" }), env, ctx);
  checar(w.status === 401, "pelo Worker inteiro a rota é da nuvem (ia.js), e sem o segredo dá 401");
  checar(!(await conta.pedir("minha_conta")).google, "e nada foi gravado");
}

console.log("\nrelatar grava");
{
  const r = await relatar({ escopos: ["calendar.events", "mail.google.com", "mail.google.com", "https://www.googleapis.com/auth/drive", "dono@escritorio.com.br", 7] }, segredo);
  checar(r.status === 200 && r.d.ok === true && r.d.pendente === null, "200, sem ordem pendente", r.d);
  const g = (await conta.pedir("minha_conta")).google;
  checar(g && JSON.stringify(g.escopos) === JSON.stringify(["calendar.events", "mail.google.com"]) && g.conferido === new Date(relogio).toISOString(),
    "grava só os nomes curtos dos quatro serviços, sem repetir, e quando conferiu", g);
  checar(ESCOPOS_GOOGLE.length === 4 && ESCOPOS_GOOGLE.includes("drive.readonly"), "os quatro: Gmail, Agenda, Drive enviar e Drive ler");
  relogio += 60000;
  await relatar({ escopos: [] }, segredo);
  checar((await conta.pedir("minha_conta")).google === null, "sem nenhum serviço (sem conta Google no PAULUS): a Minha conta fica sem o que mostrar");
  checar((await ia("GET", "/api/ia/google", null, segredo)).status === 404, "só POST");
}

console.log("\na ordem pendente volta");
let ordemA;
{
  await relatar({ escopos: ["mail.google.com", "calendar.events", "drive.file"] }, segredo);
  relogio += 1000;
  await conta.pedir("google_ordem", { ligados: ["mail.google.com"] });
  const r = await relatar({ escopos: ["mail.google.com", "calendar.events", "drive.file"] }, segredo);
  ordemA = r.d.pendente;
  checar(r.status === 200 && ordemA && ordemA.id === "g" + relogio && JSON.stringify(ordemA.ligados) === '["mail.google.com"]'
    && ordemA.por === "Minha conta" && ordemA.quando === new Date(relogio).toISOString(),
    "a ordem da Minha conta volta com o id, os serviços que ficam, quando e por quem", r.d);
  const r2 = await relatar({ escopos: ["mail.google.com", "calendar.events", "drive.file"], aplicado: "g123" }, segredo);
  checar(r2.d.pendente && r2.d.pendente.id === ordemA.id, "aplicado com outro id não apaga a ordem", r2.d);
  const r3 = await relatar({ escopos: ["mail.google.com"], aplicado: "<script>" }, segredo);
  checar(r3.d.pendente && r3.d.pendente.id === ordemA.id, "aplicado que não parece id é ignorado", r3.d);
}

console.log("\naplicado apaga só a ordem com o mesmo id");
{
  relogio += 1000;
  const r = await relatar({ escopos: ["mail.google.com"], aplicado: ordemA.id }, segredo);
  checar(r.status === 200 && r.d.pendente === null, "o id da ordem cumprida: ela sai", r.d);
  const mc = await conta.pedir("minha_conta");
  checar(!mc.google_pendente && JSON.stringify(mc.google.escopos) === '["mail.google.com"]', "e a Minha conta passa a mostrar o que o PAULUS usa", mc.google);
  // Uma ordem nova enquanto o PAULUS cumpria a anterior: a nova continua esperando.
  relogio += 1000;
  await conta.pedir("google_ordem", { ligados: ["mail.google.com", "calendar.events"] });
  const b = (await relatar({ escopos: ["mail.google.com"] }, segredo)).d.pendente;
  relogio += 1000;
  await conta.pedir("google_ordem", { ligados: [] });
  const c = await relatar({ escopos: ["mail.google.com", "calendar.events"], aplicado: b.id }, segredo);
  checar(c.d.pendente && c.d.pendente.id !== b.id && c.d.pendente.ligados.length === 0,
    "a ordem dada depois (desvincular) não sai com o aplicado da anterior", c.d);
  const fim = await relatar({ escopos: [], aplicado: c.d.pendente.id }, segredo);
  checar(fim.d.pendente === null && (await conta.pedir("minha_conta")).google === null, "cumprida a de desvincular, nada fica pendente nem ligado", fim.d);
}

console.log("\na ordem do painel");
{
  relogio += 1000;
  await conta.pedir("admin_google", { ligados: ["drive.readonly"] });
  const r = await relatar({ escopos: [] }, segredo);
  checar(r.d.pendente && r.d.pendente.por === "painel" && r.d.pendente.ligados[0] === "drive.readonly", "a do painel diz que veio do painel", r.d);
  await relatar({ escopos: [], aplicado: r.d.pendente.id }, segredo);
  checar(!(await conta.pedir("admin_detalhe")).google_pendente, "e sai do painel quando o PAULUS cumpre");
}

console.log(falhas ? "\n  Google do escritório: " + falhas + " falha(s)" : "\n  Google do escritório: todos os testes passaram");
process.exit(falhas ? 1 : 0);
