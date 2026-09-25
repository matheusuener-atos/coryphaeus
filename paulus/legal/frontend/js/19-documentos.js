/* ------------------------------------------- escrita (C1, C2, C3) */
/*
   Documentos (docs/ui/03-telas-desktop.md, A6): as abas dos documentos
   abertos no topo, o seletor Editor · Planilha · Pre-visualizacao, duas
   barras de ferramentas (a de formatar e a juridica) e o painel de 400 px
   com a conversa sobre o documento. O editor guarda HTML porque e o que um
   campo editavel do navegador produz sem biblioteca nenhuma; o servidor
   transforma isso em blocos, e e dos blocos que saem o PDF e o DOCX - um so
   conteudo, dois formatos, sem divergir.
*/

const escr = {
  doc: null, versoes: [], sugestao: null, salvando: false, relogio: null,
  pl: null, aba: 0, celula: "A1", editando: null,
  visao: "editor",        // editor | planilha | previa
  abas: [],               // os documentos abertos, na ordem das abas
  escolhidos: new Set(),  // a selecao da lista (segurar, Shift, Ctrl)
  atual: null,            // id da aba ativa; null e a lista de documentos
  lista: [],              // /api/documentos
  foco: (() => { try { return !!localStorage.getItem("paulus.docs.foco"); } catch (err) { return false; } })(),
  conversas: {},          // a conversa do painel, por documento
  pendente: null, antes: null, ocupada: false, guardarAoSair: true,
  previa: null, filtro: null, notaFormula: "", ouvindo: false, regua: false,
  // A senha do PDF vive nesta tela e so nela: nao vai para o disco nem para
  // as preferencias. Fechar o programa esquece, que e o certo - senha
  // guardada junto do documento que ela protege nao protege nada.
  senhaPdf: "",
};

const GLIFO_DO_TIPO = { texto: ["docx", "W"], planilha: ["xlsx", "X"], pdf: ["pdf", "PDF"] };
const ROTULO_DA_VISAO = { editor: "Editor", planilha: "Planilha", previa: "Pré-visualização" };

/* ------------------------------------------------- lista de documentos */

async function mostrarEditor() { return mostrarDocumentos("editor"); }
async function mostrarPlanilha() { return mostrarDocumentos("planilha"); }

/* Quem chamava a lista antiga cai na tela nova sem aba aberta. */
async function listaDocumentos(tipo) {
  escr.atual = null;
  lembrarAbas();
  return mostrarDocumentos(tipo === "planilha" ? "planilha" : "editor");
}

async function abrirDocumento(id) {
  abrirAba({ id: id, titulo: tituloNaLista(id) || "Documento", tipo: "texto" });
  return mostrarDocumentos("editor");
}

async function abrirPlanilha(id) {
  abrirAba({ id: id, titulo: tituloNaLista(id) || "Planilha", tipo: "planilha" });
  return mostrarDocumentos("planilha");
}

async function mostrarPrevia(id) {
  abrirAba({ id: id, titulo: tituloNaLista(id) || "Documento", tipo: "texto" });
  return mostrarDocumentos("previa");
}

function tituloNaLista(id) {
  const x = escr.lista.find((d) => d.id === id);
  return x ? x.titulo : "";
}

/* As abas sobrevivem a fechar o programa: reabrir os mesmos documentos e o
   que a pessoa espera de um editor. */
function lembrarAbas() {
  try {
    localStorage.setItem("paulus.docs.abas", JSON.stringify({ abas: escr.abas, atual: escr.atual }));
  } catch (err) { /* sem armazenamento, sem memoria - a tela continua */ }
}

function recuperarAbas() {
  if (escr.abas.length || escr.abasLidas) return;
  escr.abasLidas = true;
  try {
    const d = JSON.parse(localStorage.getItem("paulus.docs.abas") || "null");
    if (d && Array.isArray(d.abas)) { escr.abas = d.abas; escr.atual = d.atual; }
  } catch (err) { escr.abas = []; }
}

function abaAtual() {
  return escr.abas.find((a) => a.id === escr.atual) || null;
}

function abrirAba(aba) {
  recuperarAbas();
  const existe = escr.abas.find((a) => a.id === aba.id);
  if (existe) Object.assign(existe, aba); else escr.abas.push(aba);
  escr.atual = aba.id;
  lembrarAbas();
}

function fecharAba(id) {
  const i = escr.abas.findIndex((a) => a.id === id);
  if (i < 0) return;
  escr.abas.splice(i, 1);
  if (escr.atual === id) {
    const proxima = escr.abas[i] || escr.abas[i - 1];
    escr.atual = proxima ? proxima.id : null;
  }
  lembrarAbas();
}

async function mostrarDocumentos(visao) {
  abrirTela("Editor de documentos", { cheia: true });
  marcarDestino("editor");
  recuperarAbas();
  if (visao) escr.visao = visao;

  const centro = $("centro");
  centro.innerHTML = '<div class="acervo sem-painel"><div class="acervo-principal">' + esqueleto("lista") + '</div></div>';
  try {
    escr.lista = (await (await fetch("/api/documentos")).json()).documentos;
    escr.abas.forEach((a) => { const t = tituloNaLista(a.id); if (t) a.titulo = t; });
    await carregarDocumentoAtual();
  } catch (err) {
    centro.innerHTML = '<div class="acervo sem-painel"><div class="acervo-principal"><p class="nota">não consegui abrir: ' +
      esc(String(err)) + "</p></div></div>";
    return;
  }
  desenharDocumentos();
  atualizarPostura();
}

/* O que a aba ativa precisa do servidor. Uma aba cujo documento foi apagado
   fecha sozinha em vez de mostrar erro. */
async function carregarDocumentoAtual() {
  const aba = abaAtual();
  if (!aba) { escr.atual = null; return; }

  if (aba.tipo === "pdf") return;

  if (aba.tipo === "planilha") {
    escr.visao = "planilha";
    const r = await fetch("/api/planilha/" + aba.id);
    if (!r.ok) { fecharAba(aba.id); return carregarDocumentoAtual(); }
    const pl = await r.json();
    if (!escr.pl || escr.pl.id !== pl.id) { escr.aba = 0; escr.celula = "A1"; escr.ancora = null; escr.filtro = null; escr.notaFormula = ""; }
    escr.pl = pl;
    aba.titulo = pl.titulo;
    return;
  }

  if (escr.visao === "planilha") escr.visao = "editor";
  const r = await fetch("/api/documentos/" + aba.id);
  if (!r.ok) { fecharAba(aba.id); return carregarDocumentoAtual(); }
  const doc = await r.json();
  if (!escr.doc || escr.doc.id !== doc.id) { escr.sugestao = null; escr.pendente = null; escr.antes = null; escr.notas = null; escr.paginacao = null; }
  escr.doc = doc;
  aba.titulo = doc.titulo;

  if (escr.visao === "previa") {
    const c = await fetch("/api/documentos/" + aba.id + "/conferir");
    if (!c.ok) throw new Error(await erroDe(c));
    const dados = await c.json();
    const antes = escr.previa && escr.previa.id === aba.id ? escr.previa : { pagina: 1, duas: false, cheia: false };
    escr.previa = { id: aba.id, pagina: Math.min(antes.pagina || 1, dados.paginas || 1), duas: antes.duas, cheia: antes.cheia, dados: dados };
    try { escr.versoes = (await (await fetch("/api/documentos/" + aba.id + "/versoes")).json()).versoes; } catch (err) { escr.versoes = []; }
  }
}

/* ---------------------------------------------------------- a tela */

function desenharDocumentos() {
  const aba = abaAtual();
  cabecalhoDocumentos(aba);

  let barras = "", principal, painel;
  if (!aba) {
    principal = listaDeDocumentos();
    painel = painelDaLista();
  } else if (aba.tipo === "pdf") {
    barras = barrasDoPdf(aba);
    principal = visorDoPdf(aba);
    painel = painelDoPdf(aba);
  } else if (escr.visao === "previa") {
    barras = barrasDaPrevia();
    principal = folhaDaPrevia();
    painel = painelDaPrevia();
  } else if (aba.tipo === "planilha") {
    barras = barrasDaPlanilha();
    principal = cartaoDaPlanilha();
    painel = painelDaPlanilha();
  } else {
    barras = barrasDoEditor();
    principal = cartaoDoEditor();
    painel = painelDoEditor();
  }

  const cheia = escr.visao === "previa" && escr.previa && escr.previa.cheia && aba && aba.tipo === "texto";
  const classe = "acervo docs-corpo" + (cheia ? " sem-painel" : (escr.foco && aba ? " painel-oculto" : ""));
  $("centro").innerHTML = '<div class="docs" id="docs">' + abasDosDocumentos() + barras +
    '<div class="' + classe + '" id="docs-corpo"><div class="acervo-principal">' + principal + "</div>" +
    (cheia ? "" : painel) + "</div></div>";
  ligarDocumentos(aba);
}

function desenharEditor() { desenharDocumentos(); }

function cabecalhoDocumentos(aba) {
  const titulo = $("conversa-titulo");
  const meta = $("conversa-meta");
  titulo.textContent = aba ? aba.titulo : "Editor de documentos";
  titulo.title = aba && aba.tipo !== "pdf" ? "Clique duas vezes para renomear" : "";
  titulo.ondblclick = aba && aba.tipo !== "pdf" ? () => renomearDocumento(aba) : null;

  if (!aba) {
    const textos = escr.lista.filter((d) => d.tipo !== "planilha").length;
    meta.textContent = plural(textos, "documento") + " · " + plural(escr.lista.length - textos, "planilha");
  } else if (aba.tipo === "pdf") {
    meta.textContent = "só leitura · " + (aba.paginas ? plural(aba.paginas, "página") : "PDF do Acervo");
  } else if (escr.visao === "previa" && escr.previa) {
    const d = escr.previa.dados;
    meta.innerHTML = "Versão " + d.versao + " · " + plural(d.paginas, "página") + " · A4 · " +
      '<span class="docs-sinc' + (d.impedem ? " atencao" : "") + '"><i></i>' +
      (d.impedem ? plural(d.impedem, "ponto") + " a resolver" : "pronto para sair") + "</span>";
  } else if (aba.tipo === "planilha") {
    const p = escr.pl;
    const res = p.resumos[escr.aba] || {};
    meta.innerHTML = '<span id="pl-estado">v' + p.versao + " · " + plural(p.abas.length, "aba") + "</span> · " +
      '<span class="docs-sinc' + (res.erros ? " atencao" : "") + '"><i></i>' +
      (res.erros ? plural(res.erros, "erro") + " de cálculo" : "cálculos em dia") + "</span>";
  } else {
    const d = escr.doc;
    const c = d.contagem || { palavras: 0 };
    meta.innerHTML = '<span id="ed-estado">v' + d.versao + " · " + plural(c.palavras, "palavra") + "</span> · " +
      '<span id="ed-paginas">' + plural(d.paginacao ? d.paginacao.paginas : 1, "página") + "</span> · " +
      '<span class="docs-sinc"><i></i>salvando sozinho</span>';
  }

  const visoes = (aba && aba.tipo === "pdf") ? "" : escr.visao;
  const botao = (v) => {
    const classe = v === visoes ? "ativa" : "";
    return '<button class="' + classe + '" data-docs-visao="' + v + '">' + ROTULO_DA_VISAO[v] + "</button>";
  };
  let acoes;
  if (!aba) {
    acoes = '<div class="com-menu"><button class="primario com-icone" id="doc-novo">' + ic("add", 16) + "Novo" + ic("expand_more", 16) + "</button></div>";
  } else if (aba.tipo === "pdf") {
    acoes = '<button class="com-icone" id="doc-editar-copia">' + ic("edit", 16) + "Abrir para editar</button>";
  } else if (escr.visao === "previa") {
    acoes = '<button class="com-icone" id="pv-comparar">' + ic("difference", 16) + "Comparar versões</button>" +
      '<button class="primario com-icone" id="pv-assinar">' + ic("draw", 16) + "Assinar</button>";
  } else if (aba.tipo === "planilha") {
    acoes = '<button class="com-icone" id="pl-importar-b">' + ic("upload", 16) + "Importar CSV</button>" +
      '<button class="com-icone" id="pl-xlsx">' + ic("download", 16) + "Baixar XLSX</button>" +
      '<button class="primario com-icone" id="pl-guardar">' + ic("inventory_2", 16) + "Salvar no Acervo</button>" +
      '<input type="file" id="pl-arquivo" accept=".csv,.xlsx,.txt" hidden>';
  } else {
    acoes = '<button class="com-icone" id="ed-versoes">' + ic("history", 16) + "Histórico</button>" +
      '<button class="com-icone" id="ed-imprimir">' + ic("print", 16) + "Imprimir</button>" +
      '<button class="primario com-icone" id="ed-pdf">' + ic("picture_as_pdf", 16) + "Exportar PDF</button>";
  }
  $("acoes-tela").innerHTML = '<div class="visoes">' + botao("editor") + botao("planilha") + "</div>" +
    '<div class="visoes">' + botao("previa") + "</div>" + acoes;
  $("nav-tela").innerHTML = "";
}

async function renomearDocumento(aba) {
  const nome = await perguntar({ titulo: "Renomear documento", contexto: "Editor", campo: { rotulo: "Nome", valor: aba.titulo, icone: "description" }, confirmar: "Renomear" });
  if (nome === null || !nome.trim()) return;
  aba.titulo = nome.trim();
  const campo = $("ed-titulo");
  if (campo) { campo.value = aba.titulo; marcarSujo(); }
  else if (escr.pl && escr.pl.id === aba.id) {
    escr.pl.titulo = aba.titulo;
    fetch("/api/documentos/" + aba.id, {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ corpo: corpoDaPlanilha(), titulo: aba.titulo }),
    });
  }
  lembrarAbas();
  $("conversa-titulo").textContent = aba.titulo;
  const botao = document.querySelector('[data-docs-aba="' + aba.id + '"] .docs-aba-nome');
  if (botao) botao.textContent = aba.titulo;
}

function glifoDaAba(aba) {
  const g = GLIFO_DO_TIPO[aba.tipo] || GLIFO_DO_TIPO.texto;
  const classe = "glifo " + g[0];
  return '<span class="' + classe + '">' + g[1] + "</span>";
}

function abasDosDocumentos() {
  const abas = escr.abas.map((a) => {
    const classe = "docs-aba" + (a.id === escr.atual ? " ativa" : "");
    return '<button class="' + classe + '" data-docs-aba="' + esc(String(a.id)) + '" title="' + esc(a.titulo) + '">' +
      glifoDaAba(a) + '<span class="docs-aba-nome">' + esc(a.titulo) + "</span>" +
      (a.tipo === "pdf" ? "<small>só leitura</small>" : "") +
      '<span class="ic ic-16 docs-fechar" data-docs-fechar="' + esc(String(a.id)) + '" title="Fechar">close</span></button>';
  }).join("");
  const classe = "docs-aba-mais" + (escr.atual === null ? " ativa" : "");
  return '<div class="docs-abas">' + abas +
    '<button class="' + classe + '" data-docs-lista="1" title="Abrir ou criar um documento">' + ic("add", 18) + "</button>" +
    (escr.atual !== null ? botaoDoFoco() : "") + "</div>";
}

/* ----------------------------------------------------- a lista */

function listaDeDocumentos() {
  const filtro = escr.visao === "planilha" ? "planilha" : (escr.visao === "editor" ? "texto" : "");
  const itens = escr.lista.filter((d) => !filtro || d.tipo === filtro);
  const linhas = itens.map((d) => {
    const g = GLIFO_DO_TIPO[d.tipo === "planilha" ? "planilha" : "texto"];
    const classe = "glifo " + g[0];
    const classeLinha = "tabela-linha colunas-docs" + (escr.escolhidos.has(String(d.id)) ? " escolhida" : "");
    return '<div class="' + classeLinha + '" data-doc-abrir="' + d.id + '" data-sel="' + d.id + '" data-doc-tipo="' + esc(d.tipo) + '">' +
      '<span class="nome-doc"><span class="' + classe + '">' + g[1] + '</span><span class="duas-linhas"><b>' + esc(d.titulo) + "</b>" +
      "<small>" + (d.tipo === "planilha" ? "planilha" : "documento de texto") + "</small></span></span>" +
      '<span class="quando-doc">' + esc(d.cadastro_nome || "—") + "</span>" +
      '<span class="quando-doc">v' + d.versao + "</span>" +
      '<span class="quando-doc">' + esc(quandoCurto(d.atualizado_em)) + "</span>" +
      '<button class="mais-linha" data-doc-mais="' + d.id + '" title="Mais">' + ic("more_horiz", 18) + "</button></div>";
  }).join("");
  return '<div class="tabela-cartao"><div class="tabela-barra">' +
    (escr.escolhidos.size
      ? barraDeSelecao(escr.escolhidos.size, false, '<button class="botao-icone perigo" data-doc-sel-apagar="1" title="Apagar" aria-label="Apagar">' + ic("delete", 18) + "</button>", "data-doc-sel-limpar")
      : '<span class="selecao">' + plural(itens.length, "arquivo") + "</span>") +
    '<div class="direita"><div class="visoes">' + [["texto", "Textos"], ["planilha", "Planilhas"]].map(([t, r]) => {
      const classe = t === filtro ? "ativa" : "";
      return '<button class="' + classe + '" data-doc-filtro="' + t + '">' + r + "</button>";
    }).join("") + "</div></div></div>" +
    '<div class="tabela-cabecalho colunas-docs"><span>Documento</span><span>Cliente</span><span>Versão</span><span>Atualizado</span><span></span></div>' +
    '<div class="tabela-corpo">' + (linhas || '<div class="ag-vazio"><h4>' +
      (filtro === "planilha" ? "Nenhuma planilha ainda" : "Nenhum documento ainda") + "</h4><p>" +
      (filtro === "planilha"
        ? "Fórmulas em português, do jeito que você escreve no Excel: ponto e vírgula separa argumento e vírgula é decimal."
        : "O ganho aqui não é o editor — o Word já existe. É o assistente escrevendo dentro do documento, com os seus cadastros e o Acervo do lado, e a conferência antes de o arquivo sair.") +
      "</p></div>") + "</div>" +
    '<div class="tabela-rodape"><span>gravados na sua máquina</span></div></div>';
}

