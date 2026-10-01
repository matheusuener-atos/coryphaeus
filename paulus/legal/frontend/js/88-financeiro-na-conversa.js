/* ---------------------------- o financeiro e o relatorio pela conversa (T4) */
/*
   Pacote de telas de 01/10/2026: `Conversa - Financeiro` e `Conversa -
   Relatorio` (src/financeiro_pela_conversa.py).

   "Como está o financeiro do mês?": na conversa, os cinco numeros do mes, o
   fluxo de caixa dos ultimos seis meses e o que esta a receber e a pagar.
   Na coluna (420 px): o que precisa de voce, o parecer do mes (o unico texto
   do modelo, escrito sobre os numeros ja somados), os papeis do mes e as
   sugestoes (a mesma regra da tela Financeiro, sugestoesDoMes).

   "Gera o relatório financeiro de outubro": o extrato e as categorias na
   conversa, com o PDF e a planilha ja gerados no Acervo; na coluna, o
   periodo, o parecer, o envio por e-mail (pela rota de sempre, com o sim e,
   com Limites da IA, por Aprovacoes) e as sugestoes.
*/

const fnc = { d: null, caixa: null, dados: null, rel: null, mes: "", comparar: "", parecer: null, para: [], podeSozinho: false };
const FNC_MESES = ["janeiro", "fevereiro", "março", "abril", "maio", "junho", "julho", "agosto", "setembro", "outubro", "novembro", "dezembro"];

function fncMes(chave) {
  return FNC_MESES[Number(String(chave).slice(5, 7)) - 1] || "";
}

function fncMil(centavos) {
  return "R$ " + Math.round((Number(centavos) || 0) / 100).toLocaleString("pt-BR");
}

