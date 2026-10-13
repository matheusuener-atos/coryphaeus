/* --------------------------------------------- o editor inteligente
   docs/PLANO-EDITOR.md (E1-E5, E8). O documento aberto ao lado da conversa
   tem blocos com nome (data-b), e o Paulus edita nele como sugestão marcada:
   o que entra sublinhado, o que sai riscado, cada mudança com Aceitar e
   Recusar - como o controlar alterações do Word.

   Aqui mora a parte da tela:
     - os nomes dos blocos (o Enter do navegador copia o parágrafo inteiro,
       nome junto: o segundo ganha outro);
     - os remendos que o servidor manda enquanto o modelo escreve, aplicados
       no lugar - e o parágrafo que a pessoa mexeu enquanto isso não é
       sobrescrito;
     - aceitar e recusar, um, uma rodada ou todos;
     - a seleção que fica marcada enquanto se escreve o pedido, e a barrinha
       sobre ela;
     - o pedido ao agente (/api/documentos/{id}/editar), ao vivo;
     - o painel de alterações, o cartão de conclusão e o do PDF. */

const ei = { selecao: null, faixa: null, barrinha: null, mudancas: {}, ultimaRodada: 0 };

const RE_ESPACOS_EI = /[ \t\r\n\f\v      　]+/g;

/* ---------------------------------------------------- os blocos com nome */

function novoNomeDeBloco(usados) {
  let id;
  do { id = "b" + Math.random().toString(16).slice(2, 8); } while (usados.has(id) || id.length < 7);
  usados.add(id);
  return id;
}

/* Os blocos da folha, na ordem: os de primeiro nível e os itens das listas. */
function blocosComNome(folha) {
  return [...folha.querySelectorAll("[data-b]")];
}

/* Todo bloco com um nome só dele. Chamado antes de gravar e de pedir ao
   Paulus: o nome que o servidor recebe é o que a tela tem. */
function nomearBlocos(folha) {
  if (!folha) return;
  // Texto solto no primeiro nível (a primeira linha digitada numa folha
  // vazia) vira parágrafo - o nó de texto é o mesmo, então o cursor fica.
  [...folha.childNodes].forEach((no) => {
    if (no.nodeType === 3 && no.nodeValue.trim()) {
      const p = document.createElement("p");
      folha.insertBefore(p, no);
      p.appendChild(no);
    }
  });
  const usados = new Set();
  const docxVistos = new Set();
  const alvos = [];
  [...folha.children].forEach((el) => {
    if (el.matches(".dupla-cartao, .ei-cartao")) return;
    if (el.tagName === "UL" || el.tagName === "OL") alvos.push(...el.querySelectorAll("li"));
    else alvos.push(el);
  });
  alvos.forEach((el) => {
    const id = el.getAttribute("data-b");
    if (!id || !/^[A-Za-z][A-Za-z0-9_-]{0,40}$/.test(id) || usados.has(id)) {
      el.setAttribute("data-b", novoNomeDeBloco(usados));
    } else {
      usados.add(id);
    }
    // O parágrafo do .docx partido em dois: o original é o primeiro.
    const docx = el.getAttribute("data-docx");
    if (docx) {
      if (docxVistos.has(docx)) { el.removeAttribute("data-docx"); el.removeAttribute("data-num"); } else docxVistos.add(docx);
    }
  });
}

/* O texto que se vê: o que sai (sugestão de apagar) não conta. A mesma conta
   de src/blocos.py (Bloco.texto) - é ela que diz se a pessoa mexeu no bloco. */
function textoVisivelDoBloco(el) {
  const partes = [];
  const andar = (no) => {
    if (no.nodeType === 3) { partes.push(no.nodeValue); return; }
    if (no.nodeType !== 1) return;
    if (no.tagName === "DEL" && no.hasAttribute("data-s")) return;
    if (no.tagName === "BR") { partes.push("\n"); return; }
    no.childNodes.forEach(andar);
  };
  el.childNodes.forEach((no) => {
    // Lista dentro do item: os itens de dentro são blocos deles.
    if (no.nodeType === 1 && (no.tagName === "UL" || no.tagName === "OL")) return;
    andar(no);
  });
  let t = partes.join("").replace(/\n/g, "\u0000").replace(RE_ESPACOS_EI, " ").replace(/\u0000/g, "\n");
  t = t.replace(/ *\n */g, "\n").replace(/^ +| +$/g, "");
  // O <br> que o navegador põe no fim de bloco vazio não é texto.
  return t.replace(/\n$/, "");
}

function textoNormal(t) {
  return String(t || "").replace(/\n$/, "").replace(RE_ESPACOS_EI, " ").trim();
}

/* ------------------------------------------------------------ os remendos */

/* "Troque os blocos [b3, b4] por este HTML" - o pedaço de primeiro nível da
   folha que os contém. O bloco cujo texto mudou desde que o servidor o leu
   (a pessoa escreveu nele) não é sobrescrito: volta como conflito. */
function aplicarRemendosNaFolha(folha, remendos) {
  let aplicados = 0, conflitos = 0;
  const primeiros = [];
  (remendos || []).forEach((r) => {
    const ids = r.ids || [];
    const molde = document.createElement("div");
    molde.innerHTML = r.html || "";
    if (!ids.length) {
      if (!blocosComNome(folha).length) { folha.innerHTML = r.html; aplicados += 1; } else conflitos += 1;
      return;
    }
    const els = ids.map((id) => folha.querySelector('[data-b="' + CSS.escape(id) + '"]'));
    if (els.some((el) => !el) || ids.some((id, i) => textoNormal(textoVisivelDoBloco(els[i])) !== textoNormal((r.antes || {})[id] || ""))) {
      conflitos += 1;
      return;
    }
    const topo = (el) => { let n = el; while (n.parentNode && n.parentNode !== folha) n = n.parentNode; return n; };
    const ini = topo(els[0]);
    const fim = topo(els[els.length - 1]);
    const novos = [...molde.childNodes];
    novos.forEach((n) => folha.insertBefore(n, ini));
    let n = ini;
    while (n) {
      const proximo = n.nextSibling;
      folha.removeChild(n);
      if (n === fim) break;
      n = proximo;
    }
    aplicados += 1;
    const primeiro = novos.find((x) => x.nodeType === 1);
    if (primeiro) primeiros.push(primeiro);
  });
  return { aplicados, conflitos, primeiros };
}

