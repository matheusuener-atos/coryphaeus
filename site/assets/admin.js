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
    { id: "contas", label: "Contas e cadastros", icon: "contacts", chip: "Contas", o: "as contas", ler: ["contas"] },
    { id: "google", label: "Permissões Google", icon: "shield", chip: "Permissões Google", o: "as contas com Google", ler: ["contas"] },
    { id: "tuneis", label: "Túneis Cloudflare", icon: "dns", chip: "Túneis", o: "os túneis", ler: ["tuneis"] },
    { id: "renovacoes", label: "Não renovações", icon: "notifications", chip: "Não renovações", o: "as não renovações", ler: ["renovacoes"] },
    { id: "emails", label: "Disparo de e-mails", icon: "mail", chip: "E-mails", o: "as campanhas", ler: ["campanhas"] },
    { id: "tokens", label: "Tokens e custos", icon: "token", chip: "Tokens", o: "os tokens e custos", ler: [] },
    { id: "planos", label: "Planos", icon: "payments", chip: "Planos", o: "os planos", ler: ["planos", "tokens:geral:mes"] },
    { id: "materiais", label: "Moderar materiais", icon: "menu_book", chip: "Materiais", o: "os materiais", ler: ["materiais"] },
    { id: "nfse", label: "Notas fiscais", icon: "receipt_long", chip: "Notas fiscais", o: "as notas fiscais", ler: ["nfse"] },
    { id: "equipe", label: "Equipe", icon: "group", chip: "Equipe", o: "a equipe", ler: ["equipe"] },
    { id: "alteracoes", label: "Confirmar alterações", icon: "publish", chip: "Alterações", o: "as alterações", ler: ["alteracoes"] },
  ];
  var TELA = {}; TELAS.forEach(function (t) { TELA[t.id] = t; });

  // O papel que pode cada tipo da fila (a tabela do contrato).
  var DF = ["dono", "financeiro"], DS = ["dono", "suporte"];
  var PAPEIS = {
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
    google: { confirmando: null },
    tuneis: { filtro: "todos", sel: {}, aberto: null },
    renovacoes: {},
    emails: { aba: "campanhas", passo: 1, so: null, camp: novaCamp() },
    tokens: { visao: "geral", periodo: "mes" },
    planos: { novo: { nome: "", id: "", valor: "", anual: "", tokens: "" } },
    materiais: { filtro: "fila", aberto: null, checks: {}, recados: {} },
    nfse: { teste: null, testando: false, pfx: null, senha: "", instalando: false, aviso: null },
  };
  function novaCamp() { return { publico: "", nome: "", assunto: "", pre: "", titulo: "", texto: "", botao: "Abrir o PAULUS", link: "https://paulus.ia.br/", quando: "agora" }; }

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
    if (ch.indexOf("tokens:") === 0) { var p = ch.split(":"); return "/api/admin/tokens?visao=" + p[1] + "&periodo=" + p[2]; }
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
  function tokensChave() { return "tokens:" + U.tokens.visao + ":" + U.tokens.periodo; }
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
    var m = dadosDe("materiais"); if (m) c.materiais = (m.materiais || []).filter(function (x) { return x.situacao === "fila"; }).length;
    var n = dadosDe("nfse"); if (n) c.nfse = (n.pagamentos || []).length + (n.notas || []).filter(function (x) { return x.estado === "rejeitada" || x.estado === "na_fila" || x.estado === "aguardando_confirmacao"; }).length;
    c.alteracoes = E.pendentes.length;
    return c;
  }

  function renderNav() {
    var c = contagens();
    var h = TELAS.map(function (t) {
      var b = c[t.id] || 0;
      return '<a class="nav-item" href="#' + t.id + '"' + (E.tela === t.id ? ' aria-current="page"' : "") + ">" + ic(t.icon) + '<span class="rot">' + esc(t.label) + "</span>" +
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
    hp += pend.length ? pend.map(function (p) {
      return '<button type="button" class="linha-btn" data-a="irTela" data-tela="' + esc(p.tela) + '" data-filtro="' + esc(p.filtro || "") + '">' + ic(p.icone || "arrow_forward") +
        '<span class="txt2"><b>' + esc(p.titulo) + "</b><small>" + esc(p.sub) + "</small></span>" + ic("arrow_forward") + "</button>";
    }).join("") : '<p class="vazio-linha">Nada precisa de você agora.</p>';
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
      '<div class="legenda"><span><i></i>entrada + saída</span><span><i class="s"></i>saída</span></div></div>';

    var av = v.avisos || [];
    var COR = { entrada: "var(--ok)", recusado: "var(--erro)", cancelado: "var(--ink3)", neutro: "var(--ink2)" };
    var mp = cfg("mercado_pago");
    var ha = '<div class="painel">' + painelCab("Últimos avisos do Mercado Pago", "/api/mp/aviso") + (desligado(mp) ? '<p class="aviso-falta embutido">' + ic("warning") + "<span>" + esc(mp.falta) + "</span></p>" : "");
    ha += av.length ? av.map(function (a) {
      var val = Number(a.valor) || 0;
      var txt = a.tom === "entrada" ? "+ " + brl(val) : a.tom === "cancelado" ? "− " + brl(Math.abs(val)) : brl(val);
      return '<div class="aviso-mp"><span class="q">' + esc(quando(a.quando)) + '</span><span class="tp">' + esc(a.tipo) + '</span><span class="tx">' + esc(a.texto) + '</span><span class="v" style="color:' + (COR[a.tom] || COR.neutro) + '">' + esc(txt) + "</span></div>";
    }).join("") : '<p class="vazio-linha">Nenhum aviso ainda.</p>';
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
    var h = cab("Contas e cadastros", "Uma conta por conta Google. O escritório agrupa as contas que compartilham o mesmo CNPJ ou o mesmo endereço de acesso de fora.");
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
    var h = cab("Permissões do Google", "Contas que ligaram o Gmail, a Agenda ou o Drive ao app OAuth PAVLVS. <b>Revogar permissões</b> mexe no que o PAULUS pode fazer no Google da pessoa (serviço a serviço); a conta continua entrando com o mesmo Google. <b>Desvincular</b> solta a conta Google da conta da nuvem: plano e tokens ficam, mas a pessoa precisa entrar com outro Google.");
    var est = estadoLeitura(["contas"], "google"); if (est) return h + est;
    h += erroRecente("contas", "google");
    var todas = dadosDe("contas").contas || [];
    var gs = todas.filter(function (c) { return c.google; });
    var podeRev = pode("google.servicos"), podeDes = pode("google.desvincular");
    h += '<div class="painel">' + painelCab("Contas com Google ligado", gs.length + " de " + todas.length);
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
      return '<div class="linha"><span class="txt2" style="min-width:200px"><b>' + esc(c.nome) + '</b><small class="mono">' + esc(c.email) + "</small></span>" +
        '<span class="chips">' + (c.google.escopos || []).map(function (s) { return '<span class="chip">' + esc(s) + "</span>"; }).join("") + "</span>" +
        '<span class="num s11 c-ink3" style="flex:none;white-space:nowrap">conferido ' + esc(rel(c.google.conferido)) + "</span>" + acoes + "</div>";
    }).join("") : '<p class="vazio-linha">Nenhuma conta ligou o Google ainda.</p>';
    h += "</div>";
    if (!podeRev && !podeDes) h += '<p class="nota-pe">O papel ' + esc(PAPEL_NOME[E.sessao.papel] || E.sessao.papel) + " vê as permissões, mas não revoga nem desvincula.</p>";
    h += '<p class="nota-pe">Os escopos vêm do consentimento guardado no PAULUS instalado; aqui só o nome. O token em si nunca passa por este painel.</p>';
    return h;
  };

  /* ---------- 4. Tuneis Cloudflare ---------- */
  var EST_TUNEL = { healthy: ["saudável", "var(--ok)"], degraded: ["instável", "var(--atencao)"], inactive: ["parado", "var(--ink3)"], down: ["fora do ar", "var(--erro)"], desativado: ["desativado", "var(--erro)"] };
  function parado(t) { return t.estado === "inactive" || t.estado === "down"; }
  function limpezaDe(t) {
    var l = t.limpeza;
    if (!l || l.dias == null) return ["—", "var(--ink3)", null];
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
    var h = cab("Túneis Cloudflare", "Um túnel e um CNAME por escritório. A limpeza diária apaga o que nunca conectou em 7 dias e o parado há mais de 180; a coluna Limpeza mostra quem está perto. Clique na linha para ver o histórico e agir.");
    var est = estadoLeitura(["tuneis"], "tuneis");
    var sel = U.tuneis.sel, nSel = Object.keys(sel).filter(function (k) { return sel[k]; }).length;
    var cf = tuneisCf(), cfOff = desligado(cf), podeA = pode("tunel.apagar");
    h += '<div class="barra-filtros">' + seg("tuneis.filtro", [["todos", "Todos"], ["parados", "Só parados"], ["risco", "Perto de apagar"], ["ativos", "Conectados"]], U.tuneis.filtro) + '<span style="flex:1"></span>' +
      (nSel && podeA ? '<span class="num c-ink2">' + nSel + (nSel === 1 ? " selecionado" : " selecionados") + '</span><button type="button" class="btn-duplo pequeno vermelho" data-a="tuneisApagar"' + attrDis(cfOff, cf.falta) + "><span>" + ic("delete") + "Apagar túnel e DNS</span></button>" : "") + "</div>";
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
    var cols = "14px minmax(140px,1fr) 84px 96px 104px 20px";
    var todosParadosSel = todos.filter(parado).length > 0 && todos.filter(parado).every(function (t) { return sel[t.slug]; });
    var cabeca = (podeA ? '<button type="button" class="caixinha" data-a="tuneisSelParados" role="checkbox" aria-checked="' + todosParadosSel + '" aria-label="Selecionar os parados" title="Selecionar os parados">' + (todosParadosSel ? ic("check") : "") + "</button>" : "<span></span>") +
      '<span>Endereço</span><span>Estado</span><span class="dir">Última conexão</span><span class="dir">Limpeza</span><span></span>';
    var emailOff = desligado(cfg("email"));
    var linhas = lista.map(function (t) {
      var k = t.ativo === false ? "desativado" : t.estado;
      var e = EST_TUNEL[k] || [k, "var(--ink3)"];
      var ult = dt(t.ultima_conexao), velho = !ult || (Date.now() - ult) > 60 * 864e5;
      var l = limpezaDe(t), aberto = U.tuneis.aberto === t.slug, s = !!sel[t.slug];
      var r = '<div class="tunel' + (s ? " sel" : aberto ? " aberto" : "") + '">' +
        '<div class="grade-linha clicavel" role="button" tabindex="0" aria-expanded="' + aberto + '" data-a="tunelAbrir" data-slug="' + esc(t.slug) + '">' +
        (podeA ? '<button type="button" class="caixinha" role="checkbox" aria-checked="' + s + '" aria-label="Selecionar ' + esc(t.slug) + '" data-a="tunelSel" data-slug="' + esc(t.slug) + '">' + (s ? ic("check") : "") + "</button>" : "<span></span>") +
        '<span class="cel-nome endereco"><b class="corta">' + esc(t.slug) + "<span>.paulus.ia.br</span></b><small class=\"corta sans\">" + esc(t.nome) + (t.responsavel ? " · " + esc(t.responsavel) : "") + "</small></span>" +
        sit(e[0], e[1]) + '<span class="num dir" style="color:' + (velho ? "var(--erro)" : "var(--ink2)") + '">' + esc(rel(t.ultima_conexao)) + "</span>" +
        '<span class="num s11 dir" style="color:' + l[1] + '"' + (t.limpeza && t.limpeza.motivo ? ' title="' + esc(t.limpeza.motivo) + '"' : "") + ">" + esc(l[0]) + "</span>" + ic(aberto ? "expand_less" : "expand_more", "s18 c-ink3") + "</div>";
      if (aberto) {
        var hist = (t.historico || []).slice().sort(function (a, b) { return String(b.quando).localeCompare(String(a.quando)); });
        var podeE = pode("tunel.endereco"), podeT = pode("tunel.ativo");
        var filaA = naFila("tunel.apagar", t.slug), filaE = naFila("tunel.endereco", t.slug), filaT = naFila("tunel.ativo", t.slug);
        r += '<div class="tunel-det"><div class="pilha" style="gap:6px"><span class="rotulo">Histórico</span>' +
          (hist.length ? hist.map(function (x) { return '<div class="hist"><span>' + esc(ddmm(x.quando)) + "</span><span>" + esc(x.texto) + "</span></div>"; }).join("") : '<div class="hist"><span>—</span><span>Sem eventos registrados.</span></div>') + "</div>" +
          '<div class="pilha" style="gap:10px"><span class="rotulo">Ações</span><div class="acoes-linha">' +
          '<button type="button" class="mini cheia" data-a="tunelAvisar" data-slug="' + esc(t.slug) + '"' + attrDis(emailOff || !t.responsavel, emailOff ? cfg("email").falta : "sem responsável") + ">" + ic("mail") + "Avisar responsável</button>" +
          (podeE ? '<button type="button" class="mini" data-a="modalEndereco" data-slug="' + esc(t.slug) + '"' + attrDis(cfOff || filaE || filaA, cfOff ? cf.falta : "já está na fila de alterações") + ">" + ic("swap_horiz") + (filaE ? "Troca na fila" : "Alterar endereço") + "</button>" : "") +
          (podeT ? '<button type="button" class="mini" data-a="tunelAtivo" data-slug="' + esc(t.slug) + '"' + attrDis(cfOff || filaT || filaA, cfOff ? cf.falta : "já está na fila de alterações") + ">" + (filaT ? "Na fila" : t.ativo === false ? "Ativar acesso" : "Desativar acesso") + "</button>" : "") +
          (podeA ? '<button type="button" class="mini vermelho" data-a="tunelLiberar" data-slug="' + esc(t.slug) + '"' + attrDis(cfOff || filaA, cfOff ? cf.falta : "já está na fila de alterações") + ">" + (filaA ? "Apagar na fila" : "Liberar endereço") + "</button>" : "") +
          "</div>" + '<dl class="fatos-p f96">' + fato("Túnel", (t.tunnel_id || "—") + " · cfd_tunnel") + fato("Porta", t.porta == null ? "—" : String(t.porta)) + fato("Criado", ddmmaaaa(t.criado_em)) + fato("Responsável", t.responsavel || "—") + "</dl></div></div>";
      }
      return r + "</div>";
    }).join("") || '<p class="vazio-linha">Nenhum túnel com esse filtro.</p>';
    h += '<div class="painel">' + grade(cols, 520, cabeca, linhas) + "</div>";
    var livres = d.livres || [];
    if (livres.length) h += '<div class="chips" style="align-items:center;gap:8px"><span class="rotulo">Endereços livres</span>' + livres.map(function (l) { return '<span class="chip">' + esc(l) + ".paulus.ia.br</span>"; }).join("") + "</div>";
    h += '<p class="nota-pe">Apagar ou liberar remove as conexões, o túnel (cfd_tunnel), o CNAME e o registro escritorio:&lt;slug&gt; no KV. Desativar só pausa o CNAME: o túnel fica, o endereço não responde. O PAULUS do escritório recebe o motivo na próxima tentativa.</p>';
    return h;
  };
  function fato(k, v) { return "<div><dt>" + esc(k) + "</dt><dd>" + esc(v) + "</dd></div>"; }

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
      return '<div class="grade-linha p10"><span class="cel-nome"><b class="corta">' + esc(r.nome) + '</b><small class="corta">' + esc(r.email) + "</small></span>" +
        '<span class="cel-nome"><span class="t13">' + esc(r.plano ? r.plano.nome : "—") + '</span><small class="c-ink3" style="font-size:11px">' + esc(r.plano ? brl(r.plano.valor) : "") + "</small></span>" +
        '<span class="num s11" style="line-height:1.4;color:' + (resta > 0 ? "var(--atencao)" : "var(--erro)") + '" title="venceu em ' + esc(ddmmaaaa(r.fim)) + '">' + esc(prazo) + "</span>" +
        '<span class="t125">' + esc(r.motivo || "—") + "</span>" +
        '<span class="par" style="justify-content:flex-end">' +
        '<button type="button" class="mini cheia" data-a="renovLembrete" data-id="' + esc(r.id) + '"' + (emailOff ? ' disabled title="' + esc(email.falta) + '"' : r.lembrete_em ? ' title="enviado ' + esc(quando(r.lembrete_em)) + '"' : "") + ">" + ic("mail") + (r.lembrete_em ? "Lembrete enviado" : "Enviar lembrete") + "</button>" +
        '<button type="button" class="mini" data-a="abrirConta" data-id="' + esc(r.id) + '">Conta</button>' +
        '<button type="button" class="mini quadrado" data-a="renovTratar" data-id="' + esc(r.id) + '" aria-label="Marcar tratada" title="Marcar tratada">' + ic("check", "c-ink2") + "</button></span></div>";
    }).join("") || '<p class="vazio-linha">Nenhuma pendente.</p>';
    h += '<div class="painel">' + grade(cols, 880, "<span>Conta</span><span>Plano</span><span>Prazo</span><span>Motivo</span><span></span>", linhas) +
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
    var h = cab("Campanhas de e-mail", "Versão 1.0: públicos prontos a partir das contas, um modelo de e-mail com título, texto e botão, e a fila que sai em lotes por minuto do endereço da equipe.");
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
      h += '<div class="painel">' + (ps.length ? ps.map(function (p) {
        return '<div class="linha p10" style="min-height:52px"><span class="txt2" style="min-width:180px;gap:1px"><b>' + esc(p.label) + '</b><small class="mono" style="font-size:11px;color:var(--ink3)">' + (p.n || 0) + " contas · " + (p.gmail || 0) + ' no Gmail</small></span><button type="button" class="mini" data-a="usarPublico" data-id="' + esc(p.id) + '">Usar numa campanha</button></div>';
      }).join("") : '<p class="vazio-linha">Nenhum público.</p>') + "</div>";
      h += '<p class="nota-pe">Os públicos vêm das contas da nuvem (situação, plano, Google). Filtros próprios e importação de lista entram na 1.1.</p>';
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
      esq += '<span class="rotulo">Quem recebe</span><div class="painel" role="radiogroup" aria-label="Público">' + publicosLista().map(function (p) {
        var on = pub && p.id === pub.id;
        return '<button type="button" class="linha-btn publico' + (on ? " on" : "") + '" role="radio" aria-checked="' + on + '" data-a="escolherPublico" data-id="' + esc(p.id) + '"><span class="radio' + (on ? " on" : "") + '"></span><span class="txt2"><b>' + esc(p.label) + "</b><small>" + (p.gmail || 0) + ' no Gmail</small></span><span class="n">' + (p.n || 0) + "</span></button>";
      }).join("") + "</div>";
    } else if (passo === 2) {
      esq += campoTexto("camp-nome", "Nome da campanha (interno)", camp.nome, "Lembrete OAB · outubro", "camp.nome") +
        campoTexto("camp-assunto", "Assunto", camp.assunto, "Um presente para o {escritorio}", "camp.assunto") +
        campoTexto("camp-pre", "Pré-cabeçalho", camp.pre, "o texto cinza que aparece ao lado do assunto", "camp.pre") +
        campoTexto("camp-titulo", "Título", camp.titulo, "Desconto no plano {plano}", "camp.titulo") +
        '<label class="campo-adm"><span class="rot">Texto</span><textarea class="area" id="camp-texto" rows="6" data-in="campo" data-campo="camp.texto" placeholder="Olá, {nome}.">' + esc(camp.texto) + "</textarea></label>" +
        '<div class="grade-campos">' + campoTexto("camp-botao", "Texto do botão", camp.botao, "", "camp.botao") + campoTexto("camp-link", "Link do botão", camp.link, "https://", "camp.link") + "</div>" +
        '<span class="nota-campo">Campos: {nome}, {escritorio}, {plano}, {vence_em}</span>';
    } else {
      var de = (d.envio && d.envio.de) || "naoresponda@paulus.ia.br", ritmo = Number(d.envio && d.envio.ritmo) || 50;
      esq += '<span class="rotulo">Revisar</span><dl class="fatos-p f110">' + fato("Público", pub ? pub.label + " · " + n : "—") + fato("Assunto", trocaCampos(camp.assunto) || "(sem assunto)") + fato("De", "PAVLVS <" + de + ">") +
        fato("Botão", (camp.botao || "—") + " → " + (camp.link || "—")) + fato("Ritmo", ritmo + " por minuto · " + Math.max(1, Math.ceil(n / ritmo)) + " min") + "</dl>" +
        '<span class="rotulo">Quando</span>' + seg("emails.quando", [["agora", "Agora"], ["amanha", "Amanhã, 9h"], ["segunda", "Segunda, 9h"]], camp.quando) +
        '<div style="display:flex;align-items:center;gap:14px;flex-wrap:wrap;padding-top:6px">' +
        '<button type="button" class="btn-duplo" data-a="pedirDisparo"' + attrDis(envioOff || !n, envioOff ? envio.falta : "público vazio") + "><span>" + ic("send") + "Pedir disparo para " + n + (n === 1 ? " conta" : " contas") + "</span></button>" +
        '<button type="button" class="btn-texto-mudo" data-a="enviarTeste"' + attrDis(envioOff, envio.falta) + ">Mandar um teste para mim</button></div>";
    }
    esq += '<div style="display:flex;gap:6px;padding-top:6px">' +
      (passo > 1 ? '<button type="button" class="mini" data-a="passo" data-n="' + (passo - 1) + '">' + ic("arrow_back") + "Voltar</button>" : "") +
      (passo < 3 ? '<button type="button" class="mini cheia" data-a="passo" data-n="' + (passo + 1) + '">Avançar' + ic("arrow_forward") + "</button>" : "") + "</div></div>";
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
    h += '<div class="barra-filtros">' + seg("tokens.visao", [["geral", "Geral"], ["escritorio", "Por escritório"], ["conta", "Por conta"]], U.tokens.visao) +
      seg("tokens.periodo", [["mes", "Este mês"], ["30", "30 dias"], ["ano", ano]], U.tokens.periodo) +
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
      return '<div class="grade-linha p10"><span class="cel-nome" style="gap:3px"><b class="corta" style="font-size:13px">' + esc(l.nome) + '</b><span class="uso" style="height:3px;max-width:220px"><i style="width:' + Math.round(((l.entrada || 0) + (l.saida || 0)) / max * 100) + '%"></i></span></span>' +
        '<span class="num dir c-ink2">' + esc(tok(l.entrada)) + '</span><span class="num dir c-ink2">' + esc(tok(l.saida)) + '</span><span class="num dir" title="' + esc(usd(l.custo_usd)) + '">' + esc(brl(cu)) + '</span><span class="num dir">' + esc(brl(r)) + '</span><span class="num dir" style="color:' + cor + '">' + (m == null ? "—" : pct(m)) + "</span></div>";
    }).join("") || '<p class="vazio-linha">Nada medido neste período.</p>';
    var col = { geral: "Modelo", escritorio: "Escritório", conta: "Conta" }[U.tokens.visao];
    h += '<div class="painel">' + grade(cols, 700, "<span>" + col + '</span><span class="dir">Entrada</span><span class="dir">Saída</span><span class="dir">Custo</span><span class="dir">Arrecadado</span><span class="dir">Margem</span>', linhas) + "</div>";
    return h;
  };

  /* ---------- 9. Planos ---------- */
  function precosPlanos() { var d = dadosDe("tokens:geral:mes"); return d && d.precos ? d.precos : null; }
  // Se o assinante usar o pacote inteiro: a proporcao entrada/saida e uma
  // estimativa (72/28, a do desenho); o preco e o cambio vem da API.
  // O preco e o do modelo do plano (custo_modelo, [entrada, saida] em dolar); sem ele, o IA_PRECOS.
  function custoCheio(tokens, usd) {
    var p = precosPlanos(); if (!p) return null;
    var e = usd ? usd[0] : p.entrada, s = usd ? usd[1] : p.saida;
    return (tokens * 0.72 / 1e6 * e + tokens * 0.28 / 1e6 * s) * p.cambio;
  }
  function planoPadraoUsd() { var d = dadosDe("planos") || {}; var p = (d.planos || []).filter(function (x) { return x.id === d.padrao; })[0]; return p ? p.custo_modelo : null; }
  TELAS_RENDER.planos = function () {
    var h = cab("Planos de assinatura", "A lista vira a variável IA_PLANOS do Worker. Quem já assina fica no plano de agora; o novo valor só entra na próxima renovação.");
    var est = estadoLeitura(["planos"], "planos"); if (est) return h + est;
    h += erroRecente("planos", "planos");
    var d = dadosDe("planos"), ps = d.planos || [], podeE = pode("plano.editar"), podeC = pode("plano.criar");
    var esq = '<div class="pilha g24"><div class="painel">' + ps.map(function (p) {
      var fila = naFila("plano.editar", p.id);
      return '<div class="linha plano-linha"><span class="txt2"><b>' + esc(p.nome) + (p.id === d.padrao ? "<em>padrão</em>" : "") + "</b><small>" + esc(p.id) + " · " + esc(p.modelo_nome || "") + " · " + esc(tok(p.tokens)) + " créditos/mês · " + (p.pessoas || 1) + (p.pessoas === 1 ? " pessoa" : " pessoas") + " · " + (p.valor_anual ? esc(brl(p.valor_anual)) + "/ano" : "sem anual") + (p.recarga ? " · recarga " + esc(brl(p.recarga.valor)) + " / " + esc(tok(p.recarga.tokens)) : "") + "</small></span>" +
        '<span class="num c-ink2">' + (p.assinantes || 0) + (p.assinantes === 1 ? " assinante" : " assinantes") + "</span>" +
        '<span class="valor">' + esc(brl(p.valor)) + "/mês</span>" +
        (podeE ? '<button type="button" class="mini quadrado" data-a="modalPlano" data-id="' + esc(p.id) + '" aria-label="Editar plano ' + esc(p.nome) + '"' + attrDis(fila, "já está na fila de alterações") + ">" + ic("edit") + "</button>" : "") + "</div>";
    }).join("") + '<div class="linha plano-linha"><span class="txt2"><b>Recarga (Pix)</b><small>a de cada plano, na linha dele · pacotes ½ · 1 · 2 no mesmo preço por crédito</small></span></div></div>' +
      '<div class="painel"><div class="painel-cab"><span class="rotulo">IA_PLANOS</span><button type="button" class="btn-texto-mudo s12" data-a="copiarJson">Copiar JSON</button></div><pre class="json">' + esc(d.json || JSON.stringify(ps.map(function (p) { return { id: p.id, nome: p.nome, valor: p.valor, tokens: p.tokens }; }), null, 2)) + "</pre></div></div>";
    var dir;
    if (podeC) {
      var np = U.planos.novo, v = numDec(np.valor), t = numDec(np.tokens) * 1e6, cc = t ? custoCheio(t, planoPadraoUsd()) : null, mg = cc != null && v ? 1 - cc / v : null;
      dir = '<div class="pilha"><span class="rotulo">Novo plano</span>' +
        campoTexto("plano-nome", "Nome", np.nome, "Escritório Grande", "plano.nome") +
        '<label class="campo-adm"><span class="rot">Id</span><span class="caixa-campo mono"><input id="plano-id" data-in="campo" data-campo="plano.id" value="' + esc(np.id) + '" placeholder="grande" spellcheck="false" maxlength="24"></span><span class="nota-campo">2 a 24 letras minúsculas, números e hífen</span></label>' +
        '<div class="grade-campos">' + campoNum("plano-valor", "Valor por mês", np.valor, "plano.valor", "R$") + campoNum("plano-anual", "Valor por ano", np.anual, "plano.anual", "R$") + campoNum("plano-tokens", "Créditos por mês", np.tokens, "plano.tokens", "", "M") + "</div>" +
        '<span class="nota-campo">O plano novo usa o modelo e os recursos do Escritório; para mudar, edite o IA_PLANOS.</span>' +
        '<div class="conta-rapida"><span class="rotulo">Conta rápida</span><span>' + (t ? esc(brl(v / (t / 1e6))) + " por milhão de tokens · uma pergunta média (3.500 tokens) sai a R$ " + esc(dec(v / (t / 3500), 3)) : "Preencha valor e tokens.") + "</span>" +
        (t ? (cc != null ? '<span style="color:' + (mg >= 0.4 ? "var(--ok)" : "var(--erro)") + '">Se o assinante usar tudo, custa ' + esc(brl(cc)) + " no provedor do modelo: margem mínima de " + Math.round(mg * 100) + "%.</span>" : '<span class="c-ink3">Sem os preços (' + esc(D["tokens:geral:mes"] && D["tokens:geral:mes"].erro || "carregando") + ") não dá para calcular o custo.</span>") : "") + "</div>" +
        '<button type="button" class="btn-duplo inicio" data-a="criarPlano"><span>Criar plano</span></button></div>';
    } else {
      dir = '<p class="nota-pe">O papel ' + esc(PAPEL_NOME[E.sessao.papel] || E.sessao.papel) + " vê os planos, mas não cria nem edita.</p>";
    }
    return h + '<div class="duas-col d400">' + esq + dir + "</div>";
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
    var h = cab("Notas fiscais (NFS-e)", "A NFS-e que o PAVLVS emite para quem assina o PAULUS. Emitir, cancelar, substituir, o certificado e os parâmetros valem <b>na hora</b>; só os três interruptores passam pela fila de alterações.");
    var est = estadoLeitura(["nfse"], "nfse"); if (est) return h + est;
    h += erroRecente("nfse", "nfse");
    var d = dadosDe("nfse"), s = d.situacao || null, emitir = podeNf(), N = U.nfse;
    var trava = emitir ? "" : ' disabled title="o papel ' + esc(E.sessao.papel) + ' só vê as notas fiscais"';
    if (d.emissor && d.emissor.ligado === false) h += falta(d.emissor);
    if (d.erro) h += '<p class="erro-linha">' + ic("warning") + "<span>" + esc(d.erro) + "</span></p>";
    var prod = s && s.ambiente === "producao";
    // o topo: o selo do ambiente e os quatro botões
    h += '<div class="nf-topo"><span class="nf-selo' + (prod ? " producao" : "") + '">' + (prod ? "produção · as notas valem de verdade" : "ambiente de testes · produção restrita, sem valor fiscal") + "</span>" +
      '<div class="nf-botoes"><button type="button" class="btn-acao verde" data-a="nfEmitir"' + (s ? trava : " disabled") + ">" + ic("receipt_long") + "Emitir NFS-e</button>" +
      '<button type="button" class="btn-acao" data-a="nfClientes"' + (s ? "" : " disabled") + ">" + ic("contacts") + "Clientes</button>" +
      '<button type="button" class="btn-acao" data-a="nfParametros"' + (s ? "" : " disabled") + ">" + ic("tune") + "Parâmetros</button>" +
      '<button type="button" class="btn-acao" data-a="nfTestar"' + (s ? trava : " disabled") + (N.testando ? " disabled" : "") + ">" + ic("lan") + (N.testando ? "Testando…" : "Testar comunicação") + "</button></div></div>";
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
      ["email", "Entregar ao app do cliente logo depois de emitir", "a nota (PDF e XML) aparece no PAULUS dele; desligado, o botão Enviar ao cliente entrega"],
      ["mail", "Mandar também por e-mail", "PDF e XML anexos, ao e-mail fiscal do cliente; precisa da RESEND_API_KEY"]];
    var p = s ? (s.prestador || {}).dados || {} : {};
    var fatos = s ? [["Prestador", p.razao_social ? p.razao_social + " · " + (nfDoc(p.documento) || "CNPJ a definir") : "a definir em Parâmetros"],
      ["Serviço", (p.servico || {}).ctribnac ? "cTribNac " + p.servico.ctribnac + ((p.servico || {}).nbs ? " · NBS " + p.servico.nbs : "") + ((p.servico || {}).aliquota_iss_bp ? " · ISS " + nfPct(p.servico.aliquota_iss_bp) + "%" : "") : "a definir"],
      ["Município", s.municipio ? s.municipio.frase : "—"], ["Próxima DPS", "nº " + s.proximo_numero + " · série " + (p.serie || "1")]] : [];
    h += '<div class="duas-col"><div class="painel">' + OP.map(function (o) {
      var on = !!atual[o[0]], mud = pc && !!c[o[0]] !== on;
      return '<button type="button" class="linha-btn" role="switch" aria-checked="' + on + '" data-a="nfseCfg" data-k="' + o[0] + '"' + (podeC ? "" : ' disabled title="o papel ' + esc(E.sessao.papel) + ' não muda a NFS-e"') + '><span class="txt2"><b>' + esc(o[1]) + "</b><small>" + esc(o[2]) + (mud ? ' · <span class="c-atencao">na fila</span>' : "") + "</small></span>" + sw(on) + "</button>";
    }).join("") + "</div>" + (fatos.length ? '<dl class="fatos-p f110 alto">' + fatos.map(function (f) { return fato(f[0], f[1]); }).join("") + "</dl>" : "<span></span>") + "</div>";
    // a lista das notas
    var ns = d.notas || [];
    var cols = "64px minmax(170px,1fr) 120px 96px 150px";
    var linhas = ns.map(function (n) {
      var cor = NF_SIT[n.estado] || "var(--ink3)", txt = n.estado_rotulo + (n.ambiente !== "producao" ? " · testes" : "");
      var A = [];
      if (n.estado === "emitida" || n.estado === "cancelada" || n.estado === "substituida") {
        A.push('<a class="mini" href="' + NF + "notas/" + n.id + '/pdf?baixar=1" download>' + ic("download") + "PDF</a>");
        A.push(nfMini("Imprimir", "print", "nfImprimir", n.id));
        A.push('<a class="mini" href="' + NF + "notas/" + n.id + '/xml" download>' + ic("code") + "XML</a>");
      }
      if (n.estado === "emitida") {
        A.push(nfMini(n.cliente_avisado && !/^erro/.test(n.cliente_avisado) ? "Reenviar ao cliente" : "Enviar ao cliente", "send", "nfEnviar", n.id, n.conta ? trava : ' disabled title="nota sem conta de assinante"'));
        A.push(nfMini("Substituir", "swap_horiz", "nfSubstituir", n.id, trava));
        A.push('<button type="button" class="mini vermelho" data-a="nfCancelar" data-id="' + n.id + '"' + trava + ">" + ic("block") + "Cancelar</button>");
      } else if (n.estado === "na_fila" || n.estado === "aguardando_confirmacao" || n.estado === "enviando") {
        A.push(nfMini("Tentar agora", "refresh", "nfTentar", n.id, trava));
      } else if (n.estado === "rejeitada" || n.estado === "rascunho") {
        A.push(nfMini("Descartar", "delete", "nfDescartar", n.id, trava));
      }
      var info = [];
      if (n.erro && n.estado !== "emitida") info.push(n.erro);
      if (n.cliente_avisado && !/^erro/.test(n.cliente_avisado)) info.push("no app do cliente desde " + ddmm(n.cliente_avisado));
      else if (n.cliente_avisado) info.push("app do cliente: " + n.cliente_avisado);
      if (n.email) info.push("e-mail: " + n.email);
      if (n.substituida_por_id) info.push("substituída pela nota " + ((nfNota(n.substituida_por_id) || {}).numero || "#" + n.substituida_por_id));
      return '<div class="grade-linha p10"><span class="num">' + esc(n.numero || "—") + "</span>" +
        '<span class="cel-nome"><b class="corta" style="font-size:13px">' + esc(n.cliente || "—") + "</b><small>" + esc(nfDoc(n.documento)) + "</small></span>" +
        '<span class="num c-ink2">' + esc(nfCompetencia(n.competencia)) + '</span><span class="num dir">' + esc(brl(n.centavos / 100)) + "</span>" +
        '<span class="sit" style="color:' + cor + '" title="' + esc(txt) + '"><i></i><span class="corta">' + esc(txt) + "</span></span>" +
        (A.length || info.length ? '<div class="nf-acoes">' + A.join("") + (info.length ? '<small class="nf-info">' + esc(info.join(" · ")) + "</small>" : "") + "</div>" : "") + "</div>";
    }).join("") || '<p class="vazio-linha">Nenhuma nota ainda. Comece por Emitir NFS-e.</p>';
    h += '<div class="painel">' + painelCab("Notas", ns.length + (ns.length === 1 ? " nota" : " notas")) +
      grade(cols, 640, '<span>Nº</span><span>Cliente</span><span>Competência</span><span class="dir">Valor</span><span>Situação</span>', linhas) + "</div>";
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
      h += '<div class="nf-cert"><label class="btn-acao nf-arquivo">' + ic("upload") + '<span class="corta">' + esc(N.pfx ? N.pfx.nome : "Escolher o .pfx") + '</span><input type="file" id="nf-pfx" data-in="nfPfx" accept=".pfx,.p12,application/x-pkcs12"></label>' +
        '<span class="caixa-campo fundo nf-senha"><input type="password" id="nf-senha" data-in="nfSenha" value="' + esc(N.senha) + '" placeholder="senha do certificado" autocomplete="off" aria-label="Senha do certificado"></span>' +
        '<button type="button" class="btn-acao" data-a="nfCert"' + (N.instalando || !N.pfx ? " disabled" : "") + ">" + (N.instalando ? "Instalando…" : c.instalado ? "Trocar" : "Instalar") + "</button></div>" +
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
    h += '<div class="painel">' + (d.membros || []).map(function (m) {
      var p = ultimaNaFila("equipe.papel", m.email), papel = p && p.dados ? p.dados.papel : m.papel;
      return '<div class="linha"><span class="txt2" style="min-width:200px"><b>' + esc(m.nome || m.email) + '</b><small class="mono">' + esc(m.email) + " · último acesso " + esc(m.ultimo ? quando(m.ultimo) : "nunca") + (p ? ' · <span class="c-atencao">na fila</span>' : "") + "</small></span>" +
        seg("equipe.papel:" + m.email, [["dono", "Dono"], ["financeiro", "Financeiro"], ["suporte", "Suporte"]], papel, "pequeno", !podeP) + "</div>";
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
    h += '<div class="painel">' + painelCab("Publicações anteriores") + (pubs.length ? pubs.map(function (p) {
      return '<div class="linha p10"><span class="num s11 c-ink3" style="width:92px;flex:none">' + esc(quando(p.quando)) + '</span><span class="num" style="width:72px;flex:none">' + esc(String(p.commit || "").slice(0, 7)) + '</span><span style="flex:1;min-width:200px;font-size:13px;color:var(--ink2)">' + esc(p.resumo) + (p.por ? ' <span class="c-ink3">· ' + esc(p.por) + "</span>" : "") + '</span><span class="num s11 c-ink3">' + (p.n || 0) + (p.n === 1 ? " alteração" : " alterações") + "</span></div>";
    }).join("") : '<p class="vazio-linha">Nenhuma publicação ainda.</p>') + "</div>";
    return h;
  };

  /* ================================================================ camada: gaveta, modal, busca */

  function renderCamada() {
    var el = $("camada");
    var g = el.querySelector(".gaveta"), gs = g ? g.scrollTop : 0;
    var b = el.querySelector(".busca-res"), bs = b ? b.scrollTop : 0;
    var h = "";
    if (E.gaveta) h += gavetaHtml();
    if (E.modal) h += modalHtml();
    if (E.busca.aberta) h += buscaHtml();
    pintar(el, h);
    g = el.querySelector(".gaveta"); if (g) g.scrollTop = gs;
    b = el.querySelector(".busca-res"); if (b) b.scrollTop = bs;
    document.body.style.overflow = h ? "hidden" : "";
  }

  function contaResumo(id) { var d = dadosDe("contas"); return d ? (d.contas || []).filter(function (c) { return String(c.id) === String(id); })[0] : null; }

  function gavetaHtml() {
    var G = E.gaveta, c = G.det || G.resumo;
    var h = '<div class="veu" data-a="fecharGaveta"></div><aside class="gaveta" role="dialog" aria-modal="true" aria-labelledby="gaveta-titulo">' +
      '<div class="gaveta-cab"><button type="button" class="btn-icone" data-a="fecharGaveta" aria-label="Fechar" id="gaveta-fechar">' + ic("arrow_back", "s18") + '</button><span class="rotulo corta">Conta · ' + esc(G.id) + "</span></div>";
    if (!c) {
      return h + '<div class="gaveta-corpo">' + (G.erro ? '<p class="erro-linha">' + ic("warning") + "<span>Não consegui ler a conta agora: " + esc(G.erro) + "</span></p>" : '<p class="carregando">Carregando…</p>') + "</div></aside>";
    }
    var s = sitConta(c.situacao), det = G.det;
    h += '<div class="gaveta-corpo"><div class="pilha" style="gap:6px"><h2 id="gaveta-titulo">' + esc(c.nome) + '</h2><span class="num c-mute">' + esc(c.email) + "</span>" +
      '<span class="sit" style="color:' + s[1] + '"><i></i>' + esc(s[0]) + (c.plano ? " · " + esc(c.plano.nome) + " · " + esc(brl(c.plano.valor)) + "/mês" : "") + "</span></div>";
    if (G.erro) h += '<p class="erro-linha">' + ic("warning") + "<span>Não consegui ler o detalhe da conta: " + esc(G.erro) + "</span></p>";
    if (!det) return h + '<p class="carregando">Carregando o detalhe…</p></div></aside>';
    // ciclo
    if (det.ciclo) {
      var cic = det.ciclo, p = cic.tokens ? Math.min(100, Math.round((cic.usados || 0) / cic.tokens * 100)) : 0;
      h += '<div class="pilha" style="gap:8px"><div class="entre"><span>Ciclo ' + esc(ddmm(cic.inicio)) + " → " + esc(ddmm(cic.fim)) + "</span><span>" + p + '% usado</span></div><span class="uso"><i style="width:' + p + '%"></i></span>' +
        '<div class="entre s12"><span>' + esc(tok(cic.usados)) + " usados</span><span>" + esc(tok(det.restantes)) + ' restantes <span class="c-ink3">(+' + esc(tok(det.extra)) + " recarga)</span></span></div></div>";
    } else {
      h += '<div class="entre s12"><span>Sem ciclo aberto</span><span>' + esc(tok(det.restantes)) + ' restantes <span class="c-ink3">(+' + esc(tok(det.extra)) + " recarga)</span></span></div>";
    }
    var cad = det.cadastro || {}, esc_ = det.escritorio || {}, con = det.consentimento, ass = det.assinatura;
    var prepago = ass && (ass.periodo === "anual" || ass.periodo === "avulso");
    var mp = !ass ? "sem assinatura"
      : prepago ? (ass.periodo === "anual" ? "anual" : "um mês no Pix") + " · " + (SIT_PAGO[ass.situacao] || ass.situacao) + (det.pago_ate ? " · até " + ddmmaaaa(det.pago_ate) : "")
      : "preapproval " + ass.situacao + " · " + ass.id + (ass.desde ? " · desde " + ddmmaaaa(ass.desde) : "");
    if (det.plano_proximo) mp += " · troca para " + (det.plano_proximo.nome || det.plano_proximo.id || det.plano_proximo) + " na renovação";
    var gtxt = det.google ? (det.google.escopos || []).join(" · ") || "ligado, sem escopos" : "não ligado";
    if (det.google_pendente) gtxt += " · revogação pendente no PAULUS";
    h += '<dl class="fatos-p">' + fato("Escritório", (esc_.nome || "—") + (esc_.slug ? " · " + esc_.slug + ".paulus.ia.br" : "")) + fato("CPF/CNPJ", cad.documento || esc_.documento || "—") +
      fato("OAB, RG ou CNH", cad.oab || det.oab || "—") + fato("Telefone", cad.telefone || "—") + fato("Conta desde", ddmmaaaa(det.criada)) + fato("Google", gtxt) +
      fato("Consentimento", con ? "termos " + con.versao + " · " + (con.quem || "") + (con.quando ? " · " + ddmmaaaa(con.quando) : "") : "—") + fato("Mercado Pago", mp) + "</dl>";
    // instalacoes
    var inst = det.instalacoes || [], podeI = pode("conta.instalacao.apagar");
    h += '<div class="pilha" style="gap:10px"><span class="rotulo">Instalações · ' + inst.length + ' de 3</span><div class="inst">' + (inst.length ? inst.map(function (i) {
      var fila = naFila("conta.instalacao.apagar", det.id + ":" + i.hash8);
      return '<div class="linha"><span class="txt2"><b class="corta">' + esc(i.instalacao) + "</b><small>segredo " + esc(i.hash8) + " · desde " + esc(ddmm(i.criado)) + "</small></span>" +
        (podeI ? '<button type="button" class="mini" style="height:26px" data-a="instDesvincular" data-hash="' + esc(i.hash8) + '" data-inst="' + esc(i.instalacao) + '"' + attrDis(fila, "já está na fila de alterações") + ">" + (fila ? "Na fila" : "Desvincular") + "</button>" : "") + "</div>";
    }).join("") : '<p class="vazio-linha" style="padding:14px">Nenhuma instalação ligada.</p>') + "</div></div>";
    // pagamentos
    var pgs = (det.pagamentos || []).slice().reverse(), podeR = pode("conta.reembolsar"), mpDesl = desligado(cfg("mercado_pago"));
    h += '<div class="pilha" style="gap:10px"><span class="rotulo">Pagamentos · ' + pgs.length + '</span><div class="inst">' + (pgs.length ? pgs.map(function (x) {
      var fila = naFila("conta.reembolsar", det.id + ":" + x.ref);
      var dias = Math.floor((Date.now() - Date.parse(x.quando)) / 864e5);
      var sub = x.reembolso ? "reembolsado em " + ddmm(x.reembolso.quando) + (x.reembolso.por ? " · " + x.reembolso.por : "")
        : (dias <= 7 ? "há " + dias + (dias === 1 ? " dia · no prazo de arrependimento" : " dias · no prazo de arrependimento") : "há " + dias + " dias · fora dos 7 dias");
      var botao = !podeR || x.reembolso ? "" : '<button type="button" class="mini" style="height:26px" data-a="contaReembolsar" data-ref="' + esc(x.ref) + '"' +
        attrDis(fila || mpDesl, fila ? "já está na fila de alterações" : cfg("mercado_pago").falta) + ">" + (fila ? "Na fila" : "Reembolsar") + "</button>";
      return '<div class="linha"><span class="txt2"><b class="corta">' + esc(TIPO_PAG[x.tipo] || x.tipo) + " · " + esc(brl(x.valor)) + " · " + esc(ddmm(x.quando)) + "</b><small" +
        (x.reembolso ? ' class="c-ink3"' : "") + ">" + esc(sub) + "</small></span>" + botao + "</div>";
    }).join("") : '<p class="vazio-linha" style="padding:14px">Nenhum pagamento.</p>') + "</div>" +
      (podeR && pgs.some(function (x) { return !x.reembolso; }) ? '<span class="nota-campo">Reembolsar devolve o valor inteiro pelo Mercado Pago, no cartão ou no Pix de origem, e tira da conta o que ele pagou: o anual e o mês no Pix acabam, a mensalidade cancela a assinatura, a recarga sai dos créditos. Entra na fila e acontece ao confirmar. A nota fiscal já emitida se cancela em Notas fiscais.</span>' : "") + "</div>";
    // acoes
    var nome1 = primeiro(det.nome), mpOff = desligado(cfg("mercado_pago"));
    var A = [];
    A.push(acaoG("mail", "Enviar e-mail para " + nome1, "contaEmail"));
    if (pode("conta.creditar")) A.push(acaoG("account_balance_wallet", naFila("conta.creditar", det.id) ? "Cortesia na fila (+10M)" : "Creditar tokens de cortesia", "contaCreditar"));
    if (pode("google.servicos") && det.google) A.push(acaoG("shield", "Revogar permissões do Google", "modalGoogle", naFila("google.servicos", det.id) ? "já está na fila de alterações" : ""));
    if (pode("google.desvincular") && det.google) A.push(acaoG("link_off", naFila("google.desvincular", det.id) ? "Desvinculação na fila" : "Desvincular conta Google", "contaDesvincular", naFila("google.desvincular", det.id) ? "já está na fila de alterações" : ""));
    if (pode("conta.cancelar") && ass && !prepago && ass.situacao !== "cancelled" && det.situacao !== "cancelada") A.push(acaoG("close", naFila("conta.cancelar", det.id) ? "Cancelamento na fila" : "Cancelar assinatura no Mercado Pago", "contaCancelar", mpOff ? cfg("mercado_pago").falta : naFila("conta.cancelar", det.id) ? "já está na fila de alterações" : "", true));
    h += '<div class="pilha" style="gap:10px"><span class="rotulo">Ações</span><div class="pilha" style="gap:6px">' + A.join("") + "</div>" + (mpOff && pode("conta.cancelar") && ass ? '<span class="nota-campo">' + esc(cfg("mercado_pago").falta) + "</span>" : "") + "</div>";
    return h + "</div></aside>";
  }
  var TIPO_PAG = { assinatura: "Mensalidade", anual: "Anual", avulso: "Mês no Pix", recarga: "Recarga" };
  var SIT_PAGO = { authorized: "em dia", expired: "vencido", refunded: "reembolsado" };
  function acaoG(icone, rot, a, travado, vermelho) {
    return '<button type="button" class="acao-g' + (vermelho ? " vermelho" : "") + '" data-a="' + a + '" data-id="' + esc(E.gaveta.id) + '"' + attrDis(!!travado, travado) + ">" + ic(icone) + '<span class="rot">' + esc(rot) + "</span>" + ic("arrow_forward") + "</button>";
  }

  var SERV_G = [["gmail", "Gmail", "ler e enviar, com Aprovações", "M", "#EA4335"], ["calendar.events", "Agenda e Meet", "criar e atualizar eventos", "31", "#1A73E8"], ["drive.file", "Drive · enviar", "só o que o PAULUS criou", "D", "#FBBC04"], ["drive.readonly", "Drive · ler", "cópia das pastas escolhidas", "D", "#34A853"]];
  function modalCab(rot) { return '<div class="modal-cab"><span class="rotulo" id="modal-titulo">' + esc(rot) + '</span><button type="button" class="btn-icone" data-a="fecharModal" aria-label="Fechar">' + ic("close", "s18") + "</button></div>"; }
  function modalPe(botao) { return '<div class="modal-pe"><button type="button" class="mini h32" data-a="fecharModal">Cancelar</button>' + botao + "</div>"; }
  function modalHtml() {
    var M = E.modal, larga = /^nf(Emitir|Clientes|Parametros|Substituir)$/.test(M.tipo);
    var h = '<div class="veu forte" data-a="fecharModal"></div><div class="modal' + (larga ? " larga" : "") + '" role="dialog" aria-modal="true" aria-labelledby="modal-titulo">';
    if (/^nf/.test(M.tipo)) {
      h += nfModalHtml(M);
    } else if (M.tipo === "google") {
      var n = SERV_G.filter(function (s) { return M.ligados[s[0]]; }).length;
      h += modalCab("Permissões do Google") + '<div class="modal-corpo"><div class="quem"><b>' + esc(M.nome) + "</b><span>" + esc(M.email) + '</span></div><div class="caixa-escura">' +
        SERV_G.map(function (s) {
          var on = !!M.ligados[s[0]];
          return '<button type="button" class="linha-btn servico-g" role="switch" aria-checked="' + on + '" data-a="googleServico" data-k="' + s[0] + '"><span class="tile" style="background:' + s[4] + '" aria-hidden="true">' + s[3] + '</span><span class="txt2"><b>' + s[1] + "</b><small>" + s[2] + "</small><small>" + s[0] + "</small></span>" + sw(on) + "</button>";
        }).join("") + '</div><p class="nota-campo">Desligar um serviço revoga só esse escopo no Google. Com todos desligados, o token inteiro é revogado e o PAULUS da pessoa pede o consentimento de novo. A conta continua entrando com este Google.</p></div>' +
        modalPe('<button type="button" class="btn-acao" data-a="googleAplicar" id="modal-ok">Aplicar · ' + n + (n === 1 ? " ligado" : " ligados") + "</button>");
    } else if (M.tipo === "endereco") {
      var ch = M.check || { msg: "", cor: "var(--ink3)", ok: false };
      var livres = ((dadosDe("tuneis") || {}).livres || []);
      h += modalCab("Alterar endereço") + '<div class="modal-corpo"><div class="pilha" style="gap:2px"><span class="t13 c-mute">Endereço atual</span><span class="endereco"><b>' + esc(M.slug) + "<span>.paulus.ia.br</span></b></span></div>" +
        '<label class="campo-adm"><span class="rot">Endereço novo</span><span class="caixa-campo mono fundo"><input id="modal-slug" data-in="slugNovo" value="' + esc(M.novo) + '" placeholder="nome-do-escritorio" spellcheck="false" autocapitalize="none" maxlength="24" aria-describedby="modal-slug-msg"><span class="sufixo">.paulus.ia.br</span></span>' +
        '<span class="msg-slug" id="modal-slug-msg" aria-live="polite" style="color:' + ch.cor + '">' + (ch.msg ? "<i></i>" + esc(ch.msg) : "") + "</span></label>" +
        (livres.length ? '<div class="pilha" style="gap:6px"><span class="nota-campo">Ou use um endereço livre</span><div class="chips">' + livres.map(function (l) { return '<button type="button" class="chip" data-a="usarLivre" data-v="' + esc(l) + '">' + esc(l) + "</button>"; }).join("") + "</div></div>" : "") +
        '<p class="nota-campo">O CNAME antigo é apagado e o novo criado no mesmo túnel; o PAULUS do escritório recebe o endereço novo na próxima conexão. O antigo fica livre para outro escritório.</p></div>' +
        modalPe('<button type="button" class="btn-acao" data-a="enderecoConfirmar" id="modal-ok"' + (ch.ok ? "" : " disabled") + ">" + ic("swap_horiz") + "Trocar endereço</button>");
    } else if (M.tipo === "plano") {
      var v = numDec(M.valor), va = numDec(M.anual), t = numDec(M.tokens) * 1e6, cc = t ? custoCheio(t, M.usd) : null;
      h += modalCab("Editar plano") + '<div class="modal-corpo"><b style="font:500 15px var(--sans)">' + esc(M.nome) + ' <span class="num s11 c-ink3">' + esc(M.id) + "</span></b>" +
        '<div class="grade-campos">' + campoModal("modal-valor", "Valor por mês", M.valor, "planoValor", "R$") + campoModal("modal-anual", "Valor por ano", M.anual, "planoAnual", "R$") + campoModal("modal-tokens", "Créditos por mês", M.tokens, "planoTokens", "", "M") + "</div>" +
        '<span class="t125">' + (t ? esc(brl(v / (t / 1e6))) + " por milhão" + (cc != null ? " · se o assinante usar tudo, custa " + esc(brl(cc)) + " no " + esc(M.modelo || "modelo do plano") : "") + (va && v ? " · o anual sai " + Math.round((1 - va / (v * 12)) * 100) + "% abaixo de 12 meses" : "") : "Preencha valor e créditos.") + "</span>" +
        '<p class="nota-campo">Quem já assina continua pagando o valor de agora até a próxima renovação; o PUT no preapproval do Mercado Pago sai na publicação.</p></div>' +
        modalPe('<button type="button" class="btn-acao" data-a="planoSalvar" id="modal-ok"' + (v > 0 && va > 0 && t > 0 ? "" : " disabled") + ">Salvar</button>");
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
    var v = E.modal.v[k];
    return '<label class="campo-adm"><span class="rot">' + esc(rot) + '</span><span class="caixa-campo fundo"><input id="' + nfId(k) + '" data-in="nf" data-k="' + esc(k) + '" value="' + esc(v == null ? "" : v) + '"' + (extra || "") + ' autocomplete="off"></span></label>';
  }
  function nfEscolha(k, rot, opcoes, inp) {
    var v = String(E.modal.v[k] == null ? "" : E.modal.v[k]);
    return '<label class="campo-adm"><span class="rot">' + esc(rot) + '</span><span class="caixa-campo fundo"><select id="' + nfId(k) + '" data-in="' + (inp || "nf") + '" data-k="' + esc(k) + '">' +
      opcoes.map(function (o) { return '<option value="' + esc(o[0]) + '"' + (String(o[0]) === v ? " selected" : "") + ">" + esc(o[1]) + "</option>"; }).join("") + "</select></span></label>";
  }
  function nfDominio(obj, comCodigo) { return Object.keys(obj || {}).sort().map(function (k) { return [k, (comCodigo ? k + " – " : "") + obj[k]]; }); }
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
      }, function () { delete nfMunPedidos[cod]; });
    }
    return cod;
  }
  function nfMunicipio(k, rot, extra, kUf) {
    var M = E.modal; M.mun = M.mun || {};
    var st = M.mun[k] || {}, cod = String(M.v[k] == null ? "" : M.v[k]), id = nfId(k), lista = id + "-lista";
    var aberto = !!(st.editando && st.res);
    var h = '<div class="campo-adm nf-mun"><label class="rot" for="' + id + '">' + esc(rot) + '</label><span class="caixa-campo fundo"><input id="' + id + '" data-in="nfMun" data-k="' + esc(k) + '" data-uf="' + esc(kUf || "") +
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
    } else if (/^\d{7}$/.test(cod)) {
      h += '<span class="nf-mun-cod">código IBGE ' + esc(cod) + "</span>";
    }
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
      h += nfDuas(nfEscolha("conta", "Cliente (assinante)", [["", cl ? "— preencher à mão —" : "carregando…"]].concat((cl || []).map(function (c) { return [c.id, c.nome + (c.faltas && c.faltas.length ? " · falta " + c.faltas.join(", ") : "")]; })), "nfCliente"),
        nfEscolha("pagamento", "Pagamento (opcional)", [["", "— nenhum —"]].concat(pgs.map(function (x) { return [x.id, (x.cliente || "conta") + " · " + x.tipo + " · " + brl(x.valor) + " · " + ddmm(x.quando)]; })), "nfPagamento"));
      var esc_ = (cl || []).filter(function (c) { return c.id === M.v.conta; })[0];
      if (esc_ && esc_.faltas && esc_.faltas.length) h += '<p class="aviso-falta">' + ic("warning") + "<span>No cadastro de " + esc(esc_.nome) + " falta " + esc(esc_.faltas.join(", ")) + ". Complete abaixo (vale só para esta nota) ou em Clientes (vale para as próximas).</span></p>";
      h += nfSub("Tomador") + nfTomadorCampos("tomador.") + nfSub("Serviço") +
        nfDuas(nfCampo("valor", "Valor (R$)", ' inputmode="decimal" placeholder="300,00"'), nfCampo("competencia", "Competência", ' type="month"')) +
        nfCampo("descricao", "Descrição") +
        '<p class="nota-campo">' + (prod ? "<b>Produção:</b> esta nota vale de verdade." : "Ambiente de testes: a nota não tem valor fiscal.") + " Com um pagamento escolhido, o valor, a descrição e a competência vêm dele.</p>" + nfErro(M) + "</div>" +
        modalPe('<button type="button" class="btn-acao verde" data-a="nfEmitirConfirmar" id="modal-ok"' + (M.enviando ? " disabled" : "") + ">" + ic("receipt_long") + (M.enviando ? "Emitindo…" : "Emitir") + "</button>");
    } else if (M.tipo === "nfClientes") {
      h += modalCab("Clientes") + '<div class="modal-corpo"><p class="nota-campo">Os assinantes vêm do cadastro feito no paulus.ia.br. O que você editar aqui vale para as notas (dados fiscais); o cadastro original da conta fica como está.</p>';
      if (M.erroClientes) h += '<p class="erro-linha">' + ic("warning") + "<span>Não consegui ler os clientes: " + esc(M.erroClientes) + "</span></p>";
      else if (!M.clientes) h += '<p class="carregando">Carregando…</p>';
      else if (!M.clientes.length) h += '<p class="vazio-linha">Nenhum assinante ainda.</p>';
      else {
        h += '<div class="caixa-escura">' + M.clientes.map(function (c) {
          var t = c.tomador || {}, aberto = M.editando === c.id;
          var r = '<div class="linha"><span class="txt2"><b>' + esc(c.nome) + "</b><small>" + esc([nfDoc(t.documento), t.email, c.plano ? c.plano.nome : "", c.situacao].filter(Boolean).join(" · ")) +
            (c.faltas && c.faltas.length ? ' · <span class="c-atencao">falta ' + esc(c.faltas.join(", ")) + "</span>" : ' · <span class="c-ok">completo</span>') + "</small></span>" +
            (podeNf() ? '<button type="button" class="mini" data-a="nfCliEditar" data-id="' + esc(c.id) + '">' + (aberto ? "Fechar" : "Editar") + "</button>" : "") + "</div>";
          if (aberto) r += '<div class="nf-form">' + nfTomadorCampos("tomador.") + nfErro(M) + '<div class="nf-botoes"><button type="button" class="btn-acao" data-a="nfCliSalvar" data-id="' + esc(c.id) + '"' + (M.enviando ? " disabled" : "") + ">" + (M.enviando ? "Salvando…" : "Salvar") + "</button></div></div>";
          return r;
        }).join("") + "</div>";
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
        nfDuas(nfCampo("servico.ctribnac", "Código de serviço (cTribNac)", ' placeholder="ex.: 010501"' + so), nfCampo("servico.nbs", "NBS", so)) +
        nfDuas(nfCampo("servico.aliquota_iss_pct", "Alíquota do ISS (%)", ' inputmode="decimal" placeholder="2,00"' + so), nfCampo("servico.ctribmun", "Código municipal (3 dígitos, se houver)", so)) +
        nfCampo("servico.descricao", "Descrição padrão do serviço", so) +
        nfDuas(nfCampo("ibscbs.cst", "IBS/CBS — CST", so), nfCampo("ibscbs.cclasstrib", "IBS/CBS — cClassTrib", so)) +
        nfDuas(nfCampo("ibscbs.cindop", "IBS/CBS — indicador da operação (cIndOp)", so), nfEscolha("ibscbs.indfinal", "Consumidor final", [["0", "não"], ["1", "sim"]])) +
        nfMarcar("ibscbs.enviar", "Enviar o grupo IBS/CBS na nota") +
        nfDuas(nfCampo("pis_cofins.cst", "PIS/COFINS — CST (se houver retenção)", so), nfCampo("total_tributos.federal_pct", "Tributos aproximados — federal (%)", ' inputmode="decimal"' + so)) +
        nfDuas(nfCampo("total_tributos.estadual_pct", "Tributos aproximados — estadual (%)", ' inputmode="decimal"' + so), nfCampo("total_tributos.municipal_pct", "Tributos aproximados — municipal (%)", ' inputmode="decimal"' + so)) +
        '<p class="nota-campo">O código do serviço, a NBS e a classificação do IBS/CBS do PAVLVS (programa de computador) são do contador.</p>' +
        nfSub("Retenções") + Object.keys(ret).map(function (k) {
          return nfDuas(nfEscolha("retencoes." + k + ".quando", ret[k] + " — quando reter", nfDominio(op.quando_reter)),
            k === "iss" ? "" : nfCampo("retencoes." + k + ".aliquota_pct", ret[k] + " — alíquota (%)", ' inputmode="decimal"' + so));
        }).join("") +
        nfDuas(nfCampo("contador.nome", "Contador", so), nfCampo("contador.email", "E-mail do contador", so)) + nfErro(M) +
        nfSub("Token da Cloudflare") +
        '<p class="nota-campo">Com ele o painel cadastra o certificado na Cloudflare (o mTLS que a Sefin exige) e republica o Worker auxiliar paulus-nfse-mtls. ' + esc(cf.como_criar_token || "") + " Fica guardado cifrado; não volta para a tela.</p>" +
        '<div class="nf-cert"><span class="caixa-campo fundo nf-senha"><input type="password" id="nf-token" data-in="nfTokenCampo" value="' + esc(M.token || "") + '" placeholder="' + (cf.token ? "token gravado · cole outro para trocar" : "cole o token aqui") + '" autocomplete="off" aria-label="Token da Cloudflare"' + so + "></span>" +
        '<button type="button" class="btn-acao" data-a="nfToken"' + (so || M.gravandoToken ? " disabled" : "") + ">" + (M.gravandoToken ? "Gravando…" : "Gravar token") + "</button>" +
        '<span class="num s11 ' + (cf.token ? "c-ok" : "c-atencao") + '">' + (cf.token ? "token gravado" : "sem token") + "</span></div>" +
        (M.tokenMsg ? '<p class="' + (M.tokenOk ? "nf-aviso ok" : "nf-aviso") + '">' + ic(M.tokenOk ? "check" : "warning") + "<span>" + esc(M.tokenMsg) + "</span></p>" : "") +
        nfSub("Produção") +
        (s.producao_liberada
          ? '<p class="nota-campo">Em produção: as notas valem de verdade.</p><div class="nf-botoes"><button type="button" class="btn-acao" data-a="nfProducao" data-v="voltar"' + so + ">Voltar para testes</button></div>"
          : '<p class="nota-campo">Em testes (produção restrita, sem valor fiscal). Só muda depois de ao menos uma nota emitida em testes.</p><div class="nf-botoes"><button type="button" class="btn-acao' + (M.prodConfirma ? " perigo-cheio" : "") + '" data-a="nfProducao" data-v="liberar"' + so + ">" +
            (M.prodConfirma ? "Confirmar: as notas passam a valer de verdade" : "Mudar para produção") + "</button></div>") +
        (M.erroProd ? '<p class="erro-campo">' + esc(M.erroProd) + "</p>" : "") + "</div>" +
        modalPe(so ? "" : '<button type="button" class="btn-acao verde" data-a="nfParamSalvar" id="modal-ok"' + (M.enviando ? " disabled" : "") + ">" + (M.enviando ? "Gravando…" : "Gravar parâmetros") + "</button>");
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
    l.push({ icon: "menu_book", t: "Materiais › Na fila", d: c.materiais != null ? c.materiais + " para ler" : "para ler", ir: function () { U.materiais.filtro = "fila"; irPara("materiais"); } });
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
    ["contas", "escritorios", "tuneis", "planos", "materiais"].forEach(function (k) {
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
    E.tela = id; E.gaveta = null; E.busca.aberta = false;
    if (!E.dentro) return;
    carregarTela();
    render();
    if (mudou) { window.scrollTo(0, 0); var m = $("conteudo"); if (m && document.activeElement && document.activeElement.closest && document.activeElement.closest(".adm-pilulas,.adm-lateral")) { /* fica no menu */ } }
  }

  function abrirConta(id) {
    focoAntes = document.activeElement;
    E.gaveta = { id: id, resumo: contaResumo(id), det: null, erro: "" };
    renderCamada();
    var b = $("gaveta-fechar"); if (b) b.focus();
    var G = E.gaveta;
    api("GET", "/api/admin/contas/" + encodeURIComponent(id)).then(function (d) { if (E.gaveta === G) { G.det = d; renderCamada(); } }, function (e) { if (E.gaveta === G && e.status !== 401) { G.erro = e.message; renderCamada(); } });
  }
  function recarregarGaveta() { if (E.gaveta) { var id = E.gaveta.id; var f = focoAntes; abrirConta(id); focoAntes = f; } }

  /* ================================================================ acoes */

  var A = {};
  var SEG = {
    "tokens.visao": function (v) { U.tokens.visao = v; ler(tokensChave()); },
    "tokens.periodo": function (v) { U.tokens.periodo = v; ler(tokensChave()); },
    "emails.aba": function (v) { U.emails.aba = v; if (v === "nova") U.emails.passo = U.emails.passo || 1; },
    "emails.quando": function (v) { U.emails.camp.quando = v; },
  };
  A.seg = function (el) {
    var n = el.dataset.seg, v = el.dataset.v;
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
  A.contaEmail = function () {
    var c = E.gaveta.det || E.gaveta.resumo; if (!c) return;
    U.emails.so = c; U.emails.camp.publico = "conta:" + c.id; U.emails.aba = "nova"; U.emails.passo = 1;
    irPara("emails");
  };
  A.contaCreditar = function () {
    var c = E.gaveta.det || E.gaveta.resumo; if (!c) return;
    enfileirar("contas", "conta.creditar", c.id, { id: c.id, tokens: 10000000 }, "Creditei 10M tokens de cortesia para " + c.nome);
  };
  A.contaDesvincular = function () {
    var c = E.gaveta.det || E.gaveta.resumo; if (!c) return;
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
  A.tunelAbrir = function (el) { var s = el.dataset.slug; U.tuneis.aberto = U.tuneis.aberto === s ? null : s; render(); };
  A.tunelSel = function (el) { var s = el.dataset.slug; U.tuneis.sel[s] = !U.tuneis.sel[s]; render(); };
  A.tuneisSelParados = function () {
    var ts = (dadosDe("tuneis") || {}).tuneis || [], par = ts.filter(parado);
    var todos = par.length && par.every(function (t) { return U.tuneis.sel[t.slug]; });
    U.tuneis.sel = {}; if (!todos) par.forEach(function (t) { U.tuneis.sel[t.slug] = true; });
    render();
  };
  A.tuneisApagar = async function () {
    var slugs = Object.keys(U.tuneis.sel).filter(function (k) { return U.tuneis.sel[k] && !naFila("tunel.apagar", k); });
    var ok = 0;
    for (var i = 0; i < slugs.length; i++) { if (await enfileirar("tuneis", "tunel.apagar", slugs[i], { slug: slugs[i] }, "Apaguei " + slugs[i], true)) ok++; }
    U.tuneis.sel = {};
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
  A.escolherPublico = function (el) { U.emails.camp.publico = el.dataset.id; render(); };
  A.usarPublico = function (el) { U.emails.camp.publico = el.dataset.id; U.emails.aba = "nova"; U.emails.passo = 2; render(); };
  function dadosCampanha() {
    var c = U.emails.camp, pub = publicoAtual();
    return { nome: c.nome.trim() || c.assunto.trim(), publico: pub ? pub.id : "", assunto: c.assunto, pre: c.pre, titulo: c.titulo, texto: c.texto, botao: c.botao, link: c.link, quando: c.quando };
  }
  A.pedirDisparo = async function () {
    var c = U.emails.camp, pub = publicoAtual();
    if (!c.assunto.trim() || !c.texto.trim()) { toast("Preencha o assunto e o texto antes de pedir o disparo", true); U.emails.passo = 2; render(); return; }
    var dd = dadosCampanha(), n = pub ? pub.n || 0 : 0;
    var q = { agora: "agora", amanha: "amanhã, 9h", segunda: "segunda, 9h" }[c.quando];
    var ok = await enfileirar("emails", "campanha.disparar", dd.nome, dd, 'Pedi o disparo "' + dd.nome + '" para ' + n + (n === 1 ? " conta" : " contas") + " (" + q + ")");
    if (ok) { var keep = { botao: c.botao, link: c.link }; U.emails.camp = novaCamp(); U.emails.camp.botao = keep.botao; U.emails.camp.link = keep.link; U.emails.so = null; U.emails.aba = "campanhas"; U.emails.passo = 1; render(); }
  };
  A.enviarTeste = function () { naHora("POST", "/api/admin/campanhas/teste", { campanha: dadosCampanha() }, "Teste enviado para " + (E.sessao.access && E.sessao.access.email || "você")); };

  // planos
  A.copiarJson = async function () {
    var d = dadosDe("planos"); if (!d) return;
    try { await navigator.clipboard.writeText(d.json || ""); toast("JSON copiado"); } catch (e) { toast("Não consegui copiar: o navegador não deixou", true); }
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
    if (r) { toast("Enviada: a nota está no PAULUS do cliente" + (r.email ? " · e-mail: " + r.email : "")); ler("nfse"); } else el.disabled = false;
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
    var c = (M.clientes || []).filter(function (x) { return x.id === id; })[0];
    NF_TOMADOR.forEach(function (x) { M.v["tomador." + x[0]] = c ? (c.tomador || {})[x[0]] || "" : ""; });
  }
  function nfEscolherPagamento(M, id) {
    M.v.pagamento = id;
    var p = (((dadosDe("nfse") || {}).pagamentos) || []).filter(function (x) { return x.id === id; })[0];
    if (!p) return;
    nfEscolherCliente(M, p.conta || "");
    M.v.valor = Number(p.valor || 0).toLocaleString("pt-BR", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
    // O mesmo texto do emissor (worker/nfse/emissor.js, descricaoDoPagamento).
    M.v.descricao = { mensalidade: "Assinatura do PAULUS — plano mensal", anual: "Assinatura do PAULUS — plano anual",
      "mês avulso": "Assinatura do PAULUS — um mês, sem renovação" }[p.tipo] || "Recarga de uso do PAULUS (nuvem)";
    if (String(p.quando || "").length >= 7) M.v.competencia = String(p.quando).slice(0, 7);
  }
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
    if (M.editando === id) { M.editando = null; renderCamada(); return; }
    var c = (M.clientes || []).filter(function (x) { return x.id === id; })[0]; if (!c) return;
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
      M.clientes = (M.clientes || []).map(function (x) { return x.id === id ? c : x; });
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
  function abrirModal(m) {
    if (!E.modal) focoAntes = document.activeElement;
    E.modal = m; renderCamada();
    var alvo = document.querySelector(".modal input") || $("modal-ok") || document.querySelector(".modal button");
    if (alvo) alvo.focus();
  }
  function fecharModal() { E.modal = null; renderCamada(); devolverFoco(); }

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
    planoTokens: function (el) { E.modal.tokens = el.value; renderCamada(); },
    planoAnual: function (el) { E.modal.anual = el.value; renderCamada(); },
    commitTexto: function (el) { E.modal.texto = el.value; E.modal.erro = ""; renderCamada(); },
    buscaQ: function (el) { E.busca.q = el.value; E.busca.idx = 0; buscar(); renderCamada(); },
    // notas fiscais: os campos dos pop-ups guardam o valor sem redesenhar
    nf: function (el) { if (E.modal && E.modal.v) E.modal.v[el.dataset.k] = el.type === "checkbox" ? el.checked : el.value; },
    nfMun: function (el) { nfMunDigitar(el); },
    nfCliente: function (el) { nfEscolherCliente(E.modal, el.value); renderCamada(); },
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
    if (el && IN[el.dataset.in]) IN[el.dataset.in](el, ev);
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
      var caixa = document.querySelector("#camada .busca") || document.querySelector("#camada .modal") || document.querySelector("#camada .gaveta");
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

  var GITHUB_SVG = '<svg width="15" height="15" viewBox="0 0 16 16" fill="currentColor" aria-hidden="true"><path d="M8 0C3.58 0 0 3.58 0 8c0 3.54 2.29 6.53 5.47 7.59.4.07.55-.17.55-.38 0-.19-.01-.82-.01-1.49-2.01.37-2.53-.49-2.69-.94-.09-.23-.48-.94-.82-1.13-.28-.15-.68-.52-.01-.53.63-.01 1.08.58 1.23.82.72 1.21 1.87.87 2.33.66.07-.52.28-.87.51-1.07-1.78-.2-3.64-.89-3.64-3.95 0-.87.31-1.59.82-2.15-.08-.2-.36-1.02.08-2.12 0 0 .67-.21 2.2.82.64-.18 1.32-.27 2-.27.68 0 1.36.09 2 .27 1.53-1.04 2.2-.82 2.2-.82.44 1.1.16 1.92.08 2.12.51.56.82 1.27.82 2.15 0 3.07-1.87 3.75-3.65 3.95.29.25.54.73.54 1.48 0 1.07-.01 1.93-.01 2.2 0 .21.15.46.55.38A8.01 8.01 0 0 0 16 8c0-4.42-3.58-8-8-8z"/></svg>';

  function renderEntrada(erroLeitura) {
    var s = E.sessao || {}, acc = !!(s.access && s.access.ok), gh = !!(s.github && s.github.ok);
    var nome = primeiro(s.nome), sd = saudacaoHora();
    var saud = gh && acc ? sd + (nome ? ", " + nome : "") + ". Tudo pronto." : acc ? sd + (nome ? ", " + nome : "") + ". Falta o GitHub." : sd + ". Bem‑vindo de volta.";
    var cA = cfg("access"), cG = cfg("github");
    var h = '<div class="entrada-marca"><h1 class="saudacao">' + esc(saud) + '</h1><p class="sub">Administração do PAVLVS. Duas portas, nenhuma senha.</p></div><div class="campos" style="gap:18px">';
    if (erroLeitura) h += '<p class="erro-campo">Não consegui conferir a sessão: ' + esc(erroLeitura) + "</p>";
    if (E.erroVolta) h += '<p class="erro-campo" role="alert">' + esc(E.erroVolta) + "</p>";
    // passo 1
    h += '<div class="passo">' +
      '<div class="selo"><span class="selo-esq"><span class="selo-icone' + (acc ? "" : " neutro") + '">' + ic(acc ? "check" : "shield") + "</span><span>" + esc(acc ? s.access.email : "Entrada pelo e-mail da equipe") + '</span></span><span class="selo-dir"><b>PAULUS.IA.BR/ADMIN</b><span>verificação do Cloudflare</span></span></div>';
    if (!acc) h += '<button type="button" class="btn-duplo largo" data-a="recarregar"' + attrDis(desligado(cA), cA.falta) + "><span>" + ic("shield") + "Entrar pelo Cloudflare Access</span></button>" + (desligado(cA) ? '<p class="erro-campo">' + esc(cA.falta) + "</p>" : "");
    h += '<span class="nota-campo">O Access confere o seu e-mail com um código de uso único antes de a página carregar. Só quem está na lista da equipe chega aqui.</span></div>';
    // passo 2
    h += '<div class="passo' + (acc ? "" : " depois") + '">' +
      '<div class="selo"><span class="selo-esq"><span class="selo-icone' + (gh ? "" : " neutro") + '">' + ic(gh ? "check" : "lock") + "</span><span>" + esc(gh ? s.github.login : "Login social do GitHub") + '</span></span><span class="selo-dir"><b>GITHUB</b><span>coryphaeus · colaborador</span></span></div>';
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
    $("selo-email").textContent = (s.access && s.access.email) || "";
    $("selo-papel").textContent = s.papel || "";
    $("selo-sessao").title = "Cloudflare Access · " + ((s.access && s.access.email) || "") + " · " + (PAPEL_NOME[s.papel] || s.papel || "") + (s.github && s.github.login ? " · GitHub " + s.github.login : "");
    $("versao-worker").textContent = "worker " + (s.worker ? "v" + String(s.worker).replace(/^v/, "") : "—");
    try { if (!/Mac|iPhone|iPad/.test(navigator.platform || navigator.userAgent)) $("tecla-mod").textContent = "Ctrl"; } catch (e) { /* nada */ }
    var id = location.hash.replace(/^#/, "");
    E.tela = TELA[id] ? id : "visao";
    if (!TELA[id]) history.replaceState(null, "", "#visao");
    // As contagens da navegacao e das acoes rapidas: le em segundo plano.
    ["alteracoes", "tuneis", "renovacoes", "materiais", "nfse"].forEach(function (ch) { ler(ch); });
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
