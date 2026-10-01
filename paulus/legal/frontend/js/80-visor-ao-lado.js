/* -------------------------------------- o documento ao lado da conversa */
/*
   Pacote de telas de 01/10/2026 (docs/PLANO-TELAS-ASSISTENTE.md, T3):
   `Conversa - Documento` e `Conversa - PDF`. "Mostrar aqui" abre o documento
   na coluna da direita, como ferramenta (a conversa fica com 560 px): o
   nome com o formato, "só leitura · N páginas · K trechos citados", No
   Windows, Abrir editor (e Assinar, no PDF), e embaixo o quadro com as
   paginas de verdade - o PDF desenhado do arquivo; o Word, do PDF que o
   gerador do editor monta.

   Os trechos citados ficam marcados NA FRASE (src/citacao.py procura cada
   um no PDF desenhado), e a barra anda de um para o outro: "1 de 2". A lupa
   procura no documento e marca os achados do mesmo jeito. O trecho que nao
   se acha no arquivo fica so com a pagina - melhor sem marca do que marca no
   lugar errado.

   So leitura: nada e copiado nem gravado. Fechar (o X) devolve a coluna ao
   contexto da resposta.
*/

const va = {
  reg: null,        // o que /api/biblioteca/leitura (ou /fazer exibir) devolveu
  escala: 100,
  marca: 0,         // o trecho citado em foco
  busca: null,      // { termo, achados: [{pagina, marcas}], atual }
  oferta: null,     // a caixa do cartao "quer ver o documento?", para marcar o botao
  oferta_d: null,
  quadro: 0,
};

const VA_ESCALAS = [50, 67, 75, 90, 100, 110, 125, 150, 175, 200];

function extensaoDe(nome) {
  const m = /\.([a-z0-9]{1,5})$/i.exec(nome || "");
  return m ? m[1].toLowerCase() : "";
}

function nomeSemExtensao(nome) {
  const ext = extensaoDe(nome);
  return ext ? String(nome).slice(0, -(ext.length + 1)) : String(nome || "");
}

/* O cabecalho de toda ferramenta da coluna: a marca do formato (32 px), o
   nome com a extensao apagada em monoespaco, a linha de baixo e os botoes. */
function topoDaFerramenta(o) {
  const ext = o.extensao !== undefined ? o.extensao : extensaoDe(o.nome);
  const marca = o.marca || ("<span class=\"fl-marca " + (["pdf", "docx", "doc", "xlsx", "xls"].includes(ext) ? ext : "outro") + "\">" +
    (ext === "pdf" ? "PDF" : (ext === "docx" || ext === "doc") ? "W" : (ext === "xlsx" || ext === "xls") ? "X" : ic("description", 18)) + "</span>");
  return '<div class="fl-topo">' + marca +
    '<div class="fl-nome"><b title="' + esc(o.nome) + '"><span class="corta">' + (o.tituloHtml || esc(nomeSemExtensao(o.nome))) + "</span>" +
    (ext ? '<span class="fl-ext">.' + esc(ext) + "</span>" : "") + (o.depoisDoNome || "") + "</b>" +
    (o.linhaHtml || "<small>" + esc(o.linha || "") + "</small>") + "</div>" +
    '<div class="fl-acoes">' + (o.acoes || "") +
    '<button class="botao-icone" data-fl="mais" title="Mais" aria-label="Mais">' + ic("more_horiz", 18) + "</button>" +
    '<button class="botao-icone" data-fl="fechar" title="Fechar" aria-label="Fechar">' + ic("close", 18) + "</button></div></div>";
}

function botaoNoWindows() {
  return '<button data-fl="windows" title="Abrir no programa padrão do Windows">No Windows' + ic("open_in_new", 14) + "</button>";
}

function tamanhoCurto(bytes) {
  if (!bytes) return "";
  if (bytes < 1024 * 1024) return Math.max(1, Math.round(bytes / 1024)) + " KB";
  return (bytes / (1024 * 1024)).toFixed(1).replace(".", ",") + " MB";
}

