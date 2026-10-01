/* ------------------------------------------ aprender com o uso (L1) */
/*
   👍/👎 embaixo de cada resposta, o cartão da 👎 (motivo, comentário, a
   resposta certa e o que ela precisa ter - que vira caso de teste) e o
   caderno de falhas em Configurações › Feedback, só na janela do escritório
   (src/aprendizado.py, docs/PLANO-PILOTO.md).

   Os polegares são desenhados aqui (SVG): o recorte da fonte de ícones não
   tem thumb_up/thumb_down.
*/

const aprender = { ligado: true, porConversa: {}, motivos: {}, caderno: null, verResolvidas: false };

const SVG_BOM = '<svg viewBox="0 0 24 24" width="16" height="16" aria-hidden="true"><path fill="currentColor" d="M2 21h4V9H2v12zm20-11c0-1.1-.9-2-2-2h-6.31l.95-4.57.03-.32c0-.41-.17-.79-.44-1.06L13.17 1 6.59 7.59C6.22 7.95 6 8.45 6 9v10c0 1.1.9 2 2 2h9c.83 0 1.54-.5 1.84-1.22l3.02-7.05c.09-.23.14-.47.14-.73v-2z"/></svg>';
const SVG_RUIM = '<svg viewBox="0 0 24 24" width="16" height="16" aria-hidden="true"><path fill="currentColor" d="M15 3H6c-.83 0-1.54.5-1.84 1.22l-3.02 7.05c-.09.23-.14.47-.14.73v2c0 1.1.9 2 2 2h6.31l-.95 4.57-.03.32c0 .41.17.79.44 1.06L9.83 23l6.59-6.59c.36-.36.58-.86.58-1.41V5c0-1.1-.9-2-2-2zm4 0v12h4V3h-4z"/></svg>';

/* Os dois botões, que linhaAssinatura (03-assistente.js) põe na assinatura. */
function botoesDeAvaliacao() {
  if (!aprender.ligado) return "";
  return '<span class="apr-notas"><button class="apr-nota" data-avaliar="bom" title="Boa resposta" aria-label="Boa resposta">' + SVG_BOM + "</button>" +
    '<button class="apr-nota" data-avaliar="ruim" title="Resposta com problema — conta o que foi" aria-label="Resposta com problema">' + SVG_RUIM + "</button></span>";
}

async function indiceDaResposta(resposta) {
  if (resposta && resposta.dataset.msg !== undefined) return Number(resposta.dataset.msg);
  if (!estado.trabalhoId) return null;
  try {
    const t = await (await fetch("/api/trabalhos/" + estado.trabalhoId)).json();
    if (typeof marcarRespostasGuardadas === "function") marcarRespostasGuardadas(t);
  } catch (err) { return null; }
  return resposta && resposta.dataset.msg !== undefined ? Number(resposta.dataset.msg) : null;
}

async function mandarAvaliacao(indice, corpo) {
  const r = await fetch("/api/aprendizado/avaliar", { method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify(Object.assign({ trabalho_id: estado.trabalhoId, indice: indice }, corpo)) });
  if (!r.ok) { avisoCert(await erroDe(r), { tom: "erro" }); return null; }
  const d = await r.json();
  (aprender.porConversa[estado.trabalhoId] = aprender.porConversa[estado.trabalhoId] || {})[String(indice)] =
    { nota: d.nota, motivo: d.motivo, caso: d.caso };
  pintarAvaliacoes();
  return d;
}

/* O cartao da resposta com problema (pacote de telas, `Conversa -
   Feedback`): o motivo em etiquetas, o que estava errado e a resposta certa
   lado a lado, o "Precisa ter" (que transforma a pergunta em caso de teste)
   e, no pe, o que isso faz, Cancelar e Anotar. */
