// Teste do Worker sem rede: node worker/teste.mjs
// O Mercado Pago nao e chamado - so as conferencias que acontecem antes.
import { createHmac } from "node:crypto";
import worker from "./index.js";

const guardados = new Map();
const metadados = new Map();
let chamadasNoLimite = 0;
// Os arquivos do site que o Worker le: as versoes e o ITCD registrado.
const arquivos = {
  "/dados/versoes.json": { releases: [{ version: "0.9.3", date: "2026-09-28", changes: ["Extrato novo"] }] },
  "/dados/itcd.json": { "2026-09": 1.5 },
};
const env = {
  MP_WEBHOOK_SECRET: "segredo-de-teste",
  MP_ACCESS_TOKEN: "sem-token",
  ASSETS: {
    fetch: async (req) => {
      const caminho = new URL(req.url || req).pathname;
      if (arquivos[caminho]) return new Response(JSON.stringify(arquivos[caminho]), { status: 200 });
      return new Response("site", { status: 200 });
    },
  },
  APOIOS: {
    get: async (k) => guardados.get(k) || null,
    getWithMetadata: async (k) => ({ value: guardados.get(k) || null, metadata: metadados.get(k) || null }),
    put: async (k, v, opcoes) => { guardados.set(k, v); if (opcoes && opcoes.metadata) metadados.set(k, opcoes.metadata); },
    list: async ({ prefix }) => ({ list_complete: true, keys: [...guardados.keys()].filter((k) => k.startsWith(prefix)).map((name) => ({ name, metadata: metadados.get(name) })) }),
  },
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

// Recuperar: so o Pix com a impressao do e-mail E na data pedida.
const { createHash } = await import("node:crypto");
const impressao = (e) => createHash("sha256").update(e.trim().toLowerCase()).digest("hex");
guardados.set("pix:ORD01ANTIGO", JSON.stringify({ situacao: "processed", pago: true, valor: "5.00", quando: "2026-09-26T07:18:55.610Z", emails: [impressao("apoiador@exemplo.com.br")] }));
guardados.set("pix:ORD01OUTRADATA", JSON.stringify({ situacao: "processed", pago: true, valor: "9.00", quando: "2026-09-20T15:00:00.000Z", emails: [impressao("apoiador@exemplo.com.br")] }));
chamadasNoLimite = 0;
const rec = await (await postar("/api/mp/pix/recuperar", { emails: ["Apoiador@Exemplo.com.br"], datas: ["26/09/2026"] })).json();
checar(rec.pix.some((p) => p.id === "ORD01ANTIGO" && p.valor === 5) && !rec.pix.some((p) => p.id === "ORD01OUTRADATA"), "recupera o Pix do e-mail na data certa, e só dela");
const semData = await (await postar("/api/mp/pix/recuperar", { emails: ["apoiador@exemplo.com.br"], datas: [] })).json();
checar(semData.pix.length === 0, "só com o e-mail, sem a data, não devolve nada");
const outroEmail = await (await postar("/api/mp/pix/recuperar", { emails: ["outra@pessoa.com"], datas: ["26/09/2026"] })).json();
checar(outroEmail.pix.length === 0, "e-mail de outra pessoa não vê o Pix");

// Criar o Pix grava a impressao do e-mail (nunca o e-mail).
const fetchAntes = globalThis.fetch;
globalThis.fetch = async (url) => (String(url).endsWith("/v1/orders")
  ? new Response(JSON.stringify({ id: "ORD01NOVO", status: "action_required", transactions: { payments: [{ payment_method: { qr_code: "x" } }] } }), { status: 200 })
  : fetchAntes(url));
chamadasNoLimite = 0;
await pix({ valor: 10, email: "Novo@Exemplo.com.br" });
const novo = guardados.get("pix:ORD01NOVO") || "";
checar(novo.includes(impressao("novo@exemplo.com.br")) && !novo.includes("Novo@Exemplo"), "o Pix novo guarda a impressão do e-mail, não o e-mail");
globalThis.fetch = fetchAntes;

// O limite: a 11a tentativa no minuto e recusada antes de chamar o Mercado Pago.
chamadasNoLimite = 0;
let ultima = null;
for (let i = 0; i < 11; i++) ultima = await pix({ valor: 1, email: "a@b.com" });
checar(ultima.status === 429, "passou do limite de cobranças por minuto, recusa");

// ------------------------------------------------ o que e publico
console.log("\no que é público");
// O Pix com nome autorizado: pago, conta no mes e entra no mural.
guardados.set("pix:ORD01MURAL", JSON.stringify({ pago: false, valor: "25.00", quando: "2026-09-27T12:00:00.000Z", emails: [impressao("ana@exemplo.com.br")], mural: "Ana Exemplo" }));
await worker.fetch(avisoDe("order", "ORD01MURAL"), env);
checar([...guardados.keys()].some((k) => /^contrib:\d{4}-\d{2}:pix-ORD01MURAL$/.test(k)), "o Pix pago vira uma contribuição do mês");
checar((metadados.get("mural:" + impressao("ana@exemplo.com.br")) || {}).nome === "Ana Exemplo", "o nome autorizado entra no mural");
await worker.fetch(avisoDe("order", "ORD01MURAL"), env);
checar([...guardados.keys()].filter((k) => k.endsWith(":pix-ORD01MURAL")).length === 1, "o mesmo aviso repetido não conta duas vezes");
// Sem nome autorizado, nada no mural.
guardados.set("pix:ORD01ANONIMO", JSON.stringify({ pago: false, valor: "10.00", emails: [impressao("anonimo@exemplo.com.br")], mural: "" }));
await worker.fetch(avisoDe("order", "ORD01ANONIMO"), env);
checar(!metadados.has("mural:" + impressao("anonimo@exemplo.com.br")), "quem não autorizou não aparece no mural");

// Criar com nome: marcacao e endereco nao passam.
const fetchPix = globalThis.fetch;
let corpoMP = null;
globalThis.fetch = async (url, op) => {
  const u = String(url);
  if (u.endsWith("/v1/orders")) return new Response(JSON.stringify({ id: "ORD01NOME", status: "action_required", transactions: { payments: [{ payment_method: {} }] } }), { status: 200 });
  if (u.endsWith("/checkout/preferences")) { corpoMP = JSON.parse(op.body); return new Response(JSON.stringify({ init_point: "https://mp/checkout" }), { status: 200 }); }
  if (u.includes("/v1/payments/")) return new Response(JSON.stringify({ status: "approved", transaction_amount: 30, date_approved: "2026-09-28T10:00:00.000-03:00", external_reference: corpoMP && corpoMP.external_reference }), { status: 200 });
  if (u.includes("/authorized_payments/")) return new Response(JSON.stringify({ id: 777, preapproval_id: "PRE0001", transaction_amount: 40, debit_date: "2026-09-10T10:00:00Z", payment: { status: "approved" } }), { status: 200 });
  return fetchPix(url, op);
};
chamadasNoLimite = 0;
await pix({ valor: 10, email: "b@exemplo.com.br", mural: "<script>x</script> Beto" });
checar(JSON.parse(guardados.get("pix:ORD01NOME")).mural === "scriptx/script Beto", "o nome do mural perde a marcação");
chamadasNoLimite = 0;
await pix({ valor: 10, email: "c@exemplo.com.br", mural: "visite http://golpe.exemplo" });
checar(JSON.parse(guardados.get("pix:ORD01NOME")).mural === "", "nome com endereço de internet não entra");

// Cartao uma vez (Checkout Pro): o link volta, o cartao nunca passa aqui.
chamadasNoLimite = 0;
const cartao = await (await postar("/api/mp/cartao", { valor: 30, email: "carla@exemplo.com.br", mural: "Carla Exemplo" })).json();
checar(cartao.link === "https://mp/checkout" && corpoMP.back_urls.success.startsWith("https://paulus.ia.br/apoiar/"), "o cartão abre o checkout e volta para /apoiar");
checar(corpoMP.items[0].unit_price === 30 && corpoMP.payment_methods.installments === 1, "valor conferido e sem parcelamento");
const refCartao = "cartao:" + corpoMP.external_reference;
checar(!(guardados.get(refCartao) || "").includes("carla@"), "o pedido do cartão guarda a impressão do e-mail, não o e-mail");
await worker.fetch(avisoDe("payment", "9001"), env);
checar([...guardados.keys()].some((k) => k.endsWith(":cartao-9001")), "o pagamento aprovado no cartão conta no mês");
checar((metadados.get("mural:" + impressao("carla@exemplo.com.br")) || {}).nome === "Carla Exemplo", "e o nome autorizado entra no mural");
// A cobranca mensal da assinatura.
await worker.fetch(avisoDe("subscription_authorized_payment", "777"), env);
checar(guardados.has("contrib:2026-09:cobranca-777"), "cada cobrança mensal paga conta no mês dela");
globalThis.fetch = fetchPix;

// As rotas publicas: so consolidado, nada de pessoa.
const dev = await worker.fetch(new Request("https://paulus.ia.br/api/public/desenvolvimento"), env);
const devTexto = await dev.text();
const devDados = JSON.parse(devTexto);
const setembro = devDados.meses.find((m) => m.month === "2026-09") || { contributions: {}, releases: [] };
checar(dev.status === 200 && (dev.headers.get("cache-control") || "").includes("public"), "desenvolvimento responde e pode ficar em cache");
checar(setembro.releases.length === 1 && setembro.releases[0].version === "0.9.3", "as versões vêm do arquivo do site, no mês delas");
checar(setembro.contributions.count >= 4 && setembro.contributions.total >= 5 + 9 + 25 + 40, "o mês soma as contribuições (os Pix antigos entram uma vez)");
checar(setembro.contributions.itcdPaid === 1.5, "o ITCD só aparece registrado");
checar(!/ORD01|@|pix-|cartao-|cobranca-|[0-9a-f]{64}/.test(devTexto), "nenhum id, e-mail ou impressão sai na rota pública");
const apo = await (await worker.fetch(new Request("https://paulus.ia.br/api/public/apoiadores"), env)).text();
const apoDados = JSON.parse(apo);
checar(apoDados.apoiadores.some((a) => a.name === "Ana Exemplo" && /^\d{4}-\d{2}$/.test(a.since)), "o mural lista o nome autorizado com o mês");
checar(apoDados.apoiadores.every((a) => Object.keys(a).join() === "name,since") && !/@|[0-9a-f]{64}/.test(apo), "o mural só tem nome e mês");

const site = await worker.fetch(new Request("https://paulus.ia.br/"), env);
checar(site.status === 200 && (await site.text()) === "site", "o resto continua sendo o site");
checar((await worker.fetch(new Request("https://paulus.ia.br/api/nada"), env)).status === 404, "rota desconhecida dá 404");

console.log(falhas ? `\n  ${falhas} FALHA(S)` : "\n  todos os testes passaram");
process.exit(falhas ? 1 : 0);
