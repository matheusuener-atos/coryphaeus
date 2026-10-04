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

  /* Uma lista no estilo do sistema por cima de um <select> que o CardForm
     preenche e le: o select continua no formulario (invisivel, .pg-nativo); o
     botao mostra a opcao escolhida e o menu escolhe nele, com o evento de
     mudanca. `opcoes()` diz o que o menu mostra ([{valor, texto}]); sem ela,
     as opcoes do proprio select. Teclado: setas, Enter, Esc, Home e End. */
  function combo(select, opcoes) {
    var lista = opcoes || function () {
      return [].slice.call(select.options).filter(function (o) { return o.value; })
        .map(function (o) { return { valor: o.value, texto: o.textContent }; });
    };
    select.classList.add("pg-nativo");
    select.tabIndex = -1;
    var caixa = document.createElement("div");
    caixa.className = "pg-combo";
    var botao = document.createElement("button");
    botao.type = "button";
    botao.className = "pg-combo-botao";
    botao.setAttribute("aria-haspopup", "listbox");
    botao.setAttribute("aria-expanded", "false");
    var rotulo = select.getAttribute("aria-labelledby");
    if (rotulo) botao.setAttribute("aria-labelledby", rotulo);
    botao.innerHTML = '<span></span><span class="icon" aria-hidden="true">expand_more</span>';
    var menu = document.createElement("ul");
    menu.className = "pg-combo-menu";
    menu.setAttribute("role", "listbox");
    menu.hidden = true;
    select.parentNode.insertBefore(caixa, select);
    caixa.appendChild(botao);
    caixa.appendChild(menu);
    caixa.appendChild(select);

    var texto = function () {
      var atual = lista().filter(function (x) { return x.valor === select.value; })[0];
      botao.firstChild.textContent = atual ? atual.texto : lista().length ? "Escolha" : (select.getAttribute("data-vazio") || "");
    };
    var itens = function () { return [].slice.call(menu.children); };
    var focar = function (i) {
      var t = itens();
      if (t.length) t[(i + t.length) % t.length].focus();
    };
    var fechar = function (devolverFoco) {
      menu.hidden = true;
      botao.setAttribute("aria-expanded", "false");
      if (devolverFoco) botao.focus();
    };
    var escolher = function (valor) {
      select.value = valor;
      select.dispatchEvent(new Event("change", { bubbles: true }));
      fechar(true);
    };
    var abrir = function () {
      menu.innerHTML = "";
      lista().forEach(function (x) {
        var li = document.createElement("li");
        li.setAttribute("role", "option");
        li.tabIndex = -1;
        li.textContent = x.texto;
        li.setAttribute("aria-selected", String(x.valor === select.value));
        li.onclick = function () { escolher(x.valor); };
        li.onkeydown = function (e) {
          var i = itens().indexOf(li);
          if (e.key === "ArrowDown") { e.preventDefault(); focar(i + 1); }
          else if (e.key === "ArrowUp") { e.preventDefault(); focar(i - 1); }
          else if (e.key === "Home") { e.preventDefault(); focar(0); }
          else if (e.key === "End") { e.preventDefault(); focar(-1); }
          else if (e.key === "Enter" || e.key === " ") { e.preventDefault(); escolher(x.valor); }
          else if (e.key === "Escape" || e.key === "Tab") { fechar(e.key === "Escape"); }
        };
        menu.appendChild(li);
      });
      if (!menu.children.length) return;
      menu.hidden = false;
      botao.setAttribute("aria-expanded", "true");
      var sel = menu.querySelector('[aria-selected="true"]') || menu.firstChild;
      sel.focus();
      sel.scrollIntoView({ block: "nearest" });
    };
    botao.onclick = function () { if (menu.hidden) abrir(); else fechar(false); };
    botao.onkeydown = function (e) {
      if ((e.key === "ArrowDown" || e.key === "ArrowUp") && menu.hidden) { e.preventDefault(); abrir(); }
    };
    document.addEventListener("click", function (e) { if (!caixa.contains(e.target)) fechar(false); });
    select.addEventListener("change", texto);
    new MutationObserver(texto).observe(select, { childList: true });
    texto();
    return { atualizar: texto };
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
  // A fonte do site carregada dentro dos quadros (eles sao outra pagina, do Mercado Pago).
  var FONTES = [{ src: "https://fonts.googleapis.com/css2?family=Manrope:wght@400;500&display=swap" }];

  var montado = null;  // a chave e a oferta, para remontar quando o tema muda
  var montouEm = 0;    // quando os quadros seguros ficaram prontos
  // As parcelas que o Mercado Pago ofereceu para o cartao digitado (payer_costs
  // do onInstallmentsReceived), ja cortadas no teto do plano.
  var custos = [];
  var listaDeParcelas = null;

  /* O que se liga uma vez so (o tema pode montar o CardForm de novo): as
     listas e o aviso dos juros. */
  function prepararFormulario() {
    var parcelas = $("pg-parcelas");
    // A lista das parcelas mostra as do Mercado Pago ate o teto do plano; o
    // select do CardForm traz todas (ate 18), e o servidor recusa acima do teto.
    listaDeParcelas = combo(parcelas, function () {
      return custos.map(function (c) { return { valor: String(c.installments), texto: c.recommended_message }; });
    });
    combo($("pg-doc-tipo"));
    parcelas.addEventListener("change", mostrarJuros);
  }

  /* O total no cartao e o juro, do proprio Mercado Pago (total_amount da
     parcela escolhida), so no anual. */
  function mostrarJuros() {
    var anual = montado && montado.oferta.periodo === "anual";
    var c = custos.filter(function (x) { return String(x.installments) === $("pg-parcelas").value; })[0];
    if (!anual || !c) { $("pg-juros").textContent = ""; return; }
    var dif = Math.round((c.total_amount - montado.oferta.valor) * 100) / 100;
    $("pg-juros").textContent = dif > 0.009
      ? "Total no cartão: " + brl(c.total_amount) + ", com " + brl(dif) + " de juros do parcelamento."
      : "Sem juros: total de " + brl(c.total_amount) + ".";
  }

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
    var mp = new window.MercadoPago(publicKey, { locale: "pt-BR" });
    var estilo = estiloDosQuadros();
    // Monta com o formulario ja visivel (o Mercado Pago pede quadros com tamanho).
    requestAnimationFrame(function () {
      controle = mp.cardForm({
        amount: String(oferta.valor),
        iframe: true,
        form: {
          id: "pg-form",
          cardNumber: { id: "pg-numero", placeholder: "0000 0000 0000 0000", style: estilo, customFonts: FONTES },
          expirationDate: { id: "pg-validade", placeholder: "MM/AA", style: estilo, customFonts: FONTES },
          securityCode: { id: "pg-codigo", placeholder: "123", style: estilo, customFonts: FONTES },
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
          onInstallmentsReceived: function (e, dados) {
            var teto = montado.oferta.parcelas_max;
            // A resposta e a de getInstallments: uma lista, com as payer_costs no primeiro item.
            var r = Array.isArray(dados) ? dados[0] : dados;
            custos = (!e && r && r.payer_costs ? r.payer_costs : []).filter(function (c) { return c.installments <= teto; });
            listaDeParcelas.atualizar();
            mostrarJuros();
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
      prepararFormulario();
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
    custos = [];
    montar(montado.publicKey, montado.oferta);
  }).observe(document.documentElement, { attributes: true, attributeFilter: ["data-theme"] });

  // Saiu da pagina: o formulario e desmontado.
  window.addEventListener("pagehide", function () {
    if (controle) { try { controle.unmount(); } catch (e) { /* ja saiu */ } controle = null; }
  });
  document.addEventListener("DOMContentLoaded", function () {
    $("pg-fora-botao").addEventListener("click", pagarFora);
    iniciar();
  });
})();
