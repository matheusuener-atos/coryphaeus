/* --------------------------------------------- assinar documento (A8) */

const assina = {
  doc: null, cofre: null, pagina: 1, x: null, y: null,
  paginas: "ultima", intervalo: "", posicao: "rodape_direita",
  baixar: true, biblioteca: true, manter: true, senhaPdf: "", proteger: false, repetir: true,
  pdfs: [], feito: null,
};

async function mostrarAssinar(caminho) {
  abrirTela("Assinatura", { cheia: true });
  marcarDestino("assinar");
  cert.visao = "assinar";
  assina.feito = null;
  const centro = $("centro");
  centro.innerHTML = '<div class="acervo sem-painel"><div class="acervo-principal"><p class="nota">abrindo…</p></div></div>';

  try {
    cert.dados = await (await fetch("/api/certificado")).json();
  } catch (err) {
    centro.innerHTML = '<div class="acervo sem-painel"><div class="acervo-principal"><p class="nota">não consegui abrir: ' + esc(String(err)) + "</p></div></div>";
    return;
  }

  assina.doc = null;
  if (caminho) {
    const r = await fetch("/api/assinar/documento?arquivo=" + encodeURIComponent(caminho));
    if (!r.ok) {
      avisoCert(await erroDe(r));
    } else {
      const d = await r.json();
      assina.doc = d.documento;
      assina.cofre = d;
      assina.pagina = d.documento.paginas;
      assina.paginas = "ultima";
      assina.intervalo = "";
      assina.x = assina.y = null;
      assina.posicao = (d.selo && d.selo.posicao) || "rodape_direita";
    }
  }
  if (!assina.doc) {
    try { assina.pdfs = (await (await fetch("/api/assinar/pdfs")).json()).pdfs; } catch (err) { assina.pdfs = []; }
  }
  desenharAssinatura();
  atualizarPostura();
}

/* ---------------------------------------------------- escolher o PDF */

function listaDePdfs() {
  const linhas = assina.pdfs.map((p) =>
    '<div class="tabela-linha colunas-pdfs" data-pdf="' + esc(p.path) + '">' +
    '<span class="nome-doc">' + glifo(p.nome) + '<span class="duas-linhas"><b>' + esc(p.nome) + "</b><small>" +
    (p.paginas ? plural(p.paginas, "página") + " · " : "") + String(p.mb).replace(".", ",") + " MB</small></span></span>" +
    '<span class="quando-doc">PDF do Acervo</span><span class="acoes-linha"><button data-pdf-abrir="' + esc(p.path) + '">Abrir</button></span></div>').join("");
  return '<div class="tabela-cartao"><div class="tabela-barra"><span class="selecao">' + plural(assina.pdfs.length, "PDF", "PDFs") + " que já conheço</span>" +
    '<span class="nota-barra">só assino PDF · outro arquivo? escolha no computador</span></div>' +
    '<div class="tabela-corpo">' + (linhas || '<div class="ag-vazio"><h4>Nenhum PDF no acervo ainda</h4><p>Inclua a pasta onde eles estão, ou escolha um arquivo direto no computador — eu subo uma cópia para o Acervo e assino a cópia.</p></div>') + "</div>" +
    '<div class="tabela-rodape"><button class="com-icone" id="assina-escolher">' + ic("folder_open", 16) + "Escolher um PDF no computador</button>" +
    '<input type="file" id="assina-arquivo" accept=".pdf" hidden><span class="cresce"></span><span>a assinatura é feita nesta máquina com o seu certificado</span></div></div>';
}

