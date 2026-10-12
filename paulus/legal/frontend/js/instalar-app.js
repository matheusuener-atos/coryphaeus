/* ------------------------------------------ o app instalavel do escritorio */
/*
   12/10/2026: o escritorio de fora (<nome>.paulus.ia.br) e um app instalavel
   (PWA), e nao um aplicativo de loja. So este endereco vira app: o manifesto
   e o service worker sao do PAULUS do escritorio (src/api.py, /manifest.webmanifest
   e /sw.js), e o escopo e o endereco dele. paulus.ia.br continua site - o app
   nao pode comecar la, porque o escritorio e outro endereco (o app abriria o
   escritorio fora dele, com a barra do navegador e, no iPhone, sem a sessao).

   Carregado pela tela de entrar de fora (entrar.html) e pelo programa
   (index.html). Na janela do computador (127.0.0.1) nao faz nada.

   1. Aberto como app (display-mode standalone, ou navigator.standalone no
      iPhone): nada a pedir.
   2. No navegador: pede para instalar. Onde o navegador oferece
      (beforeinstallprompt: Chrome, Edge, Samsung), o botao Instalar abre o
      pedido dele; no iPhone/iPad e nos outros, os passos pelo menu.
   3. Ja instalado, mas aberto no navegador (getInstalledRelatedApps, onde
      existe): lembra de abrir pelo icone, uma vez por sessao.
   "Agora nao" adia por 3 dias, neste aparelho.
*/
(function () {
  "use strict";
  if (!/\.paulus\.ia\.br$/.test(location.hostname)) return;

  var ADIADO = "paulus.app.adiado";
  var ADIAR_MS = 3 * 24 * 3600 * 1000;
  var LEMBRADO = "paulus.app.lembrado";

  // O manifesto e os icones entram so aqui (e nao no <head>): a janela do
  // computador nao e app e nao pede o manifesto.
  function noHead(tag, attrs) {
    var el = document.createElement(tag);
    for (var k in attrs) el.setAttribute(k, attrs[k]);
    document.head.appendChild(el);
  }
  noHead("link", { rel: "manifest", href: "/manifest.webmanifest" });
  noHead("link", { rel: "apple-touch-icon", href: "/img/paulus-icone-512.png" });
  noHead("meta", { name: "theme-color", content: "#131312" });
  noHead("meta", { name: "apple-mobile-web-app-title", content: "PAVLVS" });
  noHead("meta", { name: "mobile-web-app-capable", content: "yes" });
  noHead("meta", { name: "apple-mobile-web-app-status-bar-style", content: "black" });

  if ("serviceWorker" in navigator) {
    navigator.serviceWorker.register("/sw.js", { scope: "/" }).catch(function () { /* sem o worker, so a tela de erro do tunel fica a da Cloudflare */ });
  }

  function comoApp() {
    var m = window.matchMedia;
    return navigator.standalone === true || !!(m && (m("(display-mode: standalone)").matches ||
      m("(display-mode: fullscreen)").matches || m("(display-mode: minimal-ui)").matches ||
      m("(display-mode: window-controls-overlay)").matches));
  }
  if (comoApp()) return;

  function ler(chave, guarda) {
    try { return (guarda || localStorage).getItem(chave); } catch (e) { return null; }
  }
  function gravar(chave, valor, guarda) {
    try { (guarda || localStorage).setItem(chave, valor); } catch (e) { /* sem memoria: pede de novo na proxima */ }
  }
  function adiado() {
    var t = Number(ler(ADIADO) || 0);
    return t && Date.now() - t < ADIAR_MS;
  }

  var ua = navigator.userAgent || "";
  var ios = /iPad|iPhone|iPod/.test(ua) || (/Macintosh/.test(ua) && navigator.maxTouchPoints > 1);
  var celular = ios || /Android|Mobile/.test(ua);
  var firefox = /Firefox\//.test(ua);
  var safariMac = !ios && /Macintosh/.test(ua) && /Version\/\d+.*Safari/.test(ua) && !/Chrome|Chromium|Edg\//.test(ua);

  var pedidoDoNavegador = null;
  var folha = null;

  function passosPeloMenu() {
    if (ios) return "No Safari, toque em <b>Compartilhar</b> (o quadrado com a seta para cima) e depois em <b>Adicionar à Tela de Início</b>.";
    if (safariMac) return "No Safari, abra o menu <b>Arquivo</b> e escolha <b>Adicionar ao Dock</b>.";
    if (firefox && !celular) return "O Firefox no computador não instala apps. Abra este endereço no <b>Chrome</b> ou no <b>Edge</b> e instale por lá.";
    if (celular) return "Abra o menu do navegador (<b>⋮</b>) e toque em <b>Instalar app</b> ou <b>Adicionar à tela inicial</b>.";
    return "Na barra de endereço, clique no ícone de <b>instalar</b>, ou abra o menu do navegador (<b>⋮</b>) e escolha <b>Instalar PAVLVS</b>.";
  }

  function fechar(adiar) {
    if (adiar) gravar(ADIADO, String(Date.now()));
    if (!folha) return;
    var f = folha;
    folha = null;
    f.classList.remove("aberta");
    setTimeout(function () { if (f.parentNode) f.parentNode.removeChild(f); }, 200);
    document.removeEventListener("keydown", aoTeclar);
  }
  function aoTeclar(ev) { if (ev.key === "Escape") fechar(true); }

  // tipo: "instalar" (o navegador instala), "passos" (pelo menu), "instalado"
  function mostrar(tipo) {
    if (!document.body) { document.addEventListener("DOMContentLoaded", function () { mostrar(tipo); }); return; }
    if (folha) fechar(false);
    var titulo, texto, sim, nao;
    if (tipo === "instalado") {
      titulo = "Abra pelo app";
      texto = "<p>O PAVLVS deste escritório já está instalado neste aparelho. Abra pelo ícone dele: no app, o escritório fica sem a barra do navegador e com a tela inteira.</p>";
      sim = "";
      nao = "Continuar aqui";
    } else {
      titulo = "Instale o PAVLVS do escritório";
      texto = "<p>O acesso ao escritório é feito pelo app. Ele não vem de loja nenhuma: é este endereço, instalado no " +
        (celular ? "celular" : "computador") + ", com ícone próprio e sem a barra do navegador.</p>" +
        (tipo === "passos" ? "<p>" + passosPeloMenu() + "</p>" : "");
      sim = tipo === "instalar" ? "Instalar" : "Entendi";
      nao = "Agora não";
    }
    var fundo = document.createElement("div");
    fundo.className = "app-inst-fundo";
    fundo.dataset.tipo = tipo;
    fundo.innerHTML = '<div class="app-inst" role="dialog" aria-modal="true" aria-labelledby="app-inst-titulo">' +
      '<div class="app-inst-topo"><img src="/img/paulus-icone-512.png" alt=""><h2 id="app-inst-titulo"></h2></div>' + texto +
      '<div class="app-inst-botoes"><button type="button" class="app-inst-nao"></button>' +
      (sim ? '<button type="button" class="app-inst-sim"></button>' : "") + "</div></div>";
    fundo.querySelector("h2").textContent = titulo;
    fundo.querySelector(".app-inst-nao").textContent = nao;
    var botaoSim = fundo.querySelector(".app-inst-sim");
    if (botaoSim) botaoSim.textContent = sim;
    fundo.querySelector(".app-inst-nao").onclick = function () {
      if (tipo === "instalado") { gravar(LEMBRADO, "1", sessionStorage); fechar(false); } else fechar(true);
    };
    if (botaoSim) botaoSim.onclick = function () {
      if (tipo !== "instalar" || !pedidoDoNavegador) { fechar(true); return; }
      var p = pedidoDoNavegador;
      pedidoDoNavegador = null;
      p.prompt();
      p.userChoice.then(function (escolha) {
        fechar(!(escolha && escolha.outcome === "accepted"));
      }, function () { fechar(true); });
    };
    fundo.addEventListener("click", function (ev) { if (ev.target === fundo) fechar(tipo !== "instalado"); });
    document.body.appendChild(fundo);
    folha = fundo;
    document.addEventListener("keydown", aoTeclar);
    requestAnimationFrame(function () { fundo.classList.add("aberta"); });
    (botaoSim || fundo.querySelector(".app-inst-nao")).focus();
  }

  window.addEventListener("beforeinstallprompt", function (ev) {
    ev.preventDefault();
    pedidoDoNavegador = ev;
    // Chegou depois dos passos pelo menu: o botao Instalar resolve sozinho.
    if (!adiado() && (!folha || folha.dataset.tipo === "passos")) mostrar("instalar");
  });
  window.addEventListener("appinstalled", function () { fechar(false); });

  // O navegador que instala avisa (beforeinstallprompt) logo depois de ler o
  // manifesto; o que nao avisa, ou ja tem o app, fica para depois de 2,5 s.
  setTimeout(function () {
    if (pedidoDoNavegador || folha) return;
    var verInstalado = navigator.getInstalledRelatedApps ? navigator.getInstalledRelatedApps().catch(function () { return []; }) : Promise.resolve([]);
    verInstalado.then(function (apps) {
      if (pedidoDoNavegador || folha) return;
      if (apps && apps.length) {
        if (ler(LEMBRADO, sessionStorage) !== "1") mostrar("instalado");
        return;
      }
      if (!adiado()) mostrar("passos");
    });
  }, 2500);
})();