function linhaDoVisor(reg) {
  const ext = extensaoDe(reg.nome);
  const partes = [ext === "pdf" ? "PDF" : "só leitura", plural(reg.paginas || 1, "página")];
  const n = (reg.marcas || []).length;
  if (n) partes.push(plural(n, "trecho citado", "trechos citados"));
  if (reg.assinado) partes.push("assinado digitalmente");
  return partes.join(" · ");
}

function pdfDoVisor(reg) {
  return extensaoDe(reg.nome) === "pdf";
}

/* ------------------------------------------------------------- abrir */

/* Abre o documento na coluna. `reg` e a leitura; `o.foco` e o trecho que
   abre em foco; `o.oferta`/`o.d` sao o cartao de onde veio o clique. */
function abrirDocumentoAoLado(reg, o) {
  const opcoes = o || {};
  va.reg = reg;
  va.escala = 100;
  va.busca = null;
  va.marca = Math.max(0, Math.min((reg.marcas || []).length - 1, opcoes.foco || 0));
  va.oferta = opcoes.oferta || null;
  va.oferta_d = opcoes.d || null;
  // A proxima pergunta le so este documento (a linha acima da caixa diz), e
  // a caixa pergunta sobre ele - como no desenho.
  definirFoco([reg.nome]);
  abrirNoLado("ferramenta", {
    chave: "visor:" + reg.nome,
    html: htmlDoVisor(reg),
    ligar: ligarVisorAoLado,
    aoFechar: () => {
      cancelAnimationFrame(va.quadro);
      if (va.oferta) marcarBotaoDaOferta(va.oferta, "", reg.nome);
      va.reg = null;
      atualizarPostura();
    },
  });
  if (va.oferta) marcarBotaoDaOferta(va.oferta, "exibir", reg.nome);
  atualizarPostura();
}

/* O botao do cartao que esta aberto ao lado fica cheio, com o visto; os
   outros voltam ao normal (pacote: "✓ Mostrar aqui" / "✓ Abrir editor"). */
function marcarBotaoDaOferta(caixa, qual, nome) {
  if (!caixa || !caixa.isConnected) return;
  caixa.querySelectorAll('[data-prop="exibir"], [data-prop="editar"], [data-prop="windows"]').forEach((b) => {
    if (nome && b.dataset.nome && b.dataset.nome !== nome) return;
    const ativo = Boolean(qual) && b.dataset.prop === qual;
    b.classList.toggle("feito", ativo);
    const visto = b.querySelector(".ic-visto");
    if (ativo && !visto) b.insertAdjacentHTML("afterbegin", '<span class="ic ic-14 ic-visto">check</span>');
    if (!ativo && visto) visto.remove();
  });
}

function htmlDoVisor(reg) {
  const pdf = pdfDoVisor(reg);
  const acoes = botaoNoWindows() +
    '<button class="' + (pdf ? "" : "primario") + '" data-fl="editar">Abrir editor</button>' +
    (pdf ? '<button class="primario" data-fl="assinar">Assinar</button>' : "");
  const paginas = reg.paginas || 1;
  let miniaturas = "";
  if (paginas > 1) {
    for (let n = 1; n <= paginas; n++) {
      miniaturas += '<button class="fl-mini" data-va-ir="' + n + '" title="Página ' + n + '">' +
        '<img loading="lazy" alt="" src="/api/biblioteca/pagina?nome=' + encodeURIComponent(reg.nome) + "&numero=" + n + '&largura=240">' +
        "<small>" + n + "</small></button>";
    }
  }
  let folhas = "";
  for (let n = 1; n <= paginas; n++) {
    folhas += '<div class="fl-folha" data-va-pagina="' + n + '"><img alt="página ' + n + '" data-va-img="' + n + '"></div>';
  }
  const pe = [plural(paginas, "página"), pdf ? tamanhoCurto(reg.bytes) : (reg.palavras ? plural(reg.palavras, "palavra") : "")].filter(Boolean).join(" · ");
  return '<div class="fl" data-fl-tipo="visor">' +
    topoDaFerramenta({ nome: reg.nome, linha: linhaDoVisor(reg), acoes: acoes }) +
    '<div class="fl-quadro">' +
    '<div class="fl-barra" id="va-barra"></div>' +
    '<div class="fl-mesa' + (miniaturas ? " com-miniaturas" : "") + '">' +
    (miniaturas ? '<div class="fl-miniaturas" id="va-miniaturas">' + miniaturas + "</div>" : "") +
    '<div class="fl-folhas" id="va-folhas">' + folhas + "</div></div>" +
    '<div class="fl-pe"><span>' + esc(pe) + '</span><span class="fl-pe-nota">o arquivo original não é alterado</span></div>' +
    "</div></div>";
}

