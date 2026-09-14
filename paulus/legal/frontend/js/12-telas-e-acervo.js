/* ------------------------------------------------------------- telas */
/*
   Biblioteca, habilidades e maquina ocupam a area da conversa. Nada se
   perde: a conversa continua listada na coluna e volta com um clique.
*/

function abrirTela(nome, opcoes) {
  const o = opcoes || {};
  fecharEditorNaConversa();
  guardarLugarDoAssistente();
  deixarDitadoPendente();
  transicaoDeTela("tela:" + nome);
  estado.trabalhoId = null;
  estado.trabalho = null;
  /* O campo de pergunta e da conversa. Numa tela de Financeiro ou de Planilha
     ele so ocupava o rodape sem ter o que fazer ali. */
  $("compositor").hidden = true;
  $("conversa-titulo").textContent = nome;
  $("conversa-titulo").classList.remove("renomeavel");
  $("conversa-titulo").removeAttribute("title");
  $("conversa-meta").textContent = "";
  $("apagar").hidden = true;
  $("exportar-conversa").hidden = true;
  $("registro").hidden = true;
  $("agora").hidden = true;
  $("centro").classList.remove("prosa");
  $("conversa-col").classList.remove("tela-dupla");
  $("conversa-col").classList.toggle("tela-cheia", Boolean(o.cheia));
  $("acoes-tela").innerHTML = "";
  $("nav-tela").innerHTML = "";
  mostrarLateral(false);
  fecharFlutuante();
  carregarTrabalhos();
}


/*
   Pagina 2: onde ficam as telas que nao sao conversa. A pagina 1 pergunta,
   a pagina 2 administra.
*/


/* --------------------------------------------------------- biblioteca */
/*
   O Acervo do desenho (docs/ui/03-telas-desktop.md, A5): tres visoes num
   cabecalho so - Documentos, Organizar, Prazos - e um painel a direita com a
   ficha do que esta aberto. O servidor faz o corte da lista porque procurar
   inclui o conteudo dos documentos, e o conteudo nao esta no navegador.
*/

const bib = {
  documentos: [], todos: [], termo: "", filtro: "todos", ordem: "modificacao",
  escolhidos: new Set(), limite: 60, contas: null, pasta: "", pastaFiltro: "",
  aberto: null, visao: "documentos", largo: false, sugestoes: null,
};

const MESES_CURTOS = ["jan", "fev", "mar", "abr", "mai", "jun", "jul", "ago", "set", "out", "nov", "dez"];

function dataCurta(iso) {
  const m = /^(\d{4})-(\d{2})-(\d{2})/.exec(iso || "");
  if (!m) return esc(iso || "");
  return Number(m[3]) + " " + MESES_CURTOS[Number(m[2]) - 1];
}

/* "12 out 2026 · em 30 dias": a data e a distancia ate ela, que e o que
   importa num prazo. */
function dataLonga(iso) {
  const m = /^(\d{4})-(\d{2})-(\d{2})/.exec(iso || "");
  if (!m) return esc(iso || "—");
  const d = new Date(Number(m[1]), Number(m[2]) - 1, Number(m[3]));
  const hoje = new Date();
  hoje.setHours(0, 0, 0, 0);
  const dias = Math.round((d - hoje) / 86400000);
  const base = Number(m[3]) + " " + MESES_CURTOS[Number(m[2]) - 1] +
    (d.getFullYear() !== hoje.getFullYear() ? " " + m[1] : "");
  if (dias === 0) return base + " · hoje";
  if (dias === 1) return base + " · amanhã";
  if (dias > 1 && dias <= 60) return base + " · em " + dias + " dias";
  return base;
}

/* O glifo de formato do desenho: PDF, W, X. */
function glifo(nome) {
  const ext = ((nome || "").split(".").pop() || "").toLowerCase();
  const conhecidas = ["pdf", "docx", "doc", "xlsx", "xls"];
  const classe = conhecidas.includes(ext) ? ext : "outro";
  const texto = ext === "pdf" ? "PDF"
    : (ext === "docx" || ext === "doc") ? "W"
    : (ext === "xlsx" || ext === "xls") ? "X"
    : (ext.slice(0, 3).toUpperCase() || "?");
  return '<span class="glifo ' + classe + '">' + texto + "</span>";
}

/* O cabecalho da tela: busca, seletor de visoes e a acao principal. E o
   mesmo nas tres visoes; muda so o que a acao principal faz. */
function cabecalhoAcervo(visao, acao) {
  $("acoes-tela").innerHTML =
    '<label class="busca-tela">' + ic("search", 18) +
    '<input type="text" id="bib-termo" placeholder="Buscar por nome, pasta ou trecho…" value="' + esc(bib.termo) + '"></label>' +
    '<div class="visoes">' +
    [["documentos", "Documentos"], ["organizar", "Organizar"], ["prazos", "Prazos"]].map(([v, r]) => {
      const classe = v === visao ? "ativa" : "";
      return '<button class="' + classe + '" data-visao="' + v + '">' + r + "</button>";
    }).join("") +
    "</div>" + (acao || "");
  $("acoes-tela").querySelectorAll("[data-visao]").forEach((b) => {
    b.onclick = () => abrirVisaoDoAcervo(b.dataset.visao);
  });

  const campo = $("bib-termo");
  let t;
  campo.oninput = (e) => {
    clearTimeout(t);
    const v = e.target.value;
    // A busca vai ao servidor porque procura no conteudo; a espera evita uma
    // consulta por tecla digitada. Buscar sempre leva para Documentos.
    t = setTimeout(() => {
      bib.termo = v.trim();
      bib.limite = 60;
      if (bib.visao !== "documentos") mostrarBiblioteca(); else buscarAcervo();
    }, 260);
  };
  campo.onkeydown = (e) => {
    if (e.key === "Escape") { campo.value = ""; bib.termo = ""; if (bib.visao === "documentos") buscarAcervo(); }
  };
}

function abrirVisaoDoAcervo(visao) {
  marcarDestino("biblioteca");
  if (visao === "organizar") return organizarComecar();
  if (visao === "prazos") return mostrarPrazos();
  return mostrarBiblioteca();
}

async function mostrarBiblioteca() {
  abrirTela("Acervo", { cheia: true });
  bib.visao = "documentos";
  cabecalhoAcervo("documentos",
    '<button class="primario com-icone" id="bib-pasta">' + ic("add", 16) + "Incluir pasta</button>");
  $("bib-pasta").onclick = adicionarPastaAoAcervo;
  if (!bib.documentos.length) {
    $("centro").innerHTML = '<div class="acervo sem-painel"><div class="acervo-principal"><p class="nota">carregando…</p></div></div>';
  }
  await buscarAcervo();
}

async function buscarAcervo() {
  let d;
  const limite = bib.pastaFiltro ? 0 : bib.limite;
  try {
    d = await (await fetch("/api/biblioteca?termo=" + encodeURIComponent(bib.termo) +
      "&filtro=" + encodeURIComponent(bib.filtro) +
      "&ordem=" + encodeURIComponent(bib.ordem) +
      "&limite=" + limite)).json();
  } catch (err) {
    $("centro").innerHTML = '<div class="acervo sem-painel"><div class="acervo-principal"><p class="nota">não consegui abrir: ' +
      esc(String(err)) + "</p></div></div>";
    return;
  }

  bib.documentos = bib.pastaFiltro ? d.documentos.filter((x) => x.pasta === bib.pastaFiltro) : d.documentos;
  bib.contas = d;
  bib.pasta = d.pasta;

  // A arvore de pastas precisa do acervo inteiro, nao da pagina: vem numa
  // segunda consulta, sem termo nem filtro, so quando o total muda.
  if (bib.todos.length !== d.total) {
    try {
      const tudo = await (await fetch("/api/biblioteca?filtro=todos&limite=0")).json();
      bib.todos = tudo.documentos;
    } catch (err) { bib.todos = []; }
  }
  if (bib.sugestoes === null) {
    try {
      bib.sugestoes = (await (await fetch("/api/tarefas/sugestoes")).json()).sugestoes || [];
    } catch (err) { bib.sugestoes = []; }
  }

  // Some da selecao o que saiu da lista: agir sobre o que nao esta a vista e
  // exatamente o erro que a barra de lote precisa nao cometer.
  const visiveis = new Set(bib.documentos.map((x) => x.caminho));
  for (const c of [...bib.escolhidos]) if (!visiveis.has(c)) bib.escolhidos.delete(c);
  if (bib.aberto && !visiveis.has(bib.aberto)) bib.aberto = null;

  desenharBiblioteca();
  atualizarPostura();
}

function tamanho(bytes) {
  if (!bytes) return "0 KB";
  if (bytes < 1024 * 1024) return Math.max(1, Math.round(bytes / 1024)) + " KB";
  return (bytes / 1024 / 1024).toFixed(1).replace(".", ",") + " MB";
}

/* A coluna da esquerda: os quatro cortes e as pastas indexadas, com a conta
   de cada uma. Pasta dentro de pasta indexada aparece recuada. */
