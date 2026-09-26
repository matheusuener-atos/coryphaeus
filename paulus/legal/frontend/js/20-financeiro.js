/* ------------------------ financeiro, relatórios, bem-estar, conexões */
/*
   As telas que precisam de história. Todo número aqui é soma do que já está
   gravado — quando não há lançamento, o número é zero e a tela diz que está
   vazio, em vez de desenhar um gráfico bonito de dado que ninguém digitou.
*/


/* --------------------------------------------------------- financeiro */
/*
   Financeiro (docs/ui/03-telas-desktop.md, A9): Visao geral, Lancamentos e
   Relatorios numa tela so. Desde o redesenho de 26/09/2026 a tela e uma
   coluna de leitura, na medida de Servicos e da caixa de E-mail (sv-medida),
   sem painel ao lado: os numeros numa ficha em faixa, e todo cadastro -
   lancamento, nota, boleto, folha - abre num pop-up (16-dialogos.js).
   Todo numero continua sendo soma do que esta gravado; o que ainda nao tem
   motor (cobrar por WhatsApp, gerar boleto, emitir nota) nao aparece como
   se tivesse.
*/

const fin = {
  visao: "geral", mes: "", dados: null, lista: null, todos: null,
  filtro: "todos", categoria: "", aberto: null, form: null, formVez: 0,
  pedidos: [], pedidosTodos: false, rel: null, relAba: "financeiro",
  parecer: null, parecerErro: "", pedindo: false, numerosAbertos: false, escolhidos: new Set(),
  // O extrato lido do banco e o que a pessoa marcou nele. Vive so na tela: o
  // arquivo do banco nao fica guardado, e a conferencia so vira dado depois
  // do sim, como lancamento liquidado.
  extrato: null, baixas: new Set(), novos: new Set(),
};

const FIN_JSON = { "Content-Type": "application/json" };

async function mostrarFinanceiro(visao) {
  if (visao) fin.visao = visao;
  abrirTela("Financeiro", { cheia: true });
  marcarDestino("financeiro");
  $("centro").innerHTML = '<div class="acervo sem-painel"><div class="acervo-principal sv-principal"><div class="sv-medida"><p class="nota">somando…</p></div></div></div>';
  atualizarPostura();
  try {
    await carregarFinanceiro();
  } catch (err) {
    $("centro").innerHTML = '<div class="acervo sem-painel"><div class="acervo-principal sv-principal"><div class="sv-medida"><p class="nota">não consegui abrir: ' +
      esc(String(err)) + "</p></div></div></div>";
    return;
  }
  desenharFinanceiro();
  // Quem chega com um lancamento pronto (Cobrar, em Servicos) ve o cadastro
  // aberto no pop-up.
  if (fin.form && !document.getElementById("fin-form-pop")) finAbrirForm();
}

/* O destino antigo Relatorios virou a terceira visao do Financeiro. */
function mostrarRelatorios() { return mostrarFinanceiro("relatorios"); }

async function carregarFinanceiro() {
  const d = await (await fetch("/api/financeiro?mes=" + encodeURIComponent(fin.mes || ""))).json();
  fin.dados = d;
  fin.mes = d.painel.mes;
  const pedidos = [fetch("/api/financeiro/lancamentos?tipo=&mes=&situacao=").then((r) => r.json())];
  if (fin.visao === "relatorios") {
    pedidos.push(fetch("/api/relatorios?quando=" + encodeURIComponent(quandoDoRelatorio())).then((r) => r.json()));
  }
  const [todos, rel] = await Promise.all(pedidos);
  fin.todos = todos.lancamentos || [];
  // Um lancamento pertence ao mes em que vence; sem vencimento, ao mes em
  // que foi liquidado. E a mesma regra do servidor.
  fin.lista = fin.todos.filter((l) => mesDoLancamento(l) === fin.mes);
  if (rel) fin.rel = rel;
}

function desenharFinanceiro() {
  cabecalhoFinanceiro();
  const antes = document.querySelector("#financeiro .sv-principal");
  const chave = fin.visao + ":" + fin.mes;
  const topo = antes && antes.dataset.finChave === chave ? antes.scrollTop : 0;
  let miolo;
  if (fin.visao === "lancamentos") miolo = corpoDosLancamentos();
  else if (fin.visao === "relatorios") miolo = corpoDosRelatorios();
  else miolo = corpoDaVisaoGeral();
  $("centro").innerHTML = '<div class="acervo sem-painel fin-tela" id="financeiro"><div class="acervo-principal sv-principal" data-fin-chave="' +
    esc(chave) + '"><div class="sv-medida">' + miolo + "</div></div></div>";
  const depois = document.querySelector("#financeiro .sv-principal");
  if (depois && topo) depois.scrollTop = topo;
  ligarFinanceiro(document);
  atualizarPostura();
}

/* ------------------------------------------------------ o cabecalho */

function cabecalhoFinanceiro() {
  const p = fin.dados.painel;
  const titulo = $("conversa-titulo");
  const meta = $("conversa-meta");
  const mesRotulo = maiuscula(p.mes_rotulo);
  if (fin.visao === "lancamentos") {
    titulo.textContent = "Lançamentos";
    meta.textContent = plural(fin.lista.length, "lançamento") + " em " + mesCurto(fin.mes) + " · " +
      fin.lista.filter((l) => l.tipo === "recebimento").length + " a receber · " +
      fin.lista.filter((l) => l.tipo === "despesa").length + " a pagar";
  } else if (fin.visao === "relatorios") {
    titulo.textContent = "Relatórios";
    meta.textContent = mesRotulo + " · gerado na sua máquina";
  } else {
    const fecha = (fin.dados.fechamento || {}).dias_para_fechar;
    titulo.textContent = "Financeiro";
    meta.textContent = mesRotulo + (fecha ? " · fechamento em " + plural(fecha, "dia") : " · mês encerrado");
  }
  const botao = (v, r) => {
    const classe = v === fin.visao ? "ativa" : "";
    return '<button class="' + classe + '" data-fin-visao="' + v + '">' + r + "</button>";
  };
  let acoes;
  if (fin.visao === "lancamentos") {
    acoes = '<button class="com-icone" data-fin-importar="1">' + ic("upload", 16) + "Importar extrato</button>" +
      '<button class="primario com-icone" data-fin-novo="1">' + ic("add", 16) + "Novo lançamento</button>";
  } else if (fin.visao === "relatorios") {
    acoes = seletorDeMes() + '<button class="com-icone" data-fin-pdf="1">' + ic("picture_as_pdf", 16) + "Baixar PDF</button>" +
      '<button class="primario com-icone" data-fin-enviar="1">' + ic("mail", 16) + "Enviar por e-mail</button>";
  } else {
    acoes = seletorDeMes() + '<button class="com-icone" data-fin-exportar="1">' + ic("download", 16) + "Exportar</button>" +
      '<button class="primario com-icone" data-fin-novo="1">' + ic("add", 16) + "Novo lançamento</button>";
  }
  $("acoes-tela").innerHTML = '<div class="visoes">' + botao("geral", "Visão geral") + botao("lancamentos", "Lançamentos") + "</div>" +
    '<div class="visoes">' + botao("relatorios", "Relatórios") + "</div>" + acoes;
  $("nav-tela").innerHTML = "";
}

function seletorDeMes() {
  return '<label class="fin-mes-sel" title="Mês"><select id="fin-mes">' +
    (fin.dados.meses || []).map((m) => '<option value="' + esc(m.valor) + '"' + (m.valor === fin.mes ? " selected" : "") + ">" +
      esc(m.valor === mesDeHoje() ? "Este mês" : maiuscula(m.rotulo)) + "</option>").join("") +
    "</select>" + ic("expand_more", 16) + "</label>";
}

/* Uma secao da pagina, no cabecalho de Servicos: titulo curto em sans, a
   conta ou a acao a direita. */
function finSecao(classe, titulo, meta, direita, corpo) {
  return '<section class="sv-secao ' + classe + '"><div class="sv-secao-cabeca"><span class="sv-secao-titulo">' + titulo + "</span>" +
    (meta ? '<span class="sv-secao-meta">' + meta + "</span>" : "") + (direita || "") + "</div>" + corpo + "</section>";
}

/* ---------------------------------------------------- a visao geral */

function corpoDaVisaoGeral() {
  return finFicha() + finPedidosHtml() + finFluxoHtml() +
    '<div class="sv-duas">' + finContasHtml("recebimento") + finContasHtml("despesa") + "</div>" +
    finPapeisHtml() + finParecerSecao(false);
}

/* Os numeros do mes numa faixa, como a ficha do Acervo e de Servicos. */
function finFicha() {
  const d = fin.dados;
  const p = d.painel;
  const f = d.fechamento || {};
  const faltas = f.faltas || [];
  const folha = d.folha || {};
  const item = (rotulo, valor, sub, classe) => '<div class="sv-ficha-item"><span class="sv-kicker">' + rotulo + "</span>" +
    '<b class="' + (classe || "") + '">' + esc(valor) + '</b><small class="fin-ficha-sub">' + esc(sub) + "</small></div>";
  const atraso = p.atrasado > 0;
  const classeAtraso = atraso ? "fin-acc" : "";
  return '<div class="sv-ficha fin-ficha">' +
    item("Saldo em caixa", p.saldo_texto, p.resultado_mes_texto + " no mês") +
    item("A receber", p.a_receber_texto, plural(p.a_receber_quantos, "cobrança aberta", "cobranças abertas")) +
    item("A pagar", p.a_pagar_texto, plural(p.a_pagar_quantos, "conta") + (folha.lancamento_id ? " · folha inclusa" : "")) +
    item("Em atraso", atraso ? p.atrasado_texto : "nada", atraso ? plural(p.atrasado_quantos, "cobrança") : "nenhuma cobrança vencida", classeAtraso) +
    item("Fechamento", f.dias_para_fechar ? "em " + plural(f.dias_para_fechar, "dia") : "mês encerrado",
      faltas.length ? plural(faltas.length, "pendência") : "nada pendente") +
    "</div>";
}

/* O que espera decisao sua, tudo de regra: folha pronta, cobranca atrasada,
   conta vencendo, papel faltando. Cada item aponta uma coisa que existe. */
