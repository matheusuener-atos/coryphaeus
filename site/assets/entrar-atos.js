/* "Entrar com Atos" (09/10/2026): a Conta Atos, ao lado do "Entrar com o
   Google" (o cadastro e a Minha conta). No lugar do formulario de e-mail e
   senha que ficava aqui (assets/conta-senha.js): a senha agora so e digitada
   em atos.dev.br, e o PAVLVS recebe o id_token da Atos (ES256), que o Worker
   confere como confere o do Google (donoDoToken, worker/identidade.js).

   O fluxo e OpenID Connect com PKCE, cliente "pavlvs-site": o botao abre
   atos.dev.br/entrar numa janela; la a pessoa entra e permite; a Atos volta a
   /entrar-atos/, que troca o codigo pelo id_token e o entrega a esta pagina
   (BroadcastChannel, mesma origem). Sem janela (bloqueada pelo navegador), a
   pagina inteira vai e volta, e o token chega pelo sessionStorage.

   EntrarAtos.montar(elemento, { aoEntrar(id_token, {email, nome}), ingles }) */
(function () {
  "use strict";
  var ATOS = "https://atos.dev.br";
  var VOLTA = location.origin + "/entrar-atos/";
  var CANAL = "pavlvs-entrar-atos";

  function b64url(bytes) {
    var s = "";
    for (var i = 0; i < bytes.length; i++) s += String.fromCharCode(bytes[i]);
    return btoa(s).replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/, "");
  }
  function aleatorio(n) { return b64url(crypto.getRandomValues(new Uint8Array(n))); }
  function desafio(verifier) {
    return crypto.subtle.digest("SHA-256", new TextEncoder().encode(verifier)).then(function (h) { return b64url(new Uint8Array(h)); });
  }
  function corpo(token) {
    try { var p = token.split(".")[1]; return JSON.parse(decodeURIComponent(escape(atob(p.replace(/-/g, "+").replace(/_/g, "/"))))); } catch (e) { return {}; }
  }
  function guardar(k, v) { try { localStorage.setItem(k, v); } catch (e) {} }

  function montar(raiz, op) {
    op = op || {};
    if (!raiz) return;
    var t = function (pt, en) { return op.ingles ? en : pt; };
    raiz.innerHTML = '<button type="button" class="atos-botao"><span class="atos-a" aria-hidden="true">A</span><span>' + t("Entrar com Atos", "Sign in with Atos") + "</span></button>" +
      '<p class="erro-campo atos-erro" role="alert" hidden></p>';
    var botao = raiz.querySelector(".atos-botao");
    var erro = raiz.querySelector(".atos-erro");
    var esperando = "";

    function falhou(msg) { erro.textContent = msg; erro.hidden = false; botao.disabled = false; }
    function chegou(d) {
      if (!d || !esperando || d.state !== esperando) return;
      esperando = "";
      botao.disabled = false;
      if (d.erro) { if (d.erro !== "access_denied") falhou(d.erro); return; }
      erro.hidden = true;
      var c = corpo(d.id_token);
      op.aoEntrar(d.id_token, { email: c.email || "", nome: c.name || "" });
    }
    if (window.BroadcastChannel) new BroadcastChannel(CANAL).onmessage = function (e) { chegou(e.data); };
    // Sem BroadcastChannel (navegador antigo): o aviso pelo localStorage.
    window.addEventListener("storage", function (e) {
      if (e.key === CANAL && e.newValue) try { chegou(JSON.parse(e.newValue)); } catch (x) {}
    });

    // Volta da ida e volta da pagina inteira (janela bloqueada).
    try {
      var guardado = sessionStorage.getItem("atos-token");
      if (guardado) {
        sessionStorage.removeItem("atos-token");
        var g = JSON.parse(guardado);
        esperando = g.state;
        setTimeout(function () { chegou(g); }, 0);
      }
    } catch (e) {}

    botao.addEventListener("click", function () {
      erro.hidden = true;
      botao.disabled = true;
      var verifier = aleatorio(48), state = aleatorio(16), nonce = aleatorio(16);
      desafio(verifier).then(function (ch) {
        guardar("atos-pkce:" + state, JSON.stringify({ verifier: verifier, nonce: nonce, volta: location.href, quando: Date.now() }));
        var url = ATOS + "/entrar?" + new URLSearchParams({
          client_id: "pavlvs-site", redirect_uri: VOLTA, response_type: "code", scope: "openid email profile",
          state: state, nonce: nonce, code_challenge: ch, code_challenge_method: "S256",
        }).toString();
        esperando = state;
        var w = 480, h = 700;
        var janela = window.open(url, "atos-entrar", "popup=yes,width=" + w + ",height=" + h + ",left=" + Math.max(0, (screen.width - w) / 2) + ",top=" + Math.max(0, (screen.height - h) / 2));
        if (!janela) { location.assign(url); return; }
        // Fechou a janela sem terminar: o botao volta.
        var vigia = setInterval(function () {
          if (!janela.closed) return;
          clearInterval(vigia);
          // A pagina de volta avisa e fecha: da tempo de o aviso chegar antes de desistir.
          setTimeout(function () { if (esperando === state) { esperando = ""; botao.disabled = false; } }, 2000);
        }, 700);
      }, function () { falhou(t("este navegador não consegue entrar com a Atos", "this browser can't sign in with Atos")); });
    });
  }

  window.EntrarAtos = { montar: montar, CANAL: CANAL };
})();
