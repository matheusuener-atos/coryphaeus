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
  /* Os PDFs marcados na lista, e o lote que sai deles (ver "assinar em
     lote", no fim do arquivo). Sem lote, a tela e a de um documento so. */
  escolhidos: new Set(), lote: null,
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

  /* Com um lote aberto, voltar para a tela (do Certificado, do menu) volta
     para o lote, no documento em que a pessoa estava. Um documento de fora
     do lote encerra o lote. */
  const l = assina.lote;
  if (l && !feito) {
    const i = caminho ? l.itens.findIndex((it) => it.caminho === caminho || (it.feito && it.feito.destino === caminho)) : Math.max(l.atual, 0);
    if (i >= 0) { await abrirDoLote(i); return; }
  }
  assina.lote = null;

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
  if (feito && feito.tipo === "assinatura_lote") return mostrarLoteAssinado(feito);
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

/* A lista marca como as outras do sistema: a caixinha, ou segurar a linha,
   ou Ctrl+clique. Com dois ou mais marcados, "Assinar N documentos" abre o
   lote; um marcado so abre o documento como sempre. */
function listaDePdfs() {
  const marcados = assina.escolhidos;
  const total = assina.pdfs.length;
  const linhas = assina.pdfs.map((p) => {
    const marcado = marcados.has(p.path);
    const classe = "tabela-linha colunas-pdfs" + (marcado ? " escolhida" : "");
    return '<div class="' + classe + '" data-pdf="' + esc(p.path) + '">' +
      '<span class="marcar' + (marcado ? " on" : "") + '" data-pdf-marcar="' + esc(p.path) + '" role="checkbox" aria-checked="' + marcado +
      '" title="Marcar para assinar em lote">' + ic("check", 12) + "</span>" +
      '<span class="nome-doc">' + glifo(p.nome) + '<span class="duas-linhas"><b>' + esc(p.nome) + "</b><small>" +
      (p.paginas ? plural(p.paginas, "página") + " · " : "") + String(p.mb).replace(".", ",") + " MB</small></span></span>" +
      '<span class="quando-doc">PDF do Acervo</span><span class="acoes-linha"><button data-pdf-abrir="' + esc(p.path) + '">Abrir</button>' +
      '<button class="mais-linha" data-pdf-mais="' + esc(p.path) + '" title="Mais" aria-label="Mais">' + ic("more_horiz", 18) + "</button></span></div>";
  }).join("");
  const n = marcados.size;
  const barra = n
    ? barraDeSelecao(n, false, '<button class="primario com-icone" id="assina-lote">' + ic("draw", 16) + "Assinar " + plural(n, "documento") + "</button>", "data-pdf-sel-limpar", total)
    : '<span class="selecao">' + plural(total, "PDF", "PDFs") + " no Acervo</span>" +
      (total > 1 ? '<button class="limpar" id="assina-marcar-todos">Selecionar todos</button>' : "") +
      '<span class="nota-barra">clique em um para assinar · segure para marcar vários</span>';
  /* A caixinha so aparece em modo de selecao (depois de segurar uma linha ou
     Ctrl+clique): sem nada marcado, a linha e so o documento. */
  return '<div class="tabela-cartao' + (n ? "" : " sem-selecao") + '"><div class="tabela-barra">' + barra + "</div>" +
    '<div class="tabela-corpo">' + (linhas || '<div class="ag-vazio"><h4>Nenhum PDF no acervo ainda</h4><p>Inclua a pasta onde eles estão, ou escolha um arquivo direto no computador — eu subo uma cópia para o Acervo e assino a cópia.</p></div>') + "</div>" +
    '<div class="tabela-rodape"><button class="com-icone" id="assina-escolher">' + ic("folder_open", 16) + "Escolher PDFs no computador</button>" +
    '<input type="file" id="assina-arquivo" accept=".pdf" multiple hidden><span class="cresce"></span><span>a assinatura é feita nesta máquina com o seu certificado</span></div></div>';
}

/* Redesenha so a lista (a barra muda a cada marca), sem perder a rolagem. */
function redesenharListaDePdfs() {
  const principal = document.querySelector("#assinatura .as-principal");
  if (!principal) return;
  const corpo = principal.querySelector(".tabela-corpo");
  const rolagem = corpo ? corpo.scrollTop : 0;
  principal.innerHTML = listaDePdfs();
  const novo = principal.querySelector(".tabela-corpo");
  if (novo) novo.scrollTop = rolagem;
  ligarListaDePdfs();
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
  return '<aside class="acervo-painel"><div class="rolagem as-painel">' +
    '<div class="painel-cabeca"><span class="titulo-painel"><h3>Antes de assinar</h3><span class="meta">escolha o PDF na lista</span></span></div>' +
    '<div class="painel-bloco"><div class="painel-bloco-cabeca"><span>Com qual certificado</span>' + seloDeSituacao() + "</div>" + cartaoDoCertificadoEmUso() + "</div>" +
    '<div class="painel-bloco"><div class="painel-bloco-cabeca"><span>Como funciona</span></div>' +
    "<p>Você adiciona a assinatura na página, arrasta para onde quiser e ajusta o tamanho; o selo é o desenho, a assinatura é o dado criptográfico que cobre o documento inteiro.</p>" +
    "<p>Vou pedir sua confirmação e a senha do certificado antes de gravar. O original nunca é sobrescrito: o assinado nasce ao lado.</p>" +
    "<p>Marque vários na lista para assinar em lote: você passa por um documento de cada vez, põe o selo e, no fim, assina os prontos com uma confirmação e uma senha só.</p>" +
    "<p>Nada é enviado para a internet.</p></div></div></aside>";
}

