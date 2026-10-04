/* ----------------------------------------------------------- anexar */

/* ANEXAR abre um pop-up com duas visoes, como a alternancia da lista de
   conversas: ACERVO, o padrao - os documentos que o programa ja tem, com
   busca, para marcar -, e MEU COMPUTADOR - a navegacao por pastas desta
   maquina, com os arquivos que o programa sabe ler - e GOOGLE DRIVE, a mesma
   navegacao dentro da pasta do Google Drive para computador (o escopo do app
   no Google so ve o que ele criou; a pasta ve o Drive inteiro). Do acervo, o marcado
   entra direto em foco; do computador, o servidor copia o arquivo para o
   acervo, le e poe em foco. O seletor do Windows continua a um clique, e
   arrastar arquivos para a conversa continua valendo. */
const anx = { visao: "acervo", acervo: new Set(), computador: new Map(), caminho: "", termo: "", docs: null, verbo: "Anexar", drive: null, caminhoDrive: "" };

/* `opcoes` deixa outra tela usar o mesmo pop-up: título, contexto, o verbo do
   botão e `aoAnexar(nomes)`, o que fazer com os documentos (já no Acervo).
   Sem isso, é o anexar da conversa: os documentos entram em foco. */
async function abrirAnexar(opcoes) {
  const o = opcoes || {};
  anx.acervo = new Set();
  anx.computador = new Map();
  anx.termo = "";
  anx.docs = null;
  anx.drive = null;
  anx.caminhoDrive = "";
  if (anx.visao === "drive") anx.visao = "acervo";
  anx.verbo = o.verbo || "Anexar";
  // Quem pede os caminhos (a pasta de um serviço) copia os arquivos por
  // conta própria: o seletor do Windows, que sobe para a raiz do Acervo,
  // não aparece.
  anx.soCaminhos = Boolean(o.aoCaminhos);
  // Outra tela (Assinar) pode pedir so um tipo de arquivo, um arquivo so, e
  // o seu proprio seletor do Windows. "Ja anexado" e coisa da conversa.
  anx.filtro = o.so || null;
  anx.um = Boolean(o.um);
  anx.daConversa = !o.aoAnexar && !o.aoCaminhos;
  const escolha = dialogo({
    titulo: o.titulo || "Anexar documentos", contexto: o.contexto || "Assistente", classe: "dialogo-anexar", confirmar: anx.verbo,
    html: '<div class="anx">' +
      '<div class="anx-topo"><span class="visoes lc-visoes">' +
      '<button type="button" data-anx-visao="acervo">Acervo</button>' +
      '<button type="button" data-anx-visao="computador">Meu computador</button>' +
      '<button type="button" data-anx-visao="drive">' + marca("google-drive", 14) + "Google Drive</button></span>" +
      '<label class="lc-busca anx-busca">' + ic("search", 18) + '<input type="text" id="anx-busca" placeholder="Buscar…" autocomplete="off"></label></div>' +
      '<div class="anx-migalhas" id="anx-migalhas" hidden></div>' +
      '<div class="anx-lista" id="anx-lista"></div></div>',
    // A conta e o seletor do Windows moram no pe da janela, na linha dos
    // botoes (pacote de telas, `Anexar - Google Drive`).
    rodape: '<span class="anx-rodape"><span id="anx-conta"></span>' +
      '<button type="button" class="anx-windows" id="anx-windows">' + ic("open_in_new", 14) + "Usar o seletor do Windows</button></span>",
  });
  const veu = $("veu-dialogo");
  veu.querySelectorAll("[data-anx-visao]").forEach((b) => {
    b.onclick = () => { anx.visao = b.dataset.anxVisao; anx.termo = ""; $("anx-busca").value = ""; desenharAnexar(); };
  });
  $("anx-busca").oninput = (e) => { anx.termo = e.target.value.trim().toLowerCase(); desenharListaDoAnexar(); };
  $("anx-windows").onclick = () => { if (dialogoAberto) dialogoAberto.fechar(null); if (o.aoWindows) o.aoWindows(); else $("arquivos").click(); };
  desenharAnexar();
  const r = await escolha;
  if (!r || !r.ok) return;
  if (o.aoCaminhos) {
    const doAcervo = [...anx.acervo].map((nome) => ((anx.docs || []).find((d) => d.nome === nome) || {}).caminho).filter(Boolean);
    o.aoCaminhos(doAcervo.concat([...anx.computador.keys()]));
    return;
  }
  const nomes = await anexarEscolhidos();
  if (o.aoAnexar) { o.aoAnexar(nomes); return; }
  if (nomes.length) definirEscopo([...new Set(estado.escopo.concat(nomes))]);
  $("pedido").focus();
}

function contarAnexar() {
  const total = anx.acervo.size + anx.computador.size;
  const botao = document.querySelector('#veu-dialogo [data-dialogo="confirmar"]');
  if (botao) {
    botao.disabled = !total;
    botao.textContent = total && !anx.um ? anx.verbo + " " + total : anx.verbo;
  }
  const conta = $("anx-conta");
  // Fora da conversa (Assinar, a pasta de um servico) nada e "anexado".
  const feito = anx.daConversa ? " para anexar" : (total === 1 ? " escolhido" : " escolhidos");
  if (conta) conta.textContent = total ? (anx.um ? "1 escolhido" : plural(total, "documento") + feito) : "Nenhum documento escolhido";
}

async function desenharAnexar() {
  const veu = $("veu-dialogo");
  if (!veu) return;
  veu.querySelectorAll("[data-anx-visao]").forEach((b) => b.classList.toggle("ativa", b.dataset.anxVisao === anx.visao));
  $("anx-busca").placeholder = anx.visao === "acervo" ? "Buscar no acervo…" : "Buscar nesta pasta…";
  $("anx-windows").hidden = anx.visao !== "computador" || anx.soCaminhos;
  $("anx-lista").innerHTML = '<p class="anx-vazio">abrindo…</p>';
  if (anx.visao === "acervo") {
    $("anx-migalhas").hidden = true;
    if (!anx.docs) {
      try { anx.docs = (await (await fetch("/api/biblioteca?ordem=modificacao")).json()).documentos || []; }
      catch (err) { anx.docs = []; }
    }
  } else if (anx.visao === "drive") {
    // A pasta do Drive: descoberta uma vez, depois navega como o computador.
    if (anx.drive === null) {
      try { anx.drive = (await (await fetch("/api/pastas")).json()).drive || []; }
      catch (err) { anx.drive = []; }
    }
    if (!anx.caminhoDrive && anx.drive.length) anx.caminhoDrive = anx.drive[0];
    if (anx.drive.length) {
      try { anx.pasta = await (await fetch("/api/pastas?arquivos=1&caminho=" + encodeURIComponent(anx.caminhoDrive))).json(); }
      catch (err) { anx.pasta = { erro: "não consegui abrir: " + err, pastas: [], arquivos: [], migalhas: [] }; }
    }
  } else {
    try { anx.pasta = await (await fetch("/api/pastas?arquivos=1&caminho=" + encodeURIComponent(anx.caminho))).json(); }
    catch (err) { anx.pasta = { erro: "não consegui abrir: " + err, atalhos: [], unidades: [], pastas: [], arquivos: [], migalhas: [] }; }
  }
  desenharListaDoAnexar();
}

function desenharListaDoAnexar() {
  const lista = $("anx-lista");
  if (!lista) return;
  const casa = (nome) => !anx.termo || nome.toLowerCase().includes(anx.termo);
  const serve = (nome) => !anx.filtro || anx.filtro.test(nome);
  let html = "";
  if (anx.visao === "acervo") {
    const docs = (anx.docs || []).filter((d) => casa(d.nome) && serve(d.nome));
    html = docs.map((d) => {
      const ja = anx.daConversa && estado.escopo.includes(d.nome);
      const marcado = ja || anx.acervo.has(d.nome);
      const classe = "anx-linha" + (marcado ? " escolhida" : "") + (ja ? " ja" : "");
      return '<div class="' + classe + '" data-anx-doc="' + esc(d.nome) + '">' +
        '<span class="marcar' + (marcado ? " on" : "") + '">' + ic("check", 12) + "</span>" + glifo(d.nome) +
        '<span class="duas-linhas"><b class="corta">' + esc(d.nome) + '</b><small class="corta">' + esc(d.pasta_curta || "") + "</small></span>" +
        (ja ? '<span class="anx-ja">já anexado</span>' : '<span class="anx-quando">' + esc(d.modificado || "") + "</span>") + "</div>";
    }).join("") || '<p class="anx-vazio">' + (anx.termo ? "Nenhum documento com esse nome no acervo." : "O acervo ainda está vazio — anexe pelo Meu computador.") + "</p>";
  } else if (anx.visao === "drive" && !(anx.drive || []).length) {
    $("anx-migalhas").hidden = true;
    html = semDriveHtml();
  } else {
    const d = anx.pasta || {};
    const migalhas = $("anx-migalhas");
    migalhas.hidden = false;
    const noDrive = anx.visao === "drive";
    const raizDrive = (anx.caminhoDrive && anx.drive || []).find((r) => anx.caminhoDrive.toLowerCase().startsWith(r.toLowerCase())) || "";
    const trilha = noDrive
      ? (d.migalhas || []).filter((m) => m.caminho.length > raizDrive.length && m.caminho.toLowerCase().startsWith(raizDrive.toLowerCase()))
      : (d.migalhas || []);
    migalhas.innerHTML = (noDrive
      ? '<button type="button" data-anx-ir="' + esc(raizDrive) + '">' + marca("google-drive", 13) + " Google Drive</button>"
      : '<button type="button" data-anx-ir="">Este computador</button>') +
      trilha.map((m) => '<span class="lc-sep">›</span><button type="button" data-anx-ir="' + esc(m.caminho) + '">' + esc(m.nome) + "</button>").join("");
    const pasta = (p, icone) => '<div class="anx-linha anx-pasta" data-anx-ir="' + esc(p.caminho) + '">' +
      (p.tipo === "drive" ? marca("google-drive", 17) : ic(icone, 17)) +
      '<span class="duas-linhas"><b class="corta">' + esc(p.nome) + "</b></span>" +
      (p.caminho && icone !== "folder" ? "" : "") + ic("chevron_right", 16) + "</div>";
    if ((d.atalhos || []).length) html += '<div class="nav-grupo">Começar por</div>' + d.atalhos.filter((a) => casa(a.nome)).map((a) => pasta(a, "folder")).join("");
    if ((d.unidades || []).length) html += '<div class="nav-grupo">Unidades</div>' + d.unidades.filter((u) => casa(u.nome)).map((u) => pasta(u, "desktop_windows")).join("");
    html += (d.pastas || []).filter((p) => casa(p.nome)).map((p) => pasta(p, "folder")).join("");
    html += (d.arquivos || []).filter((a) => casa(a.nome) && serve(a.nome)).map((a) => {
      const marcado = anx.computador.has(a.caminho);
      const classe = "anx-linha" + (marcado ? " escolhida" : "");
      return '<div class="' + classe + '" data-anx-arq="' + esc(a.caminho) + '" data-nome="' + esc(a.nome) + '">' +
        '<span class="marcar' + (marcado ? " on" : "") + '">' + ic("check", 12) + "</span>" + glifo(a.nome) +
        '<span class="duas-linhas"><b class="corta">' + esc(a.nome) + "</b></span>" +
        '<span class="anx-quando">' + esc(dataCurta(a.modificado)) + "</span></div>";
    }).join("");
    if (d.erro) html += '<p class="anx-vazio">' + esc(d.erro) + "</p>";
    else if (!html) html = '<p class="anx-vazio">' + (anx.termo ? "Nada com esse nome nesta pasta." : "Nenhum documento que eu saiba ler nesta pasta (PDF, Word, texto).") + "</p>";
    migalhas.querySelectorAll("[data-anx-ir]").forEach((b) => { b.onclick = () => { irNoAnexar(b.dataset.anxIr); }; });
  }
  lista.innerHTML = html;
  lista.querySelectorAll("[data-anx-doc]").forEach((l) => {
    l.onclick = () => {
      const nome = l.dataset.anxDoc;
      if (anx.daConversa && estado.escopo.includes(nome)) return;
      if (anx.acervo.has(nome)) anx.acervo.delete(nome);
      else { if (anx.um) { anx.acervo.clear(); anx.computador.clear(); } anx.acervo.add(nome); }
      desenharListaDoAnexar();
    };
  });
  lista.querySelectorAll(".anx-pasta[data-anx-ir]").forEach((l) => {
    l.onclick = () => { irNoAnexar(l.dataset.anxIr); };
  });
  lista.querySelectorAll("[data-anx-arq]").forEach((l) => {
    l.onclick = () => {
      if (anx.computador.has(l.dataset.anxArq)) anx.computador.delete(l.dataset.anxArq);
      else { if (anx.um) { anx.acervo.clear(); anx.computador.clear(); } anx.computador.set(l.dataset.anxArq, l.dataset.nome); }
      desenharListaDoAnexar();
    };
  });
  contarAnexar();
}

/* Sem o Google Drive para computador: o que fazer para o Drive aparecer. O
   mesmo texto no anexar e no escolher pasta (29-verificar.js). */
/* No desenho do pacote de telas (`Anexar - Google Drive`): a marca num
   quadrado, o titulo em serifa, a frase, e os dois caminhos lado a lado -
   instalar (o recomendado) ou trazer pela internet, sem instalar nada. */
function semDriveHtml() {
  return '<div class="anx-sem-drive"><span class="anx-drive-marca">' + marca("google-drive", 24) + "</span>" +
    "<h3>O Google Drive para computador<br>não está nesta máquina.</h3>" +
    "<p>Com ele instalado, o Drive vira uma pasta do Windows e aparece aqui, inteiro, para escolher — sem dar ao PAULUS nenhuma permissão a mais na sua conta Google.</p>" +
    '<div class="anx-caminhos">' +
    '<div class="anx-caminho"><span class="anx-caminho-rotulo">Instalar <span class="etiqueta ok">recomendado</span></span>' +
    "<p>Baixe em <b>google.com/drive/download</b>, entre com a sua conta e abra esta janela de novo.</p>" +
    '<button type="button" class="anx-caminho-botao" data-anx-drive-baixar="1">Abrir página de download' + ic("open_in_new", 14) + "</button></div>" +
    '<div class="anx-caminho"><span class="anx-caminho-rotulo">Sem instalar nada</span>' +
    "<p>Traga pastas do Drive pela internet. Elas viram uma cópia no Acervo e aparecem aqui.</p>" +
    '<button type="button" class="anx-trilha" data-anx-drive-acervo="1" title="Abrir o Acervo para incluir uma pasta do Drive"><b>Acervo</b>' + ic("chevron_right", 14) +
    "<b>Incluir pasta</b>" + ic("chevron_right", 14) + "<b>Google Drive</b></button></div></div></div>";
}

/* Os dois botoes do quadro acima, onde quer que ele apareca. */
document.addEventListener("click", (e) => {
  const baixar = e.target.closest && e.target.closest("[data-anx-drive-baixar]");
  if (baixar) { window.open("https://www.google.com/drive/download/", "_blank"); return; }
  const acervo = e.target.closest && e.target.closest("[data-anx-drive-acervo]");
  if (acervo) {
    if (dialogoAberto) dialogoAberto.fechar(null);
    marcarDestino("biblioteca");
    mostrarBiblioteca();
  }
});

/* Entrar numa pasta: no computador ou no Drive, cada visao guarda onde estava. */
function irNoAnexar(caminho) {
  if (anx.visao === "drive") anx.caminhoDrive = caminho;
  else anx.caminho = caminho;
  anx.termo = "";
  $("anx-busca").value = "";
  desenharAnexar();
}

async function anexarEscolhidos() {
  const doAcervo = [...anx.acervo];
  const caminhos = [...anx.computador.keys()];
  let lidos = [];
  if (caminhos.length) {
    avisoNaJanela("Lendo " + plural(caminhos.length, "arquivo") + "…", { icone: "sync", girar: true, dura: 0 });
    try {
      // Acima de 50 MB, pergunta e manda de novo so o confirmado (js/37).
      // Nome repetido com outro conteudo: pergunta (Renomear / Substituir);
      // fechar a pergunta nao traz nada.
      const res = await enviarComConfirmacao(caminhos, async (quais, autorizados) => {
        const r = await comNomesDecididos((decisoes) => fetch("/api/anexar/caminhos", {
          method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ caminhos: quais, autorizados: autorizados, decisoes: decisoes }),
        }));
        return r ? r.json() : { salvos: [], recusados: [], pedem_confirmacao: [] };
      }, "salvos");
      lidos = res.salvos || [];
      const feito = anx.daConversa ? (lidos.length === 1 ? " anexado" : " anexados") : (lidos.length === 1 ? " trazido para o Acervo" : " trazidos para o Acervo");
      let texto = lidos.length ? plural(lidos.length, "documento") + feito : "Nenhum arquivo foi trazido.";
      if ((res.recusados || []).length) {
        texto += " Não consegui abrir: " + res.recusados.map((x) => x.nome + " (" + x.motivo + ")").join(", ") + ".";
      }
      avisoNaJanela(texto, (res.recusados || []).length ? { tom: "erro", dura: 12000 } : { icone: "task_alt" });
      estado.contratos = res.contratos;
      carregarStatus();
      await carregarAbertos();
    } catch (err) {
      avisoNaJanela("Não consegui anexar: " + String(err), { tom: "erro", dura: 12000 });
    }
  } else if (doAcervo.length && anx.daConversa) {
    avisoCert(plural(doAcervo.length, "documento") + (doAcervo.length === 1 ? " anexado" : " anexados"), { tom: "ok" });
  }
  return doAcervo.concat(lidos);
}

/* "Perguntar ao PAULUS", do botao direito no Explorer (src/desktop.py): o
   arquivo entra numa conversa nova, anexado, como pelo "Meu computador". */
async function perguntarSobreArquivo(caminho) {
  if (!caminho) return;
  // Travado (a conta Google deste servidor, js/45-vinculo.js): o arquivo
  // espera ate alguem entrar - a pagina recarrega ao destravar e o retoma.
  if (document.getElementById("trava")) {
    try { sessionStorage.setItem("paulus.perguntar", caminho); } catch (err) { /* sem memoria: o clique se perde */ }
    return;
  }
  marcarDestino("conversa");
  $("nova").click();
  anx.acervo = new Set();
  anx.computador = new Map([[caminho, true]]);
  anx.daConversa = true;
  const nomes = await anexarEscolhidos();
  if (nomes.length) definirEscopo(nomes);
  $("pedido").focus();
}

$("anexar").onclick = () => abrirAnexar();
$("arquivos").onchange = (e) => {
  const lista = Array.from(e.target.files);
  e.target.value = "";
  if (lista.length) subirArquivos(lista);
};

const fluxo = $("fluxo");
["dragenter", "dragover"].forEach((ev) => fluxo.addEventListener(ev, (e) => {
  e.preventDefault();
  fluxo.classList.add("arrastando");
}));
["dragleave", "drop"].forEach((ev) => fluxo.addEventListener(ev, (e) => {
  e.preventDefault();
  if (ev === "dragleave" && fluxo.contains(e.relatedTarget)) return;
  fluxo.classList.remove("arrastando");
}));
fluxo.addEventListener("drop", (e) => {
  const lista = Array.from(e.dataTransfer.files || []);
  if (lista.length) subirArquivos(lista);
});

