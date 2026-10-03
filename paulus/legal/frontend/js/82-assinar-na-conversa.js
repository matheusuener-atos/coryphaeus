/* ---------------------------------------- assinar pela conversa (T3) */
/*
   Pacote de telas de 01/10/2026: `Conversa - Assinar`. "Assine o contrato de
   honorários" (src/intencao.py, ler_assinatura) abre o PDF na coluna da
   direita, com o selo ja posto onde o certificado guarda (a ultima pagina,
   no canto escolhido em Certificado), e a conversa traz o cartao das
   escolhas: onde a assinatura entra, com qual certificado e o que fazer
   depois. O selo arrasta e muda de tamanho na pagina, como na tela
   Assinatura - e o mesmo codigo (js/17-assinar.js), so mudou de lugar.

   Assinar continua pedindo o sim (e a senha), como sempre: o dialogo e o de
   assinarAgora. Com Limites da IA mandando passar por Aprovacoes, o pedido
   fica la e o cartao diz isso. O resultado entra na conversa
   (/fazer "assinatura"); o original nunca e sobrescrito.
*/

const asc = {
  ativa: false,      // a assinatura pela conversa esta aberta
  caixa: null,       // o cartao das escolhas, no chat
  nome: "",
  escala: 100,
};

const ROTULO_CURTO_DAS_PAGINAS = { ultima: "Só a última página", todas: "Todas", primeira_ultima: "Primeira e última", intervalo: "Intervalo…" };
const ASC_ESCALAS = [75, 90, 100, 110, 125, 150];

/* O cartao da proposta: aberto ao vivo; guardado (a conversa reaberta), so o
   convite para abrir de novo. */
function cartaoDeAssinar(d) {
  const c = d.campos || {};
  return '<div class="proposta asc-cartao asc-fechado"><div class="asc-linha">' + glifo(c.nome || "") +
    '<b class="asc-nome" title="' + esc(c.nome || "") + '">' + esc(c.nome || "") + "</b>" +
    '<button class="primario" data-asc-abrir="1">Abrir a assinatura</button></div></div>';
}

function ligarAssinarNaProposta(caixa, d) {
  const c = d.campos || {};
  const abrir = () => assinarAoLado({ caminho: c.caminho, nome: c.nome }, caixa);
  const b = caixa.querySelector("[data-asc-abrir]");
  if (b) b.onclick = abrir;
  if (!caixa.dataset.propostaGuardada) abrir();
}

/* Abre o PDF ao lado, com o selo, e o cartao das escolhas no chat. `caixa`:
   onde o cartao mora (a proposta); sem ela, o cartao entra no fim da conversa. */
async function assinarAoLado(reg, caixa) {
  if (!reg || !reg.caminho) { avisoNaJanela("Não achei o arquivo para assinar", { icone: "error" }); return; }
  try {
    cert.dados = await (await fetch("/api/certificado")).json();
  } catch (err) { cert.dados = {}; }
  const r = await fetch("/api/assinar/documento?arquivo=" + encodeURIComponent(reg.caminho)).catch(() => null);
  if (!r || !r.ok) { avisoNaJanela("Não consegui abrir para assinar: " + (r ? await erroDe(r) : "sem resposta"), { icone: "error" }); return; }
  const d = await r.json();
  Object.assign(assina, {
    doc: d.documento, cofre: d, lote: null, feito: null, menuSelo: false,
    pagina: d.documento.paginas, paginas: "ultima", intervalo: "",
    posicao: (d.selo && d.selo.posicao) || "rodape_direita",
  });
  // O selo ja vem posto, no canto que o certificado guarda: e o que a
  // conversa disse ("Coloquei a assinatura no rodapé da última página").
  assina.selo = seloNoCanto(assina.posicao);
  asc.ativa = true;
  asc.nome = reg.nome || d.documento.nome;
  asc.escala = 100;

  if (!caixa) {
    // Veio de um botao (o Assinar do visor ou do editor), e nao de um pedido
    // escrito: a conversa diz o que fez, como diria ao pedido.
    const rotulo = ((d.posicoes || []).find((p) => p.valor === assina.posicao) || {}).rotulo || "";
    const resposta = document.createElement("div");
    resposta.className = "resposta";
    resposta.innerHTML = '<div class="texto">' + esc("Coloquei a assinatura na última página" + (rotulo ? " (" + rotulo.toLowerCase() + ")" : "") +
      ". Confira ao lado, ajuste o que quiser aqui e assine.") + "</div>";
    caixa = document.createElement("div");
    caixa.className = "proposta-caixa";
    resposta.appendChild(caixa);
    $("centro").appendChild(resposta);
  }
  asc.caixa = caixa;
  caixa.innerHTML = cartaoDasEscolhas();
  ligarCartaoDasEscolhas();
  definirFoco([asc.nome]);

  abrirNoLado("ferramenta", {
    chave: "assinar:" + reg.caminho,
    html: htmlDoAssinarAoLado(),
    ligar: ligarAssinarAoLado,
    aoFechar: () => {
      asc.ativa = false;
      if (asc.caixa && asc.caixa.isConnected && asc.caixa.querySelector(".asc-escolhas")) {
        asc.caixa.innerHTML = cartaoDeAssinar({ campos: { nome: asc.nome, caminho: reg.caminho } });
        asc.caixa.querySelector("[data-asc-abrir]").onclick = () => assinarAoLado(reg, asc.caixa);
      }
      atualizarPostura();
    },
  });
  atualizarPostura();
  if (pertoDoFim()) rolar();
}