function cartaoDoCertificadoEmUso() {
  const d = cert.dados || {};
  const c = d.certificado;
  if (!d.instalado || !c) {
    return '<div class="as-cert"><span class="as-cert-ic">' + ic("workspace_premium", 22) + '</span><span class="duas-linhas"><b>Nenhum certificado instalado</b>' +
      '<small>instale o arquivo .pfx do seu e-CPF para assinar</small></span><button class="em-ligacao forte" data-as-visao="certificado">instalar</button></div>';
  }
  return '<div class="as-cert"><span class="as-cert-ic">' + ic("workspace_premium", 22) + '</span><span class="duas-linhas"><b>' + esc(c.titular || "Certificado instalado") + "</b><small>" +
    esc(c.tipo || "A1") + (c.emissor ? " · " + esc(c.emissor) : "") + (c.valido_ate ? " · até " + esc(dataBR(c.valido_ate)) : "") + "</small></span>" +
    '<button class="em-ligacao forte" data-as-visao="certificado">trocar</button></div>';
}

function painelSemDocumento() {
  return '<aside class="acervo-painel">' + alcaDaAssinatura() + '<div class="rolagem as-painel">' +
    '<div class="painel-cabeca"><span class="titulo-painel"><h3>Antes de assinar</h3><span class="meta">escolha o PDF na lista</span></span></div>' +
    '<div class="painel-bloco"><div class="painel-bloco-cabeca"><span>Com qual certificado</span>' + seloDeSituacao() + "</div>" + cartaoDoCertificadoEmUso() + "</div>" +
    '<div class="painel-bloco"><div class="painel-bloco-cabeca"><span>Como funciona</span></div>' +
    "<p>Você escolhe as páginas e onde o selo fica; o selo é o desenho, a assinatura é o dado criptográfico que cobre o documento inteiro.</p>" +
    "<p>Vou pedir sua confirmação e a senha do certificado antes de gravar. O original nunca é sobrescrito: o assinado nasce ao lado.</p>" +
    "<p>Nada é enviado para a internet.</p></div></div></aside>";
}

function ligarListaDePdfs() {
  const raiz = $("assinatura");
  raiz.querySelectorAll("[data-pdf], [data-pdf-abrir]").forEach((b) => {
    b.onclick = (e) => { e.stopPropagation(); mostrarAssinar(b.dataset.pdf || b.dataset.pdfAbrir); };
  });
  /* O navegador nao entrega o caminho do arquivo escolhido, so o conteudo.
     Como o assinador precisa do arquivo no disco, este botao sobe uma copia
     para o acervo e assina a copia. */
  const campo = $("assina-arquivo");
  const escolher = () => campo.click();
  $("assina-escolher").onclick = escolher;
  const topo = $("assina-escolher-topo");
  if (topo) topo.onclick = escolher;
  campo.onchange = async () => {
    if (!campo.files[0]) return;
    const forma = new FormData();
    forma.append("arquivos", campo.files[0]);
    const r = await fetch("/api/upload", { method: "POST", body: forma });
    if (!r.ok) { avisoCert(await erroDe(r)); return; }
    const pdfs = (await (await fetch("/api/assinar/pdfs")).json()).pdfs;
    const achado = pdfs.find((p) => p.nome === campo.files[0].name);
    if (achado) mostrarAssinar(achado.path); else avisoCert("o arquivo subiu, mas não achei o PDF na lista");
  };
}

/* --------------------------------------------------- o visor e o selo */

