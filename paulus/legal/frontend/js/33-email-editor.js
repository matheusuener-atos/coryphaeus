/* ------------------------------------------------- e-mail: faixa de edicao */
/*
   O texto do e-mail com formatacao: a mesma faixa do editor de documentos
   (.docs-barra, 10-documentos.css) em cima de um campo editavel. Serve o
   Escrever, a resposta na caixa e a assinatura em Configuracoes.

     editorRico({ id, html, texto, placeholder, imagem, classe })
                               o HTML: a faixa e o campo. `imagem` poe o
                               botao de imagem (a assinatura); `texto` e o
                               conteudo inicial quando so ha texto puro
     ligarEditorRico(id, aoMudar)   liga a faixa; aoMudar() a cada mudanca

   O campo ganha `.value` (o texto puro, ler e escrever - e o que o resto do
   codigo ja usava na textarea) e `.html` (o texto formatado, que vai no
   envio como corpo_html). `readOnly` trava a edicao, como na textarea.

   Os comandos sao os do navegador (execCommand): negrito, listas, cor,
   tamanho... O HTML que sai e limpo de novo no servidor antes de ir embora
   (correio.limpar_html_escrito).
*/

const ER_FONTES = [
  { id: "sans", rotulo: "Sem serifa", valor: "Arial, Helvetica, sans-serif" },
  { id: "serifa", rotulo: "Serifada", valor: "Georgia, 'Times New Roman', serif" },
  { id: "mono", rotulo: "Monoespaçada", valor: "'Courier New', monospace" },
];
const ER_TAMANHOS = [
  { id: "2", rotulo: "Pequeno" }, { id: "3", rotulo: "Normal" }, { id: "5", rotulo: "Grande" }, { id: "6", rotulo: "Enorme" },
];
// As cores que o destinatario ve: vao dentro do e-mail, nao seguem o tema.
const ER_CORES = [
  { rotulo: "Automática", valor: "" }, { rotulo: "Cinza", valor: "#5f6368" }, { rotulo: "Vermelho", valor: "#c5221f" },
  { rotulo: "Laranja", valor: "#e37400" }, { rotulo: "Verde", valor: "#188038" }, { rotulo: "Azul", valor: "#1a73e8" },
  { rotulo: "Roxo", valor: "#8430ce" },
];
// A imagem da assinatura: reduzida na maquina antes de entrar.
const ER_IMAGEM_LADO = 320;
const ER_IMAGEM_MAX = 150 * 1024;

function erTextoParaHtml(texto) {
  return String(texto || "").split("\n").map((l) => "<div>" + (esc(l) || "<br>") + "</div>").join("");
}

function editorRico(o) {
  const botao = (cmd, nome, titulo) => '<button type="button" data-er-cmd="' + cmd + '" title="' + titulo + '" aria-label="' + titulo + '">' + ic(nome, 18) + "</button>";
  const inicial = o.html || (o.texto ? erTextoParaHtml(o.texto) : "");
  return '<div class="er' + (o.classe ? " " + o.classe : "") + '" data-er="' + o.id + '">' +
    '<div class="docs-barra er-barra" role="toolbar" aria-label="Formatação">' +
    '<select class="docs-sel" data-er-fonte="1" title="Fonte">' + ER_FONTES.map((f) => '<option value="' + f.id + '">' + f.rotulo + "</option>").join("") + "</select>" +
    '<select class="docs-sel curta" data-er-tamanho="1" title="Tamanho">' + ER_TAMANHOS.map((t) => '<option value="' + t.id + '"' + (t.id === "3" ? " selected" : "") + ">" + t.rotulo + "</option>").join("") + "</select>" +
    '<span class="divisa-v"></span>' +
    botao("undo", "undo", "Desfazer") + botao("redo", "redo", "Refazer") +
    '<span class="divisa-v"></span>' +
    botao("bold", "format_bold", "Negrito") + botao("italic", "format_italic", "Itálico") +
    botao("underline", "format_underlined", "Sublinhado") + botao("strikeThrough", "strikethrough_s", "Tachado") +
    '<button type="button" class="er-cor" data-er-cor="1" title="Cor do texto" aria-label="Cor do texto"><span class="er-cor-letra">A</span><i class="er-cor-faixa"></i></button>' +
    '<span class="divisa-v"></span>' +
    botao("insertUnorderedList", "format_list_bulleted", "Lista") + botao("insertOrderedList", "format_list_numbered", "Numeração") +
    botao("indent", "format_indent_increase", "Recuar") + botao("citar", "format_quote", "Citação") +
    '<span class="divisa-v"></span>' +
    botao("link", "link", "Link") +
    (o.imagem ? '<button type="button" class="com-texto" data-er-imagem="1" title="Imagem pequena, como um logo">' + ic("upload", 16) + "Imagem</button>" : "") +
    '<button type="button" class="com-texto" data-er-cmd="removeFormat" title="Tirar a formatação do trecho">Limpar</button>' +
    "</div>" +
    '<div class="er-texto" id="' + o.id + '" contenteditable="true" role="textbox" aria-multiline="true" data-vazio="' + esc(o.placeholder || "") + '">' + inicial + "</div>" +
    (o.imagem ? '<input type="file" accept="image/png,image/jpeg,image/gif,image/webp" hidden data-er-arquivo="1">' : "") +
    "</div>";
}

