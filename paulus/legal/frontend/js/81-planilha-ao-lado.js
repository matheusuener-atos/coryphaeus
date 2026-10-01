/* ------------------------------------- a planilha ao lado da conversa */
/*
   Pacote de telas de 01/10/2026 (docs/PLANO-TELAS-ASSISTENTE.md, T3):
   `Conversa - Planilha` e `Conversa - Editor de planilha`. A planilha do
   Acervo abre na coluna da direita como grade de verdade - letras das
   colunas, numeros das linhas, a barra da formula, as abas embaixo -, e nao
   como paginas desenhadas.

   Leitura: o .xlsx lido do disco (POST /api/biblioteca/planilha), com o valor
   calculado de cada celula e as linhas que a resposta citou marcadas; nada e
   gravado. Edicao: "Abrir editor" cria o rascunho (uma planilha do editor,
   POST /api/documentos/importar) e cada mudanca vai pelas rotas de sempre da
   planilha (/celula, /faixa, /ordenar, /estrutura). A celula que mudou fica
   verde, com o valor de antes riscado, e o "Alterações" conta. O .xlsx de
   origem nao e tocado - "Salvar na biblioteca" grava uma copia.
*/

const pa = {
  modo: "",          // "leitura" | "edicao"
  nome: "",          // o arquivo do Acervo
  id: 0,             // o rascunho (edicao)
  titulo: "",
  versao: 1,
  dados: null,       // { abas, calculado, citadas }
  aba: 0,
  celula: "A1",
  citada: 0,
  escala: 100,
  esconder: null,    // linhas escondidas pelo filtro (so a tela)
  destacar: null,    // linhas destacadas (so a tela)
  mudancas: {},      // "aba:ref" -> { antes } - o que mudou nesta sessao
  desfazer: [],
  refazer: [],
  oferta: null,
  ocupada: false,
  destino: "",       // "planilha" | "conversa" | "" (a regra decide)
};

const PA_ESCALAS = [75, 90, 100, 110, 125, 150];

function planilhaAoLadoAberta() {
  return Boolean(pa.modo && pa.dados && $("pa-grade") && papelDoLado() === "ferramenta");
}

function planilhaEmEdicao() {
  return planilhaAoLadoAberta() && pa.modo === "edicao";
}

/* ------------------------------------------------------------- abrir */

async function abrirPlanilhaAoLado(nome, o) {
  const opcoes = o || {};
  const r = await fetch("/api/biblioteca/planilha", {
    method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ nome: nome, trechos: opcoes.trechos || [] }),
  }).catch(() => null);
  if (!r || !r.ok) { avisoNaJanela("Não consegui abrir a planilha: " + (r ? await erroDe(r) : "sem resposta"), { icone: "error" }); return; }
  const d = await r.json();
  comecarPlanilha("leitura", { nome: nome, dados: d, oferta: opcoes.oferta });
  const c = (d.citadas || [])[0];
  if (c) { pa.aba = c.aba; pa.celula = "A" + c.linha; }
  desenharPlanilhaAoLado();
}

async function editarPlanilhaAoLado(id, o) {
  const opcoes = o || {};
  const r = await fetch("/api/planilha/" + id).catch(() => null);
  if (!r || !r.ok) { avisoNaJanela("Não consegui abrir a planilha: " + (r ? await erroDe(r) : "sem resposta"), { icone: "error" }); return; }
  const d = await r.json();
  comecarPlanilha("edicao", { nome: opcoes.nome || d.titulo + ".xlsx", dados: d, oferta: opcoes.oferta });
  pa.id = id;
  pa.titulo = d.titulo;
  pa.versao = d.versao || 1;
  desenharPlanilhaAoLado();
}

function comecarPlanilha(modo, o) {
  Object.assign(pa, {
    modo: modo, nome: o.nome, dados: o.dados, aba: 0, celula: "A1", citada: 0, escala: 100,
    esconder: null, destacar: null, mudancas: {}, desfazer: [], refazer: [], oferta: o.oferta || null, id: 0, destino: "",
  });
  definirFoco([o.nome]);
}