/* A mudança que acabou de entrar pisca, e a folha rola até ela. */
function piscarNaFolha(el) {
  if (!el) return;
  const alvo = el.querySelector("ins[data-s], del[data-s]") || el;
  alvo.scrollIntoView({ behavior: animacoesLigadas() ? "smooth" : "auto", block: "center" });
  el.classList.remove("ei-pisca");
  void el.offsetWidth;
  el.classList.add("ei-pisca");
  setTimeout(() => el.classList.remove("ei-pisca"), 1600);
}

function irParaBloco(id) {
  const folha = folhaAberta();
  const el = folha && folha.querySelector('[data-b="' + CSS.escape(id) + '"]');
  if (!el) { avisoNaJanela("Esse trecho não está mais no documento"); return; }
  piscarNaFolha(el);
}

/* O bloco onde o cursor estava - o último lugar clicado ou selecionado na
   folha. Botão da barra e painel tiram o foco da folha; o lugar fica. */
document.addEventListener("selectionchange", () => {
  const sel = window.getSelection();
  if (!sel || !sel.rangeCount) return;
  const no = sel.anchorNode;
  const el = no && (no.nodeType === 1 ? no : no.parentElement);
  const bloco = el && el.closest && el.closest("#dp-folha [data-b], #ed-folha [data-b]");
  if (bloco) ei.cursor = bloco;
});

/* Texto que o programa põe no documento a pedido (a citação da lei, a
   qualificação da parte): entra DEPOIS do parágrafo do cursor, e não no fim,
   e como sugestão - aceitar ou recusar, como o que o Paulus escreve. */
function inserirNaFolhaComoSugestao(folha, texto, resumo) {
  if (!folha) return "";
  nomearBlocos(folha);
  const usados = new Set(blocosComNome(folha).map((b) => b.getAttribute("data-b")));
  const sid = "s" + Math.random().toString(16).slice(2, 8);
  let ancora = ei.cursor && folha.contains(ei.cursor) ? ei.cursor : null;
  while (ancora && ancora.parentNode !== folha) ancora = ancora.parentNode;
  let ultimo = ancora;
  String(texto || "").split(/\n\s*\n/).filter((t) => t.trim()).forEach((t) => {
    const p = document.createElement("p");
    p.setAttribute("data-b", novoNomeDeBloco(usados));
    p.setAttribute("data-s", sid);
    p.setAttribute("data-sug", "ins");
    p.setAttribute("data-r", "0");
    p.textContent = t.trim();
    if (ultimo) ultimo.after(p); else folha.appendChild(p);
    ultimo = p;
  });
  ei.mudancas[sid] = { resumo: resumo || "texto inserido" };
  piscarNaFolha(folha.querySelector('[data-s="' + sid + '"]'));
  return sid;
}

/* ------------------------------------------------- aceitar e recusar */

/* As sugestões pendentes, na ordem do documento: uma por nome (data-s). */
function sugestoesNaFolha(folha) {
  const porSid = new Map();
  if (!folha) return [];
  folha.querySelectorAll("[data-s]").forEach((el) => {
    const sid = el.getAttribute("data-s");
    if (!sid) return;
    if (!porSid.has(sid)) porSid.set(sid, { sid, rodada: Number(el.getAttribute("data-r") || 0), els: [], entra: "", sai: "" });
    const s = porSid.get(sid);
    s.els.push(el);
    const ehBloco = el.hasAttribute("data-sug");
    const tipo = ehBloco ? el.getAttribute("data-sug") : el.tagName.toLowerCase();
    const texto = el.textContent.replace(RE_ESPACOS_EI, " ").trim();
    if (tipo === "ins") s.entra = (s.entra + " " + texto).trim();
    else s.sai = (s.sai + " " + texto).trim();
  });
  return [...porSid.values()];
}

function desembrulhar(el) {
  const pai = el.parentNode;
  while (el.firstChild) pai.insertBefore(el.firstChild, el);
  pai.removeChild(el);
}

/* Aceitar ou recusar, no próprio texto: o que entra fica (ou sai), o que sai
   some (ou volta). Bloco que fica sem texto nenhum sai junto. `filtro`:
   {sid}, {rodada} ou nada (todas). Devolve quantas sugestões decidiu. */
function decidirNaFolha(folha, aceitar, filtro) {
  const f = filtro || {};
  const vale = (el) => (!f.sid || el.getAttribute("data-s") === f.sid) &&
    (!f.rodada || Number(el.getAttribute("data-r") || 0) === Number(f.rodada));
  const decididas = new Set();
  folha.querySelectorAll("ins[data-s], del[data-s]").forEach((el) => {
    if (!vale(el)) return;
    decididas.add(el.getAttribute("data-s"));
    const fica = (el.tagName === "INS") === aceitar;
    if (fica) desembrulhar(el); else el.remove();
  });
  folha.querySelectorAll("[data-sug]").forEach((el) => {
    if (!vale(el)) return;
    decididas.add(el.getAttribute("data-s"));
    const fica = (el.getAttribute("data-sug") === "ins") === aceitar;
    if (fica) { el.removeAttribute("data-sug"); el.removeAttribute("data-s"); el.removeAttribute("data-r"); } else el.remove();
  });
  // Bloco que ficou vazio (a sugestão apagava o texto inteiro) e lista sem item.
  blocosComNome(folha).forEach((el) => {
    if (!el.isConnected || el.tagName === "TABLE") return;
    if (!el.textContent.replace(RE_ESPACOS_EI, "") && !el.querySelector("br, img")) el.remove();
  });
  folha.querySelectorAll("ul, ol").forEach((l) => { if (!l.querySelector("li")) l.remove(); });
  folha.normalize();
  return decididas.size;
}

/* Depois de decidir: grava, atualiza o contador e o cartão. */
function depoisDeDecidir(quantas, verbo) {
  if (!quantas) { avisoNaJanela("Não há sugestão pendente aqui: já foram decididas"); return; }
  if ($("dp-folha")) { contarAlteracoes(); marcarDuplaSuja(); gravarDupla(); }
  else salvarOndeEstiver();
  fecharPopoverDeSugestao();
  if ($("ei-painel")) desenharPainelDeAlteracoes();
  avisoNaJanela(verbo + " " + plural(quantas, "sugestão", "sugestões"));
}

function contarAlteracoes() {
  const n = sugestoesNaFolha($("dp-folha")).length;
  const conta = $("dp-alteracoes-n");
  if (conta) conta.textContent = n;
  const botao = $("dp-alteracoes");
  if (botao) botao.classList.toggle("ei-com-pendentes", n > 0);
  if (dupla.doc) dupla.doc.pendentes = n;
  return n;
}