function cartaoDaFalha(indice) {
  const motivos = Object.entries(aprender.motivos || {}).map(([id, rotulo]) =>
    '<button type="button" class="apr-motivo" data-apr-motivo="' + esc(id) + '">' + ic("check", 14) + esc(rotulo) + "</button>").join("");
  return '<div class="apr-cartao" data-apr-cartao="' + indice + '">' +
    '<div class="apr-corpo"><div class="apr-cabeca"><span class="apr-titulos"><b>O que houve com esta resposta?</b>' +
    "<small>Fica no caderno de falhas deste computador.</small></span>" +
    '<button type="button" class="botao-icone" data-apr-fechar="1" title="Fechar" aria-label="Fechar">' + ic("close", 16) + "</button></div>" +
    '<div class="apr-motivos">' + motivos + "</div>" +
    '<div class="apr-campos"><label class="apr-campo"><span>O que estava errado</span><textarea data-apr="comentario" rows="3"></textarea></label>' +
    '<label class="apr-campo"><span>A resposta certa seria</span><textarea data-apr="correcao" rows="3"></textarea></label></div>' +
    '<label class="apr-campo"><span>Precisa ter <small>opcional</small></span>' +
    '<span class="apr-linha">' + ic("rule", 16) + '<input type="text" data-apr="deve_conter" placeholder="ex.: 30 dias, cláusula 7"></span></label></div>' +
    '<div class="apr-pe"><small class="apr-explica">Com “Precisa ter” preenchido, a pergunta vira caso de teste: cada troca de modelo ou de regra é medida contra ela.</small>' +
    '<button type="button" class="fantasma" data-apr-cancelar="1">Cancelar</button><button type="button" class="primario" data-apr-enviar="1">Anotar</button></div></div>';
}

document.addEventListener("click", async (e) => {
  const b = e.target.closest && e.target.closest("[data-avaliar]");
  if (b) {
    e.preventDefault();
    const resposta = b.closest(".resposta");
    const indice = await indiceDaResposta(resposta);
    if (indice === null) { avisoCert("espere a resposta terminar de se gravar", { tom: "erro" }); return; }
    const aberto = resposta.querySelector(".apr-cartao");
    if (b.dataset.avaliar === "bom") {
      if (aberto) aberto.remove();
      const d = await mandarAvaliacao(indice, { nota: "bom" });
      if (d) avisoCert("Obrigado: anotado como boa resposta.", { tom: "ok" });
      return;
    }
    if (aberto) { aberto.remove(); pintarAvaliacoes(); return; }
    resposta.querySelector(".assinatura").insertAdjacentHTML("afterend", cartaoDaFalha(indice));
    // Com o cartao aberto, o "nao gostei" fica marcado, como no desenho.
    b.classList.add("on");
    const c = resposta.querySelector(".apr-cartao");
    c.querySelectorAll("[data-apr-motivo]").forEach((m) => {
      m.onclick = () => { c.querySelectorAll("[data-apr-motivo]").forEach((x) => x.classList.toggle("on", x === m)); };
    });
    const fechar = () => { sairDoAr(c); pintarAvaliacoes(); };
    c.querySelector("[data-apr-fechar]").onclick = fechar;
    c.querySelector("[data-apr-cancelar]").onclick = fechar;
    if (animacoesLigadas()) entraConteudo(c);
    c.querySelector("[data-apr-enviar]").onclick = async () => {
      const motivo = (c.querySelector("[data-apr-motivo].on") || {}).dataset;
      const campo = (k) => (c.querySelector('[data-apr="' + k + '"]') || {}).value || "";
      const d = await mandarAvaliacao(indice, { nota: "ruim", motivo: motivo ? motivo.aprMotivo : "",
        comentario: campo("comentario"), correcao: campo("correcao"), deve_conter: campo("deve_conter") });
      if (!d) return;
      c.innerHTML = '<p class="apr-feito">' + ic("check", 16) + " Anotado no caderno de falhas" + (d.caso ? ", e a pergunta virou caso de teste." : ".") + "</p>";
      setTimeout(() => sairDoAr(c), 4000);
    };
    return;
  }
});

/* Marca os botões das respostas já avaliadas por esta pessoa. */
function pintarAvaliacoes() {
  const minhas = aprender.porConversa[estado.trabalhoId] || {};
  document.querySelectorAll("#centro .resposta").forEach((r) => {
    const a = r.dataset.msg !== undefined ? minhas[r.dataset.msg] : null;
    r.querySelectorAll("[data-avaliar]").forEach((b) => b.classList.toggle("on", Boolean(a && a.nota === b.dataset.avaliar)));
  });
}

