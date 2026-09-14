/* ------------------------------------------------------ o que está rolando */
/*
   A janelinha dos bastidores. Durante os oitenta segundos em que o modelo lê o
   prompt inteiro, a tela não tinha o que dizer — e mostrava uma barra em 25/25
   que não era progresso, porque os dois números chegavam juntos.

   Cada linha daqui é uma coisa que aconteceu de verdade, com o número que veio
   junto. Nada é escrito para parecer ocupado: quando não há o que dizer, a
   janelinha fica quieta e só o relógio anda.
*/

/* Sem id fixo: cada pergunta abre a sua janelinha, e duas janelinhas com o
   mesmo id fazem a segunda escrever dentro da primeira — foi o que aconteceu
   ao perguntar duas vezes seguidas. As referências ficam guardadas aqui. */
const bastidor = { desde: 0, timer: null, fase: "", palavras: 0,
                   caixa: null, linhasEl: null, relogioEl: null, vivaEl: null,
                   previsao: null, escreveDesde: 0 };

function abrirBastidor(caixa) {
  fecharBastidor();
  bastidor.desde = Date.now();
  bastidor.fase = "";
  bastidor.palavras = 0;
  bastidor.previsao = null;
  bastidor.vivaEl = null;

  caixa.innerHTML = '<div class="bastidor"><div class="bastidor-topo">' + coroa(18) +
    '<span class="bastidor-titulo">o que estou fazendo</span><span class="num"></span>' +
    ic("expand_more", 18) + '</div><div class="bastidor-linhas"></div></div>';

  bastidor.caixa = caixa.querySelector(".bastidor");
  bastidor.caixa.querySelector(".bastidor-topo").onclick = () => bastidor.caixa.classList.toggle("fechado");
  bastidor.relogioEl = caixa.querySelector(".bastidor-topo .num");
  bastidor.linhasEl = caixa.querySelector(".bastidor-linhas");
  bastidor.relogioEl.textContent = "0 s";

  bastidor.timer = setInterval(tiquetaqueBastidor, 250);
}

function anotarBastidor(texto, classe) {
  if (!bastidor.linhasEl) return;
  const segundos = ((Date.now() - bastidor.desde) / 1000).toFixed(1).replace(".", ",");
  bastidor.linhasEl.insertAdjacentHTML("beforeend",
    '<div class="bastidor-linha ' + (classe || "") + '">' +
    '<span class="bastidor-quando">' + segundos + ' s</span>' +
    "<span>" + esc(texto) + "</span></div>");
  bastidor.linhasEl.scrollTop = bastidor.linhasEl.scrollHeight;
}

/* A última linha muda sozinha enquanto a fase dura: é ela que dá o movimento,
   e o que ela mostra é medido — segundos que passaram, palavras que saíram. */
function tiquetaqueBastidor() {
  if (!bastidor.relogioEl || !bastidor.relogioEl.isConnected) {
    clearInterval(bastidor.timer);
    return;
  }
  const passados = (Date.now() - bastidor.desde) / 1000;
  bastidor.relogioEl.textContent = Math.round(passados) + " s";

  const viva = bastidor.vivaEl;
  if (!viva) return;

  if (bastidor.fase === "lendo") {
    const p = bastidor.previsao;
    if (p && p.sabe) {
      // Quanto já passou do que costuma levar. Passou do previsto? A tela diz
      // que passou — esconder isso seria errar duas vezes.
      const parte = Math.min(100, Math.round((passados / p.segundos) * 100));
      viva.innerHTML = "lendo… " + Math.round(passados) + " s de ~" + p.segundos + " s" +
        (passados > p.segundos ? " (passou do previsto)" : "") +
        '<div class="bastidor-barra"><i style="width:' + parte + '%"></i></div>';
    } else {
      viva.innerHTML = "lendo… " + Math.round(passados) + " s" +
        '<div class="bastidor-barra indefinida"><i></i></div>';
    }
  } else if (bastidor.fase === "escrevendo") {
    const desde = (Date.now() - bastidor.escreveDesde) / 1000;
    const taxa = desde > 0.5
      ? (bastidor.palavras / desde).toFixed(1).replace(".", ",")
      : "";
    viva.textContent = "escrevendo… " + plural(bastidor.palavras, "palavra") +
      (taxa ? " · " + taxa + " por segundo" : "");
  }
}

/* A linha viva é transitória: existe para mostrar que a coisa anda. Quando a
   fase acaba, some — porque logo abaixo entra a linha de fato, com o que
   aconteceu. Deixá-la congelada em "lendo… 12 s" com "agora" ao lado seria um
   número parado mentindo que ainda está acontecendo. */
function encerrarFaseViva() {
  if (bastidor.vivaEl) {
    const linha = bastidor.vivaEl.closest(".bastidor-linha");
    if (linha) linha.remove();
    bastidor.vivaEl = null;
  }
}

function faseBastidor(fase, texto) {
  encerrarFaseViva();
  bastidor.fase = fase;
  if (!bastidor.linhasEl) return;
  bastidor.linhasEl.insertAdjacentHTML("beforeend",
    '<div class="bastidor-linha viva"><span class="bastidor-quando">agora</span>' +
    "<span>" + esc(texto) + "</span></div>");
  const ultima = bastidor.linhasEl.lastElementChild;
  bastidor.vivaEl = ultima ? ultima.lastElementChild : null;
  bastidor.linhasEl.scrollTop = bastidor.linhasEl.scrollHeight;
}

function fecharBastidor() {
  clearInterval(bastidor.timer);
  bastidor.fase = "";
  encerrarFaseViva();
  /* Terminou: a janelinha recolhe numa linha so, com o visto no lugar do
     anel. Clicar reabre. */
  const caixa = bastidor.caixa;
  if (caixa && caixa.isConnected && !caixa.classList.contains("fechado")) {
    caixa.classList.add("fechado");
    const anel = caixa.querySelector(".indicador");
    if (anel) anel.outerHTML = '<span class="ic ic-18 marcador-feito">check_circle</span>';
    const titulo = caixa.querySelector(".bastidor-titulo");
    if (titulo) titulo.textContent = "o que fiz";
  }
}

function milhar(n) {
  return Number(n || 0).toLocaleString("pt-BR");
}

/* "0.4 s" nao e portugues, e "0 s" para uma leitura que aconteceu nao e
   numero. Abaixo de um decimo, o que houve foi "menos de um segundo". */
function segundosBR(s) {
  const n = Number(s || 0);
  if (n < 0.1) return "menos de 0,1 s";
  return n.toFixed(1).replace(".", ",") + " s";
}


/* ------------------------------------------- o editor ao lado da conversa */
/*
   Pedir "abra a procuração" e receber o texto transcrito dentro da resposta é
   o pior dos dois mundos: não dá para editar e ainda ocupa a conversa inteira.
   O documento aparece AO LADO da conversa, editável, e a conversa continua ali
   — com o que foi dito, e com a mesma caixa de pedido.

   Da caixa, o pedido vai para um de dois lugares: para o documento ("deixe
   mais formal", "acrescente uma cláusula de foro") ou para a conversa ("qual
   o prazo desta procuração?"). Quem decide é a regra, pelo verbo que abre a
   frase — e a caixa mostra o destino enquanto se digita, com um clique para
   trocar. A alteração cai no documento, marcada, e a pessoa decide se fica.

   A folha tem aspecto de páginas: A4 na escala do PDF, e o espaço entre as
   páginas na altura em que o próprio PDF quebra (a mesma medida do editor de
   Documentos).
*/

const dupla = {
  doc: null, antes: null, pendente: null, ocupada: false, relogio: null,
  paginacao: null, relogioPaginas: null, destino: "",
};

// O rótulo cabe na coluna da conversa; o pedido que vai ao modelo é o inteiro.
const ATALHOS_DO_EDITOR = [["Mais formal", "Deixar mais formal"], ["Citar a lei", "Citar a lei"],
  ["Resumir", "Resumir em 1 página"]];

function editorNaConversaAberto() {
  return Boolean(dupla.doc && $("editor-lado") && $("conversa-col").classList.contains("com-editor"));
}

