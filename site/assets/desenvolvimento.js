/* PAULUS - Desenvolvimento aberto: a linha do tempo mes a mes.
   Le /api/public/desenvolvimento (as versoes publicadas). Abre os
   dois meses mais recentes e o ano atual; os anos anteriores ficam
   recolhidos com um resumo. #2026-09 abre o mes; #v0-9-3, a versao. */
(function () {
  var MESES = ['Janeiro', 'Fevereiro', 'Março', 'Abril', 'Maio', 'Junho', 'Julho', 'Agosto', 'Setembro', 'Outubro', 'Novembro', 'Dezembro'];
  var linha = document.getElementById('dv-linha');
  var periodo = document.getElementById('dv-periodo');
  var dados = null, abertos = new Set(), anosAbertos = new Set();

  function el(tag, classe, texto) {
    var e = document.createElement(tag);
    if (classe) e.className = classe;
    if (texto != null) e.textContent = texto;
    return e;
  }
  function dataBR(s) { var p = String(s).split('-'); return p[2] + '/' + p[1] + '/' + p[0]; }
  function idVersao(v) { return 'v' + String(v).replace(/\./g, '-'); }
  function plural(n, um, varios) { return n + ' ' + (n === 1 ? um : varios); }
  function icone(nome) { var s = el('span', 'icon', nome); s.setAttribute('aria-hidden', 'true'); return s; }

  function desenhar() {
    var porAno = {};
    dados.meses.forEach(function (m) { var a = m.month.slice(0, 4); (porAno[a] = porAno[a] || []).push(m); });
    var anos = Object.keys(porAno).sort().reverse();

    periodo.textContent = '';
    anos.forEach(function (ano) {
      var l = el('div', 'linha');
      l.appendChild(el('span', 'ano', ano));
      porAno[ano].forEach(function (m) {
        var a = el('a', null, MESES[+m.month.slice(5) - 1].slice(0, 3).toLowerCase());
        a.href = '#' + m.month;
        a.addEventListener('click', function () { abertos.add(m.month); anosAbertos.add(ano); desenhar(); });
        l.appendChild(a);
      });
      periodo.appendChild(l);
    });
    periodo.hidden = !anos.length;

    linha.textContent = '';
    if (!anos.length) {
      linha.appendChild(el('p', 'pg-vazio', 'Ainda não há versões publicadas.'));
      return;
    }
    anos.forEach(function (ano) {
      var ms = porAno[ano], aberto = anosAbertos.has(ano);
      var nVers = ms.reduce(function (t, m) { return t + m.releases.length; }, 0);
      var sec = el('section', 'dv-ano');
      var cab = el('div', 'dv-ano-cabeca');
      cab.appendChild(el('h2', null, ano));
      var alt = el('button', 'dv-texto-botao', (aberto ? 'Recolher ' : 'Mostrar ') + ano);
      alt.type = 'button';
      alt.addEventListener('click', function () { aberto ? anosAbertos.delete(ano) : anosAbertos.add(ano); desenhar(); });
      cab.appendChild(alt);
      sec.appendChild(cab);
      if (!aberto) {
        sec.appendChild(el('span', 'dv-resumo-ano', plural(ms.length, 'mês', 'meses') + ' · ' + plural(nVers, 'versão', 'versões')));
      } else {
        ms.forEach(function (m) { sec.appendChild(mes(m, ano)); });
      }
      linha.appendChild(sec);
    });
  }

  function mes(m, ano) {
    var exp = abertos.has(m.month), n = m.releases.length;
    var art = el('article', 'dv-mes');
    art.id = m.month;
    var marco = el('button', 'dv-mes-marco');
    marco.type = 'button';
    marco.setAttribute('aria-expanded', exp ? 'true' : 'false');
    marco.appendChild(el('span', 'nome', MESES[+m.month.slice(5) - 1]));
    var sub = el('span', 'ano', ano);
    sub.appendChild(icone(exp ? 'expand_less' : 'expand_more'));
    marco.appendChild(sub);
    var alternar = function () { exp ? abertos.delete(m.month) : abertos.add(m.month); desenhar(); };
    marco.addEventListener('click', alternar);
    art.appendChild(marco);

    var corpo = el('div', 'dv-mes-corpo');
    if (exp) {
      m.releases.forEach(function (r) {
        var v = el('div', 'dv-versao');
        v.id = idVersao(r.version);
        var cabeca = el('div', 'dv-versao-cabeca');
        var link = el('a', null, 'v' + r.version);
        link.href = '#' + v.id;
        cabeca.appendChild(link);
        cabeca.appendChild(el('span', null, dataBR(r.date)));
        v.appendChild(cabeca);
        var ul = el('ul');
        (r.changes || []).forEach(function (x) { ul.appendChild(el('li', null, typeof x === 'string' ? x : x.text)); });
        v.appendChild(ul);
        corpo.appendChild(v);
      });
      if (!n) corpo.appendChild(el('span', 'dv-sem', 'Sem novas versões neste mês.'));
    } else {
      var ver = el('button', 'dv-ver', n ? 'Ver ' + plural(n, 'versão', 'versões') + ' · ' + m.releases.map(function (r) { return 'v' + r.version; }).join(', ') : 'Sem novas versões neste mês');
      ver.type = 'button';
      ver.addEventListener('click', alternar);
      corpo.appendChild(ver);
    }
    art.appendChild(corpo);
    return art;
  }

  fetch('/api/public/desenvolvimento').then(function (r) {
    if (!r.ok) throw new Error(r.status);
    return r.json();
  }).then(function (d) {
    dados = { meses: (d.meses || []).slice().sort(function (a, b) { return b.month.localeCompare(a.month); }), atualizadoEm: d.atualizadoEm };
    dados.meses.slice(0, 2).forEach(function (m) { abertos.add(m.month); });
    var anoAtual = dados.meses[0] ? dados.meses[0].month.slice(0, 4) : '';
    anosAbertos.add(anoAtual);
    var h = decodeURIComponent(location.hash.slice(1));
    var alvo = dados.meses.find(function (m) { return m.month === h || m.releases.some(function (r) { return idVersao(r.version) === h; }); });
    if (alvo) { abertos.add(alvo.month); anosAbertos.add(alvo.month.slice(0, 4)); }
    desenhar();
    if (d.atualizadoEm) document.getElementById('dv-atualizado').textContent = 'Atualizado em ' + dataBR(d.atualizadoEm);
    if (alvo) { var e = document.getElementById(h); if (e) e.scrollIntoView(); }
  }).catch(function () {
    linha.textContent = '';
    linha.appendChild(el('p', 'pg-vazio', 'Não consegui carregar o histórico agora. Tente de novo em alguns minutos.'));
  });
})();