async function lerAvaliacoesDaConversa(id) {
  if (!id) return;
  try {
    const d = await (await fetch("/api/aprendizado/da-conversa/" + encodeURIComponent(id))).json();
    aprender.ligado = d.ligado !== false;
    aprender.motivos = d.motivos || {};
    aprender.porConversa[id] = d.avaliacoes || {};
    document.documentElement.classList.toggle("sem-avaliar", !aprender.ligado);
    if (estado.trabalhoId === id) pintarAvaliacoes();
  } catch (err) { /* sem as avaliações, os botões ficam sem marca */ }
}

/* A nota desta resposta, para o painel "Sobre esta resposta". */
function avaliacaoDaResposta(indice) {
  const a = (aprender.porConversa[estado.trabalhoId] || {})[String(indice)];
  if (!a) return "";
  return a.nota === "bom" ? "boa resposta" : "com problema" + (a.motivo && aprender.motivos[a.motivo] ? " · " + aprender.motivos[a.motivo] : "") +
    (a.caso ? " · virou caso de teste" : "");
}

(function () {
  let espera = null, ultima = "";
  const centro = document.getElementById("centro");
  if (!centro || typeof MutationObserver === "undefined") return;
  new MutationObserver(() => {
    clearTimeout(espera);
    espera = setTimeout(() => {
      const n = centro.querySelectorAll(".resposta .assinatura").length;
      const chave = (estado.trabalhoId || "") + ":" + n;
      if (!estado.trabalhoId || !n || chave === ultima) { pintarAvaliacoes(); return; }
      ultima = chave;
      lerAvaliacoesDaConversa(estado.trabalhoId);
    }, 300);
  }).observe(centro, { childList: true, subtree: true });
})();

/* ------------------------------------------ o caderno de falhas */

function cartaoCaderno() {
  if (!acessoDeFora.local) return "";
  return cartaoCfg("Caderno de falhas", metaCfg("as 👎 das respostas, neste computador"),
    '<div class="cfg-sub">' + interruptor("aprendizado", "avaliar", "Avaliar as respostas",
      "👍 e 👎 embaixo de cada resposta; a 👎 pergunta o motivo e a resposta certa. Nada sai deste computador") + "</div>" +
    '<div id="apr-caderno"><p class="nota">abrindo o caderno…</p></div>');
}

function linhaDaFalha(f) {
  const quando = typeof quandoCurto === "function" ? quandoCurto(f.quando) : f.quando;
  return '<div class="apr-falha' + (f.resolvida ? " resolvida" : "") + '">' +
    '<div class="apr-falha-cab"><b>' + esc(f.pergunta || "(sem pergunta)") + "</b><small>" +
    esc([f.motivo_rotulo || "sem motivo", f.pessoa_nome, quando, f.modelo + (f.onde === "aparelho" ? " · no aparelho" : "")].filter(Boolean).join(" · ")) +
    "</small></div>" +
    '<p class="apr-resposta">' + esc((f.resposta || "").slice(0, 280)) + ((f.resposta || "").length > 280 ? "…" : "") + "</p>" +
    (f.comentario ? '<p><span class="apr-rot">O que estava errado</span> ' + esc(f.comentario) + "</p>" : "") +
    (f.correcao ? '<p><span class="apr-rot">A resposta certa</span> ' + esc(f.correcao) + "</p>" : "") +
    (f.caso ? '<p class="apr-caso">' + ic("task_alt", 14) + " caso de teste: precisa ter " + esc(f.termos.join(", ")) + "</p>" : "") +
    '<div class="apr-botoes">' +
    '<button data-apr-abrir="' + esc(f.trabalho_id) + '">' + ic("chat", 16) + "Abrir a conversa</button>" +
    (!f.caso ? '<button data-apr-caso="' + f.id + '">' + ic("rule", 16) + "Virar caso de teste</button>" : "") +
    '<button data-apr-resolver="' + f.id + '" data-resolvida="' + (f.resolvida ? "0" : "1") + '">' + (f.resolvida ? "Reabrir" : "Resolvida") + "</button>" +
    "</div></div>";
}