function fncReais(centavos) {
  return (Math.abs(Number(centavos) || 0) / 100).toLocaleString("pt-BR", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}

function cartaoDoFinanceiro() {
  return '<div class="fcn-cartao" data-fnc-cartao="1"><div class="emc-carregando">' + esqueleto("lista") + "</div></div>";
}

function ligarFinanceiroNaProposta(caixa, d) {
  const alvo = caixa.querySelector("[data-fnc-cartao]");
  if (!alvo) return;
  fnc.d = d;
  fnc.caixa = alvo;
  fnc.mes = (d.campos || {}).mes || new Date().toISOString().slice(0, 7);
  fnc.comparar = (d.campos || {}).comparar || "";
  fnc.parecer = null;
  if (d.tipo === "relatorio") abrirRelatorioNaConversa(Boolean(caixa.dataset.propostaGuardada));
  else abrirFinanceiroNaConversa(Boolean(caixa.dataset.propostaGuardada));
}

/* ------------------------------------------------------- o financeiro */

async function abrirFinanceiroNaConversa(guardado) {
  try {
    fnc.dados = await (await fetch("/api/financeiro?mes=" + fnc.mes)).json();
  } catch (err) {
    fnc.caixa.innerHTML = '<div class="emc-falta">' + ic("error", 16) + "<span>Não consegui ler o Financeiro agora.</span></div>";
    return;
  }
  desenharFinanceiroNaConversa();
  if (!guardado) abrirColunaDoFinanceiro();
}

function kpiDoFinanceiro(rotulo, valor, sub, tom) {
  const classe = "lcn-kpi" + (tom ? " " + tom : "");
  return '<div class="' + classe + '"><span class="emc-kicker">' + esc(rotulo) + "</span><b>" + valor + "</b><small>" + esc(sub) + "</small></div>";
}

function desenharFinanceiroNaConversa() {
  const alvo = fnc.caixa;
  const d = fnc.dados || {};
  const p = d.painel || {};
  const fech = d.fechamento || {};
  const hoje = (d.precisa || []).filter((x) => x.detalhe === "vence hoje").length;
  const kpis = '<div class="lcn-kpis fnc-kpis">' +
    kpiDoFinanceiro("Saldo em caixa", fncMil(p.saldo), (p.resultado_mes >= 0 ? "+ " : "– ") + fncMil(Math.abs(p.resultado_mes || 0)) + " no mês") +
    kpiDoFinanceiro("A receber", fncMil(p.a_receber), plural(p.a_receber_quantos || 0, "cobrança aberta", "cobranças abertas")) +
    kpiDoFinanceiro("A pagar", fncMil(p.a_pagar), plural(p.a_pagar_quantos || 0, "conta")) +
    kpiDoFinanceiro("Em atraso", p.atrasado ? fncMil(p.atrasado) : "nada", p.atrasado ? plural(p.atrasado_quantos || 0, "cobrança vencida", "cobranças vencidas") : "nenhuma cobrança vencida", p.atrasado ? "" : "nada") +
    kpiDoFinanceiro("Fechamento", fech.dias_para_fechar ? "em " + plural(fech.dias_para_fechar, "dia") : "hoje",
      hoje ? plural(hoje, "conta vence hoje", "contas vencem hoje") : (fech.faltas || []).length ? plural(fech.faltas.length, "pendência") + " para fechar" : "nada faltando") +
    "</div>";
  const fluxo = (d.fluxo || []).slice(-6);
  const maior = Math.max(1, ...fluxo.map((m) => Math.max(m.entradas || 0, m.saidas || 0)));
  const barras = '<div class="fnc-fluxo"><div class="fcn-tabela-cabeca"><b>Fluxo de caixa</b><span class="vazio-flex"></span>' +
    '<small>últimos 6 meses</small><span class="fnc-legenda"><i class="entra"></i>Entradas</span><span class="fnc-legenda"><i class="sai"></i>Saídas</span></div>' +
    '<div class="fnc-barras">' + fluxo.map((m) => {
      const agora = m.mes === fnc.mes;
      const classe = "fnc-mes" + (agora ? " agora" : "");
      const he = Math.round((m.entradas || 0) * 100 / maior);
      const hs = Math.round((m.saidas || 0) * 100 / maior);
      return '<div class="' + classe + '" title="' + esc((m.rotulo || "") + ": entradas " + (m.entradas_texto || "") + ", saídas " + (m.saidas_texto || "")) + '">' +
        '<span class="fnc-par"><i class="entra" style="height:' + he + '%"></i><i class="sai" style="height:' + hs + '%"></i></span>' +
        "<small>" + esc(maiuscula(String(m.rotulo || fncMes(m.mes)).slice(0, 3))) + "</small></div>";
    }).join("") + "</div></div>";
  const lista = (titulo, itens, entra) => '<div class="fnc-lista"><div class="fnc-lista-cabeca"><b>' + titulo + "</b><small>" + plural(itens.length, "em aberto", "em aberto") + "</small></div>" +
    itens.slice(0, 3).map((x) => '<div class="fnc-item"><span><b>' + esc(x.cadastro_nome || x.descricao) + "</b><small>" + esc(x.cadastro_nome ? x.descricao : x.categoria_rotulo || "") + "</small></span>" +
      '<span class="fnc-item-valor"><b>' + (entra ? "+ " : "– ") + fncReais(x.centavos) + '</b><small class="' + (x.dias_para_vencer === 0 ? "hoje" : x.atrasado ? "atraso" : "") + '">' +
      esc(x.dias_para_vencer === 0 ? "vence hoje" : x.atrasado ? "atrasado" : x.vencimento ? "vence " + dataCurta(x.vencimento) : "sem data") + "</small></span></div>").join("") + "</div>";
  alvo.innerHTML = '<div class="fcn-tabela">' + kpis + barras +
    '<div class="fnc-listas">' + lista("A receber", d.receber || [], true) + lista("A pagar", d.pagar || [], false) + "</div></div>";
}

/* A coluna do financeiro: o que precisa de voce, o parecer, os papeis e as sugestoes. */
function htmlDaColunaDoFinanceiro() {
  const d = fnc.dados || {};
  const urgente = (d.precisa || []).find((x) => x.acao === "pagar" || x.grau === "urgente");
  const notas = (d.notas || []).length;
  const aEmitir = (d.notas_a_emitir || []).length;
  const boletos = (d.boletos || []).filter((b) => b.situacao === "aberto");
  const comprovantes = (d.comprovantes || []).length;
  const faltam = (d.sem_comprovante || []).length;
  const folha = (d.candidatos_folha || []).reduce((s, x) => s + (Number(x.salario_centavos) || 0), 0);
  const pessoas = (d.candidatos_folha || []).length;
  const tile = (rotulo, valor, sub) => '<div class="fnc-tile"><small>' + esc(rotulo) + "</small><b>" + esc(valor) + "</b><span>" + esc(sub) + "</span></div>";
  return '<div class="fcn fnc-coluna" data-fl-tipo="financeiro"><div class="fcn-corpo">' +
    (urgente
      ? '<div class="fnc-precisa"><div class="fnc-precisa-topo">' + ic("schedule", 16) + "<b>Precisa de você</b><span class=\"vazio-flex\"></span><small>" + plural((d.precisa || []).length, "item", "itens") + "</small></div>" +
        "<b>" + esc(urgente.titulo) + '</b><small class="fnc-precisa-quando">' + esc(urgente.detalhe || "") + "</small>" +
        '<div class="fnc-precisa-acoes">' + (urgente.acao === "pagar" ? '<button type="button" class="primario" data-fnc-pagar="' + esc((urgente.ids || [])[0] || "") + '">' + ic("check", 15) + "Registrar pagamento</button>" : "") +
        '<button type="button" class="emc-botao" data-fnc-ver="1">Ver</button></div></div>'
      : "") +
    htmlDoParecer() +
    '<div class="fnc-secao"><div class="fnc-secao-cabeca"><b>Papéis do mês</b><small>' + esc(fncMes(fnc.mes)) + "</small></div>" +
    '<div class="fnc-tiles">' +
    tile("Notas fiscais", plural(notas, "registrada"), aEmitir ? plural(aEmitir, "recebimento sem nota", "recebimentos sem nota") : "nenhuma faltando") +
    tile("Boletos", boletos.length ? plural(boletos.length, "em aberto", "em aberto") : "nenhum aberto", boletos.slice(0, 2).map((b) => b.observacao || b.cliente || "").filter(Boolean).join(" e ") || "—") +
    tile("Comprovantes", plural(comprovantes, "guardado"), faltam ? plural(faltam, "faltando", "faltando") : "nenhum faltando") +
    tile("Folha", folha ? fncMil(folha) : "sem folha", plural(pessoas, "pessoa")) + "</div></div>" +
    htmlDasSugestoes() + "</div></div>";
}

function htmlDoParecer() {
  const p = fnc.parecer;
  const corpo = !p ? '<p class="em-andamento ativo">' + coroa(14) + "escrevendo nesta máquina…</p>"
    : p.erro ? '<p class="fnc-parecer-erro">Sem parecer agora: ' + esc(p.erro) + "</p>"
      : "<p>" + esc(p.texto) + "</p>";
  return '<div class="fnc-secao"><div class="fnc-secao-cabeca"><b>Parecer do mês</b><small>escrito pelo assistente</small></div>' + corpo +
    '<small class="fnc-nota">os números foram somados aqui; o assistente só escreve sobre eles</small></div>';
}

function htmlDasSugestoes() {
  const sugestoes = typeof sugestoesDoMes === "function" ? sugestoesDoMes(fnc.dados || {}, fnc.mes) : [];
  return '<div class="fnc-secao"><div class="fnc-secao-cabeca"><b>Sugestões</b><small>saem de regra</small></div>' +
    (sugestoes.length
      ? '<ul class="fnc-sugestoes">' + sugestoes.slice(0, 5).map((s) => "<li>" + esc(s.texto) + "</li>").join("") + "</ul>" +
        '<button type="button" class="emc-botao" data-fnc-tarefas="1">' + ic("task_alt", 15) + "Criar tarefas para hoje</button>"
      : '<p class="fnc-nota">Nada a sugerir: nenhuma cobrança atrasada, nenhuma conta vencendo nesta semana e nenhum papel faltando.</p>') + "</div>";
}

function abrirColunaDoFinanceiro() {
  abrirNoLado("formulario", {
    chave: "financeiro",
    html: htmlDaColunaDoFinanceiro(),
    ligar: ligarColunaDoFinanceiro,
    aoFechar: () => { fnc.dados = fnc.rel ? fnc.dados : null; atualizarPostura(); },
  });
  atualizarPostura();
  pedirParecerDoMes();
}

function redesenharColunaDoFinanceiro() {
  const lado = $("lado-ferramenta");
  if (!lado || papelDoLado() !== "formulario") return;
  const tipo = (lado.querySelector("[data-fl-tipo]") || {}).dataset;
  if (!tipo) return;
  lado.innerHTML = tipo.flTipo === "relatorio" ? htmlDaColunaDoRelatorio() : htmlDaColunaDoFinanceiro();
  (tipo.flTipo === "relatorio" ? ligarColunaDoRelatorio : ligarColunaDoFinanceiro)(lado);
}

async function pedirParecerDoMes() {
  const pedido = fnc.mes + "|" + fnc.comparar;
  fnc.parecerDe = pedido;
  const r = await fetch("/api/relatorios/parecer-do-mes", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ mes: fnc.mes, comparar: fnc.comparar }) }).catch(() => null);
  if (fnc.parecerDe !== pedido) return;
  fnc.parecer = r && r.ok ? await r.json() : { erro: r ? await erroDe(r) : "o programa não respondeu" };
  redesenharColunaDoFinanceiro();
}