function desenharPlanilhaAoLado() {
  const edicao = pa.modo === "edicao";
  const abas = pa.dados.abas || [];
  const conta = contaDaAba();
  const citadas = (pa.dados.citadas || []).length;
  const linha = edicao
    ? "rascunho · versão " + pa.versao + " · o original não é alterado"
    : ["só leitura", plural(abas.length, "aba"), plural(conta.linhas > 1 ? conta.linhas - 1 : conta.linhas, "linha"),
      citadas ? plural(citadas, "linha citada", "linhas citadas") : ""].filter(Boolean).join(" · ");
  const acoes = edicao
    ? '<button class="primario" data-fl="guardar">Salvar na biblioteca</button>'
    : botaoNoWindows() + '<button class="primario" data-fl="editar">Abrir editor</button>';
  const html = '<div class="fl" data-fl-tipo="planilha">' +
    topoDaFerramenta({ nome: pa.nome, linhaHtml: '<small id="pa-linha">' + esc(linha) + "</small>", acoes: acoes }) +
    '<div class="fl-quadro">' +
    '<div class="fl-barra" id="pa-barra"></div>' +
    '<div class="pa-formula"><span class="pa-ref" id="pa-ref">A1</span><span class="pa-fx">fx</span>' +
    '<input type="text" id="pa-entrada" spellcheck="false" autocomplete="off"' + (edicao ? "" : " readonly") + ' aria-label="Conteúdo da célula"></div>' +
    '<div class="pa-mesa" id="pa-mesa"><div class="pa-grade" id="pa-grade"></div></div>' +
    '<div class="fl-pe pa-pe"><span class="visoes pa-abas" id="pa-abas"></span><span id="pa-conta"></span>' +
    '<span class="cresce"></span>' +
    (edicao ? '<span class="edl-selo" id="pa-selo">salvo no rascunho</span>' : '<span class="fl-pe-nota">o arquivo original não é alterado</span>') +
    '<span class="cresce"></span></div>' +
    "</div></div>";
  abrirNoLado("ferramenta", {
    chave: (edicao ? "planilha-editor:" : "planilha:") + pa.nome,
    html: html,
    ligar: ligarPlanilhaAoLado,
    aoFechar: () => {
      if (pa.oferta) marcarBotaoDaOferta(pa.oferta, "", pa.nome);
      const faixa = $("pa-atalhos");
      if (faixa) faixa.remove();
      pa.modo = "";
      pa.dados = null;
      atualizarPostura();
    },
  });
  if (pa.oferta) marcarBotaoDaOferta(pa.oferta, edicao ? "editar" : "exibir", pa.nome);
  desenharAtalhosDaPlanilha();
  atualizarPostura();
}

/* ------------------------------------------------------------- a grade */

function posDaRef(ref) {
  const m = /^([A-Z]{1,2})(\d{1,4})$/.exec(String(ref || "").toUpperCase());
  return m ? { l: Number(m[2]), c: letraParaIndice(m[1]) } : { l: 1, c: 0 };
}

/* O que a aba usa de verdade: a tabela, e nao a grade inteira. */
function contaDaAba() {
  const aba = (pa.dados.abas || [])[pa.aba];
  let linhas = 0;
  let colunas = 0;
  Object.keys((aba && aba.celulas) || {}).forEach((ref) => {
    const p = posDaRef(ref);
    linhas = Math.max(linhas, p.l);
    colunas = Math.max(colunas, p.c + 1);
  });
  return { linhas: linhas, colunas: colunas };
}

function classeDaCelula(v, cel, l) {
  const nomes = ["pa-cel"];
  const texto = v ? String(v.texto || "") : "";
  if (v && v.erro) nomes.push("ruim");
  else if (v && typeof v.bruto === "number") nomes.push("numero");
  else if (/^\d{2}\/\d{2}\/\d{4}$/.test(texto)) nomes.push("numero");
  else if (/^[\d][\d.\-/]{9,}$/.test(texto)) nomes.push("mono");
  if ((cel && cel.negrito) || (l === 1 && texto)) nomes.push("forte");
  if (cel && cel.italico) nomes.push("inclinada");
  const plano = texto.trim().toLowerCase();
  if (plano === "a pagar") nomes.push("pa-pagar");
  else if (plano === "a receber") nomes.push("pa-receber");
  return nomes.join(" ");
}

