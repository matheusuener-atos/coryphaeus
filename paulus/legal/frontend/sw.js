/* ----------------------------------- o service worker do app do escritorio */
/*
   O app instalavel de <nome>.paulus.ia.br (12/10/2026; js/instalar-app.js
   registra, so de fora). Nao guarda nada: toda pagina e todo dado vem do
   PAULUS do escritorio, pelo tunel, a cada abertura.

   O que ele faz e uma coisa so: quando o computador do escritorio esta
   desligado (ou o PAULUS fechado), o tunel responde com a pagina de erro da
   Cloudflare (502, 530...) ou nem responde. No app instalado, isso vira
   uma tela que diz o que aconteceu, em vez de uma pagina em ingles da
   Cloudflare.
*/
"use strict";

self.addEventListener("install", function () { self.skipWaiting(); });
self.addEventListener("activate", function (ev) { ev.waitUntil(self.clients.claim()); });

var FORA_DO_AR = [502, 503, 504, 520, 521, 522, 523, 524, 525, 526, 527, 530];

function paginaForaDoAr() {
  var html = '<!doctype html><html lang="pt-BR"><head><meta charset="utf-8">' +
    '<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">' +
    '<title>PAVLVS — escritório fora do ar</title><style>' +
    ':root{color-scheme:dark}html,body{margin:0;height:100%}' +
    'body{display:flex;align-items:center;justify-content:center;background:#131312;color:#f2f1ec;' +
    'font:400 15px/1.55 Manrope,system-ui,sans-serif;padding:24px;box-sizing:border-box}' +
    'main{max-width:400px}h1{font-weight:500;font-size:22px;margin:0 0 12px}p{color:#a8a69e;margin:0 0 12px}' +
    'a{display:inline-block;margin-top:12px;padding:10px 18px;border:1px solid rgba(242,241,236,.14);border-radius:12px;' +
    'color:#f2f1ec;text-decoration:none;background:#1a1a1a}' +
    '@media (prefers-color-scheme:light){:root{color-scheme:light}body{background:#f6f5f1;color:#1c1c1a}p{color:#55544f}' +
    'a{color:#1c1c1a;background:#f6f5f1;border-color:rgba(28,28,26,.14)}}' +
    '</style></head><body><main><h1>O escritório não respondeu.</h1>' +
    '<p>O PAVLVS mora no computador do escritório. Ele pode estar desligado, sem internet ou com o PAVLVS fechado.</p>' +
    '<p>Quando ele voltar, é só tentar de novo.</p><a href="/">Tentar de novo</a></main></body></html>';
  return new Response(html, { status: 503, headers: { "content-type": "text/html; charset=utf-8", "cache-control": "no-store" } });
}

self.addEventListener("fetch", function (ev) {
  // Fora das paginas (os dados, os arquivos), o navegador segue sozinho.
  if (ev.request.mode !== "navigate") return;
  ev.respondWith(fetch(ev.request).then(function (resposta) {
    return FORA_DO_AR.indexOf(resposta.status) >= 0 ? paginaForaDoAr() : resposta;
  }, function () {
    return paginaForaDoAr();
  }));
});