function painelDaLista() {
  return '<aside class="acervo-painel" id="docs-painel"><div class="rolagem docs-painel">' + regioesDeFerramenta() +
    '<div class="painel-cabeca"><span class="titulo-painel"><h3>Comece por aqui</h3><span class="meta">criar, abrir ou trazer do Acervo</span></span></div>' +
    '<div class="painel-acoes"><button class="primario" data-doc-criar="texto">' + ic("description", 16) + "Novo documento</button>" +
    '<button data-doc-criar="planilha">' + ic("table", 16) + "Nova planilha</button>" +
    '<button data-doc-importar="1">' + ic("inventory_2", 16) + "Abrir do Acervo</button></div>" +
    '<div class="painel-bloco"><div class="painel-bloco-cabeca"><span>O que acontece aqui</span></div>' +
    "<p>O assistente escreve dentro do documento e marca o que mexeu; você decide se fica. Cláusulas do escritório, qualificação das partes e os códigos instalados entram sem sair da tela.</p>" +
    "<p>Um arquivo do Acervo abre como cópia editável: o original que já foi assinado ou enviado não é tocado. PDF abre só para leitura.</p></div>" +
    "</div></aside>";
}

/* Foco no documento: o painel sai de cena inteiro e a folha fica sozinha no
   centro. Volta pelo mesmo botao, ou sozinho quando alguma ferramenta
   escreve nele (Folha, Clausulas, a resposta do assistente) - resposta num
   painel escondido seria resposta perdida. */
function botaoDoFoco() {
  const rotulo = escr.foco ? "Mostrar o painel" : "Ocultar o painel";
  return '<button class="docs-foco' + (escr.foco ? " on" : "") + '" data-docs-foco="1" title="' + rotulo + '" aria-pressed="' + escr.foco + '">' +
    ic("view_sidebar", 18) + '<span>' + (escr.foco ? "Painel" : "Foco") + "</span></button>";
}

function alternarFoco(foco) {
  escr.foco = foco === undefined ? !escr.foco : foco;
  try { localStorage.setItem("paulus.docs.foco", escr.foco ? "1" : ""); } catch (err) { /* so conveniencia */ }
  const corpo = $("docs-corpo");
  if (corpo) corpo.classList.toggle("painel-oculto", escr.foco);
  const b = document.querySelector("[data-docs-foco]");
  if (b) b.outerHTML = botaoDoFoco();
  const novo = document.querySelector("[data-docs-foco]");
  if (novo) novo.onclick = () => alternarFoco();
  /* A folha muda de largura so depois da transicao da coluna: medir antes
     vestiria a letra na escala errada. */
  setTimeout(revestirFolha, animacoesLigadas() ? 280 : 0);
}

/* Qualquer coisa que entre no painel escondido traz o painel de volta. */
function vigiarPainelEscondido() {
  const painel = $("docs-painel");
  if (!painel) return;
  const vigia = new MutationObserver(() => { if (escr.foco && document.body.contains(painel)) alternarFoco(false); });
  painel.querySelectorAll(".docs-ferramenta, .docs-conversa").forEach((el) => vigia.observe(el, { childList: true }));
}

/* Os paineis de ferramenta que o motor ja tinha (historico, clausulas, quadro,
   folha, alteracoes, conferencia, notas, codigos) desenham aqui, no alto do
   painel, cada um no seu lugar de sempre. */
function regioesDeFerramenta() {
  return '<div class="docs-ferramenta" id="ed-abaixo"></div><div class="docs-ferramenta" id="pv-abaixo"></div><div class="docs-ferramenta" id="pl-abaixo"></div>';
}

/* --------------------------------------------------- C1: editor de texto */

function barrasDoEditor() {
  const f = escr.doc.formato || {};
  const icone = (cmd, nome, titulo) => '<button data-cmd="' + cmd + '" title="' + titulo + '">' + ic(nome, 18) + "</button>";
  return '<div class="docs-barra">' +
    '<select class="docs-sel" id="ed-bloco" title="Estilo do parágrafo"><option value="p">Corpo do texto</option><option value="h1">Título 1</option><option value="h2">Título 2</option><option value="h3">Título 3</option></select>' +
    '<select class="docs-sel" id="ed-fonte" title="Fonte"><option value="serifada"' + (f.fonte === "sem-serifa" ? "" : " selected") + '>Times</option><option value="sem-serifa"' + (f.fonte === "sem-serifa" ? " selected" : "") + ">Arial</option></select>" +
    '<select class="docs-sel curta" id="ed-corpo" title="Corpo">' + [11, 12, 13].map((n) => '<option value="' + n + '"' + (Number(f.corpo || 12) === n ? " selected" : "") + ">" + n + "</option>").join("") + "</select>" +
    '<span class="divisa-v"></span>' +
    icone("undo", "undo", "Desfazer") + icone("redo", "redo", "Refazer") +
    '<span class="divisa-v"></span>' +
    icone("bold", "format_bold", "Negrito") + icone("italic", "format_italic", "Itálico") +
    icone("underline", "format_underlined", "Sublinhado") + icone("strikeThrough", "strikethrough_s", "Tachado") +
    '<span class="divisa-v"></span>' +
    icone("justifyFull", "format_align_justify", "Justificar") + icone("insertUnorderedList", "format_list_bulleted", "Lista") +
    icone("insertOrderedList", "format_list_numbered", "Numeração") + icone("indent", "format_indent_increase", "Recuar") +
    '<button id="ed-quadro" title="Quadro">' + ic("table", 18) + "</button>" +
    '<span class="divisa-v"></span>' +
    '<button class="com-texto" id="ed-alteracoes">' + ic("difference", 16) + "Controlar alterações</button>" +
    '<button class="com-texto" id="ed-comentar" title="Comentar o trecho selecionado">' + ic("rate_review", 16) + "Comentar</button>" +
    "</div>" +
    '<div class="docs-barra juridica">' +
    '<span class="docs-rotulo">Códigos</span>' +
    ["cc", "cpc", "cp", "clt"].map((c) => '<button class="docs-chip" data-codigo="' + c + '">' + c.toUpperCase() + "</button>").join("") +
    '<span class="divisa-v"></span>' +
    '<button class="com-texto" id="ed-codigos">' + ic("format_quote", 16) + "Inserir citação</button>" +
    '<button class="com-texto adiante" data-adiante="jurisprudência">' + ic("gavel", 16) + "Jurisprudência</button>" +
    '<button class="com-texto adiante" data-adiante="súmulas">' + ic("menu_book", 16) + "Súmulas</button>" +
    '<button class="com-texto" id="ed-clausulas">' + ic("library_books", 16) + "Cláusulas</button>" +
    '<span class="divisa-v"></span>' +
    '<button class="com-texto" id="ed-numerar">' + ic("format_list_numbered", 16) + "Numerar</button>" +
    '<button class="com-texto" id="ed-refs">' + ic("link", 16) + "Ref. cruzada</button>" +
    '<button class="com-texto" id="ed-conferir">' + ic("event_upcoming", 16) + "Conferir prazos</button>" +
    '<button class="com-texto" id="ed-qualificar">' + ic("groups", 16) + "Partes</button>" +
    "</div>";
}

function cartaoDoEditor() {
  const d = escr.doc;
  return '<div class="docs-cartao">' +
    '<div class="docs-status"><span id="ed-regua-fim">A4 · margens 2,5 cm</span><span class="cresce"></span>' +
    '<button class="docs-ligacao" id="ed-regua-botao">' + (escr.regua ? "Esconder a régua" : "Régua") + "</button>" +
    '<span class="docs-divisa-fina"></span><button class="docs-ligacao" id="ed-formato">Formato</button>' +
    '<span class="docs-divisa-fina"></span><button class="docs-ligacao docs-modo-folha' + (escr.modoFolha ? " on" : "") + '" id="ed-modo-folha">' + ic("edit_document", 16) + (escr.modoFolha ? "Concluir a folha" : "Editar a folha") + "</button></div>" +
    '<div class="docs-papel-area"><div class="docs-papel">' +
    '<div class="ed-regua" id="ed-regua"' + (escr.regua ? "" : " hidden") + '><div class="ed-regua-barra"><span class="ed-regua-margem" style="width:11.9%"></span>' +
    '<span class="ed-regua-texto"></span><span class="ed-regua-margem" style="width:11.9%"></span></div>' +
    '<div class="ed-regua-legenda"><span>a folha, na escala do PDF</span><span>2,5 cm de cada lado</span></div></div>' +
    '<div class="ed-papel paginado' + (escr.modoFolha ? " modo-folha" : "") + '" id="ed-papel"><div class="ed-folhas" id="ed-folhas" aria-hidden="true"></div>' +
    '<div class="ed-folha" id="ed-folha" contenteditable="' + (escr.modoFolha ? "false" : "true") + '">' + (d.corpo || "<p><br></p>") + "</div>" +
    '<div class="ed-margens" id="ed-margens"></div>' +
    '<div class="ed-quebras" id="ed-quebras"></div><div class="ed-notas" id="ed-notas"></div><style id="ed-saltos"></style></div>' +
    '<input type="text" id="ed-titulo" value="' + esc(d.titulo) + '" hidden><span id="ed-paginas-nota" hidden></span>' +
    "</div></div></div>";
}

function painelDoEditor() {
  return '<aside class="acervo-painel" id="docs-painel"><div class="rolagem docs-painel">' + regioesDeFerramenta() +
    '<div class="docs-painel-cabeca">' + coroa(18) + '<span class="cresce">Pedir aqui</span><span id="ed-sobre">sobre o documento</span></div>' +
    '<div class="docs-conversa" id="ed-fala">' + falasDoDocumento(conversaAtual()) + "</div>" +
    '<div class="painel-bloco"><div class="painel-bloco-cabeca"><span>O que eu posso fazer</span></div><div class="docs-acoes-lista">' +
    '<button data-ed-fazer="Revisar a redação deste trecho"><span>Revisar a redação deste trecho</span>' + ic("chevron_right", 16) + "</button>" +
    '<button data-ed-fazer="Padronizar este documento com as cláusulas do escritório"><span>Padronizar com o modelo do escritório</span>' + ic("chevron_right", 16) + "</button>" +
    '<button data-ed-conferir="1"><span>Conferir prazos e datas do documento</span>' + ic("chevron_right", 16) + "</button>" +
    '<button data-ed-timbre="1"><span>Montar o papel timbrado e o rodapé</span>' + ic("chevron_right", 16) + "</button></div></div>" +
    '<div class="docs-chips"><button class="adiante" data-adiante="jurisprudência">Buscar jurisprudência</button>' +
    '<button data-ed-citar="1">Citar artigo</button>' +
    '<button data-ed-fazer="Reescrever este trecho com mais clareza">Reescrever trecho</button>' +
    '<button data-ed-fazer="Deixar mais formal">Deixar mais formal</button></div>' +
    '<div class="docs-pedido"><div class="docs-pedido-linha"><input type="text" id="ed-pedido" placeholder="Peça uma alteração ou uma pesquisa…">' +
    '<button class="enviar" id="ed-pedir" aria-label="Enviar">' + ic("arrow_forward", 18) + "</button></div>" +
    "<small>Busca nas bases locais; nada é consultado na internet sem você pedir.</small></div>" +
    "</div></aside>";
}

function conversaAtual() {
  const chave = String(escr.atual);
  if (!escr.conversas[chave]) escr.conversas[chave] = [];
  return escr.conversas[chave];
}

/* A conversa do painel: a pessoa a direita, a resposta a esquerda com os
   botoes de acao que ela trouxer. */
function falasDoDocumento(lista) {
  if (!lista.length) {
    return '<p class="docs-explica">' + (abaAtual() && abaAtual().tipo === "planilha"
      ? "Peça o cálculo em português. Eu escrevo a fórmula na barra fx, você confere e mantém — quem calcula é a planilha, não o modelo."
      : "Peça uma mudança ou uma pesquisa. Eu escrevo no documento e marco o que mexi — você decide se fica.") + "</p>";
  }
  return lista.map((m, i) => {
    if (m.autor === "pessoa") return '<div class="docs-bolha">' + esc(m.texto) + "</div>";
    return '<div class="docs-resposta"><p>' + m.html + "</p>" +
      (m.trecho ? '<blockquote class="docs-trecho">' + esc(m.trecho) + "</blockquote>" : "") +
      (m.acoes && m.acoes.length
        ? '<div class="docs-resposta-acoes">' + m.acoes.map((a, j) => {
            const classe = a.primario ? "primario" : "";
            return '<button class="' + classe + '" data-fala-acao="' + i + ":" + j + '">' + (a.icone ? ic(a.icone, 16) : "") + esc(a.rotulo) + "</button>";
          }).join("") + "</div>"
        : "") + "</div>";
  }).join("") + (escr.ocupada ? '<p class="nota" id="docs-pensando">escrevendo… isso leva cerca de um minuto nesta máquina</p>' : "");
}

function ligarFalas(caixa, lista) {
  caixa.querySelectorAll("[data-fala-acao]").forEach((b) => {
    b.onclick = () => {
      const [i, j] = b.dataset.falaAcao.split(":").map(Number);
      const a = lista[i] && lista[i].acoes && lista[i].acoes[j];
      if (a) a.acao(b);
    };
  });
  caixa.scrollTop = caixa.scrollHeight;
}

function redesenharFalas(id) {
  const caixa = $(id);
  if (!caixa) return;
  const lista = conversaAtual();
  caixa.innerHTML = falasDoDocumento(lista);
  ligarFalas(caixa, lista);
}

/* --------------------------------------------------------- ligacoes */

function ligarDocumentos(aba) {
  const raiz = $("docs");
  raiz.querySelectorAll("[data-docs-aba]").forEach((b) => {
    b.onclick = (e) => {
      if (e.target.closest("[data-docs-fechar]")) return;
      const id = idDaAba(b.dataset.docsAba);
      if (id === escr.atual) return;
      trocarDeAba(id);
    };
  });
  raiz.querySelectorAll("[data-docs-fechar]").forEach((x) => {
    x.onclick = (e) => { e.stopPropagation(); fecharDocumento(idDaAba(x.dataset.docsFechar)); };
  });
  const mais = raiz.querySelector("[data-docs-lista]");
  if (mais) mais.onclick = () => { escr.atual = null; lembrarAbas(); mostrarDocumentos(); };
  const foco = raiz.querySelector("[data-docs-foco]");
  if (foco) foco.onclick = () => alternarFoco();
  if (aba) vigiarPainelEscondido();
  raiz.querySelectorAll("[data-adiante]").forEach((b) => {
    b.onclick = () => avisoCert("a base de " + b.dataset.adiante + " ainda não está instalada nesta máquina — por enquanto só os códigos");
  });

  $("acoes-tela").querySelectorAll("[data-docs-visao]").forEach((b) => { b.onclick = () => trocarDeVisao(b.dataset.docsVisao); });

  if (!aba) return ligarLista();
  if (aba.tipo === "pdf") return ligarPdf(aba);
  if (escr.visao === "previa") return ligarPrevia();
  if (aba.tipo === "planilha") return ligarPlanilha();
  ligarEditor();
}

function idDaAba(texto) {
  return /^\d+$/.test(texto) ? Number(texto) : texto;
}

async function trocarDeAba(id) {
  const folha = $("ed-folha");
  if (folha && escr.doc) await gravarDocumento();
  const aba = escr.abas.find((a) => a.id === id);
  if (!aba) return;
  escr.atual = id;
  if (aba.tipo === "planilha") escr.visao = "planilha";
  else if (aba.tipo === "texto" && escr.visao === "planilha") escr.visao = "editor";
  lembrarAbas();
  mostrarDocumentos();
}

async function fecharDocumento(id) {
  const aba = escr.abas.find((a) => a.id === id);
  if (!aba) return;
  if (id === escr.atual) {
    if ($("ed-folha") && escr.doc) await gravarDocumento();
    if (escr.visao === "previa" && escr.guardarAoSair && aba.tipo === "texto") await guardarNaBiblioteca(id);
  }
  fecharAba(id);
  mostrarDocumentos();
}

/* O seletor: Editor leva a ultima aba de texto, Planilha a ultima de
   planilha; sem aba do tipo, a lista ja filtrada. Pre-visualizacao e do
   documento de texto aberto. */
function trocarDeVisao(visao) {
  const aba = abaAtual();
  if (visao === "previa") {
    if (!aba || aba.tipo !== "texto") { avisoCert("a pré-visualização é do documento de texto — abra um para ver o PDF"); return; }
    escr.visao = "previa";
    return mostrarDocumentos();
  }
  const tipo = visao === "planilha" ? "planilha" : "texto";
  if (aba && aba.tipo === tipo) { escr.visao = visao; return mostrarDocumentos(); }
  const ultima = escr.abas.slice().reverse().find((a) => a.tipo === tipo);
  escr.atual = ultima ? ultima.id : null;
  escr.visao = visao;
  lembrarAbas();
  mostrarDocumentos();
}

function apagarDocumentosEmLote(ids) {
  return apagarEmLote(ids, (id) => "/api/documentos/" + id, {
    rotulo: "documento", contexto: "Editor", texto: "O histórico de versões e os comentários vão junto.",
    depois: () => { escr.escolhidos.clear(); ids.forEach((id) => fecharAba(Number(id))); mostrarDocumentos(); },
  });
}

function ligarLista() {
  const raiz = $("docs");
  ligarSelecao(raiz.querySelector(".tabela-corpo"), {
    linhas: ".tabela-linha[data-sel]", escolhidos: escr.escolhidos, aoMudar: desenharDocumentos, apagar: (ids) => apagarDocumentosEmLote(ids),
  });
  const selLimpar = raiz.querySelector("[data-doc-sel-limpar]");
  if (selLimpar) selLimpar.onclick = (e) => { e.stopPropagation(); escr.escolhidos.clear(); desenharDocumentos(); };
  const selApagar = raiz.querySelector("[data-doc-sel-apagar]");
  if (selApagar) selApagar.onclick = (e) => { e.stopPropagation(); apagarDocumentosEmLote([...escr.escolhidos]); };
  raiz.querySelectorAll("[data-doc-abrir]").forEach((l) => {
    l.onclick = (e) => {
      if (e.target.closest("[data-doc-mais]")) return;
      const id = Number(l.dataset.docAbrir);
      l.dataset.docTipo === "planilha" ? abrirPlanilha(id) : abrirDocumento(id);
    };
  });
  raiz.querySelectorAll("[data-doc-mais]").forEach((b) => {
    b.onclick = (e) => {
      e.stopPropagation();
      const id = Number(b.dataset.docMais);
      const d = escr.lista.find((x) => x.id === id);
      if (!d) return;
      const itens = [{ icone: "edit", rotulo: "Abrir", acao: () => (d.tipo === "planilha" ? abrirPlanilha(id) : abrirDocumento(id)) }];
      if (d.tipo !== "planilha") {
        itens.push({ icone: "forum", rotulo: "Abrir com a conversa", acao: () => mostrarDupla(id) });
        itens.push({ icone: "picture_as_pdf", rotulo: "Pré-visualizar", acao: () => mostrarPrevia(id) });
      }
      itens.push("-", { icone: "delete", rotulo: "Apagar", perigo: true, acao: () => apagarDocumento(d) });
      menuNaLinha(b, itens);
    };
  });
  raiz.querySelectorAll("[data-doc-filtro]").forEach((b) => {
    b.onclick = () => { escr.visao = b.dataset.docFiltro === "planilha" ? "planilha" : "editor"; desenharDocumentos(); };
  });
  raiz.querySelectorAll("[data-doc-criar]").forEach((b) => { b.onclick = () => criarDocumento(b.dataset.docCriar); });
  const importar = raiz.querySelector("[data-doc-importar]");
  if (importar) importar.onclick = escolherDoAcervo;
  const novo = $("doc-novo");
  if (novo) novo.onclick = (e) => {
    e.stopPropagation();
    menuNaLinha(novo, [
      { icone: "description", rotulo: "Documento de texto", acao: () => criarDocumento("texto") },
      { icone: "table", rotulo: "Planilha", acao: () => criarDocumento("planilha") },
      "-",
      { icone: "inventory_2", rotulo: "Abrir do Acervo", acao: escolherDoAcervo },
    ]);
  };
}

