/* --------------------------------------------- verificar assinatura */
/*
   O modal que confere as assinaturas de um PDF, e o "PAVLVS - Certificado
   de conformidade" que sai dele. A conferencia e a de sempre
   (/api/assinaturas/conferir): feita nesta maquina, sem internet - diz quem
   assinou, quem emitiu o certificado, quando, e se o documento foi alterado
   depois. O que ela nao faz (revogacao, cadeia ate a raiz) vai dito no modal
   e no relatorio.

   Cada assinatura aparece recolhida - quem, a AC, quando e o veredito -, e
   clicar revela o tecnico: padrao, algoritmos, serie e validade do
   certificado, carimbo de tempo.
*/

const ver = { caminho: "", nome: "", dados: null, relatorio: null, pagina: 1 };

const ROTULOS_DO_TECNICO = [
  ["campo", "Campo da assinatura"], ["padrao", "Padrão"], ["algoritmo_resumo", "Algoritmo de resumo"],
  ["algoritmo_assinatura", "Algoritmo de assinatura"], ["numero_de_serie", "Número de série do certificado"],
  ["valido_de", "Certificado válido de"], ["valido_ate", "Certificado válido até"], ["carimbo_de_tempo", "Carimbo de tempo"],
];

async function abrirVerificacao(caminho, nome) {
  ver.caminho = caminho;
  ver.nome = nome || String(caminho).split(/[\\/]/).pop();
  ver.dados = null;
  dialogo({
    titulo: "Verificar assinatura", contexto: ver.nome, classe: "dialogo-verificar",
    html: '<div class="vr" id="vr-corpo"><p class="nota">conferindo as assinaturas deste PDF…</p></div>',
    confirmar: "Certificado de conformidade", cancelar: "Fechar", aoConfirmar: gerarConformidade,
    rodape: '<small class="vr-limite">Conferido nesta máquina, sem internet.</small>',
  });
  try {
    const r = await fetch("/api/assinaturas/conferir?arquivo=" + encodeURIComponent(caminho));
    if (!r.ok) throw new Error(await erroDe(r));
    ver.dados = await r.json();
    desenharVerificacao();
  } catch (err) {
    const corpo = $("vr-corpo");
    if (corpo) corpo.innerHTML = '<div class="vr-veredito sem">' + ic("error", 20) + "<span>Não consegui conferir: " + esc(String(err.message || err)) + "</span></div>";
  }
}