function visorParaAssinar() {
  const doc = assina.doc;
  const alvos = new Set(paginasEscolhidas());
  const total = Math.min(doc.paginas, 40);
  const minis = [];
  for (let i = 1; i <= total; i += 1) {
    const classe = "docs-mini" + (i === assina.pagina ? " atual" : "");
    minis.push('<button class="' + classe + '" data-pdf-pagina="' + i + '"><img alt="" src="/api/assinar/pagina?arquivo=' +
      encodeURIComponent(doc.caminho) + "&numero=" + i + '&largura=96"><span>' + i + "</span>" +
      (alvos.has(i) ? '<i class="as-mini-selo"></i>' : "") + "</button>");
  }
  return '<div class="as-cartao"><div class="docs-status">' +
    '<button class="voltar" id="pdf-antes" title="Página anterior">' + ic("chevron_left", 18) + "</button>" +
    '<span class="docs-pagina-num">Pág. <b id="pdf-num">' + assina.pagina + "</b> / " + doc.paginas + "</span>" +
    '<button class="voltar" id="pdf-depois" title="Próxima página">' + ic("chevron_right", 18) + "</button>" +
    '<span class="docs-divisa-fina"></span><span>lido da sua máquina</span><span class="cresce"></span>' + seloDeSituacao() + "</div>" +
    '<div class="docs-previa"><div class="docs-miniaturas" id="pdf-minis">' + minis.join("") + (doc.paginas > total ? '<small class="as-mais">+' + (doc.paginas - total) + "</small>" : "") + "</div>" +
    '<div class="docs-pv-rolagem as-visor"><div class="pdf-folha" id="pdf-folha"><img class="docs-pagina" id="pdf-img" alt="página ' + assina.pagina + '">' +
    '<div class="pdf-selo" id="pdf-selo" hidden><div class="as-selo-dentro" id="pdf-selo-conteudo">' + previaSelo(cert.dados || {}) + "</div>" +
    '<span class="as-selo-legenda">' + ic("open_with", 14) + '<span id="pdf-selo-texto">Selo entra aqui · arraste para mover</span></span>' +
    '<i class="as-alca a"></i><i class="as-alca b"></i><i class="as-alca c"></i><i class="as-alca d"></i></div></div></div></div></div>';
}