function desenharGradeAoLado() {
  const caixa = $("pa-grade");
  if (!caixa || !pa.dados) return;
  const aba = pa.dados.abas[pa.aba];
  const calc = (pa.dados.calculado || [])[pa.aba] || {};
  const conta = contaDaAba();
  const linhas = Math.max(conta.linhas + 6, 22);
  const colunas = Math.max(conta.colunas, 6);
  const citadas = new Set((pa.dados.citadas || []).filter((x) => x.aba === pa.aba).map((x) => x.linha));
  const atual = (pa.dados.citadas || [])[pa.citada];
  const escondidas = new Set(pa.esconder || []);
  const destacadas = new Set(pa.destacar || []);
  const sel = posDaRef(pa.celula);

  // A largura de cada coluna pelo texto mais longo dela (sem passar de 320).
  const larguras = [];
  for (let c = 0; c < colunas; c++) {
    let maior = 0;
    for (let l = 1; l <= conta.linhas; l++) {
      const v = calc[letraColuna(c) + l];
      if (v && v.texto) maior = Math.max(maior, String(v.texto).length);
    }
    larguras.push(Math.round(Math.max(96, Math.min(320, maior * 7.6 + 28))));
  }
  let html = '<table class="pa-tabela" style="--pa-escala:' + (pa.escala / 100) + '"><colgroup><col class="pa-col-num">' +
    larguras.map((w) => '<col style="width:' + Math.round(w * pa.escala / 100) + 'px">').join("") + "</colgroup>" +
    '<thead><tr><th class="pa-canto"></th>';
  for (let c = 0; c < colunas; c++) {
    html += '<th class="' + (c === sel.c ? "atual" : "") + '">' + letraColuna(c) + "</th>";
  }
  html += "</tr></thead><tbody>";
  for (let l = 1; l <= linhas; l++) {
    if (escondidas.has(l)) continue;
    const classes = [];
    if (citadas.has(l)) classes.push("citada");
    if (atual && atual.aba === pa.aba && atual.linha === l && pa.modo === "leitura") classes.push("atual");
    if (destacadas.has(l)) classes.push("destacada");
    if (l === conta.linhas && /^total/i.test(String((calc["A" + l] || {}).texto || ""))) classes.push("total");
    html += "<tr" + (classes.length ? ' class="' + classes.join(" ") + '"' : "") + ' data-pa-linha="' + l + '">' +
      '<th class="pa-num' + (l === sel.l ? " atual" : "") + '">' + l + "</th>";
    for (let c = 0; c < colunas; c++) {
      const ref = letraColuna(c) + l;
      const v = calc[ref];
      const cel = aba.celulas[ref];
      const mudou = pa.mudancas[pa.aba + ":" + ref];
      const classe = classeDaCelula(v, cel, l) + (ref === pa.celula ? " escolhida" : "") + (mudou ? " mudou" : "");
      html += '<td class="' + classe + '" data-ref="' + ref + '">' +
        (mudou && mudou.antes ? "<s>" + esc(mudou.antes) + "</s> " : "") + (v ? esc(v.texto) : "") + "</td>";
    }
    html += "</tr>";
  }
  caixa.innerHTML = html + "</tbody></table>";
  atualizarFormulaAoLado();
  const c = $("pa-conta");
  if (c) c.textContent = plural(conta.linhas > 1 ? conta.linhas - 1 : conta.linhas, "linha") + " · " + plural(conta.colunas, "coluna");
}

function atualizarFormulaAoLado() {
  const aba = pa.dados.abas[pa.aba];
  const cel = aba.celulas[pa.celula];
  const calc = (pa.dados.calculado || [])[pa.aba] || {};
  $("pa-ref").textContent = pa.celula;
  const entrada = $("pa-entrada");
  if (document.activeElement !== entrada) {
    entrada.value = cel ? cel.valor : "";
    if (pa.modo === "leitura" && cel && !String(cel.valor).startsWith("=")) entrada.value = (calc[pa.celula] || {}).texto || cel.valor;
  }
}

function desenharAbasAoLado() {
  const caixa = $("pa-abas");
  if (!caixa) return;
  caixa.innerHTML = (pa.dados.abas || []).map((a, i) =>
    '<button data-pa-aba="' + i + '"' + (i === pa.aba ? ' class="ativa"' : "") + ">" + esc(a.nome) + "</button>").join("");
  caixa.querySelectorAll("[data-pa-aba]").forEach((b) => {
    b.onclick = () => { pa.aba = Number(b.dataset.paAba); pa.celula = "A1"; pa.esconder = null; pa.destacar = null; desenharAbasAoLado(); desenharGradeAoLado(); };
  });
}

/* A barra do quadro. Na leitura, as linhas citadas ("1 de 2"), a lupa e o
   zoom; na edicao, a barra de edicao do desenho. */
