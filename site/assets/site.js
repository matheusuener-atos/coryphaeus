/* PAULUS - site publico. So tema claro/escuro e menu no celular. */
(function () {
  var raiz = document.documentElement;

  function temaAtual() {
    return raiz.getAttribute('data-theme') === 'dark' ? 'escuro' : 'claro';
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
    function fechar() {
      nav.classList.remove('aberta');
      menu.setAttribute('aria-expanded', 'false');
      menu.querySelector('.icon').textContent = 'menu';
    }
    menu.addEventListener('click', function () {
      var abrir = !nav.classList.contains('aberta');
      nav.classList.toggle('aberta', abrir);
      menu.setAttribute('aria-expanded', abrir ? 'true' : 'false');
      menu.querySelector('.icon').textContent = abrir ? 'close' : 'menu';
    });
    nav.querySelectorAll('a').forEach(function (a) { a.addEventListener('click', fechar); });
    document.addEventListener('keydown', function (e) { if (e.key === 'Escape') fechar(); });
  }
})();