function painelAntesDeAssinar() {
  const doc = assina.doc;
  const d = assina.cofre;
  const c = (cert.dados || {}).certificado;
  const radio = (valor, rotulo, extra) => {
    const classe = "as-radio" + (assina.paginas === valor ? " on" : "");
    return '<div class="' + classe + '" data-as-pag="' + valor + '"><i></i><span>' + rotulo + "</span>" + (extra || "") + "</div>";
  };
  const escolhas = (d.escolhas || []).map((e) => {
    if (e.valor === "todas") return radio("todas", "Todas as " + doc.paginas + " páginas");
    if (e.valor === "intervalo") return radio("intervalo", "Intervalo", '<input type="text" id="assina-intervalo" placeholder="ex. 1-3, 7, 12" value="' + esc(assina.intervalo) + '">');
    return radio(e.valor, e.rotulo);
  }).join("");
  const classeRepetir = "ag-toggle" + (assina.repetir ? " on" : "");
  const classeProteger = "ag-toggle" + (assina.proteger ? " on" : "");
  const marca = (chave, rotulo) => {
    const classe = "as-marca liga" + (assina[chave] ? " on" : "");
    return '<div class="' + classe + '" data-depois="' + chave + '"><span class="as-caixinha">' + ic("check", 12) + "</span><span>" + rotulo + "</span></div>";
  };

  let pronto;
  const f = assina.feito;
  if (f && f.aguardando_aprovacao) {
    pronto = '<div class="as-pronto"><div class="as-pronto-cabeca">' + coroa(18) + "<span>Esperando o seu sim</span></div>" +
      "<p><b>" + esc(f.pedido.titulo) + "</b> — " + esc(f.pedido.resumo) + "</p>" +
      "<p>Assinar tem efeito jurídico, então o pedido parou na fila de Aprovações. Nada foi assinado ainda.</p>" +
      '<div class="as-pronto-acoes"><button class="em-ligacao" id="assina-voltar">Mudar as escolhas</button><button class="primario com-icone" id="assina-ver-fila">' + ic("verified", 16) + "Abrir a fila</button></div></div>";
  } else if (f) {
    pronto = '<div class="as-pronto feito"><div class="as-pronto-cabeca">' + ic("check_circle", 18) + "<span>Documento assinado</span>" +
      '<span class="contagem">código ' + esc(f.codigo) + "</span></div>" +
      "<p><b>" + esc(nomeDe(f.destino)) + "</b> · assinado com o certificado de " + esc(f.titular) + ", " +
      (f.paginas.length > 1 ? f.paginas.length + " páginas seladas" : "1 página selada") + "." +
      (f.protegido ? " O arquivo está protegido por senha." : "") + " O original continua onde estava.</p>" +
      (f.icp_brasil ? "" : '<div class="cert-aviso"><strong>Sem validade jurídica de ICP-Brasil</strong><p>O certificado usado não é credenciado. A assinatura prova que o arquivo não mudou depois de assinado, mas não substitui a assinatura com e-CPF ou e-CNPJ.</p></div>') +
      '<div class="as-pronto-acoes"><button class="em-ligacao" id="assinado-conferir">Conferir a assinatura</button><button class="primario com-icone" id="assinado-baixar">' + ic("download", 16) + "Baixar o PDF</button></div>" +
      '<div id="assinado-conferencia"></div></div>';
  } else {
    pronto = '<div class="as-pronto"><div class="as-pronto-cabeca">' + coroa(18) + "<span>Pronto para assinar</span></div>" +
      '<p id="assina-frase"></p>' +
      (d.precisa_senha ? '<input type="password" id="assina-senha-cert" placeholder="senha do certificado">' : "") +
      '<div class="as-pronto-acoes"><button class="em-ligacao" id="assina-previa">Ver a prévia</button><button class="primario com-icone" id="assina-agora">' + ic("draw", 16) + "Assinar agora</button></div>" +
      "<small>" + (d.pede_confirmacao ? "Vou pedir sua confirmação" + (d.precisa_senha ? " e a senha do certificado" : "") + " antes de gravar." : "A assinatura sai direto, sem nova confirmação.") + "</small></div>";
  }

  const podeCompartilhar = Boolean(f && !f.aguardando_aprovacao);
  const bloqueio = podeCompartilhar ? "" : " disabled";
  return '<aside class="acervo-painel">' + alcaDaAssinatura() + '<div class="rolagem as-painel">' +
    '<div class="painel-cabeca"><span class="titulo-painel"><h3>Antes de assinar</h3><span class="meta">' + esc(doc.nome) + " · " + plural(doc.paginas, "página") + "</span></span></div>" +
    '<div class="as-opcoes">' + escolhas +
    '<div class="ag-chave"><span>Onde o selo fica na página</span><select id="assina-posicao">' +
    (d.posicoes || []).map((p) => '<option value="' + esc(p.valor) + '"' + (assina.posicao === p.valor ? " selected" : "") + ">" + esc(p.rotulo) + "</option>").join("") +
    "</select></div>" +
    '<div class="' + classeRepetir + '" id="assina-repetir"><span>Repetir o selo em todo canto igual</span><i></i></div></div>' +
    '<div class="painel-bloco"><div class="painel-bloco-cabeca"><span>Com qual certificado</span>' + seloDeSituacao() + "</div>" + cartaoDoCertificadoEmUso() +
    (c && !c.icp_brasil && !c.erro ? '<p class="as-explica">Este certificado é de fora da ICP-Brasil: a assinatura será íntegra, mas sem a validade jurídica de um e-CPF ou e-CNPJ credenciado.</p>' : "") + "</div>" +
    '<div class="painel-bloco"><div class="painel-bloco-cabeca"><span>Depois de assinar</span></div><div class="as-lista">' +
    marca("baixar", "Baixar o PDF assinado") + marca("biblioteca", "Guardar no Acervo") + marca("manter", "Manter também o arquivo original") +
    '<div class="' + classeProteger + '" id="assina-proteger"><span class="duas-linhas"><b>Proteger o PDF com senha</b><small>quem receber vai precisar dessa senha para abrir</small></span><i></i></div>' +
    '<div class="em-senha" id="assina-senha-pdf"' + (assina.proteger ? "" : " hidden") + '><input type="password" id="assina-senha-campo" value="' + esc(assina.senhaPdf) + '" placeholder="senha para abrir o PDF"><button class="em-ligacao" id="assina-mostrar-pdf">mostrar</button></div>' +
    "</div></div>" +
    pronto +
    '<div class="painel-bloco"><div class="painel-bloco-cabeca"><span>Compartilhar depois</span>' + (podeCompartilhar ? "" : '<span class="contagem">depois de assinar</span>') + "</div>" +
    '<div class="painel-acoes semi"><button class="com-icone" id="as-baixar"' + bloqueio + ">" + ic("download", 16) + "Baixar</button>" +
    '<button class="com-icone" id="as-email"' + bloqueio + ">" + ic("mail", 16) + "Enviar por e-mail</button>" +
    '<button class="com-icone adiante" id="as-whats"' + bloqueio + ">" + ic("chat", 16) + "WhatsApp</button>" +
    '<button class="com-icone" id="as-codigo"' + bloqueio + ">" + ic("link", 16) + "Copiar o código de verificação</button></div></div>" +
    "</div></aside>";
}