/* A barra do quadro: os trechos citados (ou os achados da lupa) com o
   "k de n", a pagina, a lupa e o zoom. */
function desenharBarraDoVisor() {
  const barra = $("va-barra");
  if (!barra || !va.reg) return;
  const reg = va.reg;
  const marcas = reg.marcas || [];
  const passo = (atual, total, rotulo) =>
    '<span class="fl-passo"><button class="botao-icone" data-va="antes" aria-label="Anterior"' + (total < 2 ? " disabled" : "") + ">" + ic("chevron_left", 16) + "</button>" +
    '<span class="fl-mono">' + (total ? atual + 1 : 0) + " de " + total + "</span>" +
    '<button class="botao-icone" data-va="depois" aria-label="Próximo"' + (total < 2 ? " disabled" : "") + ">" + ic("chevron_right", 16) + "</button></span>" +
    (rotulo || "");
  let esquerda = "";
  if (va.busca) {
    esquerda = '<label class="fl-busca">' + ic("search", 16) +
      '<input type="text" id="va-termo" placeholder="Procurar no documento" value="' + esc(va.busca.termo) + '">' +
      '<button class="botao-icone" data-va="sem-busca" aria-label="Fechar a busca">' + ic("close", 16) + "</button></label>" +
      (va.busca.achados ? passo(va.busca.atual, va.busca.achados.length) : "");
  } else if (marcas.length) {
    esquerda = '<span class="fl-cit"><i class="fl-cor"></i>Trechos citados</span>' + passo(va.marca, marcas.length);
  } else {
    esquerda = '<span class="fl-cit fl-cit-vazio">Sem trecho citado</span>';
  }
  const paginas = reg.paginas || 1;
  barra.innerHTML = esquerda + '<span class="cresce"></span>' +
    (paginas > 1 ? '<label class="fl-pag">Página <input type="text" inputmode="numeric" id="va-pagina" value="1" aria-label="Página"> de ' + paginas + "</label>" : "") +
    (va.busca ? "" : '<button class="botao-icone" data-va="lupa" title="Procurar no documento" aria-label="Procurar no documento">' + ic("search", 16) + "</button>") +
    '<span class="divisa-v"></span>' +
    '<span class="fl-zoom"><button class="botao-icone" data-va="menos" aria-label="Diminuir">' + ic("remove", 16) + "</button>" +
    '<span class="fl-mono">' + va.escala + "%</span>" +
    '<button class="botao-icone" data-va="mais" aria-label="Aumentar">' + ic("add", 16) + "</button></span>";
  ligarBarraDoVisor();
  atualizarPaginaDoVisor();
}

function ligarBarraDoVisor() {
  const barra = $("va-barra");
  const clique = (q, fn) => { const b = barra.querySelector('[data-va="' + q + '"]'); if (b) b.onclick = fn; };
  clique("antes", () => andarNoVisor(-1));
  clique("depois", () => andarNoVisor(1));
  clique("menos", () => zoomDoVisor(-1));
  clique("mais", () => zoomDoVisor(1));
  clique("lupa", () => { va.busca = { termo: "", achados: null, atual: 0 }; desenharBarraDoVisor(); $("va-termo").focus(); });
  clique("sem-busca", () => { va.busca = null; desenharBarraDoVisor(); desenharMarcasDoVisor(); });
  const termo = $("va-termo");
  if (termo) {
    termo.onkeydown = (e) => {
      if (e.key === "Enter") { e.preventDefault(); procurarNoVisor(termo.value); }
      if (e.key === "Escape") { va.busca = null; desenharBarraDoVisor(); desenharMarcasDoVisor(); }
    };
  }
  const pagina = $("va-pagina");
  if (pagina) {
    pagina.onkeydown = (e) => {
      if (e.key !== "Enter") return;
      e.preventDefault();
      const n = Math.max(1, Math.min(va.reg.paginas || 1, parseInt(pagina.value, 10) || 1));
      irParaPaginaDoVisor(n, true);
    };
    pagina.onfocus = () => pagina.select();
  }
}

