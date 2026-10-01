/* ------------------------------------------------------------ captura */
/*
   Fotografar um documento (ideia E do umbrelOS, docs/DECISAO-UMBREL.md,
   src/captura.py). No celular, o campo de arquivo com `capture` abre a
   câmera; no computador, o seletor de imagens. Várias páginas, a prévia com
   girar e tirar, e confirmar: as fotos viram um PDF, uma página por foto, e
   o PDF passa pelo OCR de sempre.

   De fora (pelo celular), a foto não entra direto no Acervo: vai para
   Aprovações, e entra quando o escritório confirmar. A tela diz qual dos dois
   aconteceu.
*/

const cap = { fotos: [], servicos: null };

/* L8: a nitidez e a luz de cada foto nova, antes de guardar (src/captura.py). */
async function conferirFotos() {
  const novas = cap.fotos.filter((f) => !f.q && !f.conferindo);
  if (!novas.length) return;
  novas.forEach((f) => { f.conferindo = true; });
  const corpo = new FormData();
  novas.forEach((f, i) => corpo.append("fotos", f.arquivo, f.arquivo.name || "pagina-" + (i + 1) + ".jpg"));
  try {
    const r = await fetch("/api/captura/conferir", { method: "POST", body: corpo });
    const d = r.ok ? await r.json() : { fotos: [] };
    novas.forEach((f, i) => { f.q = d.fotos[i] || {}; f.conferindo = false; });
  } catch (err) { novas.forEach((f) => { f.conferindo = false; f.q = {}; }); }
}

function avisoDaFoto(f) {
  const q = f.q || {};
  if (q.borrada) return '<p class="cap-alerta">tremida ou fora de foco — fotografe de novo</p>';
  if (q.escura) return '<p class="cap-alerta">escura — mais luz ajuda a leitura</p>';
  return "";
}

async function servicosParaCaptura() {
  if (cap.servicos) return cap.servicos;
  try { cap.servicos = ((await (await fetch("/api/servicos?filtro=andamento")).json()).servicos) || []; } catch (err) { cap.servicos = []; }
  return cap.servicos;
}

function botaoFotografar() {
  return (window.PAULUS_UMBREL || {}).captura
    ? '<button class="com-icone" id="bib-fotografar" title="Fotografar um documento de papel">' + ic("photo_camera", 16) + "Fotografar</button>"
    : "";
}

function escolherFotos(depois) {
  const campo = document.createElement("input");
  campo.type = "file";
  campo.accept = "image/*";
  campo.multiple = true;
  campo.setAttribute("capture", "environment");
  campo.onchange = () => {
    Array.from(campo.files || []).forEach((f) => cap.fotos.push({ arquivo: f, url: URL.createObjectURL(f), giro: 0 }));
    depois();
  };
  campo.click();
}

/* N10: a folha achada na foto - o contorno por cima da prévia e o "cortar",
   ligado quando a folha foi achada. O corte de verdade é refeito no servidor. */
function cortaraFoto(f) {
  return Boolean(f.q && f.q.folha && f.q.folha.achou && f.cortar !== false);
}

function imagemDaPrevia(f, i) {
  const folha = (f.q || {}).folha || {};
  if (!folha.achou || !folha.largura) {
    return '<img src="' + f.url + '" alt="página ' + (i + 1) + '" style="transform: rotate(' + f.giro + 'deg)">';
  }
  const pontos = folha.cantos.map((c) => c[0] + "," + c[1]).join(" ");
  return '<div class="cap-quadro" style="aspect-ratio: ' + folha.largura + " / " + folha.altura + "; transform: rotate(" + f.giro + 'deg)">' +
    '<img src="' + f.url + '" alt="página ' + (i + 1) + '">' +
    (cortaraFoto(f) ? '<svg viewBox="0 0 1 1" preserveAspectRatio="none" aria-hidden="true"><polygon points="' + pontos + '"></polygon></svg>' : "") + "</div>";
}

function notaDoCorte(f) {
  const folha = (f.q || {}).folha;
  if (!folha) return "";
  if (folha.achou) {
    return '<button type="button" class="cap-cortar' + (cortaraFoto(f) ? " on" : "") + '" data-cap-cortar="' + cap.fotos.indexOf(f) + '">' +
      ic(cortaraFoto(f) ? "check" : "close", 14) + (cortaraFoto(f) ? "corta e endireita" : "vai como veio") + "</button>";
  }
  return folha.motivo ? '<p class="cap-nota">' + esc(folha.motivo) + "</p>" : "";
}

function previaDasFotos() {
  return '<div class="cap-fotos">' + cap.fotos.map((f, i) =>
    '<figure class="cap-foto">' + imagemDaPrevia(f, i) +
    "<figcaption>página " + (i + 1) +
    '<span><button type="button" data-cap-girar="' + i + '" title="Girar">' + ic("refresh", 16) + "</button>" +
    '<button type="button" data-cap-tirar="' + i + '" title="Tirar esta página">' + ic("delete", 16) + "</button></span></figcaption>" +
    avisoDaFoto(f) + notaDoCorte(f) + "</figure>").join("") +
    '<button type="button" class="cap-mais" data-cap-mais="1">' + ic("add", 18) + "mais uma página</button></div>";
}

