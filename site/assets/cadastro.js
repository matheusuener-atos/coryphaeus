/* A pagina de cadastro (paulus.ia.br/cadastro): entrar com o Google, os dados
   do escritorio, o plano e o pagamento no Mercado Pago, pelo Worker
   (worker/ia.js, /api/ia/planos e /api/ia/site/*). O id_token do Google vale
   uma hora e fica so nesta aba (sessionStorage): e com ele que a pagina sabe,
   na volta do Mercado Pago, de quem e a assinatura. */
(function () {
  "use strict";

  // O cliente OAuth web do PAULUS (o mesmo da equipe). Identificador de
  // cliente nao e segredo; https://paulus.ia.br precisa estar entre as
  // origens JavaScript autorizadas dele no Google Cloud.
  var CLIENTE_GOOGLE = "834374999044-278vmq8hd7th777q084u0rthand7e1jn.apps.googleusercontent.com";
  var CHAVE = "pv-cadastro-token";
  var $ = function (id) { return document.getElementById(id); };
  var estado = { planos: [], escolhido: "escritorio", token: "", conta: null };

  function brl(v) { return Number(v).toLocaleString("pt-BR", { style: "currency", currency: "BRL", maximumFractionDigits: 0 }); }
  function milhoes(t) { return (t / 1e6).toLocaleString("pt-BR", { maximumFractionDigits: 1 }) + " milhões de tokens"; }
  function perguntas(t) { return "~" + (Math.round(t / 3500 / 100) * 100).toLocaleString("pt-BR") + " perguntas por mês"; }
  function esc(t) { return String(t == null ? "" : t).replace(/[&<>"']/g, function (c) { return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]; }); }

  function mostrarErro(id, texto) {
    var el = $(id);
    el.textContent = texto || "";
    el.hidden = !texto;
  }

  async function pedir(caminho, corpo) {
    var r = await fetch(caminho, corpo ? { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(corpo) } : {});
    var dados = {};
    try { dados = await r.json(); } catch (e) { dados = {}; }
    if (!r.ok) {
      var erro = new Error(dados.erro || "o site não respondeu (" + r.status + ")");
      erro.status = r.status;
      throw erro;
    }
    return dados;
  }

  /* ------------------------------------------------------------ planos */

  function desenharPlanos() {
    var travado = estado.conta && estado.conta.plano_vigente;
    $("cd-planos").innerHTML = estado.planos.map(function (p) {
      var on = p.id === estado.escolhido;
      return '<button type="button" class="cd-plano' + (on ? " on" : "") + '" role="radio" aria-checked="' + on + '" data-plano="' + esc(p.id) + '"' +
        (travado ? " disabled" : "") + ">" +
        '<span class="cd-plano-nome">' + esc(p.nome) + "</span>" +
        '<span class="cd-plano-valor">' + brl(p.valor) + "<small>/mês</small></span>" +
        '<span class="cd-plano-tokens">' + milhoes(p.tokens) + "</span>" +
        '<span class="cd-plano-uso">' + perguntas(p.tokens) + "</span></button>";
    }).join("");
    $("cd-planos").querySelectorAll("[data-plano]").forEach(function (b) {
      b.onclick = function () { estado.escolhido = b.dataset.plano; desenharPlanos(); atualizarBotao(); };
    });
  }

  function atualizarBotao() {
    var p = estado.planos.filter(function (x) { return x.id === estado.escolhido; })[0];
    $("cd-pagar-texto").textContent = p ? "Assinar o " + p.nome + " · " + brl(p.valor) + "/mês" : "Ir para o pagamento";
  }

  async function carregarPlanos() {
    try {
      var d = await pedir("/api/ia/planos");
      estado.planos = d.planos || [];
      if (d.recarga) {
        $("cd-recarga").textContent = "Os tokens valem por ciclo de um mês. Uma pergunta sobre documentos gasta, em média, uns 3.500 tokens. " +
          "Se acabarem antes, a recarga de " + milhoes(d.recarga.tokens) + " sai por " + brl(d.recarga.valor) + ", no Pix, e não vence na renovação.";
      }
      desenharPlanos();
      atualizarBotao();
    } catch (e) {
      $("cd-planos").innerHTML = '<p class="pg-vazio">Não consegui ler os planos agora: ' + esc(e.message) + ". Tente de novo em instantes.</p>";
    }
  }

  /* ------------------------------------------------------------- conta */

  function mostrarConta(conta) {
    estado.conta = conta;
    $("cd-conta-texto").innerHTML = "Entrou como <b>" + esc(conta.email) + "</b>. " +
      '<button type="button" class="cd-trocar" id="cd-trocar">Usar outra conta</button>';
    $("cd-trocar").onclick = sair;
    $("cd-google").hidden = true;
    var c = conta.cadastro || {};
    if (c.nome_escritorio && !$("cd-nome").value) $("cd-nome").value = c.nome_escritorio;
    if (c.documento && !$("cd-documento").value) $("cd-documento").value = mascararDocumento(c.documento);
    if (c.telefone && !$("cd-telefone").value) $("cd-telefone").value = mascararTelefone(c.telefone);
    if (c.oab && !$("cd-oab").value) $("cd-oab").value = c.oab;
    if (conta.plano && conta.plano.id) estado.escolhido = conta.plano.id;
    var ativa = conta.plano_vigente;
    $("cd-form").hidden = Boolean(ativa);
    $("cd-pronto").hidden = !ativa;
    if (ativa) {
      mostrarErro("cd-conta-erro", "");
      var fim = conta.ciclo && conta.ciclo.fim ? new Date(conta.ciclo.fim).toLocaleDateString("pt-BR") : "";
      $("cd-pronto-titulo").textContent = conta.cortesia ? "Plano de cortesia ativo" : "Assinatura ativa";
      $("cd-pronto-texto").textContent = "Plano " + (conta.plano || {}).nome + (fim ? ", ciclo até " + fim : "") + ". " +
        "Agora é só baixar o PAVLVS e entrar com " + conta.email + ".";
    }
    desenharPlanos();
    atualizarBotao();
  }

  async function entrar(token) {
    mostrarErro("cd-conta-erro", "");
    try {
      var conta = await pedir("/api/ia/site/entrar", { id_token: token });
      estado.token = token;
      try { sessionStorage.setItem(CHAVE, token); } catch (e) { /* sem a aba guardar, entra de novo na volta */ }
      mostrarConta(conta);
      return conta;
    } catch (e) {
      if (e.status === 401) {
        try { sessionStorage.removeItem(CHAVE); } catch (x) { /* nada guardado */ }
        estado.token = "";
      }
      mostrarErro("cd-conta-erro", e.status === 401 ? "A confirmação do Google venceu. Entre de novo." : "Não consegui entrar: " + e.message);
      return null;
    }
  }

  function sair() {
    try { sessionStorage.removeItem(CHAVE); } catch (e) { /* nada guardado */ }
    estado.token = "";
    estado.conta = null;
    $("cd-form").hidden = true;
    $("cd-pronto").hidden = true;
    $("cd-google").hidden = false;
    $("cd-conta-texto").textContent = "A conta do PAVLVS é a sua conta Google: é com ela que você entra no programa depois. Nenhuma senha a mais.";
    if (window.google && google.accounts && google.accounts.id) google.accounts.id.disableAutoSelect();
    desenharPlanos();
  }

  function iniciarGoogle() {
    if (!(window.google && google.accounts && google.accounts.id)) { setTimeout(iniciarGoogle, 300); return; }
    google.accounts.id.initialize({
      client_id: CLIENTE_GOOGLE,
      callback: function (r) { if (r && r.credential) entrar(r.credential); },
      ux_mode: "popup",
      context: "signup",
    });
    google.accounts.id.renderButton($("cd-google"), { theme: "outline", size: "large", text: "continue_with", shape: "pill", locale: "pt-BR" });
  }

  /* ------------------------------------------------------- o formulario */

  function digitos(t) { return String(t || "").replace(/\D/g, ""); }
  function mascararDocumento(t) {
    var d = digitos(t).slice(0, 14);
    if (d.length <= 11) return d.replace(/^(\d{3})(\d)/, "$1.$2").replace(/^(\d{3})\.(\d{3})(\d)/, "$1.$2.$3").replace(/\.(\d{3})(\d{1,2})$/, ".$1-$2");
    return d.replace(/^(\d{2})(\d)/, "$1.$2").replace(/^(\d{2})\.(\d{3})(\d)/, "$1.$2.$3").replace(/\.(\d{3})(\d)/, ".$1/$2").replace(/(\d{4})(\d{1,2})$/, "$1-$2");
  }
  function mascararTelefone(t) {
    var d = digitos(t).slice(0, 11);
    if (d.length < 3) return d;
    return "(" + d.slice(0, 2) + ") " + (d.length > 10 ? d.slice(2, 7) + "-" + d.slice(7) : d.slice(2, 6) + (d.length > 6 ? "-" + d.slice(6) : ""));
  }

  async function pagar(ev) {
    ev.preventDefault();
    mostrarErro("cd-form-erro", "");
    if (!estado.token) { mostrarErro("cd-form-erro", "Entre com o Google primeiro."); return; }
    if (!$("cd-aceite").checked) { mostrarErro("cd-form-erro", "Para assinar, aceite os Termos de uso e a Política de privacidade."); return; }
    var botao = $("cd-pagar");
    botao.disabled = true;
    try {
      var r = await pedir("/api/ia/site/cadastro", {
        id_token: estado.token, nome_escritorio: $("cd-nome").value, documento: $("cd-documento").value,
        telefone: $("cd-telefone").value, oab: $("cd-oab").value, aceite: true, plano: estado.escolhido,
      });
      if (!r.link) throw new Error("o Mercado Pago não devolveu a página de pagamento");
      window.location.href = r.link;
    } catch (e) {
      botao.disabled = false;
      if (e.status === 401) { sair(); mostrarErro("cd-conta-erro", "A confirmação do Google venceu. Entre de novo e confira os dados."); return; }
      mostrarErro("cd-form-erro", e.message.charAt(0).toUpperCase() + e.message.slice(1) + ".");
    }
  }

  /* --------------------------------------------- a volta do Mercado Pago */

  async function conferirVolta(token) {
    // O aviso do Mercado Pago pode chegar uns segundos depois da volta.
    for (var i = 0; i < 6; i++) {
      var conta;
      try { conta = await pedir("/api/ia/site/situacao", { id_token: token }); } catch (e) { return entrar(token); }
      estado.token = token;
      mostrarConta(conta);
      if (conta.plano_vigente) return conta;
      $("cd-conta-erro").hidden = false;
      $("cd-conta-erro").textContent = "Conferindo o pagamento no Mercado Pago…";
      await new Promise(function (ok) { setTimeout(ok, 5000); });
    }
    mostrarErro("cd-conta-erro", "O Mercado Pago ainda não confirmou o cartão. Se você concluiu o pagamento, recarregue esta página em alguns minutos.");
    return null;
  }

  document.addEventListener("DOMContentLoaded", function () {
    carregarPlanos();
    iniciarGoogle();
    $("cd-form").addEventListener("submit", pagar);
    $("cd-documento").addEventListener("input", function () { this.value = mascararDocumento(this.value); });
    $("cd-telefone").addEventListener("input", function () { this.value = mascararTelefone(this.value); });
    var guardado = "";
    try { guardado = sessionStorage.getItem(CHAVE) || ""; } catch (e) { guardado = ""; }
    if (guardado) {
      if (/[?&]voltou=1/.test(location.search)) conferirVolta(guardado); else entrar(guardado);
    }
  });
})();
