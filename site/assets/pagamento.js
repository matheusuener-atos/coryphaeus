/* A pagina de pagamento (paulus.ia.br/cadastro/pagamento): o formulario do
   cartao (CardForm do MercadoPago.js, com os tres campos do cartao em quadros
   seguros do Mercado Pago) e a cobranca pelo Worker
   (worker/ia.js, /api/ia/mp-config, /api/ia/site/oferta e /api/ia/site/pagar).

   O cartao e digitado nos quadros do Mercado Pago; desta pagina sai so o token
   que ele gera. O valor vem do servidor (oferta), nunca do formulario. Mensal: a
   assinatura no cartao, sem parcelas. Anual: o ano em ate 12 parcelas. Ou o
   Pix: o mes avulso (vale um mes e nao renova) ou o ano a vista, com o QR do
   Mercado Pago e a pagina conferindo sozinha (/api/ia/site/pix). O id_token do
   Google e o da pagina de cadastro (sessionStorage, uma hora). */
(function () {
  "use strict";

  var CHAVE = "pv-cadastro-token";
  var $ = function (id) { return document.getElementById(id); };
  var params = new URLSearchParams(location.search);
  var pedido = {
    plano: params.get("plano") || "",
    periodo: params.get("periodo") === "anual" ? "anual" : "mensal",
  };
  var token = "";
  var controle = null;
  var oferta = null;      // a oferta do servidor (valor, meios)
  var meio = "pix";       // "pix" (o primeiro) ou "cartao"
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
    motivoSemFormulario = motivo;
    $("pg-form").hidden = true;
    if (meio !== "cartao") return;
    estado("");
    erro(motivo);
    if (token && pedido.plano) $("pg-fora").hidden = false;
  }
  var motivoSemFormulario = "";
  async function pagarFora() {
    var b = $("pg-fora-botao");
    b.disabled = true;
    try {
      var r = await pedir("/api/ia/site/pagar-fora", { id_token: token, plano: pedido.plano, periodo: pedido.periodo });
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
    var ida = pedido.plano ? "../?plano=" + encodeURIComponent(pedido.plano) + "&periodo=" + pedido.periodo : "../../assinatura/";
    $("pg-voltar").href = ida;
    estado("");
    erro(motivo);
  }

  /* ---------------------------------------------------------- pronto */

  function pronto(r) {
    if (controle) { try { controle.unmount(); } catch (e) { /* ja saiu */ } controle = null; }
    pararPix();
    $("pg-form").hidden = true;
    $("pg-pix").hidden = true;
    $("pg-meios").hidden = true;
    $("pg-meio-nota").hidden = true;
    $("pg-fora").hidden = true;
    $("pg-total").hidden = true;
    estado("");
    erro("");
    var c = r.conta || {};
    var nome = (c.plano || {}).nome || "";
    if (r.situacao === "in_process") {
      $("pg-pronto-titulo").textContent = "Pagamento em análise";
      $("pg-pronto-texto").textContent = frase(r.mensagem || "o Mercado Pago está analisando o pagamento; o plano entra assim que for aprovado") +
        " Você pode fechar esta página: o PAVLVS confere sozinho.";
    } else if (c.periodo === "avulso" || r.periodo === "anual") {
      var ate = c.pago_ate ? new Date(c.pago_ate).toLocaleDateString("pt-BR") : "";
      var mes = c.periodo === "avulso";
      $("pg-pronto-titulo").textContent = mes ? "Mês pago" : "Ano pago";
      $("pg-pronto-texto").textContent = "Plano " + nome + (mes ? ", pago no Pix" : " anual") + (ate ? ", até " + ate : "") + "." +
        (mes ? " Não renova sozinho: para continuar, pague outro mês em paulus.ia.br/assinatura ou assine no cartão." : "") +
        " Agora é só baixar o PAVLVS e entrar com " + (c.email || "a sua conta Google") + ".";
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

  /* O total e o que ele quer dizer, no meio escolhido. */
  function textos() {
    var anual = oferta.periodo === "anual";
    var pix = meio === "pix";
    $("pg-plano").textContent = "Plano " + oferta.plano.nome + (anual ? " · anual" : pix ? " · um mês" : " · mensal");
    $("pg-valor").textContent = brl(oferta.valor) + (anual ? "/ano" : pix ? " por um mês" : "/mês");
    $("pg-detalhe").textContent = pix
      ? (anual ? "à vista no Pix; vale 12 meses, com a cota de cada mês, e não renova sozinho" : "à vista no Pix; vale um mês e não renova sozinho")
      : anual ? "à vista ou em até 12 vezes no cartão de crédito; os juros do parcelamento são de quem parcela"
        : "cobrado todo mês no cartão de crédito";
    $("pg-total").hidden = false;
    $("pg-selo").textContent = pix ? "Pix, à vista" : anual ? "o ano, em até 12×" : "cobrança mensal";
    $("pg-pix-texto").textContent = anual
      ? "O ano é pago de uma vez. O QR vale 30 minutos; o plano entra assim que o Mercado Pago confirmar, em geral em segundos."
      : "Um mês do plano, sem assinatura: vale até o mesmo dia do mês que vem e acaba sozinho, sem cobrança nenhuma. O QR vale 30 minutos; o plano entra assim que o Mercado Pago confirmar.";
  }

  /* Cartao ou Pix: o que o servidor nao permite fica desligado, com o porque. */
  function desenharMeios() {
    var meios = oferta.meios || { cartao: "", pix: "" };
    ["cartao", "pix"].forEach(function (x) {
      var b = $("pg-meio-" + x);
      b.setAttribute("aria-checked", String(meio === x));
      b.classList.toggle("on", meio === x);
      b.disabled = Boolean(meios[x]);
      b.title = meios[x] ? frase(meios[x]) : "";
    });
    var fechado = meios.cartao ? meios.cartao : meios.pix;
    $("pg-meio-nota").textContent = fechado ? (meios.cartao ? "Cartão: " : "Pix: ") + frase(fechado) : "";
    $("pg-meio-nota").hidden = !fechado;
    $("pg-meios").hidden = false;
  }

  function escolherMeio(x) {
    if (x === meio || (oferta.meios || {})[x]) return;
    meio = x;
    erro("");
    estado("");
    desenharMeios();
    textos();
    var pix = meio === "pix";
    $("pg-pix").hidden = !pix;
    $("pg-fora").hidden = pix || !semFormulario || !token;
    $("pg-form").hidden = pix || semFormulario || !montado;
    if (!pix && semFormulario) erro(motivoSemFormulario);
    if (!pix && !montado && !semFormulario) montarCartao();
  }

  function montar(publicKey, oferta) {
    montado = { publicKey: publicKey, oferta: oferta };
    var anual = oferta.periodo === "anual";
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
    if (!pedido.plano) { voltarAoCadastro("escolha o plano na página de planos"); return; }
    if (!token) { voltarAoCadastro("entre com o Google no cadastro antes de pagar"); return; }
    try {
      oferta = await pedir("/api/ia/site/oferta", { id_token: token, plano: pedido.plano, periodo: pedido.periodo });
    } catch (e) {
      if (e.status === 401) { voltarAoCadastro("a confirmação do Google venceu: volte e entre com o Google de novo"); return; }
      estado("");
      erro(e.message);
      return;
    }
    if (!oferta.cadastro_completo) { voltarAoCadastro("preencha os dados do escritório antes de pagar"); return; }
    // Comeca no Pix; com o Pix fechado (a assinatura no cartao ativa, por exemplo), no cartao.
    if ((oferta.meios || {}).pix && !(oferta.meios || {}).cartao) meio = "cartao";
    estado("");
    desenharMeios();
    textos();
    $("pg-pix").hidden = meio !== "pix";
    if (meio === "cartao") montarCartao();
  }

  /* O formulario do cartao: a chave publica e o CardForm. Sem o MercadoPago.js
     (bloqueador, rede), o plano B; o Pix continua. */
  var cartaoPedido = false;
  async function montarCartao() {
    if (cartaoPedido) return;
    cartaoPedido = true;
    if (typeof window.MercadoPago !== "function") {
      planoB("o formulário do cartão não carregou (um bloqueador de anúncios pode ter barrado o Mercado Pago); dá para pagar no Pix");
      return;
    }
    estado("Carregando o formulário do cartão…");
    try {
      var config = await pedir("/api/ia/mp-config");
      prepararFormulario();
      montar(config.publicKey, oferta);
      if (meio !== "cartao") $("pg-form").hidden = true;
      // Sem os quadros seguros em 15 segundos, o plano B aparece.
      setTimeout(function () {
        if (!montouEm) planoB("o formulário do cartão está demorando para carregar");
      }, 15000);
    } catch (e) {
      estado("");
      planoB(e.message);
    }
  }

  /* ---------------------------------------------------------- o Pix */

  var pix = null;        // {pagamento, vence}
  var vigia = null;
  var chavePix = novaChave();

  function pararPix() {
    if (vigia) { clearTimeout(vigia); vigia = null; }
  }

  async function gerarPix() {
    var b = $("pg-pix-gerar");
    b.disabled = true;
    erro("");
    pararPix();
    try {
      var r = await pedir("/api/ia/site/pagar", { id_token: token, plano: pedido.plano, periodo: pedido.periodo,
        meio: "pix", idempotencia: chavePix });
      pix = { pagamento: r.pagamento, vence: Date.parse(r.vence) || Date.now() + 30 * 60 * 1000 };
      $("pg-pix-img").src = r.qr_code_base64 ? "data:image/png;base64," + r.qr_code_base64 : "";
      $("pg-pix-img").hidden = !r.qr_code_base64;
      $("pg-pix-codigo").value = r.qr_code;
      $("pg-pix-qr").hidden = false;
      b.hidden = true;
      $("pg-meios").hidden = true;
      $("pg-meio-nota").hidden = true;
      var hora = new Date(pix.vence).toLocaleTimeString("pt-BR", { hour: "2-digit", minute: "2-digit" });
      $("pg-pix-espera").textContent = "Esperando o pagamento. Este Pix vale até " + hora + "; pode deixar esta página aberta.";
      vigia = setTimeout(conferirPix, 4000);
    } catch (e) {
      b.disabled = false;
      if (e.status === 401) { voltarAoCadastro("a confirmação do Google venceu: volte, entre com o Google de novo e pague"); return; }
      erro(e.message);
    }
  }

  async function conferirPix() {
    vigia = null;
    if (!pix) return;
    try {
      var r = await pedir("/api/ia/site/pix", { id_token: token, pagamento: pix.pagamento });
      if (r.pago) { pronto({ periodo: pedido.periodo, conta: r.conta }); return; }
      if (r.situacao === "cancelled" || r.situacao === "rejected" || Date.now() > pix.vence + 60000) { pixVenceu(); return; }
    } catch (e) {
      if (e.status === 401) { voltarAoCadastro("a confirmação do Google venceu: se você já pagou, o plano entra sozinho; entre de novo para conferir"); return; }
      // Rede: tenta de novo na proxima volta.
    }
    vigia = setTimeout(conferirPix, 4000);
  }

  function pixVenceu() {
    pix = null;
    chavePix = novaChave();
    $("pg-pix-qr").hidden = true;
    $("pg-pix-gerar").hidden = false;
    $("pg-pix-gerar").disabled = false;
    desenharMeios();
    erro("este Pix venceu sem pagamento: gere outro");
  }

  async function copiarPix() {
    var campo = $("pg-pix-codigo");
    try {
      await navigator.clipboard.writeText(campo.value);
    } catch (e) {
      campo.select();
      try { document.execCommand("copy"); } catch (x) { /* o codigo fica selecionado para copiar a mao */ }
    }
    $("pg-pix-copiar-texto").textContent = "Copiado";
    setTimeout(function () { $("pg-pix-copiar-texto").textContent = "Copiar"; }, 2000);
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
      var r = await pedir("/api/ia/site/pagar", { id_token: token, plano: pedido.plano, periodo: pedido.periodo,
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
    pararPix();
  });
  // Voltou para a aba com o Pix aberto (pagou pelo celular): confere na hora.
  document.addEventListener("visibilitychange", function () {
    if (document.visibilityState === "visible" && pix) { pararPix(); conferirPix(); }
  });
  document.addEventListener("DOMContentLoaded", function () {
    $("pg-fora-botao").addEventListener("click", pagarFora);
    $("pg-meio-cartao").addEventListener("click", function () { escolherMeio("cartao"); });
    $("pg-meio-pix").addEventListener("click", function () { escolherMeio("pix"); });
    $("pg-pix-gerar").addEventListener("click", gerarPix);
    $("pg-pix-copiar").addEventListener("click", copiarPix);
    iniciar();
  });
})();