function desenharBarraDaPlanilha() {
  const barra = $("pa-barra");
  if (!barra) return;
  const zoom = '<span class="divisa-v"></span><span class="fl-zoom"><button class="botao-icone" data-pa="menos" aria-label="Diminuir">' + ic("remove", 16) + "</button>" +
    '<span class="fl-mono">' + pa.escala + "%</span>" +
    '<button class="botao-icone" data-pa="mais" aria-label="Aumentar">' + ic("add", 16) + "</button></span>";
  if (pa.modo === "leitura") {
    const n = (pa.dados.citadas || []).length;
    barra.className = "fl-barra";
    barra.innerHTML = (n
      ? '<span class="fl-cit"><i class="fl-cor"></i>Linhas citadas</span><span class="fl-passo">' +
        '<button class="botao-icone" data-pa="antes" aria-label="Anterior"' + (n < 2 ? " disabled" : "") + ">" + ic("chevron_left", 16) + "</button>" +
        '<span class="fl-mono">' + (pa.citada + 1) + " de " + n + "</span>" +
        '<button class="botao-icone" data-pa="depois" aria-label="Próxima"' + (n < 2 ? " disabled" : "") + ">" + ic("chevron_right", 16) + "</button></span>"
      : '<span class="fl-cit fl-cit-vazio">Sem linha citada</span>') +
      '<span class="cresce"></span>' +
      '<label class="fl-busca pa-busca">' + ic("search", 16) + '<input type="text" id="pa-termo" placeholder="Procurar na planilha"></label>' + zoom;
  } else {
    const botao = (q, icone, titulo, texto) => '<button class="' + (texto ? "edl-texto" : "botao-icone") + '" data-pa="' + q + '" title="' + titulo + '" aria-label="' + titulo + '">' +
      (icone ? ic(icone, 18) : "") + (texto || "") + "</button>";
    const n = Object.keys(pa.mudancas).length;
    barra.className = "fl-barra edl-barra";
    barra.innerHTML = botao("desfazer", "undo", "Desfazer") + botao("refazer", "redo", "Refazer") + '<span class="divisa-v"></span>' +
      botao("negrito", "format_bold", "Negrito") + botao("italico", "format_italic", "Itálico") + '<span class="divisa-v"></span>' +
      botao("moeda", "", "Moeda", "R$") + botao("porcento", "", "Porcentagem", "%") + botao("numero", "", "Número com duas casas", ",00") +
      '<span class="divisa-v"></span>' +
      botao("somar", "", "Somar a coluna acima", "Σ Somar") + botao("ordenar", "", "Ordenar a tabela por esta coluna", "Ordenar") +
      botao("filtrar", "", "Mostrar só as linhas que casam", pa.esconder ? "Tirar filtro" : "Filtrar") + botao("linha", "", "Inserir linha abaixo", "+ Linha") +
      '<span class="cresce"></span>' +
      '<button class="edl-texto" data-pa="alteracoes" title="Ir até a alteração">Alterações <span class="edl-conta">' + n + "</span></button>";
  }
  ligarBarraDaPlanilha();
}

function ligarBarraDaPlanilha() {
  const barra = $("pa-barra");
  const clique = (q, fn) => { const b = barra.querySelector('[data-pa="' + q + '"]'); if (b) b.onclick = fn; };
  clique("antes", () => andarNasCitadas(-1));
  clique("depois", () => andarNasCitadas(1));
  clique("menos", () => zoomDaPlanilha(-1));
  clique("mais", () => zoomDaPlanilha(1));
  clique("desfazer", () => desfazerNaPlanilha(false));
  clique("refazer", () => desfazerNaPlanilha(true));
  clique("negrito", () => faixaNaPlanilha({ negrito: !(celulaAtual() || {}).negrito }));
  clique("italico", () => faixaNaPlanilha({ italico: !(celulaAtual() || {}).italico }));
  clique("moeda", () => faixaNaPlanilha({ formato: "moeda" }));
  clique("porcento", () => faixaNaPlanilha({ formato: "porcento" }));
  clique("numero", () => faixaNaPlanilha({ formato: "numero" }));
  clique("somar", somarNaPlanilha);
  clique("ordenar", () => ordenarPlanilha(letraColuna(posDaRef(pa.celula).c)));
  clique("filtrar", filtrarPlanilha);
  clique("linha", inserirLinhaNaPlanilha);
  clique("alteracoes", () => {
    const m = $("pa-grade").querySelector("td.mudou");
    if (m) m.scrollIntoView({ behavior: animacoesLigadas() ? "smooth" : "auto", block: "center", inline: "nearest" });
  });
  const termo = $("pa-termo");
  if (termo) termo.onkeydown = (e) => { if (e.key === "Enter") { e.preventDefault(); procurarNaPlanilha(termo.value); } };
}

function celulaAtual() {
  return pa.dados.abas[pa.aba].celulas[pa.celula];
}

function andarNasCitadas(passo) {
  const lista = pa.dados.citadas || [];
  if (!lista.length) return;
  pa.citada = (pa.citada + passo + lista.length) % lista.length;
  const c = lista[pa.citada];
  if (c.aba !== pa.aba) { pa.aba = c.aba; desenharAbasAoLado(); }
  pa.celula = "A" + c.linha;
  desenharBarraDaPlanilha();
  desenharGradeAoLado();
  rolarAteCelula();
}

function zoomDaPlanilha(passo) {
  const i = PA_ESCALAS.indexOf(pa.escala);
  pa.escala = PA_ESCALAS[Math.max(0, Math.min(PA_ESCALAS.length - 1, (i < 0 ? 2 : i) + passo))];
  desenharBarraDaPlanilha();
  desenharGradeAoLado();
}

function rolarAteCelula() {
  const td = $("pa-grade") && $("pa-grade").querySelector('[data-ref="' + pa.celula + '"]');
  if (td) td.scrollIntoView({ behavior: animacoesLigadas() ? "smooth" : "auto", block: "nearest", inline: "nearest" });
}

/* A lupa da leitura: a primeira celula que tem o termo, e as seguintes a
   cada Enter. */