function ligarAssinar() {
  const raiz = $("assinatura");
  $("assina-trocar").onclick = () => mostrarAssinar();
  raiz.querySelectorAll("[data-as-acervo]").forEach((b) => { b.onclick = () => { bib.termo = assina.doc.nome; marcarDestino("biblioteca"); mostrarBiblioteca(); }; });
  document.querySelectorAll("[data-as-acervo]").forEach((b) => { b.onclick = () => { bib.termo = assina.doc.nome; marcarDestino("biblioteca"); mostrarBiblioteca(); }; });

  $("pdf-antes").onclick = () => { if (assina.pagina > 1) { assina.pagina -= 1; carregarPagina(); } };
  $("pdf-depois").onclick = () => { if (assina.pagina < assina.doc.paginas) { assina.pagina += 1; carregarPagina(); } };
  raiz.querySelectorAll("[data-pdf-pagina]").forEach((b) => { b.onclick = () => { assina.pagina = Number(b.dataset.pdfPagina); carregarPagina(); }; });

  raiz.querySelectorAll("[data-as-pag]").forEach((r) => {
    r.onclick = (e) => {
      if (e.target.tagName === "INPUT") return;
      assina.paginas = r.dataset.asPag;
      raiz.querySelectorAll("[data-as-pag]").forEach((x) => x.classList.toggle("on", x === r));
      const campo = $("assina-intervalo");
      if (assina.paginas === "intervalo" && campo) campo.focus();
      atualizarFrase();
    };
  });
  const intervalo = $("assina-intervalo");
  if (intervalo) intervalo.oninput = (e) => { assina.paginas = "intervalo"; raiz.querySelectorAll("[data-as-pag]").forEach((x) => x.classList.toggle("on", x.dataset.asPag === "intervalo")); assina.intervalo = e.target.value; atualizarFrase(); };

  $("assina-posicao").onchange = (e) => {
    assina.posicao = e.target.value;
    assina.x = assina.y = null;   /* escolher o canto desfaz o arrasto */
    posicionarSelo();
    atualizarFrase();
  };
  $("assina-repetir").onclick = () => {
    assina.repetir = !assina.repetir;
    $("assina-repetir").classList.toggle("on", assina.repetir);
    if (!assina.repetir) { assina.x = assina.y = null; posicionarSelo(); }
    atualizarFrase();
  };

  raiz.querySelectorAll("[data-depois]").forEach((m) => {
    m.onclick = () => { assina[m.dataset.depois] = !assina[m.dataset.depois]; m.classList.toggle("on", assina[m.dataset.depois]); atualizarFrase(); };
  });
  const proteger = $("assina-proteger");
  proteger.onclick = () => {
    assina.proteger = !assina.proteger;
    proteger.classList.toggle("on", assina.proteger);
    $("assina-senha-pdf").hidden = !assina.proteger;
    if (!assina.proteger) { assina.senhaPdf = ""; $("assina-senha-campo").value = ""; } else $("assina-senha-campo").focus();
    atualizarFrase();
  };
  $("assina-senha-campo").oninput = (e) => { assina.senhaPdf = e.target.value; atualizarFrase(); };
  $("assina-mostrar-pdf").onclick = () => {
    const campo = $("assina-senha-campo");
    campo.type = campo.type === "password" ? "text" : "password";
    $("assina-mostrar-pdf").textContent = campo.type === "password" ? "mostrar" : "esconder";
  };

  const agora = $("assina-agora");
  if (agora) agora.onclick = assinarAgora;
  const agoraTopo = $("assina-agora-topo");
  if (agoraTopo) agoraTopo.onclick = () => { if (assina.feito) { avisoCert("este documento já foi assinado — abra o assinado ou troque o documento"); return; } assinarAgora(); };
  const previa = $("assina-previa");
  if (previa) previa.onclick = () => { const alvos = paginasEscolhidas(); if (alvos.length) { assina.pagina = alvos[0]; carregarPagina(); } };

  const voltar = $("assina-voltar");
  if (voltar) voltar.onclick = () => { assina.feito = null; desenharAssinatura(); };
  const fila = $("assina-ver-fila");
  if (fila) fila.onclick = () => { marcarDestino("aprovacoes"); mostrarAprovacoes(); };

  const f = assina.feito;
  if (f && !f.aguardando_aprovacao) {
    const baixar = () => { window.location.href = "/api/assinar/baixar?arquivo=" + encodeURIComponent(f.destino); };
    $("assinado-baixar").onclick = baixar;
    $("as-baixar").onclick = baixar;
    $("assinado-conferir").onclick = conferirAssinado;
    $("as-codigo").onclick = () => copiarTexto(f.codigo, "código " + f.codigo + " copiado");
    $("as-whats").onclick = () => avisoCert("WhatsApp ainda não tem motor nesta máquina — por enquanto, e-mail ou o PDF baixado");
    $("as-email").onclick = async () => {
      if (!mail.contas) { try { mail.contas = await (await fetch("/api/email/contas")).json(); } catch (err) { mail.contas = null; } }
      if (!mail.contas || !mail.contas.contas.length) { marcarDestino("caixa"); return mostrarEmail(); }
      mail.conta = mail.contas.contas.find((c) => c.em_uso) || mail.contas.contas[0];
      marcarDestino("caixa");
      telaEscrever({ assunto: nomeDe(f.destino), corpo: "" });
      mail.anexos = [{ path: f.destino, nome: nomeDe(f.destino), mb: 0 }];
      desenharAnexos();
    };
  }

  ligarArrasto();
  carregarPagina();
  atualizarFrase();
}

