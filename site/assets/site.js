/* Paulus - site publico. O tema (escuro por padrao; claro se a pessoa
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

/* PvCampos: o estado de cada campo de formulario no site, na Minha conta e no painel (regra do dono,
   08/10/2026). Erro de campo = borda vermelha (.campo-erro), certo = borda verde (.campo-ok), sem texto na
   tela; a frase fica para o leitor de tela (aria-invalid + aria-describedby num .so-leitor). O CSS esta em
   site.css.

   marcar(el, "erro"|"ok"|"", frase)  pinta na hora (el = o input, ou o invólucro .caixa-campo).
   regras({ id: fn(valor, el) })      fn devolve true (certo), uma frase (errado) ou null (sem estado).
   O campo so mostra estado depois de tocado: digitou e saiu, ou tentou enviar (conferir). Ja tocado, ou
   vermelho, atualiza enquanto digita. As regras e o estado ficam por id, entao sobrevivem ao redesenho
   da pagina: depois de trocar o HTML, reaplicar(raiz).
   conferir([ids])                   marca todos como tocados, pinta, foca o primeiro errado; true = tudo certo.
   servidor(id, frase)               erro do servidor que e de um campo: vermelho ate o valor mudar.
   porFrase(msg, [[regex, ids]])     acha o(s) campo(s) pela frase do servidor; true = era de campo.
   esquecer(prefixo)                 zera o estado (um formulario novo com os mesmos ids). */