async function mostrarDupla(id) {
  /* O editor mora ao lado de uma conversa. Vindo de outra tela (Documentos),
     a conversa é a última aberta no Assistente — ou uma nova, com o nome do
     documento. */
  if (!estado.trabalhoId) {
    let aberta = lembrancaDoAssistente.trabalhoId && await abrirTrabalho(lembrancaDoAssistente.trabalhoId);
    if (!aberta) {
      const doc = await fetch("/api/documentos/" + id).then((r) => (r.ok ? r.json() : null));
      const r = await fetch("/api/trabalhos", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ pedido: "Editar " + (doc ? doc.titulo : "documento") }),
      });
      if (r.ok) aberta = await abrirTrabalho((await r.json()).id);
    }
    if (!aberta) return;
    marcarDestino("conversa");
  }

  const r = await fetch("/api/documentos/" + id);
  if (!r.ok) { avisoNaJanela("Não consegui abrir o documento: " + (await erroDe(r)), { icone: "error" }); return; }
  if (dupla.doc && dupla.doc.id !== id) await gravarDupla();
  dupla.doc = await r.json();
  dupla.antes = null;
  dupla.pendente = null;
  dupla.paginacao = null;
  dupla.destino = "";
  desenharEditorAoLado();
}

function desenharEditorAoLado() {
  const d = dupla.doc;
  const c = d.contagem || { palavras: 0 };
  let lado = $("editor-lado");
  if (!lado) {
    lado = document.createElement("aside");
    lado.className = "editor-lado";
    lado.id = "editor-lado";
    $("conversa-col").appendChild(lado);
  }
  $("conversa-col").classList.add("com-editor");
  mostrarLateral(false);
  posicionarEditorAoLado();

  const botao = (cmd, icone, titulo) =>
    '<button data-cmd="' + cmd + '" title="' + titulo + '" aria-label="' + titulo + '">' + ic(icone, 18) + "</button>";
  lado.innerHTML =
    '<div class="edl-topo"><div class="edl-nome">' +
    '<h3 class="edl-titulo" id="dp-titulo" contenteditable="true" spellcheck="false">' + esc(d.titulo) + "</h3>" +
    '<span class="meta" id="dp-selo">versão ' + d.versao + " · " + plural(c.palavras, "palavra") + "</span></div>" +
    '<button class="botao-icone" id="dp-so-editor" title="Abrir no Editor, em tela cheia" aria-label="Abrir no Editor">' + ic("open_in_new", 18) + "</button>" +
    '<button class="botao-icone" id="dp-pdf" title="Exportar PDF" aria-label="Exportar PDF">' + ic("picture_as_pdf", 18) + "</button>" +
    '<button class="botao-icone" id="dp-fechar" title="Fechar o editor" aria-label="Fechar o editor">' + ic("close", 18) + "</button></div>" +

    '<div class="edl-barra">' +
    botao("undo", "undo", "Desfazer") + botao("redo", "redo", "Refazer") + '<span class="edl-vao"></span>' +
    botao("bold", "format_bold", "Negrito") + botao("italic", "format_italic", "Itálico") +
    botao("insertOrderedList", "format_list_numbered", "Numeração") +
    '<button id="dp-citacao" title="Citação" aria-label="Citação">' + ic("format_quote", 18) + "</button>" +
    '<span class="edl-vao"></span>' +
    '<button id="dp-numerar" title="Renumerar as cláusulas">' + ic("format_list_numbered", 16) + "Numerar</button>" +
    '<button id="dp-qualificar" title="Qualificação das partes">' + ic("group", 16) + "Qualificar</button>" +
    '<button id="dp-citar" title="Citar a lei">' + ic("gavel", 16) + "Citar a lei</button>" +
    '<button id="dp-alteracoes" title="Ir até a alteração">' + ic("difference", 16) +
    'Alterações · <span id="dp-alteracoes-n">0</span></button>' +
    '<span class="sinc"><i class="ponto-verde"></i><span id="dp-sinc">ao lado da conversa</span></span>' +
    '<button class="primario" id="dp-salvar">' + ic("save", 16) + "Salvar</button></div>" +

    '<div class="edl-mesa" id="dp-mesa"><div class="edl-papel">' +
    '<div class="ed-folha edl-folha" id="dp-folha" contenteditable="true">' + (d.corpo || "<p><br></p>") + "</div>" +
    '<div class="edl-entre" id="dp-entre"></div></div><div id="dp-abaixo"></div></div>' +

    '<div class="edl-rodape"><span id="dp-paginas">' + plural(c.palavras, "palavra") + "</span>" +
    '<span class="cresce"></span><button id="dp-guardar">Salvar na biblioteca</button>' +
    '<button id="dp-assinar">Assinar</button></div>' +
    '<style id="dp-estilo-paginas"></style>';

  desenharAtalhosDoEditor();
  ligarDupla();
  atualizarPostura();
  desenharPaginas();
  pedirPaginasDaFolha(true);
}

/* Do cabeçalho ao pé da janela: o topo é a altura do cabeçalho da conversa,
   que muda com o título e a meta. */
function posicionarEditorAoLado() {
  const lado = $("editor-lado");
  if (lado) lado.style.top = ($("conversa-topo").offsetHeight + 8) + "px";
}

window.addEventListener("resize", () => {
  if (!editorNaConversaAberto()) return;
  posicionarEditorAoLado();
  desenharPaginas();
});

async function fecharEditorNaConversa() {
  if (!dupla.doc) return;
  clearTimeout(dupla.relogio);
  clearTimeout(dupla.relogioPaginas);
  if ($("dp-folha")) await gravarDupla();
  dupla.doc = null;
  dupla.pendente = null;
  dupla.destino = "";
  const lado = $("editor-lado");
  if (lado) lado.remove();
  const faixa = $("edl-atalhos");
  if (faixa) faixa.remove();
  $("conversa-col").classList.remove("com-editor");
  if (estado.trabalhoId && $("centro").classList.contains("prosa")) mostrarLateral(lateralPreferida());
  atualizarPostura();
}

/* ------------------------------------------------ para onde vai o pedido */

// O verbo que abre a frase diz se é mudança no documento. Sem ele, é conversa.
const RE_PEDIDO_DE_MUDANCA = new RegExp(
  "^\\s*(?:(?:por favor|pfv|pode|poderia|agora|entao|quero que voce|preciso que voce|me ajude a)[\\s,]+)*" +
  "(deix[ae]|torn[ae]|reescrev[ae]|escrev[ae]|redij[ao]|redige|troqu?e|troca|substitu[ai]|acrescent[ae]|" +
  "adicion[ae]|inclu[ai]|insir[ao]|insere|alter[ae]|mud[ae]|corrij[ao]|corrige|remov[ae]|retir[ae]|" +
  "apagu?e|apaga|resum[ae]|encurt[ae]|melhor[ae]|formaliz[ae]|cit[ae]|numer[ae]|renumer[ae]|revis[ae]|" +
  "ajust[ae]|complet[ae]|traduz[ae]?)\\b");

function destinoDoPedido(texto) {
  if (dupla.destino) return dupla.destino;
  const plano = String(texto || "").normalize("NFD").replace(/[\u0300-\u036f]/g, "").toLowerCase();
  if (!plano.trim()) return "";
  return RE_PEDIDO_DE_MUDANCA.test(plano) ? "documento" : "conversa";
}

function desenharAtalhosDoEditor() {
  let faixa = $("edl-atalhos");
  if (!faixa) {
    faixa = document.createElement("div");
    faixa.id = "edl-atalhos";
    faixa.className = "edl-atalhos";
    $("cartao-campo").before(faixa);
  }
  faixa.innerHTML = '<div class="edl-destino" role="group" aria-label="Para onde vai o pedido">' +
    '<button data-edl-destino="documento" title="O pedido muda o documento aberto ao lado">' + ic("edit_note", 16) + "No documento</button>" +
    '<button data-edl-destino="conversa" title="O pedido é uma pergunta para a conversa">' + ic("forum", 16) + "Na conversa</button></div>" +
    ATALHOS_DO_EDITOR.map((a) => '<button class="edl-atalho" data-dp-atalho="' + esc(a[1]) + '" title="' + esc(a[1]) + '">' +
      esc(a[0]) + "</button>").join("");
  faixa.querySelectorAll("[data-edl-destino]").forEach((b) => {
    b.onclick = () => {
      dupla.destino = dupla.destino === b.dataset.edlDestino ? "" : b.dataset.edlDestino;
      atualizarDestino();
      $("pedido").focus();
    };
  });
  faixa.querySelectorAll("[data-dp-atalho]").forEach((b) => {
    b.onclick = () => pedirNoDocumento(b.dataset.dpAtalho);
  });
  atualizarDestino();
}

function atualizarDestino() {
  const faixa = $("edl-atalhos");
  if (!faixa) return;
  const alvo = destinoDoPedido($("pedido").value);
  faixa.querySelectorAll("[data-edl-destino]").forEach((b) => {
    b.classList.toggle("ativa", b.dataset.edlDestino === alvo);
  });
}