function procurarNaPlanilha(termo) {
  const t = String(termo || "").trim().toLowerCase();
  if (!t) return;
  const calc = (pa.dados.calculado || [])[pa.aba] || {};
  const refs = Object.keys(calc).filter((ref) => String((calc[ref] || {}).texto || "").toLowerCase().includes(t))
    .sort((a, b) => { const x = posDaRef(a); const y = posDaRef(b); return x.l - y.l || x.c - y.c; });
  if (!refs.length) { avisoNaJanela("Não achei “" + termo + "” nesta aba"); return; }
  const depois = refs.find((ref) => { const p = posDaRef(ref); const s = posDaRef(pa.celula); return p.l > s.l || (p.l === s.l && p.c > s.c); });
  pa.celula = depois || refs[0];
  desenharGradeAoLado();
  rolarAteCelula();
}

/* ------------------------------------------------------------ ligar */

function ligarPlanilhaAoLado(raiz) {
  desenharBarraDaPlanilha();
  desenharAbasAoLado();
  desenharGradeAoLado();
  setTimeout(() => { if (pa.dados) rolarAteCelula(); }, LADO_DURA_MS + 40);

  const grade = $("pa-grade");
  grade.onclick = (e) => {
    const td = e.target.closest && e.target.closest("td[data-ref]");
    if (!td) return;
    pa.celula = td.dataset.ref;
    desenharGradeAoLado();
  };
  grade.ondblclick = (e) => {
    if (pa.modo !== "edicao") return;
    const td = e.target.closest && e.target.closest("td[data-ref]");
    if (!td) return;
    const entrada = $("pa-entrada");
    entrada.focus();
    entrada.select();
  };
  const entrada = $("pa-entrada");
  entrada.onkeydown = (e) => {
    if (pa.modo !== "edicao") return;
    if (e.key === "Enter") { e.preventDefault(); gravarCelulaAoLado(pa.celula, entrada.value, { mover: 1 }); entrada.blur(); }
    if (e.key === "Escape") { entrada.blur(); atualizarFormulaAoLado(); }
  };
  // Na edicao, escrever com a celula escolhida escreve nela (como no Excel).
  raiz.tabIndex = -1;
  raiz.onkeydown = (e) => {
    if (pa.modo !== "edicao" || e.target !== raiz && e.target.closest("input, select, textarea, [contenteditable]")) return;
    const p = posDaRef(pa.celula);
    const mover = { ArrowDown: [1, 0], ArrowUp: [-1, 0], ArrowRight: [0, 1], ArrowLeft: [0, -1] }[e.key];
    if (mover) {
      e.preventDefault();
      pa.celula = letraColuna(Math.max(0, p.c + mover[1])) + Math.max(1, p.l + mover[0]);
      desenharGradeAoLado();
      rolarAteCelula();
      return;
    }
    if (e.key === "Delete") { gravarCelulaAoLado(pa.celula, ""); return; }
    if (e.key.length === 1 && !e.ctrlKey && !e.metaKey && !e.altKey) {
      entrada.focus();
      entrada.value = "";
    }
  };
  grade.addEventListener("click", () => { if (pa.modo === "edicao") raiz.focus({ preventScroll: true }); });

  const acao = (q, fn) => { const b = raiz.querySelector('[data-fl="' + q + '"]'); if (b) b.onclick = () => fn(b); };
  acao("fechar", () => voltarAoContexto());
  acao("windows", async (b) => {
    b.disabled = true;
    const r = await fetch("/api/trabalhos/" + estado.trabalhoId + "/fazer", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ tipo: "abrir", campos: { nome: pa.nome } }),
    }).catch(() => null);
    b.disabled = false;
    if (!r || !r.ok) { avisoNaJanela("Não consegui abrir: " + (r ? await erroDe(r) : "sem resposta"), { icone: "error" }); return; }
    avisoNaJanela("Abri no programa padrão do Windows");
  });
  acao("editar", () => editarDocumentoDoAcervo(pa.nome, pa.oferta));
  acao("guardar", () => guardarNaBiblioteca(pa.id));
  acao("mais", (b) => menuNaLinha(b, pa.modo === "edicao" ? [
    { rotulo: "Baixar como Excel", acao: () => { window.location.href = "/api/planilha/" + pa.id + "/exportar?formato=xlsx"; } },
    { rotulo: "Abrir no Editor, em tela cheia", acao: () => { const id = pa.id; voltarAoContexto(); abrirDocumento(id); } },
  ] : [
    { rotulo: "Ver no Acervo", acao: () => verNoAcervo(pa.nome) },
  ]));
}

/* ------------------------------------------------------------ editar */

function respostaDaPlanilha(d) {
  pa.dados = Object.assign({}, pa.dados, { abas: d.abas, calculado: d.calculado });
  if (d.versao) pa.versao = d.versao;
}

function seloDaPlanilha(texto, tom) {
  const selo = $("pa-selo");
  if (!selo) return;
  selo.textContent = texto;
  selo.classList.toggle("sujo", tom === "sujo");
  selo.classList.toggle("erro", tom === "erro");
}

