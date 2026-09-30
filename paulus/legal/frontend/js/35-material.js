/* ------------------------------------------------------------ material */
/*
   Configurações › Aprendizado › Material de consulta (src/material.py).
   O escritório entrega um PDF - manual interno, tabela de honorários,
   doutrina - e o PAULUS passa a consultá-lo em cada pergunta da conversa,
   citando o material e a página.

   A tela diz o que acontece de verdade: o arquivo fica guardado nesta
   máquina, o texto é lido uma vez, e a consulta é por trecho. Não é treino
   do modelo; remover tira da consulta na hora. PDF escaneado passa pelo
   OCR do Windows (src/ocr_windows.py); o que nem assim vira texto volta com o motivo.

   Enviar e remover valem na hora: não passam pelo "Salvar alterações".
*/

const mat = { enviando: [] };

function dataCurtaMat(quando) {
  const s = String(quando || "");
  return s.length >= 10 ? s.slice(8, 10) + "/" + s.slice(5, 7) + "/" + s.slice(0, 4) : s;
}

function cartaoMaterial() {
  const d = cfg.material || { itens: [], trechos: 0 };
  const itens = d.itens || [];
  const linhas = itens.map((m) => {
    const f = m.ficha || null;
    const sub = [f ? resumoDaFicha(f) : "", m.paginas ? plural(m.paginas, "página") : "sem páginas", plural(m.trechos || 0, "trecho"),
      "entrou em " + dataCurtaMat(m.criado_em)].filter(Boolean).join(" · ");
    const conferir = f && !f.confirmada ? '<span class="etiqueta atencao">conferir a ficha</span>' : "";
    const aviso = (f && f.aviso ? '<span class="etiqueta">' + esc(f.aviso) + "</span>" : "") +
      (f && f.origem === "comunidade" ? '<span class="etiqueta" title="Veio de outro advogado; não foi revisado por este escritório">da comunidade</span>' : "");
    return '<div class="cfg-servico mat-linha"><span class="caixa-tipo">' + ic("menu_book", 18) + "</span>" +
      '<span class="duas-linhas cresce"><b>' + esc(f && f.titulo ? f.titulo : m.nome) + "</b><small>" + esc(sub) + "</small></span>" +
      conferir + aviso +
      '<button class="mais-linha" data-mat-mais="' + esc(m.id) + '" title="Mais" aria-label="Mais">' + ic("more_horiz", 18) + "</button></div>";
  }).join("");
  const enviando = mat.enviando.length;
  const solta = '<div class="cfg-solta" id="cfg-solta-material"><span class="duas-linhas"><b>' +
    (enviando ? "lendo " + (enviando === 1 ? "“" + esc(mat.enviando[0]) + "”" : plural(enviando, "arquivo")) + "…" : "Arraste PDFs, DOCX, TXT ou MD para cá") + "</b>" +
    "<small>o arquivo fica guardado nesta máquina e é consultado em cada pergunta</small></span>" +
    '<span class="cfg-botoes"><button data-mat-pacote="1" title="Um material que outro PAULUS exportou">' + ic("download", 16) + "Importar pacote</button>" +
    '<button class="primario com-icone" data-mat-escolher="1"' + (enviando ? " disabled" : "") + ">" +
    ic("upload", 16) + "Escolher arquivos</button></span></div>";
  return cartaoCfg("Material de consulta", metaCfg(itens.length ? plural(itens.length, "arquivo") + " · " + plural(d.trechos || 0, "trecho") : "o que eu consulto para responder"),
    (linhas ? '<div class="cfg-linhas">' + linhas + "</div>" : '<p class="nota">Nenhum material ainda.</p>') + solta +
    '<p class="cfg-explica">Em cada pergunta da conversa eu procuro aqui os trechos que têm a ver, leio junto com os documentos e cito o material e a página. ' +
    "Não é treino do modelo: o que você remover deixa de ser consultado na hora. PDF escaneado é lido pelo leitor de imagem do Windows, e o texto pode ter erro de leitura.</p>");
}

async function recarregarMaterial() {
  try {
    const r = await fetch("/api/material");
    cfg.material = r.ok ? await r.json() : cfg.material;
  } catch (err) { /* fica o que havia */ }
}

