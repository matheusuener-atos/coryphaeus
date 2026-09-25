/* ------------------------------------------- planilha: o jeito do Excel */
/*
   A grade da planilha (C3) com o que quem usa Excel procura sem pensar:

   - a grade cresce enquanto a pessoa rola, e encolhe de volta quando ela
     volta, se o que sobrou no fim estiver vazio. Linha e coluna vazias nao
     vao para o documento - sao so a tela;
   - botao direito na celula, na letra da coluna e no numero da linha, com o
     menu do Excel (recortar, copiar, colar, inserir, excluir, classificar,
     filtrar, formatar, largura, ocultar, mesclar, congelar, comentario);
   - arrastar a borda do cabecalho muda a largura/altura; clique duplo
     ajusta ao conteudo;
   - a alca no canto da selecao (cursor em cruz) replica o valor ou continua
     a sequencia: 1, 2, 3...; datas; Jan, Fev...; Seg, Ter...; "Item 1";
     formulas com a referencia relativa andando e a $ presa. Clique duplo na
     alca preenche ate onde vai a coluna vizinha;
   - teclado: setas, Shift, Ctrl, Enter, Tab, F2, Delete, Ctrl+C/X/V/D/R/B/I.

   19-documentos.js chama tres ganchos daqui: plxGrade (desenhar), plxLigar
   (ligar) e plxPintar (pintar a selecao). Quem grava e o servidor, pelas
   rotas de sempre e por /lote, /estrutura e /layout.
*/

const PLX_LARGURA = 112;     // px, a coluna que ninguem mediu
const PLX_ALTURA = 34;       // px, a linha que ninguem mediu (a do CSS)
const PLX_CABECA = 48;       // px, a coluna dos numeros de linha
const PLX_FOLGA_L = 30;      // linhas que entram de cada vez ao rolar
const PLX_FOLGA_C = 6;       // colunas que entram de cada vez ao rolar
const PLX_PERTO = 260;       // px do fim em que a grade cresce

const plx = {
  vista: { chave: "", linhas: 0, colunas: 0 },
  rolagem: {},        // chave -> { top, left }, para voltar ao lugar depois de redesenhar
  clip: null,         // o que foi copiado ou recortado
  arraste: null,      // selecionar, medir, alca
  editor: null,       // o campo que escreve dentro da celula
  selTipo: null,      // "colunas" | "linhas" | "tudo" | null
  menu: null,
  quadro: 0,
  ligado: false,
};

/* ------------------------------------------------------------ o basico */

function plxAba() { return escr.pl.abas[escr.aba]; }
function plxCalc() { return escr.pl.calculado[escr.aba] || {}; }
function plxChave() { return escr.pl.id + ":" + escr.aba; }
function plxCaixa() { return $("plx-caixa"); }
function plxLimites() { return escr.pl.limites || { linhas: 2000, colunas: 104 }; }
function plxRef(l, c) { return letraColuna(c) + l; }

function plxPos(ref) {
  const m = /^([A-Z]{1,2})(\d{1,4})$/.exec(String(ref || "").toUpperCase());
  return m ? { l: Number(m[2]), c: letraParaIndice(m[1]) } : { l: 1, c: 0 };
}

function plxFaixa() {
  const a = plxPos(escr.ancora || escr.celula);
  const b = plxPos(escr.celula);
  return { l1: Math.min(a.l, b.l), l2: Math.max(a.l, b.l), c1: Math.min(a.c, b.c), c2: Math.max(a.c, b.c) };
}

function plxFaixaTexto(f) {
  const a = plxRef(f.l1, f.c1);
  const b = plxRef(f.l2, f.c2);
  return a === b ? a : a + ":" + b;
}

function plxLargura(aba, c) { return (aba.larguras || {})[letraColuna(c)] || PLX_LARGURA; }
function plxAltura(aba, l) { return (aba.alturas || {})[String(l)] || 0; }
function plxOcultasC(aba) { return new Set((aba.colunas_ocultas || []).map((x) => letraParaIndice(x))); }
function plxOcultasL(aba) {
  const s = new Set(aba.linhas_ocultas || []);
  if (escr.filtro) escr.filtro.esconder.forEach((l) => s.add(l));
  return s;
}

function plxCel(aba, l, c) { return aba.celulas[plxRef(l, c)]; }
function plxTem(aba, l, c) { const x = plxCel(aba, l, c); return Boolean(x && x.valor !== ""); }

/* Ate onde ha coisa escrita. A grade nunca encolhe para menos que isso. */
function plxUsado(aba) {
  let linhas = 0, colunas = 0;
  Object.keys(aba.celulas).forEach((ref) => {
    const p = plxPos(ref);
    const cel = aba.celulas[ref];
    linhas = Math.max(linhas, p.l);
    colunas = Math.max(colunas, p.c + Math.max(1, cel.juntar || 1));
  });
  return { linhas: linhas, colunas: colunas };
}

function plxBase(aba) {
  const lim = plxLimites();
  const usado = plxUsado(aba);
  const sel = plxFaixa();
  return {
    linhas: Math.min(lim.linhas, Math.max(aba.linhas, usado.linhas + 1, sel.l2)),
    colunas: Math.min(lim.colunas, Math.max(aba.colunas, usado.colunas + 1, sel.c2 + 1)),
  };
}

/* -------------------------------------------------------------- desenhar */

function plxGrade(aba, calc) {
  const chave = plxChave();
  if (plx.vista.chave !== chave) plx.vista = { chave: chave, linhas: 0, colunas: 0 };
  const base = plxBase(aba);
  const nl = Math.max(base.linhas, plx.vista.linhas);
  const nc = Math.max(base.colunas, plx.vista.colunas);
  plx.vista.linhas = nl;
  plx.vista.colunas = nc;
  plx.editor = null;

  const ocC = plxOcultasC(aba);
  const ocL = plxOcultasL(aba);
  let largura = PLX_CABECA;
  let cols = '<col style="width:' + PLX_CABECA + 'px">';
  let cabeca = '<tr><th class="canto" data-canto="1" title="Selecionar tudo"></th>';
  for (let c = 0; c < nc; c++) {
    if (ocC.has(c)) continue;
    const w = plxLargura(aba, c);
    largura += w;
    cols += plxColHtml(c, w);
    cabeca += plxThHtml(c, ocC);
  }
  let corpo = "";
  for (let l = 1; l <= nl; l++) {
    if (ocL.has(l)) continue;
    corpo += plxLinhaHtml(aba, calc, l, 0, nc, ocC, ocL);
  }
  return '<div class="pl-caixa plx-caixa' + (aba.congelar_cabecalho ? " congelada" : "") +
    '" id="plx-caixa" tabindex="-1"><table class="pl-grade plx-grade" id="plx-grade" style="width:' + largura + 'px">' +
    '<colgroup id="plx-cols">' + cols + "</colgroup><thead><tr>" + cabeca.slice(4) + "</tr></thead>" +
    '<tbody id="plx-corpo">' + corpo + "</tbody></table></div>";
}

function plxColHtml(c, w) {
  return '<col data-c="' + c + '" style="width:' + w + 'px">';
}

function plxThHtml(c, ocC) {
  const classes = [];
  if (c > 0 && ocC.has(c - 1)) classes.push("plx-apos-oculta");
  if (ocC.has(c + 1)) classes.push("plx-antes-oculta");
  const letra = letraColuna(c);
  return '<th data-coluna="' + letra + '" data-c="' + c + '"' + (classes.length ? ' class="' + classes.join(" ") + '"' : "") + ">" +
    letra + '<i class="plx-borda-c" data-borda-c="' + c + '" title="Arraste para mudar a largura · clique duplo ajusta"></i></th>';
}

/* Uma linha, das colunas `de` ate `ate` (sem incluir). `de` > 0 e so a
   ponta nova de uma linha que ja existe, quando a grade cresce para o lado. */
function plxLinhaHtml(aba, calc, l, de, ate, ocC, ocL) {
  let html = "";
  if (de === 0) {
    const h = plxAltura(aba, l);
    const classes = [];
    if (l > 1 && ocL.has(l - 1) && (aba.linhas_ocultas || []).includes(l - 1)) classes.push("plx-apos-oculta");
    html += '<tr data-l="' + l + '"' + (h ? ' style="height:' + h + 'px"' : "") + ">" +
      '<td class="cabeca-linha' + (classes.length ? " " + classes.join(" ") : "") + '" data-linha="' + l + '">' + l +
      '<i class="plx-borda-l" data-borda-l="' + l + '" title="Arraste para mudar a altura · clique duplo ajusta"></i></td>';
  }
  let pulando = 0;
  for (let c = de; c < ate; c++) {
    if (pulando > 0) { pulando -= 1; continue; }
    if (ocC.has(c)) continue;
    const ref = plxRef(l, c);
    const v = calc[ref];
    const cel = aba.celulas[ref];
    const juntar = cel && cel.juntar > 1 ? Math.min(cel.juntar, ate - c) : 1;
    pulando = juntar - 1;
    let visiveis = 0;
    for (let k = c; k < c + juntar; k++) if (!ocC.has(k)) visiveis += 1;
    const classes = ["pl-cel"];
    if (v) {
      if (v.erro) classes.push("ruim");
      else if (typeof v.bruto === "number") classes.push("numero");
      if (v.formula) classes.push("formula");
    }
    if (cel && cel.negrito) classes.push("forte");
    if (cel && cel.italico) classes.push("inclinada");
    if (cel && cel.borda) classes.push("com-borda");
    if (cel && cel.comentario) classes.push("plx-nota");
    html += '<td class="' + classes.join(" ") + '" data-ref="' + ref + '" data-c="' + c + '"' +
      (visiveis > 1 ? ' colspan="' + visiveis + '"' : "") +
      (cel && cel.comentario ? ' title="' + esc(cel.comentario) + '"' : "") + ">" +
      (v ? esc(v.texto) : "") + "</td>";
  }
  if (de === 0) html += "</tr>";
  return html;
}

/* ----------------------------------------------------------------- ligar */

function plxLigar(raiz, aba) {
  const caixa = plxCaixa();
  if (!caixa) return;
  const r = plx.rolagem[plxChave()];
  if (r) { caixa.scrollTop = r.top; caixa.scrollLeft = r.left; }

  caixa.insertAdjacentHTML("beforeend",
    '<div class="plx-moldura" id="plx-moldura" hidden></div>' +
    '<div class="plx-alca" id="plx-alca" title="Arraste para preencher · clique duplo preenche até o fim" hidden></div>' +
    '<div class="plx-copia" id="plx-copia" hidden></div>' +
    '<div class="plx-previa" id="plx-previa" hidden></div>');

  caixa.addEventListener("mousedown", plxAoApertar);
  caixa.addEventListener("mouseover", plxAoPassar);
  caixa.addEventListener("dblclick", plxAoDuploClique);
  caixa.addEventListener("contextmenu", plxAoMenu);
  caixa.addEventListener("scroll", () => {
    plx.rolagem[plxChave()] = { top: caixa.scrollTop, left: caixa.scrollLeft };
    plxFecharMenu();
    if (!plx.quadro) plx.quadro = requestAnimationFrame(() => { plx.quadro = 0; plxCrescer(); });
  }, { passive: true });

  /* A barra fx: Enter grava e desce, Tab grava e vai para o lado. */
  const entrada = $("pl-entrada");
  if (entrada) {
    entrada.onkeydown = (e) => {
      if (e.key === "Enter" || e.key === "Tab") {
        e.preventDefault();
        const passo = e.key === "Enter" ? [e.shiftKey ? -1 : 1, 0] : [0, e.shiftKey ? -1 : 1];
        plxGravarEMover(escr.celula, entrada.value, passo[0], passo[1]);
      }
      if (e.key === "Escape") { entrada.value = valorCru(plxAba(), escr.celula); entrada.blur(); }
    };
  }

  if (!plx.ligado) {
    plx.ligado = true;
    document.addEventListener("mousemove", plxAoMover);
    document.addEventListener("mouseup", plxAoSoltar);
    document.addEventListener("keydown", plxTecla);
    document.addEventListener("copy", (e) => plxAreaDeTransferencia(e, "copiar"));
    document.addEventListener("cut", (e) => plxAreaDeTransferencia(e, "recortar"));
    document.addEventListener("paste", (e) => plxAreaDeTransferencia(e, "colar"));
    window.addEventListener("resize", () => { plxFecharMenu(); if (plxCaixa()) { plxCrescer(); plxPosicionar(); } });
    window.addEventListener("blur", plxFecharMenu);
  }

  requestAnimationFrame(() => { plxCrescer(); plxPosicionar(); });
}

