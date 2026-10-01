/* ------------------------------------------ lei com vigência (L10) */
/*
   O botão "Vigência" de cada artigo achado (js/22-leis.js): a situação de
   cada dispositivo numa data, e o histórico das mudanças, pelas notas do
   texto compilado do Planalto (src/vigencia.py). O que não dá para saber -
   o texto de uma redação anterior, a vacatio legis - é dito junto.
*/

async function vigenciaDoArtigo(a) {
  if (!a) return;
  const agora = new Date();
  let quando = agora.getFullYear() + "-" + String(agora.getMonth() + 1).padStart(2, "0") + "-" + String(agora.getDate()).padStart(2, "0");
  const corpoDe = (d) => {
    // N12: na data em que valia outra redação, o texto dela (das redações riscadas do Planalto).
    const linhas = d.dispositivos.map((x) => '<div class="vig-linha' + (x.diferente ? " diferente" : "") + '"><b>' + esc(x.rotulo) + "</b><span>" +
      esc(x.na_data.frase) + (x.na_data.texto ? '<q class="vig-anterior">' + esc(x.na_data.texto) + "</q>" : "") + "</span></div>").join("");
    const hist = d.historico.length ? '<ol class="vig-historico">' + d.historico.map((h) => "<li><b>" + esc(!h.data ? "sem data" : (h.data_exata ? h.data.split("-").reverse().join("/") : h.data.slice(0, 4))) +
      "</b> · " + esc(h.dispositivo) + " — " + esc(h.nota.replace(/^\(|\)$/g, "")) +
      (h.vigor && h.vigor !== h.data ? ' <small class="vig-vigor">em vigor desde ' + esc(h.vigor.split("-").reverse().join("/")) +
        (h.vacatio_dias ? " · " + h.vacatio_dias + " dias de vacatio" : "") + "</small>" : "") +
      (h.em_partes ? ' <small class="vig-vigor">vigência em partes: confira</small>' : "") + "</li>").join("") + "</ol>" : '<p class="cfg-explica">Nenhuma mudança anotada no texto compilado.</p>';
    return '<p class="vig-resumo">' + esc(d.resumo) + "</p>" + '<div class="vig-lista">' + linhas + "</div>" +
      '<h4 class="vig-sub">O que mudou, na ordem</h4>' + hist +
      (d.inicio_do_codigo ? '<p class="cfg-explica">O código vigora desde ' + esc(d.inicio_do_codigo.data.split("-").reverse().join("/")) + " (" + esc(d.inicio_do_codigo.como) + ").</p>" : "") +
      '<p class="cfg-explica">' + esc(d.limites) + "</p>";
  };
  const buscar = async () => {
    const r = await fetch("/api/leis/vigencia?codigo=" + encodeURIComponent(a.codigo) + "&numero=" + encodeURIComponent(a.numero) + "&data=" + encodeURIComponent(quando));
    if (!r.ok) throw new Error(await erroDe(r));
    return r.json();
  };
  let d;
  try { d = await buscar(); } catch (err) { avisoCert(String(err.message || err), { tom: "erro" }); return; }
  const aberto = dialogo({ titulo: "Vigência · " + a.citacao, contexto: "Pelas notas do Planalto", larga: true, classe: "vig-dialogo",
    html: '<div class="ag-campo"><label for="vig-data">Como estava em</label><input type="date" id="vig-data" value="' + quando + '"></div>' +
      '<div id="vig-corpo">' + corpoDe(d) + "</div>",
    confirmar: "Fechar", semCancelar: true });
  const campo = $("vig-data");
  if (campo) campo.addEventListener("change", async () => {
    if (!campo.value) return;
    quando = campo.value;
    try { const novo = await buscar(); const alvo = $("vig-corpo"); if (alvo) alvo.innerHTML = corpoDe(novo); }
    catch (err) { avisoCert(String(err.message || err), { tom: "erro" }); }
  });
  await aberto;
}