async function subirArquivos(escolhidos) {
  // Acima de 50 MB pergunta ANTES de subir (js/37-arquivo-grande.js).
  const envio = await prepararEnvio(escolhidos);
  const lista = envio.lista;
  if (!lista.length) {
    avisoNaJanela("Nenhum arquivo foi aberto. " + envio.fora.map((x) => x.nome + " (" + x.motivo + ")").join(", ") + ".", { tom: "erro", dura: 12000 });
    return;
  }
  // Nome repetido com conteudo diferente: pergunta (comNomesDecididos) e
  // manda de novo com a decisao; fechar a pergunta nao grava nada.
  const enviar = (decisoes) => {
    const dados = new FormData();
    lista.forEach((a) => dados.append("arquivos", a));
    dados.append("autorizados", JSON.stringify(envio.autorizados));
    dados.append("decisoes", JSON.stringify(decisoes));
    return fetch("/api/upload", { method: "POST", body: dados });
  };

  avisoNaJanela("Lendo " + plural(lista.length, "arquivo") + "…", { icone: "sync", girar: true, dura: 0 });

  try {
    const r = await comNomesDecididos(enviar);
    if (!r) { avisoNaJanela("Nada foi aberto: o arquivo de mesmo nome ficou como estava.", { icone: "info" }); return; }
    const res = await r.json();
    res.recusados = (res.recusados || []).concat(envio.fora);

    let texto = res.salvos.length
      ? plural(res.salvos.length, "documento") +
        (res.salvos.length === 1 ? " aberto" : " abertos") + ". Agora são " + res.contratos + " no total."
      : "Nenhum documento novo foi aberto.";
    if (res.recusados.length) {
      texto += " Não consegui abrir: " +
        res.recusados.map((x) => x.nome + " (" + x.motivo + ")").join(", ") + ".";
    }
    avisoNaJanela(texto, res.recusados.length
      ? { tom: "erro", dura: 12000 }
      : { icone: res.salvos.length ? "task_alt" : "info" });
    estado.contratos = res.contratos;
    carregarStatus();
    await carregarAbertos();
    /* Anexar é dizer do que se quer falar. Sem isto, quem arrastava dois PDFs
       e perguntava sobre eles fazia o programa reler o acervo inteiro — 55 mil
       caracteres e um minuto — como se nada tivesse sido anexado. */
    if (res.salvos.length) definirEscopo(estado.escopo.concat(res.salvos));
  } catch (err) {
    avisoNaJanela("Não consegui abrir os arquivos: " + String(err), { tom: "erro", dura: 12000 });
  }
}

/* ------------------------------------------------------------ buscar */

/* BUSCAR sem nada escrito nao pode ser um clique que nao faz nada - era o
   que parecia quebrado. Vazio, ele liga o modo de busca: a pilula acende, o
   campo pede a palavra e ganha o foco, e Enter busca em vez de perguntar ao
   assistente. Clicar de novo ou Esc desliga. */
function modoDeBusca(ligar) {
  const campo = $("pedido");
  estado.modoBusca = Boolean(ligar);
  $("buscar").classList.toggle("ativa", estado.modoBusca);
  if (estado.modoBusca) {
    if (!campo.dataset.placeholderAntes) campo.dataset.placeholderAntes = campo.placeholder;
    campo.placeholder = "Qual palavra procurar nos documentos?";
    campo.focus();
  } else if (campo.dataset.placeholderAntes) {
    campo.placeholder = campo.dataset.placeholderAntes;
    delete campo.dataset.placeholderAntes;
  }
}

$("buscar").onclick = async () => {
  const termo = $("pedido").value.trim();
  if (estado.ocupado) return;
  if (!termo) { modoDeBusca(!estado.modoBusca); return; }
  modoDeBusca(false);
  $("pedido").value = "";
  $("pedido").style.height = "auto";

  const centro = $("centro");
  const caixaNoInicio = medirInicio();
  if (!estado.trabalhoId) centro.innerHTML = "";
  centro.insertAdjacentHTML("beforeend", bolhaPessoa(termo));
  atualizarPostura();
  animarInicioParaConversa(caixaNoInicio);

  const bloco = document.createElement("div");
  bloco.className = "resposta";
  centro.appendChild(bloco);
  rolar();

  try {
    const r = await fetch("/api/buscar-agora", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ termo: termo }),
    });
    const d = await r.json();

    if (!d.resultados.length) {
      bloco.innerHTML = "<div>Não achei “" + esc(termo) + "” nos " + plural(d.documentos, "documento") + " abertos.</div>";
    } else {
      const nomes = new Set(d.resultados.map((x) => x.documento));
      bloco.innerHTML = "<div>" + plural(d.resultados.length, "trecho") + " com “" + esc(termo) + "” em " + plural(nomes.size, "documento") + ", sem passar pelo assistente.</div>" +
        d.resultados.map((x) =>
          '<div class="trecho"><div class="origem">' + esc(x.documento) + " · trecho " + x.trecho +
          "</div><pre>" + esc(x.texto) + "</pre></div>"
        ).join("");
    }
  } catch (err) {
    bloco.innerHTML = "<div>Não consegui buscar: " + esc(String(err)) + "</div>";
  }
  rolar();
};

/* ------------------------------------------------------------ desenho */

function desenharTrabalho() {
  const t = estado.trabalho;
  $("conversa-titulo").textContent = t.titulo;
  atualizarBotaoEnviar();
  entrarNaConversa();

  let html = "";
  let pergunta = "";
  let fontes = [], perguntaDasFontes = "";
  propostasGuardadas.length = 0;
  // Quem perguntou so aparece quando mais de uma pessoa perguntou aqui.
  const quemPerguntou = new Set(t.mensagens.filter((m) => m.autor === "pessoa").map((m) => m.quem || ""));
  const varias = quemPerguntou.size > 1;
  t.mensagens.forEach((m, i) => {
    if (m.autor === "pessoa") {
      pergunta = m.texto;
      html += bolhaPessoa(m.texto, varias ? m.quem : "");
    } else {
      html += blocoResposta(m, pergunta, i === t.mensagens.length - 1, i);
      if (m.fontes && m.fontes.length) { fontes = m.fontes; perguntaDasFontes = pergunta; }
    }
  });
  if (t.etapas.length && t.estado !== "concluido") html += cartaoPlano(t.etapas, t.etapa_atual, t.estado === "executando" || estado.ocupado);
  if (t.aprovacao) html += cartaoAprovacao(t.aprovacao);

  $("centro").innerHTML = html || exemplos();
  ligarExemplos();
  ligarResposta($("centro"));
  $("centro").querySelectorAll("[data-proposta-guardada]").forEach((caixa) => {
    ligarProposta(caixa, propostasGuardadas[Number(caixa.dataset.propostaGuardada)]);
  });
  ligarAprovacaoNaConversa($("centro"));
  const botaoRetomar = $("centro").querySelector("[data-retomar]");
  if (botaoRetomar) botaoRetomar.onclick = retomarTrabalho;
  desenharProgresso(t.etapas || []);
  // C3: o painel descreve uma resposta (a ultima com fontes, ou a clicada).
  if (painelNovo()) selecionarResposta(respostaPadrao(t));
  else desenharTrechos(fontes, perguntaDasFontes, null);
  desenharAtividade(t.atividade);
  atualizarPostura();
  rolar();
  vigiarTrabalhoEmCurso(t);
  // F1: as perguntas desta conversa que esperam a vez (js/58-fila.js).
  if (typeof desenharPendentes === "function") desenharPendentes();
  // A gravacao que anda nesta conversa volta para o fio e para a coluna.
  if (typeof montarGravacaoNaConversa === "function") montarGravacaoNaConversa();
}

/* Trabalho em curso que não é desta página (continuou enquanto a pessoa
   estava fora): com a execução (C1), a tela se reinscreve nela e mostra o
   texto que já saiu, ao vivo; sem ela, a conversa se redesenha sozinha
   quando ele termina. */
let vigiaDoTrabalho = null;
function vigiarTrabalhoEmCurso(t) {
  clearTimeout(vigiaDoTrabalho);
  if (t.estado !== "executando" || estado.ocupado || dupla.ocupada) return;
  fetch("/api/trabalhos/" + t.id + "/execucao").then((r) => (r.ok ? r.json() : null)).then((d) => {
    const e = d && d.execucao;
    if (e && e.estado === "rodando" && estado.trabalhoId === t.id && !estado.ocupado) acompanharExecucao(t, e);
    else vigiarPorConsulta(t);
  }).catch(() => vigiarPorConsulta(t));
}

function vigiarPorConsulta(t) {
  clearTimeout(vigiaDoTrabalho);
  vigiaDoTrabalho = setTimeout(async () => {
    if (estado.trabalhoId !== t.id) return;
    const novo = await fetch("/api/trabalhos/" + t.id).then((r) => (r.ok ? r.json() : null));
    if (!novo || estado.trabalhoId !== t.id) return;
    if (novo.estado === "executando") { vigiarPorConsulta(novo); return; }
    estado.trabalho = novo;
    desenharTrabalho();
  }, 3000);
}

function bolhaPessoa(texto, quem) {
  return (quem ? '<div class="bolha-quem">' + esc(quem) + "</div>" : "") + '<div class="bolha-pessoa">' + esc(texto) + "</div>";
}

/* Os cartões que continuam valendo quando a conversa é reaberta: abrir e
   mostrar um documento (só leitura, podem ser usados de novo) e o "onde eu
   procuro?" que ainda espera resposta. Proposta de gravar alguma coisa não
   volta: refazer o cartão de uma agenda já anotada convidaria a anotar duas. */
const propostasGuardadas = [];

function cartaoGuardado(m, ultima) {
  const p = m.proposta || {};
  // N14: o que o agente fez sozinho volta com o "Desfazer" (o próprio botão diz se já foi desfeito).
  if (!(p.tipo === "abrir" || p.tipo === "exibir" || p.tipo === "programa" || p.tipo === "sozinho" || (p.tipo === "escopo" && ultima) ||
        p.tipo === "entrevista" || p.tipo === "levar_ao_editor" || p.tipo === "preparo" || p.tipo === "clausula" ||
        p.tipo === "editor_criado" || (p.tipo === "mudar_documento" && ultima) ||
        (p.tipo === "assinar" && ultima) || (p.tipo === "email" && ultima) || (p.tipo === "ficha" && ultima) || (p.tipo === "lancamento" && ultima) || ((p.tipo === "financeiro" || p.tipo === "relatorio") && ultima) || p.tipo === "config" ||
        (p.tipo === "consulta_cadastro" && (p.modo === "achado" || ultima)))) return "";
  propostasGuardadas.push(p);
  return '<div class="proposta-caixa" data-proposta-guardada="' + (propostasGuardadas.length - 1) + '">' +
    cartaoProposta(p) + "</div>";
}

/* O que o programa fez num clique (mostrei, abri no Windows, abri para
   editar) vem logo depois de outra fala dele, e nao de uma pergunta: e nota,
   e nao resposta (pacote de telas, `Conversa`). */
function ehNotaDeFeito(m, indice) {
  const msgs = (estado.trabalho && estado.trabalho.mensagens) || [];
  const antes = indice ? msgs[indice - 1] : null;
  return Boolean(m.feito && m.feito.tipo && !(m.fontes || []).length && !(m.proposta || {}).tipo && antes && antes.autor === "paulus");
}

function blocoResposta(m, pergunta, ultima, indice) {
  const classe = "resposta" + (indice !== undefined && ehNotaDeFeito(m, indice) ? " nota-feito" : "");
  let html = '<div class="' + classe + '"' + (indice !== undefined ? ' data-msg="' + indice + '"' : "") + ">";
  if (m.cobertura && ((m.cobertura.ignorados && m.cobertura.ignorados.length) || m.cobertura.ignorados_n)) {
    html += avisoCobertura(m.cobertura);
  }
  if (m.interrompida) html += etiquetaDeParada();
  if (m.cobertura && m.cobertura.truncou) html += etiquetaDeCorte();
  if (m.inferencia) html += etiquetaDeLeitura();
  html += '<div class="texto">' + textoComCitacoes(m.texto, m.fontes, pergunta) + "</div>";
  if (m.fontes && m.fontes.length) html += blocoFontes(m.fontes, m.cobertura);
  // N7: os temas e as súmulas ligados aos artigos citados - antes da assinatura, como ao vivo.
  if (m.cobertura && m.cobertura.relacionados && typeof blocoRelacionados === "function") html += blocoRelacionados(m.cobertura.relacionados);
  const citados = m.fontes && m.fontes.length ? new Set(m.fontes.map((f) => f.documento)).size : 0;
  const p = m.proposta || {};
  if (p.tipo === "programa") html += linhaAssinatura(0, 0, pergunta || "", p.por_modelo ? "" : "sem modelo");
  else if (p.tipo === "consulta_cadastro") html += linhaAssinatura(0, 0, pergunta || "", "sem modelo");
  else if (m.segundos || (m.cobertura && m.cobertura.como)) {
    html += linhaAssinatura(m.segundos || 0, citados, pergunta || "", "", (m.cobertura || {}).como, m.fontes);
  }
  html += cartaoGuardado(m, ultima);
  if (m.cobertura && m.cobertura.detalhes) html += detalhesGuardados(m.cobertura.detalhes);
  return html + "</div>";
}

/* O que veio do resumo guardado nao e trecho de documento: e conclusao do
   assistente sobre ele. A resposta tem de dizer isso antes de ser lida - uma
   frase que parece citacao e nao e vale menos que nada. */
/* A resposta que a pessoa parou no meio: o texto e o que o modelo tinha
   escrito ate ali, e quem le precisa saber que nao e a resposta inteira. */
/* A resposta com as marcas [T1], [T2]... (I8, src/citacoes.py): cada marca
   vira um botão com o número do trecho, que abre o trecho na página do
   documento — o mesmo "ver no documento" do painel. "[sem fonte]" vira o
   rótulo da frase que não aponta para trecho nenhum. Sem marcas, o texto de
   sempre. */
const CITACOES = [];

/* A origem de cada marca, na resposta em camadas da Biblioteca (M4,
   src/biblioteca/camadas.py): um rótulo curto e uma cor por origem - a lei
   não se confunde com a opinião de um autor. */
const ORIGEM_CIT = { lei: "lei", sumula: "súm.", doutrina: "dout.", comunidade: "com.", casa: "casa", material: "mat.", documento: "doc." };
const ORIGEM_DICA = { lei: "texto da lei", sumula: "súmula", doutrina: "doutrina: o que o autor sustenta",
  comunidade: "compartilhado por outro advogado, não revisado por este escritório", casa: "regra da casa",
  material: "material de consulta", documento: "documento do Acervo" };

/* "Lei · CDC, art. 18", "Doutrina · Brandão…": de onde veio cada fonte no painel. */
function prefixoDaFonte(f) {
  const nomes = { lei: "Lei · ", sumula: "Súmulas · ", doutrina: "Doutrina · ", comunidade: "Comunidade · ", casa: "Regra da casa · " };
  if (f && nomes[f.origem]) return nomes[f.origem];
  return f && f.material ? "Material · " : "";
}

/* M7 da Biblioteca: a linha "Não tenho material de <área> na biblioteca"
   ganha o botão que leva à Biblioteca, para acrescentar material. */
function comAvisoDeArea(html) {
  return html.replace(/(Não tenho material de [^<\n]{2,40} na biblioteca; esta resposta usa só os documentos\.)/,
    '$1 <button class="bib-acrescentar" data-bib-acrescentar="1">acrescentar material</button>');
}

document.addEventListener("click", (e) => {
  const b = e.target.closest && e.target.closest("[data-bib-acrescentar]");
  if (!b) return;
  marcarDestino("config");
  mostrarConfig("aprendizado");
});

function textoComCitacoes(texto, fontes, pergunta) {
  const bruto = String(texto || "");
  if (!/\[T\d{1,3}\]|\[sem fonte\]/.test(bruto)) return comAvisoDeArea(esc(bruto));
  const k = CITACOES.push({ fontes: fontes || [], pergunta: pergunta || "" }) - 1;
  return comAvisoDeArea(esc(bruto))
    .replace(/\[T(\d{1,3})\]/g, (_, n) => {
      const f = (fontes || [])[Number(n) - 1];
      const origem = f && f.origem && ORIGEM_CIT[f.origem] ? f.origem : "";
      const dica = (f ? f.documento + (f.pagina ? ", p. " + f.pagina : "") : "trecho " + n) + (origem ? " — " + ORIGEM_DICA[origem] : "");
      return '<button class="cit-tn' + (origem ? " cit-" + origem : "") + '" data-cit-resp="' + k + '" data-tn="' + n + '" title="' + esc(dica) + '">' +
        (origem ? '<span class="cit-origem">' + esc(ORIGEM_CIT[origem]) + "</span>" : "") + n + "</button>";
    })
    .replace(/\s?\[sem fonte\]/g, ' <span class="sem-fonte" title="Esta frase não aponta para nenhum trecho lido">sem fonte</span>');
}

document.addEventListener("click", (e) => {
  const b = e.target.closest && e.target.closest(".cit-tn");
  if (!b) return;
  const reg = CITACOES[Number(b.dataset.citResp)];
  const f = reg && reg.fontes[Number(b.dataset.tn) - 1];
  if (!f || f.material) return;
  // T3: o trecho abre no documento, na coluna da direita.
  verTrechoAoLado(f);
});

function etiquetaDeParada() {
  return '<div class="etiqueta">' + ic("pause", 14) + "resposta parada no meio</div>";
}

/* O texto mandado ao modelo passou da janela dele, e o Ollama descartou o
   começo calado (src/inferencia.py). Quem lê precisa saber que a resposta
   não fala pelo texto inteiro. */
function etiquetaDeCorte() {
  return '<div class="etiqueta atencao">' + ic("info", 14) +
    "o texto não coube inteiro nesta leitura: o começo ficou de fora</div>";
}

function etiquetaDeLeitura() {
  return '<div class="etiqueta">' + ic("auto_awesome", 14) +
    "leitura do assistente, não trecho do documento</div>";
}

function avisoCobertura(c) {
  if (pensando() || c.ignorados_n) {
    // C2: a contagem; a lista, quando veio (ao vivo), fica recolhida. A
    // resposta guardada so tem a contagem.
    const n = c.ignorados_n || (c.ignorados || []).length;
    const lista = (c.ignorados || []).length
      ? ' <details class="cobertura-lista"><summary>ver lista</summary>' + esc(c.ignorados.join(", ")) + "</details>" : "";
    return '<div class="aviso-cobertura"><strong>Li ' + c.consultados.length + " de " + c.total_contratos +
      " documentos.</strong> " + plural(n, "documento") + " sem nada sobre isso — a resposta não fala por eles." + lista + "</div>";
  }
  return '<div class="aviso-cobertura"><strong>Li ' + c.consultados.length + " de " +
    c.total_contratos + " documentos.</strong> Sem trecho sobre isso em: " +
    esc(c.ignorados.join(", ")) + ". A resposta não fala por esses.</div>";
}