function arvoreDoAcervo(d) {
  const pastas = new Map();
  for (const x of bib.todos) {
    const p = pastas.get(x.pasta) || { pasta: x.pasta, nome: x.pasta_curta || x.pasta, n: 0 };
    p.n += 1;
    pastas.set(x.pasta, p);
  }
  const lista = [...pastas.values()].sort((a, b) => a.pasta.localeCompare(b.pasta));
  const caminhos = new Set(lista.map((p) => p.pasta));
  const pai = (c) => {
    const i = Math.max(c.lastIndexOf("\\"), c.lastIndexOf("/"));
    return i > 0 ? c.slice(0, i) : "";
  };

  const corte = (id, icone, rotulo, conta, classeConta) => {
    const classe = "ac-item" + (bib.filtro === id && !bib.pastaFiltro ? " ativa" : "");
    return '<button class="' + classe + '" data-ac-filtro="' + id + '">' +
      ic(icone, 18) + '<span class="rotulo-arvore">' + rotulo + "</span>" +
      (conta === null ? "" : '<span class="conta-arvore' + (classeConta || "") + '">' + conta + "</span>") + "</button>";
  };

  return '<div class="ac-arvore">' +
    corte("todos", "inventory_2", "Todos os documentos", d.total) +
    corte("recentes", "history", "Recentes", null) +
    corte("fixados", "push_pin", "Fixados", d.fixados) +
    corte("sem-analise", "radio_button_unchecked", "Sem análise", d.sem_analise, d.sem_analise ? " acc" : "") +
    '<span class="ac-divisa"></span><span class="ac-secao">Pastas indexadas</span>' +
    lista.map((p) => {
      const sub = caminhos.has(pai(p.pasta));
      return '<button class="ac-item' + (sub ? " sub" : "") + (bib.pastaFiltro === p.pasta ? " ativa" : "") +
        '" data-ac-pasta="' + esc(p.pasta) + '" title="' + esc(p.pasta) + '">' +
        ic(sub ? "subdirectory_arrow_right" : "folder", 18) +
        '<span class="rotulo-arvore">' + esc(p.nome) + '</span><span class="conta-arvore">' + p.n + "</span></button>";
    }).join("") +
    '<button class="ac-incluir" data-ac-incluir="1">+ incluir pasta</button></div>';
}

function desenharBiblioteca() {
  const d = bib.contas || {};
  $("conversa-meta").textContent = d.total
    ? plural(d.total, "documento") + " · " + plural(d.total_trechos || 0, "trecho") + " lidos · nada saiu da máquina hoje"
    : "nada aberto ainda";

  if (!d.total) {
    $("centro").innerHTML = '<div class="acervo sem-painel"><div class="acervo-principal">' +
      '<div class="tabela-cartao"><div class="painel-vazio"><h3>Nenhum documento ainda</h3>' +
      "<p>Aponte uma pasta e eu leio o que houver lá dentro. Os documentos ficam em " + esc(bib.pasta) + ".</p>" +
      '<div><button class="primario" id="bib-pasta-vazio">Escolher pasta</button></div></div></div></div></div>';
    $("bib-pasta-vazio").onclick = adicionarPastaAoAcervo;
    return;
  }

  const quantos = bib.escolhidos.size;
  const barra = quantos
    ? '<span class="selecao"><span class="marcar on">' + ic("check", 12) + "</span>" +
      '<span class="selecao-conta">' + plural(quantos, "selecionado") + "</span>" +
      '<button class="limpar" data-selecionar-todos="1">Selecionar todos</button>' +
      '<button class="limpar" id="lote-limpar">Limpar</button></span><span class="divisa-v"></span>' +
      '<button class="primario" data-lote="perguntar">' + ic("forum", 16) + "Perguntar sobre estes</button>" +
      '<button class="botao-icone" data-lote="analisar" title="Tomar vista de novo" aria-label="Tomar vista de novo">' + ic("visibility", 18) + "</button>" +
      '<button class="botao-icone" data-lote="mover" title="Mover para pasta" aria-label="Mover para pasta">' + ic("drive_file_move", 18) + "</button>" +
      '<button class="botao-icone" data-lote="fixar" title="Fixar" aria-label="Fixar">' + ic("push_pin", 18) + "</button>" +
      '<button class="botao-icone" data-lote="exportar" title="Exportar" aria-label="Exportar">' + ic("download", 18) + "</button>" +
      '<span class="divisa-v"></span>' +
      '<button class="botao-icone perigo" data-lote="apagar" title="Apagar do acervo" aria-label="Apagar do acervo">' + ic("delete", 18) + "</button>"
    : '<span class="nota-barra">' + (bib.pastaFiltro ? esc(bib.pastaFiltro) : esc((d.filtros || {})[bib.filtro] || "Todos")) + "</span>";
  const ordem = '<span class="direita"><label class="nota-barra" for="bib-ordem">Ordenar por</label>' +
    '<select class="ordem-sel" id="bib-ordem">' +
    Object.entries(d.ordens || {}).map(([v, r]) =>
      '<option value="' + v + '"' + (bib.ordem === v ? " selected" : "") + ">" + esc(r) + "</option>").join("") +
    "</select></span>";

  const linhas = bib.documentos.length
    ? bib.documentos.map(linhaDoAcervo).join("")
    : '<p class="nota">' + (bib.termo
        ? "Nada com esse termo — nem no nome, nem na pasta, nem no texto dos documentos."
        : "Nenhum documento neste filtro.") + "</p>";
  const achados = bib.pastaFiltro ? bib.documentos.length : d.achados;
  const mais = !bib.pastaFiltro && d.achados > bib.limite;

  $("centro").innerHTML =
    '<div class="acervo' + (bib.largo ? " painel-largo" : "") + '"><div class="acervo-principal"><div class="acervo-colunas">' +
    arvoreDoAcervo(d) +
    '<div class="tabela-cartao"><div class="tabela-barra">' + barra + ordem + "</div>" +
    '<div class="tabela-cabecalho colunas-documentos"><span></span><span>Nome e pasta</span><span>Modificado</span><span>Análise</span><span></span></div>' +
    '<div class="tabela-corpo" id="bib-lista">' + linhas + "</div>" +
    '<div class="tabela-rodape"><span>Mostrando ' + bib.documentos.length + " de " + achados + '</span><span class="cresce"></span>' +
    "<span>Nada saiu da máquina hoje</span>" +
    (mais ? '<button class="mais" id="bib-mais">Mais documentos →</button>' : "") + "</div>" +
    "</div></div></div>" + painelDoAcervo() + "</div>";
  ligarBiblioteca();
}

function linhaDoAcervo(x) {
  const escolhido = bib.escolhidos.has(x.caminho);
  const a = x.analise || {};
  const estadoA = a.estado || "sem-analise";
  const ponto = estadoA === "analisado" ? '<i class="ponto-verde"></i>'
    : estadoA === "mudou" ? '<i class="ponto-ambar"></i>'
    : estadoA === "lendo" ? coroa(16)
    : '<i class="ponto-vazio"></i>';
  const rotulo = a.rotulo || "sem análise";
  const quando = a.quando && !rotulo.includes(a.quando) ? " · " + a.quando : "";

  return '<div class="tabela-linha colunas-documentos' + (escolhido ? " escolhida" : "") +
    (bib.aberto === x.caminho ? " aberta" : "") + (x.existe ? "" : " apagada") +
    '" data-doc="' + esc(x.caminho) + '">' +
    '<span class="marcar' + (escolhido ? " on" : "") + '" data-pegar="' + esc(x.caminho) +
    '" role="checkbox" aria-checked="' + (escolhido ? "true" : "false") + '">' + ic("check", 12) + "</span>" +
    '<span class="nome-doc">' + glifo(x.nome) + '<span class="duas-linhas"><b>' + (x.fixado ? "▪ " : "") + esc(x.nome) + "</b><small>" +
    esc(x.pasta_curta || x.pasta) + (x.tipo_rotulo ? " · " + esc(x.tipo_rotulo) : "") +
    (x.cliente ? " · " + esc(x.cliente) : "") + (x.existe ? "" : " · não está mais no disco") + "</small></span></span>" +
    '<span class="quando-doc">' + esc(x.modificado || "") + "</span>" +
    '<span class="analise-doc ' + esc(estadoA) + '">' + ponto + "<span>" + esc(rotulo) + esc(quando) + "</span></span>" +
    '<button class="mais-linha" data-menu="' + esc(x.caminho) + '" title="Mais" aria-label="Mais">' + ic("more_horiz", 18) + "</button>" +
    (x.trecho ? '<div class="acervo-trecho">' + esc(x.trecho) + "</div>" : "") +
    "</div>";
}

/* A ficha do documento aberto: analise, prazos extraidos, o que o assistente
   ja identificou e o historico. Sem documento aberto, diz o que fazer. */
