/* A lista curada de materiais (site/dados/materiais.json), montada na
   pagina: uma linha por material - o tipo, o titulo com o resumo, o autor e
   a data - com o filtro Todos / Artigos / Modelos / Tabelas. */
(function () {
  var alvo = document.getElementById("mt-lista");
  var filtro = document.getElementById("mt-filtro");
  if (!alvo) return;
  var TIPOS = { artigo: "Artigo", modelo: "Modelo", tabela: "Tabela" };
  var itens = [], tipo = "";
  function esc(s) {
    return String(s == null ? "" : s).replace(/[&<>"']/g, function (c) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c];
    });
  }
  function data(iso) { var m = /^(\d{4})-(\d{2})-(\d{2})/.exec(iso || ""); return m ? m[3] + "/" + m[2] + "/" + m[1] : (iso || ""); }

  function desenhar() {
    var lista = itens.filter(function (m) { return !tipo || String(m.tipo || "").toLowerCase() === tipo; });
    if (!itens.length) { alvo.innerHTML = '<p class="vazio">Ainda não há materiais publicados. O primeiro pode ser o seu.</p>'; return; }
    if (!lista.length) { alvo.innerHTML = '<p class="vazio">Nenhum material deste tipo ainda.</p>'; return; }
    alvo.innerHTML = lista.map(function (m) {
      var t = String(m.tipo || "").toLowerCase();
      return '<a class="material mt-item" href="..' + esc(m.arquivo) + '">' +
        '<span class="tipo">' + esc(TIPOS[t] || m.tipo || "Material") + "</span>" +
        '<span class="meio"><b>' + esc(m.titulo) + "</b>" + (m.resumo ? "<span>" + esc(m.resumo) + "</span>" : "") +
        "<span>" + esc([(m.areas || []).join(", "), m.licenca || "CC BY 4.0"].filter(Boolean).join(" · ")) + "</span></span>" +
        '<span class="quem"><span>' + esc(m.autor + (m.oab ? " · OAB " + m.oab : "")) + "</span><span>" + esc(data(m.publicado_em)) + "</span></span></a>";
    }).join("");
  }

  if (filtro) filtro.querySelectorAll("[data-tipo]").forEach(function (b) {
    b.addEventListener("click", function () {
      tipo = b.dataset.tipo;
      filtro.querySelectorAll("[data-tipo]").forEach(function (x) { x.setAttribute("aria-pressed", x === b ? "true" : "false"); });
      desenhar();
    });
  });

  fetch("../dados/materiais.json", { cache: "no-cache" })
    .then(function (r) { if (!r.ok) throw new Error(r.status); return r.json(); })
    .then(function (d) { itens = (d && d.materiais) || []; desenhar(); })
    .catch(function () { alvo.innerHTML = '<p class="vazio">Não consegui abrir a lista agora.</p>'; });
})();