/* C2 (`conversa.pensando`). */
function pensando() {
  return Boolean((window.PAULUS_CONVERSA || {}).pensando);
}

/* A etapa em que a resposta esta: a que executa, ou a ultima concluida. A
   mesma conta no cartao e no painel. */
function etapaAtual(etapas) {
  const lista = etapas || [];
  const i = lista.findIndex((e) => e.estado === "executando");
  if (i >= 0) return i + 1;
  return lista.filter((e) => e.estado === "concluido").length || (lista.length ? 1 : 0);
}

/* O que acontece mora no cartao de trabalho (pacote de telas); a resposta
   nasce vazia, e a linha de estado so guarda o texto para a barra. */
function linhaDeEstadoInicial() {
  return "";
}

function mudarLinhaDeEstado(resposta, texto) {
  // C3: a barra acima do campo repete o que esta acontecendo, com o Parar.
  if (texto) estado.linhaViva = texto;
  if (painelNovo()) desenharBarra();
  const el = resposta && resposta.querySelector(".linha-estado");
  if (!el) return;
  if (!texto) { el.remove(); return; }
  el.querySelector("span").textContent = texto;
}

/* O "Tentar de novo" do cartao de erro: a mesma pergunta, na mesma conversa. */
function tentarDeNovo(pedido, conversaId) {
  if (estado.ocupado || estado.trabalhoId !== conversaId || !pedido) return;
  enviar({ texto: pedido, retomar: true });
}

/* O "ver detalhes" de uma resposta guardada: as linhas do registro da
   execucao, guardadas com ela (src/detalhes.py). */
function detalhesGuardados(linhas) {
  if (!linhas || !linhas.length) return "";
  return '<details class="detalhes-resposta"><summary>ver detalhes</summary><div class="bastidor-linhas">' +
    linhas.map((l) => '<div class="bastidor-linha ' + esc(l.classe || "") + '"><span class="bastidor-quando">' +
      String(l.s).replace(".", ",") + " s</span><span>" + esc(l.texto) + "</span></div>").join("") + "</div></details>";
}

/* No desenho os trechos moram na coluna da direita. Os documentos citados
   viram etiquetas na linha de baixo da resposta (linhaAssinatura); aqui fica
   so a caixa onde o visor se desenha. */
function blocoFontes() {
  return '<div class="visor-caixa"></div>';
}

/* `quem` troca o nome do modelo quando a resposta não passou por ele: a
   camada do programa responde do banco e do mapa das telas, e assinar
   "llama3.2:3b" embaixo seria dizer que o modelo escreveu. */
/* Como a resposta foi feita, dito em linguagem simples (I9): pelos fatos já
   conferidos, sem o modelo; lendo os documentos inteiros; ou lendo alguns
   trechos. Sem essa informação (resposta antiga), a linha de sempre. */
function fraseDoComo(c, segundos) {
  if (!c || !c.caminho) return "";
  const em = ", em " + segundosBR(segundos);
  if (c.caminho === "nivel0") return (c.molde ? "respondi pelos fatos já conferidos, sem o modelo" : "respondi pelos fatos já conferidos") + em;
  if (c.caminho === "tudo") return "li " + (c.documentos === 1 ? "o documento inteiro" : plural(c.documentos, "documento") + " por inteiro") + em;
  if (c.caminho === "busca" || c.caminho === "foco") {
    return "li " + plural(c.trechos || 0, "trecho") + (c.documentos ? " de " + plural(c.documentos, "documento") : "") + em;
  }
  return "";
}

/* A LINHA DE BAIXO DA RESPOSTA (pacote de telas, `Conversa`): uma etiqueta
   por documento citado (o tipo, o nome e quantos trechos dele), o tempo e o
   modelo em letra miuda e, a direita, os quatro icones - gostei, nao
   gostei, copiar e refazer. O caminho por inteiro ("li o documento
   inteiro") mora em "Como respondi", na coluna da direita. */
function etiquetasDosCitados(fontes) {
  const conta = new Map();
  (fontes || []).forEach((f) => { if (f && f.documento && !f.material) conta.set(f.documento, (conta.get(f.documento) || 0) + 1); });
  return [...conta].map(([nome, n]) => '<button class="ass-doc" data-ver-trechos="1" data-doc="' + esc(nome) + '" title="' + esc(nome) + '">' +
    glifo(nome) + '<span class="corta">' + esc(nome) + "</span><small>" + n + "</small></button>").join("");
}

function linhaAssinatura(segundos, citados, pergunta, quem, como, fontes) {
  // D4: escrita no aparelho de quem perguntou assina com o modelo de la.
  if (como && como.escrita && como.escrita.onde === "aparelho" && como.escrita.modelo) quem = como.escrita.modelo;
  // N15: a resposta escrita pela nuvem assina com o modelo dela.
  if (como && como.nuvem && como.nuvem.onde === "nuvem") quem = como.nuvem.modelo + " (" + como.nuvem.provedor + ", nuvem)";
  // A2: o agente que respondeu, e a versao dele.
  if (como && como.agente) quem = (quem || estado.modelo || "assistente local") + " · " + como.agente + (como.agente_versao ? " v" + como.agente_versao : "");
  // Pelos fatos ja conferidos, sem o modelo: a linha nao diz que ele escreveu.
  if (como && como.caminho === "nivel0" && como.molde) quem = "sem modelo";
  // A profundidade escolhida (js/92-entrevista.js): o nível na frente do modelo.
  if (como && como.profundidade && como.profundidade.nome) quem = como.profundidade.nome + " · " + (quem || estado.modelo || "assistente local");
  const meta = [segundos ? segundosBR(segundos) : "", quem || estado.modelo || "assistente local"].filter(Boolean).join(" · ");
  // O aviso da nuvem (worker/ia.js): ex., na primeira semana do Plus, o Opus libera no 8º dia.
  const aviso = como && como.nuvem && como.nuvem.aviso ? '<p class="ass-aviso">' + ic("schedule", 14) + "<span>" + esc(como.nuvem.aviso) + ".</span></p>" : "";
  return aviso + '<div class="assinatura">' + etiquetasDosCitados(fontes) +
    '<span class="ass-meta">' + esc(meta) + "</span>" +
    '<span class="vazio-flex"></span>' +
    // L1: gostei / nao gostei (js/63-aprendizado.js), so nas respostas de uma pergunta.
    (pergunta && typeof botoesDeAvaliacao === "function" ? botoesDeAvaliacao() : "") +
    '<button class="ass-acao" data-copiar="1" title="Copiar" aria-label="Copiar">' + ic("content_copy", 16) + "</button>" +
    (pergunta ? '<button class="ass-acao" data-refazer="' + esc(pergunta) + '" title="Refazer" aria-label="Refazer">' + ic("refresh", 16) + "</button>" : "") +
    "</div>";
}

function ligarResposta(caixa) {
  caixa.querySelectorAll("[data-copiar]").forEach((b) => {
    b.onclick = () => {
      const texto = b.closest(".resposta").querySelector(".texto");
      if (!texto || !navigator.clipboard) return;
      navigator.clipboard.writeText(texto.textContent).then(() => {
        const icone = b.querySelector(".ic");
        if (icone) icone.textContent = "check";
        b.title = "Copiado";
        setTimeout(() => { if (icone) icone.textContent = "content_copy"; b.title = "Copiar"; }, 1800);
      });
    };
  });
  caixa.querySelectorAll("[data-refazer]").forEach((b) => {
    b.onclick = () => { $("pedido").value = b.dataset.refazer; enviar(); };
  });
  caixa.querySelectorAll("[data-ver-trechos]").forEach((b) => {
    b.onclick = () => {
      // C3: "ver fontes" numa resposta mostra as fontes DAQUELA resposta.
      const r = b.closest(".resposta");
      if (painelNovo() && r && r.dataset.msg !== undefined) { selecionarResposta(Number(r.dataset.msg), true); return; }
      try { localStorage.setItem("paulus.lateral", "1"); } catch (err) { /* sem memoria */ }
      mostrarLateral(true);
      alternarRamo($("lat-trechos-cabeca"), true);
      $("lat-trechos").scrollIntoView({ behavior: "smooth", block: "start" });
    };
  });
}

/* Os trechos citados, no painel da direita, numerados. Clicar num trecho
   marca-o; "ver no documento" abre a pagina do PDF na conversa, com o trecho
   destacado - e o visor de sempre, so mudou de onde e chamado. */
function desenharTrechos(fontes, pergunta, ondeVisor, numeros) {
  const bloco = $("lat-trechos");
  const lista = $("lat-trechos-lista");
  if (!fontes || !fontes.length) { bloco.hidden = true; lista.innerHTML = ""; return; }
  // `numeros`: o [Tn] de cada fonte, quando o painel mostra so as citadas (C3).
  const numero = (i) => (numeros && numeros[i]) || i + 1;

  bloco.hidden = false;
  $("lat-trechos-conta").textContent = fontes.length;
  /* Um cartao por trecho (pacote de telas, `Conversa`): o documento, a
     pagina e tres linhas do texto. Uma leitura de 80 trechos nao empurra o
     resto da coluna para fora: os cinco primeiros a vista, o resto num
     clique. A numeracao continua a da citacao, que e a que a resposta usa. */
  const VISIVEIS = 5;
  const cartao = (f, i) => {
    // O indice guarda o trecho com a pagina na frente ("[pagina 2] ..."): a
    // pagina vai para o canto do cartao, e o texto fica limpo.
    const bruto = String(f.texto || "").replace(/\s+/g, " ").trim();
    const marcaPagina = bruto.match(/^\[p[aá]gina (\d+)\]\s*/i);
    const pagina = f.pagina || (marcaPagina ? marcaPagina[1] : "");
    const onde = pagina ? "p. " + pagina : (f.onde || "trecho " + (f.trecho || numero(i)));
    // Material de consulta nao esta no Acervo: o cartao so mostra o texto.
    return '<button class="lat-trecho" data-ver-cit="' + i + '"' + (f.material ? " disabled" : "") +
      ' title="' + esc((f.material ? "" : "Abrir o documento neste trecho · ") + "[T" + numero(i) + "]") + '">' +
      '<span class="lat-trecho-cabeca">' + glifo(f.documento) + "<b>" + esc(prefixoDaFonte(f) + f.documento) + "</b>" +
      "<small>" + esc(onde) + "</small></span>" +
      "<p>" + esc(marcaPagina ? bruto.slice(marcaPagina[0].length) : bruto) + "</p></button>";
  };
  lista.innerHTML = fontes.slice(0, VISIVEIS).map(cartao).join("") +
    (fontes.length > VISIVEIS ? '<button class="lat-mais" data-lat-mais="1">mais ' + plural(fontes.length - VISIVEIS, "trecho") + "</button>" : "");
  lista.hidden = false;
  $("lat-trechos-cabeca").setAttribute("aria-expanded", "true");
  const ligar = () => lista.querySelectorAll("[data-ver-cit]").forEach((b) => {
    b.onclick = (e) => {
      e.stopPropagation();
      const f = fontes[Number(b.dataset.verCit)];
      if (!f || f.material) return;
      verTrechoNoDocumento(f);
    };
  });
  ligar();
  const mais = lista.querySelector("[data-lat-mais]");
  if (mais) mais.onclick = (e) => {
    e.stopPropagation();
    mais.remove();
    lista.insertAdjacentHTML("beforeend", fontes.slice(VISIVEIS).map((f, k) => cartao(f, k + VISIVEIS)).join(""));
    ligar();
  };
}

/* O trecho no documento: o documento abre na coluna da direita, como
   ferramenta, com o trecho marcado (js/80-visor-ao-lado.js, T3). */
function verTrechoNoDocumento(f) {
  verTrechoAoLado(f);
}

/* Abre ou fecha um ramo da arvore (o botao e o que vem logo depois dele).
   Fechar leva junto tudo o que estava aberto abaixo: reabrir mostra o ramo
   compacto de novo, e nao a arvore inteira do jeito que ficou. */
function alternarRamo(no, abrir) {
  const filhos = no.nextElementSibling;
  if (!filhos) return;
  const vai = abrir === undefined ? filhos.hidden : abrir;
  if (vai === !filhos.hidden) return;
  no.setAttribute("aria-expanded", String(vai));
  if (!vai) {
    filhos.querySelectorAll('.arv-no[aria-expanded="true"]').forEach((n) => {
      n.setAttribute("aria-expanded", "false");
      n.nextElementSibling.hidden = true;
    });
  }
  abrirComoGaveta(filhos, vai);
}

/* A gaveta de sempre: cresce ate a altura dela enquanto aparece (curva expo)
   e encolhe mais rapido ao fechar. A mesma da lista de conversas. */
function abrirComoGaveta(el, abrir) {
  if (el.gaveta) { el.gaveta.cancel(); el.gaveta = null; el.style.overflow = ""; }
  if (!animacoesLigadas()) { el.hidden = !abrir; return; }
  el.style.overflow = "hidden";
  if (abrir) {
    el.hidden = false;
    el.gaveta = el.animate([{ height: "0px", opacity: 0 }, { height: el.scrollHeight + "px", opacity: 1 }],
      { duration: 360, easing: CURVA_ENTRA });
    el.gaveta.onfinish = () => { el.gaveta = null; el.style.overflow = ""; };
  } else {
    el.gaveta = el.animate([{ height: el.offsetHeight + "px", opacity: 1 }, { height: "0px", opacity: 0 }],
      { duration: 240, easing: "cubic-bezier(.55,0,.45,1)" });
    el.gaveta.onfinish = () => { el.gaveta = null; el.hidden = true; el.style.overflow = ""; };
  }
}


/* O progresso do plano, no painel: a lista de etapas do sistema (.lat-etapa). */
/* No pacote de telas o Progresso volta para a coluna da direita, no alto:
   cada etapa com o nome e, embaixo, o que ela achou ou fez ("2 documentos,
   1 trecho"); a que anda gira, a que espera diz "aguardando". */
function desenharProgresso(etapas) {
  const bloco = $("lat-progresso");
  if (!etapas || !etapas.length) { bloco.hidden = true; return; }
  bloco.hidden = false;
  // A mesma conta do cartao de trabalho ("etapa 2 de 3" e "2 de 3 etapas").
  $("lat-progresso-conta").textContent = etapaAtual(etapas) + " de " + plural(etapas.length, "etapa");
  const classe = { concluido: "feita", executando: "andando", na_fila: "fila", falhou: "falhou", pausado: "fila" };
  $("lat-etapas").innerHTML = etapas.map((e) => {
    const detalhe = e.estado === "na_fila" ? "aguardando"
      : e.estado === "pausado" ? "parada"
        : (e.detalhe || "") + (e.total ? (e.detalhe ? " · " : "") + e.feitos + " de " + e.total : "");
    // O anel que gira e o circulo vazio sao desenhados (o pacote de telas):
    // os glifos da fonte de icones pesavam mais que o check ao lado.
    const marca = e.estado === "concluido" ? ic("check_circle", 16)
      : e.estado === "falhou" ? ic("error", 16)
        : e.estado === "executando" ? '<span class="marca-etapa"><i class="giro"></i></span>'
          : '<span class="marca-etapa"><i class="circulo-vazio"></i></span>';
    return '<div class="lat-etapa ' + (classe[e.estado] || "fila") + '">' + marca +
      '<span class="lat-etapa-nome"><b>' + esc(e.titulo) + "</b>" + (detalhe ? "<small>" + esc(detalhe) + "</small>" : "") + "</span></div>";
  }).join("");
}

/* A pergunta que da para retomar: a ultima da conversa, quando ela ficou sem
   resposta ou com a resposta parada no meio. */
function perguntaParaRetomar() {
  const t = estado.trabalho;
  if (!t || !["pausado", "falhou"].includes(t.estado)) return "";
  const msgs = t.mensagens || [];
  const fim = msgs[msgs.length - 1];
  if (!fim || (fim.autor === "paulus" && !fim.interrompida)) return "";
  const pessoa = [...msgs].reverse().find((m) => m.autor === "pessoa");
  return pessoa ? pessoa.texto : "";
}

/* RETOMAR: refaz a ultima pergunta onde ela parou - o programa fechou no
   meio, a pessoa apertou parar, ou deu errado. A resposta interrompida sai
   da tela e do historico; a pergunta nao se repete. */
async function retomarTrabalho() {
  const t = estado.trabalho;
  const pergunta = perguntaParaRetomar();
  if (!t || !pergunta || estado.ocupado) return;
  const fim = t.mensagens[t.mensagens.length - 1];
  if (fim && fim.autor === "paulus" && fim.interrompida) t.mensagens.pop();
  t.etapas = [];
  t.estado = "executando";
  desenharTrabalho();
  enviar({ texto: pergunta, retomar: true });
}

/* `andando`: a conversa reaberta com trabalho em curso (um pedido ao documento
   que continuou enquanto a pessoa estava em outra tela) está trabalhando,
   mesmo sem nada andando nesta página. */
/* O CARTÃO DE TRABALHO (pacote de telas, `Conversa - Carregando`): um
   cartão só, com o título ("Trabalhando · etapa 2 de 3"), o tempo ("15 s de
   ~32 s" quando esta máquina já mediu leituras deste tamanho) e o Parar; as
   faixas das etapas, como no Acontecendo agora; e, embaixo, o registro do
   que está acontecendo (o bastidor, js/13-editor-na-conversa.js), aberto,
   com a última linha viva. O topo se redesenha a cada etapa; o registro fica. */
function topoDoPlano(etapas, atual, andando) {
  const total = etapas.length;
  const rodando = andando !== undefined ? Boolean(andando) : estado.ocupado;
  const retomar = !rodando && perguntaParaRetomar()
    ? '<button class="primario com-icone" data-retomar="1">' + ic("play_arrow", 16) + "Retomar</button>" : "";
  const parar = rodando ? '<button class="agr-parar" data-parar-resposta="1" title="Parar a resposta"><i></i>Parar</button>' : "";
  return '<div class="cabeca trab-cabeca"><b class="quem">' + (rodando ? "Trabalhando" : "Parado") +
    (total ? " · etapa " + atual + " de " + total : "") + "</b>" +
    '<span class="agr-tempo" id="cronometro"></span>' + parar + retomar + "</div>" + faixasDasEtapas(etapas, null);
}

function cartaoPlano(etapas, atual, andando) {
  return '<div class="trab-cartao"><div class="trab-topo">' + topoDoPlano(etapas, atual, andando) + '</div><div class="trab-log"></div></div>';
}

/* Desenha (ou redesenha so o topo de) o cartao de trabalho em `plano`, e
   devolve onde o registro mora. */
function desenharPlano(plano, etapas, atual, andando) {
  let topo = plano.querySelector(".trab-topo");
  if (!topo) {
    plano.innerHTML = cartaoPlano(etapas, atual, andando);
    topo = plano.querySelector(".trab-topo");
  } else {
    topo.innerHTML = topoDoPlano(etapas, atual, andando);
  }
  const parar = topo.querySelector("[data-parar-resposta]");
  if (parar) parar.onclick = () => pararResposta();
  atualizarTempoDoPlano();
  return plano.querySelector(".trab-log");
}