$("pedido").addEventListener("input", atualizarDestino);

/* ----------------------------------------------------------- as páginas */

const A4_ALTURA_POR_LARGURA = 297 / 210;
const ESPACO_ENTRE_PAGINAS = 24;

function htmlDaFolha() {
  // O cartão da alteração é da tela, não do documento.
  const folha = $("dp-folha").cloneNode(true);
  folha.querySelectorAll(".dupla-cartao").forEach((c) => c.remove());
  return folha.innerHTML;
}

function pedirPaginasDaFolha(agora) {
  clearTimeout(dupla.relogioPaginas);
  const fazer = async () => {
    if (!$("dp-folha") || !dupla.doc) return;
    try {
      const r = await fetch("/api/documentos/" + dupla.doc.id + "/paginacao", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ corpo: htmlDaFolha() }),
      });
      if (!r.ok || !dupla.doc) return;
      dupla.paginacao = await r.json();
      if (dupla.paginacao.formato) dupla.doc.formato = dupla.paginacao.formato;
      desenharPaginas();
    } catch (err) { /* medir a página não pode atrapalhar quem está escrevendo */ }
  };
  if (agora) fazer(); else dupla.relogioPaginas = setTimeout(fazer, 700);
}

/* O caminho do bloco dentro da folha, para a regra de margem não precisar de
   classe nem estilo NO bloco: o que está dentro da folha vai para o arquivo. */
function seletorNaFolha(el) {
  const partes = [];
  let n = el;
  while (n && n.id !== "dp-folha") {
    partes.unshift(":nth-child(" + (Array.prototype.indexOf.call(n.parentNode.children, n) + 1) + ")");
    n = n.parentNode;
  }
  return "#dp-folha > " + partes.join(" > ");
}

/* Cada página tem a altura de um A4 na largura da folha. Onde o PDF quebra, o
   texto seguinte desce para o topo da próxima página (margem de cima
   incluída), e o recorte da cor da mesa é desenhado no espaço entre elas. */
function desenharPaginas() {
  const folha = $("dp-folha");
  const entre = $("dp-entre");
  const estilo = $("dp-estilo-paginas");
  if (!folha || !entre || !estilo || !dupla.doc) return;
  if (dupla.doc.formato) vestirFolhaEm(folha, dupla.doc.formato);
  estilo.textContent = "";
  entre.innerHTML = "";
  folha.style.minHeight = "";

  const largura = folha.offsetWidth;
  if (!largura) return;
  const altura = largura * A4_ALTURA_POR_LARGURA;
  const margem = parseFloat(getComputedStyle(folha).paddingBottom) || 0;
  const mapa = dupla.paginacao;
  const elementos = mapa ? blocosDaFolha(folha) : [];
  const topo = () => folha.getBoundingClientRect().top;

  let inicio = 0;
  let pagina = 1;
  const regras = [];
  if (mapa && elementos.length === mapa.de_bloco.length) {
    for (let i = 1; i < elementos.length; i += 1) {
      if (mapa.de_bloco[i] === mapa.de_bloco[i - 1]) continue;
      const fimDoTexto = elementos[i - 1].getBoundingClientRect().bottom - topo();
      const fimDaPagina = Math.max(inicio + altura, fimDoTexto + margem);
      const proxima = fimDaPagina + ESPACO_ENTRE_PAGINAS;
      const atual = elementos[i].getBoundingClientRect().top - topo();
      const margemAtual = parseFloat(getComputedStyle(elementos[i]).marginTop) || 0;
      regras.push(seletorNaFolha(elementos[i]) + " { margin-top: " +
        Math.max(0, margemAtual + proxima + margem - atual).toFixed(1) + "px !important; }");
      estilo.textContent = regras.join("\n");
      pagina += 1;
      entre.insertAdjacentHTML("beforeend", '<div class="edl-entre-paginas" style="top:' + fimDaPagina.toFixed(1) +
        "px;height:" + ESPACO_ENTRE_PAGINAS + 'px">página ' + pagina + "</div>");
      inicio = proxima;
    }
  }
  /* Página que o PDF tem e nenhum bloco começa nela: é a continuação de um
     parágrafo longo. A folha cresce até ela, e o recorte só é desenhado onde
     não há texto embaixo — cortar uma linha ao meio seria pior que não
     mostrar a quebra. */
  let fimDaFolha = inicio + altura;
  const ultimo = elementos.length ? elementos[elementos.length - 1] : null;
  const fimDoConteudo = ultimo ? ultimo.getBoundingClientRect().bottom - topo() + margem : 0;
  for (let resta = (mapa ? mapa.paginas : 1) - pagina; resta > 0; resta -= 1) {
    pagina += 1;
    if (fimDaFolha >= fimDoConteudo) {
      entre.insertAdjacentHTML("beforeend", '<div class="edl-entre-paginas" style="top:' + fimDaFolha.toFixed(1) +
        "px;height:" + ESPACO_ENTRE_PAGINAS + 'px">página ' + pagina + "</div>");
    }
    fimDaFolha += ESPACO_ENTRE_PAGINAS + altura;
  }
  folha.style.minHeight = fimDaFolha.toFixed(1) + "px";

  const contador = $("dp-paginas");
  const c = dupla.doc.contagem || { palavras: 0 };
  if (contador) contador.textContent = plural(mapa ? mapa.paginas : pagina, "página") + " · " + plural(c.palavras, "palavra");
}

/* -------------------------------------------------------- a folha viva */

function ligarDupla() {
  const lado = $("editor-lado");
  $("dp-fechar").onclick = () => fecharEditorNaConversa();
  $("dp-so-editor").onclick = async () => { const id = dupla.doc.id; await fecharEditorNaConversa(); abrirDocumento(id); };
  $("dp-assinar").onclick = () => { marcarDestino("assinar"); mostrarAssinar(); };
  $("dp-citar").onclick = painelCodigosNaDupla;
  $("dp-numerar").onclick = renumerarClausulas;
  $("dp-qualificar").onclick = inserirQualificacao;
  $("dp-guardar").onclick = () => guardarNaBiblioteca(dupla.doc.id);
  $("dp-pdf").onclick = () => { window.location.href = "/api/documentos/" + dupla.doc.id + "/pdf"; };
  $("dp-salvar").onclick = () => gravarDupla();
  $("dp-citacao").onmousedown = (e) => { e.preventDefault(); document.execCommand("formatBlock", false, "blockquote"); marcarDuplaSuja(); };
  $("dp-alteracoes").onclick = () => {
    const m = $("dp-folha").querySelector(".ed-novo");
    if (m) m.scrollIntoView({ behavior: "smooth", block: "center" });
  };
  $("dp-alteracoes-n").textContent = $("dp-folha").querySelectorAll(".ed-novo").length;

  lado.querySelectorAll("[data-cmd]").forEach((b) => {
    b.onmousedown = (e) => { e.preventDefault(); document.execCommand(b.dataset.cmd, false, null); marcarDuplaSuja(); };
  });
  $("dp-folha").oninput = () => marcarDuplaSuja();
  $("dp-titulo").oninput = () => marcarDuplaSuja();
}

/* O pedido vira alteração no documento, marcada — e a conversa registra o
   pedido e o que foi feito, como qualquer outra coisa dita nela. */
