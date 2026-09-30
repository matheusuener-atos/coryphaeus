/* --------------------------------------------- o motor no aparelho (D2) */
/*
   O lado da página do motor que escreve no aparelho (docs/PROGRESSO-APARELHO.md).
   O motor mora num Web Worker dedicado (/motor/trabalhador.js): esta parte só
   conversa com ele. A tela do switch é da D4; aqui ficam o teste de
   capacidade, carregar o modelo, escrever um pacote e apagar o modelo.

   O teste de capacidade manda ao servidor só números (WebGPU sim/não,
   memória, tokens por segundo num texto de exemplo).
*/

const motorAparelho = { trabalhador: null, pedidos: {}, contador: 0, carregado: "", falso: false };

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

/* O que o aparelho tem, antes de baixar qualquer coisa. */
async function capacidadeDoAparelho() {
  let webgpu = false;
  try {
    const adaptador = navigator.gpu ? await navigator.gpu.requestAdapter() : null;
    webgpu = Boolean(adaptador);
  } catch (err) { webgpu = false; }
  const memoria = typeof navigator.deviceMemory === "number" ? navigator.deviceMemory : null;
  // O modelo tem ~1,3 GB: com menos de 4 GB de memória no aparelho, não vale.
  const passa = webgpu && (memoria === null || memoria >= 4);
  const motivo = !webgpu ? "este navegador não tem WebGPU (o Edge e o Chrome de computador têm)"
    : (!passa ? "o aparelho tem pouca memória para o modelo" : "");
  return { webgpu: webgpu, memoria_gb: memoria, passa: passa, motivo: motivo };
}

async function carregarModeloNoAparelho(andamento) {
  const r = await fetch("/api/aparelho/modelo");
  if (!r.ok) throw new Error(await erroDe(r));
  const m = await r.json();
  if (!m.disponivel) throw new Error(m.motivo);
  const cap = await capacidadeDoAparelho();
  const feito = await pedirAoMotor("carregar", { partes: m.partes, sha256: m.sha256, falso: motorAparelho.falso, webgpu: cap.webgpu }, andamento);
  motorAparelho.carregado = m.sha256;
  return Object.assign({ modelo: m.nome, bytes: m.bytes }, feito);
}

/* O teste de capacidade inteiro: carrega, mede num texto de exemplo e manda
   ao servidor só os números. */
async function testarCapacidadeDoAparelho(andamento) {
  const cap = await capacidadeDoAparelho();
  let medida = {}, carregou = null;
  if (cap.passa || motorAparelho.falso) {
    const c = await carregarModeloNoAparelho(andamento);
    carregou = c.segundos;
    medida = await pedirAoMotor("medir", {});
  }
  const numeros = { webgpu: cap.webgpu, memoria_gb: cap.memoria_gb, tokens_por_segundo: medida.tokens_por_segundo || null, carregou_s: carregou };
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
