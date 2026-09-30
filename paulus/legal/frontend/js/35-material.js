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
    const aviso = f && f.aviso ? '<span class="etiqueta">' + esc(f.aviso) + "</span>" : "";
    return '<div class="cfg-servico mat-linha"><span class="caixa-tipo">' + ic("menu_book", 18) + "</span>" +
      '<span class="duas-linhas cresce"><b>' + esc(f && f.titulo ? f.titulo : m.nome) + "</b><small>" + esc(sub) + "</small></span>" +
      conferir + aviso +
      '<button class="mais-linha" data-mat-mais="' + esc(m.id) + '" title="Mais" aria-label="Mais">' + ic("more_horiz", 18) + "</button></div>";
  }).join("");
  const enviando = mat.enviando.length;
  const solta = '<div class="cfg-solta" id="cfg-solta-material"><span class="duas-linhas"><b>' +
    (enviando ? "lendo " + (enviando === 1 ? "“" + esc(mat.enviando[0]) + "”" : plural(enviando, "arquivo")) + "…" : "Arraste PDFs, DOCX, TXT ou MD para cá") + "</b>" +
    "<small>o arquivo fica guardado nesta máquina e é consultado em cada pergunta</small></span>" +
    '<span class="cfg-botoes"><button class="primario com-icone" data-mat-escolher="1"' + (enviando ? " disabled" : "") + ">" +
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
    { rotulo: "Conferir a ficha", icone: "badge", acao: () => dialogoDaFicha(m) },
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