/* A planilha esta na tela e o teclado e dela (nao de um campo, de um
   dialogo ou do menu). */
function plxAtiva() {
  const caixa = plxCaixa();
  if (!caixa || !escr.pl || typeof dialogoAberto !== "undefined" && dialogoAberto) return false;
  const a = document.activeElement;
  if (a && a !== document.body && a !== caixa) {
    if (/^(INPUT|TEXTAREA|SELECT)$/.test(a.tagName) || a.isContentEditable) return false;
    if (a.closest && a.closest(".docs-painel")) return false;
  }
  return true;
}

/* --------------------------------------------------- crescer e encolher */

function plxCrescer() {
  const caixa = plxCaixa();
  if (!caixa || !escr.pl) return;
  const aba = plxAba();
  const lim = plxLimites();
  const base = plxBase(aba);
  let voltas = 0;

  // Para baixo: perto do fim, entra mais um bloco de linhas.
  while (voltas++ < 40 && plx.vista.linhas < lim.linhas &&
         caixa.scrollTop + caixa.clientHeight > caixa.scrollHeight - PLX_PERTO) {
    plxAcrescentarLinhas(Math.min(PLX_FOLGA_L, lim.linhas - plx.vista.linhas));
  }
  // Para o lado.
  voltas = 0;
  while (voltas++ < 20 && plx.vista.colunas < lim.colunas &&
         caixa.scrollLeft + caixa.clientWidth > caixa.scrollWidth - PLX_PERTO) {
    plxAcrescentarColunas(Math.min(PLX_FOLGA_C, lim.colunas - plx.vista.colunas));
  }

  // Voltando: o que sobrou bem abaixo da vista, vazio e alem da area usada, sai.
  const topo = caixa.getBoundingClientRect().top;
  const fundoDaVista = topo + caixa.clientHeight;
  while (plx.vista.linhas - PLX_FOLGA_L >= base.linhas) {
    const corte = plx.vista.linhas - PLX_FOLGA_L;
    const tr = plxUltimaLinhaAte(corte);
    if (!tr || tr.getBoundingClientRect().top < fundoDaVista + PLX_PERTO * 2) break;
    plxTirarLinhasDepois(corte);
  }
  const esquerda = caixa.getBoundingClientRect().left;
  const direitaDaVista = esquerda + caixa.clientWidth;
  while (plx.vista.colunas - PLX_FOLGA_C >= base.colunas) {
    const corte = plx.vista.colunas - PLX_FOLGA_C;
    const th = plxUltimaColunaAntes(corte);
    if (!th || th.getBoundingClientRect().left < direitaDaVista + PLX_PERTO * 2) break;
    plxTirarColunasDesde(corte);
  }
}

function plxUltimaLinhaAte(l) {
  const corpo = $("plx-corpo");
  if (!corpo) return null;
  for (let i = corpo.rows.length - 1; i >= 0; i--) {
    if (Number(corpo.rows[i].dataset.l) <= l) return corpo.rows[i];
  }
  return null;
}

function plxUltimaColunaAntes(c) {
  const ths = document.querySelectorAll("#plx-grade thead th[data-c]");
  for (let i = ths.length - 1; i >= 0; i--) if (Number(ths[i].dataset.c) < c) return ths[i];
  return null;
}

function plxAcrescentarLinhas(n) {
  const corpo = $("plx-corpo");
  if (!corpo || n <= 0) return;
  const aba = plxAba();
  const calc = plxCalc();
  const ocC = plxOcultasC(aba);
  const ocL = plxOcultasL(aba);
  let html = "";
  for (let l = plx.vista.linhas + 1; l <= plx.vista.linhas + n; l++) {
    if (!ocL.has(l)) html += plxLinhaHtml(aba, calc, l, 0, plx.vista.colunas, ocC, ocL);
  }
  corpo.insertAdjacentHTML("beforeend", html);
  plx.vista.linhas += n;
  plxPintar();
}

function plxTirarLinhasDepois(l) {
  const corpo = $("plx-corpo");
  if (!corpo) return;
  for (let i = corpo.rows.length - 1; i >= 0 && Number(corpo.rows[i].dataset.l) > l; i--) corpo.rows[i].remove();
  plx.vista.linhas = l;
}

function plxAcrescentarColunas(n) {
  const tabela = $("plx-grade");
  if (!tabela || n <= 0) return;
  const aba = plxAba();
  const calc = plxCalc();
  const ocC = plxOcultasC(aba);
  const ocL = plxOcultasL(aba);
  const de = plx.vista.colunas;
  const ate = de + n;
  let cols = "", ths = "", largura = 0;
  for (let c = de; c < ate; c++) {
    if (ocC.has(c)) continue;
    const w = plxLargura(aba, c);
    largura += w;
    cols += plxColHtml(c, w);
    ths += plxThHtml(c, ocC);
  }
  $("plx-cols").insertAdjacentHTML("beforeend", cols);
  tabela.tHead.rows[0].insertAdjacentHTML("beforeend", ths);
  Array.from($("plx-corpo").rows).forEach((tr) => {
    tr.insertAdjacentHTML("beforeend", plxLinhaHtml(aba, calc, Number(tr.dataset.l), de, ate, ocC, ocL));
  });
  tabela.style.width = (parseFloat(tabela.style.width) + largura) + "px";
  plx.vista.colunas = ate;
  plxPintar();
}

function plxTirarColunasDesde(c) {
  const tabela = $("plx-grade");
  if (!tabela) return;
  let largura = 0;
  tabela.querySelectorAll("col[data-c]").forEach((col) => {
    if (Number(col.dataset.c) >= c) { largura += parseFloat(col.style.width) || 0; col.remove(); }
  });
  tabela.querySelectorAll("th[data-c], td[data-c]").forEach((el) => { if (Number(el.dataset.c) >= c) el.remove(); });
  tabela.style.width = (parseFloat(tabela.style.width) - largura) + "px";
  plx.vista.colunas = c;
}

/* ------------------------------------------------------ pintar e moldura */

function plxPintar() {
  const caixa = plxCaixa();
  if (!caixa || !escr.pl) return;
  const f = plxFaixa();
  caixa.querySelectorAll(".pl-cel.escolhida, .pl-cel.na-faixa").forEach((td) => td.classList.remove("escolhida", "na-faixa"));
  caixa.querySelectorAll(".plx-sel").forEach((el) => el.classList.remove("plx-sel", "plx-sel-toda"));

  const unica = f.l1 === f.l2 && f.c1 === f.c2;
  const corpo = $("plx-corpo");
  if (corpo) {
    for (const tr of corpo.rows) {
      const l = Number(tr.dataset.l);
      if (l < f.l1) continue;
      if (l > f.l2) break;
      tr.cells[0].classList.add("plx-sel");
      if (plx.selTipo === "linhas" || plx.selTipo === "tudo") tr.cells[0].classList.add("plx-sel-toda");
      if (unica) continue;
      for (let i = 1; i < tr.cells.length; i++) {
        const td = tr.cells[i];
        const c = Number(td.dataset.c);
        if (c >= f.c1 && c <= f.c2) td.classList.add("na-faixa");
      }
    }
  }
  caixa.querySelectorAll("thead th[data-c]").forEach((th) => {
    const c = Number(th.dataset.c);
    if (c >= f.c1 && c <= f.c2) {
      th.classList.add("plx-sel");
      if (plx.selTipo === "colunas" || plx.selTipo === "tudo") th.classList.add("plx-sel-toda");
    }
  });
  const ativa = caixa.querySelector('[data-ref="' + escr.celula + '"]');
  if (ativa) { ativa.classList.add("escolhida"); ativa.classList.remove("na-faixa"); }
  plxPosicionar();
}

/* O retangulo, em pixels dentro da caixa, que cobre as linhas l1..l2 e as
   colunas c1..c2 que estao desenhadas. */
function plxRetangulo(f) {
  const caixa = plxCaixa();
  const corpo = $("plx-corpo");
  if (!caixa || !corpo) return null;
  let trA = null, trB = null;
  for (const tr of corpo.rows) {
    const l = Number(tr.dataset.l);
    if (l >= f.l1 && l <= f.l2) { if (!trA) trA = tr; trB = tr; }
    if (l > f.l2) break;
  }
  let thA = null, thB = null;
  caixa.querySelectorAll("thead th[data-c]").forEach((th) => {
    const c = Number(th.dataset.c);
    if (c >= f.c1 && c <= f.c2) { if (!thA) thA = th; thB = th; }
  });
  if (!trA || !thA) return null;
  const base = caixa.getBoundingClientRect();
  const ra = trA.getBoundingClientRect(), rb = trB.getBoundingClientRect();
  const ca = thA.getBoundingClientRect(), cb = thB.getBoundingClientRect();
  const dy = caixa.scrollTop - base.top - caixa.clientTop;
  const dx = caixa.scrollLeft - base.left - caixa.clientLeft;
  return { top: ra.top + dy, left: ca.left + dx, width: cb.right - ca.left, height: rb.bottom - ra.top };
}

function plxPor(el, r) {
  if (!el) return;
  if (!r) { el.hidden = true; return; }
  el.hidden = false;
  el.style.top = r.top + "px";
  el.style.left = r.left + "px";
  el.style.width = r.width + "px";
  el.style.height = r.height + "px";
}

function plxPosicionar() {
  if (!plxCaixa()) return;
  const f = plxFaixa();
  const r = plxRetangulo(f);
  plxPor($("plx-moldura"), r);
  const alca = $("plx-alca");
  if (alca) {
    if (!r || plx.selTipo) alca.hidden = true;
    else {
      alca.hidden = false;
      alca.style.top = (r.top + r.height - 4) + "px";
      alca.style.left = (r.left + r.width - 4) + "px";
    }
  }
  const copia = $("plx-copia");
  if (copia) {
    const c = plx.clip;
    plxPor(copia, c && c.doc === escr.pl.id && c.aba === escr.aba && !c.usado ? plxRetangulo(c.f) : null);
    if (copia) copia.classList.toggle("recorte", Boolean(c && c.recortar));
  }
  if (plx.editor) plxAjustarEditor();
}

/* ------------------------------------------------------------- o mouse */

function plxCelulaDe(el) { return el && el.closest ? el.closest("td[data-ref]") : null; }

function plxSelecionar(ancora, celula, tipo) {
  plx.selTipo = tipo || null;
  escolherCelula(ancora);
  if (celula !== ancora) escolherCelula(celula, true);
}

function plxSelecionarColunas(c1, c2) {
  plxSelecionar(plxRef(1, c1), plxRef(plx.vista.linhas, c2), "colunas");
}

function plxSelecionarLinhas(l1, l2) {
  plxSelecionar(plxRef(l1, 0), plxRef(l2, plx.vista.colunas - 1), "linhas");
}