function pedidosDoMes() {
  const d = fin.dados;
  const folha = d.folha || {};
  const saida = [];
  (d.precisa || []).forEach((a) => {
    const id = (a.ids || [])[0];
    const acoes = [];
    if (a.acao === "cobrar") acoes.push({ rotulo: "Cobrar", primario: true, fazer: () => prepararCobranca(id) });
    if (a.acao === "pagar") acoes.push({ rotulo: "Registrar pagamento", primario: true, fazer: () => liquidarLancamento(id) });
    if (a.acao === "anexar") acoes.push({ rotulo: "Anexar comprovante", primario: true, fazer: () => finVerLancamento(id) });
    acoes.push({ rotulo: "Ver", fazer: () => finVerLancamento(id) });
    saida.push({ grau: a.acao === "cobrar" ? "atraso" : "", titulo: a.titulo, detalhe: a.detalhe, acoes: acoes });
  });
  if (folha.quantos && !folha.lancamento_id) {
    saida.push({ titulo: "Folha de " + mesCurto(folha.mes) + " pronta para lançar — " + folha.total_curto,
      detalhe: plural(folha.quantos, "pessoa") + " · vence no último dia do mês",
      acoes: [{ rotulo: "Lançar em contas a pagar", primario: true, fazer: () => pedirFolha("pagar") },
              { rotulo: "Ver", fazer: finVerFolha }] });
  } else if (!folha.quantos && (d.candidatos_folha || []).length) {
    saida.push({ titulo: "Folha de " + mesCurto(fin.mes) + " ainda não montada",
      detalhe: plural(d.candidatos_folha.length, "pessoa") + " com vínculo definido em Cadastros",
      acoes: [{ rotulo: "Montar a folha", primario: true, fazer: () => pedirFolha("montar") }] });
  }
  const aEmitir = d.notas_a_emitir || [];
  if (aEmitir.length) {
    const x = aEmitir[0];
    saida.push({ titulo: plural(aEmitir.length, "recebimento sem nota fiscal registrada", "recebimentos sem nota fiscal registrada"),
      detalhe: (x.cliente || x.descricao) + " · " + emReais(x.centavos),
      acoes: [{ rotulo: "Registrar a nota", primario: true, fazer: () => finFormPapel("nota", x) }] });
  }
  const hoje = iso(new Date());
  const vencidos = (d.boletos || []).filter((b) => b.situacao === "aberto" && b.data && b.data < hoje);
  if (vencidos.length) {
    saida.push({ grau: "atraso", titulo: plural(vencidos.length, "boleto vencido", "boletos vencidos") + " e ainda em aberto",
      detalhe: vencidos.map((b) => b.cliente || b.numero || "sem nome").slice(0, 3).join(", "),
      acoes: [{ rotulo: "Dar baixa", primario: true, fazer: () => baixarBoleto(vencidos[0].id) },
              { rotulo: "Ver boletos", fazer: () => finVerPapeis("boleto") }] });
  }
  (d.concluidos || []).forEach((c) => {
    saida.push({ titulo: "Contrato de " + c.nome + " quitado", detalhe: "nada em aberto · " + semReais(c.recebido_texto) + " recebidos",
      acoes: [{ rotulo: "Ver no Acervo", fazer: () => arquivarCliente(c.id) }] });
  });
  fin.pedidos = saida;
  return saida;
}

/* "Precisa de voce" some quando nao ha nada: uma pagina calma e o sinal de
   que esta tudo em dia. */
function finPedidosHtml() {
  const pedidos = pedidosDoMes();
  if (!pedidos.length) return "";
  // Tres por vez: o resto fica a um clique, para a lista nao tomar a pagina.
  const mostrados = fin.pedidosTodos ? pedidos : pedidos.slice(0, 3);
  const resto = pedidos.length - mostrados.length;
  let mais = "";
  if (resto > 0) mais = '<button class="sv-ligacao fin-pede-mais" data-fin-pede-todos="1">' + ic("expand_more", 15) + "Ver mais " + plural(resto, "item", "itens") + "</button>";
  else if (pedidos.length > 3) mais = '<button class="sv-ligacao fin-pede-mais" data-fin-pede-todos="1">Mostrar só os três primeiros</button>';
  const linhas = mostrados.map((p, i) => {
    const classe = "fin-pede-linha" + (p.grau === "atraso" ? " atraso" : "");
    return '<div class="' + classe + '"><i></i><span class="duas-linhas"><b>' + esc(p.titulo) + "</b>" +
      (p.detalhe ? "<small>" + esc(p.detalhe) + "</small>" : "") + "</span>" +
      '<span class="fin-pede-botoes">' + p.acoes.map((a, j) => {
        const classeBotao = a.primario ? "fin-botao-linha" : "sv-ligacao";
        return '<button class="' + classeBotao + '" data-fin-pede="' + i + ":" + j + '">' + esc(a.rotulo) + "</button>";
      }).join("") + "</span></div>";
  }).join("");
  return finSecao("fin-pedidos", ic("notifications", 16) + "Precisa de você", esc(plural(pedidos.length, "item", "itens")), "",
    '<div class="fin-pede-lista">' + linhas + "</div>" + mais);
}

function finFluxoHtml() {
  const d = fin.dados;
  const p = d.painel;
  const fluxo = d.fluxo || [];
  const fluxoMes = fluxo.find((m) => m.mes === fin.mes) || null;
  const teto = Math.max(1, ...fluxo.map((m) => Math.max(m.entradas, m.saidas)));
  const barras = fluxo.map((m) =>
    '<div class="fin-fluxo-mes" title="' + esc(maiuscula(m.rotulo) + ": entradas " + m.entradas_texto + " · saídas " + m.saidas_texto) + '">' +
    '<span style="height:' + Math.round(m.entradas * 100 / teto) + '%"></span>' +
    '<span class="fin-saida" style="height:' + Math.round(m.saidas * 100 / teto) + '%"></span></div>').join("");
  const rotulos = fluxo.map((m) => {
    const classe = m.mes === fin.mes ? "atual" : "";
    return '<span class="' + classe + '">' + esc(maiuscula(m.rotulo)) + "</span>";
  }).join("");
  const legenda = '<span class="fin-legenda"><span><i></i>Entradas</span><span><i class="fin-saida"></i>Saídas</span></span>';
  const resultado = fluxoMes ? fluxoMes.entradas - fluxoMes.saidas : 0;
  const somas = '<div class="fin-fluxo-pe"><span>Em ' + esc(mesCurto(fin.mes)) + ": entraram <b>" + esc(fluxoMes ? fluxoMes.entradas_texto : "R$ 0") +
    "</b> · saíram <b>" + esc(fluxoMes ? fluxoMes.saidas_texto : "R$ 0") + "</b> · resultado <b>" +
    esc((resultado >= 0 ? "+" : "−") + curtoEmReais(Math.abs(resultado))) + "</b></span>" +
    '<button class="sv-ligacao" data-fin-importar="1">' + ic("upload", 15) + "Conferir com o extrato do banco</button></div>";
  const corpo = p.tem_dado
    ? '<div class="fin-fluxo"><div class="fin-fluxo-grade">' + barras + '</div><div class="fin-fluxo-rotulos">' + rotulos + "</div></div>" + somas
    : '<div class="fin-fluxo-vazio"><p>Nada lançado ainda. Os números desta tela são a soma dos lançamentos — sem nenhum, tudo fica em zero.</p>' +
      '<button class="primario com-icone" data-fin-novo="1">' + ic("add", 16) + "Lançar o primeiro</button></div>" +
      '<div class="fin-fluxo fin-fluxo-apagado"><div class="fin-fluxo-grade">' + barras + '</div><div class="fin-fluxo-rotulos">' + rotulos + "</div></div>";
  return finSecao("fin-fluxo-secao", ic("bar_chart", 16) + "Fluxo de caixa", "últimos 6 meses", legenda, corpo);
}

function curtoEmReais(centavos) {
  return "R$ " + Math.round(centavos / 100).toLocaleString("pt-BR");
}

/* A receber e a pagar, lado a lado: o que esta em aberto, o mais urgente
   primeiro (a ordem vem do servidor: vencimento). */
function finContasHtml(tipo) {
  const d = fin.dados;
  const p = d.painel;
  const receber = tipo === "recebimento";
  const todos = (receber ? d.receber : d.pagar) || [];
  const mostrados = todos.slice(0, 5);
  const quantos = receber ? p.a_receber_quantos : p.a_pagar_quantos;
  const linhas = mostrados.length
    ? '<div class="fin-contas">' + mostrados.map(finLinhaDeConta).join("") + "</div>"
    : '<p class="sv-dica fin-contas-vazio">' + (receber ? "Nenhuma cobrança em aberto." : "Nenhuma conta em aberto.") + "</p>";
  const pe = '<div class="fin-contas-pe"><span>' + (quantos > mostrados.length ? mostrados.length + " de " + quantos : "") + "</span>" +
    '<button class="sv-ligacao" data-fin-ver-lancamentos="' + (receber ? "receber" : "pagar") + '">Ver em Lançamentos' + ic("arrow_forward", 15) + "</button></div>";
  return finSecao("fin-contas-secao", ic(receber ? "payments" : "schedule", 16) + (receber ? "A receber" : "A pagar"),
    esc(plural(quantos, "em aberto", "em aberto")), "", linhas + pe);
}

/* Uma linha de conta: quem, do que se trata, quando vence e o valor. */
function finLinhaDeConta(l) {
  const quem = l.cadastro_nome || l.descricao;
  const sobre = l.cadastro_nome ? l.descricao : l.categoria_rotulo;
  const classeSit = l.atrasado ? "fin-acc" : "";
  return '<button type="button" class="fin-conta" data-fin-abrir="' + l.id + '"><span class="duas-linhas"><b>' + esc(quem) + "</b><small>" + esc(sobre) + "</small></span>" +
    '<span class="fin-conta-fim"><b class="fin-valor">' + esc(semReais(l.valor)) + '</b><small class="' + classeSit + '">' + esc(situacaoCurta(l)) + "</small></span></button>";
}

function situacaoCurta(l) {
  if (!l.aberto) return (l.tipo === "recebimento" ? "recebido " : "pago ") + dataBR(l.liquidado_em).slice(0, 5);
  if (l.atrasado) return "atrasado " + plural(l.dias_atraso, "dia");
  if (l.vencimento) return "vence " + dataBR(l.vencimento).slice(0, 5);
  return "sem vencimento";
}

/* Os papeis do mes numa faixa so: nota, boleto, comprovante e folha. Cada
   coluna diz o numero e o que falta; a lista e o cadastro abrem no pop-up. */