/* ------------------------------------------------- a coluna: o PDF */

function htmlDoAssinarAoLado() {
  const doc = assina.doc;
  const total = Math.min(doc.paginas, 40);
  let minis = "";
  for (let i = 1; i <= total; i++) {
    minis += '<button class="fl-mini" data-pdf-pagina="' + i + '" title="Página ' + i + '"><img alt="" loading="lazy" src="/api/assinar/pagina?arquivo=' +
      encodeURIComponent(doc.caminho) + "&numero=" + i + '&largura=240"><small>' + i + "</small></button>";
  }
  return '<div class="fl" data-fl-tipo="assinar">' +
    topoDaFerramenta({
      nome: doc.nome, linhaHtml: '<small id="asc-linha">' + esc(linhaDoAssinar()) + "</small>",
      acoes: botaoNoWindows() + '<button data-fl="editar">Abrir editor</button>' +
        '<button class="primario" id="assina-agora-topo">Assinar agora</button>',
    }) +
    '<div class="fl-quadro as-cartao">' +
    '<div class="fl-barra">' +
    // O convite fica a vista mesmo com o selo posto (no desenho); o
    // #pdf-adicionar que js/17-assinar.js liga e desliga fica vazio aqui.
    '<span class="as-adicionar" id="pdf-adicionar" hidden></span>' +
    '<span class="as-adicionar"><button class="edl-texto asc-adicionar" id="assina-add-pagina">' + ic("add", 16) + "Adicionar assinatura</button><small>ou clique na página</small></span>" +
    '<span class="as-nesta" id="pdf-nesta" hidden><span>Sem assinatura nesta página</span><button class="em-ligacao forte" id="assina-por-aqui">pôr aqui também</button></span>' +
    '<span class="cresce"></span>' +
    '<span class="fl-pag">Página <span class="asc-pagina" id="pdf-num">' + assina.pagina + "</span> de " + doc.paginas + "</span>" +
    '<span class="divisa-v"></span><span class="fl-zoom"><button class="botao-icone" data-asc="menos" aria-label="Diminuir">' + ic("remove", 16) + "</button>" +
    '<span class="fl-mono" id="asc-escala">100%</span><button class="botao-icone" data-asc="mais" aria-label="Aumentar">' + ic("add", 16) + "</button></span></div>" +
    '<div class="fl-mesa com-miniaturas"><div class="fl-miniaturas" id="pdf-minis">' + minis + "</div>" +
    '<div class="fl-folhas as-visor"><div class="pdf-folha" id="pdf-folha"><img class="docs-pagina" id="pdf-img" alt="página ' + assina.pagina + '">' +
    '<div class="pdf-selo" id="pdf-selo" hidden><div class="as-selo-dentro" id="pdf-selo-conteudo">' + previaSelo(cert.dados || {}) + "</div>" +
    '<div class="as-selo-barra" id="pdf-selo-barra">' +
    '<button type="button" id="selo-replicar" title="Repetir o selo em outras páginas" aria-haspopup="menu">' + ic("content_copy", 14) + '<span id="selo-replicar-rotulo">Replicar</span></button>' +
    '<button type="button" id="selo-remover" title="Tirar a assinatura" aria-label="Tirar a assinatura">' + ic("delete", 14) + "</button>" +
    '<div class="as-selo-menu" id="selo-menu" role="menu" hidden></div></div>' +
    '<span class="as-selo-legenda">' + ic("open_with", 14) + '<span id="pdf-selo-texto">arraste para mover</span></span>' +
    '<i class="as-alca a" data-alca="a"></i><i class="as-alca b" data-alca="b"></i><i class="as-alca c" data-alca="c"></i><i class="as-alca d" data-alca="d"></i></div></div></div></div>' +
    '<div class="fl-pe"><span>' + esc(plural(assina.doc.paginas, "página") + " · " + String(assina.doc.mb).replace(".", ",") + " MB") + "</span>" +
    '<span class="fl-pe-nota">o arquivo original não é alterado</span></div>' +
    "</div></div>";
}