function plxAoApertar(e) {
  const alvo = e.target;
  plxFecharMenu();
  if (e.button === 1) return;

  if (alvo.closest(".plx-alca")) {
    e.preventDefault();
    plx.arraste = { tipo: "alca", f: plxFaixa(), alvo: null };
    document.body.classList.add("plx-cruz");
    return;
  }
  const bordaC = alvo.closest("[data-borda-c]");
  if (bordaC && e.button === 0) {
    e.preventDefault();
    e.stopPropagation();
    const c = Number(bordaC.dataset.bordaC);
    const f = plxFaixa();
    const todas = plx.selTipo === "colunas" || plx.selTipo === "tudo";
    const lista = todas && c >= f.c1 && c <= f.c2 ? plxVisiveisC(f.c1, f.c2) : [c];
    plx.arraste = { tipo: "largura", c: c, lista: lista, x0: e.clientX, w0: plxLargura(plxAba(), c), mudou: false };
    document.body.classList.add("plx-medindo-c");
    return;
  }
  const bordaL = alvo.closest("[data-borda-l]");
  if (bordaL && e.button === 0) {
    e.preventDefault();
    e.stopPropagation();
    const l = Number(bordaL.dataset.bordaL);
    const tr = bordaL.closest("tr");
    const f = plxFaixa();
    const todas = plx.selTipo === "linhas" || plx.selTipo === "tudo";
    const lista = todas && l >= f.l1 && l <= f.l2 ? plxVisiveisL(f.l1, f.l2) : [l];
    plx.arraste = { tipo: "altura", l: l, lista: lista, y0: e.clientY, h0: tr.getBoundingClientRect().height, mudou: false };
    document.body.classList.add("plx-medindo-l");
    return;
  }

  // Escrevendo uma formula: clicar na celula poe a referencia no texto.
  const td = plxCelulaDe(alvo);
  if (td && e.button === 0 && plxInserirReferencia(td.dataset.ref, e)) return;

  if (plx.editor) plxFecharEditor(true);
  const f = plxFaixa();
  // O teclado passa a ser da grade (e nao da barra fx, se ela tinha o foco).
  if (!alvo.closest(".plx-editor")) plxCaixa().focus({ preventScroll: true });

  if (alvo.closest("[data-canto]")) {
    e.preventDefault();
    plxSelecionar("A1", plxRef(plx.vista.linhas, plx.vista.colunas - 1), "tudo");
    return;
  }
  const th = alvo.closest("th[data-c]");
  if (th) {
    e.preventDefault();
    const c = Number(th.dataset.c);
    const dentro = (plx.selTipo === "colunas" || plx.selTipo === "tudo") && c >= f.c1 && c <= f.c2;
    if (e.button === 2 && dentro) return;
    if (e.shiftKey && plx.selTipo === "colunas") {
      const a = plxPos(escr.ancora || escr.celula).c;
      plxSelecionarColunas(a, c);
    } else plxSelecionarColunas(c, c);
    if (e.button === 0) plx.arraste = { tipo: "colunas", de: plxPos(escr.ancora).c };
    return;
  }
  const cabL = alvo.closest("td[data-linha]");
  if (cabL) {
    e.preventDefault();
    const l = Number(cabL.dataset.linha);
    const dentro = (plx.selTipo === "linhas" || plx.selTipo === "tudo") && l >= f.l1 && l <= f.l2;
    if (e.button === 2 && dentro) return;
    if (e.shiftKey && plx.selTipo === "linhas") {
      const a = plxPos(escr.ancora || escr.celula).l;
      plxSelecionarLinhas(a, l);
    } else plxSelecionarLinhas(l, l);
    if (e.button === 0) plx.arraste = { tipo: "linhas", de: plxPos(escr.ancora).l };
    return;
  }
  if (td) {
    e.preventDefault();
    const p = plxPos(td.dataset.ref);
    const dentro = p.l >= f.l1 && p.l <= f.l2 && p.c >= f.c1 && p.c <= f.c2;
    if (e.button === 2 && dentro) return;
    plx.selTipo = null;
    escolherCelula(td.dataset.ref, e.shiftKey && e.button === 0);
    if (e.button === 0) plx.arraste = { tipo: "sel" };
  }
}

function plxAoPassar(e) {
  const a = plx.arraste;
  if (!a) return;
  if (a.tipo === "sel") {
    const td = plxCelulaDe(e.target);
    if (td && td.dataset.ref !== escr.celula) escolherCelula(td.dataset.ref, true);
  } else if (a.tipo === "colunas") {
    const th = e.target.closest("th[data-c]");
    if (th) plxSelecionarColunas(a.de, Number(th.dataset.c));
  } else if (a.tipo === "linhas") {
    const td = e.target.closest("td[data-linha]");
    if (td) plxSelecionarLinhas(a.de, Number(td.dataset.linha));
  } else if (a.tipo === "formula") {
    const td = plxCelulaDe(e.target);
    if (td) plxEsticarReferencia(td.dataset.ref);
  }
}

function plxAoMover(e) {
  const a = plx.arraste;
  if (!a) return;
  if (a.tipo === "largura") {
    const w = Math.max(24, Math.min(900, Math.round(a.w0 + e.clientX - a.x0)));
    a.mudou = a.mudou || w !== a.w0;
    a.w = w;
    plxAplicarLarguras(a.lista, w);
    return;
  }
  if (a.tipo === "altura") {
    const h = Math.max(18, Math.min(400, Math.round(a.h0 + e.clientY - a.y0)));
    a.mudou = a.mudou || h !== Math.round(a.h0);
    a.h = h;
    a.lista.forEach((l) => { const tr = document.querySelector('#plx-corpo tr[data-l="' + l + '"]'); if (tr) tr.style.height = h + "px"; });
    plxPosicionar();
    return;
  }
  // Arrastando alem da borda da caixa, a grade rola junto.
  if (a.tipo === "sel" || a.tipo === "alca" || a.tipo === "colunas" || a.tipo === "linhas") {
    const caixa = plxCaixa();
    if (!caixa) return;
    const r = caixa.getBoundingClientRect();
    if (e.clientY > r.bottom - 12) caixa.scrollTop += 24;
    else if (e.clientY < r.top + 40) caixa.scrollTop -= 24;
    if (e.clientX > r.right - 12) caixa.scrollLeft += 24;
    else if (e.clientX < r.left + PLX_CABECA) caixa.scrollLeft -= 24;
  }
  if (a.tipo === "alca") plxArrastarAlca(e);
}

function plxAoSoltar(e) {
  const a = plx.arraste;
  if (!a) return;
  plx.arraste = null;
  document.body.classList.remove("plx-cruz", "plx-medindo-c", "plx-medindo-l");
  if (a.tipo === "largura" && a.mudou) {
    const larguras = {};
    a.lista.forEach((c) => { larguras[letraColuna(c)] = a.w; });
    plxLayout({ larguras: larguras }, false);
  } else if (a.tipo === "altura" && a.mudou) {
    const alturas = {};
    a.lista.forEach((l) => { alturas[String(l)] = a.h; });
    plxLayout({ alturas: alturas }, false);
  } else if (a.tipo === "alca") {
    const previa = $("plx-previa");
    if (previa) previa.hidden = true;
    plxEsconderDica();
    if (a.alvo) plxPreencher(a.f, a.alvo, e.ctrlKey);
  }
}

function plxAoDuploClique(e) {
  const alvo = e.target;
  if (alvo.closest(".plx-alca")) { plxPreencherAteOFim(); return; }
  const bordaC = alvo.closest("[data-borda-c]");
  if (bordaC) {
    const c = Number(bordaC.dataset.bordaC);
    const f = plxFaixa();
    const todas = plx.selTipo === "colunas" || plx.selTipo === "tudo";
    plxAutoAjustar(todas && c >= f.c1 && c <= f.c2 ? plxVisiveisC(f.c1, f.c2) : [c]);
    return;
  }
  const bordaL = alvo.closest("[data-borda-l]");
  if (bordaL) {
    const l = Number(bordaL.dataset.bordaL);
    const f = plxFaixa();
    const todas = plx.selTipo === "linhas" || plx.selTipo === "tudo";
    const lista = todas && l >= f.l1 && l <= f.l2 ? plxVisiveisL(f.l1, f.l2) : [l];
    const alturas = {};
    lista.forEach((x) => { alturas[String(x)] = null; });
    plxLayout({ alturas: alturas }, true);
    return;
  }
  // Clique duplo na marca da coluna oculta a mostra de volta.
  const th = alvo.closest("th.plx-apos-oculta");
  if (th && e.clientX - th.getBoundingClientRect().left < 10) {
    plxReexibirPerto("colunas", Number(th.dataset.c) - 1, Number(th.dataset.c) - 1);
    return;
  }
  const td = plxCelulaDe(alvo);
  if (td) plxEditar(td.dataset.ref, null);
}

function plxVisiveisC(c1, c2) {
  const oc = plxOcultasC(plxAba());
  const saida = [];
  for (let c = c1; c <= c2; c++) if (!oc.has(c)) saida.push(c);
  return saida;
}

function plxVisiveisL(l1, l2) {
  const oc = plxOcultasL(plxAba());
  const saida = [];
  for (let l = l1; l <= l2; l++) if (!oc.has(l)) saida.push(l);
  return saida;
}

/* ------------------------------------------------ largura e altura */

function plxAplicarLarguras(lista, w) {
  const tabela = $("plx-grade");
  if (!tabela) return;
  lista.forEach((c) => {
    const col = tabela.querySelector('col[data-c="' + c + '"]');
    if (col) col.style.width = w + "px";
  });
  let total = 0;
  tabela.querySelectorAll("col").forEach((col) => { total += parseFloat(col.style.width) || 0; });
  tabela.style.width = total + "px";
  plxPosicionar();
}

/* Ajustar ao conteudo: mede o texto de cada celula da coluna com a fonte
   dela - negrito ocupa mais que o normal. */
function plxAutoAjustar(lista) {
  const tabela = $("plx-grade");
  if (!tabela) return;
  const regua = document.createElement("canvas").getContext("2d");
  const larguras = {};
  lista.forEach((c) => {
    let maior = 0;
    tabela.querySelectorAll('td.pl-cel[data-c="' + c + '"]').forEach((td) => {
      if (td.colSpan > 1 || !td.textContent) return;
      const estilo = getComputedStyle(td);
      regua.font = estilo.fontStyle + " " + estilo.fontWeight + " " + estilo.fontSize + " " + estilo.fontFamily;
      const folga = parseFloat(estilo.paddingLeft) + parseFloat(estilo.paddingRight) + 6;
      maior = Math.max(maior, Math.ceil(regua.measureText(td.textContent).width + folga));
    });
    larguras[letraColuna(c)] = maior ? Math.max(40, Math.min(600, maior)) : null;
  });
  plxLayout({ larguras: larguras }, true);
}

async function plxPedirMedida(eixo) {
  const aba = plxAba();
  const f = plxFaixa();
  const colunas = eixo === "colunas";
  const lista = colunas ? plxVisiveisC(f.c1, f.c2) : plxVisiveisL(f.l1, f.l2);
  if (!lista.length) return;
  let atual;
  if (colunas) atual = plxLargura(aba, lista[0]);
  else {
    const tr = document.querySelector('#plx-corpo tr[data-l="' + lista[0] + '"]');
    atual = plxAltura(aba, lista[0]) || (tr ? Math.round(tr.getBoundingClientRect().height) : PLX_ALTURA);
  }
  const nomes = colunas
    ? (lista.length === 1 ? "coluna " + letraColuna(lista[0]) : "colunas " + letraColuna(lista[0]) + " a " + letraColuna(lista[lista.length - 1]))
    : (lista.length === 1 ? "linha " + lista[0] : "linhas " + lista[0] + " a " + lista[lista.length - 1]);
  const valor = await perguntar({
    titulo: colunas ? "Largura da coluna" : "Altura da linha",
    contexto: "Planilha › " + aba.nome + " › " + nomes,
    campo: {
      rotulo: colunas ? "Largura" : "Altura", valor: String(atual), sufixo: "px",
      icone: colunas ? "width" : "height",
      dica: colunas ? "de 24 a 900 px · o padrão é " + PLX_LARGURA : "de 18 a 400 px · o padrão é " + PLX_ALTURA,
    },
    confirmar: "Aplicar",
  });
  if (valor === null) return;
  const n = Math.round(Number(String(valor).replace(",", ".")));
  if (!Number.isFinite(n) || n <= 0) { avisoCert("a medida é um número de pixels", { tom: "erro" }); return; }
  const medidas = {};
  lista.forEach((x) => { medidas[colunas ? letraColuna(x) : String(x)] = n; });
  plxLayout(colunas ? { larguras: medidas } : { alturas: medidas }, true);
}

async function plxLayout(dados, redesenhar) {
  const r = await fetch("/api/planilha/" + escr.pl.id + "/layout", {
    method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify(Object.assign({ aba: escr.aba }, dados)),
  });
  if (!r.ok) { avisoCert(await erroDe(r), { tom: "erro" }); desenharPlanilha(); return; }
  escr.pl = await r.json();
  if (redesenhar) desenharPlanilha();
}

/* --------------------------------------------------- ocultar e reexibir */

function plxOcultar(eixo) {
  const f = plxFaixa();
  const lista = [];
  if (eixo === "colunas") for (let c = f.c1; c <= f.c2; c++) lista.push(letraColuna(c));
  else for (let l = f.l1; l <= f.l2; l++) lista.push(l);
  plxLayout({ ocultar: eixo === "colunas" ? { colunas: lista } : { linhas: lista } }, true);
}

/* As ocultas dentro da selecao e as coladas nela, dos dois lados. */
function plxOcultasPerto(eixo, a, b) {
  const aba = plxAba();
  const ocultas = eixo === "colunas"
    ? new Set((aba.colunas_ocultas || []).map((x) => letraParaIndice(x)))
    : new Set(aba.linhas_ocultas || []);
  const saida = new Set();
  for (let i = a; i <= b; i++) if (ocultas.has(i)) saida.add(i);
  for (let i = a - 1; ocultas.has(i); i--) saida.add(i);
  for (let i = b + 1; ocultas.has(i); i++) saida.add(i);
  return Array.from(saida).sort((x, y) => x - y);
}

