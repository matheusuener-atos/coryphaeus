/*
  O painel do PAVLVS no Word (W1). Fiel à maquete aprovada na W0
  (word/prova/maquete.html): os mesmos estados, textos e peças.

  - Nada é enviado sem a pessoa pedir; nesta etapa o painel só conecta.
  - O token do suplemento (src/word_suplemento.py) fica no armazenamento do
    painel; nunca cookie (no Word na web o painel roda em moldura).
  - Toda chamada leva o nome do documento, para a auditoria do PAULUS.
  - O tema acompanha o do Office (officeTheme), relido a cada 2 s: o Word
    2021 não avisa quando o tema muda.
*/
"use strict";

(function () {
  var CHAVE_TOKEN = "paulus.word.token";
  var MONTAGEM = location.hostname === "localhost" || location.hostname === "127.0.0.1" ? "A" : "C";
  var qs = new URLSearchParams(location.search);
  var TELA_PEDIDA = qs.get("tela") || "inicio";

  var st = {
    token: lerToken(), eu: null, documento: "", conjuntos: {}, word: "", plataforma: "",
    pedido: null, espera: null, menu: false, aviso: "", violacoes: [], tela: "abrindo", controlada: true,
  };

  // CSP: o que a política barrar volta no "carregou", para a W1 medir.
  document.addEventListener("securitypolicyviolation", function (e) {
    st.violacoes.push((e.violatedDirective || "") + " " + (e.blockedURI || ""));
  });

  // ------------------------------------------------------------ ícones
  var I = {
    conferir: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M5 3.5h9l5 5V20.5H5z"/><path d="M14 3.5v5h5"/><path d="M8.5 14.5l2.2 2.2 4.8-4.8"/></svg>',
    lei: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M4 5.5c2.7-1.3 5.3-1.3 8 0v14c-2.7-1.3-5.3-1.3-8 0z"/><path d="M12 5.5c2.7-1.3 5.3-1.3 8 0v14c-2.7-1.3-5.3-1.3-8 0z"/><path d="M15 9.5h2.5M15 12.5h2.5"/></svg>',
    fundamentacao: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M4 20.5h16M6 17.5h12M7 17.5v-7M12 17.5v-7M17 17.5v-7M4.5 10.5L12 4l7.5 6.5z"/></svg>',
    qualificacao: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><rect x="3" y="5" width="18" height="14" rx="2"/><circle cx="9" cy="11" r="2.3"/><path d="M5.8 16c.6-1.7 1.8-2.6 3.2-2.6s2.6.9 3.2 2.6M14.5 10h4M14.5 13h3"/></svg>',
    perguntar: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M4 5.5h16v10.5H10l-4.5 3.5V16H4z"/><path d="M10 9.3a2 2 0 1 1 2.6 1.9c-.4.2-.6.5-.6.9v.3M12 14.3v.1"/></svg>',
    revisar: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M4 4.5h11v6M4 4.5v15h7"/><path d="M7 8.5h5M7 11.5h3"/><path d="M14 13.5h7v5h-3.5L15 20.5v-2h-1z"/></svg>',
    guardar: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M3.5 13.5l2.5-8h12l2.5 8v6h-17z"/><path d="M3.5 13.5h5l1 2h5l1-2h5"/><path d="M12 7.5v5M9.8 10.3L12 12.5l2.2-2.2"/></svg>',
    mais: '<svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor" aria-hidden="true"><circle cx="5" cy="12" r="1.6"/><circle cx="12" cy="12" r="1.6"/><circle cx="19" cy="12" r="1.6"/></svg>',
    volta: '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M14.5 6l-6 6 6 6"/></svg>',
    cadeado: '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" aria-hidden="true"><rect x="5" y="10.5" width="14" height="10" rx="2"/><path d="M8 10.5V8a4 4 0 0 1 8 0v2.5"/></svg>',
    tomada: '<svg class="grande" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.4" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M9 3.5v4M15 3.5v4M6.5 7.5h11v4a5.5 5.5 0 0 1-11 0z"/><path d="M12 17v3.5"/></svg>',
    semrede: '<svg class="grande" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.4" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M2.5 9a14 14 0 0 1 19 0M5.5 12.5a9.5 9.5 0 0 1 13 0M8.8 16a5 5 0 0 1 6.4 0M12 19.5v.1M3 3l18 18"/></svg>',
    word: '<svg class="grande" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.4" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><rect x="4" y="3.5" width="16" height="17" rx="2"/><path d="M7.5 8l1.5 7 3-6 3 6 1.5-7"/></svg>',
    erro: '<svg class="grande" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.4" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M12 3.5l9 16H3z"/><path d="M12 10v4.5M12 17.3v.2"/></svg>',
  };

  // As funções do início. `pronta` vira true na etapa que a faz (W2…W6);
  // até lá aparece desabilitada, com "em breve" - só durante o trabalho.
  var FUNCOES = [
    { tela: "conferir", ico: "conferir", nome: "Conferir citações", linha: "Leis, súmulas e processos do documento, sem IA.", pronta: false },
    { tela: "lei", ico: "lei", nome: "Inserir lei", linha: "O texto vigente do artigo, com a referência.", pronta: false },
    { tela: "fundamentacao", ico: "fundamentacao", nome: "Fundamentação", linha: "Lei, súmula e doutrina para o parágrafo do cursor.", pronta: false },
    { tela: "qualificacao", ico: "qualificacao", nome: "Qualificação", linha: "A qualificação de uma parte, pelos Cadastros.", pronta: false },
    { tela: "perguntar", ico: "perguntar", nome: "Perguntar", linha: "Sobre este documento ou o trecho selecionado.", pronta: false },
    { tela: "revisar", ico: "revisar", nome: "Revisar com agente", linha: "Apontamentos em comentários; o texto não muda.", pronta: false },
    { tela: "guardar", ico: "guardar", nome: "Guardar no PAULUS", linha: "Uma cópia no Acervo, no cliente ou Serviço.", pronta: false },
  ];

  // ------------------------------------------------------------ utilidades
  function esc(s) {
    return String(s == null ? "" : s).replace(/[&<>"']/g, function (c) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c];
    });
  }
  function lerToken() { try { return localStorage.getItem(CHAVE_TOKEN) || ""; } catch (e) { return ""; } }
  function gravarToken(t) {
    st.token = t || "";
    try { if (t) localStorage.setItem(CHAVE_TOKEN, t); else localStorage.removeItem(CHAVE_TOKEN); } catch (e) { /* sem armazenamento: pede de novo */ }
  }

  function Falha(tipo, status, detalhe) { this.tipo = tipo; this.status = status; this.detalhe = detalhe; }

  // Uma chamada ao PAULUS. Falha de rede vira Falha("rede"); 401 apaga o token.
  function api(metodo, caminho, corpo) {
    var cab = { "Content-Type": "application/json" };
    if (st.token) cab.Authorization = "Bearer " + st.token;
    if (st.documento) cab["X-PAULUS-Documento"] = encodeURIComponent(st.documento);
    return fetch(caminho, { method: metodo, headers: cab, cache: "no-store", body: corpo === undefined ? undefined : JSON.stringify(corpo) })
      .catch(function () { throw new Falha("rede", 0, ""); })
      .then(function (r) {
        return r.text().then(function (txt) {
          var dados = null;
          try { dados = txt ? JSON.parse(txt) : null; } catch (e) { dados = null; }
          if (r.ok) return dados;
          throw new Falha(r.status === 401 ? "token" : "http", r.status, (dados && dados.detail) || "");
        });
      });
  }

  // ------------------------------------------------------------ tema
  function luminancia(hex) {
    var m = /^#?([0-9a-f]{6})$/i.exec(String(hex || "").trim());
    if (!m) return 1;
    var n = parseInt(m[1], 16);
    return (0.299 * ((n >> 16) & 255) + 0.587 * ((n >> 8) & 255) + 0.114 * (n & 255)) / 255;
  }
  var temaVisto = "";
  function aplicarTema() {
    var t = null;
    try { t = Office.context.officeTheme; } catch (e) { t = null; }
    if (!t) return;
    var assinatura = [t.bodyBackgroundColor, t.bodyForegroundColor, t.isDarkTheme].join("|");
    if (assinatura === temaVisto) return;
    temaVisto = assinatura;
    var escuro = t.isDarkTheme === true || luminancia(t.bodyBackgroundColor) < 0.5;
    document.documentElement.dataset.tema = escuro ? "escuro" : "claro";
    if (t.bodyBackgroundColor) document.documentElement.style.setProperty("--bg", t.bodyBackgroundColor);
  }
  function largura() { document.body.classList.toggle("largo", window.innerWidth >= 420); }
  window.addEventListener("resize", largura);

  // ------------------------------------------------------------ peças
  function topo(opc) {
    opc = opc || {};
    var estado = opc.estado || "ok";
    var txt = { ok: "Conectado", mal: "Sem conexão", nao: "Não conectado" }[estado];
    var esq = opc.titulo
      ? '<button class="p-volta" data-acao="inicio" aria-label="Voltar ao início">' + I.volta + "Início</button>" +
        '<span class="p-titulo cresce">' + esc(opc.titulo) + "</span>"
      : '<span class="cresce"></span>';
    var dica = estado === "ok" ? (MONTAGEM === "A" ? "Conectado ao PAULUS deste computador" : "Conectado ao PAULUS do escritório") : txt;
    var mais = estado === "ok"
      ? '<button class="ico-btn" data-acao="menu" aria-label="Mais opções" aria-haspopup="menu" aria-expanded="' + st.menu + '">' + I.mais + "</button>"
      : "";
    var menu = st.menu && estado === "ok"
      ? '<div class="menu" role="menu"><button role="menuitem" class="perigo" data-acao="desconectar">Desconectar este Word</button></div>'
      : "";
    return '<div class="p-topo">' + esq + '<span class="p-estado ' + estado + '" title="' + esc(dica) + '"><i aria-hidden="true"></i>' +
      (opc.titulo ? '<span class="so-leitor">' + txt + "</span>" : txt) + "</span>" + mais + menu + "</div>";
  }
  function rodape(html) { return '<div class="p-rodape" role="status" aria-live="polite">' + (html || "Pronto") + "</div>"; }
  function andando(txt) { return '<span class="anel" aria-hidden="true"></span><span class="cresce">' + esc(txt) + "</span>"; }
  function tela(icone, titulo, texto, botoes) {
    return '<div class="estado-tela">' + icone + '<h1 class="p-h">' + esc(titulo) + "</h1>" + texto +
      (botoes ? '<div class="linha-btns">' + botoes + "</div>" : "") + "</div>";
  }

  // ------------------------------------------------------------ os estados
  var TELAS = {
    abrindo: function () {
      return '<div class="p-corpo"><div class="estado-tela"><p class="p-sub">Abrindo…</p></div></div>';
    },
    foraDoWord: function () {
      return topo({ estado: "nao" }) + '<div class="p-corpo">' + tela(I.word, "Abra pelo Word",
        '<p class="p-sub">Este é o painel do PAVLVS dentro do Word. Abra o Word e clique na aba PAVLVS.</p>', "") + "</div>" +
        rodape("Fora do Word");
    },
    primeira: function () {
      return topo({ estado: "nao" }) + '<div class="p-corpo"><div class="estado-tela">' +
        (st.aviso ? '<div class="aviso atencao" role="alert"><span>' + esc(st.aviso) + "</span></div>" : "") +
        '<h1 class="p-h maior">O PAULUS no seu Word</h1>' +
        '<ul class="passos-mini" style="padding-left:16px">' +
        "<li>Confere as leis, súmulas e processos citados no documento.</li>" +
        "<li>Insere artigo vigente, fundamentação e qualificação das partes, como alteração controlada.</li>" +
        "<li>Responde sobre o documento com as fontes do escritório.</li></ul>" +
        '<button class="btn primario cheio" data-acao="conectar">Conectar ao PAULUS</button>' +
        '<div class="aviso neutro">' + I.cadeado + "<span>" +
        (MONTAGEM === "A" ? "O texto do documento vai só para o PAULUS deste computador. Nada sai daqui."
          : "O texto do documento vai só para o PAULUS do escritório, pelo endereço dele.") +
        "</span></div></div></div>" + rodape("Não conectado");
    },
    conectando: function () {
      var p = st.pedido || {};
      var codigo = p.codigo || "";
      var falado = codigo.replace("-", ", ").split("").join(" ");
      var passos = MONTAGEM === "A"
        ? "<li>Abra a janela do PAULUS neste computador.</li><li>Confira se aparece o mesmo código.</li><li>Clique em <b>Permitir</b>.</li>"
        : "<li>Abra o PAULUS do escritório pelo navegador e entre com a sua conta.</li><li>Em Minha conta › Conectar o Word, digite este código e o do autenticador.</li><li>Clique em <b>Permitir</b>.</li>";
      return topo({ estado: "nao" }) + '<div class="p-corpo"><div class="estado-tela">' +
        '<h1 class="p-h">' + (MONTAGEM === "A" ? "Confira o código na janela do PAULUS" : "Confirme o código no PAULUS do escritório") + "</h1>" +
        '<div class="codigo" aria-label="Código ' + esc(falado) + '">' + esc(codigo) + "</div>" +
        '<ol class="passos-mini">' + passos + "</ol>" +
        '<div class="linha-btns"><button class="btn fantasma" data-acao="cancelar">Cancelar</button></div></div></div>' +
        rodape(andando(MONTAGEM === "A" ? "Esperando a confirmação na janela do PAULUS…" : "Esperando a confirmação no PAULUS…"));
    },
    inicio: function () {
      var pedida = FUNCOES.filter(function (f) { return f.tela === TELA_PEDIDA; })[0];
      var avisoTela = pedida && !pedida.pronta
        ? '<div class="aviso neutro" role="status"><span><b>' + esc(pedida.nome) + "</b> chega numa próxima versão do PAVLVS.</span></div>" : "";
      var cartoes = FUNCOES.map(function (f) {
        var desligada = !f.pronta;
        return '<button class="funcao" data-acao="funcao" data-tela="' + f.tela + '"' + (desligada ? ' aria-disabled="true"' : "") + ">" +
          I[f.ico] + '<span><b>' + esc(f.nome) + (desligada ? '<span class="breve">em breve</span>' : "") + "</b>" +
          '<span class="linha">' + esc(f.linha) + "</span></span></button>";
      }).join("");
      return topo() + '<div class="p-corpo">' + avisoTela +
        '<div><div class="rotulo">Documento aberto</div><div class="corta" style="font-weight:600;font-size:13px" title="' + esc(st.documento) + '">' +
        esc(st.documento || "Documento sem nome (ainda não salvo)") + "</div></div>" +
        '<div class="funcoes">' + cartoes + "</div>" +
        '<label class="chave"><input type="checkbox" role="switch" data-acao="controlada"' + (st.controlada ? " checked" : "") + "> " +
        "<span>Inserir como alteração controlada: <b>" + (st.controlada ? "sim" : "não") + "</b></span></label>" +
        "</div>" + rodape("Pronto · " + esc((st.eu && st.eu.pessoa) || ""));
    },
    fechado: function () {
      var titulo = MONTAGEM === "A" ? "O PAULUS está fechado neste computador" : "O PAULUS do escritório não respondeu";
      var texto = MONTAGEM === "A" ? "Abra o PAULUS e tente de novo. O documento não foi lido."
        : "O computador do escritório pode estar desligado, ou o acesso de fora, fechado. Nada do documento foi enviado.";
      return topo({ estado: "mal" }) + '<div class="p-corpo">' +
        tela(I.tomada, titulo, '<p class="p-sub">' + texto + "</p>", '<button class="btn primario" data-acao="tentar">Tentar de novo</button>') +
        "</div>" + rodape("Sem conexão");
    },
    semrede: function () {
      return topo({ estado: "mal" }) + '<div class="p-corpo">' + tela(I.semrede, "Sem conexão com o escritório",
        '<p class="p-sub">Este Word fala com o PAULUS pela internet, e a internet caiu. Nada do documento foi enviado.</p>',
        '<button class="btn primario" data-acao="tentar">Tentar de novo</button>') + "</div>" + rodape("Sem conexão · tentando de novo em 20 s");
    },
    semapi: function () {
      return topo({ estado: "nao" }) + '<div class="p-corpo">' + tela(I.word, "Este Word é antigo demais para o PAULUS",
        '<p class="p-sub">O PAULUS precisa do Word 2021, 2024 ou Microsoft 365. Este é o Word ' + esc(st.word || "sem versão conhecida") + ".</p>" +
        '<p class="p-sub">Atualize o Office ou escreva no editor do próprio PAULUS.</p>', "") + "</div>" +
        rodape("Nenhuma função disponível neste Word");
    },
    erro: function () {
      return topo({ estado: "mal" }) + '<div class="p-corpo">' + tela(I.erro, "Não deu para conectar agora",
        '<p class="p-sub">' + esc(st.aviso || "O PAULUS respondeu com um erro. O documento não mudou.") + "</p>" +
        "<details><summary>Detalhes para o suporte</summary>" + esc(st.erroDetalhe || "") + "</details>",
        '<button class="btn primario" data-acao="tentar">Tentar de novo</button>') + "</div>" + rodape("Erro");
    },
  };

  function desenhar(nome) {
    if (nome) st.tela = nome;
    var raiz = document.getElementById("painel");
    var foco = document.activeElement && document.activeElement.dataset ? document.activeElement.dataset.acao : null;
    raiz.innerHTML = (TELAS[st.tela] || TELAS.erro)();
    largura();
    // O foco não se perde ao redesenhar: volta ao botão de mesma ação.
    if (foco) { var el = raiz.querySelector('[data-acao="' + foco + '"]'); if (el) el.focus(); }
  }

  // ------------------------------------------------------------ fluxo
  var esperaRede = null;
  function falhou(f) {
    if (f && f.tipo === "token") {
      gravarToken("");
      st.aviso = "A conexão deste Word foi revogada no PAULUS. Conecte de novo.";
      return desenhar("primeira");
    }
    if (f && f.tipo === "rede") {
      if (MONTAGEM === "C" && navigator.onLine === false) {
        desenhar("semrede");
        clearTimeout(esperaRede);
        esperaRede = setTimeout(conferir, 20000);
        return;
      }
      return desenhar("fechado");
    }
    st.aviso = (f && f.detalhe) || "";
    st.erroDetalhe = "conectar · " + ((f && f.status) || "?") + " · " + new Date().toLocaleString("pt-BR");
    desenhar("erro");
  }

  function conferir() {
    if (!st.token) { desenhar("primeira"); return Promise.resolve(); }
    return api("GET", "/api/word/s/eu").then(function (eu) {
      st.eu = eu;
      st.aviso = "";
      st.controlada = !(eu && eu.preferencias && eu.preferencias.controlada === false);
      desenhar("inicio");
    }).catch(falhou);
  }

  function conectar() {
    st.aviso = "";
    return api("POST", "/api/word/parear", { word: st.word }).then(function (p) {
      st.pedido = p;
      desenhar("conectando");
      esperar();
    }).catch(falhou);
  }

  function esperar() {
    clearTimeout(st.espera);
    var p = st.pedido;
    if (!p) return;
    st.espera = setTimeout(function () {
      api("POST", "/api/word/parear/trocar", { pedido: p.pedido, segredo: p.segredo }).then(function (r) {
        if (st.pedido !== p) return;
        if (r.estado === "esperando") return esperar();
        st.pedido = null;
        if (r.estado === "permitido") { gravarToken(r.token); return conferir(); }
        st.aviso = r.estado === "recusado" ? "O pedido foi recusado no PAULUS." : "O código venceu. Peça outro.";
        desenhar("primeira");
      }).catch(function (f) { st.pedido = null; falhou(f); });
    }, 1500);
  }

  function preferir(controlada) {
    st.controlada = controlada;
    desenhar();
    api("PUT", "/api/word/s/preferencias", { controlada: controlada }).catch(falhou);
  }

  function desconectar() {
    st.menu = false;
    api("DELETE", "/api/word/s/eu").catch(function () { /* revogado ou fora do ar: o token sai daqui do mesmo jeito */ })
      .then(function () {
        gravarToken("");
        st.eu = null;
        st.aviso = "";
        desenhar("primeira");
      });
  }

  document.addEventListener("click", function (e) {
    var alvo = e.target.closest("[data-acao]");
    if (!alvo) { if (st.menu) { st.menu = false; desenhar(); } return; }
    var acao = alvo.dataset.acao;
    if (acao === "conectar") conectar();
    else if (acao === "cancelar") { clearTimeout(st.espera); st.pedido = null; desenhar("primeira"); }
    else if (acao === "tentar") { desenhar("abrindo"); conferir(); }
    else if (acao === "menu") { st.menu = !st.menu; desenhar(); }
    else if (acao === "desconectar") desconectar();
    else if (acao === "inicio") { TELA_PEDIDA = "inicio"; desenhar("inicio"); }
    else if (acao === "funcao") { /* as funções chegam nas próximas etapas (W2–W6) */ }
  });
  document.addEventListener("change", function (e) {
    if (e.target.dataset && e.target.dataset.acao === "controlada") preferir(e.target.checked);
  });
  document.addEventListener("keydown", function (e) {
    if (e.key === "Escape" && st.menu) { st.menu = false; desenhar(); }
  });

  // ------------------------------------------------------------ abrir
  function nomeDoDocumento() {
    try {
      var url = Office.context.document.url || "";
      var nome = decodeURIComponent(url.split(/[\\/]/).pop() || "");
      return nome;
    } catch (e) { return ""; }
  }

  function conjuntos() {
    var r = {};
    var s = Office.context.requirements;
    ["1.1", "1.2", "1.3", "1.4", "1.5", "1.6"].forEach(function (v) { r["WordApi " + v] = s.isSetSupported("WordApi", v); });
    r["AddinCommands 1.1"] = s.isSetSupported("AddinCommands", "1.1");
    r["KeyboardShortcuts 1.1"] = s.isSetSupported("KeyboardShortcuts", "1.1");
    r["DialogApi 1.1"] = s.isSetSupported("DialogApi", "1.1");
    return r;
  }

  function avisarQueCarregou() {
    // Sem token e sem texto do documento: só a versão do Word, os conjuntos
    // e o que a CSP barrou. É o que deixa a tela do PAULUS dizer "instalado".
    setTimeout(function () {
      api("POST", "/api/word/carregou", {
        word: st.word, plataforma: st.plataforma, conjuntos: st.conjuntos, montagem: MONTAGEM, violacoes: st.violacoes,
      }).catch(function () { /* fora do ar: o resto da tela diz */ });
    }, 1500);
  }

  function abrir() {
    if (typeof Office === "undefined") { desenhar("foraDoWord"); return; }
    Office.onReady(function (info) {
      if (!info || !info.host) { desenhar("foraDoWord"); return; }
      var diag = Office.context.diagnostics || {};
      st.word = diag.version || "";
      st.plataforma = String(info.platform || "");
      st.conjuntos = conjuntos();
      st.documento = nomeDoDocumento();
      aplicarTema();
      setInterval(aplicarTema, 2000);
      try {
        Office.context.document.addHandlerAsync(Office.EventType.OfficeThemeChanged, aplicarTema);
      } catch (e) { /* o Word 2021 não tem o evento: a leitura a cada 2 s cobre */ }
      avisarQueCarregou();
      if (!Office.context.requirements.isSetSupported("WordApi", "1.3")) { desenhar("semapi"); return; }
      conferir();
    });
  }

  largura();
  abrir();
})();