function ligarListaDePdfs() {
  const raiz = $("assinatura");
  raiz.querySelectorAll("[data-pdf], [data-pdf-abrir]").forEach((b) => {
    b.onclick = (e) => { e.stopPropagation(); mostrarAssinar(b.dataset.pdf || b.dataset.pdfAbrir); };
  });
  raiz.querySelectorAll("[data-pdf-mais]").forEach((b) => {
    b.onclick = (e) => {
      e.stopPropagation();
      const p = assina.pdfs.find((x) => x.path === b.dataset.pdfMais);
      if (p) menuDoPdf(b, p, () => mostrarAssinar());
    };
  });
  /* O navegador nao entrega o caminho do arquivo escolhido, so o conteudo.
     Como o assinador precisa do arquivo no disco, este botao sobe uma copia
     para o acervo e assina a copia. */
  /* Marcar: a caixinha sempre; segurar, Ctrl+clique e Shift+clique pelo
     gesto comum das listas (16-selecao.js). Com algo marcado, clicar na
     linha marca em vez de abrir; o botao Abrir continua abrindo. */
  const alternar = (caminho) => {
    if (assina.escolhidos.has(caminho)) assina.escolhidos.delete(caminho); else assina.escolhidos.add(caminho);
    redesenharListaDePdfs();
  };
  ligarSelecao(raiz.querySelector(".tabela-corpo"), {
    linhas: "[data-pdf]", chave: (linha) => linha.dataset.pdf, escolhidos: assina.escolhidos, aoMudar: redesenharListaDePdfs,
  });
  raiz.querySelectorAll("[data-pdf-marcar]").forEach((m) => {
    m.onclick = (e) => { e.stopPropagation(); alternar(m.dataset.pdfMarcar); };
  });
  raiz.querySelectorAll("[data-pdf-sel-limpar]").forEach((b) => { b.onclick = () => { assina.escolhidos.clear(); redesenharListaDePdfs(); }; });
  const todos = $("assina-marcar-todos");
  if (todos) todos.onclick = () => { assina.pdfs.forEach((p) => assina.escolhidos.add(p.path)); redesenharListaDePdfs(); };
  const lote = $("assina-lote");
  if (lote) lote.onclick = () => {
    // Na ordem da lista, que e a ordem em que a pessoa vai passar por eles.
    const caminhos = assina.pdfs.map((p) => p.path).filter((c) => assina.escolhidos.has(c));
    if (caminhos.length === 1) mostrarAssinar(caminhos[0]); else iniciarLote(caminhos);
  };

  const campo = $("assina-arquivo");
  /* Um escolhido abre o documento; varios abrem o lote. */
  const abrirEscolhidos = async (nomes, faltou) => {
    if (!nomes.length) return;
    const pdfs = (await (await fetch("/api/assinar/pdfs")).json()).pdfs;
    assina.pdfs = pdfs;
    const achados = [...new Set(nomes.map((n) => (pdfs.find((p) => p.nome === n) || {}).path).filter(Boolean))];
    if (!achados.length) { avisoCert(faltou); return; }
    if (achados.length < nomes.length) avisoCert("não achei " + plural(nomes.length - achados.length, "PDF", "PDFs") + " entre os que dá para assinar");
    if (achados.length === 1) mostrarAssinar(achados[0]); else iniciarLote(achados);
  };
  /* O nosso seletor (Acervo e Meu computador, so PDF, um ou varios); o do
     Windows continua a um clique, no canto do modal. */
  const escolher = () => abrirAnexar({
    titulo: "Escolher PDFs para assinar", contexto: "Assinatura", verbo: "Abrir",
    so: /\.pdf$/i, aoWindows: () => campo.click(),
    aoAnexar: (nomes) => abrirEscolhidos(nomes, "não achei esse PDF entre os que dá para assinar"),
  });
  $("assina-escolher").onclick = escolher;
  const topo = $("assina-escolher-topo");
  if (topo) topo.onclick = escolher;
  campo.onchange = async () => {
    const arquivos = Array.from(campo.files);
    if (!arquivos.length) return;
    const forma = new FormData();
    arquivos.forEach((a) => forma.append("arquivos", a));
    const r = await fetch("/api/upload", { method: "POST", body: forma });
    if (!r.ok) { avisoCert(await erroDe(r)); return; }
    abrirEscolhidos(arquivos.map((a) => a.name), "o arquivo subiu, mas não achei o PDF na lista");
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
  return '<div class="as-cartao">' + (assina.lote ? faixaDoLote() : "") + '<div class="docs-status">' +
    '<button class="voltar" id="pdf-antes" title="Página anterior">' + ic("chevron_left", 18) + "</button>" +
    '<span class="docs-pagina-num">Pág. <b id="pdf-num">' + assina.pagina + "</b> / " + doc.paginas + "</span>" +
    '<button class="voltar" id="pdf-depois" title="Próxima página">' + ic("chevron_right", 18) + "</button>" +
    '<span class="docs-divisa-fina"></span><span>' + (assina.feito && !assina.feito.aguardando_aprovacao ? "o documento assinado" : "lido da sua máquina") + "</span>" +
    /* O convite e o aviso de pagina ficam na barra, e nao sobre a folha: em
       cima do documento eles cobriam justamente o cabecalho dele. */
    '<span class="as-adicionar" id="pdf-adicionar"' + (pondo ? "" : " hidden") + '><span class="docs-divisa-fina"></span>' +
    '<button class="primario com-icone" id="assina-add-pagina">' + ic("add", 16) + "Adicionar assinatura</button>" +
    "<small>ou clique na página</small></span>" +
    '<span class="as-nesta" id="pdf-nesta" hidden><span class="docs-divisa-fina"></span><span>Sem assinatura nesta página</span><button class="em-ligacao forte" id="assina-por-aqui">pôr aqui também</button></span>' +
    '<span class="cresce"></span>' + seloDeSituacao() + "</div>" +
    '<div class="docs-previa"><div class="docs-miniaturas" id="pdf-minis">' + minis.join("") + (doc.paginas > total ? '<small class="as-mais">+' + (doc.paginas - total) + "</small>" : "") + "</div>" +
    '<div class="docs-pv-rolagem as-visor"><div class="pdf-folha' + (pondo ? " pondo" : "") + '" id="pdf-folha"><img class="docs-pagina" id="pdf-img" alt="página ' + assina.pagina + '">' +
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
  const lote = assina.lote;
  if (f && f.aguardando_aprovacao && lote) {
    // No lote, o "quase pronto" e do lote inteiro: mora no bloco do lote.
    pronto = "";
  } else if (f && f.aguardando_aprovacao) {
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
      "</div>";
  } else {
    // O miolo depende do selo e do certificado: atualizarPronto preenche.
    pronto = '<div class="as-pronto" id="assina-pronto"></div>';
  }

  const podeCompartilhar = Boolean(f && !f.aguardando_aprovacao);
  const bloqueio = podeCompartilhar ? "" : " disabled";
  /* No lote, "Baixar" vira a pergunta do fim (um a um ou .zip), e o que vale
     para todos os documentos diz isso. Compartilhar fica para depois de
     salvar: e coisa de um documento, nao do lote. */
  const depois = lote
    ? '<div class="painel-bloco"><div class="painel-bloco-cabeca"><span>Depois de assinar</span><span class="contagem">vale para todos do lote</span></div><div class="as-lista">' +
      marca("biblioteca", "Guardar no Acervo") + marca("manter", "Manter também o arquivo original")
    : '<div class="painel-bloco"><div class="painel-bloco-cabeca"><span>Depois de assinar</span></div><div class="as-lista">' +
      marca("baixar", "Baixar o PDF assinado") + marca("biblioteca", "Guardar no Acervo") + marca("manter", "Manter também o arquivo original");
  const compartilhar = lote ? "" :
    '<div class="painel-bloco"><div class="painel-bloco-cabeca"><span>Compartilhar depois</span>' + (podeCompartilhar ? "" : '<span class="contagem">depois de assinar</span>') + "</div>" +
    '<div class="painel-acoes semi"><button class="com-icone" id="as-baixar"' + bloqueio + ">" + ic("download", 16) + "Baixar</button>" +
    '<button class="com-icone" id="as-email"' + bloqueio + ">" + ic("mail", 16) + "Enviar por e-mail</button>" +
    '<button class="com-icone adiante" id="as-whats"' + bloqueio + ">" + ic("chat", 16) + "WhatsApp</button>" +
    '<button class="com-icone" id="as-codigo"' + bloqueio + ">" + ic("link", 16) + "Copiar o código de verificação</button></div></div>";
  return '<aside class="acervo-painel"><div class="rolagem as-painel">' +
    '<div class="painel-cabeca"><span class="titulo-painel"><h3>' + (lote ? "Assinar em lote" : "Antes de assinar") + '</h3><span class="meta">' + esc(doc.nome) + " · " + plural(doc.paginas, "página") + "</span></span></div>" +
    (lote ? '<div class="painel-bloco as-lote-bloco" id="as-lote-bloco">' + blocoDoLote() + "</div>" : "") +
    (f ? "" : '<div class="as-selo-coluna" id="assina-selo-coluna"></div>') +
    '<div class="as-opcoes">' + escolhas +
    '<div class="ag-chave"><span>Onde a assinatura entra</span><select id="assina-posicao">' +
    (d.posicoes || []).map((p) => '<option value="' + esc(p.valor) + '"' + (assina.posicao === p.valor ? " selected" : "") + ">" + esc(p.rotulo) + "</option>").join("") +
    "</select></div></div>" +
    '<div class="painel-bloco"><div class="painel-bloco-cabeca"><span>Com qual certificado</span>' + seloDeSituacao() + "</div>" + cartaoDoCertificadoEmUso() +
    (c && !c.icp_brasil && !c.erro ? '<p class="as-explica">Este certificado é de fora da ICP-Brasil: a assinatura será íntegra, mas sem a validade jurídica de um e-CPF ou e-CNPJ credenciado.</p>' : "") + "</div>" +
    depois +
    '<div class="' + classeProteger + '" id="assina-proteger"><span class="duas-linhas"><b>Proteger o PDF com senha</b><small>quem receber vai precisar dessa senha para abrir</small></span><i></i></div>' +
    '<div class="em-senha" id="assina-senha-pdf"' + (assina.proteger ? "" : " hidden") + '><input type="password" id="assina-senha-campo" value="' + esc(assina.senhaPdf) + '" placeholder="senha para abrir o PDF"><button class="em-ligacao" id="assina-mostrar-pdf">mostrar</button></div>' +
    (lote ? '<p class="as-explica as-lote-salvar-nota">No fim, pergunto se você quer salvar os assinados um a um ou num .zip.</p>' : "") +
    "</div></div>" +
    pronto +
    (lote ? '<div class="as-lote-acao" id="as-lote-acao">' + acaoDoLote() + "</div>" : "") +
    compartilhar +
    "</div></aside>";
}

function ligarAssinar() {
  const raiz = $("assinatura");
  $("assina-trocar").onclick = () => (assina.lote ? sairDoLote() : mostrarAssinar());
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
  if (intervalo) intervalo.oninput = (e) => { assina.paginas = "intervalo"; assina.intervalo = e.target.value; if (assina.selo) mexeuNoSelo(); marcarEscolhaDePaginas(); atualizarFrase(); };

  $("assina-posicao").onchange = (e) => {
    assina.posicao = e.target.value;
    // Com o selo ja na pagina, escolher o canto leva o selo para la, no mesmo tamanho.
    if (assina.selo) assina.selo = seloNoCanto(assina.posicao, assina.selo.largura);
    mexeuNoSelo();
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
    const baixar = () => baixarArquivo(f.destino, "/api/assinar/baixar?arquivo=");
    $("assinado-baixar").onclick = baixar;
    $("assinado-conferir").onclick = () => abrirVerificacao(f.destino, nomeDe(f.destino));
  }
  // "Compartilhar depois" e do documento avulso; no lote, salvar e no fim.
  if (f && !f.aguardando_aprovacao && !assina.lote) {
    const baixar = () => baixarArquivo(f.destino, "/api/assinar/baixar?arquivo=");
    $("as-baixar").onclick = baixar;
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
  ligarLote();
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
  mexeuNoSelo();
  if (paginasEscolhidas().indexOf(assina.pagina) < 0) escolherPaginas("intervalo", String(assina.pagina));
  else atualizarFrase();
  // O canto padrao costuma ser o rodape: traz o selo para a vista.
  const selo = $("pdf-selo");
  if (selo && !selo.hidden) selo.scrollIntoView({ block: "nearest", behavior: animacoesLigadas() ? "smooth" : "auto" });
}

function removerSelo() {
  assina.selo = null;
  assina.menuSelo = false;
  mexeuNoSelo();
  atualizarFrase();
}

function escolherPaginas(valor, intervalo) {
  assina.paginas = valor;
  if (intervalo !== undefined) assina.intervalo = intervalo;
  if (assina.selo) mexeuNoSelo();
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
    mexeuNoSelo();
    atualizarFrase();
  };
  selo.onpointerup = soltar;
  selo.onpointercancel = soltar;
}

function paginasEscolhidas() {
  return paginasDe(assina.paginas, assina.intervalo, assina.doc.paginas);
}

/* As paginas de uma escolha num documento de `total` paginas - a do
   documento aberto, ou a de outro do lote. */
function paginasDe(escolha, intervalo, total) {
  if (escolha === "ultima") return [total];
  if (escolha === "primeira_ultima") return total > 1 ? [1, total] : [1];
  if (escolha === "intervalo") {
    const achados = new Set();
    String(intervalo || "").split(/[,;]/).forEach((pedaco) => {
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
  if (assina.lote) { prontoNoLote(caixa, falta); return; }
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
  if (assina.lote) { guardarNoLote(); atualizarLote(); }
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
      campo: c.precisa_senha ? { rotulo: doWindows ? "Senha do PAULUS" : "Senha do certificado", tipo: "password", icone: "key", selecionar: false } : undefined,
      confirmar: "Assinar",
    });
    if (!r || !r.ok) return;
    senha = c.precisa_senha ? r.valor : "";
  }

  const rotulo = botao ? botao.innerHTML : "";
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
  if (botao) { botao.disabled = false; botao.innerHTML = rotulo; }

  if (!r.ok) { avisoCert(await erroDe(r)); return; }
  const d = await r.json();
  // No lote, "Assinar so este" marca o documento e segue para o proximo;
  // salvar fica para a pergunta do fim.
  if (assina.lote) { await umDoLoteAssinado(origem, d); return; }
  if (d.aguardando_aprovacao) {
    assina.feito = d;
    desenharAssinatura();
    contarPendencias();
    // O recado de "quase pronto" fica no pe da coluna: traz para a vista.
    const quase = document.querySelector(".as-pronto.quase");
    if (quase) quase.scrollIntoView({ block: "nearest", behavior: animacoesLigadas() ? "smooth" : "auto" });
    return;
  }
  if (assina.baixar) baixarArquivo(d.destino, "/api/assinar/baixar?arquivo=");
  await abrirAssinado(Object.assign({ origem: origem }, d));
}

function telaAssinado(d) {
  assina.feito = d;
  desenharAssinatura();
}

function nomeDe(caminho) {
  return String(caminho || "").split(/[\\/]/).pop();
}

/* ------------------------------------------------------ assinar em lote */
/*
   Varios PDFs marcados na lista viram um lote. A tela e a mesma do
   documento avulso - o visor, o selo, a coluna -, com uma faixa "Documento
   2 de 5" e a lista do lote na coluna. A pessoa passa por um de cada vez:
   poe o selo (o primeiro documento sem selo que ela abre ja chega com o
   selo do ultimo em que ela pos, marcado como trazido, para conferir),
   pula o que nao vai assinar, e no fim assina os prontos com UMA
   confirmacao e UMA senha. Cada documento recebe a sua propria assinatura.

   Quando a regra de alcada pede aprovacao, o lote vira um pedido so em
   Aprovacoes (acao "assinatura.lote" no servidor), aprovado de uma vez.

   Estado de cada documento (estadoNoLote): sem selo, selo posto, pulado,
   assinado, em Aprovacoes, nao assinou (erro), nao abre.
*/

function novoLote(caminhos) {
  return {
    atual: -1, ultimo: null, pedido: null,
    itens: caminhos.map((c) => ({
      caminho: c, nome: nomeDe(c), doc: null, erro: "",
      selo: null, paginas: "ultima", intervalo: "", posicao: "", pagina: 0,
      visto: false, herdado: false, herdadoDe: 0, pulado: false,
      feito: null, pedido: null, falha: "",
    })),
  };
}

/* Le quantas paginas e o tamanho de cada documento - do assinado, quando
   ja foi assinado. O que nao abre fica no lote, marcado, com o motivo. */
async function lerDocsDoLote(l) {
  let cofre = null;
  await Promise.all(l.itens.map(async (it) => {
    const tentar = it.feito ? [it.feito.destino, it.caminho] : [it.caminho];
    for (const caminho of tentar) {
      try {
        const r = await fetch("/api/assinar/documento?arquivo=" + encodeURIComponent(caminho));
        if (!r.ok) { it.erro = await erroDe(r); continue; }
        const d = await r.json();
        it.doc = d.documento;
        it.erro = "";
        cofre = d;
        return;
      } catch (err) {
        it.erro = String(err);
      }
    }
  }));
  if (cofre) assina.cofre = cofre;
}

async function iniciarLote(caminhos) {
  const unicos = [...new Set(caminhos)];
  if (unicos.length < 2) { if (unicos[0]) mostrarAssinar(unicos[0]); return; }
  const l = novoLote(unicos);
  await lerDocsDoLote(l);
  const primeiro = l.itens.findIndex((it) => it.doc);
  if (primeiro < 0) { avisoCert("não consegui abrir nenhum dos documentos: " + (l.itens[0].erro || "erro ao ler")); return; }
  assina.lote = l;
  assina.escolhidos = new Set();
  assina.feito = null;
  assina.selo = null;
  assina.doc = null;
  assina.posicao = (assina.cofre && assina.cofre.selo && assina.cofre.selo.posicao) || "rodape_direita";
  await abrirDoLote(primeiro);
  const ruins = l.itens.filter((it) => !it.doc);
  if (ruins.length) {
    avisoCert(plural(ruins.length, "documento") + (ruins.length === 1 ? " não abriu e fica" : " não abriram e ficam") + " de fora: " + ruins.map((it) => it.nome).join(", "));
  }
}

/* Abre o documento i do lote no visor. Guarda antes o que a pessoa fez no
   documento que estava aberto. */
async function abrirDoLote(i) {
  const l = assina.lote;
  if (!l || !l.itens[i]) return;
  const it = l.itens[i];
  if (!it.doc) { avisoCert(it.nome + " não abre: " + (it.erro || "erro ao ler")); return; }
  guardarNoLote();
  // O assinado aparece como ficou, com o selo de verdade na pagina.
  if (it.feito && !it.docDoAssinado) {
    it.docDoAssinado = true;
    try {
      const r = await fetch("/api/assinar/documento?arquivo=" + encodeURIComponent(it.feito.destino));
      if (r.ok) it.doc = (await r.json()).documento;
    } catch (err) { /* fica o original, com o resultado na coluna */ }
  }
  l.atual = i;
  assina.doc = it.doc;
  assina.menuSelo = false;
  if (it.feito) assina.feito = Object.assign({ origem: it.caminho }, it.feito);
  else if (it.pedido) assina.feito = { aguardando_aprovacao: true, pedido: it.pedido };
  else assina.feito = null;
  if (!it.visto && !it.selo && !assina.feito) herdarSelo(it);
  it.visto = true;
  assina.selo = it.selo ? Object.assign({}, it.selo) : null;
  assina.paginas = it.paginas;
  assina.intervalo = it.intervalo;
  if (it.posicao) assina.posicao = it.posicao;
  const alvos = assina.selo ? paginasEscolhidas() : [];
  assina.pagina = Math.min(it.pagina || (alvos.length ? alvos[0] : it.doc.paginas), it.doc.paginas);
  desenharAssinatura();
  atualizarPostura();
}

/* O que esta no visor volta para o item do lote. Chamado a cada mudanca. */
function guardarNoLote() {
  const l = assina.lote;
  if (!l || l.atual < 0 || !assina.doc) return;
  const it = l.itens[l.atual];
  if (!it || it.feito || it.pedido) return;
  it.selo = assina.selo ? Object.assign({}, assina.selo) : null;
  it.paginas = assina.paginas;
  it.intervalo = assina.intervalo;
  it.posicao = assina.posicao;
  it.pagina = assina.pagina;
}

/* A pessoa mexeu no selo deste documento: ele deixa de ser "trazido", sai
   dos pulados e vira a referencia para o proximo documento sem selo. */
function mexeuNoSelo() {
  const l = assina.lote;
  if (!l || l.atual < 0) return;
  const it = l.itens[l.atual];
  if (!it || it.feito || it.pedido) return;
  it.herdado = false;
  it.pulado = false;
  it.falha = "";
  if (assina.selo) {
    l.ultimo = {
      selo: Object.assign({}, assina.selo), paginas: assina.paginas, intervalo: assina.intervalo, posicao: assina.posicao,
      largura: assina.doc.largura || 595, altura: assina.doc.altura || 842, nome: it.nome, numero: l.atual + 1,
    };
  }
}

/* O selo do ultimo documento em que a pessoa pos, levado para este: preso
   ao mesmo canto (um selo no rodape a direita continua no rodape a direita
   de uma folha de outro tamanho), no mesmo tamanho e com a mesma escolha de
   paginas. Um intervalo que nao existe neste documento vira "ultima". */
function herdarSelo(it) {
  const u = assina.lote.ultimo;
  if (!u) return;
  const L = it.doc.largura || 595, A = it.doc.altura || 842;
  const m = medidasDoSelo(u.selo.largura);
  const direita = u.selo.x + m.w / 2 > u.largura / 2;
  const embaixo = u.selo.y + m.h / 2 > u.altura / 2;
  it.selo = prenderNaPagina({
    x: direita ? L - (u.largura - u.selo.x) : u.selo.x,
    y: embaixo ? A - (u.altura - u.selo.y) : u.selo.y,
    largura: m.w,
  });
  it.paginas = u.paginas;
  it.intervalo = u.intervalo;
  it.posicao = u.posicao;
  if (!paginasDe(it.paginas, it.intervalo, it.doc.paginas).length) { it.paginas = "ultima"; it.intervalo = ""; }
  it.herdado = true;
  it.herdadoDe = u.numero;
}

function estadoNoLote(it) {
  if (it.feito) return { chave: "assinado", rotulo: "assinado" };
  if (it.pedido) return { chave: "aguardando", rotulo: "em Aprovações" };
  if (!it.doc) return { chave: "fora", rotulo: "não abre", motivo: it.erro || "erro ao ler" };
  if (it.pulado) return { chave: "pulado", rotulo: "pulado" };
  if (it.falha) return { chave: "falhou", rotulo: "não assinou", motivo: it.falha };
  if (it.selo && paginasDe(it.paginas, it.intervalo, it.doc.paginas).length) {
    return { chave: "posto", rotulo: it.herdado ? "selo trazido" : "selo posto" };
  }
  return { chave: "sem", rotulo: "sem selo" };
}

/* O estado de cada documento do lote, num icone: da para bater o olho na
   coluna e ver o que falta sem ler etiqueta por etiqueta. */
const ICONE_NO_LOTE = {
  sem: "radio_button_unchecked", posto: "radio_button_partial", pulado: "remove",
  assinado: "check_circle", aguardando: "schedule", falhou: "error", fora: "error",
};

function contagemDoLote() {
  const conta = { sem: 0, posto: 0, pulado: 0, assinado: 0, aguardando: 0, falhou: 0, fora: 0 };
  (assina.lote ? assina.lote.itens : []).forEach((it) => { conta[estadoNoLote(it).chave] += 1; });
  return conta;
}

/* A faixa em cima do visor: onde estou no lote, e o que falta neste. */
function faixaDoLote() {
  const l = assina.lote;
  const it = l.itens[l.atual];
  const n = l.itens.length;
  const e = estadoNoLote(it);
  let aviso;
  if (e.chave === "assinado") aviso = ic("check_circle", 16) + "<span>Assinado · código " + esc(it.feito.codigo || "") + "</span>";
  else if (e.chave === "aguardando") aviso = ic("schedule", 16) + "<span>Esperando o seu sim em Aprovações</span>";
  else if (e.chave === "pulado") aviso = ic("skip_next", 16) + "<span>Pulado: fica de fora do lote</span>";
  else if (e.chave === "falhou") aviso = ic("error", 16) + "<span>Não assinou: " + esc(it.falha) + "</span>";
  else if (e.chave === "posto" && it.herdado) aviso = ic("content_copy", 16) + "<span>Selo trazido do documento " + esc(String(it.herdadoDe)) + " — mesmo canto, tamanho e páginas. Confira antes de assinar.</span>";
  else if (e.chave === "posto") aviso = ic("task_alt", 16) + "<span>Selo posto</span>";
  else aviso = ic("draw", 16) + "<span>Sem selo: ponha a assinatura na página, ou pule este documento</span>";
  const classeAviso = "as-lote-aviso " + e.chave + (it.herdado && e.chave === "posto" ? " trazido" : "");
  const pendente = !it.feito && !it.pedido;
  return '<div class="as-lote-faixa" id="as-lote-faixa">' +
    '<button class="voltar" id="lote-antes" title="Documento anterior" aria-label="Documento anterior"' + (l.atual > 0 ? "" : " disabled") + ">" + ic("chevron_left", 18) + "</button>" +
    '<span class="as-lote-conta">Documento <b>' + (l.atual + 1) + "</b> de " + n + "</span>" +
    '<button class="voltar" id="lote-depois" title="Próximo documento" aria-label="Próximo documento"' + (l.atual < n - 1 ? "" : " disabled") + ">" + ic("chevron_right", 18) + "</button>" +
    '<span class="docs-divisa-fina"></span><span class="' + classeAviso + '">' + aviso + "</span><span class=\"cresce\"></span>" +
    (pendente && e.chave === "pulado" ? '<button class="em-ligacao" id="lote-incluir">Incluir de novo</button>' : "") +
    (pendente && e.chave !== "pulado" ? '<button class="em-ligacao" id="lote-pular">Pular este</button>' : "") +
    (l.atual < n - 1 ? '<button class="com-icone" id="lote-proximo">Próximo' + ic("chevron_right", 16) + "</button>" : "") + "</div>";
}

/* Na coluna: os documentos do lote, cada um com o seu estado. */
function blocoDoLote() {
  const l = assina.lote;
  const conta = contagemDoLote();
  const partes = [];
  if (conta.posto) partes.push(plural(conta.posto, "pronto"));
  if (conta.assinado) partes.push(plural(conta.assinado, "assinado"));
  if (conta.aguardando) partes.push(conta.aguardando + " em Aprovações");
  const linhas = l.itens.map((it, i) => {
    const e = estadoNoLote(it);
    const classe = "as-lote-item" + (i === l.atual ? " atual" : "");
    const icone = ICONE_NO_LOTE[e.chave] || "radio_button_unchecked";
    return '<button type="button" class="' + classe + " " + e.chave + '" data-lote-ir="' + i + '" title="' + esc(it.nome + (e.motivo ? " — " + e.motivo : "")) + '">' +
      '<span class="as-lote-ic">' + ic(icone, 18) + '</span><span class="duas-linhas as-lote-texto"><b>' + esc(it.nome) + "</b>" +
      '<small>' + (i + 1) + " · " + esc(e.rotulo) + "</small></span></button>";
  }).join("");
  return '<div class="painel-bloco-cabeca"><span>Documentos do lote</span><span class="contagem">' + (partes.join(" · ") || "nenhum pronto ainda") + "</span></div>" +
    '<div class="as-lote-lista">' + linhas + "</div>";
}

/* O pe da coluna no lote: assinar os prontos, o pedido em Aprovacoes, e
   salvar os assinados. */
function acaoDoLote() {
  const l = assina.lote;
  const conta = contagemDoLote();
  const sozinho = (cert.dados || {}).pode_assinar_sozinho !== false;
  const cabeca = (icone, texto) => '<div class="as-pronto-cabeca">' + ic(icone, 18) + "<span>" + texto + "</span></div>";
  let html = "";
  if (conta.aguardando) {
    html += '<div class="as-pronto quase">' + cabeca("task_alt", "Está quase pronto — só falta a confirmação") +
      "<p>" + (conta.aguardando === 1 ? "1 documento do lote está" : conta.aguardando + " documentos do lote estão") +
      " em Aprovações. Nada foi assinado ainda: assinar tem efeito jurídico, então falta o seu sim. Depois dele, eu trago você de volta para cá, com os assinados.</p>" +
      '<div class="as-pronto-acoes"><button class="primario com-icone" id="lote-ver-fila">' + ic("verified", 16) + "Confirmar em Aprovações</button></div></div>";
  }
  if (conta.posto) {
    html += '<div class="as-pronto pronto">' + cabeca("draw", conta.posto === 1 ? "1 documento pronto" : conta.posto + " documentos prontos") +
      "<p>" + (sozinho
        ? "Assino todos os prontos com uma confirmação e uma senha só. Cada documento recebe a sua própria assinatura, com o selo onde você o pôs."
        : "Pela regra de alçada, os prontos vão para Aprovações num pedido só: nada é assinado antes do seu sim.") + "</p>" +
      '<div class="as-pronto-acoes"><button class="primario com-icone" id="lote-assinar">' + ic("draw", 16) +
      (sozinho ? "Assinar " + plural(conta.posto, "documento") : "Pedir aprovação") + "</button></div></div>";
  }
  if (conta.assinado) {
    html += '<div class="as-pronto feito">' + cabeca("check_circle", conta.assinado === 1 ? "1 documento assinado" : conta.assinado + " documentos assinados") +
      "<p>Para levar uma cópia para fora do programa, salve um a um ou num .zip.</p>" +
      '<div class="as-pronto-acoes"><button class="primario com-icone" id="lote-salvar">' + ic("download", 16) + "Salvar os assinados</button></div></div>";
  }
  if (!html) {
    html = '<div class="as-pronto falta">' + cabeca("draw", "Nenhum documento pronto") +
      "<p>Ponha o selo em cada documento que vai assinar. Os pulados ficam de fora.</p></div>";
  }
  return html;
}

/* A caixa "pronto" do documento aberto, no lote: pular, ou assinar so este
   e seguir. */
function prontoNoLote(caixa, falta) {
  const l = assina.lote;
  const temProximo = l.atual < l.itens.length - 1;
  const cabeca = (icone, texto) => '<div class="as-pronto-cabeca">' + ic(icone, 18) + "<span>" + texto + "</span></div>";
  if (falta) {
    caixa.className = "as-pronto falta";
    caixa.innerHTML = cabeca(falta.icone, falta.titulo) + "<p>" + falta.texto + "</p>" +
      '<div class="as-pronto-acoes"><button class="em-ligacao" id="lote-pular-aqui">Pular este documento</button>' + falta.botao + "</div>";
  } else {
    caixa.className = "as-pronto pronto";
    caixa.innerHTML = cabeca("task_alt", "Selo posto neste documento") + '<p id="assina-frase">' + esc(fraseDeAssinar()) + "</p>" +
      '<div class="as-pronto-acoes"><button class="em-ligacao" id="assina-agora">Assinar só este</button>' +
      (temProximo ? '<button class="primario com-icone" id="lote-seguir">Próximo documento' + ic("chevron_right", 16) + "</button>" : "") + "</div>";
  }
  const agora = $("assina-agora");
  if (agora) agora.onclick = assinarAgora;
  const add = $("assina-add-pronto");
  if (add) add.onclick = () => adicionarSelo();
  const pular = $("lote-pular-aqui");
  if (pular) pular.onclick = pularNoLote;
  const seguir = $("lote-seguir");
  if (seguir) seguir.onclick = () => abrirDoLote(l.atual + 1);
  caixa.querySelectorAll("[data-as-visao]").forEach((b) => { b.onclick = () => mostrarCertificado(); });
}

/* O botao do cabecalho, no lote. */
function topoDoLote() {
  const conta = contagemDoLote();
  const sozinho = (cert.dados || {}).pode_assinar_sozinho !== false;
  return {
    texto: conta.posto ? (sozinho ? "Assinar " + plural(conta.posto, "pronto") : "Pedir aprovação (" + conta.posto + ")") : "Assinar os prontos",
    desligado: !conta.posto,
  };
}

/* Redesenha o que depende do estado do lote, sem refazer o visor. */
function atualizarLote() {
  const l = assina.lote;
  if (!l) return;
  const faixa = $("as-lote-faixa");
  if (faixa) faixa.outerHTML = faixaDoLote();
  const bloco = $("as-lote-bloco");
  if (bloco) bloco.innerHTML = blocoDoLote();
  const acao = $("as-lote-acao");
  if (acao) acao.innerHTML = acaoDoLote();
  const topo = $("assina-lote-topo");
  if (topo) {
    const t = topoDoLote();
    topo.innerHTML = ic("draw", 16) + esc(t.texto);
    topo.disabled = t.desligado;
  }
  ligarLote();
}

function ligarLote() {
  const l = assina.lote;
  if (!l) return;
  const ligar = (id, fazer) => { const el = document.getElementById(id); if (el) el.onclick = fazer; };
  ligar("lote-antes", () => abrirDoLote(l.atual - 1));
  ligar("lote-depois", () => abrirDoLote(l.atual + 1));
  ligar("lote-proximo", () => abrirDoLote(l.atual + 1));
  ligar("lote-pular", pularNoLote);
  ligar("lote-incluir", () => { l.itens[l.atual].pulado = false; atualizarLote(); });
  ligar("lote-assinar", assinarLote);
  ligar("assina-lote-topo", assinarLote);
  ligar("lote-salvar", perguntarComoSalvar);
  ligar("assina-trocar", sairDoLote);
  ligar("lote-ver-fila", () => {
    if (l.pedido && typeof aprov !== "undefined") aprov.aberto = l.pedido.id;
    marcarDestino("aprovacoes");
    mostrarAprovacoes();
  });
  document.querySelectorAll("[data-lote-ir]").forEach((b) => { b.onclick = () => abrirDoLote(Number(b.dataset.loteIr)); });
}

/* Pular: o documento fica de fora (o selo, se tinha, fica guardado para o
   caso de a pessoa incluir de novo) e a tela segue para o proximo. */
function pularNoLote() {
  const l = assina.lote;
  if (!l) return;
  guardarNoLote();
  l.itens[l.atual].pulado = true;
  if (l.atual < l.itens.length - 1) abrirDoLote(l.atual + 1);
  else atualizarLote();
}

async function sairDoLote() {
  const l = assina.lote;
  if (!l) return;
  guardarNoLote();
  const conta = contagemDoLote();
  if (conta.posto) {
    const ok = await confirmar({
      titulo: "Sair do lote?", contexto: "Assinatura › Lote",
      texto: "O selo posto em " + plural(conta.posto, "documento") + " que ainda não " + (conta.posto === 1 ? "foi assinado" : "foram assinados") +
        " se perde." + (conta.assinado ? " O que já foi assinado continua assinado." : ""),
      confirmar: "Sair do lote",
    });
    if (!ok) return;
  }
  assina.lote = null;
  assina.doc = null;
  assina.selo = null;
  assina.feito = null;
  mostrarAssinar();
}

/* "Assinar os prontos": antes, diz quem fica de fora e por que; depois,
   uma confirmacao e uma senha para todos. */
async function assinarLote() {
  const l = assina.lote;
  if (!l) return;
  guardarNoLote();
  const estados = l.itens.map(estadoNoLote);
  const prontos = l.itens.filter((it, i) => estados[i].chave === "posto");
  const fora = l.itens.map((it, i) => ({ it: it, i: i, e: estados[i] })).filter((x) => ["sem", "pulado", "falhou", "fora"].indexOf(x.e.chave) >= 0);
  const porque = (x) => ({
    sem: "sem selo — a assinatura não foi posta na página",
    pulado: "pulado por você",
    falhou: "não assinou: " + x.e.motivo,
    fora: "não abre: " + x.e.motivo,
  })[x.e.chave];

  if (fora.length) {
    const lista = '<ul class="as-lote-rol">' + fora.map((x) => "<li><b>" + esc(x.it.nome) + "</b><span>" + esc(porque(x)) + "</span></li>").join("") + "</ul>";
    const seguir = prontos.length
      ? "Se seguir, " + (prontos.length === 1 ? "só o documento pronto entra" : "só os " + prontos.length + " prontos entram") + ". Os de fora continuam como estão, sem esta assinatura."
      : "Nenhum documento está pronto para assinar.";
    const r = await dialogo({
      titulo: fora.length === 1 ? "1 documento vai ficar de fora" : fora.length + " documentos vão ficar de fora",
      contexto: "Assinatura › Lote",
      html: lista + "<p>" + esc(seguir) + "</p>",
      confirmar: prontos.length ? "Seguir assim" : "Voltar para eles",
      cancelar: prontos.length ? "Voltar para eles" : "Fechar",
    });
    const voltar = prontos.length ? !(r && r.ok) : Boolean(r && r.ok);
    // Voltar abre o primeiro que ficou de fora e que da para abrir.
    if (voltar) {
      const alvo = fora.find((x) => x.it.doc);
      if (alvo) abrirDoLote(alvo.i);
      return;
    }
    if (!prontos.length) return;
  }
  if (!prontos.length) { avisoCert("ponha o selo em pelo menos um documento"); return; }

  // A senha pode ter vencido desde que o lote abriu: pergunta de novo ao servidor.
  try {
    const r = await fetch("/api/assinar/documento?arquivo=" + encodeURIComponent(prontos[0].caminho));
    if (r.ok) assina.cofre = await r.json();
  } catch (err) { /* segue com o que ja sabia; o servidor confere a senha de novo */ }
  const c = assina.cofre || {};
  const doWindows = c.origem === "windows";
  const titular = (c.certificado && c.certificado.titular) || "";
  const sozinho = (cert.dados || {}).pode_assinar_sozinho !== false;
  const n = prontos.length;
  const vao = '<ul class="as-lote-rol">' + prontos.map((it) =>
    "<li><b>" + esc(it.nome) + "</b><span>selo " + (paginasDe(it.paginas, it.intervalo, it.doc.paginas).length > 1
      ? "nas páginas " + paginasDe(it.paginas, it.intervalo, it.doc.paginas).join(", ")
      : "na página " + paginasDe(it.paginas, it.intervalo, it.doc.paginas)[0]) + "</span></li>").join("") + "</ul>";
  let nota = sozinho
    ? "Cada documento recebe a sua própria assinatura, com o selo onde você o pôs."
    : "Pela regra de alçada, nada é assinado agora: o lote vira um pedido só em Aprovações e é assinado depois do seu sim.";
  if (assina.senhaPdf) nota += " Os arquivos saem protegidos por senha.";
  nota += " Nada é enviado para a internet.";
  if (doWindows && sozinho) nota += " Se o certificado foi instalado com proteção forte, o Windows pode pedir a senha dele em cada documento.";
  const r = await dialogo({
    titulo: (sozinho ? "Assinar " + plural(n, "documento") : "Pedir aprovação para " + plural(n, "documento")) + (titular ? " como " + titular : "") + "?",
    contexto: "Assinatura › Lote",
    html: vao + "<p>" + esc(nota) + "</p>",
    campo: c.precisa_senha ? { rotulo: doWindows ? "Senha do PAULUS" : "Senha do certificado", tipo: "password", icone: "key", selecionar: false } : undefined,
    confirmar: sozinho ? "Assinar " + n : "Pedir aprovação",
  });
  if (!r || !r.ok) return;
  const senha = c.precisa_senha ? r.valor : "";

  const botoes = [$("lote-assinar"), $("assina-lote-topo")].filter(Boolean);
  botoes.forEach((b) => { b.disabled = true; b.textContent = sozinho ? "assinando " + n + "…" : "pedindo…"; });
  let resposta;
  try {
    resposta = await fetch("/api/assinar/lote", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        itens: prontos.map((it) => ({
          arquivo: it.caminho, paginas: it.paginas, intervalo: it.intervalo, posicao: it.posicao || "rodape_direita",
          x: it.selo.x, y: it.selo.y, tamanho: it.selo.largura,
        })),
        senha_pdf: assina.senhaPdf,
        guardar_biblioteca: assina.biblioteca,
        manter_original: assina.manter,
        senha_certificado: senha,
      }),
    });
  } catch (err) {
    avisoCert("não consegui assinar: " + String(err));
    atualizarLote();
    return;
  }
  if (!resposta.ok) { avisoCert(await erroDe(resposta)); atualizarLote(); return; }
  const d = await resposta.json();
  marcarResultadoDoLote(d);
  const falhas = d.falhas || [];
  if (d.aguardando_aprovacao) {
    contarPendencias();
    await abrirDoLote(l.atual);
    const quase = document.querySelector("#as-lote-acao .as-pronto.quase");
    if (quase) quase.scrollIntoView({ block: "nearest", behavior: animacoesLigadas() ? "smooth" : "auto" });
    if (falhas.length) avisoCert(plural(falhas.length, "documento") + " não entrou no pedido: " + falhas.map((f) => f.nome + " (" + f.motivo + ")").join("; "));
    return;
  }
  // Mostra o primeiro que acabou de ser assinado, com o selo de verdade.
  const primeiro = l.itens.findIndex((it) => it.feito && (d.feitos || []).some((f) => f.origem === it.caminho));
  await abrirDoLote(primeiro >= 0 ? primeiro : l.atual);
  if (falhas.length) avisoCert(plural(falhas.length, "documento") + (falhas.length === 1 ? " não foi assinado: " : " não foram assinados: ") + falhas.map((f) => f.nome + " (" + f.motivo + ")").join("; "));
  if ((d.feitos || []).length) await perguntarComoSalvar();
}

