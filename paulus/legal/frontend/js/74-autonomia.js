/* ------------------------------------------ agente que faz sozinho (N14) */
/*
   Com a chave "Agentes fazem sozinhos" (Aprovações › Regras de alçada) e a
   ferramenta na `autonomia:` do AGENTE.md, o agente faz sem o cartão de
   confirmar (src/agente_na_conversa.py). O que ele fez aparece aqui, dito, com
   "Desfazer" - na conversa e no Histórico de Aprovações.
*/

function cartaoSozinho(d) {
  const c = d.campos || {};
  const desfeito = Boolean(d.desfeito);
  return '<div class="proposta sozinho"><div class="proposta-topo"><span class="rotulo">' + (desfeito ? "desfeito" : "feito sozinho") + "</span>" +
    "<b>" + esc(d.titulo || "") + "</b></div>" +
    '<p class="explica">O agente “' + esc((d.agente || {}).nome || "") + "” fez isto sem perguntar: a ferramenta " + esc(d.ferramenta || "") +
    " está na autonomia do AGENTE.md dele, e a chave “Agentes fazem sozinhos” está ligada nas Regras de alçada. Fica no Histórico de Aprovações.</p>" +
    (desfeito ? "" : '<div class="linha-form">' + (c.onde ? '<button data-sozinho-ver="1">Ver na tela</button>' : "") +
      '<button class="perigo" data-sozinho-desfazer="' + esc(d.pedido_id || "") + '">' + ic("undo", 15) + "Desfazer</button></div>") + "</div>";
}

async function desfazerSozinho(pedidoId) {
  const r = await fetch("/api/aprovacoes/" + encodeURIComponent(pedidoId) + "/desfazer", { method: "POST" });
  if (!r.ok) { avisoCert(await erroDe(r), { tom: "erro" }); return null; }
  const d = await r.json();
  avisoCert("Desfeito: " + d.desfeito + ".", { tom: "ok" });
  if (typeof aprov !== "undefined" && d.hoje) { aprov.pendentes = d.pendentes; aprov.hoje = d.hoje; }
  return d;
}

function ligarSozinho(caixa, d) {
  const ver = caixa.querySelector("[data-sozinho-ver]");
  if (ver) ver.onclick = () => {
    const c = d.campos || {};
    marcarDestino(c.onde);
    if (c.onde === "calendario") mostrarCalendario();
    else if (c.onde === "cadastros") mostrarCadastros();
    else if (c.onde === "passos" && typeof mostrarAgentes === "function") mostrarAgentes();
    else mostrarBiblioteca();
  };
  const desfazer = caixa.querySelector("[data-sozinho-desfazer]");
  if (desfazer) desfazer.onclick = async () => {
    desfazer.disabled = true;
    const r = await desfazerSozinho(desfazer.dataset.sozinhoDesfazer);
    if (!r) { desfazer.disabled = false; return; }
    caixa.innerHTML = cartaoSozinho(Object.assign({}, d, { desfeito: true }));
  };
}