function desenharVerificacao() {
  const corpo = $("vr-corpo");
  if (!corpo || !ver.dados) return;
  const d = ver.dados;
  const lista = (d.assinaturas || []).filter((a) => !a.erro);
  const icone = { ok: "check_circle", alerta: "error", sem: "info" }[d.tom] || "info";
  const arq = d.arquivo || {};
  corpo.innerHTML =
    '<div class="vr-veredito ' + esc(d.tom) + '">' + ic(icone, 20) + "<span><b>" +
    (d.tom === "sem" ? "Sem assinatura digital" : (d.tom === "ok" ? "Assinado e íntegro" : "Atenção")) + "</b>" + esc(d.veredito) + "</span></div>" +
    lista.map((a, i) => {
      const bom = a.intacta === true;
      const t = a.tecnico || {};
      const linhas = [
        ["Integridade", a.intacta === true ? "íntegra — não alterado depois de assinado" : (a.intacta === false ? "alterado depois de assinado" : "não foi possível conferir")],
        ["Cobre", a.cobre_documento_todo === true ? "o arquivo inteiro" : (a.cobre_documento_todo === false ? "parte do arquivo (houve acréscimo depois)" : "não informado")],
        ["ICP-Brasil", a.icp_brasil ? "pelo nome, a AC é da ICP-Brasil (cadeia não conferida)" : "AC fora da lista ICP-Brasil conhecida"],
      ].concat(ROTULOS_DO_TECNICO.filter(([k]) => t[k]).map(([k, r]) => [r, t[k]]));
      return '<div class="vr-cartao" data-vr-cartao="' + i + '">' +
        '<button type="button" class="vr-cartao-cabeca" aria-expanded="false">' +
        '<span class="vr-selo ' + (bom ? "ok" : "alerta") + '">' + ic(bom ? "check_circle" : "error", 18) + "</span>" +
        '<span class="duas-linhas"><b>' + esc(a.titular || "Assinante sem nome") + "</b><small>" +
        esc([a.emissor, a.quando ? "assinado em " + a.quando : ""].filter(Boolean).join(" · ")) + "</small></span>" +
        '<span class="vr-mais">detalhes' + ic("expand_more", 18) + "</span></button>" +
        '<div class="vr-tecnico" hidden>' + linhas.map(([r, v]) => '<div class="vr-linha"><span>' + esc(r) + "</span><b>" + esc(v) + "</b></div>").join("") + "</div></div>";
    }).join("") +
    (arq.sha256
      ? '<details class="vr-arquivo"><summary>O arquivo conferido</summary>' +
        '<div class="vr-linha"><span>Arquivo</span><b>' + esc(arq.nome || ver.nome) + "</b></div>" +
        (arq.paginas ? '<div class="vr-linha"><span>Páginas</span><b>' + arq.paginas + "</b></div>" : "") +
        '<div class="vr-linha"><span>SHA-256</span><b class="vr-hash">' + esc(arq.sha256) + "</b></div></details>"
      : "") +
    '<p class="vr-nota">Não confiro revogação nem a cadeia até a raiz da ICP-Brasil — isso exige internet. Para a validação jurídica completa, use o verificador do ITI (validar.iti.gov.br) com o arquivo original.</p>';

  corpo.querySelectorAll("[data-vr-cartao] .vr-cartao-cabeca").forEach((b) => {
    b.onclick = () => {
      const aberto = b.getAttribute("aria-expanded") === "true";
      b.setAttribute("aria-expanded", String(!aberto));
      const tec = b.parentElement.querySelector(".vr-tecnico");
      tec.hidden = aberto;
      if (!aberto && animacoesLigadas()) tec.animate([{ opacity: 0, transform: "translateY(-4px)" }, { opacity: 1, transform: "none" }], { duration: 180, easing: "ease-out" });
    };
  });
}

/* O relatorio: gera, mostra a pagina, e so entao oferece baixar e mandar. */
async function gerarConformidade() {
  const botao = document.querySelector('.dialogo-verificar [data-dialogo="confirmar"]');
  if (botao) { botao.disabled = true; botao.textContent = "Gerando…"; }
  try {
    const r = await fetch("/api/assinaturas/conformidade", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ arquivo: ver.caminho }),
    });
    if (!r.ok) throw new Error(await erroDe(r));
    ver.relatorio = await r.json();
    ver.pagina = 1;
    if (dialogoAberto) dialogoAberto.fechar(null);
    mostrarConformidade();
  } catch (err) {
    if (botao) { botao.disabled = false; botao.textContent = "Certificado de conformidade"; }
    avisoCert("não consegui gerar o certificado: " + (err.message || err));
  }
}

function mostrarConformidade() {
  const rel = ver.relatorio;
  if (!rel) return;
  dialogo({
    titulo: "PAVLVS · Certificado de conformidade", contexto: ver.nome, classe: "dialogo-conformidade",
    html: '<div class="vc"><div class="vc-folha"><img id="vc-img" alt="Certificado de conformidade"></div>' +
      (rel.paginas > 1
        ? '<div class="imp-andar"><button type="button" class="botao-icone" data-vc-andar="-1" aria-label="Página anterior">' + ic("chevron_left", 18) +
          '</button><span id="vc-num"></span><button type="button" class="botao-icone" data-vc-andar="1" aria-label="Próxima página">' + ic("chevron_right", 18) + "</button></div>"
        : "") + "</div>",
    confirmar: "Baixar", cancelar: "Fechar",
    aoConfirmar: () => baixarArquivo(rel.caminho),
    rodape: '<button type="button" class="docs-ligacao vc-acao" id="vc-windows">' + ic("open_in_new", 16) + "Abrir no Windows</button>" +
      '<button type="button" class="docs-ligacao vc-acao" id="vc-email">' + ic("mail", 16) + "Enviar por e-mail</button>",
  });
  const pintar = () => {
    $("vc-img").src = "/api/arquivos/pagina?caminho=" + encodeURIComponent(rel.caminho) + "&numero=" + ver.pagina + "&largura=640";
    const n = $("vc-num");
    if (n) n.textContent = "Página " + ver.pagina + " de " + rel.paginas;
  };
  document.querySelectorAll("[data-vc-andar]").forEach((b) => {
    b.onclick = () => { ver.pagina = Math.min(Math.max(1, ver.pagina + Number(b.dataset.vcAndar)), rel.paginas); pintar(); };
  });
  $("vc-windows").onclick = () => abrirNoWindows(rel.caminho);
  $("vc-email").onclick = () => { if (dialogoAberto) dialogoAberto.fechar(null); compartilharPorEmail(rel.caminho, rel.nome); };
  pintar();
}

