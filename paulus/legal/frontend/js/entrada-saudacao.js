/* ------------------------------------------- a saudacao das telas de entrar */
/*
   "Paulus está te esperando." no alto de toda tela de entrar (de fora, o
   convite, a trava do programa) e, embaixo, a frase do banco das telas de
   entrar (src/saudacao.py, saudar_entrada; config/saudacoes_entrada.json) -
   a mesma regra da saudacao do assistente, so com a hora, o dia e o
   calendario. O mesmo jeito de aparecer da saudacao (js/78-chamada-da-vez.js):
   o bloco nasce apagado, a frase chega e ele aparece devagar; ao trocar de
   passo, a frase sai e a nova entra.

   Fica fora do index.html de proposito: as telas de entrar carregam so isto
   (src/acesso/politicas.py, SEM_SESSAO). O bloco:

     <div class="marca abrindo" data-entrada="entrar">
       <h1 data-es-titulo>Paulus está te esperando.</h1>
       <p data-es-frase>frase de reserva</p>
     </div>
*/
(function () {
  "use strict";
  var VISTAS = "paulus.saudacoesEntrada";
  var TROCA_MS = 450;
  var RESERVA_MS = 1500;

  function lerVistas() {
    try { return JSON.parse(localStorage.getItem(VISTAS) || "[]") || []; } catch (e) { return []; }
  }
  function guardarVistas(ids) {
    try { localStorage.setItem(VISTAS, JSON.stringify(lerVistas().concat(ids || []).slice(-40))); } catch (e) { /* sem memoria: repete mais */ }
  }

  function pedir(tela, extras) {
    var q = new URLSearchParams({ tela: tela, recentes: lerVistas().slice(-40).join(",") });
    ["nome", "escritorio", "provedor"].forEach(function (k) { if (extras && extras[k]) q.set(k, extras[k]); });
    return fetch("/api/saudacao/entrada?" + q.toString(), { credentials: "same-origin" })
      .then(function (r) { return r.ok ? r.json() : null; })
      .catch(function () { return null; });
  }

  function partes(bloco) {
    return { titulo: bloco.querySelector("[data-es-titulo]"), frase: bloco.querySelector("[data-es-frase]") };
  }

  function escrever(bloco, d) {
    var p = partes(bloco);
    if (d.titulo && p.titulo) p.titulo.textContent = d.titulo;
    if (d.subtitulo && p.frase) p.frase.textContent = d.subtitulo;
    guardarVistas(d.ids);
  }

  // O texto novo ja no lugar, ainda apagado: so no quadro seguinte o
  // esmaecido sai, e ele aparece devagar.
  function revelar(bloco) {
    void bloco.offsetWidth;
    requestAnimationFrame(function () { requestAnimationFrame(function () { bloco.classList.remove("abrindo", "saindo"); }); });
  }

  /* A abertura: a frase do banco, ou a de reserva se ela nao vier logo. */
  function abrir(bloco, tela, extras) {
    if (!bloco) return Promise.resolve();
    bloco.dataset.entrada = tela;
    var feito = false;
    var reserva = setTimeout(function () { if (!feito) { feito = true; revelar(bloco); } }, RESERVA_MS);
    return pedir(tela, extras).then(function (d) {
      if (d && bloco.dataset.entrada === tela) {
        if (feito) return trocarPara(bloco, function () { escrever(bloco, d); });
        escrever(bloco, d);
      }
      if (!feito) { feito = true; clearTimeout(reserva); revelar(bloco); }
    });
  }

  function trocarPara(bloco, aplicar) {
    var parado = document.documentElement.classList.contains("sem-animacao") ||
      (window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches);
    if (parado || bloco.classList.contains("abrindo")) { aplicar(); revelar(bloco); return Promise.resolve(); }
    bloco.classList.add("saindo");
    return new Promise(function (ok) {
      setTimeout(function () { aplicar(); revelar(bloco); ok(); }, TROCA_MS);
    });
  }

  /* Outro passo (o codigo, a chave, o erro): a frase sai e a nova entra. */
  function trocar(bloco, tela, extras) {
    if (!bloco || bloco.dataset.entrada === tela) return Promise.resolve();
    bloco.dataset.entrada = tela;
    return pedir(tela, extras).then(function (d) {
      if (bloco.dataset.entrada !== tela) return;
      return trocarPara(bloco, function () {
        if (d) escrever(bloco, d);
        else if (extras && extras.reserva) partes(bloco).frase.textContent = extras.reserva;
      });
    });
  }

  /* Um texto que nao e do banco (o motivo de um erro): o mesmo esmaecer. */
  function dizer(bloco, texto) {
    if (!bloco) return Promise.resolve();
    bloco.dataset.entrada = "";
    return trocarPara(bloco, function () { partes(bloco).frase.textContent = texto; });
  }

  window.EntradaSaudacao = { abrir: abrir, trocar: trocar, dizer: dizer };
})();