function plxReexibirPerto(eixo, a, b) {
  const lista = plxOcultasPerto(eixo, a, b);
  if (!lista.length) return;
  plxLayout({ reexibir: eixo === "colunas" ? { colunas: lista.map(letraColuna) } : { linhas: lista } }, true);
}

function plxReexibirTodas(eixo) {
  const aba = plxAba();
  plxLayout({ reexibir: eixo === "colunas" ? { colunas: aba.colunas_ocultas || [] } : { linhas: aba.linhas_ocultas || [] } }, true);
}

/* ------------------------------------------ inserir e excluir, gravar */

async function plxEstrutura(eixo, acao, em, quantas) {
  const r = await fetch("/api/planilha/" + escr.pl.id + "/estrutura", {
    method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ aba: escr.aba, eixo: eixo, acao: acao, em: em, quantas: quantas }),
  });
  if (!r.ok) { avisoCert(await erroDe(r), { tom: "erro" }); return; }
  const d = await r.json();
  escr.pl = d;
  escr.filtro = null;
  plx.clip = null;
  desenharPlanilha();
  const nome = eixo === "linhas" ? plural(quantas, "linha") : plural(quantas, "coluna");
  avisoCert(nome + (acao === "inserir" ? " inserida" : " excluída") + (quantas > 1 ? "s" : "") +
    (d.feito && d.feito.formulas ? " · " + plural(d.feito.formulas, "fórmula") + " acompanhou" : "") +
    (acao === "excluir" ? " · dá para voltar no Histórico" : ""), { tom: "ok" });
}

async function plxLote(itens, nota, aba) {
  if (!itens.length) return null;
  const r = await fetch("/api/planilha/" + escr.pl.id + "/lote", {
    method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ aba: aba === undefined ? escr.aba : aba, itens: itens, nota: nota }),
  });
  if (!r.ok) { avisoCert(await erroDe(r), { tom: "erro" }); return null; }
  escr.pl = await r.json();
  return escr.pl;
}

function plxLimpar(o) {
  const aba = plxAba();
  const f = plxFaixa();
  const itens = [];
  Object.keys(aba.celulas).forEach((ref) => {
    const p = plxPos(ref);
    if (p.l < f.l1 || p.l > f.l2 || p.c < f.c1 || p.c > f.c2) return;
    const dados = {};
    if (o !== "formatos") dados.valor = "";
    if (o !== "conteudo") Object.assign(dados, { formato: "", negrito: false, italico: false, borda: false });
    if (o === "tudo") dados.comentario = "";
    itens.push({ ref: ref, dados: dados });
  });
  if (!itens.length) return;
  plxLote(itens, (o === "formatos" ? "limpou a formatação de " : "limpou ") + plxFaixaTexto(f)).then((d) => { if (d) desenharPlanilha(); });
}

async function plxGravarEMover(ref, valor, dl, dc) {
  const aba = plxAba();
  if (valor !== valorCru(aba, ref)) {
    escr.celula = ref;
    escr.ancora = ref;
    await gravarCelula(valor);
  }
  plxMover(dl, dc, false);
}

/* ------------------------------------------------------------ o teclado */

function plxTecla(e) {
  if (plx.menu) { plxTeclaNoMenu(e); return; }
  if (!plxAtiva()) return;
  // AltGr chega como Ctrl+Alt no Windows: "/" e "?" no teclado ABNT2 sao
  // letras, e nao atalho.
  const ctrl = (e.ctrlKey || e.metaKey) && !e.altKey;
  const k = e.key;
  const passos = { ArrowDown: [1, 0], ArrowUp: [-1, 0], ArrowRight: [0, 1], ArrowLeft: [0, -1] };

  if (passos[k]) {
    e.preventDefault();
    if (ctrl) plxSaltar(passos[k][0], passos[k][1], e.shiftKey);
    else plxMover(passos[k][0], passos[k][1], e.shiftKey);
    return;
  }
  if (k === "Enter") { e.preventDefault(); plxMover(e.shiftKey ? -1 : 1, 0, false); return; }
  if (k === "Tab") { e.preventDefault(); plxMover(0, e.shiftKey ? -1 : 1, false); return; }
  if (k === "PageDown" || k === "PageUp") {
    e.preventDefault();
    const caixa = plxCaixa();
    plxMover((k === "PageDown" ? 1 : -1) * Math.max(1, Math.floor(caixa.clientHeight / PLX_ALTURA) - 1), 0, e.shiftKey);
    return;
  }
  if (k === "Home") {
    e.preventDefault();
    const p = plxPos(escr.celula);
    plx.selTipo = null;
    escolherCelula(ctrl ? "A1" : plxRef(p.l, 0), e.shiftKey);
    plxMostrar(escr.celula);
    return;
  }
  if (k === "F2") { e.preventDefault(); plxEditar(escr.celula, null); return; }
  if (k === "Delete") { e.preventDefault(); plxLimpar("conteudo"); return; }
  if (k === "Backspace") { e.preventDefault(); plxEditar(escr.celula, ""); return; }
  if (k === "Escape") { if (plx.clip) { plx.clip = null; plxPosicionar(); } return; }
  if (k === "ContextMenu" || (k === "F10" && e.shiftKey)) {
    e.preventDefault();
    const td = plxCaixa().querySelector('[data-ref="' + escr.celula + '"]');
    const r = td ? td.getBoundingClientRect() : plxCaixa().getBoundingClientRect();
    plx.alvoDoMenu = null;
    plxAbrirMenu(r.left + 12, r.bottom - 4, "celula");
    return;
  }
  if (ctrl) {
    const letra = k.toLowerCase();
    if (letra === "a") { e.preventDefault(); plxSelecionar("A1", plxRef(plx.vista.linhas, plx.vista.colunas - 1), "tudo"); return; }
    if (letra === "b") { e.preventDefault(); aplicarNaFaixa({ negrito: !((plxAba().celulas[escr.celula] || {}).negrito) }); return; }
    if (letra === "i") { e.preventDefault(); aplicarNaFaixa({ italico: !((plxAba().celulas[escr.celula] || {}).italico) }); return; }
    if (letra === "d") { e.preventDefault(); plxPreencherDaPrimeira("baixo"); return; }
    if (letra === "r") { e.preventDefault(); plxPreencherDaPrimeira("direita"); return; }
    return; // Ctrl+C, X e V chegam pelos eventos copy, cut e paste
  }
  if (k.length === 1 && !(e.altKey && !e.ctrlKey)) {
    e.preventDefault();
    plxEditar(escr.celula, k);
  }
}

/* Anda uma casa (ou `dl` linhas), pulando o que esta oculto. */
function plxMover(dl, dc, estender) {
  const aba = plxAba();
  const lim = plxLimites();
  const ocC = plxOcultasC(aba);
  const ocL = plxOcultasL(aba);
  const p = plxPos(escr.celula);
  let l = p.l, c = p.c;
  const passoL = Math.sign(dl), passoC = Math.sign(dc);
  for (let i = 0; i < Math.abs(dl); i++) {
    let n = l + passoL;
    while (n >= 1 && n <= lim.linhas && ocL.has(n)) n += passoL;
    if (n < 1 || n > lim.linhas) break;
    l = n;
  }
  for (let i = 0; i < Math.abs(dc); i++) {
    let n = c + passoC;
    while (n >= 0 && n < lim.colunas && ocC.has(n)) n += passoC;
    if (n < 0 || n >= lim.colunas) break;
    c = n;
  }
  plxIrPara(l, c, estender);
}

function plxIrPara(l, c, estender) {
  if (l > plx.vista.linhas) plxAcrescentarLinhas(l - plx.vista.linhas + PLX_FOLGA_L);
  if (c >= plx.vista.colunas) plxAcrescentarColunas(c - plx.vista.colunas + PLX_FOLGA_C);
  if (!estender) plx.selTipo = null;
  escolherCelula(plxRef(l, c), estender);
  plxMostrar(escr.celula);
}

/* Ctrl+seta: vai ate a borda do bloco com conteudo, como no Excel; sem
   nada no caminho, vai ate a borda da grade. */
function plxSaltar(dl, dc, estender) {
  const aba = plxAba();
  const p = plxPos(escr.celula);
  const fimL = plx.vista.linhas, fimC = plx.vista.colunas - 1;
  const dentro = (l, c) => l >= 1 && c >= 0 && l <= fimL && c <= fimC;
  const tem = (l, c) => plxTem(aba, l, c);
  let l = p.l, c = p.c;
  if (tem(l, c) && dentro(l + dl, c + dc) && tem(l + dl, c + dc)) {
    while (dentro(l + dl, c + dc) && tem(l + dl, c + dc)) { l += dl; c += dc; }
  } else {
    do { l += dl; c += dc; } while (dentro(l, c) && !tem(l, c));
    if (!dentro(l, c)) { l = Math.max(1, Math.min(fimL, l)); c = Math.max(0, Math.min(fimC, c)); }
  }
  plxIrPara(l, c, estender);
}

/* Rola o minimo para a celula aparecer inteira, fora dos cabecalhos presos. */
function plxMostrar(ref) {
  const caixa = plxCaixa();
  const td = caixa && caixa.querySelector('[data-ref="' + ref + '"]');
  if (!td) return;
  const r = td.getBoundingClientRect();
  const c = caixa.getBoundingClientRect();
  const thead = $("plx-grade").tHead.getBoundingClientRect();
  const cima = c.top + thead.height + (plxAba().congelar_cabecalho ? PLX_ALTURA : 0);
  const esquerda = c.left + PLX_CABECA;
  if (r.top < cima) caixa.scrollTop -= cima - r.top;
  else if (r.bottom > c.top + caixa.clientHeight) caixa.scrollTop += r.bottom - (c.top + caixa.clientHeight);
  if (r.left < esquerda) caixa.scrollLeft -= esquerda - r.left;
  else if (r.right > c.left + caixa.clientWidth) caixa.scrollLeft += r.right - (c.left + caixa.clientWidth);
}

/* ------------------------------------------- escrever dentro da celula */

function plxEditar(ref, inicial) {
  const caixa = plxCaixa();
  const td = caixa && caixa.querySelector('[data-ref="' + ref + '"]');
  if (!td) return;
  if (plx.editor) plxFecharEditor(true);
  const aba = plxAba();
  const campo = document.createElement("input");
  campo.type = "text";
  campo.className = "plx-editor";
  campo.spellcheck = false;
  campo.autocomplete = "off";
  const cru = valorCru(aba, ref);
  campo.value = inicial === null || inicial === undefined ? cru : inicial;
  const estilo = getComputedStyle(td);
  campo.style.font = estilo.font;
  campo.style.textAlign = inicial === null && td.classList.contains("numero") ? "right" : "left";
  caixa.appendChild(campo);
  // Entrou digitando: as setas gravam e andam. Entrou com F2 ou clique
  // duplo: as setas andam dentro do texto. E a regra do Excel.
  plx.editor = { campo: campo, ref: ref, cru: cru, digitando: inicial !== null && inicial !== undefined };
  plxAjustarEditor();
  campo.focus();
  const fim = campo.value.length;
  campo.setSelectionRange(fim, fim);
  const fx = $("pl-entrada");
  if (fx) fx.value = campo.value;

  campo.oninput = () => { if (fx) fx.value = campo.value; plxAjustarEditor(); };
  campo.onkeydown = (e) => {
    const setas = { ArrowDown: [1, 0], ArrowUp: [-1, 0], ArrowRight: [0, 1], ArrowLeft: [0, -1] };
    if (e.key === "Enter") { e.preventDefault(); plxConfirmarEditor(e.shiftKey ? -1 : 1, 0); }
    else if (e.key === "Tab") { e.preventDefault(); plxConfirmarEditor(0, e.shiftKey ? -1 : 1); }
    else if (e.key === "Escape") { e.preventDefault(); plxFecharEditor(false); plxCaixa().focus({ preventScroll: true }); }
    else if (setas[e.key] && plx.editor && plx.editor.digitando && !plxPedeReferencia(campo)) {
      e.preventDefault();
      plxConfirmarEditor(setas[e.key][0], setas[e.key][1]);
    }
    e.stopPropagation();
  };
  campo.onblur = () => {
    // O clique numa celula enquanto se escreve uma formula nao fecha o campo.
    setTimeout(() => { if (plx.editor && plx.editor.campo === campo && document.activeElement !== campo && !plx.arraste) plxFecharEditor(true); }, 0);
  };
}

