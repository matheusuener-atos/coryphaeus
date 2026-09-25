/* --------------------------------------------- assinar documento (A8) */

/* O selo em pontos do PDF: o tamanho de sempre, os limites do redimensionar
   e a margem dos cantos. Os mesmos numeros moram em src/assinatura.py. */
const SELO_PT = { largura: 228, altura: 62, minimo: 114, maximo: 684, margem: 28 };

const assina = {
  doc: null, cofre: null, pagina: 1,
  paginas: "ultima", intervalo: "", posicao: "rodape_direita",
  baixar: true, biblioteca: true, manter: true, senhaPdf: "", proteger: false,
  /* O selo posto pela pessoa: {x, y, largura} em pontos do PDF, com origem
     no canto de cima. Nulo ate ela pedir "Adicionar assinatura" - escolher o
     PDF nao carimba nada sozinho. */
  selo: null, menuSelo: false,
  pdfs: [], feito: null,
};

async function mostrarAssinar(caminho, feito) {
  abrirTela("Assinatura", { cheia: true });
  marcarDestino("assinar");
  cert.visao = "assinar";
  assina.feito = null;
  const centro = $("centro");
  centro.innerHTML = '<div class="acervo sem-painel"><div class="acervo-principal">' + esqueleto("lista") + '</div></div>';

  try {
    cert.dados = await (await fetch("/api/certificado")).json();
  } catch (err) {
    centro.innerHTML = '<div class="acervo sem-painel"><div class="acervo-principal"><p class="nota">não consegui abrir: ' + esc(String(err)) + "</p></div></div>";
    return;
  }

  // Voltar do Certificado para o mesmo documento nao desfaz o selo posto.
  const mesmo = Boolean(caminho && assina.doc && assina.doc.caminho === caminho && !feito);
  assina.doc = null;
  if (caminho) {
    const r = await fetch("/api/assinar/documento?arquivo=" + encodeURIComponent(caminho));
    if (!r.ok) {
      avisoCert(await erroDe(r));
    } else {
      const d = await r.json();
      assina.doc = d.documento;
      assina.cofre = d;
      if (!mesmo) {
        assina.pagina = d.documento.paginas;
        assina.paginas = "ultima";
        assina.intervalo = "";
        assina.selo = null;
        assina.posicao = (d.selo && d.selo.posicao) || "rodape_direita";
      }
      assina.menuSelo = false;
      if (feito) assina.feito = feito;
    }
  }
  if (!assina.doc) {
    try { assina.pdfs = (await (await fetch("/api/assinar/pdfs")).json()).pdfs; } catch (err) { assina.pdfs = []; }
  }
  desenharAssinatura();
  atualizarPostura();
  const pronto = assina.feito ? document.querySelector(".as-pronto.feito") : null;
  if (pronto) pronto.scrollIntoView({ block: "nearest" });
}

/* Depois de assinar - direto ou pelo sim em Aprovacoes -, a tela abre o PDF
   ja assinado, com o selo de verdade na pagina. Se o assinado nao abrir
   (protegido por senha, por exemplo), mostra o original com o resultado. */
