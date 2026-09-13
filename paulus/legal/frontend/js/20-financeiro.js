/* ------------------------ financeiro, relatórios, bem-estar, conexões */
/*
   As telas que precisam de história. Todo número aqui é soma do que já está
   gravado — quando não há lançamento, o número é zero e a tela diz que está
   vazio, em vez de desenhar um gráfico bonito de dado que ninguém digitou.
*/


/* --------------------------------------------------------- financeiro */
/*
   Financeiro (docs/ui/03-telas-desktop.md, A9): Visao geral, Lancamentos e
   Relatorios numa tela so, com o painel fixo a direita. Todo numero continua
   sendo soma do que esta gravado; o que ainda nao tem motor (conciliacao
   bancaria, importar extrato, cobrar por WhatsApp, pagar pela fila de
   Aprovacoes) diz isso na tela em vez de fingir.
*/

const fin = {
  visao: "geral", mes: "", dados: null, lista: null, todos: null,
  filtro: "todos", categoria: "", aberto: null, form: null, papel: null,
  folhaAberta: false, pedidos: [], rel: null, relAba: "financeiro",
  parecer: null, parecerErro: "", pedindo: false, numerosAbertos: false,
};

const FIN_JSON = { "Content-Type": "application/json" };

async function mostrarFinanceiro(visao) {
  if (visao) fin.visao = visao;
  abrirTela("Financeiro", { cheia: true });
  marcarDestino("financeiro");
  $("centro").innerHTML = '<div class="acervo sem-painel"><div class="acervo-principal"><p class="nota">somando…</p></div></div>';
  atualizarPostura();
  try {
    await carregarFinanceiro();
  } catch (err) {
    $("centro").innerHTML = '<div class="acervo sem-painel"><div class="acervo-principal"><p class="nota">não consegui abrir: ' +
      esc(String(err)) + "</p></div></div>";
    return;
  }
  desenharFinanceiro();
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
  if (fin.aberto) fin.aberto = fin.todos.find((l) => l.id === fin.aberto.id) || null;
}