/* ------------------------------------------------------- as paginas */

function larguraDaFolha() {
  const folhas = $("va-folhas");
  if (!folhas) return 0;
  const base = Math.min(900, Math.max(280, folhas.clientWidth - 64));
  return Math.round(base * va.escala / 100);
}

function desenharFolhasDoVisor() {
  const folhas = $("va-folhas");
  if (!folhas || !va.reg) return;
  const w = larguraDaFolha();
  const pedir = Math.min(1600, Math.max(400, Math.ceil(w * (window.devicePixelRatio || 1) / 100) * 100));
  folhas.querySelectorAll("[data-va-pagina]").forEach((f) => {
    f.style.width = w + "px";
    const img = f.querySelector("img");
    const src = "/api/biblioteca/pagina?nome=" + encodeURIComponent(va.reg.nome) + "&numero=" + f.dataset.vaPagina + "&largura=" + pedir;
    if (img.dataset.src !== src) {
      img.dataset.src = src;
      // A folha guarda a altura de A4 ate a pagina chegar: a rolagem nao pula.
      if (!img.complete || !img.naturalWidth) f.style.minHeight = Math.round(w * 297 / 210) + "px";
      img.onload = () => { f.style.minHeight = ""; };
      img.loading = Number(f.dataset.vaPagina) <= 2 ? "eager" : "lazy";
      img.src = src;
    }
  });
  desenharMarcasDoVisor();
}

/* As marcas: retangulos em fracao da pagina, sobre a imagem. */
function desenharMarcasDoVisor() {
  const folhas = $("va-folhas");
  if (!folhas || !va.reg) return;
  folhas.querySelectorAll(".fl-trecho").forEach((m) => m.remove());
  const desenhar = (lista, classe, atual) => lista.forEach((g, i) => {
    const folha = folhas.querySelector('[data-va-pagina="' + g.pagina + '"]');
    if (!folha) return;
    (g.marcas || []).forEach((r) => {
      const el = document.createElement("span");
      el.className = classe + (i === atual ? " atual" : "");
      el.dataset.vaMarca = i;
      el.style.left = (r.x * 100) + "%";
      el.style.top = (r.y * 100) + "%";
      el.style.width = (r.w * 100) + "%";
      el.style.height = (r.h * 100) + "%";
      folha.appendChild(el);
    });
  });
  if (va.busca && va.busca.achados) desenhar(va.busca.achados, "fl-trecho achado", va.busca.atual);
  else desenhar(va.reg.marcas || [], "fl-trecho", va.marca);
}

function rolagemDoVisor() {
  return $("va-folhas");
}

function irParaPaginaDoVisor(n, suave) {
  const folhas = rolagemDoVisor();
  const folha = folhas && folhas.querySelector('[data-va-pagina="' + n + '"]');
  if (!folha) return;
  folhas.scrollTo({ top: folha.offsetTop - 24, behavior: suave && animacoesLigadas() ? "smooth" : "auto" });
}

/* Leva o trecho (ou o achado) em foco ao meio da mesa. */
function irParaMarcaDoVisor(suave) {
  const lista = va.busca && va.busca.achados ? va.busca.achados : (va.reg.marcas || []);
  const atual = va.busca && va.busca.achados ? va.busca.atual : va.marca;
  const g = lista[atual];
  const folhas = rolagemDoVisor();
  if (!g || !folhas) return;
  const folha = folhas.querySelector('[data-va-pagina="' + g.pagina + '"]');
  if (!folha) return;
  const r = (g.marcas || [])[0];
  const altura = folha.offsetHeight || larguraDaFolha() * 297 / 210;
  const naFolha = r ? r.y * altura : 0;
  // Cabe com a pagina vista do alto: abre no alto dela, como no desenho.
  // Senao, o trecho vem para perto do meio.
  const alvo = naFolha < folhas.clientHeight * 0.7 ? folha.offsetTop - 24 : folha.offsetTop + naFolha - folhas.clientHeight * 0.35;
  folhas.scrollTo({ top: Math.max(0, alvo), behavior: suave && animacoesLigadas() ? "smooth" : "auto" });
}