async function gravarCelulaAoLado(ref, valor, o) {
  const opcoes = o || {};
  if (pa.modo !== "edicao" || pa.ocupada) return false;
  const aba = pa.aba;
  const antesCru = ((pa.dados.abas[aba].celulas[ref]) || {}).valor || "";
  if (antesCru === valor) { if (opcoes.mover) moverSelecao(opcoes.mover); return true; }
  const antesTexto = (((pa.dados.calculado || [])[aba] || {})[ref] || {}).texto || "";
  pa.ocupada = true;
  seloDaPlanilha("salvando…", "sujo");
  const r = await fetch("/api/planilha/" + pa.id + "/celula", {
    method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ aba: aba, ref: ref, dados: { valor: valor } }),
  }).catch(() => null);
  pa.ocupada = false;
  if (!r || !r.ok) { seloDaPlanilha("não consegui salvar", "erro"); avisoNaJanela("Não consegui gravar " + ref + ": " + (r ? await erroDe(r) : "sem resposta"), { icone: "error" }); return false; }
  respostaDaPlanilha(await r.json());
  const chave = aba + ":" + ref;
  if (!opcoes.desfazendo) {
    pa.desfazer.push({ aba: aba, ref: ref, antes: antesCru, depois: valor });
    pa.refazer = [];
  }
  if (!pa.mudancas[chave]) pa.mudancas[chave] = { antes: antesTexto };
  else if ((((pa.dados.calculado || [])[aba] || {})[ref] || {}).texto === pa.mudancas[chave].antes) delete pa.mudancas[chave];
  seloDaPlanilha("salvo no rascunho às " + new Date().toTimeString().slice(0, 5), "");
  if ($("pa-linha")) $("pa-linha").textContent = "rascunho · versão " + pa.versao + " · o original não é alterado";
  if (opcoes.mover) moverSelecao(opcoes.mover); else desenharGradeAoLado();
  desenharBarraDaPlanilha();
  return true;
}

function moverSelecao(linhas) {
  const p = posDaRef(pa.celula);
  pa.celula = letraColuna(p.c) + Math.max(1, p.l + linhas);
  desenharGradeAoLado();
  rolarAteCelula();
}

async function desfazerNaPlanilha(refazer) {
  const de = refazer ? pa.refazer : pa.desfazer;
  const item = de.pop();
  if (!item) return;
  pa.aba = item.aba;
  pa.celula = item.ref;
  const ok = await gravarCelulaAoLado(item.ref, refazer ? item.depois : item.antes, { desfazendo: true });
  if (ok) (refazer ? pa.desfazer : pa.refazer).push(item);
  else de.push(item);
}

async function faixaNaPlanilha(dados) {
  if (pa.modo !== "edicao") return;
  const r = await fetch("/api/planilha/" + pa.id + "/faixa", {
    method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify(Object.assign({ aba: pa.aba, faixa: pa.celula }, dados)),
  }).catch(() => null);
  if (!r || !r.ok) { avisoNaJanela("Não consegui: " + (r ? await erroDe(r) : "sem resposta"), { icone: "error" }); return; }
  respostaDaPlanilha(await r.json());
  seloDaPlanilha("salvo no rascunho às " + new Date().toTimeString().slice(0, 5), "");
  desenharGradeAoLado();
}

/* Σ Somar: a soma dos numeros logo acima da celula escolhida. */
function somarNaPlanilha() {
  const p = posDaRef(pa.celula);
  const calc = (pa.dados.calculado || [])[pa.aba] || {};
  const letra = letraColuna(p.c);
  let fim = p.l - 1;
  while (fim >= 1 && typeof (calc[letra + fim] || {}).bruto !== "number") fim -= 1;
  let ini = fim;
  while (ini - 1 >= 1 && typeof (calc[letra + (ini - 1)] || {}).bruto === "number") ini -= 1;
  if (fim < 1) { avisoNaJanela("Não há números acima de " + pa.celula + " para somar"); return; }
  gravarCelulaAoLado(pa.celula, "=SOMA(" + letra + ini + ":" + letra + fim + ")");
}

/* A tabela vai da linha 1 ate a ultima com dado; a linha de Total fica de
   fora - ordenar a poria no meio. */
function faixaDaTabela() {
  const conta = contaDaAba();
  const calc = (pa.dados.calculado || [])[pa.aba] || {};
  let ultima = conta.linhas;
  if (/^total/i.test(String((calc["A" + ultima] || {}).texto || ""))) ultima -= 1;
  return { faixa: "A1:" + letraColuna(Math.max(0, conta.colunas - 1)) + ultima, ultima: ultima };
}