async function abrirNoWindows(caminho) {
  const r = await fetch("/api/arquivos/abrir", {
    method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ caminho: caminho }),
  });
  if (!r.ok) avisoCert(await erroDe(r));
}

/* Na janela do programa, download de navegador nao chega a lugar nenhum: o
   PDF passa pelo "Salvar como" do Windows e o servidor grava a copia. No
   navegador, download comum. */
async function baixarArquivo(caminho, rota) {
  const api = (window.pywebview || {}).api || {};
  const nome = String(caminho).split(/[\\/]/).pop();
  if (api.salvar_como) {
    const destino = await api.salvar_como(nome, ["PDF (*.pdf)"]);
    if (!destino) return;
    const r = await fetch("/api/arquivos/salvar", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ caminho: caminho, destino: destino }),
    });
    if (!r.ok) { avisoCert(await erroDe(r)); return; }
    const d = await r.json();
    avisoCert("salvo em " + d.pasta + " — " + d.nome);
    return;
  }
  window.location.href = (rota || "/api/arquivos/baixar?caminho=") + encodeURIComponent(caminho);
}

/* O nosso "escolher pasta", no visual do anexar: atalhos, unidades e pastas
   desta maquina, a pasta atual no rodape. Com `nome`, um campo para o nome do
   arquivo que vai ser gravado. Devolve { pasta, nome } ou null. */
const ep = { caminho: "", dados: null };

function escolherPastaNossa(o) {
  ep.caminho = "";
  const opcoes = o || {};
  const escolha = dialogo({
    titulo: opcoes.titulo || "Escolher a pasta", contexto: opcoes.contexto || "Esta máquina", classe: "dialogo-anexar dialogo-pasta",
    confirmar: opcoes.confirmar || "Salvar aqui",
    html: '<div class="anx">' +
      '<div class="anx-migalhas" id="ep-migalhas"></div>' +
      '<div class="anx-lista" id="ep-lista"><p class="anx-vazio">abrindo…</p></div>' +
      (opcoes.nome !== undefined
        ? '<label class="ep-nome"><span>Nome do arquivo</span><input type="text" id="ep-nome" value="' + esc(opcoes.nome) + '" autocomplete="off" spellcheck="false"></label>'
        : "") +
      '<div class="anx-rodape"><span id="ep-onde" class="ep-onde"></span></div></div>',
    aoConfirmar: () => {
      if (!ep.caminho) return;
      const campo = $("ep-nome");
      const nome = campo ? campo.value.trim() : "";
      if (campo && !nome) { campo.focus(); return; }
      dialogoAberto.fechar({ ok: true, pasta: ep.caminho, nome: nome });
    },
  });
  navegarPastaNossa("");
  return escolha.then((r) => (r && r.ok ? { pasta: r.pasta, nome: r.nome } : null));
}

