/* A lista curada de materiais (site/dados/materiais.json), montada na página. */
(function () {
  var alvo = document.getElementById("mt-lista");
  if (!alvo) return;
  function esc(s) {
    return String(s == null ? "" : s).replace(/[&<>"']/g, function (c) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c];
    });
  }
  function data(iso) { var m = /^(\d{4})-(\d{2})-(\d{2})/.exec(iso || ""); return m ? m[3] + "/" + m[2] + "/" + m[1] : (iso || ""); }
  fetch("../dados/materiais.json", { cache: "no-cache" })
    .then(function (r) { if (!r.ok) throw new Error(r.status); return r.json(); })
    .then(function (d) {
      var itens = (d && d.materiais) || [];
      if (!itens.length) {
        alvo.innerHTML = '<p class="pg-vazio">Ainda não há materiais publicados. O primeiro pode ser o seu.</p>';
        return;
      }
      alvo.innerHTML = itens.map(function (m) {
        return '<article class="mt-item"><h2>' + esc(m.titulo) + '</h2><p class="mt-meta">' +
          esc([m.autor + (m.oab ? " · OAB " + m.oab : ""), (m.areas || []).join(", "), data(m.publicado_em)].filter(Boolean).join(" · ")) + "</p>" +
          (m.resumo ? "<p>" + esc(m.resumo) + "</p>" : "") +
          '<p class="mt-pe"><a class="pg-seta" href="..' + esc(m.arquivo) + '">Ler o material →</a><span>' + esc(m.licenca || "CC BY 4.0") + "</span></p></article>";
      }).join("");
    })
    .catch(function () { alvo.innerHTML = '<p class="pg-vazio">Não consegui abrir a lista agora.</p>'; });
})();
