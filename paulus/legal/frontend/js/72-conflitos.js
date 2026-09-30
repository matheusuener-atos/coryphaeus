/* ------------------------------------------ o conflito como pendência (N4) */
/*
   Cada conflito de interesse achado (src/clientes.py) fica aberto até alguém
   dizer como resolveu - não é a mesma pessoa, os clientes autorizaram, a
   muralha foi aplicada, o escritório recusou um dos casos, ou outro motivo
   escrito -, com quem e quando. Abre pela Central de avisos, pelo Serviço,
   pela visão do cliente e por Cadastros › Conflitos. Só na janela do
   escritório: a conferência cruza todos os clientes.
*/

const cfl = { resolucoes: [] };

function dataCurtaCfl(iso) {
  return iso ? String(iso).slice(0, 10).split("-").reverse().join("/") : "";
}

function subDoConflito(c) {
  if (c.estado === "resolvido") {
    return "resolvido: " + (c.resolucao_rotulo || c.resolucao || "") + (c.resolvido_por ? " · por " + c.resolvido_por : "") +
      (c.resolvido_em ? " em " + dataCurtaCfl(c.resolvido_em) : "");
  }
  return ["aberto desde " + dataCurtaCfl(c.criado_em), c.parte ? "por “" + c.parte + "”" : "", c.servico_nome || ""].filter(Boolean).join(" · ");
}

function linhaDoConflito(c) {
  const resolvido = c.estado === "resolvido";
  return '<div class="cfl-linha' + (resolvido ? " resolvido" : "") + '">' + ic(resolvido ? "check" : "flag", 16) +
    '<span class="duas-linhas"><b>' + esc(c.texto) + "</b><small>" + esc(subDoConflito(c)) + "</small></span>" +
    '<button type="button" data-cfl-abrir="' + c.id + '">' + (resolvido ? "Ver" : "Resolver") + "</button></div>";
}

async function abrirConflito(id) {
  let d;
  try {
    const r = await fetch("/api/conflitos/" + id);
    if (!r.ok) throw new Error(await erroDe(r));
    d = await r.json();
  } catch (err) { avisoCert(String(err.message || err), { tom: "erro" }); return; }
  const c = d.conflito;
  cfl.resolucoes = d.resolucoes || [];
  const onde = [c.servico_nome ? "Serviço “" + c.servico_nome + "”" : "", c.outro_servico_nome ? "Serviço “" + c.outro_servico_nome + "”" : "",
    c.cliente_nome ? "cliente do escritório: " + c.cliente_nome : ""].filter(Boolean).join(" · ");
  if (c.estado === "resolvido") {
    let reabrir = false;
    const espera = dialogo({ titulo: "Conflito resolvido", contexto: "Conflito de interesse", classe: "dialogo-ver",
      html: '<p class="ap-resumo">' + esc(c.texto) + "</p>" + fichaDoDialogo([
        ["Como", c.resolucao_rotulo || c.resolucao], ["Por", c.resolvido_por || "—"], ["Quando", dataCurtaCfl(c.resolvido_em)],
        c.nota ? ["Anotação", c.nota] : null, onde ? ["Onde", onde] : null, ["Aberto em", dataCurtaCfl(c.criado_em)]]),
      confirmar: "Fechar", semCancelar: true,
      rodape: '<button type="button" id="cfl-reabrir">' + ic("undo", 16) + "Reabrir</button>" });
    const b = document.getElementById("cfl-reabrir");
    if (b) b.onclick = () => { reabrir = true; if (dialogoAberto) dialogoAberto.fechar(null); };
    await espera;
    if (reabrir) {
      const r = await fetch("/api/conflitos/" + id + "/reabrir", { method: "POST" });
      if (!r.ok) { avisoCert(await erroDe(r), { tom: "erro" }); return; }
      avisoCert("Conflito reaberto: volta para os avisos.", { tom: "ok" });
      depoisDoConflito();
    }
    return;
  }
  let escolha = "", nota = "";
  const espera = dialogo({
    titulo: "Resolver o conflito", contexto: "Conflito de interesse", larga: true,
    html: '<p class="ap-resumo">' + esc(c.texto) + "</p>" +
      (onde ? '<p class="cfg-explica">' + esc(onde) + (c.parte ? " · pela parte “" + esc(c.parte) + "”" : "") + "</p>" : "") +
      '<fieldset class="ap-opcoes"><legend>Como foi resolvido</legend>' + cfl.resolucoes.map((o) =>
        '<label class="ap-opcao"><input type="radio" name="cfl-como" value="' + esc(o.valor) + '" data-cfl-como="1"><span>' + esc(o.rotulo) + "</span></label>").join("") +
      "</fieldset>" +
      '<div class="dialogo-campo"><label for="cfl-nota">Anotação (quem autorizou, qual documento, o que mudou)</label>' +
      '<textarea id="cfl-nota" rows="3" class="cfl-nota"></textarea></div>' +
      '<p class="cfg-explica">Fica guardado com o seu nome e a data. Resolvido, o aviso sai; dá para reabrir depois.</p>',
    confirmar: "Guardar a resolução",
  });
  document.querySelectorAll("[data-cfl-como]").forEach((el) => { el.onchange = () => { if (el.checked) escolha = el.value; }; });
  const area = document.getElementById("cfl-nota");
  if (area) area.oninput = () => { nota = area.value; };
  const r = await espera;
  if (!r || !r.ok) return;
  if (!escolha) { avisoCert("escolha como o conflito foi resolvido", { tom: "erro" }); return; }
  const x = await fetch("/api/conflitos/" + id + "/resolver", { method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ resolucao: escolha, nota: nota }) });
  if (!x.ok) { avisoCert(await erroDe(x), { tom: "erro" }); return; }
  avisoCert("Conflito resolvido e guardado.", { tom: "ok" });
  depoisDoConflito();
}

