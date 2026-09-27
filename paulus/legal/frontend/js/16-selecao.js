/* ------------------------------------------------------------- selecao */
/*
   Selecao multipla nas listas (docs/ui/05-interacoes-e-estados.md e o
   pedido de "clicar e segurar"): segurar o botao numa linha por meio
   segundo entra no modo de selecao e marca a linha; dai cada clique marca
   ou desmarca, Shift+clique marca o intervalo, Ctrl+clique marca sem
   precisar segurar. Esc limpa, Delete manda a selecao para a lixeira, F2
   renomeia a que esta marcada sozinha, Ctrl+A marca todas.

   Cada tela guarda o seu conjunto de ids e desenha a propria barra
   ("3 selecionadas · Apagar · Limpar"); o que e comum - o gesto, as
   teclas, o intervalo, apagar em lote com um Desfazer so - esta aqui.

   ligarSelecao(raiz, {
     linhas: seletor das linhas dentro da raiz,
     chave(linha): o id da linha (padrao: data-sel),
     escolhidos: Set com os ids marcados, guardado no estado da tela,
     aoMudar(): redesenha a barra e as linhas,
     apagar(ids): Delete (opcional),
     renomear(id): F2 (opcional),
   })
*/

const SEGURAR_MS = 450;
let selecaoAtiva = null;

function ligarSelecao(raiz, o) {
  if (!raiz) return null;
  const chave = o.chave || ((linha) => linha.dataset.sel);
  const sel = { raiz: raiz, o: o, ancora: null, ultimo: null, chave: chave };
  const linhas = () => Array.from(raiz.querySelectorAll(o.linhas));
  const marcar = (linha) => {
    const id = chave(linha);
    if (o.escolhidos.has(id)) o.escolhidos.delete(id); else o.escolhidos.add(id);
    sel.ancora = id;
    selecaoAtiva = sel;
    o.aoMudar();
  };
  const intervalo = (linha) => {
    const ids = linhas().map(chave);
    const a = ids.indexOf(sel.ancora);
    const b = ids.indexOf(chave(linha));
    if (a < 0 || b < 0) { marcar(linha); return; }
    for (let i = Math.min(a, b); i <= Math.max(a, b); i++) o.escolhidos.add(ids[i]);
    selecaoAtiva = sel;
    o.aoMudar();
  };
  const dentroDeControle = (alvo) => alvo && alvo.closest && alvo.closest("button, input, select, textarea, a, .marcar");

  linhas().forEach((linha) => {
    linha.classList.toggle("escolhida", o.escolhidos.has(chave(linha)));
    let relogio = null;
    let segurou = false;
    const cancelar = () => { clearTimeout(relogio); relogio = null; };
    linha.addEventListener("pointerdown", (e) => {
      if (e.button !== 0 || dentroDeControle(e.target)) return;
      sel.ultimo = chave(linha);
      selecaoAtiva = sel;
      segurou = false;
      relogio = setTimeout(() => { relogio = null; segurou = true; marcar(linha); }, SEGURAR_MS);
    });
    ["pointerup", "pointerleave", "pointercancel"].forEach((ev) => linha.addEventListener(ev, cancelar));
    linha.addEventListener("pointermove", (e) => { if (relogio && Math.abs(e.movementX) + Math.abs(e.movementY) > 6) cancelar(); });
    linha.addEventListener("click", (e) => {
      if (dentroDeControle(e.target)) return;
      if (segurou) { segurou = false; e.preventDefault(); e.stopImmediatePropagation(); return; }
      if (e.shiftKey && (o.escolhidos.size || sel.ancora)) { e.preventDefault(); e.stopImmediatePropagation(); intervalo(linha); return; }
      if (e.ctrlKey || e.metaKey || o.escolhidos.size) { e.preventDefault(); e.stopImmediatePropagation(); marcar(linha); return; }
      selecaoAtiva = sel;
    }, true);
  });
  raiz.classList.toggle("selecionando", o.escolhidos.size > 0);
  if (o.escolhidos.size) selecaoAtiva = sel;
  return sel;
}

