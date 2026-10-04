/* A pagina de pagamento (paulus.ia.br/cadastro/pagamento): o formulario do
   cartao (CardForm do MercadoPago.js, com os tres campos do cartao em quadros
   seguros do Mercado Pago) e a cobranca pelo Worker
   (worker/ia.js, /api/ia/mp-config, /api/ia/site/oferta e /api/ia/site/pagar).

   O cartao e digitado nos quadros do Mercado Pago; desta pagina sai so o token
   que ele gera. O valor vem do servidor (oferta), nunca do formulario. Mensal: a
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

  /* O plano B: o formulario nao carregou. O Worker cria a assinatura (ou o
     pagamento do ano) na pagina do Mercado Pago, com o valor conferido la, e a
     pessoa vai para ela; a volta e a pagina de cadastro, que confere. */
  var semFormulario = false;
  function planoB(motivo) {
    if (semFormulario) return;
    semFormulario = true;
    estado("");
    erro(motivo);
    if (token && pedido.plano) $("pg-fora").hidden = false;
  }
  async function pagarFora() {
    var b = $("pg-fora-botao");
    b.disabled = true;
    try {
      var r = await pedir("/api/ia/site/pagar-fora", { id_token: token, plano: pedido.plano, periodo: pedido.periodo, cupom: pedido.cupom });
      if (!r.link || !/^https:\/\/[a-z0-9.-]*mercadopago\.com(\.br)?\//.test(r.link)) throw new Error("o Mercado Pago não devolveu a página de pagamento");
      window.location.assign(r.link);
    } catch (e) {
      b.disabled = false;
      if (e.status === 401) { voltarAoCadastro("a confirmação do Google venceu: volte e entre com o Google de novo"); return; }
      erro(e.message);
    }
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
    $("pg-form").hidden = true;
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

  /* ------------------------------------------------- o formulario */

  /* O estilo do texto dentro dos tres quadros do Mercado Pago (o numero, a
     validade e o codigo): as cores e a fonte do tema do site. */
  function estiloDosQuadros() {
    var css = getComputedStyle(document.documentElement);
    var v = function (nome) { return css.getPropertyValue(nome).trim(); };
    return { color: v("--ink"), placeholderColor: v("--ink3"), fontSize: "14px", fontFamily: "Manrope, system-ui, sans-serif" };
  }

  var montado = null;  // a chave e a oferta, para remontar quando o tema muda
  var montouEm = 0;    // quando os quadros seguros ficaram prontos

  function montar(publicKey, oferta) {
    montado = { publicKey: publicKey, oferta: oferta };
    var anual = oferta.periodo === "anual";
    $("pg-plano").textContent = "Plano " + oferta.plano.nome + (anual ? " · anual" : " · mensal");
    $("pg-valor").textContent = brl(oferta.valor) + (anual ? "/ano" : "/mês");
    $("pg-detalhe").textContent = anual
      ? "à vista ou em até 12 vezes no cartão de crédito; os juros do parcelamento são de quem parcela"
      : "cobrado todo mês no cartão de crédito" + (oferta.cupom ? " (com o cupom " + oferta.cupom.codigo + ")" : "");
    $("pg-total").hidden = false;
    $("pg-selo").textContent = anual ? "o ano, em até 12×" : "cobrança mensal";
    // As parcelas so aparecem no anual; no mensal o seletor fica no formulario
    // (o CardForm precisa dele), escondido, e o servidor cobra sem parcelas.
    $("pg-campo-parcelas").hidden = !anual;
    $("pg-form").hidden = false;
    // O Mercado Pago oferece as parcelas do cartao (ate 18); o plano vai ate
    // parcelas_max, e o servidor recusa acima disso.
    var parcelas = $("pg-parcelas");
    if (!parcelas.dataset.teto) {
      new MutationObserver(function () {
        var teto = Number(parcelas.dataset.teto) || 1;
        [].slice.call(parcelas.options).forEach(function (o) { if (Number(o.value) > teto) o.remove(); });
      }).observe(parcelas, { childList: true });
    }
    parcelas.dataset.teto = String(oferta.parcelas_max);
    // Os juros: cada opcao do Mercado Pago traz o total no cartao entre
    // parenteses; a diferenca para o valor do plano e o juro do parcelamento.
    var juros = function () {
      var o = parcelas.options[parcelas.selectedIndex];
      var m = o && o.textContent.match(/\(R\$\s*([\d.]+,\d{2})\)\s*$/);
      if (!m || !anual) { $("pg-juros").textContent = ""; return; }
      var total = Number(m[1].replace(/\./g, "").replace(",", "."));
      var dif = Math.round((total - oferta.valor) * 100) / 100;
      $("pg-juros").textContent = dif > 0.009
        ? "Total no cartão: " + brl(total) + ", com " + brl(dif) + " de juros do parcelamento."
        : "Sem juros: total de " + brl(total) + ".";
    };
    parcelas.onchange = juros;
    new MutationObserver(juros).observe(parcelas, { childList: true });

    var mp = new window.MercadoPago(publicKey, { locale: "pt-BR" });
    var estilo = estiloDosQuadros();
    // Monta com o formulario ja visivel (o Mercado Pago pede quadros com tamanho).
    requestAnimationFrame(function () {
      controle = mp.cardForm({
        amount: String(oferta.valor),
        iframe: true,
        form: {
          id: "pg-form",
          cardNumber: { id: "pg-numero", placeholder: "0000 0000 0000 0000", style: estilo },
          expirationDate: { id: "pg-validade", placeholder: "MM/AA", style: estilo },
          securityCode: { id: "pg-codigo", placeholder: "123", style: estilo },
          cardholderName: { id: "pg-titular" },
          issuer: { id: "pg-emissor" },
          installments: { id: "pg-parcelas", placeholder: "Parcelas" },
          identificationType: { id: "pg-doc-tipo" },
          identificationNumber: { id: "pg-doc" },
        },
        callbacks: {
          onFormMounted: function (e) {
            estado("");
            if (e) {
              console.error(e);
              planoB("o formulário do cartão não carregou");
            } else {
              montouEm = Date.now();
            }
          },
          onSubmit: function (ev) {
            ev.preventDefault();
            pagar();
          },
          // A bandeira lida dos primeiros digitos: a miniatura do Mercado Pago no lugar do icone.
          onPaymentMethodsReceived: function (e, metodos) {
            var m = !e && metodos && metodos[0];
            var img = $("pg-bandeira");
            if (m && (m.secure_thumbnail || m.thumbnail)) {
              img.src = m.secure_thumbnail || m.thumbnail;
              img.alt = m.name || m.id || "";
              img.hidden = false;
              $("pg-bandeira-icone").hidden = true;
            } else {
              img.hidden = true;
              $("pg-bandeira-icone").hidden = false;
            }
          },
        },
      });
    });
  }

  async function iniciar() {
    try { token = sessionStorage.getItem(CHAVE) || ""; } catch (e) { token = ""; }
    if (!pedido.plano) { voltarAoCadastro("escolha o plano na página de assinatura"); return; }
    if (!token) { voltarAoCadastro("entre com o Google na página de assinatura antes de pagar"); return; }
    if (typeof window.MercadoPago !== "function") {
      planoB("o formulário do cartão não carregou (um bloqueador de anúncios pode ter barrado o Mercado Pago)");
      return;
    }
    try {
      var config = await pedir("/api/ia/mp-config");
      var oferta = await pedir("/api/ia/site/oferta", { id_token: token, plano: pedido.plano, periodo: pedido.periodo, cupom: pedido.cupom });
      if (!oferta.cadastro_completo) { voltarAoCadastro("preencha os dados do escritório antes de pagar"); return; }
      montar(config.publicKey, oferta);
      // Sem os quadros seguros em 15 segundos, o plano B aparece.
      setTimeout(function () {
        if (!montouEm && !$("pg-form").hidden) planoB("o formulário do cartão está demorando para carregar");
      }, 15000);
    } catch (e) {
      if (e.status === 401) { voltarAoCadastro("a confirmação do Google venceu: volte e entre com o Google de novo"); return; }
      estado("");
      erro(e.message);
    }
  }

  /* Pagar: o CardForm gera o token (o cartao vai do quadro direto ao Mercado
     Pago); daqui sai so o token e o que o servidor precisa. O valor e o do
     servidor. */
  var enviando = false;
  async function pagar() {
    if (enviando || !controle) return;
    erro("");
    var d;
    try {
      d = controle.getCardFormData();
    } catch (e) {
      d = null;
    }
    if (!d || !d.token) { erro("confira os dados do cartão: algum campo está incompleto"); return; }
    var anual = montado && montado.oferta.periodo === "anual";
    var cartao = {
      token: d.token,
      issuer_id: d.issuerId,
      payment_method_id: d.paymentMethodId,
      installments: anual ? Number(d.installments) || 1 : 1,
      payer: { identification: { type: d.identificationType, number: d.identificationNumber } },
    };
    enviando = true;
    $("pg-pagar").disabled = true;
    estado("Processando o pagamento…");
    try {
      var r = await pedir("/api/ia/site/pagar", { id_token: token, plano: pedido.plano, periodo: pedido.periodo, cupom: pedido.cupom,
        idempotencia: idempotencia, cartao: cartao });
      pronto(r);
    } catch (e) {
      estado("");
      if (e.status === 401) { voltarAoCadastro("a confirmação do Google venceu: volte, entre com o Google de novo e pague"); return; }
      // Recusado (cartao, banco, risco): a proxima tentativa e outra compra,
      // com outro token - o CardForm gera um novo a cada envio.
      if (e.status === 402 || e.status === 400) idempotencia = novaChave();
      erro(e.message);
    } finally {
      enviando = false;
      $("pg-pagar").disabled = false;
    }
  }

  // Trocou o tema: o formulario e montado de novo, com as cores do tema novo
  // dentro dos quadros (elas sao lidas na montagem). Depois de pago, nao ha.
  new MutationObserver(function () {
    if (!controle || !montado || $("pg-form").hidden) return;
    try { controle.unmount(); } catch (e) { /* ja saiu */ }
    controle = null;
    montar(montado.publicKey, montado.oferta);
  }).observe(document.documentElement, { attributes: true, attributeFilter: ["data-theme"] });

  // Saiu da pagina: o formulario e desmontado.
  window.addEventListener("pagehide", function () {
    if (controle) { try { controle.unmount(); } catch (e) { /* ja saiu */ } controle = null; }
  });
  document.addEventListener("DOMContentLoaded", function () { $("pg-fora-botao").addEventListener("click", pagarFora); });
  document.addEventListener("DOMContentLoaded", iniciar);
})();