async function ordenarPlanilha(coluna) {
  if (pa.modo !== "edicao") return;
  const t = faixaDaTabela();
  const r = await fetch("/api/planilha/" + pa.id + "/ordenar", {
    method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ aba: pa.aba, faixa: t.faixa, coluna: coluna, crescente: true, com_cabecalho: true }),
  }).catch(() => null);
  if (!r || !r.ok) { avisoNaJanela("Não consegui ordenar: " + (r ? await erroDe(r) : "sem resposta"), { icone: "error" }); return null; }
  const d = await r.json();
  respostaDaPlanilha(d);
  // Ordenar mexe na tabela inteira: as marcas de celula mudada nao valem mais.
  pa.mudancas = {};
  pa.desfazer = [];
  pa.refazer = [];
  seloDaPlanilha("salvo no rascunho às " + new Date().toTimeString().slice(0, 5), "");
  desenharBarraDaPlanilha();
  desenharGradeAoLado();
  return d;
}

async function filtrarPlanilha() {
  if (pa.esconder) { pa.esconder = null; desenharBarraDaPlanilha(); desenharGradeAoLado(); return; }
  const letra = letraColuna(posDaRef(pa.celula).c);
  const criterio = await perguntar({ titulo: "Filtrar pela coluna " + letra, contexto: "Planilha",
    campo: { rotulo: "Mostrar só o que", placeholder: 'ex.: a pagar, >1000, <>0', icone: "filter_list" }, confirmar: "Filtrar" });
  if (!criterio) return;
  const r = await fetch("/api/planilha/" + pa.id + "/filtrar", {
    method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ aba: pa.aba, faixa: faixaDaTabela().faixa, coluna: letra, criterio: criterio, com_cabecalho: true }),
  }).catch(() => null);
  if (!r || !r.ok) { avisoNaJanela("Não consegui filtrar: " + (r ? await erroDe(r) : "sem resposta"), { icone: "error" }); return; }
  const d = await r.json();
  pa.esconder = d.esconder || [];
  avisoNaJanela("Mostrando " + d.mostrando + " de " + d.de + " linhas · o filtro é só da tela");
  desenharBarraDaPlanilha();
  desenharGradeAoLado();
}

async function inserirLinhaNaPlanilha() {
  const p = posDaRef(pa.celula);
  const r = await fetch("/api/planilha/" + pa.id + "/estrutura", {
    method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ aba: pa.aba, eixo: "linhas", acao: "inserir", em: p.l + 1, quantas: 1 }),
  }).catch(() => null);
  if (!r || !r.ok) { avisoNaJanela("Não consegui inserir a linha: " + (r ? await erroDe(r) : "sem resposta"), { icone: "error" }); return; }
  respostaDaPlanilha(await r.json());
  pa.mudancas = {};
  pa.celula = "A" + (p.l + 1);
  desenharBarraDaPlanilha();
  desenharGradeAoLado();
}

/* --------------------------------------------- a caixa com a planilha aberta */

const ATALHOS_DA_PLANILHA = [
  ["Somar a receber", "somar"], ["Ordenar por vencimento", "ordenar"], ["Destacar atrasados", "atrasados"],
];

function desenharAtalhosDaPlanilha() {
  const velha = $("pa-atalhos");
  if (velha) velha.remove();
  if (pa.modo !== "edicao") return;
  const faixa = document.createElement("div");
  faixa.id = "pa-atalhos";
  faixa.className = "edl-atalhos pa-atalhos";
  faixa.innerHTML = '<div class="visoes edl-destino" role="group" aria-label="Para onde vai o pedido">' +
    '<button data-pa-destino="planilha" title="O pedido muda a planilha aberta ao lado">' + ic("table", 16) + "Na planilha</button>" +
    '<button data-pa-destino="conversa" title="O pedido é uma pergunta para a conversa">' + ic("forum", 16) + "Na conversa</button></div>" +
    ATALHOS_DA_PLANILHA.map((a) => '<button class="edl-atalho" data-pa-atalho="' + a[1] + '">' + esc(a[0]) + "</button>").join("");
  $("cartao-campo").before(faixa);
  faixa.querySelectorAll("[data-pa-destino]").forEach((b) => {
    b.onclick = () => { pa.destino = pa.destino === b.dataset.paDestino ? "" : b.dataset.paDestino; atualizarDestinoDaPlanilha(); $("pedido").focus(); };
  });
  faixa.querySelectorAll("[data-pa-atalho]").forEach((b) => { b.onclick = () => atalhoDaPlanilha(b.dataset.paAtalho); });
  atualizarDestinoDaPlanilha();
}

function destinoNaPlanilha(texto) {
  if (pa.destino) return pa.destino;
  const plano = String(texto || "").normalize("NFD").replace(/[̀-ͯ]/g, "").toLowerCase();
  if (!plano.trim()) return "planilha";
  return RE_PEDIDO_DE_MUDANCA.test(plano) || /^\s*(marqu?e|some|soma|calcul[ae]|ordene|ordena|destaqu?e)\b/.test(plano) ? "planilha" : "conversa";
}

function atualizarDestinoDaPlanilha() {
  const faixa = $("pa-atalhos");
  if (!faixa) return;
  const alvo = destinoNaPlanilha($("pedido").value);
  faixa.querySelectorAll("[data-pa-destino]").forEach((b) => b.classList.toggle("ativa", b.dataset.paDestino === alvo));
}

