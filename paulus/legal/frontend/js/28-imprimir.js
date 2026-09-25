/* ------------------------------------------------------------ imprimir */
/*
   O dialogo de imprimir do PAULUS, no lugar do do navegador: a folha de
   verdade (o PDF desenhado) a esquerda, e a direita impressora, copias,
   paginas, cor e frente e verso. O PDF vai direto para o spooler do Windows
   (src/impressao.py). Quem preferir a janela do Windows tem o link no canto.
*/

const imp = { id: null, pagina: 1, total: 1, lista: [] };

async function abrirImprimir(id, titulo, paginaAtual, total) {
  imp.id = id;
  imp.total = Math.max(1, total || 1);
  imp.pagina = Math.min(Math.max(1, paginaAtual || 1), imp.total);

  let dados = { disponivel: false, impressoras: [] };
  try { dados = await (await fetch("/api/impressoras")).json(); } catch (err) { /* cai no Windows abaixo */ }
  imp.lista = dados.impressoras || [];
  if (!dados.disponivel || !imp.lista.length) {
    const ok = await confirmar({
      titulo: "Nenhuma impressora encontrada", contexto: "Imprimir",
      texto: "Não achei impressora instalada nesta conta do Windows. Posso abrir o PDF para você imprimir pela janela do sistema.",
      confirmar: "Abrir o PDF",
    });
    if (ok) imprimirPeloWindows(id);
    return;
  }

  const opcoes = imp.lista.map((x, i) =>
    '<option value="' + i + '"' + (x.padrao ? " selected" : "") + ">" + esc(x.nome) + (x.padrao ? " (padrão)" : "") + "</option>").join("");
  const html = '<div class="imp">' +
    '<div class="imp-previa"><div class="imp-folha"><img id="imp-img" alt=""></div>' +
    '<div class="imp-andar"><button type="button" class="botao-icone" data-imp-andar="-1" aria-label="Página anterior">' + ic("chevron_left", 18) + "</button>" +
    '<span id="imp-num"></span><button type="button" class="botao-icone" data-imp-andar="1" aria-label="Próxima página">' + ic("chevron_right", 18) + "</button></div></div>" +
    '<div class="imp-campos">' +
    '<label class="imp-rotulo" for="imp-impressora">Impressora</label><select id="imp-impressora">' + opcoes + "</select>" +
    '<small class="imp-dica" id="imp-dica"></small>' +
    '<label class="imp-rotulo" for="imp-copias">Cópias</label>' +
    '<div class="imp-copias"><button type="button" class="botao-icone" data-imp-copias="-1" aria-label="Menos">' + ic("remove", 18) + "</button>" +
    '<input type="text" id="imp-copias" value="1" inputmode="numeric" maxlength="2"><button type="button" class="botao-icone" data-imp-copias="1" aria-label="Mais">' + ic("add", 18) + "</button></div>" +
    '<span class="imp-rotulo">Páginas</span><div class="imp-paginas">' +
    '<label><input type="radio" name="imp-quais" value="todas" checked><span>Todas <small>(' + plural(imp.total, "página") + ")</small></span></label>" +
    '<label><input type="radio" name="imp-quais" value="esta"><span>Só a página <b id="imp-esta"></b></span></label>' +
    '<label class="imp-intervalo"><input type="radio" name="imp-quais" value="intervalo"><span>Intervalo</span>' +
    '<input type="text" id="imp-intervalo" placeholder="ex. 1-3, 5"></label></div>' +
    '<label class="imp-rotulo" for="imp-cor">Cor</label><select id="imp-cor"><option value="1">Colorida</option><option value="0">Preto e branco</option></select>' +
    '<label class="imp-chave"><input type="checkbox" id="imp-duplex"><span>Frente e verso</span></label>' +
    '<p class="imp-erro" id="imp-erro" hidden></p>' +
    "</div></div>";

  dialogo({
    titulo: "Imprimir", contexto: titulo || "Documento", classe: "dialogo-imprimir", html: html,
    confirmar: "Imprimir", aoConfirmar: enviarParaImpressora,
    rodape: '<button type="button" class="docs-ligacao imp-windows" id="imp-windows">' + ic("open_in_new", 16) + "Usar a janela do Windows</button>",
  });
  $("dialogo-titulo").closest(".dialogo").querySelectorAll("select").forEach(melhorarSelect);
  $("imp-windows").onclick = () => { if (dialogoAberto) dialogoAberto.fechar(null); imprimirPeloWindows(id); };
  document.querySelectorAll("[data-imp-andar]").forEach((b) => {
    b.onclick = () => { imp.pagina = Math.min(Math.max(1, imp.pagina + Number(b.dataset.impAndar)), imp.total); mostrarFolhaDaImpressao(); };
  });
  document.querySelectorAll("[data-imp-copias]").forEach((b) => {
    b.onclick = () => { const c = $("imp-copias"); c.value = Math.min(99, Math.max(1, (parseInt(c.value, 10) || 1) + Number(b.dataset.impCopias))); };
  });
  $("imp-intervalo").onfocus = () => { document.querySelector('input[name="imp-quais"][value="intervalo"]').checked = true; };
  $("imp-impressora").onchange = dicaDaImpressora;
  dicaDaImpressora();
  mostrarFolhaDaImpressao();
}

function mostrarFolhaDaImpressao() {
  $("imp-img").src = "/api/documentos/" + imp.id + "/pagina?numero=" + imp.pagina + "&largura=520";
  $("imp-num").textContent = "Página " + imp.pagina + " de " + imp.total;
  $("imp-esta").textContent = imp.pagina;
}

function dicaDaImpressora() {
  const x = imp.lista[Number($("imp-impressora").value)] || {};
  $("imp-dica").textContent = x.arquivo
    ? "Esta não imprime em papel: o Windows vai perguntar onde salvar o arquivo."
    : (x.rede ? "Impressora de rede." : "");
}

async function enviarParaImpressora() {
  const x = imp.lista[Number($("imp-impressora").value)];
  const quais = document.querySelector('input[name="imp-quais"]:checked').value;
  const paginas = quais === "todas" ? "todas" : (quais === "esta" ? String(imp.pagina) : $("imp-intervalo").value.trim());
  const erro = $("imp-erro");
  const botao = document.querySelector('.dialogo-imprimir [data-dialogo="confirmar"]');
  erro.hidden = true;
  if (quais === "intervalo" && !paginas) { erro.textContent = "Diga quais páginas — ex. 1-3, 5."; erro.hidden = false; $("imp-intervalo").focus(); return; }
  botao.disabled = true;
  botao.textContent = "Enviando…";
  try {
    const r = await fetch("/api/documentos/" + imp.id + "/imprimir", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        impressora: x.nome, paginas: paginas, copias: parseInt($("imp-copias").value, 10) || 1,
        cor: $("imp-cor").value === "1", frente_verso: $("imp-duplex").checked,
      }),
    });
    if (!r.ok) throw new Error(await erroDe(r));
    const d = await r.json();
    if (dialogoAberto) dialogoAberto.fechar({ ok: true });
    avisoCert(plural(d.folhas, "página") + (d.copias > 1 ? " × " + d.copias + " cópias" : "") + " enviada" + (d.folhas > 1 ? "s" : "") + " para " + d.impressora);
  } catch (err) {
    erro.textContent = String(err.message || err);
    erro.hidden = false;
    botao.disabled = false;
    botao.textContent = "Imprimir";
  }
}

function imprimirPeloWindows(id) {
  const janela = window.open("/api/documentos/" + id + "/pdf", "_blank");
  if (!janela) avisoCert("o navegador bloqueou a janela de impressão");
}