async function pedirNoDocumento(pedido) {
  if (!pedido || dupla.ocupada || !dupla.doc) return;
  dupla.ocupada = true;
  const titulo = dupla.doc.titulo;
  const centro = $("centro");
  centro.insertAdjacentHTML("beforeend", bolhaPessoa(pedido));
  const resposta = document.createElement("div");
  resposta.className = "resposta";
  resposta.innerHTML = '<p class="nota">escrevendo em “' + esc(titulo) + "”… isso leva cerca de um minuto nesta máquina</p>";
  centro.appendChild(resposta);
  atualizarPostura();
  rolar();
  if ($("dp-sinc")) $("dp-sinc").textContent = "escrevendo…";

  // Antes de mexer, guarda o documento inteiro: é isso que o "Desfazer" devolve.
  const antes = htmlDaFolha();
  const docId = dupla.doc.id;
  try {
    const r = await fetch("/api/documentos/" + docId + "/assistente", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ pedido: pedido, trecho: trechoSelecionadoNaDupla(), trabalho_id: estado.trabalhoId || "" }),
    });
    if (!r.ok) throw new Error(await erroDe(r));
    const sugestao = await r.json();
    if (!dupla.doc || dupla.doc.id !== docId) throw new Error("o editor foi fechado antes de a alteração chegar");

    dupla.antes = antes;
    aplicarNaDupla(sugestao);
    resposta.innerHTML = '<div class="texto">' + esc(sugestao.sobre
      ? "Troquei o trecho que você selecionou em “" + titulo + "”. A alteração está marcada no documento."
      : "Escrevi no fim de “" + titulo + "”. A alteração está marcada — confira antes de manter.") + "</div>" +
      '<blockquote class="edl-trecho">' + esc(sugestao.sugestao.slice(0, 180)) + "</blockquote>" +
      '<div class="linha-form"><button data-edl-ver="1">Ver no documento</button>' +
      '<button data-edl-desfazer="1">Desfazer</button></div>';
    resposta.querySelector("[data-edl-ver]").onclick = () => {
      const marca = $("dp-folha") && $("dp-folha").querySelector(".ed-novo");
      if (marca) marca.scrollIntoView({ behavior: "smooth", block: "center" });
      else avisoNaJanela("Essa alteração já foi aceita e virou parte do texto");
    };
    resposta.querySelector("[data-edl-desfazer]").onclick = () => {
      if (!dupla.doc || dupla.doc.id !== docId) { avisoNaJanela("Abra o documento de novo para desfazer"); return; }
      $("dp-folha").innerHTML = antes;
      dupla.pendente = null;
      gravarDupla();
      marcarDuplaSuja();
      resposta.innerHTML = '<div class="texto">Desfeito. “' + esc(titulo) + "” voltou ao que era antes dessa alteração.</div>";
    };
  } catch (err) {
    resposta.innerHTML = '<div class="texto">Não consegui: ' + esc(String((err && err.message) || err)) + "</div>";
  } finally {
    dupla.ocupada = false;
    if ($("dp-sinc")) $("dp-sinc").textContent = "ao lado da conversa";
    rolar();
  }
}

function aplicarNaDupla(sugestao) {
  const folha = $("dp-folha");
  folha.querySelectorAll(".ed-novo").forEach((m) => desmarcar(m));

  const marca = document.createElement("mark");
  marca.className = "ed-novo";
  marca.textContent = sugestao.sugestao;

  const sel = window.getSelection();
  if (sugestao.sobre && sel && sel.rangeCount && !sel.isCollapsed &&
      folha.contains(sel.anchorNode)) {
    const faixa = sel.getRangeAt(0);
    faixa.deleteContents();
    faixa.insertNode(marca);
  } else {
    const bloco = document.createElement("p");
    bloco.appendChild(marca);
    folha.appendChild(bloco);
  }

  dupla.pendente = { aviso: sugestao.aviso, resumo: sugestao.sugestao.slice(0, 120) };
  desenharCartaoDaAlteracao();
  marcarDuplaSuja();
  marca.scrollIntoView({ behavior: "smooth", block: "center" });
}

function desenharCartaoDaAlteracao() {
  const antigo = $("dp-cartao");
  if (antigo) antigo.remove();
  if (!dupla.pendente) return;

  const marca = $("dp-folha").querySelector(".ed-novo");
  if (!marca) return;

  const cartao = document.createElement("div");
  cartao.className = "dupla-cartao";
  cartao.id = "dp-cartao";
  cartao.contentEditable = "false";
  cartao.innerHTML = '<span class="rotulo-cartao">Alteração sugerida agora</span>' +
    "<p>" + esc(dupla.pendente.resumo) + "</p>" +
    '<p class="explica">' + esc(dupla.pendente.aviso) + "</p>" +
    '<div class="linha-form"><button id="dp-descartar">Descartar</button>' +
    '<button class="primario" id="dp-manter">Manter</button></div>';
  marca.closest("p, li, h1, h2, h3, div").after(cartao);

  $("dp-manter").onclick = () => {
    $("dp-folha").querySelectorAll(".ed-novo").forEach((m) => desmarcar(m));
    dupla.pendente = null;
    cartao.remove();
    marcarDuplaSuja();
    gravarDupla();
  };
  $("dp-descartar").onclick = () => {
    if (dupla.antes !== null) $("dp-folha").innerHTML = dupla.antes;
    dupla.pendente = null;
    const c = $("dp-cartao");
    if (c) c.remove();
    marcarDuplaSuja();
    gravarDupla();
  };
}

/* Tirar a marca sem tirar o texto: o conteúdo fica, o destaque sai. */
function desmarcar(marca) {
  const pai = marca.parentNode;
  while (marca.firstChild) pai.insertBefore(marca.firstChild, marca);
  pai.removeChild(marca);
}

function trechoSelecionadoNaDupla() {
  const sel = window.getSelection();
  if (!sel || sel.isCollapsed) return "";
  const folha = $("dp-folha");
  return folha && folha.contains(sel.anchorNode) ? sel.toString().trim().slice(0, 2500) : "";
}

function marcarDuplaSuja() {
  if (!$("dp-folha")) return;
  $("dp-selo").textContent = "alterações não salvas";
  $("dp-alteracoes-n").textContent = $("dp-folha").querySelectorAll(".ed-novo").length;
  clearTimeout(dupla.relogio);
  dupla.relogio = setTimeout(gravarDupla, 1600);
  desenharPaginas();
  pedirPaginasDaFolha();
}

async function gravarDupla() {
  if (!dupla.doc || !$("dp-folha")) return;
  clearTimeout(dupla.relogio);
  const id = dupla.doc.id;
  const r = await fetch("/api/documentos/" + id, {
    method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ corpo: htmlDaFolha(), titulo: $("dp-titulo").textContent.trim() }),
  });
  if (!$("dp-selo") || !dupla.doc || dupla.doc.id !== id) return;
  if (!r.ok) { $("dp-selo").textContent = "não consegui salvar"; return; }

  const d = await r.json();
  dupla.doc = Object.assign(dupla.doc, d);
  const c = d.contagem || { palavras: 0 };
  $("dp-selo").textContent = "versão " + d.versao + " · " + plural(c.palavras, "palavra") +
    " · salvo às " + new Date().toTimeString().slice(0, 5);
}

async function painelCodigosNaDupla() {
  const r = await fetch("/api/leis");
  const d = await r.json();
  const instalados = d.codigos.filter((c) => c.instalado);
  if (!instalados.length) { avisoCert(d.porque); return; }
  const termo = await perguntar({ titulo: "Citar um artigo", contexto: "Documentos › Códigos de lei", campo: { rotulo: "Qual artigo?", placeholder: "número ou palavra", icone: "gavel" }, confirmar: "Procurar" });
  if (!termo) return;

  const busca = await fetch("/api/leis/procurar?termo=" + encodeURIComponent(termo));
  const achados = (await busca.json()).achados || [];
  if (!achados.length) { avisoCert("não achei esse artigo nos códigos instalados"); return; }

  const a = achados[0];
  if (a.revogado && !(await confirmar({ titulo: "Artigo revogado", contexto: a.citacao, texto: "O " + a.citacao + " está revogado: continua no texto compilado por referência histórica, mas não está em vigor.", confirmar: "Inserir mesmo assim", perigo: true }))) return;
  aplicarNaDupla({
    sugestao: "Nos termos do " + a.citacao + ": “" + a.texto.replace(/\s+/g, " ").slice(0, 700) + "”",
    sobre: "",
    aviso: "Texto oficial do código instalado — confira se é o artigo que você quer citar.",
  });
}


/* ------------------------------------------- o documento aberto na conversa */
/*
   "3 arquivos citados" era um texto que a pessoa lia e acreditava. Conferir de
   verdade exigia abrir o PDF por fora, achar a página e procurar o parágrafo
   com o olho.

   Aqui o documento abre na própria conversa, na página em que o trecho está,
   com o trecho marcado. É o PDF de verdade rasterizado — não uma aproximação
   em HTML: o que aparece na tela é o arquivo.
*/

const visor = { aberto: null, pagina: 1, total: 0, escala: 100, marcas: [], pergunta: "" };

async function abrirCitacao(nome, trecho, pergunta, ondeColocar) {
  const caixa = ondeColocar;
  caixa.innerHTML = '<div class="visor"><p class="nota">procurando o trecho no documento…</p></div>';

  const r = await fetch("/api/biblioteca/citacao", {
    method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ nome: nome, trecho: trecho, pergunta: pergunta || "" }),
  });
  if (!r.ok) {
    caixa.innerHTML = '<div class="visor"><p class="explica">' + esc(await erroDe(r)) + "</p></div>";
    return;
  }

  const d = await r.json();
  visor.aberto = d;
  visor.pagina = d.pagina || 1;
  visor.total = d.total || 0;
  visor.escala = 100;
  visor.marcas = d.marcas || [];
  visor.caixa = caixa;
  desenharVisor();
}

