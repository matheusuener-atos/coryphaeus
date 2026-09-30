/* --------------------------------------------- o motor no aparelho (D2) */
/*
   O lado da página do motor que escreve no aparelho (docs/PROGRESSO-APARELHO.md).
   O motor mora num Web Worker dedicado (/motor/trabalhador.js): esta parte só
   conversa com ele. A tela do switch é da D4; aqui ficam o teste de
   capacidade, carregar o modelo, escrever um pacote e apagar o modelo.

   O teste de capacidade manda ao servidor só números (WebGPU sim/não,
   memória, tokens por segundo num texto de exemplo).
*/

const motorAparelho = { trabalhador: null, pedidos: {}, contador: 0, carregado: "", falso: false, falsoTps: 42 };

function trabalhadorDoAparelho() {
  if (!motorAparelho.trabalhador) {
    motorAparelho.trabalhador = new Worker("/motor/trabalhador.js", { type: "module" });
    motorAparelho.trabalhador.onmessage = (e) => {
      const d = e.data || {};
      const p = motorAparelho.pedidos[d.id];
      if (!p) return;
      if (d.tipo === "andamento") { if (p.andamento) p.andamento(d); return; }
      delete motorAparelho.pedidos[d.id];
      if (d.tipo === "erro") p.falhou(new Error(d.mensagem));
      else p.feito(d);
    };
  }
  return motorAparelho.trabalhador;
}

function pedirAoMotor(tipo, dados, andamento) {
  const id = ++motorAparelho.contador;
  return new Promise((feito, falhou) => {
    motorAparelho.pedidos[id] = { feito: feito, falhou: falhou, andamento: andamento };
    trabalhadorDoAparelho().postMessage(Object.assign({ id: id, tipo: tipo }, dados || {}));
  });
}

/* O que o aparelho tem, antes de baixar qualquer coisa. `bytes`: o tamanho do
   modelo escolhido pelo escritório (sem ele, o do 3B). */
async function capacidadeDoAparelho(bytes) {
  let webgpu = false;
  try {
    const adaptador = navigator.gpu ? await navigator.gpu.requestAdapter() : null;
    webgpu = Boolean(adaptador);
  } catch (err) { webgpu = false; }
  const memoria = typeof navigator.deviceMemory === "number" ? navigator.deviceMemory : null;
  // A memória pedida cresce com o modelo: o dobro dos pesos, pelo menos 4 GB
  // (o navegador não diz mais que 8).
  const gb = (bytes || 2.1 * 1024 ** 3) / 1024 ** 3;
  const precisa = Math.min(8, Math.max(4, Math.ceil(gb * 2)));
  const passa = webgpu && (memoria === null || memoria >= precisa);
  const motivo = !webgpu ? "este navegador não tem WebGPU (o Edge e o Chrome de computador têm)"
    : (!passa ? "o aparelho tem pouca memória para o modelo" : "");
  return { webgpu: webgpu, memoria_gb: memoria, passa: passa, motivo: motivo };
}

async function carregarModeloNoAparelho(andamento) {
  const r = await fetch("/api/aparelho/modelo");
  if (!r.ok) throw new Error(await erroDe(r));
  const m = await r.json();
  if (!m.disponivel) throw new Error(m.motivo);
  const cap = await capacidadeDoAparelho(m.bytes);
  const feito = await pedirAoMotor("carregar", { partes: m.partes, sha256: m.sha256, falso: motorAparelho.falso, falsoTps: motorAparelho.falsoTps, webgpu: cap.webgpu }, andamento);
  motorAparelho.carregado = m.sha256;
  motorAparelho.modelo = m.nome;
  return Object.assign({ modelo: m.nome, bytes: m.bytes }, feito);
}

/* O teste de capacidade inteiro: carrega, mede num texto de exemplo e manda
   ao servidor só os números. */
async function testarCapacidadeDoAparelho(andamento) {
  let bytes = 0;
  try { const e = await (await fetch("/api/aparelho/estado")).json(); bytes = e.bytes || 0; } catch (err) { /* sem o tamanho, o do 3B */ }
  const cap = await capacidadeDoAparelho(bytes);
  let medida = {}, carregou = null;
  if (cap.passa || motorAparelho.falso) {
    const c = await carregarModeloNoAparelho(andamento);
    carregou = c.segundos;
    medida = await pedirAoMotor("medir", {});
  }
  const numeros = { webgpu: cap.webgpu, memoria_gb: cap.memoria_gb, tokens_por_segundo: medida.tokens_por_segundo || null,
    leitura_tps: medida.leitura_tps || null, carregou_s: carregou };
  await fetch("/api/aparelho/capacidade", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(numeros) });
  return Object.assign({ passa: cap.passa, motivo: cap.motivo }, numeros);
}

/* Escreve um pacote (D1) neste aparelho. `andamento` recebe o texto parcial. */
async function escreverNoAparelho(mensagens, parametros, andamento) {
  if (!motorAparelho.carregado) await carregarModeloNoAparelho();
  const r = await pedirAoMotor("escrever", { mensagens: mensagens, parametros: parametros || {} }, andamento);
  return r.texto || "";
}

function pararNoAparelho() {
  if (motorAparelho.trabalhador) motorAparelho.trabalhador.postMessage({ id: 0, tipo: "parar" });
}

async function apagarModeloDoAparelho() {
  const r = await pedirAoMotor("apagar", {});
  motorAparelho.carregado = "";
  return r;
}