function finPapeisHtml() {
  const d = fin.dados;
  const notas = d.notas || [];
  const aEmitir = d.notas_a_emitir || [];
  const boletos = d.boletos || [];
  const abertos = boletos.filter((b) => b.situacao === "aberto");
  const hoje = iso(new Date());
  const vencidos = abertos.filter((b) => b.data && b.data < hoje);
  const comprovantes = d.comprovantes || [];
  const semComp = d.sem_comprovante || [];
  const folha = d.folha || {};
  const coluna = (icone, titulo, valor, sub, subAcc, links) => '<div class="fin-papel"><span class="fin-papel-titulo">' + ic(icone, 16) + titulo + "</span>" +
    "<b>" + esc(valor) + '</b><small class="' + (subAcc ? "fin-acc" : "") + '">' + esc(sub) + "</small>" +
    '<span class="fin-papel-links">' + links + "</span></div>";
  const link = (atributo, rotulo) => '<button class="sv-ligacao" ' + atributo + ">" + rotulo + "</button>";

  let folhaValor, folhaSub, folhaLinks;
  if (folha.quantos) {
    folhaValor = folha.total_curto;
    folhaSub = plural(folha.quantos, "pessoa") + (folha.lancamento_id ? " · já em contas a pagar" : " · falta lançar");
    folhaLinks = link('data-fin-folha="ver"', "Ver a folha");
  } else if ((d.candidatos_folha || []).length) {
    folhaValor = "não montada";
    folhaSub = plural(d.candidatos_folha.length, "pessoa") + " com vínculo";
    folhaLinks = link('data-fin-folha="montar"', "Montar a folha");
  } else {
    folhaValor = "—";
    folhaSub = "ninguém com vínculo em Cadastros";
    folhaLinks = link('data-fin-cadastros="1"', "Ir para Cadastros");
  }

  const grade = '<div class="fin-papeis">' +
    coluna("receipt_long", "Notas fiscais", plural(notas.length, "registrada"),
      aEmitir.length ? plural(aEmitir.length, "recebimento sem nota", "recebimentos sem nota") : "nenhum recebimento sem nota", false,
      link('data-fin-papel="nota"', "Registrar") + ((notas.length || aEmitir.length) ? link('data-fin-ver-papel="nota"', "Ver lista") : "")) +
    coluna("description", "Boletos", plural(abertos.length, "em aberto", "em aberto"),
      vencidos.length ? plural(vencidos.length, "vencido") : (boletos.length ? plural(boletos.length, "no mês", "no mês") : "nenhum no mês"), vencidos.length > 0,
      link('data-fin-papel="boleto"', "Registrar") + (boletos.length ? link('data-fin-ver-papel="boleto"', "Ver lista") : "")) +
    coluna("attach_file", "Comprovantes", plural(comprovantes.length, "guardado"),
      semComp.length ? plural(semComp.length, "pagamento sem comprovante", "pagamentos sem comprovante") : "nenhum pagamento sem comprovante", false,
      (comprovantes.length || semComp.length) ? link('data-fin-ver-papel="comprovante"', "Ver lista") : "") +
    coluna("group", "Folha de pagamento", folhaValor, folhaSub, false, folhaLinks) +
    "</div>";
  return finSecao("fin-papeis-secao", ic("folder_open", 16) + "Papéis do mês", esc(maiuscula(mesCurto(fin.mes))), "", grade);
}

/* O parecer e a unica parte que passa pelo modelo, e sempre depois: ele
   recebe os numeros ja somados e escreve sobre eles. Nunca calcula. */
function finParecerSecao(destaque) {
  let direita;
  if (fin.pedindo) direita = '<span class="fin-pensando">' + coroa(16) + "escrevendo…</span>";
  else if (fin.parecer) direita = '<button class="sv-ligacao" data-fin-descartar="1">Descartar</button>';
  else direita = '<button class="sv-ligacao" data-fin-parecer="1">' + ic("insights", 15) + "Pedir o parecer</button>";
  return finSecao("fin-parecer-secao", ic("auto_awesome", 16) + "Parecer do mês", "escrito pelo assistente, nesta máquina", direita,
    '<div class="fin-parecer-corpo">' + parecerHtml(destaque) + "</div>");
}

function parecerHtml(destaque) {
  const classe = "fin-parecer" + (destaque ? " solto" : "");
  if (fin.pedindo) {
    return '<div class="' + classe + '"><p>Escrevendo sobre os números do mês — cerca de um minuto nesta máquina.</p></div>';
  }
  if (!fin.parecer) {
    return '<div class="' + classe + '"><p>Um comentário sobre os números acima. Eles foram somados aqui; o assistente só escreve sobre eles. Leva cerca de um minuto e nada sai desta máquina.</p>' +
      (fin.parecerErro ? '<small class="fin-acc">' + esc(fin.parecerErro) + "</small>" : "") + "</div>";
  }
  const paragrafos = String(fin.parecer.parecer || "").split(/\n+/).map((t) => t.trim()).filter(Boolean);
  return '<div class="' + classe + '">' + paragrafos.map((t, i) => {
    const classeP = i === 0 ? (destaque ? "fin-lead" : "fin-parecer-lead") : "";
    return '<p class="' + classeP + '">' + esc(t) + "</p>";
  }).join("") +
    "<small>" + esc(fin.parecer.aviso) + ' · <button class="em-ligacao" data-fin-numeros="1">' +
    (fin.numerosAbertos ? "esconder os números" : "ver os números que usei") + "</button></small>" +
    (fin.numerosAbertos ? '<div class="fin-numeros-crus">' + esc(fin.parecer.numeros) + "</div>" : "") + "</div>";
}

async function pedirParecer() {
  if (fin.pedindo) return;
  fin.pedindo = true;
  fin.parecerErro = "";
  desenharFinanceiro();
  const r = await fetch("/api/relatorios/parecer", { method: "POST", headers: FIN_JSON, body: JSON.stringify({ quando: quandoDoRelatorio() }) });
  fin.pedindo = false;
  if (!r.ok) fin.parecerErro = await erroDe(r);
  else fin.parecer = await r.json();
  // Um minuto depois a pessoa pode estar em outra tela: so repinta se o
  // Financeiro ainda estiver aberto.
  if ($("financeiro")) desenharFinanceiro();
}

/* ---------------------------------------------------- os lancamentos */

function lancamentosFiltrados() {
  let base = fin.filtro === "atrasados" ? fin.todos.filter((l) => l.atrasado) : fin.lista;
  if (fin.filtro === "receber") base = base.filter((l) => l.tipo === "recebimento");
  if (fin.filtro === "pagar") base = base.filter((l) => l.tipo === "despesa");
  if (fin.categoria) base = base.filter((l) => l.categoria === fin.categoria);
  return base;
}

function corpoDosLancamentos() {
  const lista = lancamentosFiltrados();
  const contagem = {
    todos: fin.lista.length,
    receber: fin.lista.filter((l) => l.tipo === "recebimento").length,
    pagar: fin.lista.filter((l) => l.tipo === "despesa").length,
    atrasados: fin.todos.filter((l) => l.atrasado).length,
  };
  const total = fin.filtro === "atrasados" ? contagem.atrasados : fin.lista.length;
  const chip = (v, r) => {
    const classe = v === fin.filtro ? "ativa" : "";
    return '<button class="' + classe + '" data-fin-filtro="' + v + '">' + r + " · " + contagem[v] + "</button>";
  };
  const entradas = lista.filter((l) => l.tipo === "recebimento").reduce((s, l) => s + l.centavos, 0);
  const saidas = lista.filter((l) => l.tipo === "despesa").reduce((s, l) => s + l.centavos, 0);
  const categoria = fin.categoria ? (fin.dados.opcoes_categoria.find((c) => c.valor === fin.categoria) || {}).rotulo : "";
  let vazio;
  if (!fin.lista.length && fin.filtro !== "atrasados") {
    vazio = "Nenhum lançamento em " + mesCurto(fin.mes) + ". Lance o primeiro pelo botão Novo lançamento.";
  } else {
    vazio = "Nenhum lançamento com este filtro.";
  }

  return (fin.extrato ? finConferenciaHtml() : "") +
    '<div class="tabela-cartao fin-tabela">' +
    '<div class="tabela-barra fin-barra">' +
    (fin.escolhidos.size
      ? barraDeSelecao(fin.escolhidos.size, false, '<button class="botao-icone perigo" data-fin-sel-apagar="1" title="Apagar" aria-label="Apagar">' + ic("delete", 18) + "</button>", "data-fin-sel-limpar")
      : '<div class="visoes">' + chip("todos", "Todos") + chip("receber", "A receber") + chip("pagar", "A pagar") + chip("atrasados", "Atrasados") + "</div>") +
    '<div class="direita">' + seletorDeMes() +
    '<button data-fin-filtros="1">' + ic("filter_list", 16) + (categoria ? esc(categoria) : "Categoria") + "</button>" +
    '<button data-fin-exportar="1">' + ic("download", 16) + "Exportar</button></div></div>" +
    '<div class="tabela-cabecalho colunas-lancamentos"><span>Data</span><span>Quem · descrição</span><span>Categoria</span>' +
    '<span class="fin-num">Valor</span><span>Situação</span><span class="fin-num">Ação</span></div>' +
    '<div class="tabela-corpo">' + (lista.length ? lista.map(linhaDeLancamento).join("") : '<p class="rel-vazio">' + esc(vazio) + "</p>") + "</div>" +
    '<div class="tabela-rodape"><span>' + lista.length + " de " + total + '</span><span class="fin-somas">' +
    "<span>Entradas <b>+ " + esc(semReais(emReais(entradas))) + "</b></span>" +
    "<span>Saídas <b>− " + esc(semReais(emReais(saidas))) + "</b></span></span></div>" +
    "</div>";
}

function linhaDeLancamento(l) {
  const classe = "tabela-linha colunas-lancamentos" + (fin.escolhidos.has(String(l.id)) ? " escolhida" : "");
  const quem = l.cadastro_nome
    ? "<b>" + esc(l.cadastro_nome) + "</b><small>" + esc(l.descricao) + "</small>"
    : "<b>" + esc(l.descricao) + "</b><small>" + esc(l.categoria_rotulo + (l.comprovantes ? " · " + plural(l.comprovantes, "comprovante") : "")) + "</small>";
  const classeValor = "fin-valor fin-valor-col";
  const status = statusDoLancamento(l);
  const classeStatus = "fin-status " + status.classe;
  let acoes;
  if (l.aberto && l.tipo === "recebimento" && l.atrasado) {
    acoes = '<button data-fin-cobrar="' + l.id + '">Cobrar</button>';
  } else if (l.aberto && l.tipo === "despesa" && status.classe === "vence") {
    acoes = '<button data-fin-liquidar="' + l.id + '">Pagar</button>';
  } else {
    acoes = '<button class="fin-acao-ver" data-fin-abrir="' + l.id + '">Abrir</button>';
  }
  return '<div class="' + classe + '" data-fin-abrir="' + l.id + '" data-sel="' + l.id + '">' +
    '<span class="fin-data">' + esc(dataCurta(l.vencimento || l.liquidado_em)) + "</span>" +
    '<span class="duas-linhas">' + quem + "</span>" +
    '<span class="fin-cat">' + esc(l.categoria_rotulo) + "</span>" +
    '<span class="' + classeValor + '">' + (l.tipo === "recebimento" ? "+ " : "− ") + esc(semReais(l.valor)) + "</span>" +
    '<span class="' + classeStatus + '"><i></i>' + esc(status.texto) + "</span>" +
    '<span class="fin-acoes">' + acoes + "</span></div>";
}

function statusDoLancamento(l) {
  if (!l.aberto) return { classe: "pago", texto: l.tipo === "recebimento" ? "Recebido" : "Pago" };
  if (l.atrasado) return { classe: "atrasado", texto: "Atrasado " + l.dias_atraso + " d" };
  const dias = l.dias_para_vencer;
  if (dias !== null && dias !== undefined && dias <= 7) {
    return { classe: "vence", texto: dias === 0 ? "Vence hoje" : "Vence em " + dias + " d" };
  }
  return { classe: "aberto", texto: l.vencimento ? "A vencer" : "Em aberto" };
}

/* ------------------------------------------------------ os relatorios */

