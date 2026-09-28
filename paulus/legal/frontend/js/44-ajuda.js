/* ------------------------------------------------------------------
   A IA ajudando sem ser perguntada (I9, src/ajuda.py), na ficha do
   documento do Acervo:

   - o que já está CONFERIDO no texto — tipo, partes, valores, processo,
     datas, pedidos —, cada um com a página. Só fato conferido: o que o
     modelo achou e não se confirmou no texto não aparece aqui. O lápis
     corrige; a correção fica gravada como manual e vira pergunta do
     conjunto de medição (docs/medicao.md);
   - as perguntas deste tipo de documento que respondem na hora, pelos
     fatos conferidos. Clicar pergunta.

   Os prazos achados vão sozinhos para Aprovações (nada entra na Agenda sem
   o sim); o botão da ficha só propõe de novo os que ainda não foram.
   ------------------------------------------------------------------ */

const ajudaDoc = { dados: {}, pedindo: new Set(), editando: "" };

function carregarAjuda(nome) {
  if (!nome || ajudaDoc.pedindo.has(nome) || ajudaDoc.dados[nome]) return;
  ajudaDoc.pedindo.add(nome);
  fetch("/api/ajuda/documento?nome=" + encodeURIComponent(nome))
    .then((r) => (r.ok ? r.json() : null))
    .then((d) => {
      ajudaDoc.pedindo.delete(nome);
      if (!d) return;
      ajudaDoc.dados[nome] = d;
      if (bib.aberto && (docDoAcervo(bib.aberto) || {}).nome === nome) desenharBiblioteca();
    })
    .catch(() => ajudaDoc.pedindo.delete(nome));
}

function blocosDaAjuda(x) {
  const d = ajudaDoc.dados[x.nome];
  if (!d) { carregarAjuda(x.nome); return ""; }
  if (!d.cartao) return "";
  const itens = d.cartao.itens || [];
  const manual = new Set(d.cartao.manual || []);
  const linhas = itens.length
    ? itens.map((it) => {
      const chave = it.secao + "|" + it.id;
      const pagina = it.pagina ? '<small class="aj-pagina">p. ' + esc(String(it.pagina)) + "</small>" : "";
      const marca = manual.has(it.id) ? '<small class="aj-manual" title="Corrigido à mão">corrigido</small>' : "";
      if (ajudaDoc.editando === chave) {
        return '<div class="aj-item aj-editando"><span class="aj-rotulo">' + esc(it.rotulo || it.secao_rotulo) + "</span>" +
          '<div class="linha-form"><input type="text" id="aj-novo" value="' + esc(it.valor) + '" autocomplete="off">' +
          '<button class="primario" data-aj-salvar="' + esc(chave) + '">Salvar</button>' +
          '<button data-aj-cancelar="1">Cancelar</button></div></div>';
      }
      return '<div class="aj-item"><span class="aj-rotulo">' + esc(it.rotulo || it.secao_rotulo) + "</span>" +
        '<b class="aj-valor" title="' + esc(it.quote || it.valor) + '">' + esc(it.valor) + "</b>" + pagina + marca +
        '<button class="aj-editar" data-aj-editar="' + esc(chave) + '" title="Corrigir" aria-label="Corrigir">' + ic("edit", 16) + "</button></div>";
    }).join("")
    : "<p>Nada conferido ainda neste documento: o que aparece aqui é só o que foi achado e confirmado no texto.</p>";
  const sugestoes = (d.sugestoes || []).length
    ? '<div class="ae-ficha-bloco"><span class="sv-kicker">Perguntas que respondem na hora</span>' +
      '<div class="aj-sugestoes">' + d.sugestoes.map((q) =>
        '<button class="aj-sugestao com-icone" data-aj-perguntar="' + esc(q) + '">' + ic("forum", 16) + esc(q) + "</button>").join("") +
      "</div></div>"
    : "";
  const prazos = (d.prazos || []).length
    ? '<button class="ligacao-painel" data-aj-prazos="1">Propor ' + plural(d.prazos.length, "prazo") + " em Aprovações →</button>"
    : "";
  return '<div class="ae-ficha-bloco"><span class="sv-kicker">Conferido no texto · ' + itens.length + "</span>" +
    '<div class="aj-itens">' + linhas + "</div>" + prazos + "</div>" + sugestoes;
}

function ligarAjuda(raiz) {
  const x = bib.aberto ? docDoAcervo(bib.aberto) : null;
  if (!x) return;
  raiz.querySelectorAll("[data-aj-editar]").forEach((b) => {
    b.onclick = () => { ajudaDoc.editando = b.dataset.ajEditar; desenharBiblioteca(); const i = $("aj-novo"); if (i) i.focus(); };
  });
  raiz.querySelectorAll("[data-aj-cancelar]").forEach((b) => {
    b.onclick = () => { ajudaDoc.editando = ""; desenharBiblioteca(); };
  });
  raiz.querySelectorAll("[data-aj-salvar]").forEach((b) => {
    b.onclick = async () => {
      const [secao, id] = b.dataset.ajSalvar.split("|");
      const valor = ($("aj-novo") || {}).value || "";
      const r = await fetch("/api/ajuda/corrigir", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ nome: x.nome, secao: secao, id: id, valor: valor }),
      });
      if (!r.ok) { avisoCert(await erroDe(r), { tom: "erro" }); return; }
      const d = await r.json();
      ajudaDoc.dados[x.nome] = Object.assign({}, ajudaDoc.dados[x.nome], { cartao: d.cartao });
      ajudaDoc.editando = "";
      avisoCert("corrigido — e guardado como pergunta de medição", { tom: "ok" });
      desenharBiblioteca();
    };
  });
  const campo = $("aj-novo");
  if (campo) campo.onkeydown = (e) => {
    if (e.key === "Enter") { const s = raiz.querySelector("[data-aj-salvar]"); if (s) s.click(); }
    if (e.key === "Escape") { ajudaDoc.editando = ""; desenharBiblioteca(); }
  };
  raiz.querySelectorAll("[data-aj-perguntar]").forEach((b) => {
    b.onclick = () => {
      const pergunta = b.dataset.ajPerguntar;
      perguntarSobre(x);
      setTimeout(() => { const p = $("pedido"); if (p) { p.value = pergunta; enviar(); } }, 260);
    };
  });
  const prazos = raiz.querySelector("[data-aj-prazos]");
  if (prazos) prazos.onclick = async () => {
    const r = await fetch("/api/ajuda/prazos", {
      method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ nome: x.nome }),
    });
    if (!r.ok) { avisoCert(await erroDe(r), { tom: "erro" }); return; }
    const d = await r.json();
    avisoCert(d.propostos ? plural(d.propostos, "prazo") + " em Aprovações — nada vai para a Agenda sem o sim"
      : "esses prazos já foram propostos em Aprovações");
  };
}