$("pedido").addEventListener("input", atualizarDestinoDaPlanilha);

/* A coluna cujo cabecalho (linha 1) tem a palavra. */
function colunaDoCabecalho(palavra) {
  const calc = (pa.dados.calculado || [])[pa.aba] || {};
  const conta = contaDaAba();
  for (let c = 0; c < conta.colunas; c++) {
    const t = String((calc[letraColuna(c) + 1] || {}).texto || "").normalize("NFD").replace(/[̀-ͯ]/g, "").toLowerCase();
    if (t.includes(palavra)) return letraColuna(c);
  }
  return "";
}

async function atalhoDaPlanilha(qual) {
  if (qual === "ordenar") {
    const col = colunaDoCabecalho("vencimento");
    if (!col) { avisoNaJanela("Não achei a coluna de vencimento na linha 1"); return; }
    if (await ordenarPlanilha(col)) notaDeFeitoNaConversa("Ordenei a planilha pela coluna " + col + " (vencimento). A linha de total ficou no lugar.");
    return;
  }
  if (qual === "atrasados") {
    // Destaque so da tela: a planilha do editor nao guarda cor de fundo.
    const col = colunaDoCabecalho("vencimento");
    if (!col) { avisoNaJanela("Não achei a coluna de vencimento na linha 1"); return; }
    const calc = (pa.dados.calculado || [])[pa.aba] || {};
    const hoje = new Date(); hoje.setHours(0, 0, 0, 0);
    const pagos = colunaDoCabecalho("situa");
    pa.destacar = [];
    for (let l = 2; l <= contaDaAba().linhas; l++) {
      const m = /^(\d{2})\/(\d{2})\/(\d{4})$/.exec(String((calc[col + l] || {}).texto || ""));
      if (!m) continue;
      const quando = new Date(Number(m[3]), Number(m[2]) - 1, Number(m[1]));
      const situacao = pagos ? String((calc[pagos + l] || {}).texto || "").toLowerCase() : "";
      if (quando < hoje && !/pago|recebido|quitad/.test(situacao)) pa.destacar.push(l);
    }
    desenharGradeAoLado();
    notaDeFeitoNaConversa(pa.destacar.length
      ? "Destaquei " + plural(pa.destacar.length, "linha vencida", "linhas vencidas") + " e não pagas. O destaque é só da tela: o arquivo não guarda a cor."
      : "Nenhuma linha vencida e não paga nesta aba.");
    return;
  }
  if (qual === "somar") pedirNaPlanilha("Somar o valor das linhas a receber");
}

/* O pedido "na planilha": o modelo escreve a FORMULA (POST /assistente) e o
   motor da planilha calcula - um erro do modelo vira #NOME? numa celula, e
   nao numero errado. A formula entra na celula escolhida, se estiver vazia,
   ou na primeira vazia abaixo da tabela; Desfazer volta. */
async function pedirNaPlanilha(pedido) {
  if (!planilhaEmEdicao() || pa.ocupada) return;
  const centro = $("centro");
  centro.insertAdjacentHTML("beforeend", bolhaPessoa(pedido));
  const resposta = document.createElement("div");
  resposta.className = "resposta";
  resposta.innerHTML = '<div class="texto">Escrevendo a fórmula…</div>';
  centro.appendChild(resposta);
  rolar();
  const r = await fetch("/api/planilha/" + pa.id + "/assistente", {
    method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ pedido: pedido }),
  }).catch(() => null);
  if (!r || !r.ok) { resposta.innerHTML = '<div class="texto">Não consegui: ' + esc(r ? await erroDe(r) : "sem resposta") + "</div>"; return; }
  const d = await r.json();
  let alvo = pa.celula;
  if (celulaAtual() && celulaAtual().valor) {
    const t = faixaDaTabela();
    const p = posDaRef(pa.celula);
    alvo = letraColuna(p.c) + (contaDaAba().linhas + 2 > t.ultima ? contaDaAba().linhas + 2 : t.ultima + 2);
  }
  pa.celula = alvo;
  const ok = await gravarCelulaAoLado(alvo, d.formula);
  resposta.innerHTML = ok
    ? '<div class="texto">Escrevi <code>' + esc(d.formula) + "</code> em " + esc(alvo) + (d.erro ? " — deu " + esc(d.resultado) + ", confira." : ", que dá " + esc(d.resultado) + ".") +
      " " + esc(d.aviso || "") + '</div><div class="linha-form"><button data-pa-desfazer="1">Desfazer</button></div>'
    : '<div class="texto">A fórmula saiu (<code>' + esc(d.formula) + "</code>), mas não consegui gravar na planilha.</div>";
  const b = resposta.querySelector("[data-pa-desfazer]");
  if (b) b.onclick = () => { desfazerNaPlanilha(false); resposta.querySelector(".linha-form").remove(); };
  rolar();
}