/* O tempo do cartao e a faixa da etapa que le: o que passou desde a
   pergunta e, com a previsao desta maquina, ate onde deve ir. */
function atualizarTempoDoPlano(desde) {
  const base = desde || bastidor.desde || Date.now();
  const passados = (Date.now() - base) / 1000;
  let texto = Math.round(passados) + " s";
  let pct = 0;
  const p = bastidor.previsao;
  if (bastidor.fase === "lendo" && p && p.sabe && bastidor.lendoDesde) {
    const total = Math.round((bastidor.lendoDesde - base) / 1000 + p.segundos);
    if (total > passados) texto += " de ~" + total + " s";
    pct = Math.min(95, ((Date.now() - bastidor.lendoDesde) / 1000 / p.segundos) * 100);
  }
  const c = $("cronometro");
  if (c) c.textContent = texto;
  const faixa = document.querySelector(".trab-topo .agr-etapa.andando .agr-faixa");
  if (faixa && pct) {
    faixa.classList.remove("sem-medida");
    if (faixa.firstElementChild) faixa.firstElementChild.style.width = pct.toFixed(1) + "%";
  }
}

/* Terminou: o registro vai para dentro da resposta, recolhido em "ver
   detalhes" (o mesmo da resposta guardada), e o cartao sai. */
function guardarLogNaResposta(resposta) {
  const linhas = bastidor.linhasEl;
  if (!linhas || !linhas.children.length || !resposta || resposta.querySelector(".detalhes-resposta")) return;
  resposta.insertAdjacentHTML("beforeend", '<details class="detalhes-resposta"><summary>ver detalhes</summary><div class="bastidor-linhas">' +
    linhas.innerHTML + "</div></details>");
}

function linhaEtapa(e) {
  const rotulos = { concluido: "concluído", executando: "", na_fila: "na fila", falhou: "não deu", pausado: "parada" };
  const icone = { concluido: "check_circle", executando: "radio_button_partial", na_fila: "radio_button_unchecked", falhou: "error", pausado: "pause" };
  const direita = e.total
    ? '<span class="estado">' + e.feitos + " / " + e.total + "</span>"
    : '<span class="estado">' + (rotulos[e.estado] || "") + "</span>";
  const barra = e.estado === "executando" && e.total
    ? '<div class="progresso"><i style="width:' + Math.round((e.feitos / e.total) * 100) + '%"></i></div>'
    : "";
  return '<div class="etapa ' + e.estado + '"><span class="ic ic-18 marcador">' +
    (icone[e.estado] || "radio_button_unchecked") + "</span>" +
    '<span class="texto">' + esc(e.titulo) + (e.detalhe ? " · " + esc(e.detalhe) : "") + "</span>" +
    direita + "</div>" + barra;
}

function cartaoAprovacao(a) {
  return '<div class="aprovacao"><div class="cabeca"><i class="ponto-acc"></i><span class="nome">Esperando você</span></div>' +
    "<p>" + esc(a.pergunta) + "</p>" +
    (a.detalhe ? '<p class="detalhe">' + esc(a.detalhe) + "</p>" : "") +
    '<div class="acoes"><button>Revisar</button>' +
    '<button class="primario">Aprovar</button></div></div>';
}

/* Aprovar e decidir na fila: os dois botoes levam para la. */
function ligarAprovacaoNaConversa(caixa) {
  caixa.querySelectorAll(".aprovacao button").forEach((b) => {
    b.onclick = () => { marcarDestino("aprovacoes"); mostrarAprovacoes(); };
  });
}

function desenharAtividade(itens) {
  // C3: a barra acima do campo diz o que vai acontecer com a proxima pergunta.
  if (painelNovo()) { desenharBarra(); return; }
  const caixa = $("registro");
  if (!itens || !itens.length) {
    caixa.hidden = true;
    return;
  }

  caixa.hidden = false;
  $("registro-agora").textContent = itens[0].texto;
  $("atividade").innerHTML = itens.slice(0, 6).map((a) =>
    '<div class="atividade-linha"><span class="txt">' + esc(a.texto) +
    '<span class="num">' + quando(a.em) + "</span></span></div>"
  ).join("");
}

$("registro-cabeca").onclick = () => {
  // Como barra da proxima pergunta ("A próxima pergunta lê só…"), ela so
  // informa: nao abre nem fecha nada (pedido de 02/10).
  if ($("registro").classList.contains("barra-escopo")) return;
  const aberto = $("registro").classList.toggle("aberto");
  $("atividade").hidden = !aberto;
};

function quando(iso) {
  const seg = Math.max(0, Math.round((Date.now() - new Date(iso).getTime()) / 1000));
  if (seg < 5) return "agora";
  if (seg < 60) return "há " + seg + " s";
  if (seg < 3600) return "há " + Math.floor(seg / 60) + " min";
  return "há " + Math.floor(seg / 3600) + " h";
}

function rolar() {
  $("fluxo").scrollTop = $("fluxo").scrollHeight;
  atualizarIrAoFim();
}

/* A pessoa subiu para reler: a resposta que esta chegando nao a arrasta de
   volta para baixo, e o botao de ir ao fim aparece. Perto do fim (120 px) e
   o mesmo que estar no fim - uma linha nova nao conta como ter subido. */
const FOLGA_DO_FIM = 120;

function pertoDoFim() {
  const f = $("fluxo");
  return f.scrollHeight - f.scrollTop - f.clientHeight < FOLGA_DO_FIM;
}

function atualizarIrAoFim() {
  const longe = !$("conversa-col").classList.contains("vazia") && !pertoDoFim();
  $("ir-ao-fim").classList.toggle("visivel", longe);
}

$("fluxo").addEventListener("scroll", atualizarIrAoFim, { passive: true });
$("ir-ao-fim").onclick = () => {
  const f = $("fluxo");
  f.scrollTo({ top: f.scrollHeight, behavior: animacoesLigadas() ? "smooth" : "auto" });
};

/* ------------------------------------------------------------ ditar */
/*
   O microfone da caixa de pedido. Usa o modelo de voz que ja mora nesta
   maquina (o mesmo das Gravacoes): o audio vai em pedacos de 2 s para uma
   sessao ao vivo no servidor local, que devolve o texto a cada pausa na
   fala. Nada sai do computador - foi a escolha entre isto e o ditado do
   Windows, que em portugues manda o audio para a Microsoft. A captura e a
   conversao do audio sao as das Gravacoes (11-gravacoes.js).

   Pacote de telas de 01/10/2026 (`Conversa - Ditando`): numa conversa, o
   cartao do ditado TOMA O LUGAR da caixa de pedido enquanto o microfone
   esta aberto - o ponto vermelho, o tempo, a onda da voz e o texto ouvido
   ate aqui, que chega a cada pausa na fala. O texto entra na caixa ao
   concluir: "Concluir e editar" poe na caixa para corrigir, "Concluir e
   enviar" poe e manda. Cancelar descarta o que foi ditado. Estados:

     ouvindo     microfone aberto
     pausado     microfone aberto, mas nada e ouvido
     pendente    a pessoa saiu do Assistente: o microfone fechou, o texto
                 ja esta no campo e a sessao fica; o cartao oferece
                 continuar, concluir ou descartar
     finalizando transcrevendo o que sobrou
*/
const ditado = {
  estado: "", sessao: "", fluxo: null, captura: null, amostras: [],
  relogio: 0, enviando: false, recebidos: 0, inicio: 0, acumulado: 0, quadro: 0,
  // O campo antes do ditado (o texto ditado vai depois dele, ao concluir) e
  // o que ja foi ouvido nesta sessao.
  campoAntes: "", campoDepois: "", texto: "",
};

const dsAberto = () => ditado.estado === "ouvindo" || ditado.estado === "pausado";

/* O tempo que o microfone ficou ouvindo, sem contar pausas nem o pendente. */
function tempoDoDitado() {
  const ms = ditado.acumulado + (ditado.estado === "ouvindo" ? performance.now() - ditado.inicio : 0);
  const s = Math.floor(ms / 1000);
  return String(Math.floor(s / 60)).padStart(2, "0") + ":" + String(s % 60).padStart(2, "0");
}

function marcarTempo(parando) {
  if (ditado.estado === "ouvindo" && parando) ditado.acumulado += performance.now() - ditado.inicio;
  if (!parando) ditado.inicio = performance.now();
}

/* O foco volta para o campo de pedido - a nao ser que a pessoa esteja
   escrevendo em outro campo (a busca da lista, um dialogo): ai o texto
   entra do mesmo jeito, mas ninguem tira o cursor de onde ela esta. */
function focarCampoDoDitado() {
  const campo = $("pedido");
  const ativo = document.activeElement;
  const escrevendoEmOutro = ativo && ativo !== campo && (ativo.tagName === "INPUT" || ativo.tagName === "TEXTAREA" || ativo.isContentEditable);
  if (escrevendoEmOutro || document.getElementById("veu-dialogo")) return;
  campo.focus();
  campo.setSelectionRange(campo.value.length, campo.value.length);
}

/* O que foi ouvido vai para o cartao (e nao ainda para a caixa): a caixa
   recebe tudo de uma vez ao concluir. */
function juntarAoDitado(trechos) {
  const novos = (trechos || []).map((x) => (x.texto || "").trim()).filter(Boolean);
  if (!novos.length) return;
  ditado.texto = (ditado.texto ? ditado.texto.replace(/\s+$/, "") + " " : "") + novos.join(" ");
  document.querySelectorAll("[data-ditado-texto]").forEach((el) => { el.innerHTML = textoDoCartaoDoDitado(); el.scrollTop = el.scrollHeight; });
}

function textoDoCartaoDoDitado() {
  const vazio = ditado.estado === "pausado" ? "em pausa — o microfone não ouve nada até continuar"
    : ditado.estado === "pendente" ? "o microfone fechou quando você saiu do Assistente"
      : "ouvindo… o texto chega a cada pausa na fala";
  return ditado.texto ? esc(ditado.texto) + (ditado.estado === "ouvindo" ? '<i class="dit-cursor"></i>' : "")
    : '<span class="dit-espera">' + esc(vazio) + "</span>";
}

/* O ditado terminou: o que foi ouvido entra na caixa, depois do que ja
   estava escrito nela. */
function levarDitadoParaCaixa() {
  const campo = $("pedido");
  if (!ditado.texto) return false;
  // Ditado começado no editor do e-mail (js/85): o texto vai para o e-mail.
  if (ditado.destino === "email" && typeof levarDitadoAoEmail === "function" && levarDitadoAoEmail(ditado.texto)) return true;
  const antes = campo.value || "";
  campo.value = (antes.trim() ? antes.replace(/\s+$/, "") + " " : "") + ditado.texto;
  campo.style.height = "auto";
  campo.style.height = Math.min(campo.scrollHeight, 150) + "px";
  ditado.campoDepois = campo.value;
  return true;
}

/* O CARTAO DO DITADO. So o aviso la embaixo nao bastava para saber se o
   microfone estava ouvindo. No inicio ele e o primeiro cartao de
   "Acontecendo agora"; numa conversa, onde essa secao nao existe, fica logo
   acima da caixa de pedido. */
function cartaoDoDitado() {
  const e = ditado.estado;
  if (!e) return "";
  const nomes = { ouvindo: "Ditando", pausado: "Ditado em pausa", pendente: "Ditado pendente", finalizando: "Transcrevendo o que sobrou…" };
  const notas = {
    ouvindo: "o texto entra na caixa ao concluir",
    pausado: "o texto entra na caixa ao concluir",
    pendente: "o texto ouvido continua aqui",
    finalizando: "o último trecho entra em alguns segundos",
  };
  const botao = (dado, icone, rotulo, classe) => '<button class="' + (classe || "dit-fantasma") + '" ' + dado + '="1">' + (icone ? ic(icone, 15) : "") + rotulo + "</button>";
  let esquerda = "", direita = "";
  if (e === "ouvindo" || e === "pausado") {
    esquerda = botao("data-ditado-cancelar", "close", "Cancelar") +
      botao("data-ditado-pausar", e === "pausado" ? "mic" : "pause", e === "pausado" ? "Continuar" : "Pausar");
    direita = botao("data-ditado-usar", "", "Concluir e editar", "dit-borda") + botao("data-ditado-enviar", "arrow_upward", "Concluir e enviar", "dit-cheio");
  } else if (e === "pendente") {
    esquerda = botao("data-ditado-cancelar", "delete", "Descartar") + botao("data-ditado-continuar", "mic", "Continuar");
    direita = botao("data-ditado-usar", "", "Concluir e editar", "dit-borda") + botao("data-ditado-enviar", "arrow_upward", "Concluir e enviar", "dit-cheio");
  }
  // Começado no editor do e-mail: o texto vai para o e-mail, e "enviar" não é daqui.
  if (ditado.destino === "email") {
    notas.ouvindo = notas.pausado = "o texto entra no e-mail ao concluir";
    if (direita) direita = botao("data-ditado-usar", "", "Pôr no e-mail", "dit-cheio");
  }
  const classe = "cartao-agora ditado-cartao " + e;
  const marca = e === "finalizando" ? '<span class="marca-etapa"><i class="giro"></i></span>' : '<i class="agr-rec' + (e === "ouvindo" ? " vivo" : "") + '"></i>';
  return '<div class="' + classe + '">' +
    '<div class="cabeca"><span class="dit-estado">' + marca + nomes[e] + "</span>" +
    '<span class="dit-nota">' + notas[e] + "</span>" +
    '<span class="ditado-tempo" data-ditado-tempo="1">' + tempoDoDitado() + "</span></div>" +
    '<canvas class="ditado-onda" data-ditado-onda="1"></canvas>' +
    '<div class="dit-texto" data-ditado-texto="1">' + textoDoCartaoDoDitado() + "</div>" +
    (esquerda || direita ? '<div class="acoes">' + esquerda + '<span class="vazio-flex"></span>' + direita + "</div>" : "") + "</div>";
}

function ligarCartaoDoDitado() {
  const ligar = (dado, fazer) => document.querySelectorAll("[" + dado + "]").forEach((b) => {
    b.onmousedown = (ev) => ev.preventDefault();   // clicar no cartao nao tira o foco do campo
    b.onclick = (ev) => { ev.stopPropagation(); fazer(); focarCampoDoDitado(); };
  });
  ligar("data-ditado-cancelar", () => cancelarDitado());
  ligar("data-ditado-pausar", () => pausarDitado(ditado.estado === "ouvindo"));
  ligar("data-ditado-continuar", () => continuarDitado());
  ligar("data-ditado-usar", () => usarDitadoNoChat());
  ligar("data-ditado-enviar", () => usarDitadoNoChat({ enviar: true }));
  document.querySelectorAll("[data-ditado-onda]").forEach((cv) => desenharOnda(cv, null));
}

function desenharCartaoDoDitado() {
  const html = cartaoDoDitado();
  const noInicio = $("conversa-col").classList.contains("vazia");
  const lista = $("agora-cartoes");
  lista.querySelectorAll(".ditado-cartao").forEach((c) => c.remove());
  if (noInicio) {
    if (html) lista.insertAdjacentHTML("afterbegin", html);
    $("agora").hidden = !lista.children.length;
  }
  const rodape = $("ditado-rodape");
  const novo = rodape.hidden && html && !noInicio;
  rodape.hidden = !html || noInicio;
  rodape.querySelector(".centro").innerHTML = html && !noInicio ? html : "";
  // Numa conversa, o cartao toma o lugar da caixa de pedido enquanto dura.
  $("conversa-col").classList.toggle("ditando", Boolean(html) && !noInicio);
  if (novo && animacoesLigadas()) entraConteudo(rodape.querySelector(".ditado-cartao"));
  $("ditar").classList.toggle("ouvindo", dsAberto());
  $("ditar").title = dsAberto() ? "Usar o ditado no chat" : (ditado.estado === "pendente" ? "Continuar o ditado" : "Ditar — o modelo de voz desta máquina escreve no campo");
  ligarCartaoDoDitado();
}

/* O equalizador: barras finas, espelhadas a partir do centro - os graves da
   voz no meio, os agudos nas pontas -, como uma onda. Le o analisador do
   proprio contexto de audio da captura; em pausa, as barras deitam. */
function desenharOnda(cv, dados, ativo) {
  // `ativo`: quem desenha diz se o som esta chegando (o tocador das
  // Gravacoes usa o mesmo desenho); sem ele, vale o estado do ditado.
  const ouvindo = ativo === undefined ? ditado.estado === "ouvindo" : ativo;
  const dpr = window.devicePixelRatio || 1;
  const w = cv.clientWidth;
  const h = cv.clientHeight;
  if (!w || !h) return;
  if (cv.width !== Math.round(w * dpr) || cv.height !== Math.round(h * dpr)) {
    cv.width = Math.round(w * dpr);
    cv.height = Math.round(h * dpr);
  }
  const g = cv.getContext("2d");
  g.setTransform(dpr, 0, 0, dpr, 0, 0);
  g.clearRect(0, 0, w, h);
  g.fillStyle = getComputedStyle(cv).color;
  const barra = 3;
  const passo = 6;
  const n = Math.max(1, Math.floor(w / passo));
  const sobra = (w - n * passo + (passo - barra)) / 2;
  const util = dados ? Math.max(1, Math.floor(dados.length * 0.5)) : 1;
  for (let i = 0; i < n; i++) {
    const pos = n > 1 ? Math.abs(i - (n - 1) / 2) / ((n - 1) / 2) : 0;
    const valor = dados && ouvindo ? dados[Math.floor(pos * (util - 1))] / 255 : 0;
    const alt = Math.max(2, valor * h * (1 - pos * 0.4));
    g.fillRect(sobra + i * passo, (h - alt) / 2, barra, alt);
  }
}

function animarDitado() {
  const captura = ditado.captura;
  if (!dsAberto() || !captura) { ditado.quadro = 0; return; }
  const dados = new Uint8Array(captura.analisador.frequencyBinCount);
  captura.analisador.getByteFrequencyData(dados);
  document.querySelectorAll("[data-ditado-onda]").forEach((cv) => desenharOnda(cv, dados));
  document.querySelectorAll("[data-ditado-tempo]").forEach((t) => { t.textContent = tempoDoDitado(); });
  ditado.quadro = requestAnimationFrame(animarDitado);
}

async function novaSessaoDeDitado() {
  const r = await fetch("/api/voz/ao-vivo", { method: "POST", headers: { "Content-Type": "application/json" }, body: "{}" }).catch(() => null);
  if (!r || !r.ok) {
    avisoCert("não consegui abrir o ditado" + (r ? ": " + (await erroDe(r)) : ""), { tom: "erro" });
    return "";
  }
  ditado.recebidos = 0;
  return (await r.json()).sessao;
}