function corpoDosRelatorios() {
  const r = fin.rel;
  const aba = (v, rotulo) => {
    const classe = v === fin.relAba ? "ativa" : "";
    return '<button class="' + classe + '" data-fin-rel-aba="' + v + '">' + rotulo + "</button>";
  };
  let cartoes;
  if (fin.relAba === "dia") cartoes = cartoesDoDia(r.dia);
  else if (fin.relAba === "acoes") cartoes = cartaoDasAcoes(r.mes);
  else cartoes = cartoesFinanceiros(r.mes);
  const depois = fin.relAba === "financeiro" ? finParecerSecao(true) + finSugestoesSecao() : "";
  return '<div class="visoes fin-rel-abas">' +
    aba("dia", "Tarefas do dia") + aba("financeiro", "Financeiro") + aba("acoes", "Ações de IA aprovadas") + "</div>" +
    '<div class="fin-grade2">' + cartoes + "</div>" + depois;
}

function cartoesFinanceiros(m) {
  const p = fin.dados.painel;
  const ex = m.extrato || { linhas: [] };
  const resultado = (m.entradas || 0) - (m.saidas || 0);
  const linha = (rotulo, valor, tom) => {
    const classe = tom || "";
    return '<div class="rel-linha"><span>' + esc(rotulo) + '</span><b class="' + classe + '">' + esc(valor) + "</b></div>";
  };
  const cats = fin.dados.categorias || [];
  const teto = Math.max(1, ...cats.map((c) => c.total));
  const prazo = m.prazo_medio || {};

  const extrato = '<div class="fin-cartao"><div class="fin-cartao-cabeca"><span>Extrato do mês</span><small>' +
    esc(mesCurto(fin.mes) + " · " + plural((ex.linhas || []).length, "lançamento")) + "</small></div>" +
    '<div class="rel-linhas">' +
    linha("Entradas", "+ " + semReais(emReais(m.entradas || 0))) +
    linha("Saídas", "− " + semReais(emReais(m.saidas || 0))) +
    linha("Resultado", (resultado >= 0 ? "+ " : "− ") + semReais(emReais(Math.abs(resultado))), resultado >= 0 ? "" : "fin-acc") +
    linha("A receber em aberto", semReais(p.a_receber_texto)) +
    linha("A pagar em aberto", semReais(p.a_pagar_texto)) +
    linha("Em atraso", semReais(p.atrasado_texto), p.atrasado > 0 ? "fin-acc" : "") + "</div>" +
    (m.comparacao && m.comparacao.tem_base
      ? '<p class="rel-explica">Contra ' + esc(m.comparacao.mes_anterior) + ": entradas " + esc(m.comparacao.entradas.texto) + ", saídas " + esc(m.comparacao.saidas.texto) + ".</p>"
      : '<p class="rel-explica">Sem lançamento em ' + esc(m.comparacao ? m.comparacao.mes_anterior : "mês anterior") + ", não dá para comparar.</p>") +
    '<p class="rel-explica">' + (prazo.tem
      ? "Prazo médio de recebimento: " + esc(String(prazo.dias).replace(".", ",")) + " dias, sobre " + esc(plural(prazo.quantos, "recebimento")) + "."
      : "Prazo médio: " + esc(prazo.porque || "sem base ainda") + ".") + "</p>" +
    '<div class="rel-espaco"></div>' +
    '<div class="fin-rodape-botoes"><button data-fin-pdf="1">' + ic("picture_as_pdf", 16) + "Baixar PDF</button>" +
    '<button data-fin-exportar="1">' + ic("table", 16) + "Baixar XLSX</button></div></div>";

  const categorias = '<div class="fin-cartao"><div class="fin-cartao-cabeca"><span>Por categoria</span><small>' + esc(mesCurto(fin.mes)) + "</small></div>" +
    (cats.length
      ? '<div class="rel-categorias">' + cats.map((c, i) => {
        const classe = "rel-categoria c" + Math.min(i + 1, 4);
        return '<div class="' + classe + '"><div><span>' + esc(c.rotulo + (c.tipo === "recebimento" ? " · entrada" : "")) + "</span><b>" +
          esc(semReais(c.total_texto)) + '</b></div><div class="rel-trilho"><i style="width:' + Math.max(2, Math.round(c.total * 100 / teto)) + '%"></i></div></div>';
      }).join("") + "</div>"
      : '<p class="rel-vazio">Nada recebido ou pago em ' + esc(mesCurto(fin.mes)) + ". As barras saem do que foi efetivamente liquidado.</p>") +
    "</div>";
  return extrato + categorias;
}

function cartoesDoDia(dia) {
  const t = dia.tarefas;
  const tarefas = '<div class="fin-cartao"><div class="fin-cartao-cabeca"><span>Tarefas do dia</span><small>' + esc(dia.rotulo) + "</small></div>" +
    '<div class="rel-tarefas">' +
    (t.planejado ? '<p class="rel-explica">' + t.feitas.length + " de " + t.planejado + " feitas · " + t.percentual + "%</p>" : "") +
    t.feitas.map((x) => '<div class="rel-tarefa feita">' + ic("check_circle", 18) + '<span class="cresce">' + esc(x.titulo) + "</span><small>" + esc(x.hora) + "</small></div>").join("") +
    t.abertas.map((x) => '<div class="rel-tarefa"><span class="rel-aberta"></span><span class="cresce">' + esc(x.titulo) + "</span><small>" + esc(x.quando) + "</small></div>").join("") +
    (t.planejado ? "" : '<p class="rel-vazio">Nada estava no Meu dia nem vencia neste dia.</p>') + "</div></div>";
  const medido = dia.medido || {};
  const numeros = '<div class="fin-cartao"><div class="fin-cartao-cabeca"><span>Números do dia</span><small>somados do que ficou gravado</small></div>' +
    '<div class="rel-numeros">' + numeroRel("documentos assinados", dia.assinaturas.length) + numeroRel("e-mails enviados", dia.emails.length) +
    numeroRel("versões gravadas", dia.versoes) + numeroRel("compromissos", dia.compromissos) +
    (medido.tempo_ativo ? numeroRel("tempo ativo", medido.tempo_ativo) : "") +
    (medido.pausas !== undefined ? numeroRel("pausas", medido.pausas) : "") + "</div>" +
    (dia.sem_medicao
      ? '<p class="rel-explica">O tempo no escritório não aparece: o acompanhamento de bem-estar está desligado.' +
        '<button class="em-ligacao forte" data-fin-foco="1">Ligar em Foco e bem-estar</button></p>'
      : "") + "</div>";
  return tarefas + numeros;
}

function cartaoDasAcoes(m) {
  const acoes = m.acoes || [];
  return '<div class="fin-cartao larga"><div class="fin-cartao-cabeca"><span>Ações de IA aprovadas</span><small>' + esc(mesCurto(fin.mes)) + " · " + acoes.length + "</small></div>" +
    '<p class="rel-explica rel-topo">Cada linha é um pedido que passou pela fila de Aprovações, com o resultado guardado.</p>' +
    (acoes.length
      ? '<div class="rel-acoes">' + acoes.map((a) => {
        const classe = "ic ic-18" + (a.estado === "aprovado" ? "" : " nao");
        return '<div class="rel-acao"><span class="fin-data">' + esc(dataCurta(a.dia) + " " + a.hora) + '</span><span class="' + classe + '">' +
          (a.estado === "aprovado" ? "check_circle" : "close") + '</span><span class="duas-linhas"><b>' + esc(a.titulo) + "</b><small>" +
          esc(a.categoria_rotulo + " · " + (a.resultado || a.estado)) + "</small></span></div>";
      }).join("") + "</div>"
      : '<p class="rel-vazio">Nada foi aprovado em ' + esc(mesCurto(fin.mes)) + ". Quando você aprovar um pedido na fila, ele aparece aqui.</p>") +
    "</div>";
}

/* As sugestoes saem de regra, nao de opiniao: atraso, vencimento, papel que
   falta. Sao as mesmas coisas de "Precisa de voce", ditas como proximo passo. */
function finSugestoesSecao() {
  const sugestoes = sugestoesDoMes();
  const direita = sugestoes.length
    ? '<button class="sv-ligacao" data-fin-criar-tarefas="1">' + ic("add_task", 15) + "Criar tarefas para hoje</button>"
    : "";
  return finSecao("fin-sugestoes-secao", ic("checklist", 16) + "Sugestões", sugestoes.length ? "saem de regra, não de opinião" : "", direita,
    sugestoes.length
      ? '<div class="fin-sugestoes">' + sugestoes.map((s) => '<div class="fin-sugestao"><i></i><span>' + esc(s.texto) + "</span></div>").join("") + "</div>"
      : '<p class="sv-dica fin-contas-vazio">Nada a sugerir: nenhuma cobrança atrasada, nenhuma conta vencendo nesta semana e nenhum papel faltando.</p>');
}

function sugestoesDoMes() {
  const d = fin.dados;
  const saida = [];
  (d.precisa || []).forEach((a) => {
    if (a.acao === "cobrar") {
      saida.push({ texto: "Cobrar hoje — " + a.titulo + (a.detalhe ? ": " + a.detalhe : "") + ". A cobrança sai pronta como rascunho de e-mail.",
        tarefa: "Cobrar " + (a.detalhe || a.titulo) });
    } else if (a.acao === "pagar") {
      saida.push({ texto: "Pagar " + a.titulo + " — " + a.detalhe + ".", tarefa: "Pagar " + a.titulo });
    } else if (a.acao === "anexar") {
      saida.push({ texto: "Guardar o comprovante de " + a.detalhe + ": sem ele o mês não fecha.", tarefa: "Anexar comprovante: " + a.detalhe });
    }
  });
  ((d.fechamento || {}).faltas || []).forEach((f) => {
    if (f.o_que === "comprovante") return;
    saida.push({ texto: maiuscula(f.titulo) + (f.detalhe ? " — " + f.detalhe : "") + ".", tarefa: maiuscula(f.titulo) });
  });
  const dias = (d.fechamento || {}).dias_para_fechar;
  if (dias && dias <= 7 && saida.length) {
    saida.push({ texto: "Fechar o mês nos próximos " + plural(dias, "dia") + ": resolver os itens acima antes deixa a planilha de exportação completa.",
      tarefa: "Fechar o mês de " + mesCurto(fin.mes) });
  }
  return saida;
}

async function criarTarefasDasSugestoes() {
  const sugestoes = sugestoesDoMes();
  if (!sugestoes.length) return;
  const hoje = iso(new Date());
  let feitas = 0;
  for (const s of sugestoes) {
    const r = await fetch("/api/tarefas", { method: "POST", headers: FIN_JSON,
      body: JSON.stringify({ dados: { titulo: s.tarefa.slice(0, 120), prazo: hoje, anotacao: s.texto } }) });
    if (r.ok) feitas += 1;
  }
  avisoCert(feitas ? plural(feitas, "tarefa criada", "tarefas criadas") + " para hoje — estão na Agenda, em Meu dia" : "não consegui criar as tarefas");
}

