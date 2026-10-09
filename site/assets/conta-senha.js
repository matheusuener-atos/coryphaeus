/* A conta PAVLVS por e-mail e senha, ao lado do "Entrar com o Google" (o
   cadastro e a Minha conta). Fala com o Worker (worker/identidade.js,
   /api/id/*): criar a conta (com a senha repetida e o codigo que chega por
   e-mail), entrar, e "Esqueci a senha" (codigo por e-mail e a senha nova,
   repetida). No fim entrega o token ao aoEntrar(token, {email, nome}) da
   pagina, que o usa como usaria o id_token do Google.

   PavlvsSenha.montar(elemento, { aoEntrar, ingles, modo }) */
(function () {
  "use strict";
  var EN = {
    "E-mail": "Email", "Senha": "Password", "Entrar": "Sign in", "Esqueci a senha": "Forgot password", "Criar conta": "Create account",
    "Nome": "Name", "Confirmar a senha": "Confirm password", "Pelo menos 10 caracteres, com letras e números.": "At least 10 characters, with letters and numbers.",
    "Código": "Code", "Confirmar": "Confirm", "Reenviar o código": "Resend the code", "Voltar": "Back",
    "Enviar o código": "Send the code", "Nova senha": "New password", "Confirmar a nova senha": "Confirm the new password", "Trocar a senha": "Change password",
    "Já tem conta? Entrar": "Already have an account? Sign in", "ou com e-mail e senha": "or with email and password",
    "Mostrar a senha": "Show password", "Esconder a senha": "Hide password",
    "as duas senhas não são iguais": "the two passwords don't match", "a senha precisa ter pelo menos 10 caracteres": "the password needs at least 10 characters",
    "use letras e números na senha": "use letters and numbers in the password", "confira o e-mail": "check the email", "digite o código de 6 dígitos": "type the 6-digit code",
    "e-mail ou senha não conferem": "email or password don't match", "o código não confere": "the code doesn't match", "o código venceu: peça outro": "the code expired: ask for another",
    "muitas tentativas erradas com este e-mail: espere 15 minutos e tente de novo": "too many wrong attempts with this email: wait 15 minutes and try again",
    "sem conexão com o servidor": "no connection to the server", "digite a senha": "type the password", "Código reenviado.": "Code sent again.",
  };
  function montar(raiz, op) {
    op = op || {};
    var t = function (s) { return op.ingles && EN[s] ? EN[s] : s; };
    var esc = function (s) { return String(s == null ? "" : s).replace(/[&<>"']/g, function (c) { return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]; }); };
    var S = { modo: op.modo || "entrar", email: "", nome: "", erro: "", nota: "", ocupado: false };
    var id = "cs" + Math.random().toString(36).slice(2, 7);

    function campo(nome, rotulo, tipo, extra) {
      var senha = tipo === "password";
      return '<label class="campo"><span class="rotulo">' + t(rotulo) + '</span><span class="caixa-campo' + (nome === "codigo" ? " mono" : "") + '">' +
        '<input id="' + id + "-" + nome + '" name="' + nome + '" type="' + tipo + '" ' + (extra || "") + ">" +
        (senha ? '<button type="button" class="cs-olho" data-cs="olho" aria-label="' + t("Mostrar a senha") + '"><span class="icon" aria-hidden="true">visibility</span></button>' : "") +
        "</span></label>";
    }
    function botao(texto) {
      return '<button type="submit" class="btn-duplo largo"><span>' + t(texto) + "</span></button>";
    }
    function link(acao, texto) { return '<button type="button" class="btn-texto" data-cs="' + acao + '">' + t(texto) + "</button>"; }
    var REGRA = '<span class="nota-campo">' + t("Pelo menos 10 caracteres, com letras e números.") + "</span>";

    function html() {
      var h = "";
      if (S.modo === "entrar") {
        h = campo("email", "E-mail", "email", 'autocomplete="email" maxlength="200" required value="' + esc(S.email) + '"') +
          campo("senha", "Senha", "password", 'autocomplete="current-password" maxlength="200" required') + botao("Entrar") +
          '<div class="cs-links">' + link("esqueci", "Esqueci a senha") + link("criar", "Criar conta") + "</div>";
      } else if (S.modo === "criar") {
        h = campo("nome", "Nome", "text", 'autocomplete="name" maxlength="80" value="' + esc(S.nome) + '"') +
          campo("email", "E-mail", "email", 'autocomplete="email" maxlength="200" required value="' + esc(S.email) + '"') +
          campo("senha", "Senha", "password", 'autocomplete="new-password" maxlength="200" required') +
          campo("senha2", "Confirmar a senha", "password", 'autocomplete="new-password" maxlength="200" required') + REGRA + botao("Criar conta") +
          '<div class="cs-links">' + link("entrar", "Já tem conta? Entrar") + "</div>";
      } else if (S.modo === "codigo" || S.modo === "redefinir") {
        h = '<p class="nota-campo cs-aviso">' + esc(op.ingles ? "We sent a 6-digit code to " + S.email + ". It is valid for 15 minutes." : "Enviamos um código de 6 dígitos para " + S.email + ". Ele vale 15 minutos.") + "</p>" +
          campo("codigo", "Código", "text", 'inputmode="numeric" autocomplete="one-time-code" maxlength="6" pattern="[0-9]{6}" required') +
          (S.modo === "redefinir" ? campo("senha", "Nova senha", "password", 'autocomplete="new-password" maxlength="200" required') +
            campo("senha2", "Confirmar a nova senha", "password", 'autocomplete="new-password" maxlength="200" required') + REGRA : "") +
          botao(S.modo === "redefinir" ? "Trocar a senha" : "Confirmar") +
          '<div class="cs-links">' + link("reenviar", "Reenviar o código") + link(S.modo === "redefinir" ? "esqueci" : "criar", "Voltar") + "</div>";
      } else if (S.modo === "esqueci") {
        h = campo("email", "E-mail", "email", 'autocomplete="email" maxlength="200" required value="' + esc(S.email) + '"') + botao("Enviar o código") +
          '<div class="cs-links">' + link("entrar", "Voltar") + "</div>";
      }
      // .cs-erro fica so para o que nao e de um campo (sem conexao, limite de tentativas, e-mail que nao saiu):
      // o erro de um campo e a borda vermelha dele (PvCampos, em site.js).
      return '<form class="campos cs-form" novalidate>' + h + '<p class="erro-campo cs-erro" role="alert" hidden></p><p class="nota-campo cs-nota" role="status" hidden></p></form>';
    }
    var P = window.PvCampos;
    function cid(n) { return id + "-" + n; }
    // Os campos de cada passo, na ordem em que aparecem (o primeiro errado recebe o foco).
    var CAMPOS = { entrar: ["email", "senha"], criar: ["email", "senha", "senha2"], codigo: ["codigo"], redefinir: ["codigo", "senha", "senha2"], esqueci: ["email"] };
    function regraSenha(s) {
      if (String(s).length < 10) return t("a senha precisa ter pelo menos 10 caracteres");
      if (!/[a-zA-ZÀ-ÿ]/.test(s) || !/[0-9]/.test(s)) return t("use letras e números na senha");
      return String(s).length > 200 ? t("a senha precisa ter pelo menos 10 caracteres") : true;
    }
    if (P) {
      var R = {};
      R[cid("email")] = P.regra("email", t("confira o e-mail"));
      R[cid("senha")] = function (v) { return S.modo === "entrar" ? (v ? true : t("digite a senha")) : regraSenha(v); };
      R[cid("senha2")] = function (v) { return v && v === valor("senha") ? true : t("as duas senhas não são iguais"); };
      R[cid("codigo")] = P.regra("codigo", t("digite o código de 6 dígitos"));
      P.regras(R);
    }
    // Erro do servidor que e de um campo: a borda vermelha no lugar do texto.
    var DO_CAMPO = [[/e-mail ou senha não conferem/, ["email", "senha"]], [/^confira o e-mail/, ["email"]], [/o código (não confere|venceu)/, ["codigo"]],
      [/^(a senha precisa|use letras e números)/, ["senha"]]];
    function erroDeCampo(msg) {
      if (!P) return false;
      return P.porFrase(msg, DO_CAMPO.map(function (p) { return [p[0], p[1].map(cid)]; }), { frase: t(String(msg || "")) });
    }
    // So a mensagem e o botao mudam: o que a pessoa digitou (as senhas) fica.
    function avisar() {
      var e = raiz.querySelector(".cs-erro"), n = raiz.querySelector(".cs-nota"), b = raiz.querySelector('.cs-form button[type="submit"]');
      if (e) { e.textContent = S.erro; e.hidden = !S.erro; }
      if (n) { n.textContent = S.nota; n.hidden = !S.nota; }
      if (b) b.disabled = S.ocupado;
    }
    function pintar(foco) {
      if (P) P.esquecer(id + "-");
      raiz.innerHTML = html();
      avisar();
      var f = raiz.querySelector("input" + (foco ? '[name="' + foco + '"]' : ""));
      if (f && foco !== false) f.focus();
    }
    function valor(n) { var i = raiz.querySelector('[name="' + n + '"]'); return i ? i.value : ""; }
    function regra(senha, senha2) {
      if (String(senha).length < 10) return "a senha precisa ter pelo menos 10 caracteres";
      if (!/[a-zA-ZÀ-ÿ]/.test(senha) || !/[0-9]/.test(senha)) return "use letras e números na senha";
      if (senha !== senha2) return "as duas senhas não são iguais";
      return "";
    }
    function cap(s) { s = t(String(s || "")); return s.charAt(0).toUpperCase() + s.slice(1) + (/[.!?]$/.test(s) ? "" : "."); }
    async function pedir(rota, corpo) {
      var r;
      try { r = await fetch("/api/id/" + rota, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(corpo), credentials: "same-origin" }); }
      catch (e) { throw new Error("sem conexão com o servidor"); }
      var d = {}; try { d = await r.json(); } catch (e) { d = {}; }
      if (!r.ok) throw new Error(d.erro || ("o servidor respondeu " + r.status));
      return d;
    }
    async function enviar() {
      if (S.ocupado) return;
      S.erro = ""; S.nota = "";
      var email = (valor("email") || S.email).trim().toLowerCase();
      if (S.modo !== "codigo" && S.modo !== "redefinir") S.email = email;
      if (S.modo === "criar") S.nome = valor("nome").trim();
      var corpo, rota, falha = "";
      if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(S.email)) falha = "confira o e-mail";
      if (S.modo === "entrar") { rota = "entrar"; corpo = { email: S.email, senha: valor("senha") }; }
      else if (S.modo === "criar") { falha = falha || regra(valor("senha"), valor("senha2")); rota = "cadastrar"; corpo = { email: S.email, senha: valor("senha"), nome: S.nome }; }
      else if (S.modo === "esqueci") { rota = "esqueci"; corpo = { email: S.email }; }
      else if (S.modo === "codigo") { rota = "confirmar"; corpo = { email: S.email, codigo: valor("codigo").trim() }; falha = /^\d{6}$/.test(corpo.codigo) ? "" : "digite o código de 6 dígitos"; }
      else if (S.modo === "redefinir") {
        rota = "redefinir"; corpo = { email: S.email, codigo: valor("codigo").trim(), senha: valor("senha") };
        falha = !/^\d{6}$/.test(corpo.codigo) ? "digite o código de 6 dígitos" : regra(valor("senha"), valor("senha2"));
      }
      // Os campos errados ficam vermelhos (e o primeiro recebe o foco); o texto so aparece sem o PvCampos.
      if (P && !P.conferir(CAMPOS[S.modo].map(cid))) { avisar(); return; }
      if (falha) { if (!P || !erroDeCampo(falha)) S.erro = cap(falha); avisar(); return; }
      S.ocupado = true; avisar();
      try {
        var d = await pedir(rota, corpo);
        S.ocupado = false;
        if (S.modo === "criar") { S.criando = corpo; S.modo = "codigo"; pintar("codigo"); return; }
        if (S.modo === "esqueci") { S.modo = "redefinir"; pintar("codigo"); return; }
        avisar();
        if (d.token && op.aoEntrar) op.aoEntrar(d.token, { email: d.email || S.email, nome: d.nome || "" });
      } catch (e) {
        S.ocupado = false;
        if (!erroDeCampo(e.message)) S.erro = cap(e.message);
        avisar();
      }
    }
    raiz.addEventListener("submit", function (ev) { ev.preventDefault(); enviar(); });
    // A confirmacao da senha acompanha a senha: mudou uma, a outra (se ja foi tocada) e conferida de novo.
    raiz.addEventListener("input", function () { if (P) P.reaplicar(raiz); });
    raiz.addEventListener("click", function (ev) {
      var b = ev.target.closest("[data-cs]"); if (!b) return;
      var a = b.getAttribute("data-cs");
      if (a === "olho") {
        var i = b.parentNode.querySelector("input"), ver = i.type === "password";
        i.type = ver ? "text" : "password";
        b.setAttribute("aria-label", t(ver ? "Esconder a senha" : "Mostrar a senha"));
        b.querySelector(".icon").textContent = ver ? "visibility_off" : "visibility";
        return;
      }
      if (a === "reenviar") {
        S.erro = ""; S.nota = "";
        var r = S.modo === "redefinir" ? pedir("esqueci", { email: S.email }) : S.criando ? pedir("cadastrar", S.criando) : null;
        if (r) r.then(function () { S.nota = t("Código reenviado."); avisar(); }, function (e) { S.erro = cap(e.message); avisar(); });
        return;
      }
      var email = valor("email"); if (email) S.email = email.trim().toLowerCase();
      S.erro = ""; S.nota = ""; S.modo = a; pintar();
    });
    pintar(false);
    return { modo: function (m) { S.modo = m; S.erro = ""; S.nota = ""; pintar(false); } };
  }
  window.PavlvsSenha = { montar: montar };
})();