/* Abre o microfone e a captura. Falhou, nao muda o estado do ditado. */
async function abrirCapturaDoDitado() {
  let fluxo;
  try {
    fluxo = await navigator.mediaDevices.getUserMedia({ audio: true });
  } catch (err) {
    avisoCert("não consegui usar o microfone: " + (err && err.message ? err.message : err), { tom: "erro" });
    return false;
  }
  try {
    let ctx;
    try { ctx = new AudioContext({ sampleRate: 16000 }); } catch (err) { ctx = new AudioContext(); }
    const fonte = ctx.createMediaStreamSource(fluxo);
    await ctx.audioWorklet.addModule(URL.createObjectURL(new Blob([GV_CAPTADOR], { type: "application/javascript" })));
    const no = new AudioWorkletNode(ctx, "paulus-captador");
    no.port.onmessage = (e) => { if (ditado.estado === "ouvindo") ditado.amostras.push(e.data); };
    fonte.connect(no);
    no.connect(ctx.destination);
    const analisador = ctx.createAnalyser();
    analisador.fftSize = 128;
    analisador.smoothingTimeConstant = 0.72;
    fonte.connect(analisador);
    ditado.fluxo = fluxo;
    ditado.captura = { ctx: ctx, no: no, fonte: fonte, analisador: analisador };
  } catch (err) {
    fluxo.getTracks().forEach((t) => t.stop());
    avisoCert("esta janela não deixou capturar o áudio (" + (err && err.message ? err.message : err) + ")", { tom: "erro" });
    return false;
  }
  clearInterval(ditado.relogio);
  ditado.relogio = setInterval(enviarPedacoDoDitado, 2000);
  return true;
}

function fecharCapturaDoDitado() {
  clearInterval(ditado.relogio);
  cancelAnimationFrame(ditado.quadro);
  if (ditado.captura) {
    try { ditado.captura.no.disconnect(); ditado.captura.fonte.disconnect(); ditado.captura.ctx.close(); } catch (err) { /* ja fechado */ }
    ditado.captura = null;
  }
  if (ditado.fluxo) { ditado.fluxo.getTracks().forEach((t) => t.stop()); ditado.fluxo = null; }
}

function ouvir() {
  ditado.estado = "ouvindo";
  marcarTempo(false);
  desenharCartaoDoDitado();
  cancelAnimationFrame(ditado.quadro);
  ditado.quadro = requestAnimationFrame(animarDitado);
}

async function comecarDitado() {
  let voz = null;
  try { voz = await (await fetch("/api/voz")).json(); } catch (err) { voz = null; }
  if (!voz || !voz.disponivel) {
    avisoCert("ditar precisa do modelo de voz desta máquina — baixe em Configurações › Assistente", {
      tom: "erro", acao: { rotulo: "Abrir", fazer: () => { cfg.secao = "assistente"; abrirDestino("config"); } },
    });
    return;
  }
  const sessao = await novaSessaoDeDitado();
  if (!sessao) return;
  if (!(await abrirCapturaDoDitado())) { fetch("/api/voz/ao-vivo/" + sessao, { method: "DELETE" }).catch(() => {}); return; }
  ditado.sessao = sessao;
  ditado.amostras = [];
  ditado.acumulado = 0;
  ditado.texto = "";
  ditado.campoAntes = $("pedido").value;
  ditado.campoDepois = ditado.campoAntes;
  ouvir();
}

function pausarDitado(pausar) {
  if (!dsAberto()) return;
  if (pausar) {
    marcarTempo(true);
    ditado.estado = "pausado";
    enviarPedacoDoDitado();   // o que foi ouvido antes da pausa vai logo
    desenharCartaoDoDitado();
  } else {
    ouvir();
  }
}

/* Voltar do pendente: o microfone abre de novo na mesma sessao. */
async function continuarDitado() {
  if (ditado.estado !== "pendente") return;
  if (!(await abrirCapturaDoDitado())) return;
  ouvir();
}

/* SAIR DO ASSISTENTE com o microfone aberto: ele fecha - ninguem quer o
   microfone ouvindo enquanto mexe no Financeiro -, mas o que foi ditado e a
   sessao ficam, e o cartao espera a pessoa voltar. */
function deixarDitadoPendente() {
  if (!dsAberto()) return;
  marcarTempo(true);
  fecharCapturaDoDitado();
  ditado.estado = "pendente";
  enviarPedacoDoDitado();
  desenharCartaoDoDitado();
}

async function enviarPedacoDoDitado() {
  if (!ditado.sessao || ditado.enviando || !ditado.amostras.length) return;
  const sessao = ditado.sessao;
  const partes = ditado.amostras;
  ditado.amostras = [];
  const junto = new Float32Array(partes.reduce((n, p) => n + p.length, 0));
  let i = 0;
  partes.forEach((p) => { junto.set(p, i); i += p.length; });
  const taxa = ditado.captura ? ditado.captura.ctx.sampleRate : 16000;
  ditado.enviando = true;
  try {
    const r = await fetch("/api/voz/ao-vivo/" + sessao + "/audio", {
      method: "POST", headers: { "Content-Type": "application/octet-stream" }, body: pcm16De(reamostrarGv(junto, taxa, 16000)),
    });
    if (ditado.sessao !== sessao) return;   // descartado enquanto transcrevia
    if (r.status === 404) {
      // O servidor descarta sessao parada ha 15 min (pendente esquecido):
      // abre outra e o pedaco tenta de novo. O texto do cartao nao se perde.
      ditado.sessao = await novaSessaoDeDitado();
      ditado.amostras = partes.concat(ditado.amostras);
      return;
    }
    if (!r.ok) { avisoCert("o ditado parou: " + (await erroDe(r)), { tom: "erro" }); deixarDitadoPendente(); return; }
    const d = await r.json();
    if (d.trechos && d.trechos.length) {
      ditado.recebidos += d.trechos.length;
      juntarAoDitado(d.trechos);
    }
  } catch (err) {
    if (ditado.sessao === sessao) ditado.amostras = partes.concat(ditado.amostras);
  } finally {
    ditado.enviando = false;
  }
}

function zerarDitado() {
  ditado.estado = "";
  ditado.destino = "";
  ditado.sessao = "";
  ditado.amostras = [];
  ditado.acumulado = 0;
  ditado.texto = "";
  desenharCartaoDoDitado();
}

/* Cancelar (ou Descartar, no pendente): o microfone fecha, a sessao e
   descartada sem transcrever o resto, e o que foi ditado nao entra na
   caixa - ela continua como estava. */
function cancelarDitado() {
  if (!ditado.estado) return;
  const sessao = ditado.sessao;
  fecharCapturaDoDitado();
  if (sessao) fetch("/api/voz/ao-vivo/" + sessao, { method: "DELETE" }).catch(() => {});
  zerarDitado();
  focarCampoDoDitado();
}

/* Concluir: o que ficou sem pausa ainda e transcrito e entra no campo, e a
   sessao e descartada - a fila de transcricao das Gravacoes espera enquanto
   ha sessao aberta. */
async function usarDitadoNoChat(opcoes) {
  const o = opcoes || {};
  if (!ditado.estado || ditado.estado === "finalizando") return;
  if (dsAberto()) marcarTempo(true);
  fecharCapturaDoDitado();
  ditado.estado = "finalizando";
  desenharCartaoDoDitado();
  while (ditado.enviando) await new Promise((fimEspera) => setTimeout(fimEspera, 100));
  if (ditado.amostras.length) await enviarPedacoDoDitado();
  const sessao = ditado.sessao;
  if (sessao) {
    try {
      const r = await fetch("/api/voz/ao-vivo/" + sessao + "/fim", { method: "POST" });
      if (r.ok) juntarAoDitado(((await r.json()).trechos || []).slice(ditado.recebidos));
    } catch (err) { /* o que ja foi transcrito continua valendo */ }
    fetch("/api/voz/ao-vivo/" + sessao, { method: "DELETE" }).catch(() => {});
  }
  const levou = levarDitadoParaCaixa();
  if (!levou) avisoCert("não ouvi nada para escrever");
  zerarDitado();
  focarCampoDoDitado();
  // "Concluir e enviar": a caixa ja tem o texto; manda como quem aperta Enter.
  if (o.enviar && levou) enviar();
}

$("ditar").onclick = () => {
  if (dsAberto()) return usarDitadoNoChat();
  if (ditado.estado === "pendente") return continuarDitado();
  if (!ditado.estado) return comecarDitado();
};

/* Fechar a janela com uma sessao aberta: ela e descartada, para a fila de
   transcricao nao ficar esperando por ninguem. */
window.addEventListener("pagehide", () => {
  if (ditado.sessao) navigator.sendBeacon && fetch("/api/voz/ao-vivo/" + ditado.sessao, { method: "DELETE", keepalive: true }).catch(() => {});
});

/* ------------------------------------------------------------ enviar */

/* O botao da caixa de pedido tem quatro rostos. ENVIAR e o de sempre. PARAR
   aparece na conversa cuja resposta esta sendo escrita - por esta pagina ou
   por uma sessao que ja nao existe e a deixou "trabalhando". PARANDO e o
   instante entre o clique e o servidor confirmar. ESPERANDO e fora dessa
   conversa (no inicio, em outra): uma resposta anda por vez, entao o enviar
   fica esmaecido, e interromper e pelo icone do cartao em "Acontecendo
   agora" - antes o botao virava parar ali tambem, e nao parava nada. */
const ENVIAR_ORIGINAL = $("enviar").innerHTML;

function modoDoEnviar(modo) {
  const botao = $("enviar");
  const parar = modo === "parar" || modo === "parando";
  botao.classList.toggle("parar", parar);
  botao.classList.toggle("esperando", modo === "esperando");
  botao.disabled = modo === "parando" || modo === "esperando";
  botao.title = parar ? "Parar a resposta" : (modo === "esperando" ? "Uma resposta está sendo escrita — interrompa pelo cartão em Acontecendo agora" : "Enviar");
  botao.setAttribute("aria-label", botao.title);
  botao.innerHTML = parar ? ic("stop", 18) : ENVIAR_ORIGINAL;
  if (typeof atualizarDicaPrioridade === "function") atualizarDicaPrioridade();
}

function atualizarBotaoEnviar() {
  if (estado.ocupado) modoDoEnviar(estado.trabalhoId && estado.trabalhoId === estado.respondendoId ? "parar" : "esperando");
  else modoDoEnviar(estado.trabalho && estado.trabalho.estado === "executando" ? "parar" : "enviar");
}

/* Conversa aberta "trabalhando" sem resposta andando nesta pagina: a janela
   foi recarregada no meio, ou a resposta e de antes. Ainda da para parar. */
function respondendoFora() {
  return Boolean(!estado.ocupado && estado.trabalho && estado.trabalho.estado === "executando");
}

async function pararResposta() {
  const id = estado.trabalhoId;
  if (!id) return;
  modoDoEnviar("parando");
  let d = {};
  try {
    d = await (await fetch("/api/trabalhos/" + id + "/parar", { method: "POST" })).json();
  } catch (err) { /* o servidor sumiu: cortar a leitura daqui mesmo */ }
  if (estado.ocupado) {
    /* A resposta desta pagina termina sozinha com o evento "parado", em ate
       um quarto de segundo. Se nao terminar - servidor travado -, a pagina
       corta a leitura dela e segue. */
    const controle = estado.controle;
    setTimeout(() => { if (estado.ocupado && estado.controle === controle && controle) controle.abort(); }, 5000);
    return;
  }
  /* Nada andando por aqui: a rota ja devolveu a conversa como parada. */
  if (!d.parando) {
    abrirTrabalho(id);
  } else {
    setTimeout(() => abrirTrabalho(id), 700);
  }
}


/* `opcoes.retomar` com `opcoes.texto`: refaz a ultima pergunta de uma
   conversa parada - sem nova bolha, sem mexer no que esta escrito no campo. */
async function enviar(opcoes) {
  const o = opcoes && (opcoes.texto || opcoes.prioridade) ? opcoes : {};
  // F1 (js/58-fila.js): com a fila ligada, a pergunta mandada com esta
  // conversa respondendo fica nela, na fila, e vai sozinha na vez.
  if (estado.ocupado && filaLigada() && estado.trabalhoId && estado.trabalhoId === estado.respondendoId) {
    return enfileirarNaConversa(o);
  }
  if (estado.ocupado) {
    // C3: diz por que nao foi, e oferece esperar a vez.
    const texto = (o.texto || $("pedido").value).trim();
    if (painelNovo() && texto) avisarOcupado(texto);
    return;
  }
  // Enviar com ditado aberto ou pendente: primeiro o texto ditado entra no campo.
  if (!o.retomar && !o.entrevista && ditado.estado && ditado.estado !== "finalizando") await usarDitadoNoChat();
  const pedido = (o.texto || $("pedido").value).trim();
  if (!pedido) return;

  // Com o editor aberto ao lado, pedido de mudança vai para o documento.
  if (!o.retomar && !o.entrevista && editorNaConversaAberto() && destinoDoPedido(pedido) === "documento") {
    $("pedido").value = "";
    $("pedido").style.height = "auto";
    pedirNoDocumento(pedido);
    return;
  }
  // Com o e-mail aberto na conversa e "No e-mail" (js/85-email-na-conversa.js),
  // a pergunta e sobre a mensagem.
  if (!o.retomar && !o.entrevista && typeof pedidoNoEmail === "function" && pedidoNoEmail(pedido)) {
    $("pedido").value = "";
    $("pedido").style.height = "auto";
    return;
  }
  // Com a ficha aberta na coluna (js/86-fichas-na-conversa.js), a frase que
  // traz um dado corrige o campo; a que nao traz segue para a conversa.
  if (!o.retomar && !o.entrevista && ((typeof pedidoNaFicha === "function" && await pedidoNaFicha(pedido)) ||
      (typeof pedidoNoLancamento === "function" && await pedidoNoLancamento(pedido)))) {
    $("pedido").value = "";
    $("pedido").style.height = "auto";
    return;
  }
  // Com o agente aberto ao lado (js/84-criar-agente.js), o pedido muda as instrucoes.
  if (!o.retomar && !o.entrevista && typeof agenteAoLadoAberto === "function" && agenteAoLadoAberto() && !agn.escrevendo) {
    $("pedido").value = "";
    $("pedido").style.height = "auto";
    mudarAgentePelaConversa(pedido);
    return;
  }
  // Com a planilha em edicao ao lado (js/81-planilha-ao-lado.js), idem.
  if (!o.retomar && !o.entrevista && planilhaEmEdicao() && destinoNaPlanilha(pedido) === "planilha") {
    $("pedido").value = "";
    $("pedido").style.height = "auto";
    pa.destino = "";
    atualizarDestinoDaPlanilha();
    pedirNaPlanilha(pedido);
    return;
  }

  if (!estado.trabalhoId) {
    const r = await fetch("/api/trabalhos", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ pedido: pedido }),
    });
    const t = await r.json();
    estado.trabalhoId = t.id;
    estado.trabalho = t;
    $("centro").innerHTML = "";
  }

  const caixaNoInicio = medirInicio();
  entrarNaConversa();
  estado.ocupado = true;
  estado.respondendoId = estado.trabalhoId;
  estado.controle = new AbortController();
  modoDoEnviar("parar");
  if (!o.retomar) {
    $("pedido").value = "";
    $("pedido").style.height = "auto";
    if (painelNovo()) gravarNaConversa(estado.trabalhoId, { rascunho: "", anexos: [] });
  }
  atualizarSelo(true);
  estado.linhaViva = "";
  estado.comoVivo = null;
  if (painelNovo()) desenharBarra();

  const centro = $("centro");
  if (!o.retomar) centro.insertAdjacentHTML("beforeend", bolhaPessoa(pedido));
  atualizarPostura();
  animarInicioParaConversa(caixaNoInicio);

  const minha = estado.trabalhoId;
  const plano = document.createElement("div");
  // C2: as etapas vem do servidor, no primeiro evento; a tela nao inventa as
  // dela. Sem a chave, o cartao de antes ("Entender o pedido" primeiro,
  // porque nem toda mensagem e pergunta sobre documento).
  const registro = desenharPlano(plano, pensando() ? [] :
    [{ titulo: "Entender o pedido", estado: "executando", feitos: 0, total: 0, detalhe: "" },
     { titulo: "Procurar e responder", estado: "na_fila", feitos: 0, total: 0, detalhe: "" }], 1, true);
  centro.appendChild(plano);
  if (animacoesLigadas()) entraConteudo(plano);

  // O registro do que esta acontecendo mora dentro do cartao, aberto.
  abrirBastidor(registro, { solto: true });

  const resposta = document.createElement("div");
  resposta.className = "resposta";
  resposta.innerHTML = linhaDeEstadoInicial() + '<div class="texto"></div>';
  centro.appendChild(resposta);
  const texto = resposta.querySelector(".texto");
  rolar();

  const inicio = Date.now();
  const relogio = setInterval(() => { if (estado.trabalhoId === minha) atualizarTempoDoPlano(inicio); }, 1000);

  /* Os anexos vão com esta mensagem e saem da caixa; o documento deles vira o
     foco da conversa. */
  const envio = o.apenas || o.tudo
    ? { apenas: o.apenas || [], tudo: Boolean(o.tudo), sem_anexo: false }
    : escopoDoEnvio();
  if (!o.apenas && !o.tudo && estado.escopo.length) {
    definirEscopo([]);
    definirFoco(envio.apenas);
  }

  try {
    // D4 (js/61-aparelho-tela.js): onde a resposta é escrita - o seletor, o
    // Automático ou a janela de sugestão, antes de a pergunta entrar na fila.
    const onde = typeof ondeEscrever === "function" ? await ondeEscrever(o, envio, estado.controle.signal) : {};
    const r = await fetch("/api/trabalhos/" + estado.trabalhoId + "/perguntar", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      // `apenas` e `tudo` podem vir do cartão "onde eu procuro?", que refaz
      // a pergunta com a escolha feita ali.
      body: JSON.stringify(Object.assign({ pergunta: pedido, retomar: Boolean(o.retomar), documentos: Boolean(o.documentos),
        inteiro: Boolean(o.inteiro), prioridade: Boolean(o.prioridade) }, envio,
        typeof agenteDoEnvio === "function" ? agenteDoEnvio() : {}, onde,
        // N15: a pílula "Nuvem" (js/75-nuvem.js) vale para esta pergunta só.
        typeof nuvemDoEnvio === "function" ? nuvemDoEnvio() : {},
        // A profundidade e as respostas do módulo de perguntas (js/92-entrevista.js).
        typeof profundidadeDoEnvio === "function" ? profundidadeDoEnvio() : {},
        o.entrevista ? { entrevista: o.entrevista } : {})),
      signal: estado.controle.signal,
    });
    // F1: a conversa já respondia (outra aba, outra pessoa) e a pergunta
    // ficou na fila dela (202); ou a pessoa já tem duas esperando (429) e a
    // pergunta volta para o campo, sem nada guardado.
    if (filaLigada() && (r.status === 202 || r.status === 429)) {
      await desfazerEnvioNaFila(r, pedido, [plano, resposta]);
      return;
    }
    // A fila do modelo cheia (429) diz por que; o resto, o de sempre.
    if (!r.ok) throw new Error(r.status === 429 ? await erroDe(r) : "não consegui responder");

    await lerResposta(r, { plano: plano, resposta: resposta, texto: texto, pedido: pedido, minha: minha });
  } catch (err) {
    if (err && err.name === "AbortError" && estado.saindo) {
      // Saiu da conversa (C1): a resposta segue no servidor.
    } else if (err && err.name === "AbortError") {
      plano.remove();
      if (!texto.textContent.trim()) texto.textContent = "Parei antes de escrever a resposta.";
      resposta.insertAdjacentHTML("afterbegin", etiquetaDeParada());
    } else {
      texto.textContent = "Não consegui responder: " + err;
    }
  } finally {
    const reinscrever = estado.saindo && estado.trabalhoId === minha;
    estado.saindo = false;
    estado.execucaoId = "";
    if (estado.trabalhoId === minha) fecharBastidor();
    clearInterval(relogio);
    estado.ocupado = false;
    estado.respondendoId = null;
    estado.controle = null;
    atualizarBotaoEnviar();
    atualizarSelo(false);
    carregarTrabalhos();
    if (estado.trabalhoId) {
      fetch("/api/trabalhos/" + estado.trabalhoId)
        .then((r) => r.json())
        // O botao espera o estado de verdade: o Retomar marca a conversa como
        // "executando" na tela, e sem isto ele ficava em "parar" depois do fim.
        .then((t) => {
          estado.trabalho = t; desenharAtividade(t.atividade); desenharProgresso(t.etapas || []); atualizarBotaoEnviar();
          // C3: a resposta que acabou de chegar passa a ser a do painel.
          if (painelNovo() && estado.trabalhoId === t.id) { marcarRespostasGuardadas(t); selecionarResposta(respostaPadrao(t)); }
        });
    }
    if (painelNovo()) { estado.linhaViva = ""; desenharBarra(); setTimeout(soltarEspera, 0); }
    rolar();
    $("pedido").focus();
    if (reinscrever && estado.trabalho) vigiarTrabalhoEmCurso(estado.trabalho);
  }
}

