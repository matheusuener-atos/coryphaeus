/* ---------------------------------------------------- acervo editorial */
/*
   O Acervo no desenho editorial das telas refeitas (Servicos, Gravacoes,
   Agenda): uma coluna de leitura, sem painel ao lado. A abertura diz como o
   acervo esta em uma frase; a ficha do documento abre DEBAIXO da linha, como
   a gravacao que revela o tocador. Dois desenhos para escolher:

   "indice"  - os documentos agrupados por pasta, cada pasta um cartao.
   "sumario" - as pastas num sumario tipografico a esquerda e os documentos
               como verbetes, com a analise em uma linha.

   "misto"   - APROVADO (1c): o sumario em cartao a esquerda e as secoes por
               pasta de "indice" a direita. E o padrao.

   Qual vale: ?acervo=indice|sumario|misto na URL, ou paulus.acervo.desenho. Os
   ganchos (data-doc, data-pegar, data-ficha...) sao os de sempre, entao
   ligarBiblioteca() liga tudo sem mudar.
*/

function desenhoDoAcervo() {
  const daUrl = new URLSearchParams(location.search).get("acervo");
  if (daUrl === "indice" || daUrl === "sumario" || daUrl === "misto") return daUrl;
  try { const g = localStorage.getItem("paulus.acervo.desenho"); if (g === "indice" || g === "sumario" || g === "misto") return g; } catch (err) { /* sem memoria */ }
  return "misto";
}

function estadoDaAnalise(x) {
  const a = x.analise || {};
  const estado = a.estado || "sem-analise";
  const ponto = estado === "analisado" ? '<i class="ponto-verde"></i>'
    : estado === "mudou" ? '<i class="ponto-ambar"></i>'
    : estado === "lendo" ? coroa(14) : '<i class="ponto-vazio"></i>';
  const rotulo = a.rotulo || "sem análise";
  return '<span class="analise-doc ' + esc(estado) + '">' + ponto + "<span>" + esc(rotulo) + "</span></span>";
}

/* A faixa de abertura: quanto ha, de quantos clientes, o que falta ler e as
   datas que esperam confirmacao. */
function abreAcervo(d) {
  const todos = bib.todos.length ? bib.todos : bib.documentos;
  const clientes = new Set(todos.map((x) => x.cliente).filter(Boolean)).size;
  const prazos = (bib.sugestoes || []).length;
  const item = (rotulo, valor) => '<div class="sv-ficha-item"><span class="sv-kicker">' + rotulo + "</span>" + valor + "</div>";
  return '<div class="sv-ficha">' +
    item("Documentos", "<b>" + d.total + "</b>") +
    item("Clientes", "<b>" + clientes + "</b>") +
    item("Sem análise", '<b class="' + (d.sem_analise ? "ae-acc" : "") + '">' + (d.sem_analise || "nenhum") + "</b>") +
    item("Prazos a conferir", '<button type="button" class="sv-ficha-pasta" data-visao-acervo="prazos">' + (prazos ? plural(prazos, "data") + " →" : "nenhum") + "</button>") +
    "</div>";
}

function chipsDoAcervo(d) {
  const chip = (id, rotulo, conta) => {
    const classe = bib.filtro === id && !bib.pastaFiltro ? "on" : "";
    return '<button class="' + classe + '" data-ac-filtro="' + id + '">' + rotulo + (conta === null ? "" : " · " + conta) + "</button>";
  };
  const ordem = '<label class="ae-ordem"><span>Ordenar por</span><select id="bib-ordem">' +
    Object.entries(d.ordens || {}).map(([v, r]) => '<option value="' + v + '"' + (bib.ordem === v ? " selected" : "") + ">" + esc(r) + "</option>").join("") +
    "</select></label>";
  const pasta = bib.pastaFiltro
    ? '<button class="on" data-ac-pasta="' + esc(bib.pastaFiltro) + '" title="Tirar o filtro da pasta">' + esc(pastaCurta(bib.pastaFiltro)) + ic("close", 14) + "</button>" : "";
  return '<div class="ae-barra"><div class="ae-chips">' + chip("todos", "Todos", d.total) + chip("recentes", "Recentes", null) +
    chip("fixados", "Fixados", d.fixados) + chip("sem-analise", "Sem análise", d.sem_analise) + pasta + "</div>" + ordem + "</div>";
}