async function carregarPagina() {
  const img = $("pdf-img");
  if (!img) return;
  $("pdf-num").textContent = assina.pagina;
  document.querySelectorAll("[data-pdf-pagina]").forEach((b) => b.classList.toggle("atual", Number(b.dataset.pdfPagina) === assina.pagina));
  img.src = "/api/assinar/pagina?arquivo=" + encodeURIComponent(assina.doc.caminho) + "&numero=" + assina.pagina + "&largura=900";
  img.onload = posicionarSelo;
}

/* O selo so aparece nas paginas que vao recebe-lo, e na posicao real: o que
   a tela mostra e o que o PDF vai receber. */
function posicionarSelo() {
  const selo = $("pdf-selo");
  const img = $("pdf-img");
  if (!selo || !img || !img.clientWidth) return;

  const alvos = paginasEscolhidas();
  if (alvos.indexOf(assina.pagina) < 0 || assina.feito) { selo.hidden = true; return; }
  selo.hidden = false;

  const escala = img.clientWidth / (assina.doc.largura || 595);
  const largura = 228 * escala;
  const altura = 62 * escala;

  let x, y;
  if (assina.x !== null && assina.repetir) {
    x = assina.x * escala;
    y = assina.y * escala;
  } else {
    const margem = 28 * escala;
    const alturaPag = (assina.doc.altura || 842) * escala;
    x = assina.posicao === "rodape_esquerda" ? margem
      : assina.posicao === "rodape_centro" ? (img.clientWidth - largura) / 2
      : img.clientWidth - largura - margem;
    y = assina.posicao === "topo_direita" ? margem : alturaPag - altura - margem;
  }

  selo.style.width = largura + "px";
  selo.style.height = altura + "px";
  selo.style.left = Math.max(0, Math.min(x, img.clientWidth - largura)) + "px";
  selo.style.top = Math.max(0, Math.min(y, img.clientHeight - altura)) + "px";
  const dentro = $("pdf-selo-conteudo");
  if (dentro) dentro.style.transform = "scale(" + escala.toFixed(3) + ")";
  const texto = $("pdf-selo-texto");
  const posicao = ((assina.cofre && assina.cofre.posicoes) || []).find((p) => p.valor === assina.posicao);
  if (texto) texto.textContent = "Selo entra aqui · arraste para mover · " + (assina.x !== null && assina.repetir ? "posição escolhida" : (posicao ? posicao.rotulo.toLowerCase() : assina.posicao));
}