/* O texto puro do campo: o mesmo que a textarea dava. */
function erTexto(el) {
  const copia = el.cloneNode(true);
  copia.querySelectorAll("br").forEach((b) => b.replaceWith("\n"));
  // Bloco (paragrafo, lista, citacao) comeca em linha nova quando ha algo antes.
  copia.querySelectorAll("div, p, ul, ol, li, blockquote, h1, h2, h3").forEach((b) => {
    if (b.previousSibling) b.before("\n");
  });
  copia.querySelectorAll("li").forEach((b) => b.prepend("- "));
  return copia.textContent.replace(/ /g, " ").replace(/\n{3,}/g, "\n\n").replace(/^\n+|\n+$/g, "");
}

function erVazio(el) { return !erTexto(el).trim() && !el.querySelector("img"); }

function ligarEditorRico(id, aoMudar) {
  const campo = document.getElementById(id);
  const raiz = campo && campo.closest(".er");
  if (!campo || !raiz) return null;
  // Ligar de novo o mesmo campo (a tela liga outra vez ao mudar um chip) so
  // troca quem ouve: os eventos ficam uma vez so.
  campo._erAoMudar = aoMudar;
  if (campo._erLigado) return campo;
  campo._erLigado = true;
  const mudou = () => { raiz.classList.toggle("vazio", erVazio(campo)); if (campo._erAoMudar) campo._erAoMudar(); };

  // O que o resto do codigo le e escreve, como numa textarea.
  Object.defineProperty(campo, "value", {
    configurable: true,
    get: () => erTexto(campo),
    set: (texto) => { campo.innerHTML = erTextoParaHtml(texto); raiz.classList.toggle("vazio", erVazio(campo)); },
  });
  Object.defineProperty(campo, "html", {
    configurable: true,
    get: () => (erVazio(campo) ? "" : campo.innerHTML),
    set: (html) => { campo.innerHTML = html || ""; raiz.classList.toggle("vazio", erVazio(campo)); },
  });
  Object.defineProperty(campo, "readOnly", {
    configurable: true,
    get: () => campo.getAttribute("contenteditable") === "false",
    set: (sim) => { campo.setAttribute("contenteditable", sim ? "false" : "true"); raiz.classList.toggle("travado", !!sim); },
  });
  campo.setSelectionRange = () => erCursorNoFim(campo);
  raiz.classList.toggle("vazio", erVazio(campo));

  try { document.execCommand("styleWithCSS", false, true); } catch (err) { /* navegador antigo: fica com tags */ }

  // A selecao some quando o foco vai para um menu da faixa: guarda e volta.
  let faixa = null;
  const guardar = () => {
    const sel = document.getSelection();
    if (sel && sel.rangeCount && campo.contains(sel.anchorNode)) faixa = sel.getRangeAt(0).cloneRange();
  };
  const voltar = () => {
    campo.focus();
    if (!faixa) return;
    const sel = document.getSelection();
    sel.removeAllRanges();
    sel.addRange(faixa);
  };
  const fazer = (cmd, valor) => {
    if (campo.readOnly) return;
    voltar();
    document.execCommand(cmd, false, valor);
    guardar();
    marcarEstados();
    mudou();
  };
  const marcarEstados = () => {
    raiz.querySelectorAll("[data-er-cmd]").forEach((b) => {
      const cmd = b.dataset.erCmd;
      if (!/^(bold|italic|underline|strikeThrough|insertUnorderedList|insertOrderedList)$/.test(cmd)) return;
      let ligado = false;
      try { ligado = document.queryCommandState(cmd); } catch (err) { ligado = false; }
      b.classList.toggle("on", ligado);
    });
  };

  campo.addEventListener("input", mudou);
  campo.addEventListener("keyup", () => { guardar(); marcarEstados(); });
  campo.addEventListener("mouseup", () => { guardar(); marcarEstados(); });
  campo.addEventListener("blur", guardar);
  // Colar traz so o texto: a formatacao de outro programa vem com estilos
  // que nao combinam com o e-mail. A formatacao se faz pela faixa.
  campo.addEventListener("paste", (e) => {
    const texto = e.clipboardData && e.clipboardData.getData("text/plain");
    if (texto === undefined || texto === null) return;
    e.preventDefault();
    document.execCommand("insertText", false, texto);
  });

  raiz.querySelectorAll("[data-er-cmd]").forEach((b) => {
    b.onmousedown = (e) => e.preventDefault();
    b.onclick = () => {
      const cmd = b.dataset.erCmd;
      if (cmd === "citar") return fazer("formatBlock", "blockquote");
      if (cmd === "link") return erPedirLink(campo, voltar, fazer);
      fazer(cmd);
    };
  });

  const fonte = raiz.querySelector("[data-er-fonte]");
  const tamanho = raiz.querySelector("[data-er-tamanho]");
  if (fonte) fonte.onchange = () => fazer("fontName", (ER_FONTES.find((f) => f.id === fonte.value) || ER_FONTES[0]).valor);
  if (tamanho) tamanho.onchange = () => fazer("fontSize", tamanho.value);
  [fonte, tamanho].forEach((s) => { if (s && typeof melhorarSelect === "function") melhorarSelect(s); });

  const cor = raiz.querySelector("[data-er-cor]");
  if (cor) {
    cor.onmousedown = (e) => e.preventDefault();
    cor.onclick = (e) => {
      e.stopPropagation();
      menuNaLinha(cor, ER_CORES.map((c) => ({
        rotulo: c.rotulo,
        acao: () => {
          if (c.valor) fazer("foreColor", c.valor);
          else fazer("removeFormat");
          const faixaCor = cor.querySelector(".er-cor-faixa");
          if (faixaCor) faixaCor.style.background = c.valor || "";
        },
      })));
    };
  }

  const imagem = raiz.querySelector("[data-er-imagem]");
  const arquivo = raiz.querySelector("[data-er-arquivo]");
  if (imagem && arquivo) {
    imagem.onmousedown = (e) => e.preventDefault();
    imagem.onclick = () => { guardar(); arquivo.value = ""; arquivo.click(); };
    arquivo.onchange = async () => {
      const f = arquivo.files && arquivo.files[0];
      if (!f) return;
      const url = await erImagemPequena(f);
      if (!url) return;
      fazer("insertImage", url);
    };
  }
  return campo;
}