function linhaDoAssinar() {
  const alvos = assina.selo ? paginasEscolhidas() : [];
  const partes = ["PDF", plural(assina.doc.paginas, "página")];
  partes.push(alvos.length ? "assinatura posicionada " + (alvos.length === 1 ? "na página " + alvos[0] : "em " + plural(alvos.length, "página")) : "sem assinatura posta");
  if (assina.doc.ja_assinado) partes.push(plural(assina.doc.assinaturas, "assinatura") + " já no arquivo");
  return partes.join(" · ");
}

function larguraDaFolhaDeAssinar() {
  const mesa = document.querySelector('[data-fl-tipo="assinar"] .fl-folhas');
  const base = mesa ? Math.min(800, Math.max(280, mesa.clientWidth - 64)) : 760;
  return Math.round(base * asc.escala / 100);
}

function ajustarFolhaDeAssinar() {
  const folha = $("pdf-folha");
  if (!folha) return;
  folha.style.width = larguraDaFolhaDeAssinar() + "px";
  posicionarSelo();
}

function ligarAssinarAoLado(raiz) {
  ajustarFolhaDeAssinar();
  setTimeout(() => { if (asc.ativa) ajustarFolhaDeAssinar(); }, LADO_DURA_MS + 40);
  raiz.querySelectorAll("[data-pdf-pagina]").forEach((b) => { b.onclick = () => { assina.pagina = Number(b.dataset.pdfPagina); carregarPagina(); }; });
  ligarSelo();
  carregarPagina();
  atualizarFrase();
  // O selo fica no rodape: a mesa rola ate ele quando a pagina chega.
  $("pdf-img").addEventListener("load", () => {
    setTimeout(() => {
      const selo = $("pdf-selo");
      const mesa = document.querySelector('[data-fl-tipo="assinar"] .fl-folhas');
      if (!selo || selo.hidden || !mesa) return;
      mesa.scrollTop = Math.max(0, selo.offsetTop + $("pdf-folha").offsetTop - mesa.clientHeight * 0.55);
    }, LADO_DURA_MS + 80);
  }, { once: true });
  const clique = (q, fn) => { const b = raiz.querySelector('[data-asc="' + q + '"]'); if (b) b.onclick = fn; };
  const zoom = (passo) => {
    const i = ASC_ESCALAS.indexOf(asc.escala);
    asc.escala = ASC_ESCALAS[Math.max(0, Math.min(ASC_ESCALAS.length - 1, (i < 0 ? 2 : i) + passo))];
    $("asc-escala").textContent = asc.escala + "%";
    ajustarFolhaDeAssinar();
  };
  clique("menos", () => zoom(-1));
  clique("mais", () => zoom(1));
  const acao = (q, fn) => { const b = raiz.querySelector('[data-fl="' + q + '"]'); if (b) b.onclick = () => fn(b); };
  acao("fechar", () => voltarAoContexto());
  acao("windows", async (b) => {
    b.disabled = true;
    const r = await fetch("/api/trabalhos/" + estado.trabalhoId + "/fazer", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ tipo: "abrir", campos: { nome: asc.nome } }),
    }).catch(() => null);
    b.disabled = false;
    if (!r || !r.ok) { avisoNaJanela("Não consegui abrir: " + (r ? await erroDe(r) : "sem resposta"), { icone: "error" }); return; }
    avisoNaJanela("Abri no programa padrão do Windows");
  });
  acao("editar", () => editarDocumentoDoAcervo(asc.nome, null));
  acao("mais", (b) => menuNaLinha(b, [
    { rotulo: "Abrir na tela Assinatura", acao: () => { const c = assina.doc.caminho; voltarAoContexto(); mostrarAssinar(c); } },
    { rotulo: "Ver no Acervo", acao: () => verNoAcervo(asc.nome) },
  ]));
  $("assina-agora-topo").onclick = () => {
    if (!assina.selo) { avisoCert("adicione a assinatura na página antes de assinar"); return; }
    assinarAgora();
  };
}

