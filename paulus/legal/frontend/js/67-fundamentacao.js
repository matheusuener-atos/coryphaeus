/* ------------------------------------------ a Biblioteca ajudando a escrever (L5) */
/*
   "Fundamentar" no painel do editor: para o trecho escolhido (ou o parágrafo
   onde está o cursor), os artigos citados e os achados pelas palavras, as
   súmulas do STJ, os temas repetitivos e a posição da casa - cada um com o
   porquê, e o botão que insere o texto oficial (src/fundamentacao.py).
   Embaixo de cada artigo achado em "Citar artigo": a posição da casa
   (escrita pelo titular, na janela do escritório) e os temas do STJ que
   citam o artigo.
*/

function trechoDoEditor() {
  const folha = $("ed-folha");
  if (!folha) return "";
  const sel = window.getSelection ? window.getSelection() : null;
  if (sel && sel.rangeCount && !sel.isCollapsed && folha.contains(sel.anchorNode)) return String(sel).trim();
  let no = sel && sel.anchorNode && folha.contains(sel.anchorNode) ? sel.anchorNode : null;
  while (no && no.parentNode !== folha) no = no.parentNode;
  if (no && no.textContent && no.textContent.trim().length > 20) return no.textContent.trim();
  return folha.textContent.trim().slice(-1200);
}

function inserirNoEditor(texto) {
  const folha = $("ed-folha");
  if (!folha) { avisoCert("abra um documento para inserir"); return; }
  const p = document.createElement("p");
  p.textContent = texto;
  folha.appendChild(p);
  if (typeof marcarSujo === "function") marcarSujo();
  avisoCert("inserido no fim do documento");
}

async function fundamentarNoEditor() {
  const trecho = trechoDoEditor();
  if (trecho.length < 12) { avisoCert("escreva ou escolha um trecho da peça primeiro", { tom: "erro" }); return; }
  let d;
  try {
    const r = await fetch("/api/biblioteca/fundamentacao", { method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ trecho: trecho }) });
    if (!r.ok) throw new Error(await erroDe(r));
    d = await r.json();
  } catch (err) { avisoCert(String(err.message || err), { tom: "erro" }); return; }
  const art = d.artigos.map((a, i) => '<div class="fun-item"><div class="fun-cab"><b>' + esc(a.citacao) + "</b>" +
      (a.revogado ? '<span class="etiqueta prazo">revogado</span>' : "") + "<small>" + esc(a.porque) + "</small></div>" +
      '<p class="fun-texto">' + esc(a.texto.slice(0, 420)) + (a.texto.length > 420 ? "…" : "") + "</p>" +
      (a.posicao ? '<p class="fun-casa"><b>Posição da casa:</b> ' + esc(a.posicao) + "</p>" : "") +
      (a.temas.length ? '<p class="fun-nota">Temas do STJ sobre ele: ' + esc(a.temas.join(", ")) + "</p>" : "") +
      '<div class="fun-botoes"><button data-fun-art="' + i + '" data-com="0">Inserir a citação</button>' +
      '<button data-fun-art="' + i + '" data-com="1">Inserir com o texto</button></div></div>').join("");
  const sum = d.sumulas.map((s, i) => '<div class="fun-item"><div class="fun-cab"><b>' + esc(s.titulo) + "</b><small>" + esc(s.porque) + "</small></div>" +
      '<p class="fun-texto">' + esc(s.texto) + '</p><div class="fun-botoes"><button data-fun-sum="' + i + '">Inserir</button></div></div>').join("");
  const tem = d.temas.map((t, i) => '<div class="fun-item"><div class="fun-cab"><b>' + esc(t.rotulo) + "</b><small>" +
      esc([t.situacao, t.orgao, t.porque].filter(Boolean).join(" · ")) + "</small></div>" +
      '<p class="fun-texto">' + esc((t.tese || ("Questão: " + t.questao)).slice(0, 420)) + ((t.tese || t.questao).length > 420 ? "…" : "") + "</p>" +
      (t.tese ? '<div class="fun-botoes"><button data-fun-tema="' + i + '">Inserir a tese</button></div>' : '<p class="fun-nota">Ainda sem tese firmada.</p>') + "</div>").join("");
  const bloco = (titulo, corpo, vazio) => '<section class="fun-bloco"><h4>' + esc(titulo) + "</h4>" + (corpo || '<p class="fun-nota">' + esc(vazio) + "</p>") + "</section>";
  const aberto = dialogo({ titulo: "Fundamentação sugerida", contexto: "pelas palavras: " + (d.palavras.join(", ") || "—"), classe: "fun-dialogo", larga: true,
    html: '<p class="cfg-explica">Do que está instalado neste computador — os códigos do Planalto, as súmulas e os temas do STJ, e a posição da casa. ' +
      "Sem modelo: é você quem escolhe o que entra, e o que entra é o texto oficial.</p>" +
      bloco("Artigos", art, "Nenhum artigo achado com essas palavras.") + bloco("Súmulas do STJ", sum, "Nenhuma súmula com essas palavras.") +
      bloco("Temas repetitivos do STJ", tem, "Nenhum tema com essas palavras."),
    confirmar: "Fechar", semCancelar: true });
  document.querySelectorAll("[data-fun-art]").forEach((b) => {
    b.onclick = () => inserirCitacao(d.artigos[Number(b.dataset.funArt)], b.dataset.com === "1");
  });
  document.querySelectorAll("[data-fun-sum]").forEach((b) => {
    b.onclick = () => { const s = d.sumulas[Number(b.dataset.funSum)]; inserirNoEditor(s.titulo + ": “" + s.texto + "”"); };
  });
  document.querySelectorAll("[data-fun-tema]").forEach((b) => {
    b.onclick = () => { const t = d.temas[Number(b.dataset.funTema)]; inserirNoEditor("Tese firmada no " + t.rotulo + ": “" + t.tese + "”"); };
  });
  await aberto;
}

