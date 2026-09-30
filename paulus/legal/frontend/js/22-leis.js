/* ------------------------------------------------------------ conexões */
/* A tela virou a secao Conexoes de Configuracoes. */

/* ------------------------------------------------------- códigos de lei */
/*
   Citar artigo passou a ser consulta a um índice, não palpite. O texto do
   artigo aparece junto da citação — quem insere confere antes.
*/

const lei = { codigos: [], termo: "", codigo: "", achados: [] };

/* Os painéis do editor nascem abaixo da folha, e a folha é do tamanho de uma
   página: sem isto, clicar no botão abria o painel fora da tela e parecia que
   nada tinha acontecido. */
function revelarAbaixo() {
  const alvo = $("ed-abaixo");
  if (alvo && alvo.firstChild) alvo.scrollIntoView({ behavior: "smooth", block: "nearest" });
}

async function painelCodigos() {
  const alvo = $("ed-abaixo");
  alvo.innerHTML = '<p class="nota">abrindo os códigos…</p>';

  let d;
  try {
    d = await (await fetch("/api/leis")).json();
  } catch (err) {
    alvo.innerHTML = '<p class="nota">não consegui abrir: ' + esc(String(err)) + "</p>";
    return;
  }
  lei.codigos = d.codigos;
  const instalados = d.codigos.filter((c) => c.instalado);

  if (!instalados.length) {
    alvo.innerHTML = '<div class="painel" style="margin-top:16px"><h3>Nenhum código instalado</h3>' +
      '<p class="explica">' + esc(d.porque) + "</p>" +
      '<p class="explica">' + esc(d.como_baixar) + "</p>" +
      '<div class="linha-form"><button class="primario" id="lei-ir-config">Instalar em Configurações</button></div>' +
      "</div>";
    $("lei-ir-config").onclick = () => { marcarDestino("config"); mostrarConfig("assistente"); };
    revelarAbaixo();
    return;
  }

  alvo.innerHTML = '<div class="painel" style="margin-top:16px"><h3>Citar a lei</h3>' +
    '<p class="explica">Procure pelo número do artigo ou por palavra. O texto aparece ' +
    "aqui para você conferir antes de inserir.</p>" +
    '<div class="linha-form"><input type="text" id="lei-termo" placeholder="421, boa-fé, tutela de urgência…">' +
    '<button class="primario" id="lei-buscar">Procurar</button></div>' +
    '<div class="chips" style="margin-top:8px">' +
    '<button class="chip' + (lei.codigo ? "" : " on") + '" data-leicod="">Todos</button>' +
    instalados.map((c) =>
      '<button class="chip' + (lei.codigo === c.codigo ? " on" : "") +
      '" data-leicod="' + esc(c.codigo) + '">' + esc(c.codigo.toUpperCase()) +
      '<span class="caminho">' + c.artigos + "</span></button>").join("") + "</div>" +
    '<div id="lei-achados"></div></div>';

  const buscar = () => {
    lei.termo = $("lei-termo").value.trim();
    procurarLei();
  };
  $("lei-buscar").onclick = buscar;
  $("lei-termo").onkeydown = (e) => { if (e.key === "Enter") buscar(); };
  alvo.querySelectorAll("[data-leicod]").forEach((b) => {
    b.onclick = () => { lei.codigo = b.dataset.leicod; painelCodigos(); if (lei.termo) procurarLei(); };
  });
  if (lei.termo) { $("lei-termo").value = lei.termo; procurarLei(); }
  revelarAbaixo();
  $("lei-termo").focus();
}

async function procurarLei() {
  const alvo = $("lei-achados");
  if (!alvo || !lei.termo) return;
  alvo.innerHTML = '<p class="nota">procurando…</p>';

  const r = await fetch("/api/leis/procurar?termo=" + encodeURIComponent(lei.termo) +
    "&codigo=" + encodeURIComponent(lei.codigo));
  if (!r.ok) { alvo.innerHTML = '<p class="explica">' + esc(await erroDe(r)) + "</p>"; return; }

  const d = await r.json();
  lei.achados = d.achados;

  if (d.sem_codigo) { alvo.innerHTML = '<p class="explica">' + esc(d.aviso) + "</p>"; return; }
  if (!d.achados.length) {
    alvo.innerHTML = '<p class="explica">Nada achado com esse termo nos códigos instalados. ' +
      "Isso quer dizer que não achei — não que não exista.</p>";
    return;
  }

  alvo.innerHTML = '<div style="margin-top:12px">' + d.achados.map((a, i) =>
    '<div class="artigo' + (a.revogado ? " revogado" : "") + '">' +
    '<div class="artigo-topo"><b>' + esc(a.citacao) + "</b>" +
    (a.revogado ? '<span class="etiqueta prazo">revogado</span>' : "") +
    (a.alterado_por ? '<span class="rotulo">' + esc(a.alterado_por) + "</span>" : "") +
    "</div>" +
    (a.contexto ? '<span class="rotulo">' + esc(a.contexto) + "</span>" : "") +
    '<p class="artigo-texto">' + esc(a.texto.slice(0, 620)) +
    (a.texto.length > 620 ? "…" : "") + "</p>" +
    '<div class="linha-form">' +
    '<button data-citar="' + i + '">Inserir a citação</button>' +
    '<button data-transcrever="' + i + '">Inserir com o texto</button>' +
    // L10: como estava numa data (js/71-vigencia.js).
    (typeof vigenciaDoArtigo === "function" ? '<button data-vigencia="' + i + '">' + ic("history", 16) + "Vigência</button>" : "") + "</div>" +
    '<div class="lei-biblioteca" data-lei-bib="' + i + '" hidden></div>' +
    '<div class="lei-biblioteca" data-lei-pos="' + i + '" hidden></div></div>').join("") + "</div>";

  alvo.querySelectorAll("[data-citar]").forEach((b) => {
    b.onclick = () => inserirCitacao(lei.achados[Number(b.dataset.citar)], false);
  });
  alvo.querySelectorAll("[data-vigencia]").forEach((b) => {
    b.onclick = () => vigenciaDoArtigo(lei.achados[Number(b.dataset.vigencia)]);
  });
  alvo.querySelectorAll("[data-transcrever]").forEach((b) => {
    b.onclick = () => inserirCitacao(lei.achados[Number(b.dataset.transcrever)], true);
  });
  /* Os primeiros artigos ganham o que a biblioteca do escritório diz deles. */
  d.achados.slice(0, 5).forEach((a, i) => naBibliotecaDoEscritorio(a, alvo.querySelector('[data-lei-bib="' + i + '"]')));
  // L5: a posição da casa e os temas do STJ sobre o artigo (js/67-fundamentacao.js).
  if (typeof posicaoDaCasa === "function") d.achados.slice(0, 5).forEach((a, i) => posicaoDaCasa(a, alvo.querySelector('[data-lei-pos="' + i + '"]')));
  revelarAbaixo();
}