function desenharFinanceiro() {
  cabecalhoFinanceiro();
  let miolo;
  if (fin.visao === "lancamentos") miolo = corpoDosLancamentos() + painelDosLancamentos();
  else if (fin.visao === "relatorios") miolo = corpoDosRelatorios() + painelDosRelatorios();
  else miolo = corpoDaVisaoGeral() + painelDaVisaoGeral();
  $("centro").innerHTML = '<div class="acervo fin-tela" id="financeiro">' + miolo + "</div>";
  ligarFinanceiro();
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
    meta.innerHTML = esc(mesRotulo) + (fecha ? " · fechamento em " + plural(fecha, "dia") : " · mês encerrado") +
      '<span class="fin-meta-ponto" title="Conciliação bancária ainda não existe: sem extrato importado, não há o que conferir"><i></i>conciliação bancária em breve</span>';
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

/* ---------------------------------------------------- a visao geral */

function corpoDaVisaoGeral() {
  const d = fin.dados;
  const p = d.painel;
  const folha = d.folha || {};
  const numero = (rotulo, valor, sub, valorAcc, subTom) => {
    const classe = valorAcc ? "acc" : "";
    const classeSub = "fin-sub" + (subTom ? " " + subTom : "");
    return '<div class="fin-numero"><small>' + esc(rotulo) + '</small><b class="' + classe + '">' + esc(valor) +
      '</b><span class="' + classeSub + '">' + esc(sub) + "</span></div>";
  };
  const fluxo = d.fluxo || [];
  const fluxoMes = fluxo.find((m) => m.mes === fin.mes) || null;
  const teto = Math.max(1, ...fluxo.map((m) => Math.max(m.entradas, m.saidas)));
  const barras = fluxo.map((m) =>
    '<div class="fin-fluxo-mes" title="' + esc(maiuscula(m.rotulo) + ": entradas " + m.entradas_texto + " · saídas " + m.saidas_texto) + '">' +
    '<span style="height:' + Math.round(m.entradas * 100 / teto) + '%"></span>' +
    '<span class="fin-saida" style="height:' + Math.round(m.saidas * 100 / teto) + '%"></span></div>').join("");
  const rotulos = fluxo.map((m) => "<span>" + esc(maiuscula(m.rotulo)) + "</span>").join("");

  const receber = d.receber || [];
  const mostrados = receber.slice(0, 5);

  let folhaHtml;
  let folhaMeta;
  if (folha.quantos) {
    folhaMeta = plural(folha.quantos, "pessoa") + " · " + mesCurto(folha.mes);
    folhaHtml = '<div class="fin-folha"><span class="fin-folha-total">' + esc(folha.total_curto) + "</span>" +
      '<div class="fin-folha-linhas"><div><span>Salários</span><b>' + esc(semReais(folha.salarios_texto)) + "</b></div>" +
      "<div><span>Encargos e INSS</span><b>" + esc(semReais(folha.encargos_texto)) + "</b></div>" +
      "<div><span>Estagiários</span><b>" + esc(semReais(folha.estagios_texto)) + "</b></div></div>" +
      '<div class="fin-botoes"><button data-fin-folha="ver">' + ic("list", 16) + "Ver detalhamento</button>" +
      '<button data-fin-folha="recibos">' + ic("receipt_long", 16) + "Gerar recibos</button>" +
      (folha.lancamento_id
        ? '<span class="fin-feito">' + ic("check_circle", 16) + "já em contas a pagar</span>"
        : '<button class="primario" data-fin-folha="pagar">' + ic("schedule_send", 16) + "Lançar em contas a pagar</button>") +
      "</div></div>";
  } else if ((d.candidatos_folha || []).length) {
    folhaMeta = "nada montado";
    folhaHtml = '<div class="fin-folha"><p>' + esc(plural(d.candidatos_folha.length, "pessoa")) +
      " com vínculo definido. Montar a folha copia os valores de hoje para este mês — depois disso, mudar o salário no cadastro não reescreve este mês.</p>" +
      '<div class="fin-botoes"><button class="primario" data-fin-folha="montar">' + ic("add", 16) + "Montar a folha de " + esc(mesCurto(fin.mes)) + "</button></div></div>";
  } else {
    folhaMeta = "nada montado";
    folhaHtml = '<div class="fin-folha"><p>Ninguém tem vínculo definido ainda. Abra <b>Cadastros</b>, escolha a pessoa e diga como ela é paga e quanto recebe — a folha sai daí. Sem isso eu não invento valor.</p>' +
      '<div class="fin-botoes"><button data-fin-cadastros="1">' + ic("contacts", 16) + "Ir para Cadastros</button></div></div>";
  }

  return '<div class="acervo-principal fin-geral">' +
    '<div class="fin-numeros">' +
    numero("Saldo em caixa", p.saldo_texto, p.resultado_mes_texto + " no mês", false, (p.resultado_mes || 0) >= 0 ? "ok" : "acc") +
    numero("A receber", p.a_receber_texto, plural(p.a_receber_quantos, "cobrança aberta", "cobranças abertas")) +
    numero("A pagar", p.a_pagar_texto, plural(p.a_pagar_quantos, "conta") + (folha.lancamento_id ? " · folha inclusa" : "")) +
    numero("Em atraso", p.atrasado_texto, plural(p.atrasado_quantos, "cobrança"), p.atrasado > 0, p.atrasado > 0 ? "acc" : "") +
    "</div>" +
    '<div class="fin-grade">' +
    '<div class="fin-cartao"><div class="fin-cartao-cabeca"><span>Fluxo de caixa · 6 meses</span>' +
    '<span class="fin-legenda"><span><i></i>Entradas</span><span><i class="fin-saida"></i>Saídas</span></span></div>' +
    '<div class="fin-fluxo">' +
    (p.tem_dado ? "" : '<div class="fin-vazio">Nada lançado ainda. Todo número desta tela é soma dos lançamentos que existem — enquanto não houver nenhum, prefiro mostrar zero a desenhar um gráfico de dado que ninguém digitou.' +
      '<button class="primario" data-fin-novo="1">Lançar o primeiro</button></div>') +
    '<div class="fin-fluxo-grade">' + barras + "</div>" +
    '<div class="fin-fluxo-rotulos">' + rotulos + "</div>" +
    '<div class="fin-fluxo-somas"><div><small>Entradas no mês</small><b>' + esc(fluxoMes ? fluxoMes.entradas_texto : "—") + "</b></div>" +
    "<div><small>Saídas no mês</small><b>" + esc(fluxoMes ? fluxoMes.saidas_texto : "—") + "</b></div></div>" +
    "</div></div>" +
    '<div class="fin-coluna">' +
    '<div class="fin-cartao"><div class="fin-cartao-cabeca"><span>Recebimentos</span><small>' + esc(plural(p.a_receber_quantos, "aberto")) + "</small></div>" +
    '<div class="fin-rolagem">' + (mostrados.length ? mostrados.map(itemDeLancamento).join("") : '<p class="rel-vazio">Nenhuma cobrança em aberto.</p>') + "</div>" +
    '<div class="fin-cartao-rodape"><span>' + mostrados.length + " de " + p.a_receber_quantos + "</span>" +
    '<button class="em-ligacao forte" data-fin-ver-lancamentos="receber">Todos os lançamentos →</button></div></div>' +
    '<div class="fin-cartao"><div class="fin-cartao-cabeca"><span>Folha de pagamento</span><small>' + esc(folhaMeta) + "</small></div>" + folhaHtml + "</div>" +
    "</div></div></div>";
}

/* Uma linha de lista: bolinha, nome em duas linhas e o valor. */
function itemDeLancamento(l) {
  const classe = l.atrasado ? "acc" : (l.aberto ? "" : "mute");
  const classeSub = l.atrasado ? "acc" : "";
  const nome = l.cadastro_nome ? l.cadastro_nome + " · " + l.descricao : l.descricao;
  return '<div class="fin-item" data-fin-abrir="' + l.id + '"><i class="' + classe + '"></i>' +
    '<span class="duas-linhas"><b>' + esc(nome) + '</b><small class="' + classeSub + '">' + esc(situacaoCurta(l)) + "</small></span>" +
    '<span class="fin-valor">' + esc(semReais(l.valor)) + "</span></div>";
}

function itemCurtoDeLancamento(l) {
  const classe = l.atrasado ? "acc" : (l.aberto ? "" : "mute");
  return '<div class="fin-linha fin-clicavel" data-fin-abrir="' + l.id + '"><i class="' + classe + '"></i>' +
    '<span class="duas-linhas"><b>' + esc(l.descricao) + "</b><small>" + esc(situacaoCurta(l)) + "</small></span>" +
    '<span class="fin-valor">' + esc(semReais(l.valor)) + "</span></div>";
}

function situacaoCurta(l) {
  if (!l.aberto) return (l.tipo === "recebimento" ? "recebido " : "pago ") + dataBR(l.liquidado_em).slice(0, 5);
  if (l.atrasado) return "atrasado " + plural(l.dias_atraso, "dia");
  if (l.vencimento) return "vence " + dataBR(l.vencimento).slice(0, 5);
  return "sem vencimento";
}

function painelDaVisaoGeral() {
  if (fin.folhaAberta) return painelDaFolha();
  if (fin.papel) return painelDoPapel();
  const d = fin.dados;
  const pedidos = pedidosDoMes();
  const f = d.fechamento || {};
  const faltas = f.faltas || [];
  const notas = d.notas || [];
  const aEmitir = d.notas_a_emitir || [];
  const boletos = d.boletos || [];
  const abertos = boletos.filter((b) => b.situacao === "aberto");
  const comprovantes = d.comprovantes || [];
  const semComp = d.sem_comprovante || [];
  const concluidos = d.concluidos || [];
  const hoje = iso(new Date());

  let html = '<aside class="acervo-painel fin-painel"><div class="rolagem">' +
    '<div class="painel-cabeca"><span class="titulo-painel"><h3>Precisa de você</h3><span class="meta">' +
    (pedidos.length ? "<b>" + esc(plural(pedidos.length, "item", "itens")) + "</b> · cobrar por e-mail passa por Aprovações" : "nada esperando decisão sua") +
    "</span></span></div>";
  html += pedidos.length
    ? '<div class="fin-pedidos">' + pedidos.map(pedeHtml).join("") + "</div>"
    : '<p class="fin-nada">Nenhuma cobrança atrasada, nenhuma conta vencendo nesta semana e nenhum papel faltando. Quando algo precisar de decisão sua, aparece aqui.</p>';

  html += '<div class="painel-bloco"><div class="fin-bloco-cabeca">' + (fin.pedindo ? coroa(18) : "") +
    "<span>Parecer do mês</span><small>gerado na sua máquina</small></div>" + parecerHtml(false) +
    '<div class="fin-botoes">' +
    (fin.parecer || fin.pedindo ? "" : '<button data-fin-parecer="1">' + ic("insights", 16) + "Pedir o parecer</button>") +
    '<button data-fin-visao="relatorios">' + ic("bar_chart", 16) + "Ver relatório</button></div></div>";

  html += '<div class="painel-bloco"><div class="painel-bloco-cabeca"><span>Notas fiscais</span><span class="contagem">' +
    esc(plural(notas.length, "registrada")) + " no mês</span></div>" +
    '<div class="fin-linhas">' +
    aEmitir.map((x) => '<div class="fin-linha"><span class="duas-linhas"><b>' + esc(x.cliente || x.descricao) +
      '</b><small class="fin-acc">recebido · a registrar</small></span><span class="fin-valor">' + esc(semReais(emReais(x.centavos))) +
      '</span><button data-fin-nota-de="' + x.id + '">Registrar</button></div>').join("") +
    notas.map((n) => '<div class="fin-linha"><span class="duas-linhas"><b>' + esc((n.numero ? "NF " + n.numero + " · " : "") + (n.cliente || "sem cliente")) +
      "</b><small>" + esc(n.data_br) + '</small></span><span class="fin-valor">' + esc(semReais(n.valor)) +
      '</span><button class="botao-icone" data-fin-tirar-papel="' + n.id + '" title="Tirar o registro">' + ic("close", 16) + "</button></div>").join("") +
    (notas.length || aEmitir.length ? "" : "<p>Nenhuma nota registrada neste mês.</p>") + "</div>" +
    '<div class="fin-botoes"><button data-fin-papel="nota">' + ic("add", 16) + "Registrar nota emitida</button></div>" +
    '<small class="fin-nota">A emissão continua no sistema da prefeitura. Aqui eu só guardo número, valor e data — e mostro o que foi recebido e ainda não tem nota anotada.</small></div>';

  html += '<div class="painel-bloco"><div class="painel-bloco-cabeca"><span>Boletos</span><span class="contagem">' + abertos.length + " na fila</span></div>" +
    '<div class="fin-linhas">' + (boletos.length ? boletos.map((b) => {
      const vencido = b.situacao === "aberto" && b.data && b.data < hoje;
      const classe = vencido ? "fin-acc" : "";
      return '<div class="fin-linha"><span class="duas-linhas"><b>' + esc(b.cliente || b.numero || "sem cliente") + '</b><small class="' + classe + '">' +
        esc(b.situacao === "pago" ? "pago" : (vencido ? "venceu " : "vence ") + b.data_br) + "</small></span>" +
        '<span class="fin-valor">' + esc(semReais(b.valor)) + "</span>" +
        (b.situacao === "aberto" ? '<button data-fin-boleto-pago="' + b.id + '">Baixar</button>' : "") +
        '<button class="botao-icone" data-fin-tirar-papel="' + b.id + '" title="Tirar o registro">' + ic("close", 16) + "</button></div>";
    }).join("") : "<p>Nenhum boleto na fila.</p>") + "</div>" +
    '<div class="fin-botoes"><button data-fin-papel="boleto">' + ic("add", 16) + "Registrar boleto</button>" +
    (abertos.length ? '<button data-fin-cobrar-email="1">' + ic("mail", 16) + "Cobrar por e-mail</button>" : "") + "</div>" +
    '<small class="fin-nota">O boleto sai do seu banco. Eu acompanho o vencimento e aviso — gerar boleto exigiria convênio bancário, que é do banco e não deste programa.</small></div>';

  html += '<div class="painel-bloco"><div class="painel-bloco-cabeca"><span>Comprovantes</span><span class="contagem">' + comprovantes.length + " no mês</span></div>" +
    '<div class="fin-linhas">' +
    semComp.map((x) => '<div class="fin-linha"><span class="duas-linhas"><b>' + esc(x.descricao) + '</b><small class="fin-acc">pago ' +
      esc(dataBR(x.liquidado_em)) + ' · sem comprovante</small></span><span class="fin-valor">' + esc(semReais(x.valor)) +
      '</span><button data-fin-abrir="' + x.id + '">Anexar</button></div>').join("") +
    comprovantes.slice(0, 6).map((k) => '<div class="fin-linha"><span class="duas-linhas"><b>' + esc(k.nome) + "</b><small>" +
      esc(k.descricao + " · " + dataBR(k.liquidado_em)) + '</small></span><button class="botao-icone" data-fin-tirar-comp="' + k.id +
      '" title="Tirar do lançamento">' + ic("close", 16) + "</button></div>").join("") +
    (comprovantes.length || semComp.length ? "" : "<p>Nenhum comprovante guardado neste mês. Cada anexo fica ligado a um lançamento — abra o lançamento e anexe por lá.</p>") +
    "</div></div>";

  if (concluidos.length) {
    html += '<div class="painel-bloco"><div class="painel-bloco-cabeca"><span>Contratos concluídos</span><span class="contagem">' + concluidos.length + ' no mês</span></div><div class="fin-linhas">' +
      concluidos.map((c) => '<div class="fin-linha"><span class="duas-linhas"><b>' + esc(c.nome) + '</b><small>quitado · nada em aberto</small></span>' +
        '<span class="fin-valor fin-ok">' + esc(semReais(c.recebido_texto)) + '</span><button data-fin-arquivar="' + c.id + '">Arquivar a pasta</button></div>').join("") +
      "</div></div>";
  }

  const fechaValor = f.dias_para_fechar
    ? "em " + plural(f.dias_para_fechar, "dia") + " · " + dataCurta(ultimoDiaDoMes(fin.mes))
    : "mês encerrado";
  html += '<div class="painel-chaves">' +
    '<div class="chave-valor"><span>Fechamento</span><b' + (faltas.length ? ' class="acc" title="' + esc(faltas.map((x) => x.titulo).join("; ")) + '"' : "") + ">" +
    esc(fechaValor + (faltas.length ? " · " + plural(faltas.length, "pendência") : "")) + "</b></div>" +
    '<div class="chave-valor"><span>Conciliação bancária</span><b class="mute">em breve</b></div>' +
    '<div class="chave-valor"><span>Permissão</span><b>só você · esta máquina</b></div></div>';
  return html + "</div></aside>";
}

/* O que espera decisao sua, tudo de regra: folha pronta, cobranca atrasada,
   conta vencendo, papel faltando. Cada item aponta uma coisa que existe. */
function pedidosDoMes() {
  const d = fin.dados;
  const folha = d.folha || {};
  const saida = [];
  if (folha.quantos && !folha.lancamento_id) {
    saida.push({ grau: "urgente", titulo: "Folha de " + mesCurto(folha.mes) + " pronta para lançar — " + folha.total_curto,
      detalhe: plural(folha.quantos, "pessoa") + " · vence no último dia do mês",
      acoes: [{ rotulo: "Lançar em contas a pagar", primario: true, fazer: () => pedirFolha("pagar") },
              { rotulo: "Ver detalhamento", fazer: () => { fin.folhaAberta = true; desenharFinanceiro(); } }] });
  } else if (!folha.quantos && (d.candidatos_folha || []).length) {
    saida.push({ grau: "atencao", titulo: "Folha de " + mesCurto(fin.mes) + " ainda não montada",
      detalhe: plural(d.candidatos_folha.length, "pessoa") + " com vínculo definido em Cadastros",
      acoes: [{ rotulo: "Montar a folha", primario: true, fazer: () => pedirFolha("montar") }] });
  }
  (d.precisa || []).forEach((a) => {
    const id = (a.ids || [])[0];
    const acoes = [];
    if (a.acao === "cobrar") acoes.push({ rotulo: "Cobrar", primario: true, fazer: () => prepararCobranca(id) });
    if (a.acao === "pagar") acoes.push({ rotulo: "Registrar pagamento", primario: true, fazer: () => liquidarLancamento(id) });
    if (a.acao === "anexar") acoes.push({ rotulo: "Anexar comprovante", primario: true, fazer: () => abrirLancamento(id) });
    acoes.push({ rotulo: "Ver", fazer: () => abrirLancamento(id) });
    saida.push({ grau: a.grau, titulo: a.titulo, detalhe: a.detalhe, acoes: acoes });
  });
  const aEmitir = d.notas_a_emitir || [];
  if (aEmitir.length) {
    const x = aEmitir[0];
    saida.push({ grau: "atencao", titulo: plural(aEmitir.length, "nota fiscal aguardando registro", "notas fiscais aguardando registro"),
      detalhe: (x.cliente || x.descricao) + " · " + emReais(x.centavos),
      acoes: [{ rotulo: aEmitir.length > 1 ? "Registrar a primeira" : "Registrar", primario: true, fazer: () => fichaPapel("nota", x) },
              { rotulo: "Abrir", fazer: () => abrirLancamento(x.id) }] });
  }
  const hoje = iso(new Date());
  const vencidos = (d.boletos || []).filter((b) => b.situacao === "aberto" && b.data && b.data < hoje);
  if (vencidos.length) {
    saida.push({ grau: "urgente", titulo: plural(vencidos.length, "boleto vencido", "boletos vencidos") + " e ainda em aberto",
      detalhe: vencidos.map((b) => b.cliente || b.numero || "sem nome").slice(0, 3).join(", "),
      acoes: [{ rotulo: "Baixar", primario: true, fazer: () => baixarBoleto(vencidos[0].id) },
              { rotulo: "Cobrar por e-mail", fazer: () => { marcarDestino("caixa"); mostrarEmail(); } }] });
  }
  fin.pedidos = saida;
  return saida;
}

function pedeHtml(p, i) {
  const classe = "fin-pede" + (p.grau === "urgente" ? "" : " atencao");
  return '<div class="' + classe + '"><i></i><span><span class="fin-pede-titulo">' + esc(p.titulo) + "</span>" +
    (p.detalhe ? "<small>" + esc(p.detalhe) + "</small>" : "") +
    '<span class="fin-pede-acoes">' + p.acoes.map((a, j) => {
      const classeBotao = a.primario ? "primario" : "";
      return '<button class="' + classeBotao + '" data-fin-pede="' + i + ":" + j + '">' + esc(a.rotulo) + "</button>";
    }).join("") + "</span></span></div>";
}

/* O parecer e a unica parte que passa pelo modelo, e sempre depois: ele
   recebe os numeros ja somados e escreve sobre eles. Nunca calcula. */
function parecerHtml(destaque) {
  const classe = "fin-parecer" + (destaque ? " solto" : "");
  if (fin.pedindo) {
    return '<div class="' + classe + '"><p>Escrevendo sobre os números do mês — cerca de um minuto nesta máquina.</p></div>';
  }
  if (!fin.parecer) {
    return '<div class="' + classe + '"><p>Eu escrevo sobre os números desta tela — que foram calculados aqui, não por mim. Leva cerca de um minuto nesta máquina e nada sai dela.</p>' +
      (fin.parecerErro ? "<small>" + esc(fin.parecerErro) + "</small>" : "") + "</div>";
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

function painelDaFolha() {
  const f = fin.dados.folha;
  return '<aside class="acervo-painel fin-painel"><div class="rolagem">' +
    '<div class="painel-cabeca"><span class="titulo-painel"><h3>Folha de ' + esc(mesCurto(f.mes)) + '</h3><span class="meta">' +
    esc(f.total_texto + " · " + plural(f.quantos, "pessoa")) + "</span></span>" +
    '<button class="botao-icone" data-fin-voltar="1" title="Voltar">' + ic("close", 18) + "</button></div>" +
    '<div class="fin-linhas fin-painel-lista">' + (f.pessoas || []).map((p) =>
      '<div class="fin-linha"><span class="duas-linhas"><b>' + esc(p.nome) + "</b><small>" +
      esc(p.vinculo_rotulo + " · salário " + semReais(p.salario) + " · encargos " + semReais(p.encargos)) +
      '</small></span><span class="fin-valor">' + esc(semReais(p.total)) + "</span></div>").join("") + "</div>" +
    '<div class="painel-bloco"><p>Estes são os valores gravados neste mês. Mudar o salário no cadastro não reescreve um mês já montado — é por isso que a folha é cópia.</p>' +
    '<div class="fin-botoes"><button data-fin-folha="recibos">' + ic("receipt_long", 16) + "Gerar recibos</button>" +
    (f.lancamento_id ? '<span class="fin-feito">' + ic("check_circle", 16) + "já em contas a pagar</span>"
      : '<button class="primario" data-fin-folha="pagar">' + ic("schedule_send", 16) + "Lançar em contas a pagar</button>") +
    "</div></div></div></aside>";
}

/* Nota fiscal e boleto: a nota sai na prefeitura e o boleto sai do banco.
   Aqui so se guarda o registro - dizer que emite seria mentir. */
function painelDoPapel() {
  const p = fin.papel;
  const eNota = p.tipo === "nota";
  const de = p.de || null;
  return '<aside class="acervo-painel fin-painel"><div class="rolagem">' +
    '<div class="painel-cabeca"><span class="titulo-painel"><h3>' + (eNota ? "Registrar nota emitida" : "Registrar boleto") + '</h3><span class="meta">' +
    (eNota ? "o registro da nota que a prefeitura emitiu" : "o registro do boleto que o banco gerou") + "</span></span>" +
    '<button class="botao-icone" data-fin-voltar="1" title="Fechar">' + ic("close", 18) + "</button></div>" +
    '<div class="ag-form fin-form">' +
    '<div class="ag-campo"><label>' + (eNota ? "Número da nota" : "Número ou identificação") + '</label><input type="text" data-fp="numero" value=""></div>' +
    '<div class="ag-duas"><div class="ag-campo"><label>Valor</label><input type="text" data-fp="valor" placeholder="1.200,00" value="' +
    esc(de ? semReais(emReais(de.centavos)) : "") + '"></div>' +
    '<div class="ag-campo"><label>Data</label><input type="date" data-fp="data" value="' + iso(new Date()) + '"></div></div>' +
    '<div class="ag-campo"><label>Cliente</label><select data-fp="cadastro_id"><option value="">Sem cliente</option>' +
    (fin.dados.clientes || []).map((c) => '<option value="' + c.id + '"' + (de && de.cliente === c.nome ? " selected" : "") + ">" + esc(c.nome) + "</option>").join("") +
    "</select></div>" +
    (de ? '<p class="ag-explica">Ligada ao recebimento “' + esc(de.descricao) + "”.</p>" : "") +
    '<div class="ag-form-rodape"><button data-fin-voltar="1">Cancelar</button><button class="primario" data-fin-papel-salvar="1">Guardar registro</button></div>' +
    "</div></div></aside>";
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
    vazio = "Nenhum lançamento em " + mesCurto(fin.mes) + ". Todo número do Financeiro é soma do que está aqui — lance o primeiro pelo botão acima.";
  } else {
    vazio = "Nenhum lançamento com este filtro.";
  }

  return '<div class="acervo-principal"><div class="tabela-cartao">' +
    '<div class="tabela-barra fin-barra"><div class="visoes">' + chip("todos", "Todos") + chip("receber", "A receber") + chip("pagar", "A pagar") + chip("atrasados", "Atrasados") + "</div>" +
    '<div class="direita">' + seletorDeMes() +
    '<button data-fin-filtros="1">' + ic("filter_list", 16) + (categoria ? esc(categoria) : "Filtros") + "</button>" +
    '<button data-fin-exportar="1">' + ic("download", 16) + "Exportar</button></div></div>" +
    '<div class="tabela-cabecalho colunas-lancamentos"><span>Data</span><span>Quem · descrição</span><span>Categoria</span>' +
    '<span class="fin-num">Valor</span><span>Status</span><span class="fin-num">Ação</span></div>' +
    '<div class="tabela-corpo">' + (lista.length ? lista.map(linhaDeLancamento).join("") : '<p class="rel-vazio">' + esc(vazio) + "</p>") + "</div>" +
    '<div class="tabela-rodape"><span>' + lista.length + " de " + total + '</span><span class="fin-somas">' +
    '<span>Entradas <b class="ok">+ ' + esc(semReais(emReais(entradas))) + "</b></span>" +
    "<span>Saídas <b>− " + esc(semReais(emReais(saidas))) + "</b></span></span></div>" +
    "</div></div>";
}

function linhaDeLancamento(l) {
  const aberta = fin.aberto && fin.aberto.id === l.id;
  const classe = "tabela-linha colunas-lancamentos" + (aberta ? " aberta" : "");
  const quem = l.cadastro_nome
    ? "<b>" + esc(l.cadastro_nome) + "</b><small>" + esc(l.descricao) + "</small>"
    : "<b>" + esc(l.descricao) + "</b><small>" + esc(l.categoria_rotulo + (l.comprovantes ? " · " + plural(l.comprovantes, "comprovante") : "")) + "</small>";
  const classeValor = "fin-valor fin-valor-col" + (l.tipo === "recebimento" ? " ok" : "");
  const status = statusDoLancamento(l);
  const classeStatus = "fin-status " + status.classe;
  let acoes;
  if (l.aberto && l.tipo === "recebimento" && l.atrasado) {
    acoes = '<button class="primario" data-fin-cobrar="' + l.id + '">Cobrar</button><button data-fin-liquidar="' + l.id + '">Registrar pgto</button>';
  } else if (l.aberto && l.tipo === "despesa" && status.classe === "vence") {
    acoes = '<button class="primario" data-fin-liquidar="' + l.id + '">Pagar</button>';
  } else if (l.aberto) {
    acoes = '<button data-fin-abrir="' + l.id + '">Ver</button>';
  } else {
    acoes = '<button data-fin-abrir="' + l.id + '">' + (l.comprovantes ? "Comprovante" : "Ver") + "</button>";
  }
  return '<div class="' + classe + '" data-fin-abrir="' + l.id + '">' +
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

function painelDosLancamentos() {
  if (fin.form) return painelDoFormulario();
  if (fin.aberto) return painelDoLancamento(fin.aberto);
  return '<aside class="acervo-painel fin-painel"><div class="rolagem"><div class="painel-vazio"><h3>Nenhum lançamento aberto</h3>' +
    "<p>Clique numa linha para ver o detalhe, cobrar, registrar o pagamento ou anexar o comprovante.</p>" +
    '<div class="fin-botoes"><button class="primario" data-fin-novo="1">' + ic("add", 16) + "Novo lançamento</button></div></div></div></aside>";
}

function painelDoLancamento(l) {
  const receb = l.tipo === "recebimento";
  const nome = l.cadastro_nome || l.descricao;
  const mesmos = fin.todos.filter((x) => l.cadastro_id && x.cadastro_id === l.cadastro_id && x.id !== l.id).slice(0, 6);
  const comps = (fin.dados.comprovantes || []).filter((k) => k.lancamento_id === l.id);

  let acoes = "";
  if (l.aberto && receb) {
    acoes += '<span class="fin-dividido"><span>Cobrar</span><button data-fin-cobrar="' + l.id + '">' + ic("mail", 16) + "E-mail</button>" +
      '<button class="adiante" data-fin-whats="1">' + ic("chat", 16) + "WhatsApp</button></span>";
  }
  if (l.aberto) acoes += '<button data-fin-liquidar="' + l.id + '">' + ic("check", 16) + (receb ? "Registrar recebimento" : "Registrar pagamento") + "</button>";
  if (l.aberto && receb) acoes += '<button data-fin-renegociar="' + l.id + '">' + ic("handshake", 16) + "Renegociar</button>";
  if (!l.aberto) acoes += '<button data-fin-reabrir="' + l.id + '">' + ic("undo", 16) + "Reabrir</button>";
  acoes += '<button data-fin-editar="' + l.id + '">' + ic("edit", 16) + "Editar</button>";

  const historico = [];
  if (l.criado_em) historico.push("Lançado · " + quandoCurto(l.criado_em));
  if (l.liquidado_em) historico.push((receb ? "Recebido" : "Pago") + " · " + dataBR(l.liquidado_em));
  comps.forEach((k) => historico.push("Comprovante " + k.nome + " · " + quandoCurto(k.criado_em)));
  if (l.atrasado) historico.push("Venceu em " + dataBR(l.vencimento) + " · " + plural(l.dias_atraso, "dia") + " de atraso");

  let abaixoDoValor = "";
  if (l.atrasado) abaixoDoValor = '<small class="fin-acc">' + esc(plural(l.dias_atraso, "dia")) + " de atraso</small>";
  else if (!l.aberto) abaixoDoValor = '<small class="fin-ok">' + (receb ? "recebido" : "pago") + " em " + esc(dataBR(l.liquidado_em)) + "</small>";

  return '<aside class="acervo-painel fin-painel"><div class="rolagem">' +
    '<div class="painel-cabeca"><span class="titulo-painel"><h3>' + esc(nome) + '</h3><span class="meta">' + esc(l.categoria_rotulo + " · " + situacaoCurta(l)) + "</span></span>" +
    '<button class="botao-icone" data-fin-fechar="1" title="Fechar">' + ic("close", 18) + "</button></div>" +
    '<div class="fin-detalhe"><div class="fin-valor-grande"><span>' + esc(l.valor) + "</span>" + abaixoDoValor + "</div>" +
    '<div class="fin-botoes">' + acoes + "</div>" +
    '<small class="fin-nota">' + (l.aberto && receb
      ? "Cobrar por e-mail passa por Aprovações antes de sair. WhatsApp ainda não está ligado."
      : "Registrar aqui não movimenta banco nenhum: é o seu controle, na sua máquina.") + "</small></div>" +
    '<div class="painel-chaves">' +
    '<div class="chave-valor"><span>Vencimento</span><b>' + esc(l.vencimento ? dataExtensa(l.vencimento) : "sem vencimento") + "</b></div>" +
    (l.liquidado_em ? '<div class="chave-valor"><span>' + (receb ? "Recebido em" : "Pago em") + "</span><b>" + esc(dataExtensa(l.liquidado_em)) + "</b></div>" : "") +
    '<div class="chave-valor"><span>Categoria</span><b>' + esc(l.categoria_rotulo) + "</b></div>" +
    '<div class="chave-valor"><span>Cliente</span>' + (l.cadastro_nome
      ? '<button class="em-ligacao forte" data-fin-cadastro="1">' + esc(l.cadastro_nome) + " · cadastro</button>"
      : '<b class="mute">nenhum</b>') + "</div>" +
    (l.cadastro_nome ? '<div class="chave-valor"><span>Documentos</span><button class="em-ligacao forte" data-fin-acervo="1">ver no Acervo</button></div>' : "") +
    (l.observacao ? '<div class="chave-valor"><span>Observação</span><b>' + esc(l.observacao) + "</b></div>" : "") +
    "</div>" +
    '<div class="painel-bloco"><div class="painel-bloco-cabeca"><span>Comprovantes</span><span class="contagem">' + (l.comprovantes || 0) + "</span></div>" +
    (comps.length
      ? '<div class="fin-linhas">' + comps.map((k) => '<div class="fin-linha"><span class="duas-linhas"><b>' + esc(k.nome) + "</b><small>" + esc(quandoCurto(k.criado_em)) +
        '</small></span><button class="botao-icone" data-fin-tirar-comp="' + k.id + '" title="Tirar do lançamento">' + ic("close", 16) + "</button></div>").join("") + "</div>"
      : (l.comprovantes ? "<p>" + esc(plural(l.comprovantes, "comprovante guardado", "comprovantes guardados")) + " (de outro mês).</p>" : "")) +
    '<div class="fin-solta" data-fin-solta="1">Arraste o comprovante aqui<button data-fin-anexar="1">' + ic("attach_file", 16) + "Anexar comprovante</button></div>" +
    '<input type="file" id="fin-arquivo" hidden multiple></div>' +
    '<div class="painel-bloco"><div class="painel-bloco-cabeca"><span>Histórico</span></div><div class="fin-historico">' +
    historico.map((h) => "<span>" + esc(h) + "</span>").join("") + "</div></div>" +
    (mesmos.length
      ? '<div class="painel-bloco"><div class="painel-bloco-cabeca"><span>Do mesmo cliente</span><span class="contagem">' + mesmos.length + '</span></div><div class="fin-linhas">' +
        mesmos.map(itemCurtoDeLancamento).join("") + "</div></div>"
      : "") +
    "</div></aside>";
}

function painelDoFormulario() {
  const v = fin.form;
  const d = fin.dados;
  const chips = [["recebimento", "Recebimento"], ["despesa", "Despesa"]].map(([t, r]) => {
    const classe = t === v.tipo ? "on" : "";
    return '<button class="' + classe + '" data-fin-tipo="' + t + '">' + r + "</button>";
  }).join("");
  let meta;
  if (v.renegociando) meta = "renegociar é mudar vencimento ou valor — o histórico fica no lançamento";
  else if (v.id) meta = esc(v.descricao);
  else meta = "entra na soma assim que for salvo";
  return '<aside class="acervo-painel fin-painel"><div class="rolagem">' +
    '<div class="painel-cabeca"><span class="titulo-painel"><h3>' + (v.id ? "Editar lançamento" : "Novo lançamento") + '</h3><span class="meta">' + meta + "</span></span>" +
    '<button class="botao-icone" data-fin-fechar="1" title="Fechar">' + ic("close", 18) + "</button></div>" +
    '<div class="ag-form fin-form"><div class="ag-chips">' + chips + "</div>" +
    '<div class="ag-campo"><label>Descrição</label><input type="text" data-fc="descricao" value="' + esc(v.descricao || "") + '" placeholder="do que se trata"></div>' +
    '<div class="ag-duas"><div class="ag-campo"><label>Valor</label><input type="text" data-fc="valor" value="' + esc(v.valor || "") + '" placeholder="12.000,00"></div>' +
    '<div class="ag-campo"><label>Categoria</label><select data-fc="categoria">' +
    d.opcoes_categoria.map((c) => '<option value="' + esc(c.valor) + '"' + (c.valor === v.categoria ? " selected" : "") + ">" + esc(c.rotulo) + "</option>").join("") +
    "</select></div></div>" +
    '<div class="ag-campo"><label>Cliente</label><select data-fc="cadastro_id"><option value="">ninguém do cadastro</option>' +
    d.clientes.map((c) => '<option value="' + c.id + '"' + (c.id === Number(v.cadastro_id) ? " selected" : "") + ">" + esc(c.nome) + "</option>").join("") +
    "</select></div>" +
    '<div class="ag-duas"><div class="ag-campo"><label>Vencimento</label><input type="date" data-fc="vencimento" value="' + esc(v.vencimento || "") + '"' +
    (v.renegociando ? " autofocus" : "") + "></div>" +
    '<div class="ag-campo"><label>Já ' + (v.tipo === "recebimento" ? "recebido" : "pago") + ' em</label><input type="date" data-fc="liquidado_em" value="' + esc(v.liquidado_em || "") + '"></div></div>' +
    '<div class="ag-form-rodape">' + (v.id ? '<button class="perigo" data-fin-apagar="1">Apagar</button>' : "") +
    '<button data-fin-fechar="1">Cancelar</button><button class="primario" data-fin-salvar="1">Salvar</button></div></div></div></aside>';
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
  return '<div class="acervo-principal fin-rel"><div class="visoes fin-rel-abas">' +
    aba("dia", "Tarefas do dia") + aba("financeiro", "Financeiro") + aba("acoes", "Ações de IA aprovadas") + "</div>" +
    '<div class="fin-grade2">' + cartoes + "</div></div>";
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
    linha("Entradas", "+ " + semReais(emReais(m.entradas || 0)), "fin-ok") +
    linha("Saídas", "− " + semReais(emReais(m.saidas || 0))) +
    linha("Resultado", (resultado >= 0 ? "+ " : "− ") + semReais(emReais(Math.abs(resultado))), resultado >= 0 ? "fin-ok" : "fin-acc") +
    linha("A receber em aberto", semReais(p.a_receber_texto)) +
    linha("A pagar em aberto", semReais(p.a_pagar_texto)) +
    linha("Em atraso", semReais(p.atrasado_texto), p.atrasado > 0 ? "fin-acc" : "") + "</div>" +
    (m.comparacao && m.comparacao.tem_base
      ? '<p class="rel-explica">Contra ' + esc(m.comparacao.mes_anterior) + ": entradas " + esc(m.comparacao.entradas.texto) + ", saídas " + esc(m.comparacao.saidas.texto) + ".</p>"
      : '<p class="rel-explica">Sem lançamento em ' + esc(m.comparacao ? m.comparacao.mes_anterior : "mês anterior") + ", não dá para comparar com o mês anterior.</p>") +
    '<p class="rel-explica">' + (prazo.tem
      ? "Prazo médio de recebimento: " + esc(String(prazo.dias).replace(".", ",")) + " dias, sobre " + esc(plural(prazo.quantos, "recebimento")) + "."
      : "Prazo médio: " + esc(prazo.porque || "sem base ainda") + ".") + "</p>" +
    '<div class="rel-espaco"></div>' +
    '<div class="fin-rodape-botoes"><button data-fin-pdf="1">' + ic("picture_as_pdf", 16) + "Baixar PDF</button>" +
    '<button data-fin-exportar="1">' + ic("table", 16) + "Baixar XLSX</button>" +
    '<button class="primario" data-fin-enviar="1">' + ic("mail", 16) + "Enviar por e-mail</button></div></div>";

  const categorias = '<div class="fin-cartao"><div class="fin-cartao-cabeca"><span>Por categoria</span><small>' + esc(mesCurto(fin.mes)) + "</small></div>" +
    (cats.length
      ? '<div class="rel-categorias">' + cats.map((c, i) => {
        const classe = "rel-categoria c" + Math.min(i + 1, 4);
        return '<div class="' + classe + '"><div><span>' + esc(c.rotulo + (c.tipo === "recebimento" ? " · entrada" : "")) + "</span><b>" +
          esc(semReais(c.total_texto)) + '</b></div><div class="rel-trilho"><i style="width:' + Math.max(2, Math.round(c.total * 100 / teto)) + '%"></i></div></div>';
      }).join("") + "</div>"
      : '<p class="rel-vazio">Nenhum lançamento liquidado em ' + esc(mesCurto(fin.mes)) + ". As barras saem do que foi efetivamente recebido ou pago.</p>") +
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
      ? '<p class="rel-explica">Tempo no escritório não aparece porque o acompanhamento de bem-estar está desligado. Prefiro não mostrar a estimar.' +
        '<button class="em-ligacao forte" data-fin-foco="1">Ligar em Foco e bem-estar</button></p>'
      : "") + "</div>";
  return tarefas + numeros;
}

function cartaoDasAcoes(m) {
  const acoes = m.acoes || [];
  return '<div class="fin-cartao larga"><div class="fin-cartao-cabeca"><span>Ações de IA aprovadas</span><small>' + esc(mesCurto(fin.mes)) + " · " + acoes.length + "</small></div>" +
    '<p class="rel-explica rel-topo">Cada linha é um pedido que passou pela fila de Aprovações e guardou o resultado. É o registro que torna a fila conferível depois.</p>' +
    (acoes.length
      ? '<div class="rel-acoes">' + acoes.map((a) => {
        const classe = "ic ic-18" + (a.estado === "aprovado" ? "" : " nao");
        return '<div class="rel-acao"><span class="fin-data">' + esc(dataCurta(a.dia) + " " + a.hora) + '</span><span class="' + classe + '">' +
          (a.estado === "aprovado" ? "check_circle" : "close") + '</span><span class="duas-linhas"><b>' + esc(a.titulo) + "</b><small>" +
          esc(a.categoria_rotulo + " · " + (a.resultado || a.estado)) + "</small></span></div>";
      }).join("") + "</div>"
      : '<p class="rel-vazio">Nada foi aprovado em ' + esc(mesCurto(fin.mes)) + ". Quando você aprovar um pedido na fila, ele aparece aqui com o resultado.</p>") +
    "</div>";
}

function painelDosRelatorios() {
  const m = fin.rel.mes;
  const sugestoes = sugestoesDoMes();
  const todas = m.acoes || [];
  const acoes = todas.slice(0, 5);
  return '<aside class="acervo-painel fin-painel"><div class="rolagem">' +
    '<div class="fin-bloco-cabeca fin-painel-topo">' + (fin.pedindo ? coroa(18) : "") + "<span>Parecer sobre o mês</span><small>gerado na sua máquina</small></div>" +
    parecerHtml(true) +
    (fin.parecer || fin.pedindo ? "" : '<div class="fin-botoes fin-painel-botoes"><button class="primario" data-fin-parecer="1">' + ic("insights", 16) + "Pedir o parecer</button></div>") +
    '<div class="painel-bloco"><div class="painel-bloco-cabeca"><span>Sugestões</span><span class="contagem">' + (sugestoes.length ? "saem de regra, não de opinião" : "") + "</span></div>" +
    (sugestoes.length
      ? '<div class="fin-sugestoes">' + sugestoes.map((s) => '<div class="fin-sugestao"><i></i><span>' + esc(s.texto) + "</span></div>").join("") + "</div>"
      : "<p>Nada a sugerir: nenhuma cobrança atrasada, nenhuma conta vencendo nesta semana e nenhum papel faltando.</p>") +
    '<div class="fin-sug-rodape"><button class="em-ligacao" data-fin-inutil="1">Não foi útil</button>' +
    '<button class="primario" data-fin-criar-tarefas="1"' + (sugestoes.length ? "" : " disabled") + ">" + ic("add_task", 16) + "Criar tarefas</button></div></div>" +
    '<div class="painel-bloco"><div class="painel-bloco-cabeca"><span>Ações de IA aprovadas</span><span class="contagem">' + esc(mesCurto(fin.mes)) + " · " + todas.length + "</span></div>" +
    (acoes.length
      ? '<div class="fin-linhas">' + acoes.map((a) => {
        const classe = "ic ic-18" + (a.estado === "aprovado" ? "" : " nao");
        return '<div class="fin-acao"><span class="' + classe + '">' + (a.estado === "aprovado" ? "check_circle" : "close") +
          '</span><span class="duas-linhas"><b>' + esc(a.titulo) + "</b><small>" +
          esc((a.estado === "aprovado" ? "aprovada" : "recusada") + " por você · " + dataCurta(a.dia)) + "</small></span></div>";
      }).join("") + "</div>"
      : "<p>Nenhuma ação passou pela fila neste mês.</p>") + "</div>" +
    "</div></aside>";
}

/* As sugestoes saem de regra, nao de opiniao: atraso, vencimento, papel que
   falta. Sao as mesmas coisas de "Precisa de voce", ditas como proximo passo. */
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

function ligarFinanceiro() {
  const cada = (seletor, fn) => document.querySelectorAll(seletor).forEach(fn);
  const clique = (seletor, fn) => cada(seletor, (b) => { b.onclick = (e) => { e.stopPropagation(); fn(b, e); }; });

  clique("[data-fin-visao]", (b) => { fin.visao = b.dataset.finVisao; fin.form = null; fin.papel = null; fin.folhaAberta = false; mostrarFinanceiro(); });
  const seletor = $("fin-mes");
  if (seletor) seletor.onchange = () => { fin.mes = seletor.value; fin.aberto = null; fin.form = null; mostrarFinanceiro(); };
  clique("[data-fin-novo]", () => novoLancamento());
  clique("[data-fin-exportar]", () => { window.location.href = "/api/financeiro/exportar?mes=" + encodeURIComponent(fin.mes); });
  clique("[data-fin-importar]", () => avisoCert("Importar extrato do banco ainda não existe — cada banco exporta num formato próprio; por enquanto lance à mão ou peça ao Assistente"));
  clique("[data-fin-pdf]", baixarRelatorio);
  clique("[data-fin-enviar]", enviarRelatorioPorEmail);
  clique("[data-fin-parecer]", pedirParecer);
  clique("[data-fin-numeros]", () => { fin.numerosAbertos = !fin.numerosAbertos; desenharFinanceiro(); });
  clique("[data-fin-ver-lancamentos]", (b) => { fin.filtro = b.dataset.finVerLancamentos || "todos"; fin.visao = "lancamentos"; mostrarFinanceiro(); });
  clique("[data-fin-filtro]", (b) => { fin.filtro = b.dataset.finFiltro; desenharFinanceiro(); });
  clique("[data-fin-filtros]", (b) => {
    menuNaLinha(b, [{ rotulo: "Todas as categorias", acao: () => { fin.categoria = ""; desenharFinanceiro(); } }, "-"].concat(
      fin.dados.opcoes_categoria.map((c) => ({ rotulo: c.rotulo, acao: () => { fin.categoria = c.valor; desenharFinanceiro(); } }))));
  });
  clique("[data-fin-abrir]", (b) => abrirLancamento(Number(b.dataset.finAbrir)));
  clique("[data-fin-fechar]", () => { fin.aberto = null; fin.form = null; desenharFinanceiro(); });
  clique("[data-fin-voltar]", () => { fin.folhaAberta = false; fin.papel = null; desenharFinanceiro(); });
  clique("[data-fin-cobrar]", (b) => prepararCobranca(Number(b.dataset.finCobrar)));
  clique("[data-fin-whats]", () => avisoCert("Cobrar por WhatsApp ainda não está ligado — por enquanto a cobrança sai por e-mail"));
  clique("[data-fin-liquidar]", (b) => liquidarLancamento(Number(b.dataset.finLiquidar)));
  clique("[data-fin-reabrir]", (b) => reabrirLancamento(Number(b.dataset.finReabrir)));
  clique("[data-fin-editar]", (b) => editarLancamento(Number(b.dataset.finEditar), false));
  clique("[data-fin-renegociar]", (b) => editarLancamento(Number(b.dataset.finRenegociar), true));
  clique("[data-fin-cadastro], [data-fin-cadastros]", () => { marcarDestino("cadastros"); mostrarCadastros(); });
  clique("[data-fin-acervo]", () => verNoAcervo(fin.aberto ? fin.aberto.cadastro_nome : ""));
  clique("[data-fin-foco]", () => { marcarDestino("foco"); mostrarFoco(); });
  clique("[data-fin-rel-aba]", (b) => { fin.relAba = b.dataset.finRelAba; desenharFinanceiro(); });
  clique("[data-fin-inutil]", () => {
    if (fin.parecer) {
      fin.parecer = null;
      desenharFinanceiro();
      avisoCert("parecer descartado — peça outro quando quiser; as sugestões continuam, porque saem de regra e não do parecer");
    } else {
      avisoCert("as sugestões saem de regra (atraso, vencimento, papel faltando) — ainda não há motor para aprender com o seu não");
    }
  });
  clique("[data-fin-criar-tarefas]", criarTarefasDasSugestoes);
  clique("[data-fin-pede]", (b) => {
    const [i, j] = b.dataset.finPede.split(":").map(Number);
    const p = (fin.pedidos || [])[i];
    if (p && p.acoes[j]) p.acoes[j].fazer();
  });
  clique("[data-fin-folha]", (b) => {
    const a = b.dataset.finFolha;
    if (a === "ver") { fin.folhaAberta = true; desenharFinanceiro(); } else if (a === "recibos") gerarRecibos(); else pedirFolha(a);
  });
  clique("[data-fin-papel]", (b) => fichaPapel(b.dataset.finPapel, null));
  clique("[data-fin-nota-de]", (b) => {
    const x = (fin.dados.notas_a_emitir || []).find((n) => n.id === Number(b.dataset.finNotaDe));
    fichaPapel("nota", x || null);
  });
  clique("[data-fin-papel-salvar]", salvarPapel);
  clique("[data-fin-tirar-papel]", async (b) => {
    if (!(await confirmar({ titulo: "Tirar este registro?", contexto: "Financeiro", texto: "O papel de verdade continua onde está; só o registro sai daqui.", confirmar: "Tirar", perigo: true }))) return;
    await fetch("/api/financeiro/papeis/" + b.dataset.finTirarPapel, { method: "DELETE" });
    mostrarFinanceiro();
  });
  clique("[data-fin-boleto-pago]", (b) => baixarBoleto(Number(b.dataset.finBoletoPago)));
  clique("[data-fin-cobrar-email]", () => { marcarDestino("caixa"); mostrarEmail(); });
  clique("[data-fin-tirar-comp]", async (b) => {
    if (!(await confirmar({ titulo: "Tirar este comprovante?", contexto: "Financeiro › Lançamentos", texto: "Ele deixa de estar ligado ao lançamento. O arquivo continua na pasta.", confirmar: "Tirar", perigo: true }))) return;
    await fetch("/api/financeiro/comprovantes/" + b.dataset.finTirarComp, { method: "DELETE" });
    mostrarFinanceiro();
  });
  clique("[data-fin-arquivar]", (b) => arquivarCliente(Number(b.dataset.finArquivar)));

  // o formulario guarda o que foi digitado no estado, para o redesenho
  // (trocar recebimento por despesa) nao apagar os campos
  clique("[data-fin-tipo]", (b) => { fin.form.tipo = b.dataset.finTipo; desenharFinanceiro(); });
  cada("[data-fc]", (el) => { el.oninput = () => { fin.form[el.dataset.fc] = el.value; }; el.onchange = el.oninput; });
  clique("[data-fin-salvar]", salvarLancamento);
  clique("[data-fin-apagar]", apagarLancamento);

  const arquivo = $("fin-arquivo");
  const solta = document.querySelector("[data-fin-solta]");
  if (arquivo && solta) {
    clique("[data-fin-anexar]", () => arquivo.click());
    arquivo.onchange = () => { if (arquivo.files.length) anexarComprovantes([...arquivo.files]); };
    solta.ondragover = (e) => { e.preventDefault(); solta.classList.add("sobre"); };
    solta.ondragleave = () => solta.classList.remove("sobre");
    solta.ondrop = (e) => {
      e.preventDefault();
      solta.classList.remove("sobre");
      if (e.dataTransfer.files.length) anexarComprovantes([...e.dataTransfer.files]);
    };
  }
}

function abrirLancamento(id) {
  const l = fin.todos.find((x) => x.id === id);
  if (!l) return;
  fin.aberto = l;
  fin.form = null;
  fin.folhaAberta = false;
  fin.papel = null;
  const mes = mesDoLancamento(l);
  const foraDoMes = mes && mes !== fin.mes && fin.filtro !== "atrasados";
  if (fin.visao !== "lancamentos" || foraDoMes) {
    fin.visao = "lancamentos";
    if (foraDoMes) {
      if (l.atrasado) fin.filtro = "atrasados";
      else fin.mes = mes;
    }
    mostrarFinanceiro();
    return;
  }
  desenharFinanceiro();
}

function novoLancamento() {
  fin.form = { tipo: "despesa", descricao: "", valor: "", categoria: "outros", cadastro_id: null, vencimento: iso(new Date()), liquidado_em: "" };
  fin.aberto = null;
  if (fin.visao !== "lancamentos") { fin.visao = "lancamentos"; mostrarFinanceiro(); return; }
  desenharFinanceiro();
  const campo = document.querySelector('[data-fc="descricao"]');
  if (campo) campo.focus();
}

function editarLancamento(id, renegociando) {
  const l = fin.todos.find((x) => x.id === id);
  if (!l) return;
  fin.form = {
    id: l.id, tipo: l.tipo, descricao: l.descricao, valor: semReais(l.valor), categoria: l.categoria,
    cadastro_id: l.cadastro_id, vencimento: l.vencimento || "", liquidado_em: l.liquidado_em || "", renegociando: !!renegociando,
  };
  desenharFinanceiro();
}

async function salvarLancamento() {
  const v = fin.form;
  const r = await fetch("/api/financeiro/lancamentos", {
    method: "POST", headers: FIN_JSON,
    body: JSON.stringify({ id: v.id || null, dados: {
      tipo: v.tipo, descricao: v.descricao, valor: v.valor, categoria: v.categoria,
      cadastro_id: Number(v.cadastro_id) || null, vencimento: v.vencimento, liquidado_em: v.liquidado_em,
    } }),
  });
  if (!r.ok) { avisoCert(await erroDe(r)); return; }
  const salvo = await r.json();
  fin.form = null;
  fin.aberto = salvo && salvo.id ? { id: salvo.id } : null;
  const mes = salvo && salvo.id ? mesDoLancamento(salvo) : "";
  if (mes && mes !== fin.mes) fin.mes = mes;
  avisoCert(v.id ? "lançamento atualizado" : "lançamento salvo — já entra na soma");
  mostrarFinanceiro();
}

async function apagarLancamento() {
  const v = fin.form;
  if (!v || !v.id) return;
  if (!(await confirmar({ titulo: "Apagar este lançamento?", contexto: "Financeiro › Lançamentos", texto: "Os comprovantes ligados a ele vão junto. " + LIXEIRA_TEXTO, confirmar: "Apagar", perigo: true }))) return;
  const r = await fetch("/api/financeiro/lancamentos/" + v.id, { method: "DELETE" });
  fin.form = null;
  fin.aberto = null;
  mostrarFinanceiro();
  avisarLixeira(r, () => mostrarFinanceiro());
}

async function liquidarLancamento(id) {
  const l = fin.todos.find((x) => x.id === id);
  const r = await fetch("/api/financeiro/lancamentos/" + id + "/liquidar", { method: "POST", headers: FIN_JSON, body: "{}" });
  if (!r.ok) { avisoCert(await erroDe(r)); return; }
  const receb = l && l.tipo === "recebimento";
  avisoCert((receb ? "recebimento" : "pagamento") + " registrado hoje" + (receb ? "" : " — anexe o comprovante no painel do lançamento"));
  if (fin.visao === "lancamentos") fin.aberto = { id: id };
  mostrarFinanceiro();
}

async function reabrirLancamento(id) {
  const r = await fetch("/api/financeiro/lancamentos/" + id + "/reabrir", { method: "POST", headers: FIN_JSON, body: "{}" });
  if (!r.ok) { avisoCert(await erroDe(r)); return; }
  avisoCert("lançamento reaberto — volta para as listas de aberto");
  mostrarFinanceiro();
}

async function anexarComprovantes(arquivos) {
  const l = fin.aberto;
  if (!l) return;
  for (const arquivo of arquivos) {
    const forma = new FormData();
    forma.append("arquivo", arquivo);
    const r = await fetch("/api/financeiro/lancamentos/" + l.id + "/comprovante", { method: "POST", body: forma });
    if (!r.ok) { avisoCert(await erroDe(r)); return; }
  }
  avisoCert(plural(arquivos.length, "comprovante ligado", "comprovantes ligados") + " a “" + l.descricao + "”");
  mostrarFinanceiro();
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

async function pedirFolha(acao) {
  avisoCert(acao === "montar" ? "montando a folha…" : "lançando…");
  const r = await fetch("/api/financeiro/folha/" + acao, { method: "POST", headers: FIN_JSON, body: JSON.stringify({ mes: fin.mes || "" }) });
  if (!r.ok) { avisoCert(await erroDe(r)); return; }
  await mostrarFinanceiro();
  avisoCert(acao === "montar" ? "folha montada" : "folha lançada em contas a pagar — vence no último dia do mês");
}

async function gerarRecibos() {
  avisoCert("gerando os recibos…");
  const r = await fetch("/api/financeiro/folha/recibos", { method: "POST", headers: FIN_JSON, body: JSON.stringify({ mes: fin.mes || "" }) });
  if (!r.ok) { avisoCert(await erroDe(r)); return; }
  const d = await r.json();
  avisoCert(plural(d.recibos.length, "recibo") + " em " + d.pasta);
  fetch("/api/biblioteca/abrir-pasta", { method: "POST", headers: FIN_JSON, body: JSON.stringify({ caminho: d.pasta }) });
}

function fichaPapel(tipo, de) {
  fin.papel = { tipo: tipo, de: de || null };
  fin.folhaAberta = false;
  if (fin.visao !== "geral") { fin.visao = "geral"; mostrarFinanceiro(); return; }
  desenharFinanceiro();
}

async function salvarPapel() {
  const p = fin.papel;
  const raiz = $("financeiro");
  const campo = (n) => { const el = raiz.querySelector('[data-fp="' + n + '"]'); return el ? el.value : ""; };
  const r = await fetch("/api/financeiro/papeis", {
    method: "POST", headers: FIN_JSON,
    body: JSON.stringify({ id: null, dados: {
      tipo: p.tipo, numero: campo("numero").trim(), centavos: centavosDe(campo("valor")),
      cadastro_id: Number(campo("cadastro_id")) || null, lancamento_id: p.de ? p.de.id : null, data: campo("data"),
    } }),
  });
  if (!r.ok) { avisoCert(await erroDe(r)); return; }
  fin.papel = null;
  avisoCert(p.tipo === "nota" ? "nota registrada" : "boleto registrado");
  mostrarFinanceiro();
}

async function baixarBoleto(id) {
  const r = await fetch("/api/financeiro/papeis/" + id + "/pago", { method: "POST", headers: FIN_JSON, body: "{}" });
  if (!r.ok) { avisoCert(await erroDe(r)); return; }
  avisoCert("boleto baixado");
  mostrarFinanceiro();
}

/* Arquivar a pasta de um cliente encerrado e mover os documentos dele - e
   mover e efeito externo, entao vai pela fila como todo o resto. */
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

