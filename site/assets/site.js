/* PAULUS - site publico. O tema (escuro por padrao; claro se a pessoa
   escolher, guardado em pv-tema, a mesma chave do programa) e o menu no
   celular. */
(function () {
  var raiz = document.documentElement;

  function temaAtual() {
    return raiz.getAttribute('data-theme') === 'light' ? 'claro' : 'escuro';
  }

  function pintarBotao() {
    var escuro = temaAtual() === 'escuro';
    document.querySelectorAll('[data-alternar-tema]').forEach(function (b) {
      var ic = b.querySelector('.icon');
      if (ic) ic.textContent = escuro ? 'light_mode' : 'dark_mode';
      b.setAttribute('aria-label', escuro ? 'Usar tema claro' : 'Usar tema escuro');
      b.setAttribute('title', escuro ? 'Tema claro' : 'Tema escuro');
    });
  }

  document.querySelectorAll('[data-alternar-tema]').forEach(function (b) {
    b.addEventListener('click', function () {
      var t = temaAtual() === 'escuro' ? 'claro' : 'escuro';
      raiz.setAttribute('data-theme', t === 'escuro' ? 'dark' : 'light');
      try { localStorage.setItem('pv-tema', t); } catch (e) {}
      pintarBotao();
    });
  });
  pintarBotao();

  var menu = document.querySelector('[data-menu]');
  var nav = document.getElementById('nav-principal');
  if (menu && nav) {
    var fechar = function () {
      nav.classList.remove('aberta');
      menu.setAttribute('aria-expanded', 'false');
      menu.querySelector('.icon').textContent = 'menu';
    };
    menu.addEventListener('click', function () {
      var abrir = !nav.classList.contains('aberta');
      nav.classList.toggle('aberta', abrir);
      menu.setAttribute('aria-expanded', abrir ? 'true' : 'false');
      menu.querySelector('.icon').textContent = abrir ? 'close' : 'menu';
    });
    nav.querySelectorAll('a').forEach(function (a) { a.addEventListener('click', fechar); });
    document.addEventListener('keydown', function (e) { if (e.key === 'Escape') fechar(); });
  }

  // O sumario das paginas de texto marca a secao que esta na tela.
  var sumario = document.querySelector('.sumario');
  if (sumario && 'IntersectionObserver' in window) {
    var links = {};
    sumario.querySelectorAll('a[href^="#"]').forEach(function (a) { links[a.getAttribute('href').slice(1)] = a; });
    var obs = new IntersectionObserver(function (es) {
      es.forEach(function (e) {
        if (!e.isIntersecting || !links[e.target.id]) return;
        Object.keys(links).forEach(function (k) { links[k].classList.toggle('ativo', k === e.target.id); });
      });
    }, { rootMargin: '-80px 0px -70% 0px' });
    Object.keys(links).forEach(function (id) { var el = document.getElementById(id); if (el) obs.observe(el); });
  }
})();