async function enviarRelatorioPorEmail() {
  const m = fin.rel.mes;
  const p = fin.dados.painel;
  const corpo = "Relatório financeiro de " + p.mes_rotulo + "\n\n" +
    "Entradas: " + emReais(m.entradas || 0) + "\nSaídas: " + emReais(m.saidas || 0) + "\nResultado: " + m.extrato.resultado_texto +
    "\nSaldo em caixa: " + m.extrato.saldo_final_texto + "\n" +
    "A receber em aberto: " + p.a_receber_texto + " (" + plural(p.a_receber_quantos, "cobrança") + ")\nA pagar em aberto: " + p.a_pagar_texto +
    "\nEm atraso: " + p.atrasado_texto + "\n" +
    (fin.parecer ? "\nParecer:\n" + fin.parecer.parecer + "\n" : "") +
    "\nRelatório montado no PAULUS, nesta máquina.";
  if (!mail.contas) {
    try { mail.contas = await (await fetch("/api/email/contas")).json(); } catch (err) { mail.contas = null; }
  }
  if (!mail.contas || !mail.contas.contas.length) {
    avisoCert("entre com uma conta de e-mail primeiro — o relatório fica pronto para o envio");
    marcarDestino("caixa");
    return mostrarEmail();
  }
  mail.conta = mail.contas.contas.find((c) => c.em_uso) || mail.contas.contas[0];
  marcarDestino("caixa");
  telaEscrever({ para: "", assunto: "Relatório financeiro — " + p.mes_rotulo, corpo: corpo });
}

function baixarRelatorio() {
  const forma = document.createElement("form");
  forma.method = "POST";
  forma.action = "/api/relatorios/pdf";
  const quando = document.createElement("input");
  quando.type = "hidden";
  quando.name = "quando";
  quando.value = quandoDoRelatorio();
  forma.appendChild(quando);
  document.body.appendChild(forma);
  forma.submit();
  forma.remove();
}

/* ------------------------------------------------------------ as acoes */

/* Liga os botoes da pagina e os dos pop-ups: os dois usam os mesmos
   data-fin-*. Dentro de um pop-up, a acao fecha o pop-up antes. */
function ligarFinanceiro(raiz) {
  const onde = raiz || document;
  const noDialogo = onde !== document;
  // A pagina nao religa o pop-up aberto por cima dela: os botoes dele fecham
  // o pop-up antes de agir, e isso so vale ligado por ele.
  const cada = (seletor, fn) => onde.querySelectorAll(seletor).forEach((el) => {
    if (!noDialogo && el.closest(".veu-dialogo")) return;
    fn(el);
  });
  const clique = (seletor, fn) => cada(seletor, (b) => {
    b.onclick = (e) => { e.stopPropagation(); if (noDialogo) finFecharDialogo(); fn(b, e); };
  });

  if (!noDialogo) {
    clique("[data-fin-visao]", (b) => { fin.visao = b.dataset.finVisao; mostrarFinanceiro(); });
    const seletor = $("fin-mes");
    if (seletor) seletor.onchange = () => { fin.mes = seletor.value; mostrarFinanceiro(); };
    ligarSelecao(document.querySelector("#financeiro .tabela-corpo"), {
      linhas: ".tabela-linha[data-sel]", escolhidos: fin.escolhidos, aoMudar: desenharFinanceiro, apagar: (ids) => apagarLancamentosEmLote(ids),
    });
    cada("[data-fin-conc]", (caixa) => {
      caixa.onclick = (ev) => {
        ev.stopPropagation();
        const i = Number(caixa.dataset.finConc);
        const par = (fin.extrato.pares || [])[i] || {};
        const conjunto = par.lancamento_id ? fin.baixas : fin.novos;
        if (caixa.checked) conjunto.add(i); else conjunto.delete(i);
        desenharFinanceiro();
      };
    });
  }
  clique("[data-fin-novo]", () => novoLancamento());
  clique("[data-fin-exportar]", () => { window.location.href = "/api/financeiro/exportar?mes=" + encodeURIComponent(fin.mes); });
  clique("[data-fin-importar]", escolherExtrato);
  clique("[data-fin-conc-aplicar]", aplicarConciliacao);
  clique("[data-fin-conc-sair]", () => {
    fin.extrato = null; fin.baixas = new Set(); fin.novos = new Set(); desenharFinanceiro();
  });
  clique("[data-fin-pdf]", baixarRelatorio);
  clique("[data-fin-enviar]", enviarRelatorioPorEmail);
  clique("[data-fin-parecer]", pedirParecer);
  clique("[data-fin-pede-todos]", () => { fin.pedidosTodos = !fin.pedidosTodos; desenharFinanceiro(); });
  clique("[data-fin-descartar]", () => { fin.parecer = null; desenharFinanceiro(); });
  clique("[data-fin-numeros]", () => { fin.numerosAbertos = !fin.numerosAbertos; desenharFinanceiro(); });
  clique("[data-fin-ver-lancamentos]", (b) => { fin.filtro = b.dataset.finVerLancamentos || "todos"; fin.visao = "lancamentos"; mostrarFinanceiro(); });
  clique("[data-fin-filtro]", (b) => { fin.filtro = b.dataset.finFiltro; desenharFinanceiro(); });
  clique("[data-fin-filtros]", (b) => {
    menuNaLinha(b, [{ rotulo: "Todas as categorias", acao: () => { fin.categoria = ""; desenharFinanceiro(); } }, "-"].concat(
      fin.dados.opcoes_categoria.map((c) => ({ rotulo: c.rotulo, acao: () => { fin.categoria = c.valor; desenharFinanceiro(); } }))));
  });
  clique("[data-fin-abrir]", (b) => finVerLancamento(Number(b.dataset.finAbrir)));
  clique("[data-fin-sel-limpar]", () => { fin.escolhidos.clear(); desenharFinanceiro(); });
  clique("[data-fin-sel-apagar]", () => apagarLancamentosEmLote([...fin.escolhidos]));
  clique("[data-fin-cobrar]", (b) => prepararCobranca(Number(b.dataset.finCobrar)));
  clique("[data-fin-liquidar]", (b) => liquidarLancamento(Number(b.dataset.finLiquidar)));
  clique("[data-fin-reabrir]", (b) => reabrirLancamento(Number(b.dataset.finReabrir)));
  clique("[data-fin-editar]", (b) => editarLancamento(Number(b.dataset.finEditar), false));
  clique("[data-fin-renegociar]", (b) => editarLancamento(Number(b.dataset.finRenegociar), true));
  clique("[data-fin-cadastro], [data-fin-cadastros]", () => { marcarDestino("cadastros"); mostrarCadastros(); });
  clique("[data-fin-acervo]", (b) => verNoAcervo(b.dataset.finAcervo || ""));
  clique("[data-fin-foco]", () => { marcarDestino("foco"); mostrarFoco(); });
  clique("[data-fin-rel-aba]", (b) => { fin.relAba = b.dataset.finRelAba; desenharFinanceiro(); });
  clique("[data-fin-criar-tarefas]", criarTarefasDasSugestoes);
  clique("[data-fin-pede]", (b) => {
    const [i, j] = b.dataset.finPede.split(":").map(Number);
    const p = (fin.pedidos || [])[i];
    if (p && p.acoes[j]) p.acoes[j].fazer();
  });
  clique("[data-fin-folha]", (b) => {
    const a = b.dataset.finFolha;
    if (a === "ver") finVerFolha(); else if (a === "recibos") gerarRecibos(); else pedirFolha(a);
  });
  clique("[data-fin-papel]", (b) => finFormPapel(b.dataset.finPapel, null));
  clique("[data-fin-ver-papel]", (b) => finVerPapeis(b.dataset.finVerPapel));
  clique("[data-fin-nota-de]", (b) => {
    const x = (fin.dados.notas_a_emitir || []).find((n) => n.id === Number(b.dataset.finNotaDe));
    finFormPapel("nota", x || null);
  });
  clique("[data-fin-tirar-papel]", async (b) => {
    if (!(await confirmar({ titulo: "Tirar este registro?", contexto: "Financeiro", texto: "O papel de verdade continua onde está; só o registro sai daqui.", confirmar: "Tirar", perigo: true }))) return;
    await fetch("/api/financeiro/papeis/" + b.dataset.finTirarPapel, { method: "DELETE" });
    mostrarFinanceiro();
  });
  clique("[data-fin-boleto-pago]", (b) => baixarBoleto(Number(b.dataset.finBoletoPago)));
  clique("[data-fin-tirar-comp]", async (b) => {
    if (!(await confirmar({ titulo: "Tirar este comprovante?", contexto: "Financeiro › Lançamentos", texto: "Ele deixa de estar ligado ao lançamento. O arquivo continua na pasta.", confirmar: "Tirar", perigo: true }))) return;
    await fetch("/api/financeiro/comprovantes/" + b.dataset.finTirarComp, { method: "DELETE" });
    mostrarFinanceiro();
  });
}

function finFecharDialogo() {
  if (dialogoAberto) dialogoAberto.fechar(null);
}

/* ------------------------------------------- o lancamento, no pop-up */

/* A exibicao do lancamento (pop-up de exibicao, docs/ui/05): o valor, a
   ficha, as acoes que servem a ele e os comprovantes. Editar troca para o
   cadastro. */