async function criarDocumento(tipo) {
  const ehTexto = tipo !== "planilha";
  const titulo = await perguntar({ titulo: ehTexto ? "Novo documento" : "Nova planilha", contexto: "Editor", campo: { rotulo: "Nome", valor: ehTexto ? "Documento sem título" : "Planilha sem título", icone: ehTexto ? "description" : "table" }, confirmar: "Criar" });
  if (titulo === null) return;
  const r = await fetch("/api/documentos", {
    method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ titulo: titulo.trim() || (ehTexto ? "Documento sem título" : "Planilha sem título"), tipo: ehTexto ? "texto" : "planilha" }),
  });
  if (!r.ok) { avisoCert(await erroDe(r)); return; }
  const novo = await r.json();
  abrirAba({ id: novo.id, titulo: novo.titulo, tipo: ehTexto ? "texto" : "planilha" });
  mostrarDocumentos(ehTexto ? "editor" : "planilha");
}

async function apagarDocumento(d) {
  if (!(await confirmar({ titulo: "Apagar este documento?", contexto: "Editor › " + d.titulo, texto: "Todo o histórico de versões e os comentários vão junto. " + LIXEIRA_TEXTO, confirmar: "Apagar", perigo: true }))) return;
  const r = await fetch("/api/documentos/" + d.id, { method: "DELETE" });
  fecharAba(d.id);
  mostrarDocumentos();
  avisarLixeira(r, () => mostrarDocumentos());
}

/* Do Acervo, num pop-up proprio - como o de anexar -, e nao mais na
   coluna. PDF abre so para ler; o resto vira uma copia editavel, e o
   arquivo original nao e tocado. Clique escolhe; clique duplo abre. */
const aa = { docs: null, termo: "", escolhido: -1 };

async function escolherDoAcervo() {
  aa.docs = null;
  aa.termo = "";
  aa.escolhido = -1;
  const escolha = dialogo({
    titulo: "Abrir do Acervo", contexto: "Editor de documentos", classe: "dialogo-anexar", confirmar: "Abrir",
    html: '<div class="anx">' +
      '<div class="anx-topo"><span class="aa-dica">PDF abre só para ler; Word e texto viram uma cópia editável — o original fica como está.</span>' +
      '<label class="lc-busca anx-busca">' + ic("search", 15) + '<input type="text" id="aa-busca" placeholder="Buscar no acervo…" autocomplete="off"></label></div>' +
      '<div class="anx-lista" id="aa-lista"><p class="anx-vazio">lendo o acervo…</p></div>' +
      '<div class="anx-rodape"><span id="aa-conta"></span></div></div>',
  });
  $("aa-busca").oninput = (e) => { aa.termo = e.target.value.trim().toLowerCase(); aa.escolhido = -1; desenharAbrirDoAcervo(); };
  conferirAbrirDoAcervo();
  try {
    const d = await (await fetch("/api/biblioteca?filtro=todos&ordem=modificacao&limite=0")).json();
    aa.docs = (d.documentos || []).filter((x) => x.existe !== false);
  } catch (err) {
    aa.docs = [];
  }
  desenharAbrirDoAcervo();
  $("aa-busca").focus();
  const r = await escolha;
  if (r && r.ok && aa.escolhido >= 0) abrirDoAcervo(aa.docs[aa.escolhido]);
}

function desenharAbrirDoAcervo() {
  const lista = $("aa-lista");
  if (!lista || !aa.docs) return;
  const casa = (x) => !aa.termo || x.nome.toLowerCase().includes(aa.termo) || String(x.pasta_curta || "").toLowerCase().includes(aa.termo);
  const linhas = aa.docs.map((x, i) => [x, i]).filter(([x]) => casa(x));
  lista.innerHTML = linhas.map(([x, i]) => {
    const classe = "anx-linha" + (i === aa.escolhido ? " escolhida" : "");
    return '<div class="' + classe + '" data-aa="' + i + '">' + glifo(x.nome) +
      '<span class="duas-linhas"><b class="corta">' + esc(x.nome) + '</b><small class="corta">' + esc(x.pasta_curta || "") + "</small></span>" +
      '<span class="anx-quando">' + (/\.pdf$/i.test(x.nome) ? "Ler" : "Editar cópia") + "</span></div>";
  }).join("") || '<p class="anx-vazio">' + (aa.termo ? "Nenhum documento com esse nome no acervo." : "O Acervo está vazio.") + "</p>";
  lista.querySelectorAll("[data-aa]").forEach((el) => {
    el.onclick = () => { aa.escolhido = Number(el.dataset.aa); desenharAbrirDoAcervo(); };
    el.ondblclick = () => { aa.escolhido = Number(el.dataset.aa); if (dialogoAberto) dialogoAberto.fechar({ ok: true }); };
  });
  conferirAbrirDoAcervo();
}

function conferirAbrirDoAcervo() {
  const botao = document.querySelector('#veu-dialogo [data-dialogo="confirmar"]');
  const x = aa.docs && aa.escolhido >= 0 ? aa.docs[aa.escolhido] : null;
  if (botao) botao.textContent = x ? (/\.pdf$/i.test(x.nome) ? "Ler" : "Editar cópia") : "Abrir";
  if (botao) botao.disabled = !x;
  const conta = $("aa-conta");
  if (conta) conta.textContent = x ? "escolhido: " + x.nome : (aa.docs ? plural(aa.docs.length, "documento") + " no acervo" : "");
}

async function abrirDoAcervo(x) {
  if (/\.pdf$/i.test(x.nome)) {
    abrirAba({ id: "pdf:" + x.nome, titulo: x.nome.replace(/\.pdf$/i, ""), tipo: "pdf", nome: x.nome, caminho: x.caminho, paginas: x.paginas || 0 });
    return mostrarDocumentos();
  }
  const r = await fetch("/api/documentos/importar", {
    method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ caminho: x.caminho || "", nome: x.nome }),
  });
  if (!r.ok) { avisoCert(await erroDe(r)); return; }
  const d = await r.json();
  abrirAba({ id: d.id, titulo: d.titulo, tipo: "texto" });
  avisoCert("cópia editável criada a partir de " + d.de + " — o original fica como está");
  mostrarDocumentos("editor");
}

/* ---------------------------------------------------- PDF so leitura */

function barrasDoPdf(aba) {
  return '<div class="docs-barra">' +
    '<button data-pdf-andar="-1" title="Anterior">' + ic("chevron_left", 18) + "</button>" +
    '<span class="docs-pagina-num">Pág. <b id="pdf-num">' + (aba.pagina || 1) + "</b>" + (aba.paginas ? " / " + aba.paginas : "") + "</span>" +
    '<button data-pdf-andar="1" title="Próxima">' + ic("chevron_right", 18) + "</button>" +
    '<span class="docs-nota-direita">só leitura · o arquivo do Acervo, desenhado</span></div>';
}

function visorDoPdf(aba) {
  return '<div class="docs-cartao"><div class="docs-status"><span>' + esc(aba.nome) + '</span><span class="cresce"></span><span>PDF</span></div>' +
    '<div class="docs-pv-rolagem"><img class="docs-pagina" id="pdf-img" alt="página ' + (aba.pagina || 1) + '" src="/api/biblioteca/pagina?nome=' +
    encodeURIComponent(aba.nome) + "&numero=" + (aba.pagina || 1) + '&largura=1000"></div></div>';
}

function painelDoPdf(aba) {
  return '<aside class="acervo-painel" id="docs-painel"><div class="rolagem docs-painel">' + regioesDeFerramenta() +
    '<div class="painel-cabeca"><span class="titulo-painel"><h3>' + esc(aba.titulo) + '</h3><span class="meta">PDF do Acervo · só leitura</span></span></div>' +
    '<div class="painel-acoes"><button class="primario" id="doc-editar-copia-2">' + ic("edit", 16) + "Abrir para editar</button>" +
    '<button data-doc-no-acervo="1">' + ic("inventory_2", 16) + "Ver no Acervo</button></div>" +
    '<div class="painel-bloco"><div class="painel-bloco-cabeca"><span>O que dá para fazer</span></div>' +
    "<p>Ler e conferir, página a página. Para mexer no texto, “Abrir para editar” cria uma cópia editável — o PDF original continua intacto no Acervo.</p></div>" +
    "</div></aside>";
}

function ligarPdf(aba) {
  const raiz = $("docs");
  raiz.querySelectorAll("[data-pdf-andar]").forEach((b) => {
    b.onclick = () => {
      const n = (aba.pagina || 1) + Number(b.dataset.pdfAndar);
      if (n < 1 || (aba.paginas && n > aba.paginas)) return;
      aba.pagina = n;
      lembrarAbas();
      $("pdf-num").textContent = n;
      $("pdf-img").src = "/api/biblioteca/pagina?nome=" + encodeURIComponent(aba.nome) + "&numero=" + n + "&largura=1000";
    };
  });
  ["doc-editar-copia", "doc-editar-copia-2"].forEach((id) => { const b = $(id); if (b) b.onclick = () => importarPdf(aba); });
  const ver = raiz.querySelector("[data-doc-no-acervo]");
  if (ver) ver.onclick = () => { bib.termo = aba.nome; marcarDestino("biblioteca"); mostrarBiblioteca(); };
}

async function importarPdf(aba) {
  const r = await fetch("/api/documentos/importar", {
    method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ caminho: aba.caminho || "", nome: aba.nome }),
  });
  if (!r.ok) { avisoCert(await erroDe(r)); return; }
  const d = await r.json();
  abrirAba({ id: d.id, titulo: d.titulo, tipo: "texto" });
  mostrarDocumentos("editor");
}

function ligarEditor() {
  const folha = $("ed-folha");
  const id = escr.doc.id;
  const raiz = $("docs");

  raiz.querySelectorAll("[data-cmd]").forEach((b) => {
    b.onmousedown = (e) => e.preventDefault();   /* não perde a seleção */
    b.onclick = () => { document.execCommand(b.dataset.cmd, false, null); folha.focus(); marcarSujo(); };
  });
  $("ed-bloco").onchange = (e) => { document.execCommand("formatBlock", false, e.target.value); folha.focus(); marcarSujo(); };
  $("ed-fonte").onchange = () => gravarFormatoDaBarra();
  $("ed-corpo").onchange = () => gravarFormatoDaBarra();

  folha.oninput = marcarSujo;

  $("ed-versoes").onclick = () => painelVersoes(id);
  $("ed-imprimir").onclick = async () => {
    await gravarDocumento();
    abrirImprimir(id, escr.doc.titulo, 1, escr.paginacao ? escr.paginacao.paginas : 1);
  };
  $("ed-pdf").onclick = async () => { await gravarDocumento(); window.location.href = "/api/documentos/" + id + "/pdf"; };

  $("ed-quadro").onclick = painelQuadro;
  $("ed-alteracoes").onclick = () => painelAlteracoes();
  $("ed-comentar").onclick = comentarTrecho;
  raiz.querySelectorAll("[data-codigo]").forEach((b) => {
    b.onclick = () => { lei.codigo = b.dataset.codigo; painelCodigos(); };
  });
  $("ed-codigos").onclick = painelCodigos;
  $("ed-clausulas").onclick = painelClausulas;
  $("ed-numerar").onclick = renumerarClausulas;
  $("ed-refs").onclick = () => conferirReferencias(id);
  $("ed-conferir").onclick = () => painelConferir(id);
  $("ed-qualificar").onclick = inserirQualificacao;
  $("ed-formato").onclick = painelFormato;
  $("ed-modo-folha").onclick = alternarModoFolha;
  raiz.querySelectorAll("[data-ed-timbre]").forEach((b) => { b.onclick = () => { abrirModoFolha(); const c = $("ed-pedido"); if (c) c.focus(); }; });
  $("ed-regua-botao").onclick = () => {
    escr.regua = !escr.regua;
    $("ed-regua").hidden = !escr.regua;
    $("ed-regua-botao").textContent = escr.regua ? "Esconder a régua" : "Régua";
    revestirFolha();
  };

  const pedir = () => { const campo = $("ed-pedido"); const t = campo.value.trim(); campo.value = ""; pedirNoEditor(t); };
  $("ed-pedir").onclick = pedir;
  $("ed-pedido").onkeydown = (e) => { if (e.key === "Enter") pedir(); };
  raiz.querySelectorAll("[data-ed-fazer]").forEach((b) => { b.onclick = () => pedirNoEditor(b.dataset.edFazer); });
  raiz.querySelectorAll("[data-ed-conferir]").forEach((b) => { b.onclick = () => painelConferir(id); });
  raiz.querySelectorAll("[data-ed-citar]").forEach((b) => { b.onclick = painelCodigos; });
  ligarFalas($("ed-fala"), conversaAtual());

  folha.addEventListener("input", () => { pedirPaginacao(); repaginarLogo(); });
  if (!escr.ouvindo) {
    escr.ouvindo = true;
    document.addEventListener("selectionchange", mostrarPaginaDoCursor);
    document.addEventListener("selectionchange", lembrarCursor);
    document.addEventListener("selectionchange", mostrarSobreOQue);
    window.addEventListener("resize", revestirFolha);
  }
  aplicarPaginacao(Object.assign({}, escr.doc.paginacao, { folha: escr.doc.folha }));
  if (escr.modoFolha) { aplicarModoFolha(); painelDoModoFolha(); }
  carregarNotas();
  if (escr.pendente) desenharCartaoNoEditor();
}

/* "sobre o trecho selecionado" ou "sobre o documento": o painel diz em que
   o pedido vai cair antes de a pessoa pedir. */
function mostrarSobreOQue() {
  const alvo = $("ed-sobre");
  const folha = $("ed-folha");
  if (!alvo || !folha) return;
  const sel = window.getSelection();
  const dentro = sel && !sel.isCollapsed && sel.anchorNode && folha.contains(sel.anchorNode) && sel.toString().trim();
  alvo.textContent = dentro ? "sobre o trecho selecionado" : "sobre o documento";
}

/* Fonte e corpo saem da barra; recuo e entrelinhas continuam em "Folha". */
async function gravarFormatoDaBarra() {
  const f = Object.assign({}, escr.doc.formato || {});
  f.fonte = $("ed-fonte").value;
  f.corpo = Number($("ed-corpo").value) || 12;
  const r = await fetch("/api/documentos/" + escr.doc.id + "/formato", {
    method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ formato: f, corpo: $("ed-folha").innerHTML }),
  });
  if (!r.ok) { avisoCert(await erroDe(r)); return; }
  const d = await r.json();
  escr.doc.formato = d.formato;
  aplicarPaginacao(d);
}

/* Referencia cruzada: o que aponta para clausula que nao existe. E a
   conferencia sem mexer em nada; renumerar e quem conserta. */
async function conferirReferencias(id) {
  await gravarDocumento();
  const alvo = $("ed-abaixo");
  alvo.innerHTML = '<div class="painel"><p class="nota">conferindo as referências…</p></div>';
  const r = await fetch("/api/documentos/" + id + "/conferir-clausulas");
  if (!r.ok) { alvo.innerHTML = '<div class="painel"><p class="explica">' + esc(await erroDe(r)) + "</p></div>"; return; }
  const d = await r.json();
  alvo.innerHTML = '<div class="painel"><h3>Referências cruzadas</h3>' +
    '<p class="explica">' + (d.clausulas ? plural(d.clausulas, "cláusula numerada") + (d.fora_de_ordem ? " · fora de ordem" : " · em ordem") : "nenhuma cláusula numerada") + "</p>" +
    (d.quebradas && d.quebradas.length
      ? '<p class="explica">Apontando para o nada: ' + d.quebradas.map((q) => esc(q.texto)).join(", ") + ". Não existe cláusula com esse número.</p>"
      : '<p class="explica">Toda referência aponta para uma cláusula que existe.</p>') +
    '<div class="linha-form">' + (d.fora_de_ordem ? '<button class="primario" data-doc-renumerar="1">Renumerar</button>' : "") +
    '<button data-doc-fechar-ferramenta="1">Fechar</button></div></div>';
  alvo.querySelector("[data-doc-fechar-ferramenta]").onclick = () => { alvo.innerHTML = ""; };
  const ren = alvo.querySelector("[data-doc-renumerar]");
  if (ren) ren.onclick = renumerarClausulas;
  revelarAbaixo();
}

/* -------------------------------------------------- a página, medida

   "páginas ~4" era palavras dividido por 450. Erra em todo documento com
   título, lista ou parágrafo curto — e erra mais quanto maior o documento,
   que é quando a pessoa precisa saber. Agora quem conta é o próprio PDF
   sendo montado, o mesmo arquivo que a pré-visualização desenha. */

/* Os blocos da folha na MESMA regra que o servidor usa para lê-los: um
   parágrafo, título ou item que tenha texto ou uma quebra dentro. Se as duas
   contas divergirem, as linhas de quebra não são desenhadas — linha no lugar
   errado é pior que linha nenhuma. */
function blocosDaFolha(folha) {
  return Array.from(folha.querySelectorAll("p, div, h1, h2, h3, li, table"))
    /* O quadro é UM bloco, como no PDF — os parágrafos dentro das células não
       contam separado, senão a conta daqui deixa de bater com a de lá. */
    .filter((el) => el.tagName === "TABLE" || !el.closest("table"))
    /* O cartão da alteração sugerida é da tela: não vai para o arquivo, e
       contado aqui desencontrava a conta do PDF enquanto estava aberto. */
    .filter((el) => !el.closest(".dupla-cartao"))
    .filter((el) => el.textContent.trim() || el.querySelector("br"));
}

let relogioPaginacao = null;