function plxAjustarEditor() {
  const ed = plx.editor;
  if (!ed) return;
  const caixa = plxCaixa();
  const td = caixa && caixa.querySelector('[data-ref="' + ed.ref + '"]');
  if (!td) { plxFecharEditor(false); return; }
  const base = caixa.getBoundingClientRect();
  const r = td.getBoundingClientRect();
  ed.campo.style.top = (r.top - base.top + caixa.scrollTop - 1) + "px";
  ed.campo.style.left = (r.left - base.left + caixa.scrollLeft - 1) + "px";
  ed.campo.style.height = (r.height + 2) + "px";
  ed.campo.style.minWidth = (r.width + 2) + "px";
  ed.campo.style.width = Math.max(r.width + 2, Math.min(560, ed.campo.value.length * 8 + 28)) + "px";
}

function plxConfirmarEditor(dl, dc) {
  const ed = plx.editor;
  if (!ed) return;
  plx.editor = null;
  const valor = ed.campo.value;
  ed.campo.remove();
  plxCaixa().focus({ preventScroll: true });
  plxGravarEMover(ed.ref, valor, dl, dc);
}

function plxFecharEditor(gravar) {
  const ed = plx.editor;
  if (!ed) return;
  plx.editor = null;
  const valor = ed.campo.value;
  ed.campo.remove();
  if (gravar && valor !== ed.cru) {
    escr.celula = ed.ref;
    escr.ancora = ed.ref;
    gravarCelula(valor);
  } else {
    const fx = $("pl-entrada");
    if (fx) fx.value = valorCru(plxAba(), escr.celula);
  }
}

/* A formula sendo escrita aceita referencia onde o cursor esta depois de
   "=", de um operador, de ";" ou de "(" - e ali clicar numa celula escreve
   o endereco dela, como no Excel. */