/* O cartãozinho de uma sugestão, ao clicar nela: de que rodada é, o que muda
   e os dois botões. */
function abrirPopoverDeSugestao(el) {
  fecharPopoverDeSugestao();
  const sid = el.getAttribute("data-s");
  const s = sugestoesNaFolha(folhaAberta()).find((x) => x.sid === sid);
  if (!s) return;
  const info = ei.mudancas[sid] || {};
  const caixa = document.createElement("div");
  caixa.className = "ei-popover";
  caixa.id = "ei-popover";
  caixa.innerHTML = '<span class="rotulo">' + (s.rodada ? "Paulus · resposta " + s.rodada : "Paulus") + "</span>" +
    "<p>" + esc(info.resumo || (s.sai && s.entra ? "“" + s.sai.slice(0, 80) + "” → “" + s.entra.slice(0, 80) + "”"
      : s.entra ? "entra: “" + s.entra.slice(0, 140) + "”" : "sai: “" + s.sai.slice(0, 140) + "”")) + "</p>" +
    '<div class="linha-form"><button data-ei-dec="recusar">' + ic("close", 16) + "Recusar</button>" +
    '<button class="primario" data-ei-dec="aceitar">' + ic("check", 16) + "Aceitar</button></div>";
  document.body.appendChild(caixa);
  const r = el.getBoundingClientRect();
  const largura = Math.min(320, window.innerWidth - 24);
  caixa.style.left = Math.max(12, Math.min(window.innerWidth - largura - 12, r.left)) + "px";
  caixa.style.top = Math.min(window.innerHeight - caixa.offsetHeight - 12, r.bottom + 8) + "px";
  caixa.querySelectorAll("[data-ei-dec]").forEach((b) => {
    b.onclick = () => {
      const aceitar = b.dataset.eiDec === "aceitar";
      depoisDeDecidir(decidirNaFolha(folhaAberta(), aceitar, { sid }), aceitar ? "Aceitei" : "Recusei");
    };
  });
}

function fecharPopoverDeSugestao() {
  const p = $("ei-popover");
  if (p) p.remove();
}

document.addEventListener("click", (e) => {
  const alvo = e.target.closest && e.target.closest("#dp-folha [data-s], #ed-folha [data-s]");
  if (alvo) { abrirPopoverDeSugestao(alvo); return; }
  if (!(e.target.closest && e.target.closest("#ei-popover"))) fecharPopoverDeSugestao();
  // "ir para" e "aceitar/recusar as desta resposta", na conversa.
  const ir = e.target.closest && e.target.closest("[data-ed-ir]");
  if (ir) { e.preventDefault(); irParaBloco(ir.dataset.edIr); return; }
  const rod = e.target.closest && e.target.closest("[data-ed-rodada]");
  if (rod) {
    e.preventDefault();
    const folha = $("dp-folha");
    if (!folha) { avisoNaJanela("Abra o documento ao lado para decidir"); return; }
    const aceitar = rod.dataset.edAcao === "aceitar";
    depoisDeDecidir(decidirNaFolha(folha, aceitar, { rodada: Number(rod.dataset.edRodada) }), aceitar ? "Aceitei" : "Recusei");
  }
});

/* ------------------------------------------- o painel de alterações (E8) */

function alternarPainelDeAlteracoes() {
  const aberto = $("ei-painel");
  if (aberto) { aberto.remove(); return; }
  const lugar = $("dp-abaixo");
  if (!lugar) return;
  const painel = document.createElement("div");
  painel.className = "ei-painel";
  painel.id = "ei-painel";
  lugar.before(painel);
  desenharPainelDeAlteracoes();
}

function desenharPainelDeAlteracoes() {
  const painel = $("ei-painel");
  const folha = $("dp-folha");
  if (!painel || !folha) return;
  const lista = sugestoesNaFolha(folha);
  if (!lista.length) {
    painel.innerHTML = '<div class="ei-painel-topo"><b>Alterações</b><span class="cresce"></span>' +
      '<button class="botao-icone" data-ei-painel="fechar" aria-label="Fechar">' + ic("close", 16) + "</button></div>" +
      '<p class="explica">Nenhuma sugestão esperando você. O que o Paulus muda aparece aqui, marcado no texto.</p>';
  } else {
    painel.innerHTML = '<div class="ei-painel-topo"><b>' + plural(lista.length, "alteração", "alterações") + "</b>" +
      '<span class="cresce"></span><button data-ei-painel="recusar">Recusar todas</button>' +
      '<button class="primario" data-ei-painel="aceitar">' + ic("done_all", 16) + "Aceitar todas</button>" +
      '<button class="botao-icone" data-ei-painel="fechar" aria-label="Fechar">' + ic("close", 16) + "</button></div>" +
      '<div class="ei-painel-lista">' + lista.map((s) => {
        const info = ei.mudancas[s.sid] || {};
        const resumo = info.resumo || (s.sai && s.entra ? "“" + s.sai.slice(0, 60) + "” → “" + s.entra.slice(0, 60) + "”"
          : s.entra ? "entra: “" + s.entra.slice(0, 90) + "”" : "sai: “" + s.sai.slice(0, 90) + "”");
        return '<div class="ei-mudanca" data-ei-sid="' + esc(s.sid) + '">' +
          '<button class="ei-mudanca-texto" data-ei-ir="' + esc(s.sid) + '"><span class="rotulo">' +
          (s.rodada ? "resposta " + s.rodada : "") + "</span>" + esc(resumo) + "</button>" +
          '<button class="botao-icone" data-ei-um="recusar" title="Recusar" aria-label="Recusar">' + ic("close", 16) + "</button>" +
          '<button class="botao-icone" data-ei-um="aceitar" title="Aceitar" aria-label="Aceitar">' + ic("check", 16) + "</button></div>";
      }).join("") + "</div>";
  }
  painel.querySelectorAll("[data-ei-painel]").forEach((b) => {
    b.onclick = () => {
      if (b.dataset.eiPainel === "fechar") { painel.remove(); return; }
      const aceitar = b.dataset.eiPainel === "aceitar";
      depoisDeDecidir(decidirNaFolha(folha, aceitar), aceitar ? "Aceitei" : "Recusei");
    };
  });
  painel.querySelectorAll("[data-ei-ir]").forEach((b) => {
    b.onclick = () => {
      const el = folha.querySelector('[data-s="' + CSS.escape(b.dataset.eiIr) + '"]');
      if (el) piscarNaFolha(el.closest("[data-b]") || el);
    };
  });
  painel.querySelectorAll("[data-ei-um]").forEach((b) => {
    b.onclick = () => {
      const sid = b.closest("[data-ei-sid]").dataset.eiSid;
      const aceitar = b.dataset.eiUm === "aceitar";
      depoisDeDecidir(decidirNaFolha(folha, aceitar, { sid }), aceitar ? "Aceitei" : "Recusei");
    };
  });
}