function ligarColunaDoFinanceiro(raiz) {
  const pagar = raiz.querySelector("[data-fnc-pagar]");
  if (pagar) pagar.onclick = async () => {
    const id = pagar.dataset.fncPagar;
    const item = (fnc.dados.precisa || []).find((x) => String((x.ids || [])[0]) === id);
    const sim = await confirmar({ titulo: "Registrar o pagamento?", contexto: "Conversa › Financeiro",
      texto: (item ? item.titulo : "Esta conta") + " — com a data de hoje, como o botão do Financeiro. Dá para reabrir lá.", confirmar: "Registrar pagamento" });
    if (!sim) return;
    const r = await fetch("/api/financeiro/lancamentos/" + id + "/liquidar", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({}) }).catch(() => null);
    if (!r || !r.ok) { avisoCert("não registrei: " + (r ? await erroDe(r) : "sem resposta"), { tom: "erro" }); return; }
    notaDeFeitoNaConversa("Registrei o pagamento de " + (item ? item.titulo : "a conta") + ".");
    fnc.dados = await (await fetch("/api/financeiro?mes=" + fnc.mes)).json();
    desenharFinanceiroNaConversa();
    redesenharColunaDoFinanceiro();
  };
  const ver = raiz.querySelector("[data-fnc-ver]");
  if (ver) ver.onclick = () => abrirDestino("financeiro");
  const tarefas = raiz.querySelector("[data-fnc-tarefas]");
  if (tarefas) tarefas.onclick = () => criarTarefasDasSugestoes(fnc.dados || {}, fnc.mes);
}