/* Delete, Esc, F2 e Ctrl+A valem para a lista que foi tocada por ultimo. */
document.addEventListener("keydown", (e) => {
  const alvo = e.target;
  if (alvo && (alvo.tagName === "INPUT" || alvo.tagName === "TEXTAREA" || alvo.isContentEditable)) return;
  if (document.getElementById("veu-dialogo")) return;
  const s = selecaoAtiva;
  if (!s || !document.contains(s.raiz)) return;
  const o = s.o;
  if (e.key === "Escape" && o.escolhidos.size) { o.escolhidos.clear(); o.aoMudar(); return; }
  if (e.key === "Delete" && o.escolhidos.size && o.apagar) { e.preventDefault(); o.apagar([...o.escolhidos]); return; }
  if (e.key === "F2" && o.renomear) {
    const id = o.escolhidos.size === 1 ? [...o.escolhidos][0] : (o.escolhidos.size ? null : s.ultimo);
    if (id) { e.preventDefault(); o.renomear(id); }
    return;
  }
  if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "a" && o.escolhidos.size) {
    e.preventDefault();
    s.raiz.querySelectorAll(o.linhas).forEach((linha) => o.escolhidos.add(s.chave(linha)));
    o.aoMudar();
  }
});

/* A barra de selecao que as listas mostram no lugar dos filtros: a caixa, a
   contagem e as acoes da tela. A caixa E o "selecionar todas / limpar": com
   parte marcada ela mostra o traco e marca todas; com todas marcadas mostra
   o check e limpa. Esc tambem limpa. `atributoLimpar` ficou por
   compatibilidade - o Limpar em texto saiu (26/09/2026, pedido do usuario:
   uma forma so em todas as listas, a do Assistente). Com `total`, a caixa ja
   nasce no estado certo; sem ele, sincronizarBarraDeSelecao acerta. */
function barraDeSelecao(quantos, feminino, acoes, atributoLimpar, total) {
  const todas = total !== undefined && quantos >= total;
  return '<span class="selecao">' + caixaDaSelecao(todas, feminino) +
    '<span class="selecao-conta">' + plural(quantos, feminino ? "selecionada" : "selecionado") + "</span>" +
    '</span><span class="divisa-v"></span>' + acoes;
}

function caixaDaSelecao(todas, feminino) {
  const dica = todas ? "Limpar a seleção" : (feminino ? "Selecionar todas" : "Selecionar todos");
  return '<button type="button" class="marcar on' + (todas ? "" : " parte") + '" data-selecao-alternar="1"' +
    (feminino ? ' data-feminino="1"' : "") + ' role="checkbox" aria-checked="' + (todas ? "true" : "mixed") +
    '" title="' + dica + '" aria-label="' + dica + '">' + ic(todas ? "check" : "remove", 12) + "</button>";
}

function linhasDaSelecao(s) {
  return Array.from(s.raiz.querySelectorAll(s.o.linhas));
}

function todasEscolhidas(s) {
  const linhas = linhasDaSelecao(s);
  return linhas.length > 0 && linhas.every((linha) => s.o.escolhidos.has(s.chave(linha)));
}

/* A caixa da barra acompanha a lista: cada tela redesenha a barra do seu
   jeito, e nem toda sabe o total. Depois de cada mudanca na pagina, a caixa
   confere a lista que esta selecionando e mostra o estado real. */
function sincronizarBarraDeSelecao() {
  const s = selecaoAtiva;
  if (!s || !document.contains(s.raiz)) return;
  const todas = todasEscolhidas(s);
  document.querySelectorAll("[data-selecao-alternar]").forEach((b) => {
    if (b.classList.contains("parte") !== todas) return;
    b.outerHTML = caixaDaSelecao(todas, Boolean(b.dataset.feminino));
  });
}

let quadroDaSincronia = 0;
new MutationObserver(() => {
  if (quadroDaSincronia) return;
  quadroDaSincronia = requestAnimationFrame(() => { quadroDaSincronia = 0; sincronizarBarraDeSelecao(); });
}).observe(document.documentElement, { childList: true, subtree: true });

/* A caixa da barra - e o antigo "Selecionar todos", que alguma tela ainda
   pode desenhar. Por delegacao, porque cada tela redesenha a barra inteira
   a cada clique. */
document.addEventListener("click", (e) => {
  const botao = e.target && e.target.closest && e.target.closest("[data-selecao-alternar], [data-selecionar-todos]");
  if (!botao) return;
  const s = selecaoAtiva;
  if (!s || !document.contains(s.raiz)) return;
  e.preventDefault();
  e.stopPropagation();
  if (botao.hasAttribute("data-selecao-alternar") && todasEscolhidas(s)) {
    s.o.escolhidos.clear();
  } else {
    linhasDaSelecao(s).forEach((linha) => s.o.escolhidos.add(s.chave(linha)));
  }
  s.o.aoMudar();
});

/* ---------------------------------------------------- botao direito */
/* Botao direito numa linha de lista abre o mesmo menu do "…" da linha, no
   ponto do clique. Um so lugar para todas as listas: acha a linha, acha o
   "…" dela, abre o menu como o clique abriria e leva o menu ate o ponteiro.
   Linha sem "…" fica com o menu do navegador - nao se inventa menu. */