function painelDoAcervo() {
  const alca = '<button class="alca-painel" id="bib-alca" title="Alargar ou recolher o painel" aria-label="Alargar ou recolher o painel">' +
    ic(bib.largo ? "chevron_right" : "chevron_left", 18) + "</button>";
  const x = bib.aberto ? docDoAcervo(bib.aberto) : null;
  if (!x) {
    return '<aside class="acervo-painel">' + alca + '<div class="rolagem"><div class="painel-vazio"><h3>Nenhum documento aberto</h3>' +
      "<p>Clique numa linha para ver a ficha: análise, prazos extraídos e o que o assistente já identificou.</p></div></div></aside>";
  }

  const a = x.analise || {};
  const analisado = a.estado === "analisado";
  const prazosDoc = (bib.sugestoes || []).filter((s) => s.arquivo === x.nome);
  const ext = ((x.nome.split(".").pop() || "")).toUpperCase();
  const chave = (k, v, classe) => v
    ? '<div class="chave-valor"><span>' + k + '</span><b class="' + (classe || "") + '" title="' + esc(v) + '">' + esc(v) + "</b></div>"
    : "";
  const analise = x.tipo_rotulo
    ? esc(x.tipo_rotulo) + (x.cliente ? " de " + esc(x.cliente) : "") + (x.data ? ", com data de " + esc(x.data) : "") +
      (x.valor ? " · " + esc(x.valor) : "") + ". " + plural(x.trechos || 0, "trecho") + " lidos" +
      (x.caracteres ? " em " + milhar(x.caracteres) + " caracteres" : "") + "."
    : "Ainda não tomei vista deste documento. " + plural(x.trechos || 0, "trecho") + " indexados para busca.";

  return '<aside class="acervo-painel">' + alca + '<div class="rolagem">' +
    '<div class="painel-cabeca"><span class="titulo-painel"><h3>' + esc(x.nome) + '</h3><span class="meta">' +
    esc(ext) + " · " + tamanho(x.bytes) + (x.paginas ? " · " + plural(x.paginas, "página") : "") + " · " + esc(x.pasta_curta || "") + "</span></span>" +
    '<button class="voltar" id="bib-fechar" title="Fechar a ficha" aria-label="Fechar a ficha">' + ic("close", 18) + "</button></div>" +
    '<div class="painel-acoes"><button class="primario" data-ficha="perguntar">' + ic("forum", 16) + "Perguntar sobre este</button>" +
    '<button data-ficha="aqui">' + ic("open_in_new", 16) + "Abrir aqui</button>" +
    (ext === "PDF" ? '<button data-ficha="assinar">' + ic("draw", 16) + "Assinar</button>" : "") + "</div>" +
    '<div class="painel-bloco"><div class="painel-bloco-cabeca"><span>Análise</span><span class="' + (analisado ? "ok" : "contagem") + '">' +
    esc(a.rotulo || "sem análise") + (a.quando && !(a.rotulo || "").includes(a.quando) ? " · " + esc(a.quando) : "") + "</span></div>" +
    "<p>" + analise + "</p>" +
    (analisado ? "" : '<div><button class="com-icone" data-ficha="vista">' + ic("visibility", 16) + "Tomar vista</button></div>") + "</div>" +
    '<div class="painel-bloco"><div class="painel-bloco-cabeca"><span>Prazos extraídos</span><span class="contagem">' + prazosDoc.length + "</span></div>" +
    (prazosDoc.length
      ? '<div style="display:grid;gap:8px">' + prazosDoc.map((s, i) =>
          '<div class="prazo-cartao' + (i === 0 ? " acc" : "") + '" data-ficha="prazos"><span class="data">' + dataCurta(s.prazo) +
          '</span><span class="duas-linhas"><b>Conferir prazo</b><small>' + esc(s.lista || "") + (s.cliente ? " · " + esc(s.cliente) : "") +
          " · " + dataLonga(s.prazo) + "</small></span></div>").join("") + "</div>"
      : "<p>Nenhuma data futura lida neste documento.</p>") +
    '<button class="ligacao-painel" data-ficha="prazos">Ver todos os prazos →</button></div>' +
    '<div class="painel-chaves">' +
    chave("Cliente", x.cliente) + chave("Tipo", x.tipo_rotulo) + chave("Data no documento", x.data) +
    chave("Valor", x.valor) + chave("Pasta", x.pasta) +
    '<div class="chave-valor"><span>Fixado</span><b class="' + (x.fixado ? "ok" : "") + '">' + (x.fixado ? "sim" : "não") + "</b></div></div>" +
    '<div class="painel-bloco"><div class="painel-bloco-cabeca"><span>Histórico</span></div><div class="historico-painel">' +
    (x.visto_em ? "<span>Tomei vista · " + esc(a.quando || x.visto_em) + "</span>" : "") +
    "<span>Modificado no disco · " + esc(x.modificado || "") + "</span>" +
    "<span>Incluído do disco · " + esc(x.pasta_curta || "") + "</span></div></div>" +
    '<div class="visor-caixa" id="bib-visor"></div></div></aside>';
}

function ligarBiblioteca() {
  const centro = $("centro");
  const ordem = $("bib-ordem");
  if (ordem) ordem.onchange = (e) => { bib.ordem = e.target.value; buscarAcervo(); };
  const mais = $("bib-mais");
  if (mais) mais.onclick = () => { bib.limite += 60; buscarAcervo(); };

  centro.querySelectorAll("[data-ac-filtro]").forEach((b) => {
    b.onclick = () => { bib.filtro = b.dataset.acFiltro; bib.pastaFiltro = ""; bib.limite = 60; buscarAcervo(); };
  });
  centro.querySelectorAll("[data-ac-pasta]").forEach((b) => {
    b.onclick = () => {
      bib.pastaFiltro = bib.pastaFiltro === b.dataset.acPasta ? "" : b.dataset.acPasta;
      bib.filtro = "todos";
      buscarAcervo();
    };
  });
  centro.querySelectorAll("[data-ac-incluir]").forEach((b) => { b.onclick = adicionarPastaAoAcervo; });

  centro.querySelectorAll("[data-pegar]").forEach((c) => {
    c.onclick = (e) => {
      e.stopPropagation();
      const caminho = c.dataset.pegar;
      if (bib.escolhidos.has(caminho)) bib.escolhidos.delete(caminho); else bib.escolhidos.add(caminho);
      desenharBiblioteca();
    };
  });
  centro.querySelectorAll("[data-doc]").forEach((linha) => {
    linha.onclick = () => {
      bib.aberto = bib.aberto === linha.dataset.doc ? null : linha.dataset.doc;
      desenharBiblioteca();
    };
  });
  // Segurar o botao numa linha marca, como a caixinha; Delete apaga a selecao.
  ligarSelecao(centro, {
    linhas: ".tabela-linha[data-doc]", chave: (linha) => linha.dataset.doc, escolhidos: bib.escolhidos,
    aoMudar: desenharBiblioteca, apagar: () => acaoEmLote("apagar"),
  });
  const limpar = $("lote-limpar");
  if (limpar) limpar.onclick = (e) => { e.stopPropagation(); bib.escolhidos.clear(); desenharBiblioteca(); };
  centro.querySelectorAll("[data-lote]").forEach((b) => {
    b.onclick = (e) => { e.stopPropagation(); acaoEmLote(b.dataset.lote); };
  });
  centro.querySelectorAll("[data-menu]").forEach((b) => {
    b.onclick = (e) => { e.stopPropagation(); menuDoDocumento(b, b.dataset.menu); };
  });

  const alca = $("bib-alca");
  if (alca) alca.onclick = () => { bib.largo = !bib.largo; desenharBiblioteca(); };
  const fechar = $("bib-fechar");
  if (fechar) fechar.onclick = () => { bib.aberto = null; desenharBiblioteca(); };
  centro.querySelectorAll("[data-ficha]").forEach((b) => {
    b.onclick = () => acaoDaFicha(b.dataset.ficha);
  });
}

function acaoDaFicha(qual) {
  const x = docDoAcervo(bib.aberto);
  if (!x) return;
  if (qual === "perguntar") return perguntarSobre(x);
  if (qual === "prazos") return mostrarPrazos();
  if (qual === "vista") return tomarVista([x.caminho]);
  if (qual === "assinar") { marcarDestino("assinar"); return mostrarAssinar(); }
  if (qual === "aqui") {
    // O visor do PDF, dentro da ficha: e o de sempre, so mudou de onde e
    // chamado. O painel alarga para a pagina caber.
    bib.largo = true;
    desenharBiblioteca();
    const caixa = $("bib-visor");
    if (caixa) {
      abrirCitacao(x.nome, "", "", caixa);
      caixa.scrollIntoView({ behavior: "smooth", block: "start" });
    }
  }
}

/* A linha e identificada pelo caminho, nao pelo conteudo: dois arquivos
   iguais byte a byte tem o mesmo SHA-1, e agir por hash pegaria a copia que a
   pessoa nao marcou. Fixar continua indo por SHA-1 - ali a identidade e mesmo
   o conteudo, e mover ou renomear nao pode apagar a marca. */