async function finVerLancamento(id) {
  const l = fin.todos.find((x) => x.id === id);
  if (!l) return;
  fin.aberto = l;
  const receb = l.tipo === "recebimento";
  const comps = (fin.dados.comprovantes || []).filter((k) => k.lancamento_id === l.id);

  let situacao = "";
  if (l.atrasado) situacao = '<small class="fin-acc">' + esc(plural(l.dias_atraso, "dia")) + " de atraso</small>";
  else if (!l.aberto) situacao = "<small>" + (receb ? "recebido" : "pago") + " em " + esc(dataBR(l.liquidado_em)) + "</small>";
  else if (l.vencimento) situacao = "<small>vence em " + esc(dataBR(l.vencimento)) + "</small>";

  const acoes = [];
  if (l.aberto && receb) acoes.push('<button type="button" class="com-icone" data-fin-cobrar="' + l.id + '">' + ic("mail", 16) + "Cobrar por e-mail</button>");
  if (l.aberto) acoes.push('<button type="button" class="com-icone" data-fin-liquidar="' + l.id + '">' + ic("check", 16) + (receb ? "Registrar recebimento" : "Registrar pagamento") + "</button>");
  if (l.aberto && receb) acoes.push('<button type="button" class="com-icone" data-fin-renegociar="' + l.id + '">' + ic("handshake", 16) + "Renegociar</button>");
  if (!l.aberto) acoes.push('<button type="button" class="com-icone" data-fin-reabrir="' + l.id + '">' + ic("undo", 16) + "Reabrir</button>");
  if (l.cadastro_nome) acoes.push('<button type="button" class="com-icone" data-fin-acervo="' + esc(l.cadastro_nome) + '">' + ic("folder_open", 16) + "Documentos no Acervo</button>");

  const listaComps = comps.length
    ? '<div class="fin-linhas">' + comps.map((k) => '<div class="fin-linha"><span class="duas-linhas"><b>' + esc(k.nome) + "</b><small>" + esc(quandoCurto(k.criado_em)) +
      '</small></span><button class="botao-icone" data-fin-tirar-comp="' + k.id + '" title="Tirar do lançamento" aria-label="Tirar do lançamento">' + ic("close", 16) + "</button></div>").join("") + "</div>"
    : (l.comprovantes ? '<p class="dialogo-dica">' + esc(plural(l.comprovantes, "comprovante guardado", "comprovantes guardados")) + " em outro mês.</p>" : "");

  const html = '<div class="fin-dlg-valor"><b>' + esc(l.valor) + "</b>" + situacao + "</div>" +
    fichaDoDialogo([
      ["Tipo", l.tipo === "recebimento" ? "Recebimento" : "Despesa"],
      ["Categoria", l.categoria_rotulo],
      ["Cliente", l.cadastro_nome || "ninguém do cadastro"],
      ["Vencimento", l.vencimento ? dataExtensa(l.vencimento) : "sem vencimento"],
      l.liquidado_em ? [receb ? "Recebido em" : "Pago em", dataExtensa(l.liquidado_em)] : null,
      l.observacao ? ["Observação", l.observacao] : null,
    ]) +
    '<div class="dialogo-acoes">' + acoes.join("") + "</div>" +
    '<div class="fin-dlg-bloco"><span class="sv-kicker">Comprovantes' + (comps.length ? " · " + comps.length : "") + "</span>" + listaComps +
    '<div class="fin-solta" data-fin-solta="1">Arraste o arquivo aqui ou<button type="button" class="sv-ligacao" data-fin-anexar="1">' + ic("attach_file", 15) + "escolha no computador</button></div>" +
    '<input type="file" id="fin-arquivo" hidden multiple></div>' +
    (l.aberto && receb ? '<p class="dialogo-dica">A cobrança sai como rascunho de e-mail e passa por Aprovações antes de ser enviada.</p>' : "");

  const escolha = dialogo({
    titulo: l.cadastro_nome ? l.cadastro_nome + " · " + l.descricao : l.descricao,
    contexto: "Financeiro › " + (receb ? "A receber" : "A pagar") + " · " + situacaoCurta(l),
    classe: "dialogo-ver fin-dlg", larga: true, html: html, cancelar: "Fechar", confirmar: "Editar",
  });
  const dlg = document.querySelector(".fin-dlg");
  if (dlg) {
    ligarFinanceiro(dlg);
    const arquivo = dlg.querySelector("#fin-arquivo");
    const solta = dlg.querySelector("[data-fin-solta]");
    const anexar = dlg.querySelector("[data-fin-anexar]");
    if (arquivo && solta && anexar) {
      anexar.onclick = (e) => { e.stopPropagation(); arquivo.click(); };
      arquivo.onchange = () => { if (arquivo.files.length) anexarComprovantes(l, [...arquivo.files]); };
      solta.ondragover = (e) => { e.preventDefault(); solta.classList.add("sobre"); };
      solta.ondragleave = () => solta.classList.remove("sobre");
      solta.ondrop = (e) => {
        e.preventDefault();
        solta.classList.remove("sobre");
        if (e.dataTransfer.files.length) anexarComprovantes(l, [...e.dataTransfer.files]);
      };
    }
  }
  const r = await escolha;
  if (r && r.ok) editarLancamento(l.id, false);
}

function novoLancamento() {
  fin.form = { tipo: "despesa", descricao: "", valor: "", categoria: "outros", cadastro_id: null, vencimento: iso(new Date()), liquidado_em: "" };
  finAbrirForm();
}

function editarLancamento(id, renegociando) {
  const l = fin.todos.find((x) => x.id === id);
  if (!l) return;
  fin.form = {
    id: l.id, tipo: l.tipo, descricao: l.descricao, valor: semReais(l.valor), categoria: l.categoria,
    cadastro_id: l.cadastro_id, vencimento: l.vencimento || "", liquidado_em: l.liquidado_em || "", renegociando: !!renegociando,
  };
  finAbrirForm();
}

/* O cadastro do lancamento (pop-up de cadastro): Novo ou Editar, Excluir a
   esquerda do rodape so ao editar. Salvar com erro avisa no rodape e nao
   fecha - o que foi digitado fica. */
function finAbrirForm() {
  const v = fin.form;
  if (!v) return;
  const d = fin.dados;
  const vez = fin.formVez = fin.formVez + 1;
  const campo = (rotulo, controle, id) => '<div class="dialogo-campo"><label for="' + id + '">' + rotulo + '</label><div class="dialogo-caixa">' + controle + "</div></div>";
  const duas = (a, b) => '<div class="dialogo-duas">' + a + b + "</div>";
  const chips = [["recebimento", "Recebimento"], ["despesa", "Despesa"]].map(([t, r]) => {
    const classe = t === v.tipo ? "on" : "";
    return '<button type="button" class="' + classe + '" data-fin-tipo="' + t + '">' + r + "</button>";
  }).join("");
  const corpo =
    '<div class="dialogo-campo"><label>Tipo</label><div class="dialogo-chips">' + chips + "</div></div>" +
    campo("Descrição", '<input type="text" id="fin-f-descricao" value="' + esc(v.descricao || "") + '" placeholder="do que se trata" autocomplete="off">', "fin-f-descricao") +
    duas(campo("Valor", '<input type="text" id="fin-f-valor" value="' + esc(v.valor || "") + '" placeholder="12.000,00" autocomplete="off"><span class="dialogo-sufixo">R$</span>', "fin-f-valor"),
      campo("Categoria", '<select id="fin-f-categoria">' +
        d.opcoes_categoria.map((c) => '<option value="' + esc(c.valor) + '"' + (c.valor === v.categoria ? " selected" : "") + ">" + esc(c.rotulo) + "</option>").join("") +
        "</select>", "fin-f-categoria")) +
    campo("Cliente", '<select id="fin-f-cliente"><option value="">ninguém do cadastro</option>' +
      d.clientes.map((c) => '<option value="' + c.id + '"' + (c.id === Number(v.cadastro_id) ? " selected" : "") + ">" + esc(c.nome) + "</option>").join("") +
      "</select>", "fin-f-cliente") +
    duas(campo("Vencimento", '<input type="date" id="fin-f-vencimento" value="' + esc(v.vencimento || "") + '">', "fin-f-vencimento"),
      campo('<span data-fin-rotulo-liquidado="1">' + (v.tipo === "recebimento" ? "Já recebido em" : "Já pago em") + "</span> <small>se já aconteceu</small>",
        '<input type="date" id="fin-f-liquidado" value="' + esc(v.liquidado_em || "") + '">', "fin-f-liquidado")) +
    (v.renegociando ? '<p class="dialogo-dica">Renegociar é mudar o vencimento ou o valor. O lançamento continua o mesmo.</p>' : "");
  let titulo;
  if (v.renegociando) titulo = "Renegociar";
  else titulo = v.id ? "Editar lançamento" : "Novo lançamento";
  const escolha = dialogo({
    titulo: titulo, contexto: v.id ? "Financeiro › " + v.descricao : "Financeiro · entra na soma assim que for salvo",
    classe: "dialogo-cadastro fin-dlg-form", larga: true,
    html: '<div class="dialogo-form" id="fin-form-pop">' + corpo + "</div>",
    rodape: (v.id ? '<button type="button" class="dialogo-excluir" data-fin-apagar="1">Excluir</button>' : "") + '<span class="dialogo-aviso" data-fin-aviso="1"></span>',
    cancelar: "Cancelar", confirmar: v.id ? "Salvar" : "Lançar", aoConfirmar: salvarLancamento,
  });
  const dlg = document.querySelector(".fin-dlg-form");
  if (dlg) {
    dlg.querySelectorAll("[data-fin-tipo]").forEach((b) => {
      b.onclick = () => {
        v.tipo = b.dataset.finTipo;
        dlg.querySelectorAll("[data-fin-tipo]").forEach((x) => x.classList.toggle("on", x === b));
        const rotulo = dlg.querySelector("[data-fin-rotulo-liquidado]");
        if (rotulo) rotulo.textContent = v.tipo === "recebimento" ? "Já recebido em" : "Já pago em";
      };
    });
    const apagar = dlg.querySelector("[data-fin-apagar]");
    if (apagar) apagar.onclick = apagarLancamento;
    const primeiro = dlg.querySelector(v.renegociando ? "#fin-f-vencimento-botao, #fin-f-vencimento" : "#fin-f-descricao");
    if (primeiro) primeiro.focus();
  }
  // Fechou sem salvar (Cancelar, Esc, clique fora): o formulario sai junto.
  escolha.then(() => { if (fin.formVez === vez) fin.form = null; });
}

async function salvarLancamento() {
  const v = fin.form;
  const dlg = document.querySelector(".fin-dlg-form");
  if (!v || !dlg) return;
  const valor = (id) => { const el = dlg.querySelector("#" + id); return el ? el.value : ""; };
  const aviso = dlg.querySelector("[data-fin-aviso]");
  const dados = {
    tipo: v.tipo, descricao: valor("fin-f-descricao").trim(), valor: valor("fin-f-valor").trim(), categoria: valor("fin-f-categoria"),
    cadastro_id: Number(valor("fin-f-cliente")) || null, vencimento: valor("fin-f-vencimento"), liquidado_em: valor("fin-f-liquidado"),
  };
  if (!dados.descricao) { aviso.textContent = "diga do que se trata"; dlg.querySelector("#fin-f-descricao").focus(); return; }
  const r = await fetch("/api/financeiro/lancamentos", {
    method: "POST", headers: FIN_JSON, body: JSON.stringify({ id: v.id || null, dados: dados }),
  });
  if (!r.ok) { aviso.textContent = await erroDe(r); return; }
  const salvo = await r.json();
  fin.form = null;
  if (dialogoAberto) dialogoAberto.fechar({ ok: true });
  const mes = salvo && salvo.id ? mesDoLancamento(salvo) : "";
  if (mes && mes !== fin.mes) fin.mes = mes;
  avisoCert(v.id ? "lançamento atualizado" : "lançamento salvo — já entra na soma", { tom: "ok" });
  mostrarFinanceiro();
}

function apagarLancamentosEmLote(ids) {
  return apagarEmLote(ids, (id) => "/api/financeiro/lancamentos/" + id, {
    rotulo: "lançamento", contexto: "Financeiro › Lançamentos", texto: "Os comprovantes ligados vão junto.",
    depois: () => { fin.escolhidos.clear(); fin.form = null; fin.aberto = null; mostrarFinanceiro(); },
  });
}

async function apagarLancamento() {
  const v = fin.form;
  if (!v || !v.id) return;
  fin.form = null;
  if (!(await confirmar({ titulo: "Excluir este lançamento?", contexto: "Financeiro › " + v.descricao, texto: "Os comprovantes ligados a ele vão junto. " + LIXEIRA_TEXTO, confirmar: "Excluir", perigo: true }))) return;
  const r = await fetch("/api/financeiro/lancamentos/" + v.id, { method: "DELETE" });
  fin.aberto = null;
  mostrarFinanceiro();
  avisarLixeira(r, () => mostrarFinanceiro());
}