function ligarArrasto() {
  const selo = $("pdf-selo");
  const img = $("pdf-img");
  if (!selo) return;
  let pegando = false, dx = 0, dy = 0;

  selo.onpointerdown = (e) => {
    pegando = true;
    selo.setPointerCapture(e.pointerId);
    selo.classList.add("pegando");
    dx = e.clientX - selo.offsetLeft;
    dy = e.clientY - selo.offsetTop;
  };
  selo.onpointermove = (e) => {
    if (!pegando) return;
    const escala = img.clientWidth / (assina.doc.largura || 595);
    const x = Math.max(0, Math.min(e.clientX - dx, img.clientWidth - selo.offsetWidth));
    const y = Math.max(0, Math.min(e.clientY - dy, img.clientHeight - selo.offsetHeight));
    selo.style.left = x + "px";
    selo.style.top = y + "px";
    /* Guarda em pontos do PDF, nao em pixels da tela: o zoom muda, o PDF nao. */
    assina.x = x / escala;
    assina.y = y / escala;
    assina.repetir = true;
  };
  selo.onpointerup = () => {
    pegando = false;
    selo.classList.remove("pegando");
    const r = $("assina-repetir");
    if (r) r.classList.add("on");
    atualizarFrase();
  };
}

function paginasEscolhidas() {
  const total = assina.doc.paginas;
  if (assina.paginas === "ultima") return [total];
  if (assina.paginas === "primeira_ultima") return total > 1 ? [1, total] : [1];
  if (assina.paginas === "intervalo") {
    const achados = new Set();
    assina.intervalo.split(/[,;]/).forEach((pedaco) => {
      const faixa = pedaco.trim().match(/^(\d+)\s*-\s*(\d+)$/);
      if (faixa) {
        let [, a, b] = faixa.map(Number);
        if (a > b) { const t = a; a = b; b = t; }
        for (let n = a; n <= b; n++) if (n >= 1 && n <= total) achados.add(n);
      } else if (/^\d+$/.test(pedaco.trim())) {
        const n = Number(pedaco.trim());
        if (n >= 1 && n <= total) achados.add(n);
      }
    });
    return [...achados].sort((a, b) => a - b);
  }
  return Array.from({ length: total }, (_, i) => i + 1);
}