function pastaCurta(caminho) {
  const x = bib.todos.find((d) => d.pasta === caminho);
  return x ? (x.pasta_curta || x.pasta) : caminho.split(/[\\/]/).pop();
}

function barraDoLote() {
  const quantos = bib.escolhidos.size;
  if (!quantos) return "";
  return '<div class="barra-selecao"><span class="selecao"><span class="marcar on">' + ic("check", 12) + "</span>" +
    '<span class="selecao-conta">' + plural(quantos, "selecionado") + "</span>" +
    '<button class="limpar" id="lote-limpar">Limpar</button></span><span class="divisa-v"></span>' +
    '<button class="primario" data-lote="perguntar">' + ic("forum", 16) + "Perguntar sobre estes</button>" +
    '<button class="botao-icone" data-lote="analisar" title="Tomar vista de novo" aria-label="Tomar vista de novo">' + ic("visibility", 18) + "</button>" +
    '<button class="botao-icone" data-lote="mover" title="Mover para pasta" aria-label="Mover para pasta">' + ic("drive_file_move", 18) + "</button>" +
    '<button class="botao-icone" data-lote="fixar" title="Fixar" aria-label="Fixar">' + ic("push_pin", 18) + "</button>" +
    '<button class="botao-icone" data-lote="exportar" title="Exportar" aria-label="Exportar">' + ic("download", 18) + "</button>" +
    '<span class="divisa-v"></span><button class="botao-icone perigo" data-lote="apagar" title="Apagar do acervo" aria-label="Apagar do acervo">' + ic("delete", 18) + "</button></div>";
}

/* A FICHA NA LINHA: o que era o painel da direita, agora embaixo do
   documento aberto, na largura da coluna. */
function fichaNaLinha(x) {
  const a = x.analise || {};
  const analisado = a.estado === "analisado";
  const ext = (x.nome.split(".").pop() || "").toUpperCase();
  const prazos = (bib.sugestoes || []).filter((s) => s.arquivo === x.nome);
  const texto = x.tipo_rotulo
    ? maiuscula(x.tipo_rotulo) + (x.cliente ? " de " + x.cliente : "") + (x.data ? ", com data de " + x.data : "") + (x.valor ? ", no valor de " + x.valor : "") +
      ". Li " + plural(x.trechos || 0, "trecho") + (x.caracteres ? " em " + milhar(x.caracteres) + " caracteres" : "") + "."
    : "Ainda não tomei vista deste documento: sei o nome e a pasta, e " + plural(x.trechos || 0, "trecho") + " já estão indexados para a busca.";
  const item = (rotulo, valor) => valor ? '<div class="sv-ficha-item"><span class="sv-kicker">' + rotulo + '</span><b class="corta" title="' + esc(valor) + '">' + esc(valor) + "</b></div>" : "";
  const linhasPrazo = prazos.map((s) => '<div class="ae-prazo"><span class="ae-prazo-data"><b>' + esc(s.prazo.slice(8, 10)) + "</b><small>" + esc(mesCurto(s.prazo.slice(0, 7)).slice(0, 3)) + "</small></span>" +
    '<span class="duas-linhas"><b>' + esc(s.titulo || "Conferir prazo") + "</b><small>" + esc(dataLonga(s.prazo) + (s.lista ? " · " + s.lista : "")) + "</small></span>" +
    '<button class="sv-ligacao" data-ficha="prazos">conferir</button></div>').join("");
  return '<div class="ae-ficha">' +
    '<p class="ae-ficha-lide">' + esc(texto) + "</p>" +
    '<div class="sv-ficha ae-ficha-faixa">' + item("Cliente", x.cliente) + item("Tipo", x.tipo_rotulo) + item("Data", x.data) + item("Valor", x.valor) +
    item("Arquivo", ext + " · " + tamanho(x.bytes) + (x.paginas ? " · " + plural(x.paginas, "página") : "")) + "</div>" +
    (linhasPrazo ? '<div class="ae-ficha-bloco"><span class="sv-kicker">Datas lidas neste documento</span>' + linhasPrazo + "</div>" : "") +
    '<div class="ae-ficha-acoes"><button class="primario com-icone" data-ficha="perguntar">' + ic("forum", 16) + "Perguntar sobre este</button>" +
    '<button class="com-icone" data-ficha="aqui">' + ic("open_in_new", 16) + "Abrir aqui</button>" +
    (ext === "PDF" ? '<button class="com-icone" data-ficha="assinar">' + ic("draw", 16) + "Assinar</button>" : "") +
    (analisado ? "" : '<button class="com-icone" data-ficha="vista">' + ic("visibility", 16) + "Tomar vista</button>") +
    '<span class="cresce"></span><small class="ae-ficha-onde" title="' + esc(x.pasta) + '">' + esc(x.pasta_curta || x.pasta) + " · modificado " + esc(x.modificado || "—") + "</small></div>" +
    '<div class="visor-caixa" id="bib-visor"></div></div>';
}