function desenharVisor() {
  const d = visor.aberto;
  if (!d) return;

  if (!d.desenhavel) {
    // Honesto: docx e txt não têm página para desenhar. Em vez de fingir uma,
    // a tela diz o que dá para fazer.
    visor.caixa.innerHTML = '<div class="visor"><div class="visor-topo">' +
      '<div><b>' + esc(d.nome) + "</b>" +
      '<div class="rotulo">aberto da sua máquina · ' + tamanho(d.bytes) + "</div></div>" +
      '<div class="visor-acoes"><button data-vs="fora">Abrir fora</button>' +
      '<button data-vs="fechar">Fechar</button></div></div>' +
      '<p class="explica">Só PDF tem página para desenhar aqui. Este é ' +
      esc((d.nome.split(".").pop() || "").toUpperCase()) +
      " — dá para abrir no programa padrão do Windows.</p></div>";
    ligarVisor();
    return;
  }

  visor.caixa.innerHTML = '<div class="visor">' +
    '<div class="visor-topo"><div><b>' + esc(d.nome) + "</b>" +
    '<div class="rotulo">aberto da sua máquina · ' + tamanho(d.bytes) + "</div></div>" +
    '<div class="visor-acoes">' +
    '<button data-vs="antes" ' + (visor.pagina <= 1 ? "disabled" : "") + ">‹</button>" +
    '<span class="rotulo">pág. ' + visor.pagina + " / " + visor.total + "</span>" +
    '<button data-vs="depois" ' + (visor.pagina >= visor.total ? "disabled" : "") + ">›</button>" +
    '<span class="visor-divisa"></span>' +
    '<button data-vs="menos">−</button><span class="rotulo">' + visor.escala + "%</span>" +
    '<button data-vs="mais">+</button>' +
    '<span class="visor-divisa"></span>' +
    '<button data-vs="fora">Abrir fora</button>' +
    '<button data-vs="fechar">Fechar</button></div></div>' +

    '<div class="visor-miniaturas">' + miniaturasDoVisor() + "</div>" +

    '<div class="visor-corpo"><div class="visor-rolagem">' +
    '<div class="visor-pagina">' +
    '<img src="/api/biblioteca/pagina?nome=' + encodeURIComponent(d.nome) +
    "&numero=" + visor.pagina + "&largura=" + Math.round(9 * visor.escala) +
    '" alt="página ' + visor.pagina + '">' +
    (visor.pagina === d.pagina ? marcasDoVisor() : "") + "</div></div>" +

    '<aside class="visor-porque"><span class="rotulo">por que este trecho</span>' +
    porqueDoVisor(d) +
    '<p class="rotulo visor-selo">lido localmente · nada enviado</p></aside></div></div>';

  ligarVisor();
}

function miniaturasDoVisor() {
  const d = visor.aberto;
  // Cinco em volta da página atual: a fita inteira de um contrato de 60
  // páginas seria 60 requisições de imagem para mostrar o que ninguém olha.
  const primeira = Math.max(1, Math.min(visor.pagina - 2, Math.max(1, visor.total - 4)));
  const fim = Math.min(visor.total, primeira + 4);
  let html = "";
  for (let n = primeira; n <= fim; n++) {
    html += '<button class="visor-mini' + (n === visor.pagina ? " atual" : "") +
      '" data-vs-pag="' + n + '" title="página ' + n + '">' +
      '<img src="/api/biblioteca/pagina?nome=' + encodeURIComponent(d.nome) +
      "&numero=" + n + '&largura=240" alt="página ' + n + '" loading="lazy"></button>';
  }
  return html + '<span class="rotulo">pág. ' + visor.pagina + " de " + visor.total + "</span>";
}

/* As marcas vêm em fração da página, não em pixel: a imagem muda de tamanho
   com o zoom e com a janela, e a marca acompanha sem recalcular nada. */
function marcasDoVisor() {
  return visor.marcas.map((m) =>
    '<i class="visor-marca" style="left:' + (m.x * 100).toFixed(3) + "%;top:" +
    (m.y * 100).toFixed(3) + "%;width:" + (m.w * 100).toFixed(3) + "%;height:" +
    (m.h * 100).toFixed(3) + '%"></i>').join("");
}

function porqueDoVisor(d) {
  if (!d.achou) {
    return '<p class="explica">Não consegui localizar este trecho dentro do ' +
      "arquivo — pode ser um PDF escaneado, ou o arquivo pode ter mudado desde " +
      "que eu li. A página está aqui, mas sem marca: prefiro não destacar o " +
      "lugar errado.</p>";
  }
  const p = d.porque || { termos: [] };
  if (!p.termos.length) {
    return '<p class="explica">Este trecho entrou pela busca no texto inteiro, ' +
      "não por uma palavra específica da sua pergunta.</p>";
  }
  return '<p class="explica">Da sua pergunta, aparecem aqui: <b>' +
    p.termos.map(esc).join("</b>, <b>") + "</b>.</p>" +
    '<p class="explica">' + plural(p.quantos, "palavra") + " de " + p.de +
    " que você usou estão neste pedaço.</p>";
}

function ligarVisor() {
  const caixa = visor.caixa;
  const ir = (n) => { visor.pagina = Math.max(1, Math.min(visor.total, n)); desenharVisor(); };

  caixa.querySelectorAll("[data-vs]").forEach((b) => {
    b.onclick = () => {
      const o = b.dataset.vs;
      if (o === "antes") ir(visor.pagina - 1);
      else if (o === "depois") ir(visor.pagina + 1);
      else if (o === "mais") { visor.escala = Math.min(200, visor.escala + 25); desenharVisor(); }
      else if (o === "menos") { visor.escala = Math.max(50, visor.escala - 25); desenharVisor(); }
      else if (o === "fechar") { caixa.innerHTML = ""; visor.aberto = null; }
      else if (o === "fora") {
        fetch("/api/biblioteca/abrir-pasta", {
          method: "POST", headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ caminho: visor.aberto.caminho.replace(/[^\\/]+$/, "") }),
        });
      }
    };
  });
  caixa.querySelectorAll("[data-vs-pag]").forEach((b) => {
    b.onclick = () => ir(Number(b.dataset.vsPag));
  });
}


/* ------------------------------------------- o que o Word não faz por aqui */
/*
   O editor em si o Word já faz. O que não faz é o que é específico de redigir
   contrato em português do Brasil: renumerar cláusulas levando as referências
   cruzadas junto, e qualificar uma parte com o que já está em Cadastros.
*/

/* A folha do editor ou a da tela dividida — o que estiver aberto. */
function folhaAberta() {
  return $("dp-folha") || $("ed-folha");
}

function documentoAberto() {
  if ($("dp-folha") && dupla.doc) return dupla.doc;
  return escr.doc;
}

function abaixoDoEditor() {
  return $("dp-abaixo") || $("ed-abaixo");
}

async function renumerarClausulas() {
  const folha = folhaAberta();
  const doc = documentoAberto();
  if (!folha || !doc) return;

  const r = await fetch("/api/documentos/" + doc.id + "/clausulas", {
    method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ corpo: folha.innerHTML }),
  });
  if (!r.ok) { avisoCert(await erroDe(r)); return; }
  const d = await r.json();

  if (!d.clausulas) {
    avisoCert("não achei cláusula numerada neste documento");
    return;
  }
  if (!d.trocas.length) {
    avisoCert(plural(d.clausulas, "cláusula") + " — já estão em ordem" +
      (d.quebradas.length ? ", mas há referência apontando para o nada" : ""));
    if (d.quebradas.length) mostrarQuebradas(d.quebradas);
    return;
  }

  mostrarRenumeracao(d, folha);
}

/* Renumerar mexe no contrato inteiro de uma vez. A lista do que vai mudar
   aparece ANTES, e nada é gravado sem o sim. */