async function abrirAssinado(feito) {
  if (!feito || !feito.destino) return false;
  let caminho = feito.destino;
  try {
    const r = await fetch("/api/assinar/documento?arquivo=" + encodeURIComponent(caminho));
    if (!r.ok) caminho = feito.origem || "";
  } catch (err) {
    caminho = feito.origem || "";
  }
  if (!caminho) { avisoCert("documento assinado · código " + (feito.codigo || ""), { tom: "ok" }); return false; }
  await mostrarAssinar(caminho, feito);
  return true;
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
    "<p>Você adiciona a assinatura na página, arrasta para onde quiser e ajusta o tamanho; o selo é o desenho, a assinatura é o dado criptográfico que cobre o documento inteiro.</p>" +
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
  const alvos = new Set(assina.selo ? paginasEscolhidas() : []);
  const total = Math.min(doc.paginas, 40);
  const minis = [];
  for (let i = 1; i <= total; i += 1) {
    const classe = "docs-mini" + (i === assina.pagina ? " atual" : "");
    minis.push('<button class="' + classe + '" data-pdf-pagina="' + i + '"><img alt="" src="/api/assinar/pagina?arquivo=' +
      encodeURIComponent(doc.caminho) + "&numero=" + i + '&largura=96"><span>' + i + "</span>" +
      (alvos.has(i) ? '<i class="as-mini-selo"></i>' : "") + "</button>");
  }
  const pondo = !assina.selo && !assina.feito;
  return '<div class="as-cartao"><div class="docs-status">' +
    '<button class="voltar" id="pdf-antes" title="Página anterior">' + ic("chevron_left", 18) + "</button>" +
    '<span class="docs-pagina-num">Pág. <b id="pdf-num">' + assina.pagina + "</b> / " + doc.paginas + "</span>" +
    '<button class="voltar" id="pdf-depois" title="Próxima página">' + ic("chevron_right", 18) + "</button>" +
    '<span class="docs-divisa-fina"></span><span>' + (assina.feito && !assina.feito.aguardando_aprovacao ? "o documento assinado" : "lido da sua máquina") + '</span><span class="cresce"></span>' + seloDeSituacao() + "</div>" +
    '<div class="docs-previa"><div class="docs-miniaturas" id="pdf-minis">' + minis.join("") + (doc.paginas > total ? '<small class="as-mais">+' + (doc.paginas - total) + "</small>" : "") + "</div>" +
    '<div class="docs-pv-rolagem as-visor"><div class="pdf-folha' + (pondo ? " pondo" : "") + '" id="pdf-folha"><img class="docs-pagina" id="pdf-img" alt="página ' + assina.pagina + '">' +
    '<div class="as-adicionar" id="pdf-adicionar"' + (pondo ? "" : " hidden") + '><button class="primario com-icone" id="assina-add-pagina">' + ic("add", 16) + "Adicionar assinatura</button>" +
    "<small>ou clique na página onde ela deve ficar</small></div>" +
    '<div class="as-nesta" id="pdf-nesta" hidden><span>A assinatura não entra nesta página</span><button class="em-ligacao forte" id="assina-por-aqui">pôr aqui também</button></div>' +
    '<div class="pdf-selo" id="pdf-selo" hidden><div class="as-selo-dentro" id="pdf-selo-conteudo">' + previaSelo(cert.dados || {}) + "</div>" +
    '<div class="as-selo-barra" id="pdf-selo-barra">' +
    '<button type="button" id="selo-replicar" title="Repetir o selo em outras páginas" aria-haspopup="menu">' + ic("content_copy", 14) + '<span id="selo-replicar-rotulo">Replicar</span></button>' +
    '<button type="button" id="selo-remover" title="Tirar a assinatura" aria-label="Tirar a assinatura">' + ic("delete", 14) + "</button>" +
    '<div class="as-selo-menu" id="selo-menu" role="menu" hidden></div></div>' +
    '<span class="as-selo-legenda">' + ic("open_with", 14) + '<span id="pdf-selo-texto">arraste para mover · puxe um canto para mudar o tamanho</span></span>' +
    '<i class="as-alca a" data-alca="a"></i><i class="as-alca b" data-alca="b"></i><i class="as-alca c" data-alca="c"></i><i class="as-alca d" data-alca="d"></i></div></div></div></div></div>';
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
    if (e.valor === "todas") return radio("todas", doc.paginas > 1 ? "Todas as " + doc.paginas + " páginas" : "A única página");
    if (e.valor === "intervalo") return radio("intervalo", "Intervalo", '<input type="text" id="assina-intervalo" placeholder="ex. 1-3, 7, 12" value="' + esc(assina.intervalo) + '">');
    return radio(e.valor, e.rotulo);
  }).join("");
  const classeProteger = "ag-toggle" + (assina.proteger ? " on" : "");
  const marca = (chave, rotulo) => {
    const classe = "as-marca liga" + (assina[chave] ? " on" : "");
    return '<div class="' + classe + '" data-depois="' + chave + '"><span class="as-caixinha">' + ic("check", 12) + "</span><span>" + rotulo + "</span></div>";
  };

  let pronto;
  const f = assina.feito;
  if (f && f.aguardando_aprovacao) {
    const passo = (feito, texto) => '<li class="' + (feito ? "feito" : "espera") + '">' + ic(feito ? "check_circle" : "schedule", 16) + "<span>" + texto + "</span></li>";
    pronto = '<div class="as-pronto quase"><div class="as-pronto-cabeca">' + ic("task_alt", 18) + "<span>Está quase pronto — só falta a confirmação</span></div>" +
      "<p><b>" + esc(f.pedido.titulo) + "</b> — " + esc(f.pedido.resumo) + "</p>" +
      '<ul class="as-passos">' + passo(true, "Documento e páginas escolhidos") + passo(true, "Assinatura posicionada na página") +
      passo(true, "Certificado conferido") + passo(false, "Sua confirmação em Aprovações") + "</ul>" +
      "<p>Nada foi assinado ainda: assinar tem efeito jurídico, então falta só o seu sim. Confira e aprove em Aprovações — depois do sim, eu trago você de volta para o documento já assinado.</p>" +
      '<div class="as-pronto-acoes"><button class="em-ligacao" id="assina-voltar">Mudar as escolhas</button><button class="primario com-icone" id="assina-ver-fila">' + ic("verified", 16) + "Confirmar em Aprovações</button></div></div>";
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
    // O miolo depende do selo e do certificado: atualizarPronto preenche.
    pronto = '<div class="as-pronto" id="assina-pronto"></div>';
  }

  const podeCompartilhar = Boolean(f && !f.aguardando_aprovacao);
  const bloqueio = podeCompartilhar ? "" : " disabled";
  return '<aside class="acervo-painel">' + alcaDaAssinatura() + '<div class="rolagem as-painel">' +
    '<div class="painel-cabeca"><span class="titulo-painel"><h3>Antes de assinar</h3><span class="meta">' + esc(doc.nome) + " · " + plural(doc.paginas, "página") + "</span></span></div>" +
    (f ? "" : '<div class="as-selo-coluna" id="assina-selo-coluna"></div>') +
    '<div class="as-opcoes">' + escolhas +
    '<div class="ag-chave"><span>Onde a assinatura entra</span><select id="assina-posicao">' +
    (d.posicoes || []).map((p) => '<option value="' + esc(p.valor) + '"' + (assina.posicao === p.valor ? " selected" : "") + ">" + esc(p.rotulo) + "</option>").join("") +
    "</select></div></div>" +
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
      escolherPaginas(r.dataset.asPag);
      const campo = $("assina-intervalo");
      if (assina.paginas === "intervalo" && campo) campo.focus();
    };
  });
  const intervalo = $("assina-intervalo");
  if (intervalo) intervalo.oninput = (e) => { assina.paginas = "intervalo"; assina.intervalo = e.target.value; marcarEscolhaDePaginas(); atualizarFrase(); };

  $("assina-posicao").onchange = (e) => {
    assina.posicao = e.target.value;
    // Com o selo ja na pagina, escolher o canto leva o selo para la, no mesmo tamanho.
    if (assina.selo) assina.selo = seloNoCanto(assina.posicao, assina.selo.largura);
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

  const agoraTopo = $("assina-agora-topo");
  if (agoraTopo) agoraTopo.onclick = () => {
    if (assina.feito) { avisoCert("este documento já foi assinado — abra o assinado ou troque o documento"); return; }
    if (!assina.selo) { avisoCert("adicione a assinatura na página antes de assinar"); return; }
    assinarAgora();
  };

  const voltar = $("assina-voltar");
  if (voltar) voltar.onclick = () => { assina.feito = null; desenharAssinatura(); };
  const fila = $("assina-ver-fila");
  if (fila) fila.onclick = () => {
    // Abre Aprovacoes com o pedido desta assinatura ja aberto no painel.
    if (assina.feito && assina.feito.pedido && typeof aprov !== "undefined") aprov.aberto = assina.feito.pedido.id;
    marcarDestino("aprovacoes");
    mostrarAprovacoes();
  };

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

  ligarSelo();
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

/* ------------------------------------------------ o selo, em pontos do PDF */

function medidasDoSelo(largura) {
  const teto = Math.min(SELO_PT.maximo, assina.doc.largura || 595);
  const w = Math.max(SELO_PT.minimo, Math.min(largura || SELO_PT.largura, teto));
  return { w: w, h: w * SELO_PT.altura / SELO_PT.largura };
}

function prenderNaPagina(s) {
  const L = assina.doc.largura || 595, A = assina.doc.altura || 842;
  const m = medidasDoSelo(s.largura);
  return { x: Math.max(0, Math.min(s.x, L - m.w)), y: Math.max(0, Math.min(s.y, A - m.h)), largura: m.w };
}

/* O canto escolhido na coluna, no tamanho pedido. */
function seloNoCanto(posicao, largura) {
  const L = assina.doc.largura || 595, A = assina.doc.altura || 842, margem = SELO_PT.margem;
  const m = medidasDoSelo(largura);
  const x = posicao === "rodape_esquerda" ? margem : posicao === "rodape_centro" ? (L - m.w) / 2 : L - m.w - margem;
  const y = posicao === "topo_direita" ? margem : A - m.h - margem;
  return prenderNaPagina({ x: x, y: y, largura: m.w });
}

/* Poe o selo: no ponto clicado (centro do selo) ou no canto da coluna. Se a
   pagina a vista nao estava entre as escolhidas, a escolha passa a ser ela:
   o selo aparece onde a pessoa estava olhando, nunca em outra pagina. */
function adicionarSelo(centro) {
  if (!assina.doc || assina.feito) return;
  if (centro) {
    const m = medidasDoSelo();
    assina.selo = prenderNaPagina({ x: centro.x - m.w / 2, y: centro.y - m.h / 2, largura: m.w });
  } else {
    assina.selo = seloNoCanto(assina.posicao);
  }
  if (paginasEscolhidas().indexOf(assina.pagina) < 0) escolherPaginas("intervalo", String(assina.pagina));
  else atualizarFrase();
  // O canto padrao costuma ser o rodape: traz o selo para a vista.
  const selo = $("pdf-selo");
  if (selo && !selo.hidden) selo.scrollIntoView({ block: "nearest", behavior: animacoesLigadas() ? "smooth" : "auto" });
}

function removerSelo() {
  assina.selo = null;
  assina.menuSelo = false;
  atualizarFrase();
}

function escolherPaginas(valor, intervalo) {
  assina.paginas = valor;
  if (intervalo !== undefined) assina.intervalo = intervalo;
  marcarEscolhaDePaginas();
  atualizarFrase();
}

function marcarEscolhaDePaginas() {
  document.querySelectorAll("[data-as-pag]").forEach((x) => x.classList.toggle("on", x.dataset.asPag === assina.paginas));
  const campo = $("assina-intervalo");
  if (campo && campo.value !== assina.intervalo) campo.value = assina.intervalo;
}

/* "Replicar" no proprio selo: as mesmas escolhas da coluna, mais "so nesta". */
function menuDoSelo() {
  const total = assina.doc.paginas;
  const aqui = String(assina.pagina);
  const itens = [["aqui", "Só nesta página (" + assina.pagina + ")"]];
  ((assina.cofre && assina.cofre.escolhas) || []).forEach((e) => {
    if (e.valor === "intervalo") return;
    if (e.valor === "todas") itens.push(["todas", total > 1 ? "Todas as " + total + " páginas" : "A única página"]);
    else itens.push([e.valor, e.rotulo]);
  });
  const atual = assina.paginas === "intervalo" && assina.intervalo.trim() === aqui ? "aqui" : assina.paginas;
  return '<small>Repetir o selo, no mesmo lugar e tamanho</small>' + itens.map(([v, r]) =>
    '<button type="button" role="menuitemradio" aria-checked="' + (v === atual) + '" data-replicar="' + v + '"' + (v === atual ? ' class="on"' : "") + ">" +
    ic("check", 14) + "<span>" + esc(r) + "</span></button>").join("");
}

function rotuloDasPaginas(alvos) {
  const total = assina.doc.paginas;
  if (!alvos.length) return "nenhuma página";
  if (alvos.length === total && total > 1) return "todas as " + total + " páginas";
  if (alvos.length === 1) return "página " + alvos[0];
  return "páginas " + alvos.join(", ");
}

/* O selo so aparece nas paginas que vao recebe-lo, e na posicao real: o que
   a tela mostra e o que o PDF vai receber. */
function posicionarSelo() {
  const selo = $("pdf-selo");
  const img = $("pdf-img");
  const folha = $("pdf-folha");
  if (!selo || !img || !img.clientWidth) return;

  const s = assina.selo;
  const alvos = paginasEscolhidas();
  const pondo = !s && !assina.feito;
  folha.classList.toggle("pondo", pondo);
  $("pdf-adicionar").hidden = !pondo;
  $("pdf-nesta").hidden = !(s && !assina.feito && alvos.indexOf(assina.pagina) < 0);

  if (!s || assina.feito || alvos.indexOf(assina.pagina) < 0) { selo.hidden = true; return; }
  selo.hidden = false;

  const escala = img.clientWidth / (assina.doc.largura || 595);
  const m = medidasDoSelo(s.largura);
  selo.style.width = m.w * escala + "px";
  selo.style.height = m.h * escala + "px";
  selo.style.left = s.x * escala + "px";
  selo.style.top = s.y * escala + "px";
  // Perto do topo da pagina a barra do selo desce, para nao sumir no corte.
  selo.classList.toggle("barra-embaixo", s.y * escala < 44);
  selo.classList.toggle("menu-embaixo", s.y * escala < 200);
  const dentro = $("pdf-selo-conteudo");
  if (dentro) dentro.style.transform = "scale(" + (escala * m.w / SELO_PT.largura).toFixed(3) + ")";

  const rotulo = $("selo-replicar-rotulo");
  if (rotulo) rotulo.textContent = alvos.length > 1 ? "Em " + alvos.length + " páginas" : "Replicar";
  const menu = $("selo-menu");
  if (menu) {
    menu.hidden = !assina.menuSelo;
    if (assina.menuSelo) menu.innerHTML = menuDoSelo();
  }
  $("selo-replicar").setAttribute("aria-expanded", String(assina.menuSelo));
}

function ligarSelo() {
  const selo = $("pdf-selo");
  const img = $("pdf-img");
  const folha = $("pdf-folha");
  if (!selo) return;

  $("assina-add-pagina").onclick = (e) => { e.stopPropagation(); adicionarSelo(); };
  $("assina-por-aqui").onclick = (e) => {
    e.stopPropagation();
    const alvos = new Set(paginasEscolhidas());
    alvos.add(assina.pagina);
    escolherPaginas("intervalo", [...alvos].sort((a, b) => a - b).join(", "));
  };

  // Sem selo, clicar na pagina poe o selo ali mesmo.
  folha.onclick = (e) => {
    if (assina.menuSelo && !e.target.closest(".as-selo-barra")) { assina.menuSelo = false; posicionarSelo(); return; }
    if (assina.selo || assina.feito || e.target.closest("button, .pdf-selo, .as-adicionar, .as-nesta")) return;
    const r = img.getBoundingClientRect();
    if (!r.width) return;
    const escala = r.width / (assina.doc.largura || 595);
    adicionarSelo({ x: (e.clientX - r.left) / escala, y: (e.clientY - r.top) / escala });
  };

  $("selo-replicar").onclick = (e) => { e.stopPropagation(); assina.menuSelo = !assina.menuSelo; posicionarSelo(); };
  $("selo-remover").onclick = (e) => { e.stopPropagation(); removerSelo(); };
  $("selo-menu").onclick = (e) => {
    e.stopPropagation();
    const b = e.target.closest("[data-replicar]");
    if (!b) return;
    assina.menuSelo = false;
    const v = b.dataset.replicar;
    if (v === "aqui") escolherPaginas("intervalo", String(assina.pagina));
    else escolherPaginas(v);
    // A pagina a vista saiu da escolha: vai para uma que tem o selo.
    const alvos = paginasEscolhidas();
    if (alvos.length && alvos.indexOf(assina.pagina) < 0) { assina.pagina = alvos[alvos.length - 1]; carregarPagina(); }
  };

  /* Mover e redimensionar. Guarda em pontos do PDF, nao em pixels da tela:
     o zoom muda, o PDF nao. O redimensionar prende o canto oposto e mantem
     a proporcao do selo. */
  let gesto = null;
  selo.onpointerdown = (e) => {
    if (e.button !== 0 || e.target.closest(".as-selo-barra") || !assina.selo) return;
    e.preventDefault();
    const alca = e.target.dataset ? e.target.dataset.alca : "";
    const m = medidasDoSelo(assina.selo.largura);
    gesto = { alca: alca || "", x0: e.clientX, y0: e.clientY, s0: { x: assina.selo.x, y: assina.selo.y, w: m.w, h: m.h } };
    selo.setPointerCapture(e.pointerId);
    selo.classList.add(alca ? "redimensionando" : "pegando");
  };
  selo.onpointermove = (e) => {
    if (!gesto) return;
    const escala = img.clientWidth / (assina.doc.largura || 595);
    const dx = (e.clientX - gesto.x0) / escala;
    const dy = (e.clientY - gesto.y0) / escala;
    const s0 = gesto.s0;
    if (!gesto.alca) {
      assina.selo = prenderNaPagina({ x: s0.x + dx, y: s0.y + dy, largura: s0.w });
    } else {
      const esquerda = gesto.alca === "a" || gesto.alca === "c";
      const cima = gesto.alca === "a" || gesto.alca === "b";
      // O canto puxado segue o maior dos dois deslocamentos, na proporcao.
      const pelaLargura = esquerda ? -dx : dx;
      const pelaAltura = (cima ? -dy : dy) * SELO_PT.largura / SELO_PT.altura;
      const m = medidasDoSelo(s0.w + (Math.abs(pelaLargura) > Math.abs(pelaAltura) ? pelaLargura : pelaAltura));
      const x = esquerda ? s0.x + s0.w - m.w : s0.x;
      const y = cima ? s0.y + s0.h - m.h : s0.y;
      assina.selo = prenderNaPagina({ x: x, y: y, largura: m.w });
    }
    posicionarSelo();
  };
  const soltar = () => {
    if (!gesto) return;
    gesto = null;
    selo.classList.remove("pegando", "redimensionando");
    atualizarFrase();
  };
  selo.onpointerup = soltar;
  selo.onpointercancel = soltar;
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

/* O que ainda falta para assinar, na ordem em que a pessoa resolve. */
function oQueFalta() {
  const d = cert.dados || {};
  const c = d.certificado || {};
  if (!d.instalado || c.erro || c.vencido) {
    return { icone: "workspace_premium", titulo: "Falta o certificado", texto: "Instale o certificado ou digite a senha dele em Certificado digital.", botao: '<button class="primario com-icone" data-as-visao="certificado">' + ic("workspace_premium", 16) + "Abrir o certificado</button>" };
  }
  if (!assina.selo) {
    return { icone: "draw", titulo: "Falta adicionar a assinatura", texto: "Diga onde o selo entra: clique em Adicionar assinatura, ou direto na página. Depois dá para arrastar, mudar o tamanho e replicar nas outras páginas.", botao: '<button class="primario com-icone" id="assina-add-pronto">' + ic("add", 16) + "Adicionar assinatura</button>" };
  }
  if (!paginasEscolhidas().length) {
    return { icone: "info", titulo: "Falta dizer as páginas", texto: "O intervalo não tem nenhuma página deste documento. Escreva, por exemplo, 1-3 ou 7.", botao: "" };
  }
  return null;
}

/* A ultima coisa que a pessoa le antes de usar o certificado dela. */
function fraseDeAssinar() {
  const alvos = paginasEscolhidas();
  const c = (cert.dados || {}).certificado || {};
  const total = assina.doc.paginas;
  const onde = alvos.length === total && total > 1 ? "em todas as " + total + " páginas"
    : alvos.length === 1 ? "na página " + alvos[0]
    : "nas páginas " + alvos.join(", ");
  let frase = "O selo entra " + onde + ", onde você o colocou, e o documento é assinado com o " +
    (c.tipo || "certificado") + " de " + (c.titular || "você") + ".";
  if (assina.senhaPdf) frase += " O arquivo sai protegido por senha.";
  if (alvos.length > 1) frase += " A assinatura digital é uma só e cobre o documento inteiro.";
  return frase + " Nada é enviado para a internet.";
}

function atualizarPronto() {
  const caixa = $("assina-pronto");
  if (!caixa) return;
  const d = assina.cofre || {};
  const falta = oQueFalta();
  if (falta) {
    caixa.className = "as-pronto falta";
    caixa.innerHTML = '<div class="as-pronto-cabeca">' + ic(falta.icone, 18) + "<span>" + falta.titulo + "</span></div>" +
      "<p>" + falta.texto + "</p>" +
      '<div class="as-pronto-acoes">' + falta.botao + '<button class="com-icone" id="assina-agora" disabled title="' + esc(falta.titulo) + '">' + ic("draw", 16) + "Assinar agora</button></div>";
  } else {
    caixa.className = "as-pronto pronto";
    caixa.innerHTML = '<div class="as-pronto-cabeca">' + ic("task_alt", 18) + "<span>Tudo pronto para assinar</span></div>" +
      '<p id="assina-frase">' + esc(fraseDeAssinar()) + "</p>" +
      '<div class="as-pronto-acoes"><button class="em-ligacao" id="assina-previa">Ver onde entra</button><button class="primario com-icone" id="assina-agora">' + ic("draw", 16) + "Assinar agora</button></div>" +
      "<small>" + (d.pede_confirmacao || d.precisa_senha
        ? "Antes de gravar, peço sua confirmação" + (d.precisa_senha ? (d.origem === "windows" ? " e a senha do PAULUS" : " e a senha do certificado") : "") + "."
        : "A assinatura sai direto, sem nova confirmação.") + "</small>";
  }
  const agora = $("assina-agora");
  if (agora && !agora.disabled) agora.onclick = assinarAgora;
  const add = $("assina-add-pronto");
  if (add) add.onclick = () => adicionarSelo();
  const previa = $("assina-previa");
  if (previa) previa.onclick = () => { const alvos = paginasEscolhidas(); if (alvos.length) { assina.pagina = alvos[0]; carregarPagina(); } };
  caixa.querySelectorAll("[data-as-visao]").forEach((b) => { b.onclick = () => mostrarCertificado(); });
}

/* A linha do selo na coluna: o botao de por, ou o que ja foi posto. */
function atualizarColunaDoSelo() {
  const alvo = $("assina-selo-coluna");
  if (!alvo) return;
  const s = assina.selo;
  if (!s) {
    alvo.innerHTML = '<button class="com-icone as-add-coluna" id="assina-add-coluna">' + ic("add", 16) + "Adicionar assinatura</button>";
    $("assina-add-coluna").onclick = () => adicionarSelo();
    return;
  }
  const m = medidasDoSelo(s.largura);
  const cm = (pt) => (pt * 2.54 / 72).toFixed(1).replace(".", ",");
  alvo.innerHTML = '<div class="as-selo-linha">' + ic("draw", 18) + '<span class="duas-linhas"><b>Assinatura na página</b><small>' +
    rotuloDasPaginas(paginasEscolhidas()) + " · " + cm(m.w) + " × " + cm(m.h) + " cm</small></span>" +
    '<button class="em-ligacao" id="assina-tirar-coluna">tirar</button></div>';
  $("assina-tirar-coluna").onclick = removerSelo;
}

function atualizarFrase() {
  if (!assina.doc) return;
  const falta = assina.feito ? null : oQueFalta();
  const topo = $("assina-agora-topo");
  if (topo) topo.disabled = Boolean(assina.feito) || Boolean(falta);
  const marcados = new Set(assina.selo ? paginasEscolhidas() : []);
  document.querySelectorAll("[data-pdf-pagina]").forEach((b) => {
    const n = Number(b.dataset.pdfPagina);
    const tem = b.querySelector(".as-mini-selo");
    if (marcados.has(n) && !tem) b.insertAdjacentHTML("beforeend", '<i class="as-mini-selo"></i>');
    if (!marcados.has(n) && tem) tem.remove();
  });
  atualizarColunaDoSelo();
  atualizarPronto();
  posicionarSelo();
}

async function assinarAgora() {
  const botao = $("assina-agora");
  const alvos = paginasEscolhidas();
  if (!alvos.length || !assina.selo) return;

  // A confirmacao e a senha num modal so: "Assinar como FULANO?". Com o
  // certificado do Windows, a senha e a do PAULUS - e o Windows ainda pede a
  // dele depois, se o certificado tiver protecao forte.
  const c = assina.cofre;
  const doWindows = c.origem === "windows";
  let senha = "";
  if (c.pede_confirmacao || c.precisa_senha) {
    const titular = (c.certificado && c.certificado.titular) || "";
    const r = await dialogo({
      titulo: titular ? "Assinar como " + titular + "?" : "Assinar agora?", contexto: "Assinatura",
      texto: fraseDeAssinar() + (doWindows ? "\nSe o certificado foi instalado com proteção forte, o Windows vai pedir a senha dele em seguida." : ""),
      campo: c.precisa_senha ? { rotulo: doWindows ? "Senha do PAULUS" : "Senha do certificado", tipo: "password", icone: "lock", selecionar: false } : undefined,
      confirmar: "Assinar",
    });
    if (!r || !r.ok) return;
    senha = c.precisa_senha ? r.valor : "";
  }

  if (botao) { botao.disabled = true; botao.textContent = "assinando…"; }
  const origem = assina.doc.caminho;
  const r = await fetch("/api/assinar", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      arquivo: origem,
      paginas: assina.paginas,
      intervalo: assina.intervalo,
      posicao: assina.posicao,
      x: assina.selo.x,
      y: assina.selo.y,
      tamanho: medidasDoSelo(assina.selo.largura).w,
      senha_pdf: assina.senhaPdf,
      guardar_biblioteca: assina.biblioteca,
      manter_original: assina.manter,
      senha_certificado: senha,
    }),
  });
  if (botao) { botao.disabled = false; botao.innerHTML = ic("draw", 16) + "Assinar agora"; }

  if (!r.ok) { avisoCert(await erroDe(r)); return; }
  const d = await r.json();
  if (d.aguardando_aprovacao) {
    assina.feito = d;
    desenharAssinatura();
    contarPendencias();
    // O recado de "quase pronto" fica no pe da coluna: traz para a vista.
    const quase = document.querySelector(".as-pronto.quase");
    if (quase) quase.scrollIntoView({ block: "nearest", behavior: animacoesLigadas() ? "smooth" : "auto" });
    return;
  }
  if (assina.baixar) window.location.href = "/api/assinar/baixar?arquivo=" + encodeURIComponent(d.destino);
  await abrirAssinado(Object.assign({ origem: origem }, d));
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