function pedirPaginacao(agora) {
  clearTimeout(relogioPaginacao);
  const fazer = async () => {
    const folha = $("ed-folha");
    if (!folha || !escr.doc) return;
    try {
      const r = await fetch("/api/documentos/" + escr.doc.id + "/paginacao", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ corpo: folha.innerHTML }),
      });
      if (r.ok) aplicarPaginacao(await r.json());
    } catch (err) { /* medir a página não pode atrapalhar quem está escrevendo */ }
  };
  /* 700 ms depois da última tecla: montar o PDF custa dezenas de
     milissegundos, mas a cada tecla seriam dezenas de PDFs por frase. */
  if (agora) fazer(); else relogioPaginacao = setTimeout(fazer, 700);
}

/* A folha na tela desenhada na escala do PDF: um A4 tem 21 cm, ou 595,3 pt,
   de borda a borda. Sabendo quantos pixels essa largura tem aqui, um corpo
   12 pt vira o tamanho que ele terá no papel — e a linha quebra quase onde vai
   quebrar impressa. Sem isso, a folha era 15 px fixos e escolher corpo 13 no
   PDF não mudava nada na tela.

   clientWidth é a medida certa porque INCLUI o padding, e o padding da folha é
   justamente a margem de 2,5 cm: o que ele mede é a folha inteira. */
const PT_LARGURA_A4 = 595.3;
const CM_LARGURA_A4 = 21;

function vestirFolha(formato) {
  vestirFolhaEm($("ed-folha"), formato);
}

/* A mesma escala para qualquer folha: a do editor de Documentos e a do
   editor ao lado da conversa. */
function vestirFolhaEm(folha, formato) {
  if (!folha || !formato || !folha.clientWidth) return;
  const largura = folha.clientWidth;

  folha.style.fontFamily = formato.fonte === "sem-serifa"
    ? "Arial, Helvetica, sans-serif"
    : "'Times New Roman', Times, Georgia, serif";
  folha.style.fontSize = (formato.corpo * largura / PT_LARGURA_A4).toFixed(2) + "px";
  folha.style.lineHeight = String(formato.entrelinhas);
  folha.style.setProperty(
    "--recuo", (formato.recuo_cm * largura / CM_LARGURA_A4).toFixed(1) + "px");
}

function revestirFolha() {
  if (!escr.doc || !escr.doc.formato) return;
  vestirFolha(escr.doc.formato);
  if (escr.paginacao) aplicarPaginacao(escr.paginacao);
}

function aplicarPaginacao(mapa) {
  const folha = $("ed-folha");
  const tela = $("ed-quebras");
  if (!folha || !tela || !mapa) return;
  escr.paginacao = mapa;
  if (mapa.formato) escr.doc.formato = mapa.formato;
  if (mapa.folha) escr.doc.folha = mapa.folha;
  vestirFolha(escr.doc.formato);

  const contador = $("ed-paginas");
  if (contador) contador.textContent = plural(mapa.paginas, "página");

  const elementos = blocosDaFolha(folha);
  tela.innerHTML = "";
  const nota = $("ed-paginas-nota");

  paginarNaTela();

  if (elementos.length !== mapa.de_bloco.length) {
    /* Acontece com HTML colado de fora, com estrutura que o editor não cria.
       O total continua medido; as folhas da tela quebram pelo que cabe nelas. */
    if (nota) {
      nota.textContent = "Contagem medida no PDF. Neste documento as folhas da tela " +
        "quebram pelo que cabe nelas: a estrutura do texto não bate com a da folha impressa.";
    }
    mostrarPaginaDoCursor();
    return;
  }

  desenharNotas();
  if (nota) {
    nota.textContent = mapa.paginas === 1
      ? "Cabe em uma página. Contagem medida no PDF, não estimada."
      : "As linhas na folha são as quebras do PDF, medidas — não uma estimativa por " +
        "número de palavras.";
  }
  mostrarPaginaDoCursor();
}

/* -------------------------------------------- as folhas, como no Word

   O texto continua num campo editável só - é o que deixa o cursor, o
   desfazer e a seleção funcionarem sem biblioteca. As folhas são desenhadas
   ATRÁS dele (ed-folhas), e cada bloco que abre página ganha uma margem de
   cima que o leva ao topo da folha seguinte.

   Essa margem não pode ir no bloco: o que está dentro do contenteditable
   acaba no arquivo. Ela vai numa folha de estilo à parte (ed-saltos), com
   seletor pela posição do bloco. Parágrafo que atravessa o pé da folha é
   partido do mesmo jeito: um ::before que flutua com shape-outside empurra
   só as linhas que cairiam no vão entre as folhas.

   Onde a página quebra vem do PDF (o mapa medido); se a tela não couber o
   mesmo que o papel, a tela quebra antes em vez de invadir o vão. */
const VAO_ENTRE_FOLHAS = 28;

function seletorDoBloco(el, folha) {
  const passos = [];
  for (let no = el; no && no !== folha; no = no.parentElement) {
    passos.unshift(":nth-child(" + (Array.prototype.indexOf.call(no.parentElement.children, no) + 1) + ")");
  }
  return "#ed-folha > " + passos.join(" > ");
}

function desenhoDaFolha() {
  const f = escr.doc && escr.doc.folha;
  return (f && f.desenho) || { linhas: [], logo: false, logo_cm: 1.3, alinhar: "centro", fio: true, rodape: escr.doc ? escr.doc.titulo : "",
    numeracao: "pagina", numeracao_onde: "direita", topo_cm: 2.5, base_cm: 2.5, margem_cm: 2.5 };
}

let quadroDaPaginacao = 0;
function repaginarLogo() {
  cancelAnimationFrame(quadroDaPaginacao);
  quadroDaPaginacao = requestAnimationFrame(paginarNaTela);
}

function paginarNaTela() {
  const folha = $("ed-folha");
  const fundo = $("ed-folhas");
  const saltos = $("ed-saltos");
  if (!folha || !fundo || !saltos || !folha.clientWidth) return;

  const d = desenhoDaFolha();
  const cm = folha.clientWidth / CM_LARGURA_A4;
  const alto = 29.7 * cm;
  folha.style.paddingTop = (d.topo_cm * cm).toFixed(1) + "px";
  folha.style.paddingBottom = (d.base_cm * cm).toFixed(1) + "px";
  folha.style.minHeight = alto + "px";
  saltos.textContent = "";

  const inicio = (k) => (k - 1) * (alto + VAO_ENTRE_FOLHAS) + d.topo_cm * cm;
  const fim = (k) => (k - 1) * (alto + VAO_ENTRE_FOLHAS) + alto - d.base_cm * cm;
  const regras = new Map();
  const escrever = () => { saltos.textContent = Array.from(regras.values()).join("\n"); };
  const base = () => folha.getBoundingClientRect().top;
  const topoDe = (el) => el.getBoundingClientRect().top - base();
  const peDe = (el) => el.getBoundingClientRect().bottom - base();

  /* Levar o bloco até `alvo`: a margem colapsa com a do bloco de cima, então
     mede, corrige e mede de novo em vez de confiar na conta. */
  const levar = (el, alvo) => {
    const sel = seletorDoBloco(el, folha);
    let margem = parseFloat(getComputedStyle(el).marginTop) || 0;
    for (let n = 0; n < 3; n += 1) {
      const falta = alvo - topoDe(el);
      if (Math.abs(falta) < 0.5) break;
      margem = Math.max(0, margem + falta);
      regras.set(sel, sel + " { margin-top: " + margem.toFixed(1) + "px !important; }");
      escrever();
    }
  };

  const mapa = escr.paginacao;
  const blocos = blocosDaFolha(folha);
  const confere = mapa && mapa.de_bloco && blocos.length === mapa.de_bloco.length;
  /* Só as folhas da árvore: um div que embrulha parágrafos não se move, os
     parágrafos dentro dele é que se movem. */
  const embrulhos = new Set();
  blocos.forEach((el) => { for (let p = el.parentElement; p && p !== folha; p = p.parentElement) embrulhos.add(p); });

  let k = 1;
  blocos.forEach((el, i) => {
    if (embrulhos.has(el)) return;
    /* A folha da tela só anda por causa do PDF quando está atrás dele: se a
       tela já partiu o parágrafo anterior, a página nova já começou. */
    const quebraNoPdf = confere && mapa.de_bloco[i] > k;
    let topo = topoDe(el);
    if (quebraNoPdf || topo >= fim(k) - 1) {
      k = quebraNoPdf ? mapa.de_bloco[i] : k + 1;
      levar(el, inicio(k));
      topo = topoDe(el);
    }
    if (peDe(el) <= fim(k) + 1) return;

    const partivel = el.tagName !== "TABLE" && topo < fim(k);
    if (partivel) {
      const y = Math.max(0, fim(k) - topo);
      const vao = inicio(k + 1) - fim(k);
      const sel = seletorDoBloco(el, folha) + "::before";
      regras.set(sel, sel + ' { content: ""; float: left; width: 100%; height: ' + (y + vao).toFixed(1) +
        "px; shape-outside: inset(" + y.toFixed(1) + "px 0 0 0); }");
      escrever();
      k += 1;
    } else if (topo > inicio(k) + 1) {
      k += 1;
      levar(el, inicio(k));
    }
  });

  const total = Math.max(k, Math.ceil((folha.scrollHeight + VAO_ENTRE_FOLHAS) / (alto + VAO_ENTRE_FOLHAS)));
  folha.style.minHeight = (total * alto + (total - 1) * VAO_ENTRE_FOLHAS) + "px";
  desenharFolhas(total, alto, cm, d);
}

/* As folhas atrás do texto e, por cima das margens, o cabeçalho e o rodapé
   de cada uma - na mesma medida do PDF. Duplo clique neles abre o modo
   Folha, como no Word. */
function desenharFolhas(total, alto, cm, d) {
  const fundo = $("ed-folhas");
  const margens = $("ed-margens");
  if (!fundo || !margens) return;
  const pt = cm * CM_LARGURA_A4 / PT_LARGURA_A4;
  const fonte = (escr.doc.formato || {}).fonte === "sem-serifa" ? "Arial, Helvetica, sans-serif" : "'Times New Roman', Times, Georgia, serif";
  const paginasDoPdf = escr.paginacao && escr.paginacao.paginas ? escr.paginacao.paginas : total;
  const numero = (n) => {
    if (d.numeracao === "nenhuma") return "";
    if (d.numeracao === "numero") return String(n);
    if (d.numeracao === "pagina_de") return "página " + n + " de " + Math.max(paginasDoPdf, total);
    return "página " + n;
  };
  const ladoDoTexto = d.numeracao_onde === "esquerda" ? "direita" : "esquerda";
  const logo = d.logo ? '<img class="ed-cab-logo" src="/marca/logo.png?v=' + (escr.versaoDaLogo || 0) + '" alt="" style="height:' + (d.logo_cm * cm).toFixed(1) + 'px">' : "";

  let folhas = "", cabecas = "";
  for (let n = 1; n <= total; n += 1) {
    const topo = (n - 1) * (alto + VAO_ENTRE_FOLHAS);
    folhas += '<div class="ed-pagina" style="top:' + topo + "px;height:" + alto + 'px"></div>';
    const cab = d.linhas.length
      ? '<div class="ed-cab lado-' + d.alinhar + (d.fio ? " com-fio" : "") + '" data-ed-cab="1" title="Clique duas vezes para editar o cabeçalho" style="top:' + (topo + d.margem_cm * cm) +
        "px;height:" + ((d.topo_cm - d.margem_cm - 0.3) * cm).toFixed(1) + "px;left:" + (d.margem_cm * cm) + "px;right:" + (d.margem_cm * cm) + "px;font-family:" + fonte + '">' +
        logo + '<b style="font-size:' + (12 * pt).toFixed(1) + 'px">' + esc(d.linhas[0]) + "</b>" +
        d.linhas.slice(1).map((l) => '<span style="font-size:' + (8.5 * pt).toFixed(1) + 'px">' + esc(l) + "</span>").join("") + "</div>"
      : '<div class="ed-cab vazio" data-ed-cab="1" title="Clique duas vezes para criar um cabeçalho" style="top:' + (topo + 0.6 * cm) + "px;height:" + ((d.margem_cm - 0.9) * cm).toFixed(1) +
        "px;left:" + (d.margem_cm * cm) + "px;right:" + (d.margem_cm * cm) + 'px"></div>';
    const pe = '<div class="ed-pe" data-ed-pe="1" title="Clique duas vezes para editar o rodapé" style="top:' + (topo + alto - 1.4 * cm - 8.5 * pt) + "px;left:" + (d.margem_cm * cm) +
      "px;right:" + (d.margem_cm * cm) + "px;font-size:" + (8.5 * pt).toFixed(1) + "px;font-family:" + fonte + '">' +
      '<span class="lado-' + ladoDoTexto + '">' + esc(d.rodape || "") + '</span><span class="lado-' + d.numeracao_onde + '">' + esc(numero(n)) + "</span></div>";
    cabecas += cab + pe;
  }
  fundo.innerHTML = folhas;
  margens.innerHTML = cabecas;
  margens.querySelectorAll("[data-ed-cab], [data-ed-pe]").forEach((z) => {
    z.ondblclick = () => abrirModoFolha(z.dataset.edPe ? "rodape" : "cabecalho");
  });
}

/* ------------------------------------------------------ o modo Folha

   Mexer na folha, e não no texto: o papel timbrado, o rodapé, a logo e a
   numeração. O texto fica esmaecido e travado enquanto isso - quem clica no
   cabeçalho não pode acabar escrevendo no contrato. Tudo grava na hora e
   não cria versão: mudou como o documento sai, não o que ele diz. */

const ROTULO_DA_NUMERACAO = { pagina: "página 1", pagina_de: "página 1 de 3", numero: "1", nenhuma: "sem número" };
const ROTULO_DO_LADO = { esquerda: "Esquerda", centro: "Centro", direita: "Direita" };

function abrirModoFolha(onde) {
  if (!escr.modoFolha) { escr.modoFolha = true; aplicarModoFolha(); }
  if (escr.foco) alternarFoco(false);
  painelDoModoFolha(onde);
}

function alternarModoFolha() {
  if (escr.modoFolha) { escr.modoFolha = false; aplicarModoFolha(); } else abrirModoFolha();
}

function aplicarModoFolha() {
  const papel = $("ed-papel");
  const folha = $("ed-folha");
  const b = $("ed-modo-folha");
  if (papel) papel.classList.toggle("modo-folha", escr.modoFolha);
  if (folha) folha.contentEditable = escr.modoFolha ? "false" : "true";
  if (b) {
    b.classList.toggle("on", escr.modoFolha);
    b.innerHTML = ic("edit_document", 16) + (escr.modoFolha ? "Concluir a folha" : "Editar a folha");
  }
  const pedido = $("ed-pedido");
  if (pedido) pedido.placeholder = escr.modoFolha ? "Descreva a folha: timbre, rodapé, numeração…" : "Peça uma alteração ou uma pesquisa…";
  if (!escr.modoFolha) {
    const alvo = $("ed-abaixo");
    if (alvo && alvo.querySelector(".folha-painel")) alvo.innerHTML = "";
    if (folha) folha.focus();
  }
}

function folhaAtual() {
  const f = Object.assign({}, escr.doc.folha || {});
  delete f.desenho;
  delete f.escritorio;
  return f;
}

/* O modo "padrao" (seguir a chave de Configurações) aparece como a escolha
   que ele resolve hoje; tocar num botão troca para a escolha explícita. */
function cabecalhoEfetivo(f) {
  if (f.cabecalho !== "padrao") return f.cabecalho;
  const e = (escr.doc.folha || {}).escritorio || {};
  return e.timbre_ligado ? "escritorio" : "nenhum";
}