function docDoAcervo(caminho) {
  return bib.documentos.find((x) => x.caminho === caminho);
}

function menuDoDocumento(botao, caminho) {
  document.querySelectorAll(".menu-conversa").forEach((m) => m.remove());
  const doc = docDoAcervo(caminho);
  if (!doc) return;

  const menu = document.createElement("div");
  menu.className = "menu-conversa";
  menu.innerHTML =
    '<button data-i="aqui">Abrir aqui</button>' +
    '<button data-i="perguntar">Perguntar sobre este</button>' +
    '<button data-i="analisar">Tomar vista de novo</button>' +
    '<button data-i="mover">Mover para pasta<span class="seta">›</span></button>' +
    '<button data-i="fixar">' + (doc.fixado ? "Desfixar" : "Fixar") + "</button>" +
    '<button data-i="pasta">Abrir a pasta no Windows</button>' +
    '<div class="menu-risco"></div>' +
    '<button class="perigo" data-i="apagar">Apagar do acervo</button>';

  const caixa = botao.getBoundingClientRect();
  menu.style.position = "fixed";
  menu.style.top = Math.min(caixa.bottom + 4, window.innerHeight - 300) + "px";
  menu.style.right = (window.innerWidth - caixa.right) + "px";
  document.body.appendChild(menu);

  const fechar = () => menu.remove();
  setTimeout(() => document.addEventListener("click", fechar, { once: true }), 0);

  menu.querySelector('[data-i="aqui"]').onclick = () => { fechar(); bib.aberto = caminho; acaoDaFicha("aqui"); };
  menu.querySelector('[data-i="perguntar"]').onclick = () => { fechar(); perguntarSobre(doc); };
  menu.querySelector('[data-i="analisar"]').onclick = () => { fechar(); tomarVista([caminho]); };
  menu.querySelector('[data-i="mover"]').onclick = () => { fechar(); bib.escolhidos = new Set([caminho]); acaoEmLote("mover"); };
  menu.querySelector('[data-i="fixar"]').onclick = async () => {
    fechar();
    await fetch("/api/biblioteca/fixar", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ sha1: doc.sha1, fixado: !doc.fixado }),
    });
    buscarAcervo();
  };
  menu.querySelector('[data-i="pasta"]').onclick = () => {
    fechar();
    fetch("/api/biblioteca/abrir-pasta", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ caminho: doc.pasta }),
    });
  };
  menu.querySelector('[data-i="apagar"]').onclick = () => {
    fechar();
    bib.escolhidos = new Set([caminho]);
    acaoEmLote("apagar");
  };
}

/* Perguntar sobre um documento e abrir a conversa com ele em foco: a pilula
   de escopo fica a vista, e a pergunta e lida SO nele. */
function perguntarSobre(doc) {
  marcarDestino("conversa");
  $("nova").click();
  setTimeout(() => {
    definirEscopo([doc.nome]);
    const campo = $("pedido");
    if (campo) campo.focus();
  }, 150);
}

async function acaoEmLote(acao) {
  const caminhos = [...bib.escolhidos];
  if (!caminhos.length) return;
  const escolhidos = caminhos.map(docDoAcervo).filter(Boolean);

  if (acao === "perguntar") {
    const nomes = escolhidos.map((x) => x.nome);
    marcarDestino("conversa");
    $("nova").click();
    setTimeout(() => { definirEscopo(nomes); $("pedido").focus(); }, 150);
    return;
  }

  if (acao === "fixar") {
    // Se todos ja estao fixados, o botao desfixa: um botao que nao faz nada
    // quando clicado duas vezes e um botao quebrado.
    const alvo = !escolhidos.every((x) => x.fixado);
    for (const sha of new Set(escolhidos.map((x) => x.sha1))) {
      await fetch("/api/biblioteca/fixar", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ sha1: sha, fixado: alvo }),
      });
    }
    bib.escolhidos.clear();
    buscarAcervo();
    return;
  }

  if (acao === "analisar") return tomarVista(caminhos);

  let destino = "";
  if (acao === "mover" || acao === "exportar") {
    destino = await escolherPastaDoSistema(
      acao === "mover" ? "Mover para qual pasta" : "Copiar para qual pasta");
    if (!destino) return;
  }

  const r = await fetch("/api/biblioteca/lote/" + acao, {
    method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ caminhos: caminhos, destino: destino }),
  });
  if (!r.ok) { avisoCert(await erroDe(r)); return; }

  const d = await r.json();
  if (!d.pedido) { avisoCert(d.aviso || "nada a fazer"); return; }

  // Nada acontece aqui: o lote vira pedido na fila, e e la que a pessoa ve o
  // plano inteiro antes de dizer sim. Um erro em lote e um erro vezes 128.
  const impedidos = (d.impedidos || []).length;
  avisoCert("Pedido na fila de aprovações: " + d.pedido.titulo +
    (impedidos ? " · " + impedidos + " ficaram de fora" : ""));
  bib.escolhidos.clear();
  desenharBiblioteca();
  contarPendencias();
  carregarStatus();
  carregarAbertos();
}

/* Ler de novo leva perto de um minuto por documento nesta maquina. O andamento
   que aparece e o numero de documentos prontos - contado, nao estimado. */
async function tomarVista(caminhos) {
  const alvo = $("bib-lista");
  const antes = alvo ? alvo.innerHTML : "";
  if (alvo) alvo.innerHTML = '<p class="nota" id="vista-passo">lendo 0 de ' + caminhos.length + "…</p>";
  atualizarSelo(true);

  try {
    const r = await fetch("/api/biblioteca/analisar", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ caminhos: caminhos }),
    });
    if (!r.ok) throw new Error(await erroDe(r));

    await lerEventos(r, (tipo, dados) => {
      const passo = $("vista-passo");
      if (tipo === "progresso" && passo) {
        passo.textContent = "lendo " + dados.indice + " de " + dados.total + " — " + dados.nome;
      }
    });
    bib.escolhidos.clear();
    bib.sugestoes = null;
    await buscarAcervo();
    avisoCert(plural(caminhos.length, "documento") + " lidos de novo");
  } catch (err) {
    if (alvo) alvo.innerHTML = antes;
    avisoCert("não consegui ler: " + err);
  } finally {
    atualizarSelo(false);
  }
}

/* Incluir pasta e o organizador: e ele que sabe varrer, classificar e trazer
   para ca. Duplicar essa varredura aqui seria manter dois caminhos para a
   mesma coisa. */
function adicionarPastaAoAcervo() {
  marcarDestino("biblioteca");
  organizarComecar();
}

/* ------------------------------------------------------------- prazos */
/*
   As datas que os documentos ja lidos pedem para conferir. Vem de
   /api/tarefas/sugestoes (datas futuras, ate 90 dias, lidas na classificacao)
   e das tarefas que ja nasceram delas. Confirmar e criar a tarefa; ignorar
   tira da lista nesta sessao. Nao ha calculo de clausula: a data e a que o
   modelo leu, e a tela diz isso.
*/

const prazos = { sugestoes: [], tarefas: [], ignorados: new Set(), aberto: null, soAbertos: true, largo: false };

async function mostrarPrazos() {
  abrirTela("Prazos", { cheia: true });
  bib.visao = "prazos";
  cabecalhoAcervo("prazos", '<button class="com-icone" id="prazos-extrair">' + ic("refresh", 16) + "Extrair de novo</button>");
  $("prazos-extrair").onclick = () => carregarPrazos(true);
  $("centro").innerHTML = '<div class="acervo sem-painel"><div class="acervo-principal"><p class="nota">lendo as datas…</p></div></div>';
  await carregarPrazos(false);
}

async function carregarPrazos(avisar) {
  try {
    const s = await (await fetch("/api/tarefas/sugestoes")).json();
    const t = await (await fetch("/api/tarefas?filtro=planejadas")).json();
    prazos.sugestoes = s.sugestoes || [];
    prazos.tarefas = (t.tarefas || []).filter((x) => /^Conferir prazo — /.test(x.titulo || ""));
    bib.sugestoes = prazos.sugestoes;
  } catch (err) {
    $("centro").innerHTML = '<div class="acervo sem-painel"><div class="acervo-principal"><p class="nota">não consegui ler: ' +
      esc(String(err)) + "</p></div></div>";
    return;
  }
  desenharPrazos();
  atualizarPostura();
  if (avisar) avisoCert("datas relidas nos documentos");
}

/* Uma lista so, ordenada por data: o que espera confirmacao e o que ja virou
   tarefa. */
function linhasDePrazos() {
  const abertos = prazos.sugestoes
    .filter((s) => !prazos.ignorados.has(s.titulo))
    .map((s) => ({
      id: "s:" + s.titulo, tipo: "sugestao", arquivo: s.arquivo, titulo: "Conferir prazo",
      prazo: s.prazo, lista: s.lista, cliente: s.cliente, estado: "confirmar", bruto: s,
    }));
  const confirmados = prazos.tarefas.map((t) => ({
    id: "t:" + t.id, tipo: "tarefa", arquivo: (t.titulo || "").replace(/^Conferir prazo — /, ""), titulo: "Conferir prazo",
    prazo: t.prazo, lista: t.lista, cliente: t.cadastro_nome || "", estado: "confirmado", bruto: t,
  }));
  return abertos.concat(confirmados).sort((a, b) => (a.prazo || "").localeCompare(b.prazo || ""));
}