async function liquidarLancamento(id) {
  const l = fin.todos.find((x) => x.id === id);
  const r = await fetch("/api/financeiro/lancamentos/" + id + "/liquidar", { method: "POST", headers: FIN_JSON, body: "{}" });
  if (!r.ok) { avisoCert(await erroDe(r)); return; }
  const receb = l && l.tipo === "recebimento";
  avisoCert((receb ? "recebimento" : "pagamento") + " registrado hoje" + (receb ? "" : " — anexe o comprovante no lançamento"), { tom: "ok" });
  mostrarFinanceiro();
}

async function reabrirLancamento(id) {
  const r = await fetch("/api/financeiro/lancamentos/" + id + "/reabrir", { method: "POST", headers: FIN_JSON, body: "{}" });
  if (!r.ok) { avisoCert(await erroDe(r)); return; }
  avisoCert("lançamento reaberto — volta para as listas de aberto");
  mostrarFinanceiro();
}

async function anexarComprovantes(l, arquivos) {
  if (!l) return;
  for (const arquivo of arquivos) {
    const forma = new FormData();
    forma.append("arquivo", arquivo);
    const r = await fetch("/api/financeiro/lancamentos/" + l.id + "/comprovante", { method: "POST", body: forma });
    if (!r.ok) { avisoCert(await erroDe(r), { tom: "erro" }); return; }
  }
  avisoCert(plural(arquivos.length, "comprovante ligado", "comprovantes ligados") + " a “" + l.descricao + "”", { tom: "ok" });
  await mostrarFinanceiro();
  finVerLancamento(l.id);
}

/* A cobranca sai como rascunho de e-mail: o envio segue o caminho de sempre,
   com a fila de Aprovacoes no meio. */
async function prepararCobranca(id) {
  const r = await fetch("/api/financeiro/cobrar", { method: "POST", headers: FIN_JSON, body: JSON.stringify({ id: id }) });
  if (!r.ok) { avisoCert(await erroDe(r)); return; }
  const d = await r.json();
  if (d.sem_email) {
    avisoCert("o cliente " + (d.cliente || "deste lançamento") + " não tem e-mail no cadastro");
    return;
  }
  if (!mail.contas) {
    try { mail.contas = await (await fetch("/api/email/contas")).json(); } catch (err) { mail.contas = null; }
  }
  if (!mail.contas || !mail.contas.contas.length) { marcarDestino("caixa"); return mostrarEmail(); }
  mail.conta = mail.contas.contas.find((c) => c.em_uso) || mail.contas.contas[0];
  marcarDestino("caixa");
  telaEscrever({ para: d.para, assunto: d.assunto, corpo: d.corpo });
}

/* ---------------------------------------------------- a folha, no pop-up */

async function finVerFolha() {
  const f = fin.dados.folha;
  if (!f || !f.quantos) return;
  const linhas = (f.pessoas || []).map((p) =>
    '<div class="fin-linha"><span class="duas-linhas"><b>' + esc(p.nome) + "</b><small>" +
    esc(p.vinculo_rotulo + " · salário " + semReais(p.salario) + " · encargos " + semReais(p.encargos)) +
    '</small></span><span class="fin-valor">' + esc(semReais(p.total)) + "</span></div>").join("");
  const escolha = dialogo({
    titulo: "Folha de " + mesCurto(f.mes), contexto: "Financeiro › " + plural(f.quantos, "pessoa") + " · " + f.total_texto,
    classe: "dialogo-ver fin-dlg", larga: true,
    html: '<div class="fin-dlg-bloco"><span class="sv-kicker">Pessoas</span><div class="fin-linhas">' + linhas + "</div></div>" +
      '<div class="fin-dlg-bloco"><span class="sv-kicker">Totais do mês</span>' +
      fichaDoDialogo([["Salários", f.salarios_texto], ["Encargos e INSS", f.encargos_texto], ["Estagiários", f.estagios_texto], ["Total", f.total_texto]]) + "</div>" +
      '<div class="dialogo-acoes"><button type="button" class="com-icone" data-fin-folha="recibos">' + ic("receipt_long", 16) + "Gerar recibos</button></div>" +
      '<p class="dialogo-dica">Os valores foram copiados do cadastro quando a folha foi montada. Mudar o salário depois não reescreve este mês.</p>',
    cancelar: "Fechar", confirmar: f.lancamento_id ? "Ver o lançamento" : "Lançar em contas a pagar",
  });
  const dlg = document.querySelector(".fin-dlg");
  if (dlg) ligarFinanceiro(dlg);
  const r = await escolha;
  if (!r || !r.ok) return;
  if (f.lancamento_id) finVerLancamento(f.lancamento_id);
  else pedirFolha("pagar");
}

async function pedirFolha(acao) {
  avisoCert(acao === "montar" ? "montando a folha…" : "lançando…");
  const r = await fetch("/api/financeiro/folha/" + acao, { method: "POST", headers: FIN_JSON, body: JSON.stringify({ mes: fin.mes || "" }) });
  if (!r.ok) { avisoCert(await erroDe(r)); return; }
  await mostrarFinanceiro();
  avisoCert(acao === "montar" ? "folha montada" : "folha lançada em contas a pagar — vence no último dia do mês", { tom: "ok" });
}

async function gerarRecibos() {
  avisoCert("gerando os recibos…");
  const r = await fetch("/api/financeiro/folha/recibos", { method: "POST", headers: FIN_JSON, body: JSON.stringify({ mes: fin.mes || "" }) });
  if (!r.ok) { avisoCert(await erroDe(r)); return; }
  const d = await r.json();
  avisoCert(plural(d.recibos.length, "recibo") + " em " + d.pasta);
  fetch("/api/biblioteca/abrir-pasta", { method: "POST", headers: FIN_JSON, body: JSON.stringify({ caminho: d.pasta }) });
}

/* -------------------------------------------- notas e boletos, no pop-up */

/* Nota fiscal e boleto: a nota sai na prefeitura e o boleto sai do banco.
   Aqui so se guarda o registro - dizer que emite seria mentir. */
function finFormPapel(tipo, de) {
  const eNota = tipo === "nota";
  const campo = (rotulo, controle, id) => '<div class="dialogo-campo"><label for="' + id + '">' + rotulo + '</label><div class="dialogo-caixa">' + controle + "</div></div>";
  const corpo =
    campo(eNota ? "Número da nota" : "Número ou identificação", '<input type="text" id="fin-p-numero" value="" autocomplete="off" placeholder="' + (eNota ? "2026/118" : "linha digitável ou número") + '">', "fin-p-numero") +
    '<div class="dialogo-duas">' +
    campo("Valor", '<input type="text" id="fin-p-valor" placeholder="1.200,00" autocomplete="off" value="' + esc(de ? semReais(emReais(de.centavos)) : "") + '"><span class="dialogo-sufixo">R$</span>', "fin-p-valor") +
    campo(eNota ? "Emitida em" : "Vence em", '<input type="date" id="fin-p-data" value="' + iso(new Date()) + '">', "fin-p-data") + "</div>" +
    campo("Cliente", '<select id="fin-p-cliente"><option value="">Sem cliente</option>' +
      (fin.dados.clientes || []).map((c) => '<option value="' + c.id + '"' + (de && de.cliente === c.nome ? " selected" : "") + ">" + esc(c.nome) + "</option>").join("") +
      "</select>", "fin-p-cliente") +
    (de ? '<p class="dialogo-dica">Fica ligada ao recebimento “' + esc(de.descricao) + "”.</p>" : "") +
    '<p class="dialogo-dica">' + (eNota
      ? "A nota é emitida no sistema da prefeitura. Aqui fica só o registro: número, valor e data."
      : "O boleto é gerado pelo seu banco. Aqui fica o registro, e o vencido aparece em Precisa de você.") + "</p>";
  dialogo({
    titulo: eNota ? "Registrar nota emitida" : "Registrar boleto", contexto: "Financeiro › " + (eNota ? "Notas fiscais" : "Boletos"),
    classe: "dialogo-cadastro fin-dlg-papel", larga: true,
    html: '<div class="dialogo-form">' + corpo + "</div>",
    rodape: '<span class="dialogo-aviso" data-fin-aviso="1"></span>',
    cancelar: "Cancelar", confirmar: "Guardar registro", aoConfirmar: () => salvarPapel(tipo, de),
  });
  const primeiro = document.getElementById("fin-p-numero");
  if (primeiro) primeiro.focus();
}

async function salvarPapel(tipo, de) {
  const dlg = document.querySelector(".fin-dlg-papel");
  if (!dlg) return;
  const campo = (id) => { const el = dlg.querySelector("#" + id); return el ? el.value : ""; };
  const aviso = dlg.querySelector("[data-fin-aviso]");
  const centavos = centavosDe(campo("fin-p-valor"));
  if (!centavos) { aviso.textContent = "diga o valor"; dlg.querySelector("#fin-p-valor").focus(); return; }
  const r = await fetch("/api/financeiro/papeis", {
    method: "POST", headers: FIN_JSON,
    body: JSON.stringify({ id: null, dados: {
      tipo: tipo, numero: campo("fin-p-numero").trim(), centavos: centavos,
      cadastro_id: Number(campo("fin-p-cliente")) || null, lancamento_id: de ? de.id : null, data: campo("fin-p-data"),
    } }),
  });
  if (!r.ok) { aviso.textContent = await erroDe(r); return; }
  if (dialogoAberto) dialogoAberto.fechar({ ok: true });
  avisoCert(tipo === "nota" ? "nota registrada" : "boleto registrado", { tom: "ok" });
  mostrarFinanceiro();
}

/* A lista de um papel do mes: notas (e o que foi recebido sem nota),
   boletos ou comprovantes. */