async function navegarPastaNossa(caminho) {
  ep.caminho = caminho;
  const lista = $("ep-lista");
  if (!lista) return;
  try { ep.dados = await (await fetch("/api/pastas?caminho=" + encodeURIComponent(caminho))).json(); }
  catch (err) { ep.dados = { erro: "não consegui abrir: " + err, atalhos: [], unidades: [], pastas: [], migalhas: [] }; }
  const d = ep.dados;
  const pasta = (p, icone) => '<div class="anx-linha anx-pasta" data-ep-ir="' + esc(p.caminho) + '">' + ic(icone, 17) +
    '<span class="duas-linhas"><b class="corta">' + esc(p.nome) + "</b></span>" + ic("chevron_right", 16) + "</div>";
  let html = "";
  if ((d.atalhos || []).length) html += '<div class="nav-grupo">Começar por</div>' + d.atalhos.map((a) => pasta(a, "folder_special")).join("");
  if ((d.unidades || []).length) html += '<div class="nav-grupo">Unidades</div>' + d.unidades.map((u) => pasta(u, "desktop_windows")).join("");
  html += (d.pastas || []).map((p) => pasta(p, "folder")).join("");
  if (d.erro) html += '<p class="anx-vazio">' + esc(d.erro) + "</p>";
  else if (!html) html = '<p class="anx-vazio">Nenhuma pasta dentro desta. Dá para salvar aqui mesmo.</p>';
  lista.innerHTML = html;
  const migalhas = $("ep-migalhas");
  migalhas.innerHTML = '<button type="button" data-ep-ir="">Este computador</button>' +
    (d.migalhas || []).map((m) => '<span class="lc-sep">›</span><button type="button" data-ep-ir="' + esc(m.caminho) + '">' + esc(m.nome) + "</button>").join("");
  document.querySelectorAll("#veu-dialogo [data-ep-ir]").forEach((b) => { b.onclick = () => navegarPastaNossa(b.dataset.epIr); });
  $("ep-onde").textContent = caminho ? "Salvar em " + caminho : "Escolha uma pasta";
  const botao = document.querySelector('#veu-dialogo [data-dialogo="confirmar"]');
  if (botao) botao.disabled = !caminho;
}

/* Compartilhar e o e-mail do proprio PAULUS, com o arquivo ja anexado. Sem
   conta de e-mail, leva para a Caixa, onde a conta se liga. */
async function compartilharPorEmail(caminho, nome) {
  if (!mail.contas) { try { mail.contas = await (await fetch("/api/email/contas")).json(); } catch (err) { mail.contas = null; } }
  marcarDestino("caixa");
  if (!mail.contas || !mail.contas.contas.length) {
    avisoCert("ligue uma conta de e-mail para mandar o arquivo por aqui");
    return mostrarEmail();
  }
  mail.conta = mail.contas.contas.find((c) => c.em_uso) || mail.contas.contas[0];
  const titulo = nome || String(caminho).split(/[\\/]/).pop();
  telaEscrever({ assunto: titulo.replace(/\.pdf$/i, ""), corpo: "" });
  mail.anexos = [{ path: caminho, nome: titulo, mb: 0 }];
  desenharAnexos();
}

/* O "..." de um PDF (na lista da Assinatura): o que se faz com o arquivo. */
function menuDoPdf(botao, p, depoisDeApagar) {
  menuNaLinha(botao, [
    { rotulo: "Assinar", acao: () => mostrarAssinar(p.path) },
    { rotulo: "Verificar assinatura", acao: () => abrirVerificacao(p.path, p.nome) },
    "-",
    { rotulo: "Abrir no Windows", acao: () => abrirNoWindows(p.path) },
    { rotulo: "Baixar", acao: () => baixarArquivo(p.path) },
    { rotulo: "Enviar por e-mail", acao: () => compartilharPorEmail(p.path, p.nome) },
    "-",
    { rotulo: "Apagar do acervo", perigo: true, acao: () => apagarPdf(p, depoisDeApagar) },
  ]);
}

/* Apagar passa por Aprovações, como no Acervo: o arquivo sai do disco sem
   lixeira, então nada some antes do sim. */
async function apagarPdf(p, depois) {
  const ok = await confirmar({
    titulo: "Apagar este PDF?", contexto: p.nome,
    texto: "O arquivo é apagado do disco e não vai para a lixeira. O pedido vai para Aprovações e nada é apagado antes do seu sim lá.",
    confirmar: "Apagar", perigo: true,
  });
  if (!ok) return;
  const r = await fetch("/api/biblioteca/lote/apagar", {
    method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ caminhos: [p.path], destino: "" }),
  });
  if (!r.ok) { avisoCert(await erroDe(r)); return; }
  const d = await r.json();
  if (!d.pedido) { avisoCert(d.aviso || "esse arquivo não pode ser apagado daqui"); return; }
  avisoCert("o pedido para apagar foi para Aprovações — confirme lá");
  if (depois) depois();
}