function desenharPrazos() {
  const todas = linhasDePrazos();
  const abertas = todas.filter((p) => p.estado === "confirmar");
  const lista = prazos.soAbertos ? abertas : todas;
  const docs = new Set(todas.map((p) => p.arquivo));
  $("conversa-meta").textContent = plural(todas.length, "prazo") + " em " + plural(docs.size, "documento") +
    " · " + abertas.length + " aguardando sua confirmação";
  if (prazos.aberto && !todas.some((p) => p.id === prazos.aberto)) prazos.aberto = null;

  const linhas = lista.length ? lista.map((p) =>
    '<div class="tabela-linha colunas-prazos' + (prazos.aberto === p.id ? " aberta" : "") + '" data-prazo="' + esc(p.id) + '">' +
    '<span class="nome-doc">' + glifo(p.arquivo) + '<span class="duas-linhas"><b>' + esc(p.arquivo) + "</b><small>" +
    esc(p.cliente || p.lista || "") + "</small></span></span>" +
    '<span class="duas-linhas"><b>' + esc(p.titulo) + "</b><small>" +
    (p.tipo === "sugestao" ? "data lida na classificação" : "tarefa criada") + (p.lista ? " · " + esc(p.lista) : "") + "</small></span>" +
    '<span class="quando-doc">' + dataLonga(p.prazo) + "</span>" +
    (p.estado === "confirmar"
      ? '<span class="pilula-estado prazo"><i></i>Confirmar</span><span class="acoes-linha">' +
        '<button class="primario" data-confirmar="' + esc(p.id) + '">Confirmar</button>' +
        '<button data-ignorar="' + esc(p.id) + '">Ignorar</button></span>'
      : '<span class="pilula-estado ok"><i></i>Confirmado</span><span class="acoes-linha"><button data-agenda="1">Na Agenda</button></span>') +
    "</div>").join("")
    : '<p class="nota">' + (prazos.soAbertos
        ? "Nada aguardando confirmação."
        : "Os documentos lidos não trazem data nos próximos 90 dias.") + "</p>";

  $("centro").innerHTML =
    '<div class="acervo' + (prazos.largo ? " painel-largo" : "") + '"><div class="acervo-principal">' +
    '<div class="tiles"><div class="tile"><b>' + todas.length + "</b><span>Nos próximos 90 dias</span></div>" +
    '<div class="tile acc"><b>' + abertas.length + "</b><span>Aguardando sua confirmação</span></div>" +
    '<div class="tile apagado"><b>' + prazos.tarefas.length + "</b><span>Já na Agenda</span></div></div>" +
    '<div class="tabela-cartao"><div class="tabela-barra"><span class="visoes">' +
    '<button class="' + (prazos.soAbertos ? "ativa" : "") + '" data-so="1">Em aberto · ' + abertas.length + "</button>" +
    '<button class="' + (prazos.soAbertos ? "" : "ativa") + '" data-so="0">Todos · ' + todas.length + "</button></span>" +
    '<span class="nota-barra">Datas lidas na última tomada de vista</span>' +
    '<span class="direita">' + (abertas.length
      ? '<button class="primario" id="prazos-todos">' + ic("event_upcoming", 16) + "Levar todos para a Agenda</button>" : "") + "</span></div>" +
    '<div class="tabela-cabecalho colunas-prazos"><span>Documento</span><span>Prazo</span><span>Data</span><span>Status</span><span>Ação</span></div>' +
    '<div class="tabela-corpo">' + linhas + "</div>" +
    '<div class="tabela-rodape"><span>' + plural(todas.length, "prazo") + " em " + plural(docs.size, "documento") +
    '</span><span class="cresce"></span><span>Datas extraídas pelo modelo · confira no contrato antes de agir</span></div>' +
    "</div></div>" + painelDePrazo(todas) + "</div>";
  ligarPrazos();
}

function painelDePrazo(todas) {
  const alca = '<button class="alca-painel" id="prazos-alca" title="Alargar ou recolher o painel" aria-label="Alargar ou recolher o painel">' +
    ic(prazos.largo ? "chevron_right" : "chevron_left", 18) + "</button>";
  const p = todas.find((x) => x.id === prazos.aberto);
  if (!p) {
    return '<aside class="acervo-painel">' + alca + '<div class="rolagem"><div class="painel-vazio"><h3>Nenhum prazo aberto</h3>' +
      "<p>Clique numa linha para ver de onde a data veio e o que fazer com ela.</p></div></div></aside>";
  }
  const outros = todas.filter((x) => x.arquivo === p.arquivo && x.id !== p.id);
  const confirmado = p.estado === "confirmado";
  return '<aside class="acervo-painel">' + alca + '<div class="rolagem">' +
    '<div class="painel-cabeca"><span class="titulo-painel"><h3>' + esc(p.titulo) + " — " + esc(p.arquivo) + '</h3><span class="meta">' +
    esc(p.cliente || p.lista || "") + (p.cliente || p.lista ? " · " : "") + "vence " + dataLonga(p.prazo) + "</span></span>" +
    '<button class="voltar" id="prazos-fechar" title="Fechar" aria-label="Fechar">' + ic("close", 18) + "</button></div>" +
    '<div class="painel-acoes">' + (confirmado
      ? '<button data-agenda="1">' + ic("event", 16) + "Ver na Agenda</button>"
      : '<button class="primario" data-confirmar="' + esc(p.id) + '">' + ic("check", 16) + "Confirmar prazo</button>" +
        '<button data-ignorar="' + esc(p.id) + '">' + ic("visibility_off", 16) + "Ignorar</button>") +
    '<button data-abrir-doc="' + esc(p.arquivo) + '">' + ic("inventory_2", 16) + "Abrir no Acervo</button></div>" +
    '<div class="painel-bloco"><div class="painel-bloco-cabeca"><span>De onde veio</span><span class="contagem">tomada de vista</span></div>' +
    '<div class="folha-clausula"><small>Data lida na classificação</small><p>' + esc(p.arquivo) + " · " +
    (p.lista ? esc(p.lista) + " · " : "") + dataLonga(p.prazo) + "</p></div>" +
    '<div class="arquivo-painel">' + glifo(p.arquivo) + "<span>" + esc(p.arquivo) + '</span><button data-abrir-doc="' + esc(p.arquivo) + '">abrir</button></div></div>' +
    '<div class="painel-bloco"><div class="painel-bloco-cabeca"><span>Como calculei</span></div>' +
    "<p>A data é a que o modelo leu no documento ao classificá-lo — data de assinatura ou de vencimento — e ainda cai nos próximos 90 dias. " +
    "Não há cálculo de prazo em cima dela: confira no contrato antes de agir.</p></div>" +
    '<div class="painel-chaves">' +
    '<div class="chave-valor"><span>Na Agenda</span><b class="' + (confirmado ? "ok" : "") + '">' +
    (confirmado ? "sim · " + dataLonga(p.prazo) : "ainda não") + "</b></div>" +
    (p.cliente ? '<div class="chave-valor"><span>Cliente</span><b>' + esc(p.cliente) + "</b></div>" : "") +
    (p.lista ? '<div class="chave-valor"><span>Tipo</span><b>' + esc(p.lista) + "</b></div>" : "") + "</div>" +
    (outros.length
      ? '<div class="painel-bloco"><div class="painel-bloco-cabeca"><span>Também deste documento</span><span class="contagem">' + outros.length + "</span></div>" +
        outros.map((o) => '<div class="prazo-cartao" data-prazo="' + esc(o.id) + '"><span class="data">' + dataCurta(o.prazo) +
          '</span><span class="duas-linhas"><b>' + esc(o.titulo) + "</b><small>" +
          (o.estado === "confirmado" ? "confirmado · na Agenda" : "aguardando confirmação") + "</small></span></div>").join("") + "</div>"
      : "") +
    "</div></aside>";
}