if (window.ResizeObserver) {
  new ResizeObserver(() => { if (asc.ativa) ajustarFolhaDeAssinar(); }).observe($("lado-ferramenta"));
}

/* ------------------------------------------------- o cartao no chat */

function cartaoDasEscolhas() {
  const d = assina.cofre || {};
  const c = (cert.dados || {}).certificado;
  const ordem = Object.keys(ROTULO_CURTO_DAS_PAGINAS);
  const escolhas = (d.escolhas || []).slice().sort((a, b) => (ordem.indexOf(a.valor) + 9) % 9 - (ordem.indexOf(b.valor) + 9) % 9);
  const chips = escolhas.map((e) =>
    '<button type="button" class="asc-chip' + (assina.paginas === e.valor ? " on" : "") + '" data-asc-pag="' + e.valor + '">' +
    (assina.paginas === e.valor ? ic("check", 14) : "") + esc(ROTULO_CURTO_DAS_PAGINAS[e.valor] || e.rotulo) + "</button>").join("");
  const posicoes = (d.posicoes || []).map((p) => '<option value="' + esc(p.valor) + '"' + (assina.posicao === p.valor ? " selected" : "") + ">" + esc(p.rotulo) + "</option>").join("");
  const certificado = !(cert.dados || {}).instalado || !c
    ? '<div class="asc-cert"><span class="asc-cert-ic">' + ic("workspace_premium", 18) + '</span><span class="duas-linhas"><b>Nenhum certificado instalado</b><small>instale o .pfx do seu e-CPF para assinar</small></span>' +
      '<button class="fantasma" data-asc-cert="1">Instalar</button></div>'
    : '<div class="asc-cert"><span class="asc-cert-ic">' + ic("verified", 18) + '</span><span class="duas-linhas"><b>' + esc(c.titular || "Certificado instalado") + "</b><small>" +
      esc(c.tipo || "A1") + (c.emissor ? " · " + esc(c.emissor) : "") + (c.valido_ate ? " · até " + esc(dataBR(c.valido_ate)) : "") + "</small></span>" +
      '<button class="fantasma" data-asc-cert="1">Trocar</button></div>';
  const marca = (chave, rotulo) => '<label class="asc-marca"><input type="checkbox" data-asc-depois="' + chave + '"' + (assina[chave] ? " checked" : "") + "><span>" + rotulo + "</span></label>";
  return '<div class="proposta asc-cartao asc-escolhas">' +
    '<section class="asc-passo"><div class="asc-cabeca"><span class="asc-num">1</span><b>Onde a assinatura entra</b><span class="vazio-flex"></span><small>arraste na página</small></div>' +
    '<div class="asc-chips">' + chips + "</div>" +
    '<input type="text" class="asc-intervalo" id="asc-intervalo" placeholder="ex. 1-3, 7, 12" value="' + esc(assina.intervalo) + '"' + (assina.paginas === "intervalo" ? "" : " hidden") + ">" +
    '<label class="asc-posicao"><span>Posição</span><span class="asc-select"><select id="asc-posicao">' + posicoes + "</select>" + ic("expand_more", 16) + "</span></label></section>" +
    '<section class="asc-passo"><div class="asc-cabeca"><span class="asc-num">2</span><b>Com qual certificado</b><span class="vazio-flex"></span>' + seloDeSituacao() + "</div>" + certificado +
    (c && !c.icp_brasil && !c.erro ? '<p class="explica">Este certificado é de fora da ICP-Brasil: a assinatura será íntegra, mas sem a validade jurídica de um e-CPF ou e-CNPJ credenciado.</p>' : "") + "</section>" +
    '<section class="asc-passo"><div class="asc-cabeca"><span class="asc-num">3</span><b>Depois de assinar</b></div>' +
    '<div class="asc-marcas">' + marca("biblioteca", "Guardar no Acervo") + marca("manter", "Manter também o arquivo original") + marca("baixar", "Baixar o PDF assinado") + "</div>" +
    '<div class="asc-senha"><span class="duas-linhas"><span>Proteger o PDF com senha</span><small>quem receber vai precisar dela para abrir</small></span>' +
    '<button type="button" class="ag-toggle' + (assina.proteger ? " on" : "") + '" id="asc-proteger" role="switch" aria-checked="' + assina.proteger + '" aria-label="Proteger o PDF com senha"><i></i></button></div>' +
    '<input type="password" class="asc-intervalo" id="asc-senha" placeholder="senha para abrir o PDF" value="' + esc(assina.senhaPdf) + '"' + (assina.proteger ? "" : " hidden") + "></section>" +
    '<div class="asc-pe"><span id="asc-resumo"></span><span class="vazio-flex"></span><button class="fantasma" data-asc-cancelar="1">Cancelar</button>' +
    '<button class="primario" id="assina-agora">' + ic("verified", 16) + "Assinar agora</button></div></div>";
}