/* A resposta do servidor (ou o desfecho depois do sim) volta para os itens. */
function marcarResultadoDoLote(d) {
  const l = assina.lote;
  if (!l) return;
  const achar = (caminho) => l.itens.find((it) => it.caminho === caminho);
  (d.falhas || []).forEach((f) => { const it = achar(f.arquivo); if (it) { it.falha = f.motivo; it.pedido = null; } });
  if (d.aguardando_aprovacao && d.pedido) {
    l.pedido = d.pedido;
    ((d.pedido.dados || {}).arquivos || []).forEach((c) => { const it = achar(c); if (it) it.pedido = d.pedido; });
  }
  (d.feitos || []).forEach((f) => {
    const it = achar(f.origem);
    if (it) { it.feito = f; it.pedido = null; it.falha = ""; it.docDoAssinado = false; }
  });
}

/* "Assinar so este", dentro do lote. */
async function umDoLoteAssinado(origem, d) {
  const l = assina.lote;
  const it = l.itens.find((x) => x.caminho === origem);
  if (!it) return;
  if (d.aguardando_aprovacao) {
    it.pedido = d.pedido;
    if (!l.pedido) l.pedido = d.pedido;
    contarPendencias();
  } else {
    it.feito = d;
    it.docDoAssinado = false;
    avisoCert(it.nome + " assinado · código " + d.codigo, { tom: "ok" });
  }
  // Segue para o proximo que ainda nao foi resolvido; sem nenhum, fica aqui.
  const i = l.itens.findIndex((x, j) => j > l.atual && ["sem", "posto"].indexOf(estadoNoLote(x).chave) >= 0);
  await abrirDoLote(i >= 0 ? i : l.itens.indexOf(it));
}

