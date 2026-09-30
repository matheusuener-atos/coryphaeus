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

const cap = { fotos: [] };

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

function previaDasFotos() {
  return '<div class="cap-fotos">' + cap.fotos.map((f, i) =>
    '<figure class="cap-foto"><img src="' + f.url + '" alt="página ' + (i + 1) + '" style="transform: rotate(' + f.giro + 'deg)">' +
    "<figcaption>página " + (i + 1) +
    '<span><button type="button" data-cap-girar="' + i + '" title="Girar">' + ic("refresh", 16) + "</button>" +
    '<button type="button" data-cap-tirar="' + i + '" title="Tirar esta página">' + ic("delete", 16) + "</button></span></figcaption></figure>").join("") +
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
  };
  const ligar = () => {
    const veu = $("veu-dialogo");
    if (!veu) return;
    veu.querySelectorAll("[data-cap-girar]").forEach((b) => { b.onclick = () => { const f = cap.fotos[Number(b.dataset.capGirar)]; f.giro = (f.giro + 90) % 360; redesenhar(); }; });
    veu.querySelectorAll("[data-cap-tirar]").forEach((b) => { b.onclick = () => { const [f] = cap.fotos.splice(Number(b.dataset.capTirar), 1); URL.revokeObjectURL(f.url); redesenhar(); }; });
    veu.querySelectorAll("[data-cap-mais]").forEach((b) => { b.onclick = () => escolherFotos(redesenhar); });
  };
  const aviso = '<p class="dialogo-dica" id="cap-erro" hidden></p>';
  const r = dialogo({
    titulo: "Fotografar documento", contexto: "Acervo", larga: true,
    texto: "Confira cada página: gire a que estiver deitada e tire a que saiu tremida. As fotos viram um PDF, e o texto é lido da imagem (pode ter erro de leitura).",
    campo: { chave: "titulo", rotulo: "Nome do documento", placeholder: "Intimação da audiência", obrigatorio: false },
    depois: '<div class="cap-previa">' + previaDasFotos() + "</div>" + aviso,
    confirmar: "Guardar no Acervo",
    aoConfirmar: async () => {
      if (!cap.fotos.length) return;
      const veu = $("veu-dialogo");
      const corpo = new FormData();
      cap.fotos.forEach((f, i) => corpo.append("fotos", f.arquivo, f.arquivo.name || "pagina-" + (i + 1) + ".jpg"));
      corpo.append("giros", JSON.stringify(cap.fotos.map((f) => f.giro)));
      corpo.append("titulo", (veu.querySelector("#dialogo-campo") || {}).value || "");
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
      avisoCert(d.destino === "aprovacoes"
        ? "“" + d.nome + "” foi para Aprovações: entra no Acervo quando o escritório confirmar"
        : "“" + d.nome + "” entrou no Acervo (" + plural(d.paginas, "página") + "); o texto está sendo lido", { tom: "ok" });
      if (d.destino === "acervo" && typeof mostrarBiblioteca === "function" && bib.visao === "documentos") mostrarBiblioteca();
    },
  });
  ligar();
  const fim = await r;
  if (fim === null) limparFotos();
}
