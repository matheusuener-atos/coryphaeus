/* Minha conta (paulus.ia.br/minha-conta/): o titular da assinatura - e quem ele autorizar - cuida do plano,
   do consumo, das faturas, da forma de pagamento, do cadastro e do escritorio. Entra com a conta Google.
   Desenho: a topbar do site, o titulo centrado e as abas na pilula (como a pagina da conta no Admin). */
(function () {
  "use strict";
  var S = { aba: "resumo", d: null, modal: null, filtroFat: "todas", periodo: "ciclo", anual: false, pix: null, recarga: 1 };
  var ABAS = [["resumo", "Resumo"], ["consumo", "Consumo"], ["faturas", "Faturas"], ["pagamento", "Pagamento"], ["plano", "Plano"], ["cadastro", "Cadastro"], ["escritorio", "Escritório"], ["pessoas", "Pessoas"]];
  var DO_FINANCEIRO = { resumo: 1, consumo: 1, faturas: 1, pagamento: 1 };
  var MESES = ["jan", "fev", "mar", "abr", "mai", "jun", "jul", "ago", "set", "out", "nov", "dez"];

  function $(id) { return document.getElementById(id); }
  function esc(s) { return String(s == null ? "" : s).replace(/[&<>"']/g, function (c) { return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]; }); }
  function ic(n) { return '<span class="icon" aria-hidden="true">' + n + "</span>"; }
  function brl(v) { return Number(v || 0).toLocaleString("pt-BR", { style: "currency", currency: "BRL" }); }
  function brl0(v) { return Number(v || 0).toLocaleString("pt-BR", { style: "currency", currency: "BRL", maximumFractionDigits: 0 }); }
  function tok(n) { var m = Number(n || 0) / 1e6; return (m >= 10 ? Math.round(m) : Math.round(m * 10) / 10).toLocaleString("pt-BR") + " M"; }
  function dt(iso) { if (!iso) return "—"; var p = String(iso).slice(0, 10).split("-"); return p[2] + "/" + p[1] + "/" + p[0]; }
  function mesAno(iso) { var p = String(iso).slice(0, 10).split("-"); return MESES[Number(p[1]) - 1] + "/" + p[0]; }
  function diasAte(iso) { var a = new Date(); a.setHours(0, 0, 0, 0); return Math.round((new Date(String(iso).slice(0, 10) + "T00:00") - a) / 864e5); }
  function iniciais(n) { var p = String(n || "").trim().split(/\s+/).filter(Boolean); return p.length ? (p.length > 1 ? p[0][0] + p[p.length - 1][0] : p[0].slice(0, 2)).toUpperCase() : "?"; }
  function titular() { return S.d && S.d.perfil.papel === "titular"; }
  function abas() { return ABAS.filter(function (a) { return titular() || DO_FINANCEIRO[a[0]]; }); }

  var PIX = '<svg class="mc-pix" viewBox="0 0 16 16" width="14" height="14" aria-hidden="true"><path fill="currentColor" d="M12.3 11.9a2 2 0 0 1-1.4-.6L8.6 9a.4.4 0 0 0-.6 0l-2.3 2.3a2 2 0 0 1-1.4.6h-.5l2.9 2.9a2.3 2.3 0 0 0 3.3 0l2.9-2.9h-.6ZM4.3 4.1a2 2 0 0 1 1.4.6L8 7a.4.4 0 0 0 .6 0l2.3-2.3a2 2 0 0 1 1.4-.6h.4L9.8 1.2a2.3 2.3 0 0 0-3.3 0L3.7 4.1h.6Zm10.5 2.2L13 4.6h-.7a1.4 1.4 0 0 0-1 .4L9.1 7.3a1.1 1.1 0 0 1-1.6 0L5.3 5a1.4 1.4 0 0 0-1-.4h-.9L1.2 6.3a2.3 2.3 0 0 0 0 3.3l1.7 1.7h1a1.4 1.4 0 0 0 1-.4l2.3-2.3a1.1 1.1 0 0 1 1.6 0l2.3 2.3a1.4 1.4 0 0 0 1 .4h.7l1.7-1.7a2.3 2.3 0 0 0 0-3.3Z"/></svg>';
  var GOOGLE = '<svg viewBox="0 0 18 18" width="16" height="16" aria-hidden="true"><path fill="#4285F4" d="M17.6 9.2c0-.6-.1-1.2-.2-1.7H9v3.3h4.8a4.1 4.1 0 0 1-1.8 2.7v2.2h2.9c1.7-1.6 2.7-3.9 2.7-6.5Z"/><path fill="#34A853" d="M9 18c2.4 0 4.5-.8 6-2.2l-2.9-2.2c-.8.5-1.8.9-3.1.9-2.4 0-4.4-1.6-5.1-3.8H.9v2.3A9 9 0 0 0 9 18Z"/><path fill="#FBBC05" d="M3.9 10.7a5.4 5.4 0 0 1 0-3.4V5H.9a9 9 0 0 0 0 8l3-2.3Z"/><path fill="#EA4335" d="M9 3.6c1.3 0 2.5.5 3.5 1.4l2.6-2.6A9 9 0 0 0 .9 5l3 2.3C4.6 5.2 6.6 3.6 9 3.6Z"/></svg>';
  function bandeira(b) {
    var k = String(b || "").toLowerCase();
    if (k === "mastercard") return '<span class="mc-bandeira" aria-label="Mastercard"><svg viewBox="0 0 24 16" width="24" height="16" aria-hidden="true"><circle cx="9.5" cy="8" r="5" fill="#EB001B"/><circle cx="14.5" cy="8" r="5" fill="#F79E1B"/><path d="M12 3.6a5 5 0 0 1 0 8.8 5 5 0 0 1 0-8.8Z" fill="#FF5F00"/></svg></span>';
    if (k === "visa") return '<span class="mc-bandeira" aria-label="Visa"><svg viewBox="0 0 24 16" width="24" height="16" aria-hidden="true"><text x="12" y="11.2" text-anchor="middle" font-family="Arial, Helvetica, sans-serif" font-size="8.4" font-weight="700" font-style="italic" fill="#1A1F71">VISA</text></svg></span>';
    if (k === "elo") return '<span class="mc-bandeira" style="background:#000" aria-label="Elo"><svg viewBox="0 0 24 16" width="24" height="16" aria-hidden="true"><text x="12" y="11.2" text-anchor="middle" font-family="Arial, Helvetica, sans-serif" font-size="8.6" font-weight="700" fill="#fff">elo</text></svg></span>';
    if (k === "amex") return '<span class="mc-bandeira" style="background:#016FD0" aria-label="American Express"><svg viewBox="0 0 24 16" width="24" height="16" aria-hidden="true"><text x="12" y="10.6" text-anchor="middle" font-family="Arial, Helvetica, sans-serif" font-size="6.6" font-weight="700" fill="#fff">AMEX</text></svg></span>';
    if (k === "hipercard") return '<span class="mc-bandeira" style="background:#B3131B" aria-label="Hipercard"><svg viewBox="0 0 24 16" width="24" height="16" aria-hidden="true"><text x="12" y="10.2" text-anchor="middle" font-family="Arial, Helvetica, sans-serif" font-size="4.6" font-weight="700" fill="#fff">Hipercard</text></svg></span>';
    return '<span class="mc-bandeira texto">' + esc(b || "Cartão") + "</span>";
  }
  function forma(f) {
    if (!f) return "—";
    if (f.tipo === "pix") return '<span class="mc-forma">' + PIX + "<span>Pix</span></span>";
    return '<span class="mc-forma">' + bandeira(f.bandeira) + "<span>•••• " + esc(f.final) + "</span></span>";
  }
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
      .then(function (r) { return r.json().catch(function () { return {}; }).then(function (j) { if (!r.ok) { var e = new Error(j.erro || "não foi possível agora"); e.status = r.status; throw e; } return j; }); });
  }
  function toast(t, erro) {
    var el = $("mc-toast"); if (!el) { el = document.createElement("div"); el.id = "mc-toast"; el.className = "mc-toast"; el.setAttribute("role", "status"); document.body.appendChild(el); }
    el.textContent = t; el.classList.toggle("erro", !!erro); el.classList.add("on");
    clearTimeout(toast.t); toast.t = setTimeout(function () { el.classList.remove("on"); }, 3200);
  }

  /* ------------------------------------------------------------ as abas */
  var TELAS = {};

  TELAS.resumo = function (d) {
    var a = d.assinatura, c = a.ciclo, pct = Math.min(100, Math.round(c.usados / c.tokens * 100)), resta = Math.max(0, c.tokens - c.usados), dias = diasAte(a.proxima);
    var assin = '<div class="mc-corpo"><div class="mc-plano-nome"><h2>' + esc(a.nome) + '</h2><span class="mc-tag">' + (a.periodo === "anual" ? "anual" : "mensal") + "</span></div>" +
      '<dl class="mc-fatos">' +
      "<div><dt>Situação</dt><dd>" + '<span class="mc-bolinha ok"></span>Ativa</dd></div>' +
      "<div><dt>Próxima cobrança</dt><dd>" + dt(a.proxima) + " · " + brl(a.valor) + "</dd></div>" +
      "<div><dt>Cobrança em</dt><dd>" + (d.pagamento.tipo === "pix" ? forma({ tipo: "pix" }) : forma(d.pagamento.cartao)) + "</dd></div>" +
      "<div><dt>Assinante desde</dt><dd>" + mesAno(a.desde) + "</dd></div></dl></div>" +
      '<div class="mc-pe">' + (titular() ? '<button type="button" class="mini" data-aba="plano">Trocar de plano</button>' : "") + '<button type="button" class="mini" data-aba="faturas">Ver faturas</button></div>';
    var uso = '<div class="mc-corpo"><div class="mc-uso-num"><b>' + pct + '%</b><span>' + tok(c.usados) + " de " + tok(c.tokens) + " tokens</span></div>" +
      '<span class="mc-barra" role="progressbar" aria-valuenow="' + pct + '" aria-valuemin="0" aria-valuemax="100"><i style="width:' + pct + '%"></i></span>' +
      '<dl class="mc-fatos"><div><dt>Restam</dt><dd>' + tok(resta) + " tokens</dd></div><div><dt>Renova em</dt><dd>" + dt(a.proxima) + " · " + dias + (dias === 1 ? " dia" : " dias") + "</dd></div>" +
      (c.recargas ? "<div><dt>Recargas no ciclo</dt><dd>" + tok(c.recargas) + " tokens</dd></div>" : "") + "</dl></div>" +
      '<div class="mc-pe"><button type="button" class="mini" data-aba="consumo">Ver consumo</button><button type="button" class="mini" data-a="recarga">' + PIX + "Recarga no Pix</button></div>";
    var ult = d.faturas.slice(0, 3).map(linhaFatura).join("");
    return '<div class="mc-grade2">' + painel("Assinatura", "", assin) + painel("Uso do ciclo", dt(c.de).slice(0, 5) + " – " + dt(c.ate).slice(0, 5), uso) + "</div>" +
      painel("Últimas faturas", "", '<div class="mc-tabela">' + cabFatura() + ult + '</div><div class="mc-ver"><button type="button" class="mc-ver-mais" data-aba="faturas">Ver todas' + ic("arrow_outward") + "</button></div>");
  };

  TELAS.consumo = function (d) {
    var dias = d.consumo.dias, ritmo = d.assinatura.ciclo.tokens / dias.length;
    var maior = Math.max.apply(null, dias.map(function (x) { return x.tokens; }).concat([1])), max = Math.max(maior, ritmo) * 1.1;
    var total = dias.reduce(function (s, x) { return s + x.tokens; }, 0);
    // Uma barra por dia; a linha tracejada e o ritmo da cota (o que da para usar por dia sem faltar no fim do ciclo).
    var barras = '<p class="mc-legenda"><span><i class="mc-leg-barra"></i>tokens usados no dia</span><span><i class="mc-leg-linha"></i>ritmo da cota: ' + tok(ritmo) + ' por dia</span><span><i class="mc-leg-futuro"></i>dias que ainda não chegaram</span></p>' +
      '<div class="mc-grafico-area"><span class="mc-ritmo" style="bottom:' + (ritmo / max * 100) + '%"></span><div class="mc-grafico" role="img" aria-label="Tokens por dia no ciclo">' + dias.map(function (x) {
      var h = x.tokens ? Math.max(3, Math.round(x.tokens / max * 100)) : 0;
      return '<span class="mc-dia' + (x.futuro ? " futuro" : "") + '" title="' + dt(x.data) + (x.futuro ? "" : " · " + tok(x.tokens) + " tokens") + '"><i style="height:' + h + '%"></i></span>';
    }).join("") + '</div></div><div class="mc-grafico-eixo"><span>' + dt(dias[0].data).slice(0, 5) + "</span><span>" + dt(dias[dias.length - 1].data).slice(0, 5) + "</span></div>";
    var feitos = dias.filter(function (x) { return !x.futuro; });
    var media = feitos.length ? total / feitos.length : 0;
    var graf = '<div class="mc-corpo">' + barras + '<dl class="mc-fatos linha"><div><dt>No ciclo</dt><dd>' + tok(total) + " tokens</dd></div><div><dt>Média por dia</dt><dd>" + tok(media) + "</dd></div><div><dt>Maior dia</dt><dd>" + tok(maior) + "</dd></div></dl></div>";
    var ps = d.consumo.pessoas.slice().sort(function (a, b) { return b.tokens - a.tokens; });
    var pessoas = ps.map(function (p) {
      var pc = total ? Math.round(p.tokens / total * 100) : 0;
      return '<div class="mc-linha"><span class="mc-avatar">' + esc(iniciais(p.nome)) + '</span><span class="mc-txt"><b>' + esc(p.nome) + "</b><small>" + esc(p.email) + '</small></span><span class="mc-uso-pessoa"><span class="mc-barra fina"><i style="width:' + pc + '%"></i></span></span><span class="mc-num">' + tok(p.tokens) + '</span><span class="mc-num mudo">' + pc + "%</span></div>";
    }).join("");
    // "Outro ciclo" abre o seletor de mes e ano do Admin (vista de meses; o titulo troca para a vista de anos).
    // So ficam liberados os meses com assinatura, do inicio ate o ciclo antes do anterior.
    var ini = new Date(d.assinatura.desde + "T12:00"), at = new Date(d.assinatura.ciclo.de + "T12:00");
    var primeiro = ini.getFullYear() * 12 + ini.getMonth(), ultimo = at.getFullYear() * 12 + at.getMonth() - 2;
    var rotEsc = S.cicloEsc ? MESES[Number(S.cicloEsc.slice(5)) - 1] + "/" + S.cicloEsc.slice(0, 4) : "";
    var pop = S.calAberto && S.calAberto.alvo === "consumo" ? calPop(primeiro, ultimo, S.cicloEsc) : "";
    var outro = [["ciclo", "Este ciclo"], ["anterior", "Ciclo anterior"], ["outro", S.periodo === "outro" && rotEsc ? "Ciclo de " + rotEsc : "Outro ciclo"]];
    return painel("Por dia · " + dt(d.consumo.de).slice(0, 5) + " – " + dt(d.consumo.ate).slice(0, 5), '<span class="mc-periodo">' + pilula("periodo", outro, S.periodo) + pop + "</span>", graf, "mc-com-pop") + painel("Por pessoa", ps.length + (ps.length === 1 ? " pessoa" : " pessoas"), pessoas);
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
  function mesesAssinatura(d, ateAtual) {
    var ini = new Date(d.assinatura.desde + "T12:00"), at = new Date(d.assinatura.ciclo.de + "T12:00");
    return [ini.getFullYear() * 12 + ini.getMonth(), at.getFullYear() * 12 + at.getMonth() - (ateAtual ? 0 : 2)];
  }
  function cabFatura() { return '<div class="mc-fat cab"><span>Data</span><span>Descrição</span><span>Forma</span><span class="dir">Valor</span><span>Situação</span><span>NFS-e</span><span class="centro">Arquivos</span></div>'; }
  var SIT_FAT = { paga: ["Paga", "ok"], pendente: ["Pendente", "atencao"], estornada: ["Estornada", "mudo"] };
  function linhaFatura(f) {
    var s = SIT_FAT[f.situacao] || [f.situacao, "mudo"];
    return '<div class="mc-fat"><span class="mono">' + dt(f.data) + '</span><span class="mc-corta">' + esc(f.descricao) + "</span><span>" + forma(f.forma) + '</span><span class="dir mono">' + brl(f.valor) + '</span><span><span class="mc-sit ' + s[1] + '"><span class="mc-bolinha"></span>' + s[0] + '</span></span><span class="mono">' + esc(f.nfse || "—") + "</span>" +
      '<span class="centro mc-arquivos">' + (f.nfse ? '<a class="btn-icone" href="' + esc(f.pdf || "#") + '" title="NFS-e em PDF" aria-label="Baixar a NFS-e em PDF">' + ic("picture_as_pdf") + '</a><a class="btn-icone" href="' + esc(f.xml || "#") + '" title="NFS-e em XML" aria-label="Baixar o XML da NFS-e">' + ic("code") + "</a>" : '<span class="mudo">—</span>') + "</span></div>";
  }
  TELAS.faturas = function (d) {
    var l = d.faturas.filter(function (f) { return (S.filtroFat === "todas" || f.situacao === S.filtroFat) && (!S.mesFat || String(f.data).slice(0, 7) === S.mesFat); });
    var mm = mesesAssinatura(d, true), rotM = S.mesFat ? MESES[Number(S.mesFat.slice(5)) - 1] + "/" + S.mesFat.slice(0, 4) : "";
    var pop = S.calAberto && S.calAberto.alvo === "faturas" ? calPop(mm[0], mm[1], S.mesFat) : "";
    var cab = '<span class="mc-periodo">' + pilula("faturas", [["todas", "Todas"], ["paga", "Pagas"], ["pendente", "Pendentes"]], S.filtroFat) +
      '<div class="segmentos mc-seg"><div><button type="button" class="mc-seg-cal" data-a="mesFatAbrir" aria-pressed="' + !!S.mesFat + '" aria-expanded="' + !!pop + '">' + ic("calendar_month") + "<span>" + (rotM || "Outro período") + "</span></button>" +
      (S.mesFat ? '<button type="button" data-a="mesFatLimpar" aria-label="Tirar o período" title="Tirar o período">' + ic("close") + "</button>" : "") + "</div></div>" + pop + "</span>";
    return painel("Faturas · " + l.length, cab, '<div class="mc-tabela">' + cabFatura() + (l.length ? l.map(linhaFatura).join("") : '<p class="mc-vazio">Nenhuma fatura com esse filtro.</p>') + "</div>" +
      '<div class="mc-pe"><button type="button" class="mini" data-a="baixarTudo">' + ic("download") + "Baixar as NFS-e do ano (.zip)</button></div>", "mc-com-pop") +
      '<p class="mc-nota">A NFS-e sai em até 2 dias úteis depois do pagamento, em nome de ' + esc(d.cadastro.nome) + ".</p>";
  };

  TELAS.pagamento = function (d) {
    var p = d.pagamento, c = p.cartao, rc = d.recarga;
    var formaH = '<div class="mc-corpo"><div class="mc-opcoes" role="radiogroup">' +
      '<button type="button" class="mc-opcao' + (p.tipo === "cartao" ? " on" : "") + '" role="radio" aria-checked="' + (p.tipo === "cartao") + '" data-a="formaPag" data-v="cartao"><span class="mc-radio"></span><span class="mc-txt"><b>Cartão de crédito</b><small>cobrança automática todo mês</small></span>' + (c ? forma(c) : "") + "</button>" +
      '<button type="button" class="mc-opcao' + (p.tipo === "pix" ? " on" : "") + '" role="radio" aria-checked="' + (p.tipo === "pix") + '" data-a="formaPag" data-v="pix"><span class="mc-radio"></span><span class="mc-txt"><b>Pix</b><small>o QR chega por e-mail 3 dias antes de cada cobrança</small></span>' + PIX + "</button></div>" +
      (c ? '<dl class="mc-fatos"><div><dt>Cartão</dt><dd>' + forma(c) + "</dd></div><div><dt>Validade</dt><dd>" + esc(c.validade) + "</dd></div><div><dt>Nome no cartão</dt><dd>" + esc(c.titular) + "</dd></div></dl>" : "") + "</div>" +
      '<div class="mc-pe"><span class="mc-mp">Pagamentos pelo Mercado Pago</span><button type="button" class="mini" data-a="trocarCartao">' + ic("credit_card") + (c ? "Trocar cartão" : "Cadastrar cartão") + "</button></div>";
    var recH;
    if (S.pix) {
      recH = '<div class="mc-corpo mc-pix-gerado"><div class="mc-qr" aria-label="QR Code do Pix">' + ic("qr_code_2") + '</div><div class="mc-pix-lado"><b>' + brl(S.pix.valor) + " · " + tok(S.pix.tokens) + " tokens</b><small>Vale por 30 minutos. Os créditos entram assim que o pagamento cair, e não vencem na renovação.</small>" +
        '<label class="campo-site"><span>Pix copia e cola</span><span class="caixa-campo"><input readonly value="' + esc(S.pix.copia) + '"><button type="button" class="btn-icone" data-a="copiarPix" aria-label="Copiar" title="Copiar">' + ic("content_copy") + "</button></span></label></div></div>" +
        '<div class="mc-pe"><button type="button" class="mc-texto" data-a="pixCancelar">Escolher outro valor</button></div>';
    } else {
      recH = '<div class="mc-corpo"><p class="mc-p">Se a cota do ciclo acabar, a recarga é no Pix, no preço do seu plano: ' + brl0(rc.valor) + " a cada " + tok(rc.tokens) + " tokens.</p>" +
        '<div class="mc-pacotes">' + [1, 2, 3].map(function (n) {
          return '<button type="button" class="mc-pacote' + (S.recarga === n ? " on" : "") + '" data-a="pacote" data-v="' + n + '"><b>' + brl(rc.valor * n) + "</b><small>" + tok(rc.tokens * n) + " tokens</small></button>";
        }).join("") + "</div></div>" +
        '<div class="mc-pe"><span></span><button type="button" class="btn-duplo pequeno" data-a="gerarPix"><span>' + PIX + "Gerar Pix de " + brl0(rc.valor * S.recarga) + "</span></button></div>";
    }
    return '<div class="mc-grade2">' + painel("Forma de pagamento", "", formaH) + painel("Recarga de créditos", "", recH, "mc-recarga") + "</div>";
  };

  TELAS.plano = function (d) {
    var a = d.assinatura, per = S.anual ? "anual" : "mensal";
    var cards = d.planos.map(function (p) {
      var atual = p.id === a.plano && per === a.periodo, preco = S.anual ? p.valor_anual : p.valor;
      return '<div class="mc-plano' + (atual ? " atual" : "") + '"><div class="mc-plano-topo"><b>' + esc(p.nome) + "</b>" + (atual ? '<span class="mc-tag">plano atual</span>' : "") + "</div>" +
        '<div class="mc-preco"><span>' + brl0(preco) + "</span><small>" + (S.anual ? "por ano" : "por mês") + "</small></div>" +
        (S.anual ? '<small class="mc-economia">' + Math.round((1 - p.valor_anual / (p.valor * 12)) * 100) + "% a menos que 12 meses</small>" : "") +
        '<ul class="mc-itens"><li>' + tok(p.tokens) + " tokens por mês</li><li>" + (p.pessoas === 1 ? "1 pessoa" : "até " + p.pessoas + " pessoas") + "</li><li>" + esc((p.modelos_info || []).map(function (m) { return m.nome; }).join(" e ")) + "</li></ul>" +
        (atual ? '<span class="mc-plano-pe mudo">É o que você tem hoje</span>' : '<button type="button" class="mini cheia" data-a="trocarPlano" data-id="' + esc(p.id) + '">Trocar para este</button>') + "</div>";
    }).join("");
    return '<div class="mc-centro">' + pilula("periodoPlano", [["mensal", "Mensal"], ["anual", "Anual"]], per) + "</div>" +
      '<div class="mc-planos">' + cards + "</div>" +
      '<div class="mc-cancelar"><span>Cancelar a assinatura mantém o plano até ' + dt(a.ciclo.ate) + ". Depois, o Paulus abre só com os arquivos.</span>" +
      '<button type="button" class="mc-texto perigo" data-a="cancelar">Cancelar assinatura</button></div>';
  };

  var UFS = "AC AL AP AM BA CE DF ES GO MA MT MS MG PA PB PR PE PI RJ RN RS RO RR SC SP SE TO".split(" ");
  TELAS.cadastro = function (d) {
    var c = d.cadastro;
    var campo = function (k, rot, extra, cls) { return '<label class="campo-site' + (cls ? " " + cls : "") + '"><span>' + rot + '</span><span class="caixa-campo"><input data-cad="' + k + '" value="' + esc(c[k] || "") + '"' + (extra || "") + "></span></label>"; };
    var corpo = '<div class="mc-corpo mc-form">' +
      '<div class="mc-form-grade">' + campo("nome", "Nome ou razão social", "", "largo") + campo("documento", "CPF ou CNPJ", ' inputmode="numeric"') + campo("oab", "OAB") + campo("telefone", "Telefone", ' inputmode="tel"') + campo("email_cobranca", "E-mail das faturas", ' type="email"') + "</div>" +
      '<span class="rotulo mc-sub">Endereço</span>' +
      '<div class="mc-form-grade">' + campo("cep", "CEP", ' inputmode="numeric"') + campo("logradouro", "Logradouro", "", "largo") + campo("numero", "Número") + campo("complemento", "Complemento") + campo("bairro", "Bairro") + campo("cidade", "Cidade") +
      '<label class="campo-site"><span>UF</span><span class="caixa-campo"><select data-cad="uf">' + UFS.map(function (u) { return "<option" + (u === c.uf ? " selected" : "") + ">" + u + "</option>"; }).join("") + "</select>" + ic("expand_more") + "</span></label></div></div>" +
      '<div class="mc-pe"><span class="mc-nota">As próximas NFS-e saem com estes dados.</span><button type="button" class="btn-duplo pequeno" data-a="salvarCadastro"><span>Salvar</span></button></div>';
    return painel("Dados do cadastro", "", corpo);
  };

  TELAS.escritorio = function (d) {
    var e = d.escritorio;
    var end = '<div class="mc-corpo"><div class="mc-endereco"><img class="mc-cf" src="' + MP_IMG + 'cloudflare.svg" alt="Cloudflare" width="24" height="24"><span class="mc-bolinha ' + (e.online ? "ok" : "erro") + '"></span><b class="mono">' + esc(e.slug) + '<span class="mudo">.paulus.ia.br</span></b><span class="mc-sit ' + (e.online ? "ok" : "erro") + '">' + (e.online ? "no ar" : "fora do ar") + "</span></div>" +
      '<p class="mc-p">É por este endereço que a equipe e os clientes entram no Paulus do escritório, pelo túnel do Cloudflare.</p></div>' +
      '<div class="mc-pe"><a class="mini" href="https://' + esc(e.slug) + '.paulus.ia.br" target="_blank" rel="noopener">' + ic("arrow_outward") + "Abrir</a>" + '<button type="button" class="mini" data-a="alterarEndereco">' + ic("edit") + "Alterar endereço</button></div>";
    var inst = d.instalacoes.map(function (i) {
      return '<div class="mc-linha"><span class="mc-linha-ic">' + ic("computer") + '</span><span class="mc-txt"><b>' + esc(i.nome) + (i.principal ? ' <span class="mc-tag">principal</span>' : "") + "</b><small>versão " + esc(i.versao) + " · último acesso " + esc(i.ultimo) + "</small></span>" +
        (i.principal ? "" : '<button type="button" class="btn-icone" data-a="removerInstalacao" data-id="' + esc(i.id) + '" aria-label="Tirar ' + esc(i.nome) + '" title="Tirar este computador">' + ic("delete") + "</button>") + "</div>";
    }).join("");
    // O mesmo card das Permissoes do Google do Admin (que veio das Conexoes do assistente): a conta e uma linha por servico, com a marca.
    var g = d.google, lig = {}; g.servicos.forEach(function (s) { lig[s.id] = !!s.ligado; });
    var linhaG = function (id, marca, nome, desc, junto) {
      var on = lig[id];
      return '<div class="g-servico' + (on ? " on" : "") + (junto ? " junto" : "") + '"' + (junto ? ' title="Vem com a Agenda: a mesma permissão"' : ' role="switch" tabindex="0" aria-checked="' + on + '" aria-label="' + esc(nome + ", " + desc) + '" data-a="servico" data-id="' + id + '"') + ">" +
        '<span class="g-marca">' + SIMB_G[marca] + '</span><span class="g-nome">' + esc(nome) + '</span><span class="g-desc">' + esc(desc) + '</span><span class="interruptor-min' + (on ? " on" : "") + '"></span></div>';
    };
    var perm = '<div class="mc-corpo"><span class="rotulo">Conta</span><div class="g-conta"><span class="g-marca">' + SIMB_G.google + '</span><span class="mc-txt"><b>' + esc(d.cadastro.nome) + "</b><small>" + esc(g.conta) + '</small></span><span class="etiqueta-ok">conectado</span></div>' +
      '<span class="rotulo">O que autorizar</span><div class="g-servicos">' +
      linhaG("gmail", "gmail", "Gmail", "ler e enviar, com Aprovações") + linhaG("agenda", "agenda", "Agenda", "ler e criar eventos") + linhaG("agenda", "meet", "Meet", "criar reuniões nos eventos", true) +
      linhaG("drive_enviar", "drive", "Drive", "só os arquivos que o Paulus envia") + linhaG("drive_ler", "drive", "Drive", "ler as pastas escolhidas") + "</div>" +
      '<p class="mc-nota">Desligar um serviço revoga só esse acesso no Google, na hora.</p></div>' +
      '<div class="mc-pe g-desv"><span class="mc-txt"><b>Desvincular a conta Google</b><small>Revoga todas as permissões de uma vez.</small></span><button type="button" class="mc-perigo mini-perigo" data-a="desvincular">Desvincular</button></div>';
    return painel("Endereço do escritório", "", end) + '<div class="mc-grade2">' + painel("Instalações", d.instalacoes.length + (d.instalacoes.length === 1 ? " computador" : " computadores"), inst) + painel("Permissões Google", "", perm) + "</div>";
  };

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
    return painel("Quem entra em Minha conta", '<button type="button" class="mini cheia" data-a="convidar">' + ic("person_add") + "Convidar</button>", l) +
      '<p class="mc-nota centro">O financeiro vê o resumo, o consumo, as faturas e a forma de pagamento. Trocar de plano, cancelar e mexer no escritório são só do titular.</p>';
  };

  /* ------------------------------------------------------------ trocar o cartao: pagina propria, com os campos seguros do Mercado Pago */
  function bandDe(n) {
    if (/^(4011|4312|4389|4514|4576|5041|5066|5067|509|6277|6362|6363|650|6516|6550)/.test(n)) return "elo";
    if (/^(606282|3841)/.test(n)) return "hipercard";
    if (/^4/.test(n)) return "visa";
    if (/^(5[1-5]|2[2-7])/.test(n)) return "mastercard";
    if (/^3[47]/.test(n)) return "amex";
    return "";
  }
  function bandSlot(n) { var b = bandDe(n); return b ? '<span class="mc-k-surge">' + bandeira(b) + "</span>" : ic("credit_card"); }
  function luhn(n) { var s = 0, dbl = false; for (var k = n.length - 1; k >= 0; k--) { var x = Number(n[k]); if (dbl) { x *= 2; if (x > 9) x -= 9; } s += x; dbl = !dbl; } return s % 10 === 0; }
  function cartaoValido() {
    var K = S.cartao; if (!K) return false;
    var m = /^(\d{2})\/(\d{2})$/.exec(K.val), agora = new Date(), mesOk = false;
    if (m) { var mm = Number(m[1]), aa = 2000 + Number(m[2]); mesOk = mm >= 1 && mm <= 12 && (aa * 12 + mm) >= (agora.getFullYear() * 12 + agora.getMonth() + 1); }
    var doc = K.doc.replace(/\D/g, "");
    return K.num.length >= 13 && luhn(K.num) && mesOk && /^\d{3,4}$/.test(K.cvv) && K.nome.trim().length >= 3 && (doc.length === 11 || doc.length === 14);
  }
  function cartaoOk() { var b = $("mc-cartao-salvar"); if (b) b.disabled = !cartaoValido(); }
  // As imagens ficam em site/assets/: a pagina real esta em /minha-conta/ e a demonstracao na raiz do projeto.
  var MP_IMG = /\/en\/my-account\//.test(location.pathname) ? "../../assets/" : /\/minha-conta\//.test(location.pathname) ? "../assets/" : "site/assets/";
  function cartaoHtml(d) {
    var c = d.pagamento.cartao, K = S.cartao || (S.cartao = { num: "", val: "", cvv: "", nome: "", doc: d.cadastro.documento || "" });
    var campo = function (id, k, rot, extra, val) { return '<label class="campo-site"><span>' + rot + '</span><span class="caixa-campo"><input id="' + id + '" data-a-in="' + k + '" value="' + esc(val) + '"' + extra + ">" + (k === "kNum" ? '<span id="mc-k-band" class="mc-k-band">' + bandSlot(K.num) + "</span>" : "") + "</span></label>"; };
    var form = '<div class="mc-corpo mc-form">' +
      campo("mc-k-num", "kNum", "Número do cartão", ' inputmode="numeric" autocomplete="cc-number" placeholder="0000 0000 0000 0000"', K.num.replace(/(.{4})(?=.)/g, "$1 ")) +
      '<div class="mc-k-grade">' + campo("mc-k-val", "kVal", "Validade", ' inputmode="numeric" autocomplete="cc-exp" placeholder="MM/AA"', K.val) +
      campo("mc-k-cvv", "kCvv", "Código de segurança", ' inputmode="numeric" autocomplete="cc-csc" placeholder="' + (bandDe(K.num) === "amex" ? "4 dígitos" : "3 dígitos") + '"', K.cvv) + "</div>" +
      campo("mc-k-nome", "kNome", "Nome impresso no cartão", ' autocomplete="cc-name" spellcheck="false"', K.nome) +
      campo("mc-k-doc", "kDoc", "CPF ou CNPJ do titular do cartão", ' inputmode="numeric"', K.doc) + "</div>" +
      '<div class="mc-pe"><button type="button" class="mc-texto" data-a="cartaoVoltar">Cancelar</button><button type="button" class="btn-duplo pequeno" id="mc-cartao-salvar" data-a="cartaoSalvar"' + (cartaoValido() ? "" : " disabled") + "><span>" + ic("lock") + "Salvar cartão</span></button></div>";
    return '<div class="mc-col mc-col-estreita"><button type="button" class="mc-voltar" data-a="cartaoVoltar">← Voltar</button>' +
      '<header class="mc-cab"><h1>Trocar o cartão</h1><p class="texto-lead">' + (c ? "Hoje as cobranças saem no " + forma(c) + ". " : "") + "A próxima, em " + dt(d.assinatura.proxima) + ", já sai no cartão novo.</p></header>" +
      painel("Cartão novo", "", form) +
      '<div class="selo"><span class="selo-esq"><span class="selo-mp"><img class="mp-pluma" src="' + MP_IMG + 'mercadopago-pluma.png" alt="" width="57" height="23"><img class="mp-cor" src="' + MP_IMG + 'mercadopago-cor.png" alt="" width="57" height="23"></span>Campos seguros do Mercado Pago</span><span class="selo-dir"><span>Cartão</span></span></div>' +
      '<p class="mc-nota centro">O número, a validade e o código vão direto para o Mercado Pago. O PAVLVS guarda só a bandeira e os 4 últimos dígitos.</p></div>';
  }

  /* ------------------------------------------------------------ os pop-ups (o dialogo do Paulus) */
  function dialogo(tit, ctx, corpo, pe) {
    return '<div class="mc-veu" data-a="fechar"></div><div class="mc-dialogo" role="dialog" aria-modal="true" aria-labelledby="mc-dlg-tit"><div class="mc-dlg-cab"><span class="mc-dlg-titulos"><h2 id="mc-dlg-tit">' + esc(tit) + "</h2>" + (ctx ? "<span>" + esc(ctx) + "</span>" : "") + '</span><button type="button" class="btn-icone" data-a="fechar" aria-label="Fechar">' + ic("close") + '</button></div><div class="mc-dlg-corpo">' + corpo + '</div><div class="mc-dlg-pe"><span class="mc-cresce"></span>' + pe + "</div></div>";
  }
  var MOTIVOS = [["preco", "Está caro para o escritório"], ["uso", "Não estamos usando o bastante"], ["falta", "Falta algo de que precisamos"], ["outro", "Outro motivo"]];
  // Disponibilidade do endereco, conferida enquanto a pessoa digita (espera 350 ms sem tecla para perguntar ao servidor).
  var SLUG_OK = /^[a-z0-9](?:[a-z0-9-]{1,22}[a-z0-9])$/, slugT = null;
  // As frases curtas do Admin (Alterar endereco), com a bolinha da cor do estado.
  function endStatus(M) {
    var v = M.v || "", atual = S.d.escritorio.slug, C = M.check || {}, f = function (cls, msg, ok) { return { cls: cls, icone: "", msg: msg ? "<i></i>" + msg : "", ok: !!ok }; };
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
  function endAtualizar() {
    var M = S.modal; if (!M || M.tipo !== "endereco") return; var st = endStatus(M);
    var cx = $("mc-slug-caixa"), ico = $("mc-slug-st"), msg = $("mc-slug-msg"), b = $("mc-end-ok");
    if (cx) cx.className = "caixa-campo mono mc-slug-caixa" + (st.cls ? " " + st.cls : "");
    if (msg) { msg.className = "mc-slug-msg " + st.cls; msg.innerHTML = st.msg; }
    if (b) b.disabled = !st.ok;
  }
  function modalHtml() {
    var M = S.modal, d = S.d; if (!M) return "";
    var cancel = '<button type="button" class="mc-texto" data-a="fechar">Cancelar</button>';
    if (M.tipo === "trocarPlano") {
      var p = d.planos.filter(function (x) { return x.id === M.id; })[0], novo = S.anual ? p.valor_anual : p.valor;
      return dialogo("Trocar para o " + p.nome + "?", "Plano · " + (S.anual ? "anual" : "mensal"),
        "<p>A troca vale a partir de hoje. A diferença deste ciclo é calculada pelos dias que faltam e entra na próxima cobrança, em " + dt(d.assinatura.proxima) + ".</p>" +
        '<dl class="mc-fatos"><div><dt>Hoje</dt><dd>' + esc(d.assinatura.nome) + " · " + brl0(d.assinatura.valor) + (d.assinatura.periodo === "anual" ? "/ano" : "/mês") + "</dd></div><div><dt>Novo</dt><dd>" + esc(p.nome) + " · " + brl0(novo) + (S.anual ? "/ano" : "/mês") + "</dd></div><div><dt>Tokens</dt><dd>" + tok(p.tokens) + " por mês</dd></div></dl>",
        cancel + '<button type="button" class="btn-duplo pequeno" data-a="confirmarTroca"><span>Trocar de plano</span></button>');
    }
    if (M.tipo === "cancelar") {
      if (M.passo === 1) return dialogo("Por que você quer cancelar?", "Cancelar assinatura",
        '<div class="mc-opcoes">' + MOTIVOS.map(function (m) { return '<button type="button" class="mc-opcao' + (M.motivo === m[0] ? " on" : "") + '" role="radio" aria-checked="' + (M.motivo === m[0]) + '" data-a="motivo" data-v="' + m[0] + '"><span class="mc-radio"></span><span class="mc-txt"><b>' + m[1] + "</b></span></button>"; }).join("") + "</div>" +
        '<label class="campo-site"><span>Quer contar mais? (opcional)</span><span class="caixa-campo"><input data-a-in="motivoTexto" value="' + esc(M.texto || "") + '"></span></label>',
        cancel + '<button type="button" class="btn-duplo pequeno" data-a="cancelarPasso" data-v="2"' + (M.motivo ? "" : " disabled") + "><span>Continuar</span></button>");
      if (M.passo === 2) {
        var credito = M.motivo === "uso" || M.motivo === "falta";
        return dialogo(credito ? "Antes de sair: 20 M de tokens por nossa conta" : "Antes de sair: 30% a menos por 2 meses", "Cancelar assinatura",
          "<p>" + (credito ? "Entram agora no ciclo, sem custo, para você testar o que ainda não usou. O plano continua igual." : "As duas próximas cobranças do " + esc(d.assinatura.nome) + " saem por " + brl0(d.assinatura.valor * 0.7) + ". Depois, volta ao preço do plano.") + "</p>",
          '<button type="button" class="mc-texto perigo" data-a="cancelarPasso" data-v="3">Cancelar mesmo assim</button><button type="button" class="btn-duplo pequeno" data-a="aceitarOferta" data-v="' + (credito ? "creditos" : "desconto") + '"><span>Aceitar a oferta</span></button>');
      }
      return dialogo("Cancelar a assinatura?", "Cancelar assinatura",
        "<p>O " + esc(d.assinatura.nome) + " fica ativo até <b>" + dt(d.assinatura.ciclo.ate) + "</b>. Depois disso, o Paulus abre só com os arquivos: sem respostas da IA, sem NFS-e e sem os demais serviços. Ao assinar de novo, volta tudo, sem reinstalar.</p>",
        '<button type="button" class="mc-texto" data-a="cancelarPasso" data-v="2">Voltar</button><button type="button" class="mc-perigo" data-a="confirmarCancelar">Cancelar assinatura</button>');
    }
    if (M.tipo === "endereco") {
      var st = endStatus(M);
      return dialogo("Alterar o endereço", "Escritório",
        '<div class="campo-site"><label for="mc-slug">Endereço novo</label><span class="caixa-campo mono mc-slug-caixa' + (st.cls ? " " + st.cls : "") + '" id="mc-slug-caixa"><input id="mc-slug" data-a-in="slug" value="' + esc(M.v || "") + '" spellcheck="false" autocomplete="off" aria-describedby="mc-slug-msg"><span class="mudo">.paulus.ia.br</span></span>' +
        '<p class="mc-slug-msg ' + st.cls + '" id="mc-slug-msg" role="status" aria-live="polite">' + st.msg + "</p></div>" +
        '<div class="selo selo-cf"><span class="selo-esq"><img src="' + MP_IMG + 'cloudflare.svg" alt="" width="22" height="22">Túnel do Cloudflare</span><span class="selo-dir"><span>conexão protegida</span></span></div>' +
        '<p class="mc-nota">O endereço atual, ' + esc(d.escritorio.slug) + ".paulus.ia.br, deixa de funcionar na hora. Avise a equipe e os clientes.</p>",
        cancel + '<button type="button" class="btn-duplo pequeno" id="mc-end-ok" data-a="confirmarEndereco"' + (st.ok ? "" : " disabled") + "><span>Alterar</span></button>");
    }
    if (M.tipo === "convidar") {
      var okE = /^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(M.email || "");
      return dialogo("Convidar para Minha conta", "Pessoas",
        '<label class="campo-site"><span>E-mail Google da pessoa</span><span class="caixa-campo"><input id="mc-conv" type="email" data-a-in="convEmail" value="' + esc(M.email || "") + '" placeholder="nome@escritorio.com.br" autocomplete="off"></span></label>' +
        "<p>Entra como <b>financeiro</b>: vê o resumo, o consumo, as faturas e a forma de pagamento. Ela recebe um e-mail com o link, válido por 7 dias.</p>",
        cancel + '<button type="button" class="btn-duplo pequeno" data-a="confirmarConvite"' + (okE ? "" : " disabled") + "><span>Enviar convite</span></button>");
    }
    if (M.tipo === "confirmar") return dialogo(M.titulo, M.ctx, "<p>" + M.texto + "</p>", cancel + '<button type="button" class="mc-perigo" data-a="confirmarSim">' + esc(M.botao) + "</button>");
    return "";
  }

  /* ------------------------------------------------------------ pintar */
  function render() {
    var r = $("mc-raiz"); if (!r) return;
    if (!S.d) { r.innerHTML = '<div class="mc-carregando">Carregando…</div>'; return; }
    if (S.d.entrar) { r.innerHTML = entrarHtml(); return; }
    if (S.sub === "cartao") { r.innerHTML = cartaoHtml(S.d); renderModal(); return; }
    var lista = abas(); if (!lista.some(function (a) { return a[0] === S.aba; })) S.aba = "resumo";
    var a = S.d.assinatura;
    var h = '<div class="mc-col"><header class="mc-cab"><h1>Minha conta</h1><p class="texto-lead">' + esc(S.d.cadastro.nome) + " · plano " + esc(a.nome) + " · " + esc(S.d.perfil.email) + (titular() ? "" : " (financeiro)") + "</p></header>" +
      '<div class="mc-centro">' + pilula("aba", lista, S.aba) + "</div>" +
      '<div class="mc-tela" data-tela="' + S.aba + '">' + TELAS[S.aba](S.d) + "</div></div>";
    r.innerHTML = h;
    var c = $("mc-camada"); if (!c) { c = document.createElement("div"); c.id = "mc-camada"; document.body.appendChild(c); }
    c.innerHTML = modalHtml();
  }
  function renderModal() { var c = $("mc-camada"); if (c) c.innerHTML = modalHtml(); }
  function entrarHtml() {
    return '<div class="mc-entrar"><h1>Minha conta</h1><p class="texto-lead">Entre com a conta Google da assinatura, ou com a que o titular autorizou. Nenhuma senha a mais.</p>' +
      '<button type="button" class="btn-duplo" data-a="entrarGoogle"><span>' + GOOGLE + "Entrar com o Google</span></button>" +
      '<p class="mc-nota centro">Ainda não assina? <a href="' + (MP_IMG === "../../assets/" ? "../../assinatura/" : MP_IMG === "../assets/" ? "../assinatura/" : "Site - Assinatura.dc.html") + '">Conheça os planos</a>.</p></div>';
  }

  /* ------------------------------------------------------------ acoes */
  var A = {
    fechar: function () { S.modal = null; renderModal(); },
    recarga: function () { S.aba = "pagamento"; render(); },
    pacote: function (el) { S.recarga = Number(el.dataset.v); render(); },
    gerarPix: function () {
      var rc = S.d.recarga, n = S.recarga;
      api("POST", "/api/conta/recarga", { pacotes: n }).then(function (j) { S.pix = { valor: rc.valor * n, tokens: rc.tokens * n, copia: j.copia || "00020126580014br.gov.bcb.pix0136pavlvs-recarga-" + Date.now() + "5204000053039865802BR6304ABCD" }; render(); })
        .catch(function (e) { toast(e.message, true); });
    },
    pixCancelar: function () { S.pix = null; render(); },
    copiarPix: function () { try { navigator.clipboard.writeText(S.pix.copia); toast("Código do Pix copiado"); } catch (e) { toast("Copie o código no campo", true); } },
    formaPag: function (el) { var v = el.dataset.v; if (S.d.pagamento.tipo === v) return; S.d.pagamento.tipo = v; render(); api("POST", "/api/conta/forma", { tipo: v }).then(function () { toast(v === "pix" ? "As próximas cobranças saem no Pix" : "As próximas cobranças saem no cartão"); }).catch(function (e) { toast(e.message, true); }); },
    trocarCartao: function () { S.sub = "cartao"; S.cartao = null; window.scrollTo(0, 0); try { history.replaceState(null, "", "#cartao"); } catch (e) {} render(); setTimeout(function () { var i = $("mc-k-num"); if (i) i.focus(); }, 30); },
    cartaoVoltar: function () { S.sub = null; S.cartao = null; S.aba = "pagamento"; window.scrollTo(0, 0); try { history.replaceState(null, "", "#pagamento"); } catch (e) {} render(); },
    cartaoSalvar: function (el) {
      // Na pagina real, os campos sao os Secure Fields do Mercado Pago: o SDK gera o token do cartao e so o token chega aqui.
      var K = S.cartao; if (!cartaoValido()) return; el.disabled = true;
      api("POST", "/api/conta/cartao", { token: "card_token_demo", ultimos: K.num.slice(-4), bandeira: bandDe(K.num) }).then(function () {
        var p = S.d.pagamento; p.tipo = "cartao"; p.cartao = { bandeira: bandDe(K.num) || "Cartão", final: K.num.slice(-4), validade: K.val, titular: K.nome.trim().toUpperCase() };
        var fim = K.num.slice(-4); A.cartaoVoltar(); toast("Cartão trocado. As próximas cobranças saem no final " + fim);
      }).catch(function (e) { el.disabled = false; toast(e.message, true); });
    },
    trocarPlano: function (el) { S.modal = { tipo: "trocarPlano", id: el.dataset.id }; renderModal(); },
    confirmarTroca: function () {
      var M = S.modal, p = S.d.planos.filter(function (x) { return x.id === M.id; })[0];
      api("POST", "/api/conta/plano", { plano: p.id, periodo: S.anual ? "anual" : "mensal" }).then(function () {
        var a = S.d.assinatura; a.plano = p.id; a.nome = p.nome; a.periodo = S.anual ? "anual" : "mensal"; a.valor = S.anual ? p.valor_anual : p.valor; a.ciclo.tokens = p.tokens;
        S.modal = null; render(); toast("Plano trocado para o " + p.nome);
      }).catch(function (e) { toast(e.message, true); });
    },
    cancelar: function () { S.modal = { tipo: "cancelar", passo: 1, motivo: null, texto: "" }; renderModal(); },
    motivo: function (el) { S.modal.motivo = el.dataset.v; renderModal(); },
    cancelarPasso: function (el) { S.modal.passo = Number(el.dataset.v); renderModal(); },
    aceitarOferta: function (el) {
      var v = el.dataset.v; api("POST", "/api/conta/oferta", { tipo: v, motivo: S.modal.motivo }).then(function () {
        if (v === "creditos") S.d.assinatura.ciclo.tokens += 20e6;
        S.modal = null; render(); toast(v === "creditos" ? "20 M de tokens entraram no ciclo" : "As duas próximas cobranças saem com 30% a menos");
      }).catch(function (e) { toast(e.message, true); });
    },
    confirmarCancelar: function () {
      var M = S.modal; api("POST", "/api/conta/cancelar", { motivo: M.motivo, texto: M.texto }).then(function () {
        S.modal = null; render(); toast("Assinatura cancelada. O plano fica ativo até " + dt(S.d.assinatura.ciclo.ate));
      }).catch(function (e) { toast(e.message, true); });
    },
    salvarCadastro: function () {
      var v = {}; document.querySelectorAll("[data-cad]").forEach(function (i) { v[i.dataset.cad] = i.value.trim(); });
      api("POST", "/api/conta/cadastro", v).then(function () { Object.assign(S.d.cadastro, v); toast("Cadastro salvo"); }).catch(function (e) { toast(e.message, true); });
    },
    alterarEndereco: function () { S.modal = { tipo: "endereco", v: "" }; renderModal(); setTimeout(function () { var i = $("mc-slug"); if (i) i.focus(); }, 30); },
    confirmarEndereco: function () {
      if (!endStatus(S.modal).ok) return; var v = S.modal.v; api("POST", "/api/conta/endereco", { slug: v }).then(function () { S.d.escritorio.slug = v; S.modal = null; render(); toast("Endereço alterado para " + v + ".paulus.ia.br"); }).catch(function (e) { toast(e.message, true); });
    },
    removerInstalacao: function (el) {
      var i = S.d.instalacoes.filter(function (x) { return x.id === el.dataset.id; })[0];
      S.modal = { tipo: "confirmar", titulo: "Tirar este computador?", ctx: "Instalações", texto: esc(i.nome) + " deixa de abrir o Paulus do escritório. Para usar de novo, é preciso entrar com a conta Google no programa.", botao: "Tirar", fazer: function () { return api("POST", "/api/conta/instalacoes/" + encodeURIComponent(i.id) + "/remover", {}).then(function () { S.d.instalacoes = S.d.instalacoes.filter(function (x) { return x !== i; }); toast("Computador tirado"); }); } };
      renderModal();
    },
    servico: function (el) {
      var s = S.d.google.servicos.filter(function (x) { return x.id === el.dataset.id; })[0]; s.ligado = !s.ligado; render();
      api("POST", "/api/conta/google/servico", { id: s.id, ligado: s.ligado }).then(function () { toast(s.nome + (s.ligado ? " ligado" : " desligado")); }).catch(function (e) { s.ligado = !s.ligado; render(); toast(e.message, true); });
    },
    desvincular: function () {
      S.modal = { tipo: "confirmar", titulo: "Desvincular a conta Google?", ctx: "Permissões Google", texto: "O Paulus perde o acesso ao Gmail, à Agenda e ao Drive de " + esc(S.d.google.conta) + ". Para ligar de novo, faça o consentimento no programa.", botao: "Desvincular", fazer: function () { return api("POST", "/api/conta/google/desvincular", {}).then(function () { S.d.google.servicos.forEach(function (s) { s.ligado = false; }); toast("Conta Google desvinculada"); }); } };
      renderModal();
    },
    convidar: function () { S.modal = { tipo: "convidar", email: "" }; renderModal(); setTimeout(function () { var i = $("mc-conv"); if (i) i.focus(); }, 30); },
    confirmarConvite: function () {
      var em = S.modal.email.trim(); api("POST", "/api/conta/pessoas", { email: em, papel: "financeiro" }).then(function () { S.d.pessoas.push({ email: em, papel: "financeiro", convite: true }); S.modal = null; render(); toast("Convite enviado para " + em); }).catch(function (e) { toast(e.message, true); });
    },
    removerPessoa: function (el) {
      var p = S.d.pessoas.filter(function (x) { return x.email === el.dataset.id; })[0];
      S.modal = { tipo: "confirmar", titulo: p.convite ? "Cancelar o convite?" : "Tirar o acesso?", ctx: "Pessoas", texto: esc(p.nome || p.email) + (p.convite ? " não vai mais poder usar o link." : " deixa de entrar em Minha conta."), botao: p.convite ? "Cancelar convite" : "Tirar o acesso", fazer: function () { return api("POST", "/api/conta/pessoas/" + encodeURIComponent(p.email) + "/remover", {}).then(function () { S.d.pessoas = S.d.pessoas.filter(function (x) { return x !== p; }); toast("Acesso tirado"); }); } };
      renderModal();
    },
    confirmarSim: function (el) { var M = S.modal; el.disabled = true; M.fazer().then(function () { S.modal = null; render(); }).catch(function (e) { el.disabled = false; toast(e.message, true); }); },
    calMes: function (el) {
      if (S.calAberto && S.calAberto.alvo === "faturas") { S.mesFat = el.dataset.v; S.calAberto = null; render(); return; }
      S.cicloEsc = el.dataset.v; S.periodo = "outro"; S.calAberto = null; render(); carregarConsumo(el.dataset.v);
    },
    mesFatAbrir: function () { S.calAberto = S.calAberto ? null : { ano: S.mesFat ? Number(S.mesFat.slice(0, 4)) : new Date().getFullYear(), vista: "meses", alvo: "faturas" }; render(); },
    mesFatLimpar: function () { S.mesFat = null; S.calAberto = null; render(); },
    calAnoPasso: function (el) { S.calAberto.ano += Number(el.dataset.v) * (S.calAberto.vista === "anos" ? 12 : 1); render(); },
    calVistaAnos: function () { S.calAberto.vista = "anos"; render(); },
    calAno: function (el) { S.calAberto.ano = Number(el.dataset.v); S.calAberto.vista = "meses"; render(); },
    baixarTudo: function () { toast("O .zip com as NFS-e do ano está sendo preparado"); },
    entrarGoogle: function () { api("POST", "/api/conta/entrar", {}).then(function (j) { if (j.url) location.assign(j.url); else carregar(); }).catch(function (e) { toast(e.message, true); }); },
  };
  var ENTRADAS = {
    kNum: function (el) {
      var d = el.value.replace(/\D/g, "").slice(0, bandDe(el.value.replace(/\D/g, "")) === "amex" ? 15 : 19), antes = bandDe(S.cartao.num);
      el.value = bandDe(d) === "amex" ? d.replace(/^(\d{4})(\d{1,6})?(\d{1,5})?$/, function (_, a, b, c) { return [a, b, c].filter(Boolean).join(" "); }) : d.replace(/(.{4})(?=.)/g, "$1 ");
      S.cartao.num = d; var b = $("mc-k-band"); if (b && antes !== bandDe(d)) b.innerHTML = bandSlot(d);
      var cvv = $("mc-k-cvv"); if (cvv) cvv.placeholder = bandDe(d) === "amex" ? "4 dígitos" : "3 dígitos";
      cartaoOk();
    },
    kVal: function (el) { var d = el.value.replace(/\D/g, "").slice(0, 4); el.value = d.length > 2 ? d.slice(0, 2) + "/" + d.slice(2) : d; S.cartao.val = el.value; cartaoOk(); },
    kCvv: function (el) { el.value = el.value.replace(/\D/g, "").slice(0, 4); S.cartao.cvv = el.value; cartaoOk(); },
    kNome: function (el) { S.cartao.nome = el.value; cartaoOk(); },
    kDoc: function (el) { S.cartao.doc = el.value; cartaoOk(); },
    motivoTexto: function (el) { S.modal.texto = el.value; },
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
    convEmail: function (el) { S.modal.email = el.value; var b = document.querySelector('[data-a="confirmarConvite"]'); if (b) b.disabled = !/^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(el.value); },
  };
  var SEGS = {
    aba: function (v) { S.aba = v; S.pix = null; S.calAberto = null; window.scrollTo(0, 0); try { history.replaceState(null, "", "#" + v); } catch (e) {} },
    faturas: function (v) { S.filtroFat = v; S.calAberto = null; },
    periodo: function (v) {
      if (v === "outro") { var base = S.cicloEsc ? Number(S.cicloEsc.slice(0, 4)) : new Date(S.d.assinatura.ciclo.de + "T12:00").getFullYear(); S.calAberto = S.calAberto ? null : { ano: base, vista: "meses", alvo: "consumo" }; return; }
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
  document.addEventListener("keydown", function (ev) { var sw = ev.target.closest && ev.target.closest('[role="switch"][data-a]'); if (sw && (ev.key === "Enter" || ev.key === " ")) { ev.preventDefault(); sw.click(); } });
  document.addEventListener("keydown", function (ev) { if (ev.key === "Escape") { if (S.modal) A.fechar(); else if (S.calAberto) { S.calAberto = null; render(); } } });
  document.addEventListener("mousedown", function (ev) { if (S.calAberto && !ev.target.closest(".mc-periodo")) { S.calAberto = null; render(); } });

  function carregarConsumo(v) { api("GET", "/api/conta/consumo?ciclo=" + v).then(function (j) { S.d.consumo = j; render(); }).catch(function () { /* fica o que tinha */ }); }
  function carregar() {
    api("GET", "/api/conta").then(function (d) { S.d = d; render(); })
      .catch(function (e) { S.d = e.status === 401 ? { entrar: true } : { entrar: true }; render(); });
  }
  function iniciar(op) {
    op = op || {};
    var h = (location.hash || "").slice(1); if (op.aba) S.aba = op.aba; else if (h) S.aba = h;
    if (S.aba === "cartao") { S.aba = "pagamento"; S.sub = "cartao"; }
    render(); carregar();
  }
  window.MinhaConta = { iniciar: iniciar };
})();