async function enviarMaterial(arquivos) {
  const lista = Array.from(arquivos || []);
  if (!lista.length || mat.enviando.length) return;
  mat.enviando = lista.map((a) => a.name);
  desenharConfig();
  const corpo = new FormData();
  lista.forEach((a) => corpo.append("arquivos", a, a.name));
  let r;
  try {
    r = await fetch("/api/material", { method: "POST", body: corpo });
  } catch (err) {
    r = null;
  }
  mat.enviando = [];
  if (!r) { avisoCert("não consegui enviar o arquivo", { tom: "erro" }); desenharConfig(); return; }
  if (!r.ok) { avisoCert(await erroDe(r), { tom: "erro" }); desenharConfig(); return; }
  const d = await r.json();
  cfg.material = d;
  const novos = (d.entraram || []).filter((x) => !x.ja_existia);
  const repetidos = (d.entraram || []).filter((x) => x.ja_existia);
  const partes = [];
  if (novos.length) partes.push(novos.length === 1 ? "“" + novos[0].nome + "” entrou no material" : plural(novos.length, "arquivo") + " entraram no material");
  if (repetidos.length) partes.push(repetidos.length === 1 ? "“" + repetidos[0].nome + "” já estava" : plural(repetidos.length, "arquivo") + " já estavam");
  /* A triagem da Biblioteca: o CDC em PDF foi para as leis em casa, e diz. */
  (d.avisos || []).forEach((x) => partes.push(x.mensagem));
  (d.recusados || []).forEach((x) => partes.push("“" + x.nome + "”: " + x.motivo));
  avisoCert(partes.join(" · "), { tom: (d.recusados || []).length ? "erro" : "ok" });
  desenharConfig();
  /* A ficha que a regra achou, para conferir ao entrar: o que a pessoa
     escreve vale sobre o que a regra achou. */
  const conferir = novos.find((x) => x.ficha && !x.ficha.confirmada);
  if (conferir) dialogoDaFicha(conferir);
}

/* ------------------------------------------- o que o PAULUS sabe (M7) */
/* A biblioteca por área: as obras (com a ficha), as leis instaladas e, por
   código, quantos artigos as obras do escritório comentam. É daqui que sai o
   aviso "Não tenho material de <área> na biblioteca" da conversa. */
function cartaoMapa() {
  const d = cfg.mapa;
  if (!d || !d.ligada) return "";
  const areas = (d.areas || []).map((a) =>
    '<div class="bib-area"><b>' + esc(a.area.charAt(0).toUpperCase() + a.area.slice(1)) + "</b>" +
    '<span class="bib-area-itens">' +
    (a.leis || []).map((l) => '<span class="etiqueta">' + esc(l.nome) + "</span>").join("") +
    (a.obras || []).map((o) => '<span class="etiqueta atencao" title="' + esc([o.tipo, o.autor, o.ano].filter(Boolean).join(" · ")) + '">' +
      esc(o.titulo) + "</span>").join("") + "</span></div>").join("");
  const semArea = (d.sem_area || []).length
    ? '<p class="cfg-explica">Sem área na ficha: ' + (d.sem_area || []).map((o) => esc(o.titulo)).join(", ") + ". Confira a ficha para eu saber de que área são.</p>" : "";
  const codigos = (d.codigos || []).map((c) =>
    '<div class="cfg-lei"><span class="duas-linhas"><b>' + esc(c.nome) + "</b><small>" +
    (c.anotados ? plural(c.anotados, "artigo") + " comentado" + (c.anotados === 1 ? "" : "s") + " pelas obras do escritório" +
      (c.mais_comentados && c.mais_comentados.length ? " · mais comentados: " + c.mais_comentados.slice(0, 5).map((m) => "art. " + esc(m.artigo)).join(", ") : "")
      : "nenhum artigo comentado pelas obras do escritório") + "</small></span></div>").join("");
  return cartaoCfg("O que eu sei", metaCfg(plural((d.areas || []).length, "área")),
    (areas ? '<div class="bib-areas">' + areas + "</div>" : '<p class="nota">Nenhuma área ainda: entregue um livro, um manual ou baixe um código de lei.</p>') + semArea +
    (codigos ? '<div class="cfg-linhas">' + codigos + "</div>" : "") +
    '<p class="cfg-explica">Quando a pergunta é de uma área que não está aqui, eu respondo pelos documentos e digo, no fim, que não tenho material dela. ' +
    (d.lembretes ? plural(d.lembretes, "lembrete") + " valem para toda pergunta, de qualquer área." : "") + "</p>");
}

/* ------------------------------------ o pacote .paulus-material (local) */
/* Levar um material a outro PAULUS: ficha, texto com as páginas e as
   anotações, num arquivo. Nada vai pela rede - é um arquivo que você leva.
   Só o autor exporta, e só depois de declarar e escolher a licença. */