function marcaDoDoc(x) {
  const on = bib.escolhidos.has(x.caminho);
  return '<span class="marcar' + (on ? " on" : "") + '" data-pegar="' + esc(x.caminho) + '" role="checkbox" aria-checked="' + on + '">' + ic("check", 12) + "</span>";
}

function classeDaLinha(x, base) {
  return base + " tabela-linha" + (bib.escolhidos.has(x.caminho) ? " escolhida" : "") + (bib.aberto === x.caminho ? " aberta" : "") + (x.existe ? "" : " apagada");
}

/* ---------------------------------------------------- A: o indice */

function linhaDoIndice(x) {
  const sub = [x.tipo_rotulo, x.cliente, x.existe ? "" : "não está mais no disco"].filter(Boolean).join(" · ") || "sem análise ainda";
  return '<div class="' + classeDaLinha(x, "ae-linha") + '" data-doc="' + esc(x.caminho) + '">' + marcaDoDoc(x) + glifo(x.nome) +
    '<span class="duas-linhas"><b>' + (x.fixado ? ic("push_pin", 14) : "") + esc(x.nome) + "</b><small>" + esc(sub) + "</small></span>" +
    '<span class="quando-doc">' + esc(x.modificado || "") + "</span>" + estadoDaAnalise(x) +
    '<button class="mais-linha" data-menu="' + esc(x.caminho) + '" title="Mais" aria-label="Mais">' + ic("more_horiz", 18) + "</button>" +
    (x.trecho ? '<div class="acervo-trecho">' + esc(x.trecho) + "</div>" : "") + "</div>" +
    (bib.aberto === x.caminho ? fichaNaLinha(x) : "");
}

function corpoDoIndice() {
  const grupos = new Map();
  bib.documentos.forEach((x) => { const k = x.pasta_curta || x.pasta; if (!grupos.has(k)) grupos.set(k, []); grupos.get(k).push(x); });
  if (!grupos.size) return '<div class="sv-vazio"><h3>' + (bib.termo ? "Nada com “" + esc(bib.termo) + "”" : "Nenhum documento neste filtro") + "</h3><p>" +
    (bib.termo ? "Procurei no nome, na pasta e no texto dos documentos." : "Troque o filtro acima ou inclua outra pasta.") + "</p></div>";
  return [...grupos].map(([pasta, docs]) => {
    const caminho = docs[0].pasta;
    const sem = docs.filter((x) => (x.analise || {}).estado !== "analisado").length;
    return '<section class="sv-secao ae-pasta"><div class="sv-secao-cabeca"><button type="button" class="sv-secao-titulo ae-pasta-nome" data-ac-pasta="' + esc(caminho) + '" title="Ver só esta pasta">' +
      ic("folder", 16) + esc(pasta) + "</button>" +
      '<span class="sv-secao-meta">' + plural(docs.length, "documento") + (sem ? " · " + sem + " a ler" : "") + "</span></div>" +
      docs.map(linhaDoIndice).join("") + "</section>";
  }).join("");
}