function mostrarRenumeracao(d, folha) {
  const antes = folha.innerHTML;
  const clausulas = d.trocas.filter((t) => t.tipo === "clausula");
  const refs = d.trocas.filter((t) => t.tipo === "referencia");

  const caixa = document.createElement("div");
  caixa.className = "proposta";
  caixa.innerHTML = '<div class="proposta-topo">' +
    '<span class="rotulo">vou renumerar</span>' +
    "<b>" + plural(clausulas.length, "cláusula") +
    (refs.length ? " e " + plural(refs.length, "referência") : "") + "</b></div>" +
    '<div class="renum">' + d.trocas.map((t) =>
      '<div class="renum-linha"><span class="rotulo">' +
      (t.tipo === "referencia" ? "referência" : "cláusula") + "</span>" +
      "<span>" + esc(t.de) + "</span><span class=\"renum-seta\">→</span>" +
      "<b>" + esc(t.para) + "</b></div>").join("") + "</div>" +
    (refs.length
      ? '<p class="explica">As referências cruzadas vão junto: é a metade do ' +
        "trabalho que costuma ficar para trás, e é ela que gera a cláusula 7 " +
        "citando a cláusula 4 depois que a 4 virou 5.</p>"
      : "") +
    (d.quebradas.length
      ? '<p class="explica">Continua apontando para o nada: ' +
        d.quebradas.map((q) => esc(q.texto)).join(", ") +
        " — não existe cláusula com esse número.</p>"
      : "") +
    '<div class="linha-form"><button class="primario" data-renum="sim">Renumerar</button>' +
    '<button data-renum="nao">Deixa como está</button></div>';

  const destino = abaixoDoEditor() || folha.parentElement;
  destino.innerHTML = "";
  destino.appendChild(caixa);
  caixa.scrollIntoView({ behavior: "smooth", block: "center" });

  caixa.querySelector('[data-renum="nao"]').onclick = () => { caixa.remove(); };
  caixa.querySelector('[data-renum="sim"]').onclick = () => {
    folha.innerHTML = d.texto;
    caixa.innerHTML = '<div class="proposta-topo"><span class="rotulo">feito</span>' +
      "<b>" + plural(d.trocas.length, "troca") + " aplicada" +
      (d.trocas.length === 1 ? "" : "s") + "</b></div>" +
      '<div class="linha-form"><button data-renum="desfazer">Desfazer</button></div>';
    caixa.querySelector('[data-renum="desfazer"]').onclick = () => {
      folha.innerHTML = antes;
      caixa.remove();
      salvarOndeEstiver();
    };
    salvarOndeEstiver();
  };
}

function mostrarQuebradas(quebradas) {
  const destino = abaixoDoEditor();
  if (!destino) return;
  destino.innerHTML = '<div class="painel" style="margin-top:16px">' +
    "<h3>Referência apontando para o nada</h3>" +
    '<p class="explica">' + quebradas.map((q) => esc(q.texto)).join(", ") +
    " — não existe cláusula com esse número neste documento. " +
    "É o tipo de erro que passa na leitura e aparece na discussão.</p></div>";
}

/* --------------------------------------------------- notas na margem

   A conferência já sabia apontar o parágrafo — só que dizia isso numa lista à
   parte, e quem lia tinha que achar o parágrafo com o olho. Aqui a marca fica
   ao lado da linha a que ela se refere.

   Como a quebra de página, a marca é desenhada POR CIMA da folha: o que está
   dentro do contenteditable acaba no contrato gravado, e nota de margem não é
   conteúdo do contrato. */

const GRAU_MARCA = { impede: "!", confira: "?", comentario: "•" };

async function carregarNotas() {
  const folha = folhaAberta();
  const doc = documentoAberto();
  if (!folha || !doc || !$("ed-notas")) return;

  try {
    const r = await fetch("/api/documentos/" + doc.id + "/notas", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ corpo: folha.innerHTML }),
    });
    if (!r.ok) return;
    escr.notas = await r.json();
  } catch (err) { return; }
  desenharNotas();
}

function desenharNotas() {
  const folha = $("ed-folha");
  const tela = $("ed-notas");
  const dados = escr.notas;
  if (!folha || !tela || !dados) return;

  const elementos = blocosDaFolha(folha);
  tela.innerHTML = "";
  if (elementos.length !== dados.blocos) return;

  const topo = tela.getBoundingClientRect().top;
  const porBloco = new Map();
  dados.notas.forEach((n) => {
    if (n.bloco < 0 || n.bloco >= elementos.length) return;
    if (!porBloco.has(n.bloco)) porBloco.set(n.bloco, []);
    porBloco.get(n.bloco).push(n);
  });

  porBloco.forEach((notas, bloco) => {
    const grave = notas.find((n) => n.grau === "impede") || notas[0];
    const marca = document.createElement("button");
    marca.className = "ed-nota " + esc(grave.grau);
    marca.textContent = GRAU_MARCA[grave.grau] || "•";
    marca.title = notas.map((n) => n.titulo).join(" · ");
    marca.style.top = (elementos[bloco].getBoundingClientRect().top - topo) + "px";
    marca.onclick = () => abrirNota(notas, elementos[bloco]);
    tela.appendChild(marca);
  });
}

function abrirNota(notas, elemento) {
  const destino = abaixoDoEditor();
  if (!destino) return;
  elemento.scrollIntoView({ behavior: "smooth", block: "center" });

  destino.innerHTML = '<div class="painel" style="margin-top:16px"><h3>Nesta linha</h3>' +
    '<p class="explica corta">' + esc(elemento.textContent.slice(0, 160)) + "</p>" +
    notas.map((n) =>
      '<div class="ed-nota-item ' + esc(n.grau) + '">' +
      '<span class="rotulo">' + (n.origem === "regra" ? "conferência" : esc(n.origem)) +
      " · " + esc(n.titulo) + "</span><p>" + esc(n.texto) + "</p>" +
      (n.id ? '<div class="linha-form"><button data-resolver="' + n.id + '">Resolver</button>' +
        '<button class="perigo" data-apagar="' + n.id + '">Apagar</button></div>' : "") +
      "</div>").join("") +
    '<div class="linha-form"><button id="nota-fechar">Fechar</button></div></div>';

  $("nota-fechar").onclick = () => { destino.innerHTML = ""; };
  destino.querySelectorAll("[data-resolver]").forEach((b) => {
    b.onclick = () => mexerNaNota(b.dataset.resolver, "resolver");
  });
  destino.querySelectorAll("[data-apagar]").forEach((b) => {
    b.onclick = () => mexerNaNota(b.dataset.apagar, "apagar");
  });
}

async function mexerNaNota(id, acao) {
  const doc = documentoAberto();
  const url = "/api/documentos/" + doc.id + "/comentarios/" + id;
  const r = acao === "apagar"
    ? await fetch(url, { method: "DELETE" })
    : await fetch(url + "/resolver", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ resolvido: true }),
      });
  if (!r.ok) { avisoCert(await erroDe(r)); return; }
  const destino = abaixoDoEditor();
  if (destino) destino.innerHTML = "";
  carregarNotas();
}

/* Comentar não é pedir alteração: a resposta é observação para quem lê
   decidir, e não texto para entrar no contrato. Por isso o trecho é
   obrigatório — comentário sobre "o documento" não gruda em lugar nenhum. */
async function comentarTrecho() {
  const trecho = trechoSelecionado();
  const destino = abaixoDoEditor();
  const doc = documentoAberto();
  if (!destino || !doc) return;

  if (!trecho || trecho.length < 12) {
    destino.innerHTML = '<div class="painel" style="margin-top:16px"><h3>Comentar</h3>' +
      '<p class="explica">Selecione antes, no texto, o trecho que você quer que eu ' +
      "comente. Sem trecho o comentário não tem onde ficar preso.</p></div>";
    return;
  }

  destino.innerHTML = '<div class="painel" style="margin-top:16px">' +
    '<p class="nota">lendo o trecho… isso leva cerca de um minuto nesta máquina</p></div>';

  const r = await fetch("/api/documentos/" + doc.id + "/comentar", {
    method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ trecho: trecho }),
  });
  if (!r.ok) { destino.innerHTML = '<div class="painel"><p class="explica">' +
    esc(await erroDe(r)) + "</p></div>"; return; }
  const d = await r.json();

  destino.innerHTML = '<div class="painel" style="margin-top:16px"><h3>Comentário</h3>' +
    '<p class="explica corta">sobre: ' + esc(d.trecho.slice(0, 140)) + "</p>" +
    '<div class="ed-nota-item comentario"><p>' + esc(d.texto) + "</p></div>" +
    '<p class="explica">' + esc(d.aviso) + "</p>" +
    '<div class="linha-form"><button class="perigo" id="nota-apagar">Apagar</button>' +
    '<button id="nota-fechar2">Fechar</button></div></div>';

  $("nota-fechar2").onclick = () => { destino.innerHTML = ""; };
  $("nota-apagar").onclick = () => mexerNaNota(d.id, "apagar");
  carregarNotas();
}

