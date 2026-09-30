/* ---------------------------------------------- o motor no aparelho (D2) */
/*
   Web Worker dedicado (docs/PROGRESSO-APARELHO.md, D2). Recebe o pacote de
   escrita, escreve com o modelo deste aparelho, devolve e apaga o que recebeu.

   - O que fica no aparelho: só os pesos do modelo, em partes de ~512 MB (a
     wllama não lê arquivo acima de ~2 GB), no Cache Storage "paulus-modelo",
     sob /api/aparelho/modelo/<sha256>/parte/<n> - o nome guardado é só o
     hash. Antes de usar, o SHA-256 de cada parte é conferido; diferente, a
     parte é apagada e o motor recusa.
   - O que nunca fica: a pergunta, os trechos e a resposta vivem só nas
     variáveis desta execução e são soltos no fim de cada escrita. Nada em
     localStorage, sessionStorage, IndexedDB nem Service Worker.
   - A biblioteca (wllama, versão fixa) vem do próprio PAULUS, /motor/...,
     com o hash conferido pelo servidor. Nenhuma chamada a outra origem: a
     CSP da página só deixa 'self'.
   - `falso` (só os testes): o mesmo caminho, sem a biblioteca - escreve um
     texto fixo, para conferir o que fica guardado sem precisar de WebGPU.
*/

const CACHE = "paulus-modelo";
const BIBLIOTECA = "/motor/wllama-3.6.1/index.js";
const WASM = "/motor/wllama-3.6.1/wllama.wasm";

let motor = null;
let falso = false;
let carregado = "";
let parar = null;
// Só os testes: a velocidade que o motor falso diz ter.
let motorFalsoTps = 42;

function hex(buf) {
  return Array.from(new Uint8Array(buf)).map((b) => b.toString(16).padStart(2, "0")).join("");
}

async function pesos(url, sha, avisar) {
  const cache = await caches.open(CACHE);
  let resp = await cache.match(url);
  if (!resp) {
    avisar({ fase: "baixando" });
    const r = await fetch(url, { credentials: "same-origin" });
    if (!r.ok) throw new Error("não consegui baixar o modelo (" + r.status + ")");
    try {
      await cache.put(url, r.clone());
    } catch (err) {
      // Sem espaço para guardar (a cota do navegador): usa assim mesmo, e
      // baixa de novo na próxima vez.
      avisar({ fase: "sem_espaco" });
    }
    resp = r;
  }
  avisar({ fase: "conferindo" });
  let buf = await resp.arrayBuffer();
  const h = hex(await crypto.subtle.digest("SHA-256", buf));
  if (h !== sha) {
    buf = null;
    await cache.delete(url);
    throw new Error("hash do modelo não confere: apaguei e recusei");
  }
  // Guardada no Cache Storage, a parte vem de lá (o navegador a lê do disco);
  // sem cache, dos bytes baixados. A cópia em memória sai já: somando as
  // partes do 3B (2 GB), manter tudo em memória estourava a leitura.
  buf = null;
  const guardada = await cache.match(url);
  if (guardada) return await guardada.blob();
  return await resp.blob();
}

async function carregar(m, avisar) {
  falso = Boolean(m.falso);
  if (typeof m.falsoTps === "number") motorFalsoTps = m.falsoTps;
  const inicio = Date.now();
  const blobs = [];
  for (const [i, parte] of (m.partes || []).entries()) {
    blobs.push(await pesos(parte.url, parte.sha256, (a) => avisar(Object.assign({ parte: i + 1, partes: m.partes.length }, a))));
  }
  if (!blobs.length) throw new Error("o modelo veio sem partes");
  if (falso) {
    motor = { falso: true };
  } else {
    avisar({ fase: "carregando" });
    const { Wllama } = await import(BIBLIOTECA);
    motor = new Wllama({ default: WASM }, { suppressNativeLog: true });
    // As partes na ordem (modelo-00001-of-0000N primeiro): a wllama junta.
    await motor.loadModel(blobs, { n_ctx: m.n_ctx || 4096, n_gpu_layers: m.webgpu === false ? 0 : 999 });
  }
  carregado = m.sha256;
  return { carregado: true, segundos: Math.round((Date.now() - inicio) / 100) / 10 };
}