function ligarCartaoDasEscolhas() {
  const caixa = asc.caixa;
  caixa.querySelectorAll("[data-asc-pag]").forEach((b) => {
    b.onclick = () => {
      escolherPaginas(b.dataset.ascPag);
      if (!assina.selo) assina.selo = seloNoCanto(assina.posicao);
      const alvos = paginasEscolhidas();
      if (alvos.length && alvos.indexOf(assina.pagina) < 0) { assina.pagina = alvos[alvos.length - 1]; carregarPagina(); }
      redesenharEscolhas();
      if (assina.paginas === "intervalo") $("asc-intervalo").focus();
    };
  });
  const intervalo = $("asc-intervalo");
  intervalo.oninput = () => { assina.paginas = "intervalo"; assina.intervalo = intervalo.value; if (assina.selo) mexeuNoSelo(); atualizarFrase(); };
  $("asc-posicao").onchange = (e) => {
    assina.posicao = e.target.value;
    if (assina.selo) assina.selo = seloNoCanto(assina.posicao, assina.selo.largura);
    mexeuNoSelo();
    atualizarFrase();
  };
  caixa.querySelectorAll("[data-asc-depois]").forEach((m) => { m.onchange = () => { assina[m.dataset.ascDepois] = m.checked; }; });
  const proteger = $("asc-proteger");
  proteger.onclick = () => {
    assina.proteger = !assina.proteger;
    proteger.classList.toggle("on", assina.proteger);
    proteger.setAttribute("aria-checked", String(assina.proteger));
    $("asc-senha").hidden = !assina.proteger;
    if (!assina.proteger) { assina.senhaPdf = ""; $("asc-senha").value = ""; } else $("asc-senha").focus();
    atualizarFrase();
  };
  $("asc-senha").oninput = (e) => { assina.senhaPdf = e.target.value; atualizarFrase(); };
  caixa.querySelectorAll("[data-asc-cert]").forEach((b) => { b.onclick = () => { voltarAoContexto(); marcarDestino("assinar"); mostrarCertificado(); }; });
  caixa.querySelector("[data-asc-cancelar]").onclick = () => {
    voltarAoContexto();
    caixa.innerHTML = '<p class="explica">Tudo bem — não assinei nada.</p>';
  };
  $("assina-agora").onclick = () => assinarAgora();
  atualizarAssinarNaConversa();
}

function redesenharEscolhas() {
  if (!asc.caixa || !asc.caixa.isConnected) return;
  asc.caixa.innerHTML = cartaoDasEscolhas();
  ligarCartaoDasEscolhas();
}