async function finVerPapeis(tipo) {
  const d = fin.dados;
  const hoje = iso(new Date());
  const linha = (titulo, sub, subAcc, valor, botoes) => '<div class="fin-linha"><span class="duas-linhas"><b>' + esc(titulo) + '</b><small class="' + (subAcc ? "fin-acc" : "") + '">' +
    esc(sub) + "</small></span>" + (valor ? '<span class="fin-valor">' + esc(semReais(valor)) + "</span>" : "") + botoes + "</div>";
  const tirar = (atributo, id, rotulo) => '<button class="botao-icone" ' + atributo + '="' + id + '" title="' + rotulo + '" aria-label="' + rotulo + '">' + ic("close", 16) + "</button>";
  let titulo, linhas, confirmarRotulo, depois, vazio;
  if (tipo === "nota") {
    titulo = "Notas fiscais";
    linhas = (d.notas_a_emitir || []).map((x) => linha(x.cliente || x.descricao, "recebido · falta registrar a nota", false, emReais(x.centavos),
      '<button data-fin-nota-de="' + x.id + '">Registrar</button>')).join("") +
      (d.notas || []).map((n) => linha((n.numero ? "NF " + n.numero + " · " : "") + (n.cliente || "sem cliente"), "emitida em " + n.data_br, false, n.valor,
        tirar("data-fin-tirar-papel", n.id, "Tirar o registro"))).join("");
    vazio = "Nenhuma nota registrada neste mês.";
    confirmarRotulo = "Registrar nota";
    depois = () => finFormPapel("nota", null);
  } else if (tipo === "boleto") {
    titulo = "Boletos";
    linhas = (d.boletos || []).map((b) => {
      const vencido = b.situacao === "aberto" && b.data && b.data < hoje;
      let sub;
      if (b.situacao === "pago") sub = "pago";
      else sub = (vencido ? "venceu em " : "vence em ") + b.data_br;
      return linha(b.cliente || b.numero || "sem cliente", sub, vencido, b.valor,
        (b.situacao === "aberto" ? '<button data-fin-boleto-pago="' + b.id + '">Dar baixa</button>' : "") + tirar("data-fin-tirar-papel", b.id, "Tirar o registro"));
    }).join("");
    vazio = "Nenhum boleto neste mês.";
    confirmarRotulo = "Registrar boleto";
    depois = () => finFormPapel("boleto", null);
  } else {
    titulo = "Comprovantes";
    linhas = (d.sem_comprovante || []).map((x) => linha(x.descricao, "pago em " + dataBR(x.liquidado_em) + " · sem comprovante", false, x.valor,
      '<button data-fin-abrir="' + x.id + '">Anexar</button>')).join("") +
      (d.comprovantes || []).map((k) => linha(k.nome, k.descricao + " · " + dataBR(k.liquidado_em), false, "",
        '<button data-fin-abrir="' + k.lancamento_id + '">Abrir</button>' + tirar("data-fin-tirar-comp", k.id, "Tirar do lançamento"))).join("");
    vazio = "Nenhum comprovante neste mês.";
    confirmarRotulo = "Ver lançamentos";
    depois = () => { fin.visao = "lancamentos"; fin.filtro = "todos"; mostrarFinanceiro(); };
  }
  const dica = {
    nota: "A nota é emitida no sistema da prefeitura; aqui fica o registro. Recebimento sem nota registrada aparece no topo.",
    boleto: "O boleto é gerado pelo seu banco; aqui fica o registro e o vencimento.",
    comprovante: "Cada comprovante fica ligado a um lançamento. Para anexar, abra o lançamento.",
  }[tipo];
  const escolha = dialogo({
    titulo: titulo, contexto: "Financeiro › " + maiuscula(mesCurto(fin.mes)), classe: "dialogo-ver fin-dlg", larga: true,
    html: '<div class="fin-linhas">' + (linhas || '<p class="dialogo-dica">' + vazio + "</p>") + "</div>" + '<p class="dialogo-dica">' + dica + "</p>",
    cancelar: "Fechar", confirmar: confirmarRotulo,
  });
  const dlg = document.querySelector(".fin-dlg");
  if (dlg) ligarFinanceiro(dlg);
  const r = await escolha;
  if (r && r.ok) depois();
}

async function baixarBoleto(id) {
  const r = await fetch("/api/financeiro/papeis/" + id + "/pago", { method: "POST", headers: FIN_JSON, body: "{}" });
  if (!r.ok) { avisoCert(await erroDe(r)); return; }
  avisoCert("baixa dada no boleto", { tom: "ok" });
  mostrarFinanceiro();
}

/* O contrato quitado: os documentos do cliente no Acervo, para mover a
   pasta por la - mover e efeito externo e vai pela fila como todo o resto. */
async function arquivarCliente(id) {
  const cliente = (fin.dados.concluidos || []).find((c) => c.id === id);
  if (!cliente) return;
  await verNoAcervo(cliente.nome);
  avisoCert("os documentos de " + cliente.nome + " — selecione e use Mover para pasta");
}

async function verNoAcervo(nome) {
  bib.termo = nome || "";
  bib.filtro = "todos";
  marcarDestino("biblioteca");
  await mostrarBiblioteca();
}

/* --------------------------------------------------------- miudezas */

/* Um numero com rotulo em cima; Foco e bem-estar usa o mesmo cartao. */
function numeroRel(rotulo, valor) {
  return '<div class="rel-numero"><small>' + esc(rotulo) + "</small><b>" + esc(String(valor)) + "</b></div>";
}

function semReais(texto) {
  return String(texto || "").replace(/R\$\s?/, "");
}

function dataExtensa(iso) {
  const m = /^(\d{4})-(\d{2})-(\d{2})/.exec(iso || "");
  if (!m) return iso || "—";
  return Number(m[3]) + " " + MESES_CURTOS[Number(m[2]) - 1] + " " + m[1];
}

function mesDeHoje() {
  return iso(new Date()).slice(0, 7);
}

function mesDoLancamento(l) {
  return String(l.vencimento || l.liquidado_em || "").slice(0, 7);
}

function ultimoDiaDoMes(mes) {
  const [a, m] = String(mes || mesDeHoje()).split("-").map(Number);
  return iso(new Date(a, m, 0));
}

/* O relatorio e de um dia; para o mes escolhido vale o ultimo dia dele. */
function quandoDoRelatorio() {
  if (!fin.mes || fin.mes === mesDeHoje()) return "";
  return ultimoDiaDoMes(fin.mes);
}

/* ------------------------------------------- o extrato do banco (A9) */

/* O arquivo do banco vira uma lista de propostas: cada linha do extrato com o
   lancamento que parece ser ela. Nada e gravado ate a pessoa marcar e
   confirmar - dar baixa por conta propria num livro-caixa alheio, por causa
   de um valor igual, seria palpite com a cara de conferencia. */
function escolherExtrato() {
  const campo = document.createElement("input");
  campo.type = "file";
  campo.accept = ".ofx,.csv,.txt";
  campo.onchange = () => {
    const arquivo = campo.files && campo.files[0];
    if (arquivo) lerExtrato(arquivo);
  };
  campo.click();
}

async function lerExtrato(arquivo) {
  const corpo = new FormData();
  corpo.append("arquivo", arquivo, arquivo.name);
  avisoCert("lendo o extrato…");
  const r = await fetch("/api/financeiro/banco", { method: "POST", body: corpo });
  if (!r.ok) { avisoCert(await erroDe(r), { tom: "erro" }); return; }
  const d = await r.json();
  fin.extrato = d;
  // Os pares que o programa achou ja vem marcados; os sem par, nao - lancar
  // de novo o que ja esta lancado e o erro caro aqui.
  fin.baixas = new Set(d.pares.map((p, i) => (p.lancamento_id ? i : -1)).filter((i) => i >= 0));
  fin.novos = new Set();
  fin.visao = "lancamentos";
  desenharFinanceiro();
  avisoCert(d.resumo.conciliados + " de " + plural(d.resumo.movimentos, "linha") + " com lançamento correspondente", { tom: "ok" });
}

/* A conferencia aparece em cima da tabela, na propria pagina: e uma revisao
   linha a linha, que se faz olhando os lancamentos logo abaixo. */
function finConferenciaHtml() {
  const e = fin.extrato;
  const r = e.resumo || {};
  const linhas = (e.pares || []).map((p, i) => {
    const m = p.movimento;
    const entrada = m.centavos >= 0;
    const marcada = p.lancamento_id ? fin.baixas.has(i) : fin.novos.has(i);
    const classe = "fin-conc" + (marcada ? " marcada" : "") + (p.lancamento_id ? "" : " sozinha");
    const alvo = p.lancamento
      ? "<small>dá baixa em “" + esc(p.lancamento.descricao) + "”" +
        (p.lancamento.cliente ? " · " + esc(p.lancamento.cliente) : "") +
        (p.lancamento.vencimento ? " · vence " + dataCurta(p.lancamento.vencimento) : "") + "</small>" +
        '<small class="fin-conc-porque">' + esc(p.porque) + "</small>"
      : '<small class="fin-conc-porque">sem lançamento correspondente · marcar lança este valor como novo</small>';
    return '<label class="' + classe + '"><input type="checkbox" data-fin-conc="' + i + '"' + (marcada ? " checked" : "") + ">" +
      '<span class="duas-linhas"><b>' + esc(m.descricao) + "</b>" + alvo + "</span>" +
      '<span class="fin-conc-valor"><b class="' + (entrada ? "entra" : "sai") + '">' + esc(emReais(m.centavos)) + "</b>" +
      "<small>" + dataCurta(m.data) + "</small></span></label>";
  }).join("");

  const quantas = fin.baixas.size + fin.novos.size;
  const meta = esc(e.arquivo || "extrato") + " · " + plural(r.movimentos || 0, "linha") + (r.de ? " · " + dataCurta(r.de) + " a " + dataCurta(r.ate) : "") +
    " · " + (r.conciliados || 0) + " com lançamento";
  return finSecao("fin-conferir", ic("sync", 16) + "Conferir com o banco", meta, "",
    '<div class="fin-conc-lista">' + linhas + "</div>" +
    '<p class="fin-conc-nota">Nada é gravado até você confirmar. Marcado com lançamento recebe a baixa na data do banco; ' +
    "marcado sem lançamento entra como lançamento novo, já pago, na categoria Outros.</p>" +
    '<div class="fin-conc-botoes"><button data-fin-conc-sair="1">Descartar</button><button class="primario" data-fin-conc-aplicar="1"' + (quantas ? "" : " disabled") + ">" +
    ic("check", 16) + "Conferir " + plural(quantas, "linha") + "</button></div>");
}

async function aplicarConciliacao() {
  const e = fin.extrato;
  const baixas = [];
  const novos = [];
  (e.pares || []).forEach((p, i) => {
    const m = p.movimento;
    if (p.lancamento_id && fin.baixas.has(i)) baixas.push({ lancamento_id: p.lancamento_id, data: m.data });
    else if (!p.lancamento_id && fin.novos.has(i)) {
      novos.push({ descricao: m.descricao, centavos: m.centavos, data: m.data, categoria: "outros" });
    }
  });
  if (!baixas.length && !novos.length) { avisoCert("marque o que deve ser conferido"); return; }
  if (!(await confirmar({
    titulo: "Conferir com o banco?",
    contexto: "Financeiro › " + (e.arquivo || "extrato"),
    texto: plural(baixas.length, "lançamento") + " recebe baixa na data do banco" +
      (novos.length ? " e " + plural(novos.length, "linha") + " entra como lançamento novo" : "") +
      ". Dá para desfazer lançamento por lançamento depois, em Lançamentos.",
    confirmar: "Conferir",
  }))) return;

  const r = await fetch("/api/financeiro/banco/aplicar", {
    method: "POST", headers: FIN_JSON, body: JSON.stringify({ baixas: baixas, novos: novos }),
  });
  if (!r.ok) { avisoCert(await erroDe(r), { tom: "erro" }); return; }
  const d = await r.json();
  fin.extrato = null;
  fin.baixas = new Set();
  fin.novos = new Set();
  await carregarFinanceiro();
  desenharFinanceiro();
  avisoCert(d.aviso, { tom: "ok" });
  if ((d.erros || []).length) avisoCert(d.erros[0], { tom: "erro" });
}