const LICENCAS_PACOTE = ["CC BY 4.0", "CC BY-SA 4.0", "CC BY-NC 4.0", "Uso livre pelo escritório que importar, sem republicar"];

async function exportarPacote(m) {
  const f = m.ficha || {};
  if (!f.autoria_declarada || !LICENCAS_PACOTE.includes(f.licenca)) {
    const r = await dialogo({
      titulo: "Exportar “" + (f.titulo || m.nome) + "”", contexto: "Biblioteca · pacote .paulus-material",
      texto: "O pacote leva a ficha, o texto com as páginas e as anotações de artigos. Não leva o arquivo original nem nada do Acervo, e não vai pela rede: é um arquivo que você entrega.\nSó exporte o que é seu. Livro de editora não se exporta.",
      html: '<div class="dialogo-campo"><label for="pacote-licenca">Licença</label><div class="dialogo-caixa"><select id="pacote-licenca">' +
        LICENCAS_PACOTE.map((l) => '<option value="' + esc(l) + '">' + esc(l) + "</option>").join("") + "</select></div></div>",
      marcar: { rotulo: "Sou o autor deste material e posso compartilhá-lo", marcada: false },
      confirmar: "Declarar e exportar",
    });
    if (!r) return;
    if (!r.marcada) { avisoCert("para exportar, é preciso declarar que você é o autor", { tom: "erro" }); return; }
    const licenca = (document.getElementById("pacote-licenca") || {}).value || LICENCAS_PACOTE[0];
    const d = await fetch("/api/material/" + encodeURIComponent(m.id) + "/autoria", {
      method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ sou_autor: true, licenca: licenca }),
    });
    if (!d.ok) { avisoCert(await erroDe(d), { tom: "erro" }); return; }
    cfg.material = await d.json();
  }
  const r = await fetch("/api/material/" + encodeURIComponent(m.id) + "/pacote");
  if (!r.ok) { avisoCert(await erroDe(r), { tom: "erro" }); return; }
  const a = document.createElement("a");
  a.href = URL.createObjectURL(await r.blob());
  a.download = (f.titulo || m.nome).replace(/\.[A-Za-z0-9]{2,4}$/, "") + ".paulus-material";
  a.click();
  setTimeout(() => URL.revokeObjectURL(a.href), 2000);
  avisoCert("pacote pronto: “" + a.download + "”", { tom: "ok" });
  desenharConfig();
}

function importarPacote() {
  const campo = document.createElement("input");
  campo.type = "file";
  campo.accept = ".paulus-material";
  campo.onchange = async () => {
    const arquivo = campo.files && campo.files[0];
    if (!arquivo) return;
    const corpo = new FormData();
    corpo.append("arquivo", arquivo, arquivo.name);
    const r = await fetch("/api/material/pacote", { method: "POST", body: corpo });
    if (!r.ok) { avisoCert(await erroDe(r), { tom: "erro" }); return; }
    const d = await r.json();
    cfg.material = d;
    const s = (d.item && d.item.ficha && d.item.ficha.suspeitas) || [];
    avisoCert("“" + d.item.nome + "” entrou como material da comunidade, não revisado por este escritório" +
      (s.length ? " · atenção: o texto parece tentar dar ordens ao assistente (" + s.join("; ") + "); eu não sigo ordens escritas em material" : ""),
      { tom: s.length ? "erro" : "ok" });
    desenharConfig();
  };
  campo.click();
}

/* O glossário e as teses do autor (Biblioteca, M5): o que o modelo leu na
   obra e a frase do livro confirmou - cada item com a página. */
