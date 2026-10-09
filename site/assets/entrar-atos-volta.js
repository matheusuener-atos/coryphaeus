/* A pagina de volta do "Entrar com Atos" (/entrar-atos/): a Atos manda para
   ca o codigo; aqui ele vira o id_token (POST https://atos.dev.br/oauth/token,
   com o code_verifier que assets/entrar-atos.js guardou) e o token vai para a
   pagina que pediu - pelo BroadcastChannel, se ela abriu esta numa janela, ou
   pelo sessionStorage, na volta da pagina inteira. */
(function () {
  "use strict";
  var ATOS = "https://atos.dev.br";
  var CANAL = "pavlvs-entrar-atos";
  var q = new URLSearchParams(location.search);
  var state = q.get("state") || "";
  var msg = document.getElementById("atos-msg");
  var guardado = null;
  try {
    guardado = JSON.parse(localStorage.getItem("atos-pkce:" + state) || "null");
    localStorage.removeItem("atos-pkce:" + state);
    // Restos de tentativas que nao voltaram (mais de 1 hora).
    for (var i = localStorage.length - 1; i >= 0; i--) {
      var k = localStorage.key(i);
      if (k && k.indexOf("atos-pkce:") === 0) {
        try { if (Date.now() - JSON.parse(localStorage.getItem(k)).quando > 3600e3) localStorage.removeItem(k); } catch (e) { localStorage.removeItem(k); }
      }
    }
  } catch (e) {}

  function entregar(d) {
    d.state = state;
    var popup = Boolean(window.opener) || window.name === "atos-entrar";
    if (popup) {
      if (window.BroadcastChannel) new BroadcastChannel(CANAL).postMessage(d);
      try { localStorage.setItem(CANAL, JSON.stringify(d)); localStorage.removeItem(CANAL); } catch (e) {}
      msg.textContent = d.erro ? "Não deu para entrar: " + d.erro + ". Pode fechar esta janela." : "Pronto. Pode fechar esta janela.";
      setTimeout(function () { window.close(); }, 300);
      return;
    }
    try { sessionStorage.setItem("atos-token", JSON.stringify(d)); } catch (e) {}
    location.replace(guardado && guardado.volta && guardado.volta.indexOf(location.origin + "/") === 0 ? guardado.volta : "/minha-conta/");
  }

  function corpo(token) {
    try { var p = token.split(".")[1]; return JSON.parse(decodeURIComponent(escape(atob(p.replace(/-/g, "+").replace(/_/g, "/"))))); } catch (e) { return {}; }
  }

  if (q.get("error")) { entregar({ erro: q.get("error") === "access_denied" ? "access_denied" : (q.get("error_description") || q.get("error")) }); return; }
  if (!guardado) { entregar({ erro: "o pedido de entrada venceu ou foi aberto em outro navegador: tente de novo" }); return; }
  if (q.get("iss") !== ATOS) { entregar({ erro: "a resposta não veio da Atos" }); return; }

  fetch(ATOS + "/oauth/token", {
    method: "POST",
    headers: { "content-type": "application/x-www-form-urlencoded" },
    body: new URLSearchParams({ grant_type: "authorization_code", code: q.get("code") || "", redirect_uri: location.origin + "/entrar-atos/", client_id: "pavlvs-site", code_verifier: guardado.verifier }).toString(),
  }).then(function (r) { return r.json(); }).then(function (d) {
    if (!d.id_token) { entregar({ erro: d.error_description || "a Atos não confirmou a entrada" }); return; }
    // O nonce prova que o token e deste pedido (o Worker ainda confere a assinatura).
    if (corpo(d.id_token).nonce !== guardado.nonce) { entregar({ erro: "a resposta não é deste pedido" }); return; }
    entregar({ id_token: d.id_token });
  }, function () { entregar({ erro: "sem conexão com a Atos" }); });
})();