/* Salvar os assinados: um a um, ou um .zip com todos. Os assinados ja estao
   gravados (no Acervo ou ao lado do original, como a pessoa escolheu); isto
   leva uma copia para fora. */
async function perguntarComoSalvar() {
  const l = assina.lote;
  const arquivos = l ? l.itens.filter((it) => it.feito).map((it) => it.feito.destino) : [];
  if (!arquivos.length) { avisoCert("nenhum documento assinado para salvar ainda"); return; }
  const n = arquivos.length;
  let modo = n > 1 ? "zip" : "um";
  const opcao = (valor, icone, titulo, sub) => {
    const classe = "as-salvar-opcao" + (valor === modo ? " on" : "");
    return '<button type="button" class="' + classe + '" data-salvar="' + valor + '" aria-pressed="' + (valor === modo) + '">' + ic(icone, 20) +
      '<span class="duas-linhas"><b>' + titulo + "</b><small>" + sub + "</small></span></button>";
  };
  const escolha = dialogo({
    titulo: n === 1 ? "Como salvar o PDF assinado?" : "Como salvar os " + n + " PDFs assinados?",
    contexto: "Assinatura › Lote",
    texto: "Eles já estão gravados nesta máquina. Aqui você leva uma cópia para onde quiser.",
    html: '<div class="as-salvar-opcoes">' +
      opcao("zip", "archive", "Um .zip com todos", (n === 1 ? "o PDF" : "os " + n + " PDFs") + " num arquivo só · nome repetido ganha um número") +
      opcao("um", "picture_as_pdf", "Um a um", "cada PDF solto, na pasta que você escolher · nada que já está lá é substituído") + "</div>",
    confirmar: "Salvar", cancelar: "Agora não",
  });
  const botoes = document.querySelectorAll("#veu-dialogo [data-salvar]");
  botoes.forEach((b) => {
    b.onclick = () => {
      modo = b.dataset.salvar;
      botoes.forEach((x) => { x.classList.toggle("on", x === b); x.setAttribute("aria-pressed", String(x === b)); });
    };
  });
  const r = await escolha;
  if (!r || !r.ok) return;
  await salvarAssinados(modo, arquivos);
}