function ligarPrazos() {
  const centro = $("centro");
  centro.querySelectorAll("[data-so]").forEach((b) => {
    b.onclick = () => { prazos.soAbertos = b.dataset.so === "1"; desenharPrazos(); };
  });
  centro.querySelectorAll("[data-prazo]").forEach((l) => {
    l.onclick = () => {
      const mesmo = prazos.aberto === l.dataset.prazo && l.classList.contains("tabela-linha");
      prazos.aberto = mesmo ? null : l.dataset.prazo;
      desenharPrazos();
    };
  });
  centro.querySelectorAll("[data-confirmar]").forEach((b) => {
    b.onclick = (e) => { e.stopPropagation(); confirmarPrazo(b.dataset.confirmar, false); };
  });
  centro.querySelectorAll("[data-ignorar]").forEach((b) => {
    b.onclick = (e) => {
      e.stopPropagation();
      prazos.ignorados.add(b.dataset.ignorar.slice(2));
      if (prazos.aberto === b.dataset.ignorar) prazos.aberto = null;
      desenharPrazos();
      avisoCert("prazo ignorado nesta sessão");
    };
  });
  centro.querySelectorAll("[data-agenda]").forEach((b) => {
    b.onclick = (e) => { e.stopPropagation(); marcarDestino("tarefas"); mostrarTarefas(); };
  });
  centro.querySelectorAll("[data-abrir-doc]").forEach((b) => {
    b.onclick = (e) => { e.stopPropagation(); bib.termo = b.dataset.abrirDoc; bib.pastaFiltro = ""; bib.filtro = "todos"; mostrarBiblioteca(); };
  });
  const todos = $("prazos-todos");
  if (todos) todos.onclick = async () => {
    todos.disabled = true;
    for (const p of linhasDePrazos().filter((x) => x.estado === "confirmar")) await confirmarPrazo(p.id, true);
    await carregarPrazos(false);
    avisoCert("prazos levados para a Agenda");
  };
  const alca = $("prazos-alca");
  if (alca) alca.onclick = () => { prazos.largo = !prazos.largo; desenharPrazos(); };
  const fechar = $("prazos-fechar");
  if (fechar) fechar.onclick = () => { prazos.aberto = null; desenharPrazos(); };
}

/* Confirmar e criar a tarefa: e a mesma sugestao que a tela de Tarefas
   aceita, so que daqui. */
async function confirmarPrazo(id, silencioso) {
  const p = linhasDePrazos().find((x) => x.id === id);
  if (!p || p.estado !== "confirmar") return;
  const s = p.bruto;
  await fetch("/api/tarefas", {
    method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ dados: { titulo: s.titulo, prazo: s.prazo, lista: s.lista } }),
  });
  if (silencioso) return;
  await carregarPrazos(false);
  avisoCert("prazo confirmado · tarefa criada para " + dataLonga(s.prazo));
}


function mesCurto(mes) {
  const nomes = ["janeiro", "fevereiro", "março", "abril", "maio", "junho",
                 "julho", "agosto", "setembro", "outubro", "novembro", "dezembro"];
  const partes = String(mes || "").split("-");
  return partes.length === 2 ? nomes[Number(partes[1]) - 1] : mes;
}

/* "6 pessoa(s)" ninguém escreve. O plural do português é quase sempre um "s"
   no fim; as poucas exceções desta tela já vêm escritas à mão no segundo
   argumento. */
function plural(quantos, palavra, muitos) {
  return quantos + " " + (Number(quantos) === 1 ? palavra : (muitos || palavra + "s"));
}

function emReais(centavos) {
  const sinal = centavos < 0 ? "-" : "";
  const inteiro = Math.floor(Math.abs(centavos) / 100);
  const resto = String(Math.abs(centavos) % 100).padStart(2, "0");
  return sinal + "R$ " + inteiro.toLocaleString("pt-BR") + "," + resto;
}

function centavosDe(texto) {
  const limpo = String(texto || "").replace(/[^\d,.-]/g, "").replace(/\./g, "").replace(",", ".");
  return Math.round((Number(limpo) || 0) * 100);
}


/* A proposta que a conversa devolve quando o pedido é uma ação.
   Entender não é fazer: os campos ficam à vista e editáveis, e nada entra no
   calendário de ninguém por interpretação de frase. */
function cartaoProposta(d) {
  const c = d.campos || {};
  const ehAgenda = d.tipo === "agenda";

  // Abrir é o único que não tem campo para conferir: ou é este arquivo, ou
  // não é. O que a pessoa confere é o nome — e onde quer abrir.
  if (d.tipo === "exibir") return cartaoOferta(d);
  if (d.tipo === "escopo") return cartaoEscopo(d);

  if (d.tipo === "abrir") {
    return '<div class="proposta"><div class="proposta-topo">' +
      '<span class="rotulo">vou abrir este arquivo</span>' +
      "<b>" + esc(c.nome) + "</b></div>" +
      '<p class="explica">Li isso de ' + esc(d.porque) + ". Mostro aqui na " +
      "conversa, só para leitura, ou crio um rascunho editável ao lado — o " +
      "arquivo original não é tocado. Ou abro no programa padrão do Windows.</p>" +
      '<div class="linha-form"><button class="primario" data-prop="exibir" data-nome="' + esc(c.nome) + '">Mostrar aqui</button>' +
      '<button data-prop="editar">Abrir para editar</button>' +
      '<button data-prop="fazer">Abrir no Windows</button>' +
      '<button data-prop="nao">Deixa pra lá</button></div></div>';
  }

  // Um serviço nasce da conversa: nome, cliente (como está em Cadastros) e o
  // que está sendo feito. A pessoa confere e confirma; a pasta abre em Serviços.
  if (d.tipo === "servico") {
    const explica = d.falta
      ? "Entendi que você quer abrir um serviço (" + esc(d.porque) + "), mas " + esc(d.falta) + ". Dê o nome aqui."
      : "Li isso de " + esc(d.porque) + " na sua frase. A pasta nasce em Serviços" +
        (c.cliente ? ", ligada a " + esc(c.cliente) : ", sem cliente — escreva o nome como está em Cadastros para ligar") +
        ". Confira antes — eu não gravo nada sem o seu sim.";
    return '<div class="proposta"><div class="proposta-topo">' +
      '<span class="' + (d.falta ? "pv-grau" : "rotulo") + '">' + (d.falta ? "falta um dado" : "vou abrir um serviço") + "</span>" +
      "<b>" + esc(c.nome || d.titulo || "Serviço") + "</b></div>" +
      '<div class="linha-form"><input type="text" data-pc="nome" value="' + esc(c.nome || "") + '" placeholder="nome do serviço"' + (d.falta ? " autofocus" : "") + ">" +
      '<input type="text" data-pc="cliente" value="' + esc(c.cliente || "") + '" placeholder="cliente, como está em Cadastros"></div>' +
      '<div class="linha-form"><input type="text" data-pc="descricao" value="' + esc(c.descricao || "") + '" placeholder="o que está sendo feito (opcional)"></div>' +
      '<p class="explica">' + explica + "</p>" +
      '<div class="linha-form"><button class="primario" data-prop="fazer">Abrir o serviço</button>' +
      '<button data-prop="nao">Deixa pra lá</button></div></div>';
  }

  // Cadastro e nota fiscal: ferramentas do catálogo (src/ferramentas.py).
  if (FERRAMENTAS_DA_CONVERSA[d.tipo]) return cartaoFerramenta(d);

  if (d.falta) {
    return '<div class="proposta"><div class="proposta-topo">' +
      '<span class="pv-grau">falta um dado</span>' +
      "<b>" + esc(d.titulo || "Compromisso") + "</b></div>" +
      '<p class="explica">Entendi que você quer anotar isso na agenda (' +
      esc(d.porque) + "), mas " + esc(d.falta) + ". Diga o dia — ou preencha aqui.</p>" +
      camposProposta(d, true) +
      '<div class="linha-form"><button class="primario" data-prop="fazer">Anotar</button>' +
      '<button data-prop="nao">Deixa pra lá</button></div></div>';
  }

  return '<div class="proposta"><div class="proposta-topo">' +
    '<span class="rotulo">' + (ehAgenda ? "vou anotar na agenda" : "vou criar a tarefa") +
    "</span><b>" + esc(c.titulo || d.titulo) + "</b></div>" +
    camposProposta(d, false) +
    '<p class="explica">Li isso de ' + esc(d.porque) + " na sua frase. " +
    "Confira antes — eu não gravo nada sem o seu sim.</p>" +
    '<div class="linha-form"><button class="primario" data-prop="fazer">' +
    (ehAgenda ? "Anotar na agenda" : "Criar a tarefa") + "</button>" +
    '<button data-prop="nao">Deixa pra lá</button></div></div>';
}

/* QUER VER O DOCUMENTO? Depois de uma resposta tirada de um ou dois
   documentos, o servidor oferece mostrá-los (exibir_documento). O cartão só
   oferece: nada abre sem o clique, e mostrar não copia nem altera nada. */