/* A leitura dos eventos de uma resposta, ao perguntar e ao voltar para uma
   conversa que ainda responde (C1). `v` tem o que a resposta desenha: o
   cartao do plano, a resposta, o texto, a pergunta e a conversa de que ela e.
   Tudo o que mexe fora da resposta (titulo, foco, painel) so vale enquanto
   essa conversa esta aberta. Devolve "saiu" quando a pessoa foi para outra. */
async function lerResposta(r, v) {
  const { plano, resposta, texto, minha } = v;
  const pedido = v.pedido;
  const aqui = () => estado.trabalhoId === minha;
  let citados = 0, saiu = false, execId = "";
  // C2: a linha de estado, no lugar em que a resposta vai aparecer.
  const linha = (txt) => mudarLinhaDeEstado(resposta, txt);
  let primeiro = true, abrirAoFim = "", assinaSemModelo = false;
  // I8: depois da conferência, o texto mostrado é o conferido, com as
  // marcas virando botões; o que chegar depois (a frase decisiva) soma nele.
  let fontesAtuais = [], revisado = false, bruto = "";

  // C5: o leitor unico de SSE (eventosSSE, 16-dialogos.js); o break de "saiu"
  // fecha a leitura.
  for await (const ev of eventosSSE(r)) {
    {
      const mt = [0, ev.tipo];
      const dados = ev.dados;
      // C1: evento de outra conversa nao mexe nesta. Com a execucao, a
      // pessoa saiu da conversa: larga a inscricao (a resposta continua
      // no servidor, e a tela se reinscreve ao voltar). Sem ela, a leitura
      // segue calada - fechar a conexao pararia a resposta.
      if (dados.execucao_id) { execId = dados.execucao_id; if (aqui()) estado.execucaoId = execId; }
      if (!aqui() || (dados.conversa_id && dados.conversa_id !== estado.trabalhoId)) {
        if (execId) { saiu = true; break; }
        continue;
      }

      if (mt[1] === "fontes") {
        /* Quando a pergunta nomeia um arquivo, a leitura para nele — e o
           bastidor diz isso, porque "li 1 de 9" sem explicação parece falha
           de cobertura quando é obediência ao que foi pedido. */
        if ((dados.apenas || []).length && aqui()) definirFoco(dados.apenas);
        if (pensando()) linha("Lendo " + plural((dados.consultados || []).length || 1, "documento") + "…");
        anotarBastidor(dados.apenas.length
          ? (dados.apenas.length === 1
              ? "a pergunta é sobre “" + dados.apenas[0] + "” · li só ele, "
              : "a pergunta é sobre " + plural(dados.apenas.length, "documento") +
                " · li só eles, ") + plural(dados.trechos.length, "trecho")
          : "procurei nos " + plural(dados.total_contratos, "documento") +
            " abertos · vou usar " + plural(dados.trechos.length, "trecho") +
            " de " + plural(dados.consultados.length, "documento"));
        if (dados.ignorados.length) {
          // C2: a contagem, nunca a lista inteira; a lista fica recolhida
          // no aviso ("ver lista").
          anotarBastidor(pensando() ? plural(dados.ignorados.length, "documento") + " sem nada sobre isso"
            : plural(dados.ignorados.length, "documento") + " sem trecho sobre isso: " + dados.ignorados.join(", "), "atencao");
          resposta.insertAdjacentHTML("afterbegin", avisoCobertura(dados));
        }
        resposta.insertAdjacentHTML("beforeend", blocoFontes(dados.trechos, dados));
        citados = new Set(dados.trechos.map((f) => f.documento)).size;
        fontesAtuais = dados.trechos || [];
        if (aqui()) desenharTrechos(dados.trechos, pedido, resposta.querySelector(".visor-caixa"));
        if (aqui()) comoAoVivo({ fontes: dados });
      } else if (mt[1] === "execucao") {
        // O id da execucao (C1): ja guardado acima.
      } else if (mt[1] === "fila") {
        /* O modelo desta máquina responde uma pergunta por vez, e alguém
           chegou antes (src/fila_modelo.py). A linha viva diz a posição;
           quando a vez chega, a fase seguinte a substitui. */
        const texto = textoDaFila(dados);
        if (bastidor.fase !== "fila") faseBastidor("fila", texto);
        else if (bastidor.vivaEl) bastidor.vivaEl.textContent = texto;
        if (pensando()) linha(texto.charAt(0).toUpperCase() + texto.slice(1));
      } else if (mt[1] === "aparelho") {
        // D4: o escritório mandou os trechos; este aparelho escreve (js/61-aparelho-tela.js).
        if (typeof escreverPacoteNoAparelho === "function") {
          escreverPacoteNoAparelho(dados, { texto: texto, linha: linha, anotar: anotarBastidor });
        }
      } else if (/^nuvem_/.test(mt[1])) {
        // N15: o pedido para ir à nuvem, o envio e onde terminou (js/75-nuvem.js).
        if (typeof eventoDaNuvem === "function") {
          eventoDaNuvem(mt[1], dados, { resposta: resposta, linha: linha, anotar: anotarBastidor, conversaId: minha });
        }
      } else if (mt[1] === "aparelho_fim") {
        if (typeof fimDoAparelho === "function") fimDoAparelho(dados, { texto: texto, linha: linha, anotar: anotarBastidor });
      } else if (mt[1] === "lendo" && dados.molde && !dados.caracteres) {
        /* Nível 0 por molde (src/inteligencia/molde.py): a resposta é o
           próprio fato conferido, montado sem o modelo. */
        anotarBastidor("respondi pelos fatos já conferidos, sem o modelo");
        if (pensando()) linha("Respondendo pelos fatos já conferidos…");
      } else if (mt[1] === "lendo") {
        anotarBastidor("mandei " + milhar(dados.caracteres) + " caracteres para o " +
          dados.modelo + ", janela de " + milhar(dados.janela) + " tokens");
        bastidor.previsao = dados.previsao;
        if (dados.previsao && dados.previsao.sabe) {
          anotarBastidor("aqui, leituras deste tamanho levaram ~" +
            dados.previsao.segundos + " s (mediana de " +
            plural(dados.previsao.medicoes, "leitura") + ")");
        } else {
          anotarBastidor("ainda não medi leituras deste modelo nesta máquina — " +
            "esta vai virar a primeira medida");
        }
        bastidor.lendoDesde = Date.now();
        faseBastidor("lendo", "lendo…");
        if (aqui()) comoAoVivo({ lendo: dados });
        if (pensando()) {
          // A estimativa vem do ritmo medido nesta maquina, e so acima de 10 s.
          const p = dados.previsao || {};
          linha("Lendo " + plural(dados.documentos || 1, "documento") + (p.sabe && p.segundos > 10 ? " · ~" + segundosCurtos(p.segundos) : "") + "…");
        }
      } else if (mt[1] === "escrevendo") {
        anotarBastidor("primeira palavra saiu · esperei " +
          segundosBR(dados.lendo_segundos) + " até aqui");
        bastidor.escreveDesde = Date.now();
        bastidor.palavras = 0;
        faseBastidor("escrevendo", "escrevendo…");
        if (pensando()) linha("Escrevendo…");
      } else if (mt[1] === "truncou") {
        anotarBastidor("o texto passou da janela de " + milhar(dados.num_ctx) +
          " tokens; o modelo leu só o final dele");
        if (!resposta.querySelector(".etiqueta.atencao")) resposta.insertAdjacentHTML("afterbegin", etiquetaDeCorte());
      } else if (mt[1] === "medida") {
        fecharBastidor();
        // Dois tempos diferentes e de proposito: o que a pessoa esperou e o
        // que o modelo gastou calculando. A diferenca e o modelo carregando.
        anotarBastidor("pronto · o modelo gastou " + segundosBR(dados.lendo_segundos) +
          " lendo " + milhar(dados.tokens_lidos) + " tokens" +
          (dados.do_cache ? " (boa parte ja estava em cache)" : "") +
          " e " + segundosBR(dados.escrevendo_segundos) + " escrevendo " +
          milhar(dados.tokens_escritos), "feito");
      } else if (mt[1] === "etapas") {
        // C2: uma conta so, a do servidor, no cartao e no painel.
        desenharPlano(plano, dados.etapas, pensando() ? etapaAtual(dados.etapas) : 2, true);
        if (aqui()) desenharProgresso(dados.etapas);
        if (pensando()) {
          const andando = dados.etapas.find((e) => e.estado === "executando");
          if (andando && /^Procurar/.test(andando.titulo)) {
            linha("Procurando " + (estado.contratos ? "em " + plural(estado.contratos, "documento") : "nos documentos") + "…");
          }
        }
      } else if (mt[1] === "revisao") {
        revisado = true;
        bruto = dados.texto || "";
        texto.innerHTML = textoComCitacoes(bruto, fontesAtuais, pedido);
        if (dados.removidas && dados.removidas.length) {
          anotarBastidor("tirei da resposta o que não está nos trechos lidos: " + dados.removidas.join("; "));
        }
      } else if (mt[1] === "refazendo") {
        anotarBastidor("a resposta citou um trecho que não existe — refazendo com menos trechos");
      } else if (mt[1] === "pensando") {
        // O trabalho em etapas (src/elaboracao.py): o que está sendo feito agora.
        if (pensando()) linha(dados.texto || "");
        anotarBastidor((dados.texto || "").replace(/…$/, "").toLowerCase());
      } else if (mt[1] === "nota") {
        anotarBastidor(dados.texto || "");
      } else if (mt[1] === "reescrevendo") {
        // A revisão pediu para refazer: o rascunho dá lugar à versão revista.
        texto.textContent = "";
        primeiro = true;
        if (pensando()) linha("Reescrevendo com as correções da revisão…");
      } else if (mt[1] === "substituir") {
        texto.textContent = dados.texto || "";
      } else if (mt[1] === "token" && revisado) {
        bruto += dados.t;
        texto.innerHTML = textoComCitacoes(bruto, fontesAtuais, pedido);
      } else if (mt[1] === "token") {
        if (primeiro) { texto.textContent = ""; primeiro = false; linha(""); }
        texto.textContent += dados.t;
        // Palavras escritas ate agora: e o numero que a janelinha mostra
        // subindo enquanto o modelo escreve. Contado, nao estimado.
        bastidor.palavras = texto.textContent.trim().split(/\s+/).filter(Boolean).length;
        if (aqui()) { if (pertoDoFim()) rolar(); else atualizarIrAoFim(); }
      } else if (mt[1] === "proposta" || mt[1] === "oferta") {
        // "oferta" chega depois do fim: quer ver o documento de onde saiu
        // a resposta? O cartão fica embaixo da resposta.
        // Pedido de ação: nada de procurar nos documentos. O cartão mostra
        // o que eu entendi, e quem grava é a pessoa.
        plano.remove();
        linha("");
        const caixa = document.createElement("div");
        caixa.className = "proposta-caixa";
        caixa.innerHTML = cartaoProposta(dados);
        resposta.appendChild(caixa);
        ligarProposta(caixa, dados);
        // "abra o financeiro": o pedido era a tela. Abre depois do fim,
        // para a conversa terminar de se gravar antes de sair dela.
        if (dados.tipo === "programa" && (dados.campos || {}).modo === "ir") abrirAoFim = dados.campos.destino;
        // O pedido de mudança e o "salve no editor": o editor abre sozinho,
        // depois de a conversa terminar de se gravar.
        if ((dados.tipo === "mudar_documento" || dados.tipo === "editor_criado") && aqui()) {
          setTimeout(() => { if (caixa.isConnected) fazerDoCartaoDoEditor(caixa, dados); }, 800);
        }
        if ((dados.tipo === "programa" && !dados.por_modelo) || dados.tipo === "escopo" ||
            dados.tipo === "consulta_cadastro" || dados.tipo === "gravar" || dados.tipo === "assinar" || dados.tipo === "criar_agente" || dados.tipo === "email" || dados.tipo === "ficha" || dados.tipo === "lancamento" || dados.tipo === "financeiro" || dados.tipo === "relatorio" || dados.tipo === "config" ||
            ((dados.tipo === "agenda" || dados.tipo === "tarefa") && !(dados.ajuda_do_modelo || []).length)) assinaSemModelo = true;
        rolar();
      } else if (mt[1] === "relacionados") {
        // N7: chega depois do fim - os temas e as súmulas ligados aos artigos citados.
        if (typeof blocoRelacionados === "function") {
          const assinatura = resposta.querySelector(".assinatura");
          const html = blocoRelacionados(dados);
          if (assinatura) assinatura.insertAdjacentHTML("beforebegin", html); else resposta.insertAdjacentHTML("beforeend", html);
        }
      } else if (mt[1] === "vazio") {
        linha("");
        texto.textContent = dados.mensagem;
      } else if (mt[1] === "erro") {
        linha("");
        plano.innerHTML = '<div class="aprovacao"><p><strong>Não consegui terminar.</strong> ' +
          esc(dados.mensagem) + '</p><div class="acoes"><button class="primario" data-recarregar="1">Tentar de novo</button></div></div>';
        // C2: o "Tentar de novo" faz a pergunta de novo (antes, sem acao).
        const botao = plano.querySelector("[data-recarregar]");
        if (botao && pensando()) botao.onclick = () => { plano.remove(); tentarDeNovo(pedido, minha); };
      } else if (mt[1] === "parado") {
        // A pessoa parou: o que ja saiu fica, com a marca de que parou ali.
        if (typeof pararEscritaNoAparelho === "function") pararEscritaNoAparelho();
        linha("");
        fecharBastidor();
        plano.remove();
        if (!texto.textContent.trim()) texto.textContent = "Parei antes de escrever a resposta.";
        resposta.insertAdjacentHTML("afterbegin", etiquetaDeParada());
        resposta.insertAdjacentHTML("beforeend", linhaAssinatura(dados.segundos, citados, pedido, "", null, fontesAtuais));
        guardarLogNaResposta(resposta);
        ligarResposta(resposta);
        if (aqui()) $("conversa-titulo").textContent = dados.titulo;
      } else if (mt[1] === "fim") {
        linha("");
        fecharBastidor();
        plano.remove();
        /* O aviso de fora da cobertura (M7) chega como texto: no fim, ganha o botão. */
        if (!revisado && /Não tenho material de .{2,40} na biblioteca/.test(texto.textContent)) {
          texto.innerHTML = comAvisoDeArea(esc(texto.textContent));
        }
        resposta.insertAdjacentHTML("beforeend", linhaAssinatura(dados.segundos, citados, pedido,
          assinaSemModelo ? "sem modelo" : "", dados.como, fontesAtuais));
        guardarLogNaResposta(resposta);
        ligarResposta(resposta);
        if (aqui()) $("conversa-titulo").textContent = dados.titulo;
        if (abrirAoFim && aqui()) { const id = abrirAoFim; setTimeout(() => abrirTelaDaConversa(id), 700); }
      }
    }
  }
  if (saiu) return "saiu";
  return "fim";
}

/* Voltou para uma conversa que ainda responde (C1): a resposta é redesenhada
   do começo do registro da execução - etapas, o que estou fazendo e o texto
   que já saiu - e continua ao vivo. */
async function acompanharExecucao(t, execucao) {
  if (estado.ocupado) return;
  const minha = t.id;
  const pessoa = (t.mensagens || []).filter((m) => m.autor === "pessoa").pop();
  const pedido = pessoa ? pessoa.texto : "";
  estado.ocupado = true;
  estado.respondendoId = minha;
  estado.controle = new AbortController();
  modoDoEnviar("parar");
  atualizarSelo(true);
  const centro = $("centro");
  // O cartão parado que desenharTrabalho pôs no fim dá lugar ao vivo.
  const parado = centro.lastElementChild;
  if (parado && parado.querySelector && parado.querySelector("[data-retomar]") === null && parado.classList.contains("trab-cartao")) parado.remove();
  const plano = document.createElement("div");
  const registro = desenharPlano(plano, t.etapas || [], pensando() ? etapaAtual(t.etapas || []) : t.etapa_atual, true);
  centro.appendChild(plano);
  abrirBastidor(registro, { solto: true });
  const desde = Date.parse(execucao.criada || "") || Date.now();
  bastidor.desde = desde;
  const resposta = document.createElement("div");
  resposta.className = "resposta";
  resposta.innerHTML = linhaDeEstadoInicial() + '<div class="texto"></div>';
  centro.appendChild(resposta);
  const texto = resposta.querySelector(".texto");
  const relogio = setInterval(() => { if (estado.trabalhoId === minha) atualizarTempoDoPlano(desde); }, 1000);
  rolar();
  try {
    const r = await fetch("/api/execucoes/" + execucao.id + "/eventos?desde=0", { signal: estado.controle.signal });
    if (!r.ok) throw new Error(await erroDe(r));
    await lerResposta(r, { plano: plano, resposta: resposta, texto: texto, pedido: pedido, minha: minha });
  } catch (err) {
    if (!(err && err.name === "AbortError")) texto.textContent = "Não consegui acompanhar a resposta: " + (err.message || err);
  } finally {
    const reinscrever = estado.saindo && estado.trabalhoId === minha;
    estado.saindo = false;
    estado.execucaoId = "";
    if (estado.trabalhoId === minha) fecharBastidor();
    clearInterval(relogio);
    estado.ocupado = false;
    estado.respondendoId = null;
    estado.controle = null;
    atualizarBotaoEnviar();
    atualizarSelo(false);
    carregarTrabalhos();
    if (estado.trabalhoId === minha) {
      fetch("/api/trabalhos/" + minha).then((r) => r.json())
        .then((novo) => {
          if (estado.trabalhoId !== minha) return;
          estado.trabalho = novo; desenharAtividade(novo.atividade); desenharProgresso(novo.etapas || []); atualizarBotaoEnviar();
          if (painelNovo()) { marcarRespostasGuardadas(novo); selecionarResposta(respostaPadrao(novo)); }
        });
    }
    if (painelNovo()) { estado.linhaViva = ""; desenharBarra(); setTimeout(soltarEspera, 0); }
    if (reinscrever && estado.trabalho) vigiarTrabalhoEmCurso(estado.trabalho);
  }
}