/* Na janela do programa, download de navegador nao chega a lugar nenhum: o
   .zip passa pelo "Salvar como" do Windows e o um a um pela escolha de
   pasta, e o servidor grava. No navegador, downloads comuns. */
async function salvarAssinados(modo, arquivos) {
  /* A pasta sai do seletor do PAULUS e quem grava e o servidor: vale igual
     na janela do programa e no navegador. Nada e sobrescrito - nome repetido
     ganha "(2)". */
  const json = { "Content-Type": "application/json" };
  const hoje = new Date().toISOString().slice(0, 10);
  if (modo === "zip") {
    const e = await escolherPastaNossa({ titulo: "Onde salvar o .zip", contexto: "Assinatura em lote", nome: "PDFs assinados " + hoje + ".zip" });
    if (!e) return;
    const caminho = e.pasta.replace(/[\\/]+$/, "") + "\\" + e.nome;
    const r = await fetch("/api/assinar/zip", { method: "POST", headers: json, body: JSON.stringify({ arquivos: arquivos, caminho: caminho }) });
    if (!r.ok) { avisoCert(await erroDe(r), { tom: "erro" }); return; }
    const d = await r.json();
    avisoCert(plural(d.quantos, "PDF", "PDFs") + " no " + d.nome + " — " + e.pasta, { tom: "ok" });
    return;
  }
  const e = await escolherPastaNossa({ titulo: "Onde salvar os PDFs assinados", contexto: "Assinatura em lote" });
  if (!e) return;
  const r = await fetch("/api/assinar/copiar", { method: "POST", headers: json, body: JSON.stringify({ arquivos: arquivos, pasta: e.pasta }) });
  if (!r.ok) { avisoCert(await erroDe(r), { tom: "erro" }); return; }
  const d = await r.json();
  avisoCert(plural(d.copiados.length, "PDF", "PDFs") + (d.copiados.length === 1 ? " salvo em " : " salvos em ") + d.pasta, { tom: "ok" });
}