/* -------------------------------------------------- B: o sumario */

function sumarioDoAcervo() {
  const pastas = new Map();
  bib.todos.forEach((x) => { const p = pastas.get(x.pasta) || { pasta: x.pasta, nome: x.pasta_curta || x.pasta, n: 0 }; p.n += 1; pastas.set(x.pasta, p); });
  const porRaiz = new Map();
  [...pastas.values()].sort((a, b) => a.nome.localeCompare(b.nome)).forEach((p) => {
    const [raiz, ...resto] = p.nome.split(" › ");
    if (!porRaiz.has(raiz)) porRaiz.set(raiz, []);
    porRaiz.get(raiz).push(Object.assign({}, p, { folha: resto.join(" › ") || raiz }));
  });
  return '<nav class="ae-sumario"><span class="sv-kicker">Sumário</span>' +
    '<button class="ae-sum-item' + (!bib.pastaFiltro ? " on" : "") + '" data-ac-filtro="todos"><span>Todo o acervo</span><i></i><small>' + bib.todos.length + "</small></button>" +
    [...porRaiz].map(([raiz, lista]) => '<div class="ae-sum-grupo"><span class="ae-sum-raiz">' + esc(raiz) + "</span>" +
      lista.map((p) => '<button class="ae-sum-item' + (bib.pastaFiltro === p.pasta ? " on" : "") + '" data-ac-pasta="' + esc(p.pasta) + '" title="' + esc(p.pasta) + '"><span>' +
        esc(p.folha) + "</span><i></i><small>" + p.n + "</small></button>").join("") + "</div>").join("") +
    '<button class="ae-sum-incluir" data-ac-incluir="1">' + ic("add", 15) + "incluir pasta</button></nav>";
}

function verbete(x) {
  const a = x.analise || {};
  const lide = x.tipo_rotulo
    ? maiuscula(x.tipo_rotulo) + (x.cliente ? " de " + x.cliente : "") + (x.data ? ", de " + x.data : "") + (x.valor ? " · " + x.valor : "") + "."
    : "Ainda não tomei vista — só o nome e a pasta são conhecidos.";
  return '<article class="' + classeDaLinha(x, "ae-verbete") + '" data-doc="' + esc(x.caminho) + '">' + marcaDoDoc(x) +
    '<div class="ae-verbete-corpo"><span class="sv-kicker">' + esc((x.pasta_curta || "").split(" › ").pop()) + (x.fixado ? " · fixado" : "") + "</span>" +
    '<h3>' + glifo(x.nome) + '<span class="corta">' + esc(x.nome.replace(/\.[^.]+$/, "")) + "</span></h3>" +
    '<p class="' + (x.tipo_rotulo ? "" : "vazio") + '">' + esc(lide) + "</p>" +
    '<div class="ae-verbete-pe">' + estadoDaAnalise(x) + "<span>" + esc(x.modificado || "") + "</span>" +
    (x.paginas ? "<span>" + plural(x.paginas, "página") + "</span>" : "") + (a.estado === "analisado" && x.trechos ? "<span>" + plural(x.trechos, "trecho") + "</span>" : "") + "</div>" +
    (x.trecho ? '<div class="acervo-trecho">' + esc(x.trecho) + "</div>" : "") + "</div>" +
    '<button class="mais-linha" data-menu="' + esc(x.caminho) + '" title="Mais" aria-label="Mais">' + ic("more_horiz", 18) + "</button></article>" +
    (bib.aberto === x.caminho ? fichaNaLinha(x) : "");
}

