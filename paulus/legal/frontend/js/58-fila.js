/* ------------------------------------------------------------ fila (F1) */
/*
   A fila do modelo à vista (docs/PROGRESSO-APARELHO.md, F1; src/fila_de_todos.py).
   Com a chave aparelho.fila:

   - a pergunta mandada com esta conversa respondendo não some mais: vira uma
     bolha "na fila · 2º · ~40 s", com Editar e Cancelar, guardada no
     servidor (sobrevive a trocar de conversa e a recarregar), e vai sozinha
     na vez. Quando ela sai da fila, a tela reabre a conversa e se inscreve
     na resposta, como faz com qualquer resposta em curso;
   - a terceira da mesma pessoa volta para o campo, com a razão, sem nada
     guardado;
   - Ctrl+Enter manda com prioridade; a dica só aparece quando há fila;
   - a janela do escritório vê a fila inteira: nome e tela, nunca o texto.
*/

const filaConversa = { vigia: null, quantas: 0, conversa: "", ids: [], reabrir: false };

async function enfileirarNaConversa(o) {
  const texto = ((o && o.texto) || $("pedido").value).trim();
  if (!texto || !estado.trabalhoId) return;
  const id = estado.trabalhoId;
  let r;
  try {
    r = await fetch("/api/trabalhos/" + id + "/perguntar", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify(Object.assign({ pergunta: texto, prioridade: Boolean(o && o.prioridade) }, escopoDoEnvio(),
        typeof agenteDoEnvio === "function" ? agenteDoEnvio() : {})),
    });
  } catch (err) {
    avisoCert("não consegui mandar a pergunta", { tom: "erro" });
    return;
  }
  if (r.status === 202) {
    const d = await r.json();
    if (!(o && o.texto)) {
      $("pedido").value = "";
      $("pedido").style.height = "auto";
      if (painelNovo()) gravarNaConversa(id, { rascunho: "", anexos: [] });
    }
    if (d.aviso) avisoCert(d.aviso);
    desenharPendentes();
    return;
  }
  if (!r.ok) {
    // 429: "você já tem duas perguntas esperando" - o texto fica no campo.
    avisoCert(await erroDe(r), { tom: "erro" });
    return;
  }
  // A resposta anterior acabou no caminho: a pergunta foi respondida direto.
  // A resposta segue no servidor; a tela reabre a conversa e se inscreve.
  try { await r.body.cancel(); } catch (err) { /* nada */ }
  if (!(o && o.texto)) $("pedido").value = "";
  setTimeout(() => abrirTrabalho(id), 300);
}

/* O envio normal voltou 202 (a conversa já respondia, de outra aba ou de
   outra pessoa) ou 429: tira o que a tela já tinha posto para a resposta. */
async function desfazerEnvioNaFila(r, pedido, elementos) {
  (elementos || []).forEach((el) => { if (el && el.remove) el.remove(); });
  const bolhas = $("centro").querySelectorAll(".bolha-pessoa");
  const ultima = bolhas[bolhas.length - 1];
  if (ultima && ultima.textContent === pedido) {
    const quem = ultima.previousElementSibling;
    if (quem && quem.classList.contains("bolha-quem")) quem.remove();
    ultima.remove();
  }
  if (r.status === 429) {
    $("pedido").value = pedido;
    avisoCert(await erroDe(r), { tom: "erro" });
    return;
  }
  const d = await r.json();
  if (d.aviso) avisoCert(d.aviso);
  setTimeout(desenharPendentes, 50);
}

function linhaDaPendente(p) {
  if (p.estado === "interrompida") return "não foi enviada · " + (p.motivo || "");
  const frente = (p.na_frente || []).map((x) => x.nome + " · " + x.origem);
  return "na fila · " + Math.max(1, p.posicao || 1) + "º" + (p.previsao_s ? " · ~" + segundosCurtos(p.previsao_s) : "") +
    (frente.length ? " · na frente: " + frente.join(", ") : "") +
    (p.prioridade ? " · com prioridade" : "") + (p.motivo ? " · " + p.motivo : "");
}

