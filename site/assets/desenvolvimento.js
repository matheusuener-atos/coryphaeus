/* PAULUS - Desenvolvimento: uma linha por versao publicada, da mais nova
   para a mais antiga - o mes, o numero e as mudancas (a primeira em
   destaque, as outras recolhidas a partir da terceira). Le
   /api/public/desenvolvimento (as versoes, mes a mes). Mostra as dez mais
   novas; "Versoes anteriores" traz o resto. #v0-9-3 abre a versao. */
(function () {
  var MESES = ['jan', 'fev', 'mar', 'abr', 'mai', 'jun', 'jul', 'ago', 'set', 'out', 'nov', 'dez'];
  var PRIMEIRAS = 10, MUDANCAS = 3;
  var linha = document.getElementById('dv-linha');
  var versoes = [], todas = false, abertas = new Set(), atualizado = '';

  function el(tag, classe, texto) {
    var e = document.createElement(tag);
    if (classe) e.className = classe;
    if (texto != null) e.textContent = texto;
    return e;
  }
  function idVersao(v) { return 'v' + String(v).replace(/\./g, '-'); }
  function mes(data) { var p = String(data).split('-'); return MESES[+p[1] - 1] + ' ' + p[0]; }
  function dataBR(s) { var p = String(s).split('-'); return p[2] + '/' + p[1] + '/' + p[0]; }

  function desenhar() {
    linha.textContent = '';
    if (!versoes.length) { linha.appendChild(el('p', 'vazio', 'Ainda não há versões publicadas.')); return; }
    (todas ? versoes : versoes.slice(0, PRIMEIRAS)).forEach(function (r) {
      var v = el('article', 'versao');
      v.id = idVersao(r.version);
      var quando = el('span', 'quando', mes(r.date));
      quando.title = dataBR(r.date);
      v.appendChild(quando);
      var num = el('a', 'num', r.version);
      num.href = '#' + v.id;
      v.appendChild(num);
      var corpo = el('div');
      corpo.style.display = 'grid';
      corpo.style.gap = '8px';
      var lista = (r.changes || []).map(function (x) { return typeof x === 'string' ? x : x.text; });
      var aberta = abertas.has(r.version);
      var ul = el('ul');
      (aberta ? lista : lista.slice(0, MUDANCAS)).forEach(function (t) { ul.appendChild(el('li', null, t)); });
      if (!lista.length) ul.appendChild(el('li', null, 'Correções e ajustes.'));
      corpo.appendChild(ul);
      if (lista.length > MUDANCAS) {
        var mais = el('button', 'mais', aberta ? 'Mostrar menos' : 'Mais ' + (lista.length - MUDANCAS) + (lista.length - MUDANCAS === 1 ? ' mudança' : ' mudanças'));
        mais.type = 'button';
        mais.addEventListener('click', function () { aberta ? abertas.delete(r.version) : abertas.add(r.version); desenhar(); });
        corpo.appendChild(mais);
      }
      v.appendChild(corpo);
      linha.appendChild(v);
    });
    if (!todas && versoes.length > PRIMEIRAS) {
      var ant = el('button', 'ver-anteriores', 'Versões anteriores');
      ant.type = 'button';
      ant.addEventListener('click', function () { todas = true; desenhar(); });
      linha.appendChild(ant);
    }
    if (atualizado) linha.appendChild(el('span', 'atualizado', 'atualizado em ' + dataBR(atualizado)));
  }

  fetch('/api/public/desenvolvimento').then(function (r) {
    if (!r.ok) throw new Error(r.status);
    return r.json();
  }).then(function (d) {
    (d.meses || []).forEach(function (m) { (m.releases || []).forEach(function (r) { versoes.push(r); }); });
    versoes.sort(function (a, b) {
      var x = String(b.date).localeCompare(String(a.date));
      if (x) return x;
      var pa = String(a.version).split('.').map(Number), pb = String(b.version).split('.').map(Number);
      for (var i = 0; i < 3; i++) if ((pb[i] || 0) !== (pa[i] || 0)) return (pb[i] || 0) - (pa[i] || 0);
      return 0;
    });
    atualizado = d.atualizadoEm || '';
    var h = decodeURIComponent(location.hash.slice(1));
    var alvo = versoes.findIndex(function (r) { return idVersao(r.version) === h; });
    if (alvo >= PRIMEIRAS) todas = true;
    if (alvo >= 0) abertas.add(versoes[alvo].version);
    desenhar();
    if (alvo >= 0) { var e = document.getElementById(h); if (e) e.scrollIntoView(); }
  }).catch(function () {
    linha.textContent = '';
    linha.appendChild(el('p', 'vazio', 'Não consegui carregar o histórico agora. Tente de novo em alguns minutos.'));
  });
})();