function andarNoVisor(passo) {
  if (va.busca && va.busca.achados) {
    const n = va.busca.achados.length;
    if (!n) return;
    va.busca.atual = (va.busca.atual + passo + n) % n;
  } else {
    const n = (va.reg.marcas || []).length;
    if (!n) return;
    va.marca = (va.marca + passo + n) % n;
  }
  desenharBarraDoVisor();
  desenharMarcasDoVisor();
  irParaMarcaDoVisor(true);
}

function zoomDoVisor(passo) {
  const i = VA_ESCALAS.indexOf(va.escala);
  const novo = VA_ESCALAS[Math.max(0, Math.min(VA_ESCALAS.length - 1, (i < 0 ? 4 : i) + passo))];
  if (novo === va.escala) return;
  // Mantem a mesma altura relativa da rolagem: o que estava no meio continua.
  const folhas = rolagemDoVisor();
  const proporcao = folhas && folhas.scrollHeight ? (folhas.scrollTop + folhas.clientHeight / 2) / folhas.scrollHeight : 0;
  va.escala = novo;
  desenharBarraDoVisor();
  desenharFolhasDoVisor();
  if (folhas) folhas.scrollTop = proporcao * folhas.scrollHeight - folhas.clientHeight / 2;
}

/* A pagina que esta no meio da mesa: o campo "Página" e a miniatura. */
function atualizarPaginaDoVisor() {
  const folhas = rolagemDoVisor();
  if (!folhas) return;
  const meio = folhas.scrollTop + folhas.clientHeight * 0.4;
  let n = 1;
  folhas.querySelectorAll("[data-va-pagina]").forEach((f) => { if (f.offsetTop <= meio) n = Number(f.dataset.vaPagina); });
  const campo = $("va-pagina");
  if (campo && document.activeElement !== campo) campo.value = n;
  const minis = $("va-miniaturas");
  if (minis) {
    minis.querySelectorAll("[data-va-ir]").forEach((b) => b.classList.toggle("atual", Number(b.dataset.vaIr) === n));
  }
}

async function procurarNoVisor(termo) {
  const t = String(termo || "").trim();
  if (!va.reg || t.length < 2) return;
  const nome = va.reg.nome;
  va.busca = { termo: t, achados: null, atual: 0 };
  const r = await fetch("/api/biblioteca/procurar-no-documento", {
    method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ nome: nome, termo: t }),
  }).catch(() => null);
  if (!va.reg || va.reg.nome !== nome || !va.busca) return;
  if (!r || !r.ok) { avisoNaJanela("Não consegui procurar: " + (r ? await erroDe(r) : "sem resposta do servidor"), { icone: "error" }); return; }
  va.busca.achados = (await r.json()).achados || [];
  desenharBarraDoVisor();
  desenharMarcasDoVisor();
  if (va.busca.achados.length) irParaMarcaDoVisor(true);
  else avisoNaJanela("Não achei “" + t + "” neste documento");
  const campo = $("va-termo");
  if (campo) campo.focus();
}

/* ------------------------------------------------------------ ligar */