/* A conferência jurídica (E6) no mesmo painel: cada aviso com o lugar. */
async function abrirConferenciaNoPainel() {
  const folha = $("dp-folha");
  const lugar = $("dp-abaixo");
  if (!folha || !lugar || !dupla.doc) return;
  let painel = $("ei-painel");
  if (!painel) {
    painel = document.createElement("div");
    painel.className = "ei-painel";
    painel.id = "ei-painel";
    lugar.before(painel);
  }
  painel.innerHTML = '<p class="explica">conferindo…</p>';
  nomearBlocos(folha);
  const r = await fetch("/api/documentos/" + dupla.doc.id + "/conferencia", {
    method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ corpo: htmlDaFolha() }),
  }).catch(() => null);
  if (!r || !r.ok) { painel.innerHTML = '<p class="explica">Não consegui conferir agora.</p>'; return; }
  const d = await r.json();
  const avisos = d.avisos || [];
  painel.innerHTML = '<div class="ei-painel-topo"><b>Conferência</b><span class="rotulo">' +
    (avisos.length ? plural(avisos.length, "ponto") + " para olhar" : "nada a apontar") + "</span>" +
    '<span class="cresce"></span><button class="botao-icone" data-ei-painel="fechar" aria-label="Fechar">' + ic("close", 16) + "</button></div>" +
    (avisos.length
      ? '<div class="ei-painel-lista">' + avisos.map((a) => {
        const classe = "ei-aviso" + (a.grau === "impede" ? " ei-impede" : "");
        return '<button class="' + classe + '" data-ed-ir="' + esc(a.bloco) + '"><span class="rotulo">' +
          esc((a.rotulo ? a.rotulo + " · " : "") + a.titulo) + "</span>" + esc(a.detalhe) + "</button>";
      }).join("") + "</div>"
      : '<p class="explica">Numeração, referências cruzadas, termos definidos, valores e extensos, datas, CPF/CNPJ, ' +
        "lacunas e artigos de lei: nada a apontar.</p>");
  painel.querySelector('[data-ei-painel="fechar"]').onclick = () => painel.remove();
}

/* ------------------------------------------------ a seleção (E4) */

/* O trecho selecionado numa folha: os blocos que ele toca e o texto. */
function selecaoDaFolha(folha) {
  const sel = window.getSelection();
  if (!folha || !sel || !sel.rangeCount || sel.isCollapsed || !folha.contains(sel.anchorNode) || !folha.contains(sel.focusNode)) return null;
  const faixa = sel.getRangeAt(0).cloneRange();
  const texto = faixa.toString().replace(RE_ESPACOS_EI, " ").trim();
  if (texto.length < 2) return null;
  nomearBlocos(folha);
  const doBloco = (no) => { const el = no.nodeType === 1 ? no : no.parentElement; return el && el.closest("[data-b]"); };
  const ini = doBloco(faixa.startContainer);
  const fim = doBloco(faixa.endContainer);
  if (!ini || !fim) return null;
  const todos = blocosComNome(folha);
  const a = todos.indexOf(ini), b = todos.indexOf(fim);
  const blocos = a >= 0 && b >= a ? todos.slice(a, b + 1).map((x) => x.getAttribute("data-b")) : [ini.getAttribute("data-b")];
  return { faixa: faixa, selecao: { bloco: blocos[0], blocos: blocos, texto: texto.slice(0, 4000) } };
}

/* O trecho selecionado na folha fica marcado (Highlight API) enquanto a
   pessoa escreve o pedido na caixa - e vai junto com ele. */
function guardarSelecaoDaFolha() {
  const achado = selecaoDaFolha($("dp-folha"));
  if (!achado) return;
  const faixa = achado.faixa;
  ei.faixa = faixa;
  ei.selecao = achado.selecao;
  if (window.CSS && CSS.highlights && window.Highlight) CSS.highlights.set("paulus-selecao", new Highlight(faixa));
  desenharChipDaSelecao();
  mostrarBarrinha(faixa);
}

function esquecerSelecaoDaFolha() {
  ei.selecao = null;
  ei.faixa = null;
  if (window.CSS && CSS.highlights) CSS.highlights.delete("paulus-selecao");
  const chip = $("ei-chip-selecao");
  if (chip) chip.remove();
  esconderBarrinha();
}

function desenharChipDaSelecao() {
  let chip = $("ei-chip-selecao");
  if (!ei.selecao) { if (chip) chip.remove(); return; }
  if (!chip) {
    chip = document.createElement("div");
    chip.className = "ei-chip-selecao";
    chip.id = "ei-chip-selecao";
    const campo = $("cartao-campo");
    if (!campo) return;
    campo.before(chip);
  }
  chip.innerHTML = '<span class="rotulo">trecho selecionado</span><span class="corta">“' + esc(ei.selecao.texto.slice(0, 90)) +
    (ei.selecao.texto.length > 90 ? "…" : "") + "”</span>" +
    '<button class="botao-icone" aria-label="Esquecer o trecho" title="Esquecer o trecho">' + ic("close", 14) + "</button>";
  chip.querySelector("button").onclick = () => esquecerSelecaoDaFolha();
}

const ATALHOS_DA_SELECAO = [
  ["Reescrever", "Reescreva este trecho com mais clareza"],
  ["Mais formal", "Deixe este trecho mais formal"],
  ["Encurtar", "Encurte este trecho, sem perder o sentido"],
  ["Explicar", "O que este trecho quer dizer, e que riscos ele traz?"],
  ["Comentar", "Comente este trecho: o que falta, o que está ambíguo, o que merece conferência"],
];