function cartaoOferta(d) {
  const c = d.campos || {};
  const nomes = d.nomes && d.nomes.length ? d.nomes : (c.nomes && c.nomes.length ? c.nomes : [c.nome]);
  const linhas = nomes.map((n) =>
    '<div class="oferta-doc">' + ic(/\.pdf$/i.test(n) ? "picture_as_pdf" : "description", 18) +
    '<span class="oferta-nome" title="' + esc(n) + '">' + esc(n) + "</span>" +
    '<button class="primario" data-prop="exibir" data-nome="' + esc(n) + '">Mostrar aqui</button>' +
    '<button data-prop="editar" data-nome="' + esc(n) + '">Editar</button>' +
    '<button data-prop="windows" data-nome="' + esc(n) + '">No Windows</button></div>').join("");
  const porque = d.porque || "a resposta saiu " + (nomes.length === 1 ? "deste documento" : "destes documentos");
  return '<div class="proposta oferta"><div class="proposta-topo">' +
    '<span class="rotulo">' + (nomes.length === 1 ? "quer ver o documento?" : "quer ver os documentos?") + "</span></div>" +
    linhas +
    '<p class="explica">' + esc(porque.charAt(0).toUpperCase() + porque.slice(1)) +
    ". Mostro aqui mesmo, só para leitura" + (d.trechos ? ", com os trechos citados marcados" : "") +
    " — ou abro no editor, ou no Windows.</p>" +
    '<div class="linha-form"><button data-prop="nao">Agora não</button></div></div>';
}

/* ONDE EU PROCURO? A pessoa tirou o anexo e perguntou sem nomear documento.
   Em vez de sair lendo o Acervo inteiro — minutos, neste computador —, a
   conversa pergunta. Escolher refaz a pergunta com o Retomar. */
function nomeCurto(nome) {
  return nome.length > 34 ? nome.slice(0, 32) + "…" : nome;
}

function cartaoEscopo(d) {
  const nomes = d.nomes || [];
  return '<div class="proposta"><div class="proposta-topo"><span class="rotulo">onde eu procuro?</span></div>' +
    '<p class="explica">' + (nomes.length
      ? "Você tirou o anexo. Sigo só no documento que esta conversa vinha lendo, ou procuro nos "
      : "Sem anexo, eu procuraria nos ") +
    plural(d.total || 0, "documento") + " do Acervo — ler todos leva mais tempo.</p>" +
    '<div class="linha-form">' +
    nomes.map((n, i) => "<button" + (i === 0 ? ' class="primario"' : "") + ' data-escopo-doc="' + esc(n) +
      '" title="' + esc(n) + '">Só em “' + esc(nomeCurto(n)) + "”</button>").join("") +
    "<button" + (nomes.length ? "" : ' class="primario"') + ' data-escopo-tudo="1">Em todo o Acervo</button>' +
    '<button data-escopo-anexar="1">Anexar outro</button></div></div>';
}

function ligarEscopo(caixa, d) {
  const escolher = (aviso, opcoes) => {
    caixa.innerHTML = '<p class="explica">' + esc(aviso) + "</p>";
    enviar(Object.assign({ texto: d.pergunta, retomar: true }, opcoes));
  };
  caixa.querySelectorAll("[data-escopo-doc]").forEach((b) => {
    b.onclick = () => {
      const nome = b.dataset.escopoDoc;
      definirEscopo([nome]);
      escolher("Procurando só em “" + nome + "”.", { apenas: [nome] });
    };
  });
  const tudo = caixa.querySelector("[data-escopo-tudo]");
  if (tudo) tudo.onclick = () => {
    definirEscopo([]);
    estado.escopoTudo = true;
    escolher("Procurando em todo o Acervo.", { tudo: true });
  };
  const anexar = caixa.querySelector("[data-escopo-anexar]");
  if (anexar) anexar.onclick = () => abrirAnexar();
}

/* O visor dentro da conversa: as PÁGINAS do documento, empilhadas, como no
   editor. Um visor só para PDF e Word — antes eram dois (a página desenhada
   do PDF e o Word em parágrafos corridos), e o mesmo documento parecia duas
   coisas diferentes conforme o formato. O Word é desenhado a partir do PDF
   que o gerador do editor monta. As páginas onde estão os trechos citados
   ganham o fio de destaque, e o visor já abre na primeira delas. */
function srcDaPagina(nome, pagina) {
  return "/api/biblioteca/pagina?nome=" + encodeURIComponent(nome) + "&numero=" + pagina + "&largura=1100";
}

function leitorNaConversa(reg) {
  const citadas = reg.citadas || [];
  const topo = '<div class="proposta-topo leitor-topo"><span class="rotulo">só leitura</span>' +
    '<b class="oferta-nome" title="' + esc(reg.nome) + '">' + esc(reg.nome) + "</b>" +
    '<span class="explica leitor-conta">' + plural(reg.paginas || 1, "página") + "</span>" +
    (citadas.length
      ? '<button class="leitor-ir" data-leitor-ir="' + citadas[0] + '">' + ic("format_quote", 16) +
        (citadas.length === 1 ? "trecho citado na pág. " + citadas[0] : "trechos nas págs. " + citadas.join(", ")) + "</button>"
      : "") +
    '<button class="botao-icone" data-visor="fechar" title="Fechar" aria-label="Fechar">' + ic("close", 18) + "</button></div>";
  let paginas = "";
  for (let n = 1; n <= (reg.paginas || 1); n++) {
    const classe = citadas.includes(n) ? "leitor-folha citada" : "leitor-folha";
    paginas += '<img class="' + classe + '" data-leitor-pagina="' + n + '" loading="lazy" alt="página ' + n +
      '" src="' + srcDaPagina(reg.nome, n) + '">';
  }
  return '<div class="proposta leitor-conversa">' + topo +
    '<div class="leitor-paginas">' + paginas + "</div>" +
    '<div class="linha-form"><button data-prop="editar" data-nome="' + esc(reg.nome) + '">Abrir para editar</button>' +
    '<button data-prop="windows" data-nome="' + esc(reg.nome) + '">Abrir no Windows</button></div></div>';
}

function ligarLeitor(caixa, reg, d) {
  const rolagem = caixa.querySelector(".leitor-paginas");
  const irPara = (n, suave) => {
    const folha = rolagem.querySelector('[data-leitor-pagina="' + n + '"]');
    if (!folha) return;
    rolagem.scrollTo({
      top: rolagem.scrollTop + folha.getBoundingClientRect().top - rolagem.getBoundingClientRect().top - 12,
      behavior: suave && animacoesLigadas() ? "smooth" : "auto",
    });
  };
  const ir = caixa.querySelector("[data-leitor-ir]");
  if (ir) {
    ir.onclick = () => irPara(Number(ir.dataset.leitorIr), true);
    irPara((reg.citadas || [])[0], false);
  }

  caixa.querySelector('[data-visor="fechar"]').onclick = () => {
    caixa.innerHTML = '<div class="proposta oferta"><div class="oferta-doc">' +
      ic(reg.origem === "pdf" ? "picture_as_pdf" : "description", 18) +
      '<span class="oferta-nome" title="' + esc(reg.nome) + '">' + esc(reg.nome) + "</span>" +
      '<button data-prop="exibir" data-nome="' + esc(reg.nome) + '">Mostrar de novo</button></div></div>';
    ligarBotoesDeDocumento(caixa, d);
  };
  ligarBotoesDeDocumento(caixa, d);
}

function rascunhoDaConversa(nome) {
  return ((estado.trabalho || {}).mensagens || []).some((m) =>
    m.feito && m.feito.tipo === "editar" && m.feito.nome === nome);
}

/* Mostrar aqui, abrir no Windows e abrir para editar: os mesmos três botões
   no cartão de abrir, na oferta depois da resposta e dentro do visor. O nome
   vem do botão — a oferta pode ter dois documentos. */
function ligarBotoesDeDocumento(caixa, d) {
  const nomeDe = (b) => b.dataset.nome || (d.campos || {}).nome;

  caixa.querySelectorAll('[data-prop="exibir"]').forEach((b) => {
    b.onclick = async () => {
      b.disabled = true;
      const r = await fetch("/api/trabalhos/" + estado.trabalhoId + "/fazer", {
        method: "POST", headers: { "Content-Type": "application/json" },
        // Os trechos da resposta vão junto: o visor abre na página deles.
        body: JSON.stringify({ tipo: "exibir", campos: {
          nome: nomeDe(b), trechos: ((d.trechos || {})[nomeDe(b)] || []),
        } }),
      });
      if (!r.ok) {
        b.disabled = false;
        caixa.insertAdjacentHTML("beforeend", '<p class="explica">Não consegui mostrar: ' + esc(await erroDe(r)) + "</p>");
        return;
      }
      const reg = (await r.json()).registro;
      caixa.innerHTML = leitorNaConversa(reg);
      ligarLeitor(caixa, reg, d);
      if (pertoDoFim()) rolar();
    };
  });

  caixa.querySelectorAll('[data-prop="windows"]').forEach((b) => {
    b.onclick = async () => {
      b.disabled = true;
      const r = await fetch("/api/trabalhos/" + estado.trabalhoId + "/fazer", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ tipo: "abrir", campos: { nome: nomeDe(b) } }),
      });
      if (!r.ok) {
        b.disabled = false;
        avisoNaJanela("Não consegui abrir: " + (await erroDe(r)), { icone: "error" });
        return;
      }
      b.textContent = "Aberto no Windows";
    };
  });

  /* Abrir para editar traz o documento para dentro do programa, como rascunho:
     o .docx de origem pode já ter sido assinado ou protocolado, e editar ele
     no lugar seria mexer no que já saiu. O rascunho fica ligado à conversa:
     o cartão continua aqui, e clicar de novo volta ao MESMO rascunho — antes
     o cartão sumia, e cada clique criava outra cópia. */
  caixa.querySelectorAll('[data-prop="editar"]').forEach((editar) => {
    if (rascunhoDaConversa(nomeDe(editar))) editar.textContent = "Voltar ao editor";
    editar.onclick = async () => {
      editar.disabled = true;
      const r = await fetch("/api/documentos/importar", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ nome: nomeDe(editar), trabalho_id: estado.trabalhoId || "" }),
      });
      editar.disabled = false;
      if (!r.ok) {
        avisoNaJanela("Não consegui abrir no editor: " + (await erroDe(r)), { icone: "error" });
        return;
      }
      const novo = await r.json();
      editar.textContent = "Voltar ao editor";
      if (!novo.reaberto && estado.trabalho) {
        estado.trabalho.mensagens.push({ autor: "paulus", texto: "Abri “" + novo.de + "” para editar.",
          feito: { tipo: "editar", id: novo.id, nome: novo.de } });
      }
      mostrarDupla(novo.id);
    };
  });
}