/* ------------------------------------------------------ controlar alterações

   O Word marca cada tecla enquanto se digita. Aqui a marca vem da comparação
   com uma versão gravada, e não de interceptar a digitação — interceptar tecla
   dentro de um campo editável é o caminho curto para perder texto de contrato,
   e texto de contrato perdido não tem conserto do lado de cá.

   O que interessa é o mesmo: o que entrou, o que saiu, o que mudou, e o
   caminho de volta para cada um, um a um. */

async function painelAlteracoes(desde) {
  const destino = abaixoDoEditor();
  const folha = folhaAberta();
  const doc = documentoAberto();
  if (!destino || !folha || !doc) return;

  destino.innerHTML = '<div class="painel" style="margin-top:16px"><p class="nota">comparando…</p></div>';
  const r = await fetch("/api/documentos/" + doc.id + "/alteracoes", {
    method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ corpo: folha.innerHTML, desde: desde || 0 }),
  });
  if (!r.ok) { destino.innerHTML = '<div class="painel"><p class="explica">' +
    esc(await erroDe(r)) + "</p></div>"; return; }
  const d = await r.json();

  const versoes = [];
  for (let v = 1; v <= d.ultima; v += 1) versoes.push(v);
  const escolher = '<select id="al-desde">' + versoes.map((v) =>
    '<option value="' + v + '"' + (v === d.desde ? " selected" : "") +
    ">desde a versão " + v + "</option>").join("") + "</select>";

  destino.innerHTML = '<div class="painel" style="margin-top:16px"><h3>Alterações</h3>' +
    '<div class="linha-form">' + escolher +
    '<span class="rotulo">' + (d.mudancas.length
      ? plural(d.mudancas.length, "alteração", "alterações") + " no texto"
      : "nada mudou no texto") + "</span></div>" +
    (d.mudancas.length
      ? '<div class="al-lista">' + d.mudancas.map((m, i) =>
          '<div class="al-linha ' + esc(m.tipo) + '" data-mud="' + i + '">' +
          '<span class="rotulo">' + esc(m.tipo) + "</span><span>" +
          (m.tipo === "mudou"
            ? '<span class="al-saiu">' + esc(m.antes) + "</span><br>" +
              '<span class="comparar-depois">' + esc(m.depois) + "</span>"
            : m.tipo === "saiu"
              ? '<span class="al-saiu">' + esc(m.antes) + "</span>"
              : esc(m.depois)) +
          "</span>" +
          (m.tipo === "saiu"
            ? '<span class="rotulo">só no Histórico</span>'
            : '<button data-desfazer="' + i + '">Descartar esta</button>') +
          "</div>").join("") + "</div>" +
        '<p class="explica">"Descartar esta" volta só este parágrafo ao que ele era na ' +
        "versão escolhida. O resto do texto fica como está. Parágrafo que saiu inteiro " +
        "não volta por aqui — para isso é o Histórico, que traz a versão inteira.</p>"
      : '<p class="explica">O texto do editor é igual ao da versão ' + d.desde +
        ". Trocar <b> por <strong> não conta: a comparação é do texto, não da marcação.</p>") +
    '<div class="linha-form"><button id="al-fechar">Fechar</button></div></div>';

  $("al-fechar").onclick = () => { destino.innerHTML = ""; };
  $("al-desde").onchange = (e) => painelAlteracoes(Number(e.target.value));
  destino.querySelectorAll("[data-desfazer]").forEach((b) => {
    b.onclick = () => descartarAlteracao(d.mudancas[Number(b.dataset.desfazer)], b);
  });
}

/* Acha o parágrafo pelo texto que ele tem AGORA, e não por posição: entre
   abrir o painel e clicar em "Descartar", a pessoa pode ter escrito mais
   acima, e aí a terceira posição já não é o terceiro parágrafo. */
function descartarAlteracao(mudanca, botao) {
  const folha = folhaAberta();
  if (!folha || !mudanca) return;

  const alvoTexto = normalTexto(mudanca.depois);
  const achado = blocosDaFolha(folha).find((el) => normalTexto(el.textContent) === alvoTexto);

  if (!achado) {
    botao.textContent = "o parágrafo mudou de novo";
    botao.disabled = true;
    return;
  }

  if (mudanca.tipo === "entrou") achado.remove();
  else achado.textContent = mudanca.antes;

  marcarSujo();
  pedirPaginacao(true);
  botao.closest(".al-linha").classList.add("desfeita");
  botao.textContent = "descartada";
  botao.disabled = true;
}

function normalTexto(t) {
  return String(t || "").replace(/\s+/g, " ").trim();
}

/* ------------------------------------------------------------- o quadro

   Quadro de parcelas, de honorários, de bens — o contrato que traz um deles
   hoje sai do Word, porque aqui não havia como fazer. As células guardam texto
   puro: negrito dentro de célula de quadro não aparece em contrato, e o que
   importa é o texto chegar inteiro ao PDF e ao Word. */

/* Clicar num botão tira o cursor de dentro da folha, e um painel com campos
   tira de novo. Então o lugar onde a pessoa estava escrevendo é guardado
   enquanto ela ainda está lá — senão o quadro cai no começo do documento, ou
   não cai em lugar nenhum. */
function lembrarCursor() {
  const folha = folhaAberta();
  const sel = window.getSelection();
  if (!folha || !sel || !sel.rangeCount) return;
  if (folha.contains(sel.anchorNode)) escr.marca = sel.getRangeAt(0).cloneRange();
}

function voltarAoCursor() {
  const folha = folhaAberta();
  if (!folha) return false;
  folha.focus();
  if (!escr.marca || !folha.contains(escr.marca.startContainer)) return false;
  const sel = window.getSelection();
  sel.removeAllRanges();
  sel.addRange(escr.marca);
  return true;
}

function noDoCursor() {
  const folha = folhaAberta();
  if (!folha) return null;
  const sel = window.getSelection();
  let no = sel && sel.anchorNode && folha.contains(sel.anchorNode) ? sel.anchorNode : null;
  if (!no && escr.marca && folha.contains(escr.marca.startContainer)) {
    no = escr.marca.startContainer;
  }
  if (!no) return null;
  return no.nodeType === 1 ? no : no.parentElement;
}

function quadroDoCursor() {
  const no = noDoCursor();
  return no ? no.closest("table") : null;
}

function painelQuadro() {
  const destino = abaixoDoEditor();
  if (!destino) return;
  const dentro = quadroDoCursor();

  destino.innerHTML = '<div class="painel" style="margin-top:16px"><h3>Quadro</h3>' +
    '<p class="explica">Sai no PDF com fio fino e a primeira linha em negrito, e ' +
    "no DOCX como tabela de verdade — dá para continuar no Word.</p>" +
    '<div class="linha-form"><label class="pl-check">colunas ' +
    '<input type="number" id="qd-colunas" value="3" min="1" max="8"></label>' +
    '<label class="pl-check">linhas ' +
    '<input type="number" id="qd-linhas" value="3" min="1" max="40"></label>' +
    '<button class="primario" id="qd-inserir">Inserir quadro</button></div>' +
    (dentro
      ? '<div class="linha-form"><span class="rotulo">o cursor está num quadro</span>' +
        '<button id="qd-mais-linha">+ linha</button>' +
        '<button id="qd-mais-coluna">+ coluna</button>' +
        '<button class="perigo" id="qd-menos-linha">Apagar esta linha</button></div>'
      : '<p class="explica">Para mexer num quadro que já existe, ponha o cursor dentro ' +
        "dele e abra este painel de novo.</p>") +
    '<div class="linha-form"><button id="qd-fechar">Fechar</button></div></div>';

  $("qd-fechar").onclick = () => { destino.innerHTML = ""; };
  $("qd-inserir").onclick = inserirQuadro;
  if (dentro) {
    $("qd-mais-linha").onclick = () => mexerNoQuadro("linha");
    $("qd-mais-coluna").onclick = () => mexerNoQuadro("coluna");
    $("qd-menos-linha").onclick = () => mexerNoQuadro("tirar");
  }
}