/* Trocar de conversa com uma resposta sendo lida (C1): com a execução, a
   leitura larga - a resposta continua no servidor, e voltar se reinscreve.
   Sem ela, nada: fechar a leitura pararia a resposta. */
function largarInscricao(paraId) {
  if (!estado.ocupado || !estado.execucaoId || !estado.controle) return;
  // A mesma conversa, redesenhada: larga e se reinscreve logo depois.
  estado.saindo = true;
  estado.controle.abort();
}

/* ------------------------------------------- o documento de que se fala

   Ler o acervo inteiro para responder sobre um documento é o que fazia a
   pergunta sobre um comprovante de viagem voltar falando de contrato de compra
   e venda: o documento citado era 3,4% do que o modelo recebia. Agora a
   conversa tem um documento em foco, e ele fica à VISTA numa pílula — escopo
   silencioso seria tão ruim quanto ler tudo calado.

   Para sair dele: o ✕ da pílula, ou pedir com todas as letras ("em todos os
   documentos"). */

const mencao = { aberta: false, itens: [], marcado: 0, inicio: -1 };

async function carregarAbertos() {
  try {
    const d = await (await fetch("/api/documentos-abertos")).json();
    estado.abertos = d.documentos || [];
  } catch (err) { estado.abertos = []; }
}

/* Lista, e nao um nome so: anexar dois arquivos e perguntar sobre "eles" e o
   caso comum - quem arrasta um contrato e o aditivo quer os dois lidos. */
/* ANEXO E FOCO SÃO COISAS DIFERENTES.

   O anexo vale para a mensagem em que foi anexado — como em qualquer chat:
   anexa, pergunta, e ele sai da caixa. Antes o anexo ficava preso na caixa
   depois da resposta, e a conversa parecia pedir o mesmo arquivo de novo a
   cada pergunta.

   Sem anexo, a pílula diz onde a próxima pergunta procura, e um clique
   alterna entre os três modos:
   - "foco": o documento que esta conversa vinha lendo;
   - "acervo": todos os documentos abertos;
   - "perguntar": sem escolher — a pergunta que não nomeia documento volta
     com um cartão perguntando onde;
   - "criativo": sem ler documento nenhum — o Paulus responde pelo que ele
     mesmo sabe (direito em tese, redação, ideias), na nuvem. */
const MODOS_DO_ESCOPO = ["foco", "acervo", "perguntar", "criativo"];

function definirEscopo(nomes) {
  const lista = Array.isArray(nomes) ? nomes : (nomes ? [nomes] : []);
  estado.escopo = lista.filter((n, i) => n && lista.indexOf(n) === i);
  desenharEscopo();
}

/* O documento da conversa: sai da resposta (os documentos que ela leu) ou da
   conversa reaberta. Com foco, o modo passa a ser o foco; sem, fica no que
   estava — a não ser que estivesse no foco, que deixou de existir. */
function definirFoco(nomes) {
  const lista = (Array.isArray(nomes) ? nomes : (nomes ? [nomes] : [])).filter(Boolean);
  estado.foco = lista.filter((n, i) => lista.indexOf(n) === i);
  if (estado.foco.length) estado.modoEscopo = "foco";
  else if (!estado.modoEscopo || estado.modoEscopo === "foco") estado.modoEscopo = "acervo";
  desenharEscopo();
}

function modoDoEscopo() {
  const modo = estado.modoEscopo || "acervo";
  return modo === "foco" && !(estado.foco || []).length ? "acervo" : modo;
}

function alternarModoDoEscopo() {
  const ordem = (estado.foco || []).length ? MODOS_DO_ESCOPO : ["acervo", "perguntar", "criativo"];
  estado.modoEscopo = ordem[(ordem.indexOf(modoDoEscopo()) + 1) % ordem.length];
  desenharEscopo();
  // C3: o modo e da conversa, e fica no servidor.
  guardarModoNoServidor();
}

/* O que a pergunta leva, dos anexos e do modo. */
function escopoDoEnvio() {
  if (estado.escopo.length) return { apenas: estado.escopo.slice(), tudo: false, sem_anexo: false };
  const modo = modoDoEscopo();
  return {
    apenas: modo === "foco" ? estado.foco.slice() : [],
    tudo: modo === "acervo",
    sem_anexo: modo === "perguntar",
    criativo: modo === "criativo",
  };
}

function somarAoEscopo(nome) {
  if (nome && !estado.escopo.includes(nome)) definirEscopo(estado.escopo.concat([nome]));
}

function tirarDoEscopo(nome) {
  definirEscopo(estado.escopo.filter((n) => n !== nome));
}

function nomeDoFoco() {
  const foco = estado.foco || [];
  if (foco.length === 1) return foco[0].length > 30 ? foco[0].slice(0, 28) + "…" : foco[0];
  return plural(foco.length, "documento") + " da conversa";
}

function desenharEscopo() {
  const caixa = $("escopo");
  if (!caixa) return;
  atualizarPropriedades();
  if (painelNovo() && !estado.ocupado) desenharBarra();
  caixa.hidden = false;

  if (!estado.escopo.length) {
    caixa.classList.remove("com-anexos");
    const modo = modoDoEscopo();
    const total = estado.contratos ? "Acervo · " + plural(estado.contratos, "documento") : "Acervo vazio";
    const rotulo = modo === "foco"
      ? ((estado.foco.length === 1 ? glifo(estado.foco[0]) : ic("description", 18)) + "<b>" + esc(nomeDoFoco()) + "</b>")
      : modo === "perguntar"
        ? ic("help", 18) + "<b>Pergunto onde procurar</b>"
        : modo === "criativo"
          ? ic("auto_awesome", 18) + "<b>Modo criativo</b>"
          : ic("folder", 18) + "<b>" + total + "</b>";
    const ordem = (estado.foco || []).length ? "o documento da conversa, todo o Acervo, perguntar onde procurar ou o modo criativo"
      : "todo o Acervo, perguntar onde procurar ou o modo criativo";
    const agora = modo === "foco"
      ? "A próxima pergunta lê só " + (estado.foco.length === 1 ? "“" + estado.foco[0] + "”" : "os documentos da conversa: " + estado.foco.join(", "))
      : modo === "perguntar"
        ? "A próxima pergunta que não nomear documento volta com um cartão perguntando onde procurar"
        : modo === "criativo"
          ? "A próxima pergunta não lê documento: o Paulus responde pelo que ele mesmo sabe, na nuvem"
          : "A próxima pergunta procura em todo o Acervo";
    caixa.innerHTML = '<span class="escopo-acervo escopo-livre" id="escopo-modo" role="button" tabindex="0" title="' +
      esc(agora + ". Clique para alternar entre " + ordem + ".") + '">' + rotulo + "</span>";
    const botao = $("escopo-modo");
    botao.onclick = () => { alternarModoDoEscopo(); $("pedido").focus(); };
    botao.onkeydown = (e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); alternarModoDoEscopo(); } };
    return;
  }

  /* Os anexos da próxima mensagem: cada um com o ícone do tipo (PDF, Word),
     o nome e o X. Numa conversa eles ganham uma linha própria, acima do
     texto - dividindo a linha com ele, espremiam o campo até o texto quebrar
     palavra por palavra. */
  caixa.innerHTML = estado.escopo.map((nome) =>
      '<span class="escopo-pilula" title="' + esc(nome) + ' — a próxima pergunta lê só os documentos anexados">' + glifo(nome) +
      '<b class="corta">' + esc(nome) + "</b>" +
      '<button data-tirar="' + esc(nome) + '" title="Tirar este documento" ' +
      'aria-label="Tirar ' + esc(nome) + '">' + ic("close", 14) + "</button></span>").join("");

  caixa.classList.add("com-anexos");
  caixa.querySelectorAll("[data-tirar]").forEach((b) => {
    b.onclick = () => { tirarDoEscopo(b.dataset.tirar); $("pedido").focus(); };
  });
}

/* O "/" e o que vem depois dele, até o cursor. Só vale no começo de uma
   palavra: "e/ou" não abre menção. */
function termoDaMencao() {
  const campo = $("pedido");
  const ate = campo.value.slice(0, campo.selectionStart);
  const barra = ate.lastIndexOf("/");
  if (barra < 0) return null;
  if (barra > 0 && !/\s/.test(ate[barra - 1])) return null;
  const termo = ate.slice(barra + 1);
  if (/[\n]/.test(termo)) return null;
  return { inicio: barra, termo: termo };
}

function fecharMencao() {
  mencao.aberta = false;
  const caixa = $("mencao");
  if (caixa) { caixa.hidden = true; caixa.innerHTML = ""; }
}

function abrirMencao() {
  const achado = termoDaMencao();
  const caixa = $("mencao");
  if (!caixa || !achado) { fecharMencao(); return; }

  const plano = (t) => String(t || "").normalize("NFD")
    .replace(new RegExp("[\u0300-\u036f]", "g"), "").toLowerCase();
  const procurado = plano(achado.termo);
  const todos = estado.abertos || [];
  mencao.itens = todos.filter((d) => plano(d.nome).includes(procurado)).slice(0, 12);
  mencao.marcado = 0;
  mencao.inicio = achado.inicio;
  mencao.aberta = true;

  caixa.hidden = false;
  caixa.innerHTML = mencao.itens.length
    ? mencao.itens.map((d, i) =>
        '<button class="mencao-item' + (i === 0 ? " marcado" : "") +
        '" data-doc="' + esc(d.nome) + '"><b>' + esc(d.nome) + "</b>" +
        (d.paginas ? '<span class="rotulo">' + plural(d.paginas, "página") + "</span>" : "") +
        "</button>").join("")
    : '<div class="mencao-vazio">nenhum documento aberto com “' +
      esc(achado.termo) + "”</div>";

  caixa.querySelectorAll("[data-doc]").forEach((b) => {
    b.onmousedown = (e) => { e.preventDefault(); escolherMencao(b.dataset.doc); };
  });
}

function escolherMencao(nome) {
  const campo = $("pedido");
  /* Tira o "/termo" do texto: quem guarda o documento é a pílula, e deixar o
     nome escrito no meio da frase faria a pergunta chegar ao modelo com um
     pedaço que não é pergunta. */
  const antes = campo.value.slice(0, mencao.inicio);
  const depois = campo.value.slice(campo.selectionStart);
  campo.value = (antes + depois).replace(/^\s+/, "");
  campo.selectionStart = campo.selectionEnd = antes.replace(/^\s+/, "").length;

  somarAoEscopo(nome);
  fecharMencao();
  campo.focus();
}

function andarNaMencao(passo) {
  if (!mencao.itens.length) return;
  mencao.marcado = (mencao.marcado + passo + mencao.itens.length) % mencao.itens.length;
  const caixa = $("mencao");
  caixa.querySelectorAll(".mencao-item").forEach((b, i) => {
    b.classList.toggle("marcado", i === mencao.marcado);
    if (i === mencao.marcado) b.scrollIntoView({ block: "nearest" });
  });
}

$("enviar").onclick = () => {
  const aqui = estado.ocupado && estado.trabalhoId && estado.trabalhoId === estado.respondendoId;
  return (aqui || respondendoFora()) ? pararResposta() : enviar();
};
$("pedido").addEventListener("keydown", (e) => {
  if (mencao.aberta) {
    if (e.key === "ArrowDown") { e.preventDefault(); andarNaMencao(1); return; }
    if (e.key === "ArrowUp") { e.preventDefault(); andarNaMencao(-1); return; }
    if (e.key === "Escape") { e.preventDefault(); fecharMencao(); return; }
    if ((e.key === "Enter" || e.key === "Tab") && mencao.itens.length) {
      e.preventDefault();
      escolherMencao(mencao.itens[mencao.marcado].nome);
      return;
    }
  }
  if (estado.modoBusca && e.key === "Escape") { e.preventDefault(); modoDeBusca(false); return; }
  // F1: Ctrl+Enter manda com prioridade na fila do modelo (js/58-fila.js).
  if (e.key === "Enter" && !e.shiftKey) {
    e.preventDefault();
    if (estado.modoBusca) $("buscar").click();
    else enviar(filaLigada() && (e.ctrlKey || e.metaKey) ? { prioridade: true } : undefined);
  }
});
$("pedido").addEventListener("input", (e) => {
  e.target.style.height = "auto";
  e.target.style.height = Math.min(e.target.scrollHeight, 150) + "px";
  if (termoDaMencao()) abrirMencao(); else fecharMencao();
});
$("pedido").addEventListener("blur", () => setTimeout(fecharMencao, 120));

/* ------------------------------------------------------------- estado */

/* A marca do trilho e so a marca: quando o assistente trabalha, quem diz e a
   propria conversa - o cartao do plano, a linha do que esta acontecendo e o
   ponto no cabecalho. Um anel girando em volta do logo repetia isso no canto
   do olho, longe de onde a pessoa esta lendo. */
function atualizarSelo(trabalhando) {
  document.documentElement.classList.toggle("trabalhando", Boolean(trabalhando));
}

async function carregarStatus() {
  try {
    const s = await (await fetch("/api/status")).json();
    estado.contratos = s.contratos;
    estado.modelo = s.modelo || "";
    estado.trechos = s.trechos || 0;
    estado.motor = s.motor && s.motor.host ? "Ollama · " + s.motor.host + (s.motor.rodando ? "" : " (desligado)") : "";
    estado.pasta = s.pasta || "";
    /* O subtitulo e de quem esta na tela. O status chega de tempos em tempos e
       escrevia por cima de qualquer tela aberta: a Agenda dizia "17 documentos
       abertos" no lugar da semana, o Foco no lugar do tempo ativo. */
    if (!String(troca.tela || "").startsWith("tela:") && !(typeof cfgNoLado === "function" && cfgNoLado())) {
      $("conversa-meta").textContent = s.contratos
        ? plural(s.contratos, "documento") + " abertos · " + s.trechos + " trechos"
        : "nenhum documento aberto";
    }
    desenharAvisoDoMotor(s);
    desenharEscopo();
    if ($("conversa-col").classList.contains("vazia")) desenharRecentes();
  } catch (err) { /* servidor caiu; o anel do trilho ja parou */ }
}

/* O cartao de erro do motor (docs/ui/05): "O assistente esta desligado" com
   Ligar agora; "Falta baixar o modelo" com o tamanho e Baixar agora; "O
   Ollama nao esta instalado" com o caminho. Aparece no inicio, acima da
   caixa de pedido, e some sozinho quando o motor responde. */
let relogioDaPuxada = null;

function desenharAvisoDoMotor(s) {
  const alvo = $("aviso-motor");
  if (!alvo) return;
  const m = s.motor || {};
  const puxando = m.puxando || {};
  if ((s.ollama && !puxando.andando) || !$("conversa-col").classList.contains("vazia")) {
    alvo.hidden = true;
    alvo.innerHTML = "";
    return;
  }
  let titulo, causa, acao;
  if (puxando.andando) {
    titulo = "Baixando o modelo do assistente";
    causa = "Uma vez só, com internet. Dá para continuar usando o PAULUS; o assistente responde quando terminar.";
    acao = '<div class="barra-fina"><i id="motor-barra" style="width:' + (puxando.progresso || 1) + '%"></i></div><small id="motor-linha">' + esc(puxando.linha || "começando…") + "</small>";
  } else if (puxando.erro) {
    titulo = "O download do modelo parou";
    causa = puxando.erro;
    acao = '<button class="primario" data-motor-puxar="1">' + ic("refresh", 16) + "Tentar de novo</button>";
  } else if (!m.instalado) {
    titulo = "O Ollama não está instalado";
    causa = "O Ollama é o programa que roda o modelo nesta máquina, sem mandar nada para fora. Instale pelo site e abra o PAULUS de novo.";
    acao = '<button class="primario" data-motor-site="1">' + ic("open_in_new", 16) + "Abrir a página do Ollama</button>";
  } else if (!m.rodando) {
    titulo = "O assistente está desligado";
    causa = "O Ollama, que roda o modelo nesta máquina, não está aberto. Dá para ligar daqui, sem terminal.";
    acao = '<button class="primario" data-motor-ligar="1">' + ic("play_arrow", 16) + "Ligar agora</button>";
  } else if (!m.modelo_presente) {
    titulo = "Falta baixar o modelo";
    causa = "O Ollama está aberto, mas o modelo" + (m.tamanho ? " (" + m.tamanho + ")" : "") + " ainda não está nesta máquina. É um download só, com internet; leva alguns minutos.";
    acao = '<button class="primario" data-motor-puxar="1">' + ic("download", 16) + "Baixar agora</button>";
  } else {
    alvo.hidden = true;
    alvo.innerHTML = "";
    return;
  }
  alvo.innerHTML = '<div class="cartao-erro"><b>' + esc(titulo) + "</b><p>" + esc(causa) + '</p><div class="acoes">' + acao + "</div>" +
    (m.mensagem && !puxando.andando ? "<details><summary>" + ic("expand_more", 16) + "Detalhes</summary><pre>" + esc(m.mensagem) + "</pre></details>" : "") + "</div>";
  alvo.hidden = false;
  const ligar = alvo.querySelector("[data-motor-ligar]");
  if (ligar) ligar.onclick = () => ligarMotor(ligar);
  const puxar = alvo.querySelector("[data-motor-puxar]");
  if (puxar) puxar.onclick = () => puxarModelo(puxar);
  const site = alvo.querySelector("[data-motor-site]");
  if (site) site.onclick = () => window.open("https://ollama.com/download", "_blank");
  if (puxando.andando) vigiarPuxada();
}

async function ligarMotor(botao) {
  botao.disabled = true;
  botao.textContent = "ligando…";
  const r = await fetch("/api/ollama/ligar", { method: "POST" });
  if (!r.ok) { avisoCert(await erroDe(r), { tom: "erro" }); botao.disabled = false; botao.textContent = "Ligar agora"; return; }
  const d = await r.json();
  if (d.ligado) avisoCert("assistente ligado", { tom: "ok" });
  else if (d.motor && d.motor.rodando) avisoCert("o Ollama abriu, mas falta o modelo", { tom: "erro" });
  else avisoCert("o Ollama não respondeu: " + (d.mensagem || ""), { tom: "erro" });
  carregarStatus();
}

async function puxarModelo(botao) {
  botao.disabled = true;
  const r = await fetch("/api/ollama/puxar", { method: "POST" });
  if (!r.ok) { avisoCert(await erroDe(r), { tom: "erro" }); botao.disabled = false; return; }
  carregarStatus();
}