const LINHAS_COM_MENU = ".tabela-linha, .lc-linha, .ag-linha, .ae-linha, .ae-verbete, .sv-pasta, .ex-linha, .ap-linha, .mod-linha, .mat-linha";

function botaoMaisDa(linha) {
  return Array.from(linha.querySelectorAll("button")).find((b) =>
    b.closest(LINHAS_COM_MENU) === linha && Array.from(b.querySelectorAll(".ic, .icon")).some((i) => i.textContent.trim() === "more_horiz"));
}

function levarMenuAoPonto(menu, x, y) {
  menu.style.position = "fixed";
  menu.style.right = "auto";
  menu.style.bottom = "auto";
  menu.style.left = x + "px";
  menu.style.top = y + "px";
  menu.style.marginTop = "0";
  // Um ancestral com transform muda a referencia do "fixed": mede o desvio
  // e desconta.
  const caixa = menu.getBoundingClientRect();
  const dx = caixa.left - x;
  const dy = caixa.top - y;
  // Perto da borda da janela, o menu abre para o outro lado do ponteiro.
  let esquerda = x + caixa.width > innerWidth - 8 ? x - caixa.width : x;
  let topo = y + caixa.height > innerHeight - 8 ? y - caixa.height : y;
  esquerda = Math.max(8, esquerda);
  topo = Math.max(8, topo);
  menu.style.left = (esquerda - dx) + "px";
  menu.style.top = (topo - dy) + "px";
}

document.addEventListener("contextmenu", (e) => {
  const alvo = e.target;
  if (!alvo || !alvo.closest || alvo.closest("input, textarea, [contenteditable='true'], .menu-conversa")) return;
  const linha = alvo.closest(LINHAS_COM_MENU);
  if (!linha) return;
  const mais = botaoMaisDa(linha);
  if (!mais) return;
  e.preventDefault();
  document.querySelectorAll(".menu-conversa").forEach((m) => m.remove());
  const antes = new Set(document.querySelectorAll(".menu-conversa"));
  mais.click();
  const menu = Array.from(document.querySelectorAll(".menu-conversa:not(.menu-sub)")).find((m) => !antes.has(m));
  if (menu) levarMenuAoPonto(menu, e.clientX, e.clientY);
});

/* Apaga varios de uma vez pela lixeira e avisa uma vez so, com um Desfazer
   que devolve todos. `urlDe(id)` e a rota DELETE de cada um. */
async function apagarEmLote(ids, urlDe, o) {
  if (!ids.length) return false;
  const n = ids.length;
  const ok = await confirmar({
    titulo: o.titulo || ("Apagar " + plural(n, o.rotulo, o.plural) + "?"),
    contexto: o.contexto || "",
    texto: (o.texto ? o.texto + " " : "") + LIXEIRA_TEXTO,
    confirmar: "Apagar " + (n === 1 ? "" : n), perigo: true,
  });
  if (!ok) return false;
  const lixo = [];
  for (const id of ids) {
    const r = await fetch(urlDe(id), { method: "DELETE" });
    if (!r.ok) continue;
    try { const d = await r.json(); if (d.lixeira) lixo.push(d.lixeira); } catch (err) { /* sem corpo */ }
  }
  if (o.depois) o.depois();
  avisoCert(plural(lixo.length, o.rotulo, o.plural) + (lixo.length === 1 ? " foi" : " foram") + " para a lixeira · 30 dias", {
    tom: "ok",
    acao: { rotulo: "Desfazer", fazer: async () => {
      let voltaram = 0;
      for (const id of lixo) { const r = await fetch("/api/lixeira/" + id + "/restaurar", { method: "POST" }); if (r.ok) voltaram += 1; }
      avisoCert(plural(voltaram, o.rotulo, o.plural) + (voltaram === 1 ? " voltou" : " voltaram"), { tom: "ok" });
      if (o.depois) o.depois();
    } },
  });
  return true;
}

/* ------------------------------------------------------------- teclado */
/* Ctrl+F vai para a busca da tela que esta aberta (doc 05). Ctrl+K, Ctrl+N,
   Ctrl+S, Ctrl+1/2/3 e Esc ja moram na casca e nos dialogos. Sem busca na
   tela, o navegador faz o que sempre fez. */
document.addEventListener("keydown", (e) => {
  if (!(e.ctrlKey || e.metaKey) || e.altKey || e.key.toLowerCase() !== "f") return;
  const busca = Array.from(document.querySelectorAll(".busca-tela input, [data-gv-busca-trecho]")).find((el) => el.offsetParent !== null);
  if (busca) { e.preventDefault(); busca.focus(); busca.select(); }
});