function ligarVisorAoLado(raiz) {
  const reg = va.reg;
  desenharBarraDoVisor();
  desenharFolhasDoVisor();
  // A coluna ainda esta se alargando: a largura da folha se acerta no fim.
  setTimeout(() => { if (va.reg === reg) { desenharFolhasDoVisor(); irParaMarcaDoVisor(false); } }, LADO_DURA_MS + 40);
  irParaMarcaDoVisor(false);

  const folhas = rolagemDoVisor();
  folhas.onscroll = () => {
    cancelAnimationFrame(va.quadro);
    va.quadro = requestAnimationFrame(atualizarPaginaDoVisor);
  };
  raiz.querySelectorAll("[data-va-ir]").forEach((b) => { b.onclick = () => irParaPaginaDoVisor(Number(b.dataset.vaIr), true); });

  const acao = (q, fn) => { const b = raiz.querySelector('[data-fl="' + q + '"]'); if (b) b.onclick = () => fn(b); };
  acao("fechar", () => voltarAoContexto());
  acao("windows", async (b) => {
    b.disabled = true;
    const r = await fetch("/api/trabalhos/" + estado.trabalhoId + "/fazer", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ tipo: "abrir", campos: { nome: reg.nome } }),
    }).catch(() => null);
    b.disabled = false;
    if (!r || !r.ok) { avisoNaJanela("Não consegui abrir: " + (r ? await erroDe(r) : "sem resposta"), { icone: "error" }); return; }
    avisoNaJanela("Abri no programa padrão do Windows");
  });
  acao("editar", () => editarDocumentoDoAcervo(reg.nome, va.oferta));
  acao("assinar", () => {
    if (!reg.caminho) { avisoNaJanela("Não achei o arquivo para assinar", { icone: "error" }); return; }
    if (typeof assinarAoLado === "function") { assinarAoLado(reg); return; }
    marcarDestino("assinar");
    mostrarAssinar(reg.caminho);
  });
  acao("mais", (b) => menuNaLinha(b, [
    { rotulo: "Procurar no documento", acao: () => { va.busca = { termo: "", achados: null, atual: 0 }; desenharBarraDoVisor(); $("va-termo").focus(); } },
    { rotulo: "Ver no Acervo", acao: () => verNoAcervo(reg.nome) },
  ]));
}

if (window.ResizeObserver) {
  let ultimo = 0;
  new ResizeObserver(() => {
    const folhas = $("va-folhas");
    if (!folhas || !va.reg) return;
    const w = folhas.clientWidth;
    if (Math.abs(w - ultimo) < 8) return;
    ultimo = w;
    desenharFolhasDoVisor();
  }).observe($("lado-ferramenta"));
}

/* Abrir para editar: o rascunho editavel do documento, ligado a conversa
   (o original nao e tocado). O mesmo do botao do cartao. */
async function editarDocumentoDoAcervo(nome, oferta) {
  const r = await fetch("/api/documentos/importar", {
    method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ nome: nome, trabalho_id: estado.trabalhoId || "" }),
  });
  if (!r.ok) {
    avisoNaJanela("Não consegui abrir no editor: " + (await erroDe(r)), { icone: "error" });
    return null;
  }
  const novo = await r.json();
  if (!novo.reaberto && estado.trabalho) {
    estado.trabalho.mensagens.push({ autor: "paulus", texto: "Abri “" + novo.de + "” para editar.",
      feito: { tipo: "editar", id: novo.id, nome: novo.de } });
    notaDeFeitoNaConversa("Abri um rascunho editável ao lado. O original continua intacto no Acervo.");
  }
  if (novo.tipo === "planilha") await editarPlanilhaAoLado(novo.id, { oferta: oferta, nome: nome });
  else await mostrarDupla(novo.id, { oferta: oferta, nome: nome });
  return novo;
}

/* A nota do que foi feito num clique, logo abaixo, com o fio a esquerda. */
function notaDeFeitoNaConversa(texto) {
  if (!texto) return;
  const nota = document.createElement("div");
  nota.className = "resposta nota-feito";
  nota.innerHTML = '<div class="texto">' + esc(texto) + "</div>";
  $("centro").appendChild(nota);
  if (animacoesLigadas()) entraConteudo(nota);
  if (pertoDoFim()) rolar();
}

/* O trecho lido (cartao da coluna, [T1] da resposta): o documento abre ao
   lado, nesse trecho, sem anotar nada na conversa. */
async function verTrechoAoLado(f) {
  if (!f || !f.documento || f.material) return;
  if (extensaoDe(f.documento) === "xlsx") { abrirPlanilhaAoLado(f.documento, { trechos: [f.texto || ""] }); return; }
  const r = await fetch("/api/biblioteca/leitura", {
    method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ nome: f.documento, trechos: [f.texto || ""] }),
  }).catch(() => null);
  if (!r || !r.ok) { avisoNaJanela("Não consegui abrir: " + (r ? await erroDe(r) : "sem resposta"), { icone: "error" }); return; }
  abrirDocumentoAoLado(await r.json(), { foco: 0 });
}