function painelDoModoFolha(onde) {
  const alvo = $("ed-abaixo");
  if (!alvo || !escr.doc) return;
  const f = folhaAtual();
  const esc_ = (escr.doc.folha || {}).escritorio || { linhas: [], logo: false };
  const cab = cabecalhoEfetivo(f);
  const segmento = (grupo, valor, rotulo, atual) =>
    '<button type="button" class="' + (valor === atual ? "ativa" : "") + '" data-fl-' + grupo + '="' + valor + '">' + rotulo + "</button>";
  const linhas = [0, 1, 2, 3].map((i) =>
    '<input type="text" class="fl-linha' + (i === 0 ? " destaque" : "") + '" data-fl-linha="' + i + '" maxlength="130" value="' + esc(f.linhas[i] || "") + '" placeholder="' +
    ["Nome em destaque", "OAB · CPF ou CNPJ", "Endereço · telefone · e-mail", "Mais uma linha (opcional)"][i] + '">').join("");

  alvo.innerHTML = '<div class="painel folha-painel">' +
    '<div class="fl-cabeca"><h3>A folha deste documento</h3><button class="docs-ligacao" data-fl-concluir="1">Concluir</button></div>' +
    '<p class="explica">Sai em toda página: no PDF, na impressão e na assinatura. O texto do documento não muda.</p>' +

    '<section class="fl-bloco" id="fl-cabecalho"><h4>Cabeçalho</h4>' +
    '<div class="visoes fl-seg">' + segmento("cab", "escritorio", "Do escritório", cab) + segmento("cab", "proprio", "Escrever", cab) + segmento("cab", "nenhum", "Nenhum", cab) + "</div>" +
    (f.cabecalho === "padrao" ? '<small class="fl-nota">Segue a chave de Configurações › timbre no PDF (' + (esc_.timbre_ligado ? "ligada" : "desligada") + ").</small>" : "") +
    (cab === "escritorio"
      ? (esc_.linhas.length
        ? '<div class="fl-previa-linhas">' + esc_.linhas.map((l, i) => (i ? "<span>" : "<b>") + esc(l) + (i ? "</span>" : "</b>")).join("") + "</div>" +
          '<button class="docs-ligacao" data-fl-copiar="1">Copiar para editar só neste documento</button>'
        : '<small class="fl-nota">Seus dados profissionais ainda estão vazios. <button class="docs-ligacao" data-fl-config="1">Preencher em Configurações</button></small>')
      : "") +
    (cab === "proprio" ? '<div class="fl-linhas">' + linhas + "</div>" +
      (esc_.linhas.length ? '<button class="docs-ligacao" data-fl-meus="1">Trazer meus dados profissionais</button>' : "") : "") +
    (cab !== "nenhum"
      ? '<div class="fl-linha-form"><span>Alinhar</span><div class="visoes fl-seg pequeno">' +
        ["esquerda", "centro", "direita"].map((l) => segmento("alinhar", l, ROTULO_DO_LADO[l], f.alinhar)).join("") + "</div></div>" +
        '<label class="fl-marcar"><input type="checkbox" data-fl-logo="1"' + (f.logo ? " checked" : "") + "><span>Com a logo" +
        (esc_.logo ? "" : " <small>(nenhuma enviada)</small>") + '</span><button class="docs-ligacao" data-fl-trocar-logo="1">' + (esc_.logo ? "Trocar a logo" : "Enviar a logo") + "</button></label>" +
        '<label class="fl-marcar"><input type="checkbox" data-fl-fio="1"' + (f.fio ? " checked" : "") + "><span>Fio separando do texto</span></label>"
      : "") +
    '<input type="file" id="fl-logo-arquivo" accept="image/png,image/jpeg,image/webp" hidden></section>' +

    '<section class="fl-bloco" id="fl-rodape"><h4>Rodapé</h4>' +
    '<div class="visoes fl-seg">' + segmento("rod", "titulo", "Título", f.rodape) + segmento("rod", "proprio", "Escrever", f.rodape) + segmento("rod", "nenhum", "Nenhum", f.rodape) + "</div>" +
    (f.rodape === "proprio" ? '<input type="text" class="fl-linha" data-fl-rodape="1" maxlength="110" value="' + esc(f.rodape_texto || "") + '" placeholder="Ex.: Documento confidencial · www.seusite.com.br">' : "") +
    '<div class="fl-linha-form"><span>Numeração</span><select class="docs-sel" id="fl-numeracao">' +
    Object.keys(ROTULO_DA_NUMERACAO).map((n) => '<option value="' + n + '"' + (n === f.numeracao ? " selected" : "") + ">" + ROTULO_DA_NUMERACAO[n] + "</option>").join("") + "</select></div>" +
    (f.numeracao !== "nenhuma"
      ? '<div class="fl-linha-form"><span>Posição</span><div class="visoes fl-seg pequeno">' +
        ["esquerda", "centro", "direita"].map((l) => segmento("onde", l, ROTULO_DO_LADO[l], f.numeracao_onde)).join("") + "</div></div>"
      : "") + "</section>" +

    '<section class="fl-bloco">' + '<h4>' + coroa(14) + "Pedir ao assistente</h4>" +
    '<small class="fl-nota">Descreva a folha na conversa aqui embaixo — ex.: “timbre com meu nome e OAB à esquerda, página 1 de 3 no centro, sem logo”. ' +
    "Eu aplico e você mantém ou desfaz. Número de OAB, telefone ou endereço só entram se estiverem nos seus dados.</small></section></div>";

  const salvarJa = (mudanca) => salvarFolha(Object.assign(folhaAtual(), mudanca), true);
  alvo.querySelector("[data-fl-concluir]").onclick = () => { escr.modoFolha = false; aplicarModoFolha(); };
  alvo.querySelectorAll("[data-fl-cab]").forEach((b) => { b.onclick = () => {
    const mudanca = { cabecalho: b.dataset.flCab };
    if (b.dataset.flCab === "proprio" && !folhaAtual().linhas.length) mudanca.linhas = esc_.linhas.slice(0, 4);
    salvarJa(mudanca);
  }; });
  alvo.querySelectorAll("[data-fl-rod]").forEach((b) => { b.onclick = () => salvarJa({ rodape: b.dataset.flRod }); });
  alvo.querySelectorAll("[data-fl-alinhar]").forEach((b) => { b.onclick = () => salvarJa({ alinhar: b.dataset.flAlinhar }); });
  alvo.querySelectorAll("[data-fl-onde]").forEach((b) => { b.onclick = () => salvarJa({ numeracao_onde: b.dataset.flOnde }); });
  const ligar = (sel, fazer) => { const el = alvo.querySelector(sel); if (el) fazer(el); };
  ligar("[data-fl-logo]", (el) => { el.onchange = () => salvarJa({ logo: el.checked }); });
  ligar("[data-fl-fio]", (el) => { el.onchange = () => salvarJa({ fio: el.checked }); });
  ligar("#fl-numeracao", (el) => { el.onchange = () => salvarJa({ numeracao: el.value }); });
  ligar("[data-fl-copiar]", (el) => { el.onclick = () => salvarJa({ cabecalho: "proprio", linhas: esc_.linhas.slice(0, 4) }); });
  ligar("[data-fl-meus]", (el) => { el.onclick = () => salvarJa({ linhas: esc_.linhas.slice(0, 4) }); });
  ligar("[data-fl-config]", (el) => { el.onclick = () => mostrarConfig("perfil"); });
  ligar("[data-fl-trocar-logo]", (el) => { el.onclick = (e) => { e.preventDefault(); $("fl-logo-arquivo").click(); }; });
  ligar("#fl-logo-arquivo", (el) => { el.onchange = () => enviarLogoDaFolha(el.files[0]); });
  /* Texto grava sem redesenhar o painel: o cursor fica onde a pessoa está. */
  alvo.querySelectorAll("[data-fl-linha]").forEach((el) => {
    el.oninput = () => {
      const linhas = Array.from(alvo.querySelectorAll("[data-fl-linha]")).map((c) => c.value);
      salvarFolha(Object.assign(folhaAtual(), { cabecalho: "proprio", linhas: linhas }), false);
    };
  });
  ligar("[data-fl-rodape]", (el) => { el.oninput = () => salvarFolha(Object.assign(folhaAtual(), { rodape: "proprio", rodape_texto: el.value }), false); });
  alvo.querySelectorAll("select").forEach(melhorarSelect);

  const secao = onde === "rodape" ? $("fl-rodape") : $("fl-cabecalho");
  if (secao) secao.scrollIntoView({ behavior: animacoesLigadas() ? "smooth" : "auto", block: "nearest" });
}

let relogioDaFolha = null;
function salvarFolha(folha, redesenhar) {
  clearTimeout(relogioDaFolha);
  const fazer = async () => {
    const r = await fetch("/api/documentos/" + escr.doc.id + "/formato", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ formato: Object.assign({}, escr.doc.formato, { folha: folha }), corpo: $("ed-folha").innerHTML }),
    });
    if (!r.ok) { avisoCert(await erroDe(r)); return; }
    const d = await r.json();
    escr.doc.formato = d.formato;
    aplicarPaginacao(d);
    if (redesenhar && escr.modoFolha) painelDoModoFolha();
  };
  if (redesenhar) return fazer();
  relogioDaFolha = setTimeout(fazer, 450);
}

async function enviarLogoDaFolha(arquivo) {
  if (!arquivo) return;
  const dados = new FormData();
  dados.append("arquivo", arquivo);
  const r = await fetch("/api/marca/logo", { method: "POST", body: dados });
  if (!r.ok) { avisoCert(await erroDe(r)); return; }
  escr.versaoDaLogo = Date.now();
  await salvarFolha(Object.assign(folhaAtual(), { logo: true }), true);
}

/* O assistente monta a folha: a regra resolve as escolhas, o modelo escreve
   as linhas. Aplica na hora e oferece desfazer - o mesmo trato do texto. */
async function pedirNaFolha(pedido) {
  const conversa = conversaAtual();
  escr.ocupada = true;
  conversa.push({ autor: "pessoa", texto: pedido });
  redesenharFalas("ed-fala");
  const antes = folhaAtual();
  try {
    const r = await fetch("/api/documentos/" + escr.doc.id + "/folha/sugerir", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ pedido: pedido, folha: antes }),
    });
    if (!r.ok) throw new Error(await erroDe(r));
    const s = await r.json();
    await salvarFolha(s.folha, true);
    const f = s.folha;
    const partes = [];
    if (f.cabecalho === "proprio" && f.linhas.length) partes.push("cabeçalho com " + plural(f.linhas.length, "linha"));
    else if (f.cabecalho === "nenhum") partes.push("sem cabeçalho");
    partes.push("numeração " + ROTULO_DA_NUMERACAO[f.numeracao] + (f.numeracao === "nenhuma" ? "" : " à " + ROTULO_DO_LADO[f.numeracao_onde].toLowerCase()));
    if (f.rodape === "proprio") partes.push("rodapé “" + f.rodape_texto + "”");
    conversa.push({
      autor: "paulus",
      html: esc("Montei a folha: " + partes.join(", ") + "." + (s.nota ? " (" + s.nota + ")" : "") + " Confira nas páginas ao lado."),
      acoes: [
        { icone: "check", rotulo: "Manter", primario: true, acao: (b) => { b.closest(".docs-resposta-acoes").innerHTML = '<span class="nota">mantido</span>'; } },
        { icone: "undo", rotulo: "Desfazer", acao: () => salvarFolha(antes, true) },
      ],
    });
  } catch (err) {
    conversa.push({ autor: "paulus", html: esc("Não consegui montar a folha: " + (err.message || err)) });
  } finally {
    escr.ocupada = false;
    redesenharFalas("ed-fala");
  }
}

/* Em que página está o cursor. Sai do mesmo mapa medido: é a página do bloco
   onde a seleção está, não uma conta de quanto texto veio antes. */
function mostrarPaginaDoCursor() {
  const fim = $("ed-regua-fim");
  const folha = $("ed-folha");
  const mapa = escr.paginacao;
  if (!fim || !folha || !mapa) return;

  const base = "A4 · margens 2,5 cm";
  const sel = window.getSelection();
  if (!sel || !sel.anchorNode || !folha.contains(sel.anchorNode)) { fim.textContent = base; return; }

  const elementos = blocosDaFolha(folha);
  if (elementos.length !== mapa.de_bloco.length) { fim.textContent = base; return; }

  const no = sel.anchorNode.nodeType === 1 ? sel.anchorNode : sel.anchorNode.parentElement;
  const onde = elementos.findIndex((el) => el === no || el.contains(no));
  fim.textContent = onde < 0
    ? base
    : base + " · cursor na página " + mapa.de_bloco[onde] + " de " + mapa.paginas;
}

function marcarSujo() {
  const estadoTexto = $("ed-estado");
  if (estadoTexto) { estadoTexto.textContent = "salvando…"; estadoTexto.classList.add("salvando"); }
  clearTimeout(escr.relogio);
  escr.relogio = setTimeout(gravarDocumento, 1400);
}

async function gravarDocumento(nota) {
  const folha = $("ed-folha");
  if (!folha || !escr.doc) return;
  clearTimeout(escr.relogio);

  /* O cartao da alteracao e da tela, nao do documento. */
  const copia = folha.cloneNode(true);
  copia.querySelectorAll(".dupla-cartao").forEach((c) => c.remove());
  const titulo = $("ed-titulo") ? $("ed-titulo").value : escr.doc.titulo;

  const r = await fetch("/api/documentos/" + escr.doc.id, {
    method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ corpo: copia.innerHTML, titulo: titulo, nota: nota || "" }),
  });
  if (!r.ok) { avisoCert(await erroDe(r)); return; }

  const d = await r.json();
  escr.doc.corpo = copia.innerHTML;
  escr.doc.titulo = titulo;
  escr.doc.versao = d.versao;
  escr.doc.contagem = d.contagem || escr.doc.contagem;
  const aba = abaAtual();
  if (aba && aba.id === escr.doc.id && aba.titulo !== titulo) { aba.titulo = titulo; lembrarAbas(); }

  const alvo = $("ed-estado");
  if (alvo) {
    alvo.classList.remove("salvando");
    alvo.textContent = "Salvo às " + new Date().toTimeString().slice(0, 5) + " · v" + d.versao +
      (d.contagem ? " · " + plural(d.contagem.palavras, "palavra") : "");
  }
}

function trechoSelecionado() {
  const sel = window.getSelection();
  return sel && sel.toString().trim() ? sel.toString().trim() : "";
}

/* O pedido vira alteracao no documento, marcada, com o cartao de manter ou
   descartar ancorado no proprio texto - o comentario do assistente do
   desenho. Nada entra no contrato sem o sim. */
async function pedirNoEditor(pedido) {
  if (!pedido || escr.ocupada) return;
  if (escr.modoFolha) return pedirNaFolha(pedido);
  const conversa = conversaAtual();
  escr.ocupada = true;
  conversa.push({ autor: "pessoa", texto: pedido });
  redesenharFalas("ed-fala");

  const folha = $("ed-folha");
  escr.antes = folha.innerHTML;
  const trecho = trechoSelecionado();

  try {
    const r = await fetch("/api/documentos/" + escr.doc.id + "/assistente", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ pedido: pedido, trecho: trecho }),
    });
    if (!r.ok) throw new Error(await erroDe(r));
    const s = await r.json();
    const antes = escr.antes;
    aplicarNoEditor(s);
    conversa.push({
      autor: "paulus",
      html: esc(s.sobre
        ? "Troquei o trecho que você selecionou. A alteração está marcada no documento — mantenha ou descarte ali mesmo."
        : "Escrevi no fim do documento. A alteração está marcada — confira antes de manter."),
      trecho: s.sugestao.slice(0, 180),
      acoes: [
        { icone: "visibility", rotulo: "Ver o que mudei", acao: () => {
          const m = $("ed-folha").querySelector(".ed-novo");
          if (m) m.scrollIntoView({ behavior: "smooth", block: "center" });
          else avisoCert("essa alteração já foi mantida e virou parte do texto");
        } },
        { icone: "undo", rotulo: "Desfazer", acao: () => desfazerNoEditor(antes) },
      ],
    });
  } catch (err) {
    conversa.push({ autor: "paulus", html: esc("Não consegui: " + (err.message || err)) });
  } finally {
    escr.ocupada = false;
    redesenharFalas("ed-fala");
  }
}

function aplicarNoEditor(s) {
  const folha = $("ed-folha");
  folha.querySelectorAll(".ed-novo").forEach((m) => desmarcar(m));
  const velho = $("ed-cartao");
  if (velho) velho.remove();

  const marca = document.createElement("mark");
  marca.className = "ed-novo";
  marca.textContent = s.sugestao;

  const sel = window.getSelection();
  if (s.sobre && sel && sel.rangeCount && !sel.isCollapsed && folha.contains(sel.anchorNode)) {
    const faixa = sel.getRangeAt(0);
    faixa.deleteContents();
    faixa.insertNode(marca);
  } else {
    const bloco = document.createElement("p");
    bloco.appendChild(marca);
    folha.appendChild(bloco);
  }
  escr.pendente = { aviso: s.aviso, resumo: s.sugestao.slice(0, 120) };
  desenharCartaoNoEditor();
  marca.scrollIntoView({ behavior: "smooth", block: "center" });
  marcarSujo();
  pedirPaginacao();
}

function desenharCartaoNoEditor() {
  const velho = $("ed-cartao");
  if (velho) velho.remove();
  if (!escr.pendente) return;
  const folha = $("ed-folha");
  const marca = folha && folha.querySelector(".ed-novo");
  if (!marca) { escr.pendente = null; return; }

  const cartao = document.createElement("div");
  cartao.className = "dupla-cartao";
  cartao.id = "ed-cartao";
  cartao.contentEditable = "false";
  cartao.innerHTML = '<span class="rotulo-cartao">' + coroa(14) + "Comentário do assistente</span>" +
    "<p>" + esc(escr.pendente.resumo) + "</p>" +
    '<p class="explica">' + esc(escr.pendente.aviso || "") + "</p>" +
    '<div class="linha-form"><button class="primario" id="ed-manter">Manter</button><button id="ed-descartar">Descartar</button></div>';
  marca.closest("p, li, h1, h2, h3, div, td, th").after(cartao);

  $("ed-manter").onclick = () => {
    folha.querySelectorAll(".ed-novo").forEach((m) => desmarcar(m));
    escr.pendente = null;
    cartao.remove();
    gravarDocumento();
    pedirPaginacao(true);
  };
  $("ed-descartar").onclick = () => desfazerNoEditor(escr.antes);
}

function desfazerNoEditor(antes) {
  const folha = $("ed-folha");
  if (antes === null || antes === undefined || !folha) return;
  folha.innerHTML = antes;
  escr.pendente = null;
  const c = $("ed-cartao");
  if (c) c.remove();
  conversaAtual().push({ autor: "paulus", html: "Desfeito. O documento voltou ao que era antes dessa alteração." });
  redesenharFalas("ed-fala");
  gravarDocumento();
  pedirPaginacao(true);
}

/* Quem chamava a sugestao antiga (qualificacao, clausulas) continua
   encontrando o mesmo nome. */
function aceitarSugestao() {
  if (!escr.sugestao) return;
  aplicarNoEditor(escr.sugestao);
  escr.sugestao = null;
}

async function painelClausulas() {
  const alvo = $("ed-abaixo");
  alvo.innerHTML = '' + esqueleto("lista") + '';
  const d = await (await fetch("/api/documentos/modelos")).json();

  alvo.innerHTML = '<div class="painel" style="margin-top:16px"><h3>Cláusulas do escritório</h3>' +
    '<p class="explica">Modelos que você mesmo guarda. Clique para inserir no fim do documento.</p>' +
    (d.clausulas.length
      ? d.clausulas.map((c) =>
          '<div class="doc-lista-linha"><span class="cresce corta">' + esc(c.titulo) + "</span>" +
          '<button data-clausula="' + esc(c.id) + '">Inserir</button>' +
          '<button class="perigo" data-tirar-cl="' + esc(c.id) + '">Apagar</button></div>').join("")
      : '<p class="explica">Nenhuma cláusula guardada ainda.</p>') +
    '<div class="linha-form"><button id="cl-nova">Guardar o trecho selecionado como cláusula</button></div>' +
    (d.tem_codigo
      ? '<div class="linha-form"><button id="cl-codigos">Citar a lei</button></div>'
      : '<div class="cert-aviso" style="margin-top:14px"><strong>' + esc(d.sem_codigo.titulo) + "</strong>" +
        "<p>" + esc(d.sem_codigo.porque) + " Instale em " + esc(d.sem_codigo.onde) + ".</p></div>") +
    "</div>";

  d.clausulas.forEach((c) => {
    const b = alvo.querySelector('[data-clausula="' + c.id + '"]');
    if (b) b.onclick = () => {
      const bloco = document.createElement("p");
      bloco.textContent = c.texto;
      $("ed-folha").appendChild(bloco);
      marcarSujo();
      avisoCert("cláusula “" + c.titulo + "” inserida no fim do documento");
    };
  });
  alvo.querySelectorAll("[data-tirar-cl]").forEach((b) => {
    b.onclick = async () => {
      await fetch("/api/documentos/modelos/" + b.dataset.tirarCl, { method: "DELETE" });
      painelClausulas();
    };
  });
  const bcod = $("cl-codigos");
  if (bcod) bcod.onclick = painelCodigos;

  $("cl-nova").onclick = async () => {
    const texto = trechoSelecionado();
    if (!texto) { avisoCert("selecione o trecho no documento antes"); return; }
    const titulo = await perguntar({ titulo: "Guardar cláusula", contexto: "Editor › Cláusulas", campo: { rotulo: "Nome desta cláusula", valor: texto.slice(0, 40), icone: "draft" }, confirmar: "Guardar" });
    if (!titulo) return;
    await fetch("/api/documentos/modelos", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ titulo: titulo, texto: texto }),
    });
    painelClausulas();
  };
  revelarAbaixo();
}