/* Depois do sim em Aprovacoes a um pedido de lote: volta para o lote (o
   mesmo, se ainda esta aberto; senao, um novo so com os documentos do
   pedido), mostra os assinados e pergunta como salvar. */
async function mostrarLoteAssinado(desfecho) {
  const feitos = desfecho.feitos || [];
  const falhas = desfecho.falhas || [];
  const origens = feitos.map((f) => f.origem).concat(falhas.map((f) => f.arquivo));
  if (!origens.length) return false;
  let l = assina.lote;
  const mesmo = l && l.itens.some((it) => origens.indexOf(it.caminho) >= 0);
  if (!mesmo) {
    l = novoLote(origens);
    assina.lote = l;
  }
  marcarResultadoDoLote({ feitos: feitos, falhas: falhas });
  l.pedido = null;
  l.itens.forEach((it) => { if (it.pedido && origens.indexOf(it.caminho) >= 0) it.pedido = null; });
  if (!mesmo) await lerDocsDoLote(l);

  abrirTela("Assinatura", { cheia: true });
  marcarDestino("assinar");
  cert.visao = "assinar";
  try { cert.dados = await (await fetch("/api/certificado")).json(); } catch (err) { /* a tela abre com o que tem */ }
  const primeiro = l.itens.findIndex((it) => it.feito && it.doc);
  if (primeiro < 0) { avisoCert("nenhum documento do lote foi assinado"); return false; }
  await abrirDoLote(primeiro);
  if (feitos.length) perguntarComoSalvar();
  return true;
}
