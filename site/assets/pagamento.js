/* A pagina de pagamento (paulus.ia.br/cadastro/pagamento): o bloco de cartao
   do Mercado Pago (Card Payment Brick) e a cobranca pelo Worker
   (worker/ia.js, /api/ia/mp-config, /api/ia/site/oferta e /api/ia/site/pagar).

   O cartao e digitado nos quadros do Mercado Pago; desta pagina sai so o token
   que ele gera. O valor vem do servidor (oferta), nunca do bloco. Mensal: a
   assinatura no cartao, sem parcelas. Anual: o ano em ate 12 parcelas. O
   id_token do Google e o da pagina de cadastro (sessionStorage, uma hora). */
(function () {
  "use strict";

  var CHAVE = "pv-cadastro-token";
  var $ = function (id) { return document.getElementById(id); };
  var params = new URLSearchParams(location.search);
  var pedido = {
    plano: params.get("plano") || "",
    periodo: params.get("periodo") === "anual" ? "anual" : "mensal",
    cupom: params.get("cupom") || "",
  };
  var token = "";
  var controle = null;
  // A mesma chave numa nova tentativa do mesmo pagamento nao cobra duas vezes;
  // depois de uma recusa (cartao novo, token novo), outra chave.
  var idempotencia = novaChave();

  function novaChave() {
    try { return crypto.randomUUID(); } catch (e) { return String(Date.now()) + "-" + Math.random().toString(36).slice(2, 12); }
  }
  function brl(v) { return Number(v).toLocaleString("pt-BR", { style: "currency", currency: "BRL", minimumFractionDigits: Number(v) % 1 ? 2 : 0 }); }
  function frase(t) { t = String(t || ""); return t.charAt(0).toUpperCase() + t.slice(1) + (/[.!?]$/.test(t) ? "" : "."); }

  function estado(texto) {
    var el = $("pg-estado");
    el.textContent = texto || "";
    el.hidden = !texto;
  }
  function erro(texto) {
    var el = $("pg-erro");
    el.textContent = texto ? frase(texto) : "";
    el.hidden = !texto;
  }

  async function pedir(caminho, corpo) {
    var r = await fetch(caminho, corpo
      ? { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(corpo), cache: "no-store" }
      : { cache: "no-store" });
    var dados = {};
    try { dados = await r.json(); } catch (e) { dados = {}; }
    if (!r.ok) {
      var e = new Error(dados.erro || "o site não respondeu (" + r.status + ")");
      e.status = r.status;
      e.dados = dados;
      throw e;
    }
    return dados;
  }

  function voltarAoCadastro(motivo) {
    var ida = "../?plano=" + encodeURIComponent(pedido.plano) + "&periodo=" + pedido.periodo;
    $("pg-voltar").href = ida;
    estado("");
    erro(motivo);
  }

  /* ---------------------------------------------------------- pronto */

  function pronto(r) {
    if (controle) { try { controle.unmount(); } catch (e) { /* ja saiu */ } controle = null; }
    $("cardPaymentBrick_container").hidden = true;
    $("pg-total").hidden = true;
    estado("");
    erro("");
    var c = r.conta || {};
    var nome = (c.plano || {}).nome || "";
    if (r.situacao === "in_process") {
      $("pg-pronto-titulo").textContent = "Pagamento em análise";
      $("pg-pronto-texto").textContent = frase(r.mensagem || "o Mercado Pago está analisando o pagamento; o plano entra assim que for aprovado") +
        " Você pode fechar esta página: o PAVLVS confere sozinho.";
    } else if (r.periodo === "anual") {
      var ate = c.pago_ate ? new Date(c.pago_ate).toLocaleDateString("pt-BR") : "";
      $("pg-pronto-titulo").textContent = "Ano pago";
      $("pg-pronto-texto").textContent = "Plano " + nome + " anual" + (ate ? ", pago até " + ate : "") + ". Agora é só baixar o PAVLVS e entrar com " + (c.email || "a sua conta Google") + ".";
    } else {
      $("pg-pronto-titulo").textContent = "Assinatura ativa";
      $("pg-pronto-texto").textContent = "Plano " + nome + ", cobrado todo mês no cartão. Agora é só baixar o PAVLVS e entrar com " + (c.email || "a sua conta Google") + ".";
    }
    $("pg-pronto").hidden = false;
    $("pg-voltar").hidden = true;
  }

  /* ------------------------------------------------------ o bloco */

  /* As cores do site (as variaveis do :root, do tema claro ou do escuro) nas
     variaveis que o bloco do Mercado Pago aceita (customVariables). O botao
     Pagar fica como os do site: a tinta como fundo, o fundo como letra. */
  function coresDoSite() {
    var css = getComputedStyle(document.documentElement);
    var v = function (nome) { return css.getPropertyValue(nome).trim(); };
    return {
      formBackgroundColor: v("--panel"),
      inputBackgroundColor: v("--bg"),
      textPrimaryColor: v("--ink"),
      textSecondaryColor: v("--ink2"),
      baseColor: v("--ink"),
      baseColorFirstVariant: v("--ink2"),
      baseColorSecondVariant: v("--ink3"),
      buttonTextColor: v("--bg"),
      outlinePrimaryColor: v("--line3"),
      outlineSecondaryColor: v("--line"),
      errorColor: v("--erro"),
      successColor: v("--ok"),
      borderRadiusSmall: "6px",
      borderRadiusMedium: "8px",
      borderRadiusLarge: "10px",
    };
  }

  var montado = null;  // a chave e a oferta, para remontar quando o tema muda

  async function montar(publicKey, oferta) {
    montado = { publicKey: publicKey, oferta: oferta };
    var anual = oferta.periodo === "anual";
    $("pg-plano").textContent = "Plano " + oferta.plano.nome + (anual ? " · anual" : " · mensal");
    $("pg-valor").textContent = brl(oferta.valor) + (anual ? "/ano" : "/mês");
    $("pg-detalhe").textContent = anual
      ? "à vista ou em até 12 vezes no cartão de crédito; os juros do parcelamento são de quem parcela"
      : "cobrado todo mês no cartão de crédito" + (oferta.cupom ? " (com o cupom " + oferta.cupom.codigo + ")" : "");
    $("pg-total").hidden = false;
    $("pg-selo").textContent = anual ? "o ano, em até 12×" : "cobrança mensal";

    var mp = new window.MercadoPago(publicKey, { locale: "pt-BR" });
    var escuro = document.documentElement.getAttribute("data-theme") !== "light";
    var settings = {
      initialization: { amount: oferta.valor, payer: { email: oferta.email } },
      customization: {
        visual: { style: { theme: escuro ? "dark" : "default", customVariables: coresDoSite() } },
        paymentMethods: { minInstallments: 1, maxInstallments: oferta.parcelas_max },
      },
      callbacks: {
        onReady: function () { estado(""); },
        // Volta uma Promise que so termina depois da resposta do servidor:
        // sem isso, o bloco fica carregando para sempre.
        onSubmit: function (formData) {
          erro("");
          estado("Processando o pagamento…");
          return new Promise(function (resolve, reject) {
            pedir("/api/ia/site/pagar", { id_token: token, plano: pedido.plano, periodo: pedido.periodo, cupom: pedido.cupom,
              idempotencia: idempotencia, cartao: formData })
              .then(function (r) { resolve(); pronto(r); })
              .catch(function (e) {
                estado("");
                if (e.status === 401) { voltarAoCadastro("a confirmação do Google venceu: volte, entre com o Google de novo e pague"); reject(); return; }
                // Recusado (cartao, banco, risco): a proxima tentativa e outra compra.
                if (e.status === 402 || e.status === 400) idempotencia = novaChave();
                erro(e.message);
                reject();
              });
          });
        },
        onError: function (e) {
          console.error(e);
          estado("");
          erro("o bloco de pagamento do Mercado Pago não carregou. Se houver bloqueador de anúncios, libere este site e recarregue a página");
        },
      },
    };
    controle = await mp.bricks().create("cardPayment", "cardPaymentBrick_container", settings);
  }

  async function iniciar() {
    try { token = sessionStorage.getItem(CHAVE) || ""; } catch (e) { token = ""; }
    if (!pedido.plano) { voltarAoCadastro("escolha o plano na página de assinatura"); return; }
    if (!token) { voltarAoCadastro("entre com o Google na página de assinatura antes de pagar"); return; }
    if (typeof window.MercadoPago !== "function") {
      estado("");
      erro("o MercadoPago.js não carregou. Se houver bloqueador de anúncios, libere este site e recarregue a página");
      return;
    }
    try {
      var config = await pedir("/api/ia/mp-config");
      var oferta = await pedir("/api/ia/site/oferta", { id_token: token, plano: pedido.plano, periodo: pedido.periodo, cupom: pedido.cupom });
      if (!oferta.cadastro_completo) { voltarAoCadastro("preencha os dados do escritório antes de pagar"); return; }
      await montar(config.publicKey, oferta);
    } catch (e) {
      if (e.status === 401) { voltarAoCadastro("a confirmação do Google venceu: volte e entre com o Google de novo"); return; }
      estado("");
      erro(e.message);
    }
  }

  // Trocou o tema: o bloco e montado de novo com as cores do tema novo (as
  // variaveis sao lidas na montagem). Depois de pago, nao ha bloco.
  new MutationObserver(function () {
    if (!controle || !montado) return;
    try { controle.unmount(); } catch (e) { /* ja saiu */ }
    controle = null;
    montar(montado.publicKey, montado.oferta);
  }).observe(document.documentElement, { attributes: true, attributeFilter: ["data-theme"] });

  // Saiu da pagina: o bloco e desmontado (o Mercado Pago pede).
  window.addEventListener("pagehide", function () {
    if (controle) { try { controle.unmount(); } catch (e) { /* ja saiu */ } controle = null; }
  });
  document.addEventListener("DOMContentLoaded", iniciar);
})();
