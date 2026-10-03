/* A demo animada da pagina inicial (desenho "Site e Entrada", 03/10/2026):
   pergunta -> resposta com a fonte -> gravacao -> transcricao -> resumo ->
   aprovacao, em 22,5 s e em loop. Um palco de 1280 x 800 desenhado em
   funcao do tempo T e escalado para a largura da moldura. Sem React: o
   quadro inteiro e refeito a cada passo (30 por segundo), parado quando a
   moldura sai da tela ou a aba fica escondida. Com "reduzir movimento",
   fica um quadro so (o resumo com a aprovacao). */
(function () {
  "use strict";
  var raiz = document.querySelector("[data-demo]");
  if (!raiz) return;

  var F = "'Manrope',system-ui,sans-serif", S = "'EB Garamond',Georgia,serif", M = "'Fira Code',monospace";
  var C = { bg: "#131312", panel: "#1a1a18", pill: "#2a2a27", ink: "#f2f1ec", mute: "#a8a69e", dim: "#6f6e68", line: "rgba(242,241,236,.12)", ok: "#7fbf8e" };
  var CENAS = [["Pergunta", 4], ["Resposta", 3.5], ["Gravacao", 3.5], ["Transcricao", 4], ["Resumo", 4], ["Aprovacao", 3.5]];
  var CUE = {}, TOTAL = 0;
  CENAS.forEach(function (c) { CUE[c[0]] = TOTAL; TOTAL += c[1]; });

  var TRANS = [
    ["12:40", "Podemos compensar no aditivo, parcelado em duas vezes, se vocês abrirem mão da multa."],
    ["12:58", "Sem a multa a gente precisa da anuência da Cooperativa. Mandem a proposta por escrito."],
    ["13:21", "Fechado. Minuta do aditivo até sexta."],
  ];
  var PROMPT = "O que ficou pendente da reunião de ontem?";
  var RESP = "Duas pendências: enviar a minuta do aditivo até sexta e conferir se a renúncia à multa precisa da anuência da Cooperativa.";
  var RESUMO = [
    ["RESUMO", "O fornecedor propõe parcelar em duas vezes em troca da renúncia à multa. Ficou de mandar a proposta por escrito."],
    ["DECISÕES · 1", "Aditivo parcelado em duas vezes, sem multa."],
    ["PENDÊNCIAS · 2", "Enviar a minuta do aditivo até sexta · Conferir se a renúncia precisa da anuência da Cooperativa."],
  ];
  var LEGENDAS = [
    ["Pergunta", "Resposta", "Pergunte em português."],
    ["Resposta", "Gravacao", "A resposta vem com a fonte."],
    ["Gravacao", "Transcricao", "A fonte é a gravação da reunião. O áudio ficou no computador."],
    ["Transcricao", "Resumo", "Transcrita nesta máquina, com o minuto de cada trecho."],
    ["Resumo", "Aprovacao", "A IA resume: decisões e pendências."],
    ["Aprovacao", null, "Nada sai sem o seu sim."],
  ];

  // A pagina em ingles (data-demo="en"): os mesmos quadros, o texto traduzido.
  var EN = raiz.getAttribute("data-demo") === "en";
  var TXT = {
    gravacao: "GRAVAÇÃO · ONTEM", aqui: "transcrita nesta máquina · o áudio não sai do computador", transcricao: "TRANSCRIÇÃO",
    resumo: "RESUMO DA IA", tarefas: "Criar 2 tarefas na Agenda", proposto: "proposto pelo assistente · espera o seu sim",
    aprovar: "Aprovar", aprovado: "Aprovado", fonte: "gravação de ontem · 12:58 e 13:21", fonteDe: "fonte da resposta",
    outra: "Pergunte outra coisa…", vazio: "Pergunte sobre os seus documentos…",
  };
  if (EN) {
    TRANS = [
      ["12:40", "We can make it up in the amendment, in two installments, if you waive the penalty."],
      ["12:58", "Without the penalty we need the Cooperative's consent. Send the proposal in writing."],
      ["13:21", "Deal. Draft amendment by Friday."],
    ];
    PROMPT = "What was left open from yesterday's meeting?";
    RESP = "Two action items: send the draft amendment by Friday and check whether waiving the penalty needs the Cooperative's consent.";
    RESUMO = [
      ["SUMMARY", "The supplier offers two installments in exchange for waiving the penalty. They will send the proposal in writing."],
      ["DECISIONS · 1", "Amendment in two installments, no penalty."],
      ["ACTION ITEMS · 2", "Send the draft amendment by Friday · Check whether the waiver needs the Cooperative's consent."],
    ];
    LEGENDAS = [
      ["Pergunta", "Resposta", "Ask in plain language."],
      ["Resposta", "Gravacao", "The answer comes with its source."],
      ["Gravacao", "Transcricao", "The source is the meeting recording. The audio stayed on the computer."],
      ["Transcricao", "Resumo", "Transcribed on this machine, with the minute of each passage."],
      ["Resumo", "Aprovacao", "The AI summarizes: decisions and action items."],
      ["Aprovacao", null, "Nothing leaves without your yes."],
    ];
    TXT = {
      gravacao: "RECORDING · YESTERDAY", aqui: "transcribed on this machine · the audio never leaves the computer", transcricao: "TRANSCRIPT",
      resumo: "AI SUMMARY", tarefas: "Create 2 tasks in the Calendar", proposto: "proposed by the assistant · waiting for your yes",
      aprovar: "Approve", aprovado: "Approved", fonte: "yesterday's recording · 12:58 and 13:21", fonteDe: "source of the answer",
      outra: "Ask something else…", vazio: "Ask about your documents…",
    };
  }

  function clamp(v, a, b) { return Math.min(b, Math.max(a, v)); }
  var ease = {
    out: function (t) { return 1 - Math.pow(1 - t, 3); },
    back: function (t) { var c1 = 1.70158, c3 = c1 + 1; return 1 + c3 * Math.pow(t - 1, 3) + c1 * Math.pow(t - 1, 2); },
    inout: function (t) { return t < .5 ? 4 * t * t * t : 1 - Math.pow(-2 * t + 2, 3) / 2; },
  };
  function anim(fn, s, e, T) { return T <= s ? 0 : T >= e ? 1 : fn((T - s) / (e - s)); }
  function enter(s, e, T) { return anim(ease.out, s, e, T); }
  function pop(s, e, T) { return anim(ease.back, s, e, T); }
  function draw(s, e, T) { return anim(ease.inout, s, e, T); }
  function typeOut(txt, s, d, T) { return txt.slice(0, Math.round(clamp((T - s) / d, 0, 1) * txt.length)); }
  function mmss(s) { return String(Math.floor(s / 60)).padStart(2, "0") + ":" + String(Math.floor(s % 60)).padStart(2, "0"); }
  function esc(t) { return String(t).replace(/[&<>"]/g, function (c) { return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]; }); }
  function ic(nome, tam, cor) {
    return '<span style="font-family:\'Material Symbols Outlined\';font-weight:300;font-size:' + tam + "px;line-height:1;color:" + cor +
      ";display:inline-block;width:" + tam + 'px;overflow:hidden;white-space:nowrap;font-feature-settings:\'liga\'">' + nome + "</span>";
  }
  function rotulo(t, extra) { return '<span style="font:400 11px ' + M + ";letter-spacing:.18em;color:" + C.dim + ";" + (extra || "") + '">' + t + "</span>"; }
  function cartao(conteudo, estilo) { return '<div style="border-radius:12px;background:' + C.panel + ";border:1px solid " + C.line + ";box-sizing:border-box;" + estilo + '">' + conteudo + "</div>"; }

  var palco = document.createElement("div");
  palco.setAttribute("aria-hidden", "true");
  palco.style.cssText = "position:absolute;left:0;top:0;width:1280px;height:800px;transform-origin:0 0;overflow:hidden;background:" + C.bg + ";font-family:" + F + ";color:" + C.ink;
  raiz.appendChild(palco);
  var alvo = { x: 0, y: 0 };

  function quadro(T) {
    var A = CUE.Pergunta, B = CUE.Resposta, Cg = CUE.Gravacao, D = CUE.Transcricao, E = CUE.Resumo, G = CUE.Aprovacao;
    var push = draw(Cg, Cg + .9, T);
    var convX = 320 + push * 980, convTop = 200, convO = 1 - push * .4;
    var promptIn = enter(A + .2, A + .7, T), typed = typeOut(PROMPT, A + .6, 1.9, T);
    var sentAt = A + 2.9, sent = T >= sentAt, think = T >= sentAt + .2 && T < B, bubbleIn = pop(sentAt, sentAt + .5, T);
    var respIn = enter(B, B + .5, T), respTxt = typeOut(RESP, B, 2, T), citeIn = enter(B + 2, B + 2.5, T), citeHot = pop(Cg - .4, Cg, T);
    var recIn = enter(Cg + .5, Cg + 1.1, T), playing = T >= Cg + 1.2 && T < D + .4, playT = clamp(T - (Cg + 1.2), 0, 999);
    var trIn = enter(D + .1, D + .7, T);
    var toSum = draw(E, E + .8, T);
    var appIn = pop(G, G + .6, T), cursor = draw(G + .7, G + 1.4, T), press = T >= G + 1.45 && T < G + 1.65, done = pop(G + 1.6, G + 2.1, T);
    var fadeEnd = draw(TOTAL - .5, TOTAL, T);
    var h = [];

    h.push('<span style="position:absolute;left:0;right:0;top:48px;text-align:center;font:400 28px ' + S + ';letter-spacing:.14em;color:#2a2a28">PAVLVS</span>');

    // a gravacao e a transcricao (somem quando o resumo entra)
    var barras = "", head = playing ? .45 + (playT / 3.4) * .5 : (T < Cg + 1.2 ? .45 : .95);
    for (var i = 0; i < 48; i++) {
      var amp = Math.abs(Math.sin(i * .9) * Math.sin(i * .37));
      barras += '<span style="flex:1;height:' + (6 + amp * 54).toFixed(1) + "px;border-radius:2px;background:" + (i / 48 < head ? C.ink : "rgba(242,241,236,.25)") + '"></span>';
    }
    var tocar = playing
      ? '<span style="display:flex;gap:3px"><span style="width:3px;height:11px;background:' + C.ink + ';border-radius:1px"></span><span style="width:3px;height:11px;background:' + C.ink + ';border-radius:1px"></span></span>'
      : ic("play_arrow", 16, C.ink);
    var linhas = TRANS.map(function (l, n) {
      var o = enter(D + .4 + n * .9, D + .8 + n * .9, T);
      return '<div style="display:grid;grid-template-columns:48px 1fr;gap:12px;opacity:' + o + ";transform:translateY(" + ((1 - o) * 6) + 'px)">' +
        '<span style="font:400 10.5px ' + M + ";color:" + (n >= 1 ? C.ok : C.dim) + ';padding-top:3px">' + l[0] + "</span>" +
        '<span style="font:400 14.5px/1.5 ' + F + ";color:" + (n >= 1 ? C.ink : C.mute) + '">' + esc(typeOut(l[1], D + .5 + n * .9, .9, T)) + "</span></div>";
    }).join("");
    if (recIn > 0 && toSum < 1) {
      h.push('<div style="position:absolute;left:340px;top:' + convTop + "px;width:600px;opacity:" + (recIn * (1 - toSum)) +
        ";transform:translateX(" + ((1 - recIn) * 60) + "px) scale(" + (.9 + .1 * recIn) + ") translateY(" + (toSum * -16) + 'px);transform-origin:center top;display:grid;gap:14px">' +
        cartao('<div style="display:flex;align-items:center;gap:8px">' + ic("mic", 14, C.ok) + rotulo(TXT.gravacao, "color:" + C.mute) +
          '<span style="margin-left:auto;font:400 12px ' + M + ";color:" + C.ink + '">' + mmss(playing ? 760 + playT * 14 : (T < Cg + 1.2 ? 760 : 801)) + "</span></div>" +
          '<div style="margin-top:16px;height:64px;display:flex;align-items:center;gap:3px">' + barras + "</div>" +
          '<div style="margin-top:12px;display:flex;align-items:center;gap:10px"><span style="width:28px;height:28px;border-radius:14px;background:' + C.pill +
          ';display:flex;align-items:center;justify-content:center">' + tocar + '</span><span style="font:400 12.5px/1.4 ' + F + ";color:" + C.dim +
          '">' + TXT.aqui + "</span></div>", "padding:16px 18px") +
        cartao(rotulo(TXT.transcricao) + linhas, "padding:14px 18px;display:grid;gap:10px;opacity:" + trIn + ";transform:translateY(" + ((1 - trIn) * 12) + "px)") +
        "</div>");
    }

    // o resumo da IA, com a aprovacao dentro
    if (toSum > 0) {
      var itens = RESUMO.map(function (l, n) {
        var o = enter(E + .5 + n * .7, E + 1 + n * .7, T);
        return '<div style="display:grid;gap:4px;opacity:' + o + ";transform:translateY(" + ((1 - o) * 6) + 'px)">' +
          '<span style="font:400 10px ' + M + ";letter-spacing:.14em;color:" + (n === 2 ? C.ok : C.dim) + '">' + l[0] + "</span>" +
          '<span style="font:400 15px/1.55 ' + F + ";color:" + (n === 0 ? C.ink : C.mute) + '">' + esc(l[1]) + "</span></div>";
      }).join("");
      var aprovar = "";
      if (T >= G) {
        var fundo = done > 0 ? C.ok : (cursor >= 1 ? "#333330" : C.pill);
        aprovar = '<div style="display:flex;margin-top:6px;border-radius:10px;background:' + C.bg + ";border:1px solid " + C.line + ";padding:12px 14px;align-items:center;gap:12px;opacity:" + appIn +
          ";transform:scale(" + (.96 + .04 * appIn) + ');transform-origin:left top">' + ic("calendar_month", 18, C.dim) +
          '<span style="flex:1;display:grid;gap:2px"><span style="font:500 14px ' + F + ";color:" + C.ink + '">' + TXT.tarefas + "</span>" +
          '<span style="font:400 12px ' + F + ";color:" + C.mute + '">' + TXT.proposto + "</span></span>" +
          '<span data-alvo style="height:30px;padding:0 14px;display:flex;align-items:center;border-radius:8px;background:' + fundo + ";color:" + (done > 0 ? C.bg : C.ink) +
          ";font:500 13px " + F + ";transform:" + (press ? "scale(.96)" : "none") + '">' +
          (done > 0 ? '<span style="display:flex;align-items:center;gap:6px">' + ic("check", 15, C.bg) + TXT.aprovado + "</span>" : TXT.aprovar) + "</span></div>";
      }
      h.push(cartao('<div style="display:flex;align-items:center;gap:8px">' + ic("auto_awesome", 14, C.ok) + rotulo(TXT.resumo) + "</div>" + itens + aprovar,
        "position:absolute;left:340px;top:" + convTop + "px;width:600px;padding:20px 24px;display:grid;gap:14px;opacity:" + toSum + ";transform:translateY(" + ((1 - toSum) * 16) + "px)"));
    }

    // a conversa
    var conversa = "";
    if (sent) {
      conversa += '<div style="display:flex;justify-content:flex-end;opacity:' + bubbleIn + ";transform:translateY(" + ((1 - bubbleIn) * 8) + 'px)"><span style="max-width:80%;padding:10px 14px;border-radius:10px;background:' +
        C.pill + ";font:400 15px/1.5 " + F + ";color:" + C.ink + '">' + esc(PROMPT) + "</span></div>";
    }
    if (think) {
      conversa += '<div style="display:flex;gap:6px">' + [0, 1, 2].map(function (n) {
        return '<span style="width:6px;height:6px;border-radius:3px;background:' + C.mute + ";opacity:" + (.35 + .65 * Math.abs(Math.sin(T * 3 + n * .9))) + '"></span>';
      }).join("") + "</div>";
    }
    if (T >= B) {
      var quente = citeHot > 0;
      conversa += '<div style="opacity:' + respIn + '"><p style="margin:0;font:400 17px/1.55 ' + F + ";color:" + C.ink + '">' + esc(respTxt) + "</p>" +
        '<div style="margin-top:14px;display:flex;align-items:center;gap:8px;opacity:' + citeIn + ";transform:translateX(" + ((1 - citeIn) * -8) + 'px)">' +
        '<span style="display:flex;align-items:center;gap:6px;height:26px;padding:0 10px;border-radius:6px;border:1px solid ' +
        (quente ? "rgba(127,191,142," + (.3 + .5 * citeHot) + ")" : C.line) + ";background:" + (quente ? "rgba(127,191,142,.08)" : "transparent") +
        ";font:400 11px " + M + ";color:" + (quente ? C.ink : C.mute) + ";transform:scale(" + (1 + .04 * citeHot) + ");transform-origin:left center;margin-right:" + (8 * citeHot) + 'px">' +
        ic("mic", 13, C.ok) + TXT.fonte + "</span>" +
        '<span style="font:400 12px ' + F + ";color:" + C.dim + '">' + TXT.fonteDe + "</span></div></div>";
    }
    var escrito = typed && !sent;
    var caret = !sent ? '<span style="display:inline-block;width:1.5px;height:18px;background:' + C.ink + ";margin-left:2px;opacity:" + (Math.round(T * 2.5) % 2 ? 1 : .15) + '"></span>' : "";
    conversa += cartao('<span style="flex:1;display:flex;align-items:center">' + esc(sent ? TXT.outra : (typed || TXT.vazio)) + caret + "</span>" +
      '<span style="width:30px;height:30px;border-radius:15px;background:' + (escrito ? C.ink : C.pill) + ";display:flex;align-items:center;justify-content:center;transform:" +
      (T >= sentAt - .1 && T < sentAt + .15 ? "scale(.9)" : "none") + '">' + ic("arrow_upward", 16, escrito ? C.bg : C.ink) + "</span>",
      "padding:14px 16px;font:400 16px " + F + ";color:" + (escrito ? C.ink : C.dim) + ";display:flex;align-items:center;gap:10px;min-height:50px");
    if (convX < 1280) {
      h.push('<div style="position:absolute;left:' + convX + "px;top:" + convTop + "px;width:640px;opacity:" + (promptIn * convO) + ";transform:translateY(" + ((1 - promptIn) * 16) +
        'px);display:grid;gap:22px">' + conversa + "</div>");
    }

    // o cursor que aprova
    var cOp = appIn * cursor * (1 - done) * (1 - fadeEnd);
    if (cOp > 0) {
      h.push('<svg width="22" height="26" viewBox="0 0 22 26" style="position:absolute;z-index:5;left:' + (alvo.x - 2 + (1 - cursor) * 140) + "px;top:" + (alvo.y - 2 + (1 - cursor) * 90) +
        "px;opacity:" + cOp + ";filter:drop-shadow(0 2px 4px rgba(0,0,0,.6));transform:" + (press ? "scale(.9)" : "none") +
        '"><path d="M2 2l6 20 3.5-7.5L19 11z" fill="#fff" stroke="#111" stroke-width="1.4" stroke-linejoin="round"/></svg>');
    }

    // as legendas
    var leg = LEGENDAS.map(function (l) {
      var s = CUE[l[0]], e = l[1] ? CUE[l[1]] : TOTAL;
      var o = enter(s + .1, s + .6, T) * (1 - draw(e - .4, e, T));
      return o > 0 ? '<span style="position:absolute;left:0;right:0;bottom:0;line-height:1.2;font:400 ' + (estreito ? 34 : 26) + "px " + S + ";color:" + C.ink + ";opacity:" + o + ";transform:translateY(" + ((1 - o) * 8) + 'px)">' + esc(l[2]) + "</span>" : "";
    }).join("");
    // No celular so a faixa do meio do palco aparece: a legenda quebra linha dentro dela, maior.
    h.push('<div style="position:absolute;left:' + (estreito ? 310 : 0) + "px;right:" + (estreito ? 310 : 0) + 'px;bottom:56px;height:96px;text-align:center">' + leg + "</div>");
    if (fadeEnd > 0) h.push('<div style="position:absolute;inset:0;z-index:10;background:' + C.bg + ";opacity:" + fadeEnd + '"></div>');

    palco.innerHTML = h.join("");
    var botao = palco.querySelector("[data-alvo]");
    if (botao) {
      var b = botao.getBoundingClientRect(), r = palco.getBoundingClientRect(), k = r.width / 1280 || 1;
      alvo.x = (b.left + b.width * .5 - r.left) / k;
      alvo.y = (b.top + b.height * .55 - r.top) / k;
    }
  }

  // Na tela larga, o palco inteiro; no celular, a faixa do meio (x de 300 a
  // 980, onde ficam a conversa e o resumo), na altura toda.
  var estreito = false;
  function ajustar() {
    var w = raiz.clientWidth;
    estreito = w < 600;
    var k = w / (estreito ? 680 : 1280);
    palco.style.transform = (estreito ? "translateX(" + (-300 * k) + "px) " : "") + "scale(" + k + ")";
  }
  ajustar();
  window.addEventListener("resize", ajustar);

  var parado = window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  var visivel = true, rodando = false, inicio = null, desde = 0, ultimo = 0;
  // Quem pediu menos movimento ao sistema (no Windows: Efeitos de animação
  // desligados) vê um quadro parado e um botão para assistir, se quiser.
  if (parado) {
    quadro(CUE.Aprovacao + 2.6); quadro(CUE.Aprovacao + 2.6);
    var tocar = document.createElement("button");
    tocar.type = "button";
    tocar.className = "demo-tocar";
    tocar.textContent = document.documentElement.lang === "en" ? "\u25B6 Watch the demo" : "\u25B6 Ver a demonstra\u00e7\u00e3o";
    tocar.addEventListener("click", function () { tocar.remove(); parado = false; seguir(); });
    raiz.appendChild(tocar);
  }
  function seguir() { if (!parado && !rodando && visivel && !document.hidden) { rodando = true; requestAnimationFrame(passo); } }
  if ("IntersectionObserver" in window) {
    new IntersectionObserver(function (e) { visivel = e[0].isIntersecting; seguir(); }, { threshold: .05 }).observe(raiz);
  }
  document.addEventListener("visibilitychange", seguir);
  function passo(agora) {
    if (!visivel || document.hidden) { inicio = null; rodando = false; return; }
    if (inicio === null) inicio = agora - desde * 1000;
    desde = ((agora - inicio) / 1000) % TOTAL;
    if (agora - ultimo >= 33) { ultimo = agora; quadro(desde); }
    requestAnimationFrame(passo);
  }
  seguir();
})();