function erCursorNoFim(campo) {
  campo.focus();
  const faixa = document.createRange();
  faixa.selectNodeContents(campo);
  faixa.collapse(false);
  const sel = document.getSelection();
  sel.removeAllRanges();
  sel.addRange(faixa);
}

async function erPedirLink(campo, voltar, fazer) {
  const sel = document.getSelection();
  const temTexto = sel && sel.rangeCount && !sel.isCollapsed && campo.contains(sel.anchorNode);
  const endereco = await perguntar({
    titulo: "Pôr um link", contexto: temTexto ? "no trecho selecionado" : "o endereço entra no texto",
    campo: { rotulo: "Endereço", valor: "https://", icone: "link" }, confirmar: "Pôr link",
  });
  if (!endereco || !/^(https?:\/\/|mailto:)\S+$/i.test(endereco.trim())) {
    if (endereco) avisoCert("o link precisa começar com https:// ou mailto:");
    return;
  }
  if (temTexto) fazer("createLink", endereco.trim());
  else { voltar(); document.execCommand("insertHTML", false, '<a href="' + esc(endereco.trim()) + '">' + esc(endereco.trim()) + "</a>"); }
}

/* Reduz a imagem na maquina (lado maior ate ER_IMAGEM_LADO) e devolve como
   data: - o servidor a embute no e-mail como anexo interno. */
function erImagemPequena(arquivo) {
  return new Promise((pronto) => {
    const leitor = new FileReader();
    leitor.onerror = () => { avisoCert("não consegui ler a imagem"); pronto(""); };
    leitor.onload = () => {
      const img = new Image();
      img.onerror = () => { avisoCert("esse arquivo não parece uma imagem"); pronto(""); };
      img.onload = () => {
        const escala = Math.min(1, ER_IMAGEM_LADO / Math.max(img.width, img.height));
        const tela = document.createElement("canvas");
        tela.width = Math.max(1, Math.round(img.width * escala));
        tela.height = Math.max(1, Math.round(img.height * escala));
        tela.getContext("2d").drawImage(img, 0, 0, tela.width, tela.height);
        let url = tela.toDataURL("image/png");
        if (url.length * 0.75 > ER_IMAGEM_MAX) url = tela.toDataURL("image/jpeg", 0.85);
        if (url.length * 0.75 > ER_IMAGEM_MAX) { avisoCert("a imagem ficou grande demais mesmo reduzida - use uma mais simples"); pronto(""); return; }
        pronto(url);
      };
      img.src = leitor.result;
    };
    leitor.readAsDataURL(arquivo);
  });
}
