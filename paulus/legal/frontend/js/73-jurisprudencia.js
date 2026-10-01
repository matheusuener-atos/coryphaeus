/* ------------------------------------------ jurisprudência do STJ (N13) */
/*
   Biblioteca › Jurisprudência (src/jurisprudencia.py): os acórdãos do STJ
   (espelhos de acórdãos, Portal de Dados Abertos, CC-BY) baixados só quando a
   pessoa escolhe os órgãos julgadores e pede - na janela do escritório. A
   busca é por palavras, no computador, sem modelo; o resultado é a ementa
   oficial, com a citação pronta e o link para o processo no STJ.
*/

const jur = { estado: null, achados: null, termo: "", orgao: "", vigia: null, escolhidos: null, abertos: new Set() };

async function carregarJurisprudencia() {
  try { jur.estado = await (await fetch("/api/jurisprudencia")).json(); } catch (err) { jur.estado = null; }
  if (jur.escolhidos === null) {
    const salvos = (jur.estado && jur.estado.escolhidos) || [];
    jur.escolhidos = new Set(salvos.length ? salvos : ["segunda-secao", "terceira-turma", "quarta-turma"]);
  }
}

function marcarTrecho(t) {
  return esc(t || "").replace(/\[/g, "<mark>").replace(/\]/g, "</mark>");
}

function cartaoDoAcordao(a) {
  const aberto = jur.abertos.has(a.id);
  return '<div class="jur-acordao" data-jur-id="' + esc(a.id) + '"><div class="jur-cab"><b>' + esc(a.classe + " " + a.processo) + "</b>" +
    "<small>" + esc([a.orgao, "rel. Min. " + a.relator, "julgado em " + String(a.data_decisao || "").split("-").reverse().join("/")].filter(Boolean).join(" · ")) + "</small></div>" +
    (aberto ? '<p class="jur-ementa">' + esc(a.ementa).replace(/\n/g, "<br>") + "</p>" + (a.tese ? '<p class="jur-tese"><b>Tese:</b> ' + esc(a.tese) + "</p>" : "")
      : '<p class="jur-trecho">' + (a.trecho ? marcarTrecho(a.trecho) : esc(String(a.ementa || "").slice(0, 320)) + "…") + "</p>") +
    '<div class="jur-pe"><button type="button" data-jur-abrir="' + esc(a.id) + '">' + (aberto ? "Fechar a ementa" : "Ver a ementa") + "</button>" +
    '<button type="button" data-jur-copiar="' + esc(a.id) + '">' + ic("content_copy", 15) + "Copiar a citação</button>" +
    '<button type="button" data-bib-abrir-fora="' + esc(a.link) + '">' + ic("open_in_new", 15) + "No STJ</button></div></div>";
}

function abaJurisprudenciaBib() {
  const e = jur.estado || { total: 0, orgaos: [], andamento: {} };
  const local = typeof acessoDeFora === "undefined" || acessoDeFora.local;
  const and = e.andamento || {};
  const baixando = Boolean(and.baixando);
  const orgaos = (e.orgaos || []).map((o) => '<label class="jur-orgao"><input type="checkbox" data-jur-orgao="' + esc(o.slug) + '"' +
    (jur.escolhidos && jur.escolhidos.has(o.slug) ? " checked" : "") + (baixando ? " disabled" : "") + ">" +
    '<span class="duas-linhas"><b>' + esc(o.nome) + "</b><small>" + esc(o.ramo + " · ~" + o.download_mb + " MB para baixar" +
      (o.acordaos ? " · " + milhar(o.acordaos) + " acórdãos aqui" : "")) + "</small></span></label>").join("");
  const progresso = baixando
    ? '<p class="jur-andamento">' + ic("download", 16) + " Baixando " + esc(and.orgao || "") + (and.arquivo ? " · " + esc(and.arquivo) : "") +
      " · " + (and.feitos || 0) + " de " + (and.total || "?") + " arquivos · " + milhar(and.novos || 0) + " acórdãos novos</p>"
    : (and.erro ? '<p class="acesso-erro">' + esc(and.erro) + "</p>" : "") +
      ((and.com_defeito || []).length ? '<p class="cfg-explica">' + plural(and.com_defeito.length, "arquivo do STJ veio com defeito", "arquivos do STJ vieram com defeito") +
        " e ficou de fora (tento de novo no próximo “Atualizar”): " + esc(and.com_defeito.slice(0, 3).join("; ")) + "</p>" : "");
  const painel = local
    ? '<section class="sv-secao jur-secao jur-painel"><div class="sv-secao-cabeca"><span class="sv-secao-titulo">' + ic("library_books", 16) + "No computador</span></div>" +
      '<p class="cfg-explica">' + (e.total ? milhar(e.total) + " acórdãos guardados" + (e.tamanho_mb >= 1 ? " (" + Math.round(e.tamanho_mb) + " MB)" : "") + (e.atualizado_em ? ", atualizados em " +
        e.atualizado_em.slice(0, 10).split("-").reverse().join("/") : "") + ". " : "Nada baixado ainda. ") +
      "Escolha os órgãos julgadores: só o pedido dos arquivos públicos sai deste computador, para o portal de dados abertos do STJ — nenhum dado do escritório. " +
      "Atualizar baixa só os meses novos.</p><div class=\"jur-orgaos\">" + orgaos + "</div>" + progresso +
      '<div class="cfg-botoes">' + (baixando ? '<button data-jur-parar="1">' + ic("stop", 16) + "Parar</button>"
        : '<button class="primario com-icone" data-jur-baixar="1">' + ic("download", 16) + (e.total ? "Baixar e atualizar" : "Baixar os escolhidos") + "</button>" +
          (e.total ? '<button class="perigo" data-jur-apagar="1">' + ic("delete", 16) + "Apagar tudo</button>" : "")) + "</div>" +
      '<p class="cfg-explica jur-licenca">' + esc(e.licenca || "") + "</p></section>"
    : "";
  const opcoes = '<option value="">todos os órgãos</option>' + (e.orgaos || []).filter((o) => o.acordaos).map((o) =>
    '<option value="' + esc(o.slug) + '"' + (jur.orgao === o.slug ? " selected" : "") + ">" + esc(o.nome) + "</option>").join("");
  const parcial = (jur.achados || []).length && jur.achados.every((a) => a.todas === false)
    ? '<p class="cfg-explica">Nenhum acórdão tem todas as palavras; estes têm parte delas.</p>' : "";
  const lista = jur.achados === null ? "" : (jur.achados.length ? parcial + '<div class="jur-lista">' + jur.achados.map(cartaoDoAcordao).join("") + "</div>"
    : '<p class="cfg-explica">Nenhum acórdão com essas palavras nos que estão neste computador.</p>');
  const busca = e.total
    ? '<section class="sv-secao jur-secao"><div class="sv-secao-cabeca"><span class="sv-secao-titulo">' + ic("search", 16) + "Procurar</span></div>" +
      '<div class="jur-busca"><input type="text" id="jur-termo" placeholder="multa moratória locação" value="' + esc(jur.termo) + '">' +
      '<select id="jur-orgao">' + opcoes + '</select><button class="primario" data-jur-procurar="1">Procurar</button></div>' +
      '<p class="cfg-explica">Por palavras, na ementa, na tese e nas informações complementares, sem modelo. A ementa é a oficial; confira o inteiro teor no STJ antes de citar.</p>' +
      lista + "</section>"
    : "";
  return aberturaBib("Jurisprudência do STJ", "Os acórdãos do STJ guardados neste computador, para procurar sem internet e para ligar aos artigos que eles citam.") +
    painel + busca;
}