async function glossarioETeses(m) {
  let d;
  try {
    const r = await fetch("/api/material/" + encodeURIComponent(m.id) + "/leitura");
    if (!r.ok) { avisoCert(await erroDe(r), { tom: "erro" }); return; }
    d = await r.json();
  } catch (err) { avisoCert("não consegui abrir a leitura", { tom: "erro" }); return; }
  const pag = (x) => (x.pagina ? " <small>p. " + x.pagina + "</small>" : "");
  const conceitos = (d.conceitos || []).map((c) => '<li><b>' + esc(c.termo) + "</b>" + pag(c) + '<span class="bib-quote">“' + esc(c.quote) + "”</span></li>").join("");
  const teses = (d.posicoes || []).map((p) => "<li>" + esc(p.afirmacao) + pag(p) + '<span class="bib-quote">“' + esc(p.quote) + "”</span></li>").join("");
  const vazio = !d.ligada
    ? "A leitura das obras está desligada. Ela usa o modelo de leitura desta máquina, em segundo plano."
    : (d.andamento && d.andamento.andando ? "Estou lendo a obra agora (" + d.andamento.feitos + " de " + d.andamento.total + " trechos)." : "Ainda não li esta obra.");
  dialogo({
    titulo: "Glossário e teses", contexto: (m.ficha && m.ficha.titulo) || m.nome, larga: true,
    texto: "O modelo lê cada trecho e propõe; só fica o que a frase do livro confirma, com a página." + (d.modelo ? " Lido por " + d.modelo + "." : ""),
    html: (conceitos || teses)
      ? (conceitos ? '<h3 class="bib-titulo">Glossário</h3><ul class="bib-lista">' + conceitos + "</ul>" : "") +
        (teses ? '<h3 class="bib-titulo">Teses do autor</h3><ul class="bib-lista">' + teses + "</ul>" : "")
      : '<p class="nota">' + esc(vazio) + "</p>",
    confirmar: "Fechar", semCancelar: true,
  });
}

/* ------------------------------------------------ a ficha (Biblioteca, M2) */

const ROTULO_TIPO_MAT = { doutrina: "Doutrina", manual: "Manual interno", tabela: "Tabela", sumulas: "Súmulas",
  lei: "Lei", artigo: "Artigo", modelo_de_peca: "Modelo de peça", outro: "Outro" };

function resumoDaFicha(f) {
  const autor = f.autor ? f.autor : "";
  const quando = [f.edicao ? f.edicao + " ed." : "", f.ano || ""].filter(Boolean).join(", ");
  return [ROTULO_TIPO_MAT[f.tipo] || "", autor, quando, (f.areas || []).join(", ")].filter(Boolean).join(" · ");
}

async function listasDaBiblioteca() {
  if (cfg.biblioteca) return cfg.biblioteca;
  try {
    const r = await fetch("/api/biblioteca-juridica");
    if (r.ok) cfg.biblioteca = await r.json();
  } catch (err) { /* sem a lista, o dialogo usa a de fabrica */ }
  return cfg.biblioteca || { tipos: Object.keys(ROTULO_TIPO_MAT).map((t) => ({ id: t, rotulo: ROTULO_TIPO_MAT[t] })), areas: [] };
}

async function dialogoDaFicha(item) {
  const b = await listasDaBiblioteca();
  const f = item.ficha || {};
  const tipo = '<div class="dialogo-campo"><label for="ficha-tipo">O que é</label><div class="dialogo-caixa">' +
    '<select id="ficha-tipo">' + b.tipos.map((t) => '<option value="' + esc(t.id) + '"' + (t.id === f.tipo ? " selected" : "") + ">" + esc(t.rotulo) + "</option>").join("") +
    "</select></div></div>";
  const areas = '<div class="dialogo-campo"><label>Áreas</label><div class="chips ficha-areas">' +
    b.areas.map((a) => '<label class="chip-marcar"><input type="checkbox" data-ficha-area="' + esc(a) + '"' +
      ((f.areas || []).includes(a) ? " checked" : "") + "><span>" + esc(a) + "</span></label>").join("") + "</div></div>";
  const vazios = ["titulo", "autor", "edicao", "ano", "editora", "isbn"].filter((c) => !f[c]).length;
  const texto = vazios
    ? "Li a ficha pelas primeiras páginas. O que não achei ficou em branco: não chuto campo de ficha. O que você escrever aqui vale sobre o que eu li."
    : "Li a ficha pelas primeiras páginas. Confira: o que você escrever aqui vale sobre o que eu li.";
  const campo = (chave, rotulo, extra) => Object.assign({ chave: chave, rotulo: rotulo, valor: f[chave] || "", obrigatorio: false }, extra || {});
  const erro = '<p class="dialogo-dica" id="ficha-erro" hidden></p>';
  await dialogo({
    titulo: "A ficha de “" + item.nome + "”", contexto: "Configurações › Aprendizado › Material de consulta", larga: true,
    texto: texto, html: tipo,
    campos: [campo("titulo", "Título"), campo("autor", "Autor"), campo("edicao", "Edição", { placeholder: "2ª" }),
      campo("ano", "Ano", { placeholder: "2015", max: 4 }), campo("editora", "Editora"), campo("isbn", "ISBN")],
    depois: areas + erro, confirmar: "Guardar a ficha",
    aoConfirmar: async () => {
      const veu = $("veu-dialogo");
      if (!veu) return;
      const corpo = { tipo: veu.querySelector("#ficha-tipo").value, areas: [] };
      veu.querySelectorAll("[data-dialogo-chave]").forEach((el) => { corpo[el.dataset.dialogoChave] = el.value.trim(); });
      veu.querySelectorAll("[data-ficha-area]").forEach((el) => { if (el.checked) corpo.areas.push(el.dataset.fichaArea); });
      const r = await fetch("/api/material/" + encodeURIComponent(item.id) + "/ficha", { method: "PUT", headers: { "Content-Type": "application/json" }, body: JSON.stringify(corpo) });
      if (!r.ok) {
        const aviso = veu.querySelector("#ficha-erro");
        aviso.textContent = await erroDe(r);
        aviso.hidden = false;
        return;
      }
      cfg.material = await r.json();
      if (dialogoAberto) dialogoAberto.fechar(null);
      avisoCert("ficha guardada", { tom: "ok" });
      desenharConfig();
    },
  });
}

