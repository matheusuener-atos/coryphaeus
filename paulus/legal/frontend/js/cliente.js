/* ------------------------------------------------------- area do cliente */
/*
   A Area do cliente (docs/PLANO-AREA-CLIENTE.md, src/area_cliente.py): a
   pagina que o cliente abre pelo link do escritorio (frontend/cliente.html) e
   a previa "Ver como o cliente", dentro do Paulus (js/94-area-cliente.js).
   As duas desenham pela mesma funcao e a mesma resposta da API - o advogado
   ve o que o cliente ve, e nao uma imitacao.

   Tudo mora dentro de window.AreaCliente: este arquivo entra tambem no
   index.html do Paulus, e nenhum nome daqui pode esbarrar num de la.

   Na pagina do cliente: entrar (e-mail -> codigo), a lista das pastas (com
   mais de uma) e a pasta - "Para voce", o resumo, as proximas datas, o
   andamento, os documentos e a conversa com o escritorio.
*/
window.AreaCliente = (function () {
  "use strict";

  var MESES = ["jan", "fev", "mar", "abr", "mai", "jun", "jul", "ago", "set", "out", "nov", "dez"];
  var MESES_LONGOS = ["janeiro", "fevereiro", "março", "abril", "maio", "junho", "julho", "agosto", "setembro", "outubro", "novembro", "dezembro"];
  var SEMANA = ["domingo", "segunda", "terça", "quarta", "quinta", "sexta", "sábado"];

  // O servidor do escritorio desligado: a Cloudflare responde pelo tunel
  // (502, 503, 504, 530) ou a rede falha. A frase e esta, e nao um erro tecnico.
  var FORA = [502, 503, 504, 520, 521, 522, 523, 524, 530];
  var FORA_DO_AR = "O escritório está fora do ar agora. Tente de novo mais tarde.";

  // O estado da pagina do cliente (a previa nao usa: desenha e pronto).
  var st = { token: "", csrf: "", eu: null, pastaId: null, visao: null, etapa: "", relogio: null, enviando: false };

  function esc(t) {
    return String(t == null ? "" : t).replace(/[&<>"']/g, function (c) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c];
    });
  }

  // O calendario do Admin (mes, setas, dias da semana, hoje marcado, dias passados apagados), para escolher um dia so.
  // O mes por extenso e o MESES_LONGOS: um segundo "var MESES" aqui trocava os meses curtos da pagina inteira
  // ("16 outubro" no lugar de "16 out", e o "OUTUBRO" sem caber no quadrinho das proximas datas).
  function isoDe(d) { return d.getFullYear() + "-" + String(d.getMonth() + 1).padStart(2, "0") + "-" + String(d.getDate()).padStart(2, "0"); }
  function montarCalRemarcar(form) {
    var caixa = form.querySelector("[data-pcl-cal]"); if (!caixa) return;
    var base = new Date(); base.setDate(1);
    var mes = form._mes || base;
    var hoje = isoDe(new Date());
    var ini = new Date(mes.getFullYear(), mes.getMonth(), 1), comeco = new Date(ini); comeco.setDate(1 - ini.getDay());
    var h = '<div class="pcl-cal-topo"><button type="button" class="pcl-btn-icone" data-pcl-cal-mes="-1" aria-label="Mês anterior"' + (mes <= base ? " disabled" : "") + ">" + ic("chevron_left") + "</button><b>" + MESES_LONGOS[mes.getMonth()] + " " + mes.getFullYear() + '</b><button type="button" class="pcl-btn-icone" data-pcl-cal-mes="1" aria-label="Próximo mês">' + ic("chevron_right") + "</button></div>" +
      '<div class="pcl-cal-grade">' + ["D", "S", "T", "Q", "Q", "S", "S"].map(function (s) { return '<span class="pcl-cal-sem">' + s + "</span>"; }).join("");
    for (var i = 0; i < 42; i++) {
      var d = new Date(comeco); d.setDate(comeco.getDate() + i); var iso = isoDe(d);
      var fora = d.getMonth() !== mes.getMonth(), antes = iso < hoje, fim = d.getDay() === 0 || d.getDay() === 6;
      h += '<button type="button" class="pcl-cal-dia' + (fora ? " fora" : "") + (iso === hoje ? " hoje" : "") + (iso === form.dataset.dia ? " on" : "") + '" data-pcl-dia="' + iso + '"' + (antes || fim ? " disabled" : "") + ">" + d.getDate() + "</button>";
    }
    caixa.innerHTML = h + "</div>";
    caixa.querySelectorAll("[data-pcl-cal-mes]").forEach(function (b) { b.onclick = function () { form._mes = new Date(mes.getFullYear(), mes.getMonth() + Number(b.dataset.pclCalMes), 1); montarCalRemarcar(form); }; });
    caixa.querySelectorAll("[data-pcl-dia]").forEach(function (b) { b.onclick = function () { form.dataset.dia = b.dataset.pclDia; montarCalRemarcar(form); escolhaRemarcar(form); }; });
    form.querySelectorAll("[data-pcl-periodo]").forEach(function (b) {
      b.onclick = function () { form.dataset.periodo = b.dataset.pclPeriodo; form.querySelectorAll("[data-pcl-periodo]").forEach(function (x) { var on = x === b; x.classList.toggle("on", on); x.setAttribute("aria-checked", on); }); escolhaRemarcar(form); };
    });
  }
  function escolhaRemarcar(form) {
    var p = form.querySelector("[data-pcl-escolha]"); if (!p || !form.dataset.dia) return;
    var d = new Date(form.dataset.dia + "T12:00");
    p.classList.remove("falta");
    p.textContent = "Vamos pedir: " + d.toLocaleDateString("pt-BR", { weekday: "long", day: "numeric", month: "long" }) + ", " + (form.dataset.periodo || "Qualquer horário").toLowerCase() + ".";
  }
  function iniciaisDe(n) { var p = String(n || "").trim().split(/\s+/).filter(Boolean); return p.length ? (p.length > 1 ? p[0][0] + p[p.length - 1][0] : p[0].slice(0, 2)).toUpperCase() : "?"; }
  function ic(nome) {
    return '<span class="ic" aria-hidden="true">' + nome + "</span>";
  }

  function data(iso) {
    var m = /^(\d{4})-(\d{2})-(\d{2})/.exec(iso || "");
    return m ? new Date(Number(m[1]), Number(m[2]) - 1, Number(m[3])) : null;
  }

  function diasAte(iso) {
    var d = data(iso);
    if (!d) return 9999;
    var hoje = new Date();
    hoje.setHours(0, 0, 0, 0);
    return Math.round((d - hoje) / 86400000);
  }

  function dataCurta(iso) {
    var d = data(iso);
    return d ? d.getDate() + " " + MESES[d.getMonth()] : "";
  }

  function dataLonga(iso) {
    var d = data(iso);
    if (!d) return "";
    var dias = diasAte(iso);
    var dia = dias === 0 ? "hoje" : (dias === 1 ? "amanhã" : SEMANA[d.getDay()]);
    return dia + ", " + d.getDate() + " de " + MESES_LONGOS[d.getMonth()];
  }

  function quandoMsg(iso) {
    var d = new Date(iso);
    if (isNaN(d)) return "";
    var hora = d.toLocaleTimeString("pt-BR", { hour: "2-digit", minute: "2-digit" });
    var dias = -diasAte(String(iso).slice(0, 10));
    if (dias === 0) return "hoje " + hora;
    if (dias === 1) return "ontem " + hora;
    return d.getDate() + " " + MESES[d.getMonth()] + " " + hora;
  }

  function plural(n, um, varios) {
    return n + " " + (n === 1 ? um : (varios || um + "s"));
  }

  /* ------------------------------------------------- desenhar a pasta */

  function classeDoStatus(status) {
    if (status === "aguardando") return "pcl-selo aguardando";
    if (status === "concluido") return "pcl-selo concluido";
    return "pcl-selo";
  }

  function desabilitado(ctx) {
    return ctx.previa ? ' disabled title="Na prévia, os botões não fazem nada: funcionam para o cliente"' : "";
  }

  function pendencia(p, ctx) {
    if (p.pendencia === "confirmar") {
      var c = p.confirmacao || {};
      var quando = dataLonga(p.quando) + (p.hora ? " às " + p.hora : "") + (p.onde ? " · " + p.onde : "");
      var estado = c.resposta === "remarcar"
        ? '<p class="pcl-respondido espera">' + ic("schedule") + "Você pediu para remarcar: " + esc(c.sugestao) + ". O escritório vai responder.</p>"
        : "";
      return '<div class="pcl-pend" data-pcl-pend="c' + p.id + '">' +
        '<div class="pcl-pend-titulo">' + ic("event") + "<div><b>Confirmar: " + esc(p.titulo) + "</b><small>" + esc(quando) + "</small></div></div>" +
        estado +
        '<div class="pcl-acoes"><button type="button" class="pcl-botao primario" data-pcl-confirmar="' + p.id + '"' + desabilitado(ctx) + ">" + ic("check_circle") + "Confirmo</button>" +
        (c.resposta === "remarcar" ? "" : '<button type="button" class="pcl-botao" data-pcl-remarcar="' + p.id + '"' + desabilitado(ctx) + ">Preciso remarcar</button>") + "</div>" +
        '<form class="pcl-remarcar" data-pcl-remarcar-form="' + p.id + '" hidden><span class="pcl-remarcar-tit">Pedir para remarcar</span>' +
        '<div class="pcl-remarcar-grade"><div class="pcl-campo"><label>Que dia fica melhor?</label><div class="pcl-cal" data-pcl-cal="1"></div></div>' +
        '<div class="pcl-remarcar-lado"><div class="pcl-campo"><label>Em que período?</label><div class="pcl-periodos" role="radiogroup">' +
        ["Manhã", "Tarde", "Qualquer horário"].map(function (t, i) { return '<button type="button" class="pcl-periodo' + (i === 2 ? " on" : "") + '" role="radio" aria-checked="' + (i === 2) + '" data-pcl-periodo="' + t + '">' + t + "</button>"; }).join("") + "</div></div>" +
        '<div class="pcl-campo"><label for="pcl-sug-' + p.id + '">Algo mais? (opcional)</label>' +
        '<input id="pcl-sug-' + p.id + '" type="text" maxlength="300" placeholder="Ex.: depois das 15h" autocomplete="off"></div>' +
        '<p class="pcl-remarcar-escolha" data-pcl-escolha="1">Escolha um dia no calendário.</p></div></div>' +
        '<div class="pcl-acoes"><button type="submit" class="pcl-botao primario">Mandar</button><button type="button" class="pcl-botao" data-pcl-remarcar-fechar="' + p.id + '">Voltar</button></div></form>' +
        "</div>";
    }
    var prazo = p.quando ? (diasAte(p.quando) < 0 ? "era até " + dataCurta(p.quando) : "até " + dataLonga(p.quando)) : "";
    return '<div class="pcl-pend" data-pcl-pend="e' + p.indice + '">' +
      '<div class="pcl-pend-titulo">' + ic("task_alt") + "<div><b>" + esc(p.titulo) + "</b>" + (prazo ? "<small>" + esc(prazo) + "</small>" : "") + "</div></div>" +
      '<div class="pcl-acoes"><button type="button" class="pcl-botao primario" data-pcl-enviar="' + p.indice + '"' + desabilitado(ctx) + ">" + ic("upload") + "Enviar arquivo</button>" +
      '<button type="button" class="pcl-botao" data-pcl-feita="' + p.indice + '"' + desabilitado(ctx) + ">Já fiz</button></div></div>";
  }

  function linhaDeData(d, ctx) {
    var dia = data(d.quando);
    var caixa = '<div class="pcl-dia"><b>' + (dia ? dia.getDate() : "") + "</b><small>" + (dia ? MESES[dia.getMonth()] : "") + "</small></div>";
    var sub = [];
    if (d.hora) sub.push(d.hora);
    if (d.onde) sub.push(d.onde);
    if (d.tipo === "etapa") sub.push(d.do_cliente ? "cabe a você" : "prazo de uma etapa");
    var extra = "";
    if (d.tipo === "compromisso") {
      var acoes = [];
      if (d.sala) acoes.push('<a class="pcl-link" href="' + esc(d.sala) + '" target="_blank" rel="noopener noreferrer">' + ic("video_call") + "<span>Entrar na sala</span></a>");
      acoes.push(ctx.previa
        ? '<span class="pcl-link"' + desabilitado(ctx) + ">" + ic("calendar_month") + "<span>Pôr na minha agenda</span></span>"
        : '<a class="pcl-link" href="' + esc(ctx.urlAgenda(d.id)) + '" data-pcl-agenda="1">' + ic("calendar_month") + "<span>Pôr na minha agenda</span></a>");
      if (d.confirmacao && d.confirmacao.resposta === "confirmado") extra = '<p class="pcl-respondido">' + ic("check_circle") + "Você confirmou este horário.</p>";
      extra += '<div class="pcl-acoes">' + acoes.join("") + "</div>";
    }
    return '<div class="pcl-data">' + caixa + '<div class="pcl-data-corpo"><b>' + esc(d.titulo) + "</b>" +
      (sub.length ? "<small>" + esc(dataLonga(d.quando) + " · " + sub.join(" · ")) + "</small>" : "<small>" + esc(dataLonga(d.quando)) + "</small>") +
      extra + "</div></div>";
  }

  function linhaDeEtapa(e) {
    var classe = "pcl-etapa" + (e.feita ? " feita" : "");
    var quando = e.feita ? (e.feita_em ? dataCurta(e.feita_em) : "feito") : (e.quando ? "até " + dataCurta(e.quando) : "");
    return '<div class="' + classe + '">' + ic(e.feita ? "check_circle" : "radio_button_unchecked") +
      "<b>" + esc(e.titulo) + (e.do_cliente && !e.feita ? '<span class="pcl-tag">com você</span>' : "") + "</b>" +
      "<small>" + esc(quando) + "</small></div>";
  }

  function linhaDeDocumento(d) {
    var pdf = /\.pdf$/i.test(d.nome);
    return '<button type="button" class="pcl-doc" data-pcl-doc="' + esc(d.sha1) + '">' + ic(pdf ? "picture_as_pdf" : "description") +
      "<span><b>" + esc(d.nome) + "</b><small>compartilhado em " + esc(dataCurta(d.desde)) + "</small></span>" + ic("chevron_right") + "</button>";
  }

  function mensagem(m) {
    var minha = m.de === "cliente";
    var cita = m.etapa ? '<span class="pcl-citacao">' + ic("subdirectory_arrow_right") + esc(m.etapa) + "</span>" : "";
    var texto = m.anexo ? ic("attach_file") + " " + esc(m.texto) : esc(m.texto);
    return '<div class="pcl-msg' + (minha ? " minha" : "") + '"><p>' + cita + texto + "</p>" +
      "<small>" + esc((minha ? "você" : m.autor) + " · " + quandoMsg(m.quando)) + "</small></div>";
  }

  function secao(titulo, extra, corpo) {
    return '<section class="pcl-secao"><h2>' + esc(titulo) + (extra ? "<small>" + esc(extra) + "</small>" : "") + "</h2>" + corpo + "</section>";
  }

  /* A pasta inteira, em HTML, a partir da visao da API. `ctx`: previa,
     nomeDoCliente (na previa), voltar (ha lista de pastas). */
  function htmlDaPasta(v, ctx) {
    var p = v.pasta;
    var topo = '<div class="pcl-topo">' +
      (ctx.voltar ? '<button type="button" class="pcl-botao-leve" data-pcl-voltar="1">' + ic("arrow_back") + "Pastas</button>" : '<span class="pcl-marca">PAVLVS</span>') +
      '<span class="pcl-espaco"></span>' +
      (ctx.previa ? "" : '<button type="button" class="pcl-botao-leve" data-pcl-sair="1">' + ic("logout") + "Sair</button>") + "</div>";
    var cabeca = '<header class="pcl-cabeca"><span class="pcl-kicker">' + esc(v.escritorio || "Seu escritório") + "</span>" +
      "<h1>" + esc(p.nome) + "</h1>" +
      (v.responsavel ? '<p class="pcl-sub">Quem cuida: <span class="pcl-pessoa" tabindex="0">' + esc(v.responsavel) +
        '<span class="pcl-balao" role="tooltip"><span class="pcl-avatar">' + esc(iniciaisDe(v.responsavel)) + '</span><span class="pcl-balao-txt"><b>' + esc(v.responsavel) + "</b><small>" + esc(v.escritorio || "Seu escritório") + " · cuida desta pasta</small></span></span></span></p>" : "") +
      '<div class="pcl-situacao"><span class="' + classeDoStatus(p.status) + '">' + esc(p.status_rotulo) + "</span>" +
      (v.andamento.length ? '<span class="pcl-barra" role="progressbar" aria-valuemin="0" aria-valuemax="100" aria-valuenow="' + p.progresso + '"><i style="width:' + p.progresso + '%"></i></span>' +
        '<span class="pcl-pct">' + p.progresso + "%</span>" : "") + "</div></header>";

    // Largura e paineis da Visao geral do Admin: o que pede acao e a conversa na coluna larga; datas, andamento e documentos ao lado.
    var painel = function (rot, dir, miolo) { return '<section class="pcl-painel"><div class="pcl-painel-cab"><span class="pcl-rotulo">' + esc(rot) + "</span>" + (dir ? '<span class="pcl-cab-dir">' + esc(dir) + "</span>" : "") + "</div>" + miolo + "</section>"; };
    var esq = [], dir = [];
    if (v.pendencias.length) esq.push(painel("Para você", plural(v.pendencias.length, "pendência", "pendências"), '<div class="pcl-cartao">' + v.pendencias.map(function (x) { return pendencia(x, ctx); }).join("") + "</div>"));
    if (v.resumo && v.resumo.texto) esq.push(painel("Resumo", v.resumo.em ? "escrito em " + dataCurta(v.resumo.em) : "", '<div class="pcl-cartao"><p class="pcl-texto">' + esc(v.resumo.texto) + "</p></div>"));
    var conversa = '<div class="pcl-cartao"><div class="pcl-conversa" id="pcl-conversa">' +
      (v.mensagens.length ? v.mensagens.map(mensagem).join("") : '<p class="pcl-vazio">Escreva ao escritório por aqui. Quando responderem, você recebe um e-mail.</p>') + "</div>" +
      '<form class="pcl-escrever" data-pcl-escrever="1">' +
      '<button type="button" class="pcl-icone-botao" data-pcl-anexar="1" title="Mandar um arquivo" aria-label="Mandar um arquivo"' + desabilitado(ctx) + ">" + ic("attach_file") + "</button>" +
      '<textarea rows="1" maxlength="4000" placeholder="Escreva ao escritório…" aria-label="Mensagem ao escritório"' + (ctx.previa ? " disabled" : "") + "></textarea>" +
      '<button type="submit" class="pcl-icone-botao primario" title="Mandar" aria-label="Mandar"' + desabilitado(ctx) + ">" + ic("send") + "</button></form></div>";
    esq.push(painel("Conversa com o escritório", "", conversa));
    dir.push(painel("Próximas datas", v.datas.length ? String(v.datas.length) : "", '<div class="pcl-cartao">' +
      (v.datas.length ? v.datas.map(function (d) { return linhaDeData(d, ctx); }).join("") : '<p class="pcl-vazio">Nenhuma data marcada por enquanto.</p>') + "</div>"));
    dir.push(painel("Andamento", v.andamento.length ? v.andamento.filter(function (e) { return e.feita; }).length + " de " + v.andamento.length : "",
      '<div class="pcl-cartao">' + (v.andamento.length ? v.andamento.map(linhaDeEtapa).join("") : '<p class="pcl-vazio">O escritório ainda não registrou as etapas.</p>') + "</div>"));
    dir.push(painel("Documentos", v.documentos.length ? String(v.documentos.length) : "", '<div class="pcl-cartao">' +
      (v.documentos.length ? v.documentos.map(linhaDeDocumento).join("") : '<p class="pcl-vazio">Nenhum documento compartilhado ainda.</p>') + "</div>"));
    var aviso = '<p class="pcl-aviso-registro">' + ic("visibility") + "<span>O escritório vê quando você entra, abre, baixa ou imprime um documento. Cada página aberta leva o seu nome e a hora.</span></p>";
    var faixa = ctx.previa ? '<p class="pcl-previa-faixa">Prévia: é assim que ' + esc(ctx.nomeDoCliente || "o cliente") + " vê esta pasta. Os botões funcionam só para ele.</p>" : "";
    return faixa + '<div class="pcl-coluna pcl-larga pcl-pasta-tela">' + topo + cabeca +
      '<div class="pcl-pasta-grade"><div class="pcl-pilha">' + esq.join("") + '</div><div class="pcl-pilha">' + dir.join("") + "</div></div>" + aviso + "</div>" +
      '<input type="file" id="pcl-arquivo" hidden accept=".pdf,.jpg,.jpeg,.png,.docx,.xlsx,.txt">';
  }

  /* -------------------------------------------- o documento aberto */

  function abrirDocumento(raiz, doc, urlPagina, urlBaixar, servicoId) {
    // As paginas uma depois da outra, numa coluna que rola; o contador acompanha a pagina que esta a vista.
    var visor = document.createElement("div");
    visor.className = "pcl-visor";
    visor.setAttribute("role", "dialog");
    visor.setAttribute("aria-label", doc.nome);
    var pdf = /\.pdf$/i.test(doc.nome);
    visor.innerHTML = '<div class="pcl-visor-topo"><button type="button" class="pcl-botao-leve" data-pcl-fechar="1" aria-label="Fechar">' + ic("close") + "</button>" +
      "<b>" + esc(doc.nome) + '</b><span class="pcl-visor-num" data-pcl-num="1">…</span>' +
      (urlBaixar ? '<a class="pcl-botao-leve" href="' + esc(urlBaixar) + '" data-pcl-baixar="1">' + ic("download") + "Baixar</a>" : "") + "</div>" +
      '<div class="pcl-visor-paginas" data-pcl-paginas="1"></div>' +
      '<div class="pcl-visor-pe"><small>' + (pdf || !urlBaixar ? "Cada página leva o nome de quem abriu e a hora." :
        "Cada página aqui leva o nome de quem abriu e a hora. O arquivo baixado vai no formato original, sem a marca.") + "</small></div>";
    raiz.appendChild(visor);
    var lista = visor.querySelector("[data-pcl-paginas]");
    var num = visor.querySelector("[data-pcl-num]");
    var urls = [], total = 1, fechado = false, olho = null;
    function pagina(n) {
      var fig = document.createElement("div");
      fig.className = "pcl-visor-pagina"; fig.dataset.n = n;
      fig.innerHTML = '<img alt="Página ' + n + ' do documento"><span class="pcl-visor-carregando">carregando…</span>';
      lista.appendChild(fig);
      return fetch(urlPagina(doc.sha1, n), { credentials: "same-origin" }).then(function (r) {
        if (!r.ok) throw new Error(r.status === 401 ? "sessao" : "erro");
        if (n === 1) total = Number(r.headers.get("x-paginas") || 1) || 1;
        return r.blob();
      }).then(function (b) {
        if (fechado) return;
        var u = URL.createObjectURL(b); urls.push(u);
        fig.querySelector("img").src = u;
        var c = fig.querySelector(".pcl-visor-carregando"); if (c) c.remove();
        if (olho) olho.observe(fig);
      }).catch(function (e) {
        var c = fig.querySelector(".pcl-visor-carregando");
        if (c) c.textContent = e.message === "sessao" ? "a sessão acabou — entre de novo" : "não consegui abrir esta página";
        throw e;
      });
    }
    function contar(n) { num.textContent = n + " de " + total; }
    if (window.IntersectionObserver) {
      olho = new IntersectionObserver(function (es) {
        es.forEach(function (e) { if (e.isIntersecting) contar(Number(e.target.dataset.n)); });
      }, { root: lista, threshold: 0.5 });
    }
    function fechar() {
      fechado = true;
      urls.forEach(function (u) { URL.revokeObjectURL(u); });
      if (olho) olho.disconnect();
      document.removeEventListener("keydown", teclas);
      visor.remove();
      st.docAberto = null;
    }
    function teclas(e) { if (e.key === "Escape") fechar(); }
    visor.querySelector("[data-pcl-fechar]").onclick = fechar;
    document.addEventListener("keydown", teclas);
    st.docAberto = { nome: doc.nome, servico: servicoId };
    pagina(1).then(function () {
      contar(1);
      var seq = Promise.resolve();
      for (var n = 2; n <= total; n++) (function (k) { seq = seq.then(function () { if (!fechado) return pagina(k); }); })(n);
      return seq;
    }).catch(function () { if (num.textContent === "…") num.textContent = ""; });
  }

  /* ------------------------------------------------- a previa (Paulus) */

  /* "Ver como o cliente": a mesma pasta, desenhada a partir da MESMA visao
     (GET /api/servicos/{id}/como-cliente). Os botoes ficam travados. */
  function previa(raiz, servicoId, nomeDoCliente) {
    raiz.classList.add("pcl-pagina");
    raiz.innerHTML = '<div class="pcl-coluna"><p class="pcl-vazio">abrindo…</p></div>';
    return fetch("/api/servicos/" + servicoId + "/como-cliente").then(function (r) {
      if (!r.ok) throw new Error("não consegui abrir a prévia");
      return r.json();
    }).then(function (v) {
      raiz.innerHTML = htmlDaPasta(v, { previa: true, nomeDoCliente: nomeDoCliente });
      raiz.querySelectorAll("[data-pcl-doc]").forEach(function (b) {
        b.onclick = function () {
          var doc = v.documentos.find(function (d) { return d.sha1 === b.dataset.pclDoc; });
          abrirDocumento(raiz, doc, function (sha1, n) {
            return "/api/servicos/" + servicoId + "/como-cliente/documentos/" + sha1 + "/pagina?n=" + n;
          }, "", servicoId);
        };
      });
    }).catch(function (e) {
      raiz.innerHTML = '<div class="pcl-coluna"><p class="pcl-erro">' + esc(e.message) + "</p></div>";
    });
  }

  /* ---------------------------------------------- a pagina do cliente */

  function raiz() {
    return document.getElementById("pcl-raiz");
  }

  function api(caminho, opcoes) {
    opcoes = opcoes || {};
    var cab = Object.assign({}, opcoes.headers || {});
    if (opcoes.method && opcoes.method !== "GET" && st.csrf) cab["x-paulus-csrf"] = st.csrf;
    if (opcoes.json !== undefined) {
      cab["content-type"] = "application/json";
      opcoes.body = JSON.stringify(opcoes.json);
    }
    return fetch(caminho, { method: opcoes.method || "GET", headers: cab, body: opcoes.body, credentials: "same-origin" }).catch(function () {
      throw new Error(FORA_DO_AR);
    }).then(function (r) {
      if (FORA.indexOf(r.status) >= 0) throw new Error(FORA_DO_AR);
      if (r.status === 401 && caminho !== "/api/cliente/eu") {
        st.eu = null;
        telaDeEntrar("A sessão acabou. Entre de novo.");
        throw new Error("sessao");
      }
      return r.json().catch(function () { return {}; }).then(function (d) {
        if (!r.ok) throw new Error(d.detail || "algo deu errado (" + r.status + ")");
        return d;
      });
    });
  }

  /* Erro de campo e a borda do campo, sem texto na tela (regra de 08/10/2026):
     campo-erro / campo-ok no input, aria-invalid e a frase num .pcl-so-leitor
     apontado por aria-describedby. Este arquivo vive sozinho na pagina do
     cliente: o mesmo que marcarCampo do Paulus (js/00-base.js), aqui dentro. */
  function marcar(campo, estado, frase) {
    if (!campo) return;
    campo.classList.toggle("campo-erro", estado === "erro");
    campo.classList.toggle("campo-ok", estado === "ok");
    var id = campo.id + "-sr";
    var sr = document.getElementById(id);
    if (estado === "erro") {
      campo.setAttribute("aria-invalid", "true");
      if (!sr) {
        sr = document.createElement("span");
        sr.id = id;
        sr.className = "pcl-so-leitor";
        sr.setAttribute("aria-live", "polite");
        campo.insertAdjacentElement("afterend", sr);
      }
      sr.textContent = frase ? frase.charAt(0).toUpperCase() + frase.slice(1) : "";
      campo.setAttribute("aria-describedby", id);
    } else {
      campo.removeAttribute("aria-invalid");
      campo.removeAttribute("aria-describedby");
      if (sr) sr.remove();
    }
  }

  /* `regra(valor)`: "" certo, frase errado. Mostra estado depois de tocado
     (saiu do campo com algo escrito, ou tentou enviar); vermelho atualiza ao vivo. */
  function vigiar(campo, regra) {
    var tocado = false;
    var pintar = function () { var p = regra(campo.value); marcar(campo, p ? "erro" : "ok", p); return p; };
    campo.addEventListener("blur", function () { if (campo.value.trim() || tocado) { tocado = true; pintar(); } });
    campo.addEventListener("input", function () {
      if (!tocado) return;
      if (regra(campo.value) && !campo.classList.contains("campo-erro")) marcar(campo, "");
      else pintar();
    });
    return function () { tocado = true; return pintar(); };
  }

  var regraEmail = function (v) { return /^[^\s@<>"]+@[^\s@<>"]+\.[a-z]{2,}$/i.test(String(v).trim()) ? "" : "confira o e-mail"; };
  var regraCodigo = function (v) { return /^\d{6}$/.test(v) ? "" : "o código tem 6 números"; };

  function telaDeEntrar(aviso) {
    pararRelogio();
    var r = raiz();
    r.innerHTML = '<div class="pcl-entrada"><h1>Área do cliente</h1>' +
      "<p>Digite o e-mail em que você recebeu o link. Mandamos um código para ele.</p>" +
      '<form class="pcl-form" data-pcl-form-email="1"><div class="pcl-campo"><label for="pcl-email">E-mail</label>' +
      '<input id="pcl-email" type="email" inputmode="email" autocomplete="email" required maxlength="200"></div>' +
      (aviso ? '<p class="pcl-erro">' + esc(aviso) + "</p>" : "") + '<p class="pcl-erro" data-pcl-erro="1" hidden></p>' +
      '<button type="submit" class="pcl-botao primario">Mandar o código</button></form>' +
      '<p class="pcl-aviso-registro">' + ic("visibility") + "<span>O escritório vê quando você entra, abre, baixa ou imprime um documento.</span></p></div>";
    var form = r.querySelector("[data-pcl-form-email]");
    var campo = r.querySelector("#pcl-email");
    var conferir = vigiar(campo, regraEmail);
    form.noValidate = true;
    campo.focus();
    form.onsubmit = function (e) {
      e.preventDefault();
      var botao = form.querySelector("button");
      var erro = form.querySelector("[data-pcl-erro]");
      erro.hidden = true;
      if (conferir()) { campo.focus(); return; }
      botao.disabled = true;
      botao.textContent = "mandando…";
      api("/api/cliente/entrar", { method: "POST", json: { token: st.token, email: campo.value.trim() } }).then(function (d) {
        telaDoCodigo(campo.value.trim(), d.para);
      }).catch(function (err) {
        botao.disabled = false;
        botao.textContent = "Mandar o código";
        // O e-mail recusado e o campo (borda vermelha, sem texto); o resto (limite, link, envio) fica no aviso.
        if (/e-mail/i.test(err.message) && !/mandar|mandamos/i.test(err.message)) { marcar(campo, "erro", err.message); campo.focus(); return; }
        erro.hidden = false;
        erro.textContent = err.message;
      });
    };
  }

  function telaDoCodigo(email, para) {
    var r = raiz();
    r.innerHTML = '<div class="pcl-entrada"><h1>Confira o e-mail</h1>' +
      "<p>Se " + esc(para || "esse e-mail") + " for o que o escritório cadastrou, o código chega em instantes. Ele vale por 10 minutos.</p>" +
      '<form class="pcl-form" data-pcl-form-codigo="1"><div class="pcl-campo"><label for="pcl-codigo">Código</label>' +
      '<input id="pcl-codigo" class="pcl-codigo" type="text" inputmode="numeric" autocomplete="one-time-code" maxlength="6" pattern="[0-9]{6}" required></div>' +
      '<label class="pcl-marcar"><input type="checkbox" id="pcl-lembrar"> Lembrar este aparelho por 30 dias</label>' +
      '<p class="pcl-erro" data-pcl-erro="1" hidden></p>' +
      '<button type="submit" class="pcl-botao primario">Entrar</button>' +
      '<div class="pcl-acoes"><button type="button" class="pcl-link" data-pcl-outro="1"><span>Mandar outro código</span></button>' +
      '<button type="button" class="pcl-link" data-pcl-trocar="1"><span>Usar outro e-mail</span></button></div></form></div>';
    var form = r.querySelector("[data-pcl-form-codigo]");
    var campo = r.querySelector("#pcl-codigo");
    var erro = form.querySelector("[data-pcl-erro]");
    var conferir = vigiar(campo, regraCodigo);
    form.noValidate = true;
    campo.focus();
    campo.oninput = function () {
      campo.value = campo.value.replace(/\D/g, "").slice(0, 6);
      if (campo.value.length === 6) form.requestSubmit ? form.requestSubmit() : form.onsubmit(new Event("submit"));
    };
    form.onsubmit = function (e) {
      e.preventDefault();
      var botao = form.querySelector('button[type="submit"]');
      erro.hidden = true;
      if (conferir()) { campo.focus(); return; }
      botao.disabled = true;
      api("/api/cliente/codigo", { method: "POST", json: { token: st.token, codigo: campo.value, lembrar: r.querySelector("#pcl-lembrar").checked } }).then(function (d) {
        st.csrf = d.csrf;
        return carregarEu();
      }).catch(function (err) {
        botao.disabled = false;
        // Codigo errado ou vencido e o campo: borda vermelha, sem texto. "Muitas vezes" e o limite ficam no aviso.
        if (/código (errado|venceu)/.test(err.message)) { marcar(campo, "erro", err.message); campo.select(); return; }
        erro.hidden = false;
        erro.textContent = err.message;
        campo.select();
      });
    };
    r.querySelector("[data-pcl-outro]").onclick = function () {
      api("/api/cliente/entrar", { method: "POST", json: { token: st.token, email: email } }).then(function () {
        erro.hidden = false;
        erro.className = "pcl-ok";
        erro.textContent = "Mandamos outro código.";
      }).catch(function (err) {
        erro.hidden = false;
        erro.className = "pcl-erro";
        erro.textContent = err.message;
      });
    };
    r.querySelector("[data-pcl-trocar]").onclick = function () { telaDeEntrar(""); };
  }

  function carregarEu() {
    return fetch("/api/cliente/eu", { credentials: "same-origin" }).catch(function () {
      throw new Error(FORA_DO_AR);
    }).then(function (r) {
      if (FORA.indexOf(r.status) >= 0) throw new Error(FORA_DO_AR);
      if (r.status === 401) { telaDeEntrar(""); return null; }
      return r.json().then(function (d) {
        if (!r.ok) throw new Error(d.detail || "não consegui abrir");
        return d;
      });
    }).then(function (eu) {
      if (!eu) return;
      st.eu = eu;
      st.csrf = eu.csrf || st.csrf;
      if (eu.pastas.length === 1) return abrirPasta(eu.pastas[0].id);
      if (st.pastaId && eu.pastas.some(function (p) { return p.id === st.pastaId; })) return abrirPasta(st.pastaId);
      telaDasPastas();
    }).catch(function (err) {
      raiz().innerHTML = '<div class="pcl-entrada"><h1>Área do cliente</h1><p class="pcl-erro">' + esc(err.message) + "</p></div>";
    });
  }

  // O inicio do cliente no desenho da Visao geral do Admin: saudacao pela hora, e paineis com cabecalho (rotulo + numero a direita).
  function saudacaoDaHora() { var h = new Date().getHours(); return h < 12 ? "Bom dia" : h < 18 ? "Boa tarde" : "Boa noite"; }
  function telaDasPastas() {
    pararRelogio();
    st.pastaId = null;
    var eu = st.eu;
    var r = raiz();
    var ps = eu.pastas || [];
    var cab = function (rot, dir) { return '<div class="pcl-painel-cab"><span class="pcl-rotulo">' + rot + "</span>" + (dir != null ? '<span class="pcl-cab-dir">' + dir + "</span>" : "") + "</div>"; };
    var linhas = ps.length ? ps.map(function (p) {
      return '<button type="button" class="pcl-linha" data-pcl-pasta="' + p.id + '"><span class="pcl-linha-ic">' + ic("folder") + '</span><span class="pcl-linha-txt"><b>' + esc(p.nome) + "</b></span>" +
        '<span class="' + classeDoStatus(p.status) + '">' + esc(p.status_rotulo) + "</span>" +
        (p.novas ? '<i class="pcl-bolinha" title="Mensagens novas">' + p.novas + "</i>" : "") + ic("chevron_right") + "</button>";
    }).join("") : '<p class="pcl-vazio-linha">Nenhuma pasta compartilhada com você agora. Se acha que é engano, fale com o escritório.</p>';
    var pend = [];
    ps.forEach(function (p) {
      if (p.status === "aguardando") pend.push({ id: p.id, ic: "task_alt", t: "O escritório espera algo de você", d: p.nome });
      if (p.novas) pend.push({ id: p.id, ic: "chat", t: p.novas + (p.novas === 1 ? " mensagem nova" : " mensagens novas"), d: p.nome });
    });
    var pendHtml = pend.length ? pend.map(function (x) {
      return '<button type="button" class="pcl-linha" data-pcl-pasta="' + x.id + '"><span class="pcl-linha-ic">' + ic(x.ic) + '</span><span class="pcl-linha-txt"><b>' + esc(x.t) + "</b><small>" + esc(x.d) + "</small></span>" + ic("chevron_right") + "</button>";
    }).join("") : '<p class="pcl-vazio-linha">Nada pendente agora.</p>';
    r.innerHTML = '<div class="pcl-coluna pcl-larga"><div class="pcl-topo"><span class="pcl-espaco"></span>' +
      '<button type="button" class="pcl-botao-leve" data-pcl-sair="1">' + ic("logout") + "Sair</button></div>" +
      '<header class="pcl-cab-tela"><h1>' + esc(saudacaoDaHora() + ", " + eu.pessoa.nome.split(" ")[0] + ".") + "</h1>" +
      '<p class="pcl-lead">' + (ps.length ? "Estas são as pastas que " + esc(eu.escritorio || "o escritório") + " compartilhou com você." : esc(eu.escritorio || "")) + "</p></header>" +
      '<div class="pcl-duas"><section class="pcl-painel">' + cab("Suas pastas", String(ps.length)) + linhas + "</section>" +
      '<section class="pcl-painel">' + cab("Precisa de você", pend.length ? String(pend.length) : null) + pendHtml + "</section></div></div>";
    r.querySelectorAll("[data-pcl-pasta]").forEach(function (b) { b.onclick = function () { abrirPasta(Number(b.dataset.pclPasta)); }; });
    ligarSair(r);
  }

  function ligarSair(r) {
    r.querySelectorAll("[data-pcl-sair]").forEach(function (b) {
      b.onclick = function () {
        api("/api/cliente/sair", { method: "POST", json: {} }).catch(function () { return null; }).then(function () {
          st.eu = null;
          st.csrf = "";
          telaDeEntrar("");
        });
      };
    });
  }

  function abrirPasta(id) {
    st.pastaId = id;
    return api("/api/cliente/pastas/" + id).then(function (v) {
      st.visao = v;
      desenharPastaDoCliente();
      iniciarRelogio();
    }).catch(function (err) {
      if (err.message !== "sessao") raiz().innerHTML = '<div class="pcl-entrada"><p class="pcl-erro">' + esc(err.message) + "</p></div>";
    });
  }

  function desenharPastaDoCliente() {
    var r = raiz();
    var conversaAntes = document.getElementById("pcl-conversa");
    var noFim = !conversaAntes || conversaAntes.scrollTop + conversaAntes.clientHeight >= conversaAntes.scrollHeight - 30;
    var rascunho = (r.querySelector("[data-pcl-escrever] textarea") || {}).value || "";
    var rolagem = window.scrollY;
    var sid = st.pastaId;
    r.innerHTML = htmlDaPasta(st.visao, {
      previa: false, voltar: st.eu && st.eu.pastas.length > 1,
      urlAgenda: function (cid) { return "/api/cliente/pastas/" + sid + "/compromissos/" + cid + "/agenda"; },
    });
    window.scrollTo(0, rolagem);
    var conversa = document.getElementById("pcl-conversa");
    if (conversa && noFim) conversa.scrollTop = conversa.scrollHeight;
    var caixa = r.querySelector("[data-pcl-escrever] textarea");
    if (caixa && rascunho) caixa.value = rascunho;
    ligarPasta(r, sid);
  }

  function ligarPasta(r, sid) {
    ligarSair(r);
    var voltar = r.querySelector("[data-pcl-voltar]");
    if (voltar) voltar.onclick = function () { carregarEu().then(telaDasPastas); };
    r.querySelectorAll("[data-pcl-doc]").forEach(function (b) {
      b.onclick = function () {
        var doc = st.visao.documentos.find(function (d) { return d.sha1 === b.dataset.pclDoc; });
        abrirDocumento(r, doc, function (sha1, n) { return "/api/cliente/pastas/" + sid + "/documentos/" + sha1 + "/pagina?n=" + n; },
          "/api/cliente/pastas/" + sid + "/documentos/" + doc.sha1 + "/baixar", sid);
      };
    });
    r.querySelectorAll("[data-pcl-feita]").forEach(function (b) {
      b.onclick = function () {
        b.disabled = true;
        api("/api/cliente/pastas/" + sid + "/etapas/" + b.dataset.pclFeita + "/feita", { method: "POST", json: {} }).then(function (v) {
          st.visao = v;
          desenharPastaDoCliente();
        }).catch(function (err) { b.disabled = false; avisar(err.message); });
      };
    });
    var arquivo = r.querySelector("#pcl-arquivo");
    r.querySelectorAll("[data-pcl-enviar]").forEach(function (b) {
      b.onclick = function () { st.etapa = b.dataset.pclEnviar; arquivo.click(); };
    });
    var anexar = r.querySelector("[data-pcl-anexar]");
    if (anexar) anexar.onclick = function () { st.etapa = ""; arquivo.click(); };
    arquivo.onchange = function () {
      var f = arquivo.files && arquivo.files[0];
      arquivo.value = "";
      if (f) enviarArquivo(sid, f, st.etapa);
    };
    r.querySelectorAll("[data-pcl-confirmar]").forEach(function (b) {
      b.onclick = function () { responder(sid, b.dataset.pclConfirmar, "confirmado", "", b); };
    });
    r.querySelectorAll("[data-pcl-remarcar]").forEach(function (b) {
      b.onclick = function () {
        var form = r.querySelector('[data-pcl-remarcar-form="' + b.dataset.pclRemarcar + '"]');
        form.hidden = false;
        montarCalRemarcar(form);
      };
    });
    r.querySelectorAll("[data-pcl-remarcar-fechar]").forEach(function (b) {
      b.onclick = function () { r.querySelector('[data-pcl-remarcar-form="' + b.dataset.pclRemarcarFechar + '"]').hidden = true; };
    });
    r.querySelectorAll("[data-pcl-remarcar-form]").forEach(function (form) {
      form.onsubmit = function (e) {
        e.preventDefault();
        if (!form.dataset.dia) { var aviso = form.querySelector("[data-pcl-escolha]"); if (aviso) { aviso.textContent = "Escolha um dia no calendário para mandar."; aviso.classList.add("falta"); } return; }
        var d = form.dataset.dia.split("-"), obs = form.querySelector("input").value.trim(), per = form.dataset.periodo || "Qualquer horário";
        var texto = d[2] + "/" + d[1] + "/" + d[0] + " · " + per.toLowerCase() + (obs ? " · " + obs : "");
        responder(sid, form.dataset.pclRemarcarForm, "remarcar", texto, form.querySelector('button[type="submit"]'));
      };
    });
    var escrever = r.querySelector("[data-pcl-escrever]");
    if (escrever) {
      var caixa = escrever.querySelector("textarea");
      caixa.oninput = function () {
        caixa.style.height = "auto";
        caixa.style.height = Math.min(caixa.scrollHeight, 160) + "px";
      };
      caixa.onkeydown = function (e) {
        if (e.key === "Enter" && (e.ctrlKey || e.metaKey)) { e.preventDefault(); escrever.requestSubmit(); }
      };
      escrever.onsubmit = function (e) {
        e.preventDefault();
        var texto = caixa.value.trim();
        if (!texto) return;
        var botao = escrever.querySelector('button[type="submit"]');
        botao.disabled = true;
        api("/api/cliente/pastas/" + sid + "/mensagens", { method: "POST", json: { texto: texto } }).then(function (d) {
          caixa.value = "";
          st.visao.mensagens = d.mensagens;
          desenharPastaDoCliente();
          var c = document.getElementById("pcl-conversa");
          if (c) c.scrollTop = c.scrollHeight;
        }).catch(function (err) { botao.disabled = false; avisar(err.message); });
      };
    }
  }

  function responder(sid, cid, resposta, sugestao, botao) {
    if (botao) botao.disabled = true;
    api("/api/cliente/pastas/" + sid + "/compromissos/" + cid + "/responder", { method: "POST", json: { resposta: resposta, sugestao: sugestao } }).then(function (v) {
      st.visao = v;
      desenharPastaDoCliente();
      avisar(resposta === "confirmado" ? "Horário confirmado. O escritório já sabe." : "Pedido mandado. O escritório vai responder por aqui.", true);
    }).catch(function (err) {
      if (botao) botao.disabled = false;
      avisar(err.message);
    });
  }

  function enviarArquivo(sid, arquivo, etapa) {
    if (st.enviando) return;
    if (arquivo.size > 25 * 1024 * 1024) { avisar("O arquivo passa de 25 MB. Mande um menor, ou fale com o escritório."); return; }
    st.enviando = true;
    avisar("Enviando " + arquivo.name + "…", true, 0);
    var url = "/api/cliente/pastas/" + sid + "/enviar?nome=" + encodeURIComponent(arquivo.name) + (etapa !== "" ? "&etapa=" + encodeURIComponent(etapa) : "");
    api(url, { method: "POST", body: arquivo, headers: { "content-type": "application/octet-stream" } }).then(function (d) {
      st.enviando = false;
      st.visao = d.visao;
      desenharPastaDoCliente();
      avisar(d.nome + " chegou ao escritório.", true);
    }).catch(function (err) {
      st.enviando = false;
      if (err.message !== "sessao") avisar(err.message);
    });
  }

  /* Um aviso no pe da tela, que some sozinho. */
  function avisar(texto, ok, dura) {
    var velho = document.querySelector(".pcl-pagina .pcl-toast");
    if (velho) velho.remove();
    var el = document.createElement("p");
    el.className = "pcl-toast" + (ok ? " ok" : "");
    el.setAttribute("role", "status");
    el.textContent = texto;
    raiz().appendChild(el);
    if (dura !== 0) setTimeout(function () { el.remove(); }, dura || 6000);
  }

  /* A pasta se atualiza sozinha a cada 30 s com a pagina a vista: a resposta
     do escritorio aparece sem recarregar. */
  function iniciarRelogio() {
    pararRelogio();
    st.relogio = setInterval(function () {
      if (document.hidden || !st.pastaId || document.querySelector(".pcl-visor") || st.enviando) return;
      var digitando = document.activeElement && /^(TEXTAREA|INPUT)$/.test(document.activeElement.tagName);
      api("/api/cliente/pastas/" + st.pastaId).then(function (v) {
        var mudou = JSON.stringify(v) !== JSON.stringify(st.visao);
        st.visao = v;
        if (mudou && !digitando) desenharPastaDoCliente();
      }).catch(function () { return null; });
    }, 30000);
  }

  function pararRelogio() {
    if (st.relogio) clearInterval(st.relogio);
    st.relogio = null;
  }

  // A barra do site (a .topo de site/assets): PAVLVS, o Sair quando ha sessao e o tema. Fica fora do #pcl-raiz,
  // que e redesenhado a cada tela; o Sair de cada tela muda para ca.
  function montarBarra() {
    if (document.getElementById("pcl-barra-site")) return;
    var r = raiz(); if (!r || !r.parentNode) return;
    var b = document.createElement("header");
    b.id = "pcl-barra-site"; b.className = "pcl-pagina pcl-barra-site";
    b.innerHTML = '<div class="pcl-barra-dentro"><span class="pcl-marca">PAVLVS</span><span class="pcl-espaco"></span>' +
      '<span class="pcl-barra-acoes" id="pcl-barra-acoes"></span>' +
      '<button type="button" class="pcl-btn-icone" id="pcl-tema-btn" aria-label="Alternar tema" title="Alternar tema"></button></div>';
    r.parentNode.insertBefore(b, r);
    var bt = document.getElementById("pcl-tema-btn");
    var icone = function () { bt.innerHTML = ic(document.documentElement.dataset.tema === "claro" ? "dark_mode" : "light_mode"); };
    bt.onclick = function () {
      var novo = document.documentElement.dataset.tema === "claro" ? "escuro" : "claro";
      document.documentElement.dataset.tema = novo;
      try { localStorage.setItem("pcl-tema", novo); } catch (e) { /* sem guardar */ }
      icone();
    };
    icone();
    new MutationObserver(icone).observe(document.documentElement, { attributes: true, attributeFilter: ["data-tema"] });
    var mover = function () {
      var slot = document.getElementById("pcl-barra-acoes"), s = r.querySelector(".pcl-topo [data-pcl-sair]");
      if (!slot) return;
      slot.innerHTML = ""; if (s) slot.appendChild(s);
      r.querySelectorAll(".pcl-topo").forEach(function (t) { if (!t.querySelector("button, a")) t.remove(); });
    };
    new MutationObserver(mover).observe(r, { childList: true });
    mover();
  }

  function iniciar() {
    // O claro ou o escuro do aparelho do cliente (css/cliente.css le o data-tema).
    // O escuro (o do site) e o padrao; o claro so quando o aparelho pede.
    var claro = window.matchMedia ? window.matchMedia("(prefers-color-scheme: light)") : null;
    var salvo = null; try { salvo = localStorage.getItem("pcl-tema"); } catch (e) { /* nada */ }
    var tema = function () { document.documentElement.dataset.tema = salvo || (claro && claro.matches ? "claro" : "escuro"); };
    tema();
    montarBarra();
    if (claro && claro.addEventListener) claro.addEventListener("change", tema);
    var m = /^\/cliente\/([^/]+)$/.exec(location.pathname);
    st.token = m ? decodeURIComponent(m[1]) : "";
    // "Imprimir" pelo navegador fica registrado - o print de tela, nao (o
    // navegador nao fica sabendo; a marca d'agua e que diz de onde saiu).
    window.addEventListener("beforeprint", function () {
      if (!st.eu) return;
      api("/api/cliente/evento", { method: "POST", json: { tipo: "imprimiu", servico_id: st.pastaId, alvo: st.docAberto ? st.docAberto.nome : "a pasta" } })
        .catch(function () { return null; });
    });
    if (!st.token || st.token === "previa") {
      raiz().innerHTML = '<div class="pcl-entrada"><h1>Área do cliente</h1><p>Abra pelo link que o escritório mandou para você.</p></div>';
      return;
    }
    carregarEu();
  }

  return { iniciar: iniciar, previa: previa, htmlDaPasta: htmlDaPasta };
})();

if (document.body && document.body.classList.contains("pcl-corpo")) window.AreaCliente.iniciar();