function bolhaPendente(p) {
  if (!p.sua) {
    return '<div class="fila-pendente de-outro" data-pendente="' + esc(p.id) + '"><small>' +
      esc("pergunta de " + (p.nome || "outra pessoa") + " · " + linhaDaPendente(p)) + "</small></div>";
  }
  const botoes = p.estado === "interrompida"
    ? '<button class="com-icone" data-pendente-reenviar="' + esc(p.id) + '">' + ic("send", 16) + "Enviar agora</button>" +
      '<button data-pendente-cancelar="' + esc(p.id) + '">Descartar</button>'
    : '<button class="com-icone" data-pendente-editar="' + esc(p.id) + '">' + ic("edit", 16) + "Editar</button>" +
      '<button data-pendente-cancelar="' + esc(p.id) + '">Cancelar</button>';
  return '<div class="fila-pendente" data-pendente="' + esc(p.id) + '">' +
    '<div class="bolha-pessoa na-fila">' + esc(p.texto) + "</div>" +
    '<div class="fila-pendente-linha"><small>' + esc(linhaDaPendente(p)) + "</small>" +
    '<span class="fila-pendente-botoes">' + botoes +
    (acessoDeFora.local ? '<button data-ver-fila="1">Ver a fila</button>' : "") + "</span></div></div>";
}

async function desenharPendentes() {
  clearTimeout(filaConversa.vigia);
  const id = estado.trabalhoId;
  const velho = $("fila-na-conversa");
  if (!filaLigada() || !id) { if (velho) velho.remove(); filaConversa.quantas = 0; atualizarDicaPrioridade(); return; }
  let d;
  try {
    const r = await fetch("/api/trabalhos/" + id + "/pendentes");
    d = r.ok ? await r.json() : { pendentes: [] };
  } catch (err) { d = { pendentes: [] }; }
  if (estado.trabalhoId !== id) return;
  const lista = d.pendentes || [];
  const ids = lista.filter((p) => p.estado !== "interrompida").map((p) => p.id);
  const naFila = ids.length;
  // Uma saiu da fila: foi mandada. Com a página livre, a tela reabre a
  // conversa e se inscreve na resposta dela (vigiarTrabalhoEmCurso); com a
  // página ainda acompanhando a anterior, espera ela acabar.
  if (filaConversa.conversa !== id) { filaConversa.ids = []; filaConversa.reabrir = false; }
  if (filaConversa.ids.some((x) => !ids.includes(x))) filaConversa.reabrir = true;
  filaConversa.ids = ids;
  filaConversa.quantas = naFila;
  filaConversa.conversa = id;
  if (filaConversa.reabrir && !estado.ocupado) {
    filaConversa.reabrir = false;
    abrirTrabalho(id);
    return;
  }
  let caixa = $("fila-na-conversa");
  if (!lista.length) {
    if (caixa) caixa.remove();
    atualizarDicaPrioridade();
    if (filaConversa.reabrir) filaConversa.vigia = setTimeout(desenharPendentes, 2000);
    return;
  }
  if (!caixa) {
    caixa = document.createElement("div");
    caixa.id = "fila-na-conversa";
    caixa.className = "fila-na-conversa";
  }
  // Sempre por último na conversa, embaixo da resposta que está sendo escrita.
  $("centro").appendChild(caixa);
  caixa.innerHTML = lista.map(bolhaPendente).join("");
  ligarPendentes(caixa, id);
  atualizarDicaPrioridade();
  if (naFila || filaConversa.reabrir) filaConversa.vigia = setTimeout(desenharPendentes, 2000);
}

