/* ------------------------------------------------------- area do cliente */
/*
   A Area do cliente (docs/PLANO-AREA-CLIENTE.md, src/area_cliente.py): a
   pagina que o cliente abre pelo link do escritorio (frontend/cliente.html) e
   a previa "Ver como o cliente", dentro do PAULUS (js/94-area-cliente.js).
   As duas desenham pela mesma funcao e a mesma resposta da API - o advogado
   ve o que o cliente ve, e nao uma imitacao.

   Tudo mora dentro de window.AreaCliente: este arquivo entra tambem no
   index.html do PAULUS, e nenhum nome daqui pode esbarrar num de la.

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
        '<form class="pcl-remarcar" data-pcl-remarcar-form="' + p.id + '" hidden><div class="pcl-campo"><label for="pcl-sug-' + p.id + '">Que dia e horário ficam melhor?</label>' +
        '<input id="pcl-sug-' + p.id + '" type="text" maxlength="300" placeholder="Ex.: quinta à tarde, depois das 15h" autocomplete="off"></div>' +
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
      (v.responsavel ? '<p class="pcl-sub">Quem cuida: ' + esc(v.responsavel) + "</p>" : "") +
      '<div class="pcl-situacao"><span class="' + classeDoStatus(p.status) + '">' + esc(p.status_rotulo) + "</span>" +
      (v.andamento.length ? '<span class="pcl-barra" role="progressbar" aria-valuemin="0" aria-valuemax="100" aria-valuenow="' + p.progresso + '"><i style="width:' + p.progresso + '%"></i></span>' +
        '<span class="pcl-pct">' + p.progresso + "%</span>" : "") + "</div></header>";

    var partes = [topo, cabeca];
    if (v.pendencias.length) {
      partes.push('<div class="pcl-pendencias">' + secao("Para você", plural(v.pendencias.length, "pendência", "pendências"),
        '<div class="pcl-cartao">' + v.pendencias.map(function (x) { return pendencia(x, ctx); }).join("") + "</div>") + "</div>");
    }
    if (v.resumo && v.resumo.texto) {
      partes.push(secao("Resumo", v.resumo.em ? "escrito em " + dataCurta(v.resumo.em) : "", '<div class="pcl-cartao"><p class="pcl-texto">' + esc(v.resumo.texto) + "</p></div>"));
    }
    partes.push(secao("Próximas datas", "", '<div class="pcl-cartao">' +
      (v.datas.length ? v.datas.map(function (d) { return linhaDeData(d, ctx); }).join("") : '<p class="pcl-vazio">Nenhuma data marcada por enquanto.</p>') + "</div>"));
    partes.push(secao("Andamento", v.andamento.length ? v.andamento.filter(function (e) { return e.feita; }).length + " de " + v.andamento.length : "",
      '<div class="pcl-cartao">' + (v.andamento.length ? v.andamento.map(linhaDeEtapa).join("") : '<p class="pcl-vazio">O escritório ainda não registrou as etapas.</p>') + "</div>"));
    partes.push(secao("Documentos", "", '<div class="pcl-cartao">' +
      (v.documentos.length ? v.documentos.map(linhaDeDocumento).join("") : '<p class="pcl-vazio">Nenhum documento compartilhado ainda.</p>') + "</div>"));
    var conversa = '<div class="pcl-cartao"><div class="pcl-conversa" id="pcl-conversa">' +
      (v.mensagens.length ? v.mensagens.map(mensagem).join("") : '<p class="pcl-vazio">Escreva ao escritório por aqui. Quando responderem, você recebe um e-mail.</p>') + "</div>" +
      '<form class="pcl-escrever" data-pcl-escrever="1">' +
      '<button type="button" class="pcl-icone-botao" data-pcl-anexar="1" title="Mandar um arquivo" aria-label="Mandar um arquivo"' + desabilitado(ctx) + ">" + ic("attach_file") + "</button>" +
      '<textarea rows="1" maxlength="4000" placeholder="Escreva ao escritório…" aria-label="Mensagem ao escritório"' + (ctx.previa ? " disabled" : "") + "></textarea>" +
      '<button type="submit" class="pcl-icone-botao primario" title="Mandar" aria-label="Mandar"' + desabilitado(ctx) + ">" + ic("send") + "</button></form></div>";
    partes.push(secao("Conversa com o escritório", "", conversa));
    partes.push('<p class="pcl-aviso-registro">' + ic("visibility") + "<span>O escritório vê quando você entra, abre, baixa ou imprime um documento. Cada página aberta leva o seu nome e a hora.</span></p>");
    var faixa = ctx.previa ? '<p class="pcl-previa-faixa">Prévia: é assim que ' + esc(ctx.nomeDoCliente || "o cliente") + " vê esta pasta. Os botões funcionam só para ele.</p>" : "";
    return faixa + '<div class="pcl-coluna">' + partes.join("") + "</div>" +
      '<input type="file" id="pcl-arquivo" hidden accept=".pdf,.jpg,.jpeg,.png,.docx,.xlsx,.txt">';
  }

  /* -------------------------------------------- o documento aberto */

  function abrirDocumento(raiz, doc, urlPagina, urlBaixar, servicoId) {
    var visor = document.createElement("div");
    visor.className = "pcl-visor";
    visor.setAttribute("role", "dialog");
    visor.setAttribute("aria-label", doc.nome);
    var pdf = /\.pdf$/i.test(doc.nome);
    visor.innerHTML = '<div class="pcl-visor-topo"><button type="button" class="pcl-botao-leve" data-pcl-fechar="1" aria-label="Fechar">' + ic("close") + "</button>" +
      "<b>" + esc(doc.nome) + "</b>" +
      (urlBaixar ? '<a class="pcl-botao-leve" href="' + esc(urlBaixar) + '" data-pcl-baixar="1">' + ic("download") + "Baixar</a>" : "") + "</div>" +
      '<div class="pcl-visor-pagina"><img alt="Página do documento"></div>' +
      '<div class="pcl-visor-pe"><button type="button" class="pcl-botao-leve" data-pcl-ant="1" aria-label="Página anterior">' + ic("chevron_left") + "</button>" +
      '<span data-pcl-num="1">…</span><button type="button" class="pcl-botao-leve" data-pcl-prox="1" aria-label="Próxima página">' + ic("chevron_right") + "</button></div>" +
      '<div class="pcl-visor-pe"><small>' + (pdf || !urlBaixar ? "Cada página leva o nome de quem abriu e a hora." :
        "Cada página aqui leva o nome de quem abriu e a hora. O arquivo baixado vai no formato original, sem a marca.") + "</small></div>";
    raiz.appendChild(visor);
    var img = visor.querySelector("img");
    var num = visor.querySelector("[data-pcl-num]");
    var atual = 1;
    var total = 1;
    var urlVelha = "";
    function mostrar(n) {
      num.textContent = "carregando…";
      fetch(urlPagina(doc.sha1, n), { credentials: "same-origin" }).then(function (r) {
        if (!r.ok) throw new Error(r.status === 401 ? "sessao" : "erro");
        total = Number(r.headers.get("x-paginas") || 1) || 1;
        return r.blob();
      }).then(function (b) {
        if (urlVelha) URL.revokeObjectURL(urlVelha);
        urlVelha = URL.createObjectURL(b);
        img.src = urlVelha;
        atual = n;
        num.textContent = n + " de " + total;
      }).catch(function (e) {
        num.textContent = e.message === "sessao" ? "a sessão acabou — entre de novo" : "não consegui abrir esta página";
      });
    }
    function fechar() {
      if (urlVelha) URL.revokeObjectURL(urlVelha);
      document.removeEventListener("keydown", teclas);
      visor.remove();
      st.docAberto = null;
    }
    function teclas(e) {
      if (e.key === "Escape") fechar();
      else if (e.key === "ArrowRight" && atual < total) mostrar(atual + 1);
      else if (e.key === "ArrowLeft" && atual > 1) mostrar(atual - 1);
    }
    visor.querySelector("[data-pcl-fechar]").onclick = fechar;
    visor.querySelector("[data-pcl-ant]").onclick = function () { if (atual > 1) mostrar(atual - 1); };
    visor.querySelector("[data-pcl-prox]").onclick = function () { if (atual < total) mostrar(atual + 1); };
    document.addEventListener("keydown", teclas);
    st.docAberto = { nome: doc.nome, servico: servicoId };
    mostrar(1);
  }

  /* ------------------------------------------------- a previa (PAULUS) */

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
    campo.focus();
    form.onsubmit = function (e) {
      e.preventDefault();
      var botao = form.querySelector("button");
      var erro = form.querySelector("[data-pcl-erro]");
      botao.disabled = true;
      botao.textContent = "mandando…";
      api("/api/cliente/entrar", { method: "POST", json: { token: st.token, email: campo.value.trim() } }).then(function (d) {
        telaDoCodigo(campo.value.trim(), d.para);
      }).catch(function (err) {
        botao.disabled = false;
        botao.textContent = "Mandar o código";
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
    campo.focus();
    campo.oninput = function () {
      campo.value = campo.value.replace(/\D/g, "").slice(0, 6);
      if (campo.value.length === 6) form.requestSubmit ? form.requestSubmit() : form.onsubmit(new Event("submit"));
    };
    form.onsubmit = function (e) {
      e.preventDefault();
      var botao = form.querySelector('button[type="submit"]');
      botao.disabled = true;
      api("/api/cliente/codigo", { method: "POST", json: { token: st.token, codigo: campo.value, lembrar: r.querySelector("#pcl-lembrar").checked } }).then(function (d) {
        st.csrf = d.csrf;
        return carregarEu();
      }).catch(function (err) {
        botao.disabled = false;
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

  function telaDasPastas() {
    pararRelogio();
    st.pastaId = null;
    var eu = st.eu;
    var r = raiz();
    var lista = eu.pastas.length
      ? '<div class="pcl-pastas">' + eu.pastas.map(function (p) {
        return '<button type="button" class="pcl-pasta-item" data-pcl-pasta="' + p.id + '">' + ic("folder") +
          "<span><b>" + esc(p.nome) + "</b><small>" + esc(p.status_rotulo) + "</small></span>" +
          (p.novas ? '<i class="pcl-bolinha" title="Mensagens novas">' + p.novas + "</i>" : "") + ic("chevron_right") + "</button>";
      }).join("") + "</div>"
      : '<p class="pcl-vazio">Nenhuma pasta compartilhada com você agora. Se acha que é engano, fale com o escritório.</p>';
    r.innerHTML = '<div class="pcl-coluna"><div class="pcl-topo"><span class="pcl-marca">PAVLVS</span><span class="pcl-espaco"></span>' +
      '<button type="button" class="pcl-botao-leve" data-pcl-sair="1">' + ic("logout") + "Sair</button></div>" +
      '<header class="pcl-cabeca"><span class="pcl-kicker">' + esc(eu.escritorio || "Seu escritório") + "</span><h1>Olá, " + esc(eu.pessoa.nome.split(" ")[0]) + "</h1>" +
      '<p class="pcl-sub">' + (eu.pastas.length ? "Estas são as pastas que o escritório compartilhou com você." : "") + "</p></header>" + lista + "</div>";
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
        form.querySelector("input").focus();
      };
    });
    r.querySelectorAll("[data-pcl-remarcar-fechar]").forEach(function (b) {
      b.onclick = function () { r.querySelector('[data-pcl-remarcar-form="' + b.dataset.pclRemarcarFechar + '"]').hidden = true; };
    });
    r.querySelectorAll("[data-pcl-remarcar-form]").forEach(function (form) {
      form.onsubmit = function (e) {
        e.preventDefault();
        responder(sid, form.dataset.pclRemarcarForm, "remarcar", form.querySelector("input").value, form.querySelector("button"));
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

  function iniciar() {
    // O claro ou o escuro do aparelho do cliente (css/cliente.css le o data-tema).
    var escuro = window.matchMedia ? window.matchMedia("(prefers-color-scheme: dark)") : null;
    var tema = function () { document.documentElement.dataset.tema = escuro && escuro.matches ? "escuro" : "claro"; };
    tema();
    if (escuro && escuro.addEventListener) escuro.addEventListener("change", tema);
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