(function () {
  "use strict";
  var REGRAS = {}, TOCADO = {}, DIGITOU = {}, SERV = {}, seq = 0;

  function caixa(el) {
    if (!el || !el.classList) return null;
    if (el.classList.contains("caixa-campo")) return el;
    return (el.closest && el.closest(".caixa-campo")) || el;
  }
  function entrada(el) {
    if (!el) return null;
    if (/^(INPUT|TEXTAREA|SELECT)$/.test(el.tagName)) return el;
    return el.querySelector ? el.querySelector('input:not([type="hidden"]), textarea, select') : null;
  }
  function frase(t) { t = String(t || "").trim(); if (!t) return ""; return t.charAt(0).toUpperCase() + t.slice(1) + (/[.!?…]$/.test(t) ? "" : "."); }
  function descricao(el, id, ligar) {
    var l = (el.getAttribute("aria-describedby") || "").split(/\s+/).filter(Boolean).filter(function (x) { return x !== id; });
    if (ligar) l.push(id);
    if (l.length) el.setAttribute("aria-describedby", l.join(" ")); else el.removeAttribute("aria-describedby");
  }

  function marcar(el, estado, texto) {
    var cx = caixa(el); if (!cx) return;
    var inp = entrada(el) || entrada(cx), alvo = inp || cx;
    cx.classList.toggle("campo-erro", estado === "erro");
    cx.classList.toggle("campo-ok", estado === "ok");
    if (!alvo.id) alvo.id = "pvc-" + (++seq);
    var sid = alvo.id + "-pv-erro", sr = document.getElementById(sid);
    if (estado === "erro" && texto) {
      if (!sr) { sr = document.createElement("span"); sr.className = "so-leitor"; sr.id = sid; cx.parentNode.insertBefore(sr, cx.nextSibling); }
      if (sr.textContent !== frase(texto)) sr.textContent = frase(texto);
      descricao(alvo, sid, true);
    } else {
      if (sr) sr.parentNode.removeChild(sr);
      descricao(alvo, sid, false);
    }
    if (inp) { if (estado === "erro") inp.setAttribute("aria-invalid", "true"); else inp.removeAttribute("aria-invalid"); }
  }

  function valor(el) { return el.type === "checkbox" ? (el.checked ? "1" : "") : String(el.value == null ? "" : el.value); }
  function estadoDe(el) {
    var id = el.id, v = valor(el), s = SERV[id];
    if (s) {
      if (s.v === v) return ["erro", s.frase];
      // Um erro que marcou varios campos ("e-mail ou senha nao conferem") sai de todos quando um deles muda.
      (s.grupo || [id]).forEach(function (k) { delete SERV[k]; });
      (s.grupo || []).forEach(function (k) { if (k !== id) { var o = document.getElementById(k); if (o) pintar(o); } });
    }
    var f = REGRAS[id];
    if (!f || !TOCADO[id]) return ["", ""];
    var r = f(v, el);
    if (r === true) return ["ok", ""];
    if (r) return ["erro", String(r)];
    return ["", ""];
  }
  function pintar(el) { if (el && el.id) { var s = estadoDe(el); marcar(el, s[0], s[1]); return s[0]; } return ""; }

  function regras(mapa) { Object.keys(mapa).forEach(function (k) { REGRAS[k] = mapa[k]; }); }
  function esquecer(prefixo) {
    [TOCADO, DIGITOU, SERV].forEach(function (o) { Object.keys(o).forEach(function (k) { if (!prefixo || k.indexOf(prefixo) === 0) delete o[k]; }); });
  }
  function reaplicar(raiz) {
    raiz = raiz || document;
    var ids = {}; Object.keys(TOCADO).concat(Object.keys(SERV)).forEach(function (k) { ids[k] = 1; });
    Object.keys(ids).forEach(function (id) { var el = document.getElementById(id); if (el && (raiz === document || raiz.contains(el))) pintar(el); });
  }
  function conferir(ids, op) {
    op = op || {};
    var primeiro = null;
    ids.forEach(function (id) {
      var el = document.getElementById(id); if (!el) return;
      TOCADO[id] = true;
      if (pintar(el) === "erro" && !primeiro) primeiro = el;
    });
    if (primeiro && !op.semFoco) focar(primeiro);
    return !primeiro;
  }
  function focar(el) {
    var f = /^(INPUT|TEXTAREA|SELECT|BUTTON)$/.test(el.tagName) ? el : entrada(el) || el;
    try { f.focus(); } catch (e) { /* sem foco */ }
  }
  function servidor(id, texto, grupo) {
    var el = document.getElementById(id); if (!el) return false;
    SERV[id] = { v: valor(el), frase: texto, grupo: grupo && grupo.length > 1 ? grupo : null }; TOCADO[id] = true; pintar(el);
    return true;
  }
  function porFrase(msg, pares, op) {
    var achou = [];
    (pares || []).forEach(function (p) {
      if (!p[0].test(String(msg || ""))) return;
      var ids = [].concat(p[1]).filter(function (id) { return document.getElementById(id); });
      ids.forEach(function (id) { if (achou.indexOf(id) < 0 && servidor(id, op && op.frase || msg, ids)) achou.push(id); });
    });
    if (achou.length && !(op && op.semFoco)) focar(document.getElementById(achou[0]));
    return achou.length > 0;
  }

  // Digitou e saiu: passa a mostrar estado. O redesenho que devolve o foco ao mesmo campo nao conta como saida.
  document.addEventListener("input", function (ev) {
    var el = ev.target, id = el && el.id; if (!id || !(REGRAS[id] || SERV[id])) return;
    DIGITOU[id] = true;
    if (TOCADO[id] || SERV[id]) pintar(el);
  }, true);
  document.addEventListener("change", function (ev) {
    var el = ev.target, id = el && el.id; if (!id || !REGRAS[id] || !/^(SELECT|INPUT)$/.test(el.tagName) || (el.tagName === "INPUT" && el.type !== "checkbox")) return;
    DIGITOU[id] = true; TOCADO[id] = true; pintar(el);
  }, true);
  document.addEventListener("focusout", function (ev) {
    var id = ev.target && ev.target.id; if (!id || !REGRAS[id]) return;
    setTimeout(function () {
      var el = document.getElementById(id); if (!el || document.activeElement === el || !DIGITOU[id]) return;
      TOCADO[id] = true; pintar(el);
    }, 0);
  }, true);

  // As conferencias que o cliente sabe fazer. Cada uma devolve true ou false; regra() junta com a frase.
  function digitos(v) { return String(v || "").replace(/\D/g, ""); }
  function cpf(c) {
    if (!/^\d{11}$/.test(c) || /^(\d)\1{10}$/.test(c)) return false;
    for (var t = 9; t < 11; t++) { var s = 0; for (var i = 0; i < t; i++) s += Number(c[i]) * (t + 1 - i); if ((s * 10) % 11 % 10 !== Number(c[t])) return false; }
    return true;
  }
  function cnpj(c) {
    if (!/^\d{14}$/.test(c) || /^(\d)\1{13}$/.test(c)) return false;
    for (var n = 12; n <= 13; n++) {
      var pesos = n === 12 ? [5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2] : [6, 5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2], s = 0;
      for (var i = 0; i < n; i++) s += Number(c[i]) * pesos[i];
      var r = s % 11; if ((r < 2 ? 0 : 11 - r) !== Number(c[n])) return false;
    }
    return true;
  }
  function numero(v) { var s = String(v == null ? "" : v).trim(); if (/,/.test(s)) s = s.replace(/\./g, "").replace(",", "."); return s && isFinite(Number(s)) ? Number(s) : NaN; }
  var UFS = "AC AL AP AM BA CE DF ES GO MA MT MS MG PA PB PR PE PI RJ RN RS RO RR SC SP SE TO".split(" ");
  var checa = {
    email: function (v) { return v.length <= 200 && /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(v); },
    senha: function (v) { return v.length >= 10 && v.length <= 200 && /[a-zA-ZÀ-ÿ]/.test(v) && /[0-9]/.test(v); },
    codigo: function (v) { return /^\d{6}$/.test(v); },
    cpf: function (v) { return cpf(digitos(v)); },
    cnpj: function (v) { return cnpj(digitos(v)); },
    cpfCnpj: function (v) { var d = digitos(v); return d.length === 11 ? cpf(d) : cnpj(d); },
    cep: function (v) { return digitos(v).length === 8; },
    telefone: function (v) { var n = digitos(v).length; return n >= 10 && n <= 11; },
    uf: function (v) { return UFS.indexOf(v.toUpperCase()) >= 0; },
    slug: function (v) { return /^[a-z0-9](?:[a-z0-9-]{1,22}[a-z0-9])$/.test(v); },
    preenchido: function (v) { return v.length > 0; },
  };
  // regra(conferencia, frase, opcional): vazio e opcional = sem estado; vazio e obrigatorio = a frase.
  function regra(c, texto, opcional) {
    var f = typeof c === "function" ? c : checa[c];
    return function (v, el) { v = String(v || "").trim(); if (!v) return opcional ? null : texto; return f(v, el) ? true : texto; };
  }
  // faixa(min, max, frase): um numero (com virgula ou ponto) no intervalo.
  function faixa(min, max, texto, opcional) {
    return regra(function (v) { var n = numero(v); return !isNaN(n) && n >= min && n <= max; }, texto, opcional);
  }

  window.PvCampos = { marcar: marcar, regras: regras, esquecer: esquecer, reaplicar: reaplicar, conferir: conferir, servidor: servidor, porFrase: porFrase,
    regra: regra, faixa: faixa, checa: checa, numero: numero, frase: frase };
})();