/* As ferramentas que a conversa propõe e a tela confere. Cada campo é um
   parâmetro do catálogo do servidor; o que a pessoa corrigir aqui é o que
   vai para /fazer, e o servidor confere de novo (CPF pelo dígito, valor em
   centavos). */
const FERRAMENTAS_DA_CONVERSA = {
  cadastro: {
    rotulo: "vou cadastrar o cliente", botao: "Cadastrar", padrao: "Cliente",
    campos: [["nome", "nome completo ou razão social"], ["documento", "CPF ou CNPJ"],
      ["telefone", "telefone com DDD"], ["email", "e-mail"],
      ["endereco", "endereço"], ["observacao", "anotação (opcional)"]],
  },
  nota: {
    rotulo: "vou preparar a NFS-e", botao: "Conferir a nota", padrao: "NFS-e",
    campos: [["cliente", "cliente, como está em Cadastros"], ["valor", "valor, em reais"],
      ["descricao", "serviço prestado"], ["data", "data de emissão", "date"]],
  },
};

const NOMES_DE_CAMPO = {
  nome: "o nome", documento: "o CPF/CNPJ", telefone: "o telefone", email: "o e-mail",
  endereco: "o endereço", cliente: "o cliente", valor: "o valor", descricao: "a descrição",
  data: "a data", titulo: "o título", hora: "a hora",
};

function cartaoFerramenta(d) {
  const cfg = FERRAMENTAS_DA_CONVERSA[d.tipo];
  const c = d.campos || {};
  let focou = false;
  const entradas = cfg.campos.map((f) => {
    let valor = c[f[0]] || "";
    // O servidor manda o valor em centavos; a pessoa lê e escreve em reais.
    if (f[0] === "valor" && typeof valor === "number") valor = emReais(valor);
    let foco = "";
    if (d.falta && !valor && !focou) { foco = " autofocus"; focou = true; }
    return '<input type="' + (f[2] || "text") + '" data-pc="' + f[0] + '" value="' + esc(valor) +
      '" placeholder="' + esc(f[1]) + '"' + foco + ">";
  });
  let linhas = "";
  for (let i = 0; i < entradas.length; i += 2) {
    linhas += '<div class="linha-form">' + entradas.slice(i, i + 2).join("") + "</div>";
  }

  // Quando a regra não bastou e o modelo completou, a tela diz o quê: é o
  // campo que mais merece um segundo olhar.
  const ajudou = (d.ajuda_do_modelo || []).map((n) => NOMES_DE_CAMPO[n] || n);
  const ajuda = ajudou.length
    ? " O modelo local completou " + ajudou.join(", ") + " — confira com atenção."
    : "";
  const garantia = d.disponivel === false
    ? " A emissão ainda não está ligada: confirmar confere os dados, mas nada é enviado nem gravado."
    : " Confira antes — eu não gravo nada sem o seu sim.";
  const explica = d.falta
    ? "Entendi o pedido (" + d.porque + "), mas " + d.falta + ". Complete aqui."
    : "Li isso de " + d.porque + " na sua frase.";
  const classe = d.falta ? "pv-grau" : "rotulo";

  return '<div class="proposta"><div class="proposta-topo">' +
    '<span class="' + classe + '">' + (d.falta ? "falta um dado" : cfg.rotulo) + "</span>" +
    "<b>" + esc(c.nome || c.cliente || d.titulo || cfg.padrao) + "</b></div>" +
    linhas +
    '<p class="explica">' + esc(explica + ajuda + garantia) + "</p>" +
    '<div class="linha-form"><button class="primario" data-prop="fazer">' + cfg.botao + "</button>" +
    '<button data-prop="nao">Deixa pra lá</button></div></div>';
}

/* "1440 minutos antes" ninguém lê. A unidade acompanha o tamanho do número. */
function rotuloDoAviso(minutos) {
  if (!minutos) return "não avisar";
  if (minutos < 60) return plural(minutos, "minuto") + " antes";
  if (minutos < 1440) return plural(minutos / 60, "hora") + " antes";
  return plural(minutos / 1440, "dia") + " antes";
}

function camposProposta(d, faltando) {
  const c = d.campos || {};
  const ehAgenda = d.tipo === "agenda";
  return '<div class="linha-form">' +
    '<input type="text" data-pc="titulo" value="' + esc(c.titulo || d.titulo || "") +
    '" placeholder="do que se trata">' +
    '<input type="date" data-pc="' + (ehAgenda ? "data" : "prazo") + '" value="' +
    esc(c.data || c.prazo || "") + '"' + (faltando ? " autofocus" : "") + ">" +
    (ehAgenda
      ? '<input type="time" data-pc="hora" value="' + esc(c.hora || "09:00") + '">'
      : "") +
    "</div>" +
    (ehAgenda
      ? '<div class="linha-form"><label class="explica">avisar antes</label>' +
        '<select data-pc="avisar_min">' +
        [0, 5, 10, 15, 30, 60, 120, 1440].map((m) =>
          '<option value="' + m + '"' + (Number(c.avisar_min || 0) === m ? " selected" : "") +
          ">" + rotuloDoAviso(m) + "</option>").join("") +
        "</select></div>"
      : "");
}

/* Ligar os botões do cartão. O que vai para o servidor é o que está nos
   campos — a pessoa pode ter corrigido a data antes de confirmar. */
function ligarProposta(caixa, d, ondeResponder) {
  if (d.tipo === "escopo") return ligarEscopo(caixa, d);
  const fazer = caixa.querySelector('[data-prop="fazer"]');
  const nao = caixa.querySelector('[data-prop="nao"]');
  ligarBotoesDeDocumento(caixa, d);

  if (nao) nao.onclick = () => {
    caixa.innerHTML = '<p class="explica">' + (d.tipo === "exibir"
      ? "Tudo bem — se quiser ver depois, é só pedir: “mostre o documento”."
      : "Tudo bem — não anotei nada.") + "</p>";
  };

  if (!fazer) return;
  fazer.onclick = async () => {
    const campos = Object.assign({}, d.campos);
    caixa.querySelectorAll("[data-pc]").forEach((el) => {
      campos[el.dataset.pc] = el.dataset.pc === "avisar_min" ? Number(el.value) : el.value;
    });
    if (d.tipo === "tarefa" && campos.prazo && campos.hora) {
      campos.lembrar_em = campos.prazo + " " + campos.hora;
    }

    fazer.disabled = true;
    const r = await fetch("/api/trabalhos/" + estado.trabalhoId + "/fazer", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ tipo: d.tipo, campos: campos }),
    });
    if (!r.ok) {
      fazer.disabled = false;
      caixa.insertAdjacentHTML("beforeend",
        '<p class="explica">Não consegui: ' + esc(await erroDe(r)) + "</p>");
      return;
    }

    const feito = await r.json();
    // Pendente é a ferramenta que ainda só confere (a NFS-e): não há o que
    // ver na tela, e o rótulo não pode dizer "feito".
    const classe = feito.pendente ? "pv-grau" : "rotulo";
    caixa.innerHTML = '<div class="proposta-topo"><span class="' + classe + '">' +
      (feito.pendente ? "conferido" : "feito") + "</span>" +
      "<b>" + esc(feito.resumo) + "</b></div>" +
      (feito.onde
        ? '<div class="linha-form"><button data-ver="' + esc(feito.onde) + '">Ver na tela</button></div>'
        : "");
    const ver = caixa.querySelector("[data-ver]");
    if (ver) ver.onclick = () => {
      marcarDestino(feito.onde);
      if (feito.onde === "calendario") mostrarCalendario();
      else if (feito.onde === "tarefas") mostrarTarefas();
      else if (feito.onde === "servicos") abrirServico(Number(feito.id));
      else if (feito.onde === "cadastros") mostrarCadastros();
      else mostrarBiblioteca();
    };
    carregarStatus();
  };
}