function corpoDoSumario() {
  const titulo = bib.pastaFiltro ? pastaCurta(bib.pastaFiltro) : ({ fixados: "Fixados", "sem-analise": "Sem análise", recentes: "Recentes" }[bib.filtro] || "Todo o acervo");
  const lista = bib.documentos.length ? bib.documentos.map(verbete).join("")
    : '<div class="sv-vazio"><h3>' + (bib.termo ? "Nada com “" + esc(bib.termo) + "”" : "Nada aqui") + "</h3><p>" +
      (bib.termo ? "Procurei no nome, na pasta e no texto dos documentos." : "Nenhum documento nesta pasta ou filtro.") + "</p></div>";
  return '<div class="ae-duas">' + sumarioDoAcervo() + '<div class="ae-verbetes"><div class="ae-verbetes-cabeca"><h2>' + esc(titulo) + "</h2>" +
    "<small>" + plural(bib.documentos.length, "documento") + "</small></div>" + lista + "</div></div>";
}

/* ------------------------------------------ C: sumario + indice */
/* O sumario de B a esquerda; a direita, as pastas em secoes como em A, com
   o nome do documento em serifa e a linha do que foi lido embaixo. */

function linhaDoMisto(x) {
  const lide = x.tipo_rotulo
    ? [maiuscula(x.tipo_rotulo), x.cliente, x.data, x.valor].filter(Boolean).join(" · ")
    : (x.existe ? "ainda sem análise" : "não está mais no disco");
  return '<div class="' + classeDaLinha(x, "ae-linha ae-linha-misto") + '" data-doc="' + esc(x.caminho) + '">' + marcaDoDoc(x) + glifo(x.nome) +
    '<span class="duas-linhas"><b>' + (x.fixado ? ic("push_pin", 14) : "") + '<span class="corta">' + esc(x.nome.replace(/\.[^.]+$/, "")) + "</span></b>" +
    '<small class="' + (x.tipo_rotulo ? "" : "vazio") + '">' + esc(lide) + "</small></span>" +
    '<span class="quando-doc">' + esc(x.modificado || "") + "</span>" + estadoDaAnalise(x) +
    '<button class="mais-linha" data-menu="' + esc(x.caminho) + '" title="Mais" aria-label="Mais">' + ic("more_horiz", 18) + "</button>" +
    (x.trecho ? '<div class="acervo-trecho">' + esc(x.trecho) + "</div>" : "") + "</div>" +
    (bib.aberto === x.caminho ? fichaNaLinha(x) : "");
}

/* O sumario em cartao, com o cabecalho e as linhas de fio das secoes de A. */
function sumarioDoMisto() {
  const pastas = new Map();
  bib.todos.forEach((x) => { const p = pastas.get(x.pasta) || { pasta: x.pasta, nome: x.pasta_curta || x.pasta, n: 0, sem: 0 }; p.n += 1;
    if ((x.analise || {}).estado !== "analisado") p.sem += 1; pastas.set(x.pasta, p); });
  const porRaiz = new Map();
  [...pastas.values()].sort((a, b) => a.nome.localeCompare(b.nome)).forEach((p) => {
    const [raiz, ...resto] = p.nome.split(" › ");
    if (!porRaiz.has(raiz)) porRaiz.set(raiz, []);
    porRaiz.get(raiz).push(Object.assign({}, p, { folha: resto.join(" › ") }));
  });
  const linha = (attr, on, rotulo, n, sem, recuo) => '<button type="button" class="am-pasta' + (on ? " on" : "") + (recuo ? " recuo" : "") + '" ' + attr + ">" +
    '<span class="corta">' + esc(rotulo) + "</span>" + (sem ? '<i title="' + sem + ' a ler"></i>' : "") + "<small>" + n + "</small></button>";
  let html = linha('data-ac-filtro="todos"', !bib.pastaFiltro, "Todo o acervo", bib.todos.length, 0, false);
  porRaiz.forEach((lista, raiz) => {
    if (lista.length === 1 && !lista[0].folha) { const p = lista[0]; html += linha('data-ac-pasta="' + esc(p.pasta) + '" title="' + esc(p.pasta) + '"', bib.pastaFiltro === p.pasta, raiz, p.n, p.sem, false); return; }
    html += '<span class="am-raiz">' + esc(raiz) + "</span>";
    lista.forEach((p) => { html += linha('data-ac-pasta="' + esc(p.pasta) + '" title="' + esc(p.pasta) + '"', bib.pastaFiltro === p.pasta, p.folha || raiz, p.n, p.sem, true); });
  });
  return '<nav class="sv-secao am-sumario"><div class="sv-secao-cabeca"><span class="sv-secao-titulo">' + ic("folder_open", 16) + "Pastas</span>" +
    '<button type="button" class="sv-ligacao" data-ac-incluir="1">' + ic("add", 15) + "incluir</button></div>" + html + "</nav>";
}