/* Depois de resolver ou reabrir: redesenha o que estiver aberto por baixo. */
function depoisDoConflito() {
  if (typeof sv !== "undefined" && sv.aberto && document.getElementById("cli-conflitos-sv") && typeof recarregarServico === "function") recarregarServico();
  else if (document.getElementById("cli-visao") && typeof cli !== "undefined" && cli.visao && typeof mostrarVisaoDoCliente === "function") mostrarVisaoDoCliente(cli.visao.cliente.id);
  if (typeof carregarAvisosDoDia === "function") carregarAvisosDoDia(true);
}

async function mostrarConflitos() {
  let d;
  try {
    const r = await fetch("/api/conflitos?conferir=true");
    if (!r.ok) throw new Error(await erroDe(r));
    d = await r.json();
  } catch (err) { avisoCert(String(err.message || err), { tom: "erro" }); return; }
  const abertos = d.conflitos.filter((c) => c.estado !== "resolvido");
  const resolvidos = d.conflitos.filter((c) => c.estado === "resolvido");
  const fechou = d.conferido && d.conferido.fechados_sozinhos
    ? '<p class="cfg-explica">' + plural(d.conferido.fechados_sozinhos, "conflito deixou", "conflitos deixaram") + " de existir e " +
      (d.conferido.fechados_sozinhos === 1 ? "fechou" : "fecharam") + " sozinho" + (d.conferido.fechados_sozinhos === 1 ? "" : "s") + ".</p>" : "";
  const html = '<p class="cfg-explica">O PAULUS confere agora todos os Serviços em andamento: o cliente que é parte contrária em outro, ' +
    "a parte contrária que é cliente do escritório, e quem está na equipe dos dois lados. Avisa, não bloqueia: quem decide é o advogado.</p>" + fechou +
    '<h4 class="pr-sub">Abertos' + (abertos.length ? " · " + abertos.length : "") + "</h4>" +
    (abertos.length ? '<div class="cfl-lista">' + abertos.map(linhaDoConflito).join("") + "</div>" : '<p class="cfg-explica">Nenhum conflito aberto.</p>') +
    (resolvidos.length ? '<h4 class="pr-sub">Resolvidos</h4><div class="cfl-lista">' + resolvidos.slice(0, 40).map(linhaDoConflito).join("") + "</div>" : "");
  dialogo({ titulo: "Conflitos de interesse", contexto: "Cadastros", html: html, confirmar: "Fechar", semCancelar: true, larga: true, classe: "cfl-dialogo" });
}

document.addEventListener("click", (e) => {
  const b = e.target.closest && e.target.closest("[data-cfl-abrir], [data-cfl-lista]");
  if (!b) return;
  e.preventDefault();
  if (b.dataset.cflLista !== undefined) { mostrarConflitos(); return; }
  const id = Number(b.dataset.cflAbrir);
  if (dialogoAberto && document.querySelector(".cfl-dialogo")) { dialogoAberto.fechar(null); setTimeout(() => abrirConflito(id), 60); return; }
  abrirConflito(id);
});
