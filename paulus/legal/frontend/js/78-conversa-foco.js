/* ---------------------------------------- o foco no alto da coluna */
/*
   Pacote de telas de 01/10/2026 (`Conversa - Foco`): com um ciclo de foco
   andando, a coluna de contexto da conversa ganha, no alto, o cartao do
   Foco - a tarefa do ciclo, o tempo que falta, a barra do ciclo e, quando
   um lembrete venceu (ou a medicao diz que a pessoa esta ha muito tempo sem
   parar), a linha dele com o Feito. Tudo vem de /api/bemestar (js/21-foco.js
   e src/bemestar.py): o relogio anda aqui e confere com o servidor.
*/

const fcl = { ciclo: null, recebido: 0, lembrete: null, alerta: null, lidoEm: 0, pedindo: false };
const FCL_CICLO_MS = 5000;
const FCL_TUDO_MS = 30000;

function focoNaConversa() {
  const col = $("conversa-col");
  return Boolean(col && col.classList.contains("em-conversa") && !col.classList.contains("vazia"));
}

async function lerFocoDoLado() {
  if (fcl.pedindo || !focoNaConversa()) return;
  fcl.pedindo = true;
  try {
    const tudo = !fcl.lidoEm || Date.now() - fcl.lidoEm > FCL_TUDO_MS;
    if (tudo) {
      const d = await (await fetch("/api/bemestar")).json();
      fcl.ciclo = d.ciclo;
      fcl.alerta = d.alerta || null;
      // O lembrete da vez: o primeiro ligado que ja passou da hora.
      fcl.lembrete = (d.lembretes || []).find((l) => l.ligado && l.atrasado_min > 0 && !l.cumprido) || null;
      fcl.lidoEm = Date.now();
    } else {
      fcl.ciclo = await (await fetch("/api/bemestar/ciclo")).json();
    }
    fcl.recebido = Date.now();
  } catch (err) {
    /* sem servidor agora: fica o que estava */
  } finally {
    fcl.pedindo = false;
  }
  desenharFocoNoLado();
}

function restanteDoFoco() {
  const c = fcl.ciclo;
  if (!c || c.estado === "parado") return 0;
  return Math.max(0, Math.round((c.restante || 0) - (Date.now() - fcl.recebido) / 1000));
}

function textoDoRestante(s) {
  return String(Math.floor(s / 60)).padStart(2, "0") + ":" + String(s % 60).padStart(2, "0");
}

function desenharFocoNoLado() {
  const caixa = $("lado-topo");
  if (!caixa) return;
  const c = fcl.ciclo;
  if (!focoNaConversa() || !c || c.estado === "parado") {
    caixa.hidden = true;
    caixa.innerHTML = "";
    return;
  }
  const restante = restanteDoFoco();
  const pct = c.duracao ? Math.max(0, Math.min(100, (1 - restante / c.duracao) * 100)) : 0;
  const pausa = c.estado === "pausa";
  const tarefa = c.tarefa || (pausa ? "pausa depois do ciclo " + c.numero : "ciclo " + c.numero);
  const sentado = fcl.alerta ? fcl.alerta.titulo.replace(/^Você está /, "").replace(/ sem parar$/, " sem parar") : "";
  const lembrete = fcl.lembrete
    ? '<div class="fcl-lembrete">' + ic("directions_walk", 16) + '<span class="fcl-lembrete-texto">' + esc(fcl.lembrete.titulo) +
      (sentado ? " · " + esc(sentado) : "") + "</span>" +
      '<button type="button" class="fcl-feito" data-fcl-feito="' + fcl.lembrete.id + '">Feito</button></div>'
    : (sentado ? '<div class="fcl-lembrete">' + ic("directions_walk", 16) + '<span class="fcl-lembrete-texto">' + esc(fcl.alerta.titulo) + "</span></div>" : "");
  const novo = caixa.hidden;
  caixa.hidden = false;
  caixa.innerHTML = '<div class="fcl-cartao' + (pausa ? " pausa" : "") + '">' +
    '<div class="fcl-cabeca"><i class="fcl-ponto"></i><b>' + (pausa ? "Pausa" : "Foco") + "</b>" +
    '<span class="fcl-tarefa">' + esc(tarefa) + "</span>" +
    '<span class="fcl-tempo" data-fcl-tempo="1">' + textoDoRestante(restante) + "</span>" +
    (pausa
      ? '<button type="button" class="botao-icone" data-fcl-ciclo="1" title="Começar o próximo ciclo" aria-label="Começar o próximo ciclo">' + ic("play_arrow", 16) + "</button>"
      : '<button type="button" class="botao-icone" data-fcl-pausa="1" title="Ir para a pausa" aria-label="Ir para a pausa">' + ic("pause", 16) + "</button>") +
    "</div>" +
    '<div class="fcl-barra"><i data-fcl-barra="1" style="width:' + pct.toFixed(1) + '%"></i></div>' + lembrete + "</div>";
  if (novo && animacoesLigadas()) entraConteudo(caixa.firstElementChild);
  const feito = caixa.querySelector("[data-fcl-feito]");
  if (feito) feito.onclick = async () => {
    feito.disabled = true;
    const r = await fetch("/api/bemestar/lembretes/" + feito.dataset.fclFeito + "/feito", { method: "POST" }).catch(() => null);
    if (!r || !r.ok) { feito.disabled = false; avisoCert(r ? await erroDe(r) : "não consegui marcar agora", { tom: "erro" }); return; }
    avisoCert("lembrete marcado como feito", { tom: "ok" });
    fcl.lidoEm = 0;
    lerFocoDoLado();
  };
  const pausar = caixa.querySelector("[data-fcl-pausa]");
  if (pausar) pausar.onclick = async () => { await fetch("/api/bemestar/pausa", { method: "POST" }).catch(() => null); fcl.lidoEm = 0; lerFocoDoLado(); };
  const ciclo = caixa.querySelector("[data-fcl-ciclo]");
  if (ciclo) ciclo.onclick = async () => {
    await fetch("/api/bemestar/ciclo", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ tarefa: c.tarefa || "" }) }).catch(() => null);
    fcl.lidoEm = 0;
    lerFocoDoLado();
  };
}

/* O relogio do cartao anda a cada segundo; o servidor confere a cada 5 s. */
setInterval(() => {
  const tempo = document.querySelector("[data-fcl-tempo]");
  if (!tempo || !fcl.ciclo) return;
  const restante = restanteDoFoco();
  tempo.textContent = textoDoRestante(restante);
  const barra = document.querySelector("[data-fcl-barra]");
  if (barra && fcl.ciclo.duracao) barra.style.width = Math.max(0, Math.min(100, (1 - restante / fcl.ciclo.duracao) * 100)).toFixed(1) + "%";
}, 1000);
setInterval(lerFocoDoLado, FCL_CICLO_MS);

(function () {
  const col = $("conversa-col");
  if (col && typeof MutationObserver === "function") {
    new MutationObserver(() => { if (focoNaConversa()) lerFocoDoLado(); else desenharFocoNoLado(); }).observe(col, { attributes: true, attributeFilter: ["class"] });
  }
})();