/* ---------------------------------------------------------- o relatorio */

async function abrirRelatorioNaConversa(guardado) {
  await carregarRelatorioDaConversa();
  desenharRelatorioNaConversa();
  if (guardado) return;
  try {
    const contas = await (await fetch("/api/email/contas")).json();
    fnc.podeSozinho = Boolean(contas.pode_enviar_sozinho) && (contas.contas || []).some((c) => c.pode_enviar_sem_confirmar);
    fnc.temConta = (contas.contas || []).length > 0;
  } catch (err) { fnc.temConta = false; }
  abrirNoLado("formulario", {
    chave: "relatorio",
    html: htmlDaColunaDoRelatorio(),
    ligar: ligarColunaDoRelatorio,
    aoFechar: () => { fnc.rel = null; atualizarPostura(); },
  });
  atualizarPostura();
  pedirParecerDoMes();
}

async function carregarRelatorioDaConversa(gerar) {
  const c = (fnc.d || {}).campos || {};
  try {
    if (gerar) {
      const g = await fetch("/api/relatorios/financeiro/gerar", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ mes: fnc.mes, comparar: fnc.comparar }) });
      if (!g.ok) throw new Error(await erroDe(g));
    }
    const [r, f] = await Promise.all([
      fetch("/api/relatorios/financeiro?mes=" + fnc.mes + "&comparar=" + fnc.comparar).then((x) => x.json()),
      fetch("/api/financeiro?mes=" + fnc.mes).then((x) => x.json()),
    ]);
    fnc.rel = r;
    fnc.dados = f;
  } catch (err) {
    fnc.rel = { relatorio: null, erro: err.message, pdf: c.pdf, xlsx: c.xlsx };
  }
}