function mostrarBarrinha(faixa) {
  esconderBarrinha();
  const r = faixa.getBoundingClientRect();
  if (!r.width && !r.height) return;
  const barra = document.createElement("div");
  barra.className = "ei-barrinha";
  barra.id = "ei-barrinha";
  barra.innerHTML = '<button data-ei-atalho="pedir">' + ic("auto_awesome", 14) + "Pedir ao Paulus</button>" +
    ATALHOS_DA_SELECAO.map((a, i) => '<button data-ei-atalho="' + i + '">' + esc(a[0]) + "</button>").join("");
  document.body.appendChild(barra);
  const largura = barra.offsetWidth;
  const altura = barra.offsetHeight;
  barra.style.left = Math.max(8, Math.min(window.innerWidth - largura - 8, r.left + r.width / 2 - largura / 2)) + "px";
  // Acima do trecho; sem espaço, abaixo - e sempre dentro da janela.
  const acima = r.top - altura - 8;
  const topo = acima >= 8 ? acima : r.bottom + 8;
  barra.style.top = Math.max(8, Math.min(window.innerHeight - altura - 8, topo)) + "px";
  barra.onmousedown = (e) => e.preventDefault();        // não perde a seleção
  barra.querySelectorAll("[data-ei-atalho]").forEach((b) => {
    b.onclick = () => {
      esconderBarrinha();
      if (b.dataset.eiAtalho === "pedir") { $("pedido").focus(); return; }
      editarComOPaulus(ATALHOS_DA_SELECAO[Number(b.dataset.eiAtalho)][1]);
    };
  });
}

function esconderBarrinha() {
  const b = $("ei-barrinha");
  if (b) b.remove();
}

document.addEventListener("mouseup", (e) => {
  if (!(e.target.closest && e.target.closest("#dp-folha"))) return;
  setTimeout(guardarSelecaoDaFolha, 0);
});
document.addEventListener("keyup", (e) => {
  if (e.shiftKey && e.target && e.target.id === "dp-folha") guardarSelecaoDaFolha();
});
document.addEventListener("mousedown", (e) => {
  // Clicar de novo dentro da folha (sem arrastar) desfaz a seleção guardada.
  if (e.target.closest && e.target.closest("#dp-folha") && ei.selecao) {
    esconderBarrinha();
    setTimeout(() => {
      const sel = window.getSelection();
      if (!sel || sel.isCollapsed) esquecerSelecaoDaFolha();
    }, 180);
  }
});
/* Rolando a folha (ou a conversa), a barrinha acompanha o trecho; com o
   trecho fora da vista, ela some até ele voltar. */
let quadroDaBarrinha = 0;
window.addEventListener("scroll", () => {
  cancelAnimationFrame(quadroDaBarrinha);
  quadroDaBarrinha = requestAnimationFrame(() => {
    const barra = $("ei-barrinha");
    if (!barra || !ei.faixa) return;
    const r = ei.faixa.getBoundingClientRect();
    const visivel = r.bottom > 0 && r.top < window.innerHeight && (r.width || r.height);
    barra.hidden = !visivel;
    if (!visivel) return;
    const altura = barra.offsetHeight;
    const acima = r.top - altura - 8;
    barra.style.top = Math.max(8, Math.min(window.innerHeight - altura - 8, acima >= 8 ? acima : r.bottom + 8)) + "px";
    barra.style.left = Math.max(8, Math.min(window.innerWidth - barra.offsetWidth - 8, r.left + r.width / 2 - barra.offsetWidth / 2)) + "px";
  });
}, true);

/* ---------------------------------------------- o pedido ao agente (E5) */

/* Com o documento aberto ao lado, para onde vai o pedido: mudança e pergunta
   sobre o documento vão para ele; ação do programa (agendar, e-mail,
   cadastrar, pesquisar) e conversa, para a conversa. Quem decide entre
   pergunta e mudança, do lado de lá, é o servidor (src/agente_de_edicao.py). */
const RE_ACAO_DO_PROGRAMA = /\b(agend|tarefa|lembr[ae]|e-?mail|envi[ae]|mand[ae] para|whatsapp|cadastr|ficha|pesquis|jurisprud|sumula|procure no acervo|busque no acervo|financeiro|lancamento|nota fiscal|assin[ae]|grav[ae] a reuni|abra o |abrir o |mostre o |crie uma? (?:tarefa|pasta|compromisso))/;
const RE_SOBRE_O_DOCUMENTO = /\b(clausula|paragrafo|inciso|alinea|contrato|documento|minuta|texto|peticao|procuracao|notificacao|item|prazo|valor|aluguel|multa|preco|parte|partes|foro|vigencia|garantia|objeto|pagamento|qualificac|assinatura|testemunha|isso|isto|este|esta|esse|essa|aqui)\b/;

function vaiParaODocumento(texto) {
  const plano = String(texto || "").normalize("NFD").replace(/[̀-ͯ]/g, "").toLowerCase();
  if (!plano.trim()) return false;
  if (ei.selecao) return true;
  if (RE_ACAO_DO_PROGRAMA.test(plano) && !RE_PEDIDO_DE_MUDANCA.test(plano)) return false;
  if (destinoDoPedido(texto) === "documento") return true;
  return RE_SOBRE_O_DOCUMENTO.test(plano) || /\?\s*$/.test(plano);
}

/* O cartão de trabalho na conversa, enquanto o Paulus edita. */
function cartaoDaEdicao(titulo) {
  return '<div class="cartao"><div class="cartao-topo">' + coroa(20) +
    '<span class="quem">Trabalhando em “' + esc(titulo) + '”</span><span class="tempo" data-ei-tempo="1">0 s</span></div>' +
    '<div class="cartao-corpo"><div class="ei-etapas" data-ei-etapas="1">' +
    linhaEtapa({ titulo: "Entender o pedido", estado: "executando" }) + "</div>" +
    '<div class="ei-bastidor" data-ei-bastidor="1"></div></div></div>';
}

function desenharEtapasDaEdicao(lugar, etapas) {
  if (!lugar) return;
  lugar.innerHTML = Object.values(etapas).map((e) => linhaEtapa({ titulo: e.titulo, estado: e.estado === "concluido" ? "concluido" : "executando" })).join("");
}