function corpoDoMisto() {
  const grupos = new Map();
  bib.documentos.forEach((x) => { const k = x.pasta_curta || x.pasta; if (!grupos.has(k)) grupos.set(k, []); grupos.get(k).push(x); });
  const titulo = bib.pastaFiltro ? pastaCurta(bib.pastaFiltro) : ({ fixados: "Fixados", "sem-analise": "Sem análise", recentes: "Recentes" }[bib.filtro] || "Todo o acervo");
  const secoes = grupos.size ? [...grupos].map(([pasta, docs]) => {
    const sem = docs.filter((x) => (x.analise || {}).estado !== "analisado").length;
    const [raiz, ...resto] = pasta.split(" › ");
    return '<section class="sv-secao ae-pasta"><div class="sv-secao-cabeca"><button type="button" class="sv-secao-titulo ae-pasta-nome" data-ac-pasta="' + esc(docs[0].pasta) + '" title="Ver só esta pasta">' +
      (resto.length ? '<small class="ae-pasta-raiz">' + esc(raiz) + " ›</small>" : "") + esc(resto.join(" › ") || raiz) + "</button>" +
      '<span class="sv-secao-meta">' + plural(docs.length, "documento") + (sem ? " · " + sem + " a ler" : "") + "</span></div>" +
      docs.map(linhaDoMisto).join("") + "</section>";
  }).join("") : '<div class="sv-vazio"><h3>' + (bib.termo ? "Nada com “" + esc(bib.termo) + "”" : "Nada aqui") + "</h3><p>" +
    (bib.termo ? "Procurei no nome, na pasta e no texto dos documentos." : "Nenhum documento nesta pasta ou filtro.") + "</p></div>";
  return '<div class="ae-duas am-duas">' + sumarioDoMisto() + '<div class="ae-secoes">' + secoes + "</div></div>";
}

/* -------------------------------------------------------- a tela */

function desenharAcervoEditorial() {
  const d = bib.contas || {};
  const desenho = desenhoDoAcervo();
  const mais = !bib.pastaFiltro && d.achados > bib.limite;
  const corpo = desenho === "sumario" ? corpoDoSumario() : desenho === "misto" ? corpoDoMisto() : corpoDoIndice();
  $("centro").innerHTML = '<div class="acervo sem-painel ae-tela ae-desenho-' + desenho + '"><div class="acervo-principal sv-principal"><div class="sv-medida">' +
    abreAcervo(d) + chipsDoAcervo(d) + barraDoLote() + corpo +
    (mais ? '<button class="ae-mais" id="bib-mais">Mais documentos · mostrando ' + bib.documentos.length + " de " + d.achados + "</button>" : "") +
    "</div></div></div>";
  ligarBiblioteca();
  const centro = $("centro");
  centro.querySelectorAll("[data-visao-acervo]").forEach((b) => { b.onclick = () => abrirVisaoDoAcervo(b.dataset.visaoAcervo); });
  if (conteudoNovo("acervo:" + desenho + ":" + bib.filtro + ":" + bib.pastaFiltro + ":" + bib.termo)) {
    entraConteudo(centro.firstElementChild);
    entraLista(centro, ".ae-linha, .ae-verbete");
  }
}