function desenharRelatorioNaConversa() {
  const alvo = fnc.caixa;
  const x = fnc.rel || {};
  const r = x.relatorio;
  if (!r) { alvo.innerHTML = '<div class="emc-falta">' + ic("error", 16) + "<span>Não consegui somar o mês: " + esc(x.erro || "") + "</span></div>"; return; }
  const baixar = (arq, rotulo) => arq ? '<a class="emc-botao" href="/api/relatorios/financeiro/arquivo?nome=' + encodeURIComponent(arq.nome) + '" download>' + glifo(arq.nome) + rotulo + "</a>" : "";
  const linha = (rotulo, valor, classe) => '<div class="fnc-extrato-linha' + (classe ? " " + classe : "") + '"><span>' + esc(rotulo) + "</span><b>" + valor + "</b></div>";
  const c = r.comparacao;
  const pct = (p) => (p === null || p === undefined ? "sem base" : (p >= 0 ? "+ " : "– ") + Math.abs(p) + "%");
  const maior = Math.max(1, ...r.categorias.map((k) => Math.max(k.entradas, k.saidas)));
  alvo.innerHTML = '<div class="fcn-tabela fnc-relatorio">' +
    '<div class="fcn-tabela-cabeca">' + ic("description", 16) + "<b>Relatório financeiro · " + esc(r.rotulo) + " " + esc(r.ano) + "</b><small>" +
    plural(r.lancamentos, "lançamento") + (r.corrente ? " · até " + dataCurta(r.ate) : "") + '</small><span class="vazio-flex"></span>' +
    baixar(x.pdf, "Baixar PDF") + baixar(x.xlsx, "Baixar XLSX") + "</div>" +
    '<div class="fnc-relatorio-corpo"><div class="fnc-extrato"><span class="emc-kicker">Extrato do mês</span>' +
    linha("Entradas", "+ " + fncReais(r.entradas), "entra") + linha("Saídas", "– " + fncReais(r.saidas), "sai") +
    linha("Resultado", (r.resultado >= 0 ? "+ " : "– ") + fncReais(r.resultado), "forte") +
    linha("A receber em aberto", fncReais(r.a_receber)) + linha("A pagar em aberto", fncReais(r.a_pagar)) + linha("Em atraso", r.atrasado ? fncReais(r.atrasado) : "0") +
    (c ? '<p class="fnc-contra">' + ic(c.resultado_pct === null || c.resultado_pct >= 0 ? "check_circle" : "schedule", 15) +
      "Contra " + esc(c.rotulo) + (c.inteiro ? "" : " (até o dia " + c.ate_o_dia + ")") + ": entradas " + pct(c.entradas_pct) + ", saídas " + pct(c.saidas_pct) + ".</p>" : "") +
    "</div>" +
    '<div class="fnc-categorias"><div class="fnc-cat-cabeca"><span class="emc-kicker">Por categoria</span><span class="vazio-flex"></span>' +
    '<span class="fnc-legenda"><i class="entra"></i>entradas</span><span class="fnc-legenda"><i class="sai"></i>saídas</span></div>' +
    (r.categorias.length
      ? r.categorias.map((k) => {
        const entra = k.entradas >= k.saidas;
        const valor = entra ? k.entradas : k.saidas;
        const classe = "fnc-cat-barra " + (entra ? "entra" : "sai");
        return '<div class="fnc-cat"><span>' + esc(k.rotulo) + '</span><span class="fnc-cat-trilho"><i class="' + classe + '" style="width:' + Math.max(1, Math.round(valor * 100 / maior)) + '%"></i></span>' +
          "<b>" + (entra ? "+ " : "– ") + fncReais(valor) + "</b></div>";
      }).join("")
      : '<p class="fnc-nota">Nada liquidado no mês ainda.</p>') +
    '<small class="fnc-nota">as barras saem do que foi efetivamente liquidado</small></div></div></div>';
}