/* Chamado por atualizarFrase (js/17-assinar.js): o pe do cartao, o botao e
   a linha de baixo do nome, sempre com o que o PDF vai receber. */
function atualizarAssinarNaConversa() {
  if (!asc.ativa || !assina.doc) return;
  const alvos = assina.selo ? paginasEscolhidas() : [];
  const resumo = $("asc-resumo");
  if (resumo) resumo.textContent = alvos.length ? plural(alvos.length, "assinatura") + " · " + rotuloDasPaginas(alvos) : "nenhuma assinatura posta";
  const falta = oQueFalta();
  const botao = $("assina-agora");
  if (botao) { botao.disabled = Boolean(falta); botao.title = falta ? falta.titulo : ""; }
  const linha = $("asc-linha");
  if (linha) linha.textContent = linhaDoAssinar();
  if (asc.caixa) asc.caixa.querySelectorAll("[data-asc-pag]").forEach((b) => b.classList.toggle("on", b.dataset.ascPag === assina.paginas));
}

/* Depois de assinar (ou de o pedido ir para Aprovacoes): o cartao vira o
   resultado, a conversa registra, e a coluna volta ao contexto. */
async function assinadoNaConversa(f) {
  const caixa = asc.caixa;
  const nome = asc.nome;
  asc.ativa = false;
  const aguardando = Boolean(f.aguardando_aprovacao);
  try {
    const r = await fetch("/api/trabalhos/" + estado.trabalhoId + "/fazer", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ tipo: "assinatura", campos: { nome: nome, destino: f.destino || "", codigo: f.codigo || "",
        titular: f.titular || "", aguardando: aguardando } }),
    });
    const feito = r.ok ? await r.json() : null;
    if (feito && feito.resumo) notaDeFeitoNaConversa(feito.resumo + ".");
  } catch (err) { /* a assinatura ja foi feita; a nota e so o registro */ }
  if (caixa && caixa.isConnected) {
    caixa.innerHTML = aguardando
      ? '<div class="proposta asc-cartao asc-fim"><div class="asc-linha">' + ic("schedule", 18) + "<b>Falta só o seu sim em Aprovações</b></div>" +
        '<p class="explica">Nada foi assinado ainda: assinar tem efeito jurídico, e os Limites da IA mandam passar por Aprovações. Depois do sim, o assinado fica no Acervo.</p>' +
        '<div class="linha-form"><button class="primario" data-asc-aprovar="1">Abrir Aprovações</button></div></div>'
      : '<div class="proposta asc-cartao asc-fim"><div class="asc-linha">' + ic("check_circle", 18) + "<b>Assinado</b>" +
        (f.codigo ? '<span class="fl-mono">código ' + esc(f.codigo) + "</span>" : "") + "</div>" +
        '<p class="explica">' + esc(nomeDe(f.destino)) + " · com o certificado de " + esc(f.titular || "") + " · " +
        (f.paginas && f.paginas.length > 1 ? f.paginas.length + " páginas seladas" : "1 página selada") + (f.protegido ? " · protegido por senha" : "") + ". O original continua onde estava.</p>" +
        (f.icp_brasil === false ? '<p class="explica">Sem validade jurídica de ICP-Brasil: o certificado usado não é credenciado.</p>' : "") +
        '<div class="linha-form"><button data-asc-conferir="1">Conferir a assinatura</button><button data-asc-baixar="1">Baixar o PDF</button></div></div>';
    const aprovar = caixa.querySelector("[data-asc-aprovar]");
    if (aprovar) aprovar.onclick = () => {
      if (f.pedido && typeof aprov !== "undefined") aprov.aberto = f.pedido.id;
      marcarDestino("aprovacoes");
      mostrarAprovacoes();
    };
    const conferir = caixa.querySelector("[data-asc-conferir]");
    if (conferir) conferir.onclick = () => abrirVerificacao(f.destino, nomeDe(f.destino));
    const baixar = caixa.querySelector("[data-asc-baixar]");
    if (baixar) baixar.onclick = () => baixarArquivo(f.destino);
  }
  if (!aguardando && assina.baixar && f.destino) baixarArquivo(f.destino);
  voltarAoContexto();
  contarPendencias();
}