async function editarComOPaulus(pedido, opcoes) {
  if (!pedido || !dupla.doc || dupla.ocupada) return;
  const o = opcoes || {};
  const folha = $("dp-folha");
  if (!folha) return;
  dupla.ocupada = true;
  const docId = dupla.doc.id;
  const titulo = dupla.doc.titulo;
  const tid = estado.trabalhoId || dupla.doc.trabalho_id || "";
  const selecao = o.semSelecao ? null : ei.selecao;
  const centro = $("centro");
  if (!o.jaDito) centro.insertAdjacentHTML("beforeend", bolhaPessoa(pedido));
  const resposta = document.createElement("div");
  resposta.className = "resposta";
  resposta.innerHTML = cartaoDaEdicao(titulo);
  centro.appendChild(resposta);
  atualizarPostura();
  rolar();
  seloDoRascunho("o Paulus está escrevendo…", "sujo");
  esquecerSelecaoDaFolha();
  clearTimeout(dupla.relogio);
  nomearBlocos(folha);
  const inicio = Date.now();
  const relogio = setInterval(() => {
    const t = resposta.querySelector("[data-ei-tempo]");
    if (t) t.textContent = segundosCurtos((Date.now() - inicio) / 1000);
  }, 500);
  const etapas = {};
  let textoAoVivo = "";
  let fim = null;
  let primeiroRemendo = true;
  try {
    const r = await fetch("/api/documentos/" + docId + "/editar", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify(Object.assign({ pedido: pedido, corpo: htmlDaFolha(), revisao: dupla.doc.revisao,
        selecao: selecao, trabalho_id: tid, ja_dito: Boolean(o.jaDito) },
        typeof profundidadeDoEnvio === "function" ? profundidadeDoEnvio() : {},
        typeof nuvemDoEnvio === "function" ? nuvemDoEnvio() : {})),
    });
    if (r.status === 409) {
      const d = await r.json().catch(() => ({}));
      if (d.conflito) await resolverConflitoDaFolha(d);
      throw new Error(d.detail || "o documento mudou em outro lugar");
    }
    if (!r.ok) throw new Error(await erroDe(r));
    for await (const ev of eventosSSE(r)) {
      const d = ev.dados;
      if (ev.tipo === "etapa") {
        etapas[d.id] = d;
        desenharEtapasDaEdicao(resposta.querySelector("[data-ei-etapas]"), etapas);
      } else if (ev.tipo === "nota") {
        const b = resposta.querySelector("[data-ei-bastidor]");
        if (b) b.insertAdjacentHTML("beforeend", '<div class="ei-nota">' + esc(d.texto) + "</div>");
      } else if (ev.tipo === "remendo") {
        const f = $("dp-folha");
        if (!f || !dupla.doc || dupla.doc.id !== docId) continue;
        const feito = aplicarRemendosNaFolha(f, d.remendos);
        (d.sids || []).forEach((sid) => { ei.mudancas[sid] = { resumo: d.resumo }; });
        if (feito.primeiros.length && primeiroRemendo) { piscarNaFolha(feito.primeiros[0]); primeiroRemendo = false; }
        else feito.primeiros.forEach((x) => { x.classList.add("ei-pisca"); setTimeout(() => x.classList.remove("ei-pisca"), 1600); });
        const b = resposta.querySelector("[data-ei-bastidor]");
        if (b && d.resumo) b.insertAdjacentHTML("beforeend", '<div class="ei-nota ei-nota-mudou">' + ic("edit", 14) + esc(d.resumo) + "</div>");
        contarAlteracoes();
        redesenharPaginas();
      } else if (ev.tipo === "token") {
        textoAoVivo += d.t || "";
        let viva = resposta.querySelector("[data-ei-viva]");
        if (!viva) { resposta.insertAdjacentHTML("beforeend", '<div class="texto" data-ei-viva="1"></div>'); viva = resposta.querySelector("[data-ei-viva]"); }
        viva.textContent = textoAoVivo.replace(/\[(b[0-9a-f]{4,8})(?:\s*[·|-][^\]\n]{0,60})?\]/g, "");
      } else if (ev.tipo === "concluir") {
        mostrarCartaoDeConclusao(Object.assign({}, d, { id: docId }));
      } else if (ev.tipo === "fim") {
        fim = d;
      } else if (ev.tipo === "erro") {
        throw new Error(d.texto || "não consegui");
      }
    }
    if (!fim) throw new Error("a resposta parou no meio");
    if (dupla.doc && dupla.doc.id === docId) {
      dupla.doc.revisao = fim.revisao;
      dupla.doc.pendentes = fim.pendentes;
    }
    (fim.mudancas || []).forEach((m) => (m.sids || []).forEach((sid) => { ei.mudancas[sid] = { resumo: m.resumo }; }));
    ei.ultimaRodada = fim.rodada;
    resposta.innerHTML = '<div class="texto">' + textoDaRespostaDoEditor(fim.texto, fim) + "</div>" +
      acoesDaRodada(fim, docId) + linhaDoModeloDoEditor(fim);
    contarAlteracoes();
  } catch (err) {
    resposta.innerHTML = '<div class="texto">Não consegui: ' + esc(String((err && err.message) || err)) + "</div>";
  } finally {
    clearInterval(relogio);
    dupla.ocupada = false;
    if ($("dp-selo")) seloDoRascunho("salvo no rascunho às " + new Date().toTimeString().slice(0, 5), "");
    // O que a pessoa escreveu enquanto o Paulus trabalhava grava agora.
    if ($("dp-folha") && dupla.sujaDuranteAEdicao) { dupla.sujaDuranteAEdicao = false; gravarDupla(); }
    if (resposta.isConnected) rolar();
    else if (estado.trabalhoId === tid && tid) {
      const t = await fetch("/api/trabalhos/" + tid).then((x) => (x.ok ? x.json() : null));
      if (t && estado.trabalhoId === tid) { estado.trabalho = t; desenharTrabalho(); }
    }
  }
}

/* A resposta do agente na conversa: as linhas "- mudança" viram atalhos que
   levam ao lugar no documento; "[b12]" vira o rótulo do bloco. */
function textoDaRespostaDoEditor(texto, d) {
  const citados = {};
  ((d && d.citados) || []).forEach((c) => { citados[c.id] = c.rotulo || "ver no documento"; });
  const mudancas = (d && d.mudancas) || [];
  return String(texto || "").split("\n").map((linha) => {
    const m = linha.match(/^- (.*)$/);
    const mud = m && mudancas.find((x) => x.resumo === m[1]);
    if (mud && (mud.ids || []).length) {
      return '<button class="ei-linha-mudanca" data-ed-ir="' + esc(mud.ids[0]) + '">' + ic("edit_note", 14) + esc(m[1]) + "</button>";
    }
    return esc(linha).replace(/\[(b[0-9a-f]{4,8})\]/g, (_, id) =>
      '<button class="ei-citado" data-ed-ir="' + id + '">' + esc(citados[id] || "ver no documento") + "</button>");
  }).join("<br>");
}