async function procurarJurisprudencia() {
  const termo = ($("jur-termo") || {}).value || "";
  jur.termo = termo;
  jur.orgao = ($("jur-orgao") || {}).value || "";
  try {
    const d = await (await fetch("/api/jurisprudencia/procurar?termo=" + encodeURIComponent(termo) + "&orgao=" + encodeURIComponent(jur.orgao))).json();
    jur.achados = d.acordaos || [];
  } catch (err) { jur.achados = []; }
  desenharBib();
}

function vigiarJurisprudencia() {
  clearTimeout(jur.vigia);
  if (!(jur.estado && jur.estado.andamento && jur.estado.andamento.baixando)) return;
  jur.vigia = setTimeout(async () => {
    if (bibc.aba !== "jurisprudencia" || !$("bib-tela")) return;
    await carregarJurisprudencia();
    desenharBib();
  }, 1500);
}

function ligarJurisprudenciaBib() {
  const raiz = $("bib-tela");
  if (!raiz) return;
  raiz.querySelectorAll("[data-jur-orgao]").forEach((el) => { el.onchange = () => { if (el.checked) jur.escolhidos.add(el.dataset.jurOrgao); else jur.escolhidos.delete(el.dataset.jurOrgao); }; });
  const baixar = raiz.querySelector("[data-jur-baixar]");
  if (baixar) baixar.onclick = async () => {
    const orgaos = [...(jur.escolhidos || [])];
    const r = await fetch("/api/jurisprudencia/baixar", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ orgaos: orgaos }) });
    if (!r.ok) { avisoCert(await erroDe(r), { tom: "erro" }); return; }
    jur.estado = await r.json();
    desenharBib();
  };
  const parar = raiz.querySelector("[data-jur-parar]");
  if (parar) parar.onclick = async () => { await fetch("/api/jurisprudencia/parar", { method: "POST" }); await carregarJurisprudencia(); desenharBib(); };
  const apagar = raiz.querySelector("[data-jur-apagar]");
  if (apagar) apagar.onclick = async () => {
    if (!(await confirmar({ titulo: "Apagar a jurisprudência baixada?", contexto: "Biblioteca", texto: "Os acórdãos saem deste computador; dá para baixar de novo.", confirmar: "Apagar", perigo: true }))) return;
    const r = await fetch("/api/jurisprudencia", { method: "DELETE" });
    if (!r.ok) { avisoCert(await erroDe(r), { tom: "erro" }); return; }
    jur.estado = await r.json();
    jur.achados = null;
    desenharBib();
  };
  const procurar = raiz.querySelector("[data-jur-procurar]");
  if (procurar) procurar.onclick = procurarJurisprudencia;
  const termo = $("jur-termo");
  if (termo) termo.onkeydown = (ev) => { if (ev.key === "Enter") { ev.preventDefault(); procurarJurisprudencia(); } };
  raiz.querySelectorAll("[data-jur-abrir]").forEach((b) => { b.onclick = () => { const id = b.dataset.jurAbrir; if (jur.abertos.has(id)) jur.abertos.delete(id); else jur.abertos.add(id); desenharBib(); }; });
  raiz.querySelectorAll("[data-jur-copiar]").forEach((b) => { b.onclick = () => { const a = (jur.achados || []).find((x) => x.id === b.dataset.jurCopiar); if (a) copiarTexto(a.citacao, "citação copiada"); }; });
  raiz.querySelectorAll("[data-bib-abrir-fora]").forEach((b) => { b.onclick = () => window.open(b.dataset.bibAbrirFora, "_blank"); });
  vigiarJurisprudencia();
}
