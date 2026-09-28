/* PAULUS - Apoiadores: o mural, agrupado por "apoiam desde <ano>", nomes em
   ordem alfabetica, todos no mesmo estilo. So nome e mes vem da API. */
(function () {
  var alvo = document.getElementById('ap-grupos');

  function el(tag, classe, texto) {
    var e = document.createElement(tag);
    if (classe) e.className = classe;
    if (texto != null) e.textContent = texto;
    return e;
  }

  function vazio(texto) {
    alvo.textContent = '';
    alvo.appendChild(el('p', 'pg-vazio', texto));
  }

  fetch('/api/public/apoiadores').then(function (r) {
    if (!r.ok) throw new Error(r.status);
    return r.json();
  }).then(function (d) {
    var por = {};
    (d.apoiadores || []).forEach(function (a) {
      var ano = String(a.since || '').slice(0, 4);
      if (a.name && /^\d{4}$/.test(ano)) (por[ano] = por[ano] || []).push(a.name);
    });
    var anos = Object.keys(por).sort();
    if (!anos.length) return vazio('Ainda não há nomes publicados. Quem apoia e autoriza aparece aqui.');
    alvo.textContent = '';
    anos.forEach(function (ano) {
      var sec = el('section', 'ap-grupo');
      var h = el('h2');
      h.appendChild(el('span', 'pg-rotulo p', 'Apoiam desde'));
      h.appendChild(el('span', 'ano', ano));
      sec.appendChild(h);
      var ul = el('ul');
      por[ano].sort(function (x, y) { return x.localeCompare(y, 'pt-BR'); }).forEach(function (nome) { ul.appendChild(el('li', null, nome)); });
      sec.appendChild(ul);
      alvo.appendChild(sec);
    });
  }).catch(function () {
    vazio('Não consegui carregar a lista agora. Tente de novo em alguns minutos.');
  });
})();