async function painelVersoes(id) {
  const alvo = $("ed-abaixo");
  alvo.innerHTML = '<p class="nota">abrindo o histórico…</p>';
  const d = await (await fetch("/api/documentos/" + id + "/versoes")).json();

  alvo.innerHTML = '<div class="painel" style="margin-top:16px"><h3>Histórico de versões</h3>' +
    '<p class="explica">Voltar para uma versão antiga cria uma versão nova — o caminho de ' +
    "volta continua existindo.</p>" +
    d.versoes.map((v) =>
      '<div class="doc-lista-linha"><span class="doc-versao">v' + v.numero + "</span>" +
      '<span class="cresce corta">' + esc(v.nota || "sem nota") + "</span>" +
      '<span class="num">' + esc(quandoCurto(v.criada_em)) + "</span>" +
      '<button data-ver="' + v.numero + '">Comparar com a atual</button>' +
      '<button data-voltar="' + v.numero + '">Voltar para esta</button></div>').join("") +
    '<div id="ed-diferencas"></div></div>';

  alvo.querySelectorAll("[data-ver]").forEach((b) => {
    b.onclick = async () => {
      const alvoDif = $("ed-diferencas");
      alvoDif.innerHTML = '<p class="nota">comparando…</p>';
      const c = await (await fetch("/api/documentos/" + id + "/comparar?de=" + b.dataset.ver)).json();
      alvoDif.innerHTML = '<div style="margin-top:12px"><span class="rotulo">v' + c.de + " comparada com a v" + c.ate + "</span>" +
        (c.mudancas.length
          ? c.mudancas.map((m) =>
              '<div class="pv-mudanca">' +
              (m.antes ? '<div class="saiu">' + esc(m.antes) + "</div>" : "") +
              (m.depois ? '<div class="entrou">' + esc(m.depois) + "</div>" : "") +
              "</div>").join("")
          : '<p class="explica">Nada mudou no texto entre essas versões.</p>') + "</div>";
    };
  });
  alvo.querySelectorAll("[data-voltar]").forEach((b) => {
    b.onclick = async () => {
      if (!(await confirmar({ titulo: "Voltar para a v" + b.dataset.voltar + "?", contexto: "Editor › Versões", texto: "Isso cria uma versão nova com aquele conteúdo. Nada é perdido: as versões seguintes continuam no histórico.", confirmar: "Voltar para a v" + b.dataset.voltar }))) return;
      const r = await (await fetch("/api/documentos/" + id + "/restaurar", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ numero: Number(b.dataset.voltar) }),
      })).json();
      escr.doc = r.documento;
      desenharEditor();
    };
  });
  revelarAbaixo();
}

async function painelConferir(id) {
  const alvo = $("ed-abaixo");
  alvo.innerHTML = '<p class="nota">conferindo…</p>';
  await gravarDocumento();
  const d = await (await fetch("/api/documentos/" + id + "/conferir")).json();
  alvo.innerHTML = '<div class="painel" style="margin-top:16px">' + blocoAvisos(d) + "</div>";
  revelarAbaixo();
}

function blocoAvisos(d) {
  return "<h3>Confira antes de sair</h3>" +
    '<p class="explica">' + plural(d.paginas, "página") + " · " +
    (d.avisos.length ?plural(d.avisos.length, "aviso") + "" : "nada a apontar") + "</p>" +
    (d.avisos.length
      ? d.avisos.map((a) =>
          '<div class="pv-aviso"><span class="pv-grau ' + (a.grau === "impede" ? "impede" : "") + '">' +
          (a.grau === "impede" ? "resolver" : "confira") + "</span>" +
          "<span><b>" + esc(a.titulo) + "</b><br>" + esc(a.detalhe) + "</span></div>").join("")
      : '<p class="explica">Não achei lacuna de modelo, CPF ou CNPJ com dígito errado, nem valor sem número.</p>');
}

/* ------------------------------------------------ C2: pré-visualização */
/*
   O PDF de verdade, desenhado: miniaturas a esquerda, a pagina no meio e, no
   painel, o que fazer agora, o que conferir antes de sair e as versoes.
*/

function barrasDaPrevia() {
  const p = escr.previa;
  const d = p.dados;
  const classeDuas = "com-texto" + (p.duas ? " on" : "");
  return '<div class="docs-barra">' +
    '<button id="pv-antes" title="Página anterior">' + ic("chevron_left", 18) + "</button>" +
    '<span class="docs-pagina-num">Pág. <b id="pv-num">' + p.pagina + "</b> / " + d.paginas + "</span>" +
    '<button id="pv-depois" title="Próxima página">' + ic("chevron_right", 18) + "</button>" +
    '<span class="divisa-v"></span>' +
    '<button class="' + classeDuas + '" id="pv-duas">' + ic("auto_stories", 16) + "Duas páginas</button>" +
    '<button class="com-texto" id="pv-cheia">' + ic("fullscreen", 16) + (p.cheia ? "Sair da tela cheia" : "Tela cheia") + "</button>" +
    '<span class="divisa-v"></span>' +
    '<button class="com-texto" id="pv-comparar-b">' + ic("difference", 16) + "Comparar versões</button>" +
    '<span class="docs-nota-direita">Versão ' + d.versao + " · A4 · margens 2,5 cm</span></div>";
}

function folhaDaPrevia() {
  const p = escr.previa;
  const d = p.dados;
  const paginas = [];
  for (let i = 1; i <= d.paginas; i += 1) paginas.push(i);
  const miniaturas = paginas.map((i) => {
    const classe = "docs-mini" + (i === p.pagina || (p.duas && i === p.pagina + 1) ? " atual" : "");
    return '<button class="' + classe + '" data-pv-pagina="' + i + '"><img alt="" src="/api/documentos/' + p.id +
      "/pagina?numero=" + i + '&largura=96"><span>' + i + "</span></button>";
  }).join("");
  const classeSinc = "docs-sinc" + (d.impedem ? " atencao" : "");
  return '<div class="docs-cartao previa">' +
    '<div class="docs-status"><span>Página ' + p.pagina + " de " + d.paginas + '</span><span class="docs-divisa-fina"></span>' +
    '<span class="' + classeSinc + '"><i></i>' + (d.impedem ? plural(d.impedem, "ponto") + " a resolver" : "Sem alterações pendentes") + "</span>" +
    '<span class="cresce"></span><span>' + (d.impedem ? "Confira antes de sair" : "Pronto para sair") + "</span></div>" +
    '<div class="docs-previa">' + (p.cheia ? "" : '<div class="docs-miniaturas">' + miniaturas + "</div>") +
    '<div class="docs-pv-rolagem"><div class="pv-paginas' + (p.duas ? " duas" : "") + '">' +
    '<img class="docs-pagina" id="pv-img" alt="página ' + p.pagina + '">' +
    (p.duas ? '<img class="docs-pagina" id="pv-img2" alt="página ' + (p.pagina + 1) + '">' : "") +
    "</div></div></div></div>";
}

function painelDaPrevia() {
  const p = escr.previa;
  const d = p.dados;
  const avisos = d.avisos || [];
  const classeGuardar = "ag-toggle" + (escr.guardarAoSair ? " on" : "");
  return '<aside class="acervo-painel" id="docs-painel"><div class="rolagem docs-painel">' + regioesDeFerramenta() +
    '<div class="painel-cabeca"><span class="titulo-painel"><h3>O que fazer agora</h3><span class="meta">Versão ' + d.versao + " · " +
    plural(d.paginas, "página") + " · " + (d.impedem ? plural(d.impedem, "ponto") + " a resolver" : "pronto para sair") + "</span></span></div>" +
    '<div class="painel-acoes"><button class="primario" id="pv-pdf">' + ic("picture_as_pdf", 16) + "Baixar PDF</button>" +
    '<button id="pv-docx">' + ic("description", 16) + "Baixar DOCX</button>" +
    '<button id="pv-assinar-2">' + ic("draw", 16) + "Assinar</button>" +
    '<button id="pv-email">' + ic("mail", 16) + "Enviar por e-mail</button>" +
    '<button class="adiante" data-pv-adiante="WhatsApp">' + ic("chat", 16) + "WhatsApp</button>" +
    '<button id="pv-imprimir">' + ic("print", 16) + "Imprimir</button></div>" +
    '<div class="docs-toggles"><div class="' + classeGuardar + '" data-pv-guardar="1"><span>Guardar no Acervo ao sair</span><i></i></div>' +
    '<div class="ag-toggle' + (escr.senhaPdf ? " on" : "") + '" data-pv-senha="1"><span>Proteger o PDF com senha</span><i></i></div>' +
    (escr.senhaPdf
      ? '<p class="docs-nota-senha">O PDF vai pedir senha para abrir — inclusive o que for anexado no e-mail. ' +
        'Guarde a senha: sem ela nem você abre, e um PDF com senha não entra na busca do Acervo. ' +
        '<button class="docs-ligacao" data-pv-senha-trocar="1">trocar a senha</button></p>'
      : "") + "</div>" +

    '<div class="painel-bloco"><div class="painel-bloco-cabeca"><span>Confira antes de sair</span>' +
    '<span class="contagem">' + (avisos.length ? '<span class="ag-acc">' + plural(avisos.length, "aviso") + "</span>" : "nada a apontar") + "</span></div>" +
    (avisos.length
      ? avisos.map((a) => {
          const classe = "docs-aviso " + (a.grau === "impede" ? "impede" : "confira");
          return '<div class="' + classe + '"><i></i><span><b>' + esc(a.titulo) + "</b><small>" + esc(a.detalhe || "") + "</small></span></div>";
        }).join("")
      : '<div class="docs-aviso ok"><i></i><span><b>Não achei lacuna de modelo, CPF ou CNPJ com dígito errado, nem valor sem número.</b></span></div>') +
    '<div class="docs-aviso-acoes"><button class="docs-ligacao" data-pv-editor="1">Corrigir no editor</button>' +
    '<button class="primario" data-pv-sair="1">Sair assim mesmo</button></div></div>' +

    '<div class="painel-bloco"><div class="painel-bloco-cabeca"><span>Versões</span><span class="contagem">' + (escr.versoes || []).length + "</span></div>" +
    ((escr.versoes || []).length
      ? '<div class="docs-versoes">' + escr.versoes.slice().reverse().slice(0, 12).map((v) => {
          const classe = "docs-versao" + (v.numero === d.versao ? " atual" : "");
          return '<div class="' + classe + '" data-pv-versao="' + v.numero + '" title="Comparar com a atual"><b>v' + v.numero + "</b><span>" +
            esc(v.nota || (v.numero === d.versao ? "a versão de agora" : "sem nota")) + "</span><small>" + esc(quandoCurto(v.criada_em)) + "</small></div>";
        }).join("") + "</div>"
      : "<p>Só a versão de agora.</p>") + "</div>" +
    "</div></aside>";
}

function ligarPrevia() {
  const p = escr.previa;
  const passo = p.duas ? 2 : 1;
  const raiz = $("docs");
  const ligar = (id, acao) => { const b = $(id); if (b) b.onclick = acao; };

  ligar("pv-antes", () => { if (p.pagina > 1) { p.pagina = Math.max(1, p.pagina - passo); carregarPaginaPrevia(); } });
  ligar("pv-depois", () => {
    if (p.pagina < p.dados.paginas) { p.pagina = Math.min(p.dados.paginas, p.pagina + passo); carregarPaginaPrevia(); }
  });
  raiz.querySelectorAll("[data-pv-pagina]").forEach((b) => {
    b.onclick = () => { p.pagina = Number(b.dataset.pvPagina); carregarPaginaPrevia(); };
  });
  ligar("pv-duas", () => { p.duas = !p.duas; desenharDocumentos(); });
  ligar("pv-cheia", () => { p.cheia = !p.cheia; desenharDocumentos(); });
  /* Imprimir é o PDF de verdade indo para a impressora, não a tela impressa:
     o que sai do papel tem que ser o mesmo arquivo que vai para o cliente. */
  ligar("pv-imprimir", () => abrirImprimir(p.id, (abaAtual() || {}).titulo, p.pagina, p.dados.paginas));
  const comparar = () => { if (p.cheia) { p.cheia = false; desenharDocumentos(); } compararVersoes(); };
  ligar("pv-comparar", comparar);
  ligar("pv-comparar-b", comparar);
  raiz.querySelectorAll("[data-pv-versao]").forEach((l) => {
    l.onclick = () => compararComVersao(Number(l.dataset.pvVersao));
  });

  ligar("pv-pdf", async () => {
    if (!escr.senhaPdf) { window.location.href = "/api/documentos/" + p.id + "/pdf"; return; }
    // Com senha o arquivo vem por POST (senha nao mora em endereco), entao o
    // download e feito aqui, a partir do que voltou.
    const r = await fetch("/api/documentos/" + p.id + "/pdf", {
      method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ senha: escr.senhaPdf }),
    });
    if (!r.ok) { avisoCert(await erroDe(r), { tom: "erro" }); return; }
    const bin = await r.blob();
    const a = document.createElement("a");
    a.href = URL.createObjectURL(bin);
    a.download = (escr.doc && escr.doc.titulo ? escr.doc.titulo : "documento") + ".pdf";
    a.click();
    setTimeout(() => URL.revokeObjectURL(a.href), 2000);
    avisoCert("PDF baixado com senha", { tom: "ok" });
  });
  ligar("pv-docx", () => { window.location.href = "/api/documentos/" + p.id + "/docx"; });
  const assinar = async () => {
    const alvo = await guardarNaBiblioteca(p.id);
    if (alvo) { marcarDestino("assinar"); mostrarAssinar(alvo); }
  };
  ligar("pv-assinar", assinar);
  ligar("pv-assinar-2", assinar);
  ligar("pv-email", async () => {
    const alvo = await guardarNaBiblioteca(p.id, escr.senhaPdf);
    if (!alvo) return;
    if (!mail.contas) {
      try { mail.contas = await (await fetch("/api/email/contas")).json(); } catch (err) { mail.contas = null; }
    }
    if (!mail.contas || !mail.contas.contas.length) { marcarDestino("caixa"); return mostrarEmail(); }
    mail.conta = mail.contas.contas.find((c) => c.em_uso) || mail.contas.contas[0];
    marcarDestino("caixa");
    telaEscrever({ assunto: escr.doc.titulo, corpo: "" });
    mail.anexos = [{ path: alvo, nome: alvo.split(/[\\/]/).pop() }];
    desenharAnexos();
  });
  const pedirSenhaPdf = async () => {
    const senha = await perguntar({
      titulo: "Senha do PDF",
      contexto: "Editor › " + (escr.doc ? escr.doc.titulo : "documento"),
      texto: "Quem receber o arquivo vai precisar dela para abrir. Guarde: sem a senha nem " +
        "você abre depois, e um PDF com senha não entra na busca do Acervo.",
      campo: { rotulo: "Senha", tipo: "password", placeholder: "a senha que abre o PDF", obrigatorio: true },
      confirmar: "Proteger",
    });
    if (!senha) return false;
    escr.senhaPdf = senha;
    desenharDocumentos();
    avisoCert("o PDF vai sair protegido — a senha fica só nesta tela", { tom: "ok" });
    return true;
  };
  const chaveSenha = raiz.querySelector("[data-pv-senha]");
  if (chaveSenha) chaveSenha.onclick = async () => {
    if (escr.senhaPdf) { escr.senhaPdf = ""; desenharDocumentos(); return; }
    await pedirSenhaPdf();
  };
  const trocarSenha = raiz.querySelector("[data-pv-senha-trocar]");
  if (trocarSenha) trocarSenha.onclick = pedirSenhaPdf;
  raiz.querySelectorAll("[data-pv-adiante]").forEach((b) => {
    b.onclick = () => avisoCert(b.dataset.pvAdiante + " ainda não tem motor nesta máquina — por enquanto, e-mail e PDF");
  });
  const guardar = raiz.querySelector("[data-pv-guardar]");
  if (guardar) guardar.onclick = () => { escr.guardarAoSair = !escr.guardarAoSair; guardar.classList.toggle("on", escr.guardarAoSair); };
  const editor = raiz.querySelector("[data-pv-editor]");
  if (editor) editor.onclick = () => { escr.visao = "editor"; mostrarDocumentos(); };
  const sair = raiz.querySelector("[data-pv-sair]");
  if (sair) sair.onclick = () => fecharDocumento(p.id);

  carregarPaginaPrevia();
}

/* A versao escolhida contra a de agora: a lista do que mudou no texto. */
async function compararComVersao(numero) {
  const p = escr.previa;
  const alvo = $("pv-abaixo");
  if (!alvo) return;
  alvo.innerHTML = '<div class="painel"><p class="nota">comparando…</p></div>';
  const r = await fetch("/api/documentos/" + p.id + "/comparar?de=" + numero);
  if (!r.ok) { alvo.innerHTML = '<div class="painel"><p class="explica">' + esc(await erroDe(r)) + "</p></div>"; return; }
  const c = await r.json();
  alvo.innerHTML = '<div class="painel"><h3>v' + c.de + " comparada com a v" + c.ate + "</h3>" +
    (c.mudancas.length
      ? c.mudancas.map((m) =>
          '<div class="pv-mudanca">' +
          (m.antes ? '<div class="saiu">' + esc(m.antes) + "</div>" : "") +
          (m.depois ? '<div class="entrou">' + esc(m.depois) + "</div>" : "") + "</div>").join("")
      : '<p class="explica">Nada mudou no texto entre essas versões.</p>') +
    '<div class="linha-form"><button data-pv-voltar="' + c.de + '">Voltar para a v' + c.de + "</button>" +
    '<button data-doc-fechar-ferramenta="1">Fechar</button></div></div>';
  alvo.querySelector("[data-doc-fechar-ferramenta]").onclick = () => { alvo.innerHTML = ""; };
  alvo.querySelector("[data-pv-voltar]").onclick = async () => {
    if (!(await confirmar({ titulo: "Voltar para a v" + c.de + "?", contexto: "Editor › Versões", texto: "Isso cria uma versão nova com aquele conteúdo. Nada é perdido: as versões seguintes continuam no histórico.", confirmar: "Voltar para a v" + c.de }))) return;
    const r2 = await (await fetch("/api/documentos/" + p.id + "/restaurar", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ numero: c.de }),
    })).json();
    escr.doc = r2.documento;
    mostrarDocumentos();
  };
  alvo.scrollIntoView({ behavior: "smooth", block: "start" });
}

/* Ctrl+Shift+S: assina o documento que esta aberto. Guarda o PDF na
   biblioteca antes, porque e o arquivo que a assinatura assina. */