/* "Na biblioteca do escritório" (Biblioteca, M3): as obras que citam este
   artigo, com obra, autor, edição e página, e um trecho curto. Artigo sem
   obra diz isso - e não mostra trecho "parecido". */
async function naBibliotecaDoEscritorio(a, caixa) {
  if (!caixa || !a) return;
  let d;
  try {
    const r = await fetch("/api/leis/anotacoes?codigo=" + encodeURIComponent(a.codigo) + "&numero=" + encodeURIComponent(a.numero));
    if (!r.ok) return;
    d = await r.json();
  } catch (err) { return; }
  if (!d.ligada) return;
  caixa.hidden = false;
  const lista = d.anotacoes || [];
  caixa.innerHTML = '<span class="rotulo">Na biblioteca do escritório</span>' + (lista.length
    ? lista.map((n, j) => '<div class="lei-bib-item"><div class="lei-bib-onde"><b>' + esc(n.obra) + "</b>" +
        '<small>' + esc([n.autor, [n.edicao ? n.edicao + " ed." : "", n.ano].filter(Boolean).join(", "), n.pagina ? "p. " + n.pagina : ""].filter(Boolean).join(" · ")) + "</small>" +
        (n.aviso ? '<span class="etiqueta atencao">' + esc(n.aviso) + "</span>" : "") + "</div>" +
        (n.teses && n.teses.length ? n.teses.map((x) => '<p class="lei-bib-tese"><b>Tese do autor:</b> ' + esc(x) + "</p>").join("") : "") +
        '<p class="lei-bib-trecho">“' + esc(n.trecho) + "”</p>" +
        (n.pdf && n.pagina ? '<button data-lei-bib-abrir="' + j + '">' + ic("menu_book", 16) + "abrir na página</button>" : "") + "</div>").join("")
    : '<p class="nota">' + esc(d.mensagem) + "</p>");
  caixa.querySelectorAll("[data-lei-bib-abrir]").forEach((b) => {
    b.onclick = () => { const n = lista[Number(b.dataset.leiBibAbrir)]; abrirMaterialNaPagina(n.material_id, n.pagina, n.obra); };
  });
}

/* O arquivo do próprio escritório, no visor de PDF do programa, já na página. */
function abrirMaterialNaPagina(id, pagina, titulo) {
  dialogo({
    titulo: titulo || "Material", contexto: "Biblioteca do escritório · página " + pagina, larga: true, classe: "dialogo-pdf",
    html: '<iframe class="visor-pdf" title="' + esc(titulo || "") + '" src="/api/material/' + encodeURIComponent(id) + "/arquivo#page=" + Number(pagina) + '"></iframe>',
    confirmar: "Fechar", semCancelar: true,
  });
}

/* Artigo revogado nunca entra sem a pessoa dizer que quer: citar um artigo que
   não está mais em vigor é o erro mais caro que esta tela pode cometer. */
async function inserirCitacao(a, comTexto) {
  if (!a) return;
  if (a.revogado && !(await confirmar({ titulo: "Artigo revogado", contexto: a.citacao, texto: "O " + a.citacao + " está revogado: continua no texto compilado por referência histórica, mas não está em vigor.", confirmar: "Inserir mesmo assim", perigo: true }))) return;

  const folha = $("ed-folha");
  if (!folha) { avisoCert("abra um documento para inserir a citação"); return; }

  const bloco = document.createElement("p");
  bloco.textContent = comTexto
    ? "Nos termos do " + a.citacao + ": “" + a.texto.replace(/\s+/g, " ").slice(0, 900) + "”"
    : "(" + a.citacao + ")";
  folha.appendChild(bloco);
  marcarSujo();
  avisoCert(a.citacao + " inserido no fim do documento" + (a.revogado ? " — artigo revogado" : ""));
}

/* ------------------------------------------------ instalar em Configurações */

/* O seletor de pasta do Windows só existe na janela do programa; no navegador
   o caminho é digitado, e a tela diz qual dos dois está acontecendo. */
async function escolherPastaDoSistema(titulo) {
  if (window.pywebview && window.pywebview.api && window.pywebview.api.escolher_pasta) {
    try {
      const escolhida = await window.pywebview.api.escolher_pasta();
      if (escolhida) return escolhida;
    } catch (err) { /* cai para o campo digitado */ }
  }
  return perguntar({ titulo: titulo, contexto: "Esta máquina", campo: { rotulo: "Caminho da pasta", placeholder: "C:\\Users\\você\\Documentos\\Contratos", icone: "folder" }, confirmar: "Usar esta pasta" });
}