function htmlDaColunaDoRelatorio() {
  const meses = [];
  const base = new Date();
  for (let i = 0; i < 12; i++) {
    const d = new Date(base.getFullYear(), base.getMonth() - i, 1);
    meses.push([d.getFullYear() + "-" + String(d.getMonth() + 1).padStart(2, "0"), i === 0 ? "Este mês" : maiuscula(FNC_MESES[d.getMonth()]) + " " + d.getFullYear()]);
  }
  const op = (lista, atual) => lista.map(([v, r]) => '<option value="' + v + '"' + (v === atual ? " selected" : "") + ">" + esc(r) + "</option>").join("");
  const comparar = [["", "sem comparar"]].concat(meses.slice(1).map(([v, r]) => [v, "vs. " + r.replace(/ \d{4}$/, "").toLowerCase()]));
  const fila = !fnc.podeSozinho;
  return '<div class="fcn fnc-coluna" data-fl-tipo="relatorio"><div class="fcn-topo"><span><b>Relatórios</b></span></div>' +
    '<span class="visoes fcn-abas fnc-abas"><button type="button" data-fnc-aba="dia">Tarefas do dia</button><button type="button" class="ativa">Financeiro</button>' +
    '<button type="button" data-fnc-aba="acoes">Ações de IA</button></span>' +
    '<div class="fcn-corpo"><div class="fcn-par"><label class="fcn-campo meia"><span class="fcn-rotulo">Período</span><select data-fnc-mes="1">' + op(meses, fnc.mes) + "</select></label>" +
    '<label class="fcn-campo meia"><span class="fcn-rotulo">Comparar</span><select data-fnc-comparar="1">' + op(comparar, fnc.comparar) + "</select></label></div>" +
    htmlDoParecer() +
    (fnc.temConta
      ? '<div class="fnc-secao"><div class="fnc-secao-cabeca"><b>Enviar por e-mail</b><small>' + (fila ? "passa por Aprovações" : "sai no seu sim") + "</small></div>" +
        '<div class="fnc-para">' + fnc.para.map((x, i) => '<span class="emc-chip"><span class="emc-chip-avatar">' + esc(fcnIniciais(x.nome || x.email)) + "</span><b>" + esc(x.nome || x.email) + "</b>" +
          '<button type="button" data-fnc-tirar="' + i + '" aria-label="Tirar">' + ic("close", 14) + "</button></span>").join("") +
        '<input type="text" class="emc-add" data-fnc-add="1" list="fnc-emails" placeholder="adicionar…" autocomplete="off"></div>' +
        '<datalist id="fnc-emails"></datalist>' +
        '<button type="button" class="primario fnc-enviar" data-fnc-enviar="1">' + ic("mail", 15) + "Enviar PDF e XLSX</button></div>"
      : "") +
    htmlDasSugestoes() + "</div></div>";
}

function ligarColunaDoRelatorio(raiz) {
  raiz.querySelectorAll("[data-fnc-aba]").forEach((b) => { b.onclick = () => abrirDestino("relatorios"); });
  const mudarPeriodo = async () => {
    fnc.mes = raiz.querySelector("[data-fnc-mes]").value;
    fnc.comparar = raiz.querySelector("[data-fnc-comparar]").value;
    fnc.parecer = null;
    await carregarRelatorioDaConversa(true);
    desenharRelatorioNaConversa();
    redesenharColunaDoFinanceiro();
    pedirParecerDoMes();
  };
  raiz.querySelector("[data-fnc-mes]").onchange = mudarPeriodo;
  raiz.querySelector("[data-fnc-comparar]").onchange = mudarPeriodo;
  const add = raiz.querySelector("[data-fnc-add]");
  if (add) {
    fetch("/api/cadastros").then((r) => r.json()).then((d) => {
      const lista = $("fnc-emails");
      if (lista) lista.innerHTML = (d.fichas || []).filter((f) => f.email).map((f) => '<option value="' + esc(f.email) + '">' + esc(f.nome) + "</option>").join("");
      fnc.fichas = d.fichas || [];
    }).catch(() => null);
    const juntar = () => {
      enderecosDe(add.value).forEach((email) => {
        if (fnc.para.some((x) => x.email === email)) return;
        const ficha = (fnc.fichas || []).find((f) => String(f.email || "").toLowerCase() === email.toLowerCase());
        fnc.para.push({ email: email, nome: ficha ? ficha.nome : "" });
      });
      add.value = "";
      redesenharColunaDoFinanceiro();
      const de_novo = document.querySelector("#lado-ferramenta [data-fnc-add]");
      if (de_novo) de_novo.focus();
    };
    add.onkeydown = (e) => { if (e.key === "Enter" || e.key === ",") { e.preventDefault(); juntar(); } };
    add.onchange = juntar;
  }
  raiz.querySelectorAll("[data-fnc-tirar]").forEach((b) => { b.onclick = () => { fnc.para.splice(Number(b.dataset.fncTirar), 1); redesenharColunaDoFinanceiro(); }; });
  const enviar = raiz.querySelector("[data-fnc-enviar]");
  if (enviar) enviar.onclick = () => enviarRelatorioPelaConversa(enviar);
  const tarefas = raiz.querySelector("[data-fnc-tarefas]");
  if (tarefas) tarefas.onclick = () => criarTarefasDasSugestoes(fnc.dados || {}, fnc.mes);
}