function limparFotos() {
  cap.fotos.forEach((f) => URL.revokeObjectURL(f.url));
  cap.fotos = [];
}

async function fotografarDocumento() {
  if (!cap.fotos.length) {
    await new Promise((pronto) => escolherFotos(pronto));
    if (!cap.fotos.length) return;
  }
  const redesenhar = () => {
    const caixa = document.querySelector("#veu-dialogo .cap-previa");
    if (caixa) { caixa.innerHTML = previaDasFotos(); ligar(); }
    // As fotos novas são conferidas; quando a conta volta, a prévia mostra o aviso.
    if (cap.fotos.some((f) => !f.q)) conferirFotos().then(() => { const c = document.querySelector("#veu-dialogo .cap-previa"); if (c) { c.innerHTML = previaDasFotos(); ligar(); } });
  };
  const ligar = () => {
    const veu = $("veu-dialogo");
    if (!veu) return;
    veu.querySelectorAll("[data-cap-girar]").forEach((b) => { b.onclick = () => { const f = cap.fotos[Number(b.dataset.capGirar)]; f.giro = (f.giro + 90) % 360; redesenhar(); }; });
    veu.querySelectorAll("[data-cap-tirar]").forEach((b) => { b.onclick = () => { const [f] = cap.fotos.splice(Number(b.dataset.capTirar), 1); URL.revokeObjectURL(f.url); redesenhar(); }; });
    veu.querySelectorAll("[data-cap-mais]").forEach((b) => { b.onclick = () => escolherFotos(redesenhar); });
    veu.querySelectorAll("[data-cap-cortar]").forEach((b) => { b.onclick = () => { const f = cap.fotos[Number(b.dataset.capCortar)]; f.cortar = !cortaraFoto(f); redesenhar(); }; });
  };
  const aviso = '<p class="dialogo-dica" id="cap-erro" hidden></p>';
  const servicos = await servicosParaCaptura();
  const destino = servicos.length
    ? '<div class="ag-campo"><label for="cap-servico">Guardar em</label><select id="cap-servico"><option value="">o Acervo</option>' +
      servicos.map((s) => '<option value="' + s.id + '">o Serviço “' + esc(s.nome) + "”</option>").join("") + "</select></div>"
    : "";
  const r = dialogo({
    titulo: "Fotografar documento", contexto: "Acervo", larga: true,
    texto: "Confira cada página: gire a que estiver deitada e tire a que saiu tremida. As fotos viram um PDF, e o texto é lido da imagem (pode ter erro de leitura).",
    campo: { chave: "titulo", rotulo: "Nome do documento", placeholder: "Intimação da audiência", obrigatorio: false },
    depois: destino + '<div class="cap-previa">' + previaDasFotos() + "</div>" + aviso,
    confirmar: "Guardar no Acervo",
    aoConfirmar: async () => {
      if (!cap.fotos.length) return;
      const veu = $("veu-dialogo");
      const corpo = new FormData();
      cap.fotos.forEach((f, i) => corpo.append("fotos", f.arquivo, f.arquivo.name || "pagina-" + (i + 1) + ".jpg"));
      corpo.append("giros", JSON.stringify(cap.fotos.map((f) => f.giro)));
      corpo.append("cortes", JSON.stringify(cap.fotos.map((f) => cortaraFoto(f))));
      corpo.append("titulo", (veu.querySelector("#dialogo-campo") || {}).value || "");
      corpo.append("servico_id", (veu.querySelector("#cap-servico") || {}).value || "");
      const botao = veu.querySelector('[data-dialogo="confirmar"]');
      botao.disabled = true;
      botao.textContent = "guardando…";
      const resp = await fetch("/api/captura", { method: "POST", body: corpo });
      if (!resp.ok) {
        const erro = veu.querySelector("#cap-erro");
        erro.textContent = await erroDe(resp);
        erro.hidden = false;
        botao.disabled = false;
        botao.textContent = "Guardar no Acervo";
        return;
      }
      const d = await resp.json();
      limparFotos();
      if (dialogoAberto) dialogoAberto.fechar(null);
      const l = d.leitura || {};
      const leu = l.lido ? "li " + milhar(l.caracteres) + " caracteres" + (l.ocr_paginas ? " (" + plural(l.ocr_paginas, "página") + " pela leitura da imagem)" : "")
        : "não li texto: " + (l.motivo || "confira as fotos");
      avisoCert(d.destino === "aprovacoes"
        ? "“" + d.nome + "” foi para Aprovações: entra " + (d.servico_id ? "no Serviço" : "no Acervo") + " quando o escritório confirmar"
        : "“" + d.nome + "” entrou " + (d.servico_id ? "no Serviço" : "no Acervo") + " (" + plural(d.paginas, "página") +
          (d.cortadas ? ", " + plural(d.cortadas, "endireitada", "endireitadas") : "") + "); " + leu, { tom: l.lido || d.destino === "aprovacoes" ? "ok" : "" });
      if (d.destino === "acervo" && typeof mostrarBiblioteca === "function" && bib.visao === "documentos") mostrarBiblioteca();
    },
  });
  ligar();
  redesenhar();
  const fim = await r;
  if (fim === null) limparFotos();
}