function vigiarPuxada() {
  clearTimeout(relogioDaPuxada);
  relogioDaPuxada = setTimeout(async () => {
    let p;
    try { p = await (await fetch("/api/ollama/puxar")).json(); } catch (err) { return; }
    if (p.andando) {
      const barra = $("motor-barra");
      if (barra) barra.style.width = (p.progresso || 1) + "%";
      const linha = $("motor-linha");
      if (linha) linha.textContent = p.linha || "baixando…";
      vigiarPuxada();
      return;
    }
    if (p.pronto) avisoCert("modelo baixado — o assistente está pronto", { tom: "ok" });
    carregarStatus();
  }, 2000);
}

async function carregarModelo() {
  try {
    const s = await (await fetch("/api/status")).json();
    $("prop-modelo").title = s.tamanho_gb
      ? String(s.tamanho_gb).replace(".", ",") + " GB na sua máquina"
      : "na sua máquina";
  } catch (err) { /* mantem o texto padrao */ }
}

/* O painel Propriedades: modelo, motor, o que esta em foco e o indice. */
function atualizarPropriedades() {
  // C3: motor, trechos indexados e pasta sao dado tecnico - so no modo de
  // diagnostico, e o motor vem de /api/status (nao do texto fixo do HTML).
  const props = $("lat-propriedades");
  if (props) props.hidden = painelNovo() && !diagnostico();
  if (estado.motor) $("prop-motor").textContent = estado.motor;
  $("prop-modelo-nome").textContent = estado.modelo || "—";
  let pasta = "—";
  const foco = estado.escopo.length ? estado.escopo : (modoDoEscopo() === "foco" ? estado.foco : []);
  if (foco.length === 1) pasta = foco[0];
  else if (foco.length > 1) pasta = plural(foco.length, "documento") + " em foco";
  else if (estado.contratos) pasta = "Acervo · " + plural(estado.contratos, "documento");
  $("prop-pasta").textContent = pasta;
  $("prop-trechos").textContent = estado.trechos ? plural(estado.trechos, "trecho") + " indexados" : "—";
}

/* ------------------------------------------------- saudacao e relogio */
/*
   A saudacao sai do relogio da maquina, nao de um modelo. Pedir isso ao
   assistente custaria 20 s de espera na abertura, e o programa promete nao
   falar com ninguem la fora - a hora ele ja tem.
*/

function contexto() {
  const d = new Date();
  const dias = ["domingo", "segunda-feira", "terça-feira", "quarta-feira",
                "quinta-feira", "sexta-feira", "sábado"];
  const meses = ["janeiro", "fevereiro", "março", "abril", "maio", "junho",
                 "julho", "agosto", "setembro", "outubro", "novembro", "dezembro"];
  const h = d.getHours();
  const periodo = h < 5 ? "madrugada" : h < 12 ? "manha" : h < 18 ? "tarde" : h < 22 ? "noite" : "noite_alta";
  const hora = String(h).padStart(2, "0") + ":" + String(d.getMinutes()).padStart(2, "0");
  return {
    dia: dias[d.getDay()],
    hora: hora,
    periodo: periodo,
    /* A etiqueta do alto da saudacao. O dia sai sem "-feira" porque ali ele e
       um carimbo, nao uma frase. */
    momento: dias[d.getDay()].replace("-feira", "") + ", " + d.getDate() + " de " +
      meses[d.getMonth()] + " · " + hora.replace(":", "h"),
  };
}

/* O texto da saudacao fala como gente, nao como o painel de controle:
   nada de "indexar", "trecho" ou "varrer". Quem le e advogado, e o que ele
   quer saber e se pode pedir e se o que e dele fica com ele. */
function saudacao(c, temDocumentos) {
  const semDocs = "Para começar, me mande alguns documentos — ou me mostre a pasta onde eles estão.";
  const padrao = "É só me dizer o que você precisa — eu leio e respondo aqui mesmo.";
  const sub = temDocumentos ? padrao : semDocs;

  if (c.periodo === "madrugada") {
    return ["Ainda de pé a esta hora?", temDocumentos ? "Se quiser, eu adianto a leitura enquanto você descansa." : semDocs];
  }
  if (c.periodo === "noite_alta") return ["Trabalhando até tarde?!", temDocumentos ? "Me conta o que falta, e eu vou adiantando por aqui." : semDocs];
  if (c.dia === "sexta-feira") return ["Sexta. Fechamos algo antes do fim do dia?", sub];
  if (c.dia === "segunda-feira" && c.periodo === "manha") return ["Segunda. Por onde começamos?", sub];
  return ["Olá. Por onde começamos?", sub];
}

function atualizarSaudacao() {
  const c = contexto();
  const [titulo, sub] = saudacao(c, estado.contratos > 0);
  $("momento").textContent = c.momento;
  $("chamada").textContent = titulo;
  /* O texto base fica guardado aqui porque `carregarAgora` acrescenta a
     situacao do acervo a esta mesma frase, e ele roda a cada cinco segundos:
     sem a base, a frase cresceria sozinha a cada volta. */
  $("sub-chamada").dataset.base = sub;
  $("sub-chamada").textContent = sub;
  $("relogio").textContent = c.hora;
  // T1: com conversa.saudacao, a frase do banco troca esta assim que chega.
  if (typeof pedirSaudacao === "function") pedirSaudacao();
}

setInterval(() => { $("relogio").textContent = contexto().hora; }, 30000);

/* ------------------------------------------------- acontecendo agora */

/* O ANDAMENTO DO CARTAO, so com numero de verdade. A barra aparece onde ha
   medida: um trabalho que conta (12 de 40 documentos) ou a leitura de uma
   resposta quando esta maquina ja mediu leituras daquele tamanho - ai ela e
   o tempo decorrido sobre a previsao, parando em 95% ate a primeira palavra
   sair. Sem previsao, e escrevendo (nao ha como saber o tamanho da
   resposta), nao ha barra: ha o tempo e o que ja saiu. Antes a barra era a
   conta de etapas, e ficava parada em 50% a leitura inteira. */
function segundosCurtos(s) {
  s = Math.max(0, Math.round(s));
  return s < 60 ? s + " s" : Math.floor(s / 60) + " min " + String(s % 60).padStart(2, "0") + " s";
}

function andamentoDoCartao(t) {
  if (t.total) {
    const pct = Math.round((t.feitos / t.total) * 100);
    return '<div class="barra-fina"><i style="width:' + pct + '%"></i></div>' +
      '<div class="rodape">' + esc(t.etapa || "trabalhando") + " · " + t.feitos + " de " + t.total + "</div>";
  }
  const a = t.andamento;
  if (!a) return '<div class="rodape">' + esc(t.etapa || "trabalhando") + "</div>";
  const docs = a.documentos ? plural(a.documentos, "documento") : "os documentos";
  const vivo = ' data-andamento="1" data-fase="' + a.fase + '" data-fase-s="' + a.fase_s + '" data-previsao="' + (a.previsao_s || 0) +
    '" data-palavras="' + (a.palavras || 0) + '" data-docs="' + esc(docs) + '" data-posicao="' + (a.posicao || 0) + '" data-recebido="' + Date.now() + '"';
  if ((a.fase === "lendo" || a.fase === "documento") && a.previsao_s) {
    const pct = Math.min(95, (a.fase_s / a.previsao_s) * 100);
    return '<div class="barra-fina"' + vivo + '><i style="width:' + pct.toFixed(1) + '%"></i></div>' +
      '<div class="rodape"' + vivo + ">" + textoDoAndamento(a.fase, a.fase_s, a.previsao_s, a.palavras, docs, a.posicao) + "</div>";
  }
  return '<div class="rodape"' + vivo + ">" + textoDoAndamento(a.fase, a.fase_s, a.previsao_s, a.palavras, docs, a.posicao) + "</div>";
}

/* O CARTÃO DE UMA RESPOSTA ANDANDO (pacote de telas, `Assistente -
   Acontecendo agora` e o cartão de `Conversa - Carregando`): o título, o
   tempo ("6 s de ~32 s" quando esta máquina já mediu leituras deste
   tamanho) e o Parar; embaixo, uma faixa por etapa - a que anda é mais
   larga, enche até a previsão e tem o brilho correndo; a feita fica cheia
   com o check e o que achou; a que espera fica apagada. */
const NOME_CURTO_DA_ETAPA = {
  "procurar nos documentos": "Procurar", "lendo os documentos": "Ler", "ler os documentos": "Ler",
  "escrevendo a resposta": "Responder", "responder": "Responder", "entender o pedido": "Entender",
};

function nomeCurtoDaEtapa(titulo) {
  const t = String(titulo || "");
  return NOME_CURTO_DA_ETAPA[t.toLowerCase()] || t;
}

function tempoDoTrabalho(a) {
  if (!a) return "";
  const decorrido = a.decorrido_s || 0;
  const total = a.previsao_s && (a.fase === "lendo" || a.fase === "documento") ? decorrido - (a.fase_s || 0) + a.previsao_s : 0;
  return segundosCurtos(decorrido) + (total > decorrido ? " de ~" + segundosCurtos(total) : "");
}

function faixasDasEtapas(etapas, a) {
  const lista = (etapas || []).length ? etapas : [{ titulo: "Trabalhando", estado: "executando", detalhe: "" }];
  const colunas = lista.map((e) => (e.estado === "executando" ? "2.4fr" : "1fr")).join(" ");
  const partes = lista.map((e) => {
    const nome = nomeCurtoDaEtapa(e.titulo) + (e.detalhe ? " · " + e.detalhe : "") + (e.total ? " · " + e.feitos + " de " + e.total : "");
    if (e.estado === "concluido") {
      return '<div class="agr-etapa feita"><i class="agr-faixa"></i><span>' + ic("check", 14) + esc(nome) + "</span></div>";
    }
    if (e.estado === "executando") {
      let pct = e.total ? (e.feitos / e.total) * 100 : 0;
      if (!e.total && a && a.previsao_s && (a.fase === "lendo" || a.fase === "documento")) pct = Math.min(95, ((a.fase_s || 0) / a.previsao_s) * 100);
      const vivo = a && !e.total ? ' data-agr-vivo="1" data-fase-s="' + (a.fase_s || 0) + '" data-previsao="' + (a.previsao_s || 0) + '" data-recebido="' + Date.now() + '"' : "";
      return '<div class="agr-etapa andando"><i class="agr-faixa' + (pct ? "" : " sem-medida") + '"><i style="width:' + (pct ? pct.toFixed(1) + "%" : "100%") + '"' + vivo + "></i></i>" +
        '<span><i class="agr-respira"></i>' + esc(nome) + "</span></div>";
    }
    return '<div class="agr-etapa espera"><i class="agr-faixa"></i><span>' + esc(nomeCurtoDaEtapa(e.titulo)) + "</span></div>";
  }).join("");
  return '<div class="agr-etapas" style="grid-template-columns:' + colunas + '">' + partes + "</div>";
}

function cartaoDoTrabalhoAgora(t) {
  const a = t.andamento;
  const tempo = a ? '<span class="agr-tempo" data-agr-tempo="1" data-decorrido="' + (a.decorrido_s || 0) + '" data-fase-s="' + (a.fase_s || 0) +
    '" data-previsao="' + (a.previsao_s || 0) + '" data-fase="' + esc(a.fase || "") + '" data-recebido="' + Date.now() + '">' + esc(tempoDoTrabalho(a)) + "</span>" : "";
  // Na fila do modelo a faixa nao anda: a linha diz a posição.
  const fila = a && a.fase === "fila" ? '<div class="agr-fila">' + esc(textoDoAndamento("fila", a.fase_s, a.previsao_s, 0, "", a.posicao)) + "</div>" : "";
  return '<div class="cartao-agora agr-cartao" data-abre="' + esc(t.id) + '"><div class="cabeca">' +
    '<b class="nome corta">' + esc(t.titulo) + "</b>" + tempo +
    '<button class="agr-parar" data-parar-trabalho="' + esc(t.id) + '" title="Interromper a resposta"><i></i>Parar</button></div>' +
    (fila || faixasDasEtapas(t.etapas, a)) + "</div>";
}

/* O tempo e a faixa andam entre uma consulta e outra (5 s). */
setInterval(() => {
  document.querySelectorAll("[data-agr-tempo]").forEach((el) => {
    const passou = (Date.now() - Number(el.dataset.recebido)) / 1000;
    el.textContent = tempoDoTrabalho({ decorrido_s: Number(el.dataset.decorrido) + passou, fase_s: Number(el.dataset.faseS) + passou,
      previsao_s: Number(el.dataset.previsao), fase: el.dataset.fase });
  });
  document.querySelectorAll("[data-agr-vivo]").forEach((el) => {
    const previsao = Number(el.dataset.previsao);
    if (!previsao) return;
    const s = Number(el.dataset.faseS) + (Date.now() - Number(el.dataset.recebido)) / 1000;
    el.style.width = Math.min(95, (s / previsao) * 100).toFixed(1) + "%";
  });
}, 1000);

/* "Na fila: você é o 2º, ~40 s". A previsão só aparece quando esta máquina
   já mediu respostas (src/ritmo.py); sem medida, só a posição. */
function textoDaFila(d) {
  // F1: quem está na frente, pelo primeiro nome e a tela - nunca o texto.
  const frente = (d.na_frente || []).map((x) => x.nome + " · " + x.origem);
  // N11: a resposta que voltou do aparelho espera a vez do escritório.
  return (d.depois_do_aparelho ? "a resposta voltou ao escritório e " : "") + "na fila do modelo: você é o " + (d.posicao || 1) + "º" + (d.previsao_s ? ", ~" + segundosCurtos(d.previsao_s) : "") +
    (frente.length ? " · na frente: " + frente.join(", ") : "") + (d.motivo ? " (" + d.motivo + ")" : "") +
    (d.aviso ? " · " + d.aviso : "");
}

function textoDoAndamento(fase, s, previsao, palavras, docs, posicao) {
  if (fase === "fila") return "Na fila do modelo · " + (posicao || 1) + "º" + (previsao ? " · ~" + segundosCurtos(previsao) : "");
  if (fase === "entendendo") return "Entendendo o pedido · " + segundosCurtos(s);
  if (fase === "documento") {
    return "Escrevendo no documento · " + segundosCurtos(s) + (previsao ? " de ~" + segundosCurtos(previsao) : "");
  }
  if (fase === "procurando") return "Procurando nos documentos · " + segundosCurtos(s);
  if (fase === "lendo") {
    return "Lendo " + docs + " · " + segundosCurtos(s) +
      (previsao ? " de ~" + segundosCurtos(previsao) : " · primeira leitura deste tamanho, sem previsão ainda");
  }
  return "Escrevendo a resposta · " + (palavras ? plural(palavras, "palavra") + " · " : "") + segundosCurtos(s);
}

/* Entre uma consulta e outra (5 s), o tempo e a barra andam aqui, a cada
   meio segundo, a partir do que o servidor disse. */
setInterval(() => {
  document.querySelectorAll("[data-andamento]").forEach((el) => {
    const s = Number(el.dataset.faseS) + (Date.now() - Number(el.dataset.recebido)) / 1000;
    const previsao = Number(el.dataset.previsao);
    const barra = el.querySelector("i");
    if (barra && previsao) barra.style.width = Math.min(95, (s / previsao) * 100).toFixed(1) + "%";
    if (!barra) el.textContent = textoDoAndamento(el.dataset.fase, s, previsao, Number(el.dataset.palavras), el.dataset.docs || "os documentos", Number(el.dataset.posicao));
  });
}, 500);

async function carregarAgora() {
  if (!$("conversa-col").classList.contains("vazia")) {
    $("agora").hidden = true;
    return;
  }

  let d;
  try {
    d = await (await fetch("/api/agora")).json();
  } catch (err) {
    $("agora").hidden = true;
    return;
  }

  const cartoes = [];

  // A gravação que está andando (pacote de telas, `Assistente - Gravando`).
  if (typeof cartaoDaGravacaoAgora === "function") {
    const gravando = cartaoDaGravacaoAgora();
    if (gravando) cartoes.push(gravando);
  }
  for (const t of d.executando) cartoes.push(cartaoDoTrabalhoAgora(t));

  for (const t of d.esperando) {
    cartoes.push(
      '<div class="cartao-agora chama"><div class="cabeca"><i class="ponto-acc"></i>' +
      '<span class="nome">Esperando você</span></div>' +
      '<div class="corpo">' + esc(t.pergunta) + "</div>" +
      '<div class="acoes"><button class="fantasma" data-abre="' + esc(t.id) + '">Revisar</button>' +
      '<button class="primario" data-fila="1">Aprovar</button></div></div>'
    );
  }

  /* O acervo em dia e as conversas paradas nao sao cartoes: sao frases da
     saudacao. Nenhum dos dois pede acao nenhuma - virar cartao com botao
     seria dar a eles o peso de quem espera resposta, que e dos de cima.

     Embaixo do titulo cabem DUAS linhas, entao entra uma frase de situacao
     so, depois da de abertura. A conversa que ficou pela metade vence o
     acervo em dia: e a unica das duas que a pessoa talvez queira retomar. */
  const sub = $("sub-chamada");
  const base = sub.dataset.base || sub.textContent;
  const docs = d.biblioteca.documentos;
  let situacao = "";
  if (d.pausados) {
    situacao = (d.pausados === 1 ? "Uma conversa ficou pela metade" : plural(d.pausados, "conversa") + " ficaram pela metade") +
      " — abra pelo menu para continuar.";
  } else if (docs) {
    situacao = (docs === 1 ? "Seu documento já está lido" : "Seus " + docs + " documentos já estão lidos") +
      ", e nada saiu deste computador hoje.";
  }
  sub.textContent = situacao ? base + " " + situacao : base;

  const espera = vinculoPendente() ? [cartaoDeEsperaDoVinculo()] : [];
  const ditando = cartaoDoDitado();
  $("agora").hidden = cartoes.length + espera.length === 0 && !ditando;
  $("agora-cartoes").innerHTML = ditando + espera.concat(cartoes).join("");
  ligarCartaoDoDitado();
  ligarEsperaDoVinculo();
  if (typeof ligarGravacaoAgora === "function") ligarGravacaoAgora($("agora-cartoes"));
  $("agora-cartoes").querySelectorAll("[data-abre]").forEach((el) => {
    el.onclick = (e) => {
      e.stopPropagation();
      if (el.dataset.abre === "biblioteca") { marcarDestino("biblioteca"); mostrarBiblioteca(); }
      else abrirTrabalho(el.dataset.abre);
    };
  });
  /* Interromper daqui: vale para qualquer resposta andando, inclusive a que
     esta pagina esta lendo - que entao termina sozinha com "parada". */
  $("agora-cartoes").querySelectorAll("[data-parar-trabalho]").forEach((el) => {
    el.onclick = async (e) => {
      e.stopPropagation();
      el.disabled = true;
      try { await fetch("/api/trabalhos/" + el.dataset.pararTrabalho + "/parar", { method: "POST" }); } catch (err) { /* a lista se refaz */ }
      avisoCert("resposta interrompida", { tom: "ok" });
      setTimeout(carregarAgora, 600);
    };
  });
  $("agora-cartoes").querySelectorAll("[data-fila]").forEach((el) => {
    el.onclick = () => { marcarDestino("aprovacoes"); mostrarAprovacoes(); };
  });
}

setInterval(carregarAgora, 5000);