function acoesDaRodada(d, docId) {
  const n = (d.mudancas || []).filter((m) => (m.sids || []).length).length;
  if (!n || !d.rodada) return "";
  const doc = docId || d.id || (dupla.doc && dupla.doc.id) || 0;
  return '<div class="linha-form ei-acoes-rodada"><button data-ed-rodada="' + d.rodada + '" data-ed-acao="recusar">' +
    ic("undo", 16) + "Desfazer esta resposta</button>" +
    '<button class="primario" data-ed-rodada="' + d.rodada + '" data-ed-acao="aceitar">' + ic("done_all", 16) +
    (n > 1 ? "Aceitar as " + n : "Aceitar") + "</button>" +
    '<span class="cresce"></span><span class="ei-avaliar" data-ei-doc="' + doc + '" data-ei-rodada="' + d.rodada + '">' +
    '<button class="botao-icone" data-ei-nota="1" title="Boa resposta" aria-label="Boa resposta">' + ic("check", 16) +
    '</button><button class="botao-icone" data-ei-nota="-1" title="Não era isso" aria-label="Não era isso">' +
    ic("close", 16) + "</button></span></div>";
}

function linhaDoModeloDoEditor(d) {
  const o = (d && d.onde) || {};
  if (!o.onde) return "";
  const onde = o.onde === "nuvem" ? "IA da nuvem" + (o.modelo ? " · " + String(o.modelo).split("/").pop() : "")
    : "modelo deste computador" + (o.motivo ? " · " + o.motivo : "");
  return '<div class="ei-assinatura">' + esc(onde) + (d.segundos ? " · " + String(d.segundos).replace(".", ",") + " s" : "") + "</div>";
}

/* O polegar da resposta (E9): "não era isso" pede o que deveria ter feito -
   e vira caso para o banco de provas (data/medicao/editor-avaliacoes.jsonl). */
document.addEventListener("click", async (e) => {
  const b = e.target.closest && e.target.closest("[data-ei-nota]");
  if (!b) return;
  const lugar = b.closest(".ei-avaliar");
  const docId = lugar && lugar.dataset.eiDoc;
  const rodada = lugar && lugar.dataset.eiRodada;
  if (!docId || !rodada) return;
  const nota = Number(b.dataset.eiNota);
  let comentario = "";
  if (nota < 0) {
    comentario = await perguntar({ titulo: "O que eu deveria ter feito?", contexto: "Resposta " + rodada,
      campo: { rotulo: "Conte em uma frase", placeholder: "ex.: só a cláusula 3ª, sem mexer na data", icone: "edit_note" },
      confirmar: "Enviar" });
    if (comentario === null) return;
  }
  const r = await fetch("/api/documentos/" + docId + "/rodadas/" + rodada + "/avaliar", {
    method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ nota: nota, comentario: comentario || "" }),
  });
  if (!r.ok) { avisoNaJanela("Não consegui guardar a nota", { icone: "error" }); return; }
  lugar.innerHTML = '<span class="rotulo">' + (nota > 0 ? "obrigado" : "anotado — vou aprender com isso") + "</span>";
});

/* Outra janela gravou o documento depois desta: a tela mostra o que está
   gravado, e o que estava aqui fica no Histórico. */
async function resolverConflitoDaFolha(d) {
  if (!dupla.doc || !$("dp-folha")) return;
  // Só no Histórico: gravar a tela por cima apagaria o que a outra janela gravou.
  await fetch("/api/documentos/" + dupla.doc.id, {
    method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ corpo: htmlDaFolha(), nota: "o que estava nesta tela quando outra janela gravou", so_historico: true }),
  }).catch(() => null);
  const novo = await fetch("/api/documentos/" + dupla.doc.id).then((x) => (x.ok ? x.json() : null));
  if (!novo || !dupla.doc || !$("dp-folha")) return;
  dupla.doc = Object.assign(dupla.doc, novo);
  $("dp-folha").innerHTML = novo.corpo || "<p><br></p>";
  contarAlteracoes();
  redesenharPaginas();
  avisoNaJanela("O documento tinha mudado em outra janela: esta mostra agora o que está gravado (o que estava aqui ficou no Histórico)");
}

/* ------------------------------------------- concluir (E1) e o PDF */

async function mostrarCartaoDeConclusao(d) {
  const docId = d.id || (dupla.doc && dupla.doc.id);
  if (!docId) return;
  if (dupla.doc && dupla.doc.id === docId && $("dp-folha")) {
    await gravarDupla();
    const n = contarAlteracoes();
    if (n) {
      avisoNaJanela("Antes de concluir, decida as " + plural(n, "sugestão", "sugestões") + " marcadas no texto");
      if (!$("ei-painel")) alternarPainelDeAlteracoes();
      return;
    }
  }
  let padrao = d;
  if (!padrao.formato) {
    const doc = await fetch("/api/documentos/" + docId).then((x) => (x.ok ? x.json() : null));
    padrao = Object.assign({ formato: (doc && doc.origem && doc.origem.formato === "pdf") ? "pdf" : "docx",
      nome: doc ? doc.titulo : "", pasta_curta: "" }, d);
  }
  const escolha = dialogo({
    titulo: "Concluir o documento", contexto: "O arquivo vai para o Acervo", classe: "dialogo-concluir", confirmar: "Concluir",
    html: '<div class="ei-concluir">' +
      '<p class="explica">Até aqui o documento era rascunho desta conversa. Concluindo, eu gravo o arquivo no Acervo — o ' +
      "rascunho fica guardado e dá para reabrir.</p>" +
      '<div class="ei-formato" role="radiogroup">' +
      ["docx", "pdf"].map((f) => '<label class="ei-opcao"><input type="radio" name="ei-formato" value="' + f + '"' +
        (padrao.formato === f ? " checked" : "") + ">" + ic(f === "pdf" ? "picture_as_pdf" : "description", 18) +
        "<span><b>" + f.toUpperCase() + "</b><small>" + (f === "pdf" ? "para assinar e enviar" : "para continuar no Word") +
        "</small></span></label>").join("") + "</div>" +
      '<div class="campo-form"><label for="ei-nome">Nome do arquivo</label><input type="text" id="ei-nome" maxlength="180" value="' +
      esc(padrao.nome || "") + '"></div>' +
      (padrao.pasta_curta ? '<p class="explica">Pasta: <b>' + esc(padrao.pasta_curta) + "</b></p>" : "") + "</div>",
  });
  const r = await escolha;
  if (!r || !r.ok) return;
  const formato = (document.querySelector('input[name="ei-formato"]:checked') || {}).value || padrao.formato;
  const nome = ($("ei-nome") || {}).value || padrao.nome;
  await concluirDocumento(docId, { formato: formato, nome: nome }, padrao);
}