async function assinarDocumentoAberto() {
  const id = (escr.doc && escr.doc.id) || escr.atual;
  if (!id) { avisoCert("abra um documento para assinar"); return; }
  const alvo = await guardarNaBiblioteca(id);
  if (!alvo) return;
  marcarDestino("assinar");
  mostrarAssinar(alvo);
}

async function guardarNaBiblioteca(id, senha) {
  const r = await fetch("/api/documentos/" + id + "/biblioteca", {
    method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify(senha ? { senha: senha } : {}),
  });
  if (!r.ok) { avisoCert(await erroDe(r)); return ""; }
  const d = await r.json();
  estado.contratos = d.documentos;
  avisoCert("guardado na biblioteca como " + d.guardado);
  return d.caminho;
}

function carregarPaginaPrevia() {
  const p = escr.previa;
  const largura = p.cheia ? 1300 : (p.duas ? 640 : 900);
  $("pv-num").textContent = p.pagina;
  $("pv-img").src = "/api/documentos/" + p.id + "/pagina?numero=" + p.pagina +
    "&largura=" + largura + "&t=" + Date.now();
  const segunda = $("pv-img2");
  if (segunda) {
    // A última página ímpar fica sozinha: melhor um vão do que repetir a
    // mesma folha dos dois lados.
    if (p.pagina + 1 <= p.dados.paginas) {
      segunda.src = "/api/documentos/" + p.id + "/pagina?numero=" + (p.pagina + 1) +
        "&largura=" + largura + "&t=" + Date.now();
      segunda.hidden = false;
    } else {
      segunda.hidden = true;
    }
  }
  const status = document.querySelector(".docs-cartao.previa .docs-status > span");
  if (status) status.textContent = "Página " + p.pagina + " de " + p.dados.paginas;
  document.querySelectorAll("[data-pv-pagina]").forEach((b) => {
    const n = Number(b.dataset.pvPagina);
    b.classList.toggle("atual", n === p.pagina || (p.duas && n === p.pagina + 1));
  });
}

/* Comparar duas versões é ver as duas páginas lado a lado E a lista do que
   mudou no texto. Só a lista não mostra como ficou; só as páginas não dizem
   o que procurar. */
async function compararVersoes() {
  const p = escr.previa;
  const r = await fetch("/api/documentos/" + p.id + "/comparar");
  if (!r.ok) { avisoCert(await erroDe(r)); return; }
  const d = await r.json();

  const caixa = document.createElement("div");
  caixa.className = "painel";
  caixa.style.marginTop = "16px";
  caixa.innerHTML = "<h3>Versão " + d.de + " → versão " + d.ate + "</h3>" +
    (d.mudancas.length
      ? '<div class="comparar">' + d.mudancas.map((m) =>
          '<div class="comparar-linha ' + esc(m.tipo) + '">' +
          '<span class="rotulo">' + esc(m.tipo) + "</span>" +
          "<span>" +
          (m.tipo === "mudou"
            ? esc(m.antes) + '<br><span class="comparar-depois">' + esc(m.depois) + "</span>"
            : esc(m.depois || m.antes)) +
          "</span></div>").join("") + "</div>"
      : '<p class="explica">Nada mudou no texto entre essas duas versões — ' +
        "pode ter sido só formatação.</p>") +
    '<div class="comparar-folhas">' +
    '<div><span class="rotulo">versão ' + d.de + "</span>" +
    '<img src="/api/documentos/' + p.id + "/pagina?numero=" + p.pagina +
    '&largura=520&versao=' + d.de + '" alt="versão ' + d.de + '"></div>' +
    '<div><span class="rotulo">versão ' + d.ate + " · agora</span>" +
    '<img src="/api/documentos/' + p.id + "/pagina?numero=" + p.pagina +
    '&largura=520" alt="versão ' + d.ate + '"></div></div>' +
    '<div class="linha-form"><button id="pv-fechar-comp">Fechar</button></div>';

  const abaixo = $("pv-abaixo");
  abaixo.innerHTML = "";
  abaixo.appendChild(caixa);
  caixa.scrollIntoView({ behavior: "smooth", block: "start" });
  $("pv-fechar-comp").onclick = () => { abaixo.innerHTML = ""; };
}

/* -------------------------------------------------------- C3: planilha */

function desenharPlanilha() { desenharDocumentos(); }

function barrasDaPlanilha() {
  const p = escr.pl;
  const aba = p.abas[escr.aba];
  const cel = aba.celulas[escr.celula] || {};
  const classeCongelar = "com-texto" + (aba.congelar_cabecalho ? " on" : "");
  const classeNegrito = cel.negrito ? "on" : "";
  const classeItalico = cel.italico ? "on" : "";
  return '<div class="docs-barra">' +
    '<select class="docs-sel" id="pl-formato" title="Formato da célula">' +
    p.formatos.map((f) => '<option value="' + esc(f.valor) + '"' + ((cel.formato || "") === f.valor ? " selected" : "") + ">" + esc(f.rotulo) + "</option>").join("") + "</select>" +
    [["moeda", "R$"], ["porcento", "%"], ["numero", "0,00"], ["data", "DATA"]].map(([v, r]) =>
      '<button class="docs-chip" data-pl-formato="' + v + '">' + r + "</button>").join("") +
    '<span class="divisa-v"></span>' +
    '<button class="' + classeNegrito + '" id="pl-negrito" title="Negrito">' + ic("format_bold", 18) + "</button>" +
    '<button class="' + classeItalico + '" id="pl-italico" title="Itálico">' + ic("format_italic", 18) + "</button>" +
    '<span class="divisa-v"></span>' +
    '<button class="com-texto" id="pl-juntar">' + ic("cell_merge", 16) + "Mesclar</button>" +
    '<button class="com-texto" id="pl-borda">' + ic("border_all", 16) + "Bordas</button>" +
    '<button class="' + classeCongelar + '" id="pl-congelar">' + ic("ac_unit", 16) + "Congelar</button>" +
    '<span class="divisa-v"></span>' +
    '<button class="com-texto" id="pl-filtrar">' + ic("filter_list", 16) + "Filtrar</button>" +
    '<button class="com-texto" id="pl-ordenar">' + ic("swap_vert", 16) + "Ordenar</button>" +
    '<button class="com-texto" id="pl-funcoes">Fórmulas' + ic("expand_more", 16) + "</button>" +
    '<button class="com-texto" id="pl-grafico">Gráfico' + ic("expand_more", 16) + "</button>" +
    '<button class="com-texto" id="pl-limpar" title="Limpar a célula">' + ic("delete", 16) + "Limpar</button>" +
    "</div>" +
    '<div class="docs-barra fx">' +
    '<span class="docs-ref" id="pl-ref">' + esc(faixaAtual()) + '</span><span class="docs-fx">fx</span>' +
    '<input type="text" class="docs-fx-entrada" id="pl-entrada" value="' + esc(valorCru(aba, escr.celula)) + '" placeholder="valor ou =fórmula">' +
    '<span class="docs-fx-nota" id="pl-nota">' + esc(escr.notaFormula || "") + "</span></div>";
}

function cartaoDaPlanilha() {
  const p = escr.pl;
  const aba = p.abas[escr.aba];
  const calc = p.calculado[escr.aba];
  const res = p.resumos[escr.aba] || {};
  return '<div class="docs-cartao">' + gradePlanilha(aba, calc) +
    (escr.filtro
      ? '<div class="docs-filtro-aviso">Filtro na coluna ' + esc(escr.filtro.coluna) + ": mostrando " + escr.filtro.mostrando +
        " de " + plural(escr.filtro.de, "linha") + '. O arquivo continua inteiro. <button class="docs-ligacao" id="pl-filtro-fora">Mostrar tudo</button></div>'
      : "") +
    '<div class="docs-abas-pl">' +
    p.abas.map((a, i) => {
      const classe = "docs-aba-pl" + (i === escr.aba ? " ativa" : "");
      return '<button class="' + classe + '" data-aba="' + i + '">' + esc(a.nome) + "</button>";
    }).join("") +
    '<button class="docs-aba-pl-mais" id="pl-nova-aba" title="Nova aba">' + ic("add", 16) + "</button>" +
    (p.abas.length > 1 ? '<button class="docs-ligacao" id="pl-tirar-aba">apagar aba</button>' : "") +
    '<span class="docs-selecao" id="pl-selecao"></span>' +
    '<span class="docs-nota-direita">' + plural(aba.linhas, "linha") + " · " + (res.erros ? plural(res.erros, "erro") : "cálculos em dia") + "</span></div></div>";
}

function painelDaPlanilha() {
  return '<aside class="acervo-painel" id="docs-painel"><div class="rolagem docs-painel">' + regioesDeFerramenta() +
    '<div class="docs-painel-cabeca">' + coroa(18) + '<span class="cresce">Pedir aqui</span><span>sobre a planilha</span></div>' +
    '<div class="docs-conversa" id="pl-fala">' + falasDoDocumento(conversaAtual()) + "</div>" +
    '<div class="painel-bloco"><div class="painel-bloco-cabeca"><span>O que eu posso fazer</span></div><div class="docs-acoes-lista">' +
    '<button data-pl-trazer="financeiro"><span>Importar os honorários do Financeiro</span>' + ic("chevron_right", 16) + "</button>" +
    '<button data-pl-trazer="prazos"><span>Criar aba com os prazos do Acervo</span>' + ic("chevron_right", 16) + "</button>" +
    '<button data-pl-grafico="1"><span>Montar gráfico da seleção</span>' + ic("chevron_right", 16) + "</button></div></div>" +
    '<div class="docs-pedido"><div class="docs-pedido-linha"><input type="text" id="pl-pedido" placeholder="Descreva o cálculo em português…">' +
    '<button class="enviar" id="pl-pedir" aria-label="Enviar">' + ic("arrow_forward", 18) + "</button></div>" +
    "<small>A fórmula aparece na barra fx antes de ser aplicada.</small></div>" +
    "</div></aside>";
}

/* Traz para uma aba nova o que o programa ja tem: os honorarios lancados no
   Financeiro ou os prazos lidos nos documentos do Acervo. Aba nova sempre -
   escrever por cima do que a pessoa digitou nao se desfaz. */
async function trazerParaPlanilha(de, botao) {
  const p = escr.pl;
  if (!p) return;
  let mes = "";
  if (de === "financeiro") {
    const escolha = await dialogo({
      titulo: "Trazer os honorários",
      contexto: "Planilha › " + (escr.doc ? escr.doc.titulo : ""),
      texto: "Entra uma aba nova com cliente, descrição, vencimento, valor e situação — " +
        "mais a linha de total. A planilha fica como uma fotografia de hoje; o que está " +
        "no Financeiro continua sendo o original.",
      campo: { rotulo: "Mês", valor: "", placeholder: "AAAA-MM · vazio traz todos", dica: "deixe em branco para trazer tudo" },
      confirmar: "Trazer",
    });
    if (!escolha || !escolha.ok) return;
    mes = (escolha.valor || "").trim();
    if (mes && !/^\d{4}-\d{2}$/.test(mes)) { avisoCert("o mês se escreve como 2026-09", { tom: "erro" }); return; }
  }
  if (botao) botao.disabled = true;
  const r = await fetch("/api/planilha/" + p.id + "/trazer", {
    method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ de: de, mes: mes, categoria: "honorarios" }),
  });
  if (botao) botao.disabled = false;
  if (!r.ok) { avisoCert(await erroDe(r), { tom: "erro" }); return; }
  const d = await r.json();
  escr.pl = d;
  escr.aba = d.aba_nova;
  escr.celula = "A1";
  desenharDocumentos();
  avisoCert(d.aviso, { tom: "ok" });
}

function gradePlanilha(aba, calc) {
  // A grade que cresce com a rolagem, com medidas e alca: 26-planilha-excel.js.
  if (typeof plxGrade === "function") return plxGrade(aba, calc);
  const escondidas = escr.filtro ? new Set(escr.filtro.esconder) : null;
  let html = '<div class="pl-caixa' + (aba.congelar_cabecalho ? " congelada" : "") +
    '"><table class="pl-grade"><thead><tr><th class="canto"></th>';
  for (let c = 0; c < aba.colunas; c++) {
    html += '<th data-coluna="' + letraColuna(c) + '">' + letraColuna(c) + "</th>";
  }
  html += "</tr></thead><tbody>";

  for (let l = 1; l <= aba.linhas; l++) {
    if (escondidas && escondidas.has(l)) continue;
    html += '<tr><td class="cabeca-linha" data-linha="' + l + '">' + l + "</td>";
    let pulando = 0;
    for (let c = 0; c < aba.colunas; c++) {
      const ref = letraColuna(c) + l;
      if (pulando > 0) { pulando -= 1; continue; }
      const v = calc[ref];
      const cel = aba.celulas[ref];
      const juntar = cel && cel.juntar > 1 ? Math.min(cel.juntar, aba.colunas - c) : 1;
      pulando = juntar - 1;
      const classes = ["pl-cel"];
      if (ref === escr.celula) classes.push("escolhida");
      if (v) {
        if (v.erro) classes.push("ruim");
        else if (typeof v.bruto === "number") classes.push("numero");
        if (v.formula) classes.push("formula");
      }
      if (cel && cel.negrito) classes.push("forte");
      if (cel && cel.italico) classes.push("inclinada");
      if (cel && cel.borda) classes.push("com-borda");
      html += '<td class="' + classes.join(" ") + '" data-ref="' + ref + '"' +
        (juntar > 1 ? ' colspan="' + juntar + '"' : "") + ">" +
        (v ? esc(v.texto) : "") + "</td>";
    }
    html += "</tr>";
  }
  return html + "</tbody></table></div>";
}

function letraColuna(i) {
  let nome = "";
  i += 1;
  while (i) { const r = (i - 1) % 26; nome = String.fromCharCode(65 + r) + nome; i = Math.floor((i - 1) / 26); }
  return nome;
}

function valorCru(aba, ref) {
  const c = aba.celulas[ref];
  return c ? c.valor : "";
}

function moedaBR(n) {
  return (Number(n) || 0).toLocaleString("pt-BR", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}

function ligarPlanilha() {
  const p = escr.pl;
  const aba = p.abas[escr.aba];
  const raiz = $("docs");

  /* Selecionar (arrastar, Shift, cabeçalhos), menu do botão direito, medidas,
     alça de preencher e teclado moram em 26-planilha-excel.js — ligados
     no fim desta função, por cima do que ela liga. */
  raiz.querySelectorAll("[data-aba]").forEach((b) => {
    b.onclick = () => { escr.aba = Number(b.dataset.aba); escr.celula = "A1"; escr.ancora = null; desenharPlanilha(); };
  });

  const entrada = $("pl-entrada");
  entrada.onkeydown = (e) => {
    if (e.key === "Enter") { gravarCelula(entrada.value); e.preventDefault(); }
    if (e.key === "Escape") { entrada.value = valorCru(aba, escr.celula); entrada.blur(); }
  };

  $("pl-formato").onchange = (e) => aplicarNaFaixa({ formato: e.target.value });
  raiz.querySelectorAll("[data-pl-formato]").forEach((b) => { b.onclick = () => aplicarNaFaixa({ formato: b.dataset.plFormato }); });
  $("pl-negrito").onclick = () => aplicarNaFaixa({ negrito: !((aba.celulas[escr.celula] || {}).negrito) });
  $("pl-italico").onclick = () => aplicarNaFaixa({ italico: !((aba.celulas[escr.celula] || {}).italico) });
  $("pl-limpar").onclick = () => aplicarNaFaixa({ valor: "" });

  $("pl-xlsx").onclick = () => { window.location.href = "/api/planilha/" + p.id + "/exportar?formato=xlsx"; };

  const campo = $("pl-arquivo");
  $("pl-importar-b").onclick = () => campo.click();
  campo.onchange = async () => {
    if (!campo.files[0]) return;
    const forma = new FormData();
    forma.append("arquivo", campo.files[0]);
    const r = await fetch("/api/planilha/" + p.id + "/importar", { method: "POST", body: forma });
    if (!r.ok) { avisoCert(await erroDe(r)); return; }
    escr.pl = await r.json();
    escr.aba = escr.pl.abas.length - 1;
    desenharPlanilha();
  };

  $("pl-guardar").onclick = async () => {
    const r = await fetch("/api/documentos/" + p.id + "/biblioteca", {
      method: "POST", headers: { "Content-Type": "application/json" }, body: "{}",
    });
    if (!r.ok) { avisoCert(await erroDe(r)); return; }
    const d = await r.json();
    avisoCert("guardada no Acervo como " + d.guardado);
  };

  $("pl-nova-aba").onclick = async () => {
    const nome = await perguntar({ titulo: "Nova aba", contexto: "Planilha › " + (p.titulo || "sem título"), campo: { rotulo: "Nome da aba", valor: "Página " + (p.abas.length + 1), icone: "table" }, confirmar: "Criar" });
    if (!nome) return;
    const r = await fetch("/api/planilha/" + p.id + "/aba", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ nome: nome }),
    });
    if (!r.ok) { avisoCert(await erroDe(r)); return; }
    escr.pl = await r.json();
    escr.aba = escr.pl.abas.length - 1;
    desenharPlanilha();
  };
  const tirar = $("pl-tirar-aba");
  if (tirar) tirar.onclick = async () => {
    if (!(await confirmar({ titulo: "Apagar esta aba?", contexto: "Planilha › " + aba.nome, texto: "Tudo que está nela vai junto. Não dá para desfazer.", confirmar: "Apagar", perigo: true }))) return;
    const r = await fetch("/api/planilha/" + p.id + "/aba/" + escr.aba, { method: "DELETE" });
    if (!r.ok) { avisoCert(await erroDe(r)); return; }
    escr.pl = await r.json();
    escr.aba = 0;
    desenharPlanilha();
  };

  $("pl-funcoes").onclick = () => {
    $("pl-abaixo").innerHTML = '<div class="painel"><h3>Fórmulas</h3>' +
      '<p class="explica">Ponto e vírgula separa argumento; vírgula é o decimal — como no ' +
      "Excel em português.</p>" +
      p.funcoes.map((f) =>
        '<div class="pl-funcao"><b>' + esc(f.nome) + "</b><code>" + esc(f.exemplo) + "</code>" +
        '<span class="explica">' + esc(f.explica) + "</span></div>").join("") +
      '<div class="linha-form"><button data-doc-fechar-ferramenta="1">Fechar</button></div></div>';
    $("pl-abaixo").querySelector("[data-doc-fechar-ferramenta]").onclick = () => { $("pl-abaixo").innerHTML = ""; };
  };

  $("pl-borda").onclick = () => {
    const cel = aba.celulas[escr.celula] || {};
    aplicarNaFaixa({ borda: !cel.borda });
  };
  $("pl-congelar").onclick = async () => {
    const r = await fetch("/api/planilha/" + p.id + "/congelar", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ aba: escr.aba, congelar: !aba.congelar_cabecalho }),
    });
    if (!r.ok) { avisoCert(await erroDe(r)); return; }
    escr.pl = await r.json();
    desenharPlanilha();
  };
  $("pl-ordenar").onclick = () => painelTabela("ordenar");
  $("pl-filtrar").onclick = () => painelTabela("filtrar");
  $("pl-grafico").onclick = desenharGrafico;
  $("pl-juntar").onclick = juntarCelulas;
  // O aviso de filtro fica na tela o tempo todo: linha escondida que a pessoa
  // esqueceu e uma tabela de parcelas com linhas faltando.
  const fora = $("pl-filtro-fora");
  if (fora) fora.onclick = () => { escr.filtro = null; desenharPlanilha(); };

  raiz.querySelectorAll("[data-pl-trazer]").forEach((b) => {
    b.onclick = () => trazerParaPlanilha(b.dataset.plTrazer, b);
  });
  raiz.querySelectorAll("[data-pl-grafico]").forEach((b) => { b.onclick = desenharGrafico; });

  const pedir = () => { const c = $("pl-pedido"); const t = c.value.trim(); c.value = ""; pedirFormula(t); };
  $("pl-pedir").onclick = pedir;
  $("pl-pedido").onkeydown = (e) => { if (e.key === "Enter") pedir(); };
  ligarFalas($("pl-fala"), conversaAtual());
  if (typeof plxLigar === "function") plxLigar(raiz, aba);
  pintarSelecao();
  mostrarSelecao();
}