function plxPedeReferencia(campo) {
  if (!campo || !String(campo.value).startsWith("=")) return false;
  const antes = campo.value.slice(0, campo.selectionStart).replace(/\s+$/, "");
  return /[=+\-*/^;(:&<>]$/.test(antes);
}

function plxCampoDeFormula() {
  const a = document.activeElement;
  if (plx.editor && a === plx.editor.campo) return a;
  if (a && a.id === "pl-entrada") return a;
  return null;
}

function plxInserirReferencia(ref, e) {
  const campo = plxCampoDeFormula();
  if (!campo || !plxPedeReferencia(campo)) return false;
  if (plx.editor && campo === plx.editor.campo && ref === plx.editor.ref) return false;
  e.preventDefault();
  const ini = campo.selectionStart;
  campo.value = campo.value.slice(0, ini) + ref + campo.value.slice(campo.selectionEnd);
  campo.setSelectionRange(ini + ref.length, ini + ref.length);
  campo.dispatchEvent(new Event("input"));
  plx.arraste = { tipo: "formula", campo: campo, ini: ini, de: ref, fim: ini + ref.length };
  return true;
}

function plxEsticarReferencia(ref) {
  const a = plx.arraste;
  const campo = a.campo;
  const texto = a.de === ref ? a.de : a.de + ":" + ref;
  campo.value = campo.value.slice(0, a.ini) + texto + campo.value.slice(a.fim);
  a.fim = a.ini + texto.length;
  campo.setSelectionRange(a.fim, a.fim);
  campo.dispatchEvent(new Event("input"));
}

/* ------------------------------------------------ copiar, recortar, colar */

function plxAreaDeTransferencia(e, acao) {
  if (!plxAtiva()) return;
  // Texto selecionado fora da grade (uma fala do painel) copia como sempre.
  const s = window.getSelection ? window.getSelection() : null;
  if (acao !== "colar" && s && !s.isCollapsed && !plxCaixa().contains(s.anchorNode)) return;
  if (acao === "colar") {
    e.preventDefault();
    const texto = e.clipboardData ? e.clipboardData.getData("text/plain") : null;
    plxColar(texto, "tudo");
    return;
  }
  e.preventDefault();
  const texto = plxCopiar(acao === "recortar");
  if (e.clipboardData) e.clipboardData.setData("text/plain", texto);
}

function plxCopiar(recortar) {
  const aba = plxAba();
  const calc = plxCalc();
  let f = plxFaixa();
  // Coluna ou linha inteira: so ate onde ha conteudo.
  if (plx.selTipo) {
    const usado = plxUsado(aba);
    f = { l1: f.l1, c1: f.c1, l2: Math.max(f.l1, Math.min(f.l2, usado.linhas)), c2: Math.max(f.c1, Math.min(f.c2, usado.colunas - 1)) };
  }
  const celulas = [];
  const linhas = [];
  for (let l = f.l1; l <= f.l2; l++) {
    const fila = [], textos = [];
    for (let c = f.c1; c <= f.c2; c++) {
      const ref = plxRef(l, c);
      const cel = aba.celulas[ref] || {};
      const v = calc[ref] || {};
      fila.push({
        l: l, c: c, valor: cel.valor || "", formato: cel.formato || "", negrito: Boolean(cel.negrito),
        italico: Boolean(cel.italico), borda: Boolean(cel.borda), comentario: cel.comentario || "",
        bruto: v.bruto, texto: v.texto || "",
      });
      textos.push(plxCampoTsv(v.texto || ""));
    }
    celulas.push(fila);
    linhas.push(textos.join("\t"));
  }
  const texto = linhas.join("\r\n");
  plx.clip = { doc: escr.pl.id, aba: escr.aba, f: f, celulas: celulas, texto: texto, recortar: recortar, usado: false };
  plxPosicionar();
  return texto;
}

function plxCampoTsv(t) {
  return /[\t\r\n"]/.test(t) ? '"' + t.replace(/"/g, '""') + '"' : t;
}

/* TSV como o Excel poe na area de transferencia: aspas em volta do campo que
   tem tabulacao, quebra de linha ou aspas. */
function plxLerTsv(texto) {
  const linhas = [];
  let fila = [], campo = "", i = 0, aspas = false;
  const t = String(texto).replace(/\r\n?/g, "\n");
  while (i < t.length) {
    const ch = t[i];
    if (aspas) {
      if (ch === '"' && t[i + 1] === '"') { campo += '"'; i += 2; continue; }
      if (ch === '"') { aspas = false; i++; continue; }
      campo += ch; i++; continue;
    }
    if (ch === '"' && campo === "") { aspas = true; i++; continue; }
    if (ch === "\t") { fila.push(campo); campo = ""; i++; continue; }
    if (ch === "\n") { fila.push(campo); linhas.push(fila); fila = []; campo = ""; i++; continue; }
    campo += ch; i++;
  }
  if (campo !== "" || fila.length) { fila.push(campo); linhas.push(fila); }
  return linhas;
}

async function plxLerAreaDeTransferencia() {
  try {
    return await Promise.race([navigator.clipboard.readText(), new Promise((_, nao) => setTimeout(() => nao(new Error("demorou")), 1500))]);
  } catch (err) {
    return null;
  }
}

/* Copiar pelo menu: o comando do navegador dispara o evento "copy", que
   escreve na area de transferencia do sistema - e o Excel aberto ao lado
   recebe a tabela. */
function plxCopiarPeloMenu(recortar) {
  let ok = false;
  try { ok = document.execCommand(recortar ? "cut" : "copy"); } catch (err) { ok = false; }
  if (!ok) {
    const texto = plxCopiar(recortar);
    if (navigator.clipboard) navigator.clipboard.writeText(texto).catch(() => {});
  }
}

async function plxColar(texto, modo) {
  const clip = plx.clip;
  const interno = clip && (texto === null || texto === undefined || texto === "" ||
    texto.replace(/\r\n?/g, "\n").trim() === clip.texto.replace(/\r\n?/g, "\n").trim());
  let matriz;
  if (interno) {
    matriz = clip.celulas;
    if (modo === "transposto") matriz = matriz[0].map((_, j) => matriz.map((fila) => fila[j]));
  } else {
    if (!texto) { avisoCert("não há nada copiado para colar"); return; }
    matriz = plxLerTsv(texto).map((fila) => fila.map((v) => ({ externo: true, valor: v })));
    if (modo === "transposto" && matriz.length) {
      const largura = Math.max(...matriz.map((f) => f.length));
      matriz = Array.from({ length: largura }, (_, j) => matriz.map((fila) => fila[j] || { externo: true, valor: "" }));
    }
  }
  if (!matriz.length || !matriz[0].length) return;

  const lim = plxLimites();
  const f = plxFaixa();
  const R = matriz.length, C = Math.max(...matriz.map((x) => x.length));
  const altura = f.l2 - f.l1 + 1, largura = f.c2 - f.c1 + 1;
  // Selecao que e multiplo do que foi copiado recebe o copiado repetido.
  const vezesL = !plx.selTipo && altura > R && altura % R === 0 ? altura / R : 1;
  const vezesC = !plx.selTipo && largura > C && largura % C === 0 ? largura / C : 1;
  const itens = [];
  const destino = new Set();
  for (let i = 0; i < R * vezesL; i++) {
    for (let j = 0; j < C * vezesC; j++) {
      const s = matriz[i % R][j % C];
      if (!s) continue;
      const l = f.l1 + i, c = f.c1 + j;
      if (l > lim.linhas || c >= lim.colunas) continue;
      const ref = plxRef(l, c);
      destino.add(ref);
      let dados;
      if (s.externo) dados = { valor: s.valor };
      else if (modo === "valores") dados = { valor: plxValorFinal(s) };
      else if (modo === "formatos") dados = { formato: s.formato, negrito: s.negrito, italico: s.italico, borda: s.borda };
      else {
        const valor = clip.recortar ? s.valor : plxDeslocar(s.valor, l - s.l, c - s.c);
        dados = { valor: valor, formato: s.formato, negrito: s.negrito, italico: s.italico, borda: s.borda };
        if (s.comentario || clip.recortar) dados.comentario = s.comentario;
      }
      itens.push({ ref: ref, dados: dados });
    }
  }
  const alvo = { l1: f.l1, c1: f.c1, l2: Math.min(lim.linhas, f.l1 + R * vezesL - 1), c2: Math.min(lim.colunas - 1, f.c1 + C * vezesC - 1) };
  const nota = (interno && clip.recortar ? "moveu " + plxFaixaTexto(clip.f) + " para " : "colou em ") + plxFaixaTexto(alvo);
  const d = await plxLote(itens, nota);
  if (!d) return;

  // Recortar: o que ficou para tras (e nao foi coberto) se esvazia.
  if (interno && clip.recortar && modo === "tudo") {
    const limpar = [];
    clip.celulas.forEach((fila) => fila.forEach((s) => {
      const ref = plxRef(s.l, s.c);
      if (clip.doc === escr.pl.id && clip.aba === escr.aba && destino.has(ref)) return;
      limpar.push({ ref: ref, dados: { valor: "", formato: "", negrito: false, italico: false, borda: false, comentario: "" } });
    }));
    if (clip.doc === escr.pl.id) await plxLote(limpar, "recortou " + plxFaixaTexto(clip.f), clip.aba);
    plx.clip = null;
  }
  plx.selTipo = null;
  escr.ancora = plxRef(alvo.l1, alvo.c1);
  escr.celula = plxRef(alvo.l2, alvo.c2);
  desenharPlanilha();
}

/* O valor que a celula mostra, para "colar valores": a conta vira numero. */
function plxValorFinal(s) {
  if (!String(s.valor).startsWith("=")) return s.valor;
  if (typeof s.bruto === "number") return plxNumTexto(s.bruto);
  if (typeof s.bruto === "boolean") return s.bruto ? "VERDADEIRO" : "FALSO";
  return s.texto;
}

/* Referencia relativa anda com a distancia; a que tem $ fica. Saiu da grade
   vira #REF!, como no Excel. */
const PLX_RE_REF = /(?<![A-Za-z0-9_$.])(\$?)([A-Za-z]{1,2})(\$?)(\d{1,4})(?![0-9A-Za-z_(])/g;

function plxDeslocar(valor, dl, dc) {
  if (!String(valor).startsWith("=") || (!dl && !dc)) return valor;
  const lim = plxLimites();
  return valor.split(/("(?:[^"]|"")*")/).map((pedaco) => {
    if (pedaco.startsWith('"')) return pedaco;
    return pedaco.replace(PLX_RE_REF, (m, d1, col, d2, lin) => {
      let c = letraParaIndice(col.toUpperCase());
      let l = Number(lin);
      if (!d1) c += dc;
      if (!d2) l += dl;
      if (c < 0 || l < 1 || c >= lim.colunas || l > lim.linhas) return "#REF!";
      return d1 + letraColuna(c) + d2 + l;
    });
  }).join("");
}

/* ---------------------------------------------------- a alca de preencher */

function plxArrastarAlca(e) {
  const a = plx.arraste;
  const el = document.elementFromPoint(e.clientX, e.clientY);
  let td = plxCelulaDe(el);
  if (!td) {
    a.alvo = null;
    return;
  }
  const p = plxPos(td.dataset.ref);
  const f = a.f;
  const baixo = p.l > f.l2 ? p.l - f.l2 : 0, cima = p.l < f.l1 ? f.l1 - p.l : 0;
  const direita = p.c > f.c2 ? p.c - f.c2 : 0, esquerda = p.c < f.c1 ? f.c1 - p.c : 0;
  const vertical = Math.max(baixo, cima), horizontal = Math.max(direita, esquerda);
  let alvo = null;
  if (vertical && vertical >= horizontal) {
    alvo = baixo ? { l1: f.l1, l2: p.l, c1: f.c1, c2: f.c2, sentido: "baixo" } : { l1: p.l, l2: f.l2, c1: f.c1, c2: f.c2, sentido: "cima" };
  } else if (horizontal) {
    alvo = direita ? { l1: f.l1, l2: f.l2, c1: f.c1, c2: p.c, sentido: "direita" } : { l1: f.l1, l2: f.l2, c1: p.c, c2: f.c2, sentido: "esquerda" };
  }
  a.alvo = alvo;
  const previa = $("plx-previa");
  plxPor(previa, alvo ? plxRetangulo(alvo) : null);
  if (!alvo) { plxEsconderDica(); return; }
  // A dica mostra o que vai cair na ultima celula - o Excel faz o mesmo.
  const itens = plxItensDoPreenchimento(f, alvo, e.ctrlKey);
  const ultimo = itens.length ? itens[itens.length - 1].dados.valor : "";
  plxMostrarDica(e.clientX, e.clientY, ultimo);
}

function plxMostrarDica(x, y, valor) {
  let dica = $("plx-dica");
  if (!dica) {
    dica = document.createElement("div");
    dica.id = "plx-dica";
    dica.className = "plx-dica";
    document.body.appendChild(dica);
  }
  dica.textContent = String(valor || "").startsWith("=") ? valor : (valor || "(vazio)");
  dica.style.left = (x + 14) + "px";
  dica.style.top = (y + 16) + "px";
  dica.hidden = false;
}

function plxEsconderDica() { const d = $("plx-dica"); if (d) d.hidden = true; }

/* Preenche o alvo a partir da faixa `f`. `inverter` (Ctrl) troca copiar por
   continuar a sequencia e vice-versa, como no Excel. */
function plxItensDoPreenchimento(f, alvo, inverter) {
  const aba = plxAba();
  const itens = [];
  const vertical = alvo.sentido === "baixo" || alvo.sentido === "cima";
  const para = alvo.sentido === "baixo" || alvo.sentido === "direita" ? 1 : -1;
  const trilhos = vertical ? [f.c1, f.c2] : [f.l1, f.l2];
  const k = vertical ? f.l2 - f.l1 + 1 : f.c2 - f.c1 + 1;
  const n = vertical ? (alvo.l2 - alvo.l1 + 1) - k : (alvo.c2 - alvo.c1 + 1) - k;
  if (n <= 0) return itens;
  for (let t = trilhos[0]; t <= trilhos[1]; t++) {
    // As fontes em ordem de preenchimento: para cima e para a esquerda, de tras para frente.
    const fontes = [];
    for (let i = 0; i < k; i++) {
      const pos = vertical ? { l: f.l1 + i, c: t } : { l: t, c: f.c1 + i };
      fontes.push(Object.assign({ l: pos.l, c: pos.c }, aba.celulas[plxRef(pos.l, pos.c)] || { valor: "" }));
    }
    if (para < 0) fontes.reverse();
    const gerados = plxSerie(fontes.map((x) => x.valor || ""), n, inverter);
    for (let i = 0; i < n; i++) {
      const passo = (k + i) * para;
      const inicio = para > 0 ? (vertical ? f.l1 : f.c1) : (vertical ? f.l2 : f.c2);
      const l = vertical ? inicio + passo : t;
      const c = vertical ? t : inicio + passo;
      if (l < 1 || c < 0) continue;
      const g = gerados[i];
      const fonte = fontes[i % k];
      const dados = { formato: fonte.formato || "", negrito: Boolean(fonte.negrito), italico: Boolean(fonte.italico), borda: Boolean(fonte.borda) };
      if (g.copia !== undefined) {
        const s = fontes[g.copia];
        dados.valor = plxDeslocar(s.valor || "", l - s.l, c - s.c);
      } else dados.valor = g.valor;
      itens.push({ ref: plxRef(l, c), dados: dados });
    }
  }
  return itens;
}

async function plxPreencher(f, alvo, inverter) {
  const itens = plxItensDoPreenchimento(f, alvo, inverter);
  if (!itens.length) return;
  const d = await plxLote(itens, "preencheu " + plxFaixaTexto(alvo));
  if (!d) return;
  plx.selTipo = null;
  escr.ancora = plxRef(alvo.l1, alvo.c1);
  escr.celula = plxRef(alvo.l2, alvo.c2);
  desenharPlanilha();
}

/* Clique duplo na alca: desce ate onde vai a coluna vizinha. */
function plxPreencherAteOFim() {
  const aba = plxAba();
  const f = plxFaixa();
  const lim = plxLimites();
  // As duas vizinhas (esquerda e direita); vale a que desce mais.
  const vizinhas = [f.c1 - 1, f.c2 + 1].filter((c) => c >= 0 && plxTem(aba, f.l2, c));
  if (!vizinhas.length) { avisoCert("a alça preenche até onde vai a coluna ao lado — e ela está vazia aqui"); return; }
  const livre = (l) => { for (let c = f.c1; c <= f.c2; c++) if (plxTem(aba, l, c)) return false; return true; };
  let fim = f.l2;
  vizinhas.forEach((v) => {
    let ate = f.l2;
    while (ate < lim.linhas && plxTem(aba, ate + 1, v) && livre(ate + 1)) ate++;
    fim = Math.max(fim, ate);
  });
  if (fim === f.l2) return;
  plxPreencher(f, { l1: f.l1, l2: fim, c1: f.c1, c2: f.c2, sentido: "baixo" }, false);
}

/* Ctrl+D e Ctrl+R copiam a primeira linha (coluna) da selecao para as
   outras; com uma linha so, copiam a de cima (a da esquerda). */
function plxPreencherDaPrimeira(sentido) {
  const f = plxFaixa();
  if (sentido === "baixo") {
    const l0 = f.l2 === f.l1 ? f.l1 - 1 : f.l1;
    if (l0 < 1) return;
    plxPreencher({ l1: l0, l2: l0, c1: f.c1, c2: f.c2 }, { l1: l0, l2: f.l2, c1: f.c1, c2: f.c2, sentido: "baixo" }, "copiar");
  } else {
    const c0 = f.c2 === f.c1 ? f.c1 - 1 : f.c1;
    if (c0 < 0) return;
    plxPreencher({ l1: f.l1, l2: f.l2, c1: c0, c2: c0 }, { l1: f.l1, l2: f.l2, c1: c0, c2: f.c2, sentido: "direita" }, "copiar");
  }
}

/* ----------------------------------------------------------- sequencias

   Recebe os valores de origem (na ordem em que o preenchimento anda) e
   quantos gerar. Devolve, para cada um, { valor } ou { copia: j } (copiar a
   origem j, com a formula ajustada). */

const PLX_MESES = ["janeiro", "fevereiro", "março", "abril", "maio", "junho", "julho", "agosto", "setembro", "outubro", "novembro", "dezembro"];
const PLX_MESES_CURTOS = ["jan", "fev", "mar", "abr", "mai", "jun", "jul", "ago", "set", "out", "nov", "dez"];
const PLX_DIAS = ["domingo", "segunda-feira", "terça-feira", "quarta-feira", "quinta-feira", "sexta-feira", "sábado"];
const PLX_DIAS_MEIOS = ["domingo", "segunda", "terça", "quarta", "quinta", "sexta", "sábado"];
const PLX_DIAS_CURTOS = ["dom", "seg", "ter", "qua", "qui", "sex", "sáb"];
const PLX_LISTAS = [PLX_MESES, PLX_MESES_CURTOS, PLX_DIAS, PLX_DIAS_MEIOS, PLX_DIAS_CURTOS];

function plxSemAcento(t) {
  return String(t).normalize("NFD").replace(/[̀-ͯ]/g, "").toLowerCase().replace(/\.$/, "").trim();
}

function plxCaixaDoTexto(modelo, texto) {
  if (modelo === modelo.toUpperCase() && modelo !== modelo.toLowerCase()) return texto.toUpperCase();
  if (modelo[0] === modelo[0].toUpperCase() && modelo[0] !== modelo[0].toLowerCase()) return texto[0].toUpperCase() + texto.slice(1);
  return texto;
}

function plxNumeroBr(t) {
  const s = String(t).trim();
  const m = /^(-?)(\d{1,3}(?:\.\d{3})+|\d+)(?:,(\d+))?$/.exec(s);
  if (!m) return null;
  const n = Number(m[2].replace(/\./g, "") + (m[3] ? "." + m[3] : "")) * (m[1] ? -1 : 1);
  return { n: n, casas: m[3] ? m[3].length : 0, milhar: m[2].includes(".") };
}

function plxNumTexto(n, casas, milhar) {
  let s = casas === undefined ? String(Math.round(n * 1e10) / 1e10) : n.toFixed(casas);
  const neg = s.startsWith("-");
  if (neg) s = s.slice(1);
  let [i, d] = s.split(".");
  if (milhar) i = i.replace(/\B(?=(\d{3})+(?!\d))/g, ".");
  return (neg ? "-" : "") + i + (d ? "," + d : "");
}

function plxData(t) {
  const m = /^(\d{1,2})\/(\d{1,2})\/(\d{4})$/.exec(String(t).trim());
  if (!m) return null;
  const d = new Date(Number(m[3]), Number(m[2]) - 1, Number(m[1]));
  return d.getDate() === Number(m[1]) ? { d: d, curto: m[1].length === 1 && m[2].length === 1 } : null;
}

function plxDataTexto(d, curto) {
  const dd = String(d.getDate()), mm = String(d.getMonth() + 1);
  return (curto ? dd : dd.padStart(2, "0")) + "/" + (curto ? mm : mm.padStart(2, "0")) + "/" + d.getFullYear();
}

/* Passo linear pelos minimos quadrados: com dois valores e a diferenca
   exata; com mais, a tendencia - como o Excel. */
function plxTendencia(ys) {
  const k = ys.length;
  if (k === 1) return { a: ys[0], b: 1 };
  const mx = (k - 1) / 2;
  const my = ys.reduce((s, y) => s + y, 0) / k;
  let num = 0, den = 0;
  ys.forEach((y, x) => { num += (x - mx) * (y - my); den += (x - mx) * (x - mx); });
  const b = den ? num / den : 0;
  return { a: my - b * mx, b: b };
}

function plxSerie(valores, n, inverter) {
  const k = valores.length;
  const copiar = () => Array.from({ length: n }, (_, i) => ({ copia: (k + i) % k }));
  if (inverter === "copiar" || !k || valores.some((v) => String(v).startsWith("=")) || valores.every((v) => v === "")) return copiar();

  // Numeros: um so copia (Ctrl faz sequencia); dois ou mais continuam.
  const nums = valores.map(plxNumeroBr);
  if (nums.every(Boolean)) {
    const serie = k > 1 ? !inverter : inverter;
    if (!serie) return copiar();
    const t = plxTendencia(nums.map((x) => x.n));
    const casas = Math.max(...nums.map((x) => x.casas), plxCasasDe(t.b));
    const milhar = nums.some((x) => x.milhar);
    return Array.from({ length: n }, (_, i) => ({ valor: plxNumTexto(t.a + t.b * (k + i), casas, milhar) }));
  }
  if (inverter) return copiar();

  // Datas: dia a dia, ou mes a mes se todas caem no mesmo dia do mes.
  const datas = valores.map(plxData);
  if (datas.every(Boolean)) {
    const curto = datas[0].curto;
    const ds = datas.map((x) => x.d);
    const mesmoDia = k > 1 && ds.every((d) => d.getDate() === ds[0].getDate());
    const meses = (a, b) => (b.getFullYear() - a.getFullYear()) * 12 + b.getMonth() - a.getMonth();
    if (mesmoDia && meses(ds[0], ds[1]) !== 0) {
      const passo = meses(ds[0], ds[1]);
      return Array.from({ length: n }, (_, i) => {
        const d = new Date(ds[0].getFullYear(), ds[0].getMonth() + passo * (k + i), 1);
        const ultimo = new Date(d.getFullYear(), d.getMonth() + 1, 0).getDate();
        d.setDate(Math.min(ds[0].getDate(), ultimo));
        return { valor: plxDataTexto(d, curto) };
      });
    }
    const dias = ds.map((d) => Math.round(d.getTime() / 86400000));
    const t = plxTendencia(dias);
    return Array.from({ length: n }, (_, i) => {
      const d = new Date(Math.round(t.a + t.b * (k + i)) * 86400000);
      return { valor: plxDataTexto(new Date(d.getUTCFullYear(), d.getUTCMonth(), d.getUTCDate()), curto) };
    });
  }

  // Meses e dias da semana, na lista em que o primeiro valor esta.
  const chaves = valores.map(plxSemAcento);
  for (const lista of PLX_LISTAS) {
    const normal = lista.map(plxSemAcento);
    const idx = chaves.map((c) => normal.indexOf(c));
    if (idx.every((i) => i >= 0)) {
      const m = lista.length;
      const passo = k > 1 ? ((idx[1] - idx[0]) % m + m) % m || m : 1;
      const modelo = String(valores[0]).trim();
      const ponto = /\.$/.test(modelo) ? "." : "";
      return Array.from({ length: n }, (_, i) => {
        const j = ((idx[k - 1] + passo * (i + 1)) % m + m) % m;
        return { valor: plxCaixaDoTexto(modelo, lista[j]) + ponto };
      });
    }
  }

  // Texto com numero no fim: "Item 1", "Parcela 01".
  const partes = valores.map((v) => /^(.*\D)(\d+)$/.exec(String(v)));
  if (partes.every(Boolean) && partes.every((p) => p[1] === partes[0][1])) {
    const ns = partes.map((p) => Number(p[2]));
    const t = plxTendencia(ns);
    const passo = k > 1 ? Math.round(t.b) : 1;
    const largura = partes[0][2].length;
    const zero = partes[0][2].startsWith("0");
    return Array.from({ length: n }, (_, i) => {
      const x = Math.max(0, ns[k - 1] + passo * (i + 1));
      return { valor: partes[0][1] + (zero ? String(x).padStart(largura, "0") : String(x)) };
    });
  }
  return copiar();
}

function plxCasasDe(x) {
  if (Number.isInteger(x)) return 0;
  const s = String(Math.round(x * 1e6) / 1e6);
  return s.includes(".") ? Math.min(6, s.split(".")[1].length) : 0;
}

/* --------------------------------------------------- classificar e filtrar */

/* A tabela em volta da celula: o bloco de celulas preenchidas ligado a ela
   (o "região atual" do Excel). */
function plxRegiao(l, c) {
  const aba = plxAba();
  let f = { l1: l, l2: l, c1: c, c2: c };
  const temNaLinha = (x, a, b) => { for (let y = a; y <= b; y++) if (plxTem(aba, x, y)) return true; return false; };
  const temNaColuna = (y, a, b) => { for (let x = a; x <= b; x++) if (plxTem(aba, x, y)) return true; return false; };
  let mudou = true;
  while (mudou) {
    mudou = false;
    const a = Math.max(0, f.c1 - 1), b = f.c2 + 1;
    if (f.l1 > 1 && temNaLinha(f.l1 - 1, a, b)) { f.l1--; mudou = true; }
    if (temNaLinha(f.l2 + 1, a, b)) { f.l2++; mudou = true; }
    const x1 = Math.max(1, f.l1 - 1), x2 = f.l2 + 1;
    if (f.c1 > 0 && temNaColuna(f.c1 - 1, x1, x2)) { f.c1--; mudou = true; }
    if (temNaColuna(f.c2 + 1, x1, x2)) { f.c2++; mudou = true; }
  }
  // A celula sozinha e vazia nao e tabela.
  if (f.l1 === f.l2 && f.c1 === f.c2 && !plxTem(aba, l, c)) return null;
  return f;
}

/* A tabela a usar para classificar ou filtrar pela coluna `c`. */
function plxTabelaPara(c) {
  const f = plxFaixa();
  if (!plx.selTipo && f.l2 > f.l1) return f;
  const aba = plxAba();
  let l = plxPos(plxCelulaDoMenu()).l;
  if (plx.selTipo === "colunas" || !plxTem(aba, l, c)) {
    const usadas = Object.keys(aba.celulas).map(plxPos).filter((p) => p.c === c && plxTem(aba, p.l, p.c)).map((p) => p.l);
    if (!usadas.length) return null;
    l = Math.min(...usadas);
  }
  return plxRegiao(l, c);
}

function plxTemCabecalho(f) {
  if (f.l2 <= f.l1) return false;
  const aba = plxAba();
  const calc = plxCalc();
  let textos = 0, negrito = false, numeroAbaixo = false;
  for (let c = f.c1; c <= f.c2; c++) {
    const ref = plxRef(f.l1, c);
    const v = calc[ref];
    if (!v || v.texto === "") continue;
    if (typeof v.bruto === "number") return false;
    textos += 1;
    if ((aba.celulas[ref] || {}).negrito) negrito = true;
    for (let l = f.l1 + 1; l <= f.l2 && !numeroAbaixo; l++) {
      const w = calc[plxRef(l, c)];
      if (w && typeof w.bruto === "number") numeroAbaixo = true;
    }
  }
  return textos > 0 && (negrito || aba.congelar_cabecalho || numeroAbaixo);
}

async function plxClassificar(crescente) {
  const c = plxPos(plxCelulaDoMenu()).c;
  const f = plxTabelaPara(c);
  if (!f || f.l2 === f.l1) { avisoCert("não achei uma tabela com mais de uma linha aqui"); return; }
  const cabecalho = plxTemCabecalho(f);
  const r = await fetch("/api/planilha/" + escr.pl.id + "/ordenar", {
    method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ aba: escr.aba, faixa: plxFaixaTexto(f), coluna: letraColuna(c), crescente: crescente, com_cabecalho: cabecalho }),
  });
  if (!r.ok) { avisoCert(await erroDe(r), { tom: "erro" }); return; }
  const d = await r.json();
  escr.pl = d;
  escr.filtro = null;
  plx.clip = null;
  plx.selTipo = null;
  escr.ancora = plxRef(f.l1, f.c1);
  escr.celula = plxRef(f.l2, f.c2);
  desenharPlanilha();
  avisoCert(plxFaixaTexto(f) + " classificada pela coluna " + letraColuna(c) + (crescente ? " (A→Z)" : " (Z→A)") +
    (cabecalho ? " · a linha " + f.l1 + " ficou como cabeçalho" : ""), { tom: "ok" });
}