/* A ultima coisa que a pessoa le antes de usar o certificado dela. */
function atualizarFrase() {
  const alvo = $("assina-frase");
  const alvos = paginasEscolhidas();
  const c = (cert.dados || {}).certificado || {};
  const total = assina.doc.paginas;
  const podeAssinar = Boolean((cert.dados || {}).instalado && !c.erro && !c.vencido);

  const onde = !alvos.length ? "em nenhuma página"
    : alvos.length === total && total > 1 ? "em todas as " + total + " páginas"
    : alvos.length === 1 ? "na página " + alvos[0]
    : "nas páginas " + alvos.join(", ");

  let frase = "Vou carimbar o selo " + onde + " e assinar o documento com o " +
    (c.tipo || "certificado") + " de " + (c.titular || "você") + ".";
  if (assina.senhaPdf) frase += " O arquivo sai protegido por senha.";
  if (alvos.length > 1) frase += " A assinatura digital é uma só e cobre o documento inteiro.";
  frase += " Nada é enviado para a internet.";
  if (!podeAssinar) frase = "Falta um certificado aberto e válido: instale ou digite a senha dele em Certificado digital.";

  if (alvo) alvo.textContent = frase;
  const botao = $("assina-agora");
  if (botao) botao.disabled = !alvos.length || !podeAssinar;
  const topo = $("assina-agora-topo");
  if (topo) topo.disabled = !alvos.length || !podeAssinar;
  const marcados = new Set(alvos);
  document.querySelectorAll("[data-pdf-pagina]").forEach((b) => {
    const n = Number(b.dataset.pdfPagina);
    const tem = b.querySelector(".as-mini-selo");
    if (marcados.has(n) && !tem) b.insertAdjacentHTML("beforeend", '<i class="as-mini-selo"></i>');
    if (!marcados.has(n) && tem) tem.remove();
  });
  posicionarSelo();
}

async function assinarAgora() {
  const botao = $("assina-agora");
  const senhaCert = $("assina-senha-cert");
  const alvos = paginasEscolhidas();
  if (!alvos.length) return;
  if (assina.cofre.precisa_senha && senhaCert && !senhaCert.value) { senhaCert.focus(); avisoCert("digite a senha do certificado"); return; }

  if (assina.cofre.pede_confirmacao) {
    if (!(await confirmar({ titulo: "Assinar agora?", contexto: "Assinatura", texto: $("assina-frase").textContent, confirmar: "Assinar" }))) return;
  }

  if (botao) { botao.disabled = true; botao.textContent = "assinando…"; }
  const r = await fetch("/api/assinar", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      arquivo: assina.doc.caminho,
      paginas: assina.paginas,
      intervalo: assina.intervalo,
      posicao: assina.posicao,
      x: assina.repetir ? assina.x : null,
      y: assina.repetir ? assina.y : null,
      senha_pdf: assina.senhaPdf,
      guardar_biblioteca: assina.biblioteca,
      manter_original: assina.manter,
      senha_certificado: senhaCert ? senhaCert.value : "",
    }),
  });
  if (botao) { botao.disabled = false; botao.innerHTML = ic("draw", 16) + "Assinar agora"; }

  if (!r.ok) { avisoCert(await erroDe(r)); return; }
  const d = await r.json();
  assina.feito = d;
  desenharAssinatura();
  if (!d.aguardando_aprovacao && assina.baixar) {
    window.location.href = "/api/assinar/baixar?arquivo=" + encodeURIComponent(d.destino);
  }
}

async function conferirAssinado() {
  const f = assina.feito;
  const alvo = $("assinado-conferencia");
  if (!f || !alvo) return;
  alvo.innerHTML = '<p class="nota">conferindo…</p>';
  const r = await (await fetch("/api/assinaturas/conferir?arquivo=" + encodeURIComponent(f.destino) +
    "&senha=" + encodeURIComponent(assina.senhaPdf || ""))).json();
  alvo.innerHTML = '<div class="as-conferencia"><small>o que o arquivo diz</small>' +
    r.assinaturas.map((a) => {
      if (a.erro) return '<p class="as-explica">' + esc(a.erro) + "</p>";
      const classe = "em-conferencia " + (a.intacta ? "ok" : "aviso");
      return '<div class="' + classe + '">' + ic(a.intacta ? "check_circle" : "error", 18) + "<span>" + esc(a.titular) + " · " + esc(a.emissor) + " · " +
        (a.intacta ? "não foi alterado depois" : "foi alterado depois de assinado") + "</span></div>";
    }).join("") +
    '<p class="as-explica">Não confiro revogação nem a cadeia até a raiz da ICP-Brasil: isso exigiria internet, e este programa trabalha desligado.</p></div>';
}

function telaAssinado(d) {
  assina.feito = d;
  desenharAssinatura();
}

function nomeDe(caminho) {
  return String(caminho || "").split(/[\\/]/).pop();
}