/* Negrito, itálico, borda e formato valem para a seleção inteira. Uma célula
   de cada vez obriga a repetir o clique por linha — e numa tabela de parcelas
   ninguém faz isso, simplesmente deixa sem. */
async function aplicarNaFaixa(dados) {
  const faixa = faixaAtual();
  if (!faixa.includes(":")) return gravarCelula(null, dados);

  const r = await fetch("/api/planilha/" + escr.pl.id + "/faixa", {
    method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ aba: escr.aba, faixa: faixa, ...dados }),
  });
  if (!r.ok) { avisoCert(await erroDe(r)); return; }
  escr.pl = await r.json();
  desenharPlanilha();
}

/* ------------------------------------------------------------- o gráfico

   Barra, e não linha nem pizza: a pergunta que se faz a uma coluna de valores
   é "qual é o maior e como os outros se comparam", e barra responde isso sem
   ninguém precisar interpretar. Desenhado aqui mesmo, com CSS — o programa
   roda sem internet e não vai buscar biblioteca de gráfico em CDN. */

async function desenharGrafico() {
  const faixa = faixaAtual();
  const alvo = $("pl-abaixo");
  if (!faixa.includes(":")) {
    alvo.innerHTML = '<div class="painel" style="margin-top:14px"><h3>Gráfico</h3>' +
      '<p class="explica">Selecione antes a coluna de valores — e, se quiser rótulos, ' +
      "a coluna de texto ao lado dela junto.</p></div>";
    return;
  }

  alvo.innerHTML = '<div class="painel" style="margin-top:14px"><p class="nota">lendo…</p></div>';
  const r = await fetch("/api/planilha/" + escr.pl.id + "/grafico", {
    method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ aba: escr.aba, faixa: faixa }),
  });
  if (!r.ok) { alvo.innerHTML = '<div class="painel"><p class="explica">' +
    esc(await erroDe(r)) + "</p></div>"; return; }
  const d = await r.json();

  if (!d.pode) {
    /* Gráfico de nada é pior que gráfico nenhum: parece um resultado. */
    alvo.innerHTML = '<div class="painel" style="margin-top:14px"><h3>Gráfico</h3>' +
      '<p class="explica">' + esc(d.porque) + ".</p></div>";
    return;
  }

  const teto = Math.max(Math.abs(d.maior), Math.abs(d.menor), 1);
  alvo.innerHTML = '<div class="painel" style="margin-top:14px"><h3>Gráfico de ' +
    esc(faixa) + "</h3>" +
    '<p class="explica">Valores da coluna ' + esc(d.coluna_valores) +
    (d.coluna_rotulos ? ", rótulos da coluna " + esc(d.coluna_rotulos) : ", sem coluna de rótulo") +
    " · " + plural(d.pontos.length, "valor", "valores") + " · soma " + moedaBR(d.soma) + "</p>" +
    '<div class="pl-grafico">' + d.pontos.map((p) =>
      '<div class="pl-gbarra"><i style="height:' +
      Math.max(1, Math.round(Math.abs(p.valor) * 100 / teto)) + '%"' +
      (p.valor < 0 ? ' class="negativo"' : "") + ' title="' + esc(p.texto) + '"></i>' +
      '<span class="rotulo corta">' + esc(p.rotulo) + "</span></div>").join("") + "</div>" +
    '<div class="pl-status"><span>maior ' + moedaBR(d.maior) + "</span>" +
    "<span>menor " + moedaBR(d.menor) + "</span></div>" +
    '<div class="linha-form"><button id="pl-graf-fechar">Fechar</button></div></div>';

  $("pl-graf-fechar").onclick = () => { alvo.innerHTML = ""; };
}

/* ----------------------------------------------------------- juntar células

   O Excel junta e joga fora o que estava debaixo, avisando numa caixa que todo
   mundo clica em OK sem ler — e ali some um valor que ninguém mais procura.
   Aqui o que tem conteúdo não é coberto. */

async function juntarCelulas() {
  const faixa = faixaAtual();
  const aba = escr.pl.abas[escr.aba];
  const primeira = aba.celulas[faixa.split(":")[0]];
  const separar = Boolean(primeira && primeira.juntar > 1);

  if (!separar && !faixa.includes(":")) {
    avisoCert("selecione pelo menos duas células lado a lado");
    return;
  }

  const r = await fetch("/api/planilha/" + escr.pl.id + "/mesclar", {
    method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ aba: escr.aba, faixa: faixa, separar: separar }),
  });
  if (!r.ok) { avisoCert(await erroDe(r)); return; }
  escr.pl = await r.json();
  desenharPlanilha();
}

/* ------------------------------------------------------ ordenar e filtrar

   As duas perguntas que se faz a uma tabela de parcelas: "quem deve mais?" e
   "o que ainda está em aberto?". Uma reordena o documento e a outra só muda o
   jeito de olhar — e a tela diz qual é qual, porque a diferença importa. */

function painelTabela(acao, memoria) {
  const lembra = memoria || {};
  const faixa = lembra.faixa || faixaAtual();
  const alvo = $("pl-abaixo");
  if (!faixa.includes(":")) {
    alvo.innerHTML = '<div class="painel" style="margin-top:14px">' +
      "<h3>" + (acao === "ordenar" ? "Ordenar" : "Filtrar") + "</h3>" +
      '<p class="explica">Selecione antes a tabela inteira — arrastando, ou clicando na ' +
      "letra da coluna. Com uma célula só não dá para saber que linhas andam juntas, e " +
      "ordenar a coluna errada embaralha a tabela sem deixar marca.</p></div>";
    return;
  }

  const letras = [];
  const m = /^([A-Z]{1,2})\d+:([A-Z]{1,2})\d+$/.exec(faixa);
  if (m) {
    for (let c = letraParaIndice(m[1]); c <= letraParaIndice(m[2]); c += 1) {
      letras.push(letraColuna(c));
    }
  }

  const colunas = '<select id="pl-tab-coluna">' +
    letras.map((l) => '<option value="' + l + '"' +
      (l === lembra.coluna ? " selected" : "") + ">coluna " + l + "</option>").join("") +
    "</select>";

  alvo.innerHTML = '<div class="painel" style="margin-top:14px">' +
    "<h3>" + (acao === "ordenar" ? "Ordenar " : "Filtrar ") + esc(faixa) + "</h3>" +
    (acao === "ordenar"
      ? '<p class="explica">A linha inteira anda junto, e a fórmula vai com a linha dela: ' +
        "=B7*0,1 na linha 7 vira =B9*0,1 quando a linha 7 for para a 9. " +
        "Isto muda o documento e cria uma versão — dá para voltar no Histórico.</p>" +
        '<div class="linha-form">' + colunas +
        '<select id="pl-tab-ordem"><option value="1">crescente</option>' +
        '<option value="0">decrescente</option></select>' +
        '<label class="pl-check"><input type="checkbox" id="pl-tab-cabecalho" checked> ' +
        "a primeira linha é cabeçalho</label></div>" +
        '<div class="linha-form"><button class="primario" id="pl-tab-fazer">Ordenar</button>' +
        '<button id="pl-tab-fechar">Fechar</button></div>'
      : '<p class="explica">Filtro é jeito de olhar: esconde linhas na tela e não mexe no ' +
        "arquivo. Critério igual ao de SOMASE — <code>pago</code>, <code>&gt;1000</code>, " +
        "<code>&lt;&gt;0</code>.</p>" +
        '<div class="linha-form">' + colunas +
        '<input type="text" id="pl-tab-criterio" placeholder="&gt;1000" value="' +
        esc(lembra.criterio || "") + '">' +
        '<label class="pl-check"><input type="checkbox" id="pl-tab-cabecalho" checked> ' +
        "a primeira linha é cabeçalho</label></div>" +
        '<div class="linha-form"><button class="primario" id="pl-tab-fazer">Filtrar</button>' +
        (escr.filtro ? '<button id="pl-tab-limpar">Limpar filtro</button>' : "") +
        '<button id="pl-tab-fechar">Fechar</button></div>') +
    '<p class="explica" id="pl-tab-nota"></p></div>';

  $("pl-tab-fechar").onclick = () => { alvo.innerHTML = ""; };
  const limpar = $("pl-tab-limpar");
  if (limpar) limpar.onclick = () => { escr.filtro = null; desenharPlanilha(); };
  $("pl-tab-fazer").onclick = () => (acao === "ordenar" ? fazerOrdenar(faixa) : fazerFiltrar(faixa));
}

async function fazerOrdenar(faixa) {
  const r = await fetch("/api/planilha/" + escr.pl.id + "/ordenar", {
    method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      aba: escr.aba, faixa: faixa, coluna: $("pl-tab-coluna").value,
      crescente: $("pl-tab-ordem").value === "1",
      com_cabecalho: $("pl-tab-cabecalho").checked,
    }),
  });
  if (!r.ok) { $("pl-tab-nota").textContent = await erroDe(r); return; }
  const d = await r.json();
  escr.pl = d;
  escr.filtro = null;
  desenharPlanilha();
  avisoCert(plural(d.ordenou.linhas, "linha") + " reordenada" +
    (d.ordenou.linhas === 1 ? "" : "s") +
    (d.ordenou.formulas
      ? " · " + plural(d.ordenou.formulas, "fórmula") + " acompanhou a linha"
      : ""));
}

async function fazerFiltrar(faixa) {
  const r = await fetch("/api/planilha/" + escr.pl.id + "/filtrar", {
    method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      aba: escr.aba, faixa: faixa, coluna: $("pl-tab-coluna").value,
      criterio: $("pl-tab-criterio").value,
      com_cabecalho: $("pl-tab-cabecalho").checked,
    }),
  });
  if (!r.ok) { $("pl-tab-nota").textContent = await erroDe(r); return; }
  escr.filtro = await r.json();
  const lembra = {
    faixa: faixa, coluna: $("pl-tab-coluna").value,
    criterio: $("pl-tab-criterio").value,
  };
  // Redesenhar a grade apaga o painel; ele volta com o que estava escolhido.
  // Um painel dizendo "coluna A" enquanto o filtro roda na B e pior que
  // painel nenhum.
  desenharPlanilha();
  painelTabela("filtrar", lembra);
  $("pl-tab-nota").textContent = "mostrando " + escr.filtro.mostrando + " de " +
    plural(escr.filtro.de, "linha") + " · o arquivo continua inteiro";
}

function corpoDaPlanilha() {
  return JSON.stringify({ versao: 1, abas: escr.pl.abas });
}

function escolherCelula(ref, estender) {
  const aba = escr.pl.abas[escr.aba];
  if (estender && escr.celula) {
    escr.ancora = escr.ancora || escr.celula;
  } else {
    escr.ancora = ref;
  }
  escr.celula = ref;

  $("pl-ref").textContent = escr.ancora === ref ? ref : escr.ancora + ":" + ref;
  $("pl-entrada").value = valorCru(aba, ref);
  $("pl-formato").value = (aba.celulas[ref] || {}).formato || "";
  pintarSelecao();
  mostrarSelecao();
}

/* ------------------------------------------------- selecionar um pedaço

   Uma célula de cada vez respondia "quanto é esta?". A pergunta que se faz
   numa tabela de parcelas é outra: "quanto dá esta coluna, e quantas linhas
   tem?". Para isso a seleção precisa ser um retângulo. */

function refsDaFaixa(a, b) {
  const p = (r) => {
    const m = /^([A-Z]{1,2})(\d{1,4})$/.exec(r || "");
    return m ? [Number(m[2]), letraParaIndice(m[1])] : [1, 0];
  };
  const [l1, c1] = p(a);
  const [l2, c2] = p(b);
  const saida = [];
  for (let l = Math.min(l1, l2); l <= Math.max(l1, l2); l += 1) {
    for (let c = Math.min(c1, c2); c <= Math.max(c1, c2); c += 1) {
      saida.push(letraColuna(c) + l);
    }
  }
  return saida;
}

function letraParaIndice(letras) {
  let total = 0;
  for (const c of letras.toUpperCase()) total = total * 26 + (c.charCodeAt(0) - 64);
  return total - 1;
}

function faixaAtual() {
  const a = escr.ancora || escr.celula;
  return a === escr.celula ? escr.celula : a + ":" + escr.celula;
}

function pintarSelecao() {
  // Com moldura, alça e cabeçalhos acesos: 26-planilha-excel.js.
  if (typeof plxPintar === "function") return plxPintar();
  const dentro = new Set(refsDaFaixa(escr.ancora || escr.celula, escr.celula));
  document.querySelectorAll("[data-ref]").forEach((td) => {
    td.classList.toggle("escolhida", td.dataset.ref === escr.celula);
    td.classList.toggle("na-faixa", dentro.has(td.dataset.ref) && td.dataset.ref !== escr.celula);
  });
}

async function mostrarSelecao() {
  const calc = escr.pl.calculado[escr.aba];
  const v = calc[escr.celula];
  const alvo = $("pl-selecao");
  if (!alvo) return;

  const faixa = faixaAtual();
  if (!faixa.includes(":")) {
    alvo.innerHTML = "<span>" + escr.celula + "</span>" +
      (v && v.formula ? "<span>" + esc(v.formula) + "</span>" : "") +
      (v && typeof v.bruto === "number" ? "<span>valor " + moedaBR(v.bruto) + "</span>" : "") +
      (v && v.erro ? "<span>a fórmula não fechou</span>" : "");
    return;
  }

  /* Quem soma é a planilha, não a tela: uma soma feita aqui em JavaScript e
     outra lá nas fórmulas é a promessa de duas respostas para a mesma
     coluna. */
  alvo.innerHTML = "<span>" + esc(faixa) + "</span><span>somando…</span>";
  const r = await fetch("/api/planilha/" + escr.pl.id + "/selecao", {
    method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ aba: escr.aba, faixa: faixa }),
  });
  if (!r.ok || faixaAtual() !== faixa) return;
  const d = await r.json();

  alvo.innerHTML = "<span>" + esc(faixa) + "</span>" +
    "<span>" + plural(d.quantas, "célula") + "</span>" +
    (d.com_numero
      ? "<span>soma " + moedaBR(d.soma) + "</span>" +
        "<span>média " + moedaBR(d.media) + "</span>" +
        "<span>menor " + moedaBR(d.minimo) + "</span>" +
        "<span>maior " + moedaBR(d.maximo) + "</span>"
      : "<span>nenhum número</span>") +
    (d.com_texto ? "<span>texto " + d.com_texto + "</span>" : "") +
    /* A vazia no meio de uma coluna muda a média e não muda a soma, e isso
       não se vê olhando a tabela. */
    (d.vazias ? "<span>vazias " + d.vazias + "</span>" : "") +
    (d.erros ? "<span>erros " + d.erros + "</span>" : "");
}

async function gravarCelula(valor, extras) {
  const p = escr.pl;
  const dados = extras || {};
  if (valor !== null && valor !== undefined) dados.valor = valor;

  const r = await fetch("/api/planilha/" + p.id + "/celula", {
    method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ aba: escr.aba, ref: escr.celula, dados: dados }),
  });
  if (!r.ok) { avisoCert(await erroDe(r)); return; }
  escr.pl = await r.json();
  desenharPlanilha();
}

/* A formula proposta aparece na barra fx antes de ser aplicada, com Manter
   e Desfazer na conversa: quem calcula e a planilha, nao o modelo. */
async function pedirFormula(pedido) {
  if (!pedido || escr.ocupada) return;
  const conversa = conversaAtual();
  const celula = escr.celula;
  escr.ocupada = true;
  conversa.push({ autor: "pessoa", texto: pedido });
  redesenharFalas("pl-fala");

  try {
    const r = await fetch("/api/planilha/" + escr.pl.id + "/assistente", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ pedido: pedido, selecao: celula }),
    });
    if (!r.ok) throw new Error(await erroDe(r));
    const d = await r.json();

    const entrada = $("pl-entrada");
    const antes = entrada ? entrada.value : "";
    if (entrada) entrada.value = d.formula;
    escr.notaFormula = "escrita pelo assistente · “" + pedido.slice(0, 60) + "”";
    const nota = $("pl-nota");
    if (nota) nota.textContent = escr.notaFormula;

    conversa.push({
      autor: "paulus",
      html: "Escrevi a fórmula <code>" + esc(d.formula) + "</code> para " + esc(celula) + ". " +
        (d.erro ? "Ela não fechou: " : "Resultado agora: ") + esc(d.resultado || "—") + "." +
        (d.aviso ? " " + esc(d.aviso) : ""),
      acoes: [
        { icone: "check", rotulo: "Manter", primario: true, acao: () => { escr.celula = celula; gravarCelula(d.formula); } },
        { icone: "undo", rotulo: "Desfazer", acao: () => {
          const e = $("pl-entrada"); if (e) e.value = antes;
          escr.notaFormula = ""; const n = $("pl-nota"); if (n) n.textContent = "";
          conversa.push({ autor: "paulus", html: "Desfeito. A célula " + esc(celula) + " ficou como estava." });
          redesenharFalas("pl-fala");
        } },
      ],
    });
  } catch (err) {
    conversa.push({ autor: "paulus", html: esc("Não consegui: " + (err.message || err)) });
  } finally {
    escr.ocupada = false;
    redesenharFalas("pl-fala");
  }
}