async function plxFiltrarPeloValor() {
  const ref = plxCelulaDoMenu();
  const p = plxPos(ref);
  const f = plxRegiao(p.l, p.c);
  if (!f || f.l2 === f.l1) { avisoCert("não achei uma tabela com mais de uma linha aqui"); return; }
  const cel = plxAba().celulas[ref];
  const v = plxCalc()[ref];
  const criterio = cel && !String(cel.valor).startsWith("=") ? cel.valor : (v ? v.texto : "");
  const r = await fetch("/api/planilha/" + escr.pl.id + "/filtrar", {
    method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ aba: escr.aba, faixa: plxFaixaTexto(f), coluna: letraColuna(p.c), criterio: criterio, com_cabecalho: plxTemCabecalho(f) }),
  });
  if (!r.ok) { avisoCert(await erroDe(r), { tom: "erro" }); return; }
  escr.filtro = await r.json();
  desenharPlanilha();
}

function plxAbrirPainel(acao) {
  const c = plxPos(plxCelulaDoMenu()).c;
  const f = plxTabelaPara(c);
  if (f) plxSelecionar(plxRef(f.l1, f.c1), plxRef(f.l2, f.c2));
  painelTabela(acao);
}

/* A celula em que o botao direito foi apertado. Dentro de uma selecao maior
   ela nao vira a ativa (a selecao fica), mas e dela que o comentario, o
   filtro e a coluna de classificar falam. */
function plxCelulaDoMenu() { return plx.alvoDoMenu || escr.celula; }

async function plxGravarEm(ref, dados) {
  const r = await fetch("/api/planilha/" + escr.pl.id + "/celula", {
    method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ aba: escr.aba, ref: ref, dados: dados }),
  });
  if (!r.ok) { avisoCert(await erroDe(r), { tom: "erro" }); return; }
  escr.pl = await r.json();
  desenharPlanilha();
}

async function plxComentario() {
  const aba = plxAba();
  const ref = plxCelulaDoMenu();
  const cel = aba.celulas[ref] || {};
  const texto = await perguntar({
    titulo: cel.comentario ? "Editar comentário" : "Inserir comentário",
    contexto: "Planilha › " + aba.nome + " › " + ref,
    campo: { rotulo: "Comentário", valor: cel.comentario || "", placeholder: "uma nota para quem abrir a planilha", icone: "comment", max: 2000 },
    confirmar: "Guardar",
  });
  if (texto === null) return;
  plxGravarEm(ref, { comentario: texto });
}

async function plxCongelar() {
  const aba = plxAba();
  const r = await fetch("/api/planilha/" + escr.pl.id + "/congelar", {
    method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ aba: escr.aba, congelar: !aba.congelar_cabecalho }),
  });
  if (!r.ok) { avisoCert(await erroDe(r), { tom: "erro" }); return; }
  escr.pl = await r.json();
  desenharPlanilha();
}

/* ------------------------------------------------------ o menu do botao direito */

function plxAoMenu(e) {
  e.preventDefault();
  const alvo = e.target;
  if (alvo.closest("[data-borda-c], [data-borda-l], .plx-alca")) return;
  let onde = "celula";
  const th = alvo.closest("th[data-c]");
  const cabL = alvo.closest("td[data-linha]");
  const td = plxCelulaDe(alvo);
  if (th) { onde = "coluna"; plx.alvoDoMenu = plxRef(1, Number(th.dataset.c)); }
  else if (cabL) { onde = "linha"; plx.alvoDoMenu = plxRef(Number(cabL.dataset.linha), 0); }
  else if (alvo.closest("[data-canto]")) { onde = "coluna"; plx.alvoDoMenu = null; }
  else if (td) plx.alvoDoMenu = td.dataset.ref;
  else return;
  if (plx.editor) plxFecharEditor(true);
  plxAbrirMenu(e.clientX, e.clientY, onde);
}