function escolherMaterial() {
  const campo = document.createElement("input");
  campo.type = "file";
  campo.multiple = true;
  campo.accept = ".pdf,.docx,.txt,.md";
  campo.onchange = () => enviarMaterial(campo.files);
  campo.click();
}

function menuDoMaterial(onde, id) {
  const m = ((cfg.material || {}).itens || []).find((x) => x.id === id);
  if (!m) return;
  const itens = [
    { rotulo: "Conferir a ficha", icone: "edit", acao: () => dialogoDaFicha(m) },
    { rotulo: "Glossário e teses", icone: "auto_stories", acao: () => glossarioETeses(m) },
    /* Só o que é do próprio escritório se exporta (artigo, modelo de peça,
       manual); doutrina de editora nunca. */
    ...(m.ficha && ["artigo", "modelo_de_peca", "manual"].includes(m.ficha.tipo) && m.ficha.origem !== "comunidade"
      ? [{ rotulo: "Exportar para outro PAULUS", icone: "share", acao: () => exportarPacote(m) }] : []),
    { rotulo: "Abrir o arquivo", icone: "open_in_new", acao: async () => {
      const r = await fetch("/api/material/" + encodeURIComponent(id) + "/abrir", { method: "POST" });
      if (!r.ok) avisoCert(await erroDe(r), { tom: "erro" });
    } },
    "-",
    { rotulo: "Remover", icone: "delete", perigo: true, acao: async () => {
      const ok = await confirmar({
        titulo: "Remover “" + m.nome + "”?", contexto: "Configurações › Aprendizado",
        texto: "Deixo de consultar este material na hora, e o arquivo guardado aqui é apagado. Não passa pela lixeira: para usar de novo, é enviar outra vez.",
        confirmar: "Remover", perigo: true,
      });
      if (!ok) return;
      const r = await fetch("/api/material/" + encodeURIComponent(id), { method: "DELETE" });
      if (!r.ok) { avisoCert(await erroDe(r), { tom: "erro" }); return; }
      cfg.material = await r.json();
      avisoCert("“" + m.nome + "” saiu do material", { tom: "ok" });
      desenharConfig();
    } },
  ];
  menuNaLinha(onde, itens);
}

function ligarMaterial() {
  const raiz = $("cfg-tela");
  if (!raiz) return;
  const escolher = raiz.querySelector("[data-mat-escolher]");
  if (escolher) escolher.onclick = (e) => { e.stopPropagation(); escolherMaterial(); };
  const pacote = raiz.querySelector("[data-mat-pacote]");
  if (pacote) pacote.onclick = (e) => { e.stopPropagation(); importarPacote(); };
  raiz.querySelectorAll("[data-mat-mais]").forEach((b) => {
    b.onclick = (e) => { e.stopPropagation(); menuDoMaterial(b, b.dataset.matMais); };
  });
  const solta = $("cfg-solta-material");
  if (solta) {
    solta.ondragover = (e) => { e.preventDefault(); solta.classList.add("sobre"); };
    solta.ondragleave = () => solta.classList.remove("sobre");
    solta.ondrop = (e) => {
      e.preventDefault();
      solta.classList.remove("sobre");
      if (e.dataTransfer && e.dataTransfer.files) enviarMaterial(e.dataTransfer.files);
    };
  }
}
