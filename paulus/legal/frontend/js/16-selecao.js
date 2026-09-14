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

/* A barra de selecao que as listas mostram no lugar dos filtros. `acoes` e
   o HTML dos botoes da tela; "Selecionar todas" e "Limpar" sao os mesmos em
   todas. Com `total`, "Selecionar todas" some quando ja estao todas. */
function barraDeSelecao(quantos, feminino, acoes, atributoLimpar, total) {
  const todas = total !== undefined && quantos >= total;
  return '<span class="selecao"><span class="marcar on">' + ic("check", 12) + "</span>" +
    '<span class="selecao-conta">' + plural(quantos, feminino ? "selecionada" : "selecionado") + "</span>" +
    (todas ? "" : '<button class="limpar" data-selecionar-todos="1">' + (feminino ? "Selecionar todas" : "Selecionar todos") + "</button>") +
    '<button class="limpar" ' + atributoLimpar + '="1">Limpar</button></span><span class="divisa-v"></span>' + acoes;
}

/* "Selecionar todos" e o Ctrl+A em forma de botao: marca todas as linhas da
   lista que tem a selecao. Por delegacao, porque cada tela redesenha a barra
   inteira a cada clique. */
document.addEventListener("click", (e) => {
  const botao = e.target && e.target.closest && e.target.closest("[data-selecionar-todos]");
  if (!botao) return;
  const s = selecaoAtiva;
  if (!s || !document.contains(s.raiz)) return;
  e.preventDefault();
  e.stopPropagation();
  s.raiz.querySelectorAll(s.o.linhas).forEach((linha) => s.o.escolhidos.add(s.chave(linha)));
  s.o.aoMudar();
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