function plxItensDoMenu(onde) {
  const aba = plxAba();
  const f = plxFaixa();
  const cel = aba.celulas[plxCelulaDoMenu()] || {};
  const nl = f.l2 - f.l1 + 1, nc = f.c2 - f.c1 + 1;
  const linhasTxt = (n) => (n === 1 ? "1 linha" : n + " linhas");
  const colunasTxt = (n) => (n === 1 ? "1 coluna" : n + " colunas");
  const temClip = Boolean(plx.clip);
  const formatar = [
    { rotulo: "Texto", acao: () => aplicarNaFaixa({ formato: "" }), atual: !cel.formato },
    { rotulo: "Número (0,00)", acao: () => aplicarNaFaixa({ formato: "numero" }), atual: cel.formato === "numero" },
    { rotulo: "Moeda (R$)", acao: () => aplicarNaFaixa({ formato: "moeda" }), atual: cel.formato === "moeda" },
    { rotulo: "Porcentagem (%)", acao: () => aplicarNaFaixa({ formato: "porcento" }), atual: cel.formato === "porcento" },
    { rotulo: "Data", acao: () => aplicarNaFaixa({ formato: "data" }), atual: cel.formato === "data" },
    "-",
    { rotulo: cel.negrito ? "Tirar negrito" : "Negrito", atalho: "Ctrl+B", acao: () => aplicarNaFaixa({ negrito: !cel.negrito }) },
    { rotulo: cel.italico ? "Tirar itálico" : "Itálico", atalho: "Ctrl+I", acao: () => aplicarNaFaixa({ italico: !cel.italico }) },
    { rotulo: cel.borda ? "Tirar bordas" : "Bordas", acao: () => aplicarNaFaixa({ borda: !cel.borda }) },
  ];
  const colar = [
    { rotulo: "Colar valores", acao: () => plxColarPeloMenu("valores") },
    { rotulo: "Colar só a formatação", acao: () => plxColarPeloMenu("formatos"), desativado: !temClip },
    { rotulo: "Colar transposto", acao: () => plxColarPeloMenu("transposto") },
  ];
  const base = [
    { rotulo: "Recortar", atalho: "Ctrl+X", acao: () => plxCopiarPeloMenu(true) },
    { rotulo: "Copiar", atalho: "Ctrl+C", acao: () => plxCopiarPeloMenu(false) },
    { rotulo: "Colar", atalho: "Ctrl+V", acao: () => plxColarPeloMenu("tudo") },
    { rotulo: "Colar especial", sub: colar },
    "-",
  ];
  const limpar = [
    { rotulo: "Limpar conteúdo", atalho: "Delete", acao: () => plxLimpar("conteudo") },
    { rotulo: "Limpar formatação", acao: () => plxLimpar("formatos") },
  ];

  if (onde === "coluna") {
    const ocultas = plxOcultasPerto("colunas", f.c1, f.c2);
    return base.concat([
      { rotulo: "Inserir " + colunasTxt(nc) + " à esquerda", acao: () => plxEstrutura("colunas", "inserir", f.c1, nc) },
      { rotulo: "Inserir " + colunasTxt(nc) + " à direita", acao: () => plxEstrutura("colunas", "inserir", f.c2 + 1, nc) },
      { rotulo: "Excluir " + (nc === 1 ? "coluna" : nc + " colunas"), perigo: true, acao: () => plxEstrutura("colunas", "excluir", f.c1, nc) },
    ], limpar, ["-",
      { rotulo: "Classificar A → Z", acao: () => plxClassificar(true) },
      { rotulo: "Classificar Z → A", acao: () => plxClassificar(false) },
      { rotulo: "Filtrar…", acao: () => plxAbrirPainel("filtrar") },
      { rotulo: "Formatar células", sub: formatar },
      "-",
      { rotulo: "Largura da coluna…", acao: () => plxPedirMedida("colunas") },
      { rotulo: "Ajustar largura ao conteúdo", acao: () => plxAutoAjustar(plxVisiveisC(f.c1, f.c2)) },
      { rotulo: "Ocultar", acao: () => plxOcultar("colunas") },
      ocultas.length ? { rotulo: "Reexibir", acao: () => plxReexibirPerto("colunas", f.c1, f.c2) } : null,
      (aba.colunas_ocultas || []).length ? { rotulo: "Reexibir todas as colunas", acao: () => plxReexibirTodas("colunas") } : null,
    ]).filter(Boolean);
  }
  if (onde === "linha") {
    const ocultas = plxOcultasPerto("linhas", f.l1, f.l2);
    return base.concat([
      { rotulo: "Inserir " + linhasTxt(nl) + " acima", acao: () => plxEstrutura("linhas", "inserir", f.l1, nl) },
      { rotulo: "Inserir " + linhasTxt(nl) + " abaixo", acao: () => plxEstrutura("linhas", "inserir", f.l2 + 1, nl) },
      { rotulo: "Excluir " + (nl === 1 ? "linha" : nl + " linhas"), perigo: true, acao: () => plxEstrutura("linhas", "excluir", f.l1, nl) },
    ], limpar, ["-",
      { rotulo: "Formatar células", sub: formatar },
      "-",
      { rotulo: "Altura da linha…", acao: () => plxPedirMedida("linhas") },
      { rotulo: "Ajustar altura ao conteúdo", acao: () => { const a = {}; plxVisiveisL(f.l1, f.l2).forEach((l) => { a[String(l)] = null; }); plxLayout({ alturas: a }, true); } },
      { rotulo: "Ocultar", acao: () => plxOcultar("linhas") },
      ocultas.length ? { rotulo: "Reexibir", acao: () => plxReexibirPerto("linhas", f.l1, f.l2) } : null,
      (aba.linhas_ocultas || []).length ? { rotulo: "Reexibir todas as linhas", acao: () => plxReexibirTodas("linhas") } : null,
      "-",
      { rotulo: aba.congelar_cabecalho ? "Descongelar a primeira linha" : "Congelar a primeira linha", acao: plxCongelar },
    ]).filter(Boolean);
  }

  const juntada = cel.juntar > 1;
  return base.concat([
    { rotulo: "Inserir", sub: [
      { rotulo: "Inserir " + linhasTxt(nl) + " acima", acao: () => plxEstrutura("linhas", "inserir", f.l1, nl) },
      { rotulo: "Inserir " + linhasTxt(nl) + " abaixo", acao: () => plxEstrutura("linhas", "inserir", f.l2 + 1, nl) },
      { rotulo: "Inserir " + colunasTxt(nc) + " à esquerda", acao: () => plxEstrutura("colunas", "inserir", f.c1, nc) },
      { rotulo: "Inserir " + colunasTxt(nc) + " à direita", acao: () => plxEstrutura("colunas", "inserir", f.c2 + 1, nc) },
    ] },
    { rotulo: "Excluir", sub: [
      { rotulo: nl === 1 ? "Excluir a linha " + f.l1 : "Excluir as linhas " + f.l1 + " a " + f.l2, perigo: true, acao: () => plxEstrutura("linhas", "excluir", f.l1, nl) },
      { rotulo: nc === 1 ? "Excluir a coluna " + letraColuna(f.c1) : "Excluir as colunas " + letraColuna(f.c1) + " a " + letraColuna(f.c2), perigo: true, acao: () => plxEstrutura("colunas", "excluir", f.c1, nc) },
    ] },
  ], limpar, ["-",
    { rotulo: "Classificar", sub: [
      { rotulo: "Classificar A → Z", acao: () => plxClassificar(true) },
      { rotulo: "Classificar Z → A", acao: () => plxClassificar(false) },
      { rotulo: "Classificação personalizada…", acao: () => plxAbrirPainel("ordenar") },
    ] },
    { rotulo: "Filtrar", sub: [
      { rotulo: "Pelo valor desta célula", acao: plxFiltrarPeloValor },
      { rotulo: "Filtro…", acao: () => plxAbrirPainel("filtrar") },
      escr.filtro ? { rotulo: "Limpar o filtro", acao: () => { escr.filtro = null; desenharPlanilha(); } } : null,
    ].filter(Boolean) },
    "-",
    { rotulo: "Formatar células", sub: formatar },
    { rotulo: juntada ? "Desfazer mesclagem" : "Mesclar células", acao: juntarCelulas, desativado: !juntada && nc < 2 },
    { rotulo: cel.comentario ? "Editar comentário…" : "Inserir comentário…", acao: plxComentario },
    cel.comentario ? { rotulo: "Excluir comentário", acao: () => plxGravarEm(plxCelulaDoMenu(), { comentario: "" }) } : null,
    "-",
    { rotulo: "Preencher para baixo", atalho: "Ctrl+D", acao: () => plxPreencherDaPrimeira("baixo") },
    { rotulo: "Preencher à direita", atalho: "Ctrl+R", acao: () => plxPreencherDaPrimeira("direita") },
    { rotulo: "Montar gráfico da seleção", acao: desenharGrafico },
    { rotulo: aba.congelar_cabecalho ? "Descongelar a primeira linha" : "Congelar a primeira linha", acao: plxCongelar },
  ]).filter(Boolean);
}

async function plxColarPeloMenu(modo) {
  const texto = await plxLerAreaDeTransferencia();
  plxColar(texto, modo);
}

function plxAbrirMenu(x, y, onde) {
  plxFecharMenu();
  const itens = plxItensDoMenu(onde);
  const menu = plxMontarMenu(itens, false);
  document.body.appendChild(menu);
  plxColocar(menu, x, y);
  plx.menu = { raiz: menu, itens: itens, foco: -1 };
  setTimeout(() => document.addEventListener("mousedown", plxForaDoMenu, true), 0);
}

function plxMontarMenu(itens, sub) {
  const menu = document.createElement("div");
  menu.className = "menu-conversa plx-menu" + (sub ? " plx-sub" : "");
  menu.setAttribute("role", "menu");
  menu.innerHTML = itens.map((it, i) => {
    if (it === "-") return '<div class="menu-risco"></div>';
    const classe = [it.perigo ? "perigo" : "", it.atual ? "atual" : ""].filter(Boolean).join(" ");
    return '<button type="button" role="menuitem" data-plx-i="' + i + '"' + (classe ? ' class="' + classe + '"' : "") +
      (it.desativado ? " disabled" : "") + '><span class="plx-rotulo">' + esc(it.rotulo) + "</span>" +
      (it.atalho ? '<span class="plx-atalho">' + esc(it.atalho) + "</span>" : "") +
      (it.sub ? '<span class="seta">›</span>' : "") + "</button>";
  }).join("");
  menu.querySelectorAll("[data-plx-i]").forEach((b) => {
    const it = itens[Number(b.dataset.plxI)];
    b.onmouseenter = () => {
      menu.querySelectorAll(":scope > .plx-aberto").forEach((x) => x.classList.remove("plx-aberto"));
      if (!sub) plxFecharSub();
      if (it.sub) plxAbrirSub(b, it.sub);
    };
    b.onclick = (e) => {
      e.stopPropagation();
      if (it.sub) { plxAbrirSub(b, it.sub); return; }
      plxFecharMenu();
      if (it.acao) it.acao();
    };
  });
  return menu;
}

function plxAbrirSub(botao, itens) {
  if (!plx.menu) return;
  if (plx.menu.sub && plx.menu.sub.botao === botao) return;
  plxFecharSub();
  const sub = plxMontarMenu(itens, true);
  document.body.appendChild(sub);
  botao.classList.add("plx-aberto");
  const r = botao.getBoundingClientRect();
  sub.style.left = (r.right + 4) + "px";
  sub.style.top = (r.top - 6) + "px";
  const caixa = sub.getBoundingClientRect();
  if (caixa.right > innerWidth - 8) sub.style.left = Math.max(8, r.left - caixa.width - 4) + "px";
  if (caixa.bottom > innerHeight - 8) sub.style.top = Math.max(8, innerHeight - caixa.height - 8) + "px";
  plx.menu.sub = { raiz: sub, botao: botao, itens: itens, foco: -1 };
}

function plxFecharSub() {
  if (plx.menu && plx.menu.sub) {
    plx.menu.sub.raiz.remove();
    plx.menu.sub.botao.classList.remove("plx-aberto");
    plx.menu.sub = null;
  }
}

function plxColocar(menu, x, y) {
  menu.style.left = x + "px";
  menu.style.top = y + "px";
  const r = menu.getBoundingClientRect();
  if (r.right > innerWidth - 8) menu.style.left = Math.max(8, x - r.width) + "px";
  if (r.bottom > innerHeight - 8) menu.style.top = Math.max(8, Math.min(y - r.height, innerHeight - r.height - 8)) + "px";
}

function plxForaDoMenu(e) {
  if (!plx.menu) return;
  if (e.target.closest && e.target.closest(".plx-menu")) return;
  plxFecharMenu();
}

function plxFecharMenu() {
  if (!plx.menu) return;
  plxFecharSub();
  plx.menu.raiz.remove();
  plx.menu = null;
  document.removeEventListener("mousedown", plxForaDoMenu, true);
}

/* Setas, Enter e Esc dentro do menu. */
function plxTeclaNoMenu(e) {
  const m = plx.menu;
  const nivel = m.sub && m.sub.foco >= 0 ? m.sub : m;
  const botoes = Array.from(nivel.raiz.querySelectorAll(":scope > button:not(:disabled)"));
  const atual = botoes.indexOf(document.activeElement);
  if (e.key === "Escape") {
    e.preventDefault();
    if (nivel === m.sub) { const b = m.sub.botao; plxFecharSub(); b.focus(); } else plxFecharMenu();
  } else if (e.key === "ArrowDown" || e.key === "ArrowUp") {
    e.preventDefault();
    const i = atual < 0 ? (e.key === "ArrowDown" ? 0 : botoes.length - 1) : (atual + (e.key === "ArrowDown" ? 1 : -1) + botoes.length) % botoes.length;
    if (botoes[i]) { botoes[i].focus(); nivel.foco = i; }
  } else if (e.key === "ArrowRight" && atual >= 0) {
    const it = nivel.itens[Number(botoes[atual].dataset.plxI)];
    if (it && it.sub && nivel === m) {
      e.preventDefault();
      plxAbrirSub(botoes[atual], it.sub);
      const primeiro = m.sub.raiz.querySelector("button:not(:disabled)");
      if (primeiro) { primeiro.focus(); m.sub.foco = 0; }
    }
  } else if (e.key === "ArrowLeft" && nivel === m.sub) {
    e.preventDefault();
    const b = m.sub.botao;
    plxFecharSub();
    b.focus();
  } else if (e.key === "Enter" && atual >= 0) {
    e.preventDefault();
    botoes[atual].click();
  } else if (e.key === "Tab") {
    e.preventDefault();
  }
}