function inserirQuadro() {
  const folha = folhaAberta();
  if (!folha) return;
  const colunas = Math.max(1, Math.min(8, Number($("qd-colunas").value) || 3));
  const linhas = Math.max(1, Math.min(40, Number($("qd-linhas").value) || 3));

  let html = "<table><tr>";
  for (let c = 0; c < colunas; c += 1) html += "<th>título</th>";
  html += "</tr>";
  for (let l = 1; l < linhas; l += 1) {
    html += "<tr>";
    for (let c = 0; c < colunas; c += 1) html += "<td><br></td>";
    html += "</tr>";
  }
  /* O parágrafo depois do quadro é o que dá para onde ir: sem ele, um quadro
     no fim do documento não tem linha abaixo e não há como continuar
     escrevendo. */
  html += "</table><p><br></p>";

  voltarAoCursor();
  document.execCommand("insertHTML", false, html);
  marcarSujo();
  pedirPaginacao();
  const destino = abaixoDoEditor();
  if (destino) destino.innerHTML = "";
}

function mexerNoQuadro(acao) {
  const quadro = quadroDoCursor();
  const no = noDoCursor();
  if (!quadro || !no) return;
  const linha = no.closest("tr");

  if (acao === "coluna") {
    Array.from(quadro.rows).forEach((tr, i) => {
      const celula = tr.insertCell(-1);
      if (i === 0 && tr.cells[0] && tr.cells[0].tagName === "TH") {
        const cabeca = document.createElement("th");
        cabeca.textContent = "título";
        tr.replaceChild(cabeca, celula);
      } else {
        celula.innerHTML = "<br>";
      }
    });
  } else if (acao === "linha" && linha) {
    const nova = quadro.insertRow(linha.rowIndex + 1);
    for (let c = 0; c < linha.cells.length; c += 1) nova.insertCell(-1).innerHTML = "<br>";
  } else if (acao === "tirar" && linha) {
    /* Um quadro sem nenhuma linha não é um quadro: apagar a última apaga o
       quadro inteiro, que é o que a pessoa quis dizer. */
    if (quadro.rows.length <= 1) quadro.remove();
    else quadro.deleteRow(linha.rowIndex);
  }

  marcarSujo();
  pedirPaginacao();
  painelQuadro();
}

/* ----------------------------------------------------- o formato da folha

   Fonte, corpo, recuo de primeira linha e entrelinhas. Fica por documento e
   não por escritório: uma petição e um contrato pedem recuos diferentes, e
   quem escreve os dois no mesmo dia não pode ter que trocar a configuração
   entre um e outro. */

const FORMATO_OPCOES = {
  fonte: { rotulo: "Fonte", itens: [
    ["serifada", "Times (serifada)"],
    ["sem-serifa", "Arial (sem serifa)"],
  ] },
  corpo: { rotulo: "Corpo", itens: [["11", "11 pt"], ["12", "12 pt"], ["13", "13 pt"]] },
  recuo_cm: { rotulo: "Recuo de primeira linha", itens: [
    ["0", "sem recuo"], ["1.25", "1,25 cm"], ["2", "2 cm"],
  ] },
  entrelinhas: { rotulo: "Entrelinhas", itens: [["1", "simples"], ["1.5", "1,5"], ["2", "duplo"]] },
};

function painelFormato() {
  const destino = $("ed-abaixo");
  if (!destino) return;
  const f = escr.doc.formato || {};

  const campo = (chave) => {
    const o = FORMATO_OPCOES[chave];
    const atual = String(f[chave] === undefined ? "" : f[chave]);
    return '<div class="campo-form"><label class="rotulo">' + o.rotulo + "</label>" +
      '<select data-formato="' + chave + '">' +
      o.itens.map(([v, t]) => '<option value="' + v + '"' +
        (Number(v) === Number(atual) || v === atual ? " selected" : "") + ">" + t + "</option>").join("") +
      "</select></div>";
  };

  destino.innerHTML = '<div class="painel" style="margin-top:16px"><h3>A folha</h3>' +
    '<p class="explica">Vale para este documento, no PDF e no DOCX. A4 e margem de ' +
    "2,5 cm não mudam: são as medidas da peça jurídica, e escolher outra coisa seria " +
    "só um jeito de errar.</p>" +
    '<div class="ed-formato">' + Object.keys(FORMATO_OPCOES).map(campo).join("") + "</div>" +
    '<p class="explica" id="ed-formato-nota" style="margin-top:10px"></p>' +
    '<div class="linha-form"><button id="ed-formato-fechar">Fechar</button></div></div>';

  destino.querySelectorAll("[data-formato]").forEach((s) => { s.onchange = gravarFormato; });
  $("ed-formato-fechar").onclick = () => { destino.innerHTML = ""; };
  destino.querySelector(".painel").scrollIntoView({ behavior: "smooth", block: "center" });
}

async function gravarFormato() {
  const nota = $("ed-formato-nota");
  const antes = escr.paginacao ? escr.paginacao.paginas : 0;
  const pedido = {};
  document.querySelectorAll("[data-formato]").forEach((s) => {
    pedido[s.dataset.formato] = s.dataset.formato === "fonte" ? s.value : Number(s.value);
  });

  if (nota) nota.textContent = "medindo…";
  const r = await fetch("/api/documentos/" + escr.doc.id + "/formato", {
    method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ formato: pedido, corpo: $("ed-folha").innerHTML }),
  });
  if (!r.ok) { if (nota) nota.textContent = await erroDe(r); return; }

  const d = await r.json();
  escr.doc.formato = d.formato;
  aplicarPaginacao(d);
  if (nota) {
    nota.textContent = antes && antes !== d.paginas
      ? "O documento passou de " + plural(antes, "página") + " para " +
        plural(d.paginas, "página") + " — medido no PDF."
      : plural(d.paginas, "página") + ", medido no PDF.";
  }
}

/* ------------------------------------------------ qualificação das partes */

async function inserirQualificacao() {
  const folha = folhaAberta();
  if (!folha) return;

  const d = await (await fetch("/api/cadastros")).json();
  if (!d.fichas.length) {
    avisoCert("nenhum cadastro ainda — a qualificação sai de lá");
    return;
  }

  const destino = abaixoDoEditor() || folha.parentElement;
  const caixa = document.createElement("div");
  caixa.className = "painel";
  caixa.style.marginTop = "16px";
  caixa.innerHTML = "<h3>Qualificar uma parte</h3>" +
    '<p class="explica">O parágrafo sai do cadastro. O que faltar vira lacuna ' +
    "entre colchetes — eu não invento estado civil nem endereço.</p>" +
    '<div class="chips">' + d.fichas.map((f) =>
      '<button class="chip" data-qual="' + f.id + '">' + esc(f.nome) + "</button>").join("") +
    '</div><div id="qual-previa"></div>';
  destino.innerHTML = "";
  destino.appendChild(caixa);
  caixa.scrollIntoView({ behavior: "smooth", block: "center" });

  caixa.querySelectorAll("[data-qual]").forEach((b) => {
    b.onclick = () => preverQualificacao(Number(b.dataset.qual), folha, caixa);
  });
}

async function preverQualificacao(id, folha, caixa) {
  const alvo = caixa.querySelector("#qual-previa");
  alvo.innerHTML = '<p class="nota">montando…</p>';

  const r = await fetch("/api/redacao/qualificacao?cadastro_id=" + id);
  if (!r.ok) { alvo.innerHTML = '<p class="explica">' + esc(await erroDe(r)) + "</p>"; return; }
  const q = await r.json();

  alvo.innerHTML = '<div class="ed-sugestao" style="margin-top:12px">' +
    '<span class="rotulo">como vai entrar</span><p>' + esc(q.texto) + "</p>" +
    (q.falta.length
      ? '<p class="explica">O cadastro de ' + esc(q.nome) + " não tem: " +
        q.falta.join(", ") + ". Fica como lacuna no texto — " +
        "completar em Cadastros agora é mais barato que caçar colchete depois.</p>"
      : '<p class="explica">O cadastro está completo.</p>') +
    '<div class="linha-form"><button class="primario" id="qual-inserir">Inserir no documento</button>' +
    (q.falta.length ? '<button id="qual-cadastro">Completar o cadastro</button>' : "") +
    "</div></div>";

  $("qual-inserir").onclick = () => {
    const bloco = document.createElement("p");
    bloco.textContent = q.texto;
    folha.appendChild(bloco);
    bloco.scrollIntoView({ behavior: "smooth", block: "center" });
    caixa.remove();
    salvarOndeEstiver();
  };
  const irCadastro = $("qual-cadastro");
  if (irCadastro) irCadastro.onclick = () => { marcarDestino("cadastros"); mostrarCadastros(); };
}

function salvarOndeEstiver() {
  if ($("dp-folha")) marcarDuplaSuja();
  else marcarSujo();
}


