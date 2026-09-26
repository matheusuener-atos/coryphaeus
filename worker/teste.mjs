// Teste do Worker sem rede: node worker/teste.mjs
// O Mercado Pago nao e chamado - so as conferencias que acontecem antes.
import { createHmac } from "node:crypto";
import worker from "./index.js";

const guardados = new Map();
let chamadasNoLimite = 0;
const env = {
  MP_WEBHOOK_SECRET: "segredo-de-teste",
  MP_ACCESS_TOKEN: "sem-token",
  ASSETS: { fetch: async () => new Response("site", { status: 200 }) },
  APOIOS: { get: async (k) => guardados.get(k) || null, put: async (k, v) => { guardados.set(k, v); } },
  LIMITE: { limit: async () => ({ success: ++chamadasNoLimite <= 10 }) },
};

// O Mercado Pago de mentira: a order paga e a assinatura ativa.
globalThis.fetch = async (url) => {
  const u = String(url);
  if (u.includes("/v1/orders/")) return new Response(JSON.stringify({ status: "processed", total_amount: "40.00" }), { status: 200 });
  if (u.includes("/preapproval/")) return new Response(JSON.stringify({ status: "authorized", auto_recurring: { transaction_amount: 40 } }), { status: 200 });
  return new Response("{}", { status: 404 });
};
let falhas = 0;
const checar = (ok, descricao) => { console.log((ok ? "  ok   " : "  FALHA ") + descricao); if (!ok) falhas++; };

function aviso(dataId, segredo, ts = Date.now()) {
  const requestId = "4ed4fa2b-0b31-42ec-a62f-ad793c486c59";
  const manifest = `id:${dataId.toLowerCase()};request-id:${requestId};ts:${ts};`;
  const v1 = createHmac("sha256", segredo).update(manifest).digest("hex");
  return new Request(`https://paulus.ia.br/api/mp/aviso?data.id=${dataId}&type=order`, {
    method: "POST",
    headers: { "x-signature": `ts=${ts},v1=${v1}`, "x-request-id": requestId },
    body: "{}",
  });
}

const r1 = await worker.fetch(aviso("ORD01HRYFWNYRE1MR1E60MW3X0T2P", env.MP_WEBHOOK_SECRET), env);
checar(r1.status === 200, "aviso com a assinatura certa é aceito");
const r2 = await worker.fetch(aviso("123456789", "outro-segredo"), env);
checar(r2.status === 401, "aviso com assinatura errada é recusado");
const r3 = await worker.fetch(aviso("123456789", env.MP_WEBHOOK_SECRET, Date.now() - 60 * 60 * 1000), env);
checar(r3.status === 401, "aviso velho (repetido) é recusado");
const r4 = await worker.fetch(new Request("https://paulus.ia.br/api/mp/aviso", { method: "POST", body: "{}" }), env);
checar(r4.status === 401, "aviso sem assinatura é recusado");

const pix = (corpo) => worker.fetch(new Request("https://paulus.ia.br/api/mp/pix", { method: "POST", body: JSON.stringify(corpo) }), env);
checar((await pix({ valor: 1, email: "a@b.com" })).status === 400, "Pix abaixo do mínimo é recusado antes de chamar o Mercado Pago");
checar((await pix({ valor: 99999, email: "a@b.com" })).status === 400, "Pix acima do máximo é recusado");
checar((await pix({ valor: 40, email: "nao-e-email" })).status === 400, "Pix sem e-mail válido é recusado");

// O aviso aceito busca a situacao no Mercado Pago e guarda no KV.
function avisoDe(tipo, id) {
  const ts = Date.now();
  const requestId = "req-1";
  const v1 = createHmac("sha256", env.MP_WEBHOOK_SECRET).update(`id:${id.toLowerCase()};request-id:${requestId};ts:${ts};`).digest("hex");
  return new Request(`https://paulus.ia.br/api/mp/aviso?data.id=${id}&type=${tipo}`, {
    method: "POST", headers: { "x-signature": `ts=${ts},v1=${v1}`, "x-request-id": requestId }, body: "{}",
  });
}
await worker.fetch(avisoDe("order", "ORD01PAGO"), env);
checar(JSON.parse(guardados.get("pix:ORD01PAGO") || "{}").pago === true, "aviso de Pix pago fica guardado no KV");
await worker.fetch(avisoDe("subscription_preapproval", "PRE0001"), env);
checar(JSON.parse(guardados.get("assinatura:PRE0001") || "{}").situacao === "authorized", "aviso de assinatura ativa fica guardado");
const sit = await (await worker.fetch(new Request("https://paulus.ia.br/api/mp/assinatura/PRE0001"), env)).json();
checar(sit.ativa === true && sit.fonte === "aviso", "a situação da assinatura vem do que o aviso guardou");