async function escrever(m, avisar) {
  if (!motor) throw new Error("o modelo não está carregado");
  let mensagens = m.mensagens || [];
  const p = m.parametros || {};
  let texto = "";
  parar = new AbortController();
  try {
    if (motor.falso) {
      for (const pedaco of ["Texto ", "escrito ", "pelo ", "motor ", "falso."]) {
        if (parar.signal.aborted) break;
        texto += pedaco;
        avisar({ fase: "escrevendo", texto: texto });
      }
    } else {
      await motor.createChatCompletion({
        messages: mensagens, stream: true, abortSignal: parar.signal,
        temperature: typeof p.temperature === "number" ? p.temperature : 0.2,
        max_tokens: p.num_predict || 700,
        onData: (chunk) => {
          const d = ((chunk.choices || [])[0] || {}).delta || {};
          if (d.content) { texto += d.content; avisar({ fase: "escrevendo", texto: texto }); }
        },
      });
    }
    return { texto: texto };
  } finally {
    // Solta o que recebeu: a pergunta, os trechos e a resposta não ficam.
    mensagens = null;
    m.mensagens = null;
    texto = "";
    parar = null;
  }
}

/* A velocidade num texto de exemplo, sem nada do escritório: quanto o
   aparelho lê (até a primeira palavra) e quanto escreve (depois dela). */
const EXEMPLO = "O contrato de locação é o acordo pelo qual uma pessoa cede a outra o uso de um imóvel " +
  "por tempo determinado ou não, mediante pagamento de aluguel. As partes combinam o valor, o prazo, " +
  "a forma de reajuste, as garantias e quem paga as despesas do imóvel. ";

async function medir() {
  if (!motor) throw new Error("o modelo não está carregado");
  if (motor.falso) return { tokens_por_segundo: motorFalsoTps, leitura_tps: motorFalsoTps * 10 };
  const pergunta = EXEMPLO.repeat(8) + "\nResuma o texto acima em duas frases.";
  let lidos = 0;
  try { lidos = (await motor.tokenize(pergunta)).length; } catch (err) { lidos = Math.round(pergunta.length / 4); }
  const inicio = performance.now();
  let primeira = 0, n = 0;
  await motor.createChatCompletion({
    messages: [{ role: "user", content: pergunta }],
    stream: true, max_tokens: 48, temperature: 0,
    onData: (chunk) => {
      if ((((chunk.choices || [])[0] || {}).delta || {}).content) { if (!primeira) primeira = performance.now(); n += 1; }
    },
  });
  const fim = performance.now();
  const lendo = ((primeira || fim) - inicio) / 1000, escrevendo = (fim - (primeira || fim)) / 1000;
  return {
    tokens_por_segundo: escrevendo > 0 && n > 1 ? Math.round(((n - 1) / escrevendo) * 10) / 10 : 0,
    leitura_tps: lendo > 0 ? Math.round((lidos / lendo) * 10) / 10 : 0,
  };
}

async function apagar() {
  try { if (motor && !motor.falso) await motor.exit(); } catch (err) { /* já saiu */ }
  motor = null;
  carregado = "";
  await caches.delete(CACHE);
  return { apagado: true };
}

self.onmessage = async (e) => {
  const m = e.data || {};
  const avisar = (dados) => self.postMessage(Object.assign({ id: m.id, tipo: "andamento" }, dados));
  try {
    let r;
    if (m.tipo === "carregar") r = await carregar(m, avisar);
    else if (m.tipo === "escrever") r = await escrever(m, avisar);
    else if (m.tipo === "medir") r = await medir();
    else if (m.tipo === "parar") { if (parar) parar.abort(); r = { parado: true }; }
    else if (m.tipo === "apagar") r = await apagar();
    else throw new Error("pedido desconhecido");
    self.postMessage(Object.assign({ id: m.id, tipo: "pronto" }, r));
  } catch (err) {
    self.postMessage({ id: m.id, tipo: "erro", mensagem: String((err && err.message) || err) });
  }
};