/* O envio: o sim primeiro, e a rota de sempre (/api/email/enviar), com o PDF
   e a planilha do Acervo como anexos. */
async function enviarRelatorioPelaConversa(botao) {
  const x = fnc.rel || {};
  const r = x.relatorio;
  if (!fnc.para.length) { avisoCert("falta para quem vai", { tom: "erro" }); return; }
  if (!x.pdf || !x.xlsx) { await carregarRelatorioDaConversa(true); }
  const pdf = (fnc.rel || {}).pdf;
  const xlsx = (fnc.rel || {}).xlsx;
  if (!pdf || !xlsx) { avisoCert("não achei o PDF e a planilha do mês", { tom: "erro" }); return; }
  const assunto = "Relatório financeiro · " + r.rotulo + " " + r.ano;
  const corpo = "Olá,\n\nSegue o relatório financeiro de " + r.rotulo + " de " + r.ano + (r.corrente ? " (até " + dataCurta(r.ate) + ")" : "") +
    ", em PDF, e a planilha com os lançamentos do mês.\n\nEntradas: R$ " + fncReais(r.entradas) + "\nSaídas: R$ " + fncReais(r.saidas) +
    "\nResultado: R$ " + fncReais(r.resultado) + "\n\nAtenciosamente,";
  const sim = await confirmar({ titulo: "Enviar o relatório?", contexto: "Conversa › Relatório",
    texto: "Para " + fnc.para.map((p) => p.nome || p.email).join(", ") + ": “" + assunto + "”, com o PDF e a planilha.\n" +
      (fnc.podeSozinho ? "Sai agora. Não dá para desfazer." : "Vai para Aprovações: só sai depois do sim lá."),
    confirmar: fnc.podeSozinho ? "Enviar" : "Mandar para Aprovações" });
  if (!sim) return;
  botao.disabled = true;
  const d = await mandarPedido({ conta_id: "", para: fnc.para.map((p) => p.email).join(", "), cc: "", cco: "", assunto: assunto, corpo: corpo, corpo_html: "",
    anexos: [pdf.caminho, xlsx.caminho], responder_a: "" });
  botao.disabled = false;
  if (!d) return;
  const aguardando = Boolean(d.aguardando_aprovacao);
  const feito = await fetch("/api/trabalhos/" + estado.trabalhoId + "/fazer", { method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ tipo: "email", campos: { aguardando: aguardando, para: fnc.para.map((p) => p.email), assunto: assunto } }) }).then((y) => (y.ok ? y.json() : null)).catch(() => null);
  notaDeFeitoNaConversa(feito && feito.resumo ? feito.resumo + "." : (aguardando ? "O relatório está esperando o seu sim em Aprovações." : "Enviei o relatório."));
  fnc.para = [];
  redesenharColunaDoFinanceiro();
}

function financeiroAbertoNoLado() {
  return Boolean(papelDoLado() === "formulario" && document.querySelector("#lado-ferramenta [data-fl-tipo='financeiro'], #lado-ferramenta [data-fl-tipo='relatorio']"));
}
