/* Minha conta (paulus.ia.br/minha-conta/): o titular da assinatura - e quem ele autorizar - ve o plano e o
   consumo e cuida do cadastro, do escritorio, das pessoas e do Google. Entra com a Conta Atos
   (assets/entrar-atos.js). O dinheiro (a assinatura, as faturas, o cartao) fica na Conta Atos, que e quem cobra o
   PAVLVS: a tela leva la (os links vem em d.atos).
   Desenho: a topbar do site, o titulo centrado e as abas na pilula (como a pagina da conta no Admin).
   O servidor e o worker/conta.js: GET /api/conta traz tudo, cada acao e um POST da propria origem e o
   papel (titular ou financeiro) e conferido la. */
(function () {
  "use strict";
  var S = { aba: "resumo", d: null, modal: null, periodo: "ciclo", anual: null, convite: "", erroEntrar: "" };
  var ABAS = [["resumo", "Resumo"], ["consumo", "Consumo"], ["plano", "Plano"], ["cadastro", "Cadastro"], ["escritorio", "Escritório"], ["pessoas", "Pessoas"]];
  var DO_FINANCEIRO = { resumo: 1, consumo: 1 };
  var MESES = ["jan", "fev", "mar", "abr", "mai", "jun", "jul", "ago", "set", "out", "nov", "dez"];

  function $(id) { return document.getElementById(id); }
  function esc(s) { return String(s == null ? "" : s).replace(/[&<>"']/g, function (c) { return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]; }); }
  function ic(n) { return '<span class="icon" aria-hidden="true">' + n + "</span>"; }
  function brl(v) { return Number(v || 0).toLocaleString("pt-BR", { style: "currency", currency: "BRL" }); }
  function brl0(v) { return Number(v || 0).toLocaleString("pt-BR", { style: "currency", currency: "BRL", maximumFractionDigits: 0 }); }
  function tok(n) { var m = Number(n || 0) / 1e6; return (m >= 10 ? Math.round(m) : Math.round(m * 10) / 10).toLocaleString("pt-BR") + " M"; }
  function dt(iso) { if (!iso) return "—"; var p = String(iso).slice(0, 10).split("-"); return p[2] + "/" + p[1] + "/" + p[0]; }
  function dtHora(iso) { var t = new Date(iso); if (isNaN(t)) return "—"; return t.toLocaleDateString("pt-BR") + ", " + t.toLocaleTimeString("pt-BR", { hour: "2-digit", minute: "2-digit" }); }
  function mesAno(iso) { if (!iso) return "—"; var p = String(iso).slice(0, 10).split("-"); return MESES[Number(p[1]) - 1] + "/" + p[0]; }
  function diasAte(iso) { var a = new Date(); a.setHours(0, 0, 0, 0); return Math.round((new Date(String(iso).slice(0, 10) + "T00:00") - a) / 864e5); }
  function iniciais(n) { var p = String(n || "").trim().split(/\s+/).filter(Boolean); return p.length ? (p.length > 1 ? p[0][0] + p[p.length - 1][0] : p[0].slice(0, 2)).toUpperCase() : "?"; }
  // As frases do servidor vem em minusculas (servem no meio de outra frase); sozinhas, com a primeira maiuscula.
  function cap(t) { t = String(t || ""); return t.charAt(0).toUpperCase() + t.slice(1); }
  function L(pt, en) { return window.MC_IDIOMA === "en" ? en : pt; }
  function titular() { return S.d && S.d.perfil.papel === "titular"; }
  function abas() { return ABAS.filter(function (a) { return titular() || DO_FINANCEIRO[a[0]]; }); }
  var FORA = ' target="_blank" rel="noopener"';

  function painel(rot, dir, miolo, cls) {
    return '<section class="painel mc-painel' + (cls ? " " + cls : "") + '"><div class="painel-cab"><span class="rotulo">' + esc(rot) + "</span>" + (dir ? "<span>" + dir + "</span>" : "") + "</div>" + miolo + "</section>";
  }
  function pilula(nome, ops, atual) {
    return '<div class="segmentos mc-seg"><div role="tablist">' + ops.map(function (o) {
      return '<button type="button" role="tab" data-seg="' + nome + '" data-v="' + o[0] + '" aria-pressed="' + (o[0] === atual) + '" aria-selected="' + (o[0] === atual) + '">' + esc(o[1]) + "</button>";
    }).join("") + "</div></div>";
  }
  function api(metodo, caminho, corpo) {
    return fetch(caminho, { method: metodo, credentials: "same-origin", headers: corpo ? { "Content-Type": "application/json" } : {}, body: corpo ? JSON.stringify(corpo) : undefined })
      .then(function (r) {
        return r.json().catch(function () { return {}; }).then(function (j) {
          if (!r.ok) { var e = new Error(j.erro || "não foi possível agora"); e.status = r.status; e.dados = j; throw e; }
          return j;
        });
      });
  }
  function toast(t, erro) {
    var el = $("mc-toast"); if (!el) { el = document.createElement("div"); el.id = "mc-toast"; el.className = "mc-toast"; el.setAttribute("role", "status"); document.body.appendChild(el); }
    el.textContent = cap(t); el.classList.toggle("erro", !!erro); el.classList.add("on");
    clearTimeout(toast.t); toast.t = setTimeout(function () { el.classList.remove("on"); }, erro ? 5200 : 3200);
  }
  /* ------------------------------------------------------------ as abas */
  var TELAS = {};
  var SIT = { nenhuma: ["Sem assinatura", "mudo"], ativa: ["Ativa", "ok"], cortesia: ["Cortesia", "ok"], cancelada: ["Cancelada", "atencao"], vencida: ["Vencida", "erro"], pausada: ["Pausada no Mercado Pago", "atencao"], pendente: ["Esperando o Mercado Pago", "atencao"] };
  /* O resumo: o plano e o uso daqui; a assinatura, as faturas e o cartao, na Conta Atos. */
  TELAS.resumo = function (d) {
    var a = d.assinatura, c = a.ciclo, s = SIT[a.situacao] || [a.situacao, "mudo"], tem = a.situacao !== "nenhuma" && a.situacao !== "vencida";
    var assin = '<div class="mc-corpo">' + (tem ? '<div class="mc-plano-nome"><h2>' + esc(a.nome) + '</h2><span class="mc-tag">' + (a.periodo === "anual" ? "anual" : "mensal") + "</span></div>" : "") +
      '<dl class="mc-fatos"><div><dt>Situação</dt><dd><span class="mc-bolinha ' + s[1] + '"></span>' + esc(s[0]) + "</dd></div>" +
      (tem && c.ate ? "<div><dt>" + (a.situacao === "cancelada" ? "Vale até" : "Ciclo até") + "</dt><dd>" + dt(c.ate) + "</dd></div>" : "") +
      "<div><dt>Cobrança</dt><dd>" + (a.situacao === "cortesia" ? "sem cobrança" : "pela Conta Atos") + "</dd></div></dl>" +
      (tem ? "" : '<p class="mc-p">' + (a.situacao === "vencida" ? "O plano venceu. " : "") + "Sem a assinatura, o Paulus abre com todos os arquivos, sem a IA. Escolha um plano na aba Plano.</p>") + "</div>" +
      '<div class="mc-pe">' + (titular() ? '<button type="button" class="mini" data-aba="plano">' + (tem ? "Ver os planos" : "Assinar") + "</button>" : "") +
      (a.situacao === "cortesia" ? "" : '<a class="mini" href="' + esc(d.atos.assinaturas) + '"' + FORA + ">Conta Atos" + ic("arrow_outward") + "</a>") + "</div>";
    var uso;
    if (!c.tokens || !tem) {
      uso = '<div class="mc-corpo"><p class="mc-p">Não há um ciclo aberto agora.</p></div>';
    } else {
      var pct = Math.min(100, Math.round(c.usados / c.tokens * 100)), resta = Math.max(0, c.tokens - c.usados), dias = diasAte(c.ate);
      uso = '<div class="mc-corpo"><div class="mc-uso-num"><b>' + pct + '%</b><span>' + tok(c.usados) + " de " + tok(c.tokens) + " tokens</span></div>" +
        '<span class="mc-barra" role="progressbar" aria-valuenow="' + pct + '" aria-valuemin="0" aria-valuemax="100"><i style="width:' + pct + '%"></i></span>' +
        '<dl class="mc-fatos"><div><dt>Restam</dt><dd>' + tok(resta) + " tokens</dd></div>" +
        "<div><dt>Novo ciclo em</dt><dd>" + dt(c.ate) + " · " + dias + (dias === 1 ? " dia" : " dias") + "</dd></div>" +
        (c.extra ? "<div><dt>Créditos de recarga</dt><dd>" + tok(c.extra) + " tokens · não vencem na renovação</dd></div>" : "") + "</dl></div>";
    }
    uso += '<div class="mc-pe"><button type="button" class="mini" data-aba="consumo">Ver consumo</button>' +
      (tem && a.situacao !== "cortesia" ? '<a class="mini" href="' + esc(d.atos.recarga) + '">Comprar créditos</a>' : "") + "</div>";
    var pag = '<div class="mc-corpo"><p class="mc-p">A assinatura, as faturas e o cartão ficam na sua Conta Atos, que é quem cobra o PAVLVS. Lá você troca o plano, pausa, cancela e vê os pagamentos.</p></div>' +
      '<div class="mc-pe"><a class="mini" href="' + esc(d.atos.faturamento) + '"' + FORA + ">Ver as faturas" + ic("arrow_outward") + "</a></div>";
    return '<div class="mc-grade2">' + painel("Assinatura", "", assin) + painel("Uso do ciclo", tem && c.de ? dt(c.de).slice(0, 5) + " – " + dt(c.ate).slice(0, 5) : "", uso) + "</div>" +
      painel("Pagamentos", "", pag);
  };

  TELAS.consumo = function (d) {
    var k = d.consumo, dias = k.dias || [];
    var mm = mesesAssinatura(d, false), rotEsc = S.cicloEsc ? MESES[Number(S.cicloEsc.slice(5)) - 1] + "/" + S.cicloEsc.slice(0, 4) : "";
    var pop = S.calAberto && S.calAberto.alvo === "consumo" ? calPop(mm[0], mm[1], S.cicloEsc) : "";
    var outro = [["ciclo", "Este ciclo"], ["anterior", "Ciclo anterior"], ["outro", S.periodo === "outro" && rotEsc ? "Ciclo de " + rotEsc : "Outro ciclo"]];
    var seletor = '<span class="mc-periodo">' + pilula("periodo", outro, S.periodo) + pop + "</span>";
    if (!dias.length) return painel("Por dia", seletor, '<p class="mc-vazio">Não há consumo para mostrar neste período.</p>', "mc-com-pop");
    var ritmo = d.assinatura.ciclo.tokens ? d.assinatura.ciclo.tokens / dias.length : 0;
    var maior = Math.max.apply(null, dias.map(function (x) { return x.tokens; }).concat([1])), max = Math.max(maior, ritmo) * 1.1;
    var total = dias.reduce(function (s, x) { return s + x.tokens; }, 0);
    // Uma barra por dia; a linha tracejada e o ritmo da cota (o que da para usar por dia sem faltar no fim do ciclo).
    var barras = '<p class="mc-legenda"><span><i class="mc-leg-barra"></i>tokens usados no dia</span>' + (ritmo ? '<span><i class="mc-leg-linha"></i>ritmo da cota: ' + tok(ritmo) + " por dia</span>" : "") + '<span><i class="mc-leg-futuro"></i>dias que ainda não chegaram</span></p>' +
      '<div class="mc-grafico-area">' + (ritmo ? '<span class="mc-ritmo" style="bottom:' + (ritmo / max * 100) + '%"></span>' : "") + '<div class="mc-grafico" role="img" aria-label="Tokens por dia no ciclo">' + dias.map(function (x) {
        var h = x.tokens ? Math.max(3, Math.round(x.tokens / max * 100)) : 0;
        return '<span class="mc-dia' + (x.futuro ? " futuro" : "") + '" title="' + dt(x.data) + (x.futuro ? "" : " · " + tok(x.tokens) + " tokens") + '"><i style="height:' + h + '%"></i></span>';
      }).join("") + '</div></div><div class="mc-grafico-eixo"><span>' + dt(dias[0].data).slice(0, 5) + "</span><span>" + dt(dias[dias.length - 1].data).slice(0, 5) + "</span></div>";
    var feitos = dias.filter(function (x) { return !x.futuro; });
    var media = feitos.length ? total / feitos.length : 0;
    var graf = '<div class="mc-corpo">' + barras + '<dl class="mc-fatos linha"><div><dt>No ciclo</dt><dd>' + tok(total) + " tokens</dd></div><div><dt>Média por dia</dt><dd>" + tok(media) + "</dd></div><div><dt>Maior dia</dt><dd>" + tok(maior) + "</dd></div></dl>" +
      (k.sem_dias ? '<p class="mc-nota">Este ciclo é de antes do registro dia a dia: no total, foram ' + tok(k.total_do_mes) + " tokens.</p>" : "") + "</div>";
    var ps = (k.pessoas || []).slice().sort(function (a, b) { return b.tokens - a.tokens; });
    var pessoas = ps.length ? ps.map(function (p) {
      var pc = total ? Math.round(p.tokens / total * 100) : 0;
      return '<div class="mc-linha"><span class="mc-avatar">' + esc(iniciais(p.nome)) + '</span><span class="mc-txt"><b>' + esc(p.nome) + "</b><small>" + esc(p.email) + '</small></span><span class="mc-uso-pessoa"><span class="mc-barra fina"><i style="width:' + pc + '%"></i></span></span><span class="mc-num">' + tok(p.tokens) + '</span><span class="mc-num mudo">' + pc + "%</span></div>";
    }).join("") : '<p class="mc-vazio">Quem perguntou fica no Paulus do escritório: a nuvem recebe só o total de cada dia, sem saber de quem foi a pergunta.</p>';
    return painel("Por dia · " + dt(k.de).slice(0, 5) + " – " + dt(k.ate).slice(0, 5), seletor, graf, "mc-com-pop") +
      painel("Por pessoa", ps.length ? ps.length + (ps.length === 1 ? " pessoa" : " pessoas") : "", pessoas);
  };

  // O calendario do Admin (vistas de meses e de anos), para escolher um mes entre primeiro e ultimo (contados em meses).
  function calPop(primeiro, ultimo, escolhido) {
    var C = S.calAberto, ano = C.ano, anos = C.vista === "anos", ano0 = ano - (ano % 12);
    var h = '<div class="calendario-adm mc-cal" role="dialog" aria-label="Escolher o mês"><div class="cal-topo">' +
      '<button type="button" class="btn-icone" data-a="calAnoPasso" data-v="-1" aria-label="Anterior">' + ic("chevron_left") + "</button>" +
      '<button type="button" class="cal-titulo" data-a="calVistaAnos"' + (anos ? " disabled" : "") + ">" + (anos ? ano0 + " – " + (ano0 + 11) : ano) + "</button>" +
      '<button type="button" class="btn-icone" data-a="calAnoPasso" data-v="1" aria-label="Próximo">' + ic("chevron_right") + "</button></div>";
    if (anos) {
      h += '<div class="cal-grade meses">';
      for (var y = ano0; y < ano0 + 12; y++) { var temY = y * 12 + 11 >= primeiro && y * 12 <= ultimo; h += '<button type="button" class="cal-celula' + (y === ano ? " escolhido" : "") + '" data-a="calAno" data-v="' + y + '"' + (temY ? "" : " disabled") + ">" + y + "</button>"; }
      h += "</div>";
    } else {
      h += '<div class="cal-grade meses">' + MESES.map(function (nm, k) {
        var idx = ano * 12 + k, livre = idx >= primeiro && idx <= ultimo, v = ano + "-" + String(k + 1).padStart(2, "0");
        return '<button type="button" class="cal-celula' + (v === escolhido ? " escolhido" : "") + '" data-a="calMes" data-v="' + v + '"' + (livre ? "" : ' disabled title="sem assinatura neste mês"') + ">" + nm + "</button>";
      }).join("") + "</div>";
    }
    return h + "</div>";
  }
  // Os meses com assinatura: do inicio ate o ciclo atual (faturas) ou ate o de antes do anterior (consumo).
  function mesesAssinatura(d, ateAtual) {
    var a = d.assinatura, hoje = new Date();
    var ini = new Date((a.desde || a.ciclo.de || hoje.toISOString().slice(0, 10)) + "T12:00"), at = new Date((a.ciclo.de || hoje.toISOString().slice(0, 10)) + "T12:00");
    return [ini.getFullYear() * 12 + ini.getMonth(), at.getFullYear() * 12 + at.getMonth() - (ateAtual ? 0 : 2)];
  }
  /* Os planos: assinar leva ao checkout da Atos; com o plano em dia, mudar de plano e cancelar e na Conta Atos
     (la a regra de nao cobrar em dobro diz como). */
  TELAS.plano = function (d) {
    var a = d.assinatura, per = S.anual ? "anual" : "mensal", tem = a.situacao !== "nenhuma" && a.situacao !== "vencida";
    var cards = d.planos.map(function (p) {
      var atual = tem && p.id === a.plano, preco = S.anual ? p.valor_anual : p.valor;
      var acao = atual ? '<span class="mc-plano-pe mudo">É o que você tem hoje</span>'
        : !tem || a.situacao === "cancelada" ? '<a class="mini cheia" href="' + esc(d.atos.checkout[p.id] ? d.atos.checkout[p.id][per] : d.atos.assinaturas) + '">Assinar este</a>' : "";
      return '<div class="mc-plano' + (atual ? " atual" : "") + '"><div class="mc-plano-topo"><b>' + esc(p.nome) + "</b>" + (atual ? '<span class="mc-tag">plano atual</span>' : "") + "</div>" +
        '<div class="mc-preco"><span>' + brl0(preco) + "</span><small>" + (S.anual ? "por ano" : "por mês") + "</small></div>" +
        (S.anual ? '<small class="mc-economia">' + Math.round((1 - p.valor_anual / (p.valor * 12)) * 100) + "% a menos que 12 meses</small>" : "") +
        '<ul class="mc-itens"><li>' + tok(p.tokens) + " tokens por mês</li><li>" + (p.pessoas === 1 ? "1 pessoa" : "até " + p.pessoas + " pessoas") + "</li><li>" + esc((p.modelos_info || []).map(function (m) { return m.nome; }).join(" e ")) + "</li></ul>" +
        acao + "</div>";
    }).join("");
    var pe = a.situacao === "cortesia" ? '<div class="mc-cancelar"><span>O plano de cortesia não tem cobrança. Para mudar de plano, escreva para contato@paulus.ia.br.</span></div>'
      : tem && a.situacao !== "cancelada" ? '<div class="mc-cancelar"><span>Mudar de plano, pausar e cancelar são na Conta Atos, que é quem cobra.</span><a class="mini" href="' + esc(d.atos.assinaturas) + '"' + FORA + ">Abrir a Conta Atos" + ic("arrow_outward") + "</a></div>"
        : '<div class="mc-cancelar"><span>O pagamento é na Atos, com cartão ou Pix. O plano entra assim que o pagamento é aprovado, sem reinstalar.</span></div>';
    return '<div class="mc-centro">' + pilula("periodoPlano", [["mensal", "Mensal"], ["anual", "Anual"]], per) + "</div>" + '<div class="mc-planos">' + cards + "</div>" + pe;
  };

  var UFS = "AC AL AP AM BA CE DF ES GO MA MT MS MG PA PB PR PE PI RJ RN RS RO RR SC SP SE TO".split(" ");
  // As mascaras do cadastro: o servidor fica so com os digitos.
  function digitos(t) { return String(t || "").replace(/\D/g, ""); }
  function mascararDocumento(t) {
    var d = digitos(t).slice(0, 14);
    if (d.length <= 11) return d.replace(/^(\d{3})(\d)/, "$1.$2").replace(/^(\d{3})\.(\d{3})(\d)/, "$1.$2.$3").replace(/\.(\d{3})(\d{1,2})$/, ".$1-$2");
    return d.replace(/^(\d{2})(\d)/, "$1.$2").replace(/^(\d{2})\.(\d{3})(\d)/, "$1.$2.$3").replace(/\.(\d{3})(\d)/, ".$1/$2").replace(/(\d{4})(\d{1,2})$/, "$1-$2");
  }
  function mascararTelefone(t) {
    var d = digitos(t).slice(0, 11);
    if (d.length < 3) return d;
    return "(" + d.slice(0, 2) + ") " + (d.length > 10 ? d.slice(2, 7) + "-" + d.slice(7) : d.slice(2, 6) + (d.length > 6 ? "-" + d.slice(6) : ""));
  }
  function mascararCep(t) { var d = digitos(t).slice(0, 8); return d.length > 5 ? d.slice(0, 5) + "-" + d.slice(5) : d; }
  var MASCARAS = { documento: mascararDocumento, telefone: mascararTelefone, cep: mascararCep };
  // O que veio do servidor so ganha a mascara se couber nela: um valor fora do tamanho fica como esta, sem perder digito.
  var MAXIMO = { documento: 14, telefone: 11, cep: 8 };
  function comMascara(k, v) { v = v || ""; return MASCARAS[k] && digitos(v).length <= MAXIMO[k] ? MASCARAS[k](v) : v; }
  /* Aplica a mascara enquanto digita, sem jogar o cursor para o fim no meio do campo. */
  function mascarar(el) {
    var f = MASCARAS[el.dataset.cad]; if (!f) return;
    var antes = el.value, pos = el.selectionStart, digAntes = digitos(antes.slice(0, pos)).length;
    var novo = f(antes); if (novo === antes) return;
    el.value = novo;
    var i = 0, n = 0; while (i < novo.length && n < digAntes) { if (/\d/.test(novo[i])) n++; i++; }
    try { el.setSelectionRange(i, i); } catch (e) { /* campo sem cursor */ }
  }
  /* O estado de cada campo (regra do dono, 08/10/2026): errado = borda vermelha, certo = verde, sem texto na
     tela (PvCampos, em site.js). As regras sao as do servidor (worker/ia.js, conferirCadastro, e worker/conta.js). */
  var P = window.PvCampos;
  var CAD = ["nome", "documento", "oab", "telefone", "email_cobranca", "cep", "logradouro", "numero", "bairro", "cidade", "uf"].map(function (k) { return "mc-cad-" + k; });
  if (P) P.regras({
    "mc-cad-nome": P.regra(function (v) { return v.length >= 2 && v.length <= 80; }, L("diga o nome do escritório (ou o seu, se trabalha sozinho)", "type the office name (or yours, if you work alone)")),
    "mc-cad-documento": P.regra("cpfCnpj", L("o CPF ou CNPJ não confere", "the CPF or CNPJ doesn't check out")),
    "mc-cad-oab": P.regra("preenchido", L("falta o número da OAB, do RG ou da CNH", "the OAB, ID or driver's license number is missing")),
    "mc-cad-telefone": P.regra("telefone", L("o telefone precisa do DDD", "the phone needs the area code")),
    "mc-cad-email_cobranca": P.regra("email", L("o e-mail das faturas não confere", "the invoice email doesn't check out"), true),
    "mc-cad-cep": P.regra("cep", L("o CEP tem 8 dígitos", "the postal code has 8 digits")),
    "mc-cad-logradouro": P.regra(function (v) { return v.length >= 2; }, L("diga a rua do endereço", "type the street")),
    "mc-cad-numero": P.regra("preenchido", L("diga o número do endereço (ou S/N)", "type the street number (or S/N)")),
    "mc-cad-bairro": P.regra("preenchido", L("diga o bairro do endereço", "type the district")),
    "mc-cad-cidade": P.regra(function (v) { return v.length >= 2; }, L("diga a cidade do endereço", "type the city")),
    "mc-cad-uf": P.regra("uf", L("a UF tem 2 letras (ex.: PA)", "pick the state")),
    "mc-conv": P.regra("email", L("o e-mail não confere", "the email doesn't check out")),
    "mc-k-nome": P.regra(function (v) { return v.length >= 3; }, L("diga o nome impresso no cartão", "type the name printed on the card")),
    "mc-k-doc": P.regra("cpfCnpj", L("o CPF ou CNPJ do titular do cartão não confere", "the cardholder's CPF or CNPJ doesn't check out")),
  });
  // A frase do servidor que aponta um campo: ele fica vermelho e o aviso nao aparece.
  var CAD_DO_CAMPO = [[/CPF ou CNPJ/, "mc-cad-documento"], [/nome do escritório/, "mc-cad-nome"], [/telefone/, "mc-cad-telefone"], [/OAB, do RG ou da CNH/, "mc-cad-oab"],
    [/e-mail das faturas/, "mc-cad-email_cobranca"], [/^o CEP/, "mc-cad-cep"], [/rua do endereço/, "mc-cad-logradouro"], [/número do endereço/, "mc-cad-numero"],
    [/bairro do endereço/, "mc-cad-bairro"], [/cidade do endereço|código do município/, "mc-cad-cidade"], [/^a UF/, "mc-cad-uf"],
    [/^preencha o endereço/, ["mc-cad-cep", "mc-cad-logradouro", "mc-cad-numero", "mc-cad-bairro", "mc-cad-cidade", "mc-cad-uf"]]];
  function erroDeCampo(e, pares) { return Boolean(P && e && (e.status === 400 || e.status === 409) && P.porFrase(e.message, pares, { frase: L(e.message, e.message) })); }
  TELAS.cadastro = function (d) {
    var c = d.cadastro;
    var campo = function (k, rot, extra, cls) { return '<label class="campo-site' + (cls ? " " + cls : "") + '"><span>' + rot + '</span><span class="caixa-campo"><input id="mc-cad-' + k + '" data-cad="' + k + '" value="' + esc(comMascara(k, c[k])) + '"' + (extra || "") + "></span></label>"; };
    var corpo = '<div class="mc-corpo mc-form">' +
      '<div class="mc-form-grade">' + campo("nome", "Nome ou razão social", "", "largo") + campo("documento", "CPF ou CNPJ", ' inputmode="numeric" maxlength="18" data-a-in="mascarar" placeholder="000.000.000-00"') + campo("oab", "OAB") + campo("telefone", "Telefone", ' inputmode="tel" maxlength="15" data-a-in="mascarar" placeholder="(91) 90000-0000"') + campo("email_cobranca", "E-mail das faturas", ' type="email"') + "</div>" +
      '<span class="rotulo mc-sub">Endereço</span>' +
      '<div class="mc-form-grade">' + campo("cep", "CEP", ' inputmode="numeric" maxlength="9" data-a-in="cep" placeholder="00000-000"') + campo("logradouro", "Logradouro", "", "largo") + campo("numero", "Número") + campo("complemento", "Complemento") + campo("bairro", "Bairro") + campo("cidade", "Cidade", ' data-a-in="semCmun"') +
      '<label class="campo-site"><span>UF</span><span class="caixa-campo"><select id="mc-cad-uf" data-cad="uf" data-a-in="semCmun">' + (c.uf ? "" : '<option value="" selected>—</option>') + UFS.map(function (u) { return "<option" + (u === c.uf ? " selected" : "") + ">" + u + "</option>"; }).join("") + "</select>" + ic("expand_more") + "</span></label></div>" +
      '<p class="mc-nota" id="mc-cep-nota" hidden></p></div>' +
      '<div class="mc-pe"><span class="mc-nota">Os dados do escritório no Paulus. Os da nota fiscal ficam na Conta Atos.</span><button type="button" class="btn-duplo pequeno" data-a="salvarCadastro"><span>Salvar</span></button></div>';
    return painel("Dados do cadastro", "", corpo);
  };

  TELAS.escritorio = function (d) {
    var e = d.escritorio, end;
    if (!e) {
      end = '<div class="mc-corpo"><p class="mc-p">Este escritório ainda não tem endereço. Ele nasce no Paulus do escritório, em Configurações › Acesso externo; depois de ligado, aparece aqui.</p></div>';
    } else {
      var no = e.ativo !== false && e.online, sitE = e.ativo === false ? "desligado" : e.online ? "no ar" : "fora do ar";
      end = '<div class="mc-corpo"><div class="mc-endereco"><img class="mc-cf" src="' + MP_IMG + 'cloudflare.svg" alt="Cloudflare" width="24" height="24"><span class="mc-bolinha ' + (no ? "ok" : "erro") + '"></span><b class="mono">' + esc(e.slug) + '<span class="mudo">.paulus.ia.br</span></b><span class="mc-sit ' + (no ? "ok" : "erro") + '">' + sitE + "</span></div>" +
        '<p class="mc-p">É por este endereço que a equipe e os clientes entram no Paulus do escritório, pelo túnel do Cloudflare.</p></div>' +
        '<div class="mc-pe"><a class="mini" href="https://' + esc(e.slug) + '.paulus.ia.br" target="_blank" rel="noopener">' + ic("arrow_outward") + "Abrir</a>" + '<button type="button" class="mini" data-a="alterarEndereco">' + ic("edit") + "Alterar endereço</button></div>";
    }
    var inst = d.instalacoes.length ? d.instalacoes.map(function (i) {
      return '<div class="mc-linha"><span class="mc-linha-ic">' + ic("computer") + '</span><span class="mc-txt"><b>' + esc(i.nome) + (i.principal ? ' <span class="mc-tag">principal</span>' : "") + "</b><small>versão " + esc(i.versao) + " · último acesso " + esc(i.ultimo) + "</small></span>" +
        (i.principal ? "" : '<button type="button" class="btn-icone" data-a="removerInstalacao" data-id="' + esc(i.id) + '" aria-label="Tirar ' + esc(i.nome) + '" title="Tirar este computador">' + ic("delete") + "</button>") + "</div>";
    }).join("") : '<p class="mc-vazio">Nenhum computador entrou com esta conta no Paulus ainda.</p>';
    return painel("Endereço do escritório", "", end) + '<div class="mc-grade2">' + painel("Instalações", d.instalacoes.length + (d.instalacoes.length === 1 ? " computador" : " computadores"), inst) + painel("Permissões Google", "", googleHtml(d)) + "</div>";
  };

  // O mesmo card das Permissoes do Google do Admin: a conta e uma linha por servico, com a marca. O estado e o
  // que o Paulus do escritorio contou a nuvem; a ordem nova (ligar, desligar, desvincular) vale quando ele a
  // recebe - ele e quem guarda a permissao do Google, a nuvem nao.
  function googleHtml(d) {
    var g = d.google, lig = {}, pend = g.pendente;
    if (pend) (pend.ligados || []).forEach(function (e) { ESC_G.forEach(function (x) { if (String(e).indexOf(x[1]) >= 0) lig[x[0]] = true; }); });
    else g.servicos.forEach(function (s) { lig[s.id] = !!s.ligado; });
    var mexe = titular() && (g.informado || pend);
    var linhaG = function (id, marca, nome, desc, junto) {
      var on = !!lig[id], ativo = mexe && !junto;
      var dentro = '<span class="lb-ic">' + SIMB_G[marca] + '</span><span class="lb-nome">' + esc(nome) + '</span><span class="lb-desc">' + esc(desc) + '</span><span class="lb-chave' + (on ? " on" : "") + '"></span>';
      if (junto) return '<div class="lb-escopo junto" aria-disabled="true" title="Vem com a Agenda: a mesma permissão">' + dentro + "</div>";
      return '<button type="button" class="lb-escopo" role="switch" aria-checked="' + on + '" aria-label="' + esc(nome + ", " + desc) + '"' + (ativo ? ' data-a="servico" data-id="' + id + '"' : ' aria-disabled="true"') + ">" + dentro + "</button>";
    };
    var estado = pend ? '<p class="mc-nota mc-pendente">Ordem enviada em ' + dtHora(pend.quando) + ". O Paulus do escritório cumpre quando estiver aberto e ligado à internet.</p>"
      : !g.informado ? '<p class="mc-nota">Nenhum serviço do Google ligado — ou o Paulus do escritório ainda não contou. Ele conta quando está aberto e ligado à internet.</p>'
        : '<p class="mc-nota">Conferido pelo Paulus do escritório em ' + dtHora(g.conferido) + ".</p>";
    return '<div class="mc-corpo"><div class="cartao-permissoes"><div class="linha-botao duas"><span class="lb-icones"><span class="lb-ic">' + SIMB_G.google + '</span></span><span class="lb-texto"><b class="lb-titulo">' + esc(d.cadastro.nome) + '</b><small class="lb-sub">' + esc(g.conta) + "</small></span>" + (g.informado ? '<span class="lb-fim lb-status">conectado</span>' : "") + "</div>" +
      '<span class="cp-rotulo">O que autorizar</span><div class="cp-escopos">' +
      linhaG("gmail", "gmail", "Gmail", "ler e enviar, com Aprovações") + linhaG("agenda", "agenda", "Agenda", "ler e criar eventos") + linhaG("agenda", "meet", "Meet", "criar reuniões nos eventos", true) +
      linhaG("drive_enviar", "drive", "Drive", "só os arquivos que o Paulus envia") + linhaG("drive_ler", "drive", "Drive", "ler as pastas escolhidas") + "</div></div>" + estado +
      '<p class="mc-nota">Desligar um serviço faz o Paulus do escritório parar de usá-lo. O Google não tira uma permissão sozinha: para revogar tudo no Google, use Desvincular. Para ligar um serviço que nunca foi autorizado, entre com o Google no Paulus do escritório.</p></div>' +
      (titular() ? '<div class="mc-pe g-desv"><span class="mc-txt"><b>Desvincular a conta Google</b><small>Revoga todas as permissões de uma vez.</small></span><button type="button" class="mc-perigo mini-perigo" data-a="desvincular">Desvincular</button></div>' : "");
  }
  var ESC_G = [["gmail", "mail.google.com"], ["agenda", "calendar.events"], ["drive_enviar", "drive.file"], ["drive_ler", "drive.readonly"]];

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
  var PAPEIS = { titular: "titular", financeiro: "financeiro" };
  TELAS.pessoas = function (d) {
    var l = d.pessoas.map(function (p) {
      return '<div class="mc-linha"><span class="mc-avatar">' + esc(iniciais(p.nome || p.email)) + '</span><span class="mc-txt"><b>' + esc(p.nome || p.email) + (p.convite ? ' <span class="mc-tag atencao">convite enviado</span>' : "") + "</b><small>" + esc(p.email) + "</small></span>" +
        '<span class="mc-tag">' + esc(PAPEIS[p.papel] || p.papel) + "</span>" +
        (p.papel === "titular" ? '<span class="mc-acao-vazia"></span>' : '<button type="button" class="btn-icone" data-a="removerPessoa" data-id="' + esc(p.email) + '" aria-label="Tirar ' + esc(p.nome || p.email) + '" title="Tirar o acesso">' + ic("close") + "</button>") + "</div>";
    }).join("");
    var conv = d.email_ligado ? '<button type="button" class="mini cheia" data-a="convidar">' + ic("person_add") + "Convidar</button>"
      : '<button type="button" class="mini cheia" disabled title="O convite vai por e-mail, e o e-mail do Paulus ainda não está ligado">' + ic("person_add") + "Convidar</button>";
    return painel("Quem entra em Minha conta", conv, l) +
      '<p class="mc-nota centro">O financeiro vê o resumo, o consumo, as faturas e a forma de pagamento. Trocar de plano, cancelar e mexer no escritório são só do titular.</p>';
  };

  // As imagens ficam em site/assets/: a pagina real esta em /minha-conta/ e a demonstracao na raiz do projeto.
  var MP_IMG = /\/en\/my-account\//.test(location.pathname) ? "../../assets/" : /\/minha-conta\//.test(location.pathname) ? "../assets/" : "site/assets/";
  // O tema mudou com o entrar aberto: o botao da Conta Atos e montado de novo com as cores novas.
  new MutationObserver(function () { if (S.d && S.d.entrar) montarSenha(); }).observe(document.documentElement, { attributes: true, attributeFilter: ["data-theme"] });

  /* ------------------------------------------------------------ os pop-ups (o dialogo do Paulus) */
  function dialogo(tit, ctx, corpo, pe) {
    return '<div class="mc-veu" data-a="fechar"></div><div class="mc-dialogo" role="dialog" aria-modal="true" aria-labelledby="mc-dlg-tit"><div class="mc-dlg-cab"><span class="mc-dlg-titulos"><h2 id="mc-dlg-tit">' + esc(tit) + "</h2>" + (ctx ? "<span>" + esc(ctx) + "</span>" : "") + '</span><button type="button" class="btn-icone" data-a="fechar" aria-label="Fechar">' + ic("close") + '</button></div><div class="mc-dlg-corpo">' + corpo + '</div><div class="mc-dlg-pe"><span class="mc-cresce"></span>' + pe + "</div></div>";
  }
  // Disponibilidade do endereco, conferida enquanto a pessoa digita (espera 350 ms sem tecla para perguntar ao servidor).
  var SLUG_OK = /^[a-z0-9](?:[a-z0-9-]{1,22}[a-z0-9])$/, slugT = null;
  // As frases curtas do Admin (Alterar endereco), com a bolinha da cor do estado.
  function endStatus(M) {
    var v = M.v || "", atual = S.d.escritorio.slug, C = M.check || {}, f = function (cls, msg, ok) { return { cls: cls, icone: "", msg: msg ? "<i></i>" + esc(msg) : "", ok: !!ok }; };
    if (!v) return f("", "");
    if (v.length < 3) return f("erro", "use pelo menos 3 letras");
    if (/^-|-$/.test(v)) return f("erro", "não comece nem termine com hífen");
    if (!SLUG_OK.test(v)) return f("erro", "só letras minúsculas, números e hífen");
    if (v === atual) return f("erro", "é o endereço de agora");
    if (C.slug !== v || C.estado === "verificando") return f("mudo", "conferindo…");
    if (C.estado === "livre") return f("ok", "disponível", true);
    if (C.estado === "usado") return f("erro", "já em uso");
    return f("erro", "não consegui conferir agora");
  }
  /* O endereco novo segue a regra dos campos: a borda vermelha (errado, ou ja em uso) ou verde (livre) aparece
     depois de tocado (digitou e saiu, ou tentou Alterar); a frase fica so para o leitor de tela. "conferindo…"
     continua a vista: e a espera pelo servidor, nao um erro. */
  function endPintar(M, st) {
    var cx = $("mc-slug-caixa"), msg = $("mc-slug-msg"); if (!cx) return;
    var mostra = M.tocado && (st.cls === "erro" || st.cls === "ok");
    if (P) P.marcar(cx, mostra ? st.cls : "", mostra && st.cls === "erro" ? (msg ? msg.textContent : "") : "");
    if (msg) msg.classList.toggle("so-leitor", st.cls === "erro" || st.cls === "ok");
  }
  function endAtualizar() {
    var M = S.modal; if (!M || M.tipo !== "endereco") return; var st = endStatus(M);
    var msg = $("mc-slug-msg");
    if (msg) { msg.className = "mc-slug-msg " + st.cls; msg.innerHTML = st.msg; }
    endPintar(M, st);
  }
  function modalHtml() {
    var M = S.modal, d = S.d; if (!M) return "";
    var cancel = '<button type="button" class="mc-texto" data-a="fechar">Cancelar</button>';
    if (M.tipo === "endereco") {
      var st = endStatus(M);
      return dialogo("Alterar o endereço", "Escritório",
        '<div class="campo-site"><label for="mc-slug">Endereço novo</label><span class="caixa-campo mono mc-slug-caixa" id="mc-slug-caixa"><input id="mc-slug" data-a-in="slug" value="' + esc(M.v || "") + '" spellcheck="false" autocomplete="off" aria-describedby="mc-slug-msg"><span class="mudo">.paulus.ia.br</span></span>' +
        '<p class="mc-slug-msg ' + st.cls + '" id="mc-slug-msg" role="status" aria-live="polite">' + st.msg + "</p></div>" +
        '<div class="linha-botao tom-cf"><span class="lb-icones"><span class="lb-ic lb-cf"><img src="' + MP_IMG + 'cloudflare-completo.svg" alt="" width="26" height="26"></span></span><span class="lb-texto"><b class="lb-titulo">Túnel do Cloudflare</b></span><span class="lb-fim lb-meta">conexão protegida</span></div>' +
        '<p class="mc-nota">O endereço atual, ' + esc(d.escritorio.slug) + ".paulus.ia.br, deixa de funcionar na hora. Avise a equipe e os clientes.</p>",
        cancel + '<button type="button" class="btn-duplo pequeno" id="mc-end-ok" data-a="confirmarEndereco"><span>Alterar</span></button>');
    }
    if (M.tipo === "convidar") {
      return dialogo("Convidar para Minha conta", "Pessoas",
        '<label class="campo-site"><span>E-mail da pessoa</span><span class="caixa-campo"><input id="mc-conv" type="email" data-a-in="convEmail" value="' + esc(M.email || "") + '" placeholder="nome@escritorio.com.br" autocomplete="off"></span></label>' +
        "<p>Entra como <b>financeiro</b>: vê o resumo e o consumo. Ela recebe um e-mail com o link, válido por 7 dias.</p>",
        cancel + '<button type="button" class="btn-duplo pequeno" data-a="confirmarConvite"><span>Enviar convite</span></button>');
    }
    if (M.tipo === "aviso") return dialogo(M.titulo, M.ctx, "<p>" + esc(M.texto) + "</p>", cancel + '<a class="btn-duplo pequeno" href="' + esc(M.link) + '"><span>' + esc(M.botao) + "</span></a>");
    if (M.tipo === "confirmar") return dialogo(M.titulo, M.ctx, "<p>" + M.texto + "</p>", cancel + '<button type="button" class="' + (M.leve ? "btn-duplo pequeno" : "mc-perigo") + '" data-a="confirmarSim">' + (M.leve ? "<span>" + esc(M.botao) + "</span>" : esc(M.botao)) + "</button>");
    return "";
  }

  /* ------------------------------------------------------------ pintar */
  function render() {
    var r = $("mc-raiz"); if (!r) return;
    if (!S.d) { r.innerHTML = '<div class="mc-carregando">Carregando…</div>'; return; }
    if (S.d.entrar) { r.innerHTML = entrarHtml(); montarSenha(); renderModal(); return; }
    var lista = abas(); if (!lista.some(function (a) { return a[0] === S.aba; })) S.aba = "resumo";
    var a = S.d.assinatura;
    var semPlano = a.situacao === "nenhuma" || a.situacao === "vencida";
    var h = '<div class="mc-col"><header class="mc-cab"><h1>Minha conta</h1><p class="texto-lead">' + esc(S.d.cadastro.nome) + (semPlano ? " · sem assinatura" : " · plano " + esc(a.nome)) + " · " + esc(S.d.perfil.email) + (titular() ? "" : " (financeiro)") +
      ' <button type="button" class="mc-sair" data-a="sair">Sair</button></p></header>' +
      '<div class="mc-centro">' + pilula("aba", lista, S.aba) + "</div>" +
      '<div class="mc-tela" data-tela="' + S.aba + '">' + TELAS[S.aba](S.d) + "</div></div>";
    r.innerHTML = h;
    // No celular as abas rolam dentro da pilula: a aba aberta fica a vista.
    var on = r.querySelector('.mc-centro [data-seg="aba"][aria-pressed="true"]');
    if (on && on.parentElement.scrollWidth > on.parentElement.clientWidth) on.parentElement.scrollLeft = on.offsetLeft - (on.parentElement.clientWidth - on.offsetWidth) / 2;
    renderModal();
  }
  function renderModal() {
    var c = $("mc-camada"); if (!c) { c = document.createElement("div"); c.id = "mc-camada"; document.body.appendChild(c); }
    c.innerHTML = modalHtml();
    // O redesenho troca os campos: a borda de cada um volta pelo estado guardado (PvCampos).
    if (P) P.reaplicar();
    if (S.modal && S.modal.tipo === "endereco") endAtualizar();
  }
  // So a Conta Atos (09/10/2026): o Google e escolhido em atos.dev.br. O id_token da Atos abre a sessao da
  // Minha conta (um cookie HttpOnly), como o do Google abria.
  function entrarHtml() {
    return '<div class="mc-entrar"><h1>Minha conta</h1><p class="texto-lead">' + (S.convite ? "Você recebeu um convite para a Minha conta de um escritório. Entre com a Conta Atos do e-mail que recebeu o convite." :
      "Entre com a Conta Atos da assinatura, ou com a que o titular autorizou.") + "</p>" +
      '<div class="mc-senha" id="mc-senha"></div>' +
      (S.erroEntrar ? '<p class="mc-nota centro mc-erro" role="alert">' + esc(cap(S.erroEntrar)) + "</p>" : "") +
      '<p class="mc-nota centro">Ainda não assina? <a href="' + (MP_IMG === "../../assets/" ? "../../assinatura/" : MP_IMG === "../assets/" ? "../assinatura/" : "Site - Assinatura.dc.html") + '">Conheça os planos</a>.</p></div>';
  }
  // A Conta Atos (assets/entrar-atos.js).
  function montarSenha() {
    var l = $("mc-senha"); if (!l || !window.EntrarAtos) return;
    EntrarAtos.montar(l, { ingles: L(false, true), aoEntrar: function (token) { A.entrarComToken(token); } });
  }

  /* ------------------------------------------------------------ acoes */
  function recarregar() { return api("GET", "/api/conta").then(function (d) { S.d = d; render(); }).catch(function () { location.reload(); }); }
  var A = {
    fechar: function () { S.modal = null; renderModal(); },
    salvarCadastro: function (el) {
      var v = {}; document.querySelectorAll("[data-cad]").forEach(function (i) { v[i.dataset.cad] = i.value.trim(); });
      if (S.cmun) v.cmun = S.cmun;
      if (P && !P.conferir(CAD)) return;
      el.disabled = true;
      api("POST", "/api/conta/cadastro", v).then(function (j) { el.disabled = false; S.d.cadastro = j.cadastro || S.d.cadastro; S.cmun = ""; if (P) P.esquecer("mc-cad-"); render(); toast("Cadastro salvo"); })
        .catch(function (e) { el.disabled = false; if (!erroDeCampo(e, CAD_DO_CAMPO)) toast(e.message, true); });
    },
    alterarEndereco: function () { S.modal = { tipo: "endereco", v: "", tocado: false }; renderModal(); setTimeout(function () { var i = $("mc-slug"); if (i) i.focus(); }, 30); },
    confirmarEndereco: function (el) {
      var M = S.modal; M.tocado = true; endAtualizar();
      if (!endStatus(M).ok) { var i = $("mc-slug"); if (i) i.focus(); return; }
      var v = M.v; el.disabled = true;
      api("POST", "/api/conta/endereco", { slug: v }).then(function (j) { S.d.escritorio.slug = j.slug || v; S.modal = null; render(); toast("Endereço alterado para " + (j.slug || v) + ".paulus.ia.br"); })
        .catch(function (e) {
          el.disabled = false;
          // Ocupado ou ja desta conta: a borda vermelha no endereco, sem o aviso.
          if (e.status === 409 && S.modal === M && /endereço (já|não está livre)/.test(e.message)) { M.check = { slug: v, estado: "usado" }; endAtualizar(); var i2 = $("mc-slug"); if (i2) i2.focus(); return; }
          toast(e.message, true);
        });
    },
    removerInstalacao: function (el) {
      var i = S.d.instalacoes.filter(function (x) { return x.id === el.dataset.id; })[0];
      S.modal = { tipo: "confirmar", titulo: "Tirar este computador?", ctx: "Instalações", texto: esc(i.nome) + " deixa de usar a assinatura: a IA e os serviços da nuvem param nele até alguém entrar de novo no programa, com a Conta Google ou a Conta Atos.", botao: "Tirar",
        fazer: function () { return api("POST", "/api/conta/instalacoes/" + encodeURIComponent(i.id) + "/remover", {}).then(function () { S.d.instalacoes = S.d.instalacoes.filter(function (x) { return x !== i; }); toast("Computador tirado"); }); } };
      renderModal();
    },
    servico: function (el) {
      var id = el.dataset.id, ligar = el.getAttribute("aria-checked") !== "true";
      el.setAttribute("aria-checked", String(ligar)); var sw = el.querySelector(".lb-chave"); if (sw) sw.classList.toggle("on", ligar);
      api("POST", "/api/conta/google/servico", { id: id, ligado: ligar }).then(function () {
        var nome = { gmail: "Gmail", agenda: "Agenda", drive_enviar: "Drive · enviar", drive_ler: "Drive · ler" }[id] || id;
        toast(nome + (ligar ? ": ordem de ligar enviada" : ": ordem de desligar enviada")); return recarregar();
      }).catch(function (e) { toast(e.message, true); recarregar(); });
    },
    desvincular: function () {
      S.modal = { tipo: "confirmar", titulo: "Desvincular a conta Google?", ctx: "Permissões Google", botao: "Desvincular",
        texto: "O Paulus do escritório revoga no Google o acesso ao Gmail, à Agenda e ao Drive, da próxima vez que estiver aberto e ligado à internet. Para ligar de novo, é preciso entrar com o Google no programa.",
        fazer: function () { return api("POST", "/api/conta/google/desvincular", {}).then(function () { toast("Ordem de desvincular enviada"); return recarregar(); }); } };
      renderModal();
    },
    convidar: function () { if (P) P.esquecer("mc-conv"); S.modal = { tipo: "convidar", email: "" }; renderModal(); setTimeout(function () { var i = $("mc-conv"); if (i) i.focus(); }, 30); },
    confirmarConvite: function (el) {
      var em = S.modal.email.trim().toLowerCase();
      if (P && !P.conferir(["mc-conv"])) return;
      el.disabled = true;
      api("POST", "/api/conta/pessoas", { email: em, papel: "financeiro" }).then(function () { S.modal = null; toast("Convite enviado para " + em); return recarregar(); })
        .catch(function (e) { el.disabled = false; if (!erroDeCampo(e, [[/^o e-mail não confere|^esse é o e-mail do titular/, "mc-conv"]])) toast(e.message, true); });
    },
    removerPessoa: function (el) {
      var p = S.d.pessoas.filter(function (x) { return x.email === el.dataset.id; })[0];
      S.modal = { tipo: "confirmar", titulo: p.convite ? "Cancelar o convite?" : "Tirar o acesso?", ctx: "Pessoas", texto: esc(p.nome || p.email) + (p.convite ? " não vai mais poder usar o link." : " deixa de entrar em Minha conta."), botao: p.convite ? "Cancelar convite" : "Tirar o acesso",
        fazer: function () { return api("POST", "/api/conta/pessoas/" + encodeURIComponent(p.email) + "/remover", {}).then(function () { S.d.pessoas = S.d.pessoas.filter(function (x) { return x !== p; }); toast(p.convite ? "Convite cancelado" : "Acesso tirado"); }); } };
      renderModal();
    },
    confirmarSim: function (el) { var M = S.modal; el.disabled = true; M.fazer().then(function () { if (S.modal === M) S.modal = null; render(); }).catch(function (e) { el.disabled = false; toast(e.message, true); }); },
    calMes: function (el) {
      S.cicloEsc = el.dataset.v; S.periodo = "outro"; S.calAberto = null; render(); carregarConsumo(el.dataset.v);
    },
    calAnoPasso: function (el) { S.calAberto.ano += Number(el.dataset.v) * (S.calAberto.vista === "anos" ? 12 : 1); render(); },
    calVistaAnos: function () { S.calAberto.vista = "anos"; render(); },
    calAno: function (el) { S.calAberto.ano = Number(el.dataset.v); S.calAberto.vista = "meses"; render(); },
    entrarComToken: function (credencial) {
      S.erroEntrar = "";
      api("POST", "/api/conta/entrar", { credential: credencial, convite: S.convite || "" }).then(function () { S.convite = ""; S.d = null; render(); carregar(); })
        .catch(function (e) {
          // Entrou, mas a conta ainda nao assina (e nao veio por convite): vai escolher o plano (o Assinar leva
          // ao checkout da Atos).
          if (e.dados && e.dados.sem_conta && !S.convite) {
            location.assign("/assinatura/");
            return;
          }
          S.erroEntrar = e.message; render();
        });
    },
    sair: function () {
      api("POST", "/api/conta/sair", {}).catch(function () { /* o cookie some de qualquer jeito */ }).then(function () {
        try { if (window.google && google.accounts && google.accounts.id) google.accounts.id.disableAutoSelect(); } catch (e) { /* nada */ }
        S.d = { entrar: true }; S.modal = null; S.aba = "resumo"; S.anual = null; try { history.replaceState(null, "", location.pathname); } catch (e) {} render();
      });
    },
  };
  // O CEP com 8 digitos preenche rua, bairro, cidade e UF pela ViaCEP e guarda o codigo IBGE do municipio (vai na NFS-e).
  var cepLido = "";
  function buscarCep(el) {
    var cep = el.value.replace(/\D/g, ""), nota = $("mc-cep-nota");
    if (cep.length !== 8) { if (nota) nota.hidden = true; return; }
    if (cep === cepLido) return;
    cepLido = cep; S.cmun = "";
    if (nota) { nota.textContent = "Procurando o CEP…"; nota.hidden = false; }
    fetch("https://viacep.com.br/ws/" + cep + "/json/").then(function (r) { return r.json().then(function (d) { if (!r.ok || !d || d.erro) throw new Error(""); return d; }); }).then(function (d) {
      if ((($("mc-cad-cep") || {}).value || "").replace(/\D/g, "") !== cep) return;
      var por = function (k, v) { var i = $("mc-cad-" + k); if (i && v) i.value = v; };
      por("logradouro", d.logradouro); por("bairro", d.bairro); por("cidade", d.localidade);
      var uf = $("mc-cad-uf"); if (uf && d.uf) uf.value = d.uf;
      S.cmun = /^\d{7}$/.test(String(d.ibge || "")) ? d.ibge : "";
      if (nota) nota.hidden = true;
      if (P) P.reaplicar();
      var foco = $(d.logradouro ? "mc-cad-numero" : "mc-cad-logradouro"); if (foco) foco.focus();
    }).catch(function () {
      if (nota) { nota.textContent = "Não achei esse CEP agora. Confira o número ou preencha o endereço à mão."; nota.hidden = false; }
    });
  }
  var ENTRADAS = {
    cep: function (el) { mascarar(el); buscarCep(el); },
    mascarar: mascarar,
    semCmun: function () { S.cmun = ""; },
    slug: function (el) {
      var v = el.value.toLowerCase().replace(/[^a-z0-9-]/g, "").slice(0, 24); if (el.value !== v) el.value = v;
      var M = S.modal; M.v = v; clearTimeout(slugT);
      if (SLUG_OK.test(v) && v !== S.d.escritorio.slug) {
        M.check = { slug: v, estado: "verificando" };
        slugT = setTimeout(function () {
          api("GET", "/api/conta/endereco/disponivel?slug=" + encodeURIComponent(v)).then(function (j) {
            if (S.modal === M && M.v === v) { M.check = { slug: v, estado: j.disponivel ? "livre" : "usado" }; endAtualizar(); }
          }).catch(function () { if (S.modal === M && M.v === v) { M.check = { slug: v, estado: "erro" }; endAtualizar(); } });
        }, 350);
      }
      endAtualizar();
    },
    convEmail: function (el) { S.modal.email = el.value; },
  };
  var SEGS = {
    aba: function (v) { S.aba = v; S.calAberto = null; window.scrollTo(0, 0); try { history.replaceState(null, "", "#" + v); } catch (e) {} },
    periodo: function (v) {
      if (v === "outro") { var base = S.cicloEsc ? Number(S.cicloEsc.slice(0, 4)) : new Date((S.d.assinatura.ciclo.de || new Date().toISOString().slice(0, 10)) + "T12:00").getFullYear(); S.calAberto = S.calAberto ? null : { ano: base, vista: "meses", alvo: "consumo" }; return; }
      S.calAberto = null; S.periodo = v; carregarConsumo(v);
    },
    periodoPlano: function (v) { S.anual = v === "anual"; },
  };

  document.addEventListener("click", function (ev) {
    var seg = ev.target.closest("[data-seg]"); if (seg && SEGS[seg.dataset.seg]) { SEGS[seg.dataset.seg](seg.dataset.v); render(); return; }
    var ab = ev.target.closest("[data-aba]"); if (ab) { SEGS.aba(ab.dataset.aba); render(); return; }
    var a = ev.target.closest("[data-a]"); if (a && A[a.dataset.a] && !a.disabled) { ev.preventDefault(); A[a.dataset.a](a); }
  });
  document.addEventListener("input", function (ev) { var k = ev.target.dataset && ev.target.dataset.aIn; if (k && ENTRADAS[k]) ENTRADAS[k](ev.target); });
  // O endereco novo passa a mostrar o estado depois que a pessoa digitou e saiu do campo.
  document.addEventListener("focusout", function (ev) {
    if (ev.target.id !== "mc-slug" || !S.modal || S.modal.tipo !== "endereco" || !S.modal.v) return;
    var M = S.modal; setTimeout(function () { if (S.modal === M && document.activeElement !== $("mc-slug")) { M.tocado = true; endAtualizar(); } }, 0);
  });
  document.addEventListener("change", function (ev) { if (ev.target.tagName === "SELECT") { var k = ev.target.dataset && ev.target.dataset.aIn; if (k && ENTRADAS[k]) ENTRADAS[k](ev.target); } });
  document.addEventListener("keydown", function (ev) { var sw = ev.target.closest && ev.target.closest('[role="switch"][data-a]'); if (sw && (ev.key === "Enter" || ev.key === " ")) { ev.preventDefault(); sw.click(); } });
  document.addEventListener("keydown", function (ev) { if (ev.key === "Escape") { if (S.modal) A.fechar(); else if (S.calAberto) { S.calAberto = null; render(); } } });
  document.addEventListener("mousedown", function (ev) { if (S.calAberto && !ev.target.closest(".mc-periodo")) { S.calAberto = null; render(); } });

  function carregarConsumo(v) { api("GET", "/api/conta/consumo?ciclo=" + encodeURIComponent(v)).then(function (j) { S.d.consumo = j; render(); }).catch(function (e) { toast(e.message, true); }); }
  function carregar() {
    api("GET", "/api/conta").then(function (d) {
      S.d = d; if (!d.entrar && S.anual === null) S.anual = d.assinatura.periodo === "anual";
      render();
    }).catch(function (e) { S.d = { entrar: true }; if (e.status !== 401) S.erroEntrar = e.message; render(); });
  }
  function iniciar(op) {
    op = op || {};
    var h = (location.hash || "").slice(1);
    // O link do convite (#convite=<codigo>): o codigo vai junto ao entrar com o Google, e sai do endereco.
    if (/^convite=[0-9a-f]{48}$/.test(h)) { S.convite = h.slice(8); h = ""; try { history.replaceState(null, "", location.pathname); } catch (e) {} }
    if (op.aba) S.aba = op.aba; else if (h) S.aba = h;
    // ?entrar=<codigo>: o link que o Paulus abriu ("edite no site", "Fazer upgrade") ja traz a sessao.
    var q = new URLSearchParams(location.search).get("entrar") || "";
    if (/^[0-9a-f]{64}$/.test(q)) {
      try { history.replaceState(null, "", location.pathname + location.hash); } catch (e) {}
      render();
      api("POST", "/api/conta/entrar", { link: q }).catch(function (e) { S.erroEntrar = e.message; }).then(carregar);
      return;
    }
    render(); carregar();
  }
  window.MinhaConta = { iniciar: iniciar };
  // Comeca sozinha: a CSP da pagina nao deixa script inline.
  if (document.getElementById("mc-raiz")) {
    if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", function () { iniciar(); }); else iniciar();
  }
})();