document.addEventListener("click", (e) => {
  const b = e.target.closest && e.target.closest("[data-ed-fundamentar]");
  if (b) { e.preventDefault(); fundamentarNoEditor(); }
});

/* ------------------------------------------ a posição da casa, embaixo do artigo */

async function posicaoDaCasa(a, caixa) {
  if (!caixa || !a) return;
  let pos = null, temas = [];
  try {
    const [p, t] = await Promise.all([
      fetch("/api/leis/posicao?codigo=" + encodeURIComponent(a.codigo) + "&numero=" + encodeURIComponent(a.numero)).then((r) => r.json()),
      fetch("/api/biblioteca/temas?codigo=" + encodeURIComponent(a.codigo) + "&artigo=" + encodeURIComponent(a.numero)).then((r) => r.json()),
    ]);
    pos = p.posicao;
    temas = t.temas || [];
  } catch (err) { return; }
  const local = acessoDeFora.local;
  if (!pos && !temas.length && !local) return;
  caixa.hidden = false;
  caixa.innerHTML = '<span class="rotulo">Posição da casa</span>' +
    (pos ? '<p class="fun-casa">' + esc(pos.texto) + "</p>" : '<p class="nota">O escritório ainda não escreveu a posição dele sobre este artigo.</p>') +
    (local ? '<button data-lei-pos-editar="1">' + ic("edit_note", 16) + (pos ? "Mudar" : "Escrever a posição da casa") + "</button>" : "") +
    (temas.length ? '<span class="rotulo">Temas do STJ que citam este artigo</span>' + temas.slice(0, 4).map((t) =>
      '<p class="fun-nota"><b>' + esc(t.rotulo) + "</b> · " + esc(t.situacao) + " — " + esc((t.tese || t.questao).slice(0, 260)) + "</p>").join("") : "");
  const editar = caixa.querySelector("[data-lei-pos-editar]");
  if (editar) editar.onclick = async () => {
    let texto = pos ? pos.texto : "";
    const aberto = dialogo({ titulo: "Posição da casa", contexto: a.citacao,
      html: '<p class="cfg-explica">O que o escritório entende deste artigo. Aparece junto dele e na fundamentação sugerida do editor. Em branco, sai.</p>' +
        '<textarea id="fun-pos" rows="5" placeholder="Ex.: multa acima de 2% em relação de consumo é abusiva (art. 52, § 1º, do CDC).">' + esc(texto) + "</textarea>",
      confirmar: "Guardar" });
    const area = $("fun-pos");
    if (area) { area.addEventListener("input", () => { texto = area.value; }); area.focus(); }
    const r = await aberto;
    if (!r || !r.ok) return;
    const x = await fetch("/api/leis/posicao", { method: "PUT", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ codigo: a.codigo, numero: a.numero, texto: texto }) });
    if (!x.ok) { avisoCert(await erroDe(x), { tom: "erro" }); return; }
    avisoCert("Posição da casa guardada.", { tom: "ok" });
    posicaoDaCasa(a, caixa);
  };
}

/* ------------------------------------------ na resposta da conversa (N7) */
/* Embaixo da resposta: os temas do STJ ligados aos artigos que a conversa
   citou, as súmulas e os temas citados pelo número, e a posição da casa. Por
   regra (src/fundamentacao.py, `relacionados`) - não muda a resposta, e diz
   de onde veio. Fechado de início: é para quem quer conferir. */
function blocoRelacionados(r) {
  if (!r) return "";
  const n = (r.temas || []).length + (r.sumulas || []).length + (r.posicoes || []).length;
  if (!n) return "";
  const temas = (r.temas || []).map((t) => '<li class="rel-item"><b>' + esc(t.rotulo) + "</b>" + (t.situacao ? " <small>" + esc(t.situacao) + "</small>" : "") +
    '<p class="rel-texto">' + esc(t.tese || t.questao || "") + "</p><small class=\"rel-porque\">" + esc(t.porque) + "</small></li>").join("");
  const sumulas = (r.sumulas || []).map((x) => '<li class="rel-item"><b>' + esc(x.titulo || ("Súmula " + x.numero)) + "</b>" +
    '<p class="rel-texto">' + esc(x.texto) + "</p><small class=\"rel-porque\">" + esc(x.porque) + "</small></li>").join("");
  const posicoes = (r.posicoes || []).map((x) => '<li class="rel-item"><b>Posição da casa · ' + esc(x.artigo) + "</b>" +
    '<p class="rel-texto">' + esc(x.texto) + "</p>" + (x.autor ? '<small class="rel-porque">por ' + esc(x.autor) + "</small>" : "") + "</li>").join("");
  const partes = [];
  if ((r.temas || []).length) partes.push(plural(r.temas.length, "tema", "temas"));
  if ((r.sumulas || []).length) partes.push(plural(r.sumulas.length, "súmula", "súmulas"));
  if ((r.posicoes || []).length) partes.push("posição da casa");
  return '<details class="rel-bloco"><summary>' + ic("library_books", 16) + " Na Biblioteca: " + esc(partes.join(", ")) +
    ((r.artigos || []).length ? " · " + esc(r.artigos.slice(0, 3).join(", ")) : "") + "</summary>" +
    '<ul class="rel-lista">' + posicoes + temas + sumulas + "</ul>" +
    '<p class="rel-aviso">' + esc(r.aviso || "") + "</p></details>";
}
