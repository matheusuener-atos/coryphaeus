// Teste do Worker sem rede: node worker/teste.mjs
// O Mercado Pago nao e chamado - so as conferencias que acontecem antes.
import { createHmac } from "node:crypto";
import worker from "./index.js";

const env = {
  MP_WEBHOOK_SECRET: "segredo-de-teste",
  MP_ACCESS_TOKEN: "sem-token",
  ASSETS: { fetch: async () => new Response("site", { status: 200 }) },
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

const site = await worker.fetch(new Request("https://paulus.ia.br/"), env);
checar(site.status === 200 && (await site.text()) === "site", "o resto continua sendo o site");
checar((await worker.fetch(new Request("https://paulus.ia.br/api/nada"), env)).status === 404, "rota desconhecida dá 404");

console.log(falhas ? `\n  ${falhas} FALHA(S)` : "\n  todos os testes passaram");
process.exit(falhas ? 1 : 0);
