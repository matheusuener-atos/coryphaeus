// Teste do Worker sem rede: node worker/teste.mjs
// O Mercado Pago nao e chamado - so as conferencias que acontecem antes.
import { createHmac } from "node:crypto";
import worker from "./index.js";

const guardados = new Map();
let chamadasNoLimite = 0;
// Nenhum arquivo do site e lido pelo Worker nestes testes.
const arquivos = {};
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
  // O KV da calibracao (o binding ainda se chama APOIOS).
  APOIOS: {
    get: async (k) => guardados.get(k) || null,
    put: async (k, v) => { guardados.set(k, v); },
  },
  LIMITE: { limit: async () => ({ success: ++chamadasNoLimite <= 10 }) },
};

// O Mercado Pago de mentira: a order paga.
globalThis.fetch = async (url) => {
  const u = String(url);
  if (u.includes("/v1/orders/")) return new Response(JSON.stringify({ status: "processed", total_amount: "40.00" }), { status: 200 });
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

// A cobranca e da Atos: o webhook do Mercado Pago de antes so e respondido (200, para ele nao repetir), e nada muda.
const r1 = await worker.fetch(aviso("ORD01HRYFWNYRE1MR1E60MW3X0T2P", env.MP_WEBHOOK_SECRET), env);
checar(r1.status === 200 && (await r1.json()).ignorado, "o aviso do Mercado Pago de antes é respondido e ignorado");
const r4 = await worker.fetch(new Request("https://paulus.ia.br/api/mp/aviso", { method: "POST", body: "{}" }), env);
checar(r4.status === 200, "até sem assinatura: não há o que aplicar");
checar(guardados.size === 0, "e nada é gravado");

// O antigo "Apoiar o projeto" saiu: as rotas dele nao existem mais.
const postar = (caminho, corpo) => worker.fetch(new Request("https://paulus.ia.br" + caminho, { method: "POST", body: JSON.stringify(corpo) }), env);
const antigas = [
  await postar("/api/mp/pix", { valor: 10, email: "a@b.com" }),
  await worker.fetch(new Request("https://paulus.ia.br/api/mp/pix/ORD01PAGO"), env),
  await postar("/api/mp/pix/recuperar", { emails: ["a@b.com"], datas: ["26/09/2026"] }),
  await postar("/api/mp/cartao", { valor: 10, email: "a@b.com" }),
  await postar("/api/mp/assinatura", { valor: 10, email: "a@b.com" }),
  await worker.fetch(new Request("https://paulus.ia.br/api/mp/assinatura/PRE0001"), env),
  await postar("/api/mp/assinatura/PRE0001/interromper", { chave: "abc" }),
  await worker.fetch(new Request("https://paulus.ia.br/api/public/apoiadores"), env),
];
checar(antigas.every((r) => r.status === 404), "as rotas do apoio (Pix, cartão, assinatura, mural) dão 404");

// ------------------------------------------------ o que saiu
console.log("\no que saiu do site");
const dev = await worker.fetch(new Request("https://paulus.ia.br/api/public/desenvolvimento"), env);
checar(dev.status === 404, "a página Desenvolvimento saiu: /api/public/desenvolvimento dá 404");

// ------------------------------------------------ calibracao
console.log("\ncalibração");
const amostra = {
  maquina: { id: "abc123", versao: 1, processador: "Intel Core i5", nucleos: 8, ram_total_gb: 16, avx2: true, banda_gbs: 20, gflops: 100 },
  modelo: "llama3.2:3b", tamanho_gb: 2, parametros_b: 3, quantizacao: "Q4_K_M", escrita_tps: 8, leitura_tps: 60,
};
chamadasNoLimite = 0;
const cal = await postar("/api/calibracao", { amostras: [amostra, { maquina: { id: "x" } }] });
const calDados = await cal.json();
checar(cal.status === 200 && calDados.recebidas === 1 && calDados.total === 1, "a calibração guarda só a amostra válida");
await postar("/api/calibracao", { amostras: [{ ...amostra, escrita_tps: 9 }] });
const todas = await (await worker.fetch(new Request("https://paulus.ia.br/api/calibracao"), env)).json();
checar(todas.amostras.length === 1 && todas.amostras[0].escrita_tps === 9, "medir de novo troca a amostra antiga da mesma máquina e modelo");
checar((await postar("/api/calibracao", { amostras: [] })).status === 400, "sem amostra válida, recusa");
chamadasNoLimite = 10;
checar((await postar("/api/calibracao", { amostras: [amostra] })).status === 429, "passou do limite por minuto, recusa");

const site = await worker.fetch(new Request("https://paulus.ia.br/"), env);
checar(site.status === 200 && (await site.text()) === "site", "o resto continua sendo o site");
checar((await worker.fetch(new Request("https://paulus.ia.br/api/nada"), env)).status === 404, "rota desconhecida dá 404");
checar((await worker.fetch(new Request("https://paulus.ia.br/api/tunel/iniciar", { method: "POST", body: "{}" }), env)).status === 404,
  "sem TUNEL_ATIVO, o acesso de fora não existe no ar");

// O acesso de fora tem o proprio teste, com a API da Cloudflare de mentira.
console.log("\n--- acesso de fora (worker/tunel.js)");
falhas += (await import("./teste-tunel.mjs")).default;

console.log(falhas ? `\n  ${falhas} FALHA(S)` : "\n  todos os testes passaram");
process.exit(falhas ? 1 : 0);