// Mudar o valor e interromper so com a chave que a criacao devolveu.
const { createHmac: hmac2 } = await import("node:crypto");
const chaveBoa = hmac2("sha256", env.MP_WEBHOOK_SECRET).update("assinatura:PRE0001").digest("hex");
const postar = (caminho, corpo) => worker.fetch(new Request("https://paulus.ia.br" + caminho, { method: "POST", body: JSON.stringify(corpo) }), env);
const semChave = await postar("/api/mp/assinatura/PRE0001/interromper", { chave: "abc" });
checar(semChave.status === 403, "interromper sem a chave certa é recusado");
const outraChave = await postar("/api/mp/assinatura/PRE0002X/valor", { chave: chaveBoa, valor: 20 });
checar(outraChave.status === 403, "a chave de uma assinatura não serve para outra");
const valorBaixo = await postar("/api/mp/assinatura/PRE0001/valor", { chave: chaveBoa, valor: 2 });
checar(valorBaixo.status === 400, "diminuir abaixo do mínimo é recusado");

// Recuperar: so o Pix do e-mail e da data pedidos.
guardados.set("pix:ORD01ANTIGO", JSON.stringify({ situacao: "processed", pago: true, valor: "5.00", quando: "2026-09-26T07:18:55.610Z" }));
guardados.set("pix:ORD01OUTRADATA", JSON.stringify({ situacao: "processed", pago: true, valor: "9.00", quando: "2026-09-20T15:00:00.000Z" }));
env.APOIOS.list = async ({ prefix }) => ({ keys: [...guardados.keys()].filter((k) => k.startsWith(prefix)).map((name) => ({ name })) });
const fetchAntes = globalThis.fetch;
globalThis.fetch = async (url) => (String(url).includes("/v1/orders/")
  ? new Response(JSON.stringify({ status: "processed", total_amount: "5.00", payer: { email: "apoiador@exemplo.com.br" } }), { status: 200 })
  : fetchAntes(url));
chamadasNoLimite = 0;
const rec = await (await postar("/api/mp/pix/recuperar", { emails: ["Apoiador@Exemplo.com.br"], datas: ["26/09/2026"] })).json();
checar(rec.pix.some((p) => p.id === "ORD01ANTIGO" && p.valor === 5) && !rec.pix.some((p) => p.id === "ORD01OUTRADATA"), "recupera o Pix do e-mail na data certa, e só dela");
const semData = await (await postar("/api/mp/pix/recuperar", { emails: ["apoiador@exemplo.com.br"], datas: [] })).json();
checar(semData.pix.length === 0, "só com o e-mail, sem a data, não devolve nada");
const outroEmail = await (await postar("/api/mp/pix/recuperar", { emails: ["outra@pessoa.com"], datas: ["26/09/2026"] })).json();
checar(outroEmail.pix.length === 0, "e-mail de outra pessoa não vê o Pix");
globalThis.fetch = fetchAntes;

// O limite: a 11a tentativa no minuto e recusada antes de chamar o Mercado Pago.
chamadasNoLimite = 0;
let ultima = null;
for (let i = 0; i < 11; i++) ultima = await pix({ valor: 1, email: "a@b.com" });
checar(ultima.status === 429, "passou do limite de cobranças por minuto, recusa");

const site = await worker.fetch(new Request("https://paulus.ia.br/"), env);
checar(site.status === 200 && (await site.text()) === "site", "o resto continua sendo o site");
checar((await worker.fetch(new Request("https://paulus.ia.br/api/nada"), env)).status === 404, "rota desconhecida dá 404");

console.log(falhas ? `\n  ${falhas} FALHA(S)` : "\n  todos os testes passaram");
process.exit(falhas ? 1 : 0);