function htmlDoCaderno(d) {
  const c = d.conta || {};
  const total = (c.bom || 0) + (c.ruim || 0);
  const motivos = Object.entries(d.por_motivo || {}).sort((a, b) => b[1] - a[1])
    .map(([k, v]) => '<span class="apr-chip">' + esc(k) + " · " + v + "</span>").join("");
  const caminhos = Object.entries(d.por_caminho || {}).map(([k, v]) =>
    '<div class="apr-conta-linha"><span>' + esc(k) + "</span><b>👍 " + v.bom + "</b><b>👎 " + v.ruim + "</b></div>").join("");
  const falhas = (d.falhas || []).filter((f) => aprender.verResolvidas || !f.resolvida);
  return '<div class="apr-resumo"><p><b>Últimos ' + d.dias + " dias:</b> " + (total
    ? plural(total, "resposta avaliada", "respostas avaliadas") + " · 👍 " + (c.bom || 0) + " · 👎 " + (c.ruim || 0) +
      " · " + plural(d.casos || 0, "caso de teste", "casos de teste") + " do caderno"
    : "nenhuma resposta avaliada ainda.") + "</p>" +
    (motivos ? '<div class="apr-chips">' + motivos + "</div>" : "") +
    (caminhos ? '<div class="apr-contas"><div class="apr-conta-linha apr-conta-cab"><span>Caminho</span><b>bom</b><b>ruim</b></div>' + caminhos + "</div>" : "") +
    "</div>" +
    '<label class="apr-ver"><input type="checkbox" data-apr-ver-resolvidas="1"' + (aprender.verResolvidas ? " checked" : "") + "> mostrar as resolvidas</label>" +
    (falhas.length ? '<div class="apr-falhas">' + falhas.map(linhaDaFalha).join("") + "</div>"
      : '<p class="cfg-explica">Nenhuma falha em aberto.</p>') +
    '<p class="cfg-explica">Os casos de teste vão para <code>data/medicao/conjunto-real.jsonl</code>, junto das correções do cartão do documento; ' +
    "<code>tools/medir.py</code> mede cada troca de modelo contra eles.</p>";
}

async function blocoCaderno() {
  const alvo = $("apr-caderno");
  if (!alvo) return;
  if (!cfg.chaves && typeof carregarChaves === "function") {
    await carregarChaves();
    if ($("conversa-titulo").textContent === "Configurações" && cfg.secao === "feedback") { desenharConfig(); return; }
  }
  try {
    const r = await fetch("/api/aprendizado/caderno");
    if (!r.ok) throw new Error(await erroDe(r));
    aprender.caderno = await r.json();
  } catch (err) {
    alvo.innerHTML = '<p class="cfg-explica">não consegui abrir o caderno: ' + esc(String(err.message || err)) + "</p>";
    return;
  }
  desenharCaderno();
}

function desenharCaderno() {
  const alvo = $("apr-caderno");
  if (!alvo || !aprender.caderno) return;
  alvo.innerHTML = htmlDoCaderno(aprender.caderno);
  const ver = alvo.querySelector("[data-apr-ver-resolvidas]");
  if (ver) ver.onchange = () => { aprender.verResolvidas = ver.checked; desenharCaderno(); };
  alvo.querySelectorAll("[data-apr-abrir]").forEach((b) => { b.onclick = () => abrirTrabalho(b.dataset.aprAbrir); });
  alvo.querySelectorAll("[data-apr-resolver]").forEach((b) => {
    b.onclick = async () => {
      const r = await fetch("/api/aprendizado/caderno/" + b.dataset.aprResolver + "/resolver", { method: "POST",
        headers: { "Content-Type": "application/json" }, body: JSON.stringify({ resolvida: b.dataset.resolvida === "1" }) });
      if (!r.ok) { avisoCert(await erroDe(r), { tom: "erro" }); return; }
      blocoCaderno();
    };
  });
  alvo.querySelectorAll("[data-apr-caso]").forEach((b) => {
    b.onclick = async () => {
      const termos = await perguntar({ titulo: "Virar caso de teste", contexto: "Caderno de falhas",
        texto: "O que a resposta certa precisa ter? Separe por vírgula. Cada troca de modelo ou de regra vai ser medida contra isso.",
        campo: { rotulo: "Precisa ter", placeholder: "30 dias, cláusula 7", icone: "rule" }, confirmar: "Virar caso de teste" });
      if (!termos) return;
      const r = await fetch("/api/aprendizado/caderno/" + b.dataset.aprCaso + "/caso", { method: "POST",
        headers: { "Content-Type": "application/json" }, body: JSON.stringify({ deve_conter: termos }) });
      if (!r.ok) { avisoCert(await erroDe(r), { tom: "erro" }); return; }
      avisoCert("Virou caso de teste.", { tom: "ok" });
      blocoCaderno();
    };
  });
}
