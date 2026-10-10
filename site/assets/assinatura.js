/* A pagina dos planos (paulus.ia.br/assinatura): os planos em cards, por mes
   ou por ano. Os numeros (preco, creditos, pessoas, modelo, limites) vem do
   Worker (worker/ia.js, /api/ia/planos); os textos - a frase do plano, o texto
   antes dos itens e os itens, com o que abre em cada um - tambem
   (/api/planos/textos: os que o painel admin escreveu ou os padrao, montados
   com os numeros do plano em worker/planos-textos.js). O botao do plano
   escolhido leva ao checkout da Atos (atos.dev.br/pavlvs/assinar, a Atos Cobranca: a Conta Atos, os
   dados para a nota e o pagamento, tudo la), com o preco do catalogo da Atos e a volta para ca. */
(function () {
  "use strict";

  var $ = function (id) { return document.getElementById(id); };
  // O checkout da Atos (C:\atos\docs\COBRANCA.md): o id do preco e "pavlvs.<plano>.<mes|ano>".
  var CHECKOUT_DA_ATOS = "https://atos.dev.br/pavlvs/assinar/";
  var pedido = new URLSearchParams(location.search);
  var estado = { planos: [], textos: {}, escolhido: pedido.get("plano") || "escritorio", periodo: pedido.get("periodo") === "anual" ? "anual" : "mensal", aberto: {} };

  function esc(t) { return String(t == null ? "" : t).replace(/[&<>"']/g, function (c) { return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]; }); }
  function brlFino(v) { return Number(v).toLocaleString("pt-BR", { style: "currency", currency: "BRL", minimumFractionDigits: Number(v) % 1 ? 2 : 0, maximumFractionDigits: 2 }); }

  // O plano que a pagina recomenda (a faixa). "Recomendado", e nao "mais
  // escolhido": a pagina so diz o que e verdade.
  var RECOMENDADO = "escritorio";

  /* Os textos de um plano (do Worker): {para, heranca, itens: [[titulo, o que abre]]}.
     "(em breve)" no texto marca o que ainda nao existe. Sem os textos (o Worker
     nao respondeu), o cartao mostra so os numeros. */
  function textosDoPlano(p) {
    var t = estado.textos[p.id] || {};
    return { para: t.para || "", heranca: t.heranca || "", itens: (t.itens || []).map(function (it) { return [it.titulo, it.descricao || ""]; }) };
  }

  function valorDe(p) { return estado.periodo === "anual" ? p.valor_anual : p.valor; }

  /* "3 meses grátis": quantos meses inteiros o anual poupa (o menor entre os planos). */
  function mesesGratis() {
    var m = estado.planos.map(function (p) { return Math.floor((p.valor * 12 - p.valor_anual) / p.valor); });
    return m.length ? Math.min.apply(null, m) : 0;
  }

  function desenharPeriodo() {
    ["mensal", "anual"].forEach(function (x) {
      var b = $("cd-periodo-" + x);
      b.setAttribute("aria-checked", String(estado.periodo === x));
      b.classList.toggle("on", estado.periodo === x);
    });
    // A pastilha desliza ate a opcao escolhida.
    var on = $("cd-periodo-" + estado.periodo), grupo = on && on.parentElement;
    if (grupo) {
      var m = grupo.querySelector(".ciclo-marcador");
      if (!m) { m = document.createElement("span"); m.className = "ciclo-marcador"; m.setAttribute("aria-hidden", "true"); grupo.insertBefore(m, grupo.firstChild); grupo.classList.add("com-marcador"); }
      m.style.width = on.offsetWidth + "px";
      m.style.transform = "translateX(" + (on.offsetLeft - 3) + "px)";
    }
    var gratis = mesesGratis();
    $("cd-selo-anual").textContent = gratis > 0 ? gratis + (gratis === 1 ? " mês grátis" : " meses grátis") : "";
  }

  function cartao(p, on) {
    var anual = estado.periodo === "anual";
    var mesAno = Math.round((p.valor_anual / 12) * 100) / 100;
    // Uma frase so por caso, para nao parecer que o valor por pessoa se soma ao do plano.
    var economia = brlFino(p.valor * 12 - p.valor_anual);
    var porColab = function (v) { return brlFino(Math.round((v / p.pessoas) * 100) / 100); };
    var det = anual
      ? "Aqui você economiza " + economia + " em relação ao plano mensal. Equivale a " + brlFino(mesAno) + " por mês" +
        (p.pessoas > 1 ? ", o equivalente a " + porColab(mesAno) + " por colaborador/mês." : ".")
      : (p.pessoas > 1 ? "Equivale a " + porColab(p.valor) + " por colaborador/mês. " : "") +
        "No plano anual, você economiza " + economia + ": " + brlFino(p.valor_anual) + " por ano, o equivalente a " + brlFino(mesAno) + " por mês.";
    var porPessoa = "";
    var textos = textosDoPlano(p);
    var itens = textos.itens.map(function (it, i) {
      var chave = p.id + ":" + i;
      var aberto = Boolean(estado.aberto[chave]);
      var breve = /\(em breve\)/.test(it[1]);
      return '<div class="cd-item"><button type="button" class="cd-item-botao" data-item="' + esc(chave) + '" aria-expanded="' + aberto + '">' +
        '<span class="icon" aria-hidden="true">check</span><span>' + esc(it[0]) + (breve ? '<span class="cd-breve">parte em breve</span>' : "") + "</span>" +
        '<span class="icon cd-seta" aria-hidden="true">expand_more</span></button>' +
        '<div class="cd-resposta' + (aberto ? " aberta" : "") + '"><div><p>' + esc(it[1]) + "</p></div></div></div>";
    }).join("");
    // A licenca do Llama pede o "Built with Llama" visivel onde ele e oferecido.
    var llama = (p.modelos_info || []).some(function (m) { return /llama/i.test(m.nome); });
    return '<article class="cd-cartao' + (on ? " on" : "") + '" data-plano="' + esc(p.id) + '" aria-label="Plano ' + esc(p.nome) + '">' +
      (p.id === RECOMENDADO ? '<span class="cd-faixa">recomendado</span>' : "") +
      '<div class="cd-cabeca"><span class="cd-nome"><b>' + esc(p.nome) + '</b><span class="cd-radio" aria-hidden="true"></span></span>' +
      // O detalhe do preco (o outro periodo e o valor por pessoa) aparece ao passar o mouse - ou ao focar - sobre o valor.
      '<span class="cd-preco" tabindex="0"><span class="cd-valor"><strong>' + brlFino(valorDe(p)) + "</strong><span>" + (anual ? "por ano" : "por mês") + "</span></span>" +
      '<span class="cd-dica" role="tooltip"><small>' + esc(det) + "</small>" + (porPessoa ? "<small>" + esc(porPessoa) + "</small>" : "") + "</span></span>" +
      (textos.para ? '<span class="cd-para">' + esc(textos.para) + "</span>" : "") + "</div>" +
      '<div class="cd-numeros"><span><b>' + esc((p.tokens / 1e6).toLocaleString("pt-BR", { maximumFractionDigits: 1 }) + " milhões") + "</b><small>créditos de IA por mês</small></span>" +
      "<span><b>" + (p.pessoas === 1 ? "1 pessoa" : "até " + p.pessoas + " pessoas") + "</b><small>" + (p.pessoas === 1 ? "uma licença" : "cada uma com o seu login") + "</small></span></div>" +
      '<div class="cd-itens">' + (textos.heranca ? '<span class="cd-heranca"><span class="cd-heranca-selo">' + esc(textos.heranca) + "</span></span>" : "") + itens + "</div>" +
      '<div class="cd-pe">' + (llama ? "<small>Built with Llama</small>" : "") +
      '<button type="button" class="cd-acao" data-mp-checkout-cta="checkout-api" data-acao="' + esc(p.id) + '" aria-pressed="' + on + '">' + esc((on ? "Assinar " : "Escolher ") + p.nome) + "</button></div></article>";
  }

  /* Clicar no card escolhe; o botao do card escolhido leva ao checkout da Atos, com o preco
     (plano e periodo) e a volta para ca. */
  function escolher(id, irAoCheckout) {
    estado.escolhido = id;
    if (irAoCheckout) {
      var preco = "pavlvs." + id + "." + (estado.periodo === "anual" ? "ano" : "mes");
      window.location.assign(CHECKOUT_DA_ATOS + "?preco=" + encodeURIComponent(preco) + "&volta=" + encodeURIComponent("https://paulus.ia.br/"));
      return;
    }
    desenharPlanos();
  }

  var CURVA = "cubic-bezier(.22,.8,.24,1)";
  var calmo = window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  function alternarResposta(el, abrir) {
    var de = el.offsetHeight;
    el.classList.toggle("aberta", abrir);
    el.style.height = "auto";
    var ate = abrir ? el.scrollHeight : 0;
    if (!el.animate) { el.style.height = abrir ? "auto" : "0px"; return; }
    if (el._anim) el._anim.cancel();
    el._anim = el.animate([{ height: de + "px" }, { height: ate + "px" }], { duration: 300, easing: CURVA });
    el.style.height = ate + "px";
    el._anim.onfinish = function () { el.style.height = abrir ? "auto" : "0px"; el._anim = null; };
    var p = el.querySelector("p");
    if (p) p.animate(abrir ? [{ opacity: 0, transform: "translateY(-4px)" }, { opacity: 1, transform: "none" }] : [{ opacity: 1 }, { opacity: 0 }],
      { duration: abrir ? 300 : 160, easing: CURVA, fill: "both" });
  }

  /* Trocar o periodo nao redesenha os cartoes: so os textos do preco, com um deslize curto. */
  function atualizarPrecos() {
    var anual = estado.periodo === "anual";
    estado.planos.forEach(function (p) {
      var card = $("cd-planos").querySelector('[data-plano="' + p.id + '"]');
      if (!card) return;
      var novo = cartao(p, p.id === estado.escolhido);
      var tmp = document.createElement("div"); tmp.innerHTML = novo;
      var valorNovo = tmp.querySelector(".cd-valor"), dicaNova = tmp.querySelector(".cd-dica"), acaoNova = tmp.querySelector(".cd-acao");
      var valor = card.querySelector(".cd-valor"), dica = card.querySelector(".cd-dica");
      if (dica && dicaNova) dica.innerHTML = dicaNova.innerHTML;
      if (!valor || !valorNovo) return;
      if (!valor.animate) { valor.innerHTML = valorNovo.innerHTML; return; }
      if (calmo) { valor.innerHTML = valorNovo.innerHTML; valor.animate([{ opacity: 0 }, { opacity: 1 }], { duration: 200, easing: "ease-out" }); return; }
      var sai = valor.animate([{ opacity: 1, transform: "none" }, { opacity: 0, transform: "translateY(-6px)" }], { duration: 140, easing: "ease-in", fill: "forwards" });
      sai.onfinish = function () {
        valor.innerHTML = valorNovo.innerHTML;
        sai.cancel();
        valor.animate([{ opacity: 0, transform: "translateY(6px)" }, { opacity: 1, transform: "none" }], { duration: 260, easing: CURVA });
      };
    });
  }

  /* As listas fechadas dos cartoes que estao lado a lado ficam da mesma altura (a maior), para os botoes alinharem.
     Medido com tudo fechado; abrir um item depois so estica aquele cartao. */
  function igualarListas() {
    var listas = [].slice.call($("cd-planos").querySelectorAll(".cd-itens"));
    listas.forEach(function (l) { l.style.minHeight = ""; });
    var linhas = {};
    listas.forEach(function (l) { var t = Math.round(l.getBoundingClientRect().top); (linhas[t] = linhas[t] || []).push(l); });
    Object.keys(linhas).forEach(function (t) {
      var grupo = linhas[t]; if (grupo.length < 2) return;
      var alt = Math.max.apply(null, grupo.map(function (l) {
        var abertas = [].slice.call(l.querySelectorAll(".cd-resposta.aberta"));
        var extra = abertas.reduce(function (a, r) { return a + r.offsetHeight; }, 0);
        return l.offsetHeight - extra;
      }));
      grupo.forEach(function (l) { l.style.minHeight = alt + "px"; });
      // O pe tambem (o "Built with Llama" do Advogado ocupa uma linha a mais): o botao fica no fundo de todos.
      var pes = grupo.map(function (l) { return l.parentElement.querySelector(".cd-pe"); }).filter(Boolean);
      pes.forEach(function (p) { p.style.minHeight = ""; });
      var altPe = Math.max.apply(null, pes.map(function (p) { return p.offsetHeight; }));
      pes.forEach(function (p) { p.style.minHeight = altPe + "px"; });
    });
  }

  function desenharPlanos() {
    $("cd-planos").innerHTML = estado.planos.map(function (p) { return cartao(p, p.id === estado.escolhido); }).join("");
    $("cd-planos").querySelectorAll(".cd-cartao").forEach(function (el) {
      el.onclick = function (e) { if (!e.target.closest("button")) escolher(el.dataset.plano, false); };
    });
    $("cd-planos").querySelectorAll("[data-acao]").forEach(function (b) {
      b.onclick = function () { escolher(b.dataset.acao, b.dataset.acao === estado.escolhido); };
    });
    igualarListas();
    $("cd-planos").querySelectorAll("[data-item]").forEach(function (b) {
      // Abre e fecha no lugar, sem redesenhar: a altura anima de 0 ate a do texto (Web Animations), e o texto aparece junto.
      b.onclick = function () {
        var on = !estado.aberto[b.dataset.item];
        estado.aberto[b.dataset.item] = on;
        b.setAttribute("aria-expanded", String(on));
        alternarResposta(b.nextElementSibling, on);
      };
    });
  }

  async function carregarPlanos() {
    try {
      // Os numeros e os textos juntos; sem os textos, os cartoes saem so com os numeros.
      var textos = fetch("/api/planos/textos").then(function (x) { return x.ok ? x.json() : null; }).catch(function () { return null; });
      var r = await fetch("/api/ia/planos");
      var d = await r.json();
      if (!r.ok) throw new Error(d.erro || "o site não respondeu (" + r.status + ")");
      var t = await textos;
      estado.textos = {};
      ((t && t.planos) || []).forEach(function (x) { estado.textos[x.id] = x; });
      estado.planos = d.planos || [];
      if (!estado.planos.some(function (p) { return p.id === estado.escolhido; })) estado.escolhido = RECOMENDADO;
      if (d.recarga) {
        $("cd-recarga").textContent = "Uma pergunta sobre documentos gasta, em média, 3.500 créditos. A cota é do mês, liberada por semana; " +
          "uma vez por mês dá para adiantar a semana seguinte. Se acabar, a recarga é no Pix, no preço do plano, e não vence na renovação. " +
          "Pague no Pix (um mês ou o ano, sem renovação) ou no cartão (o mensal renova sozinho; o anual, em até 12×).";
      }
      desenharPeriodo();
      desenharPlanos();
    } catch (e) {
      $("cd-planos").innerHTML = '<p class="nota-campo" style="padding:16px 14px">Não consegui ler os planos agora: ' + esc(e.message) + ". Tente de novo em instantes.</p>";
    }
  }

  document.addEventListener("DOMContentLoaded", function () {
    ["mensal", "anual"].forEach(function (x) {
      $("cd-periodo-" + x).addEventListener("click", function () {
        if (estado.periodo === x) return;
        estado.periodo = x;
        desenharPeriodo(); atualizarPrecos();
      });
    });
    desenharPeriodo();
    carregarPlanos();
    if (document.fonts && document.fonts.ready) document.fonts.ready.then(desenharPeriodo);
    window.addEventListener("resize", function () { desenharPeriodo(); igualarListas(); });
    if (document.fonts && document.fonts.ready) document.fonts.ready.then(function () { if (estado.planos.length) igualarListas(); });
  });
})();