async function concluirDocumento(docId, pedido, padrao) {
  const r = await fetch("/api/documentos/" + docId + "/concluir", {
    method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(pedido),
  });
  if (r.status === 409) {
    const d = await r.json().catch(() => ({}));
    if (d.conflitos && d.conflitos.length) {
      const c = d.conflitos[0];
      const decisao = await dialogo({
        titulo: "Já existe um arquivo com esse nome", contexto: c.pasta_curta || "Acervo", confirmar: "Salvar com outro nome",
        html: '<p class="explica">Em “' + esc(c.pasta_curta || "") + "” já há “" + esc(c.existente) + "”. Eu salvo como “" +
          esc(c.sugestao) + "” — o arquivo que já está lá não muda.</p>",
      });
      if (!decisao || !decisao.ok) return;
      const decisoes = {};
      decisoes[c.nome] = { acao: "renomear", nome: c.sugestao };
      return concluirDocumento(docId, Object.assign({}, pedido, { decisoes: decisoes }), padrao);
    }
    avisoNaJanela(d.detail || "Não consegui concluir", { icone: "error" });
    return;
  }
  if (!r.ok) { avisoNaJanela("Não consegui concluir: " + (await erroDe(r)), { icone: "error" }); return; }
  const d = await r.json();
  avisoNaJanela("Concluído: " + d.nome + " está no Acervo");
  if (dupla.doc && dupla.doc.id === docId) {
    dupla.doc.situacao = "concluido";
    dupla.doc.arquivo = d.arquivo;
    desenharEstadoDoDocumento();
  }
  // A conversa ganha a nota do que foi feito - sem redesenhar tudo, que
  // trocaria a coluna da direita e fecharia o editor.
  if (estado.trabalhoId) {
    notaDeFeitoNaConversa("Concluí: " + d.nome + " está no Acervo, em " + nomeDe(d.pasta) + ". O rascunho fica " +
      "guardado nesta conversa.");
    const t = await fetch("/api/trabalhos/" + estado.trabalhoId).then((x) => (x.ok ? x.json() : null));
    if (t && t.id === estado.trabalhoId) estado.trabalho = t;
  }
  return d;
}

/* O cabeçalho do editor diz em que pé o documento está, e a folha do
   concluído é só leitura - mexer de novo é "Reabrir". */
function desenharEstadoDoDocumento() {
  const d = dupla.doc;
  if (!d) return;
  const linha = $("dp-linha");
  if (linha) linha.textContent = linhaDoRascunho(d);
  const folha = $("dp-folha");
  const concluido = d.situacao === "concluido";
  if (folha) folha.contentEditable = concluido ? "false" : "true";
  const guardar = $("dp-guardar");
  if (guardar) {
    guardar.textContent = concluido ? "Reabrir" : (d.da_conversa ? "Concluir" : "Salvar na biblioteca");
    guardar.title = concluido ? "Mexer de novo: o documento volta a ser rascunho (o arquivo gravado fica)" :
      (d.da_conversa ? "Gravar o arquivo no Acervo, no formato que você escolher" : "Gravar no Acervo, em PDF");
  }
  const editor = $("editor-lado");
  if (editor) editor.classList.toggle("ei-concluido", concluido);
}

async function reabrirDocumento() {
  if (!dupla.doc) return;
  const r = await fetch("/api/documentos/" + dupla.doc.id + "/reabrir", { method: "POST" });
  if (!r.ok) { avisoNaJanela("Não consegui reabrir", { icone: "error" }); return; }
  dupla.doc.situacao = "conversa";
  desenharEstadoDoDocumento();
  avisoNaJanela("O documento voltou a ser rascunho desta conversa");
}

/* O PDF não vira editável sozinho: o cartão pergunta, e o sim cria a versão
   editável da conversa (e faz a mudança pedida, quando havia uma). */
async function criarVersaoEditavelDoPdf(nome, pedido) {
  const r = await fetch("/api/documentos/importar", {
    method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ nome: nome, trabalho_id: estado.trabalhoId || "", de_pdf: true }),
  });
  if (!r.ok) { avisoNaJanela("Não consegui criar a versão editável: " + (await erroDe(r)), { icone: "error" }); return null; }
  const novo = await r.json();
  await mostrarDupla(novo.id, { nome: nome });
  if (pedido) await editarComOPaulus(pedido, { jaDito: true });
  return novo;
}

function ligarEditavelDePdf(caixa, d) {
  const c = d.campos || {};
  const sim = caixa.querySelector('[data-prop="editavel"]');
  const nao = caixa.querySelector('[data-prop="nao"]');
  if (nao) nao.onclick = () => { caixa.innerHTML = '<p class="explica">Tudo bem: o PDF continua só para leitura.</p>'; };
  if (sim) sim.onclick = async () => {
    sim.disabled = true;
    const novo = await criarVersaoEditavelDoPdf(c.nome, c.pedido || "");
    if (!novo) { sim.disabled = false; return; }
    caixa.innerHTML = '<p class="explica">Criei a versão editável de “' + esc(c.nome || "") + "” ao lado. O PDF original continua " +
      "como está.</p>";
  };
}

function ligarConcluirDocumento(caixa, d) {
  const b = caixa.querySelector('[data-prop="concluir"]');
  if (b) b.onclick = () => mostrarCartaoDeConclusao(Object.assign({}, d.campos || {}));
}

/* O editor volta com a conversa (E1): reabrir a conversa reabre ao lado o
   documento que estava aberto nela. */
async function reabrirEditorDaConversa(tid) {
  if (!tid || dupla.abrindo) return;
  const d = await fetch("/api/trabalhos/" + tid + "/documentos").then((x) => (x.ok ? x.json() : null)).catch(() => null);
  if (!d || !d.aberto || estado.trabalhoId !== tid || dupla.abrindo) return;
  if (dupla.doc && dupla.doc.id === d.aberto) return;
  await mostrarDupla(d.aberto);
}

function avisarLadoDaConversa(docId) {
  const tid = estado.trabalhoId;
  if (!tid) return;
  fetch("/api/trabalhos/" + tid + "/lado", {
    method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ editor: docId || 0 }),
  }).catch(() => null);
}