function ligarPendentes(caixa, id) {
  const achar = (pid) => fetch("/api/trabalhos/" + id + "/pendentes").then((r) => r.json())
    .then((d) => (d.pendentes || []).find((p) => p.id === pid));
  caixa.querySelectorAll("[data-pendente-cancelar]").forEach((b) => {
    b.onclick = async () => {
      // Cancelada não é mandada: não reabre a conversa por ela.
      filaConversa.ids = filaConversa.ids.filter((x) => x !== b.dataset.pendenteCancelar);
      const r = await fetch("/api/trabalhos/" + id + "/pendentes/" + b.dataset.pendenteCancelar, { method: "DELETE" });
      if (!r.ok) avisoCert(await erroDe(r), { tom: "erro" });
      desenharPendentes();
    };
  });
  caixa.querySelectorAll("[data-pendente-editar]").forEach((b) => {
    b.onclick = async () => {
      const p = await achar(b.dataset.pendenteEditar);
      if (!p) { desenharPendentes(); return; }
      const novo = await perguntar({ titulo: "Editar a pergunta na fila", contexto: "Ela continua no mesmo lugar da fila",
        campo: { rotulo: "Pergunta", valor: p.texto, max: 4000 }, confirmar: "Guardar" });
      if (!novo || !novo.trim()) return;
      const r = await fetch("/api/trabalhos/" + id + "/pendentes/" + p.id, {
        method: "PUT", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ texto: novo }) });
      if (!r.ok) avisoCert(await erroDe(r), { tom: "erro" });
      desenharPendentes();
    };
  });
  caixa.querySelectorAll("[data-pendente-reenviar]").forEach((b) => {
    b.onclick = async () => {
      const p = await achar(b.dataset.pendenteReenviar);
      if (!p) return;
      await fetch("/api/trabalhos/" + id + "/pendentes/" + p.id, { method: "DELETE" });
      enviar({ texto: p.texto });
    };
  });
}

/* A dica só quando há fila: sem ela, Ctrl+Enter é o mesmo Enter e a dica
   seria ruído. */
function atualizarDicaPrioridade() {
  const campo = $("pedido");
  if (!campo) return;
  let dica = $("dica-prioridade");
  const mostrar = filaLigada() && (estado.ocupado || filaConversa.quantas > 0 || Boolean(estado.linhaViva && /na fila/.test(estado.linhaViva)));
  if (!mostrar) { if (dica) dica.hidden = true; return; }
  if (!dica) {
    dica = document.createElement("small");
    dica.id = "dica-prioridade";
    dica.className = "dica-prioridade";
    dica.textContent = "Ctrl+Enter envia com prioridade";
    // Embaixo da caixa do campo, e não dentro dela: é uma dica, não um botão.
    const cartao = $("cartao-campo");
    if (cartao) cartao.insertAdjacentElement("afterend", dica);
    else campo.parentElement.appendChild(dica);
  }
  dica.hidden = false;
}

/* A fila inteira, na janela do escritório: quem, de onde, há quanto tempo. */
async function verFilaInteira() {
  const r = await fetch("/api/fila");
  if (!r.ok) { avisoCert(await erroDe(r), { tom: "erro" }); return; }
  const d = await r.json();
  const linhas = (d.fila || []).map((v, i) =>
    '<div class="fila-linha"><b>' + (v.respondendo ? "respondendo" : (i + "º")) + "</b><span>" + esc(v.nome) + " · " + esc(v.origem) +
    (v.prioridade ? " · com prioridade" : "") + "</span><small>" +
    esc(v.respondendo ? "há " + segundosCurtos(v.respondendo_s) : "esperando há " + segundosCurtos(v.esperando_s)) + "</small></div>").join("");
  await dialogo({ titulo: "A fila do modelo", contexto: "Agora, nesta máquina",
    texto: d.fila && d.fila.length ? "Quem está esperando a vez do modelo, em ordem. O texto das perguntas não aparece aqui."
      : "Ninguém esperando: o modelo está livre.",
    html: linhas ? '<div class="fila-lista">' + linhas + "</div>" : "", confirmar: "Fechar", semCancelar: true });
}

document.addEventListener("click", (e) => {
  const b = e.target.closest && e.target.closest("[data-ver-fila]");
  if (b) { e.preventDefault(); verFilaInteira(); }
});
