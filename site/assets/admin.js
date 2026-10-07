/* PAVLVS - painel de administracao (paulus.ia.br/admin). Uma pagina so, sem
   build: a Entrada (Cloudflare Access + GitHub) e a casca com as 13 telas,
   navegadas por hash (#visao, #contas, ...). Tudo o que aparece vem de
   /api/admin/* (contrato em worker/admin-api.md); nada de dado inventado.
   O que muda o que esta no ar vai para a fila (POST /api/admin/alteracoes) e
   so acontece em "Commitar e pushar". Desenho: handoff "Painel Admin". */
(function () {
  "use strict";

  /* ================================================================ base */

  var $ = function (id) { return document.getElementById(id); };
  function esc(t) { return String(t == null ? "" : t).replace(/[&<>"']/g, function (c) { return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]; }); }
  function ic(nome, cls) { return '<span class="icon' + (cls ? " " + cls : "") + '" aria-hidden="true">' + nome + "</span>"; }
  function norm(t) { return String(t == null ? "" : t).toLowerCase().normalize("NFD").replace(/[̀-ͯ]/g, ""); }
  function pad(n) { return String(n).padStart(2, "0"); }
  function primeiro(nome) { return String(nome || "").trim().split(/\s+/)[0] || ""; }
  function num(v) { var n = Number(String(v == null ? "" : v).replace(/\./g, "").replace(",", ".")); return isFinite(n) ? n : 0; }
  function numDec(v) { var s = String(v == null ? "" : v).trim(); if (/,/.test(s)) s = s.replace(/\./g, "").replace(",", "."); var n = Number(s); return isFinite(n) ? n : 0; }

  /* ---------- formatos ---------- */
  function brl(v) { return "R$ " + Number(v || 0).toLocaleString("pt-BR", { minimumFractionDigits: 2, maximumFractionDigits: 2 }); }
  function usd(v) { return "US$ " + Number(v || 0).toLocaleString("pt-BR", { minimumFractionDigits: 2, maximumFractionDigits: 2 }); }
  function dec(x, c) { return Number(x).toLocaleString("pt-BR", { minimumFractionDigits: 0, maximumFractionDigits: c }); }
  function tok(n) {
    n = Number(n) || 0; var a = Math.abs(n);
    if (a >= 1e9) return dec(n / 1e9, 1) + " bi";
    if (a >= 1e6 || Math.round(a / 1e3) >= 1000) return dec(n / 1e6, 1) + "M";
    if (a >= 1e3) return Math.round(n / 1e3).toLocaleString("pt-BR") + " mil";
    return String(Math.round(n));
  }
  function cambioTxt(c) { return Number(c || 0).toLocaleString("pt-BR", { minimumFractionDigits: 2, maximumFractionDigits: 2 }); }
  function pct(x) { return Math.round(x * 100) + "%"; }
  function taxa(v) { v = Number(v) || 0; return Math.round(v > 1 ? v : v * 100) + "%"; }
  function dt(iso) { if (!iso) return null; var d; if (/^\d{4}-\d{2}-\d{2}$/.test(iso)) { var p = iso.split("-"); d = new Date(+p[0], +p[1] - 1, +p[2]); } else d = new Date(iso); return isNaN(d) ? null : d; }
  function diasAte(d) { var h = new Date(); var a = new Date(h.getFullYear(), h.getMonth(), h.getDate()); var b = new Date(d.getFullYear(), d.getMonth(), d.getDate()); return Math.round((a - b) / 864e5); }
  function rel(iso) {
    var d = dt(iso); if (!d) return "nunca";
    var n = diasAte(d);
    if (n <= 0) return "hoje"; if (n === 1) return "ontem"; if (n < 30) return "há " + n + " dias";
    if (n < 365) { var m = Math.round(n / 30); return "há " + m + (m === 1 ? " mês" : " meses"); }
    return "há mais de 1 ano";
  }
  function hm(d) { return pad(d.getHours()) + ":" + pad(d.getMinutes()); }
  function ddmm(iso) { var d = dt(iso); return d ? pad(d.getDate()) + "/" + pad(d.getMonth() + 1) : "—"; }
  function ddmmaaaa(iso) { var d = dt(iso); return d ? ddmm(iso) + "/" + d.getFullYear() : "—"; }
  function quando(iso) {
    var d = dt(iso); if (!d) return "—";
    var n = diasAte(d);
    if (n === 0) return "hoje " + hm(d); if (n === 1) return "ontem " + hm(d);
    return ddmm(iso) + " " + hm(d);
  }
  function quandoCurto(iso) { var d = dt(iso); if (!d) return "—"; return diasAte(d) === 0 ? hm(d) : ddmm(iso); }
  function hojeLongo() {
    var s = new Date().toLocaleDateString("pt-BR", { weekday: "long", day: "numeric", month: "long", year: "numeric" });
    return s.replace("-feira", "");
  }
  function saudacaoHora() { var h = new Date().getHours(); return h >= 5 && h < 12 ? "Bom dia" : h >= 12 && h < 18 ? "Boa tarde" : "Boa noite"; }

  /* ================================================================ estado */

  var TELAS = [
    { id: "visao", label: "Visão geral", icon: "dashboard", chip: "Visão geral", o: "a visão geral", ler: ["visao"] },
    { id: "contas", label: "Contas e cadastros", icon: "contacts", chip: "Contas", o: "as contas", ler: ["contas"], grupo: "Clientes" },
    { id: "google", label: "Permissões Google", icon: "shield", chip: "Permissões Google", o: "as contas com Google", ler: ["contas"] },
    { id: "tuneis", label: "Túneis Cloudflare", icon: "dns", chip: "Túneis", o: "os túneis", ler: ["tuneis"] },
    { id: "renovacoes", label: "Não renovações", icon: "notifications", chip: "Não renovações", o: "as não renovações", ler: ["renovacoes"] },
    { id: "tokens", label: "Tokens e custos", icon: "token", chip: "Tokens", o: "os tokens e custos", ler: [], grupo: "Dinheiro" },
    { id: "planos", label: "Planos", icon: "payments", chip: "Planos", o: "os planos", ler: ["planos", "tokens:geral:mes"] },
    { id: "nfse", label: "Notas fiscais", icon: "receipt_long", chip: "Notas fiscais", o: "as notas fiscais", ler: ["nfse"] },
    { id: "emails", label: "Disparo de e-mails", icon: "mail", chip: "E-mails", o: "as campanhas", ler: ["campanhas"], grupo: "Comunicação" },
    { id: "equipe", label: "Equipe", icon: "group", chip: "Equipe", o: "a equipe", ler: ["equipe"], grupo: "Painel" },
    { id: "alteracoes", label: "Confirmar alterações", icon: "publish", chip: "Alterações", o: "as alterações", ler: ["alteracoes"] },
  ];
  var TELA = {}; TELAS.forEach(function (t) { TELA[t.id] = t; });

  // O papel que pode cada tipo da fila (a tabela do contrato).
  var DF = ["dono", "financeiro"], DS = ["dono", "suporte"];
  var PAPEIS = { "retroagir": ["dono"],
    "conta.creditar": DF, "conta.instalacao.apagar": DS, "conta.cancelar": DF, "conta.reembolsar": DF, "google.servicos": DS, "google.desvincular": DS,
    "tunel.apagar": DS, "tunel.endereco": DS, "tunel.ativo": DS, "plano.editar": DF,
    "plano.criar": DF, "nfse.config": DF, "equipe.papel": ["dono"],
  };
  var PAPEL_NOME = { dono: "Dono", financeiro: "Financeiro", suporte: "Suporte" };

  var E = {
    sessao: null, dentro: false, tela: "visao", pendentes: [], gaveta: null, modal: null,
    busca: { aberta: false, q: "", idx: 0, res: null, erro: "", carregando: false, seq: 0 },
    erroVolta: "",
  };
  var D = {}; // cache das leituras: D[chave] = {dados, erro, carregando}
  var U = {   // o estado de tela de cada aba
    contas: { filtro: "todas", agrupar: "conta", q: "" },
    google: { confirmando: null, sel: null },
    tuneis: { filtro: "todos", sel: {}, aberto: null, selecionando: false, reg: "todos", regTodos: false },
    renovacoes: { sel: null, aberto: null, msg: {}, oferta: {} },
    emails: { aba: "campanhas", passo: 1, so: null, camp: novaCamp() },
    tokens: { visao: "geral", periodo: "mes", sel: null },
    planos: { novo: { nome: "", id: "", valor: "", anual: "", tokens: "" } },
    materiais: { filtro: "fila", aberto: null, checks: {}, recados: {} },
    nfse: { aba: "notas", teste: null, testando: false, pfx: null, senha: "", instalando: false, aviso: null },
  };
  function novaCamp() { return { publico: "", nome: "", assunto: "", pre: "", titulo: "", texto: "", botao: "Abrir o Paulus", link: "https://paulus.ia.br/", quando: "agora" }; }

  function pode(tipo) { var p = PAPEIS[tipo]; return !p || (E.sessao && p.indexOf(E.sessao.papel) >= 0); }
  function cfg(nome) { var c = E.sessao && E.sessao.config && E.sessao.config[nome]; return c || { ligado: true, falta: "" }; }
  function desligado(c) { return !!(c && c.ligado === false); }
  function naFila(tipo, alvo) { return E.pendentes.some(function (p) { return p.tipo === tipo && String(p.alvo) === String(alvo); }); }
  function ultimaNaFila(tipo, alvo) { var r = null; E.pendentes.forEach(function (p) { if (p.tipo === tipo && (alvo == null || String(p.alvo) === String(alvo))) r = p; }); return r; }

  /* ================================================================ API */

  var voltando = false;
  async function api(metodo, caminho, corpo) {
    var op = { method: metodo, headers: { Accept: "application/json" }, credentials: "same-origin" };
    if (corpo !== undefined) { op.headers["Content-Type"] = "application/json"; op.body = JSON.stringify(corpo); }
    var r;
    try { r = await fetch(caminho, op); } catch (e) { var er = new Error("sem conexão com o servidor"); er.status = 0; throw er; }
    var dados = {};
    try { dados = await r.json(); } catch (e) { dados = {}; }
    if (r.status === 401 && caminho !== "/api/admin/sessao") voltarEntrada();
    if (!r.ok) { var e2 = new Error(dados.erro || "o servidor respondeu " + r.status); e2.status = r.status; e2.dados = dados; throw e2; }
    return dados;
  }

  function caminhoDe(ch) {
    if (ch.indexOf("tokens:") === 0) { var p = ch.split(":"); return "/api/admin/tokens?visao=" + p[1] + "&periodo=" + (p[2] === "custom" ? "custom&de=" + p[3] + "&ate=" + p[4] : p[2]); }
    return "/api/admin/" + ch;
  }
  function ler(ch) {
    var r = D[ch] || (D[ch] = {});
    if (r.promessa) return r.promessa;
    r.carregando = true;
    r.promessa = api("GET", caminhoDe(ch)).then(function (d) {
      r.dados = d; r.erro = null;
      if (ch === "alteracoes") E.pendentes = d.pendentes || [];
    }, function (e) { if (e.status !== 401) r.erro = e.message; }).then(function () {
      r.carregando = false; r.promessa = null;
      if (E.dentro) render();
    });
    return r.promessa;
  }
  function dadosDe(ch) { return D[ch] && D[ch].dados; }
  function tokensChave() { return "tokens:" + U.tokens.visao + ":" + U.tokens.periodo + (U.tokens.periodo === "custom" ? ":" + U.tokens.de + ":" + U.tokens.ate : ""); }
  function leiturasDa(t) { return t === "tokens" ? [tokensChave()] : TELA[t].ler; }

  // Mostra a linha de erro ou de carregando; devolve "" quando os dados estao prontos.
  function estadoLeitura(chaves, t) {
    for (var i = 0; i < chaves.length; i++) {
      var r = D[chaves[i]];
      if (r && r.erro && !r.dados) return '<p class="erro-linha">' + ic("warning") + "<span>Não consegui ler " + esc(TELA[t].o) + " agora: " + esc(r.erro) + "</span></p>";
    }
    for (var j = 0; j < chaves.length; j++) { var q = D[chaves[j]]; if (!q || !q.dados) return '<p class="carregando">Carregando…</p>'; }
    return "";
  }
  function erroRecente(ch, t) {
    var r = D[ch];
    return r && r.erro && r.dados ? '<p class="erro-linha">' + ic("warning") + "<span>Não consegui atualizar " + esc(TELA[t].o) + " agora: " + esc(r.erro) + ". Mostrando a última leitura.</span></p>" : "";
  }

  /* ---------- a fila ---------- */
  async function enfileirar(tela, tipo, alvo, dados, texto, quieto) {
    try {
      var r = await api("POST", "/api/admin/alteracoes", { tela: tela, tipo: tipo, alvo: String(alvo), dados: dados, texto: texto });
      if (r.pendentes) E.pendentes = r.pendentes;
      if (D.alteracoes && D.alteracoes.dados) D.alteracoes.dados.pendentes = E.pendentes;
      if (!quieto) toastFila();
      render();
      return true;
    } catch (e) {
      if (e.status !== 401) toast(e.message, true);
      return false;
    }
  }
  function toastFila() { toast('Na fila de alterações · <a href="#alteracoes">Confirmar alterações</a>', false, true); }

  // As acoes "na hora": 503 com erro vira o toast de erro, nunca um sucesso fingido.
  async function naHora(metodo, caminho, corpo, ok) {
    try { var r = await api(metodo, caminho, corpo); if (ok) toast(ok); return r || {}; }
    catch (e) { if (e.status !== 401) toast(e.message, true); return null; }
  }

  /* ================================================================ desenho */

  // Troca o HTML e devolve o foco (e o cursor) ao campo que estava em uso.
  function pintar(el, html) {
    var a = document.activeElement, id = a && a.id && el.contains(a) ? a.id : null, s = null, f = null;
    if (id && (a.tagName === "INPUT" || a.tagName === "TEXTAREA")) { try { s = a.selectionStart; f = a.selectionEnd; } catch (x) { s = null; } }
    el.innerHTML = html;
    if (id) {
      var n = document.getElementById(id);
      if (n && el.contains(n)) { n.focus({ preventScroll: true }); if (s != null) { try { n.setSelectionRange(s, f); } catch (x) { /* nada */ } } }
    }
  }

  function render() {
    if (!E.dentro) return;
    renderNav();
    renderTela();
    renderCamada();
  }

  function contagens() {
    var c = {};
    var t = dadosDe("tuneis"); if (t) c.tuneis = (t.tuneis || []).filter(function (x) { return x.estado === "inactive" || x.estado === "down"; }).length;
    var r = dadosDe("renovacoes"); if (r) c.renovacoes = (r.abertas || []).length;
    var n = dadosDe("nfse"); if (n) c.nfse = (n.pagamentos || []).length + (n.notas || []).filter(function (x) { return x.estado === "rejeitada" || x.estado === "na_fila" || x.estado === "aguardando_confirmacao"; }).length;
    c.alteracoes = E.pendentes.length;
    return c;
  }

  function renderNav() {
    var c = contagens();
    var h = TELAS.map(function (t) {
      var b = c[t.id] || 0;
      return (t.grupo ? '<span class="adm-t-risco"></span>' : "") + '<a class="nav-item" href="#' + t.id + '"' + (E.tela === t.id ? ' aria-current="page"' : "") + ">" + ic(t.icon) + '<span class="rot">' + esc(t.label) + "</span>" +
        (b > 0 ? '<span class="badge' + (t.id === "alteracoes" ? " pend" : "") + '" aria-label="' + b + (t.id === "alteracoes" ? " pendentes" : " para ver") + '">' + b + "</span>" : "") + "</a>";
    }).join("");
    pintar($("nav-lateral"), h);
    pintar($("nav-celular"), h + '<button type="button" class="nav-item" data-a="sair">Sair</button>');
    // Na faixa do celular, a pilula da tela atual fica a vista.
    if (navRolada !== E.tela) {
      navRolada = E.tela;
      var pai = $("nav-celular"), atual = pai.querySelector('[aria-current="page"]');
      if (atual) pai.scrollLeft = Math.max(0, atual.offsetLeft - 12);
    }
  }
  var navRolada = null;

  function renderTela() {
    var f = TELAS_RENDER[E.tela];
    var col = $("tela");
    col.className = "adm-col" + (E.tela === "visao" ? " larga" : "");
    pintar(col, f());
  }

  function cab(titulo, lead) { return '<div class="cab-tela"><h1>' + esc(titulo) + "</h1>" + (lead ? '<p class="lead">' + lead + "</p>" : "") + "</div>"; }
  function falta(c) { return c && c.ligado === false ? '<p class="aviso-falta">' + ic("warning") + "<span>" + esc(c.falta || "não configurado") + "</span></p>" : ""; }
  function seg(nome, opcoes, ativo, cls, travado) {
    return '<div class="segmentos' + (cls ? " " + cls : "") + '"><div role="group">' + opcoes.map(function (o) {
      return '<button type="button" data-a="seg" data-seg="' + esc(nome) + '" data-v="' + esc(o[0]) + '" aria-pressed="' + (o[0] === ativo) + '"' + (travado ? " disabled" : "") + ">" + esc(o[1]) + "</button>";
    }).join("") + "</div></div>";
  }
  function sit(texto, cor) { return '<span class="sit" style="color:' + cor + '"><i></i><span class="corta">' + esc(texto) + "</span></span>"; }
  function sw(on) { return '<span class="switch' + (on ? " on" : "") + '" aria-hidden="true"><i></i></span>'; }
  function painelCab(rotulo, dir, dirCls) { return '<div class="painel-cab"><span class="rotulo">' + esc(rotulo) + "</span>" + (dir != null ? '<span class="cab-dir' + (dirCls ? " " + dirCls : "") + '">' + dir + "</span>" : "") + "</div>"; }
  function attrDis(cond, titulo) { return cond ? ' disabled title="' + esc(titulo || "") + '"' : ""; }
  function grade(cols, min, cabeca, linhas) {
    return '<div class="rolar"><div class="grade" style="--cols:' + cols + ";--min:" + (min || 0) + 'px">' +
      '<div class="grade-cab">' + cabeca + "</div>" + linhas + "</div></div>";
  }

  var SIT_CONTA = { ativa: ["ativa", "var(--ok)"], vencida: ["vencida", "var(--erro)"], cortesia: ["cortesia", "var(--ink2)"], pendente: ["pendente", "var(--atencao)"], cancelada: ["cancelada", "var(--ink3)"] };
  function sitConta(s) { return SIT_CONTA[s] || [s || "—", "var(--ink3)"]; }

  /* ================================================================ telas */

  var TELAS_RENDER = {};

  /* ---------- 1. Visao geral ---------- */
  TELAS_RENDER.visao = function () {
    var nome = primeiro(E.sessao.nome);
    var topo = '<div class="cab-tela"><h1>' + esc(saudacaoHora() + (nome ? ", " + nome : "") + ".") + "</h1>";
    var est = estadoLeitura(["visao"], "visao");
    if (est) return topo + '<span class="mono-linha">' + esc(hojeLongo()) + "</span></div>" + est;
    var v = dadosDe("visao"), k = v.kpi || {};
    var receita = Number(k.receita_mes) || 0, cambio = Number(k.cambio) || 0, custoU = Number(k.custo_usd_mes) || 0, custoR = custoU * cambio;
    var margem = receita > 0 ? 1 - custoR / receita : null;
    var h = topo + '<span class="mono-linha">' + esc(hojeLongo()) + " · " + (k.contas_ativas || 0) + " contas ativas em " + (k.escritorios || 0) + " escritórios</span></div>";
    h += erroRecente("visao", "visao");
    h += '<dl class="kpis">' +
      kpi("Arrecadado no mês", brl(receita), brl(k.receita_assinaturas) + " assinaturas · " + brl(k.receita_recargas) + " recargas Pix") +
      kpi("Custo de IA no mês", brl(custoR), "DeepInfra · " + usd(custoU) + " · câmbio " + cambioTxt(cambio)) +
      kpi("Margem", margem == null ? "—" : pct(margem), brl(receita - custoR) + " líquido", margem == null ? "" : margem >= 0 ? "var(--ok)" : "var(--erro)") +
      kpi("Tokens no mês", tok((k.entrada_mes || 0) + (k.saida_mes || 0)), tok(k.entrada_mes) + " entrada · " + tok(k.saida_mes) + " saída") + "</dl>";

    var pend = v.pendencias || [];
    var hp = '<div class="painel">' + painelCab("Precisa de você", pend.length + (pend.length === 1 ? " item" : " itens"), pend.length ? "c-erro" : "");
    var pendVer = visaoTodas ? pend : pend.slice(0, 3);
    hp += pend.length ? pendVer.map(function (p) {
      return '<button type="button" class="linha-btn" data-a="irTela" data-tela="' + esc(p.tela) + '" data-filtro="' + esc(p.filtro || "") + '">' + ic(p.icone || "arrow_forward") +
        '<span class="txt2"><b>' + esc(p.titulo) + "</b><small>" + esc(p.sub) + "</small></span>" + ic("arrow_forward") + "</button>";
    }).join("") : '<p class="vazio-linha">Nada precisa de você agora.</p>';
    if (pend.length > 3) hp += '<div class="ver-mais-linha"><button type="button" class="ver-mais" data-a="visaoVerMais">' + (visaoTodas ? "Ver menos" : "Ver mais") + ic(visaoTodas ? "north_west" : "arrow_outward") + "</button></div>";
    hp += "</div>";

    var dias = v.dias || [];
    var max = dias.reduce(function (m, d) { return Math.max(m, Number(d.total) || 0); }, 0) || 1;
    var TURNO = ["manhã", "tarde", "noite"];
    var hd = '<div class="painel">' + painelCab("Tokens · últimos 14 dias", esc(tok(k.tokens_hoje)) + " hoje") +
      '<div class="ondas" role="img" aria-label="Tokens por turno nos últimos 14 dias">' + dias.map(function (d) {
        var t = Number(d.total) || 0, s = Number(d.saida) || 0;
        var tit = ddmm(d.dia) + " · " + (TURNO[d.turno] || "") + " · " + tok(t) + " (" + tok(s) + " saída)";
        return '<div class="onda" title="' + esc(tit) + '"><i style="height:' + Math.max(t ? 2 : 0, Math.round(t / max * 100)) + '%"></i><i style="height:' + Math.round(s / max * 100) + '%"></i></div>';
      }).join("") + "</div>" +
      '<div class="legenda"><span><i></i>entrada + saída</span><span><i class="s"></i>saída</span></div>';
    // Tres numeros tirados do proprio grafico: media por dia, a ultima semana contra a anterior e quanto foi saida.
    var somaT = 0, somaS = 0, nDias = {};
    dias.forEach(function (d) { var t = Number(d.total) || 0; somaT += t; somaS += Number(d.saida) || 0; nDias[d.dia] = 1; });
    var qtd = Object.keys(nDias).length;
    // A ultima semana contra a anterior, pelos mesmos 14 dias do grafico.
    var diasOrd = Object.keys(nDias).sort(), porDia = {};
    dias.forEach(function (d) { porDia[d.dia] = (porDia[d.dia] || 0) + (Number(d.total) || 0); });
    var sem = function (ds) { return ds.reduce(function (s, x) { return s + porDia[x]; }, 0); };
    var semA = sem(diasOrd.slice(-7)), semB = sem(diasOrd.slice(-14, -7));
    var varSemana = semB ? (semA >= semB ? "+" : "−") + pct(Math.abs(semA / semB - 1)) + " vs anterior" : "—";
    if (dias.length) hd += '<dl class="onda-fatos">' +
      "<div><dt>Média por dia</dt><dd>" + esc(tok(qtd ? somaT / qtd : 0)) + "</dd></div>" +
      "<div><dt>Última semana</dt><dd>" + esc(varSemana) + "</dd></div>" +
      "<div><dt>Saída</dt><dd>" + esc(somaT ? pct(somaS / somaT) : "—") + "</dd></div></dl>";
    hd += "</div>";

    var av = v.avisos || [];
    var COR = { entrada: "var(--ok)", recusado: "var(--erro)", cancelado: "var(--ink3)", neutro: "var(--ink2)" };
    var mp = cfg("mercado_pago");
    var ha = '<div class="painel">' + painelCab("Últimos avisos do Mercado Pago", "/api/mp/aviso") + (desligado(mp) ? '<p class="aviso-falta embutido">' + ic("warning") + "<span>" + esc(mp.falta) + "</span></p>" : "");
    var avVer = avisosTodos ? av : av.slice(0, 5);
    ha += av.length ? avVer.map(function (a) {
      var val = Number(a.valor) || 0;
      var txt = a.tom === "entrada" ? "+ " + brl(val) : a.tom === "cancelado" ? "− " + brl(Math.abs(val)) : brl(val);
      return '<div class="aviso-mp"><span class="q">' + esc(quando(a.quando)) + '</span><span class="tp">' + esc(a.tipo) + '</span><span class="tx">' + esc(a.texto) + '</span><span class="v" style="color:' + (COR[a.tom] || COR.neutro) + '">' + esc(txt) + "</span></div>";
    }).join("") : '<p class="vazio-linha">Nenhum aviso ainda.</p>';
    if (av.length > 5) ha += '<div class="ver-mais-linha"><button type="button" class="ver-mais" data-a="avisosVerMais">' + (avisosTodos ? "Ver menos" : "Ver mais") + ic(avisosTodos ? "north_west" : "arrow_outward") + "</button></div>";
    ha += "</div>";

    return h + '<div class="duas-col">' + hp + hd + "</div>" + ha;
  };
  function kpi(t, v, sub, cor) { return "<div><dt>" + esc(t) + '</dt><dd' + (cor ? ' style="color:' + cor + '"' : "") + ">" + esc(v) + '</dd><span class="sub">' + esc(sub) + "</span></div>"; }

  /* ---------- 2. Contas e cadastros ---------- */
  function contasFiltradas() {
    var d = dadosDe("contas"); if (!d) return [];
    var q = norm(U.contas.q.trim()), f = U.contas.filtro;
    return (d.contas || []).filter(function (c) {
      if (f !== "todas" && c.situacao !== f) return false;
      if (!q) return true;
      return norm([c.nome, c.email, c.escritorio && c.escritorio.nome, c.escritorio && c.escritorio.slug, c.oab].join(" ")).indexOf(q) >= 0;
    });
  }
  TELAS_RENDER.contas = function () {
    if (E.gaveta && E.gaveta.pagina) return contaPaginaHtml();
    var h = cab("Contas e cadastros", "Uma conta por conta Google. O escritório agrupa as contas que compartilham o mesmo CNPJ ou o mesmo endereço de acesso externo.");
    h += '<div class="barra-filtros">' +
      seg("contas.filtro", [["todas", "Todas"], ["ativa", "Ativas"], ["vencida", "Vencidas"], ["cortesia", "Cortesias"], ["cancelada", "Canceladas"]], U.contas.filtro) +
      seg("contas.agrupar", [["conta", "Por conta"], ["escritorio", "Por escritório"]], U.contas.agrupar) +
      '<label class="caixa-campo caixa-busca">' + ic("search") + '<input id="contas-q" data-in="contasQ" value="' + esc(U.contas.q) + '" placeholder="nome, e-mail, escritório, OAB ou RG" aria-label="Buscar contas" spellcheck="false"></label></div>';
    var est = estadoLeitura(["contas"], "contas"); if (est) return h + est;
    h += erroRecente("contas", "contas");
    var lista = contasFiltradas();
    if (U.contas.agrupar === "conta") {
      var cols = "minmax(180px,1fr) 110px 96px 100px 100px";
      var linhas = lista.map(function (c) {
        var s = sitConta(c.situacao);
        return '<button type="button" class="grade-linha" data-a="abrirConta" data-id="' + esc(c.id) + '">' +
          '<span class="cel-nome"><b class="corta">' + esc(c.nome) + '</b><small class="corta">' + esc(c.email) + (c.escritorio && c.escritorio.nome ? " · " + esc(c.escritorio.nome) : "") + "</small></span>" +
          '<span class="t13">' + esc(c.plano ? c.plano.nome : "—") + "</span>" + sit(s[0], s[1]) +
          '<span class="num dir">' + esc(tok(c.restantes)) + '</span><span class="num dir c-ink3">' + esc(rel(c.ultimo_uso)) + "</span></button>";
      }).join("") || '<p class="vazio-linha">Nenhuma conta com esse filtro.</p>';
      h += '<div class="painel">' + grade(cols, 640, "<span>Conta</span><span>Plano</span><span>Situação</span><span class=\"dir\">Restantes</span><span class=\"dir\">Último uso</span>", linhas) +
        '<div class="pe-painel">' + lista.length + (lista.length === 1 ? " conta" : " contas") + "</div></div>";
    } else {
      var ids = {}; lista.forEach(function (c) { ids[c.id] = c; });
      var escs = (dadosDe("contas").escritorios || []).map(function (e) {
        return { e: e, cs: (e.contas || []).map(function (id) { return ids[id]; }).filter(Boolean) };
      }).filter(function (x) { return x.cs.length; });
      h += escs.length ? '<div class="pilha" style="gap:16px">' + escs.map(function (x) {
        var e = x.e;
        return '<div class="painel"><div class="esc-cab"><span class="txt2"><b>' + esc(e.nome) + "</b><small>" + esc(e.slug ? e.slug + ".paulus.ia.br" : "sem endereço") + (e.documento ? " · " + esc(e.documento) : "") + "</small></span>" +
          '<span class="num">' + x.cs.length + (x.cs.length === 1 ? " conta" : " contas") + '</span><span class="num">' + esc(tok(e.tokens_mes)) + ' no mês</span><span class="num c-ok">' + esc(brl(e.receita_mes)) + "</span></div>" +
          x.cs.map(function (c) {
            var s = sitConta(c.situacao);
            return '<button type="button" class="linha-btn esc-conta" data-a="abrirConta" data-id="' + esc(c.id) + '"><span class="nm">' + esc(c.nome) + " <span>" + esc(c.email) + '</span></span><span class="t125">' + esc(c.plano ? c.plano.nome : "—") + '</span><span class="sit" style="color:' + s[1] + '">' + esc(s[0]) + "</span></button>";
          }).join("") + "</div>";
      }).join("") + "</div>" : '<div class="painel"><p class="vazio-linha">Nenhum escritório com esse filtro.</p></div>';
    }
    return h;
  };

  /* ---------- 3. Permissoes do Google ---------- */
  TELAS_RENDER.google = function () {
    var h = cab("Permissões do Google", "Quem ligou o Gmail, a Agenda ou o Drive ao Paulus. <b>Revogar</b> tira serviços; <b>Desvincular</b> solta a conta Google inteira.");
    var est = estadoLeitura(["contas"], "google"); if (est) return h + est;
    h += erroRecente("contas", "google");
    var todas = dadosDe("contas").contas || [];
    var gs = todas.filter(function (c) { return c.google; });
    var podeRev = pode("google.servicos"), podeDes = pode("google.desvincular");
    // Clicar e segurar numa linha abre a selecao; depois, cada clique marca ou desmarca.
    var SEL = U.google.sel, nSel = SEL ? Object.keys(SEL).filter(function (k) { return SEL[k]; }).length : 0;
    // Selecionando, o cabecalho do card vira a barra de selecao, como em Gravacoes no programa.
    var elegiveis = gs.filter(function (c) { return !naFila("google.desvincular", c.id); }).length, tudo = nSel && nSel >= elegiveis;
    h += '<div class="painel' + (SEL ? " selecionando" : "") + '">' + (SEL && podeDes ?
      '<div class="painel-cab sel-cab"><button type="button" class="caixinha tri' + (tudo ? " cheia" : nSel ? " parcial" : "") + '" role="checkbox" aria-checked="' + (tudo ? "true" : nSel ? "mixed" : "false") + '" data-a="' + (nSel ? "googleSelSair" : "googleSelTodas") + '" aria-label="' + (nSel ? "Limpar a seleção" : "Selecionar todas") + '">' + (tudo ? ic("check") : nSel ? ic("remove") : "") + "</button>" +
      "<b>" + nSel + (nSel === 1 ? " selecionada" : " selecionadas") + '</b><span class="sel-div"></span><button type="button" class="btn-icone sel-perigo" data-a="googleDesvMassa"' + (nSel ? "" : " disabled") + ' aria-label="Desvincular as selecionadas" title="Desvincular as selecionadas">' + ic("link_off") + "</button></div>"
      : painelCab("Contas com Google ligado", gs.length + " de " + todas.length));
    h += gs.length ? gs.map(function (c) {
      var conf = U.google.confirmando === c.id;
      var filaS = naFila("google.servicos", c.id), filaD = naFila("google.desvincular", c.id);
      var acoes;
      if (conf) {
        acoes = '<span style="display:flex;align-items:center;gap:6px;flex-wrap:wrap"><span class="t125 c-erro">Desvincular a conta Google de ' + esc(primeiro(c.nome)) + '?</span>' +
          '<button type="button" class="mini" data-a="googleVoltar">Voltar</button><button type="button" class="mini perigo" data-a="googleDesvincular" data-id="' + esc(c.id) + '">Confirmar</button></span>';
      } else {
        acoes = '<span class="par">' +
          (podeRev ? '<button type="button" class="mini" data-a="modalGoogle" data-id="' + esc(c.id) + '"' + attrDis(filaS, "já está na fila de alterações") + ">" + (filaS ? "Revogação na fila" : "Revogar permissões") + "</button>" : "") +
          (podeDes ? '<button type="button" class="mini cheia" data-a="googleConfirmar" data-id="' + esc(c.id) + '"' + attrDis(filaD, "já está na fila de alterações") + ">" + ic("link_off") + (filaD ? "Na fila" : "Desvincular") + "</button>" : "") + "</span>";
      }
      var marc = !!(SEL && SEL[c.id]), filaDes = naFila("google.desvincular", c.id);
      return '<div class="linha g-linha' + (marc ? " marcada" : "") + '"' + (SEL ? ' aria-selected="' + marc + '"' : "") + (podeDes && !filaDes ? ' data-gsel="' + esc(c.id) + '"' : "") + ">" +

        '<span class="txt2" style="min-width:200px"><b>' + esc(c.nome) + '</b><small class="mono">' + esc(c.email) + "</small></span>" +
        '<span class="res-perms">' + [["mail.google.com", "gmail", "Gmail"], ["calendar.events", "agenda", "Agenda e Meet"], ["drive.file", "drive", "Drive · enviar"], ["drive.readonly", "drive", "Drive · ler"]].filter(function (s) { return (c.google.escopos || []).indexOf(s[0]) >= 0; }).map(function (s) {
          return '<span class="res-perm" title="' + esc(s[0]) + '">' + SIMB_G[s[1]] + esc(s[2]) + "</span>"; }).join("") + "</span>" +
        '<span class="num s11 c-ink3" style="flex:none;white-space:nowrap">conferido ' + esc(rel(c.google.conferido)) + "</span>" + (SEL ? '<span class="acoes-esmaecidas" aria-hidden="true">' + acoes + "</span>" : acoes) + "</div>";
    }).join("") : '<p class="vazio-linha">Nenhuma conta ligou o Google ainda.</p>';
    h += "</div>";
    if (!podeRev && !podeDes) h += '<p class="nota-pe">O papel ' + esc(PAPEL_NOME[E.sessao.papel] || E.sessao.papel) + " vê as permissões, mas não revoga nem desvincula.</p>";
    h += '<p class="nota-pe">Os escopos vêm do consentimento guardado no Paulus instalado; aqui só o nome. O token em si nunca passa por este painel.</p>';
    return h;
  };

  /* ---------- 4. Tuneis Cloudflare ---------- */
  var EST_TUNEL = { healthy: ["saudável", "var(--ok)"], degraded: ["instável", "var(--atencao)"], inactive: ["parado", "var(--ink3)"], down: ["fora do ar", "var(--erro)"], desativado: ["desativado", "var(--erro)"] };
  function parado(t) { return t.estado === "inactive" || t.estado === "down"; }
  function limpezaDe(t) {
    var l = t.limpeza;
    if (!l || l.dias == null) return ["sem previsão", "var(--ink3)", null];
    var d = Number(l.dias);
    var cor = !t.ultima_conexao ? (d <= 2 ? "var(--erro)" : "var(--atencao)") : (d <= 7 ? "var(--erro)" : "var(--atencao)");
    return [d <= 0 ? "apaga hoje" : "apaga em " + d + "d", cor, d];
  }
  function tuneisCf() {
    var d = dadosDe("tuneis") || {};
    var c = d.cf && d.cf.ligado === false ? d.cf : cfg("tuneis");
    return c;
  }
  TELAS_RENDER.tuneis = function () {
    var h = cab("Túneis Cloudflare", "Cada escritório tem um túnel e um endereço. A limpeza diária apaga os que nunca conectaram em 7 dias e os parados há mais de 180.");
    var est = estadoLeitura(["tuneis"], "tuneis");
    var sel = U.tuneis.sel, nSel = Object.keys(sel).filter(function (k) { return sel[k]; }).length;
    var cf = tuneisCf(), cfOff = desligado(cf), podeA = pode("tunel.apagar");
    h += '<div class="barra-filtros">' + seg("tuneis.filtro", [["todos", "Todos"], ["parados", "Só parados"], ["risco", "Perto de apagar"], ["ativos", "Conectados"]], U.tuneis.filtro) + '<span style="flex:1"></span>' +
      "</div>";
    if (est) return h + est;
    h += falta(cf) + erroRecente("tuneis", "tuneis");
    var d = dadosDe("tuneis"), todos = d.tuneis || [];
    var f = U.tuneis.filtro;
    var lista = todos.filter(function (t) {
      if (f === "parados") return parado(t);
      if (f === "risco") return limpezaDe(t)[2] !== null;
      if (f === "ativos") return t.ativo !== false && (t.estado === "healthy" || t.estado === "degraded");
      return true;
    });
    var cols = "minmax(140px,1fr) 84px 96px 104px 20px";
    var todosParadosSel = todos.filter(parado).length > 0 && todos.filter(parado).every(function (t) { return sel[t.slug]; });
    var cabeca = '<span>Endereço</span><span>Estado</span><span class="dir">Última conexão</span><span class="dir">Limpeza</span><span></span>';
    var emailOff = desligado(cfg("email"));
    var linhas = lista.map(function (t) {
      var k = t.ativo === false ? "desativado" : t.estado;
      var e = EST_TUNEL[k] || [k, "var(--ink3)"];
      var ult = dt(t.ultima_conexao), velho = !ult || (Date.now() - ult) > 60 * 864e5;
      var l = limpezaDe(t), aberto = U.tuneis.aberto === t.slug, s = !!sel[t.slug];
      var r = '<div class="tunel' + (s ? " sel" : aberto ? " aberto" : "") + '">' +
        '<div class="grade-linha clicavel' + (U.tuneis.selecionando && s ? " marcada" : "") + '" role="button" tabindex="0" aria-expanded="' + aberto + '" data-a="tunelAbrir" data-slug="' + esc(t.slug) + '"' + (podeA && !naFila("tunel.apagar", t.slug) ? ' data-tsel="' + esc(t.slug) + '"' : "") + (U.tuneis.selecionando ? ' aria-selected="' + s + '"' : "") + ">" +
        '<span class="cel-nome endereco"><b class="corta">' + esc(t.slug) + "<span>.paulus.ia.br</span></b><small class=\"corta sans\">" + esc(t.nome) + (t.responsavel ? " · " + esc(t.responsavel) : "") + "</small></span>" +
        sit(e[0], e[1]) + '<span class="num dir" style="color:' + (velho ? "var(--erro)" : "var(--ink2)") + '">' + esc(rel(t.ultima_conexao)) + "</span>" +
        '<span class="num s11 dir" style="color:' + l[1] + '"' + (t.limpeza && t.limpeza.motivo ? ' title="' + esc(t.limpeza.motivo) + '"' : "") + ">" + esc(l[0]) + "</span>" + ic(aberto ? "expand_less" : "expand_more", "s18 c-ink3") + "</div>";
      if (aberto) {
        var hist = (t.historico || []).slice().sort(function (a, b) { return String(b.quando).localeCompare(String(a.quando)); });
        var podeE = pode("tunel.endereco"), podeT = pode("tunel.ativo");
        var filaA = naFila("tunel.apagar", t.slug), filaE = naFila("tunel.endereco", t.slug), filaT = naFila("tunel.ativo", t.slug);
        // O detalhe aberto: os dados em grade e as acoes embaixo, a esquerda; o historico, a direita.
        r += '<div class="tunel-det"><div class="td-esq td-col"><span class="td-tit">Dados do túnel</span><dl class="res-grade c2">' +
          fato("Responsável", t.responsavel || "—") + fato("Criado", ddmmaaaa(t.criado_em)) + fato("Porta", t.porta == null ? "—" : String(t.porta)) +
          '<div><dt>Limpeza</dt><dd style="color:' + l[1] + '">' + esc(l[0]) + (t.limpeza && t.limpeza.motivo ? '<small class="td-motivo">' + esc(t.limpeza.motivo) + "</small>" : "") + "</dd></div>" +
          '<div class="largo"><dt>ID do túnel</dt><dd class="mono" style="font-size:12.5px">' + esc(t.tunnel_id || "—") + "</dd></div></dl>" +
          '<div class="res-acoes">' +
          '<button type="button" class="mini" data-a="tunelAvisar" data-slug="' + esc(t.slug) + '"' + attrDis(emailOff || !t.responsavel, emailOff ? cfg("email").falta : "sem responsável") + ">" + ic("mail") + "Avisar responsável</button>" +
          (podeE ? '<button type="button" class="mini" data-a="modalEndereco" data-slug="' + esc(t.slug) + '"' + attrDis(cfOff || filaE || filaA, cfOff ? cf.falta : "já está na fila de alterações") + ">" + ic("swap_horiz") + (filaE ? "Troca na fila" : "Alterar endereço") + "</button>" : "") +
          (podeT ? '<button type="button" class="mini" data-a="tunelAtivo" data-slug="' + esc(t.slug) + '"' + attrDis(cfOff || filaT || filaA, cfOff ? cf.falta : "já está na fila de alterações") + ">" + (filaT ? "Na fila" : t.ativo === false ? "Ativar acesso" : "Desativar acesso") + "</button>" : "") +
          (podeA ? '<button type="button" class="mini vermelho" data-a="tunelLiberar" data-slug="' + esc(t.slug) + '"' + attrDis(cfOff || filaA, cfOff ? cf.falta : "já está na fila de alterações") + ">" + (filaA ? "Apagar na fila" : "Liberar endereço") + "</button>" : "") +
          '</div></div><div class="td-dir"><span class="td-tit">Histórico</span>' +
          (hist.length ? hist.slice(0, 4).map(function (x) { return '<div class="td-hist"><span>' + esc(ddmm(x.quando)) + "</span><span>" + esc(x.texto) + "</span></div>"; }).join("") : '<div class="td-hist"><span>—</span><span>Sem eventos registrados.</span></div>') +
          (hist.length ? '<button type="button" class="ver-mais td-ver" data-a="tunelHist" data-slug="' + esc(t.slug) + '">Ver histórico completo' + ic("arrow_outward") + "</button>" : "") + "</div></div>";
      }
      return r + "</div>";
    }).join("") || '<p class="vazio-linha">Nenhum túnel com esse filtro.</p>';
    // Selecionando (segurar o clique numa linha), o alto do card vira a barra de selecao, como em Permissoes.
    var elegT = todos.filter(function (t) { return !naFila("tunel.apagar", t.slug); }).length, tudoT = nSel && nSel >= elegT;
    var selCab = U.tuneis.selecionando && podeA ? '<div class="painel-cab sel-cab"><button type="button" class="caixinha tri' + (tudoT ? " cheia" : nSel ? " parcial" : "") + '" role="checkbox" aria-checked="' + (tudoT ? "true" : nSel ? "mixed" : "false") + '" data-a="' + (nSel ? "tuneisSelSair" : "tuneisSelTodas") + '" aria-label="' + (nSel ? "Limpar a seleção" : "Selecionar todos") + '">' + (tudoT ? ic("check") : nSel ? ic("remove") : "") + "</button>" +
      "<b>" + nSel + (nSel === 1 ? " selecionado" : " selecionados") + '</b><span class="sel-div"></span><button type="button" class="btn-icone sel-perigo" data-a="tuneisApagar"' + attrDis(cfOff || !nSel, cfOff ? cf.falta : "") + ' aria-label="Apagar túnel e DNS dos selecionados" title="Apagar túnel e DNS">' + ic("delete") + "</button>" +
      '<button type="button" class="btn-texto-mudo" style="margin-left:auto" data-a="tuneisSelParados">Selecionar os parados</button></div>' : "";
    h += '<div class="painel' + (U.tuneis.selecionando ? " selecionando" : "") + '">' + selCab + grade(cols, 520, cabeca, linhas) + "</div>";
    // O registro de enderecos: cada evento com data, endereco, o que aconteceu, quem fez e como ficou.
    var REG_EV = { criado: ["criou o endereço", "add_link"], alterado: ["trocou o endereço", "swap_horiz"], desativado: ["desativou o endereço", "pause_circle"], reativado: ["reativou o endereço", "play_circle"], liberado: ["liberou o endereço", "link_off"] };
    var REG_EST = { ativo: ["ativo", "var(--ok)"], desativado: ["desativado", "var(--erro)"], livre: ["livre", "var(--ink3)"] };
    var reg = (d.registro || []).slice().sort(function (a, b) { return String(b.quando).localeCompare(String(a.quando)); });
    var fr = U.tuneis.reg, fq = norm(U.tuneis.regQ || ""), fp = U.tuneis.periodo || "tudo";
    var regF = reg.filter(function (x) {
      var dia = String(x.quando).slice(0, 10);
      return (fr === "todos" || x.evento === fr) && (!fq || norm([x.slug, x.de, x.quem, x.motivo].join(" ")).indexOf(fq) >= 0) && (fp !== "custom" || (dia >= U.tuneis.de && dia <= U.tuneis.ate));
    });
    var regVer = U.tuneis.regTodos ? regF : regF.slice(0, 6);
    var colsR = "116px minmax(140px,1fr) minmax(220px,1.7fr) minmax(170px,1.1fr) 96px";
    var linhasR = regVer.map(function (x) {
      var ev = REG_EV[x.evento] || [x.evento, "history"], es = REG_EST[x.estado] || [x.estado || "—", "var(--ink3)"];
      var auto = /autom/.test(x.quem || "");
      return '<div class="grade-linha p10 reg-linha"><span class="num">' + esc(ddmmaaaa(x.quando)) + "<small>" + esc(String(x.quando).slice(11, 16)) + "</small></span>" +
        '<span class="endereco reg-end"><b class="corta">' + esc(x.slug) + "<span>.paulus.ia.br</span></b>" + (x.de ? '<small class="corta">antes ' + esc(x.de) + "</small>" : "") + "</span>" +
        '<span class="reg-ev">' + ic(ev[1]) + '<span class="txt2"><b>' + esc((auto ? "O sistema " : "") + ev[0]) + "</b>" + (x.motivo ? "<small>" + esc(x.motivo) + "</small>" : "") + "</span></span>" +
        '<span class="corta reg-quem' + (auto ? " auto" : "") + '">' + esc(x.quem || "—") + "</span>" + sit(es[0], es[1]) + "</div>";
    }).join("") || '<p class="vazio-linha">Nenhum evento com esse filtro.</p>';
    h += '<div class="pilha" style="gap:12px"><h2 class="reg-tit">Registro de endereços</h2><div class="barra-filtros reg-filtros">' +
      seg("tuneis.reg", [["todos", "Todos"], ["criado", "Criados"], ["alterado", "Alterados"], ["desativado", "Desativados"], ["reativado", "Reativados"], ["liberado", "Liberados"]], fr) +
      '<span class="caixa-campo reg-busca">' + ic("search") + '<input id="reg-q" data-in="regQ" value="' + esc(U.tuneis.regQ || "") + '" placeholder="Buscar endereço, e-mail ou motivo" autocomplete="off"></span>' +
      '<div class="segmentos"><div role="group"><button type="button" class="seg-cal" data-a="regCal" aria-pressed="' + (fp === "custom") + '" aria-expanded="' + !!U.tuneis.cal + '">' + ic("calendar_month") + "<span>" + (fp === "custom" ? esc(ddmm(U.tuneis.de) + " – " + ddmm(U.tuneis.ate)) : "Período") + "</span></button>" +
      (fp === "custom" ? '<button type="button" data-a="calLimparReg" aria-label="Tirar o período" title="Tirar o período">' + ic("close") + "</button>" : "") + "</div></div>" +
      (U.tuneis.cal ? calHtml(U.tuneis.cal) : "") + "</div>" +
      '<div class="painel">' + grade(colsR, 760, "<span>Data</span><span>Endereço</span><span>Evento</span><span>Quem</span><span>Estado</span>", linhasR) +
      (regF.length ? '<div class="ver-mais-linha reg-pe"><button type="button" class="mini" data-a="regJson">' + ic("download") + "Exportar .json</button>" +
        (regF.length > 6 ? '<button type="button" class="ver-mais" data-a="regVerMais">' + (U.tuneis.regTodos ? "Ver menos" + ic("north_west") : "Ver todos os " + regF.length + ic("arrow_outward")) + "</button>" : "") + "</div>" : "") + "</div></div>";
    regFiltrado = regF;
    // O que cada acao faz, lado a lado, na largura toda.
    h += '<div class="tun-legenda"><div>' + ic("delete") + '<span><b>Liberar ou apagar</b>Remove o túnel, o endereço e o registro do escritório. O nome fica livre para outro escritório, e o acesso externo precisa ser ligado de novo no Paulus.</span></div>' +
      "<div>" + ic("pause_circle") + "<span><b>Desativar acesso</b>Só pausa o endereço: o túnel continua e nada é apagado. O Paulus do escritório recebe o motivo na próxima conexão, e Ativar acesso devolve tudo como estava.</span></div></div>";
    return h;
  };
  function fato(k, v) { return "<div><dt>" + esc(k) + "</dt><dd>" + esc(v) + "</dd></div>"; }

  // A aba Tunel da pagina da conta: o tunel do escritorio, com as mesmas acoes da tela Tuneis.
  function tunelAbaHtml(slug) {
    var d = dadosDe("tuneis");
    if (!d) { if (!tunelAbaHtml.pedido) { tunelAbaHtml.pedido = true; ler("tuneis"); } return '<p class="carregando">Carregando o túnel…</p>'; }
    var t = (d.tuneis || []).filter(function (x) { return x.slug === slug; })[0];
    if (!t) return '<p class="vazio-linha">Este escritório ainda não tem túnel.</p>';
    var e = EST_TUNEL[t.ativo === false ? "desativado" : t.estado] || [t.estado, "var(--ink3)"], l = limpezaDe(t);
    var cf = tuneisCf(), cfOff = desligado(cf), emailOff = desligado(cfg("email"));
    var podeE = pode("tunel.endereco"), podeT = pode("tunel.ativo"), podeA = pode("tunel.apagar");
    var filaA = naFila("tunel.apagar", t.slug), filaE = naFila("tunel.endereco", t.slug), filaT = naFila("tunel.ativo", t.slug);
    var acoes = '<button type="button" class="mini" data-a="tunelAvisar" data-slug="' + esc(t.slug) + '"' + attrDis(emailOff || !t.responsavel, emailOff ? cfg("email").falta : "sem responsável") + ">" + ic("mail") + "Avisar responsável</button>" +
      (podeE ? '<button type="button" class="mini" data-a="modalEndereco" data-slug="' + esc(t.slug) + '"' + attrDis(cfOff || filaE || filaA, cfOff ? cf.falta : "já está na fila de alterações") + ">" + ic("swap_horiz") + (filaE ? "Troca na fila" : "Alterar endereço") + "</button>" : "") +
      (podeT ? '<button type="button" class="mini" data-a="tunelAtivo" data-slug="' + esc(t.slug) + '"' + attrDis(cfOff || filaT || filaA, cfOff ? cf.falta : "já está na fila de alterações") + ">" + (filaT ? "Na fila" : t.ativo === false ? "Ativar acesso" : "Desativar acesso") + "</button>" : "") +
      (podeA ? '<button type="button" class="mini vermelho" data-a="tunelLiberar" data-slug="' + esc(t.slug) + '"' + attrDis(cfOff || filaA, cfOff ? cf.falta : "já está na fila de alterações") + ">" + (filaA ? "Apagar na fila" : "Liberar endereço") + "</button>" : "");
    var h = '<div class="painel res-card"><div class="painel-cab secao-cab cf-faixa"><span class="cf-titulo"><img src="' + ASSETS + 'cloudflare.svg" alt="" width="22" height="22"><span class="rotulo">Túnel Cloudflare</span></span><a class="conta-link" style="margin:0;padding:0;border:0" href="https://' + esc(t.slug) + '.paulus.ia.br" target="_blank" rel="noopener">' + esc(t.slug) + ".paulus.ia.br" + ic("arrow_outward") + "</a></div>" +
      '<dl class="res-grade c3">' +
      '<div><dt>Situação</dt><dd><span class="ficha-sit" style="color:' + e[1] + ';margin:0 6px 0 0"><i></i></span>' + esc(e[0]) + "</dd></div>" +
      fato("Última conexão", rel(t.ultima_conexao)) +
      '<div><dt>Limpeza</dt><dd style="color:' + l[1] + '"' + (t.limpeza && t.limpeza.motivo ? ' title="' + esc(t.limpeza.motivo) + '"' : "") + ">" + esc(l[0]) + "</dd></div>" +
      fato("Criado", ddmmaaaa(t.criado_em)) + fato("Porta", t.porta == null ? "—" : String(t.porta)) + fato("Responsável", t.responsavel || "—") +
      '<div class="largo"><dt>ID do túnel</dt><dd class="mono" style="font-size:12.5px">' + esc(t.tunnel_id || "—") + "</dd></div></dl>" +
      '<div class="res-acoes">' + acoes + "</div></div>";
    var hist = (t.historico || []).slice().sort(function (a, b) { return String(b.quando).localeCompare(String(a.quando)); });
    h += '<div class="painel"><div class="painel-cab secao-cab"><span class="rotulo">Histórico</span><span class="cab-dir">' + hist.length + "</span></div>" +
      (hist.length ? hist.map(function (x) { return '<div class="linha hist-linha"><span class="num">' + esc(ddmmaaaa(x.quando)) + "</span><span>" + esc(x.texto) + "</span></div>"; }).join("") : '<p class="vazio-linha">Sem eventos registrados.</p>') + "</div>";
    return h + (falta(cf) || "");
  }

  /* ---------- 5. Nao renovacoes ---------- */
  TELAS_RENDER.renovacoes = function () {
    var h = cab("Não renovações", "Ciclos que venceram sem a cobrança do Mercado Pago. O plano segue valendo durante a tolerância; depois, a conta fica sem IA até pagar.");
    var est = estadoLeitura(["renovacoes"], "renovacoes"); if (est) return h + est;
    h += erroRecente("renovacoes", "renovacoes");
    var d = dadosDe("renovacoes"), ab = d.abertas || [], tr = d.tratadas || [];
    var email = cfg("email"), emailOff = desligado(email);
    h += falta(email);
    var cols = "minmax(170px,1fr) 100px 150px minmax(160px,1.2fr) 244px";
    var linhas = ab.map(function (r) {
      var dv = Number(r.dias_vencido) || 0, tol = r.tolerancia_dias == null ? 0 : Number(r.tolerancia_dias), resta = tol - dv;
      var prazo = resta > 0 ? "venceu há " + dv + "d · " + resta + "d de tolerância" : "sem IA há " + (-resta) + "d";
      var SR = U.renovacoes.sel, marc = !!(SR && SR[r.id]);
      var abertoR = !SR && String(U.renovacoes.aberto) === String(r.id);
      return '<div class="grade-linha p10 clicavel' + (marc ? " marcada" : "") + (abertoR ? " aberta" : "") + '" data-rsel="' + esc(r.id) + '" data-a="renovAbrir" data-id="' + esc(r.id) + '" role="button" tabindex="0" aria-expanded="' + abertoR + '"' + (SR ? ' aria-selected="' + marc + '"' : "") + '><span class="cel-nome"><b class="corta">' + esc(r.nome) + '</b><small class="corta">' + esc(r.email) + "</small></span>" +
        '<span class="cel-nome"><span class="t13">' + esc(r.plano ? r.plano.nome : "—") + '</span><small class="c-ink3" style="font-size:11px">' + esc(r.plano ? brl(r.plano.valor) : "") + "</small></span>" +
        '<span class="num s11" style="line-height:1.4;color:' + (resta > 0 ? "var(--atencao)" : "var(--erro)") + '" title="venceu em ' + esc(ddmmaaaa(r.fim)) + '">' + esc(prazo) + "</span>" +
        '<span class="t125">' + esc(r.motivo || "—") + "</span>" +
        '<span class="par' + (SR ? " acoes-esmaecidas-par" : "") + '" style="justify-content:flex-end">' +
        '<button type="button" class="mini cheia" data-a="renovLembrete" data-id="' + esc(r.id) + '"' + (emailOff ? ' disabled title="' + esc(email.falta) + '"' : r.lembrete_em ? ' title="enviado ' + esc(quando(r.lembrete_em)) + '"' : "") + ">" + ic("mail") + (r.lembrete_em ? "Lembrete enviado" : "Enviar lembrete") + "</button>" +
        '<button type="button" class="mini" data-a="abrirConta" data-id="' + esc(r.id) + '">Conta</button>' +
        '<button type="button" class="mini quadrado" data-a="renovTratar" data-id="' + esc(r.id) + '" aria-label="Marcar tratada" title="Marcar tratada">' + ic("check", "c-ink2") + "</button></span></div>" +
        (abertoR ? renovDetHtml(r, emailOff, email) : "");
    }).join("") || '<p class="vazio-linha">Nenhuma pendente.</p>';
    // Segurar o clique numa linha seleciona varias (como em Permissoes e Tuneis): lembrete e "tratada" para todas de uma vez.
    var SR = U.renovacoes.sel, nR = SR ? Object.keys(SR).filter(function (k) { return SR[k]; }).length : 0, tudoR = nR && nR >= ab.length;
    var selR = SR ? '<div class="painel-cab sel-cab"><button type="button" class="caixinha tri' + (tudoR ? " cheia" : nR ? " parcial" : "") + '" role="checkbox" aria-checked="' + (tudoR ? "true" : nR ? "mixed" : "false") + '" data-a="' + (nR ? "renovSelSair" : "renovSelTodas") + '" aria-label="' + (nR ? "Limpar a seleção" : "Selecionar todas") + '">' + (tudoR ? ic("check") : nR ? ic("remove") : "") + "</button>" +
      "<b>" + nR + (nR === 1 ? " selecionada" : " selecionadas") + '</b><span class="sel-div"></span>' +
      '<button type="button" class="btn-icone sel-acao" data-a="renovLembreteMassa"' + attrDis(emailOff || !nR, emailOff ? email.falta : "") + ' aria-label="Enviar lembrete às selecionadas" title="Enviar lembrete">' + ic("mail") + "</button>" +
      '<button type="button" class="btn-icone sel-acao" data-a="renovTratarMassa"' + (nR ? "" : " disabled") + ' aria-label="Marcar as selecionadas como tratadas" title="Marcar tratadas">' + ic("check") + "</button></div>" : "";
    h += '<div class="painel' + (SR ? " selecionando" : "") + '">' + selR + grade(cols, 880, "<span>Conta</span><span>Plano</span><span>Prazo</span><span>Motivo</span><span></span>", linhas) +
      '<div class="pe-painel fio">' + ab.length + (ab.length === 1 ? " aberta" : " abertas") + " · " + tr.length + (tr.length === 1 ? " tratada" : " tratadas") + "</div></div>";
    var c = d.config || {};
    var OP = [["email", "E-mail a cada não renovação", "para " + (E.sessao.access && E.sessao.access.email || "você") + ", na hora do aviso do Mercado Pago"], ["resumo", "Resumo diário às 8h", "vencidas, tolerância acabando, túneis parados"], ["whats", "WhatsApp quando a tolerância acabar", "só o nome e o plano, sem dados pessoais"], ["tol", "Lembrete automático ao cliente no 3º dia", "modelo \"Seu plano não renovou\""]];
    h += '<div class="duas-col"><div class="painel">' + painelCab("Como você quer ser avisado") + OP.map(function (o) {
      return '<button type="button" class="linha-btn" role="switch" aria-checked="' + !!c[o[0]] + '" data-a="renovCfg" data-k="' + o[0] + '"><span class="txt2"><b>' + esc(o[1]) + "</b><small>" + esc(o[2]) + "</small></span>" + sw(!!c[o[0]]) + "</button>";
    }).join("") + "</div>";
    h += '<div class="painel">' + painelCab("Tratadas", String(tr.length)) + (tr.length ? tr.map(function (r) {
      return '<div class="linha p10" style="flex-wrap:nowrap"><span class="t13" style="flex:1;min-width:0">' + esc(r.nome) + '</span><span class="num s11 c-ink3">' + esc(r.plano ? r.plano.nome : "") + '</span><button type="button" class="mini" data-a="renovReabrir" data-id="' + esc(r.id) + '">Reabrir</button></div>';
    }).join("") : '<p class="vazio-linha">Nenhuma tratada.</p>') + "</div></div>";
    return h;
  };

  /* ---------- 6. Disparo de e-mails ---------- */
  var SIT_CAMP = { enviada: "var(--ok)", agendada: "var(--atencao)", "na fila": "var(--atencao)", enviando: "var(--atencao)", rascunho: "var(--ink3)" };
  function publicosLista() {
    var d = dadosDe("campanhas") || {}, l = (d.publicos || []).slice(), so = U.emails.so;
    if (so) l.unshift({ id: "conta:" + so.id, label: "Só " + so.nome, n: 1, gmail: /@gmail\.com$/i.test(so.email || "") ? 1 : 0 });
    var es = U.emails.escolhidas || [];
    l.push({ id: "escolhidas", label: "Escolher contas", sub: "busque e adicione uma a uma", n: es.length, gmail: es.filter(function (c) { return /@gmail\.com$/i.test(c.email || ""); }).length });
    return l;
  }
  function publicoAtual() {
    var l = publicosLista(), id = U.emails.camp.publico;
    return l.filter(function (p) { return p.id === id; })[0] || l[0] || null;
  }
  // Os campos {nome} {escritorio}... so sao trocados quando o publico e uma conta
  // so (a da gaveta); nos outros, ficam a mostra, marcados.
  function trocaCampos(t, html) {
    var so = U.emails.so, pub = publicoAtual();
    var unico = so && pub && pub.id === "conta:" + so.id;
    var val = unico ? { nome: primeiro(so.nome), escritorio: so.escritorio && so.escritorio.nome, plano: so.plano && so.plano.nome, vence_em: so.ciclo && so.ciclo.fim ? ddmm(so.ciclo.fim) : null } : {};
    var s = html ? esc(t) : t;
    return s.replace(/\{(nome|escritorio|plano|vence_em)\}/g, function (m, k) {
      if (val[k]) return html ? esc(val[k]) : val[k];
      return html ? '<span class="campo-livre">' + m + "</span>" : m;
    });
  }
  TELAS_RENDER.emails = function () {
    var h = cab("Campanhas de e-mail", "Escreva um e-mail, escolha quem recebe e envie agora ou agende. As mensagens saem aos poucos, em lotes por minuto.");
    var d = dadosDe("campanhas"), cs = d ? d.campanhas || [] : [];
    var env = cs.filter(function (c) { return c.situacao === "enviada"; });
    h += '<div class="barra-filtros">' + seg("emails.aba", [["campanhas", "Campanhas"], ["nova", "Nova campanha"], ["publicos", "Públicos"]], U.emails.aba) +
      (d ? '<span class="mono-dir">' + cs.length + (cs.length === 1 ? " campanha" : " campanhas") + " · " + env.length + (env.length === 1 ? " enviada" : " enviadas") + "</span>" : "") + "</div>";
    var est = estadoLeitura(["campanhas"], "emails"); if (est) return h + est;
    var envio = d.envio && d.envio.ligado === false ? d.envio : cfg("email");
    h += falta(envio) + erroRecente("campanhas", "emails");
    var aba = U.emails.aba;
    if (aba === "campanhas") {
      var st = d.stats || {};
      h += '<dl class="kpis k150">' + [["Enviados", String(st.enviados || 0)], ["Abertura", taxa(st.abertura)], ["Cliques", taxa(st.cliques)], ["Devolvidos", String(st.devolvidos || 0)]].map(function (k) { return "<div><dt>" + k[0] + "</dt><dd>" + esc(k[1]) + "</dd></div>"; }).join("") + "</dl>";
      var cols = "minmax(180px,1fr) 130px 70px 70px 70px 100px";
      var linhas = cs.map(function (c) {
        var n = Number(c.enviados) || 0, cor = SIT_CAMP[c.situacao] || "var(--ink3)";
        return '<div class="grade-linha"><span class="cel-nome"><b class="corta">' + esc(c.nome) + '</b><small class="sit" style="color:' + cor + '"><i></i>' + esc(c.situacao) + "</small></span>" +
          '<span class="t125 corta">' + esc(c.publico ? c.publico.label : "—") + '</span><span class="num dir c-ink2">' + (n ? n : "—") + '</span><span class="num dir">' + (n ? pct((c.abertos || 0) / n) : "—") + '</span><span class="num dir">' + (n ? pct((c.cliques || 0) / n) : "—") + '</span><span class="num dir c-ink3">' + esc(c.situacao === "enviada" ? ddmm(c.quando) : quando(c.quando)) + "</span></div>";
      }).join("") || '<p class="vazio-linha">Nenhuma campanha ainda.</p>';
      h += '<div class="painel">' + grade(cols, 680, '<span>Campanha</span><span>Público</span><span class="dir">Enviados</span><span class="dir">Abertura</span><span class="dir">Cliques</span><span class="dir">Quando</span>', linhas) + "</div>";
      h += '<button type="button" class="btn-duplo inicio" data-a="seg" data-seg="emails.aba" data-v="nova"><span>' + ic("campaign") + "Nova campanha</span></button>";
      return h;
    }
    if (aba === "publicos") {
      var ps = publicosLista();
      // A mesma tabela das outras listas do Admin: cabecalho, colunas e a acao na ponta.
      h += '<div class="painel">' + (ps.length ? grade("minmax(180px,2fr) 90px 90px 150px", 560, "<span>Público</span><span class=\"dir\">Contas</span><span class=\"dir\">No Gmail</span><span style=\"text-align:center\">Ações</span>", ps.map(function (p) {
        return '<div class="grade-linha p10"><span class="cel-nome"><b class="corta">' + esc(p.label) + "</b>" + (p.sub ? '<small class="corta">' + esc(p.sub) + "</small>" : "") + "</span>" +
          '<span class="dir mono">' + (p.n || 0) + '</span><span class="dir mono">' + (p.gmail || 0) + "</span>" +
          '<span class="par" style="justify-content:center"><button type="button" class="mini" data-a="usarPublico" data-id="' + esc(p.id) + '">Usar numa campanha</button></span></div>';
      }).join("")) : '<p class="vazio-linha">Nenhum público.</p>') + "</div>";
      h += '<p class="nota-pe">Cada público é montado com as contas cadastradas, pela situação da assinatura, pelo plano e por usar ou não o Gmail. Criar filtros próprios e importar listas chega na versão 1.1.</p>';
      return h;
    }
    // Nova campanha
    var camp = U.emails.camp, passo = U.emails.passo, pub = publicoAtual(), n = pub ? pub.n || 0 : 0;
    var envioOff = desligado(envio);
    h += '<div class="passos">' + [1, 2, 3].map(function (i) {
      return '<button type="button" class="passo-btn' + (passo >= i ? " feito" : "") + '" data-a="passo" data-n="' + i + '"' + (passo === i ? ' aria-current="step"' : "") + '><span class="n">' + i + "</span>" + ["Público", "Conteúdo", "Revisar"][i - 1] + "</button>";
    }).join("") + "</div>";
    var esq = '<div class="pilha">';
    if (passo === 1) {
      esq += '<div class="painel" role="radiogroup" aria-label="Público"><div class="painel-cab"><span class="rotulo">Quem recebe</span></div>' + publicosLista().map(function (p) {
        var on = pub && p.id === pub.id;
        return '<button type="button" class="linha-btn publico' + (on ? " on" : "") + '" role="radio" aria-checked="' + on + '" data-a="escolherPublico" data-id="' + esc(p.id) + '"><span class="radio' + (on ? " on" : "") + '"></span><span class="txt2"><b>' + esc(p.label) + "</b><small>" + (p.id === "escolhidas" ? ((U.emails.escolhidas || []).length ? "clique para alterar a lista" : "clique para escolher") : p.sub && !p.n ? esc(p.sub) : (p.gmail || 0) + " no Gmail") + '</small></span><span class="n">' + (p.n || 0) + "</span></button>";
      }).join("");
      // "Escolher contas": nada aparece aqui; clicar na linha abre o pop-up, e e la que se adiciona ou tira.
      esq += "</div>";
    } else if (passo === 2) {
      esq += '<div class="painel camp-card"><div class="painel-cab camp-cab"><span class="rotulo">Conteúdo</span></div>' + campoTexto("camp-nome", "Nome da campanha (interno)", camp.nome, "Lembrete OAB · outubro", "camp.nome") +
        campoTexto("camp-assunto", "Assunto", camp.assunto, "Um presente para o {escritorio}", "camp.assunto") +
        campoTexto("camp-pre", "Pré-cabeçalho", camp.pre, "o texto cinza que aparece ao lado do assunto", "camp.pre") +
        campoTexto("camp-titulo", "Título", camp.titulo, "Desconto no plano {plano}", "camp.titulo") +
        '<label class="campo-adm"><span class="rot">Texto</span><textarea class="area" id="camp-texto" rows="6" data-in="campo" data-campo="camp.texto" placeholder="Olá, {nome}.">' + esc(camp.texto) + "</textarea></label>" +
        '<div class="grade-campos">' + campoTexto("camp-botao", "Texto do botão", camp.botao, "", "camp.botao") + linkBotaoCampo(camp) + "</div>" +
        '<span class="nota-campo">Campos: {nome}, {escritorio}, {plano}, {vence_em}</span></div>';
    } else {
      var de = (d.envio && d.envio.de) || "naoresponda@paulus.ia.br", ritmo = Number(d.envio && d.envio.ritmo) || 50;
      esq += '<div class="painel camp-card"><div class="painel-cab camp-cab"><span class="rotulo">Revisar</span></div><dl class="fatos-p f110">' + fato("Público", pub ? pub.label + " · " + n : "—") + fato("Assunto", trocaCampos(camp.assunto) || "(sem assunto)") + fato("De", "PAVLVS <" + de + ">") +
        fato("Botão", (camp.botao || "—") + " → " + (camp.link || "—")) + fato("Ritmo", ritmo + " por minuto · " + Math.max(1, Math.ceil(n / ritmo)) + " min") + "</dl>" +
        '<div class="camp-quando"><span class="rot-campo">Quando</span><div class="quando-dir">' + seg("emails.quando", [["agora", "Agora"]], camp.quando === "agendado" ? "" : "agora") +
        '<div class="segmentos"><div role="group"><button type="button" class="seg-cal" data-a="campAgendar" aria-pressed="' + (camp.quando === "agendado") + '" aria-expanded="' + !!camp.cal + '">' + ic("calendar_month") + "<span>" + (camp.quando === "agendado" && camp.de ? esc(ddmm(camp.de) + " · " + camp.hora) : "Agendar") + "</span></button></div></div>" +
        (camp.cal ? calHtml(camp.cal) : "") + "</div>" +
        '</div><div class="camp-pe">' +
        '<button type="button" class="mini" data-a="enviarTeste"' + attrDis(envioOff, envio.falta) + ">" + ic("mail") + "Mandar um teste para mim</button></div></div>";
    }
    esq += '<div class="passo-pe">' + (passo > 1 ? "" : "<span></span>") +
      (passo > 1 ? '<button type="button" class="btn-texto-mudo passo-voltar" data-a="passo" data-n="' + (passo - 1) + '">' + ic("arrow_back") + "Voltar</button>" : "") +
      (passo === 3 ? '<button type="button" class="btn-duplo" data-a="pedirDisparo"' + attrDis(envioOff || !n, envioOff ? envio.falta : "público vazio") + "><span>" + ic("send") + "Disparar</span></button>" : "") +
      (passo < 3 ? '<button type="button" class="mini cheia h32" data-a="passo" data-n="' + (passo + 1) + '">Avançar para ' + (passo === 1 ? "Conteúdo" : "Revisar") + ic("arrow_forward") + "</button>" : "") + "</div></div>";
    var so = U.emails.so, unico = so && pub && pub.id === "conta:" + so.id;
    var dir = '<div class="painel">' + painelCab("Prévia", esc("para " + (unico ? so.email : pub ? pub.label : "—"))) +
      '<div class="previa-cab"><b>' + (trocaCampos(camp.assunto, true) || "Assunto do e-mail") + "</b><span>" + (trocaCampos(camp.pre, true) || "pré-cabeçalho") + "</span></div>" +
      '<div class="previa-corpo"><span class="marca-e">PAVLVS</span><h2>' + (trocaCampos(camp.titulo, true) || "Título do e-mail") + "</h2>" +
      "<p>" + (trocaCampos(camp.texto, true) || "O texto que você escrever em Conteúdo aparece aqui" + (unico ? ", com os campos preenchidos para " + esc(primeiro(so.nome)) : "") + ".") + "</p>" +
      '<span class="btn-duplo inicio" aria-hidden="true"><span>' + esc(camp.botao || "Botão") + "</span></span>" +
      '<span class="pe">PAVLVS · ' + esc((d.envio && d.envio.de) || "naoresponda@paulus.ia.br") + " · Este e-mail é automático e não recebe respostas. Dúvidas ou para não receber mais avisos: contato@paulus.ia.br</span></div></div>";
    return h + '<div class="duas-col">' + esq + dir + "</div>";
  };
  function campoTexto(id, rot, val, ph, campo, extra) {
    return '<label class="campo-adm"><span class="rot">' + esc(rot) + '</span><span class="caixa-campo' + (extra || "") + '"><input id="' + id + '" data-in="campo" data-campo="' + campo + '" value="' + esc(val) + '" placeholder="' + esc(ph) + '" spellcheck="false"></span></label>';
  }

  function campoNum(id, rot, val, campo, pre, suf) {
    return '<label class="campo-adm"><span class="rot">' + esc(rot) + '</span><span class="caixa-campo mono">' + (pre ? '<span class="pre">' + pre + "</span>" : "") +
      '<input id="' + id + '" data-in="campo" data-campo="' + campo + '" value="' + esc(val) + '" inputmode="decimal" style="width:0">' + (suf ? '<span class="sufixo">' + suf + "</span>" : "") + "</span></label>";
  }
  /* ---------- 8. Tokens, custos e receita ---------- */
  TELAS_RENDER.tokens = function () {
    var h = cab("Tokens, custos e receita", "Entrada e saída medidas no portão (ContaIA), custo pelo preço do DeepInfra por milhão, receita pelo que o Mercado Pago confirmou.");
    var ch = tokensChave(), d = dadosDe(ch), ano = String(new Date().getFullYear());
    var pr = d && d.precos;
    h += '<div class="barra-filtros">' + seg("tokens.visao", [["geral", "Geral"], ["modelo", "Por modelo"], ["escritorio", "Por escritório"], ["conta", "Por conta"]], U.tokens.visao) +
      seg("tokens.periodo", [["mes", "Este mês"], ["30", "30 dias"], ["90", "90 dias"]], U.tokens.periodo).replace(/<\/div><\/div>$/, "") +
      '<button type="button" class="seg-cal" data-a="tokCal" aria-pressed="' + (U.tokens.periodo === "custom") + '" aria-expanded="' + !!U.tokens.cal + '">' + ic("calendar_month") + "<span>" + (U.tokens.periodo === "custom" ? esc(ddmm(U.tokens.de) + " – " + ddmm(U.tokens.ate)) : "Outro período") + "</span></button></div></div>" +
      (U.tokens.cal ? calHtml(U.tokens.cal) : "") +
      (pr ? '<span class="mono-dir">DeepInfra · entrada ' + esc(usd(pr.entrada)) + "/M · saída " + esc(usd(pr.saida)) + "/M · câmbio " + esc(cambioTxt(pr.cambio)) + "</span>" : "") + "</div>";
    h += falta(cfg("nuvem"));
    var est = estadoLeitura([ch], "tokens"); if (est) return h + est;
    h += erroRecente(ch, "tokens");
    var k = d.kpis || {}, cambio = Number(pr && pr.cambio) || 0;
    var custoR = (Number(k.custo_usd) || 0) * cambio, rec = Number(k.receita) || 0, nc = Number(k.contas) || 0, mg = rec > 0 ? 1 - custoR / rec : null;
    h += '<dl class="kpis k160">' + kpi("Entrada", tok(k.entrada), "prompt_tokens") + kpi("Saída", tok(k.saida), "completion_tokens") +
      kpi("Custo", brl(custoR), usd(k.custo_usd) + " · câmbio " + cambioTxt(cambio)) + kpi("Arrecadado", brl(rec), "assinaturas + Pix") +
      kpi("Margem", mg == null ? "—" : pct(mg), brl(rec - custoR) + " líquido", mg == null ? "" : mg >= 0 ? "var(--ok)" : "var(--erro)") +
      kpi("Custo por conta", nc ? brl(custoR / nc) : "—", nc ? "média · " + brl(rec / nc) + " arrecadado" : "sem contas") + "</dl>";
    var ls = (d.linhas || []).slice().sort(function (a, b) { return ((b.entrada || 0) + (b.saida || 0)) - ((a.entrada || 0) + (a.saida || 0)); });
    var max = ls.reduce(function (m, l) { return Math.max(m, (l.entrada || 0) + (l.saida || 0)); }, 0) || 1;
    var cols = "minmax(160px,1fr) 80px 80px 96px 96px 70px";
    var linhas = ls.map(function (l) {
      var cu = (Number(l.custo_usd) || 0) * cambio, r = Number(l.receita) || 0, m = r > 0 ? 1 - cu / r : null;
      var cor = m == null ? "var(--ink3)" : m >= 0.4 ? "var(--ok)" : m >= 0 ? "var(--atencao)" : "var(--erro)";
      var ST = U.tokens.sel, mt = !!(ST && ST[l.nome]);
      return '<div class="grade-linha p10' + (mt ? " marcada" : "") + '" data-ksel="' + esc(l.nome) + '"' + (ST ? ' aria-selected="' + mt + '"' : "") + '><span class="cel-nome" style="gap:3px"><b class="corta" style="font-size:13px">' + esc(l.nome) + "</b>" + (l.sub ? '<small class="corta tok-sub">' + esc(l.sub) + "</small>" : "") + (l.preco ? '<small class="corta tok-sub">' + esc(usd(l.preco[0]) + " entrada · " + usd(l.preco[1]) + " saída, por milhão") + "</small>" : "") + '<span class="uso" style="height:3px;max-width:220px"><i style="width:' + Math.round(((l.entrada || 0) + (l.saida || 0)) / max * 100) + '%"></i></span></span>' +
        '<span class="num dir c-ink2">' + esc(tok(l.entrada)) + '</span><span class="num dir c-ink2">' + esc(tok(l.saida)) + '</span><span class="num dir" title="' + esc(usd(l.custo_usd)) + '">' + esc(brl(cu)) + '</span><span class="num dir">' + esc(brl(r)) + '</span><span class="num dir" style="color:' + cor + '">' + (m == null ? "—" : pct(m)) + "</span></div>";
    }).join("") || '<p class="vazio-linha">Nada medido neste período.</p>';
    var col = { geral: "Origem", modelo: "Modelo", escritorio: "Escritório", conta: "Conta" }[U.tokens.visao];
    // Segurar o clique numa linha seleciona varias; a barra mostra a soma das selecionadas.
    var ST = U.tokens.sel, selL = ST ? ls.filter(function (l) { return ST[l.nome]; }) : [], nT = selL.length, tudoK = nT && nT >= ls.length;
    var soma = function (k) { return selL.reduce(function (s, l) { return s + (Number(l[k]) || 0); }, 0); };
    var selK = ST ? '<div class="painel-cab sel-cab"><button type="button" class="caixinha tri' + (tudoK ? " cheia" : nT ? " parcial" : "") + '" role="checkbox" aria-checked="' + (tudoK ? "true" : nT ? "mixed" : "false") + '" data-a="' + (nT ? "tokSelSair" : "tokSelTodas") + '" aria-label="' + (nT ? "Limpar a seleção" : "Selecionar todas") + '">' + (tudoK ? ic("check") : nT ? ic("remove") : "") + "</button>" +
      "<b>" + nT + (nT === 1 ? " selecionada" : " selecionadas") + '</b><span class="sel-div"></span><span class="sel-soma">' + esc(tok(soma("entrada") + soma("saida"))) + " tokens · custo " + esc(brl(soma("custo_usd") * cambio)) + " · arrecadado " + esc(brl(soma("receita"))) + "</span></div>" : "";
    h += '<div class="painel' + (ST ? " selecionando" : "") + '">' + selK + grade(cols, 700, "<span>" + col + '</span><span class="dir">Entrada</span><span class="dir">Saída</span><span class="dir">Custo</span><span class="dir">Arrecadado</span><span class="dir">Margem</span>', linhas) + "</div>";
    return h;
  };

  /* ---------- 9. Planos ---------- */
  function precosPlanos() { var d = dadosDe("tokens:geral:mes"); return d && d.precos ? d.precos : null; }
  // Se o assinante usar o pacote inteiro: a proporcao entrada/saida e uma
  // estimativa (72/28, a do desenho); o preco e o cambio vem da API.
  // O preco e o do modelo do plano (custo_modelo, [entrada, saida] em dolar); sem ele, o IA_PRECOS.
  function custoCheio(tokens, usd) {
    var p = precosPlanos(); if (!p) return null;
    var ok = Array.isArray(usd) && isFinite(usd[0]) && isFinite(usd[1]);
    var e = ok ? Number(usd[0]) : Number(p.entrada), s = ok ? Number(usd[1]) : Number(p.saida);
    return (tokens * 0.72 / 1e6 * e + tokens * 0.28 / 1e6 * s) * p.cambio;
  }
  function planoPadraoUsd() { var d = dadosDe("planos") || {}; var p = (d.planos || []).filter(function (x) { return x.id === d.padrao; })[0]; return p ? p.custo_modelo : null; }
  // O IA_PLANOS inteiro (precos, creditos, recursos e os textos da pagina de assinatura), num campo ja preenchido:
  // edita aqui ou baixa o .json, edita fora e carrega de volta. Salvar valida e manda para a fila.
  var CAMPOS_PLANO = ["id", "nome", "para", "valor", "valor_anual", "tokens", "pessoas", "modelos", "recarga", "recursos", "heranca", "itens"];
  function planosAtuais(ps) { return JSON.stringify(ps.map(function (p) { var o = {}; CAMPOS_PLANO.forEach(function (k) { if (p[k] !== undefined) o[k] = p[k]; }); return o; }), null, 2); }
  function validaPlanos(t) {
    var v; try { v = JSON.parse(t); } catch (e) { return "JSON inválido: " + e.message; }
    if (!Array.isArray(v) || !v.length) return "Precisa ser uma lista de planos: [ { … }, … ]";
    for (var i = 0; i < v.length; i++) {
      var p = v[i], n = "Plano " + (i + 1) + (p && p.nome ? " (" + p.nome + ")" : "");
      if (!p || typeof p !== "object") return n + ": não é um objeto";
      if (!/^[a-z0-9-]{2,24}$/.test(p.id || "")) return n + ": id precisa ter 2 a 24 letras minúsculas, números e hífen";
      if (!p.nome) return n + ": falta o nome";
      if (!(p.valor > 0) || !(p.valor_anual > 0)) return n + ": valor e valor_anual precisam ser números maiores que zero";
      if (!(p.tokens > 0)) return n + ": tokens precisa ser um número maior que zero";
      if (p.itens && (!Array.isArray(p.itens) || p.itens.some(function (it) { return !it || !it.titulo; }))) return n + ": cada item precisa de titulo (e, se quiser, descricao)";
    }
    var ids = v.map(function (p) { return p.id; }); if (ids.some(function (x, k) { return ids.indexOf(x) !== k; })) return "Há dois planos com o mesmo id";
    return null;
  }
  function planosJsonHtml(ps, podeE) {
    var atual = planosAtuais(ps), t = U.planos.json != null ? U.planos.json : atual, mudou = t !== atual, erro = mudou ? validaPlanos(t) : null, fila = naFila("planos.json", "IA_PLANOS");
    return '<div class="painel"><div class="painel-cab secao-cab"><span class="rotulo">IA_PLANOS</span><span class="par">' +
      '<button type="button" class="mini" data-a="planosBaixar">' + ic("download") + "Baixar .json</button>" +
      (podeE ? '<label class="mini">' + ic("upload") + 'Carregar arquivo<input type="file" accept=".json,application/json" data-in="planosArquivo" hidden></label>' : "") +
      '<button type="button" class="btn-icone" data-a="copiarJson" aria-label="Copiar JSON" title="Copiar JSON">' + ic("content_copy") + "</button></span></div>" +
      '<textarea id="planos-json" class="json json-edit" spellcheck="false" data-in="planosJson"' + (podeE && !fila ? "" : " readonly") + ">" + esc(t) + "</textarea>" +
      (podeE ? '<div class="res-acoes json-pe"><span id="planos-json-st" class="nota-campo' + (erro ? " c-erro" : "") + '">' + esc(fila ? "Há uma alteração do IA_PLANOS na fila." : erro || (mudou ? "Alterado. Quem já assina fica no plano de agora até a próxima renovação." : "Igual ao que está no ar.")) + "</span>" +
        '<span class="par"><button type="button" class="btn-texto-mudo s12" data-a="planosRestaurar"' + (mudou ? "" : " disabled") + ">Desfazer</button>" +
        '<button type="button" class="mini cheia" id="planos-salvar" data-a="planosSalvarJson"' + (mudou && !erro && !fila ? "" : " disabled") + ">Salvar</button></span></div>" : "") + "</div>";
  }
  // Historico do IA_PLANOS: cada versao salva, com quem, quando e o que mudou. Abrir mostra o JSON daquela versao;
  // "Usar esta versao" leva o JSON para a guia .JSON, onde ainda e preciso salvar.
  function planosHistHtml(d, ps, podeE) {
    var vs = (d.versoes || []).slice().sort(function (a, b) { return b.n - a.n; }), ab = U.planos.versao;
    if (!vs.length) return '<div class="painel"><p class="vazio">Ainda não há versões salvas.</p></div>';
    return '<div class="painel"><div class="painel-cab"><span class="rotulo">Versões do IA_PLANOS</span><span class="c-mute s12">' + vs.length + (vs.length === 1 ? " versão" : " versões") + "</span></div>" +
      vs.map(function (v, k) {
        var aberta = String(ab) === String(v.n);
        return '<div class="grade-linha p10 clicavel hist-v' + (aberta ? " aberta" : "") + '" data-a="planoVersao" data-n="' + v.n + '" role="button" tabindex="0" aria-expanded="' + aberta + '">' +
          '<span class="mono c-mute s12">v' + v.n + "</span>" +
          '<span class="cel-nome"><b class="corta">' + esc(v.resumo) + '</b><small class="corta">' + esc(v.quem) + "</small></span>" +
          '<span class="c-ink2 s12 hist-q">' + esc(ddmmaaaa(v.quando) + " " + hm(dt(v.quando))) + "</span>" +
          (k === 0 ? '<span class="hist-ar">no ar</span>' : "<span></span>") + "</div>" +
          (aberta ? '<div class="hist-det"><pre class="json">' + esc(JSON.stringify(v.planos, null, 2)) + "</pre>" +
            (k > 0 && podeE ? '<div class="res-acoes json-pe"><span class="nota-campo">Vai para a guia .JSON; nada muda até você salvar.</span><button type="button" class="mini cheia" data-a="planoUsarVersao" data-n="' + v.n + '">' + ic("history") + "Usar esta versão</button></div>" : "") + "</div>" : "");
      }).join("") + "</div>";
  }
  function planosStatus() {
    var ps = (dadosDe("planos") || {}).planos || [], atual = planosAtuais(ps), t = U.planos.json, mudou = t != null && t !== atual, erro = mudou ? validaPlanos(t) : null;
    var st = $("planos-json-st"), b = $("planos-salvar"), r = document.querySelector('[data-a="planosRestaurar"]');
    if (st) { st.textContent = erro || (mudou ? "Alterado. Quem já assina fica no plano de agora até a próxima renovação." : "Igual ao que está no ar."); st.classList.toggle("c-erro", !!erro); }
    if (b) b.disabled = !mudou || !!erro; if (r) r.disabled = !mudou;
  }
  TELAS_RENDER.planos = function () {
    var h = cab("Planos de assinatura", "Preços, créditos e os textos que aparecem na página de assinatura. Uma mudança vale para quem assinar depois; quem já assina só passa ao novo valor na renovação.");
    var est = estadoLeitura(["planos"], "planos"); if (est) return h + est;
    h += erroRecente("planos", "planos");
    var d = dadosDe("planos"), ps = d.planos || [], podeE = pode("plano.editar"), podeC = pode("plano.criar");
    // Um card por plano, com cada numero rotulado: quanto custa, o que inclui, quem assina e quanto sobra.
    // Uma guia (pilula) por plano: so o plano escolhido aparece.
    var abaP = ps.some(function (p) { return p.id === U.planos.aba; }) ? U.planos.aba : (ps[0] && ps[0].id);
    var abasPlano = ps.length > 1 ? seg("planos.aba", ps.map(function (p) { return [p.id, p.nome]; }), abaP) : "";
    var esq = '<div class="pilha g24">' +
      ps.filter(function (p) { return p.id === abaP; }).map(function (p) {
      var fila = naFila("plano.editar", p.id), cc = custoCheio(p.tokens, p.custo_modelo);
      if (cc != null && !isFinite(cc)) cc = null;
      var mg = cc != null && p.valor ? 1 - cc / p.valor : null;
      var econ = p.valor_anual && p.valor ? 1 - p.valor_anual / (p.valor * 12) : null;
      return '<div class="painel res-card"><div class="painel-cab secao-cab"><span class="rotulo">' + esc(p.nome) + (p.id === d.padrao ? ' <em class="plano-padrao">padrão</em>' : "") + "</span>" +
        (podeE ? '<button type="button" class="btn-icone icone-secao" data-a="planoIrEdicao" data-id="' + esc(p.id) + '" aria-label="Editar plano ' + esc(p.nome) + '" title="Editar"' + attrDis(fila, "já está na fila de alterações") + ">" + ic("edit") + "</button>" : "") + "</div>" +
        '<dl class="res-grade c3">' +
        '<div><dt>Por mês</dt><dd class="plano-grande">' + esc(brl(p.valor)) + "</dd></div>" +
        '<div><dt>Por ano</dt><dd>' + (p.valor_anual ? esc(brl(p.valor_anual)) + (econ > 0 ? '<small class="plano-nota">' + Math.round(econ * 100) + "% de desconto</small>" : "") : "sem plano anual") + "</dd></div>" +
        fato("Assinantes", String(p.assinantes || 0)) +
        fato("Créditos por mês", tok(p.tokens) + " tokens") + fato("Pessoas", String(p.pessoas || 1)) + fato("Modelo", p.modelo_nome || "—") +
        '<div><dt>Preço por milhão</dt><dd>' + esc(brl(p.valor / (p.tokens / 1e6))) + "</dd></div>" +
        '<div><dt>Se usar tudo, custa</dt><dd>' + (cc != null ? esc(brl(cc)) + '<small class="plano-nota" style="color:' + (mg >= 0.4 ? "var(--ok)" : "var(--erro)") + '">margem mínima de ' + Math.round(mg * 100) + "%</small>" : '<span class="c-mute">' + (D["tokens:geral:mes"] && D["tokens:geral:mes"].carregando ? "carregando preços…" : "sem os preços do provedor") + "</span>") + "</dd></div>" +
        '<div><dt>Recarga (Pix)</dt><dd>' + (p.recarga ? esc(brl(p.recarga.valor)) + '<small class="plano-nota">' + esc(tok(p.recarga.tokens)) + " tokens</small>" : "—") + "</dd></div></dl>" +
        ((p.itens || []).length ? '<div class="plano-pag"><span class="td-tit">Na página de assinatura</span>' + (p.para ? '<p class="plano-para">' + esc(p.para) + (p.heranca ? " " + esc(p.heranca) + ":" : "") + "</p>" : "") +
          '<ul class="plano-itens">' + p.itens.map(function (it) { return "<li><b>" + esc(it.titulo) + "</b><span>" + esc(it.descricao || "") + "</span></li>"; }).join("") + "</ul></div>" : "") + "</div>";
    }).join("") +
      "</div>";
    // A coluna da direita edita o plano da guia escolhida: numeros, frase, heranca e os itens da pagina de assinatura.
    var dir, pe = ps.filter(function (p) { return p.id === abaP; })[0];
    var lado = ["json", "edicao", "historico"].indexOf(U.planos.lado) >= 0 ? U.planos.lado : "resumo";
    if (lado === "json") {
      dir = planosJsonHtml(ps, podeE);
    } else if (podeE && pe) {
      var ed = planoEd(pe), v = ed.v, filaE = naFila("plano.editar", pe.id);
      var vv = numDec(v.valor), tt = numDec(v.tokens) * 1e6, cc2 = tt ? custoCheio(tt, pe.custo_modelo) : null, mg2 = cc2 != null && vv ? 1 - cc2 / vv : null;
      var cE = function (k, rot, pre, suf) { return '<label class="campo-adm"><span class="rot">' + esc(rot) + '</span><span class="caixa-campo mono fundo">' + (pre ? '<span class="pre">' + pre + "</span>" : "") + '<input data-in="planoEd" data-k="' + k + '" value="' + esc(v[k]) + '" inputmode="decimal" style="width:0">' + (suf ? '<span class="sufixo">' + suf + "</span>" : "") + "</span></label>"; };
      var cT = function (k, rot, ph) { return '<label class="campo-adm"><span class="rot">' + esc(rot) + '</span><span class="caixa-campo fundo"><input data-in="planoEd" data-k="' + k + '" value="' + esc(v[k]) + '" placeholder="' + esc(ph || "") + '"></span></label>'; };
      dir = '<div class="painel res-card"><div class="painel-cab secao-cab"><span class="rotulo">Editar ' + esc(pe.nome) + '</span></div><div class="ed-corpo">' +
        cT("para", "Frase do plano", "Para quem advoga sozinho.") +
        '<div class="grade-campos">' + cE("valor", "Valor por mês", "R$") + cE("anual", "Valor por ano", "R$") + "</div>" +
        '<div class="grade-campos">' + cE("tokens", "Créditos por mês", "", "M") + cE("pessoas", "Pessoas", "") + "</div>" +
        '<div class="grade-campos">' + cE("rv", "Recarga (Pix)", "R$") + cE("rt", "Tokens da recarga", "", "M") + "</div>" +
        cT("heranca", "Antes dos itens", "Tudo do plano Advogado, e mais") +
        '<div class="conta-rapida"><span class="rotulo">Conta rápida</span><span>' + (tt ? esc(brl(vv / (tt / 1e6))) + " por milhão de tokens" : "Preencha valor e créditos.") + "</span>" +
        (cc2 != null ? '<span style="color:' + (mg2 >= 0.4 ? "var(--ok)" : "var(--erro)") + '">Se o assinante usar tudo, custa ' + esc(brl(cc2)) + ": margem mínima de " + Math.round(mg2 * 100) + "%.</span>" : "") + "</div>" +
        '<div class="secao-cab"><span class="rotulo">Itens na página de assinatura</span><button type="button" class="btn-texto-mudo s12" data-a="planoEdItemMais">' + ic("add") + "Item</button></div>" +
        '<div class="ed-itens">' + ed.itens.map(function (it, k) {
          return '<div class="ed-item"><div class="ed-item-cab"><span class="mono c-mute s12">' + (k + 1) + '</span><span class="par">' +
            '<button type="button" class="btn-icone" data-a="planoEdItemMover" data-i="' + k + '" data-d="-1" aria-label="Subir"' + (k ? "" : " disabled") + ">" + ic("arrow_upward") + "</button>" +
            '<button type="button" class="btn-icone" data-a="planoEdItemMover" data-i="' + k + '" data-d="1" aria-label="Descer"' + (k < ed.itens.length - 1 ? "" : " disabled") + ">" + ic("arrow_downward") + "</button>" +
            '<button type="button" class="btn-icone" data-a="planoEdItemTirar" data-i="' + k + '" aria-label="Tirar o item">' + ic("close") + "</button></span></div>" +
            '<span class="caixa-campo fundo"><input data-in="planoEdItem" data-i="' + k + '" data-k="titulo" value="' + esc(it.titulo) + '" placeholder="Título"></span>' +
            '<textarea class="area fundo" rows="2" data-in="planoEdItem" data-i="' + k + '" data-k="descricao" placeholder="Descrição">' + esc(it.descricao || "") + "</textarea></div>";
        }).join("") + "</div>" +
        '<span class="nota-campo">Quem já assina fica no valor de agora; o novo só entra na próxima renovação.</span>' +
        '<div class="par" style="justify-content:flex-end"><button type="button" class="btn-texto-mudo s12" data-a="planoEdDesfazer">Desfazer</button>' +
        '<button type="button" class="btn-duplo" data-a="planoEdSalvar"' + attrDis(filaE, "já está na fila de alterações") + "><span>Salvar " + esc(pe.nome) + "</span></button></div></div></div>";
    } else {
      dir = '<p class="nota-pe">O papel ' + esc(PAPEL_NOME[E.sessao.papel] || E.sessao.papel) + " vê os planos, mas não edita.</p>";
    }
    // Uma experiencia so: o plano a esquerda, o que ver dele a direita, e um card embaixo.
    return h + '<div class="pilha g24"><div class="plano-topo">' + abasPlano + seg("planos.lado", [["resumo", "Resumo"], ["edicao", "Edição"], ["json", ".JSON"], ["historico", "Histórico"]], lado) + "</div>" +
      (lado === "resumo" ? esq : lado === "historico" ? planosHistHtml(d, ps, podeE) : dir) + "</div>";
  };

  /* ---------- 10. Moderar materiais ---------- */
  var SIT_MAT = { fila: ["na fila", "var(--atencao)"], ajustes: ["aguardando autor", "var(--ink2)"], publicado: ["publicado", "var(--ok)"], recusado: ["recusado", "var(--erro)"] };
  var TIPO_MAT = { artigo: "Artigo", modelo: "Modelo", tabela: "Tabela" };
  var CHK = [["dados", "não tem nome, CPF, CNPJ ou número de processo de cliente"], ["autor", "o autor é quem diz ser (OAB confere com o cadastro)"], ["licenca", "o texto cabe na licença aberta escolhida"], ["tom", "é material entre advogados, não consultoria a leigo nem propaganda"]];
  function areasTxt(a) { return Array.isArray(a) ? a.join(", ") : String(a || ""); }
  function contagem(v) { return Array.isArray(v) ? v.length : Number(v) || 0; }
  // O "# titulo" do comeco do .md repete o titulo que ja esta em cima: sai.
  function mdParaHtml(t, titulo) {
    return String(t || "").replace(/\r/g, "").split(/\n{2,}/).map(function (b, i) {
      b = b.trim(); if (!b) return "";
      if (i === 0 && /^#\s/.test(b) && norm(titulo).indexOf(norm(b.replace(/^#\s+/, ""))) === 0) return "";
      if (/^\|/.test(b) || /^ {4}|^```/.test(b)) return "<pre>" + esc(b.replace(/^```\w*\n?|```$/g, "")) + "</pre>";
      if (/^#{1,6}\s/.test(b)) return "<h3>" + esc(b.replace(/^#{1,6}\s+/, "")) + "</h3>";
      return "<p>" + esc(b.replace(/\n/g, " ")) + "</p>";
    }).join("");
  }
  TELAS_RENDER.materiais = function () {
    var h = cab("Materiais entre advogados", "O que os advogados mandam pela aba Da comunidade da Biblioteca chega aqui. Cada texto é lido antes de entrar em paulus.ia.br/materiais: sem dado de cliente, com autor e licença aberta.");
    var d = dadosDe("materiais"), ms = d ? d.materiais || [] : [];
    h += '<div class="barra-filtros">' + seg("materiais.filtro", [["fila", "Na fila"], ["ajustes", "Com o autor"], ["publicado", "Publicados"], ["recusado", "Recusados"], ["todos", "Todos"]], U.materiais.filtro) +
      (d ? '<span class="mono-dir">' + ms.filter(function (m) { return m.situacao === "fila"; }).length + " na fila · " + ms.filter(function (m) { return m.situacao === "publicado"; }).length + " no ar</span>" : "") + "</div>";
    var est = estadoLeitura(["materiais"], "materiais"); if (est) return h + est;
    h += erroRecente("materiais", "materiais");
    var f = U.materiais.filtro, lista = ms.filter(function (m) { return f === "todos" || m.situacao === f; });
    var cols = "72px minmax(200px,1fr) 150px 110px 96px";
    var linhas = lista.map(function (m) {
      var s = SIT_MAT[m.situacao] || [m.situacao, "var(--ink3)"], on = U.materiais.aberto === m.id;
      return '<div class="grade-linha clicavel' + (on ? " sel" : "") + '" role="button" tabindex="0" aria-expanded="' + on + '" data-a="materialAbrir" data-id="' + esc(m.id) + '">' +
        '<span class="rotulo" style="letter-spacing:.14em">' + esc(TIPO_MAT[m.tipo] || m.tipo) + "</span>" +
        '<span class="cel-nome"><b class="corta">' + esc(m.titulo) + '</b><small class="sans corta">' + esc(areasTxt(m.areas)) + " · " + esc(m.licenca) + "</small></span>" +
        '<span class="cel-nome"><span class="t125 corta">' + esc(m.autor) + '</span><small class="c-ink3" style="font-size:11px">OAB ' + esc(m.oab) + "</small></span>" +
        '<span class="num c-ink3">' + esc(rel(m.enviado)) + "</span>" + sit(s[0], s[1]) + "</div>";
    }).join("") || '<p class="vazio-linha">Nenhum material com esse filtro.</p>';
    h += '<div class="painel">' + grade(cols, 680, "<span>Tipo</span><span>Material</span><span>Autor</span><span>Enviado</span><span>Situação</span>", linhas) + "</div>";
    var m = ms.filter(function (x) { return x.id === U.materiais.aberto; })[0];
    if (!m) return h;
    var ch = U.materiais.checks[m.id] || {}, ok = CHK.every(function (c) { return ch[c[0]]; });
    var vr = m.varredura || {}, itens = [["CPF", contagem(vr.cpf)], ["CNPJ", contagem(vr.cnpj)], ["Número de processo", contagem(vr.processo)], ["Nome próprio fora da autoria", contagem(vr.nomes)]];
    var achados = itens.reduce(function (s, x) { return s + x[1]; }, 0);
    var fila = naFila("material.situacao", m.id), pub = m.situacao === "publicado";
    var leitura = '<div class="painel"><div class="painel-cab"><span class="rotulo">Leitura</span><span class="cab-dir corta">/materiais/' + esc(m.slug) + ".md · " + (m.palavras || 0) + " palavras</span></div>" +
      '<div class="leitura" tabindex="0" aria-label="Texto do material"><span class="rotulo" style="letter-spacing:.14em">' + esc(TIPO_MAT[m.tipo] || m.tipo) + " · " + esc(areasTxt(m.areas)) + "</span><h2>" + esc(m.titulo) + '</h2><span class="autor">' + esc(m.autor) + " · OAB " + esc(m.oab) + " · " + esc(m.licenca) + "</span>" +
      (m.texto ? mdParaHtml(m.texto, m.titulo) : "<p>" + esc(m.resumo || "Sem texto.") + "</p>") + "</div></div>";
    var lado = '<div class="pilha g20"><div class="painel">' + painelCab("Leitura automática", achados ? achados + " para conferir" : "limpo", achados ? "c-erro" : "c-ok") +
      itens.map(function (x) { return '<div class="varre">' + ic(x[1] ? "warning" : "check", x[1] ? "c-erro" : "c-ok") + "<span>" + esc(x[0]) + '</span><span class="num s11" style="color:' + (x[1] ? "var(--erro)" : "var(--ok)") + '">' + (x[1] ? x[1] + (x[1] > 1 ? " achados" : " achado") : "nenhum") + "</span></div>"; }).join("") + "</div>" +
      '<div class="painel">' + painelCab("Conferi que") + CHK.map(function (c) {
        var on = !!ch[c[0]];
        return '<button type="button" class="linha-btn check-linha" role="checkbox" aria-checked="' + on + '" data-a="materialCheck" data-k="' + c[0] + '"><span class="caixinha g16" aria-checked="' + on + '">' + (on ? ic("check") : "") + "</span><span>" + esc(c[1]) + "</span></button>";
      }).join("") + "</div>" +
      '<label class="campo-adm"><span class="rot">Recado ao autor (vai no e-mail)</span><textarea class="area" id="material-recado" rows="3" data-in="recado" style="font-size:13.5px" placeholder="ex. no 3º parágrafo há um número de processo; troque por [processo] e mande de novo">' + esc(U.materiais.recados[m.id] || "") + "</textarea></label>" +
      '<div class="acoes-linha">' +
      '<button type="button" class="btn-duplo pequeno verde" data-a="materialSit" data-v="publicado"' + attrDis(fila || pub || !ok, fila ? "já está na fila de alterações" : pub ? "já publicado" : "confira os quatro itens") + "><span>" + ic("check") + (pub ? "Publicado" : "Aprovar e publicar") + "</span></button>" +
      '<button type="button" class="mini cheia" data-a="materialSit" data-v="ajustes"' + attrDis(fila, "já está na fila de alterações") + ">" + ic("mail") + "Pedir ajustes</button>" +
      '<button type="button" class="mini vermelho" data-a="materialSit" data-v="recusado"' + attrDis(fila || m.situacao === "recusado", fila ? "já está na fila de alterações" : "já recusado") + ">Recusar</button>" +
      (pub ? '<button type="button" class="mini" style="margin-left:auto" data-a="materialSit" data-v="tirar"' + attrDis(fila, "já está na fila de alterações") + ">Tirar do ar</button>" : "") + "</div>" +
      '<span class="nota-campo">' + (fila ? "Este material já tem uma decisão na fila de alterações. " : "") + "Publicar grava o .md em site/materiais, o sha256 em dados/materiais.json e avisa o autor. Os quatro itens precisam estar conferidos.</span></div>";
    return h + '<div class="duas-col">' + leitura + lado + "</div>";
  };

  /* ---------- 11. Notas fiscais ---------- */
  // O emissor de NFS-e da nuvem (worker/nfse/api.js) em /api/admin/nfse/emissor/*:
  // emitir, cancelar, substituir, certificado e parâmetros valem na hora (sem a
  // fila); só os três interruptores passam pela fila de alterações.
  var NF = "/api/admin/nfse/emissor/";
  var NF_MESES = ["janeiro", "fevereiro", "março", "abril", "maio", "junho", "julho", "agosto", "setembro", "outubro", "novembro", "dezembro"];
  var NF_SIT = {
    emitida: "var(--ok)", rejeitada: "var(--erro)", na_fila: "var(--atencao)", aguardando_confirmacao: "var(--atencao)", enviando: "var(--atencao)",
    assinada: "var(--atencao)", rascunho: "var(--ink3)", cancelada: "var(--ink3)", substituida: "var(--ink3)", descartada: "var(--ink3)",
  };
  var NF_TOMADOR = [["nome", "Nome ou razão social"], ["documento", "CPF ou CNPJ"], ["email", "E-mail"], ["telefone", "Telefone"], ["cep", "CEP"],
    ["logradouro", "Rua"], ["numero", "Número"], ["complemento", "Complemento"], ["bairro", "Bairro"], ["cmun", "Município"],
    ["uf", "UF"], ["inscricao_municipal", "Inscrição municipal (se houver)"]];
  function podeNf() { var d = dadosDe("nfse"); return !!(d && d.pode ? d.pode.emitir : E.sessao && DF.indexOf(E.sessao.papel) >= 0); }
  function nfCompetencia(c) { var m = /^(\d{4})-(\d{2})/.exec(c || ""); return m ? NF_MESES[Number(m[2]) - 1] + "/" + m[1] : "—"; }
  function nfDoc(d) {
    var x = String(d || "").replace(/\D/g, "");
    if (x.length === 14) return x.replace(/^(\d{2})(\d{3})(\d{3})(\d{4})(\d{2})$/, "$1.$2.$3/$4-$5");
    if (x.length === 11) return x.replace(/^(\d{3})(\d{3})(\d{3})(\d{2})$/, "$1.$2.$3-$4");
    return d || "";
  }
  function nfMesAtual() { var d = new Date(Date.now() - 3 * 36e5); return d.getUTCFullYear() + "-" + pad(d.getUTCMonth() + 1); }
  function nfPct(bp) { return bp ? dec(Number(bp) / 100, 2) : ""; }
  function nfBp(t) { var n = numDec(t); return Math.round(n * 100); }
  function nfReais(centavos) { return (Number(centavos || 0) / 100).toLocaleString("pt-BR", { minimumFractionDigits: 2, maximumFractionDigits: 2 }); }
  function nfNota(id) { return (((dadosDe("nfse") || {}).notas) || []).filter(function (n) { return String(n.id) === String(id); })[0]; }
  function nfMini(rot, icone, a, id, extra) { return '<button type="button" class="mini" data-a="' + a + '" data-id="' + esc(id) + '"' + (extra || "") + ">" + (icone ? ic(icone) : "") + esc(rot) + "</button>"; }

  TELAS_RENDER.nfse = function () {
    var h = cab("Notas fiscais (NFS-e)", "A NFS-e que o PAVLVS emite para quem assina o Paulus. Emitir, cancelar, substituir, o certificado e os parâmetros valem <b>na hora</b>; só os três interruptores passam pela fila de alterações.");
    var est = estadoLeitura(["nfse"], "nfse"); if (est) return h + est;
    h += erroRecente("nfse", "nfse");
    var d = dadosDe("nfse"), s = d.situacao || null, emitir = podeNf(), N = U.nfse;
    var trava = emitir ? "" : ' disabled title="o papel ' + esc(E.sessao.papel) + ' só vê as notas fiscais"';
    if (d.emissor && d.emissor.ligado === false) h += falta(d.emissor);
    if (d.erro) h += '<p class="erro-linha">' + ic("warning") + "<span>" + esc(d.erro) + "</span></p>";
    var prod = s && s.ambiente === "producao";
    // o topo: o selo do ambiente e os quatro botões
    var topoDir = '<div class="nf-topo-dir"><span class="nf-selo' + (prod ? " producao" : "") + '">' + (prod ? "produção · as notas valem de verdade" : "ambiente de testes · produção restrita, sem valor fiscal") + "</span>" +
      '<div class="nf-botoes"><button type="button" class="mini" data-a="nfTestar"' + (s ? trava : " disabled") + (N.testando ? " disabled" : "") + ">" + ic("lan") + (N.testando ? "Testando…" : "Testar comunicação") + "</button></div></div>";
    // Emitir, Clientes e Parametros eram pop-ups: agora sao guias da pagina (o mesmo conteudo, embutido).
    var abaNf = N.aba;
    if (abaNf !== "notas" && !(E.modal && E.modal.embutido)) abaNf = N.aba = "notas";
    h += '<div class="plano-topo">' + seg("nfse.aba", [["notas", "Notas"], ["emitir", "Emitir NFS-e"], ["clientes", "Clientes"], ["parametros", "Parâmetros"]], abaNf) + topoDir + "</div>";
    if (abaNf !== "notas") return h + modalHtml().replace(/^<div class="veu[^>]*><\/div><div class="modal/, '<div class="modal embutido');
    if (s && !s.pode_emitir && (s.motivos || []).length) h += '<p class="aviso-falta">' + ic("warning") + "<span><b>Ainda não dá para emitir:</b> " + esc(s.motivos.join("; ")) + ".</span></p>";
    // o resultado do teste
    var t = N.teste;
    if (t) {
      h += '<div class="painel nf-teste">' + painelCab(t.ok ? "Comunicação ok" : "A comunicação falhou", esc(quando(t.quando)), t.ok ? "c-ok" : "c-erro") + (t.etapas || []).map(function (e) {
        return '<div class="linha p10">' + ic(e.ok ? "check" : "close", e.ok ? "c-ok" : "c-erro") + '<span class="txt2"><b>' + esc(e.titulo) + "</b><small>" + esc(e.detalhe || "") + "</small></span>" +
          (e.ms != null ? '<span class="num s11 c-ink3">' + esc(e.ms) + " ms</span>" : "") + "</div>";
      }).join("") + "</div>";
    }
    // o certificado numa linha + o cartão
    if (s) h += nfCertificado(d, s, emitir);
    // os interruptores e os fatos
    var c = d.config || {}, pc = ultimaNaFila("nfse.config");
    var atual = pc ? pc.dados || c : c, podeC = pode("nfse.config");
    var OP = [["auto", "Emitir ao confirmar o pagamento", "assim que o Mercado Pago confirma, se os dados fiscais do cliente estiverem completos; senão o motivo aparece em Pagamentos sem nota"],
      ["email", "Entregar ao app do cliente logo depois de emitir", "a nota (PDF e XML) aparece no Paulus dele; desligado, o botão Enviar ao cliente entrega"],
      ["mail", "Mandar também por e-mail", "PDF e XML anexos, ao e-mail fiscal do cliente; precisa da RESEND_API_KEY"]];
    var p = s ? (s.prestador || {}).dados || {} : {};
    var fatos = s ? [["Prestador", p.razao_social ? p.razao_social + " · " + (nfDoc(p.documento) || "CNPJ a definir") : "a definir em Parâmetros"],
      ["Serviço", (p.servico || {}).ctribnac ? "cTribNac " + p.servico.ctribnac + ((p.servico || {}).nbs ? " · NBS " + p.servico.nbs : "") + ((p.servico || {}).aliquota_iss_bp ? " · ISS " + nfPct(p.servico.aliquota_iss_bp) + "%" : "") : "a definir"],
      ["Município", s.municipio ? s.municipio.frase : "—"], ["Próxima DPS", "nº " + s.proximo_numero + " · série " + (p.serie || "1")]] : [];
    h += '<div class="duas-col"><div class="painel">' + OP.map(function (o) {
      var on = !!atual[o[0]], mud = pc && !!c[o[0]] !== on;
      return '<button type="button" class="linha-btn" role="switch" aria-checked="' + on + '" data-a="nfseCfg" data-k="' + o[0] + '"' + (podeC ? "" : ' disabled title="o papel ' + esc(E.sessao.papel) + ' não muda a NFS-e"') + '><span class="txt2"><b>' + esc(o[1]) + "</b><small>" + esc(o[2]) + (mud ? ' · <span class="c-atencao">na fila</span>' : "") + "</small></span>" + sw(on) + "</button>";
    }).join("") + "</div>" + (fatos.length ? '<div class="painel nf-fatos"><dl class="fatos-p f110 alto">' + fatos.map(function (f) { return fato(f[0], f[1]); }).join("") + "</dl></div>" : "<span></span>") + "</div>";
    // a lista das notas
    var ns = d.notas || [];
    // Uma linha por nota: as acoes viram icones a direita (com titulo), e o que se sabe da entrega fica embaixo do cliente.
    // As acoes de cada nota ficam num menu "…" no fim da linha.
    var cols = "minmax(104px,.9fr) minmax(0,2.2fr) minmax(104px,1fr) minmax(100px,.9fr) minmax(112px,1fr) 36px";
    var NS = N.sel;
    var nfIc = function (icone, rot, a, id, extra, cls) { return '<button type="button" role="menuitem" class="nf-mi' + (cls ? " " + cls : "") + '" data-a="' + a + '" data-id="' + esc(id) + '"' + (extra || "") + ">" + ic(icone) + "<span>" + esc(rot) + "</span></button>"; };
    var nfLink = function (icone, rot, href) { return '<a role="menuitem" class="nf-mi" href="' + href + '" download>' + ic(icone) + "<span>" + esc(rot) + "</span></a>"; };
    var linhas = ns.map(function (n) {
      var cor = NF_SIT[n.estado] || "var(--ink3)", txt = n.estado_rotulo + (n.ambiente !== "producao" ? " · testes" : "");
      var A = [];
      if (n.estado === "emitida" || n.estado === "cancelada" || n.estado === "substituida") {
        A.push(nfLink("picture_as_pdf", "Baixar o PDF", NF + "notas/" + n.id + "/pdf?baixar=1"));
        A.push(nfIc("print", "Imprimir", "nfImprimir", n.id));
        A.push(nfLink("code", "Baixar o XML", NF + "notas/" + n.id + "/xml"));
      }
      if (n.estado === "emitida") {
        A.push(nfIc("send", n.cliente_avisado && !/^erro/.test(n.cliente_avisado) ? "Reenviar ao cliente" : "Enviar ao cliente", "nfEnviar", n.id, n.conta ? trava : " disabled"));
        A.push(nfIc("swap_horiz", "Substituir", "nfSubstituir", n.id, trava));
        A.push(nfIc("block", "Cancelar a nota", "nfCancelar", n.id, trava, "vermelho"));
      } else if (n.estado === "na_fila" || n.estado === "aguardando_confirmacao" || n.estado === "enviando") {
        A.push(nfIc("refresh", "Tentar agora", "nfTentar", n.id, trava));
      } else if (n.estado === "rejeitada" || n.estado === "rascunho") {
        A.push(nfIc("delete", "Descartar", "nfDescartar", n.id, trava));
      }
      var info = [];
      if (n.erro && n.estado !== "emitida") info.push(n.erro);
      if (n.cliente_avisado && !/^erro/.test(n.cliente_avisado)) info.push("no app do cliente desde " + ddmm(n.cliente_avisado));
      else if (n.cliente_avisado) info.push("app do cliente: " + n.cliente_avisado);
      if (n.email) info.push("e-mail: " + n.email);
      if (n.substituida_por_id) info.push("substituída pela nota " + ((nfNota(n.substituida_por_id) || {}).numero || "#" + n.substituida_por_id));
      var marcN = !!(NS && NS[n.id]);
      return '<div class="grade-linha p10' + (marcN ? " marcada" : "") + '" data-nsel="' + esc(n.id) + '"' + (NS ? ' aria-selected="' + marcN + '"' : "") + '><span class="num">' + esc(n.numero || "—") + "</span>" +
        '<span class="cel-nome"><b class="corta" style="font-size:13px" title="' + esc([nfDoc(n.documento)].concat(info).filter(Boolean).join(" · ")) + '">' + esc(n.cliente || "—") + "</b></span>" +
        '<span class="num c-ink2">' + esc(nfCompetencia(n.competencia)) + '</span><span class="num dir">' + esc(brl(n.centavos / 100)) + "</span>" +
        '<span class="sit" style="color:' + cor + '" title="' + esc(txt) + '"><i></i><span class="corta">' + esc(txt) + "</span></span>" +
        '<span class="nf-mais' + (NS ? " acoes-esmaecidas-par" : "") + '">' + (A.length ? '<button type="button" class="btn-icone nf-ic" data-a="nfMenu" data-id="' + esc(n.id) + '" aria-haspopup="menu" aria-expanded="' + (String(N.menu) === String(n.id)) + '" aria-label="Ações da nota" title="Ações">' + ic("more_horiz") + "</button>" +
          (String(N.menu) === String(n.id) ? '<div class="nf-menu" role="menu">' + A.join("") + "</div>" : "") : "") + "</span></div>";
    }).join("") || '<p class="vazio-linha">Nenhuma nota ainda. Comece por Emitir NFS-e.</p>';
    // Segurar o clique numa nota seleciona varias; o cabecalho vira a barra com as mesmas acoes do "…".
    var idsN = NS ? Object.keys(NS).filter(function (k) { return NS[k]; }) : [], nN = idsN.length, tudoN = nN && nN >= ns.length;
    var selN = ns.filter(function (n) { return NS && NS[n.id]; });
    var temE = function (f) { return selN.length && selN.every(f); };
    var docOk = temE(function (n) { return n.estado === "emitida" || n.estado === "cancelada" || n.estado === "substituida"; });
    var emit = temE(function (n) { return n.estado === "emitida"; });
    var bS = function (icone, rot, a, ok) { return '<button type="button" class="btn-icone sel-acao' + (icone === "block" ? " sel-perigo" : "") + '" data-a="' + a + '"' + (ok ? "" : " disabled") + ' aria-label="' + esc(rot) + '" title="' + esc(rot) + '">' + ic(icone) + "</button>"; };
    var cabN = NS ? '<div class="painel-cab sel-cab"><button type="button" class="caixinha tri' + (tudoN ? " cheia" : nN ? " parcial" : "") + '" role="checkbox" aria-checked="' + (tudoN ? "true" : nN ? "mixed" : "false") + '" data-a="' + (nN ? "nfSelSair" : "nfSelTodas") + '" aria-label="' + (nN ? "Limpar a seleção" : "Selecionar todas") + '">' + (tudoN ? ic("check") : nN ? ic("remove") : "") + "</button>" +
      "<b>" + nN + (nN === 1 ? " selecionada" : " selecionadas") + '</b><span class="sel-div"></span>' +
      bS("picture_as_pdf", "Baixar os PDFs", "nfMassaPdf", docOk) + bS("print", "Imprimir", "nfMassaImprimir", docOk) + bS("code", "Baixar os XMLs", "nfMassaXml", docOk) +
      bS("send", "Enviar aos clientes", "nfMassaEnviar", emit && !trava && selN.every(function (n) { return n.conta; })) +
      bS("swap_horiz", nN > 1 ? "Substituir (uma nota por vez)" : "Substituir", "nfMassaSubstituir", emit && nN === 1 && !trava) +
      bS("block", nN > 1 ? "Cancelar (uma nota por vez)" : "Cancelar a nota", "nfMassaCancelar", emit && nN === 1 && !trava) + "</div>"
      : painelCab("Notas", ns.length + (ns.length === 1 ? " nota" : " notas"));
    h += '<div class="painel' + (NS ? " selecionando" : "") + '">' + cabN +
      grade(cols, 620, '<span>Nº</span><span>Cliente</span><span>Competência</span><span class="dir">Valor</span><span>Situação</span><span></span>', linhas) + "</div>";
    // os pagamentos sem nota
    var pg = d.pagamentos || [];
    var lp = pg.map(function (x) {
      return '<div class="linha p10"><span class="cel-nome" style="width:96px;flex:none;gap:1px"><span class="num c-ink2">' + esc(quando(x.quando)) + '</span><span class="num c-ink3" style="font-size:10.5px">' + esc(x.tipo) + "</span></span>" +
        '<span class="txt2" style="min-width:180px"><b>' + esc(x.cliente || "conta " + String(x.conta || "").slice(0, 6)) + "</b>" + (x.motivo || x.erro ? '<small class="c-atencao">' + esc(x.motivo || x.erro) + "</small>" : "<small>sem nota</small>") + "</span>" +
        '<span class="num">' + esc(brl(x.valor)) + "</span>" + nfMini("Emitir", "receipt_long", "nfEmitirPag", x.id, s ? trava : " disabled") + "</div>";
    }).join("") || '<p class="vazio-linha">Todos os pagamentos têm nota.</p>';
    h += '<div class="painel">' + painelCab("Pagamentos sem nota", String(pg.length), pg.length ? "c-atencao" : "") + lp + "</div>";
    return h;
  };

  function nfCertificado(d, s, emitir) {
    var N = U.nfse, c = s.certificado || {}, cf = d.cloudflare || {};
    var h = '<div class="painel">' + painelCab("Certificado digital A1", c.instalado ? "instalado " + esc(ddmmaaaa(c.instalado_em)) : "nenhum");
    if (emitir) {
      h += '<div class="nf-cert"><label class="mini nf-arquivo">' + ic("upload") + '<span class="corta">' + esc(N.pfx ? N.pfx.nome : "Escolher o .pfx") + '</span><input type="file" id="nf-pfx" data-in="nfPfx" accept=".pfx,.p12,application/x-pkcs12"></label>' +
        '<span class="caixa-campo fundo nf-senha"><input type="password" id="nf-senha" data-in="nfSenha" value="' + esc(N.senha) + '" placeholder="senha do certificado" autocomplete="off" aria-label="Senha do certificado"></span>' +
        '<button type="button" class="mini cheia" data-a="nfCert"' + (N.instalando || !N.pfx ? " disabled" : "") + ">" + (N.instalando ? "Instalando…" : c.instalado ? "Trocar" : "Instalar") + "</button></div>" +
        '<p class="nota-campo nf-nota">O .pfx é aberto aqui no navegador: o arquivo e a senha não saem desta página. Vão ao servidor só o certificado e a chave, guardados cifrados.</p>';
    }
    if (N.aviso) h += '<p class="' + (N.aviso.ok ? "nf-aviso ok" : "nf-aviso") + '">' + ic(N.aviso.ok ? "check" : "warning") + "<span>" + esc(N.aviso.frase) + "</span></p>";
    if (c.instalado) {
      var dias = c.dias_restantes, perto = c.vencido || (dias != null && dias <= 30);
      h += '<dl class="fatos-p f110 nf-cartao">' + fato("Nome", String(c.titular || "—").split(":")[0]) + fato("CNPJ/CPF", nfDoc(c.documento) || "—") +
        '<div><dt>Vencimento</dt><dd class="' + (perto ? "c-erro" : "") + '">' + esc(ddmmaaaa(c.valido_ate) + (dias != null ? " · " + (dias < 0 ? "vencido" : dias + (dias === 1 ? " dia" : " dias")) : "")) +
        (perto && !c.vencido ? " · renove antes de vencer" : "") + "</dd></div>" +
        fato("Conexão", cf.mtls ? "mTLS na Cloudflare · " + cf.mtls.id + " · desde " + ddmmaaaa(cf.mtls.quando) : cf.falta || "ainda não cadastrado na Cloudflare") + "</dl>";
    } else h += '<p class="nota-campo nf-nota">Use o A1 (.pfx ou .p12) do CNPJ do PAVLVS; o CNPJ, o nome e o vencimento saem dele.</p>';
    if (cf.falta && c.instalado && !cf.mtls) h += '<p class="aviso-falta embutido">' + ic("warning") + "<span>Sem a conexão com a Sefin: " + esc(cf.falta) + ".</span></p>";
    return h + "</div>";
  }

  /* ---------- 12. Equipe ---------- */
  TELAS_RENDER.equipe = function () {
    var h = cab("Equipe", "Quem entra neste painel é quem o Cloudflare Access deixa passar. O papel decide o que cada um vê e faz aqui dentro.");
    var est = estadoLeitura(["equipe"], "equipe"); if (est) return h + est;
    h += erroRecente("equipe", "equipe");
    var d = dadosDe("equipe"), podeP = pode("equipe.papel");
    // Sem a API do Access no Worker, quem aceita o convite entra na equipe, mas o e-mail vai a politica do Access a mao.
    if (podeP) h += falta(d.liberacao || cfg("equipe"));
    h += '<div class="painel"><div class="painel-cab secao-cab"><span class="rotulo">Pessoas</span>' + (podeP ? '<button type="button" class="mini cheia" data-a="membroNovo">' + ic("person_add") + "Convidar</button>" : "") + "</div>" + (d.membros || []).map(function (m) {
      var p = ultimaNaFila("equipe.papel", m.email), papel = p && p.dados ? p.dados.papel : m.papel, mf = naFila("equipe.membro", m.email);
      // Convite pendente: a pessoa ainda nao entrou; reenviar ou cancelar no lugar do papel.
      if (m.convite) {
        var venc = m.convite.vence ? new Date(m.convite.vence) : null, vencido = venc && venc < new Date();
        return '<div class="linha"><span class="txt2" style="min-width:200px"><b>' + esc(m.nome || m.email) + ' <em class="convite-tag' + (vencido ? " vencido" : "") + '">' + (vencido ? "convite vencido" : "convite enviado") + '</em></b><small class="mono">' + esc(m.email) + " · " + esc(m.papel) + " · " + (vencido ? "venceu " : "vence ") + esc(venc ? ddmm(isoDia(venc)) : "—") + "</small></span>" +
          (podeP ? '<span class="par"><button type="button" class="mini" data-a="conviteReenviar" data-id="' + esc(m.email) + '">' + ic("send") + "Reenviar</button>" +
            '<button type="button" class="btn-icone" data-a="membroExcluir" data-id="' + esc(m.email) + '" aria-label="Cancelar convite de ' + esc(m.nome || m.email) + '" title="Cancelar convite">' + ic("close") + "</button></span>" : "") + "</div>";
      }
      return '<div class="linha"><span class="txt2" style="min-width:200px"><b>' + esc(m.nome || m.email) + '</b><small class="mono">' + esc(m.email) + " · último acesso " + esc(m.ultimo ? quando(m.ultimo) : "nunca") + (p ? ' · <span class="c-atencao">na fila</span>' : "") + "</small></span>" +
        '<span class="par">' + seg("equipe.papel:" + m.email, [["dono", "Dono"], ["financeiro", "Financeiro"], ["suporte", "Suporte"]], papel, "pequeno", !podeP) +
        (podeP ? '<button type="button" class="btn-icone" data-a="membroEditar" data-id="' + esc(m.email) + '" aria-label="Editar ' + esc(m.nome || m.email) + '" title="Editar"' + attrDis(mf, "já está na fila de alterações") + ">" + ic("edit") + "</button>" +
          '<button type="button" class="btn-icone" data-a="membroExcluir" data-id="' + esc(m.email) + '" aria-label="Excluir ' + esc(m.nome || m.email) + '" title="Excluir"' + attrDis(mf, "já está na fila de alterações") + ">" + ic("delete") + "</button>" : "") + "</span></div>";
    }).join("") + "</div>";
    if (!podeP) h += '<p class="nota-pe">Só o papel Dono muda os papéis da equipe.</p>';
    var mz = d.matriz || [];
    var marca = function (v) { return '<span style="color:' + (v ? "var(--ok)" : "var(--ink3)") + '">' + (v ? "✓" : "—") + "</span>"; };
    h += '<div class="painel"><div class="matriz-cab"><span>O que cada papel faz</span><span>Dono</span><span>Financeiro</span><span>Suporte</span></div>' +
      mz.map(function (x) { return '<div class="matriz-linha"><span>' + esc(x.acao) + "</span>" + marca(x.dono) + marca(x.financeiro) + marca(x.suporte) + "</div>"; }).join("") + "</div>";
    return h;
  };

  /* ---------- 13. Confirmar alteracoes ---------- */
  TELAS_RENDER.alteracoes = function () {
    var h = cab("Confirmar alterações", "Tudo o que você mudou nesta sessão fica aqui até publicar. Publicar aplica tudo em ordem: contas, Mercado Pago, túneis e KV na hora; material publicado vira commit na main, que o deploy do site leva ao ar.");
    var est = estadoLeitura(["alteracoes"], "alteracoes"); if (est) return h + est;
    h += erroRecente("alteracoes", "alteracoes");
    var ps = E.pendentes, pubs = (dadosDe("alteracoes").publicacoes || []);
    h += '<div class="painel">' + painelCab("Pendentes", String(ps.length), "c-atencao") + (ps.length ? ps.map(function (a) {
      return '<div class="linha" style="padding:11px 14px"><span class="num s11 c-ink3" style="width:48px;flex:none">' + esc(quandoCurto(a.quando)) + '</span><span class="chip p22">' + esc(TELA[a.tela] ? TELA[a.tela].chip : a.tela) + '</span><span style="flex:1;min-width:200px;font-size:13.5px">' + esc(a.texto) + "</span>" +
        '<button type="button" class="btn-icone" data-a="tirarDaFila" data-id="' + esc(a.id) + '" aria-label="Tirar da fila: ' + esc(a.texto) + '" title="Tirar da fila">' + ic("close") + "</button></div>";
    }).join("") : '<p class="vazio-linha" style="padding:28px 14px">Nada pendente. O painel está igual ao que está no ar.</p>') + "</div>";
    h += '<div style="display:flex;align-items:center;gap:16px;flex-wrap:wrap"><button type="button" class="btn-duplo' + (ps.length ? "" : " fraco") + '" data-a="modalCommit"' + (ps.length ? "" : ' aria-disabled="true"') + "><span>" + ic("publish") + 'Commitar e pushar</span></button><span class="num s11 c-ink3">grava no KV; material publicado vira commit na main</span></div>';
    h += '<div class="painel">' + painelCab("Publicações anteriores") + (pubs.length ? pubs.map(function (p, i) {
      var podeR = p.commit && !p.revertida && pode("retroagir");
      return '<div class="linha p10"><span class="num s11 c-ink3" style="width:92px;flex:none">' + esc(quando(p.quando)) + '</span><span class="num" style="width:72px;flex:none">' + esc(String(p.commit || "").slice(0, 7)) + '</span><span style="flex:1;min-width:200px;font-size:13px;color:var(--ink2)">' + esc(p.resumo) + (p.por ? ' <span class="c-ink3">· ' + esc(p.por) + "</span>" : "") + '</span><span class="num s11 c-ink3">' + (p.n || 0) + (p.n === 1 ? " alteração" : " alterações") + "</span>" +
        (p.revertida ? '<span class="num s11 c-ink3" style="width:84px;text-align:right">retroagida</span>' : '<button type="button" class="mini" data-a="modalRetroagir" data-i="' + i + '"' + attrDis(!podeR, p.commit ? "só o papel Dono retroage" : "sem commit para desfazer") + ">" + ic("undo") + "Retroagir</button>") + "</div>";
    }).join("") : '<p class="vazio-linha">Nenhuma publicação ainda.</p>') + "</div>";
    return h;
  };

  /* ================================================================ camada: gaveta, modal, busca */

  function renderCamada() {
    var el = $("camada");
    var g = el.querySelector(".ficha-corpo"), gs = g ? g.scrollTop : 0;
    var b = el.querySelector(".busca-res"), bs = b ? b.scrollTop : 0;
    var h = "";
    if (E.gaveta) h += gavetaHtml();
    if (E.modal && !E.modal.embutido) h += modalHtml();
    if (E.busca.aberta) h += buscaHtml();
    pintar(el, h);
    if (E.modal && E.modal.embutido && !renderCamada.dentro) { renderCamada.dentro = true; try { render(); } finally { renderCamada.dentro = false; } }
    g = el.querySelector(".ficha-corpo"); if (g) g.scrollTop = gs;
    b = el.querySelector(".busca-res"); if (b) b.scrollTop = bs;
    document.body.style.overflow = h ? "hidden" : "";
  }

  function contaResumo(id) { var d = dadosDe("contas"); return d ? (d.contas || []).filter(function (c) { return String(c.id) === String(id); })[0] : null; }

  // As partes da conta, usadas no pop-up (resumo e acoes) e na pagina da conta (tudo).
  function contaPartes(c, det) {
    var P = { perigo: "" };
    var cad = det.cadastro || {}, esc_ = det.escritorio || {}, con = det.consentimento, ass = det.assinatura;
    var prepago = ass && (ass.periodo === "anual" || ass.periodo === "avulso");
    // Os cards do Resumo: titulo e acao no alto; embaixo, os dados em grade (rotulo pequeno em cima, valor embaixo).
    var secao = function (rot, linhas, links, cols) { linhas = linhas.filter(Boolean); return linhas.length ? '<div class="painel res-card"><div class="painel-cab secao-cab"><span class="rotulo">' + esc(rot) + "</span>" + (links || "") + '</div><dl class="res-grade c' + (cols || 2) + '">' + linhas.join("") + "</dl></div>" : ""; };
    var largo = function (k, v) { return '<div class="largo"><dt>' + esc(k) + "</dt><dd>" + v + "</dd></div>"; };
    var link = function (rot, a, icone) { return '<button type="button" class="link-secao" data-a="' + a + '" data-id="' + esc(det.id) + '">' + esc(rot) + ic(icone || "arrow_forward") + "</button>"; };
    var linhasDe = function (k, vs) { return "<div><dt>" + esc(k) + "</dt><dd>" + vs.map(esc).join("<br>") + "</dd></div>"; };
    // plano e ciclo
    var cic = det.ciclo, p = cic && cic.tokens ? Math.min(100, Math.round((cic.usados || 0) / cic.tokens * 100)) : 0;
    // O uso do ciclo em destaque, logo abaixo da situacao.
    P.uso = !cic ? "" : '<div class="gaveta-uso"><div class="entre-uso"><span class="rotulo">Uso do ciclo</span><b>' + p + '%</b></div><span class="uso"><i style="width:' + p + '%"></i></span></div>';
    P.plano = secao("Plano", [
      c.plano ? fato("Plano", c.plano.nome) : fato("Plano", "—"),
      c.plano ? fato("Valor", brl(c.plano.valor) + "/mês") : "",
      cic ? fato("Ciclo", ddmm(cic.inicio) + " a " + ddmm(cic.fim)) : fato("Ciclo", "sem ciclo aberto"),
      cic ? fato("Usados", tok(cic.usados)) : "",
      fato("Restantes", tok(det.restantes)),
      fato("Recarga", tok(det.extra)),
      det.plano_proximo ? fato("Na renovação", "troca para " + (det.plano_proximo.nome || det.plano_proximo.id || det.plano_proximo)) : ""
    ], '<button type="button" class="btn-icone icone-secao" data-a="contaPlano" data-id="' + esc(det.id) + '" aria-label="Alterar plano" title="Alterar plano">' + ic("swap_horiz") + "</button>", 3);
    // cadastro
    P.cadastro = secao("Cadastro", [
      fato("Escritório", esc_.nome || "—"),
      esc_.slug ? fato("Endereço", esc_.slug + ".paulus.ia.br") : "",
      fato("CPF/CNPJ", cad.documento || esc_.documento || "—"),
      fato("OAB, RG ou CNH", cad.oab || det.oab || "—"),
      fato("Telefone", cad.telefone || "—"),
      largo("Endereço", esc([cad.logradouro, cad.numero].filter(Boolean).join(", ") || "—") + (cad.complemento ? ' <span class="c-mute">· ' + esc(cad.complemento) + "</span>" : "")),
      fato("Bairro", cad.bairro || "—"),
      fato("Cidade", (cad.cidade || "—") + (cad.uf ? " / " + cad.uf : "")),
      fato("CEP", cad.cep || "—"),
      fato("Conta desde", ddmmaaaa(det.criada))
    ], '<button type="button" class="btn-icone icone-secao" data-a="contaCadastro" data-id="' + esc(det.id) + '" aria-label="Editar cadastro" title="Editar cadastro">' + ic("edit") + "</button>");
    // pagamento
    var tipoAss = !ass ? "sem assinatura" : ass.periodo === "anual" ? "anual" : ass.periodo === "avulso" ? "um mês no Pix" : "mensal (preapproval)";
    P.mp = secao("Mercado Pago", [
      fato("Assinatura", tipoAss),
      ass ? fato("Situação", prepago ? (SIT_PAGO[ass.situacao] || ass.situacao) : ass.situacao) : "",
      prepago && det.pago_ate ? fato("Pago até", ddmmaaaa(det.pago_ate)) : "",
      ass && !prepago && ass.desde ? fato("Desde", ddmmaaaa(ass.desde)) : "",
      ass && !prepago ? fato("ID", ass.id) : ""
    ], '<button type="button" class="btn-icone icone-secao" data-a="contaExtrato" data-id="' + esc(det.id) + '" aria-label="Extrato completo" title="Extrato completo">' + ic("receipt_long") + "</button>");
    // google e termos
    var esc2 = det.google ? (det.google.escopos || []) : [];
    P.google = secao("Google e termos", [
      fato("Google", det.google ? "ligado" : "desligado"),
      det.google ? largo("Permissões", '<span class="res-perms">' + [["mail.google.com", "gmail", "Gmail"], ["calendar.events", "agenda", "Agenda e Meet"], ["drive.file", "drive", "Drive · enviar"], ["drive.readonly", "drive", "Drive · ler"]].map(function (s) {
        var on = esc2.indexOf(s[0]) >= 0; return '<span class="res-perm' + (on ? "" : " off") + '" title="' + esc(s[0]) + (on ? "" : " · não autorizado") + '">' + SIMB_G[s[1]] + esc(s[2]) + "</span>";
      }).join("") + "</span>") : "",
      det.google_pendente ? fato("Pendente", "revogação no Paulus") : "",
      fato("Termos", con ? "versão " + con.versao : "—"),
      con && con.quem ? fato("Aceito por", con.quem) : "",
      con && con.quando ? fato("Aceito em", ddmmaaaa(con.quando)) : ""
    ], det.google && pode("google.servicos") ? '<button type="button" class="btn-icone icone-secao" data-a="modalGoogle" data-id="' + esc(det.id) + '" aria-label="Revogar permissões do Google" title="Revogar permissões do Google">' + ic("link_off") + "</button>" : "");
    // instalacoes
    var inst = det.instalacoes || [], podeI = pode("conta.instalacao.apagar");
    P.inst = '<div class="painel"><div class="painel-cab secao-cab"><span class="rotulo">Instalações</span><span class="cab-dir">' + inst.length + ' de 3</span></div>' + (inst.length ? inst.map(function (i) {
      var fila = naFila("conta.instalacao.apagar", det.id + ":" + i.hash8);
      return '<div class="linha"><span class="txt2"><b class="corta">' + esc(i.instalacao) + "</b><small>desde " + esc(ddmm(i.criado)) + "</small></span>" +
        (podeI ? '<button type="button" class="mini" style="height:26px" data-a="instDesvincular" data-hash="' + esc(i.hash8) + '" data-inst="' + esc(i.instalacao) + '"' + attrDis(fila, "já está na fila de alterações") + ">" + (fila ? "Na fila" : "Desvincular") + "</button>" : "") + "</div>";
    }).join("") : '<p class="vazio-linha" style="padding:14px">Nenhuma instalação ligada.</p>') + "</div>";
    // pagamentos
    var pgs = (det.pagamentos || []).slice().sort(function (a, b) { return Date.parse(b.quando) - Date.parse(a.quando); }), podeR = pode("conta.reembolsar"), mpDesl = desligado(cfg("mercado_pago"));
    P.pgs = '<div class="pilha" style="gap:10px"><div class="painel"><div class="painel-cab secao-cab"><span class="rotulo">Pagamentos</span><span class="cab-dir">' + pgs.length + "</span></div>" + (pgs.length ? pgs.slice(0, 5).map(function (x) {
      var fila = naFila("conta.reembolsar", det.id + ":" + x.ref);
      var dias = Math.floor((Date.now() - Date.parse(x.quando)) / 864e5);
      var sub = x.reembolso ? "reembolsado em " + ddmm(x.reembolso.quando) : "";
      var botao = !podeR || x.reembolso ? "" : '<button type="button" class="mini" style="height:26px" data-a="contaReembolsar" data-ref="' + esc(x.ref) + '"' +
        attrDis(fila || mpDesl, fila ? "já está na fila de alterações" : cfg("mercado_pago").falta) + ">" + (fila ? "Na fila" : "Reembolsar") + "</button>";
      return '<div class="linha"><span class="txt2"><b class="corta">' + esc(TIPO_PAG[x.tipo] || x.tipo) + " de " + esc(brl(x.valor)) + "</b><small>" + esc(ddmmaaaa(x.quando)) + "</small>" + (sub ? "<small" + (x.reembolso ? ' class="c-ink3"' : "") + ">" + esc(sub) + "</small>" : "") + "</span>" + botao + "</div>";
    }).join("") : '<p class="vazio-linha" style="padding:14px">Nenhum pagamento.</p>') +
      "</div>" +
      (podeR && pgs.some(function (x) { return !x.reembolso; }) ? '<span class="nota-campo">Reembolsar devolve o valor inteiro pelo Mercado Pago, no cartão ou no Pix de origem, e tira da conta o que ele pagou: o anual e o mês no Pix acabam, a mensalidade cancela a assinatura, a recarga sai dos créditos. Entra na fila e acontece ao confirmar. A nota fiscal já emitida se cancela em Notas fiscais.</span>' : "") + "</div>";
    // acoes
    var nome1 = primeiro(det.nome), mpOff = desligado(cfg("mercado_pago"));
    var A = [];
    if (pode("conta.creditar")) A.push(acaoG("account_balance_wallet", naFila("conta.creditar", det.id) ? "Cortesia na fila" : "Cortesia", "contaCreditar"));
    if (pode("conta.cancelar") && ass && !prepago && ass.situacao !== "cancelled" && det.situacao !== "cancelada") P.perigo = (acaoG("close", naFila("conta.cancelar", det.id) ? "Cancelamento na fila" : "Cancelar assinatura", "contaCancelar", mpOff ? cfg("mercado_pago").falta : naFila("conta.cancelar", det.id) ? "já está na fila de alterações" : "", true));
    P.acoes = '<div class="ficha-acoes">' + A.join("") + "</div>" + (mpOff && pode("conta.cancelar") && ass ? '<span class="nota-campo">' + esc(cfg("mercado_pago").falta) + "</span>" : "");
    return P;
  }

  function gavetaHtml() {
    var G = E.gaveta, c = G.det || G.resumo;
    if (G.pagina) return "";
    // O pop-up e so o resumo e as acoes; o detalhe fica na pagina da conta.
    var fechar = '<button type="button" class="btn-icone" data-a="fecharGaveta" aria-label="Fechar" id="gaveta-fechar">' + ic("close", "s18") + "</button>";
    var h = '<div class="veu veu-ficha" data-a="fecharGaveta"></div><div class="ficha" role="dialog" aria-modal="true" aria-labelledby="gaveta-titulo">';
    if (!c) {
      return h + '<div class="ficha-cab"><div class="pilha" style="gap:3px"><h2 id="gaveta-titulo">Conta</h2><span class="ficha-sub">Contas › ' + esc(G.id) + "</span></div>" + fechar + '</div><div class="ficha-corpo">' + (G.erro ? '<p class="erro-linha">' + ic("warning") + "<span>Não foi possível ler a conta agora: " + esc(G.erro) + "</span></p>" : '<p class="carregando">Carregando…</p>') + "</div></div>";
    }
    var s = sitConta(c.situacao), det = G.det;
    h += '<div class="ficha-cab"><div class="pilha" style="gap:3px"><h2 id="gaveta-titulo">' + esc(c.nome) + '</h2><span class="ficha-sub">Contas › ' + esc(c.email) +
      ' <span class="ficha-sit" style="color:' + s[1] + '" title="' + esc(s[0]) + '" aria-label="' + esc(s[0]) + '"><i></i></span></span></div>' + fechar + '</div><div class="ficha-corpo">';
    if (G.erro) h += '<p class="erro-linha">' + ic("warning") + "<span>Não foi possível ler o detalhe da conta: " + esc(G.erro) + "</span></p>";
    if (!det) return h + '<p class="carregando">Carregando o detalhe…</p></div></div>';
    var P = contaPartes(c, det), es = det.escritorio || {};
    h += P.uso + '<dl class="fatos-p gaveta-fatos ficha-resumo">' + fato("Plano", c.plano ? c.plano.nome : "—") + (c.plano ? fato("Valor", brl(c.plano.valor) + "/mês") : "") +
      fato("Escritório", es.nome || "—") + fato("Restantes", tok(det.restantes)) + "</dl>";
    return h + '</div><div class="ficha-pe">' + P.perigo +
      '<button type="button" class="btn-duplo pequeno ficha-abrir" data-a="abrirPaginaConta"><span>Abrir a conta' + ic("arrow_forward", "s18") + "</span></button></div></div>";
  }

  // A pagina da conta: tudo o que a conta tem, em cards, dentro da tela Contas.
  function contaPaginaHtml() {
    var G = E.gaveta, c = G.det || G.resumo, det = G.det;
    var h = '<div class="cab-tela"><button type="button" class="voltar-conta" data-a="voltarContas">' + ic("arrow_back", "s18") + "Contas</button>";
    if (!c) return h + "<h1>Conta</h1></div>" + (G.erro ? '<p class="erro-linha">' + ic("warning") + "<span>Não foi possível ler a conta agora: " + esc(G.erro) + "</span></p>" : '<p class="carregando">Carregando…</p>');
    var s = sitConta(c.situacao);
    var slug = ((det && det.escritorio) || c.escritorio || {}).slug;
    h += "<h1>" + esc(c.nome) + '</h1><span class="conta-sub">' + esc(c.email) + ' <span class="ficha-sit" style="color:' + s[1] + '" title="' + esc(s[0]) + '"><i></i></span>' +
      (slug ? '<a class="conta-link" href="https://' + esc(slug) + '.paulus.ia.br" target="_blank" rel="noopener">' + esc(slug) + ".paulus.ia.br" + ic("arrow_outward") + "</a>" : "") + "</span></div>";
    if (!det) return h + '<p class="carregando">Carregando o detalhe…</p>';
    var P = contaPartes(c, det), aba = G.aba || "resumo", slugT = ((det.escritorio || {}).slug) || ((c.escritorio || {}).slug);
    var temG = det.google && pode("google.servicos");
    // As abas na mesma pilula dos filtros (.segmentos).
    h += '<div class="conta-barra"><div class="segmentos conta-abas"><div role="tablist" aria-label="Partes da conta">' + ABAS_CONTA.filter(function (x) { return (x[0] !== "google" || temG) && (x[0] !== "tunel" || slugT); }).map(function (x) {
      return '<button type="button" role="tab" data-a="contaAba" data-aba="' + x[0] + '" aria-pressed="' + (aba === x[0]) + '" aria-selected="' + (aba === x[0]) + '">' + esc(x[1]) + "</button>";
    }).join("") + "</div></div>" + '<div class="conta-topo">' + P.acoes + (P.perigo ? '<span class="conta-perigo">' + P.perigo + "</span>" : "") + "</div></div>";
    if (aba === "tunel") return h + tunelAbaHtml(slugT);
    if (aba !== "resumo" && E.modal && E.modal.embutido) {
      return h + modalHtml().replace(/^<div class="veu[^>]*><\/div><div class="modal/, '<div class="modal embutido');
    }
    h += P.uso;
    h += '<div class="conta-grade"><div class="pilha g20">' + P.plano + P.pgs + '</div><div class="pilha g20">' + P.cadastro + P.google + P.inst + "</div></div>";
    return h;
  }
  var UFS = ["AC", "AL", "AP", "AM", "BA", "CE", "DF", "ES", "GO", "MA", "MT", "MS", "MG", "PA", "PB", "PR", "PE", "PI", "RJ", "RN", "RS", "RO", "RR", "SC", "SP", "SE", "TO"];
  var TIPO_PAG = { assinatura: "Mensalidade", anual: "Anual", avulso: "Mês no Pix", recarga: "Recarga" };
  var SIT_PAGO = { authorized: "em dia", expired: "vencido", refunded: "reembolsado" };
  function acaoG(icone, rot, a, travado, vermelho) {
    return '<button type="button" class="mini ficha-acao' + (vermelho ? " vermelho" : "") + '" data-a="' + a + '" data-id="' + esc(E.gaveta ? E.gaveta.id : "") + '"' + attrDis(!!travado, travado) + ">" + (vermelho ? "" : ic(icone)) + esc(rot) + "</button>";
  }

  // As marcas dos servicos do Google, as mesmas do programa (app/js/30-email-oauth.js).
  var SIMB_G = {
    google: '<svg class="eo-simbolo" viewBox="0 0 48 48" aria-hidden="true">' +
    '<path fill="#EA4335" d="M24 9.5c3.54 0 6.71 1.22 9.21 3.6l6.85-6.85C35.9 2.38 30.47 0 24 0 14.62 0 6.51 5.38 2.56 13.22l7.98 6.19C12.43 13.72 17.74 9.5 24 9.5z"/>' +
    '<path fill="#4285F4" d="M46.98 24.55c0-1.57-.15-3.09-.38-4.55H24v9.02h12.94c-.58 2.96-2.26 5.48-4.78 7.18l7.73 6c4.51-4.18 7.09-10.36 7.09-17.65z"/>' +
    '<path fill="#FBBC05" d="M10.53 28.59c-.48-1.45-.76-2.99-.76-4.59s.27-3.14.76-4.59l-7.98-6.19C.92 16.46 0 20.12 0 24c0 3.88.92 7.54 2.56 10.78l7.97-6.19z"/>' +
    '<path fill="#34A853" d="M24 48c6.48 0 11.93-2.13 15.89-5.81l-7.73-6c-2.15 1.45-4.92 2.3-8.16 2.3-6.26 0-11.57-4.22-13.47-9.91l-7.98 6.19C6.51 42.62 14.62 48 24 48z"/></svg>',
    gmail: '<svg class="eo-simbolo" viewBox="0 0 24 24" aria-hidden="true"><path fill="#4285F4" d="M2 6.5V18a1.5 1.5 0 0 0 1.5 1.5H6.5V11l-4.5-4.5Z"></path><path fill="#34A853" d="M17.5 19.5h3A1.5 1.5 0 0 0 22 18V6.5L17.5 11Z"></path><path fill="#FBBC04" d="M17.5 5.5V11L22 6.5V5.3c0-1.3-1.5-2-2.5-1.3Z"></path><path fill="#EA4335" d="M6.5 11V5.5L12 9.6l5.5-4.1V11L12 15.1Z"></path><path fill="#C5221F" d="M2 5.3v1.2L6.5 11V5.5L4.5 4C3.5 3.3 2 4 2 5.3Z"></path></svg>',
    agenda: '<svg class="eo-simbolo" viewBox="0 0 24 24" aria-hidden="true"><rect x="3" y="3" width="18" height="18" rx="2.5" fill="#fff" stroke="#4285F4" stroke-width="2"></rect><path fill="#4285F4" d="M3 5.5A2.5 2.5 0 0 1 5.5 3h13A2.5 2.5 0 0 1 21 5.5V8H3Z"></path><text x="12" y="18" text-anchor="middle" font-family="Arial,sans-serif" font-size="8.5" font-weight="700" fill="#1967D2">31</text></svg>',
    meet: '<svg class="eo-simbolo" viewBox="0 0 24 24" aria-hidden="true"><path fill="#00832D" d="M14 12l2.6 2.3 3.4 2.2V7.5l-3.4 2.2Z"></path><path fill="#0066DA" d="M3 15.5v3A1.5 1.5 0 0 0 4.5 20h3v-4.5Z"></path><path fill="#E94235" d="M7.5 4 3 8.5h4.5Z"></path><path fill="#2684FC" d="M3 8.5h4.5v7H3Z"></path><path fill="#00AC47" d="M15.5 16.3 14 12v5.5a1.5 1.5 0 0 1-1.5 1.5H7.5v-4.5h6.5Z"></path><path fill="#FFBA00" d="M12.5 4h-5v4.5H14V5.5A1.5 1.5 0 0 0 12.5 4Z"></path><path fill="#00832D" d="M7.5 8.5H14V12l-6.5 3.5Z"></path></svg>',
    drive: '<svg class="eo-simbolo" viewBox="0 0 24 24" aria-hidden="true"><path fill="#0066DA" d="m3.5 17.3.9 1.6c.2.3.5.6.8.7L8.3 14H2.1c0 .4.1.7.3 1Z"></path><path fill="#00AC47" d="M12 8.2 8.9 2.8c-.3.2-.6.4-.8.7L2.4 13c-.2.3-.3.7-.3 1h6.2Z"></path><path fill="#EA4335" d="M18.8 19.6c.3-.2.6-.4.8-.7l.4-.6 1.7-3c.2-.3.3-.7.3-1h-6.2l1.3 2.6Z"></path><path fill="#00832D" d="M12 8.2 15.1 2.8c-.3-.2-.7-.3-1-.3H9.9c-.4 0-.7.1-1 .3Z"></path><path fill="#2684FC" d="M15.7 14H8.3l-3.1 5.6c.3.2.7.3 1 .3h11.6c.4 0 .7-.1 1-.3Z"></path><path fill="#FFBA00" d="m18.8 8.6-2.9-5c-.2-.3-.5-.6-.8-.8L12 8.2l3.7 5.8h6.2c0-.4-.1-.7-.3-1Z"></path></svg>'
  };
  var SERV_G = [["mail.google.com", "Gmail", "ler e enviar, com Aprovações", "M", "#EA4335"], ["calendar.events", "Agenda e Meet", "criar e atualizar eventos", "31", "#1A73E8"], ["drive.file", "Drive · enviar", "só o que o Paulus criou", "D", "#FBBC04"], ["drive.readonly", "Drive · ler", "cópia das pastas escolhidas", "D", "#34A853"]];
  function modalCab(rot) { return '<div class="modal-cab"><span class="rotulo" id="modal-titulo">' + esc(rot) + '</span><button type="button" class="btn-icone" data-a="fecharModal" aria-label="Fechar">' + ic("close", "s18") + "</button></div>"; }
  function modalPe(botao) { return '<div class="modal-pe"><button type="button" class="btn-texto-mudo" data-a="fecharModal">Cancelar</button>' + botao + "</div>"; }
  function modalHtml() {
    var M = E.modal, larga = /^(nf(Emitir|Clientes|Parametros|Substituir)|contaCadastro|escContas)$/.test(M.tipo), extrato = M.tipo === "contaExtrato";
    var h = '<div class="veu forte" data-a="fecharModal"></div><div class="modal' + (larga ? " larga" : "") + (extrato ? " extrato" : "") + " tipo-" + M.tipo + '" role="dialog" aria-modal="true" aria-labelledby="modal-titulo">';
    if (/^nf/.test(M.tipo)) {
      h += nfModalHtml(M);
    } else if (M.tipo === "membro") {
      var okM = /^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(M.v.email || "") && (M.v.nome || "").trim();
      h += modalCab(M.novo ? "Convidar para a equipe" : "Editar pessoa") + '<div class="modal-corpo pilha" style="gap:14px">' +
        '<label class="campo-adm"><span class="rot">Nome</span><span class="caixa-campo"><input id="mb-nome" data-in="membroCampo" data-k="nome" value="' + esc(M.v.nome || "") + '" autocomplete="off"></span></label>' +
        '<label class="campo-adm"><span class="rot">E-mail</span><span class="caixa-campo"><input data-in="membroCampo" data-k="email" value="' + esc(M.v.email || "") + '" placeholder="nome@paulus.ia.br" autocomplete="off" spellcheck="false"></span></label>' +
        '<div class="campo-adm"><span class="rot">Papel</span>' + seg("membro.papel", [["dono", "Dono"], ["financeiro", "Financeiro"], ["suporte", "Suporte"]], M.v.papel) + "</div>" +
        '<p class="nota-campo">' + (desligado(cfg("equipe"))
          ? (M.novo ? "Ela recebe um e-mail com o link do convite, válido por 7 dias. A liberação no Cloudflare Access ainda é à mão: quando ela aceitar, inclua o e-mail na política do Access do painel." : "Mudar o e-mail troca quem entra: o novo recebe um convite e o antigo sai da equipe. No Cloudflare Access, a troca ainda é à mão.")
          : (M.novo ? "Ela recebe um e-mail com o link para entrar, válido por 7 dias. No primeiro acesso, o Cloudflare Access manda um código para esse mesmo e-mail, e o painel libera o endereço sozinho." : "Mudar o e-mail troca quem entra: o endereço antigo sai do Cloudflare Access e o novo recebe um convite.")) + "</p></div>" +
        modalPe('<button type="button" class="btn-acao" data-a="membroSalvar"' + (okM ? "" : " disabled") + ">" + (M.novo ? ic("send") + "Enviar convite" : "Salvar") + "</button>");
    } else if (M.tipo === "membroExcluir") {
      h += modalCab(M.convite ? "Cancelar convite" : "Excluir da equipe") + '<div class="modal-corpo"><p class="t135">' + (M.convite ? "O link enviado para " + esc(M.email) + " deixa de funcionar." : esc(M.nome || M.email) + " (" + esc(M.email) + ") perde o acesso a este painel" + (desligado(cfg("equipe")) ? ". O endereço continua na política do Cloudflare Access até você tirar à mão." : ", e o endereço sai do Cloudflare Access.")) + "</p></div>" +
        modalPe('<button type="button" class="btn-acao perigo-cheio" data-a="membroExcluirOk">' + (M.convite ? "Cancelar convite" : "Excluir") + "</button>");
    } else if (M.tipo === "escContas") {
      var todasC = (dadosDe("contas") || {}).contas, qn = norm(M.q || "");
      // Duas colunas: a esquerda as contas que ainda nao entraram (com a busca); clicar joga para a direita, e clicar la devolve.
      var lc = (todasC || []).filter(function (c) { return !M.sel[c.id] && (!qn || norm([c.nome, c.email, c.escritorio && c.escritorio.nome].join(" ")).indexOf(qn) >= 0); });
      var escol = Object.keys(M.sel).filter(function (k) { return M.sel[k]; }).map(function (k) { return (todasC || []).filter(function (x) { return String(x.id) === k; })[0] || ((U.emails.escolhidas || []).filter(function (x) { return String(x.id) === k; })[0]); }).filter(Boolean);
      var nS = escol.length;
      var opE = function (c, dentro) {
        return '<button type="button" class="escm-op" data-a="escMarcar" data-id="' + esc(c.id) + '" title="' + (dentro ? "Tirar da lista" : "Adicionar") + '"><span class="txt2"><b>' + esc(c.nome) + "</b><small>" + esc([c.email, c.escritorio && c.escritorio.nome].filter(Boolean).join(" · ")) + "</small></span>" + ic(dentro ? "close" : "add") + "</button>";
      };
      h += modalCab("Escolher contas") + '<div class="modal-corpo escm-corpo"><div class="escm-col"><span class="escm-tit">Contas</span><span class="caixa-campo fundo escm-busca">' + ic("search") + '<input id="escm-q" data-in="escmQ" value="' + esc(M.q || "") + '" placeholder="Buscar por nome, e-mail ou escritório" autocomplete="off"></span>' +
        '<div class="escm-lista">' + (!todasC ? '<p class="nf-cli-vazio">Carregando contas…</p>' : lc.length ? lc.map(function (c) { return opE(c, false); }).join("") : '<p class="nf-cli-vazio">' + (qn ? "Nenhuma conta com “" + esc(M.q) + "”." : "Todas as contas já estão na lista.") + "</p>") + "</div></div>" +
        '<div class="escm-col"><span class="escm-tit">Recebem<b>' + nS + "</b></span>" +
        '<div class="escm-lista escm-dir">' + (nS ? escol.map(function (c) { return opE(c, true); }).join("") : '<p class="nf-cli-vazio">Clique numa conta para ela entrar aqui.</p>') + "</div></div></div>" +
        modalPe('<button type="button" class="btn-acao" data-a="escConfirmar">' + (nS ? "Adicionar " + nS + (nS === 1 ? " conta" : " contas") : "Sem contas") + "</button>");
    } else if (M.tipo === "google") {
      // O mesmo desenho das Conexoes do assistente (08-boas-vindas.css): a conta, e uma linha por servico com a marca, o que faz e o interruptor.
      var n = SERV_G.filter(function (s) { return M.ligados[s[0]]; }).length;
      var linhaG = function (k, marca, nome, desc, junto) {
        var on = !!M.ligados[k];
        return '<div class="g-servico' + (on ? " on" : "") + (junto ? " junto" : "") + '"' + (junto ? ' title="Vem com a Agenda: a mesma permissão"' : ' role="switch" tabindex="0" aria-checked="' + on + '" data-a="googleServico" data-k="' + k + '"') + ">" +
          '<span class="g-marca">' + SIMB_G[marca] + '</span><span class="g-nome">' + esc(nome) + '</span><span class="g-desc">' + esc(desc) + '</span><span class="interruptor-min' + (on ? " on" : "") + '"></span></div>';
      };
      h += modalCab("Permissões do Google") + '<div class="modal-corpo">' +
        '<span class="rotulo">Conta</span><div class="g-conta"><span class="g-marca">' + SIMB_G.google + '</span><span class="txt2"><b>' + esc(M.nome) + "</b><small>" + esc(M.email) + '</small></span><span class="etiqueta-ok">conectado</span></div>' +
        '<span class="rotulo">O que autorizar</span><div class="g-servicos">' +
        linhaG("mail.google.com", "gmail", "Gmail", "ler e enviar, com Aprovações") +
        linhaG("calendar.events", "agenda", "Agenda", "ler e criar eventos") +
        linhaG("calendar.events", "meet", "Meet", "criar reuniões nos eventos", true) +
        linhaG("drive.file", "drive", "Drive", "só os arquivos que o Paulus envia") +
        linhaG("drive.readonly", "drive", "Drive", "ler as pastas escolhidas") +
        '</div><p class="nota-campo">Desligar um serviço revoga só esse escopo no Google. Com todos desligados, o token inteiro é revogado e o Paulus da pessoa pede o consentimento de novo.</p>' +
        (pode("google.desvincular") ? (function () {
          var fila = naFila("google.desvincular", M.id);
          return '<div class="painel g-desvincular"><div class="painel-cab secao-cab"><span class="rotulo">Desvincular conta Google</span></div><div class="linha"><span class="txt2"><b>Tira a conta Google desta conta</b><small>Revoga todas as permissões de uma vez. Para voltar, a pessoa entra de novo com o Google no Paulus.</small></span>' +
            '<button type="button" class="mini vermelho" data-a="contaDesvincular" data-id="' + esc(M.id) + '"' + attrDis(fila, "já está na fila de alterações") + ">" + (fila ? "Na fila" : "Desvincular") + "</button></div></div>";
        })() : "") + "</div>" +
        modalPe('<button type="button" class="btn-acao" data-a="googleAplicar" id="modal-ok">Aplicar</button>');
    } else if (M.tipo === "endereco") {
      var ch = M.check || { msg: "", cor: "var(--ink3)", ok: false };
      var livres = ((dadosDe("tuneis") || {}).livres || []);
      // Atual -> novo lado a lado; o campo com o sufixo; os livres como atalho; o que acontece, em tres linhas curtas.
      var novoTxt = (M.novo || "").trim().toLowerCase();
      h += modalCab("Alterar endereço") + '<div class="modal-corpo">' +
        '<div class="end-atual"><span>Endereço atual</span><b>' + esc(M.slug) + "<span>.paulus.ia.br</span></b></div>" +
        '<label class="campo-adm"><span class="rot">Endereço novo</span><span class="caixa-campo mono fundo"><input id="modal-slug" data-in="slugNovo" value="' + esc(M.novo) + '" placeholder="nome-do-escritorio" spellcheck="false" autocapitalize="none" maxlength="24" aria-describedby="modal-slug-msg"><span class="sufixo">.paulus.ia.br</span></span>' +
        '<span class="msg-slug" id="modal-slug-msg" aria-live="polite" style="color:' + ch.cor + '">' + (ch.msg ? "<i></i>" + esc(ch.msg) : "") + "</span></label>" +
        (livres.length ? '<div class="end-livres"><span class="rot-livres">Livres</span>' + livres.map(function (l) { return '<button type="button" class="chip" data-a="usarLivre" data-v="' + esc(l) + '">' + esc(l) + "</button>"; }).join("") + "</div>" : "") +
        '<ul class="end-passos"><li>' + ic("link_off") + "O endereço antigo sai do ar e fica livre para outro escritório.</li><li>" + ic("dns") + "O novo é criado no mesmo túnel, sem reinstalar nada.</li><li>" + ic("sync") + "O Paulus do escritório passa a usar o novo na próxima conexão.</li></ul></div>" +
        modalPe('<button type="button" class="btn-acao" data-a="enderecoConfirmar" id="modal-ok"' + (ch.ok ? "" : " disabled") + ">Trocar endereço</button>");
    } else if (M.tipo === "plano") {
      var v = numDec(M.valor), va = numDec(M.anual), t = numDec(M.tokens) * 1e6, cc = t ? custoCheio(t, M.usd) : null;
      h += modalCab("Editar plano") + '<div class="modal-corpo"><b style="font:500 15px var(--sans)">' + esc(M.nome) + ' <span class="num s11 c-ink3">' + esc(M.id) + "</span></b>" +
        '<div class="grade-campos">' + campoModal("modal-valor", "Valor por mês", M.valor, "planoValor", "R$") + campoModal("modal-anual", "Valor por ano", M.anual, "planoAnual", "R$") + campoModal("modal-tokens", "Créditos por mês", M.tokens, "planoTokens", "", "M") + "</div>" +
        '<span class="t125">' + (t ? esc(brl(v / (t / 1e6))) + " por milhão" + (cc != null ? " · se o assinante usar tudo, custa " + esc(brl(cc)) + " no " + esc(M.modelo || "modelo do plano") : "") + (va && v ? " · o anual sai " + Math.round((1 - va / (v * 12)) * 100) + "% abaixo de 12 meses" : "") : "Preencha valor e créditos.") + "</span>" +
        '<p class="nota-campo">Quem já assina continua pagando o valor de agora até a próxima renovação; o PUT no preapproval do Mercado Pago sai na publicação.</p></div>' +
        modalPe('<button type="button" class="btn-acao" data-a="planoSalvar" id="modal-ok"' + (v > 0 && va > 0 && t > 0 ? "" : " disabled") + ">Salvar</button>");
    } else if (M.tipo === "contaPlano") {
      h += modalCab("Alterar plano") + '<div class="modal-corpo"><div class="quem"><b>' + esc(M.nome) + "</b><span>" + esc(M.email) + "</span></div>" +
        (M.planos ? '<div class="caixa-escura">' + M.planos.map(function (p) {
          var on = M.escolhido === p.id;
          return '<button type="button" class="linha-btn escolha-plano' + (on ? " on" : "") + '" data-a="contaPlanoEscolher" data-id="' + esc(p.id) + '" aria-pressed="' + on + '"><span class="txt2"><b>' + esc(p.nome) + (p.id === M.atual ? ' <span class="c-ink3">· atual</span>' : "") + "</b><small>" + esc(brl(p.valor)) + "/mês</small></span>" + (on ? ic("check") : "") + "</button>";
        }).join("") + "</div>" : M.erro ? '<p class="erro-linha">' + ic("warning") + "<span>Não foi possível ler os planos: " + esc(M.erro) + "</span></p>" : '<p class="carregando">Carregando os planos…</p>') +
        '<p class="nota-campo">A troca entra na fila e vale a partir da próxima renovação; o ciclo de agora continua no plano atual.</p></div>' +
        modalPe('<button type="button" class="btn-acao" data-a="contaPlanoSalvar" id="modal-ok"' + (M.escolhido && M.escolhido !== M.atual ? "" : " disabled") + ">Feito</button>");
    } else if (M.tipo === "contaCadastro") {
      var cc = function (k, rot) { return '<label class="campo-adm"><span class="rot">' + esc(rot) + '</span><span class="caixa-campo fundo"><input id="cad-' + k + '" data-in="cadCampo" data-k="' + k + '" value="' + esc(M.v[k]) + '"></span></label>'; };
      h += modalCab("Editar cadastro") + '<div class="modal-corpo"><div class="quem"><b>' + esc(M.nome) + "</b><span>" + esc(M.email) + "</span></div>" +
        cc("escritorio", "Escritório") +
        '<div class="grade-campos">' + cc("documento", "CPF ou CNPJ") + cc("telefone", "Telefone ou WhatsApp") + cc("oab", "OAB, RG ou CNH") + cc("cep", "CEP") + "</div>" +
        '<div class="grade-campos rua">' + cc("logradouro", "Rua") + cc("numero", "Número") + "</div>" +
        '<div class="grade-campos">' + cc("complemento", "Complemento") + cc("bairro", "Bairro") + "</div>" +
        '<div class="grade-campos rua"><label class="campo-adm"><span class="rot">Cidade</span><span class="caixa-campo fundo"><input id="cad-cidade" data-in="cadCidade" list="cad-cidades" autocomplete="off" value="' + esc(M.v.cidade) + '" placeholder="Comece a digitar"></span><datalist id="cad-cidades"></datalist></label>' +
        '<label class="campo-adm"><span class="rot">UF</span><span class="caixa-campo fundo"><select id="cad-uf" data-in="cadUf"><option value="">—</option>' +
        UFS.map(function (u) { return '<option value="' + u + '"' + (M.v.uf === u ? " selected" : "") + ">" + u + "</option>"; }).join("") + "</select></span></label></div>" +
        '<p class="nota-campo">O CPF ou CNPJ e o endereço vão na nota fiscal da assinatura. As mudanças entram na fila e valem ao confirmar; o titular vê os dados novos em Seus dados, no Paulus.</p></div>' +
        modalPe('<button type="button" class="btn-acao" data-a="contaCadastroSalvar" id="modal-ok">Feito</button>');
    } else if (M.tipo === "contaExtrato") {
      var SIT_FAT = { pago: ["paga", "var(--ok)"], pendente: ["pendente", "var(--atencao)"], recusado: ["recusada", "var(--erro)"], reembolsado: ["reembolsada", "var(--ink3)"] };
      var cols = "88px minmax(120px,1fr) minmax(150px,1.1fr) 100px 128px 100px 56px 32px 32px";
      var fT = M.filtro || "todos", fP = M.periodo || "tudo", agoraE = Date.now(), anoE = String(new Date().getFullYear());
      var itensF = M.itens.filter(function (x) {
        var okT = fT === "todos" || (fT === "reembolsados" ? !!x.reembolso : !x.reembolso && x.tipo === fT);
        var dd = (agoraE - Date.parse(x.quando)) / 864e5;
        var dia = String(x.quando).slice(0, 10);
        var okP = fP === "tudo" || (fP === "custom" ? dia >= M.de && dia <= M.ate : fP === "ano" ? dia.slice(0, 4) === anoE : dd <= Number(fP));
        return okT && okP;
      });
      var linhasE = itensF.map(function (x) {
        var st = SIT_FAT[x.reembolso ? "reembolsado" : (x.situacao || "pago")] || [x.situacao, "var(--ink3)"], nf = x.nfse;
        var arq = function (tipo, icone) { return nf ? '<a class="btn-icone ext-arq" href="' + NF + "notas/" + esc(nf.id) + "/" + tipo + (tipo === "pdf" ? "?baixar=1" : "") + '" download aria-label="' + tipo.toUpperCase() + " da NFS-e " + esc(nf.numero) + '" title="' + tipo.toUpperCase() + '">' + ic(icone) + "</a>" : '<span class="c-ink3">—</span>'; };
        return '<div class="grade-linha p10"><span class="num">' + esc(ddmmaaaa(x.quando)) + '</span><span class="corta">' + esc(descPag(x, M)) + "</span>" + formaHtml(x.forma) +
          '<span class="num dir">' + esc(brl(x.valor)) + '</span><span class="corta">' + esc(MODALIDADE[x.tipo] || "—") + "</span>" +
          sit(st[0], st[1]) + '<span class="num"' + (nf && nf.estado && nf.estado !== "emitida" ? ' title="NFS-e ' + esc(nf.estado === "substituida" ? "substituída" : nf.estado) + '"' : "") + ">" + esc(nf ? nf.numero : "—") + "</span>" + arq("pdf", "picture_as_pdf") + arq("xml", "code") + "</div>";
      }).join("") || '<p class="vazio-linha">Nenhum pagamento com esse filtro.</p>';
      var pago = itensF.reduce(function (s, x) { return s + (x.reembolso ? 0 : Number(x.valor) || 0); }, 0);
      if (itensF.length) linhasE += '<div class="grade-linha linha-total"><span class="tot-rot"><b>Total pago</b><small>' + itensF.length + (itensF.length === 1 ? " lançamento" : " lançamentos") + "</small></span><span></span>" +
        '<span class="num dir tot-v">' + esc(brl(pago)) + '</span><span class="extrato-baixar">' +
        '<button type="button" class="mini" data-a="extratoJson">' + ic("download") + 'JSON</button><button type="button" class="mini" data-a="extratoPdf">' + ic("picture_as_pdf") + "PDF</button></span></div>";
      var A_ = M.ass, SIT_PRE = { authorized: ["ativa", "var(--ok)"], paused: ["pausada", "var(--atencao)"], cancelled: ["cancelada", "var(--erro)"], pending: ["pendente", "var(--atencao)"], expired: ["vencida", "var(--erro)"], refunded: ["reembolsada", "var(--ink3)"] };
      var sa = A_ ? (SIT_PRE[A_.situacao] || [A_.situacao, "var(--ink3)"]) : null;
      var tile = function (rot, val, extra) { return '<div class="ass-tile"><span class="ass-rot">' + rot + '</span><span class="ass-val">' + val + "</span>" + (extra || "") + "</div>"; };
      var cardAss = !A_ ? '<div class="ass-card vazio"><span class="ass-marca mp"><img src="' + ASSETS + 'mercadopago-cor.png" alt="Mercado Pago"></span><span class="txt2"><b>Sem assinatura no Mercado Pago</b><small>Os pagamentos avulsos aparecem na tabela abaixo.</small></span></div>' :
        '<div class="ass-card"><div class="ass-topo"><img class="ass-logo" src="' + ASSETS + 'mercadopago-cor.png" alt="Mercado Pago"><span class="ass-linha"><b>' + esc(MODALIDADE[A_.periodo === "anual" ? "anual" : A_.periodo === "avulso" ? "avulso" : "assinatura"]) + "</b>" +
        (M.plano ? "<span>Plano " + esc(M.plano) + "</span>" : "") + (M.valor != null ? "<span>" + esc(brl(M.valor)) + (A_.periodo === "anual" ? "/ano" : "/mês") + "</span>" : "") + "</span>" +
        '<span class="ass-sit"><i style="background:' + sa[1] + '"></i>' + esc(sa[0]) + "</span></div>" +
        '<div class="ass-tiles">' + tile("Assinante desde", esc(A_.desde ? ddmmaaaa(A_.desde) : "—")) +
        tile(A_.prepago ? "Pago até" : "Próxima cobrança", esc(A_.prepago ? (M.pagoAte ? ddmmaaaa(M.pagoAte) : "—") : (M.proxima ? ddmmaaaa(M.proxima) : "—")) +
          (!A_.prepago && A_.situacao === "authorized" && pode("conta.cancelar") ? '<button type="button" class="btn-icone ass-copiar" data-a="contaPausar" data-id="' + esc(M.id) + '"' + attrDis(naFila("conta.pausar", M.id), "já está na fila de alterações") + ' aria-label="Pausar a cobrança" title="Pausar a cobrança">' + ic("pause_circle") + "</button>" : "")) +
        (A_.id ? tile("ID no Mercado Pago", '<span class="ass-id-linha"><span class="ass-id" title="' + esc(A_.id) + '">' + esc(A_.id) + '</span><button type="button" class="btn-icone ass-copiar" data-a="copiarTexto" data-t="' + esc(A_.id) + '" aria-label="Copiar o ID" title="Copiar">' + ic("content_copy") + "</button></span>") : "") + "</div></div>";
      h += modalCab("Extrato") + '<div class="modal-corpo">' + (M.embutido ? "" : '<div class="quem"><b>' + esc(M.nome) + "</b><span>" + esc(M.email) + "</span></div>") + cardAss +
        '<div class="barra-filtros">' + seg("extrato.tipo", [["todos", "Todos"], ["assinatura", "Mensalidades"], ["anual", "Anuais"], ["recarga", "Recargas"], ["reembolsados", "Reembolsados"]], fT) +
        seg("extrato.periodo", [["tudo", "Tudo"], ["30", "30 dias"], ["90", "90 dias"]], fP).replace(/<\/div><\/div>$/, "") +
        '<button type="button" class="seg-cal" data-a="extratoCal" aria-pressed="' + (fP === "custom") + '" aria-expanded="' + !!M.cal + '" title="Período específico" aria-label="Período específico">' + ic("calendar_month") +
        "<span>" + (fP === "custom" ? esc(ddmm(M.de) + " – " + ddmm(M.ate)) : "Outro período") + "</span></button></div></div>" + (M.cal ? calHtml(M.cal) : "") + "</div>" +
        '<div class="painel">' + grade(cols, 840, "<span>Data</span><span>Descrição</span><span>Forma</span><span class=\"dir\">Valor</span><span>Modalidade</span><span>Status</span><span>NFS-e</span><span>PDF</span><span>XML</span>", linhasE) + "</div>" +
        "</div>" + '<div class="modal-pe"><button type="button" class="btn-acao" data-a="fecharModal" id="modal-ok">Fechar</button></div>';
    } else if (M.tipo === "tunelHist") {
      h += modalCab("Histórico · " + M.slug + ".paulus.ia.br") + '<div class="modal-corpo"><div class="painel">' +
        (M.itens.length ? M.itens.map(function (x) { return '<div class="linha hist-linha"><span class="num">' + esc(ddmmaaaa(x.quando)) + "</span><span>" + esc(x.texto) + "</span></div>"; }).join("") : '<p class="vazio-linha">Sem eventos registrados.</p>') +
        "</div></div>" + '<div class="modal-pe"><button type="button" class="btn-acao" data-a="fecharModal" id="modal-ok">Fechar</button></div>';
    } else if (M.tipo === "conta") {
      // O mesmo "Minha conta" do Paulus e do Acesso externo (00-acesso.js + 16-dialogos.js): cabeca do dialogo, quem e, as acoes em linhas, Fechar.
      var S = E.sessao || {}, emailS = S.email || (S.access && S.access.email) || "", nomeS = nomeCompletoSessao() || emailS;
      var cabD = function (tit, ctx) { return '<div class="dialogo-cabeca"><span class="dialogo-titulos"><h2 id="modal-titulo">' + esc(tit) + '</h2><span class="dialogo-contexto">' + esc(ctx) + '</span></span><button type="button" class="btn-icone dialogo-fechar" data-a="fecharModal" title="Fechar" aria-label="Fechar">' + ic("close") + "</button></div>"; };
      if (M.passo !== "todas") {
        var linhaC = function (acao, icone, titulo, sub, tom) { return '<button type="button" class="conta-acao' + (tom ? " " + tom : "") + '" data-a="' + acao + '"><span class="caixa-tipo">' + ic(icone) + '</span><span class="duas-linhas"><b>' + titulo + "</b><small>" + sub + "</small></span>" + ic("chevron_right") + "</button>"; };
        h += cabD("Minha conta", "Painel Admin") + '<div class="dialogo-corpo"><div class="conta-cabeca"><span class="cad-avatar">' + esc(iniciaisAdm(nomeS)) + '</span><span class="duas-linhas"><b>' + esc(nomeS) + "</b><small>" + esc([emailS, S.papel].filter(Boolean).join(" · ")) + "</small></span></div>" +
          '<div class="conta-acoes">' + linhaC("contaTodas", "group", "Encerrar todas as sessões", "todos os aparelhos em que você entrou saem, este também", "perigo") +
          linhaC("sair", "logout", "Sair", "encerra esta sessão neste aparelho") + "</div>" +
          '<p class="conta-nota">Você entra pelo Cloudflare Access, com o código que chega no seu e-mail.</p></div>' +
          '<div class="dialogo-pe"><span class="cresce"></span><button type="button" class="primario" data-a="fecharModal" id="modal-ok">Fechar</button></div>';
      } else {
        h += cabD("Encerrar todas as sessões?", "Minha conta") + '<div class="dialogo-corpo"><p>Todos os aparelhos em que você entrou saem agora, este também. Para entrar de novo: o código do Cloudflare Access no seu e-mail.</p></div>' +
          '<div class="dialogo-pe"><span class="cresce"></span><button type="button" class="dialogo-cancelar" data-a="contaVoltar">Cancelar</button><button type="button" class="perigo" data-a="contaSairTodas">Encerrar</button></div>';
      }
    } else if (M.tipo === "retroagir") {
      var P = M.pub, okR = M.texto.trim() === "retroagir";
      h += modalCab("Retroagir publicação") + '<div class="modal-corpo"><p class="t13" style="line-height:1.55;font-size:13.5px">Desfaz a publicação de <b class="c-ink" style="font-weight:500">' + esc(quando(P.quando)) + "</b> (commit " + esc(String(P.commit).slice(0, 7)) + "): " + (P.n || 0) + (P.n === 1 ? " alteração volta" : " alterações voltam") + " ao estado anterior, num commit novo de reversão na main. As publicações depois dela não mudam.</p>" +
        '<div class="lista-commit"><span><span>—</span>' + esc(P.resumo || "") + "</span></div>" +
        '<p class="nota-campo">O que já saiu para fora não volta: e-mails enviados, cobranças feitas no Mercado Pago e notas emitidas continuam valendo.</p>' +
        '<label class="campo-adm"><span class="rot">Digite <code class="cod">retroagir</code> para confirmar</span><span class="caixa-campo mono fundo"><input id="modal-retro" data-in="retroTexto" value="' + esc(M.texto) + '" placeholder="retroagir" spellcheck="false" autocomplete="off" autocapitalize="none"></span></label>' +
        (M.erro ? '<p class="erro-campo">' + esc(M.erro) + "</p>" : "") + "</div>" +
        modalPe('<button type="button" class="btn-acao' + (okR ? " perigo-cheio" : "") + '" data-a="retroagir" id="modal-ok"' + (okR && !M.enviando ? "" : " disabled") + ">" + ic("undo") + (M.enviando ? "Retroagindo…" : "Retroagir") + "</button>");
    } else if (M.tipo === "commit") {
      h += modalCab("Commitar e pushar");
      if (M.resultado) {
        var R = M.resultado, falhas = (R.resultados || []).filter(function (x) { return !x.ok; });
        var porId = {}; (M.itens || []).forEach(function (a) { porId[a.id] = a; });
        h += '<div class="modal-corpo"><p class="t13" style="line-height:1.55"><b class="c-ink" style="font-weight:500">' + ((R.resultados || []).length - falhas.length) + " de " + (R.resultados || []).length + "</b> alterações foram para o ar" + (R.publicacao && R.publicacao.commit ? " no commit " + esc(String(R.publicacao.commit).slice(0, 7)) : "") + ".</p>" +
          (falhas.length ? '<div class="lista-commit"><span class="rotulo">Falharam</span>' + falhas.map(function (x) { var a = porId[x.id]; return '<span class="falhou"><span>—</span>' + esc((a ? a.texto : x.id) + ": " + (x.erro || "sem motivo")) + "</span>"; }).join("") + "</div>" +
            '<p class="nota-campo">As que falharam continuam na fila; as outras não são desfeitas.</p>' : "") + "</div>" +
          '<div class="modal-pe"><button type="button" class="btn-acao" data-a="fecharModal" id="modal-ok">Fechar</button></div>';
      } else {
        var ps = E.pendentes, okTxt = M.texto.trim() === "comitar e pushar";
        h += '<div class="modal-corpo"><p class="t13" style="line-height:1.55;font-size:13.5px"><b class="c-ink" style="font-weight:500">' + ps.length + (ps.length === 1 ? " alteração vai" : " alterações vão") + "</b> para o ar, uma depois da outra. Se uma falhar, as outras ficam feitas e ela volta para a fila com o motivo.</p>" +
          '<div class="lista-commit">' + ps.slice(0, 4).map(function (a) { return "<span><span>—</span>" + esc(a.texto) + "</span>"; }).join("") + (ps.length > 4 ? '<span class="mais">+ ' + (ps.length - 4) + " alterações</span>" : "") + "</div>" +
          '<label class="campo-adm"><span class="rot">Digite <code class="cod">comitar e pushar</code> para confirmar</span><span class="caixa-campo mono fundo"><input id="modal-commit" data-in="commitTexto" value="' + esc(M.texto) + '" placeholder="comitar e pushar" spellcheck="false" autocomplete="off" autocapitalize="none"></span></label>' +
          (M.erro ? '<p class="erro-campo">' + esc(M.erro) + "</p>" : "") + "</div>" +
          modalPe('<button type="button" class="btn-acao' + (okTxt ? " verde" : "") + '" data-a="publicar" id="modal-ok"' + (okTxt && !M.enviando ? "" : " disabled") + ">" + ic("publish") + (M.enviando ? "Publicando…" : "Commitar e pushar") + "</button>");
      }
    }
    return h + "</div>";
  }
  /* ---------- os pop-ups das notas fiscais ---------- */
  function nfId(k) { return "nf-c-" + String(k).replace(/[^A-Za-z0-9_-]/g, "-"); }
  function nfCampo(k, rot, extra) {
    var v = E.modal.v[k], nota = (E.modal.cnpjNota || {})[k];
    return '<label class="campo-adm"><span class="rot">' + esc(rot) + '</span><span class="caixa-campo fundo"><input id="' + nfId(k) + '" data-in="nf" data-k="' + esc(k) + '" value="' + esc(v == null ? "" : v) + '"' + (extra || "") + ' autocomplete="off"></span>' +
      (nota ? '<span class="nota-campo" role="status">' + esc(nota) + "</span>" : "") + "</label>";
  }
  /* O CNPJ completo e certo no documento (do tomador ou do PAVLVS, em
     Parâmetros) preenche os campos vizinhos com os dados da Receita, pela
     BrasilAPI (assets/cnpj.js): só os vazios ou os que a consulta anterior
     preencheu. No prestador as chaves são as de Parâmetros; no tomador, as
     de NF_TOMADOR com o mesmo prefixo. */
  var NF_CNPJ_PRESTADOR = { razao_social: "razao_social", municipio: "codigo_municipio_ibge", "endereco.cep": "cep", "endereco.logradouro": "logradouro",
    "endereco.numero": "numero", "endereco.complemento": "complemento", "endereco.bairro": "bairro", email: "email", telefone: "telefone" };
  var NF_CNPJ_TOMADOR = { nome: "razao_social", email: "email", telefone: "telefone", cep: "cep", logradouro: "logradouro", numero: "numero",
    complemento: "complemento", bairro: "bairro", cmun: "codigo_municipio_ibge", uf: "uf" };
  function nfCnpj(el) {
    var M = E.modal, k = el.dataset.k;
    if (!M || !M.v || !/(^|\.)documento$/.test(k) || !window.PavlvsCnpj || el.disabled) return;
    var cnpj = PavlvsCnpj.paraConsultar(el.value);
    M.cnpjLido = M.cnpjLido || {}; M.cnpjNota = M.cnpjNota || {}; M.peloCnpj = M.peloCnpj || {};
    if (cnpj === (M.cnpjLido[k] || "")) return;
    M.cnpjLido[k] = cnpj;
    // O pop-up é redesenhado inteiro: o foco volta a quem estava com ele
    // (a pessoa pode já estar em outro campo quando a resposta chega).
    var redesenhar = function () {
      var ativo = document.activeElement, id = ativo && ativo.id, pos = ativo && ativo.selectionStart;
      renderCamada();
      var i = id && $(id);
      if (i && i !== document.activeElement) { i.focus(); try { if (pos != null) i.setSelectionRange(pos, pos); } catch (x) { /* nada */ } }
    };
    if (!cnpj) { if (M.cnpjNota[k]) { delete M.cnpjNota[k]; redesenhar(); } return; }
    M.cnpjNota[k] = "Consultando a Receita…"; redesenhar();
    var prefixo = k.slice(0, k.length - "documento".length), mapa = prefixo ? NF_CNPJ_TOMADOR : NF_CNPJ_PRESTADOR;
    PavlvsCnpj.consultar(cnpj).then(function (d) {
      if (E.modal !== M || PavlvsCnpj.paraConsultar(M.v[k]) !== cnpj) return;
      var n = 0;
      Object.keys(mapa).forEach(function (c) {
        var alvo = prefixo + c, v = d[mapa[c]] || "", atual = String(M.v[alvo] == null ? "" : M.v[alvo]).trim();
        if (!v || (atual && atual !== M.peloCnpj[alvo])) return;
        M.v[alvo] = v; M.peloCnpj[alvo] = v; n += 1;
        if (mapa[c] === "codigo_municipio_ibge") { NF_MUN[v] = d.municipio + "/" + d.uf; if (M.mun) M.mun[alvo] = {}; }
      });
      M.cnpjNota[k] = PavlvsCnpj.frase(d).replace(" (Receita", (n ? " · " + n + (n === 1 ? " campo preenchido" : " campos preenchidos") : "") + " (Receita");
      redesenhar();
    }, function (e) {
      if (E.modal !== M || PavlvsCnpj.paraConsultar(M.v[k]) !== cnpj) return;
      M.cnpjNota[k] = "Não preenchi pela Receita: " + e.message + "."; redesenhar();
    });
  }
  function nfEscolha(k, rot, opcoes, inp) {
    var v = String(E.modal.v[k] == null ? "" : E.modal.v[k]);
    // O combobox do sistema: um botao com o valor e a seta; a lista abre embaixo, com o escolhido marcado.
    var M = E.modal, vazio = !opcoes.length, ab = !vazio && M.selAberto === k, at = opcoes.filter(function (o) { return String(o[0]) === v; })[0];
    var h = '<div class="campo-adm nf-combo"><span class="rot">' + esc(rot) + '</span><button type="button" id="' + nfId(k) + '" class="caixa-campo fundo nf-combo-btn" data-a="nfComboAbrir" data-k="' + esc(k) + '" aria-haspopup="listbox" aria-expanded="' + ab + '"' + (vazio ? " disabled" : "") + ">" +
      '<span class="corta' + (at ? "" : " c-ink3") + '">' + esc(at ? at[1] : vazio ? "sem opções do emissor" : "escolha") + "</span>" + ic("expand_more") + "</button>";
    if (ab) h += '<div class="nf-cli-lista nf-combo-lista" role="listbox">' + opcoes.map(function (o) {
      var on = String(o[0]) === v;
      return '<button type="button" role="option" aria-selected="' + on + '" class="nf-combo-op' + (on ? " on" : "") + '" data-a="nfComboEscolher" data-k="' + esc(k) + '" data-v="' + esc(o[0]) + '" data-in2="' + esc(inp || "nf") + '"><span>' + esc(o[1]) + "</span>" + (on ? ic("check") : "") + "</button>";
    }).join("") + "</div>";
    return h + "</div>";
  }
  function nfDominio(obj, comCodigo) {
    if (Array.isArray(obj)) return obj.map(function (o) { var k = String(o.codigo != null ? o.codigo : o[0]), n = o.nome != null ? o.nome : o[1]; return [k, (comCodigo ? k + " – " : "") + n]; });
    return Object.keys(obj || {}).sort().map(function (k) { return [k, (comCodigo ? k + " – " : "") + obj[k]]; });
  }
  function nfTexto(k, rot, ph) {
    return '<label class="campo-adm"><span class="rot">' + esc(rot) + '</span><textarea class="area" rows="3" id="' + nfId(k) + '" data-in="nf" data-k="' + esc(k) + '" maxlength="255" placeholder="' + esc(ph || "") + '">' + esc(E.modal.v[k] || "") + "</textarea></label>";
  }
  function nfMarcar(k, rot) {
    return '<label class="nf-marcar"><input type="checkbox" id="' + nfId(k) + '" data-in="nf" data-k="' + esc(k) + '"' + (E.modal.v[k] ? " checked" : "") + "><span>" + esc(rot) + "</span></label>";
  }
  function nfDuas(a, b) { return '<div class="grade-campos">' + a + (b || "<span></span>") + "</div>"; }
  function nfSub(t) { return '<span class="rotulo nf-sub">' + esc(t) + "</span>"; }
  // O município: a pessoa digita o nome ("goi" -> Goiânia/GO) e escolhe na
  // lista; o código IBGE fica escondido em M.v[k] (e num input hidden). Colar
  // os 7 dígitos também serve. Quem já tem código mostra "Nome/UF".
  var NF_UF = { 11: "RO", 12: "AC", 13: "AM", 14: "RR", 15: "PA", 16: "AP", 17: "TO", 21: "MA", 22: "PI", 23: "CE", 24: "RN", 25: "PB", 26: "PE", 27: "AL",
    28: "SE", 29: "BA", 31: "MG", 32: "ES", 33: "RJ", 35: "SP", 41: "PR", 42: "SC", 43: "RS", 50: "MS", 51: "MT", 52: "GO", 53: "DF" };
  var NF_MUN = {}, nfMunPedidos = {};
  function nfMunRotulo(cod) {
    cod = String(cod || "");
    if (!/^\d{7}$/.test(cod)) return cod;
    if (NF_MUN[cod]) return NF_MUN[cod];
    if (!nfMunPedidos[cod]) {
      nfMunPedidos[cod] = 1;
      api("GET", NF + "municipios?q=" + cod).then(function (r) {
        var m = (r.municipios || [])[0];
        NF_MUN[cod] = m ? m.nome + "/" + m.uf : cod + " (fora da tabela do IBGE)";
        renderCamada();
        document.querySelectorAll('input[data-in="nfMun"]').forEach(function (i) { var M = E.modal; if (M && M.v && String(M.v[i.dataset.k]) === cod && document.activeElement !== i) i.value = NF_MUN[cod]; });
      }, function () { delete nfMunPedidos[cod]; });
    }
    return cod;
  }
  function nfMunicipio(k, rot, extra, kUf) {
    var M = E.modal; M.mun = M.mun || {};
    var st = M.mun[k] || {}, cod = String(M.v[k] == null ? "" : M.v[k]), id = nfId(k), lista = id + "-lista";
    var aberto = !!(st.editando && st.res);
    var h = '<div class="nf-mun-par"><div class="campo-adm nf-mun"><label class="rot" for="' + id + '">' + esc(rot) + '</label><span class="caixa-campo fundo"><input id="' + id + '" data-in="nfMun" data-k="' + esc(k) + '" data-uf="' + esc(kUf || "") +
      '" value="' + esc(st.editando ? st.texto : nfMunRotulo(cod)) + '" placeholder="digite o nome (ex.: Goiânia) ou o código IBGE" role="combobox" aria-autocomplete="list" aria-expanded="' + aberto + '" aria-controls="' + lista + '"' +
      (aberto && st.res.length ? ' aria-activedescendant="' + lista + "-" + st.idx + '"' : "") + (extra || "") + ' autocomplete="off" spellcheck="false"></span>' +
      '<input type="hidden" id="' + id + '-codigo" data-codigo="' + esc(k) + '" value="' + esc(cod) + '">';
    if (aberto) {
      h += '<div class="nf-mun-lista" role="listbox" id="' + lista + '" aria-label="Municípios">' + (st.res.length ? st.res.map(function (m, i) {
        return '<button type="button" class="nf-mun-opcao" role="option" id="' + lista + "-" + i + '" aria-selected="' + (i === st.idx) + '" tabindex="-1" data-a="nfMunEscolher" data-mun="' + esc(k) + '" data-i="' + i + '">' +
          esc(m.nome + "/" + m.uf) + "<small>" + esc(m.codigo) + "</small></button>";
      }).join("") : '<span class="nf-mun-vazio">' + esc(st.erro || "Nenhum município com esse nome.") + "</span>") + "</div>";
    } else if (st.editando && String(st.texto || "").trim()) {
      h += '<span class="nf-mun-cod">procurando…</span>';
    }
    // O codigo IBGE num campo proprio: aparece o do municipio escolhido, e pode ser digitado direto (7 digitos).
    h += "</div>" + '<label class="campo-adm"><span class="rot">Código IBGE</span><span class="caixa-campo fundo mono"><input id="' + id + '-ibge" data-in="nfMunCod" data-k="' + esc(k) + '" value="' + esc(M.munCod && M.munCod[k] != null ? M.munCod[k] : cod) + '" inputmode="numeric" maxlength="7" placeholder="0000000" autocomplete="off"' + (extra || "") + ' style="width:0"></span></label>';
    return h + "</div>";
  }
  function nfMunFixar(M, k, m, kUf) {
    M.v[k] = m.codigo;
    NF_MUN[m.codigo] = m.nome + "/" + m.uf;
    if (kUf) M.v[kUf] = m.uf;
    M.mun[k] = {};
    renderCamada();
    var i = $(nfId(k)); if (i) { i.focus(); try { i.setSelectionRange(i.value.length, i.value.length); } catch (x) { /* nada */ } }
  }
  function nfMunDigitar(el) {
    var M = E.modal; if (!M || !M.v) return;
    M.mun = M.mun || {};
    var k = el.dataset.k, t = el.value, kUf = el.dataset.uf, st = M.mun[k] = M.mun[k] || {};
    clearTimeout(st.timer);
    if (/^\s*\d{7}\s*$/.test(t)) {
      var cod = t.replace(/\D/g, "");
      M.v[k] = cod; M.mun[k] = {};
      if (kUf && NF_UF[cod.slice(0, 2)]) M.v[kUf] = NF_UF[cod.slice(0, 2)];
      renderCamada();
      return;
    }
    M.v[k] = "";
    st.editando = true; st.texto = t; st.idx = 0; st.erro = "";
    if (!t.trim()) { st.res = null; st.editando = false; renderCamada(); return; }
    st.res = st.res && st.res.length ? st.res : null;
    renderCamada();
    st.timer = setTimeout(function () {
      api("GET", NF + "municipios?q=" + encodeURIComponent(t)).then(function (r) {
        if (E.modal !== M || st.texto !== t) return;
        st.res = r.municipios || []; st.idx = 0; renderCamada();
      }, function (e) {
        if (E.modal !== M || st.texto !== t || e.status === 401) return;
        st.res = []; st.erro = "Não consegui buscar agora: " + e.message; renderCamada();
      });
    }, 150);
  }
  // As setas andam na lista, Enter escolhe, Esc fecha a lista. true = tratou.
  function nfMunTecla(ev) {
    var el = ev.target, M = E.modal, k = ev.key;
    if (!M || !M.mun || !el || !el.dataset || el.dataset.in !== "nfMun") return false;
    var st = M.mun[el.dataset.k];
    if (!st || !st.editando) return false;
    var n = st.res ? st.res.length : 0;
    if ((k === "ArrowDown" || k === "ArrowUp") && n) { st.idx = ((st.idx + (k === "ArrowDown" ? 1 : -1)) % n + n) % n; renderCamada(); }
    else if (k === "Enter") { if (n) nfMunFixar(M, el.dataset.k, st.res[st.idx], el.dataset.uf); }
    else if (k === "Escape" && st.res) { st.res = null; renderCamada(); }
    else return false;
    ev.preventDefault();
    return true;
  }
  function nfTomadorCampos(prefixo) {
    var c = NF_TOMADOR.map(function (x) {
      if (x[0] === "cmun") return nfMunicipio(prefixo + "cmun", "Município", "", prefixo + "uf");
      return nfCampo(prefixo + x[0], x[1], x[0] === "cep" || x[0] === "documento" || x[0] === "telefone" ? ' inputmode="numeric"' : "");
    });
    var h = "";
    for (var i = 0; i < c.length; i += 2) h += nfDuas(c[i], c[i + 1]);
    return h;
  }
  // Os campos em cards por assunto (como o cadastro na pagina da conta).
  function nfCard(titulo, corpo, dir) { return '<div class="painel nf-card"><div class="painel-cab"><span class="rotulo">' + esc(titulo) + "</span>" + (dir || "") + '</div><div class="nf-card-corpo">' + corpo + "</div></div>"; }
  // Cada subtitulo (nfSub) vira o cabecalho de um card com os campos que vem depois dele.
  function nfEmCards(h) {
    var m = '<span class="rotulo nf-sub">', p = h.split(m); if (p.length < 2) return h;
    var ult = p.length - 1, fecha = p[ult].lastIndexOf("</div>"), resto = p[ult].slice(fecha); p[ult] = p[ult].slice(0, fecha);
    return p[0] + p.slice(1).map(function (x) { var k = x.indexOf("</span>"); return '<div class="painel nf-card"><div class="painel-cab"><span class="rotulo">' + x.slice(0, k) + '</span></div><div class="nf-card-corpo">' + x.slice(k + 7) + "</div></div>"; }).join("") + resto;
  }
  function nfTomadorGrupos(prefixo) {
    var f = function (k, rot, extra) { return k === "cmun" ? nfMunicipio(prefixo + "cmun", "Município", "", prefixo + "uf") : nfCampo(prefixo + k, rot, extra || ""); };
    var num = ' inputmode="numeric"';
    return nfCard("Tomador", nfDuas(f("nome", "Nome ou razão social"), f("documento", "CPF ou CNPJ", num)) + nfDuas(f("email", "E-mail"), f("telefone", "Telefone", num)) + nfDuas(f("inscricao_municipal", "Inscrição municipal (se houver)"))) +
      nfCard("Endereço", nfDuas(f("cep", "CEP", num), f("logradouro", "Rua")) + nfDuas(f("numero", "Número"), f("complemento", "Complemento")) + nfDuas(f("bairro", "Bairro"), f("cmun")) + nfDuas(f("uf", "UF")));
  }
  // Competencia: o mesmo calendario do Admin, na vista de meses (no lugar do seletor nativo do navegador).
  function nfCompetenciaCampo(M) {
    var v = String(M.v.competencia || ""), y = Number(v.slice(0, 4)) || new Date().getFullYear(), mm = Number(v.slice(5, 7)) - 1;
    var ano = M.compAno || y, txt = v ? MESES_C[mm] + " de " + y : "";
    var h = '<div class="campo-adm nf-comp"><span class="rot">Competência</span><button type="button" class="caixa-campo fundo nf-comp-btn" data-a="nfCompAbrir" aria-expanded="' + !!M.compAberto + '">' +
      "<span>" + (txt ? esc(txt) : '<span class="c-ink3">escolha o mês</span>') + "</span>" + ic("calendar_month") + "</button>";
    if (M.compAberto) {
      h += '<div class="calendario-adm nf-comp-cal" role="dialog" aria-label="Escolher a competência"><div class="cal-topo"><button type="button" class="btn-icone" data-a="nfCompAno" data-d="-1" aria-label="Ano anterior">' + ic("chevron_left") + "</button>" +
        '<span class="cal-titulo">' + ano + '</span><button type="button" class="btn-icone" data-a="nfCompAno" data-d="1" aria-label="Próximo ano">' + ic("chevron_right") + "</button></div>" +
        '<div class="cal-grade meses">' + MESES_C.map(function (nm, i) { return '<button type="button" class="cal-celula' + (ano === y && i === mm ? " escolhido" : "") + '" data-a="nfCompMes" data-m="' + i + '">' + nm.slice(0, 3) + "</button>"; }).join("") + "</div>" +
        '<div class="cal-rodape"><button type="button" class="btn-texto-mudo" data-a="nfCompLimpar">Limpar</button><button type="button" class="btn-texto-mudo" data-a="nfCompEste">Este mês</button></div></div>';
    }
    return h + "</div>";
  }
  function nfErro(M) { return M.erro ? '<p class="erro-campo" role="alert">' + esc(M.erro) + "</p>" : ""; }
  // "a.b.c" -> {a: {b: {c}}}
  function nfAninhar(v, prefixo) {
    var saida = {};
    Object.keys(v).forEach(function (k) {
      if (prefixo && k.indexOf(prefixo) !== 0) return;
      var partes = k.slice(prefixo ? prefixo.length : 0).split("."), alvo = saida;
      partes.slice(0, -1).forEach(function (p) { alvo[p] = alvo[p] || {}; alvo = alvo[p]; });
      alvo[partes[partes.length - 1]] = v[k];
    });
    return saida;
  }
  function nfAchatar(obj, prefixo, saida) {
    saida = saida || {};
    Object.keys(obj || {}).forEach(function (k) {
      var x = obj[k];
      if (x && typeof x === "object" && !Array.isArray(x)) nfAchatar(x, prefixo + k + ".", saida);
      else saida[prefixo + k] = x == null ? "" : x;
    });
    return saida;
  }

  function nfModalHtml(M) {
    var d = dadosDe("nfse") || {}, s = d.situacao || {}, op = s.opcoes || {}, prod = s.ambiente === "producao", h = "";
    if (M.tipo === "nfEmitir") {
      var cl = M.clientes, pgs = d.pagamentos || [];
      h += modalCab("Emitir NFS-e") + '<div class="modal-corpo">';
      if (M.erroClientes) h += '<p class="nota-campo">Sem a lista de clientes (' + esc(M.erroClientes) + "): preencha à mão.</p>";
      // Cliente: um campo de busca (nome, CPF/CNPJ ou e-mail) com a lista logo abaixo.
      var cSel = (cl || []).filter(function (c) { return String(c.id) === String(M.v.conta); })[0];
      var q = M.cliQ != null ? M.cliQ : cSel ? cSel.nome : "", qn = norm(M.cliQ || "");
      var achados = (cl || []).filter(function (c) { return !qn || norm([c.nome, c.documento, nfDoc(c.documento), c.email].join(" ")).indexOf(qn) >= 0; }).slice(0, 8);
      var buscaCli = '<label class="campo-adm nf-cli"><span class="rot">Cliente (assinante)</span><span class="caixa-campo fundo">' + ic("search") +
        '<input id="nf-cli-q" data-in="nfCliBusca" value="' + esc(q) + '" placeholder="' + (cl ? "Buscar por nome, CPF/CNPJ ou e-mail" : "carregando…") + '" autocomplete="off" role="combobox" aria-expanded="' + !!M.cliAberto + '">' +
        (M.v.conta ? '<button type="button" class="btn-icone" data-a="nfCliPick" data-id="" aria-label="Tirar o cliente" title="Tirar o cliente">' + ic("close") + "</button>" : "") + "</span>" +
        (M.cliAberto && cl ? '<div class="nf-cli-lista" role="listbox">' + (achados.length ? achados.map(function (c) {
          return '<button type="button" role="option" class="nf-cli-op" data-a="nfCliPick" data-id="' + esc(c.id) + '"><b>' + esc(c.nome) + "</b><small>" + esc([nfDoc(c.documento), c.email].filter(Boolean).join(" · ")) + (c.faltas && c.faltas.length ? ' · <span class="c-atencao">falta ' + esc(c.faltas.join(", ")) + "</span>" : "") + "</small></button>";
        }).join("") : '<p class="nf-cli-vazio">Nenhum cliente com “' + esc(M.cliQ) + '”.</p>') +
          '<button type="button" class="nf-cli-op mao" data-a="nfCliPick" data-id="">' + ic("edit") + "<b>Preencher à mão</b></button></div>" : "") + "</label>";
      // Pagamento: a mesma busca, por cliente, tipo, valor ou data.
      var pSel = pgs.filter(function (x) { return String(x.id) === String(M.v.pagamento); })[0];
      var pTxt = function (x) { return (x.cliente || "conta") + " · " + x.tipo + " · " + brl(x.valor) + " · " + ddmm(x.quando); };
      var pq = M.pagQ != null ? M.pagQ : pSel ? pTxt(pSel) : "", pqn = norm(M.pagQ || "");
      var pAch = pgs.filter(function (x) { return !pqn || norm(pTxt(x)).indexOf(pqn) >= 0; }).slice(0, 8);
      var pagBusca = '<label class="campo-adm nf-cli nf-pag"><span class="rot">Pagamento (opcional)</span><span class="caixa-campo fundo">' + ic("search") +
        '<input id="nf-pag-q" data-in="nfPagBusca" value="' + esc(pq) + '" placeholder="Buscar por cliente, valor ou data" autocomplete="off" role="combobox" aria-expanded="' + !!M.pagAberto + '">' +
        (M.v.pagamento ? '<button type="button" class="btn-icone" data-a="nfPagPick" data-id="" aria-label="Tirar o pagamento" title="Tirar o pagamento">' + ic("close") + "</button>" : "") + "</span>" +
        (M.pagAberto ? '<div class="nf-cli-lista" role="listbox">' + (pAch.length ? pAch.map(function (x) {
          return '<button type="button" role="option" class="nf-cli-op" data-a="nfPagPick" data-id="' + esc(x.id) + '"><b>' + esc((x.cliente || "conta") + " · " + brl(x.valor)) + "</b><small>" + esc(x.tipo + " · " + ddmm(x.quando)) + "</small></button>";
        }).join("") : '<p class="nf-cli-vazio">' + (pgs.length ? "Nenhum pagamento com “" + esc(M.pagQ) + "”." : "Nenhum pagamento sem nota.") + "</p>") + "</div>" : "") + "</label>";
      h += nfCard("Cliente e pagamento", nfDuas(buscaCli, pagBusca));
      var esc_ = (cl || []).filter(function (c) { return String(c.id) === String(M.v.conta); })[0];
      if (esc_ && esc_.faltas && esc_.faltas.length) h += '<p class="aviso-falta">' + ic("warning") + "<span>No cadastro de " + esc(esc_.nome) + " falta " + esc(esc_.faltas.join(", ")) + ". Complete abaixo (vale só para esta nota) ou em Clientes (vale para as próximas).</span></p>";
      h += nfTomadorGrupos("tomador.") + nfCard("Serviço",
        nfDuas(nfCampo("valor", "Valor (R$)", ' inputmode="decimal" placeholder="300,00"'), nfCompetenciaCampo(M)) +
        nfCampo("descricao", "Descrição")) +
        '<p class="nota-campo">' + (prod ? "<b>Produção:</b> esta nota vale de verdade." : "Ambiente de testes: a nota não tem valor fiscal.") + " Com um pagamento escolhido, o valor, a descrição e a competência vêm dele.</p>" + nfErro(M) + "</div>" +
        modalPe('<button type="button" class="btn-acao verde" data-a="nfEmitirConfirmar" id="modal-ok"' + (M.enviando ? " disabled" : "") + ">" + ic("receipt_long") + (M.enviando ? "Emitindo…" : "Emitir") + "</button>");
    } else if (M.tipo === "nfClientes") {
      h += modalCab("Clientes") + '<div class="modal-corpo"><p class="nota-campo">Os assinantes vêm do cadastro feito no paulus.ia.br. O que você editar aqui vale para as notas (dados fiscais); o cadastro original da conta fica como está.</p>';
      if (M.erroClientes) h += '<p class="erro-linha">' + ic("warning") + "<span>Não consegui ler os clientes: " + esc(M.erroClientes) + "</span></p>";
      else if (!M.clientes) h += '<p class="carregando">Carregando…</p>';
      else if (!M.clientes.length) h += '<p class="vazio-linha">Nenhum assinante ainda.</p>';
      else {
        // Como a lista de Contas e cadastros: filtro, busca, uma grade com colunas; clicar na linha abre a edicao embaixo.
        var fC = M.filtro || "todos", qC = norm(M.q || "");
        var lsC = M.clientes.filter(function (c) {
          var ok = fC === "todos" || (fC === "falta" ? c.faltas && c.faltas.length : !(c.faltas && c.faltas.length));
          return ok && (!qC || norm([c.nome, (c.tomador || {}).documento, nfDoc((c.tomador || {}).documento), (c.tomador || {}).email].join(" ")).indexOf(qC) >= 0);
        });
        h += '<div class="barra-filtros">' + seg("nfCli.filtro", [["todos", "Todos"], ["falta", "Com dados faltando"], ["completo", "Completos"]], fC) +
          '<label class="caixa-campo caixa-busca">' + ic("search") + '<input id="nf-clis-q" data-in="nfClisQ" value="' + esc(M.q || "") + '" placeholder="nome, CPF/CNPJ ou e-mail" aria-label="Buscar clientes" spellcheck="false"></label></div>';
        var colsC = "minmax(180px,1.6fr) minmax(130px,1fr) 110px 96px minmax(120px,1fr) 28px";
        var linC = lsC.map(function (c) {
          var t = c.tomador || {}, aberto = String(M.editando) === String(c.id), s = sitConta(c.situacao);
          var r = '<button type="button" class="grade-linha' + (aberto ? " aberta" : "") + '" data-a="nfCliEditar" data-id="' + esc(c.id) + '" aria-expanded="' + aberto + '"' + (podeNf() ? "" : " disabled") + ">" +
            '<span class="cel-nome"><b class="corta">' + esc(c.nome) + '</b><small class="corta">' + esc(t.email || c.email || "—") + "</small></span>" +
            '<span class="num c-ink2 corta">' + esc(nfDoc(t.documento) || "—") + '</span><span class="t13">' + esc(c.plano ? (c.plano.nome || c.plano) : "—") + "</span>" + sit(s[0], s[1]) +
            (c.faltas && c.faltas.length ? '<span class="t125 c-atencao corta" title="falta ' + esc(c.faltas.join(", ")) + '">falta ' + esc(c.faltas.join(", ")) + "</span>" : '<span class="t125 c-ok">completo</span>') + '<span class="nf-seta' + (aberto ? " aberta" : "") + '" aria-hidden="true">' + ic("expand_more") + "</span></button>";
          if (aberto) r += '<div class="nf-form nf-cli-ed">' + nfTomadorGrupos("tomador.") + nfErro(M) + '<div class="nf-botoes" style="justify-content:flex-end"><button type="button" class="btn-texto-mudo s12" data-a="nfCliEditar" data-id="' + esc(c.id) + '">Fechar</button><button type="button" class="mini cheia" data-a="nfCliSalvar" data-id="' + esc(c.id) + '"' + (M.enviando ? " disabled" : "") + ">" + (M.enviando ? "Salvando…" : "Salvar") + "</button></div></div>";
          return r;
        }).join("") || '<p class="vazio-linha">Nenhum cliente com esse filtro.</p>';
        h += '<div class="painel">' + grade(colsC, 680, '<span>Cliente</span><span>CPF/CNPJ</span><span>Plano</span><span>Situação</span><span>Dados fiscais</span><span></span>', linC) +
          '<div class="pe-painel">' + lsC.length + (lsC.length === 1 ? " cliente" : " clientes") + "</div></div>";
      }
      if (M.ok) h += '<p class="nf-aviso ok">' + ic("check") + "<span>" + esc(M.ok) + "</span></p>";
      h += "</div>" + '<div class="modal-pe"><button type="button" class="btn-acao" data-a="fecharModal" id="modal-ok">Fechar</button></div>';
    } else if (M.tipo === "nfParametros") {
      var ret = op.retencoes || {}, cf = d.cloudflare || {}, so = !podeNf() ? " disabled" : "";
      h += modalCab("Parâmetros") + '<div class="modal-corpo">' + (so ? '<p class="nota-campo">Só o dono e o financeiro mudam os parâmetros; aqui você só lê.</p>' : "") +
        nfSub("O PAVLVS (prestador)") +
        nfDuas(nfCampo("documento", "CNPJ", ' inputmode="numeric"' + so), nfCampo("inscricao_municipal", "Inscrição municipal", so)) + nfCampo("razao_social", "Razão social", so) +
        nfDuas(nfMunicipio("municipio", "Município", so, ""), nfCampo("endereco.cep", "CEP", ' inputmode="numeric"' + so)) +
        nfDuas(nfCampo("endereco.logradouro", "Rua", so), nfCampo("endereco.numero", "Número", so)) +
        nfDuas(nfCampo("endereco.complemento", "Complemento", so), nfCampo("endereco.bairro", "Bairro", so)) +
        nfDuas(nfCampo("email", "E-mail", so), nfCampo("telefone", "Telefone", so)) +
        nfSub("Tributação") +
        nfDuas(nfEscolha("opcao_simples", "Regime", nfDominio(op.opcao_simples)), nfEscolha("regime_apuracao_sn", "Apuração no Simples", [["", "não se aplica"]].concat(nfDominio(op.regime_apuracao_sn, true)))) +
        nfDuas(nfEscolha("regime_especial", "Regime especial", nfDominio(op.regime_especial)), nfCampo("serie", "Série da DPS", ' inputmode="numeric"' + so)) +
        nfSub("Serviço") + nfDuas(nfCampo("servico.ctribnac", "Código de serviço (cTribNac)", ' placeholder="ex.: 010501"' + so), nfCampo("servico.nbs", "NBS", so)) +
        nfDuas(nfCampo("servico.aliquota_iss_pct", "Alíquota do ISS (%)", ' inputmode="decimal" placeholder="2,00"' + so), nfCampo("servico.ctribmun", "Código municipal (3 dígitos, se houver)", so)) +
        nfCampo("servico.descricao", "Descrição padrão do serviço", so) +
        nfSub("IBS/CBS e tributos aproximados") + nfDuas(nfCampo("ibscbs.cst", "IBS/CBS — CST", so), nfCampo("ibscbs.cclasstrib", "IBS/CBS — cClassTrib", so)) +
        nfDuas(nfCampo("ibscbs.cindop", "IBS/CBS — indicador da operação (cIndOp)", so), nfEscolha("ibscbs.indfinal", "Consumidor final", [["0", "não"], ["1", "sim"]])) +
        nfMarcar("ibscbs.enviar", "Enviar o grupo IBS/CBS na nota") +
        nfDuas(nfCampo("pis_cofins.cst", "PIS/COFINS — CST (se houver retenção)", so), nfCampo("total_tributos.federal_pct", "Tributos aproximados — federal (%)", ' inputmode="decimal"' + so)) +
        nfDuas(nfCampo("total_tributos.estadual_pct", "Tributos aproximados — estadual (%)", ' inputmode="decimal"' + so), nfCampo("total_tributos.municipal_pct", "Tributos aproximados — municipal (%)", ' inputmode="decimal"' + so)) +
        '<p class="nota-campo">O código do serviço, a NBS e a classificação do IBS/CBS do PAVLVS (programa de computador) são do contador.</p>' +
        (Object.keys(ret).length ? nfSub("Retenções") : "") + Object.keys(ret).map(function (k) {
          return nfDuas(nfEscolha("retencoes." + k + ".quando", ret[k] + " — quando reter", nfDominio(op.quando_reter)),
            k === "iss" ? "" : nfCampo("retencoes." + k + ".aliquota_pct", ret[k] + " — alíquota (%)", ' inputmode="decimal"' + so));
        }).join("") +
        nfSub("Contador") + nfDuas(nfCampo("contador.nome", "Contador", so), nfCampo("contador.email", "E-mail do contador", so)) + nfErro(M) +
        nfSub("Token da Cloudflare") +
        '<p class="nota-campo">Com ele o painel cadastra o certificado na Cloudflare (o mTLS que a Sefin exige) e republica o Worker auxiliar paulus-nfse-mtls. ' + esc(cf.como_criar_token || "") + " Fica guardado cifrado; não volta para a tela.</p>" +
        '<div class="nf-cert"><span class="caixa-campo fundo nf-senha"><input type="password" id="nf-token" data-in="nfTokenCampo" value="' + esc(M.token || "") + '" placeholder="' + (cf.token ? "••••••••••••••••••••••••••••••••" : "cole o token aqui") + '"' + (cf.token ? ' title="Token gravado. Cole outro para trocar." class="nf-token-gravado"' : "") + ' autocomplete="off" aria-label="Token da Cloudflare"' + so + "></span>" +
        '<button type="button" class="mini cheia" data-a="nfToken"' + (so || M.gravandoToken ? " disabled" : "") + ">" + (M.gravandoToken ? "Gravando…" : "Gravar token") + "</button>" +
        '<span class="num s11 ' + (cf.token ? "c-ok" : "c-atencao") + '">' + (cf.token ? "token gravado" : "sem token") + "</span></div>" +
        (M.tokenMsg ? '<p class="' + (M.tokenOk ? "nf-aviso ok" : "nf-aviso") + '">' + ic(M.tokenOk ? "check" : "warning") + "<span>" + esc(M.tokenMsg) + "</span></p>" : "") +
        nfSub("Produção") +
        (s.producao_liberada
          ? '<p class="nota-campo">Em produção: as notas valem de verdade.</p><div class="nf-botoes"><button type="button" class="mini" data-a="nfProducao" data-v="voltar"' + so + ">Voltar para testes</button></div>"
          : '<p class="nota-campo">Em testes (produção restrita, sem valor fiscal). Só muda depois de ao menos uma nota emitida em testes.</p><div class="nf-botoes"><button type="button" class="mini' + (M.prodConfirma ? " perigo" : "") + '" data-a="nfProducao" data-v="liberar"' + so + ">" +
            (M.prodConfirma ? "Confirmar: as notas passam a valer de verdade" : "Mudar para produção") + "</button></div>") +
        (M.erroProd ? '<p class="erro-campo">' + esc(M.erroProd) + "</p>" : "") + "</div>";
      h = nfEmCards(h);
      h += modalPe(so ? "" : '<button type="button" class="btn-acao verde" data-a="nfParamSalvar" id="modal-ok"' + (M.enviando ? " disabled" : "") + ">" + (M.enviando ? "Gravando…" : "Gravar parâmetros") + "</button>");
    } else if (M.tipo === "nfCancelar") {
      var n = nfNota(M.id) || {};
      h += modalCab("Cancelar a NFS-e nº " + (n.numero || "")) + '<div class="modal-corpo"><p class="t13" style="line-height:1.55">NFS-e nº ' + esc(n.numero) + " · " + esc(n.cliente) + " · " + esc(brl(n.centavos / 100)) +
        (n.ambiente === "producao" ? "" : " · ambiente de testes") + ". O cancelamento vai ao Sistema Nacional e não se desfaz; o município tem um prazo para cancelar. Depois do prazo, o caminho é Substituir.</p>" +
        nfEscolha("motivo", "Motivo (tabela oficial)", nfDominio(op.motivos_cancelamento, true)) + nfTexto("texto", "Descreva o motivo (15 a 255 caracteres)") + nfErro(M) + "</div>" +
        modalPe('<button type="button" class="btn-acao perigo-cheio" data-a="nfCancelarConfirmar" id="modal-ok"' + (M.enviando ? " disabled" : "") + ">" + (M.enviando ? "Cancelando…" : "Cancelar a nota") + "</button>");
    } else if (M.tipo === "nfSubstituir") {
      var o = nfNota(M.id) || {};
      h += modalCab("Substituir a NFS-e nº " + (o.numero || "")) + '<div class="modal-corpo"><p class="t13" style="line-height:1.55">Sai uma nota nova no lugar da nº ' + esc(o.numero) + ", e a Sefin cancela a antiga sozinha. Corrija abaixo o que estava errado; o resto vem da nota original.</p>" +
        nfEscolha("motivo", "Motivo (tabela oficial)", nfDominio(op.motivos_substituicao, true)) + nfTexto("texto", "Descrição do motivo (15 a 255 caracteres; obrigatória no 99 – Outros)") +
        nfSub("Tomador") + nfTomadorCampos("ajustes.tomador.") + nfSub("Serviço") +
        nfDuas(nfCampo("ajustes.valor", "Valor (R$)", ' inputmode="decimal"'), nfCampo("ajustes.competencia", "Competência", ' type="month"')) + nfCampo("ajustes.descricao", "Descrição") +
        '<p class="nota-campo">No Simples Nacional, a substituta não pode mudar o tomador, o valor nem a competência (regra E0061).</p>' + nfErro(M) + "</div>" +
        modalPe('<button type="button" class="btn-acao verde" data-a="nfSubstituirConfirmar" id="modal-ok"' + (M.enviando ? " disabled" : "") + ">" + (M.enviando ? "Emitindo…" : "Emitir a substituta") + "</button>");
    }
    return h;
  }

  function campoModal(id, rot, val, inp, pre, suf) {
    return '<label class="campo-adm"><span class="rot">' + esc(rot) + '</span><span class="caixa-campo mono fundo">' + (pre ? '<span class="pre">' + pre + "</span>" : "") + '<input id="' + id + '" data-in="' + inp + '" value="' + esc(val) + '" inputmode="decimal">' + (suf ? '<span class="sufixo">' + suf + "</span>" : "") + "</span></label>";
  }

  /* ---------- busca ---------- */
  var ICONE_GRUPO = { contas: "contacts", escritorios: "group", tuneis: "dns", planos: "payments", materiais: "menu_book" };
  var NOME_GRUPO = { contas: "Contas", escritorios: "Escritórios", tuneis: "Túneis", planos: "Planos", materiais: "Materiais" };
  var TELA_GRUPO = { contas: "contas", escritorios: "contas", tuneis: "tuneis", planos: "planos", materiais: "materiais" };
  function rapidas() {
    var c = contagens(), l = [];
    l.push({ icon: "campaign", t: "E-mails › Nova campanha", d: "público, conteúdo e disparo em 3 passos", ir: function () { U.emails.aba = "nova"; U.emails.passo = 1; irPara("emails"); } });
    if (podeNf()) l.push({ icon: "receipt_long", t: "Notas fiscais › Emitir NFS-e", d: c.nfse != null ? c.nfse + " pendências (pagamentos sem nota e notas na fila)" : "pagamentos sem nota", ir: function () { irPara("nfse"); } });
    l.push({ icon: "publish", t: "Confirmar alterações › Commitar e pushar", d: c.alteracoes + " pendentes", ir: function () { irPara("alteracoes"); } });
    l.push({ icon: "dns", t: "Túneis › Perto de apagar", d: "os que a limpeza diária vai pegar", ir: function () { U.tuneis.filtro = "risco"; irPara("tuneis"); } });
    l.push({ icon: "notifications", t: "Não renovações › Abertas", d: c.renovacoes != null ? c.renovacoes + " ciclos sem cobrança" : "ciclos sem cobrança", ir: function () { irPara("renovacoes"); } });
    return l;
  }
  function gruposBusca() {
    var B = E.busca, q = norm(B.q.trim());
    if (!q) return [["Ações rápidas", rapidas()]];
    var bate = function (t) { return norm(t).indexOf(q) >= 0; };
    var g = [];
    var telas = TELAS.filter(function (t) { return bate(t.label); }).map(function (t) { return { icon: t.icon, t: t.label, d: "tela", ir: function () { irPara(t.id); } }; });
    if (telas.length) g.push(["Telas", telas]);
    var ac = rapidas().filter(function (r) { return bate(r.t + " " + r.d); });
    if (ac.length) g.push(["Ações", ac]);
    var res = B.res || {};
    ["contas", "escritorios", "tuneis", "planos"].forEach(function (k) {
      var it = (res[k] || []).slice(0, 6).map(function (x) {
        return { icon: ICONE_GRUPO[k], t: NOME_GRUPO[k] + " › " + x.titulo, d: x.desc, ir: function () { abrirResultado(k, x); } };
      });
      if (it.length) g.push([NOME_GRUPO[k], it]);
    });
    return g;
  }
  function abrirResultado(k, x) {
    var tela = TELA[x.tela] ? x.tela : TELA_GRUPO[k];
    if (k === "contas") { irPara("contas"); abrirConta(x.alvo); return; }
    if (k === "escritorios") { U.contas.agrupar = "escritorio"; U.contas.q = x.titulo || ""; U.contas.filtro = "todas"; }
    if (k === "tuneis") { U.tuneis.filtro = "todos"; U.tuneis.aberto = x.alvo; }
    if (k === "materiais") { U.materiais.filtro = "todos"; U.materiais.aberto = x.alvo; }
    irPara(tela);
  }
  var itensBusca = [];
  function buscaHtml() {
    var B = E.busca, gr = gruposBusca(), n = 0;
    itensBusca = [];
    var total = gr.reduce(function (s, g) { return s + g[1].length; }, 0);
    if (B.idx >= total) B.idx = Math.max(0, total - 1);
    var corpo = gr.map(function (g) {
      return '<div class="busca-grupo" role="presentation">' + esc(g[0]) + "</div>" + g[1].map(function (r) {
        var i = n++; itensBusca.push(r);
        var partes = r.t.split(" › ");
        return '<button type="button" class="busca-item" role="option" id="bi-' + i + '" aria-selected="' + (i === B.idx) + '" data-a="buscaIr" data-i="' + i + '" tabindex="-1">' + ic(r.icon) +
          '<span class="tx"><b>' + esc(r.t) + "</b><span> " + esc(r.d || "") + "</span></span>" + ic("arrow_forward", "seta") + "</button>";
      }).join("");
    }).join("");
    var q = B.q.trim();
    if (q && !total) corpo += B.carregando ? '<p class="vazio-linha">Buscando…</p>' : '<p class="vazio-linha" style="padding:28px 16px">Nada com "' + esc(q) + '". Tente o nome de uma conta, um escritório ou uma tela.</p>';
    if (q && B.erro) corpo += '<p class="erro-linha" style="margin:8px 16px">' + ic("warning") + "<span>Não consegui buscar nas contas agora: " + esc(B.erro) + "</span></p>";
    return '<div class="veu forte veu-busca" data-a="fecharBusca"></div><div class="busca" role="dialog" aria-modal="true" aria-label="Buscar em tudo">' +
      '<div class="busca-campo">' + ic("search") + '<input id="busca-q" data-in="buscaQ" value="' + esc(B.q) + '" placeholder="Buscar em tudo: telas, ações, contas, escritórios, túneis, planos…" spellcheck="false" autocomplete="off" role="combobox" aria-expanded="true" aria-controls="busca-lista" aria-activedescendant="bi-' + B.idx + '">' +
      '<button type="button" data-a="fecharBusca" aria-label="Fechar a busca"><kbd class="tecla">Esc</kbd></button></div>' +
      '<div class="busca-res" id="busca-lista" role="listbox" aria-label="Resultados">' + corpo + "</div>" +
      '<div class="busca-pe"><span><kbd class="tecla">↑</kbd><kbd class="tecla">↓</kbd><span>para navegar</span></span><span><kbd class="tecla">↵</kbd><span>para abrir</span></span></div></div>';
  }
  function marcarBusca(i) {
    var B = E.busca; B.idx = i;
    document.querySelectorAll(".busca-item").forEach(function (b) { b.setAttribute("aria-selected", String(Number(b.dataset.i) === i)); });
    var inp = $("busca-q"); if (inp) inp.setAttribute("aria-activedescendant", "bi-" + i);
    var at = $("bi-" + i); if (at && at.scrollIntoView) at.scrollIntoView({ block: "nearest" });
  }
  var buscaTimer = null;
  function buscar() {
    var B = E.busca, q = B.q.trim();
    clearTimeout(buscaTimer);
    if (q.length < 2) { B.res = null; B.erro = ""; B.carregando = false; return; }
    B.carregando = true;
    buscaTimer = setTimeout(function () {
      var seq = ++B.seq;
      api("GET", "/api/admin/busca?q=" + encodeURIComponent(q)).then(function (r) { if (seq !== B.seq) return; B.res = r; B.erro = ""; }, function (e) { if (seq !== B.seq) return; B.res = null; B.erro = e.status === 401 ? "" : e.message; })
        .then(function () { if (seq !== B.seq) return; B.carregando = false; if (B.aberta) renderCamada(); });
    }, 200);
  }
  var focoAntes = null;
  function abrirBusca() { if (!E.dentro) return; focoAntes = document.activeElement; E.busca.aberta = true; E.busca.q = ""; E.busca.idx = 0; E.busca.res = null; renderCamada(); var i = $("busca-q"); if (i) i.focus(); }
  function fecharBusca() { E.busca.aberta = false; renderCamada(); devolverFoco(); }
  function devolverFoco() { if (focoAntes && document.contains(focoAntes)) { try { focoAntes.focus({ preventScroll: true }); } catch (e) { /* nada */ } } focoAntes = null; }

  /* ================================================================ navegacao */

  function irPara(tela) {
    E.busca.aberta = false; E.gaveta = null;
    if (location.hash.slice(1) === tela) { E.tela = tela; carregarTela(); render(); }
    else location.hash = tela;
  }
  function carregarTela() { leiturasDa(E.tela).forEach(function (ch) { ler(ch); }); }
  function aoMudarHash() {
    var id = location.hash.replace(/^#/, "");
    if (!TELA[id]) id = "visao";
    var mudou = E.tela !== id;
    if (E.modal && E.modal.embutido) E.modal = null;
    E.tela = id; E.gaveta = null; E.busca.aberta = false;
    if (!E.dentro) return;
    carregarTela();
    render();
    if (mudou) { window.scrollTo(0, 0); var m = $("conteudo"); if (m && document.activeElement && document.activeElement.closest && document.activeElement.closest(".adm-pilulas,.adm-trilho")) { /* fica no menu */ } }
  }

  function abrirConta(id, pagina) {
    focoAntes = document.activeElement;
    E.gaveta = { id: id, resumo: contaResumo(id), det: null, erro: "", pagina: !!pagina };
    if (pagina) render();
    renderCamada();
    var b = $("gaveta-fechar"); if (b) b.focus();
    var G = E.gaveta;
    api("GET", "/api/admin/contas/" + encodeURIComponent(id)).then(function (d) { if (E.gaveta === G) { G.det = d; renderCamada(); if (G.pagina) render(); } }, function (e) { if (E.gaveta === G && e.status !== 401) { G.erro = e.message; renderCamada(); } });
  }
  function recarregarGaveta() { if (E.gaveta) { var id = E.gaveta.id, pag = E.gaveta.pagina; var f = focoAntes; abrirConta(id, pag); focoAntes = f; } }

  /* ================================================================ acoes */

  var A = {};
  var SEG = {
    "nfse.aba": function (v) {
      if (E.modal && E.modal.embutido) E.modal = null;
      U.nfse.aba = "notas";
      if (!(dadosDe("nfse") || {}).situacao) return;
      if (v === "emitir") { if (podeNf()) nfAbrirEmitir(""); } else if (v === "clientes") A.nfClientes(); else if (v === "parametros") A.nfParametros();
    },
    "tokens.visao": function (v) { U.tokens.visao = v; U.tokens.sel = null; ler(tokensChave()); },
    "tokens.periodo": function (v) { U.tokens.periodo = v; U.tokens.cal = null; ler(tokensChave()); },
    "emails.aba": function (v) { U.emails.aba = v; if (v === "nova") U.emails.passo = U.emails.passo || 1; },
    "membro.papel": function (v) { if (E.modal) { E.modal.v.papel = v; renderCamada(); } },
    "emails.quando": function (v) { U.emails.camp.quando = v; U.emails.camp.cal = null; },
    "extrato.tipo": function (v) { if (E.modal) { E.modal.filtro = v; renderCamada(); } },
    "extrato.periodo": function (v) { if (E.modal) { E.modal.periodo = v; E.modal.cal = null; renderCamada(); } },
  };
  A.seg = function (el) {
    var n = el.dataset.seg, v = el.dataset.v;
    if (n === "nfCli.filtro") { if (E.modal) { E.modal.filtro = v; E.modal.editando = null; } renderCamada(); return; }
    if (n.indexOf("renovOferta:") === 0) { var o = U.renovacoes.oferta[n.slice(12)]; if (o) o.tipo = v; render(); return; }
    if (n.indexOf("equipe.papel:") === 0) return mudarPapel(n.slice(13), v);
    if (SEG[n]) SEG[n](v);
    else { var p = n.split("."); U[p[0]][p[1]] = v; }
    if (n === "tuneis.filtro") U.tuneis.sel = {};
    render();
  };
  A.irTela = function (el) {
    var t = el.dataset.tela, f = el.dataset.filtro;
    if (!TELA[t]) return;
    if (f && U[t] && "filtro" in U[t]) U[t].filtro = f;
    irPara(t);
  };
  // Sempre duas letras, como os avatares do Paulus: primeira e ultima palavra; com uma palavra so, as duas primeiras letras.
  function iniciaisAdm(n) {
    var p = String(n || "").replace(/@.*/, "").trim().split(/[\s._-]+/).filter(Boolean);
    if (!p.length) return "?";
    return (p.length > 1 ? p[0][0] + p[p.length - 1][0] : p[0].slice(0, 2)).toUpperCase();
  }
  // O nome completo vem da Equipe quando a sessao so traz o primeiro nome.
  function nomeCompletoSessao() {
    var s = E.sessao || {}, em = s.email || (s.access && s.access.email) || "";
    var m = ((dadosDe("equipe") || {}).membros || []).filter(function (x) { return x.email === em; })[0];
    return (m && m.nome) || s.nome || em;
  }
  // O avatar abre a conta, como no Paulus (00-acesso.js): quem esta aqui e as saidas seguras.
  A.contaMenu = function () { abrirModal({ tipo: "conta", passo: null }); };
  A.contaTodas = function () { E.modal.passo = "todas"; renderCamada(); };
  A.contaVoltar = function () { E.modal.passo = null; renderCamada(); };
  A.contaSairTodas = async function (el) {
    el.disabled = true;
    try { await api("POST", "/api/admin/sessoes/encerrar", {}); } catch (e) { /* sai assim mesmo */ }
    A.sair();
  };
  A.sair = async function () {
    try { await api("POST", "/api/admin/sair", {}); } catch (e) { /* sai assim mesmo */ }
    try { sessionStorage.removeItem("pv-admin-dentro"); } catch (e) { /* nada */ }
    location.assign("/cdn-cgi/access/logout");
  };
  A.recarregar = function () { location.reload(); };
  A.github = function () { location.assign("/api/admin/github/entrar"); };
  A.entrarPainel = function () { try { sessionStorage.setItem("pv-admin-dentro", "1"); } catch (e) { /* nada */ } mostrarCasca(); };

  // contas e gaveta
  A.abrirConta = function (el) { abrirConta(el.dataset.id); };
  A.fecharGaveta = function () { E.gaveta = null; renderCamada(); devolverFoco(); };
  A.abrirPaginaConta = function () { if (!E.gaveta) return; E.gaveta.pagina = true; renderCamada(); render(); window.scrollTo(0, 0); };
  A.voltarContas = function () { E.gaveta = null; if (E.modal && E.modal.embutido) E.modal = null; render(); window.scrollTo(0, 0); };
  // Na pagina da conta, o que era pop-up (extrato, cadastro, plano, Google) abre como aba.
  var ABAS_CONTA = [["resumo", "Resumo", ""], ["extrato", "Pagamentos", "contaExtrato"], ["cadastro", "Cadastro", "contaCadastro"], ["plano", "Plano", "contaPlano"], ["google", "Permissões Google", "modalGoogle"], ["tunel", "Túnel", ""]];
  A.contaAba = function (el) {
    var aba = el.dataset.aba, def = ABAS_CONTA.filter(function (x) { return x[0] === aba; })[0]; if (!def || !E.gaveta) return;
    if (!def[2]) { E.modal = null; E.gaveta.aba = aba; render(); return; }
    A[def[2]]({ dataset: { id: E.gaveta.id } });
  };
  A.contaEmail = function () {
    var c = E.gaveta.det || E.gaveta.resumo; if (!c) return;
    U.emails.so = c; U.emails.camp.publico = "conta:" + c.id; U.emails.aba = "nova"; U.emails.passo = 1;
    irPara("emails");
  };
  A.contaCreditar = function () {
    var c = E.gaveta.det || E.gaveta.resumo; if (!c) return;
    enfileirar("contas", "conta.creditar", c.id, { id: c.id, tokens: 10000000 }, "Creditei 10M tokens de cortesia para " + c.nome);
  };
  A.contaDesvincular = function (el) {
    var c = (E.gaveta && (E.gaveta.det || E.gaveta.resumo)) || contaResumo(el && el.dataset.id); if (!c) return;
    enfileirar("contas", "google.desvincular", c.id, { id: c.id }, "Desvinculei a conta Google de " + c.nome);
  };
  A.contaCancelar = function () {
    var c = E.gaveta.det || E.gaveta.resumo; if (!c) return;
    enfileirar("contas", "conta.cancelar", c.id, { id: c.id }, "Cancelei a assinatura de " + c.nome + (c.plano ? " (" + c.plano.nome + ")" : ""));
  };
  A.contaReembolsar = function (el) {
    var c = E.gaveta.det; if (!c) return;
    var p = (c.pagamentos || []).filter(function (x) { return String(x.ref) === el.dataset.ref; })[0]; if (!p) return;
    enfileirar("contas", "conta.reembolsar", c.id + ":" + p.ref, { id: c.id, pagamento: p.ref },
      "Reembolsei " + brl(p.valor) + " (" + (TIPO_PAG[p.tipo] || p.tipo).toLowerCase() + " de " + ddmm(p.quando) + ") de " + c.nome);
  };
  A.instDesvincular = function (el) {
    var c = E.gaveta.det; if (!c) return;
    enfileirar("contas", "conta.instalacao.apagar", c.id + ":" + el.dataset.hash, { id: c.id, hash8: el.dataset.hash }, "Desvinculei a instalação " + el.dataset.inst + " de " + c.nome);
  };

  // google
  A.googleConfirmar = function (el) { U.google.confirmando = el.dataset.id; render(); };
  A.googleVoltar = function () { U.google.confirmando = null; render(); };
  A.googleDesvincular = function (el) {
    var c = contaResumo(el.dataset.id); U.google.confirmando = null;
    if (c) enfileirar("google", "google.desvincular", c.id, { id: c.id }, "Desvinculei a conta Google de " + c.nome); else render();
  };
  A.modalGoogle = function (el) {
    var id = el.dataset.id, c = (E.gaveta && String(E.gaveta.id) === String(id) && (E.gaveta.det || E.gaveta.resumo)) || contaResumo(id);
    if (!c || !c.google) return;
    var lig = {}; (c.google.escopos || []).forEach(function (s) { lig[s] = true; });
    abrirModal({ tipo: "google", id: c.id, nome: c.nome, email: c.email, ligados: lig, antes: (c.google.escopos || []).slice(), tela: E.gaveta ? "contas" : "google" });
  };
  A.googleServico = function (el) { var k = el.dataset.k; E.modal.ligados[k] = !E.modal.ligados[k]; renderCamada(); };
  A.googleAplicar = function () {
    var M = E.modal, esc_ = SERV_G.map(function (s) { return s[0]; }).filter(function (k) { return M.ligados[k]; });
    var nome = M.nome;
    fecharModal();
    enfileirar(M.tela, "google.servicos", M.id, { id: M.id, ligados: esc_ }, esc_.length ? "Deixei " + primeiro(nome) + " só com " + esc_.join(", ") : "Revoguei todo o acesso ao Google de " + nome);
  };

  // tuneis
  A.tunelAbrir = function (el) {
    var s = el.dataset.slug;
    if (U.tuneis.selecionando) {
      if (tunelSegurou) { tunelSegurou = false; return; }
      if (!el.dataset.tsel) return;
      U.tuneis.sel[s] = !U.tuneis.sel[s];
      if (!Object.keys(U.tuneis.sel).some(function (k) { return U.tuneis.sel[k]; })) { U.tuneis.selecionando = false; U.tuneis.sel = {}; }
      render(); return;
    }
    U.tuneis.aberto = U.tuneis.aberto === s ? null : s; render();
  };
  A.tunelHist = function (el) {
    var s = el.dataset.slug, t = ((dadosDe("tuneis") || {}).tuneis || []).filter(function (x) { return x.slug === s; })[0]; if (!t) return;
    abrirModal({ tipo: "tunelHist", slug: s, itens: (t.historico || []).slice().sort(function (a, b) { return String(b.quando).localeCompare(String(a.quando)); }) });
  };
  A.calLimparReg = function () { U.tuneis.periodo = "tudo"; U.tuneis.cal = null; render(); };
  var regFiltrado = [];
  // Exporta o que o filtro mostra (tipo, busca e periodo), nao so as 6 linhas a vista.
  A.regJson = function () {
    var b = new Blob([JSON.stringify({ gerado: new Date().toISOString(), filtro: { evento: U.tuneis.reg, busca: U.tuneis.regQ || "", de: U.tuneis.periodo === "custom" ? U.tuneis.de : null, ate: U.tuneis.periodo === "custom" ? U.tuneis.ate : null }, eventos: regFiltrado }, null, 2)], { type: "application/json" });
    var a = document.createElement("a"); a.href = URL.createObjectURL(b); a.download = "registro-de-enderecos.json"; document.body.appendChild(a); a.click(); a.remove();
    setTimeout(function () { URL.revokeObjectURL(a.href); }, 1000);
  };
  A.regVerMais = function () { U.tuneis.regTodos = !U.tuneis.regTodos; render(); };
  A.tuneisSelSair = function () { U.tuneis.selecionando = false; U.tuneis.sel = {}; render(); };
  A.tuneisSelTodas = function () { U.tuneis.sel = {}; ((dadosDe("tuneis") || {}).tuneis || []).forEach(function (t) { if (!naFila("tunel.apagar", t.slug)) U.tuneis.sel[t.slug] = true; }); render(); };
  var tunelSegurou = false;
  (function () {
    var t = null;
    document.addEventListener("pointerdown", function (ev) {
      var l = ev.target.closest("[data-tsel]"); if (!l || ev.target.closest("button") || U.tuneis.selecionando) return;
      tunelSegurou = false;
      t = setTimeout(function () { tunelSegurou = true; U.tuneis.selecionando = true; U.tuneis.sel = {}; U.tuneis.sel[l.dataset.tsel] = true; U.tuneis.aberto = null; render(); }, 450);
    });
    var parar = function () { clearTimeout(t); t = null; if (tunelSegurou) setTimeout(function () { tunelSegurou = false; }, 0); };
    ["pointerup", "pointercancel", "pointerleave"].forEach(function (n) { document.addEventListener(n, parar); });
  })();
  A.tunelSel = function (el) { var s = el.dataset.slug; U.tuneis.sel[s] = !U.tuneis.sel[s]; render(); };
  A.tuneisSelParados = function () {
    var ts = (dadosDe("tuneis") || {}).tuneis || [], par = ts.filter(parado);
    var todos = par.length && par.every(function (t) { return U.tuneis.sel[t.slug]; });
    U.tuneis.sel = {}; if (!todos) par.forEach(function (t) { U.tuneis.sel[t.slug] = true; });
    U.tuneis.selecionando = Object.keys(U.tuneis.sel).some(function (k) { return U.tuneis.sel[k]; });
    render();
  };
  A.tuneisApagar = async function () {
    var slugs = Object.keys(U.tuneis.sel).filter(function (k) { return U.tuneis.sel[k] && !naFila("tunel.apagar", k); });
    var ok = 0;
    for (var i = 0; i < slugs.length; i++) { if (await enfileirar("tuneis", "tunel.apagar", slugs[i], { slug: slugs[i] }, "Apaguei " + slugs[i], true)) ok++; }
    U.tuneis.sel = {}; U.tuneis.selecionando = false;
    render();
    if (ok) toastFila();
  };
  A.tunelAvisar = async function (el) {
    var s = el.dataset.slug, t = ((dadosDe("tuneis") || {}).tuneis || []).filter(function (x) { return x.slug === s; })[0];
    el.disabled = true;
    var r = await naHora("POST", "/api/admin/tuneis/" + encodeURIComponent(s) + "/avisar", {}, "Aviso enviado a " + (t && t.responsavel || "o responsável"));
    if (r) ler("tuneis"); else el.disabled = false;
  };
  A.tunelAtivo = function (el) {
    var s = el.dataset.slug, t = ((dadosDe("tuneis") || {}).tuneis || []).filter(function (x) { return x.slug === s; })[0]; if (!t) return;
    var ativo = t.ativo === false;
    enfileirar("tuneis", "tunel.ativo", s, { slug: s, ativo: ativo }, (ativo ? "Reativei " : "Desativei ") + s + ".paulus.ia.br");
  };
  A.tunelLiberar = function (el) {
    var s = el.dataset.slug;
    enfileirar("tuneis", "tunel.apagar", s, { slug: s }, "Liberei o endereço " + s + ".paulus.ia.br (túnel e DNS apagados)");
  };
  A.modalEndereco = function (el) { abrirModal({ tipo: "endereco", slug: el.dataset.slug, novo: "", check: null, seq: 0 }); };
  A.usarLivre = function (el) { E.modal.novo = el.dataset.v; conferirSlug(); renderCamada(); var i = $("modal-slug"); if (i) i.focus(); };
  A.enderecoConfirmar = function () {
    var M = E.modal; if (!M.check || !M.check.ok) return;
    var novo = M.novo.trim().toLowerCase(), slug = M.slug;
    fecharModal();
    enfileirar("tuneis", "tunel.endereco", slug, { slug: slug, novo: novo }, "Alterei o endereço " + slug + " → " + novo + ".paulus.ia.br");
  };
  var slugTimer = null;
  function conferirSlug() {
    var M = E.modal, s = M.novo.trim().toLowerCase(), motivo = "";
    clearTimeout(slugTimer);
    if (!s) { M.check = null; return; }
    if (s.length < 3) motivo = "use pelo menos 3 letras";
    else if (s.length > 24) motivo = "use no máximo 24 letras";
    else if (!/^[a-z0-9-]+$/.test(s)) motivo = "só letras minúsculas sem acento, números e hífen";
    else if (/^-|-$/.test(s)) motivo = "não comece nem termine com hífen";
    else if (s === M.slug) motivo = "é o endereço de agora";
    if (motivo) { M.check = { msg: motivo, cor: "var(--erro)", ok: false }; return; }
    M.check = { msg: "conferindo…", cor: "var(--ink3)", ok: false };
    var seq = ++M.seq;
    slugTimer = setTimeout(function () {
      api("GET", "/api/admin/tuneis/disponivel?nome=" + encodeURIComponent(s)).then(function (r) {
        if (E.modal !== M || seq !== M.seq) return;
        M.check = r.ok ? { msg: "disponível · CNAME livre na zona", cor: "var(--ok)", ok: true } : { msg: r.motivo || "já em uso", cor: "var(--erro)", ok: false };
        renderCamada();
      }, function (e) {
        if (E.modal !== M || seq !== M.seq || e.status === 401) return;
        M.check = { msg: "não consegui conferir: " + e.message, cor: "var(--erro)", ok: false };
        renderCamada();
      });
    }, 250);
  }

  // renovacoes
  A.renovLembrete = async function (el) {
    var id = el.dataset.id, r = (((dadosDe("renovacoes") || {}).abertas) || []).filter(function (x) { return String(x.id) === String(id); })[0];
    el.disabled = true;
    var ok = await naHora("POST", "/api/admin/renovacoes/" + encodeURIComponent(id) + "/lembrete", {}, "Lembrete enviado para " + (r ? r.email : "a conta"));
    if (ok) ler("renovacoes"); else el.disabled = false;
  };
  // O detalhe aberto da nao renovacao: uma mensagem do proprio punho e uma oferta para a pessoa voltar.
  function renovDetHtml(r, emailOff, email) {
    var id = String(r.id), msg = U.renovacoes.msg[id] || "", of = U.renovacoes.oferta[id] || (U.renovacoes.oferta[id] = { tipo: "creditos", tokens: "10", valor: "", plano: r.plano ? r.plano.id : "" });
    var ps = (dadosDe("planos") || {}).planos; if (!ps && !renovDetHtml.pediu) { renovDetHtml.pediu = true; ler("planos"); }
    ps = ps || (r.plano ? [r.plano] : []);
    var h = '<div class="tunel-det renov-det"><div class="td-esq rd-col"><span class="td-tit">Mensagem para ' + esc(primeiro(r.nome)) + "</span>" +
      '<textarea class="area rd-msg" rows="4" data-in="renovMsg" data-id="' + esc(id) + '" placeholder="Escreva do seu jeito. Sai do e-mail do Paulus, com o seu nome.">' + esc(msg) + "</textarea>" +
      '<div class="res-acoes rd-pe"><span class="nota-campo">Vai para ' + esc(r.email) + "</span>" +
      '<button type="button" class="mini cheia" data-a="renovMsgEnviar" data-id="' + esc(id) + '"' + attrDis(emailOff || !msg.trim(), emailOff ? email.falta : "escreva a mensagem") + ">" + ic("send") + "Enviar mensagem</button></div></div>" +
      '<div class="td-dir rd-col"><span class="td-tit">Oferta para voltar</span>' + seg("renovOferta:" + id, [["creditos", "Créditos extras"], ["preco", "Preço especial"]], of.tipo, "pequeno") +
      (of.tipo === "creditos"
        ? '<div class="rd-linha"><label class="campo-adm"><span class="rot">Créditos</span><span class="caixa-campo fundo"><input inputmode="numeric" data-in="renovOf" data-id="' + esc(id) + '" data-k="tokens" value="' + esc(of.tokens) + '" style="width:0"><span class="sufixo">M tokens</span></span></label>' +
          '<label class="campo-adm"><span class="rot">Vale por</span><span class="caixa-campo fundo"><input readonly value="60 dias" style="width:0"></span></label></div>' +
          '<p class="nota-campo">Os créditos entram na conta quando a pessoa voltar a pagar, com o próximo pagamento confirmado. Ela recebe a oferta por e-mail.</p>'
        : '<div class="rd-linha"><label class="campo-adm"><span class="rot">Só este mês por</span><span class="caixa-campo fundo"><span class="pre">R$</span><input inputmode="decimal" data-in="renovOf" data-id="' + esc(id) + '" data-k="valor" value="' + esc(of.valor) + '" placeholder="' + esc(r.plano ? String(Math.round(r.plano.valor * 0.6)) : "") + '" style="width:0"></span></label>' +
          '<label class="campo-adm"><span class="rot">No plano</span><span class="caixa-campo fundo"><select data-in="renovOf" data-id="' + esc(id) + '" data-k="plano">' + ps.map(function (p) { return '<option value="' + esc(p.id) + '"' + (p.id === of.plano ? " selected" : "") + ">" + esc(p.nome) + " · " + esc(brl(p.valor)) + "</option>"; }).join("") + "</select></span></label></div>" +
          '<p class="nota-campo">Vale só para o próximo pagamento; depois volta ao preço do plano.</p>') +
      '<div class="res-acoes rd-pe"><span></span><button type="button" class="mini cheia" data-a="renovOfertaEnviar" data-id="' + esc(id) + '"' + attrDis(emailOff || (of.tipo === "creditos" ? !(Number(of.tokens) > 0) : !(numDec(of.valor) > 0)), emailOff ? email.falta : "preencha a oferta") + ">" + ic("local_offer") + "Enviar oferta</button></div></div></div>";
    return h;
  }
  A.renovAbrir = function (el) { if (U.renovacoes.sel) return; var id = el.dataset.id; U.renovacoes.aberto = String(U.renovacoes.aberto) === String(id) ? null : id; render(); };
  A.renovMsgEnviar = async function (el) {
    var id = el.dataset.id, t = (U.renovacoes.msg[id] || "").trim(); if (!t) return;
    el.disabled = true;
    var ok = await naHora("POST", "/api/admin/renovacoes/" + encodeURIComponent(id) + "/mensagem", { texto: t }, "Mensagem enviada");
    if (ok) { U.renovacoes.msg[id] = ""; render(); } else el.disabled = false;
  };
  A.renovOfertaEnviar = function (el) {
    var id = el.dataset.id, of = U.renovacoes.oferta[id], r = (((dadosDe("renovacoes") || {}).abertas) || []).filter(function (x) { return String(x.id) === String(id); })[0]; if (!of || !r) return;
    var dados = of.tipo === "creditos" ? { id: id, tipo: "creditos", tokens: Number(of.tokens) * 1e6 } : { id: id, tipo: "preco", valor: numDec(of.valor), plano: of.plano };
    var txt = of.tipo === "creditos" ? "Ofereci " + of.tokens + "M tokens para " + r.nome + " voltar (entram quando voltar a pagar)" : "Ofereci a " + r.nome + " o próximo mês por " + brl(numDec(of.valor)) + " no plano " + of.plano;
    enfileirar("renovacoes", "renov.oferta", id, dados, txt);
  };
  A.renovSelSair = function () { U.renovacoes.sel = null; render(); };
  A.renovSelTodas = function () { U.renovacoes.sel = {}; (((dadosDe("renovacoes") || {}).abertas) || []).forEach(function (r) { U.renovacoes.sel[r.id] = true; }); render(); };
  function renovSelIds() { var S = U.renovacoes.sel || {}; return Object.keys(S).filter(function (k) { return S[k]; }); }
  A.renovLembreteMassa = async function () {
    var ids = renovSelIds(); if (!ids.length) return; U.renovacoes.sel = null; render();
    var ok = 0; for (var i = 0; i < ids.length; i++) { try { await api("POST", "/api/admin/renovacoes/" + encodeURIComponent(ids[i]) + "/lembrete", {}); ok++; } catch (e) { /* segue */ } }
    toast(ok === ids.length ? "Lembrete enviado a " + ok + (ok === 1 ? " conta" : " contas") : ok + " de " + ids.length + " lembretes enviados", ok !== ids.length); ler("renovacoes");
  };
  A.renovTratarMassa = async function () {
    var ids = renovSelIds(); if (!ids.length) return; U.renovacoes.sel = null; render();
    var ok = 0; for (var i = 0; i < ids.length; i++) { try { await api("POST", "/api/admin/renovacoes/" + encodeURIComponent(ids[i]) + "/tratar", {}); ok++; } catch (e) { /* segue */ } }
    toast(ok + (ok === 1 ? " marcada como tratada" : " marcadas como tratadas"), ok !== ids.length); ler("renovacoes");
  };
  (function () {
    var t = null, segurou = false;
    document.addEventListener("pointerdown", function (ev) {
      var l = ev.target.closest("[data-rsel]"); if (!l || ev.target.closest("button") || U.renovacoes.sel) return;
      segurou = false;
      t = setTimeout(function () { segurou = true; U.renovacoes.sel = {}; U.renovacoes.sel[l.dataset.rsel] = true; render(); }, 450);
    });
    var parar = function () { clearTimeout(t); t = null; if (segurou) setTimeout(function () { segurou = false; }, 0); };
    ["pointerup", "pointercancel", "pointerleave"].forEach(function (n) { document.addEventListener(n, parar); });
    document.addEventListener("click", function (ev) {
      var l = ev.target.closest("[data-rsel]"); if (!l || !U.renovacoes.sel || segurou || ev.target.closest("button")) return;
      var id = l.dataset.rsel; U.renovacoes.sel[id] = !U.renovacoes.sel[id];
      if (!renovSelIds().length) U.renovacoes.sel = null;
      render();
    });
  })();
  A.renovTratar = async function (el) { el.disabled = true; var ok = await naHora("POST", "/api/admin/renovacoes/" + encodeURIComponent(el.dataset.id) + "/tratar", {}, "Marcada como tratada"); if (ok) ler("renovacoes"); else el.disabled = false; };
  A.renovReabrir = async function (el) { el.disabled = true; var ok = await naHora("POST", "/api/admin/renovacoes/" + encodeURIComponent(el.dataset.id) + "/reabrir", {}, "Reaberta"); if (ok) ler("renovacoes"); else el.disabled = false; };
  A.renovCfg = async function (el) {
    var d = dadosDe("renovacoes"); if (!d) return;
    var antes = Object.assign({ email: false, resumo: false, whats: false, tol: false }, d.config || {}), novo = Object.assign({}, antes);
    novo[el.dataset.k] = !antes[el.dataset.k];
    d.config = novo; render();
    var r = await naHora("POST", "/api/admin/renovacoes/config", novo, "Avisos atualizados");
    if (!r) { d.config = antes; render(); } else if (r.config) { d.config = r.config; render(); }
  };

  // e-mails
  A.passo = function (el) { U.emails.passo = Number(el.dataset.n) || 1; render(); };
  // Link do botao: um combobox com os enderecos do site; "Digitar outro link" troca por um campo livre.
  var LINKS_BOTAO = [["Abrir o Paulus", "https://paulus.ia.br/"], ["Planos e preços", "https://paulus.ia.br/assinatura/"], ["Cadastro", "https://paulus.ia.br/cadastro/"], ["Termos de uso", "https://paulus.ia.br/termos-de-uso/"], ["Política de privacidade", "https://paulus.ia.br/politica-de-privacidade/"]];
  function linkBotaoCampo(camp) {
    var v = camp.link || "", pre = LINKS_BOTAO.filter(function (l) { return l[1] === v; })[0], ab = !!U.emails.linkAberto;
    if (U.emails.linkManual || (v && !pre)) {
      return '<label class="campo-adm"><span class="rot">Link do botão</span><span class="caixa-campo"><input id="camp-link" data-in="campo" data-campo="camp.link" value="' + esc(v) + '" placeholder="https://" spellcheck="false">' +
        '<button type="button" class="btn-icone" data-a="linkLista" aria-label="Escolher da lista" title="Escolher da lista">' + ic("list") + "</button></span></label>";
    }
    var h = '<div class="campo-adm nf-combo link-combo"><span class="rot">Link do botão</span><button type="button" class="caixa-campo nf-combo-btn" data-a="linkAbrir" aria-haspopup="listbox" aria-expanded="' + ab + '">' +
      '<span class="corta">' + (pre ? esc(pre[0]) : '<span class="c-ink3">escolha um link</span>') + "</span>" + ic("expand_more") + "</button>";
    if (ab) h += '<div class="nf-cli-lista nf-combo-lista" role="listbox">' + LINKS_BOTAO.map(function (l) {
      var on = l[1] === v;
      return '<button type="button" role="option" aria-selected="' + on + '" class="nf-combo-op link-op' + (on ? " on" : "") + '" data-a="linkEscolher" data-v="' + esc(l[1]) + '"><span class="link-at"><b>' + esc(l[0]) + "</b><small>" + esc(l[1].replace(/^https:\/\//, "")) + "</small></span>" + (on ? ic("check") : "") + "</button>";
    }).join("") + '<button type="button" class="nf-combo-op link-op link-manual" data-a="linkManual"><span class="link-at"><b>' + ic("edit") + "Digitar outro link</b></span></button></div>";
    return h + "</div>";
  }
  A.linkAbrir = function () { U.emails.linkAberto = !U.emails.linkAberto; if (!U.emails.linkAberto && !U.emails.camp.link && U.emails.linkGuardado) U.emails.camp.link = U.emails.linkGuardado; render(); };
  A.linkEscolher = function (el) { U.emails.camp.link = el.dataset.v; U.emails.linkAberto = false; U.emails.linkManual = false; render(); };
  A.linkManual = function () { U.emails.linkAberto = false; U.emails.linkManual = true; if (LINKS_BOTAO.some(function (l) { return l[1] === U.emails.camp.link; })) U.emails.camp.link = ""; render(); var i = $("camp-link"); if (i) i.focus(); };
  A.linkLista = function () { U.emails.linkManual = false; U.emails.linkGuardado = U.emails.camp.link; if (!LINKS_BOTAO.some(function (l) { return l[1] === U.emails.camp.link; })) U.emails.camp.link = ""; U.emails.linkAberto = true; render(); };
  document.addEventListener("mousedown", function (ev) { if (U.emails.linkAberto && !ev.target.closest(".link-combo")) { U.emails.linkAberto = false; fecharLista(".link-combo .nf-combo-lista"); } });
  A.escolherPublico = function (el) { U.emails.camp.publico = el.dataset.id; render(); if (el.dataset.id === "escolhidas") A.escAbrir(); };
  A.escAbrir = function () {
    if (!(dadosDe("contas") || {}).contas) ler("contas");
    var sel = {}; (U.emails.escolhidas || []).forEach(function (c) { sel[c.id] = true; });
    abrirModal({ tipo: "escContas", q: "", sel: sel });
    setTimeout(function () { var i = $("escm-q"); if (i) i.focus(); }, 30);
  };
  A.escMarcar = function (el) { var S = E.modal.sel, id = el.dataset.id; S[id] = !S[id]; renderCamada(); };
  A.escConfirmar = function () {
    var S = E.modal.sel, todas = ((dadosDe("contas") || {}).contas) || [], antes = {};
    (U.emails.escolhidas || []).forEach(function (c) { antes[c.id] = c; });
    U.emails.escolhidas = Object.keys(S).filter(function (k) { return S[k]; }).map(function (k) { var c = todas.filter(function (x) { return String(x.id) === k; })[0] || antes[k]; return c ? { id: c.id, nome: c.nome, email: c.email } : null; }).filter(Boolean);
    fecharModal(); render();
  };
  // Fechar uma lista ao clicar fora: tira so a lista do DOM, sem repintar a tela no mousedown
  // (repintar trocava o botao sob o ponteiro e o clique se perdia). O proximo render ja vem sem ela.
  function fecharLista(sel) { document.querySelectorAll(sel).forEach(function (l) { var p = l.parentElement, b = p && p.querySelector('[aria-expanded="true"]'); if (b) b.setAttribute("aria-expanded", "false"); l.remove(); }); }
  A.escAdd = function (el) {
    var c = (((dadosDe("contas") || {}).contas) || []).filter(function (x) { return String(x.id) === String(el.dataset.id); })[0]; if (!c) return;
    U.emails.escolhidas = (U.emails.escolhidas || []).concat([{ id: c.id, nome: c.nome, email: c.email }]);
    U.emails.escQ = ""; U.emails.escAberto = true; render(); var i = $("esc-q"); if (i) i.focus();
  };
  A.escTirar = function (el) { U.emails.escolhidas = (U.emails.escolhidas || []).filter(function (c) { return String(c.id) !== String(el.dataset.id); }); render(); };
  document.addEventListener("focusin", function (ev) { if (ev.target.id === "esc-q" && !U.emails.escAberto) { U.emails.escAberto = true; render(); var i = $("esc-q"); if (i) i.focus(); } });
  document.addEventListener("mousedown", function (ev) { if (U.emails.escAberto && !ev.target.closest(".esc-busca")) { U.emails.escAberto = false; fecharLista(".esc-busca .nf-cli-lista"); } });
  A.usarPublico = function (el) { U.emails.camp.publico = el.dataset.id; U.emails.aba = "nova"; U.emails.passo = 2; render(); };
  function dadosCampanha() {
    var c = U.emails.camp, pub = publicoAtual();
    return { nome: c.nome.trim() || c.assunto.trim(), publico: pub ? pub.id : "", contas: pub && pub.id === "escolhidas" ? (U.emails.escolhidas || []).map(function (x) { return x.id; }) : undefined, assunto: c.assunto, pre: c.pre, titulo: c.titulo, texto: c.texto, botao: c.botao, link: c.link, quando: c.quando,
      // Agendada: o dia e a hora do calendario, no horario de Brasilia (o servidor dispara na hora marcada).
      de: c.quando === "agendado" ? c.de : undefined, hora: c.quando === "agendado" ? c.hora : undefined };
  }
  A.pedirDisparo = async function () {
    var c = U.emails.camp, pub = publicoAtual();
    if (!c.assunto.trim() || !c.texto.trim()) { toast("Preencha o assunto e o texto antes de pedir o disparo", true); U.emails.passo = 2; render(); return; }
    var dd = dadosCampanha(), n = pub ? pub.n || 0 : 0;
    var q = c.quando === "agendado" ? ddmm(c.de) + " às " + c.hora : { agora: "agora", amanha: "amanhã, 9h", segunda: "segunda, 9h" }[c.quando];
    var ok = await enfileirar("emails", "campanha.disparar", dd.nome, dd, 'Pedi o disparo "' + dd.nome + '" para ' + n + (n === 1 ? " conta" : " contas") + " (" + q + ")");
    if (ok) { var keep = { botao: c.botao, link: c.link }; U.emails.camp = novaCamp(); U.emails.camp.botao = keep.botao; U.emails.camp.link = keep.link; U.emails.so = null; U.emails.aba = "campanhas"; U.emails.passo = 1; render(); }
  };
  A.enviarTeste = function () { naHora("POST", "/api/admin/campanhas/teste", { campanha: dadosCampanha() }, "Teste enviado para " + (E.sessao.access && E.sessao.access.email || "você")); };

  // planos
  A.planosBaixar = function () {
    var ps = (dadosDe("planos") || {}).planos || [], t = U.planos.json != null ? U.planos.json : planosAtuais(ps);
    var a = document.createElement("a"); a.href = URL.createObjectURL(new Blob([t], { type: "application/json" })); a.download = "IA_PLANOS.json"; document.body.appendChild(a); a.click(); a.remove();
    setTimeout(function () { URL.revokeObjectURL(a.href); }, 1000);
  };
  A.planosRestaurar = function () { U.planos.json = null; render(); };
  A.planosSalvarJson = function () {
    var t = U.planos.json; if (t == null || validaPlanos(t)) return;
    var v = JSON.parse(t);
    enfileirar("planos", "planos.json", "IA_PLANOS", { planos: v }, "Atualizei o IA_PLANOS (" + v.length + (v.length === 1 ? " plano" : " planos") + ")").then(function () { U.planos.json = null; render(); });
  };
  function planoEd(p) {
    var e = U.planos.ed;
    if (!e || e.id !== p.id) e = U.planos.ed = { id: p.id, v: { nome: p.nome, para: p.para || "", heranca: p.heranca || "", valor: String(p.valor).replace(".", ","), anual: String(p.valor_anual || "").replace(".", ","), tokens: dec(p.tokens / 1e6, 2), pessoas: String(p.pessoas || 1), rv: p.recarga ? String(p.recarga.valor).replace(".", ",") : "", rt: p.recarga ? dec(p.recarga.tokens / 1e6, 2) : "" }, itens: (p.itens || []).map(function (x) { return { titulo: x.titulo, descricao: x.descricao || "" }; }) };
    return e;
  }
  A.planoEdItemMais = function () { var e = U.planos.ed; if (!e) return; e.itens.push({ titulo: "", descricao: "" }); render(); };
  A.planoEdItemTirar = function (el) { var e = U.planos.ed; if (!e) return; e.itens.splice(Number(el.dataset.i), 1); render(); };
  A.planoEdItemMover = function (el) { var e = U.planos.ed; if (!e) return; var k = Number(el.dataset.i), d = Number(el.dataset.d), x = e.itens[k]; e.itens.splice(k, 1); e.itens.splice(k + d, 0, x); render(); };
  A.planoIrEdicao = function () { U.planos.lado = "edicao"; render(); };
  A.planoEdDesfazer = function () { U.planos.ed = null; render(); };
  A.planoEdSalvar = function () {
    var e = U.planos.ed; if (!e) return; var v = e.v;
    var dados = { id: e.id, nome: v.nome.trim(), para: v.para.trim(), heranca: v.heranca.trim() || null, valor: numDec(v.valor), valor_anual: numDec(v.anual), tokens: Math.round(numDec(v.tokens) * 1e6), pessoas: Math.round(numDec(v.pessoas)) || 1,
      recarga: numDec(v.rv) > 0 ? { valor: numDec(v.rv), tokens: Math.round(numDec(v.rt) * 1e6) } : null,
      itens: e.itens.filter(function (x) { return x.titulo.trim(); }).map(function (x) { return { titulo: x.titulo.trim(), descricao: x.descricao.trim() }; }) };
    if (!dados.nome || !(dados.valor > 0) || !(dados.valor_anual > 0) || !(dados.tokens > 0)) { toast("Preencha nome, valores e créditos", true); return; }
    enfileirar("planos", "plano.editar", e.id, dados, "Editei o plano " + dados.nome + " (" + brl(dados.valor) + "/mês, " + dados.itens.length + " itens)").then(function () { U.planos.ed = null; render(); });
  };
  A.planoVersao = function (el) { var n = el.dataset.n; U.planos.versao = String(U.planos.versao) === n ? null : n; render(); };
  A.planoUsarVersao = function (el) {
    var v = ((dadosDe("planos") || {}).versoes || []).filter(function (x) { return String(x.n) === el.dataset.n; })[0]; if (!v) return;
    U.planos.json = JSON.stringify(v.planos, null, 2); U.planos.lado = "json"; U.planos.versao = null; render(); toast("Versão " + v.n + " no editor: confira e salve");
  };
  A.copiarJson = async function () {
    var d = dadosDe("planos"); if (!d) return;
    try { await navigator.clipboard.writeText(U.planos.json != null ? U.planos.json : planosAtuais(d.planos || [])); toast("JSON copiado"); } catch (e) { toast("Não consegui copiar: o navegador não deixou", true); }
  };
  A.modalPlano = function (el) {
    var p = ((dadosDe("planos") || {}).planos || []).filter(function (x) { return x.id === el.dataset.id; })[0]; if (!p) return;
    abrirModal({ tipo: "plano", id: p.id, nome: p.nome, va: p.valor, aa: p.valor_anual, ta: p.tokens, valor: String(p.valor).replace(".", ","),
      anual: String(p.valor_anual || "").replace(".", ","), tokens: dec(p.tokens / 1e6, 2), usd: p.custo_modelo, modelo: p.modelo_nome });
  };
  A.planoSalvar = function () {
    var M = E.modal, nv = numDec(M.valor), na = numDec(M.anual), nt = Math.round(numDec(M.tokens) * 1e6);
    if (!(nv > 0) || !(na > 0) || !(nt > 0)) return;
    if (nv === M.va && na === M.aa && nt === M.ta) { fecharModal(); toast("Nada mudou no plano " + M.nome); return; }
    var partes = [];
    if (nv !== M.va) partes.push("mês " + brl(M.va) + " → " + brl(nv));
    if (na !== M.aa) partes.push("ano " + brl(M.aa) + " → " + brl(na));
    if (nt !== M.ta) partes.push("créditos " + tok(M.ta) + " → " + tok(nt));
    var txt = "Mudei o plano " + M.nome + ": " + partes.join(" · ");
    var id = M.id;
    fecharModal();
    enfileirar("planos", "plano.editar", id, { id: id, valor: nv, valor_anual: na, tokens: nt }, txt);
  };
  A.criarPlano = async function () {
    var np = U.planos.novo, id = np.id.trim(), nome = np.nome.trim(), v = numDec(np.valor), va = numDec(np.anual), t = Math.round(numDec(np.tokens) * 1e6);
    var ps = (dadosDe("planos") || {}).planos || [];
    var erro = !nome ? "Dê um nome ao plano" : !/^[a-z0-9-]{2,24}$/.test(id) ? "O id precisa de 2 a 24 letras minúsculas, números ou hífen" :
      ps.some(function (p) { return p.id === id; }) ? "Já existe um plano com o id " + id : !(v > 0) ? "Diga o valor por mês" : !(va > 0) ? "Diga o valor por ano" : !(t > 0) ? "Diga os créditos por mês" : "";
    if (erro) { toast(erro, true); return; }
    var ok = await enfileirar("planos", "plano.criar", id, { id: id, nome: nome, valor: v, valor_anual: va, tokens: t }, "Criei o plano " + nome + " · " + brl(v) + "/mês · " + brl(va) + "/ano · " + tok(t) + " créditos");
    if (ok) { U.planos.novo = { nome: "", id: "", valor: "", anual: "", tokens: "" }; render(); }
  };

  function contaAtual() { return E.gaveta && (E.gaveta.det || E.gaveta.resumo); }
  A.contaPlano = function () {
    var c = contaAtual(); if (!c) return;
    var M = { tipo: "contaPlano", id: c.id, nome: c.nome, email: c.email, atual: c.plano && c.plano.id, escolhido: c.plano && c.plano.id, planos: null, erro: "" };
    var ps = (dadosDe("planos") || {}).planos;
    if (ps) M.planos = ps;
    abrirModal(M);
    if (!ps) api("GET", "/api/admin/planos").then(function (d) { if (E.modal === M) { M.planos = d.planos || []; renderCamada(); } }, function (e) { if (E.modal === M) { M.erro = e.message; renderCamada(); } });
  };
  A.contaPlanoEscolher = function (el) { E.modal.escolhido = el.dataset.id; renderCamada(); };
  A.contaPlanoSalvar = function () {
    var M = E.modal, p = (M.planos || []).filter(function (x) { return x.id === M.escolhido; })[0]; if (!p) return;
    var antes = (M.planos || []).filter(function (x) { return x.id === M.atual; })[0];
    fecharModal();
    enfileirar("contas", "conta.plano", M.id, { id: M.id, plano: p.id }, "Troquei o plano de " + M.nome + ": " + (antes ? antes.nome : "—") + " → " + p.nome + " na renovação");
  };
  A.contaCadastro = function () {
    var c = contaAtual(); if (!c || !E.gaveta.det) return;
    var d = E.gaveta.det, cad = d.cadastro || {}, es = d.escritorio || {};
    var v = { escritorio: es.nome || "", documento: cad.documento || es.documento || "", oab: cad.oab || d.oab || "", telefone: cad.telefone || "",
      cep: cad.cep || "", logradouro: cad.logradouro || "", numero: cad.numero || "", complemento: cad.complemento || "", bairro: cad.bairro || "", cidade: cad.cidade || "", uf: cad.uf || "" };
    abrirModal({ tipo: "contaCadastro", id: c.id, nome: c.nome, email: c.email, v: v, antes: Object.assign({}, v) });
  };
  A.contaCadastroSalvar = function () {
    var M = E.modal, mud = Object.keys(M.v).filter(function (k) { return M.v[k].trim() !== M.antes[k]; });
    if (!mud.length) { fecharModal(); toast("Nada mudou no cadastro de " + M.nome); return; }
    var dados = { id: M.id }; mud.forEach(function (k) { dados[k] = M.v[k].trim(); });
    fecharModal();
    enfileirar("contas", "conta.cadastro", M.id, dados, "Editei o cadastro de " + M.nome + " (" + mud.length + (mud.length === 1 ? " campo)" : " campos)"));
  };
  var MESES_C = ["janeiro", "fevereiro", "março", "abril", "maio", "junho", "julho", "agosto", "setembro", "outubro", "novembro", "dezembro"];
  function isoDia(d) { return d.getFullYear() + "-" + pad(d.getMonth() + 1) + "-" + pad(d.getDate()); }
  function calHtml(C) {
    var m = C.mes, ini = new Date(m.getFullYear(), m.getMonth(), 1), hoje = isoDia(new Date());
    var comeco = new Date(ini); comeco.setDate(1 - ini.getDay());
    var vista = C.vista || "dias", ano = m.getFullYear(), ano0 = ano - (ano % 12);
    var titulo = vista === "dias" ? MESES_C[m.getMonth()] + " " + ano : vista === "meses" ? String(ano) : ano0 + " – " + (ano0 + 11);
    var h = '<div class="calendario-adm" role="dialog" aria-label="Escolher período"><div class="cal-topo"><button type="button" class="btn-icone" data-a="calMes" data-d="-1" aria-label="Anterior">' + ic("chevron_left") + "</button>" +
      '<button type="button" class="cal-titulo" data-a="calVista"' + (vista === "anos" ? " disabled" : "") + ">" + titulo + '</button><button type="button" class="btn-icone" data-a="calMes" data-d="1" aria-label="Próximo">' + ic("chevron_right") + "</button></div>";
    if (vista === "meses") {
      h += '<div class="cal-grade meses">' + MESES_C.map(function (nm, i) { return '<button type="button" class="cal-celula' + (i === m.getMonth() ? " escolhido" : "") + '" data-a="calEscMes" data-m="' + i + '">' + nm.slice(0, 3) + "</button>"; }).join("") + "</div>";
    } else if (vista === "anos") {
      h += '<div class="cal-grade meses">'; for (var y = ano0; y < ano0 + 12; y++) h += '<button type="button" class="cal-celula' + (y === ano ? " escolhido" : "") + '" data-a="calEscAno" data-y="' + y + '">' + y + "</button>"; h += "</div>";
    }
    if (vista !== "dias") return h + "</div>";
    h += '<div class="cal-grade dias">' + ["D", "S", "T", "Q", "Q", "S", "S"].map(function (s) { return '<span class="cal-semana">' + s + "</span>"; }).join("");
    for (var i = 0; i < 42; i++) {
      var d = new Date(comeco); d.setDate(comeco.getDate() + i); var iso = isoDia(d);
      var cls = "cal-dia" + (d.getMonth() !== m.getMonth() ? " fora-do-mes" : "") + (iso === hoje ? " hoje" : "") +
        (iso === C.ini || iso === C.fim ? " escolhido" : "") + (C.ini && C.fim && iso > C.ini && iso < C.fim ? " no-intervalo" : "");
      var antes = C.unico && iso < hoje;
      h += '<button type="button" class="' + cls + (antes ? " passado" : "") + '" data-a="calDia" data-dia="' + iso + '"' + (antes ? " disabled" : "") + ">" + d.getDate() + "</button>";
    }
    // Um dia so e a hora: o mesmo relogio do Paulus (16-dialogos.js), mostrador e duas reguas.
    if (C.unico) {
      var hh = C.h == null ? 9 : C.h, mm = C.m == null ? 0 : C.m;
      return h + '</div><div class="relogio-adm"><div class="relogio-mostrador"><b data-rel-h>' + pad(hh) + "</b><i>:</i><b data-rel-m>" + pad(mm) + "</b></div>" +
        '<label class="relogio-regua"><span>Horas</span><input type="range" min="0" max="23" step="1" value="' + hh + '" data-in="calHora" data-k="h" style="--andado:' + (hh / 23 * 100) + '%"></label>' +
        '<label class="relogio-regua"><span>Minutos</span><input type="range" min="0" max="55" step="5" value="' + mm + '" data-in="calHora" data-k="m" style="--andado:' + (mm / 55 * 100) + '%"></label></div>' +
        '<div class="cal-rodape"><button type="button" class="btn-texto-mudo" data-a="calLimpar">Limpar</button><button type="button" class="btn-duplo pequeno" data-a="calAplicar"' + (C.ini ? "" : " disabled") + "><span>Agendar</span></button></div></div>";
    }
    // Inicio e fim em duas caixas; a que o proximo clique preenche fica acesa.
    var proxima = !C.ini || C.fim ? "ini" : "fim";
    var caixa = function (k, rot, v) { return '<span class="cal-ponta' + (proxima === k ? " ativa" : "") + '"><small>' + rot + "</small><b>" + (v ? esc(ddmmaaaa(v)) : '<span class="c-ink3">dd/mm/aaaa</span>') + "</b></span>"; };
    h += '</div><div class="cal-pontas">' + caixa("ini", "Início", C.ini) + ic("arrow_forward") + caixa("fim", "Fim", C.fim) + "</div>" +
      '<div class="cal-rodape"><button type="button" class="btn-texto-mudo" data-a="calLimpar">Limpar</button><button type="button" class="btn-duplo pequeno" data-a="calAplicar"' + (C.ini ? "" : " disabled") + "><span>Aplicar</span></button></div></div>";
    return h;
  }
  A.extratoCal = function () {
    var M = E.modal; if (!M) return;
    if (M.cal) { M.cal = null; renderCamada(); return; }
    var base = M.periodo === "custom" && M.de ? new Date(M.de + "T12:00") : new Date();
    M.cal = { mes: new Date(base.getFullYear(), base.getMonth(), 1), ini: M.periodo === "custom" ? M.de : null, fim: M.periodo === "custom" ? M.ate : null };
    renderCamada();
  };
  // O calendario serve ao extrato (no modal) e ao registro de enderecos (na tela): calCtx diz qual esta aberto.
  function calCtx() {
    if (E.modal && E.modal.cal) return { M: E.modal, C: E.modal.cal, pinta: renderCamada };
    if (U.emails && U.emails.camp && U.emails.camp.cal) return { M: U.emails.camp, C: U.emails.camp.cal, pinta: render };
    if (U.tuneis.cal) return { M: U.tuneis, C: U.tuneis.cal, pinta: render };
    if (U.tokens.cal) return { M: U.tokens, C: U.tokens.cal, pinta: function () { if (U.tokens.periodo === "custom" && !U.tokens.cal) ler(tokensChave()); render(); } };
    return null;
  }
  A.calMes = function (el) {
    var x = calCtx(); if (!x) return; var C = x.C, d = Number(el.dataset.d), v = C.vista || "dias";
    C.mes = v === "dias" ? new Date(C.mes.getFullYear(), C.mes.getMonth() + d, 1) : new Date(C.mes.getFullYear() + d * (v === "anos" ? 12 : 1), C.mes.getMonth(), 1);
    x.pinta();
  };
  A.calVista = function () { var x = calCtx(); if (!x) return; x.C.vista = (x.C.vista || "dias") === "dias" ? "meses" : "anos"; x.pinta(); };
  A.calEscMes = function (el) { var x = calCtx(); if (!x) return; x.C.mes = new Date(x.C.mes.getFullYear(), Number(el.dataset.m), 1); x.C.vista = "dias"; x.pinta(); };
  A.calEscAno = function (el) { var x = calCtx(); if (!x) return; x.C.mes = new Date(Number(el.dataset.y), x.C.mes.getMonth(), 1); x.C.vista = "meses"; x.pinta(); };
  A.calDia = function (el) {
    var x = calCtx(), d = el.dataset.dia; if (!x) return; var C = x.C;
    if (C.unico) { C.ini = C.fim = d; } else if (!C.ini || C.fim) { C.ini = d; C.fim = null; } else if (d < C.ini) { C.fim = C.ini; C.ini = d; } else C.fim = d;
    x.pinta();
  };
  A.calLimpar = function () { var x = calCtx(); if (!x) return; if (x.C.unico) { x.M.quando = "agora"; x.M.de = null; x.M.cal = null; x.pinta(); return; } var tok_ = x.M === U.tokens; x.M.cal = null; if (x.M.periodo === "custom") { x.M.periodo = tok_ ? "mes" : "tudo"; if (tok_) ler(tokensChave()); } x.pinta(); };
  A.calAplicar = function () { var x = calCtx(); if (!x || !x.C.ini) return;
    if (x.C.unico) { x.M.de = x.C.ini; x.M.hora = pad(x.C.h == null ? 9 : x.C.h) + ":" + pad(x.C.m == null ? 0 : x.C.m); x.M.quando = "agendado"; x.M.cal = null; x.pinta(); return; }
    x.M.de = x.C.ini; x.M.ate = x.C.fim || x.C.ini; x.M.periodo = "custom"; x.M.cal = null; x.pinta(); };
  A.campAgendar = function () {
    var c = U.emails.camp; if (c.cal) { c.cal = null; render(); return; }
    var base = c.de ? new Date(c.de + "T12:00") : new Date(), hr = (c.hora || "09:00").split(":");
    c.cal = { unico: true, mes: new Date(base.getFullYear(), base.getMonth(), 1), ini: c.de || null, fim: c.de || null, h: Number(hr[0]), m: Number(hr[1]) };
    render();
  };
  function membroDe(email) { return ((dadosDe("equipe") || {}).membros || []).filter(function (m) { return m.email === email; })[0]; }
  A.membroNovo = function () { abrirModal({ tipo: "membro", novo: true, v: { nome: "", email: "", papel: "suporte" } }); setTimeout(function () { var i = $("mb-nome"); if (i) i.focus(); }, 30); };
  A.membroEditar = function (el) { var m = membroDe(el.dataset.id); if (!m) return; abrirModal({ tipo: "membro", novo: false, de: m.email, v: { nome: m.nome || "", email: m.email, papel: m.papel } }); };
  A.membroSalvar = function () {
    var M = E.modal, v = M.v; fecharModal();
    enfileirar("equipe", "equipe.membro", M.novo ? v.email : M.de, { acao: M.novo ? "criar" : "editar", de: M.de || null, nome: v.nome.trim(), email: v.email.trim(), papel: v.papel },
      M.novo ? "Convidei " + v.nome.trim() + " (" + v.email.trim() + ") como " + v.papel : "Editei " + v.nome.trim() + " na equipe");
  };
  A.conviteReenviar = async function (el) { el.disabled = true; var ok = await naHora("POST", "/api/admin/equipe/convite/" + encodeURIComponent(el.dataset.id) + "/reenviar", {}, "Convite reenviado, vale por mais 7 dias"); if (ok) ler("equipe"); else el.disabled = false; };
  A.membroExcluir = function (el) { var m = membroDe(el.dataset.id); if (!m) return; abrirModal({ tipo: "membroExcluir", email: m.email, nome: m.nome, convite: !!m.convite }); };
  A.membroExcluirOk = function () { var M = E.modal; fecharModal(); enfileirar("equipe", "equipe.membro", M.email, { acao: M.convite ? "cancelar_convite" : "excluir", email: M.email }, M.convite ? "Cancelei o convite de " + (M.nome || M.email) : "Tirei " + (M.nome || M.email) + " da equipe"); };
  A.tokSelSair = function () { U.tokens.sel = null; render(); };
  A.tokSelTodas = function () { var d = dadosDe(tokensChave()); U.tokens.sel = {}; ((d && d.linhas) || []).forEach(function (l) { U.tokens.sel[l.nome] = true; }); render(); };
  (function () {
    var t = null, segurou = false;
    document.addEventListener("pointerdown", function (ev) {
      var l = ev.target.closest("[data-ksel]"); if (!l || U.tokens.sel) return;
      segurou = false; t = setTimeout(function () { segurou = true; U.tokens.sel = {}; U.tokens.sel[l.dataset.ksel] = true; render(); }, 450);
    });
    var parar = function () { clearTimeout(t); t = null; if (segurou) setTimeout(function () { segurou = false; }, 0); };
    ["pointerup", "pointercancel", "pointerleave"].forEach(function (n) { document.addEventListener(n, parar); });
    document.addEventListener("click", function (ev) {
      var l = ev.target.closest("[data-ksel]"); if (!l || !U.tokens.sel || segurou) return;
      var k = l.dataset.ksel; U.tokens.sel[k] = !U.tokens.sel[k];
      if (!Object.keys(U.tokens.sel).some(function (x) { return U.tokens.sel[x]; })) U.tokens.sel = null;
      render();
    });
  })();
  A.tokCal = function () {
    var T = U.tokens; if (T.cal) { T.cal = null; render(); return; }
    var base = T.periodo === "custom" && T.de ? new Date(T.de + "T12:00") : new Date();
    T.cal = { mes: new Date(base.getFullYear(), base.getMonth(), 1), ini: T.periodo === "custom" ? T.de : null, fim: T.periodo === "custom" ? T.ate : null };
    render();
  };
  A.regCal = function () {
    var T = U.tuneis; if (T.cal) { T.cal = null; render(); return; }
    var base = T.periodo === "custom" && T.de ? new Date(T.de + "T12:00") : new Date();
    T.cal = { mes: new Date(base.getFullYear(), base.getMonth(), 1), ini: T.periodo === "custom" ? T.de : null, fim: T.periodo === "custom" ? T.ate : null };
    render();
  };
  var MODALIDADE = { assinatura: "Assinatura mensal", anual: "Assinatura anual", avulso: "Mês avulso", recarga: "Recarga avulsa" };
  function descPag(x, M) { return x.tipo === "recarga" ? "Recarga" + (x.tokens ? " de " + tok(x.tokens) + " tokens" : "") : "Plano " + (M.plano || ""); }
  // A forma: o simbolo do Pix e a chave, ou a bandeira do cartao e o final.
  var PIX_SVG = '<svg class="pix-ic" viewBox="0 0 16 16" width="14" height="14" aria-hidden="true"><path fill="currentColor" d="M12.3 11.9a2 2 0 0 1-1.4-.6L8.6 9a.4.4 0 0 0-.6 0l-2.3 2.3a2 2 0 0 1-1.4.6h-.5l2.9 2.9a2.3 2.3 0 0 0 3.3 0l2.9-2.9h-.6ZM4.3 4.1a2 2 0 0 1 1.4.6L8 7a.4.4 0 0 0 .6 0l2.3-2.3a2 2 0 0 1 1.4-.6h.4L9.8 1.2a2.3 2.3 0 0 0-3.3 0L3.7 4.1h.6Zm10.5 2.2L13 4.6h-.7a1.4 1.4 0 0 0-1 .4L9.1 7.3a1.1 1.1 0 0 1-1.6 0L5.3 5a1.4 1.4 0 0 0-1-.4h-.9L1.2 6.3a2.3 2.3 0 0 0 0 3.3l1.7 1.7h1a1.4 1.4 0 0 0 1-.4l2.3-2.3a1.1 1.1 0 0 1 1.6 0l2.3 2.3a1.4 1.4 0 0 0 1 .4h.7l1.7-1.7a2.3 2.3 0 0 0 0-3.3Z"/></svg>';
  // A bandeira do cartao desenhada no cartaozinho branco (Visa, Mastercard); as outras vao pelo nome.
  function bandeiraHtml(b) {
    var k = String(b || "").toLowerCase();
    if (k === "mastercard") return '<span class="bandeira-c" aria-label="Mastercard"><svg viewBox="0 0 24 16" width="24" height="16" aria-hidden="true"><circle cx="9.5" cy="8" r="5" fill="#EB001B"/><circle cx="14.5" cy="8" r="5" fill="#F79E1B"/><path d="M12 3.6a5 5 0 0 1 0 8.8 5 5 0 0 1 0-8.8Z" fill="#FF5F00"/></svg></span>';
    if (k === "visa") return '<span class="bandeira-c" aria-label="Visa"><svg viewBox="0 0 24 16" width="24" height="16" aria-hidden="true"><text x="12" y="11.2" text-anchor="middle" font-family="Arial, Helvetica, sans-serif" font-size="8.4" font-weight="700" font-style="italic" fill="#1A1F71" letter-spacing=".2">VISA</text></svg></span>';
    return '<span class="bandeira">' + esc(b || "Cartão") + "</span>";
  }
  function formaHtml(f) {
    if (!f) return '<span class="c-ink3">—</span>';
    if (f.tipo === "pix") return '<span class="forma" title="Pix · ' + esc(f.chave || "") + '">' + PIX_SVG + '<span class="corta">' + esc(f.chave || "Pix") + "</span></span>";
    return '<span class="forma" title="' + esc((f.bandeira || "Cartão") + " final " + (f.final || "")) + '">' + bandeiraHtml(f.bandeira) + '<span class="num">•••• ' + esc(f.final || "") + "</span></span>";
  }
  function extratoLinhas(M) {
    var fT = M.filtro || "todos", fP = M.periodo || "tudo", agora = Date.now(), ano = String(new Date().getFullYear());
    return M.itens.filter(function (x) {
      var okT = fT === "todos" || (fT === "reembolsados" ? !!x.reembolso : !x.reembolso && x.tipo === fT);
      var dd = (agora - Date.parse(x.quando)) / 864e5;
      var dia = String(x.quando).slice(0, 10);
      return okT && (fP === "tudo" || (fP === "custom" ? dia >= M.de && dia <= M.ate : fP === "ano" ? dia.slice(0, 4) === ano : dd <= Number(fP)));
    }).map(function (x) {
      // A NFS-e do pagamento: o numero, o estado e os links do painel para o PDF e o XML (atras do Access).
      var nf = x.nfse ? { numero: x.nfse.numero, estado: x.nfse.estado || "emitida", pdf: x.nfse.pdf || location.origin + NF + "notas/" + x.nfse.id + "/pdf?baixar=1", xml: x.nfse.xml || location.origin + NF + "notas/" + x.nfse.id + "/xml" } : null;
      return { data: (x.quando || "").slice(0, 10), descricao: descPag(x, M), forma: x.forma ? (x.forma.tipo === "pix" ? "Pix " + (x.forma.chave || "") : (x.forma.bandeira || "Cartão") + " •••• " + (x.forma.final || "")) : null, modalidade: MODALIDADE[x.tipo] || null, valor: Number(x.valor) || 0, status: x.reembolso ? "reembolsada" : (x.situacao || "pago"), nfse: nf, ref: x.ref };
    });
  }
  A.contaPausar = function (el) {
    var c = contaAtual() || contaResumo(el.dataset.id); if (!c) return;
    enfileirar("contas", "conta.pausar", c.id, { id: c.id }, "Pausei a cobrança da assinatura de " + c.nome + " no Mercado Pago");
  };
  A.copiarTexto = async function (el) { try { await navigator.clipboard.writeText(el.dataset.t || ""); toast("Copiado"); } catch (e) { toast("O navegador não deixou copiar", true); } };
  A.extratoJson = function () {
    var M = E.modal; if (!M || M.tipo !== "contaExtrato") return;
    var b = new Blob([JSON.stringify({ conta: { id: M.id, nome: M.nome, email: M.email }, gerado: new Date().toISOString(), pagamentos: extratoLinhas(M) }, null, 2)], { type: "application/json" });
    var a = document.createElement("a"); a.href = URL.createObjectURL(b); a.download = "extrato-" + M.id + ".json"; document.body.appendChild(a); a.click(); a.remove();
    setTimeout(function () { URL.revokeObjectURL(a.href); }, 1000);
  };
  // O PDF sai pela impressao do navegador, numa pagina limpa so com a tabela.
  A.extratoPdf = function () {
    var M = E.modal; if (!M || M.tipo !== "contaExtrato") return;
    var ls = extratoLinhas(M), tot = ls.reduce(function (s, x) { return s + (x.status === "reembolsada" ? 0 : x.valor); }, 0);
    var w = window.open("", "_blank"); if (!w) { toast("O navegador bloqueou a janela do PDF", true); return; }
    w.document.write('<!doctype html><html lang="pt-BR"><head><meta charset="utf-8"><title>Extrato · ' + esc(M.nome) + '</title><style>body{font:13px/1.5 system-ui,sans-serif;color:#1c1c1a;margin:32px}h1{font-size:18px;margin:0 0 2px}p{margin:0 0 18px;color:#66655f}table{width:100%;border-collapse:collapse}th,td{text-align:left;padding:8px 6px;border-bottom:1px solid #ddd}th{font-weight:600;font-size:12px}td.n,th.n{text-align:right;font-variant-numeric:tabular-nums}tfoot td{font-weight:600;border-top:2px solid #1c1c1a}</style></head><body>' +
      "<h1>Extrato · " + esc(M.nome) + "</h1><p>" + esc(M.email) + " · gerado em " + esc(ddmmaaaa(new Date().toISOString())) + "</p><table><thead><tr><th>Data</th><th>Descrição</th><th>Forma</th><th class=\"n\">Valor</th><th>Modalidade</th><th>Status</th><th>NFS-e</th></tr></thead><tbody>" +
      ls.map(function (x) {
        var nf = x.nfse ? esc(x.nfse.numero || "—") + (x.nfse.estado !== "emitida" ? " (" + esc(x.nfse.estado === "substituida" ? "substituída" : x.nfse.estado) + ")" : "") +
          ' · <a href="' + esc(x.nfse.pdf) + '">PDF</a> · <a href="' + esc(x.nfse.xml) + '">XML</a>' : "—";
        return "<tr><td>" + esc(ddmmaaaa(x.data)) + "</td><td>" + esc(x.descricao) + "</td><td>" + esc(x.forma || "—") + '</td><td class="n">' + esc(brl(x.valor)) + "</td><td>" + esc(x.modalidade || "—") + "</td><td>" + esc(x.status) + "</td><td>" + nf + "</td></tr>";
      }).join("") +
      '</tbody><tfoot><tr><td></td><td>Total pago</td><td></td><td class="n">' + esc(brl(tot)) + "</td><td></td><td></td><td></td></tr></tfoot></table></body></html>");
    w.document.close(); w.focus(); setTimeout(function () { w.print(); }, 200);
  };
  A.contaExtrato = function () {
    var c = contaAtual(); if (!c || !E.gaveta.det) return;
    var ass = E.gaveta.det.assinatura, prep = ass && (ass.periodo === "anual" || ass.periodo === "avulso");
    abrirModal({ tipo: "contaExtrato", id: c.id, nome: c.nome, email: c.email, plano: c.plano ? c.plano.nome : "", valor: c.plano ? c.plano.valor : null, pagoAte: E.gaveta.det.pago_ate, proxima: E.gaveta.det.ciclo ? E.gaveta.det.ciclo.fim : null,
      ass: ass ? { periodo: ass.periodo, situacao: ass.situacao, desde: ass.desde, id: ass.id, prepago: prep } : null, itens: (E.gaveta.det.pagamentos || []).slice().sort(function (a, b) { return Date.parse(b.quando) - Date.parse(a.quando); }) });
  };

  A.googleSelSair = function () { U.google.sel = null; render(); };
  A.googleSelTodas = function () {
    var gs = ((dadosDe("contas") || {}).contas || []).filter(function (c) { return c.google && !naFila("google.desvincular", c.id); });
    U.google.sel = {}; gs.forEach(function (c) { U.google.sel[c.id] = true; }); render();
  };
  A.googleDesvMassa = async function () {
    var S = U.google.sel || {}, ids = Object.keys(S).filter(function (k) { return S[k]; }); if (!ids.length) return;
    var cs = ((dadosDe("contas") || {}).contas || []);
    U.google.sel = null; render();
    for (var i = 0; i < ids.length; i++) {
      var c = cs.filter(function (x) { return String(x.id) === ids[i]; })[0]; if (!c) continue;
      await enfileirar("google", "google.desvincular", c.id, { id: c.id }, "Desvinculei a conta Google de " + c.nome, i < ids.length - 1);
    }
  };
  // Segurar 450 ms numa linha entra na selecao; ja selecionando, o clique marca e desmarca.
  (function () {
    var t = null, alvo = null, segurou = false;
    document.addEventListener("pointerdown", function (ev) {
      var l = ev.target.closest("[data-gsel]"); if (!l || ev.target.closest("button")) return;
      alvo = l; segurou = false;
      if (U.google.sel) return;
      t = setTimeout(function () { segurou = true; U.google.sel = {}; U.google.sel[alvo.dataset.gsel] = true; U.google.confirmando = null; render(); }, 450);
    });
    var cancelar = function () { clearTimeout(t); t = null; if (segurou) setTimeout(function () { segurou = false; }, 0); };
    document.addEventListener("pointerup", cancelar); document.addEventListener("pointerleave", cancelar); document.addEventListener("pointercancel", cancelar);
    document.addEventListener("click", function (ev) {
      var l = ev.target.closest("[data-gsel]"); if (!l || !U.google.sel) return;
      if (segurou) { segurou = false; return; }
      if (ev.target.closest("button")) return;
      var id = l.dataset.gsel; U.google.sel[id] = !U.google.sel[id];
      if (!Object.keys(U.google.sel).some(function (k) { return U.google.sel[k]; })) U.google.sel = null;
      render();
    });
  })();

  var visaoTodas = false, avisosTodos = false;
  A.avisosVerMais = function () { avisosTodos = !avisosTodos; render(); };
  A.visaoVerMais = function () { visaoTodas = !visaoTodas; render(); };

  // materiais
  A.materialAbrir = function (el) { var id = el.dataset.id; U.materiais.aberto = U.materiais.aberto === id ? null : id; render(); };
  A.materialCheck = function (el) {
    var id = U.materiais.aberto, k = el.dataset.k, ch = U.materiais.checks[id] || (U.materiais.checks[id] = {});
    ch[k] = !ch[k]; render();
  };
  A.materialSit = function (el) {
    var m = ((dadosDe("materiais") || {}).materiais || []).filter(function (x) { return x.id === U.materiais.aberto; })[0]; if (!m) return;
    var v = el.dataset.v, recado = U.materiais.recados[m.id] || "";
    var sitv = v === "tirar" ? "recusado" : v;
    var verbo = { publicado: "Publiquei", ajustes: "Pedi ajustes em", recusado: "Recusei", tirar: "Tirei do ar" }[v];
    enfileirar("materiais", "material.situacao", m.id, { id: m.id, situacao: sitv, recado: recado }, verbo + ' "' + m.titulo + '" de ' + m.autor);
  };

  // nfse
  A.nfseCfg = function (el) {
    var d = dadosDe("nfse"); if (!d) return;
    var pc = ultimaNaFila("nfse.config"), atual = Object.assign({ auto: false, email: false, mail: false }, pc ? pc.dados : d.config || {});
    var k = el.dataset.k, novo = Object.assign({}, atual); novo[k] = !atual[k];
    var tit = { auto: "emitir ao confirmar o pagamento", email: "entregar ao app do cliente logo depois de emitir", mail: "mandar também por e-mail" }[k];
    enfileirar("nfse", "nfse.config", "config", { auto: !!novo.auto, email: !!novo.email, mail: !!novo.mail }, (novo[k] ? "Liguei: " : "Desliguei: ") + tit);
  };
  var scriptsCarregados = {};
  function carregarScript(src) {
    if (!scriptsCarregados[src]) {
      scriptsCarregados[src] = new Promise(function (ok, falhou) {
        var s = document.createElement("script");
        s.src = src; s.onload = ok;
        s.onerror = function () { delete scriptsCarregados[src]; falhou(new Error("não consegui carregar " + src)); };
        document.head.appendChild(s);
      });
    }
    return scriptsCarregados[src];
  }
  A.nfCert = async function () {
    var N = U.nfse; if (!N.pfx || N.instalando) return;
    N.instalando = true; N.aviso = null; render();
    try {
      await carregarScript("../assets/vendor/forge.min.js");
      await carregarScript("../assets/nfse-pfx.js");
      var par = window.PavlvsPfx.ler(N.pfx.bytes, N.senha);
      var r = await api("POST", NF + "certificado", par);
      N.pfx = null; N.senha = "";
      var cx = r.conexao || {};
      N.aviso = { ok: !!cx.ok, frase: (cx.ok ? "Certificado de " + (r.certificado.titular || "—") + " instalado. " : "") + (cx.frase || "") + (cx.aviso ? " " + cx.aviso : "") };
      toast("Certificado instalado");
    } catch (e) {
      if (e.status !== 401) N.aviso = { ok: false, frase: e.message };
    }
    N.instalando = false;
    var i = $("nf-pfx"); if (i) i.value = "";
    ler("nfse"); render();
  };
  A.nfTestar = async function () {
    var N = U.nfse; if (N.testando) return;
    N.testando = true; render();
    try { N.teste = await api("POST", NF + "testar", {}); } catch (e) { if (e.status !== 401) toast(e.message, true); }
    N.testando = false; ler("nfse"); render();
  };
  A.nfImprimir = function (el) {
    var antigo = $("nf-impressao"); if (antigo) antigo.remove();
    var q = document.createElement("iframe");
    q.id = "nf-impressao"; q.title = "Impressão da NFS-e";
    q.style.cssText = "position:fixed;right:0;bottom:0;width:0;height:0;border:0";
    q.src = NF + "notas/" + encodeURIComponent(el.dataset.id) + "/pdf";
    q.onload = function () { try { q.contentWindow.focus(); q.contentWindow.print(); } catch (e) { window.open(q.src, "_blank"); } };
    document.body.appendChild(q);
  };
  A.nfEnviar = async function (el) {
    el.disabled = true;
    var r = await naHora("POST", NF + "notas/" + encodeURIComponent(el.dataset.id) + "/enviar", {});
    if (r) { toast("Enviada: a nota está no Paulus do cliente" + (r.email ? " · e-mail: " + r.email : "")); ler("nfse"); } else el.disabled = false;
  };
  A.nfTentar = async function (el) {
    el.disabled = true;
    var r = await naHora("POST", NF + "notas/" + encodeURIComponent(el.dataset.id) + "/tentar", {});
    if (r) { toast(r.estado === "emitida" ? "NFS-e nº " + r.numero + " emitida" : "A nota continua: " + (r.estado_rotulo || r.estado), r.estado !== "emitida"); if (r.estado === "emitida") nfDepois(r.id); ler("nfse"); } else el.disabled = false;
  };
  A.nfDescartar = async function (el) {
    el.disabled = true;
    var r = await naHora("POST", NF + "notas/" + encodeURIComponent(el.dataset.id) + "/descartar", {}, "Nota descartada; o número volta para a próxima");
    if (r) ler("nfse"); else el.disabled = false;
  };
  // O PDF (e o e-mail) num pedido separado, logo depois de emitir.
  function nfDepois(id) { api("POST", NF + "notas/" + encodeURIComponent(id) + "/depois", {}).catch(function () { /* o Cron faz depois */ }); }

  // pop-up Emitir
  function nfAbrirEmitir(pagamento) {
    var v = { conta: "", pagamento: "", valor: "", competencia: nfMesAtual(), descricao: "" };
    NF_TOMADOR.forEach(function (x) { v["tomador." + x[0]] = ""; });
    abrirModal({ tipo: "nfEmitir", v: v, clientes: null, erro: "", enviando: false });
    var M = E.modal;
    api("GET", NF + "clientes").then(function (r) {
      if (E.modal !== M) return;
      M.clientes = r.clientes || [];
      if (pagamento) nfEscolherPagamento(M, pagamento);
      renderCamada();
    }, function (e) {
      if (E.modal !== M || e.status === 401) return;
      M.erroClientes = e.message; M.clientes = [];
      if (pagamento) nfEscolherPagamento(M, pagamento);
      renderCamada();
    });
    if (pagamento) nfEscolherPagamento(M, pagamento);
  }
  function nfEscolherCliente(M, id) {
    M.v.conta = id; M.mun = {};
    var c = (M.clientes || []).filter(function (x) { return String(x.id) === String(id); })[0];
    NF_TOMADOR.forEach(function (x) { M.v["tomador." + x[0]] = c ? (c.tomador || {})[x[0]] || "" : ""; });
  }
  function nfEscolherPagamento(M, id) {
    M.v.pagamento = id;
    var p = (((dadosDe("nfse") || {}).pagamentos) || []).filter(function (x) { return String(x.id) === String(id); })[0];
    if (!p) return;
    nfEscolherCliente(M, p.conta || "");
    M.v.valor = Number(p.valor || 0).toLocaleString("pt-BR", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
    // O mesmo texto do emissor (worker/nfse/emissor.js, descricaoDoPagamento).
    M.v.descricao = { mensalidade: "Assinatura do Paulus — plano mensal", anual: "Assinatura do Paulus — plano anual",
      "mês avulso": "Assinatura do Paulus — um mês, sem renovação" }[p.tipo] || "Recarga de uso do Paulus (nuvem)";
    if (String(p.quando || "").length >= 7) M.v.competencia = String(p.quando).slice(0, 7);
  }
  function nfIdsSel() { var S = U.nfse.sel || {}; return Object.keys(S).filter(function (k) { return S[k]; }); }
  A.nfSelSair = function () { U.nfse.sel = null; render(); };
  A.nfSelTodas = function () { U.nfse.sel = {}; ((dadosDe("nfse") || {}).notas || []).forEach(function (n) { U.nfse.sel[n.id] = true; }); render(); };
  function nfBaixar(href) { var a = document.createElement("a"); a.href = href; a.download = ""; document.body.appendChild(a); a.click(); a.remove(); }
  A.nfMassaPdf = function () { nfIdsSel().forEach(function (id, k) { setTimeout(function () { nfBaixar(NF + "notas/" + id + "/pdf?baixar=1"); }, k * 300); }); };
  A.nfMassaXml = function () { nfIdsSel().forEach(function (id, k) { setTimeout(function () { nfBaixar(NF + "notas/" + id + "/xml"); }, k * 300); }); };
  A.nfMassaImprimir = function () {
    var ids = nfIdsSel(); if (ids.length === 1) return A.nfImprimir({ dataset: { id: ids[0] } });
    ids.forEach(function (id) { window.open(NF + "notas/" + id + "/pdf", "_blank"); });
  };
  A.nfMassaEnviar = async function () {
    var ids = nfIdsSel(); if (!ids.length) return; U.nfse.sel = null; render();
    var ok = 0; for (var i = 0; i < ids.length; i++) { try { await api("POST", NF + "notas/" + encodeURIComponent(ids[i]) + "/enviar", {}); ok++; } catch (e) { /* segue */ } }
    toast(ok === ids.length ? (ok === 1 ? "Nota enviada ao cliente" : ok + " notas enviadas aos clientes") : ok + " de " + ids.length + " enviadas", ok !== ids.length); ler("nfse");
  };
  A.nfMassaSubstituir = function () { var ids = nfIdsSel(); if (ids.length !== 1) return; U.nfse.sel = null; A.nfSubstituir({ dataset: { id: ids[0] } }); };
  A.nfMassaCancelar = function () { var ids = nfIdsSel(); if (ids.length !== 1) return; U.nfse.sel = null; A.nfCancelar({ dataset: { id: ids[0] } }); };
  (function () {
    var t = null, segurou = false;
    document.addEventListener("pointerdown", function (ev) {
      var l = ev.target.closest("[data-nsel]"); if (!l || ev.target.closest("button, a") || U.nfse.sel) return;
      segurou = false;
      t = setTimeout(function () { segurou = true; U.nfse.menu = null; U.nfse.sel = {}; U.nfse.sel[l.dataset.nsel] = true; render(); }, 450);
    });
    var parar = function () { clearTimeout(t); t = null; if (segurou) setTimeout(function () { segurou = false; }, 0); };
    ["pointerup", "pointercancel", "pointerleave"].forEach(function (n) { document.addEventListener(n, parar); });
    document.addEventListener("click", function (ev) {
      var l = ev.target.closest("[data-nsel]"); if (!l || !U.nfse.sel || segurou || ev.target.closest("button, a")) return;
      var id = l.dataset.nsel; U.nfse.sel[id] = !U.nfse.sel[id];
      if (!nfIdsSel().length) U.nfse.sel = null;
      render();
    });
  })();
  A.nfCliPick = function (el) {
    var M = E.modal; if (!M) return; var id = el.dataset.id;
    if (id) nfEscolherCliente(M, id); else { M.v.conta = ""; }
    M.cliQ = null; M.cliAberto = !id && el.closest(".nf-cli-lista") ? false : false; renderCamada();
    if (!id) { var i = $("nf-cli-q"); if (i) i.focus(); }
  };
  A.nfPagPick = function (el) {
    var M = E.modal; if (!M) return; var id = el.dataset.id;
    if (id) nfEscolherPagamento(M, id); else M.v.pagamento = "";
    M.pagQ = null; M.pagAberto = false; renderCamada();
  };
  document.addEventListener("focusin", function (ev) { if (ev.target.id === "nf-pag-q" && E.modal && !E.modal.pagAberto) { E.modal.pagAberto = true; var p = ev.target.selectionStart; renderCamada(); var i = $("nf-pag-q"); if (i) { i.focus(); try { i.setSelectionRange(p, p); } catch (e) {} } } });
  document.addEventListener("mousedown", function (ev) { if (E.modal && E.modal.pagAberto && !ev.target.closest(".nf-pag")) { E.modal.pagAberto = false; E.modal.pagQ = null; fecharLista(".nf-pag .nf-cli-lista"); } });
  document.addEventListener("focusin", function (ev) { if (ev.target.id === "nf-cli-q" && E.modal && !E.modal.cliAberto) { E.modal.cliAberto = true; var p = ev.target.selectionStart; renderCamada(); var i = $("nf-cli-q"); if (i) { i.focus(); try { i.setSelectionRange(p, p); } catch (e) {} } } });
  document.addEventListener("mousedown", function (ev) { if (E.modal && E.modal.cliAberto && !ev.target.closest(".nf-cli:not(.nf-pag)")) { E.modal.cliAberto = false; E.modal.cliQ = null; fecharLista(".nf-cli:not(.nf-pag):not(.esc-busca) .nf-cli-lista"); } });
  A.nfCompAbrir = function () { var M = E.modal; if (!M) return; M.compAberto = !M.compAberto; M.compAno = null; renderCamada(); };
  A.nfCompAno = function (el) { var M = E.modal; if (!M) return; var y = Number(String(M.v.competencia || "").slice(0, 4)) || new Date().getFullYear(); M.compAno = (M.compAno || y) + Number(el.dataset.d); renderCamada(); };
  A.nfCompMes = function (el) { var M = E.modal; if (!M) return; var y = M.compAno || Number(String(M.v.competencia || "").slice(0, 4)) || new Date().getFullYear(); M.v.competencia = y + "-" + pad(Number(el.dataset.m) + 1); M.compAberto = false; M.compAno = null; renderCamada(); };
  A.nfCompEste = function () { var M = E.modal; if (!M) return; M.v.competencia = nfMesAtual(); M.compAberto = false; M.compAno = null; renderCamada(); };
  A.nfCompLimpar = function () { var M = E.modal; if (!M) return; M.v.competencia = ""; M.compAberto = false; renderCamada(); };
  document.addEventListener("mousedown", function (ev) { if (E.modal && E.modal.compAberto && !ev.target.closest(".nf-comp")) { E.modal.compAberto = false; fecharLista(".nf-comp-cal"); } });
  A.nfComboAbrir = function (el) { var M = E.modal; if (!M) return; M.selAberto = M.selAberto === el.dataset.k ? null : el.dataset.k; renderCamada(); };
  A.nfComboEscolher = function (el) {
    var M = E.modal; if (!M) return; var k = el.dataset.k, f = IN[el.dataset.in2] || IN.nf;
    M.selAberto = null;
    f({ dataset: { k: k, in: el.dataset.in2 }, value: el.dataset.v, type: "select-one", tagName: "SELECT" });
    renderCamada(); var b = $(nfId(k)); if (b) b.focus();
  };
  document.addEventListener("mousedown", function (ev) { if (E.modal && E.modal.selAberto && !ev.target.closest(".nf-combo")) { E.modal.selAberto = null; fecharLista(".nf-combo-lista"); } });
  document.addEventListener("keydown", function (ev) { if (ev.key === "Escape" && E.modal && E.modal.selAberto) { E.modal.selAberto = null; renderCamada(); } });
  A.nfMenu = function (el) {
    var id = el.dataset.id; U.nfse.menu = String(U.nfse.menu) === id ? null : id; render();
    var m = document.querySelector(".nf-menu"), b = document.querySelector('[data-a="nfMenu"][data-id="' + id + '"]'); if (!m || !b) return;
    var r = b.getBoundingClientRect(), h = m.offsetHeight, w = m.offsetWidth;
    m.style.left = Math.max(8, r.right - w) + "px";
    m.style.top = (r.bottom + 4 + h > innerHeight - 8 ? Math.max(8, r.top - 4 - h) : r.bottom + 4) + "px";
  };
  addEventListener("scroll", function () { if (U.nfse.menu != null) { U.nfse.menu = null; render(); } }, true);
  document.addEventListener("click", function (ev) {
    if (U.nfse.menu == null || ev.target.closest('[data-a="nfMenu"]')) return;
    var dentro = ev.target.closest(".nf-menu");
    U.nfse.menu = null;
    if (!dentro) render(); else setTimeout(render, 0);
  }, true);
  document.addEventListener("keydown", function (ev) { if (ev.key === "Escape" && U.nfse.menu != null) { U.nfse.menu = null; render(); } });
  A.nfEmitir = function () { nfAbrirEmitir(""); };
  A.nfEmitirPag = function (el) { nfAbrirEmitir(el.dataset.id); };
  A.nfEmitirConfirmar = async function () {
    var M = E.modal; if (!M || M.enviando) return;
    var v = M.v, corpo = { tomador: nfAninhar(v, "tomador."), descricao: v.descricao, competencia: v.competencia };
    if (v.conta) corpo.conta = v.conta;
    if (v.pagamento) corpo.pagamento = v.pagamento;
    if (String(v.valor || "").trim()) corpo.valor = String(v.valor).trim();
    else if (!v.pagamento) { M.erro = "diga o valor da nota"; renderCamada(); return; }
    M.enviando = true; M.erro = ""; renderCamada();
    try {
      var n = await api("POST", NF + "notas", corpo);
      if (E.modal === M) fecharModal();
      if (n.estado === "emitida") { toast("NFS-e nº " + n.numero + " emitida"); nfDepois(n.id); }
      else toast("A nota ficou “" + (n.estado_rotulo || n.estado) + "”" + (n.erro ? ": " + n.erro : ""), true);
      ler("nfse");
    } catch (e) {
      if (E.modal !== M) return;
      M.enviando = false;
      var lista = e.dados && e.dados.erros && e.dados.erros.length ? e.dados.erros : null;
      M.erro = e.status === 401 ? "" : lista ? "A nota não passou na conferência: " + lista.join("; ") : e.message;
      renderCamada();
    }
  };

  // pop-up Clientes
  A.nfClientes = function () {
    abrirModal({ tipo: "nfClientes", clientes: null, editando: null, v: {}, erro: "", ok: "" });
    var M = E.modal;
    api("GET", NF + "clientes").then(function (r) { if (E.modal === M) { M.clientes = r.clientes || []; renderCamada(); } },
      function (e) { if (E.modal === M && e.status !== 401) { M.erroClientes = e.message; renderCamada(); } });
  };
  A.nfMunEscolher = function (el) {
    var M = E.modal, k = el.dataset.mun, st = M && M.mun && M.mun[k];
    if (!st || !st.res) return;
    var m = st.res[Number(el.dataset.i)], i = $(nfId(k));
    if (m) nfMunFixar(M, k, m, i ? i.dataset.uf : "");
  };
  A.nfCliEditar = function (el) {
    var M = E.modal, id = el.dataset.id;
    if (String(M.editando) === String(id)) { M.editando = null; renderCamada(); return; }
    var c = (M.clientes || []).filter(function (x) { return String(x.id) === String(id); })[0]; if (!c) return;
    M.editando = id; M.erro = ""; M.ok = ""; M.v = {}; M.mun = {};
    NF_TOMADOR.forEach(function (x) { M.v["tomador." + x[0]] = (c.tomador || {})[x[0]] || ""; });
    renderCamada();
    var i = $(nfId("tomador.nome")); if (i) i.focus();
  };
  A.nfCliSalvar = async function (el) {
    var M = E.modal, id = el.dataset.id; if (!M || M.enviando) return;
    M.enviando = true; M.erro = ""; renderCamada();
    try {
      var c = await api("POST", NF + "clientes/" + encodeURIComponent(id), { tomador: nfAninhar(M.v, "tomador.") });
      M.clientes = (M.clientes || []).map(function (x) { return String(x.id) === String(id) ? c : x; });
      M.editando = null; M.ok = "Dados fiscais de " + c.nome + " salvos" + (c.faltas && c.faltas.length ? "; ainda falta " + c.faltas.join(", ") : "") + ".";
    } catch (e) { if (e.status !== 401) M.erro = e.message; }
    M.enviando = false; renderCamada();
  };

  // pop-up Parâmetros
  A.nfParametros = function () {
    var s = (dadosDe("nfse") || {}).situacao; if (!s) return;
    var p = JSON.parse(JSON.stringify((s.prestador || {}).dados || {}));
    var v = nfAchatar(p, "");
    Object.keys(v).forEach(function (k) {
      if (/_bp$/.test(k) && !/minimo/.test(k)) { v[k.replace(/_bp$/, "_pct")] = nfPct(v[k]); delete v[k]; }
    });
    v["ibscbs.enviar"] = !!(p.ibscbs || {}).enviar;
    abrirModal({ tipo: "nfParametros", v: v, erro: "", token: "", tokenMsg: "", prodConfirma: false });
  };
  A.nfParamSalvar = async function () {
    var M = E.modal; if (!M || M.enviando) return;
    var v = {};
    Object.keys(M.v).forEach(function (k) {
      if (/^(ambiente|revisado_por|revisado_em|uf)$/.test(k)) return;
      if (/_pct$/.test(k)) v[k.replace(/_pct$/, "_bp")] = nfBp(M.v[k]);
      else v[k] = M.v[k];
    });
    M.enviando = true; M.erro = ""; renderCamada();
    try {
      var r = await api("POST", NF + "prestador", { prestador: nfAninhar(v, "") });
      if (E.modal === M) fecharModal();
      toast(r.mudou ? "Parâmetros gravados (versão " + r.versao + ")" + (r.faltas && r.faltas.length ? "; ainda falta " + r.faltas.join(", ") : "") : "Nada mudou nos parâmetros", !!(r.faltas && r.faltas.length));
      ler("nfse");
    } catch (e) {
      if (E.modal !== M) return;
      M.enviando = false; M.erro = e.status === 401 ? "" : e.message; renderCamada();
    }
  };
  A.nfToken = async function () {
    var M = E.modal; if (!M || M.gravandoToken) return;
    if (!String(M.token || "").trim()) { M.tokenMsg = "Cole o token antes de gravar."; M.tokenOk = false; renderCamada(); return; }
    M.gravandoToken = true; M.tokenMsg = ""; renderCamada();
    try {
      var r = await api("POST", NF + "cloudflare", { token: M.token.trim() });
      M.token = ""; M.tokenOk = !r.conexao || !!r.conexao.ok;
      M.tokenMsg = "Token gravado (cifrado)." + (r.conexao ? " " + r.conexao.frase : "");
      var d = dadosDe("nfse"); if (d) d.cloudflare = r.cloudflare;
      if (r.conexao && r.conexao.ok) U.nfse.aviso = null;
      ler("nfse");
    } catch (e) { if (e.status !== 401) { M.tokenMsg = e.message; M.tokenOk = false; } }
    M.gravandoToken = false; renderCamada();
  };
  A.nfProducao = async function (el) {
    var M = E.modal, acao = el.dataset.v; if (!M) return;
    if (acao === "liberar" && !M.prodConfirma) { M.prodConfirma = true; renderCamada(); return; }
    M.erroProd = ""; el.disabled = true;
    try {
      var r = await api("POST", NF + "producao/" + acao, {});
      if (E.modal === M) fecharModal();
      toast(r.producao_liberada ? "Em produção: as notas valem de verdade" : "De volta ao ambiente de testes");
      ler("nfse");
    } catch (e) { if (e.status !== 401 && E.modal === M) { M.erroProd = e.message; M.prodConfirma = false; renderCamada(); } }
  };

  // cancelar e substituir
  A.nfCancelar = function (el) { abrirModal({ tipo: "nfCancelar", id: el.dataset.id, v: { motivo: "1", texto: "" }, erro: "", enviando: false }); };
  A.nfCancelarConfirmar = async function () {
    var M = E.modal; if (!M || M.enviando) return;
    M.enviando = true; M.erro = ""; renderCamada();
    try {
      var r = await api("POST", NF + "notas/" + encodeURIComponent(M.id) + "/cancelar", { motivo: M.v.motivo, texto: M.v.texto });
      if (E.modal === M) fecharModal();
      var ev = r.evento || {};
      if (r.nota && r.nota.estado === "cancelada") toast("NFS-e nº " + r.nota.numero + " cancelada");
      else toast("O cancelamento ficou “" + (ev.estado || "pendente") + "”" + (ev.ultimo_erro ? ": " + ev.ultimo_erro : ""), true);
      ler("nfse");
    } catch (e) { if (E.modal === M) { M.enviando = false; M.erro = e.status === 401 ? "" : e.message; renderCamada(); } }
  };
  A.nfSubstituir = function (el) {
    var n = nfNota(el.dataset.id); if (!n) return;
    var v = { motivo: "99", texto: "", "ajustes.valor": nfReais(n.centavos), "ajustes.competencia": String(n.competencia || "").slice(0, 7), "ajustes.descricao": n.descricao || "" };
    NF_TOMADOR.forEach(function (x) { v["ajustes.tomador." + x[0]] = (n.tomador || {})[x[0]] || ""; });
    abrirModal({ tipo: "nfSubstituir", id: n.id, v: v, erro: "", enviando: false });
  };
  A.nfSubstituirConfirmar = async function () {
    var M = E.modal; if (!M || M.enviando) return;
    var corpo = nfAninhar(M.v, "");
    M.enviando = true; M.erro = ""; renderCamada();
    try {
      var r = await api("POST", NF + "notas/" + encodeURIComponent(M.id) + "/substituir", corpo);
      if (E.modal === M) fecharModal();
      var n = r.nota || {};
      if (n.estado === "emitida") { toast("NFS-e nº " + n.numero + " emitida no lugar da nº " + ((r.original || {}).numero || "")); nfDepois(n.id); }
      else toast("A substituta ficou “" + (n.estado_rotulo || n.estado) + "”" + (n.erro ? ": " + n.erro : ""), true);
      ler("nfse");
    } catch (e) {
      if (E.modal !== M) return;
      var lista = e.dados && e.dados.erros && e.dados.erros.length ? e.dados.erros : null;
      M.enviando = false; M.erro = e.status === 401 ? "" : lista ? "A nota não passou na conferência: " + lista.join("; ") : e.message; renderCamada();
    }
  };

  // equipe
  function mudarPapel(email, papel) {
    var m = (((dadosDe("equipe") || {}).membros) || []).filter(function (x) { return x.email === email; })[0]; if (!m) return;
    var p = ultimaNaFila("equipe.papel", email), atual = p && p.dados ? p.dados.papel : m.papel;
    if (atual === papel) return;
    enfileirar("equipe", "equipe.papel", email, { email: email, papel: papel }, "Mudei " + (m.nome || email) + " para " + PAPEL_NOME[papel]);
  }

  // alteracoes
  A.tirarDaFila = async function (el) {
    el.disabled = true;
    try { var r = await api("DELETE", "/api/admin/alteracoes/" + encodeURIComponent(el.dataset.id)); E.pendentes = r.pendentes || []; if (D.alteracoes && D.alteracoes.dados) D.alteracoes.dados.pendentes = E.pendentes; toast("Tirei da fila"); render(); }
    catch (e) { el.disabled = false; if (e.status !== 401) toast(e.message, true); }
  };
  A.modalCommit = function () { if (!E.pendentes.length) { toast("Nada para publicar"); return; } abrirModal({ tipo: "commit", texto: "", enviando: false, erro: "" }); };
  A.modalRetroagir = function (el) {
    var p = ((dadosDe("alteracoes") || {}).publicacoes || [])[Number(el.dataset.i)]; if (!p) return;
    abrirModal({ tipo: "retroagir", pub: p, texto: "", enviando: false, erro: "" });
    setTimeout(function () { var i = $("modal-retro"); if (i) i.focus(); }, 30);
  };
  A.retroagir = async function () {
    var M = E.modal; if (!M || M.texto.trim() !== "retroagir" || M.enviando) return;
    M.enviando = true; M.erro = ""; renderCamada();
    try {
      var r = await api("POST", "/api/admin/retroagir", { commit: M.pub.commit, confirmacao: "retroagir" });
      if (E.modal !== M) return;
      toast("Retroagido · " + (r.commit ? String(r.commit).slice(0, 7) : "commit de reversão"), false);
      fecharModal(); ler("alteracoes");
    } catch (e) { if (E.modal !== M) return; M.enviando = false; M.erro = e.status === 401 ? "" : e.message; renderCamada(); }
  };
  A.publicar = async function () {
    var M = E.modal; if (M.texto.trim() !== "comitar e pushar" || M.enviando) return;
    M.enviando = true; M.erro = ""; M.itens = E.pendentes.slice(); renderCamada();
    try {
      var r = await api("POST", "/api/admin/publicar", { confirmacao: "comitar e pushar" });
      if (E.modal !== M) return;
      M.enviando = false;
      var falhas = (r.resultados || []).filter(function (x) { return !x.ok; });
      toast("Publicado · " + (r.publicacao && r.publicacao.commit ? String(r.publicacao.commit).slice(0, 7) : "sem commit"), false);
      if (falhas.length) { M.resultado = r; renderCamada(); var b = $("modal-ok"); if (b) b.focus(); }
      else fecharModal();
      ler("alteracoes");
    } catch (e) {
      if (E.modal !== M) return;
      M.enviando = false; M.erro = e.status === 401 ? "" : e.message; renderCamada();
    }
  };

  // camada
  A.fecharModal = function () { fecharModal(); };
  A.fecharBusca = function () { fecharBusca(); };
  A.buscaIr = function (el) { var r = itensBusca[Number(el.dataset.i)]; if (r) { E.busca.aberta = false; renderCamada(); r.ir(); } };
  var ABA_DO_MODAL = { contaExtrato: "extrato", contaCadastro: "cadastro", contaPlano: "plano", google: "google" };
  var NF_ABA = { nfEmitir: "emitir", nfClientes: "clientes", nfParametros: "parametros" };
  function abrirModal(m) {
    if (E.tela === "nfse" && !E.gaveta && NF_ABA[m.tipo]) { m.embutido = true; U.nfse.aba = NF_ABA[m.tipo]; E.modal = m; render(); return; }
    // Na pagina da conta, esses pop-ups abrem como aba, dentro da pagina.
    if (E.gaveta && E.gaveta.pagina && ABA_DO_MODAL[m.tipo]) { m.embutido = true; E.gaveta.aba = ABA_DO_MODAL[m.tipo]; E.modal = m; render(); return; }
    if (!E.modal) focoAntes = document.activeElement;
    E.modal = m; renderCamada();
    var alvo = document.querySelector(".modal input") || $("modal-ok") || document.querySelector(".modal button");
    if (alvo) alvo.focus();
  }
  function fecharModal() {
    if (E.modal && E.modal.embutido) { E.modal = null; if (E.gaveta) E.gaveta.aba = "resumo"; if (E.tela === "nfse") U.nfse.aba = "notas"; render(); return; }
    E.modal = null; renderCamada(); devolverFoco();
  }

  /* ---------- entradas de texto ---------- */
  var IN = {
    contasQ: function (el) { U.contas.q = el.value; render(); },
    campo: function (el) {
      var p = el.dataset.campo.split("."), alvo = p[0] === "camp" ? U.emails.camp : U.planos.novo;
      alvo[p[1]] = el.value; render();
    },
    recado: function (el) { U.materiais.recados[U.materiais.aberto] = el.value; },
    slugNovo: function (el) { E.modal.novo = el.value; conferirSlug(); renderCamada(); },
    planoValor: function (el) { E.modal.valor = el.value; renderCamada(); },
    calHora: function (el) {
      var x = calCtx(); if (!x) return; var k = el.dataset.k, v = Number(el.value); x.C[k] = v;
      el.style.setProperty("--andado", (v / Number(el.max) * 100) + "%");
      var b = el.closest(".relogio-adm").querySelector(k === "h" ? "[data-rel-h]" : "[data-rel-m]"); if (b) b.textContent = pad(v);
    },
    membroCampo: function (el) {
      E.modal.v[el.dataset.k] = el.value;
      var ok = /^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(E.modal.v.email || "") && (E.modal.v.nome || "").trim(), b = document.querySelector('[data-a="membroSalvar"]'); if (b) b.disabled = !ok;
    },
    retroTexto: function (el) { E.modal.texto = el.value; var b = $("modal-ok"); if (b) { var ok = el.value.trim() === "retroagir"; b.disabled = !ok || E.modal.enviando; b.classList.toggle("perigo-cheio", ok); } },
    escmQ: function (el) { E.modal.q = el.value; var pos = el.selectionStart; renderCamada(); var i = $("escm-q"); if (i) { i.focus(); try { i.setSelectionRange(pos, pos); } catch (e) {} } },
    escQ: function (el) { U.emails.escQ = el.value; U.emails.escAberto = true; var pos = el.selectionStart; render(); var i = $("esc-q"); if (i) { i.focus(); try { i.setSelectionRange(pos, pos); } catch (e) {} } },
    cadCampo: function (el) { E.modal.v[el.dataset.k] = el.value; },
    planoEdEscolher: function (el) { U.planos.aba = el.value; U.planos.ed = null; render(); },
    planoEd: function (el) { var e = U.planos.ed; if (e) e.v[el.dataset.k] = el.value; },
    planoEdItem: function (el) { var e = U.planos.ed; if (e && e.itens[el.dataset.i]) e.itens[el.dataset.i][el.dataset.k] = el.value; },
    planosJson: function (el) { U.planos.json = el.value; planosStatus(); },
    planosArquivo: function (el) {
      var f = el.files && el.files[0]; if (!f) return;
      f.text().then(function (t) { try { t = JSON.stringify(JSON.parse(t), null, 2); } catch (e) { /* mostra como veio; o aviso diz o erro */ } U.planos.json = t; render(); toast("Arquivo carregado: confira e salve"); });
    },
    renovMsg: function (el) { U.renovacoes.msg[el.dataset.id] = el.value; var b = document.querySelector('[data-a="renovMsgEnviar"][data-id="' + el.dataset.id + '"]'); if (b) b.disabled = !el.value.trim(); },
    renovOf: function (el) { var o = U.renovacoes.oferta[el.dataset.id]; if (!o) return; o[el.dataset.k] = el.value; if (el.tagName !== "SELECT") { var pos = el.selectionStart, k = el.dataset.k, id = el.dataset.id; render(); var n = document.querySelector('[data-in="renovOf"][data-id="' + id + '"][data-k="' + k + '"]'); if (n) { n.focus(); try { n.setSelectionRange(pos, pos); } catch (e) {} } } else render(); },
    regQ: function (el) { U.tuneis.regQ = el.value; var pos = el.selectionStart; render(); var i = $("reg-q"); if (i) { i.focus(); try { i.setSelectionRange(pos, pos); } catch (e) {} } },
    cadUf: function (el) { E.modal.v.uf = el.value; },
    // A cidade sugere os municipios do IBGE (a mesma busca da NFS-e), so os da UF escolhida.
    cadCidade: function (el) {
      var M = E.modal, t = el.value.trim(); M.v.cidade = el.value;
      clearTimeout(M.timerCidade);
      if (t.length < 2) return;
      M.timerCidade = setTimeout(function () {
        api("GET", NF + "municipios?q=" + encodeURIComponent(t)).then(function (r) {
          if (E.modal !== M) return;
          var dl = $("cad-cidades"); if (!dl) return;
          dl.innerHTML = (r.municipios || []).filter(function (x) { return !M.v.uf || x.uf === M.v.uf; }).map(function (x) { return '<option value="' + esc(x.nome) + '">' + esc(x.nome + "/" + x.uf) + "</option>"; }).join("");
          var achou = (r.municipios || []).filter(function (x) { return x.nome === el.value; })[0];
          if (achou && !M.v.uf) { M.v.uf = achou.uf; var s = $("cad-uf"); if (s) s.value = achou.uf; }
        }, function () {});
      }, 200);
    },
    planoTokens: function (el) { E.modal.tokens = el.value; renderCamada(); },
    planoAnual: function (el) { E.modal.anual = el.value; renderCamada(); },
    commitTexto: function (el) { E.modal.texto = el.value; E.modal.erro = ""; renderCamada(); },
    buscaQ: function (el) { E.busca.q = el.value; E.busca.idx = 0; buscar(); renderCamada(); },
    // notas fiscais: os campos dos pop-ups guardam o valor sem redesenhar
    nf: function (el) { if (E.modal && E.modal.v) { E.modal.v[el.dataset.k] = el.type === "checkbox" ? el.checked : el.value; nfCnpj(el); } },
    nfMun: function (el) { nfMunDigitar(el); },
    nfMunCod: function (el) {
      var M = E.modal; if (!M) return; var k = el.dataset.k, v = el.value.replace(/\D/g, "").slice(0, 7);
      M.munCod = M.munCod || {}; M.munCod[k] = v;
      if (v.length !== 7) return;
      M.v[k] = v; M.munCod[k] = null; if (M.mun) M.mun[k] = {};
      var mi = $(nfId(k)), kUf = mi ? mi.dataset.uf : "";
      if (kUf && NF_UF[v.slice(0, 2)]) M.v[kUf] = NF_UF[v.slice(0, 2)];
      // O nome do municipio sai do proprio codigo (nfMunRotulo busca e repinta); ate chegar, o campo mostra o codigo.
      var pos = el.selectionStart; renderCamada();
      var nm = $(nfId(k)); if (nm) nm.value = nfMunRotulo(v);
      var u = kUf ? $(nfId(kUf)) : null; if (u && M.v[kUf] != null) u.value = M.v[kUf];
      var i = $(el.id); if (i) { i.focus(); try { i.setSelectionRange(pos, pos); } catch (e) {} }
    },
    nfCliente: function (el) { nfEscolherCliente(E.modal, el.value); renderCamada(); },
    nfPagBusca: function (el) {
      var M = E.modal; if (!M) return; M.pagQ = el.value; M.pagAberto = true; var pos = el.selectionStart; renderCamada();
      var i = $("nf-pag-q"); if (i) { i.focus(); try { i.setSelectionRange(pos, pos); } catch (e) {} }
    },
    nfClisQ: function (el) { var M = E.modal; if (!M) return; M.q = el.value; var pos = el.selectionStart; renderCamada(); var i = $("nf-clis-q"); if (i) { i.focus(); try { i.setSelectionRange(pos, pos); } catch (e) {} } },
    nfCliBusca: function (el) {
      var M = E.modal; if (!M) return; M.cliQ = el.value; M.cliAberto = true; var pos = el.selectionStart; renderCamada();
      var i = $("nf-cli-q"); if (i) { i.focus(); try { i.setSelectionRange(pos, pos); } catch (e) {} }
    },
    nfPagamento: function (el) { if (el.value) nfEscolherPagamento(E.modal, el.value); else E.modal.v.pagamento = ""; renderCamada(); },
    nfSenha: function (el) { U.nfse.senha = el.value; },
    nfTokenCampo: function (el) { if (E.modal) E.modal.token = el.value; },
    nfPfx: function (el) {
      var f = el.files && el.files[0];
      if (!f) return;
      if (f.size > 64 * 1024) { toast("Esse arquivo é grande demais para um certificado A1 (.pfx)", true); el.value = ""; return; }
      f.arrayBuffer().then(function (b) { U.nfse.pfx = { nome: f.name, bytes: new Uint8Array(b) }; U.nfse.aviso = null; render(); });
    },
  };

  /* ================================================================ toast */

  var toastTimer = null;
  function toast(msg, erro, html) {
    var el = $("toast");
    el.className = "toast" + (erro ? " erro" : "");
    el.innerHTML = ic(erro ? "warning" : "check") + '<span class="tx">' + (html ? msg : esc(msg)) + "</span>";
    el.hidden = false;
    clearTimeout(toastTimer);
    toastTimer = setTimeout(function () { el.hidden = true; }, erro ? 5000 : 2600);
  }

  /* ================================================================ eventos */

  document.addEventListener("click", function (ev) {
    var el = ev.target.closest("[data-a]");
    if (!el || el.disabled || el.getAttribute("aria-disabled") === "true" && el.dataset.a !== "modalCommit") return;
    var f = A[el.dataset.a];
    if (!f) return;
    ev.preventDefault();
    f(el, ev);
  });
  document.addEventListener("input", function (ev) {
    var el = ev.target.closest("[data-in]");
    if (el && IN[el.dataset.in] && el.type !== "file") IN[el.dataset.in](el, ev);
  });
  // Arquivo escolhido dispara "change" (e o "input" nao chega em todo navegador): so os campos de arquivo passam por aqui.
  document.addEventListener("change", function (ev) {
    var el = ev.target.closest("[data-in]");
    if (el && el.type === "file" && IN[el.dataset.in]) IN[el.dataset.in](el, ev);
  });
  document.addEventListener("mouseover", function (ev) {
    var b = ev.target.closest(".busca-item");
    if (b && Number(b.dataset.i) !== E.busca.idx) marcarBusca(Number(b.dataset.i));
  });
  document.addEventListener("keydown", function (ev) {
    var k = ev.key;
    if ((ev.metaKey || ev.ctrlKey) && String(k).toLowerCase() === "k") {
      if (!E.dentro) return;
      ev.preventDefault();
      if (E.busca.aberta) fecharBusca(); else abrirBusca();
      return;
    }
    if (nfMunTecla(ev)) return;
    if (k === "Escape") {
      if (E.busca.aberta) { ev.preventDefault(); fecharBusca(); return; }
      if (E.modal) { ev.preventDefault(); fecharModal(); return; }
      if (E.gaveta) { ev.preventDefault(); A.fecharGaveta(); return; }
      if (U.google.confirmando) { U.google.confirmando = null; render(); }
      return;
    }
    if (ev.target && ev.target.id === "busca-q") {
      var total = itensBusca.length;
      if (k === "ArrowDown" || k === "ArrowUp") {
        ev.preventDefault(); if (!total) return;
        marcarBusca(((E.busca.idx + (k === "ArrowDown" ? 1 : -1)) % total + total) % total);
      } else if (k === "Enter") {
        ev.preventDefault();
        var r = itensBusca[E.busca.idx]; if (r) { E.busca.aberta = false; renderCamada(); r.ir(); }
      }
      return;
    }
    // linhas clicaveis (div role=button): Enter e espaco
    if ((k === "Enter" || k === " ") && ev.target.matches && ev.target.matches('[role="button"][data-a]')) { ev.preventDefault(); ev.target.click(); return; }
    // Enter no campo do modal confirma
    if (k === "Enter" && ev.target.closest && ev.target.closest(".modal") && ev.target.tagName === "INPUT") { var ok = $("modal-ok"); if (ok && !ok.disabled) { ev.preventDefault(); ok.click(); } return; }
    // foco preso dentro do modal, da gaveta e da busca
    if (k === "Tab") {
      var caixa = document.querySelector("#camada .busca") || document.querySelector("#camada .modal") || document.querySelector("#camada .ficha");
      if (!caixa) return;
      var fs = Array.prototype.filter.call(caixa.querySelectorAll('button:not([disabled]):not([tabindex="-1"]), input, textarea, [tabindex="0"], a[href]'), function (x) { return x.offsetParent !== null; });
      if (!fs.length) return;
      var pri = fs[0], ult = fs[fs.length - 1];
      if (!caixa.contains(document.activeElement)) { ev.preventDefault(); pri.focus(); }
      else if (ev.shiftKey && document.activeElement === pri) { ev.preventDefault(); ult.focus(); }
      else if (!ev.shiftKey && document.activeElement === ult) { ev.preventDefault(); pri.focus(); }
    }
  });
  window.addEventListener("hashchange", aoMudarHash);

  /* ================================================================ entrada e sessao */

  // A pasta dos assets, tirada do endereco deste script (serve em /admin e na previa).
  var ASSETS = (function () { var s = document.querySelector('script[src*="admin.js"]'); return s ? s.src.replace(/admin\.js.*$/, "") : "../assets/"; })();
  var GITHUB_SVG = '<svg width="15" height="15" viewBox="0 0 16 16" fill="currentColor" aria-hidden="true"><path d="M8 0C3.58 0 0 3.58 0 8c0 3.54 2.29 6.53 5.47 7.59.4.07.55-.17.55-.38 0-.19-.01-.82-.01-1.49-2.01.37-2.53-.49-2.69-.94-.09-.23-.48-.94-.82-1.13-.28-.15-.68-.52-.01-.53.63-.01 1.08.58 1.23.82.72 1.21 1.87.87 2.33.66.07-.52.28-.87.51-1.07-1.78-.2-3.64-.89-3.64-3.95 0-.87.31-1.59.82-2.15-.08-.2-.36-1.02.08-2.12 0 0 .67-.21 2.2.82.64-.18 1.32-.27 2-.27.68 0 1.36.09 2 .27 1.53-1.04 2.2-.82 2.2-.82.44 1.1.16 1.92.08 2.12.51.56.82 1.27.82 2.15 0 3.07-1.87 3.75-3.65 3.95.29.25.54.73.54 1.48 0 1.07-.01 1.93-.01 2.2 0 .21.15.46.55.38A8.01 8.01 0 0 0 16 8c0-4.42-3.58-8-8-8z"/></svg>';

  function renderEntrada(erroLeitura) {
    var s = E.sessao || {}, acc = !!(s.access && s.access.ok), gh = !!(s.github && s.github.ok);
    var nome = primeiro(s.nome), sd = saudacaoHora();
    var saud = gh && acc ? sd + (nome ? ", " + nome : "") + ". Tudo pronto." : acc ? sd + (nome ? ", " + nome : "") + ". Falta o GitHub." : sd + ". Bem‑vindo de volta.";
    var cA = cfg("access"), cG = cfg("github");
    var h = '<div class="entrada-marca"><h1 class="saudacao">' + esc(saud) + '</h1><p class="sub">Administração do Paulus. Duas portas, nenhuma senha.</p></div><div class="campos" style="gap:18px">';
    if (erroLeitura) h += '<p class="erro-campo">Não foi possível conferir a sessão: ' + esc(erroLeitura) + "</p>";
    if (E.erroVolta) h += '<p class="erro-campo" role="alert">' + esc(E.erroVolta) + "</p>";
    // passo 1
    h += '<div class="passo">' +
      '<div class="selo"><span class="selo-esq">' + (acc ? '<span class="selo-icone">' + ic("check") + "</span>" : '<img class="selo-marca" src="' + ASSETS + 'cloudflare.svg" alt="" width="22" height="22">') + "<span>" + esc(acc ? s.access.email : "Cloudflare Access") + '</span></span><span class="selo-dir"><b>ZERO TRUST</b><span>só o e-mail da equipe</span></span></div>';
    if (!acc) h += '<button type="button" class="btn-duplo largo" data-a="recarregar"' + attrDis(desligado(cA), cA.falta) + "><span>" + ic("shield") + "Entrar pelo Cloudflare Access</span></button>" + (desligado(cA) ? '<p class="erro-campo">' + esc(cA.falta) + "</p>" : "");
    h += '<span class="nota-campo">O Access confere o seu e-mail com um código de uso único antes de a página carregar. Só quem está na lista da equipe chega aqui.</span></div>';
    // passo 2
    h += '<div class="passo' + (acc ? "" : " depois") + '">' +
      '<div class="selo"><span class="selo-esq">' + (gh ? '<span class="selo-icone">' + ic("check") + "</span>" : '<span class="selo-marca selo-github" aria-hidden="true">' + GITHUB_SVG.replace('width="15" height="15"', 'width="22" height="22"') + "</span>") + "<span>" + esc(gh ? s.github.login : "GitHub") + '</span></span><span class="selo-dir"><b>COLABORADOR</b><span>repositório coryphaeus</span></span></div>';
    if (acc && !gh) h += '<button type="button" class="btn-duplo largo" data-a="github"' + attrDis(desligado(cG), cG.falta) + "><span>" + GITHUB_SVG + "Entrar com o GitHub</span></button>" + (desligado(cG) ? '<p class="erro-campo">' + esc(cG.falta) + "</p>" : "");
    h += "</div>";
    if (acc && gh) {
      if (s.pronto) h += '<button type="button" class="btn-duplo largo" data-a="entrarPainel" id="entrar-painel"><span>Entrar no painel' + ic("arrow_forward", "s18") + "</span></button>";
      else h += '<p class="erro-campo">' + (s.papel ? "A sessão ainda não está pronta. Recarregue a página." : "O e-mail " + esc(s.access.email) + " não está na equipe do painel.") + "</p>";
    }
    h += "</div>";
    pintar($("entrada-col"), h);
  }

  function mostrarEntrada(erroLeitura) {
    E.dentro = false;
    $("casca").hidden = true; $("entrada").hidden = false;
    $("camada").innerHTML = ""; document.body.style.overflow = "";
    document.title = "Administração — PAVLVS";
    renderEntrada(erroLeitura);
    var b = $("entrar-painel"); if (b) b.focus();
  }

  function mostrarCasca() {
    var s = E.sessao;
    E.dentro = true;
    $("entrada").hidden = true; $("casca").hidden = false;
    var id = location.hash.replace(/^#/, "");
    E.tela = TELA[id] ? id : "visao";
    if (!TELA[id]) history.replaceState(null, "", "#visao");
    // As contagens da navegacao e das acoes rapidas: le em segundo plano.
    ["alteracoes", "tuneis", "renovacoes", "nfse"].forEach(function (ch) { ler(ch); });
    carregarTela();
    render();
  }

  async function iniciar() {
    // ?erro= na volta do GitHub
    var u = new URL(location.href), e = u.searchParams.get("erro");
    if (e) { E.erroVolta = e; u.searchParams.delete("erro"); history.replaceState(null, "", u.pathname + u.search + u.hash); }
    var s;
    try { s = await api("GET", "/api/admin/sessao"); }
    catch (err) { E.sessao = null; mostrarEntrada(err.message); return; }
    E.sessao = s;
    var av = $("adm-avatar"), avn = $("adm-avatar-nome");
    if (av) av.textContent = iniciaisAdm(s.nome || s.email || (s.access && s.access.email));
    ler("equipe").then && ler("equipe").then(function () { var a2 = $("adm-avatar"); if (a2) a2.textContent = iniciaisAdm(nomeCompletoSessao()); });
    if (avn) avn.textContent = s.nome || "Minha conta";
    var bc = $("adm-conta"); if (bc) bc.title = (s.nome || (s.access && s.access.email) || "") + (s.papel ? " · " + s.papel : "");
    var dentro = false; try { dentro = sessionStorage.getItem("pv-admin-dentro") === "1"; } catch (x) { /* nada */ }
    if (s.pronto && s.access && s.access.ok && s.github && s.github.ok && dentro && !E.erroVolta) mostrarCasca();
    else mostrarEntrada();
  }

  function voltarEntrada() {
    if (voltando) return; voltando = true;
    try { sessionStorage.removeItem("pv-admin-dentro"); } catch (e) { /* nada */ }
    E.gaveta = null; E.modal = null; E.busca.aberta = false;
    Object.keys(D).forEach(function (k) { delete D[k]; });
    E.pendentes = [];
    iniciar().then(function () { voltando = false; }, function () { voltando = false; });
  }

  $("abrir-busca").addEventListener("click", abrirBusca);
  iniciar();
})();
